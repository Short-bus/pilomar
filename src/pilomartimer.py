#!/usr/bin/python

# timer class for use in Pilomar project.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from datetime import datetime, timedelta, timezone
from textcolor import textcolor
import threading # To use the Event.wait() method as a non-blocking wait function.

class progresstimer():
    """ Simple progress timer, provide a target count, a starting point and a current count.
        It will maintain the % complete and estimated completion time. """
    def __init__(self,name,target,start=0,initial=None):
        """ name = any name for this instance.
            target = The value that's considered to be 100% complete. 
            start = The value that's considered to be 0% complete.
            initial = The initial count if the process has already begun. """
        self.Name = name
        self.Start = start # Value representing 0%
        if initial != None:
            self.Current = initial # Current value.
        else:
            self.Current = start # Current value.
        self.Target = target # Value representing 100%
        self.StartTime = self.NowUTC()
        
    def NowUTC(self):
        """ Return current timestamp in UTC. """
        return datetime.now(timezone.utc)
        
    def Increment(self,step=1):
        """ Increment current count. """
        self.Current += step 
    
    def UpdateCount(self,count):
        """ Update current count to new value. """
        self.Current = count
        
    def GetTotalSeconds(self):
        """ How many seconds will the entire run take? """
        temp = self.Current - self.Start
        if temp != 0: # Progress has begun.
            totalseconds = (self.NowUTC() - self.StartTime).total_seconds() * 100 / self.GetPercent()
        else:
            totalseconds = 0
        return totalseconds
        
    def GetETA(self):
        """ Return UTC timestamp when process will be completed. """
        temp = self.GetTotalSeconds()
        if temp != 0: # Progress has begun.
            ETA = self.StartTime + timedelta(seconds=temp)
        else:
            ETA = self.StartTime
        return ETA

    def RemainingSeconds(self):
        """ How many seconds left? """
        ts = int(round((self.GetETA() - self.NowUTC()).total_seconds),0)
        return ts

    def SecondsToHMS(self,value):
        """ Receive number of seconds. 
            Return as hh:mm:ss format string. """
        if value < 0: si = "-"
        else: si = ""
        value = int(round(abs(value),0)) # Round to nearest integer.
        ss = value % 60 # Number of seconds.
        value = value // 60 # Minutes left?
        mm = value % 60 # Number of minutes.
        value = value // 60 # Hours left?
        hh = value % 24 # Number of hours.
        value = value // 24 # Days left?
        if value > 0: dy = str(value) + "d "
        else: dy = ""
        return si + dy + str(hh).rjust(2,"0") + ":" + str(mm).rjust(2,"0") + ":" + str(ss).rjust(2,"0")
        
    def GetPercent(self):
        """ How many % complete is the process? """
        return 100 * (self.Current - self.Start) / (self.Target - self.Start)
        
    def UnitsPerSecond(self):
        """ Calculate the 'speed' of progress. """
        elapsed = (self.NowUTC() - self.StartTime).total_seconds()
        if elapsed != 0: return float(self.Current) / elapsed
        else: return 0.0
        
    def SecondsPerUnit(self):
        """ Calculate the time to progress 1 unit. """
        elapsed = (self.NowUTC() - self.StartTime).total_seconds()
        if self.Current != 0: return elapsed / float(self.Current)
        else: return 0.0

    def RelativeDatetime(self,value):
        """ Return just time if it's the same DATE as now. 
            Else return the date too. """
        result = str(value).split('.')[0] # yyyy-mm-dd hh:mm:ss
        cnow = str(self.NowUTC()).split('.')[0] # yyyy-mm-dd hh:mm:ss
        if result.split(' ')[0] == cnow.split(' ')[0]: # Same date so don't show it.
            result = result.split(' ')[1] # Just the HH:MM:SS part.
        return result
        
    def MakeProgressBar(self,color=True,text='',length=20,show_start=True,show_eta=True,todo_fg=textcolor.WHITE,todo_bg=textcolor.GREY15,done_fg=textcolor.WHITE,done_bg=textcolor.GREEN):
        """ Create a status line with or without textcolor terminal color codes embedded.
            color : True, line includes some color codes.
                    False, line is plain text.
            text  : Optional additional text to add to the end of the line after the automatic items.
            length : Character length of the progress bar.
            show_start : Start time is shown.
            show_eta : ETA time is shown.
            done_fg : textcolor to use for foreground.
            done_bg : textcolor to use for background.
            todo_fg : textcolor to use for foreground.
            todo_bg : textcolor to use for background. 
            Returns ----------------------------------------------------------
            String ready for print() statement. Includes control codes to update existing display. """
        # Construct barcode string.
        pc = self.GetPercent()
        pc_str_v = str(self.Current) + "/" + str(self.Target)
        pc_str_p = str(round(pc,1)) + "%"
        pc_str = '' # Construct text describing progress.
        if len(pc_str_v) + len(pc_str) < length: pc_str = (pc_str + " " + pc_str_v).strip() # Add "a of b" info if there's space.
        if len(pc_str_p) + len(pc_str) < length: pc_str = (pc_str + " " + pc_str_p).strip() # Add "%" measure if there's space.
        pc_str = (pc_str + length * ' ')[:length]
        # Split between filled and empty portion.
        fp = int(round(length * pc / 100,0))
        left = pc_str[:fp]
        right = pc_str[fp:]
        if color:
            result = textcolor.cursorup() + str(self.NowUTC()).split('.')[0] + " "
            if show_start: result += "Started:" + self.RelativeDatetime(self.StartTime).split('.')[0] + " "
            result += textcolor.fgbgcolor(done_fg,done_bg,left) + textcolor.fgbgcolor(todo_fg,todo_bg,right) + " " # todo
            if show_eta: result += "ETA:" + self.RelativeDatetime(self.GetETA()).split('.')[0] + " UTC "
            if text != '': result += text
            result += textcolor.clearlineforward()
        else:
            result = self.MakeStatusLine(color=False,text=text) # Use regular status line if no colors allowed.
        return result

    def MakeStatusLine(self,color=False,text=''):
        """ Create a status line with or without textcolor terminal color codes embedded.
            color : True, line includes some color codes.
                    False, line is plain text.
            text  : Optional additional text to add to the end of the line after the automatic items. """
        if color:
            result = textcolor.cursorup() + str(self.NowUTC()).split('.')[0] + " "
            result += textcolor.white(str(round(self.GetPercent(),1))) + "%. Done "
            result += str(self.Current) + " of " + str(self.Target) + ". ETA "
            result += str(self.GetETA()).split('.')[0] + " UTC " + text
            result += textcolor.clearlineforward()
        else:
            result = str(self.NowUTC()).split('.')[0] + " "
            result += str(round(self.GetPercent(),1)) + "%. Done "
            result += str(self.Current) + " of " + str(self.Target) + ". ETA "
            result += str(self.GetETA()).split('.')[0] + " UTC " + text
        return result

    def IncrementAndDisplay(self,color=True,text='',bar=False):
        """ Increment the target and display a status line.
            color : True, line includes some color codes.
                    False, line is plain text.
            text  : Optional additional text to add to the end of the line after the automatic items.        """
        self.Increment()
        if bar: print(self.MakeProgressBar(color=color,text=text)) 
        else: print(self.MakeStatusLine(color=color,text=text)) 
        
    def IncrementAndGetStatus(self):
        """ Increment the target and return a status line. """
        self.Increment()
        return self.MakeStatusLine()

class timer(): # 14 references.
    """ Clock driven timer class. 
        This can be polled periodically to see if a timer is due. 
            mytimer = timer(20) # Create a timer for 20 seconds. 
            ...
            if mytimer.due(): # 20 seconds has elapsed.
                ...
                
        parameters:
            - period = Number of seconds that the timer should run for. (It will repeat!)
            - offset = An initial additional delay before the timer starts. 
            - skip = True : If the timer expires multiple times before being checked the extra events are ignored.
            - skip = False: If the timer expires multiple times before being checked, the extra events are queued up and will still trigger separately.
                    """

    def __init__(self, period: int, offset : int = 0, skip : bool = True):
        """ Create the object, set the timer parameters. 
            period = number of seconds between events.
            offset = number of seconds earlier/later than first due time. 
            skip = If timer is late, just trigger once then reset for next future due time. """
        if period < 1:
            self.Period = 1
        else:
            self.Period = period
        if offset == 0:
            self.NextTrigger = self.NowUTC() + timedelta(seconds=self.Period)
        else:
            self.NextTrigger = self.NowUTC() + timedelta(seconds=offset)
        self.SkipEvents = skip # If the timer falls behind, do we skip missed events?
        self.ForceTrigger = False # When set to True, the .Due() method returns True regardless of timing. Used to force an event.

    def NowUTC(self) -> datetime: # Many references.
        """ Get system clock as UTC (timezone aware) 
            Microcontroller and Skyfield are operated in UTC vales. 
            All clock-times used in this program use the UTC timestamped clock.
            This should be the only reference to datetime.now() method in the entire
            module. All other uses should refer to this NowUTC() function.
            """
        # Not adapted to support ClockOffset because timer clock is entirely internal.
        return datetime.now(timezone.utc)

    def _SetNextTrigger(self):
        """ Update the trigger due time to the next occurrence. 
            The next due time depends upon the skip parameter too! """
        if self.SkipEvents: # Skip any missed events. 
            while self.NextTrigger <= self.NowUTC():
                self.NextTrigger = self.NextTrigger + timedelta(seconds=self.Period)
        else: # Don't skip missed events, process every one!
            self.NextTrigger = self.NextTrigger + timedelta(seconds=self.Period)
        self.ForceTrigger = False # If the previous trigger was forced, reset that status now.

    def Elapsed(self) -> bool:
        """ Return number of seconds that have elapsed since the timer was set. """
        starttime = self.NextTrigger - timedelta(seconds=self.Period)
        elapsed = (self.NowUTC() - starttime).total_seconds()
        return elapsed

    def ElapsedPc(self) -> float:
        """ Return % of time elapsed. """
        result = round(100 * self.Elapsed() / self.Period,0)
        return result
        
    def Remaining(self) -> float:
        """ Return number of seconds remaining on a timer. """
        result = (self.NextTrigger - self.NowUTC()).total_seconds()
        if result < 0.0: result = 0.0 # Timer expired.
        return result

    def Due(self) -> bool:
        """ If timed event is due, this returns TRUE. Otherwise returns FALSE.
            It automatically sets the next due timestamp. """
        if self.NextTrigger < self.NowUTC() or self.ForceTrigger:
            result = True
            self._SetNextTrigger()
        else:
            result = False
        return result

    def Wait(self) -> bool:
        """ Wait for timer to expire. 
            The thread cannot do anything else while waiting for this. """
        # NOTE: If you're expecting the clock to change out of DST, this may last longer than you think!
        while self.Due() == False:
            t = self.Remaining()
            if t > 0:
                # RPi5B - Non-blocking wait function.
                event = threading.Event()
                event.wait(t)
                # time.sleep(t) # RPi4B - Blocking wait!
        return True
        
    #def Wait(self) -> bool:
    #    """ Wait for timer to expire. 
    #        The thread cannot do anything else while waiting for this. """
    #    while self.Due() == False:
    #        t = self.Remaining()
    #        if t > 0:
    #            time.sleep(t)
    #    return True

    def Restart(self) -> bool:
        """ Use this to reset the timer clock.
            This will abandon the current countdown and 
            restart it from the current moment. 
            If multiple events are overdue for this trigger they are dropped. """
        self.NextTrigger = self.NowUTC() + timedelta(seconds=self.Period)
        self.ForceTrigger = False # If the previous trigger was forced, reset that status now.
        return True
        
    def Trigger(self) -> bool:
        """ Use this to trigger the timer. 
            This will force the next .Due() call to return TRUE and then reset the timer.
            This is for cases where you want to override the timer. """
        self.ForceTrigger = True
        return True


# 
        