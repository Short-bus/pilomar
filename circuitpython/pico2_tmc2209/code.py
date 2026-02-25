# code.py - Circuitpython 9.2 build for Raspberry Pi Pico 2 (RP2350).
# For use with Raspberry Pi Pico 2 only.
# Dec.2024 / Refactored with help from TPROFFEN.
# May.2025 / Now exclusively Pico2 code version.

# Sample messages...
#  From microcontroller to RPi
#   session status 20210409090929 False False False 20 None None
#   comms status 20210409090929 0 0 538 0
#   motor status 20210409090939 azimuth False 20210409090939 0 48000 180.0 True
#   motor status 20210409090949 altitude False 20210409090949 0 0 0.0 True
#  From RPi to microcontroller
#   configure motor 20210409090949 azimuth 180.0
#   sendstatus 20210409090949 False

# NOTE: If you get memory and other errors thrown at you when you try to load a new version of this program
# onto the microcontroller :-
# - The microcontroller can switch to 'read-only' mode sometimes.
#   Search online for 'reset file system in circuitpython'
# 
#      From REPL in Thonny
#      >>> import storage
#      >>> storage.erase_filesystem()
#
#      You can then try downloading code.py once more.
# - If you cannot open code.py in Thonny it usually helps to restart Thonny.

# If you want to run the microcontroller with the USB cable permanently attached 
# there is a risk that the microcontroller will auto-reload randomly when the 
# RPi O/S accesses the CIRCUITPY drive.
#    (If these lines are active you will have to manually restart the 
#     microcontroller each time you update the source code. 
#     Pressing the RESET button is the most effective method.)
import supervisor
supervisor.runtime.autoreload = False
print("AUTORELOAD is disabled.")
# Call supervisor.reload() to perform a full reset of the CircuitPython environment.

# Version numbering scheme:
#       MAJOR.MINOR.MICRO
#       MAJOR = Major version, large changes to functionality. Likely to require major version change on RPi side too.
#       MINOR = Feature changes, but same overall program. May require functionality change on RPi side too.
#       MICRO = Bugfix, no feature changes. Will not require changes on RPi side.
VERSION = '1.2.0' # Software version reported to the RPi.
ACCEPTABLERPIVERSIONS = ['1.0','1.1','1.2','1.3'] # Which RPi versions are acceptable? (Ignore patch level)

print('hello')
print('This is code.py for CircuitPython.')
print('This supports: Raspberry Pi Pico 2.')
print('This version does NOT fit onto the original Raspberry Pi Pico (1).')

from pilomar.helpers import * # Utility classes and methods used in this program. (logfile, clock, gpio etc)
print('pilomar.helpers:',helpers_version) # Print source code version number.
#from pilomar.trajectory import * # Trajectory handling classes and methods used in this program. (trajectorypoint and trajectory) *Q* IS this needed here???
#print('pilomar.trajectory:',trajectory_version) # Print source code version number.
from pilomar.devices import * # Handlers for various supported devices (lis3dh, as5600 position sensors etc)
print('pilomar.devices:',devices_version) # Print source code version number.
from pilomar.steppermotor import * # Handlers for steppermotors. (tmc2209 etc)
print('pilomar.steppermotor:',steppermotor_version) # Print source code version number.

# Check we are running CircuitPython.
CircuitPythonVersion, Bootline, CircuitPython = check_version() # From pilomar.helpers
print("CircuitPython installed:",CircuitPython, "version:",CircuitPythonVersion,"environment:",Bootline)

import digitalio
import board
print("This board is",board.board_id)
from busio import UART as busio_UART # Only need the UART and I2C features.
print("Creating I2C channel (SDA=GP4, SCL=GP5)")
from busio import I2C as busio_I2C 
import time
import struct
import math
import gc # Garbage Collector
i2c = busio_I2C(board.GP5, board.GP4)
program_start_ns = time.monotonic_ns() # Monotonic clock as program starts. *Q* Report up-time in status messages.

# What features do we have available on this board?
# Will contain a list like ['RP2350','TINY'], ['RP2040','TINY'], ['RP2350','PICO'], etc.
FEATURES = []
if board.board_id in ['raspberry_pi_pico2']:
    FEATURES.append('RP2350') # Can use capacity and features of RP2350 chip.
    FEATURES.append('PICO')
    FEATURES.append('VMOT') # We will measure motor voltage via ADC0 on these microcontrollers. 
    FEATURES.append('TMC2209')
else:
    print("This version only runs on RPi Pico2")
    print("This is",board.board_id)
    exit()

print("FEATURES:",FEATURES)

# Before initializing any communications, change the clock frequency.
import microcontroller
target = 220000000
microcontroller.cpu.frequency = target # Set to 220MHz (default 150MHz on Tiny2350)#temp = microcontroller.cpu.frequency
print("Set clock frequency on",board.board_id,"to:",microcontroller.cpu.frequency,"Hz")
    
StatusLed = statusled(features=FEATURES)
StatusLed.Task('init') # System is initializing...
print("Pausing 1 second at",time.monotonic_ns(),"...")
ns_sleep(delay=1) # Pause 1 second.
print("Done at",time.monotonic_ns(),".")

ExceptionCounter = exceptioncounter(StatusLed) # Exception counter instance. Records code exceptions and flashes status LED.
DegreeSymbol = 'deg'
print("Base clock:",IntToTimeString(time.time()))
SessionTimer = timer('session',30,offset=7)
LogFile = logfile() # Create log handler.

Clock = clock(LogFile=LogFile, ExceptionCounter=ExceptionCounter, RPi=None, TimeValue=time.time()) # Simulate RTC
LogFile.Clock = Clock # Tell the LogFile which clock to use.

from pilomar.uarthost import uarthost # For serial communication over UART with Raspberry Pi.
RPi = uarthost(channel=0,logfile=LogFile,exceptioncounter=ExceptionCounter,statusled=StatusLed,clock=Clock) # Create UART serial comms with Raspberry Pi.
print("RPi UART communication baud rate:",RPi.BaudRate)
LogFile.setHost(RPi) # Tell the log file where to send messages.

# Show why the microcontroller (re)started.
print('ResetReason: ' + str(microcontroller.cpu.reset_reason))
    
def SendCpuStatus():
    """ Report microcontroller condition back to RPi.

        Output ---------------------------------------
        cpu status 20250531114534 POWER_ON 220 1.3 33040 10232 27 RP2350_PICO_VMOT   
         0    1          2           3      4   5    6     7    8        9        
         
        3 = Reset Reason (if CircuitPython declares it, not all microcontroller instances do.) 
        4 = Clock frequency (in MHz) 
        5 = CPU voltage (if CircuitPython declares it, not all microcontroller instances do.) 
        6 = Memory allocated 
        7 = Memory free 
        8 = CPU temperature 
        9 = FEATURES """
    line = 'cpu status ' + IntToTimeString(Clock.Now()) + ' '
    line += str(microcontroller.cpus[0].reset_reason).split('.')[-1].replace(' ','_') + ' '
    line += str(microcontroller.cpus[0].frequency / 1e6) + ' ' 
    line += str(microcontroller.cpus[0].voltage) + ' '
    line += str(gc.mem_alloc()) + ' ' + str(gc.mem_free()) + ' '
    line += str(int(microcontroller.cpus[0].temperature)) + ' '
    temp = ''
    for t in FEATURES:
        if temp != '': temp += '_'
        temp += str(t)
    line += temp + ' ' # Send feature list.
    RPi.Write(line)

# Use ADC to read VMOT value. We can detect if motors are actually powered.
# - Losing power is an easy problem to detect and report.
# - Also can give clues if running off batteries and they are running low.
import analogio
VMotADC = analogio.AnalogIn(board.A0)

def VMot():
    """ Read the current MotorPower ADC value directly. 
        Don't scale for voltage, let the host deal with that. """
    result = VMotADC.value
    return result

def MotorsPowered():
    """ Return TRUE if VMot is above threshold. 
        Indicating that motors are powered.
        Anything under 5000 on ADC0 is considered 'unpowered'.
        In testing: VMot returns 0 - 3100 when no power connected (presumably an open circuit on ADC0).
                    If power lost, it gradually decays to around 0.
                    VMot returns 23333 when 12.75V connected. """
    if VMot() > 5000: return True
    else: return False 
    
print('Defining pins for',board.board_id)

#DevButtonBCM = GPIOpin(board.GP18,'dev_button') # Pico GP18 is a development button. Not in final design.
#DevButtonBCM.SetDirection(digitalio.Direction.INPUT)
#DevButtonBCM.SetPullUp() # Button open state is HIGH (ON), when button is pressed it goes LOW (OFF).

CommonEnableBCM = GPIOpin(board.GP21,'common_enable') # Pico (COM_EN)
CommonEnableBCM.SetDirection(digitalio.Direction.OUTPUT)
CommonEnableBCM.SetValue(False) # Set LOW to enable.

CommonDirectionBCM = GPIOpin(board.GP16,'common_dir') # Pico (COM_DIR)
CommonDirectionBCM.SetDirection(digitalio.Direction.OUTPUT)
CommonDirectionBCM.SetValue(False)

AzimuthStepBCM = GPIOpin(board.GP7,'azimuth_step') # Pico (AZ_STEP)
AzimuthStepBCM.SetDirection(digitalio.Direction.OUTPUT)
AzimuthStepBCM.SetValue(False)

AltitudeStepBCM = GPIOpin(board.GP17,'altitude_step') # Pico (AZ_STEP)
AltitudeStepBCM.SetDirection(digitalio.Direction.OUTPUT)
AltitudeStepBCM.SetValue(False)

AzimuthFaultBCM = GPIOpin(board.GP10,'azimuth_fault') # Pico (AZ_FAULT)
AzimuthFaultBCM.SetDirection(digitalio.Direction.INPUT) 
AzimuthFaultBCM.SetPull(digitalio.Pull.UP)

AltitudeFaultBCM = GPIOpin(board.GP22,'altitude_fault') # Pico (ALT_FAULT)
AltitudeFaultBCM.SetDirection(digitalio.Direction.INPUT) 
AltitudeFaultBCM.SetPull(digitalio.Pull.UP)

MotorStopBCM = GPIOpin(board.GP11,'motor stop') # Pico (MSTOP)
MotorStopBCM.SetDirection(digitalio.Direction.INPUT) 
MotorStopBCM.SetPull(digitalio.Pull.UP)

class limitswitch():
    """ Define a limit switch and its action. 
        They can define MIN, MAX or just CALIBRATION actions for a motor. 
        
        
        Example usage ----------------------------------------------------------------
        DevButtonBCM = GPIOpin(pin=board.GP18,name='dev_button',invert=True) # Goes LOW when pressed.
        DevButtonBCM.SetDirection(digitalio.Direction.INPUT)
        DevButtonBCM.SetPullUp() # Button open state is HIGH (ON), when button pressed it goes LOW (OFF).
        LimSw = limitswitch(name='testls',motor=Azimuth,pin=DevButtonBCM,angle=0,action='minimum',enabled=True,logfile=LogFile)
        
        """
        
    switches = [] # Global list of all defined limit switches. 
    pins = [] # Global list of all defined pins.
    
    #@staticmethod
    #def ScanAllSwitches():
    #    """ Will scan all input switches and trigger any appropriate actions.
    #        This is static, so call it with limitswitch.ScanTriggers() """
    #    
    #    # Which pins have been triggered? Note them here because we allow multiple triggers to share the same pin.
    #    triggered_pins = [] # List of pin names that have been triggered.
    #    for pin in limitswitch.pins:
    #        if pin.Pressed(): triggered_pins.append(pin.Name) # Switch has just triggered.
    #    # Now find all triggers that use the identified pins.                 
    #    for sw in limitswitch.switches:
    #        if sw.Pin.Name in triggered_pins and sw.Enabled: # Has the pin just gone LOW since the last poll? (ie it's triggered?)
    #            sw.Trigger() # Trigger appropriate action in the steppermotor instance.
    
    def __init__(self,name,motor,pin,angle,action,enabled,logfile):
        """ Define new limit switch rule for a stepper motor.
            Here you can assign a GPIO pin to act as a trigger for a stepper motor.
            A single GPIO pin can trigger multiple rules in multiple motors if needed.

            Parameters -------------------------------------------
            name : A name for the switch.
            motor : Instance of 'steppermotor' class - the motor this trigger applies to.
            pin : instance of GPIOpin for the actual switch.
                # To create the instance of GPIOpin externally....
                Pin = GPIOpin(pin_number,pin_name) # Create pin.
                Pin.SetDirection(digitalio.Direction.INPUT)
                Pin.pull = digitalio.Pull.UP
                
                pin exposes the following 'input' methods:
                .Deinit(), .SetPull(), .SetPullUp(), .SetPullDown(),
                .GetValue(), .High(), .IsOn(), .Low(), .IsOff(),
                .Rise(), .Pressed(), .Fall(), .Released(), .PinStatus()
                
            angle : What angle is the limit switch at? 
            action : 'min','max','calibrate' 
               'min' : Indicates that the motor has reached minimum movement. 
               'max' : Indicates that the motor has reached maximum movement.
               'calibrate' : Indicates that the motor has reached a specific angle, but can continue moving. 
            logfile : Instance of logfile class. """
        self.Name = name # Name of the limitswitch.
        self.Motor = motor # Instance of steppermotor() that this limitswitch rule applies to.
        self.Pin = pin # Instance of GPIOpin() for the actual switch. Define externally because multiple triggers can share a pin.
        self.Enabled = True # Is the pin active?
        # Define characteristics.
        self.Angle = angle # What angle does the limitswitch represent?
        self.Action = action.lower() # What action should happen when triggered?
        self.Log = logfile.Log
        if not self in self.Motor.LimitSwitches: 
            self.Motor.LimitSwitches.append(self) # Tell the motor it is responsible for this limit switch.
        limitswitch.switches.append(self) # Add this limitswitch rule to the global list.
        if not pin in limitswitch.pins: # First occurrence of this GPIO pin, add it to the list of pins to monitor.
            limitswitch.pins.append(pin) # Add this GPIO pin to the global list.
        
    #def Trigger(self):
    #    """ Call this when the limit switch is triggered. 
    #        It calls the trigger routine in the motor instance.
    #        The Motor instance should provide callable methods as defined here.
    #        - LimitSwitchTriggered(x) : x is the instance of the limitswitch so that it's type, values and actions can be understood. """
    #    self.Log("limitswitch.Trigger(",self.Name,"):",self.Motor.MotorName)
    #    if hasattr(self.Motor,'LimitSwitchTriggered'): self.Motor.LimitSwitchTriggered(self) # Call the motor method for handling triggers.
    #    else: self.Log("limitswitch.Trigger(",self.Name,"): No LimitSwitchTriggered() method in",self.Motor.MotorName)

# Pico2 pins :-
# 'A0', 'A1', 'A2', 'A3', 'GP0', 'GP1', 'GP10', 'GP11', 'GP12', 'GP13', 'GP14',
# 'GP15', 'GP16', 'GP17', 'GP18', 'GP19', 'GP2', 'GP20', 'GP21', 'GP22', 'GP23',
# 'GP24', 'GP25', 'GP26', 'GP26_A0', 'GP27', 'GP27_A1', 'GP28', 'GP28_A2', 'GP3',
# 'GP4', 'GP5', 'GP6', 'GP7', 'GP8', 'GP9', 'LED', 'SMPS_MODE', 'STEMMA_I2C',
# 'VBUS_SENSE', 'VOLTAGE_MONITOR'

print("Creating TMCuart for motor drivers...")
print("VMOT ADC value is",VMot(),"(Remember, no VMOT = no communication!)")
print("-    16 = 0V (disconnected)")
print("-  9000 ~= 5V")
print("- 22000 ~= 12V")

TMC_BAUD_RATE = 19200 # 9600, 19200, 115200 supported.
TMC_BAUD_RATE = 9600 # 9600, 19200, 115200 supported.
print("Initiating TMCUART (UART1) with TX on GP8, RX on GP9,",TMC_BAUD_RATE,"baud.")
TMCuart = busio_UART(board.GP8,board.GP9,baudrate=TMC_BAUD_RATE,receiver_buffer_size=1024,timeout=0) # Define UART1 as the serial comms channel to the TMC2209 chip. (MEDIUM)

# Configure Motors.
Azimuth = steppermotor('azimuth',logfile=LogFile,clock=Clock,exceptioncounter=ExceptionCounter,features=FEATURES,TMCuart=TMCuart,motor_id=0,rpi=RPi,vmot=VMot,statusled=StatusLed)
Azimuth.SetPins(stepBCM=AzimuthStepBCM,directionBCM=CommonDirectionBCM,enableBCM=CommonEnableBCM,faultBCM=AzimuthFaultBCM) # Direct control over Azimuth motor.
Azimuth.SetConfig(gearratio=(60 * 4),motorstepsperrev=400,minangle=45.0,maxangle=315.0,restangle=180.0,currentangle=180.0,orientation=1,backlashangle=0.0) # Default configuration, can be overriden from the RPi.

Altitude = steppermotor('altitude',logfile=LogFile,clock=Clock,exceptioncounter=ExceptionCounter,features=FEATURES,TMCuart=TMCuart,motor_id=1,rpi=RPi,vmot=VMot,statusled=StatusLed)
Altitude.SetPins(stepBCM=AltitudeStepBCM,directionBCM=CommonDirectionBCM,enableBCM=CommonEnableBCM,faultBCM=AltitudeFaultBCM) # Direct control over Altitude motor.
Altitude.SetConfig(gearratio=(60 * 4),motorstepsperrev=400,minangle=0.0,maxangle=90.0,restangle=0.0,currentangle=0.0,orientation=-1,backlashangle=0.0) # Default configuration, can be overriden from the RPi.

Motors = steppermotor.motor_list # Shortcut to list of 'all' motors.

# Configure sensors.
print("Creating as5600 position sensor instance for measuring azimuth...")
try:
    ps = as5600_handler(name='azimuth',i2c=i2c,invert=True,parent=Azimuth,clock=Clock) # Create as5600 instance for measuring AZIMUTH position.
    if not Azimuth.add_position_sensor(ps):
        raise Exception("Unable to add position sensor to",Azimuth.MotorName,"motor.")
except Exception as e:
    print("Unable to create Azimuth as5600:",str(e))
    LogFile.Log("Unable to create Azimuth as5600:",str(e))
    Azimuth.add_position_sensor(None)
    ExceptionCounter.Raise()

print("Creating lis3dh position sensor instance for measuring altitude...")
try:
    ps = lis3dh_handler(name='altitude',i2c=i2c,orientation=lis3dh_handler.ORIENTATION_1,offset=0,invert=False,parent=Altitude,decimals=3,clock=Clock) # Create lis3dh instance for measuring altitude position.
    if not Altitude.add_position_sensor(ps):
        raise Exception("Unable to add position sensor to",Altitude.MotorName,"motor.")
except Exception as e:
    print("Unable to create Altitude lis3dh:",str(e))
    LogFile.Log("Unable to create Altitude lis3dh:",str(e))
    Altitude.add_position_sensor(None)
    ExceptionCounter.Raise()

class picosession():
    def __init__(self):
        """ Create new instance of picosession. """
        self.SessionStart = time.time()
        self.AutonomousControl = False # Triggers movement of the motors when they are configured and trajectories loaded.
        self.RemoteControl = False # Allows movement of the motors when they are configured, regardless of trajectories existing.
        self.Quit = False # Set to TRUE to terminate the session.
        self.TrajectorySafetyms = 2 * 60 * 1000 # How many milliseconds can a valid trajectory remain in use before comms failure terminates it? == 2 minutes.
        self.TrajectorySafetyFlushes = 0 # How many times have we had to flush the trajectories for safety when comms seemed to fail?
        self.FailsafeLatch = False # Latch to prevent 'failsafe' messages flooding the communication buffers when safety flush is triggered.

    def ScanMotorStop(self):
        """ Check the motor stop button state and set the MotorHalt attribute if needed.
            Send immediate status back to the RPi so it knows the motors are now halted. """
        if MotorStopBCM.GetValue() == False: # MSTOP pin has been grounded. Halt the motors.
            print("picosession.ScanMotorStop: MSTOP triggered. Value:",MotorStopBCM.GetValue(),". Latching MotorHalt flag.")
            LogFile.Log("MSTOP triggered")
            for i in Motors: 
                if not i.MotorHalt:
                    LogFile.Log(i.MotorName,"Latching MotorHalt flag")
                    i.MotorHalt = True
                    i.SendMotorStatus(immediate=True,codes='mstop')

    def MovePermission(self):
        """ Decide if the microcontroller can accept remote control of the motors.
            They will move under the direction of the remote RPi. 
            RemoteControl means the RPi can directl motor movement, but the microcontroller may not be ready to autonomously handle a trajectory plan. 
            AutonomousControl means the microcontroller can autonomously handle a trajectory plan from the RPi. """
        result = True
        for i in Motors: # for ALL motors.
            if not i.MotorConfigured: 
                result = False # Motor must be configured.
                break
        self.RemoteControl = result
        # Decide if the microcontroller can have autonomous control of the motors.
        # They may start moving immediately.
        if not Clock.ClockSynchronised: result = False # Clock must be synchronised.
        for i in Motors: # for ALL motors.
            if not i.Trajectory.Valid: 
                result = False # Trajectory must be valid.
                break
            if i.MotorHalt:
                result = False # MotorHalt flag is set.
                break
        self.AutonomousControl = result

    #def SendMotorStatus(self,motorname,immediate=False,codes='?-?'):
    #    """ Decide which motor status to send. 
    #        immediate: True: Status is sent even if not due. 
    #                   False: Status is only sent if timer is due. 
    #        codes: Optional extra codes added to the status message (dev/test/debug etc) """
    #    print("*** picosession.SendMotorStatus(): Call not expected. Deprecated method! ***")
    #    for i in Motors:
    #        if i.MotorName == motorname: i.SendMotorStatus(immediate=immediate,codes=codes)
            
    def TrajectorySafety(self):
        """ If the remote RPi crashes while a trajectory is underway but leaves the microcontroller powered
            the microcontroller will continue to follow the trajectory until it expires, this could be 20+ minutes.        
            For safety, clear trajectories of all motors if communication has stalled. 
            If communication resumes, the RPi will send the trajectory again. """
        failsafe = False
        try:
            elapsed = RPi.ticks_ms() - RPi.LastRxms # How many ms elapsed since last receipt?
        except:
            elapsed = 0
            LogFile.Log('TrajectorySafety: elapsed calculation failed.',RPi.ticks_ms(),RPi.LastRxms)
            ExceptionCounter.Raise() # Increment exception count for the session.
        if self.TrajectorySafetyms != None and elapsed > self.TrajectorySafetyms: # No messages received recently.
            for i in Motors:
                if i.Trajectory.Valid: # There's a trajectory underway.
                    failsafe = True # Trigger failsafe activity.
        if failsafe and self.FailsafeLatch == False:
            LogFile.Log('TrajectorySafety:',elapsed,'ms, failsafe?')
            self.FailsafeLatch = True # Don't let this message repeat continually.
            self.TrajectorySafetyFlushes += 1 # Increment the number of times we've flushed the trajectories for safety.
            for i in Motors:
                i.ClearTrajectory() # Flush the trajectory from each motor for safety.
        if failsafe == False: self.FailsafeLatch = False # Reset the latch.

    def SendSessionStatus(self,codes='?-?'):
        """ Generate status message to RPi.
            The RPi uses this to decide what commands and configurations to send to the microcontroller.
            This can send multipleitems to the RPi, they are sent individually in sequence rather than as
            a single large packet of everything. Smaller messages work more reliably.
            codes: Optional extra flags added to status message (dev/test/debug etc)
            """
        if CircuitPythonVersion.split('.')[0] in ('7','8','9'): pass # Supported CircuitPython version.
        else: # Unexpected CircuitPython version, report it back.
            line = '# Expecting CircuitPython 7,8 or 9, found ' + str(CircuitPythonVersion)
            RPi.Write(line) # Send over UART to RPi.
        line = "session status "
        i = time.time() - RPi.StartTime # Alive seconds. Use CPU clock not synchronised clock.
        line += IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        line += BoolToString(Clock.ClockSynchronised) + ' ' # Do the RPi and microcontroller clocks agree?
        line += BoolToString(self.AutonomousControl) + ' '  # Can motors drive themselves? Fully configured and trajectory known.
        line += BoolToString(self.RemoteControl) + ' '  # Can motors be commanded remotely? Fully configured.
        line += str(i) + ' ' # Alive seconds. Use CPU clock, not synchronised clock.
        line += str(self.TrajectorySafetyFlushes) + ' ' # How many times has the trajectory been flushed for safety when comms failed?
        line += str(codes) + ' ' # Add optional extra codes.
        line += str(ExceptionCounter.Count) + ' ' # Append count of exceptions raised during operation.
        line += str(VERSION) + ' ' # Append software version.
        RPi.Write(line) # Send over UART to RPi.
        line = "comms status "
        line += IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        line += str(RPi.PicoRxErrors) + ' '  # How many messages were rejected from RPi by Microcontroller.
        line += str(RPi.CharactersRead) + ' '  # How many bytes received from RPi by Microcontroller.
        line += str(RPi.CharactersWritten) + ' '  # How many bytes written by Microcontroller to RPi.
        line += str(RPi.WriteDrops) + ' '  # How many messages were dropped due to buffer overflow?
        line += str(RPi.ReceiveAge()) + ' ' # Report how old the last received message is...
        line += str(RPi.ReadDrops) + ' ' # How many received messages have been dropped because input buffer was full?
        line += str(len(RPi.WriteQueue)) + ' ' # How many messages in the send queue currently? Checking for backlog building up.
        line += str(codes) + ' ' # Add optional extra codes.
        RPi.Write(line) # Send over UART to RPi.

    def SendPinStatus(self,namelist=[]): # Send a status message back to the RPi showing all the configured pins and their condition.
        """ Receives a pin query like this ...
        
            pin query YYYYMMDDHHMMSS azstep                  <- Will reply with azstep pin.
            pin query YYYYMMDDHHMMSS mode0 mode1 mode2       <- Will reply with 3 mode pins.
            pin query YYYYMMDDHHMMSS                         <- Will reply with ALL pins.
        
            Generates a PIN status line like this... 
        
            pin status YYYYMMDDHHMMSS GP29 azstep n
               or
            pin status YYYYMMDDHHMMSS GP3 mode0 n GP6 mode1 n GP7 mode2 n
               or
            pin status YYYYMMDDHHMMSS GP29 azstep n GP28 altstep n GP27 dir n GP3 mode0 n GP6 mode1 n GP7 mode2 n GP2 enable n GP10 azfault n GP22 altfault n  
                                      LED_R red n LED_G green n LED_B blue n """
        line = "pin status "
        line += IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        for pin in GPIOpin.PinList: # Go through all defined pins.
            if namelist == [] or pin.Name in namelist: line += pin.PinStatus() + ' ' # Append the ID, Name and State of the pin
        for pin in led.LedList: # Go through all defined pins.
            if namelist == [] or pin.Name in namelist: line += pin.PinStatus() + ' ' # Append the ID, Name and State of the pin
        RPi.Write(line) # Send over UART to RPi.

    def AutoMoveMotors(self): # Trigger movement of the motors.
        """ Call this to check the current position of each motor against their trajectory.
            If the motor needs to move, this will perform the motion. """
        overallresult = False
        self.MovePermission() # Is motor still capable of autonomous movement?
        if self.AutonomousControl:
            overallresult = True
            for i in Motors:
                result = i.TargetFromTrajectoryPosition() # Set target for the motor based upon trajectory if available.
                if result: # Target was successfully set.
                    #if i.TargetPosition != i.CurrentPosition: i.MoveMotor()
                    if i.TargetPosition != i.CurrentPosition: i.MoveMotorFast(slew_motor=False) # Don't need to perform fast slew if making minor moves.
                else: # Target was not successfuly set.
                    LogFile.Log('AutoMoveMotors',i.MotorName,'failed: TargetFromTrajectory returned', result)
                    overallresult = False
        return overallresult

def CheckVersionCompatibility(rpiversion):
    """ The Raspberry Pi has sent the version number for pilomar.py
        Check that it's compatible with this code.py program.
        This issues a log file warning. It will not terminate the program. """
    compversion = rpiversion[:rpiversion.rindex('.')]
    if not compversion in ACCEPTABLERPIVERSIONS:
        LogFile.Log('CheckVersionCompatibility',rpiversion,'not in',ACCEPTABLERPIVERSIONS)

def CreateLimitSwitch(line):
    """ Process 'create limitswitch' command. 
        create limitswitch timestamp switchname motorname pin angle action enabled  
        
        create limitswitch 20251101244523 az_min azimuth GP18 0 minimum true
           0        1          2            3      4      5   6     7    8 """
    success = False
    lineitems = line.split(' ')
    switchname = lineitems[3] # Identifying name of the switch.
    motorname = lineitems[4] # Identifying name of the motor.
    pin_id = lineitems[5] # Which GPIO pin ID to use? (eg 'GP18') must exist in the 'board' class.
    if not pin_id.startswith("GP"): pin_id = "GP" + pin_id # convert integer pin numbers into board recognised names.
    board_id = board.__dict__.get(pin_id,None) # Retrieve the PIN declaration from the board class.
    if board_id == None: # Could not find the pin.
        print("CreateLimitSwitch(",line,"): board does not contain",pin_id)
    else: # OK to proceed.
        inputswitch = GPIOpin(pin=board_id,name=switchname,invert=True) # Goes LOW when pressed.
        inputswitch.SetDirection(digitalio.Direction.INPUT)
        inputswitch.SetPullUp() # Button open state is HIGH (ON), when button pressed it goes LOW (OFF).
        angle = float(lineitems[6]) # What angle does the limit switch signify?
        action = lineitems[7] # What should happen when the switch is triggered?
        if len(lineitems) > 8: enabled = StringToBool(lineitems[8]) # Option to 'disable'/'enable' explicitly.
        else: enabled = True # Enabled if no other choice.
        for motor in Motors: # Find the motor.
            if motor.MotorName == motorname: # The motor exists, add the switch.
                # Create the switch and append it to the limitswitch.switches list.
                sw = limitswitch(name=switchname,motor=motor,pin=inputswitch,angle=angle,action=action,enabled=enabled,logfile=LogFile)
                success = True
    if success: LogFile.Log("CreateLimitswitch(",switchname,pin_id,"): Success.")
    else: LogFile.Log("CreateLimitswitch(",switchname,pin_id,"): Failed.")

# *Q* DEVELOPMENT TEST
print("Testing limitswitch creation:")
cls_line = 'create limitswitch 20251101114900 azmin azimuth GP18 0 minimum true'
CreateLimitSwitch(cls_line)
#exit()

def PinCommand(line):
    """ Receive a direct command for a GPIO pin and execute it. 
        
        pin {date} {name} state/on/off [duration [repeat]]
        
                                                   ^ Defines how many times to repeat the command.
                                         ^ Defines how long the signal stays at set value before reverting.
                                 ^ Turn ON or OFF the pin, or return its current state.
                   ^ The pin name (must be set when GPIOpin instance created).
            ^ Standard message timestamp string.
            
        pin 20240307013045 dir on     
            Would turn the 'dir' pin on and leave it on.
            
        pin 20240307013045 dir on 0.5
            Would turn the 'dir' pin on for 0.5 seconds then turn it off.
            
        pin 20240307013045 dir on 0.25 10
            Would turn the 'dir' pin on for 0.25 seconds then off for .25 seconds. It would do this 10 times.
            
        pin 20240307013045 dir status 
            Would return a comment message to the RPi with the current state of the 'dir' pin.
            
        """
    lineitems = line.split() # Extract individual items.
    itemcount = len(lineitems)
    if itemcount > 2: # item 2 = number/name exists.
        pin = lineitems[2] 
    else: # Incomplete command.
        RPi.Write("# pin command failed: No pin ID.")
        return False
    if itemcount > 3: # item 3 = command exists.
        command = lineitems[3].lower()
    else: # Incomplete command.
        RPi.Write("# pin command failed: No command.")
        return False
    if itemcount > 4: # item 4 = optional duration.
        duration = float(lineitems[4])
    else: duration = 0
    if itemcount > 5: # item 5 = repeat count.
        repeats = int(lineitems[5])
    else:
        repeats = 0
    pinobj = None
    for pins in GPIOpin.PinList: # Search the defined pins for the specified one.
        if pins.Name == str(pin): # Find by name.
            pinobj = pins # This is the pin instance we'll work with.
            break # Found it.
    if pinobj == None: # Failed to identify the pin.
        RPi.Write("# pin command failed: " + str(pin) + " unknown.")
        return False
    # We have a valid command.
    print(pinobj.Name,command,duration,repeats)
    for i in range(max(repeats,1)): # Loop as many times as requested.
        if command == 'on' and pinobj.Pin.direction == digitalio.Direction.OUTPUT: # Switch on and it's an OUTPUT. command
            pinobj.SetValue(True) # Turn on.
            if duration != 0: # For a limited time only.
                ns_sleep(delay=duration) # Wait until time to turn off again.
                pinobj.SetValue(False) # Turn off.
                if repeats > 0: ns_sleep(delay=duration) # If we're going to repeat, pause before repeating too.
        elif command == 'off' and pinobj.Pin.direction == digitalio.Direction.OUTPUT: # Switch off and it's an INPUT.
            pinobj.SetValue(False) # Turn off.
            if duration != 0: # For a limited time only.
                ns_sleep(delay=duration) # Wait until time to turn on again.
                pinobj.SetValue(True) # Turn on.
                if repeats > 0: ns_sleep(delay=duration) # If we're going to repeat, pause before repeating too.
        elif command == 'state': # Send pin state.
            RPi.Write("# pin status " + str(pinobj.Name) + " " + str(pinobj.Pin.value))
    return True

Session = picosession() # Instantiate a sesson object.

def ReportEnvironment():
    """ Send environment information to the host. """
    RPi.Write('# CP env ' + str(Bootline) + ' ver ' + str(CircuitPythonVersion))
    RPi.Write('# CP mem alloc ' + str(gc.mem_alloc()) + ' free ' + str(gc.mem_free()))
    RPi.Write('# FEATURES ' + str(FEATURES))
    RPi.Write('controller started') # Tell the remote device we're up and running.
    RPi.Write('controller version ' + str(VERSION)) # Tell the remote device which software version is running.

def ProcessInput(line):
    """ This is called whenever the UART serial comms receives a command from the RPi. """
    line = line.strip()
    if len(line) < 1:
        print("ProcessInput(): Received empty command line. Ignoring it.")
        return
    lineitems = line.split(' ')
    if lineitems[0] == 'exit':
        print('exit cmd received.')
        LogFile.Log('exit cmd received.')
        Session.Quit = True # Mark session as completed.
    elif lineitems[0] == 'stop': # Immediately stop motion.
        for i in Motors: 
            i.Stop()
        Session.MovePermission()
    elif line.startswith('#'): # Ignore comments.
        pass # print("ProcessInput(): Received a comment:",line)
    elif line.startswith('rpi started'):
        RPi.Write('acknowledged rpi started')
        for i in Motors: 
            i.Reset()
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith('reset motors'): # Soft reset, does not instantiate any new objects. Catch this BEFORE checking for more general RESET command.
        print("reset motors cmd received.")
        for i in Motors: 
            i.Reset() # Reset motor status to initial unconfigured state.
        RPi.Write('acknowledged reset motors') # Confirm reset performed.
    elif lineitems[0] == 'reset': # Soft reset of everything, does not instantiate any new objects.
        print("reset cmd received.")
        for i in Motors: 
            i.Reset() # Reset motor status to initial unconfigured state.
        RPi.Reset() # Flush output buffers.
        RPi.Write('acknowledged reset') # Confirm reset performed.
    elif lineitems[0] == 'sendstatus': # Turn off status messages for motors. Useful when downloading a batch of trajectories, so no conflicting requests exchanged.
        RPi.Write('# ' + line)
        for i in Motors: 
            i.SendStatus = StringToBool(lineitems[2])
    elif line.startswith('set rgb'): # A direct command to set a specific RGB LED color. (Debug support)
        StatusLed.SetRGB(line) # Set the RGB color regardless of LED status.
        RPi.Write("# Acknowledge set rgb :" + str(line)) # Echo the command back.
    elif line.startswith('raise exception'): # Generate example exception to prove status LED workds as expected.
        ExceptionCounter.Raise()
        RPi.Write('# Raised artificial exception for testing.')
    elif lineitems[0] == 'tune':
        for i in Motors:
            if i.MotorName == lineitems[2]: i.TunePosition(line)
    elif line.startswith('rpi version'):
        CheckVersionCompatibility(lineitems[3])
    elif line.startswith('pin query'):
        Session.SendPinStatus(lineitems[3:]) # Send list of names (could be an empty list).
    elif line.startswith('clear trajectory'):
        RPi.Write('cleared trajectory')
        for i in Motors:
            i.Trajectory.Clear()
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith('configure motor') or line.startswith('configure drv8825'):
        print("Received DRV8825 motor configuration for",lineitems[3])
        for i in Motors:
            if i.MotorName == lineitems[3]:
                i.ConfigureDrv8825(line) # Load configuration.
                i.SendMotorStatus(immediate=True,codes='cfg') # Immediately respond with latest motor status.
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith('configure tmc2209'):
        print("Received TMC2209 motor configuration for",lineitems[3])
        for i in Motors:
            if i.MotorName == lineitems[3]:
                i.ConfigureTmc2209(line) # Load configuration.
                i.SendMotorStatus(immediate=True,codes='cfg') # Immediately respond with latest motor status.
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith == 'report motor': # RPi has requested the motor configurations to be reported back.
        for i in Motors: 
            i.ReportMotorConfig()
    elif lineitems[0] == 'trajectory':
        for i in Motors: 
            if i.MotorName == lineitems[2]: i.AddTrajectoryPoint(line)
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif lineitems[0] == 'goto':
        for i in Motors: 
            if i.MotorName == lineitems[2]: i.GoToAngle(float(lineitems[3]))
    elif line.startswith('set time'):
        Clock.SetTimeFromString(lineitems[2])
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith('leds off'): # Go to stealth mode, turn LEDs off.
        StatusLed.Disable() # Disable the onboard status LED.
    elif line.startswith('leds on'): # Enable the LEDs to show processing.
        StatusLed.Enable() # Enable the onboard status LED.
    elif lineitems[0] == 'pin': # Direct GPIO pin command.
        PinCommand(line) # Execute the pin command.
    elif line.startswith('create limitswitch'): # Create some form of limitswitch.
        CreateLimitswitch(line) # Process the command.
    #elif line.startswith('set as5600 offset'): # Store offsets for any AS5600 rotation sensors connected to the telescope.
    elif line.startswith('set sensor offsets'): # Store offsets for any position sensors connected to the telescope.
        print("Setting position sensor angle and offsets")
        for i in Motors:
            #if hasattr(i.position_sensor,"set_reference_angle"):
            if i.position_sensor != None:
                print("Calculating offset for",i.MotorName,"at",i.StepToAngle(i.CurrentPosition))
                i.SetReferenceAngle(i.StepToAngle(i.CurrentPosition))
    #elif line.startswith('set sensor tuning'): # Turn tuning on/off.
    #    print("Setting position sensor tuning")
    #    for i in Motors:
    #        #if hasattr(i,"set_sensor_tuning"):
    #        if i.position_sensor != None:
    #            print("Changing position sensor tuning status for",i.MotorName)
    #            i.set_sensor_tuning(line)
    else:
        RPi.Write('error: unrecognised RPi command: ' + line)

MemMgr = memorymanager()

print('Starting...')
RPi.Reset() # Reset comms and send initial header.
ReportEnvironment() # Send environment information to the host.
# Report back which motors are defined.
line = "defined motors "
for i in Motors:
    line += i.MotorName + ' '
RPi.Write(line)
    
# This is the main processing loop.
try:
    while True: # Full interaction
        
        Session.ScanMotorStop() # Check for MSTOP button being engaged. Will prevent movement.
        
        try:
            LogFile.SendCheck() # Keep log file buffer under control. Flushes the buffer if it gets too large.
        except Exception as e:
            LogFile.Log("Main:LogFile.SendCheck failed.",e)
            print("Main:LogFile.SendCheck failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.

        line = ''
        try:
            line = RPi.Read() # Any input from the Raspberry Pi in the cache? 
        except Exception as e:
            LogFile.Log("Main:RPi.Read failed.",e)
            print("Main:RPi.Read failed.",e)
            print("Main:Failed on",line)
            ExceptionCounter.Raise() # Increment exception count for the session.
        try:
            if len(line) != 0: ProcessInput(line) # Process it.
        except Exception as e:
            LogFile.Log("Main:ProcessInput failed.",e)
            print("Main:ProcessInput failed.",e)
            print("Main:Failed on",line)
            ExceptionCounter.Raise() # Increment exception count for the session.

        try:
            Session.TrajectorySafety() # If no recent receipt from RPi, assume comms break take precautions and clear trajectories.
        except Exception as e:
            LogFile.Log("Main: SessionTrajectorySafety() failed.",e)
            print("Main: SessionTrajectorySafety() failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.
            
        if Session.Quit: break 
        
        try:
            if SessionTimer.Due():
                Session.SendSessionStatus(codes='tmr') # Send session status messages.
                SendCpuStatus() # Send microcontroller status.
        except Exception as e:
            LogFile.Log("Main: SessionTimer failed.",e)
            print("Main: SessionTimer failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.

        for i in Motors: # Send motor status messages if needed.                
            try:
                i.SendMotorStatus(immediate=False,codes='tmr')
            except Exception as e:
                LogFile.Log("Main:",i.MotorName,"status failed.",e)
                print("Main:",i.MotorName,"status failed.",e)
                ExceptionCounter.Raise() # Increment exception count for the session.

        try:
            RPi.WritePoll() # Send anything in the transmit buffer if it's safe.
        except Exception as e:
            LogFile.Log("Main: RPi.WritePoll() failed.",e)
            print("Main: RPi.WritePoll() failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.
            
        try:
            Session.AutoMoveMotors() # Move motors if allowed to. 
        except Exception as e:
            LogFile.Log("Main: AutoMoveMotors failed.",e)
            print("Main: AutoMoveMotors failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.

        try:
            MemMgr.Poll() # Check memory condition.
        except Exception as e:
            LogFile.Log("Main: MemMgr.Poll() failed.",e)
            print("Main:MemMgr.Poll() failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.
            
except Exception as e:
        print('Mainloop failed:', str(e))
        StatusLed.Task('error')
        print(e.args)
        ExceptionCounter.Raise() # Increment exception count for the session.

# Shutdown procedure...
RPi.Write('controller stopping')
print('controller stopping...')
# Make sure that the log file buffer is flushed fully to the remote host.
LogFile.SendCheck(force=True)
RPi.Write('# GCCount ' + str(MemMgr.GCCount))
RPi.Write('controller stopped')
LoopCounter = 0
print('Flushing final comms to RPi.')
print('Further input from RPi will be ignored.')
while len(RPi.WriteQueue) > 0:
    RPi.WritePoll()
    LoopCounter += 1
    if LoopCounter > 1000:
        print('Flushing incomplete.')
        break
print('controller stopped')
