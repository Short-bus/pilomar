# code.py - circuitpython version - Pimoroni TinyRP2040 version.

# Sample messages...
#  From microcontroller to RPi
#   session status 20210409090929 False False False 20 None None
#   comms status 20210409090929 0 0 538 0
#   motor status 20210409090939 azimuth False 20210409090939 0 48000 180.0 True
#   motor status 20210409090949 altitude False 20210409090949 0 0 0.0 True
#  From RPi to microcontroller
#   configure motor 20210409090949 azimuth 180.0
#   sendstatus 20210409090949 False

# If MODE0/1/2 pins are declared as None, Microstepping is disabled.

# Version numbering scheme:
#           aa.bb.cc
#           aa = Major version, large changes to functionality. Likely to require major version change on RPi side too.
#           bb = Feature changes, but same overall program. Likely to require functionality change on RPi side too.
#           cc = Bugfix, no feature changes. Will not require changes on RPi side.
VERSION = '0.3.0' # Software version reported to the RPi.
ACCEPTABLERPIVERSIONS = ['0.0','0.1','0.2'] # Which RPi versions are acceptable? (Ignore patch level)

print ('hello')
# Check we are running CircuitPython.
CircuitPython = False # Indicates CircuitPython rather than MicroPython.
Bootline = '' # Make sure the entire boot_out.txt content is available as a single item.
with open('boot_out.txt','r') as f:
    while True:
        line = f.readline()
        if line == '': break
        lines = line.split(';')
        for item in lines:
            cleanitem = item.strip() # Remove unwanted characters.
            Bootline += cleanitem + ' '
            print(cleanitem)
            for elements in item.split(' '):
                if elements.strip().lower() == 'circuitpython': CircuitPython = True # This is a CircuitPython build.
print("CircuitPython installation?:",CircuitPython)
print("CircuitPython version:",Bootline)

import digitalio
import microcontroller
import board
import analogio
import busio
import time
import gc # Garbage Collector
gcmf = gc.mem_free()
print("At startup gc.mem_free:",gcmf)

def neatprint(*args):
    """ Own 'print' function. Formats neatly in early Python versions and allows
        general suppression / redirection of output when this runs headlessly. """
    if True: # Output to terminal/stdout.
        line = ''
        for a in args:
            if type(a) != type(str):
                a = str(a)
            line += ' ' + a
        line = line.strip()
        print (line)
    else: # Suppress output.
        pass

neatprint ('CIRCUITPYTHON: code.py running...')
neatprint ('Pimoroni Tiny2040 board.')

class GPIOpin():
    def __init__(self,pin):
        self.Pin = digitalio.DigitalInOut(pin)
        self.PinNumber = pin

    def SetDirection(self,direction):
        self.Pin.direction = direction
        if direction == digitalio.Direction.OUTPUT: self.Pin.value = False # turn off.

    def SetValue(self,value):
        if self.Pin.direction == digitalio.Direction.OUTPUT: self.Pin.value = value

    def GetValue(self):
        return self.Pin.value

    def SetPull(self,pull):
        if self.Pin.direction == digitalio.Direction.INPUT: self.Pin.pull = pull

class led():
    def __init__(self,pin,state=False):
        """ Tiny2040 LED on/off state is inverted!
            ie to turn LED ON, pin must go LOW.
               to turn LED OFF, pin must go HIGH. """
        self.Led = digitalio.DigitalInOut(pin)
        self.Led.direction = digitalio.Direction.OUTPUT
        self.Led.value = None # Off
        if state: self.On()
        else: self.Off()
        self.Enabled = True # Set to FALSE to turn off the LED completely.

    def Enable(self):
        self.Enabled = True
        if self.State(): self.On()

    def Disable(self):
        self.Enabled = False
        self.Off()

    def On(self):
        """ Tiny2040 uses opposite pin state to control LED. """
        if self.Enabled: self.Led.value = False
        else: self.Led.value = True

    def Off(self):
        """ Tiny2040 uses opposite pin state to control LED. """
        self.Led.value = True

    def Toggle(self):
        if self.Led.value: self.Off()
        else: self.On()

    def State(self):
        return self.Led.value

class statusled():
    """ Pimoroni Tiny2040 version of RGB LED handling. """
    def __init__(self):
        self.LedR = led(board.LED_R)
        self.LedG = led(board.LED_G)
        self.LedB = led(board.LED_B)
        self.TaskList = {'idle': (False,False,False), # Off
                         'tx': (False,False,True), # Blue - Flashes when writing output to UART
                         'rx': (False,False,True), # Blue - Flashes when clearing input from UART
                         'altitude': (False,True,False), # green - Flashes when ALTITUDE motor is moving.
                         'azimuth': (False,True,False), # green - Flashes when AZIMUTH motor is moving.
                         'move': (False,True,False), # green - Flashes when motor is moving (If no specific motor colour).
                         'error': (True,False,False), # Red - Indicates failure/fault.
                         'pulse': (True,False,True), # Pink - Heartbeat signal (if used).
                         'init': (False,True,True)} # cyan - System is initializing.
        # self.Led.brightness = 0.01
        self.Enabled = True # If set to FALSE, the LED is permanently off except for ERROR conditions.
        self.Task('idle')
        #print(dir(self.LedR))

    def Enable(self):
        self.Enabled = True

    def Disable(self):
        self.Enabled = False
        self.Task('idle')

    def Task(self,task):
        if self.Enabled or task == 'error':
            if task in self.TaskList:
                t = self.TaskList[task]
                if t[0]: self.LedR.On()
                else: self.LedR.Off()
                if t[1]: self.LedG.On()
                else: self.LedG.Off()
                if t[2]: self.LedB.On()
                else: self.LedB.Off()
            else:
                self.LedR.Off()
                self.LedG.Off()
                self.LedB.Off()
        else: # LED is disabled for everything except ERRORS
            self.LedR.Off()
            self.LedG.Off()
            self.LedB.Off()

StatusLed = statusled()
StatusLed.Task('init') # System is initializing...
time.sleep(3)

button = digitalio.DigitalInOut(board.USER_SW) # Built in button.
button.switch_to_input(pull=digitalio.Pull.DOWN)
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

def HRSeconds(seconds):
    ss = seconds % 60
    minutes = int((seconds - ss) / 60)
    mm = minutes % 60
    hours = int((minutes - mm) / 60)
    result = ('000' + str(hours))[-3:] + ':'
    result += ('00' + str(mm))[-2:] + ':'
    result += ('00' + str(ss))[-2:]
    return result

def IntToTimeString(timestamp):
    # Sometime after 2030 localtime() method may fail if it starts receiving longint values.
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
    # Sometime after 2030, this may cause problems for localtime() method if it generates longint values.
    year = int(timestamp[0:4])
    month = int(timestamp[4:6])
    day = int(timestamp[6:8])
    hour = int(timestamp[8:10])
    minute = int(timestamp[10:12])
    second = int(timestamp[12:14])
    result = time.mktime((year,month,day,hour,minute,second,0,-1,-1))
    return result

def ValidateTimeString(timestamp):
    result = False
    if len(timestamp) == 14 and timestamp.isdigit():
        result = True
    if result != True:
        LogFile.Log('error: ValidateTimeString(' + timestamp + ') is invalid.')
        print('error: ValidateTimeString(' + timestamp + ') is invalid.')
    return result

def ValidateAngleString(angle):
    result = False
    try:
        temp = float(angle)
    except Exception as e:
        temp = None
        LogFile.Log('error: ValidateAngleString(' + angle + ') is invalid.')
        print('error: ValidateAngleString(' + angle + ') is invalid.')
    if temp != None:
        if temp >= -360.0 and temp <= 360.0:
            result = True
    if result != True:
        LogFile.Log('error: ValidateAngleString(' + angle + ') is invalid.')
        print('error: ValidateAngleString(' + angle + ') is invalid.')
    return result

def IsFloat(text):
    """ Return TRUE if a string can be converted to a float value. """
    result = False
    try:
        temp = float(text)
        result = True
    except ValueError:
        pass
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

    def SetNextDue_orig(self):
        """ Original NEXT DUE calculation, rolls forward 1 RepeatSeconds slot at a time until it's in the future. """
        while self.NextDue <= time.time():
            self.NextDue = self.NextDue + self.RepeatSeconds # Move forward if still needed.

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

SessionTimer = timer('session',20,offset=7)
CpuTimer = timer('cpu',120,offset=11)

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
        self.Clock = None

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
        if len(self.Lines) < 20:
            self.Lines.append(line)
            self.BufferSize += len(line)
        else:
            print("logfile.Log: Buffer is full. log message ignored until cleared.")

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

print ('ResetReason: ' + str(microcontroller.cpu.reset_reason))

def MicroControllerLog():
    """ Report microcontroller condition back to RPi. """
    i = 0
    x = ''
    for s in microcontroller.cpu.uid:
        if x != '': x+= '-'
        x += hex(s)[2:]
    for cpu in microcontroller.cpus:
        line = 'CPU UID: ' + x + ' '
        line += 'Core: ' + str(i) + ', ResetReason: ' + str(microcontroller.cpus[i].reset_reason).split('.')[-1] + ', '
        line += 'Temp: ' + str(microcontroller.cpus[i].temperature) + ', '
        line += 'Freq: ' + str(microcontroller.cpus[i].frequency)[:-6] + 'M, ' # To apply to live copy
        line += 'Volt: ' + str(microcontroller.cpus[i].voltage)
        LogFile.Log(line)
        i += 1

class uarthost():
    """ UART serial communication handler.
        Handles buffering of received and transmitted data over serial line. """
    def __init__(self,name=None,channel=0):
        print(dir(board))
        if name == None: name = 'UART' + str(channel) # Default to useful name.
        if channel == 0: # UART0
            self.uart = busio.UART(board.GP0,board.GP1,baudrate=115200,receiver_buffer_size=1024) # was 256 # Define UART0 as the serial comms channel to the host.
            print ('UART TX=', board.GP0, 'UART RX=', board.GP1)
        else: # UART1
            raise Exception('uarthost on Tiny2040 not configued for UART channel 1. Use channel 0 only.')
            # We can quit here because without a UART channel there's no way to report the error back to the RPi.
        self.WriteChunk = 32 # 32 seems OK on Circuitpython.
        self.ReceivedLines = [] # No lines received yet.
        self.LinesRead = 0 # total number of lines received.
        self.CharactersRead = 0 # Total number of characters received.
        self.LinesWritten = 0 # Total number of lines sent.
        self.PicoRxErrors = 0 # How many checksum rejections occurred with received data?
        self.CharactersWritten = 0 # total number of characters sent.
        self.StartTime = time.time()
        self.WriteGapms = 100 # 200ms pause between each chunk of data written.
        self.Name = name
        self.ReceivingLine = '' # Current line being received. It's constructed here until '\n' received.
        self.WriteQueue = [] # List of queued messages to be sent when safe.
        self.WriteDrops = 0 # Number of messages dropped because queue filled.
        self.ReadDrops = 0 # How many received messages are dropped because input buffer is full?
        self.LastTxms = self.ticks_ms() # Milliseconds since last transmission.
        self.LastRxms = self.ticks_ms() # Milliseconds since last receipt.
        self.Clock = None # *Q* Is this used?
        neatprint (self.Name, self.uart)

    def Reset(self):
        """ Reset communications (flush output buffers). """
        self.WriteQueue = [] # Empty the write queue.
        self.ReceivedLines = [] # Empty the input queue.
        for i in range(2): self.Write('#' * 20) # Send dummy lines through the UART line to flush out any junk.
        self.Write('controller started') # Tell the remote device we're up and running. Replaced 'pico started' message.
        self.Write('controller version ' + VERSION) # Tell the remove device which software version is running.
        
    def ticks_ms(self):
        """ Standardise result of CircuitPython and MicroPython CPU ticks value. """
        return int(time.monotonic_ns() / 1000000) # Nano seconds. Reduce by 1.0e6 to get milliseconds (as integer).

    def ticks_s(self):
        """ Standardise result of CircuitPython and MicroPython CPU ticks value. """
        return float(time.monotonic_ns() / 1000000000) # Seconds. Reduce by 1.0e9 to get seconds (as decimal).

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
        """ Perform safe and friendly read of UART serial port.
            Completed lines are added to the ReceivedLines list and
            are available to the rest of the program. """
        CharCounter = 0
        while self.RxWaiting(): # Input waiting in Rx buffer.
            StatusLed.Task('rx')
            CharCounter += 1
            if CharCounter > 20: break # Max 20 chars read per call.
            try:
                bchar = self.uart.read(1) # 1 char at a time. # *Q* This fails in CircuitPython 8.x, use alternative below.
                #bchar = self.uart.read(nbytes=1) # *Q* This fails in CircuitPython 7.2, use alternative above.
                cchar = ''
                self.CharactersRead += 1
                nchar = int.from_bytes(bchar,'little',False)
                if nchar <= 127: # Acceptable as 7 bit ascii
                    cchar = bchar.decode('utf-8')
                    if cchar != chr(nchar):
                        print('uarthost.BufferInput: 7bit character conversion cheat would fail.')
                    self.ReceivingLine += cchar
                else:
                    LogFile.Log('uarthost.BufferInput: Ignored bad char (', str(bchar), "/", str(nchar), ')')
            except Exception as e:
                LogFile.Log('uarthost.BufferInput: Error:', str(e))
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
                            print('warning: receive buffer full. Ignored: ' + line)
                            self.ReadDrops += 1
                self.ReceivingLine = ''
            self.LastRxms = self.ticks_ms() # When was last message received?
        StatusLed.Task('idle')
    
    def ReceiveAge(self):
        """ How many ms old is the last receipt? """
        LastRecMs = self.ticks_ms() - self.LastRxms # How old is the last receipt?
        return LastRecMs

    def Read(self):
        """ Return next available complete received line. """
        # 1st check for new data received on serial port.
        self.BufferInput() # Check UART port.
        line = ''
        while len(line) == 0 and len(self.ReceivedLines) > 0:
            line = self.ReceivedLines.pop(0)
            if self.ValidateChecksum(line): # Checksum is good, trust the line.
                line = self.RemoveChecksum(line)
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
        StatusLed.Task('tx')
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
        # It queues up to 100 messages for sending. After that, the queue only accepts extra messages if force==True.
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
        #else:
        #    LogFile.Log("UpdateClockFromInt(",IntToTimeString(TimeInt),") does not replace",IntToTimeString(tn))
        return result

    def UpdateClockFromString(self,TimeString):
    
        """ Given any character timestamp this will compare against the clock
            and update the clock if the new timestamp is AHEAD of the current 
            clock. This increases the accuracy/synchronisation of the clock with the RPi's clock.
            This can be run against any received timestamp to continually improve the clock's time.   

            If the microcontroller is connected via USB to Thonny on a remote machine, the machine clock may then
            get synchronised, in which case the TimeDelta value is nolonger needed. """

        #print("c.UCFS: Received",TimeString)
        result = False
        for a in [' ','.','-',':']:
            TimeString = TimeString.replace(a,"")
        try:
            #print("c.UCFS: Using",TimeString)
            result = TimeStringToInt(TimeString)
            #print("c.UCFS: As int",result)
            self.UpdateClockFromInt(result)
        except:
            LogFile.Log("UpdateClockFromString(",TimeString,") failed.")
        return result

    def CheckTimeDelta(self,now):
        """ If the basic clock time suddenly jumps, assume that the clock has been synchronised
            in which case clear TimeDelta because it's nolonger needed. """
        # now = time.time()
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
        result = True

    def SetTimeFromString(self,TimeString):
        """ Set clock offset from a CHARACTER TIME. """
        result = False
        for a in [' ','.','-',':']:
            TimeString = TimeString.replace(a,"")
        try:
            result = self.SetTimeFromInt(TimeStringToInt(TimeString))
        except Exception as e:
            LogFile.Log('clock.SetTimeFromString: Invalid timestamp string (', TimeString, ')')
        return result

    def Now(self):
        """ Return current clock time. As micropython number of seconds."""
        now = time.time()
        self.CheckTimeDelta(now) # If the internal clock has recently been synchronised clear TimeDelta until it can be recalculated.
        return (now + self.TimeDelta)
        
    def NowString(self):
        """ Return current clock time. As character string. """
        return IntToTimeString(self.Now())

Clock = clock(time.time()) # Simulate RTC
LogFile.Clock = Clock # Tell the LogFile which clock to use.
RPi.Clock = Clock # Tell the RPi which clock to use.

class trajectorypoint():
    """ An individual segment in a trajectory.
        Each segment is a short straight line path that approximates the arc that
        the target is following. The segment is short enough that it is very
        close to the actual curve that the target follows.
        trajectory point yymmddhhmmss motorname start startangle end endangle
             0       1         2          3       4       5       6     7     """
    def __init__(self,line):
        # Be very protective of junk arriving on the serial line.
        # Don't create the entry if there is any problem with it.
        # The remote server will re-send the record if it doesn't get created this time.
        # trajectory 20210410163444 azimuth 20210410163444 256.57984815616663 20210410163544 256.7949264136615
        lineitems = line.split(' ')
        self.StartTime = TimeStringToInt(lineitems[3])
        self.StartAngle = float(lineitems[4])
        self.EndTime = TimeStringToInt(lineitems[5]) # In the future. Could overflow 'int' eventually and fail somewhere.
        self.EndAngle = float(lineitems[6])

    def Printable(self,clock=None):
        """ Generate test printable version of the entry. """
        line = ''
        line += IntToTimeString(self.StartTime) + " "
        line += str(self.StartAngle) + " "
        line += IntToTimeString(self.EndTime) + " "
        line += str(self.EndAngle)
        if clock != None:
            line += ' Clock=' + IntToTimeString(clock) + " "
        return line

    def ExpectedAngle(self,timeint=None):
        """ Calculate the expected angle based upon this entry.
            If the trajectory point's start time has not yet been reached, 
            we 'loiter' at the start angle. Useful for satellite passes when 
            we need to go to the 'rise' position and wait for it to appear.
            if the trajectory segment has expired, the expected angle is the end of the segment. """
        if timeint == None:
            timeint = Clock.Now()
        if timeint > self.EndTime: timeint = self.EndTime # Cannot proceed past the end of the planned trajectory.
        elif timeint < self.StartTime: timeint = self.StartTime # Cannot extrapolate backwards in time, just hover at the start point.
        elapsedseconds = timeint - self.StartTime
        AngleDelta = self.EndAngle - self.StartAngle
        TimeDelta = self.EndTime - self.StartTime
        location = (float(elapsedseconds) * AngleDelta / TimeDelta) + self.StartAngle
        return location

class trajectory():
    """ A complete trajectory for a target. Consists of a list of individual segments in sequence. """
    def __init__(self,name):
        self.TrajectoryList = []
        self.Valid = False # Indicates that the trajectory is useable.
        self.MotorName = name # The parent MotorName to match log messages with the parent motor.

    def Clean(self): # Trim expired entries from the trajectory list.
        """ All the entries in Trajectory List should complete in the future. """
        c = Clock.Now()
        while len(self.TrajectoryList) > 0 and self.TrajectoryList[0].EndTime < c:
            LogFile.Log('trajectory.Clean: Expired (', self.MotorName, self.TrajectoryList[0].Printable(), ')')
            temp = self.TrajectoryList.pop(0) # Remove the first entry from the list, it's not needed anymore.
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
            True means the ExpectedAngle() method can be trusted.
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

    def ExpectedAngle(self):
        """ What is the current expected angle of the motor based upon
            the trajectory list contents?
            If the last entry has expired, this will continue following
            that path in the hope that it gets updated soon. """
        self.Clean() # Make sure the list is up to date.
        # Calculate the angle that the motor should be at right now.
        if len(self.TrajectoryList) > 0:
            result = self.TrajectoryList[0].ExpectedAngle()
        else:
            result = None # No angle set yet.
        return result

# Use ADC to read VMOT value. We can detect if motors are actually powered.
# - Losing power is an easy problem to detect and report.
ADC0_Mode = 'adc' # 'adc' means an analog signal is reported.
if ADC0_Mode == 'adc':
    # print (dir(analogio))
    VMotADC = analogio.AnalogIn(board.A0)
else:   
    VMotADC = None

def VMot():
    """ Read the current MotorPower ADC value directly.
        Don't scale for voltage, let the host deal with that.
        If not available or failed, ZERO is returned. """
    result = 0
    try:
        if ADC0_Mode == 'adc':
            result = VMotADC.value
        else: 
            result = 0 # No ADC value supported.
    except Exception as e:
        print('VMot() failed:',e)
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
        self.UseMicrostepping = False
        self.WaitTime = self.SlowTime # The time between pulses, starts slow, reduces as a move progresses. Resets every time a new target is set.
        self.Orientation = 1 # 1=Fwd, -1=Bkwd. This sets the overall orientation of motion. Compensate for gearing reversing the direction of motion here! It's applied to the DirectionBCM pin when the move is made.
        self.StepDir = 1 # The direction of a particular move +/-1. It always represents a SINGLE FULL STEP.
        self.LastStepDir = 0 # Record the 'last' direction that the motor moved in. This may be useful for handling gear backlash. Starts at ZERO (No direction)
        self.BacklashAngle = 0.0 # This is the angle the motor must move to overcome backlash in the gearing when changing direction.
        self.DriftSteps = 0 # This is the number of steps 'error' that DriftTracking has identified. It must be incorporated back into motor movements as smoothly as possible. Consider backlash etc.
        self.MotorStepsPerRev = None
        self.MicrostepRatio = None
        self.MotorPower = None
        self.MicrosteppingMode0 = 0
        self.MicrosteppingMode1 = 0
        self.MicrosteppingMode2 = 0
        self.MotorStepsPerAxisDegree = None
        self.GearRatio = None # gearratio is the overall gearing of the entire transmission. 60 means 60 motor revs for 1 transmission rev.
        self.AxisStepsPerRev = None
        self.MinAngle = None # Max anticlockwise movement.
        self.MaxAngle = None # Max clockwise movement.
        self.CurrentAngle = None
        self.TargetAngle = None
        self.MinPosition = None # Min clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.MaxPosition = None # Max clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.RestAngle = None # The 'rest' position of the axis. Used for calibrating at startup. Typically DUE SOUTH or HORIZONTAL position of the axis.
        self.RestPosition = None
        self.RequestedAngle = None
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
        self.FullStepBoundary = True # True if the motor position is currently on a FULL STEP position. We can make FULL STEP moves if we are. Otherwise we're microstepping.
        self.LatestTuneSteps = 0 # Record details of the last tune command received. So we can see it was handled.
        self.LatestTuneTime = None
        # Latest Start/Stop times for config and status methods.
        self.ConfigStartTime = None
        self.ConfigEndTime = None
        self.StatusStartTime = None
        self.StatusEndTime = None

    def ReportStamps(self):
        """ Report back start/end timestmaps for config and status methods. """
        line = "# Timestamps: " + self.MotorName + " Config "
        if self.ConfigStartTime == None: line += "NOT SET"
        else: line += IntToTimeString(self.ConfigStartTime)
        line += "-"
        if self.ConfigEndTime == None: line += "NOT SET"
        else: line += IntToTimeString(self.ConfigEndTime)
        line += " Status "
        if self.StatusStartTime == None: line += "NOT SET"
        else: line += IntToTimeString(self.StatusStartTime)
        line += "-"
        if self.StatusEndTime == None: line += "NOT SET"
        else: line += IntToTimeString(self.StatusEndTime)
        RPi.Write(line) # Send over UART to RPi.

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
        LogFile.Log(self.MotorName + ".Reset.")
        self.Trajectory.Clear() # Delete the trajectory completely. We'll be needing a new one.
        if enable: self.EnableMotor() # Leave motor enabled.
        else: self.DisableMotor() # Disable the motor.
        self.OnTarget = False
        self.CurrentPosition = self.RestPosition # Initialise CurrentPosition, we'll set it in next line. This is updated DURING moves too.
        self.CurrentAngle = self.RestAngle
        self.TargetPosition = self.CurrentPosition
        self.TargetAngle = self.CurrentAngle
        self.RequestedPosition = None
        self.RequestedAngle = None
        self.MotorConfigured = False
        self.SendStatus = True 
        self.SendMotorStatus(immediate=True,codes='rst')
        return True

    def AddTrajectoryPoint(self,entry):
        try:
            self.Trajectory.Add(entry)
        except Exception as e:
            LogFile.Log('steppermotor(' + self.MotorName + ').AddTrajectoryPoint: ' + str(entry) + ': Failed. ' + str(e))
        self.SendMotorStatus(immediate=True,codes='atp') # This triggers the next trajectory point faster than waiting for the regular status message will.

    def ClearTrajectory(self):
        """ Remove current trajectory. """
        self.Trajectory.Clear() # Empty the entire trajectory.
        self.SendMotorStatus(immediate=True,codes='clt')

    def Stop(self):
        """ Immediately stop the motor. """
        self.ClearTrajectory()
        self.TargetPosition = self.CurrentPosition
        self.TargetAngle = self.CurrentAngle
        self.OnTarget = False
        self.RequestedPosition = None
        self.RequestedAngle = None
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

    def ExpectedAngle(self):
        """ What angle should the motor be at according to the current trajectory. """
        angle = self.Trajectory.ExpectedAngle()
        return angle

    def GoToAngle(self,newangle):
        if self.MotorConfigured:
            print ('GoToAngle: Motor configured')
            LogFile.Log('steppermotor.GoToAngle(' + self.MotorName + ') ' + str(newangle))
            print ('GoToAngle: Stop')
            self.Stop() # Clear any pre-existing trajectory before moving.
            print ('GoToAngle: SetNewTargetAngle')
            self.SetNewTargetAngle(newangle)
            print ('GoToAngle: MoveMotor')
            self.MoveMotor()
            print ('GoToAngle: MoveMotor complete.')
        else:
            print ('GoToAngle: Motor NOT configured')
            LogFile.Log('steppermotor.GoToAngle(' + self.MotorName + ') Rejected. Motor is not configured.')
            RPi.Write('goto rejected ' + self.MotorName + ' ' + str(newangle) + ' MotorNotConfigured')
        print ('GoToAngle: SendMotorStatus (immediate) gte')
        self.SendMotorStatus(immediate=True,codes='gte') # Tell RPi latest condition of the motor.

    def SetNewTargetAngle(self,newangle):
        """ Set a new target ANGLE (and therefore position) for the motor.
            This will not move the motor, it will just prepare the step count and direction etpc.
        """
        self.RequestedAngle = newangle # What angle was requested?
        self.RequestedPosition = self.AngleToStep(newangle) # What position was requested?
        self.EnableMotor() # Enable the motor.
        result = True # Set was successful.
        if newangle == None:
            result = False
        else:
            # Limit new angle to movement range. (MaxAngle, MinAngle)
            if newangle > self.MaxAngle:
                LogFile.Log(self.MotorName + ": SetNewTargetAngle: " + str(newangle) + " limited to: " + str(self.MaxAngle))
                newangle = self.MaxAngle
                result = False # Set failed.
            if newangle < self.MinAngle:
                LogFile.Log(self.MotorName + ": SetNewTargetAngle: " + str(newangle) + " limited to: " + str(self.MinAngle))
                newangle = self.MinAngle
                result = False # Set failed.
            self.TargetAngle = newangle
            self.TargetPosition = self.AngleToStep(newangle) # Convert it into the nearest absolute STEP position.
            self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call MoveFullStep().
            if self.ChangeSteps() > 0: self.StepDir = 1 # Which direction do we move in?
            else: self.StepDir = -1
        return result

    def SetNewTargetPosition(self,newposition=0,Limit=True):
        """ Set a new target POSITION (and therefore angle) for the motor.
            This will not move the motor, it will just prepare the step count and direction etc.
        """
        # Limit new angle to movement range. (MaxAngle, MinAngle)
        newangle = self.StepToAngle(newposition)
        result = True # Set succeeded.
        self.RequestedAngle = newangle # What angle was requested?
        self.RequestedPosition = newposition # What position was requested?
        self.EnableMotor() # Enable the motor.
        if Limit:
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
        self.TargetAngle = newangle
        self.TargetPosition = newposition # Convert it into the nearest absolute STEP position.
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call MoveFullStep().
        if self.ChangeSteps() > 0: self.StepDir = 1 # Which direction do we move in?
        else: self.StepDir = -1
        return result

    def TargetExpectedAngle(self):
        result = False # Failed unless successful.
        a = self.ExpectedAngle()
        if a != None and self.Trajectory.Valid and self.MotorConfigured: # We can set the target based upon current trajectory.
            result = self.SetNewTargetAngle(a)
        else: # Target is just the current position. Config and Trajectory are invalid.
            result = self.SetNewTargetAngle(self.CurrentAngle) # Target is where we are!
            LogFile.Log('TargetExpectedAngle',self.MotorName,'not ready. tv,mc,a=', self.Trajectory.Valid, self.MotorConfigured,a)
        return result

    def TunePosition(self,delta):
        """ Tune the motor position. This shifts the motor, but retains the 'position' calculation unchanged.
            Use this to address positioning errors or drift adjustments. """
        if self.MotorConfigured:
            self.EnableMotor()
            old = self.CurrentPosition # Store the current position of the motor. We'll restore this when finished.
            new = self.CurrentPosition + delta # Calculate the new target position (fullsteps).
            self.SetNewTargetPosition(new,Limit=False) # Set the target in the object. Primes it for the move, No error check on limits.
            LogFile.Log("TunePosition(" + self.MotorName + ") Current:" + str(self.CurrentPosition) + ", NewTarget: " + str(self.TargetPosition))
            self.MoveMotor() # Perform the move.
            self.CurrentPosition = self.TargetPosition = old
            self.CurrentAngle = self.TargetAngle = self.StepToAngle(self.TargetPosition)
            LogFile.Log("TunePosition(" + self.MotorName + ") set to " + str(self.CurrentPosition))
            self.LatestTuneSteps = delta # Record details of the last tune command received. So we can see it was handled.
            self.LatestTuneTime = Clock.Now()
            RPi.Write('tune complete ' + self.MotorName + ' ' + IntToTimeString(self.LatestTuneTime) + ' ' + str(delta))
            self.SendMotorStatus(immediate=True,codes='tup') # Tell RPi latest condition of the motor.
        else:
            RPi.Write('tune rejected ' + self.MotorName + ' ' + IntToTimeString(self.LatestTuneTime) + ' ' + str(delta) + ': Motor not configured')
            LogFile.Log("error : TunePosition(" + self.MotorName + ") Rejected, motor is not yet configured.")

    def SetPins(self,stepBCM,directionBCM,mode0BCM,mode1BCM,mode2BCM,enableBCM,faultBCM):
        self.StepBCM = stepBCM # Pin(stepBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This sends the MOVE pulse to the controller.
        self.StepBCM.SetValue(False) # (0) # Turn pin off.
        LogFile.Log("#", self.MotorName, 'Step pin', self.StepBCM.PinNumber)
        self.DirectionBCM = directionBCM # Pin(directionBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This sets the MOVE direction to the controller.
        self.DirectionBCM.SetValue(False) # (0)  # Turn pin off.
        LogFile.Log("#", self.MotorName, 'Direction pin', self.DirectionBCM.PinNumber)
        self.Mode0BCM = mode0BCM # Pin(mode0BCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode1BCM = mode1BCM # Pin(mode1BCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode2BCM = mode2BCM # Pin(mode2BCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This controls FULL vs MICRO stepping for the controller.
        self.Mode0BCM.SetValue(False) # (0)  # Turn pin off.
        self.Mode1BCM.SetValue(False) # (0)  # Turn pin off.
        self.Mode2BCM.SetValue(False) # (0)  # Turn pin off.
        #LogFile.Log("#", self.MotorName, 'Mode0 pin', self.Mode0BCM.PinNumber)
        #LogFile.Log("#", self.MotorName, 'Mode1 pin', self.Mode1BCM.PinNumber)
        #LogFile.Log("#", self.MotorName, 'Mode2 pin', self.Mode2BCM.PinNumber)
        self.EnableBCM = enableBCM # Pin(enableBCM, Pin.OUT, Pin.PULL_DOWN) # Set pin to OUTPUT. This enables/disabled the motor.
        self.EnableBCM.SetValue(False) # (0)  # Turn pin off.
        #LogFile.Log("#", self.MotorName, 'Enable pin', self.EnableBCM.PinNumber)
        self.FaultBCM = faultBCM # Pin(faultBCM, Pin.IN) # Set pin to INPUT. Will EARTH when triggered.
        #LogFile.Log("#", self.MotorName, 'Fault pin', self.FaultBCM.PinNumber)

    def SetConfig(self,gearratio,motorstepsperrev,microstepratio,minangle,maxangle,restangle,currentangle,orientation,backlashangle):
        #LogFile.Log("#", self.MotorName, 'gearratio', gearratio)
        #LogFile.Log("#", self.MotorName, 'motorstepsperrev', motorstepsperrev)
        #LogFile.Log("#", self.MotorName, 'microstepratio', microstepratio)
        #LogFile.Log("#", self.MotorName, 'minangle', minangle)
        #LogFile.Log("#", self.MotorName, 'maxangle', maxangle)
        #LogFile.Log("#", self.MotorName, 'restangle', restangle)
        #LogFile.Log("#", self.MotorName, 'currentangle', currentangle)
        #LogFile.Log("#", self.MotorName, 'orientation', orientation)
        #LogFile.Log("#", self.MotorName, 'backlashangle', backlashangle)
        self.GearRatio = gearratio
        self.MotorStepsPerRev = motorstepsperrev
        self.MicrostepRatio = microstepratio
        self.MinAngle = minangle
        self.MaxAngle = maxangle
        self.RestAngle = restangle
        self.CurrentAngle = currentangle
        self.Orientation = orientation
        self.BacklashAngle = backlashangle
        # Reapply dependent calculations.
        #self.FastTime = 0.0005 # The fastest pulse time for moving the motor.
        #self.SlowTime = 0.05 # The slowest pulse time for moving the motor.
        #self.DeltaTime = 0.003 # The acceleration amount moving from SlowTime to FastTime as the motor gets going.
        if self.MicrostepRatio != 1: self.UseMicrostepping = True # Allow microstepping to be used. Increases resolution 32times, but let torque.
        else: self.UseMicrostepping = False
        self.WaitTime = self.SlowTime # The time between pulses, starts slow, reduces as a move progresses. Resets every time a new target is set.
        self.StepDir = 1 # The direction of a particular move +/-1. It always represents a SINGLE FULL STEP.
        self.LastStepDir = 0 # Record the 'last' direction that the motor moved in. This may be useful for handling gear backlash. Starts at ZERO (No direction)
        self.DriftSteps = 0 # This is the number of steps 'error' that DriftTracking has identified. It must be incorporated back into motor movements as smoothly as possible. Consider backlash etc.
        # gearratio is the overall gearing of the entire transmission. 60 means 60 motor revs for 1 transmission rev.
        # Officially a NEMA17 motor has 200 (1.8Deg), or 400 steps (0.9deg) steps (each has XX substeps available, but with reduced accuracy/power)
        # - If using MICROSTEPPING, the precision is increased by up to 32x . Which is 0.056 degrees. The 16mm lens on the HQ Camera has 0.01 degree per pixel. So some gearing is probably needed, but not too strong.
        # - OR switch back to FULL STEPS and using higher gearing!! Needs to be 1:200 gearing in FULL STEP mode to match pixel resolution...
        # WARNING!!! MICROSTEPPING Typically reduces torque dramatically.
        # An example of the effect is shown here from https://www.machinedesign.com/archive/article/21812154/microstepping-myths
        # Full step     100.00% torque
        # 2 microsteps  70.71%
        # 4      -"-    38.27%
        # 8      -"-    19.51%
        # 16     -"-    9.80%
        # 32     -"-    4.91% <- Max on NEMA17, and probably too weak to achieve movement.
        # 64     -"-    2.45%
        # 128    -"-    1.23%
        # 256    -"-    0.61%
        # If we activate Microstepping, how do we set the Mode pins (Mode0,1,2) on the DRV8825 chip?
        steppinglist = {1 : {'power' : 100, 'mode0' : False, 'mode1' : False, 'mode2' : False},
                        2 : {'power' : 70, 'mode0' : True, 'mode1' : False, 'mode2' : False},
                        4 : {'power' : 40, 'mode0' : False, 'mode1' : True, 'mode2' : False},
                        8 : {'power' : 20, 'mode0' : True, 'mode1' : True, 'mode2' : False},
                        16 : {'power' : 10, 'mode0' : False, 'mode1' : False, 'mode2' : True},
                        32 : {'power' : 5, 'mode0' : True, 'mode1' : True, 'mode2' : True}}
        if self.UseMicrostepping: # If we're using microstepping, then we have 32 times more positions for a NEMA17 motor in each revolution, but only 5% of the power!
            self.MotorStepsPerRev = self.MotorStepsPerRev * self.MicrostepRatio
            try:
                self.MotorPower = steppinglist[self.MicrostepRatio]['power']
                self.MicrosteppingMode0 = steppinglist[self.MicrostepRatio]['mode0']
                self.MicrosteppingMode1 = steppinglist[self.MicrostepRatio]['mode1']
                self.MicrosteppingMode2 = steppinglist[self.MicrostepRatio]['mode2']
                if self.MicrostepRatio != 1:
                    LogFile.Log("Configure(" + self.MotorName + ") MicrostepRatio " + str(self.MicrostepRatio) + " " + str(self.MotorPower) + "% torque.")
            except Exception as e:
                LogFile.Log("error: steppermotor.Configure(" + self.MotorName + ") MicrostepRatio failed: " + str(e))
                LogFile.Log("error: steppermotor.Configure(" + self.MotorName + ") invalid MicrostepRatio (" + str(self.MicrostepRatio) + "). Please correct it.")
        self.MotorStepsPerAxisDegree = self.MotorStepsPerRev / 360.0
        self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio
        # AngleToStep and StepToAngle only work from here on!
        self.RestPosition = self.AngleToStep(self.RestAngle)
        self.CurrentPosition = self.TargetPosition = self.AngleToStep(self.CurrentAngle)
        self.MinPosition = self.AngleToStep(self.MinAngle) # Min clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.MaxPosition = self.AngleToStep(self.MaxAngle) # Max clockwise movement. Location of limit switch in steps (This is self calibrating when in use).
        self.RequestedAngle = self.CurrentAngle
        self.RequestedPosition = self.CurrentPosition
        return self.MotorConfigured

    def ConfigureMotor(self,line):
        """ This loads the motor configuration received from the RPi.
            It can override some default values in the configuration.
            All values are optional.
            Any value of 'none' is ignored.

            configure motor 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n
                0       1         2           3       4    5  6   7  8   9     10    11  12 13
                
            """
        #LogFile.Log("steppermotor.ConfigureMotor(",self.MotorName,") start.")
        #print("s.CM rec:",line)
        self.ConfigStartTime = Clock.Now()
        try:
            lineitems = line.split(' ')
            lc = len(lineitems)
            if lc > 2: 
                #print("s.CM Check clock",lineitems[2])
                Clock.UpdateClockFromString(lineitems[2]) # Check that the clock is as synchronised as possible.
            if lc > 4 and lineitems[4].lower() != 'none': # To apply to live copy.
                self.CurrentAngle = float(lineitems[4]) # Restore current position of the motor from the RPi's memory.
                self.CurrentPosition = self.AngleToStep(self.CurrentAngle)
            if lc > 5 and lineitems[5].lower() != 'none':
                self.MinAngle = float(lineitems[5]) # Set new minimum angle for motor.
                self.MinPosition = self.AngleToStep(self.MinAngle)
            if lc > 6 and lineitems[6].lower() != 'none':
                self.MaxAngle = float(lineitems[6]) # Set new maximum angle for motor.
                self.MaxPosition = self.AngleToStep(self.MaxAngle)
            if lc > 7 and lineitems[7].lower() != 'none':
                self.BacklashAngle = float(lineitems[7]) # Set new backlash angle for motor.
            if lc > 8 and lineitems[8].lower() != 'none':
                self.Orientation = int(lineitems[8]) # Set new orientation for motor.
            if lc > 9 and lineitems[9].lower() != 'none':
                self.FastTime = float(lineitems[9]) # Set new FASTEST PULSE time for motor.
            if lc > 10 and lineitems[10].lower() != 'none':
                self.SlowTime = float(lineitems[10]) # Set new SLOWEST PULSE time for motor.
            if lc > 11 and lineitems[11].lower() != 'none':
                self.TimeDelta = float(lineitems[11]) # Set new acceleration rate for motor.
            if self.WaitTime < self.FastTime: self.WaitTime = self.FastTime # Current motor speed cannot be faster than new fastest limit.
            if self.WaitTime > self.SlowTime: self.WaitTime = self.SlowTime # Current motor speed cannot be slower than new slowest limit.
            if lc > 12 and lineitems[12].lower() != 'none': # Must be within reasonable limits.
                temp = int(lineitems[12])
                if temp < 1: temp = 1
                elif temp > 30: temp = 30
                self.StatusTimer = timer(self.MotorName,temp) # Set new repeat time for sending motor status messages back to the RPi
            if lc > 13 and lineitems[13].lower() != 'none': # Enable/disable fault sensitivity. DRV8825 can then abort an observation.
                self.FaultSensitive = StringToBool(lineitems[13])
            self.MotorConfigured = True
            #LogFile.Log("steppermotor.ConfigureMotor(",self.MotorName,") success.")
        except Exception as e:
            LogFile.Log("steppermotor.ConfigureMotor(line) failed: " + str(e))
            print("steppermotor.ConfigureMotor() failed.")
        self.ConfigEndTime = Clock.Now()
        #LogFile.Log("steppermotor.ConfigureMotor(",self.MotorName,") end.")
        return self.MotorConfigured

    def MoveFullStep(self,stepsize=1):
        """ Move the motor one full step. Target must be initialized before calling this.
            If Microstepping is enabled, then this accepts 2 stepsize values.
                stepsize = 1 = Micro step movement.
                stepsize = 32 = Full step movement.
            If Microstepping is disabled, then this only accepts stepsize = 1 """
        if self.FaultBCM.GetValue() == False: # DRV8825 'fault' pin is triggered.
            if self.FaultSensitive: # The fault matters.
                if not self.FaultDetected:
                    print("Setting FAULT status.")
                    self.FaultDetected = True
                    LogFile.Log("steppermotor.MoveFullStep(", self.MotorName, ') DRV8825 fault - terminating.')
                return
            else: # The fault does not matter.
                if not self.FaultDetected: # Only report once.
                    LogFile.Log("steppermotor.MoveFullStep(", self.MotorName, ') DRV8825 fault - ignored.')
                    print("Setting FAULT status.")
                    self.FaultDetected = True
        else: # No DRV8825 fault, clear any previous fault status.
            if self.FaultDetected: 
                LogFile.Log("steppermotor.MoveFullStep(", self.MotorName, ') DRV8825 fault - cleared.')
                self.FaultDetected = False # No fault.
        if abs(self.StepDir) != 1: # self.StepDir must be +1 or -1
            #raise Exception ('MoveFullStep: ' + self.MotorName + ' StepDir " + str(self.StepDir) + " is invalid. Must be +/-1')
            LogFile.Log('MoveFullStep: ' + self.MotorName + ' StepDir " + str(self.StepDir) + " is invalid. Must be +/-1')
            return
        if (self.StepDir * self.Orientation) > 0:
            self.DirectionBCM.SetValue(True) # value(1) # Move motor forward.
        else:
            self.DirectionBCM.SetValue(False) # value(0) # Move motor backwards.
        if self.StepDir != self.LastStepDir: # We have a change of direction.
            LogFile.Log('MoveFullStep: ' + self.MotorName + ' changed direction (' + str(self.StepDir) + ' vs ' + str(self.LastStepDir) + '). Backlash?')
        self.LastStepDir = self.StepDir # Record the direction that the motor is moving in. This may be useful for handling gear backlash etc.
        # Set DRV8825 driver mode to FULL STEPPING.
        if self.UseMicrostepping: # We can switch between FULL and MICRO steps to have both speed and fine control.
            if stepsize > 1:
                self.Mode0BCM.SetValue(False) # value(0) # Full steps # Keep DRV8825 MODE pins LOW.
                self.Mode1BCM.SetValue(False) # value(0) # Full steps # Keep DRV8825 MODE pins LOW.
                self.Mode2BCM.SetValue(False) # value(0) # Full steps # Keep DRV8825 MODE pins LOW.
            else:
                self.Mode0BCM.SetValue(self.MicrosteppingMode0) # value(self.MicrosteppingMode0) # Micro steps set Mode pins.
                self.Mode1BCM.SetValue(self.MicrosteppingMode1) # value(self.MicrosteppingMode1) # Micro steps set Mode pins.
                self.Mode2BCM.SetValue(self.MicrosteppingMode2) # value(self.MicrosteppingMode2) # Micro steps set Mode pins.
        else: # We use full steps only. Less fine control, but faster and stronger movement.
            self.Mode0BCM.SetValue(False) # value(0) # Full steps # Keep DRV8825 MODE pins LOW.
            self.Mode1BCM.SetValue(False) # value(0) # Full steps # Keep DRV8825 MODE pins LOW.
            self.Mode2BCM.SetValue(False) # value(0) # Full steps # Keep DRV8825 MODE pins LOW.
        # Send MOVE pulse to controller.
        if self.MotorEnabled: # If we've disabled the motor, then perform everything except the move pulse.
            #print ('Sending motor pulse...')
            self.StepBCM.SetValue(True) # value(1)
            time.sleep(self.WaitTime)
            self.StepBCM.SetValue(False) # value(0)
            time.sleep(self.WaitTime)
        self.CurrentPosition += (self.StepDir * stepsize)
        self.CurrentAngle = self.StepToAngle(self.CurrentPosition)
        if self.UseMicrostepping:
            if self.CurrentPosition % self.MicrostepRatio == 0: # We're on a full-step-boundary.
                self.FullStepBoundary = True
            else:
                self.FullStepBoundary = False
        # Else. FullStepBoundary remains True all the time.
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
            LogFile.Log("steppermotor.EfficiencyCheck(): Inefficient move:",self.CurrentPosition,"to",self.TargetPosition,motorsteps,"steps, suggest",inversemove)
        return inversemove

    def MoveMotor(self):
        """ Move the motor to the new target position. Target must be defined before calling this.
            If this is handling a very large move, it may take some time, so it can also trigger
            sending MotorStatus messages back to the RPi. Because some moves are quite long, this 
            also processes UART communication periodically too. """
        # *Q* Choosing MotorSteps should take into account that it may be faster to go from 359Deg to 1Deg directly instead of winding backwards 358 degrees.
        #     Decide which direction to move.
        #     Make sure that the motor position counter handles wrapping around in both directions.
        #     Respect an arbitrary 'turn back' point to avoid cables becoming tangled.
        #     Does minangle/maxangle become redundant?
        #     Find any/all checks against MinAngle and MaxAngle too.
        MotorSteps = self.TargetPosition - self.CurrentPosition # How many steps to take?
        _ = self.EfficiencyCheck(MotorSteps) # Check if this is the most efficient move.
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call MoveFullStep().
        #FullStepCount = 0
        #MicroStepCount = 0
        if MotorSteps != 0:
            StatusLed.Task(self.MotorName) # Flash status LED with motor specific colour.
            if abs(MotorSteps) > 100: # Large moves will reset the 'OnTarget' flag.
                #LogFile.Log('steppermotor.MoveMotor: Large move (',MotorSteps,'). OnTarget=False')
                self.OnTarget = False
        while MotorSteps != 0:
            # If supporting microstepping. If we're on a full step boundary and the move is large enough we can use FULL STEPS for speed.
            # We can make a FULL step.
            if self.UseMicrostepping: # Switch between FULL and MICRO stepping as required.
                if abs(MotorSteps) > self.MicrostepRatio and self.FullStepBoundary:
                    # We have a long way to go, and we are at a safe point, so move a FULL STEP.
                    # Only trigger a FULL STEP if we're on a full step boundary. Otherwise the motor may 'settle' to the closest boundary later on and cause drift.
                    MotorSteps = MotorSteps - (self.StepDir * self.MicrostepRatio) # REDUCE (-ve) the number of steps to take.
                    self.MoveFullStep(stepsize=self.MicrostepRatio) # This will update CurrentPosition on-the-fly as the motor moves.
                    #FullStepCount += 1
                else:
                    # We're only moving a small distance or we're not on a full step boundary, so use MICROSTEPPING.
                    MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
                    self.MoveFullStep(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
                    #MicroStepCount += 1
            else: # We're not using microstepping, so we're just moving full steps.
                MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
                self.MoveFullStep(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
                #FullStepCount += 1
            self.SendMotorStatus(codes='mov') # Long slow moves would cause RPi to trigger a reset, so send regular status updates.
            for i in range(1): # *Q* does this need to be twice anymore? UART seems more reliable in latest version of Micropython. Could use larger buffers instead?
                RPi.BufferInput() # Keep polling for input from the RPi.
                RPi.WritePoll() # Keep sending data to RPi.
            StatusLed.Task(self.MotorName) # Flash status LED with motor specific colour.
        self.CheckOnTarget() # Are we actually pointing at the target?
        if self.CurrentPosition != self.TargetPosition: # Did the motor reach intended position? (May not be the requested target if movement limits reached)
            LogFile.Log("MoveMotor(" + self.MotorName + "): End. CurrentPosition (" + str(self.CurrentPosition) + ") is NOT TargetPosition (" + str(self.TargetPosition) + ")!")
        StatusLed.Task('idle')

    def MoveMotor_xxx(self):
        """ Move the motor to the new target position. Target must be defined before calling this.
            If this is handling a very large move, it may take some time, so it can also trigger
            sending MotorStatus messages back to the RPi. """
        MotorSteps = self.TargetPosition - self.CurrentPosition # How many steps to take?
        self.WaitTime = self.SlowTime # Start with slow move pulses. This reduces each time we call MoveFullStep().
        FullStepCount = 0
        MicroStepCount = 0
        if MotorSteps != 0:
            StatusLed.Task(self.MotorName) # Flash status LED with motor specific colour.
            if abs(MotorSteps) > 100: # Large moves will reset the 'OnTarget' flag.
                LogFile.Log('steppermotor.MoveMotor: Large move (',MotorSteps,'). OnTarget=False')
                self.OnTarget = False
        while MotorSteps != 0:
            # If supporting microstepping. If we're on a full step boundary and the move is large enough we can use FULL STEPS for speed.
            # We can make a FULL step.
            if self.UseMicrostepping: # Switch between FULL and MICRO stepping as required.
                if abs(MotorSteps) > self.MicrostepRatio and self.FullStepBoundary:
                    # We have a long way to go, and we are at a safe point, so move a FULL STEP.
                    # Only trigger a FULL STEP if we're on a full step boundary. Otherwise the motor may 'settle' to the closest boundary later on and cause drift.
                    MotorSteps = MotorSteps - (self.StepDir * self.MicrostepRatio) # REDUCE (-ve) the number of steps to take.
                    self.MoveFullStep(stepsize=self.MicrostepRatio) # This will update CurrentPosition on-the-fly as the motor moves.
                    FullStepCount += 1
                else:
                    # We're only moving a small distance or we're not on a full step boundary, so use MICROSTEPPING.
                    MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
                    self.MoveFullStep(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
                    MicroStepCount += 1
            else: # We're not using microstepping, so we're just moving full steps.
                MotorSteps = MotorSteps - self.StepDir # REDUCE (-ve) the number of steps to take.
                self.MoveFullStep(stepsize=1) # This will update CurrentPosition on-the-fly as the motor moves.
                FullStepCount += 1
            self.SendMotorStatus(codes='mov') # Long slow moves would cause RPi to trigger a reset, so send regular status updates.
            for i in range(1): # *Q* does this need to be twice anymore? UART seems more reliable in latest version of Micropython. Could use larger buffers instead?
                RPi.BufferInput() # Keep polling for input from the RPi.
                RPi.WritePoll() # Keep sending data to RPi.
            StatusLed.Task(self.MotorName) # Flash status LED with motor specific colour.
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
            #print("motorcontrol.SendMotorStatus(",self.MotorName,"): Start")
            self.StatusStartTime = Clock.Now()
            if self.SendStatus == False: # Don't send status message.
                RPi.Write('# SendMotorStatus ' + IntToTimeString(Clock.Now()) + ' ' + self.MotorName + ' disabled. ' + str(codes))
                print("SendMotorStatus",self.MotorName,"currently disabled.",codes)
                return
            line = 'motor status '
            line += IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
            line += self.MotorName + ' '
            line += BoolToString(self.Trajectory.Valid) + ' ' # TrajectoryValid
            line += IntToTimeString(self.Trajectory.ValidUntil()) + ' '
            line += str(len(self.Trajectory.TrajectoryList)) + ' '
            line += str(self.CurrentPosition) + ' '
            line += str(self.CurrentAngle) + ' '
            line += BoolToString(self.MotorConfigured) + ' ' # MotorConfigured
            line += BoolToString(self.OnTarget) + ' ' # Motor is on target or not.
            line += str(self.WaitTime * 2) + ' ' # The pulse period (indicates speed) of the motor.
            line += str(VMot()) + ' ' # Measure the motor power voltage from ADC0. Will return '0' if adc0 is not configured as an 'adc' input.
            line += str(codes) + ' ' # Optional codes added to status message.
            RPi.Write(line) # Send over UART to RPi.
            self.StatusEndTime = Clock.Now()
            # Reset the status timer.
            self.StatusTimer.Reset()
            #print(self.MotorName,"status next due in",self.StatusTimer.Remaining(),"s. at",IntToTimeString(self.StatusTimer.NextDue),"Repeat",self.StatusTimer.RepeatSeconds,"s.", codes)

# Define pins for motorcontroller chips.
AzimuthStepBCM = GPIOpin(board.GP29) # Tiny RP2040
AltitudeStepBCM = GPIOpin(board.GP28) # Tiny RP2040
CommonDirectionBCM = GPIOpin(board.GP27) # Tiny RP2040
CommonMode0BCM = GPIOpin(board.GP3) # Tiny RP2040
CommonMode1BCM = GPIOpin(board.GP4) # Tiny RP2040
CommonMode2BCM = GPIOpin(board.GP5) # Tiny RP2040
CommonEnableBCM = GPIOpin(board.GP2) # Tiny RP2040
AzimuthFaultBCM = GPIOpin(board.GP6) # Tiny RP2040
AltitudeFaultBCM = GPIOpin(board.GP7) # Tiny RP2040

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
AltitudeFaultBCM.SetDirection(digitalio.Direction.INPUT)

# Configure Motors.
Azimuth = steppermotor('azimuth')
Azimuth.SetPins(stepBCM=AzimuthStepBCM,directionBCM=CommonDirectionBCM,mode0BCM=CommonMode0BCM,mode1BCM=CommonMode1BCM,mode2BCM=CommonMode2BCM,enableBCM=CommonEnableBCM,faultBCM=AzimuthFaultBCM) # Direct control over Azimuth motor.
Azimuth.SetConfig(gearratio=(60 * 4),motorstepsperrev=400,microstepratio=1,minangle=45.0,maxangle=315.0,restangle=180.0,currentangle=180.0,orientation=1,backlashangle=0.5)
Altitude = steppermotor('altitude')
Altitude.SetPins(stepBCM=AltitudeStepBCM,directionBCM=CommonDirectionBCM,mode0BCM=CommonMode0BCM,mode1BCM=CommonMode1BCM,mode2BCM=CommonMode2BCM,enableBCM=CommonEnableBCM,faultBCM=AltitudeFaultBCM) # Direct control over Altitude motor.
Altitude.SetConfig(gearratio=(60 * 4),motorstepsperrev=400,microstepratio=1,minangle=0.0,maxangle=90.0,restangle=0.0,currentangle=0.0,orientation=-1,backlashangle=0.0)
Motors = [Azimuth, Altitude] # Control over 'all' motors.

class picosession():
    def __init__(self):
        self.SessionStart = time.time()
        self.AutonomousControl = False # Triggers movement of the motors when they are configured and trajectories loaded.
        self.RemoteControl = False # Allows movement of the motors when they are configured, regardless of trajectories existing.
        self.Quit = False # Set to TRUE to terminate the session.
        self.TrajectorySafetyms = 2 * 60 * 1000 # How many milliseconds can a valid trajectory remain in use before comms failure terminates it? == 2 minutes.
        self.TrajectorySafetyFlushes = 0 # How many times have we had to flush the trajectories for safety when comms seemed to fail?
        self.FailsafeLatch = False # Latch to prevent 'failsafe' messages flooding the commication buffers when safety flush is triggered.

    def MovePermission(self):
        # Decide if the microcontroller can accept remote control of the motors.
        # They will move under the direction of the remote RPi.
        result = True
        for i in Motors: # for ALL motors.
            if not i.MotorConfigured: result = False # Motor must be configured.
        #if result != self.RemoteControl:
        #    RPi.Write('RemoteControl ' + str(result))
        self.RemoteControl = result
        # Decide if the microcontroller can have autonomous control of the motors.
        # They may start moving immediately.
        if not Clock.ClockSynchronised: result = False # Clock must be synchronised.
        for i in Motors: # for ALL motors.
            if not i.Trajectory.Valid: result = False # Trajectory must be valid.
        #if result != self.AutonomousControl:
        #    RPi.Write('AutonomousControl ' + BoolToString(result))
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
        line = "session status "
        i = time.time() - RPi.StartTime # Alive seconds. Use CPU clock not synchronised clock.
        line += IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        line += BoolToString(Clock.ClockSynchronised) + ' ' # Do the RPi and microcontroller clocks agree?
        line += BoolToString(self.AutonomousControl) + ' '  # Can motors drive themselves? Fully configured and trajectory known.
        line += BoolToString(self.RemoteControl) + ' '  # Can motors be commanded remotely? Fully configured.
        line += str(i) + ' ' # Alive seconds. Use CPU clock, not synchronised clock.
        line += str(self.TrajectorySafetyFlushes) + ' ' # How many times has the trajectory been flushed for safety when comms failed?
        line += str(codes) + ' ' # Add optional extra codes.
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
        #for i in Motors: i.ReportStamps() # Report timestamps to aid tracing situations where motor status messages stop for a motor sometimes.

    def AutoMoveMotors(self): # Trigger movement of the motors.
        """ Call this to check the current position of each motor against their trajectory.
            If the motor needs to move, this will perform the motion. """
        overallresult = False
        self.MovePermission() # Is motor still capable of autonomous movement?
        if self.AutonomousControl:
            overallresult = True
            for i in Motors:
                result = i.TargetExpectedAngle() # Set target for the motor based upon trajectory if available.
                if result: # Target was successfully set.
                    if i.TargetPosition != i.CurrentPosition: i.MoveMotor()
                else: # Target was not successfuly set.
                    LogFile.Log('AutoMoveMotors',i.MotorName,'failed: TargetExpectedAngle returned', result)
                    overallresult = False
        return overallresult

def CheckVersionCompatibility(rpiversion):
    """ The Raspberry Pi has sent the version number for pilomar.py
        Check that it's compatible with this code.py program.
        This issues a log file warning. It will not terminate the program. """
    compversion = rpiversion[:rpiversion.rindex('.')]
    if not compversion in ACCEPTABLERPIVERSIONS:
        LogFile.Log('CheckVersionCompatibility',rpiversion,'not in',str(ACCEPTABLERPIVERSIONS))

Session = picosession() # Instantiate a sesson object.

def ProcessInput(line):
    lineitems = line.split(' ')
    if lineitems[0] == 'exit':
        print('exit command received.')
        LogFile.Log('exit command received.')
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
        #BoardLed.Disable()
    elif line.startswith('leds on'): # Enable the LEDs to show processing.
        StatusLed.Enable() # Enable the onboard status LED.
        #BoardLed.Enable()
    else:
        RPi.Write('error: unrecognised RPi command: ' + line)

class memorymanager():
    def __init__(self):
        self.currmem = None # Current memory free value.
        self.GCCount = 0 # How often has garbage collector run?
        self.Poll()

    def Poll(self): # Check current memory and trigger memory garbage collection early if needed.
        self.currmem = gc.mem_free()
        if self.currmem < 3000:
            gc.collect()
            self.GCCount += 1 # Increase count of garbagecollector runs.

MemMgr = memorymanager()

print ('Starting...')
# *Q* Following code could be merged/replaced by RPi.Reset() ?
for i in range(2): RPi.Write('#' * 20) # Send dummy lines through the UART line to flush out any junk.
RPi.Write('controller started') # Tell the remote device we're up and running. Replaced 'pico started' message.
RPi.Write('controller version ' + VERSION) # Tell the remove device which software version is running.
RPi.Write('# circuitpython ' + Bootline) # Tell what version of circuitpython is in use.
RPi.Write('# gc.mem_free ' + str(gc.mem_free())) # Tell how much memory is initially available.
# Report back which motors are configured.
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
            LogFile.Log("Main:Logfile.SendCheck failed.",e)
            print("Main:Logfile.SendCheck failed.",e)
            
        try:
            line = RPi.Read() # Any input from the Raspberry Pi in the cache? 
            if len(line) != 0: ProcessInput(line) # Process it.
        except Exception as e:
            LogFile.Log("Main:RPi.Read failed.",e)
            print("Main:RPi.Read failed.",e)
            print("Main:Failed on",line)
            
        try:
            Session.TrajectorySafety() # If no recent receipt from RPi, assume comms break take precautions... Clear trajectories?
        except Exception as e:
            LogFile.Log("Main: SessionTrajectorySafety() failed.",e)
            print("Main: SessionTrajectorySafety() failed.",e)
            
        if Session.Quit: break 
        
        try:
            if SessionTimer.Due(): Session.SendSessionStatus(codes='tmr') # Send session status messages.
        except Exception as e:
            LogFile.Log("Main: SessionTimer failed.",e)
            print("Main: SessionTimer failed.",e)
            
        try:
            if CpuTimer.Due(): MicroControllerLog() # Send microcontroller status message.
        except Exception as e:
            LogFile.Log("Main: CpuTimer failed.",e)
            print("Main: CpuTimer failed.",e)
            
        try:
            Session.SendMotorStatus('azimuth',codes='tmr') # Send azimuth status message.
        except Exception as e:
            LogFile.Log("Main: Azimuth status failed.",e)
            print("Main: Azimuth status failed.",e)
            
        try:
            Session.SendMotorStatus('altitude',codes='tmr') # Send altitude status message.
        except Exception as e:
            LogFile.Log("Main: Altitude status failed.",e)
            print("Main: Altitude status failed.",e)
            
        try:
            RPi.WritePoll() # Send anything in the transmit buffer if it's safe.
        except Exception as e:
            LogFile.Log("Main: RPi.WritePoll() failed.",e)
            print("Main: RPi.WritePoll() failed.",e)
            
        try:
            Session.AutoMoveMotors() # Move motors if allowed to. 
        except Exception as e:
            LogFile.Log("Main: AutoMoveMotors failed.",e)
            print("Main: AutoMoveMotors failed.",e)
        try:
            MemMgr.Poll() # Check memory condition.
        except Exception as e:
            LogFile.Log("Main: MemMgr.Poll() failed.",e)
            print("Main:MemMgr.Poll() failed.",e)
            
except Exception as e:
        neatprint('Mainloop failed:', str(e))
        StatusLed.Task('error')
        neatprint(e.args)

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


