#!/usr/bin/python

# Pilomar's cpu monitor class.
# Also provides some measurements of RPi's voltage/current measurements.
# Also provides read access to settings from config.txt file.
# Also provides measurement of CPU temperature.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from pilomaroscommand import oscommand # Pilomar's OS Command execution.
from pilomartimer import timer # Pilomar's timer class.
from gpiozero import CPUTemperature
from datetime import datetime

class cpumonitor(): # 1 references.
    """ Simple class to monitor the CPU load of the RPi.
        This periodically polls the CPU load and establishes some metrics. """

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.Logger = logger # Logger instance.
        self.Log = self._NullLogger # No log method.
        self.ReportException = self._NullLogger # Cannot report exception details to logfile.
        self.RaiseException = self._NullLogger # Cannor report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        self.Log("pilomarcpu.SetLogger(",self.Name,"): Linked to this log file.",terminal=False)

    def _NullLogger(self,*args, **kwargs):
        """ Null logger. Absorbs parameters and .Log call but does nothing. 
            Use this when there is no logger defined. """
        return

    def __init__(self,logger=None,name='',period=60):
        self.Name = name # Allow an instance name to be assigned.
        self.SetLogger(logger) # CamLog # Handle to the class that handles logging and error tracing.
        self.oscommand = oscommand(logger=self.Log) # Create OS command executor.
        self.osCmd = self.oscommand.Execute
        self.CPUTimer = timer(period) # Set timer for 60 seconds.
        self.MeasuredTime = datetime.now()
        # Overall CPU load figures.
        self.CpuUsed = 0 # Cpu used slots since system start
        self.CpuIdle = 0 # Cpu idle slots since system start
        self.CpuBusy = 0 # Percentage busy over Poll period.
        self.BusyHistory = [] # List of last 10 busy percentage figures.
        self.CpuTemp = 0 # Reported CPU temperature.
        self.CurrFreq = None # Current frequency
        self.PrevFreq = None # The previous frequency measure. Updated when checked by FreqChanged() method.
        self.MinFreq = None # Minimum frequency
        self.MaxFreq = None # Maximum frequency
        self.ClockPercent = None # Is the CPU being throttled? 100 = 100% full speed, anything lower means it's idling a bit.
        # Individual CORE load figures.
        self.CoreList = ['cpu0','cpu1','cpu2','cpu3'] # These are the cores to measure.
        self.CoreUsed = [0] * len(self.CoreList) # Individual core used slots since system start.
        self.CoreIdle = [0] * len(self.CoreList) # Individual core idle slots since system start.
        self.CoreBusy = [0] * len(self.CoreList) # Individual core busy slots since system start.
        self.PowerTimestamp = datetime.now()
        self.PowerData = {'timestamp':self.PowerTimestamp}
        self.ThrottleTimestamp = datetime.now()
        self.ThrottleData = {'timestamp':self.ThrottleTimestamp} # Clear out the readings.
        self.PollAll(force=True) # Update the stats initially.

    def FreqChanged(self):
        """ Call this to see if the clock frequency has changed since you last checked. """
        result = False
        if self.CurrFreq != None: # We have a current measure.
            if self.PrevFreq != None and self.PrevFreq != self.CurrFreq: # Frequency changed.
                result = True
            self.PrevFreq = self.CurrFreq # Save this clock frequency for the next comparison.
        return result

    def IsThrottled(self):
        """ Return TRUE if CPU appears to be throttled. """
        result = False
        if self.CurrFreq != None and self.MaxFreq != None and self.CurrFreq < self.MaxFreq: result = True
        return result

    def MinSpeed(self):
        """ Return TRUE if CPU appears to be running a minimum clock speed. """
        result = False
        if self.CurrFreq != None and self.MinFreq != None and self.CurrFreq <= self.MinFreq: result = True
        return result

    def FullSpeed(self):
        """ Return TRUE if CPU appears to be running at full clock speed. """
        result = False
        if self.CurrFreq != None and self.MaxFreq != None and self.CurrFreq >= self.MaxFreq: result = True
        return result

    def LogCpuInfo(self):
        """ Record CPU information to the main log file. """
        cCmd = 'cat /proc/cpuinfo'
        listlines = self.osCmd(cCmd)
        for line in listlines: self.Log(line,terminal=False)

    def MeasurePower(self):
        """ Update the dictionary containing current and voltage measurements
            from the RPi. ONLY works on RPi5 currently. 
            
            vcgencmd pmic_read_adc generates output like this... 
            
             3V7_WL_SW_A current(0)=0.05855580A
               3V3_SYS_A current(1)=0.06148359A
               1V8_SYS_A current(2)=0.13272650A
              DDR_VDD2_A current(3)=0.13955800A
              DDR_VDDQ_A current(4)=0.00980400A
               1V1_SYS_A current(5)=0.19811380A
                0V8_SW_A current(6)=0.34157550A
              VDD_CORE_A current(7)=5.03652000A
               3V3_DAC_A current(17)=0.00006105A
               3V3_ADC_A current(18)=0.00054945A
               0V8_AON_A current(16)=0.00531135A
                  HDMI_A current(22)=0.02161170A
             3V7_WL_SW_V volt(8)=3.61069200V
               3V3_SYS_V volt(9)=3.29982600V
               1V8_SYS_V volt(10)=1.81684800V
              DDR_VDD2_V volt(11)=1.10109800V
              DDR_VDDQ_V volt(12)=0.60366240V
               1V1_SYS_V volt(13)=1.10292900V
                0V8_SW_V volt(14)=0.80292960V
              VDD_CORE_V volt(15)=0.89369880V
               3V3_DAC_V volt(20)=3.29944700V
               3V3_ADC_V volt(21)=3.30402600V
               0V8_AON_V volt(19)=0.79618980V
                  HDMI_V volt(23)=4.92450000V
                 EXT5V_V volt(24)=4.92450000V
                  BATT_V volt(25)=0.00341880V
      
        It sets self.PowerData dictionary with values like...
            {'timestamp':....,
             'EXT5V':{'V':4.9245},
             '3V3_SYS':{'V':3.299826,'A':0.06148359},
             
            """
        self.PowerTimestamp = datetime.now()
        self.PowerData['timestamp'] = self.PowerTimestamp
        cCmd = 'vcgencmd pmic_read_adc'
        lines = self.osCmd(cCmd)
        for rawline in lines:
            #print('MeasurePower: rawline',rawline)
            line = rawline.strip()
            lineitems = line.split(' ')
            if len(lineitems) == 2 and lineitems[1][-1] in ['A','V']:
                point = lineitems[0][:-2]
                unit = lineitems[0][-1]
                measure = float(lineitems[1].split('=')[1][:-1])
                #print('MeasurePower: point',point)
                #print('MeasurePower: unit',unit)
                #print('MeasurePower: measure',measure)
                entry = self.PowerData.get(point,{})
                entry[unit] = measure
                # Store min/max too.
                minlab = "min_" + unit
                maxlab = "max_" + unit
                minval = min(measure,entry.get(minlab,99999))
                maxval = max(measure,entry.get(maxlab,-99999))
                entry[minlab] = minval
                entry[maxlab] = maxval
                self.PowerData[point] = entry

    def MeasureThrottle(self):
        """ Update the dictionary containing the various throttle measurements for the CPU.
            vcgencmd get_throttled
            returns
            throttled=0x0

            Bit	        Hexadecimal value	        Meaning
            0           0x1                         Undervoltage detected
            1           0x2                         Arm frequency capped
            2           0x4                         Currently throttled
            3           0x8                         Soft temperature limit active
            16          0x10000                     Undervoltage has occurred
            17          0x20000                     Arm frequency capping has occurred
            18          0x40000                     Throttling has occurred
            19          0x80000                     Soft temperature limit has occurred

            """
        self.ThrottleTimestamp = datetime.now()
        self.ThrottleData = {} # Clear out the readings.
        self.ThrottleData['timestamp'] = self.ThrottleTimestamp
        cCmd = 'vcgencmd get_throttled'
        lines = self.osCmd(cCmd)
        for line in lines:
            lineitems = line.strip().split('=')
            if len(lineitems) > 1:
                value = int(lineitems[1],16) # Convert from Hex to integer.
                if value & 0x1: self.ThrottleData['UndervoltageDetected'] = True # Undervoltage detected
                else: self.ThrottleData['UndervoltageDetected'] = False # Undervoltage not detected
                if value & 0x2: self.ThrottleData['ARMFrequencyCapped'] = True # ARMFrequencyCapped detected
                else: self.ThrottleData['ARMFrequencyCapped'] = False # ARMFrequencyCapped not detected
                if value & 0x4: self.ThrottleData['CurrentlyThrottled'] = True # Currently throttled
                else: self.ThrottleData['CurrentlyThrottled'] = False # Not Currently throttled
                if value & 0x8: self.ThrottleData['SoftTemperatureLimitActive'] = True # SoftTemperatureLimit active
                else: self.ThrottleData['SoftTemperatureLimitActive'] = False # SoftTemperatureLimit not active
                if value & 0x10000: self.ThrottleData['UndervoltageOccurred'] = True # Undervoltage occurred
                else: self.ThrottleData['UndervoltageOccurred'] = False # Undervoltage not occurred
                if value & 0x20000: self.ThrottleData['ARMFrequencyCapOccurred'] = True # ARMFrequencyCap occurred
                else: self.ThrottleData['ARMFrequencyCapOccurred'] = False # ARMFrequencyCap has not occurred
                if value & 0x40000: self.ThrottleData['ThrottlingOccurred'] = True # Throttling occurred
                else: self.ThrottleData['ThrottlingOccurred'] = False # Throttling has not occurred
                if value & 0x80000: self.ThrottleData['SoftTemperatureLimitOccurred'] = True # SoftTemperatureLimit has occurred
                else: self.ThrottleData['SoftTemperatureLimitOccurred'] = False # SoftTemperatureLimit has not occurred

    def DisplayThrottle(self):
        """ Basic display of cpu throttling measurements from the RPi. """
        print("Raspberry Pi throttling values")
        self.MeasureThrottle()
        for key,value in self.ThrottleData.items():
            print(key,":",value)

    def DisplayPower(self):
        """ Basic display of power measurements from the RPi. """
        print("Raspberry Pi power measurements:")
        self.MeasurePower() # Generate dictionary of V and A measurements for various points in the RPi.
        for key,entry in self.PowerData.items(): # Choose each measurement in turn.
            line = key.rjust(20," ") + ": " # Use measurement as the line label.
            if type(entry) == dict: # If we have a dictionary, process each entry in turn.
                for k,v in entry.items():
                    line += k.rjust(5," ") + ":" + str(v).ljust(14," ")
            else: # Not a dictionary so just report the value.
                line += str(entry)
            print(line) # Print the resulting line.
        print("")
        print("Power configuration:")
        print('usb_max_current_enable:',self.GetConfigValue('usb_max_current_enable',0))

    def GetConfigValue(self,name,default=None):
        """ Retrieve configuration setting from config.txt
            Parameters ----------------------------------------------
            name = name as it appears in config.txt
            default = value to return if 'name' is not found. 
            Output -------------------------------------------------- 
            Value as a string. """
        result = default
        cCmd = 'vcgencmd get_config ' + name
        lines = self.osCmd(cCmd)
        for line in lines:
            #print('GetConfigValue:',line)
            lineitems = line.split('=')
            if len(lineitems) <= 1: continue # Nothing there.
            result = lineitems[1].strip()
        return result

    def GetCpuTemp(self):
        """ Return the CPU temperature. """
        cput = CPUTemperature()
        self.CpuTemp = cput.temperature
        return self.CpuTemp

    def LogCpuTemp(self):
        """ Record CPU temperature in main log file. """
        self.Log("cpumonitor(",self.Name,").LogCpuTemp: Temperature",self.GetCpuTemp(),terminal=False)

    def CmdInt(self,cCmd,multiplier=1):
        """ Execute command and return integer value. """
        result = None
        listlines = self.osCmd(cCmd)
        for line in listlines: 
            self.Log(line,terminal=False)
            try:
                result = int(line.strip()) * multiplier
            except:
                pass
        return result
        
    def CpuFrequency(self,force=False):
        """ Return current, min and max CPU frequencies. """
        self.CurrFreq = self.CmdInt('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq',multiplier=1000) # Current frequency
        # Minimum frequency
        if self.MinFreq == None: self.MinFreq = self.CmdInt('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq',multiplier=1000) # Minimum frequency
        # Maximum frequency
        if self.MaxFreq == None: self.MaxFreq = self.CmdInt('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq',multiplier=1000) # Maximum frequency
        try:
            self.ClockPercent = int(round(100 * self.CurrFreq / self.MaxFreq,0))
        except:
            self.ClockPercent = None # Not measured yet.
        return True

    def PollAll(self, force = False):
        """ Check if it is time to retrieve updated statistics from the entire CPU.
            Retrieves OVERALL load across all the cores and CPU.

            cpu  1550 30 2105 190212 711 0 32 0 0 0
            cpu0 354 8 622 47511 114 0 15 0 0 0
            cpu1 445 3 488 47498 234 0 5 0 0 0
            cpu2 354 5 528 47663 101 0 6 0 0 0
            cpu3 397 14 467 47539 261 0 6 0 0 0
            intr 131734 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1200 35002 0 2452 0 0 0 1 0 24246 0 0 0 0 0 889 0 0 6892 0 0 0 370 0 0 0 0 0 0 1482 27266 28957 0 0 0 0 0 0 2337 0 0 0 0 0 0 544 0 96
            ctxt 137336
            btime 1697994434
            processes 1335
            procs_running 1
            procs_blocked 0
            softirq 55555 3 5392 1 469 6425 0 10711 10714 0 21840

        """
        if force or self.CPUTimer.Due(): # Time to update the CPU figures.
            statslist = self.osCmd("cat /proc/stat") # Check /proc/stat for specific core figures.
            
            # Update CPU figures.
            result = ""
            for statsline in statslist: # Find the statistics for this core in the result.
                if statsline.split()[0] == "cpu": # 1st element will match the core name.
                    result = statsline
                    break
            if result == "":
                self.Log("cpumonitor(",self.Name,").PollAll(): Didn't find stats for","cpu",terminal=False)
                return None # No stats for the cpu, fail.
            elements = result.split() # Break down the 1st line for analysis. Using default split() makes it ignore duplicated spaces.
            newUsed = int(elements[1]) + int(elements[2]) + int(elements[3]) # We consider cols 1,2,3 as 'busy' activities.
            newIdle = int(elements[4]) # col 4 is an idle activity.
            difUsed = newUsed - self.CpuUsed # Change since the last poll
            difIdle = newIdle - self.CpuIdle # Change since the last poll
            self.CpuUsed = newUsed # Update stored figures.
            self.CpuIdle = newIdle
            self.CpuBusy = int(100 * difUsed / (difUsed + difIdle)) # Calculate % busy since last poll.
            self.BusyHistory.append(self.CpuBusy) # Add to history list.
            self.BusyHistory = self.BusyHistory[-10:] # Only keep last 10 measures.
            
            # Update individual cores.
            for i,core in enumerate(self.CoreList):
                result = ""
                for statsline in statslist: # Find the statistics for this core in the result.
                    if statsline.split()[0] == core: # 1st element will match the core name.
                        result = statsline
                        break
                if result == "": 
                    self.Log("cpumonitor(",self.Name,").PollAll(): Didn't find stats for",core,terminal=False)
                    continue # No stats for this core, so ignore it.
                try:
                    elements = result.split() # Break down the 1st line for analysis.
                    newUsed = int(elements[1]) + int(elements[2]) + int(elements[3]) # We consider cols 1,2,3 as 'busy' activities.
                    newIdle = int(elements[4]) # col 4 is an idle activity.
                    difUsed = newUsed - self.CoreUsed[i] # Change since the last poll
                    difIdle = newIdle - self.CoreIdle[i] # Change since the last poll
                    self.CoreUsed[i] = newUsed # Store current value for comparison with next round.
                    self.CoreIdle[i] = newIdle 
                    self.CoreBusy[i] = int(100 * difUsed / (difUsed + difIdle)) # Calculate % busy since last poll.
                except Exception as e:
                    if self.Logger != None: # A log handler is defined.
                        self.Log("cpumonitor(",self.Name,").PollAll(",core,") failed.",terminal=False)
                        self.Log("cpumonitor(",self.Name,").PollAll(",core,") Error:",str(e),terminal=False)
                    else: # No log handler available, print the error instead.
                        print("cpumonitor(",self.Name,").PollAll(",core,") failed.")
                        print("cpumonitor(",self.Name,").PollAll(",core,") Error:",str(e))
            self.MeasuredTime = datetime.now()
            self.LogCpuTemp()
            self.CpuFrequency() # Update CPU clock speed attributes.
            _ = self.StatusLine()

    def StatusLine(self,label=True,sep=' ',force=False):
        """ Return a status line for the CPU and all cores. 
            label = True: Labels before each value. 
                    False: Just values.
            sep = Separator between each value. """
        self.PollAll(force=force) # Check we have recent enough numbers.
        line = ''
        # Overall CPU load figures.
        if label: line += "Timestamp="
        line += str(self.MeasuredTime) + sep
        if label: line += "CpuUsedSlots="
        line += str(self.CpuUsed) + sep
        if label: line += "CpuIdleSlots="
        line += str(self.CpuIdle) + sep
        if label: line += "CpuBusyPc="
        line += str(self.CpuBusy) + "%" + sep
        if label: line += "CpuTemp="
        line += str(self.CpuTemp) + "C" + sep
        if label: line += "CurrFreq="
        line += str(self.CurrFreq) + "Hz" + sep
        if label: line += "MinFreq="
        line += str(self.MinFreq) + "Hz" + sep
        if label: line += "MaxFreq="
        line += str(self.MaxFreq) + "Hz" + sep
        if label: line += "ClockPc="
        line += str(self.ClockPercent) + "%" + sep
        if label: line += "CpuBusyRange="
        temp = self.GetBusyRange()
        if temp == '' or temp == None: temp = 'calculating'
        line += str(temp) + sep
        if label: line += "IsThrottled="
        line += str(self.IsThrottled()) + sep
        if label: line += "MinSpeed="
        line += str(self.MinSpeed()) + sep
        if label: line += "FullSpeed="
        line += str(self.FullSpeed()) + sep
        # Individual CORE load figures.
        for i,c in enumerate(self.CoreList):
            if label: line += c + "UsedSlots=" 
            line += str(self.CoreUsed[i]) + sep
            if label: line += c + "IdleSlots=" 
            line += str(self.CoreIdle[i]) + sep
            if label: line += c + "BusyPc="
            line += str(self.CoreBusy[i]) + "%" + sep
        self.Log("cpumonitor(",self.Name,").StatusLine:",line,terminal=False)
        return line

    def PercentBusy(self,force=False) -> int:
        """ Return the recent CPU Busy % figure. """
        self.PollAll(force=force) # Check we have recent enough numbers.
        return self.CpuBusy 
        
    def PercentClock(self,force=False) -> int:
        """ Return the recent clockspeed as percentage of clock range. """
        self.PollAll(force=force) # Check we have recent enough numbers.
        return self.ClockPercent
        
    def GetBusyRange(self,force=False) -> str:
        """ Return recent range of CPU busy percentages. """
        self.PollAll(force=force)
        result = ''
        if len(self.BusyHistory) > 5:
            MinBusy = int(min(self.BusyHistory))
            MaxBusy = int(max(self.BusyHistory))
            result = '(' + str(MinBusy) + "% - " + str(MaxBusy) + "%" + ')'
        return result

if __name__ == '__main__': # Fixes issue in notepad++ editor.
    pass
