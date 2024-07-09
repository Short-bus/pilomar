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

from pilomaroscommand import oscommand # OS Command execution.
from pilomartimer import timer # Pilomar's timer class.

class memorymonitor(): # 1 references.
    """ Simple class to monitor the memory load of the RPi. """

    def __init__(self,logger=None):
        self.Log = logger # Define which logger to use.
        self.oscommand = oscommand(logger=logger)
        self.osCmd = self.oscommand.Execute
        self.osCmdCode = self.oscommand.ExecuteCode
        self.Command = "free -m"
        self.Timer = timer(60) # Set timer for 60 seconds.
        self.MemoryTotal = 0
        self.MemoryUsed = 0
        self.MemoryFree = 0
        self.UsedHistory = []
        self.FreeHistory = []
        self.Poll(force=True) # Kickstart the values.

    def Poll(self,force = False):
        """ Decide if it is time to update the memory usage statistics. 
            'Free' memory is based upon the 'available memory' figure rather than the 'free' column.
            This is because 'free' is missing memory allocated to the O/S cache. 
            'available' shows something closer to the memory that the system COULD allocate to running programs. """
        #    $ free -m
        #                  total        used        free      shared  buff/cache   available
        #    Mem:           1815         175         216           1        1423        1548   <- This line is used.
        #    Swap:            99          33          66
        if force or self.Timer.Due(): # Time to update the CPU figures.
            lines = self.osCmd(self.Command)  # osCmd function dedicated to the MAIN thread.
            memoryfields = lines[1].split() # This splits by blocks of whitespace.
            if len(memoryfields) > 2:
                self.MemoryTotal = int(memoryfields[1]) * 1000000 # Total
                self.MemoryUsed = int(memoryfields[2]) * 1000000 # Used
                self.MemoryFree = int(memoryfields[6]) * 1000000 # 'Available' (Because FREE column is misleading.)
            self.UsedHistory.append(self.MemoryUsed)
            self.FreeHistory.append(self.MemoryFree)
            self.UsedHistory = self.UsedHistory[-10:] # Last 10 entries only.
            self.FreeHistory = self.FreeHistory[-10:] # Last 10 entries only.

    def GetMemory(self,force=False):
        """ Return recent memory usage statistics. """
        self.Poll(force=force)
        return self.MemoryTotal, self.MemoryUsed, self.MemoryFree
        
    def GetTotal(self,force=False) -> int:
        """ Return recent total memory value. """
        self.Poll(force=force)
        return self.MemoryTotal

    def GetUsed(self,force=False) -> int:
        """ Return recent used memory value. """
        self.Poll(force=force)
        return self.MemoryUsed

    def GetFree(self,force=False) -> int:
        """ Return recent free memory value. """
        self.Poll(force=force)
        return self.MemoryFree

    def GetUsedRange(self,force=False) -> str:
        """ Return recent range of memory full. """
        self.Poll(force=force)
        result = ''
        if len(self.UsedHistory) > 5:
            MinUsed = int(100 * min(self.UsedHistory) / self.MemoryTotal)
            MaxUsed = int(100 * max(self.UsedHistory) / self.MemoryTotal)
            result = '(' + str(MinUsed) + "% - " + str(MaxUsed) + "%" + ')'
        return result

    def GetFreeRange(self,force=False) -> str:
        """ Return recent range of memory free. """
        self.Poll(force=force)
        result = ''
        if len(self.FreeHistory) > 5:
            MinFree = int(100 * min(self.FreeHistory) / self.MemoryTotal)
            MaxFree = int(100 * max(self.FreeHistory) / self.MemoryTotal)
            result = '(' + str(MinFree) + "% - " + str(MaxFree) + "%" + ')'
        return result

