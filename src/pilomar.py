#!/usr/bin/python
#!/usr/bin/python

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.
# Examples
# - SKYFIELD is issued and used under the "MIT License" terms.
# - HIPPARCOS data is used under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License.
# - JPL data for planet positions will have its own licence.
# - NGC (New General Catalog) data is based upon the Saguaro Astronomy Club Database version 8.1
# - The MESSIER catalog is gathered from multiple sources.
# - The MeteorShower list is based upon the wikipedia list (2021).

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# THIS SOFTWARE CAN CONTROL ELECTRICAL AND MECHANICAL DEVICES. 
# THERE IS THEREFORE A RISK OF INJURY FROM INCORRECT ASSEMBLY, OPERATION OR FAILURE OF COMPONENTS.
# IT IS YOUR RESPONSIBILITY TO ENSURE THE SAFETY OF THE DEVICES YOU CHOOSE TO CONTROL WITH THIS SOFTWARE.

# The Skyfield API is described here: https://rhodesmill.org/skyfield/api.html

# This version expects the following hardware:
# - RaspberryPi microcomputer (V4 2GB or greater recommended)
# - Raspbian BUSTER operating system.
# - Pimoroni Tiny2040 8MB as a microcontroller of the motors
# - Nema 17 stepper motors (0.9degree per full step).
# - DRV8825 stepper motor driver chips.
# - Raspberry Pi High Quality Camera Sensor V1.0
# - Raspberry Pi 16mm 'telephoto' lens.
# - - You can use other lenses however some calculations in the program may need adapting to cater for the different field of view.

# Recommended exposures.
# = Full Moon = 1e-6 seconds
# = M31 Andromeda Galaxy = 10.0 seconds = Magnitude 3.44
# = M27 Dumbbell Nebula = 20.0 seconds = Magnitude 7.50
# Fastest possible exposure is 1e-6 seconds.

# ================================================================================================================================================
# This version runs on RASPBIAN BUSTER (DEBIAN BUSTER). This uses the original CAMERA services developed for the RPi.
# After November 2021 RASPBIAN was updated to DEBIAN BULLSEYE which uses the libcamera package, this software does not currently work with that.
# - Camera interaction is via the raspistill program to reduce dependencies, BULLSEYE should be directly compatible, but this has not been tested.
# - Oher package dependencies currently prevent migration to BULLSEYE.
# ================================================================================================================================================

# BEWARE! This program uses THREADS. It has to handle UI, MOVEMENT, COMMUNICATIONS and PHOTOGRAPHY in parallel.
# Thread 1 (MAIN Process) handles:
#   - User interface, astro calculations, observation control.
# Thread 2 handles:
#   - Image capture, image preparation, preview generation, tracking image processing, motor position tuning.
# Thread 3 handles:
#   - UART communication flow between RPi and microcontroller, including trajectory calculation and updates.

# KNOWN ISSUES -----------------------------------------------------------------------------------------------------------------------------------------------------------
# *Q* On rare occassions, the camera thread can hang completely, requiring a power cycle of the RPi.
#     The cause is not known, but the camera board stops responding. I have read online that power problems to the camera can cause this.
#     This is detected and reported, but I cannot yet recover the situation programmatically.
# *Q* Some microcontrollers sometimes randomly reset. The software is relatively fault tolerant and recovers automatically, but the cause of the resets is not yet identified.
#     Resets are reported, and generally only cause brief delays while the system recovers.
#     Problem is very common with RPi Pico and Adafruit Feather 2040.
#     Problem does not occur with Pimoroni Tiny2040
# *Q* The keyboard scanning routine causes the display to flash sometimes. If you are sensitive to flashing images you can slow down the keyboard scanning so that the image is more stable.

# POSSIBLE DEVELOPMENTS --------------------------------------------------------------------------------------------------------------------------------------------------
# TODO: Is photometry transit method exoplanet detection possible at all with this set up? See aavso.org - AAVSO DSLR Observing Manual. Trapist-10 may be the simplest star to monitor?
# TODO: Speed up the image tracking calculations. If reference images are constructed on a smaller scale it will be faster. - Under development. Needs comparing with original.
# TODO: Can Astropy (including pyFITS) convert .DNG into .FITS? Then images can be maybe live-stacked?
# TODO: Can ASTAP perform Plate Solving and live stacking directly on the RPi?
# TODO: Astrometry.net - can it be used to autolocate the telescope?
# TODO: Switch from picamera to libcamera libraries. (Requires Raspbian BULLSEYE - not all dependencies work on BULLSEYE yet.)
# TODO: Check for any conversions from Python datetime into skyfield time objects. Can use ts.from_datetime() method to do it cleanly.
# TODO: Can capture be faster if DNG export etc is delayed until AFTER observation complete? Or even a completely separate process from the menu?
# TODO: For satellite passes, it can JUST keep up with ISS passes.
#       - code.py needs to revert to earlier algorithm that smooths motion across the two axes in parallel.
#       - OnTarget needs to be more relaxed for fast moving objects.
#         - Consider a 'speed' option to help optimise things?
#       - Exposures need to be VERY short!
# TODO: Mark live pixels (fake stars in tracking, and remove from stacking)
# TODO: Make LATEST and TARGET images represent the relative magnitudes of the stars, astroalign will benefit from this extra information.

# Import required libraries
from typing import Tuple # For type hinting.
import sys # For version verification.
import serial # UART communication with a microcontroller.
import time # sleep functionality for pauses in execution. 
import RPi.GPIO as GPIO # Handling IO signals
from gpiozero import CPUTemperature
import glob # file system 
import os # OS Command execution
import subprocess # Threadsafe os command execution with access to command output.
import math # Math and trig functions. 
import json # json file handling.
import random # random number generator.
import cv2 # openCV for image file handling.  
import astroalign # Image alignment routines.
from datetime import datetime, timedelta, timezone
from datetime import time as datetime_time # rename this class to avoid ambiguity in the code.
#from skyfield.api import Star, Topos, position_of_radec, EarthSatellite
from skyfield.api import Star, Topos, EarthSatellite
from skyfield.api import Loader # Create own 'load' functionality by specifying the download directory this way.
#from skyfield.api import load_constellation_map, load_constellation_names 
from skyfield.api import load_constellation_names 
from skyfield.magnitudelib import planetary_magnitude # Calculate the realtime apparent magnitude of solar system objects.
from skyfield.api import N as skyfield_N_sign
from skyfield.api import S as skyfield_S_sign
from skyfield.api import E as skyfield_E_sign
from skyfield.api import W as skyfield_W_sign
from skyfield import almanac # Calculating set and rise times of objects.
from skyfield import VERSION as SkyfieldVersion
from skyfield.data import hipparcos # Hipparcos star catalog.
from skyfield.data import mpc # For comet trajectory handling.
from skyfield.data import stellarium # For constellation mapping. *Q* Can replace homegrown solution.
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN # Used for calculating Comet positions relative to sun.
from skyfield.units import Angle
import pytz # Timezone handling.
# textcolor is a homegrown simplified terminal colouring library. There are other libraries available for groovy character displays ('colorama', 'termcolor', 'blessing', 'rich' etc).
from textcolor import textcolor # Basic colour and cursor control codes for terminal displays.
from textcolor import colordisplay # Basic colour character graphics for chart display on terminal.
from textcolor import keyboardscanner # Simple non-blocking keyboard scanner.
from textcolor import proceduremenu, optionmenu # Basic menu handlers.
from textcolor import listchooser # Allow user to filter through a list of names.
from pidng.core import RPICAM2DNG # DNG data extraction from RPi camera RAW images. From https://github.com/schoolpost/pidng Needs to be 3.4.6 version. Later versions are not compatible.
import numpy as np # Fast array handling
import pandas # Dataframe handling.
import sep # This is used by astroalign, it is only imported here to flush out any problems with the package. (It has suffered from the classic 'numpy.ndarray size changed' in the past.)
import threading # Run the image capture in a separate thread so that motor movement can continue. *Q* Drift calculation and targetting could also move to separate thread.
from queue import Queue # Use queue mechanism to communicate between ObservationRun and Camera threads because they run in parallel.
import requests # To handle json response for seeing conditions from online services.
from requests.exceptions import HTTPError # Error handling.
import traceback
print (textcolor.clearforward()) # Clear the screen from the start point forward. 

ReloadData = False # Set this to TRUE to cause the data files to be reloaded from the online resources. Can be set by 'reload' runtime argument too.
ResumeObservation = False # Set this to TRUE to automatically load the previous observation and resume.

# Extract runtime parameters. (Not currently used...) 
RunArgs = sys.argv[1:] # Ignore 1st argument which is this program name.
if len(RunArgs) > 0:
    print ("Runtime arguments :-")
    for i in RunArgs:
        print('>', i)
        if i == 'reload': ReloadData = True
        if i == 'resume': ResumeObservation = True
        else: print (' ** Ignored **')
        
if ReloadData:
    print(textcolor.red("ReloadData triggered. Data files will be reloaded from original sources."))

ProjectRoot = '/home/pi/pilomar' # Where are all the project's folders sitting?

RequiredPythonVersion = 3 # Expect python3 to be used.
ActualPythonVersion = sys.version_info.major
if RequiredPythonVersion != ActualPythonVersion:
    print ("*ERROR* This program requires Python" + str(RequiredPythonVersion))
    raise Exception ("This program requires Python version " + str(RequiredPythonVersion))

# ------------------------------------------------------------------------------------------------------

def ClearScreen(): # 6 references.
    """ Use this to perform a clean wipe of the screen and force display windows to refresh. """
    colordisplay.GlobalForceRedraw() # Force all window buffers to fully redraw.
    print(textcolor.clearscreen()) # Clear screen for refresh.

# ------------------------------------------------------------------------------------------------------

def SourceCode() -> str: # 4 references.
    """ Return the filename of the source code being executed. """
    return sys.argv[0]

# ------------------------------------------------------------------------------------------------------

ProgramTitle = 'pilomar2' # Used in display titles and also filenaming to separate different generations of the program.
ProgramTitle = SourceCode().split('/')[-1].split('.')[0].lower() # Used in display titles and also filenaming to separate different generations of the program.

# ------------------------------------------------------------------------------------------------------

def SourceDate() -> datetime: # 3 references.
    """ Return datetime of the modified timestamp of the source file.
        As close as I get to 'version' stamping :) """
    try:
        sourcefile = SourceCode()
        t = os.path.getmtime(sourcefile)
        d = datetime.fromtimestamp(t)
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("SourceDate() failed") from e # Continue with regular exception handling.
    return d

# ------------------------------------------------------------------------------------------------------

def NowUTC() -> datetime: # Many references.
    """ Get system clock as UTC (timezone aware) 
        Microcontroller and Skyfield are operated in UTC vales. 
        All clock-times used in this program use the UTC timestamped clock.
        This should be the only reference to datetime.now() method in the entire
        program. All other uses should refer to this NowUTC() function.
        """
    return datetime.now(timezone.utc)

# ------------------------------------------------------------------------------------------------------

def CleanDatetimeString(line: str) -> str: # Many references.
    """ Remove all the special characters from a timestamp string.
        Converts things like YYYY-MM-DD HH:MM:SS into YYYYMMDDHHMMSS """
    try:
        if not isinstance(line,str): line = str(line) # Auto-convert into a string if it isn't already.
        for a in ['-',' ',':','.']:
            line = line.replace(a,'')
        line = line[:14] # Only accurate to SECONDS currently.
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("CleanDatetimeString() failed.") from e # Continue with regular exception stack.
    return line

# ------------------------------------------------------------------------------------------------------

def MctlStringToDatetime(line: str) -> datetime: # 3 references.
    """ Convert microcontroller timestring into conventional datatime value.
        The microcontroller sends timestamps as a simple YYYYMMDDHHMMSS string. """
    result = None # No good result yet.
    try:
        line = (line + (' ' * 14))[:14]
        year = int(line[0:4])
        month = int(line[4:6])
        day = int(line[6:8])
        hour = int(line[8:10])
        minute = int(line[10:12])
        second = int(line[12:14])
        result = datetime(year,month,day,hour,minute,second,0)
        result = result.replace(tzinfo=pytz.UTC) # Clarify it is a UTC timestamp.
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("MctlStringToDatetime() failed.") from e # Continue with regular exception stack.
    return result

# ------------------------------------------------------------------------------------------------------

def FileAge(filename): # 2 references.
    """ How many seconds old is a file? """
    if os.path.exists(filename):
        mtime = os.path.getmtime(filename)
        td = datetime.now() - datetime.fromtimestamp(mtime)
        result = int(td.total_seconds())
    else:
        result = None
    return result

# ------------------------------------------------------------------------------------------------------

def SafeName(text: str) -> str: # 6 references.
    """ Convert text into a 'safe' set of characters for the disc operations. """
    if not isinstance(text,str): text = str(text) # Convert to string if it isn't already.
    replacelist = [' ','/'] # Characters that will be replaced with '_'
    removelist = ["'",'"','(',')'] # Characters that will be removed. 
    try:
        for c in replacelist:
            text = text.replace(c,"_")
        for c in removelist:
            text = text.replace(c,"")
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("SafeName() failed.") from e # Continue with regular exception stack.
    return text

# ------------------------------------------------------------------------------------------------------

def DictionaryToString(rawdict: dict) -> str: # 7 references.
    """ Convert Python dictionary into simpler string for display purposes. """
    try:
        result = ''
        for key, value in rawdict.items():
            if len(result) > 0: result += ', '
            result += str(key) + '=' + str(value)
    except Exception as e:
        print("DictionaryToString:", str(e), ':', str(rawdict))
        result = ''
    return result
    
# ------------------------------------------------------------------------------------------------------

def BoolToString(value: bool) -> str: # No references.
    """ Convert a logical value into a single character string.
        Convert True into 'y'
        Convert False into 'n'. """
    if value: result = 'y'
    else: result = 'n'
    return result

# ------------------------------------------------------------------------------------------------------

def StringToBool(value: str) -> bool: # 8 references.
    """ Convert a single character representation back into a logical value.
        Convert 'y[es]' or 't[rue]' into True
        Convert everything else False. """
    result = False # Default is FALSE. 
    value = value.lower() # Handle upper and lower case.
    if len(value) > 1: value = value[0] # Consider first character only.
    if value in ['t','y']: result = True 
    return result

# ------------------------------------------------------------------------------------------------------

def HRBytes(bytecount: int) -> str: # Move to textcolor? # 14 references.
    """ Turn a large number into human readable format.
        Turns 1MB etc. (Note: Uses binary definition of 1MB etc.)    """
    try:
        if bytecount > (1024 ** 4): line = str(round(bytecount / (1024 ** 4),1)) + "Tb"
        elif bytecount > (1024 ** 3): line = str(round(bytecount / (1024 ** 3),1)) + "Gb"
        elif bytecount > (1024 ** 2): line = str(round(bytecount / (1024 ** 2),1)) + "Mb"
        elif bytecount > (1024 ** 1): line = str(round(bytecount / (1024 ** 1),1)) + "Kb"
        else: line = str(bytecount) + "b"
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("HRBytes() failed.") from e # Continue with regular exception stack.
    return line

# ------------------------------------------------------------------------------------------------------

def HRSeconds(seconds: int) -> str: # 15 references.
    """ Turn a number of seconds into days:hours:minutes:seconds """
    line = None
    try:
        d, remainder = divmod(seconds,24 * 60 * 60)
        h, remainder = divmod(remainder,60 * 60)
        m, s = divmod(remainder,60)
        line = str(int(h)).rjust(2,"0") + "h:" + str(int(m)).rjust(2,"0") + "m:" + str(int(s)).rjust(2,"0") + "s"
        if d > 0: # Only show days if needed.
            line = str(int(d)) + "d:" + line
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("HRSeconds() failed.") from e # Continue with regular exception stack.
    return line

# ------------------------------------------------------------------------------------------------------

def UtcTimeStamp() -> str: # 30 references.
    """ Return current UTC datetime value as a string of digits. Discard fractions of a second.
        Returns value in string format YYYYMMDDHHMMSS. """
    ds = None
    try:
        ds = str(NowUTC()).split(".")[0]
        ds = CleanDatetimeString(ds)
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("UtcTimeStamp() failed.") from e # Continue with regular exception stack.
    return ds

# ------------------------------------------------------------------------------------------------------

def HmsFromStamp(timestamp: datetime) -> str: # 5 references.
    """ Return the HH:MM:SS part of a timestamp as a string.
        Works with datetime input. """
    result = None
    try:
        if timestamp == None: # Protect from null values.
            result = ""
        else:
            result = str(timestamp)
            result = result.split(" ")[1]
            result = result.split(".")[0]
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("HmsFromStamp() failed.") from e # Continue with regular exception stack.
    return result

# ------------------------------------------------------------------------------------------------------

def NowHMS() -> str: # 95 references.
    """ Return current time as formatted string. 
        Returns HH:MM:SS string for the current time (UTC) """
    return HmsFromStamp(NowUTC())

# ------------------------------------------------------------------------------------------------------

# During an observation run we need to interrupt the processing. Python doesn't do this natively and
# <ctrl-c> will stop the program, so we use the curses library to provide a keyboard scanner. 
Keyboard = keyboardscanner() # Non-Blocking reader of the keyboard (via curses library). 

# Identify the program and version to the user.
print(textcolor.yellow(SourceCode() + " " + str(SourceDate())))

# ------------------------------------------------------------------------------------------------------

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
            self.NextTrigger = NowUTC() + timedelta(seconds=self.Period)
        else:
            self.NextTrigger = NowUTC() + timedelta(seconds=offset)
        self.SkipEvents = skip # If the timer falls behind, do we skip missed events?

    def _SetNextTrigger(self):
        """ Update the trigger due time to the next occurrence. 
            The next due time depends upon the skip parameter too! """
        if self.SkipEvents: # Skip any missed events. 
            while self.NextTrigger <= NowUTC():
                self.NextTrigger = self.NextTrigger + timedelta(seconds=self.Period)
        else: # Don't skip missed events, process every one!
            self.NextTrigger = self.NextTrigger + timedelta(seconds=self.Period)

    def Elapsed(self) -> bool:
        """ Return number of seconds that have elapsed since the timer was set. """
        starttime = self.NextTrigger - timedelta(seconds=self.Period)
        elapsed = (NowUTC() - starttime).total_seconds()
        return elapsed

    def ElapsedPc(self) -> float:
        """ Return % of time elapsed. """
        result = round(100 * self.Elapsed() / self.Period,0)
        return result
        
    def Remaining(self) -> float:
        """ Return number of seconds remaining on a timer. """
        result = (self.NextTrigger - NowUTC()).total_seconds()
        if result < 0.0: result = 0.0 # Timer expired.
        return result

    def Due(self) -> bool:
        """ If timed event is due, this returns TRUE. Otherwise returns FALSE.
            It automatically sets the next due timestamp. """
        if self.NextTrigger < NowUTC():
            result = True
            self._SetNextTrigger()
        else:
            result = False
        return result
        
# ///////////////////////////////////////////////////////////////////////////////////
# Initialize Logging.
# ///////////////////////////////////////////////////////////////////////////////////

class logfile(): # 2 references.
    """ An object to maintain a log file recording the activities and events in the program.
        This writes to a disc file and flushes the write buffers as quickly as it can.
        It can also copy ERROR messages to any nominated error window object (which must support a 'Print()' method. )        """
    def __init__(self,filename : str):
        self.FileName = filename
        self.PrevLogTime = NowUTC()
        self.ErrorWindow = None # Reference to window object for displaying errors.
        self.ErrorList = [] # Maintain list of any errors raised. These can then be summarised and reported if needed.
        # The following filters specify which types of messages are logged.
        # - If you change these lists, some messages may be ignored from file and displays.
        self.DetailFilter = ['u','f','d'] # Specify the detail levels that are recorded (user choices, flow, detail).
        self.LevelFilter = ['i','w','e'] # Specify which message types are recorded (info, warning, error).

    def Log(self,*args, **kwargs) -> bool:
        """ Record a log message. 
            All unnamed arguments are converted to str type and appended to the line logged.
            Some named arguments are supported. 
            terminal=True ... displays the message to the terminal too.
            level='info'/'warning'/'error' specifies level of information.
                  (warning and error are repeated to the terminal automatically) 
            detail='user'/'flow'/'detail' specifies the depth of logging that is recorded.
                  (user means user choices)
                  (flow means high level flow of the program, main logic events)
                  (detail means detailed flow of the program, decisions, calculations etc)
            errorprompt=The user is required to acknowledge the error message.
            sep=Separator string inserted between each argument appended to the log message. Default is ' '. """
        # Establish defaults for other arguments.
        terminal = True # Display to the user.
        errorprompt = False # Ask user to acknowledge.
        level = 'info' # Establish log level.
        detail = 'detail' # Establish the level of detail this entry represents.
        separator = ' '
        copytowindow = False
        for key,value in kwargs.items():
            if key == 'level': level = value.lower() # info, warning or error?
            elif key == 'detail': detail = value.lower() # user, flow, detail message types recorded.
            elif key == 'terminal': terminal = value # Display to the user or not?
            elif key == 'errorprompt': errorprompt = value
            elif key == 'window': copytowindow = value # Copy the message to the error window if possible.
            elif key == 'sep': separator = value # Separator string can be overridden.
        # Now generate the log message by appending all the unnamed arguments into a single string.
        line = ''
        for x in args: # Convert and append extra arguments.
            if not isinstance(x,str): x = str(x)
            line = (line + separator + x).strip()
        if errorprompt: terminal = True # User must see message if they are supposed to acknowledge it.
        # Write the message to the log file.
        dtNow = NowUTC()
        Elapsed = (dtNow - self.PrevLogTime).total_seconds() # The log message includes the elapsed time since the previous message.
        ES = "{:.6f}".format(Elapsed) # 6dp and make sure it is not in scientific notation.
        saveline = str(dtNow) + "\t" + ES + "\t" + line # Add current system timestamp and elapsed time to message. 
        printline = str(dtNow).split(".")[0] + " " + line # Add current system timestamp to message. 
        # Check if any LEVEL OR DETAIL filters are specified in the received parameters.
        if level[0] in self.LevelFilter and detail[0] in self.DetailFilter: # The filters pass the criteria for writing to disc.
            with open(self.FileName,'a') as f:
                f.write(saveline + '\n')
                f.flush() # Immediately flush to disc.
                os.fsync(f) # Flush in the OS too!
        # Handle the display and user response.
        if level[0] == 'e': # Error
            if terminal: # We're allowed to display on the terminal.
                self.ErrorList.append(printline) # Record the error for later summary or reporting.
                print(textcolor.red('** ERROR ** reported in LogFile: ') + printline)
                if errorprompt: # User has to acknowledge the error. 
                    #temp = input(textcolor.cyan("Press [ENTER] to continue: "))
                    input(textcolor.cyan("Press [ENTER] to continue: "))
            if self.ErrorWindow != None: self.ErrorWindow.Print(printline,fg=textcolor.BLACK,bg=textcolor.RED) # Error color.
        elif level[0] == 'w':
            if terminal: # We're allowed to display on the terminal.
                print(textcolor.yellow('WARNING: reported in LogFile: ') + printline)
                if errorprompt: # User has to acknowledge the warning. 
                    #temp = input(textcolor.cyan("Press [ENTER] to continue: "))
                    input(textcolor.cyan("Press [ENTER] to continue: "))
            if self.ErrorWindow != None and copytowindow: self.ErrorWindow.Print(printline,fg=textcolor.YELLOW,bg=textcolor.BLACK) # Warning color.
        elif terminal: # Display to the terminal. 
            print(printline)
            if self.ErrorWindow != None and copytowindow: self.ErrorWindow.Print(printline) # Info lines just keep default color scheme.
        self.PrevLogTime = NowUTC() # Note the last time a message was logged. This is used to report the elapsed time between messages in the log file. 
        return True

    def ReportSlowEvents(self,limit=4.0): ### DEVELOPMENT ###
        """ Analyses the log file and reports any events which have taken too long. """
        print('Analysing log file for slow events')
        with open(self.FileName,'r') as f:
            prevline = ''
            for line in f:
                thisline = line.strip()
                lineitems = thisline.split('\t')
                if len(lineitems) > 2 and IsFloat(lineitems[1]):
                    delay = float(lineitems[1])
                    if delay >= limit: # Delay found.
                        print('Delay',delay,':-')
                        print(prevline)
                        print(thisline)
                prevline = thisline
        print('Analysis complete')

    def ReportException(self,e,level='error',comment=None):
        """ Record any exception class in the log file.
            This does not terminate, it just reports/logs the
            exception then allows the program to continue. """
        self.Log("logfile.ReportException(): Error",str(e),level='error')
        self.RecordTraceback(e)
        if hasattr(e,'__dict__'): # The exception object has a dictionary that can be reported.
            for key, value in e.__dict__.items():
                self.Log("logfile.ReportException():",key,":",value,level=level)
        else:
            self.Log("logfile.ReportException(): No __dict__ object to report. (",type(e),")",level='error')
        if comment != None:
            self.Log("logfile.ReportException(): Comment:",str(comment),level=level)

    def RaiseException(self,e,level='error',comment=None):
        """ Record any exception class in the log file. 
            Then terminate via regular exception handler. """
        self.RecordTraceback(e)
        if hasattr(e,'__dict__'): # The exception object has a dictionary that can be reported.
            for key, value in e.__dict__.items():
                self.Log("logfile.RaiseException():",key,":",value,level=level)
        else:
            self.Log("logfile.RaiseException(): No __dict__ object to report. (",type(e),")",level='error')
        if comment != None:
            self.Log("logfile.RaiseException(): Comment:",str(comment),level=level)
        raise Exception('Program exception raised') from e # Terminate through regular exception stack.

    def RecordTraceback(self,e,terminal=True):
        """ Use Traceback module to report the execution stack to the log file.
            Setting terminal=False prevents the error being displayed on the screen. """
        self.Log("logfile.RecordTraceback(): ErrorMessage", str(e),terminal=terminal)
        a = traceback.format_exc() # String representation of stack report.
        b = a.split('\n')
        for c in b:
            self.Log("logfile.RecordTraceback():",c,terminal=terminal)

# ------------------------------------------------------------------------------------------------------

# Clear old log files.
logdir = ProjectRoot + "/log"
LogFileName = logdir + "/" + ProgramTitle + "_" + UtcTimeStamp() + ".log"
print("Main log to", LogFileName)
MainLog = logfile(LogFileName) # Create a MAIN log file object.
MainLog.Log("Startup parameters:", RunArgs,terminal=False)
CamLogFileName = logdir + "/" + ProgramTitle + "_camera_" + UtcTimeStamp() + ".log"
MainLog.Log("Camera log to", LogFileName)
CamLog = logfile(CamLogFileName) # Create a CAMERA specific log file. (This runs in separate thread, unsure if logging would be thread-safe.)
HistoryFile = ProjectRoot + '/data/' + ProgramTitle + '_sessions.txt' # Chosen observation targets and settings are stored in this file.
MainLog.Log("Skyfield version:", SkyfieldVersion,terminal=False)
textcolor.GetTermType()
MainLog.Log("Terminal type:", textcolor.TermType, textcolor.Mode,terminal=False)

# ------------------------------------------------------------------------------------------------------

def osCmd(cmd,output : str = 'none') -> list: # Common # 30 references.
    """ Execute a command and record it to the log file.
        command and result is always recorded in the log file,
        1st return parameter is a clean list of output lines,
        2nd return parameter is the return code, 0 = Success, <> 0 is error.
        output='terminal' : Default output is to the terminal. 
        output='none' : Suppresses output.
        output contains '.' : Output is written to that file. 
        This should be thread safe.
        """
    MainLog.Log(cmd,terminal=False)
    # returncode = 0 # Assume success.
    try:
        result = subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode('utf-8')
    except subprocess.CalledProcessError as e:
        MainLog.Log("osCmd " + cmd + " returned " + str(e),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned returncode " + str(e.returncode),terminal=False)
        # returncode = e.returncode # return the return code.
        MainLog.Log("osCmd " + cmd + " returned output " + str(e.output),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned cmd " + str(e.cmd),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned stdout " + str(e.stdout),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned stderr " + str(e.stderr),terminal=False)
        result = "" # We lose result output, even if some was generated before the error was reached.
    lines = result.split('\n')
    returnlist = []
    for line in lines:
        if '.' in output:
            with open(output,'a') as f: # Create or append to the specified file.
                f.write(line + "\n")
        if output == 'terminal': print (line) # display to the terminal
        MainLog.Log(line,terminal=False)
        returnlist.append(line) # Construct clean returnlist of the output.
    return returnlist

# ------------------------------------------------------------------------------------------------------

def DrawDumbbell(imagebuffer,drawfrom,drawto,rad,fromcolor,tocolor,linecolor,arrow):
    """ Add a 'dumbbell' to an image between two different points.
    
        from = tuple (x,y)
        to = tuple (x,y)
        fromcolor = tuple (b,g,r,a) 
        tocolor = tuple (b,g,r,a)
        linecolor = tuple (b,g,r,a)
        arrow = boolean 6
    
          xxx                     .    xxx
         x   x                     .  x   x
        x     x                     .x     x
        x  O  x----------------------x  o  x
        x     x                     .x     x 
         x   x                     .  x   x
          xxx                     .    xxx                   """
        
    fromx = drawfrom[0] # Centre of the FROM circle.
    fromy = drawfrom[1]
    tox = drawto[0] # Centre of the TO circle.
    toy = drawto[1]
    # Calculate distance between FROM and TO points.
    dx = tox - fromx
    dy = toy - fromy
    distance = math.sqrt((dx **2) + (dy **2))
    angle = math.atan2(dy,dx) # What angle is the joining line at?
    # Line does not cross the boundary circle drawn around each point.
    # Calculate the points on the circumference of each circle that the arrowed line will start and end on.
    rc = rad * math.cos(angle) # x offset for circle edge where line starts.
    rs = rad * math.sin(angle) # y offset for circle edge where line starts.
    startx = int(fromx + rc) # Draw line from this point on the starting circle.
    starty = int(fromy + rs)
    endx = int(tox - rc) # Draw line to this point on the ending circle.
    endy = int(toy - rs)
    dia = rad * 2 # Only draw the line if there's a big enough gap between the two circles.
    if distance > dia: # Enough space to draw a line.
        arrowproportion = 10.0 / (distance - dia) # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
        if arrow: imagebuffer = cv2.arrowedLine(imagebuffer, (startx,starty), (endx,endy), linecolor, thickness=1, line_type=cv2.LINE_AA, tipLength=arrowproportion)
        else: imagebuffer = cv2.line(imagebuffer, (startx,starty), (endx,endy), linecolor, thickness=1, lineType=cv2.LINE_AA)
    imagebuffer = cv2.circle(imagebuffer,(fromx, fromy), rad, fromcolor, thickness=1, lineType=cv2.LINE_AA)
    imagebuffer = cv2.circle(imagebuffer,(tox, toy), rad, tocolor, thickness=1, lineType=cv2.LINE_AA)
    return imagebuffer # The image now has the 'dumbbell' drawn on it.

# ------------------------------------------------------------------------------------------------------

def osCmdCode(cmd,output : str = 'none') -> list: # Common # 1 references.
    """ Execute a command and record it to the log file.
        command and result is always recorded in the log file,
        Return parameter is the return code, 0 = Success, <> 0 is error.
        output='terminal' : Default output is to the terminal. 
        output='none' : Suppresses output.
        output contains '.' : Output is written to that file. 
        This should be thread safe.
        """
    MainLog.Log(cmd,terminal=False)
    returncode = 0 # Assume success.
    try:
        result = subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode('utf-8')
    except subprocess.CalledProcessError as e:
        MainLog.Log("osCmd " + cmd + " returned " + str(e),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned returncode " + str(e.returncode),terminal=False)
        returncode = e.returncode # return the return code.
        MainLog.Log("osCmd " + cmd + " returned output " + str(e.output),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned cmd " + str(e.cmd),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned stdout " + str(e.stdout),terminal=False)
        MainLog.Log("osCmd " + cmd + " returned stderr " + str(e.stderr),terminal=False)
        result = "" # We lose result output, even if some was generated before the error was reached.
    lines = result.split('\n')
    for line in lines:
        if '.' in output:
            with open(output,'a') as f: # Create or append to the specified file.
                f.write(line + "\n")
        if output == 'terminal': print (line) # display to the terminal
        MainLog.Log(line,terminal=False)
    return returncode

# ------------------------------------------------------------------------------------------------------

# Remove out of date log files to preserve disc space.
print (textcolor.yellow('Removing out of date log files to preserve disc space...'))
cmd = "find " + logdir + " -type f -name '" + ProgramTitle + "_*.log' -mtime +2 -delete"
print(cmd) # Show the user the command being executed.
osCmd(cmd)
print (textcolor.yellow('Done.'))
# Check 32 vs 64 bit O/S
osbits = int(osCmd('getconf LONG_BIT')[0])
unamem = osCmd('uname -m')[0]
MainLog.Log('Running on', unamem, osbits, 'bit system.',terminal=False)

# ------------------------------------------------------------------------------------------------------

class attributemaster(): # A parent class containing some common methods that other classes can inherit from. # 13 references.
    """ General base class that other classes can be based upon.
        Provides useful methods that many classes may use. """

    def SaveAttributes(self,filename : str):
        """ Pull parameter attribute values out of the object and store back into the parameter dictionary.
            Save the parameter dictionary back to disc.
            If the target file exists it will be overwritten by the 'mv' command. """
        tempfilename = filename.replace(".json",".tmp") # During creation, the file is given a temporary filename, so that any reading process doesn't pick it up too soon.
        tempdictionary = self.SaveToDictionary() # Save to a working dictionary. 
        with open(tempfilename,'w') as f: # Dump as json to disc.
            json.dump(tempdictionary,f,indent=4,default=str) # Save the updated dictionary back to disc.
        osCmd("mv " + tempfilename + " " + filename) # When the file is complete, rename it to its proper name.

    def SaveToDictionary(self,allowlist = None, denylist = None, initialdictionary={}, nameprefix=None) -> dict:
        """ Adds the ability to save attributes of the object to a dictionary.
            It ignores any attributes starting with '_' character.
            allowlist: If specified lists the fieldnames that should be saved. If missing, all fields are saved.
            denylist: If specified lists fieldnames that will NOT be saved, all others are.
            initialdictionary provides initial values that this method will append to.
            nameprefix provides an optional prefix to all the fieldnames.
            It will also ignore certain datatypes which don't save well or are typically very large (numpy arrays). """
        confdict = initialdictionary # Start an empty dictionary. 
        ignoretypes = [type(np.ndarray)]
        for attr, value in vars(self).items():
            if attr[0] == '_': continue # Don't send internals.
            if type(attr) in ignoretypes: continue # Don't export certain variable types.
            if denylist != None and attr in denylist: continue # Blocked item. Don't save.
            if allowlist == None or attr in allowlist: # Allowed item, save.
                if nameprefix != None: attr = nameprefix + attr # Add optional prefix to fieldname.
                confdict[attr] = value
                MainLog.Log('SaveToDictionary: Saved: ', attr, value,terminal=False)
        return confdict

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Parameter settings
# ///////////////////////////////////////////////////////////////////////////////////

class parameters(attributemaster): # Common # 1 references.
    """ Class to load, store and manage parameters for the program.
        The parameters() class allows you to load runtime parameters from a file.
        It can also reload parameters during a run if you want to change them without restarting the program.
        The latest parameter settings are automatically written back to disc when the program closes.
        - So if you change any of these parameters during the run, they will remain active the next time the program is started.
        These parameters are generally those which you may want to modify during development or testing. """

    def __init__(self,filename,log=None):
        if log == None: log = MainLog.Log # Default logging method that is used internally.
        self.Log = log # Handle to the logging method that this object should use. 
        self._Dictionary = {}
        self.ParamFileName = filename # The disc copy of the parameter file. This is overwritten if the program completes correctly.
        if os.path.isfile(self.ParamFileName): # If the dictionary file exists, we'll import it now.
            with open(self.ParamFileName,'r') as f:
                self.Log("Loading parameters from file: " + self.ParamFileName)
                self._Dictionary = json.load(f) # Overwrite the default parameter values with anything from file.
        # Pull parameter values from the dictionary, and update the dictionary with defaults if necessary.
        self.BatchSize = self._Dictionary.get('BatchSize',100) # How many photos to take in a batch.
        self.ControlBatchSize = self._Dictionary.get('ControlBatchSize',20) # How many images to capture in each 'control set' (DARK, BIAS etc). High values offer limited gains.
        self.ColorScheme = self._Dictionary.get('ColorScheme','green') # What colour scheme to use? (green, blue, red, white)
        self.ChartEnabled = self._Dictionary.get('ChartEnabled',True) # Generate character base chart during observation run?
        self.MotorsEnabled = self._Dictionary.get('MotorsEnabled',True) # Are the motors to be powered on?
        self.CameraEnabled = self._Dictionary.get('CameraEnabled',True) # Is the camera on?
        self.CameraSaveJpg = self._Dictionary.get('CameraSaveJpg',True) # Save the jpg image from observations, but will strip out the embedded RAW data.
        self.CameraSaveDng = self._Dictionary.get('CameraSaveDng',True) # Save the raw image data as .dng file.
        if self.CameraSaveJpg or self.CameraSaveDng: pass # OK
        else: self.Log("No image types are saved according to the parameters.",level='warning')
        self.DisableCleanup = self._Dictionary.get('DisableCleanup',True) # Set to TRUE to disable the on-chip cleanup. (More pure RAW image is captured.)
        self.BacklashEnabled = self._Dictionary.get('BacklashEnabled',False) # ENABLE to let the motors make extra moves to cope with gear backlash.
        self.MctlLedStatus = self._Dictionary.get('MctlLedStatus',True) # Turn on STATUS LEDs on microcontroller.
        self.TrackingInterval = self._Dictionary.get('TrackingInterval',300) # How many seconds between each target tracking check?
        self.TrackingStarRadius = self._Dictionary.get('TrackingStarRadius',3) # Pixel radius of stars in clean targetting images.
        self.TrackingExposureSeconds = self._Dictionary.get('TrackingExposureSeconds',5.0) # How long is the exposure when capturing a tracking photo. It must be standardised rather than the 
        self.DebugMode = self._Dictionary.get('DebugMode',True) # In DebugMode ObservationRun does not display the status windows. This makes error messages easier to read.
        self.HomeLat = self._Dictionary.get('HomeLat',None) # Latitude of the observer.
        self.HomeLon = self._Dictionary.get('HomeLon',None) # Longitude of the observer.
        self.HomeLatVal = 0.0
        if self.HomeLat != None:
            self.HomeLatVal = float(self.HomeLat.split(" ")[0]) # Convert to float value.
            if self.HomeLat.split(" ")[1] == "S": self.HomeLatVal = self.HomeLatVal * -1 # -ve for southern hemisphere in Skyfield.
        self.HomeLonVal = 0.0
        if self.HomeLon != None:
            self.HomeLonVal = float(self.HomeLon.split(" ")[0]) # Convert to float value.
            if self.HomeLon.split(" ")[1] == "W": self.HomeLonVal = self.HomeLonVal * -1 # -ve for western hemisphere in Skyfield.
        self.Log("Parameters: Home:", self.HomeLat, self.HomeLon, ":", self.HomeLatVal, self.HomeLonVal,terminal=False)
        self.MarkupInterval = self._Dictionary.get('MarkupInterval',300) # How often do we generate a preview image (seconds).
        self.GenerateOverlay = self._Dictionary.get('GenerateOverlay',False) # Flag to generate an overlay file at the start of the observation. (transparent .png image of expected objects)
        self.MarkupAvi = self._Dictionary.get('MarkupAvi',False) # Generate a small animation of the preview files at the end of the observation.
        self.MarkupShowLabels = self._Dictionary.get('MarkupShowLabels',False) # Add labels to markup images, such as locations.
        self.MarkupShowNames = self._Dictionary.get('MarkupShowNames',False) # Add names to markup images, such as star names.
        self.TargetInclusionRadius = self._Dictionary.get('TargetInclusionRadius',15) # Angle (radius) for inclusion of neighbouring stars when generating target image.
        self.TargetMinMagnitude = self._Dictionary.get('TargetMinMagnitude',9.0) # Minimum magnitude for stars to display. At a 2 second exposure, Magnitude 5.0 is a good value, at 5 seconds, Mag 9.0 is better.
        self.LensLength = self._Dictionary.get('LensLength',16.0) # Focal length of lens
        self.LensHorizontalFov = self._Dictionary.get('LensHorizontalFov',21.8) # Degrees FoV horizontally
        self.LensVerticalFov = self._Dictionary.get('LensVerticalFov',16.4) # Degrees FoV vertically.
        self.SensorType = self._Dictionary.get('SensorType','imx477') # Sensor type. 
        self.TrajectoryWindow = self._Dictionary.get('TrajectoryWindow',1200) # How many seconds into the future should the motor trajectory last?
        self.UseDynamicTrajectoryPeriods = self._Dictionary.get('UseDynamicTrajectoryPeriods',True) # Can we use flexible time periods in the trajectory plan?
        self.ObservationResetsMctl = self._Dictionary.get('ObservationResetsMctl',False) # Force a reset of the microcontroller each time a new ObservationRun begins?
        self.MctlResetPin = self._Dictionary.get('MctlResetPin',4) # Which RPi4 GPIO pin is used to RESET the microcontroller?
        # Display colorscheme.
        self.MenuTitleFG = self._Dictionary.get('MenuTitleFG',textcolor.BLACK)
        self.MenuTitleBG = self._Dictionary.get('MenuTitleBG',textcolor.GRAY)
        self.MenuSubtitleFG = self._Dictionary.get('MenuSubtitleFG',textcolor.BLACK)
        self.MenuSubtitleBG = self._Dictionary.get('MenuSubtitleBG',textcolor.GREY30)
        # - ObservationStatusWindow
        self.TitleFG = self._Dictionary.get('TitleFG',textcolor.WHITE)
        self.TitleBG = self._Dictionary.get('TitleBG',textcolor.GRAY)
        self.TextFG = self._Dictionary.get('TextFG',textcolor.WHITE)
        self.TextBG = self._Dictionary.get('TextBG',textcolor.BLACK)
        self.TextGood = self._Dictionary.get('TextGood',textcolor.LIGHTGREEN)
        self.TextPoor = self._Dictionary.get('TextPoor',textcolor.YELLOW)
        self.TextBad = self._Dictionary.get('TextBad',textcolor.ORANGERED1)
        self.BorderFG = self._Dictionary.get('BorderFG',textcolor.DARKGREEN)
        self.BorderBG = self._Dictionary.get('BorderBG',textcolor.BLACK)
        self.SetColorScheme(self.ColorScheme)
        self.InitialGoTo = self._Dictionary.get('InitialGoTo',True) # Perform initial GOTO before downloading the trajectory. (Eases comms with microcontroller.)
        self.KeyboardScanDelay = self._Dictionary.get('KeyboardScanDelay',6) # Number of refresh loops performed before scanning the keyboard during observations. Higher delay = Slower scan rate.
        self.MinAzimuthAngle = self._Dictionary.get('MinAzimuthAngle',0)
        self.MaxAzimuthAngle = self._Dictionary.get('MaxAzimuthAngle',360)
        self.MinAltitudeAngle = self._Dictionary.get('MinAzimuthAngle',0)
        self.MaxAltitudeAngle = self._Dictionary.get('MaxAzimuthAngle',90)
        self.UseTracking = self._Dictionary.get('UseTracking',True) # TRUE = Use image tracking. FALSE = No tracking.
        self.UseWeatherService = self._Dictionary.get('UseWeatherService',True) # Enable this to pull weather information from a web service.
        self.FastImageCapture = self._Dictionary.get('FastImageCapture',False) # Do not extract raw data during observation, do it later. Captures data more quickly.
        self.FakeStars = self._Dictionary.get('FakeStars',True) # Do simulated images includes stars, nebulae etc?
        self.FakeNoise = self._Dictionary.get('FakeNoise',True) # Do simulated images also simulate sensor noise?
        self.FakeField = self._Dictionary.get('FakeField',True) # Do simulated images also simulate electronic field noise?
        self.FakePollution = self._Dictionary.get('FakePollution',True) # Do simulated images also simulate light pollution?
        self.FakeMeteor = self._Dictionary.get('FakeMeteor',True) # Do simulated images also fake meteor streaks?
        self.FakeMeteorPercent = self._Dictionary.get('FakeMeteorPercent',2) # What percentage of images get fake meteor streaks?
        self.UseMicrostepping = self._Dictionary.get('UseMicrostepping',False) # Do we let the motors use microstepping for fine position control at the cost of lower torque?
        self.FindTransformScale = self._Dictionary.get('FindTransformScale',1.0) # When passing star lists to FindTransform, how are the (x,y) coordinates scaled?
        if self.FindTransformScale < 0.01: self.VariableFindTransformScale = 0.01 # Protect minimum value. 
        if self.FindTransformScale > 1.0: self.VariableFindTransformScale = 1.0 # Protect maximum value. 
        self.ScanForMeteors = self._Dictionary.get('ScanForMeteors',True) # Scan light images for streaks, report them if found.
        self.UseUSBStorage = self._Dictionary.get('UseUSBStorage',True) # If USB storage is mounted then images are stored there instead of the SD card.

    def ChooseColorScheme(self):
        """ Prompt for and set a standard color scheme. """
        ItemList = ['white','blue','green','red']
        objectchooser = listchooser(ItemList,compress=False) # Always show the full list.
        print (textcolor.yellow('Choose color scheme to apply.'))
        ChosenItem = objectchooser.Prompt()
        if ChosenItem == None: return # Nothing to change.
        else: self.SetColorScheme(ChosenItem)
        self.ShowColorScheme() # Show the current color scheme.
        print (textcolor.yellow('Please restart the program for these changes to take effect.'))
        return
        
    def ChooseColor(self):
        """ Prompt for color and update display characteristics to match. """
        # Prompt for color item to change.
        ItemList = ['MenuTitleFG','MenuTitleBG','MenuSubtitleFG','MenuSubtitleBG','TitleFG','TitleBG','TextFG','TextBG','TextGood','TextPoor','TextBad','BorderFG','BorderBG']
        objectchooser = listchooser(ItemList,compress=False) # Always show the full list.
        print (textcolor.yellow('Choose color item to change.'))
        ChosenItem = objectchooser.Prompt()
        if ChosenItem == None: return # Nothing to change.
        print (textcolor.yellow('Chosen',ChosenItem))
        print (textcolor.yellow('Available colors:-'))
        textcolor.listcolors()
        Result = None
        while Result == None:
            Result = input(textcolor.cyan('Color (0-255), x to quit, ? for list: '))
            if Result.lower() == 'x': 
                Result = None
                break # Quit
            if Result == '?':
                textcolor.listcolors()
                continue # Try again
            if IsInt(Result):
                i = int(Result)
                if i < 0 or i > 255: # Out of range.
                    print(textcolor.red('Must be in the range 0 - 255'))
                    Result = None
                    continue # Try again.
                # Good value, assign it.
                print ('Setting',self,ChosenItem,Result)
                setattr(self,ChosenItem,Result) # Dynamically set the value in the parameter class.
                self.ColorScheme = 'custom'
                print ("Example choice on white: ",textcolor.fgbgcolor(Result,textcolor.WHITE," Lorem ipsum dolor sit amet "))
                print ("Example choice on black: ",textcolor.fgbgcolor(Result,textcolor.BLACK," Lorem ipsum dolor sit amet "))
                print ("Example white on choice: ",textcolor.fgbgcolor(textcolor.WHITE,Result," Lorem ipsum dolor sit amet "))
                print ("Example black on choice: ",textcolor.fgbgcolor(textcolor.BLACK,Result," Lorem ipsum dolor sit amet "))
            else:
                Result = None
                continue # Try again
        self.ShowColorScheme() # Show the current color scheme.
        # print (textcolor.yellow('You must restart the program for these changes to take effect.'))
        textcolor.TextBox('You must restart the program for these changes to take effect.',fg=textcolor.yellow,bg=textcolor.black)
        return

    def SetColorScheme(self,scheme='green'):
        if scheme == "white": # Chosen schemes.
            # - Menu
            self.MenuTitleFG = textcolor.GREY66
            self.MenuTitleBG = textcolor.GREY11
            self.MenuSubtitleFG = textcolor.GREY66
            self.MenuSubtitleBG = textcolor.GREY7
            # - ObservationStatusWindow
            self.TitleFG = textcolor.GREY66
            self.TitleBG = textcolor.GREY11
            self.TextFG = textcolor.GREY3
            self.TextBG = textcolor.BLACK
            self.TextGood = textcolor.WHITE
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.GREY15
            self.BorderBG = textcolor.BLACK
        elif scheme == "blue": # Chosen schemes.
            # - Menu
            self.MenuTitleFG = textcolor.WHITE
            self.MenuTitleBG = textcolor.DEEPSKYBLUE4A
            self.MenuSubtitleFG = textcolor.BLACK
            self.MenuSubtitleBG = textcolor.DEEPSKYBLUE3
            # - ObservationStatusWindow
            self.TitleFG = textcolor.WHITE
            self.TitleBG = textcolor.DEEPSKYBLUE4A
            self.TextFG = textcolor.CYAN
            self.TextBG = textcolor.BLACK
            self.TextGood = textcolor.LIGHTSKYBLUE1
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.NAVYBLUE
            self.BorderBG = textcolor.BLACK
        elif scheme == "green": # Chosen schemes.
            # - Menu
            self.MenuTitleFG = textcolor.LIME
            self.MenuTitleBG = textcolor.DARKGREEN
            self.MenuSubtitleFG = textcolor.BLACK
            self.MenuSubtitleBG = textcolor.GREEN
            # - ObservationStatusWindow
            self.TitleFG = textcolor.LIME
            self.TitleBG = textcolor.DARKGREEN
            self.TextFG = textcolor.GREEN
            self.TextBG = textcolor.BLACK
            self.TextGood = textcolor.LIGHTGREEN
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.DARKGREEN
            self.BorderBG = textcolor.BLACK
        elif scheme == "red": # Chosen schemes.
            # - Menu
            self.MenuTitleFG = textcolor.WHITE
            self.MenuTitleBG = textcolor.DARKRED
            self.MenuSubtitleFG = textcolor.BLACK
            self.MenuSubtitleBG = textcolor.RED3
            # - ObservationStatusWindow
            self.TitleFG = textcolor.WHITE
            self.TitleBG = textcolor.RED3
            self.TextFG = textcolor.RED
            self.TextBG = textcolor.BLACK
            self.TextGood = textcolor.LIGHTPINK1
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.DARKRED
            self.BorderBG = textcolor.BLACK
        else: return # Don't do anything.
        self.ColorScheme = scheme
        return

    def ShowColorScheme(self):
        """ Demonstrate current color scheme. """
        print(textcolor.yellow("Current color scheme (" + str(self.ColorScheme) + "):"))
        print(textcolor.fgbgcolor(self.MenuTitleFG,self.MenuTitleBG,      " MENU TITLE    "))
        print(textcolor.fgbgcolor(self.MenuSubtitleFG,self.MenuSubtitleBG," MENU SUBTITLE "))
        print(textcolor.fgbgcolor(self.TitleFG,self.TitleBG,              " TITLE         "))
        print(textcolor.fgbgcolor(self.TextFG,self.TextBG,                " TEXT          "))
        print(textcolor.fgbgcolor(self.TextGood,self.TextBG,              " GOOD VALUE    "))
        print(textcolor.fgbgcolor(self.TextPoor,self.TextBG,              " POOR VALUE    "))
        print(textcolor.fgbgcolor(self.TextBad,self.TextBG,               " BAD VALUE     "))
        print(textcolor.fgbgcolor(self.BorderFG,self.BorderBG,            " BORDER        "))
        return

    def Show(self):
        """ List parameters. """
        print (textcolor.yellow("List parameters:"))
        tempd = vars(self) # Load variables into a temporary dictionary.
        for key,value in tempd.items():
            if key.startswith('_'): continue # Ignore internals.
            print (textcolor.yellow(key.rjust(30)) + " : " + str(value))
        #temp = input(textcolor.cyan("Press [enter] to continue:"))
        input(textcolor.cyan("Press [enter] to continue:"))

# Establish the filename of the parameters file that will be loaded.
ParameterFileName = ProjectRoot + '/data/' + ProgramTitle + '_params.json'
Parameters = parameters(filename=ParameterFileName,log=MainLog.Log) # Create and load parameters.

if Parameters.HomeLat == None or Parameters.HomeLon == None:
    # Home location is not yet set. Save the parameter file for editing then quit.
    # The user has to manually enter the home latitude and longitude into the paramter file.
    Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
    print(textcolor.red('Home location is not set in ' + Parameters.ParamFileName))
    print(' ')
    print(textcolor.yellow('Eg: Paris, France : "HomeLat" : "48.864716 N",'))
    print(textcolor.yellow('                    "HomeLon" : "2.349014 E",'))
    print(' ')
    print(textcolor.yellow('    Atlanta, USA  : "HomeLat" : "33.753746 N",'))
    print(textcolor.yellow('                    "HomeLon" : "84.386330 W",'))
    print(' ')
    print(textcolor.yellow('    Toyko, Japan  : "HomeLat" : "35.652832 N",'))
    print(textcolor.yellow('                    "HomeLon" : "139.839478 E",'))
    print(' ')
    textcolor.TextBox('Please edit the HomeLat and HomeLon parameters, then restart this program.',fg=textcolor.WHITE,bg=textcolor.RED)
    exit() # Quit the program.
    
if Parameters.HomeLatVal < 0: # We're in the Southern Hemisphere. The software isn't tested for that.
    linelist = ["Home Latitude (" + str(Parameters.HomeLatVal) + ") is in the Southern Hemisphere.",
                "Sorry, but the Pilomar software has not been validated for southern latitudes."]
    textcolor.TextBox(linelist,fg=textcolor.WHITE,bg=textcolor.RED)
    exit() # Quit the program.

# Create global timers.
PreviewTimer = timer(period=Parameters.MarkupInterval) # ObservationRun will generate a Preview image every 180 seconds. 

# Colour scheme for displays.
MENU_TITLE_FG = Parameters.MenuTitleFG
MENU_TITLE_BG = Parameters.MenuTitleBG
MENU_SUBTITLE_FG = Parameters.MenuSubtitleFG
MENU_SUBTITLE_BG = Parameters.MenuSubtitleBG
OSW_TITLE_FG = Parameters.TitleFG
OSW_TITLE_BG = Parameters.TitleBG
OSW_TEXT_FG = Parameters.TextFG
OSW_TEXT_BG = Parameters.TextBG
OSW_TEXT_GOOD = Parameters.TextGood
OSW_TEXT_POOR = Parameters.TextPoor
OSW_TEXT_BAD = Parameters.TextBad
OSW_BORDER_FG = Parameters.BorderFG
OSW_BORDER_BG = Parameters.BorderBG

# Color names for OpenCV drawing. (Beware colors are BGR not RGB!)
# 4 Channel with transparency (BLUE, GREEN, RED, OPACITY)
BGRABlack = (0,0,0,255)
BGRABlue = (255,0,0,255)
BGRACyan = (255,255,0,255)
BGRADimGray = (105,105,105,255)
BGRAGold = (0,215,255,255)
BGRAGreen = (0,255,0,255)
BGRAHotPink = (180,105,255,255)
BGRALimeGreen = (50,205,50,255)
BGRAOrange = (0,165,255,255)
BGRAPaleGreen = (152,251,152,255)
BGRARed = (0,0,255,255)
BGRATransparent = (0,0,0,0)
BGRAWhite = (255,255,255,255)
BGRAYellow = (0,255,255,255)
# 3 Channel BLUE, GREEN, RED only.
BGRBlack = (0,0,0)
BGRBlue = (255,0,0)
BGRUltraDarkBlue = (35,0,0)
BGRVeryDarkBlue = (70,0,0)
BGRDarkBlue = (135,0,0)
BGRCyan = (255,255,0)
BGRDimGray = (105,105,105)
BGRGold = (0,215,255)
BGRLimeGreen = (50,205,50)
BGRPaleGreen = (152,251,152)
BGRGreen = (0,255,0)
BGRMidGreen = (0,127,0)
BGRDimGreen = (0,63,0)
BGRDarkGreen = (0,31,0)
BGRHotPink = (180,105,255)
BGROrange = (0,165,255)
BGRRed = (0,0,255)
BGRVeryDarkRed = (0,0,10)
BGRWhite = (255,255,255)
BGRYellow = (0,255,255)
# Grayscale single channel.
GRAYSCALEWhite = 255
GRAYSCALE50 = 127
GRAYSCALEBlack = 0


# ///////////////////////////////////////////////////////////////////////////////////
# Trigonometry functions.
# ///////////////////////////////////////////////////////////////////////////////////

def AltAzToXYZ(alt: float, az: float, distance:float =1.0) -> Tuple[float, float, float]: # 1 references.
    """ Convert alt,az angles to XYZ coordinates. Based upon originlab definition on web. 
        X and Y web definitions are swapped to match alignment in Pilomar space. """
    try:
        y = distance * math.cos(math.radians(alt)) * math.cos(math.radians(az))
        x = distance * math.cos(math.radians(alt)) * math.sin(math.radians(az))
        z = distance * math.sin(math.radians(alt))
    except Exception as e:
        MainLog.RaiseException(e,comment='AltAzToXYZ') # Trap all the exception information in the main log file.
    return x,y,z 
    
# ------------------------------------------------------------------------------------------------------

def XYZToAltAz(x:float, y:float, z:float) -> Tuple[float, float]: # 1 references.
    """ Convert 3D coordinates into altitude and azimuth. """
    try:
        range = math.sqrt(x * x + y * y)
        alt = math.degrees(math.atan2(z,range))
        az = math.degrees(math.atan2(x,y)) % 360
    except Exception as e:
        MainLog.RaiseException(e,comment='XYZToAltAz') # Trap all the exception information in the main log file.
    return alt, az

# ------------------------------------------------------------------------------------------------------

# def RotateYZ(y:float ,z:float ,angle:float) -> Tuple[float, float]: # 0 references.
#     """ Rotate Y,Z coordinates around the X axis by 'angle'.
#         This is the EAST-WEST axis. 
#         Y represents position on NORTH-SOUTH axis. (?) 
#         Z represents position on NADIR-ZENITH axis. (?) 
#         - Function not used (Apr.2021), but retained for development of alternative camera mounts. """
#     try:
#         hyp = math.sqrt(y * y + z * z)
#         OrigAngle = math.degrees(math.atan2(z,y))
#         NewAngle = OrigAngle + angle
#         NewY = math.cos(math.radians(NewAngle)) * hyp
#         NewZ = math.sin(math.radians(NewAngle)) * hyp
#     except Exception as e:
#         MainLog.RaiseException(e,comment='RotateYZ') # Trap all the exception information in the main log file.
#     return NewY, NewZ

# ------------------------------------------------------------------------------------------------------

# def FitPolynomial(xlist,ylist): # 0 references.
#     """ Use numpy to find a best fit polynomial function for a series of values. 
#         Used in estimating lens distortion.
#         The 'z' object returned can be used directly by numpy to evaluate new values of 'x'. """
#     x = np.array(xlist) # Convert 'X' values into a numpy array.
#     y = np.array(ylist) # Convert 'Y' values into a numpy array.
#     if len(xlist) != len(ylist): # Lists do not agree.
#         MainLog.Log('FitPolynomial: Lists must be the same length :',len(xlist),'vs',len(ylist),level='error')
#         return None
#     if len(xlist) < 5: # Lists are not long enough.
#         MainLog.Log('FitPolynomial: Lists need at least 5 entries :',len(xlist),'elements',level='error')
#         return None
#     z = np.polyfit(x, y, 3) # Numpy will calculate a reasonable fit polynomial for the lists.
#     # eg: z = array([ 0.00001, -1.123123,  4.345354, 1.231123])
#     #                 * x**3   * x**2      * x       constant
#     return z

# ------------------------------------------------------------------------------------------------------

# def EvaluatePolynomial(xvalue,zmodel): # 0 references.
#     """ Use numpy to estimate a 'y' value for any input 'xvalue' using the polynomial defined in zmodel.
#         Used in estimating lens distortion. """
#     p = np.poly1d(zmodel) # Define the polynomial function.
#     y = p(xvalue) # Evaluate the function for xvalue.
#     return y

# ------------------------------------------------------------------------------------------------------

def RelativeAltAz(StarAlt,StarAz,LookAtAlt,LookAtAz): # 35 references.
    """ Calculate the angles of a star relative to some look-at position. 
        There will be some wonderfully clever maths to do this cleanly, quickly and precisely.
        But this was developed with trial and error, and it works well enough for me and is modifiable as required. """
    PlotX, PlotY, PlotZ = AltAzToXYZ(StarAlt,StarAz) # Place star on celestial sphere (unit 1)
    
    # Swing round to LOOK-AT Azimuth.
    NewY = PlotY * math.cos(math.radians(-1 * LookAtAz)) - PlotX * math.sin(math.radians(-1 * LookAtAz)) # 0degrees is due north on Y axis. 90degrees is due east on X axis.
    NewX = PlotX * math.cos(math.radians(-1 * LookAtAz)) + PlotY * math.sin(math.radians(-1 * LookAtAz))
    PlotX = NewX
    PlotY = NewY
    
    # Drop down to LOOK-AT Altitude.
    NewY = PlotY * math.cos(math.radians(-1 * LookAtAlt)) - PlotZ * math.sin(math.radians(-1 * LookAtAlt)) # 0degrees is due north on Y axis. 90degrees is straight up on Z axis.
    NewZ = PlotZ * math.cos(math.radians(-1 * LookAtAlt)) + PlotY * math.sin(math.radians(-1 * LookAtAlt))
    PlotY = NewY
    PlotZ = NewZ
    
    PlotStarAlt, PlotStarAz = XYZToAltAz(PlotX,PlotY,PlotZ) # Convert from an x,y,z location back into Alt/Az combination.
    # Clip result to +/- 180Degrees because we're relative to the 'centre' of the map we're drawing.
    PlotStarAz = PlotStarAz % 360
    if PlotStarAz > 180: PlotStarAz -= 360
    PlotStarAlt = PlotStarAlt % 360
    if PlotStarAlt > 180: PlotStarAlt -= 360
    return PlotStarAlt, PlotStarAz
    
# ------------------------------------------------------------------------------------------------------

def ConvertArcsecondsToPixels(arcseconds):
    """ Convert an arcsecond value into a pixel count. 
        Used for calculating the size of objects in an image. """
    return arcseconds * CameraInUse.PixelsPerFovDegreeWidth / 3600
    
# ------------------------------------------------------------------------------------------------------

#def PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=False): # 18 references.
def PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width): # 18 references.
    """ Given a relative altitude and azimuth, return the X,Y co-ordinates on the image of dimensions (height*width) 
        PlotStarAlt = +/- degrees from the centre of the image. 
        PlotStarAz = +/- degrees from the centre of the image.
        height = pixel height of the image.
        width = pixel width of the image.
        applydistortion = Position will be modified to simulate lens distortion. """
    # Convert relative AltAz to a location on an image.
    try:
        TempStarX = int((width/2) + (PlotStarAz * CameraInUse.PixelsPerFovDegreeWidth)) # Raw position
        TempStarY = int((height/2) - (PlotStarAlt * CameraInUse.PixelsPerFovDegreeHeight)) # SUBTRACT rather than ADD because Y axis in image counts down from the top, whereas ALTITUDE counts up from the bottom.
    except Exception as e:
        MainLog.RaiseException(e,comment='PlotRelativeAltAz') # Trap all the exception information in the main log file.
    return TempStarX,TempStarY

# ///////////////////////////////////////////////////////////////////////////////////
# Utility functions.
# ///////////////////////////////////////////////////////////////////////////////////

# Special characters.
# The terminal will need to be UTF-8 too. If not, these will look corrupted.
Symbol = {'degree' : '\u00B0', 'left' : '\u2190', 'right' : '\u2192', 'up' : '\u2191', 'down' : '\u2193', 'delta' : '\u0394', 'sun' : '\u2609', 'moon' : '\u263D', 'mercury' : '\u263F',
'venus' : '\u2640', 'earth' : '\u2641', 'mars' : '\u2642', 'jupiter' : '\u2643', 'saturn' : '\u2644', 'uranus' : '\u2645', 'neptune' : '\u2646', 'pluto' : '\u2647', 'ceres' : '\u26B3', 
'pallas' : '\u26B4', 'juno' : '\u26B5', 'vesta' : '\u26B6', 'astraea' : '\u2BD9', 'flora' : '\u2698', 'hygiea' : '\u2695', 'chiron' : '\u26B7', 'pholus' : '\u2BDB', 'aries' : '\u2648',
'taurus' : '\u2649', 'gemini' : '\u264A', 'cancer' : '\u264B', 'leo' : '\u264C', 'virgo' : '\u264D', 'libra' : '\u264E', 'scorpio' : '\u264F', 'sagittarius' : '\u2650', 'capricorn' : '\u2651',
'aquarius' : '\u2652', 'pisces' : '\u2653', 'ophiuchus' : '\u26CE', 'comet' : '\u2604', 'star' : '\u2736', 'camera' : '\u00A9', 'target' : 'T', 'iss' : 'H', 'css' : '#'}
DegreeSymbol = Symbol['degree'] # For typing speed, it's used a lot.
print (textcolor.yellow("Python3 is UTF-8 compliant, make sure that the terminal is in UTF-8 mode too."))

def ShowSymbolList():
    """ List the preset symbols. """
    print(textcolor.yellow("Symbol list"))
    for key,value in Symbol.items():
        print(key.ljust(15) + textcolor.cyan(value))
        
# ------------------------------------------------------------------------------------------------------

def AzAltText(az,alt,symbol=None) -> str: # 15 references.
    """ Return standardised string of Altitude and Azimuth coordinates. """
    if symbol == None: symbol = DegreeSymbol
    return "az: " + str(round(az,3)) + symbol + " alt: " + str(round(alt,3)) + symbol

# ------------------------------------------------------------------------------------------------------


def GetTerminalSize(): # 3 references.
    """ Return tuple of the current screen dimensions. (cols,rows) 
        This is used to dynamically build the ObservationRun display. 
        More information can be shown if the screen is large enough,
        but the system still works on a relatively small display space. """
    return textcolor.terminalsize() # returns (cols,rows)

# ------------------------------------------------------------------------------------------------------

class cpumonitor(): # 1 references.
    """ Simple class to monitor the CPU load of the RPi.
        This periodically polls the CPU load and establishes some metrics. """

    def __init__(self):
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
        MainLog.Log("cpumonitor.LogCpuInfo:",terminal=False)
        cCmd = 'cat /proc/cpuinfo'
        listlines = osCmd(cCmd)
        for line in listlines: MainLog.Log(line,terminal=False)

    def GetCpuTemp(self):
        """ Return the CPU temperature. """
        MainLog.Log("cpumonitor.GetCpuTemp:",terminal=False)
        cput = CPUTemperature()
        self.CpuTemp = cput.temperature
        return self.CpuTemp

    def LogCpuTemp(self):
        """ Record CPU temperature in main log file. """
        MainLog.Log("cpumonitor.LogCpuTemp: Temperature",self.GetCpuTemp(),terminal=False)

    def Poll(self,force = False):
        """ Check if it is time to retrieve updated statistics from the CPU. """
        if force or self.Timer.Due(): # Time to update the CPU figures.
            result = osCmd(self.Command) # Check /proc/stat for CPU figures.
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

CpuMonitor = cpumonitor() # Create new CPU monitor.
CpuMonitor.LogCpuInfo() # Note details about the CPU.

# ------------------------------------------------------------------------------------------------------

class memorymonitor(): # 1 references.
    """ Simple class to monitor the memory load of the RPi. """

    def __init__(self):
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
            lines = osCmd(self.Command)  # osCmd function dedicated to the MAIN thread.
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

MemoryMonitor = memorymonitor() # Create new memory monitor.
MainLog.Log("Memory available",MemoryMonitor.MemoryTotal,terminal=False)

# ------------------------------------------------------------------------------------------------------

class discmonitor(): # 2 references.
    """ Class to monitor the storage capacity of the RPi.
        Basic operation monitors the 'root' disc of the system (memory card).
        But can also monitor other mounted disks, such as usb memory sticks.
        - Will attempt to mount them using the default Raspbian desktop auto-mounting behaviour if needed. """

    def __init__(self,name='root',devname='/dev/root',path='/',disctype='boot'):
        self.Name = name # A label to refer to this instance.
        self.DevName = devname # The storage mapping device name as seen by the operating system. /dev/root for example.
        self.DiscType = disctype # 'boot' or 'usb'. 'usb' triggers some extra processing to check it is mounted and available.
        self.Timer = timer(60) # Set timer for 60 seconds.
        self.DiscFree = 0 # Bytes free.
        self.LowDiscMB = 500 # Megabytes min disc free.
        self.Path = path # This is the path without any device label (ie /media/pi  or   /   )
        self.DfPath = path # This is the path including the device label (ie /media/pi/USBMEMORY   )
        # USB storage details.
        self.USBLabel = None # Label of the device when it was formatted. Something like 'USBMEMORY'. Will appear in DfPath and is part of drive mapping.
        self.USBUUID = None # Unique ID
        self.USBTYPE = None # file system type. FAT/FAT32.
        self.USBPARTUUID = None # Unique ID
        self.DriveAvailable = True # True if available (eg root or USB is mounted), else False.
        if self.DiscType in ['usb']: # USB devices may need mounting. Check 'em out!
            self.FindUSB(devname=self.DevName) # Check if USB memory stick is available.
        self.Poll(force=True) # Kickstart the values.
        MainLog.Log("discmonitor: Available storage on:",self.Name, self.DevName, self.Path, self.DiscFree,'bytes',terminal=False)
        
    def GetDfDictionary(self):
        """ Return df information as a dictionary. """
        dictionary = {}
        #    $ df -h
        #    $ df -h [mountpath]
        #    Filesystem      Size  Used Avail Use% Mounted on
        #    /dev/root        29G  7.5G   21G  27% /
        #    devtmpfs        750M     0  750M   0% /dev
        #    tmpfs           911M     0  911M   0% /dev/shm
        #    tmpfs           911M  8.6M  902M   1% /run
        #    tmpfs           5.0M  4.0K  5.0M   1% /run/lock
        #    tmpfs           911M     0  911M   0% /sys/fs/cgroup
        #    /dev/mmcblk0p1  253M   49M  204M  20% /boot
        #    tmpfs           183M     0  183M   0% /run/user/1000
        #    /dev/sda1       ***G   **G   **G  *** /media/pi/USBMEMORY
        convlist = [['K',1024],['M',1024**2],['G',1024**3],['T',1024**4],["%",1]] # Conversions from 'human readable' forms back to float/integers.
        cCmd = 'df -h' # Use the df command in human readable format.
        lines = osCmd(cCmd) # Execute command and gather result.
        fieldnames = None # This will be a list of the column headers from the first line of the 'df' command output.
        for i,line in enumerate(lines): # Read the output lines one at a time.
            lineitems = line.strip().split() # Split into individual fields.
            if len(lineitems) > 0: # Poll through the devices.
                if i == 0: # 1st line is just field names.
                    fieldnames = lineitems
                else: # Other lines contain data.
                    for j in range(1,5): # Poll through the columns.
                        v = lineitems[j] # Get raw column value.
                        for ji in convlist: # Convert from HumanReadable into absolute value. Check all conversions.
                            if ji[0] in v: # This HR value can be converted.
                                v = int(float(v[:-1]) * ji[1]) # Convert from HR text value into absolute value.
                                break # No need to convert further.
                        lineitems[j] = v # Store back in the line.
                    dictentry = {} # Create an entry for this particular drive mount.
                    for j,v in enumerate(lineitems): # Pull each field and convert into dictionary entry.
                        dictentry[fieldnames[j]] = lineitems[j]
                    dictionary[lineitems[-1]] = dictentry # Append this entry to the dictionary of all mount points.
        return dictionary 
        
    def Poll(self,force = False):
        """ Decide if it is time to update the storage statistics. """
        if force or self.Timer.Due():
            dfdict = self.GetDfDictionary()
            if self.DriveAvailable: # Drive is available, so report the space left.
                self.DiscFree = dfdict[self.DfPath]['Avail']
            else:
                self.DiscFree = 0 # Drive isn't available, so no space.
            
    def FreeBytes(self,force = False) -> int:
        """ Return the amount of memory left free. """
        self.Poll(force=force) # Make sure that the figures are the very latest.
        return self.DiscFree
        
    def FreeMegaBytes(self,force=False) -> int:
        """ Return the amount of memory left free in megabytes. """
        return self.FreeBytes(force=force) / (1024 ** 2)
        
    def DiscOK(self, force = False) -> bool:
        """ Check that there is at least 500megabytes of storage available. """
        megabytes = self.FreeMegaBytes(force=force)
        if megabytes < self.LowDiscMB: return False
        else: return True
        
    def FindUSB(self,devname='/dev/sda1'):
        """ Return True if a USB memory stick exists. """
        # /dev/usb1 might mount automatically if desktop is running, but it doesn't happen when running headlessly.
        #           Does pcmanfm process help?
        #           Website suggests udisksctl mount -b /dev/sda1                  will create /media/pi folder on the USB memory stick.
        result = False # Assume there's no USB memory available at first.
        MainLog.Log("discmonitor.FindUSB: Checking if",devname,"is recognised",terminal=False)
        validdevnames = ['/dev/sda1']
        if devname in validdevnames: # Safety check. Don't run commands with values we don't trust.
            cCmd = 'sudo blkid ' + devname
            lines = osCmd(cCmd) # Run the command and gather the results.
            # Example output:    /dev/sda1: LABEL="USBMEMORY" UUID="B267-53C5" TYPE="vfat" PARTUUID="c3072e18-01"
            for line in lines: # Run through each result line in turn.
                if len(line) == 0: continue # Ignore blanks.
                items = line.strip().split(" ") # Clean and separate out the line elements.
                if items[0][:-1] == devname: # Found the USB memory stick. Extract details. (Ignore trailing ':' character)
                    self.USBLabel = items[1].split("=")[1].replace('"','') # Volume label - Will be the folder name under /media/pi/{USBLabel}
                    self.USBUUID = items[2].split("=")[1].replace('"','') # Unique ID of the memory stick.
                    self.USBFSType = items[3].split("=")[1].replace('"','') # File system type - vfat / vfat32 etc.
                    self.USBPartUUID = items[4].split("=")[1].replace('"','') # Universal identifier.
                    MainLog.Log("discmonitor.FindUSB: Device:",devname,"Label:",self.USBLabel,"UUID:",self.USBUUID,"FS Type:",self.USBFSType,"PARTUUID:",self.USBPartUUID,terminal=False)
                    result = True # We're happy so far.
        else: # The device value was not valid. Tell the user.
            MainLog.Log("discmonitor.FindUSB: '",devname,"' is invalid. Must be in",str(validdevnames),level='error',terminal=True)
        if result: # Previous steps succeeded.
            MainLog.Log("discmonitor.FindUSB: ",devname,"is recognised as",self.USBLabel,".",terminal=False)
        else: # Previous steps failed.
            MainLog.Log("discmonitor.FindUSB: ",devname,"is NOT recognised.",terminal=True)
        
        if result: # OK so far.
            self.DfPath = self.Path + "/" + self.USBLabel # The path to the mapped drive as it will appear in 'df' command output and in directory structures later on.
            MainLog.Log("discmonitor.FindUSB: Checking if",devname,"is mounted as",self.DfPath,terminal=False)
            if os.path.exists(self.DfPath): # The directory exists.
                MainLog.Log("discmonitor.FindUSB:",self.DfPath,"exists.",terminal=False)
            else: # The directory does not exist. The drive is recognised by the system, but not mounted. Try to mount it now.
                MainLog.Log("discmonitor.FindUSB:",self.DfPath,"does not exist. Will attempt to mount.",terminal=True)
                # Warn the user that the 'pi' user password will be required. The udisksctl utility requires it in order to mount the disc.
                print(textcolor.yellow('Mounting ' + self.USBLabel + ' under ' + self.Path))
                print(textcolor.yellow('You will be prompted for the "pi" user password as part of the mount process.'))
                print(textcolor.yellow('If you do not give the correct password the USB storage will not be mounted.'))
                cCmd = 'udisksctl mount -b ' + devname # Construct the mount command.
                print(textcolor.yellow('Executing: ' + cCmd)) # Show the user exactly what's being executed.
                temp = osCmdCode(cCmd) # Check return code.
                if temp == 0: # Return code '0' means success.
                    print('Thank you.')
                    MainLog.Log("discmonitor.FindUSB: Mount",devname,"as",self.DfPath,'success.',terminal=False)
                else: # Any other return code value means a problem.
                    result = False # Failed.
                    MainLog.Log("discmonitor.FindUSB: Mount",devname,"as",self.DfPath,'failed.',level='error',terminal=True)
        if result: # OK so far.
            dictionary = self.GetDfDictionary() # Get the 'df' results from the operating system.
            if self.DfPath in dictionary: # We found it now in the list of mount points.
                MainLog.Log("discmonitor.FindUSB: Check",devname,"as",self.DfPath,'found.',terminal=False)
            else: # We still can't find it. Something failed.
                MainLog.Log("discmonitor.FindUSB: Check",devname,"as",self.DfPath,'not found.',terminal=True)
                result = False # Failed.
        self.DriveAvailable = result
        MainLog.Log("discmonitor: FindUSB: DriveAvailable",self.DriveAvailable,terminal=False)
        return result

SDCardMonitor = discmonitor(name='root',devname='/dev/root',path='/',disctype='boot') # Create new disc space monitor for the SD card.
USBDiscMonitor = discmonitor(name='usb',devname='/dev/sda1',path='/media/pi',disctype='usb') # Create USB memory card monitor (if it exists).
# Decide which of the two above monitors will be the one that images are stored in. Create a pointer to that one for the status monitoring later on.
if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable: 
    ImageStorageMonitor = USBDiscMonitor # Point to USB storage when checking available space.
else: 
    ImageStorageMonitor = SDCardMonitor # Point to the SD card storage when checking available space.

# ------------------------------------------------------------------------------------------------------

def IsFloat(text) -> bool: # 3 references.
    """ Return TRUE if a string can be converted to a float value. """
    try:
        #temp = float(text)
        _ = float(text)
        return True
    except ValueError:
        return False

# ------------------------------------------------------------------------------------------------------

def IsInt(text) -> bool: # 3 references.
    """ Return TRUE if a string can be converted to an integer value. """
    try:
        #temp = int(text)
        _ = int(text)
        return True
    except ValueError:
        return False

# ------------------------------------------------------------------------------------------------------

def TextToInt(text) -> int: # 10 references.
    """ Convert a character string into an INTEGER value.
        Returns None if it can't be done. """
    try:
        a = int(text)
    except ValueError:
        a = None
    return a

# ------------------------------------------------------------------------------------------------------

def TextToFloat(text) -> float: # 11 references.
    """ Convert a character string into a FLOAT value.
        Returns None if it can't be done. """
    try:
        a = float(text)
    except ValueError:
        a = None
    return a

# ------------------------------------------------------------------------------------------------------

# There are online resources to forecast the 'seeing' conditions for astronomy. This forecasts things like the wind, temperature, cloud 
# and the atmospheric turbulence that can degrade the quality of an image. Turbulance will blur a star out for example.
# The metcheck.com service provides a 3hourly forecast. Define a class which can read this over the internet and output some 
# human readable explanation of the forecast. This can be saved in the observation notes (DocumentSession function) and displayed
# in the ObservationRun display if there is enough space.
class metcheck_handler(attributemaster): # 1 references.
    """ Load and maintain Astronomical Seeing conditions from www.metcheck.com 
        Other sources are probably available, this demonstrates what is possible. """
    
    def __init__(self):
        # Available products are 'As' (astro), 'No' (normal) and others...
        self.SourceTitle = 'Metcheck.com'
        self.WebServiceOK = False # Indicates that last web service call was successful. 
        self.AstroURL = 'http://ws1.metcheck.com/ENGINE/v9_0/json.asp?lat={lat}&lon={lon}&Fc=As' # Template for request URL.
        self.AstroURL = self.AstroURL.format(lon=Parameters.HomeLonVal,lat=Parameters.HomeLatVal) # Insert the current location into the request.
        self.AstroResult = {} # Empty result dictionary. 
        self.CivilURL = 'http://ws1.metcheck.com/ENGINE/v9_0/json.asp?lat={lat}&lon={lon}&Fc=No' # Template for request URL.
        self.CivilURL = self.CivilURL.format(lon=Parameters.HomeLonVal,lat=Parameters.HomeLatVal) # Insert the current location into the request.
        self.CivilResult = {} # Empty result dictionary. 
        self.Log = MainLog.Log # Decide which log file this class uses.
        self.AstroCacheFilename = ProjectRoot + '/data/astrocache.json' # Store latest data on disc, good for debug/development and reduces calls to web service.
        self.CivilCacheFilename = ProjectRoot + '/data/civilcache.json'
        self.Timer = timer(3600) # Set refresh timer for every 60 minutes (=3600 seconds).
        self.ForecastMatrix = None # Will contain a matrix of all the forecast data when populated. Easy to access ALL times for an individual measure.
        self.TransposedMatrix = None # Will contain a transposed matrix of the forecast data. Easy to access ALL measures for an individual time.
        self.MatrixKeys = None # Will contain a list of the data values in the DataMatrix.
        self.MatrixDates = None # Will contain a list of the timestamp values in the DataMatrix.
        self.Refresh() # Try to update the information immediately.
        # Define a standard range of colours which can be applied to all the 'percentage' measurement values.
        percentage_low_good = {-100000: textcolor.GREEN, 25: textcolor.LIGHTGREEN, 50: textcolor.YELLOW, 75: textcolor.ORANGE1, 90: textcolor.RED}
        # Consolidated color and translation tables for both ASTRO and CIVIL measurements.
        # Colors dictionary contains an entry per 'measure'.
        # The entry can provide
        # - '{value}' = Display color associated with a specific value.
        # - {value} = Display color associated with values >= {value} (This allows colors to be assigned to ranges of values rather than specific values).
        self.MeasureColours = {
            'seeingIndex': {'0': textcolor.RED, '1': textcolor.RED, '2': textcolor.ORANGE1, 
                            '3': textcolor.ORANGE1, '4': textcolor.ORANGE1, '5': textcolor.YELLOW, 
                            '6': textcolor.YELLOW, '7': textcolor.LIGHTGREEN, '8': textcolor.LIGHTGREEN, 
                            '9': textcolor.GREEN, '10': textcolor.GREEN},
            'pickeringIndex': {'0': textcolor.RED, '1': textcolor.RED, '2': textcolor.ORANGE1, 
                               '3': textcolor.ORANGE1, '4': textcolor.ORANGE1, '5': textcolor.ORANGE1, 
                               '6': textcolor.YELLOW, '7': textcolor.YELLOW, '8': textcolor.LIGHTGREEN, 
                               '9': textcolor.LIGHTGREEN, '10': textcolor.LIGHTGREEN, '11': textcolor.LIGHTGREEN, 
                               '12': textcolor.GREEN},
            'temperature': {-100: textcolor.PURPLE, -30: textcolor.MAGENTA, -20: textcolor.BLUE, 
                            -10: textcolor.CYAN, 0: textcolor.GREEN, 15: textcolor.LIGHTGREEN, 
                            20: textcolor.YELLOW, 25: textcolor.ORANGE1, 30: textcolor.RED},
            'lowcloud': percentage_low_good,
            'medcloud': percentage_low_good,
            'highcloud': percentage_low_good,
            'totalcloud': percentage_low_good,
            'humidity': percentage_low_good,
            'dayOrNight': {'D': textcolor.RED, 'N': textcolor.GREEN},
            'windspeed': {0: textcolor.GREEN, 10: textcolor.LIGHTGREEN, 15: textcolor.YELLOW, 
                          20: textcolor.ORANGE1, 25: textcolor.RED},
            'windgustspeed': {0: textcolor.GREEN, 10: textcolor.LIGHTGREEN, 20: textcolor.YELLOW, 
                              30: textcolor.ORANGE1, 40: textcolor.RED},
            'chanceofrain': percentage_low_good,
            'chanceofsnow': percentage_low_good
            }
        # Translation dictionary contains an entry per 'measure'.
        # The entry can provide
        # - 'desc' = Description of the measure.
        # - '{value}' = Translation of specific values.
        # - 'pattern' = Formatting pattern for the value (use it to add UOM for example).
        # - 'fieldnames' = List of textcolor.colordisplay fieldnames that can be auto-populated by the UpdateWindow() class.
        self.MeasureTranslation = {
            "seeingIndex": {'desc': 'Seeing index', 
                            '0':'Worst', '1':'Terrible', '2':'Bad', '3':'Bad', 
                            '2-3':'Bad', '4':'Poor', '5':'Poor', '6':'Poor', 
                            '4-6':'Poor', '7':'Fair', '8':'Fair', '7-8':'Fair', 
                            '9':'Excellent', '10':'Excellent', '9-10':'Excellent', 'pattern': None, 'fieldnames': ['SI']},
            "pickeringIndex": {'desc': 'Pickering seeing', 
                               '0':'Worst', '1':'Terrible', '2':'Bad', '3':'Bad', 
                               '4':'Poor', '5':'Poor', '6':'Poor', '7':'Poor', 
                               '8':'Fair','9':'Good', '10':'Good', '11':'Excellent', 
                               '12':'Excellent', 'pattern': None, 'fieldnames': ['PI']},
            "temperature": {'desc': 'Temp', 'pattern': '{0}C', 'fieldnames': ['TE']},
            "dewpoint": {'desc': 'Dewpoint', 'pattern': '{0}C', 'fieldnames': ['DP']},
            "rain": {'desc': 'Rain', 'pattern': '{0}mm', 'fieldnames': ['RD']},
            "freezinglevel": {'desc': 'Freezing level', 'pattern': '{0}m', 'fieldnames': ['FL']},
            "totalcloud": {'desc': 'Cloud: Total cover', 'pattern': '{0}%', 'fieldnames': ['CT']},
            "lowcloud": {'desc': 'Cloud: Low cover', 'pattern': '{0}%', 'fieldnames': ['CL']},
            "medcloud": {'desc': 'Cloud: Medium cover', 'pattern': '{0}%', 'fieldnames': ['CM']},
            "highcloud": {'desc': 'Cloud: High cover', 'pattern': '{0}%', 'fieldnames': ['CH']},
            "humidity": {'desc': 'Humidity', 'pattern': '{0}%', 'fieldnames': ['HU']},
            "windspeed": {'desc': 'Windspeed (mph)', 'pattern': '{0}mph', 'fieldnames': ['WS']},
            "meansealevelpressure": {'desc': 'Pressure (hPa)', 'pattern': '{0}hPa', 'fieldnames': ['PR']},
            "windgustspeed": {'desc': 'Wind gusts (mph)', 'pattern': '{0}mph', 'fieldnames': ['WG']},
            "winddirection": {'desc': 'Wind angle', 'pattern': '{0}deg', 'fieldnames': ['WA']},
            "chanceofrain": {'desc': 'Rain chance', 'pattern': '{0}%', 'fieldnames': ['RC','RPB']},
            "chanceofsnow": {'desc': 'Snow chance', 'pattern': '{0}%', 'fieldnames': ['SC','SPB']}
            }
        
        try:
            self.TwelveHourForecast() # Show immediate forecast.
        except Exception as e:
            MainLog.ReportException(e,comment='seeingmetcheck: init: TwelveHourForecast')
        try:
            self.GetFogData() # Check for fog conditions.
        except Exception as e:
            MainLog.ReportException(e,comment='seeingmetcheck: init: GetFogData')

    def SelectForecast(self,dictionary):
        """ From a list of forecasts, return the current entry. """
        try:
            allentries = dictionary['metcheckData']['forecastLocation']['forecast'] # Pull the list of forecasts.
        except Exception as e:
            allentries = []
            self.Log("metcheck_handler.SelectForecast(): Failed with", str(e),level='warning',terminal=False)
        result = {}
        if len(allentries) > 0:
            for i in range(len(allentries)): # Poll through each entry in the dataseries.
                dataset = allentries[i] # Select individual item.
                timepoint = datetime.fromisoformat(dataset['utcTime'].split('.')[0] + '+00:00') # 2021-11-25T18:00:32.00 Calculate the actual timestamp for this individual dataset. 
                dataset['timestamp'] = timepoint # What timeslot are we using?
                if timepoint <= NowUTC(): # We're looking for the most recent entry, but ignore anything in the future.        
                    result = dataset
                else:
                    break # We're into the future. So stop looking.
        else: self.Log("metcheck_handler.SelectForecast(): No forecast entries to process. Is the web service OK?",terminal=False)
        return result

    def CurrentMeasures(self):
        """ Return dictionary of fieldname, value, colour for transferring to a colordisplay() window. 
            value is the formatted value, it applies any pattern defined in the MeasureTranslation dictionary. 
            fg = any foreground color to use. (None if nothing specified).
            bg = any background color to use. (None if nothing specified). """
        # *Q* This seems to return some duplicate entries. Check and correct.
        returndict = {} # The resulting dictionary will be stored here. 
        astroresult = self.SelectForecast(self.AstroResult) # Get the most current forecast from the list provided.
        civilresult = self.SelectForecast(self.CivilResult) # Get the most current forecast from the list provided.
        fulldict = {**astroresult, **civilresult} # Merged dictionary of the different weather datasets.
        for key,value in fulldict.items(): # Process the KEY and VALUE pairs for the weather forecast source data.
            dkey = str(key) # Ensure key is a string.
            transvalue = self.MeasureTranslation.get(dkey,{}) # Get the translation entry for the key if it exists.
            # deltavalue = ''
            if 'fieldnames' in transvalue: # The translation dictionary provides a fieldname for the colordisplay() instance.
                fieldnames = transvalue['fieldnames'] # Get LIST of fieldnames.
                pattern = transvalue.get('pattern',"") # This pattern will format the value in the display.
                desc = transvalue.get(value,"") # If the value has a translation, get it here.
                if pattern != None and len(pattern) > 0: # The pattern is valid.
                    dval = str(pattern).format(value) # Format the display string for the value.
                else: # No valid pattern, so present the value as is.
                    dval = str(value)
                for fieldname in fieldnames:
                    fg = self.SelectColor(key, value) # If the color rules exist for the weather value, set the foreground color appropriately.
                    if fg != None: bg = textcolor.BLACK # Foreground color is set to black if a background color exists.
                    else: bg = None # Foreground color will not be changed if background does not change.
                    returndict[fieldname] = {'value': dval, 'fg': fg, 'bg': bg, 'title': dkey, 'desc': desc} # Create new entry for the defined window field.
        return returndict

    def CurrentTemperature(self):
        """ Return the current temperature. """
        dictionary = self.SelectForecast(self.CivilResult) # Get the current values.
        self.Log("metcheck_handler.CurrentTemperature: (",dictionary,")",terminal=False)
        result = dictionary['temperature'] # Get the temperature.
        self.Log("metcheck_handler.CurrentTemperature: (",result,") Called but not yet implemented.",terminal=False)
        return result

    def GetFogData(self):
        """ Return the current fog data as a dictionary. """
        dictionary = self.SelectForecast(self.CivilResult) # Get the current values.
        self.Log("metcheck_handler.GetFogData: Basis:",dictionary,terminal=False)
        result = {}
        fieldlist = ['temperature','dewpoint','humidity','windspeed']
        for i in fieldlist:
            result[i] = dictionary[i]
        dpd = float(result['temperature']) - float(result['dewpoint']) # How close is temperature to dewpoint?
        result['dewpointdelta'] = dpd
        fogscore = 0
        if dpd >= 0 and dpd <= 3: # Fog can form within 2.5Degrees of dewpoint.
            result['dewpointstatus'] = 'HIGH ' + str(dpd) + DegreeSymbol
            fogscore += 1
        else:
            result['dewpointstatus'] = 'LOW'
        ws = float(result['windspeed'])
        if ws < 10: # Calm.
            result['windspeedstatus'] = 'HIGH ' + str(ws) + 'mph'
            fogscore += 1
        else:
            result['windspeedstatus'] = 'LOW'
        hm = float(result['humidity'])
        if hm >= 85: # Humid
            result['humiditystatus'] = 'HIGH ' + str(hm) + '%'
            fogscore += 1
        else:
            result['humiditystatus'] = 'LOW'
        result['fogscore'] = fogscore
        result['fogrisk'] = str(fogscore) + '/3'
        timepoint = datetime.fromisoformat(dictionary['utcTime'].split('.')[0] + '+00:00') # 2021-11-25T18:00:32.00 Calculate the actual timestamp for this individual dataset. 
        result['timestamp'] = timepoint # What timeslot are we using?
        
        self.Log("metcheck_handler.GetFogData: Result:",result,terminal=False)
        return result

    def UpdateWindow(self,windowhandle,notes=''):
        """ Update the fields in a colordisplay window.
            The windowhandle instance must have FieldValue() and FieldColor() methods implemented.
            - for example textcolor library's colordisplay() class.  """
        self.Refresh() # Update from the web if needed.
        dictionary = self.CurrentMeasures() # Get the current values, formatting and color coding is calculated here too, no need to do it again.
        for key, details in dictionary.items(): # Go through each field in turn.
            windowhandle.FieldValue(key,details['value']) # Update any field with the dictionary defined values.
            if details['bg'] != None: # Only change display colour if there's reason.
                windowhandle.FieldColor(key,details['fg'],details['bg'])
            # Also handle some exceptions that need specific processing.
            if key == 'SI': # Update SeeingIndex description too.
                windowhandle.FieldValue('SID',details['desc'])
                # Copy color from SI to SID field too.
                windowhandle.CopyFieldColor('SI','SID')
            if key == 'PI': # Update PickeringIndex description too.
                windowhandle.FieldValue('PID',details['desc'])
                windowhandle.CopyFieldColor('PI','PID')
            if key == 'WA': # Convert wind angle into compass point.
                windowhandle.FieldValue('WC',CompassPoint(int(details['value'].replace('deg',''))))
        return True

    def GetMeasure(self,measurename):
        """ Return a measure from the downloaded data. 
            eg: GetMeasure('winddirection'). 
            Always returns a string representation of the measure. """
        self.Refresh() # Update from the web if needed.
        dictionary = self.CurrentMeasures() # Get the values.
        result = ''
        #for key, details in dictionary.items(): # Find the measure.
        for _, details in dictionary.items(): # Find the measure.
            if details['title'] == measurename:
                result = str(details['value'])
                break
        return result

    def SelectColor(self,key,value):
        # Colour the translation.
        sel_color = None # No colour selected.
        # dkey = str(key) # Default KEY and VALUE strings.
        dval = str(value)
        dfloat = TextToFloat(dval) # Convert to a float too if possible. # Easier to find 'nearest match' in incomplete lists.
        if key in self.MeasureColours: # The KEY can be coloured.
            if value in self.MeasureColours[key]: # Exact match, value can be coloured.
                sel_color = self.MeasureColours[key][value] # Note the colour selected.
            elif dfloat != None: # No precise match, try range match.
                for ckey, cval in self.MeasureColours[key].items(): # Try the range of colours in the dictionary looking for nearest lowest match.
                    cFloat = TextToFloat(ckey) # Convert values to float for numeric comparison.
                    if cFloat != None and cFloat <= dfloat: # Use the closest colour <= the value.
                        sel_color = cval # Note the colour selected.
        return sel_color

    def FormatValue(self,key,value):
        # Format the value, adding UOM etc.
        dkey = str(key) # Ensure key is a string.
        dval = str(value) # Default value string.
        transvalue = self.MeasureTranslation.get(dkey,{}) # Get the translation entry for the key if it exists.
        pattern = transvalue.get('pattern',None) # This pattern will format the value in the display.
        if pattern != None and len(pattern) > 0: # The pattern is valid.
            dval = str(pattern).format(value) # Format the display string for the value.
        return dval

    def FormatAndColor(self,key,value,bg=0,invert=False,length=None):
        """ Format a value and color it. """
        color = self.SelectColor(key,value)
        formatted = self.FormatValue(key,value)
        if length != None: formatted = formatted.ljust(length)[:length]
        if invert: result = textcolor.fgbgcolor(bg,color,formatted)
        else: result = textcolor.fgbgcolor(color,bg,formatted)
        return result

    def Refresh(self):
        """ Use the 'requests' module to request the forecast from www.metcheck.com.
            The result is returned as a JSON object, and stored as a Python dictionary.
            This requests the ASTRO and CIVIL forecasts. There is useful info in both. """
        r = False # We won't download fresh data unless there's a good reason for it.
        if self.Timer.Due(): r = True # OK to refresh.
        if self.AstroResult == {}: r = True # OK to refresh.
        if self.CivilResult == {}: r = True # OK to refresh.
        if Parameters.UseWeatherService != True: 
            r = False # NOT OK to refresh.
            self.Log("metcheck_handler.Refresh(): Parameters.UseWeatherService is False. Not polling remote weather service.",terminal=False)
        if r: # We should refresh.
            # Can we use the caches?
            self.LoadCaches() # If the disc cache of the data exist and is recent enough, this will load from disc instead of web service.
            if self.AstroResult != {}:
                self.Log("metcheck_handler.Refresh(): Astro forecast taken from disc cache.",terminal=False)
            if self.CivilResult != {}:
                self.Log("metcheck_handler.Refresh(): Civil forecast taken from disc cache.",terminal=False)
            
            WSOK = True # WebService needs to be proven.
            if self.AstroResult == {}: # No cached data available.
                self.Log('metcheck_handler.Refresh: Start: Astro product.',terminal=False)
                try: # Trap and report errors, but don't allow the entire program to abort.
                    response = requests.get(self.AstroURL) # Try to retrieve the response from the remote server.
                    response.raise_for_status() # Check for errors in the request.
                    self.AstroResult = response.json() # Convert the response into a dictionary. 
                    #self.Log(str(self.AstroResult),terminal=False)
                    # Cache the response on disc to save web calls.
                    with open(self.AstroCacheFilename,'w') as f:
                        json.dump(self.AstroResult,f,indent=4,default=str)
                except HTTPError as e: # There was an HTTP error.
                    self.Log('metcheck_handler.Refresh Astro: HTTPError: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
                except Exception as e: # There was some other sort of error.
                    self.Log('metcheck_handler.Refresh Astro: Error: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
            else: self.Log('metcheck_handler.Refresh: Used cached Astro data.',terminal=False)
            
            if self.CivilResult == {}: # No cached data available.
                self.Log('metcheck_handler.Refresh: Start: Civil product.',terminal=False)
                try: # Trap and report errors, but don't allow the entire program to abort.
                    response = requests.get(self.CivilURL) # Try to retrieve the response from the remote server.
                    response.raise_for_status() # Check for errors in the request.
                    self.CivilResult = response.json() # Convert the response into a dictionary. 
                    #self.Log(str(self.CivilResult),terminal=False)
                    # Cache the response on disc to save web calls.
                    with open(self.CivilCacheFilename,'w') as f:
                        json.dump(self.CivilResult,f,indent=4,default=str)
                except HTTPError as e: # There was an HTTP error.
                    self.Log('metcheck_handler.Refresh Civil: HTTPError: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
                except Exception as e: # There was some other sort of error.
                    self.Log('metcheck_handler.Refresh Civil: Error: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
            else: self.Log('metcheck_handler.Refresh: Used cached Civil data.',terminal=False)
            # Write a copy of the data to disc for development / debugging.
            with open(ProjectRoot + '/data/AstroResult.json','w') as f:
                json.dump(self.AstroResult,f,indent=4,default=str) # Write astroresult to disc.
            with open(ProjectRoot + '/data/CivilResult.json','w') as f:
                json.dump(self.CivilResult,f,indent=4,default=str) # Write civilresult to disc.
            self.Log('metcheck_handler.Refresh: Done',terminal=False)
            self.WebServiceOK = WSOK
            self.ForecastTable() # Prepare matrix table of times and values.

    def LoadCache(self,filename):
        """ Load a single cache if available and recent enough. """
        result = {} # Return empty cache.
        if os.path.exists(filename):
            fa = FileAge(filename)
            self.Log("metcheck_handler.LoadCache:",filename,fa,"seconds old",terminal=False)
            if FileAge(filename) < 3600: # Only use the cache if less than an hour old.
                with open(filename,'r') as f:
                    self.Log("metcheck_handler.LoadCache: Loading Cache: " + filename,terminal=False)
                    result = json.load(f) # Overwrite the default parameter values with anything from file.
        else:
            self.Log("metcheck_handler.LoadCache:",filename,"cache does not exist.",terminal=False)
        return result
        
    def LoadCaches(self):
        """ If disc caches of data are available and recent enough, load them. """
        self.AstroResult = self.LoadCache(self.AstroCacheFilename)
        self.CivilResult = self.LoadCache(self.CivilCacheFilename)
        
    def ForecastTable(self):
        self.MatrixKeys = [] # List of data values available.
        self.MatrixDates = [] # List of timestamps available.
        
        if self.CivilResult == None or self.CivilResult == {}: # No data available.
            self.Log('metcheck_handler.ForecastTable: No self.CivilResult values available.',level='warning')
            return
        if self.AstroResult == None or self.AstroResult == {}: # No data available.
            self.Log('metcheck_handler.ForecastTable: No self.AstroResult values available.',level='warning')
            return

        # Identify all the DATES and MEASURES available in the forecasts.
        # Civil forecast.
        forecast = self.CivilResult['metcheckData']['forecastLocation']['forecast'] # An array of dictionaries.
        for dictionary in forecast:
            for key,value in dictionary.items():
                if not key in self.MatrixKeys: self.MatrixKeys.append(key)
                if key == 'utcTime':
                    if not value in self.MatrixDates: self.MatrixDates.append(value)
        # Astro forecast.
        forecast = self.AstroResult['metcheckData']['forecastLocation']['forecast'] # An array of dictionaries.
        for dictionary in forecast:
            for key,value in dictionary.items():
                if not key in self.MatrixKeys: self.MatrixKeys.append(key)
                if key == 'utcTime':
                    if not value in self.MatrixDates: self.MatrixDates.append(value)

        self.MatrixDates.sort() # Make sure dates are in ascending sequence.
        
        # Create empty matrices for the known dates and measures.
        self.ForecastMatrix = [[' ' for d in self.MatrixDates] for k in self.MatrixKeys] # Create matrix to hold all values vs dates. Gives all dates for any measure.
        self.TransposedMatrix = [[' ' for k in self.MatrixKeys] for d in self.MatrixDates] # Create matrix to hold all dates vs values (transposed). Gives all measures for any date.

        # Pull all the details ouf of the Civil forecast.
        forecast = self.CivilResult['metcheckData']['forecastLocation']['forecast'] # An array of dictionaries.
        for dictionary in forecast:
            if not dictionary['utcTime'] in self.MatrixDates: continue # Skip this entry.
            c = self.MatrixDates.index(dictionary['utcTime']) # Which column are we filling?
            for key,value in dictionary.items():
                if not key in self.MatrixKeys: continue # Skip this item.
                r = self.MatrixKeys.index(key) # Which row are we filling?
                self.ForecastMatrix[r][c] = value # Populate column.
        # Append all the details out of the Astro forecast.
        forecast = self.AstroResult['metcheckData']['forecastLocation']['forecast'] # An array of dictionaries.
        for dictionary in forecast:
            if not dictionary['utcTime'] in self.MatrixDates: continue # Skip this entry.
            c = self.MatrixDates.index(dictionary['utcTime']) # Which column are we filling?
            for key,value in dictionary.items():
                if not key in self.MatrixKeys: continue # Skip this item.
                r = self.MatrixKeys.index(key) # Which row are we filling?
                self.ForecastMatrix[r][c] = value # Populate column.
                
        # Convert datatypes. Convert values from STR to more appropriate datatypes.
        for r in range(len(self.ForecastMatrix)):
            for c in range(len(self.ForecastMatrix[r])):
                v = self.ForecastMatrix[r][c] # Get raw value from matrix.
                vlist = v.split(':') # Prepare list of ':' separated elements.
                vlen  = len(vlist) # How many ':' separated elements are there?
                if IsInt(v): v = int(v) # Can we convert to integer?
                elif IsFloat(v): v = float(v) # Can we convert to float?
                elif vlen == 3: # Can we convert to datetime?
                    v = datetime.fromisoformat(v.split('.')[0] + '+00:00') # Convert from ISO string into datetime.
                    v = v.replace(tzinfo=pytz.UTC) # Clarify it's UTC timezone.
                elif vlen == 2: # Can we convert to time?
                    v = datetime_time(hour=int(vlist[0]),minute=int(vlist[1]),tzinfo=pytz.UTC) # Convert to time datatype - *Q* not sure that this is UTC though!
                self.ForecastMatrix[r][c] = v

        # Move weekday to first row.
        i = self.MatrixKeys.index('weekday') # This is the ROW for the utcTime value. We'll pull it out of the list and make it the first entry.
        temprow = self.MatrixKeys.pop(i) # Update the list of key names.
        self.MatrixKeys.insert(0,temprow)
        temprow = self.ForecastMatrix.pop(i) # Update the list of values.
        self.ForecastMatrix.insert(0,temprow)
        # Move utcTime to first row. This shunts weekday to 2nd row.
        i = self.MatrixKeys.index('utcTime') # This is the ROW for the utcTime value. We'll pull it out of the list and make it the first entry.
        temprow = self.MatrixKeys.pop(i) # Update the list of key names.
        self.MatrixKeys.insert(0,temprow)
        temprow = self.ForecastMatrix.pop(i) # Update the list of values.
        self.ForecastMatrix.insert(0,temprow)

        # Create transposed matrix too.
        for r in range(len(self.ForecastMatrix)): # Rows (measures) will be converted into columns.
            for c in range(len(self.ForecastMatrix[r])): # Columns (dates) will be converted into rows.
                self.TransposedMatrix[c][r] = self.ForecastMatrix[r][c] # Swap rows and columns.

    def TwelveHourForecast(self):
        print ('')
        if self.ForecastMatrix == None: # No forecast yet.
            self.Log('metcheck_handler.TwelveHourForecast(): ForecastMatrix is not populated.',level='warning')
            return
        # Clip forecast to match available window space.
        width = GetTerminalSize()[0] # How wide is the window?
        temp = width - 21 # Remove label width.
        maxhours = temp // 12 # How many 12 character columns fit the window width?
        print (textcolor.yellow('Observing conditions for next ' + str(maxhours) + ' hours:'))
        # ForecastMatrix is created when the Metcheck data is loaded. It's a matrix of time slots vs weather measurements.
        # *Q* The table generated always starts with the timeslot when the data was loaded. It should roll forward as time advances.
        # self.MatrixDates contains a list of timestamps, they need converting to datetime type for comparison against NowUTC()
        # - That would help identify the FIRST column to select for trimmedrow = row[starthour:starthour + maxhours]
        for i,row in enumerate(self.ForecastMatrix): # Each row represents a single weather measurement across multiple timeslots.
            valuename = self.MatrixKeys[i] # The weather 'measure' for this row in the forecast matrix.
            line = valuename.rjust(20)[-20:] + ' ' # Construct a line to display. Start each line with measure name.
            trimmedrow = row[:maxhours] # We're only interested in the first 12 timeslots = the first 12 hours.
            for e in trimmedrow: # Construct the display line with a column for each timeslot.
                f = e # Default measurement value.
                f = self.FormatValue(valuename,e) # Format the measure value.
                # Some exceptional formatting to fit the column space available.
                if valuename == 'utcTime': # Compress a datetime value to MM.DD HH:MM
                    f = str(e.month).rjust(2,'0') + '.' + str(e.day).rjust(2,'0') + ' ' + str(e.hour).rjust(2,'0') + ':' + str(e.minute).rjust(2,'0')
                elif valuename in ['sunrise','sunset']: # Compress to HH:MM
                    f = str(e.hour).rjust(2,'0') + ':' + str(e.minute).rjust(2,'0')
                column_e = str(f).rjust(11)[-11:] + ' ' # 11 characters per column.
                color = self.SelectColor(valuename,e) # Is there any specific color associated with this measure?
                if color != None: column_e = textcolor.fgbgcolor(color,0,column_e) # color code the value.
                line += column_e # Add the measure column to the display line.
            print(line) # Print the line of measure columns.
        #self.ForecastChange() # Show which two timeslots we would compare if showing the upcoming changes in the weather.

    def Translate(self,separator=': ',color=False):
        """ Return the combined results of TranslateAstro and TranslateCivil.
            Value is returned as a list of text lines. """
        temp = self.CurrentMeasures() # Get a dictionary of weather measurements and their values.
        result = [] # Start with an empty return list.
        prevline = '' # There are some duplicates in the dictionary, filter them out.
        for key,details in temp.items(): # Go through each weather measurement in turn.
            cvalue = str(details['value']) # Get the measurement value.
            if color: # The value should be colored.
                fg = details['fg'] # Get the foreground color.
                bg = details['bg'] # Get the background color.
                if bg != None: # Only colour the measurement value if valid colors are available.
                    cvalue = textcolor.fgbgcolor(fg,bg,str(details['value']))
            line = details['title'] + separator + cvalue
            if line != prevline: # Only return unique entries.
                result.append(line) # Add to the return list.
                prevline = line
        return result
        
MainLog.Log("AstroSeeing: Initializing...")
if Parameters.UseWeatherService != True:
    MainLog.Log("AstroSeeing: WARNING: Parameters.UseWeatherService is FALSE. Atmospheric conditions will not be processed.",level='warning')
AstroSeeing = metcheck_handler() # Create instance of the 'astronomical visibility conditions' object. 
MainLog.Log("AstroSeeing: Loaded")

def VerifyFolder(FN): # 18 references.
    """ Check that all directorys in the list exist. 
        If they don't create them. """
        #*Q* Should this use the os.mkdir function instead? 
        #    - Or from pathlib import Path
        #         Path("/my/directory").mkdir(parents=True, exist_ok=True).
    result = False
    try:
        if FN[-1:] == "/": FN = FN[:-1] # Remove trailing directory separator if found.
        if os.path.isdir(FN): # Directory exists already.
            MainLog.Log('VerifyFolder: Found',FN,terminal=False)
        else:
            MainLog.Log('VerifyFolder: Missing',FN,terminal=False)
            cmd = "mkdir " + FN # Create the directory.
            #temp = osCmd(cmd) 
            osCmd(cmd) 
            cmd = "chown pi:pi " + FN # Make sure that the directory's owner is the pi user.
            #temp = osCmd(cmd) 
            osCmd(cmd) 
            cmd = "chmod +w " + FN # Make sure there is write access to the directory.
            #temp = osCmd(cmd) 
            osCmd(cmd) 
            result = True
    except Exception as e:
        MainLog.ReportException(e,comment='VerifyFolder') # Trap all the exception information in the main log file.
    return result
    
# ------------------------------------------------------------------------------------------------------

def CreateFolderList(campaign_name,exposure=None): # 9 references.
    """ Given a campaign name, generate the hierarchy of folders for this specific observation session.
        /home/pi/pilomar/
                   campaign_{name}_{exposure}/
                                   session_{timestamp}/
                                                       dark/ # Dark images stored here.
                                                       light/ # Light images stored here.
                                                       flat/ # Flat images stored here.
                                                       darkflat/ # Dark Flat images stored here.
                                                       bias/ # Bias images stored here.
                                                       preview/ # Preview images stored here.
                                                       tracking/ # Tracking images stored here.
                                                       stacked/ # Stacked images. Work files for debugging.
                                                       distortion/ # Distortion analysis images. Work files for debugging.
        If exposure time is provided as 2nd parameter it is combined into the campaign folder name. 
    """
    campaign_name = campaign_name.lower()
    campaign_name = campaign_name.replace(" ","").replace("-","").replace(":","")
    campaign_name = campaign_name.replace("(","").replace(")","")
    # temp = Parameters.GetUsbFolder() # Is there a USB drive specified for the image folders?
    if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable:
        temp = USBDiscMonitor.DfPath
        imageroot = temp + "/"
        MainLog.Log("CreateFolderList: UsbFolder is specified for image storage. Using ",temp,terminal=False)
    else:
        temp = ProjectRoot # Default to the system SD card for storage.
        imageroot = temp + "/data/"
        MainLog.Log("CreateFolderList: No UsbFolder is secified for image storage. Using ",temp,terminal=False)
    dataroot = ProjectRoot + "/data/" # This structure should be setup and configured BEFORE running this program. For safety we don't mess with this here.
    if exposure == None: # No exposure, so don't include it in the campaign name.
        campaign = "campaign_" + campaign_name + "/" # Folder specific to the campaign (the target). All images related to the campaign are stored here.
    else: # We know the exposure, so include it in the campaign name.
        campaign = "campaign_" + campaign_name + '_e' + str(exposure) + "s/" # Folder specific to the campaign (the target). All images related to the campaign are stored here.
    session = campaign + "session_" + UtcTimeStamp() + "/" # Folder specific to the current batch of photos being taken.
    FL = {}
    FL["imageroot"] = imageroot # Don't verify the root structure. (For safety!) # Root of folders for campaign (image) data.
    FL["dataroot"] = dataroot # Don't verify the root structure. (For safety!) # Root of folders for other data (target lists, parameters etc).

    FL["campaign"] = imageroot + campaign # The parent folder for the campaign. Which could store work over several nights.
    VerifyFolder(imageroot + campaign)
    
    FL["temp"] = ProjectRoot + "/temp/" # Temporary folder for experiments.
    VerifyFolder(ProjectRoot + "/temp/")
    
    FL["session"] = imageroot + session # The folder for an individual session.
    VerifyFolder(imageroot + session)
    
    FL["tracking"] = imageroot + session + "tracking/" # This is the folder where tracking images are stored.
    VerifyFolder(imageroot + session + "tracking/")
    
    FL["auto"] = imageroot + session + "auto/" # This is the folder where automatic images are stored (Normally during commissioning).
    VerifyFolder(imageroot + session + "auto/")
    
    FL["dark"] = imageroot + session + "dark/" # The folder for the DARK images.
    VerifyFolder(imageroot + session + "dark/")
    
    FL["darkflat"] = imageroot + session + "darkflat/" # The folder for the DARK FLAT images.
    VerifyFolder(imageroot + session + "darkflat/")
    
    FL["light"] = imageroot + session + "light/" # The folder for the LIGHT images. (The actual observations)
    VerifyFolder(imageroot + session + "light/")
    
    FL["flat"] = imageroot + session + "flat/" # The folder for the FLAT images.
    VerifyFolder(imageroot + session + "flat/")
    
    FL["bias"] = imageroot + session + "bias/" # The folder for the BIAS/OFFSET images.
    VerifyFolder(imageroot + session + "bias/")
    
    FL["preview"] = imageroot + session + "preview/" # The folder for the PREVIEW images.
    VerifyFolder(imageroot + session + "preview/")
    
    MainLog.Log("CreateFolderList:",str(FL),terminal=False)
    return FL

# ------------------------------------------------------------------------------------------------------

def AskYesNo(text,default=True): # 7 references.
    """ Ask any question that needs a simple Y/N answer.
        Returns logical value ('yes' or 'true' returns True, 'no' or 'false' returns False)
        Returns default value if user just presses ENTER. 
        Ignores 2nd and subsequent characters.
        Rejects all other input. """
    while True: # Loop until a satisfactory answer is given.
        temp = input(textcolor.cyan(text.strip() + " ")) # Python3
        if len(temp) == 0:
            result = default
            break
        elif temp.lower()[0] in ["n"]: # FALSE and NO recognised.
            result = False
            break
        elif temp.lower()[0] in ["y"]: # TRUE and YES recognised.
            result = True
            break
        if default: print ("Please answer yes, no or [ENTER]=(YES)")
        else: print ("Please answer yes, no or [ENTER]=(NO)")
    return result

# ------------------------------------------------------------------------------------------------------

ObservationStatusWindow = colordisplay(rows=16,columns=86,row=0,col=0,name='OSW',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title='Observation status') # This is the text window that displays current progress of an observation.
ObservationStatusWindow.DrawBorder = True # Test the 'draw border' facility.
ObservationStatusWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
ObservationStatusWindow.ClipWindow = True # Clip the display if the terminal area is insufficient. This means we see at least something.
ObservationStatusWindow.PlaceString('           Target: [TARGET                                                           ]',row=2,col=0)
ObservationStatusWindow.PlaceString('   Session folder: [FOLDER                                                           ]',row=3,col=0)
ObservationStatusWindow.PlaceString('   Tracking clock: [CLOCK                     ] UTC          [DURATION        ]       ',row=4,col=0)
ObservationStatusWindow.PlaceString('                                                                                    ',row=5,col=0)
ObservationStatusWindow.PlaceString('Storage available: [STORAGE               ]Memory available: [MEMORY              ]   ',row=6,col=0)
ObservationStatusWindow.PlaceString('         CPU load: [CPU                   ]  Motors enabled: [MEN ]                   ',row=7,col=0)
ObservationStatusWindow.PlaceString('   Camera Enabled: [CEN ] Exposure: [EXP         ]Timelapse: [TLAPSE      ]Fast:[FAST]',row=8,col=0)
ObservationStatusWindow.PlaceString('   OnChip cleanup: [OCC ]                      Control mode: [CMODE           ]       ',row=9,col=0)
ObservationStatusWindow.PlaceString('    Target status: [TSTATUS] [TSDESC                                                 ]',row=10,col=0)
ObservationStatusWindow.PlaceString('                                                                                    ',row=11,col=0)
ObservationStatusWindow.PlaceString('Camera:   Azimuth: [CAMAZ        ]                 Altitude: [CAMALT      ]           ',row=12,col=0)
ObservationStatusWindow.PlaceString('Target:   Azimuth: [TARAZ        ] [COMP]          Altitude: [TARALT      ]           ',row=13,col=0)
ObservationStatusWindow.PlaceString('Target:        RA: [RA                ]         Declination: [DEC         ]           ',row=14,col=0)
ObservationStatusWindow.PlaceString('                                                                                      ',row=15,col=0)
ObservationStatusWindow.ScanForFields() # Scan the current image for field markers.
ObservationStatusWindow.FieldFormat('MVOLTS',justify='right')
swFields = ObservationStatusWindow.ListFields() # Colour the data fields.
for key,value in swFields.items():
    ObservationStatusWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
ObservationStatusWindow.FieldColor('TSDESC',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG)
ObservationStatusWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.
ObservationStatusWindow.PlaceString(ProgramTitle.upper().ljust(86),row=1,col=0,fg=OSW_TITLE_FG,bg=OSW_TITLE_BG) # Inverse colours.

# Define some debugging windows. These appear when the terminal window is maximised.
# - The ERROR WINDOW shows any error messages raised by the software.
PrintColorList = [OSW_TEXT_FG,OSW_TEXT_GOOD] # Scrolling text windows use alternating colors for each line to aid readability in busy displays.
ErrorWindow = colordisplay(rows=5,columns=84,row=1,col=88,name='ERROR',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Error messages") 
ErrorWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
ErrorWindow.DrawBorder = True # Test the 'draw border' facility.
ErrorWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# - The SESSION WINDOW shows the condition of the RPi <> Microcontroller control.
SessionWindow = colordisplay(rows=11,columns=84,row=ErrorWindow.LastDisplayRow + 2,col=88,name='SESSION',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title='Communication status') 
SessionWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
SessionWindow.DrawBorder = True # Test the 'draw border' facility.
SessionWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
#                                    1         2         3         4         5         6         7        
#                          0123456789012345678901234567890123456789012345678901234567890123456789012345678
SessionWindow.PlaceString('  Messages:Rx queued:[RQ]   Rx total:[RT   ]    Tx queued:[TQ] Tx total:[TT   ]',row=1,col=0)
SessionWindow.PlaceString('     State:   Resets:[SR]    DevFail:[DF ]        Last Rx:[LR     ]            ',row=2,col=0)
SessionWindow.PlaceString(' RPi Bytes:Rx:[BX    ]            Tx:[TX    ]         RxErrs:[RE]              ',row=3,col=0)
SessionWindow.PlaceString('MCtl Bytes:Rx:[MRX   ] [MRXR ]    Tx:[MTX   ] [MTXR ] RxErrs:[R2] TxDrops:[TD] ',row=4,col=0)
SessionWindow.PlaceString('      MCtl:  AutoCtl:[AC ]        RemCtl:[RCL]        ClkSyn:[CS ]             ',row=5,col=0)
SessionWindow.PlaceString('            Restarts:Forced:[FR]  Remote:[RR]          Alive:[ALIVE    ]       ',row=6,col=0)
SessionWindow.PlaceString('   azimuth:Conf:[ZC ]     Reported angle:[ZA     ]  OnTarget:[ZT ]             ',row=7,col=0)
SessionWindow.PlaceString('                [ZMODE           ]:[ZD]   Trajectory expires:[ZU    ] UTC      ',row=8,col=0)
SessionWindow.PlaceString('  altitude:Conf:[LC ]     Reported angle:[LA     ]  OnTarget:[LT ]             ',row=9,col=0)
SessionWindow.PlaceString('                [LMODE           ]:[LD]   Trajectory expires:[LU    ] UTC      ',row=10,col=0)
SessionWindow.ScanForFields() # Scan the current image for field markers.
swFields = SessionWindow.ListFields()
for key,value in swFields.items():
    SessionWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
for i in ['SR','RE','R2','FR','RR']: # Set range colours on some fields to automatically color as the value changes.
    if not SessionWindow.InitializeColorRange(i,badfg=OSW_TEXT_BAD,badbg=OSW_TEXT_BG,poorfg=OSW_TEXT_POOR,poorbg=OSW_TEXT_BG):
        MainLog.Log('Unable to SetFieldColorRange for',i,'in SessionWindow.',level='error')
SessionWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.

# - The MICROCONTROLLER RX WINDOW shows the latest messages received from the microcontroller.
MctlRxWindow = colordisplay(rows=14,columns=84,row=SessionWindow.LastDisplayRow + 2,col=88,name='MCTLRX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Receive from microcontroller") 
MctlRxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlRxWindow.DrawBorder = True # Test the 'draw border' facility.
MctlRxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# - The MICROCONTROLLER TX WINDOW shows the latest messages sent to the microcontroller.
MctlTxWindow = colordisplay(rows=8,columns=84,row=MctlRxWindow.LastDisplayRow + 2,col=88,name='MCTLTX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Transmit to microcontroller") 
MctlTxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlTxWindow.DrawBorder = True # Test the 'draw border' facility.
MctlTxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# - The CAMERA WINDOW shows the activities of the CAMERA THREAD which runs separately to the main thread of the software.
CameraWindow = colordisplay(rows=8,columns=84,row=MctlTxWindow.LastDisplayRow + 2,col=88,name='CAMERA',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Camera events") 
CameraWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraWindow.DrawBorder = True # Test the 'draw border' facility.
CameraWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
MiscWindow = colordisplay(rows=9,columns=84,row=CameraWindow.LastDisplayRow + 2,col=88,name='MISC',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Miscellaneous measures") 
MiscWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MiscWindow.DrawBorder = True # Test the 'draw border' facility.
MiscWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
MiscWindow.PlaceString('  Motor clocks: Azimuth: [AZCLOCK ] Hrs             Altitude: [ALTCLOCK] Hrs        ',row=1,col=0)
MiscWindow.PlaceString('Field rotation: [FIELDROTATION                        ] Blur: [BLUR       ]         ',row=3,col=0)
MiscWindow.PlaceString('          Moon: Brightness: [MOONP]% [W]             Visible: [MOONV]               ',row=4,col=0)
MiscWindow.PlaceString('   Light level: [TWILIGHT             ]     Object magnitude: [MAGNITUDE]           ',row=5,col=0)
MiscWindow.PlaceString('     Loop time: [TOTLOOP       ]                     Average: [AVELOOP]             ',row=6,col=0)
MiscWindow.PlaceString('    Loop times: [RECLOOPS                                                      ]    ',row=7,col=0)
MiscWindow.ScanForFields() # Scan the current image for field markers.
swFields = MiscWindow.ListFields()
MiscWindow.FieldFormat('AZCLOCK',justify='right')
MiscWindow.FieldFormat('ALTCLOCK',justify='right')
MiscWindow.FieldFormat('MOONP',justify='right')
for key,value in swFields.items():
    MiscWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
MiscWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.

ImageStatusWindow = colordisplay(rows=9,columns=86,row=ObservationStatusWindow.LastDisplayRow + 2,col=0,name='IMAGE',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Image Status")
ImageStatusWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
ImageStatusWindow.DrawBorder = True # Test the 'draw border' facility.
ImageStatusWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# This is the text window that displays image and tracking progress of an observation.
ImageStatusWindow.PlaceString('       Capture state: [CAMERASTATE   ][STATETIMES       ] UTC [STATEAGE           ]  ',row=1,col=0)
ImageStatusWindow.PlaceString('        Image buffer: [OCVIB                            ] Camera task: [CTASK     ]  ',row=2,col=0)
ImageStatusWindow.PlaceString('  Drift target image: [DTI                                                        ]  ',row=3,col=0)
ImageStatusWindow.PlaceString('  Drift latest image: [DLI                                                        ]  ',row=4,col=0)
ImageStatusWindow.PlaceString(' Last azimuth tuning: [LAZT                                                       ]  ',row=5,col=0)
ImageStatusWindow.PlaceString('Last altitude tuning: [LALT                                                       ]  ',row=6,col=0)
ImageStatusWindow.PlaceString('      Session images: [IMAGES                                                     ]  ',row=7,col=0)
ImageStatusWindow.PlaceString('   Current image run: [RUN                            ]  ETA: [ETA           ] UTC   ',row=8,col=0)

ImageStatusWindow.ScanForFields() # Scan the current image for field markers.
swFields = ImageStatusWindow.ListFields()
for key,value in swFields.items():
    ImageStatusWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
ImageStatusWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.

# - The WEATHER WINDOW shows messages related to the observation conditions (forecast by online service)
# - NOTE: The fieldnames must match the fieldnames listed in the metcheck_handler object, otherwise the 
# -       weather measurements will not get automatically populated. (See self.AstroTranslation and self.CivilTranslation dictionaries)
# - Metcheck request that their name is shown whenever this free data feed service is shown. Happy to do so.
WeatherWindow = colordisplay(rows=8,columns=86,row=ImageStatusWindow.LastDisplayRow + 2,col=1,name='WEATHER',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Weather (metcheck.com)") 
WeatherWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
WeatherWindow.DrawBorder = True # Test the 'draw border' facility.
WeatherWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
WeatherWindow.PlaceString(' Cloud: Low: [CL]     Med: [CM]    High: [CH]      Tot: [CT]                ',row=1,col=0)
WeatherWindow.PlaceString('  Windspeed: [WS  ] Gusts: [WG  ]           Wind angle: [WA  ] [WC  ]       ',row=2,col=0)
WeatherWindow.PlaceString('Rain chance: [RD     ] [RPB             ]  Snow chance: [SPB             ]  ',row=3,col=0)
WeatherWindow.PlaceString('       Temp: [TE]   Freezing level: [FL  ]    Dewpoint: [DP]                ',row=4,col=0)
WeatherWindow.PlaceString('   Humidity: [HU]   Fog risk: [FOG      ] Seeing index: [SI] [SID          ]',row=5,col=0)
WeatherWindow.PlaceString('   Pressure: [PR    ]                  Pickering index: [PI] [PID          ]',row=6,col=0)
WeatherWindow.PlaceString('             [NOTES                                                        ]',row=7,col=0)
WeatherWindow.ScanForFields() # Scan the default image for field markers.
swFields = WeatherWindow.ListFields()
for key,value in swFields.items():
    WeatherWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
WeatherWindow.InitializeProgressBar('RPB',0,100,fg=textcolor.DARKGREEN,bg=textcolor.YELLOW) # Rain chance bar. 0 - 100%
WeatherWindow.InitializeProgressBar('SPB',0,100,fg=textcolor.DARKGREEN,bg=textcolor.YELLOW) # Snow chance bar. 0 - 100%
WeatherWindow.SetDefault() # Store the updated 'blank' template to be reused when clearing the display.

# ---------------------------------------------------------------------------------

class orbitchart(attributemaster): # 1 references.
    """ Generate a character graphics chart to plot and trace the orbit of the observation target.
        This can be displayed in the terminal output. 
        Uses the textcolor library : colordisplay to maintain the display window and sprites. """
        
    def __init__(self,minaz=45,maxaz=315,minalt=0,maxalt=90,colorscheme=None,row=0,col=0):
        """ minaz, minalt, maxaz, maxalt specify the observable limits of the telescope.
            The display reflects this by shading the region outside this area.
            colorscheme = text name of a chosen color scheme. """
        # Create an empty plot grid.
        self.Log = MainLog.Log # Handle to the method/function that will be used to log messages.
        self.MinAzimuth = minaz
        self.MaxAzimuth = maxaz
        self.MinAltitude = minalt
        self.MaxAltitude = maxalt
        # Default colour scheme is the 'blue' scheme.
        self.LabelColor = textcolor.SKYBLUE2 
        self.ScaleColor = textcolor.CYAN
        self.InRangeColor = textcolor.NAVYBLUE
        self.OutRangeColor = textcolor.DEEPSKYBLUE4A
        self.BorderFG = textcolor.NAVYBLUE
        self.BorderBG = textcolor.BLACK
        if colorscheme == 'white':
            self.LabelColor = textcolor.GREY3
            self.ScaleColor = textcolor.GREY11
            self.InRangeColor = textcolor.BLACK
            self.OutRangeColor = textcolor.GREY50
            self.BorderFG = textcolor.GREY15
            self.BorderBG = textcolor.BLACK
        elif colorscheme == 'red':
            self.LabelColor = textcolor.ORANGERED1 
            self.ScaleColor = textcolor.ORANGE1
            self.InRangeColor = textcolor.BLACK
            self.OutRangeColor = textcolor.MAROON
            self.BorderFG = textcolor.DARKRED
            self.BorderBG = textcolor.BLACK
        elif colorscheme == 'green':
            self.LabelColor = textcolor.LIME 
            self.ScaleColor = textcolor.PALEGREEN1
            self.InRangeColor = textcolor.BLACK
            self.OutRangeColor = textcolor.DARKGREEN
            self.BorderFG = textcolor.DARKGREEN
            self.BorderBG = textcolor.BLACK
        self.DisplayBuffer = colordisplay(row=row,col=col,rows=22,columns=86,name='Chart') # Create virtual colour display buffer.
        self.DisplayBuffer.SetBorderColors(self.BorderFG,self.BorderBG)
        self.DisplayBuffer.DrawBorder = True
        self.TrackColor = textcolor.BLUE3 # The color of the track left behind the target object.
        
        self.InitializeChart()
        # Create sprites to highlight the observation target.
        self.DisplayBuffer.AddSprite("target",Symbol['target'],row=None,col=None,fg=textcolor.BLACK,bg=textcolor.LIME,level=3) # Horizontal location of target. Level 2 means in front of level 1 sprites.
        self.DisplayBuffer.ShowSprite("target")
        self.DisplayBuffer.AddSprite("camera",Symbol['camera'],row=None,col=None,fg=textcolor.CYAN,bg=textcolor.BLACK,level=2) # Where is the camera currently pointing?
        self.DisplayBuffer.ShowSprite("camera")
        self.DisplayBuffer.AddSprite("sun",Symbol['sun'],row=None,col=None,fg=textcolor.YELLOW,bg=textcolor.BLACK,level=1) # Where is the sun?
        self.DisplayBuffer.ShowSprite("sun")
        self.DisplayBuffer.AddSprite("moon",Symbol['moon'],row=None,col=None,fg=textcolor.GREY70,bg=textcolor.BLACK,level=1) # Where is the moon?
        self.DisplayBuffer.ShowSprite("moon")
        self.DisplayBuffer.AddSprite("iss",Symbol['iss'],row=None,col=None,fg=textcolor.WHITE,bg=textcolor.BLACK,level=1) # Where is the international space station?
        self.DisplayBuffer.ShowSprite("iss")
        self.DisplayBuffer.AddSprite("css",Symbol['css'],row=None,col=None,fg=textcolor.RED,bg=textcolor.BLACK,level=1) # Where is the international space station?
        self.DisplayBuffer.ShowSprite("css")
        # Add key to chart dynamically from the list of defined sprites.
        a = 15 # Number of columns allowed for key entry
        c = 2 # Character offset from column 0
        for i,s in enumerate(self.DisplayBuffer.sprites): 
            f = s.fg
            if f == None: s.fg = textcolor.WHITE
            b = s.bg
            if b == None: s.bg = textcolor.BLACK
            self.DisplayBuffer.PlaceString(s.symbol,row=21,col= (i * a) + c,fg=f,bg=b)
            self.DisplayBuffer.PlaceString('=' + s.name,row=21,col = (i * a) + 1 + c, fg=self.LabelColor,bg=textcolor.BLACK)
        
    def InitializeChart(self):
        """ Draw the initial empty chart. """
        self.DisplayBuffer.PlaceString("N-      NE      -E-      SE       -S-      SW       -W-       NW      -N",row=0,col=0,fg=self.LabelColor,bg=textcolor.BLACK)
        self.DisplayBuffer.PlaceString("0       45       90      135      180      225      270      315       0",row=1,col=0,fg=self.ScaleColor,bg=textcolor.BLACK)
        alt = 90
        for i in range(19): # The sky sphere is shown over 19 lines (0-18).
            if i == 9: # Horizon
                self.DisplayBuffer.PlaceString("=================+=================+=================+=================+",row=2+i,col=0,fg=textcolor.SILVER,bg=textcolor.BLACK)
            else:
                self.DisplayBuffer.PlaceString(  "                 |                 |                 |                 |",row=2+i,col=0,fg=self.ScaleColor,bg=textcolor.BLACK)
            t = str(alt).rjust(3," ")
            self.DisplayBuffer.PlaceString(t,row=2+i,col=73,fg=self.ScaleColor,bg=textcolor.BLACK) # Altitude 
            if alt == 90: # Zenith
                self.DisplayBuffer.PlaceString("Zenith",row=2+i,col=78,fg=self.LabelColor,bg=textcolor.BLACK)
            elif alt == 0: # Horizon
                self.DisplayBuffer.PlaceString("Horizon",row=2+i,col=78,fg=self.LabelColor,bg=textcolor.BLACK)
            elif alt == -90: # Nadir
                self.DisplayBuffer.PlaceString("Nadir",row=2+i,col=78,fg=self.LabelColor,bg=textcolor.BLACK)
            alt -= 10 # Each line is 10 degrees altitude lower than the previous one.
        # Set colours to show the visible region of the sky that can be observed.
        for iAlt in range(-90,90,5): # 5 degree rows from Zenith to Nadir.
            for iAz in range(0,360,5): # 5 degree columns around the horizon.
                fg = self.ScaleColor
                bg = textcolor.BLACK 
                if iAlt < self.MinAltitude or iAlt > self.MaxAltitude or iAz < self.MinAzimuth or iAz >= self.MaxAzimuth: # Azimuth is out of range.
                    fg = self.ScaleColor 
                    bg = self.OutRangeColor
                else:
                    fg = self.ScaleColor 
                    bg = self.InRangeColor
                col, row = self.altaztocell(iAlt,iAz) # Which character cell does this alt/az represent?
                self.DisplayBuffer.ColorCell(row,col,fg,bg)

    def draw(self,TerminalRows=None,TerminalCols=None):
        """ Refresh the display. """
        # Draw the grid and add some colour.
        #self.DisplayBuffer.Draw(TerminalRows,TerminalCols)
        self.DisplayBuffer.Display(TerminalRows,TerminalCols)
        return True

    def altaztocell(self,alt,az):
        """ Convert an alt/az location into a specific character cell. """
        # Convert alt and az values into row/column on chart.
        x = round(((az % 360) * 71.0/360.0) + 0.5) # 360Degrees in 72 slots (0 - 71). 
        y = 18 - round(((alt + 90) * 18.0/180.0) + 0.5) # 180Degrees in 18 slots.
        y = y + 2 # Offset y to allow for first 2 heading lines.
        return x,y

    def celltoaltaz(self,x,y):
        """ Convert a character position (row,column) into an alt/az location. """
        # Convert row/column to alt and az values.
        y = y - 2
        alt = (180 * (18 - y - 0.5) / 18) - 85 # 180Degrees in 18 slots.
        az = 360 * (x - 0.5) / 72 # 360Degrees in 72 slots. 
        return alt,az

    def plot(self,name,alt,az,track=True):
        """ Place a sprite at a specific alt/az position on the chart. """
        # Update the location of the object on the grid.
        x,y = self.altaztocell(alt,az) # Convert alt, az coordinates into row/column.
        self.DisplayBuffer.MoveSprite(name=name,row=y,col=x) # Place the sprite at the x,y position in the display.
        if track: self.DisplayBuffer.PlaceString(".",row=y,col=x,fg=OSW_TEXT_BAD,bg=self.TrackColor) # This is permanently added to the display background and tracks the historic path of the target.
        return True

# ---------------------------------------------------------------------------------

# Orbit Chart. This is a character graphic of the sky, observation target and camera location.
chart = orbitchart(minaz=Parameters.MinAzimuthAngle,maxaz=Parameters.MaxAzimuthAngle,colorscheme=Parameters.ColorScheme,row=WeatherWindow.LastDisplayRow + 2,col=0) # Initialize a new chart for plotting the position of the target (and camera).
InstructionWindow = colordisplay(rows=2,columns=86,row=chart.DisplayBuffer.LastDisplayRow + 2,col=0,fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Commands")
# Instruction summary window.
#                             '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456'
InstructionWindow.PlaceString('    [x]Quit          [r]Refresh           [m]Menu           [d]Debug on/off           ',row=1,col=0)
InstructionWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.

# - The LOG objects can be told to output error messages to a specific window too.
MainLog.ErrorWindow = ErrorWindow # Tell the MAIN logging mechanism that error messages can be replicated to the ERROR WINDOW. 
CamLog.ErrorWindow = CameraWindow # Tell the CAMERA logging mechanism that error messages can be replicated to the CAMERA WINDOW. 
# - Drift tracker debugging window.
# Events and decisions made by the drift tracking routine.
DriftWindow = colordisplay(rows=10,columns=50,row=1,col=173,name='DRIFT',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Drift tracking")
DriftWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DriftWindow.DrawBorder = True # Test the 'draw border' facility.
DriftWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# - Camera thread communications windows.
# Window showing communication from the camera handler thread to the main observation routine.
CameraRxWindow = colordisplay(rows=19,columns=50,row=DriftWindow.LastDisplayRow + 2,col=173,name='CAMERARX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Receive from camera handler")
CameraRxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraRxWindow.DrawBorder = True # Test the 'draw border' facility.
CameraRxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# Window showing communications sent TO the camera handler from the main observation routine.
CameraTxWindow = colordisplay(rows=10,columns=50,row=CameraRxWindow.LastDisplayRow + 2,col=173,name='CAMERATX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Transmit to camera handler")
CameraTxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraTxWindow.DrawBorder = True # Test the 'draw border' facility.
CameraTxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# General purpose window where developer messages can be written during observations.
DevWindow = colordisplay(rows=18,columns=50,row=CameraTxWindow.LastDisplayRow + 2,col=173,name='DEVELOPER',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Developer events")
DevWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DevWindow.DrawBorder = True # Test the 'draw border' facility.
DevWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# All windows are defined. Turn on the 'reduceio' feature in them all.
colordisplay.GlobalReduceIO(True) # When redrawing windows, only the changed lines are repainted. 

# ///////////////////////////////////////////////////////////////////////////////////
# Camera assets. 
# ///////////////////////////////////////////////////////////////////////////////////

# The camera module records RAW image data in a JPG file with the data encoded as extra data.
# We need to extract that RAW data and save it as a regular DNG file for later processing.
# PiDNG is a great utility to do this. Need to use an older version of PiDNG because newer versions do more things, but don't support this function easily anymore.
PiDNG = RPICAM2DNG() # Create instance of the PiDNG converter to extract RAW data from JPG files.

# ------------------------------------------------------------------------------------------------------

class astrolens(attributemaster): # 1 references.
    """ Object representing the LENS being used by the telescope. 
        Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example. """
    def __init__(self,length,horizontal_fov,vertical_fov,aperture=2.8):
        self.Log = CamLog.Log # Handle to the method that logs messages.
        self.BaseLength = length # The length of the lense WITHOUT any multiplier effect.
        self.Length = length # 'focal length' of the lens.
        self.EquivLength = self.Length * 5.6 # From https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/ 35mm equivalent focal length (?)
        self.FovHorizontal = horizontal_fov
        self.FovVertical = vertical_fov
        self.Fov = min(self.FovHorizontal, self.FovVertical) # When calculating the FOV for a survey, use the smaller value.
        self.Aperture = aperture # FStop of the lens. *Q* Multiplier will impact this too. Hmm...
        self.ID = str(self.Length) + "|" + str(self.FovHorizontal) + "|" + str(self.FovVertical) # Unique ID of lens features.
        self.Log("AstroLens: Length: " + str(self.Length) + "mm (equiv. " + str(self.EquivLength) + "mm) FoV: " + str(self.FovHorizontal) + DegreeSymbol + "*" + str(self.FovVertical) + DegreeSymbol,terminal=False)

# ------------------------------------------------------------------------------------------------------

class astrosensor(attributemaster): # 1 references.
    """ Object representing the IMAGE SENSOR being used by the telescope. 
        Default values are for the V1 RPi High Quality Camera (Sony sensor)? 
        Individual characteristics can be specified, or a specific sensor type can be given. 
        Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example. """
    def __init__(self,sensor_type='',pixel_width=4056,pixel_height=3040,max_seconds=200,min_seconds=0.0000001):
        self.Log = CamLog.Log # Handle to the method that logs messages.
        self.PixelWidth = pixel_width
        self.PixelHeight = pixel_height
        self.MaxExposureSeconds = max_seconds
        self.MinExposureSeconds = min_seconds
        self.Type = sensor_type
        if sensor_type == 'imx477': # If the sensor type is recognised then set the value automatically.
            self.Log("AstroSensor: Recognised " + sensor_type + " setting other characteristics automatically.",terminal=False)
            self.PixelWidth=4056
            self.PixelHeight=3040
            self.MaxExposureSeconds=200 # 200 seconds is the longest exposure time that raspistill can deliver.
            self.MinExposureSeconds=1e-6 # 1 microsecond is the fastest exposure time that raspistill can deliver.
        self.ID = str(self.PixelWidth) + "|" + str(self.PixelHeight) # Unique ID of lens features.
        self.Mode = 3 
        self.OnChipCleanup = True # Records whether we've got the on-chip cleanup enabled or not. 
        # width = image width in pixels.
        # height = image height in pixels.
        # video = Can take video in this mode.
        # image = Can take photo in this mode.
        # fov = full or partial field of view. partial means only the centre of the sensor is used. full means the whole sensor is used.
        self.ModeDict = {1 : {'width' : 2028, 'height' : 1080, 'video' : True, 'image' : False, 'aspect' : '169:90', 'framerate' : {'min' : 0.1, 'max' : 50}, 'fov' : 'partial', 'binning' : True, 'scaled' : False, 'maxseconds' : 10.2, 'raw' : False},
                         2 : {'width' : 2028, 'height' : 1520, 'video' : True, 'image' : False, 'aspect' : '4:3', 'framerate' : {'min' : 0.1, 'max' : 50}, 'fov' : 'full', 'binning' : True, 'scaled' : False, 'maxseconds' : 10.2, 'raw' : True},
                         3 : {'width' : 4056, 'height' : 3040, 'video' : True, 'image' : True, 'aspect' : '4:3', 'framerate' : {'min' : 0.005, 'max' : 10}, 'fov' : 'full', 'binning' : False, 'scaled' : False, 'maxseconds' : 200.0, 'raw' : False},
                         4 : {'width' : 1012, 'height' : 760, 'video' : True, 'image' : True, 'aspect' : '4:3', 'framerate' : {'min' : 50.1, 'max' : 120}, 'fov' : 'full', 'binning' : False, 'scaled' : True, 'maxseconds' : 10.2, 'raw' : False}}
        self.Log("AstroSensor: Size, " + str(self.PixelWidth) + "*" + str(self.PixelHeight),terminal=False)

    def GetCentre(self):
        """ Return the X and Y co-ordinates of the centre of the image. """
        return int(round(self.PixelWidth / 2,0)), int(round(self.PixelHeight / 2,0))
        
    def _SetMode(self,mode : int):
        """ Given a new mode, validate it and then update the dependent values in the sensor.
            There are dependencies in AstroCamera that should be updated afterwards, so this
            should be called via astrocamera.SetMode(mode). """
        if mode in self.ModeDict:
            self.PixelWidth = self.ModeDict[mode]['width'] # Update maximum image pixel width
            self.PixelHeight = self.ModeDict[mode]['height'] # Update maximum image pixel height
            self.Mode = mode
            self.MaxExposureSeconds = self.ModeDict[mode]['maxseconds'] # Update maximum exposure time. 
            if self.ModeDict[mode]['image'] == False:
                self.Log("AstroSensor._SetMode: Mode " + str(self.Mode) + ") is not recommended for still images.",level='warning')
            if self.ModeDict[mode]['binning'] == True:
                self.Log("AstroSensor._SetMode: Mode " + str(self.Mode) + ") activates binning for increased sensitivity.",level='info',terminal=False)
            if self.ModeDict[mode]['raw'] == False:
                self.Log("AstroSensor._SetMode: Mode " + str(self.Mode) + ") does not support RAW data correctly. Processing may fail.",level='error')
        else:
            self.Log("AstroSensor._SetMode: Mode " + str(mode) + " is not recognised, ignored.",level='warning')
        self.Log("AstroSensor._SetMode: Mode " + str(mode) + " selected.",terminal=False)
        CameraWindow.Print("Sensor mode: " + str(mode))
        self.Log("AstroSensor: Pixel dimensions now: " + str(self.PixelWidth) + "x" + str(self.PixelHeight),terminal=False)

    def DisableCleanup(self):
        """ Disable the on-chip image cleanup for the sensor.
            Even in RAW capture mode, the sensor will perform some image cleanup by default.
            This cleanup degrades the raw data that astro photo stacking software will work with.
            Therefore it is advisable to disable this cleanup before taking photos for stacking.            """
        print (textcolor.yellow("Disabling sensor cleanup to improve purity of sensor raw data."))
        if not self.Type in ['imx477']: # Check that the sensor cleanup function actually can be disabled.
            self.Log("AstroSensor.DisableCleanup is not supported for " + self.Type + " sensors. Ignored.",level='warning')
            return False
        cmd = 'sudo vcdbg set imx477.dpc 0' # Turn off on-chip cleaning of the image.
        # This raises some error messages like this...
        #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
        # According to raspberry pi forum, these can be ignored. The output is not displayed, but is logged in case other errors occur in the future.
        self.Log(cmd,terminal=False)
        #temp = osCmd(cmd)
        osCmd(cmd)
        self.OnChipCleanup = False
        self.Log("Raspberry Pi High Quality Camera, on chip image cleanup DISABLED.",terminal=False)
        CameraWindow.Print(NowHMS() + " On Chip Cleanup - OFF")
        return True

    def EnableCleanup(self):
        """ Enable the on-chip image cleanup for the sensor.
            This returns the on-chip image cleanup back to the default state (ON)
            It is recommended to have it disabled for image stacking of raw images. """
        print (textcolor.yellow("Enabling sensor cleanup to restore factory functionality."))
        if not self.Type in ['imx477']:
            self.Log("AstroSensor.EnableCleanup is not supported for " + self.Type + " sensors. Ignored.",level='warning')
            return False
        cmd = 'sudo vcdbg set imx477.dpc 3' # Turn on on-chip cleaning of the image.
        # This raises some error messages like this...
        #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
        # According to raspberry pi forum, these can be ignored. The output is logged but not displayed in case other errors occur in the future.
        self.Log(cmd,terminal=False)
        # temp = osCmd(cmd)
        osCmd(cmd)
        self.OnChipCleanup = True
        self.Log("Raspberry Pi High Quality Camera, on chip image cleanup ENABLED.",terminal=False)
        CameraWindow.Print(NowHMS() + " On Chip Cleanup - ON")
        return True

# ------------------------------------------------------------------------------------------------------

FolderList={} # Dummy entry until FolderList is fully defined. astrocamera doesn't initialize otherwise. 

class astrocamera(attributemaster): # 1 references.
    """ Object representing the camera assembly being used.
        It contains the LENS and SENSOR objects, also various attributes and settings of the overall camera. """
    def __init__(self,inp_sensor,inp_lens,exposure=1.0,trackingexposure=5.0):
        self.Log = CamLog.Log # Handle to the method that logs messages.
        self.Sensor = inp_sensor # The sensor that makes up the camera.
        self.Lens = inp_lens # The lens that makes up the camera.
        self.ExposureSeconds = exposure # Exposure seconds per frame for astro photos ('light' frames).
        self.TrackingExposureSeconds = trackingexposure # Tracking photos are always 5 second exposure.
        self.TimelapseSeconds = 0 # Delay between successive exposures if taking timelapse images.
        self.TimelapseTimer = None # Handle to timelapse timer if set.
        self.PixelsPerFovDegreeWidth = 0 # Set by ModeChange() below.
        self.PixelsPerFovDegreeHeight = 0 # Set by ModeChange() below. 
        self.SecondsPerPixel = 0.0 # Set by ModeChange() below. Specifies how long an object takes to traverse one pixel of an image.
        self.ModeChange() # Set values based upon sensor mode. 
        self.LastImageDateTime = None # When was the latest image taken? # *Q* How widely is this attribute used?
        self.Lastjpg = None # The filename of the last jpg taken (if saved)
        self.Previewjpg = None # The filename of the last preview image generated. 
        self.CvImage = None # openCV image buffer. Loaded explicitly when needed.
        self.CaptureStart = None # Timestamp when image capture started. Used to detect camera hanging.
        #self.AstrotimeStart = None # skyfield timestamp when image capture started. # Used to synchronise markup calculations.
        self.CaptureEnd = None # Timestamp when image capture completed. Used to detect camera hanging.
        self.AstrotimeEnd = None # skyfield timestamp when image capture completed. # Used to synchronise markup calculations.
        self.BatchCount = 0 # How many photos taken in the current observation batch? 
        self.ImageGenerator = None # Can be handle to image generation procedure if we are creating 'fake' photos.
        self.ID = self.Sensor.ID + "|" + self.Lens.ID # Unique ID of lens and sensor characteristics.
        self.SetImageType('light') # The type of image being captured. Links to FolderList. Tells HOW to process the image and WHERE to store it.
        self.CameraTasks = [] # No tasks to perform yet.
        self.LastLightOptions = '' # Keep a note of the camera options used for the latest light image.
        # Observation specific settings. These override the general parameters in instances where the general parameters don't make sense. Eg meteor monitoring.
        self.CameraSaveDng = True
        self.CameraSaveJpg = True
        self.FastImageCapture = False
        self.CameraOptions = '' # The camera options passed to raspistill. These depend upon the image type being captured.

    def SetObservationParameters(self):
        """ Choose which parameter settings to apply to the observation about to begin.
            These are based upon the general parameter settings, but are overridden 
            for some types of targets, such as meteors. 
            
                self.CameraTasks        : What tasks should the camerahandler deal with?
                self.CameraSaveDng      : Do we produce DNG raw sensor data?
                self.CameraSaveJpg      : Do we create simple JPG images? (Raw data removed)
                self.CameraSaveFits     : Do we create FITS files? (Still under development)
                self.FastImageCapture   : Do we perform fast image capture (delay image processing until later).
                self.LiveStacking       : Do we perform live stacking?
            
            """
        # Decide which tasks the camerahandler will deal with.
        self.CameraTasks = ['image','pause']
        if Session.Target.ObjectType in ['meteor']: 
            CameraWindow.Print(NowHMS() + " No preview's generated for " + Session.Target.ObjectType + " recordings.")
            self.Log("astrocamera.SetObservationParameters No preview's generated for", Session.Target.ObjectType, "recordings.",terminal=False)
        else: self.CameraTasks.append('preview') # Don't preview for meteor showers.
        if Session.Target.ObjectType in ['meteor','altaz']:
            CameraWindow.Print(NowHMS() + " No tracking performed for " + Session.Target.ObjectType + " targets.")
            self.Log("astrocamera.SetObservationParameters No tracking performed for", Session.Target.ObjectType, "targets.",terminal=False)
        elif Parameters.UseTracking: self.CameraTasks.append('tracking') # Don't track for fixed targets.
        else: # Tracking will not be used.
            DriftWindow.Print(NowHMS() + ' Tracking disabled.')
        # self.CameraTasks = ['image','preview','tracking','pause'] # A list of tasks that must be performed in sequence.
        #if Parameters.AnalyseLensDistortion: # We should analyse lens distortion too.
        #    self.CameraTasks.append('distortion')
        #    CameraWindow.Print(NowHMS() + " Will analyse lens distortion.")
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", Selected tasks:", self.CameraTasks,terminal=False)
        
        # Set observation specific parameters for the camera based upon general parameter settings.
        # - Eg 'meteor' mode can override some settings, but we don't want to disturb the general settings used for other targets.
        if Session.Target.ObjectType in ['meteor']: self.CameraSaveDng = False
        else: self.CameraSaveDng = Parameters.CameraSaveDng
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", CameraSaveDng",self.CameraSaveDng,terminal=False)

        if Session.Target.ObjectType in ['meteor']: self.CameraSaveJpg = True
        else: self.CameraSaveJpg = Parameters.CameraSaveJpg
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", CameraSaveJpg",self.CameraSaveJpg,terminal=False)

        if Session.Target.ObjectType in ['meteor']: self.FastImageCapture = True
        else: self.FastImageCapture = Parameters.FastImageCapture
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", FastImageCapture",self.FastImageCapture,terminal=False)

        #if Session.Target.ObjectType in ['meteor']: self.LiveStacking = False
        #else: self.LiveStacking = Parameters.LiveStacking
        #self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", LiveStacking",self.LiveStacking,terminal=False)
        
        # What image types to process?
        if Session.Target.ObjectType in ['meteor']: # Meteor detection is special, just grap JPGS as fast as possible.
            # Meteor monitoring is always in fast mode and we don't intend to extract any further data, just capture .jpgs.
            self.CameraSaveDng = False # Don't generate raw data.
            self.CameraSaveJpg = True # Just create simple JPG files.
            self.FastImageCapture = True # Capture images as quickly as possible.
        else: # Other targets follow the general parameter settings.
            self.CameraSaveDng = Parameters.CameraSaveDng
            self.CameraSaveJpg = Parameters.CameraSaveJpg
            self.FastImageCapture = Parameters.FastImageCapture

        self.Log("astrocamera.SetObservationParameters CameraSaveDng/Jpg:", self.CameraSaveDng, self.CameraSaveJpg, terminal=False)
        self.Log("astrocamera.SetObservationParameters FastImageCapture:", self.FastImageCapture, terminal=False)
        return True
        
    def EstimateFov(self):
        """ Ask the user to enter the pixel diameter of the moon from a photograph. 
            Use this to estimate the FieldOfView of the camera and adjust parameters accordingly. """
        self.Log("astrocamera.EstimateFov: Begin",terminal=False)
        print(textcolor.yellow("Calibrate lens"))
        MoonMeanDiaDeg = 0.5286
        ExpectedDiaPix = int(self.PixelsPerFovDegreeWidth * MoonMeanDiaDeg) # How big do we expect the moon to be with current settings?
        listlines = ["Currently the lens has the following characteristics", " ",
                     "Horizontal field of view: " + str(self.Lens.FovHorizontal) + DegreeSymbol,
                     "Vertical field of view: " + str(self.Lens.FovVertical) + DegreeSymbol,
                     "Minimum field of view: " + str(self.Lens.Fov) + DegreeSymbol,
                     "Horizontal pixels per degree FOV: " + str(self.PixelsPerFovDegreeWidth),
                     "Vertical pixels per degree FOV: " + str(self.PixelsPerFovDegreeHeight),
                     "",
                     "The Moon's disc is " + str(MoonMeanDiaDeg) + DegreeSymbol + " diameter on average.",
                     "Expected diameter in an image is about " + str(ExpectedDiaPix) + " pixels."]
        textcolor.TextBox(listlines)
        result = AskYesNo("Do you want to calibrate the field of view of the lens? [y/N]",False)
        if result:
            result = AskYesNo("Do you have an image of the moon captured with the current lens? [y/N]",False)
        if result == False:
            listlines = ["You must take a photograph of the moon with the current lens.",
                         "Measure the pixel diameter of the moon's full disc on that image.",
                         "Using that pixel size we can estimate the field of view of the lens."]
            textcolor.TextBox(listlines)
            return # Do nothing.

        # Can we offer any hints from the last image captured?
        if type(self.CvImage) != type(None): # There's an image in the buffer, what large objects are in there?
            lastimage = self.SimplifyImage(self.CvImage) # Simplify the last image captured.
            dia_min = 50 # Smallest diameter objects to list.
            dia_max = 600 # Largest diameter objects to list.
            area_min = math.pi * ((dia_min / 2) ** 2)
            area_max = math.pi * ((dia_max / 2) ** 2)
            BC_Count, BC_List = self.CountStars(lastimage,minval=area_min,maxval=area_max) # Count objects with large pixel areas (100-600 pixel radius).
        else: # No objects identified.
            BC_Count = 0
            BC_List = []
        if BC_Count > 0:
            self.Log("The last image has",BC_Count,"large objects in it.",terminal=True)
            for i,j in enumerate(BC_List): # List all the large objects found.
                jx = j[0] # x value for centre of object.
                jy = j[1] # y value for centre of object.
                dia = int(j[2] * 2) # Pixel diameter of the object.
                self.Log(i,"Centered at (",jx,",",jy,") diameter",dia,"pixels",terminal=True)
        else: # There is no existing image in the buffer, so we cannot offer any clues.
            self.Log("There is no recent image loaded, cannot list any large objects.",terminal=True)

        # We want to continue.
        rawtext = None
        while rawtext == None:
            rawtext = input(textcolor.cyan("How many pixels is the diameter of the Moon's full disc? ('x' to quit): "))
            rawtext = rawtext.lower()
            if rawtext == 'x':
                rawtext = None
                break # Quit
            if IsInt(rawtext):
                break # We have a value to use.
                
            print(textcolor.red("Please try again. Integer values only."))
            rawtext = None # Try again.
            
        if rawtext == None: 
            return # Nothing to do.

        # We have what we need.
        moonpixels = TextToInt(rawtext) # Convert the measured diameter into integer.
        print ("The camera records the moon as",moonpixels,"pixels in diameter.")
        print ("The moon is" + str(MoonMeanDiaDeg) + DegreeSymbol,"in diameter on average.")
        # Convert to field of view.
        # Lens fields to change...
        self.Lens.FovHorizontal = round(self.Sensor.PixelWidth * MoonMeanDiaDeg / moonpixels,1) # FOV to 1 decimal place is enough.
        self.Lens.FovVertical = round(self.Sensor.PixelHeight * MoonMeanDiaDeg / moonpixels,1) # FOV to 1 decimal place is enough.
        self.Lens.Fov = min(self.Lens.FovHorizontal, self.Lens.FovVertical) # When calculating the FOV for a survey, use the smaller value.
        # Camera fields to change...
        self.ModeChange() # Set camera's FOV related values just as if the sensor mode had changed. 
        ExpectedDiaPix = int(self.PixelsPerFovDegreeWidth * MoonMeanDiaDeg) # How big do we expect the moon to be with current settings?
        listlines = ["The lens now has the following characteristics"," ",
                     "Horizontal field of view: " + str(self.Lens.FovHorizontal) + DegreeSymbol,
                     "Vertical field of view: " + str(self.Lens.FovVertical) + DegreeSymbol,
                     "Minimum field of view: " + str(self.Lens.Fov) + DegreeSymbol,
                     "Horizontal pixels per degree FOV: " + str(self.PixelsPerFovDegreeWidth),
                     "Vertical pixels per degree FOV: " + str(self.PixelsPerFovDegreeHeight), " ",
                     "The Moon's disc is " + str(MoonMeanDiaDeg) + DegreeSymbol + " diameter on average.",
                     "Expected diameter in an image is about " + str(ExpectedDiaPix) + " pixels."]
        textcolor.TextBox(listlines)
        result = AskYesNo("Do you want to make these changes permanent? [y/N]",False)
        if result: # Make these changes permanent by setting them in the parameter file.
            Parameters.LensHorizontalFov = self.Lens.FovHorizontal
            Parameters.LensVerticalFov = self.Lens.FovVertical
        else: # Don't touch the parameter settings, so the system will reset when restarted.
            print (textcolor.yellow("These values are temporary. They will reset when you restart the software."))
            print (textcolor.red("To make these values permanent please edit LensHorizontalFov and LensVerticalFov values in the parameters file."))
            print (textcolor.red("(" + ParameterFileName + ")"))
        
    def SimplifyImage(self,cvimagebuffer,blurradius=13):
        """ Enhance the image ready for astroalign to process it. """
        self.Log("astrocamera.SimplifyImage: Begin",terminal=False)
        cvimagebuffer = cvimagebuffer.astype(np.uint8) # Make sure it's int8 type.
        if len(cvimagebuffer.shape) > 2: # Color image. Convert to Grayscale.
            cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2GRAY)# Convert to grayscale.
        retval, cvimagebuffer = cv2.threshold(cvimagebuffer,100,255,cv2.THRESH_BINARY) # 100 should ignore clouds more easily and just recognise brighter stars.
        if blurradius % 2 == 0: blurradius += 1 # Must be odd.
        # 2nd enlarge the stars using a blur filter.
        cvimagebuffer = cv2.GaussianBlur(cvimagebuffer,(blurradius,blurradius),0)
        # 3rd sharpen these larger star dots back into more definite black-or-white.
        # - Use adaptive thresholding now to make the stars more crisp.
        # - Adaptive means that the threshold limit between BLACK and WHITE is chosen by the function.
        retval, cvimagebuffer = cv2.threshold(cvimagebuffer,16,255,cv2.THRESH_BINARY + cv2.THRESH_OTSU) # OTSU is adaptive threshold limits.
        # 4th shrink the image to make movement comparisons faster (though less precise).
        self.Log("astrocamera.SimplifyImage: End. Image is",cvimagebuffer.shape[0],"*",cvimagebuffer.shape[1],terminal=False)
        return cvimagebuffer

    def CountStars(self,cvimagebuffer,minval=3,maxval=300):
        """ Count the number of stars in an image. 
            From: https://stackoverflow.com/questions/48154642/how-to-count-number-of-dots-in-an-image-using-python-and-opencv
            for 100% scaled image, maxval 300 is good, stars are generally 200pixel areas.
            for 25% scaled image, maxval 20 is good, stars are generally 13pixel areas. """
            
        self.Log("astrocamera.CountStars: Begin",terminal=False)
        # Make sure image is grayscale.
        if len(cvimagebuffer.shape) == 3:
            if cvimagebuffer.shape[2] == 4: # We have a BGRA image, convert it to grayscale.
                self.Log("astrocamera.CountStars: Received BGRA color image, converted to grayscale.",terminal=False)
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGRA2GRAY)
            else: # We have a BGR image, convert it to grayscale.
                self.Log("astrocamera.CountStars: Received BGR color image, converted to grayscale.",terminal=False)
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2GRAY)
        # Threshold the image to make it more crisp.
        temp, threshed = cv2.threshold(cvimagebuffer, 100, 255, cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
        # findcontours to identify 'dots' (contours) in the image. This will recognise STARS and also some patterns made by stars. So it needs filtering.
        dots = cv2.findContours(threshed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[-2]
        # filter the 'dots' by their area. Small ones are stars, large ones are some other artifact.
        starcount = 0
        starlist = []
        for dot in dots: # Check each dot in turn.
            if minval < cv2.contourArea(dot) < maxval: # We only want small dots to count as stars.
                starcount += 1 # Increment count.
                dot_x, dot_y, dot_w, dot_h = cv2.boundingRect(dot) # Bordering rectangle of dot.
                dot_radius = int((dot_w + dot_h) / 4) # Half average of width and height.
                ctr_x = int(dot_x + dot_w / 2) # Centre of dot.
                ctr_y = int(dot_y + dot_h / 2) # Centre of dot.
                staritem = [ctr_x, ctr_y, dot_radius]
                starlist.append(staritem) # Construct list of star locations.
        self.Log("astrocamera.CountStars: End. Counted",starcount,terminal=False)
        return starcount, starlist

    def SetImageType(self,imagetype):
        """ Validate and set the ImageType attribute.
            The image type must be in the FolderList dictionary. """
        if imagetype in FolderList:
            self._ImageType = imagetype # OK to accept this image type.
            self.Log("astrocamera.SetImageType(",imagetype,") new image type set.",terminal=False)
        else: # ImageType has nowhere to go.
            self.Log("astrocamera.SetImageType(",imagetype,") is not recognised. Must be in FolderList. Defaulting to 'light'.",terminal=False)
            self._ImageType = 'light'
    
    def GetImageType(self):
        return self._ImageType

    def SetTimelapse(self,seconds):
        """ Set timelapse delay and initiate timer. """
        if seconds == None or seconds <= 0.0:
            self.TimelapseTimer = None
            self.TimelapseSeconds = 0.0
        else:
            self.TimelapseTimer = timer(period=seconds)
            self.TimelapseSeconds = seconds

    def TimelapseDue(self):
        """ Return TRUE if the camera timelapse is active and due.
            Return TRUE if the camera timelapse is not active at all. 
            Return FALSE if the camera timelapse is active but not due. """
        if self.TimelapseTimer == None:
            return True # No timer, so always due.
        else:
            return self.TimelapseTimer.Due() # Use the real timer.

    def Reset(self):
        """ Reset camera settings at the beginning of a new session. """
        self.LastImageDateTime = None # When was the latest image taken?
        self.Lastjpg = None # The filename of the last jpg taken (if saved)
        self.Previewjpg = None # The filename of the last preview image generated. 
        self.CvImage = None # openCV image buffer. Loaded explicitly when needed.
        self.CaptureStart = None # Timestamp when image capture started. Used to detect camera hanging.
        self.CaptureEnd = None # Timestamp when image capture completed. Used to detect camera hanging.
        self.BatchCount = 0 # How many photos taken in the current observation batch?
        CameraWindow.Print(NowHMS() + " astrocamera.Reset")
        
    def CaptureStartAge(self):
        """ Return a timedelta object showing how long ago the last image capture began. 
            Returns None if no image captured yet. """
        result = None
        if self.CaptureStart != None:
            result = NowUTC() - self.CaptureStart
        return result
    
    def CaptureStartAgeSeconds(self):
        """ Number of seconds since last camera capture began.
            Returns None if no image. """
        result = self.CaptureStartAge()
        if result != None:
            result = result.total_seconds()
        return result

    def LastImageAge(self):
        """ Return a timedelta object with the age of the last image. 
            Returns None if no image captured yet. """
        result = None
        if self.LastImageDateTime != None:
            result = NowUTC() - self.LastImageDateTime
        return result

    def LastImageAgeSeconds(self):
        """ Return age of last image in seconds.
            Returns None if no image. """
        result = self.LastImageAge()
        if result != None:
            result = result.total_seconds()
        return result

    def CameraFault(self):
        """ Return true if it looks like the camera has hung. 
            This usually requires an entire reboot of the RPi.
            The hang is somewhere in the camera subsystem.
            Suspect it is related to memory problems, but cause or effect? 
            NOTE: There are overheads in the camera libraries, the camera takes much longer than just the 'exposure' time to complete an image. 
                  Typically a call to raspistill will take at least DOUBLE the exposure time to complete a capture."""
        result = False # no fault detected yet.
        if self.CaptureStart != None: # An attempt has been made.
            if self.CaptureEnd == None or self.CaptureEnd <= self.CaptureStart: # It hasn't completed yet.
                # Decide upon a sensible 'failure' delay to accept. At least 300seconds(5 minutes)
                # We have to be very generous here because this is a linux system and can sometimes pause a lot!
                faultdelay = max(self.ExposureSeconds * 5,300)
                if self.CaptureStartAgeSeconds() > faultdelay: # It has been running too long.
                    result = True # It looks like there's something wrong.
                    line = "astrocamera.CameraFault: Image capture time " + str(round(self.CaptureStartAgeSeconds(),1)) + "s is too long. The camera may have hung. Consider power cycling the RPi."
                    CameraWindow.Print(NowHMS() + ' ' + line)
                    self.Log("astrocamera.CaptureStart",self.CaptureStart,terminal=False)
                    self.Log("astrocamera.CaptureEnd",self.CaptureStart,terminal=False)
                    self.Log("astrocamera.faultdelay",faultdelay,terminal=False)
                    self.Log("astrocamera.CaptureStartAgeSeconds",self.CaptureStartAgeSeconds(),terminal=False)
                    self.Log("astrocamera.LastImageDateTime",self.LastImageDateTime,terminal=False)
                    self.Log(line,level='error')
        return result

    def StoreImageBuffer(self,imagebuffer):
        """ Given an OpenCV image buffer, store it as the latest captured image. """
        # Load image from a PIL buffer into the class. And at the same time convert into grayscale OpenCV buffer too.
        self.Log("astrocamera.StoreImageBuffer: Begin",terminal=False)
        self.CvImage = imagebuffer.copy() # Make sure you don't just copy a pointer to the same buffer, you'll overwrite other activities if you do!
        self.Log("astrocamera.StoreImageBuffer: End",terminal=False)

    def SetMode(self,mode):
        """ Change the sensor mode. 
            This may change the format and other characteristics of the images recorded. 
            It does not have any impact on the RAW data collected. """
        self.Sensor._SetMode(mode) # Update the sensor to the new mode first.
        self.ModeChange() # Update dependent values in the camera to reflect the new change. 
        self.Log("astrocamera.SetMode(): Mode " + str(mode) + " selected.",terminal=False)
        self.Log("astrocamera.SetMode(): Sensor pixel dimensions now: " + str(self.Sensor.PixelWidth) + "x" + str(self.Sensor.PixelHeight),terminal=False)
        self.Log("astrocamera.SetMode(): Pixels per degree are now: " + str(self.PixelsPerFovDegreeWidth) + "x" + str(self.PixelsPerFovDegreeHeight),terminal=False)
        self.Log("astrocamera.SetMode(): Seconds per pixel is now: " + str(self.SecondsPerPixel),terminal=False)

    def ModeChange(self):
        """ Call this whenever the sensor changes mode. """
        self.PixelsPerFovDegreeWidth = int(self.Sensor.PixelWidth / self.Lens.FovHorizontal) # Conversion value between ANGLE and PIXELS.
        self.PixelsPerFovDegreeHeight = int(self.Sensor.PixelHeight / self.Lens.FovVertical) # Conversion value between ANGLE and PIXELS.
        self.ExposureSeconds = 1.0 # Default 1 second exposure per frame for astro photos.
        self.Log("astrocamera.ModeChange(): PixelsPerDegree Width/Height " + str(self.PixelsPerFovDegreeWidth) + " / " + str(self.PixelsPerFovDegreeHeight),terminal=False)
        ArcSecondsPerWidth = self.Lens.FovHorizontal * 60 * 60
        ArcSecondsPerPixel = float(ArcSecondsPerWidth) / self.Sensor.PixelWidth
        self.Log("astrocamera.ModeChange(): Arcseconds per pixel: " + str(round(ArcSecondsPerPixel,3)),terminal=False)
        FullRotationAS = 360 * 60 * 60 # Arcseconds in an entire rotation.
        SecondsPerAS = 24 * 60 * 60 / float(FullRotationAS) # How many seconds does a single arcsecond last before earth rotation has moved on.
        self.Log("astrocamera.ModeChange(): Seconds per arcsecond: " + str(SecondsPerAS),terminal=False)
        self.SecondsPerPixel = float(ArcSecondsPerPixel) * SecondsPerAS
        self.Log("astrocamera.ModeChange(): Static camera image will blur if exposure exceeds " + str(round(self.SecondsPerPixel,3)) + "seconds.",terminal=False)
        self.Log("astrocamera.ModeChange(): Mode " + str(self.Sensor.Mode) + " selected.",terminal=False)

    def CleanupLastjpg(self):
        """ Call this to delete the disc copy of the last jpg file that was generated.
            It also clears the reference to the file that has been deleted. """
        self.Log("astrocamera.CleanupLastjpg()",terminal=False)
        if self.Lastjpg != None:
            cmd = "rm " + self.Lastjpg
            # temp = osCmd(cmd)
            osCmd(cmd)
            self.Lastjpg = None # Clear the saved filename.

    def FakeField(self,srcimg): # Generate fake field noise.
        """ Create a small blank image and add some fake electronic noise to it. 
            Then enlarge the image to match the size of the target image. 
            Then combine the two images.
            Return the combined image. """
        self.Log("astrocamera.FakeField: Simulating electrical field noise.",terminal=False)
        fieldimg = np.zeros((int(SensorInUse.PixelHeight/100),int(SensorInUse.PixelWidth/100),3),np.uint16) # Shrink to 1% of original size.
        fieldimg = cv2.circle(fieldimg,(fieldimg.shape[1],fieldimg.shape[0]),int(fieldimg.shape[1]/3),BGRVeryDarkRed,thickness=-1) # Simulate an electric field shadow.
        fieldimg = cv2.resize(fieldimg,(srcimg.shape[1],srcimg.shape[0])) # Scale back up to full image size.
        fieldimg = np.add(fieldimg,srcimg)
        fieldimg = np.clip(fieldimg,0,255).astype(np.uint8) # Clip to uint8 values.
        # cv2.imwrite(FolderList['temp'] + "FakeField.jpg",fieldimg)
        return fieldimg

    def FakeMeteor(self,srcimg): # Generate fake meteor streak
        """ Add a random meteor like streak to an image. """
        self.Log("astrocamera.FakeMeteor: Simulating meteor like streak across the image.",terminal=False)
        meteorimg = np.zeros((int(SensorInUse.PixelHeight),int(SensorInUse.PixelWidth),3),np.uint16) # Shrink to 1% of original size.
        length = 0
        while length < 500: # Make the meteor streak long enough to see.
            x1 = random.randint(0,SensorInUse.PixelWidth)
            x2 = random.randint(0,SensorInUse.PixelWidth)
            y1 = random.randint(0,SensorInUse.PixelHeight)
            y2 = random.randint(0,SensorInUse.PixelHeight)
            length = int(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
        meteorimg = cv2.line(meteorimg, (x1, y1), (x2, y2), (255,255,255), 2) # Mark the line on the image.
        meteorimg = np.add(meteorimg,srcimg)
        meteorimg = np.clip(meteorimg,0,255).astype(np.uint8) # Clip to uint8 values.
        # cv2.imwrite(FolderList['temp'] + "FakeMeteor.jpg",meteorimg)
        return meteorimg

    def FakeNoise(self,srcimg): # Generate fake image noise.
        """ Create a small blank image and add some fake image noise to it. 
            Return the combined image. """
        self.Log("astrocamera.FakeNoise: Simulating image sensor noise.",terminal=False)
        fieldimg = np.random.randint(0,25,(SensorInUse.PixelHeight,SensorInUse.PixelWidth,3),np.uint16)
        fieldimg = np.add(fieldimg,srcimg)
        fieldimg = np.clip(fieldimg,0,255).astype(np.uint8) # Clip to uint8 values.
        # cv2.imwrite(FolderList['temp'] + "FakeNoise.jpg",fieldimg)
        return fieldimg

    def FakePollution(self,srcimg): # Generate fake light pollution.
        """ Create a small blank image and add some fake light pollution to it. 
            Return the combined image. """
        self.Log("astrocamera.FakePollution: Simulating light pollution.",terminal=False)
        ThickestValue = [50,50,50] # How thick is the haze at the horizon? (BGR) (Scale 0-255, higher values = more pollution)
        ThinnestValue = [10,10,10] # How thick is the haze above PollutionMaxAlt? (BGR)  (Scale 0-255, higher values = more pollution)
        PollutionMaxAlt = 15 # Degrees. Pollution fades to ThinnestValue at this altitude above the horizon.
        HazeChange = [] # What's the delta between the two limits?
        for j in range(len(ThickestValue)):
            HazeChange.append(ThickestValue[j] - ThinnestValue[j])
        AveValue = [] # What's the average between the two limits?
        for j in range(len(ThickestValue)):
            AveValue.append(int((ThickestValue[j] - ThinnestValue[j])/2))
        self.Log("astrocamera.FakePollution: HazeChange",HazeChange,terminal=False)
        CentreAlt, CentreAz = CurrentAltAz() # What is the alt/az location of the centre of the image?
        self.Log("astrocamera.FakePollution: CentreAltAz",CentreAlt, CentreAz,terminal=False)
        RelAlt, RelAz = RelativeAltAz(0,CentreAz,CentreAlt,CentreAz) # Image pixel height of horizon. (Thickest pollution level).
        _, HorizonY = PlotRelativeAltAz(RelAlt,RelAz,SensorInUse.PixelHeight,SensorInUse.PixelWidth) # Covert to pixel height.
        self.Log("astrocamera.FakePollution: HorizonAltAz",RelAlt,RelAz,HorizonY,terminal=False)
        RelAlt, RelAz = RelativeAltAz(PollutionMaxAlt,CentreAz,CentreAlt,CentreAz) # Image pixel height of pollution upper limit. (Thinnest pollution level)
        _, TopY = PlotRelativeAltAz(RelAlt,RelAz,SensorInUse.PixelHeight,SensorInUse.PixelWidth) # Covert to pixel height.
        self.Log("astrocamera.FakePollution: TopAltAz",RelAlt,RelAz,TopY,terminal=False)
        self.Log("astrocamera.FakePollution: Horizon height",HorizonY,"px",terminal=False)
        self.Log("astrocamera.FakePollution: Top height",TopY,"px, (PollutionMaxAlt",PollutionMaxAlt,"deg)",terminal=False)
        fieldimg = np.zeros((SensorInUse.PixelHeight,SensorInUse.PixelWidth,3),np.uint16) # Black image.

        fieldimg[:,:] = np.array(ThinnestValue).astype(np.uint16) # Set ALL pixels to the thinnest haze value by default.

        if HorizonY < SensorInUse.PixelHeight: # Horizon is in range.
            # Fill everything below horizon with Thickest pollution value.
            for i in range(max(0,HorizonY),SensorInUse.PixelHeight):
                fieldimg[i,:] = np.array(ThickestValue).astype(np.uint16)

        # Now to calculate the gradient values where the haze builds up as it approaches the horizon. 
        
        # Remember that images count rows from top down.
        rowspan = HorizonY - TopY # How many rows to fill with the gradient if the image was infinitely tall?

        # Constrain the Top of the gradient to within the image boundary.
        if TopY < 0: startrow = 0
        elif TopY > SensorInUse.PixelHeight: startrow = SensorInUse.PixelHeight
        else: startrow = TopY

        # Constrain the Horizon to within the image boundary.
        if HorizonY < 0: endrow = 0
        elif HorizonY > SensorInUse.PixelHeight: endrow = SensorInUse.PixelHeight
        else: endrow = HorizonY

        if startrow != endrow: # There's a band of the image that needs the haze gradient calculating.
            for i in range(startrow,endrow): # Process each row of the gradient in turn.
                GradientPoint = (i - TopY) / rowspan # How thick is the haze? Increasing in thickness towards the horizon.
                NewValue = []
                for j in range(len(ThinnestValue)): # Calculate strength of each color channel in turn. BGR.
                    tV = ((ThickestValue[j] - ThinnestValue[j]) * GradientPoint) + ThinnestValue[j]
                    NewValue.append(int(tV))
                fieldimg[i,:] = np.array(NewValue).astype(np.uint16) 

        # TODO: Add some random noise to the pattern. +/- Thinnest value at random to the entire image.
        
        self.Log("astrocamera.FakePollution: Gradient span",startrow,endrow,rowspan,terminal=False)

        # Pollution is a gradient at a fixed altitude parallel to the horizon.
        fieldimg = np.add(fieldimg,srcimg) 
        fieldimg = np.clip(fieldimg,0,255).astype(np.uint8) # Clip to uint8 values.
        # cv2.imwrite(FolderList['temp'] + "FakePollution.jpg",fieldimg)
        return srcimg # *Q* This should be 'fieldimg' to return the calculated image when development is OK.

    def FakePhoto(self,outputfile,astrotime=None):
        # Generate false disc file to simulate a photograph being captured. 
        self.Log("astrocamera.FakePhoto: Simulating photo capture (",outputfile,")",terminal=False)
        if self.ImageGenerator == None or Parameters.FakeStars == False: image = NewBlankImage() # No image generator, or not allowed to fake the stars.
        else: image = self.ImageGenerator(color=True,MinMagnitude=10,astrotime=astrotime) # Handle to CreateTargetImage function
        if Parameters.FakeNoise: # Simulate fake image noise.
            image = self.FakeNoise(image)
        if Parameters.FakeField: # Simulate fake electrical field noise in the image.
            image = self.FakeField(image)
        if Parameters.FakePollution: # Simulate fake light pollution.
            image = self.FakePollution(image)
        if Parameters.FakeMeteor and random.randint(0,100) < Parameters.FakeMeteorPercent: # 2% of images get fake meteor streaks in them.
            image = self.FakeMeteor(image)
        try:
            cv2.imwrite(outputfile,image)
        except Exception as e:
            self.Log("astrocamera.FakePhoto failed to write:",outputfile,level='error')
            self.ReportException(e,comment='astrocamera.FakePhoto cv2.imwrite')
        self.Log("astrocamera.FakePhoto: Completed.",terminal=False)
        return True

    def FakeDark(self,outputfile):
        # Generate false disc file to simulate a photograph being captured. 
        self.Log("astrocamera.FakeDark: Simulating dark photo capture (",outputfile,")",terminal=False)
        image = NewBlankImage()
        if Parameters.FakeNoise: # Simulate fake image noise.
            image = self.FakeNoise(image)
        if Parameters.FakeField: # Simulate fake electrical field noise in the image.
            image = self.FakeField(image)
        try:
            cv2.imwrite(outputfile,image)
        except Exception as e:
            self.Log("astrocamera.FakeDark failed to write:",outputfile,level='error')
            self.ReportException(e,comment='astrocamera.FakeDark cv2.imwrite')
        self.Log("astrocamera.FakeDark: Completed.",terminal=False)
        return True

    def FakeDelay(self,camera_options):
        """ Extract the exposure time from camera options and pause processing
            to mimic the actual amount of time the camera would take. """
        optlist = camera_options.split(' ')
        for i,opt in enumerate(optlist):
            if opt == '-ss': # Found exposure time.
                delay = float(optlist[i + 1]) * 2 # Find the microsecond exposure time and double it to mimic camera.
                delay = delay / 1000000 # Convert from microseconds to seconds.
                if delay > 5: # Don't bother for less than this time. Processing overhead already reaches this probably.
                    time.sleep(delay)
                break
        return True

#    def CaptureSet(self,file_root,batch_size,camera_options,tempfile=False,terminal=True,cleanup=True,astrotime=None,stacker=None):
    def CaptureSet(self,file_root,batch_size,camera_options,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take batch of photos. Uses CaptureSetFull or CaptureSetFast depending upon configuration. """
        if self.FastImageCapture: # Just capture the images, don't process them further. Saves time during observation.
            #result = self.CaptureSetFast(file_root,batch_size,camera_options,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime,stacker=stacker)
            result = self.CaptureSetFast(file_root,batch_size,camera_options,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime)
        else: # Capture images AND process them, splitting them out into the right file types. Slower during observation.
            #result = self.CaptureSetFull(file_root,batch_size,camera_options,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime,stacker=stacker)
            result = self.CaptureSetFull(file_root,batch_size,camera_options,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime)
        return result
    
#    def CaptureSetFull(self,file_root,batch_size,camera_options,tempfile=False,terminal=True,cleanup=True,astrotime=None,stacker=None):
    def CaptureSetFull(self,file_root,batch_size,camera_options,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take a batch of photos... The batch can be interrupted by sending a BREAK signal to the routine. 
            cleanup = True. means that intermediate files (.jpg) are deleted when finished with. 
                      False. means that the intermediate files (.jpg) are retained for the calling function to deal with.
                      astrocamera.Lastjpg contains the filename of the .jpg file generated. 
            tempfile = True. Means that a single temporary filename is used each time.
            terminal=True. Means that the progress message is shown on the terminal.
            astrotime = the timestamp of the image to be generated if we're faking the result.
            stacker = a handle to a live image stacker object if we're live stacking. """
        result = True
        self.Log("astrocamera.CaptureSetFull(): Capturing " + str(batch_size) + " images...",terminal=False)
        dt_start = NowUTC()
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(2) # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile: outputfile = file_root + 'temp.jpg' # This is the 'intermediate' jpg generated by the camera. *Q* Delete when finished.
            else: outputfile = file_root + UtcTimeStamp() + "_" + frame + '.jpg' # This is the 'intermediate' jpg generated by the camera.
            self.Log("astrocamera.CaptureSetFull(): Capturing " + outputfile + "...",terminal=False)
            cmd = 'raspistill -o ' + outputfile + ' ' + camera_options # Use raspistill to take the photo.
            remoterestarts = Mctl.RemoteRestarts # If this changes during exposure, the microcontroller reset and we should reject the image.
            rejectimage = False # Set to 'true' if there's a reason to reject the image.
            Led3.On()
            self.CaptureStart = NowUTC()
            #self.AstrotimeStart = ts.now()
            if Parameters.CameraEnabled: # Camera is in use. Take real photo.
                #temp = osCmd(cmd,output='none')
                osCmd(cmd,output='none')
            else: # Camera is not in use. Generate fake photo.
                self.Log("astrocamera.CaptureSetFull(): About to call FakePhoto.",terminal=False)
                tr = False # Fake image generation failed unless we are told otherwise.
                imty = self.GetImageType() # What type of image are we faking?
                if imty == 'dark': tr= self.FakeDark(outputfile=outputfile) # Fake a dark frame.
                else: tr = self.FakePhoto(outputfile=outputfile,astrotime=astrotime) # Fake a light frame.
                if not tr: # Image generation failed.
                    self.Log("astrocamera.CaptureSetFull(): Fake image call failed (",imty,").",terminal=True,level='error')
                else: # Fake the expected exposure time if a real image was being captured.
                    self.FakeDelay(camera_options)
                self.Log("astrocamera.CaptureSetFull(): Returned from FakePhoto.",terminal=False)
            self.CaptureEnd = NowUTC()
            self.AstrotimeEnd = ts.now()
            Led3.Off()
            self.Log("astrocamera.CaptureSetFull(): Capture complete. (",(self.CaptureEnd - self.CaptureStart).total_seconds(), "s).",terminal=False)
            if remoterestarts != Mctl.RemoteRestarts: # Microcontroller reset during exposure.
                self.Log('astrocamera.CaptureSetFull(): Microcontroller restarted during exposure. Reject',outputfile,level='warning',terminal=False)
                CameraWindow.Print(NowHMS() + " Motors reset during exposure.") # Just the filename.
                ErrorWindow.Print(NowHMS() + " Motors reset during exposure.") # Just the filename.
                rejectimage = True # We should reject this image.
            CameraWindow.Print(NowHMS() + " " + outputfile.split('/')[-1]) # Just the jpg filename.
            if rejectimage: # There was reason to reject the image for some cause.
                self.Log("astrocamera.CAptureSetFast(): Image should be rejected.",terminal=False)
            self.Lastjpg = outputfile # The camera can remember this file as the 'last jpg taken'
            self.Log("astrocamera.CaptureSetFull(): Load image from " + outputfile,terminal=False)
            cvimage = cv2.imread(outputfile,cv2.IMREAD_COLOR) # OpenCV format.
            if type(cvimage) == type(None): # imread failed.
                self.Log("astrocamera.CaptureSetFull(): imread of",outputfile,"failed.",terminal=False)
            self.StoreImageBuffer(cvimage) # Retain the openCV format image buffer in the camera object.
            self.LastImageDateTime = NowUTC() # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.Log("astrocamera.CaptureSetFull(): Image loaded.",terminal=False)
            if " -r " in camera_options and Parameters.CameraEnabled: # The jpg contains RAW data in the file tags, extract it. Convert it.
                # Convert to RAW. We have to extract RAW for either .dng or .fits files to be saved.
                self.Log("astrocamera.CaptureSetFull(): Converting to RAW (.DNG) file...",terminal=False)
                dngname = outputfile.replace('.jpg','.dng')
                try:
                    PiDNG.convert(outputfile) # Convert the saved .jpg file into the raw .dng format.
                except Exception as e:
                    CamLog.RaiseException(e,comment='astrocamera.CaptureSetFull(): PiDNG.convert failed.')
                self.Log("astrocamera.CaptureSetFull(): Converted to RAW (.DNG) file.",terminal=False)
                # Cleanup. Remove any intermediate files that are nolonger needed.
                if self.CameraSaveJpg: # We should save 'JUST' the jpg data, effectively stripping out the embedded RAW data 
                    cv2.imwrite(outputfile, self.CvImage) # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                else: # We're only saving the RAW data, so just delete the original jpg file.
                    self.Log("astrocamera.CaptureSetFull(): Deleting intermediate .jpg file...",terminal=False)
                    self.CleanupLastjpg() # We've finished with the original .jpg on disc.
                if not self.CameraSaveDng: # We don't need to keep the .dng file anymore.
                    self.Log("astrocamera.CaptureSetFull(): DNG nolonger needed.",terminal=False)
                    cmd = 'rm ' + dngname
                    #temp = osCmd(cmd,output='log')
                    osCmd(cmd,output='log')
                else:
                    CameraWindow.Print(NowHMS() + " " + dngname.split('/')[-1]) # Just the dng filename.
            if tempfile: # Delete the temporary file.
                cmd = 'rm ' + outputfile
                #temp = osCmd(cmd,output='log')
                osCmd(cmd,output='log')
            # Estimate ETA. If we're looping through a batch of photos.
            if batch_size > 1:
                dt_now = NowUTC() # Current time.
                td_elapsed = dt_now - dt_start # Elapsed time.
                dt_eta = dt_start + (batch_size * td_elapsed / (i + 1)) # Estimate completion time.
                pc_complete = int(100 * (i + 1.0) / batch_size) # Estimate how far through the batch of photos we are.
                self.Log("astrocamera.CaptureSet: " + str(i + 1) + " of " + str(batch_size) + " (" + str(pc_complete) + "%), Disc: " + str(int(ImageStorageMonitor.FreeMegaBytes())) + "Mb, ETA: " + str(dt_eta).split(" ")[1].split(".")[0],terminal=terminal)
                if i < batch_size - 1: # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print (textcolor.cursorup() + textcolor.cursorup()) # Stay on the same line for the CaptureSet message to the terminal.
            if ImageStorageMonitor.DiscOK() != True: # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.Log("astrocamera.CaptureSetFull(): Out of disc space. Stopping!",level='error')
                result = False
                break
        self.Log("astrocamera.CaptureSetFull(): Completed",terminal=False)
        return result

    #def CaptureSetFast(self,file_root,batch_size,camera_options,tempfile=False,terminal=True,cleanup=True,astrotime=None,stacker=None):
    def CaptureSetFast(self,file_root,batch_size,camera_options,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take a batch of photos... The batch can be interrupted by sending a BREAK signal to the routine. 
            This just captures the combined JPG & DNG data file. It does not perform conversion to other file types.
            This is testing if it improves performance for image capture by delaying processing until the observation is over.
            tempfile = True. Means that a single temporary filename is used each time.
            terminal=True. Means that the progress message is shown on the terminal.
            astrotime = the timestamp of the image to be generated if we're faking the result.
            stacker = a handle to a live image stacker object if we're live stacking. """
        result = True
        self.Log("astrocamera.CaptureSetFast(): Capturing " + str(batch_size) + " images...",terminal=False)
        dt_start = NowUTC()
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(2) # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile: outputfile = file_root + 'temp.jpg' # This is the 'intermediate' jpg generated by the camera.
            else: outputfile = file_root + UtcTimeStamp() + "_" + frame + '.jpg' # This is the 'intermediate' jpg generated by the camera.
            self.Log("astrocamera.CaptureSetFast(): Capturing " + outputfile + "...",terminal=False)
            cmd = 'raspistill -o ' + outputfile + ' ' + camera_options # Use raspistill to take the photo.
            remoterestarts = Mctl.RemoteRestarts # If this changes during exposure, the microcontroller reset and we should reject the image.
            rejectimage = False # Set to 'true' if there's a reason to reject the image.
            Led3.On()
            self.CaptureStart = NowUTC()
            #self.AstrotimeStart = ts.now()
            if Parameters.CameraEnabled: # Camera is in use. Take real photo.
                #temp = osCmd(cmd,output='none')
                osCmd(cmd,output='none')
            else: # Camera is not in use. Generate fake photo.
                self.Log("astrocamera.CaptureSetFast(): About to call FakePhoto.",terminal=False)
                tr = False # Fake image generation failed unless we are told otherwise.
                imty = self.GetImageType() # What type of image are we faking?
                if imty == 'dark': tr= self.FakeDark(outputfile=outputfile) # Fake a dark frame.
                else: tr = self.FakePhoto(outputfile=outputfile,astrotime=astrotime) # Fake a light frame.
                if not tr: # Image generation failed.
                    self.Log("astrocamera.CaptureSetFast(): Fake image call failed (",imty,").",terminal=True,level='error')
                else: # Fake the expected exposure time if a real image was being captured.
                    self.FakeDelay(camera_options)
                self.Log("astrocamera.CaptureSetFast(): Returned from FakePhoto.",terminal=False)
            self.CaptureEnd = NowUTC()
            self.AstrotimeEnd = ts.now()
            Led3.Off()
            self.Log("astrocamera.CaptureSetFast(): Capture complete. (",(self.CaptureEnd - self.CaptureStart).total_seconds(), "s).",terminal=False)
            if remoterestarts != Mctl.RemoteRestarts: # Microcontroller reset during exposure.
                self.Log('astrocamera.CaptureSetFast(): Microcontroller restarted during exposure. Reject',outputfile,level='warning',terminal=False)
                CameraWindow.Print(NowHMS() + " Motors reset during exposure.") # Just the filename.
                ErrorWindow.Print(NowHMS() + " Motors reset during exposure.") # Just the filename.
                rejectimage = True # We should reject this image.
            CameraWindow.Print(NowHMS() + " " + outputfile.split('/')[-1]) # Just the jpg filename.
            if rejectimage: # There was reason to reject the image for some cause.
                self.Log("astrocamera.CAptureSetFast(): Image should be rejected.",terminal=False)
            self.Lastjpg = outputfile # The camera can remember this file as the 'last jpg taken'
            self.Log("astrocamera.CaptureSetFast(): Load image from " + outputfile,terminal=False)
            cvimage = cv2.imread(outputfile,cv2.IMREAD_COLOR) # OpenCV format.
            if type(cvimage) == type(None): # imread failed.
                self.Log("astrocamera.CaptureSetFast(): imread of",outputfile,"failed.",terminal=False)
            self.StoreImageBuffer(cvimage) # Retain the openCV format image buffer in the camera object.
            self.LastImageDateTime = NowUTC() # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.Log("astrocamera.CaptureSetFast(): Image loaded.",terminal=False)
            # Estimate ETA. If we're looping through a batch of photos.
            if batch_size > 1:
                dt_now = NowUTC() # Current time.
                td_elapsed = dt_now - dt_start # Elapsed time.
                dt_eta = dt_start + (batch_size * td_elapsed / (i + 1)) # Estimate completion time.
                pc_complete = int(100 * (i + 1.0) / batch_size) # Estimate how far through the batch of photos we are.
                self.Log("astrocamera.CaptureSetFast(): " + str(i + 1) + " of " + str(batch_size) + " (" + str(pc_complete) + "%), Disc: " + str(int(ImageStorageMonitor.FreeMegaBytes())) + "Mb, ETA: " + str(dt_eta).split(" ")[1].split(".")[0],terminal=terminal)
                if i < batch_size - 1: # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print (textcolor.cursorup() + textcolor.cursorup()) # Stay on the same line for the CaptureSet message to the terminal.
            if ImageStorageMonitor.DiscOK() != True: # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.Log("astrocamera.CaptureSetFast(): Out of disc space. Stopping!",level='error')
                result = False
                break
        self.Log("astrocamera.CaptureSetFast(): Completed",terminal=False)
        return result

    def ProcessImageFiles(self):
        """ If image conversions were not done during capture, this can find and convert all the 
            image files currently in storage. This is used if CaptureSetFast was used to gather 
            images as quickly as possible. 
            This will convert all image files found the have the characteristics of a jpg with embedded raw data. """
        self.Log("astrocamera.ProcessImageFiles(): Starting",terminal=True)
        rawfilesize = 1024 * 1024 * 20 # Files containing raw data are quite large, set the threshold at 20Mb
        # Find all image files that need converting.
        rootfolder = FolderList['imageroot'] # This is the parent data folder for all Pilomar images.
        allfiles = glob.glob(rootfolder + '**/*.jpg', recursive=True) # Every jpg in every folder and subfolder.
        files = [] # Cleaned list of files to handle.
        folders = ['flat','bias','light','darkflat','dark'] # Which subfolders do we want?
        for file in allfiles: # Go through all the .jpg files found.
            for folder in folders: # Check all the image folder/types.
                temp = '/' + folder + '/' + folder + '_' # Key to an image file we are interested in.
                if temp in file: # This is an image/type that we should consider converting.
                    # How big is the file? Large ones need converting.
                    if os.stat(file).st_size > rawfilesize: # File is large enough to convert.
                        files.append(file) # Add to list of files to process.
                    break # No need to check anything else in the list.
        # Convert them.
        filecount = len(files)
        self.Log("astrocamera.ProcessImageFiles(): Found", filecount, "files to process.",terminal=True)
        if filecount > 0:
            for file in files:
                print(file)
                # Load jpg data into temporary buffer.
                tempimagebuffer = cv2.imread(file,cv2.IMREAD_COLOR)
                if type(tempimagebuffer) == type(None): # imread failed.
                    self.Log("astrocamera.ProcessImageFiles: imread",file,"failed.",terminal=False)
                else: # imread was successful.
                    self.Log("astrocamera.ProcessImageFiles: Converting to RAW (.DNG) file...",terminal=False)
                    if self.CameraSaveDng: # We don't need to keep the .dng file anymore.
                        try:
                            PiDNG.convert(file) # Convert the saved .jpg file into the raw .dng format. The .dng filename is automatically generated.
                        except Exception as e:
                            CamLog.ReportException(e,comment='astrocamera.ProcessImageFiles() error when converting to DNG file.')
                    # Replace the .jpg file with a simpler file, or delete it completely.
                    if self.CameraSaveJpg: # We should save 'JUST' the jpg data, effectively stripping out the embedded RAW data 
                        cv2.imwrite(file, tempimagebuffer) # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else: # We're only saving the RAW data, so just delete the original jpg file.
                        self.Log("astrocamera.ProcessImageFiles: Deleting intermediate .jpg file...",terminal=False)
                        cmd = 'rm ' + file
                        #temp = osCmd(cmd,output='log')
                        osCmd(cmd,output='log')
        else:
            print(textcolor.yellow("No suitable unprocessed files were found."))
            print("- There is no RAW data in simulated images (Is the camera disabled?)")
            print("- There must still be observation images on disc to process.")
        self.Log("astrocamera.ProcessImageFiles(): Done",terminal=True)
        return True

    def ClearCameraOptions(self):
        """ Clear the camera options list. """
        self.Log("astrocamera.ClearCameraOptions",terminal=False)
        self.CameraOptions = '' # Empty the options list.

    def AddCameraOption(self,NewOption):
        """ Add an option to the camera option list. 
            This gives possibility to validate options as they are added. """
        self.Log("astrocamera.AddCameraOption:",NewOption,terminal=False)
        NewOption = NewOption.strip(' ') + ' ' # Make sure there's a single separator character after the option.
        NewKey = NewOption.split(' ')[0] # What is the option key we are setting?
        # Split all the existing options into a list.
        # OptionListEntries = ['-' + a for a in OptionList.split('-')]
        OptionListEntries = self.CameraOptions.split('-')
        for OLE in OptionListEntries:
            OLE = '-' + OLE # Add the lost '-' tag back to each entry.
        found = False
        # If the option is already in the list, update it to the new value.
        for OLE in OptionListEntries:
            if OLE.split(' ')[0] == NewKey:
                found = True
                OLE = NewOption
                break
        if not found: # If the option is NOT in the list, add it now.
            OptionListEntries.append(NewOption)
        # Construct the new version of the option list ready for returning.
        self.CameraOptions = ''
        for OLE in OptionListEntries:
            self.CameraOptions += OLE
        self.Log("astrocamera.AddCameraOption: New list:",self.CameraOptions,terminal=False)

    def DelCameraOption(self,DelOption):
        """ Remove an option from the camera option list. """
        self.Log("astrocamera.DelCameraOption:",DelOption,terminal=False)
        DelKey = DelOption.split(' ')[0] # What is the option key we are setting?
        # Split all the existing options into a list.
        # OptionListEntries = ['-' + a for a in OptionList.split('-')]
        OptionListEntries = self.CameraOptions.split('-')
        for OLE in OptionListEntries:
            OLE = '-' + OLE # Add the lost '-' tag back to each entry.
        # Construct the new version of the option list ready for returning but ignore the deleted option.
        self.CameraOptions = ''
        for OLE in OptionListEntries:
            if OLE.split(' ')[0] != DelKey:
                self.CameraOptions += OLE
        self.Log("astrocamera.DelCameraOption: New list:",self.CameraOptions,terminal=False)
            
    def ContainsMeteors(self,image):
        """ Return TRUE if meteors or aircraft trails are detected in an image. """
        if len(self.LineDetection(image)) > 0: return True
        else: return False
        
    def TakePhoto(self,batch_size,terminal=True):
        """ Make an observation. This is a LIGHT image of the actual object under observation. """
        self.Log("astrocamera.TakePhoto: Begin",terminal=False)
        ExposureMicroseconds = self.ExposureSeconds * 1000000
        self.SetImageType('light') # Tell the camera we are taking flat photos.
        FileRoot=FolderList.get('light') + 'light_'
        CameraOptions = ''
        CameraOptions += '-ex off ' # Exposure control off.
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-ss ' + str(ExposureMicroseconds) + ' ' # Use the global SHUTTER time to match the DARK and LIGHT frames.
        if self.CameraSaveDng and not '-r ' in CameraOptions: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraOptions += '-r ' # Raw is appended to JPEG file. Needs extracting later.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        self.LastLightOptions = CameraOptions # keep a note of the exposure options, it's reported in the preview images.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions,terminal=terminal,cleanup=False)
        if not result:
            self.Log("astrocamera.TakePhoto: CaptureSet failed.",level='error')
        self.Log("astrocamera.TakePhoto: Complete",terminal=False)
        return result

    def LineDetection(self,imagebuffer):
        """ Detect lines (satellites, meteors). """
        # Code based upon https://www.meteornews.net/2020/05/05/d64-nl-meteor-detecting-project/
        # Make a gray-scale copy and save the result in the variable 'gray'
        gray = cv2.cvtColor(imagebuffer, cv2.COLOR_BGR2GRAY)
        # Apply blur and save the result in the variable 'blur'
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        # Apply the Canny edge algorithm
        canny = cv2.Canny(blur, 100, 200, 3)
        filename = '/home/pi/pilomar/temp/plane-canny.jpg'
        cv2.imwrite(filename,canny) # Save the marked up image.
        # The Hough line detection algorithm.
        lines = cv2.HoughLinesP(canny, 1, np.pi/180, 25, minLineLength=50, maxLineGap=5)
        linereturn = [] # The list of selected lines that will be returned.
        longest = 0 # Length of longest line.
        if type(lines) != type(None): # We have something to process.
            for i,line in enumerate(lines): # Check each detected line in turn.
                x1, y1, x2, y2 = line[0] # Coordinates of each end of the line.
                length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) # Length of the line.
                if length < 10: continue # Too short.
                self.Log("astrocamera.LineDetection: Line", i, ",", line[0], ", length", length,terminal=False)
                longest = max(length,longest) # Is this the longest line found so far?
                linereturn.append([x1,y1,x2,y2]) # Add to the list of detected lines.
                imagebuffer = cv2.line(imagebuffer, (x1, y1), (x2, y2), (255,0,255), 2) # Mark the line on the image.
            filename = '/home/pi/pilomar/temp/plane-lines.jpg'
            cv2.imwrite(filename,imagebuffer) # Save the marked up image.
        self.Log("astrocamera.LineDetection: Found", len(linereturn), "lines in the image.",terminal=False)
        self.Log("astrocamera.LineDetection: Longest line is", longest, "pixels.",terminal=False)
        return linereturn

    def MeteorFileScan(self):
        """ If image conversions were not done during capture, this can find and convert all the 
            image files currently in storage. This is used if CaptureSetFast was used to gather 
            images as quickly as possible. 
            This will convert all image files found the have the characteristics of a jpg with embedded raw data. """
        self.Log("astrocamera.MeteorFileScan(): Starting",terminal=True)
        # Find all image files that need converting.
        rootfolder = FolderList['imageroot'] # This is the parent data folder for all Pilomar images.
        allfiles = glob.glob(rootfolder + '**/*.jpg', recursive=True) # Every jpg in every folder and subfolder.
        files = [] # Cleaned list of files to handle.
        folders = ['light'] # Which subfolders do we want?
        candidatefilename = FolderList['imageroot'] + 'MeteorCandidates_' + UtcTimeStamp() + '.txt'
        for file in allfiles: # Go through all the .jpg files found.
            for folder in folders: # Check all the image folder/types.
                temp = '/' + folder + '/' + folder + '_' # Key to an image file we are interested in.
                if temp in file: # This is an image/type that we should consider converting.
                    files.append(file) # Add to list of files to process.
                    break # No need to check anything else in the list.
        # Convert them.
        filecount = len(files)
        MeteorFiles = [] # Resulting list of meteor files.
        self.Log("astrocamera.MeteorFileScan(): Found", filecount, "files to process.",terminal=True)
        print(' ') # Blank line for incremental counter to occupy.
        if filecount > 0:
            for i,file in enumerate(files):
                # Check for EXIT from keyboard.
                if Keyboard.Check().lower() == 'x': # Exit key pressed.
                    print ("")
                    print ("** Quit **")
                    break
                print(textcolor.cursorup() + textcolor.clearforward() + NowHMS(), "Scanning", (i + 1), "of", filecount, "(" + file.split("/")[-1] + ")", "Found", len(MeteorFiles), "candidates,")
                # Load jpg data into temporary buffer.
                tempimagebuffer = cv2.imread(file,cv2.IMREAD_COLOR)
                if type(tempimagebuffer) == type(None): # imread failed.
                    self.Log("astrocamera.ProcessImageFiles: imread",file,"failed.",terminal=False)
                else: # imread was successful.
                    if len(self.LineDetection(tempimagebuffer)) > 0: # Potential meteor lines were found.
                        self.Log(file,"potentially contains meteor trail.",terminal=True)
                        MeteorFiles.append(file) # Add to list of files containing potential meteor trails. (Could be aircraft or satellites too).
        else: # Filecount == 0
            print(textcolor.yellow("No suitable image files were found."))
        self.Log("Found potential meteor trails in",len(MeteorFiles),"of",len(files),"images",terminal=True)
        if len(MeteorFiles) > 0: # Write file of candidates.
            with open(candidatefilename,'w') as f:
                for file in MeteorFiles:
                    f.write(file + "\n")
            self.Log("Candidate filenames written to",candidatefilename,terminal=True)
        self.Log("astrocamera.MeteorFileScan(): Done",terminal=True)
        return MeteorFiles # List of candidate files.
            
    def TakeTrackingPhoto(self,batch_size,terminal=True):
        """ Make an observation. This is a TRACKING image of the actual object under observation.
            Similar to TakePhoto, except the exposure is fixed to give a more consistent star count for image matching. """
        self.Log("astrocamera.TakeTrackingPhoto: Begin",terminal=False)
        ExposureMicroseconds = self.TrackingExposureSeconds * 1000000
        self.SetImageType('tracking') # Tell the camera we are taking tracking photos.
        FileRoot=FolderList.get('tracking') + 'tracking_'
        CameraOptions = ''
        CameraOptions += '-ex off ' # Exposure control off.
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-ss ' + str(ExposureMicroseconds) + ' ' # Use the TRACKING specific exposure time.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        #result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions,tempfile=True,terminal=terminal,cleanup=False,stacker=None)
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions,tempfile=True,terminal=terminal,cleanup=False)
        self.Log("astrocamera.TakeTrackingPhoto: Complete",terminal=False)
        return result

    def DarkSet(self,batch_size):
        """ Take a DARK set of images for photo stacking. """
        print (textcolor.yellow("DarkSet"))
        ExposureMicroseconds = self.ExposureSeconds * 1000000
        self.SetImageType('dark') # Tell the camera we are taking dark photos.
        FileRoot = FolderList.get('dark') + 'dark_'
        self.Log("Generating DARK image set.")
        self.Log("These match the LIGHT exposure time of",self.ExposureSeconds,"seconds.")
        self.Log("Lens cap must be ON.")
        self.Log("Images will be stored in", FileRoot)
        #inp = input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        CameraOptions = ''
        CameraOptions += '-ex off ' # Exposure control off.
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-r ' # Raw is appended to JPEG file. Needs extracting later.
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-q 100 ' # Quality
        CameraOptions += '-ss ' + str(ExposureMicroseconds) + ' ' # Use the global SHUTTER time to match the DARK and LIGHT frames.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions)
        return result

    def DarkFlatSet(self,batch_size):
        """ Take a DARK set of images for photo stacking. """
        print (textcolor.yellow("DarkFlatSet"))
        ExposureMicroseconds = 0.001 * 1000000 # 1/1000th of a second.
        self.SetImageType('darkflat') # Tell the camera we are taking darkflat photos.
        FileRoot = FolderList.get('darkflat') + 'darkflat_'
        self.Log("Generating DARK FLAT image set.")
        self.Log("These match the FLAT exposure time of",ExposureMicroseconds / 1000000, "seconds.")
        self.Log("Lens cap must be ON.")
        self.Log("Images will be stored in", FileRoot)
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        CameraOptions = ''
        CameraOptions += '-ex off ' # Exposure control off.
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-r ' # Raw is appended to JPEG file. Needs extracting later.
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-q 100 ' # Quality
        CameraOptions += '-ss ' + str(ExposureMicroseconds) + ' ' # Exposure time.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions)
        return result

    def FlatSet(self,batch_size):
        """ Take a FLAT set of images for photo stacking. """
        print (textcolor.yellow("FlatSet"))
        self.SetImageType('flat') # Tell the camera we are taking flat photos.
        FileRoot = FolderList.get('flat') + 'flat_'
        self.Log("Generating FLAT image set.")
        self.Log("These are flat white unfocused images.")
        self.Log("These will be a short exposure time (Auto exposure)")
        self.Log("The lens cap must be OFF. You need a evenly lit neutral white target.")
        self.Log("People often stretch a white t-shirt over the lens and point at a bright area of sky.")
        self.Log("You can re-use the flat image set across multiple campaigns.")
        self.Log("Images will be stored in", FileRoot)
        #inp = input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        CameraOptions = ''
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-q 100 ' # Quality
        CameraOptions += '-r ' # Raw is appended to JPEG file. Needs extracting later.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions)
        return result

    def BiasSet(self,batch_size):
        """ Take a BIAS/OFFSET set of images for photo stacking. """
        print (textcolor.yellow("BiasSet"))
        ExposureMicroseconds = 0.001 * 1000000 # 1/1000th of a second.
        self.SetImageType('bias') # Tell the camera we are taking bias photos.
        FileRoot = FolderList.get('bias') + 'bias_'
        self.Log("Generating OFFSET/BIAS image set.")
        self.Log("These will be the shortest possible exposure time (FASTEST)",ExposureMicroseconds / 1000000,"seconds")
        self.Log("Lens cap must be ON.")
        #inp = input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        CameraOptions = ''
        CameraOptions += '-ex off ' # Exposure control off.
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-ss ' + str(ExposureMicroseconds) + ' ' # Exposure time.
        CameraOptions += '-r ' # Raw is appended to JPEG file. Needs extracting later.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions)
        return result
        
    def AutoPhoto(self):
        print (textcolor.yellow("AutoPhoto"))
        if Parameters.CameraEnabled == False:
            self.Log("astrocamera.AutoPhoto(): Camera is disabled. No photo attempted.",level='warning')
            return False
        FileRoot = FolderList.get('auto') + 'autophoto_'
        self.SetImageType('auto')
        print ("Taking fully automatic photographs (Good for daylight testing).")
        print ("Lens cap must be OFF.")
        print ("Camera must already be on-target, it will not track during AutoPhoto functions.")
        print ("Camera will use automatic exposure settings in AutoPhoto mode.")
        print ("Images will be stored in", FileRoot)
        inp = ""
        while inp != 'x':
            inp = input("<RETURN> to begin ('x' to quit): ").lower() # Python3 
            if inp == "x":
                print ("quit")
                break
            dt = CleanDatetimeString(str(NowUTC()))
            filename = FileRoot + dt + '.jpg'
            cmd = 'raspistill --focus --settings -o ' + filename
            #temp = osCmd(cmd)
            osCmd(cmd)
            print ("-", filename)
        return True
        
# Create camera related objects.
# Parameters taken from https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
# RPiHQ16mm
#    Lens Length = 16.0 # Official lens focal length.
#    Lens horizontal field of view 21.8 degrees.
#    Lens vertical field of view 16.4 degrees.
# Arducam50mm
#    Lens Length = 50.0 # Official lens focal length.
#    Lens horizontal field of view 7.0 degrees.
#    Lens vertical field of view 2.0 degrees.
# Sensor image width 4056 pixels
# Sensor image height 3040 pixels
LensInUse = astrolens(length=Parameters.LensLength, horizontal_fov=Parameters.LensHorizontalFov, vertical_fov=Parameters.LensVerticalFov) # from https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
SensorInUse = astrosensor(sensor_type=Parameters.SensorType) # from https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
CameraInUse = astrocamera(inp_sensor=SensorInUse, inp_lens=LensInUse, exposure=10.0, trackingexposure=Parameters.TrackingExposureSeconds)

# ///////////////////////////////////////////////////////////////////////////////////
# Enable/disable key features during testing.
# ///////////////////////////////////////////////////////////////////////////////////

#print ("")
MainLog.Log("The motors can be disabled in the parameters file if you want to test only the software.",terminal=False)
if Parameters.MotorsEnabled: print (textcolor.green("Motors enabled"))
else: print (textcolor.red("Motors disabled"))
#print ("")

# ---------------------------------------------------------------------------------------------------- 

def DetectCamera(canenable=False,candisable=False): # 4 references.
    """ Test to see if the camera is connected and active. 
        candisable = True: If the camera is not found, then automatically disable it in parameters.
        canenable = True: If the camera is found, then automatically enable it in parameters. """
    filename = ProjectRoot + '/temp/testraspistill.jpg' # Or use /dev/null ? We don't need this file.
    tempcmd = 'raspistill -o ' + filename # Simple command to test the camera.
    templist = osCmd(tempcmd)
    tempresult = True
    for line in templist: # Check output of the command.
        if line.lower().find('failed') >= 0: # Any mention of 'failed' implies that the camera is not available.
            MainLog.Log("Found:", line, "in log file, considering photograph failed.")
            tempresult = False
            break
    if tempresult: # Camera appears to be working.
        if Parameters.CameraEnabled: # Camera is enabled and available.
            MainLog.Log("Camera is accessible and enabled.")
        else: # Camera is available but not accessible. Warn that it will need to be enabled from the menu.
            if canenable:
                Parameters.CameraEnabled = True
                MainLog.Log("Camera has been automatically enabled.",level='warning')
            else:
                MainLog.Log("Camera is accessible, but disabled. You can enable it from the Camera Tools menu.")
    else: # Camera does not appear to be available.
        MainLog.Log("DetectCamera: Camera not found.",level='warning')
        if candisable:
            if Parameters.CameraEnabled: # Warn the user that the camera is automatically disabled.
                Parameters.CameraEnabled = False
                MainLog.Log("Camera has been automatically disabled.",level='warning')
                MainLog.Log("When the camera is available, you can re-enable it from the Camera Tools menu.",level='warning')
    templist = osCmd('rm ' + filename) # Cleanup. Ignore errors.
    return tempresult

# ---------------------------------------------------------------------------------------------------- 

def AutoDetectCamera(): # 1 references.
    """ This tests the telescope camera. 
        If found, it enables the camera.
        If missing, it disables the camera. """
    DetectCamera(canenable=True, candisable=True)

# ---------------------------------------------------------------------------------------------------- 

def CalibrateFov(): # 1 references.
    """ Use the diameter of the full moon to calibrate the field of view of the lens. 
        The moon is a relatively stable known angular diameter in the sky. 
        By taking a photograph of the moon and measuring the number of pixels that the
        moon occupies we can work backwards to estimate the field of view of the lens. """
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        CameraInUse.EstimateFov()
        CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
        FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
        DocumentSession()
        DriftTracker.Reset()
        
# ---------------------------------------------------------------------------------------------------- 

def EnableCamera(): # 1 references.
    """ This enables the camera, even if it is not installed. """
    Parameters.CameraEnabled = True
    MainLog.Log("Camera has been manually enabled.",level='warning',terminal=True)

# ---------------------------------------------------------------------------------------------------- 

def DisableCamera(): # 1 references.
    """ This disables the camera. """
    Parameters.CameraEnabled = False
    MainLog.Log("Camera has been manually disabled.",level='warning',terminal=True)

# ---------------------------------------------------------------------------------------------------- 

# Check if camera is available.
tempresult = DetectCamera(candisable=True)

if Parameters.CameraEnabled:
    print (textcolor.green("Camera enabled"))
    MainLog.Log("The camera can be disabled in the parameters file if you don't want to take actual photographs.",terminal=False)
    if Parameters.DisableCleanup: SensorInUse.DisableCleanup()
    else: MainLog.Log("NOTE: on-chip cleanup has not changed state.",terminal=True)
else: 
    print (textcolor.red("Camera disabled"))
    MainLog.Log("The program will generate simulated images instead.",terminal=True)

# ///////////////////////////////////////////////////////////////////////////////////
# GPIO setup.
# ///////////////////////////////////////////////////////////////////////////////////
        
# Use BCM GPIO references instead of physical pin numbers.
# GPIO must be enabled via raspi-config.
GPIO.setmode(GPIO.BCM)
 
# // Initialise control IO
StopBCM = 25 # BCM pin 12 to stop an obvservation.
GPIO.setup(StopBCM,GPIO.IN,pull_up_down=GPIO.PUD_UP) # Set pin to INPUT. Will EARTH when triggered.

class outputpin(): # 4 references.
    def __init__(self,pinbcm,name=None):
        self.Pin = pinbcm
        self.Enabled = True
        self.Name = name
        self.State = False
        GPIO.setup(pinbcm, GPIO.OUT)
        self.Refresh()
    
    def On(self):
        self.State = True
        self.Refresh()
        
    def Off(self):
        self.State = False
        self.Refresh()
        
    def Refresh(self):
        if self.Enabled and self.State:
            GPIO.output(self.Pin,GPIO.HIGH)
        else:
            GPIO.output(self.Pin,GPIO.LOW)

    def Enable(self):
        self.Enabled = True
        self.Refresh()
        
    def Disable(self):
        self.Enabled = False
        self.Refresh()

Led1 = outputpin(27,'led1') # UART RX traffic.
Led2 = outputpin(22,'led2') # UART TX traffic.
Led3 = outputpin(5,'led3') # Camera capturing image.
Led4 = outputpin(6,'led4') # ReadyToObserve status LED.

LedList = [Led1,Led2,Led3,Led4]

# ------------------------------------------------------------------------------------------------------

class microcontroller(attributemaster): # 1 references.
    """ Class to manage the UART communication between the RPi and the motor microcontroller. 
        This handles I/O and buffering of inbound/outbound messages over the UART lines. """
    def __init__(self,port='/dev/serial0',resetpin=4):
        self.uart = serial.Serial(port,115200,timeout=0,exclusive=True)
        self.Log = None # Handle to the method/function which will be used for logging messages.
        self.QueueToMctl = Queue() # Use queue mechanism to send commands to the microcontroller communication thread. 
        self.QueueFromMctl = Queue() # Use queue mechanism to receive commands from the microcontroller communication thread. 
        self.ResetPin = resetpin # Earthing this pin will RESET the remote device.
        if self.ResetPin != None:
            GPIO.setup(self.ResetPin, GPIO.OUT)
            GPIO.output(self.ResetPin, GPIO.HIGH) # Makes sure the pin is HIGH, otherwise the microcontroller resets. *Q* Microcontrollers sometimes reset at random anyway :(
        self.Lines = [] # No lines received yet.
        self.WriteChunkBytes = 32
        self.WriteChunkSeconds = 0.2 # Seconds between chunks written to microcontroller.
        self.InputLine = ''
        self.WriteQueue = [] # No output to send yet.
        self.LinesReceived = 0
        self.LinesSent = 0
        self.BytesReceived = 0
        self.BytesSent = 0
        self.LedStatus = True # LEDS on by default.
        self.LineOpenedTime = NowUTC()
        self.LastTxTime = NowUTC() # When was data last sent?
        self.LastRxTime = NowUTC() # When was data last received?
        self.RxErrors = 0
        self.LastLineSent = None # We get 'reflection' on the UART port if the remote device isn't ready. This needs ignoring.
        self.CommsTimeout = 60 # Seconds. microcontroller is restarted if no data received after this period.
        self.ForcedRestarts = 0 # How many restarts have been forced by this software?
        self.RemoteRestarts = 0 # How many restarts have been registered by the remote device itself?
        self.ResetAttempts = 0 # Increment for each sequential attempt to reset communication with the remote microcontroller board.
        self.DeviceFailure = False # Set to TRUE if device seems to be irrecoverably lost.
        self.ErrorWindow = None
        self.WriteProhibited = False # OK to write again to the write queue.
        self.SendId = 0 # Incremental counter, the message number being sent to the microcontroller. The microcontroller will respond that this message number has been received.
        # Calling program needs to call microcontroller.Initiate() to get things going.

    def Initiate(self):
        """ Initiate communication. """
        self.Log('microcontroller.__init__:',\
              'baudrate=', self.uart.baudrate,\
              'bytesize=', self.uart.bytesize,\
              'parity=', self.uart.parity,\
              'stopbits=', self.uart.stopbits,\
              'timeout=', self.uart.timeout,\
              'write_timeout=', self.uart.write_timeout,\
              'inter_byte_timeout=', self.uart.inter_byte_timeout,\
              'xonxoff=', self.uart.xonxoff, \
              'rtscts=', self.uart.rtscts,\
              'dsrdtr=', self.uart.dsrdtr, terminal=False)
        self.Log('New UART device. Triggering reset to initialize it...',terminal=False)
        self.Reset(planned=True) # Make sure that the microcontroller is fresh and ready for new tasks.
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()
        self.Log('New UART connection. Flushing...',terminal=False)
        # Send a comment line to flush any crud from the system.
        for i in range(2):
            self.Write('#'*20)
        self.Write('rpi started') # Tell microcontroller that the RPi has just started.
        line = 'set time ' + CleanDatetimeString(str(NowUTC())) # Immediately send a time update to the microcontroller to synchronise the clocks ASAP.
        self.Write(line)

    def CalculateChecksum(self,line):
        """ Calculate a basic checksum for a line of text. """
        cs = ""
        a = 0
        if len(line) > 0:
            for i in range(len(line)):
                if i % 2 == 0: a += ord(line[i])
                else: a += ord(line[i]) * 3
        cs = str(hex(a % 65536))[2:]
        return cs

    def AddChecksum(self,line):
        """ Add a checksum to a line of text ready for transmission. """
        return line + '|' + self.CalculateChecksum(line)

    def RemoveChecksum(self,line):
        """ Strip off the trailing checksum from a received line of text. """
        i = line.rfind('|')
        if i >= 0:
            line = line[:i]
        return line

    def ValidateChecksum(self,line):
        """ Validate a line of text that contains a checksum. 
            Returns TRUE if the checksum is correct.
            Returns FALSE if the checksum is not correct. """
        result = False
        i = line.rfind('|')
        if i >= 0:
            cs = line[i+1:]
            line = line[:i]
            if cs == self.CalculateChecksum(line):
                result = True
        return result

    def Reset(self,planned=False):
        """ Remote device needs resetting. 
            Planned = False : Means that this was an unplanned reset, the microcontroller failed. 
                      Too many of these,and the program considers the microcontroller faulty.
            Planned = True : Means that this was a planned reset, eg end of an observation.
                      This is just a convenient way to stop the motors and prepare for a 
                      fresh observation to be set up. It doesn't indicate any fault in the microcontroller. """
        if not planned: # If this is recovering from unplanned errors, then count the resets.
            if self.ResetAttempts > 10: # Don't bother again.
                msg = 'After ' + str(self.ResetAttempts) + ' attempts, considering the microcontroller failed.'
                if self.ErrorWindow != None and hasattr(self.ErrorWindow,'Print'):
                    self.ErrorWindow.Print(msg)
                print(textcolor.red(msg))
                self.DeviceFailure = True
                MainLog.RecordTraceback(None) # Record the stack at this point.
                exit() # Quit the program.
                return False
            else:
                self.ResetAttempts += 1 # Try again.
        # GPIO pin is driven low for a second. This either triggers the microcontroller's reset pin directly (eg Pico RP2040, Feather RP2040 etc),
        # or it can simply switch off the power to a microcontroller that lacks a reset pin (eg Tiny2040).
        # The behaviour will depend upon the circuitry supporting the chosen microcontroller.
        GPIO.output(self.ResetPin, GPIO.LOW)
        time.sleep(1) #Pause 1 second.
        GPIO.output(self.ResetPin, GPIO.HIGH)
        time.sleep(1) #Pause 1 second.
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()
        self.Lines = [] # No lines received yet.
        self.InputLine = '' # This holds the currently arriving line while it is being constructed.
        self.WriteQueue = [] # No output to send yet.
        self.LineOpenedTime = NowUTC()
        self.LastTxTime = NowUTC() # When was data last sent?
        self.LastRxTime = NowUTC() # When was data last received?
        self.LastLineSent = None # We get 'reflection' on the UART port if the remote device isn't ready. This needs ignoring.
        # Reset communication counters.
        self.LinesReceived = 0
        self.LinesSent = 0
        self.BytesReceived = 0
        self.BytesSent = 0
        self.RxErrors = 0
        self.ForcedRestarts += 1 # Record that we've chosen to forcefully restart the microcontroller. 
        self.WriteProhibited = False # OK to write again to the write queue.
        ErrorWindow.Print(NowHMS() + " Microcontroller reset ; planned " + str(planned))
        return True

    def RxAge(self):
        """ How many seconds ago was the last message received? """
        Rx = int((NowUTC() - self.LastRxTime).total_seconds())
        return Rx

    def ReadPoll(self):
        """ Read all waiting characters into the input queue.
            This reads from the UART input queue and adds any received 
            text into an internal buffer ready for the program to process.
            To pull a received message from the input queue use the Read() method instead!. """
            
        if not self.uart.is_open: 
            MctlRxWindow.Print('uart.ReadPoll: uart is not open!.')
            return # Don't perform the poll.

        # Check for stalled communications.
        if self.RxAge() > self.CommsTimeout:
            self.Log('uart.ReadPoll(): microcontroller has not transmitted for', self.RxAge(), 'seconds. It will be restarted',level='error',terminal=False)
            if self.Reset(): # Trigger reset and resync mechanism.
                self.Log('uart.ReadPoll(): microcontroller reset complete.',terminal=False)
            else:
                self.Log('uart.ReadPoll(): microcontroller reset failed.',level='error')
                if self.DeviceFailure:
                    self.Log('uart.ReadPoll(): microcontroller considered permanently unavailable after ' + str(self.ResetAttempts) + ' restart attempts.',level='error',terminal=False)
        while self.uart.in_waiting: # Something in the read queue.
            Led1.On()
            try: # Try to get the next available character. 
                response = self.uart.read(1) # Read single character.
                response = response.decode('utf-8') # Decode the character.
                self.BytesReceived += 1 # Increment received count.
            except Exception as e:
                self.Log('uart.Read: uart.read(1) failed. Ignored. ' + str(e),terminal=False)
                response = '' # Ignore unusable character.
            if response == '\n': # End of line received.
                if self.InputLine == self.LastLineSent: # We have reflection on the UART channel. Trouble!
                    # This is a sign that the remote device isn't responding. UART seems to loop back in that case.
                    print(textcolor.red('uart.Read: Ignoring reflected line (' + str(self.InputLine) + ')'))
                    self.Log('uart.Read: Ignoring reflected line (' + str(self.InputLine) + ')',terminal=False)
                else: # We have a valid line received from the correspondent. 
                    self.Lines.append(self.InputLine) # Add received line to input queue.
                    self.LastRxTime = NowUTC() # Note when last receive activity occurred. 
                    self.ResetAttempts = 0 # We have activity, so clear the restart counter.
                    self.LinesReceived += 1 # Increment count of lines received. 
                self.InputLine = '' # Start a fresh input line next time anything is received. 
            else: self.InputLine += response # Add the character to the input line we are constructing. 
            Led1.Off()

    def Read(self):
        """ Return the next input line received (if there is one).
            Validate checksum and ignore anything which fails.
            This pulls the next input line from the received buffer.
            It does not poll the UART input line directly (See ReadPoll() method).
            *Q* This could store the 'controller log' messages directly here automatically. """
        result = ''
        while len(result) == 0 and len(self.Lines) > 0: # No valid line to return yet, and still lines available in the receive buffer.
            result = self.Lines.pop(0).strip()
            self.Log('RPi received: ' + self.RemoveChecksum(result),terminal=False)
            MctlRxWindow.Print(self.RemoveChecksum(result))
            if self.ValidateChecksum(result): # Line is good.
                result = self.RemoveChecksum(result)
                if result == 'pico started' or result == 'controller started': 
                    self.RemoteRestarts += 1 # Record how many times the remote device reports a restart.
                    ErrorWindow.Print(NowHMS() + " " + result)
                if 'error' in result:
                    print(textcolor.red('RPi received: ') + result)
            else: # Checksum failure.
                MctlRxWindow.Print('RPi rejected checksum on: ' + result)
                self.Log('RPi rejected checksum on: ' + result,terminal=False)
                self.RxErrors += 1
                result = ''
            # Some messages we can deal with immediately without passing back to the calling routines.
            if result.startswith('#'): result = '' # Ignore comments.
            # *Q* Can we handle regular status updates too (motor, comms, session) and potentially queue automated responses?
        return result

    def WritePoll(self):
        """ Write a chunk of data from the output buffer to the UART port.
            This takes lower priority than the READ from the UART port.
            It will only send 1 chunk every 0.2 seconds to give the receiving microcontroller
            time to read the data. 
            To add lines to the output buffer use the Write() method. """
        if len(self.WriteQueue) == 0:
            return # Nothing to send anyway.
        if self.uart.in_waiting:
            return # Input waiting. Handle that first.
        if self.LastTxTime != None and (NowUTC() - self.LastTxTime).total_seconds() < self.WriteChunkSeconds: # 0.2:
            return # Must be 0.2 second gap between each transmitted packet.
        if not self.uart.is_open: 
            MctlTxWindow.Print('uart.WritePoll: uart is not open!.')
        if len(self.WriteQueue[0]) < self.WriteChunkBytes: # Can write the entire line in one go.
            line = self.WriteQueue.pop(0)
            terminator = '\n'
        else: # Need to send just a chunk of the line in this pass.
            line = self.WriteQueue[0][0:self.WriteChunkBytes] # 1st 'chunksize' characters only.
            self.WriteQueue[0] = self.WriteQueue[0][self.WriteChunkBytes:] # Remove transmitted characters.
            terminator = ''
        self.LastLineSent = line # Keep a note of what we sent, if we receive that back it is reflection indicating a problem.
        line += terminator
        self.LinesSent += 1
        self.BytesSent += len(line)
        Led2.On()
        self.uart.write(line.encode('utf-8')) # Send data in UTF-8 format. 
        self.LastTxTime = NowUTC() # Note that time of the last data sent. 
        Led2.Off()

    def ReadFlush(self):
        """ Clear the input buffer. Don't actually transmit it, because you may never reach the end if 
            new messages are appearing. Just clear and reset the internal buffer of messages received. """
        self.Log('microcontroller.ReadFlush: Drop unprocessed messages received from microcontroller...',terminal=False)
        self.Lines = [] # Empty the queue. 
        self.InputLine = '' # Scrap any line currently being received and constructed.
        
    def WriteFlush(self,send=True):
        """ Make sure the output buffer is completely flushed. Timeout after a limited number of attempts.
            This doesn't add anything to the output queue, it just makes sure that everything
            waiting to be sent is transmitted.
            if send parameter is false, the write queue is flushed without sending anything further. """
        result = True
        if send: # We should try to send outstanding messages.
            self.Log('Flushing microcontroller output queue (pending messages will be sent)...',terminal=False)
            TryCount = 0
            self.WriteProhibited = True # Don't allow anything further to be added to the queue at the moment.
            while len(self.WriteQueue) > 0 :
                TryCount += 1
                time.sleep(0.1) # Pause until the CommsLoop thread has cleared the buffer.
                if TryCount >= 500:
                    self.Log('Flush timeout. Maximum 500 messages sent. Remaining messages will be dropped.',terminal=False)
                    self.WriteQueue = [] # Delete any remaining messages in the queue.
                    result = False
                    break
            self.WriteProhibited = False # OK to write again to the write queue.
        else: self.Log('Flushing microcontroller output queue (pending messages will be dropped)...',terminal=False)
        return result

    def SetLedStatus(self,status=True):
        """ Change status of Microcontroller LEDs.
            This will make the LEDS on the microcontroller itself go dark.
            This reduces light pollution within the telescope dome. """
        self.LedStatus = status
        if status:
            self.Write('leds on')
        else:
            self.Write('leds off')

    def MctlRestarted(self):
        """ If microcontroller reports a restart, this routine resets the buffers and 
            acknowledges the restart back to the microcontroller. """
        self.ReadFlush() # Scrap the contents of the read buffer. We're starting again.
        self.WriteFlush(send=False) # Scrap the contents of the write buffer. We're starting again.
        self.Write('# Hello controller') # Acknowledge to the microcontroller that we're restarting the conversation too.
        self.SetLedStatus(self.LedStatus) # Turn on/off the status led on the microcontroller.

    def Write(self,line):
        """ Add a new output message to the queue to be processed.
            It is not physically transmitted, it will wait in turn in the 
            output queue until WritePoll() gets around to sending it. 
            Nothing is added to the queue if self.WriteProhibited = True. 
            To send text from the output queue to the Microcontroller over the UART line use the WritePoll() method. """
        if self.WriteProhibited: 
            self.Log('microcontroller.Write: WriteProhibited: ' + line)
        elif len(line) > 0:
            line = line.replace('\n','') # Was strip()
            self.SendId += 1 # Increment the message ID number.
            if line[-1:] != ' ': line += ' ' # Need a space separator between fields.
            line += '[' + str(self.SendId) + ']' # Append sequential message ID. microcontroller will respond with this ID when it has received OK.
            MctlTxWindow.Print(line)
            self.WriteQueue.append(self.AddChecksum(line)) # Add to send queue with Checksum.
            self.Log('RPi queueing (Q# ' + str(len(self.WriteQueue)) + '): ' + line,terminal=False)

    def CommsLoop(self,commandqueue): # Runs as own thread.
        """ This runs in its own thread, it just continually reads/writes
            to the microcontroller via the uart serial connection.
            It terminates when the main thread dies.
            You can send commands to this communication loop itself via the commandqueue queue.
            - Eg : 'stop' to shut down the loop completely. """
        self.Log('microcontroller.CommsLoop(): Start',terminal=False)
        while True: # Loop until explicitly told to break.
            self.WritePoll() # Send next chunk of data from output buffer if allowed.
            self.ReadPoll() # Read anything waiting in the input buffer.
            if threading.main_thread().is_alive() == False: # Check if parent is still alive. Quit if it is nolonger there.
                self.Log("microcontroller.CommsLoop(): Parent thread is nolonger alive. Terminating",level='error')
                break # Parent thread died, so terminate this thread too.
            if commandqueue.empty() == False: # This queue allows the main thread to send commands to the microcontroller comms controller itself.
                ReceivedMessage = commandqueue.get()
                if ReceivedMessage == "stop":
                    self.Log("microcontroller.CommsLoop(): Received 'stop' command.",terminal=False)
                    break # Terminate this loop. Will require restart by main thread.
            time.sleep(0.01) # Need a tiny pause otherwise this hogs the processor.
        # Flush any outbound comms to the microcontroller before closing.
        Mctl.WriteFlush(send=True)
        self.Log('microcontroller.CommsLoop(): End',terminal=False)

UartControlQueue = Queue() # Command queue to the CommsLoop, use this to shut it down by sending 'stop'.

# ------------------------------------------------------------------------------------------------------

def InitiateMctl(): # 2 references.
    """ Start up fresh communication with the microcontroller. """
    MainLog.Log('Establishing serial UART communication with microcontroller...',terminal=False)
    mctl = None
    try:
        mctl = microcontroller(port='/dev/serial0',resetpin=Parameters.MctlResetPin) # Create communication with microcontroller over uart0 serial port.
        mctl.Log = MainLog.Log # Tell which Logging function to use.
        mctl.Initiate() # Initiate communication.
    except Exception as e:
        MainLog.Log('InitiateMctl: Failed: Is another instance already running?',level='error')
        print ("")
        linelist = ["           THE MICROCONTROLLER FAILED TO INITIALISE.",
                 "This may be because another copy of pilomar is already running.",
                 "or because the Serial Port is misconfigured in raspi-config.",
                 "1) Check for duplicate processes and terminate them if needed.",
                 "2) Check serial port is disabled for login and enabled for IO."]
        textcolor.TextBox(linelist,fg=textcolor.WHITE,bg=textcolor.RED)
        print ("")
        print (textcolor.yellow("pilomar processes currently running:-"))
        osCmd('ps -ef | grep pilomar',output='terminal')
        MainLog.RaiseException(e,comment='InitiateMctl') # Trap all the exception information in the main log file.
    return mctl
    
# ------------------------------------------------------------------------------------------------------

Mctl = InitiateMctl() # Create new microcontroller instance. 
if Mctl == None: # Microcontroller couldn't start.
    MainLog.Log("InitiateMctl failed to create Microcontroller instance.",level='error')
    exit() # Quit the program.

def SetGlobalLedStatus(): # 2 references.
    try:
        Mctl.SetLedStatus(Parameters.MctlLedStatus) # Set the LED status on the microcontroller.
        for Led in LedList:
            if Parameters.MctlLedStatus:
                Led.Enable()
            else:
                Led.Disable()
    except Exception as e:
        MainLog.RaiseException(e,comment='SetGlobalLedStatus') # Trap all the exception information in the main log file.
    

# ------------------------------------------------------------------------------------------------------

def StartMctlComms(): # 2 references.
    """ This runs the microcontroller communications in a separate thread.
        This should keep communication flowing even if the main thread
        is busy with other tasks.
        (Python does not have truly concurrent threads, so it may still pause sometimes.)"""
    # Communication between the MctlComms thread and the main thread is through the UartControlQueue.
    Mctl.CommsLoop(UartControlQueue)

# ------------------------------------------------------------------------------------------------------

# Run the microcontroller communications in a separate thread.
MctlThread = threading.Thread(target=StartMctlComms,args=(),daemon=True) # Run microcontroller communication independently, quit automatically.
MctlThread.start()

# ======================================================================================================

MainLog.Log('Preparing motor control...',terminal=False)

# ------------------------------------------------------------------------------------------------------

class motorcontrol(attributemaster): # 2 references. 
    """ Representation of remote motor.
        The actual motor is controlled in the microcontroller software,
        this class contains an image of important parameters for
        the motor so that this program can direct it. """
        
    AllMotors = [] # A list of all sibling motors which is common to all instances of motorcontrol. So any single motor instance can refer to all the other motors if needed via motorcontrol.AllMotors.

    def __init__(self,name,gearratio,motorstepsperrev,microstepratio,minangle,maxangle,restangle,currentangle,backlashangle,orientation=1):
        """ Initialize with values that we know from the physical construction of the motor.
            Other values can be configured later by the remote server. """
        self.Log = MainLog.Log # Handle to logging function/method to be used by this class.
        self.MotorName = name
        self.GearRatio = gearratio
        self.MotorStepsPerRev = motorstepsperrev
        self.MicrostepRatio = microstepratio # *Q* Does this apply to MotorStepsPerRev and AxisStepsPerRev etc too?
        self.WarningAngle = 10 # Can warn if position is within this angle of a limit.
        self.MinAngle = minangle
        self.MinWarningAngle = minangle + self.WarningAngle # Can warn if within xx degrees of minimum position.
        self.MaxAngle = maxangle
        self.MaxWarningAngle = maxangle - self.WarningAngle # Can warn if within xx degrees of maximum position.
        self.Orientation = orientation
        self.BacklashAngle = backlashangle
        self.CurrentAngle = currentangle # This will be updated by the microcontroller once running. 
        self.RestAngle = restangle
        self.MotorStepsPerAxisDegree = self.MicrostepRatio * self.MotorStepsPerRev / 360.0
        self.AxisStepsPerRev = self.MicrostepRatio * self.MotorStepsPerRev * self.GearRatio 
        self.MotorConfigured = False
        self.FastTime = 0.001 # Was 0.0005
        self.SlowTime = 0.05
        self.TimeDelta = 0.003
        self.TrajectorySegmentSize = 60 # Seconds.
        self.TrajectoryValid = False # Is the microcontroller trajectory valid?
        self.TrajectoryEntries = 0 # Number of trajectory entries stored on the microcontroller.
        self.TrajectoryValidUntil = None # The 'end time' of the trajectory as reported from the microcontroller.
        self.LastSentTrajectoryKey = None # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
        self.LastSentTrajectoryData = None # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.
        self.OnTarget = False # Is the motor currently on target? 
        self.LatestTuneTime = None # When did motor last acknowledge a TUNE command?
        self.LatestTuneSteps = 0
        self.RecoveryFolder = ProjectRoot + "/data/" + self.MotorName + "_angle"
        self.RecoveryFileName = self.RecoveryFolder + "/" + UtcTimeStamp() + ".log" # Used to record the position of the motor, this can then recover the situation in the event of any failures.
        VerifyFolder(self.RecoveryFolder) # Make sure that the recovery folder exists.
        self.MotorRunningSeconds = 0 # V2 motor running time counter.
        self.RestoreAngle()
        self.LastRecoveryAngle = self.CurrentAngle # This is used to detect when the motor has physically moved so we don't keep writing the same position repeatedly to the recovery file.
        self.Log('Motor ' + self.MotorName + ' recovered to ' + str(round(self.CurrentAngle,5)) + DegreeSymbol,terminal=False)
        self.AllMotors.append(self) # Class attribute AllMotors points to ALL sibling motors. Can be used to check condition of any other motors too.
        self.PrevStatusTimestamp = None # The timestamp of the last status message received from the motorcontroller.
        self.Restarted() # Make sure that status flags are reset for a 'new' unconfigured motor.

    def __del__(self):
        """ When deleted, remove this motor from the global list of all available motors. """
        self.AllMotors.remove(self) # Class attribute AllMotors points to ALL sibling motors. Remove this motor from the list when deleted.

    def SetMotorClock(self):
        """ Prompt user for new clock running time (in hours) 
            Update the clock time accordingly. """
        print(textcolor.yellow('Update ' + self.MotorName + ' motor clock'))
        while True:
            temp = input('Enter new running hours (x to quit): ')
            if temp.lower() == 'x': 
                print('Nothing changed.')
                break
            hours = TextToFloat(temp)
            if hours == None:
                print(textcolor.red('Invalid, must be a decimal value. Try again.'))
                continue # Try again.
            self.MotorRunningSeconds = hours * 3600 # Convert to seconds.
            print(textcolor.yellow('Clock set to ' + str(self.MotorRunningSeconds) + 'seconds (' + HRSeconds(self.MotorRunningSeconds) + ')'))
            self.StoreRecoveryAngle(force=True) # Record the new value immediately.

    def Restarted(self): 
        """ Call this if the microcontroller restarts. 
            This resets some status flags so that we know the motor isn't fully configured yet. """
        self.MotorConfigured = False
        self.OnTarget = False # Is the motor currently on target? 
        self.TrajectoryValid = False # Is the microcontroller trajectory valid?
        self.TrajectoryEntries = 0 # Number of trajectory entries stored on the microcontroller.
        self.TrajectoryValidUntil = None # The 'end time' of the trajectory as reported from the microcontroller.
        self.LastSentTrajectoryKey = None # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
        self.LastSentTrajectoryData = None # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.

    def ApproachingLimit(self):
        """ Return TRUE if motor is within warning limit of the end of movement. """
        if self.CurrentAngle <= self.MinWarningAngle: result = True
        elif self.CurrentAngle >= self.MaxWarningAngle: result = True
        else: result = False
        return result

    def CompareAngles(self,angle1,angle2,ptolerance=None,atolerance=None):
        """ Compare two (float) angles, return TRUE if they are the same 'motor position'.
            ptolerance: defines a motor position tolerance. Number of motor steps that are considered a good enough match.
            atolerance: defines an angle tolerance. Angle within which the two values are considered a good enough match.
            If neither is specified, then angles are considered equal if they resolve to precisely the same motor position. """
        result = False
        if angle1 != None and angle2 != None:
            if ptolerance != None and abs(self.AngleToStep(angle1) - self.AngleToStep(angle2)) <= ptolerance: result = True # Angles are same within STEP tolerance.
            if atolerance != None and abs(angle1 - angle2) <= atolerance: result = True # Angles are the same within ANGLE tolerange.
            if self.AngleToStep(angle1) == self.AngleToStep(angle2): result = True # Angles equate to the same step position.
        return result

    def MotorHours(self):
        """ Return number of hours the motor has been running for. 
            (total lifetime of the motor). """
        mrh = round(self.MotorRunningSeconds / 3600) # How many HOURS have the motors been running for?
        return mrh

    def RestoreAngle(self):
        """ This searches for the last recorded position of the motor and restores that state. 
            The last recorded position is stored in a file in the self.RecoveryFolder. 
            It also loads the total running time of the motor (in seconds). """
        filename = ''
        oldfiles = [] # List of recovery files, we'll delete the old ones.
        # Find all the position recovery files available. Read in time sequence due to filenaming. 
        for file in os.listdir(self.RecoveryFolder):
            thisfile = self.RecoveryFolder + "/" + file 
            if thisfile == self.RecoveryFileName: continue # Ignore the CURRENT file we're writing to.
            if file.endswith(".log"):
                if thisfile > filename: filename = thisfile # More recent image.
                oldfiles.append(thisfile) # Maintain list of all files found.
        if len(filename) == 0:
            self.Log("No recovery log file found for " + self.MotorName + " motor. Assuming " + str(self.RestAngle) + DegreeSymbol)
            return False
        angle = self.RestAngle # Default to home position.
        with open(filename) as file_in: # Read all the positions in the file, could be smarter and go to the end of the file here.
            for line in file_in: # Lines will be on chronological sequence. We keep that latest valid entry as the last known position of the motor. 
                line = line.strip() # Trim unwanted characters from line.
                ls = line.split(";") # Format is     'timestamp';'angle';'seconds'
                if len(ls) > 1: angle = float(ls[1]) # 'timestamp';'angle';'seconds'
                else: self.Log("Bad recovery entry (" + line + ") ignored.",level='warning')
                if len(ls) > 2: 
                    self.MotorRunningSeconds = int(ls[2]) # 'timestamp';'angle';'seconds'
        self.CurrentAngle = angle
        self.Log("Motor",self.MotorName,"steps restored to last known position", str(self.AngleToStep(self.CurrentAngle)), "(", str(self.CurrentAngle) + DegreeSymbol, ")")
        # Check the total running time of the motor. They have a design life!
        self.Log("Motor",self.MotorName,"has so far been running for", str(self.MotorRunningSeconds), "s (",str(self.MotorHours()), "h ).",terminal=False)
        MotorInitialHours = self.MotorHours()
        if MotorInitialHours > 10000: # Nema17 motors designed for 20,000hour 'on' time. This is whenever they are energised, not just moving.
            if MotorInitialHours > 20000: # Nema17 motors designed for 20,000hour 'on' time. This is whenever they are energised, not just moving.
                self.Log("Motor",self.MotorName,"has been energised for",str(MotorInitialHours),". Design time is 20k hours in total. Please replace it.",level='error')
            else:
                self.Log("Motor",self.MotorName,"has been energised for",str(MotorInitialHours),". Design time is 20k hours in total. Consider replacing it.",level='warning')
            self.Log("Motor",self.MotorName,": When you replace it, please reset the running time in the recovery file in",self.RecoveryFolder,level='warning')
        # Now remove any old recovery files that we don't need. Always keep last 2.
        if len(oldfiles) > 2: # Only tidyup if more than 2 files available.
            oldfiles = sorted(oldfiles)[:-2] # Sort alphabetically. This is equivalent to chronological sequence. Ignore the last 2 files, we want to keep these.
            for thisfile in oldfiles:
                cmd = 'rm ' + thisfile
                osCmd(cmd)
                self.Log("Motor.RestoreAngle(", self.MotorName, ") removed old restore file", thisfile,terminal=False)
        return True

    def TuneComplete(self,line):
        """ Process acknowledgement of a completed tuning command.
            Expects input like          tune complete azimuth yyyymmddhhmmss -342        
                                          0     1        2          3          4         . """
        self.Log("Motor",self.MotorName,"received tune acknowledgement:",line,terminal=False)
        lineitems = line.split(" ") # Separate each element of the line. 
        if len(lineitems[3]) >= 14: # *Q* Remove this once the microcontroller software is updated.
            self.LatestTuneTime = MctlStringToDatetime(lineitems[3]) # Element #3 is the timestamp of the last tune command completed.
        else: # Bug in early version of microcontroller software, timestamp returned as integer. Just use current time instead.
            self.LatestTuneTime = NowUTC()
        self.LatestTuneSteps = TextToInt(lineitems[4]) # Element 4 is the number of steps that the tune command executed.

    def StoreRecoveryAngle(self,force=False):
        """ Records the latest position of the motor for recovery purposes. 
            This is appended to self.RecoveryFileName if the position has changed.
            This data is used to restore the state of the motor when the program next restarts. 
            This is designed to retry if there is a file error, just in case there's an access conflict with any other reader/monitor. 
            force=True: A value is stored even if the motor hasn't moved. """
        if force or self.CompareAngles(self.CurrentAngle,self.LastRecoveryAngle) == False: # The motor has actually moved! 
            success = False
            while success == False:
                try:
                    with open(self.RecoveryFileName,'ab',0) as f: # Python3: Don't buffer. Note that the O/S may still have to flush buffers itself.
                        f.write((UtcTimeStamp() + ";" + str(self.CurrentAngle) + ";" + str(int(self.MotorRunningSeconds)) + "\n").encode()) # Convert text to bytes.
                    self.LastRecoveryAngle = self.CurrentAngle
                    success = True
                except Exception as e:
                    self.Log("steppermotor.StoreRecoveryAngle (", self.MotorName, ") to", self.RecoveryFileName, ". File conflict", str(e), "waiting to retry.",level='warning')
                    time.sleep(0.3)

    def GoToAngle(self,newangle):
        """ Trigger 'goto angle' movement of the motor via the remote microcontroller. 
            This version can accept status messages from all motors.
                goto 20210409090949 azimuth 180.0
                    0       1          2      3         """
        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Begin move from ', str(self.CurrentAngle) + DegreeSymbol, 'to', str(round(newangle,3)) + DegreeSymbol, '(', str(self.AngleToStep(newangle) - self.AngleToStep(self.CurrentAngle)) , 'step difference)',terminal=False)
        result = False # Failed until proven otherwise.

        # Clip angles to min/max allowed. The motor won't pass beyond these points, so the routine will wait forever for it to complete.
        if newangle < self.MinAngle:
            self.Log('motorcontrol.GoToAngle(', self.MotorName, '): move limited to minimum', str(self.MinAngle) + DegreeSymbol,terminal=False)
            newangle = self.MinAngle
        if newangle > self.MaxAngle:
            self.Log('motorcontrol.GoToAngle(', self.MotorName, '): move limited to maximum', str(self.MaxAngle) + DegreeSymbol,terminal=False)
            newangle = self.MaxAngle

        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Clear unprocessed messages received from microcontroller.',terminal=False)
        Mctl.ReadFlush() # Reset the input buffers. Scrap anything still waiting to be processed.

        # The following section 'repeats' in the event of the microcontroller resetting during a large move.
        # It repeats until the motor is finally at the target position.
        # Check that the motors are configured before proceeding.
        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Configure motor',terminal=False)
        configtimer = timer(5) # Create a timer for sending and resending configurations to motors.
        loopcounter = 0
        looplimit = 20
        # Keep trying until limit hit, or we are close enough to the target position.
        # - Allow a little tolerance for calculation rounding etc.
        while self.CompareAngles(self.CurrentAngle,newangle,ptolerance=1) == False: # Position tolerance of 1 works best here.
            loopcounter += 1
            while self.MotorConfigured == False: # Send configuration to the motor until it's acknowldeged. (May take a few seconds).
                if configtimer.Due(): self.SendConfig() # Send the motor configuration regularly.
                line = Mctl.Read() # Any response from the microcontroller? 
                lineitems = line.split(' ')
                if line != '':
                    # *Q* Check for consistency with other loops, make sure they all handle the same messages the same way.
                    if line.startswith('session'): pass # Just log these.
                    elif line.startswith('comms'): pass # Just log these.
                    elif line.startswith('controller log'): pass # Just log these.
                    elif line.startswith('cleared trajectory'): pass # Just log these.
                    elif line.startswith('tune complete'): # A tune command has been processed.
                        for i in motorcontrol.AllMotors: # Process responses for ANY motor, not just this one.
                            if i.MotorName == lineitems[2]: i.TuneComplete(line)
                    elif line.startswith('motor'): # Motor Status received, but check it is the right motor.
                        for i in motorcontrol.AllMotors: # Process responses for ANY motor, not just this one.
                            if lineitems[3] == i.MotorName: i.ReceiveStatus(line) # This should set the MotorConfigured flag when it is ready.
                    elif line.startswith('controller started'): 
                        self.Restarted() # Need to mark that the motor is nolonger configured.
                        Mctl.MctlRestarted()
                        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [1] CheckMotorConfig: Microcontroller reports restart. Move incomplete, will retry.',level='error',terminal=True)
                        ErrorWindow.Print(NowHMS() + ' [1] Microcontroller reports restart. Move incomplete, will retry.')
                        break
                    else:
                        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [1] CheckMotorConfig: Ignored microcontroller response:', line,terminal=False)
                if self.MotorConfigured: 
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [1] CheckMotorConfig: Motor reports it is now configured.',terminal=False)
                    break # All motors configured. OK to proceed.
            # Motor is now configured. Perform the actual move now. 
            self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Begin the move.',terminal=False)
            # Generate the GOTO command.
            line = 'goto '
            line += CleanDatetimeString(NowUTC()) + ' ' 
            line += self.MotorName + ' ' 
            line += str(newangle) + ' '
            Mctl.Write(line) # Send GO TO command.
            # Wait for movement to complete.
            prevangle = None # Monitor changes in angle. If it doesn't change for a while, consider something went wrong.
            prevangletime = NowUTC()
            while True:
                # Check for comms from microcontroller.
                line = Mctl.Read()
                if line != '':
                    lineitems = line.split(' ')
                    # *Q* Check for consistency with other loops, make sure they all handle the same messages the same way.
                    if line.startswith('session'): pass # *Q* Should do something with this.
                    elif line.startswith('comms'): pass # *Q* Should do something with this.
                    elif line.startswith('controller log'): pass # Just log these.
                    elif line.startswith('cleared trajectory'): pass # Just log these.
                    elif line.startswith('motor'): # Motor status.
                        if lineitems[3] == self.MotorName: # Status for this current motor.
                            self.ReceiveStatus(line)
                            self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [2] Currently at', str(self.CurrentAngle) + DegreeSymbol, "vs", str(round(newangle,3)) + DegreeSymbol + ' (' + str(self.AngleToStep(newangle) - self.AngleToStep(self.CurrentAngle)) + ' step difference)',terminal=False)
                            if prevangle != self.CurrentAngle: # The motor has moved.
                                prevangle = self.CurrentAngle
                                prevangletime = NowUTC()
                        else: # Process status for some other motor. But don't update the movement measures we're using in this routine.
                            for i in motorcontrol.AllMotors:
                                if i.MotorName == lineitems[3]:
                                    i.ReceiveStatus(line)
                                    self.Log('motorcontrol.GoToAngle(', i.MotorName, '): [2] Currently at', str(i.CurrentAngle) + DegreeSymbol, "vs", str(round(newangle,3)) + DegreeSymbol + ' (' + str(i.AngleToStep(newangle) - i.AngleToStep(i.CurrentAngle)) + ' step difference)',terminal=False)
                            # Received status for another motor. Ignore it for now.
                            self.Log('motorcontrol.GoToAngle(): [2] Ignored status from another motor: ' + line,terminal=False)
                    elif line.startswith('controller started') or self.MotorConfigured != True:
                        self.Restarted() # Need to mark that the motor is nolonger configured.
                        Mctl.MctlRestarted()
                        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [2] PerformMove. Microcontroller restarted or configuration lost. Attempt', loopcounter,'of',looplimit,'.',level='error',terminal=True)
                        ErrorWindow.Print(NowHMS() + ' [2] Microcontroller restarted or configuration lost. GoToAngle failed.')
                        break # The microcontroller restarted during the move. Start again...
                    elif line.startswith('goto rejected'):
                        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [2] Microcontroller rejected the move:',line,level='error')
                        ErrorWindow.Print(NowHMS() + ' GoToAngle Microcontroller rejected the move: ' + line)
                        break # The microcontroller rejected the command, possibly due to restart or missing config. Try again.
                    else: self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [2] Ignored Microcontroller response:',line,terminal=False)
                    if self.CompareAngles(self.CurrentAngle,newangle,ptolerance=1): # Sometimes there's a mathematical disagreement between microcontroller and this software. So allow a small tolerance when comparing angles.
                        # Move complete.
                        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): CompareAngles considers position is within tolerance, move can be considered complete.',terminal=False)
                        result = True # Success.
                        break
                    if (NowUTC() - prevangletime).total_seconds() > 30: # The angle hasn't changed for 30 seconds. Consider something's wrong.
                        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): [2] Angle has not changed for over 60 seconds. Considering the move failed.',level='error')
                        ErrorWindow.Print(NowHMS() + ' [2] motor movement stalled. GoToAngle failed.')
                        break
                time.sleep(0.01) # Don't poll too often.
            if loopcounter >= looplimit: 
                self.Log("motorcontrol.GoToAngle(", self.MotorName, "): After",looplimit,"attempts, motor still not homed. Abandoning the move at", self.CurrentAngle, DegreeSymbol, ".",level='error')
                break
        # *Q* If the motor is already within tolerance but not precisely in position, you can get a fake error here. 
        # This is typically when you're asking it to move a single motor step in isolation.
        # In practice this is because the motor won't be asked to move if it's already within tolerance.
        # Low priority, it's only happend 1 time in 2 years.
        # - Workarounds:-
        #   Move both motors by 10Degrees in any direction, which will increase the positions beyond the tolerances to allow homing again.
        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Move completed:', str(self.CurrentAngle) + DegreeSymbol, "vs", str(round(newangle,3)) + DegreeSymbol,terminal=False)
        return result # Did we succeed?

    def ReceiveStatus(self,line):
        """ Receive Status of a motor and store important parameters
            in this local motor image. 
        Sample message:-
            motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
              0      1          2           3   4         5      6   7     8   9
        2: IntToTimeString(Clock.Now()) Current local timestamp.
        3: self.MotorName
        4: BoolToString(self.Trajectory.Valid) TrajectoryValid
        5: self.Trajectory.ValidUntilString() 
        6: str(len(self.Trajectory.TrajectoryList)) 
        7: str(self.CurrentPosition)
        8: str(self.CurrentAngle) 
        9: BoolToString(self.MotorConfigured) MotorConfigured
        10: BoolToString(self.OnTarget) Motor is on target.
        11: str(self.WaitTime) Current speed of motor.
        12: str(VMot()) Current motor power supply voltage.
                                                                       """
        lineitems = line.split(' ')
        self.TrajectoryValid = StringToBool(lineitems[4])
        self.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
        self.TrajectoryEntries = int(lineitems[6])
        self.MotorConfigured = StringToBool(lineitems[9])
        if self.MotorConfigured: # Only believe the angle once the motor is configured.
            self.CurrentAngle = float(lineitems[8])
            self.StoreRecoveryAngle() # Record the latest position of the motor for restart/recovery later.
        self.OnTarget = StringToBool(lineitems[10]) # Is the motor on target?
        return True

    def SendConfig(self):
        """ Send configuration information from this motor image to the microcontroller
            where it will be loaded into the motor control there. 
                configure motor 20210409090949 azimuth 180.0 45.0 315.0 0.5 -1 0.0005 0.01 0.0005
                    0       1          2          3      4    5     6    7   8   9      10   11  """
        self.Log('motorcontrol.SendConfig (' + self.MotorName + ') begin',terminal=False)
        line = 'configure motor ' # Fields 0 & 1
        line += CleanDatetimeString(NowUTC()) + ' ' # Field 2 
        line += self.MotorName + ' '# Field 3 
        line += str(self.CurrentAngle) + ' ' # Field 4: Remind the motor where it is according to its last report.
        line += str(self.MinAngle) + ' ' # Field 5: Send the minimum movement position. Will override the default on the microcontroller.
        line += str(self.MaxAngle) + ' ' # Field 6: Send the maximum movement position. Will override the default on the microcontroller.
        line += str(self.BacklashAngle) + ' ' # Field 7: Send the backlash angle. Will override the default on the microcontroller.
        line += str(self.Orientation) + ' ' # Field 8: Send the orientation of the motor. Will override the default on the microcontroller.
        line += str(self.FastTime) + ' ' # Field 9: Send the FAST motor pulse limit.
        line += str(self.SlowTime) + ' ' # Field 10: Send the SLOW motor pulse limit.
        line += str(self.TimeDelta) + ' ' # Field 11: Send the motor pulse acceleration unit.
        Mctl.Write(line)
        return True

    def StepToAngle(self, steps=0):
        """ Convert a number of steps to a final angle (0-360) of movement. """
        # Change number of steps into an angle (will be decimal result)
        return steps * 360 / float(self.AxisStepsPerRev)
    
    def AngleToStep(self, deg=0.0):
        """ Convert a final angle of movement to the nearest whole number of motor steps. """
        # Change angle into a number of steps (will be rounded integer result)
        return int(round(deg * float(self.AxisStepsPerRev) / 360,0))

    def TunePosition(self,delta):
        """ Tune the motor position (motor steps). This corrects the position of the motor/telescope
            without registering a change in the direction it is currently pointing. 
            Use this for drift adjustment or manual finetuning of the telescope position during setup or after problems.
            tune 20210410154530 azimuth -234
              0        1           2      3            """
              
              
        # This first makes sure that the motor is configured, it waits for that to be acknowledged before sending the tune command.
        # Check that the motors are configured before proceeding.
        self.Log('motorcontrol.TunePosition(', self.MotorName, '): Configure motor.',terminal=False)
        configtimer = timer(5) # Create a timer for sending and resending configurations to motors.
        # There can be input queued from the microcontroller waiting to be handled.
        # - We should check in case the motor has lost its configuration before proceeding.
        self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Precheck motor is still configured.',terminal=False)
        line = Mctl.Read()
        while line != '':
            lineitems = line.split(' ')
            if line.startswith('motor'): # Motor Status received, but check it is the right motor.
                if lineitems[3] == self.MotorName:
                    self.ReceiveStatus(line) # This should set the MotorConfigured flag when it is ready.
                else:
                    self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Ignored status message from', lineitems[3], 'motor.',terminal=False)
            elif line == 'controller started': 
                self.Restarted() # Need to mark that the motor is nolonger configured.
                Mctl.MctlRestarted()
                self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Microcontroller reports restart. Will resend config.',level='error')
                ErrorWindow.Print(NowHMS() + ' Microcontroller reports restart. Will resend config.')
            else: pass # All other input is ignored and just logged.
            line = Mctl.Read() # Check for further input. 
        while self.MotorConfigured == False:
            if configtimer.Due(): 
                self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Sending motor configuration...',terminal=False)
                self.SendConfig()
            line = Mctl.Read() # Pull latest message received from microcontroller (if any).
            lineitems = line.split(' ') # Separate out the terms of the message.
            if line != '': # Is there a message to process?
                # *Q* Check for consistency with other loops, make sure they all handle the same messages the same way.
                if line.startswith('session'): pass # Just log these.
                elif line.startswith('comms'): pass # Just log these.
                elif line.startswith('controller log'): pass # Just log these.
                elif line.startswith('cleared trajectory'): pass # Just log these.
                elif line.startswith('motor'): # Motor Status received, but check it is the right motor.
                    if lineitems[3] == self.MotorName:
                        self.ReceiveStatus(line) # This should set the MotorConfigured flag when it is ready.
                    else:
                        self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Ignored status message from', lineitems[3], 'motor.',terminal=False)
                elif line.startswith('tune complete'): # A tune command has been processed.
                    if self.MotorName == lineitems[2]:
                        self.TuneComplete(line)
                elif line == 'controller started': 
                    self.Restarted() # Need to mark that the motor is nolonger configured.
                    Mctl.MctlRestarted()
                    self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Microcontroller reports restart. Will resend config.',level='error')
                    ErrorWindow.Print(NowHMS() + ' Microcontroller reports restart. Will resend config.')
                else:
                    self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Ignored microcontroller response:', line)
            if self.MotorConfigured: 
                self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Motor reports it is now configured.',terminal=False)
                break # All motors configured. OK to proceed.
        # Motor is now configured. Perform the actual move now. 
        if self.MotorConfigured: # Only allow tuning if the motor is configured.
            dtn = NowUTC()
            line = "tune " + CleanDatetimeString(str(dtn)) + ' ' + self.MotorName + " " + str(delta)
            Mctl.Write(line)
            # This doesn't wait for feedback, it is up to the motorcontroller to deal with the message when it sees fit.
            # This program may send further tune messages if it still needs to change things.
        else:
            self.Log("motorcontroller.TunePosition(", self.MotorName, "): Motor is not yet configured. Tune command will not be sent.",level='error')

    def ExtendTrajectory(self,targetobj): 
        """ Generate next trajectory segment and send it. 
        
            The trajectory is a series of short straight line movements chained together to create a path across the sky.
            Each segment is a simple straight line, it is short enough that it equates to a tiny part of the arc that is actually being followed.
            The segment is short enough that it is indistinguishable from the true curve when converted into motor positions.
            
            This generates a single segment. A single small straight line movement that the motors must follow.
        
            Works in 2 modes.
            - Dynamic and static: 
                Static means each segment of the trajectory is the same length of time. Typically very short.
                Dynamic means that segments can vary in the time span to minimise the number of segments that need to be passed to the microcontroller.
                    Dynamic extends the length of each straight line segment as far as possible while still remaining close to the trajectory arc through the sky. 
            
            *Q*: Experiments suggest that trajectory can be very efficiently represented by angular accelerations rather than specific positions.
                 But this needs more work yet. Both the encoding here, and the decoding in the microcontroller need to be developed.
              
        
            trajectory 20210409104504 azimuth 20210325223342 181.6003 20210325223442 181.7003
                0             1          2           3          4            5           6
                                                                                                      """
        line = 'trajectory '
        nowutc = NowUTC()
        segmentsize = self.TrajectorySegmentSize # How long does a trajectory segment last? (seconds)
        line += CleanDatetimeString(str(nowutc)) + ' ' # Timestamp must be current even if resending cached records.
        if self.TrajectoryValidUntil == None:
            startutc = nowutc
        else:
            startutc = self.TrajectoryValidUntil
        if self.LastSentTrajectoryKey == self.TrajectoryValidUntil: # We have a result cached already for this...
            self.Log('motorcontroller.ExtendTrajectory(', self.MotorName, '): Using cached trajectory calculation:', "'" + self.LastSentTrajectoryData + "'",terminal=False)
            line += self.LastSentTrajectoryData
            Mctl.Write(line)
            return # No need to process further.
        # We're not using a cached record, so continue constructing and calculating a new record.
        line += self.MotorName + ' '
        if startutc < nowutc: # Don't create OLD entries.
            startutc = nowutc
        # Calculate START angle for trajectory segment.
        az, alt = targetobj.AzAltDegrees(time=targetobj.ConvToTS(startutc)) # Needs to be Skyfield time!
        line += CleanDatetimeString(str(startutc)) + ' '
        if self.MotorName == 'altitude': startangle = alt
        else: startangle = az
        line += str(startangle) + ' '
        if targetobj.IsFixedPoint(): # Fixed points can have a larger segment size.
            endutc = startutc + timedelta(seconds=segmentsize * 2) # But not too large because we need multiple segments queued up on the microcontroller, otherwise it may send an off target signal if the trajectory list expires.
        else: 
            endutc = startutc + timedelta(seconds=segmentsize)
        # Calculate END angle for trajectory segment.
        az, alt = targetobj.AzAltDegrees(time=targetobj.ConvToTS(endutc)) # Needs to be Skyfield time! 
        if self.MotorName == 'altitude': endangle = alt
        else: endangle = az
        gradient = (endangle - startangle) / segmentsize # What's the gradient of this trajectory segment We can try to extend its validity.
        # DynamicTrajectoryPeriods:
        # - If enabled: Each segment of the trajectory extends over a variable period of time.
        #               This is to maximise movement and minimise the number of trajectory segments required.
        #               There's a small loss of precision as a result. But should be too small to notice.
        # - If disabled: Each segment of the trajectory extends over a fixed period of time.
        #               This is slightly more precise, but has more segments to pass to the microcontroller.
        if Parameters.UseDynamicTrajectoryPeriods and targetobj.IsFixedPoint() == False: # Cannot solve dynamic trajectories for fixed points!
            # We have the 'fixed time period' trajectory extent already calculated. 
            # Maximise the time period for this extent so that we don't need to pass as many segments to the microcontroller.
            MaxIterations = 100 # Always quit once MaxIterations hit.
            #while True:
            while MaxIterations > 0: # Time out if max iterations hit.
                MaxIterations -= 1 # Reduce timeout.
                segmentsize += int(self.TrajectorySegmentSize / 4) # Increase the segment size.
                nextutc = startutc + timedelta(seconds=segmentsize) # Timestamp of the larget segment size.
                az, alt = targetobj.AzAltDegrees(time=targetobj.ConvToTS(nextutc)) # Needs to be Skyfield time!
                if self.MotorName == 'altitude': nextangle = alt
                else: nextangle = az
                if self.MinAngle > nextangle or self.MaxAngle < nextangle: break # Cannot extend any further.
                projectedangle = startangle + (gradient * segmentsize) # What would the position be with the original gradient?
                angledrift = abs(nextangle - projectedangle) # How much drift would there be from the minimum timeslot if we just used that original gradient?
                if angledrift <= 0.005: # We can extend the time period if we remain close enough to the gradient of the minimum segment size.
                                        # *Q* This tolerance could be measured in terms of a pixel in the camera, that's possibly what counts.
                    endangle = nextangle
                    endutc = nextutc
                else: # The extended period would drift too far. Don't try anything larger.
                    break
            if MaxIterations <= 0: # Iteration limit hit!
                self.Log('motorcontroller.ExtendTrajectory(', self.MotorName, '): MaxIterations hit. Segment artificially limited to', endutc,terminal=False)
        line += CleanDatetimeString(str(endutc)) + ' '
        line += str(endangle) + ' '
        if endangle >= self.MinAngle and endangle <= self.MaxAngle: # We're still within range.
            Mctl.Write(line)
            self.LastSentTrajectoryKey = self.TrajectoryValidUntil # Cache the trajectory calculation, if the same calculation is triggered, we can re-use the earlier copy for speed.
            self.LastSentTrajectoryData = line[26:] # Store the data sent (without the leading timestamp, that needs recreating if resent). 
            self.Log('motorcontroller.ExtendTrajectory(', self.MotorName, '): Cached trajectory calculation:', "'" + self.LastSentTrajectoryData + "'",terminal=False)
        else:
            self.Log('motorcontroller.ExtendTrajectory(' + self.MotorName + '): Trajectory is now complete.',terminal=False)

# ------------------------------------------------------------------------------------------------------

AzimuthControl = motorcontrol('azimuth',gearratio=240,motorstepsperrev=400,microstepratio=1,minangle=Parameters.MinAzimuthAngle,maxangle=Parameters.MaxAzimuthAngle,restangle=180.0,currentangle=180.0,backlashangle=0.0,orientation=-1)
AltitudeControl = motorcontrol('altitude',gearratio=240,motorstepsperrev=400,microstepratio=1,minangle=Parameters.MinAltitudeAngle,maxangle=Parameters.MaxAltitudeAngle,restangle=0.0,currentangle=0.0,backlashangle=0.0,orientation=-1)
MotorControls = motorcontrol.AllMotors #  Alias for the list of ALL defined motors held in the motorcontrol class.

# ------------------------------------------------------------------------------------------------------

def CurrentAltAz(): # 7 references.
    """ Retrieve the current physical position of the camera. 
        Returns values based upon the data stored in the MotorControl objects. """
    az_degree = 0.0
    alt_degree = 0.0
    for i in MotorControls:
        if i.MotorName == "azimuth": az_degree = i.CurrentAngle
        elif i.MotorName == "altitude": alt_degree = i.CurrentAngle
    return alt_degree, az_degree

# ------------------------------------------------------------------------------------------------------

def HomeAltAz(): # 1 references.
    """ Return the home positions of the motors. """
    HomeAlt = HomeAz = 0.0
    for i in MotorControls:
        if i.MotorName == "altitude": HomeAlt = i.RestAngle
        elif i.MotorName == "azimuth": HomeAz = i.RestAngle
    return HomeAlt, HomeAz

# ------------------------------------------------------------------------------------------------------

# Calculate some useful conversion factors from the various elements defined.
# Calculate these once now instead of repeatedly during future calculations.
for i in MotorControls:
    if i.MotorName == "azimuth": az_pixels_per_fullstep = float(CameraInUse.PixelsPerFovDegreeWidth) / (i.MotorStepsPerAxisDegree * i.GearRatio)
    elif i.MotorName == "altitude": alt_pixels_per_fullstep = float(CameraInUse.PixelsPerFovDegreeHeight) / (i.MotorStepsPerAxisDegree * i.GearRatio)

#--------------------
# Observation session
#--------------------

class sessionstatus(attributemaster): # 1 references.
    """ Class to hold current status of the observation.
        This can export all the status information to a file so that a remote process can also monitor the status.
        These are the variables that handle a single loop in the ObservationRun routine. """
    def __init__(self):
        """ Initialize status fields. """
        self._FileNames = []
        self.ProgramStartTime = NowUTC() # When the program starts.
        self.Target = None # No target yet. This gets set to a valid target object when the target is selected.
        self.Log = MainLog.Log # Handle to the logging function used by this class.
        self.AutonomousControl = False # Is the Microcontroller controlling its own movements?
        self.RemoteControl = False # Will the Microcontroller accept remote control (from here)?
        self.ClockSynchronised = False # Has the Microcontroller synchronised the clock?
        self.MctlRxErrors = 0 # How many messages has the Microcontroller rejected? (Checksum errors)
        self.MctlRxBytes = 0 # How many bytes has the Microcontroller received?
        self.MctlTxBytes = 0 # How many bytes has the Microcontroller sent?
        self.MctlLifeSeconds = 0 # How many seconds has the Microcontroller been running for?
        self.MctlWriteDrops = 0 # How many messages were dropped from send buffer on Microcontroller due to overflow?
        self.MotorControlMode = 'idle' # What mode are we in? 'idle'/'remote'/'autonomous'. This controls the responses to some automated status messages. *Q* Is this needed anymore?
        self.MCMdict = {'idle' : {'description' : 'motors at rest.', 'trajectory' : False},
                        'direct' : {'description' : 'motor movement controlled directly from this software.', 'trajectory' : False},
                        'trajectory' : {'description' : 'motor movement is autonomous following trajectory.', 'trajectory' : True}}
        self.MaintainTrajectory = None
        self.SetMotorControlMode(self.MotorControlMode) # Updates self.MaintainTrajectory

    def Reset(self):
        self.AutonomousControl = False # Is the Microcontroller controlling its own movements?
        self.RemoteControl = False # Will the Microcontroller accept remote control (from here)?
        self.ClockSynchronised = False # Has the Microcontroller synchronised the clock?
        self.MctlRxErrors = 0 # How many messages has the Microcontroller rejected? (Checksum errors)
        self.MctlRxBytes = 0 # How many bytes has the Microcontroller received?
        self.MctlTxBytes = 0 # How many bytes has the Microcontroller sent?
        self.MctlLifeSeconds = 0 # How many seconds has the Microcontroller been running for?        
        self.MctlWriteDrops = 0 # How many messages were dropped from send buffer on Microcontroller due to overflow?
        self.MotorControlMode = 'idle' # What mode are we in? 'idle'/'remote'/'autonomous'. This controls the responses to some automated status messages.
        self.SetMotorControlMode(self.MotorControlMode) # Updates self.MaintainTrajectory

    def SetMotorControlMode(self,mode):
        """ Change the control mode of the motors.
            Supported modes are listed in self.MCMdict.
            - That defines how the session automatically responds to status messages received from the microcontroller. """
        if mode in self.MCMdict:
            self.Log('sessionstatus:SetMotorControlMode(' + mode + ') from ' + self.MotorControlMode + ' to ' + mode,terminal=False)
            self.Log('sessionstatus:SetMotorControlMode(' + mode + ') ' + self.MCMdict[mode]['description'],terminal=False)
            self.MotorControlMode = mode
            self.MaintainTrajectory = self.MCMdict[mode]['trajectory']
        else:
            self.Log('sessionstatus.SetMotorControlMode(' + mode + ') is not recognised.',level='error')

    def CheckMotorConfig(self,line):
        """ Check the Microcontroller's status message to see if the motors are configured.
            If they are not, then send the configuration immediately. 
            #  From Microcontroller to RPi
            #   motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
                  0     1           2          3    4     5          6   7     8   9
                                                                                            """
        lineitems = line.split(' ')
        motorname = lineitems[3]
        foundit = False
        for i in MotorControls:
            if motorname == i.MotorName:
                mc = StringToBool(lineitems[9])
                foundit = True
                if mc == False: # Motor is not yet configured. Do so now.
                    self.Log('CheckMotorConfig: Sending config for ' + i.MotorName + ' motor to Microcontroller.',terminal=False)
                    i.SendConfig() # Send initial information to the motor.
                else: # Motor is configured, accept its latest status.
                    i.ReceiveStatus(line)
        if not foundit: # The motor name was not recognised.
            self.Log('sessionstatus.CheckMotorConfig did not recognise the motor name (',motorname, ')', level='error')

    def CheckSessionStatus(self,line):
        """ Check the Microcontroller's status message to see if the session is configured. 
            If the time needs synchronising, do that immediately. 
                 session status 20210409090929 n n False 20 None None
                    0      1           2       3 4   5   6   7     8                           
        2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        3: BoolToString(Clock.ClockSynchronised) Do the RPi and Microcontroller clocks agree?
        4: BoolToString(self.AutonomousControl) Can motors drive themselves? Fully configured and trajectory known.
        5: BoolToString(self.RemoteControl) Can motors be commanded remotely? Fully configured.
        6: str(utime.time() - RPi.StartTime) Alive seconds. """
        lineitems = line.split(' ')
        self.ClockSynchronised = StringToBool(lineitems[3])
        self.AutonomousControl = StringToBool(lineitems[4])
        self.RemoteControl = StringToBool(lineitems[5])
        self.MctlLifeSeconds = int(lineitems[6])
        if self.ClockSynchronised == False: # Clock has not yet been synchronised.
            # Synchronise clocks.
            line = 'set time ' + CleanDatetimeString(str(NowUTC()))
            Mctl.Write(line)

    def CheckCommsStats(self,line):
        """ Check the Microcontroller's comms status message for stats.
                   comms status 20210409090929 0 0 538 0
                    0      1           2       3 4  5  6
        2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        3: str(RPi.MctlRxErrors) How many messages were rejected from RPi by Microcontroller.
        4: str(RPi.CharactersRead) How many bytes received from RPi by Microcontroller.
        5: str(RPi.CharactersWritten) How many bytes written by Microcontroller to RPi.
        6: str(RPi.WriteDrops) How many messages were dropped due to buffer overflow?  """
        lineitems = line.split(' ')
        self.MctlRxErrors = int(lineitems[3])
        self.MctlRxBytes = int(lineitems[4])
        self.MctlTxBytes = int(lineitems[5])
        self.MctlWriteDrops = int(lineitems[6])

    def CheckTrajectory(self,line,targetobj): # Needs reworking for actual Skyfield trajectory.
        """ Check the Microcontroller's status message to see if the trajectory is known.
            If it is not known far enough into the future, extend it by a single 'TrajectoryPoint'
            when that one is confirmed back by the Microcontroller, we may add another... 

            motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
            2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
            3: self.MotorName + ' ' 
            4: BoolToString(self.Trajectory.Valid) + ' ' # TrajectoryValid
            5: self.Trajectory.ValidUntilString() + ' '
            6: str(len(self.Trajectory.TrajectoryList)) + ' '
            7: str(self.CurrentPosition) + ' '
            8: str(self.CurrentAngle) + ' '
            9: BoolToString(self.MotorConfigured) + ' ' # MotorConfigured  """
        lineitems = line.split(' ')
        # This should only send a trajectory update IF we're TRACKING something!
        # *Q* Performance issue. If we receive multiple copies of the same status message, this routine can be called multiple times.
        # - This means a heavy calculation is repeated probably unneccessarily. Can the result be cached and re-used in the event of repeats?
        # - This has caused excessive obvservation loop times of 30seconds per loop.
        if self.MaintainTrajectory:
            for i in MotorControls:
                if i.MotorName == lineitems[3]:
                   i.TrajectoryEntries = int(lineitems[6])
                   i.TrajectoryValid = StringToBool(lineitems[4])
                   i.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
                   duration = i.TrajectoryValidUntil - NowUTC()
                   self.Log('sessionstatus.CheckTrajectory: Examining', i.MotorName, ', Entries', i.TrajectoryEntries, ', ValidUntil', i.TrajectoryValidUntil, ', Valid',i.TrajectoryValid, ', duration',duration.total_seconds(), ', Window', Parameters.TrajectoryWindow, ', ClkSync', self.ClockSynchronised,terminal=False)
                   if duration.total_seconds() < Parameters.TrajectoryWindow and self.ClockSynchronised: # We need to add time to the trajectory plan.
                       self.Log('sessionstatus.CheckTrajectory: Decided to extend.',terminal=False)
                       i.ExtendTrajectory(targetobj)
                   else: self.Log('sessionstatus.CheckTrajectory: Decided not to extend.',duration.total_seconds(),Parameters.TrajectoryWindow,self.ClockSynchronised,terminal=False)
        else: self.Log('sessionstatus.CheckTrajectory: Not currently maintaining trajectories on microcontroller.',terminal=False)

    def MctlInput(self,targetobj,timeout=120):
        """ This handles data received from the Microcontroller.
            It uses 'targetobj' to provide trajectory information if the motor needs it. 
            Timeout parameter limits the time spent processing lines. Give value in seconds.
            *NOTE* Timeout parameter is NOT the amount of time spent WAITING for something to arrive. """
        exittime = NowUTC() + timedelta(seconds=timeout)
        while len(Mctl.Lines) > 0: # Clear all queued input.
            if NowUTC() > exittime: 
                self.Log('sessionstatus.MctlInput: Timeout hit. Not all received lines have been processed yet.',terminal=False)
                break # Timeout hit before all lines processed.
            line = Mctl.Read()
            # *Q* Check that this loop is consistent with others that need to handle Microcontroller responses. Are all the same messages received, processed, logged, ignored in the same way?
            if len(line) > 0: # Data to process.
                if line.startswith('session'): 
                    self.CheckSessionStatus(line)
                elif line.startswith('comms'): 
                    self.CheckCommsStats(line)
                elif line.startswith('controller log'): pass # Just log these.
                elif line.startswith('motor'): 
                    self.CheckMotorConfig(line)
                    self.CheckTrajectory(line,targetobj) # *Q* Performance issue here, if several status lines come together, this repeats a heavy calculation needlessly. Cache result?
                elif line.startswith('controller heartbeat'): pass # These messages just keep the line alive.
                elif line.startswith('heartbeat'): pass # These messages just keep the line alive.
                elif line.startswith('tune complete'): # A tune command has been processed.
                    for i in MotorControls:
                        if i.MotorName == line.split(" ")[2]:
                            i.TuneComplete(line)
                elif line == 'controller started': 
                    Mctl.MctlRestarted()
                    for i in MotorControls:
                        i.Restarted() # Need to mark that the motor is nolonger configured.
                    self.Log('sessionstatus:MctlInput(): Microcontroller reports restart.',terminal=False)
                    ErrorWindow.Print(NowHMS() + ' Microcontroller reports restart.')

    def ShowRemoteStatus(self):
        """ Display status from Microcontroller """
        # Microcontroller communications
        SessionWindow.Clear(immediate=False)
        SessionWindow.FieldValue('RQ',len(Mctl.Lines)) # Messages: Rx queued
        SessionWindow.FieldValue('RT',Mctl.LinesReceived) # Messages: Rx total
        SessionWindow.FieldValue('TQ',len(Mctl.WriteQueue)) # Messages: Tx queued
        SessionWindow.FieldValue('TT',Mctl.LinesSent) # Messages: Tx total
        SessionWindow.FieldValue('SR',Mctl.ResetAttempts) # Reset attempts
        SessionWindow.RangeFieldColor('SR',lowlow=-100,low=-10,high=1,highhigh=100) # Anything >= 1 is a POOR value.
        SessionWindow.FieldValue('DF',Mctl.DeviceFailure) # Device failure flag
        if Mctl.DeviceFailure: SessionWindow.FieldColor('DF',fg=OSW_TEXT_BAD)
        else: SessionWindow.FieldColor('DF',fg=OSW_TEXT_GOOD)
        SessionWindow.FieldValue('LR',str(Mctl.LastRxTime).split('.')[0].split(' ')[1]) # Last message received.
        SessionWindow.FieldValue('BX',HRBytes(Mctl.BytesReceived)) # RPi measure of bytes received.
        SessionWindow.FieldValue('TX',HRBytes(Mctl.BytesSent)) # RPi measure of bytes sent.
        SessionWindow.FieldValue('RE',Mctl.RxErrors) # RPi measure of receive errors.
        SessionWindow.RangeFieldColor('RE',lowlow=-100,low=-10,high=1,highhigh=100) # Anything >= 1 is a POOR value.
        if self.MctlLifeSeconds > 0: # Microcontroller comms stats, including rate.
            rbps = int(self.MctlRxBytes / self.MctlLifeSeconds)
            tbps = int(self.MctlTxBytes / self.MctlLifeSeconds)
            SessionWindow.FieldValue('MRX',HRBytes(self.MctlRxBytes)) # Microcontroller measure of bytes received.
            SessionWindow.FieldValue('MRXR',HRBytes(rbps) + "/s") # receive rate.
            SessionWindow.FieldValue('MTX',HRBytes(self.MctlTxBytes)) # Microcontroller measure of bytes sent.
            SessionWindow.FieldValue('MTXR',HRBytes(tbps) + "/s") # send rate.
            SessionWindow.FieldValue('TD',self.MctlWriteDrops) # Microcontroller transmit drop count.
        else: # Microcontroller comms stats, excluding rate.
            SessionWindow.FieldValue('MRX',HRBytes(self.MctlRxBytes)) # Microcontroller measure of bytes received.
            SessionWindow.FieldValue('TRX',HRBytes(self.MctlTxBytes)) # Microcontroller measure of bytes sent.
        SessionWindow.FieldValue('R2',self.MctlRxErrors) # Microcontroller receive errors.
        SessionWindow.RangeFieldColor('R2',lowlow=-100,low=-10,high=1,highhigh=100) # Anything >= 1 is a POOR value.
        SessionWindow.FieldValue('AC',self.AutonomousControl) # Flag to show microcontroller allows autonomous control.
        if self.AutonomousControl: SessionWindow.FieldColor('AC',fg=OSW_TEXT_GOOD)
        else: SessionWindow.FieldColor('AC',fg=OSW_TEXT_POOR)
        SessionWindow.FieldValue('RCL',self.RemoteControl) # Flag to show microcontroller allows remote control.
        if self.RemoteControl: SessionWindow.FieldColor('RCL',fg=OSW_TEXT_GOOD)
        else: SessionWindow.FieldColor('RCL',fg=OSW_TEXT_BAD)
        SessionWindow.FieldValue('CS',self.ClockSynchronised) # Flag to show that microcontroller flag is synchronised.
        if self.ClockSynchronised: SessionWindow.FieldColor('CS',fg=OSW_TEXT_GOOD)
        else: SessionWindow.FieldColor('CS',fg=OSW_TEXT_BAD)
        SessionWindow.FieldValue('FR',Mctl.ForcedRestarts) # Count of FORCED restarts triggered by RPi.
        SessionWindow.RangeFieldColor('FR',lowlow=-100,low=-10,high=1,highhigh=100) # Anything >= 1 is a POOR value.
        SessionWindow.FieldValue('RR',Mctl.RemoteRestarts) # Count of REMOTE restarts triggered by microcontroller.
        SessionWindow.RangeFieldColor('RR',lowlow=-100,low=-10,high=1,highhigh=100) # Anything >= 1 is a POOR value.
        SessionWindow.FieldValue('ALIVE',HRSeconds(self.MctlLifeSeconds)) # How long since last microcontroller restart.
        for i in MotorControls: # Report trajectory information for each motor.
            if i.MotorName == 'azimuth': fnp = 'Z'
            else: fnp = 'L'
            SessionWindow.FieldValue(fnp + 'C',i.MotorConfigured)
            if i.MotorConfigured: SessionWindow.FieldColor(fnp + 'C',fg=OSW_TEXT_GOOD)
            else: SessionWindow.FieldColor(fnp + 'C',fg=OSW_TEXT_POOR)
            SessionWindow.FieldValue(fnp + 'A',"{:07.3f}".format(i.CurrentAngle) + DegreeSymbol)
            SessionWindow.FieldValue(fnp + 'T',i.OnTarget)
            if i.OnTarget: SessionWindow.FieldColor(fnp + 'T',fg=OSW_TEXT_GOOD)
            else: SessionWindow.FieldColor(fnp + 'T',fg=OSW_TEXT_POOR)
            if Parameters.UseDynamicTrajectoryPeriods:
                SessionWindow.FieldValue(fnp + 'MODE','Dynamic trajectory')
            else:
                SessionWindow.FieldValue(fnp + 'MODE',"Fixed trajectory")
            SessionWindow.FieldValue(fnp + 'D',i.TrajectoryEntries)
            if i.TrajectoryEntries > 0: SessionWindow.FieldColor(fnp + 'D',fg=OSW_TEXT_GOOD)
            else: SessionWindow.FieldColor(fnp + 'D',fg=OSW_TEXT_POOR)
            temp = str(i.TrajectoryValidUntil) # Calculate the valid until time of the trajectory for this motor.
            if ' ' in temp: # Cut the value down to just the 'time' if possible.
                temp = temp.split(' ')[1]
                if '+' in temp:
                    temp = temp.split('+')[0]
            SessionWindow.FieldValue(fnp + 'U',temp)

Session = sessionstatus() # Create new session status object.

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Image processing (OpenCV) 
# ///////////////////////////////////////////////////////////////////////////////////

class imagetracker(attributemaster): # 1 references.
    """ ImageTracker uses OpenCV and AstroAlign packages to measure the drift of the 
        stars between images. This may be useful for autocorrecting position or basic image tracking. """
        
    def __init__(self):
        self.Log = CamLog.Log # Handle to the function for logging messages by this class.

        self.TargetImage = None # This will be the opencv image buffer.
        self.TargetTimeStamp = None # UTC timestamp for image buffer.
        self.TargetStarCount = 0 # How many stars in self.TargetImage ?
        self.TargetStarList = [] # List of star locations and sizes (centre x,centre y,radius)

        self.LatestImage = None # This will be the opencv image buffer.
        self.LatestTimeStamp = None # UTC timestamp for the image buffer.
        self.LatestStarCount = 0 # How many stars in self.LatestImage ?
        self.LatestStarList = [] # List of star locations and sizes (centre x,centre y,radius)

        self.TrackingInterval = Parameters.TrackingInterval # Check target tracking every nnn seconds.

        self.dx = None # Measured delta-x between images.
        self.dy = None # Measured delta-y between images.
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None # Total seconds between reference images.


        self.imagepc = 100 # Percent scale for images when stored and processed. Smaller is faster but less precise. Find a good balance.
                           # NOTE: As the image scale changes, the CountStars() method's min/max thresholds may need adjusting.
        self.PreparedImages = 0 # Incrementing counter of images handled.
        self.TargetStarMatchList = [] # List of star locations in TargetImage (calculated by FindTransform method)
        self.LatestStarMatchList = [] # List of star locations in LatestImage (calculated by FindTransform method)
        self.TargetMinMagnitude = Parameters.TargetMinMagnitude # The actual minimum star magnitude finally selected for the target image.

    def TrackingAge(self):
        """ Return age of latest tracking image in seconds. """
        td = None
        if self.LatestTimeStamp != None: td = int((NowUTC() - self.LatestTimeStamp).total_seconds())
        return td
                
    def Reset(self):
        """ Reset image cache and related data. """
        self.Log("ImageTracker.Reset: Begin",terminal=False)
        self.TargetImage = None
        self.TargetTimeStamp = None
        self.TargetStarMatchList = []
        self.LatestImage = None
        self.LatestTimeStamp = None
        self.LatestStarMatchList = []
        self.LatestStarCount = 0
        self.BaseImage = None
        self.dx = None # Measured delta-x between images.
        self.dy = None # Measured delta-y between images.
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None # Total seconds between reference images.
        self.Log("ImageTracker.Reset: End",terminal=False)

    def ScaleImage(self,cvimagebuffer):
        """ Take a CVImage buffer and scale it based upon self.imagepc percent. 
            If that is 100% then no scaling is done. 
            Note: The scaling is relative to the SENSOR dimensions, NOT the current image dimensions.
                  This is so that images from multiple sources are all scaled relative to the same standard.
                  Changing the scale may also change the sensitivity of the CountStars() method.                  """
        self.Log("ImageTracker.ScaleImage: Begin",terminal=False)
        if self.imagepc != 100:
            width = int(SensorInUse.PixelWidth * self.imagepc / 100) # Always scale relative to sensor size for consistency.
            if width % 1 == 1: width += 1 # Must be even dimensions.
            height = int(SensorInUse.PixelHeight * self.imagepc / 100) # Always scale relative to sensor size for consistency.
            if height % 1 == 1: height += 1 # Must be even dimensions.
            dim = (width, height)
            self.Log("Imagetracker.ScaleImage: Scaling to h", height, ", w", width,terminal=False)
            cvimagebuffer = cv2.resize(cvimagebuffer, dim, interpolation = cv2.INTER_AREA)
        else:
            self.Log("Imagetracker.ScaleImage: Retaining original 100% scale.",terminal=False)
        self.Log("ImageTracker.ScaleImage: End. Dimensions", cvimagebuffer.shape[0], "*", cvimagebuffer.shape[1],terminal=False)
        return cvimagebuffer

    def CountStars(self,cvimagebuffer,minval=3,maxval=300):
        """ Count the number of stars in an image. 
            From: https://stackoverflow.com/questions/48154642/how-to-count-number-of-dots-in-an-image-using-python-and-opencv
            for 100% scaled image, maxval 300 is good, stars are generally 200pixel areas.
            for 25% scaled image, maxval 20 is good, stars are generally 13pixel areas. """
            
        self.Log("ImageTracker.CountStars: Begin",terminal=False)
        # Make sure image is grayscale.
        if len(cvimagebuffer.shape) == 3:
            if cvimagebuffer.shape[2] == 4: # We have a BGRA image, convert it to grayscale.
                self.Log("ImageTracker.CountStars: Received BGRA color image, converted to grayscale.",terminal=False)
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGRA2GRAY)
            else: # We have a BGR image, convert it to grayscale.
                self.Log("ImageTracker.CountStars: Received BGR color image, converted to grayscale.",terminal=False)
                cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2GRAY)
        # Threshold the image to make it more crisp.
        temp, threshed = cv2.threshold(cvimagebuffer, 100, 255, cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
        # findcontours to identify 'dots' (contours) in the image. This will recognise STARS and also some patterns made by stars. So it needs filtering.
        dots = cv2.findContours(threshed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[-2]
        # filter the 'dots' by their area. Small ones are stars, large ones are some other artifact.
        starcount = 0
        starlist = []
        for dot in dots: # Check each dot in turn.
            if minval < cv2.contourArea(dot) < maxval: # We only want small dots to count as stars.
                starcount += 1 # Increment count.
                dot_x, dot_y, dot_w, dot_h = cv2.boundingRect(dot) # Bordering rectangle of dot.
                dot_radius = int((dot_w + dot_h) / 4) # Half average of width and height.
                ctr_x = int(dot_x + dot_w / 2) # Centre of dot.
                ctr_y = int(dot_y + dot_h / 2) # Centre of dot.
                staritem = [ctr_x, ctr_y, dot_radius]
                starlist.append(staritem) # Construct list of star locations.
        self.Log("ImageTracker.CountStars: End. Counted",starcount,terminal=False)
        return starcount, starlist

    def PrepareImage(self,cvimagebuffer,blurradius=13):
        """ Enhance and scale the image ready for astroalign to process it. """
        self.Log("ImageTracker.PrepareImage: Begin",terminal=False)
        retval, cvimagebuffer = cv2.threshold(cvimagebuffer,100,255,cv2.THRESH_BINARY) # 100 should ignore clouds more easily and just recognise brighter stars.
        if blurradius % 2 == 0: blurradius += 1 # Must be odd.
        # 2nd enlarge the stars using a blur filter.
        # - This increases the radius of each star, so when we reduce the image size, the star survives the shrinking.
        cvimagebuffer = cv2.GaussianBlur(cvimagebuffer,(blurradius,blurradius),0)
        # 3rd sharpen these larger star dots back into more definite black-or-white.
        # - Use adaptive thresholding now to make the stars more crisp.
        # - Adaptive means that the threshold limit between BLACK and WHITE is chosen by the function.
        retval, cvimagebuffer = cv2.threshold(cvimagebuffer,16,255,cv2.THRESH_BINARY + cv2.THRESH_OTSU) # OTSU is adaptive threshold limits.
        # 4th shrink the image to make movement comparisons faster (though less precise).
        cvimagebuffer = self.ScaleImage(cvimagebuffer)
        self.Log("ImageTracker.PrepareImage: End. Image is",cvimagebuffer.shape[0],"*",cvimagebuffer.shape[1],terminal=False)
        return cvimagebuffer
        

    def StandardiseImage(self,refimage,starlist):
        """ Given an existing image buffer and a list of stars, create a clean version of the image.
            Inherit the dimensions from the source image, and place the stars according to the starlist. 
            This returns a GRAYSCALE image with all stars depicted at the same size.
            The size is the same for LATEST and TARGET images (Parameters.TrackingStarRadius), so that the 
            FindTransform() method has consistent images to compare. """
        self.Log("ImageTracker.StandardiseImage: Begin",terminal=False)
        GrayscaleWhite = (255)
        newimage = np.zeros((refimage.shape[0], refimage.shape[1]), np.uint8) # GRAYSCALE image. HEIGHT, WIDTH inherited from reference image.
        for star_x, star_y, star_r in starlist:
            newimage = cv2.circle(newimage,(star_x,star_y),Parameters.TrackingStarRadius,GrayscaleWhite,thickness=-1) # White. All stars converted to standard 7 pixel radius.
        return newimage

    def SetTargetImage(self,cvimagebuffer,starcount=None,starlist=None,timestamp=None,MinMagnitude=None):
        """ This registers a new target reference image. """
        self.Log("ImageTracker.SetTargetImage: Begin",terminal=False)
        self.Log("ImageTracker.SetTargetImage: Received image buffer type", str(type(cvimagebuffer)),terminal=False)
        if isinstance(cvimagebuffer,type(None)):
            self.Log("ImageTracker.SetTargetImage: Received None type image buffer. Nothing set.",terminal=False)
            return
        if timestamp == None: # If we don't know the timestamp of the image, use the current clock.
            timestamp = NowUTC() # Assume current clock time.
        self.TargetTimeStamp = timestamp
        if len(cvimagebuffer.shape) > 2: # We have a COLOR image, convert it to grayscale.
            self.Log("ImageTracker.SetTargetImage: Received color image, converted to grayscale.",terminal=False)
            cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2GRAY)
        else:
            self.Log("ImageTracker.SetTargetImage: Received grayscale image.",terminal=False)
        # Target image is drawn in the 'prepared' state already. So no need to reprocess it.
        self.TargetImage = cvimagebuffer
        self.Log("ImageTracker.SetTargetImage: Prepared image: type", str(type(self.TargetImage)), "shape", self.TargetImage.shape[0], "x", self.TargetImage.shape[1], "depth", len(self.TargetImage.shape),terminal=False)
        self.dx = None
        self.dy = None
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None
        self.TargetStarMatchList = []
        if MinMagnitude != None: 
            self.Log("ImageTracker.SetTargetImage: Setting MinMagnitude to", MinMagnitude,terminal=False)
            self.TargetMinMagnitude = MinMagnitude # The actual minimum star magnitude finally selected for the target image.
        self.Log("ImageTracker.SetTargetImage: registered new target image",terminal=False)
        if starcount == None or starlist == None: # StarCount or StarList not provided, calculate one from the image instead. 
            self.Log("ImageTracker.SetTargetImage: Did not receive StarCount or StarList. Calculating them from image.",terminal=False)
            self.TargetStarCount, self.TargetStarList = self.CountStars(self.TargetImage)
        else: # StarCount and StarList already available, just use those.
            self.Log("ImageTracker.SetTargetImage: Received StarCount and StarList. Not recalculating them.",terminal=False)
            self.TargetStarCount = starcount
            self.TargetStarList = starlist
        self.Log("ImageTracker.SetTargetImage: Counted", self.TargetStarCount, "stars.",terminal=False)
        # No need to clean up the image. It was generated to match the standardised image already.
        # Save target image for reference.
        folder = FolderList.get('tracking')
        filename = folder + 'TargetTrackingImage_' + UtcTimeStamp() + '.jpg'
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        cv2.imwrite(filename, self.TargetImage)
        # Calculate the transformation between TARGET and LATEST images.
        self.Log("ImageTracker.SetTargetImage: Calling FindTransform...",terminal=False)
        result = self.FindTransform() # Try to calculate transform between TARGET and LATEST images.
        self.Log("ImageTracker.SetTargetImage: FindTransform returned " + str(result),terminal=False)

    def LoadTargetImageFromDisc(self,filename):
        """ For development and reprocessing earlier tracking events. 
            This allows you to reload the latest target image from disc. """
        self.TargetImage = cv2.imread(filename)
        self.TargetTimeStamp = NowUTC() # Assume current clock time.

    def AstroalignStarList(self,rawlist,xoffset=[0],yoffset=[0]):
        """ Convert a raw list of points into astroalign formatted list. 
            [(x,y),(x,y),(x,y),....]
            find_transform should accept any iterable list of (x,y) pairs.
            offset values can add a constant offset to every point.
            if offset is an array, each element of the array is used to create a new offset star in the output array. """
        newlist = []
        offsets = []
        for i in range(len(xoffset)):
            offsets.append([xoffset[i],yoffset[i]])
        self.Log("AstroalignStarList: offsets",xoffset,yoffset,offsets,terminal=False)
        for entry in rawlist:
            for i in offsets:
                newentry = (float(entry[0] + i[0]),float(entry[1] + i[1]))
                newlist.append(newentry)
        # newlist = np.array(newlist)
        self.Log("ImageTracker.AstroalignStarlist:",str(newlist),terminal=True)
        return newlist

    def FindTransformOld(self):
        """ Use astroalign.find_transform to calculate transform between TARGET and LATEST images.
            The target image is generated by the program and represents the star layout we expect to photograph.
            The latest image is the one captured by the camera.
            Find Transform compares the two images and decides if they match.
            It measures any shift between the two images, this can be used to correct for drift in the telescope motion. """
        # ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all() 
        self.Log("ImageTracker.FindTransformOld: Begin",terminal=False)
        result = False
        self.dx = None
        self.dy = None
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None
        #self.Log("ImageTracker.FindTransform: Target is", str(type(self.TargetImage)), ", Latest is", str(type(self.LatestImage)),terminal=False)
        if isinstance(self.TargetImage,type(None)) or isinstance(self.LatestImage,type(None)):
            pass # No images to compare. Skip this.
        else: # Two images available to compare.
            try: # The transform object is a numpy structure, if the transform calculation fails you can get weird problems that I couldn't always detect cleanly.
                 # So for now ignore any errors at this stage, and assume that no transform could be calculated.
                 # Sometimes it returned a NoneType that I couldn't test for (numpy array peculiarity), and sometimes it returned an empty array.
                self.Log("ImageTracker.FindTransform: TargetImage: type", str(type(self.TargetImage)), "shape", self.TargetImage.shape[0], "x", self.TargetImage.shape[1], "depth", len(self.TargetImage.shape), "len[0]", len(self.TargetImage[0]), '(2 = (x,y), else image)', "datatype", str(self.TargetImage.dtype),terminal=False)
                self.Log("ImageTracker.FindTransform: LatestImage: type", str(type(self.LatestImage)), "shape", self.LatestImage.shape[0], "x", self.LatestImage.shape[1], "depth", len(self.LatestImage.shape), "len[0]", len(self.LatestImage[0]), '(2 = (x,y), else image)', "datatype", str(self.LatestImage.dtype),terminal=False)
                self.Log("ImageTracker.FindTransform: Calling astroalign.find_transform()...",terminal=False)
                # If find_transform fails, it reports that the input images are not supported, but this is a generic error for ANY failure at all.
                # Check the astroalign source code online and dig deeper... I've seen where _find_sources() fails due to 'sep' package versioning problems.
                transform, (LSL, TSL) = astroalign.find_transform(source=self.LatestImage,target=self.TargetImage) # In Astroalign terms, this is source=LatestImage, target=TargetImage...
                self.TargetStarMatchList = TSL
                self.LatestStarMatchList = LSL
                self.Log("ImageTracker.FindTransform: Received " + str(type(transform)) + " type in return.",terminal=False)
                self.Log("ImageTracker.FindTransform: Identified " + str(len(TSL)) + " suitable stars in target image.",terminal=False)
                self.Log("ImageTracker.FindTransform: TargetStarMatchList " + str(TSL) + ".",terminal=False)
                if len(TSL) > 0 and len(LSL) > 0: # During development, look at the datatype.
                    self.Log("ImageTracker.FindTransform: Example TSL 1st entry is:", str(TSL[0]),terminal=False)
                    self.Log("ImageTracker.FindTransform: Example LSL 1st entry is:", str(LSL[0]),terminal=False)
                self.Log("ImageTracker.FindTransform: Identified " + str(len(LSL)) + " suitable stars in latest image.",terminal=False)
                self.Log("ImageTracker.FindTransform: LatestStarMatchList " + str(LSL) + ".",terminal=False)
                self.dx = int(-1 * (100 / self.imagepc) * transform.translation[0]) # X-Difference scaled back up to compensate for any image scaling.
                self.dy = int(-1 * (100 / self.imagepc) * transform.translation[1]) # Y-Difference scaled back up to compensate for any image scaling.
                self.rotation = round(math.degrees(transform.rotation),3) # How does the image need to be rotated? Convert radians into degrees.
                self.Log("ImageTracker.FindTransform: Calculated transform: dx=" + str(self.dx),"dy=" + str(self.dy),terminal=False)
                self.Log("ImageTracker.FindTransform: Calculated rotation:",self.rotation,"degrees",terminal=False) # How does the image need rotating?
                self.measureddelta = (self.LatestTimeStamp - self.TargetTimeStamp).total_seconds()
                result = True
            except Exception as e:
                # The most likely explanation is that the lens cap is ON, or there are not enough stars visible in the observation.
                self.Log("ImageTracker.FindTransform: Ignored error: " + str(e),terminal=False) # Enable this line if you want to see what error is being ignored!
                self.Log("ImageTracker.FindTransform: No transform matrix created. Too few stars, lens cap on, no transformation identified or fault in astroalign and dependencies?",terminal=False)
                DriftWindow.Print(NowHMS() + " FindTransform unsuccessful.")
        try:
            self.SaveTrackingAnalysis() # Create an image showing the drift analysis in terms of the actual stars.
        except Exception as e:
            print(e) # Trap all the exception information in the main log file.
            CamLog.ReportException(e,level='error',comment='SaveTrackingAnalysis call failed in FindTransform.')
            
        return result # True if successful, False if failed.

    def ScaleStarList(self,inputlist,scalefactor):
        """ Take a list of star locations and scale the first two terms.
            Any additional terms are left unmodified. 
            Each star in the list can consist of up to 4 terms.
                [xpos,ypos,radius,magnitude] 
            Only the xpos and ypos entries are scaled, all other terms remain unchanged. """
        self.Log("ImageTracker.ScaleStarList: Scale:",scalefactor,"List:",inputlist,terminal=False)
        newlist = [] # The resulting list.
        for star in inputlist: # Go through each star in turn.
            newstar = []
            for i,term in enumerate(star):
                if i < 2: newterm = term * scalefactor
                else: newterm = term
                newstar.append(int(newterm))
            newlist.append(newstar)
        self.Log("ImageTracker.ScaleStarList: Result:",newlist,terminal=False)
        return newlist
        
    def FindTransform(self):
        """ Use astroalign.find_transform to calculate transform between TARGET and LATEST images.
            The target image is generated by the program and represents the star layout we expect to photograph.
            The latest image is the one captured by the camera.
            Find Transform compares the two images and decides if they match.
            It measures any shift between the two images, this can be used to correct for drift in the telescope motion. """
        # ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all() 
        self.Log("ImageTracker.FindTransform: Begin",terminal=False)
        self.Log("ImageTracker.FindTransform: LatestStarList",len(self.LatestStarList),", TargetStarList",len(self.TargetStarList),terminal=False)
        result = False
        self.dx = None
        self.dy = None
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None
        scalefactor = Parameters.FindTransformScale # If we scale down for Astroalign, this is the factor we scale by.
        recoveryfactor = 1 / scalefactor # And this is how we scale back up for the result.
        #self.Log("ImageTracker.FindTransform: Target is", str(type(self.TargetImage)), ", Latest is", str(type(self.LatestImage)),terminal=False)
        # *Q* If this version is OK, references to TargetImage and LatestImage are not needed. It's all done via the starlists now.
        if isinstance(self.TargetImage,type(None)) or isinstance(self.LatestImage,type(None)) or len(self.LatestStarList) < 3 or len(self.TargetStarList) < 3:
            self.Log("ImageTracker.FindTransform: Target or Latest images are unacceptable:",terminal=False)
            self.Log("ImageTracker.FindTransform: - LatestStarList",len(self.LatestStarList),", TargetStarList",len(self.TargetStarList),terminal=False)
            self.Log("ImageTracker.FindTransform: - LatestImage",str(type(self.LatestImage)),", TargetImage",str(type(self.TargetImage)),terminal=False)
        else: # Two images available to compare.
            self.Log("ImageTracker.FindTransform: Scaling star lists...",terminal=False)
            lateststarlist = self.ScaleStarList(self.LatestStarList,scalefactor)
            targetstarlist = self.ScaleStarList(self.TargetStarList,scalefactor)
            try: # find_transform can fail for various reasons, some trivial, some are an indication of problems.
                 # Capture any errors to the log file, but continue with the operation because the failure may be acceptable.
                self.Log("ImageTracker.FindTransform: Calling astroalign.find_transform()...",terminal=False)
                # If find_transform fails, it reports that the input images are not supported, but this may be a generic error for ANY failure at all.
                # Check the astroalign source code online and dig deeper... I've seen where _find_sources() fails due to 'sep' package versioning problems.
                # The reported error message and stack trace is recorded in the log file if you need to dig deeper. But not displayed to the terminal.
                transform, (LSL, TSL) = astroalign.find_transform(source=lateststarlist,target=targetstarlist) # In Astroalign terms, this is source=LatestImage, target=TargetImage...
                self.TargetStarMatchList = TSL
                self.LatestStarMatchList = LSL
                self.Log("ImageTracker.FindTransform: Received " + str(type(transform)) + " type in return.",terminal=False)
                self.Log("ImageTracker.FindTransform: Identified " + str(len(TSL)) + " suitable stars in target image.",terminal=False)
                self.Log("ImageTracker.FindTransform: TargetStarMatchList " + str(TSL) + ".",terminal=False)
                if len(TSL) > 0 and len(LSL) > 0: # During development, look at the datatype.
                    self.Log("ImageTracker.FindTransform: Example TSL 1st entry is:", str(TSL[0]),terminal=False)
                    self.Log("ImageTracker.FindTransform: Example LSL 1st entry is:", str(LSL[0]),terminal=False)
                self.Log("ImageTracker.FindTransform: Identified " + str(len(LSL)) + " suitable stars in latest image.",terminal=False)
                self.Log("ImageTracker.FindTransform: LatestStarMatchList " + str(LSL) + ".",terminal=False)
                self.dx = int(recoveryfactor * -1 * (100 / self.imagepc) * transform.translation[0]) # X-Difference scaled back up to compensate for any image scaling.
                self.dy = int(recoveryfactor * -1 * (100 / self.imagepc) * transform.translation[1]) # Y-Difference scaled back up to compensate for any image scaling.
                self.rotation = round(math.degrees(transform.rotation),3) # How does the image need to be rotated? Convert radians into degrees.
                self.Log("ImageTracker.FindTransform: Calculated transform: dx=" + str(self.dx),"dy=" + str(self.dy),terminal=False)
                self.Log("ImageTracker.FindTransform: Calculated rotation:",self.rotation,"degrees",terminal=False) # How does the image need rotating?
                self.measureddelta = (self.LatestTimeStamp - self.TargetTimeStamp).total_seconds()
                result = True
            except Exception as e:
                # The most likely explanation is that the lens cap is ON, or there are not enough stars visible in the observation.
                self.Log("ImageTracker.FindTransform: Ignored error: " + str(e),terminal=False) # Enable this line if you want to see what error is being ignored!
                self.Log("ImageTracker.FindTransform: No transform matrix created. Too few stars, lens cap on, no transformation identified or fault in astroalign and dependencies?",terminal=False)
                DriftWindow.Print(NowHMS() + " FindTransform unsuccessful.")
                CamLog.RecordTraceback(e,terminal=False) # Trap all the exception information in the camera log file. Don't report to the terminal.
        try:
            self.SaveTrackingAnalysis() # Create an image showing the drift analysis in terms of the actual stars.
        except Exception as e:
            print(e) # Trap all the exception information in the main log file.
            CamLog.ReportException(e,level='error',comment='SaveTrackingAnalysis call failed in FindTransform.')
            
        return result # True if successful, False if failed.
        
    def ValidStarValues(self,entry):
        """ Return if 'star' value is valid. Star is an entry from a StarMatchList.
            Used by SaveTrackingAnalysis() method. """
        result = False
        if len(entry) > 1:
            if isinstance(entry[0],float) and isinstance(entry[1],float):
                result = True
            if isinstance(entry[0],int) and isinstance(entry[1],int):
                result = True
        if not result:
            self.Log("imagetracker.ValidStarValues(",entry,") type",type(entry),"was unacceptable.",terminal=True)
        return result

    def MarkLocation(self,image,starx,stary,color,font):
        """ Write the location text next to the star.
            Places the text left/right/above/below depending upon it's location in the image. """
        starx = int(starx)
        stary = int(stary)
        if starx < (image.shape[1] / 2): xloc = starx + 10
        else: xloc = starx - 120
        if stary < (image.shape[0] / 2): yloc = stary + 10
        else: yloc = stary - 20
        text = "(" + str(starx) + "," + str(stary) + ")"
        image = cv2.putText(image,text,(xloc,yloc),font,0.5,color)
        return image
        
    def SaveTrackingAnalysis(self,latestlist=None,targetlist=None):
        """ Combine LATEST, TARGET star lists and show which stars were matched up in FindTransform.
            This is a debug/development feature, but shows how the drift tracking is actually interpreting the images. """
        self.Log("SaveTrackingAnalysis: Begin",terminal=False)
        if type(latestlist) == type(None): latestlist = self.LatestStarList
        if type(targetlist) == type(None): targetlist = self.TargetStarList
        image = NewBlankImage() # Color full frame blank image.
        font = cv2.FONT_HERSHEY_SIMPLEX
        self.Log("SaveTrackingAnalysis: latest match list:",self.LatestStarMatchList,terminal=False)
        self.Log("SaveTrackingAnalysis: target match list:",self.TargetStarMatchList,terminal=False)
        # Match lists must be the same length.
        if len(self.LatestStarMatchList) == len(self.TargetStarMatchList):
            # Mark the matched stars first, and an arrow linking the TARGET and LATEST locations.
            for i, lstar in enumerate(self.LatestStarMatchList): 
                tstar = self.TargetStarMatchList[i]
                self.Log("SaveTrackingAnalysis: matching lstar",i,"=",lstar,terminal=False)
                lx = int(lstar[0])
                ly = int(lstar[1])
                self.Log("SaveTrackingAnalysis: matching tstar",i,"=",tstar,terminal=False)
                tx = int(tstar[0])
                ty = int(tstar[1])
                if self.ValidStarValues(tstar): image = cv2.circle(image,(tx,ty),15,BGRGreen,thickness=2,lineType=cv2.LINE_AA) # Green circle around matched Target stars.
                else: self.Log("imagetracker.SaveTrackingAnalysis: TargetStarMatchList. tstar",tstar,"bad values.",terminal=True)
                if self.ValidStarValues(lstar): image = cv2.circle(image,(lx,ly),15,BGRRed,thickness=2,lineType=cv2.LINE_AA) # Red circle around matched Latest stars.
                else: self.Log("imagetracker.SaveTrackingAnalysis: LatestStarMatchList. lstar",lstar,"bad values.",terminal=True)
                if self.ValidStarValues(tstar) and self.ValidStarValues(lstar): image = cv2.arrowedLine(image,(lx,ly),(tx,ty),BGRWhite,thickness=1,line_type=cv2.LINE_AA,tipLength=0.1) # Green circle around matched Target stars.
                # New solution to above code... remove above if this works.
                image = DrawDumbbell(image,(lx,ly),(tx,ty),20,BGRRed,BGRGreen,BGRYellow,arrow=True)
        else: # Lists don't agree, so don't try to map them.
            self.Log("imagetracker.SaveTrackingAnalysis: Conflicting length of star lists: Target", len(self.TargetStarMatchList), "vs Latest", len(self.LatestStarMatchList),terminal=False)
            DriftWindow.Print(NowHMS() + " drift analysis image not done.") # Note analysis not done.
        # Superimpose all the TARGET stars. (Stars we expect to see)
        for star in self.TargetStarList: 
            self.Log("SaveTrackingAnalysis: target star",star,terminal=False)
            if self.ValidStarValues(star): 
                starx = int(star[0])
                stary = int(star[1])
                image = cv2.circle(image,(starx,stary),5,BGRGreen,thickness=-1,lineType=cv2.LINE_AA) # Green dot for Target stars.
                image = self.MarkLocation(image,starx,stary,BGRGreen,font)
            else: self.Log("imagetracker.SaveTrackingAnalysis: TargetStarList. star",star,"bad values.",terminal=True)
        # Superimpose all the LATEST stars. (Stars we actually see)
        for star in self.LatestStarList: 
            self.Log("SaveTrackingAnalysis: latest star",star,terminal=False)
            if self.ValidStarValues(star): 
                starx = int(star[0])
                stary = int(star[1])
                image = cv2.circle(image,(starx,stary),5,BGRRed,thickness=-1,lineType=cv2.LINE_AA) # Red dot for Latest stars.
                image = self.MarkLocation(image,starx,stary,BGRRed,font)
            else: self.Log("imagetracker.SaveTrackingAnalysis: LatestStarList. star",star,"bad values.",terminal=True)
        timestamp = str(NowUTC()).split('.')[0] + " UTC"
        image = cv2.putText(image,"Tracking Analysis " + timestamp,(1300,100),font,2,BGRWhite,thickness=2,lineType=cv2.LINE_AA)
        image = cv2.putText(image,str(self.TargetStarCount) + " Target stars",(100,100),font,1,BGRGreen,thickness=1,lineType=cv2.LINE_AA)
        image = cv2.putText(image,str(self.LatestStarCount) + " Latest stars",(100,140),font,1,BGRRed,thickness=1,lineType=cv2.LINE_AA)
        image = cv2.putText(image,str(len(self.LatestStarMatchList)) + " Matches",(100,180),font,1,BGRYellow,thickness=1,lineType=cv2.LINE_AA)
        filename = FolderList['tracking'] + "TrackingAnalysis_" + UtcTimeStamp() + ".jpg"
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        DriftWindow.Print(NowHMS() + " Drift analysis image done.") # Note analysis done.
        cv2.imwrite(filename,image)
        self.Log("SaveTrackingAnalysis: End",terminal=False)

    def LatestImageMagnitudes(self,imagebuffer):
        """ When LatestStarList is set and cvimage still contains the latest image
            this routine calculates a relative brightness for each star.
            It returns a new list with the relative brightness measure appended to each element.
            Each element consists of [x,y,radius,brightness]
            if radius is not available in LatestStarList a default of 4 is used. """
        # Maximum dimensions of the image.
        if type(imagebuffer) == type(None):
            self.Log("ImageTracker.LatestImageMagnitudes: imagebuffer is None.",level='error',terminal=True)
            return
        if not isinstance(self.LatestStarList, list):
            self.Log("ImageTracker.LatestImageMagnitudes: LatestStarList (type ",type(self.LatestStarList), ") is not a list.",level='error',terminal=True)
            self.Log("ImageTracker.LatestImageMagnitudes: LatestStarList:", str(self.LatestStarList),terminal=True)
            return
        if len(self.LatestStarList) < 1:
            self.Log("ImageTracker.LatestImageMagnitudes: LatestStarList is empty. Cannot calculate stellar brightnesses.",terminal=False)
            return
        maxx = imagebuffer.shape[1]
        maxy = imagebuffer.shape[0]
        span = 9 # How wide is the area that we sum up for an individual star?
        resultlist = []
        for i,star in enumerate(self.LatestStarList): # Process each star in turn.
            starx = star[0] # x location
            stary = star[1] # y location
            # star[2] = radius
            # star[3] = brightness (bright=Low, dim=High)
            if len(star) > 2: starradius = star[2] # Extract radius if available from the list.
            else: starradius = 4
            # Define subset of image buffer pixels to accumulate for the brightness measure.
            startx = max(0,starx - span) 
            endx = min(maxx,starx + span)
            starty = max(0,stary - span)
            endy = min(maxy,stary + span)
            # To be fair to stars on the edge of the image, brightness is moderated by the pixel area visible.
            area = (endx - startx) * (endy - starty)
            # Sum the pixel values in the region of the star.
            if imagebuffer.shape[2] > 1:
                brightness = np.sum(imagebuffer[startx:endx,starty:endy,:])
            else:   
                brightness = np.sum(imagebuffer[startx:endx,starty:endy])
            brightness = brightness / area # Moderate the total pixel value by the area visible.
            brightness = 1000 - brightness # Brightness needs to be recorded as low=bright, high=dim like the magnitude scale.
            self.Log("ImageTracker.LatestImageMagnitudes:",i,str(star),"brightness",brightness,terminal=False)
            resultlist.append([starx,stary,starradius,brightness])
        # Now sort the list so that the stars are arranged brightest first....
        if len(resultlist) > 0 and len(resultlist[0]) > 3:
            resultlist.sort(key = lambda x: x[3]) # 4th element in the list is the magnitude.
            self.Log("ImageTracker.LatestImageMagnitudes: Sorted resultlist:",resultlist,terminal=False)
        else:
            self.Log("ImageTracker.LatestImageMagnitudes: Could not sort list by magnitude. (Empty or incomplete)",terminal=False)
        return resultlist

    def SetLatestImage(self,cvimagebuffer,timestamp=None):
        """ This registers the latest image from the camera and performs the translation calculation.
            The imagetracker stores images in grayscale because we do some thresholding to enhance them.
            It does not return any measurements, but stores them in various attributes. """
        self.Log("ImageTracker.SetLatestImage: Begin",terminal=False)
        self.Log("ImageTracker.SetLatestImage: Received image buffer type", str(type(cvimagebuffer)),terminal=False)
        if isinstance(cvimagebuffer,type(None)):
            self.Log("ImageTracker.SetLatestImage: Received None type image buffer. Nothing set.",terminal=False)
            return
        if timestamp == None: timestamp = NowUTC() # Assume current clock time.
        self.LatestTimeStamp = None # Clear the timestamp until we've completed preparing the image. This is accessed concurrently by the CameraHandler.
        self.LatestImage = cvimagebuffer.copy() # Make sure you don't just copy a pointer to the same buffer, you'll overwrite other activities if you do!
        if len(self.LatestImage.shape) > 2: # We have a COLOR image, convert it to grayscale.
            self.Log("ImageTracker.SetLatestImage: Received color image, converted to grayscale.",terminal=False)
            self.LatestImage = cv2.cvtColor(self.LatestImage, cv2.COLOR_BGR2GRAY)
        else:
            self.Log("ImageTracker.SetLatestImage: Received grayscale image.",terminal=False)
        self.Log("ImageTracker.SetLatestImage: Preparing image",terminal=False)
        self.LatestImage = self.PrepareImage(self.LatestImage)
        self.LatestTimeStamp = timestamp # The image is now prepared, update the timestamp.
        self.Log("ImageTracker.SetLatestImage: Prepared image:","type", str(type(self.LatestImage)),"shape", self.LatestImage.shape[0], "x", self.LatestImage.shape[1],"depth", len(self.LatestImage.shape),terminal=False)
        self.LatestStarMatchList = []
        self.Log("ImageTracker.SetLatestImage: registered latest image",terminal=False)
        self.LatestStarCount, self.LatestStarList = self.CountStars(self.LatestImage)
        self.Log("ImageTracker.SetLatestImage: Counted " + str(self.LatestStarCount) + " stars.",terminal=False)
        brightnesslist = self.LatestImageMagnitudes(imagebuffer=CameraInUse.CvImage) # Estimate brightness of each identified star by checking the original image buffer.
        self.Log("ImageTracker.SetLatestImage: Ranked LatestStarList would be:",brightnesslist,terminal=False)
        # Clean up the image.
        self.LatestImage = self.StandardiseImage(self.LatestImage,self.LatestStarList) # Create clean version of the image file.
        # Save target image for reference.
        folder = FolderList.get('tracking')
        filename = folder + 'LatestTrackingImage_' + UtcTimeStamp() + '.jpg'
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the file that's being created.
        cv2.imwrite(filename, self.LatestImage)

    def PredictedTransform(self,timestamp=None):
        """ Estimate the image shift based upon the input images, projected forward in time. 
            prediction is based upon timestamp received. If None, then prediction is based upon current timestamp. """
        if timestamp == None: timestamp = NowUTC() # Assume current clock.
        self.Log("ImageTracker.PredictedTransform(): dx", str(self.dx), "dy", str(self.dy), "measureddelta", str(self.measureddelta),terminal=False)
        dx = None
        dy = None
        nowdelta = None
        if self.dx != None and self.dy != None and self.measureddelta != None:
            if self.measureddelta > 0:
                nowdelta = (timestamp - self.TargetTimeStamp).total_seconds()
                dx = self.dx * nowdelta / self.measureddelta
                dy = self.dy * nowdelta / self.measureddelta
            else:
                dx = self.dx
                dy = self.dy
        return dx, dy, nowdelta

# ------------------------------------------------------------------------------------------------------

DriftTracker = imagetracker() # Create an instance of the image tracker to measure drift between subsequent images. 

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Initialize Skyfield 
# ///////////////////////////////////////////////////////////////////////////////////

# Set up observer location.
#PoleLat = '90.0 N'
#PoleLatVal = float(PoleLat.split(" ")[0])
#PoleLon = Parameters.HomeLon
#PolarTilt = (90.0 - Parameters.HomeLatVal) 
MainLog.Log("Home location Lat:" + Parameters.HomeLat + " Lon:" + Parameters.HomeLon)
HomeSiteTopos = Topos(Parameters.HomeLat,Parameters.HomeLon)
#PoleTopos = Topos(PoleLat,PoleLon)

# Load dictionary listing star NAMES, CONSTELLATION and Hipparcos catalog number. 
load = Loader('/home/pi/pilomar/data') # Create own version of Skyfield 'load' object. This version saves cache files in the data directory.
StarNameUrl = ProjectRoot + '/data/starnames.json'
MessierDictUrl = ProjectRoot + '/data/messierobjects.json'
MeteorDictUrl = ProjectRoot + '/data/meteors.json'
NGCUrl = ProjectRoot + '/data/ngc.json'

def DictionaryLoader(filename): # 4 references.
    """ Given a json filename on disc, load it as a Python dictionary. 
        Return empty dictionary if file does not exist. """
    if os.path.exists(filename):
        with open(filename,'r') as f:
            dictionary = json.load(f)
    else:
        MainLog.Log('DictionaryLoader(',filename,') does not exist. Empty dictionary returned.')
        dictionary = {}
    return dictionary

# Load starname dictionary.
MainLog.Log("Loading StarName dictionary from " + StarNameUrl + "...")
StarName_dictionary = DictionaryLoader(StarNameUrl)

# Load Hipparcos catalog using Skyfield libraries.
# *Q* This could be smarter, go to web if local copy is missing.
HipparcosUrl = ProjectRoot + '/data/hip_main.dat.gz' # The skyfield example tries to pull this from the internet, 
# but the .gz. file doesn't always exist in the format expected so it is stored locally for now. 
# http://cdsarc.u-strasbg.fr/ftp/cats/aliases/H/Hipparcos/hip_main.dat
# This was fixed by skyfield 1.31, it may break again if someone in u-strasbg re-zips the file.
# hipparcos.URL contains the remote server copy of the file.
if not os.path.exists(HipparcosUrl):
    MainLog.Log('Hipparcos compressed catalog was not found locally (',HipparcosUrl,'), will use Skyfield sources.')
    # HipparcosUrl = 'https://cdsarc.u-strasbg.fr/ftp/cats/I/239/hip_main.dat'
    HipparcosUrl = hipparcos.URL # The official source of the data file as provided by skyfield itself.
MainLog.Log("Loading Hipparcos catalog dataframe from " + HipparcosUrl + " (or local cache)...")
MainLog.Log("- Primary Hipparcos dataframe...",terminal=True)
with load.open(HipparcosUrl,reload=ReloadData) as f: # Don't keep reloading it if it is already on disc.
    HipparcosDf = hipparcos.load_dataframe(f) # Hipparcos data as a Pandas dataframe.
    MainLog.Log('Hipparcos data:',list(HipparcosDf.columns),terminal=False)
# MainLog.Log('HipparcosDf:\n',str(HipparcosDf.describe()),terminal=False) # Describe the pandas dataframe.

def hipex_load_dataframe(fobj): # 1 references.
    """ Skyfield has a built in method to extract Hipparcos data and convert it into a Pandas dataframe.
        However it lacks some data fields that Pilomar uses.
        This is a replica of the Skyfield method, but it extracts the additional datafields that Pilomar uses. 
        If the original Skyfield method ever changes, this version should also be reviewed. """
    # This extracts extra data columns from the hipparcos file.
    _COLUMN_NAMES = (
        'Catalog', 'HIP', 'Proxy', 'RAhms', 'DEdms', 'Vmag',
        'VarFlag', 'r_Vmag', 'RAdeg', 'DEdeg', 'AstroRef', 'Plx', 'pmRA',
        'pmDE', 'e_RAdeg', 'e_DEdeg', 'e_Plx', 'e_pmRA', 'e_pmDE', 'DE:RA',
        'Plx:RA', 'Plx:DE', 'pmRA:RA', 'pmRA:DE', 'pmRA:Plx', 'pmDE:RA',
        'pmDE:DE', 'pmDE:Plx', 'pmDE:pmRA', 'F1', 'F2', '---', 'BTmag',
        'e_BTmag', 'VTmag', 'e_VTmag', 'm_BTmag', 'B-V', 'e_B-V', 'r_B-V',
        'V-I', 'e_V-I', 'r_V-I', 'CombMag', 'Hpmag', 'e_Hpmag', 'Hpscat',
        'o_Hpmag', 'm_Hpmag', 'Hpmax', 'HPmin', 'Period', 'HvarType',
        'moreVar', 'morePhoto', 'CCDM', 'n_CCDM', 'Nsys', 'Ncomp',
        'MultFlag', 'Source', 'Qual', 'm_HIP', 'theta', 'rho', 'e_rho',
        'dHp', 'e_dHp', 'Survey', 'Chart', 'Notes', 'HD', 'BD', 'CoD',
        'CPD', '(V-I)red', 'SpType', 'r_SpType',
    )
    
    # Check the first 2 'magic' bytes at the start of the file, these will tell if the file is a gzip archive.
    # The pandas.read_csv method needs to know if it's compressed or not.
    fobj.seek(0)
    magic = fobj.read(2)
    compression = 'gzip' if (magic == b'\x1f\x8b') else None
    fobj.seek(0)

    df = pandas.read_csv(
        fobj, sep='|', names=_COLUMN_NAMES, compression=compression,
        usecols=['HIP', 'B-V']
    )
    df.columns = ('hip', 'B-V') # Give names to each column in the dataframe.
    return df.set_index('hip') # set_index to the 'hip' field. So myrec = df.loc[23423] will retrieve HIP_23423

MainLog.Log("- Additional Hipparcos dataframe...",terminal=True)
try:
    with load.open(HipparcosUrl,reload=ReloadData) as f:
        HipExDf = hipex_load_dataframe(f)
        MainLog.Log('Hipparcos extra data:',list(HipExDf.columns),terminal=False)
except Exception as e:
    MainLog.ReportException(e,comment='Loading extra hipparcos dataframe.')
    exit() # Quit the program.
# MainLog.Log('HipExDf:\n',str(HipExDf.describe()),terminal=False) # Describe the pandas dataframe.

# These files come from JPL, they list the rules for positions of planets for hundreds of years.
MainLog.Log("Loading solar system ephemeris from JPL...")
# This requires an internet connection the first time it runs, after that it uses cached data.
# *Q* Oct.2020 - skyfield log suggests this may nolonger automatically update, may need manual flush and reload every few months.
planets = load('de421.bsp') # Compact list of inner planets. *Q* Does this have a 'reload' option like load.open does?

# Load Messier object list.
MainLog.Log('Loading Messier catalog from', MessierDictUrl, '...')
Messier_dictionary = DictionaryLoader(MessierDictUrl)

StellariumUrl = ('https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/constellationship.fab')
MainLog.Log('Loading Stellarium constellation patterns from',StellariumUrl)
with load.open(StellariumUrl) as f:
    StellariumConstellations = stellarium.parse_constellations(f)

# Create internal list of the stars in each constellation. This indicates which stars to 'join up' in order to draw a constellation pattern.
ConstellationLinks = [] # Start new empty list of constellation patterns.
ConstellationCodes = dict(load_constellation_names())
for cons in StellariumConstellations: # Process each constellation in turn.
    # cons contains something like 'And',[(star1, star2), (star3, star4),...]
    c_name = cons[0] # Constellation name ('And')
    # Expand constellation code into a name if possible.
    if c_name in ConstellationCodes: # A translation exists.
        c_name = ConstellationCodes[c_name] # Use the translation instead.
    c_edge = cons[1] # Constellation pattern edges as a list [(star1, star2),(star3, star4),...]
    for c_pair in c_edge: # Process each star pair in turn.
        entry = [str(c_pair[0]),str(c_pair[1]),c_name] # New entry for internal format list.
        ConstellationLinks.append(entry)

# Load NGC list.
MainLog.Log('Loading New General Catalog (NGC) entries from', NGCUrl, '...')
NGCDict = DictionaryLoader(NGCUrl)
NGC_Namelist = [] # List of names.
for key, value in NGCDict.items():
    NGC_Namelist.append(key)

# Load Meteor shower list.
MainLog.Log('Loading meteor shower list from', MeteorDictUrl, '...')
Meteor_dictionary = DictionaryLoader(MeteorDictUrl)

# Load comet data.
MainLog.Log('Loading comet list from',mpc.COMET_URL,'...')
with load.open(mpc.COMET_URL,reload=ReloadData) as f: # Don't keep reloading it if it is already on disc.
    comets = mpc.load_comets_dataframe(f) # Comet data loaded as a Pandas dataframe.
MainLog.Log(len(comets), 'comets loaded.',terminal=False)
# Keep only the most recent comet trajectory.
# Keep only the most recent orbit for each comet,
# and index by designation for fast lookup.
comets = (comets.sort_values('reference')
          .groupby('designation', as_index=False).last()
          .set_index('designation', drop=False))
# MainLog.Log('comets.df:\n',str(comets.describe()),terminal=False) # Describe the dataframe.

# Example lookups.
#row = comets.loc['1P/Halley']
#row = comets.loc['C/1995 O1 (Hale-Bopp)']

CometList = comets['designation'].tolist() # Convert comet designations column into a list for searching later on.

MainLog.Log("Establish observer's location...")
HomeSite = planets['earth'] + HomeSiteTopos # Define HomeSite as a point on earth. Could be from GPS too.
#Pole = planets['earth'] + PoleTopos # Define North Pole. This is used to align a polar mounted camera with a distant object. (Won't work for satellites!)
RadecBase = Star(ra_hours=(0,0,0.0), dec_degrees=(0,0,0.0)) # To calculate where Radec ZERO point is. (For Equatorial mount positioning)

# ----------------------------------------------------------------------------------------------------------

class localstars(attributemaster): # 1 references.
    """ Smart cache of neighbouring stars, to make rendering and markup of images faster.
        Creates a pandas dataframe of stars near the target. 
        The dataframe is automatically updated if the target moves significantly.
        This also standardises the selection logic so that all image generators
        will give similar results. """
    
    def __init__(self,ra,dec,radius,magnitude,maxstars=1000):
        MainLog.Log("localstars.__init__(",ra,dec,radius,magnitude,maxstars,"):",terminal=False)
        self._df = None # Pandas dataframe.
        self.MasterDf = HipparcosDf # The master dataframe that the cache is built from.
        self.updated = None # Timestamp when the cache was last updated.
        self.ra = ra # Centre RIGHT ASCENSION in degrees.
        self.dec = dec # Centre DECLINATION in degrees.
        self.radius = radius # Selection radius in degrees. 
        self._updateangle = radius / 4 # When centre has moved this far, it's time to update.
        self.magnitude = magnitude # Minimum magnitude to select. Ignore any stars dimmer than this.
        self.maxstars = maxstars # Maximum number of stars to select.
        self.Update(ra,dec) # Trigger update immediately to load the cache.
        
    def Update(self,ra,dec):
        MainLog.Log("localstars.Update(",ra,dec,"): Begin",terminal=False)
        self._df = None # Clear old cache.
        self.ra = ra # Update RIGHT ASCENSION location.
        self.dec = dec # Update DECLINATION location.
        self.MinRADeg = self.ra - self.radius
        self.MaxRADeg = self.ra + self.radius
        self.MinDecDeg = self.dec - self.radius
        self.MaxDecDeg = self.dec + self.radius
        # Select a subset of the Hipparcos catalog which is within TargetInclusionRadius of the target (=centre of image)
        self._df = self.MasterDf.loc[(self.MasterDf['ra_degrees'] >= self.MinRADeg) & (self.MasterDf['ra_degrees'] <= self.MaxRADeg) & (self.MasterDf['dec_degrees'] >= self.MinDecDeg) & (self.MasterDf['dec_degrees'] <= self.MaxDecDeg) & (self.MasterDf['magnitude'] <= self.magnitude)]
        # If MinRaDeg < 0 then add 360 and append result MinRaDeg<=x<360.
        if self.MinRADeg < 0: # -ve RA values need adjusting to 0-360 range.
            self._df1 = self.MasterDf.loc[(self.MasterDf['ra_degrees'] >= self.MinRADeg + 360) & (self.MasterDf['ra_degrees'] <= 360) & (self.MasterDf['dec_degrees'] >= self.MinDecDeg) & (self.MasterDf['dec_degrees'] <= self.MaxDecDeg) & (self.MasterDf['magnitude'] <= self.magnitude)]
            self._df = pandas.concat([self._df,self._df1]) # Add to original list.
        # If MaxRaDeg > 360 then subtract 360 and append result 0<x<=MaxRaDeg
        if self.MaxRADeg > 360: # +ve RA values over 360 need adjusting to 0-360 range.
            self._df2 = self.MasterDf.loc[(self.MasterDf['ra_degrees'] >= 0) & (self.MasterDf['ra_degrees'] <= self.MaxRADeg - 360) & (self.MasterDf['dec_degrees'] >= self.MinDecDeg) & (self.MasterDf['dec_degrees'] <= self.MaxDecDeg) & (self.MasterDf['magnitude'] <= self.magnitude)]
            self._df = pandas.concat([self._df,self._df2]) # Add to original list.
        #CamLog.Log("localstars.Update: self._df before sort:" + str(len(self._df)),terminal=False)
        self._df = self._df.sort_values(['magnitude'],ascending=[True]) # Sort the selected stars in ascending order of brightness. So we can match the brightest stars first.
        #CamLog.Log("localstars.Update: self._df after sort:" + str(len(self._df)),terminal=False)
        # Clip to maxstars.
        self._df = self._df[:self.maxstars]
        self.update = NowUTC() # Update timestamp.
        MainLog.Log("localstars.Update(): Selected",len(self._df.index),"rows.",terminal=False)
        MainLog.Log("localstars.Update(): End",terminal=False)
        return True
        
    def Get(self,ra,dec):
        MainLog.Log("localstars.Get(",ra,dec,"): Begin",terminal=False)
        if abs(self.ra - ra) > self._updateangle or abs(self.dec - dec) > self._updateangle: 
            MainLog.Log("localstars.Get(): Target location has moved enough to trigger a refresh.",terminal=False)
            self._df = None # Trigger refresh if target location has changed enough.
        if type(self._df) == type(None): # Need to update
            self.Update(ra,dec) # Perform the update.
        MainLog.Log("localstars.Get(): End",terminal=False)
        return self._df

#------------------------------------------------------------------------------------------------------------------------------

LocalStars = localstars(ra=0.0,dec=0.0,radius=Parameters.TargetInclusionRadius,magnitude=Parameters.TargetMinMagnitude,maxstars=2000)
# LocalStars.Get(ra,dec) returns a pandas dataframe of local stars to plot or label.

#------------------------------------------------------------------------------------------------------------------------------

# This uses built in astro corrected time functions rather than going to the web for them.
# I think these corrections will gradually fall out of date unless Skyfield is updated periodically.
ts = load.timescale() # Time handling with astro corrections.

t = ts.now() # Now.

# ------------------------------------------------------------------------------------------------------

def Ts2Datetime(tsvalue): # 6 references.
    """ Convert skyfield time value into datetime value. """
    dtvalue = tsvalue.utc_datetime()
    return dtvalue

# ------------------------------------------------------------------------------------------------------

def Datetime2Ts(dtvalue): # 1 references.
    """ Convert datetime value into skyfield time value. """
    if dtvalue.tzinfo == None: dtvalue = dtvalue.replace(tzinfo=pytz.UTC) # If timezone is not set, assign UTC.
    tsvalue = ts.from_datetime(dtvalue)
    return tsvalue

# ------------------------------------------------------------------------------------------------------

def TsDelta(basets,yyyy=0,mm=0,dd=0,h=0,m=0,s=0): # 5 references.
    """ A basic 'timedelta' functionality for Skyfield timestamps. 
        yyyy = Number of YEARS to add/subtract. 
        mm = Number of MONTHS to add/subtract. 
        dd = Number of DAYS to add/subtract. 
        h = Number of HOURS to add/subtract. 
        m = Number of MINUTES to add/subtract. 
        s = Number of SECONDS to add/subtract.
        These can be +ve or -ve and of any size, Skyfield will evaluate them to a correct timestamp. """
    WorkTs = basets.utc_datetime() # Convert to DateTime to extract components of the date.
    NewTs = ts.utc(WorkTs.year + yyyy, WorkTs.month + mm, WorkTs.day + dd, WorkTs.hour + h, WorkTs.minute + m, WorkTs.second + s)
    return NewTs

# ------------------------------------------------------------------------------------------------------

def CompassPoint(value,points=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']): # 3 references.
    """ Convert a degree value into a compass point.
        Default is 16 point compass.
        8 and 4 point compass can be generated by changing the points parameter.
        points=['N','E','S','W']
        or
        points=['N','NE','E','SE','S','SW','W','NW']             . """
    locn = int(round((value / 360) * len(points),0)) % len(points)
    return points[locn]

# ------------------------------------------------------------------------------------------------------

def AngleToHMS(value): # 9 references.
    """ Convert a decimal angle into Hours, Minutes, Seconds. """
    value = 24 * value / 360 # Convert from DEGREES to HOURS.
    h = value // 1 # Integer division. How many whole hours. 
    value = float(value) - h # Fractions of an hour left.
    value = value * 60 # Convert to minutes.
    m = value // 1 # Integer division. How many whole minutes. 
    s = float(value) - m # Fractions of a minute left.
    s = s * 60 # Convert to seconds.
    h = int(h)
    m = int(m)
    return h, m, s

# ------------------------------------------------------------------------------------------------------

# def AngleToHMSString(value): # 0 references.
#     """ Convert a decimal angle into H,M,S as string. """
#     h,m,s = AngleToHMS(value)
#     result = str(h) + "h " + str(m) + "m " + str(s) + "s"
#     return result

# ------------------------------------------------------------------------------------------------------

def HMSToAngle(h,m=None,s=None,invert=True): # 3 references.
    """ Convert hours, minutes, seconds to angle.
        Input values can be decimals, they will be converted correctly. 
        invert = True: minutes and seconds values are made negative if hour value is negative. """
    if invert and h < 0:
        if m > 0: m = -1 * m
        if s > 0: s = -1 * s
    angle = h * 360 / 24 # Convert HOURS to angle.
    if m != None: # Minutes were specified, add those.
        angle += (m / 60) * 360 / 24
    if s != None: # Minutes were specified, add those.
        angle += (s / (60 * 60)) * 360 / 24
    return angle

# ------------------------------------------------------------------------------------------------------

def DMSToAngle(degrees=0.0,minutes=0.0,seconds=0.0): # 4 references.
    """ Convert degrees, minutes and seconds into degrees. """
    # Convert all values relative to 360 degrees.
    minutes = (1 / 60) * float(minutes)
    seconds = (1 / (60 * 60)) * float(seconds)
    value = degrees + minutes + seconds
    return value

# ------------------------------------------------------------------------------------------------------

def DisplayHMS(h,m,s,length=12,rounding=1): # 3 references.
    """ Display HMS values in human readable format.
        h = hours.
        m = minutes.
        s = seconds (can be decimal). 
        length = length of returned string. 
        rounding = number of decimals precision in the seconds value. """
    hs = str(int(h))
    if len(hs) < 2: hs = hs.rjust(2)
    ms = str(int(m))
    if len(ms) < 2: ms = ms.rjust(2)
    ss = str(round(s,rounding))
    if len(ss.split('.')[0]) < 2: ss = ' ' + ss
    DH = hs + "h " + ms + "m " + ss + "s"
    DH = DH.rjust(length," ")[(-1 * length):]
    return DH

# ------------------------------------------------------------------------------------------------------

def DisplayDegree(value,length=10): # 11 references.
    """ Display a degree decimal with 3dp and right justified to specified length. """
    if value == None:
        disp = str(value).rjust(length,' ')
    else:
        disp = ((" " * length) + str(format(value, '.3f')))[(-1 * length):]
    return disp

# ------------------------------------------------------------------------------------------------------

# Construct hint lists for search functions. Lists of stars and messier objects.
Messier_namelist = [] # Empty list of Messier object names.
Messier_numlist = [] # Empty list of Messier object numbers.
for key,value in Messier_dictionary.items(): # Python3: Check every item in the starname list.
    sub_dictionary = value
    Messier_numlist.append(key)
    if len(sub_dictionary['name']) > 0:
        Messier_namelist.append(sub_dictionary['name'].lower())
Hipparcos_StarList = [] # Empty list of all the star names in the Hipparcos catalog.
Hipparcos_ConsList = [] # Empty list of all the constellation names in the Hipparcos catalog. 
for key,value in StarName_dictionary.items(): # Python3: Make a list of recognised names.
    tName = value['name']
    tCons = value['constellation']
    if len(tName) > 0 and not(tName in Hipparcos_StarList): Hipparcos_StarList.append(tName)
    if len(tCons) > 0 and not(tCons in Hipparcos_ConsList): Hipparcos_ConsList.append(tCons)
Meteor_namelist = [] # Empty list of all meteor shower names. 
for key,value in Meteor_dictionary.items(): # Python3: Check every item in the meteor list.
    Meteor_namelist.append(key)
MainLog.Log('Meteor shower list:', Meteor_namelist,terminal=False)

# And ISS position from CelesTrak data (TLE files).
def TleAgeWarning(name,tleline): # 2 references.
    epochyear = int(tleline[18:20]) + 2000
    epochday = float(tleline[20:32])
    epochdate = datetime(year=epochyear,month=1,day=1)
    epochdate += timedelta(days=int(epochday) - 1)
    daysold = (datetime.now() - epochdate).days
    MainLog.Log(name,"TLE data was updated",epochdate,terminal=False)
    if daysold > 90:
        MainLog.Log("WARNING:",name,"TLE data is",daysold,"days old. It may be inaccurate. Consider refreshing it.",level='warning',terminal=True)
        MainLog.Log("A good source of up-to-date TLE data is the CelesTrak website.",level='warning',terminal=True)
    else:
        MainLog.Log(name,"TLE data is",daysold,"days old.",terminal=True)
    
MainLog.Log("Loading earth satellites...",terminal=True)
MainLog.Log("- ISS (ZARYA)",terminal=True)
line1 = '1 25544U 98067A   23052.38451573  .00021406  00000+0  39294-3 0  9990' # Updated 21.Feb.2023
line2 = '2 25544  51.6386 182.1199 0005240  12.7328  23.3861 15.49187897383833'
ISS = EarthSatellite(line1, line2, 'ISS (ZARYA)', ts)
TleAgeWarning('ISS',line1)
# And CSS position from CelesTrak data (TLE files).
MainLog.Log("- CSS (TIANHE-1)",terminal=True)
line1 = '1 48274U 21035A   23052.28652856  .00016986  00000+0  19781-3 0  9998' # Updated 21.Feb.2023
line2 = '2 48274  41.4743 142.7275 0004853 293.9518 164.9312 15.61282286103703'
CSS = EarthSatellite(line1, line2, 'CSS (TIANHE-1)', ts)
TleAgeWarning('CSS',line1)

# ------------------------------------------------------------------------------------------------------

class FixedPoint(attributemaster): # 2 references.
    """ A target object which is a fixed altitude and azimuth position. 
        It doesn't move with the sky. """
    def __init__(self,name,alt,az):
        self.Name = name
        self.Altitude = alt
        self.Azimuth = az

#-------------------------------------------------------------------------------------------------------

class target(attributemaster): # 28 references.
    """ Class that contains all the information we need about an observation target. 
        There are some variations in the way different observation targets are handled,
        this wrapper should hide those differences from the rest of the program and
        present a common interface. """
    def __init__ (self,handle,name,objecttype=None,constellation=None,description=None,magnitude=0.0,searchgroup=None,searchterm=None,objectdiameter=None,cometpandasrow=None):
        self.Handle = handle # Skyfield object for target. This is usually provided directly by the calling routine, but in the case of 'comets' it is calculated here during initialisation.
        self.Log = MainLog.Log # Handle to the function which will log messages.
        self.Name = name # Name of object.
        self.SearchGroup = searchgroup # Which search category was used?
        self.SearchTerm = searchterm # Which search term identifies this object?
        self.ObjectType = objecttype
        self.Constellation = constellation
        self.Description = description
        self.NotesLines = [] # Can be a text block to include in documentation. (List of text lines)
        self.Magnitude = magnitude
        self.DiameterDegrees = objectdiameter # diameter of the object in the sky. # Used to warn if target is too small.!
        self.RecommendedExposure = None # Recommended exposure for this object.
        self.HomeSite = None # Skyfield object for home site.
        self.HomeSiteTopos = None # Skyfield object for home site.
        self.ts = load.timescale() # Time handling with astro corrections.
        self.SetHome(Parameters.HomeLat,Parameters.HomeLon) # Use global variables at the moment. Requires that global list 'planets' is available too.
        self.CometPandasRow = cometpandasrow # Comets don't have a skyfield object in 'Handle' we calculate the position differently, so store their pandas row here. 
        self.CacheRADeg = None # Cached RA value for target. Set each time RaDecDegrees is called.
        self.CacheDec = None # Cached Dec value for target. Set each time RaDecDegrees is called.
        self.CacheAlt = None # Cached Altitude value for target. Set each time AzAltDegrees is called.
        self.CacheAz = None # Cached Azimuth value for target. Set each time AzAltDegrees is called.

        # Calculate field rotation for target.
        CentreRa, CentreDec = self.RaDecHours() # Calculations for target from observer's location. Returns decimal degree values.
        CentreDec = CentreDec.degrees # Convert to pure float degree value.
        # Offset by nn degrees declination above/below the target. We'll measure how this point moves around the target to calculate the rotation rate.
        # Offset BELOW if we're in the northern hemisphere, ABOVE if we're in the southern hemisphere.
        if Parameters.HomeLatVal > 0: CentreDec -= 5.0 
        else: CentreDec += 5.0
        # Define a fixed radec point offset from the target, we use this to measure field rotation.
        self.RotationPoint = Star(ra_hours=(CentreRa.hms()[0],CentreRa.hms()[1],CentreRa.hms()[2]), dec=Angle(degrees=CentreDec))

        # Remove HIPCacheDf and replace with LocalStars feature globally instead.
        self.HIPCacheDf = None # List of surrounding Hipparcos stars that should be added to preview and targeting images.

    def CurrentMagnitude(self,time=None):
        """ Calculate the current magnitude (or for a specific time) if possible. """
        if time == None: time = self.CurrentTime()
        result = self.Magnitude # Default to the standard magnitude for this object if known.
        try:
            astrometric = self.HomeSite.at(time).observe(self.Handle)
            temp = planetary_magnitude(astrometric)
            if temp != None: result = temp
            self.Log("target.CurrentMagnitude: planetary_magnitude returned",temp,terminal=False)
        #except Exception as e:
        except Exception:
            self.Log("target.CurrentMagnitude: planetary_magnitude didn't work for this target.",terminal=False)
        # *Q* Could also try comet magnitude calculation, and for stars pull the data from the hipparcos catalog. 
        return result

    def UpdateLocation(self,newhandle):
        """ Revise the skyfield target handle. 
            Used when performing sky surveys of multiple locations around a target.
            Use this if you need to modify the location of the target for some reason (eg new RADEC) but retain all the other attributes. """
        self.Handle = newhandle
        self.Log("target.UpdateLocation(): New co-ordinates updated to the target.",terminal=False)

    def ClearNotes(self):
        """ Remove any pre-existing observation notes. """
        self.NotesLines = []

    def AskForNotes(self,notelist=None):
        """ Prompt for descriptive text or other observation notes to be recorded.
            These notes are added to the preview images and also stored in the 
            observation notes file. """
        #if type(notelist) != type(list):
        if not isinstance(notelist,list):
            notelist = [] # Empty list.
            print(textcolor.yellow("Enter observation notes:"))
            while True:
                line = input(textcolor.cyan("Enter text ('x' to quit): "))
                if line.lower().strip() == 'x': break # Terminate the input.
                notelist.append(line) # Add text to list.
        self.NotesLines = notelist

    # def WillBeVisible(self,windowseconds=3600,accuracy=30):
    #     """ Return TRUE if the object WILL become visible soon.
    #         Must be within observable area of sky within the 'windowseconds' timeframe.
    #         Returns datetime value if it will be visible, or None.
    #         Result accurate to xx (accuracy) seconds. 
    #         Simply runs the clock forward to see if the target appears within the observable window. """
    #     tstart = self.CurrentTime().utc_datetime() # datetime start of the window.
    #     tend = tstart + timedelta(seconds=windowseconds) # datetime end of the window.
    #     result = None # No rise time yet.
    #     tloop = tstart
    #     while tloop < tend: # Loop until risen or out of time.
    #         t0 = Datetime2Ts(tloop) # Convert to Skyfield time type.
    #         if self.Visible(time=t0): # Is it visible?
    #             result = tloop
    #             self.Log('target.WillBeVisible=', tloop, terminal=False)
    #             break
    #         tloop = tloop + timedelta(seconds=accuracy) # Move forward in the window xx seconds at a time.
    #     risetime, settime = self.RiseSet()
    #     self.Log('target.WillBeVisible: RiseSet()=', risetime, settime, terminal=False)
    #     if risetime != None:
    #         result = risetime
    #     return result # Returns Python datetime if visible or None.
    
    def NextRiseSet(self):
        """ Return next horizon event and time. 
            Rise, Set, None """
        risetime, settime = self.RiseSet()
        eventtime = None
        eventtype = None
        if risetime != None and risetime > NowUTC():
            eventtime = risetime
            eventtype = 'rise'
        if settime != None and settime > NowUTC():
            if eventtime == None or eventtime > settime:
                eventtime = settime
                eventtype = 'set'
        self.Log("target.NextRiseSet(",self.Name,"): rise",risetime,"set",settime,"eventtime",eventtime,"eventtype",eventtype,terminal=False)
        return eventtype, eventtime

    def NextRiseSetHHMM(self):
        eventtype, eventtime = self.NextRiseSet()
        result = ''
        if eventtype == 'rise':
            result = str(eventtime)[11:16] + Symbol['up']
        elif eventtype == 'set':
            result = str(eventtime)[11:16] + Symbol['down']
        self.Log("target.NextRiseSetHHMM(",self.Name,"): eventtime",eventtime,"eventtype",eventtype,"result",result,terminal=False)
        return result

    def RiseSet(self):
        """ Return next rise and set times for the object. 
            Uses Skyfield's almanac functions for this. """
        risetime = None # No RISE time until identified.
        settime = None # No SET time until identified.
        if self.IsFixedPoint(): # No risetime/settime time for fixed point. 
            pass
        else: # Moving target, so check for rise/set times.
            f = almanac.risings_and_settings(planets, self.Handle, self.HomeSiteTopos)
            tsnow = self.CurrentTime().utc_datetime() # Current Timestamp as conventional Python UTC datetime value.
            t0 = self.ts.utc(tsnow.year, tsnow.month, tsnow.day) # Generate skyfield UTC timestamp for start of day.
            tsnow += timedelta(days=1) # Move forward 24 hours.
            t1 = self.ts.utc(tsnow.year, tsnow.month, tsnow.day + 1) # Generate skyfield UTC timestamp for start of following day.
            t, y = almanac.find_discrete(t0, t1, f) # Return list of rise/set times within window.
            self.Log('target.RiseSet: t',t, 'y:', y, terminal=False)
            for ti, yi in zip(t, y): # Combine t and y lists.
                self.Log('target.RiseSet(',self.Name,'): zipped',ti, yi, terminal=False)
                tidt = ti.utc_datetime()
                if tidt < NowUTC(): continue # In the past, ignore it.
                if yi and risetime == None: # First future rise time.
                    risetime = tidt
                elif settime == None: # First future set time.
                    settime = tidt
        self.Log("target.RiseSet(",self.Name,"): rise",risetime,"set",settime,terminal=False)
        return risetime, settime

    def CurrentTime(self):
        """ Return skyfield format current time.
            Available as a method so that offsets or other features can be added if needed. """
        return self.ts.now() # Now.

    def RotationPointBearing(self,time=None):
        # AltAz mounts suffer from a characteristic rotation of the field of view as the telescope tracks an object.
        # - This field rotation can cause star trails to appear in stars on the outer edges of the image if the exposure is too long.
        # - This shows the rotation against a calculated point in the sky. 
        # The calculated point is xx degrees of declination above/below the target object.
        # *Q* Only tested for NORTHERN HEMISPHERE obervations. 
        if time == None: time = self.CurrentTime() # Current time.
        self.Log('target.RotationPointBearing(',str(time.utc_strftime()),'): Start',terminal=False)
        TempStarAstro = HomeSite.at(time).observe(self.RotationPoint) # Work out where the rotation point is.
        TempStarApparent = TempStarAstro.apparent() # Calculate its position in the sky
        TempStarAlt, TempStarAz, TempStardistance = TempStarApparent.altaz() # Get the azimuth and altitude position of the rotation point in the sky.
        self.Log('target.RotationPointBearing: Rotation point Alt/Az',TempStarAlt, TempStarAz,terminal=False)
        az_degree, alt_degree = self.AzAltDegrees(time=time) # Get current target position.
        self.Log('target.RotationPointBearing: Target Alt/Az',alt_degree, az_degree,terminal=False)
        PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt.degrees,TempStarAz.degrees,alt_degree,az_degree)
        self.Log('target.RotationPointBearing: Relative Alt/Az',PlotStarAlt, PlotStarAz,terminal=False)
        TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,SensorInUse.PixelHeight,SensorInUse.PixelWidth)
        self.Log('target.RotationPointBearing: PlotRelative X/Y',TempStarX, TempStarY,terminal=False)
        xpos = round(SensorInUse.PixelWidth/2)
        ypos = round(SensorInUse.PixelHeight/2)
        # Calculate rotation angle.
        opposite = TempStarX - xpos
        adjacent = TempStarY - ypos
        self.Log('target.RotationPointBearing: Opposite',opposite, ', Adjacent',adjacent,terminal=False)
        rotation = math.degrees(math.atan2(opposite,adjacent))
        self.Log('target.RotationPointBearing: rotation=',rotation,DegreeSymbol,terminal=False)
        return rotation

    def RotationPixels(self,angle=None,radius=None):
        """ Convert a field rotation into worst-case pixel count in the corner of the image. 
            radius parameter is the number of pixels radius from the centre of the image. If None, sensor size is used.
            span is the timespan to calculate rotation over. """
        # Convert the field rotation angle into the number of pixels in the most extreme corner of the image. That will show the maximum smearing due to rotation.
        self.Log('target.RotationPixels(',angle,'): Start.',terminal=False)
        self.Log('target.RotationPixels: ImaageSize',SensorInUse.PixelWidth,SensorInUse.PixelHeight,terminal=False)
        # If no angle, calculate one based upon current selected exposure.
        if angle == None:
            angle = self.RotationArc(span=CameraInUse.ExposureSeconds)
        # Radius of worst case rotation is the distance from the centre of the image to the corner.
        if radius == None:
            radius = math.sqrt(((SensorInUse.PixelWidth / 2) ** 2) + ((SensorInUse.PixelHeight / 2) ** 2))
        self.Log('target.RotationPixels: radius',radius,terminal=False)
        circumference = radius * 2 * math.pi # How many pixels in total for the circumference of the circle defined by radius?
        self.Log('target.RotationPixels: circumference',circumference,terminal=False)
        arclength = circumference * angle / 360 # How many pixels in the arc defined by radius and angle.
        self.Log('target.RotationPixels: arclength =',arclength,terminal=False)
        return arclength

    def RotationArc(self,span=3600,time=None):
        """ Return field rotation rate.
            This calculates the rate over an hour, but returns a result scaled to the requested time span.
            Calculation is centred upon the current time unless time parameter has a value. """
        self.Log('target.RotationArc (',span,'): Start.',terminal=False)
        if time == None: time = self.CurrentTime()
        calcperiod = 3600 # Calculate the rotation over an hour and then scale to the requested period. This reduces some inherent precision issues with small periods.
        t1 = TsDelta(time,s=-1 * round(calcperiod / 2)) # Start rotation at 30minutes ago.
        t2 = TsDelta(t1,s=calcperiod) # End rotation 30minutes ahead.
        self.Log('target.RotationArc: Times',t1.utc_strftime(),t2.utc_strftime(),terminal=False)
        a1 = self.RotationPointBearing(t1) # Rotation angle at start.
        a2 = self.RotationPointBearing(t2) # Rotation angle at end.
        self.Log('target.RotationRate: Angles',a1,DegreeSymbol,a2,DegreeSymbol,terminal=False)
        rate = a2 - a1 # Delta of rotation angle.
        self.Log('target.RotationArc: gross rate=',rate,DegreeSymbol,terminal=False)
        rate = rate * span / calcperiod
        self.Log('target.RotationArc: span rate=',rate,DegreeSymbol,terminal=False)
        return rate # Field rotates at 'rate' degrees per 'span' seconds.

    def ConvToTS(self,timestamp):
        """ Convert datetime style timestamp into Skyfield UTC timescale. 
            This works around the missing timezone value in default datetime variables too. 
            *Q* This duplicates the Datetime2Ts() function! Standardise. """
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        hour = timestamp.hour
        minute = timestamp.minute
        second = timestamp.second
        result = self.ts.utc(year,month,day,hour,minute,second)
        return result

    def SetHome(self,homelat,homelon):
        self.HomeSiteTopos = Topos(homelat,homelon)
        self.HomeSite = planets['earth'] + self.HomeSiteTopos # Define HomeSite as a point on earth. Could be from GPS too.

    def PlanetAzAltDegrees(self,name='moon',time=None):
        """ Returns the current altitude and azimuth of any planetary object from Skyfield calculations. 
            - Default is the Moon.
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used. """
        if self.HomeSite == None:
            raise Exception ("Target.AzAltDegrees: HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        solarobject = planets[name]
        # Sun centered vectors. (Barycentric)
        # Calculations for a natural body.
        astrometric = self.HomeSite.at(t).observe(solarobject)
        alt, az, d2 = astrometric.apparent().altaz()
        azd = az.degrees # Convert from Skyfield 'angle' to simple float degree value.
        altd = alt.degrees
        return azd, altd

    def AzAltDegrees(self,time=None):
        """ Returns the current altitude and azimuth of the target from Skyfield calculations. 
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used. """
        if self.HomeSite == None:
            raise Exception ("Target.AzAltDegrees: HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        if self.IsFixedPoint(): # Telescope is following fixed alt/az position. Ignoring sky movement.
            alt = self.Handle.Altitude
            az = self.Handle.Azimuth
            return az, alt
        elif hasattr(self.Handle,'center') and self.Handle.center == 399: # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite.
            difference = self.Handle - self.HomeSiteTopos # Can't use HomeSite because that's the wrong vector type !?!
            topocentric = difference.at(t)
            alt, az, d2 = topocentric.altaz()
        else: # Sun centered vectors. (Barycentric)
            # Calculations for a natural body.
            astrometric = self.HomeSite.at(t).observe(self.Handle)
            alt, az, d2 = astrometric.apparent().altaz()
        azd = az.degrees # Convert from Skyfield 'angle' to simple float degree value.
        altd = alt.degrees
        # METEOR SHOWER co-ordinates are shifted to a likely area of the sky to see the meteors.
        # The catalog contains the radiant point, but this is not the best place to look.
        # - Online recommendations say to use azimuth 45 degrees from radiant point and altitude of 45 degrees.
        # - Here I choose the azimuth 45 degrees from the radiant point and closest to due south.
        if self.ObjectType == 'meteor': # Meteor shower mode.
            altd = 45.0 # Always point to 45 degrees above the horizon.
            # Check 45 degrees either side of the radiant point.
            az1 = azd - 45.0 
            az2 = azd + 45.0 
            if abs(az1 - 180) < abs(az2 - 180): # az1 is closest to due south. Use that.
                azd = az1
            else: # az2 is closest to due south. Use that.
                azd = az2
        self.CacheAz = azd # Cached azimuth value for target. Set each time AzAltDegrees is called.
        self.CacheAlt = altd # Cached altitude value for target. Set each time AzAltDegrees is called.
        return azd, altd

    def IsFixedPoint(self):
        """ Return TRUE if this is a fixed point. Else False.
            This is used in places to allow the telescope to take photos even though 
            it is not following a trajectory. """
        if isinstance(self.Handle,FixedPoint):
            return True
        else:
            return False

    def CanMultisessionAlign(self,acceptabletypes=['radec','messier','ngc','hipparcos']):
        """ Returns TRUE if the current target can be live stacked across sessions.
                These are objects which remain static against the sky as it moves,
                this allows astroalign to work across multiple sessions because it's based upon star matching.
            Returns FALSE otherwise. 
                These are objects which do not move with the sky.
                Targets like planets, meteor showers or ALT AZ targets all shift against the star background.
                They will not stack nicely across multiple sessions because the target drifts too much. """
        if self.ObjectType in acceptabletypes:
            result = True # These object types can be aligned for stacking across multiple sessions.
        else: # Other objects will move against the background, so cannot be aligned reliably between sessions.
            result = False
        return result

    def Visible(self,time=None):
        """ Return TRUE if the target is currently in a portion of the sky that the telescope can observe. 
            Return FALSE if the target is outside the observable portion of the sky. """
        result = True
        az, alt = self.AzAltDegrees(time=time)
        for i in MotorControls:
            if i.MotorName == 'azimuth':
                if az < i.MinAngle or az > i.MaxAngle: result = False
            if i.MotorName == 'altitude':
                if alt < i.MinAngle or alt > i.MaxAngle: result = False
        return result
    
    def ApproachingLimit(self,time=None):
        """ Return TRUE if the target is approaching the limit of telescope movement. 
            else FALSE. """
        result = False
        az, alt = self.AzAltDegrees(time=time)
        for i in MotorControls:
            if i.MotorName == 'azimuth':
                if az <= i.MinWarningAngle or az >= i.MaxWarningAngle: result = True
            if i.MotorName == 'altitude':
                if alt <= i.MinWarningAngle or alt >= i.MaxWarningAngle: result = True
        return result

    def RaDecHours(self,time=None):
        """ Returns the current Right Ascension and Declination of the target from Skyfield calculations, RA and Dec in Skyfield Angle objects. 
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used. """
        if self.HomeSite == None:
            raise Exception ("Target.RaDecHours: HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        if self.IsFixedPoint(): # Telescope is following fixed alt/az position. Ignoring sky movement.
            direction = self.HomeSite.at(t).from_altaz(alt_degrees=self.Handle.Altitude, az_degrees=self.Handle.Azimuth)
            ra, dec, distance = direction.radec()
        elif hasattr(self.Handle,'center') and self.Handle.center == 399: # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite.
            difference = self.Handle - self.HomeSiteTopos # Can't use HomeSite because that's the wrong vector type !?!
            topocentric = difference.at(t)
            ra, dec, _ = topocentric.radec()
        else: # Sun centered vectors. (Barycentric)
            # Calculations for a natural body.
            astrometric = self.HomeSite.at(t).observe(self.Handle)
            ra, dec, _ = astrometric.apparent().radec()
        self.CacheRADeg = ra._degrees # Cached RA value for target. Set each time RaDecDegrees is called.
        self.CacheDec = dec.degrees # Cached Dec value for target. Set each time RaDecDegrees is called.
        return ra, dec

    def RaDecDegrees(self,time=None):
        """ Returns the current Right Ascension and Declination of the target from Skyfield calculations as degrees. 
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used. """
        if self.HomeSite == None:
            raise Exception ("Target.RaDecDegrees: HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        if self.IsFixedPoint(): # Telescope is following fixed alt/az position. Ignoring sky movement.
            direction = self.HomeSite.at(t).from_altaz(alt_degrees=self.Handle.Altitude, az_degrees=self.Handle.Azimuth)
            ra, dec, distance = direction.radec()
        elif hasattr(self.Handle,'center') and self.Handle.center == 399: # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite.
            difference = self.Handle - self.HomeSiteTopos # Can't use HomeSite because that's the wrong vector type !?!
            topocentric = difference.at(t)
            ra, dec, d2 = topocentric.radec()
        else: # Sun centered vectors. (Barycentric)
            # Calculations for a natural body.
            astrometric = self.HomeSite.at(t).observe(self.Handle)
            ra, dec, d2 = astrometric.apparent().radec()
        self.CacheRADeg = ra._degrees # Cached RA value for target. Set each time RaDecDegrees is called.
        self.CacheDec = dec.degrees # Cached Dec value for target. Set each time RaDecDegrees is called.
        return ra._degrees, dec.degrees

    def LunarPhase(self,time=None):
        """ Return the phase of the Moon. 
            0degrees = New Moon.
            1-179degrees = Waxing.
            180degrees = Full Moon.
            181-359degrees = Waning. """
        result = None # No result unless successful
        if time == None: time = self.CurrentTime()
        result = almanac.moon_phase(planets, time)
        return result.degrees

    def MoonFull(self):
        """ Return the % of full moon.
            Used to indicate light pollution from the moon. """
        moonphase = self.LunarPhase()
        # Convert moonphase into an approximate % full. We're interested in light pollution levels.
        # *Q* This is a stopgap calculation. Can be more precise.
        if moonphase > 180: 
            moonphase = 360 - moonphase
        moonphase = 100 * moonphase / 180
        self.Log('target.MoonFull: moonphase',moonphase,terminal=False)
        return moonphase

    def MoonWaxing(self):
        """ Return TRUE if moon is Waxing. 
            Return FALSE if moon is Waning. """
        if self.LunarPhase() <= 180: result = True
        else: result = False
        return result

    def ApparentCometMagnitudeGK(self):
        """ Calculate comet apparent magnitude using GK model. 
        
            Code based upon example by Bernmeister https://github.com/skyfielders/python-skyfield/issues/416 

             def getApparentMagnitude_gk( g_absoluteMagnitude, k_luminosityIndex, bodyEarthDistanceAU, bodySunDistanceAU ):
                 return g_absoluteMagnitude + \
                        5 * math.log10( bodyEarthDistanceAU ) + \
                        2.5 * k_luminosityIndex * math.log10( bodySunDistanceAU ) 
                        
            """
                        
        # *Q* Field names for MPC comet data were corrected in Skyfield after Nov.2020, _h and _g column names have been corrected to _g, _k
        if 'magnitude_h' in comets.columns: # Old format field names. Pre Nov.2020 version of Skyfield.
            g_absoluteMagnitude = self.CometPandasRow['magnitude_h']
            k_luminosityIndex = self.CometPandasRow['magnitude_g']
            self.Log("target.ApparentCometMagnitudeGK(): Using OLD format fieldnames.",terminal=False)
        else: # Post Nov.2020 version of Skyfield. To be verified.
            g_absoluteMagnitude = self.CometPandasRow['magnitude_g']
            k_luminosityIndex = self.CometPandasRow['magnitude_k']
            self.Log("target.ApparentCometMagnitudeGK(): Using NEW format fieldnames.",terminal=False)
        t = self.CurrentTime()
        temp_ra, temp_dec, sunBodyDistance = planets['sun'].at(t).observe(self.Handle).radec() 
        temp_alt, temp_az, earthBodyDistance = self.HomeSite.at(t).observe(self.Handle).apparent().altaz() 
        temp_alt, temp_az, earthSunDistance = self.HomeSite.at(t).observe(planets['sun']).apparent().altaz() 
        apparentMagnitude = g_absoluteMagnitude + (5 * math.log10(earthBodyDistance.au)) + (2.5 * k_luminosityIndex * math.log10(sunBodyDistance.au))
        apparentMagnitude = round(apparentMagnitude,1) # Magnitude to 1 decimal place.
        self.Log("target.ApparentCometMagnitudeGK(): Apparent magnitude:", apparentMagnitude,terminal=False)
        return apparentMagnitude

# ------------------------------------------------------------------------------------------------------

def TwilightLevel(): # 1 references.
    """ Return the current twilight level for the current location. """
    temptarget = target(planets['sun'],name='sun',objecttype="sun",description="The Sun",magnitude=-26.7,searchgroup='solar',searchterm="sun")
    az, alt = temptarget.AzAltDegrees()
    if alt > 0: result = "daytime"
    elif alt >= -6: result = "civil twilight"
    elif alt >= -12: result = "nautical twilight"
    elif alt >= -18: result = "astronomical twilight"
    else: result = "nighttime"
    return result

# ------------------------------------------------------------------------------------------------------

# def BestMatch(available_targets,chosen_target): # 0 references.
#     """ Given a list of target names, and a partial value, see if there's a good match.
#         This returns the first good match, it doesn't care if multiple matches could be suitable. """
#     # If there's a good and unique match in AvailableTargets, this returns the complete name from a partial input.
#     # Otherwise it just returns the original input unchanged.
#     Result = chosen_target
#     Matches = [] # No good matches found so far.
#     for target in available_targets: # Check each entry in turn.
#         if chosen_target == target[0:len(chosen_target)]: # The input characters match the start of this item.
#             Matches.append(target)
#     if len(Matches) == 1:
#         # Only 1 possible match, so use that.
#         Result = Matches[0]
#     return Result

# ------------------------------------------------------------------------------------------------------

def ChooseMessier(prechosen=None,sizewarning=True): # 4 references.
    """ Select an object from the Messier catalog by Catalog number or name. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
    objecttype = None
    magnitude= 0.0
    obstarget = None
    while Result == "": # Loop until a target has been selected. 
        if prechosen == None:
            SearchValue = input(textcolor.cyan("Enter Messier target (number, name, ? or 'x'): "))
        else:
            SearchValue = prechosen
        if SearchValue == "?": # Help
            print (textcolor.yellow("Recognised catalog IDs: ") + str(Messier_numlist))
            print (textcolor.yellow("Recognised names: ") + str(Messier_namelist))
            continue
        SearchValue = SearchValue.lower() # Lower case character matching. 
        if SearchValue == 'x': # Cancel
            return None
        for key,value in Messier_dictionary.items(): # Python3: Check every item in the starname list.
            sub_dictionary = value
            if key.lower() == SearchValue: # Messier catalog number matches.
                Result = key.lower()
                p = Star(ra_hours=(sub_dictionary['ra'][0], sub_dictionary['ra'][1], sub_dictionary['ra'][2]), dec_degrees=(sub_dictionary['dec'][0], sub_dictionary['dec'][1], sub_dictionary['dec'][2]))
                const = sub_dictionary['constellation']
                desc = sub_dictionary['description']
                objecttype = sub_dictionary['type']
                magnitude = sub_dictionary['magnitude']
                width = sub_dictionary['width']
                height = sub_dictionary['height']
                MainLog.Log("ChooseMessier: Found by catalog number (" + key + ")",terminal=False)
                break
            if sub_dictionary['name'][:len(SearchValue)] == SearchValue:
                Result = key.lower()
                p = Star(ra_hours=(sub_dictionary['ra'][0], sub_dictionary['ra'][1], sub_dictionary['ra'][2]), dec_degrees=(sub_dictionary['dec'][0], sub_dictionary['dec'][1], sub_dictionary['dec'][2]))
                const = sub_dictionary['constellation']
                desc = sub_dictionary['description']
                objecttype = sub_dictionary['type']
                magnitude = sub_dictionary['magnitude']
                width = sub_dictionary['width']
                height = sub_dictionary['height']
                MainLog.Log("ChooseMessier: Found by object name (" + sub_dictionary['name'] + ") catalog number " + key + ".",terminal=False)
                break
        if Result == "": # Still no match. Give up and ask again. 
            if prechosen != None:
                MainLog.Log("ChooseMessier: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("Messier: Nothing matched, try again.")
    NeatName = SafeName(Result)
    # Establish a size for the object if known.
    sizemin = None
    if width != None: 
        if sizemin == None or width > sizemin: sizemin = width
    if height != None: 
        if sizemin == None or height > sizemin: sizemin = height
    MainLog.Log('ChooseMessier: Selected target is width', width, 'minutes, height', height, 'minutes, size', sizemin, 'minutes.',terminal=False)
    if sizemin != None: 
        sizedeg = DMSToAngle(minutes=sizemin) # Convert from minutes to degrees.
        MainLog.Log('ChooseMessier: Selected target size is', sizedeg, 'degrees.',terminal=False)
        sizepix = sizedeg * CameraInUse.PixelsPerFovDegreeWidth # How many pixels is this size?
        MainLog.Log('ChooseMessier: Selected target is about', sizepix, 'pixels across.',terminal=False)
        if sizepix < 10 and sizewarning: # Warn if the object is quite small in the resulting images.
            MainLog.Log('ChooseMessier: The target is quite small, only about', sizepix, 'pixels across.',terminal=True)
    else:
        MainLog.Log('ChooseMessier: The target is unknown size.',terminal=False)
    obstarget = target(p,name=NeatName,objecttype=objecttype,constellation=const,description=desc,magnitude=magnitude,searchgroup='messier',searchterm=Result,objectdiameter=sizedeg)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseMeteor(prechosen=None): # 4 references.
    """ Select a meteor shower. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
    objecttype = None
    magnitude= 0.0
    obstarget = None
    MeteorChooser = listchooser(Meteor_namelist)
    while Result == "": # Loop until a target has been selected. 
        if prechosen == None:
            SearchValue = MeteorChooser.Prompt()
        else:
            SearchValue = prechosen
        for key,value in Meteor_dictionary.items(): # Python3: Check every item in the meteor shower list.
            sub_dictionary = value
            if key == SearchValue:
                Result = key.lower()
                p = Star(ra_hours=(sub_dictionary['rah'], sub_dictionary['ram'], 0), dec_degrees=(sub_dictionary['dec'], 0, 0))
                const = sub_dictionary['constellation']
                desc = key + ' meteor shower'
                objecttype = 'meteor'
                MainLog.Log("ChooseMeteor: Found by meteor shower name (" + key+ ").",terminal=False)
                break
        if Result == "": # Still no match. Give up and ask again. 
            if prechosen != None:
                MainLog.Log("ChooseMeteor: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("Meteor: Nothing matched, try again.")
    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    # Find location of origin.
    obstarget = target(handle=p,name=NeatName,objecttype=objecttype,constellation=const,description=desc,magnitude=magnitude,searchgroup='meteor',searchterm=SearchValue)
    az, alt = obstarget.AzAltDegrees() # Get initial position in the sky. We'll turn this into a fixed point.
    # Move a useful angle away from the origin.
    es = FixedPoint(name=NeatName,alt=alt,az=az) # Set a fixed point in the sky. The telescope will remain under direct control and not use trajectories.
    obstarget = target(es,name=NeatName,objecttype="meteor",description=desc,magnitude=0.0,searchgroup='meteor',searchterm=SearchValue)
    MainLog.Log("NOTE: Meteor shower selected. Camera will point to a likely area of the sky to capture meteors, not the radiant point.",terminal=False)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseNGC(prechosen=None): # 4 references.
    """ Select a NGC object. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
    objecttype = None
    magnitude= 0.0
    obstarget = None
    while Result == "": # Loop until a target has been selected. 
        if prechosen == None:
            NGCChooser = listchooser(NGC_Namelist)
            SearchValue = NGCChooser.Prompt()
        else:
            SearchValue = prechosen
        if SearchValue == None: # User quit the search.
            return None # Scrap the attempt.
        for key,value in NGCDict.items(): # Python3: Check every item in the NGC list.
            sub_dictionary = value
            if key == SearchValue:
                Result = key.lower()
                p = Star(ra_hours=(sub_dictionary['rah'], sub_dictionary['ram'], sub_dictionary['ras']), dec_degrees=(sub_dictionary['ded'], sub_dictionary['dem'], sub_dictionary['des']))
                magnitude = sub_dictionary['magnitude']
                desc = key + ' NGC'
                objecttype = 'ngc'
                MainLog.Log("ChooseNGC: Found by NGC number (" + key + ").",terminal=False)
                break
        if Result == "": # Still no match. Ask again. 
            if prechosen != None:
                MainLog.Log("ChooseNGC: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("NGC: (",str(SearchValue),") Nothing matched, try again.")
    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    obstarget = target(handle=p,name=NeatName,objecttype=objecttype,constellation=const,description=desc,magnitude=magnitude,searchgroup='ngc',searchterm=SearchValue)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseComet(prechosen=None): # 4 references.
    """ Select a comet from the comet catalog by comet name. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameters is not recognised, the user is asked fora value instead. """
        
    Result = ""
    desc = None
    # const = None
    objecttype = "comet"
    obstarget = None
    # magnitude = None
    p = None
    while Result == "": # Loop until a target has been selected. 
        if prechosen == None:
            CometChooser = listchooser(CometList)
            SearchValue = CometChooser.Prompt()
        else:
            SearchValue = prechosen
        if SearchValue == None: # User quit the search.
            return None # Scrap the attempt.
        if Result == "": # No match yet.
            for c in comets['designation']: # Python3: Check every item in the comet list.
                if c == SearchValue:
                    Result = SearchValue.lower()
                    row = comets.loc[c] # Store the Pandas row in the TargetObject because we don't immediately create the 'Star' object.
                    MainLog.Log("ChooseComet: Pandas row available data for the comet:", str(list(comets.columns)),terminal=False) # Show available data.
                    p = planets['sun'] + mpc.comet_orbit( row, ts, GM_SUN)
                    desc = "Comet " + c
                    objecttype = "comet"
                    MainLog.Log("ChooseComet: Found by comet name (" + c + ")",terminal=False)
                    break
        if Result == "": # Still no match. Give up and ask again. 
            if prechosen != None:
                MainLog.Log("ChooseComet: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("Comet: Nothing matched, try again.")

    MainLog.Log("ChooseComet: NOTE: obstarget.handle() is populated in the target.__init__() method in the case of comets.",terminal=False)

    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    obstarget = target(handle=p,name=NeatName,objecttype=objecttype,description=desc,constellation=None,magnitude=None,searchgroup='comet',searchterm=SearchValue,cometpandasrow=row)
    obstarget.Magnitude = obstarget.ApparentCometMagnitudeGK() 
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseHipparcos(prechosen=None): # 4 references.
    """ Select a star from the Hipparcos catalog by Catalog number, star name or constellation. 
        'prechosen' means that the input is provided externally, the function will not prompt. 
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
    objecttype = "star"
    obstarget = None
    while Result == "": # Loop until a target has been selected. 
        if prechosen == None: # We've not received a target name, so ask the user.
            SearchValue = input(textcolor.cyan("Enter Hipparcos target (number,? or 'x'): ")) # Python3 
        else: # We've received a target name, use that for selection.
            SearchValue = prechosen
        SearchValue = SearchValue.lower() # Lower case character matching. 
        if SearchValue == "?": # Help
            print('Enter the integer part of the hipparcos number.')
            continue
        if SearchValue == 'x': # Cancel
            return None
        # First and easiest check is for a direct entry in the catalog. Check for the HIP number durectly.
        SearchInt = TextToInt(SearchValue)
        if SearchInt != None and SearchInt in HipparcosDf.index:
            Result = "HIP_" + str(SearchInt)
            # row = HipparcosDf.loc[SearchInt] # Store the Pandas row in the TargetObject because we don't immediately create the 'Star' object.
            MainLog.Log("ChooseHipparcos: Pandas row available data for the star:", str(list(HipparcosDf.columns)),terminal=False) # Show available data.
            p = Star.from_dataframe(HipparcosDf.loc[SearchInt])
            desc = "Star HIP_" + str(SearchInt) + " (Hipparcos)."
            objecttype = "star"
            magnitude = HipparcosDf.loc[SearchInt].magnitude
            MainLog.Log("ChooseHipparcos: Found by catalog number.",terminal=False)
        if Result == "": # No match yet.
            if prechosen != None:
                MainLog.Log("ChooseHipparcos: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Return to calling routine.
            print("Hipparcos: Nothing matched, try again.")

    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    obstarget = target(handle=p,name=NeatName,objecttype=objecttype,description=desc,constellation=const,magnitude=magnitude,searchgroup='hipparcos',searchterm=str(SearchInt))
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseSolar(prechosen=None): # 8 references.
    """ Choose a solar system target. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    MainLog.Log("ChooseSolar: Begin",terminal=False)
    AvailableTargets = ["iss","css","sun","mercury","venus","moon","mars","jupiter","saturn","uranus","neptune","pluto"]
    PlanetChooser = listchooser(AvailableTargets,compress=False) # Always show the full list.
    obstarget = None
    while Result == "":
        if prechosen == None: # We've not received a prechosen name, so ask the user.
            Result = PlanetChooser.Prompt()
        else: # We've received a prechosen name. Don't ask the user.
            Result = prechosen
        if Result == None: # Nothing selected.
            return None # Quit.
        MainLog.Log("ChooseSolar: Observation target input:" + Result,terminal=False)
        if Result not in AvailableTargets:
            if prechosen != None:
                MainLog.Log("ChooseSolar: Prechosen not " + str(prechosen) + " recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print (textcolor.red("'" + Result + "' is not a recognised target name. Try again."))
            Result = ""
    if Result == "sun":
        obstarget = target(planets['sun'],name=Result,objecttype="sun",description="The Sun",magnitude=-26.7,searchgroup='solar',searchterm=Result)
    elif Result == "mercury":
        obstarget = target(planets['mercury barycenter'],name=Result,objecttype="planet",description=Result,magnitude=0.23,searchgroup='solar',searchterm=Result)
    elif Result == "venus":
        obstarget = target(planets['venus barycenter'],name=Result,objecttype="planet",description=Result,magnitude=-4.4,searchgroup='solar',searchterm=Result)
    elif Result == "moon":
        obstarget = target(planets['moon'],name=Result,objecttype="moon",description=Result,magnitude=-12.5,searchgroup='solar',searchterm=Result)
    elif Result == "mars":
        obstarget = target(planets['mars barycenter'],name=Result,objecttype="planet",description=Result,magnitude=-2.91,searchgroup='solar',searchterm=Result)
    elif Result == "jupiter":
        obstarget = target(planets['jupiter barycenter'],name=Result,objecttype="planet",description=Result,magnitude=-2.7,searchgroup='solar',searchterm=Result)
    elif Result == "saturn":
        obstarget = target(planets['saturn barycenter'],name=Result,objecttype="planet",description=Result,magnitude=-0.55,searchgroup='solar',searchterm=Result)
    elif Result == "uranus":
        obstarget = target(planets['uranus barycenter'],name=Result,objecttype="planet",description=Result,magnitude=5.68,searchgroup='solar',searchterm=Result)
    elif Result == "neptune":
        obstarget = target(planets['neptune barycenter'],name=Result,objecttype="planet",description=Result,magnitude=7.78,searchgroup='solar',searchterm=Result)
    elif Result == "pluto":
        obstarget = target(planets['pluto barycenter'],name=Result,objecttype="planet",description=Result,magnitude=15.1,searchgroup='solar',searchterm=Result)
    elif Result == "iss":
        obstarget = target(ISS,name=Result,objecttype="earth satellite",description="International Space Station",magnitude=-6.0,searchgroup='solar',searchterm=Result)
    elif Result == "css":
        obstarget = target(CSS,name=Result,objecttype="earth satellite",description="Chinese Space Station",magnitude=-6.0,searchgroup='solar',searchterm=Result)
    else:
        MainLog.Log("ChooseSolar: Could not initialize target (" + Result + ")",level="error")
        raise Exception ("ChooseSolar: Could not initialize target (" + Result + ")")
    MainLog.Log("ChooseSolar: End " + obstarget.Name,terminal=False)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def RadecObject(prechosen=None): # 4 references.
    """ Create a target from RA and DEC values. """
    if prechosen == None:
        print ("RadecObject: Create a target from RA and DEC values.")
        print ("Definition format: RA hh mm ss DEC ddd mm ss name")
    line = ''
    obstarget = None
    while True:
        if prechosen != None: # We're receiving a prechosen target description, don't ask user.
            line = prechosen
            prechosen = None # If there's a problem, then we'll ask the user instead.
        else:
            line = input("Definition (x to quit): ") # As user for target description.
        if len(line) < 1: continue # No input, ask again.
        if line.lower() == 'x': # Cancel
            return None
        lineitems = line.lower().split( )
        if lineitems[0] != "ra":
            print (textcolor.red("1st term must be 'ra'. Try again"))
            continue # Try again.
        if lineitems[4] != "dec":
            print (textcolor.red("5th term must be 'dec'. Try again"))
            continue # Try again.
        name = lineitems[8]
        rah = TextToInt(lineitems[1])
        if rah == None or rah < 0 or rah > 23:
            print (textcolor.red("2nd term must be integer RIGHT ASCENSION hours (0 to 23). Try again"))
            continue # Try again.
        ram = TextToInt(lineitems[2])
        if ram == None or ram < 0 or ram > 59:
            print (textcolor.red("3rd term must be integer RIGHT ASCENSION minutes (0 to 59). Try again"))
            continue # Try again.
        ras = TextToFloat(lineitems[3])
        if ras == None or ras < 0 or ras >= 60:
            print (textcolor.red("4th term must be decimal RIGHT ASCENSION seconds (0.000 to 59.999). Try again"))
            continue # Try again.
        ded = TextToInt(lineitems[5])
        if ded == None or ded < -90 or ded > 90:
            print (textcolor.red("6th term must be integer DECLINATION degrees (-90 to 90). Try again"))
            continue # Try again.
        dem = TextToInt(lineitems[6])
        if dem == None or dem <= -60 or dem >= 60:
            print (textcolor.red("7th term must be integer DECLINATION minutes (-59 to 59). Try again"))
            continue # Try again.
        des = TextToFloat(lineitems[7])
        if des == None or des <= -60 or des >= 60:
            print (textcolor.red("8th term must be decimal DECLINATION seconds (-59.999 to 59.999). Try again"))
            continue # Try again.
        break # Use these parameters to create the target object.
    if ded < 0 or dem < 0 or des < 0: # If any values are negative, all must be. That's how Skyfield wants the parameters.
        if ded > 0: ded = -1 * ded
        if dem > 0: dem = -1 * dem
        if des > 0: des = -1 * des
    MainLog.Log('RadecObject: Coordinates of', name, 'are RA', str(rah) + 'h', str(ram) + 'm', str(ras) + 's','DEC',str(ded) + DegreeSymbol, str(dem) + 'm', str(des) + 's',terminal=False)
    es = Star(ra_hours=(rah, ram, ras), dec_degrees=(ded, dem, des))
    obstarget = target(es,name=name,objecttype="radec location",description=name,magnitude=0.0,searchgroup='radec',searchterm=line)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def AltazObject(prechosen=None): # 4 references.
    """ Create a target from Altitude and Azimuth values. 
        These is a fixed point for the telescope, it will not move as the earth rotates.
        Useful for meteor watching, or timelapse capture of something moving. """
    if prechosen == None:
        print ("AltazObject: Create a target from Altitude and Azimuth values.")
        print ("Definition format: ALT ddd.dddd AZ ddd.dddd name")
    MainLog.Log('WARNING: AltAzObjects are not fully debugged yet.',level='warning')
    line = ''
    obstarget = None
    while True:
        if prechosen != None: # We're receiving a prechosen target description, don't ask user.
            line = prechosen
            prechosen = None # If there's a problem, then we'll ask the user instead.
        else:
            line = input("Definition ('x' to quit): ") # As user for target description.
        if len(line) < 1: continue # No input, ask again.
        if line.lower() == 'x': # Cancel
            return None
        lineitems = line.lower().split( )
        if lineitems[0] != "alt":
            print (textcolor.red("1st term must be 'alt'. Try again"))
            continue # Try again.
        if lineitems[2] != "az":
            print (textcolor.red("5th term must be 'az'. Try again"))
            continue # Try again.
        name = lineitems[4]
        alt = TextToFloat(lineitems[1])
        # Set default limits on positions available. Will be used if motor configurations are unavailable.
        minaz = 0
        maxaz = 360
        minalt = -90
        maxalt = 90
        for i in MotorControls: # Use the motor configurations to limit the positions available.
            if i.MotorName == 'azimuth':
                minaz = i.MinAngle
                maxaz = i.MaxAngle
            elif i.MotorName == 'altitude':
                minalt = i.MinAngle
                maxalt = i.MaxAngle
        if alt == None or alt < minalt or alt > maxalt:
            print (textcolor.red('2nd term must be float ALTITUDE degrees (',minalt,'to',maxalt,'). Try again'))
            continue # Try again.
        az = TextToFloat(lineitems[3])
        if az == None or az < minaz or az > maxaz:
            print (textcolor.red('4th term must be float AZIMUTH degrees (',minaz,'to',maxaz,'). Try again'))
            continue # Try again.
        break
    MainLog.Log('AltazObject: Coordinates of', name, 'are', AzAltText(az,alt),terminal=False)
    es = FixedPoint(name=name,alt=alt,az=az)
    obstarget = target(es,name=name,objecttype="altaz",description=name,magnitude=0.0,searchgroup='altaz',searchterm=line)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ReadHistoryFile(): # 2 references.
    """ Sort through the history file, remove duplicates and time sort.
        Update the history file and return the list of unique entries. """
    lines = [] # List of lines to choose from.
    uniquelines = [] # List of the unique characteristics of the lines (timestamp removed)
    with open(HistoryFile,'r') as f:
        rawlines = f.readlines() # Read all the contents into a list.
        rawlines.sort(reverse=True) # Sort the list in descending timestamp order, so we see most recent items first.
        for rawline in rawlines:
            if len(rawline.strip()) < 1: continue # Blank line, ignore it. (caused by external editor?)
            line = rawline[rawline.find("\t"):] # Ignore the timestamp at the start of the line.
            if not line in uniquelines: # Only print unique choices
                uniquelines.append(line) # Add to list of unique choices we've already found.
                lines.append(rawline.strip()) # Add to list of details that will be rewritten back to the sorted file.
    # Take the opportunity to compress the history file too. Removing duplicates.
    with open(HistoryFile,'w') as f:
        for i,line in enumerate(lines):
            if i >= 30: break # Only keep the last 30 history entries, otherwise the list becomes too large.
            f.write(line + "\n")
    return lines

# ------------------------------------------------------------------------------------------------------

def ChooseHistory(selection=None): # 1 references.
    """ User can retrieve earlier target selections and the exposure time.
        This allows resuming earlier observations more safely. """
    obstarget = None # No target selected yet.
    cols,rows = GetTerminalSize() # How wide is the display? Format the options list to fit. *Q* TO COMPLETE
    print (textcolor.yellow("Choose an object from an earlier observation."))
    print ("Listing from " + HistoryFile)
    if not os.path.exists(HistoryFile):
        print (textcolor.red("ChooseHistory: " + HistoryFile + " does not yet exist."))
        print (textcolor.red("You have not chosen any targets yet."))
        print (textcolor.red("Choose a target some other way first."))
        return obstarget
    # Construct a list of unique observation options from history.
    lines = ReadHistoryFile() # List of lines to choose from.
            
    # List the unique options. 'Lines' contains the unique observation details on offer.
    count = 0
    print ('')
    temptime = ts.now() # Use the same timestamp for everything in the list, otherwise repeated objects show inconsistent positions.
    print ('Index  Last used (UTC)     Name                 Category   Exposure  Current alt / az       RiseSet Other')
    #       123456 1234567890123456789 12345678901234567890 1234567890 12345678901234567890123456789012345678901234567890
    spacecount = 0 # Put a gap every 5 lines for readability.
    for line in lines:
        lineitems = line.split('\t')
        displine = '' # Empty line until we have constructed all the details.
        if len(lineitems) >= 4:
            displine = lineitems[0].ljust(19)[:19] + ' ' # Timestamp
            displine += textcolor.bold(lineitems[1].ljust(20)[:20]) + ' ' # Name
            displine += lineitems[2].ljust(10)[:10] + ' ' # Category
            displine += lineitems[4].rjust(5)[:5] + 's. ' # Exposure
            searchgroup = lineitems[2]
            searchterm = lineitems[3]
            miscline = '' # Miscellaneous info.
            if len(lineitems) > 6: # Timelapse is available.
                if float(lineitems[6]) != 0.0: # Timelapse is non-zero.
                    miscline += 'Timelapse ' + lineitems[6] + 's. '
            if searchgroup == 'solar':
                temptarget = ChooseSolar(searchterm) # Create a solar system target.
            elif searchgroup == 'hipparcos':
                temptarget = ChooseHipparcos(searchterm) # Create a hipparcos star target.
            elif searchgroup == 'messier':
                temptarget = ChooseMessier(searchterm,sizewarning=False) # Create a Messier object target. Don't warn about small targets at this point.
            elif searchgroup == 'radec':
                temptarget = RadecObject(searchterm) # Create an object from radec co-ordinates.
            elif searchgroup == 'altaz':
                temptarget = AltazObject(searchterm) # Create an object from alt/az co-ordinates.
            elif searchgroup == 'meteor':
                temptarget = ChooseMeteor(searchterm) # Create an object from meteor shower details.
            elif searchgroup == 'comet':
                temptarget = ChooseComet(searchterm) # Create an object from comet data.
            elif searchgroup == 'ngc':
                temptarget = ChooseNGC(searchterm) # Create an object from ngc data.
            else: temptarget = None
            if temptarget != None: # Work out where it is in the sky at the moment.
                az,alt = temptarget.AzAltDegrees(time=temptime) # Where is it?
                if az <= 180: direction = Symbol['up'] # Indicate if it's rising or setting. In northern hemisphere the azimuth is usually enough.
                else: direction = Symbol['down']
                visline = "   " + str(round(alt,3)).rjust(7) + " " + direction + " / " + str(round(az,3)).rjust(8)
                risesetline = temptarget.NextRiseSetHHMM().ljust(7)[:7] # When is next RISE/SET?
                #if temptarget.Magnitude != None: # Show apparent magnitude if known too.
                #    magline = "  " + str(temptarget.Magnitude).rjust(5)
                #else: # Apparent magnitude not known.
                #    magline = "---"
                if temptarget.Visible(time=temptime) == False: 
                    print(textcolor.red(str(count).rjust(6)[:6]),displine, textcolor.red(visline),risesetline,miscline)
                #    # Check if it will rise soon. (Default is in the next hour).
                #    # risetime = temptarget.WillBeVisible()
                #    risetime, settime = temptarget.RiseSet()
                #    #self.Log('target.WillBeVisible: RiseSet()=', risetime, settime, terminal=False)
                #    MainLog.Log('ChooseHistory: RiseSet()=', risetime, settime, terminal=False)
                #    if risetime != None:
                #        print(textcolor.yellow("                           Will rise " + str(risetime).split('.')[0] + " UTC"))
                #    else:
                #        print(textcolor.red("                           Will not rise."))
                elif temptarget.ApproachingLimit(time=temptime): 
                    print(textcolor.yellow(str(count).rjust(6)[:6]),displine,textcolor.yellow(visline),risesetline,miscline)
                else: 
                    print(textcolor.green(str(count).rjust(6)[:6]),displine,textcolor.green(visline),risesetline,miscline)
            else: print(textcolor.yellow(str(count).rjust(6)[:6]),displine) # No temptarget set.
        else: MainLog.Log("ChooseHistory: Could not process history line '" + str(line) + "', ignored.",terminal=True,level='error')
        spacecount = (spacecount + 1) % 5
        if spacecount == 0: print ('') # Blank line to make the table more readable if it is very large.
        count += 1
    MainLog.Log("ChooseHistory: Selected " + str(count) + " unique options from history.",terminal=False)
    # User must select one of the listed options.
    temp = '' # No choice made yet.
    while temp == '':
        temp = input(textcolor.cyan("Select history line (x to quit): "))
        if temp.lower() == "x": # Cancel selection.
            break
        i = TextToInt(temp) # Make sure it is a valid choice.
        if i != None and i >= 0 and i <= count:
            obitems = lines[i].split('\t') # Extract the tab delimited values from the chosen entry.
            searchgroup = obitems[2]
            searchterm = obitems[3]
            exposureseconds = float(obitems[4])
            exposuremode = int(obitems[5]) # *Q* This is not reapplied to the new observation yet!
            if len(obitems) > 6: # Timelapse is available too.
                timelapseseconds = float(obitems[6])
            else:
                timelapseseconds = 0.0
            MainLog.Log("ChooseHistory: Selected " + lines[i],terminal=False)
            CameraInUse.ExposureSeconds = exposureseconds
            CameraInUse.SetTimelapse(timelapseseconds)
            if searchgroup == 'solar':
                obstarget = ChooseSolar(searchterm) # Create a solar system target.
                break
            elif searchgroup == 'hipparcos':
                obstarget = ChooseHipparcos(searchterm) # Create a hipparcos star target.
                break
            elif searchgroup == 'messier':
                obstarget = ChooseMessier(searchterm) # Create a Messier object target.
                break
            elif searchgroup == 'radec':
                obstarget = RadecObject(searchterm) # Create an object from radec co-ordinates.
                break
            elif searchgroup == 'altaz':
                obstarget = AltazObject(searchterm) # Create an object from alt/az co-ordinates.
                break
            elif searchgroup == 'meteor':
                obstarget = ChooseMeteor(searchterm) # Create an object from meteor shower details.
                break
            elif searchgroup == 'comet':
                obstarget = ChooseComet(searchterm) # Create an object from comet details.
                break
            elif searchgroup == 'ngc':
                obstarget = ChooseNGC(searchterm) # Create an object from NGC details.
                break
            else:
                MainLog.Log("ChooseHistory: Unrecognised searchgroup: Line " + str(temp),level='error')
        # If we got this far, the choice was not valid. Reset and ask again.
        temp = '' # Reset and ask again. 
    return obstarget

print ("")
print ("Target selection")

# ------------------------------------------------------------------------------------------------------

def ChooseLastTarget(): # 2 references.
    """ Quick resume of previous observation target and settings. """
    obstarget = None # No target selected yet.
    if not os.path.exists(HistoryFile): # No file to process yet.
        print (textcolor.red("ChooseLastTarget: " + HistoryFile + " does not yet exist."))
        print (textcolor.red("You have not chosen any targets yet."))
        print (textcolor.red("Choose a target some other way first."))
        return obstarget
    # Construct a list of unique observation options from history.
    lines = ReadHistoryFile() # List of lines to choose from.

    line = lines[0]
    obitems = line.split('\t') # Extract the tab delimited values from the chosen entry.
    searchgroup = obitems[2]
    searchterm = obitems[3]
    exposureseconds = float(obitems[4])
    exposuremode = int(obitems[5]) # *Q* This is not set for the restarted observation yet!
    if len(obitems) > 6: # Timelapse is available too.
        timelapseseconds = float(obitems[6])
    else:
        timelapseseconds = 0.0
    MainLog.Log("ChooseLastTarget: Selected " + line,terminal=False)
    CameraInUse.ExposureSeconds = exposureseconds
    CameraInUse.SetTimelapse(timelapseseconds)
    if searchgroup == 'solar': obstarget = ChooseSolar(searchterm) # Create a solar system target.
    elif searchgroup == 'hipparcos': obstarget = ChooseHipparcos(searchterm) # Create a hipparcos star target.
    elif searchgroup == 'messier': obstarget = ChooseMessier(searchterm) # Create a Messier object target.
    elif searchgroup == 'radec': obstarget = RadecObject(searchterm) # Create an object from radec co-ordinates.
    elif searchgroup == 'altaz': obstarget = AltazObject(searchterm) # Create an object from alt/az co-ordinates.
    elif searchgroup == 'meteor': obstarget = ChooseMeteor(searchterm) # Create an object from meteor shower details.
    elif searchgroup == 'comet': obstarget = ChooseComet(searchterm) # Create an object from comet details.
    elif searchgroup == 'ngc': obstarget = ChooseNGC(searchterm) # Create an object from NGC details.
    else: MainLog.Log("ChooseLastTarget: Unrecognised searchgroup: Line " + str(temp),level='error')
    # Update target specific camera settings.
    return obstarget

# ------------------------------------------------------------------------------------------------------

def RiseSetString(otarget): # 2 references.
    """ Return a string listing RISE and SET times of target.
        otarget should be an instance of the target class.
        EARTH CENTRIC objects raise an error here. So they are ignored. """
    try:
        rise, set = otarget.RiseSet()
    #except Exception as e:
    except Exception:
        rise = set = None
        MainLog.Log("RiseSetString(): Failed. rise/set set to None.",terminal=False,level='warning')
    if rise != None:
        if rise < set: # Put resulting RISE and SET times in chronological sequence. 
            RS = ' Target Rise: ' + str(rise).split('.')[0] + ' UTC , Set: ' + str(set).split('.')[0] + " UTC"
        else:
            RS = ' Target Set: ' + str(set).split('.')[0] + ' UTC , Rise: ' + str(rise).split('.')[0] + " UTC"
    else:
        if otarget.Visible(): RS = ' Target is permanently above the horizon, it will not set.'
        else: RS = ' Target is permanently below the horizon, it will not rise.'
    return RS
    
# ------------------------------------------------------------------------------------------------------

def TargetSelection(): # 2 references.
    """ Submenu to allow target selection.
        Several different groups of target are available. 
        Select the group here, then pass control to a specific selection routine. """
    option = None
    TargetOptions = {
        'ResumeLastObservation':      {'label':'Resume last observation',     'bold':False, 'value':'LAST', 'docurl':None, 'helpdoc':'help.txt'},
        'RepeatEarlierObservations':  {'label':'Repeat earlier observations', 'bold':False, 'value':'HISTORY', 'docurl':None, 'helpdoc':'help.txt'},
        'SolarSystemObject':          {'label':'Solar system object',         'bold':False, 'value':'SOLAR', 'docurl':None, 'helpdoc':'help.txt'},
        'HipparcosObject':            {'label':'Hipparcos catalog',           'bold':False, 'value':'HIP', 'docurl':None, 'helpdoc':'help.txt'},
        'MessierObject':              {'label':'Messier catalog',             'bold':False, 'value':'MESSIER', 'docurl':None, 'helpdoc':'help.txt'},
        'RADEC':                      {'label':'RA-DEC co-ordinates',         'bold':False, 'value':'RADEC', 'docurl':None, 'helpdoc':'help.txt'},
        'Meteor':                     {'label':'Meteor shower',               'bold':False, 'value':'METEOR', 'docurl':None, 'helpdoc':'help.txt'},
        'Comet':                      {'label':'Comet',                       'bold':False, 'value':'COMET', 'docurl':None, 'helpdoc':'help.txt'},
        'ALTAZ':                      {'label':'Fixed ALT-AZ point',          'bold':False, 'value':'ALTAZ', 'docurl':None, 'helpdoc':'help.txt'},
        'NGC':                        {'label':'New General Catalog (NGC)',   'bold':False, 'value':'NGC', 'docurl':None, 'helpdoc':'help.txt'}
    }
    TargetMenu = optionmenu(TargetOptions,'Select target',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    while option == None:
        obstarget = None
        option = TargetMenu.Prompt()
        if option == "LAST": obstarget = ChooseLastTarget()
        elif option == "HISTORY": obstarget = ChooseHistory()
        elif option == "SOLAR": obstarget = ChooseSolar()
        elif option == "HIP": obstarget = ChooseHipparcos()
        elif option == "MESSIER": obstarget = ChooseMessier()
        elif option == "RADEC": obstarget = RadecObject()
        elif option == "METEOR": obstarget = ChooseMeteor()
        elif option == "COMET": obstarget = ChooseComet()
        elif option == "ALTAZ": obstarget = AltazObject()
        elif option == "NGC": obstarget = ChooseNGC()
        else: option = None
        if obstarget != None and obstarget.Visible() == False:
            if obstarget.Name in ['iss','css']: # RiseSet calc does not work for these yet.
                pass
            else:
                az,alt = obstarget.AzAltDegrees()
                linelist = [obstarget.Name + " is not currently in range (" + AzAltText(az,alt) + "). Select another target.",
                            RiseSetString(obstarget)]
                textcolor.TextBox(linelist,fg=textcolor.RED,bg=textcolor.BLACK)
                #print (textcolor.red(obstarget.Name + " is not currently in range (" + AzAltText(az,alt) + "). Select another target."))
                #print (textcolor.red(RiseSetString(obstarget)))
                option = None # Ask the user again.
        if obstarget == None: option = None # No target selected, so ask the user again.
        if option == None: print(textcolor.red("? Try again.")) # No success, so ask the user again.
    if obstarget != None: 
        obstarget.ClearNotes() # Remove any previous observation notes.

    return obstarget

# ------------------------------------------------------------------------------------------------------

# User MUST select a target to proceed.
Session.Target = None # No target yet.
if ResumeObservation: # Try to resume with last known target.
    Session.Target = ChooseLastTarget()
if Session.Target == None: # Still no valid target. Ask the user.
    Session.Target = TargetSelection()
CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
# Choose some other major objects to be included in the chart window.
SunTarget = ChooseSolar(prechosen='sun') 
MoonTarget = ChooseSolar(prechosen='moon')
ISSTarget = ChooseSolar(prechosen='iss')
CSSTarget = ChooseSolar(prechosen='css')
FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and ensures they exist on disc.

# ----------------------------------------------------------
# Menu options
# ----------------------------------------------------------

def HomePosition(): # 2 references.
    """ Return the whole mechanism to its home position.
        Microcontroller can mysteriously reset at any time, so this repeats until successful. """
    print (textcolor.yellow("HomePosition"))
    
    StopMotors() # Clear anything that's still programmed for the motors. 
    Session.SetMotorControlMode('direct') # We will directly control the movement of the microcontroller, no trajectory needs sending.
    MainLog.Log("HomePosition begin",terminal=False)
    loopcounter = 0
    looplimit = 50
    for i in MotorControls: # Handle each motor in turn.
        MainLog.Log("HomePosition: Homing ", i.MotorName, 'motor.',terminal=False)
        while i.CompareAngles(i.CurrentAngle,i.RestAngle) == False: # Repeat until the motor is in position.
            MainLog.Log("HomePosition:", i.MotorName, "motor from", str(round(i.CurrentAngle,3)) + DegreeSymbol, "to home", str(i.RestAngle) + DegreeSymbol,terminal=True)
            i.GoToAngle(i.RestAngle)
            MainLog.Log("HomePosition:", i.MotorName, "motor parked at", str(round(i.CurrentAngle,3)) + DegreeSymbol + ".",terminal=False)
            loopcounter += 1
            if loopcounter >= looplimit: 
                MainLog.Log("HomePosition:", i.MotorName, "After", looplimit, "attempts, motor still not homed. Abandoning the move at", str(round(i.CurrentAngle,3)) + DegreeSymbol, ".",level='error')
                break
    print (textcolor.yellow("Done.") + textcolor.clearlineforward())
    MainLog.Log("HomePosition end",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def SetMotorAngle(motor_name=None): # 2 references.
    """ Move motor to specific angle. """
    print (textcolor.yellow("SetMotorAngle " + str(motor_name)+ "."))
    print (textcolor.white("This will physically move the motor to a specific angle.",invert=False))
    print (textcolor.white("Logical position updated: TRUE            Physical position updated: TRUE"))
    c = ""
    for i in MotorControls: # Scan all the motors available.
        if i.MotorName == motor_name: # Select the correct motor.
            while c.lower() != "x": # Loop until user quits.
                print ("Enter target angle between " + str(i.MinAngle) + DegreeSymbol + " and " + str(i.MaxAngle) + DegreeSymbol)
                c = input(textcolor.cyan("Enter angle (or 'x' to exit) : ")) # Python3
                if len(c) < 1: # No valid input.
                    print ("Try again.")
                    continue # Restart loop.
                if c.lower() == "x":
                    print ("Done.")
                    break # Quit loop.
                v = TextToFloat(c)
                if v != None: # It is not a valid float.
                    if v < i.MinAngle or v > i.MaxAngle: # It is out of range for the motor.
                        print ("Out of range. Try again.")
                        continue # Restart loop.
                    # Value is acceptable, let's move the motor.
                    i.GoToAngle(v) # Set the new target position.
                    continue # Restart loop.
                print ("'" + c + "' is not recognised. Try again.")
    StopMotors() # Reset motor condition to prevent further movement.
    MainLog.Log("SetMotorAngle " + motor_name + " Completed.",terminal=False)
    print (textcolor.yellow("Done.") + textcolor.clearlineforward())
    return True

def AzimuthAngle(): # 1 references. # For menu
    SetMotorAngle('azimuth')

def AltitudeAngle(): # 1 references. # For menu
    SetMotorAngle('altitude')

# ------------------------------------------------------------------------------------------------------

def ExerciseMotor(motor_name=None): # 2 references.
    print (textcolor.yellow("ExerciseMotor " + str(motor_name)+ "."))
    a = ""
    sweep = 0
    lFound = False
    StopMotors() # Clear anything that's already programmed for the motors.
    
    Session.SetMotorControlMode('direct') # We will directly control the movement of the microcontroller. no trajectory needs sending.
    while a != "x":
        sweep += 1
        for i in MotorControls:
            if i.MotorName == motor_name:
                print (str(NowUTC()) + " Begin sweep " + str(sweep))
                print (str(NowUTC()) + " - Move to min angle (" + str(i.MinAngle) + DegreeSymbol + ")")
                i.GoToAngle(i.MinAngle)
                print (str(NowUTC()) + " - Home the motor.")
                i.GoToAngle(i.RestAngle)
                print (str(NowUTC()) + " - Move to max angle (" + str(i.MaxAngle) + DegreeSymbol + ")")
                i.GoToAngle(i.MaxAngle)
                print (str(NowUTC()) + " - Home the motor.")
                i.GoToAngle(i.RestAngle)
                lFound = True
        a = input("Press [ENTER] to repeat, 'x' to quit.") # Python3
        a = a.lower()
    print (str(NowUTC()) + " Completed.")
    StopMotors() # Reset motor condition to prevent further movement.
    if lFound != True: # We didn't find the motor!
        MainLog.Log("ExerciseMotor: Motor '" + str(motor_name) + "' was not recognised. Nothing moved.",level='error')
    MainLog.Log("ExerciseMotor " + motor_name + " completed.",terminal=False)
    print (textcolor.yellow("Done.") + textcolor.clearlineforward())
    return True

def ExerciseMotorAzimuth(): # 1 references. # For menu
    ExerciseMotor('azimuth')
    
def ExerciseMotorAltitude(): # 1 references. # For menu
    ExerciseMotor('altitude')

# ------------------------------------------------------------------------------------------------------

def TunePosition(motor_name=None): # 5 references. 
    """ Finetune the position of the mechanism. This version asks the user to enter the adjustment parameter.
        You can move a motor with this function, but its virtual position will not be updated.
        It physically moves the motor, but registers the position as it was at the START of the move.
        Use this to finetune the position if the telescope hasn't been placed properly, or the positioning is wrong.
        Scenarios are when you are initially setting up the telescope and finetuning the physical alignment to match the theoretical one.
        Or if the motor has slipped during an observation and you want to correct for that. 
        The optical drift tracking mechanism uses this function to keep the target centered too. """
    print (textcolor.yellow("TunePosition " + str(motor_name)+ "."))
    print (textcolor.white("This will move the motor to match where the computer thinks it is pointing.",invert=True))
    print (textcolor.white("This will finetune the physical position of the motor, but leave its logical position unchanged."))
    print (textcolor.white("You are making the motor physically point to where the computer already THINKS it is pointing."))
    print (textcolor.white("Logical position updated: FALSE            Physical position updated: TRUE"))
    #answer = AskYesNo("Home the motor before tuning? (y/N) ",default=False)
    #if answer:
    #    print ("Homing...")
    #    HomePosition() # First automatically home the motor. 
    lFound = False
    for i in MotorControls:
        if i.MotorName == motor_name:
            print ("Motor enabled.")
            fullrevsteps = i.AngleToStep(360.0)
            print ("- A full revolution is " + str(fullrevsteps) + " steps.")
            print ("- 1 degree is " + str(i.AngleToStep(1.0)) + " steps.")
            print ("- 100 steps is " + str(i.StepToAngle(100)) + DegreeSymbol + ".")
            circumference = math.pi * 300.0 # Dome is 300mm outside diameter. 
            print ("- Circumference of body circle is " + str(round(circumference,0)) + "mm.")
            print ("- 10mm of circumference movement is " + str(round(10 * fullrevsteps / circumference,0)) + "steps.")
            adj = None
            while adj != "x":
                adj = input(textcolor.cyan(motor_name.capitalize() + " steps to move (+/-), 'x' to exit : ")).strip().lower() # Python3
                if adj == "x":
                    break
                delta = TextToInt(adj)
                if delta == None:
                    print ("Not an integer. Try again or 'x' to exit")
                else:
                    print ("Moving", delta, "steps")
                    i.TunePosition(delta) 
            lFound = True
    if lFound:
        DriftTracker.Reset() # Reset optical tracking because we've moved the camera.
    else: # We didn't find the motor!
        MainLog.Log("TunePosition: Motor '", str(motor_name), "' was not recognised. Nothing moved.",level='error')
    print (textcolor.yellow("Done.") + textcolor.clearlineforward())
    return True

def TunePositionAzimuth(): # 2 references. # For menu call.
    TunePosition('azimuth')

def TunePositionAltitude(): # 2 references. # For menu call
    TunePosition('altitude')

# ------------------------------------------------------------------------------------------------------

def SetExposureTime(p): # 1 references.
    print (textcolor.yellow("SetExposureTime (Currently " + str(p)+ " seconds)."))
    print ("Some blurring may occur if exposures exceed " + str(round(CameraInUse.SecondsPerPixel,3)) + "seconds.")
    v = input(textcolor.cyan("New exposure time in seconds (or RETURN) : ")) # Python3
    if len(v) > 0:
        v = TextToFloat(v)
        if v != None:
            p = v
    if p > SensorInUse.MaxExposureSeconds:
        print ("Exposure cannot exceed " + str(SensorInUse.MaxExposureSeconds) + "seconds. Clipped.")
        p = SensorInUse.MaxExposureSeconds
    if p < SensorInUse.MinExposureSeconds:
        print ("Exposure cannot be below " + str(SensorInUse.MinExposureSeconds) + "seconds. Clipped.")
        p = SensorInUse.MinExposureSeconds
    MainLog.Log("SetExposureTime: Value=" + str(p) + " seconds.",terminal=False)
    return p

def MenuSetExposureTime(): # 1 references. # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        CameraInUse.ExposureSeconds = SetExposureTime(CameraInUse.ExposureSeconds)
        FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
        DocumentSession()
        DriftTracker.Reset()

# ------------------------------------------------------------------------------------------------------

def SetCameraTimelapse(p): # 1 references.
    print (textcolor.yellow("SetTimelapse (Currently " + str(p)+ " seconds)."))
    print ("This is the number of seconds BETWEEN each LIGHT image captured.")
    print ("0 means there is no delay.")
    v = input(textcolor.cyan("New timelapse delay in seconds (or RETURN) : ")) # Python3
    if len(v) > 0:
        v = TextToFloat(v)
        if v != None:
            p = v
    if p < 0:
        print ("Timelapse delay cannot be negative.")
        p = CameraInUse.TimelapseSeconds
    MainLog.Log("SetTimelapse: Value=" + str(p) + " seconds.",terminal=True)
    return p

# ------------------------------------------------------------------------------------------------------

def SetBatchSize(p): # 1 references.
    print (textcolor.yellow("SetBatchSize (Currently " + str(p)+ " frames)."))
    print ("This is the number of frames to capture when taking LIGHT images.")
    v = input(textcolor.cyan("Light images batch size (or RETURN) : ")) # Python3 
    if len(v) > 0:
        v = TextToInt(v)
        if v != None:
            p = v
    MainLog.Log("SetBatchSize: Value=" + str(p),terminal=False)
    return p

# ------------------------------------------------------------------------------------------------------

def SetControlBatchSize(p): # 1 references. 
    print (textcolor.yellow("SetControlBatchSize (Currently " + str(p)+ " frames)."))
    print ("This is the number of frames to capture when taking FLAT, DARK & BIAS images.")
    print ("HINT: A good number is around 15-20 images.")
    v = input(textcolor.cyan("Control batch size (or RETURN) : ")) # Python3 
    if len(v) > 0:
        v = TextToInt(v)
        if v != None:
            p = v
    MainLog.Log("SetControlBatchSize: Value=" + str(p),terminal=False)
    return p

# ------------------------------------------------------------------------------------------------------

# def ReadFitsFile(filename): # 0 references.
#     print (textcolor.yellow("Reading FITS file:", filename))
#     with fits.open(filename) as hdul:
#         hdul.verify('fix') # This can fix some common faults with the file before we start to process it.
#         InspectObject(hdul,"hdul")
#         print (textcolor.orange("FITS file info:"))
#         hdul.info()
#         InspectObject(hdul.info(),"hdul.info")
#         hdr = hdul[0].header
#         InspectObject(hdr,"hdr")
#         print (textcolor.orange("FITS file header:"))
#         print(repr(hdul))
#         for k,v in hdr.items():
#             print (textcolor.cyan(k),textcolor.yellow(v),textcolor.blue("(" + hdr.comments[k] + ")"))
#     print (textcolor.yellow("DONE"))
#     return True

# ------------------------------------------------------------------------------------------------------

def NewBlankImage(height=None,width=None,heightfactor=None,widthfactor=None,color=True,alpha=False): # 4 references.
    """ Return a new blank OpenCV image.
        Set to BLACK unless low & high arguments are given. 
        The image size can be scaled using heightfactor/widthfactor parameters relative to the sensor dimensions. 
        The image size can be scaled to specific pixel sizes using height/width parameters.
        If the color parameter = True a color image is created.
        If the color parameter = False a grayscale image is created.
        If alpha parameter = True an alpha channel is added. 
        If alpha parameter is False no alpha channel is added. 
        If low and high are provided, then the image is populated with random values between low (inclusive) and high (exclusive).
            Use this to generate initial random noise in the image."""
    HP = SensorInUse.PixelHeight
    WP = SensorInUse.PixelWidth
    if heightfactor != None: HP = int(HP * heightfactor) # Scale the height.
    if widthfactor != None: WP = int(WP * widthfactor) # Scale the width.
    if height != None: HP = height # Absolute values.
    if width != None: HP = width # Absolute values.
    MainLog.Log("NewBlankImage: Start", HP, "x", WP,terminal=False)
    layers = 1 # GREYSCALE image with no Alpha
    if color: layers += 2 # BGR
    if alpha: layers += 1 # Alpha chaneels
    if layers < 2: # Create a grayscale image.
        image = np.zeros((HP,WP), dtype=np.uint8) # Create a new black canvas to draw upon. This is a GREYSCALE image.
    else: # Create an image with multiple values per pixel (BGR and/or Alpha)
        image = np.zeros((HP,WP,layers), dtype=np.uint8) # Create a new black canvas to draw upon. This is a BGR image.
    
    MainLog.Log("NewBlankImage: End",terminal=False)
    return image

# ------------------------------------------------------------------------------------------------------

#def MarkupPreview(drift_pixels_x=None,drift_pixels_y=None,astrotime=None,applydistortion=False): # 2 references.
def MarkupPreview(drift_pixels_x=None,drift_pixels_y=None,astrotime=None): # 2 references.
    """ Take the last image registered in CameraInUse.CvImage and mark up various alignment indicators and labels.
        OpenCV version of MarkupPreview. 
        astrotime = You can specify the date/time that the preview is calculated for.
        applydistortion = The image can be artificially distorted to try to match an actual photo more closely. """
    CamLog.Log("MarkupPreview: Start",terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime != None: # Calculate for a specific timestamp.
        t = astrotime
    else: 
        t = ts.now() # Current timestamp in 'astro' time. If there's a delay then there may be some mismatch in placing objects.
    CamLog.Log("MarkupPreview: MarkupTime:",Ts2Datetime(t),terminal=False)
    #CamLog.Log("MarkupPreview: CameraInUse.AstrotimeStart:",Ts2Datetime(CameraInUse.AstrotimeStart),terminal=False)
    CamLog.Log("MarkupPreview: CameraInUse.CaptureStart:",CameraInUse.CaptureStart,terminal=False)
    CamLog.Log("MarkupPreview: CameraInUse.CaptureEnd:",CameraInUse.CaptureEnd,terminal=False)
    #CamLog.Log("MarkupPreview: CameraInUse.AstrotimeEnd:",Ts2Datetime(CameraInUse.AstrotimeEnd),terminal=False)
    # The time should be the time of the actual photo! If several seconds have passed, then things will already have drifted!
    CentreAlt, CentreAz = CurrentAltAz() # Get current camera position. Because this is where the photo is actually pointing!
    CentreRa, CentreDec = Session.Target.RaDecDegrees() # Calculations for target from observer's location. Returns decimal degree values.
    # load the image
    image = CameraInUse.CvImage.copy() # Take it directly from memory
    if len(image.shape) < 3:
        image = cv2.cvtColor(image,cv2.COLOR_GRAY2BGR) # Make sure it's a colour image. NOTE OPENCV actually stores colours as BGR! Blue and Red are swapped.
    font = cv2.FONT_HERSHEY_SIMPLEX
    # boldfont = cv2.FONT_HERSHEY_DUPLEX
    width = image.shape[1]
    height = image.shape[0]
    folder = FolderList.get('preview')
    # If we're including the live image, then it's a 'PREVIEW' file.
    # Otherwise it's an 'OVERLAY' file.
    filename = folder + "preview_" + UtcTimeStamp() + ".jpg"
    lineheight = 40 # Pixels high per line of text.
    ## Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - Parameters.TargetInclusionRadius
    MaxRADeg = CentreRa + Parameters.TargetInclusionRadius
    MinDecDeg = CentreDec - Parameters.TargetInclusionRadius
    MaxDecDeg = CentreDec + Parameters.TargetInclusionRadius
    
    if True: # Alt/Az spherical grid.
        CamLog.Log("MarkupPreview: ShowGrid",terminal=False)
        linestep = 1 # Grid lines every 1 degree
        for iAlt in range (-10,90,linestep):
            for iAz in range(0,360,linestep):
                PlotAlt, PlotAz = RelativeAltAz(iAlt,iAz,CentreAlt,CentreAz) # Plot point relative to centre of image.
                if abs(PlotAz) > Parameters.TargetInclusionRadius:
                    continue # Outside the image, skip it.
                if abs(PlotAlt) > Parameters.TargetInclusionRadius:
                    continue # Outside the image, skip it.
                PlotAlt2, PlotAz2 = RelativeAltAz(iAlt,iAz + linestep,CentreAlt,CentreAz) # Plot point relative to centre of image + 1 unit of Azimuth.
                PlotAlt3, PlotAz3 = RelativeAltAz(iAlt + linestep,iAz,CentreAlt,CentreAz) # Plot point relative to centre of image + 1 unit of Altitude.
                #TempStarX, TempStarY = PlotRelativeAltAz(PlotAlt,PlotAz,height,width,applydistortion=applydistortion)
                #TempStarX2, TempStarY2 = PlotRelativeAltAz(PlotAlt2,PlotAz2,height,width,applydistortion=applydistortion)
                #TempStarX3, TempStarY3 = PlotRelativeAltAz(PlotAlt3,PlotAz3,height,width,applydistortion=applydistortion)
                TempStarX, TempStarY = PlotRelativeAltAz(PlotAlt,PlotAz,height,width)
                TempStarX2, TempStarY2 = PlotRelativeAltAz(PlotAlt2,PlotAz2,height,width)
                TempStarX3, TempStarY3 = PlotRelativeAltAz(PlotAlt3,PlotAz3,height,width)
                h_thick = 1
                if iAlt == 0: # Horizon
                    h_thick = 5
                    h_color = (0,0,127)
                elif iAlt % 10 == 0: # 10 degree line
                    h_thick = 2
                    h_color = (90,90,90)
                elif iAlt % 5 == 0: # 5 degree line
                    h_thick = 2
                    h_color = (60,60,60)
                else:
                    h_thick = 1 # 1 degree line
                    h_color = (40,40,40)
                v_thick = 1
                if iAz % 10 == 0:
                    v_thick = 2
                    v_color = (90,90,90)
                elif iAz % 5 == 0:
                    v_thick = 2
                    v_color = (60,60,60)
                else:
                    v_thick = 1
                    v_color = (40,40,40)
                # Tint sectors which are below the horizon deep red.
                if iAlt < 0:
                    polygon = [(TempStarX, TempStarY), (TempStarX2, TempStarY2), (TempStarX2,TempStarY3), (TempStarX,TempStarY3)]
                    image = cv2.fillPoly(image, np.array([polygon]), (0,0,30))
                # Plot grid lines.
                image = cv2.line(image,(TempStarX,TempStarY),(TempStarX2,TempStarY2),h_color,thickness=h_thick) # DIMGREY Link to neighbouring grid intersections. # Horizontal part of grid (B-C)
                image = cv2.line(image,(TempStarX,TempStarY),(TempStarX3,TempStarY3),v_color,thickness=v_thick) # DIMGREY Link to neighbouring grid intersections. # Vertical part of grid (A-B)
                if iAlt % 5 == iAz % 5 == 0: # Show co-ordinates at crossing points.
                    text = str(iAlt) + "," + str(iAz)
                    image = cv2.putText(image,text,(TempStarX,TempStarY - 10),font,1.0,(127,127,127),thickness=1,lineType=cv2.LINE_AA)

    if True: # Parameters.MarkupShowCrosshairs: # Target cross hairs
        CamLog.Log("MarkupPreview: ShowCrosshairs",terminal=False)
        # Draw cross hairs. Gap in the centre so that target is still visible.
        image = cv2.line(image,(int(width/2),     0),            (int(width/2),        int(height/2 - 20)),BGROrange,thickness=1) # ORANGE
        image = cv2.line(image,(int(width/2),     height),       (int(width/2),        int(height/2 + 20)),BGROrange,thickness=1) # ORANGE
        image = cv2.line(image,(0,                int(height/2)),(int(width/2 - 20),   int(height/2)),     BGROrange,thickness=1) # ORANGE
        image = cv2.line(image,(int(width/2) + 20,int(height/2)),(width,int(height/2)),                    BGROrange,thickness=1) # ORANGE

    if True: # Parameters.MarkupShowDegreeScale: # Mark DEGREE scale. This is degrees movement of the camera, NOT degrees in the sky!
        CamLog.Log("MarkupPreview: ShowDegreeScale",terminal=False)
        # Calibration - Azimuth
        for i in range(-10,11):
            xpos = int(width/2) + (i * CameraInUse.PixelsPerFovDegreeWidth) # 1 degree markers
            ypos = int(height/2)
            text = str(i) + "deg" # DegreeSymbol
            image = cv2.line(image,(xpos,ypos - 100),(xpos,ypos),BGRYellow,thickness=1) # ORANGE
            image = cv2.putText(image,text,(xpos,ypos - 200),font,1.0,BGRYellow,thickness=1,lineType=cv2.LINE_AA) # orange
        # Calibration - Altitude
        for i in range(-10,11):
            xpos = int(width/2) 
            ypos = int(height/2) + (i * CameraInUse.PixelsPerFovDegreeHeight) # 1 degree markers
            image = cv2.line(image,(xpos - 100,ypos),(xpos,ypos),BGRYellow,thickness=1) # ORANGE
            text = str(i * -1) + "deg" # DegreeSymbol - Invert scale because image Y runs the wrong direction.
            image = cv2.putText(image,text,(xpos - 200,ypos),font,1.0,BGRYellow,thickness=1,lineType=cv2.LINE_AA) # orange

    if True: # Parameters.MarkupShowFullStepScale: # Mark FULL STEP scale.
        # CamLog.Log("MarkupPreview: ShowFullStepScale",terminal=False)
        # Calibration - Azimuth
        for i in range(-1000,1001,200): # Major tick marks only.
            xpos = int((width/2) + (i * az_pixels_per_fullstep))
            ypos = int(height/2)
            image = cv2.line(image,(xpos,ypos),(xpos,ypos + 100),BGRCyan,thickness=3) # Cyan
            text = str(i) + "S"
            image = cv2.putText(image,text,(xpos,ypos + 110),font,1.0,BGRCyan,thickness=1,lineType=cv2.LINE_AA) # Cyan
        # Calibration - Altitude
        for i in range(-1000,1001,200): # Major tick marks only
            xpos = int(width/2)
            ypos = int((height/2) + (i * alt_pixels_per_fullstep))
            image = cv2.line(image,(xpos,ypos),(xpos + 100,ypos),BGRCyan,thickness=3) # Cyan
            text = str(i * -1) + "S"
            image = cv2.putText(image,text,(xpos + 110,ypos),font,1.0,BGRCyan,thickness=1,lineType=cv2.LINE_AA) # Cyan
        # Mark precision circle on centre. Once you're inside this circle, there's little point in finetuning further on this scale.
        if az_pixels_per_fullstep > 5 or alt_pixels_per_fullstep > 5:
            # Only bother showing the precision circle IF it is large enough to be useful. 
            # If the gearing is very fine, then there's no real purpose to showing the precision circle, it will be too small to see.
            xpos = int(width/2)
            ypos = int(height/2)
            image = cv2.circle(image,(xpos,ypos),int(az_pixels_per_fullstep),BGRGold,thickness=3) # gold
            image = cv2.circle(image,(xpos,ypos),int(az_pixels_per_fullstep),BGRBlack,thickness=1) # black

    if True: # Draw arcs to show field rotation over differing timescales.
        CamLog.Log("MarkupPreview: FieldRotation.",terminal=False)
        xpos = int(width/2)
        ypos = int(height/2)
        count = 10
        gap = 90
        for i in [3600]: # List of exposure times.
            rotation = Session.Target.RotationArc(span=i)
            CamLog.Log("MarkupPreview: Calculated rotation",i,rotation,DegreeSymbol,terminal=False)
            r = count * gap
            image = cv2.ellipse(image,(xpos,ypos),(r,r),90,0,rotation * -1,BGRHotPink,thickness=3)
            image = cv2.putText(image,"Field rotation over " + HRSeconds(i) + " is " + str(round(rotation,2)) + "deg",(xpos,ypos + (count * gap)),font,1.0,BGRHotPink,thickness=1,lineType=cv2.LINE_AA) # Explain and demonstrate the field rotation that the telescope is currently experiencing.
            count += 1
            (tw, th), bh = cv2.getTextSize("Field rotation over ",font,1.0,thickness=1)
            CamLog.Log("MarkupPreview: getTextSize test", tw, th, bh,terminal=False)

    # TODO: Show scale of objects. 1Deg, 0.1Deg, 10min, 1min, 10sec, 1sec # Helps to judge what small objects are visible.
    #       Use CameraInUse.PixelsPerFovDegreeWidth, CameraInUse.PixelsPerFovDegreeHeight
    
    MarkedStars = {} # Make a list of stars and locations, use this for constellation mapping later...
    if True: # Parameters.MarkupShowStars: # Mark neighbouring stars.
        CamLog.Log("MarkupPreview: ShowStars",terminal=False)
        # Mark neighbouring stars on the picture too. This will help with alignment.
        # Select a subset of the Hipparcos catalog which is within 10Deg of the target (=centre of image)
        CamLog.Log("MarkupPreview: SelectStars start",terminal=False)
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        CamLog.Log("MarkupPreview: NeighbouringStars contains",len(NeighbouringStars),"entries.",terminal=False)
        # Now convert this list of ra/dec locations into alt/az positions for plotting on the preview image.
        for i in range(len(NeighbouringStars)):
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarMagnitude = TempStarRec['magnitude'] # Note the brightness of the star.
            TempStarHipparcosId = int(TempStarRec.name) # Note the Hipparcos catalog number of the star.
            TempStar = Star.from_dataframe(HipparcosDf.loc[TempStarHipparcosId]) # Convert the Hipparcos entry into a Skyfield STAR object.
            TempStarAstro = HomeSite.at(t).observe(TempStar) # Work out where the star is.
            TempStarApparent = TempStarAstro.apparent() # Calculate its position in the sky
            TempStarAlt, TempStarAz, TempStardistance = TempStarApparent.altaz() # Get the azimuth and altitude position of the star in the sky.
            TempStarRA, TempStarDec, TempStardistance = TempStarApparent.radec() # Get the azimuth and altitude position of the star in the sky.
            # CamLog.Log("MarkupPreview: NeighbouringStars:", TempStarHipparcosId,TempStarRA,TempStarDec,terminal=False)
            TempStarRALabel = str(TempStarRA)
            # Find the name (and Constellation) of the star if known.
            TempStarDict = StarName_dictionary.get(str(TempStarHipparcosId)) # Returns dictionary entry for Hipparcos ID.
            if TempStarDict != None:
                TempStarName = TempStarDict['name'] # Retrieve name of star.
                TempStarConstellation = TempStarDict['constellation'] # Constellation that it is in.
                TempStarDescription = TempStarName
                if TempStarConstellation != '':
                    TempStarDescription += " (" + TempStarConstellation + ")"
            else:
                TempStarName = None
                TempStarConstellation = None
                TempStarDescription = TempStarRec.name
            # Calculate the location in the preview image.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt.degrees,TempStarAz.degrees,CentreAlt,CentreAz)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempStarWidth = int(10 - TempStarMagnitude) * 3 # Calculate the radius of the star, brighter = bigger.
            MarkedStars[str(TempStarRec.name)] = [TempStarX, TempStarY, TempStarWidth] # Note locations of stars for constellation drawing later.
            image = cv2.circle(image,(TempStarX,TempStarY),TempStarWidth,BGRPaleGreen,thickness=3) # cyan # circle where the star is.
            if True: # Parameters.MarkupShowNames:
                if TempStarName != None:
                    image = cv2.putText(image,TempStarName + " (" + TempStarConstellation + ")",(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRWhite,thickness=1,lineType=cv2.LINE_AA) # white
                else: # Star name is Hipparcos ID instead.
                    image = cv2.putText(image,"HIP" + str(TempStarHipparcosId),(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRWhite,thickness=1,lineType=cv2.LINE_AA) # whitestr(TempStarHipparcosId)
                
            if Parameters.MarkupShowLabels:
                text = AzAltText(TempStarAz.degrees,TempStarAlt.degrees,'deg')
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + 20),font,1.0,BGRDimGreen,thickness=1,lineType=cv2.LINE_AA) # palegreen
                text = "RA:" + str(TempStarRALabel) + " Dec:" + str(TempStarDec)
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + 20 + lineheight),font,1.0,BGRDimGreen,thickness=1,lineType=cv2.LINE_AA) # palegreen

    # CamLog.Log("MarkedStars=" + str(MarkedStars),terminal=False)

    if True: #Parameters.MarkupConstellations: # Mark constellation patterns...
        # *Q* Check: Does Skyfield also provide Stellarium constellation dataset.
        CamLog.Log("MarkupPreview: ShowConstellations",terminal=False)
        rad = 10 # 10 pixel gap between line and star.
        for entryfrom, entryto, entryname in ConstellationLinks: # This could be more efficient.... just PoC at the moment.
            if entryfrom in MarkedStars and entryto in MarkedStars: # We can plot this link.
                fromdata = MarkedStars[entryfrom]
                todata = MarkedStars[entryto]
                fromx = fromdata[0]
                fromy = fromdata[1]
                tox = todata[0]
                toy = todata[1]
                deltax = tox - fromx
                deltay = toy - fromy
                # Only draw the line between stars if they are sufficiently separated on the image. (DIV-BY-ZERO error if they are the same pixel).
                if abs(deltax) > rad or abs(deltay) > rad:
                    hyp = math.sqrt(deltax**2 + deltay**2)
                    x1 = int(fromx + (deltax * rad / hyp)) # End points of line 'rad' pixels away from actual stars.
                    x2 = int(tox - (deltax * rad / hyp))
                    y1 = int(fromy + (deltay * rad / hyp))
                    y2 = int(toy - (deltay * rad / hyp))
                    image = cv2.line(image,(x1,y1),(x2,y2),BGRPaleGreen,thickness=1)

    if True: # Parameters.MarkupShowPlanets: # Mark neighbouring planets ....
        CamLog.Log("MarkupPreview: ShowPlanets",terminal=False)
        # Find the alt/az locations of all the planets.
        for TempStarName in ['sun','mercury barycenter','venus barycenter','moon','mars barycenter','jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']:
            TempStarMagnitude = 0.0
            if TempStarMagnitude > Parameters.TargetMinMagnitude: # Too dim to show.
                continue # Skip to next planet.
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = target(TempStar,name=TempStarName,objecttype="planet",description=TempStarDescription,magnitude=0.0)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t) 
            TempStarRA, TempStarDec = temptarget.RaDecDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempStarWidth = int(10 - TempStarMagnitude) * 4 # Calculate the radius of the planet, brighter = bigger.
            if TempStarName == 'moon':
                TempStarWidth = int(ConvertArcsecondsToPixels((0.5286 / 2) * 3600)) # Moon is approx 0.26 degrees angular radius.
            image = cv2.circle(image,(TempStarX,TempStarY),TempStarWidth,BGRGold,thickness=3) # cyan # circle where the planet is.
            #image = cv2.line(image,(TempStarX - (TempStarWidth * 2), TempStarY),(TempStarX + (TempStarWidth * 2), TempStarY),BGRGold,thickness=1) # gold
            #image = cv2.line(image,(TempStarX, TempStarY - (TempStarWidth * 2)),(TempStarX, TempStarY + (TempStarWidth * 2)),BGRGold,thickness=1) # gold
            if Parameters.MarkupShowLabels:
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + 40),font,1.0,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
                text = "RA:" + str(TempStarRA) + " Dec:" + str(TempStarDec)
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + 40 + lineheight),font,1.0,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
            if TempStarName != None:
                image = cv2.putText(image,TempStarName.split()[0],(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
        
    if True: # Parameters.MarkupShowMessier: # Mark neighbouring Messier objects ....
        CamLog.Log("MarkupPreview: ShowMessier",terminal=False)
        TempStarConstellation = ""
        TempStarDescription = ""
        TempStarMagnitude = 0.0
        # Find that alt/az locations of all the objects.
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            TempRAH = TempStarParms['ra'][0] # Right Ascension HOURS
            TempRAM = TempStarParms['ra'][1] # Right Ascension MINUTES
            TempRAS = TempStarParms['ra'][2] # Right Ascension SECONDS
            TempStarRA = HMSToAngle(TempRAH,TempRAM,TempRAS)
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempDED = TempStarParms['dec'][0] # Declination DEGREES
            TempDEM = TempStarParms['dec'][1] # Declination MINUTES
            TempDES = TempStarParms['dec'][2] # Declination SECONDS
            TempStarDec = round(DMSToAngle(TempDED,TempDEM,TempDES),3)
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            TempStar = Star(ra_hours=(TempRAH, TempRAM, TempRAS), dec_degrees=(TempDED, TempDEM, TempDES)) # Create star object from RADEC co-ordinates.
            TempStarType = TempStarParms['type']
            TempStarRALabel = str(TempRAH) + "h " + str(TempRAM) + "m " + str(TempRAS) + "s"
            TempStarWidth = int(((float(TempStarParms['width']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            TempStarHeight = int(((float(TempStarParms['height']) / 60) * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation=TempStarConstellation,description=TempStarDescription,magnitude=TempStarMagnitude)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/2),int(TempStarHeight/2)),0,0,360,BGRGreen,thickness=3) # cyan # circle where the star is.
            if Parameters.MarkupShowLabels:
                #image = cv2.line(image,(TempStarX - (TempStarWidth * 2), TempStarY),(TempStarX + (TempStarWidth * 2), TempStarY),BGRGreen,thickness=1) # green # Cross hairs through the circle.
                #image = cv2.line(image,(TempStarX, TempStarY - (TempStarHeight * 2)),(TempStarX, TempStarY + (TempStarHeight * 2)),BGRGreen,thickness=1) # green
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + lineheight),font,1.0,BGRGreen,thickness=1,lineType=cv2.LINE_AA) # green
                text = "RA:" + str(TempStarRALabel) + " Dec:" + str(TempStarDec)
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + (lineheight  * 2)),font,1.0,BGRGreen,thickness=1,lineType=cv2.LINE_AA) # green
            if True: # Parameters.MarkupShowNames:
                if TempStarName != None:
                    image = cv2.putText(image,TempStarName,(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRGreen,thickness=1,lineType=cv2.LINE_AA) # green

    if True: # Parameters.MarkupShowNGC: # Mark neighbouring NGC objects ....
        CamLog.Log("MarkupPreview: ShowNGC",terminal=False)
        TempStarConstellation = ""
        TempStarDescription = ""
        TempStarType = 'ngc'
        # Find that alt/az locations of all the objects.
        ObjectCount = 0
        for TempStarName,TempStarParms in NGCDict.items(): # Python3 
            # NGC list is large, eliminate unwanted items ASAP to protect performance.
            TempStarMagnitude = TempStarParms['magnitude']
            if TempStarMagnitude > Parameters.TargetMinMagnitude: # Too dim to show.
                continue # Skip to next object.
            TempRAH = TempStarParms['rah'] # Right Ascension HOURS
            TempRAM = TempStarParms['ram'] # Right Ascension MINUTES
            TempRAS = TempStarParms['ras'] # Right Ascension SECONDS
            TempStarRA = HMSToAngle(TempRAH,TempRAM,TempRAS)
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempDED = TempStarParms['ded'] # Declination DEGREES
            TempDEM = TempStarParms['dem'] # Declination MINUTES
            TempDES = TempStarParms['des'] # Declination SECONDS
            TempStarDec = DMSToAngle(TempDED,TempDEM,TempDES)
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            CamLog.Log("MarkupPreview: ShowNGC: Selected", TempStarName, terminal=False)
            ObjectCount += 1 # Increment count of objects selected.
            TempStar = Star(ra_hours=(TempRAH, TempRAM, TempRAS), dec_degrees=(TempDED, TempDEM, TempDES)) # Create star object from RADEC co-ordinates.
            TempStarRALabel = str(TempRAH) + "h " + str(TempRAM) + "m " + str(TempRAS) + "s"
            TempStarWidth = int(((float(TempStarParms['width']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            TempStarHeight = int(((float(TempStarParms['height']) / 60) * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation=TempStarConstellation,description=TempStarDescription,magnitude=TempStarMagnitude)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/2),int(TempStarHeight/2)),0,0,360,BGRLimeGreen,thickness=3) # cyan # circle where the star is.
            if Parameters.MarkupShowLabels:
                # image = cv2.line(image,(TempStarX - (TempStarWidth * 2), TempStarY),(TempStarX + (TempStarWidth * 2), TempStarY),BGRLimeGreen,thickness=1) # green # Cross hairs through the circle.
                # image = cv2.line(image,(TempStarX, TempStarY - (TempStarHeight * 2)),(TempStarX, TempStarY + (TempStarHeight * 2)),BGRLimeGreen,thickness=1) # green
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + lineheight),font,1.0,BGRLimeGreen,thickness=1,lineType=cv2.LINE_AA) # green
                text = "RA:" + TempStarRALabel + " Dec:" + str(round(TempStarDec,3))
                image = cv2.putText(image,text,(TempStarX + TempStarWidth + 5,TempStarY + (lineheight  * 2)),font,1.0,BGRLimeGreen,thickness=1,lineType=cv2.LINE_AA) # green
            if True: # Parameters.MarkupShowNames:
                if TempStarName != None:
                    image = cv2.putText(image,TempStarName,(TempStarX + TempStarWidth + 5,TempStarY -30),font,1.0,BGRLimeGreen,thickness=1,lineType=cv2.LINE_AA) # green
        CamLog.Log("MarkupPreview: ShowNGC: Selected", ObjectCount, "objects.",terminal=False)
        
    if True: # Parameters.MarkupShowRegistration: # Reference marks on preview image...
        CamLog.Log("MarkupPreview: ShowRegistration",terminal=False)
        image = cv2.line(image,(10,10),(100,10),BGRRed,thickness=3) # Red
        image = cv2.line(image,(10,10),(10,100),BGRRed,thickness=3) # Red
        text = "(10,10)"
        image = cv2.putText(image,text,(40, 60),font,1.0,BGRRed,thickness=1,lineType=cv2.LINE_AA) # red

    if True: # Parameters.MarkupShowDrift: # Mark last measured DRIFT indicator.
        CamLog.Log("MarkupPreview: ShowDrift",terminal=False)
        if drift_pixels_x != None and drift_pixels_y != None:
            image = cv2.line(image,(int(width/2),int(height/2)),(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y)),BGRBlack,thickness=3) # Black outline showing last measured drift.
            image = cv2.line(image,(int(width/2),int(height/2)),(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y)),BGRRed,thickness=1) # Red line showing last measured drift.
            image = cv2.circle(image,(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y)),10,BGRBlack,thickness=3) # Black outline showing last measured drift.
            image = cv2.circle(image,(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y)),10,BGRRed,thickness=1) # Red line showing last measured drift.
            text = "Drift " + str(int(drift_pixels_x)) + "," + str(int(drift_pixels_y)) + " pixels"
            image = cv2.putText(image,text,(int(width/2) + int(drift_pixels_x) + 10,int(height/2) + int(drift_pixels_y) + 10),font,1.0,BGRBlack,thickness=3,lineType=cv2.LINE_AA) # Black outline
            image = cv2.putText(image,text,(int(width/2) + int(drift_pixels_x) + 10,int(height/2) + int(drift_pixels_y) + 10),font,1.0,BGRRed,thickness=1,lineType=cv2.LINE_AA) # Red line
        else:
            image = cv2.putText(image,"NO DRIFT AVAILABLE",(int(width/2) + 10,int(height/2) + 10),font,1.0,BGRBlack,thickness=3,lineType=cv2.LINE_AA) # Black outline
            image = cv2.putText(image,"NO DRIFT AVAILABLE",(int(width/2) + 10,int(height/2) + 10),font,1.0,BGRRed,thickness=1,lineType=cv2.LINE_AA) # Red line

    if True: # Parameters.MarkupShowConditions: # Show current observation conditions.
        CamLog.Log("MarkupPreview: ShowConditions",terminal=False)
        seeingconditions = AstroSeeing.Translate(color=False)
        line = 0
        xpos = int(10)
        for i,condition in enumerate(seeingconditions):
            ypos = int(height - 120 - (lineheight * line / 2))
            image = cv2.putText(image,condition,(xpos,ypos),font,0.5,BGRCyan,thickness=1,lineType=cv2.LINE_AA) # cyan
            line += 1
        ypos = int(height - 120 - (lineheight * line / 2))
        image = cv2.putText(image,"Forecast observing conditions from " + AstroSeeing.SourceTitle,(xpos,ypos),font,0.5,BGRCyan,thickness=2,lineType=cv2.LINE_AA) # cyan
        image = cv2.putText(image,"Forecast observing conditions from " + AstroSeeing.SourceTitle,(xpos,ypos),font,0.5,BGRWhite,thickness=1,lineType=cv2.LINE_AA) # cyan
    
    if len(Session.Target.NotesLines) > 0:
        # Add observation notes to the display.
        CamLog.Log("MarkupPreview: Adding observation notes",terminal=False)
        line = len(Session.Target.NotesLines) + 1 # Count lines UP from bottom of image.
        xpos = int(width / 2 - 500) # 500 pixels to the left of centre.
        ypos = int(height - 50 - (lineheight * line / 2))
        image = cv2.putText(image,"Observation notes",(xpos,ypos),font,0.5,BGRYellow,thickness=2,lineType=cv2.LINE_AA) # white
        line -= 1 # Next line down.
        for text in Session.Target.NotesLines:
            ypos = int(height - 50 - (lineheight * line / 2))
            image = cv2.putText(image,str(text),(xpos,ypos),font,0.5,BGRYellow,thickness=1,lineType=cv2.LINE_AA) # white
            line -= 1 # Move down a line.
    else:
        CamLog.Log("MarkupPreview: No observation notes to add.",terminal=False)
        
    if True: # Parameters.MarkupShowCurrentPosition: # Show current position. 
        CamLog.Log("MarkupPreview: CurrentPosition",terminal=False)
        cRa ,cDec = Session.Target.RaDecHours() # Calculations for target from observer's location. Returns HMS and Degree values.
        line = 0 # Count lines UP from bottom of image.
        # Filename in bottom left corner.
        xpos = int(10)
        ypos = int(height - 50 - (lineheight * line))
        text = "File: " + filename
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGRWhite,thickness=1,lineType=cv2.LINE_AA) # white
        # Camera options in top left corner.
        xpos = int(200)
        ypos = int(40)
        text = "Camera options: " + str(CameraInUse.LastLightOptions)
        image = cv2.putText(image,text,(xpos,ypos),font,1,BGRYellow,thickness=1,lineType=cv2.LINE_AA) # white
        # More detail in bottom right corner. 
        line = 0 # Count lines UP from bottom of image.
        xpos = int(width - 500)
        ypos = int(height - 400)
        for i in MotorControls:
            text = i.MotorName + ": "
            text += str(round(i.CurrentAngle,3)) + "deg, " # DegreeSymbol 
            text += "motor position " + str(i.AngleToStep(i.CurrentAngle)) + " "
            ypos = int(height - 100 - (lineheight * line))
            image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
            line += 1 # Move up to next line.
        text = "Objects above magnitude " + str(round(Parameters.TargetMinMagnitude,1)) # Object magnitude filter.
        ypos = int(height - 100 - (lineheight * line))
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
        line += 1 # Move up to next line.
        if Session.Target.Magnitude != None: # Magnitude of the target.
            text = "Target magnitude " + str(round(Session.Target.Magnitude,1))
        else:
            text = "Target magnitude UNKNOWN"
        ypos = int(height - 100 - (lineheight * line))
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
        line += 1 # Move up to next line.
        # Astro location.
        if Session.Target.ObjectType != 'meteor': # *Q* This doesn't work for meteor shower observations, so don't show it until fixed. 
            text = "RA: " + str(cRa) + " Dec: " + str(cDec)
        ypos = int(height - 100 - (lineheight * line))
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGRGold,thickness=1,lineType=cv2.LINE_AA) # gold
        line += 1 # Move up to next line.
        # Lens characteristics
        text = "FOV: " + str(round(LensInUse.FovHorizontal,3)) + "deg * " + str(round(LensInUse.FovVertical,3)) + "deg" # DegreeSymbol
        ypos = int(height - 100 - (lineheight * line))
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGROrange,thickness=1,lineType=cv2.LINE_AA) # orange
        line += 1 # Move up to next line.
        # Exposure details
        ypos = int(height - 100 - (lineheight * line))
        image = cv2.putText(image,"Exposure: " + str(CameraInUse.ExposureSeconds) + " seconds.",(xpos,ypos),font,0.5,BGROrange,thickness=1,lineType=cv2.LINE_AA) # cyan
        line += 1 # Move up to next line.
        # Photo capture time.
        ypos = int(height - 100 - (lineheight * line))
        image = cv2.putText(image,"Captured: " + str(CameraInUse.LastImageDateTime),(xpos,ypos),font,0.5,BGRCyan,thickness=1,lineType=cv2.LINE_AA) # cyan
        line += 1 # Move up to next line.
        # Target
        ypos = int(height - 100 - (lineheight * line))
        text = "Target: " + Session.Target.Name
        image = cv2.putText(image,text,(xpos,ypos),font,1.0,BGRWhite,thickness=2,lineType=1) # white
        line += 1 # Move up to next line.
        ypos = int(height - 100 - (lineheight * line))
        text = "ImageCaptureEnd: " + str(CameraInUse.CaptureEnd)
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGROrange,thickness=1,lineType=1) # white
        line += 1 # Move up to next line.
        ypos = int(height - 100 - (lineheight * line))
        text = "ImageCaptureStart: " + str(CameraInUse.CaptureStart)
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGROrange,thickness=1,lineType=1) # white
        line += 1 # Move up to next line.
        ypos = int(height - 100 - (lineheight * line))
        text = "MarkupTime: " + str(Ts2Datetime(t))
        image = cv2.putText(image,text,(xpos,ypos),font,0.5,BGROrange,thickness=1,lineType=1) # white
        line += 1 # Move up to next line.

    if True: # Parameters.MarkupSaveDraft:
        CamLog.Log("MarkupPreview: SaveDraft",terminal=False)
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Show the preview filename that's being generated.
        cv2.imwrite(filename,image)
        CameraInUse.Previewjpg = filename # Record the filename so that the web interface can access it.

    CamLog.Log("MarkupPreview: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("MarkupPreview: End",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

#def GenerateOverlay(astrotime=None,applydistortion=False): # 1 references. 
def GenerateOverlay(astrotime=None): # 1 references. 
    """ Generate an overlay image that can be applied on top of other images to identify objects.
        This is for use in external image editors where you can combine layers. 
        This is generated before the observation starts, and populates the object caches used for targeting and preview images.
        astrotime = You can specify the date/time that the preview is calculated for. 
        applydistortion = The image can have lens distortion estimated to more closely match a real photograph.
        """
    CamLog.Log("GenerateOverlay: Start",terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime != None: # Calculate for a specific timestamp.
        t = astrotime
    else: 
        t = ts.now() # Current timestamp in 'astro' time. If there's a delay then there may be some mismatch in placing objects.
    # The time should be the time of the actual photo! If several seconds have passed, then things will already have drifted!
    alt_degree, az_degree = CurrentAltAz() # Get current camera position.
    # load the image
    image = NewBlankImage(color=True,alpha=True) # Just an empty black image as the background for OVERLAY pictures.
    font = cv2.FONT_HERSHEY_SIMPLEX
    #boldfont = cv2.FONT_HERSHEY_DUPLEX
    width = image.shape[1]
    height = image.shape[0]
    folder = FolderList.get('preview')
    filename = folder + "overlay_" + UtcTimeStamp() + ".png"
    #lineheight = 40 # Pixels high per line of text.
    # BGRA colours have 4 channels including the Alpha (transparency) channel.
    #BGRAOrange = (0,165,255,255)
    #BGRARed = (0,0,255,255)
    #BGRABlue = (255,0,0,255)
    #BGRAGreen = (0,255,0,255)
    #BGRACyan = (255,255,0,255)
    #BGRAGold = (0,215,255,255)
    #BGRAHotPink = (180,105,255,255)
    #BGRALimeGreen = (50,205,50,255)
    #BGRAWhite = (255,255,255,255)
    #BGRABlack = (0,0,0,255)
    #BGRADimGray = (105,105,105,255)
    #BGRAPaleGreen = (152,251,152,255)
    #BGRAYellow = (0,255,255,255)
    #BGRATransparent = (0,0,0,0)

    MarkedStars = {} # Make a list of stars and locations, use this for constellation mapping later...
    if True: # Mark neighbouring stars.
        CamLog.Log("GenerateOverlay: ShowStars",terminal=False)
        # Mark neighbouring stars on the picture too. This will help with alignment.
        CentreRa ,CentreDec = Session.Target.RaDecDegrees() # Calculations for target from observer's location. Returns decimal degree values.
        # # Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
        # MinRADeg = CentreRa - Parameters.TargetInclusionRadius # Minimum Right Ascension to select.
        # MaxRADeg = CentreRa + Parameters.TargetInclusionRadius # Maximum Right Ascension to select.
        # MinDecDeg = CentreDec - Parameters.TargetInclusionRadius # Minimum declination to select.
        # MaxDecDeg = CentreDec + Parameters.TargetInclusionRadius # Maximum declination to select.
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        ## Select a subset of the Hipparcos catalog which is within 10Deg of the target (=centre of image)
        #if isinstance(ObsTarget.HIPCacheDf,type(None)): # No cache yet. Create it.
        #    CamLog.Log("GenerateOverlay: Populating HIPCacheDf: SelectStars start",terminal=False)
        #    ObsTarget.HIPCacheDf = HipparcosDf.loc[(HipparcosDf['ra_degrees'] >= MinRADeg) & (HipparcosDf['ra_degrees'] <= MaxRADeg) & (HipparcosDf['dec_degrees'] >= MinDecDeg) & (HipparcosDf['dec_degrees'] <= MaxDecDeg) & (HipparcosDf['magnitude'] <= Parameters.TargetMinMagnitude)]
        #    CamLog.Log("GenerateOverlay: SelectStars end",terminal=False)
        #    CamLog.Log("GenerateOverlay: Radius=" + str(Parameters.TargetInclusionRadius) + " selected " + str(len(ObsTarget.HIPCacheDf)) + " stars.",terminal=False)
        #    CamLog.Log("GenerateOverlay: Populated HIPCacheDf with neighbouring stars.",terminal=False)
        #NeighbouringStars = ObsTarget.HIPCacheDf # Load from the cache.
        # Now convert this list of ra/dec locations into alt/az positions for plotting on the preview image.
        for i in range(len(NeighbouringStars)):
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarMagnitude = TempStarRec['magnitude'] # Note the brightness of the star.
            TempStarHipparcosId = int(TempStarRec.name) # Note the Hipparcos catalog number of the star.
            TempStar = Star.from_dataframe(HipparcosDf.loc[TempStarHipparcosId]) # Convert the Hipparcos entry into a Skyfield STAR object.
            TempStarAstro = HomeSite.at(t).observe(TempStar) # Work out where the star is.
            TempStarApparent = TempStarAstro.apparent() # Calculate its position in the sky
            TempStarAlt, TempStarAz, TempStardistance = TempStarApparent.altaz() # Get the azimuth and altitude position of the star in the sky.
            TempStarRA, TempStarDec, TempStardistance = TempStarApparent.radec() # Get the azimuth and altitude position of the star in the sky.
            # Find the name (and Constellation) of the star if known.
            TempStarDict = StarName_dictionary.get(str(TempStarHipparcosId)) # Returns dictionary entry for Hipparcos ID.
            if TempStarDict != None:
                TempStarName = TempStarDict['name'] # Retrieve name of star.
                TempStarConstellation = TempStarDict['constellation'] # Constellation that it is in.
                TempStarDescription = TempStarName
                if TempStarConstellation != '':
                    TempStarDescription += " (" + TempStarConstellation + ")"
            else:
                TempStarName = None
                TempStarConstellation = None
                TempStarDescription = TempStarRec.name
            # Calculate the location in the preview image.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt.degrees,TempStarAz.degrees,alt_degree,az_degree)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempStarWidth = int(10 - TempStarMagnitude) * 3 # Calculate the radius of the star, brighter = bigger.
            MarkedStars[str(TempStarRec.name)] = [TempStarX, TempStarY, TempStarWidth] # Note locations of stars for constellation drawing later.
            image = cv2.circle(image,(TempStarX,TempStarY),TempStarWidth,BGRAPaleGreen,thickness=3) # cyan # circle where the star is.
            if TempStarName != None:
                image = cv2.putText(image,TempStarName + " (" + TempStarConstellation + ")",(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRAWhite,thickness=1,lineType=cv2.LINE_AA) # white
            else: # Star name is Hipparcos ID instead.
                image = cv2.putText(image,str(TempStarHipparcosId),(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRAWhite,thickness=1,lineType=cv2.LINE_AA) # whitestr(TempStarHipparcosId)

    # CamLog.Log("MarkedStars=" + str(MarkedStars),terminal=False)

    if True: # Mark constellation patterns...
        # *Q* Check if the Stellarium constellation dataset is easier to use. See how it is used in Brandon Rhodes neowise comet example.
        CamLog.Log("GenerateOverlay: ShowConstellations",terminal=False)
        rad = 10 # 10 pixel gap between line and star.
        for entryfrom, entryto, entryname in ConstellationLinks: # This could be more efficient.... just PoC at the moment.
            if entryfrom in MarkedStars and entryto in MarkedStars: # We can plot this link.
                CamLog.Log("GenerateOverlay: Processing: " + str(entryfrom) + " " + str(entryto) + " " + str(entryname),terminal=False)
                fromdata = MarkedStars[entryfrom]
                todata = MarkedStars[entryto]
                fromx = fromdata[0]
                fromy = fromdata[1]
                tox = todata[0]
                toy = todata[1]
                deltax = tox - fromx
                deltay = toy - fromy
                # Only draw the line between stars if they are sufficiently separated on the image. (DIV-BY-ZERO error if they are the same pixel).
                if abs(deltax) > rad or abs(deltay) > rad:
                    hyp = math.sqrt(deltax**2 + deltay**2)
                    x1 = int(fromx + (deltax * rad / hyp)) # End points of line 'rad' pixels away from actual stars.
                    x2 = int(tox - (deltax * rad / hyp))
                    y1 = int(fromy + (deltay * rad / hyp))
                    y2 = int(toy - (deltay * rad / hyp))
                    CamLog.Log("GenerateOverlay: Drawing: " + str(x1) + "," + str(y1) + " " + str(x2) + "," + str(y2),terminal=False)
                    image = cv2.line(image,(x1,y1),(x2,y2),BGRAPaleGreen,thickness=1)
                else:
                    CamLog.Log("GenerateOverlay: Skipped stars at same location.",terminal=False)

    if True: # Mark neighbouring planets ....
        CamLog.Log("GenerateOverlay: ShowPlanets",terminal=False)
        TempStarMagnitude = 0.0
        # Find the alt/az locations of all the planets.
        for TempStarName in ['sun','mercury barycenter','venus barycenter','moon','mars barycenter','jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']:
            TempStarConstellation = ""
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = target(TempStar,name=TempStarName,objecttype="planet",description=TempStarDescription,magnitude=0.0)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t) 
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempStarWidth = int(10 - TempStarMagnitude) * 4 # Calculate the radius of the planet, brighter = bigger.
            image = cv2.circle(image,(TempStarX,TempStarY),TempStarWidth,BGRAGold,thickness=3) # cyan # circle where the planet is.
            image = cv2.line(image,(TempStarX - (TempStarWidth * 2), TempStarY),(TempStarX + (TempStarWidth * 2), TempStarY),BGRAGold,thickness=1) # gold
            image = cv2.line(image,(TempStarX, TempStarY - (TempStarWidth * 2)),(TempStarX, TempStarY + (TempStarWidth * 2)),BGRAGold,thickness=1) # gold
            if TempStarName != None:
                image = cv2.putText(image,TempStarName.split()[0],(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRAGold,thickness=1,lineType=cv2.LINE_AA) # gold
        
    if True: # Mark neighbouring Messier objects ....
        CamLog.Log("GenerateOverlay: ShowMessier",terminal=False)
        TempStarMagnitude = 0.0 # TempStarParms['magnitude']
        # Find that alt/az locations of all the objects.
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            TempRAH = TempStarParms['ra'][0] # Right Ascension HOURS 
            TempRAM = TempStarParms['ra'][1] # Right Ascension MINUTES 
            TempRAS = TempStarParms['ra'][2] # Right Ascension SECONDS 
            TempDED = TempStarParms['dec'][0] # Declination DEGREES 
            TempDEM = TempStarParms['dec'][1] # Declination MINUTES 
            TempDES = TempStarParms['dec'][2] # Declination SECONDS 
            TempStar = Star(ra_hours=(TempRAH, TempRAM, TempRAS), dec_degrees=(TempDED, TempDEM, TempDES)) # Create Radec object.
            TempStarConstellation = TempStarParms['constellation']
            TempStarDescription = TempStarParms['description']
            TempStarType = TempStarParms['type']
            TempStarWidth = int(((float(TempStarParms['width']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            TempStarHeight = int(((float(TempStarParms['height']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation=TempStarConstellation,description=TempStarDescription,magnitude=TempStarMagnitude)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t) # Current Alt/Az
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree) # Find relative alt/az to target.
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion) # Convert relative alt/az to image location.
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width) # Convert relative alt/az to image location.
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/2),int(TempStarHeight/2)),0,0,360,BGRAGreen,thickness=3) # circle where the object is.
            if TempStarName != None:
                image = cv2.putText(image,TempStarName,(TempStarX + TempStarWidth + 5,TempStarY -20),font,1.0,BGRAGreen,thickness=1,lineType=cv2.LINE_AA) # green

    if True:
        CamLog.Log("GenerateOverlay: SaveDraft",terminal=False)
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Show the preview filename that's being generated.
        cv2.imwrite(filename,image)

    CamLog.Log("GenerateOverlay: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("GenerateOverlay: End",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def BVtoBGR(BV): # 1 references.
    """ Convert a B-V color value from Hipparcos catalog to an approximate BGR color code.
        B-V     R G B (hex)
        -0.33   706ffe
        -0.3    519ffe
        -0.02   bfd0ff
        0.3     cdfdff
        0.58    eeffdf
        0.81    ffff7f
        1.40    fe7f7d
    """
    r = g = b = 255
    # List of sample B-V values and their approximate R,G,B equivalents. Found online.
    ColorPoints = [(-0.33,[0x70,0x6f,0xfe]),
                   (-0.3,[0x51,0x9f,0xfe]),
                   (-0.02,[0xbf,0xd0,0xff]),
                   (0.3,[0xcd,0xfd,0xff]),
                   (0.58,[0xee,0xff,0xdf]),
                   (0.81,[0xff,0xff,0x7f]),
                   (1.4,[0xfe,0x7f,0x7d])]

    def BVrange(BV):
        # Given a B-V value, pick the pair of ColorPoints that will be used to calculate the RGB equivalent.
        fromi = 0
        toi = 1 # If BV is too low, we use the lowest pair of entries. (We will extrapolate a value)
        try:
            for i,cp in enumerate(ColorPoints): # Consider each sample point in turn.
                if BV >= cp[0]: # Above lower threshold of this sample point.
                    fromi = i # Interpolation starts with this lower entry.
                    toi = i + 1 # Interpolation ends with the next entry.
            if toi >= len(ColorPoints): # If BV is too high, we are off the end of the list, so use the highest pair of entries.
                toi = len(ColorPoints) - 1
                fromi = toi - 1
        except Exception as e:
            MainLog.Log("BVRange:",str(BV),"failed:",str(e),level='error')
            fromi = 0
            toi = 1
        return fromi, toi

    def BVdX(fromi,toi):
        # Span of BV values from LOWER to UPPER sample limits.
        try:
            result = ColorPoints[toi][0] - ColorPoints[fromi][0]
        except Exception as e:
            MainLog.Log("BVdX:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVdR(fromi,toi):
        # Span of BLUE channel values from LOWER to UPPER sample limits.
        try:
            result = ColorPoints[toi][1][0] - ColorPoints[fromi][1][0]
        except Exception as e:
            MainLog.Log("BVdR:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVdG(fromi,toi):
        # Span of GREEN channel values from LOWER to UPPER sample limits.
        try:
            result = ColorPoints[toi][1][1] - ColorPoints[fromi][1][1]
        except Exception as e:
            MainLog.Log("BVdG:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVdB(fromi,toi):
        try:
            result = ColorPoints[toi][1][2] - ColorPoints[fromi][1][2]
        except Exception as e:
            MainLog.Log("BVdB:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVInterpolate(BV,fromi,toi):
        try:
            BVProportion = (BV - ColorPoints[fromi][0]) / BVdX(fromi,toi) # Position of our point between the two reference points. This is the scale applied to R,G,B channels.
            r = round((BVProportion * BVdR(fromi,toi)) + ColorPoints[fromi][1][0],0) # Scale RED channel relative to the BV position.
            r = max(0,r) # Colour channel values must be 0-255
            r = min(255,r)
            g = round((BVProportion * BVdG(fromi,toi)) + ColorPoints[fromi][1][1],0) # Scale GREEN channel relative to the BV position.
            g = max(0,g)
            g = min(255,g)
            b = round((BVProportion * BVdB(fromi,toi)) + ColorPoints[fromi][1][2],0) # Scale BLUE channel relative to the BV position.
            b = max(0,b)
            b = min(255,b)
        except Exception as e:
            MainLog.Log("BVInterpolate:",str(BV),str(fromi),str(toi),"failed:",str(e),level='error')
            r = b = g = 255
        return (int(b),int(g),int(r))

    try:
        fromi, toi = BVrange(BV) # Which pair of sample colour points do we interpolate from?
        b,g,r = BVInterpolate(BV,fromi,toi)
    except Exception as e:
        MainLog.Log("BVtoBGR:",str(BV),"failed:",str(e),level='warning')
        b = g = r = 255
    return (b,g,r)

# -----------------------------------------------------------------------------------------------------

def HipColor(hipid): # 1 references. 
    """ Return b,g,r values for the color of any star referenced by it's Hipparcos catalog number. """
    
    try:
        ColorRec = HipExDf.loc[hipid] # Get extension data record by key value.
        temp = ColorRec['B-V']
        if IsFloat(temp): # Some entries are BLANK in Hipparcos data set.
            ColorBV = float(temp) 
            b,g,r = BVtoBGR(ColorBV)
        else:
            b = g = r = 255
    except Exception as e:
        MainLog.Log("HipColor:",str(hipid),"failed:",str(e),level='warning')
        b = g = r = 255
    return (b,g,r)

# -----------------------------------------------------------------------------------------------------

def HSV2BGR(hue,sat,val): # 1 references.
    """ Convert 3 separate Hue,Saturation,Value values into Blue,Green,Red. """
    hsv = np.uint8([[[hue,sat,val]]]) # a 1x1 pixel image.
    bgr = cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    b = int(bgr[0][0][0])
    g = int(bgr[0][0][1])
    r = int(bgr[0][0][2])
    return b, g, r 

# ------------------------------------------------------------------------------------------------------

# def Magnitude2BGR(mag,dimmest,brightest=0): # 0 references.
#     """ Select a colour based upon a sliding scale of magnitudes.
#         Color represents where 'mag' is between dimmest and brightest values. 
#         mag = stellar magnitude.
#         dimmest = High value magnitude (dimmest star to represent).
#         brightest = Low value magnitude (brightest star to represent).
#         NOTE: If you are tempted to alter this, test it carefully first. Magnitudes run negatively!
#         """
#     lowval = brightest
#     highval = dimmest
#     span = highval - lowval # Magnitudes go negatively!
#     mag = max(mag,lowval) # Cannot exceed LOWEST value
#     mag = min(mag,highval) # Cannot exceed HIGHEST value
#     mag = float(mag) # Make sure we're not stuck in integer only calculation.
#     hue = int(130 * mag / span) # 0 = Mag 0.0 or brighter, 130 = Dimmest magnitude. # From RED to BLUE. Hue normally ranges from 0 to 180, but remember both ends are RED!
#     if mag < brightest:
#         b, g, r = int(255),int(255),int(255) # White if very bright.
#     else:
#         b, g, r = HSV2BGR(hue,255,255)
#     return [b, g, r]

# ------------------------------------------------------------------------------------------------------

def Magnitude2Radius(mag,dimmest,brightest=0,radius_max=10): # 1 references.
    """ Calculate star radius based upon a sliding scale of magnitudes.
        dimmest = High value magnitude (dimmest star to represent). (Radius 1)
        brightest = Low value magnitude (brightest star to represent). (Radius 10)
        NOTE: If you are tempted to alter this, test it carefully first. Magnitudes run negatively!
        """
    rmag = min(mag,dimmest) # Magnitudes are inverted!
    rmag = max(rmag,brightest) # Magnitudes are inverted!
    span = dimmest - brightest # Span of magnitudes to be handled.
    offset = rmag - brightest # Start point on magnitude scale.
    ratio = round((radius_max - 1) * (offset / span),0) # How far along the magnitude scale is this item?
    radius = int(radius_max - ratio) # Convert to a radius.
    return radius

# ------------------------------------------------------------------------------------------------------

def DimChannel(channel,ratio): # 3 references.
    """ simple multiplier for single color channel. """
    channel = channel * ratio
    channel = max(channel,0) # Cannot be < 0
    channel = min(channel,255) # Cannot be > 255
    return channel

# ------------------------------------------------------------------------------------------------------

def DimColor(color,ratio): # 4 references.
    """ Simple multiplier for BGR or BGRA color tuples. """
    if len(color) == 4: # Adjust BGR, but not A.
        return (DimChannel(color[0],ratio),DimChannel(color[1],ratio),DimChannel(color[2],ratio),color[3])
    elif len(color) == 3: # Adjust BGR
        return (DimChannel(color[0],ratio),DimChannel(color[1],ratio),DimChannel(color[2],ratio))
    else: return DimChannel(color,ratio) # Assume single channel.

# ------------------------------------------------------------------------------------------------------

#def CreateTargetImage(color=False,MinMagnitude=None,astrotime=None,applydistortion=False): # 3 references.
def CreateTargetImage(color=False,MinMagnitude=None,astrotime=None): # 3 references.
    """ Create a mockup target image based purely upon the expected view. 
        color parameter dictates whether the return is GRAYSCALE or COLOUR.
        Generate grayscale images for AstroAlign.
        By default it selects stars based upon Parameters.TargetMinMagnitude, however the calling routine can override this if required.
        color=True generates a colour image, star colours are estimated from the Hipparcos catalog data (B-V measure).
              This mode is used to simulate an observation photograph if there is no physical camera attached. 
        applydistortion = The image can have estimated lens distortion applied to more closely match a real photograph.
              
              *Q* TODO: Targets like COMETS etc are not simulated yet! Needs adding. 
              *Q* TODO: Targets like Galaxies and clusters are not nicely simulated yet. """
    #CamLog.Log("CreateTargetImage: Start. color",color,", MinMagnitude",MinMagnitude,", astrotime",astrotime,", applydistortion",applydistortion,terminal=False)
    CamLog.Log("CreateTargetImage: Start. color",color,", MinMagnitude",MinMagnitude,", astrotime",astrotime,terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime == None: t = ts.now() # Current timestamp in 'astro' time. As close as possible to the time of the photograph itself. Could develop this further!
    else: t = astrotime
    alt_degree, az_degree = CurrentAltAz() # Get current camera position. Not necessarily the same as the target location, there may be a very small difference.
    image = NewBlankImage() # Create a new black canvas to draw upon.
    width = SensorInUse.PixelWidth # Image dimension should match the live photos that will be compared against.
    height = SensorInUse.PixelHeight
    # font = cv2.FONT_HERSHEY_SIMPLEX # The font that will be used. 
    if MinMagnitude == None: # Calling procedure can override the minimum magnitude parameter.
        MinMagnitude = Parameters.TargetMinMagnitude
    CamLog.Log("CreateTargetImage: MinMagnitude:", MinMagnitude,terminal=False)
    starlist = [] # Create star list. This will be used by astroalign.find_transform() in tracking.

    # Mark neighbouring stars on the picture too. This will help with alignment.
    CentreRa ,CentreDec = Session.Target.RaDecDegrees() # Calculations for target from observer's location. Returns decimal degree values.
    CamLog.Log("CreateTargetImage: Centre RA/DEC=" + str(CentreRa) + "," + str(CentreDec),terminal=False)
    # Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - Parameters.TargetInclusionRadius
    MaxRADeg = CentreRa + Parameters.TargetInclusionRadius
    MinDecDeg = CentreDec - Parameters.TargetInclusionRadius
    MaxDecDeg = CentreDec + Parameters.TargetInclusionRadius

    if color: # Mark neighbouring Messier objects ....
        CamLog.Log("CreateTargetImage: ShowMessier",terminal=False)
        # Find that alt/az locations of all the objects.
        TempStarMagnitude = 0.0 # TempStarParms['magnitude']
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            TempStar = Star(ra_hours=(TempStarParms['ra'][0], TempStarParms['ra'][1], TempStarParms['ra'][2]), dec_degrees=(TempStarParms['dec'][0], TempStarParms['dec'][1], TempStarParms['dec'][2])) # Create star object from RADEC co-ordinates.
            TempStarConstellation = TempStarParms['constellation']
            TempStarDescription = TempStarParms['description']
            TempStarType = TempStarParms['type']
            if TempStarType in ['galaxy','cluster','milky way']: TempStarColor = BGRVeryDarkBlue
            else: TempStarColor = BGRHotPink
            TempStarWidth = int(((float(TempStarParms['width']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            TempStarHeight = int(((float(TempStarParms['height']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation=TempStarConstellation,description=TempStarDescription,magnitude=TempStarMagnitude)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/2),int(TempStarHeight/2)),0,0,360,DimColor(TempStarColor,0.5),thickness=-1)
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/3),int(TempStarHeight/3)),0,0,360,DimColor(TempStarColor,0.75),thickness=-1)
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/4),int(TempStarHeight/4)),0,0,360,TempStarColor,thickness=-1)
        CamLog.Log("CreateTargetImage: Plot Messier objects end.",terminal=False)

    #if color: # Mark neighbouring comets ....
    #    pass

    if color: # Mark neighbouring NGC items ...
        TempStarConstellation = ""
        TempStarDescription = ""
        TempStarType = 'ngc'
        # Find that alt/az locations of all the objects.
        ObjectCount = 0
        for TempStarName,TempStarParms in NGCDict.items(): # Python3 
            # NGC list is large, eliminate unwanted items ASAP to protect performance.
            TempStarMagnitude = TempStarParms['magnitude']
            if TempStarMagnitude > Parameters.TargetMinMagnitude: # Too dim to show.
                continue # Skip to next object.
            TempRAH = TempStarParms['rah'] # Right Ascension HOURS
            TempRAM = TempStarParms['ram'] # Right Ascension MINUTES
            TempRAS = TempStarParms['ras'] # Right Ascension SECONDS
            TempStarRA = HMSToAngle(TempRAH,TempRAM,TempRAS)
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempDED = TempStarParms['ded'] # Declination DEGREES
            TempDEM = TempStarParms['dem'] # Declination MINUTES
            TempDES = TempStarParms['des'] # Declination SECONDS
            TempStarDec = DMSToAngle(TempDED,TempDEM,TempDES)
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            ObjectCount += 1 # Increment count of objects selected.
            TempStar = Star(ra_hours=(TempRAH, TempRAM, TempRAS), dec_degrees=(TempDED, TempDEM, TempDES)) # Create star object from RADEC co-ordinates.
            TempStarWidth = int(((float(TempStarParms['width']) / 60) * CameraInUse.PixelsPerFovDegreeWidth) / 2)
            TempStarHeight = int(((float(TempStarParms['height']) / 60) * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation=TempStarConstellation,description=TempStarDescription,magnitude=TempStarMagnitude)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/2),int(TempStarHeight/2)),0,0,360,DimColor(BGRVeryDarkBlue,0.5),thickness=-1) # cyan # circle where the star is.
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/3),int(TempStarHeight/3)),0,0,360,DimColor(BGRVeryDarkBlue,0.75),thickness=-1) # cyan # circle where the star is.
            image = cv2.ellipse(image,(TempStarX,TempStarY),(int(TempStarWidth/4),int(TempStarHeight/4)),0,0,360,BGRVeryDarkBlue,thickness=-1) # cyan # circle where the star is.
    
    # Decide on a cutoff for the number of stars to plot.
    # Try to match the number of stars detected in the latest live image.
    StarLimit = max(DriftTracker.LatestStarCount + 10,30)
    TempStarRadius = int(Parameters.TrackingStarRadius) # All stars are the same size in this image.
    CamLog.Log("CreateTargetImage: LatestStarCount is:", DriftTracker.LatestStarCount, ". Setting StarLimit as:", StarLimit,terminal=False)
    
    if True: # Parameters.TargetShowStars: # Mark neighbouring stars.
        StarCount = 0 # How many stars have we plotted?
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        for i in range(len(NeighbouringStars)):
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarMagnitude = TempStarRec['magnitude'] # Note the brightness of the star.
            TempStarHipparcosId = int(TempStarRec.name) # Note the Hipparcos catalog number of the star.
            TempStar = Star.from_dataframe(HipparcosDf.loc[TempStarHipparcosId]) # Convert the Hipparcos entry into a Skyfield STAR object.
            TempStarAstro = HomeSite.at(t).observe(TempStar) # Work out where the star is.
            TempStarApparent = TempStarAstro.apparent() # Calculate its position in the sky
            TempStarAlt, TempStarAz, TempStarDistance = TempStarApparent.altaz() # Get the azimuth and altitude position of the star in the sky.
            if color == False and TempStarAlt.degrees < 0: # Below horizon 
                continue # Don't plot it.
            #if color or True: 
            if color: # Colour images need star colour and represent the magnitude via the size of the star.
                TempStarColor = HipColor(TempStarHipparcosId) # Retrieve approximation of hipparcos star color.
                TempStarRadius = Magnitude2Radius(mag=TempStarMagnitude,dimmest=MinMagnitude,radius_max=10)
            else: TempStarColor = BGRWhite # B&W tracking images are just simple white dots.
            TempStarRA, TempStarDec, TempStarDistance = TempStarApparent.radec() # Get the RA and Declination position of the star in the sky.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt.degrees,TempStarAz.degrees,alt_degree,az_degree) # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            if TempStarX < 0 or TempStarX > width or TempStarY < 0 or TempStarY > height:
                continue # The star is off the edge of the image, ignore it.
            image = cv2.circle(image,(TempStarX,TempStarY),TempStarRadius,TempStarColor,thickness=-1) # Filled circle where the star is.
            starlist.append([TempStarX,TempStarY,TempStarRadius,TempStarMagnitude])
            StarCount += 1 # Increment the count of stars plotted. 
            if StarCount >= StarLimit:
                CamLog.Log("CreateTargetImage: DriftTracker star limit " + str(StarLimit) + " reached.",terminal=False)
                break
        CamLog.Log("CreateTargetImage: Marked",StarCount,"of",StarLimit,"Stars.",terminal=False)
        if StarCount < StarLimit:
            CamLog.Log("CreateTargetImage: WARNING: NeighbouringStars cache may be too small, not enough stars available.",terminal=False)
    else:
        CamLog.Log("CreateTargetImage: No stars plotted.",terminal=False)

    if True: # Parameters.TargetShowPlanets: # Mark neighbouring planets ....
        # Find the alt/az locations of all the planets.
        CamLog.Log("CreateTargetImage: Plot planets start.",terminal=False)
        PlanetRadii = [40,4,6,40,6,10,10,4,4,4] # Radius to draw solar system objects. Must match list below.
        PlanetColors = [BGRYellow,BGRWhite,BGRWhite,BGRWhite,BGRRed,BGRYellow,BGRGold,BGRWhite,BGRBlue,BGRWhite] # Color to draw solar system objects. Must match list below.
        for i,TempStarName in enumerate(['sun','mercury barycenter','venus barycenter','moon','mars barycenter','jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']):
            TempStarMagnitude = 0.0
            if TempStarMagnitude > MinMagnitude: # Too dim to show.
                continue # Skip to next star.
            if color:
                TempStarColor = PlanetColors[i]
                TempStarRadius = PlanetRadii[i]
            else:
                TempStarColor = BGRWhite
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = target(TempStar,name=TempStarName,objecttype="planet",description=TempStarDescription,magnitude=0.0)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees()
            # Calculate the location of the star in the field of view!
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree) # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            #TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width,applydistortion=applydistortion)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            image = cv2.circle(image,(TempStarX,TempStarY),TempStarRadius,TempStarColor,thickness=-1) # circle where the star is.
        CamLog.Log("CreateTargetImage: Plot planets end.",terminal=False)

    if color: # Return a colour image.
        pass
    else: # Return Grayscale image.
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) # Convert BGR to grayscale.
    CamLog.Log("CreateTargetImage: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("CreateTargetImage: Complete.",terminal=False)
    return image,StarCount,starlist

# ------------------------------------------------------------------------------------------------------

# def CreateDarkFrame(): # 0 references.
#     """ Create fake Dark frame for development purposes. """
#     imagebuffer = np.random.randint(0,50,(SensorInUse.PixelHeight,SensorInUse.PixelWidth,3),np.uint8)
#     return imagebuffer # Return image.

# ------------------------------------------------------------------------------------------------------

CameraInUse.ImageGenerator = CreateTargetImage # Tell CameraInUse which function to use to generate fake images if needed. 

# ------------------------------------------------------------------------------------------------------

def AutoPreview(): # 1 references.
    """ Take immediate automatic photograph and mark it up with the expected objects in view. 
        This is normally used for calibration and testing. """
    MainLog.Log("AutoPreview",terminal=False)
    FileRoot = FolderList.get('preview') + 'preview_'
    CameraInUse.SetImageType('auto')
    CameraOptions = ''
    CameraOptions += '-t 10 ' # Timeout 50ms
    CameraOptions += '-n ' # Nopreview
    CameraOptions += '-md ' + str(CameraInUse.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
    CameraOptions += '-w ' + str(CameraInUse.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
    CameraOptions += '-h ' + str(CameraInUse.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
    CameraOptions += '-q 100 ' # Quality
    #result = CameraInUse.CaptureSet(file_root=FileRoot,batch_size=1,camera_options=CameraOptions,terminal=False,stacker=None)
    result = CameraInUse.CaptureSet(file_root=FileRoot,batch_size=1,camera_options=CameraOptions,terminal=False)
    MarkupPreview()
    return result

# ------------------------------------------------------------------------------------------------------

def ManualPreview(): # 2 references.
    """ Force immediate image capture from the camera.
        This is used to help check camera focus or alignment without 
        starting a full observation loop. """
    print (textcolor.yellow("ManualPreview"))
    # FileRoot = FolderList.get('preview') + 'preview_'
    print ("Capture PREVIEW images.")
    print ("Lens cap should be OFF.")
    print ("The camera will not track during preview functions.")
    print ("Camera will use automatic exposure settings in PREVIEW mode.")
    inp = ""
    result = False
    while inp != "x":
        inp = input("<RETURN> to begin ('x' to quit): ").lower() # Python3 
        if inp == "x":
            print ("quit")
            break
        result = AutoPreview()
    return result

# ------------------------------------------------------------------------------------------------------

def ImageCount_Session(): # 3 references.
    """ Count images in each folder for the current session. 
        It counts the occurrences of whichever filetype the program is currently generating. 
        - *.dng, or *.fits or *.jpg 
        So it avoids double-counting images if multiple image types are being generated. """
    result = ''
    if Parameters.CameraEnabled != True: selext = '.jpg' # No camera, so only count the simulated jpgs.
    elif CameraInUse.FastImageCapture: selext = '.jpg' # Fast image capture, only initial jpgs exist so far.
    elif CameraInUse.CameraSaveDng: selext = '.dng'
    else: selext = '.jpg'
    campaignkey = FolderList['campaign'] # Only interesed in files within the campaign structure.
    for key,value in FolderList.items(): # Python3: Check each folder.
        if value.startswith(campaignkey):
            count = 0
            try:
                for file in os.listdir(value): # List files in folder.
                    if file.endswith(selext): # Only count the right type of files.
                        count += 1
            except Exception as e:
                MainLog.Log("ImageCount: Failed with:",e,level='warning') # Allow graceful failure in case the folder nolonger exists.
            if count > 0: # Only report the folder if there's something in it.
                result += key[:5] + '=' + format(count,',') + ' ' # Abbreviate image type and number of images.
    if result == '': result = 'None'
    return result

# ------------------------------------------------------------------------------------------------------

def ImageCount_Campaign(): # 1 references.
    """ Count images in each folder for the current campaign.
        It counts the occurrences of whichever filetype the program is currently generating. 
        - *.dng, or *.fits or *.jpg 
        So it avoids double-counting images if multiple image types are being generated. """
    # *Q* This solution slows down a lot for large file collections. Could be faster (low-priority).
    result = ''
    if Parameters.CameraEnabled != True: selext = '.jpg' # No camera, so only count the simulated jpgs.
    elif CameraInUse.FastImageCapture: selext = '.jpg' # Fast image capture, only initial jpgs exist so far.
    elif CameraInUse.CameraSaveDng: selext = '.dng'
    else: selext = '.jpg'
    basedir = FolderList['campaign']
    MainLog.Log("ImageCount_Campaign: basedir",basedir,terminal=False)
    searchpath = basedir + "**/*" + selext
    MainLog.Log("ImageCount_Campaign: searchpath",searchpath,terminal=False)
    FileCountList = {}
    for file in glob.glob(searchpath, recursive=True): # Recursive search through all the folders of the current campaign.
        #MainLog.Log("ImageCount_Campaign: File",file,terminal=False)
        trimmedfile = file.replace(basedir,"") # Strip search path out.
        #MainLog.Log("ImageCount_Campaign: trimmedfile",trimmedfile,terminal=False)
        foldertype = trimmedfile.split("/")[1] # 1st remaining folder is the session, 2nd remaining folder is the image type.
        #MainLog.Log("ImageCount_Campaign: foldertype",foldertype,terminal=False)
        FileCountList[foldertype] = FileCountList.get(foldertype,0) + 1 # How many files of this type so far?
    # Convert the list of image types and counts into a summarised text string.
    for key,value in FileCountList.items():
        result += key[:5] + '=' + format(value,',') + ' ' # Abbreviate image type and number of images.
    if result == '': result = 'None'
    return result

# ------------------------------------------------------------------------------------------------------

def ImageCount(): # 2 references. # Could just be ImageCount_Session() directly now.
    """ Return count of images per type. """
    return ImageCount_Session() # Return values for the session, ignore other sessions in the same campaign.

# ------------------------------------------------------------------------------------------------------

def CheckImageSet(): # 5 references.
    """ Check that we have a full set of images. 
        Call this before allowing a change of target, session parameters or ending a session.
        If the user selects YES, then we allow the target/session to change.
        If the user selects NO, then we keep the session alive with the current target and settings. 
        If the folder has been deleted, then there are no images to worry about! """
    imagelist = ImageCount()
    result = True # We're happy that the image list is OK.
    if len(imagelist) > 0 and imagelist != 'None':
        print (" ")
        print ("Make sure you have captured the full set of images you need for this session.")
        print ("You will normally need a set of LIGHT, DARK, FLAT, DARK FLAT and BIAS images.")
        print ("Recommended minimum for stacking: LIGHT, DARK and BIAS sets.")
        print ("Images captured so far: " + textcolor.yellow(imagelist))
        result = AskYesNo("Is this session complete? (y/N) ",default=False)
        print (" ")
    return result

# ------------------------------------------------------------------------------------------------------

def CurrentMotorAltAz(): # 2 references.
    """ Return the current position of the altitude and azimuth motors.
        NOTE: The location will be the last reported position.
              The motors are controlled independently by a microcontroller,
              so the true position may be out-of-date if the motors are currently moving. """
    alt = 0.0
    az = 0.0
    for i in MotorControls:
        if i.MotorName == 'altitude':
            alt = i.CurrentAngle
        elif i.MotorName == 'azimuth':
            az = i.CurrentAngle
    return alt, az

# ------------------------------------------------------------------------------------------------------

def CameraHandler(outboundqueue,inboundqueue): # 1 references.
    """ This can run in a separate thread to take photos without distrubing tracking functions. 
        Long exposures (>4seconds) really need the camera to move DURING the exposure.
        outboundqueue and inboundqueue are the communication queues that can be used to control this thread. """
    # *Q* Are communication queues strictly needed? Can common variables/attributes actually do the trick?
    global FolderList # *Q* Does this need to be a global definition anymore? Check references. It's not modified here.
    RunThread = True # Set to False to terminate the handler. This will shutdown the thread entirely.
    batch_size = 1
    CamLog.Log('CameraHandler: Started')
    CameraWindow.Print(NowHMS() + ' CameraHandler started.')
    ReadyToObserve = False # When True the handler can start taking photographs. 
    CamLog.Log('CameraHandler.initial: ReadyToObserve = False',terminal=False)
    PrevReadyToObserve = None # Detect when the ReadyToObserve status changes.
    PhotoCount = 0 # Counter of completed photographs. 
    AzDriftSteps = 0
    AltDriftSteps = 0
    DriftX = None
    DriftY = None
    # Set observation specific parameters. These change based upon the target type etc.
    # - This sets CameraInUse.CameraTasks, the types of images to save, fast capture mode etc.
    CameraInUse.SetObservationParameters() # Set observation specific parameters. These change based upon the target type etc.
   
    CamLog.Log("camerahandler: Begin main loop.",terminal=False)
    while RunThread: # This will run through all queued commands in sequence, then start polling periodically for new ones.
        if threading.main_thread().is_alive() == False: # Check if parent thread is still alive. Quit if it is nolonger there.
            CamLog.Log('CameraHandler: Parent thread is nolonger alive. Terminating',level='error')
            RunThread = False
            time.sleep(5)
            break

        # Which task will we perform in this loop?
        LoopTask = CameraInUse.CameraTasks[0]
        if LoopTask == 'image': # Taking an actual photo.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=OSW_TEXT_GOOD) # Tell the image status window what the camera is currently doing.
        elif LoopTask == 'tracking': # Taking a tracking photo.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=textcolor.CYAN)
        #elif LoopTask == 'distortion': # Analysing lens distortion.
        #    ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=textcolor.MAGENTA)
        else: # Doing something else.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=OSW_TEXT_POOR) # Tell the image status window what the camera is currently doing.
        CameraInUse.CameraTasks = CameraInUse.CameraTasks[1:] # Shift the task list ready for the next loop. 
        CameraInUse.CameraTasks.append(LoopTask)
        CamLog.Log('CameraHandler: Loop task',LoopTask,terminal=False)
        
        # LoopStart = NowUTC()
        # This will run through all queued commands in sequence before capturing images if allowed.
        # This is performed regardless of which task is being performed in this loop.
        while inboundqueue.empty() == False: # There are some commands available from ObeservationRun to the camera.
            # Get the incoming message.
            ReceivedMessage = inboundqueue.get()
            CamLog.Log('CameraHandler received command: ' + str(ReceivedMessage),terminal=False)
            CameraTxWindow.Print(DictionaryToString(ReceivedMessage)) # Report communications from Main to Camera. 
            if 'Stop' in ReceivedMessage: # Main routine has told camera to shutdown. 
                RunThread = False
                ReplyMessage = {'TimeStamp' : NowUTC(), 'Stop' : 'acknowledged'} # Confirm back to main thread that STOP will be attempted.
                outboundqueue.put(ReplyMessage)
                CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.
            # if 'TimeStamp' in ReceivedMessage: # Main routine's timestamp. For tracing only really.
            #     TimeStamp = ReceivedMessage['TimeStamp']
            if 'BatchSize' in ReceivedMessage: # Main routine is updating the batch size.
                batch_size = ReceivedMessage['BatchSize']
            if 'ReadyToObserve' in ReceivedMessage: # Main routine is updating the ReadyToObserve status.
                ReadyToObserve = ReceivedMessage['ReadyToObserve']
                CamLog.Log('CameraHandler.inboundqueue: ReadyToObserve =',ReadyToObserve,terminal=False)
            if 'PhotoCount' in ReceivedMessage: # Main routine is updating the current photo count.
                PhotoCount = ReceivedMessage['PhotoCount']
                ReplyMessage = {'TimeStamp' : NowUTC(), 'PhotoCountReset' : True} # Acknowledge that the photo count has been reset.
                outboundqueue.put(ReplyMessage)
                CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.

        # If the Microcontroller stops working or talking, we cannot be sure that ReadyToObserve is still valid.
        # So after xx seconds of no microcontroller messages, reset ReadyToObserve.
        # *Q* This also triggers when the observation is finished. It has rarely raised a false alarm.
        if ReadyToObserve and Mctl.RxAge() > int(Mctl.CommsTimeout * 3 / 4):
            CamLog.Log('CameraHandler: (CamLog) No recent messages from microcontroller (', int(Mctl.CommsTimeout * 3 / 4), 's), assuming ReadyToObserve is nolonger valid.',level='warning',terminal=False)
            ReadyToObserve = False
            CamLog.Log('CameraHandler. Microcontroller comms timeout: ReadyToObserve = False',terminal=False)
            ErrorWindow.Print(NowHMS() + ' Microcontroller comms timeout.')

        if ReadyToObserve != PrevReadyToObserve: # Note the change in status of ReadyToObserve.
            CameraWindow.Print (NowHMS() + ' ReadyToObserve ' + str(ReadyToObserve))
            PrevReadyToObserve = ReadyToObserve
            CamLog.Log('CameraHandler. Change of state: ReadyToObserve from ',PrevReadyToObserve,'to',ReadyToObserve,terminal=False)

        if ReadyToObserve:
            # Calculate drift.
            # CamLog.Log('CameraHandler: Tracking age ' + str(DriftTracker.TrackingAge()),terminal=False)
            if LoopTask == 'tracking': # Time to consider a tracking check.
                if DriftTracker.TrackingAge() == None or DriftTracker.TrackingAge() > DriftTracker.TrackingInterval:
                    # First update the DriftTracker 
                    obs_start = NowUTC()
                    CamLog.Log('CameraHandler: Begin tracking image capture',terminal=False)
                    DriftWindow.Print(NowHMS() + ' Begin tracking image capture.')
                    if Parameters.DebugMode:
                        print(NowHMS() + ' Begin tracking image capture.')
                    try: 
                        result = CameraInUse.TakeTrackingPhoto(batch_size,terminal=False)
                    except:
                        CamLog.Log('CameraHandler: CameraInUse.TakeTrackingPhoto failed.',level='error')
                        result = False
                    CamLog.Log('CameraHandler: End tracking image capture',terminal=False)
                    CamLog.Log('CameraHandler: Storing latest tracking image.',terminal=False)
                    DriftTracker.SetLatestImage(CameraInUse.CvImage,obs_start) # OpenCV (numpy) array of the camera image it is saved in DriftTracker as Grayscale and reduced and enhanced.
                    CamLog.Log( 'CameraHandler: Consider storing target image...',terminal=False)
                    CamLog.Log( 'CameraHandler: Begin MockupTarget',terminal=False)
                    TempCvBuffer,TempStarCount,TempStarList = CreateTargetImage(color=False) # Create a completely calculated mock target image (grayscale). Used for image tracking.
                    CamLog.Log( 'CameraHandler: End MockupTarget',terminal=False)
                    CamLog.Log( 'CameraHandler: Stars',TempStarCount,':',TempStarList,terminal=False)
                    CamLog.Log( 'CameraHandler: Calling SetTargetImage after MockupTarget...',terminal=False)
                    DriftTracker.SetTargetImage(TempCvBuffer,starcount=TempStarCount,starlist=TempStarList,timestamp=obs_start) # CvImage is an OpenCV (numpy) array of the camera image in grayscale.
                    CamLog.Log( 'CameraHandler: Completed SetTargetImage after MockupTarget',terminal=False)
                    CamLog.Log( 'CameraHandler: Begin drift calculation',terminal=False)
                    DriftWindow.Print(NowHMS() + ' Updating drift calculation for tracking.')
                    AzDriftSteps = 0 # No drift unless we safely calculate one.
                    AltDriftSteps = 0
                    DriftX, DriftY, tempdelta = DriftTracker.PredictedTransform(NowUTC()) # Predict the drift by using the measured drift between 2 images and extrapolating forward to now.
                    CamLog.Log('CameraHandler: DriftTracker PredictedTransform driftx', str(DriftX), 'drifty', str(DriftY), terminal=False)
                    temp = min(len(DriftTracker.TargetStarList),len(DriftTracker.LatestStarList))
                    if DriftX != None and temp < 10: # At least 10 stars must have been matched.
                        CamLog.Log( 'CameraHandler: DriftTracker, low confidence.',temp,'star(s).',terminal=False)
                        DriftWindow.Print(NowHMS() + ' Low confidence. Matched ' + str(temp) + ' star(s).' )
                        DriftX = None
                        DriftY = None
                    CamLog.Log('CameraHandler: DriftTracker trusted driftx', str(DriftX), 'drifty', str(DriftY), terminal=False)
                    if DriftX != None:
                        AzDriftSteps = int(DriftX / az_pixels_per_fullstep)
                        AltDriftSteps = int(DriftY / alt_pixels_per_fullstep) * -1 # Invert result to convert from IMAGE Y direction to Motor Alt direction.
                        CamLog.Log('CameraHandler: Predicted drift: x=' + str(round(DriftX,2)) + '(' + str(AzDriftSteps) + 'steps), y=' + str(round(DriftY,2)) + '(' + str(AltDriftSteps) + 'steps)',terminal=False)
                    DriftWindow.Print(NowHMS() + ' Drift result: ' + str(DriftX) + ',' + str(DriftY) + ' px; ' + str(AzDriftSteps) + ',' + str(AltDriftSteps) + ' steps.')
                    # Assign latest drift values back to the motors.
                    for i in MotorControls: # Run through all the motors selecting those that need tuning.
                        if i.MotorName == 'azimuth': # Azimuth motor.
                            if AzDriftSteps != None and abs(AzDriftSteps) > 200: # Drift is large enough to do something.
                                DriftWindow.Print(NowHMS() + ' Tuning ' + i.MotorName)
                                CamLog.Log(NowHMS() + ' Tuning ' + i.MotorName,terminal=False)
                                i.TunePosition(AzDriftSteps)
                            else: # Drift is too small to worry about.
                                DriftWindow.Print(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.')
                                CamLog.Log(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.',terminal=False)
                        elif i.MotorName == 'altitude': # Altitude motor.
                            if AltDriftSteps != None and abs(AltDriftSteps) > 200: # Drift is large enough to do something.
                                DriftWindow.Print(NowHMS() + ' Tuning ' + i.MotorName)
                                CamLog.Log(NowHMS() + ' Tuning ' + i.MotorName,terminal=False)
                                i.TunePosition(AltDriftSteps)
                            else: # Drift is too small to worry about.
                                DriftWindow.Print(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.')
                                CamLog.Log(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.',terminal=False)
                    ReplyMessage = {'TimeStamp' : NowUTC(), 'DriftX' : DriftX, 'DriftY' : DriftY, 'AzDriftSteps' : AzDriftSteps, 'AltDriftSteps' : AltDriftSteps} 
                    outboundqueue.put(ReplyMessage)
                    CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.
                    CamLog.Log('CameraHandler: End drift calculation',terminal=False)
            if LoopTask == 'image': # Time to take an actual image. (If timelapse is active, only when it's due, otherwise every time.)
                if CameraInUse.TimelapseDue(): # Test timelapse mechanism.
                    CamLog.Log('CameraHandler: Image task. Timelapse is due',terminal=False)
                else:
                    CamLog.Log('CameraHandler: Image task. Timelapse is not due',terminal=False)
                # Now take the actual observation photo ('light' image).
                obs_start = NowUTC()
                # t = ts.now() # Record astro time when image starts, this is used later to locate labels if we mark up a control image, or generate a Target image.
                CamLog.Log('CameraHandler: Begin image capture',terminal=False)
                if Parameters.DebugMode:
                    print(NowHMS() + ' Begin image capture (' + str(PhotoCount + 1) + ') ' + str(CameraInUse.ExposureSeconds) + 's.')
                try:
                    result = CameraInUse.TakePhoto(batch_size,terminal=False)
                except Exception as e:
                    CamLog.Log('CameraHandler: CameraInUse.TakePhoto failed.',level='error')
                    CamLog.Log('CameraHandler: CameraInUse.TakePhoto raised:' + str(e),level='error')
                    CamLog.ReportException(e,comment='CameraHandler: Call to TakePhoto()')
                    result = False
                CamLog.Log( "CameraHandler: End image capture",terminal=False)
                obs_end = NowUTC()
                obs_time = obs_end - obs_start
                obs_mult = obs_time.total_seconds() / CameraInUse.ExposureSeconds
                CamLog.Log('CameraHandler: Total capture time', str(obs_time.total_seconds() * 1000) + 'ms. (mult=',obs_mult,')',terminal=False)
                if result:
                    PhotoCount += 1
                    CameraInUse.BatchCount += 1
                    ReplyMessage = {'TimeStamp' : NowUTC(), 'PhotoCount' : PhotoCount, 'ObsStart' : obs_start, 'ObsEnd' : obs_end, 'ObsTime' : obs_time, 'RunThread' : True}
                    outboundqueue.put(ReplyMessage) # Report communications from Camera to Main.
                    CameraRxWindow.Print(DictionaryToString(ReplyMessage))
                    CamLog.Log("Folder for image details:", FolderList['session'],terminal=False)
                    detailsfile = FolderList['session'] + 'imagedetails.txt'
                    tempra, tempdec = Session.Target.RaDecHours() # Current RA and DEC of target.
                    tempaz, tempalt = Session.Target.AzAltDegrees() # Current AZ and ALT of target.
                    if Parameters.ScanForMeteors and CameraInUse.ContainsMeteors(CameraInUse.CvImage): # Scan latest CvImage buffer for meteors or aircraft trails.
                        streaksdetected = True # Found streaks in image.
                        CameraWindow.Print(NowHMS() + " Trail in image (Meteor/plane/satellite).",fg=OSW_TEXT_POOR,bg=OSW_TEXT_BG) # Alert the operator that there's something spoiling the image.
                    else:
                        streaksdetected = False # Didn't even check.
                    # Record a data file for the captured image (could be exif data?).
                    if not os.path.exists(detailsfile): # Create header line if it's a new file.
                        with open(detailsfile,"w") as f:
                            f.write('Now' + '\t' + 'PhotoCount' + '\t' + 'Obs start' + '\t' + 'Obs end' + '\t')
                            f.write('Obs time' + '\t' + 'RA' + '\t' + 'Dec' + '\t')
                            f.write('Azimuth' + '\t' + 'Altitude' + '\t' + 'Streaks' + '\n')
                    with open(detailsfile,"a") as f:
                        f.write(str(NowUTC()) + '\t' + str(PhotoCount) + '\t' + str(obs_start) + '\t' + str(obs_end) + '\t')
                        f.write(str(obs_time) + '\t' + str(tempra) + '\t' + str(tempdec) + '\t')
                        f.write(str(tempaz) + '\t' + str(tempalt) + '\t' + str(streaksdetected) + '\n')
                else:
                    CamLog.Log("CameraHandler: Something went wrong with image capture. Aborting.",level='error')
                    RunThread = False # Something went wrong, quit!

            # Generate a labelled copy of the image periodically. For monitoring.
            if LoopTask == 'preview': # Time to consider making a preview markup.
                if PreviewTimer.Due() and type(CameraInUse.CvImage) != type(None): # Periodically prepare a new preview image. This is slow, so don't do it very frequently.
                    CamLog.Log('CameraHandler: Begin preview image markup',terminal=False)
                    if Parameters.DebugMode:
                        print (NowHMS() + ' Begin preview image generation.')
                    # astrocamera.CaptureSet will have loaded the image into OpenCV compatible buffer. This is available to mark up with more information.
                    MarkupPreview(drift_pixels_x=None,drift_pixels_y=None,astrotime=CameraInUse.AstrotimeEnd) # Use last image buffer from CameraInUse.CvImage to generate a marked up copy of the image on disc.
                    CamLog.Log('CameraHandler: End image markup',terminal=False)

            # Stop taking photos when the limit is reached. The main thread will also command the photos to stop, but it may be delayed.
            if PhotoCount >= Parameters.BatchSize:
                CamLog.Log('CameraHandler: Batch size reached.', PhotoCount, 'images captured.',terminal=False)
                CameraWindow.Print(NowHMS() + ' CameraHandler: Batch size reached. ' + str(PhotoCount) + ' images captured.')
                ReadyToObserve = False
                CamLog.Log('CameraHandler. BatchSize limit: ReadyToObserve = False',terminal=False)

        if RunThread and LoopTask == 'pause': time.sleep(0.25) # Small delay in each loop to relax things.

    ReplyMessage = {'TimeStamp' : NowUTC(), 'RunThread' : False}
    outboundqueue.put(ReplyMessage)
    CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.
    CameraWindow.Print(NowHMS() + ' CameraHandler stopped.')
    CamLog.Log('CameraHandler: Finished.')

# ------------------------------------------------------------------------------------------------------

# Run the CameraHandler as a separate thread.
# - This allows the camera to take lengthy exposures while the rest of the Observation routine continues.
CameraStatusQueue = Queue() # Use queue mechanism to send status information from capture thread to ObservationRun. 
CameraControlQueue = Queue() # Use queue mechanism to CONTROL the capture thread from the ObservationRun.
CameraThread = None # Pointer to camera thread.

# ------------------------------------------------------------------------------------------------------

def StartCameraThread(): # 10 references.
    global CameraThread # Must be global because it must persist after this function completes. 
    if CameraThread == None or CameraThread.is_alive() != True:
        CameraThread = threading.Thread(target=CameraHandler,args=(CameraStatusQueue,CameraControlQueue))
        CameraThread.start()
    return True

# ------------------------------------------------------------------------------------------------------

StartCameraThread() # Fire up the camera handler as a separate thread. 

# ------------------------------------------------------------------------------------------------------

def ShutdownCamera(): # 9 references.
    """ Close the camerahandler thread. """
    global CameraThread
    global CameraStatusQueue
    global CameraControlQueue
    success = True # Assume success unless we fail to shut down the handler correctly. 
    print ('\n' + textcolor.yellow('Stopping CameraHandler...')) # force newline before printing text.
    print ('Waiting for CameraHandler to confirm it has completed...')
    CameraControlQueue.put({'Stop' : True}) # Post a shutdown message to the CameraHandler
    # This waits for confirmation and warn to powercycle the RPi if the STOP command is unsuccessful after xxx seconds.
    CameraShutdownTimer = timer(max(200,CameraInUse.ExposureSeconds * 4)) # We'll give the CameraHandler some time to shut down.
    while True: # Loop until CameraShutdownTimer expires.
        if CameraThread.is_alive() == False: break # Camera thread is completely stopped so OK to proceed.
        if CameraStatusQueue.empty() == False: StatusMessage = CameraStatusQueue.get() # We have some feedback.
        else: StatusMessage = {} # Nothing from CameraHandler.
        if 'RunThread' in StatusMessage: # RunThread status message received.
            if StatusMessage['RunThread'] == False: # CameraHandler is shutting down.
                CameraThread.join() # Wait for it to complete.
                print (textcolor.yellow("CameraThread successfully stopped."))
                break # OK to proceed.
        if CameraShutdownTimer.Due(): # Timeout has expired, something's wrong.
            CamLog.Log("The CameraHandler did not stop in a reasonable time.",terminal=False,level='error')
            print (textcolor.fgbgcolor(textcolor.YELLOW,textcolor.RED,' Please POWER CYCLE the RPi to clear a potentially hung camera board.       '))
            print (textcolor.fgbgcolor(textcolor.YELLOW,textcolor.RED,' (Just restarting the program will probably not solve the problem.          '))
            print (textcolor.fgbgcolor(textcolor.YELLOW,textcolor.RED,'  Just rebooting the RPi will probably not solve the problem either.)       '))
            print (textcolor.fgbgcolor(textcolor.WHITE,textcolor.RED, ' You may need to CTRL-C now to break out of the stuck camerahandler thread. '))
            print (textcolor.fgbgcolor(textcolor.YELLOW,textcolor.RED,' The process stack has been recorded in the camera log file:                '))
            print (textcolor.fgbgcolor(textcolor.YELLOW,textcolor.BLACK,CamLog.FileName))
            # Record the process stack to the log file just in case there's something useful there.
            lines = osCmd('ps -ef')
            CamLog.Log('ps -ef\n',terminal=False)
            for line in lines:
                CamLog.Log(line.strip() + '\n',terminal=False)
                success = False # A terminal error occurred.
            break # OK to proceed.
        else: 
            temp = int(CameraShutdownTimer.Remaining()) # How many seconds left?
            if temp < 60: print ('Timeout in ' + textcolor.red(HRSeconds(temp)) + textcolor.cursorup())
            elif temp < 120: print ('Timeout in ' + textcolor.yellow(HRSeconds(temp)) + textcolor.cursorup())
            else: print ('Timeout in ' + textcolor.green(HRSeconds(temp)) + textcolor.cursorup())
        time.sleep(0.5) # Slight pause between loops.
    return success

# ------------------------------------------------------------------------------------------------------

def GoToTarget(target_object): # 3 references.
    """ Point camera at the target. But don't begin an observation. 
        Observations can only start once the microcontroller has a trajectory available to follow. """
    print (textcolor.yellow("GoToTarget: Pointing camera at target."))
    
    StopMotors() # Clear anything that's still programmed for the motors. 
    Session.SetMotorControlMode('direct') # We will directly control the movement of the microcontroller, no trajectory needs sending.

    # Prelocate the motors if case we need to handle gear backlash. It is good to go to a slightly lower azimuth position before starting the observation.
    if Parameters.BacklashEnabled: # We're handling gear backlash.
        currentalt, currentaz = CurrentMotorAltAz()
        az, alt = Session.Target.AzAltDegrees()
        MainLog.Log('GoToTarget: Backlash prealignment: From (' + AzAltText(currentaz,currentalt) + ") to (" + AzAltText(az,alt) + ")")
        # Prealignment for backlash effects. 
        for i in MotorControls: # Check every motor.
            if i.BacklashAngle != 0: # Does the motor have backlash set?
                targetangle = i.CurrentAngle
                if i.MotorName == "azimuth": # Compare target azimuth with current azimuth
                    if az < currentaz: # We need to move to a lower azimuth position, so move even further to allow the mechanism to take-up any backlash when the gears change position.
                        targetangle = az - i.BacklashAngle # Position the motor PAST the target so that the observation has to recover the situation, this will take up the slack in the gears.
                elif i.MotorName == "altitude": 
                    if alt < currentalt: # We need to move to a lower altitude position, so move even further to allow the mechanism to take-up any backlash when the gears change position.
                        targetangle = alt - i.BacklashAngle # Position the motor PAST the target so that the observation has to recover the situation, this will take up the slack in the gears.
                if i.CompareAngles(i.CurrentAngle,targetangle) == False:
                    MainLog.Log("GoToTarget: Pre alignment of " + i.MotorName + " motor to allow for gear backlash. Moving to " + str(round(targetangle,3)) + DegreeSymbol)
                    temp = i.GoToAngle(targetangle) # Move the motor PAST the target position, so that it will have to reverse to get on target. This will take up the slack in the gears.
                    if not temp: # Move failed.
                        MainLog.Log('GoToTarget: GoToAngle() call failed. Pre alignment of ' + i.MotorName + ' failed.',level='error')
                        return
            else: MainLog.Log('GoToTarget: No backlash adjustment required for ' + i.MotorName)
    # GoTo the target. 
    az, alt = Session.Target.AzAltDegrees()
    currentalt, currentaz = CurrentMotorAltAz()
    MainLog.Log('GoToTarget: Alignment: From ' + AzAltText(currentaz,currentalt) + " to " + AzAltText(az,alt))
    for i in MotorControls: # Check every motor.
        targetangle = i.CurrentAngle # Default is the current position.
        if i.MotorName == "azimuth": # Compare target azimuth with current azimuth
            targetangle = az # Position the motor ON the target.
        elif i.MotorName == "altitude": 
            targetangle = alt # Position the motor ON the target.
        if i.CompareAngles(i.CurrentAngle,targetangle) == False: # There's a big enough position difference that it's worth moving the camera.
            MainLog.Log("GoToTarget: Target", i.MotorName, str(round(targetangle,3)) + DegreeSymbol)
            temp = i.GoToAngle(targetangle) # Move the motor now.
            if not temp: # Move failed.
                MainLog.Log('GoToTarget: GoToAngle() call failed. Alignment of ' + i.MotorName + ' failed (From',i.CurrentAngle,'to',targetangle,'.',level='error')
                return
        else: MainLog.Log('GoToTarget: Motor ' + i.MotorName + ' already on target.')
    StopMotors() # Reset motor condition to prevent further movement.
    print ("NOTE: The camera is now positioned, but it is not tracking or photographing the object yet.")
    print ("      (Still calculating a trajectory before photography can start.)")
    print (textcolor.yellow("Done."))
  
# ------------------------------------------------------------------------------------------------------

# Session = sessionstatus() # Create new session status object.

# ------------------------------------------------------------------------------------------------------

def StopMotors(): # 9 references. 
    """ Send a fresh STOP command to the motorcontroller. 
        This is called automatically at the end of an observation, 
        it can also be sent manually from the Motor Controls menu. """
    Mctl.WriteFlush(send=False) # Scrap all outstanding messages to the microcontroller.
    Mctl.Write('stop') # Tell the motors to immediately stop.
    Mctl.Write('clear trajectory') # Remove any existing trajectory from the motors.
    Session.SetMotorControlMode('idle') # We nolonger need to maintain a trajectory.

# ------------------------------------------------------------------------------------------------------

def RestartMicrocontroller(): # 2 references. # For menu
    global MctlThread
    global Mctl
    if MctlThread.is_alive() != True: 
        MainLog.Log("ResetMctl: MctlThread is missing. Restarting...")
        Mctl = InitiateMctl() # Restart the microcontroller thread.
        MctlThread = threading.Thread(target=StartMctlComms,args=(),daemon=True) # Run microcontroller communication independently, quit automatically.
        MctlThread.start()
    Mctl.Reset(planned=True) # Restart the microcontroller manually. 

# ------------------------------------------------------------------------------------------------------

def ObservationSubmenu(drifttracker=None): # 1 references. 
    """ Submenu of options that can be used DURING an observation. """
    ClearScreen() # Clear the screen and force window refresh.
    
    if drifttracker == None: temp = None # There is no drifttracker object to call.
    else: temp = drifttracker.Reset # There is a drifttracker object to call.
    SubMenuOptions = {
        'ProgramStatus':          {'label':'Status',                  'bold':False, 'call':ProgramStatus, 'docurl':None, 'helpdoc':'help.txt'},
        'TuneAzimuth':            {'label':'Tune azimuth',            'bold':False, 'call':TunePositionAzimuth, 'docurl':None, 'helpdoc':'help.txt'},
        'TuneAltitude':           {'label':'Tune altitude',           'bold':False, 'call':TunePositionAltitude, 'docurl':None, 'helpdoc':'help.txt'},
        'ResetDriftTracking':     {'label':'Reset drift tracking',    'bold':False, 'call':temp, 'docurl':None, 'helpdoc':'help.txt'},
        'RestartMicrocontroller': {'label':'Restart microcontroller', 'bold':False, 'call':RestartMicrocontroller, 'docurl':None, 'helpdoc':'help.txt'},
        'OvernightForecast':      {'label':'Weather forecast',        'bold':False, 'call':AstroSeeing.TwelveHourForecast, 'docurl':None, 'helpdoc':'help.txt'}
    }
    SubMenu = proceduremenu(SubMenuOptions,'Pilomar observation submenu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    # Run sub menu.
    SubMenu.Prompt()

# ------------------------------------------------------------------------------------------------------

def UpdateMiscMeasures(): # 2 references.
    # Update miscellaneous display window with the lifetime running hours of each motor.
    # Update MOON phase.
    temp = round(MoonTarget.MoonFull()) # % of full moon.
    _, malt = MoonTarget.AzAltDegrees() # Moon altitude.
    if malt > 0: # Moon is visible.
        MiscWindow.FieldValue('MOONV',True,fg=OSW_TEXT_POOR)
        if temp > 25: MiscWindow.FieldValue('MOONP',temp,fg=OSW_TEXT_BAD) # Moon is too bright, will probably ruin images.
        else: MiscWindow.FieldValue('MOONP',temp,fg=OSW_TEXT_POOR) # Moon is dim but may impact images.
    else: # Moon is not visible.
        MiscWindow.FieldValue('MOONP',temp,fg=OSW_TEXT_GOOD)
        MiscWindow.FieldValue('MOONV',False,fg=OSW_TEXT_GOOD)
    waxing = MoonTarget.MoonWaxing() # True if moon waxing, false if it's waning.
    if waxing: MiscWindow.FieldValue('W',Symbol['up']) # Moon is waxing (getting brighter)
    else: MiscWindow.FieldValue('W',Symbol['down']) # Moon is waning (getting dimmer)
    MainLog.Log('Moon is', temp, "% full.",terminal=False) # % of full moon. Indicates light pollution from the moon.
    # Update Twilight phase.
    tw = TwilightLevel() # Get current twilight details.
    MainLog.Log('Twilight level is',tw,terminal=False) # Current lightlevel in Twilight terms.
    if tw in ['daytime','civil twilight']: MiscWindow.FieldValue('TWILIGHT',tw,fg=OSW_TEXT_BAD) # Too bright.
    elif tw in ['nautical twilight','astronomical twilight']: MiscWindow.FieldValue('TWILIGHT',tw,fg=OSW_TEXT_POOR) # Probably too bright. 
    else: MiscWindow.FieldValue('TWILIGHT',tw,fg=OSW_TEXT_GOOD) # Dark
    # Target magnitude.
    temp = Session.Target.CurrentMagnitude()
    if hasattr(temp,'item'): # If this is a numpy array, we want the first entry.
        temp = temp.item(0)
    temp = round(temp,1) # Only dp of magnitude is needed.
    if temp > 9: MiscWindow.FieldValue('MAGNITUDE',temp,fg=OSW_TEXT_BAD)
    elif temp < -20: MiscWindow.FieldValue('MAGNITUDE',temp,fg=OSW_TEXT_BAD)
    elif temp < -3: MiscWindow.FieldValue('MAGNITUDE',temp,fg=OSW_TEXT_POOR)
    else: MiscWindow.FieldValue('MAGNITUDE',temp,fg=OSW_TEXT_GOOD)
    # Field Rotation.
    fr_angle = Session.Target.RotationArc(span=CameraInUse.ExposureSeconds)
    fr_pixels = abs(round(Session.Target.RotationPixels(angle=fr_angle)))
    temp = str(round(fr_angle * 3600,2)) + 'arcs, ' + str(round(fr_angle,3)) + DegreeSymbol + ', ' + str(round(fr_pixels)) + 'px/frame'
    if fr_pixels > 10: MiscWindow.FieldValue('FIELDROTATION',temp,fg=OSW_TEXT_BAD) # Extreme rotation.
    elif fr_pixels > 3: MiscWindow.FieldValue('FIELDROTATION',temp,fg=OSW_TEXT_POOR) # Slight rotation.
    else: MiscWindow.FieldValue('FIELDROTATION',temp,fg=OSW_TEXT_GOOD) # Little rotation.
    tpps = round(CameraInUse.SecondsPerPixel,3)
    temp = str(tpps) + "s" # At what exposure length will pixels start to blur?
    if tpps < CameraInUse.ExposureSeconds: MiscWindow.FieldValue('BLUR',temp,fg=OSW_TEXT_BAD) # Blurring very likely.
    elif tpps < CameraInUse.ExposureSeconds * 2: MiscWindow.FieldValue('BLUR',temp,fg=OSW_TEXT_POOR) # Blurring possible.
    else: MiscWindow.FieldValue('BLUR',temp,fg=OSW_TEXT_GOOD) # Blurring unlikely.
    

# ------------------------------------------------------------------------------------------------------

def UpdateStorageStatus(): # 1 references.
    """ Checks storage available. 
        Updates displays.
        Returns TRUE if all OK.
        Returns FALSE if storage critically low. """
    # IF USB storage is being used, then check that capacity, otherwise check the SD card capacity.        
    result = True # All OK.
    fb = ImageStorageMonitor.FreeBytes() # How much storage space do we have? 
    sfb = HRBytes(fb) # Make it more readable.
    if fb > (1024 ** 3): ObservationStatusWindow.FieldValue('STORAGE',sfb,fg=OSW_TEXT_GOOD) # Lots of space available.
    elif fb > (400 * (1024 ** 2)): ObservationStatusWindow.FieldValue('STORAGE',sfb,fg=OSW_TEXT_POOR) # Space running low.
    elif fb > (150 * (1024 ** 2)): ObservationStatusWindow.FieldValue('STORAGE',sfb,fg=OSW_TEXT_BAD) # Space running low.
    else: # Dangerously low on space.
        ObservationStatusWindow.FieldValue('STORAGE',sfb,fg=OSW_TEXT_BAD) # Red
        result = False # Critically low on memory. Abort!
        MainLog.Log("UpdateStorageStatus: Low storage space (" + str(fb) + " bytes) terminating the observation.",level="error")
    memtot, memuse, memfree = MemoryMonitor.GetMemory() # Get system memory usage - memory is usually low because of Linux cache, so this may cause undue panic!
    mempercent = int(100 * (float(memfree) / float(memtot)))
    memrange = MemoryMonitor.GetFreeRange()
    if mempercent > 20: ObservationStatusWindow.FieldValue('MEMORY',str(mempercent) + "% " + memrange,fg=OSW_TEXT_GOOD)
    elif mempercent > 5: ObservationStatusWindow.FieldValue('MEMORY',str(mempercent) + "% " + memrange,fg=OSW_TEXT_POOR) # Yellow
    else:
        ObservationStatusWindow.FieldValue('MEMORY',str(mempercent) + "% " + memrange,fg=OSW_TEXT_BAD) # Red
        MainLog.Log("Free memory is very low (" + HRBytes(memfree) + "bytes)",level='warning')
    MainLog.Log("Storage available=" + HRBytes(fb) + "; Memory total=" + HRBytes(memtot) + "; Memory free=" + HRBytes(memfree),terminal=False)
    return result

# ------------------------------------------------------------------------------------------------------

def UpdateCpuLoad(): # 1 references.
    cpupercent = CpuMonitor.PercentBusy() # Get the most up-to-date CPU percent busy figures.
    cpurange = CpuMonitor.GetBusyRange()
    cputemp = CpuMonitor.CpuTemp
    cputext = str(int(cpupercent)) + "% " + cpurange + " (" + str(int(cputemp)) + DegreeSymbol + "C)"
    if cpupercent > 90 or cputemp > 75: ObservationStatusWindow.FieldValue('CPU',cputext,fg=OSW_TEXT_BAD) # Red
    elif cpupercent > 70 or cputemp > 60: ObservationStatusWindow.FieldValue('CPU',cputext,fg=OSW_TEXT_POOR) # Yellow
    else: ObservationStatusWindow.FieldValue('CPU',cputext,fg=OSW_TEXT_GOOD) # Green
    return True

# ------------------------------------------------------------------------------------------------------

def UpdateCameraStatus(): # 1 references.
    if Parameters.CameraEnabled: # Camera is enabled, report the selected exposure time.
        ObservationStatusWindow.FieldValue('CEN',Parameters.CameraEnabled,fg=OSW_TEXT_GOOD) # Green
        ObservationStatusWindow.FieldValue('EXP',str(CameraInUse.ExposureSeconds) + "s.",fg=OSW_TEXT_GOOD) # Exposure duration.
    else: # Camera is disabled, warn about this.
        ObservationStatusWindow.FieldValue('CEN',Parameters.CameraEnabled,fg=OSW_TEXT_POOR) # Red
        ObservationStatusWindow.FieldValue('EXP',str(CameraInUse.ExposureSeconds) + "s.",fg=OSW_TEXT_POOR) # Red - Blank out Exposure duration.
    if CameraInUse.TimelapseSeconds != 0:
        ObservationStatusWindow.FieldValue('TLAPSE',HRSeconds(CameraInUse.TimelapseTimer.Remaining()),fg=OSW_TEXT_GOOD) # Exposure duration.
    else:
        ObservationStatusWindow.FieldValue('TLAPSE','Off',fg=OSW_TEXT_GOOD) # Exposure duration.
    if CameraInUse.FastImageCapture: # Warn that shortcuts are being taken to get photos as quickly as possible. (Means delaying some processing until after the observation).
        ObservationStatusWindow.FieldValue('FAST',CameraInUse.FastImageCapture,fg=OSW_TEXT_POOR) # Fast Image Capture is active
    else:
        ObservationStatusWindow.FieldValue('FAST',CameraInUse.FastImageCapture,fg=OSW_TEXT_GOOD) # Fast Image Capture is not active
    if SensorInUse.OnChipCleanup: ObservationStatusWindow.FieldValue('OCC',SensorInUse.OnChipCleanup,fg=OSW_TEXT_POOR) # Red
    else: ObservationStatusWindow.FieldValue('OCC',SensorInUse.OnChipCleanup,fg=OSW_TEXT_GOOD) # Green
    return True

# ------------------------------------------------------------------------------------------------------

def UpdateCameraCaptureStatus(): # 1 references.      
    if CameraInUse.CaptureStart != None: # Monitor the progress of the current photograph.
        if CameraInUse.CaptureEnd == None or CameraInUse.CaptureEnd <= CameraInUse.CaptureStart:
            # Latest image capture has started but not finished yet.
            ImageStatusWindow.FieldValue("CAMERASTATE","Started",fg=OSW_TEXT_GOOD)
            ImageStatusWindow.FieldValue("STATETIMES",str(CameraInUse.CaptureStart).split(".")[0])
            ImageAge = (NowUTC() - CameraInUse.CaptureStart).total_seconds()
            ImageStatusWindow.FieldValue("STATEAGE","(" + HRSeconds(ImageAge) + ")")
        else: # Last image capture is complete. Waiting for next one to start.
            ImageStatusWindow.FieldValue("CAMERASTATE","Ended",fg=OSW_TEXT_GOOD)
            ImageStatusWindow.FieldValue("STATETIMES",str(CameraInUse.CaptureEnd).split(".")[0])
            ImageAge = (NowUTC() - CameraInUse.CaptureEnd).total_seconds()
            ImageStatusWindow.FieldValue("STATEAGE","(" + HRSeconds(ImageAge) + ")")
    else: # No capture even started yet.
        ImageStatusWindow.FieldValue("CAMERASTATE","Pending",fg=OSW_TEXT_POOR)
        ImageStatusWindow.FieldValue("STATETIMES","")
        ImageStatusWindow.FieldValue("STATEAGE","")
    return True

# ------------------------------------------------------------------------------------------------------

def UpdateWindGustCheck(az): # 1 references.     
    # Is there a risk that the wind is blowing into the telescope?
    try:
        winddir = int(AstroSeeing.GetMeasure('winddirection').replace('deg',''))
        windspeed = int(AstroSeeing.GetMeasure('windspeed').replace('mph',''))
        gustspeed = int(AstroSeeing.GetMeasure('windgustspeed').replace('mph',''))
        if winddir > az: winddelta = winddir - az
        else: winddelta = az - winddir
        if winddelta > 180: winddelta = 360 - winddelta # We need the acute angle between the two positions.
        winddelta = round(winddelta)
        windtemp = '(no wind risk)' # The risk of wind/gusts getting into the dome and causing vibration.
        if windspeed >= 20 or gustspeed >= 20:
            if winddelta <= 45: # Wind is straight into the front of the dome.
                windtemp = '(high wind risk)'
                WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_BAD)
            elif winddelta <= 100: # Wind is sideways on to the dome entrance.
                windtemp = '(wind risk)'
                WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_POOR)
            else: # Dome entrance is downwind.
                windtemp = '(low wind risk)'
                WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_GOOD)
            if gustspeed > 30: # Strong wind gusts.
                windtemp = '(high gust risk)'
                WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_BAD)
        else:
            WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_GOOD)
        WeatherWindow.FieldValue('NOTES','Target is ' + str(round(az)) + DegreeSymbol + ', wind from ' + str(winddir) + DegreeSymbol + ', ' + Symbol['delta'] + ' ' + str(winddelta) + DegreeSymbol + ' ' + windtemp)
        if windtemp in ['(no wind risk)','(low wind risk)']: # So consider FOG risk instead.
            tempdict = AstroSeeing.GetFogData() # Pull weather metrics and establish a risk of fog.
            if tempdict['fogrisk'] in ['3/3']: # Some risk of fog.
                WeatherWindow.FieldValue('NOTES','Fog risk: dewpoint' + Symbol['delta'] + ':' + tempdict['dewpointstatus'] + ' wind:' + tempdict['windspeedstatus'] + ' humidity:' + tempdict['humiditystatus'] + '%')
                if tempdict['fogrisk'] in ['3/3']: WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_BAD)
                elif tempdict['fogrisk'] in ['1/3','2/3']: WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_POOR)
                else: WeatherWindow.FieldColor('NOTES',fg=OSW_TEXT_GOOD)
    except Exception as e:
        MainLog.Log("UpdateWindGustCheck: AstroSeeing wind direction calculations failed with:",str(e),level='warning',terminal=False)
        MainLog.Log("UpdateWindGustCheck: AstroSeeing failed. Is the web service running correctly?",level='warning',terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------
        
def GeneratePreviewAvi(): # 1 references.    
    MainLog.Log("Generating animation of observation...",terminal=False)
    print (textcolor.yellow("Generating animation of observation previews (if available)..."))
    sourcefilepattern = FolderList.get('preview') + 'preview_*.jpg'
    avifilename = FolderList.get('preview') + 'preview_' + CleanDatetimeString(str(NowUTC())) + '.mp4'
    # *Q* GLOB facility may disappear from later versions of ffmpeg, this will need revising when that happens.
    cmd = "ffmpeg -y -pattern_type glob -i '" + sourcefilepattern + "' -vf scale='iw/2:ih/2' " + avifilename
    #temp = osCmd(cmd)
    osCmd(cmd)
    print(textcolor.yellow("Generated"), avifilename)
    MainLog.Log("GeneratePreviewAvi: Completed animation of observation.",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------
    
def ReportObservationErrors(): # 1 references.
    # If any errors were recorded during the session, summarise them here.
    # The display is very active during an observation, so it is useful to summarise errors clearly when the observation is complete.
    if len(MainLog.ErrorList) > 0: # Error messages were reported during the run.
        print(textcolor.yellow('NOTE: MainLog recorded the following errors DURING the observation :-'))
        for ln in MainLog.ErrorList: print("\t" + textcolor.orange(ln))
        MainLog.ErrorList = [] # Empty the list. We've reported it now.
    if len(CamLog.ErrorList) > 0: # Error messages were reported during the run.
        print(textcolor.yellow('NOTE: CamLog recorded the following errors DURING the observation :-'))
        for ln in CamLog.ErrorList: print("\t" + textcolor.orange(ln))
        CamLog.ErrorList = [] # Empty the list. We've reported it now.
    return True

# ------------------------------------------------------------------------------------------------------

def ObservationRun(): # 1 references.
    """ Perform an observation run. Take a set of photographs and keep the camera pointing at the target. 
        This is the core of the program. This is the main loop that tracks a target and captures photos. 
        It loops until 
            the set number of photos are reached,
                or
            a BREAK signal is received,
                or
            the target moves out of sight,
                or
            an irrecoverable situation is detected.
        It can be terminated by pressing 'x' on the keyboard.
        It could also be terminated by an input signal from a GPIO pin (ie a button) if enabled. 
        This routine maintains its own display showing the status of the tracking and observation.
        DEBUGGING NOTE: Lots happen here, including co-ordination between multiple processing threads.
                        The display refreshes constantly, so it is easy to lose error messages.
                        If you want to capture error messages you can run the routine in debug mode.
                        In debug mode the main display is disabled and ONLY error messages will appear on the terminal.
                        Activate debug mode in the startup parameters json file. 
                            'Parameters.DebugMode' : true, 
                        It can also be done from the Miscellaneous Tools. """
    MainLog.Log("ObservationRun: Beginning observation.",terminal=False)
    
    RunObservation = True # We are OK to run the observation loop.
    observationresult = True # Was observation completed successfully?
    
    # Don't start an observation if the target is not yet in range.
    if not Session.Target.Visible(): # The target isn't yet within the visibility range of the telescope.
        MainLog.Log("ObservationRun: The target is not within the visibility range of the telescope.",terminal=True)
        observationresult = False
        RunObservation = False # Not OK to run the observation loop.
        return observationresult # Quit the run.
        
    # Setup campaign information.
    DocumentSession() # Create text file listing the details of this session.
    DriftTracker.Reset() # Clear the drift tracking object for this new observation target.
    MainLog.ErrorList = [] # Clear out any old error summaries. We only want to report NEW instances.
    CamLog.ErrorList = [] # Clear out any old error summaries. We only want to report NEW instances.
    ReadyToObserve = False # We are not on-target yet.
    Led4.Off() # ReadyToObserve status LED.
    MainLog.Log('ObservationRun.initial: ReadyToObserve = False',terminal=False)
    temp = GetTerminalSize() # Note the size of the window. If it changes, we'll clear the screen.
    TerminalCols = temp[0] # Current screen columns.
    TerminalRows = temp[1] # Current screen rows.
    temp = colordisplay.GlobalWindowLimits() # How much screen space do all the windows required?
    if TerminalCols < temp[0] or TerminalRows < temp[1]:
        MainLog.Log("ObservationRun: Terminal", TerminalCols,"*",TerminalRows,", Windows",temp[0],"*",temp[1],Terminal=True)
        MainLog.Log("ObservationRun: The terminal window is not big enough to display ALL available data. Stretch if possible.",Terminal=True)
    obsstart = NowUTC() # Note the start of the observation run.
    PhotoCount = 0 # How many photos have been taken? We can exit the loop when the limit is reached. If Camera is disabled, it will loop forever.
    SlowLoopCounter = 0 # Count how often we have slow processing loops, it can be the sign of storage problems. 
    
    # Load the weather information into the weather window.
    AstroSeeing.UpdateWindow(WeatherWindow) # Get a list of weather/observation facts.

    # Reset PhotoCount in the camera and wait for acknowledgement.
    # PhotoCount is maintained by the CameraThread, so we must communicate with it.
    StartCameraThread() # Fire up the camera thread if it's not running.
    ControlMessage = {'TimeStamp' : NowUTC(), 'PhotoCount' : 0}
    CameraControlQueue.put(ControlMessage) # Tell the camera to reset the photo count.
    # Wait for acknowledgement
    MainLog.Log("ObservationRun: Resetting camera PhotoCount.",terminal=False)
    ack = False # No acknowledgement from the camera yet.
    AckTimer = timer(120) # Set a timer for an acknowledgement. Camera is considered 'hung' or 'dead' after that.
    while ack == False: # Loop until we receive acknowledgement.
        time.sleep(0.5) # Pause half a second between checks.
        # Quit if the CameraThread has failed.
        if CameraThread.is_alive() == False: # If the camera thread is dead, then quit immediately.
            MainLog.Log("ObservationRun: CameraThread is not running!",level='error')
            print ("If the camera thread is dead you can try to restart it from the Camera Tools menu.")
            RunObservation = False # We cannot perform the observation. We will have to return to the menu.
            observationresult = False # Don't continue.
            return observationresult # Return to the menu.
        if CameraStatusQueue.empty() == False: # The CameraThread has sent a message that needs processing.
            StatusMessage = CameraStatusQueue.get() # Retrieve the first available message.
            if 'PhotoCountReset' in StatusMessage: # Is it acknowledging that the PhotoCount has been reset?
                ack = True # Acknowledged, OK to proceed.
                MainLog.Log("Reset camera PhotoCount acknowledged.",terminal=False)
            else: # The message is for some other purpose, we ignore it for now.
                MainLog.Log("Reset camera PhotoCount ignored " + str(StatusMessage),terminal=False)
        # If the camera has not acknowledged in a reasonable time, assume something is wrong and quit.
        if AckTimer.Due(): # Timeout on the acknowledgement.
            MainLog.Log("Reset camera Photocount. Acknowledgement timed out. Camera considered unresponsive.",level='error')
            print ("Camera is considered unresponsive.")
            print ("The camera thread is still alive, the camera subsystem may have hung,")
            print ("in which case you should power cycle the RPi to clear the problem.")
            observationresult = False # Don't continue.
            RunObservation = False # We cannot perform the observation. We will have to return to the menu.
            return observationresult # Return to the menu.

    # Check that the communication with the motor microcontroller is alive.
    if MctlThread.is_alive() == False: # Thread has failed.
        MainLog.Log("ObservationRun (startup): MctlThread is not running!",level='error')
        observationresult = False # Don't continue.
        RunObservation = False # We cannot perform the observation. We will have to return to the menu.
        return observationresult # Return to the menu.

    # Set parameters used during the observation run.
    #fieldwidth = 20 # How wide are data fields?
    #labelwidth = 20 # How wide are label fields?
    CameraAlt = None # The current altitude of the camera (reported by the motor microcontroller). Unknown at first.
    CameraAz = None # The current azimuth of the camera (reported by the motor microcontroller). Unknown at first.
    PrevAlt = None # The previous altitude of the telescope. Uninitialised until the main loop has started. 
    #DriftX = None # Drift-X pixels. The reported X pixels error detected by the drift tracking mechanism.
    #DriftY = None # Drift-Y pixels. The reported Y pixels error detected by the drift tracking mechanism.
    #AzDriftSteps = 0 # Drift full motor steps in azimuth.
    #AltDriftSteps = 0 # Drift full motors steps in altitude.
    PrevReadyToObserve = None # We are not ready to observe until the whole telescope is synchronised and on target.
    ObservationStartUTC = None # The UTC timestamp when the image capture begins.
    LoopTimeList = [] # Show how quickly recent loops have completed. 
    cumulativelooptime = 0 # Cumulative total of all the loop times.
    cumulativeloopcount = 0 # Count of all the loops executed.
    MainLog.Log('ObservationRun: Initializing motorcontroller...',terminal=False)
    MainLog.Log('ObservationRun: Stopping any previous motor instructions.',terminal=False)
    StopMotors() # Clear any existing plan that the motors may have.
    if Parameters.ObservationResetsMctl: # Do we just force a full reset of the microcontroller to clean it up each time an observation starts?
        MainLog.Log('ObservationRun: Resetting microcontroller at start of observation (ObservationResetsMctl parameter)',terminal=False)
        Mctl.Reset(planned=True) # Perform a planned reset of the microcontroller to clear it ready for a new observation. 
    if Parameters.InitialGoTo: # Does an observation run start with a GOTO?
        MainLog.Log('ObservationRun: Performing initial GOTO performed before creating trajectory.',terminal=False)
        az, alt = Session.Target.AzAltDegrees() # Calculations for target from observer's location.
        GoToTarget(Session.Target) # Go directly to the target before starting the trajectory mechanism. Comms clogs up otherwise.
    else: # Let the telescope perform initial GOTO once the trajectory is available. Risks comms bottleneck.
        MainLog.Log('ObservationRun: No initial GOTO performed before creating trajectory.',terminal=False)
    if Session.Target.IsFixedPoint(): # Fixed point observations don't move the telescope, so no trajectory is needed.
        Session.SetMotorControlMode('direct') # We assume direct control of the telescope.
    else:
        Session.SetMotorControlMode('trajectory') # We need to pass trajectory information to the motorcontroller so that it can track the object itself.
    line = ('Start observation ' + str(NowUTC()).split('.')[0] + ' UTC -----------------')[:70] # Mark the start of a new observation in some of the status windows.
    MctlTxWindow.Print(line)
    MctlRxWindow.Print(line)
    CameraWindow.Print(line)
    ErrorWindow.Print(line)
    if not Parameters.CameraEnabled:
        CameraWindow.Print('NOTE: Camera is disabled.')
    if CameraInUse.TimelapseTimer == None:
        MainLog.Log("Timelapse inactive.",terminal=False)
    else:
        MainLog.Log("Timelapse active (",CameraInUse.TimelapseSeconds,"s)",terminal=True)
    SessionWindow.Clear(immediate=False) # Clear old messages from the session window.
    MiscTimer = timer(240) # Slow changing miscellaneous details are updated according to this timer. Immediately due.
    DebugTimer = timer(120) # In debug mode, update summary status every 2 minutes.
    UpdateMiscMeasures() # Initialise the miscellaneous measures, they won't update until MiscTimer is due.
    if Parameters.GenerateOverlay: # Generate a .png transparent image which marks expected items.
        MainLog.Log('ObservationRun: GenerateOverlay...')
        GenerateOverlay(astrotime=ts.now()) # Create a single 'OVERLAY' image for the session. This is useful for applying to images to identify things.
    # After this point all messages to the terminal should respect WINDOW and DEBUG MODE selections, otherwise they get overwritten/corrupted.
    if Parameters.DebugMode: 
        # Do not clear the screen in debug mode. We don't want to lose error messages.
        print (textcolor.orange('In DEBUG MODE. The display is suppressed so that any errors are more clear.')) # In debug mode, nothing is displayed except error messages.
        print (textcolor.yellow("In DEBUG MODE. Press 'x' to quit, 'd' toggle debug, 'm' submenu, 'r' refresh.")) # In debug mode, nothing is displayed except error messages.
    else:
        # Not in debug mode. Specific window layout will be used to show information.
        # Any output from error messages or regular print() commands will be lost as the display frequently refreshes.
        ClearScreen() # Clear the screen and force window refresh.
    if Parameters.DebugMode:
        MainLog.Log('ObservationRun: (DebugMode) Starting main loop...')
    keyboardcount = 0 # Count the iterations between keyboard scans.
    colordisplay.GlobalForceRedraw() # Force all window buffers to fully redraw initially.
    while RunObservation: # Main loop of the observation.

        MainLog.Log("ObservationRun: Loop starts",terminal=False)
        # Check for keyboard commands...
        MainLog.Log("ObservationRun: Check for keyboard input...",terminal=False)
        # *Q* The following keyboard scan uses the curses library. It can cause the terminal display to blink sometimes. Not cured yet.
        keyboardcount = (keyboardcount + 1) % Parameters.KeyboardScanDelay # How many loops before checking keyboard. Reduces irritating flash rate. Increase this number to reduce flashing (and responsiveness).
        if keyboardcount == 0: # It's time to scan the keyboard.
            keypress = Keyboard.Check().lower() # Non-blocking scan for keyboard input. 
        else:
            keypress = "" # Don't check keyboard this time round.
        if keypress != "": # Some keyboard input detected. 
            if ord(keypress) == 410: pass # Ignore the 410 character, it is associated with screen resizing.
        if keypress == "x": # Break.
            MainLog.Log("Keyboard interrupt: Terminating.",level='warning',terminal=False)
            ErrorWindow.Print(NowHMS() + ' Keyboard interrupt. Terminating observation.')
            observationresult = False # Don't continue.
            RunObservation = False # This will quit the loop and shut down the motors and camera.
        elif keypress == "m": # Submenu.
            MainLog.Log("Keyboard interrupt: Submenu selected.",terminal=False)
            ObservationSubmenu(drifttracker=DriftTracker) # Pass the drifttracker object because the submenu can access its methods.
            ClearScreen() # Clear screen afterwards.
        elif keypress == "d": # Toggle debug mode.
            MainLog.Log("Keyboard interrupt: Toggle debug mode.",terminal=False)
            Parameters.DebugMode = not Parameters.DebugMode # Toggle the value.
            MainLog.Log("Keyboard interrupt: DebugMode now", Parameters.DebugMode,terminal=False)
            ClearScreen() # Clear screen afterwards.
            if Parameters.DebugMode:
                print(textcolor.yellow("Debug mode ON."))
            else:
                print(textcolor.yellow("Debug mode OFF."))
        elif keypress == "r": # Refresh screen.
            MainLog.Log("Keyboard interrupt: Refresh selected.",terminal=False)
            ClearScreen() # Clear screen afterwards.

        # # Start fresh move/capture iteration.
        # if not Parameters.DebugMode: # In debug mode we don't want to overwrite error messages. So leave the cursor alone.
        #     pass
        # ObservationStatusWindow.PlaceString(ProgramTitle.upper().ljust(86),row=1,col=0,fg=OSW_TITLE_FG,bg=OSW_TITLE_BG) # Inverse colours.
        # t = ts.now() # Current timestamp in 'astro' time.  # Removed 7/3/2023. Unreferenced.
        dtnow = NowUTC() # In datetime format. 
        # If the window dimensions have changed, clear the screen and let it redraw automatically.
        if not Parameters.DebugMode: 
            temp = GetTerminalSize() # Note the size of the window. If it changes, we'll clear the screen.
            if TerminalCols != temp[0] or TerminalRows != temp[1]: # Screen size has changed. Trigger refresh.
                ClearScreen() # Clear screen afterwards.
                TerminalCols = temp[0] # Note the new display dimensions.
                TerminalRows = temp[1]
        MainLog.Log("ObservationRun: Check for input from microcontroller...",terminal=False)
        Session.MctlInput(Session.Target,timeout=30) # Check for anything received from microcontroller (Will trigger responses too). After 30 seconds of processing, return and proceed with rest of loop anyway.
        MainLog.Log("ObservationRun: Check CameraThread is alive...",terminal=False)
        if CameraThread.is_alive() == False: # If the CameraThread has died, quit.
            MainLog.Log("ObservationRun: CameraThread is not running!",level='error')
            CameraWindow.Print(NowHMS() + " CameraThread is not running.")
            observationresult = False # Don't continue.
            RunObservation = False # Observation cannot continue.
        MainLog.Log("ObservationRun: Check MctlThread is alive...",terminal=False)
        if MctlThread.is_alive() == False: # If the motor microcontroller communication thread has died, quit.
            MainLog.Log("ObservationRun: (loop) MctlThread is not running!",level='error')
            observationresult = False # Don't continue.
            RunObservation = False # Observation cannot continue.
        MainLog.Log("ObservationRun: Check CameraStatusQueue...",terminal=False)
        if CameraStatusQueue.empty() == False: # The CameraThread has sent messages that need to be processed.
            StatusMessage = CameraStatusQueue.get() # Retrieve the first message in the queue.
            # Extract any useful information from the received messages.
            if 'PhotoCount' in StatusMessage: PhotoCount = StatusMessage['PhotoCount'] # Camera has updated the number of photographs taken during this run.
            #if 'DriftX' in StatusMessage: DriftX = StatusMessage['DriftX'] # Camera reports new X pixel drift.
            #if 'DriftY' in StatusMessage: DriftY = StatusMessage['DriftY'] # Camera reports new Y pixel drift.
            # if 'AzDriftSteps' in StatusMessage: AzDriftSteps = StatusMessage['AzDriftSteps'] # Camera reports new Azimuth motor steps to compensate for drift.
            # if 'AltDriftSteps' in StatusMessage: AltDriftSteps = StatusMessage['AltDriftSteps'] # Camera reports new Altitude motor steps to compensate for drift.
        MainLog.Log("ObservationRun: Calculate current target position...",terminal=False)
        # Calculate the current position of the target. This also updates the cached values, which remain valid for the duration of this loop.
        ra, dec = Session.Target.RaDecDegrees() # Target's position. Right Ascension and Declination.
        az, alt = Session.Target.AzAltDegrees() # Target's position. Altitude and Azimuth from observer's location.
        MainLog.Log("ObservationRun: Update ObservationStatusWindow...",terminal=False)
        ObservationDuration = (dtnow - obsstart).total_seconds() # How long has this observation run been running for?
        ObservationStatusWindow.FieldValue('TARGET',Session.Target.Name,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Update the target name. 
        ObservationStatusWindow.FieldValue('FOLDER',FolderList.get('session'),fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Which folder is the observation data saved in. 
        ObservationStatusWindow.FieldValue('CLOCK',str(NowUTC()).split("+")[0],fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # System clock in UTC. 
        ObservationStatusWindow.FieldValue('DURATION','(' + HRSeconds(ObservationDuration)+ ')',fg=OSW_TEXT_GOOD) # How long has this observation been running.
        # Calculate storage available.    
        if not UpdateStorageStatus(): # Update storage space available, and decide if it's safe to continue.
            observationresult = False # Don't continue.
            RunObservation = False # Quit the observation run.
            MainLog.Log("ObservationRun: Insufficient storage space terminating the observation.",level="error")
        UpdateCpuLoad() # Update the CPU load figures.
        # Motor status.
        if Parameters.MotorsEnabled: ObservationStatusWindow.FieldValue('MEN',Parameters.MotorsEnabled,fg=OSW_TEXT_GOOD) # Green
        else: ObservationStatusWindow.FieldValue('MEN',Parameters.MotorsEnabled,fg=OSW_TEXT_BAD) # Red
        # Camera status.
        UpdateCameraStatus() # Update the camera status.
        # Motor control mode.
        ObservationStatusWindow.FieldValue('CMODE',Session.MotorControlMode,fg=OSW_TEXT_GOOD) # *Q* Is MotorControlMode needed anymore?
        # Target status
        if ReadyToObserve: # Camera is on target. Report the status.
            ObservationStatusWindow.FieldValue('TSTATUS',"Acquired   ",fg=OSW_TEXT_GOOD) # Green
            if Session.AutonomousControl or Session.MotorControlMode == 'direct': # We're on target AND there's a trajectory in place, or we've taken direct control of the motors.
                ObservationStatusWindow.FieldValue('TSDESC',"Ready for observation.    ") # Green
            else: # We're on target but the motor microcontroller does not have a full trajectory yet, we still need to wait before taking photographs.
                ObservationStatusWindow.FieldValue('TSDESC',"Waiting for trajectory.   ") # Green
        else: # The camera has not yet reached the target position.
            ObservationStatusWindow.FieldValue('TSTATUS',"Acquiring  ",fg=OSW_TEXT_BAD) # Red
            ObservationStatusWindow.FieldValue('TSDESC',"Not ready for observation.")
        if Session.Target.Visible() == False: fgc = OSW_TEXT_BAD # Field colour if target is not visible. (Red)
        elif Session.Target.ApproachingLimit(): fgc = OSW_TEXT_POOR # Field colour if target is approaching limits. (Yellow)
        else: fgc = OSW_TEXT_GOOD # Field colour if target is visible. (Green)
        dh, dm, ds = AngleToHMS(ra) # Convert target Right Ascension angle into hours, minutes, seconds.
        CameraAlt, CameraAz = CurrentAltAz() # Where is the camera actually pointing at the moment?
        if MiscTimer.Due(): UpdateMiscMeasures() # Slowly changing and miscellaneous facts update here.

        ObservationStatusWindow.FieldValue('CAMAZ',DisplayDegree(CameraAz,13) + DegreeSymbol,fg=fgc,bg=textcolor.BLACK) # Camera's last reported position.
        ObservationStatusWindow.FieldValue('CAMALT',DisplayDegree(CameraAlt,13) + DegreeSymbol,fg=fgc,bg=textcolor.BLACK) 
        ObservationStatusWindow.FieldValue('TARAZ',DisplayDegree(az,13) + DegreeSymbol,fg=fgc,bg=textcolor.BLACK) # Current target position.
        ObservationStatusWindow.FieldValue('TARALT',DisplayDegree(alt,13) + DegreeSymbol,fg=fgc,bg=textcolor.BLACK) 
        ObservationStatusWindow.FieldValue('COMP',CompassPoint(az),fg=fgc,bg=textcolor.BLACK) # Azimuth as compass point.
        ObservationStatusWindow.FieldValue('RA',DisplayHMS(dh,dm,ds,13),fg=fgc,bg=textcolor.BLACK) # RA and DEC of target.
        ObservationStatusWindow.FieldValue('DEC',DisplayDegree(dec,13) + DegreeSymbol,fg=fgc,bg=textcolor.BLACK) 
        MainLog.Log("ObservationRun: Target: Acquired=" + str(ReadyToObserve) + ", Alt=" + str(alt) + ", Az=" + str(az) + ", ra=" + str(ra) + ", dec=" + str(dec),terminal=False) 

        # If we're on target, then activate the camera (it runs in a separate thread until told to stop).
        if True: # Was Parameters.CameraEnabled:
            if PrevReadyToObserve != ReadyToObserve: # 'on target' status has changed.
                # It is always safe to turn OFF the camera.
                # But only turn the camera ON if the microcontroller reports that it has got AutonomousControl (ie a valid trajectory in place).
                if ReadyToObserve == False or Session.AutonomousControl or Session.Target.IsFixedPoint(): # Only change status if turning OFF or if AutonomousControl is ready, or it's a fixed point.
                    ControlMessage = {'TimeStamp' : NowUTC(), 'ReadyToObserve' : ReadyToObserve, 'BatchSize' : 1}
                    CameraControlQueue.put(ControlMessage) # Keep sending the CameraEnabled status to the camera.
                    if Parameters.DebugMode:
                        print (NowHMS() + " ReadyToObserve changed from " + str(PrevReadyToObserve) + " to " + str(ReadyToObserve))
                    MainLog.Log('ObservationRun. ReadyToObserve change from',PrevReadyToObserve,'to',ReadyToObserve,terminal=False)
                    PrevReadyToObserve = ReadyToObserve
            if ReadyToObserve:
                if ObservationStartUTC == None: ObservationStartUTC = NowUTC() # Note when the observation starts.
                if CameraInUse.CameraFault(): # The camera isn't behaving itself. We may need to power cycle the RPi.
                    MainLog.Log("CameraInUse.CameraFault: You probably need to power cycle the RPi.",level='error')
                    CamLog.Log("CameraInUse.CameraFault: You probably need to power cycle the RPi.",level='error')
                    observationresult = False # Don't continue
                    RunObservation = False # Terminate the observation.
                    
        if PhotoCount >= Parameters.BatchSize:
            # We've taken the required number of photos as defined by BatchSize.
            # The CameraHandler thread is probably already working on the next one, so you may get an extra freebie!
            MainLog.Log("ObservationRun: BatchSize reached. Observation run complete.")
            RunObservation = False

        if Mctl.DeviceFailure: # Communication with microcontroller has failed completely.
            MainLog.Log("ObservationRun: Mctl.DeviceFailure reported. Terminating observation.",level='error')
            observationresult = False # Don't continue.
            RunObservation = False

        # Check that the target is within observation range of the motors and above the horizon.
        MainLog.Log("ObservationRun: Check target is within observation range...",terminal=False)
        if alt < 0.0 and PrevAlt != None: # Target is below horizon!
            if alt < PrevAlt or alt < 5.0: # The target has set and won't rise for a while!
                MainLog.Log("ObservationRun: Object below horizon. Terminating observation.",level='warning')
                observationresult = False # Don't continue.
                RunObservation = False
        PrevAlt = alt
        for i in MotorControls: # Check also it is within range of the motor movement limits.
            if i.MotorName == "altitude": # Check range of Altitude motor.
                if alt < i.MinAngle or alt > i.MaxAngle: # Target is out of scope of the motors.
                    MainLog.Log("ObservationRun: The target is outside the altitude range of the telescope. Terminating observation.",level='warning')
                    observationresult = False # Don't continue.
                    RunObservation = False
            if i.MotorName == "azimuth": # Check range of Azimuth motor.
                if az < i.MinAngle or az > i.MaxAngle: # Target is out of scope of the motors.
                    MainLog.Log("ObservationRun: The target is outside the azimuth range of the telescope. Terminating observation.",level='warning')
                    observationresult = False # Don't continue.
                    RunObservation = False

        MainLog.Log("ObservationRun: Update image statistics...",terminal=False)
        ImageStatusWindow.FieldValue('IMAGES',str(ImageCount()),fg=OSW_TEXT_GOOD) 
        ImagesPerHour = 0 # The number of images collected per hour.
        ImageTimePerHour = 0 # The amount of light gathered each hour (in exposure seconds).
        if True: # Was Parameters.CameraEnabled:
            pceta = '' # Don't know the estimated completion time yet.
            if PhotoCount > 0 and ObservationStartUTC != None: # We can estimate when the batch of photographs will be completed.
                pcprogress = float(PhotoCount) / Parameters.BatchSize # Percentage of way through the image batch.
                if pcprogress > 0.0: # We've made some progress, so estimate the completion time.
                    pcelapsed = (NowUTC() - ObservationStartUTC).total_seconds() # Elapsed time so far (seconds).
                    pcend = ObservationStartUTC + timedelta(seconds = int(pcelapsed / pcprogress)) # Roughly when will the batch be completed?
                    pceta = str(pcend)[:16] # YYYY.MM.DD HH:MM
                    # Calculate images per hour being captured.
                    ImagesPerHour = int(3600 * PhotoCount / pcelapsed)
                    # Calculate total image time accumulated per hour.
                    ImageTimePerHour = round(ImagesPerHour * CameraInUse.ExposureSeconds,2)
            ImageStatusWindow.FieldValue('RUN',str(PhotoCount) + " of " + str(Parameters.BatchSize),fg=OSW_TEXT_GOOD) 
            ImageStatusWindow.FieldValue('ETA',pceta,fg=OSW_TEXT_GOOD) 
        else:
            ImageStatusWindow.FieldValue('RUN',str(PhotoCount) + " of " + str(Parameters.BatchSize) + ' (camera disabled)',fg=textcolor.RED1) # Red
            ImageStatusWindow.FieldValue('ETA','n/a',fg=OSW_TEXT_GOOD) 
        # ObservationStatusWindow.PlaceString("sub[M]enu, [R]efresh, e[X]it".ljust(86),row=16,col=0,fg=OSW_TITLE_FG,bg=OSW_TITLE_BG) 
        MainLog.Log("ObservationRun: Image rate",ImagesPerHour,"/hr = ", ImageTimePerHour, "s/hr",terminal=False)
        if GPIO.input(StopBCM) == 0: # Emergency stop pin on RPi has been grounded. 
            print(textcolor.red('STOP BUTTON: Break observation'))
            observationresult = False # Don't continue
            RunObservation = False # Quit loop.
        MainLog.Log("ObservationRun: Update ImageStatusWindow...",terminal=False)
        UpdateCameraCaptureStatus()
        # Explain what is in the 'last captured image' buffer.
        if not isinstance(CameraInUse.CvImage,type(None)): # openCV image buffer is loaded.
            if len(CameraInUse.CvImage.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            ImageStatusWindow.FieldValue("OCVIB","loaded " + HmsFromStamp(CameraInUse.LastImageDateTime) + " " + str(CameraInUse.CvImage.shape[0]).rjust(4) + "*" + str(CameraInUse.CvImage.shape[1]).rjust(4) + " " + fmt,fg=OSW_TEXT_GOOD)
        else:
            ImageStatusWindow.FieldValue("OCVIB","empty",fg=OSW_TEXT_POOR)
        # Explain the status of the TARGET tracking image.
        if not isinstance(DriftTracker.TargetImage,type(None)): # openCV image buffer is loaded.
            temp = "matched " + str(len(DriftTracker.TargetStarMatchList)) + " of " + str(DriftTracker.TargetStarCount) + " stars"
            if len(DriftTracker.TargetImage.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            temp = str(DriftTracker.TargetImage.shape[0]).rjust(4) + "*" + str(DriftTracker.TargetImage.shape[1]).rjust(4) + " " + fmt + " " + temp
            ImageStatusWindow.FieldValue("DTI","loaded " + HmsFromStamp(DriftTracker.TargetTimeStamp) + " " + temp,fg=OSW_TEXT_GOOD)
        else: # No drift target image available.
            ImageStatusWindow.FieldValue("DTI","empty",fg=OSW_TEXT_POOR)
        # Explain the status of the LATEST tracking image.
        if not isinstance(DriftTracker.LatestImage,type(None)): # openCV image buffers are loaded.
            temp = "matched " + str(len(DriftTracker.LatestStarMatchList)) + " of " + str(DriftTracker.LatestStarCount) + " stars"
            if len(DriftTracker.LatestImage.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            temp = str(DriftTracker.LatestImage.shape[0]).rjust(4) + "*" + str(DriftTracker.LatestImage.shape[1]).rjust(4) + " " + fmt + " " + temp
            ImageStatusWindow.FieldValue("DLI","loaded " + HmsFromStamp(DriftTracker.LatestTimeStamp) + " " + temp,fg=OSW_TEXT_GOOD)
        else: # No current drift image available.
            ImageStatusWindow.FieldValue("DLI","empty",fg=OSW_TEXT_POOR)
        ReadyToObserve = True # Work out if all the motors are on target!
        MainLog.Log('ObservationRun. Loop init: ReadyToObserve = True',terminal=False)
        for i in MotorControls: # Report tuning status of each motor in turn.
            if Session.Target.IsFixedPoint(): # Fixed point, doesn't need the motor to report 'OnTarget' - we decide in this program instead.
                pass # Take no action here. Motor was already placed 'on target' when ObservationRun started. It doesn't move after that.
            elif not i.OnTarget: 
                ReadyToObserve = False # This motor is not on target yet. So we're not ready to observe.
                MainLog.Log('ObservationRun.',i.MotorName,'Not on target: ReadyToObserve = False',terminal=False)
            if i.LatestTuneTime != None: # This motor has been tuned. 
                if i.MotorName == 'azimuth':
                    ImageStatusWindow.FieldValue("LAZT",str(i.LatestTuneSteps) + " steps at " + str(i.LatestTuneTime).split(".")[0],fg=OSW_TEXT_GOOD)
                else:
                    ImageStatusWindow.FieldValue("LALT",str(i.LatestTuneSteps) + " steps at " + str(i.LatestTuneTime).split(".")[0],fg=OSW_TEXT_GOOD)
            else: # This motor has not been tuned.
                if i.MotorName == 'azimuth':
                    ImageStatusWindow.FieldValue("LAZT",'None',fg=OSW_TEXT_GOOD)
                else:
                    ImageStatusWindow.FieldValue("LALT",'None',fg=OSW_TEXT_GOOD)
        if ReadyToObserve: Led4.On() # ReadyToObserve status LED.
        else: Led4.Off() # ReadyToObserve status LED.
        LoopTime = NowUTC() - dtnow # How long did the loop take?
        ltts = LoopTime.total_seconds() # How long did the processing loop take?
        cumulativelooptime += ltts # Total processing time of all loops.
        cumulativeloopcount += 1 # Number of loops.
        averagelooptime = cumulativelooptime / cumulativeloopcount # Average loop time.
        MiscWindow.FieldValue("AVELOOP",str(round(averagelooptime,3)) + "s")
        MiscWindow.FieldValue("TOTLOOP",str(round(ltts,3)) + "s") # Latest loop time.
        if ltts > 3: MiscWindow.FieldColor("TOTLOOP",fg=OSW_TEXT_BAD) # Loop is taking too long, something may be wrong.
        elif ltts > 0.5: MiscWindow.FieldColor("TOTLOOP",fg=OSW_TEXT_POOR) # Loop is slower than planned, but not terrible.
        else: MiscWindow.FieldColor("TOTLOOP",fg=OSW_TEXT_GOOD) # Loop is performing as expected.
        MainLog.Log("ObservationRun: Total LOOP time=" + str(ltts * 1000) + "ms. Ave LOOP time=" + str(averagelooptime * 1000) + "ms.",terminal=False)
        LoopTimeList.append(round(ltts,1)) # Add to the list of recent loop times.
        if ltts > 20: # Exceedingly long loop time. O/S is busy with something else! If frequent it can be a sign that the memory card is aging/fragmented/damaged. Time to reinstall.
            SlowLoopCounter += 1 # Increment the count of slow loops, if we get a lot, there's maybe a problem.
            ErrorWindow.Print(NowHMS() + ' slow loop time ' + str(round(ltts,0)) + "s.")
            if SlowLoopCounter % 10 == 0:
                ErrorWindow.Print(NowHMS() + ' Detected ' + str(SlowLoopCounter) + ' slow loops, O/S issue?')
                # A lot of slow loops suggests that the O/S is getting distracted with other tasks.
                # It can be a sign that the memory card is aging and needs replacing.
        LoopTimeList = LoopTimeList[-10:] # Limit list to last 10 entries.
        MiscWindow.FieldValue("RECLOOPS",str(LoopTimeList))
        UpdateWindGustCheck(az)

        MainLog.Log("ObservationRun: Update target chart...",terminal=False)
        if Parameters.DebugMode: # We're in debug mode, just summary status update.
            if DebugTimer.Due(): # It's time to publish a summary status.
                print (NowHMS() + " Target " + Session.Target.Name + " " + AzAltText(az,alt))
                print (NowHMS() + " Session images: " + ImageCount_Session()) # Count images in the current SESSION!
                for line in StorageStrings(): print (NowHMS() + line)
                print (NowHMS() + " Session: " + FolderList.get("session"))
        else: # Not in debug mode, update the color display.
            MainLog.Log("ObservationRun: Refresh display windows...",terminal=False)
            # Refresh status and debug windows.
            # These will draw if their allocated space is available.
            # - Column 1
            #ObservationStatusWindow.Draw(TerminalRows,TerminalCols) # Refresh the actual display.
            ObservationStatusWindow.Display(TerminalRows,TerminalCols) # Refresh the actual display.
            #ImageStatusWindow.Draw(TerminalRows,TerminalCols)
            ImageStatusWindow.Display(TerminalRows,TerminalCols)
            AstroSeeing.UpdateWindow(WeatherWindow) # Update weather measures in the window buffers.
            FogForecast = AstroSeeing.GetFogData()
            fr = FogForecast.get('fogrisk','')
            WeatherWindow.FieldValue('FOG',fr)
            if fr in ['3/3']: WeatherWindow.FieldColor('FOG',fg=OSW_TEXT_BAD,bg=OSW_TEXT_BG)
            elif fr in ['0/3','1/3']: WeatherWindow.FieldColor('FOG',fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
            else: WeatherWindow.FieldColor('FOG',fg=OSW_TEXT_POOR,bg=OSW_TEXT_BG)
            WeatherWindow.Display(TerminalRows,TerminalCols) # Display weather status.
            InstructionWindow.Display(TerminalRows,TerminalCols) # Display session status.
            if Parameters.ChartEnabled: # On screen primitive sky tracking chart.
                chart.plot("target",alt,az,track=True) # Plot position for horizontal mount.
                chart.plot("camera",CameraAlt,CameraAz,track=False) # Plot position of the camera.
                sun_az, sun_alt = SunTarget.AzAltDegrees()
                chart.plot("sun",sun_alt,sun_az,track=False) # Plot position of the sun.
                moon_az, moon_alt = MoonTarget.AzAltDegrees()
                chart.plot("moon",moon_alt,moon_az,track=False) # Plot position of the moon.
                iss_az, iss_alt = ISSTarget.AzAltDegrees()
                chart.plot("iss",iss_alt,iss_az,track=False) # Plot position of the international space station.
                css_az, css_alt = CSSTarget.AzAltDegrees()
                chart.plot("css",css_alt,css_az,track=False) # Plot position of the international space station.
                chart.draw(TerminalRows,TerminalCols)
            # - Column 2
            ErrorWindow.Display(TerminalRows,TerminalCols) # Display latest error messages.
            Session.ShowRemoteStatus() # Update status measures in the window buffers.
            SessionWindow.Display(TerminalRows,TerminalCols) # Display instructions.
            MctlRxWindow.Display(TerminalRows,TerminalCols) # Display Microcontroller UART RX traffic.
            MctlTxWindow.Display(TerminalRows,TerminalCols) # Display Microcontroller UART TX traffic.
            CameraWindow.Display(TerminalRows,TerminalCols) # Display camera status.
            MiscWindow.Display(TerminalRows,TerminalCols) # Display miscellaneous measurements.
            # - Column 3
            DriftWindow.Display(TerminalRows,TerminalCols) # Display drift calculation log.
            CameraTxWindow.Display(TerminalRows,TerminalCols) # Display Camera command TX traffic.
            CameraRxWindow.Display(TerminalRows,TerminalCols) # Display Camera command RX traffic.
            DevWindow.Display(TerminalRows,TerminalCols) # Display developer events messages.
        # End of main ObservationRun loop.
        MainLog.Log("ObservationRun: End of main loop...",terminal=False)
        
    # Observation is over at this point.
    print(textcolor.clearforward()) # Clear the screen from the current location forward, makes the following messages easier to read.
    ReadyToObserve = False
    Led4.Off() # ReadyToObserve light should be OFF now.
    if True: # Was Parameters.CameraEnabled: # Tell the camera it is all over.
        ControlMessage = {'TimeStamp' : NowUTC(), 'ReadyToObserve' : False}
        CameraControlQueue.put(ControlMessage) # Keep sending the CameraEnabled status to the camera.
        ShutdownCamera() # Wait for the camera thread to terminate.
    # Tell the motors it is all over now that the camera is completed. 
    StopMotors() # Tell the motors to immediately stop. 
    print ('\n' + textcolor.cursordown(10) + textcolor.clearforward()) # Move cursor below the ObservationRun display and clear the rest of the screen to make way for the menu.
    if Parameters.MarkupAvi: # We can generate a small animation (slow!) of the observation from the preview images.
        GeneratePreviewAvi()


    ReportObservationErrors()

    print(textcolor.yellow("The images are stored in " + FolderList.get('session')))
    if CameraInUse.FastImageCapture: # Only JPG files have been created so far.
        print(textcolor.yellow("FastImageCapture is active. Only the raw JPG data files have been created so far."))
        print(textcolor.yellow("If you want to create separate DNG files, or pure JPG files you still need to process them."))
        
    # End of observation...    
    MainLog.Log("ObservationRun: end.",terminal=False)
    return observationresult
    

# ----------------------------------------------------------------------------------------------------- 

def AddAngles(angle1,angle2): # 2 references.
    """ Add 2 angles together.
        Angles can be decimal values, or skyfield angle objects. """
    if hasattr(angle1,'_degrees'): a1 = angle1._degrees
    elif hasattr(angle1,'degrees'): a1 = angle1.degrees
    else: a1 = angle1
    if hasattr(angle2,'_degrees'): a2 = angle2._degrees
    elif hasattr(angle2,'degrees'): a2 = angle2.degrees
    else: a2 = angle2
    result = a1 + a2
    return result

# ----------------------------------------------------------------------------------------------------- 

def SetMotorClock(name): # 2 references.
    FoundIt = False
    for i in MotorControls:
        if i.MotorName == name:
            FoundIt = True
            i.SetMotorClock()
    return FoundIt

# ------------------------------------------------------------------------------------------------

def SetAzimuthClock(): # 1 references. # For menu
    SetMotorClock('azimuth')
    
# ------------------------------------------------------------------------------------------------

def SetAltitudeClock(): # 1 references. # For menu
    SetMotorClock('altitude')

# ------------------------------------------------------------------------------------------------

def DisableCleanup(): # 1 references. # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        print ("The Raspberry Pi HQ sensor performs some on-chip image cleanup.")
        print ("This may degrade the raw image data.")
        print ("It is recommended to disable this feature for astrophotography.")
        print ("- You may get warning messages displayed by this action, they are generally OK to ignore.")
        if AskYesNo("Disable on-sensor cleanup? (y/N)",False):
            SensorInUse.DisableCleanup()
            Parameters.DisableCleanup = True
            FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
            DocumentSession()
            DriftTracker.Reset()

# ------------------------------------------------------------------------------------------------

def EnableCleanup(): # 1 references. # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        print ("The Raspberry Pi High Quality camera can perform some on-chip image cleanup.")
        print ("It is often disabled for astrophotography because it degrades the raw image data slightly.")
        print ("It is recommended to enable this for regular photography.")
        print ("- You may get warning messages displayed by this action, they are generally OK to ignore.")
        if AskYesNo("Enable on-sensor cleanup? (y/N)",False):
            Parameters.DisableCleanup = False
            SensorInUse.EnableCleanup()
            FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
            DocumentSession()
            DriftTracker.Reset()
    
# ------------------------------------------------------------------------------------------------------

def PositionStrings(): # 1 references.
    """ Return a string listing the current motor positions. 
        For display purposes. """
    PS = " Camera:"
    for i in MotorControls:
        PS += " " + i.MotorName + ": " + str(i.AngleToStep(i.CurrentAngle)) + " (" + str(round(i.CurrentAngle,3)) + DegreeSymbol + ")"
    PS = " " + PS.strip()
    return [PS]

# ------------------------------------------------------------------------------------------------------

def TargetStrings(): # 1 references. 
    """ Returns a list of strings describing the current target. """
    # If star name is recognised in the starname dictionary, list the constellation too.
    result = []
    constellation = Session.Target.Constellation
    if constellation == None:
        constellation = ''
    else:
        constellation = "(" + constellation + ") "
    type = Session.Target.ObjectType
    if type == None:
        type = ''
    else:
        type = '(' + type + ') '
    TS = " Target: " + Session.Target.Name + " "
    TS += type
    TS += constellation
    result.append(TS)
    TS = " Mag: " + str(Session.Target.Magnitude) + " "
    az, alt = Session.Target.AzAltDegrees()
    TS += AzAltText(az,alt)
    if Session.Target.Visible(): TS += " (in range)"
    else: TS += " (out of range)"
    result.append(TS)
    return result

# ------------------------------------------------------------------------------------------------------

def SensorStrings(): # 1 references.
    """ Return a string showing the current sensor/image settings. """
    SS = " Sensor: Mode " + str(SensorInUse.Mode) + ", Dimensions " + str(SensorInUse.PixelWidth) + "x" + str(SensorInUse.PixelHeight)
    if SensorInUse.OnChipCleanup:
        SS += " OnChipCleanup enabled."
    else:
        SS += " OnChipCleanup disabled."
    return [SS]
    
# ------------------------------------------------------------------------------------------------------

def ExposureStrings(): # 1 references.
    """ Return a string listing the current exposure settings. """
    returnlist = []
    ES = " Exposure: " + str(CameraInUse.ExposureSeconds) + "s"
    ES += ", Batch: " + str(Parameters.BatchSize)
    ES += ", Ctrl: " + str(Parameters.ControlBatchSize)
    ES += ", Types: "
    if CameraInUse.CameraSaveJpg: ES += "jpg "
    if CameraInUse.CameraSaveDng: ES += "dng "
    if Parameters.CameraEnabled == False:
        ES += "(Disabled)"
    returnlist.append(ES)
    ES = ""
    if CameraInUse.TimelapseSeconds != None and CameraInUse.TimelapseSeconds > 0:
        ES += " Timelapse: " + str(CameraInUse.TimelapseSeconds) + "s. "
    if ES != "": 
        returnlist.append(ES)
    return returnlist

# ------------------------------------------------------------------------------------------------------

def SessionStrings(): # 1 references.
    """ Return a string listing current session details. """
    SS = " Session: " + FolderList.get("session")
    return [SS]
    
# ------------------------------------------------------------------------------------------------------

def ImageStrings(): # 1 references.
    """ Return a string listing current session's images. """
    returnlist = []
    SS = " Campaign images: " + ImageCount_Campaign() # Count images in the CAMPAIGN! (Multiple sessions)
    returnlist.append(SS)
    SS = " Session images: " + ImageCount_Session() # Count images in the current SESSION!
    returnlist.append(SS)
    return returnlist
    
# ------------------------------------------------------------------------------------------------------

def StorageStrings(): # 2 references.
    """ Return a string listing current storage space. """
    returnlist = []
    if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable:
        temp = int(USBDiscMonitor.FreeMegaBytes())
        SS = " USB memory: Free storage: " + format(temp,',') + "Mb."
        if temp < 1000: SS += " (<1 Gb left!)"
        elif temp < 500: SS += " (<500 Mb left! Critical!)"
        returnlist.append(SS)
    temp = int(SDCardMonitor.FreeMegaBytes())
    SS = " SD card: Free storage: " + format(temp,',') + "Mb."
    if temp < 1000: SS += " (<1 Gb left!)"
    elif temp < 500: SS += " (<500 Mb left! Critical!)"
    returnlist.append(SS)
    return returnlist

# ------------------------------------------------------------------------------------------------------

def ProgramStartStrings(): # 1 references.
    """ Return a string listing when the program started. """
    delta = HRSeconds((NowUTC() - Session.ProgramStartTime).total_seconds())
    #delta = HRSeconds(delta)
    PS = " Program started: " + str(Session.ProgramStartTime).split('.')[0] + " UTC        (" + delta + ")"
    return [PS]

# ------------------------------------------------------------------------------------------------------

def DocumentSession(): # 8 references.
    """ Create a brief description of the session and key parameters.
        Details are written to a disc file.    """
    with open(FolderList.get("session") + "info.txt",'w') as f:
        f.write("# " + ProgramTitle.upper() + " session settings:\n")
        f.write("Program started\t" + str(Session.ProgramStartTime) + "\n")
        f.write("Source code\t" + SourceCode() + "\n")
        f.write("Source version\t" + str(SourceDate()) + "\n")
        f.write("Session started\t" + str(NowUTC()) + "\n")
        f.write("Session path\t" + FolderList.get("session") + "\n")
        f.write("Target\t" + Session.Target.Name + "\n")
        f.write("SearchGroup\t" + Session.Target.SearchGroup + "\n")
        f.write("SearchTerm\t" + Session.Target.SearchTerm + "\n")
        f.write("Exposure time\t" + str(CameraInUse.ExposureSeconds) + "seconds\n")
        f.write("Timelapse delay\t" + str(CameraInUse.TimelapseSeconds) + "seconds\n")
        f.write("Sensor mode\t" + str(SensorInUse.Mode) + "\n")
        f.write("Image width\t" + str(SensorInUse.PixelWidth) + "\n")
        f.write("Image height\t" + str(SensorInUse.PixelHeight) + "\n")
        f.write("Maximum exposure time\t" + str(SensorInUse.MaxExposureSeconds) + "seconds\n")
        f.write("Sensor type\t" + SensorInUse.Type + "\n")
        f.write("Pixels per FOV degree width\t" + str(CameraInUse.PixelsPerFovDegreeWidth) + "\n")
        f.write("Pixels per FOV degree height\t" + str(CameraInUse.PixelsPerFovDegreeHeight) + "\n")
        f.write("Seconds per pixel\t" + str(CameraInUse.SecondsPerPixel) + "\n")
        if len(Session.Target.NotesLines) > 0: # There are some descriptive notes to include.
            for line in Session.Target.NotesLines:
                f.write("TargetNotes\t" + line + "\n")
        f.write('Observation conditions forecast (' + AstroSeeing.SourceTitle + '):-\n')
        seeingconditions = AstroSeeing.Translate(color=False)
        for line in seeingconditions:
            f.write(line + "\n")
    # Append key values to 'recent target list'. This is useful if recovering from system failure, or resuming a previous observation at a later date.
    # When selecting a new target, this recent target list is offered as a short-cut to duplicate previous observations.
    with open(HistoryFile,'a') as f:
        f.write(str(NowUTC()).split('.')[0] + "\t" + \
                Session.Target.Name + "\t" + \
                Session.Target.SearchGroup + "\t" + \
                Session.Target.SearchTerm + "\t" + \
                str(float(CameraInUse.ExposureSeconds)) + "\t" + \
                str(SensorInUse.Mode) + "\t" + \
                str(float(CameraInUse.TimelapseSeconds)) + "\n")
    return

# ------------------------------------------------------------------------------------------------------

def SummariseObservationParameters(): # 1 references.
    """ Construct a string listing the observation parameters. 
        Used to confirm that it's OK to start an observation. """
    result = ''
    result += 'Observation of ' + Session.Target.Name + ' will capture ' + str(int(Parameters.BatchSize)) + " images of " + str(CameraInUse.ExposureSeconds) + 's. ('
    if CameraInUse.CameraSaveJpg: result += "JPG "
    if CameraInUse.CameraSaveDng: result += "DNG "
    result = result.strip() + ")"
    return result

# ------------------------------------------------------------------------------------------------------

# Document the default session which has been defined by the startup questions.
# If the menu is used to change key parameters, a fresh session will be created at the same time.
# If you change multiple parameters, an empty set of folders will be needlessly created for each individual parameter change.
# *Q* Low priority, but this could be reworked to avoid creating those unused folder structures.
DocumentSession() # Write a summary document with key info into the session folder.

# ------------------------------------------------------------------------------------------------------

def FlushCommandQueue(): # 1 references. # For menu
    Mctl.WriteFlush(send=False)
    Mctl.ReadFlush()

# ------------------------------------------------------------------------------------------------------

def MicrocontrollerLedsOff(): # 1 references. # For menu
    Parameters.MctlLedStatus = False
    SetGlobalLedStatus()

# ------------------------------------------------------------------------------------------------------

def MicrocontrollerLedsOn(): # 1 references. # For menu
    Parameters.MctlLedStatus = True
    SetGlobalLedStatus()

# ------------------------------------------------------------------------------------------------------

def ReloadParameters(): # 1 references. # For menu
    global Parameters
    Parameters = parameters(filename=ParameterFileName,log=MainLog.Log) # Create and load parameters.
    Parameters.Show()

# ------------------------------------------------------------------------------------------------------

def ShowParameters(): # 1 references. # For menu
    Parameters.Show()

# ------------------------------------------------------------------------------------------------------

def EditParameters(): # 1 references. # For menu
    global Parameters
    # Save current values
    Parameters.SaveAttributes(Parameters.ParamFileName)
    # Backup current values
    osCmd("cp " + Parameters.ParamFileName + " " + Parameters.ParamFileName.split(".")[0] + "_" + CleanDatetimeString(UtcTimeStamp()) + ".bak")
    # Edit 
    os.system("nano " + Parameters.ParamFileName)
    # Reload parameters.
    Parameters = parameters(filename=ParameterFileName,log=MainLog.Log) # Create and load parameters.
    Parameters.Show()
    print(textcolor.yellow("It is advisable to restart the software after changing the parameter file."))

# ------------------------------------------------------------------------------------------------------


def EditTargetHistory(): # 1 references. # For menu
    # Backup current values
    osCmd("cp " + HistoryFile + " " + HistoryFile.split(".")[0] + "_" + CleanDatetimeString(UtcTimeStamp()) + ".bak")
    # Edit 
    os.system("nano " + HistoryFile)

# ------------------------------------------------------------------------------------------------------

def DebugModeOff(): # 1 references. # For menu
    Parameters.DebugMode = False # Full dynamic display enabled.
    MainLog.Log("ObservationRun debug mode disabled. (Error messages may be overwritten very quickly)")

# ------------------------------------------------------------------------------------------------------

def DebugModeOn(): # 1 references. # For menu
    Parameters.DebugMode = True # Dynamic display disabled. Error messages only shown.
    MainLog.Log("ObservationRun debug mode activated. (Easier to see error messages.)")

# ------------------------------------------------------------------------------------------------------

def SelectTarget(): # 1 references. # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        Session.Target = TargetSelection() # Returns a Target class.
        CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
        FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
        DocumentSession()
        DriftTracker.Reset()
        ProgramStatus() # Show current situation of the telescope and target.

# ------------------------------------------------------------------------------------------------------

def BeginObservation(): # 1 references. # For menu
    print(textcolor.yellow(SummariseObservationParameters()))
    if AskYesNo('OK to start observation? (y/N)',default=False):
        ObservationRun()

# ------------------------------------------------------------------------------------------------------

def MenuGoToTarget(): # 1 references. # For menu
    GoToTarget(Session.Target)

# ------------------------------------------------------------------------------------------------------

def SetTimelapseDelay(): # 1 references. # For menu
    CameraInUse.SetTimelapse(SetCameraTimelapse(CameraInUse.TimelapseSeconds))

# ------------------------------------------------------------------------------------------------------

def MenuSetBatchSize(): # 1 references. # For menu
    Parameters.BatchSize = SetBatchSize(Parameters.BatchSize)

# ------------------------------------------------------------------------------------------------------

def MenuSetControlBatchSize(): # 1 references. # For menu
    Parameters.ControlBatchSize = SetControlBatchSize(Parameters.ControlBatchSize)

# ------------------------------------------------------------------------------------------------------

def MenuDarkSet(): # 1 references. # For menu
    StartCameraThread()
    CameraInUse.DarkSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuFlatSet(): # 1 references. # For menu            
    StartCameraThread()
    CameraInUse.FlatSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuBiasSet(): # 1 references. # For menu
    StartCameraThread()
    CameraInUse.BiasSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuDarkFlatSet(): # 1 references. # For menu
    StartCameraThread()
    CameraInUse.DarkFlatSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuManualPreview(): # 1 references. # For Menu
    StartCameraThread()
    ManualPreview() # *Q* should be within AstroCamera class eventually. Some work needed first though.
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuAutoPhoto(): # 1 references. # For menu
    StartCameraThread()
    CameraInUse.AutoPhoto() # Take a series of completely automatic exposures (for focus testing etc in daylight).
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def ProcessImageFiles(): # 1 references. # For menu
    CameraInUse.ProcessImageFiles()
        
# ------------------------------------------------------------------------------------------------------

def AddObservationNotes(): # 1 references. # For menu
    print (textcolor.yellow("Add observation notes to the target."))
    Session.Target.AskForNotes()
    DocumentSession() # Update the session documentation.

# ------------------------------------------------------------------------------------------------------

def ProgramStatus(): # 1 references. # For menu
    """ Show a status summary of the telescope and session.
        What's the target?
        What are the settings?
        What's the current position of the telescope? """
    listlines = []
    temp = (" " + ProgramTitle.upper() + "   Currently: " + (str(NowUTC()).split('.')[0]) + " UTC")
    if Parameters.DebugMode: # In debug mode, warn the user.
        temp += ' (OBSERVATION DISPLAY IN DEBUG MODE!)'
    listlines.extend([temp])
    listlines.extend(TargetStrings())
    listlines.extend(PositionStrings())
    listlines.extend([RiseSetString(Session.Target)])
    listlines.extend(SessionStrings())
    listlines.extend(ExposureStrings())
    listlines.extend(ImageStrings())
    listlines.extend(SensorStrings())
    listlines.extend(StorageStrings())
    listlines.extend(ProgramStartStrings())
    temp = " Observer's location: Latitude: " + DisplayDegree(Parameters.HomeLatVal,10) + DegreeSymbol + " Longitude: " + DisplayDegree(Parameters.HomeLonVal,10) + DegreeSymbol
    listlines.extend([temp])
    textcolor.TextBox(listlines,fg=MENU_SUBTITLE_FG,bg=MENU_SUBTITLE_BG)

# ------------------------------------------------------------------------------------------------------

def ShowColorMap(): # 1 references. # For menu
    """ Development utility. Show the textcolor colors available. """
    textcolor.listcolors()
    Parameters.ShowColorScheme()

# ------------------------------------------------------------------------------------------------------

def ScanForMeteors(): # 1 references. # For menu
    print (textcolor.yellow("This will scan all available 'light' image files for potential meteor trails."))
    print (textcolor.yellow("Press 'x' to quit"))
    CameraInUse.MeteorFileScan() # Scan all available 'light' jpg files for potential meteor traces. Ignore the returned list of filenames.
    
# ------------------------------------------------------------------------------------------------------

def AskFileName(prompt=None,exists=False):
    """ Prompt for a filename.
    exists=True : Check file exists. """
    filename = None
    if prompt == None: 
        if exists: prompt = "Enter existing filename (x to quit): "
        else: prompt = "Enter filename (x to quit): "
    while filename == None:
        filename = input(textcolor.cyan(prompt))
        if filename.lower() == 'x': # Quit
            filename = None
            break
        if exists and os.path.exists(filename) == False:
            print(textcolor.red('File not found. Try again.'))
            filename = None
    return filename
    
# ------------------------------------------------------------------------------------------------------

# Create menu structure.

MotorMenuOptions = {
    'HomeAllMotors':          {'label':'Home all motors',           'bold':False, 'call':HomePosition, 'docurl':None, 'helpdoc':'help.txt'},
    'TuneAzimuth':            {'label':'Tune azimuth position',     'bold':False, 'call':TunePositionAzimuth, 'docurl':None, 'helpdoc':'help.txt'},
    'TuneAltitude':           {'label':'Tune altitude position',    'bold':False, 'call':TunePositionAltitude, 'docurl':None, 'helpdoc':'help.txt'},
    'AzimuthAngle':           {'label':'Move azimuth to angle',     'bold':False, 'call':AzimuthAngle, 'docurl':None, 'helpdoc':'help.txt'},
    'AltitudeAngle':          {'label':'Move altitude to angle',    'bold':False, 'call':AltitudeAngle, 'docurl':None, 'helpdoc':'help.txt'},
    'ExerciseAzimuth':        {'label':'Exercise azimuth motor',    'bold':False, 'call':ExerciseMotorAzimuth, 'docurl':None, 'helpdoc':'help.txt'},
    'ExerciseAltitude':       {'label':'Exercise altitude motor',   'bold':False, 'call':ExerciseMotorAltitude, 'docurl':None, 'helpdoc':'help.txt'},
    'StopAllMotors':          {'label':'Stop all motors',           'bold':False, 'call':StopMotors, 'docurl':None, 'helpdoc':'help.txt'},
}
MotorMenu = proceduremenu(MotorMenuOptions,'Motor tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

CameraMenuOptions = {
    'StartCameraThread':         {'label':'Start camera handler',       'bold':False, 'call':StartCameraThread, 'docurl':None, 'helpdoc':'help.txt'},
    'StopCameraThread':          {'label':'Stop camera handler',        'bold':False, 'call':ShutdownCamera, 'docurl':None, 'helpdoc':'help.txt'},
    'SensorCleanupOff':          {'label':'Sensor cleanup off',         'bold':False, 'call':DisableCleanup, 'docurl':None, 'helpdoc':'help.txt'},
    'SensorCleanupOn':           {'label':'Sensor cleanup on',          'bold':False, 'call':EnableCleanup, 'docurl':None, 'helpdoc':'help.txt'},
    'AutoDetectCamera':          {'label':'Auto detect camera',         'bold':False, 'call':AutoDetectCamera, 'docurl':None, 'helpdoc':'help.txt'},
    'CalibrateFov':              {'label':'Calibrate FoV',              'bold':False, 'call':CalibrateFov, 'docurl':None, 'helpdoc':'help.txt'},
    'EnableCamera':              {'label':'Enable camera',              'bold':False, 'call':EnableCamera, 'docurl':None, 'helpdoc':'help.txt'},
    'DisableCamera':             {'label':'Disable camera',             'bold':False, 'call':DisableCamera, 'docurl':None, 'helpdoc':'help.txt'}
}
CameraMenu = proceduremenu(CameraMenuOptions,'Camera tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MctlMenuOptions = {
    'RestartMicrocontroller': {'label':'Restart microcontroller',   'bold':False, 'call':RestartMicrocontroller, 'docurl':None, 'helpdoc':'help.txt'},
    'FlushCommandQueue':      {'label':'Flush command queue',       'bold':False, 'call':FlushCommandQueue, 'docurl':None, 'helpdoc':'help.txt'},
    'MicrocontrollerLedsOff': {'label':'Microcontroller LEDs off',  'bold':False, 'call':MicrocontrollerLedsOff, 'docurl':None, 'helpdoc':'help.txt'},
    'MicrocontrollerLedsOn':  {'label':'Microcontroller LEDs on',   'bold':False, 'call':MicrocontrollerLedsOn, 'docurl':None, 'helpdoc':'help.txt'}
}
MctlMenu = proceduremenu(MctlMenuOptions,'Microcontroller tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MiscMenuOptions = {
    'ShowParameters':         {'label':'Show parameters',           'bold':False, 'call':ShowParameters, 'docurl':None, 'helpdoc':'help.txt'},
    'EditParameters':         {'label':'Edit parameters',           'bold':False, 'call':EditParameters, 'docurl':None, 'helpdoc':'help.txt'},
    'ReloadParameters':       {'label':'Reload parameters',         'bold':False, 'call':ReloadParameters, 'docurl':None, 'helpdoc':'help.txt'},
    'EditTargetHistory':      {'label':'Edit target history',       'bold':False, 'call':EditTargetHistory, 'docurl':None, 'helpdoc':'help.txt'},
    'DebugModeOn':            {'label':'Debug mode on',             'bold':False, 'call':DebugModeOn, 'docurl':None, 'helpdoc':'help.txt'},
    'DebugModeOff':           {'label':'Debug mode off',            'bold':False, 'call':DebugModeOff, 'docurl':None, 'helpdoc':'help.txt'},
    'ChooseColorScheme':      {'label':'Choose color scheme',       'bold':False, 'call':Parameters.ChooseColorScheme, 'docurl':None, 'helpdoc':'help.txt'},
    'ShowColorMap':           {'label':'Show color map',            'bold':False, 'call':ShowColorMap, 'docurl':None, 'helpdoc':'help.txt'},
    'ChooseColor':            {'label':'Choose individual color',   'bold':False, 'call':Parameters.ChooseColor, 'docurl':None, 'helpdoc':'help.txt'}
}
MiscMenu = proceduremenu(MiscMenuOptions,'Miscellaneous tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

DevMenuOptions = {
    'ShowParameters':         {'label':'Show parameters',           'bold':False, 'call':ShowParameters, 'docurl':None, 'helpdoc':'help.txt'},
    'EditParameters':         {'label':'Edit parameters',           'bold':False, 'call':EditParameters, 'docurl':None, 'helpdoc':'help.txt'}
}
DevMenu = proceduremenu(DevMenuOptions,'Development tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MainMenuOptions = {
    'SelectTarget':           {'label':'Select target',             'bold':True,  'call':SelectTarget, 'docurl':None, 'helpdoc':'help.txt'},
    'BeginObservation':       {'label':'Begin observation',         'bold':True,  'call':BeginObservation, 'docurl':None, 'helpdoc':'help.txt'},
    'ProgramStatus':          {'label':'Status',                    'bold':False, 'call':ProgramStatus, 'docurl':None, 'helpdoc':'help.txt'},
    'GotoTarget':             {'label':'GOTO target',               'bold':False, 'call':MenuGoToTarget, 'docurl':None, 'helpdoc':'help.txt'},
    'HomeAllMotors':          {'label':'Home all motors',           'bold':False, 'call':HomePosition, 'docurl':None, 'helpdoc':'help.txt'},
    'SetExposureTime':        {'label':'Set exposure time',         'bold':False, 'call':MenuSetExposureTime, 'docurl':None, 'helpdoc':'help.txt'},
    'SetTimelapseDelay':      {'label':'Set timelapse delay',       'bold':False, 'call':SetTimelapseDelay, 'docurl':None, 'helpdoc':'help.txt'},
    'SetLightBatchSize':      {'label':'Set light batch size',      'bold':False, 'call':MenuSetBatchSize, 'docurl':None, 'helpdoc':'help.txt'},
    'SetControlBatchSize':    {'label':'Set control batch size',    'bold':False, 'call':MenuSetControlBatchSize, 'docurl':None, 'helpdoc':'help.txt'},
    'TakeDarkFrameSet':       {'label':'Take dark frame set',       'bold':False, 'call':MenuDarkSet, 'docurl':None, 'helpdoc':'help.txt'},
    'TakeFlatFrameSet':       {'label':'Take flat frame set',       'bold':False, 'call':MenuFlatSet, 'docurl':None, 'helpdoc':'help.txt'},
    'TakeBiasFrameSet':       {'label':'Take bias/offset frame set','bold':False, 'call':MenuBiasSet, 'docurl':None, 'helpdoc':'help.txt'},
    'TakeDarkFlatFrameSet':   {'label':'Take dark flat frame set',  'bold':False, 'call':MenuDarkFlatSet, 'docurl':None, 'helpdoc':'help.txt'},
    'TakePreviewFrames':      {'label':'Take preview frames',       'bold':False, 'call':MenuManualPreview, 'docurl':None, 'helpdoc':'help.txt'},
    'TakeAutoFrames':         {'label':'Take auto frames',          'bold':False, 'call':MenuAutoPhoto, 'docurl':None, 'helpdoc':'help.txt'},
    'ScanForMeteors':         {'label':'Scan images for meteors',   'bold':False, 'call':ScanForMeteors, 'docurl':None, 'helpdoc':'help.txt'},
    'AddObservationNotes':    {'label':'Add observation notes',     'bold':False, 'call':AddObservationNotes, 'docurl':None, 'helpdoc':'help.txt'},
    'OvernightForecast':      {'label':'Weather forecast',          'bold':False, 'call':AstroSeeing.TwelveHourForecast, 'docurl':None, 'helpdoc':'help.txt'},
    'MotorMenu':              {'label':'Motor tools',               'bold':False, 'call':MotorMenu, 'docurl':None, 'helpdoc':'help.txt'},
    'MicrocontrollerMenu':    {'label':'Microcontroller tools',     'bold':False, 'call':MctlMenu, 'docurl':None, 'helpdoc':'help.txt'},
    'CameraMenu':             {'label':'Camera tools',              'bold':False, 'call':CameraMenu, 'docurl':None, 'helpdoc':'help.txt'},
    'DevMenu':                {'label':'Development tools',         'bold':False, 'call':DevMenu, 'docurl':None, 'helpdoc':'help.txt'},
    'MiscMenu':               {'label':'Miscellaneous tools',       'bold':False, 'call':MiscMenu, 'docurl':None, 'helpdoc':'help.txt'}
}

ProgramStatus() # Show current situation of the telescope and target at startup.
MainMenu = proceduremenu(MainMenuOptions,'Pilomar main menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

# Run main menu.
while True:
    MainMenu.Prompt()
    if AskYesNo("Do you really want to shut down? (y/N)",default=False): break # OK to quit.
    

# Cleanup.

# Offer to return camera to the HOME position.
CameraAlt, CameraAz = CurrentAltAz() # Current camera position.
HomeAlt, HomeAz = HomeAltAz() # Home position for camera.
if round(CameraAlt,1) != round(HomeAlt,1) or round(CameraAz,1) != round(HomeAz,1): # Camera is not at home position.
    print(textcolor.yellow("The camera is currently at " + AzAltText(CameraAz,CameraAlt)))
    answer = AskYesNo("Would you like to home the camera before powering off? (y/N) ",False)
    if answer:
        print ("Returning camera to home position...")
        HomePosition()
        CameraAlt, CameraAz = CurrentAltAz() # Current camera position.
        if round(CameraAlt,1) != round(HomeAlt,1) or round(CameraAz,1) != round(HomeAz,1): # Camera is not at home position.
            textcolor.TextBox(["The camera did not successfully return to the home position.",
                               'The camera is left at ' + AzAltText(CameraAz,CameraAlt)],
                               fg=textcolor.WHITE,bg=textcolor.RED)
        else:
            print(textcolor.yellow('Camera homed successfully.'))
    else:
        textcolor.TextBox(['The camera will resume from its current position when restarted.',
                           'To home the camera now, use the "home" option on the Camera Tools menu.'])
else: # Camera is already at home position.
    print ('Camera is currently in home position. No homing needed.')

# Store final position and total runtime of motors.
for i in MotorControls:
    i.StoreRecoveryAngle(force=True) # Write the final position of each motor to disc. Force the write.
    
print (' ')
print (textcolor.yellow('Stopping microcontroller communication...'))
UartControlQueue.put('stop') # Tell MctlThread to shut down.
MctlThread.join() # Wait MctlThread to complete.
Mctl.Reset(planned=True) # For safety, reset the microcontroller. This prevents the stepper motors triggering due to out-of-date instructions. 
print (' ')
ShutdownCamera() # Terminate the CameraHandler thread.
print (' ')
GPIO.cleanup() # Reset the GPIO state.
print (textcolor.yellow("Saving parameters..."))
Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
print (textcolor.yellow("Done."))

print (textcolor.fgbgcolor(textcolor.BLACK,textcolor.GREEN," PILOMAR COMPLETE. OK TO SHUTDOWN "))

# Camera settings....
# - From https://github.com/RemovedMoney326/Hubble-Pi/blob/master/HubblePiDocumentation.pdf
#  *) If recording video, you can set the framerate to max 0.005 frames / second-  which results in 200second exposures! See Page 110 of the official guide.
#  *) Developer is also planning an astroguider - using the camera to keep track of the object.
#  *) It uses KStars (free) for sky-guiding. Research this.

