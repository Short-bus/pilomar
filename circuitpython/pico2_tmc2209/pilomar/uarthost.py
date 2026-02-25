# pilomar/uarthost.py 
# Class to provide serial communication between microcontroller and Raspberry Pi over UART channel.

import board
from busio import UART as busio_UART # Only need the UART and I2C features.
import time
from pilomar.helpers import * # Utility classes and methods used in this program. (logfile, clock, gpio etc)

class uarthost():
    """ UART serial communication handler.
        Handles buffering of received and transmitted data over serial line. """
    def __init__(self,name=None,channel=0,logfile=None,exceptioncounter=None,statusled=None,clock=None): # *Q* Add StatusLed and ExceptionCounter references too.
        self.ExceptionCounter = exceptioncounter # Point to ExceptionCounter instance.
        self.StatusLed = statusled # Point to StatusLed instance.
        self.Clock = clock # Point to Clock instance.
        self.Log = logfile.Log # Point to logfile handler.
        self.BaudRate = 115200
        if name == None: name = 'UART' + str(channel) # Default to useful name.
        if channel == 0: # UART0
            self.uart = busio_UART(board.GP0,board.GP1,baudrate=self.BaudRate,receiver_buffer_size=1024,timeout=0) # Define UART0 as the serial comms channel to the host.
            print('UART TX=', board.GP0, 'UART RX=', board.GP1)
        else: # UART1?
            raise Exception('uarthost on microcontroller is only configued for UART channel 0.')
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
        self.MaxReceivedLines = 20 # We can buffer up to 20 received lines before discarding.
        self.MaxSendLines = 30 # We can buffer up to 30 lines waiting to be sent before discarding.
        self.WriteGapms = 100 # ms pause between each chunk of data written.
        self.Name = name
        self.ReceivingLine = '' # Current line being received. It's constructed here until '\n' received.
        self.WriteQueue = [] # List of queued messages to be sent when safe.
        self.WriteDrops = 0 # Number of messages dropped because queue filled.
        self.ReadDrops = 0 # How many received messages are dropped because input buffer is full?
        self.LastTxms = self.LastRxms = self.ticks_ms() # Milliseconds since last transmission.
        # ShowUartTraffic :
        # True - UART messages sent to terminal. False - UART messages not replicated to terminal.
        # When disabled it makes other debug messages more visible on the terminal.
        self.ShowUartTraffic = True 
        print(self.Name, self.uart)

    def Reset(self):
        """ Reset communications (flush output buffers). """
        self.WriteQueue = [] # Empty the write queue.
        self.ReceivedLines = [] # Empty the input queue.
        self.ExceptionCounter.Reset() # Reset the ExceptionCounter also.
        for i in range(2): self.Write('#' * 20) # Send dummy lines through the UART line to flush out any junk.
        #self.Write('# CP env ' + str(Bootline) + ' ver ' + str(CircuitPythonVersion))
        #self.Write('# CP mem alloc ' + str(gc.mem_alloc()) + ' free ' + str(gc.mem_free()))
        #self.Write('# FEATURES ' + str(FEATURES))
        #self.Write('controller started') # Tell the remote device we're up and running.
        #self.Write('controller version ' + str(VERSION)) # Tell the remote device which software version is running.
        
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
            self.StatusLed.Task('coms')
            LoopCounter += 1
            CharsToProcess = '' # No characters to process yet.
            if LoopCounter > 20: break # Max 20 reads performed per call.
            try:
                bchar = self.uart.read() # Read entire waiting queue.
                CharsToProcess = ''.join([chr(b) for b in bchar]) # Convert to string.
                self.CharactersRead += len(CharsToProcess) # Count characters read.
            except Exception as e:
                #LogFile.Log('uarthost.BufferInput: uart.read() or conversion error:',e)
                self.Log('uarthost.BufferInput: uart.read() or conversion error:',e)
                self.ExceptionCounter.Raise() # Increment exception count for the session.
            # Process each new character in turn.
            if len(CharsToProcess) > 0:
                for cchar in CharsToProcess:
                    self.ReceivingLine += cchar
                    if cchar == '\n': # End of line
                        self.LinesRead += 1
                        if len(self.ReceivingLine) > 0 and self.ReceivingLine[-1] == '\n':
                            line = self.ReceivingLine.strip() # Clear special characters.
                            if len(line) > 0: # Something to process.
                                if len(self.ReceivedLines) < self.MaxReceivedLines: # Only buffer 10 lines, discard the rest. No space!
                                    self.ReceivedLines.append(line) # Add to list of lines to handle.
                                    line = self.RemoveChecksum(line)
                                    report = 'rec: ' + line
                                    if self.ShowUartTraffic: print(report) # Report all receipts to serial out.
                                    if line[0] != "#": # Acknowledge receipt of all messages except comments via the log file back to the RPi too.
                                        x = line.split(' ')[-1] # Last entry should be message sequence number.
                                        if x.startswith('['): report = 'rec: ' + x # If we have message sequence number, just report that back to the RPi.
                                        #LogFile.Log(report)
                                        self.Log(report)
                                else:
                                    print('uarthost.BufferInput full. Ignored: ' + line)
                                    self.ReadDrops += 1
                        self.ReceivingLine = '' # Start a new receiving line with the next character received.
            self.LastRxms = self.ticks_ms() # When was last message received?
        self.StatusLed.Task('idle')
    
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
                print('uarthost.Read: Rejected checksum : ' + line)
                #LogFile.Log('uarthost.Read: Rejected checksum :',line)
                self.Log('uarthost.Read: Rejected checksum :',line)
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
        self.StatusLed.Task('coms')
        if len(self.WriteQueue[0]) > self.WriteChunk: # Pull max 20 chars from write queue.
            line = self.WriteQueue[0][:self.WriteChunk]
            self.WriteQueue[0] = self.WriteQueue[0][self.WriteChunk:]
        else: # Pull the whole remaining line from the queue.
            line = self.WriteQueue.pop(0) + "\n"
        if len(line.strip()) == 0:
            print('uarthost.WritePoll: ignored null line in WriteQueue.')
        byteline = line.encode('utf-8') # Convert to bytearray.
        self.uart.write(byteline) # Physical write.
        if line[-1] == "\n": self.LinesWritten += 1
        self.CharactersWritten += len(line)
        self.LastTxms = self.ticks_ms()
        self.StatusLed.Task('idle')

    def Write(self,line,log=True):
        # Add a line to the write queue. It's physically sent separately by WritePoll()
        # It queues a limited number of messages for sending. 
        # After that, the queue only accepts extra messages if force==True.
        # Most communication is self-recovering, so it doesn't usually matter if we have to abandon a
        # message, the message will be raised gain soon.
        line = line.strip() # Clean the line.
        if len(line) > 0:
            while len(self.WriteQueue) >= self.MaxSendLines: # Only buffer 20 lines. Save memory.
                self.WriteQueue.pop(1) # Drop the 2nd entry, the first may already be partially transmitted.
                self.WriteDrops += 1
            self.WriteQueue.append(self.AddChecksum(line))
            if self.ShowUartTraffic: print('controller queueing: ' + line)

    def IntToTimeString(self,timestamp):
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

    def Heartbeat(self):
        """ Send Heartbeat signal to the RPi. """
        self.Write('controller heartbeat ' + self.IntToTimeString(self.Clock.Now()) + " on " + self.IntToTimeString(time.time()))
