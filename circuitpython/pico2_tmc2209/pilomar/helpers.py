# pilomar/helpers.py - Circuitpython 9.2 build for Raspberry Pi Pico 2 (RP2350).
# For use with Raspberry Pi Pico 2 only.
# Dec.2024 / Refactored with help from TPROFFEN.

import board
import digitalio
import time
import gc

#-----------------------------------------------------------------------------------------------

helpers_version = "0.0.2" # A version number for this source code.

#-----------------------------------------------------------------------------------------------

class GPIOpin():
    """ Define a GPIO pin. 
        CircuitPython based upon board and digitalio libraries. """

    PinList = [] # Maintain a list of all defined pins.
    
    @staticmethod
    def ListPins():
        """ Print a list of defined pins. """
        print("Current defined GPIO pins:")
        for i,pin in enumerate(GPIOpin.PinList):
            print(i + 1,pin.PinNumber,pin.Name)

    def __init__(self,pin,name=None,invert=False):
        """ Create an IO Output pin. """
        print("GPIOpin: Initializing pin",pin,name)
        self.PwmMode = False # This is NOT in PWM mode.
        self.Pin = digitalio.DigitalInOut(pin)
        self.PinNumber = pin
        self.Name = name
        self.Invert = invert # Under development. Allow the pin logic to be inverted so LOW = ON, HIGH = OFF.
        self.PrevValue = self.GetValue()
        self.Frequence = None # For PWM
        GPIOpin.PinList.append(self) # Add this pin to the list of defined pins.

    def __del__(self):
        """ Called when deleting the object. 
            This will deinitialize the pin. """
        self.Deinit()

    def Deinit(self):
        """ Deinitialize the pin and release resources. """
        # Remove from PinList
        newlist = []
        for i in GPIOpin.PinList:
            if i != self: newlist.append(i)
        GPIOpin.PinList = newlist
        self.Pin.deinit() # Deinitialize the pin and release resources.

    def ConvertToPWM(self,frequency=500):
        """ Define the pin as a PWM pin. """
        print("GPIOpin.ConvertToPWM(): Initializing pin",self.PinNumber,"as PWM, freq",frequency)
        self.Deinit() # Remove previous pin configuration.
        self.PwmMode = True # This IS now in PWM mode.
        self.Frequency = frequency
        self.Pin = pwmio.PWMOut(self.PinNumber,frequency=frequency,duty_cycle=0) # Define PWM output, but inactive.
        GPIOpin.PinList.append(self) # Add this pin to the list of defined pins.

    def StartPWMSignal(self):
        """ Start PWM output. """
        self.Pin.duty_cycle = 0x7fff # 50% on, 50% off cycle.
        
    def StopPWMSignal(self):
        """ Stop PWM output. """
        self.Pin.duty_cycle = 0 # 100% off.
        
    def RevertFromPWM(self):
        """ Revert pin to standard GPIO output pin. """
        self.DeInit()
        self.PwmMode = False # This is NOT in PWM mode.
        self.Pin = digitalio.DigitalInOut(self.PinNumber) # Revert to standard OUTPUT pin.
        GPIOpin.PinList.append(self) # Add this pin to the list of defined pins.

    def SetDirection(self,direction,value=False,pull=None):
        self.Pin.direction = direction
        if direction == digitalio.Direction.OUTPUT: 
            self.Pin.value = value # turn off.
        elif pull != None: 
            self.Pin.pull = pull # Set pull up/down if specified.

    def SetPull(self,pull):
        if self.Pin.direction == digitalio.Direction.INPUT: # Can set pull up/down.
            self.Pin.pull = pull

    def SetPullUp(self):
        self.SetPull(digitalio.Pull.UP)

    def SetPullDown(self):
        self.SetPull(digitalio.Pull.DOWN)

    def SetValue(self,value):
        if self.Pin.direction == digitalio.Direction.OUTPUT: 
            self.Pin.value = value

    def GetValue(self):
        """ Return underlying state of the pin from the GPIO library. 
            No inversion or logical changes of state applied here. """
        return self.Pin.value

    def High(self):
        """ Return the electrical value of the pin.
            TRUE means the value is 'high'. 
            FALSE means the value is 'low'. """
        return self.GetValue()

    def IsOn(self):
        """ Return TRUE if switch is ON.
            Respects self.Invert
            When self.Invert is TRUE: HIGH means OFF, LOW means ON.
            When self.Invert is FALSE: HIGH means ON, LOW means OFF. """
        if self.Invert: # Invert the electrical level.
            return self.Low()
        else:
            return self.High()

    def Low(self):
        """ Return the opposite of the electrical value of the pin.
            TRUE means the value is 'low' 
            FALSE means the value is 'high' """
        return not self.GetValue()

    def IsOff(self):
        """ Return TRUE if switch is OFF.
            Respects self.Invert
            When self.Invert is TRUE: HIGH means OFF, LOW means ON.
            When self.Invert is FALSE: HIGH means ON, LOW means OFF. """
        if self.Invert: # Invert the electrical level.
            return self.High()
        else:
            return self.Low()

    #def Pressed_orig(self):
    #    """ Return True if the electrical signal has risen (Gone High).
    #        Currently an alise of the Rise method, but may change in future versions.
    #        This represents the 'LOGICAL' change of the switch. 
    #        Doesn't respect the self.Invert attribute. """
    #    result = self.Rise()
    #    return result 
        
    def Pressed(self):
        """ Return True if the switch has been triggered.
            This represents the 'LOGICAL' change of the switch. 
            Respects the self.Invert attribute. """
        result = False # Not pressed yet.
        if self.Pin.value != self.PrevValue: # Switch has changed state.
            if self.IsOn(): # Switch has been pressed (invert respected)
                result = True
            self.PrevValue = self.Pin.value
        return result
        
    #def Pressed(self):
    def Rise(self):
        """ Return TRUE if the pin has just gone HIGH else FALSE. 
            This represents the ELECTRICAL change of the switch. """
        result = False
        if self.Pin.value != self.PrevValue:
            if self.Pin.value: # Gone HIGH.
                result = True
            self.PrevValue = self.Pin.value
        return result

    #def Released_orig(self):
    #    """ Return True if the electrical signal has fallen (Gone Low)
    #        Currently an alias of the Fall method, but may change in future versions.
    #        This represents the 'LOGICAL' change of the switch.
    #        Doesn't respect self.Invert attribute. """
    #    result = self.Fall()
    #    return result 
        
    def Released(self):
        """ Return True if the switch has been released.
            This represents the 'LOGICAL' change of the switch.
            Respects the self.Invert attribute. """
        result = False # Not pressed yet.
        if self.Pin.value != self.PrevValue: # Switch has changed state.
            if self.IsOff(): # Switch has been released (invert respected)
                result = True
            self.PrevValue = self.Pin.value
        return result
        
    def Fall(self):
        """ Return TRUE if the pin has just gone LOW else FALSE.
            This represents the ELECTRICAL change of the switch. """
        result = False
        if self.Pin.value != self.PrevValue:
            if not self.Pin.value: # Gone LOW.
                result = True
            self.PrevValue = self.Pin.value
        return result
        
    def PinStatus(self):
        """ Return text string with pin status. For reporting back to RPi.

        eg:    "GP28 altstep n"

        """
        text = str(self.PinNumber).split('.')[-1] + " " + str(self.Name) + " " 
        if self.GetValue(): text += "y" # ON
        else: text += "n" # OFF
        return text
        
#-----------------------------------------------------------------------------------------------

class led():

    LedList = [] # List of defined LEDs.
    
    def __init__(self,pin,name,state=False,features=['PICO','RP2350']):
        """ Tiny RGB LED on/off state is inverted!
            ie to turn LED ON, pin must go LOW.
               to turn LED OFF, pin must go HIGH. """
        self.Features = features
        if 'PICO' in self.Features: # Pico LEDs trigger as expected.
            self.OnValue = True
            self.OffValue = False
        else: # Tiny microcontrollers LEDs trigger is inverted.
            self.OnValue = False
            self.OffValue = True
        self.Led = digitalio.DigitalInOut(pin)
        self.LedNumber = pin
        self.Name = name
        self.Led.direction = digitalio.Direction.OUTPUT
        self.Led.value = None # Off
        self.Enabled = True # Set to FALSE to turn off the LED completely.
        if state: self.On()
        else: self.Off()
        led.LedList.append(self) # Add this pin to the list of defined pins.

    def Enable(self):
        """ Enable the LED and turn it on if required. """
        self.Enabled = True
        if self.Led.value: self.On()

    def Disable(self):
        """ Disable the LED and make sure it is turned off. """
        self.Enabled = False
        self.Off()

    def On(self):
        """ Turn the LED ON.
            NOTE: Tiny RGB LED uses opposite pin state to control LED. """
        if self.Enabled: self.Led.value = self.OnValue
        else: self.Led.value = self.OffValue

    def Off(self):
        """ Turn the LED OFF.
            NOTE: Tiny RGB LED uses opposite pin state to control LED. """
        self.Led.value = self.OffValue

    def GetValue(self):
        """ Return True/False if pin is on or off. """
        return self.Led.value
        
    def PinStatus(self):
        """ Return text string with pin status. For reporting back to RPi.

        eg:    "GP28 altstep n"

        """
        text = str(self.LedNumber).split('.')[-1] + " " + str(self.Name) + " " 
        if self.GetValue(): text += "y" # ON
        else: text += "n" # OFF
        return text

#-----------------------------------------------------------------------------------------------

class statusled():
    """ Status LED handler.
        The LED solution varies per board.
        Pimoroni Tiny boards have RGB LED status lights.
        RaspberryPi Pico boards only have a single status light.
        The RGB LED is a collection of up to three led() objects. """
    def __init__(self,features=['PICO','RP2350']):
        self.Features = features
        # Raspberry Pi Pico & Pico 2
        if 'PICO' in self.Features: # Raspberry Pi PICO single LED pin.
            self.LedR = None # No RED LED on PICO.
            self.LedG = led(board.LED,name='green',features=self.Features) # Create LED for GREEN channel.
            self.LedB = None # No BLUE LED on PICO.
            self.TaskList = {'idle': (False,False,False), # Off (r,g,b)
                             'coms': (False,True,False), # Blue - Flashes when handling UART
                             'move': (False,True,False), # green - Flashes when motor is moving.
                             'error': (False,True,False), # Red - Indicates failure/fault.
                             'init': (False,True,False)} # cyan - System is initializing.
        else: # Pimoroni Tiny separate RG&B LED pins.
            self.LedR = led(board.LED_R,name='red',features=self.Features) # Create LED for RED channel.
            self.LedG = led(board.LED,name='green',features=self.Features) # Create LED for GREEN channel.
            self.LedB = led(board.LED_B,name='blue',features=self.Features) # Create LED for BLUE channel.
            self.TaskList = {'idle': (False,False,False), # Off (r,g,b)
                             'coms': (False,False,True), # Blue - Flashes when handling UART
                             'move': (False,True,False), # green - Flashes when motor is moving.
                             'error': (True,False,False), # Red - Indicates failure/fault.
                             'init': (False,True,True)} # cyan - System is initializing.
        self.Enabled = True # If set to FALSE, the LED is permanently off except for ERROR conditions.
        self.StatusExpiry = 0 # Timeout on any status light being displayed (time in seconds based upon monotonic_ns() counter).
        self.Task('idle')

    def Enable(self):
        """ Enable the LED. """
        self.Enabled = True

    def Disable(self):
        """ Disable the LED. """
        self.Enabled = False
        self.Task('idle')

    def Task(self,task):
        """ Set LED color according to the task assigned.
            ERROR tasks always win, and an ERROR setting stays illuminated for at least 1 second
            before any other task can set any other colors. """
        ErrorTask = 'error'
        monotonic_seconds = int(time.monotonic_ns() / 1e9) # Seconds timer. Reduce by 1.0e9 to get seconds.
        if monotonic_seconds < self.StatusExpiry: # Error code is still valid. No other setting can be used yet.
            pass
        elif self.Enabled or task == ErrorTask: # No current ERROR status, so we can consider whether to set the new status.
            if task == ErrorTask: # Setting a new error status. Set the timeout for 1 second ahead.
                self.StatusExpiry = monotonic_seconds + 1 # Set 1 second expiry on error codes.
            if task in self.TaskList: # Pull the color codes for the selected task.
                t = self.TaskList[task]
                if self.LedR == None: pass # Is there an LED defined?
                elif t[0]: self.LedR.On()
                else: self.LedR.Off()
                if self.LedG == None: pass # Is there an LED defined?
                elif t[1]: self.LedG.On()
                else: self.LedG.Off()
                if self.LedB == None: pass # Is there an LED defined?
                elif t[2]: self.LedB.On()
                else: self.LedB.Off()
            else: # If the task is not recognised, the LEDs are turned off.
                if self.LedR != None: self.LedR.Off()
                if self.LedG != None: self.LedG.Off()
                if self.LedB != None: self.LedB.Off()
        else: # LED is disabled for everything except ERRORS
            if self.LedR != None: self.LedR.Off()
            if self.LedG != None: self.LedG.Off()
            if self.LedB != None: self.LedB.Off()

    def SetRGB(self,line):
        """ Receive a 'set rgb' command from the RPi and turn on
            the status LED in that color to acknowledge it.
            This is a debug/dev feature to let people prove that
            the Tiny is indeed receiving and processing commands.

            This works even if the LED is disabled!

            set rgb yyyymmddhhmmss y y y nnn
             0   1       2         3 4 5  6

            3 = y/n = RED ON
            4 = y/n = GREEN ON
            5 = y/n = BLUE ON
            6 = nnn = Minimum seconds to illuminate. """
        lineitems = line.split(' ')
        lli = len(lineitems)
        if self.LedR != None:
            if lli > 3 and lineitems[3] == 'y': self.LedR.On()
            else: self.LedR.Off()
        if self.LedG != None:
            if lli > 4 and lineitems[4] == 'y': self.LedG.On()
            else: self.LedG.Off()
        if self.LedB != None:
            if lli > 5 and lineitems[5] == 'y': self.LedB.On()
            else: self.LedB.Off()
        if lli > 6:
            self.StatusExpiry = int(time.monotonic_ns() / 1e9) + int(lineitems[6]) # Set expiry (in seconds) on the LED color.

#-----------------------------------------------------------------------------------------------

class exceptioncounter():
    """ Keep a count of how many exceptions have been raised during operation.
        All exceptions should be reported back to the RPi in the log messages
        however a simple counter also ensures we know when things are having
        problems. Implemented as a class so that it can be called consistently
        from inside other methods and objects.
        This will also automatically set the LED to the error color. """
    def __init__(self, StatusLed):
        self.StatusLed = StatusLed
        self.Count = 0 # Initialize the counter.

    def Reset(self):
        """ Reset the exception count. """
        self.Count = 0 # Initialize the counter.

    def Raise(self,info=None):
        try:
            self.Count += 1 # Increment the count.
            self.StatusLed.Task('error') # Set the LED to show an error was trapped.
            print("Exception trapped:",info)
        except Exception as e:
            print("exceptioncounter.Raise(",info,") failed:",str(e))

#-----------------------------------------------------------------------------------------------

class timer():
    """ An event timer mechanism.
        Create with
            NAME = timer('heartbeat',repeat=30,offset=10)
                'heartbeat' = name of the timer.
                repeat = 30 seconds between events.
                offset = 1st event is current time + 10 seconds.
        Use with
            if NAME.Due(): print ('Event due')

        This returns TRUE if the timer has expired.
        It automatically resets the timer to repeat.

        MyTimer = timer('demo',30)
        while True:
            if MyTimer.Due(): print("another 30 seconds has passed.")

        """
    def __init__(self,name,repeat,offset=0):
        """ Create the timer.
            Initialize the first due time. """
        self.Name = name
        if repeat < 1: repeat = 1 # Minimum repeat cycle is 1 second.
        self.RepeatSeconds = repeat
        if offset != 0: self.NextDue = time.time() + offset # If the timer starts with an offset then that's the FIRST due time.
        else: self.NextDue = time.time() + repeat # There's no offset, so due time is calculated from now.

    def SetNextDue(self):
        """ If NextDue has expired, this calculates the next future value.
            It always rolls forward a whole number of 'repeat seconds' to the first due time that is in the future. """
        while self.NextDue <= time.time():
            gap = ((time.time() - self.NextDue) // self.RepeatSeconds) + 1 # How many multiples of 'repeatseconds' do we need to add to get to the next timeslot?
            if gap >= 0:
                self.NextDue = self.NextDue + (self.RepeatSeconds * gap)

    def Reset(self):
        """ Restart the time from NOW. """
        self.NextDue = time.time() + self.RepeatSeconds

    def Remaining(self):
        """ How many seconds left on the timer? """
        remaining = self.NextDue - time.time()
        return remaining

    def Due(self):
        """ This returns TRUE if the timer has expired.
            It returns FALSE if the timer is still running.
            If the timer expires, it also resets the timer for the next event. """
        result = False
        temp = self.Remaining()
        if temp > self.RepeatSeconds: # If the local clock changes, the timer may be left out of sync. Reset it.
            print("clock(",self.Name,") remaining",temp,"exceeds repeat",self.RepeatSeconds,". Timer reset.")
            self.NextDue = time.time() + self.RepeatSeconds
        elif temp <= 0: # Timer expired.
            result = True
            self.SetNextDue()
        return result

#-----------------------------------------------------------------------------------------------

class logfile():
    """ A simple logging mechanism.
        Record any log messages in a temporary list.
        When directed, send the list to the remote server
        for storage.

        MyLog = logfile()
        MyLog.Log("This is a message for the logfile")
        ...
        MyLog.SendAll()

        """
    def __init__(self):
        self.Lines = [] # List of log messages waiting to be sent to the RPi via UART.
        self.RPi = None # Which UART handler is dealing with the RPi communication.
        self.BufferSize = 0 # Current size of the message queue (characters).
        self.MaxLines = 20 # Do not store more than 20 lines due to memory constraints.
        self.Overflows = 0 # How many times has the buffer filled?

    def setHost(self, RPi):
        """ Tell the instance which UART handler is communicating with the microcontroller. 
            This is the comms between the microcontroller and the RPi. 
            Log messages are only sent once this is assigned.
            Before this is assigned log messages are printed to the microcontroller's serial output. """
        self.RPi = RPi
        
    def Log(self,line,*args):
        """ Accept any number of arguments, convert them into a single log file message. """
        for x in args:
            #if type(x) == type(str): a = x
            if type(x) == str: a = x
            else: a = str(x) # Convert all additional items to strings and append them.
            line = (line + ' ' + a).strip()
        if self.Clock == None:
            line = IntToTimeString(time.time()) + ":" + line + '\n'
        else:
            line = IntToTimeString(self.Clock.Now()) + ":" + line + '\n'
        if len(self.Lines) < self.MaxLines: # We have space to store more messages awaiting transmission.
            self.Lines.append(line)
            self.BufferSize += len(line)
        else: # Buffer is full. Don't accept this message into the queue.
            print("logfile.Log: Buffer is full, ignored:",line)
            self.Overflows += 1 # Increment number of messages that were rejected due to overflow.
            print("logfile.Log: Memory available",gc.mem_free(),"bytes.")

    def SendAll(self):
        """ Call this to send ALL the outstanding log entries.
            Sends the log entry via UART if defined. 
            Otherwise prints to the terminal (serial debug?) display. """
        if self.RPi != None: # A UART port is defined, send the messages there.
            for line in self.Lines:
                self.RPi.Write('log :' + line,log=False)
        else: # No UART port, display to the serial debug port instead.
              # You COULD choose to hold on to these lines by waiting until some characters received, but buffer may overflow.
            for line in self.Lines:
                print('log :',line)
        self.Lines = []
        self.BufferSize = 0

    def SendOne(self):
        """ Call this to send a single log entry if the microcontroller is idle. 
            Sends the log entry via UART if defined. 
            Otherwise prints to the terminal (serial debug?) display. """
        if len(self.Lines) > 0:
            line = self.Lines.pop(0)
            tottemp = 0
            for line in self.Lines: tottemp += len(line)
            self.BufferSize = tottemp
            if self.RPi != None: self.RPi.Write('log :' + line,log=False) # Send through defined UART port.
            else: print('log :',line) # Display to terminal instead. You COULD choose to hold on to these lines by waiting until some characters received, but buffer may overflow.

    def SendCheck(self,force=False):
        """ If local buffer is large enough, send it to the host
            and reset ready for new messages. """
        if self.BufferSize > 80 or force:
            self.SendAll()

#-----------------------------------------------------------------------------------------------

class clock():
    """ Maintain a clock that is roughly in sync with the host server.
        If the microcontroller is running standalone, then its internal clock
        does not get synchronised. This class allows a 'timedelta' to be
        defined in the program which is applied to the internal clock to
        give an approximately current timestamp.
        If the microcontroller is linked to a development tool such as Thonny
        it may synchronise the internal clock, in which case the TimeDelta will
        not be used.
        If the Thonny connection is made AFTER the program has started, the
        TimeDelta value will no longer be needed when the internal clock itself
        is synchronised. If this is detected, TimeDelta is cleared and rechecked. """
        
    def __init__(self, LogFile, ExceptionCounter, RPi=None, TimeValue=None):
        """ Create instance. 
            Parameters ------------------------------------------------------
            LogFile : Instance of the logfile class. Records log messages and sends them to the host RPi. 
            ExceptionCounter : Counts code exceptions and indicates errors via Status led. 
            RPi : Optional instance of the UART class which communicates with the RPi. 
            TimeValue : Specific timestamp which is used to set the application clock. """
        self.LogFile = LogFile
        self.ExceptionCounter = ExceptionCounter
        self.RPi = RPi
        self.TimeDelta = 0 # Offset from machine clock to current date/time (in seconds).
        self.ClockSynchronised = False # Indicates that the clock is synchronised.
        self.PrevTime = time.time() # Record the initial unmodified time of the clock. Used to detect if machine clock gets updated.
        if type(TimeValue) == type(str): self.SetTimeFromString(TimeValue)
        elif type(TimeValue) == type(int): self.SetTimeFromInt(TimeValue)
        # Values for the NowDecimal() function which simulates fractions of a second for timestamps.
        self.CurrTime = time.time() # What's the current integer timestamp?
        self.FirstNS = time.monotonic_ns() # What's the nanosecond count when the current timestamp first occurred? (Used to create pseudo sub-second digits)
        # Warning: CircuitPython times are stored as single integer. The value overflows 2038-01-19 03:14:07
        if time.localtime(time.time())[0] > 2037:
            print("CLOCK WARNING: CircuitPython time.time() result: Integer overflow after 2038-01-19 03:14:07")
            self.LogFile.Log("CLOCK WARNING: CircuitPython time.time() result: Integer overflow after 2038-01-19 03:14:07")

    def UpdateClockFromInt(self,TimeInt):
        """ Given any integer timestamp this will compare against the clock
            and update the clock if the new timestamp is AHEAD of the current
            clock. This increases the accuracy/synchronisation of the clock with the RPi's clock.
            This can be run against any received timestamp to continually improve the clock's time. """

        tn = self.Now() # What time does the microcontroller think it is at the moment?
        result = False
        if TimeInt != None and TimeInt > tn: # We can nudge the clock forward, never backwards.
            self.SetTimeFromInt(TimeInt)
            self.LogFile.Log("UpdateClockFromInt(",IntToTimeString(TimeInt),") replaces",IntToTimeString(tn),"Updated clock.")
            result = True
        return result

    def PureDigitString(self,rawstring):
        """ Remove all non-digits from a character string. 
            Example: Converts "2022-12-04 09:25:45.752+00:00" into "202212040925457520000"  """
        result = ''
        # Remove special characters from timestamp. We only want the digits.
        for a in rawstring: 
            if '0' <= a <= '9': result += a
        return result
        
    def UpdateClockFromString(self,TimeString):
        """ Given any character timestamp this will compare against the clock
            and update the clock if the new timestamp is AHEAD of the current
            clock. This increases the accuracy/synchronisation of the clock with the RPi's clock.
            This can be run against any received timestamp to continually improve the clock's time.

            If the microcontroller is connected via USB to Thonny on a remote machine, the machine clock may then
            get synchronised, in which case the TimeDelta value is nolonger needed. """

        success = False
        #for a in [' ','.','-',':']: # Remove special characters from timestamp. We only want the digits.
        #    TimeString = TimeString.replace(a,"")
        CleanString = self.PureDigitString(TimeString) # Remove non-digit characters from the input string.
        try:
            result = TimeStringToInt(CleanString)
            self.UpdateClockFromInt(result)
            success = True
        except:
            self.LogFile.Log("UpdateClockFromString(",TimeString,") failed: CleanString:",CleanString)
            self.ExceptionCounter.Raise() # Increment exception count for the session.
        return success

    def CheckTimeDelta(self,now):
        """ If the basic clock time suddenly jumps, assume that the clock has been synchronised
            in which case clear TimeDelta because it's nolonger needed. """
        time_delta = now - self.PrevTime
        if time_delta > 3600: # Clock has suddenly jumped an hour or more!
            print("c.CTD: CheckTimeDelta: Delta is",time_delta,"at",self.NowString())
            print("c.CTD: Internal clock may have synchronised. Resetting clock synchronisation.")
            self.TimeDelta = 0
            self.ClockSynchronised = False
            self.LogFile.Log("CheckTimeDelta(): Internal clock may have synchronised. Resetting clock synchronisation.")
        self.PrevTime = now

    def SetTimeFromInt(self,TimeInt):
        """ Set clock offset from an INTEGER TIME. """
        self.TimeDelta = max(TimeInt - time.time(),0) # Time offset is the received time - the realtime clock time. Cannot be negative.
        self.ClockSynchronised = True
        if self.RPi != None:
            self.RPi.Write('# Clock now ' + self.NowString() + ' timedelta ' + str(self.TimeDelta) + ' seconds.')

    def SetTimeFromString(self,TimeString):
        """ Set clock offset from a CHARACTER TIME. """
        result = False
        for a in (' ','.','-',':'):
            TimeString = TimeString.replace(a,"")
        try:
            result = self.SetTimeFromInt(TimeStringToInt(TimeString))
        except Exception as e:
            self.LogFile.Log('clock.SetTimeFromString: Invalid timestamp string (', TimeString, ')')
            self.ExceptionCounter.Raise() # Increment exception count for the session.
        return result

    def Now(self):
        """ Return current clock time. As micropython number of seconds."""
        now = time.time()
        self.CheckTimeDelta(now) # If the internal clock has recently been synchronised clear TimeDelta until it can be recalculated.
        return (now + self.TimeDelta)

    def NowDecimal(self):
        """ Returns 2 values.
            1) The traditional integer time.time() value.
            2) A matching pseudo fraction of a second,
               this is calculated using time.monotonic_ns() to measure
               nanoseconds and estimate how many nanoseconds have elapsed
               since the current 'second' first occurred. """
        CurrDecimal = 2.0
        while CurrDecimal >= 1.0: # Decimal must be within the current second.
            while self.Now() != self.CurrTime: # If the clock has rolled on to a new second, calculate a ZERO point for the monotonic_ns() clock.
                self.FirstNS = time.monotonic_ns() # This is the ZERO point for nanoseconds within this second.
                self.CurrTime = self.Now() # The current clock time.
            CurrDecimal = float(time.monotonic_ns() - self.FirstNS) / 1e+9 # Elapsed fraction of a second since is started. (Be careful converting time.monotonic_ns() result directly to float, precision is lost)
        return self.CurrTime, CurrDecimal

    def NowString(self):
        """ Return current clock time. As character string. """
        return IntToTimeString(self.Now())

#-----------------------------------------------------------------------------------------------

class memorymanager():
    def __init__(self):
        self.currmem = None # Current memory free value.
        self.GCCount = 0 # How many times has garbage collector run?
        self.Poll()

    def Poll(self): # Check current memory and trigger memory garbage collection early if needed.
        """ It looks like CircuitPython allocates memory in 2K chunks, it will error out if it cannot allocate 2K at a time. 
            So run cleanup at 3K for safety. """
        self.currmem = gc.mem_free()
        if self.currmem < 3000:
            gc.collect()
            self.GCCount += 1 # Increase count of garbagecollector runs.

#-----------------------------------------------------------------------------------------------
# Various conversion routines
#-----------------------------------------------------------------------------------------------

def BoolToString(value):
    if value: result = 'y'
    else: result = 'n'
    return result

def StringToBool(value,default=False):
    if value.lower() == 'y' or value.lower() == 'true': result = True
    elif value.lower() == 'n' or value.lower() == 'false': result = False
    else: result = default
    return result

def IntToTimeString(timestamp):
    # Sometime around 2034, this may cause problems for localtime() method if it generates longint values.
    # int values max out at (2^30) - 1 = 1073741823
    lt = time.localtime(timestamp)
    entry = ('0000' + str(lt[0]))[-4:] # Year
    entry += ('00' + str(lt[1]))[-2:] # Month
    entry += ('00' + str(lt[2]))[-2:] # Day
    entry += ('00' + str(lt[3]))[-2:] # Hour
    entry += ('00' + str(lt[4]))[-2:] # Minute
    entry += ('00' + str(lt[5]))[-2:] # Second
    return entry

def TimeStringToInt(timestamp):
    # Sometime around 2034, this may cause problems for mktime() method if it generates longint values.
    # int values max out at (2^30) - 1 = 1073741823
    year = int(timestamp[0:4])
    month = int(timestamp[4:6])
    day = int(timestamp[6:8])
    hour = int(timestamp[8:10])
    minute = int(timestamp[10:12])
    second = int(timestamp[12:14])
    result = time.mktime((year,month,day,hour,minute,second,0,-1,-1))
    return result

def IsInt(text):
    """ Return TRUE if a string can be converted to an integer value. """
    result = False
    try: 
        _ = int(text)
        result = True
    except ValueError:
        pass 
        # Don't increment exception count for this one.
    return result

def IsFloat(text):
    """ Return TRUE if a string can be converted to a float value. """
    result = False
    try:
        _ = float(text)
        result = True
    except ValueError:
        pass
        # Don't increment exception count for this one.
    return result

def ns_sleep_debug(delay=1.0,debug=True):
    """ A 'sleep' function that operates on times faster than 0.001 seconds.
        The traditional time.sleep() doesn't operate below 0.001 seconds in CircuitPython.
        For times briefer than 0.001 seconds this uses the monotonic_ns clock instead.
        Development/debug version of ns_sleep() function. """
    if delay < 0.001: # Use alternative sleep functionality for very brief periods.
        start_ns = int(time.monotonic_ns() * 1.0)
        delay_ns = int(delay * 1e9)
        end_ns = start_ns + delay_ns
        #now_ns = int(time.monotonic_ns() * 1.0)
        if debug: 
            print("ns_sleep(",'{:.10f}'.format(delay),
                  "): Initial: start_ns",'{:.2f}'.format(start_ns),
                  "now_ns",'{:.2f}'.format(now_ns),
                  "end_ns",'{:.2f}'.format(end_ns),
                  "delay_ns",'{:.2f}'.format(delay_ns),
                  "check ns from start",int(now_ns - start_ns),
                  "check ns to end",int(end_ns - now_ns))
            count = 0
            if end_ns <= now_ns: print("ns_sleep: end_ns <= now_ns!")
            if end_ns <= start_ns: print("ns_sleep: end_ns <= start_ns!")
        while True:
            now_ns = int(time.monotonic_ns() * 1.0)
            if debug: 
                print("ns_sleep(",'{:.10f}'.format(delay),
                      "): Loop: start_ns",'{:.2f}'.format(start_ns),
                      "now_ns",'{:.2f}'.format(now_ns),
                      "end_ns",'{:.2f}'.format(end_ns),
                      "delay_ns",'{:.2f}'.format(delay_ns),
                      "check ns from start",int(now_ns - start_ns),
                      "check ns to end",int(end_ns - now_ns))
                if now_ns < start_ns: print("ns_sleep(): now_ns slipped backwards!")
                count += 1
            if now_ns >= end_ns: 
                if debug: print("timer expired")
                break # Timer expired. 
            if now_ns < start_ns:
                if debug: print("clock reset")
                break # Clock reset.
        if debug: print("ns_sleep(",'{:.10f}'.format(delay),
                        "): Final: start_ns",'{:.2f}'.format(start_ns),
                        "now_ns",'{:.2f}'.format(now_ns),
                        "end_ns",'{:.2f}'.format(end_ns),
                        "elapsed_ns",'{:.2f}'.format(now_ns - start_ns),
                        "count",'{:.2f}'.format(count))
    else: time.sleep(delay) # Use standard CircuitPython sleep function.

#def ns_sleep_001(delay=1.0):
#    """ A 'sleep' function that operates on times faster than 0.001 seconds.
#        The traditional time.sleep() doesn't operate below 0.001 seconds in CircuitPython.
#        For times briefer than 0.001 seconds this uses the monotonic_ns clock instead. """
#    if delay < 0.001: # Use alternative sleep functionality for very brief periods.
#        start_ns = int(time.monotonic_ns() * 1.0)
#        delay_ns = int(delay * 1e9)
#        end_ns = start_ns + delay_ns
#        while True:
#            now_ns = int(time.monotonic_ns() * 1.0)
#            if now_ns >= end_ns: 
#                break # Timer expired. 
#            if now_ns < start_ns:
#                print("ns_sleep(): Clock reset.")
#                break # Clock reset.
#    else: time.sleep(delay) # Use standard CircuitPython sleep function.

def ns_sleep(delay=1.0):
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

def test_ns_sleep(delay,iterations):
    """ Test ns.sleep() function. """
    print('test_ns_sleep(',delay,',',iterations,'): Begin')
    starttime = time.time()
    for i in range(iterations):
        ns_sleep(delay)
    endtime = time.time()
    print('test_ns_sleep completed between',IntToTimeString(starttime),'and',IntToTimeString(endtime),'=',endtime - starttime,'seconds')
    
#def ns_sleep(delay=1.0):
#        """ Provide a SLEEP function which supports pauses less than 1 millisecond.
#            Standard time.sleep() does not seem to work below 1 millisecond.
#            at 200MHz this can achieve delays down to 0.00022 seconds. 5 times shorter than time.sleep() """
#        if delay < 0.001: # Very short delays don't work with the standard function.
#            t1 = time.monotonic_ns() + (delay * 1e9) # When does the delay expire?
#            while time.monotonic_ns() < t1:
#                pass # Loop until clock reaches the set time.
#        else: # Millisecond and above delays can use standard function.
#            time.sleep(delay)
#        return True

def check_version():
    Bootline = '' # Make sure the entire boot_out.txt content is available as a single item.
    CircuitPythonVersion = ''
    CircuitPython = False
    with open('boot_out.txt','r') as f: # Read the configuration summary.
        while True: # Loop through all the lines in turn.
            line = f.readline()
            if line == '': break # End of file.
            lines = line.split(';') # Split the line.
            for item in lines:
                cleanitem = item.strip() # Remove unwanted characters.
                Bootline += cleanitem + ' '
                for elements in item.split(' '): # Split into individual elements.
                    if elements.strip().lower() == 'circuitpython': CircuitPython = True # This is a CircuitPython build.
                    if len(elements.split('.')) > 2: # 'a.b.c' and 'a.b.c-alpha.2350' formas are version number.
                        CircuitPythonVersion = elements # Allows code to adapt to different CircuitPython versions.

    return (CircuitPythonVersion, Bootline, CircuitPython)
