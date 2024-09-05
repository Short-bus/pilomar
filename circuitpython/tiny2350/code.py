# code.py - circuitpython version - Pimoroni Tiny2350 test version.
#           Currently using pico 2 circuitpython build as Tiny2350 isn't available yet.

# Sample messages...
#  From microcontroller to RPi
#   session status 20210409090929 False False False 20 None None
#   comms status 20210409090929 0 0 538 0
#   motor status 20210409090939 azimuth False 20210409090939 0 48000 180.0 True
#   motor status 20210409090949 altitude False 20210409090949 0 0 0.0 True
#  From RPi to microcontroller
#   configure motor 20210409090949 azimuth 180.0
#   sendstatus 20210409090949 False

# NOTE: Under CircuitPython 8 & Raspian Bookworm: Thonny seems to struggle sometimes.
# You can get memory and other errors thrown at you when you try to load a new version of this program
# onto the microcontroller. 
# - It is more common for the microcontroller to switch to 'read-only' mode in that configuration.
#   Search online for 'reset file system in circuitpython'
# 
#      From REPL in Thonny
#      >>> import storage
#      >>> storage.erase_filesystem()
#
#      You can then try downloading code.py once more.
# - If you cannot open code.py in Thonny it usually helps to restart Thonny.

# If you want to run the microcontroller with the USB cable permanently attached 
# there is a risk that the microcontroller will auto-reload randomly whenever the 
# RPi O/S accesses the CIRCUITPY drive. If this is the case you can disable 
# autoreloading by uncommenting the 2 lines below.
#    (If these two lines are active you will have to manually restart the 
#     microcontroller each time you update the source code. 
#     Pressing the RESET button is the most effective method.)
#import supervisor
#supervisor.runtime.autoreload = False

# Version numbering scheme:
#       MAJOR.MINOR.MICRO
#       MAJOR = Major version, large changes to functionality. Likely to require major version change on RPi side too.
#       MINOR = Feature changes, but same overall program. May require functionality change on RPi side too.
#       MICRO = Bugfix, no feature changes. Will not require changes on RPi side.
VERSION = '1.1.0' # Software version reported to the RPi.
ACCEPTABLERPIVERSIONS = ['1.0'] # Which RPi versions are acceptable? (Ignore patch level)

print ('hello')
print ('This is code.py for CircuitPython.')
print ('This supports: Pimoroni Tiny2040, Pimoroni Tiny2350.')

# Check we are running CircuitPython.
CircuitPython = False # Indicates CircuitPython rather than MicroPython.
# Bootline contains description like...
# Adafruit CircuitPython 7.2.0 on 2022-02-24 Pimoroni Tiny 2040 (8MB) with rp2040 Board ID:pimoroni_tiny2040|4e4b
Bootline = '' # Make sure the entire boot_out.txt content is available as a single item.
CircuitPythonVersion = ''
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
print("CircuitPython installed:",CircuitPython, "version:",CircuitPythonVersion,"environment:",Bootline)

import digitalio
import board
print("This board is",board.board_id)
from busio import UART as busio_UART # Only need the UART features.
import time
import gc # Garbage Collector

# What features do we have available on this board?
FEATURES = []
if board.board_id in ['raspberry_pi_pico2','pimoroni_tiny2350']:
    FEATURES.append('RP2350') # Can use capacity and features of RP2350 chip.
else:
    FEATURES.append('RP2040') # Restrict to capacity and features of RP2040 chip.
if 'pimoroni_tiny' in board.board_id: # We have a Pimoroni Tiny family microcontroller.
    FEATURES.append('TINY')
elif 'raspberry_pi_pico' in board.board_id: # We have a Raspberry Pi Pico family microcontroller.
    FEATURES.append('PICO')
# FEATURES.append('VMOT') # This turns the free ADC0 pin on the Tiny into a measure of the motor power voltage.

print("FEATURES:",FEATURES)

if 'RP2350' in FEATURES:
    # Before initializing any communications, change the clock frequency.
    import microcontroller
    temp = microcontroller.cpu.frequency
    microcontroller.cpu.frequency = 200000000 # Set to 200MHz (default 150MHz on Tiny2350)
    print("Set clock frequency on",board.board_id,
          "from:",(temp / 1e6),"MHz",
          "to:",(microcontroller.cpu.frequency / 1e6),"MHz")
    
    def ns_sleep(delay=1.0):
        """ Provide a SLEEP function which supports pauses less than 1 millisecond.
            Standard time.sleep() does not seem to work below 1 millisecond.
            at 200MHz this can achieve delays down to 0.00022 seconds. 5 times shorter than time.sleep() """
        if delay < 0.001: # Very short delays don't work with the standard function.
            t1 = time.monotonic_ns() + (delay * 1e9) # When does the delay expire?
            while time.monotonic_ns() < t1:
                pass # Loop until clock reaches the set time.
        else: # Millisecond and above delays can use standard function.
            time.sleep(delay) 
        return True

class GPIOpin():

    PinList = [] # Maintain a list of all defined pins.
    
    def __init__(self,pin,name=None):
        print("GPIOpin: Initializing pin",pin,name)
        self.Pin = digitalio.DigitalInOut(pin)
        self.PinNumber = pin
        self.Name = name
        self.PrevValue = self.GetValue()
        GPIOpin.PinList.append(self) # Add this pin to the list of defined pins. 

    def SetDirection(self,direction):
        self.Pin.direction = direction
        if direction == digitalio.Direction.OUTPUT: self.Pin.value = False # turn off.

    def SetValue(self,value):
        if self.Pin.direction == digitalio.Direction.OUTPUT: self.Pin.value = value

    def GetValue(self):
        return self.Pin.value
    
    def High(self):
        return self.GetValue()
    
    def Low(self):
        return not self.GetValue()
    
    def Pressed(self):
        """ Return TRUE if the pin has just gone HIGH else FALSE. """
        result = False
        if self.Pin.value != self.PrevValue:
            if self.Pin.value: # Gone HIGH.
                result = True
            self.PrevValue = self.Pin.value
        return result            

    def Released(self):
        """ Return TRUE if the pin has just gone LOW else FALSE. """
        result = False
        if self.Pin.value != self.PrevValue:
            if not self.Pin.value: # Gone LOW.
                result = True
            self.PrevValue = self.Pin.value
        return result            

class led():
    def __init__(self,pin,state=False):
        """ Tiny RGB LED on/off state is inverted!
            ie to turn LED ON, pin must go LOW.
               to turn LED OFF, pin must go HIGH. """
        self.Led = digitalio.DigitalInOut(pin)
        self.Led.direction = digitalio.Direction.OUTPUT
        self.Led.value = None # Off
        self.Enabled = True # Set to FALSE to turn off the LED completely.
        if state: self.On()
        else: self.Off()

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
        if self.Enabled: self.Led.value = False
        else: self.Led.value = True

    def Off(self):
        """ Turn the LED OFF.
            NOTE: Tiny RGB LED uses opposite pin state to control LED. """
        self.Led.value = True

class statusled():
    """ Pimoroni Tiny RGB LED version of RGB LED handling.
        The RGB LED is a collection of three led() objects. """
    def __init__(self):
        # Raspberry Pi Pico & Pico 2
        #self.LedR = led(board.GP18) # LED_R) # Create LED for RED channel.
        #self.LedG = led(board.GP19) # LED_G) # Create LED for GREEN channel.
        #self.LedB = led(board.GP20) # LED_B) # Create LED for BLUE channel.
        # Pimoroni Tiny...
        self.LedR = led(board.LED_R) # Create LED for RED channel.
        self.LedG = led(board.LED_G) # Create LED for GREEN channel.
        self.LedB = led(board.LED_B) # Create LED for BLUE channel.
        self.TaskList = {'idle': (False,False,False), # Off
                         'coms': (False,False,True), # Blue - Flashes when handling UART
                         'move': (False,True,False), # green - Flashes when motor is moving.
                         'error': (True,False,False), # Red - Indicates failure/fault.
                         'init': (False,True,True)} # cyan - System is initializing.
        self.Enabled = True # If set to FALSE, the LED is permanently off except for ERROR conditions.
        self.StatusExpiry = 0 # microsecond count when any error status can be cleared.
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
        ms = int(time.monotonic_ns() / 1e9) # Seconds timer. Reduce by 1.0e9 to get seconds.
        if ms < self.StatusExpiry: # Error code is still valid. No other setting can be used yet.
            pass
        elif self.Enabled or task == ErrorTask: # No current ERROR status, so we can consider whether to set the new status.
            if task == ErrorTask: # Setting a new error status. Set the timeout for 1 second ahead.
                self.StatusExpiry = ms + 1 # Set 1 second expiry on error codes.
            if task in self.TaskList: # Pull the color codes for the selected task.
                t = self.TaskList[task]
                if t[0]: self.LedR.On()
                else: self.LedR.Off()
                if t[1]: self.LedG.On()
                else: self.LedG.Off()
                if t[2]: self.LedB.On()
                else: self.LedB.Off()
            else: # If the task is not recognised, the LEDs are turned off.
                self.LedR.Off()
                self.LedG.Off()
                self.LedB.Off()
        else: # LED is disabled for everything except ERRORS
            self.LedR.Off()
            self.LedG.Off()
            self.LedB.Off()
            
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
        if lli > 3 and lineitems[3] == 'y': self.LedR.On()
        else: self.LedR.Off()
        if lli > 4 and lineitems[4] == 'y': self.LedG.On()
        else: self.LedG.Off()
        if lli > 5 and lineitems[5] == 'y': self.LedB.On()
        else: self.LedB.Off()
        if lli > 6: 
            self.StatusExpiry = int(time.monotonic_ns() / 1e9) + int(lineitems[6]) # Set expiry on the LED color.

StatusLed = statusled()
StatusLed.Task('init') # System is initializing...
time.sleep(1)

class exceptioncounter():
    """ Keep a count of how many exceptions have been raised during operation. 
        All exceptions should be reported back to the RPi in the log messages
        however a simple counter also ensures we know when things are having
        problems. Implemented as a class so that it can be called consistently
        from inside other methods and objects. 
        This will also automatically set the LED to the error color. """
    def __init__(self):
        self.Count = 0 # Initialize the counter. 

    def Reset(self):
        """ Reset the exception count. """
        self.Count = 0 # Initialize the counter.
        
    def Raise(self):
        try:
            self.Count += 1 # Increment the count. 
            StatusLed.Task('error') # Set the LED to show an error was trapped.
            print("Exception trapped.")
        except Exception as e:
            print("exceptioncounter.Raise() failed:",str(e))

ExceptionCounter = exceptioncounter() # Create instance.
# Increment exception count with ExceptionCounter.Raise()
# Reset with ExceptionCounter.Reset()

DegreeSymbol = 'deg'

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

print("Base clock:",IntToTimeString(time.time()))

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

SessionTimer = timer('session',30,offset=7)

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
        self.Lines = []
        self.BufferSize = 0
        self.MaxLines = 20 # Do not store more than 20 lines due to memory constraints.
        self.Overflows = 0 # How many times has the buffer filled?

    def Log(self,line,*args):
        """ Accept any number of arguments, convert them into a single log file message. """
        for x in args:
            if type(x) == type(str): a = x
            else: a = str(x) # Convert all additional items to strings and append them.
            line = (line + ' ' + a).strip()
        if self.Clock == None:
            line = IntToTimeString(time.time()) + ":" + line + '\n'
        else:
            line = IntToTimeString(self.Clock.Now()) + ":" + line + '\n'
        if len(self.Lines) < self.MaxLines:
            self.Lines.append(line)
            self.BufferSize += len(line)
        else:
            print("logfile.Log: Buffer is full. log message ignored until cleared.")
            self.Overflows += 1
            print("logfile.Log: Memory available",gc.mem_free(),"bytes.")

    def SendAll(self):
        """ Call this to send ALL the outstanding log entries. """
        for line in self.Lines:
            RPi.Write('log :' + line,log=False)
        self.Lines = []
        self.BufferSize = 0

    def SendOne(self):
        """ Call this to send a single log entry if the microcontroller is idle. """
        if len(self.Lines) > 0:
            line = self.Lines.pop(0)
            tottemp = 0
            for line in self.Lines: tottemp += len(line)
            self.BufferSize = tottemp
            RPi.Write('log :' + line,log=False)

    def SendCheck(self,force=False):
        """ If local buffer is large enough, send it to the host
            and reset ready for new messages. """
        if self.BufferSize > 80 or force:
            self.SendAll()

LogFile = logfile()

class uarthost():
    """ UART serial communication handler.
        Handles buffering of received and transmitted data over serial line. """
    def __init__(self,name=None,channel=0):
        print(dir(board))
        if name == None: name = 'UART' + str(channel) # Default to useful name.
        if channel == 0: # UART0
            self.uart = busio_UART(board.GP0,board.GP1,baudrate=115200,receiver_buffer_size=1024,timeout=0) # Define UART0 as the serial comms channel to the host.
            print ('UART TX=', board.GP0, 'UART RX=', board.GP1)
        else: # UART1
            raise Exception('uarthost on Tinyxxxx not configued for UART channel 1. Use channel 0 only.')
            # Don't increment exception count because we quit here. No communication can be established if this fails.
            # We can quit here because without a UART channel there's no way to report the error back to the RPi.
        self.WriteChunk = 32 # 32 seems OK on Circuitpython.
        self.ReceivedLines = [] # No lines received yet.
        self.LinesRead = 0 # total number of lines received.
        self.CharactersRead = 0 # Total number of characters received.
        self.LinesWritten = 0 # Total number of lines sent.
        self.PicoRxErrors = 0 # How many checksum rejections occurred with received data?
        self.CharactersWritten = 0 # total number of characters sent.
        self.StartTime = time.time()
        self.WriteGapms = 100 # ms pause between each chunk of data written.
        self.Name = name
        self.ReceivingLine = '' # Current line being received. It's constructed here until '\n' received.
        self.WriteQueue = [] # List of queued messages to be sent when safe.
        self.WriteDrops = 0 # Number of messages dropped because queue filled.
        self.ReadDrops = 0 # How many received messages are dropped because input buffer is full?
        self.LastTxms = self.LastRxms = self.ticks_ms() # Milliseconds since last transmission.
        print (self.Name, self.uart)

    def Reset(self):
        """ Reset communications (flush output buffers). """
        self.WriteQueue = [] # Empty the write queue.
        self.ReceivedLines = [] # Empty the input queue.
        ExceptionCounter.Reset() # Reset the ExceptionCounter also.
        for i in range(2): self.Write('#' * 20) # Send dummy lines through the UART line to flush out any junk.
        self.Write('# CP env ' + str(Bootline) + ' ver ' + str(CircuitPythonVersion))
        self.Write('# CP mem alloc ' + str(gc.mem_alloc()) + ' free ' + str(gc.mem_free()))
        self.Write('# FEATURES ' + str(FEATURES))
        self.Write('controller started') # Tell the remote device we're up and running.
        self.Write('controller version ' + str(VERSION)) # Tell the remote device which software version is running.
        
    def ticks_ms(self):
        """ Standardise result of CircuitPython and MicroPython CPU ticks value. """
        return int(time.monotonic_ns() / 1e6) # Nano seconds. Reduce by 1.0e6 to get milliseconds (as integer).

    def CalculateChecksum(self,line):
        """ Simple checksum calculation. """
        cs = ""
        a = 0
        if len(line) > 0:
            for i in range(len(line)):
                if i % 2 == 0: a += ord(line[i])
                else: a += ord(line[i]) * 3
        cs = str(hex(a % 65536))[2:]
        return cs

    def AddChecksum(self,line):
        return line + '|' + self.CalculateChecksum(line)

    def RemoveChecksum(self,line):
        if '|' in line:
            l = line.split('|')
            line = l[0]
        return line

    def ValidateChecksum(self,line):
        """ Returns FALSE if checksum MISSING or INVALID.
            Returns TRUE if checksum EXISTS and is VALID. """
        result = False
        if '|' in line:
            l = line.split('|')
            if l[1] == self.CalculateChecksum(l[0]):
                result = True
        return result

    def RxWaiting(self):
        """ Return True if something in the Rx buffer.
            Standardises CircuitPython and MicroPython methods. """
        result = False
        if self.uart.in_waiting > 0: result = True
        return result

    def BufferInput(self):
        """ Read of UART serial port. For circuitpython 8 and later.
            Completed lines are added to the ReceivedLines list and
            are available to the rest of the program. """
        LoopCounter = 0
        while self.RxWaiting(): # Input waiting in Rx buffer.
            StatusLed.Task('coms')
            LoopCounter += 1
            CharsToProcess = '' # No characters to process yet.
            if LoopCounter > 20: break # Max 20 reads performed per call.
            try:
                bchar = self.uart.read() # Read entire waiting queue.
                CharsToProcess = ''.join([chr(b) for b in bchar]) # Convert to string.
                self.CharactersRead += len(CharsToProcess) # Count characters read.
            except Exception as e:
                LogFile.Log('uarthost.BufferInput: uart.read() or conversion error:', str(e))
                ExceptionCounter.Raise() # Increment exception count for the session.
            # Process each new character in turn.
            if len(CharsToProcess) > 0:
                for cchar in CharsToProcess:
                    self.ReceivingLine += cchar
                    if cchar == '\n': # End of line
                        self.LinesRead += 1
                        if len(self.ReceivingLine) > 0 and self.ReceivingLine[-1] == '\n':
                            line = self.ReceivingLine.strip() # Clear special characters.
                            if len(line) > 0: # Something to process.
                                if len(self.ReceivedLines) < 10: # Only buffer 10 lines, discard the rest. No space!
                                    self.ReceivedLines.append(line) # Add to list of lines to handle.
                                    line = self.RemoveChecksum(line)
                                    report = 'rec: ' + line
                                    print (report) # Report all receipts to serial out.
                                    if line[0] != "#": # Acknowledge receipt of all messages except comments via the log file back to the RPi too.
                                        x = line.split(' ')[-1] # Last entry should be message sequence number.
                                        if x.startswith('['): report = 'rec: ' + x # If we have message sequence number, just report that back to the RPi.
                                        LogFile.Log(report)
                                else:
                                    print('uarthost.BufferInput full. Ignored: ' + line)
                                    self.ReadDrops += 1
                        self.ReceivingLine = '' # Start a new receiving line with the next character received.
            self.LastRxms = self.ticks_ms() # When was last message received?
        StatusLed.Task('idle')
    
    def ReceiveAge(self):
        """ How many ms old is the last receipt? """
        return self.ticks_ms() - self.LastRxms # How old is the last receipt?
        # return LastRecMs

    def RemoveCounter(self,line):
        """ If the line ends with a message counter ('[nnn]') remove it. """
        temp = line.rfind('[')
        if temp >= 0:
            line = line[:temp].strip() # Strip anything after the last '[' character, it's a message count and not data.
        return line

    def Read(self):
        """ Return next available complete received line. """
        # 1st check for new data received on serial port.
        self.BufferInput() # Check UART port.
        line = ''
        while len(line) == 0 and len(self.ReceivedLines) > 0:
            line = self.ReceivedLines.pop(0)
            if self.ValidateChecksum(line): # Checksum is good, trust the line.
                line = self.RemoveChecksum(line)
                line = self.RemoveCounter(line) # Strip any final message count from the end of the line.
            else: # Checksum is bad, reject the line.
                print ('uarthost.Read: Rejected checksum : ' + line)
                LogFile.Log('uarthost.Read: Rejected checksum : ' + line)
                self.PicoRxErrors += 1
                line = ''
        return line

    def WritePoll(self):
        """ Write queued lines to the serial port.
            Clear inbound characters received first! """
        if self.RxWaiting(): # Input waiting to be handled is higher priority.
            return # Something waitint to receive takes priority.
        LastSendMs = self.ticks_ms() - self.LastTxms
        if LastSendMs < self.WriteGapms:
            return # 200ms needed between each transmission.
        if LastSendMs > 30000: # After 30 seconds of silence, send a heartbeat signal.
            self.Heartbeat()
        if len(self.WriteQueue) == 0:
            return # Nothing to send.
        StatusLed.Task('coms')
        if len(self.WriteQueue[0]) > self.WriteChunk: # Pull max 20 chars from write queue.
            line = self.WriteQueue[0][:self.WriteChunk]
            self.WriteQueue[0] = self.WriteQueue[0][self.WriteChunk:]
        else: # Pull the whole remaining line from the queue.
            line = self.WriteQueue.pop(0) + "\n"
        if len(line.strip()) == 0:
            print ('uarthost.WritePoll: ignored null line in WriteQueue.')
        byteline = line.encode('utf-8') # Convert to bytearray.
        self.uart.write(byteline) # Physical write.
        if line[-1] == "\n": self.LinesWritten += 1
        self.CharactersWritten += len(line)
        self.LastTxms = self.ticks_ms()
        StatusLed.Task('idle')

    def Write(self,line,log=True):
        # Add a line to the write queue. It's physically sent separately by WritePoll()
        # It queues a limited number of messages for sending. 
        # After that, the queue only accepts extra messages if force==True.
        # Most communication is self-recovering, so it doesn't usually matter if we have to abandon a
        # message, the message will be raised gain soon.
        line = line.strip() # Clean the line.
        if len(line) > 0:
            while len(self.WriteQueue) >= 20: # Only buffer 20 lines. Save memory.
                self.WriteQueue.pop(1) # Drop the 2nd entry, the first may already be partially transmitted.
                self.WriteDrops += 1
            self.WriteQueue.append(self.AddChecksum(line))
            print ('controller queueing: ' + line)

    def Heartbeat(self):
        """ Send Heartbeat signal to the RPi. """
        self.Write('controller heartbeat ' + IntToTimeString(Clock.Now()) + " on " + IntToTimeString(time.time()))

RPi = uarthost(channel=0) # Create UART serial comms with Raspberry Pi. # Feather RP2040

if 'RP2350' in FEATURES:
    # RP2350 has enough memory for microcontroller related features.
    print ('ResetReason: ' + str(microcontroller.cpu.reset_reason))
        
    def SendCpuStatus():
        """ Report microcontroller condition back to RPi. """
        line = 'cpu status ' + IntToTimeString(Clock.Now()) + ' '
        line += str(microcontroller.cpus[0].reset_reason).split('.')[-1].replace(' ','_') + ' '
        line += str(microcontroller.cpus[0].frequency / 1e6) + ' ' 
        line += '0.0 ' # s/b 'volt: ' + str(microcontroller.cpus[0].voltage) + ', '
        line += str(gc.mem_alloc()) + ' ' + str(gc.mem_free()) + ' '
        line += str(int(microcontroller.cpus[0].temperature)) + ' '
        RPi.Write(line)

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
    def __init__(self,TimeValue=None):
        self.TimeDelta = 0 # Offset from machine clock to current date/time (in seconds).
        self.ClockSynchronised = False # Indicates that the clock is synchronised.
        self.PrevTime = time.time() # Record the initial unmodified time of the clock. Used to detect if machine clock gets updated.
        if type(TimeValue) == type(str):
            self.SetTimeFromString(TimeValue)
        elif type(TimeValue) == type(int):
            self.SetTimeFromInt(TimeValue)
        # Values for the NowDecimal() function which simulates fractions of a second for timestamps. 
        self.CurrTime = time.time() # What's the current integer timestamp?
        self.FirstNS = float(time.monotonic_ns()) # What's the nanosecond count at the start of the timestamp?
        self.MaxDecimal = 0.999999999 # Decimal portion cannot roll into next second.
        # Warn CP times stored as single int. Overflow after YEAR > 2033.
        if time.localtime(time.time())[0] > 2033:
            print("CLOCK WARNING: Potential int overflow after 2033.")

    def UpdateClockFromInt(self,TimeInt):
    
        """ Given any integer timestamp this will compare against the clock
            and update the clock if the new timestamp is AHEAD of the current 
            clock. This increases the accuracy/synchronisation of the clock with the RPi's clock.
            This can be run against any received timestamp to continually improve the clock's time. """
        
        tn = self.Now() # What time does the microcontroller think it is at the moment?
        result = False
        if TimeInt != None and TimeInt > tn: # We can nudge the clock forward, never backwards.
            self.SetTimeFromInt(TimeInt)
            LogFile.Log("UpdateClockFromInt(",IntToTimeString(TimeInt),") replaces",IntToTimeString(tn),"Updated clock.")
            result = True
        return result

    def UpdateClockFromString(self,TimeString):
    
        """ Given any character timestamp this will compare against the clock
            and update the clock if the new timestamp is AHEAD of the current 
            clock. This increases the accuracy/synchronisation of the clock with the RPi's clock.
            This can be run against any received timestamp to continually improve the clock's time.   

            If the microcontroller is connected via USB to Thonny on a remote machine, the machine clock may then
            get synchronised, in which case the TimeDelta value is nolonger needed. """

        result = False
        for a in [' ','.','-',':']:
            TimeString = TimeString.replace(a,"")
        try:
            result = TimeStringToInt(TimeString)
            self.UpdateClockFromInt(result)
        except:
            LogFile.Log("UpdateClockFromString(",TimeString,") failed.")
            ExceptionCounter.Raise() # Increment exception count for the session.
        return result

    def CheckTimeDelta(self,now):
        """ If the basic clock time suddenly jumps, assume that the clock has been synchronised
            in which case clear TimeDelta because it's nolonger needed. """
        if now - self.PrevTime > 3600: # Clock has suddenly jumped an hour or more!
            print("c.CTD: Internal clock may have synchronised. Resetting clock synchronisation.")
            self.TimeDelta = 0
            self.ClockSynchronised = False
            LogFile.Log("CheckTimeDelta(): Internal clock may have synchronised. Resetting clock synchronisation.")
        self.PrevTime = now
        
    def SetTimeFromInt(self,TimeInt):
        """ Set clock offset from an INTEGER TIME. """
        self.TimeDelta = max(TimeInt - time.time(),0) # Time offset is the received time - the realtime clock time. Cannot be negative.
        self.ClockSynchronised = True
        RPi.Write('# Clock now ' + IntToTimeString(self.Now()) + ' timedelta ' + str(self.TimeDelta) + ' seconds.')
        #result = True

    def SetTimeFromString(self,TimeString):
        """ Set clock offset from a CHARACTER TIME. """
        result = False
        for a in [' ','.','-',':']:
            TimeString = TimeString.replace(a,"")
        try:
            result = self.SetTimeFromInt(TimeStringToInt(TimeString))
        except Exception as e:
            LogFile.Log('clock.SetTimeFromString: Invalid timestamp string (', TimeString, ')')
            ExceptionCounter.Raise() # Increment exception count for the session.
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
                self.FirstNS = float(time.monotonic_ns()) # This is the ZERO point for nanoseconds within this second.
                self.CurrTime = self.Now() # The current clock time.
            CurrDecimal = (float(time.monotonic_ns()) - self.FirstNS) / 1e+9 # Elapsed fraction of a second since is started.
        return self.CurrTime, CurrDecimal
        
    def NowString(self):
        """ Return current clock time. As character string. """
        return IntToTimeString(self.Now())

Clock = clock(time.time()) # Simulate RTC
LogFile.Clock = Clock # Tell the LogFile which clock to use.

class trajectorypoint():
    """ An individual segment in a trajectory.
        Each segment is a short straight line path that approximates the arc that
        the target is following. The segment is short enough that it is very
        close to the actual curve that the target follows.
        trajectory yymmddhhmmss motorname start startangle end endangle startpos endpos
             0           1         2         3       4       5       6     7        8  """
    def __init__(self,line):
        """ line = the trajectory entry received from the RPi.

            For backwards compatibility, if the start/end positions are not in the message 
            the values are calculated here instead. """
        # Be sure trajectory details are not corrupted.
        # Don't create the entry if there is any problem with it.
        # The remote server will re-send the record if it doesn't get created this time.
        # trajectory 20210410163444 azimuth 20210410163444 256.57984815616663 20210410163544 256.7949264136615
        lineitems = line.split(' ')
        self.StartTime = TimeStringToInt(lineitems[3])
        self.StartAngle = float(lineitems[4])
        self.EndTime = TimeStringToInt(lineitems[5]) # In the future. Could overflow 'int' eventually and fail somewhere.
        self.EndAngle = float(lineitems[6])
        self.StartPosition = int(lineitems[7])
        self.EndPosition = int(lineitems[8])
        # Store gradient of this segment so we don't have to keep recalculating it later on.
        AngleDelta = self.EndAngle - self.StartAngle
        PositionDelta = self.EndPosition - self.StartPosition
        TimeDelta = self.EndTime - self.StartTime
        if TimeDelta != 0: 
            self.DegreesPerSecond = AngleDelta / TimeDelta
            self.StepsPerSecond = PositionDelta / TimeDelta
        else: 
            self.DegreesPerSecond = 0.0
            self.StepsPerSecond = 0.0
        print("trajectory: Start",self.StartPosition,"end",self.EndPosition,"gradient",self.StepsPerSecond)

    def Printable(self,clock=None):
        """ Generate test printable version of the entry. """
        line = ''
        line += IntToTimeString(self.StartTime) + " "
        line += str(self.StartAngle) + " "
        line += IntToTimeString(self.EndTime) + " "
        line += str(self.EndAngle)
        return line

    def ExpectedPosition(self,timeint=None,timedec=None):
        """ Calculate the expected position based upon this entry.
            If the trajectory point's start time has not yet been reached, 
            we 'loiter' at the start angle. Useful for satellite passes when 
            we need to go to the 'rise' position and wait for it to appear.
            if the trajectory segment has expired, the expected position is the end of the segment. """
        if timeint == None:
            timeint, timedec = Clock.NowDecimal()
        if timeint >= self.EndTime: 
            timeint = self.EndTime # Cannot proceed past the end of the planned trajectory.
            timedec = 0.0
        elif timeint < self.StartTime: 
            timeint = self.StartTime # Cannot extrapolate backwards in time, just hover at the start point.
            timedec = 0.0
        elapsedseconds = timeint - self.StartTime
        position = (float(elapsedseconds) * self.StepsPerSecond) + self.StartPosition
        positiondecimal = (float(timedec) * self.StepsPerSecond)
        positionfinal = int(round(position + positiondecimal,0))
        return positionfinal

class trajectory():
    """ A complete trajectory for a target. Consists of a list of individual segments in sequence. """
    def __init__(self,name):
        self.TrajectoryList = []
        self.Valid = False # Indicates that the trajectory is useable.
        self.MotorName = name # The parent MotorName to match log messages with the parent motor.

    def Clean(self): # Trim expired entries from the trajectory list.
        """ All the entries in Trajectory List should complete in the future. """
        while len(self.TrajectoryList) > 0 and self.TrajectoryList[0].EndTime < Clock.Now():
            LogFile.Log('trajectory.Clean: Expired (', self.MotorName, self.TrajectoryList[0].Printable(), ')')
            #temp = self.TrajectoryList.pop(0) # Remove the first entry from the list, it's not needed anymore.
            _ = self.TrajectoryList.pop(0) # Remove the first entry from the list, it's not needed anymore.
        self.Validate() # Is the trajectory useable?

    def Add(self,line): # Add new entry to the end of the list, any existing entries older than the new entry are trimmed.
        """ Add a new segment to the trajectory path.
            There are protections in this method to ensure that only 1 'latest' entry is added.
            This ensures that if any data is lost in transmission, or if the path is updated
            for any reason that the system is 'self correcting. It does however mean that the
            construction of the trajectory path takes several communication loops from the remote
            host.
            """
        result = False # It failed unless we are certain of success.
        self.Clean()
        lineitems = line.split(' ')
        starttime = TimeStringToInt(lineitems[3])
        # Protect from junk data received over the serial line.
        # The host will send the record again if it fails this time.
        try:
            # The new entry must always be the last one on the list.
            # If there are later entries in the list, remove them, they will be resent by the host.
            while len(self.TrajectoryList) > 0 and starttime <= self.TrajectoryList[-1].StartTime:
                self.TrajectoryList = self.TrajectoryList[:-1] # Remove last list entry, it's being replaced by new values.
            self.TrajectoryList.append(trajectorypoint(line)) # Add new entry to the end of the list.
            result = True # Entry creation was successful.
        except Exception as e:
            LogFile.Log('trajectory.Add(', self.MotorName ,'): ' + str(line) + ': Failed to create new trajectory point: ' + str(e))
            ExceptionCounter.Raise() # Increment exception count for the session.
        self.Validate() # Is the trajectory useable?
        return result

    def Clear(self): # Scrub the entire trajectory list.
        self.TrajectoryList = []
        self.Validate() # Is the trajectory useable?

    def ValidUntil(self):
        """ When does the trajectory list run out?
            The host monitors this value, and sends new entries
            as needed to keep the trajectory valid for the next
            few minutes. """
        if len(self.TrajectoryList) > 0:
            validuntil = self.TrajectoryList[-1].EndTime
        else:
            validuntil = Clock.Now() # Trajectory is empty, so it expires now!
        return validuntil

    def Validate(self):
        """ Update the validity of the trajectory.
            True means the ExpectedPosition() method can be trusted.
            False means it's not valid yet. """
        self.Valid = False
        if self.ValidUntil() > Clock.Now(): # Trajectory valid.
            self.Valid = True

    def EndAngle(self):
        """ What is the final rest angle of the trajectory so far?"""
        result = None
        if len(self.TrajectoryList) > 0:
            result = self.TrajectoryList[-1].EndAngle
        return result

    def ExpectedPosition(self):
        """ What is the current expected position of the motor based upon
            the trajectory list contents?
            If the last entry has expired, this will continue following
            that path in the hope that it gets updated soon. """
        self.Clean() # Make sure the list is up to date.
        # Calculate the angle that the motor should be at right now.
        if len(self.TrajectoryList) > 0:
            result = self.TrajectoryList[0].ExpectedPosition()
        else:
            result = None # No angle set yet.
        return result

if 'VMOT' in FEATURES:
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

class steppermotor():
    """ Handler for a NEMA17 stepper motor with DRV8825 driver chip. """
    def __init__(self,name):
        self.MotorName = name
        self.DriverType = 'drv8825'
        self.Trajectory = trajectory(name)
        self.MotorEnabled = False
        self.CurrentPosition = None
        self.TargetPosition = None
        self.MotorConfigured = False
        self.FaultSensitive = False # Set to TRUE to monitor the 'fault' pin on the DRV8825 chip.
        self.FaultDetected = False # Latch to indicate we've already reported a fault with the DRV8825. Otherwise we overflow the UART comms buffer with warnings.
        self.SendStatus = True # Set to FALSE to disable status messages while downloading batches of data (eg Trajectories)
        self.StatusTimer = timer(name,10) # Set up an internal timer for sending status messages every 10 seconds. Can we overridden by RPi.
        self.FastTime = 0.0005 # The fastest pulse time for moving the motor.
        self.SlowTime = 0.05 # The slowest pulse time for moving the motor.
        self.DeltaTime = 0.003 # The acceleration amount moving from SlowTime to FastTime as the motor gets going.
        self.WaitTime = self.SlowTime # The time between pulses, starts slow, reduces as a move progresses. Resets every time a new target is set.
        self.Orientation = 1 # 1=Fwd, -1=Bkwd. This sets the overall orientation of motion. Compensate for gearing reversing the direction of motion here! It's applied to the DirectionBCM pin when the move is made.
        self.StepDir = 1 # The direction of a particular move +/-1. It always represents a SINGLE FULL STEP.
        self.LastStepDir = 0 # Record the 'last' direction that the motor moved in. Useful for handling gear backlash and handling rotation limits. Starts at ZERO (No direction)
        self.BacklashAngle = 0.0 # This is the angle the motor must move to overcome backlash in the gearing when changing direction.
        self.DriftSteps = 0 # This is the number of steps 'error' that DriftTracking has identified. It must be incorporated back into motor movements as smoothly as possible. Consider backlash etc.
        self.MotorStepsPerRev = None
        self.MicrosteppingMode0 = False # Mode0 pin setting when microstepping.
        self.MicrosteppingMode1 = False
        self.MicrosteppingMode2 = False
        self.SlewStepMultiplier = 1 # The number of steps/microsteps taken when making large SLEW moves.
        self.SlewMotor = False # Allow the motor to make faster full-step (but less precise) moves when slewing the telescope large angles.
        self.SlewMode0 = False # Move0 pin setting when taking full steps in a large slew movement.
        self.SlewMode1 = False
        self.SlewMode2 = False
        self.GearRatio = None # gearratio is the overall gearing of the entire transmission. 60 means 60 motor revs for 1 transmission rev.
        self.AxisStepsPerRev = None
        self.MinAngle = None # Max anticlockwise movement.
        self.MaxAngle = None # Max clockwise movement.
        self.MinPosition = None # Min clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.MaxPosition = None # Max clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.RestAngle = None # The 'rest' position of the axis. Used for calibrating at startup. Typically DUE SOUTH or HORIZONTAL position of the axis.
        self.RestPosition = None
        # Limit position. This is not the position of a Limit switch, it is a rotation limit to prevent excessive cable twisting.
        self.LimitPosition = None # If given, this is the limit of movement. The telescope will reverse around this rather than cross it.
        self.RequestedPosition = None
        # Set up control pins for the motor.
        # If we're using the same pins to drive multiple motors you may get some warnings from GPIO.
        # If the program has been restarted in the same session, you may get some warnings from GPIO.
        self.StepBCM = None # Set pin to OUTPUT. This sends the MOVE pulse to the controller.
        self.DirectionBCM = None # Set pin to OUTPUT. This sets the MOVE direction to the controller.
        self.Mode0BCM = None # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode1BCM = None # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode2BCM = None # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.EnableBCM = None # Set pin to OUTPUT. This enables/disabled the motor.
        self.FaultBCM = None # Set pin to INPUT. Will EARTH when triggered.
        # The following items just need allocating, the self.Reset() call will set the values.
        self.OnTarget = False # Indicates that the motor is on target. This will control Observable status.
        self.LatestTuneSteps = 0 # Record details of the last tune command received. So we can see it was handled.
        self.LatestTuneTime = None
        # Latest Start/Stop times for config and status methods.
        self.OptimiseMoves = False # When set to TRUE the motor is allowed to take a short-cut if a requested move is > 50% of the circumference.

    def CheckOnTarget(self):
        """ Set the OnTarget indicator if it looks like we're on-target.
            This means the REQUESTED POSITION = ACTUAL POSITION.
            (Don't use ANGLE because there may be tiny differences) """
        if self.RequestedPosition == None: self.OnTarget = False
        elif self.RequestedPosition == self.CurrentPosition: self.OnTarget = True
        else: self.OnTarget = False

    def Reset(self,enable=False):
        """ This resets the status of the motor.
            It does not physically move it, but it disables it, and sets the 'current position' to be the 'home position'.
            This is typically used for manually positioning a motor during initial setup, or for
            clearing the trajectory when selecting a new observation target.
            A fresh configuration will then be required from the RPi.
        """
        print("steppermotor.Reset(): Start")
        LogFile.Log(self.MotorName + ".Reset.")
        self.Trajectory.Clear() # Delete the trajectory completely. We'll be needing a new one.
        if enable: self.EnableMotor() # Leave motor enabled.
        else: self.DisableMotor() # Disable the motor.
        self.OnTarget = False
        self.CurrentPosition = self.RestPosition # Initialise CurrentPosition, we'll set it in next line. This is updated DURING moves too.
        self.TargetPosition = self.RestPosition
        self.RequestedPosition = None
        self.MotorConfigured = False
        self.SendStatus = True 
        self.MotorStepsPerRev = None
        self.MicrosteppingMode0 = False
        self.MicrosteppingMode1 = False
        self.MicrosteppingMode2 = False
        self.SlewStepMultiplier = 1 # The number of steps/microsteps taken when making large SLEW moves.
        self.SlewMotor = False # Allow the motor to make faster full-step (but less precise) moves when slewing the telescope large angles.
        self.SlewMode0 = False # Move0 pin setting when taking full steps in a large slew movement.
        self.SlewMode1 = False
        self.SlewMode2 = False
        self.GearRatio = None # gearratio is the overall gearing of the entire transmission. 60 means 60 motor revs for 1 transmission rev.
        self.AxisStepsPerRev = None        
        print("steppermotor.Reset(): Send status...")
        self.SendMotorStatus(immediate=True,codes='rst')
        print("steppermotor.Reset(): End")
        return True

    def CurrentDegrees(self):
        """ Return CurrentPosition as an angle. """
        if self.AxisStepsPerRev == None:
            cd = None # Cannot calculate until axis configuration is known.
        else:
            cd = 360.0 * (float(self.CurrentPosition) / self.AxisStepsPerRev)
        return cd
        
    def AddTrajectoryPoint(self,entry):
        try:
            self.Trajectory.Add(entry)
        except Exception as e:
            LogFile.Log('steppermotor(' + self.MotorName + ').AddTrajectoryPoint: ' + str(entry) + ': Failed. ' + str(e))
            ExceptionCounter.Raise() # Increment exception count for the session.
        self.SendMotorStatus(immediate=True,codes='atp') # This triggers the next trajectory point faster than waiting for the regular status message will.

    def ClearTrajectory(self):
        """ Remove current trajectory. """
        self.Trajectory.Clear() # Empty the entire trajectory.
        self.SendMotorStatus(immediate=True,codes='clt')

    def Stop(self):
        """ Immediately stop the motor. """
        self.ClearTrajectory()
        self.TargetPosition = self.CurrentPosition
        self.OnTarget = False
        self.RequestedPosition = None
        LogFile.Log('steppermotor.Stop(' + self.MotorName + ')')

    def EnableMotor(self):
        """ This engages current to the motor. It will hold its position now. """
        if self.MotorConfigured:
            self.EnableBCM.SetValue(False) # (1) # Pull pin LOW to enable.
            self.MotorEnabled = True
        else:
            LogFile.Log('steppermotor.EnableMotor: Motor is not configured. Will not enable.')

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
        if self.MotorConfigured:
            print ('GoToAngle: Motor configured')
            LogFile.Log('steppermotor.GoToAngle(' + self.MotorName + ') ' + str(newangle))
            print ('GoToAngle: Stop')
            self.Stop() # Clear any pre-existing trajectory before moving.
            print ('GoToAngle: SetTargetByAngle')
            self.SetTargetByPosition(self.AngleToStep(newangle))
            if self.SlewMotor: # Can use FAST moves for rapid slew.
                print ('GoToAngle: MoveMotorFast')
                self.MoveMotorFast()
                print ('GoToAngle: MoveMotorFast complete.')
            else:
                print ('GoToAngle: MoveMotor')
                self.MoveMotor()
                print ('GoToAngle: MoveMotor complete.')
        else:
            print ('GoToAngle: Motor NOT configured')
            LogFile.Log('steppermotor.GoToAngle(' + self.MotorName + ') Rejected. Motor is not configured.')
            RPi.Write('goto rejected ' + self.MotorName + ' ' + str(newangle) + ' MotorNotConfigured')
        print ('GoToAngle: SendMotorStatus (immediate) gte')
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
                LogFile.Log(self.MotorName + ": SetNewTarget: " + str(newangle) + " exceeds MaxAngle. Limited to: " + str(self.MaxAngle))
                newangle = self.MaxAngle
                newposition = self.AngleToStep(newangle)
                result = False # Set failed.
            if newangle < self.MinAngle:
                LogFile.Log(self.MotorName + ": SetNewTarget: " + str(newangle) + " exceeds MinAngle. Limited to: " + str(self.MinAngle))
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
        print("TargetFromTrajectoryPosition=",targetposition)
        if targetposition != None and self.Trajectory.Valid and self.MotorConfigured: # We can set the target based upon current trajectory.
            result = self.SetTargetByPosition(targetposition)
        else: # Target is just the current position. Config and Trajectory are invalid.
            LogFile.Log('TargetFromTrajectoryPosition',self.MotorName,'not ready. tv,mc,ta=', self.Trajectory.Valid, self.MotorConfigured,targetposition)
        return result

    def TunePosition(self,delta):
        """ Tune the motor position. This shifts the motor, but retains the 'position' calculation unchanged.
            Use this to address positioning errors or drift adjustments. """
        if self.MotorConfigured:
            self.EnableMotor()
            tunestarttime = Clock.Now()
            old = self.CurrentPosition # Store the current position of the motor. We'll restore this when finished.
            new = self.CurrentPosition + delta # Calculate the new target position (fullsteps).
            self.SetTargetByPosition(new,Limit=False) # Set the target in the object. Primes it for the move, No error check on limits.
            LogFile.Log("TunePosition(" + self.MotorName + ") Current:" + str(self.CurrentPosition) + ", NewTarget: " + str(self.TargetPosition))
            self.MoveMotor() # Perform the move.
            self.CurrentPosition = old
            self.TargetPosition = old
            LogFile.Log("TunePosition(" + self.MotorName + ") set to " + str(self.CurrentPosition))
            self.LatestTuneSteps = delta # Record details of the last tune command received. So we can see it was handled.
            self.LatestTuneTime = Clock.Now()
            RPi.Write('tune complete ' + self.MotorName + ' ' + IntToTimeString(self.LatestTuneTime) + ' ' + str(delta) + ' ' + IntToTimeString(tunestarttime))
            self.SendMotorStatus(immediate=True,codes='tup') # Tell RPi latest condition of the motor.
        else:
            RPi.Write('tune rejected ' + self.MotorName + ' ' + IntToTimeString(self.LatestTuneTime) + ' ' + str(delta) + ': Motor not configured')
            LogFile.Log("error : TunePosition(" + self.MotorName + ") Rejected, motor is not yet configured.")

    def SetPins(self,stepBCM,directionBCM,mode0BCM,mode1BCM,mode2BCM,enableBCM,faultBCM):
        """ Allocate pin numbers for the various GPIO pins required. """
        self.StepBCM = stepBCM # Pin(stepBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This sends the MOVE pulse to the controller.
        self.StepBCM.SetValue(False) # (0) # Turn pin off.
        LogFile.Log(self.MotorName, 'Step pin', self.StepBCM.PinNumber)
        self.DirectionBCM = directionBCM # Pin(directionBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This sets the MOVE direction to the controller.
        self.DirectionBCM.SetValue(False) # (0)  # Turn pin off.
        LogFile.Log(self.MotorName, 'Direction pin', self.DirectionBCM.PinNumber)
        self.Mode0BCM = mode0BCM # Pin(mode0BCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode1BCM = mode1BCM # Pin(mode1BCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode2BCM = mode2BCM # Pin(mode2BCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode0BCM.SetValue(False) # (0)  # Turn pin off.
        self.Mode1BCM.SetValue(False) # (0)  # Turn pin off.
        self.Mode2BCM.SetValue(False) # (0)  # Turn pin off.
        self.EnableBCM = enableBCM # Pin(enableBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This enables/disabled the motor.
        self.EnableBCM.SetValue(False) # (0)  # Turn pin off.
        self.FaultBCM = faultBCM # Pin(faultBCM, Pin.IN) # Set pin to INPUT. Will EARTH when triggered.

    def SetConfig(self,gearratio,motorstepsperrev,minangle,maxangle,restangle,currentangle,orientation,backlashangle,modesignals=[False,False,False]):
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
        self.MicrosteppingMode0 = modesignals[0]
        self.MicrosteppingMode1 = modesignals[1]
        self.MicrosteppingMode2 = modesignals[2]
        self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio
        # AngleToStep and StepToAngle only work from here on!
        self.RestPosition = self.AngleToStep(self.RestAngle)
        self.CurrentPosition = self.TargetPosition = self.AngleToStep(currentangle)
        self.MinPosition = self.AngleToStep(self.MinAngle) # Min clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.MaxPosition = self.AngleToStep(self.MaxAngle) # Max clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.RequestedPosition = self.CurrentPosition
        return self.MotorConfigured

    def ConfigureMotor(self,line):
        """ This loads the motor configuration received from the RPi.
            It can override some default values in the configuration.
            All values are optional.
            Any value of 'none' is ignored.

            configure motor 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n  n 90.0 240 400  1 180.0 nnn 1 n nnn
                0       1         2           3       4    5  6   7  8   9     10    11  12 13 14 15   16 17  18 19    20 21 22 23
                
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
                16 = Gear ratio.
                17 = Motor steps per revolution (1 revolution of motor).
                18 = SlewStepMultiplier (number of steps taken with a SLEW move).
                19 = Motor rest angle (when homed).
                20 = Microstepping mode signals (used when making observation).
                21 = SlewMotor flag (Can motor make FULL STEP moves during large position changes). <- Experimental feature.
                22 = Slew stepping mode signals (used when making large position changes). <- Experimental feature.
            """
        try:
            lineitems = line.lower().split(' ')
            lc = len(lineitems)
            Clock.UpdateClockFromString(lineitems[2]) # Check that the clock is as synchronised as possible.
            if lineitems[7] != 'none':
                self.BacklashAngle = float(lineitems[7]) # Set new backlash angle for motor.
            if lineitems[8] != 'none':
                self.Orientation = int(lineitems[8]) # Set new orientation for motor.
            if lineitems[9] != 'none':
                self.FastTime = float(lineitems[9]) # Set new FASTEST PULSE time for motor.
            if lineitems[10] != 'none':
                self.SlowTime = float(lineitems[10]) # Set new SLOWEST PULSE time for motor.
            if lineitems[11] != 'none':
                self.TimeDelta = float(lineitems[11]) # Set new acceleration rate for motor.
            if self.WaitTime < self.FastTime: self.WaitTime = self.FastTime # Current motor speed cannot be faster than new fastest limit.
            if self.WaitTime > self.SlowTime: self.WaitTime = self.SlowTime # Current motor speed cannot be slower than new slowest limit.
            if lineitems[12] != 'none': # Must be within reasonable limits.
                temp = int(lineitems[12])
                if temp < 1: temp = 1
                elif temp > 30: temp = 30
                self.StatusTimer = timer(self.MotorName,temp) # Set new repeat time for sending motor status messages back to the RPi
            if lineitems[13] != 'none': # Enable/disable fault sensitivity. DRV8825 can then abort an observation.
                self.FaultSensitive = StringToBool(lineitems[13])
            if lineitems[14] != 'none': # Enable/disable move optimisation.
                self.OptimiseMoves = StringToBool(lineitems[14])
            if lineitems[16] != 'none': # Define GearRatio.
                self.GearRatio = float(lineitems[16])
            if lineitems[17] != 'none': # Define motorstepsperrev
                self.MotorStepsPerRev = int(lineitems[17])
                self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio
            self.SlewStepMultiplier = int(lineitems[18]) # Number of steps taken with a larget SLEW move (if microstepping in place).
            if lineitems[19] != 'none': # Define restangle
                self.RestAngle = float(lineitems[19])
            # Load mode signals to select full or microstepping ratio.
            temp = lineitems[20] + 'nnn'
            #self.ModeSignals = [StringToBool(temp[0]),StringToBool(temp[1]),StringToBool(temp[2])]
            modesignals = [StringToBool(temp[0]),StringToBool(temp[1]),StringToBool(temp[2])]
            self.MicrosteppingMode0 = modesignals[0] # True or False
            self.MicrosteppingMode1 = modesignals[1]
            self.MicrosteppingMode2 = modesignals[2]
            if lc > 21: # Allow SLEW fast moves.
                self.SlewMotor = StringToBool(lineitems[21]) # Are SLEW fast moves allowed?
            if lc > 22: # Load mode signals to select FULL STEPS when performing large fast slews.
                temp = lineitems[22] + 'nnn'
                modesignals = [StringToBool(temp[0]),StringToBool(temp[1]),StringToBool(temp[2])]
                self.SlewMode0 = modesignals[0] # True or False
                self.SlewMode1 = modesignals[1] # True or False
                self.SlewMode2 = modesignals[2] # True or False
            # Restore min/max/current/limit position only after the MotorStepsPerRev is known, if microstepping has changed above these will be different.
            if lineitems[4] != 'none': # To apply to live copy.
                self.CurrentPosition = self.AngleToStep(float(lineitems[4]))
            if lineitems[5] != 'none':
                self.MinAngle = float(lineitems[5]) # Set new minimum angle for motor.
                self.MinPosition = self.AngleToStep(self.MinAngle)
            if lineitems[6] != 'none':
                self.MaxAngle = float(lineitems[6]) # Set new maximum angle for motor.
                self.MaxPosition = self.AngleToStep(self.MaxAngle)
            # Define movement limit on the motor. The motor will reverse around a limit rather than crossing it.
            if lineitems[15] != 'none': # Set a movement limit.
                limitangle = float(lineitems[15])
                self.LimitPosition = self.AngleToStep(limitangle)
            else:
                self.LimitPosition = None
            self.MotorConfigured = True
        except Exception as e:
            LogFile.Log("steppermotor.ConfigureMotor(line) failed: " + str(e))
            print("steppermotor.ConfigureMotor() failed.")
            ExceptionCounter.Raise() # Increment exception count for the session.
        self.ReportMotorConfig() # Report the configuration back to the RPi.
        return self.MotorConfigured

    def StepMove(self,stepsize=1):
        """ Move the motor one full step. Target must be initialized before calling this.
            This is the 'fast' version of MoveFullStep. With logic rearranged between MoveMotor and MoveFullStep. """
        StatusLed.Task('move') # Flash status LED with motor specific colour.
        if self.MotorEnabled: # If we've disabled the motor, then perform everything except the move pulse.
            self.StepBCM.SetValue(True) # value(1)
            time.sleep(self.WaitTime)
            self.StepBCM.SetValue(False) # value(0)
            time.sleep(self.WaitTime)
        self.CurrentPosition = (self.CurrentPosition + (self.StepDir * stepsize)) % self.AxisStepsPerRev
        # Accelerate the motor.
        if self.WaitTime > self.FastTime: # We can still accelerate
            self.WaitTime = max(self.WaitTime - self.DeltaTime, self.FastTime)

    def InvertSteps(self,motorsteps):
        """ Given a number of steps to move, return the inverse move. """
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
            LogFile.Log("steppermotor.EfficiencyCheck(): Inefficient move:",self.CurrentPosition,"to",self.TargetPosition,",",motorsteps,"steps, suggest",inversemove)
            print("Inefficient move:",self.CurrentPosition,"to",self.TargetPosition,",",motorsteps,"steps, suggest",inversemove)
        return inversemove

    def MoveMotorFast(self):
        """ Move the motor to the new target position.
            If the SlewMotor parameter is True, then this can use FULL STEPS to speed things up in the middle of large moves.
            This moves the telescope faster when using very fine microstepping.
            This moves to a 'full step' boundary on the motor, then switches to FULL STEP movements until close to the target.
            When close to the target it reverts to microstepping for fine tuning.
            Target must be defined before calling this.
            Large moves can take some time, so UART communication is maintained during moves.
            The motor will generally take the shortest path to the target position.
            It may take the longer route under some circumstances. (LimitPosition must not be crossed etc.) """
        MotorSteps = self.TargetPosition - self.CurrentPosition # How many steps to take?
        if self.OptimiseMoves: # Allowed to find shorter paths!
            inversemove = self.EfficiencyCheck(MotorSteps) # Check if this is the most efficient move.
            if inversemove != MotorSteps: # We're changing direction for a short cut.
                MotorSteps = inversemove
                print("steppermotor.MoveMotorFast moving",MotorSteps,"steps after efficiency check.")
                self.StepDir *= -1
        else: # Must move as instructed, but can report if a shorter path exists.
            _ = self.EfficiencyCheck(MotorSteps) # Check if this is the most efficient move.
        if MotorSteps != 0:
            StatusLed.Task('move') # Flash status LED with motor specific colour.
            if abs(MotorSteps) > 100: # Large moves will reset the 'OnTarget' flag.
                self.OnTarget = False
        if self.FaultBCM.GetValue() == False: # DRV8825 'fault' pin is triggered.
            if self.FaultSensitive: # The fault matters.
                if not self.FaultDetected:
                    print("Setting FAULT status.")
                    self.FaultDetected = True
                    LogFile.Log("steppermotor.MoveMotorFast(", self.MotorName, ') DRV8825 fault - terminating.')
                return
            else: # The fault does not matter.
                if not self.FaultDetected: # Only report once.
                    LogFile.Log("steppermotor.MoveMotorFast(", self.MotorName, ') DRV8825 fault - ignored.')
                    print("Setting FAULT status.")
                    self.FaultDetected = True
        else: # No DRV8825 fault, clear any previous fault status.
            if self.FaultDetected: 
                LogFile.Log("steppermotor.MoveMotorFast(", self.MotorName, ') DRV8825 fault - cleared.')
                self.FaultDetected = False # No fault.
        if abs(self.StepDir) != 1: # self.StepDir must be +1 or -1
            LogFile.Log('MoveMotorFast: ' + self.MotorName + ' StepDir " + str(self.StepDir) + " is invalid. Must be +/-1')
            return
        if (self.StepDir * self.Orientation) > 0:
            self.DirectionBCM.SetValue(True) # value(1) # Move motor forward.
        else:
            self.DirectionBCM.SetValue(False) # value(0) # Move motor backwards.
        if self.StepDir != self.LastStepDir: # We have a change of direction.
            LogFile.Log('MoveMotorFast: ' + self.MotorName + ' changed direction (' + str(self.StepDir) + ' vs ' + str(self.LastStepDir) + '). Backlash?')
        self.LastStepDir = self.StepDir # Record the direction that the motor is moving in. This may be useful for handling gear backlash etc.
        if self.SlewMotor: # We're allowed to make FAST moves using FULL STEPS if there's a long way to go.
            targettolerance = 100 * self.SlewStepMultiplier # This is as close as we want to get with large slew moves. Finetuning is done with MoveMotor() afterwards.
            # Set microstepping mode.
            self.Mode0BCM.SetValue(self.MicrosteppingMode0) 
            self.Mode1BCM.SetValue(self.MicrosteppingMode1) 
            self.Mode2BCM.SetValue(self.MicrosteppingMode2) 
            self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
            while MotorSteps != 0:
                if self.CurrentPosition % self.SlewStepMultiplier == 0: # On FULLSTEP boundary. Switch to FULL STEPS.
                    break
                MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
                self.StepMove(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
                self.SendMotorStatus(codes='mov') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
                for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                    RPi.BufferInput() # Keep polling for input from the RPi.
                    RPi.WritePoll() # Keep sending data to RPi.
            # Set slew (full stepping) mode.
            self.Mode0BCM.SetValue(self.SlewMode0) 
            self.Mode1BCM.SetValue(self.SlewMode1) 
            self.Mode2BCM.SetValue(self.SlewMode2) 
            self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
            while MotorSteps != 0:
                if abs(self.TargetPosition - self.CurrentPosition) <= targettolerance: # We've got close with FULLSTEPS, switch back to microsteps.
                    break
                MotorSteps = (MotorSteps - (self.StepDir * self.SlewStepMultiplier)) # REDUCE (-ve) the number of steps to take.
                self.StepMove(stepsize=self.SlewStepMultiplier) # This will update CurrentPosition on-the-fly as the motor moves.
                self.SendMotorStatus(codes='mov') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
                for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                    RPi.BufferInput() # Keep polling for input from the RPi.
                    RPi.WritePoll() # Keep sending data to RPi.
        # Set microstepping mode. Regardless of 'slew' mode or not, now use configured microstepping to complete the move.
        self.Mode0BCM.SetValue(self.MicrosteppingMode0) 
        self.Mode1BCM.SetValue(self.MicrosteppingMode1) 
        self.Mode2BCM.SetValue(self.MicrosteppingMode2) 
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
        while MotorSteps != 0:
            MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
            self.StepMove(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
            self.SendMotorStatus(codes='mov') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
            for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                RPi.BufferInput() # Keep polling for input from the RPi.
                RPi.WritePoll() # Keep sending data to RPi.
        self.CheckOnTarget() # Are we actually pointing at the target?
        if self.CurrentPosition != self.TargetPosition: # Did the motor slew close to the intended position? (May not be the requested target if movement limits reached)
            LogFile.Log("MoveMotorFast(" + self.MotorName + "): End. CurrentPosition (" + str(self.CurrentPosition) + ") is NOT TargetPosition (" + str(self.TargetPosition) + ")!")
        StatusLed.Task('idle')

    def MoveMotor(self):
        """ Move the motor to the new target position. Target must be defined before calling this.
            This is intended to move the motor only small distances. It only uses the defined microstepping speed.
            Large moves can take some time, so UART communication is maintained during moves.
            The motor will generally take the shortest path to the target position.
            It may take the longer route under some circumstances. (LimitPosition must not be crossed etc.) """
        MotorSteps = self.TargetPosition - self.CurrentPosition # How many steps to take?
        if self.OptimiseMoves: # Allowed to find shorter paths!
            inversemove = self.EfficiencyCheck(MotorSteps) # Check if this is the most efficient move.
            if inversemove != MotorSteps: # We're changing direction for a short cut.
                MotorSteps = inversemove
                print("steppermotor.MoveMotor moving",MotorSteps,"steps after efficiency check.")
                self.StepDir *= -1
        else: # Must move as instructed, but can report if a shorter path exists.
            _ = self.EfficiencyCheck(MotorSteps) # Check if this is the most efficient move.
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call StepMove().
        if MotorSteps != 0:
            StatusLed.Task('move') # Flash status LED with motor specific colour.
            if abs(MotorSteps) > 100: # Large moves will reset the 'OnTarget' flag.
                self.OnTarget = False
        if self.FaultBCM.GetValue() == False: # DRV8825 'fault' pin is triggered.
            if self.FaultSensitive: # The fault matters.
                if not self.FaultDetected:
                    print("Setting FAULT status.")
                    self.FaultDetected = True
                    LogFile.Log("steppermotor.MoveMotor(", self.MotorName, ') DRV8825 fault - terminating.')
                return
            else: # The fault does not matter.
                if not self.FaultDetected: # Only report once.
                    LogFile.Log("steppermotor.MoveMotor(", self.MotorName, ') DRV8825 fault - ignored.')
                    print("Setting FAULT status.")
                    self.FaultDetected = True
        else: # No DRV8825 fault, clear any previous fault status.
            if self.FaultDetected: 
                LogFile.Log("steppermotor.MoveMotor(", self.MotorName, ') DRV8825 fault - cleared.')
                self.FaultDetected = False # No fault.
        if abs(self.StepDir) != 1: # self.StepDir must be +1 or -1
            LogFile.Log('MoveMotor: ' + self.MotorName + ' StepDir " + str(self.StepDir) + " is invalid. Must be +/-1')
            return
        if (self.StepDir * self.Orientation) > 0:
            self.DirectionBCM.SetValue(True) # value(1) # Move motor forward.
        else:
            self.DirectionBCM.SetValue(False) # value(0) # Move motor backwards.
        if self.StepDir != self.LastStepDir: # We have a change of direction.
            LogFile.Log('MoveMotor: ' + self.MotorName + ' changed direction (' + str(self.StepDir) + ' vs ' + str(self.LastStepDir) + '). Backlash?')
        self.LastStepDir = self.StepDir # Record the direction that the motor is moving in. This may be useful for handling gear backlash etc.
        # Set microstepping mode.
        self.Mode0BCM.SetValue(self.MicrosteppingMode0) 
        self.Mode1BCM.SetValue(self.MicrosteppingMode1) 
        self.Mode2BCM.SetValue(self.MicrosteppingMode2) 
        while MotorSteps != 0:
            MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
            self.StepMove(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
            self.SendMotorStatus(codes='mov') # Long slow moves would cause RPi to trigger a reset and the user won't see progress until the end, so send regular status updates.
            for i in range(1): # Check UART buffers. Can loop multiple times if you want to, but it pauses movement while checking.
                RPi.BufferInput() # Keep polling for input from the RPi.
                RPi.WritePoll() # Keep sending data to RPi.
        self.CheckOnTarget() # Are we actually pointing at the target?
        if self.CurrentPosition != self.TargetPosition: # Did the motor reach intended position? (May not be the requested target if movement limits reached)
            LogFile.Log("MoveMotor(" + self.MotorName + "): End. CurrentPosition (" + str(self.CurrentPosition) + ") is NOT TargetPosition (" + str(self.TargetPosition) + ")!")
        StatusLed.Task('idle')

    def StepToAngle(self, steps=None):
        """ Convert a number of steps to a final angle (0-360) of movement. """
        if steps != None:
            result = steps * 360.0 / float(self.AxisStepsPerRev)
        else:
            result = None
        return result

    def AngleToStep(self, deg=None):
        """ Convert a final angle of movement to the nearest whole number of motor steps. """
        if deg != None:
            result = int(round(deg * float(self.AxisStepsPerRev) / 360,0))
        else:
            result = None
        return result

    def ReportMotorConfig(self):
        """ Report motor configuration back to the RPi. """
        line = "# Motor " + self.MotorName + " conf 1: "
        line += IntToTimeString(Clock.Now()) + " " 
        line += "MinA " + str(self.MinAngle) + " " 
        line += "MinP " + str(self.MinPosition) + " " 
        line += "MaxA " + str(self.MaxAngle) + " " 
        line += "MaxP " + str(self.MaxPosition) + " " 
        line += "LimP " + str(self.LimitPosition) + " " 
        line += "RestA " + str(self.RestAngle) + " " 
        RPi.Write(line) # Send over UART to RPi.
        line = "# Motor " + self.MotorName + " conf 2: "
        line += "FastT " + str(self.FastTime) + " " 
        line += "SlowT " + str(self.SlowTime) + " " 
        line += "TDelta " + str(self.TimeDelta) + " " 
        line += "FaultS " + str(self.FaultSensitive) + " " 
        line += "BackA " + str(self.BacklashAngle) + " " 
        line += "Orient " + str(self.Orientation) + " " 
        line += "OptMvs " + str(self.OptimiseMoves) + " " 
        RPi.Write(line) # Send over UART to RPi.
        line = "# Motor " + self.MotorName + " conf 3: "
        line += "GearRat " + str(self.GearRatio) + " " 
        line += "uS/Rev " + str(self.MotorStepsPerRev) + " " 
        line += "usMode " + BoolToString(self.MicrosteppingMode0) + BoolToString(self.MicrosteppingMode1) + BoolToString(self.MicrosteppingMode2) + " " # Microstepping mode pin settings. 
        line += "AxStp/Rev " + str(int(self.AxisStepsPerRev)) + " "
        line += "MtrCnf " + str(self.MotorConfigured) + " " 
        RPi.Write(line) # Send over UART to RPi.
        
    def SendMotorStatus(self,immediate=False,codes='?-?'):
        """ Generate status message to RPi.
            The RPi uses this to decide what commands and configurations to send to the microcontroller.
            This can be triggered via multiple methods and in some circumstances can flood the RPi with
            messages. So there is a maximum repeat rate built in.
            immediate: True means that the status is sent even if not due.
                       False means that the status is only sent if the timer is due.
            codes: Optional string of codes that are added to the status message. (Debug/test/dev etc)
            """
        if immediate or self.StatusTimer.Due(): # Only send the status at regular intervals, otherwise we flood communications.
            if self.SendStatus == False: # Status message is currently disabled. Inform that we're not sending it.
                RPi.Write('# SendMotorStatus ' + IntToTimeString(Clock.Now()) + ' ' + self.MotorName + ' disabled. ' + str(codes))
                print("SendMotorStatus",self.MotorName,"disabled.",codes)
                return
            line = 'motor status '
            line += IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
            line += self.MotorName + ' '
            line += BoolToString(self.Trajectory.Valid) + ' ' # TrajectoryValid
            line += IntToTimeString(self.Trajectory.ValidUntil()) + ' ' # When does the trajectory run out?
            line += str(len(self.Trajectory.TrajectoryList)) + ' ' # How many segments in the trajectory?
            line += str(self.CurrentPosition) + ' ' # Where is the camera at the moment?
            line += str(self.CurrentDegrees()) + ' ' # Where is the camera at the moment?
            line += BoolToString(self.MotorConfigured) + ' ' # MotorConfigured
            line += BoolToString(self.OnTarget) + ' ' # Motor is on target or not.
            line += str(self.WaitTime * 2) + ' ' # The pulse period (indicates speed) of the motor.
            if 'VMOT' in FEATURES:
                line += str(VMot()) + ' ' # ADC0 is measuring motor voltage. Send the current ADC value.
            else:
                line += '0 ' # Measure the motor power voltage from ADC0. Will return '0' if adc0 is not configured as an 'adc' input. Nolonger supported.
            line += str(codes) + ' ' # Optional codes added to status message.
            RPi.Write(line) # Send over UART to RPi.
            # Reset the status timer.
            self.StatusTimer.Reset() # We've sent the regular status message, decide when the next is due.

# Define pins for motorcontroller chips.
AzimuthStepBCM = GPIOpin(board.GP29,'azstep') # Tiny RP2040
#AzimuthStepBCM = GPIOpin(board.VBUS_SENSE,'azstep') # Raspberry Pi Pico & Pico 2 - Doesn't work right.
AltitudeStepBCM = GPIOpin(board.GP28,'altstep') # Tiny RP2040
CommonDirectionBCM = GPIOpin(board.GP27,'dir') # Tiny RP2040
CommonMode0BCM = GPIOpin(board.GP3,'mode0') # Tiny RP2040
CommonMode1BCM = GPIOpin(board.GP4,'mode1') # Tiny RP2040
CommonMode2BCM = GPIOpin(board.GP5,'mode2') # Tiny RP2040
CommonEnableBCM = GPIOpin(board.GP2,'enable') # Tiny RP2040
AzimuthFaultBCM = GPIOpin(board.GP6,'azfault') # Tiny RP2040
AltitudeFaultBCM = GPIOpin(board.GP7,'altfault') # Tiny RP2040

AzimuthStepBCM.SetDirection(digitalio.Direction.OUTPUT)
AzimuthStepBCM.SetValue(False)
AltitudeStepBCM.SetDirection(digitalio.Direction.OUTPUT)
AltitudeStepBCM.SetValue(False)
CommonMode0BCM.SetDirection(digitalio.Direction.OUTPUT)
CommonMode0BCM.SetValue(False)
CommonMode1BCM.SetDirection(digitalio.Direction.OUTPUT)
CommonMode1BCM.SetValue(False)
CommonMode2BCM.SetDirection(digitalio.Direction.OUTPUT)
CommonMode2BCM.SetValue(False)
CommonDirectionBCM.SetDirection(digitalio.Direction.OUTPUT)
CommonDirectionBCM.SetValue(False)
CommonEnableBCM.SetDirection(digitalio.Direction.OUTPUT)
CommonEnableBCM.SetValue(False)
AzimuthFaultBCM.SetDirection(digitalio.Direction.INPUT)
AzimuthFaultBCM.pull = digitalio.Pull.UP # Floating pins will toggle between FAULT and OK which causes chaos. Pull UP defaults to OK.
AltitudeFaultBCM.SetDirection(digitalio.Direction.INPUT)
AltitudeFaultBCM.pull = digitalio.Pull.UP

# The Pimoroni Tiny family of boards allow the BOOTSEL button to be checked too.
if 'TINY' in FEATURES:
    BootBCM = GPIOpin(board.USER_SW,'boot') # Tiny RP2040 # The BOOTSEL button.
    BootBCM.SetDirection(digitalio.Direction.INPUT)
    BootBCM.pull = digitalio.Pull.UP # The button goes LOW when pressed.

# Configure Motors.
Azimuth = steppermotor('azimuth')
Azimuth.SetPins(stepBCM=AzimuthStepBCM,directionBCM=CommonDirectionBCM,mode0BCM=CommonMode0BCM,mode1BCM=CommonMode1BCM,mode2BCM=CommonMode2BCM,enableBCM=CommonEnableBCM,faultBCM=AzimuthFaultBCM) # Direct control over Azimuth motor.
Azimuth.SetConfig(gearratio=(60 * 4),motorstepsperrev=400,minangle=45.0,maxangle=315.0,restangle=180.0,currentangle=180.0,orientation=1,backlashangle=0.0)
Altitude = steppermotor('altitude')
Altitude.SetPins(stepBCM=AltitudeStepBCM,directionBCM=CommonDirectionBCM,mode0BCM=CommonMode0BCM,mode1BCM=CommonMode1BCM,mode2BCM=CommonMode2BCM,enableBCM=CommonEnableBCM,faultBCM=AltitudeFaultBCM) # Direct control over Altitude motor.
Altitude.SetConfig(gearratio=(60 * 4),motorstepsperrev=400,minangle=0.0,maxangle=90.0,restangle=0.0,currentangle=0.0,orientation=-1,backlashangle=0.0)
Motors = [Azimuth, Altitude] # Control over 'all' motors.

class picosession():
    def __init__(self):
        self.SessionStart = time.time()
        self.AutonomousControl = False # Triggers movement of the motors when they are configured and trajectories loaded.
        self.RemoteControl = False # Allows movement of the motors when they are configured, regardless of trajectories existing.
        self.Quit = False # Set to TRUE to terminate the session.
        self.TrajectorySafetyms = 2 * 60 * 1000 # How many milliseconds can a valid trajectory remain in use before comms failure terminates it? == 2 minutes.
        self.TrajectorySafetyFlushes = 0 # How many times have we had to flush the trajectories for safety when comms seemed to fail?
        self.FailsafeLatch = False # Latch to prevent 'failsafe' messages flooding the communication buffers when safety flush is triggered.

    def MovePermission(self):
        """ Decide if the microcontroller can accept remote control of the motors.
            They will move under the direction of the remote RPi. """
        result = True
        for i in Motors: # for ALL motors.
            if not i.MotorConfigured: result = False # Motor must be configured.
        self.RemoteControl = result
        # Decide if the microcontroller can have autonomous control of the motors.
        # They may start moving immediately.
        if not Clock.ClockSynchronised: result = False # Clock must be synchronised.
        for i in Motors: # for ALL motors.
            if not i.Trajectory.Valid: result = False # Trajectory must be valid.
        self.AutonomousControl = result

    def SendMotorStatus(self,motorname,immediate=False,codes='?-?'):
        """ Decide which motor status to send. 
            immediate: True: Status is sent even if not due. 
                       False: Status is only sent if timer is due. 
            codes: Optional extra codes added to the status message (dev/test/debug etc) """
        for i in Motors:
            if i.MotorName == motorname: i.SendMotorStatus(immediate=immediate,codes=codes)
            
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
        if CircuitPythonVersion.split('.')[0] in ['7','8','9']: pass # Supported CircuitPython version.
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
                    if i.TargetPosition != i.CurrentPosition: i.MoveMotor()
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
        LogFile.Log('CheckVersionCompatibility',rpiversion,'not in',str(ACCEPTABLERPIVERSIONS))

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
    #namelist = []
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
                time.sleep(duration) # Wait until time to turn off again.
                pinobj.SetValue(False) # Turn off.
                if repeats > 0: time.sleep(duration) # If we're going to repeat, pause before repeating too.
        elif command == 'off' and pinobj.Pin.direction == digitalio.Direction.OUTPUT: # Switch off and it's an INPUT.
            pinobj.SetValue(False) # Turn off.
            if duration != 0: # For a limited time only.
                time.sleep(duration) # Wait until time to turn on again.
                pinobj.SetValue(True) # Turn on.
                if repeats > 0: time.sleep(duration) # If we're going to repeat, pause before repeating too.
        elif command == 'state': # Send pin state.
            RPi.Write("# pin status " + str(pinobj.Name) + " " + str(pinobj.Pin.value))
    return True

Session = picosession() # Instantiate a sesson object.

def ProcessInput(line):
    lineitems = line.split(' ')
    if lineitems[0] == 'exit':
        print('exit cmd received.')
        LogFile.Log('exit cmd received.')
        Session.Quit = True
    elif lineitems[0] == 'stop': # Immediately stop motion.
        for i in Motors:
            i.Stop()
        Session.MovePermission()
    elif line.startswith('#'): pass # Ignore comments.
    elif line.startswith('rpi started'):
        RPi.Write('acknowledged rpi started')
        for i in Motors:
            i.Reset()
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif lineitems[0] == 'reset':
        for i in Motors:
            i.Reset() # Reset motor status.
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
            if i.MotorName == lineitems[2]: i.TunePosition(int(lineitems[3]))
    elif line.startswith('rpi version'):
        CheckVersionCompatibility(lineitems[3])        
    elif line.startswith('clear trajectory'):
        RPi.Write('cleared trajectory')
        for i in Motors:
            i.Trajectory.Clear()
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith('configure motor'):
        for i in Motors:
            if i.MotorName == lineitems[3]:
                i.ConfigureMotor(line) # Load configuration.
                i.SendMotorStatus(immediate=True,codes='cfg') # Immediately respond with lates motor status.
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith == 'report motor': # RPi has requested the motor configurations to be reported back.
        for i in Motors:
            i.ReportMotorConfig()
    elif lineitems[0] == 'trajectory':
        for i in Motors:
            if i.MotorName == lineitems[2]:
                i.AddTrajectoryPoint(line)
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif lineitems[0] == 'goto':
        for i in Motors:
            if i.MotorName == lineitems[2]:
                i.GoToAngle(float(lineitems[3]))
    elif line.startswith('set time'):
        Clock.SetTimeFromString(lineitems[2])
        Session.MovePermission() # Decide if we have valid trajectories and configuration in every motor. OK to move if we do!
    elif line.startswith('leds off'): # Go to stealth mode, turn LEDs off.
        StatusLed.Disable() # Disable the onboard status LED.
    elif line.startswith('leds on'): # Enable the LEDs to show processing.
        StatusLed.Enable() # Enable the onboard status LED.
    elif lineitems[0] == 'pin': # Direct GPIO pin command.
        PinCommand(line) # Execute the pin command.
    else:
        RPi.Write('error: unrecognised RPi command: ' + line)

class memorymanager():
    def __init__(self):
        self.currmem = None # Current memory free value.
        self.GCCount = 0 # How often has garbage collector run?
        self.Poll()

    def Poll(self): # Check current memory and trigger memory garbage collection early if needed.
        """ It looks like CircuitPython allocates memory in 2K chunks, it will error out if it cannot allocate 2K at a time. 
            So run cleanup at 3K for safety. """
        self.currmem = gc.mem_free()
        if self.currmem < 3000:
            gc.collect()
            self.GCCount += 1 # Increase count of garbagecollector runs.

MemMgr = memorymanager()

print ('Starting...')
RPi.Reset() # Reset comms and send initial header.
# Report back which motors are defined.
line = "defined motors "
for i in Motors:
    line += i.MotorName + ' '
RPi.Write(line)
    
# This is the main processing loop.
try:
    while True: # Full interaction
        
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

        if 'TINY' in FEATURES and BootBCM.Released():
            LogFile.Log("Main:BootBCM user key pressed.")
            print("Main:BootBCM user key pressed.")
            
        try:
            Session.TrajectorySafety() # If no recent receipt from RPi, assume comms break take precautions... Clear trajectories?
        except Exception as e:
            LogFile.Log("Main: SessionTrajectorySafety() failed.",e)
            print("Main: SessionTrajectorySafety() failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.
            
        if Session.Quit: break 
        
        try:
            if SessionTimer.Due():
                Session.SendSessionStatus(codes='tmr') # Send session status messages.
                if 'RP2350' in FEATURES: SendCpuStatus() # Send microcontroller status.
        except Exception as e:
            LogFile.Log("Main: SessionTimer failed.",e)
            print("Main: SessionTimer failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.
                
        try:
            Session.SendMotorStatus('azimuth',codes='tmr') # Send azimuth status message.
        except Exception as e:
            LogFile.Log("Main: Azimuth status failed.",e)
            print("Main: Azimuth status failed.",e)
            ExceptionCounter.Raise() # Increment exception count for the session.
               
        try:
            Session.SendMotorStatus('altitude',codes='tmr') # Send altitude status message.
        except Exception as e:
            LogFile.Log("Main: Altitude status failed.",e)
            print("Main: Altitude status failed.",e)
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
print ('controller stopping...')
# Make sure that the log file buffer is flushed fully to the remote host.
LogFile.SendCheck(force=True)
RPi.Write('# GCCount ' + str(MemMgr.GCCount))
RPi.Write('controller stopped')
LoopCounter = 0
print ('Flushing final comms to RPi.')
print ('Further input from RPi will be ignored.')
while len(RPi.WriteQueue) > 0:
    RPi.WritePoll()
    LoopCounter += 1
    if LoopCounter > 1000:
        print ('Flushing incomplete.')
        break
print ('controller stopped')
