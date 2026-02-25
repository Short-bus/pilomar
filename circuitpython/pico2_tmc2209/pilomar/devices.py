# pilomar/devices.py - Circuitpython 9.2 build for Raspberry Pi Pico 2 (RP2350).

#-----------------------------------------------------------------------------------------------

devices_version = "0.0.1" # A version number for this source code.

#-----------------------------------------------------------------------------------------------

from pilomar.helpers import * # Utility classes and methods used in this program. (logfile, clock, gpio etc)
import time
import math

# ----------------------------------------------------------------------------------------------------------------

class lis3dh_handler():
    """ Handler for lis3dh triple axis accelerometers.
        
        Offers standard pilomar sensor methods and attributes. 

        In default configuration this measures (g) on three axes to about 0.001g precision. 
        After trig conversion into angles this is giving precision of about +/- 1 degree. 
        
        Example usage ---------------------------------------
        i2c = busio_I2C(board.GP5, board.GP4) # Define I2C channel.
        L3D = lis3dh_handler(name='mysensor',i2c=i2c) # Create instance.
        L3D.SetReferenceAngle(0.0) # Set reference angle (marks device as configured)
        while True:
            angle = L3D.Angle() # Update sensor readings.
            print("Assembly angle:",L3D.assembly_angle,"deg") # Show angle of assembly including gearing.
            time.sleep(0.5)

        """

    device_list = [] # global list of defined devices. 
    VERSION = '0.0.1'
    
    # The device can be mounted in many different orientations. You can declare alternative orientations here.
    # Only the defined Pilomar project orientation is provided initially.
    ORIENTATION_1 = 1 # ZERO degrees when Y is up, rotate on X. Uses Y & Z axis to establish tilt. X remains constant so is ignored.
    
    # Register addresses:
    REGISTERS = {
        'REG_STATUS_AUX':0x07,
        'REG_OUTADC1_L':0x08, # Low byte ADC1 output.
        'REG_OUTADC1_H':0x09, # High byte ADC1 output.
        'REG_OUTADC2_L':0x0A, # Low byte ADC2 output.
        'REG_OUTADC2_H':0x0B, # High byte ADC2 output.
        'REG_OUTADC3_L':0x0C, # Low byte ADC3 output.
        'REG_OUTADC3_H':0x0D, # High byte ADC3 output.
        # 0x0E reserved.
        'REG_WHOAMI':0x0F, # Device ID number.
        # 0x10 - 0x1D reserved.
        'REG_CTRL0':0x1E, # Device operation settings. Don't mess.
        'REG_TEMPCFG':0x1F, # Temperature sensor config.
        'REG_CTRL1':0x20, # Power & axis control.
        'REG_CTRL2':0x21, # Filtering controls.
        'REG_CTRL3':0x22, # Interrupt controls.
        'REG_CTRL4':0x23, # Data formats.
        'REG_CTRL5':0x24, # Feature controls.
        'REG_CTRL6':0x25, # Feature controls.
        'REG_REFERENCE':0x26, # Reference value for interrupt generation.
        'REG_STATUS':0x27, # Data available/overrun flags.
        'REG_OUT_X_L':0x28, # X axis two's complement left-justified.
        'REG_OUT_X_H':0x29,
        'REG_OUT_Y_L':0x2A, # Y axis two's complement left-justified.
        'REG_OUT_Y_H':0x2B,
        'REG_OUT_Z_L':0x2C, # Z axis two's complement left-justified.
        'REG_OUT_Z_H':0x2D,
        'REG_FIFOCTRL':0x2E, # FIFO mode selection.
        'REG_FIFOSRC':0x2F, # FIFO stack status.
        'REG_INT1CFG':0x30, # Interrupt rules.
        'REG_INT1SRC':0x31, # Interrupt on/off per axis.
        'REG_INT1THS':0x32, # Interrupt threshold.
        'REG_INT1DURATION':0x33, # Interrupt duration.
        'REG_INT2CFG':0x34, # 2nd interrupt registers.
        'REG_INT2SRC':0x35,
        'REG_INT2THS':0x36,
        'REG_INT2DURATION':0x37,
        'REG_CLICKCFG':0x38, # CLICK configuration.
        'REG_CLICKSRC':0x39, # CLICK source control.
        'REG_CLICKTHS':0x3A, # CLICK threshold.
        'REG_TIMELIMIT':0x3B, # CLICK Time limit.
        'REG_TIMELATENCY':0x3C, # CLICK latency.
        'REG_TIMEWINDOW':0x3D, # CLICK time window. 
        'REG_ACTTHS':0x3E, # Activity threshold. (auto switching to low power)   
        'REG_ACTDUR':0x3F # Activity duration.
        }

    def __init__(self,name,i2c,address=None,orientation=None,offset=None,invert=False,parent=None,decimals=0,clock=None):
        """ Create a lis3dh sensor instance.
            Parameters -----------------------------------------------------------
            name : A name for the device. 
            i2c : The i2c service for communications.
            orientation : Code indicating how the sensor board is mounted in the device.
                          This establishes what is 'UP' for the device.
                          ORIENTATION_1 = 0Degrees when Y UP, rotate on X.
            offset : Angle added to measurement if you want ZERO DEGREES to be rotated differently.
            invert : True if you want rotation to be measured counter-clockwise.
            parent : Link to parent steppermotor instance. 
            decimals : How many decimal points to return.
            clock : Handle to CLOCK instance. """
        self.device_type = 'lis3dh'
        self.Clock = clock
        self.Name = name # A name for the device.
        self.Parent = parent # Link to the steppermotor instance that owns this sensor.
        if orientation == None: orientation = lis3dh_handler.ORIENTATION_1
        if address == None: address = 0x18 # Default to the standard I2C address.
        import adafruit_lis3dh
        self.Sensor = adafruit_lis3dh.LIS3DH_I2C(i2c,address=address)
        if offset == None: offset = 0
        self.offset_angle = offset # Initial angle to offset measurements by.
        self.invert_value = invert # Reverse direction of angle.
        self.decimals = decimals # How many decimals to return?
        lis3dh_handler.device_list.append(self) # Add this to the list of globally defined devices. 
        self.orientation = orientation # How is the sensor mounted?
        self.last_reset = None # Clock when last reset.
        self.last_measured = None # Clock when last measured.
        self.reference_angle = 0 # The assembly now knows it's pointing here!
        self.assembly_angle = 0 # The assembly now knows it's pointing here!
        self.configured = True # The lis3dh is now considered configured.
        self.absolute_position = 0 # Rotation position of the sensor in steps. This includes completed revolutions.

    def Reset(self):
        """ Reset the sensor. 
            Standard method for pilomar compatibility. """
        print("lis3dh_handler(",self.Name,").Reset():")
        regidx = lis3dh_handler.REGISTERS['REG_CTRL1']
        # Get the current value of the REG_CTRL1 register.
        hold_value = self.ReadReg(regidx)
        # Set to ZEROS for a moment. This powers down and turns off all three axes.
        self.WriteReg(regidx,0x00)
        ns_sleep(0.1) # Pause for change to take effect.
        # Reset the values of the REG_CTRL1 register. This should power back up and enable all three axes again.
        self.WriteReg(regidx,hold_value)
        ns_sleep(0.1) # Pause for change to take effect.
        self.last_reset = self.Parent.Clock.Now()
        self.last_measured = None # Clock when last measured.
        self.reference_angle = 0 # This is the angle fed to the sensor from the RPi telling it where it is currently pointing.
        self.assembly_angle = 0 # The assembly now knows it's pointing here!
        self.absolute_position = 0 # Rotation position of the sensor in steps. This includes completed revolutions.
        self.offset_angle = 0 # The offset to apply to lis3dh calculated angles.
        self.configured = False # Device is nolonger considered configured.
        return True

    def SetReferenceAngle(self,angle):
        """ Set the reference angle for the sensor.
            Standard method for pilomar compatibility.         
            Parameters ----------------------------------------------------------------
            angle : The reference angle received from the RPi at startup. This tells the true angle of the assembly.
            Outputs -------------------------------------------------------------------
            self.offset_angle : calculated offset to apply to lis3dh angles in order to match the true position of the assembly.
            self.reference_angle : the angle received from the RPI. """
        if self.configured: # Warn if we're overriding a previous configuration.
            print("lis3dh_handler.SetReferenceAngle(",self.Name,") This replaces previous",self.reference_angle,"configuration.")
        # Define new reference and offset angles. 
        self.reference_angle = angle # Note the received reference angle.
        self.offset_angle = 0 # Null out any previous offset.
        preoffset_assembly_angle = self.Angle() # What angle is the assembly at BEFORE applying offset?
        self.offset_angle = self.reference_angle - preoffset_assembly_angle # calculate the offset to apply to as5600 calculated angles.
        self.assembly_angle = self.reference_angle # The assembly now knows it's pointing here!
        #print("lis3dh.SetReferenceAngle(",self.Name,") assembly_angle:",self.assembly_angle,", reference_angle:",self.reference_angle,", offset_angle:",self.offset_angle)
        self.configured = True # The as5600 is now considered configured.

    def asbin(self,value):
        """ Convert integer value to binary. """
        temp = str(bin(int(value)))[2:] # Drop leading '0b' prefix.
        temp = (("0" * 8) + temp)[-8:]
        return temp
        
    def DumpRegisters(self):
        """ Show current value of all registers. """
        print("list3dh_handler(",self.Name,").DumpRegisters:")
        for reg_name,reg_idx in lis3dh_handler.REGISTERS.items():
            try:
                ba = self.ReadReg(reg_idx) # Returns single integer value from the register.
                print("Reg:",reg_idx,reg_name,"=",ba,"=",hex(ba),"=",self.asbin(ba))
            except Exception as e:
                print("Reg:",reg_idx,reg_name,": Cannot read:",e)

    def ReadReg(self,register:int):
        """ Read a register directly from the sensor. """
        ba = self.Sensor._read_register(register,1)[0] # Returns byte array. Only ever the 1st byte in this case.
        return ba

    def WriteReg(self,register:int, value:int):
        """ Write a value directly to a register on the sensor. """
        self.Sensor._write_register_byte(register,value) # No return.
        return True

    def ReadAdc(self,adcnum):
        """ Read any of the available ADC channels in the sensor. """
        if not adcnum in [1,2,3]:
            print("ReadAdc(",adcnum,"): Invalid adcnum.")
            return False
        return self.Sensor.read_adc_raw(adcnum)

    def GetXYZ(self):
        """ Return acceleration measure (g) of each axis. """
        self.last_measured = self.Clock.Now()
        return self.Sensor.acceleration

    def NormalizeAngle(self,angle):
        """ Apply offsets and normalize angle value to match settings. """
        if angle != None: # Check offset and invert settings.
            if self.invert_value: angle *= -1 # Reverse the scale if required.
            angle += self.offset_angle # Add any offset to the value.
            while angle < -180: angle += 360 # Clip to within -180 to +180 range.
            while angle > 180: angle -= 360
            angle = round(angle,self.decimals)
        return angle

    def Angle(self,x=None,y=None,z=None):
        """ Get current angle from the sensor, calculate based upon the physical orientation of the board mounted in the device.
            Standard method for pilomar compatibility.         
            Parameters -----------------------------------------------------------
            x, y, z: accelerometer values to use for calculation.
                     If not supplied the sensor live values are used. """
        if x == None or y == None or z == None: x,y,z = self.GetXYZ() # Get latest axis readings if we've not received any.
        if self.orientation == lis3dh_handler.ORIENTATION_1: theta = self.X_Rotation(x,y,z) # rotate about X, Y UP = 0Degrees.
        else: 
            print("lis3dh_handler(",self.Name,").Angle(): Orientation:",self.orientation,"not recognised.")
            theta = None
        theta = self.NormalizeAngle(theta) # Check offset and invert settings.
        self.assembly_angle = theta
        self.absolute_position = int(theta * 1000)
        return theta

    def X_Rotation(self,x=None,y=None,z=None):
        """ Measure rotation around X axis. """
        if x == None or y == None or z == None: x,y,z = self.GetXYZ()
        theta = math.degrees(math.atan2(-1 * z,y))
        theta = self.NormalizeAngle(theta) # Check offset and invert settings.
        return theta
        
    def GetStatusLine(self):
        """ Return a status line to be reported back to RPi.
            Standard method for pilomar compatibility. """
        line = "# lis3dh status " + self.Name + " "
        line += IntToTimeString(self.Parent.Clock.Now()) + " "
        line += "AA " + str(self.assembly_angle) + " " 
        line += "CO " + str(self.configured) + " "
        line += "AP " + str(self.absolute_position) + " "
        return line

    def MonitorAngle(self):
        """ Standard method for pilomar compatibility. 
            Continuous loop to report angle measurement.
            You need to break out of this once started. """
        prev_angle = None
        while True:
            angle = self.Angle()
            if angle != prev_angle:
                prev_angle = angle
                print(IntToTimeString(self.Parent.Clock.Now()),angle)
                time.sleep(0.5)
                
# --------------------------------------------------------------------------------------------------------
        
class as5600_handler():
    
    """ Handler for as5600 hall effect rotation sensors. 
        This is for a generic as5600 sensor.
        
        Offers standard pilomar sensor methods and attributes. 
        
        Maintains a number of different position measures. All are updated by calling the .Angle() method.
        SENSOR POSITION/ANGLE : The orientation of the actual sensor (irrespective of gearing or the number of rotations.
        ABSOLUTE POSITION : The current position of the sensor including excess rotations. (irrespective of gearing). 
        ASSEMBLY ANGLE : The current rotation of the parent assembly.

        Example usage ---------------------------------------
        i2c = busio_I2C(board.GP5, board.GP4) # Define I2C channel.
        ASH = as5600_handler(name='mysensor',i2c=i2c) # Create instance.
        ASH.SetReferenceAngle(0.0) # Set reference angle (marks device as configured)
        while True:
            angle = ASH.Angle() # Update sensor readings.
            print("Assembly angle:",ASH.assembly_angle,"deg") # Show angle of assembly including gearing.
            time.sleep(0.5)
        """
        
    device_list = [] # global list of defined devices. 
    VERSION = '0.0.1'
    
    def __init__(self,name,i2c,gearing=4,invert=False,bits=12,parent=None,clock=None):
        """ Create an as5600 sensor instance. 
            Parameters -----------------------------------------------------------
            name : A name for the device. 
            i2c : The i2c service for communications.
            gearing : How many complete revolutions of the sensor represent 1 revolution of the assembly?
            invert : Reverse the direction of the position values.
            bits : Bit resolution of the sensor (ie 12 bit) 
            parent : Link to parent steppermotor instance. 
            clock : reference to Clock instance. """
        self.device_type = 'as5600'
        self.Clock = clock
        self.Name = name # A name for the device.
        self.Parent = parent # Link to the steppermotor instance that owns this sensor.
        from as5600 import AS5600
        self.Sensor = AS5600(i2c) # Create instance of AS5600 sensor.
        as5600_handler.device_list.append(self) # Add this to the list of globally defined devices. 
        # is the magnet detected?
        self.gearing = gearing
        self.orientation = 0 # Sensor returns values for single axis only.
        self.invert_value = invert # Do we invert the values from the sensor?
        self.resolution_bits = bits
        self.steps_per_rotation = 2 ** bits # What's the resolution of the sensor?
        self.assembly_steps_per_rotation = self.gearing * self.steps_per_rotation # How many 'steps' represent an entire rotation of the assembly?
        self.max_step = self.steps_per_rotation - 1 # What's the highest value the sensor can return?
        self.min_step = 0 # What's the lowest value the sensor can return?
        print(f"Magnet Detected: {self.Sensor.is_magnet_detected}")
        # Set the hysteresis to 3 LSB to reduce the chance of flickering when magnet is still - stabilises the reading.
        # The lower 3 bits are filtered out of readings, so precision reduces from 12bit to 9bit.
        self.hysteresis_bits = 3 # 3LSB hysteresis setting. (Store to avoid querying as5600 registers.)
        self.Sensor.hysteresis = AS5600.HYSTERESIS_3LSB # (binary '111') # Is this a mask?
        print("as5600_handler.__init__(",self.Name,")",self.resolution_bits,"bits, range",self.min_step,"to",self.max_step,"running...")
        self.assembly_accuracy = 360.0 / (self.steps_per_rotation * self.gearing) # What angle does each 'step' represent? (Ignore hysteresis effect)
        self.assembly_tolerance = (self.assembly_accuracy / 2) * (2 ** self.hysteresis_bits) # Tolerance of each reading (including effect of 3 bit hysteresis setting).
        self.absolute_position = 0 # Rotation position of the sensor in steps. This includes completed revolutions.
        self.Reset()

    def Reset(self):
        """ Call this to reset the configuration of the as5600 to its initial state. 
            Standard method for pilomar compatibility. """
        print("as5600_handler.Reset(",self.Name,") Reset.")
        self.sensor_position = None # Not yet measured.
        self.position_rotations = 0 # How any complete rotations to include in self.absolute_position?
        self.assembly_angle = None # What's the resulting position of the entire assembly?
        self.configured = False # The as5600 is not configured with reference_angle yet.
        self.reference_angle = 0 # Reference angle received from RPi, used to offset the as5600 angle to the true position.
        self.offset_angle = 0 # Offset to apply to as5600 angles to achieve the true physical angle of the assembly.
        self.last_reset = self.Parent.Clock.Now()
        self.last_measured = None # Clock when last measured.
        self.absolute_position = 0 # Rotation position of the sensor in steps. This includes completed revolutions.
        _ = self.Angle() # Initialise to 0 - 4095 values.
        
    def SetReferenceAngle(self,angle):
        """ Set the reference angle for the sensor.
            Standard method for pilomar compatibility. 
            Without a reference position we don't know what the assembly angle actually represents in the real world.
            By setting the reference angle we tell the sensor where it is currently pointing.
            Parameters ----------------------------------------------------------------
            angle : The reference angle received from the RPi at startup. This tells the true angle of the assembly.
            Outputs -------------------------------------------------------------------
            self.offset_angle : calculated offset to apply to as5600 angles in order to match the true position of the assembly.
            self.reference_angle : the angle received from the RPI. """
        if self.configured: # Warn if we're overriding a previous configuration.
            print("as5600_handler.SetReferenceAngle(",self.Name,") This replaces previous",self.reference_angle,"configuration.")
        # Define new reference and offset angles. 
        self.reference_angle = angle
        preoffset_assembly_angle = 360.0 * (self.absolute_position % self.assembly_steps_per_rotation) / self.assembly_steps_per_rotation # What angle is the assembly at BEFORE applying offset?
        self.offset_angle = self.reference_angle - preoffset_assembly_angle # calculate the offset to apply to as5600 calculated angles.
        self.assembly_angle = self.reference_angle # The assembly now knows it's pointing here!
        print("as5600_handler.SetReferenceAngle(",self.Name,") assembly_angle:",self.assembly_angle,", reference_angle:",self.reference_angle,", offset_angle:",self.offset_angle)
        self.configured = True # The as5600 is now considered configured.

    #def update(self):
    #    """ Retrieve the current position from the SENSOR and handle 'inversion' if needed.
    #        This represents the rotation position of the SENSOR not the parent assembly.
    #        Outputs -------------------------------------------------------------------------
    #        self.sensor_position : The current 'raw' orientation of the sensor in steps (ignores completed rotations and assembly gearing).
    #        self.absolute_position : Rotation position of the sensor in steps. This includes completed revolutions.
    #        self.assembly_angle : Rotation angle of the entire assembly, including allowing for gearing. """
    #    prev = self.sensor_position # Save previous position.
    #
    #    # Establish current sensor rotation step. (sensor only, no rotations or gearing.)
    #    temp = self.Sensor.angle # NOTE: This ISN'T an ANGLE, it's a value from 0 - 4095
    #    if self.invert_value: temp = self.max_step - temp # Invert the position result.
    #    self.sensor_position = temp # NOTE: This ISN'T an ANGLE, it's a value from 0 - 4095
    #
    #    # Establish the absolute position (including rotations).
    #    # Have we completed a revolution? (Passed the 360/0 barrier)
    #    if prev != None: # If we have a previous reading we can check for full rotations.
    #        change = self.sensor_position - prev # What's the position change?
    #        if abs(change) >= 200: # Large enough change to warrant attention.
    #            c_now = IntToTimeString(self.Parent.Clock.Now())
    #            print(c_now," as5600_handler.update(",self.Name,") Large SP change:",change,"from",prev,"to",self.sensor_position)
    #        if abs(change) > (self.steps_per_rotation / 2): # Large change means we've completed a revolution in one direction or the other.
    #            if change > 0: self.position_rotations -= 1 # We've moved to an earlier rotation. (eg from position 1 to position 4095)
    #            else: self.position_rotations += 1 # We've moved to a later rotation (eg from position 4095 to position 1)
    #    self.absolute_position = (self.steps_per_rotation * self.position_rotations) + self.sensor_position
    #
    #    # Establish the assemble position (including gearing).
    #    prev = self.assembly_angle
    #    preoffset_assembly_angle = 360 * (self.absolute_position % self.assembly_steps_per_rotation) / self.assembly_steps_per_rotation # What angle is the assembly at BEFORE applying offset?
    #    self.assembly_angle = (preoffset_assembly_angle + self.offset_angle) % 360 # Add offset to get real world assembly angle.
    #    if prev != None:
    #        change = self.assembly_angle - prev
    #        if abs(change) > 5: # Any change > 5 degrees is large enough to warrant attention.
    #            c_now = IntToTimeString(self.Parent.Clock.Now())
    #            print(c_now," as5600_handler.update(",self.Name,") Large AA change:",change,"from",prev,"to",self.assembly_angle,", conf",self.configured,
    #                  "SPR=",self.steps_per_rotation,
    #                  "APR=",self.assembly_steps_per_rotation,
    #                  "SG=",self.gearing,
    #                  "SP=",self.sensor_position,
    #                  "AP=",self.absolute_position,
    #                  "PR=",self.position_rotations,
    #                  "OA=",self.offset_angle,
    #                  "HS=",self.Sensor.hysteresis,
    #                  "AT=",round(self.assembly_tolerance,4))

    def Angle(self):
        """ Retrieve the current position from the SENSOR and handle 'inversion' if needed.
            This represents the rotation position of the SENSOR ASSEMBLY.
            Standard method for pilomar compatibility. 
            Returns -------------------------------------------------------------------------
            Angle : Float
            Outputs -------------------------------------------------------------------------
            self.sensor_position : The current 'raw' orientation of the sensor in steps (ignores completed rotations and assembly gearing).
            self.absolute_position : Rotation position of the sensor in steps. This includes completed revolutions.
            self.assembly_angle : Rotation angle of the entire assembly, including allowing for gearing. """
        prev = self.sensor_position # Save previous position.

        # Establish current sensor rotation step. (sensor only, no rotations or gearing.)
        temp = self.Sensor.angle # NOTE: This ISN'T an ANGLE, it's a value from 0 - 4095
        if self.invert_value: temp = self.max_step - temp # Invert the position result.
        self.sensor_position = temp # NOTE: This ISN'T an ANGLE, it's a value from 0 - 4095

        # Establish the absolute position (including rotations).
        # Have we completed a revolution? (Passed the 360/0 barrier)
        if prev != None: # If we have a previous reading we can check for full rotations.
            change = self.sensor_position - prev # What's the position change?
            if abs(change) >= 200: # Large enough change to warrant attention.
                c_now = IntToTimeString(self.Parent.Clock.Now())
                print(c_now," as5600_handler.Angle(",self.Name,") Large SP change:",change,"from",prev,"to",self.sensor_position)
            if abs(change) > (self.steps_per_rotation / 2): # Large change means we've completed a revolution in one direction or the other.
                if change > 0: self.position_rotations -= 1 # We've moved to an earlier rotation. (eg from position 1 to position 4095)
                else: self.position_rotations += 1 # We've moved to a later rotation (eg from position 4095 to position 1)
        self.absolute_position = (self.steps_per_rotation * self.position_rotations) + self.sensor_position

        # Establish the assembly position (including gearing).
        preoffset_assembly_angle = 360 * (self.absolute_position % self.assembly_steps_per_rotation) / self.assembly_steps_per_rotation # What angle is the assembly at BEFORE applying offset?
        self.assembly_angle = (preoffset_assembly_angle + self.offset_angle) % 360 # Add offset to get real world assembly angle.
        return self.assembly_angle

    def GetStatusLine(self):
        """ Return a status line to be reported back to RPi.
            Standard method for pilomar compatibility. """
        line = "# as5600 status " + self.Name + " "
        line += IntToTimeString(self.Parent.Clock.Now()) + " "
        line += "AA " + str(self.assembly_angle) + " " 
        line += "CO " + str(self.configured) + " "
        line += "SPR " + str(self.steps_per_rotation) + " "
        line += "APR " + str(self.assembly_steps_per_rotation) + " "
        line += "SG " + str(self.gearing) + " "
        line += "SP " + str(self.sensor_position) + " "
        line += "AP " + str(self.absolute_position) + " "
        line += "PR " + str(self.position_rotations) + " "
        line += "OA " + str(self.offset_angle) + " "
        line += "HS " + str(self.Sensor.hysteresis) + " "
        line += "AT " + str(round(self.assembly_tolerance,4)) + " "
        return line

    def MonitorAngle(self):
        """ Standard method for pilomar compatibility. 
            Continuous loop to report angle measurement.
            You need to break out of this once started. """
        prev_angle = None
        while True:
            angle = self.Angle()
            if angle != prev_angle:
                prev_angle = angle
                print(IntToTimeString(self.Parent.Clock.Now()),angle)
                time.sleep(0.5)

# ---------------------------------------------------------------------------------------------
                