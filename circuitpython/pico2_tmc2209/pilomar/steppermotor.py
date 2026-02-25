# pilomar/steppermotor.py - Circuitpython 9.2 build for Raspberry Pi Pico 2 (RP2350).
# For use with Raspberry Pi Pico 2 only.
# Dec.2024 / Refactored with help from TPROFFEN.
# May.2025 / Now exclusively Pico2 code version.

#-----------------------------------------------------------------------------------------------

steppermotor_version = "0.0.1" # A version number for this source code.

#-----------------------------------------------------------------------------------------------

from pilomar.helpers import * # Utility classes and methods used in this program. (logfile, clock, gpio etc)
print('pilomar.helpers:',helpers_version) # Print source code version number.
from pilomar.trajectory import * # Trajectory handling classes and methods used in this program. (trajectorypoint and trajectory)
print('pilomar.trajectory:',trajectory_version) # Print source code version number.
import tmc2209
import time 

class steppermotor():
    
    motor_list = [] # List of globally defined motors. 
    
    """ Handler for a NEMA17 stepper motor with TMC2209 driver chip. """
    def __init__(self,name,logfile,clock,exceptioncounter,features,TMCuart,motor_id,rpi,vmot,statusled):
        """ Create new instance of steppermotor class. 
            The motor still needs to be configured once created.
            
            Parameters ---------------------------------------------------------------------
            name : A name for the motor. Eg 'altitude'. 
            logfile : Handle to LogFile instance for logging messages. 
            clock : Handle to Clock instance for time functionality. 
            exceptioncounter : Handle to ExceptionCounter instance for error notification. 
            features : List of system features. 
            TMCuart : Handle to TMC2209 UART handler for this motor. 
            motor_id : Integer number. Unique ID number for this motor, must match ID wiring of the TMC2209 chip.
            rpi : Handle to UART comms for RPi.
            statusled : Handle to statusled instance. """
        self.MotorName = name
        self.LogFile = logfile # Instance of LogFile class.
        self.Log = logfile.Log # Instance of Log method of LogFile class.
        self.RPi = rpi # Instance of uarthost class.
        self.VMot = vmot # Link to VMot() function to check motor supply.
        self.Clock = clock # Instance of clock class.
        self.ExceptionCounter = exceptioncounter # Instance of ExceptionCounter class.
        self.StatusLed = statusled # Instance of statusled class.
        self.Features = features
        self.MotorID = motor_id
        # Define attributes here which will NOT be 'reset'.
        #self.as5600 = None # Instance of as5600_handler class. Link to any as5600 sensor handler connected to this axis.
        self.tmc2209 = None # Link to tmc2209 handler instance. Initialised below...
        self.position_sensor = None # Instance of a position sensor. API must have standard signature.
        #self.lis3dh = None # Instance of lis3dh_handler class. Link to LIS3DH accelerometer instance.
        # Set up control pins for the motor.
        # If we're using the same pins to drive multiple motors you may get some warnings from GPIO.
        # If the program has been restarted in the same session, you may get some warnings from GPIO.
        self.StepBCM = None # OUTPUT: This sends the MOVE pulse to the controller.
        self.DirectionBCM = None # OUTPUT: This sets the MOVE direction to the controller.
        self.EnableBCM = None # OUTPUT: This enables/disabled the motor.
        self.FaultBCM = None # INPUT: Will EARTH when triggered.
        self.PulseEndNs = 0 # time.monotonic_ns() value when a step pulse should end.
        self.PulseStartNs = 0 # time.monotonic_ns() value when self.PulseEndNs was set (used to detect clock resets)
        # Define attributes that WILL be 'reset' here.
        print("steppermotor.__init__(",motor_id,"): Call Initialize()")
        self.Initialize() # Initialize all the values.
        print("steppermotor.__init__(",motor_id,"): Call CreateTmc2209()")
        self.CreateTmc2209(TMCuart,motor_id) # Create associated TMC2209 handler for this motor.
        steppermotor.motor_list.append(self) # Add this motor to the list of recognised motors.
        
    def CreateTmc2209(self,TMCuart,motor_id):
        """ Create a TMC2209 handler for the motor. """
        #print("steppermotor.CreateTmc2209(",motor_id,"): Stage 1: Define TMCStepper.")
        com_pause = tmc2209.TMCStepper.RecommendComPause(TMCuart.baudrate) # Select a communication pause to match the UART baudrate.
        if com_pause == None: com_pause = 0.008 # Not recognised. 
        print("steppermotor.CreateTmc2209(",motor_id,"): Baud rate",TMCuart.baudrate,"= communication pause",com_pause,"s")
        self.tmc2209 = tmc2209.TMCStepper(uart = TMCuart,
                                          LogFile = self.LogFile,
                                          ExceptionCounter = self.ExceptionCounter,
                                          mtr_id = motor_id,
                                          communication_pause = com_pause,
                                          peak_current=self.RatedCurrent)
        #print("steppermotor.CreateTmc2209(",motor_id,"): Stage 2: Set full steps.")
        self.tmc2209.set_fullsteps_per_rev(self.FullMotorStepsPerRev) # It's a 200 step 1.8Deg motor.                                 
        #print("steppermotor.CreateTmc2209(",motor_id,"): Stage 3: Set microstepping.")
        self.tmc2209.set_microstepping_resolution(self.FineMicrosteps) # 2 microsteps.
        #print("steppermotor.CreateTmc2209(",motor_id,"): Stage 4: Set current.")
        self.tmc2209.set_current(operating_ratio = self.MoveCurrentPercent, # Run at 75% of motor's peak current.
                                 hold_current_multiplier = self.HoldCurrentPercent, # HOLD current is HALF run current.
                                 hold_current_delay = self.HoldDelay, # Wait 10 cycles before switching from RUN to HOLD current.
                                 pdn_disable = True) # Keep UART communication open.
        #print("steppermotor.CreateTmc2209(",motor_id,"): End")

    def Initialize(self):
        """ Initialize all the attributes of the motor. 
            These can be 'reset' to this state too.
            Called by the __init__() method and elsewhere. """
        self.TraceMove = True # Set to TRUE to write additional log messages tracking the state of the motor during GOTO movements.
        self.DriverType = 'tmc2209' # 'drv8825'
        self.Trajectory = trajectory(self.MotorName,logfile=self.LogFile,clock=self.Clock)
        self.MotorEnabled = False
        self.CurrentPosition = None
        self.TargetPosition = None
        self.MotorConfigured = False
        self.PendingSteps = 0 # How many steps is the motor expected to take in the current movement?
        self.FaultSensitive = False # Set to TRUE to monitor the 'fault' pin on the TMC2209 chip.
        self.FaultDetected = False # Latch to indicate we've already reported a fault with the TMC2209. Otherwise we overflow the UART comms buffer with warnings.
        self.SendStatus = True # Set to FALSE to disable status messages while downloading batches of data (eg Trajectories)
        self.StatusTimer = timer(self.MotorName,10) # Set up an internal timer for sending status messages every 10 seconds. Can we overridden by RPi.
        self.FastTime = 0.001 # The fastest pulse time for moving the motor.
        self.SlowTime = 0.05 # The slowest pulse time for moving the motor.
        self.DeltaTime = 0.003 # The acceleration amount moving from SlowTime to FastTime as the motor gets going.
        self.WaitTime = self.SlowTime # The time between pulses, starts slow, reduces as a move progresses. Resets every time a new target is set.
        self.Orientation = 1 # 1=Fwd, -1=Bkwd. This sets the overall orientation of motion. Compensate for gearing reversing the direction of motion here! It's applied to the DirectionBCM pin when the move is made.
        self.StepDir = 1 # The direction of a particular move +/-1. It always represents a SINGLE STEP.
        self.LastStepDir = 0 # Record the 'last' direction that the motor moved in. Useful for handling gear backlash and handling rotation limits. Starts at ZERO (No direction)
        self.BacklashAngle = 0.0 # This is the angle the motor must move to overcome backlash in the gearing when changing direction.
        self.DriftSteps = 0 # This is the number of steps 'error' that DriftTracking has identified. It must be incorporated back into motor movements as smoothly as possible. Consider backlash etc.
        self.SlewMotor = False # Allow the motor to make faster full-step (but less precise) moves when slewing the telescope large angles.
        self.GearRatio = 240 # Eg 240 for gearing ratio of 240:1 for a typical pilomar assembly.
        self.FullMotorStepsPerRev = 400 # How many full steps per motor revolution? (200 = 1.8deg motor, 400 = 0.9deg motor)
        self.FineMovement = True # Motor is moving in FINE MICROSTEPS by default.
        self.FineMicrosteps = 4 # When making fine moves use 4 microsteps.
        self.CoarseMicrosteps = 1 # When making coarse moves use full steps.
        self.MotorStepsPerRev = self.FullMotorStepsPerRev * self.FineMicrosteps # Overall number of microsteps motor uses in one full rotation.
        self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio # Overall steps for one revolution of the entire assembly.
        self.CalculateSlewLimits() # Calculate new values for SlewStepMultiplier and SlewTolerance.
        self.RatedCurrent = 1.0 # Rated motor current from motor specifications.
        self.MoveCurrentPercent = 0.75 # Percentage of RatedCurrent to use for RUN(MOVE) of the motor.
        self.HoldCurrentPercent = 0.5 # Percentage of RatedCurrent to use for HOLDING motor position.
        self.HoldDelay = 10 # 10 cycles delay before switching from RUN(MOVE) to HOLD current.
        self.MinAngle = None # Max anticlockwise movement.
        self.MaxAngle = None # Max clockwise movement.
        self.MinPosition = None # Min clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.MaxPosition = None # Max clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.RestAngle = None # The 'rest' position of the axis. Used for calibrating at startup. Typically DUE SOUTH or HORIZONTAL position of the axis.
        self.RestPosition = None
        # Limit position. This is not the position of a Limit switch, it is a rotation limit to prevent excessive cable twisting.
        self.LimitPosition = None # If given, this is the limit of movement. The telescope will reverse around this rather than cross it.
        self.RequestedPosition = None
        # The following items just need allocating, the self.Reset() call will set the values.
        self.OnTarget = False # Indicates that the motor is on target. This will control Observable status.
        self.LatestTuneSteps = 0 # Record details of the last tune command received. So we can see it was handled.
        self.LatestTuneTime = None
        # Latest Start/Stop times for config and status methods.
        self.OptimiseMoves = False # When set to TRUE the motor is allowed to take a short-cut if a requested move is > 50% of the circumference.
        self.LimitSwitches = [] # List of any limit switches assigned to this motor. Contains handles to LimitSwitch instances.
        self.MotorHalt = False # Latch to prevent motors moving at software level. Once triggered it doesn't reset without a cold start.

    def SelectCoarseMovement(self):
        """ Switch TMC2209 to COARSE movements.
            Takes about 0.12000 seconds if a change is made.
            Takes about 0.00004 seconds if no change is made. """
        #start_ns = time.monotonic_ns()
        if self.FineMovement: # Need to switch.
            self.tmc2209.set_microstepping_resolution(self.CoarseMicrosteps)
            self.FineMovement = False
        #print("steppermotor.SelectCoarseMovement() done in",int(time.monotonic_ns() - start_ns),"ns")
        
    def SelectFineMovement(self):
        """ Switch TMC2209 to FINE movements.
            Takes about 0.12000 seconds if a change is made.
            Takes about 0.00004 seconds if no change is made. """
        #start_ns = time.monotonic_ns()
        if self.FineMovement == False: # Need to switch.
            self.tmc2209.set_microstepping_resolution(self.FineMicrosteps)
            self.FineMovement = True
        #print("steppermotor.SelectFineMovement() done in",int(time.monotonic_ns() - start_ns),"ns")

    def CheckOnTarget(self):
        """ Set the OnTarget indicator if it looks like we're on-target.
            This means the REQUESTED POSITION = ACTUAL POSITION.
            (Don't use ANGLE because there may be tiny differences) """
        if self.RequestedPosition == None: self.OnTarget = False
        elif self.RequestedPosition == self.CurrentPosition: self.OnTarget = True
        else: self.OnTarget = False

    def Reset(self):
        """ This resets the status of the motor.
            It does not physically move it, but it disables it, and sets the 'current position' to be the 'home position'.
            This is typically used for manually positioning a motor during initial setup, or for
            clearing the trajectory when selecting a new observation target.
            A fresh configuration will then be required from the RPi.
        """
        print("steppermotor.Reset(",self.MotorName,"): Start")
        self.Log(self.MotorName,".Reset.")
        print("steppermotor.Reset(",self.MotorName,"): Clear trajectory...")
        self.Trajectory.Clear() # Delete the trajectory completely. We'll be needing a new one.
        print("steppermotor.Reset(",self.MotorName,"): Disable motor...")
        self.DisableMotor() # Disable the motor.
        print("steppermotor.Reset(",self.MotorName,"): Initialize motor...")
        self.Initialize() # Reset all the attributes of the motor.
        if self.position_sensor != None: 
            print("steppermotor.Reset(",self.MotorName,"): Reset position sensor...")
            self.position_sensor.Reset() # Position sensor can be reset too.
        print("steppermotor.Reset(",self.MotorName,"): Clear FAULT status on tmc2209...")
        self.tmc2209.ClearDriverFault() # Reset/Initialize fault status in the tmc2209 driver.
        print("steppermotor.Reset(",self.MotorName,"): Send status...")
        self.SendMotorStatus(immediate=True,codes='rst')
        print("steppermotor.Reset(",self.MotorName,"): Done")
        return True

    def CurrentDegrees(self):
        """ Return CurrentPosition as an angle.
            Assembly position is stored as a number of steppermotor steps, 
            so we have to calculate the equivalent ANGLE. """
        if self.AxisStepsPerRev == None or self.CurrentPosition == None:
            cd = None # Cannot calculate until axis configuration is known.
        else:
            cd = 360.0 * (float(self.CurrentPosition) / self.AxisStepsPerRev)
        return cd
        
    def AddTrajectoryPoint(self,entry):
        """ Add a TRAJECTORY POINT instance to the trajectory list for this motor. """
        try:
            self.Trajectory.Add(entry)
        except Exception as e:
            self.Log('steppermotor(',self.MotorName,').AddTrajectoryPoint:',entry,': Failed. ',e)
            self.ExceptionCounter.Raise() # Increment exception count for the session.
        self.SendMotorStatus(immediate=True,codes='atp') # This triggers the next trajectory point faster than waiting for the regular status message will.

    def ClearTrajectory(self):
        """ Remove all trajectory points from the motor. """
        self.Trajectory.Clear() # Empty the entire trajectory.
        self.SendMotorStatus(immediate=True,codes='clt')

    def Stop(self):
        """ Immediately stop the motor. """
        self.ClearTrajectory()
        self.TargetPosition = self.CurrentPosition
        self.OnTarget = False
        self.RequestedPosition = None
        self.Log('steppermotor.Stop(',self.MotorName,')')

    def EnableMotor(self):
        """ This engages current to the motor. It will hold its position now. """
        if self.MotorConfigured:
            self.EnableBCM.SetValue(False) # (1) # Pull pin LOW to enable.
            self.MotorEnabled = True
        else:
            self.Log('steppermotor.EnableMotor: Motor is not configured. Will not enable.')

    def DisableMotor(self):
        """ This disengages current to the motor. It will not hold its position now. """
        self.EnableBCM.SetValue(True) # (0) # Pull pin HIGH to disable.
        self.MotorEnabled = False

    def ChangeSteps(self):
        """ Return proposed number of steps to move. """
        return self.TargetPosition - self.CurrentPosition

    def ExpectedPosition(self):
        """ What position should the motor be at according to the current trajectory. """
        position = self.Trajectory.ExpectedPosition()
        return position

    def GoToAngle(self,newangle):
        """ This performs a GOTO move of the motor. 
            This does not use any trajectory information, it simply performs a large move (= GOTO / SLEW) directly. """
        if self.MotorConfigured:
            print('GoToAngle(',self.MotorName,'): Motor reports it is configured')
            self.Log('steppermotor.GoToAngle(',self.MotorName,')',newangle)
            print('GoToAngle(',self.MotorName,'): Stop')
            print('GoToAngle(',self.MotorName,'): SlowTime',self.SlowTime,', FastTime',self.FastTime,', TimeDelta',self.TimeDelta)
            self.Stop() # Clear any pre-existing trajectory before moving.
            print('GoToAngle(',self.MotorName,'): SetTargetByAngle')
            self.SetTargetByPosition(self.AngleToStep(newangle)) # Calculate self.TargetPosition and self.StepDir
            print('GoToAngle(',self.MotorName,'): MoveMotorFast')
            self.MoveMotorFast(slew_motor=self.SlewMotor)
            print('GoToAngle(',self.MotorName,'): MoveMotorFast complete.')
            #if self.SlewMotor: # Can use FAST moves for rapid slew.
            #    print('GoToAngle(',self.MotorName,'): MoveMotorFast')
            #    self.MoveMotorFast()
            #    print('GoToAngle(',self.MotorName,'): MoveMotorFast complete.')
            #else: # Not allowed to use FAST moves for rapid slew. Use original code.
            #    print('GoToAngle(',self.MotorName,'): MoveMotor')
            #    self.MoveMotor()
            #    print('GoToAngle(',self.MotorName,'): MoveMotor complete.')
        else:
            print('GoToAngle(',self.MotorName,'): Motor NOT configured')
            self.Log('steppermotor.GoToAngle(',self.MotorName,') Rejected. Motor is not configured.')
            self.RPi.Write('goto rejected ' + self.MotorName + ' ' + str(newangle) + ' MotorNotConfigured')
        print('GoToAngle(',self.MotorName,'): SendMotorStatus (immediate) gte')
        self.SendMotorStatus(immediate=True,codes='gte') # Tell RPi latest condition of the motor.

    def SetTargetByPosition(self,newposition=0,Limit=True):
        """ Set a new target POSITION (and therefore angle) for the motor.
            This will not move the motor, it will just prepare the step count and direction etc.
            newposition = The target position for the motor.
            Limit = True: The position must remain within limits.
            Limit = False: The position is not restricted at all. (Used for tuning.) """
        # Limit new angle to movement range. (MaxAngle, MinAngle)
        newangle = self.StepToAngle(newposition)
        result = True # Set succeeded.
        self.RequestedPosition = newposition # What position was requested?
        self.EnableMotor() # Enable the motor.
        if Limit: # OK to apply movement limits.
            if newangle > self.MaxAngle:
                self.Log(self.MotorName,": SetNewTarget:",newangle,"exceeds MaxAngle. Limited to:",self.MaxAngle)
                newangle = self.MaxAngle
                newposition = self.AngleToStep(newangle)
                result = False # Set failed.
            if newangle < self.MinAngle:
                self.Log(self.MotorName,": SetNewTarget:",newangle,"exceeds MinAngle. Limited to:",self.MinAngle)
                newangle = self.MinAngle
                newposition = self.AngleToStep(newangle)
                result = False # Set failed.
        self.TargetPosition = newposition # Convert it into the nearest absolute STEP position.
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
        if self.ChangeSteps() > 0: self.StepDir = 1 # Which direction do we move in?
        else: self.StepDir = -1
        return result

    def TargetFromTrajectoryPosition(self):
        """ Establish the latest target angle from the current trajectory.
            Calculates the target position and sets up for the move. """
        result = False # Failed unless successful.
        targetposition = self.ExpectedPosition()
        if targetposition != None and self.Trajectory.Valid and self.MotorConfigured: # We can set the target based upon current trajectory.
            result = self.SetTargetByPosition(targetposition) # Set TargetPosition and StepDir
        else: # Target is just the current position. Config and Trajectory are invalid.
            self.Log('TargetFromTrajectoryPosition',self.MotorName,'not ready. tv,mc,ta=', self.Trajectory.Valid, self.MotorConfigured,targetposition)
        return result

    def set_sensor_tuning(self,line):
        """ Process a 'set sensor tuning' command. 
            If viable and allowed, enable or disable automatic position position tuning. """
        print("steppermotor(",self.MotorName,").set_sensor_tuning()")
        if self.position_sensor != None: # Position sensor is detected.
            # Check VMOTADC
            self.Log("steppermotor(",self.MotorName,").set_sensor_tuning(): No voltage detected.")
        else: # No position sensor detected.
            self.Log("steppermotor(",self.MotorName,").set_sensor_tuning(): No position sensor detected.")
        print("steppermotor.set_sensor_tuning(): NOT YET IMPLEMENTED!")

    def set_as5600_tuning(self,line):
        
        """ Process a 'set as5600 tuning' command. 
            If viable and allowed, enable or disable automatic as5600 position tuning.
            Deprecated.             """
        print("steppermotor(",self.MotorName,").set_as5600_tuning()")
        self.set_sensor_tuning(line) # Refer to standard processing.
        
    def set_lis3dh_tuning(self,line):
        """ Process a 'set lis3dh tuning' command. 
            If viable and allowed, enable or disable automatic lis3dh position tuning.
            Deprecated.             """
        print("steppermotor(",self.MotorName,").set_lis3dh_tuning()")
        self.set_sensor_tuning(line) # Refer to standard processing.
        
    def SetReferenceAngle(self,angle=None):
        """
        Set sensor reference angle (Sets to CurrentAngle if no angle given)
        """
        if self.position_sensor != None: # Maintain the condition of the position sensor.
            if angle == None: angle = self.StepToAngle(self.CurrentPosition)
            print("steppermotor(",self.MotorName,").SetReferenceAngle: Restore position sensor reference angle to angle",angle)
            self.position_sensor.SetReferenceAngle(angle) # Store the reference angle in the position sensor.
        
    def TunePosition(self,line):
        """ Tune the motor position. This shifts the motor, but retains the 'position' calculation unchanged.
            Use this to address positioning errors or drift adjustments.
            Receives line with format 

            tune 20210410154530 azimuth -234 1
              0        1           2      3  4

                0 : always 'tune'
                1 : timestamp
                2 : motorname
                3 : steps to move
                4 : tune command reference (for acknowledgements) """

        lineitems = line.split(' ')
        delta = int(lineitems[3]) # How many steps are we moving?
        if len(lineitems) > 4: idx = int(lineitems[4]) # Each tune command has a unique ID we should return in the acknowledgement.
        else: idx = 0
        if self.MotorConfigured:
            self.EnableMotor()
            tunestarttime = self.Clock.Now()
            old = self.CurrentPosition # Store the current position of the motor. We'll restore this when finished.
            new = self.CurrentPosition + delta # Calculate the new target position (fullsteps).
            self.SetTargetByPosition(new,Limit=False) # Set TargetPosition and StepDir. Primes it for the move, No error check on limits.
            self.Log("TunePosition(",self.MotorName,") Current:",self.CurrentPosition,", NewTarget: ",self.TargetPosition)
            #self.MoveMotor() # Perform the move.
            self.MoveMotorFast(slew_motor=False) # Don't perform fast 'slew' moves in this case.
            # Restore the 'position'
            self.CurrentPosition = old
            self.TargetPosition = old
            self.Log("TunePosition(",self.MotorName,") set to",self.CurrentPosition)
            self.LatestTuneSteps = delta # Record details of the last tune command received. So we can see it was handled.
            self.LatestTuneTime = self.Clock.Now()
            #if hasattr(self.position_sensor,"SetReferenceAngle"): # Maintain the condition of the position sensor.
            self.SetReferenceAngle() # Reset the position sensor's angle to the 'CurrentAngle'.
            #if self.position_sensor != None: # Maintain the condition of the position sensor.
            #    ra = self.StepToAngle(self.CurrentPosition)
            #    print("steppermotor(",self.MotorName,").TunePosition: Restore position sensor reference angle to pos",self.CurrentPosition,", angle",ra)
            #    self.position_sensor.SetReferenceAngle(ra) # Restore the reference angle to the position sensor.
            self.RPi.Write('tune complete ' + self.MotorName + ' ' + IntToTimeString(self.LatestTuneTime) + ' ' + str(delta) + ' ' + IntToTimeString(tunestarttime) + ' ' + str(idx))
            self.SendMotorStatus(immediate=True,codes='tup') # Tell RPi latest condition of the motor.
        else:
            self.RPi.Write('tune rejected ' + self.MotorName + ' ' + IntToTimeString(self.LatestTuneTime) + ' ' + str(delta) + ' ' + str(idx) + ': Motor not configured')
            self.Log("error : TunePosition(",self.MotorName,") Rejected, motor is not yet configured.")

    def SetPins(self,stepBCM,directionBCM,enableBCM,faultBCM):
        """ Allocate pin numbers for the various GPIO pins required. """
        self.StepBCM = stepBCM # Pin(stepBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This sends the MOVE pulse to the controller.
        self.StepBCM.SetValue(False) # (0) # Turn pin off.
        self.Log(self.MotorName, 'Step pin', self.StepBCM.PinNumber)
        self.DirectionBCM = directionBCM # Pin(directionBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This sets the MOVE direction to the controller.
        self.DirectionBCM.SetValue(False) # (0)  # Turn pin off.
        self.Log(self.MotorName, 'Direction pin', self.DirectionBCM.PinNumber)
        self.EnableBCM = enableBCM # Pin(enableBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This enables/disabled the motor.
        self.EnableBCM.SetValue(False) # (0)  # Turn pin off.
        self.FaultBCM = faultBCM # Pin(faultBCM, Pin.IN) # Set pin to INPUT. Will EARTH when triggered.

    def SetConfig(self,gearratio,motorstepsperrev,minangle,maxangle,restangle,currentangle,orientation,backlashangle):
        """ Update the motor configuration based upon the configuration values received. 
            Current position is calculated based upon the currentangle value received. 
            - This is because the RPi knows the 'angle' when the system last ran, 
              but the matching step position may not be the same if the motor configuration has changed since.
              So it is recalculated from the angle to ensure the previous and current positions represent the same physical angle. """
        self.GearRatio = gearratio
        self.MotorStepsPerRev = motorstepsperrev
        self.MinAngle = minangle
        self.MaxAngle = maxangle
        self.RestAngle = restangle
        self.Orientation = orientation
        self.BacklashAngle = backlashangle
        # Reapply dependent calculations.
        # Microstepratio and UseMicrostepping now obsolete parameters.
        self.WaitTime = self.SlowTime # The time between pulses, starts slow, reduces as a move progresses. Resets every time a new target is set.
        self.StepDir = 1 # The direction of a particular move +/-1. It always represents a SINGLE FULL STEP.
        self.LastStepDir = 0 # Record the 'last' direction that the motor moved in. This may be useful for handling gear backlash. Starts at ZERO (No direction)
        self.DriftSteps = 0 # This is the number of steps 'error' that DriftTracking has identified. It must be incorporated back into motor movements as smoothly as possible. Consider backlash etc.
        self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio
        # AngleToStep and StepToAngle only work from here on!
        self.RestPosition = self.AngleToStep(self.RestAngle)
        self.CurrentPosition = self.TargetPosition = self.AngleToStep(currentangle)
        self.MinPosition = self.AngleToStep(self.MinAngle) # Min clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.MaxPosition = self.AngleToStep(self.MaxAngle) # Max clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.RequestedPosition = self.CurrentPosition
        return self.MotorConfigured

    def CalculateSlewLimits(self):
        """ Calculate dependencies based upon SLEW ratio between FINE and COARSE stepping. """        
        self.SlewStepMultiplier = self.FineMicrosteps / self.CoarseMicrosteps # Number of steps taken with a larget SLEW move (if microstepping in place).
        self.SlewTolerance = 100 * self.SlewStepMultiplier # This is as close as we want to get with large slew moves.
        
    def DemoConfigureTmc2209(self):
        """ Call this to create a demonstration configuration of the TMC2209 for dev/testing purposes.
            configure tmc2209 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n  n 90.0 240 400 4 1 1.0 0.75 0.5 10 180 y y
                0       1          2           3       4     5  6   7  8   9     10    11  12 13 14 15   16  17 18 19 20  21  22 23 24 25 26
        """
        line = 'configure tmc2209 '
        line += IntToTimeString(Clock.Now()) + ' ' # 2 = UTC timestamp when message sent.
        line += self.MotorName + ' ' # 3 = Motor name.
        line += '180 ' # 4 = Last reported (Current) angle.
        line += '0 ' # 5 = Minimum allowed angle.
        line += '360 ' # 6 = Maximum allowed angle.
        line += '0.0 ' # 7 = Backlash angle.
        line += '-1 ' # 8 = Motor orientation.
        line += '0.001 ' # 9 = FastTime.
        line += '0.05 ' # 10 = SlowTime.
        line += '0.003 ' # 11 = TimeDelta.
        line += '10 ' # 12 = Delay between automatic status messages.
        line += 'n ' # 13 = FaultSensitive (stop if fault signal from driver).
        line += 'n ' # 14 = OptimiseMoves (allows unlimited full rotation).
        line += 'none ' # 15 = LimitAngle (motor will not cross this angle) - under development.
        line += '240 ' # 16 = Gear ratio. (DRIVETRAIN ratio, NOT MICROSTEPPING!)
        line += '200 ' # 17 = Full Motor steps per revolution (1 revolution of motor) the defined FULL STEP count for one revolution of the motor.
        line += '4 ' # 18 = Fine microstepping value for turning the motor during observations (1 - 256)
        line += '1 ' # 19 = Coarse microstepping value for turning the motor during rapid SLEW moves (1 - 256)
        line += '1.0 ' # 20 = Motor rated current. As per motor specification sheet (Amps)
        line += '0.75 ' # 21 = Move current percent. % of motor's max specified current to use for moving.
        line += '0.5 ' # 22 = Hold current percent. % of motor's max specified current to use for holding position.
        line += '10 ' # 23 = Hold delay. x10 clock cycles to wait before switching from MOVE to HOLD current.
        line += '180 ' # 24 = Motor rest angle (when homed).
        line += 'y ' # 25 = SlewMotor flag (Can motor switch between FINE and COARSE moves during large position changes).
        line += 'y ' # 26 = TraceMove : Enhanced log messages sent back by the motor.
        self.ConfigureTmc2209(line)

    def ConfigureTmc2209(self,line):
        """ This loads the motor configuration received from the RPi for a TMC2209 driver.
            It can override some default values in the configuration.
            All values are optional.
            Any value of 'none' is ignored.

            configure tmc2209 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n  n 90.0 240 400 4 1 1.0 0.75 0.5 10 180 y y
                0       1          2           3       4    5  6   7  8   9     10    11  12 13 14 15   16  17 18 19 20  21  22  23 24 25 26
                
                 2 = UTC timestamp when message sent.
                 3 = Motor name.
                 4 = Last reported (Current) angle.
                 5 = Minimum allowed angle.
                 6 = Maximum allowed angle.
                 7 = Backlash angle.
                 8 = Motor orientation.
                 9 = FastTime.
                10 = SlowTime.
                11 = TimeDelta.
                12 = Delay between automatic status messages.
                13 = FaultSensitive (stop if fault signal from driver).
                14 = OptimiseMoves (allows unlimited full rotation).
                15 = LimitAngle (motor will not cross this angle) - under development.
                16 = Gear ratio. (DRIVETRAIN ratio, NOT MICROSTEPPING!)
                17 = Full Motor steps per revolution (1 revolution of motor) the defined FULL STEP count for one revolution of the motor.
                18 = Fine microstepping value for turning the motor during observations (1 - 256)
                19 = Coarse microstepping value for turning the motor during rapid SLEW moves (1 - 256)
                20 = Motor rated current. As per motor specification sheet (Amps)
                21 = Move current percent. % of motor's max specified current to use for moving.
                22 = Hold current percent. % of motor's max specified current to use for holding position.
                23 = Hold delay. x10 clock cycles to wait before switching from MOVE to HOLD current.
                24 = Motor rest angle (when homed).
                25 = SlewMotor flag (Can motor switch between FINE and COARSE moves during large position changes).
                26 = TraceMove : Enhanced log messages sent back by the motor.
            """
        if self.DriverType != "tmc2209": # Received configuration for wrong type of driver.
            print("ConfigureTmc2209(",self.MotorName,") received tmc2209 configuration, expected",self.DriverType)
            self.Log("ConfigureTmc2209(",self.MotorName,") received tmc2209 configuration, expected",self.DriverType)
            return False
            
        try:
            lineitems = line.lower().split(' ')
            lc = len(lineitems)
            self.Clock.UpdateClockFromString(lineitems[2]) # Check that the clock is as synchronised as possible.
            self.BacklashAngle = float(lineitems[7]) # Set new backlash angle for motor.
            self.Orientation = int(lineitems[8]) # Set new orientation for motor.
            self.FastTime = float(lineitems[9]) # Set new FASTEST PULSE time for motor.
            self.SlowTime = float(lineitems[10]) # Set new SLOWEST PULSE time for motor.
            self.TimeDelta = float(lineitems[11]) # Set new acceleration rate for motor.
            if self.WaitTime < self.FastTime: self.WaitTime = self.FastTime # Current motor speed cannot be faster than new fastest limit.
            if self.WaitTime > self.SlowTime: self.WaitTime = self.SlowTime # Current motor speed cannot be slower than new slowest limit.
            temp = int(lineitems[12])
            if temp < 1: temp = 1
            elif temp > 30: temp = 30
            self.StatusTimer = timer(self.MotorName,temp) # Set new repeat time for sending motor status messages back to the RPi
            self.FaultSensitive = StringToBool(lineitems[13]) # Enable/disable fault sensitivity. TMC2209 can then abort an observation.
            self.OptimiseMoves = StringToBool(lineitems[14]) # Enable/disable move optimisation.
            self.GearRatio = float(lineitems[16]) # Eg 240 for gearing ratio of 240:1 for a typical pilomar assembly.
            self.FullMotorStepsPerRev = int(lineitems[17]) # Number of full steps the motor takes per revolution (without microstepping) as per specification sheet.
            self.FineMicrosteps = int(lineitems[18]) # Microstepping ratio for fine movements during observations.
            self.CoarseMicrosteps = int(lineitems[19]) # Microstepping ratio for coarse movements during large GOTO / SLEW moves.
            self.MotorStepsPerRev = self.FullMotorStepsPerRev * self.FineMicrosteps
            self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio
            self.CalculateSlewLimits() # Calculate new values for SlewStepMultiplier and SlewTolerance.
            self.RatedCurrent = float(lineitems[20]) # Maximum coil current as per motor specification sheet.
            self.MoveCurrentPercent = float(lineitems[21]) # % of maximum current to use for MOVES.
            self.HoldCurrentPercent = float(lineitems[22]) # % of maximum current to use for HOLDING.
            self.HoldDelay = int(lineitems[23]) # Clock cycles to wait before switching from MOVE to HOLD current.
            self.RestAngle = float(lineitems[24]) # Define rest angle, the motor returns here when homed.
            self.SlewMotor = StringToBool(lineitems[25]) # Are SLEW fast moves allowed?
            self.TraceMove = StringToBool(lineitems[26]) # Is 'TraceMove' enabled? (Enhanced development log messages from the motors)
            
            # Restore min/max/current/limit position only after the MotorStepsPerRev is known, if microstepping has changed above these will be different.
            ca = float(lineitems[4])
            self.CurrentPosition = self.AngleToStep(ca)
            #if hasattr(self.position_sensor,"SetReferenceAngle"): # position sensor available, configure that too.
            if self.position_sensor != None: # position sensor available, configure that too.
                print("ConfigureTmc2209(",self.MotorName,") setting position sensor reference angle",ca)
                self.Log("ConfigureTmc2209(",self.MotorName,") setting position sensor reference angle",ca)
                self.position_sensor.SetReferenceAngle(ca)
            self.MinAngle = float(lineitems[5]) # Set new minimum angle for motor.
            self.MinPosition = self.AngleToStep(self.MinAngle)
            self.MaxAngle = float(lineitems[6]) # Set new maximum angle for motor.
            self.MaxPosition = self.AngleToStep(self.MaxAngle)
            # Define movement limit on the motor. The motor will reverse around a limit rather than crossing it.
            if lineitems[15] != 'none':
                limitangle = float(lineitems[15])
                self.LimitPosition = self.AngleToStep(limitangle) # Set a movement limit.
            else:
                self.LimitPosition = None
            self.MotorConfigured = True
        except Exception as e:
            self.Log("steppermotor.ConfigureTmc2209(",line,") failed:",e)
            print("steppermotor(",self.MotorName,").ConfigureTmc2209() failed.")
            self.ExceptionCounter.Raise() # Increment exception count for the session.
        self.ReportMotorConfig() # Report the configuration back to the RPi.
        return self.MotorConfigured

    def ConfigureDrv8825(self,line):
        """ This loads the motor configuration received from the RPi for a DRV8825 driver.
            It can override some default values in the configuration.
            All values are optional.
            Any value of 'none' is ignored.

            ************************************************************            
            THIS CODE DOES NOT SUPPORT DRV8825 SO AN ERROR HAS OCCURRED.
            ************************************************************            

            configure motor 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n  n 90.0 240 400  1 180.0 nnn n nnn n
                0       1         2           3       4    5  6   7  8   9     10    11  12 13 14 15   16 17  18 19    20  21 22 23
                
                 2 = UTC timestamp when message sent.
                 3 = Motor name.
                 4 = Last reported (Current) angle.
                 5 = Minimum allowed angle.
                 6 = Maximum allowed angle.
                 7 = Backlash angle.
                 8 = Motor orientation.
                 9 = FastTime.
                10 = SlowTime.
                11 = TimeDelta.
                12 = Delay between automatic status messages.
                13 = FaultSensitive (stop if fault signal from driver).
                14 = OptimiseMoves (allows unlimited full rotation).
                15 = LimitAngle (motor will not cross this angle) - under development.
                16 = Gear ratio. (DRIVETRAIN ratio, NOT MICROSTEPPING!)
                17 = Motor steps per revolution (1 revolution of motor).
                18 = SlewStepMultiplier (number of steps taken with a SLEW move).
                19 = Motor rest angle (when homed).
                20 = Microstepping mode signals (used when making observation).
                21 = SlewMotor flag (Can motor make FULL STEP moves during large position changes).
                22 = Slew stepping mode signals (used when making large position changes).
                23 = TraceMove : Enhanced log messages sent back by the motor.
            """
        if self.DriverType != "drv8825": # Received configuration for wrong type of driver.
            print("ConfigureDrv8825(",self.MotorName,") received drv8825 configuration, expected",self.DriverType)
            self.Log("ConfigureDrv8825(",self.MotorName,") received drv8825 configuration, expected",self.DriverType)
        return False
        
    #def StepMove_xxx(self,stepsize=1):
    #    """ Move the motor one full step. Target must be initialized before calling this.
    #        
    #        Parameters ----------------------------------------------------------------------------
    #        stepsize : The size of the step being taken. 
    #        
    #        Uses ----------------------------------------------------------------------------------
    #        self.MotorEnabled
    #        self.WaitTime 
    #        self.CurrentPosition 
    #        self.StepDir 
    #        self.AxisStepsPerRev 
    #        self.DeltaTime 
    #        self.FastTime 
    #        
    #        Outputs -------------------------------------------------------------------------------
    #        interrupt : True if a limitswitch interrupt has occurred. Indicates to calling routine that movement needs reassessing. 
    #        
    #        Modifies ------------------------------------------------------------------------------ 
    #        self.WaitTime : Pulse duration of each step (changes due to acceleration)
    #        self.StepBCM (GPIO pin) : Triggers actual step by the motor driver.
    #        self.CurrentPosition : Updates to the new position of the motor after the step is made. """
    #    self.StatusLed.Task('move') # Flash status LED with motor specific colour.
    #    interrupt = False # No interrupt has occurred yet.
    #    if self.MotorEnabled: # If we've disabled the motor, then perform everything except the move pulse.
    #        self.StepBCM.SetValue(True) # value(1)
    #        ns_sleep(delay=self.WaitTime)
    #        self.StepBCM.SetValue(False) # value(0)
    #        ns_sleep(delay=self.WaitTime) # *Q* This may be too long if limitswitch checking takes time. 
    #    self.CurrentPosition = int((self.CurrentPosition + (self.StepDir * stepsize)) % self.AxisStepsPerRev)
    #    # Accelerate the motor.
    #    if self.WaitTime > self.FastTime: # We can still accelerate
    #        self.WaitTime = max(self.WaitTime - self.DeltaTime, self.FastTime)
    #    return interrupt

    def StepMove(self,stepsize=1):
        """ Move the motor one full step. Target must be initialized before calling this.
            The routine pauses while the "ON" part of the step pulse executes, but does not wait for the "OFF" part of the pulse to complete.
            Instead control is returned to the calling routine, the 'OFF' pulse is only terminated when this method is next called.
            This allows the microcontroller to use the 'OFF' pulse duration to do more useful things, wasting less time, this gives a 12% performance
            boost with standard settings.
            
            Parameters ----------------------------------------------------------------------------
            stepsize : The size of the step being taken. 
            
            Uses ----------------------------------------------------------------------------------
            self.MotorEnabled
            self.WaitTime 
            self.CurrentPosition 
            self.StepDir 
            self.AxisStepsPerRev 
            self.DeltaTime 
            self.FastTime 
            self.PulseStartNs
            self.PulseEndNs
            self.MotorHalt (To see if MSTOP was triggered to prevent movement)
            
            Outputs -------------------------------------------------------------------------------
            interrupt : True if a limitswitch interrupt has occurred. Indicates to calling routine that movement needs reassessing. 
            
            Modifies ------------------------------------------------------------------------------ 
            self.WaitTime : Pulse duration of each step (changes due to acceleration)
            self.StepBCM (GPIO pin) : Triggers actual step by the motor driver.
            self.CurrentPosition : Updates to the new position of the motor after the step is made. 
            self.PulseEndNs : monotonic_ns() value when the OFF cycle of the pulse should end. 
            self.PulseStartNs : monotonic_ns() value when self.PulseEndNs is set (to detect rollover/reset). """
        if self.MotorHalt: # MSTOP triggered, don't move.
            return False
        self.StatusLed.Task('move') # Flash status LED with motor specific colour.
        interrupt = False # No interrupt has occurred yet.

        # First see if the previous 'off' cycle of the step pulse is old enough to make start a new step.
        while True: # Loop until we hit the END time.
            now_ns = time.monotonic_ns() # Get the latest nanosecond timer value.
            if now_ns >= self.PulseEndNs: # Timer expired.
                break
            if now_ns < self.PulseStartNs: # Nanosecond timer has reset.
                print("StepMove_Fast(): Clock reset.")
                break
        
        # Check for limitswitch interrupts.
        
        # If safe, move.
        if self.MotorEnabled: # If we've disabled the motor so perform everything except the move pulse.
            self.StepBCM.SetValue(True) # value(1)
            ns_sleep(delay=self.WaitTime)
            self.StepBCM.SetValue(False) # value(0)
            # Don't wait for the 'OFF' cycle to complete, check it the next time we call this method.
            self.PulseStartNs = time.monotonic_ns() # When did this cycle start?
            self.PulseEndNs = int(self.WaitTime * 1e9) + self.PulseStartNs # When should the 'off' part of the pulse cycle end? It will be checked at the start of the next call.

        self.CurrentPosition = int((self.CurrentPosition + (self.StepDir * stepsize)) % self.AxisStepsPerRev)
        # Accelerate the motor.
        if self.WaitTime > self.FastTime: # We can still accelerate
            self.WaitTime = max(self.WaitTime - self.DeltaTime, self.FastTime)
            
        return interrupt

    def InvertSteps(self,motorsteps):
        """ Given a number of steps to move, return the inverse move.
            This converts a CLOCKWISE movement into an ANTICLOCKWISE movement and vice-versa. """
        if motorsteps > 0: # Instead of going forward, go backward.
            inversemove = motorsteps - self.AxisStepsPerRev
        else: # Instead of going backward, go forward.
            inversemove = motorsteps + self.AxisStepsPerRev
        return inversemove
    
    def EfficiencyCheck(self,motorsteps):
        """ Check motorsteps are efficient. 
            If the motor is taking the long route to the new position, revise it. """
        inversemove = motorsteps
        if abs(motorsteps) > int(self.AxisStepsPerRev / 2): # We're going the long way round.
            inversemove = self.InvertSteps(motorsteps)
            self.Log("steppermotor(",self.MotorName,").EfficiencyCheck(): Inefficient move:",self.CurrentPosition,"to",self.TargetPosition,",",motorsteps,"steps, suggest",inversemove)
            print(self.MotorName,"Inefficient move:",self.CurrentPosition,"to",self.TargetPosition,",",motorsteps,"steps, suggest",inversemove)
        return inversemove

    def LogMoveState(self,label):
        """ Record a log message with the state of the motor after a move.
            This shows the state of key motor movement attributes whenever it
            is called.
            
            Parameters -----------------------------------------------------------
            label : A label for the state of the motor when this is called.
                    eg: mvf0 = Start of MoveMotorFast() before any action.
                        mvf1 = Condition of motor in MoveMotorFast() when direction has been chosen.
                        mvf2 = Condition of motor in MoveMotorFast() after pre-move to FULL STEP point.
                        mvf3 = Condition of motor in MoveMotorFast() after FULL STEP slew move is completed.
                        mvf4 = End of MoveMotorFast() after final alignment move to microstep point.

            eg:
                   move state azimuth mvf3 23040 23040 -1 -1 -1 yyy 0.001
                     0    1      2     3     4     5    6  7  8  9  10
                       
                   2 = MotorName
                   3 = label (move phase)
                   4 = CurrentPosition
                   5 = TargetPosition
                   6 = Orientation
                   7 = Direction
                   8 = Previous direction
                   9 = Mode pin settings
                   10 = Pulse length """
        line = 'move state ' + self.MotorName + ' ' + label + ' '
        line += str(self.CurrentPosition) + ' ' + str(self.TargetPosition) + ' '
        line += str(self.Orientation) + ' ' + str(self.StepDir) + ' ' + str(self.LastStepDir) + ' '
        line += str(self.WaitTime)
        self.Log(line)        

    def CheckLimitSwitches(self):
        """ Check if any limit switches are triggered. 
            3 types of switch supported:
                minimum: Recognised when first pressed AND stepdir < 0 : Stops motion and sets current angle.
                maximum: Recognised when first pressed AND stepdir > 0 : Stops motion and sets current angle.
                calibration: Recognised when first pressed; stepdir is irrelevent : Motion continues, sets current angle.
            Outputs ----------------------------------------------------
            limsw_triggered (bool) : TRUE if limit switch has triggered forcing a re-assessment of movement by calling routine.
            
            Affects ----------------------------------------------------
            self.CurrentPosition : Set to limit-switch angle for all switches.
            self.TargetPosition : Set to limit-switch angle for MINIMUM and MAXIMUM switches.
            self.OnTarget : Set to False if CurrentPosition is modified. """
        something_triggered = False # Set to TRUE if a limit switch has triggered, this tells the calling routine to re-assess the situation. 
        for LimSw in self.LimitSwitches: # List of limitswitch instances.
            limsw_triggered = False # Indicates trigger to be actioned.
            if LimSw.Pin.Pressed(): # Switch has just triggered.
                if LimSw.Enabled: # The switch is active and has just triggered. 
                    print("CheckLimitSwitches(",LimSw.Name,") detected:",LimSw.Action,"dir:",self.StepDir,"angle:",LimSw.Angle)
                    self.Log("CheckLimitSwitches(",LimSw.Name,") detected:",LimSw.Action,self.StepDir,LimSw.Angle)
                    if LimSw.Action.startswith('mi'):
                        if self.StepDir < 0: 
                            print("CheckLimitSwitches: MINIMUM applies.",self.StepDir)
                            limsw_triggered = True
                        else: print("CheckLimitSwitches: MINIMUM does not apply in direction",self.StepDir)
                    elif LimSw.Action.startswith('ma'):
                        if self.StepDir > 0: 
                            print("CheckLimitSwitches: MAXIMUM applies.",self.StepDir)
                            limsw_triggered = True
                        else: print("CheckLimitSwitches: MAXIMUM does not apply in direction",self.StepDir)
                    elif LimSw.Action.startswith('c'): 
                        print("CheckLimitSwitches: CALIBRATION applies.",self.StepDir)
                        limsw_triggered = True
                    else: print("CheckLimitSwitches(",LimSw.Name,") Unrecognised action:",LimSw.Action,self.StepDir,": IGNORED")
                    if limsw_triggered: 
                        if False: #*Q* Disabled during development.
                            self.CurrentPosition = self.AngleToStep(limsw.Angle)
                            if limsw.Action.startswith('mi') or limsw.Action.startwith('ma'): self.TargetPosition = self.CurrentPosition # No further movement needed.
                            self.OnTarget = False # Let the system confirm whether we are on target.
                        else:
                            print('CheckLimitSwitches(',LimSw.Name,'): will update position here *****')
                        self.Log('CheckLimitSwitches: Set CurrentPosition and TargetPosition to',self.CurrentPosition)
                        something_triggered = True
                        # *Q* What about recalibrating connected rotation sensors? such as as5600 and lis3dh
                else:
                    print("CheckLimitSwitches(",LimSw.Name,") Triggered but disabled.")
        return something_triggered # Should calling routine reassess motion?

    def CalculatePendingSteps(self):
        """ Calculate the number of steps that the motor needs to take 
            to get from CurrentPosition to TargetPosition. 
            This will include some optimisation decisions if allowed. 
            Inputs --------------------------------------------------------
            Uses self.OptimiseMoves, self.TargetPosition, self.CurrentPosition, self.StepDir
            Outputs -------------------------------------------------------
            Number of steps to take. 
            Updates self.StepDir if reverse direction is chosen for efficiency.
            Updates self.OnTarget if a large move is chosen. """
        self.PendingSteps = self.TargetPosition - self.CurrentPosition # How many steps to take?
        if self.OptimiseMoves: # Allowed to find shorter paths!
            inversemove = self.EfficiencyCheck(self.PendingSteps) # Check if this is the most efficient move.
            if inversemove != self.PendingSteps: # We're changing direction for a short cut.
                self.PendingSteps = inversemove
                print("steppermotor.CalculateMotorSteps moving",self.PendingSteps,"steps after efficiency check.")
                self.StepDir *= -1 # *Q* Can/should this be initialised in this routine rather than being set externally? 
        else: # Must move as instructed, but can report if a shorter path exists.
            _ = self.EfficiencyCheck(self.PendingSteps) # Check if this is the most efficient move.
        if self.TraceMove: self.LogMoveState('mvf1') # For development purposes log the state of the motor at this point.
        if self.PendingSteps != 0:
            self.StatusLed.Task('move') # Flash status LED with motor specific colour. *Q* Do this in calling routine?
            if abs(self.PendingSteps) > 100: # Large moves will reset the 'OnTarget' flag.
                self.OnTarget = False

    def MoveMotorFast(self,slew_motor=True):
        """ Move the motor to the new target position.
            If the SlewMotor parameter is True, then this can use FULL STEPS to speed things up in the middle of large moves.
            This moves the telescope faster when using very fine microstepping.
            This moves to a 'full step' boundary on the motor, then switches to FULL STEP movements until close to the target.
            When close to the target it reverts to microstepping for fine tuning.
            Target must be defined before calling this.
            Large moves can take some time, so UART communication is maintained during moves.
            The motor will generally take the shortest path to the target position.
            It may take the longer route under some circumstances. (LimitPosition must not be crossed etc.) 
            
            Parameters ------------------------------------------------------------
            slew_motor : Boolean : TRUE allows large moves to use larger (COARSE) microsteps. 
                                   FALSE forces all moves to use the normal (FINE) microsteps.

            Inputs ----------------------------------------------------------------
            self.StepDir should be set prior to calling this. """
        if self.TraceMove: self.LogMoveState('mvf0') # For development purposes log the state of the motor at this point.
        self.CalculatePendingSteps() # How many steps to take, and which direction is most efficient?
        if self.FaultBCM.GetValue(): # TMC2209 DIAG (fault) goes high when there's a problem.
            if self.FaultSensitive: # The fault matters.
                if not self.FaultDetected:
                    print("Setting FAULT status (sensitive).")
                    self.FaultDetected = True
                    self.Log("steppermotor.MoveMotorFast(", self.MotorName, ') TMC2209 fault - terminating.')
                return
            else: # The fault does not matter.
                if not self.FaultDetected: # Only report once.
                    self.Log("steppermotor.MoveMotorFast(", self.MotorName, ') TMC2209 fault - ignored.')
                    print("Setting FAULT status (insensitive).")
                    self.FaultDetected = True
        else: # No TMC2209 fault, clear any previous fault status.
            if self.FaultDetected: 
                self.Log("steppermotor.MoveMotorFast(", self.MotorName, ') TMC2209 fault - cleared.')
                self.FaultDetected = False # No fault.
        if abs(self.StepDir) != 1: # self.StepDir must be +1 or -1
            self.Log('MoveMotorFast:',self.MotorName,'StepDir',self.StepDir,'is invalid. Must be +/-1')
            return
        if (self.StepDir * self.Orientation) > 0:
            self.DirectionBCM.SetValue(True) # value(1) # Move motor forward.
        else:
            self.DirectionBCM.SetValue(False) # value(0) # Move motor backwards.
        if self.StepDir != self.LastStepDir and self.LastStepDir != 0: # We have a change of direction.
            self.Log('MoveMotorFast:',self.MotorName,'changed direction (',self.StepDir,'vs',self.LastStepDir,'). Backlash?')
        self.LastStepDir = self.StepDir # Record the direction that the motor is moving in. This may be useful for handling gear backlash etc.
        if slew_motor: # We're allowed to make FAST moves using FULL STEPS if there's a long way to go.
            # --- Fine movement to full step boundary ---
            self.SelectFineMovement() # Select FINE stepping mode until we get to a 'coarse' microstep boundary.
            self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
            print("MoveMotorFast(",self.MotorName,"):SlewMotor:InitialMicrostepping:Reset WaitTime to",self.WaitTime,'at',int(time.monotonic_ns()),"ns")
            while self.PendingSteps != 0:
                if self.CurrentPosition % self.SlewStepMultiplier == 0: # On FULLSTEP boundary. Switch to FULL STEPS.
                    break
                interrupt = self.StepMove(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
                #self.PendingSteps = self.PendingSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
                self.PendingSteps -= self.StepDir # REDUCE (-ve) the number of steps to take.
                self.SendMotorStatus(codes='mvf') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
                for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                    self.RPi.BufferInput() # Keep polling for input from the RPi.
                    self.RPi.WritePoll() # Keep sending data to RPi.
            if self.TraceMove: self.LogMoveState('mvf2') # For development purposes log the state of the motor at this point.
            print("MoveMotorFast(",self.MotorName,"):SlewMotor:InitialMicrostepping:Final WaitTime",self.WaitTime,'at',int(time.monotonic_ns()),"ns")
            # --- Coarse movement using full steps toward target position ---
            self.SelectCoarseMovement() # Slew the telescope with larger coarse steps.
            self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
            print("MoveMotorFast(",self.MotorName,"):SlewMotor:Fullstepping:Reset WaitTime to",self.WaitTime,'at',int(time.monotonic_ns()),"ns")
            while self.PendingSteps != 0:
                if self.CheckLimitSwitches(): # A limit switch was triggered.
                    print("MoveMotorFast(",self.MotorName,"):SlewMotor:Fullstepping: LimitSwitch detected! ****")
                if abs(self.TargetPosition - self.CurrentPosition) <= self.SlewTolerance: # We've got close with FULLSTEPS, switch back to microsteps.
                    break
                interrupt = self.StepMove(stepsize=self.SlewStepMultiplier) # This will update CurrentPosition on-the-fly as the motor moves.
                #self.PendingSteps = (self.PendingSteps - (self.StepDir * self.SlewStepMultiplier)) # REDUCE (-ve) the number of steps to take.
                self.PendingSteps -= (self.StepDir * self.SlewStepMultiplier) # REDUCE (-ve) the number of steps to take.
                self.SendMotorStatus(codes='mvf') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
                for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                    self.RPi.BufferInput() # Keep polling for input from the RPi.
                    self.RPi.WritePoll() # Keep sending data to RPi.
            if self.TraceMove: self.LogMoveState('mvf3') # For development purposes log the state of the motor at this point.
            print("MoveMotorFast(",self.MotorName,"):SlewMotor:Fullstepping:Final WaitTime",self.WaitTime,'at',int(time.monotonic_ns()),"ns")

        # --- Fine movement to final target position ---
        self.SelectFineMovement() # Complete the move with 'fine' precision steps.
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
        print("MoveMotorFast(",self.MotorName,"):SlewMotor:FinalMicrostepping:Reset WaitTime to",self.WaitTime,'at',int(time.monotonic_ns()),"ns")
        while self.PendingSteps != 0:
            interrupt = self.StepMove(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
            #self.PendingSteps = self.PendingSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
            self.PendingSteps -= self.StepDir # REDUCE (-ve) the number of steps to take.
            self.SendMotorStatus(codes='mvf') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
            for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                self.RPi.BufferInput() # Keep polling for input from the RPi.
                self.RPi.WritePoll() # Keep sending data to RPi.
        print("MoveMotorFast(",self.MotorName,"):SlewMotor:FinalMicrostepping:Final WaitTime",self.WaitTime,'at',int(time.monotonic_ns()),"ns")
        if self.TraceMove: self.LogMoveState('mvf4') # For development purposes log the state of the motor at this point.
        self.CheckOnTarget() # Are we actually pointing at the target?
        if self.CurrentPosition != self.TargetPosition: # Did the motor slew close to the intended position? (May not be the requested target if movement limits reached)
            self.Log("MoveMotorFast(",self.MotorName,"): End. CurrentPosition (",self.CurrentPosition,") is NOT TargetPosition (",self.TargetPosition,")!")
        self.StatusLed.Task('idle')

    def StepToAngle(self, steps=None):
        """ Convert a number of steps to a final angle (0-360) of movement. 
            Parameters -----------------------------------------------------
            steps : Integer number of steps to convert into an angle. 
            Output ---------------------------------------------------------
            decimal angle """
        if steps != None:
            result = steps * 360.0 / float(self.AxisStepsPerRev)
        else:
            result = None
        return result

    def AngleToStep(self, deg=None):
        """ Convert a final angle of movement to the nearest whole number of motor steps.
            Parameters -----------------------------------------------------
            deg : Decimal angle to convert into a number of steps.
            Output ---------------------------------------------------------
            integer number of steps.             """
        if deg != None:
            result = int(round(deg * float(self.AxisStepsPerRev) / 360,0))
        else:
            result = None
        return result

    def ReportMotorConfig(self):
        """ Report motor configuration back to the RPi.
            Creates some comment lines for the serial buffer.
            This is to verify that the configuration was received and understood. """
        line = "# Motor " + self.MotorName + " conf 1: "
        line += IntToTimeString(self.Clock.Now()) + " " # Current clock time.
        line += "MinA " + str(self.MinAngle) + " "  # Motor minimum angle.
        line += "MinP " + str(self.MinPosition) + " " # Motor minimum step position.
        line += "MaxA " + str(self.MaxAngle) + " " # Motor maximum angle.
        line += "MaxP " + str(self.MaxPosition) + " " # Motor maximum step position.
        line += "LimP " + str(self.LimitPosition) + " " # Motor limit position.
        line += "RestA " + str(self.RestAngle) + " " # Motor rest/home angle.
        self.RPi.Write(line) # Send over UART to RPi.
        line = "# Motor " + self.MotorName + " conf 2: "
        line += "FastT " + str(self.FastTime) + " " # Fast step pulse time.
        line += "SlowT " + str(self.SlowTime) + " " # Slow step pulse time.
        line += "TDelta " + str(self.TimeDelta) + " " # Step pulse acceleration rate.
        line += "FaultS " + str(self.FaultSensitive) + " " # Sensitive to FAULT signals from stepper.
        line += "BackA " + str(self.BacklashAngle) + " " # Motor backlash angle.
        line += "Orient " + str(self.Orientation) + " " # Motor orientation.
        line += "OptMvs " + str(self.OptimiseMoves) + " " # Can motor optimise moves?
        self.RPi.Write(line) # Send over UART to RPi.
        line = "# Motor " + self.MotorName + " conf 3: "
        line += "GearRat " + str(self.GearRatio) + " " # Gear ratio attached to the motor.
        line += "uS/Rev " + str(self.MotorStepsPerRev) + " " # 200 or 400 step motor
        line += "AxStp/Rev " + str(int(self.AxisStepsPerRev)) + " " # Total steps for 1 revolution of entire assembly.
        line += "MtrCnf " + str(self.MotorConfigured) + " " # Is the motor configured and ready for use?
        line += "Drv " + str(self.DriverType) + " " # Driver type (tmc2209, drv8825)
        line += "MoCu% " + str(self.MoveCurrentPercent) + " " # Percentage of motor current used during movement.
        line += "HoCu% " + str(self.HoldCurrentPercent) + " " # Percentage of motor current used to hold position.
        line += "HoDe " + str(self.HoldDelay) + " " # Delay when switching from MOVE to HOLD current.
        self.RPi.Write(line) # Send over UART to RPi.
        
    def DriverFailed(self):
        """ Return TRUE if motor is in FAULT condition for any reason. """
        result = self.tmc2209.DriverFailed()
        if result: # Motor is in error condition.
            print(self.MotorName,": is in FAULT condition.")
        return result
        
    def add_position_sensor(self,sensor):
        """ Validate and add position sensor to the motor. 
            Make sure that all expected methods/attributes exist in the sensor instance.
            ----------------------------------------------------------------------------
            There can be multiple types of sensor added here, all handlers must present the 
            same list of methods/attributes so that the system can work with them. 
            Sensors are only added if they provide the expected features. """
        ok_to_add = True 
        attributes = ['Reset','Angle','SetReferenceAngle','GetStatusLine','absolute_position','configured']
        error_list = [] # List of errors to report back. 
        for a in attributes:
            if not hasattr(sensor,a):
                temp = "steppermotor(" + str(self.MotorName) + ").add_position_sensor(): Sensor does not contain " + str(a) + ". Will not add."
                print(temp)
                error_list.append(temp)
                ok_to_add = False
        if ok_to_add:
            self.position_sensor = sensor
            self.RPi.Write("# Added sensor for " + self.MotorName)
        else:
            self.RPi.Write("# Rejected sensor for " + self.MotorName)
            self.position_sensor = None
            for e in error_list: self.RPi.Write("# " + e)
        return ok_to_add
        
    def SendMotorStatus(self,immediate=False,codes='?-?'):
        """ Generate status message to RPi.
            The RPi uses this to decide what commands and configurations to send to the microcontroller.
            This can be triggered via multiple methods and in some circumstances can flood the RPi with
            messages. So there is a maximum repeat rate built in.
            immediate: True means that the status is sent even if not due.
                       False means that the status is only sent if the timer is due.
            codes: Optional string of codes that are added to the status message. (Debug/test/dev etc)
            
            Resulting line sent to RPi 
            
                motor status 20250304235046 azimuth y 20250304235135 3 34354 90.034 y y 0.002 2342 tmr 23423 90.231 n n n 
                  0     1          2           3    4      5         6   7      8   9 10  11   12   13  14     15  16 17 18
                  
            Parameters ------------------------------------------------------------------------------
            immediate : Boolean : When TRUE the status message is sent immediately.
                                  When FALSE the status message is only sent if the statustimer is due.
            """
        if immediate or self.StatusTimer.Due(): # Only send the status at regular intervals, otherwise we flood communications.
            #if hasattr(self.position_sensor,"update"): self.position_sensor.update() # Get current position of the axis if a position sensor sensor is available.
            if self.SendStatus == False: # Status message is currently disabled. Inform that we're not sending it.
                self.RPi.Write('# SendMotorStatus ' + IntToTimeString(self.Clock.Now()) + ' ' + self.MotorName + ' disabled. ' + str(codes))
                print("SendMotorStatus",self.MotorName,"disabled.",codes)
                return
            line = 'motor status ' # 0 & 1
            line += IntToTimeString(self.Clock.Now()) + ' ' # 2:  Current local timestamp.
            line += self.MotorName + ' ' # 3
            line += BoolToString(self.Trajectory.Valid) + ' ' # 4: TrajectoryValid
            line += IntToTimeString(self.Trajectory.ValidUntil()) + ' ' # 5: When does the trajectory run out?
            line += str(len(self.Trajectory.TrajectoryList)) + ' ' # 6: How many segments in the trajectory?
            line += str(self.CurrentPosition) + ' ' # 7: Where is the camera at the moment?
            line += str(self.CurrentDegrees()) + ' ' # 8: Where is the camera at the moment?
            line += BoolToString(self.MotorConfigured) + ' ' # 9: MotorConfigured
            line += BoolToString(self.OnTarget) + ' ' # 10: Motor is on target or not.
            line += str(self.WaitTime * 2) + ' ' # 11: The pulse period (indicates speed) of the motor.
            line += str(self.VMot()) + ' ' # 12: ADC0 is measuring motor voltage. Send the current ADC value. (or '0' if not enabled)
            line += str(codes) + ' ' # 13: Optional codes added to status message.
            #if hasattr(self.position_sensor,"Angle"): # Send current position.
            if self.position_sensor != None: # Send current position.
                angle = self.position_sensor.Angle() # Get angle and update associated measures.
                line += str(self.position_sensor.absolute_position) + ' ' # 14: Send absolute position of the sensor.
                line += str(angle) + ' ' # 15: Send the 'angle' of the entire assembly (including gearing).
                line += BoolToString(self.position_sensor.configured) + ' ' # 16: Is the position sensor offset angle configured?
            else:
                line += 'none ' # 14: No absolute position available from position sensor sensor.
                line += 'none ' # 15: assembly angle from position sensor.
                line += 'n ' # 16: position sensor is not configured.
            line += BoolToString(self.DriverFailed()) + ' ' # 17: Is there a FAULT condition with the driver?
            line += BoolToString(self.MotorHalt) + ' ' # 18: Is the MotorHalt latch set?
            self.RPi.Write(line) # Send over UART to RPi.
            # *Q* During development, dump the position sensor attributes too.
            #if hasattr(self.position_sensor,"get_status_line"): RPi.Write(self.position_sensor.get_status_line()) # Send over UART to RPi.
            if self.position_sensor != None: self.RPi.Write(self.position_sensor.GetStatusLine()) # Send over UART to RPi.
            # Reset the status timer.
            self.StatusTimer.Reset() # We've sent the regular status message, decide when the next is due.
