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

class cpumonitor(): # 1 references.
    """ Simple class to monitor the CPU load of the RPi.
        This periodically polls the CPU load and establishes some metrics. """

    def __init__(self,logger=None):
        self.Log = logger # Define a logging procedure. Must be a reference to a .Log() style method.
        self.oscommand = oscommand(logger=logger) # Create OS command executor.
        self.osCmd = self.oscommand.Execute
        self.Command = "grep 'cpu ' /proc/stat"
        self.Timer = timer(60) # Set timer for 60 seconds.
        self.CpuUsed = 0 # Cpu used slots since system start
        self.CpuIdle = 0 # Cpu idle slots since system start
        self.CpuBusy = 0 # Percentage busy over Poll period.
        self.BusyHistory = [] # List of last 10 busy percentage figures.
        self.CpuTemp = 0 # Reported CPU temperature.
        self.Poll(force=True) # Update the stats initially.

    def LogCpuInfo(self):
        """ Record CPU information to the main log file. """
        if self.Log != None: self.Log("cpumonitor.LogCpuInfo:",terminal=False)
        cCmd = 'cat /proc/cpuinfo'
        listlines = self.osCmd(cCmd)
        if self.Log != None: 
            for line in listlines: self.Log(line,terminal=False)

    def GetCpuTemp(self):
        """ Return the CPU temperature. """
        if self.Log != None: self.Log("cpumonitor.GetCpuTemp:",terminal=False)
        cput = CPUTemperature()
        self.CpuTemp = cput.temperature
        return self.CpuTemp

    def LogCpuTemp(self):
        """ Record CPU temperature in main log file. """
        if self.Log != None: self.Log("cpumonitor.LogCpuTemp: Temperature",self.GetCpuTemp(),terminal=False)

    def Poll(self,force = False):
        """ Check if it is time to retrieve updated statistics from the CPU. """
        if force or self.Timer.Due(): # Time to update the CPU figures.
            result = self.osCmd(self.Command) # Check /proc/stat for CPU figures.
            elements = result[0].split() # Break down the 1st line for analysis.
            newUsed = int(elements[1]) + int(elements[2]) + int(elements[3]) # We consider cols 1,2,3 as 'busy' activities.
            newIdle = int(elements[4]) # col 4 is an idle activity.
            difUsed = newUsed - self.CpuUsed # Change since the last poll
            difIdle = newIdle - self.CpuIdle # Change since the last poll
            self.CpuUsed = newUsed # Update stored figures.
            self.CpuIdle = newIdle
            self.CpuBusy = int(100 * difUsed / (difUsed + difIdle)) # Calculate % busy since last poll.
            self.BusyHistory.append(self.CpuBusy) # Add to history list.
            self.BusyHistory = self.BusyHistory[-10:] # Only keep last 10 measures.
            self.LogCpuTemp()

    def PercentBusy(self,force=False) -> int:
        """ Return the recent CPU Busy % figure. """
        self.Poll(force=force) # Check we have recent enough numbers.
        return self.CpuBusy 
        
    def GetBusyRange(self,force=False) -> str:
        """ Return recent range of CPU busy percentages. """
        self.Poll(force=force)
        result = ''
        if len(self.BusyHistory) > 5:
            MinBusy = int(min(self.BusyHistory))
            MaxBusy = int(max(self.BusyHistory))
            result = '(' + str(MinBusy) + "% - " + str(MaxBusy) + "%" + ')'
        return result
        