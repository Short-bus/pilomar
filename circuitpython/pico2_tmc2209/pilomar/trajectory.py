# pilomar/trajectory.py - Circuitpython 9.2 build for Raspberry Pi Pico 2 (RP2350).
# For use with Raspberry Pi Pico 2 only.
# Dec.2024 / Refactored with help from TPROFFEN.

from pilomar.helpers import *

#-----------------------------------------------------------------------------------------------

trajectory_version = "0.0.1" # A version number for this source code.

#-----------------------------------------------------------------------------------------------

class trajectorypoint():
    """ An individual segment in a trajectory.
        Each segment is a short straight line path that approximates the arc that
        the target is following. The segment is short enough that it is very
        close to the actual curve that the target follows.
        trajectory yymmddhhmmss motorname start startangle end endangle startpos endpos
             0           1         2         3       4       5       6     7        8  """
    def __init__(self,line,clock):
        """ line = the trajectory entry received from the RPi.

            For backwards compatibility, if the start/end positions are not in the message 
            the values are calculated here instead. """
        # Be sure trajectory details are not corrupted.
        # Don't create the entry if there is any problem with it.
        # The remote server will re-send the record if it doesn't get created this time.
        # trajectory 20210410163444 azimuth 20210410163444 256.57984815616663 20210410163544 256.7949264136615
        lineitems = line.split(' ')
        self.Clock = clock # Link to clock instance.
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
        print("trajectory: New entry: Start pos",self.StartPosition,"end pos",self.EndPosition,"gradient",self.StepsPerSecond)

    def Printable(self):
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
            timeint, timedec = self.Clock.NowDecimal()
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
    def __init__(self,name,logfile=None,clock=None):
        self.TrajectoryList = []
        self.Clock = clock # Handle to clock instance.
        self.LogFile = logfile # Handle to logging instance.
        self.Valid = False # Indicates that the trajectory is useable.
        self.MotorName = name # The parent MotorName to match log messages with the parent motor.

    def Clean(self): # Trim expired entries from the trajectory list.
        """ All the entries in Trajectory List should complete in the future. """
        while len(self.TrajectoryList) > 0 and self.TrajectoryList[0].EndTime < self.Clock.Now():
            self.LogFile.Log('trajectory.Clean: Expired (', self.MotorName, self.TrajectoryList[0].Printable(), ')')
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
            self.TrajectoryList.append(trajectorypoint(line,clock=self.Clock)) # Add new entry to the end of the list.
            result = True # Entry creation was successful.
        except Exception as e:
            self.LogFile.Log('trajectory.Add(', self.MotorName ,'): ' + str(line) + ': Failed to create new trajectory point: ' + str(e))
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
            validuntil = self.Clock.Now() # Trajectory is empty, so it expires now!
        return validuntil

    def Validate(self):
        """ Update the validity of the trajectory.
            True means the ExpectedPosition() method can be trusted.
            False means it's not valid yet. """
        self.Valid = False
        if self.ValidUntil() > self.Clock.Now(): # Trajectory valid.
            self.Valid = True

    def EndAngle(self):
        """ What is the final rest position of the trajectory so far?"""
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
        # Calculate the step position that the motor should be at right now.
        if len(self.TrajectoryList) > 0:
            result = self.TrajectoryList[0].ExpectedPosition()
        else:
            result = None # No position set yet.
        return result
