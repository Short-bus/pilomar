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
        self.StartTime = datetime.now(timezone.utc)
    
    def UpdateCount(self,count):
        self.Current = count
        
    def GetTotalSeconds(self):
        """ How many seconds will the entire run take? """
        temp = self.Current - self.Start
        if temp != 0: # Progress has begun.
            totalseconds = (datetime.now(timezone.utc) - self.StartTime).total_seconds() * 100 / self.GetPercent()
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
        
    def GetPercent(self):
        """ How many % complete is the process? """
        return 100 * (self.Current - self.Start) / (self.Target - self.Start)

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
        