# CircuitPython
# pilomar/circuitpython/tiny2350-tmc2209/pilomar/tmc2209.py
# Driver for TMC2209 stepper motor controller. 
# - Appears to be based upon the TMCStepper C library code. All the original rights respected here.
# 
# A good explanation of the technicalities of the TMC2209 were found online :-
#     Tutorial: https://www.programming-electronics-diy.xyz/2023/12/tmc2209-stepper-driver-module-tutorial.html 
#     Tutorial: https://learn.watterott.com/silentstepstick/
#     Datasheet: https://www.analog.com/media/en/technical-documentation/data-sheets/tmc2209_datasheet_rev1.09.pdf
#     
# This code branched from tproffen's fork of the pilomar project.
# Some comments and explanations added based upon online sources and spec sheet.

# NOTE: The TMC2209 supports multiple operation methods, this library refers to many of these methods however it is only
# developed and tested for HALF-DUPLEX UART communication with 'STEP PIN' control. The other operating methods are inherited 
# from the original source of this code and have not been tested or developed further.

# DEBUG: If you get no responses or incomplete responses from the TMC2209 remember consider the following.
#   The 'communication_pause' parameter is critical, can lead to incomplete responses.
#   The VIO pin on tmc2209 only sets the communication voltage, there MUST be power to VS pin for the chip to actually work.
#   Try a logic analyser to make sure that the TMC2209 is RECEIVING messages.
#   Try different speeds on the UART connection. ('communication_pause' may need to change in response)
#   Remember it's a HALF-DUPLEX UART implementation. Make sure there is a resistor in the RX/TX circuit.

import time
import board
import busio
import digitalio
import math
import struct

from pilomar.enum import *

#-----------------------------------------------------------------------------------------------

class reg(Enum): # Inherit from pilomar/enum.py
    # addresses of REGISTERS for TMC2209 chip.
    GCONF           =   0x00        # GLOBAL CONFIGURATION FLAGS
    GSTAT           =   0x01        # DRIVER STATUS FLAGS
    IFCNT           =   0x02        # INTERFACE TRANSMISSION COUNTER.
    IOIN            =   0x06        # READ STATUS OF ALL INPUT PINS.
    IHOLD_IRUN      =   0x10        # DRIVER CURRENT CONTROL.
    TSTEP           =   0x12        # MEASURED TIME BETWEEN 1/256 MICROSTEPS.
    VACTUAL         =   0x22        # SELECT TO MOVE BY STEP SIGNAL or UART CONFIGURATION.
    TCOOLTHRS       =   0x14        # CONTROL COOLSTEP LOWER VELOCITY THRESHOLD.
    SGTHRS          =   0x40        # STALLGUARD SETTING.
    SG_RESULT       =   0x41        # STALLGUARD STATUS.
    MSCNT           =   0x6A        # MICROSTEP COUNTER.
    CHOPCONF        =   0x6C        # CHOPPER AND DRIVER CONFIGURATION.
    DRVSTATUS       =   0x6F        # DRIVER STATUS FLAGS. "DRV_STATUS" in spec sheet.

    # GCONF # Identify the different bits in the GLOBAL CONFIGURATION FLAGS.
    i_scale_analog      = 1<<0      # 0th bit (lowest). (0 / 1) # Defining current limit on the stepper. # 0 = Use internal 5VOUT (UART control). # 1 = Use external VREF. (External control).
    internal_rsense     = 1<<1      # 1st bit. (0 / 2) # 0 = Use external sense resitors. # 2 = Use internal sense resistors.
    en_spreadcycle      = 1<<2      # 2nd bit. (0 / 4) # 0 = StealthChop PWM enabled. # 4 = SpreadCycle enabled.
    shaft               = 1<<3      # 3rd bit. (0 / 8) # 0 = Forward motor direction. # 8 = Reverse motor direction.
    index_otpw          = 1<<4      # 4th bit. (0 / 16) # 0 = INDEX = microstep position. # 16 = INDEX = Temperature prewarning.
    index_step          = 1<<5      # 5th bit. (0 / 32) # 0 = INDEX defined by index_otpw. # 32 = INDEX show step pulses.
    pdn_disable         = 1<<6      # 6th bit. (0 / 64) # 0 = PDN_UART controls standstill current. # 64 = PDN_UART disabled (use UART interface instead).
    mstep_reg_select    = 1<<7      # 7th bit. (0 / 128) # 0 = Microsteps selected by PINS. # 128 = Microsteps defined by MRES register.

    # GSTAT # Identify the different bits in the DRIVER STATUS FLAGS.
    reset               = 1<<0      # 0th bit (lowest). (0 / 1) # 0 = Normal operation. # 1 = IC has reset since last read.
    drv_err             = 1<<1      # 1st bit (0 / 2) # 0 = Normal operation. # 2 = Overtemp or short circuit detected.
    uv_cp               = 1<<2      # 2nd bit (0 / 4) # 0 = Normal operation. # 4 = Charge pump undervoltage.

    # CHOPCONF # Identify the different bits in the CHOPCONF status value.
    toff0               = 1<<0      # 0th bit (lowest). (0 / 1) # TOFF off time and driver enable.
    toff1               = 1<<1      # 1st bit. (0 / 2)
    toff2               = 1<<2      # 2nd bit. (0 / 4)
    toff3               = 1<<3      # 3rd bit. (0 / 8)
    vsense              = 1<<17     # 17th bit. (0 / 131702) # 0 = Normal, robust signal, low sensitivity. # 131702 = Reduced power, weaker signal, high sensitivity.
    msres0              = 1<<24     # 24th bit. (0 / 16777216) # Microstep resolution when selected by GCONF.
    msres1              = 1<<25     # 25th bit. (0 / 33554432)
    msres2              = 1<<26     # 26th bit. (0 / 67108864)
    msres3              = 1<<27     # 27th bit. (0 / 134217728)
    intpol              = 1<<28     # 28th bit. (0 / 268435456) # 0 = Microstep as directed. # 268435456 = Extrapolate to 256 microsteps for smooth operation.

    # IOIN # Identify the different bits in the IOIN status value.
    io_enn              = 1<<0      # 0th bit (lowest). (0 / 1) # Value of ENN pin.
    io_0a               = 1<<1      # 1st bit. (0 / 2) # Value of '0' pin. (?!?)
    io_ms1              = 1<<2      # 2nd bit. (0 / 4) # Value of MS1 pin.
    io_ms2              = 1<<3      # 3rd bit. (0 / 8) # Value of MS2 pin.
    io_diag             = 1<<4      # 4th bit. (0 / 16) # Value of DIAG pin.
    io_0b               = 1<<5      # 5th bit. (0 / 32) # Value of '0' pin. (?!?)
    io_pdn_uart         = 1<<6      # 6th bit. (0 / 64) # Value of PDN_UART pin.
    io_step             = 1<<7      # 7th bit. (0 / 128) # Value of STEP pin.
    io_spread           = 1<<8      # 8th bit. (0 / 256) # Value of SPREAD ENABLE pin.
    io_dir              = 1<<9      # 9th bit. (0 / 512) # Value of DIR pin.

    # DRVSTATUS # Identify the different bits in the DRVSTATUS value.
    stst                = 1<<31     # 1st bit. (0 / 2)
    stealth             = 1<<30     # 30th bit. (0 / 1073741824)
    cs_actual           = 31<<16    # 5 bits from 16th bit (0 / 65536 - 1048575)
    t157                = 1<<11     # 11th bit. (0 / 2048)
    t150                = 1<<10     # 10th bit. (0 / 1024)
    t143                = 1<<9      # 9th bit. (0 / 512)
    t120                = 1<<8      # 8th bit. (0 / 256)
    olb                 = 1<<7      # 7th bit. (0 / 128)
    ola                 = 1<<6      # 6th bit. (0 / 64)
    s2vsb               = 1<<5      # 5th bit. (0 / 32)
    s2vsa               = 1<<4      # 4th bit. (0 / 16)
    s2gb                = 1<<3      # 3rd bit. (0 / 8)
    s2ga                = 1<<2      # 2nd bit. (0 / 4)
    ot                  = 1<<1      # 1st bit. (0 / 2)
    otpw                = 1<<0      # 0th bit (lowest). (0 / 1)

    # IHOLD_IRUN # Identify the different bits in the IHOLD_IRUN status value.
    ihold               = 31<<0     # 5 bits from 0th bit to 4th bit ( 0 / 0 - 31)
    irun                = 31<<8     # 5 bits from 8th bit (0 / 256 - 4095)
    iholddelay          = 15<<16    # 4 bits from 16th bit (0 / 65536 - 1048575)

    # SGTHRS # Identify the different bits in the SGTHRS status value.
    sgthrs              = 255<<0    # 8 bits from 0th bit. (0 / 0 - 255)

    # Microstep resolutions (?)
    mres_256 = 0                    # 256 microsteps.
    mres_128 = 1                    # 128 microsteps.
    mres_64 = 2                     # 64 microsteps.
    mres_32 = 3                     # 32 microsteps.
    mres_16 = 4                     # 16 microsteps.
    mres_8 = 5                      # 8 microsteps.
    mres_4 = 6                      # 4 microsteps.
    mres_2 = 7                      # 2 microsteps.
    mres_1 = 8                      # Full stepping.

#-----------------------------------------------------------------------------------------------

class Direction(Enum): # Inherit from pilomar/enum.py
    """ Define movement direction of the motor. """
    CCW = 0                         # Counter clockwise.
    CW = 1                          # Clockwise. 

class MovementAbsRel(Enum): # Inherit from pilomar/enum.py
    """ Define movement absolute or relative. """
    ABSOLUTE = 0                    # Absolute movement. 
    RELATIVE = 1                    # Relative movement.

class MovementPhase(Enum): # Inherit from pilomar/enum.py
    """ Define the different movement phases. """
    STANDSTILL = 0                  # Motor is at rest.
    ACCELERATING = 1                # Motor is accelerating.
    MAXSPEED = 2                    # Motor is at full speed.
    DECELERATING = 3                # Motor is decelerating.

class StopMode(Enum): # Inherit from pilomar/enum.py
    """ Define the different STOP modes """
    NO = 0                          # Not stopped.
    SOFTSTOP = 1                    # Soft stop.
    HARDSTOP = 2                    # Hard stop.

#-----------------------------------------------------------------------------------------------
# Main Stepper motor class for TMC2209 (UART)
#-----------------------------------------------------------------------------------------------
class TMCStepper():

    mtr_id = 0                      # Motor ID.
    ser = None                      # Not used.
    r_frame  = [0x55, 0, 0, 0  ] # Data format used for reading registers. [0] = ?, [1] = Address, [2] = Register, [3] = CRC
    w_frame  = [0x55, 0, 0, 0 , 0, 0, 0, 0 ] # Data format used for writing to registers. 
    communication_pause = 0         # Delay between REQUESTING data and trying to read it. 0.008 works well on Pico2 & TMC2209 @ 19200 baud.
    error_handler_running = False   # Indicates ERROR raised. (Seems to latch?)

    _msres = -1                     # Chosen microstepping resolution.
    _steps_per_rev = 0              # Chosen microsteps per revolution.
    _fullsteps_per_rev = 200        # Full steps per revolution.
    _direction = True               # Motor direction.
    _stop = StopMode.NO             # Motor STOP mode.
    _starttime = 0                  # When did move START under UART defined move?
    _sg_callback = None

    #_msres = -1                     # Chosen microstepping resolution. (*Q* DUPLICATE)
    #_steps_per_rev = 0              # Chosen microsteps per revolution. (*Q* DUPLICATE)
    #_fullsteps_per_rev = 400        # Full steps per revolution. (*Q* DUPLICATE)

    _current_pos = 0                # current position of stepper in steps
    _target_pos = 0                 # the target position in steps
    _speed = 0.0                    # the current speed in steps per second
    _max_speed = 1.0                # the maximum speed in steps per second
    _max_speed_homing = 200         # the maximum speed in steps per second for homing
    _acceleration = 1.0             # the acceleration in steps per second per second
    _acceleration_homing = 10000    # the acceleration in steps per second per second for homing
    _sqrt_twoa = 1.0                # Precomputed sqrt(2*_acceleration)
    _step_interval = 0              # the current interval between two steps
    _min_pulse_width = 1            # minimum allowed pulse with in microseconds
    _last_step_time = 0             # The last step time in microseconds
    _n = 0                          # step counter
    _c0 = 0                         # Initial step size in microseconds
    _cn = 0                         # Last step size in microseconds
    _cmin = 0                       # Min step size in microseconds based on maxSpeed
    _sg_threshold = 100             # threshold for stallguard
    
    _movement_abs_rel = MovementAbsRel.ABSOLUTE
    _movement_phase = MovementPhase.STANDSTILL
    
    _baud_rates = {'9600':{'rate':9600,'pause':0.016},
                   '19200':{'rate':19200,'pause':0.008},
                   '115200':{'rate':115200,'pause':0.004}} # dictionary of recommended baud rates and communication pauses.

    #-----------------------------------------------------------------------------------------------

    @staticmethod
    def RecommendComPause(baudrate):
        """ Return NONE if baudrate is no recognised, else the recommended communication pause time. """
        result = TMCStepper._baud_rates.get(str(int(baudrate)),{})
        result = result.get('pause',None)
        return result

    #-----------------------------------------------------------------------------------------------
    
    def __init__(self, uart, LogFile, ExceptionCounter, 
                 mtr_id = 0, communication_pause = 0.008, pin_step=-1, pin_dir=-1, pin_en=-1,name=None,peak_current=2.0):
        """ Initialise new instance of a TMC2209 driver. 
            Parameters --------------------------------------------        
            uart                     uart comms instance.
            LogFile                  pilomar logger instance.
            ExceptionCounter         pilomar exception counter instance.
            mtr_id                   integer ID of the motor.
            communication_pause      set communication delay (seconds)
            pin_step                 which GPIO pin handles STEP signals.
            pin_dir                  which GPIO pin handles DIRECTION signals.
            pin_en                   which GPIO pin handles ENABLE signals. 
            name                     optional motor name (defaults to 'motor_00' based upon mtr_id) 
            peak_current             Rated peak current for the motor coil. """ 
        #print("TMCStepper.__init__(): Begin")
        self.mtr_id = mtr_id # Unique ID for the motor.
        if name != None: self.Name = name
        else:
            self.Name = "motor_" + ("0000" + str(self.mtr_id))[-2:]
        self.label = "TMCStepper(" + str(self.mtr_id) + ":" + self.Name + ")" # For consistent labeling in logs and messages.
        self.LogFile = LogFile # Which pilomar logger is in use?
        self.DriverFaultCount = 0 # How many fault conditions have occurred?
        self.DriverFault = False # Is the stepper considered in FAULT state?
        self.ExceptionCounter = ExceptionCounter # Which pilomar exceptioncounter is in use?
        if mtr_id < 0 or mtr_id > 3: # ID must be 0,1,2 or 3 (2 bit binary value).
            print(self.label+".__init__(",mtr_id,") invalid. Must be 0 ... 3")
            self.ExceptionCounter.Raise(info="invalid mtr_id")
        self.communication_pause = communication_pause # Set the delay in communication.
        self.peak_current = peak_current # Peak current per motor coil.
        self.communication_ok = True # Is communication working? (YES until we find an error)
        # Record register values that have been set but which cannot be read back.
        self.irun_value = None # CurrentScale (CS) setting for RUN current.
        self.ihold_value = None # CurrentScale (CS) setting for HOLD current.
        self.ihold_delay_value = None # Clock cycle multiplier before switching from RUN to HOLD current.
        self.run_current_actual = None # Selected RMS run current.
        self.flush_after_write = True # Flush UART input buffer after each register write. (Prevents false alarms about junk in input buffer)
        
        self.uart = uart # Define the UART port (?)
        self._pin_step = pin_step # Define the STEP GPIO pin.
        self._pin_dir = pin_dir # Define the DIRECTION GPIO pin.
        self._pin_en = pin_en # Define the ENABLE GPIO pin.
        self._vactual = 0 # Are we moving via the STEP PIN or via TMC2209 motion control?

        #if False: # Test stuff on the UART line - for the logic analyser to look at.
        #    for i in range(5):
        #        print(self.label+".__init__(): send_int(",i,")")
        #        self.send_int_as_byte(i) # Send single byte values.
        #        time.sleep(0.5) # Pause 1 second.
        #
        ## *Q* Should validate communication at this point?
        #
        #if False:
        #    if False: 
        #        print(self.label+".__init__(): Send 0xA0")
        #        self.send_a0() # Some instructions suggest sending this to initialize UART line.
        #
        #        time.sleep(0.5) # Pause 1 second.
        #
        #        print(self.label+".__init__(): Send 0x05")
        #        self.send_05()
        #
        #        time.sleep(0.5) # Pause 1 second.
        #
        #    print(self.label+".__init__(): Call read_drv_status()")
        #    self.read_drv_status()  # Record the initial drive status in the Log
        #    print(self.label+".__init__(): Returned from read_drv_status()")
        #    print(self.label+".__init__(): Call current_condition()")
        #    self.current_condition()
        #    print(self.label+".__init__(): Returned from current_condition()")
            
        #print(self.label+".__init__(): Complete")

    #-----------------------------------------------------------------------------------------------

    def IncrementDriverFault(self): 
        """ Call this each time a fault is detected. 
            When a threshold is reached the stepper is switched to FAULT mode 
            and no further actions will be taken. 
            
            To clear fault mode, reset the motor - which will also reset fault counter and status. """
        self.DriverFaultCount += 1
        if self.DriverFaultCount >= 10 and not self.DriverFault: # After 10 communication faults, set the device to 'FAULT' status. 
            self.LogFile.Log("TMCStepper(",self.label,").IncrementDriverFault():",self.DriverFaultCount,"threshold reached. Setting FAULT condition.")
            print("TMCStepper(",self.label,").IncrementDriverFault():",self.DriverFaultCount,"threshold reached. Setting FAULT condition.")
            self.SetDriverFault()
            
    #-----------------------------------------------------------------------------------------------

    def SetDriverFault(self):
        """ Mark driver as failed / faulty. """
        self.DriverFault = True 
            
    #-----------------------------------------------------------------------------------------------

    def DriverFailed(self):
        """ Decide if the driver is healthy. """
        return self.DriverFault
            
    #-----------------------------------------------------------------------------------------------

    def ClearDriverFault(self):
        """ Mark driver as healthy. """
        if self.DriverFault: 
            print("TMCStepper(",self.label,").ClearDriverFault(): FAULT condition released.")
            self.DriverFault = False
        self.DriverFaultCount = 0
            
    #-----------------------------------------------------------------------------------------------
    
    def compute_crc8_atm(self, datagram, initial_value=0):
        """ Calculate cyclic redundancy check value.
            Parameters ----------------------------------------------------
            datagram : A chunk of data that needs the CRC calculating (bytestream).
            initial_value : Any initial value for the CRC being calculated.
            Outputs -------------------------------------------------------
            The CRC value for the data received. 
            
            Used by:
            -   self.reg_read() 
            -   self.read_int()
            -   self.write_reg() """
        crc = initial_value # Start with initial or inherited CRC value.
        # Iterate bytes in data
        for byte in datagram: # Each byte in time from the bytestream.
            # Iterate bits in byte
            for _ in range(0, 8): # Repeat for 8 bits in the byte. Calculate CRC.
                if (crc >> 7) ^ (byte & 0x01):
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
                # Shift to next bit
                byte = byte >> 1 # Right shift 1 bit.
        return crc

    #-----------------------------------------------------------------------------------------------
    
    def read_reg(self, register):
        """ Read register from TMC2209 via UART channel. 
            Discards any previous data in buffers.
            Sends register request over uart.
            Returns 12 byte response. 
            
            Parameters -------------------------------------------------------
            register : The register to interrogate. 
            Outputs ----------------------------------------------------------
            12 bytes read from TMC2209.
            If one-wire UART is being used, the first 4 bytes are the outbound register request. 
                                            next 4 bytes are register ID.
                                            last 4 bytes are register VALUE. 
                                            
            Used by:
            -   self.read_int() """
        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.read_reg(",register,"): Comms disabled.")
            return False
            
        if self.uart.in_waiting > 0: # There's something in the buffer.
            discard_length = self.uart.in_waiting
            discarded = self.uart.read(discard_length) # Read the response.
            print(self.label+".read_reg(",register,"): discarded",discard_length,"bytes '",discarded,"'")
            self.uart.reset_input_buffer() # Empty the input buffer.

        # Create query frame.
        self.r_frame[1] = self.mtr_id # Assign motor ID.
        self.r_frame[2] = register # Define which register to read.
        self.r_frame[3] = self.compute_crc8_atm(self.r_frame[:-1]) # Calculate CRC for the request.
        rtn = self.uart.write(bytearray(self.r_frame)) # Convert to bytestream and send.
        if rtn != len(self.r_frame): # Did it work?
            self.LogFile.Log(self.label+".read_reg("+str(register)+"): uart.write() failed.")
            print(self.label+".read_reg("+str(register)+"): uart.write() failed.")
            self.ExceptionCounter.Raise()
            return False

        self.sleep(self.communication_pause) # Let the TMC2209 process the request.
        rtn = self.uart.read(12) # Read the response.
        #print(self.label+".read_reg("+str(register)+"): returned",rtn,"(length",len(rtn),", type",type(rtn),") expect 12 bytes.")
        self.sleep(self.communication_pause) # Pause before continuing.

        return rtn # Return the register value.

    #-----------------------------------------------------------------------------------------------
    
    def read_int(self, register, tries=5):
        """ Read an integer from the register.
            Parameters --------------------------------------
            register: The register to interrogate.
            tries: Maximum attempts to read the value. 
            Outputs -----------------------------------------
            returned data. (-1) if timed out.
            
            Used by:
            -   self.write_reg_check()
            -   self.handle_error() <- Recursive?
            -   self.read_drv_status()
            -   self.read_gconf()                
            -   self.read_gstat()
            -   self.clear_gstat()
            -   self.read_ioin()
            -   self.read_chopconf()
            -   self.get_direction_reg()
            -   self.set_direction_reg()
            -   self.get_iscale_analog()
            -   self.set_iscale_analog()
            -   self.get_vsense()
            -   self.set_vsense()
            -   self.get_internal_rsense()
            -   self.set_internal_rsense()
            -   self.set_pdn_disable()
            -   self.get_spreadcycle()
            -   self.set_spreadcycle()
            -   self.get_interpolation()
            -   self.set_interpolation()
            -   self.get_toff()
            -   self.set_toff()
            -   self.read_microstepping_resolution()
            -   self.get_microstepping_resolution()
            -   self.set_microstepping_resolution()
            -   self.set_mstep_resolution_reg_select()
            -   self.get_interface_transmission_counter()
            -   self.get_tstep()
            -   self.get_stallguard_result()
            -   self.set_stallguard_threshold()
                
            """
            
        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.read_int(",register,"): Comms disabled.")
            return False
            
        while True:
            tries -= 1 # Decrement the tries left.
            rtn = self.read_reg(register) # Read the register.
            #print(self.label+".read_int("+str(register)+"): Returned",rtn,",(length",len(rtn),", type",type(rtn),"), expect 12 bytes.")
            rtn_data = rtn[7:11] # Extract data.
            not_zero_count = len([elem for elem in rtn if elem != 0]) # How many non-zero bytes are in the response?
            if len(rtn_data) == 0:
                print(self.label+".read_int("+str(register)+"): No response: "+str(len(rtn_data))+" data bytes, "+str(len(rtn))+" total bytes")
                print(self.label+".read_int("+str(register)+"): No response: Check VMOT, address, UART pin assignment, com_delay.")
                self.LogFile.Log(self.label+".read_int("+str(register)+"): No response: "+str(len(rtn_data))+" data bytes, "+str(len(rtn))+" total bytes")
                self.ExceptionCounter.Raise(info="no response")
            elif (len(rtn) < 12 or not_zero_count == 0):
                print(self.label+".read_int("+str(register)+"): short response: "+str(len(rtn_data))+" data bytes, "+str(len(rtn))+" total bytes")
                self.LogFile.Log(self.label+".read_int("+str(register)+"): short response: "+str(len(rtn_data))+" data bytes, "+str(len(rtn))+" total bytes")
                self.ExceptionCounter.Raise(info="short response")
            elif rtn[11] != self.compute_crc8_atm(rtn[4:11]):
                print(self.label+".read_int("+str(register)+": crc mismatch, received:",rtn[11],",expected:",self.compute_crc8_atm(rtn[4:11]))
                self.LogFile.Log(self.label+".read_int("+str(register)+": crc mismatch")
                self.ExceptionCounter.Raise(info="crc mismatch")
            else: # All good, take this result.
                self.communication_ok = True
                break

            if tries <= 0: # Timeout.
                print(self.label+".read_int("+str(register)+"): Retry limit")
                self.LogFile.Log(self.label+".read_int("+str(register)+"): Retry limit")
                self.handle_error(info="read_int()")
                self.communication_ok = False
                self.IncrementDriverFault() # Increase the number of faults that have occurred. If too many, mark the driver as failed.
                return -1

            #print(self.label+".read_int("+str(register)+"): Retries left",tries)

        val = struct.unpack(">i",rtn_data)[0] # Convert 'bytes' into big-endian unsigned integer. Return 1st entry in the calculated tuple.
        return val

    #-----------------------------------------------------------------------------------------------

    def send_int_as_byte(self,value):
        """ Send a single byte of any particular value. """

        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.send_int_as_byte(",value,"): Comms disabled.")
            return False
        
        print("send_int_as_byte:",value,"=",bin(value),"=",str(bytearray([value])))
        _ = self.uart.write(bytearray([value]))
        self.sleep(self.communication_pause)

    #-----------------------------------------------------------------------------------------------

    def send_a0(self):
        """ send 0xA0 byte. """
        
        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.send_a0(): Comms disabled.")
            return False
        
        _ = self.uart.write(bytearray([0xA0]))
        self.sleep(self.communication_pause)

    #-----------------------------------------------------------------------------------------------

    def send_05(self):
        """ send 0x05 byte. """
        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.send_05(): Comms disabled.")
            return False
        
        _ = self.uart.write(bytearray([0x05]))
        self.sleep(self.communication_pause)

    #-----------------------------------------------------------------------------------------------
    
    def write_reg(self, register, val):
        """ 
            Parameters --------------------------------------------        
            register 
            val 
            
            Used by:
            -   self.write_reg_check() 
                """
        self.uart.reset_input_buffer() # Drop any previous input ready for fresh input.

        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.write_reg(",register,val,"): Comms disabled.")
            return False

        self.w_frame[1] = self.mtr_id # Set motor ID.
        self.w_frame[2] = register | 0x80  # set write bit
        self.w_frame[3] = 0xFF & (val>>24) # Split register into individual bytes. Right shift 24bits (3 bytes)
        self.w_frame[4] = 0xFF & (val>>16) # Right shift 16 bits (2 bytes)
        self.w_frame[5] = 0xFF & (val>>8) # Right shift 8 bits (1 byte)
        self.w_frame[6] = 0xFF & val # Retain only lowest 8 bits
        self.w_frame[7] = self.compute_crc8_atm(self.w_frame[:-1]) # Calculate CRC on the message.

        rtn = self.uart.write(bytes(self.w_frame)) # Send the message to the TMC2209
        if rtn != len(self.w_frame): # Did it work?
            self.LogFile.Log(self.label+".write_reg("+str(register)+","+str(val)+"): uart.write failed.")
            print(self.label+".write_reg("+str(register)+","+str(val)+"): uart.write failed.")
            self.ExceptionCounter.Raise()
            return False
        self.sleep(self.communication_pause) # Pause to allow the TMC2209 to process the request.
        # Should this then flush the outbound traffic from the RX buffer?
        if self.flush_after_write: self.uart.reset_input_buffer() # Empty the input buffer. *Q* Just checking if this stops all the false error messages. 12.Oct.2025
        return True # Success.

    #-----------------------------------------------------------------------------------------------
    
    def write_reg_check(self, register, val, tries=5):
        """ Check if a WRITE command succeeded with the TMC2209. 
            Parameters -----------------------------------------------------------
            register : The register to write.
            val : The value to write.
            tries : Max retries. 
            
            Used by:
            -   self.self.clear_gstat() 
            -   self.set_direction_reg()
            -   self.set_iscale_analog()
            -   self.set_vsense()
            -   self.set_internal_rsense()
            -   self.set_irun_ihold()
            -   self.set_pdn_disable()
            -   self.set_spreadcycle()
            -   self.set_interpolation()
            -   self.set_toff()
            -   self.set_microstepping_resolution()
            -   self.set_mstep_resolution_reg_select()
            -   self.set_vactual()
            -   self.set_stallguard_threshold()
            -   self.set_coolstep_threshold()
                
                """
                
        if self.DriverFailed(): # Driver has failed. Don't try further comms. 
            print(self.label,"TMCStepper.write_reg_check(",register,val,"): Comms disabled.")
            return False
                
        #print(self.label+".write_reg_check(",register,val,tries,"): Call initial read_int(",reg.IFCNT,")")
        ifcnt1 = self.read_int(reg.IFCNT) # Get the interface counter. We expect this to change.
        #print(self.label+".write_reg_check(",register,val,tries,"): Returned from initial read_int(",reg.IFCNT,")",ifcnt1)

        if ifcnt1 == 255: # Keep to 8 bit values.
            ifcnt1 = -1

        while True:
            #print(self.label+".write_reg_check(",register,val,tries,"): Call write_reg(",register,",",val,")")
            self.write_reg(register, val) # Send the write request to the TMC2209.
            #print(self.label+".write_reg_check(",register,val,tries,"): Returned from write_reg(",register,",",val,")")
            tries -= 1 # Decrement the attempt counter.
            #print(self.label+".write_reg_check(",register,val,tries,"): Call confirmation read_int(",reg.IFCNT,")")
            ifcnt2 = self.read_int(reg.IFCNT) # Check the latest value of the interface counter. This should have changed.
            #print(self.label+".write_reg_check(",register,val,tries,"): Returned from confirmation read_int(",reg.IFCNT,")",ifcnt2)
            if ifcnt1 >= ifcnt2: # If ifcnt2 isn't higher then it failed.
                self.LogFile.Log(self.label+".write_reg_check(): Writing to UART register failed")
                print(self.label+".write_reg_check(): Writing to UART register failed")
                self.ExceptionCounter.Raise()
            else: # Success.
                return True
            if tries<=0: # Timeout.
                self.LogFile.Log(self.label+".write_reg_check("+str(register)+","+str(val)+": retry limit.")
                print(self.label+".write_reg_check("+str(register)+","+str(val)+": retry limit.")
                self.handle_error()
                self.IncrementDriverFault() # Increase the number of faults that have occurred. If too many, mark the driver as failed.
                return -1 # Return that it failed with a timeout.
            #print(self.label+".write_reg_check(): Retries left",tries)

    #-----------------------------------------------------------------------------------------------
    
    def set_bit(self, value, bit):
        """ Set an individual bit in a register value. 
            Parameters --------------------------------------------        
            value 
            bit 
            
            Used by:
            -   self.clear_gstat()
            -   self.set_direction_reg()
            -   self.set_iscale_analog()
            -   self.set_vsense()
            -   self.set_pdn_disable()
            -   self.set_spreadcycle()
            -   self.set_interpolation()
            -   self.set_mstep_resolution_reg_select()
                
                """
        return value | (bit) # Set 'bit' in the value. (OR the two values)

    #-----------------------------------------------------------------------------------------------
    
    def clear_bit(self, value, bit):
        """ Clear an individual bit in a register value. 
            Parameters --------------------------------------------        
            value 
            bit 
            
            Used by:
            -   self.set_direction_reg()
            -   self.set_iscale_analog()
            -   self.set_vsense()
            -   self.set_internal_rsense()
            -   self.set_pdn_disable()
            -   self.set_spreadcycle()
            -   self.set_interpolation()
            -   self.set_mstep_resolution_reg_select()
                
                """
        return value & ~(bit) # Clear the 'bit' of a value. (AND NOT the two values)

    #-----------------------------------------------------------------------------------------------
    
    def handle_error(self,info=None):
        """ Call when an error condition has been arised. 
            Log recognised errors then raise the exception. 
            Parameters --------------------------------------------        
            -   info : Optional additional information to show in error messages.
            Used by:
            -   self.read_int() <- recursive?
            -   self.write_reg_check()
                """
        if self.error_handler_running: # Already handling an error.
            return
        self.error_handler_running = True
        gstat = self.read_int(reg.GSTAT) # Read Driver Status Flags.
        if gstat == -1:
            print(self.label+".handle_error(): No answer from Driver")
            self.LogFile.Log(self.label+".handle_error(): No answer from Driver")
        else:
            if gstat & reg.reset:
                print(self.label+".handle_error(): The Driver has been reset since the last read access to GSTAT")
                self.LogFile.Log(self.label+".handle_error(): The Driver has been reset since the last read access to GSTAT")
            if gstat & reg.drv_err:
                print(self.label+".handle_error(): The driver has been shut down due to overtemperature or short circuit detection since the last read access")
                self.LogFile.Log(self.label+".handle_error(): The driver has been shut down due to overtemperature or short circuit detection since the last read access")
            if gstat & reg.uv_cp:
                print(self.label+".handle_error(): Undervoltage on the charge pump. The driver is disabled in this case")
                self.LogFile.Log(self.label+".handle_error(): Undervoltage on the charge pump. The driver is disabled in this case")
        self.ExceptionCounter.Raise("handle_error(" + str(info) + ")")

    #-----------------------------------------------------------------------------------------------
    
    def read_drv_status(self,label=None):
        """ Record the current value of DRVSTATUS response from TMC2209 
            Parameters --------------------------------------------        
                label : Optional label to show in first line, identifies WHEN this is being called.        
            Used by:
            -   self.__init__()
                """
        if label == None: label = ""
        else: label = "[" + label + "]"
        print(self.label+".read_drv_status():",label)
        drvstatus = self.read_int(reg.DRVSTATUS)
        self.LogFile.Log(self.label+".read_drv_status(): TMC Driver status",drvstatus)
        if drvstatus & reg.stst:
            print("Motor is standing still")
            self.LogFile.Log("Motor is standing still")
        else:
            print("Motor is running")
            self.LogFile.Log("Motor is running")

        if drvstatus & reg.stealth:
            print("Motor is running on StealthChop")
            self.LogFile.Log("Motor is running on StealthChop")
        else:
            print("Motor is running on SpreadCycle")
            self.LogFile.Log("Motor is running on SpreadCycle")

        cs_actual = drvstatus & reg.cs_actual # *Q* Not used?
        cs_actual = cs_actual >> 16 # Right shift 16 bits (2 bytes)

        if drvstatus & reg.olb:
            print("Open load detected on phase B: True")
            self.LogFile.Log("Open load detected on phase B")
        else:
            print("Open load detected on phase B: False")

        if drvstatus & reg.ola:
            print("Open load detected on phase A: True")
            self.LogFile.Log("Open load detected on phase A")
        else:
            print("Open load detected on phase A: False")

        if drvstatus & reg.s2vsb:
            print("Short on low-side MOSFET detected on phase B: True (The driver becomes disabled)")
            self.LogFile.Log("Short on low-side MOSFET detected on phase B. The driver becomes disabled")
        else:
            print("Short on low-side MOSFET detected on phase B: False")

        if drvstatus & reg.s2vsa:
            print("Short on low-side MOSFET detected on phase A: True (The driver becomes disabled)")
            self.LogFile.Log("Short on low-side MOSFET detected on phase A. The driver becomes disabled")
        else:
            print("Short on low-side MOSFET detected on phase A: False")

        if drvstatus & reg.s2gb:
            print("Short to GND detected on phase B: True (The driver becomes disabled)")
            self.LogFile.Log("Short to GND detected on phase B. The driver becomes disabled")
        else:
            print("Short to GND detected on phase B: False")

        if drvstatus & reg.s2ga:
            print("Short to GND detected on phase A: True (The driver becomes disabled)")
            self.LogFile.Log("Short to GND detected on phase A. The driver becomes disabled")
        else:
            print("Short to GND detected on phase A: False")

        if drvstatus & reg.ot:
            print("Driver Overheating: True")
            self.LogFile.Log("Driver Overheating!")
        else:
            print("Driver Overheating: False")

        if drvstatus & reg.otpw:
            print("Driver Overheating Prewarning: True")
            self.LogFile.Log("Driver Overheating Prewarning!")
        else:
            print("Driver Overheating Prewarning: False")

        return drvstatus

    #-----------------------------------------------------------------------------------------------
    
    def read_gconf(self):
        """ Read and log the GLOBAL CONFIGURATION FLAGS from the TMC2209 chip. 
            Parameters --------------------------------------------        
            
            Used by:
                Nothing internally.
                External call? """
        gconf = self.read_int(reg.GCONF) # Global Configuration Flags

        if gconf & reg.i_scale_analog: # The VREF bit. Which reference to use for setting current limiter.
            self.LogFile.Log(self.label+".read_gconf(): Driver is using voltage supplied to VREF as current reference")
        else:
            self.LogFile.Log(self.label+".read_gconf(): Driver is using internal reference derived from 5VOUT")
        if gconf & reg.internal_rsense: # The INTERNAL RSENSE bit.
            self.LogFile.Log(self.label+".read_gconf(): Internal sense resistors. Use current supplied into VREF as reference.")
            self.LogFile.Log(self.label+".read_gconf(): VREF pin internally is driven to GND in this mode.")
            self.LogFile.Log(self.label+".read_gconf(): This will most likely destroy your driver!!!")
            raise SystemExit
        self.LogFile.Log(self.label+".read_gconf(): Operation with external sense resistors")
        if gconf & reg.en_spreadcycle: # The StealthChop mode bit.
            self.LogFile.Log(self.label+".read_gconf(): SpreadCycle mode enabled")
        else:
            self.LogFile.Log(self.label+".read_gconf(): StealthChop PWM mode enabled")
        if gconf & reg.shaft: # The motor direction bit.
            self.LogFile.Log(self.label+".read_gconf(): Inverse motor direction")
        else:
            self.LogFile.Log(self.label+".read_gconf(): Normal motor direction")
        if gconf & reg.index_otpw: # Overtemperature pre-warning bit. 
            self.LogFile.Log(self.label+".read_gconf(): INDEX pin outputs overtemperature prewarning flag")
        else:
            self.LogFile.Log(self.label+".read_gconf(): INDEX shows the first microstep position of sequencer")
        if gconf & reg.index_step: # Internal pulse generator steps bit.
            self.LogFile.Log(self.label+".read_gconf(): INDEX output shows step pulses from internal pulse generator")
        else:
            self.LogFile.Log(self.label+".read_gconf(): INDEX output as selected by index_otpw")
        if gconf & reg.mstep_reg_select: # Microstep control bit.
            self.LogFile.Log(self.label+".read_gconf(): Microstep resolution selected by MSTEP register") # Controlled by UART.
        else:
            self.LogFile.Log(self.label+".read_gconf()): Microstep resolution selected by pins MS1, MS2") # Controlled directly by pins.

        return gconf

    #-----------------------------------------------------------------------------------------------
    
    def read_gstat(self):
        """ Read and log the GSTAT values from the TMC2209. 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        gstat = self.read_int(reg.GSTAT) # Read Driver Status Flags.
        if gstat & reg.reset: # The RESET bit.
            self.LogFile.Log(self.label+".read_gstat(): The Driver has been reset since the last read access to GSTAT")
        if gstat & reg.drv_err: # The ERROR bit.
            self.LogFile.Log(self.label+".read_gstat(): The driver has been shut down due to overtemperature or short circuit detection since the last read access")
        if gstat & reg.uv_cp: # The UNDERVOLTAGE bit.
            self.LogFile.Log(self.label+".read_gstat(): Undervoltage on the charge pump. The driver is disabled in this case")
        return gstat

    #-----------------------------------------------------------------------------------------------
    
    def clear_gstat(self):
        """ Clear RESET and DRIVER ERROR flags on TMC2209 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        self.LogFile.Log(self.label+".clear_gstat(): Clearing GSTAT")
        gstat = self.uart.read_int(reg.GSTAT) # Read current Driver Status Flags.

        gstat = self.uart.set_bit(gstat, reg.reset)
        gstat = self.uart.set_bit(gstat, reg.drv_err)

        self.write_reg_check(reg.GSTAT, gstat) # Set revised Driver Status Flags.

    #-----------------------------------------------------------------------------------------------
    
    def read_ioin(self):
        """ Read the IO status of all pins for the TMC2209 
            Parameters -------------------------------------------- 
            Used by:
                Nothing internally.
                External call? """
        ioin = self.read_int(reg.IOIN)
        return ioin

    #-----------------------------------------------------------------------------------------------
    
    def read_chopconf(self):
        """ Read and log the current CHOPCONF setting of the TMC2209. 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        chopconf = self.read_int(reg.CHOPCONF)
        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Native "+str(self.get_microstepping_resolution())+" microstep setting")

        if chopconf & reg.intpol: # The interpolation bit.
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Interpolation to 256 µsteps")

        if chopconf & reg.vsense: # The vsense bit.
            # Support reduced voltage for more reduced heat generation in the sense resistor. (?)
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): High sensitivity, low sense resistor voltage")
        else:
            # Support normal full power but more heat to dissipate through the sense resistor. (?)
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Low sensitivity, high sense resistor voltage")
        return chopconf

    #-----------------------------------------------------------------------------------------------
    
    def get_direction_reg(self):
        """ Get the current motor direction from the TMC2209 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        return gconf & reg.shaft

    #-----------------------------------------------------------------------------------------------
    
    def set_direction_reg(self, direction):
        """ Set the Clockwise/CounterClockwise direction for the TMC2209. 
            Parameters --------------------------------------------        
            direction
            Used by:
            -   self.set_direction_pin_or_reg() """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        if direction:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Setting inverse motor direction")
            gconf = self.set_bit(gconf, reg.shaft)
        else:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Setting normal motor direction")
            gconf = self.clear_bit(gconf, reg.shaft)
        self.write_reg_check(reg.GCONF, gconf) # Set Global Configuration Flags
        self._direction = not direction

    #-----------------------------------------------------------------------------------------------
    
    def get_iscale_analog(self):
        """ Tells if using INTERNAL 5V or EXTERNAL VREF is being used to set motor current limit.
            FALSE: internal 5V is for UART control.
            TRUE: external VREF is for PIN control. 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        gconf = self.read_int(reg.GCONF) # Global Configuration Flags
        return gconf & reg.i_scale_analog # The i_scale_analog bit.

    #-----------------------------------------------------------------------------------------------
    
    def set_iscale_analog(self,en):
        """ Choose which reference voltage to use for motor current limit.. 
            Can be internal 5V (when controlled by UART) or external VREF (when controlled by PINS). 
            Parameters --------------------------------------------        
            en 
            Used by:
            -   self.set_current() """
        gconf = self.read_int(reg.GCONF) # Global Configuration Flags
        if en:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Activated Vref for current scale")
            gconf = self.set_bit(gconf, reg.i_scale_analog)
        else:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Activated 5V-out for current scale")
            gconf = self.clear_bit(gconf, reg.i_scale_analog)
        self.write_reg_check(reg.GCONF, gconf) # Set Global Configuration Flags

    #-----------------------------------------------------------------------------------------------
    
    def get_vsense(self):
        """ Is TMC2209 set for HIGH or LOW sensitivity?
                  High sensitivity: Motor uses lower voltage across the sense resistor for reduce heat generation.
                  Useful if using low power external resistors.
                  Low sensitivity: Motor uses higher voltage across the sense resistor but generates more heat. 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        chopconf = self.read_int(reg.CHOPCONF)
        return chopconf & reg.vsense

    #-----------------------------------------------------------------------------------------------
    
    def set_vsense(self,en):
        """ Select HIGH or LOW sensitivity on TMC2209
            TRUE: High sensitivity: Motor uses lower voltage across the sense resistor for reduce heat generation.
                  Useful if using low power external resistors.
            FALSE: Low sensitivity: Motor uses higher voltage across the sense resistor but generates more heat. 
            Parameters --------------------------------------------        
            en
            Used by:
            -   self.set_current() """
        chopconf = self.read_int(reg.CHOPCONF)
        if en:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Activated High sensitivity, low sense resistor voltage")
            chopconf = self.set_bit(chopconf, reg.vsense)
        else:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Activated Low sensitivity, high sense resistor voltage")
            chopconf = self.clear_bit(chopconf, reg.vsense)
        self.write_reg_check(reg.CHOPCONF, chopconf)

    #-----------------------------------------------------------------------------------------------
    
    def get_internal_rsense(self):
        """ Does TMC2209 use INTERNAL or EXTERNAL sense resistors?
            Internal are slightly less precise and limit the motor current to 1.4A.
            External can be more precise and support up to 2.0A. 
            Parameters --------------------------------------------
            Used by:
                Nothing internally.
                External call? """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        return gconf & reg.internal_rsense

    #-----------------------------------------------------------------------------------------------
    
    def set_internal_rsense(self,en):
        """ Choose INTERNAL or EXTERNAL sense resistors on TMC2209 
            Internal are slightly less precise and limit the motor current to 1.4A.
            External can be more precise and support up to 2.0A. 

            *Q* Warning message that INTERNAL will destroy the driver!
                Does now actually enable the internal sense resistor!
                
            Parameters -------------------------------------------        
            en
            Used by:
                Nothing internally.
                External call? """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        if en:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Activated internal sense resistors.")
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): VREF pin internally is driven to GND in this mode.")
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): This will most likely destroy your driver!!!")
            raise SystemExit
        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Activated operation with external sense resistors")
        gconf = self.clear_bit(gconf, reg.internal_rsense)
        self.write_reg_check(reg.GCONF, gconf) # Set Global Configuration Flags

    #-----------------------------------------------------------------------------------------------
    
    def set_irun_ihold(self, ihold, irun, ihold_delay):
        """ Set ihold, irun and ihold_delay on TMC2209 
            Parameters --------------------------------------------        
            ihold 
            irun 
            ihold_delay 
            
            Used by:
            - self.set_current() """
        ihold_irun = 0 # Start with all settings OFF.
        
        self.irun_value = irun
        self.ihold_value = ihold
        self.ihold_delay_value = ihold_delay

        ihold_irun = ihold_irun | ihold << 0 # Set the iHold bit
        ihold_irun = ihold_irun | irun << 8 # Set the iRun bit.
        ihold_irun = ihold_irun | ihold_delay << 16 # Set the iHold_delay bit.
        self.write_reg_check(reg.IHOLD_IRUN, ihold_irun)

    #-----------------------------------------------------------------------------------------------
    
    def set_pdn_disable(self,pdn_disable):
        """ Set pdn_disable. 
            PDN_UART enabled : Controls standstill current. 
            PDN_UART disabled : UART interface controls current instead. 
            Parameters --------------------------------------------        
                pdn_disable """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        if pdn_disable:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Enabled PDN_UART")
            gconf = self.set_bit(gconf, reg.pdn_disable)
        else:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Disabled PDN_UART")
            gconf = self.clear_bit(gconf, reg.pdn_disable)
        self.write_reg_check(reg.GCONF, gconf) # Set Global Configuration Flags

    #-----------------------------------------------------------------------------------------------
    
    def calculate_vref(self,irms):
        """ Calculation for vref setting.
            This is for setting the onboard potentiometer to the correct reference voltage.
            You have to do that manually, this routine is just to calculate the voltage you must achieve.
            
            Currents up to 1.0A need HEATSINK, currents over 1.0A need a fan too.
        
            Parameters --------------------------------------------
                irms : Required RMS current.
            Outputs -----------------------------------------------
                returns vref value for required RMS current. 
                
            Used by:
                Nothing internal.
                Available as external method.
                
            """
        return (irms * 2.5) / 1.77
        
    #-----------------------------------------------------------------------------------------------
    
    #def set_current_orig(self, run_current, hold_current_multiplier = 0.5,
    #                     hold_current_delay = 10, pdn_disable = True):
    #    """ Set the current limiter via UART, it also switches the controller to UART mode.
    #        It switches to use internal 5V reference voltage.
    #        For very low currents it switches on high sensitivity VSense.
    #        For higher currents it switches off high sensitivity VSense.
    #        Parameters --------------------------------------------        
    #        run_current 
    #        hold_current_multiplier 
    #        hold_current_delay 
    #        pdn_disable 
    #        
    #        cs = CURRENT SCALE : 
    #        vfs = ??? : 
    #        rsense = 0.11 Ohm : 
    #        
    #        Motor current rating : The specified current rating of the motor in use. 
    #        Operating current setting : % of motor current rating that you want to use (0-100%) """
    #    print(self.label+".set_current(",run_current,hold_current_multiplier,hold_current_delay,pdn_disable,")")
    #    cs_irun = 0
    #    rsense = 0.11 # 0.11Ohms internal rsense resistor value.
    #    #vfs = 0
    #
    #    print(self.label+".set_current(): Switching to internal 5V reference for current limiter.")
    #    self.set_iscale_analog(False) # Use the internal 5V reference for current limiter (therefore controlled by UART interface rather than external VREF).
    #
    #    vfs = 0.325
    #    # This is defining the current in milliAmps?
    #    cs_irun = 32.0 * 1.41421 * run_current / 1000.0 * (rsense + 0.02) / vfs - 1 # *Q* Clarify this equation. See: https://wiki.openastrotech.com/Knowledge/UART_RMS_Calculation
    #    # cs_irun = (((((32.0 * 1.41421) * run_current) / 1000.0) * (rsense+0.02)) / vfs) - 1 # *Q* Clarify this equation. See: https://wiki.openastrotech.com/Knowledge/UART_RMS_Calculation
    #
    #    # If Current Scale is low, turn on high sensitivity VSsense and calculate again
    #    if cs_irun < 16:
    #        print(self.label+".set_current(): cs_irun(",cs_irun,") is too low. Switching to HighSensitivity VSense True.")
    #        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): CS too low; switching to VSense True")
    #        vfs = 0.180
    #        cs_irun = 32.0 * 1.41421 * run_current / 1000.0 * (rsense + 0.02) / vfs - 1 # *Q* Clarify this equation. 
    #        self.set_vsense(True)
    #    else: # If CS >= 16, turn off high sensitivity VSense
    #        print(self.label+".set_current(): cs_irun(",cs_irun,") is strong. Switching to LowSensitivity VSense False.")
    #        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): CS in range; using VSense False")
    #        self.set_vsense(False)
    #
    #    cs_irun = min(cs_irun, 31) # CS value must be between 0 and 31.
    #    cs_irun = max(cs_irun, 0)
    #
    #    cs_ihold = hold_current_multiplier * cs_irun
    #
    #    cs_irun = round(cs_irun)
    #    cs_ihold = round(cs_ihold)
    #    hold_current_delay = round(hold_current_delay)
    #
    #    run_current_actual = (cs_irun + 1) / 32.0 * (vfs) / (rsense + 0.02) / 1.41421 * 1000
    #    self.LogFile.Log(f"TMCStepper({self.mtr_id}): Actual current: {round(run_current_actual)} mA")
    #    print(self.label+".set_current(): Actual current:",round(run_current_actual),"mA")
    #
    #    print(self.label+".set_current(): Setting:",cs_ihold, cs_irun, hold_current_delay)
    #    self.set_irun_ihold(cs_ihold, cs_irun, hold_current_delay) # Set the current limit.
    #    print(self.label+".set_current(): Disable POWER DOWN so that UART remains active.")
    #    self.set_pdn_disable(pdn_disable) # Switch to UART control. Prevents driver shutting down which can interrupt communication.

    #-----------------------------------------------------------------------------------------------

    def set_current(self, operating_ratio, hold_current_multiplier = 0.5,
                    hold_current_delay = 10, pdn_disable = True):
        """ Set the current limiter via UART, it also switches the controller to UART mode.
            It switches to use internal 5V reference voltage.
            For very low currents it switches on high sensitivity VSense.
            For higher currents it switches off high sensitivity VSense.
            Parameters --------------------------------------------        
            operating_ratio (0.0 - 1.0)
            hold_current_multiplier (0.0 - 1.0)
            hold_current_delay (0 - 31)
            pdn_disable (Boolean) """
        print(self.label+".set_current(",operating_ratio,hold_current_multiplier,hold_current_delay,pdn_disable,")")
        print(self.label+".set_current(): Switching to internal vref for current limiter.")
        self.set_iscale_analog(False) # Use the internal vref for current limiter (therefore controlled by UART interface rather than external VREF).

        cs_irun = self.peak_to_cs_low(operating_ratio) # Returns value 0->31 (Selects nearest available current option)
        self.run_current_actual = self.cs_low_to_rms(cs_irun) # Convert back to actual RMS current this represents.

        # If Current Scale is low, turn on high sensitivity VSsense and calculate again
        if cs_irun < 16:
            print(self.label+".set_current(): cs_irun(",cs_irun,") is low. Switching to HighSensitivity VSense True.")
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): CS low; switching to VSense True")
            cs_irun = self.peak_to_cs_high(operating_ratio) # Returns value 0->31 (Selects nearest available current option)
            self.run_current_actual = self.cs_high_to_rms(cs_irun) # Convert back to actual RMS current this represents.
            self.set_vsense(True)
        else: # If CS >= 16, turn off high sensitivity VSense
            print(self.label+".set_current(): cs_irun(",cs_irun,") is strong. Switching to LowSensitivity VSense False.")
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): CS in range; using VSense False")
            self.set_vsense(False)

        #cs_irun = min(max(cs_irun, 0), 31) # CS value must be between 0 and 31.
        cs_ihold = round(hold_current_multiplier * cs_irun)

        hold_current_delay = round(hold_current_delay) # How many clock cycles before switching from RUN to HOLD current.

        self.LogFile.Log(f"TMCStepper({self.mtr_id}): Actual RMS current: {round(self.run_current_actual,2)} A")
        print(self.label+".set_current(): Actual RMS current:",round(self.run_current_actual,2),"A")

        print(self.label+".set_current(): Setting: hold:",cs_ihold,"run:",cs_irun,"delay:",hold_current_delay)
        self.set_irun_ihold(cs_ihold, cs_irun, hold_current_delay) # Set the current limit.
        print(self.label+".set_current(): Disable POWER DOWN so that UART remains active.")
        self.set_pdn_disable(pdn_disable) # Switch to UART control. Prevents driver shutting down which can interrupt communication.

    #-----------------------------------------------------------------------------------------------

    #def peak_to_cs(self,operating_ratio):
    #    """ Calculate CS value for given operating conditions. """
    #    print("tmc2209.py:TMCStepper.peak_to_cs() called, but deprecated.")
    #    return

    #-----------------------------------------------------------------------------------------------

    #def cs_to_rms(self,cs):
    #    """ Invert peak_to_cs() method back to an irms value.
    #        (STUDYING HOW THIS WORKS) """
    #    print("tmc2209.py:TMCStepper.cs_to_rms() called, but deprecated.")
    #    return

    #-----------------------------------------------------------------------------------------------

    #def peak_to_cs_2(self,operating_ratio):
    #    """ Calculate CS value for given operating conditions. """
    #    print("tmc2209.py:TMCStepper.peak_to_cs_2() called, but deprecated.")
    #    return

    #-----------------------------------------------------------------------------------------------

    #def cs_2_to_rms(self,cs):
    #    """ Reversing peak_to_cs2() method back to an irms value. """
    #    print("tmc2209.py:TMCStepper.cs_2_to_rms() called, but deprecated.")
    #    return 

    #-----------------------------------------------------------------------------------------------

    def peak_to_cs_low(self,operating_ratio):
        """ Calculate CS value for given operating conditions. 
            Alternative calculation #3.
            Sources:
                TMC2209 Datasheet, Sections 5.2 & 9
                OpenAstroTech Wiki: UART RMS Current Calculation """
        rsense = 0.11
        if operating_ratio <= 0 or operating_ratio > 1:
            print("peak_to_cs_low(): operating_ratio must be 0.0 to 1.0 range.")
            return False
        i_rms = self.peak_to_rms(self.peak_current * operating_ratio)
        cs = (32.0 * 1.41421 * i_rms * (rsense + 0.02) / 0.325) - 1
        return min(max(round(cs),0),31)

    #-----------------------------------------------------------------------------------------------

    def peak_to_cs_high(self,operating_ratio):
        """ Calculate CS value for given operating conditions. 
            Sources:
                TMC2209 Datasheet, Sections 5.2 & 9
                OpenAstroTech Wiki: UART RMS Current Calculation """
        rsense = 0.11
        if operating_ratio <= 0 or operating_ratio > 1:
            print("peak_to_cs_high(): operating_ratio must be 0.0 to 1.0 range.")
            return False
        i_rms = self.peak_to_rms(self.peak_current * operating_ratio)
        cs = (32.0 * 1.41421 * i_rms * (rsense + 0.02) / 0.18) - 1
        return min(max(round(cs),0),31)

    #-----------------------------------------------------------------------------------------------

    def cs_high_to_rms(self,cs):
        """ Inverting peak_to_cs_high() method back to irms value. """
        rsense = 0.11
        irms = ((cs + 1) * 0.18) / (32.0 * 1.41421 * (rsense + 0.02))
        return irms

    #-----------------------------------------------------------------------------------------------

    def cs_low_to_rms(self,cs):
        """ Inverting peak_to_cs_low() method back to irms value. """
        rsense = 0.11
        irms = ((cs + 1) * 0.325) / (32.0 * 1.41421 * (rsense + 0.02))
        return irms

    #-----------------------------------------------------------------------------------------------

    def list_cs_values(self):
        """ (STUDYING HOW THIS WORKS)
            Comparing alternative CS calculations found online. """
        print("tmc2209.py:TMCStepper.list_cs_values() called, but deprecated.")
        return 

    #-----------------------------------------------------------------------------------------------

    def peak_to_rms(self,peak_current):
        """ Convert peak current value to RMS current which the TMC2209 uses internally. """
        return peak_current / (2 ** 0.5)

    #-----------------------------------------------------------------------------------------------
    
    def rms_to_peak(self,rms_current):
        """ Convert TMC2209's internal RMS current value to PEAK current. """
        return rms_current * (2 ** 0.5)

    #-----------------------------------------------------------------------------------------------
    
    def get_spreadcycle(self):
        """ Is SpreadCycle enabled or not?
            Enabled: StealthChop PWM is enabled.
            Disabled: SpreadCycle is enabled. 
            Parameters --------------------------------------------        """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        return gconf & reg.en_spreadcycle

    #-----------------------------------------------------------------------------------------------
    
    def set_spreadcycle(self,en_spread):
        """ Select SpreadCycle or StealthChop mode. 
            Stealthchop is smoother quieter operation. Good for low speeds.
            Spreadcycle is better for high speeds, reduces resonance, more powerful but more noise.
            
            Parameters --------------------------------------------        
            en_spread : True = Activate SpreadCycle.
                        False = Activate Stealthchop. """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags
        if en_spread:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+").set_spreadcycle(): Activated Spreadcycle")
            gconf = self.set_bit(gconf, reg.en_spreadcycle)
        else:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+").set_spreadcycle(): Activated Stealthchop")
            gconf = self.clear_bit(gconf, reg.en_spreadcycle)
        self.write_reg_check(reg.GCONF, gconf) # Set Global Configuration Flags

    #-----------------------------------------------------------------------------------------------
    
    def get_interpolation(self):
        """ Is step interpolation active or not? 
            Parameters --------------------------------------------        """
        chopconf = self.read_int(reg.CHOPCONF)
        return bool(chopconf & reg.intpol)

    #-----------------------------------------------------------------------------------------------
    
    def set_interpolation(self, en):
        """ Turn step interpolation on/off. 
            Parameters --------------------------------------------        
            en """
        chopconf = self.read_int(reg.CHOPCONF)

        if en:
            chopconf = self.set_bit(chopconf, reg.intpol)
        else:
            chopconf = self.clear_bit(chopconf, reg.intpol)

        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Writing microstep interpolation setting: "+str(en))
        self.write_reg_check(reg.CHOPCONF, chopconf)

    #-----------------------------------------------------------------------------------------------
    
    def get_toff(self):
        """ Return the toff setting from the TMC2209 
            Parameters --------------------------------------------        """
        chopconf = self.read_int(reg.CHOPCONF)

        toff = chopconf & (reg.toff0 | reg.toff1 | reg.toff2 | reg.toff3) # Combine (OR) the 4 elements into a single value.
        toff = toff >> 0
        return toff

    #-----------------------------------------------------------------------------------------------
    
    def set_toff(self, toff):
        """ Set the toff parameter for the TMC2209 
        
        AI generated overview ...        
            The TMC2209 toff (Off Time) setting is a crucial parameter that controls the duration 
            of the "off" time in the chopper driver's current control cycle, affecting the stepper 
            motor's performance, torque, and noise. A common starting point is toff(3), but the 
            optimal value depends on factors like the motor's characteristics, the selected driver
            mode (StealthChop or SpreadCycle), and the system's clock frequency. Tuning toff often
            involves a trial-and-error process, and for fine-tuning, a tool like the TMC2209 Calculator
            from Analog Devices can be beneficial, especially for SpreadCycle mode. 
            
            Understanding toff
            Purpose:
            The toff setting directly influences the chopper's duty cycle by determining how long the 
            driver remains in an "off" state, which is essential for regulating current and controlling
            the motor. 
            Impact:
            hop: In StealthChop mode, toff is generally not used, as the driver switches modes at a certain
            microstep threshold, according to the tpwmthrs setting. StealthChop is the 'quiet' mode anyway.
            SpreadCycle: For SpreadCycle mode, toff is critical for controlling the chopper's frequency
            and achieving smooth, stable operation. A higher toff value generally corresponds to a lower
            chopper frequency, while a lower toff value results in a higher frequency. SpeadCycle is the 
            high performance mode.
        
            Parameters --------------------------------------------        
            toff """
        # Ensure toff is a four-bit value by zeroing out the top bits
        toff = toff & 0x0F # Mask so only lower 4 bits pass through.

        # Read the current value of the CHOPCONF register
        chopconf = self.read_int(reg.CHOPCONF)

        # Zero out the lower four bits of the CHOPCONF register
        chopconf = chopconf & 0xFFFFFFF0 # Mask so lower 4 bits are removed.

        # Set the lower four bits of CHOPCONF to the toff value
        chopconf = chopconf | toff

        # Write the new value back to the CHOPCONF register
        self.write_reg_check(reg.CHOPCONF, chopconf)

        # Log the action
        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Writing toff setting: "+str(toff))

    #-----------------------------------------------------------------------------------------------

    def set_fullsteps_per_rev(self,steps):
        """ """
        self._fullsteps_per_rev = steps
        self._steps_per_rev = self._fullsteps_per_rev * self._msres

    #-----------------------------------------------------------------------------------------------
    
    def read_microstepping_resolution(self):
        """ Get the current microstepping resolution for the TMC2209. 
            Parameters --------------------------------------------        """
        chopconf = self.read_int(reg.CHOPCONF)

        msresdezimal = chopconf & (reg.msres0 | reg.msres1 | reg.msres2 | reg.msres3)
        msresdezimal = msresdezimal >> 24
        msresdezimal = 8 - msresdezimal

        self._msres = int(math.pow(2, msresdezimal))
        self._steps_per_rev = self._fullsteps_per_rev * self._msres
        
        return self._msres

    #-----------------------------------------------------------------------------------------------
    
    def get_microstepping_resolution(self):
        """ Return the current microstepping resolution. 
            Parameters --------------------------------------------        """
        return self._msres

    #-----------------------------------------------------------------------------------------------
    
    def set_microstepping_resolution(self, msres):
        """ Set the microstepping ratio for the TMC2209 
            Takes about 0.12 seconds to complete.
            Parameters --------------------------------------------        
            msres : Any value from 1 to 256 """
        print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Setting",msres)
        #print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Reading CHOPCONF(",reg.CHOPCONF,")")
        chopconf = self.read_int(reg.CHOPCONF)
        #print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Read CHOPCONF:",chopconf)
        # setting all bits to zero
        # Set inverse of each bit. AND (NOT res0 AND NOT res1 ...)
        chopconf = chopconf & (~reg.msres0 & ~reg.msres1 &
                                ~reg.msres2 & ~reg.msres3)
        msresdezimal = int(math.log(msres, 2))
        msresdezimal = 8 - msresdezimal
        chopconf = chopconf | msresdezimal <<24

        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Writing "+str(msres)+" microstep setting")
        #print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Writing CHOPCONF(",reg.CHOPCONF,",",chopconf,")")
        self.write_reg_check(reg.CHOPCONF, chopconf)
        #print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Returned from write_reg_check()")

        self._msres = msres
        self._steps_per_rev = self._fullsteps_per_rev * self._msres
        #print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Calling set_mstep_resolution_reg_select(TRUE)")
        self.set_mstep_resolution_reg_select(True)
        #print("TMCStepper.set_microstepping_resolution(",str(self.mtr_id),"): Done")

        return True

    #-----------------------------------------------------------------------------------------------
    
    def set_mstep_resolution_reg_select(self, en):
        """ Choose how microsteps are controlled. 
            TRUE : UART register is used. 
            FALSE : MODE PINS are used. 
            Parameters --------------------------------------------        
            en """
        gconf = self.read_int(reg.GCONF) # Read Global Configuration Flags

        if en is True:
            gconf = self.set_bit(gconf, reg.mstep_reg_select) # Microsteps controlled by UART.
        else:
            gconf = self.clear_bit(gconf, reg.mstep_reg_select) # Microsteps controlled by MODE PINS. 

        self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Writing MStep Reg Select: "+str(en))
        self.write_reg_check(reg.GCONF, gconf) # Set Global Configuration Flags

    #------------------------------ -----------------------------------------------------------------   
    
    def get_interface_transmission_counter(self):
        """ Get the interface message counter. 
            Parameters --------------------------------------------        """
        ifcnt = self.read_int(reg.IFCNT)
        return ifcnt

    #-----------------------------------------------------------------------------------------------
    
    def get_tstep(self):
        """ Get the current tstep value. 
            Parameters --------------------------------------------        """
        tstep = self.read_int(reg.TSTEP)
        return tstep

    #-----------------------------------------------------------------------------------------------
    
    def set_vactual(self, vactual):
        """ Set vactual value. 
            Defines whether to move by STEP PIN or UART configuration. 
            Parameters --------------------------------------------        
            -   vactual :
            Used by:
            - self.set_vactual_dur()
            
            == 0 : Means the step signal is used to move the motor.
            != 0 : Means that the TMC2209 itself times the steps automatically. (*Q*: Check this!)
            """
        self.write_reg_check(reg.VACTUAL, vactual)
        self._vactual = vactual # Record the setting for reference elsewhere.

    #-----------------------------------------------------------------------------------------------
    
    def get_stallguard_result(self):
        """ Get current state of STALLGUARD. 
            Parameters --------------------------------------------        """
        sg_result = self.read_int(reg.SG_RESULT)
        return sg_result

    #-----------------------------------------------------------------------------------------------
    
    def set_stallguard_threshold(self, threshold):
        """ Set the stallguard threshold. Sensorless homing. Motor detects physical limit of movement.
            Parameters --------------------------------------------        
            -   threshold : """
        self.write_reg_check(reg.SGTHRS, threshold)

    #-----------------------------------------------------------------------------------------------
    
    def set_coolstep_threshold(self, threshold):
        """ Set the COOLSTEP threshold. 
            COOLSTEP makes the motor dynamically adjust power to the instanteneous load.
            
            Parameters --------------------------------------------        
            -   threshold : Set velocity threshold for COOLSTEP to work at. """
        self.write_reg_check(reg.TCOOLTHRS, threshold)

    #-----------------------------------------------------------------------------------------------
    
    def get_microstep_counter(self):
        """ Get the driver's current microstep counter. 
            Parameters --------------------------------------------        """
        mscnt = self.read_int(reg.MSCNT)
        return mscnt

    #-----------------------------------------------------------------------------------------------
    
    def get_microstep_counter_in_steps(self, offset=0):
        """ Get the driver's current microstep counter as whole steps. 
            Parameters --------------------------------------------        
                offset """
        step = (self.get_microstep_counter()-64)*(self._msres*4)/1024
        step = (4*self._msres)-step-1
        step = round(step)
        return step+offset

    #-----------------------------------------------------------------------------------------------
    
    def set_direction_pin(self, direction):
        """ Set the DIR pin for CLOCKWISE or COUNTER CLOCKWISE movement. 
            Parameters --------------------------------------------        
                direction 
                
            Used by:
            - self.set_direction_pin_or_reg() """
        if self._pin_dir != -1:
            self._direction = direction
            self._pin_dir.SetValue(direction)
        else:
            self.LogFile.Log("TMCStepper("+str(self.mtr_id)+"): Direction pin not defined.")
            
    #-----------------------------------------------------------------------------------------------
    
    def set_direction_pin_or_reg(self, direction):
        """ Set the TMC2209 direction, using either the DIR PIN or the UART register. 
            Parameters --------------------------------------------        
            direction """
        if self._pin_dir != -1:
            self.set_direction_pin(direction)
        else:
            self.set_direction_reg(not direction) # no clue, why this has to be inverted

    #-----------------------------------------------------------------------------------------------
    
    def set_vactual_dur(self, vactual, duration=0, acceleration=0,
                        show_stallguard_result=False, show_tstep=False):
        """ 
            Parameters --------------------------------------------        
                vactual 
                duration 
                acceleration 
                show_stallguard_result 
                show_tstep """                            
 
        self._stop = self.NO
        current_vactual = 0
        sleeptime = 0.05
        time_to_stop = 0
        if vactual<0:
            acceleration = -acceleration

        if acceleration == 0:
            self.set_vactual(int(round(vactual)))

        if duration == 0:
            return -1

        self._starttime = time.time()
        current_time = time.time()
        while current_time < self._starttime+duration:
            if self._stop == self.HARDSTOP:
                break
            if acceleration != 0:
                time_to_stop = self._starttime+duration-abs(current_vactual/acceleration)
                if self._stop == self.SOFTSTOP:
                    time_to_stop = current_time-1
            if acceleration != 0 and current_time > time_to_stop:
                current_vactual -= acceleration*sleeptime
                self.set_vactual(int(round(current_vactual)))
                time.sleep(sleeptime)
            elif acceleration != 0 and abs(current_vactual)<abs(vactual):
                current_vactual += acceleration*sleeptime
                self.set_vactual(int(round(current_vactual)))
                time.sleep(sleeptime)
            if show_stallguard_result:
                print(f"StallGuard result: {self.get_stallguard_result()}")
                time.sleep(0.1)
            if show_tstep:
                print(f"TStep result: {self.get_tstep()}")
                time.sleep(0.1)
            current_time = time.time()
        self.set_vactual(0)
        return self._stop

    #-----------------------------------------------------------------------------------------------
    
    def set_movement_abs_rel(self, movement_abs_rel):
        """ 
            Parameters --------------------------------------------        
            movement_abs_rel """
        
        self._movement_abs_rel = movement_abs_rel

    #-----------------------------------------------------------------------------------------------
    
    def get_current_position(self):
        """ Get the current position of the motor. 
            Parameters --------------------------------------------        """
        return self._current_pos

    #-----------------------------------------------------------------------------------------------
    
    def set_current_position(self, new_pos):
        """ Update the current position of the motor. 
            Parameters --------------------------------------------        
            new_pos """
        self._current_pos = new_pos
        
    #-----------------------------------------------------------------------------------------------
    
    def set_speed(self, speed):
        """ Set speed in microsteps. 
            Parameters --------------------------------------------        
            speed """
        # Sets the motor speed in steps per second

        if speed == self._speed:
            return
        speed = self.constrain(speed, -self._max_speed, self._max_speed)
        if speed == 0.0:
            self._step_interval = 0
        else:
            self._step_interval = abs(1000000.0 / speed)
            if speed > 0:
                self.set_direction_pin_or_reg(1)
            else:
                self.set_direction_pin_or_reg(0)
        self._speed = speed

    #-----------------------------------------------------------------------------------------------
    
    def set_speed_fullstep(self, speed):
        """ Set speed in fullsteps. 
            Parameters --------------------------------------------        
            speed """
        self.set_speed(speed*self.get_microstepping_resolution())

    #-----------------------------------------------------------------------------------------------
    
    def set_max_speed(self, speed):
        """ Set maximum microstepping speed. 
            Parameters --------------------------------------------        
            speed """
        # Sets the maximum motor speed in microsteps per second

        if speed < 0.0:
            speed = -speed
        if self._max_speed != speed:
            self._max_speed = speed
            if speed == 0.0:
                self._cmin = 0.0
            else:
                self._cmin = 1000000.0 / speed
            # Recompute _n from current speed and adjust speed if accelerating or cruising
            if self._n > 0:
                self._n = (self._speed * self._speed) / (2.0 * self._acceleration) # Equation 16
                self.compute_new_speed()

    #-----------------------------------------------------------------------------------------------
    
    def set_max_speed_fullstep(self, speed):
        """ Set maximum full step speed. 
            Parameters --------------------------------------------        
            speed """
        self.set_max_speed(speed*self.get_microstepping_resolution())

    #-----------------------------------------------------------------------------------------------
    
    def get_max_speed(self):
        """ Return the maximum permitted speed. 
            Parameters --------------------------------------------        """
        return self._max_speed

    #-----------------------------------------------------------------------------------------------
    
    def set_acceleration(self, acceleration):
        """ Set acceleration in microsteps. 
            Parameters --------------------------------------------        
            acceleration """
        # Sets the motor acceleration/deceleration in microsteps per sec per sec
        if acceleration == 0.0:
            return
        acceleration = abs(acceleration)
        if self._acceleration != acceleration:
            self._n = self._n * (self._acceleration / acceleration)
            self._c0 = 0.676 * math.sqrt(2.0 / acceleration) * 1000000.0 # Equation 15
            self._acceleration = acceleration
            self.compute_new_speed()

    #-----------------------------------------------------------------------------------------------
    
    def set_acceleration_fullstep(self, acceleration):
        """ Set acceleration in full steps. 
            Parameters --------------------------------------------        
            acceleration """
        self.set_acceleration(acceleration*self.get_microstepping_resolution())

    #-----------------------------------------------------------------------------------------------
    
    def get_acceleration(self):
        """ Return the current acceleration value. 
            Parameters --------------------------------------------        """
        return self._acceleration

    #-----------------------------------------------------------------------------------------------
    
    def stop(self, stop_mode = StopMode.HARDSTOP):
        """ Stop the motor, optionally specify the stop mode.
            Default is a HARD STOP. 
            Parameters --------------------------------------------        
            stop_mode """
        self._stop = stop_mode

    #-----------------------------------------------------------------------------------------------
    
    def get_movement_phase(self):
        """ What phase of movement is the driver in? 
            Parameters --------------------------------------------     
            Results -----------------------------------------------
            One of the values from MovementPhase enum class.
            STANDSTILL,ACCELERATING,DECELERATING,MAXSPEED            """
        return self._movement_phase

    #-----------------------------------------------------------------------------------------------
    
    def current_condition(self,label=None):
        """ Output all the things we know about the current state of the motor.
            Parameters --------------------------------------------
                label: Optional label shown in first line to identify WHY the display is being shown.
            Results -----------------------------------------------
                All output is to terminal. """
        if label != None: label = "[" + str(label) + "]"
        else: label = ""
        print(self.label+".current condition():",label)

        temp_value = self.get_direction_reg()
        if temp_value > 0: temp_desc = "Counter clockwise (reverse)."
        else: temp_desc = "Clockwise (forward)."
        print("direction_reg:",temp_value,"Motor direction:",temp_desc)

        temp_value = self.get_iscale_analog()
        if temp_value == 0: temp_desc = "Internal 5VOUT (UART control)."
        else: temp_desc = "External VREF. (External control)."
        print("iscale_analog:",temp_value,"Defining current limit on the stepper:",temp_desc)
        
        temp_value = self.get_vsense()
        if temp_value == 0: temp_desc = "Normal, robust signal, low sensitivity."
        else: temp_desc = "Reduced power, weaker signal, high sensitivity."
        print("vsense:",temp_value,temp_desc)
        
        temp_value = self.get_internal_rsense()
        if temp_value == 0: temp_desc = "Use external sense resitors."
        else: temp_desc = "Use internal sense resistors."
        print("internal_rsense:",temp_value,temp_desc)

        temp_value = self.get_spreadcycle()
        if temp_value > 0: temp_desc = "spreadCycle (Voltage controlled chopper)"
        else: temp_desc = "stealthChop (Current controlled chopper)"
        print("spreadcycle:",temp_value,temp_desc)

        temp_value = self.get_interpolation()
        if temp_value == 0: temp_desc = "OFF."
        else: temp_desc = "ON."
        print("interpolation:",temp_value,"Step interpolation:",temp_desc)
        
        print("toff:",self.get_toff(),"TOFF off time and driver enable.")
        
        print("microstepping_resolution:",self.get_microstepping_resolution())
        
        print("interface_transmission_counter:",self.get_interface_transmission_counter())
        
        print("tstep:",self.get_tstep(),"Measured time between 1/25 microsteps.")
        
        print("stallguard_result:",self.get_stallguard_result())
        print("microstep_counter:",self.get_microstep_counter())
        print("microstep_counter_in_steps:",self.get_microstep_counter_in_steps())
        print("current_position:",self.get_current_position())
        print("max_speed:",self.get_max_speed())
        print("acceleration:",self.get_acceleration())
        
        temp_value = self.get_movement_phase()
        if temp_value == MovementPhase.STANDSTILL: temp_desc = "STANDSTILL."
        elif temp_value == MovementPhase.ACCELERATING: temp_desc = "ACCELERATING."
        elif temp_value == MovementPhase.DECELERATING: temp_desc = "DECELERATING."
        elif temp_value == MovementPhase.MAXSPEED: temp_desc = "MAXSPEED."
        else: temp_desc = "UNDEFINED"
        print("movement_phase:",temp_value,temp_desc)
        
        temp_value = self._vactual
        if temp_value == 0: temp_desc = "STEP PIN."
        else: temp_desc = "TMC2209 motion control."
        print("vactual:",temp_value,"Moving via:",temp_desc) # The last recorded setting.

        # These are not 'read', just show that last set value.
        print("irun:",self.irun_value,"(Current setting when motor running. [0->31])")
        print("hold:",self.ihold_value,"(Current setting when holding. [0->31])")
        print("ihold_delay:",self.ihold_delay_value,"(Pause before moving to HOLD condition. [0->15])")

        print("")
        
    #-----------------------------------------------------------------------------------------------
    
    def run_to_position_steps(self, steps, callback=None):
        """ Move motor to a new target position.
        
            Parameters --------------------------------------------        
            steps    : Number of steps to move.
            callback : Optional method to call for each step."""
        self._target_pos = self._current_pos + steps # Where is the motor heading?    
        self._stop = StopMode.NO # Motor is not yet stopped. 
        self._step_interval = 0
        self._speed = 0.0
        self._n = 0
        self.compute_new_speed() # How fast should the motor move?
        while self.run(): # returns false, when target position is reached
            if (callback != None): callback() # Can callback a parent process if required.
            if self._stop == StopMode.HARDSTOP:
                break

        self._movement_phase = MovementPhase.STANDSTILL # Motor has stopped. 
        return self._stop

    #-----------------------------------------------------------------------------------------------
    
    def run(self):
        """ Return TRUE if motor is not yet at target position.
            Return FALSE when motor reaches target position. 
            Parameters --------------------------------------------        """
        if self.run_speed(): # returns true, when a step is made
            self.compute_new_speed()
        return self._speed != 0.0 and self.distance_to_go() != 0

    #-----------------------------------------------------------------------------------------------
    
    def distance_to_go(self):
        """ Return the number of steps needed to reach the target. 
            Parameters --------------------------------------------        """
        return self._target_pos - self._current_pos

    #-----------------------------------------------------------------------------------------------
    
    def compute_new_speed(self):
        """
            Parameters --------------------------------------------        """
        # Generate stepper-motor speed profiles in real time" by David Austin
        # https://www.embedded.com/generate-stepper-motor-speed-profiles-in-real-time/

        distance_to = self.distance_to_go() # +ve is clockwise from current location
        steps_to_stop = (self._speed * self._speed) / (2.0 * self._acceleration) # Equation 16
        if ((distance_to == 0 and steps_to_stop <= 2) or
        (self._stop == StopMode.SOFTSTOP and steps_to_stop <= 1)):
            # We are at the target and its time to stop
            self._step_interval = 0
            self._speed = 0.0
            self._n = 0
            self._movement_phase = MovementPhase.STANDSTILL
            return

        if distance_to > 0:
            # We are anticlockwise from the target
            # Need to go clockwise from here, maybe decelerate now
            if self._n > 0:
                # Currently accelerating, need to decel now? Or maybe going the wrong way?
                if ((steps_to_stop >= distance_to) or self._direction == Direction.CCW or
                    self._stop == StopMode.SOFTSTOP):
                    self._n = -steps_to_stop # Start deceleration
                    self._movement_phase = MovementPhase.DECELERATING
            elif self._n < 0:
                # Currently decelerating, need to accel again?
                if (steps_to_stop < distance_to) and self._direction == Direction.CW:
                    self._n = -self._n # Start acceleration
                    self._movement_phase = MovementPhase.ACCELERATING
        elif distance_to < 0:
            # We are clockwise from the target
            # Need to go anticlockwise from here, maybe decelerate
            if self._n > 0:
                # Currently accelerating, need to decel now? Or maybe going the wrong way?
                if (((steps_to_stop >= -distance_to) or self._direction == Direction.CW or
                    self._stop == StopMode.SOFTSTOP)):
                    self._n = -steps_to_stop # Start deceleration
                    self._movement_phase = MovementPhase.DECELERATING
            elif self._n < 0:
                # Currently decelerating, need to accel again?
                if (steps_to_stop < -distance_to) and self._direction == Direction.CCW:
                    self._n = -self._n # Start acceleration
                    self._movement_phase = MovementPhase.ACCELERATING
        # Need to accelerate or decelerate
        if self._n == 0:
            # First step from stopped
            self._cn = self._c0
            self._pin_step.SetValue(False)
            if distance_to > 0:
                self.set_direction_pin_or_reg(1)
            else:
                self.set_direction_pin_or_reg(0)
            self._movement_phase = MovementPhase.ACCELERATING
        else:
            # Subsequent step. Works for accel (n is +_ve) and decel (n is -ve).
            self._cn = self._cn - ((2.0 * self._cn) / ((4.0 * self._n) + 1)) # Equation 13
            self._cn = max(self._cn, self._cmin)
            if self._cn == self._cmin:
                self._movement_phase = MovementPhase.MAXSPEED
        self._n += 1
        self._step_interval = self._cn
        self._speed = 1000000.0 / self._cn
        if self._direction == 0:
            self._speed = -self._speed

    #-----------------------------------------------------------------------------------------------
    
    def run_speed(self):
        """ 
            Parameters --------------------------------------------        """
        # Don't do anything unless we actually have a step interval
        if not self._step_interval:
            return False
        curtime = time.monotonic_ns()/1000 # Monotonic clock as microseconds. 
        if curtime - self._last_step_time >= self._step_interval:

            if self._direction == 1: # Clockwise
                self._current_pos += 1
            else: # Anticlockwise
                self._current_pos -= 1
            self.make_a_step() # Apply pulse to the motor's STEP pin. See *Q* inside this method.
            self._last_step_time = curtime # Caution: does not account for costs in making step()

            return True
        return False

    #-----------------------------------------------------------------------------------------------

    def sleep(self,delay=1.0):
        """ A 'sleep' function that operates on times faster than 0.001 seconds.
            The traditional time.sleep() doesn't operate below 0.001 seconds in CircuitPython.
            For times briefer than 0.001 seconds this uses the time.monotonic_ns() clock instead.
            This has an overhead of around 0.00005 seconds on a Pico2 at 220MHz. """
        if delay < 0.001: # Use alternative sleep functionality for very brief periods.
            start_ns = time.monotonic_ns() # When did the delay start?
            delay_ns = int(delay * 1e9) # How long does the delay last in nanoseconds?
            end_ns = start_ns + delay_ns # When should the delay end?
            while True: # Loop until we hit the END time.
                now_ns = time.monotonic_ns() # Get the latest nanosecond timer value.
                if now_ns >= end_ns: # Timer expired.
                    break
                if now_ns < start_ns: # Nanosecond timer has reset.
                    print("ns_sleep(): Clock reset.")
                    break
        else: time.sleep(delay) # Use standard CircuitPython sleep function.

    
    #def sleep(self,delay):
    #    """ Execute a sleep based upon the monotonic clock if it's too brief for time.sleep() to work properly. """
    #    if delay >= 0.001: time.sleep(delay)
    #    else: # Need to create a delay a different way. 
    #        print("TMCStepper.sleep(): NOT YET IMPLEMENTED")
    #        # Get start timer.
    #        # Calculate end time.
    #        # if current time < start time or > end time: quit.
            
    #-----------------------------------------------------------------------------------------------
    
    def make_a_step(self):
        """ Make a single STEP by triggering a pulse on the STEP pin for the motor. 
            *Q* CircuitPython time.sleep() does not support times less than 0.001 seconds (2025). 
            This may not work as expected, the 'delay' will simply return as fast as possible.
            Parameters --------------------------------------------        
            
            Used by:
            - self.run_speed() """
        self._pin_step.SetValue(True)
        #time.sleep(1/1000/1000) # *Q* CircuitPython time.sleep() does not support times less than 0.001 seconds. This may not work as expected?
        self.sleep(1/1000/1000)
        self._pin_step.SetValue(False)
        #time.sleep(1/1000/1000) # *Q* CircuitPython time.sleep() does not support times less than 0.001 seconds. This may not work as expected?
        self.sleep(1/1000/1000)

    #-----------------------------------------------------------------------------------------------
    
    def rps_to_vactual(self, rps, steps_per_rev, fclk = 12000000):
        """ Convert revolutions per second to vactual.
        
            Parameters --------------------------------------------        
            rps : revolutions per second.
            steps_per_rev = steps per revolution.
            fclk : clock speed of the TMC2209 chip. 
            
            16777216 = 2 ** 24 """
        return int(round(rps / (fclk / 16777216) * steps_per_rev))

    #-----------------------------------------------------------------------------------------------
    
    def vactual_to_rps(self, vactual, steps_per_rev, fclk = 12000000):
        """ Convert vactual to revolutions per second. 
        
            Parameters --------------------------------------------        
            vactual : Value for VACTUAL.
            steps_per_rev : Steps per revolution.
            fclk : clock speed of TMC2209 chip. 
            
            16777216 = 2 ** 24 """
        return vactual * (fclk / 16777216) / steps_per_rev

    #-----------------------------------------------------------------------------------------------
    
    def rps_to_steps(self, rps, steps_per_rev):
        """ Convert revs_per_second to steps_per_rev 
            
            Parameters --------------------------------------------
            rps : revolutions per second.
            steps_per_rev : Steps per revolution.
            """
        return rps * steps_per_rev

    #-----------------------------------------------------------------------------------------------
    
    def steps_to_rps(self, steps, steps_per_rev):
        """ Convert motor steps to revs_per_second value.
        
            Parameters --------------------------------------------        
            steps : step count
            steps_per_rev : Steps per revolution. """
        return steps / steps_per_rev

    #-----------------------------------------------------------------------------------------------
    
    def rps_to_tstep(self, rps, steps_per_rev, msres):
        """ Convert revs_per_second to tstep values. 
        
            Parameters --------------------------------------------        
            rps : revolutions per second.
            steps_per_rev : steps per revolution.
            msres : microstep resolution (?) """
        return int(round(12000000 / (rps_to_steps(rps, steps_per_rev) * 256 / msres)))

    #-----------------------------------------------------------------------------------------------
    
    def steps_to_tstep(self, steps, msres):
        """ Convert motor steps to tstep values. 
        
            Parameters --------------------------------------------
            steps : step count.
            msres : microstep resolution (?)           """
        return int(round(12000000 / (steps * 256 / msres)))

    #-----------------------------------------------------------------------------------------------
    
    def constrain(self, val, min_val, max_val):
        """ Clip a value between lower/upper limits. 
        
            Parameters --------------------------------------------        
            val : Value to constrain.
            min_val : Minimum value allowed.
            max_val : Maximum value allowed. 
            
            Used by:
            - self.set_speed() """
        if val < min_val:
            return min_val
        if val > max_val:
            return max_val
        return val
