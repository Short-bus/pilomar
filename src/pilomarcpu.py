#!/usr/bin/python

# Pilomar's cpu monitor class.

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

    def __init__(self,logger=None,name='',period=60):
        self.Log = logger # Define a logging procedure. Must be a reference to a .Log() style method.
        self.Name = name # Allow an instance name to be assigned.
        self.oscommand = oscommand(logger=logger) # Create OS command executor.
        self.osCmd = self.oscommand.Execute
        self.CPUTimer = timer(period) # Set timer for 60 seconds.
        # self.CoreTimer = timer(period) # Set timer for 60 seconds.
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
        if self.Log != None: 
            for line in listlines: self.Log(line,terminal=False)

    def GetCpuTemp(self):
        """ Return the CPU temperature. """
        cput = CPUTemperature()
        self.CpuTemp = cput.temperature
        return self.CpuTemp

    def LogCpuTemp(self):
        """ Record CPU temperature in main log file. """
        if self.Log != None: self.Log("cpumonitor(",self.Name,").LogCpuTemp: Temperature",self.GetCpuTemp(),terminal=False)

    def CmdInt(self,cCmd,multiplier=1):
        """ Execute command and return integer value. """
        result = None
        listlines = self.osCmd(cCmd)
        for line in listlines: 
            if self.Log != None: self.Log(line,terminal=False)
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

    #    def PollCores(self, force = False):
    #        """ Check if it is time to retrieve updated statistics from the CPU.
    #
    #            cpu  1550 30 2105 190212 711 0 32 0 0 0
    #            cpu0 354 8 622 47511 114 0 15 0 0 0
    #            cpu1 445 3 488 47498 234 0 5 0 0 0
    #            cpu2 354 5 528 47663 101 0 6 0 0 0
    #            cpu3 397 14 467 47539 261 0 6 0 0 0
    #            intr 131734 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1200 35002 0 2452 0 0 0 1 0 24246 0 0 0 0 0 889 0 0 6892 0 0 0 370 0 0 0 0 0 0 1482 27266 28957 0 0 0 0 0 0 2337 0 0 0 0 0 0 544 0 96
    #            ctxt 137336
    #            btime 1697994434
    #            processes 1335
    #            procs_running 1
    #            procs_blocked 0
    #            softirq 55555 3 5392 1 469 6425 0 10711 10714 0 21840
    #
    #        """
    #        
    #        # ---------------------------------------------
    #        # *Q* DEPRECATED IN FAVOUR OF PollAll() method. 
    #        # ---------------------------------------------
    #        
    #        if force or self.CoreTimer.Due(): # Time to update the CPU figures.
    #            statslist = self.osCmd("cat /proc/stat") # Check /proc/stat for specific core figures.
    #            self.MeasuredTime = datetime.now()
    #            for i,core in enumerate(self.CoreList):
    #                result = ""
    #                for statsline in statslist: # Find the statistics for this core in the result.
    #                    if statsline.split()[0] == core: # 1st element will match the core name.
    #                        result = statsline
    #                        break
    #                if result == "": 
    #                    if self.Log != None: self.Log("cpumonitor(",self.Name,").PollCores(): Didn't find stats for",core,terminal=False)
    #                    continue # No stats for this core, so ignore it.
    #                try:
    #                    elements = result.split() # Break down the 1st line for analysis.
    #                    newUsed = int(elements[1]) + int(elements[2]) + int(elements[3]) # We consider cols 1,2,3 as 'busy' activities.
    #                    newIdle = int(elements[4]) # col 4 is an idle activity.
    #                    difUsed = newUsed - self.CoreUsed[i] # Change since the last poll
    #                    difIdle = newIdle - self.CoreIdle[i] # Change since the last poll
    #                    self.CoreUsed[i] = newUsed # Store current value for comparison with next round.
    #                    self.CoreIdle[i] = newIdle 
    #                    self.CoreBusy[i] = int(100 * difUsed / (difUsed + difIdle)) # Calculate % busy since last poll.
    #                    if self.Log != None: self.Log("cpumonitor(",self.Name,").PollCores():",self.MeasuredTime," Core ",core,": Busy",self.CoreBusy[i],"%",terminal=False)
    #                except Exception as e:
    #                    if self.Log != None: self.Log("cpumonitor(",self.Name,").PollCores(",core,") failed.",terminal=True)
    #                    print("cpumonitor(",self.Name,").PollCores(",core,") failed.")
    #                    print("cpumonitor(",self.Name,").PollCores(",core,")",str(e))
    #
    #    def Poll(self,force = False):
    #        """ Check if it is time to retrieve updated statistics from the entire CPU.
    #            Retrieves OVERALL load across all the cores.
    #
    #            cpu  1550 30 2105 190212 711 0 32 0 0 0
    #            cpu0 354 8 622 47511 114 0 15 0 0 0
    #            cpu1 445 3 488 47498 234 0 5 0 0 0
    #            cpu2 354 5 528 47663 101 0 6 0 0 0
    #            cpu3 397 14 467 47539 261 0 6 0 0 0
    #            intr 131734 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1200 35002 0 2452 0 0 0 1 0 24246 0 0 0 0 0 889 0 0 6892 0 0 0 370 0 0 0 0 0 0 1482 27266 28957 0 0 0 0 0 0 2337 0 0 0 0 0 0 544 0 96
    #            ctxt 137336
    #            btime 1697994434
    #            processes 1335
    #            procs_running 1
    #            procs_blocked 0
    #            softirq 55555 3 5392 1 469 6425 0 10711 10714 0 21840
    #
    #        """
    #        
    #        # ---------------------------------------------
    #        # *Q* DEPRECATED IN FAVOUR OF PollAll() method. 
    #        # ---------------------------------------------
    #        if force or self.CPUTimer.Due(): # Time to update the CPU figures.
    #            result = self.osCmd("grep 'cpu ' /proc/stat") # Check /proc/stat for CPU figures.
    #            elements = result[0].split() # Break down the 1st line for analysis. Using default split() makes it ignore duplicated spaces.
    #            newUsed = int(elements[1]) + int(elements[2]) + int(elements[3]) # We consider cols 1,2,3 as 'busy' activities.
    #            newIdle = int(elements[4]) # col 4 is an idle activity.
    #            difUsed = newUsed - self.CpuUsed # Change since the last poll
    #            difIdle = newIdle - self.CpuIdle # Change since the last poll
    #            self.CpuUsed = newUsed # Update stored figures.
    #            self.CpuIdle = newIdle
    #            self.CpuBusy = int(100 * difUsed / (difUsed + difIdle)) # Calculate % busy since last poll.
    #            if self.Log != None: self.Log("cpumonitor(",self.Name,").Poll() Overall CPU: Used",newUsed,"Idle",newIdle,"Busy",self.CpuBusy,"%",terminal=False)
    #            self.BusyHistory.append(self.CpuBusy) # Add to history list.
    #            self.BusyHistory = self.BusyHistory[-10:] # Only keep last 10 measures.
    #            self.LogCpuTemp()
    #            self.CpuFrequency() # Update CPU clock speed attributes.

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
        #if self.Log != None: self.Log("cpumonitor(",self.Name,").PollAll(): Begin",terminal=False)
        #if self.Log != None: self.Log("cpumonitor(",self.Name,").Remaining=",self.CPUTimer.Remaining(),terminal=False)
        if force or self.CPUTimer.Due(): # Time to update the CPU figures.
            #if self.Log != None: self.Log("cpumonitor(",self.Name,").PollAll(): Due/Forced",terminal=False)
            statslist = self.osCmd("cat /proc/stat") # Check /proc/stat for specific core figures.
            
            # Update CPU figures.
            result = ""
            for statsline in statslist: # Find the statistics for this core in the result.
                if statsline.split()[0] == "cpu": # 1st element will match the core name.
                    result = statsline
                    break
            if result == "":
                if self.Log != None: self.Log("cpumonitor(",self.Name,").PollAll(): Didn't find stats for","cpu",terminal=False)
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
                    if self.Log != None: self.Log("cpumonitor(",self.Name,").PollAll(): Didn't find stats for",core,terminal=False)
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
                    if self.Log != None: 
                        self.Log("cpumonitor(",self.Name,").PollAll(",core,") failed.",terminal=False)
                        self.Log("cpumonitor(",self.Name,").PollAll(",core,") Error:",str(e),terminal=False)
                    else:
                        print("cpumonitor(",self.Name,").PollAll(",core,") failed.")
                        print("cpumonitor(",self.Name,").PollAll(",core,") Error:",str(e))
            self.MeasuredTime = datetime.now()
            self.LogCpuTemp()
            self.CpuFrequency() # Update CPU clock speed attributes.
            _ = self.StatusLine()
        #if self.Log != None: self.Log("cpumonitor(",self.Name,").PollAll(): End",terminal=False)

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
        if self.Log != None: self.Log("cpumonitor(",self.Name,").StatusLine:",line,terminal=False)
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
