#!/usr/bin/python

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.
# Examples
# - SKYFIELD is issued and used under the "MIT License" terms.
# - HIPPARCOS data is used under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License.
# - JPL data for planet positions will have its own licence.
# - NGC (New General Catalog) data is based upon the Saguaro Astronomy Club Database version 8.1
# - The MESSIER catalog is gathered from multiple sources.
# - The MeteorShower list is based upon the Wikipedia list (2021).
# - Space station data comes from the celestrak.org website (using NORAD public data).
# - The Comet list comes from the Minor Planet Center.

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
# - RaspberryPi microcomputer (V4 2GB or greater)
# - Raspbian BUSTER operating system.
# - Pimoroni Tiny2040 8MB as a microcontroller of the motors
# - Nema 17 stepper motors (0.9degree per full step).
# - DRV8825 stepper motor driver chips.
# - Raspberry Pi High Quality Camera Sensor V1.0
# - Raspberry Pi 16mm 'telephoto' lens.
# - - You can use other lenses, the program will generally try to adapt to the lens length defined in the parameter file, do not exceed 50mm.

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
# *Q* On rare occasions, the camera process can hang completely, it does not complete image capture, requiring a power cycle of the RPi.
#     The cause is not known, but the camera board stops responding. I have read online that power problems to the camera can cause this.
#     This is detected and reported, but this does not recover the situation programmatically.
#     Problem is more rare in builds from 2023 onwards.
# *Q* Some microcontrollers sometimes randomly reset. The software is relatively reset tolerant and recovers automatically, but the cause of the resets is not yet identified.
#     Resets are reported, and generally only cause brief delays while the system recovers.
#     Resets are more common with RPi Pico 2040 and Adafruit Feather 2040.
#     Resets do not occur with Pimoroni Tiny2040.
# *Q* The keyboard scanning routine causes the display to blink sometimes. 
#     If you are sensitive to flashing images you can slow down the keyboard scanning so that the image is more stable, but it will react to keyboard input more slowly.

# Version
# 0.1.1    29.11.2023 Removed out of date references to MotorRunningSeconds.
#                     Stopped eternal looping if recoveryfile write had continuous failure.
#                     MarkupPreview now tolerates older format ngc.json datafile.
# 0.1.2    29.11.2023 Remaining references to onboard LEDs removed as they are not required in the running system, and simplify the PCB build.
#          11.12.2023 ProjectRoot is respected across the program, there were some hardcoded /home/pi directory names still in the code. (GitHub Issue #35)
#          11.12.2023 Min/MaxAltitudeAngle initialisation was wrong. (GitHub Issue #38)
#          18.12.2023 Version validation only considers first 2 elements.
#                     SetMotorAngle() now states current motor angle.
# 0.2.0    13.01.2024 GoToAngle, GoToTarget show progress during large moves.
#          31.01.2024 2024-01-issues items addressed.            

# Version numbering scheme:
#           aa.bb.cc
#           aa = Major version, large changes to functionality. Likely to require major version change on RPi side too.
#           bb = Feature changes, but same overall program. Likely to require functionality change on RPi side too.
#           cc = Bugfix, no feature changes. Will not require changes on RPi side.
VERSION = '0.2.2' # Shared with microcontroller. # Make sure the microcontroller accepts any new version number.
ACCEPTABLECONTROLLERVERSIONS = ['0.0','0.1','0.2','0.3'] # Microcontroller versions that this will work with. Ignore patch level.

# Import required libraries
from typing import Tuple # For type hinting.
import sys # For version verification.
import serial # UART communication with a microcontroller.
import time # sleep functionality for pauses in execution. 
import RPi.GPIO as GPIO # Handling IO signals.
import glob # file system.
import os # OS Command execution.
import math # Math and trig functions. 
import json # json file handling.
import random # random number generator.
import cv2 # openCV for image file handling.  
from pathlib import Path # For navigating folder structure.
import astroalign # Image alignment routines.
from datetime import datetime, timedelta, timezone
from pilomartimer import timer, progresstimer # Pilomar's timer classes.
from pilomarlogfile import logfile # Pilomar's logging class.
from pilomaroscommand import oscommand # Pilomar's OS command executor.
from pilomardisc import discmonitor # Pilomar's disc storage monitor.
from pilomarimage import pilomarimage # Pilomar's IMAGE BUFFER handler (combines numpy, OpenCV and pilomar specific routines)
from pilomarcelestrak import celestrak # Pilomar's CELESTRAK satellite data handler.
from skyfield.api import Star, Topos, EarthSatellite
from skyfield.api import Loader # Create own 'load' functionality by specifying the download directory this way.
from skyfield.api import load_constellation_names 
from skyfield.magnitudelib import planetary_magnitude # Calculate the realtime apparent magnitude of solar system objects.
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
from textcolor import colordisplay # Basic colour character graphics for window display on terminal.
from textcolor import keyboardscanner # Simple non-blocking keyboard scanner.
from textcolor import proceduremenu, optionmenu # Basic menu handlers.
from textcolor import listchooser # Allow user to filter through a list of names.
from pidng.core import RPICAM2DNG # DNG data extraction from RPi camera RAW images. From https://github.com/schoolpost/pidng Needs to be 3.4.6 version. Later versions are not compatible.
import numpy as np # Fast array handling
import pandas # Dataframe handling.
import sep # This is used by astroalign, it is only imported here to flush out any problems with the package. (It has suffered from the classic 'numpy.ndarray size changed' in the past.)
import threading # Run the image capture in a separate thread so that motor movement can continue. *Q* Drift calculation and targetting could also move to separate thread.
from queue import Queue # Use queue mechanism to communicate between ObservationRun and Camera threads because they run in parallel.
print (textcolor.clearforward()) # Clear the screen from the start point forward. 

ReloadData = False # Set this to TRUE to cause the data files to be reloaded from the online resources. Can be set by 'reload' runtime argument too.
ResumeObservation = False # Set this to TRUE to automatically load the previous observation and resume.
StartupClock = None # No initial datetime set for start of program. Means we use the current system clock.
ClockOffset = None # Number of seconds to apply to clocks to make the program appear to run in a different period of time. 

# Extract runtime parameters. (Not currently used...) 
RunArgs = sys.argv[1:] # Ignore 1st argument which is this program name.
if len(RunArgs) > 0:
    print ("Runtime arguments :-")
    for i in RunArgs:
        print('>', i)
        if i == 'reload': ReloadData = True
        elif i == 'resume': ResumeObservation = True
        elif i.startswith('clock='): StartupClock = i.split('=')[1] # Pull ISO8601 format datetime from runtime parameters.
        else: print (textcolor.red('Ignored startup parameter "' + str(i) + '"'))
        
if ReloadData:
    print(textcolor.red("ReloadData triggered. Data files will be reloaded from original sources."))

# ------------------------------------------------------------------------------------------------------

def UTCStringToDatetime(utcvalue) -> datetime:
    """ Accept a UTC string and convert it into datetime. 
        Eg 2023-06-23T04:00:00 
        Regardless of any timezone info, UTC is assumed. """
    try:
        if '.' in utcvalue: utcvalue = utcvalue.split('.')[0] # Remove decimal seconds.
        if utcvalue[-1] != "Z": utcvalue += "Z" # Add missing 'Z' timezone marker.
        dt = datetime.strptime(utcvalue,'%Y-%m-%dT%H:%M:%SZ')
        dt = dt.replace(tzinfo=pytz.UTC) # Add UTC timezone.
    except:
        dt = None
    return dt

# ------------------------------------------------------------------------------------------------------

def NowUTC(real=False) -> datetime: # Many references.
    """ Get system clock as UTC (timezone aware) 
        Microcontroller and Skyfield are operated in UTC vales. 
        All clock-times used in this program use the UTC timestamped clock.
        This should be the only reference to datetime.now() method in the entire
        program. All other uses should refer to this NowUTC() function.
        real=True means that no time offset is applied, you get the true realtime clock value.
        real=False means that any time offset is applied, making the clock run at some other point in time.
        """
    dt = datetime.now(timezone.utc) # Offset supported.
    if real == False and ClockOffset != None: # Can apply time offset.
        dt = dt + timedelta(seconds=ClockOffset)
    return dt

SoftwareStartDatetime = NowUTC()
# print("SoftwareStartDatetime:",SoftwareStartDatetime,"UTC")

# ------------------------------------------------------------------------------------------------------

def SetTimeOffset(starttime=None):
    """ Given a UTC format datetime string, set the clocks to that time. 
        eg 2023-06-23T04:00:00
        This actually calculates a timeoffset which is then applied by all clocks. """
    global ClockOffset
    if starttime != None: # Offset given.
        # Convert string into datetime type.
        dt = UTCStringToDatetime(starttime) # Convert to datetime type.
        if dt != None: # Successful conversion.
            td = dt - datetime.now(timezone.utc) # What's the difference between the clocks.
            ClockOffset = td.total_seconds() # Store offset as total seconds.
        else: # Didn't convert.
            print("SetTimeOffset(",starttime,") Failed to translate into valid datetime. Not changed.")
    else: # Reset the clock offset.
        ClockOffset = None

# ------------------------------------------------------------------------------------------------------

if StartupClock != None:
    textcolor.TextBox(["StartupClock specified " + StartupClock],fg=textcolor.WHITE,bg=textcolor.RED)
    SetTimeOffset(starttime=StartupClock)
else:
    print("Using realtime clock.")

#ProjectRoot = '/home/pi/pilomar' # Where are all the project's folders sitting?
ProjectRoot = str(Path(sys.argv[0]).absolute().parent.parent) # Where are all the project's folders sitting?
print("Project root",ProjectRoot)

RequiredPythonVersion = 3 # Expect python3 to be used.
ActualPythonVersion = sys.version_info.major
if RequiredPythonVersion != ActualPythonVersion:
    print ("*ERROR* This program requires Python" + str(RequiredPythonVersion))
    raise Exception ("This program requires Python version " + str(RequiredPythonVersion))

# ------------------------------------------------------------------------------------------------------

def ClearScreen(): 
    """ Use this to perform a clean wipe of the screen and force display windows to refresh. """
    colordisplay.GlobalForceRedraw() # Force all window buffers to fully redraw.
    print(textcolor.clearscreen()) # Clear screen for refresh.

# ------------------------------------------------------------------------------------------------------

def SourceCode() -> str: 
    """ Return the filename of the source code being executed. """
    return sys.argv[0]

# ------------------------------------------------------------------------------------------------------

ProgramTitle = SourceCode().split('/')[-1].split('.')[0].lower() # Used in display titles and also filenaming to separate different generations of the program.

# ------------------------------------------------------------------------------------------------------

def SourceDate() -> datetime: 
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

print("Current time is:",NowUTC(),' UTC, offset is',ClockOffset,"seconds.")

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

def MctlStringToDatetime(line: str) -> datetime:
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

def SafeName(text: str) -> str:
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

def DictionaryToString(rawdict: dict) -> str:
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

def StringToBool(value: str) -> bool:
    """ Convert a single character representation back into a logical value.
        Convert 'y[es]' or 't[rue]' into True
        Convert everything else False. """
    result = False # Default is FALSE. 
    value = value.lower() # Handle upper and lower case.
    if len(value) > 1: value = value[0] # Consider first character only.
    if value in ['t','y']: result = True 
    return result

# ------------------------------------------------------------------------------------------------------

def HRBytes(bytecount: int) -> str: # Move to textcolor?
    """ Turn a large number into human readable format.
        Turns 1MB etc. (Note: Uses binary definition of 1MB etc.)    """
    try:
        if bytecount >= (1024 ** 4): line = str(round(bytecount / (1024 ** 4),1)) + "Tb"
        elif bytecount >= (1024 ** 3): line = str(round(bytecount / (1024 ** 3),1)) + "Gb"
        elif bytecount >= (1024 ** 2): line = str(round(bytecount / (1024 ** 2),1)) + "Mb"
        elif bytecount >= (1024 ** 1): line = str(round(bytecount / (1024 ** 1),1)) + "Kb"
        else: line = str(bytecount) + "b"
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("HRBytes() failed.") from e # Continue with regular exception stack.
    return line

# ------------------------------------------------------------------------------------------------------

def HRInteger(value: int, uom='', scale=1000, powers=['','K','M','G','T','P','E','Z','Y']) -> str:
    """ Turn a large number into human readable format.
        returns 1GHz, 5.3Mb etc.
        UOM is the unit of measure added to T,G,M,K etc.
        scale is 1000 or 1024 depending what scale you're using.
        - Computer scale is usually 1024,
        - Scientific scale is usually 1000.
        powers = list of the codes for each power. """
    line = str(value) # Don't scale it if the function fails.
    try:
        for i in range(len(powers),-1,-1): # Go through the powers in reverse order.
            divisor = scale ** i
            if value >= divisor: 
                line = str(round(value / divisor,1)) + powers[4]
                break
        line += uom
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("HRInteger() failed.") from e # Continue with regular exception stack.
    return line

# ------------------------------------------------------------------------------------------------------

def HRSeconds(seconds: int) -> str:
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

def UtcTimeStamp() -> str:
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

def HmsFromStamp(timestamp: datetime,dateaware=False) -> str:
    """ Return the HH:MM:SS part of a timestamp as a string.
        Works with datetime input. 
        dateaware = True. If the date is not today, then it shows 'DD HH:MM' instead. """
    result = None
    try:
        if timestamp == None: # Protect from null values.
            result = ""
        else:
            result = str(timestamp)
            if dateaware and timestamp.date() != NowUTC().date(): # The date is not today.
                result = result[8:16] # Extract "DD HH:MM"
            else: # The date is today. Extract "HH:MM:SS"
                result = result.split(" ")[1]
                result = result.split(".")[0]
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("HmsFromStamp() failed.") from e # Continue with regular exception stack.
    return result

# ------------------------------------------------------------------------------------------------------

def Interpolate(inp1,res1,inp2,res2,inp3):
    """ Given inp1 -> res1 and inp2 -> res2 relationship, return res3 for inp3 """
    inpdelta = inp2 - inp1
    resdelta = res2 - res1
    if inpdelta != 0.0: # Input points are different, so result can be calculated.
        res3 = ((inp3 - inp1) * float(resdelta / inpdelta)) + res1
    else: # 2 input points are the same, result is unknown.
        res3 = res1 # Default to first result.
    return res3
    
# ------------------------------------------------------------------------------------------------------

def NowHMS() -> str:
    """ Return current time as formatted string. 
        Returns HH:MM:SS string for the current time (UTC) """
    return HmsFromStamp(NowUTC())

# ------------------------------------------------------------------------------------------------------

def Ts2Datetime(tsvalue):
    """ Convert skyfield time value into datetime value. """
    dtvalue = tsvalue.utc_datetime()
    return dtvalue

# ------------------------------------------------------------------------------------------------------

def Datetime2Ts(dtvalue):
    """ Convert datetime value into skyfield time value. """
    if dtvalue.tzinfo == None: dtvalue = dtvalue.replace(tzinfo=pytz.UTC) # If timezone is not set, assign UTC.
    tsvalue = ts.from_datetime(dtvalue)
    return tsvalue

# ------------------------------------------------------------------------------------------------------

def TsDelta(basets,yyyy=0,mm=0,dd=0,h=0,m=0,s=0):
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

def CompassPoint(value,points=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']):
    """ Convert a degree value into a compass point.
        Default is 16 point compass.
        8 and 4 point compass can be generated by changing the points parameter.
        points=['N','E','S','W']
        or
        points=['N','NE','E','SE','S','SW','W','NW']             . """
    locn = int(round((value / 360) * len(points),0)) % len(points)
    return points[locn]

# ------------------------------------------------------------------------------------------------------

def AngleToHMS(value):
    """ Convert a decimal angle into Hours, Minutes, Seconds. """
    value = 24 * value / 360 # Convert from DEGREES to HOURS.
    h = value // 1 # Integer division. How many whole hours. 
    value = float(value) - h # Fractions of an hour left.
    value = value * 60 # Convert to minutes.
    m = value // 1 # Integer division. How many whole minutes. 
    s = float(value) - m # Fractions of a minute left.
    s = s * 60 # Convert to seconds.
    h = int(h) # return integer rather than float values.
    m = int(m)
    return h, m, s

# ------------------------------------------------------------------------------------------------------

def AngleToDMS(value):
    """ Convert a decimal angle into Degrees, Minutes, Seconds. """
    if value < 0: sign = -1
    else: sign = 1
    value = abs(value) # Strip out sign.
    d = value // 1 # Integer division. How many whole degrees?
    value = float(value) - d # Fractions of an hour left.
    value = value * 60 # Convert to minutes.
    m = value // 1 # Integer division. How many whole minutes. 
    s = float(value) - m # Fractions of a minute left.
    s = s * 60 # Convert to seconds.
    d = int(d * sign) # return integer rather than float values.
    m = int(m * sign)
    s = s * sign
    return d, m, s

# ------------------------------------------------------------------------------------------------------

def HMSToAngle(h,m=None,s=None,invert=True):
    """ Convert hours, minutes, seconds to angle.
        Input values can be decimals, they will be converted correctly. 
        invert = True: minutes and seconds values are made negative if hour value is negative. """
    if invert and h < 0:
        if m > 0: m = -1 * m
        if s > 0: s = -1 * s
    angle = h * 360 / 24 # Convert HOURS to angle.
    if m != None: # Minutes were specified, add those.
        angle += (m / 60) * 360 / 24
    if s != None: # Seconds were specified, add those.
        angle += (s / (60 * 60)) * 360 / 24
    return angle

# ------------------------------------------------------------------------------------------------------

def DMSToAngle(degrees=0.0,minutes=0.0,seconds=0.0):
    """ Convert degrees, minutes and seconds into degrees. """
    # Convert all values relative to 360 degrees.
    minutes = (1 / 60) * float(minutes)
    seconds = (1 / (60 * 60)) * float(seconds)
    value = degrees + minutes + seconds
    return value

# ------------------------------------------------------------------------------------------------------

def DisplayHMS(h,m,s,length=12,rounding=1):
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

def DisplayDegree(value,length=10,zerofill=True,symbol=None):
    """ Display a degree decimal with 3dp and right justified to specified length. 
        length = size of field to return (value right justified)
               = None: Don't fill or justify. 
        zerofill = True: zerofill leading and trailing digits.
        zerofill = False: zerofill only trailing digits. 
        symbol = symbol or text to use as 'degree' unit. """
    if value == None: # No value, just return blank.
        disp = str(value).rjust(length,' ')
    else: # Value, format it.
        if zerofill: # Leading zeros should be filled.
            disp = str(format(abs(value), '07.3f')) # Fill without sign.
            if value < 0: disp = "-" + disp # Add sign back.
        else: # Leading zeros not required.
            disp = str(format(value, '.3f'))
        if symbol != None: disp += symbol
        if length != None: # Field length specified, right justify to fit.
            disp = ((" " * length) + disp)[(-1 * length):]
    return disp

# ------------------------------------------------------------------------------------------------------

def Deg3dp(value,symbol=None):
    """ Turn a degree decimal into a simple zerofilled, 3dp string.

        45.0     -->> 045.000
        -45      -->> -045.000
        
        45,'deg' -->> 045.000deg

    """
    result = DisplayDegree(value,length=None,symbol=symbol)
    if value >= 0:
        result = " " + result # blank space where '+' sign would be.
    return result

# ------------------------------------------------------------------------------------------------------

# During an observation run we need to interrupt the processing. Python doesn't do this natively and
# <ctrl-c> will stop the program brutally, so we use the curses library to provide a keyboard scanner. 
Keyboard = keyboardscanner() # Non-Blocking reader of the keyboard (via curses library). 

# Identify the program and version to the user.
print(textcolor.yellow(SourceCode() + " " + str(SourceDate())))

# Initialize Logging.
logdir = ProjectRoot + "/log"
# Main log file.
LogFileName = logdir + "/" + ProgramTitle + "_" + UtcTimeStamp() + ".log"
print("Main log to", LogFileName)
MainLog = logfile(LogFileName,clockoffset=ClockOffset) # Create a MAIN log file object.

# Camera log file.
CamLogFileName = logdir + "/" + ProgramTitle + "_camera_" + UtcTimeStamp() + ".log"
print("Camera log to", CamLogFileName)
CamLog = logfile(CamLogFileName,clockoffset=ClockOffset) # Create a CAMERA specific log file. (This runs in separate thread, unsure if logging would be thread-safe.)

MainLog.Log("Python version:",sys.version,terminal=False)
MainLog.Log("Main: ReloadData",ReloadData,terminal=False) # Record that 'reload' has been triggered.

MainLog.Log("Startup parameters:", RunArgs,terminal=False)
HistoryFile = ProjectRoot + '/data/' + ProgramTitle + '_sessions.txt' # Chosen observation targets and settings are stored in this file.

# ------------------------------------------------------------------------------------------------------

OSCommand = oscommand(MainLog.Log) # Create OS Command executor. 
osCmd = OSCommand.Execute # Shortcut point to the execution method which returns the output.
osCmdCode = OSCommand.ExecuteCode # Shortcut point to the execution method which returns the termination code.

# ------------------------------------------------------------------------------------------------------

def OSVersion():
    """ Return the version of operating system.
        Returns 
            versionid       eg  10
            versioncodename eg  buster
            ostype          eg  debian
            """
    versionid = None
    versioncodename = None
    ostype = None
    for line in osCmd('cat /etc/os-release'):
        if len(line) > 0:
            elements = line.split('=')
            if elements[0] == 'VERSION_ID': versionid = int(elements[1].replace('"',''))
            elif elements[0] == 'VERSION_CODENAME': versioncodename = elements[1]
            elif elements[0] == 'ID': ostype = elements[1]
    osbits = int(osCmd('getconf LONG_BIT')[0]) # Check 32 vs 64 bit O/S
    osproc = osCmd('uname -m')[0]
    return versionid, versioncodename, ostype, osbits, osproc
            
# ------------------------------------------------------------------------------------------------------

def RPiModel():
    """ Calculate a label for the model of RPI in use. """
    lines = osCmd('cat /sys/firmware/devicetree/base/model')
    rpimodel = 'Raspberry Pi'
    for line in lines:
        if len(line) > 0: rpimodel = line
    rpimodel = rpimodel.replace('Raspberry Pi ','RPi ')
    rpimodel = rpimodel.replace('Model ','')
    rpimodel = rpimodel.replace('Rev ','')
    # Remove non printing characters.
    temp = ''
    for char in rpimodel:
        if char >= ' ': temp += char
    rpimodel = temp 
    rpinum = rpimodel.split(' ')[1] # Pull the '4' out of "RPi 4 B 1.4" format response.
    return rpimodel,rpinum

# ------------------------------------------------------------------------------------------------------

RPIMODEL, RPiNum = RPiModel()
OS_id, OS_name, OS_type, OS_bits, OS_processor = OSVersion()
OS_systemkey = RPiNum + "/" + OS_name + "/" + str(OS_bits)
MainLog.Log("RPi: Model:",RPIMODEL,"Num:",RPiNum,"OStype:",OS_type,"OSid:",OS_id,"OSname:",OS_name,"OSbits:",OS_bits,"OSproc:",OS_processor,"SysKey:",OS_systemkey,terminal=True)
RASPISTILL_SYSTEMS = ['wheezy','jessie','stretch','buster'] # These all came with raspistill for camera support.
SUPPORTED_SYSTEMS = ['3/buster/32','4/buster/32','4/bookworm/64'] # The software is designed to run under these hardware/os combinations.
if OS_name in RASPISTILL_SYSTEMS: CameraDriver = 'raspistill'
else: CameraDriver = 'libcamera' # 'bullseye' and 'bookworm' come with libcamera installed.
MainLog.Log(OS_name,"O/S found, assuming camera driver is",CameraDriver,terminal=False)
if OS_systemkey in SUPPORTED_SYSTEMS:
    MainLog.Log(ProgramTitle,"OK to run under",OS_systemkey,terminal=False)
else: # Cannot proceed, wrong O/S & hardware combination.
    MainLog.Log(ProgramTitle,"is only designed to run under",SUPPORTED_SYSTEMS,level='error',terminal=True)
    MainLog.Log(ProgramTitle,"is not designed to run under",OS_name,OS_bits,"bit on",RPIMODEL,"(",OS_systemkey,")",level='error',terminal=True)
    raise Exception(str(ProgramTitle) + " is not designed to run under this combination of hardware and O/S.")
    
# ------------------------------------------------------------------------------------------------------

# Remove out of date log files to preserve disc space.
print (textcolor.yellow('Removing out of date log files to preserve disc space...'))
# Show what will be deleted.
cmd = "find " + logdir + " -type f -name '" + ProgramTitle + "_*.log' -mtime +2 -print"
linelist = osCmd(cmd)
for line in linelist:
    if len(line) > 0: print(textcolor.orange('Deleting',line))
# Now delete.
cmd = "find " + logdir + " -type f -name '" + ProgramTitle + "_*.log' -mtime +2 -delete"
print(cmd) # Show the user the command being executed.
osCmd(cmd)
print('Done.')

# Log details about the environment.
MainLog.Log("Skyfield version:", SkyfieldVersion, terminal=False)
if SkyfieldVersion[0] > 1 or SkyfieldVersion[1] > 39:
    MainLog.Log("Pilomar is developed with Skyfield version 1.39: This version",str(SkyfieldVersion[0]) + "." + str(SkyfieldVersion[1]),"may not be compatible.",level='warning',terminal=False)

textcolor.GetTermType()
MainLog.Log("Terminal type:", textcolor.TermType, textcolor.Mode,terminal=False)

class attributemaster(): # A parent class containing some common methods that other classes can inherit from.
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
        ignoretypes = [type(np.ndarray),type(self),type(self.SaveToDictionary)]
        for attr, value in vars(self).items():
            if attr[0] == '_': continue # Don't send internals.
            if type(attr) in ignoretypes: continue # Don't export certain variable types.
            if denylist != None and attr in denylist: continue # Blocked item. Don't save.
            if allowlist == None or attr in allowlist: # Allowed item, save.
                if nameprefix != None: attr = nameprefix + attr # Add optional prefix to fieldname.
                confdict[attr] = value
        return confdict

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Parameter settings
# ///////////////////////////////////////////////////////////////////////////////////

class parameters(attributemaster): # Common
    """ Class to load, store and manage parameters for the program.
        The parameters() class allows you to load runtime parameters from a file.
        It can also reload parameters during a run if you want to change them without restarting the program.
        The latest parameter settings are automatically written back to disc when the program closes.
        - So if you change any of these parameters during the run, they will remain active the next time the program is started.
        These parameters are generally those which you may want to modify during development or testing. """

    def __init__(self,filename,log=None):
        if log == None: log = MainLog.Log # Default logging method that is used internally.
        self.Log = log # Handle to the logging method that this object should use. 
        self._Dictionary = {} # The json parameter file loaded from disc at start, saved to disc at end.
        self._Defaults = {} # Maintain a list of default values, used to highlight changes when reviewing parameters.
        self.ParamFileName = filename # The disc copy of the parameter file. This is overwritten if the program completes correctly.
        if os.path.isfile(self.ParamFileName): # If the dictionary file exists, we'll import it now.
            with open(self.ParamFileName,'r') as f:
                self.Log("Loading parameters from file: " + self.ParamFileName)
                self._Dictionary = json.load(f) # Overwrite the default parameter values with anything from file.
        # Pull parameter values from the dictionary, and update the dictionary with defaults if necessary.
        # - Define data about stepper motor driver boards and capabilities.
        sdd = {'drv8825': 
                {'modelist':
                   { '1' : {'power' : 100, 'modesignals' : 'nnn'},
                     '2' : {'power' :  70, 'modesignals' : 'ynn'},
                     '4' : {'power' :  40, 'modesignals' : 'nyn'},
                     '8' : {'power' :  20, 'modesignals' : 'yyn'},
                    '16' : {'power' :  10, 'modesignals' : 'nny'},
                    '32' : {'power' :   5, 'modesignals' : 'yyy'}
                   }
                }
              }
        self.StepperDriverData = self.GetParmVal('StepperDriverData',sdd) # Dictionary containing stepper driver types and parameters.
        self.BoardType = self.GetParmVal('BoardType',None) # Define alternative motorcontroller board type here. Changes behaviour of board/microcontroller.
        self.BatchSize = self.GetParmVal('BatchSize',100) # How many photos to take in a batch.
        self.ControlBatchSize = self.GetParmVal('ControlBatchSize',20) # How many images to capture in each 'control set' (DARK, BIAS etc). High values offer limited gains.
        self.ColorScheme = self.GetParmVal('ColorScheme','green') # What colour scheme to use? (green, blue, red, white)
        
        # The following parameters control hardware features.
        #self.MotorsEnabled = self.GetParmVal('MotorsEnabled',True) # Are the motors to be powered on?
        self.CameraEnabled = self.GetParmVal('CameraEnabled',True) # Is the camera on?
        self.DisableCleanup = self.GetParmVal('DisableCleanup',True) # Set to TRUE to disable the on-chip cleanup. (More pure RAW image is captured.)
        self.BacklashEnabled = self.GetParmVal('BacklashEnabled',False) # ENABLE to let the motors make extra moves to cope with gear backlash.
        self.FaultSensitive = self.GetParmVal('FaultSensitive',False) # ENABLE to make motorcontroller respect the DRV8825 'fault' signal.
        self.MctlLedStatus = self.GetParmVal('MctlLedStatus',True) # Turn on STATUS LEDs on microcontroller.
        self.ObservationResetsMctl = self.GetParmVal('ObservationResetsMctl',False) # Force a reset of the microcontroller each time a new ObservationRun begins?
        self.MctlResetPin = self.GetParmVal('MctlResetPin',4) # Which RPi4 GPIO pin is used to RESET the microcontroller?
        self.UartRxQueueLimit = self.GetParmVal('UartRxQueueLimit',50) # How many messages can be held in the input queue from the Microcontroller? Kill older entries.
        # Azimuth motor parameters.
        self.MinAzimuthAngle = self.GetParmVal('MinAzimuthAngle',0)
        self.MaxAzimuthAngle = min(self.GetParmVal('MaxAzimuthAngle',360),360)
        self.AzimuthDriver = self.GetParmVal('AzimuthDriver','drv8825') # Which steppermotor driver does the Azimuth motor use?
        self.AzimuthGearRatio = self.GetParmVal('AzimuthGearRatio',240)
        self.AzimuthMotorStepsPerRev = self.GetParmVal('AzimuthMotorStepsPerRev',400) # Full step count for the motor (ignore any microstepping multiplier)
        #self.AzimuthModeSignals = self.GetParmVal('AzimuthModeSignals',[False,False,False]) # How are the 3 mode pins set?
        self.AzimuthMicrostepRatio = self.GetParmVal('AzimuthMicrostepRatio',1) # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.AzimuthRestAngle = self.GetParmVal('AzimuthRestAngle',180.0)
        self.AzimuthBacklashAngle = self.GetParmVal('AzimuthBacklashAngle',0.0)
        self.AzimuthOrientation = self.GetParmVal('AzimuthOrientation',-1)
        self.AzimuthLimitAngle = self.GetParmVal('AzimuthLimitAngle',None) # Set motion limit for rotation.
        # Altitude motor parameters.
        self.MinAltitudeAngle = self.GetParmVal('MinAltitudeAngle',0) # Fixed Issue #38
        self.MaxAltitudeAngle = min(self.GetParmVal('MaxAltitudeAngle',90),90) # Fixed Issue #38
        self.AltitudeDriver = self.GetParmVal('AltitudeDriver','drv8825') # Which steppermotor driver does the Altitude motor use?
        self.AltitudeGearRatio = self.GetParmVal('AltitudeGearRatio',240)
        self.AltitudeMotorStepsPerRev = self.GetParmVal('AltitudeMotorStepsPerRev',400) # Full step count for the motor (ignore any microstepping multiplier)
        #self.AltitudeModeSignals = self.GetParmVal('AltitudeModeSignals',[False,False,False]) # How are the 3 mode pins set?
        self.AltitudeMicrostepRatio = self.GetParmVal('AltitudeMicrostepRatio',1) # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.AltitudeRestAngle = self.GetParmVal('AltitudeRestAngle',0.0)
        self.AltitudeBacklashAngle = self.GetParmVal('AltitudeBacklashAngle',0.0)
        self.AltitudeOrientation = self.GetParmVal('AltitudeOrientation',-1)
        self.AltitudeLimitAngle = self.GetParmVal('AltitudeLimitAngle',None) # Set motion limit for rotation.
        # Motor pulse speed and acceleration (applies to both motors)
        self.FastTime = self.GetParmVal('FastTime',0.002) # Fastest pulse to the motor STEP signal. (Full speed in large move.) # Was 0.0005
        self.SlowTime = self.GetParmVal('SlowTime',0.05) # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
        self.TimeDelta = self.GetParmVal('TimeDelta',0.003) # Acceleration rate for the motor STEP signal. 

        #self.UseMicrostepping = self.GetParmVal('UseMicrostepping',False) # Do we let the motors use microstepping for fine position control at the cost of lower torque?
        self.MotorStatusDelay = self.GetParmVal('MotorStatusDelay',10) # Microcontroller should send motor status messages every 'xxx' seconds. (Don't overload UART comms!)
        self.OptimiseMoves = self.GetParmVal('OptimiseMoves',False) # Can the motorcontroller optimise large moves? (ie switch direction if it's faster)
        if self.OptimiseMoves: # If allowed to optimise moves, warn the user.
            lines = [
               "OptimiseMoves parameter is enabled.",
               "The telescope has more  flexibility  about how it moves.",
               "Take care that continuous rotation in the same direction",
               "may eventually twist the power cables.",
               "It is  recommended  to check the cables are untangled at",
               "the start of each observation session."               
            ]
            textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.ORANGERED1)
        self.MctlCommsTimeout = self.GetParmVal('MctlCommsTimeout',120) # How many seconds of inactivity before resetting microcontroller communication?
        self.UseUSBStorage = self.GetParmVal('UseUSBStorage',True) # If USB storage is mounted then images are stored there instead of the SD card.
        self.SDPath = self.GetParmVal('SDPath','/') # The 'path' used by discmonitor for monitoring space on the SD card.
        self.USBPath = self.GetParmVal('USBPath','/media/pi') # The 'path' used by discmonitor for monitoring space on attached USB storage.

        # The following parameters control how bright the stars are if they are selected in the LocalStars or ConstellationStars lists.
        self.LocalStarsMagnitude = self.GetParmVal('LocalStarsMagnitude',7.0) # Max magnitude when selecting local stars.
        self.ConstellationStarsMagnitude = self.GetParmVal('ConstellationStarsMagnitude',7.0) # Max magnitude when selecting stars in a constellation.

        # The following parameters decide which types of images are stored.
        self.CameraSaveJpg = self.GetParmVal('CameraSaveJpg',True) # Save the jpg image from observations, but will strip out the embedded RAW data.
        self.CameraSaveDng = self.GetParmVal('CameraSaveDng',True) # Save the raw image data as .dng file.
        if self.CameraSaveJpg or self.CameraSaveDng: pass # OK
        else: self.Log("No image types are saved according to the parameters.",level='warning')
        
        if CameraDriver == 'raspistill': # These are the default commands for raspistill captures.
            self.CameraLightCommand = self.GetParmVal('CameraLightCommand',
                'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}') # Camera settings for 'light' images.
            self.CameraDarkCommand = self.GetParmVal('CameraDarkCommand',
                'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}') # Camera settings for 'dark' images.
            self.CameraBiasCommand = self.GetParmVal('CameraBiasCommand',
                'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}') # Camera settings for 'bias' images.
            self.CameraFlatCommand = self.GetParmVal('CameraFlatCommand',
                'raspistill -o {&output} -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0') # Camera settings for 'flat' images.
            self.CameraDarkFlatCommand = self.GetParmVal('CameraDarkFlatCommand',
                'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}') # Camera settings for 'darkflat' images.
            self.CameraAutoCommand = self.GetParmVal('CameraAutoCommand',
                'raspistill -o {&output} -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height}') # Camera settings for 'auto' images.
            self.CameraTrackingCommand = self.GetParmVal('CameraTrackingCommand',
                'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ss {&shutter}') # Camera settings for 'tracking' images.
            self.CameraRawSwitch = self.GetParmVal('CameraRawSwitch','-r') # How do you turn on RAW image extraction?
        else: # These are the default Commands for libcamera-still captures.
            self.CameraLightCommand = self.GetParmVal('CameraLightCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}') # Camera settings for 'light' images.
            self.CameraDarkCommand = self.GetParmVal('CameraDarkCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}') # Camera settings for 'dark' images.            
            self.CameraBiasCommand = self.GetParmVal('CameraBiasCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}') # Camera settings for 'bias' images.
            self.CameraFlatCommand = self.GetParmVal('CameraFlatCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0') # Camera settings for 'flat' images.
            self.CameraDarkFlatCommand = self.GetParmVal('CameraDarkFlatCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}') # Camera settings for 'darkflat' images.
            self.CameraAutoCommand = self.GetParmVal('CameraAutoCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off') # Camera settings for 'auto' images.
            self.CameraTrackingCommand = self.GetParmVal('CameraTrackingCommand',
                'libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --shutter {&shutter}') # Camera settings for 'tracking' images.
            self.CameraRawSwitch = self.GetParmVal('CameraRawSwitch','--raw') # How do you turn on RAW image extraction?

        # The following parameters control DriftTracking activity.
        self.UseTracking = self.GetParmVal('UseTracking',True) # TRUE = Use image tracking. FALSE = No tracking.
        # LatestTrackingFilter and RunFilterScript are new features being tested. If used, they override PrepImagesForTracking and TrackingUrbanFilter parameters.
        self.TrackingTargetGrayscale = self.GetParmVal('TrackingTargetGrayscale',False) # Generate grayscale tracking target?
        # The following 2 parameters are replaced by the general purpose LatestTrackingFilter parameter. This upgrades automatically.
        PrepImagesForTracking = self.GetParmVal('PrepImagesForTracking',False) # TRUE = latest image is simplified. FALSE = latest image is used as is.
        TrackingUrbanFilter = self.GetParmVal('TrackingUrbanFilter',False) # Apply the 'UrbanFilter' method to live images before passing to the drift tracking calculation.
        self.LatestTrackingFilter = self.GetParmVal("LatestTrackingFilter",None) # Which (if any) script is run through pilomarimage.RunFilterScript() when LATEST tracking images are taken.
        if self.LatestTrackingFilter == None: # No LatestTrackingFilter is set. Look for old parameters to upgrade.
            if PrepImagesForTracking: # The old PrepImagesForTracking was in use, convert this to the EnhanceStars filter script.
                self.LatestTrackingFilter = 'EnhanceStars' # This is the equivalent to the previous behaviour.
                self.Log("parameters.__init__(): Upgrading old PrepImagesForTracking parameter to new LatestTrackingFilter parameter.",terminal=True)
            elif TrackingUrbanFilter: # The old TrackingUrbanFilter was in use, convert this to the UrbanFilter script.
                self.LatestTrackingFilter = 'UrbanFilter'
                self.Log("parameters.__init__(): Upgrading old TrackingUrbanFilter parameter to new LatestTrackingFilter parameter.",terminal=True)
        self.TrackingPrediction = self.GetParmVal('TrackingPrediction',False) # Adjust tracking offsets by the elapsed time. Predicting a new offset.
        self.TrackingMatchThreshold = self.GetParmVal('TrackingMatchThreshold',5) # Minimum number of stars that must be matched before drift calculation is trusted.
        self.MinimumDriftCorrection = self.GetParmVal('MinimumDriftCorrection',50) # Minimum number of drift pixels that's worth compensating. Doesn't need to be too small.
        self.TrackingInterval = self.GetParmVal('TrackingInterval',600) # How many seconds between each target tracking check?
        self.TrackingStarRadius = self.GetParmVal('TrackingStarRadius',3) # Pixel radius of stars in clean targetting images.
        self.TrackingExposureSeconds = self.GetParmVal('TrackingExposureSeconds',5.0) # How long is the exposure when capturing a tracking photo. It must be standardised rather than using the variable 'light' image exposure time.
        self.GeneratePreview = self.GetParmVal('GeneratePreview',True) # TRUE = Preview images are generated periodically, and can be turned into AVI file when observation ends.
        self.InitialGoTo = self.GetParmVal('InitialGoTo',True) # Perform initial GOTO before downloading the trajectory. (Eases comms with microcontroller.)
        self.TargetInclusionRadius = self.GetParmVal('TargetInclusionRadius',15) # Angle (radius) for inclusion of neighbouring stars when generating target image.
        self.TargetMinMagnitude = self.GetParmVal('TargetMinMagnitude',7.0) # Minimum magnitude for stars to display. At a 2 second exposure, Magnitude 5.0 is a good value, at 5 seconds, Mag 9, over 10 seconds, Mag 10 is about as good as it gets.
        self.UseLiveLocation = self.GetParmVal('UseLiveLocation',True) # Use live target location rather than last reported location for image processing.
        self.DebugMode = self.GetParmVal('DebugMode',True) # In DebugMode ObservationRun does not display the status windows. This makes error messages easier to read.
        self.KeyboardScanDelay = self.GetParmVal('KeyboardScanDelay',2) # How many seconds between keyboard scans when running an observation?

        # Warn if magnitude limits are incorrectly set.
        if self.TargetMinMagnitude > self.LocalStarsMagnitude:
            self.Log("parameters.__init__(): TargetMinMagnitude",self.TargetMinMagnitude,"is dimmer than stars listed in Hipparcos catalog (",self.LocalStarsMagnitude,").",level='warning',terminal=True)

        # The following parameters set position and localisation.
        self.LocalTZ = self.GetParmVal('LocalTZ','Europe/London') # What's the local timezone (pytz values). pytz.all_timezones() lists all available. Info only at present.
        self.HomeLat = self.GetParmVal('HomeLat',None) # Latitude of the observer.
        self.HomeLon = self.GetParmVal('HomeLon',None) # Longitude of the observer.
        self._HomeLatVal = 0.0
        if self.HomeLat != None:
            self._HomeLatVal = float(self.HomeLat.split(" ")[0]) # Convert to float value.
            if self.HomeLat.split(" ")[1] == "S": self._HomeLatVal = self._HomeLatVal * -1 # -ve for southern hemisphere in Skyfield.
        self._HomeLonVal = 0.0
        if self.HomeLon != None:
            self._HomeLonVal = float(self.HomeLon.split(" ")[0]) # Convert to float value.
            if self.HomeLon.split(" ")[1] == "W": self._HomeLonVal = self._HomeLonVal * -1 # -ve for western hemisphere in Skyfield.
        self.Log("Parameters: Home:", self.HomeLat, self.HomeLon, ":", self._HomeLatVal, self._HomeLonVal,terminal=False)
        
        # The following parameters dictate how various graphical images are generated.
        self.MarkupInterval = self.GetParmVal('MarkupInterval',300) # How often do we generate a preview image (seconds).
        self.MarkupShowLabels = self.GetParmVal('MarkupShowLabels',True) # Add labels to markup images, such as locations.
        self.MarkupShowNames = self.GetParmVal('MarkupShowNames',True) # Add names to markup images, such as star names.
        self.MarkupStarLabelLimit = self.GetParmVal('MarkupStarLabelLimit',100) # Maximum number of star labels to add to the image. Keep it readable.
        self.MarkupAvoidCollisions = self.GetParmVal('MarkupAvoidCollisions',False) # Does image markup avoid text overlaps?
        
        # The following parameters describe the camera and lens.
        self.LensLength = self.GetParmVal('LensLength',16.0) # Focal length of lens
        self.LensHorizontalFov = self.GetParmVal('LensHorizontalFov',21.8) # Degrees FoV horizontally
        self.LensVerticalFov = self.GetParmVal('LensVerticalFov',16.4) # Degrees FoV vertically.
        self.SensorType = self.GetParmVal('SensorType','imx477') # Sensor type. 
        self.IRFilter = self.GetParmVal('IRFilter',True) # Is Infra Red filter fitted?
        self.PollutionFilter = self.GetParmVal('PollutionFilter',False) # Is light pollution filter fitted?
        
        # The following parameters dictate how the trajectory is calculated for the motorcontroller.
        self.TrajectoryWindow = self.GetParmVal('TrajectoryWindow',1200) # How many seconds into the future should the motor trajectory last?
        self.UseDynamicTrajectoryPeriods = self.GetParmVal('UseDynamicTrajectoryPeriods',True) # Can we use flexible time periods in the trajectory plan?
        
        # The following parameters dictate the color scheme for the user interface.
        # Display colorscheme.
        self.MenuTitleFG = self.GetParmVal('MenuTitleFG',textcolor.LIME)
        self.MenuTitleBG = self.GetParmVal('MenuTitleBG',textcolor.DARKGREEN)
        self.MenuSubtitleFG = self.GetParmVal('MenuSubtitleFG',textcolor.BLACK)
        self.MenuSubtitleBG = self.GetParmVal('MenuSubtitleBG',textcolor.GREEN)
        # - ObservationStatusWindow
        self.TitleFG = self.GetParmVal('TitleFG',textcolor.LIME)
        self.TitleBG = self.GetParmVal('TitleBG',textcolor.DARKGREEN)
        self.TextFG = self.GetParmVal('TextFG',textcolor.GREEN)
        self.TextBG = self.GetParmVal('TextBG',textcolor.BLACK)
        self.TextGood = self.GetParmVal('TextGood',textcolor.LIGHTGREEN)
        self.TextPoor = self.GetParmVal('TextPoor',textcolor.YELLOW)
        self.TextBad = self.GetParmVal('TextBad',textcolor.ORANGERED1)
        self.BorderFG = self.GetParmVal('BorderFG',textcolor.DARKGREEN)
        self.BorderBG = self.GetParmVal('BorderBG',textcolor.BLACK)
        self.SetColorScheme(self.ColorScheme)

        self.ScanForMeteors = self.GetParmVal('ScanForMeteors',True) # Scan light images for streaks, report them if found.
        self.MinSatelliteAltitude = self.GetParmVal('MinSatelliteAltitude',30) # Satellite's are only considered to RISE if they will culminate above this altitude. (Else too brief and low to see)
        # Load/Save image filters for pilomarimage objects.
        self.FilterScripts = self.GetParmVal('FilterScripts',pilomarimage.FILTERSCRIPTS) # Default is the initial set of filter scripts defined in the pilomarimage class.
        pilomarimage.FILTERSCRIPTS = self.FilterScripts # Now assign whatever we have loaded back to pilomarimage.
        
    def GetParmVal(self,name,default,oldnames=None):
        """ Get a value from the parameter file. 
        
            name: The parameter name.
            default: The default parameter value if it is not in the dictionary yet.
            oldnames: optional list of previous parameter names, these are used to migrate values from old parameter names to new ones.
            
            If the value does not exist, create it with the default value. 
            If the value is different to the default value, report that in the log file. """
        self._Defaults[name] = default # Maintain a list of default values, used to highlight changes when reviewing parameters.
        result = default
        if type(oldnames) == list: # Check for earlier parameter values.
            for oldname in oldnames: # Check each name in turn.
                if oldname in self._Dictionary: # oldname exists in the dictionary (can migrate from oldname to new name).
                    result = self._Dictionary[oldname] # Retrieve the value from the oldname entry.
                    if self.Log != None: self.Log("parameters.GetParmVal(",name,") migrating from",oldname,"with value",result,terminal=False)
                    break # Look no further.
        # Now get/initialise the current parameter name.
        result = self._Dictionary.get(name,result)
        if result != default: # Default value has been overridden.
            if self.Log != None: self.Log("parameters.GetParmVal(",name,") default",default,"overridden with",result,terminal=False)
        return result
               
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
                print ('Setting',ChosenItem,Result)
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
            self.TextFG = textcolor.WHITE
            self.TextBG = textcolor.BLACK
            self.TextGood = textcolor.WHITE
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.RED
            self.BorderFG = textcolor.GREY66
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
        print (textcolor.yellow("List parameters",ProgramTitle,VERSION,":"))
        print (textcolor.red("(*)"),"indicates a modified parameter value.")
        tempd = vars(self) # Load instance variables into a temporary dictionary.
        for key,value in tempd.items():
            if key.startswith('_'): continue # Ignore internals.
            if key == 'Log': continue # Ignore the link to the Log instance.
            defaultflag = '' # Mark if the value is not the default.
            if type(value) == dict: # Don't show dictionaries, they can be large.
                if key in self._Defaults: # A default value is known. 
                    if self._Defaults[key] != value: # The default is different to the current value.
                        defaultflag = textcolor.red(' (*) Has changed from default.')
                print (textcolor.yellow(key.rjust(30)) + " : dictionary " + defaultflag + "(for detail open in editor)")
            else:
                if key in self._Defaults: # A default value is known.
                    if self._Defaults[key] != value: # The default is different to the current value.
                        defaultflag = textcolor.red(' (*) Was ' + str(self._Defaults[key]))
                print (textcolor.yellow(key.rjust(30)) + " : " + str(value) + defaultflag)
        input(textcolor.cyan("Press [enter] to continue:"))

# Establish the filename of the parameters file that will be loaded.
ParameterFileName = ProjectRoot + '/data/' + ProgramTitle + '_params.json'
Parameters = parameters(filename=ParameterFileName,log=MainLog.Log) # Create and load parameters.

if Parameters.HomeLat == None or Parameters.HomeLon == None:
    # Home location is not yet set. Save the parameter file for editing then quit.
    # The user has to manually enter the home latitude and longitude into the paramter file.
    Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
    lines = ['Home location is not set in ' + Parameters.ParamFileName,
             ' ',
             'Edit the HomeLat and HomeLon values in the parameter file.',
             'Give the co-ordinates of your location.',
             'Then restart this program.']
    textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.RED)
    print(' ')
    print(textcolor.yellow('Eg: Paris, France :'))
    print(textcolor.yellow('            "HomeLat" : "48.864716 N",'))
    print(textcolor.yellow('            "HomeLon" : "2.349014 E",'))
    print(' ')
    print(textcolor.yellow('    Atlanta, USA :'))
    print(textcolor.yellow('            "HomeLat" : "33.753746 N",'))
    print(textcolor.yellow('            "HomeLon" : "84.386330 W",'))
    print(' ')
    print(textcolor.yellow('    Tokyo, Japan :'))
    print(textcolor.yellow('            "HomeLat" : "35.652832 N",'))
    print(textcolor.yellow('            "HomeLon" : "139.839478 E",'))
    print(' ')
    print(textcolor.yellow('    Alice Springs, Australia :'))
    print(textcolor.yellow('            "HomeLat" : "23.8102 S",'))
    print(textcolor.yellow('            "HomeLon" : "133.9026 E",'))
    print(' ')
    exit() # Quit the program.
    
if Parameters._HomeLatVal < 0: # We're in the Southern Hemisphere. The software isn't tested for that.
    linelist = ["Home Latitude (" + str(Parameters._HomeLatVal) + ") is in the Southern Hemisphere.",
                "NOTE: Pi-lomar may perform an unwinding manoeuvre as targets pass through due North.",
                "      This is normal behaviour, but will pause image capture while it happens."]
    textcolor.TextBox(linelist,fg=textcolor.YELLOW,bg=textcolor.BLACK)
    # exit() # Quit the program.
if Parameters._HomeLatVal >= 90.0: # Things break down at the poles.
    linelist = ["Home Latitude (" + str(Parameters._HomeLatVal) + ") is the North Pole.",
                "Please use the 0deg longitude line as due South."]
    textcolor.TextBox(linelist,fg=textcolor.WHITE,bg=textcolor.RED)

# Create global timers.
PreviewTimer = timer(period=Parameters.MarkupInterval) # ObservationRun will generate a Preview image every nnn seconds. 

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
BGRLightBlue = (230,216,173)
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

# ------------------------------------------------------------------------------------------------------

# Create a timer for the keyboard scanner.
KeyboardTimer = timer(period=Parameters.KeyboardScanDelay) # This says how frequently the keyboard is checked for input during observations.

# ------------------------------------------------------------------------------------------------------

def UTCtoLocal(dt: datetime) -> datetime:
    """ Convert a timezone aware datetime into the local timezone. 
        Will only convert the timezone if the value is timezone aware.
        If the timezone is missing (naive) then nothing changes. """
    if dt.tzinfo != None: dt = dt.astimezone(pytz.timezone(Parameters.LocalTZ))
    return dt

# ------------------------------------------------------------------------------------------------------

def NowLocal(real=False) -> datetime: # Many references.
    """ Get system clock in local timezone. 
        Microcontroller and Skyfield are operated in UTC vales. 
        All clock-times used in this program use the UTC timestamped clock.
        But this can return the current timestamp in local time for user displays etc.
        real=True means that no time offset is applied, you get the true realtime clock value.
        real=False means that any time offset is applied, making the clock run at some other point in time.
        """
    dt = UTCtoLocal(NowUTC(real=real)) # Offset supported, Convert to local timezone.
    if real == False and ClockOffset != None: # Can apply time offset.
        dt = dt + timedelta(seconds=ClockOffset)
    return dt

# ------------------------------------------------------------------------------------------------------


def LocaltoUTC(dt: datetime) -> datetime:
    """ Convert a timezone aware datetime into UTC timezone. 
        Will only convert the timezone if the value is timezone aware.
        If the timezone is missing (naive) then nothing changes. """
    if dt.tzinfo != None: dt = dt.astimezone(pytz.timezone('UTC'))
    return dt


# ------------------------------------------------------------------------------------------------------

dt = NowUTC()
print('Current UTC time is:',dt)
dt = UTCtoLocal(dt)
print('Local time is:',dt)

# ///////////////////////////////////////////////////////////////////////////////////
# Trigonometry functions.
# ///////////////////////////////////////////////////////////////////////////////////

def AltAzToXYZ(alt: float, az: float, distance:float =1.0) -> Tuple[float, float, float]:
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

def XYZToAltAz(x:float, y:float, z:float) -> Tuple[float, float]:
    """ Convert 3D coordinates into altitude and azimuth. """
    try:
        range = math.sqrt(x * x + y * y)
        alt = math.degrees(math.atan2(z,range))
        az = math.degrees(math.atan2(x,y)) % 360
    except Exception as e:
        MainLog.RaiseException(e,comment='XYZToAltAz') # Trap all the exception information in the main log file.
    return alt, az

# ------------------------------------------------------------------------------------------------------

def RelativeAltAz(StarAlt,StarAz,LookAtAlt,LookAtAz):
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

def PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width):
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

# ------------------------------------------------------------------------------------------------------

def AzAltText(az,alt,symbol=None) -> str:
    """ Return standardised string of Altitude and Azimuth coordinates. """
    if symbol == None: symbol = DegreeSymbol
    return "az: " + Deg3dp(az) + symbol + " alt: " + Deg3dp(alt) + symbol

# ------------------------------------------------------------------------------------------------------

def RaDecText(radeg,decdeg,symbol=None):
    th, tm, ts = AngleToHMS(radeg) # Convert deg to hms.
    temp = DisplayHMS(th,tm,ts).strip() # Convert to string.
    return "RA: " + temp + " Dec: " + Deg3dp(decdeg) + symbol # Return entire string.

# ------------------------------------------------------------------------------------------------------

def GetTerminalSize():
    """ Return tuple of the current screen dimensions. (cols,rows) 
        This is used to dynamically build the ObservationRun display. 
        More information can be shown if the screen is large enough,
        but the system still works on a relatively small display space. """
    return textcolor.terminalsize() # returns (cols,rows)

# ------------------------------------------------------------------------------------------------------

#SDCardMonitor = discmonitor(name='root',devname='/dev/root',path='/',disctype='boot',logger=MainLog.Log) # Create new disc space monitor for the SD card.
SDCardMonitor = discmonitor(name='root',devname='/dev/root',path=Parameters.SDPath,disctype='boot',logger=MainLog.Log) # Create new disc space monitor for the SD card.

# Use discmonitor to find any potential USB memory too.
def ChooseUSBMemory():
    """ If a USB memory stick is attached, find it. """
    usbdev = None # Default USB memory device.
    UsbList = SDCardMonitor.ListUSBdevices() # List all the potential devices.
    for dn,dl in UsbList:
        MainLog.Log("ChooseUSBMemory: Considering:",dn,dl,terminal=False)
        if dl in SDCardMonitor.USBAlarmLabels: # This device signifies a problem! Proceed no further.
            MainLog.Log("ChooseUSBMemory: Suspect the microcontroller is also connected via USB (",dn,dl,").",terminal=False)
        else:
            MainLog.Log("ChooseUSBMemory: Selecting:",dn,dl,terminal=False)
            usbdev = dn # Try this device as the USB memory.
    MainLog.Log("ChooseUSBMemory: Chosen",usbdev,terminal=False)
    return usbdev
    
usbdev = ChooseUSBMemory()     
#USBDiscMonitor = discmonitor(name='usb',devname=usbdev,path='/media/pi',disctype='usb',logger=MainLog.Log) # Create USB memory card monitor (if it exists).
USBDiscMonitor = discmonitor(name='usb',devname=usbdev,path=Parameters.USBPath,disctype='usb',logger=MainLog.Log) # Create USB memory card monitor (if it exists).
# Decide which of the two above monitors will be the one that images are stored in. Create a pointer to that one for the status monitoring later on.
if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable: 
    MainLog.Log("Initial: Using USB storage for images.",USBDiscMonitor.DfPath,terminal=True)
    ImageStorageMonitor = USBDiscMonitor # Point to USB storage when checking available space.
else: 
    MainLog.Log("Initial: Using SD card for images.",SDCardMonitor.DfPath,terminal=True)
    ImageStorageMonitor = SDCardMonitor # Point to the SD card storage when checking available space.

# ------------------------------------------------------------------------------------------------------

def RecheckDisc():
    """ This will reset/recheck disc availability.
        Useful if USB memory stick didn't mount first time, or if it's added while the system's running. """
    global SDCardMonitor
    global USBDiscMonitor
    global ImageStorageMonitor
    SDCardMonitor = discmonitor(name='root',devname='/dev/root',path='/',disctype='boot',logger=MainLog.Log) # Create new disc space monitor for the SD card.
    usbdev = ChooseUSBMemory()
    USBDiscMonitor = discmonitor(name='usb',devname=usbdev,path='/media/pi',disctype='usb',logger=MainLog.Log) # Create USB memory card monitor (if it exists).
    # Decide which of the two above monitors will be the one that images are stored in. Create a pointer to that one for the status monitoring later on.
    if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable: 
        MainLog.Log("RecheckDisc: Using USB storage for images.",USBDiscMonitor.DfPath,terminal=True)
        ImageStorageMonitor = USBDiscMonitor # Point to USB storage when checking available space.
    else: 
        MainLog.Log("RecheckDisc: Using SD card for images.",SDCardMonitor.DfPath,terminal=True)
        ImageStorageMonitor = SDCardMonitor # Point to the SD card storage when checking available space.
    return True

# ------------------------------------------------------------------------------------------------------

def IsFloat(text) -> bool:
    """ Return TRUE if a string can be converted to a float value. """
    try:
        _ = float(text)
        return True
    except ValueError:
        return False

# ------------------------------------------------------------------------------------------------------

def IsInt(text) -> bool:
    """ Return TRUE if a string can be converted to an integer value. """
    try:
        _ = int(text)
        return True
    except ValueError:
        return False

# ------------------------------------------------------------------------------------------------------

def TextToInt(text) -> int:
    """ Convert a character string into an INTEGER value.
        Returns None if it can't be done. """
    try:
        a = int(text)
    except ValueError:
        a = None
    return a

# ------------------------------------------------------------------------------------------------------

def TextToFloat(text) -> float:
    """ Convert a character string into a FLOAT value.
        Returns None if it can't be done. """
    try:
        a = float(text)
    except ValueError:
        a = None
    return a

# ------------------------------------------------------------------------------------------------------

def VerifyFolder(FN):
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
            osCmd(cmd) 
            cmd = "chown pi:pi " + FN # Make sure that the directory's owner is the pi user.
            osCmd(cmd) 
            cmd = "chmod +w " + FN # Make sure there is write access to the directory.
            osCmd(cmd) 
            result = True
    except Exception as e:
        MainLog.ReportException(e,comment='VerifyFolder') # Trap all the exception information in the main log file.
    return result
    
# ------------------------------------------------------------------------------------------------------

def CreateFolderList(campaign_name,exposure=None):
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
    VerifyFolder(FL["campaign"])
    
    FL["temp"] = ProjectRoot + "/temp/" # Temporary folder for experiments.
    VerifyFolder(FL["temp"])
    
    FL["session"] = imageroot + session # The folder for an individual session.
    VerifyFolder(FL["session"])
    
    FL["tracking"] = imageroot + session + "tracking/" # This is the folder where tracking images are stored.
    VerifyFolder(FL["tracking"])
    
    FL["auto"] = imageroot + session + "auto/" # This is the folder where automatic images are stored (Normally during commissioning).
    VerifyFolder(FL["auto"])
    
    FL["dark"] = imageroot + session + "dark/" # The Pi-lomar folder for the DARK images.
    VerifyFolder(FL["dark"])
    
    FL["darkflat"] = imageroot + session + "darkflat/" # The folder for the DARK FLAT images.
    VerifyFolder(FL["darkflat"])
    
    FL["light"] = imageroot + session + "light/" # The Pi-lomar folder for the LIGHT images. (The actual observations)
    VerifyFolder(FL["light"])
    
    FL["flat"] = imageroot + session + "flat/" # The Pi-lomar folder for the FLAT images.
    VerifyFolder(FL["flat"])
    
    FL["bias"] = imageroot + session + "bias/" # The Pi-Lomar folder for the BIAS/OFFSET images.
    VerifyFolder(FL["bias"])
    
    FL["preview"] = imageroot + session + "preview/" # The folder for the PREVIEW images.
    VerifyFolder(FL["preview"])
    
    MainLog.Log("CreateFolderList:",str(FL),terminal=False)
    return FL

# ------------------------------------------------------------------------------------------------------

def AskYesNo(text,default=True,fg=None,bg=None):
    """ Ask any question that needs a simple Y/N answer.
        Returns logical value ('yes' or 'true' returns True, 'no' or 'false' returns False)
        Returns default value if user just presses ENTER. 
        Ignores 2nd and subsequent characters.
        Rejects all other input. """
    while True: # Loop until a satisfactory answer is given.
        if fg == None: # Use default color.
            temp = input(textcolor.cyan(text.strip() + " ")) # Ensure 1 character space between text and response cursor.
        else:
            temp = input(textcolor.fgbgcolor(fg,bg,text.strip() + " "))
        if len(temp) == 0:
            result = default
            break
        elif temp.lower()[0] in ["n"]: # FALSE and NO recognised.
            result = False
            break
        elif temp.lower()[0] in ["y"]: # TRUE and YES recognised.
            result = True
            break
        print(textcolor.red("? " + str(temp) + " ?"))
        if default: print (textcolor.red("Please answer yes, no or [ENTER]=(YES)"))
        else: print (textcolor.red("Please answer yes, no or [ENTER]=(NO)"))
    return result

# ------------------------------------------------------------------------------------------------------

if Parameters.UseLiveLocation: # Using live target location to process images and maps.
    MainLog.Log("Using live target location to align images and maps.",terminal=False)
else: # Using last reported camera location to process images and maps.
    MainLog.Log("Using last reported camera location to align images and maps.",terminal=False)

# Create 3 window columns. The sub-windows for the dashboard will be automatically stacked in these three columns.
colordisplay.AddCDEntry(colwidth=87,startcol=1)
colordisplay.AddCDEntry(colwidth=80,startcol=None)
colordisplay.AddCDEntry(colwidth=55,startcol=None)

ObservationStatusWindow = colordisplay(rows=14,cdlayout=0,name='OSW',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title='Observation status ' + ProgramTitle.upper() + ' ' + VERSION) # This is the text window that displays current progress of an observation.
ObservationStatusWindow.DrawBorder = True # Draw border around window.
ObservationStatusWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
ObservationStatusWindow.ClipWindow = True # Clip the display if the terminal area is insufficient. This means we see at least something.
ObservationStatusWindow.PlaceString('           Target: [TARGET                                                           ]',row=1,col=0)
ObservationStatusWindow.PlaceString('   Session folder: [FOLDER                                                           ]',row=2,col=0)
ObservationStatusWindow.PlaceString('   Tracking clock: [CLOCK                    ]UTC  Duration: [DURATION         ]      ',row=3,col=0)
ObservationStatusWindow.PlaceString('Storage available: [STORAGE               ]                                           ',row=5,col=0)
ObservationStatusWindow.PlaceString('   Camera Enabled: [CEN ] Exposure: [EXP         ]                                    ',row=6,col=0)
ObservationStatusWindow.PlaceString('   OnChip cleanup: [OCC ]                      Control mode: [CMODE           ]       ',row=7,col=0)
ObservationStatusWindow.PlaceString('    Target status: [TSTATUS] [TSDESC                                                 ]',row=8,col=0)
ObservationStatusWindow.PlaceString('                                                                                      ',row=9,col=0)
ObservationStatusWindow.PlaceString('Camera: Latest azimuth: [CAMAZ        ]          Latest altitude: [CAMALT       ]     ',row=10,col=0)
ObservationStatusWindow.PlaceString('     Estimated azimuth: [ESTAZ        ]       Estimated altitude: [ESTALT       ]     ',row=11,col=0)
ObservationStatusWindow.PlaceString('Target:        Azimuth: [TARAZ        ] [COMP]          Altitude: [TARALT       ]     ',row=12,col=0)
ObservationStatusWindow.PlaceString('                    RA: [RA                  ]       Declination: [DEC          ]     ',row=13,col=0)
ObservationStatusWindow.ScanForFields() # Scan the current image for field markers.
swFields = ObservationStatusWindow.ListFields() # Colour the data fields.
for key,value in swFields.items():
    ObservationStatusWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
ObservationStatusWindow.FieldColor('TSDESC',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG)
ObservationStatusWindow.FieldColor('ESTAZ',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG)
ObservationStatusWindow.FieldColor('ESTALT',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG)
ObservationStatusWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.

PrintColorList = [OSW_TEXT_FG,OSW_TEXT_GOOD] # Scrolling text windows use alternating colors for each line to aid readability in busy displays.

# Define some debugging windows. These appear when the terminal window is maximised.

# - The SESSION WINDOW shows the condition of the RPi <> Microcontroller control.
SessionWindow = colordisplay(rows=12,cdlayout=1,name='SESSION',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title='Communication status') 
SessionWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
SessionWindow.DrawBorder = True # Draw border around window.
SessionWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
#                                    1         2         3         4         5         6         7        
#                          0123456789012345678901234567890123456789012345678901234567890123456789012345678
SessionWindow.PlaceString('  Messages:Rx queued:[RQ]     Rx tot:[RT   ]       Tx queued:[TQ] Tx tot:[TT  ]',row=1,col=0)
SessionWindow.PlaceString('     State:   Resets:[SR]    DevFail:[DF ]           Last Rx:[LR         ]     ',row=2,col=0)
SessionWindow.PlaceString(' RPi Bytes:Rx:[BX    ]            Tx:[TX    ]         RxErrs:[RE]              ',row=3,col=0)
SessionWindow.PlaceString('MCtl Bytes:Rx:[MRX   ] [MRXR ]    Tx:[MTX   ] [MTXR ] RxErrs:[R2] TxDrops:[TD] ',row=4,col=0)
SessionWindow.PlaceString('      MCtl:  AutoCtl:[AC ]        RemCtl:[RCL]        ClkSyn:[CS ] Exc:[EXCEPT]',row=5,col=0)
SessionWindow.PlaceString('            Restarts:Forced:[FR]  Remote:[RR]          Alive:[ALIVE    ]       ',row=6,col=0)
SessionWindow.PlaceString('   azimuth:Conf:[ZC ]     Angle:[ZA     ] [CAZA  ]  OnTarget:[ZT ] [ZDPS    ]/s',row=7,col=0)
SessionWindow.PlaceString('                [ZMODE           ]:[ZD]   Expires:[ZU    ] UTC [ZRM         ]  ',row=8,col=0)
SessionWindow.PlaceString('  altitude:Conf:[LC ]     Angle:[LA     ] [CALTA ]  OnTarget:[LT ] [LDPS    ]/s',row=9,col=0)
SessionWindow.PlaceString('                [LMODE           ]:[LD]   Expires:[LU    ] UTC [LRM         ]  ',row=10,col=0)
SessionWindow.PlaceString('   Traj.flushes:[MTSF ]   Clk diff:[CLKDIF      ] Connection:[CMODE           ]',row=11,col=0)
SessionWindow.ScanForFields() # Scan the current image for field markers.
swFields = SessionWindow.ListFields()
for key,value in swFields.items():
    SessionWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
SessionWindow.FieldFormat('ZDPS',justify='right')
SessionWindow.FieldFormat('LDPS',justify='right')
for i in ['SR','RE','R2','FR','RR']: # Set range colours on some fields to automatically color as the value changes.
    if not SessionWindow.InitializeColorRange(i,badfg=OSW_TEXT_BAD,badbg=OSW_TEXT_BG,poorfg=OSW_TEXT_POOR,poorbg=OSW_TEXT_BG):
        MainLog.Log('Unable to SetFieldColorRange for',i,'in SessionWindow.',level='error')
SessionWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.

# - The MICROCONTROLLER RX WINDOW shows the latest messages received from the microcontroller.
MctlRxWindow = colordisplay(rows=17,cdlayout=1,name='MCTLRX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Receive from microcontroller") 
MctlRxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlRxWindow.DrawBorder = True # Draw border around window.
MctlRxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# - The MICROCONTROLLER TX WINDOW shows the latest messages sent to the microcontroller.
MctlTxWindow = colordisplay(rows=13,cdlayout=1,name='MCTLTX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Transmit to microcontroller") 
MctlTxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlTxWindow.DrawBorder = True # Draw border around window.
MctlTxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# - The CAMERA WINDOW shows the activities of the CAMERA THREAD which runs separately to the main thread of the software.
CameraWindow = colordisplay(rows=11,cdlayout=2,name='CAMERA',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Camera events") 
CameraWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraWindow.DrawBorder = True # Draw border around window.
CameraWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

ImageStatusWindow = colordisplay(rows=9,cdlayout=0,name='IMAGE',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Image Status")
ImageStatusWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
ImageStatusWindow.DrawBorder = True # Draw border around window.
ImageStatusWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# This is the text window that displays image and tracking progress of an observation.
ImageStatusWindow.PlaceString('       Capture state: [CAMERASTATE   ][STATETIMES       ] UTC [STATEAGE           ]   ',row=1,col=0)
ImageStatusWindow.PlaceString('        Image buffer: [OCVIB                            ] Camera task: [CTASK     ]   ',row=2,col=0)
ImageStatusWindow.PlaceString('  Drift target image: [DTI                                                        ]   ',row=3,col=0)
ImageStatusWindow.PlaceString('  Drift latest image: [DLI                                                        ]   ',row=4,col=0)
ImageStatusWindow.PlaceString(' Last azimuth tuning: [LAZT                                                       ]   ',row=5,col=0)
ImageStatusWindow.PlaceString('Last altitude tuning: [LALT                                                       ]   ',row=6,col=0)
ImageStatusWindow.PlaceString('      Session images: [IMAGES                                                     ]   ',row=7,col=0)
ImageStatusWindow.PlaceString('   Current image run: [RUN                  ] Acc:[ACCTIME  ] ETA:[ETA           ] UTC',row=8,col=0)

ImageStatusWindow.ScanForFields() # Scan the current image for field markers.
ImageStatusWindow.FieldFormat('CTASK',justify='center')
swFields = ImageStatusWindow.ListFields()
for key,value in swFields.items():
    ImageStatusWindow.FieldColor(key,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
ImageStatusWindow.SetDefault() # Store this 'blank' template to be reused when clearing the display.

InstructionWindow = colordisplay(rows=3,cdlayout=0,fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Commands")
# Instruction summary window.
#                             '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456'
InstructionWindow.PlaceString('  [r]Refresh    [t]Tracking on/off     [p]Preview      [m]Menu      [d]Debug on/off   ',row=1,col=0)
InstructionWindow.PlaceString('                                                                    [x]Quit           ',row=2,col=0)
InstructionWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
InstructionWindow.DrawBorder = True # Draw border around window.
InstructionWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# - The ERROR WINDOW shows any error messages raised by the software.
ErrorWindow = colordisplay(rows=6,cdlayout=0,name='ERROR',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Error messages") 
ErrorWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
ErrorWindow.DrawBorder = True # Draw border around window.
ErrorWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# General purpose window where developer messages can be written during observations.
DevWindow = colordisplay(rows=8,cdlayout=0,name='DEVELOPER',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Developer events")
DevWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DevWindow.DrawBorder = True # Draw border around window.
DevWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# - The LOG objects can be told to output error messages to a specific window too.
MainLog.ErrorWindow = ErrorWindow # Tell the MAIN logging mechanism that error messages can be replicated to the ERROR WINDOW. 
CamLog.ErrorWindow = CameraWindow # Tell the CAMERA logging mechanism that error messages can be replicated to the CAMERA WINDOW. 
# - Drift tracker debugging window.
# Events and decisions made by the drift tracking routine.
DriftWindow = colordisplay(rows=10,cdlayout=2,name='DRIFT',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Drift tracking")
DriftWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DriftWindow.DrawBorder = True # Draw border around window.
DriftWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# - Camera thread communications windows.
# Window showing communication from the camera handler thread to the main observation routine.
CameraRxWindow = colordisplay(rows=10,cdlayout=2,name='CAMERARX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Receive from camera handler")
CameraRxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraRxWindow.DrawBorder = True # Draw border around window.
CameraRxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# Window showing communications sent TO the camera handler from the main observation routine.
CameraTxWindow = colordisplay(rows=10,cdlayout=2,name='CAMERATX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Transmit to camera handler")
CameraTxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraTxWindow.DrawBorder = True # Draw border around window.
CameraTxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# All windows are defined. Turn on the 'reduceio' feature in them all.
colordisplay.GlobalReduceIO(True) # When redrawing windows, only the changed lines are repainted. 

# ///////////////////////////////////////////////////////////////////////////////////
# Camera assets. 
# ///////////////////////////////////////////////////////////////////////////////////

if CameraDriver == 'raspistill': #if OS_name in ['buster']:
    # The raspistill camera module records RAW image data in a JPG file with the data encoded as extra data.
    # We need to extract that RAW data and save it as a regular DNG file for later processing.
    # PiDNG is a great utility to do this. Need to use an older version of PiDNG because newer versions do more things, but don't support this function easily anymore.
    PiDNG = RPICAM2DNG() # Create instance of the PiDNG converter to extract RAW data from JPG files.
else: # libcamera 
    # PiDNG is already loaded and embedded within libcamera libraries so we don't need to load it anymore.
    # dng extraction is performed directly by libcamera-still.
    PiDNG = None # No instance of PiDNG needed.

# ------------------------------------------------------------------------------------------------------

class astrolens(attributemaster):
    """ Object representing the LENS being used by the telescope. 
        Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example. """
    def __init__(self,length,horizontal_fov,vertical_fov,aperture=2.8):
        self.Log = CamLog.Log # Handle to the method that logs messages.
        self.BaseLength = length # The length of the lense WITHOUT any multiplier effect.
        self.Length = length # 'focal length' of the lens.
        self.EquivLength = self.Length * 5.6 # From https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/ 35mm equivalent focal length (?) (AKA the Crop Factor for the sensor?
        self.FovHorizontal = horizontal_fov
        self.FovVertical = vertical_fov
        self.Fov = min(self.FovHorizontal, self.FovVertical) # When calculating the FOV for a survey, use the smaller value.
        self.Aperture = aperture # FStop of the lens. *Q* Multiplier will impact this too. Hmm...
        self.ID = str(self.Length) + "|" + str(self.FovHorizontal) + "|" + str(self.FovVertical) # Unique ID of lens features.
        self.Log("AstroLens: Length: " + str(self.Length) + "mm (equiv. " + str(self.EquivLength) + "mm) FoV: " + str(self.FovHorizontal) + DegreeSymbol + "*" + str(self.FovVertical) + DegreeSymbol,terminal=False)

class astrosensor(attributemaster):
    """ Object representing the IMAGE SENSOR being used by the telescope. 
        Default values are for the V1 RPi High Quality Camera (Sony sensor)? 
        Individual characteristics can be specified, or a specific sensor type can be given. 
        Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example. """

    # Can create a dictionary of sensor types and capabilities here.
    # width = image width in pixels.
    # height = image height in pixels.
    # video = Can take video in this mode.
    # image = Can take photo in this mode.
    # fov = full or partial field of view. partial means only the centre of the sensor is used. full means the whole sensor is used.
    # maxseconds = Longest exposure time supported.
    # raw = Can capture raw bayer data.
    # (*Q* This may not be needed in the future if libcamera can recognise the capabilities automatically.)
    SensorDict = {'imx477':
                    {1 : {'width' : 2028, 'height' : 1080, 'video' : True, 'image' : False, 'aspect' : '169:90',
                          'framerate' : {'min' : 0.1, 'max' : 50}, 'fov' : 'partial', 'binning' : True, 'scaled' : False, 'maxseconds' : 10.2, 'raw' : False},
                     2 : {'width' : 2028, 'height' : 1520, 'video' : True, 'image' : False, 'aspect' : '4:3', 
                          'framerate' : {'min' : 0.1, 'max' : 50}, 'fov' : 'full', 'binning' : True, 'scaled' : False, 'maxseconds' : 10.2, 'raw' : True},
                     3 : {'width' : 4056, 'height' : 3040, 'video' : True, 'image' : True, 'aspect' : '4:3', 
                          'framerate' : {'min' : 0.005, 'max' : 10}, 'fov' : 'full', 'binning' : False, 'scaled' : False, 'maxseconds' : 200.0, 'raw' : False},
                     4 : {'width' : 1012, 'height' : 760, 'video' : True, 'image' : True, 'aspect' : '4:3', 
                          'framerate' : {'min' : 50.1, 'max' : 120}, 'fov' : 'full', 'binning' : False, 'scaled' : True, 'maxseconds' : 10.2, 'raw' : False}
                    }
                 }


    def __init__(self,sensor_type='',pixel_width=4056,pixel_height=3040,max_seconds=200,min_seconds=0.0000001):
        self.Log = CamLog.Log # Handle to the method that logs messages.
        self.PixelWidth = pixel_width
        self.PixelHeight = pixel_height
        self.MaxExposureSeconds = max_seconds
        self.MinExposureSeconds = min_seconds
        self.Type = sensor_type
        if self.Type == 'imx477': # If the sensor type is recognised then set the value automatically.
            self.Log("AstroSensor: Recognised " + self.Type + " setting other characteristics automatically.",terminal=False)
            self.PixelWidth=4056
            self.PixelHeight=3040
            self.MaxExposureSeconds=200 # 200 seconds is the longest exposure time that raspistill can deliver.
            self.MinExposureSeconds=1e-6 # 1 microsecond is the fastest exposure time that raspistill can deliver.
        self.ID = str(self.PixelWidth) + "|" + str(self.PixelHeight) # Unique ID of lens features.
        self.Mode = 3 
        self.OnChipCleanup = True # Records whether we've got the on-chip cleanup enabled or not. 
        if self.Type in astrosensor.SensorDict: self.ModeDict = astrosensor.SensorDict[self.Type] # Select mode information for the chosen sensor.
        else: self.ModeDict = astrosensor.SensorDict['imx477'] # Default sensor for the telescope design.
        #self.ModeDict = {1 : {'width' : 2028, 'height' : 1080, 'video' : True, 'image' : False, 'aspect' : '169:90',
        #                      'framerate' : {'min' : 0.1, 'max' : 50}, 'fov' : 'partial', 'binning' : True, 'scaled' : False, 'maxseconds' : 10.2, 'raw' : False},
        #                 2 : {'width' : 2028, 'height' : 1520, 'video' : True, 'image' : False, 'aspect' : '4:3', 
        #                      'framerate' : {'min' : 0.1, 'max' : 50}, 'fov' : 'full', 'binning' : True, 'scaled' : False, 'maxseconds' : 10.2, 'raw' : True},
        #                 3 : {'width' : 4056, 'height' : 3040, 'video' : True, 'image' : True, 'aspect' : '4:3', 
        #                      'framerate' : {'min' : 0.005, 'max' : 10}, 'fov' : 'full', 'binning' : False, 'scaled' : False, 'maxseconds' : 200.0, 'raw' : False},
        #                 4 : {'width' : 1012, 'height' : 760, 'video' : True, 'image' : True, 'aspect' : '4:3', 
        #                      'framerate' : {'min' : 50.1, 'max' : 120}, 'fov' : 'full', 'binning' : False, 'scaled' : True, 'maxseconds' : 10.2, 'raw' : False}}
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
        if CameraDriver == 'raspistill': #if OS_name in ['buster']:
            print (textcolor.yellow("Disabling sensor cleanup to improve purity of sensor raw data."))
            if not self.Type in ['imx477']: # Check that the sensor cleanup function actually can be disabled.
                self.Log("AstroSensor.DisableCleanup is not supported for " + self.Type + " sensors. Ignored.",level='warning')
                return False
            cmd = 'sudo vcdbg set imx477.dpc 0' # Turn off on-chip cleaning of the image.
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored. The output is not displayed, however pilomar logs it in case other errors occur in the future.
            self.Log(cmd,terminal=False)
            osCmd(cmd)
            self.OnChipCleanup = False
            self.Log("Raspberry Pi High Quality Camera, on chip image cleanup DISABLED.",terminal=False)
            CameraWindow.Print(NowHMS() + " On Chip Cleanup - OFF")
        else: # libcamera has a command line option to disable cleanup.
            self.Log("Raspberry Pi High Quality Camera, on chip image cleanup will be disabled during exposures.",terminal=False)
        return True

    def EnableCleanup(self):
        """ Enable the on-chip image cleanup for the sensor.
            This returns the on-chip image cleanup back to the default state (ON)
            It is recommended to have it disabled for image stacking of raw images. """
        if CameraDriver == 'raspistill': #if OS_name in ['buster']:
            print (textcolor.yellow("Enabling sensor cleanup to restore factory functionality."))
            if not self.Type in ['imx477']:
                self.Log("AstroSensor.EnableCleanup is not supported for " + self.Type + " sensors. Ignored.",level='warning')
                return False
            cmd = 'sudo vcdbg set imx477.dpc 3' # Turn on on-chip cleaning of the image.
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored. The output is logged but not displayed in case other errors occur in the future.
            self.Log(cmd,terminal=False)
            osCmd(cmd)
            self.OnChipCleanup = True
            self.Log("Raspberry Pi High Quality Camera, on chip image cleanup ENABLED.",terminal=False)
            CameraWindow.Print(NowHMS() + " On Chip Cleanup - ON")
        else:
            self.Log("Raspberry Pi High Quality Camera, on chip image cleanup will be enabled during exposures.",terminal=False)
        return True

# ------------------------------------------------------------------------------------------------------

FolderList={} # Dummy entry until FolderList is fully defined. astrocamera doesn't initialize otherwise. 
FolderList["dataroot"] = ProjectRoot + "/data/" # Create default DATA pointer.
FolderList["log"] = ProjectRoot + "/log/" # Create default LOG pointer.

class astrocamera(attributemaster):
    """ Object representing the camera assembly being used.
        It contains the LENS and SENSOR objects, also various attributes and settings of the overall camera. """
    def __init__(self,inp_sensor,inp_lens,exposure=1.0,trackingexposure=5.0):
        self.Log = CamLog.Log # Handle to the method that logs messages.
        self.Sensor = inp_sensor # The sensor that makes up the camera.
        self.Lens = inp_lens # The lens that makes up the camera.
        self.ExposureSeconds = exposure # Exposure seconds per frame for astro photos ('light' frames).
        self.TrackingExposureSeconds = trackingexposure # Tracking photos are always 5 second exposure.
        self.PixelsPerFovDegreeWidth = 0 # Set by ModeChange() below.
        self.PixelsPerFovDegreeHeight = 0 # Set by ModeChange() below. 
        self.PixelFovWidth = 0 # Set by ModeChange() below. # Field of view of an individual pixel (very approximate).
        self.PixelFovHeight = 0 # Set by ModeChange() below.
        self.SecondsPerPixel = 0.0 # Set by ModeChange() below. Specifies how long an object takes to traverse one pixel of an image.
        self.ModeChange() # Set values based upon sensor mode. 
        self.LastImageDateTime = None # When was the latest image taken? # *Q* How widely is this attribute used?
        self.Lastjpg = None # The filename of the last jpg taken (if saved)
        self.Previewjpg = None # The filename of the last preview image generated. 
        self.Image = pilomarimage(name='camera',logger=CamLog) # pilomarimage instance for handling OpenCV image buffer.
        self.CaptureStart = None # Timestamp when image capture started. Used to detect camera hanging.
        self.CaptureEnd = None # Timestamp when image capture completed. Used to detect camera hanging.
        self.AstrotimeStart = None # skyfield timestamp when image capture completed. # Used to synchronise markup calculations.
        self.AstrotimeEnd = None # skyfield timestamp when image capture completed. # Used to synchronise markup calculations.
        self.BatchCount = 0 # How many photos taken in the current observation batch? 
        self.ID = self.Sensor.ID + "|" + self.Lens.ID # Unique ID of lens and sensor characteristics.
        self.SetImageType('light') # The type of image being captured. Links to FolderList. Tells HOW to process the image and WHERE to store it.
        self.CameraTasks = [] # No tasks to perform yet.
        self.CurrentTask = None # The current task being performed by the camera.
        self.LastLightCommand = '' # Keep a note of the camera options used for the latest light image.
        # Observation specific settings. These override the general parameters in instances where the general parameters don't make sense. Eg meteor monitoring.
        self.CameraSaveDng = True
        self.CameraSaveJpg = True
        self.CameraOptions = '' # The camera options passed to raspistill. These depend upon the image type being captured.
        self.RxCount = 0 # Number of messages received by camera thread.
        self.TxCount = 0 # Number of messages sent by camera thread.

    def PixelFoV(self):
        """ Return the approximate Field Of View of a single pixel.
            This measure is useful for calibrating the tolerance of trajectory segments. """
        if self.PixelsPerFovDegreeWidth != 0: self.PixelFovWidth = 1 / self.PixelsPerFovDegreeWidth
        else: self.PixelFovWidth = 0
        if self.PixelsPerFovDegreeHeight != 0: self.PixelFovHeight = 1 / self.PixelsPerFovDegreeHeight
        else: self.PixelFovHeight = 0
        self.Log("astrocamera.PixelFoV (w/h)", self.PixelFovWidth, self.PixelFovHeight,terminal=False)

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
        elif Parameters.GeneratePreview == False:
            CameraWindow.Print(NowHMS() + " Preview generation is disabled in parameters.")
            self.Log("astrocamera.SetObservationParameters Preview generation is disabled in parameters.",terminal=False)
        else: self.CameraTasks.append('preview') # Don't preview for meteor showers.
        if Session.Target.ObjectType in ['meteor','altaz','earth satellite','aurora']:
            # Don't track for fixed targets or fast moving targets.
            CameraWindow.Print(NowHMS() + " No tracking performed for " + Session.Target.ObjectType + " targets.")
            self.Log("astrocamera.SetObservationParameters No tracking performed for", Session.Target.ObjectType, "targets.",terminal=False)
        else: # Do track for targets that rotate with the sky. Always add tracking to the tasklist, even if it's currently disabled. The tracking routine will handle that, and it could be dynamically enabled during the observation.
            self.CameraTasks.append('tracking') 
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", Selected tasks:", self.CameraTasks,terminal=False)
        
        # Set observation specific parameters for the camera based upon general parameter settings.
        # - Eg 'meteor' mode can override some settings, but we don't want to disturb the general settings used for other targets.
        if Session.Target.ObjectType in ['meteor']: self.CameraSaveDng = False
        else: self.CameraSaveDng = Parameters.CameraSaveDng
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", CameraSaveDng",self.CameraSaveDng,terminal=False)

        if Session.Target.ObjectType in ['meteor']: self.CameraSaveJpg = True
        else: self.CameraSaveJpg = Parameters.CameraSaveJpg
        self.Log("astrocamera.SetObservationParameters Target type", Session.Target.ObjectType,", CameraSaveJpg",self.CameraSaveJpg,terminal=False)

        # What image types to process?
        if Session.Target.ObjectType in ['meteor']: # Meteor detection is special, just grap JPGS as fast as possible.
            # Meteor monitoring is always in fast mode and we don't intend to extract any further data, just capture .jpgs.
            self.CameraSaveDng = False # Don't generate raw data.
            self.CameraSaveJpg = True # Just create simple JPG files.
        else: # Other targets follow the general parameter settings.
            self.CameraSaveDng = Parameters.CameraSaveDng
            self.CameraSaveJpg = Parameters.CameraSaveJpg

        self.Log("astrocamera.SetObservationParameters CameraSaveDng/Jpg:", self.CameraSaveDng, self.CameraSaveJpg, terminal=False)
        return True
        
    def CalibrateFov(self):
        """ Ask the user to enter the pixel diameter of the moon from a photograph. 
            Use this to estimate the FieldOfView of the camera and adjust parameters accordingly. """
        self.Log("astrocamera.CalibrateFov: Begin",terminal=False)
        print(textcolor.yellow("Calibrate lens"))
        MoonMeanDiaDeg = 0.5286
        ExpectedDiaPix = int(self.PixelsPerFovDegreeWidth * MoonMeanDiaDeg) # How big do we expect the moon to be with current settings?
        listlines = ["Currently the lens has the following characteristics", " ",
                     "Focal length: " + str(self.Lens.Length) + "mm",
                     "35mm equivalent: " + str(self.Lens.EquivLength) + "mm",
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
            self.Log("astrocamera.CalibrateFov: Proceeding",terminal=False)
            result = AskYesNo("Do you have an image of the moon captured with the current lens? [y/N]",False)
        if result == False:
            self.Log("astrocamera.CalibrateFov: Moon image is not available",terminal=False)
            listlines = ["You must take a photograph of the moon with the current lens.",
                         "Measure the pixel diameter of the moon's full disc on that image.",
                         "Using that pixel size we can estimate the field of view of the lens."]
            textcolor.TextBox(listlines)
            return # Do nothing.

        self.Log("astrocamera.CalibrateFov: Moon image is available",terminal=False)

        # Can we offer any hints from the last image captured?
        self.Log("astrocamera.CalibrateFov: Consider last captured image",terminal=False)
        if self.Image.ImageExists(): # There's an image in the buffer, what large objects are in there?
            dia_min = 50 # Smallest diameter objects to list.
            dia_max = 600 # Largest diameter objects to list.
            area_min = math.pi * ((dia_min / 2) ** 2)
            area_max = math.pi * ((dia_max / 2) ** 2)
            BC_Count, BC_List = self.Image.CountStars(minval=area_min,maxval=area_max) # Count objects with large pixel areas (100-600 pixel radius).
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
            self.Log("astrocamera.CalibrateFov: No moon diameter value given",terminal=False)
            return # Nothing to do.

        self.Log("astrocamera.CalibrateFov: Moon diameter",rawtext,"pixels",terminal=False)

        # We have what we need.
        moonpixels = TextToInt(rawtext) # Convert the measured diameter into integer.
        print ("The camera records the moon as",moonpixels,"pixels in diameter.")
        print ("The moon is" + str(MoonMeanDiaDeg) + DegreeSymbol,"in diameter on average.")
        # Convert to field of view.
        # Lens fields to change...
        self.Lens.FovHorizontal = round(self.Sensor.PixelWidth * MoonMeanDiaDeg / moonpixels,1) # FOV to 1 decimal place is enough.
        self.Lens.FovVertical = round(self.Sensor.PixelHeight * MoonMeanDiaDeg / moonpixels,1) # FOV to 1 decimal place is enough.
        self.Lens.Fov = min(self.Lens.FovHorizontal, self.Lens.FovVertical) # When calculating the FOV for a survey, use the smaller value.
        self.Log("astrocamera.CalibrateFov: Chosen H.FoV:",self.Lens.FovHorizontal,"V.FoV:",self.Lens.FovVertical,terminal=False)
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
            self.Log("astrocamera.CalibrateFov: Making FoV permanent.",terminal=False)
            Parameters.LensHorizontalFov = self.Lens.FovHorizontal
            Parameters.LensVerticalFov = self.Lens.FovVertical
        else: # Don't touch the parameter settings, so the system will reset when restarted.
            self.Log("astrocamera.CalibrateFov: Making FoV temporary.",terminal=False)
            print (textcolor.yellow("These values are temporary. They will reset when you restart the software."))
            print (textcolor.red("To make these values permanent please edit LensHorizontalFov and LensVerticalFov values in the parameters file."))
            print (textcolor.red("(" + ParameterFileName + ")"))
        
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

    def Reset(self):
        """ Reset camera settings at the beginning of a new session. """
        self.LastImageDateTime = None # When was the latest image taken?
        self.Lastjpg = None # The filename of the last jpg taken (if saved)
        self.Previewjpg = None # The filename of the last preview image generated. 
        self.Image.Clear() # openCV image buffer. Loaded explicitly when needed.
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


    def CameraFault(self):
        """ Return true if it looks like the camera has hung. 
            This usually requires an entire reboot of the RPi.
            The hang is somewhere in the camera subsystem.
            Suspect it is related to memory problems, but cause or effect? 
            NOTE: There are overheads in the camera libraries, the camera takes much longer than just the 'exposure' time to complete an image. 
                  Typically a call to raspistill will take at least DOUBLE the exposure time to complete a capture."""
        result = False # no fault detected yet.
        if Parameters.CameraEnabled and self.CaptureStart != None: # An attempt has been made and the camera is on!
            if self.CaptureEnd == None or self.CaptureEnd <= self.CaptureStart: # It hasn't completed yet.
                # Decide upon a sensible 'failure' delay to accept. At least 300seconds(5 minutes)
                # We have to be very generous here because this is a linux system and can sometimes pause a lot!
                faultdelay = max(self.ExposureSeconds * 5,500)
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
        self.Log("astrocamera.ModeChange(): To avoid blurring the camera needs to move every",round(self.SecondsPerPixel,3),"seconds.",terminal=False)
        self.Log("astrocamera.ModeChange(): Mode " + str(self.Sensor.Mode) + " selected.",terminal=False)
        self.PixelFoV() # Calculate field of view of an individual pixel (very approximate).

    def CleanupLastjpg(self):
        """ Call this to delete the disc copy of the last jpg file that was generated.
            It also clears the reference to the file that has been deleted. """
        self.Log("astrocamera.CleanupLastjpg()",terminal=False)
        if self.Lastjpg != None:
            cmd = "rm " + self.Lastjpg
            osCmd(cmd)
            self.Lastjpg = None # Clear the saved filename.

    def FakePhoto(self,outputfile,astrotime=None):
        # Generate false disc file to simulate a photograph being captured. 
        self.Log("astrocamera.FakePhoto: Simulating photo capture (",outputfile,")",terminal=False)
        fakeimage = pilomarimage(name='fakephoto',logger=CamLog)
        height = self.Sensor.PixelHeight
        width = self.Sensor.PixelWidth
        fakeimage.New(height,width,imagetype='bgr',datatype=np.uint8)
        if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: fakeimage.New() failed.",level='error',terminal=True)
        fakeimage.ImageBuffer,starcount,starlist = CreateTargetImage(color=True,MinMagnitude=Parameters.TargetMinMagnitude,astrotime=astrotime) # Use CreateTargetImage to make fake photo.
        if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: CreateTargetImage() failed.",level='error',terminal=True)
        try:
            fakeimage.SaveFile(outputfile)
        except Exception as e:
            self.Log("astrocamera.FakePhoto failed to write:",outputfile,level='error')
            self.ReportException(e,comment='astrocamera.FakePhoto cv2.imwrite')
        self.Log("astrocamera.FakePhoto: Completed.",terminal=False)
        return True

    def FakeDark(self,outputfile):
        # Generate false disc file to simulate a photograph being captured. 
        self.Log("astrocamera.FakeDark: Simulating dark photo capture (",outputfile,")",terminal=False)
        fakeimage = pilomarimage(name='fakedark',logger=CamLog)
        height = self.Sensor.PixelHeight
        width = self.Sensor.PixelWidth
        fakeimage.New(height,width,imagetype='bgr',datatype=np.uint8)
        fakeimage.FillColor(BGRBlack)
        try:
            fakeimage.SaveFile(outputfile)
        except Exception as e:
            self.Log("astrocamera.FakeDark failed to write:",outputfile,level='error')
            self.ReportException(e,comment='astrocamera.FakeDark cv2.imwrite')
        self.Log("astrocamera.FakeDark: Completed.",terminal=False)
        return True

    def SetFakeDelay(self,camera_options):
        """ Extract the exposure time from camera options and pause processing
            to mimic the actual amount of time the camera would take. """
        optlist = camera_options.split(' ')
        delay = 1.0
        for i,opt in enumerate(optlist): # *Q* Doesn't recognise libcamera format parameters yet!
            if opt == '-ss': # Found exposure time.
                delay = float(optlist[i + 1]) * 2 # Find the microsecond exposure time and double it to mimic camera.
                delay = delay / 1_000_000 # Convert from microseconds to seconds.
                self.Log("astrocamera.FakeDelay : ",round(delay,1),"s ...",terminal=False)
                break
        delaytimer = timer(period=delay) # Create timer.
        return delaytimer

    def CaptureSet(self,file_root,batch_size,camera_command,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take batch of photos. Uses CaptureSetFull or CaptureSetFast depending upon configuration. """
        # Automatic parameter conversion, if not already done before receiving camera_command.        
        camera_command = camera_command.replace('{&mode}',str(self.Sensor.Mode))
        camera_command = camera_command.replace('{&width}',str(self.Sensor.PixelWidth))
        camera_command = camera_command.replace('{&height}',str(self.Sensor.PixelHeight))
        result = self.CaptureSetFull(file_root,batch_size,camera_command,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime)
        return result
    
    def CaptureSetFull(self,file_root,batch_size,camera_command,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take a batch of photos... 
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
        self.LastLightCommand = camera_command # keep a note of the exposure options, it's reported in the preview images.
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(2) # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile: outputfile = file_root + 'temp.jpg' # This is the 'intermediate' jpg generated by the camera. *Q* Delete when finished.
            else: outputfile = file_root + UtcTimeStamp() + "_" + frame + '.jpg' # This is the 'intermediate' jpg generated by the camera.
            self.Log("astrocamera.CaptureSetFull(): Capturing " + outputfile + "...",terminal=False)
            cmd = camera_command.replace('{&output}',outputfile)
            #if CameraDriver == 'raspistill': #if OS_name in ['buster']:
            #    cmd = 'raspistill -o ' + outputfile + ' ' + camera_options # Use raspistill to take the photo.
            #else: # Bookworm O/S uses libcamera-still
            #    cmd = 'libcamera-still --output ' + outputfile + ' ' + camera_options # Use libcamera-still to take the photo.
            remoterestarts = Mctl.RemoteRestarts # If this changes during exposure, the microcontroller reset and we should reject the image.
            rejectimage = False # Set to 'true' if there's a reason to reject the image.
            #Led3.On()
            self.AstrotimeStart = ts.now()
            self.CaptureStart = Ts2Datetime(self.AstrotimeStart)
            if Parameters.CameraEnabled: # Camera is enabled. Take real photo.
                osCmd(cmd,output='none')
                retc = OSCommand.ReturnCode # What did the camera command exit with ?
                self.Log("astrocamera.CaptureSetFull(): Return code:",retc,terminal=False)
                if retc != 0: # Non zero return code. Did something go wrong?
                    CameraWindow.Print(NowHMS() + " Return code " + str(retc),fg=textcolor.YELLOW)
                    ErrorWindow.Print(NowHMS() + " capture returned code " + str(retc),fg=textcolor.YELLOW)
            else: # Camera is not in use. Generate fake photo.
                self.Log("astrocamera.CaptureSetFull(): About to call FakePhoto.",terminal=False)
                tr = False # Fake image generation failed unless we are told otherwise.
                imty = self.GetImageType() # What type of image are we faking?
                DelayTimer = self.SetFakeDelay(camera_command) # Create a timer to mimic the expected real camera delay.
                if imty == 'dark': tr= self.FakeDark(outputfile=outputfile) # Fake a dark frame.
                else: tr = self.FakePhoto(outputfile=outputfile,astrotime=astrotime) # Fake a light frame.
                if not tr: # Image generation failed.
                    self.Log("astrocamera.CaptureSetFull(): Fake image call failed (",imty,").",terminal=True,level='error')
                else: # Fake the expected exposure time if a real image was being captured.
                    DelayTimer.Wait() # Wait until the fake delay timer expires. Thread pauses here.
                self.Log("astrocamera.CaptureSetFull(): Returned from FakePhoto.",terminal=False)
            self.AstrotimeEnd = SkyfieldNow() # Offset supported.
            self.CaptureEnd = Ts2Datetime(self.AstrotimeEnd)
            #Led3.Off()
            self.Log("astrocamera.CaptureSetFull(): Capture complete. (",(self.CaptureEnd - self.CaptureStart).total_seconds(), "s).",terminal=False)
            if remoterestarts != Mctl.RemoteRestarts: # Microcontroller reset during exposure.
                self.Log('astrocamera.CaptureSetFull(): Microcontroller restarted during exposure. Reject',outputfile,level='warning',terminal=False)
                CameraWindow.Print(NowHMS() + " Motors reset during exposure.") # Just the filename.
                ErrorWindow.Print(NowHMS() + " Motors reset during exposure.") # Just the filename.
                rejectimage = True # We should reject this image.
            if not tempfile: # Display the filename if it's permanent, ignore the tempfile.
                CameraWindow.Print(NowHMS() + " " + outputfile.split('/')[-1]) # Just the jpg filename.
            if rejectimage: # There was reason to reject the image for some cause.
                self.Log("astrocamera.CaptureSetFull(): Image should be rejected.",terminal=False)
            self.Lastjpg = outputfile # The camera can remember this file as the 'last jpg taken'
            self.Log("astrocamera.CaptureSetFull(): Load image from " + outputfile,terminal=False)
            self.Image.LoadFile(outputfile)
            if self.Image.ImageMissing(): # imread failed. The capture did not succeed for some reason?
                self.Log("astrocamera.CaptureSetFull(): imread of",outputfile,"failed.",level='error',terminal=False)
            self.LastImageDateTime = NowUTC() # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.Log("astrocamera.CaptureSetFull(): Image loaded.",terminal=False)
            if (" -r " in camera_command + ' ' or " --raw " in camera_command + ' ') and Parameters.CameraEnabled: # The jpg contains RAW data in the file tags, extract it. Convert it.
                if CameraDriver == 'raspistill': # We need to manually extract the DNG data.
                    # with raspistill convert to RAW. We have to extract the raw data RAW for .dng files to be saved.
                    self.Log("astrocamera.CaptureSetFull(): Converting to RAW (.DNG) file...",terminal=False)
                    dngname = outputfile.replace('.jpg','.dng')
                    try:
                        PiDNG.convert(outputfile) # Convert the saved .jpg file into the raw .dng format.
                    except Exception as e:
                        CamLog.RaiseException(e,comment='astrocamera.CaptureSetFull(): PiDNG.convert failed.')
                    self.Log("astrocamera.CaptureSetFull(): Converted to RAW (.DNG) file.",terminal=False)
                    # Cleanup. Remove any intermediate files that are nolonger needed.
                    if self.CameraSaveJpg: # We should save 'JUST' the jpg data, effectively stripping out the embedded RAW data 
                        self.Image.SaveFile(outputfile) # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else: # We're only saving the RAW data, so just delete the original jpg file.
                        self.Log("astrocamera.CaptureSetFull(): Deleting intermediate .jpg file...",terminal=False)
                        self.CleanupLastjpg() # We've finished with the original .jpg on disc.
                    if not self.CameraSaveDng: # We don't need to keep the .dng file anymore.
                        self.Log("astrocamera.CaptureSetFull(): DNG nolonger needed.",terminal=False)
                        cmd = 'rm ' + dngname
                        osCmd(cmd,output='log')
                    else:
                        CameraWindow.Print(NowHMS() + " " + dngname.split('/')[-1]) # Just the dng filename.
            if tempfile: # Delete the temporary file.
                cmd = 'rm ' + outputfile
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
        tempimage = pilomarimage(name='temp',logger=CamLog)
        if filecount > 0:
            for file in files:
                print(file)
                # Load jpg data into temporary buffer.
                tempimage.LoadFile(file)
                if tempimage.ImageMissing(): # imread failed.
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
                        tempimage.SaveFile(file) # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else: # We're only saving the RAW data, so just delete the original jpg file.
                        self.Log("astrocamera.ProcessImageFiles: Deleting intermediate .jpg file...",terminal=False)
                        cmd = 'rm ' + file
                        osCmd(cmd,output='log')
        else:
            print(textcolor.yellow("No suitable unprocessed files were found."))
            print("- There is no RAW data in simulated images (Is the camera disabled?)")
            print("- There must still be observation images on disc to process.")
        self.Log("astrocamera.ProcessImageFiles(): Done",terminal=True)
        return True

    def ContainsMeteors(self,image): # In pilomarimage
        """ Return TRUE if meteors or aircraft trails are detected in an image. """
        if len(self.LineDetection(image)) > 0: return True
        else: return False
        
    def TakePhoto(self,batch_size,terminal=True):
        """ Make an observation. This is a LIGHT image of the actual object under observation. """
        self.Log("astrocamera.TakePhoto: Begin",terminal=False)
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.SetImageType('light') # Tell the camera we are taking light photos.
        FileRoot=FolderList.get('light') + 'light_'
        # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
        # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
        CameraCommand = Parameters.CameraLightCommand
        CameraCommand = CameraCommand.replace('{&shutter}',str(ExposureMicroseconds))
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if self.CameraSaveDng: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + Parameters.CameraRawSwitch + ' ' # Append RAW data to the image.
        #self.LastLightCommand = CameraCommand # keep a note of the exposure options, it's reported in the preview images.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand,terminal=terminal,cleanup=False)
        if not result:
            self.Log("astrocamera.TakePhoto: CaptureSet failed.",level='error')
        self.Log("astrocamera.TakePhoto: Complete",terminal=False)
        return result

    def MeteorFileScan(self):
        """ If image conversions were not done during capture, this can find and convert all the 
            image files currently in storage. This is used if CaptureSetFast was used to gather 
            images as quickly as possible. 
            This will convert all image files found the have the characteristics of a jpg with embedded raw data. """
        self.Log("astrocamera.MeteorFileScan(): Starting",terminal=True)
        # Find all image files that need converting.
        rootfolder = FolderList['imageroot'] # This is the parent data folder for all Pilomar images.
        self.Log("astrocamera.MeteorFileScan(): Searching for .jpgs in",rootfolder,terminal=True)
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
            tempimage = pilomarimage(name='temp',logger=CamLog)
            for i,file in enumerate(files):
                # Check for EXIT from keyboard.
                kcl = Keyboard.Check().lower()
                if kcl in ['x',chr(27)]: # Exit key pressed.
                    print ("")
                    print ("** Quit **")
                    break
                print(textcolor.cursorup() + textcolor.clearforward() + NowHMS(), "Scanning", (i + 1), "of", filecount, "(" + file.split("/")[-1] + ")", "Found", len(MeteorFiles), "candidates,")
                # Load jpg data into temporary buffer.
                tempimage.LoadFile(file)
                if tempimage.ImageMissing(): # imread failed.
                    self.Log("astrocamera.ProcessImageFiles: imread",file,"failed.",terminal=False)
                else: # imread was successful.
                    if len(tempimage.LineDetection()) > 0: # Potential meteor lines were found.
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
        CameraCommand = Parameters.CameraTrackingCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(ExposureMicroseconds))
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand,tempfile=True,terminal=terminal,cleanup=False)
        self.Log("astrocamera.TakeTrackingPhoto: Complete",terminal=False)
        return result

    def DarkSet(self,batch_size):
        """ Take a DARK set of images for photo stacking. """
        print (textcolor.yellow("DarkSet"))
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.SetImageType('dark') # Tell the camera we are taking dark photos.
        FileRoot = FolderList.get('dark') + 'dark_'
        self.Log("Generating DARK image set.")
        self.Log("These match the LIGHT exposure time of",self.ExposureSeconds,"seconds.")
        self.Log("These are used to remove electrical noise from the images.")
        self.Log("Lens cap must be ON.")
        self.Log("Images will be stored in", FileRoot)
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Dark image set...')
        CameraCommand = Parameters.CameraDarkCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(ExposureMicroseconds))
        if self.CameraSaveDng: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + Parameters.CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result

    def DarkFlatSet(self,batch_size):
        """ Take a DARK-FLAT set of images for photo stacking. """
        print (textcolor.yellow("DarkFlatSet"))
        ExposureMicroseconds = int(0.001 * 1000000) # 1/1000th of a second.
        self.SetImageType('darkflat') # Tell the camera we are taking darkflat photos.
        FileRoot = FolderList.get('darkflat') + 'darkflat_'
        self.Log("Generating DARK FLAT image set.")
        self.Log("These help remove electrical and manufacturing noise from the images.")
        self.Log("These match the FLAT exposure time of",ExposureMicroseconds / 1000000.0, "seconds.")
        self.Log("Lens cap must be ON.")
        self.Log("Images will be stored in", FileRoot)
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Dark-Flat image set...')
        CameraCommand = Parameters.CameraDarkFlatCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(ExposureMicroseconds))
        if self.CameraSaveDng: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + Parameters.CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result

    def FlatSet(self,batch_size):
        """ Take a FLAT set of images for photo stacking. """
        print (textcolor.yellow("FlatSet"))
        self.SetImageType('flat') # Tell the camera we are taking flat photos.
        FileRoot = FolderList.get('flat') + 'flat_'
        self.Log("Generating FLAT image set.")
        self.Log("These are flat white unfocused images.")
        self.Log("These will be a short exposure time (Auto exposure)")
        self.Log("Flat images are used to compensate for vignetting and dealing with dust and dead pixels.")
        self.Log("The lens cap must be OFF. You need a evenly lit neutral white target.")
        self.Log("People often stretch a white t-shirt over the lens and point at a bright area of sky.")
        self.Log("You can re-use the flat image set across multiple campaigns.")
        self.Log("Images will be stored in", FileRoot)
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Flat image set...')
        CameraCommand = Parameters.CameraFlatCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if self.CameraSaveDng: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + Parameters.CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result

    def BiasSet(self,batch_size):
        """ Take a BIAS/OFFSET set of images for photo stacking. """
        print (textcolor.yellow("BiasSet"))
        ExposureMicroseconds = int(0.001 * 1000000) # 1/1000th of a second.
        self.SetImageType('bias') # Tell the camera we are taking bias photos.
        FileRoot = FolderList.get('bias') + 'bias_'
        self.Log("Generating OFFSET/BIAS image set.")
        self.Log("These will be the shortest possible exposure time (FASTEST)",ExposureMicroseconds / 1000000.0,"seconds")
        self.Log("The temperature and ISO settings must be the same as the LIGHT images.")
        self.Log("These are used to remove manufacturing defects from the images that the sensor captures.")
        self.Log("Lens cap must be ON.")
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Bias image set...')
        CameraCommand = Parameters.CameraBiasCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(ExposureMicroseconds))
        if self.CameraSaveDng: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + Parameters.CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
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
            CameraCommand = Parameters.CameraAutoCommand
            CameraCommand = CameraCommand.replace('{&mode}',str(self.Sensor.Mode))
            CameraCommand = CameraCommand.replace('{&width}',str(self.Sensor.PixelWidth))
            CameraCommand = CameraCommand.replace('{&height}',str(self.Sensor.PixelHeight))
            CameraCommand = CameraCommand.replace('{&output}',filename)
            osCmd(CameraCommand)
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

# Summarise camera settings...
CameraWindow.Print("Lens:",LensInUse.Length,"mm (35mm equiv.",LensInUse.EquivLength,"mm)")
CameraWindow.Print("Lens: FoV:",str(LensInUse.FovHorizontal) + DegreeSymbol,"*",str(LensInUse.FovVertical) + DegreeSymbol)
CameraWindow.Print("Sensor: Width",SensorInUse.PixelWidth,"* Height",SensorInUse.PixelHeight,"pixels")

# ///////////////////////////////////////////////////////////////////////////////////
# Enable/disable key features during testing.
# ///////////////////////////////////////////////////////////////////////////////////

#MainLog.Log("The motors can be disabled in the parameters file if you want to test only the software.",terminal=False)
#if Parameters.MotorsEnabled: print (textcolor.green("Motors enabled"))
#else: print (textcolor.red("Motors disabled"))

# ---------------------------------------------------------------------------------------------------- 

def DetectRaspistill(canenable=False,candisable=False): 
    """ Test to see if the camera is connected and active via raspistill.
        This is used in BUSTER operating system builds.    
        candisable = True: If the camera is not found, then automatically disable it in parameters.
        canenable = True: If the camera is found, then automatically enable it in parameters. """
    filename = ProjectRoot + '/temp/testraspistill.jpg' # Or use /dev/null ? We don't need this file.
    # Remove any earlier copy of the file.
    tempcmd = 'rm ' + filename
    _ = osCmd(tempcmd)
    tempcmd = 'raspistill -o ' + filename # Simple command to test the camera.
    MainLog.Log("DetectRaspistill:",tempcmd,terminal=False)
    templist = osCmd(tempcmd)
    if os.path.exists(filename): # file exists so assume camera is available.
        tempresult = True
    else: # file doesn't exist, so assume camera is unavailable.
        tempresult = False
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
        MainLog.Log("DetectRaspistill: Camera not found.",level='warning')
        if candisable:
            if Parameters.CameraEnabled: # Warn the user that the camera is automatically disabled.
                Parameters.CameraEnabled = False
                MainLog.Log("Camera has been automatically disabled.",level='warning')
                MainLog.Log("When the camera is available, you can re-enable it from the Camera Tools menu.",level='warning')
    templist = osCmd('rm ' + filename) # Cleanup. Ignore errors.
    print("DetectRaspistill:",tempresult)
    return tempresult

# ---------------------------------------------------------------------------------------------------- 

def DetectLibcamera(canenable=False,candisable=False): 
    """ Test to see if the camera is connected and active via libcamera. 
        This is used in BOOKWORM operating system builds.
        candisable = True: If the camera is not found, then automatically disable it in parameters.
        canenable = True: If the camera is found, then automatically enable it in parameters. """
    filename = ProjectRoot + '/temp/testlibcamera-still.jpg' # Or use /dev/null ? We don't need this file.
    # Remove any earlier copy of the file.
    tempcmd = 'rm ' + filename
    _ = osCmd(tempcmd)
    tempcmd = 'libcamera-still --output ' + filename + ' --nopreview --timeout 10' # Simple command to test the camera.
    MainLog.Log("DetectLibcamera:",tempcmd,terminal=False)
    templist = osCmd(tempcmd)
    if os.path.exists(filename): # file exists so assume camera is available.
        tempresult = True
    else: # file doesn't exist, so assume camera is unavailable.
        tempresult = False
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
        MainLog.Log("DetectLibcamera: Camera not found.",level='warning')
        if candisable:
            if Parameters.CameraEnabled: # Warn the user that the camera is automatically disabled.
                Parameters.CameraEnabled = False
                MainLog.Log("Camera has been automatically disabled.",level='warning')
                MainLog.Log("When the camera is available, you can re-enable it from the Camera Tools menu.",level='warning')
    templist = osCmd('rm ' + filename) # Cleanup. Ignore errors.
    print("DetectLibcamera:",tempresult)
    return tempresult

# ---------------------------------------------------------------------------------------------------- 

def DetectCamera(canenable=False,candisable=False):
    """ Test for presence of a camera via raspistill or libcamera. """
    if CameraDriver == 'raspistill': #if OS_name in ['buster']:
        return DetectRaspistill(canenable=canenable,candisable=candisable)
    else: # Expect libcamera.
        return DetectLibcamera(canenable=canenable,candisable=candisable)
    
# ---------------------------------------------------------------------------------------------------- 

def AutoDetectCamera(): 
    """ This tests the telescope camera. 
        If found, it enables the camera.
        If missing, it disables the camera. """
    DetectCamera(canenable=True, candisable=True)

# ---------------------------------------------------------------------------------------------------- 

def CalibrateFovMenu():
    """ Use the diameter of the full moon to calibrate the field of view of the lens. 
        The moon is a relatively stable known angular diameter in the sky. 
        By taking a photograph of the moon and measuring the number of pixels that the
        moon occupies we can work backwards to estimate the field of view of the lens. """
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        CameraInUse.CalibrateFov()
        CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
        FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
        DocumentSession()
        DriftTracker.Reset()
        
# ---------------------------------------------------------------------------------------------------- 

def EnableCamera():
    """ This enables the camera, even if it is not installed. """
    Parameters.CameraEnabled = True
    MainLog.Log("Camera has been manually enabled.",level='warning',terminal=True)

# ---------------------------------------------------------------------------------------------------- 

def DisableCamera():
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
    MainLog.Log("The program will generate simulated images instead.",terminal=False)
    lines = ["The camera is disabled . The program will generate  simulated  images",
             "instead . The simulated images will show approximate  star and target",
             "locations.",
             "Simulated images may take longer to calculate  than a true photograph",
             "would take . Therefore the  telescope  may gather 'light' images more",
             "slowly than you would expect."]
    textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK)         

# ///////////////////////////////////////////////////////////////////////////////////
# GPIO setup.
# ///////////////////////////////////////////////////////////////////////////////////
        
# Use BCM GPIO references instead of physical pin numbers.
# GPIO must be enabled via raspi-config.
GPIO.setmode(GPIO.BCM)
 
# // Initialise control IO
StopBCM = 25 # BCM pin 12 to stop an obvservation.
GPIO.setup(StopBCM,GPIO.IN,pull_up_down=GPIO.PUD_UP) # Set pin to INPUT. Will EARTH when triggered.

class outputpin():
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


# ------------------------------------------------------------------------------------------------------

class microcontroller(attributemaster):
    """ Class to manage the UART communication between the RPi and the motor microcontroller. 
        This handles I/O and buffering of inbound/outbound messages over the UART lines.
        It also represents the entire motorcontroller PCB.

        Creating an instance of this object is not enough to initiate communication.
        - You must then call the 'initiate()' method to kick things off.

                mctl = microcontroller(port='/dev/serial0',resetpin=Parameters.MctlResetPin,boardtype=Parameters.BoardType) # Create communication with microcontroller over uart0 serial port.
                mctl.Log = MainLog.Log # Tell which Logging function to use for main logfile messages.
                mctl.Initiate() # Initiate communication.
        """
    def __init__(self,port='/dev/serial0',resetpin=4,boardtype=None):
        """ 
            port = serial port to use for UART communication. 
            resetpin = pin used to control reset or power for the microcontroller. 
            boardtype = Identifier of specific motorcontroller board. 
                        Motorcontrol board behaviour may change depending upon the board type.
                None = Default (as per Instructables 2023-11 launch) 
                                     Voltmeter on adc0 is used.
                "Ton-2023-12" = Raspberry Pi 4 HAT format with onboard 5V power source. 
                                     Voltmeter on adc0 is not used.
                "Matt-2023-12-06"  = Basic PCB board design published just after Instructables project published. 
                                     Voltmeter on adc0 it not used. """
        self.BoardType = boardtype
        # Depending upon the BoardType we can flag certain behaviours and capabilities.
        #if self.BoardType in ['Ton-2023-12','Matt-2023-12-06']: self.SupportsVoltmeter = False # Motorcontrol voltage is not available on adc0.
        #else: self.SupportsVoltmeter = True # Motorcontrol voltage will be monitored on adc0.
        self.SupportsVoltmeter = False # Motorcontrol voltage will be NOT monitored on adc0.
        if self.BoardType in ['Ton-2023-12']: self.SupportsMode0 = self.SupportsMode1 = self.SupportsMode2 = False # The microstepping modes are not supported.
        else: self.SupportsMode0 = self.SupportsMode1 = self.SupportsMode2 = True # The microstepping modes are supported.
        
        # Now initiate communication with the microcontroller.
        self.uart = serial.Serial(port,115200,timeout=0,exclusive=True)
        self.Log = None # Handle to the method/function which will be used for logging messages.
        self.QueueToMctl = Queue() # Use queue mechanism to send commands to the microcontroller communication thread. 
        self.QueueFromMctl = Queue() # Use queue mechanism to receive commands from the microcontroller communication thread. 
        self.ResetPin = resetpin # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
        self.Lines = [] # No lines received yet.
        self.WriteChunkBytes = 32
        self.WriteChunkSeconds = 0.2 # Seconds between chunks written to microcontroller.
        self.InputLine = ''
        self.WriteQueue = [] # No output to send yet.
        self.LinesReceived = 0
        self.LinesSent = 0
        self.BytesReceived = 0
        self.BytesSent = 0
        self.PrintComms = False # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
        self.LedStatus = True # LEDS on by default.
        self.LineOpenedTime = NowUTC()
        self.LastTxTime = NowUTC() # When was data last sent?
        self.LastRxTime = NowUTC() # When was data last received?
        self.RxErrors = 0
        self.LastLineSent = None # We get 'reflection' on the UART port if the remote device isn't ready. This needs ignoring.
        self.CommsTimeout = Parameters.MctlCommsTimeout # Seconds. microcontroller is restarted if no data received after this period.
        self.ForcedRestarts = 0 # How many restarts have been forced by this software?
        self.RemoteRestarts = 0 # How many restarts have been registered by the remote device itself?
        self.ResetAttempts = 0 # Increment for each sequential attempt to reset communication with the remote microcontroller board.
        self.PoweredByUsb = False # If the device is connected by USB, then power handling is different.
                                    # Power to Microcontroller comes through USB cable, DO NOT enable power via the GPIO!
        UsbList = SDCardMonitor.ListUSBdevices() # List all the potential devices. If the CIRCUITPYTHON device is connected via USB, say so here!
        for dn,dl in UsbList: # Check all connected USB devices.
            if dl in ['CIRCUITPY']: # Circuit Python device has USB connection. We cannot power it by GPIO at the same time!
                self.PoweredByUsb = True # Don't allow GPIO power pin to be used.
                print("microcontroller.__init__(): Detected that the microcontroller",dl,"is potentially being powered over USB. (WARNING)")
                lines = ["Detected a connected USB device labelled " + str(dl) + ".",
                         "This looks like it's a microcontroller.",
                         " ",
                         "The microcontroller could receive conflicting voltages via the",
                         "USB line  and the GPIO header . These may damage the devices.",
                         " ",
                         "For safety, the 'enable' pin for microcontroller power will not be used.",
                         "It will be  permanently  powered  via the USB cable instead.",
                         " ",
                         "This means  pi-lomar  cannot  power cycle  the  microcontroller  if it needs to",
                         "reset it. It also means that the  microcontroller  clock may get  independently",
                         "synchronised by the USB connection as well as by the pi-lomar software.",
                         " ",
                         "The software will continue to run, but there is a risk of unexpected behaviour.",
                         " ",
                         "Concurrent USB + GPIO connections  to the microcontroller are recommended only",
                         "during development or debugging with special care taken to protect the devices."]
                textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.ORANGERED1)       
        if self.ResetPin != None:
            GPIO.setup(self.ResetPin, GPIO.OUT)
            if self.PoweredByUsb == False: # If no USB power, we're powering it via a GPIO signal.
                # Never turn on second power source to the microcontroller if it's already got USB power.
                GPIO.output(self.ResetPin, GPIO.HIGH) # Makes sure the pin is HIGH, otherwise the microcontroller resets.
        self.DeviceFailure = False # Set to TRUE if device seems to be irrecoverably lost.
        self.ErrorWindow = None
        self.WriteProhibited = False # OK to write again to the write queue.
        self.SendId = 0 # Incremental counter, the message number being sent to the microcontroller. The microcontroller will respond that this message number has been received.
        # Calling program needs to call microcontroller.Initiate() to get things going.

    def StartMonitor(self):
        """ Start replicating communications to the terminal. 
            The messages are still logged. """
        if self.Log != None:
            self.Log("microcontroller.StartMonitor()",terminal=False)
        self.PrintComms = True # UART comms will be echoed to the terminal.

    def EndMonitor(self):
        """ Stop replicating communications to the terminal. 
            The messages are still logged. """
        if self.Log != None:
            self.Log("microcontroller.EndMonitor()",terminal=False)
        self.PrintComms = False # UART comms will not be echoed to the terminal.

    def PowerOn(self):
        """ Overrides all safeties, turns power GPIO power pin on for microcontroller. """
        if self.ResetPin == None:
            self.Log("microcontroller.PowerOn(): No Reset pin defined.",terminal=True)
            return
        authority = AskYesNo("No safety checks. Do you want to turn ON GPIO power for the microcontroller [y/N]?",False,fg=textcolor.ORANGERED1,bg=textcolor.BLACK)
        if authority:
            self.Log("microcontroller.PowerOn(): No safety checks. GPIO POWER PIN turned on for Microcontroller.",terminal=True)
            GPIO.output(self.ResetPin, GPIO.HIGH)

    def PowerOff(self):
        """ Overrides all safeties, turns power GPIO power pin off for microcontroller. """
        if self.ResetPin == None:
            self.Log("microcontroller.PowerOff(): No Reset pin defined.",terminal=True)
            return
        authority = AskYesNo("No safety checks. Do you want to turn OFF GPIO power for the microcontroller [y/N]?",False,fg=textcolor.ORANGERED1,bg=textcolor.BLACK)
        if authority:
            self.Log("microcontroller.PowerOff(): No safety checks. GPIO POWER PIN turned off for Microcontroller.",terminal=True)
            GPIO.output(self.ResetPin, GPIO.LOW)

    def PowerIsOn(self):
        """ Return TRUE if power is on, FALSE otherwise. 
            This uses GPIO.input(self.ResetPin) even though the pin is defined as an output,
            it still works and returns the state of the pin. """
        return GPIO.input(self.ResetPin)


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
        self.SetClock() # Set the time on the microcontroller.

    def ReportBoard(self):
        """ Report the board type to the log file. """
        self.Log("microcontroller.ReportBoard:",self.BoardType,terminal=False)
        
    def SetClock(self):
        """ Set the microcontroller clock. """
        line = 'set time ' + CleanDatetimeString(str(NowUTC())) # Immediately send a time update to the microcontroller to synchronise the clocks ASAP.
        self.Write(line)
        self.Log("microcontroller.SetClock(): Setting time to",line,terminal=False)

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
                      fresh observation to be set up. It doesn't indicate any fault in the microcontroller.

            If a USB connection is detected to the microcontroller, then a reset can only be a soft reset
            where we request the software itself to restart itself.

            If there is no USB connection, then the power is controlled via a GPIO pin, so we can perform 
            a hard reset by cycling the power or sending a 'low' signal to a reset pin if the microcontroller has one.
            (It's the same mechanism, but the result depends upon your chosen microcontroller and circuitry. """
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
        # The behaviour will depend upon the circuitry supporting the chosen microcontroller.
        if self.PoweredByUsb: # Powered by USB, so cannot power cycle it. Send a RESET command instead.
            MainLog.Log("microcontroller.Reset(): Device is connected via USB, will not enable power via GPIO for safety.",terminal=False)
            DevWindow.Print(NowHMS() + " Microcontroller is powered by USB, performing software reset.")
            # Send software 'reset' command instead.
            self.Write('reset')
            # self.WriteFlush() # Make sure all commands are flushed through. When initializing for the first time, the write process isn't running! This won't flush.
        else: # Not USB power, so can power cycle the microcontroller to reset it.
            # GPIO pin is driven low for a second. This either triggers the microcontroller's reset pin directly (eg Pico RP2040, Feather RP2040 etc),
            # or it can simply switch off the power to a microcontroller that lacks a reset pin (eg Tiny2040).
            DevWindow.Print(NowHMS() + " Microcontroller is powered by GPIO, performing power reset.")
            GPIO.output(self.ResetPin, GPIO.LOW)
            time.sleep(1) # Pause 1 second.
            GPIO.output(self.ResetPin, GPIO.HIGH)
            time.sleep(1) #Pause 1 second.
        self.uart.reset_output_buffer()
        self.uart.reset_input_buffer()
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
            #Led1.On()
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

                    # If we are not currently running an observation, nothing is reading the queue, so flush anything too old.
                    while len(self.Lines) > Parameters.UartRxQueueLimit:
                        delline = self.Lines.pop(0) # Kill the oldest lines first.

                self.InputLine = '' # Start a fresh input line next time anything is received. 
            else: self.InputLine += response # Add the character to the input line we are constructing. 

    def Read(self):
        """ Return the next input line received (if there is one).
            Validate checksum and ignore anything which fails.
            This pulls the next input line from the received buffer.
            It does not poll the UART input line directly (See ReadPoll() method). """
        result = ''
        while len(result) == 0 and len(self.Lines) > 0: # No valid line to return yet, and still lines available in the receive buffer.
            result = self.Lines.pop(0).strip()
            if self.ValidateChecksum(result): # Line is good, remove the checksum.
                cleanresult = self.RemoveChecksum(result)
            else: # Line is bad. Don't clean it.
                cleanresult = result
            self.Log('RPi received: ' + cleanresult,terminal=False)
            if self.PrintComms: print(textcolor.cyan('RPi received: ' + cleanresult))

            MctlRxWindow.Print(cleanresult)
            if self.ValidateChecksum(result): # Line is good.
                result = cleanresult # self.RemoveChecksum(result)
                if result == 'pico started' or result == 'controller started': 
                    self.RemoteRestarts += 1 # Record how many times the remote device reports a restart.
                    ErrorWindow.Print(NowHMS() + " " + result)
                if 'error' in result:
                    print(textcolor.red('RPi received: ') + result)
                    ErrorWindow.Print(NowHMS() + " RPi received: " + result)
            else: # Checksum failure.
                MctlRxWindow.Print('RPi rejected checksum on: ' + result)
                self.Log('RPi rejected checksum on: ' + result,terminal=False)
                self.RxErrors += 1
                ErrorWindow.Print(NowHMS() + " RPi rejected checksum on: " + result)
                result = ''
            # Some messages we can deal with immediately without passing back to the calling routines.
            if result.startswith('#'): result = '' # Ignore comments.
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
        self.uart.write(line.encode('utf-8')) # Send data in UTF-8 format. 
        self.LastTxTime = NowUTC() # Note that time of the last data sent. 

    def ReadFlush(self):
        """ Clear the input buffer. Don't actually process them, because you may never reach the end if 
            new messages are appearing. Just clear and reset the internal buffer of messages received. """
        self.Log('microcontroller.ReadFlush: Drop',len(self.Lines),'unprocessed messages received from microcontroller...',terminal=False)
        if len(self.Lines) > 0:
            for line in self.Lines:
                self.Log('microcontroller.ReadFlush: Dropped line:',line,terminal=False)
            self.Lines = [] # Empty the queue.
        if len(self.InputLine) > 0:
            self.Log('microcontroller.ReadFlush: Abandoned partly received input line (',self.InputLine,')',terminal=False)
            self.InputLine = '' # Scrap any line currently being received and constructed.
        
    def WriteFlush(self,send=True):
        """ Make sure the output buffer is completely flushed. Timeout after a limited number of attempts.
            This doesn't add anything to the output queue, it just makes sure that everything
            waiting to be sent is transmitted.
            if send parameter is false, the write queue is flushed without sending anything further. """
        result = True
        if send: # We should try to send outstanding messages.
            self.Log('Flushing microcontroller output queue (',len(self.WriteQueue),'pending messages will be sent)...',terminal=False)
            TryCount = 0
            self.WriteProhibited = True # Don't allow anything further to be added to the queue at the moment.
            while len(self.WriteQueue) > 0:
                TryCount += 1
                self.Log("WriteFlush: Queue currently",len(self.WriteQueue),"entries",terminal=False)
                time.sleep(0.1) # Pause until the CommsLoop thread has cleared the buffer.
                if TryCount >= 500:
                    self.Log('Flush timeout. Maximum loops.',len(self.WriteQueue),'Remaining messages will be dropped.',terminal=False)
                    self.WriteQueue = [] # Delete any remaining messages in the queue.
                    result = False
                    break
            self.WriteProhibited = False # OK to write again to the write queue.
        else: self.Log('Flushing microcontroller output queue (',len(self.WriteQueue),'pending messages will be dropped)...',terminal=False)
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
            if self.PrintComms: print(textcolor.green('RPi queueing (Q# ' + str(len(self.WriteQueue)) + '): ' + line))


    def CommsLoop(self,commandqueue): # Runs as own thread.
        """ This runs in its own thread, it just continually reads/writes
            to the microcontroller via the uart serial connection.
            It terminates when the main thread dies.
            You can send commands to this communication loop itself via the commandqueue queue.
            - Eg : 'stop' to shut down the loop completely. """
        self.Log('microcontroller.CommsLoop(): Start',terminal=False)

        prevloop = NowUTC()
        while True: # Loop until explicitly told to break.
            # Warn if the loop is running slowly.
            tn = NowUTC()
            td = (tn - prevloop).total_seconds()
            if td > 1:
                self.Log("microcontroller.CommsLoop(): Loop slow. Took",td,"seconds.",terminal=False)
            prevloop = tn
            # Exchange messages with the microcontroller.
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

def InitiateMctl():
    """ Start up fresh communication with the microcontroller. """
    MainLog.Log('Establishing serial UART communication with microcontroller...',terminal=False)
    mctl = None
    try:
        mctl = microcontroller(port='/dev/serial0',resetpin=Parameters.MctlResetPin,boardtype=Parameters.BoardType) # Create communication with microcontroller over uart0 serial port.
        mctl.Log = MainLog.Log # Tell which Logging function to use.
        mctl.ReportBoard() # Log the board type now that the log file is defined.
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
        print (textcolor.yellow("This copy of the pilomar is pid",os.getpid()))
        MainLog.RaiseException(e,comment='InitiateMctl') # Trap all the exception information in the main log file.
    return mctl
    
# ------------------------------------------------------------------------------------------------------

Mctl = InitiateMctl() # Create new microcontroller instance. 
if Mctl == None: # Microcontroller couldn't start.
    MainLog.Log("InitiateMctl failed to create Microcontroller instance.",level='error')
    exit() # Quit the program.

def SetGlobalLedStatus():
    try:
        Mctl.SetLedStatus(Parameters.MctlLedStatus) # Set the LED status on the microcontroller.
    except Exception as e:
        MainLog.RaiseException(e,comment='SetGlobalLedStatus') # Trap all the exception information in the main log file.

# ------------------------------------------------------------------------------------------------------

def StartMctlComms():
    """ This runs the microcontroller communications in a separate thread.
        This should keep communication flowing even if the main thread
        is busy with other tasks.
        (Python does not have truly concurrent threads, so it may still pause sometimes.)
        This does not generate or process messages in either direction, it ONLY handles the
        transfer of queued messages between the RPi and Microcontroller via the UART channel. 
        
        To see where the messages are analysed and processed you need to view the Session.MctlHandler method. """
    # Communication between the MctlComms thread and the main thread is through the UartControlQueue.
    Mctl.CommsLoop(UartControlQueue)

# ------------------------------------------------------------------------------------------------------

# Run the microcontroller communications in a separate thread.
MctlThread = threading.Thread(target=StartMctlComms,args=(),daemon=True) # Run microcontroller communication independently, quit automatically.
MctlThread.start()

# ======================================================================================================

MainLog.Log('Preparing motor control...',terminal=False)

# ------------------------------------------------------------------------------------------------------

class motorcontrol(attributemaster): 
    """ Representation of remote motor.
        The actual motor is controlled in the microcontroller software,
        this class contains an image of important parameters for
        the motor so that this program can direct it. """
        
    AllMotors = [] # A list of all sibling motors which is common to all instances of motorcontrol. So any single motor instance can refer to all the other motors if needed via motorcontrol.AllMotors.

    def __init__(self,name,gearratio,fullstepsperrev,microstepratio,minangle,maxangle,restangle,currentangle,backlashangle,orientation=1,limitangle=None,fasttime=0.002,slowtime=0.05,timedelta=0.003,driver='drv8825'):
        """ Initialize with values that we know from the physical construction of the motor.
            Other values can be configured later by the remote server. """
        self.Log = MainLog.Log # Handle to logging function/method to be used by this class.
        # Validate microstepratio. Reset to 'full steps' if not recognised.
        if driver in Parameters.StepperDriverData: # Driver is recognised.
            modelist = Parameters.StepperDriverData[driver]['modelist'] # Pull the driver's modelist.
            if not str(microstepratio) in modelist: # Keys are strings, not integers.
                self.Log("motorcontrol(",name,") microstepratio",microstepratio,"is not in",driver,"modelist.",level='error',terminal=True)
                raise Exception("motorcontrol(" + str(name) + ") microstepratio " + str(microstepratio) + " is not in " + str(driver) + "modelist.")
            # microstep ratio is recognised. Pull the modepin settings.
            modesignals = modelist[str(microstepratio)]['modesignals']
            self.Log("motorcontrol(",name,") microstepratio",microstepratio,"for",driver,"uses mode settings",modesignals,terminal=False)
        else: # Driver is not recognised.
            self.Log("motorcontrol(",name,") steppermotor driver",driver,"is not recognised.",level='error',terminal=True)
            raise Exception("Steppermotor driver " + str(driver) + " is not recognised.")
        self.MotorName = name # A unique name to identify the motor, should be the same as the motor's name in the microcontroller side too.
        self.Driver = driver # What driver board is being used?
        self.GearRatio = gearratio
        motorstepsperrev = fullstepsperrev * microstepratio # Calculate motorstepsperrev to include microstep ratio.
        self.MotorStepsPerRev = motorstepsperrev # FullStepsPerRev of the motor * any microstepping multiplier.
        self.ModeSignals = modesignals # What are the settings for the mode pins to the driver board?
        self.MicrostepRatio = microstepratio # Just for documentation from this point onwards.
        self.WarningAngle = 10 # Can warn if position is within this angle of a limit.
        self.MinAngle = minangle
        self.MinWarningAngle = minangle + self.WarningAngle # Can warn if within xx degrees of minimum position.
        self.MaxAngle = maxangle
        self.MaxWarningAngle = maxangle - self.WarningAngle # Can warn if within xx degrees of maximum position.
        self.LimitAngle = limitangle # The motor will reverse around a limit rather than crossing it.
        self.Orientation = orientation
        self.BacklashAngle = backlashangle
        self.CurrentAngle = currentangle # This will be updated by the microcontroller once running. 
        self.PreviousAngle = None # Holds angle from previous status message.
        self.PreviousMctlTimestamp = None # Says when the previous angle was set.
        self.RestAngle = restangle
        #self.MotorStepsPerAxisDegree = self.MicrostepRatio * self.MotorStepsPerRev / 360.0
        self.MotorStepsPerAxisDegree = self.MotorStepsPerRev / 360.0
        #self.AxisStepsPerRev = self.MicrostepRatio * self.MotorStepsPerRev * self.GearRatio 
        self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio 
        self.MotorConfigured = False
        self.FastTime = fasttime # Fastest pulse to the motor STEP signal. (Full speed in large move.) # Was 0.0005
        self.SlowTime = slowtime # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
        self.TimeDelta = timedelta # Acceleration rate for the motor STEP signal. 
        self.TrajectorySegmentSize = 60 # Seconds.
        self.TrajectoryValid = False # Is the microcontroller trajectory valid?
        self.TrajectoryEntries = 0 # Number of trajectory entries stored on the microcontroller.
        self.TrajectoryValidUntil = None # The 'end time' of the trajectory as reported from the microcontroller.
        self.LastSentTrajectoryKey = None # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
        self.LastSentTrajectoryData = None # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.
        self.OnTarget = False # Is the motor currently on target? 
        self.LatestTuneStart = None # When did motor last START a TUNE move? (Images could be blurred)
        self.LatestTuneTime = None # When did motor last COMPLETE a TUNE command? (Images could be blurred)
        self.LatestTuneSteps = 0
        self.RecoveryFolder = ProjectRoot + "/data/" + self.MotorName + "_angle"
        self.RecoveryFileName = self.RecoveryFolder + "/" + UtcTimeStamp() + ".log" # Used to record the position of the motor, this can then recover the situation in the event of any failures.
        VerifyFolder(self.RecoveryFolder) # Make sure that the recovery folder exists.
        self.RestoreAngle()
        self.LastRecoveryAngle = self.CurrentAngle # This is used to detect when the motor has physically moved so we don't keep writing the same position repeatedly to the recovery file.
        self.Log('Motor ' + self.MotorName + ' recovered to ' + str(round(self.CurrentAngle,5)) + DegreeSymbol,terminal=False)
        self.AllMotors.append(self) # Class attribute AllMotors points to ALL sibling motors. Can be used to check condition of any other motors too.
        self.StatusMctlTimestamp = None # When did the Microcontroller send the latest status message?
        self.StatusLocalTimestamp = None # When did the RPi process the latest status message?
        self.MotorSpeed = 0.0 # Currently calculated motor speed (degrees/second).
        self.MonitorMove = False # Set to True to enable text updates as moves are performed. False to suppress. GoToAngle(), HomePosition(), SetMotorAngle respect this.
        self.Restarted() # Make sure that status flags are reset for a 'new' unconfigured motor.

    def __del__(self):
        """ When deleted, remove this motor from the global list of all available motors. """
        self.AllMotors.remove(self) # Class attribute AllMotors points to ALL sibling motors. Remove this motor from the list when deleted.

    def ShowMotorStatus(self):
        """ Print general status of the motor. """
        print("Motor:",self.MotorName)
        print("Driver:",self.Driver)
        print("CurrentAngle:",Deg3dp(self.CurrentAngle,DegreeSymbol))
        print("Position:",self.AngleToStep(self.CurrentAngle),"steps")
        print("GearRatio:",self.GearRatio)
        print("MotorStepsPerRev:",self.MotorStepsPerRev)
        print("MicrostepRatio:",self.MicrostepRatio,"(included in MotorStepsPerRev)")
        print("ModeSignals:",self.ModeSignals)
        print("MinAngle:",Deg3dp(self.MinAngle,DegreeSymbol))
        print("MinWarningAngle:",Deg3dp(self.MinWarningAngle,DegreeSymbol))
        print("MaxAngle:",Deg3dp(self.MaxAngle,DegreeSymbol))
        print("MaxWarningAngle:",Deg3dp(self.MaxWarningAngle,DegreeSymbol))
        print("Orientation:",self.Orientation)
        print("BacklashAngle:",Deg3dp(self.BacklashAngle,DegreeSymbol))
        print("RestAngle:",Deg3dp(self.RestAngle,DegreeSymbol))
        print("MotorStepsPerAxisDegree:",self.MotorStepsPerAxisDegree)
        print("AxisStepsPerRev:",self.AxisStepsPerRev)
        print("MotorConfigured:",self.MotorConfigured)
        print("FastTime:",self.FastTime,"s")
        print("SlowTime:",self.SlowTime,"s")
        print("TimeDelta:",self.TimeDelta,"s")
        if self.MotorSpeed != None:
            print("Latest MotorSpeed:",str(round(self.MotorSpeed,4)) + DegreeSymbol + "/s")
        else:
            print("Latest MotorSpeed:",self.MotorSpeed,DegreeSymbol + "/s")
        print("TrajectorySegmentSize:",self.TrajectorySegmentSize,"s")
        print("TrajectoryValid:",self.TrajectoryValid)
        print("TrajectoryEntries:",self.TrajectoryEntries)
        print("TrajectoryValidUntil:",self.TrajectoryValidUntil,"UTC")
        print("OnTarget:",self.OnTarget)
        print("LatestTuneStart:",self.LatestTuneStart,"UTC")
        print("LatestTuneTime:",self.LatestTuneTime,"UTC")
        print("LatestTuneSteps:",self.LatestTuneSteps)
        print("RecoveryFileName:",self.RecoveryFileName)
        print("")

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
        self.StatusMctlTimestamp = None # When did the Microcontroller send the status message?
        self.StatusLocalTimestamp = None # When did the RPi process the status message?
        #self.PrevVoltageTimestamp = None # The timestamp of the last status message received from the motorcontroller.
        self.PreviousAngle = None # Holds angle from previous status message.
        self.PreviousMctlTimestamp = None # Says when the previous angle was set.

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

    def RestoreAngle(self):
        """ This searches for the last recorded position of the motor and restores that state. 
            The last recorded position is stored in a file in the self.RecoveryFolder. """
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
            self.Log("No recovery log file found for " + self.MotorName + " motor. Assuming " + Deg3dp(self.RestAngle,DegreeSymbol))
            return False
        angle = self.RestAngle # Default to home position.
        with open(filename) as file_in: # Read all the positions in the file, could be smarter and go to the end of the file here.
            for line in file_in: # Lines will be on chronological sequence. We keep that latest valid entry as the last known position of the motor. 
                line = line.strip() # Trim unwanted characters from line.
                ls = line.split(";") # Format is 'timestamp';'angle';'seconds'
                if len(ls) > 1: angle = float(ls[1]) # 'timestamp';'angle';'seconds'
                else: self.Log("Bad recovery entry (" + line + "), angle ignored.",level='warning')
        self.CurrentAngle = angle
        self.Log(self.MotorName,"motor restored to last known position", self.AngleToStep(self.CurrentAngle), "(", Deg3dp(self.CurrentAngle,DegreeSymbol), ")")
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
            Expects input like          tune complete azimuth yyyymmddhhmmss -342 yyyymmddhhmmss     
                                          0     1        2          3          4        5             """
        self.Log("Motor",self.MotorName,"received tune acknowledgement:",line,terminal=False)
        lineitems = line.split(" ") # Separate each element of the line. 
        if len(lineitems[3]) >= 14: 
            self.LatestTuneTime = MctlStringToDatetime(lineitems[3]) # Element #3 is the timestamp of the last tune command completed.
        else: # Bug in early version of microcontroller software, timestamp returned as integer. Just use current time instead.
            self.LatestTuneTime = NowUTC()
            self.Log("Motor",self.MotorName,"received old format tune acknowledgement. Please update it!",level='warning',terminal=False)
        steps = TextToInt(lineitems[4])
        endtime = lineitems[3] # When did the tune complete?
        if len(lineitems) > 5: # When did the tune start?
            self.LatestTuneStart = MctlStringToDatetime(lineitems[5]) # Start time known.
        else:
            self.LatestTuneStart = self.LatestTuneTime # Start time not known.
        self.Log("motorcontrol.TuneComplete: LatestTuneSteps:",steps,terminal=False)
        self.LatestTuneSteps = TextToInt(steps) # Element 4 is the number of steps that the tune command executed.

    def StoreRecoveryAngle(self,force=False):
        """ Records the latest position of the motor for recovery purposes. 
            This is appended to self.RecoveryFileName if the position has changed.
            This data is used to restore the state of the motor when the program next restarts. 
            This is designed to retry if there is a file error, just in case there's an access conflict with any other reader/monitor. 
            force=True: A value is stored even if the motor hasn't moved. """
        counter = 100 # Only try 100 times, then fail.
        if force or self.CompareAngles(self.CurrentAngle,self.LastRecoveryAngle) == False: # The motor has actually moved! 
            success = False
            while counter > 0:
                counter -= 1
                try:
                    with open(self.RecoveryFileName,'ab',0) as f: # Python3: Don't buffer. Note that the O/S may still have to flush buffers itself.
                        f.write((UtcTimeStamp() + ";" + str(self.CurrentAngle) + "\n").encode()) # Convert text to bytes.
                    self.LastRecoveryAngle = self.CurrentAngle
                    success = True
                    #self.Log("steppermotor.StoreRecoveryAngle (", self.MotorName, ") Updated to",self.CurrentAngle,"from",self.LastRecoveryAngle,"in the recovery file.",terminal=False)
                    break # Success, so don't try again.
                except Exception as e:
                    self.Log("steppermotor.StoreRecoveryAngle (", self.MotorName, ") to", self.RecoveryFileName, ". File conflict", str(e), "waiting to retry.",level='warning')
                    time.sleep(0.3)
            if not success: self.Log("steppermotor.StoreRecoveryAngle (", self.MotorName, ") to", self.RecoveryFileName, ". Failed to write data.",level='error')

    def GoToAngle(self,newangle):
        """ Trigger 'goto angle' movement of the motor via the remote microcontroller. 
            This version can accept status messages from all motors.
                goto 20210409090949 azimuth 180.0
                    0       1          2      3         """
        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Begin move from ', Deg3dp(self.CurrentAngle,DegreeSymbol), 'to', Deg3dp(newangle,DegreeSymbol), '(', str(self.AngleToStep(newangle) - self.AngleToStep(self.CurrentAngle)) , 'step difference)',terminal=False)
        result = False # Failed until proven otherwise.

        # Clip angles to min/max allowed. The motor won't pass beyond these points, so the routine will wait forever for it to complete.
        if newangle < self.MinAngle:
            self.Log('motorcontrol.GoToAngle(', self.MotorName, '): move limited to minimum', Deg3dp(self.MinAngle,DegreeSymbol), terminal=False)
            newangle = self.MinAngle
        if newangle > self.MaxAngle:
            self.Log('motorcontrol.GoToAngle(', self.MotorName, '): move limited to maximum', Deg3dp(self.MaxAngle,DegreeSymbol), terminal=False)
            newangle = self.MaxAngle

        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Clear unprocessed messages received from microcontroller.', terminal=False)
        Mctl.ReadFlush() # Reset the input buffers. Scrap anything still waiting to be processed.

        # The following section 'repeats' in the event of the microcontroller resetting during a large move.
        # It repeats until the motor is finally at the target position.
        # Check that the motors are configured before proceeding.
        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Configure motor',terminal=False)
        #configtimer = timer(5) # Create a timer for sending and resending configurations to motors.
        loopcounter = 0
        looplimit = 20
        # Keep trying until limit hit, or we are close enough to the target position.
        # - Allow a little tolerance for calculation rounding etc.
        while self.CompareAngles(self.CurrentAngle,newangle,ptolerance=1) == False: # Position tolerance of 1 works best here.
            loopcounter += 1
            if loopcounter > 1:
                self.Log("motorcontrol.GoToAngle(",self.MotorName,"): Begin attempt",loopcounter,"of",looplimit,terminal=True)
            else:
                self.Log("motorcontrol.GoToAngle(",self.MotorName,"): Begin attempt",loopcounter,"of",looplimit,terminal=False)
            # In each attempt, first check that the motor is configured. This should happen automatically, but check in case of an unexpected remote reset.
            rt = timer(60) # Allow 60 seconds, if no response, reset the microcontroller.
            if self.MotorConfigured:
                self.Log("motorcontrol.GoToAngle(", self.MotorName, "): Motor already configured.",terminal=False)
            else:
                self.Log("motorcontrol.GoToAngle(", self.MotorName, "): Motor is not yet configured.",terminal=False)
            mcl = 0 # How many attempts to configure the motor?
            while self.MotorConfigured == False: # Send configuration to the motor until it's acknowldeged. (May take a few seconds).
                mcl += 1 # Count how many times we've sent the configuration.
                if mcl > 15: # Too many attempts.
                    self.Log("motorcontrol.GoToAngle(", self.MotorName, "): Motor has failed to configure. Abandoning GOTO.",level='error')
                    return False # Report failure.
                self.SendConfig() # Send the motor configuration regularly.
                if self.MotorConfigured: 
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): CheckMotorConfig: Motor reports it is now configured.',terminal=False)
                    break # All motors configured. OK to proceed.
                time.sleep(5) # Pause a moment.
                if rt.Due(): # It's time to try resetting the microcontroller.
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): CheckMotorConfig: Motor config not acknowledged. Resetting microcontroller.',terminal=True)
                    Mctl.Reset(planned=True)
                self.Log("motorcontrol.GoToAngle(",self.MotorName,"): Not yet configured. Trying to configure again.",terminal=False)
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
            # 3rd task is to wait for the motor to complete.
            if self.MonitorMove: # Display movement progress.
                print(NowHMS(),self.MotorName,Deg3dp(self.CurrentAngle,DegreeSymbol),textcolor.clearlineforward())
            while True:
                if prevangle != self.CurrentAngle: # The motor has moved.
                    prevangle = self.CurrentAngle
                    prevangletime = NowUTC()
                    if self.MonitorMove: # Display movement progress.
                        print(textcolor.cursorup(),NowHMS(),self.MotorName,Deg3dp(self.CurrentAngle,DegreeSymbol),textcolor.clearlineforward())
                if self.CompareAngles(self.CurrentAngle,newangle,ptolerance=2): # Sometimes there's a mathematical disagreement between microcontroller and this software. So allow a small tolerance when comparing angles.
                    # Move complete.
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): CompareAngles considers position is within tolerance, move considered complete.',terminal=False)
                    result = True # Success.
                    break
                if (NowUTC() - prevangletime).total_seconds() > 60: # The angle hasn't changed for 60 seconds. Consider something's wrong.
                    # *Q* A common reason for the timeout is a large backlog of configuration messages being exchanged.
                    # - This can be caused by running the program as far as the main menu, but not starting an observation for a very long time.
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Angle has not changed for over 60 seconds. Will retry.',terminal=False)
                    break
                time.sleep(1) # Don't poll too often.
            if loopcounter >= looplimit: 
                self.Log("motorcontrol.GoToAngle(", self.MotorName, "): After",looplimit,"attempts, motor move still not complete. Abandoning the move at", self.CurrentAngle, DegreeSymbol, ".",level='error')
                ErrorWindow.Print(NowHMS() + ' ' + str(looplimit) + ' GOTO attemps failed.')
                break
        # *Q* If the motor is already within tolerance but not precisely in position, you can get a false alarm here. 
        # This is typically when you're asking it to move a single motor step in isolation.
        # In practice this is because the motor won't be asked to move if it's already within tolerance.
        # - Workarounds:-
        #   Move both motors by 10Degrees in any direction, which will increase the positions beyond the tolerances to allow homing again.
        self.Log('motorcontrol.GoToAngle(', self.MotorName, '): Move completed: Got', Deg3dp(self.CurrentAngle,DegreeSymbol), ", expected", Deg3dp(newangle,DegreeSymbol),terminal=False)
        return result # Did we succeed?

    def CalculateMotorSpeed(self):
        """ Based upon last 2 valid status messages, what speed is the motor currently moving at? 
            Degrees per second returned. """
        anglechange = 0.0
        timechange = 0.0
        self.MotorSpeed = 0.0 # No speed unless we know it!
        if self.CurrentAngle != None and self.PreviousAngle != None:
            anglechange = self.CurrentAngle - self.PreviousAngle
        if self.StatusMctlTimestamp != None and self.PreviousMctlTimestamp != None:
            timechange = (self.StatusMctlTimestamp - self.PreviousMctlTimestamp).total_seconds()
        if timechange != 0.0:
            self.MotorSpeed = anglechange / timechange

    def EstimateCurrentAngle(self):
        """ Given current system clock and the latest status information from the motorcontroller, estimate the current angle of the motor. """
        if self.MotorSpeed != None and self.StatusMctlTimestamp != None:
            timechange = (NowUTC() - self.StatusMctlTimestamp).total_seconds() # Seconds since last position sent. 
            anglechange = self.MotorSpeed * timechange # How many degrees has the motor probably moved in this time?
            angle = (self.CurrentAngle + anglechange) % 360 # Where is the motor likely to be now (0-360 degree range)
            #self.Log("motorcontrol.EstimateCurrentAngle(",self.MotorName,"): In",timechange,"seconds since",self.StatusMctlTimestamp,"motor moved",anglechange,"deg to",angle,"deg.",terminal=False)
        else:
            angle = self.CurrentAngle # Just use latest static angle we know.
            #self.Log("motorcontrol.EstimateCurrentAngle(",self.MotorName,"): No speed yet. Static at",angle,"deg.",terminal=False)
        return angle

    def PositionAge(self):
        """ How old (seconds) is the position measurement? """
        age = 0
        if self.StatusMctlTimestamp != None:
            age = round((NowUTC() - self.StatusMctlTimestamp).total_seconds(),0)
        if age > 30:
            self.Log("motorcontrol.PositionAge(",self.MotorName,") position",self.CurrentAngle,"from",self.StatusMctlTimestamp,"is stale (",age,"seconds).",terminal=False)
        return age
        
    def ReceiveStatus(self,line):
        """ Receive Status of a motor and store important parameters
            in this local motor image. 
            
            This is usually called via CheckMotorStatus(line) which protects updates from unconfigured motors, and handles missing configurations automatically.
            This also protects from unconfigured status messages, but will not directly handle the consequences.

        Sample message:-
            motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y y 3939 345
              0      1          2           3   4         5      6   7     8   9 10 11  12
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
        12: str(VMot()) Current motor power supply voltage. - Feature withdrawn, now always '0'.
        13: Reason. Code explaining WHY the status message was sent.
                                                                       """
        lineitems = line.split(' ')
        configuredflag = StringToBool(lineitems[9]) # Is the motor configured?
        if configuredflag != self.MotorConfigured: 
            self.Log("motorcontrol.ReceiveStatus(",self.MotorName,"): Configured flag set to ",configuredflag,terminal=False)
        self.MotorConfigured = configuredflag # Update the configured flag.
        if self.MotorConfigured: # Only believe the angle once the motor is configured, otherwise it's just a default value and probably inaccurate.
            self.PreviousAngle = self.CurrentAngle # Store previous position.
            self.CurrentAngle = float(lineitems[8])
            self.StoreRecoveryAngle() # Record the latest position of the motor for restart/recovery later.
            self.TrajectoryValid = StringToBool(lineitems[4])
            self.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
            self.TrajectoryEntries = int(lineitems[6])
            self.OnTarget = StringToBool(lineitems[10]) # Is the motor on target?
        else:
            self.Log("motorcontrol.ReceiveStatus(",self.MotorName,"): Motor is not yet configured. Position and trajectory info ignored. Configuring now.",terminal=False)
            self.SendConfig() # Send motor configuration now.

        # Calculate the following attributes regardless of configuration status.
        self.PreviousMctlTimestamp = self.StatusMctlTimestamp # Store previous timestamp
        self.StatusMctlTimestamp = MctlStringToDatetime(lineitems[2]) # When did the Microcontroller send the status message?
        self.Log("motorcontrol.ReceiveStatus(",self.MotorName,"): StatusMctlTimestamp now",self.StatusMctlTimestamp,"from",line,terminal=False)
        self.StatusLocalTimestamp = NowUTC() # When did the RPi process the status message?
        _ = self.CalculateMotorSpeed() # Check motor speed.

        return True
        
    def SendConfig(self):
        """ Send configuration information from this motor image to the microcontroller
            where it will be loaded into the motor control there. 
                configure motor 20210409090949 azimuth 180.0 45.0 315.0 0.5 -1 0.0005 0.01 0.0005 10 n n 
                    0       1          2          3      4    5     6    7   8   9      10   11  12 13 14 """
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
        line += str(Parameters.MotorStatusDelay) + ' ' # Field 12: Set timer delay for sending motor status back to the RPi.
        line += BoolToString(Parameters.FaultSensitive) + ' ' # Field 13: When 'y' the microcontroller will respect the DRV8825 fault pin to block movement.
        line += BoolToString(Parameters.OptimiseMoves) + ' ' # Field 14: When 'y' the microcontroller can take shortcuts for large moves.
        line += str(self.LimitAngle) + ' ' # Field 15: Movement limit, motor will reverse around rather than crossing this limit.
        line += str(self.GearRatio) + ' ' # Field 16: GearRatio.
        line += str(self.MotorStepsPerRev) + ' ' # Field 17 MotorStepsPerRev
        # line += str(self.MicrostepRatio) + ' ' # Field 18 MicrostepRatio
        line += '1 ' # Field 18 MicrostepRatio / Nolonger used.
        line += str(self.RestAngle) + ' ' # Field 19 RestAngle
        line += self.ModeSignals + ' ' # Field 20 Steppermotor mode signals for microstepping.
        
        Mctl.Write(line)
        self.Log('motorcontrol.SendConfig (' + self.MotorName + ') end',terminal=False)
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
        self.Log('motorcontrol.TunePosition(', self.MotorName,') by',delta,'steps.',terminal=False)
        # There can be input queued from the microcontroller waiting to be handled.
        # - We should check in case the motor has lost its configuration before proceeding.
        self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Precheck motor is still configured.',terminal=False)
                
        # Motor is now configured. Perform the actual move now. 
        if self.MotorConfigured: # Only allow tuning if the motor is configured.
            dtn = NowUTC()
            line = "tune " + CleanDatetimeString(str(dtn)) + ' ' + self.MotorName + " " + str(delta)
            Mctl.Write(line)
            # This doesn't wait for feedback, it is up to the motorcontroller to deal with the message when it sees fit.
            # This program may send further tune messages if it still needs to change things.
        else:
            self.Log("motorcontroller.TunePosition(", self.MotorName, "): Motor is not yet configured. Tune command will not be sent.",level='error')
        self.Log('motorcontrol.TunePosition(',self.MotorName,'):',delta,'step tune command sent to microcontroller.',terminal=False)

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
        if self.LastSentTrajectoryKey == self.TrajectoryValidUntil and self.TrajectoryValidUntil > nowutc: # We have a future result cached already for this...
            self.Log('motorcontroller.ExtendTrajectory(', self.MotorName, '): Using cached trajectory calculation:', "'" + self.LastSentTrajectoryData + "'",terminal=False)
            line += self.LastSentTrajectoryData
            Mctl.Write(line)
            return # No need to process further.
        if self.TrajectoryValidUntil == None: # Where does previously downloaded trajectory end? = Start of this chunk.
            startutc = nowutc
        else:
            startutc = self.TrajectoryValidUntil
        # We're not using a cached record, so continue constructing and calculating a new record.
        line += self.MotorName + ' '
        if startutc < nowutc: # Don't create OLD entries.
            startutc = nowutc
        # Calculate START angle for trajectory segment.
        az, alt = targetobj.AzAltDegrees(time=Datetime2Ts(startutc)) # Needs to be Skyfield time!
        line += CleanDatetimeString(str(startutc)) + ' '
        if self.MotorName == 'altitude': startangle = alt
        else: startangle = az
        line += str(startangle) + ' '
        if targetobj.IsFixedPoint(): # Fixed points can have a larger segment size.
            endutc = startutc + timedelta(seconds=segmentsize * 2) # But not too large because we need multiple segments queued up on the microcontroller, otherwise it may send an off target signal if the trajectory list expires.
        else: 
            endutc = startutc + timedelta(seconds=segmentsize)
        # Calculate END angle for trajectory segment.
        az, alt = targetobj.AzAltDegrees(time=Datetime2Ts(endutc)) # Needs to be Skyfield time! 
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
                nextutc = startutc + timedelta(seconds=segmentsize) # Timestamp of the larger segment size.
                az, alt = targetobj.AzAltDegrees(time=Datetime2Ts(nextutc)) # Needs to be Skyfield time!
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
        self.Log('motorcontroller.ExtendTrajectory(',self.MotorName,') Segment',(endutc - startutc).total_seconds(),'seconds',startutc,round(startangle,4),'deg -',endutc,round(endangle,4),'deg',terminal=False)
        # *Q* Could add a 'please acknowledge' flag to the line, so that we know we can calculate the next segment when needed.
        # line += 'y ' # Please acknowledge. The 'optimistic configuration' idea would eliminate the need for this flag.
        if endangle >= self.MinAngle and endangle <= self.MaxAngle: # We're still within range.
            Mctl.Write(line)
            self.LastSentTrajectoryKey = self.TrajectoryValidUntil # Cache the trajectory calculation, if the same calculation is triggered, we can re-use the earlier copy for speed.
            self.LastSentTrajectoryData = line[26:] # Store the data sent (without the leading timestamp, a fresh timestamp will be used if resent). 
            self.Log('motorcontroller.ExtendTrajectory(', self.MotorName, '): Cached trajectory calculation:', "'" + self.LastSentTrajectoryData + "'",terminal=False)
        else:
            self.Log('motorcontroller.ExtendTrajectory(' + self.MotorName + '): Trajectory is now complete.',terminal=False)

# ------------------------------------------------------------------------------------------------------

# Create and initialize motor instances.
#AzimuthControl = motorcontrol('azimuth',gearratio=240,motorstepsperrev=400,microstepratio=1,minangle=Parameters.MinAzimuthAngle,maxangle=Parameters.MaxAzimuthAngle,restangle=180.0,currentangle=180.0,backlashangle=0.0,orientation=-1,limitangle=Parameters.AzimuthLimitAngle)
#AltitudeControl = motorcontrol('altitude',gearratio=240,motorstepsperrev=400,microstepratio=1,minangle=Parameters.MinAltitudeAngle,maxangle=Parameters.MaxAltitudeAngle,restangle=0.0,currentangle=0.0,backlashangle=0.0,orientation=-1,limitangle=Parameters.AltitudeLimitAngle)
AzimuthControl = motorcontrol('azimuth',
                              gearratio=Parameters.AzimuthGearRatio, # 240 # Gearing of the drive system ignoring motor steps.
                              fullstepsperrev=Parameters.AzimuthMotorStepsPerRev, # 400 # FullStep count of the motor before microstepping added.
                              microstepratio=Parameters.AzimuthMicrostepRatio, # 1 # Level of microstepping to be added. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
                              minangle=Parameters.MinAzimuthAngle, # 0 
                              maxangle=Parameters.MaxAzimuthAngle, # 360
                              restangle=Parameters.AzimuthRestAngle, # 180.0,
                              currentangle=Parameters.AzimuthRestAngle, # 180.0 # Yes it's the same as above!
                              backlashangle=Parameters.AzimuthBacklashAngle, # 0.0
                              orientation=Parameters.AzimuthOrientation, # -1,
                              limitangle=Parameters.AzimuthLimitAngle,
                              fasttime=Parameters.FastTime,
                              slowtime=Parameters.SlowTime,
                              timedelta=Parameters.TimeDelta)
AltitudeControl = motorcontrol('altitude',
                              gearratio=Parameters.AltitudeGearRatio, # 240,
                              fullstepsperrev=Parameters.AltitudeMotorStepsPerRev, # 400 # FullStep count of the motor before microstepping added.
                              microstepratio=Parameters.AltitudeMicrostepRatio, # 1 # Level of microstepping to be added. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
                              minangle=Parameters.MinAltitudeAngle, # 0
                              maxangle=Parameters.MaxAltitudeAngle, # 90
                              restangle=Parameters.AltitudeRestAngle, # 0.0,
                              currentangle=Parameters.AltitudeRestAngle, # 0.0,
                              backlashangle=Parameters.AltitudeBacklashAngle, # 0.0,
                              orientation=Parameters.AltitudeOrientation, # -1,
                              limitangle=Parameters.AltitudeLimitAngle,
                              fasttime=Parameters.FastTime,
                              slowtime=Parameters.SlowTime,
                              timedelta=Parameters.TimeDelta)
MotorControls = motorcontrol.AllMotors #  Alias for the list of ALL defined motors held in the motorcontrol class.

# Assign filename for the 'observation running' flag file. Thie file indicates that an observation started, but has not yet cleanly finished.
# It's not created here, but this is the filename that will be used.
ObservationRunningFile = FolderList['dataroot'] + 'observationrunningflag.txt'

# ------------------------------------------------------------------------------------------------------

def LastReportedLocationDatetime():
    """ What's the oldest datetime stamp of the reported camera locations? """
    result = None
    for i in MotorControls:
        if result == None or (i.StatusMctlTimestamp != None and result > i.StatusMctlTimestamp): result = i.StatusMctlTimestamp
    return result
    
# ------------------------------------------------------------------------------------------------------

def LastReportedAltAz():
    """ Retrieve the current physical position of the camera. 
        Returns values based upon the data stored in the MotorControl objects. """
    az_degree = 0.0
    alt_degree = 0.0
    for i in MotorControls:
        if i.StatusMctlTimestamp != None:
            td = abs(NowUTC() - i.StatusMctlTimestamp).total_seconds()
            if td > 20: # Position is > 20 seconds old. Expect an update more regularly than this.
                MainLog.Log("LastReportedAltAz(",i.MotorName,") position ",Deg3dp(i.CurrentAngle),"deg is stale.",td,"s since",i.StatusMctlTimestamp,"UTC",terminal=False)
        else:
            MainLog.Log("LastReportedAltAz(",i.MotorName,") StatusMctlTimestamp is None.",terminal=False)
        if i.MotorName == "azimuth": 
            az_degree = i.CurrentAngle
        elif i.MotorName == "altitude": 
            alt_degree = i.CurrentAngle
    return alt_degree, az_degree

# ------------------------------------------------------------------------------------------------------

def EstimatedAltAz():
    """ Retrieve the current physical position of the camera. 
        Returns values based upon the data stored in the MotorControl objects. 
        *Q* Currently this continues the current speed, but that becomes inaccurate when target is moving very fast, especially as passing the zenith. 
            Needs to be smarter, or simply use the current target location at the chosen time. """
    az_degree = 0.0
    alt_degree = 0.0
    for i in MotorControls:
        if i.MotorName == "azimuth": az_degree = i.EstimateCurrentAngle()
        elif i.MotorName == "altitude": alt_degree = i.EstimateCurrentAngle()
    return alt_degree, az_degree

# ------------------------------------------------------------------------------------------------------

# Warn if the previous ObservationRun didn't complete, it may have left things in a mess.
if os.path.exists(ObservationRunningFile):
    t_alt, t_az = LastReportedAltAz() # Where does the program THINK the camera is pointing?
    lines = ["The previous observation run did not complete properly.",
             "This may have left the camera positions out of date.",
             "You may need to reset the camera altitude and azimuth",
             "before starting a new observation.", " ",
             AzAltText(t_az,t_alt,DegreeSymbol), " ",
             "If the microcontroller continued running after the program",
             "failed Pi-lomar may not have recorded later movement."]
    textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.ORANGERED1)
    result = input(textcolor.cyan("[ENTER] to continue."))
    
# ------------------------------------------------------------------------------------------------------

def HomeAltAz():
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

class sessionstatus(attributemaster):
    """ Class to hold current status of the observation.
        This can export all the status information to a file so that a remote process can also monitor the status.
        These are the variables that handle a single loop in the ObservationRun routine. """
    def __init__(self):
        """ Initialize status fields. """
        self._FileNames = []
        self.ProgramStartTime = NowUTC() # When the program starts.
        self.Target = None # No target yet. This gets set to a valid target object when the target is selected.
        self.Log = MainLog.Log # Handle to the logging function used by this class.
        self.DebugMode = Parameters.DebugMode # Initialize the debug mode flat for the entire session.
        self.AutonomousControl = False # Is the Microcontroller controlling its own movements?
        self.RemoteControl = False # Will the Microcontroller accept remote control (from here)?
        self.ClockSynchronised = False # Has the Microcontroller synchronised the clock?
        self._ObservationRunning = False # Set to TRUE when observation is running. Resets if not confirmed regularly. Check via ObservationRunning() method.
        self.MctlRxErrors = 0 # How many messages has the Microcontroller rejected? (Checksum errors)
        self.MctlRxBytes = 0 # How many bytes has the Microcontroller received?
        self.MctlTxBytes = 0 # How many bytes has the Microcontroller sent?
        self.MctlExceptionCount = 0 # How many exceptions has the Microcontroller handled?
        self.TrajectorySafetyFlushes = 0 # How many times has the microcontroller flushed a valid trajectory because of a communication break?
        self.CameraTxCount = 0 # Number of messages SENT from RPi to Camera
        self.CameraRxCount = 0 # Number of messages RECEIVED by RPi from Camera
        self.MctlLifeSeconds = 0 # How many seconds has the Microcontroller been running for?
        self.MctlWriteDrops = 0 # How many messages were dropped from send buffer on Microcontroller due to overflow?
        self.MotorControlMode = 'idle' # What mode are we in? 'idle'/'remote'/'autonomous'. This controls the responses to some automated status messages. *Q* Is this needed anymore?
        self.MCMdict = {'idle' : {'description' : 'motors at rest.', 'trajectory' : False},
                        'direct' : {'description' : 'motor movement controlled directly from this software.', 'trajectory' : False},
                        'trajectory' : {'description' : 'motor movement is autonomous following trajectory.', 'trajectory' : True}}
        self.MaintainTrajectory = None
        self.SetMotorControlMode(self.MotorControlMode) # Updates self.MaintainTrajectory
        self.TerminateMctlHandler = False # Set to TRUE to cause MctlHandler loop to terminate.
        self.ControllerVersion = 'unknown' # The microcontroller should report its software version number and store it here.
        self.TimeDiff = None # Timedelta between remote clock and local clock (includes messaging delays).

    def Reset(self):
        self.AutonomousControl = False # Is the Microcontroller controlling its own movements? eg Trajectories.
        self.RemoteControl = False # Will the Microcontroller accept remote control (from here)? eg GoTo, Tune etc.
        self.ClockSynchronised = False # Has the Microcontroller synchronised the clock?
        self.MctlRxErrors = 0 # How many messages has the Microcontroller rejected? (Checksum errors)
        self.MctlRxBytes = 0 # How many bytes has the Microcontroller received?
        self.MctlTxBytes = 0 # How many bytes has the Microcontroller sent?
        self.MctlExceptionCount = 0 # How many exceptions has the Microcontroller handled?
        self.MctlLifeSeconds = 0 # How many seconds has the Microcontroller been running for?        
        self.MctlWriteDrops = 0 # How many messages were dropped from send buffer on Microcontroller due to overflow?
        self.MotorControlMode = 'idle' # What mode are we in? 'idle'/'remote'/'autonomous'. This controls the responses to some automated status messages.
        self.SetMotorControlMode(self.MotorControlMode) # Updates self.MaintainTrajectory

    def SetMotorControlMode(self,mode):
        """ Change the control mode of the motors.
            Supported modes are listed in self.MCMdict.
            - That defines how the session automatically responds to status messages received from the microcontroller.
            - If it's in trajectory mode then the system will automatically start feeding trajectory segments to the motor.
            - If it's not in trajectory mode, then the system will flush existing trajectory segments from the motor.
            Unrecognised modes fail-safe to 'idle'. """
        PMT = self.MaintainTrajectory 
        if mode in self.MCMdict:
            self.Log('sessionstatus:SetMotorControlMode(' + mode + ') from ' + self.MotorControlMode + ' to ' + mode,terminal=False)
            self.Log('sessionstatus:SetMotorControlMode(' + mode + ') ' + self.MCMdict[mode]['description'],terminal=False)
            self.MotorControlMode = mode
            self.MaintainTrajectory = self.MCMdict[mode]['trajectory']
        else:
            self.Log('sessionstatus.SetMotorControlMode(' + mode + ') is not recognised. Setting to idle.',level='error')
            self.MotorControlMode = 'idle' # Turn off motors just in case.
            self.MaintainTrajectory = self.MCMdict['idle']['trajectory'] # Turn off trajectory just in case.
        if PMT and PMT != self.MaintainTrajectory: # We've just stopped maintaining the trajectory. Clear out any existing entries.
            self.Log('sessionstatus.SetMotorControlMode(',mode,') clearing trajectory from motors.',terminal=False)
            Mctl.Write('clear trajectory') # Send immediate instruction to wipe any existing trajectory from the motors.

    def CheckMotorStatus(self,line):
        """ Check the Microcontroller's status message.
            - If it reports that the motor is configured, update the motor status information from this message.
            - If it reports that the motor is NOT configured, then send the configuration immediately.
            If they are not, then send the configuration immediately. 
            #  From Microcontroller to RPi
            #   motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
                  0     1           2          3    4     5          6   7     8   9
                                                                                            """
        lineitems = line.split(' ') # Split out all the elements of the line.
        motorname = lineitems[3] # Extract motor name.
        foundit = False
        for i in MotorControls:
            if i.MotorName == motorname:
                foundit = True
                i.ReceiveStatus(line) # Update motor status information.
        self.CheckTrajectory(line,self.Target) # Check observation is active and keep trajectory up-to-date if needed.
        if not foundit: # The motor name was not recognised.
            self.Log('sessionstatus.CheckMotorStatus did not recognise the motor name (',motorname, ')', level='error')

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
        remotetime = MctlStringToDatetime(lineitems[2]) # What does the remote system report as the time?
        self.TimeDiff = NowUTC() - remotetime # What's the time difference?
        self.ClockSynchronised = StringToBool(lineitems[3])
        self.AutonomousControl = StringToBool(lineitems[4])
        self.RemoteControl = StringToBool(lineitems[5])
        self.MctlLifeSeconds = int(lineitems[6])
        if len(lineitems) > 7: # How many times has the microcontroller flushed the trajectory because of comms problems?
            self.TrajectorySafetyFlushes = int(lineitems[7])
        else:
            self.TrajectorySafetyFlushes = 0
        # lineitems[8] contains reason codes, for documentation rather than function.
        if len(lineitems) > 9: # Exception count is included in the message.
           self.MctlExceptionCount = int(lineitems[9])
        if self.ClockSynchronised == False: # Clock has not yet been synchronised.
            # Synchronise clocks.
            line = 'set time ' + CleanDatetimeString(str(NowUTC()))
            Mctl.Write(line)
        if self.ClockSynchronised: temp = 'Synchronised'
        else: temp = 'Unsynchronised'

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
        motorname = lineitems[3]
        # This should only send a trajectory update IF we're TRACKING something!
        if self.MaintainTrajectory:
            foundit = False
            for i in MotorControls:
                if i.MotorName == motorname:
                   foundit = True
                   i.TrajectoryEntries = int(lineitems[6])
                   i.TrajectoryValid = StringToBool(lineitems[4])
                   i.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
                   duration = i.TrajectoryValidUntil - NowUTC()
                   self.Log('sessionstatus.CheckTrajectory: Examining', i.MotorName, ', Entries', i.TrajectoryEntries, ', ValidUntil', i.TrajectoryValidUntil, ', Valid',i.TrajectoryValid, ', duration',duration.total_seconds(), 's, Window', Parameters.TrajectoryWindow, 's, ClkSync', self.ClockSynchronised,terminal=False)
                   if duration.total_seconds() < Parameters.TrajectoryWindow and self.ClockSynchronised: # We need to add time to the trajectory plan.
                       self.Log('sessionstatus.CheckTrajectory: Decided to extend.',terminal=False)
                       i.ExtendTrajectory(targetobj)
                   else: self.Log('sessionstatus.CheckTrajectory: Decided not to extend. Valid for',duration.total_seconds(),"s, Minimum",Parameters.TrajectoryWindow,"s",self.ClockSynchronised,terminal=False)
            if not foundit: # The motor name was not recognised.
                self.Log('sessionstatus.CheckTrajectory did not recognise the motor name (',motorname, ')', level='error')
        else: self.Log('sessionstatus.CheckTrajectory: Not currently maintaining trajectories on microcontroller.',terminal=False)
    
    def CheckControllerStarted(self,line):
        Mctl.MctlRestarted()
        for i in MotorControls:
            i.Restarted() # Need to mark that the motor is nolonger configured.
        self.Log('sessionstatus:CheckControllerStarted(): Microcontroller reports restart.',terminal=False)
        ErrorWindow.Print(NowHMS() + ' Microcontroller reports restart.')
        
    def CheckGotoRejected(self,line):
        self.Log('sessionstatus:MctlHandler(): Microcontroller rejected goto command.',terminal=False)
        ErrorWindow.Print(NowHMS() + ' Microcontroller rejected goto command: ' + line)
    
    def CheckTuneComplete(self,line): # A tune command has been processed.
        """ tune complete {name} {endtime} {delta} {starttime} 
              0     1       2        3        4        5        """
        foundit = False
        lineitems = line.split(' ')
        motorname = lineitems[2] # Which motor?
        for i in MotorControls:
            if i.MotorName == motorname:
                i.TuneComplete(line)
                foundit = True
        if not foundit: # The motor name was not recognised.
            self.Log('sessionstatus.CheckTuneComplete did not recognise the motor name (',motorname, ')', level='error')

    def UnrecognisedMessage(self,line):
        self.Log('sessionstatus:UnrecognisedMessage():',line,terminal=False)
        ErrorWindow.Print(NowHMS() + ' Unrecognised message: ' + line)

    def ValidControllerVersion(self):
        """ Return TRUE if controller version is known and acceptable.
            This only succeeds if the microcontroller is communicating
            and has send the controller version number to the RPi already. """
        result = False # Not acceptable unless proven.
        if self.ControllerVersion != 'unknown':
            try:
                compversion = self.ControllerVersion[:self.ControllerVersion.rindex('.')] # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
                if compversion in ACCEPTABLECONTROLLERVERSIONS:
                    result = True # Acceptable
            except Exception as e:
                self.Log('sessionstatus.ValidControllerVersion(): Failed to check',self.ControllerVersion,level='error')
                self.Log('sessionstatus.ValidControllerVersion(): Failed with',str(e),level='error')
        return result

    def CheckControllerVersion(self,line):
        """ Handle controller version message. 'controller version 0.0.0' """
        self.Log('sessionstatus:CheckControllerVersion(): ' + line,terminal=False)
        lineitems = line.split(' ')
        if len(lineitems) > 2:
            self.ControllerVersion = lineitems[2]
            try:
                compversion = self.ControllerVersion[:self.ControllerVersion.rindex('.')] # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
                if not compversion in ACCEPTABLECONTROLLERVERSIONS:
                    self.Log('sessionstatus.CheckControllerVersion():',self.ControllerVersion,'is not in',ACCEPTABLECONTROLLERVERSIONS,terminal=True)
                    ErrorWindow.Print(NowHMS() + ' ' + self.ControllerVersion + ' is not in ' + str(ACCEPTABLECONTROLLERVERSIONS))
            except Exception as e:
                self.Log('sessionstatus.CheckControllerVersion(): Failed to check',self.ControllerVersion,level='error')
                self.Log('sessionstatus.CheckControllerVersion(): Failed with',str(e),level='error')
        else:
            self.Log('sessionstatus.CheckControllerVersion(): Response is incomplete:',line,level='warning')

    def MctlHandler(self):
        """ Handles incoming messages from microcontroller queue,
            updates status information in various objects,
            performs automatic responses to standard conditions.

            This reads/writes to message queues. It analyses and processes messages from
            the microcontroller, it does not directly handle the UART transfer of data.
            To see the UART Channel handling look in microcontroller.CommsLoop method.            """
        self.Log('sessionstatus.MctlHandler(): Started.',terminal=True)
        heartbeat = timer(30,skip=True) # Send a heartbeat signal to the microcontroller every 30 seconds.
        Mctl.Write('# rpi version ' + VERSION) # Tell the microcontroller what version of software is running. *Q* Remove '#' when microcontroller software updated. Aug.2023
        try:
            while True: # Repeat until told to stop.
                if self.TerminateMctlHandler:
                    self.Log('sessionstatus.MctlHandler(): Terminate signal received.',terminal=False)
                    break
                if len(Mctl.Lines) > 0: # Something to handle.
                    line = Mctl.Read() # Pull next available message from microcontroller.
                    # Are all the same messages received, processed, logged or ignored in the same way?
                    if len(line) > 0: # Data to process.
                        #lineitems = line.split(" ")
                        if line.startswith('session'): self.CheckSessionStatus(line) # Gather information about the microcontroller general health.
                        elif line.startswith('comms'): self.CheckCommsStats(line) # Gather statistics about UART communication handling.
                        elif line.startswith('controller log'): pass # Just log messages from the microcontroller. No action needed.
                        elif line.startswith('log'): pass # Just log messages from the microcontroller. No action needed.
                        elif line.startswith('cleared trajectory'): pass # Just log these.
                        elif line.startswith('motor'): self.CheckMotorStatus(line) # Check motor info from microcontroller, respond with missing config etc.
                        elif line.startswith('controller heartbeat'): pass # Just log these.
                        elif line.startswith('heartbeat'): pass # Just log these.
                        elif line.startswith('acknowledged'): pass # Just log these.
                        elif line.startswith('#'): pass # Comments from microcontroller, ignore them.
                        elif line.startswith('controller version'): self.CheckControllerVersion(line) # Check that software is compatible across devices.
                        elif line.startswith('goto rejected'): self.CheckGotoRejected(line) # A goto command was rejected.
                        elif line.startswith('tune complete'): self.CheckTuneComplete(line) # A tune command has been processed.
                        elif line.startswith('controller started'): self.CheckControllerStarted(line) # Microcontroller reports a restart. Trigger chain of updates.
                        elif line.startswith('defined motors'): pass # Just log these.
                        else: self.UnrecognisedMessage(line) # Unexpected or corrupted message.
                else: time.sleep(0.1) #  Nothing received this round, so pause to release the pressure on the CPU!
                # Send occassional heartbeat signal to keep line alive.
                if heartbeat.Due(): # Microcontroller will panic and flush trajectories if comms goes silent for too long.
                    Mctl.Write('# heartbeat') # Prove we're still alive.
                    self.Log("sessionstatus.MctlHandler(): Heartbeat",terminal=False)
        except Exception as e: # Message handler failed.
            self.Log("sessionstatus.MctlHandler: Failed!",level='error')
            MainLog.ReportException(e,comment='MctlHandler failed.') # Trap all the exception information in the main log file.
        self.TerminateMctlHandler = False # Reset the termination flag.
        self.Log('sessionstatus.MctlHandler(): End.',terminal=True)

    def TimeDiffSecs(self):
        # Convert self.TimeDiff into an absolute number of seconds.
        # self.TimeDiff format is "d, h:m:s" or "h:m:s"
        result = 0
        if self.TimeDiff != None:
            result = round(self.TimeDiff.total_seconds(),1)
        return result

    def ShowRemoteStatus(self):
        """ Display status from Microcontroller """
        # Microcontroller communications
        nowutc = NowUTC() # Store current time.
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
        SessionWindow.FieldValue('MTSF',self.TrajectorySafetyFlushes) # How many times has the microcontroller flushed valid trajectorys due to comms problems?
        SessionWindow.FieldValue('EXCEPT',self.MctlExceptionCount) # How many code exceptions have been reported by the microcontroller.
        if self.MctlExceptionCount > 0: SessionWindow.FieldColor('EXCEPT',fg=OSW_TEXT_POOR) # The microcontroller has handled some exceptions in the code.
        else: SessionWindow.FieldColor('EXCEPT',fg=OSW_TEXT_GOOD) # The microcontroller has not encountered any code exceptions.
        if self.TrajectorySafetyFlushes > 0: SessionWindow.FieldColor('MTSF',fg=OSW_TEXT_BAD)
        else: SessionWindow.FieldColor('MTSF',fg=OSW_TEXT_GOOD)
        if Mctl.PoweredByUsb: # There's a USB connection as well as a GPIO connection to the microcontroller. BEWARE!
            SessionWindow.FieldValue('CMODE',"GPIO & USB!") # What type of connection/power is provided to the microcontroller?
            SessionWindow.FieldColor('CMODE',fg=OSW_TEXT_POOR)
        else: # Just a GPIO connection to the microcontroller. RELAX!
            SessionWindow.FieldValue('CMODE',"GPIO") # What type of connection/power is provided to the microcontroller?
            SessionWindow.FieldColor('CMODE',fg=OSW_TEXT_GOOD)
        # Mark the age of the last reported camera positions, warn if the data is getting stale.
        AzAge, AltAge = GetPositionAges()
        if AzAge > 60: azafg=OSW_TEXT_BAD
        elif AzAge > 20: azafg = OSW_TEXT_POOR
        else: azafg = OSW_TEXT_FG
        if AltAge > 60: altafg=OSW_TEXT_BAD
        elif AltAge > 20: altafg = OSW_TEXT_POOR
        else: altafg = OSW_TEXT_FG
        SessionWindow.FieldValue('CAZA',"(" + str(AzAge) + "s)",fg=azafg,bg=textcolor.BLACK) # Age of camera reported position.
        SessionWindow.FieldValue('CALTA',"(" + str(AltAge) + "s)",fg=altafg,bg=textcolor.BLACK) # Age of camera reported position.
        SessionWindow.FieldValue('CLKDIF',str(self.TimeDiffSecs()) + "s") # Time difference/delay between RPi and Microcontroller.
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
            if i.MotorSpeed == None:
                SessionWindow.FieldValue(fnp + 'DPS','0.0' + DegreeSymbol)
            else:
                SessionWindow.FieldValue(fnp + 'DPS',str(i.MotorSpeed)[:6] + DegreeSymbol)
            SessionWindow.FieldValue(fnp + 'D',i.TrajectoryEntries)
            if i.TrajectoryEntries > 0: SessionWindow.FieldColor(fnp + 'D',fg=OSW_TEXT_GOOD)
            else: SessionWindow.FieldColor(fnp + 'D',fg=OSW_TEXT_POOR)
            if i.TrajectoryValidUntil != None:
                temphms = HmsFromStamp(i.TrajectoryValidUntil,dateaware=True) # Show HH:MM:SS unless it's another day, then show DD HH:MM
                tempsec = (i.TrajectoryValidUntil - nowutc).total_seconds() # How long does the trajectory last (seconds)?
                if tempsec > Parameters.TrajectoryWindow: # Valid far enough into the future.
                    SessionWindow.FieldValue(fnp + 'U',temphms,fg=OSW_TEXT_GOOD,bg=textcolor.BLACK)
                    temp = "(" + HRSeconds(tempsec) + ")"
                    SessionWindow.FieldValue(fnp + 'RM',temp,fg=OSW_TEXT_FG,bg=textcolor.BLACK)
                elif tempsec > 0: # Running out soon, needs extending.
                    SessionWindow.FieldValue(fnp + 'U',temphms,fg=OSW_TEXT_POOR,bg=textcolor.BLACK)
                    temp = "(" + HRSeconds(tempsec) + ")"
                    SessionWindow.FieldValue(fnp + 'RM',temp,fg=OSW_TEXT_POOR,bg=textcolor.BLACK)
                else: # Already run out.
                    SessionWindow.FieldValue(fnp + 'U',temphms,fg=OSW_TEXT_BAD,bg=textcolor.BLACK)
                    temp = "(" + HRSeconds(-1 * tempsec) + ")"
                    SessionWindow.FieldValue(fnp + 'RM',temp,fg=OSW_TEXT_BAD,bg=textcolor.BLACK)
            else: # No trajectory data yet.
                temp = HRSeconds(0)
                SessionWindow.FieldValue(fnp + 'U',temp,fg=OSW_TEXT_POOR,bg=textcolor.BLACK)
                SessionWindow.FieldValue(fnp + 'RM',"(" + temp + ")",fg=OSW_TEXT_POOR,bg=textcolor.BLACK)

Session = sessionstatus() # Create new session status object.

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Image processing (OpenCV) 
# ///////////////////////////////////////////////////////////////////////////////////

class imagetracker(attributemaster):
    """ ImageTracker uses OpenCV and AstroAlign packages to measure the drift of the 
        stars between images. This may be useful for autocorrecting position or basic image tracking. """
        
    def __init__(self):
        self.Log = CamLog.Log # Handle to the function for logging messages by this class.

        self.TargetImage = pilomarimage(name='target',logger=CamLog) # This will be the opencv image buffer.
        self.TargetTimeStamp = None # UTC timestamp for image buffer.

        self.LatestImage = pilomarimage(name='latest',logger=CamLog) # This will be the opencv image buffer.
        self.LatestTimeStamp = None # UTC timestamp for the image buffer.

        self.TrackingInterval = Parameters.TrackingInterval # Check target tracking every nnn seconds.

        self.dx = None # Measured delta-x between images.
        self.dy = None # Measured delta-y between images.
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None # Total seconds between reference images.

        self.PreparedImages = 0 # Incrementing counter of images handled.
        self.TargetStarMatchList = [] # List of star locations in TargetImage (calculated by FindTransform method)
        self.LatestStarMatchList = [] # List of star locations in LatestImage (calculated by FindTransform method)
        self.TargetMinMagnitude = Parameters.TargetMinMagnitude # The actual minimum star magnitude finally selected for the target image.

    def TrackingAge(self): # In pilomarimage
        """ Return age of latest tracking image in seconds. """
        td = None
        if self.LatestTimeStamp != None: td = int((NowUTC() - self.LatestTimeStamp).total_seconds())
        return td
                
    def Reset(self):
        """ Reset image cache and related data. """
        self.Log("ImageTracker.Reset: Begin",terminal=False)
        self.TargetImage.Clear()
        self.TargetTimeStamp = None
        self.TargetStarMatchList = []
        self.LatestImage.Clear()
        self.LatestTimeStamp = None
        self.LatestStarMatchList = []
        self.LatestStarCount = 0
        self.dx = None # Measured delta-x between images.
        self.dy = None # Measured delta-y between images.
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None # Total seconds between reference images.
        self.Log("ImageTracker.Reset: End",terminal=False)

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
        self.TargetImage.LoadBuffer(cvimagebuffer)
        self.TargetImage.ChangeType('grayscale')
        self.Log("ImageTracker.SetTargetImage: About to measure contrast.",terminal=False)
        contrast_m, contrast_s = self.TargetImage.MeasureContrast() # Calculate contrast for latest image.
        self.Log("ImageTracker.SetTargetImage: Contrast measures",contrast_m, contrast_s,terminal=False)
        self.Log("ImageTracker.SetTargetImage: Prepared image: type", str(type(self.TargetImage.ImageBuffer)), "shape", self.TargetImage.GetHeight(), "x", self.TargetImage.GetWidth(), "depth",self.TargetImage.GetDepth(),terminal=False)
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
            _,_ = self.TargetImage.CountStars()
        else: # StarCount and StarList already available, just use those.
            self.Log("ImageTracker.SetTargetImage: Received StarCount and StarList. Not recalculating them.",terminal=False)
            self.TargetImage.StarCount = starcount
            self.TargetImage.StarList = starlist
        self.Log("ImageTracker.SetTargetImage: Counted", self.TargetImage.StarCount, "stars.",terminal=False)
        # No need to clean up the image. It was generated to match the standardised image already.
        # Save target image for reference.
        folder = FolderList.get('tracking')
        filename = folder + 'TargetTrackingImage_' + UtcTimeStamp() + '.jpg'
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        self.TargetImage.SaveFile(filename)
        # Calculate the transformation between TARGET and LATEST images.
        self.Log("ImageTracker.SetTargetImage: Calling FindTransform...",terminal=False)
        result = self.FindTransformImage() # Try to calculate transform from TARGET and LATEST images.
        self.Log("ImageTracker.SetTargetImage: FindTransform returned " + str(result),terminal=False)

    def FindTransformImage(self):
        """ Use astroalign.find_transform to calculate transform between TARGET and LATEST images.
            The target image is generated by the program and represents the star layout we expect to photograph.
            The latest image is the one captured by the camera.
            Find Transform compares the two images and decides if they match.
            It measures any shift between the two images, this can be used to correct for drift in the telescope motion. """
        self.Log("ImageTracker.FindTransformImage: Begin",terminal=False)
        result = False
        self.dx = None
        self.dy = None
        self.rotation = None # Measured rotation between images.
        self.measureddelta = None
        if self.TargetImage.ImageMissing() or self.LatestImage.ImageMissing():
            pass # No images to compare. Skip this.
        else: # Two images available to compare.
            try: # The transform object is a numpy structure, if the transform calculation fails you can get weird problems that I couldn't always detect cleanly.
                 # So for now ignore any errors at this stage, and assume that no transform could be calculated.
                 # Sometimes it returned a NoneType that I couldn't test for (numpy array peculiarity), and sometimes it returned an empty array.
                self.Log("ImageTracker.FindTransformImage: TargetImage: type", str(type(self.TargetImage.ImageBuffer)), "shape", self.TargetImage.GetHeight(), "x", self.TargetImage.GetWidth(), "depth", self.TargetImage.GetDepth(), "len[0]", len(self.TargetImage.ImageBuffer[0]), '(2 = (x,y), else image)', "datatype", str(self.TargetImage.ImageBuffer.dtype),terminal=False)
                self.Log("ImageTracker.FindTransformImage: LatestImage: type", str(type(self.LatestImage.ImageBuffer)), "shape", self.LatestImage.GetHeight(), "x", self.LatestImage.GetWidth(), "depth", self.LatestImage.GetDepth(), "len[0]", len(self.LatestImage.ImageBuffer[0]), '(2 = (x,y), else image)', "datatype", str(self.LatestImage.ImageBuffer.dtype),terminal=False)
                self.Log("ImageTracker.FindTransformImage: Calling astroalign.find_transform()...",terminal=False)
                # If find_transform fails, it reports that the input images are not supported, but this is a generic error for ANY failure at all.
                # Check the astroalign source code online and dig deeper... I've seen where _find_sources() fails due to 'sep' package versioning problems.
                transform, (LSL, TSL) = astroalign.find_transform(source=self.LatestImage.ImageBuffer,target=self.TargetImage.ImageBuffer) # In Astroalign terms, this is source=LatestImage, target=TargetImage...
                self.TargetStarMatchList = TSL
                self.LatestStarMatchList = LSL
                self.Log("ImageTracker.FindTransformImage: Received " + str(type(transform)) + " type in return.",terminal=False)
                self.Log("ImageTracker.FindTransformImage: Identified " + str(len(TSL)) + " suitable stars in target image.",terminal=False)
                self.Log("ImageTracker.FindTransformImage: TargetStarMatchList " + str(TSL) + ".",terminal=False)
                if len(TSL) > 0 and len(LSL) > 0: # During development, look at the datatype.
                    self.Log("ImageTracker.FindTransformImage: Example TSL 1st entry is:", str(TSL[0]),terminal=False)
                    self.Log("ImageTracker.FindTransformImage: Example LSL 1st entry is:", str(LSL[0]),terminal=False)
                self.Log("ImageTracker.FindTransformImage: Identified " + str(len(LSL)) + " suitable stars in latest image.",terminal=False)
                self.Log("ImageTracker.FindTransformImage: LatestStarMatchList " + str(LSL) + ".",terminal=False)
                self.dx = int(-1 * transform.translation[0]) # X-Difference scaled back up to compensate for any image scaling.
                self.dy = int(-1 * transform.translation[1]) # Y-Difference scaled back up to compensate for any image scaling.
                self.rotation = round(math.degrees(transform.rotation),3) # How does the image need to be rotated? Convert radians into degrees.
                self.Log("ImageTracker.FindTransformImage: Calculated transform: dx=" + str(self.dx),"dy=" + str(self.dy),terminal=False)
                self.Log("ImageTracker.FindTransformImage: Calculated rotation:",self.rotation,"degrees",terminal=False) # How does the image need rotating?
                self.measureddelta = (self.LatestTimeStamp - self.TargetTimeStamp).total_seconds()
                result = True
            except Exception as e:
                # The most likely explanation is that the lens cap is ON, or there are not enough stars visible in the observation.
                self.Log("ImageTracker.FindTransformImage: Ignored error: " + str(e),terminal=False) # Enable this line if you want to see what error is being ignored!
                self.Log("ImageTracker.FindTransformImage: No transform matrix created. Too few stars, lens cap on, no transformation identified or fault in astroalign and dependencies?",terminal=False)
                DriftWindow.Print(NowHMS() + " FindTransformImage unsuccessful.")
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

    def MarkLocation(self,image,starx,stary,color,uppertext=None,lowertext=None):
        """ Write the location text next to the star.
            image parameter should be a pilomarimage() instance.
            Places the text left/right depending upon it's location in the image.
            Write 'uppertext' value above centre of star. 
            Write 'lowertext' value below centre of star. """
        starx = int(starx)
        stary = int(stary)
        if starx < (image.GetWidth() / 2): xloc = starx + 10
        else: xloc = starx - 120
        yloc = stary
        loctext = "(" + str(starx) + "," + str(stary) + ")"
        image.AddText(loctext,xloc,yloc,size=0.5,color=color)
        if uppertext != None: # There's additional info to print above the star.
            image.AddText(uppertext,starx - 10,yloc - 20,size=0.5,color=color)
        if lowertext != None: # There's additional info to print above the star.
            image.AddText(lowertext,starx - 10,yloc + 30,size=0.5,color=color)
        return True
        
    def SaveTrackingAnalysis(self,latestlist=None,targetlist=None):
        """ Combine LATEST, TARGET star lists and show which stars were matched up in FindTransform.
            This is a debug/development feature, but shows how the drift tracking is actually interpreting the images. 
            If latestlist and targetlist are provided by the calling routine those are used for markup.
            Otherwise the existing values from the imagetracker instance are used. """
        self.Log("ImageTracker.SaveTrackingAnalysis: Begin",terminal=False)
        if type(latestlist) == type(None): latestlist = self.LatestImage.StarList
        if type(targetlist) == type(None): targetlist = self.TargetImage.StarList
        height = SensorInUse.PixelHeight
        width = SensorInUse.PixelWidth
        NewImageBuffer = pilomarimage(name='trackinganalysis',logger=CamLog) # Color full frame blank image.
        NewImageBuffer.New(height,width,imagetype='bgr',datatype=np.uint8)
        NewImageBuffer.FillColor(BGRBlack)
        # Match lists must be the same length.
        if type(self.LatestStarMatchList) != type(None) and \
           type(self.TargetStarMatchList) != type(None) and \
           len(self.LatestStarMatchList) == len(self.TargetStarMatchList):
            # Mark the matched stars first, and an arrow linking the TARGET and LATEST locations.
            for i, lstar in enumerate(self.LatestStarMatchList): 
                tstar = self.TargetStarMatchList[i]
                lx = int(lstar[0]) # Latest star X
                ly = int(lstar[1]) # Latest star Y
                tx = int(tstar[0]) # Target star X
                ty = int(tstar[1]) # Target star Y
                if self.ValidStarValues(tstar): NewImageBuffer.DrawCircle(tx,ty,15,BGRGreen,thickness=2) # Green circle around matched Target stars.
                else: self.Log("imagetracker.SaveTrackingAnalysis: TargetStarMatchList. tstar",tstar,"bad values.",terminal=True)
                if self.ValidStarValues(lstar): NewImageBuffer.DrawCircle(lx,ly,15,BGRRed,thickness=2) # Red circle around matched Latest stars.
                else: self.Log("imagetracker.SaveTrackingAnalysis: LatestStarMatchList. lstar",lstar,"bad values.",terminal=True)
                if self.ValidStarValues(tstar) and self.ValidStarValues(lstar): 
                    NewImageBuffer.DrawLine((lx,ly),(tx,ty),color=BGRWhite,arrowpixels=20) # Green circle around matched Target stars.
                NewImageBuffer.DrawDumbbell((lx,ly),(tx,ty),20,BGRRed,BGRGreen,BGRYellow,arrow=True)
        else: # Lists don't agree, so don't try to map them.
            self.Log("imagetracker.SaveTrackingAnalysis: Conflicting length of star lists: Target", type(self.TargetStarMatchList), len(self.TargetStarMatchList), "vs Latest", type(self.LatestStarMatchList), len(self.LatestStarMatchList),terminal=False)
            DriftWindow.Print(NowHMS() + " drift analysis image not done.") # Note analysis not done.
        # Superimpose all the TARGET stars. (Stars we expect to see)
        if self.TargetImage.StarList != None:
            for i,star in enumerate(self.TargetImage.StarList): 
                if self.ValidStarValues(star): 
                    starx = int(star[0])
                    stary = int(star[1])
                    magtext = "(" + str(starx) + "," + str(stary) + ")"
                    NewImageBuffer.DrawCircle(starx,stary,5,color=BGRGreen) # Green dot for Target stars.
                    self.MarkLocation(NewImageBuffer,starx,stary,BGRGreen,"[" + str(i) + "]",magtext) # Mark location, brightness ranking (Brightest -> Dimmest) and magnitude if known.
                else: self.Log("imagetracker.SaveTrackingAnalysis: TargetImage.StarList. star",star,"bad values.",terminal=True)
        # Superimpose all the LATEST stars. (Stars we actually see)
        if self.LatestImage.StarList != None:
            for i,star in enumerate(self.LatestImage.StarList): 
                if self.ValidStarValues(star): 
                    starx = int(star[0])
                    stary = int(star[1])
                    NewImageBuffer.DrawCircle(starx,stary,5,color=BGRRed) # Red dot for Latest stars.
                    magtext = "(" + str(starx) + "," + str(stary) + ")"
                    self.MarkLocation(NewImageBuffer,starx,stary,BGRRed,"[" + str(i) + "]",magtext)
                else: self.Log("imagetracker.SaveTrackingAnalysis: LatestImage.StarList. star",star,"bad values.",terminal=True)
        # Add key.
        timestamp = str(NowUTC()).split('.')[0] + " UTC"
        NewImageBuffer.AddText("Tracking Analysis " + timestamp,1300,100,size=2,color=BGRWhite,bgcolor=BGRBlack,thickness=2)
        NewImageBuffer.AddText(str(self.TargetImage.StarCount) + " Target stars",100,100,size=1,color=BGRGreen,bgcolor=BGRBlack)
        NewImageBuffer.AddText(str(self.LatestImage.StarCount) + " Latest stars",100,140,size=1,color=BGRRed,bgcolor=BGRBlack)
        NewImageBuffer.AddText(str(len(self.LatestStarMatchList)) + " Matches",100,180,size=1,color=BGRYellow,bgcolor=BGRBlack)
        #NewImageBuffer.AddText("Prep images: " + str(Parameters.PrepImagesForTracking),100,220,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Predict drift: " + str(Parameters.TrackingPrediction),100,240,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Match threshold: " + str(Parameters.TrackingMatchThreshold) + " stars.",100,260,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Min correction: " + str(Parameters.MinimumDriftCorrection) + " steps.",100,280,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Tracking interval: " + str(Parameters.TrackingInterval) + " s.",100,300,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        #NewImageBuffer.AddText("Apply UrbanFilter: " + str(Parameters.TrackingUrbanFilter),100,320,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Star radius: " + str(Parameters.TrackingStarRadius) + " px.",100,340,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Exposure: " + str(Parameters.TrackingExposureSeconds) + " s.",100,360,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Target time: " + str(DriftTracker.TargetTimeStamp) + " UTC",100,380,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Latest time: " + str(DriftTracker.LatestTimeStamp) + " UTC",100,400,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("DX: " + str(DriftTracker.dx) + " px.",100,420,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("DY: " + str(DriftTracker.dy) + " px.",100,440,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("Rot: " + str(DriftTracker.rotation) + " deg.",100,460,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        NewImageBuffer.AddText("T.Min.Mag: "  + str(DriftTracker.TargetMinMagnitude),100,480,size=0.5,color=BGRCyan,bgcolor=BGRBlack)
        
        # Program ID in bottom right corner.
        xpos = int(width - 10)
        ypos = int(height - 10)
        NewImageBuffer.AddText(ProgramTitle + " " + VERSION,xpos,ypos,color=BGRWhite,bgcolor=BGRBlack,hjust='r')
        # Save the file.
        # Save image.
        filename = FolderList['tracking'] + "TrackingAnalysis_" + UtcTimeStamp() + ".jpg"
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        DriftWindow.Print(NowHMS() + " Drift analysis image done.") # Note analysis done.
        NewImageBuffer.SaveFile(filename)
        self.Log("ImageTracker.SaveTrackingAnalysis: End",terminal=False)

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
        uts = UtcTimeStamp()
        self.LatestTimeStamp = None # Clear the timestamp until we've completed preparing the image. This is accessed concurrently by the CameraHandler.
        self.Log("ImageTracker.SetLatestImage: About to measure contrast.",terminal=False)
        self.LatestImage.LoadBuffer(cvimagebuffer) # This makes a copy of the original image rather than just creating a pointer to it.
        contrast_m, contrast_s = self.LatestImage.MeasureContrast() # Calculate contrast for latest image.
        self.Log("ImageTracker.SetLatestImage: Contrast measures",contrast_m, contrast_s,terminal=False)
        folder = FolderList.get('tracking')
        self.LatestImage.ChangeType('grayscale') # Always convert to grayscale at this point.
        if Parameters.LatestTrackingFilter != None: # A filter script is selected for latest tracking images, process that instead of the old hardcoded filter code.
            if self.LatestImage.RunFilterScript(Parameters.LatestTrackingFilter): # If the script succeeds or fails.
                self.Log("ImageTracker.SetLatestImage: LatestTrackingFilter(",Parameters.LatestTrackingFilter,") success.",terminal=False)
            else: # Failed.
                self.Log("ImageTracker.SetLatestImage: LatestTrackingFilter(",Parameters.LatestTrackingFilter,") failed.",level='warning')
        #else: # Backwards compatibility, run old hardcoded filter logic if new system is not used.
        #    if Parameters.TrackingUrbanFilter: # Apply the 'UrbanFilter' algorithm to the image. This tries to remove haze, and sometimes even trees.
        #        self.Log("ImageTracker.SetLatestImage: Applying UrbanFilter to image",terminal=False)
        #        DriftWindow.Print(NowHMS() + ' Applying UrbanFilter.')
        #        self.LatestImage.UrbanFilter()
        #    if Parameters.PrepImagesForTracking: # Simplify the images if option selected.
        #        self.Log("ImageTracker.SetLatestImage: Preparing image",terminal=False)
        #        DriftWindow.Print(NowHMS() + ' Enhancing stars.')
        #        #self.LatestImage.PrepareImage() # Remove alias to EnhanceStars, reference it directly instead.
        #        self.LatestImage.EnhanceStars()
        self.Log("ImageTracker.SetLatestImage: Prepared image:","type", str(type(self.LatestImage.ImageBuffer)),"shape", self.LatestImage.GetHeight(), "x", self.LatestImage.GetWidth(),"depth", self.LatestImage.GetDepth(),terminal=False)
        self.LatestTimeStamp = timestamp # The image is now prepared, update the timestamp.
        self.LatestStarMatchList = [] # Clear the list of matched stars, this is set later when the find_transform call is made.
        self.Log("ImageTracker.SetLatestImage: Registered latest image",terminal=False)
        _,_ = self.LatestImage.CountStars()
        self.Log("ImageTracker.SetLatestImage: Counted",self.LatestImage.StarCount,"stars.",terminal=False)
        # Save target image for reference.
        filename = folder + 'LatestTrackingImage_' + uts + '.jpg'
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the file that's being created.
        self.LatestImage.SaveFile(filename)

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
MainLog.Log("Home location Latitude " + Parameters.HomeLat + ", Longitude " + Parameters.HomeLon)
HomeSiteTopos = Topos(Parameters.HomeLat,Parameters.HomeLon)

# Load dictionary listing star NAMES, CONSTELLATION and Hipparcos catalog number. 
#load = Loader('/home/pi/pilomar/data') # Create own version of Skyfield 'load' object. This version saves cache files in the data directory.
load = Loader(ProjectRoot + '/data') # Create own version of Skyfield 'load' object. This version saves cache files in the data directory.
StarNameUrl = ProjectRoot + '/data/starnames.json'
MessierDictUrl = ProjectRoot + '/data/messierobjects.json'
MeteorDictUrl = ProjectRoot + '/data/meteors.json'
HipparcosCacheFile = ProjectRoot + '/data/hipparcos.pkl'
NGCCacheFile = ProjectRoot + '/data/ngc.pkl'
NGCUrl = ProjectRoot + '/data/ngc.json'

def DictionaryLoader(filename):
    """ Given a json filename on disc, load it as a Python dictionary. 
        Return empty dictionary if file does not exist. """
    if os.path.exists(filename):
        with open(filename,'r') as f:
            dictionary = json.load(f)
    else:
        MainLog.Log('DictionaryLoader(',filename,') does not exist. Empty dictionary returned.',level='error')
        dictionary = {}
    return dictionary

# Load starname dictionary.
MainLog.Log("Loading StarName dictionary from " + StarNameUrl + "...",terminal=False)
StarName_dictionary = DictionaryLoader(StarNameUrl)

def BVtoBGR(BV):
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

def PandasFloat(inputvalue,failvalue=None):
    """ Convert a Pandas value into a float, or return None if impossible. 
        inputvalue = The pandas value to convert. 
        failvalue = The return value if inputvalue cannot be converted. """
    try:
        result = float(str(inputvalue))
    except:
        result = failvalue
    if str(result) == 'nan': # This is unacceptable too.
        result = failvalue
    return result
    
# -----------------------------------------------------------------------------------------------------
    
def HipColor(bv): 
    """ Return b,g,r values for the color of any star given its B-V value from the hipparcos catalog. """
    bv = PandasFloat(bv) # Make sure it's a float, trap NaN values.
    try:
        if IsFloat(bv): # Some entries are BLANK in Hipparcos data set.
            ColorBV = float(bv) 
            b,g,r = BVtoBGR(ColorBV)
            # Make all the stars quite bright, so rescale the values to 128 - 255.
            b = int(b/2) + 127
            g = int(g/2) + 127
            r = int(r/2) + 127
        else:
            MainLog.Log("HipColor:",str(bv),"isn't float, setting (255,255,255)",terminal=False)
            b = g = r = 255
    except Exception as e:
        MainLog.Log("HipColor:",str(bv),"failed:",str(e),level='warning')
        b = g = r = 255
    return (b,g,r)

# ------------------------------------------------------------------------------------------------------

def Magnitude2Radius(mag,dimmest,brightest=-6,radius_max=20):
    """ Calculate star radius based upon a sliding scale of magnitudes.
        Returns a scaled 'radius' and a 'ratio' for dimming colours based upon the magnitude of the item.
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
    brightnessratio = float(offset) / float(span) # How far along the brightest - dimmest scale are we?
    brightnessratio = 1.0 - (brightnessratio / 2) # Invert the scale and make sure we don't dim below 50% so stuff stays visible.
    return radius, brightnessratio

# ------------------------------------------------------------------------------------------------------

def DimChannel(channel,ratio):
    """ simple multiplier for single color channel. """
    channel = channel * ratio
    channel = max(channel,0) # Cannot be < 0
    channel = min(channel,255) # Cannot be > 255
    return int(channel)

# ------------------------------------------------------------------------------------------------------


def hipex_load_dataframe(fobj):
    """ Skyfield has a built in method to extract Hipparcos data and convert it into a Pandas dataframe.
        However it lacks some data fields that Pilomar uses.
        This is a replica of the Skyfield method, but it extracts the additional datafields that Pilomar uses. 
        If the original Skyfield method ever changes, this version should also be reviewed.
        Original skyfield function is in :-
                /usr/local/lib/python3.7/dist-packages/skyfield/data/hipparcos.py 
                
        This version of the routine is very slow, 3+ hours on Raspberry Pi 4B. 
        - Likely that there are good Pandas improvements to make here. Needs more investigation. """
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
        usecols=['HIP', 'Vmag', 'RAdeg', 'DEdeg', 'Plx', 'pmRA', 'pmDE', 'B-V'],
        na_values=['     ', '       ', '        ', '            '],    )

    df.columns = (
        'hip', 'magnitude', 'ra_degrees', 'dec_degrees',
        'parallax_mas', 'ra_mas_per_year', 'dec_mas_per_year', 'B-V',
    )
        
    df = df.assign(
        ra_hours = df['ra_degrees'] / 15.0,
        epoch_year = 1991.25,
    )
    
    # Drop any rows with missing data.
    df = df.dropna(subset = ['ra_degrees', 'dec_degrees'])

    # Add some precalculated data to simplify things later.
    df['ralabel'] = '' # Add a column for precalculated RA label for each star.
    df['declabel'] = '' # Add a column for precalculated DEC label for each star.
    df['label'] = '' # Full HIPnnnn label for display/labelling.
    df['starname'] = '' # Add a column for the name of the star if known.
    df['constellation'] = '' # Add a column for the name of the constellation if known.
    df['color_b'] = 255 # BLUE color of star.
    df['color_g'] = 255 # GREEN color of star.
    df['color_r'] = 255 # RED color of star.
    df['markupradius'] = 1 # Size of circle surrounding a star on the preview markup.
    df['starradius'] = 1 # Size of the DOT representing the star when making images.
    df['inbounds'] = 0 # Record how many times this star is within the bounds of the image. # Can be useful for finetuning the star list.
    df['targetangle'] = 0.0 # Record how far away the star is from the target (angle). # Can be useful for finetuning the star list.

    # Set proper names for stars if known.
    MainLog.Log("hipex_load_dataframe: Setting proper names of stars :-",terminal=True)
    for key,StarDict in StarName_dictionary.items():
        hip = int(key)
        name = StarDict.get('name',None)
        constellation = StarDict.get('constellation',None)
        MainLog.Log("hipex_load_dataframe: Key",key,"Naming",hip,"as",name,"in",constellation,terminal=False)
        if name != None:
            df.loc[df.hip == hip,'starname'] = name # Set proper name of star.
        if constellation != None:
            df.loc[df.hip == hip,'constellation'] = constellation # Set constellation name.

    MainLog.Log("hipex_load_dataframe: Set",len(pandas.unique(df['starname'])) - 1,"star names.",terminal=True)
    MainLog.Log("hipex_load_dataframe: Set",len(pandas.unique(df['constellation'])) - 1,"constellation names.",terminal=True)

    # Get list of unique B-V values.
    # Convert to b,g,r. Use Pandas efficiency to update all matching entries.
    # Create a catalog that can be used later to find these precalculated values.
    BVList = pandas.unique(df['B-V']) # How many unique values of B-V are there?
    MainLog.Log("hipex_load_dataframe: Calculating",len(df),"star colors from",len(BVList),"unique B-V values...",terminal=True)
    BVColors = {}
    for i,e in enumerate(BVList): # Convert each unique value only once, then assign to all matching entries in the dataframe.
        temp = PandasFloat(e)
        if temp != None:
            b,g,r = HipColor(temp)
        else:
            b = g = r = 255
        BVColors[e] = (b,g,r)
    
    # Pandas cells are referenced via indexes, calculate the indexes for each column here.
    ColumnNames = list(df.columns)
    col_ra_degrees = ColumnNames.index('ra_degrees')
    col_dec_degrees = ColumnNames.index('dec_degrees')
    col_ralabel = ColumnNames.index('ralabel')
    col_declabel = ColumnNames.index('declabel')
    col_markupradius = ColumnNames.index('markupradius')
    col_starradius = ColumnNames.index('starradius')
    col_label = ColumnNames.index('label')
    col_color_b = ColumnNames.index('color_b')
    col_color_g = ColumnNames.index('color_g')
    col_color_r = ColumnNames.index('color_r')
    total = len(df) # How many rows to process?
    MainLog.Log("hipex_load_dataframe: Calculate extra fields directly in",total,"records.",terminal=True)
    # Populate the ralabel and declabel columns, so we don't keep recalculating the values later in the program.
    updatetimer = timer(10) # Every few seconds update the progress.
    updatetimer.Trigger() # Force the timer to trigger immediately to show processing has begun.
    prgt = progresstimer('test',target=total) # Report progress and ETA.
    print("")
    for i in range(total): # Go through all the rows in the dataframe in sequence.
        dfrec = df.iloc[i] # Point to each row in turn.
        temp = PandasFloat(dfrec['hip']) # Get hip number.
        if temp != None:
            hip = int(temp) # Extract hip number as integer.
        else:
            hip = 99999999 # Junk!
        # Create label for Right Ascension
        temp = PandasFloat(dfrec['ra_degrees'])
        if temp != None: 
            h,m,s = AngleToHMS(temp)
            df.iat[i,col_ralabel] = str(int(h)) + "h " + str(int(m)) + "' " + str(round(s,1)) + '"' 
        else:
            MainLog.Log("hipex_load_dataframe: Unable to calculate ra_degrees for record",i,df.iat[i,col_ra_degrees],terminal=False)
        # Create label for Declination
        temp = PandasFloat(dfrec['dec_degrees'])
        if temp != None:
            d,m,s = AngleToDMS(temp)
            df.iat[i,col_declabel] = str(int(d)) + "deg " + str(int(m)) + "' " + str(round(s,1)) + '"'
        else:
            MainLog.Log("hipex_load_dataframe: Unable to calculate dec_degrees for record",i,df.iat[i,col_dec_degrees],terminal=False)
        # Create label for the HIP id.
        df.iat[i,col_label] = 'HIP' + str(hip) # Full HIPnnnn label for display/labelling.
        temp = PandasFloat(dfrec['magnitude'])
        if temp != None:
            # How large a circle does PreviewImage draw around this star?
            df.iat[i,col_markupradius] = int(max(int(15 - temp) * 3,1)) # Calculate the radius of the star, brighter = bigger.
            # What size is the star dot when creating images?
            TempStarRadius, TempStarDimmer = Magnitude2Radius(mag=temp,dimmest=10,brightest=-2, radius_max=20)
            df.iat[i,col_starradius] = int(TempStarRadius)
        else:
            TempStarDimmer = 1.0
        # Estimate the color of the star.
        b, g, r = BVColors[dfrec['B-V']] # Look up the basic color from a dictionary of precalculated conversions.
        df.iat[i,col_color_b] = DimChannel(b,TempStarDimmer) # Dim the star depending upon the magnitude.
        df.iat[i,col_color_g] = DimChannel(g,TempStarDimmer)
        df.iat[i,col_color_r] = DimChannel(r,TempStarDimmer)
        # Show progress...
        if updatetimer.Due():
            prgt.UpdateCount(i) # How far have we got so far? prgt will then produce ETA and % complete for us.
            print(textcolor.cursorup() + NowHMS(),round(prgt.GetPercent(),1),"%. Record",i,"of",total,"( HIP" + str(hip),"). ETA",str(prgt.GetETA()).split('.')[0],"UTC",textcolor.clearlineforward())
    return df

# If Hipparcos data already cached, use that, otherwise load and prepare the data cache now.
if ReloadData == False and os.path.exists(HipparcosCacheFile): # A cache of the hipparcos data already exists, use it.
    MainLog.Log("Hipparcos data cache exists, using that.",terminal=True)
    HipparcosDf = pandas.read_pickle(HipparcosCacheFile)
    MainLog.Log("Hipparcos dataframe loaded",len(HipparcosDf),"stars from cache.",terminal=False)
    MainLog.Log("Hipparcos dataframe contains",list(HipparcosDf.columns),"columns.",terminal=False)
else: # There is no Hipparcos cache on disc yet, it must be constructed.
    MainLog.Log("Hipparcos data cache does not exist yet. Generating it now...",terminal=True)
    lines = ["The full Hipparcos star catalog contains over 100000 stars.",
             "Pi-lomar is about to optimise this list and add some extra detail to speed things up later.",
             "This may take up to an hour to prepare , but only needs doing once. Pi-lomar will save and",
             "reuse the calculated list in future."
    ]
    textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK)
    # Load Hipparcos catalog using Skyfield libraries.
    HipparcosUrl = ProjectRoot + '/data/hip_main.dat.gz' # The skyfield example tries to pull this from the internet, 
    # but the .gz. file doesn't always exist in the format expected so it is stored locally for now. 
    # http://cdsarc.u-strasbg.fr/ftp/cats/aliases/H/Hipparcos/hip_main.dat
    # This was fixed by skyfield 1.31, it may break again if someone in u-strasbg re-zips the file.
    # hipparcos.URL contains the remote server copy of the file.
    if not os.path.exists(HipparcosUrl):
        MainLog.Log('Hipparcos compressed catalog was not found locally (',HipparcosUrl,'), will use Skyfield sources.',terminal=False)
        # HipparcosUrl = 'https://cdsarc.u-strasbg.fr/ftp/cats/I/239/hip_main.dat'
        HipparcosUrl = hipparcos.URL # The official source of the data file as provided by skyfield itself.
    MainLog.Log("Loading Hipparcos catalog dataframe from " + HipparcosUrl + " (or local cache)...",terminal=False)
    with load.open(HipparcosUrl,reload=ReloadData) as f: # Don't keep reloading it if it is already on disc.
        HipparcosDf = hipex_load_dataframe(f) # Hipparcos data as a Pandas dataframe.
        MainLog.Log('Hipparcos data:',list(HipparcosDf.columns),terminal=False)
        MainLog.Log("Saving Hipparcos cache as",HipparcosCacheFile,terminal=True)
        HipparcosDf.to_pickle(HipparcosCacheFile)
    # GitHub issue #39 workaround.
    MainLog.Log("Hipparcos catalog successfully built.",terminal=True)
    if ReloadData: pass # We're reloading a few datafiles, don't quit yet.
    else: 
        print(textcolor.yellow("Please restart the program."))
        exit() # Quit the program. This is a workaround to a problem where the Python 'input' statements fail after the hipex_load_dataframe() function has executed for a long time.

# These files come from JPL, they list the rules for positions of planets for hundreds of years.
MainLog.Log("Loading solar system ephemeris from JPL...",terminal=False)
# This requires an internet connection the first time it runs, after that it uses cached data.
# *Q* Oct.2020 - skyfield log suggests this may nolonger automatically update, may need manual flush and reload every few months.
planets = load('de421.bsp') # Compact list of inner planets. *Q* Does this have a 'reload' option like load.open does?

# Load Messier object list.
MainLog.Log('Loading Messier catalog from', MessierDictUrl, '...',terminal=True)
Messier_dictionary = DictionaryLoader(MessierDictUrl)
# Add some precalculated fields to simplify life later on.
for key,TempStarParms in Messier_dictionary.items():
    TempRAH = TempStarParms['ra'][0] # Right Ascension HOURS
    TempRAM = TempStarParms['ra'][1] # Right Ascension MINUTES
    TempRAS = TempStarParms['ra'][2] # Right Ascension SECONDS
    TempStarParms['rah'] = TempRAH
    TempStarParms['ram'] = TempRAM
    TempStarParms['ras'] = TempRAS
    TempStarParms['radeg'] = HMSToAngle(TempRAH,TempRAM,TempRAS)
    TempDED = TempStarParms['dec'][0] # Declination whole degrees
    TempDEM = TempStarParms['dec'][1] # Declination MINUTES
    TempDES = TempStarParms['dec'][2] # Declination SECONDS
    TempStarParms['ded'] = TempDED
    TempStarParms['dem'] = TempDEM
    TempStarParms['des'] = TempDES
    TempStarParms['decdeg'] = DMSToAngle(TempDED,TempDEM,TempDES)
    TempStarParms['ralabel'] = str(int(TempRAH)) + "h " + str(int(TempRAM)) + "m " + str(round(TempRAS,1)) + "s"
    TempStarParms['declabel'] = str(int(TempDED)) + "d " + str(int(TempDEM)) + "' " + str(round(TempDES,1)) + '"'
    TempStarParms['widthdeg'] = float(TempStarParms['width'] / 60) # Convert from arcminutes to degrees
    TempStarParms['heightdeg'] = float(TempStarParms['height'] / 60) # Convert from arcminutes to degrees

StellariumUrl = ('https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/constellationship.fab')
MainLog.Log('Loading Stellarium constellation patterns from',StellariumUrl,terminal=False)
with load.open(StellariumUrl) as f:
    StellariumConstellations = stellarium.parse_constellations(f)

# Create internal list of the stars in each constellation. This indicates which stars to 'join up' in order to draw a constellation pattern.
MainLog.Log('Loading constellation patterns...',terminal=True)
ConstellationLinks = [] # Start new empty list of constellation patterns. [ [from hip num, to hip num, constellation], [from hip num, to hip num, constellation], ... ]
ConstellationCodes = dict(load_constellation_names()) # Used to turn abbreviations into full names.
ConstellationStarList = [] # List of HIP numbers for stars in constellation patterns. Used to find MarkupPreview stars which can be joined up.
for cons in StellariumConstellations: # Process each constellation in turn.
    # cons contains something like 'And',[(star1, star2), (star3, star4),...]
    c_name = cons[0] # Constellation name ('And')
    # Expand constellation code into a name if possible.
    if c_name in ConstellationCodes: # A translation exists. Convert from UMa => Ursa Major for example.
        c_name = ConstellationCodes[c_name] # Use the translation instead.
    c_name = c_name.lower() # Lower case to match other references elsewhere in the program.
    c_edge = cons[1] # Constellation pattern edges as a list [(star1, star2),(star3, star4),...]
    for c_pair in c_edge: # Process each star pair in turn.
        # c_pair format is (star1,star2) - star1/2 are Hipparcos references.
        star1 = str(c_pair[0])
        star2 = str(c_pair[1])
        entry = [star1,star2,c_name] # New entry for internal format list.
        if not star1 in ConstellationStarList: ConstellationStarList.append(star1)
        if not star2 in ConstellationStarList: ConstellationStarList.append(star2)
        ConstellationLinks.append(entry)
MainLog.Log("ConstellationLinks:",len(ConstellationLinks),"star pairs.",terminal=False)
MainLog.Log("ConstellationLinks:",len(ConstellationStarList),"unique stars.",terminal=False)

# Load NGC list.
MainLog.Log('Loading New General Catalog (NGC) entries from', NGCUrl, '...',terminal=True)
NGCDict = DictionaryLoader(NGCUrl)
NGC_Namelist = [] # List of names.
for key, value in NGCDict.items():
    NGC_Namelist.append(key)

def GenerateNGCDataframe(NGCDict):
    """ Use the Python dictionary to generate a Pandas dataframe.
        Having the data in a dataframe can speed up selection and
        processing of large lists, and moves closer to having common
        routines for handling all the different object lists. """
    MainLog.Log('GenerateNGCDataframe...',terminal=False)
    # The types of NGC objects as defined in the Saguaro database.
    NGCTypes = {"aster":"Asterism",
                "brtnb":"Bright nebula",
                "cl+nb":"Cluster with nebulosity",
                "drknb":"Dark nebula",
                "galcl":"Galaxy cluster",
                "galxy":"Galaxy",
                "glocl":"Globular cluster",
                "gx+dn":"Diffuse nebula in a galaxy",
                "gx+gc":"Globular cluster in a galaxy",
                "g+c+n":"Cluster with nebulosity in a galaxy",
                "lmccn":"LMC cluster with nebulosity",
                "lmcdn":"LMC diffuse nebula",
                "lmcgc":"LMC globular cluster",
                "lmcoc":"LMC open cluster",
                "nonex":"Nonexistent",
                "opncl":"Open cluster",
                "plnnb":"Planetary nebula",
                "smccn":"SMC cluster with nebulosity",
                "smcdn":"SMC diffuse nebula",
                "smcgc":"SMC globular cluster",
                "smcoc":"SMC open cluster",
                "snrem":"Supernova remnant",
                "quasr":"Quasar",
                "1star":"Star",
                "2star":"2 Stars",
                "3star":"3 Stars",
                "4star":"4 Stars",
                "5star":"5 Stars",
                "6star":"6 Stars",
                "7star":"7 Stars"}

    # Store some repeated calculations in the dictionary to improve performance later on.
    count = 0
    for NGCEntry,NGCValues in NGCDict.items():
        MainLog.Log("GenerateNGCDataframe: Loading:",NGCEntry,terminal=False)
        TempRAH = NGCValues['rah'] # Right Ascension HOURS
        TempRAM = NGCValues['ram'] # Right Ascension MINUTES
        TempRAS = NGCValues['ras'] # Right Ascension SECONDS
        NGCValues['radeg'] = HMSToAngle(TempRAH,TempRAM,TempRAS) # Create new 'degrees' right ascension value.
        TempDED = NGCValues['ded'] # Declination DEGREES
        TempDEM = NGCValues['dem'] # Declination MINUTES
        TempDES = NGCValues['des'] # Declination SECONDS
        NGCValues['decdeg'] = DMSToAngle(TempDED,TempDEM,TempDES) # Create new 'degrees' declination value.
        tempw = float(NGCValues['width']) / (60 ** 2) # Convert from arcseconds to degrees
        temph = float(NGCValues['height']) / (60 ** 2)
        if temph == 0.0: temph = tempw # Use WIDTH if HEIGHT is not specified.
        if tempw == 0.0: tempw = temph # Use HEIGHT if WIDTH is not specified.
        if temph == 0.0: temph = tempw = 1/ (60 ** 2) # Default to 1 arc-second if dimensions are not known.
        NGCValues['widthdeg'] = tempw # Convert from arcseconds to degrees
        NGCValues['heightdeg'] = temph
        NGCValues['name'] = NGCEntry
        n_type = NGCValues['type'].lower()
        if n_type in NGCTypes:
            NGCValues['typelabel'] = NGCTypes[n_type]
        else:
            NGCValues['typelabel'] = n_type
        NGCValues['ralabel'] = str(TempRAH) + "h " + str(TempRAM) + "m " + str(TempRAS) + "s"
        NGCValues['declabel'] = str(TempDED) + "d " + str(TempDEM) + "' " + str(TempDES) + '"'
        MainLog.Log("GenerateNGCDataframe: Record",count,":",NGCEntry,": RA deg",NGCValues['radeg'],"Dec deg",NGCValues['decdeg'],n_type,NGCValues['typelabel'],terminal=False)
        count += 1

    # Convert the dictionary to a pandas dataframe.
    NGC_DF = pandas.DataFrame.from_dict(NGCDict) # Convert from dictionary to pandas dataframe (but the rows/columns are transposed).
    NGC_DF = NGC_DF.transpose() # Swap rows/columns the right way round.

    # Eliminate any entries which will never be selected.
    MainLog.Log("GenerateNGCDataframe: Before removing dim objects.",len(NGC_DF),"records.",terminal=False)
    # Filter out dim NGC objects, but make the limit dimmer than the star selection because they are interesting objects.
    boolseries = NGC_DF['magnitude'].between(-100,Parameters.TargetMinMagnitude * 1.5, inclusive='both') # Create filter for items within Magnitude range.
    NGC_DF = NGC_DF[boolseries] # Apply filter.
    MainLog.Log("GenerateNGCDataframe: After removing dim objects.",len(NGC_DF),"records. (Magnitude",Parameters.TargetMinMagnitude,")",terminal=False)
    MainLog.Log("GenerateNGCDataframe: Dataframe contains: Rows",len(NGC_DF),"Columns",NGC_DF.columns,terminal=False)
    
    #  Index(['magnitude', 'rah', 'ram', 'ras', 'ded', 'dem', 'des', 'width',
    #         'height','radeg','decdeg','widthdeg','heightdeg'],
    #        dtype='object')
    #  Data columns (total 13 columns):
    #   #   Column     
    #  ---  ------     
    #   0   magnitude  
    #   1   rah        
    #   2   ram        
    #   3   ras        
    #   4   ded        
    #   5   dem        
    #   6   des        
    #   7   width      
    #   8   height     
    #   9   radeg      
    #   10  decdeg     
    #   11  widthdeg   
    #   12  heightdeg  
    #   13  name
    #   14  ralabel
    #   15  declabel
    NGC_DF.to_pickle(NGCCacheFile) # Save the processed file as a cache to speed things up next time.

    return NGC_DF
    
if ReloadData == False and os.path.exists(NGCCacheFile): # A cache of the NGC data already exists, use it.
    MainLog.Log("NGC data cache exists, using that.",terminal=True)
    NGC_DF = pandas.read_pickle(NGCCacheFile)
else:
    MainLog.Log("No NGC data cache, creating one now.",terminal=True)
    NGC_DF = GenerateNGCDataframe(NGCDict)
MainLog.Log("NGC dataframe contains: Rows",len(NGC_DF),"Columns",NGC_DF.columns,terminal=False)

# Load Meteor shower list.
MainLog.Log('Loading meteor shower list from', MeteorDictUrl, '...',terminal=True)
Meteor_dictionary = DictionaryLoader(MeteorDictUrl)

# Load comet data.
MainLog.Log('Loading comet list from',mpc.COMET_URL,'...',terminal=True)
with load.open(mpc.COMET_URL,reload=ReloadData) as f: # Don't keep reloading it if it is already on disc.
    comets = mpc.load_comets_dataframe(f) # Comet data loaded as a Pandas dataframe.
MainLog.Log(len(comets), 'comets loaded.',terminal=False)
# Keep only the most recent comet trajectory and index by designation for fast lookup.
comets = (comets.sort_values('reference')
          .groupby('designation', as_index=False).last()
          .set_index('designation', drop=False))
# Example lookups.
#row = comets.loc['1P/Halley']
#row = comets.loc['C/1995 O1 (Hale-Bopp)']

CometList = comets['designation'].tolist() # Convert comet designations column into a list for searching later on.

# ----------------------------------------------------------------------------------------------------------

class localstars(attributemaster):
    """ Smart cache of neighbouring stars, to make rendering and markup of images faster.
        Creates a pandas dataframe of stars near the target. 
        The dataframe is automatically updated if the target moves significantly.
        This also standardises and simplifies the selection logic so that all image generators
        will give similar results.

        Some notes on PANDAS! It can be complicated to understand what's going on under the hood.
        - Small changes to dataframe references can have unexpected impact upon performance.
          Pandas can be blisteringly fast, but making a small change can turn it into devastatingly slow.
        - It's easy to get lost in indexing in Pandas. There are multiple ways to find/reference items
          and the syntax is not always easy for a beginner. 
        - It's easy to confuse .iloc[], .loc[], .at[] methods for example, and you can retrieve the wrong information by accident.
        - Updating Pandas dataframe rows/columns has been problematic at times for multiple reasons.
        - Most 'selections' of Pandas dataframe rows here will return 'copies' of the data rather than pointers to the original,
          so when updating back to the dataframe, be sure to select the same row in the source dataframe and update that!

        Using some ChatGPT style coding tools has sometimes been useful to break deadlocks when getting Pandas to behave as expected.
        The Pandas code here is unlikely to be perfect - I'm not an expert in it, it works, but can certainly be improved.

        Finding a specific HIP star row using     MyRow = self._df.loc[hip_num] 
        Finding a specific row using index        MyRow = self._df.iloc[row_num] 
        Finding a specific cell using             MyCell = self._df.loc[hip_num,'magnitude'] 
                                                  MyCell = self._df.iloc[row_num]['magnitude']
                                                  MyCell = self._df.iat[row_num,col_num]
        Find col_num for a specific column using localstars.ColumnIndex('magnitude')
        - This returns None if the column name is not known.        """
    
    def __init__(self,ra,dec,radius,magnitude,maxstars=1000,logger=None):
        if logger == None: self.Log = CamLog.Log
        else: self.Log = logger
        self.Log("localstars.__init__(",ra,dec,radius,magnitude,maxstars,"):",terminal=False)
        self._df = None # Pandas dataframe.
        self.MasterDf = HipparcosDf # The master dataframe that the cache is built from.
        self.StarFilter = [] # Integer list of HIP numbers to filter against.
        self.updated = None # Timestamp when the cache was last updated.
        self.ra = ra # Centre RIGHT ASCENSION in degrees.
        self.dec = dec # Centre DECLINATION in degrees.
        self.radius = radius # Selection radius in degrees. 
        self._updateangle = radius / 4 # When centre has moved this far, it's time to update.
        self.magnitude = magnitude # Minimum magnitude to select. Ignore any stars dimmer than this.
        self.maxstars = maxstars # Maximum number of stars to select.
        self.Update(ra,dec) # Trigger update immediately to load the cache.
        
    def Update(self,ra,dec):
        self.Log("localstars.Update(",ra,dec,"): Begin",terminal=False)
        self._df = None # Clear old cache.
        self.ra = ra # Update RIGHT ASCENSION location.
        self.dec = dec # Update DECLINATION location.
        self.MinRADeg = self.ra - self.radius
        self.MaxRADeg = self.ra + self.radius
        self.MinDecDeg = self.dec - self.radius
        self.MaxDecDeg = self.dec + self.radius
        # Select a subset of the Hipparcos catalog which is within TargetInclusionRadius of the target (=centre of image)
        self.Log("localstars.Update(): CoreSelection RA",self.MinRADeg,"deg ...",self.MaxRADeg,"Dec",self.MinDecDeg,"...",self.MaxDecDeg,terminal=False)
        self._df = self.MasterDf.loc[(self.MasterDf['ra_degrees'] >= self.MinRADeg) & (self.MasterDf['ra_degrees'] <= self.MaxRADeg) & (self.MasterDf['dec_degrees'] >= self.MinDecDeg) & (self.MasterDf['dec_degrees'] <= self.MaxDecDeg) & (self.MasterDf['magnitude'] <= self.magnitude)]
        self.Log("localstars.Update(): Starting with",len(self._df),"stars in the master list.",terminal=False)
        if self.MinRADeg < 0: # -ve RA values need adjusting to 0-360 range.
            self.Log("localstars.Update(): -ve RA Selection RA",self.MinRADeg + 360,"deg...",360,"Dec",self.MinDecDeg,"...",self.MaxDecDeg,terminal=False)
            df1 = self.MasterDf.loc[(self.MasterDf['ra_degrees'] >= self.MinRADeg + 360) & (self.MasterDf['ra_degrees'] <= 360) & (self.MasterDf['dec_degrees'] >= self.MinDecDeg) & (self.MasterDf['dec_degrees'] <= self.MaxDecDeg) & (self.MasterDf['magnitude'] <= self.magnitude)]
            self.Log("localstars.Update(): Appending",len(df1),"stars to the master list. (<0rule)",terminal=False)
            self._df = pandas.concat([self._df,df1]) # Add to original list.
        # If MaxRaDeg > 360 then subtract 360 and append result 0<x<=MaxRaDeg
        if self.MaxRADeg > 360: # +ve RA values over 360 need adjusting to 0-360 range.
            self.Log("localstars.Update(): +ve RA Selection RA",0,"...",self.MaxRADeg - 360,"deg Dec",self.MinDecDeg,"...",self.MaxDecDeg,terminal=False)
            df2 = self.MasterDf.loc[(self.MasterDf['ra_degrees'] >= 0) & (self.MasterDf['ra_degrees'] <= self.MaxRADeg - 360) & (self.MasterDf['dec_degrees'] >= self.MinDecDeg) & (self.MasterDf['dec_degrees'] <= self.MaxDecDeg) & (self.MasterDf['magnitude'] <= self.magnitude)]
            self.Log("localstars.Update(): Appending",len(df2),"stars to the master list. (>360rule)",terminal=False)
            self._df = pandas.concat([self._df,df2]) # Add to original list.
        self._df = self._df.sort_values(['magnitude'],ascending=[True]) # Sort the selected stars in ascending order of brightness. So we can match the brightest stars first.
        # If there's a StarFilter specified, apply it now.
        if len(self.StarFilter) != 0:
            self.Log("localstars.Update(): Applying filter.",terminal=False)
            self.Filter()
            self.Log("localstars.Update(): Applied filter.",terminal=False)
        # Clip to maxstars.
        self.Log("localstars.Update(): Clipping dataframe.",terminal=False)
        self._df = self._df[:self.maxstars]
        self.Log("localstars.Update(): Clipped dataframe.",terminal=False)
        self.update = NowUTC() # Update timestamp.
        self.Log("localstars.Update(): Selected",len(self._df.index),"rows.",terminal=False)
        self.Log("localstars.Update(): Setting index.",terminal=False)
        self._df = self._df.set_index('hip',drop=False) # Make 'hip' the index of the DataFrame, but keep the 'hip' column for reference.
        self.Log("localstars.Update(): Set index.",terminal=False)
        self.ColumnNames = list(self._df.columns) # Get list of column names in sequence.
        self.Log("localstars.Update(): ColumnNames are",self.ColumnNames,terminal=False)
        self.Log("localstars.Update(): End",terminal=False)
        return True

    def ColumnIndex(self,name):
        """ Return the column index for any given column name.
            This is the column index number used in Pandas dataframe.iloc[] references. """
        if not name in self.ColumnNames:
            self.Log("localstars.ColumnIndex:",name,"is not in",self.ColumnNames,level='error',terminal=True)
            return None
        return self.ColumnNames.index(name)

    def SetFilter(self,filterlist):
        """ Set the self.StarFilter list. """
        self.StarFilter = []
        for i in filterlist: # Make sure all values in the list are integers.
            if not int(i) in self.StarFilter: # Ignore duplicates.
                self.StarFilter.append(int(i))

    def Filter(self):
        """ Given a list of Hipparcos ID,s filter the dataframe.
            Only entries in the starlist are retained. """
        self._df = self._df[self._df.hip.isin(self.StarFilter)]
        return True        

    def Get(self,ra,dec):
        self.Log("localstars.Get(",ra,dec,"): Begin",terminal=False)
        if abs(self.ra - ra) > self._updateangle or abs(self.dec - dec) > self._updateangle: 
            self.Log("localstars.Get(): Target location has moved enough to trigger a refresh.",terminal=False)
            self._df = None # Trigger refresh if target location has changed enough.
        if type(self._df) == type(None): # Need to update
            self.Update(ra,dec) # Perform the update.
        self.Log("localstars.Get(): End",terminal=False)
        return self._df

#------------------------------------------------------------------------------------------------------------------------------

# This uses built in astro corrected time functions rather than going to the web for them.
# I think these corrections will gradually fall out of date unless Skyfield is updated periodically.
ts = load.timescale() # Time handling with astro corrections.

def SkyfieldNow(real=False):
    """ Return skyfield format current time.
        Available as a method so that offsets or other features can be added if needed. 
        if ClockOffset is set, that many seconds are added to the result. Allowing you to run the program against other dates/times.
        if real == True, then the Clockoffset is not applied, giving the true CPU time. """
    global ClockOffset
    result = ts.now() # Now. # *Q* Offset supported.
    if real == False and ClockOffset != None: # Can apply time offset.
        dt = Ts2Datetime(result)
        dt + timedelta(seconds=ClockOffset)
        result = Datetime2Ts(dt)
    return result

t = SkyfieldNow() # Now. # Offset supported.

# Use camera FOV to establish the selection radius of stars.
# Establish a list of stars which surround the target. 
# If needed the list updates itself automatically each time it's queried via the Get() method.
# - 2 lists are built.
# - LocalStars is a list of stars within the narrow field of view of the camera. These are the ones we expect to see in the images.
# - ConstellationStars is a list of stars from a wider field of view, but which are part of constellation patterns. These are used to help markup constellation lines in preview images.
inclusionradius = math.sqrt((CameraInUse.Lens.FovHorizontal ** 2) + (CameraInUse.Lens.FovVertical ** 2)) * 2
LocalStars = localstars(ra=0.0,dec=0.0,radius=inclusionradius,magnitude=Parameters.LocalStarsMagnitude,maxstars=10000,logger=CamLog.Log) # Narrow field of view, list of all visible stars.
ConstellationStars = localstars(ra=0.0,dec=0.0,radius=inclusionradius + 5,magnitude=Parameters.ConstellationStarsMagnitude,maxstars=10000,logger=CamLog.Log) # Wider field of view, but filtered to just key constellation stars.
ConstellationStars.SetFilter(ConstellationStarList) # The ConstellationStars list is filtered by this list.

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

# And ISS position from CelesTrak data (TLE lines).
celestrakurl = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
MainLog.Log("Loading CelesTrak station data from",celestrakurl,terminal=True)
CelesTrak = celestrak(celestrakurl,logger=MainLog,projectroot=ProjectRoot)


if ReloadData: # We reloaded the data, quit here because STDIN can sometimes close during all the processing.
    print(textcolor.yellow("Reload complete: Please restart the program."))
    exit() # Quit the program. This is a workaround to a problem where the Python 'input' statements fail after the hipex_load_dataframe() function has executed for a long time.

# ------------------------------------------------------------------------------------------------------

MainLog.Log("Establish observer's location:",Parameters.HomeLat,Parameters.HomeLon,terminal=False)
HomeSite = planets['earth'] + HomeSiteTopos # Define HomeSite as a point on earth. Could be from GPS too.
RadecBase = Star(ra_hours=(0,0,0.0), dec_degrees=(0,0,0.0)) # To calculate where Radec ZERO point is. (For Equatorial mount positioning)

# ------------------------------------------------------------------------------------------------------

class FixedPoint(attributemaster):
    """ A target object which is a fixed altitude and azimuth position. 
        It doesn't move with the sky. """
    def __init__(self,name,alt,az):
        self.Name = name
        self.Altitude = alt
        self.Azimuth = az

#-------------------------------------------------------------------------------------------------------

class target(attributemaster):
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
        self.Magnitude = magnitude
        self.DiameterDegrees = objectdiameter # diameter of the object in the sky. # Used to warn if target is too small.!
        self.RecommendedExposure = None # Recommended exposure for this object.
        self.HomeSite = None # Skyfield object for home site.
        self.HomeSiteTopos = None # Skyfield object for home site.
        self.ts = load.timescale() # Time handling with astro corrections. ! Don't use this to read current time, always use SkyfieldNow() function!
        self.SetHome(Parameters.HomeLat,Parameters.HomeLon) # Use global variables at the moment. Requires that global list 'planets' is available too.
        self.CometPandasRow = cometpandasrow # Comets don't have a skyfield object in 'Handle' we calculate the position differently, so store their pandas row here. 
        self.CacheRADeg = None # Cached RA value for target. Set each time RaDecDegrees is called.
        self.CacheDec = None # Cached Dec value for target. Set each time RaDecDegrees is called.
        self.CacheAlt = None # Cached Altitude value for target. Set each time AzAltDegrees is called.
        self.CacheAz = None # Cached Azimuth value for target. Set each time AzAltDegrees is called.
        self.PrevT = None # TS timestamp when location was last checked (for calculating angular velocity)
        self.AzSpeed = 0.0 # Angular speed (deg/sec)
        self.AltSpeed = 0.0 # Angular speed (deg/sec)
        self.PrevAz = None # Previous location
        self.PrevAlt = None # Previous location
        self.RotationPoint = None # Will hold rotation reference point if activated.

    
    def Datetime2Ts(self,dt): # Referenced by external dependencies.
        """ Convert datetime into TS (skyfield) timestamp. """
        t = Datetime2Ts(dt) # Convert to skyfield time type.
        return t

    def CurrentMagnitude(self,time=None):
        """ Calculate the current magnitude (or for a specific time) if possible. """
        if time == None: time = self.CurrentTime()
        result = self.Magnitude # Default to the standard magnitude for this object if known.
        try:
            astrometric = self.HomeSite.at(time).observe(self.Handle)
            temp = planetary_magnitude(astrometric)
            if temp != None: result = temp
            self.Log("target.CurrentMagnitude: planetary_magnitude returned",temp,terminal=False)
        except Exception:
            self.Log("target.CurrentMagnitude: planetary_magnitude didn't work for this target.",terminal=False)
        return result

    def UpdateLocation(self,newhandle):
        """ Revise the skyfield target handle. 
            Used when performing sky surveys of multiple locations around a target.
            Use this if you need to modify the location of the target for some reason (eg new RADEC) but retain all the other attributes. """
        self.Handle = newhandle
        self.RotationPoint = None # Will hold rotation reference point if activated.
        self.Log("target.UpdateLocation(): New co-ordinates updated to the target.",terminal=False)

    def NextRiseSetObject(self):
        """ Return next horion event and time for distant objects. (Moon and beyond) """
        risetime = None # No RISE time until identified.
        settime = None # No SET time until identified.
        f = almanac.risings_and_settings(planets, self.Handle, self.HomeSiteTopos)
        tsnow = self.CurrentTime().utc_datetime() # Current Timestamp as conventional Python UTC datetime value.
        t0 = self.ts.utc(tsnow.year, tsnow.month, tsnow.day) # Generate skyfield UTC timestamp for start of day. # Doesn't need offset support.
        tsnow += timedelta(days=1) # Move forward 24 hours.
        t1 = self.ts.utc(tsnow.year, tsnow.month, tsnow.day + 1) # Generate skyfield UTC timestamp for start of following day. # Doesn't need offset support.
        t, y = almanac.find_discrete(t0, t1, f) # Return list of rise/set times within window.
        # If the object never rises/sets in the timeperiod checked, there are not values here, so None,None will be returned.
        for ti, yi in zip(t, y): # Combine t and y lists.
            self.Log('target.RiseSet(',self.Name,'): zipped',ti, yi, terminal=False)
            tidt = ti.utc_datetime()
            if tidt < NowUTC(): continue # In the past, ignore it.
            if yi and risetime == None: # First future rise time.
                risetime = tidt
            elif settime == None: # First future set time.
                settime = tidt
        return risetime, settime
    
    def NextRiseSetSatellite(self):
        """ Return next horizon event and time for satellites. """
        self.Log("target.NextRiseSetSatellite(",self.Name,")",terminal=False)
        risetime = settime = None
        t_from = self.CurrentTime() # Start now.
        t_to = TsDelta(t_from,dd=1) # Stop in 24hours time.
        self.Log("target.NextRiseSetSatellite: t_from",str(t_from),"t_to",str(t_to),terminal=False)
        times, events = self.Handle.find_events(self.HomeSiteTopos, t_from, t_to, Parameters.MinSatelliteAltitude) # What events occur above horizon in next 24 hours?
        self.Log("target.NextRiseSetSatellite: times",times,"events",events,terminal=False)
        telist = zip(times,events)
        for te in telist:
            self.Log("target.NextRiseSetSatellite: Entry:",te,terminal=False)
            eventtime = te[0]
            eventtype = te[1] # 0=Rise, 1=Culminate, 2=Set
            if eventtype == 2 and settime == None and risetime != None: settime = eventtime.utc_datetime()
            if eventtype == 0 and risetime == None: risetime = eventtime.utc_datetime()
            if eventtype == 1: # Culmination, how high?
                self.Log("target.NextRiseSetSatellite: Checking culmination at",eventtime.utc_datetime(),terminal=False)
                az,alt = self.AzAltDegrees(time=eventtime)
                self.Log("target.NextRiseSetSatellite: Culmination at",eventtime.utc_datetime(),"is",Deg3dp(alt),DegreeSymbol,terminal=False)
            if risetime != None and settime != None: break # We have our earliest acceptable set of values.
        self.Log("target.NextRiseSetSatellite: Rise",risetime,"set",settime,terminal=False)
        return risetime, settime

    def SatellitePasses(self,window=24):
        """ Print table of satellite pass information for next xx hours. """
        self.Log("target.SatellitePasses: NOT YET IMPLEMENTED.",terminal=False)
        t_from = self.CurrentTime() # Start now.
        t_to = TsDelta(t_from,dd=1) # Stop in 24hours time.
        self.Log("target.SatellitePasses: t_from",str(t_from),"t_to",str(t_to),terminal=False)
        if not hasattr(self.Handle,'find_events'): # This object doesn't support satellite pass calculations.
            self.Log("target.SatellitePasses: find_events method not in this target type.",terminal=True)
            return
        times, events = self.Handle.find_events(self.HomeSiteTopos, t_from, t_to, 0.0) # What events occur above horizon in next 24 hours?
        self.Log("target.SatellitePasses: times",times,"events",events,terminal=False)
        passelements = [] # List of the 3 elements of a pass. [[eventdetails],[eventdetails],[eventdetails]]
        listofpasses = [] # List of all the passes. [[passelements].[passelements],[passelements],...]
        for i,eventtime in enumerate(times):
            eventtype = events[i]
            eventdatetime = eventtime.utc_datetime()
            eventaz, eventalt = self.AzAltDegrees(time=eventtime)
            eventdetails = [] # List of the event details. (3 of these per pass) [eventtype,eventdatetime,eventaz,eventalt]
            eventdetails.append(eventtype)
            eventdetails.append(eventdatetime)
            eventdetails.append(eventaz)
            eventdetails.append(eventalt)
            passelements.append(eventdetails) # Add event details to the list of events in this pass.
            if eventtype == 2 and len(passelements) == 3: # We have the last entry of a complete set of three entries.
                listofpasses.append(passelements) # Append to list of passes and start constructing the next event.
                passelements = []
                
        # Now show the list of passes as a table.
        print(textcolor.yellow("Satellite: " + self.Name))
        print(textcolor.yellow("Passes which culminate above " + str(Parameters.MinSatelliteAltitude) + DegreeSymbol))
        print(textcolor.yellow("Matching passes within next " + str(window) + "hrs."))
        print("Pass rises             Az   Alt     Duration     Sets    Az")
        #     "2023-05-12 00:52:42 246.0° 53.0° 00h:02m:43s 00:55:26 121.0°"
        
        for passentry in listofpasses:
            risetime = passentry[0][1] # 0 = Rise, 1 = datetime
            settime = passentry[2][1] # 2 = Set, 1 = datetime
            duration = (settime - risetime).total_seconds()
            if duration < 60: continue # Less than 1 minute above horizon, so don't bother.
            if passentry[1][3] < Parameters.MinSatelliteAltitude: continue # It doesn't get high enough.
            riseaz = passentry[0][2] # 0 = Rise, 2 = azimuth
            maxalt = passentry[1][3] # 1 = Culmination, 3 = altitude
            setaz = passentry[2][2] # 2 = Set, 2 = azimuth
            duration = (settime - risetime).total_seconds()
            line = ''
            line += textcolor.green(str(risetime).split('.')[0]) + ' ' # When does satellite rise.
            line += textcolor.green(str(round(riseaz,0)).rjust(5,' ') + DegreeSymbol) + ' ' # Where does it rise?
            line += textcolor.yellow(str(round(maxalt,0)).rjust(4,' ') + DegreeSymbol) + ' ' # How high does it climb?
            line += textcolor.yellow(HRSeconds(duration)) + ' ' # How long is it above the horizon?
            line += textcolor.red(str(settime).split('.')[0].split(' ')[1]) + ' ' # When does satellite set.
            line += textcolor.red(str(round(setaz,0)).rjust(5,' ') + DegreeSymbol) + ' ' # Where does it set?
            print (line)
        return
        
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

    def NextRiseSetHHMM(self,window=None):
        """ Returns next RISE or SET time as HH:MM string. 
            window says how many hours into the future is acceptable. 
            Outside this window it returns '--:--' """
        eventtype, eventtime = self.NextRiseSet()
        result = ''
        if eventtype == 'rise':
            result = str(eventtime)[11:16] + Symbol['up']
        elif eventtype == 'set':
            result = str(eventtime)[11:16] + Symbol['down']
        if window != None and eventtime != None:
            cutoff = NowUTC() + timedelta(hours=window)
            if eventtime > cutoff: # Outside window.
                result = '--:--'
        self.Log("target.NextRiseSetHHMM(",self.Name,"): eventtime",eventtime,"eventtype",eventtype,"result",result,terminal=False)
        return result

    def RiseSet(self):
        """ Return next rise and set times for the object. 
            Uses Skyfield's almanac functions for this. """
        risetime = None # No RISE time until identified.
        settime = None # No SET time until identified.
        if self.IsFixedPoint(): # No risetime/settime time for fixed point. 
            pass
        elif self.ObjectType == 'earth satellite':
            risetime, settime = self.NextRiseSetSatellite()
        else: # Moving target, so check for rise/set times.
            risetime, settime = self.NextRiseSetObject()
        self.Log("target.RiseSet(",self.Name,"): rise",risetime,"set",settime,terminal=False)
        return risetime, settime

    def CurrentTime(self,real=False):
        """ Return skyfield format current time.
            Available as a method so that offsets or other features can be added if needed. 
            if ClockOffset is set, that many seconds are added to the result. Allowing you to run the program against other dates/times.
            if real == True, then the Clockoffset is not applied, giving the true CPU time. """
        result = SkyfieldNow() # Now. # Offset supported.
        if real == False and ClockOffset != None: # Can apply time offset.
            dt = Ts2Datetime(result)
            dt + timedelta(seconds=ClockOffset)
            result = Datetime2Ts(dt)
        return result

    def AltAzToRaDec(self,alt,az,time=None,asdegrees=False):
        """ Given alt,az coordinates (in degrees), return the current ra/dec values. 
            
            Code based upon 
                https://stackoverflow.com/questions/54827466/find-ra-dec-from-an-azimuth-elevation-in-skyfield by rfkortekaas 
                
            asdegrees = True, both RA and DEC are returned as an angle rather than the RA object. """

        if time != None:
            t = time
        else:
            t = ts.now()
        lookingat = HomeSite.at(t).from_altaz(alt_degrees=alt, az_degrees=az)
        ra, dec, _ = lookingat.radec()
        if asdegrees: # Convert to pure degree values.
            ra = ra._degrees
            dec = dec.degrees
        return ra,dec

    def RaDecToAltAz(self,ra,dec,time=None,asdegrees=True):
        """ Given any ra,dec coordinates (in degrees) return alt-az values.
            asdegrees TRUE = ra is a float degree value.
            asdegrees FALSE = ra is a list of H,M,S values. """
        if time == None: time = self.CurrentTime() # Current time.
        if asdegrees: # Receiving input parameters as degree values. 
            rah,ram,ras = AngleToHMS(ra)
        else: # Receiving input as list.
            rah = ra[0]
            ram = ra[1]
            ras = ra[2]
        TempStar = Star(ra_hours=(rah,ram,ras), dec=Angle(degrees=dec)) # Create a Skyfield target object.
        TempStarAlt, TempStarAz, TempStardistance = HomeSite.at(time).observe(TempStar).apparent().altaz() 
        return TempStarAlt.degrees,TempStarAz.degrees

    def SetHome(self,homelat,homelon):
        self.HomeSiteTopos = Topos(homelat,homelon)
        self.HomeSite = planets['earth'] + self.HomeSiteTopos # Define HomeSite as a point on earth. Could be from GPS too.

    def AzAltDegrees(self,time=None,updatespeed=False):
        """ Returns the current altitude and azimuth of the target from Skyfield calculations. 
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
            updatespeed = True The angular velocity of the target is updated too. """
        if self.HomeSite == None:
            raise Exception ("Target.AzAltDegrees(",self.Name,"): HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        if self.IsFixedPoint(): # Telescope is following fixed alt/az position. Ignoring sky movement.
            alt = self.Handle.Altitude
            az = self.Handle.Azimuth
            self.AltVelocity = 0.0
            self.AzVelocity = 0.0
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
        if updatespeed: # Update the angular velocity figures too.
            if self.PrevT != None:
                timediff = (Ts2Datetime(t) - Ts2Datetime(self.PrevT)).total_seconds()
                if timediff != 0.0:
                    self.AzSpeed = (azd - self.PrevAz) / timediff
                    self.AltSpeed = (altd - self.PrevAlt) / timediff
                else:
                    self.AzSpeed = self.AltSpeed = 0.0
            else:
                self.Log("target.AzAltDegrees(",self.Name,") no previous measure yet.",terminal=False)
            self.PrevAz = azd
            self.PrevAlt = altd
            self.PrevT = t
        return azd, altd

    def IsFixedPoint(self):
        """ Return TRUE if this is a fixed point. Else False.
            This is used in places to allow the telescope to take photos even though 
            it is not following a trajectory. """
        if isinstance(self.Handle,FixedPoint):
            return True
        else:
            return False

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
            raise Exception ("Target.RaDecHours",self.Name,": HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        if self.IsFixedPoint(): # Telescope is following fixed alt/az position. Ignoring sky movement.
            ra,dec = self.AltAzToRaDec(self.Handle.Altitude,self.Handle.Azimuth)
        elif hasattr(self.Handle,'center') and self.Handle.center == 399: # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite. # *Q* Could check searchgroup = 'satellite' instead?
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
            raise Exception ("Target.RaDecDegrees:",self.Name,": HomeSite is not defined. Set Target.HomeSite before calling this function.")
        if time != None: t = time # Use a given timestamp.
        else: t = self.CurrentTime() # Now.
        if self.IsFixedPoint(): # Telescope is following fixed alt/az position. Ignoring sky movement.
            ra,dec = self.AltAzToRaDec(self.Handle.Altitude,self.Handle.Azimuth)
        elif hasattr(self.Handle,'center') and self.Handle.center == 399: # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite. # *Q* Could check searchgroup = 'satellite' instead?
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
            self.Log("target.ApparentCometMagnitudeGK(",self.Name,"): Using OLD format fieldnames.",terminal=False)
        else: # Post Nov.2020 version of Skyfield. To be verified.
            g_absoluteMagnitude = self.CometPandasRow['magnitude_g']
            k_luminosityIndex = self.CometPandasRow['magnitude_k']
            self.Log("target.ApparentCometMagnitudeGK(",self.Name,"): Using NEW format fieldnames.",terminal=False)
        t = self.CurrentTime()
        temp_ra, temp_dec, sunBodyDistance = planets['sun'].at(t).observe(self.Handle).radec() 
        temp_alt, temp_az, earthBodyDistance = self.HomeSite.at(t).observe(self.Handle).apparent().altaz() 
        temp_alt, temp_az, earthSunDistance = self.HomeSite.at(t).observe(planets['sun']).apparent().altaz() 
        apparentMagnitude = g_absoluteMagnitude + (5 * math.log10(earthBodyDistance.au)) + (2.5 * k_luminosityIndex * math.log10(sunBodyDistance.au))
        apparentMagnitude = round(apparentMagnitude,1) # Magnitude to 1 decimal place.
        self.Log("target.ApparentCometMagnitudeGK(",self.Name,"): Apparent magnitude:", apparentMagnitude,terminal=False)
        return apparentMagnitude

# ------------------------------------------------------------------------------------------------------

def ChooseMessier(prechosen=None,sizewarning=True):
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

def ChooseMeteor(prechosen=None):
    """ Select a meteor shower. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
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
                MainLog.Log("ChooseMeteor: Found by meteor shower name (" + key+ ").",terminal=False)
                break
        if Result == "": # Still no match. Give up and ask again. 
            if prechosen != None:
                MainLog.Log("ChooseMeteor: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("Meteor: Nothing matched, try again.")
    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    # Find location of origin.
    obstarget = target(handle=p,name=NeatName,objecttype='meteor',constellation=const,description=desc,magnitude=magnitude,searchgroup='meteor',searchterm=SearchValue)
    az, alt = obstarget.AzAltDegrees() # Get initial position in the sky. We'll turn this into a fixed point.
    # Move a useful angle away from the origin.
    es = FixedPoint(name=NeatName,alt=alt,az=az) # Set a fixed point in the sky. The telescope will remain under direct control and not use trajectories.
    obstarget = target(es,name=NeatName,objecttype="meteor",description=desc,magnitude=0.0,searchgroup='meteor',searchterm=SearchValue)
    MainLog.Log("NOTE: Meteor shower selected. Camera will point to a likely area of the sky to capture meteors, not the radiant point.",terminal=False)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseNGC(prechosen=None):
    """ Select a NGC object. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
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
                MainLog.Log("ChooseNGC: Found by NGC number (" + key + ").",terminal=False)
                break
        if Result == "": # Still no match. Ask again. 
            if prechosen != None:
                MainLog.Log("ChooseNGC: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("NGC: (",str(SearchValue),") Nothing matched, try again.")
    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    obstarget = target(handle=p,name=NeatName,objecttype="ngc",constellation=const,description=desc,magnitude=magnitude,searchgroup='ngc',searchterm=SearchValue)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseComet(prechosen=None):
    """ Select a comet from the comet catalog by comet name. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameters is not recognised, the user is asked fora value instead. """
        
    Result = ""
    desc = None
    obstarget = None
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
                    MainLog.Log("ChooseComet: Found by comet name (" + c + ")",terminal=False)
                    break
        if Result == "": # Still no match. Give up and ask again. 
            if prechosen != None:
                MainLog.Log("ChooseComet: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("Comet: Nothing matched, try again.")

    MainLog.Log("ChooseComet: NOTE: obstarget.handle() is populated in the target.__init__() method in the case of comets.",terminal=False)

    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    obstarget = target(handle=p,name=NeatName,objecttype="comet",description=desc,constellation=None,magnitude=None,searchgroup='comet',searchterm=SearchValue,cometpandasrow=row)
    obstarget.Magnitude = obstarget.ApparentCometMagnitudeGK() 
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseHipparcos(prechosen=None):
    """ Select a star from the Hipparcos catalog by Catalog number, star name or constellation. 
        'prechosen' means that the input is provided externally, the function will not prompt. 
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    desc = None
    const = None
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
            MainLog.Log("ChooseHipparcos: Pandas row available data for the star:", str(list(HipparcosDf.columns)),terminal=False) # Show available data.
            starrec = HipparcosDf.loc[HipparcosDf.hip == SearchInt].iloc[0] # Return just the 1st record from the result.
            p = Star.from_dataframe(starrec)
            desc = "Star HIP_" + str(SearchInt) + " (Hipparcos)."
            const = starrec['constellation']
            magnitude = starrec['magnitude']
            MainLog.Log("ChooseHipparcos: Found by catalog number.",terminal=False)
        if Result == "": # No match yet.
            if prechosen != None:
                MainLog.Log("ChooseHipparcos: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Return to calling routine.
            print("Hipparcos: Nothing matched, try again.")

    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    obstarget = target(handle=p,name=NeatName,objecttype="star",description=desc,constellation=const,magnitude=magnitude,searchgroup='hipparcos',searchterm=str(SearchInt))
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseSolar(prechosen=None):
    """ Choose a solar system target. 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    MainLog.Log("ChooseSolar: Begin",terminal=False)
    AvailableTargets = ["sun","mercury","venus","moon","mars","jupiter","saturn","uranus","neptune","pluto"]
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
    else:
        MainLog.Log("ChooseSolar: Could not initialize target (" + Result + ")",level="error")
        raise Exception ("ChooseSolar: Could not initialize target (" + Result + ")")
    MainLog.Log("ChooseSolar: End " + obstarget.Name,terminal=False)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseLocalTZ(default=None):
    """ Allow the user to choose the local timezone from the available list. """
    Result = ''
    MainLog.Log('ChooseLocalTZ: Begin',terminal=False)
    TZChooser = listchooser(pytz.all_timezones,compress=False) # Always show the full list.
    while Result == '':
        Result = TZChooser.Prompt()
        if Result == None:
            return default
        if not Result in pytz.all_timezones:
            print(textcolor.red("'" + Result + "' is not recognised. Try again."))
            Result = ''
    return Result

# ------------------------------------------------------------------------------------------------------

def DefineLocalTZ():
    """ Allow the user to set the local timezone in the Parameter file. """
    MainLog.Log('DefineLocalTZ: Begin',terminal=False)
    print(textcolor.yellow('Define local Timezone'))
    print('Pi-lomar operates in UTC time, you can define a local timezone here')
    print('however beware that this is currently for information only.')
    print('Most of the displays will continue to show UTC values.')
    Result = ChooseLocalTZ(Parameters.LocalTZ)
    if Result != None:
        MainLog.Log('DefineLocalTZ: Setting',Result,terminal=False)
        Parameters.LocalTZ = Result
        print("Local Timezone set to",Parameters.LocalTZ)
        nutc = NowUTC()
        print("UTC time is",nutc)
        print("Local time is",UTCtoLocal(nutc))
    MainLog.Log('DefineLocalTZ: End',terminal=False)
    
# ------------------------------------------------------------------------------------------------------

def ChooseSatellite(prechosen=None):
    """ Choose a satellite target (eg space stations). 
        'prechosen' means that the input is provided externally, the function will not prompt.
        If the prechosen parameter is not recognised, the user is asked for a value instead. """
    Result = ""
    MainLog.Log("ChooseSatellite: Begin",terminal=False)
    AvailableTargets = CelesTrak.SatelliteList
    SatelliteChooser = listchooser(AvailableTargets,compress=False) # Always show the full list.
    obstarget = None
    while Result == "":
        if prechosen == None: # We've not received a prechosen name, so ask the user.
            Result = SatelliteChooser.Prompt()
        else: # We've received a prechosen name. Don't ask the user.
            Result = prechosen
        if Result == None: # Nothing selected.
            return None # Quit.
        MainLog.Log("ChooseSatellite: Observation target input:" + Result,terminal=False)
        if Result not in AvailableTargets:
            if prechosen != None:
                MainLog.Log("ChooseSatellite: Prechosen '" + str(prechosen) + "' not recognised. Ignored.",terminal=False)
                MainLog.Log("ChooseSatellite: Recognised list:",str(AvailableTargets),terminal=False)
                return None # Scrap the attempt.
            print (textcolor.red("'" + Result + "' is not a recognised target name. Try again."))
            Result = ""
    line1, line2 = CelesTrak.GetTleLines(Result) # Get the TLE entry for the chosen satellite.
    if line1 != None:
        es = EarthSatellite(line1, line2, Result, ts)
        obstarget = target(es,name=Result,objecttype="earth satellite",description="Spacestation:" + Result,magnitude=-6.0,searchgroup='satellite',searchterm=Result)
    else:
        MainLog.Log("ChooseSatellite: Could not initialize target (" + Result + ")",level="error")
        raise Exception ("ChooseSatellite: Could not initialize target (" + Result + ")")
    MainLog.Log("ChooseSatellite: End " + obstarget.Name,terminal=False)
    return obstarget

# ------------------------------------------------------------------------------------------------------

def RadecObject(prechosen=None):
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

def AltazObject(prechosen=None):
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

def ChooseFilterScript(default=None):
    """ From the available filter scripts, choose one to apply to a task. """
    option = None
    FilterOptions = {
        'None':{'label':'None', 'value':None}
    }
    for key,item in pilomarimage.FILTERSCRIPTS.items():
        FilterOptions[key] = {'label':key, 'value':key}
    FilterMenu = optionmenu(FilterOptions,'Select filter',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    option, found = FilterMenu.Prompt() # Ask the user to select an option from the menu.
    if not found: # Nothing was selected. Return the default value instead.
        option = default
    return option

# ------------------------------------------------------------------------------------------------------

def SelectLatestFilter():
    """ Prompt the user to select a Tracking image filter. """
    print("Choose the filter script to use for processing LATEST TRACKING images.")
    Parameters.LatestTrackingFilter = ChooseFilterScript(default=Parameters.LatestTrackingFilter)
    print("You chose:",Parameters.LatestTrackingFilter) 
    if Parameters.LatestTrackingFilter == None:
        print("LATEST TRACKING images will not be filtered.")
    else:
        print("LATEST TRACKING images will have the following filters applied.")
        ftemp = pilomarimage.FILTERSCRIPTS[Parameters.LatestTrackingFilter] # Get the filter details.
        # List the filter steps.
        for key,value in ftemp.items():
            method = value.get('method',None)
            comment = value.get('comment','')
            if comment != '': comment = "(" + comment + ")"
            print(" -",key,"step applies",method,"filter",comment)
    MainLog.Log("SelectLatestFilter: has set",Parameters.LatestTrackingFilter,terminal=False)
    
# ------------------------------------------------------------------------------------------------------

def TestLatestFilter():
    """ Test the result of the LATESTTRACKING image filter on an example image. """
    print(textcolor.yellow("Test the LATEST TRACKING image filter script on an example image."))
    print("Choose an image to process:")
    sourcefile = ''
    outputfile = FolderList["temp"] + "TestLatestFilter.jpg"
    while os.path.exists(sourcefile) == False:
        sourcefile = input(textcolor.cyan("Filepath ('x' to quit): "))
        if sourcefile.lower() == 'x': return # Quit.
        if not os.path.exists(sourcefile):
            print(textcolor.red(sourcefile,"does not exist, try again."))
    # Create pilomarimage instance for the file.
    image = pilomarimage(name='testlatestfilter',logger=MainLog)
    image.LoadFile(sourcefile)
    print("Running",Parameters.LatestTrackingFilter,"against",sourcefile,"...")
    image.RunFilterScript(Parameters.LatestTrackingFilter)
    image.SaveFile(outputfile)
    print("Result is saved in",outputfile)
    
# ------------------------------------------------------------------------------------------------------

def ReadHistoryFile():
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

def ChooseHistory(selection=None):
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
    temptime = SkyfieldNow() # Use the same timestamp for everything in the list, otherwise repeated objects show inconsistent positions. # Offset supported.
    print (' Line  Last used (UTC)     Name                 Category   Exposure  Current alt / az       RiseSet Other')
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
            if searchgroup == 'solar':
                temptarget = ChooseSolar(searchterm) # Create a solar system target.
            elif searchgroup == 'satellite':
                temptarget = ChooseSatellite(searchterm) # Create a satellite target.
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
                visline = "   " + Deg3dp(alt).rjust(7) + " " + direction + " / " + Deg3dp(az).rjust(8)
                risesetline = temptarget.NextRiseSetHHMM(window=24).ljust(7)[:7] # When is next RISE/SET?
                if temptarget.Visible(time=temptime) == False: 
                    print(textcolor.red(str(count).rjust(6)[:6]),displine, textcolor.red(visline),risesetline,miscline)
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
            CameraInUse.ExposureSeconds = exposureseconds
            MainLog.Log("ChooseHistory: Selected " + lines[i],terminal=False)
            if searchgroup == 'solar':
                obstarget = ChooseSolar(searchterm) # Create a solar system target.
                break
            elif searchgroup == 'satellite':
                obstarget = ChooseSatellite(searchterm) # Create a satellite target.
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

# ------------------------------------------------------------------------------------------------------

def ChooseLastTarget():
    """ Quick resume of previous observation target and settings. """
    MainLog.Log("ChooseLastTarget: Begin",terminal=False)
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
    CameraInUse.ExposureSeconds = exposureseconds
    MainLog.Log("ChooseLastTarget: Selected " + line,terminal=False)
    if searchgroup == 'solar': obstarget = ChooseSolar(searchterm) # Create a solar system target.
    elif searchgroup == 'satellite': obstarget = ChooseSatellite(searchterm) # Create a satellite target.
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

def RiseSetString(otarget):
    """ Return a string listing RISE and SET times of target.
        otarget should be an instance of the target class.
        EARTH CENTRIC objects raise an error here. So they are ignored. """
    try:
        rise, set = otarget.RiseSet()
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

def TargetSelection():
    """ Submenu to allow target selection.
        Several different groups of target are available. 
        Select the group here, then pass control to a specific selection routine. """
    option = None
    TargetOptions = {
        'ResumeLastObservation':      {'label':'Resume last observation',     'value':'LAST'},
        'RepeatEarlierObservations':  {'label':'Repeat earlier observations', 'value':'HISTORY'},
        'SolarSystemObject':          {'label':'Solar system object',         'value':'SOLAR'},
        'HipparcosObject':            {'label':'Hipparcos star catalog',      'value':'HIP'},
        'MessierObject':              {'label':'Messier catalog',             'value':'MESSIER'},
        'NGC':                        {'label':'New General Catalog (NGC)',   'value':'NGC'},
        'Comet':                      {'label':'Comet',                       'value':'COMET'},
        'Meteor':                     {'label':'Meteor shower',               'value':'METEOR'},
        'EarthSatellite':             {'label':'Space stations/satellites',   'value':'SATELLITE'},
        'RADEC':                      {'label':'RA-DEC co-ordinates',         'value':'RADEC'},
        'ALTAZ':                      {'label':'Fixed ALT-AZ point',          'value':'ALTAZ'}
    }
    TargetMenu = optionmenu(TargetOptions,'Select target',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    while option == None:
        obstarget = None
        option, _ = TargetMenu.Prompt() # Ask the user to select an option from the menu.
        # option contains the selected target, or None.
        if option == None: option = 'LAST' # If the user quit the menu without selecting anything, default to the last target.
        if option == "LAST": obstarget = ChooseLastTarget()
        elif option == "HISTORY": obstarget = ChooseHistory()
        elif option == "SOLAR": obstarget = ChooseSolar()
        elif option == "SATELLITE": obstarget = ChooseSatellite()
        elif option == "HIP": obstarget = ChooseHipparcos()
        elif option == "MESSIER": obstarget = ChooseMessier()
        elif option == "RADEC": obstarget = RadecObject()
        elif option == "METEOR": obstarget = ChooseMeteor()
        elif option == "COMET": obstarget = ChooseComet()
        elif option == "ALTAZ": obstarget = AltazObject()
        elif option == "NGC": obstarget = ChooseNGC()
        else: option = None
        if obstarget != None and obstarget.Visible() == False: # Target was chosen, but is not currently visible.
            if option == "SATELLITE" or obstarget.Name in ['iss','css']: # RiseSet calc does not work for these yet.
                pass # Satellites don't matter, they may become visible very soon.
            else: # Other targets probably are not visible for some time, warn the user.
                az,alt = obstarget.AzAltDegrees() # Current az/alt of the target.
                ra,dec = obstarget.RaDecDegrees() # Current RA/DEC of the target.
                rh,rm,rs = AngleToHMS(ra) # Convert RA degrees into Hrs, Mins, Secs
                dd,dm,ds = AngleToDMS(dec) # Convert DEC degrees into Deg, Mins, Secs
                linelist = [obstarget.Name + " is not currently in range (" + AzAltText(az,alt) + ").",
                            "RA: " + str(rh) + "h " + str(rm) + "' " + str(round(rs,3)) + '" ' + 
                            "Dec: " + str(dd) + DegreeSymbol + " " + str(dm) + "' " + str(round(ds,3)) + '"', 
                            RiseSetString(obstarget)]
                textcolor.TextBox(linelist,fg=textcolor.RED,bg=textcolor.BLACK)
                temp = AskYesNo(textcolor.cyan("Do you want to continue ?[y/N]"),False)
                if not temp: option = None # User wants to try a different target, ask the user again.
        if obstarget == None: option = None # No target selected, so ask the user again.
        if option == None: print(textcolor.red("No target selected: Please try again.")) # No success, so ask the user again.

    return obstarget

# ------------------------------------------------------------------------------------------------------

# User MUST select a target to proceed.
Session.Target = None # No target yet.
if ResumeObservation: # Try to resume with last known target.
    Session.Target = ChooseLastTarget()
if Session.Target == None: # Still no valid target. Ask the user.
    print(textcolor.yellow("You must select a target to start the program."))
    Session.Target = TargetSelection()
CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
# Create some other major objects to be included in the SkyChart window.
SunTarget = ChooseSolar(prechosen='sun') 
MoonTarget = ChooseSolar(prechosen='moon')
#ISSTarget = ChooseSatellite(prechosen='ISS (ZARYA)')
#CSSTarget = ChooseSatellite(prechosen='CSS (TIANHE)')
FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and ensures they exist on disc.

# ----------------------------------------------------------
# Menu options
# ----------------------------------------------------------

def HomePosition():
    """ Return the whole mechanism to its home position.
        If the Microcontroller resets at any time, this repeats until successful. """
    print (textcolor.yellow("HomePosition"))
    
    StopMotors() # Clear anything that's still programmed for the motors. 
    Session.SetMotorControlMode('direct') # We will directly control the movement of the microcontroller, no trajectory needs sending.
    MainLog.Log("HomePosition begin",terminal=False)
    loopcounter = 0
    looplimit = 50
    for i in MotorControls: # Handle each motor in turn.
        MainLog.Log("HomePosition: Homing ", i.MotorName, 'motor.',terminal=False)
        i.MonitorMove = True # Display movement progress on the terminal.
        while i.CompareAngles(i.CurrentAngle,i.RestAngle) == False: # Repeat until the motor is in position.
            MainLog.Log("HomePosition:", i.MotorName, "motor from", Deg3dp(i.CurrentAngle) + DegreeSymbol, "to home", Deg3dp(i.RestAngle) + DegreeSymbol,terminal=True)
            i.GoToAngle(i.RestAngle)
            MainLog.Log("HomePosition:", i.MotorName, "motor parked at", Deg3dp(i.CurrentAngle) + DegreeSymbol + ".",terminal=False)
            loopcounter += 1
            if loopcounter >= looplimit: 
                MainLog.Log("HomePosition:", i.MotorName, "After", looplimit, "attempts, motor still not homed. Abandoning the move at", Deg3dp(i.CurrentAngle) + DegreeSymbol, ".",level='error')
                break
        i.MonitorMove = False # Suppress movement progress on the terminal.
    print (textcolor.yellow("Done.") + textcolor.clearlineforward())
    MainLog.Log("HomePosition end",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def SetMotorAngle(motor_name=None):
    """ Move motor to specific angle. """
    print (textcolor.yellow("SetMotorAngle " + str(motor_name)+ "."))
    print("(The motor will physically move.)")
    c = ""
    for i in MotorControls: # Scan all the motors available.
        if i.MotorName == motor_name: # Select the correct motor.
            while c.lower() != "x": # Loop until user quits.
                print (i.MotorName,"is currently at",Deg3dp(i.CurrentAngle) + DegreeSymbol)
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
                    i.MonitorMove = True
                    i.GoToAngle(v) # Set the new target position.
                    i.MonitorMove = False
                    continue # Restart loop.
                print ("'" + c + "' is not recognised. Try again.")
            print (i.MotorName,"is currently at",Deg3dp(i.CurrentAngle) + DegreeSymbol)
    StopMotors() # Reset motor condition to prevent further movement.
    MainLog.Log("SetMotorAngle " + motor_name + " Completed.",terminal=False)
    print (textcolor.yellow("Done.") + textcolor.clearlineforward())
    return True

# ------------------------------------------------------------------------------------------------------

def AzimuthAngle(): # For menu
    SetMotorAngle('azimuth')

# ------------------------------------------------------------------------------------------------------

def AltitudeAngle(): # For menu
    SetMotorAngle('altitude')

# ------------------------------------------------------------------------------------------------------

def TunePosition(motor_name=None):
    """ Finetune the position of the mechanism. This version asks the user to enter the adjustment parameter.
        You can move a motor with this function, but its virtual position will not be updated.
        It physically moves the motor, but registers the position as it was at the START of the move.
        Use this to finetune the position if the telescope hasn't been placed properly, or the positioning is wrong.
        Scenarios are when you are initially setting up the telescope and finetuning the physical alignment to match the theoretical one.
        Or if the motor has slipped during an observation and you want to correct for that. 
        The optical drift tracking mechanism uses this function to keep the target centered too. """
    MainLog.Log("TunePosition:",motor_name,"begin",terminal=False)
    print (textcolor.yellow("TunePosition " + str(motor_name)+ "."))
    print (textcolor.white("This will move the motor to match where the computer thinks it is pointing.",invert=True))
    print (textcolor.white("This will finetune the physical position of the motor, but leave its logical position unchanged."))
    print (textcolor.white("You are making the motor physically point to where the computer already THINKS it is pointing."))
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
    MainLog.Log("TunePosition",motor_name,"complete.",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def TunePositionAzimuth(): # For menu call.
    TunePosition('azimuth')

# ------------------------------------------------------------------------------------------------------

def TunePositionAltitude(): # For menu call
    TunePosition('altitude')

# ------------------------------------------------------------------------------------------------------

def SetExposureTime(p):
    print (textcolor.yellow("SetExposureTime (Currently " + str(p)+ " seconds)."))
    MainLog.Log("To minimise blurring the camera needs to move every ",round(CameraInUse.SecondsPerPixel,3),"seconds.",terminal=False)
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

# ------------------------------------------------------------------------------------------------------

def MenuSetExposureTime(): # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        CameraInUse.ExposureSeconds = SetExposureTime(CameraInUse.ExposureSeconds)
        FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
        DocumentSession()
        DriftTracker.Reset()

# ------------------------------------------------------------------------------------------------------

def SetBatchSize(p):
    print (textcolor.yellow("SetBatchSize (Currently " + str(p)+ " frames)."))
    print ("This is the number of frames to capture when taking LIGHT images.")
    print ("These are the actual observation images.")
    print ("This does not change the number of CONTROL images taken for FLAT, DARK or BIAS images.")
    v = input(textcolor.cyan("Light images batch size (or RETURN) : ")) # Python3 
    if len(v) > 0:
        v = TextToInt(v)
        if v != None:
            p = v
    MainLog.Log("SetBatchSize: Value=" + str(p),terminal=False)
    return p

# ------------------------------------------------------------------------------------------------------

def SetControlBatchSize(p): 
    print (textcolor.yellow("SetControlBatchSize (Currently " + str(p)+ " frames)."))
    print ("This is the number of frames to capture when taking FLAT, DARK & BIAS images.")
    print ("This does not change the number of LIGHT (observation) images taken.")
    print ("HINT: A good number is around 15-20 images.")
    v = input(textcolor.cyan("Control batch size (or RETURN) : ")) # Python3 
    if len(v) > 0:
        v = TextToInt(v)
        if v != None:
            p = v
    MainLog.Log("SetControlBatchSize: Value=" + str(p),terminal=False)
    return p

# ------------------------------------------------------------------------------------------------------

def MarkupPreview(drift_pixels_x=None,drift_pixels_y=None,astrotime=None):
    """ Take the last image registered in CameraInUse.Image and mark up various alignment indicators and labels.
        OpenCV version of MarkupPreview. 
        astrotime = You can specify the date/time that the preview is calculated for.
        applydistortion = The image can be artificially distorted to try to match an actual photo more closely. """
    CamLog.Log("MarkupPreview: Start(",drift_pixels_x,drift_pixels_y,astrotime,")",terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime != None: # Calculate for a specific timestamp.
        t = astrotime
    else: 
        t = SkyfieldNow() # Current timestamp in 'astro' time. If there's a delay then there may be some mismatch in placing objects. # Offset supported.
    CamLog.Log("MarkupPreview: MarkupTime:",Ts2Datetime(t),terminal=False)
    CamLog.Log("MarkupPreview: CameraInUse.CaptureStart:",CameraInUse.CaptureStart,terminal=False)
    CamLog.Log("MarkupPreview: CameraInUse.CaptureEnd:",CameraInUse.CaptureEnd,terminal=False)
    # The time should be the time of the actual photo! If several seconds have passed, then things will already have drifted!
    if Parameters.UseLiveLocation: # Use the live target location rather than the last reported camera position for image processing.
        CentreAz, CentreAlt = Session.Target.AzAltDegrees() # What is the alt/az location of the centre of the image?
    else: # Use the last reported camera position. Deprecated.
        CentreAlt, CentreAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
    CentreRa, CentreDec = Session.Target.RaDecDegrees() # Calculations for target from observer's location. Returns decimal degree values. *Q* Does this ever vary with time?
    CamLog.Log("MarkupPreview: Centre coordinates: alt/az:",CentreAlt,"/",CentreAz,"ra/dec:",CentreRa,CentreDec,terminal=False)
    # load the image
    NewImageBuffer = pilomarimage(name='preview',logger=CamLog)
    NewImageBuffer.LoadBuffer(CameraInUse.Image.ImageBuffer) # Take it directly from memory
    NewImageBuffer.ChangeType('bgr') # Make sure it's a colour image.
    width = NewImageBuffer.GetWidth()
    height = NewImageBuffer.GetHeight()
    centrex = int(width / 2)
    centrey = int(height / 2)
    folder = FolderList.get('preview')
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
        compasslabels = {0:'NORTH',45:'NORTH-EAST',90:'EAST',135:'SOUTH-EAST',180:'SOUTH',225:'SOUTH-WEST',270:'WEST',315:'NORTH-WEST'}
        for iAlt in range (-10,90,linestep):
            for iAz in range(0,360,linestep):
                PlotAlt, PlotAz = RelativeAltAz(iAlt,iAz,CentreAlt,CentreAz) # Plot point relative to centre of image.
                if abs(PlotAz) > Parameters.TargetInclusionRadius: continue # Outside the image, skip it.
                if abs(PlotAlt) > Parameters.TargetInclusionRadius: continue # Outside the image, skip it.
                PlotAlt2, PlotAz2 = RelativeAltAz(iAlt,iAz + linestep,CentreAlt,CentreAz) # Plot point relative to centre of image + 1 unit of Azimuth.
                PlotAlt3, PlotAz3 = RelativeAltAz(iAlt + linestep,iAz,CentreAlt,CentreAz) # Plot point relative to centre of image + 1 unit of Altitude.
                TempStarX, TempStarY = PlotRelativeAltAz(PlotAlt,PlotAz,height,width)
                TempStarX2, TempStarY2 = PlotRelativeAltAz(PlotAlt2,PlotAz2,height,width) # From x,y
                TempStarX3, TempStarY3 = PlotRelativeAltAz(PlotAlt3,PlotAz3,height,width) # To x,y
                if iAlt == 0: h_thick, h_color = 5, (0,0,127) # Horizon
                elif iAlt % 10 == 0: h_thick, h_color = 2, (90,90,90) # 10 degree line
                elif iAlt % 5 == 0: h_thick, h_color = 2, (60,60,60) # 5 degree line
                else: h_thick, h_color = 1, (40,40,40) # Default 1 degree line
                if iAz % 90 == 0: v_thick, v_color = 3, (100,100,100) # 90 degree line (N,S,E,W)
                elif iAz % 10 == 0: v_thick, v_color = 2, (90,90,90) # 10 degree line
                elif iAz % 5 == 0: v_thick, v_color = 2, (60,60,60) # 5 degree line
                else: v_thick, v_color = 1, (40,40,40) # Default 1 degree line
                # Tint sectors which are below the horizon deep red.
                if iAlt < 0:
                    polygon = [(TempStarX, TempStarY), (TempStarX2, TempStarY2), (TempStarX2,TempStarY3), (TempStarX,TempStarY3)]
                    NewImageBuffer.FillPolygon(polygon, color=(0,0,30))
                # Plot grid lines.
                NewImageBuffer.DrawLine((TempStarX,TempStarY),(TempStarX2,TempStarY2),color=h_color,thickness=h_thick) # DIMGREY Link to neighbouring grid intersections. # Horizontal part of grid (B-C)
                NewImageBuffer.DrawLine((TempStarX,TempStarY),(TempStarX3,TempStarY3),color=v_color,thickness=v_thick) # DIMGREY Link to neighbouring grid intersections. # Vertical part of grid (A-B)
                if iAlt % 5 == iAz % 5 == 0: # Show co-ordinates at major grid crossing points.
                    text = str(iAlt) + "," + str(iAz)
                    NewImageBuffer.AddText(text,TempStarX,TempStarY - 10,color=(127,127,127))
                # Label compass points. Consider any vertical (azimuth) lines which cross the bottom of the screen. Mark those which represent compass points.
                if TempStarY > height and TempStarY3 <= height: # Place the label on the line crosses the bottom of the image.
                    label = compasslabels.get(iAz,'') # Does this azimuth line lie on a compass point?
                    if label != '': # If it's a recognised compass point, add a label.
                        y = int(height - 200)
                        x = int(Interpolate(inp1=TempStarY,res1=TempStarX,inp2=TempStarY3,res2=TempStarX3,inp3=y)) # Where does line cross bottom of the screen?
                        NewImageBuffer.AddText(label,x,y,color=BGRBlack,bgcolor=BGRGreen,size=2,thickness=2,border=10,vjust='c',hjust='c')

    if True: # Parameters.MarkupShowCrosshairs: # Target cross hairs
        CamLog.Log("MarkupPreview: ShowCrosshairs",terminal=False)
        # Draw cross hairs. Gap in the centre so that target is still visible.
        NewImageBuffer.SetPenColor(BGRYellow)
        NewImageBuffer.DrawLine((int(width/2),     0),            (int(width/2),        int(height/2 - 20)))
        NewImageBuffer.DrawLine((int(width/2),     height),       (int(width/2),        int(height/2 + 20)))
        NewImageBuffer.DrawLine((0,                int(height/2)),(int(width/2 - 20),   int(height/2))     )
        NewImageBuffer.DrawLine((int(width/2) + 20,int(height/2)),(width,int(height/2))                    )

    if True: # Parameters.MarkupShowDegreeScale: # Mark DEGREE scale. This is degrees movement of the camera, NOT degrees in the sky!
        CamLog.Log("MarkupPreview: ShowDegreeScale",terminal=False)
        NewImageBuffer.SetPenColor(BGRYellow)
        # Calibration - Azimuth
        for i in range(-10,11):
            xpos = int(width/2) + (i * CameraInUse.PixelsPerFovDegreeWidth) # 1 degree markers
            ypos = int(height/2)
            text = str(i) + "deg" # DegreeSymbol
            if i > 0: text = "+" + text
            NewImageBuffer.DrawLine((xpos,ypos - 100),(xpos,ypos))
            NewImageBuffer.AddText(text,xpos,ypos - 100,hjust='c',vjust='t') 
        # Calibration - Altitude
        for i in range(-10,11):
            xpos = int(width/2) 
            ypos = int(height/2) + (i * CameraInUse.PixelsPerFovDegreeHeight) # 1 degree markers
            NewImageBuffer.DrawLine((xpos - 100,ypos),(xpos,ypos))
            text = str(i * -1) + "deg" # DegreeSymbol - Invert scale because image Y runs the wrong direction.
            if i < 0: text = "+" + text
            NewImageBuffer.AddText(text,xpos - 100,ypos,vjust='c',hjust='r') 

    if True: # Parameters.MarkupShowFullStepScale: # Mark FULL STEP scale.
        # Calibration - Azimuth
        NewImageBuffer.SetPenColor(BGRCyan)
        c = 0
        for i in range(-1000,1001,200): # Major tick marks only.
            c = 1 - c
            xpos = int((width/2) + (i * az_pixels_per_fullstep))
            ypos = int(height/2)
            NewImageBuffer.DrawLine((xpos,ypos),(xpos,ypos + 100),thickness=3)
            text = str(i) + "Steps"
            if i > 0: text = "+" + text
            NewImageBuffer.AddText(text,xpos,ypos + 110 + (c * 25),size=1.0,hjust='c',vjust='b') # Offset alternate markings to keep legible.
        # Calibration - Altitude
        for i in range(-1000,1001,200): # Major tick marks only
            xpos = int(width/2)
            ypos = int((height/2) + (i * alt_pixels_per_fullstep))
            NewImageBuffer.DrawLine((xpos,ypos),(xpos + 100,ypos),thickness=3)
            text = str(i * -1) + "Steps"
            if i < 0: text = "+" + text
            NewImageBuffer.AddText(text,xpos + 110,ypos,vjust='c')
        # Mark precision circle on centre. Once you're inside this circle, there's little point in finetuning further on this scale.
        if az_pixels_per_fullstep > 5 or alt_pixels_per_fullstep > 5:
            # Only bother showing the precision circle IF it is large enough to be useful. 
            # If the gearing is very fine, then there's no real purpose to showing the precision circle, it will be too small to see.
            xpos = int(width/2)
            ypos = int(height/2)
            NewImageBuffer.DrawCircle(xpos,ypos,int(az_pixels_per_fullstep),color=BGRGold,thickness=3)
            NewImageBuffer.DrawCircle(xpos,ypos,int(az_pixels_per_fullstep),color=BGRBlack)

    if True: # Draw angular scale for reference.
        ScaleList = [['1deg',    1.0,0.0 ,0.0],
                     ['30arcmin',0.0,30.0,0.0],
                     ['10arcmin',0.0,10.0,0.0],
                     ['1arcmin', 0.0,1.0 ,0.0],
                     ['30arcsec',0.0,0.0 ,30.0],
                     ['10arcsec', 0.0,0.0,10.0]]
        NewImageBuffer.SetPenColor(BGRWhite)
        x = 200
        y = int(height / 2) + 200
        NewImageBuffer.AddEdgeText("Angular scale",x,y,size=0.5,edgecolor=BGRBlack)
        for i,scale in enumerate(ScaleList):
            label = scale[0]
            d = float(scale[1]) + (scale[2] / 60) + (scale[3] / (60 ** 2)) # Convert DMS into float degrees.
            p = int(d * CameraInUse.PixelsPerFovDegreeWidth)
            if p > width - 300: # Line is too long to be useful.
                continue
            y += 20
            NewImageBuffer.AddEdgeText(label,x,y,size=0.5,hjust='r',vjust='c',edgecolor=BGRBlack)
            NewImageBuffer.DrawLine((x + 10,y),(x + 10 + p,y),thickness=3)
            NewImageBuffer.DrawLine((x + 10,y - 10),(x + 10,y + 10),thickness=1)
            NewImageBuffer.DrawLine((x + 10 + p,y - 10),(x + 10 + p,y + 10),thickness=1)

    if True: # Parameters.MarkupShowMessier: # Mark neighbouring Messier objects ....
        NewImageBuffer.SetPenColor(BGRGreen)
        # Find that alt/az locations of all the objects.
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            TempRAH = TempStarParms['ra'][0] # Right Ascension HOURS
            TempRAM = TempStarParms['ra'][1] # Right Ascension MINUTES
            TempRAS = TempStarParms['ra'][2] # Right Ascension SECONDS
            TempStarRA = TempStarParms['radeg']
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempDED = TempStarParms['dec'][0] # Declination DEGREES
            TempDEM = TempStarParms['dec'][1] # Declination MINUTES
            TempDES = TempStarParms['dec'][2] # Declination SECONDS
            TempStarDec = TempStarParms['decdeg']
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            TempStar = Star(ra_hours=(TempRAH, TempRAM, TempRAS), dec_degrees=(TempDED, TempDEM, TempDES)) # Create star object from RADEC co-ordinates.
            TempStarType = TempStarParms['type']
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Width given in arcminutes.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation="",description="",magnitude=TempStarParms['magnitude'])
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            if TempStarAz < 0: # Below horizon, don't mark it up.
                continue # Skip to next object.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempTextX = TempStarX + TempStarWidth + 5 # Put Messier labels on the RIGHT of the object so they don't clash with NGC labels for the same thing.
            NewImageBuffer.DrawEllipse(TempStarX,TempStarY,int(TempStarWidth),int(TempStarHeight),0,0,360)
            if Parameters.MarkupShowLabels:
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                NewImageBuffer.AddText(text,TempTextX,TempStarY + lineheight,size=0.5)
                text = "RA:" + TempStarParms['ralabel'] + " Dec:" + TempStarParms['declabel']
                NewImageBuffer.AddText(text,TempTextX,NewImageBuffer.NextTextY,size=0.5)
                if TempStarName != None:
                    NewImageBuffer.AddText(TempStarName.upper(),TempTextX,TempStarY -20,size=1)

    if True: # Mark neighbouring NGC items ...
        # Find the alt/az locations of all the objects.
        # NGC catalog is large, eliminate as much as possible first.
        CamLog.Log("MarkupPreview: NGCItems: CentreRa",CentreRa,DegreeSymbol,"CentreDec",CentreDec,DegreeSymbol,terminal=False)
        CamLog.Log("MarkupPreview: NGCItems: Start:",len(NGC_DF),"records.",terminal=False)
        boolseries = NGC_DF['radeg'].between(MinRADeg, MaxRADeg, inclusive='both') # Create filter for items within RA range.
        tempdf = NGC_DF[boolseries] # Apply filter.
        CamLog.Log("MarkupPreview: NGCItems: RA Filtered:",MinRADeg,DegreeSymbol,MaxRADeg,DegreeSymbol,". Leaves",len(tempdf),"records.",terminal=False)
        boolseries = tempdf['decdeg'].between(MinDecDeg, MaxDecDeg, inclusive='both') # Create filter for items with Dec range.
        tempdf = tempdf[boolseries] # Apply filter.
        CamLog.Log("MarkupPreview: NGCItems: Dec Filtered:",MinDecDeg,DegreeSymbol,MaxDecDeg,DegreeSymbol,". Leaves",len(tempdf),"records.",terminal=False)
        NewImageBuffer.SetPenColor(BGRLightBlue)
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarName = TempStarParms['name']
            try: # Earlier versions of the data file may not have this column.
                TempStarName2 = TempStarParms['knownas']
            except:
                TempStarName2 = '' # Field not available in this data set.
            try: # Earlier versions of the data file may not have this column.
                NGCType = TempStarParms['typelabel']
            except:
                NGCType = TempStarParms['type']
            TempStar = Star(ra_hours=(TempStarParms['rah'], TempStarParms['ram'], TempStarParms['ras']), 
                            dec_degrees=(TempStarParms['ded'], TempStarParms['dem'], TempStarParms['des'])) # Create star object from RADEC co-ordinates.
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from arcseconds to degrees & radius.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            if TempStarWidth < 1 and TempStarHeight < 1: continue # Too small to display.
            temptarget = target(TempStar,name=TempStarName,objecttype='ngc',constellation="",description="",magnitude=TempStarParms['magnitude'])
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            if TempStarAz < 0: # Below horizon, don't mark it up.
                continue # Skip to next object.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            #TempTextX = TempStarX - TempStarWidth - 5 # Put NGC labels on the LEFT of the object so they don't clash with any matching Messier label for the same thing.
            NewImageBuffer.DrawEllipse(TempStarX,TempStarY, int(TempStarWidth),int(TempStarHeight), angle=0, startAngle=0, endAngle=360)
            CamLog.Log("MarkupPreview: NGCItems: Processing entry",i,TempStarName,TempStarName2,";",TempStarWidth,"*",TempStarHeight,";",TempStarX,",",TempStarY,terminal=False)
            if Parameters.MarkupShowLabels:
                TempTextX = TempStarX - TempStarWidth - 5 # Put NGC labels on the LEFT of the object so they don't clash with any matching Messier label for the same thing.
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                NewImageBuffer.AddText(text,TempTextX,TempStarY + lineheight,size=0.5,hjust='r')
                text = "RA:" + TempStarParms['ralabel'] + " Dec:" + TempStarParms['declabel']
                NewImageBuffer.AddText(text,TempTextX,NewImageBuffer.NextTextY,size=0.5,hjust='r')
                if NGCType != None: # Describe the object type.
                    NewImageBuffer.AddText(NGCType.title(),TempTextX,NewImageBuffer.NextTextY,size=0.5,hjust='r')
                if TempStarName != None: # Name - ie NGCxxx
                    NewImageBuffer.AddText(TempStarName.upper(),TempTextX,TempStarY -30,size=1,hjust='r')
                if TempStarName2 != None: # Known as - ie Whirlpool Galaxy
                    NewImageBuffer.AddText(TempStarName2.title(),TempTextX,NewImageBuffer.NextTextY,size=1,hjust='r')
        CamLog.Log("MarkupPreview: NGCItems: Plot NGC objects end. (",len(tempdf),"/",len(NGC_DF),"objects selected)",terminal=False)
    
    
    hsat = HomeSite.at(t)
    if True: # Parameters.MarkupShowStars: # Mark neighbouring stars.
        CamLog.Log("MarkupPreview: ShowStars",terminal=False)
        NewImageBuffer.AvoidTextCollisions = Parameters.MarkupAvoidCollisions # Do we allow star labels to overlap?
        # Mark neighbouring stars on the picture too. This will help with alignment.
        # Select a subset of the Hipparcos catalog which is within 10Deg of the target (=centre of image)
        CamLog.Log("MarkupPreview: SelectStars start",terminal=False)
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        NeighbouringStarCount = len(NeighbouringStars)
        #inbounds_idx = LocalStars.ColumnIndex('inbounds') # Which dataframe column stores the 'inbounds' counter?
        CamLog.Log("MarkupPreview: NeighbouringStars contains",NeighbouringStarCount,"entries.",terminal=False)
        NewImageBuffer.SetPenColor(BGRPaleGreen)
        # Now convert this list of ra/dec locations into alt/az positions for plotting on the preview image.
        PlottedStarCount = 0 # How many stars have been plotted? We don't want to swamp the display.
        for i in range(NeighbouringStarCount):
            if i % 400 == 0:
                CamLog.Log("MarkupPreview: ShowStars. Processing star",i,terminal=False)
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe, probably makes a COPY, not a pointer to the original row.
            TempStar = Star.from_dataframe(TempStarRec) # Convert the Hipparcos entry into a Skyfield STAR object. *Q* Can we use TempStarRec here?
            TempStarAlt, TempStarAz, _ = hsat.observe(TempStar).apparent().altaz() # Get the azimuth and altitude position of the star in the sky.
            # Calculate the location in the preview image.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt.degrees,TempStarAz.degrees,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            if NewImageBuffer.OutOfBounds(TempStarX,TempStarY): continue # This star is off the edge of the image, skip it.
            # We're going to plot this one.
            PlottedStarCount += 1
            TempStarWidth = int(TempStarRec['markupradius'])
            NewImageBuffer.DrawCircle(TempStarX,TempStarY,TempStarWidth,thickness=3) # cyan # circle where the star is.
            labelx = TempStarX + TempStarWidth + 5 # X location of labels.
            if True: # Parameters.MarkupShowNames:
                TempStarName = TempStarRec['starname']
                try:
                    TempStarConstellation = TempStarRec['constellation'].title() # Capitalise 1st letter of each word.
                except:
                    TempStarConstellation = ''
                if TempStarConstellation != '' and TempStarConstellation != None:
                    TempStarName += " (" + TempStarConstellation + ")"
                NewImageBuffer.AddText(TempStarRec['label'],labelx,TempStarY -20) # Hipparcos ID
                if len(TempStarName) > 0: # Add star name.
                    NewImageBuffer.AddText(TempStarName.title(),labelx,NewImageBuffer.NextTextY,thickness=2,size=1) 
            if Parameters.MarkupShowLabels: # Show position labels. Alt/Az and Ra/Dec
                text = AzAltText(TempStarAz.degrees,TempStarAlt.degrees,'deg')
                NewImageBuffer.AddText(text,labelx,NewImageBuffer.NextTextY,size=0.5) 
                text = "RA:" + TempStarRec['ralabel'] + " Dec:" + TempStarRec['declabel']
                NewImageBuffer.AddText(text,labelx,NewImageBuffer.NextTextY,size=0.5) 
            if PlottedStarCount >= Parameters.MarkupStarLabelLimit: # We're plotted enough, don't swamp the image.
                CamLog.Log("MarkupPreview: ShowStars: Plotted maximum",PlottedStarCount,"star labels.",terminal=False)
                break
        NewImageBuffer.AvoidTextCollisions = False # Turn off the label collision protection.

    if True: #Parameters.MarkupConstellations: # Mark constellation patterns... # Workaround for post skyfield 1.39. Fault not fully understood yet.
        CamLog.Log("MarkupPreview: ShowConstellations POST OCT.2023 version. Post Skyfield 1.39 etc.",terminal=False)
        rad = 10 # 10 pixel gap between line and star.
        cclist = {} # We place the name of the constellation in the middle of the visible stars. This list builds up where those locations are.
        NewImageBuffer.SetPenColor(BGRRed)
        ConstellationsDf = ConstellationStars.Get(CentreRa,CentreDec)
        CamLog.Log("MarkupPreview: ShowConstellations: Columns available:",list(ConstellationsDf.columns),terminal=False)
        linkcount = 0
        successcount = 0
        for entryfrom, entryto, entryname in ConstellationLinks:
            linkcount += 1
            if int(entryfrom) in ConstellationsDf.index and int(entryto) in ConstellationsDf.index: 
                CamLog.Log("MarkupPreview: ShowConstellations: from",int(entryfrom),"to",int(entryto),terminal=False)
                FromRec = ConstellationsDf.loc[int(entryfrom)] # See how many records are returned. Expect 1: 15.10.2023
                try:
                    rah, ram, ras = AngleToHMS(FromRec['ra_degrees'])
                except Exception as e:
                    CamLog.Log("AngleToHMS(",FromRec['ra_degrees'],")=",rah,ram,ras,"failed. Skipping FromStar",entryfrom,terminal=False)
                    CamLog.Log("AngleToHMS(",FromRec['ra_degrees'],") Error:",e,terminal=False)
                    continue # Don't process this star any further.
                try:
                    ded, dem, des = AngleToDMS(FromRec['dec_degrees'])
                except Exception as e:
                    CamLog.Log("AngleToHMS(",FromRec['dec_degrees'],")=",ded,dem,des,"failed. Skipping FromStar",entryfrom,terminal=False)
                    CamLog.Log("AngleToHMS(",FromRec['dec_degrees'],") Error:",e,terminal=False)
                    continue # Don't process this star any further.
                try:
                    FromStar = Star(ra_hours=(rah, ram, ras), dec_degrees=(ded, dem, des))
                except Exception as e:
                    CamLog.Log("Skyfield Star construction of FromRec hip",entryfrom,"failed. Skipping.",terminal=False)
                    CamLog.Log("Star construction of",entryfrom,"Error:",e,terminal=False)
                    continue # Don't process this star any further.
                ToRec = ConstellationsDf.loc[int(entryto)] # See how many records are returned. Expect 1: 15.10.2023
                try:
                    rah, ram, ras = AngleToHMS(ToRec['ra_degrees'])
                except Exception as e:
                    CamLog.Log("AngleToHMS(",ToRec['ra_degrees'],")=",rah,ram,ras,"failed. Skipping ToStar",entryto,terminal=False)
                    CamLog.Log("AngleToHMS(",ToRec['ra_degrees'],") Error:",e,terminal=False)
                    continue # Don't process this star any further.
                try:
                    ded, dem, des = AngleToDMS(ToRec['dec_degrees'])
                except Exception as e:
                    CamLog.Log("AngleToHMS(",ToRec['dec_degrees'],")=",ded,dem,des,"failed. Skipping ToStar",entryto,terminal=False)
                    CamLog.Log("AngleToHMS(",ToRec['dec_degrees'],") Error:",e,terminal=False)
                    continue # Don't process this star any further.
                try:
                    ToStar = Star(ra_hours=(rah, ram, ras), dec_degrees=(ded, dem, des))
                except Exception as e:
                    CamLog.Log("Skyfield Star construction of ToRec hip",entryto,"failed. Skipping.",terminal=False)
                    CamLog.Log("Star construction of",entryto,"Error:",e,terminal=False)
                    continue # Don't process this star any further.
                successcount += 1
                FromAlt, FromAz, _ = hsat.observe(FromStar).apparent().altaz() # Get the azimuth and altitude position of the star in the sky.
                PlotFromAlt, PlotFromAz = RelativeAltAz(FromAlt.degrees,FromAz.degrees,CentreAlt,CentreAz)
                fromx, fromy = PlotRelativeAltAz(PlotFromAlt,PlotFromAz,height,width)
                ToAlt, ToAz, _ = hsat.observe(ToStar).apparent().altaz() # Get the azimuth and altitude position of the star in the sky.
                PlotToAlt, PlotToAz = RelativeAltAz(ToAlt.degrees,ToAz.degrees,CentreAlt,CentreAz)
                tox, toy = PlotRelativeAltAz(PlotToAlt,PlotToAz,height,width)
                fromx,fromy,tox,toy = NewImageBuffer.TrimLine(fromx,fromy,tox,toy,trimpixels=rad) # Shorten the ends of the constellation line by a few pixels.
                deltax = tox - fromx # Line size
                deltay = toy - fromy
                # Only draw the line between stars if they are sufficiently separated on the image. (DIV-BY-ZERO error if they are the same pixel).
                if abs(deltax) > (rad * 2) or abs(deltay) > (rad * 2):
                    hyp = math.sqrt(deltax**2 + deltay**2)
                    x1 = int(fromx + (deltax * rad / hyp)) # End points of line 'rad' pixels away from actual stars.
                    x2 = int(tox - (deltax * rad / hyp))
                    y1 = int(fromy + (deltay * rad / hyp))
                    y2 = int(toy - (deltay * rad / hyp))
                    NewImageBuffer.DrawLine((x1,y1),(x2,y2))
                else:
                    CamLog.Log("MarkupPreview: ShowConstellations: Too close to plot",entryfrom,"(",x1,",",y1," ) to",entryto,"(",x2,",",y2," ).",terminal=False)
                # Add star locations to cclist to help place the constellation name sensibly.
                if NewImageBuffer.InBounds(fromx,fromy) or NewImageBuffer.InBounds(tox,toy):
                    ccentry = cclist.get(entryname,{}) # Get current locations for this constellation name.
                    ccount = ccentry.get('count',0) # Extract number of stars plotted so far for this constellation.
                    cctotx = ccentry.get('totalx',0) # Extract total 'x' positions of all stars plotted for this constellation.
                    cctoty = ccentry.get('totaly',0) # Extract total 'y' positions of all stars plotted for this constellation.
                    cctotx += fromx + tox # Add this star pair.
                    cctoty += fromy + toy
                    ccount += 2 # We've added 2 stars to the list.
                    ccentry['count'] = ccount # Update the count and totals.
                    ccentry['totalx'] = cctotx
                    ccentry['totaly'] = cctoty
                    cclist[entryname] = ccentry # Store the entry back in the list of constellation names.
        CamLog.Log("MarkupPreview: Constellation links: Attempted:", linkcount, "Succeeded:", successcount,terminal=False)
        # Now place constellation labels.
        for ccname,ccentry in cclist.items():
            x = ccentry['totalx'] / ccentry['count'] # Average x
            y = ccentry['totaly'] / ccentry['count'] # Average y
            x = max(x,0)
            x = min(x,width)
            y = max(y,0)
            y = min(y,height)
            hjust = 'c'
            if x < width / 4: hjust = 'l'
            elif x > 3 * width / 4: hjust = 'r'
            if y < 20: y = 20
            elif y > height - 20: y = height - 20
            NewImageBuffer.AddText(ccname.title(),int(x),int(y),size=3,hjust=hjust)

    if True: # Parameters.MarkupShowPlanets: # Mark neighbouring planets ....
        CamLog.Log("MarkupPreview: ShowPlanets",terminal=False)
        NewImageBuffer.SetPenColor(BGRGold)
        # Find the alt/az locations of all the planets.
        for TempStarName in ['sun','mercury barycenter','venus barycenter','moon','mars barycenter','jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']:
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = target(TempStar,name=TempStarName,objecttype="planet",description=TempStarDescription,magnitude=0.0)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t) 
            TempStarRA, TempStarDec = temptarget.RaDecDegrees(time=t) 
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempStarWidth = 40 # Planets are by default 40 pixel radius circles.
            if TempStarName == 'moon':
                TempStarWidth = int(ConvertArcsecondsToPixels((0.5286 / 2) * 3600)) # Moon is approx 0.26 degrees angular radius.
            NewImageBuffer.DrawCircle(TempStarX,TempStarY,TempStarWidth,thickness=3) # cyan # circle where the planet is.
            if Parameters.MarkupShowLabels:
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                NewImageBuffer.AddText(text,TempStarX + TempStarWidth + 5,TempStarY + 40)
                text = RaDecText(TempStarRA,TempStarDec,'deg')
                # text = "RA:" + str(TempStarRA) + " Dec:" + str(TempStarDec)
                NewImageBuffer.AddText(text,TempStarX + TempStarWidth + 5,NewImageBuffer.NextTextY)
            if TempStarName != None:
                NewImageBuffer.AddText(TempStarName.split()[0].title(),TempStarX + TempStarWidth + 5,TempStarY -20) 
        
    if True: # Parameters.MarkupShowRegistration: # Reference marks on preview image...
        CamLog.Log("MarkupPreview: ShowRegistration",terminal=False)
        NewImageBuffer.SetPenColor(BGRRed)
        NewImageBuffer.DrawLine((10,10),(100,10),thickness=3) # Red
        NewImageBuffer.DrawLine((10,10),(10,100),thickness=3) # Red
        text = "(10,10)"
        NewImageBuffer.AddText(text,40, 60,color=BGRRed) # red
        
    if True: # Parameters.MarkupShowDrift: # Mark last measured DRIFT indicator.
        CamLog.Log("MarkupPreview: ShowDrift:",drift_pixels_x,",",drift_pixels_y,terminal=False)
        if drift_pixels_x != None and drift_pixels_y != None:
            text = "Drift: " + str(drift_pixels_x) + "," + str(drift_pixels_y) + " pixels"
            NewImageBuffer.DrawEdgeLine((int(width/2),int(height/2)),(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y)),color=BGRRed,edgecolor=BGRBlack) # Black outline showing last measured drift.
            NewImageBuffer.DrawCircle(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y),10,color=BGRRed) # Black outline showing last measured drift.
            NewImageBuffer.AddEdgeText(text,int(width/2) + int(drift_pixels_x) + 10,int(height/2) + int(drift_pixels_y) + 10,color=BGRRed,edgecolor=BGRBlack,thickness=2,edgethickness=2) # Red line
        else:
            NewImageBuffer.AddEdgeText("NO DRIFT AVAILABLE",int(width/2) + 150,int(height/2) + 150,color=BGRRed,edgecolor=BGRBlack,thickness=2,edgethickness=2) # Red line

    if True: # Parameters.MarkupShowCurrentPosition: # Show current position. 
        CamLog.Log("MarkupPreview: CurrentPosition",terminal=False)
        cRa ,cDec = Session.Target.RaDecHours() # Calculations for target from observer's location. Returns HMS and Degree values.
        # Timestamp bottom center.
        xpos = int(width / 2)
        ypos = int(height - 70)
        text = str(CameraInUse.LastImageDateTime)
        NewImageBuffer.AddText(text,xpos,ypos,size=2.0,color=BGRWhite,bgcolor=BGRBlack,hjust='c')
        # Filename in bottom left corner.
        xpos = int(10)
        ypos = int(height - 10)
        text = "File: " + filename
        NewImageBuffer.AddText(text,xpos,ypos,color=BGRWhite,bgcolor=BGRBlack)
        # Program ID in bottom right corner.
        xpos = int(width - 10)
        ypos = int(height - 10)
        NewImageBuffer.AddText(ProgramTitle + " " + VERSION,xpos,ypos,color=BGRWhite,bgcolor=BGRBlack,hjust='r')
        # Camera options in top left corner.
        xpos = int(200)
        ypos = int(40)
        text = "Camera options: " + str(CameraInUse.LastLightCommand)
        NewImageBuffer.AddText(text,xpos,ypos,color=BGRYellow,bgcolor=BGRBlack) 
        # Key in top right corner.
        xpos = width - 50
        ypos = 50
        NewImageBuffer.AddText("KEY",xpos,ypos,color=BGRWhite,hjust='r',bgcolor=BGRBlack)
        NewImageBuffer.AddText("Hipparcos O",xpos,NewImageBuffer.NextTextY,color=BGRPaleGreen,hjust='r',bgcolor=BGRBlack)
        NewImageBuffer.AddText("Messier O",xpos,NewImageBuffer.NextTextY,color=BGRGreen,hjust='r',bgcolor=BGRBlack)
        NewImageBuffer.AddText("NGC O",xpos,NewImageBuffer.NextTextY,color=BGRLightBlue,hjust='r',bgcolor=BGRBlack)
        NewImageBuffer.AddText("Planet O",xpos,NewImageBuffer.NextTextY,color=BGRGold,hjust='r',bgcolor=BGRBlack)
        NewImageBuffer.AddText("Constellation -",xpos,NewImageBuffer.NextTextY,color=BGRRed,hjust='r',bgcolor=BGRBlack)
        # More detail in bottom right corner. 
        xpos = int(width - 50)
        ypos = int(height - 100)
        NewImageBuffer.PrevTextY = ypos # Initialize line pointer for a text block.
        for i in MotorControls:
            text = "Motor: " + i.MotorName + " "
            text += Deg3dp(i.CurrentAngle) + "deg, " # DegreeSymbol 
            text += "position " + str(i.AngleToStep(i.CurrentAngle)) + " of " + str(i.AxisStepsPerRev)
            NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRGreen,bgcolor=BGRBlack,hjust='r')
        text = "Marking objects above magnitude " + str(round(Parameters.TargetMinMagnitude,1)) # Object magnitude filter.
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRGold,bgcolor=BGRBlack,hjust='r') 
        if Session.Target.Magnitude != None: # Magnitude of the target.
            text = "Target magnitude " + str(round(Session.Target.Magnitude,1))
        else:
            text = "Target magnitude UNKNOWN"
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRGold,bgcolor=BGRBlack,hjust='r')
        # Astro location.
        if Session.Target.ObjectType != 'meteor': # *Q* This doesn't work for meteor shower observations, so don't show it until fixed. 
            text = AzAltText(CentreAz, CentreAlt,'deg')
            NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRHotPink,bgcolor=BGRBlack,hjust='r')
            text = "RA: " + str(cRa) + " Dec: " + str(cDec)
            NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRHotPink,bgcolor=BGRBlack,hjust='r')
        # Lens characteristics
        text = "FOV: " + Deg3dp(LensInUse.FovHorizontal) + "deg * " + Deg3dp(LensInUse.FovVertical) + "deg" # DegreeSymbol
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRGold,bgcolor=BGRBlack,hjust='r') 
        # Exposure details
        NewImageBuffer.AddText("Exposure: " + str(CameraInUse.ExposureSeconds) + " seconds.",xpos,NewImageBuffer.PrevTextY,color=BGRGold,bgcolor=BGRBlack,hjust='r') 
        # Photo capture time.
        NewImageBuffer.AddText("Captured: " + str(CameraInUse.LastImageDateTime),xpos,NewImageBuffer.PrevTextY,color=BGRGold,bgcolor=BGRBlack,hjust='r') 
        if CameraInUse.CaptureStart > CameraInUse.CaptureEnd: # *Q* Timestamp range is sometimes invalid. Needs investigating.
            CamLog.Log("MarkupPreview: Capture timestamps invalid:",str(CameraInUse.CaptureStart),"-",str(CameraInUse.CaptureEnd),level='warning',terminal=False)
        text = "ImageCaptureEnd: " + str(CameraInUse.CaptureEnd)
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRCyan,bgcolor=BGRBlack,hjust='r')
        text = "Markup time: " + str(Ts2Datetime(t))
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGROrange,bgcolor=BGRBlack,hjust='r')
        text = "Target: " + Session.Target.Name # Target
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=BGRWhite,thickness=2,bgcolor=BGRBlack,hjust='r') 

    if True: # Parameters.MarkupSaveDraft:
        CamLog.Log("MarkupPreview: SaveDraft",filename,terminal=False)
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Show the preview filename that's being generated.
        NewImageBuffer.SaveFile(filename)
        CameraInUse.Previewjpg = filename # Record the filename so that the web interface can access it.

    CamLog.Log("MarkupPreview: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("MarkupPreview: End",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def CreateTargetImage(color=False,MinMagnitude=None,astrotime=None,StarLimit=None,textlabel=None):
    """ Create a mockup target image based purely upon the expected view. 
        color parameter dictates whether the return is GRAYSCALE or COLOR.
            Color images are generated when simulating a photograph (when the camera is disabled).
            Grayscale images are generated when creating a target star map for AstroAlign.
        By default it selects stars based upon Parameters.TargetMinMagnitude, however the calling routine can override this if required.
        color=True generates a colour image, star colours are estimated from the Hipparcos catalog data (B-V measure).
              This mode is used to simulate an observation photograph if there is no physical camera attached. 
        applydistortion = The image can have estimated lens distortion applied to more closely match a real photograph. """
    CamLog.Log("CreateTargetImage: Start. color",color,", MinMagnitude",MinMagnitude,terminal=False)
    if astrotime != None: CamLog.Log("CreateTargetImage: Start. Astrotime", Ts2Datetime(astrotime),terminal=False)
    else: CamLog.Log("CreateTargetImage: Start. Astrotime", astrotime,terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime == None: # No specific time given, so we're live! Use current time and current camera position.
        t = SkyfieldNow() # Current timestamp in 'astro' time. As close as possible to the time of the photograph itself. Could develop this further! # Offset supported.
        if Parameters.UseLiveLocation: # Use the live target location rather than the last reported camera position for image processing.
            az_degree, alt_degree = Session.Target.AzAltDegrees(time=t) # What is the alt/az location of the centre of the image?
            CamLog.Log("CreateTargetImage: No astrotime received. Using current target position, at",Ts2Datetime(t),
                       "alt",Deg3dp(alt_degree),"deg, az",Deg3dp(az_degree),"deg. at",Ts2Datetime(t),"for calculations",terminal=False)
        else: # Use the last reported camera position. Deprecated.
            alt_degree, az_degree = LastReportedAltAz() # What is the alt/az location of the centre of the image?
            #ldt = LastReportedLocationDatetime() # Get the timestamp of the oldest position reading.
            CamLog.Log("CreateTargetImage: No astrotime received. Using last reported camera position from",LastReportedLocationDatetime(),", using",
                       "alt",Deg3dp(alt_degree),"deg, az",round(az_degree),"deg. at",Ts2Datetime(t),"for calculations",terminal=False)
    else: # A specific time given, so calculate the view at that time. 
        t = astrotime
        az_degree, alt_degree = Session.Target.AzAltDegrees(time=astrotime) # Get expected camera position at specified time.
        CamLog.Log("CreateTargetImage: Specific astrotime received. Using",Ts2Datetime(t),Deg3dp(alt_degree),"deg",Deg3dp(az_degree),"deg",terminal=False)
    tgt_az_degree, tgt_alt_degree = Session.Target.AzAltDegrees(time=t) # Get expected camera position at specified time.
    CamLog.Log("CreateTargetImage: Latest Alt/Az",Deg3dp(alt_degree),"/",Deg3dp(az_degree),"deg",
               "; Target location Alt/Az",Deg3dp(tgt_alt_degree),"/",Deg3dp(tgt_az_degree),"deg",
               "; Latest vs Target Alt/Az",Deg3dp(alt_degree - tgt_alt_degree),"/",Deg3dp(az_degree - tgt_az_degree),"deg",terminal=False)
    if abs(alt_degree - tgt_alt_degree) > 0.5 or abs(az_degree - tgt_az_degree) > 0.5:
        CamLog.Log("CreateTargetImage: Latest vs Target locations differ too much: Alt/Az",
                   round(alt_degree - tgt_alt_degree,4),"/",round(az_degree - tgt_az_degree,4),terminal=False)
        DevWindow.Print(NowHMS() + " Latest v Target error alt/az " + 
                        str(round(alt_degree - tgt_alt_degree,4)) + "/" + str(round(az_degree - tgt_az_degree,4)))
    NewTargetImage = pilomarimage(name='target_work',logger=CamLog) # Create a new black canvas to draw upon.
    width = SensorInUse.PixelWidth # Image dimension should match the live photos that will be compared against.
    height = SensorInUse.PixelHeight
    NewTargetImage.New(height,width,imagetype='bgr',datatype=np.uint8)
    if MinMagnitude == None: # Calling procedure can override the minimum magnitude parameter.
        MinMagnitude = Parameters.TargetMinMagnitude
    CamLog.Log("CreateTargetImage: MinMagnitude:", MinMagnitude,terminal=False)
    starlist = [] # Create star list. This will be used by astroalign.find_transform() in tracking.

    # Mark neighbouring stars on the picture too. This will help with alignment.
    CentreRa ,CentreDec = Session.Target.RaDecDegrees() # Calculations for target from observer's location. Returns decimal degree values.
    # Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - Parameters.TargetInclusionRadius
    MaxRADeg = CentreRa + Parameters.TargetInclusionRadius
    MinDecDeg = CentreDec - Parameters.TargetInclusionRadius
    MaxDecDeg = CentreDec + Parameters.TargetInclusionRadius
    CamLog.Log("CreateTargetImage: Range RA=",MinRADeg,"<- (",CentreRa,") ->",MaxRADeg,"deg.",terminal=False)
    CamLog.Log("CreateTargetImage: Range Dec=",MinDecDeg,"<- (",CentreDec,") ->",MaxDecDeg,"deg.",terminal=False)

    if color: # Mark neighbouring Messier objects ....
        CamLog.Log("CreateTargetImage: ShowMessier",terminal=False)
        # Find that alt/az locations of all the objects.
        ItemCount = 0
        FullCount = 0
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            FullCount += 1
            TempStarMagnitude = TempStarParms['magnitude']
            if TempStarMagnitude > Parameters.TargetMinMagnitude: # Too dim to show.
                continue # Skip to next object.
            TempStarRA = TempStarParms['radeg'] # HMSToAngle(TempRAH,TempRAM,TempRAS)
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempDED = TempStarParms['dec'][0] # Declination DEGREES
            TempDEM = TempStarParms['dec'][1] # Declination MINUTES
            TempDES = TempStarParms['dec'][2] # Declination SECONDS
            TempStarDec = TempStarParms['decdeg'] # DMSToAngle(TempDED,TempDEM,TempDES)
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            TempStar = Star(ra_hours=(TempStarParms['ra'][0], TempStarParms['ra'][1], TempStarParms['ra'][2]), 
                            dec_degrees=(TempDED, TempDEM, TempDES)) # Create star object from RADEC co-ordinates.
            TempStarType = TempStarParms['type']
            if TempStarType in ['galaxy','cluster','milky way']: TempStarColor = BGRVeryDarkBlue
            else: TempStarColor = BGRHotPink
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from degree diameter to pixel radius.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            temptarget = target(TempStar,name=TempStarName,objecttype=TempStarType,constellation="",description="",magnitude=TempStarMagnitude)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            NewTargetImage.FillEllipse(TempStarX,TempStarY, TempStarWidth,TempStarHeight, angle=0, startAngle=0, endAngle=360, color=TempStarColor)
            ItemCount += 1
        CamLog.Log("CreateTargetImage: Plot Messier objects end. (",ItemCount,"/",FullCount,"objects selected)",terminal=False)

    if color: # Mark neighbouring NGC items ...
        # Find that alt/az locations of all the objects.
        # NGC catalog is large, eliminate as much as possible first.
        boolseries = NGC_DF['radeg'].between(MinRADeg, MaxRADeg, inclusive='both') # Create filter for items within RA range.
        tempdf = NGC_DF[boolseries] # Apply filter.
        boolseries = tempdf['decdeg'].between(MinDecDeg, MaxDecDeg, inclusive='both') # Create filter for items with Dec range.
        tempdf = tempdf[boolseries] # Apply filter.
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStar = Star(ra_hours=(TempStarParms['rah'], TempStarParms['ram'], TempStarParms['ras']), 
                            dec_degrees=(TempStarParms['ded'], TempStarParms['dem'], TempStarParms['des'])) # Create star object from RADEC co-ordinates.
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from degree diameter to pixel radius.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            temptarget = target(TempStar,name=TempStarParms['name'],objecttype='ngc',constellation="",description="",magnitude=TempStarParms['magnitude'])
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            CamLog.Log("CreateTargetImage: Plot NGC ",i,tempdf['name'],"at",TempStarX,TempStarY,"radius",TempStarWidth,TempStarHeight,terminal=False)
            NewTargetImage.FillEllipse(TempStarX,TempStarY, TempStarWidth,TempStarHeight, angle=0, startAngle=0, endAngle=360, color=BGRDarkGreen)
        CamLog.Log("CreateTargetImage: NGCItems: Plot NGC objects end. (",len(tempdf),"/",len(NGC_DF),"objects selected)",terminal=False)
        
    # Decide on a cutoff for the number of stars to plot.
    # If not specified by calling routine, try to match the number of stars detected in the latest live image.
    # (When simulating images, the first tracking pass will have 0 stars in the LatestStarCount, because it doesn't exist until we create it here.)
    if StarLimit == None: 
        StarLimit = max(DriftTracker.LatestImage.StarCount + 10,50)
        CamLog.Log("CreateTargetImage: LatestStarCount from last saved image is:", DriftTracker.LatestImage.StarCount,terminal=False)
        CamLog.Log("CreateTargetImage: LatestImage exists?",DriftTracker.LatestImage.ImageExists(),terminal=False)
    CamLog.Log("CreateTargetImage: Setting StarLimit as:", StarLimit,terminal=False)
    TempStarRadius = int(Parameters.TrackingStarRadius) # Default is that all stars are the same size in this image.
    
    if True: # Parameters.TargetShowStars: # Mark neighbouring stars.
             # *Q* This can be very slow, taking 270 seconds in some tests. This hits the CPU hard especially when faking all the photographs!
             #     But when run alone consistently takes only 18 seconds. Hmmmmm.... A conflict comewhere?
        StarCount = 0 # How many stars have we plotted?
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        CamLog.Log("CreateTargetImage: NeighbouringStars contains",len(NeighbouringStars),"entries.",terminal=False)
        TotalStars = len(NeighbouringStars)
        hsat = HomeSite.at(t) # Calculate this once, it's reused for each star in turn.
        TempStarColor = BGRWhite # B&W tracking images are just simple white dots.
        
        for i in range(TotalStars):
            if i % 400 == 0: 
                CamLog.Log("CreateTargetImage.ShowStars: Processing star",i,terminal=False) # Monitor performance
                time.sleep(0.1) # Put a small pause in occassionally to let other processes get a chance!
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStar = Star.from_dataframe(TempStarRec) # Convert the Hipparcos entry into a Skyfield STAR object.
            TempStarAlt, TempStarAz, TempStarDistance = hsat.observe(TempStar).apparent().altaz() # Get the azimuth and altitude position of the star in the sky.
            if color == False and TempStarAlt.degrees < 0: # Below horizon 
                continue # Don't plot it.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt.degrees,TempStarAz.degrees,alt_degree,az_degree) # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            if NewTargetImage.OutOfBounds(TempStarX,TempStarY): # The star is off the edge of the image, ignore it.
                continue # The star is off the edge of the image, ignore it.
            TempStarMagnitude = TempStarRec['magnitude'] # Note the brightness of the star.
            if TempStarMagnitude > MinMagnitude: # Too dim
                continue # The star is too dim, ignore it.
            if color: # Colour images need star colour and represent the magnitude via the size of the star.
                TempStarRadius = int(TempStarRec['starradius'])
                TempStarColor = (int(TempStarRec['color_b']),int(TempStarRec['color_g']),int(TempStarRec['color_r']))
            NewTargetImage.FillCircle(TempStarX,TempStarY,TempStarRadius,color=TempStarColor)
            starlist.append([TempStarX,TempStarY]) # *Q* Does latest drift calculation need Radius or Magnitude anymore?
            StarCount += 1 # Increment the count of stars plotted. 
            if StarCount >= StarLimit:
                CamLog.Log("CreateTargetImage: DriftTracker star limit " + str(StarLimit) + " reached.",terminal=False)
                CamLog.Log("CreateTargetImage: DriftTracker star limit reached HIP",TempStarRec.name,", magnitude",TempStarRec['magnitude'],terminal=False)
                break
        CamLog.Log("CreateTargetImage: Marked",StarCount,"of",StarLimit,"Stars,",TotalStars,"available.",terminal=False)
        if StarCount < StarLimit:
            CamLog.Log("CreateTargetImage: Exhausted NeighbouringStars cache after",StarCount,"stars.",terminal=False)
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
                continue # Skip to next planet.
            if color: # Color images try to be vaguelly realistic.
                TempStarColor = PlanetColors[i]
                TempStarRadius = PlanetRadii[i]
            else: # Grayscale images just need to show dots for items.
                TempStarColor = BGRWhite
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = target(TempStar,name=TempStarName,objecttype="planet",description=TempStarDescription,magnitude=0.0)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t)
            # Calculate the location of the star in the field of view!
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree) # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            NewTargetImage.FillCircle(TempStarX,TempStarY,TempStarRadius,color=TempStarColor)
        CamLog.Log("CreateTargetImage: Plot planets end.",terminal=False)

    if textlabel != None: # We have a text string to include in the image too.
        NewTargetImage.AddText(textlabel,10,50,color=BGRWhite,size=1.0,thickness=1)

    if color: # Return a colour image.
        pass
    else: # Return Grayscale image.
        NewTargetImage.ChangeType('grayscale') # Convert BGR to grayscale.
    CamLog.Log("CreateTargetImage: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("CreateTargetImage: Complete.",terminal=False)
    return NewTargetImage.ImageBuffer,StarCount,starlist

# ------------------------------------------------------------------------------------------------------

def AutoPreview():
    """ Take immediate automatic photograph and mark it up with the expected objects in view. 
        This is normally used for calibration and testing. """
    MainLog.Log("AutoPreview",terminal=True)
    FileRoot = FolderList.get('preview') + 'preview_'
    CameraInUse.SetImageType('auto')
    # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
    # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
    CameraCommand = Parameters.CameraAutoCommand
    # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
    MainLog.Log("AutoPreview: Capturing image...",terminal=True)
    result = CameraInUse.CaptureSet(file_root=FileRoot,batch_size=1,camera_command=CameraCommand,terminal=False)
    MainLog.Log("AutoPreview: Marking image...",terminal=True)
    MarkupPreview()
    MainLog.Log("Done.",terminal=True)
    return result

# ------------------------------------------------------------------------------------------------------

def ManualPreview():
    """ Force immediate image capture from the camera.
        This is used to help check camera focus or alignment without 
        starting a full observation loop. """
    print (textcolor.yellow("ManualPreview"))
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

def ImageCount_Session():
    """ Count images in each folder for the current session. 
        It counts the occurrences of whichever filetype the program is currently generating. 
        - *.dng, or *.fits or *.jpg 
        So it avoids double-counting images if multiple image types are being generated. """
    result = ''
    campaignkey = FolderList['campaign'] # Only interested in files within the campaign structure.
    imagetypes = ['jpg','dng']
    for key,value in FolderList.items(): # Python3: Check each folder.
        if value.startswith(campaignkey):
            filelist = []
            try:
                for file in os.listdir(value): # List files in folder.
                    filename = file.split('.')[0]
                    filetype = file.split('.')[-1]
                    if filetype in imagetypes: # It's an image file.
                        if not filename in filelist: filelist.append(filename) # list of unique filenames (minus filetype).
            except Exception as e:
                MainLog.Log("ImageCount_Session: Failed with:",e,level='warning') # Allow graceful failure in case the folder nolonger exists.
            count = len(filelist)
            if count > 0: # Only report the folder if there's something in it.
                result += key + '=' + str(count) + ' ' # Abbreviate image type and number of images.
    if result == '': result = 'None'
    return result

# ------------------------------------------------------------------------------------------------------

def ImageCount_Campaign(): 
    """ Count images in each folder for the current campaign.
        It counts the occurrences of whichever filetype the program is currently generating. 
        - *.dng, or *.fits or *.jpg 
        So it avoids double-counting images if multiple image types are being generated. """
    # *Q* This solution slows down a lot for large file collections. Could be faster, but not used during an observation.
    result = ''
    if Parameters.CameraEnabled != True: selext = '.jpg' # No camera, so only count the simulated jpgs.
    elif CameraInUse.CameraSaveJpg: selext = '.jpg' # Looking for .jpg will detect more than .dng
    elif CameraInUse.CameraSaveDng: selext = '.dng'
    else: selext = '.jpg'
    basedir = FolderList['campaign']
    MainLog.Log("ImageCount_Campaign: basedir",basedir,terminal=False)
    searchpath = basedir + "**/*" + selext
    MainLog.Log("ImageCount_Campaign: searchpath",searchpath,terminal=False)
    FileCountList = {}
    for file in glob.glob(searchpath, recursive=True): # Recursive search through all the folders of the current campaign.
        trimmedfile = file.replace(basedir,"") # Strip search path out.
        foldertype = trimmedfile.split("/")[-2].split('_')[0] # Last remaining item is filename, Penultimate folder is image type.
        FileCountList[foldertype] = FileCountList.get(foldertype,0) + 1 # How many files of this type so far?
    # Convert the list of image types and counts into a summarised text string.
    for key,value in FileCountList.items():
        result += key + '=' + str(value) + ' ' # Abbreviate image type and number of images.
    if result == '': result = 'None'
    return result

# ------------------------------------------------------------------------------------------------------

def ImageCount(): # Could just be ImageCount_Session() directly now.
    """ Return count of images per type. """
    return ImageCount_Session() # Return values for the session, ignore other sessions in the same campaign.

# ------------------------------------------------------------------------------------------------------

def CheckImageSet():
    """ Check that we have a full set of images. 
        Call this before allowing a change of target, session parameters or ending a session.
        If the user selects YES, then we allow the target/session to change.
        If the user selects NO, then we keep the session alive with the current target and settings. 
        If the folder has been deleted, then there are no images to worry about! """
    imagelist = ImageCount()
    result = True # We're happy that the image list is OK.
    if len(imagelist) > 0 and imagelist != 'None':
        lines = ["Make sure you have captured the full set of images you need for this session.",
                 "You will normally need a set of LIGHT, DARK, FLAT, DARK FLAT and BIAS images.",
                 "Recommended minimum for stacking: LIGHT, DARK and BIAS sets.",
                 "Images captured so far:",
                 imagelist]
        textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK)
        result = AskYesNo("Is this session complete? [y/N]",default=False)
        print (" ")
    return result

# ------------------------------------------------------------------------------------------------------

def CameraHandler(outboundqueue,inboundqueue):
    """ This can run in a separate thread to take photos without distrubing tracking functions. 
        Long exposures (>4seconds) really need the camera to move DURING the exposure.
        outboundqueue and inboundqueue are the communication queues that can be used to control this thread. """
    RunThread = True # Set to False to terminate the handler. This will shutdown the thread entirely.
    batch_size = 1
    CamLog.Log('CameraHandler: Started')
    CameraWindow.Print(NowHMS() + ' CameraHandler started.')
    ReadyToObserve = False # When True the handler can start taking photographs. 
    CamLog.Log('CameraHandler.initial: ReadyToObserve = False',terminal=False)
    PrevReadyToObserve = False # Detect when the ReadyToObserve status changes.
    PhotoCount = 0 # Counter of completed photographs. 
    CameraInUse.BatchCount = 0 # Counter of completed photographs.
    AzDriftSteps = 0
    AltDriftSteps = 0
    DriftX = None
    DriftY = None
    TimeAllocation = {} # Measure how much time is spent on each task. Helps get scheduling and priorities right.
    AllocationTimer = timer(600) # Report time allocation figures every 10 minutes.
    LoopCounter = 0 # Count the number of loops.
    CameraInUse.CurrentTask = None # No task currently active.
    # Flush any outstanding commands in the command queue.
    FlushedCount = 0
    while inboundqueue.empty() == False: # There are some commands available from ObservationRun to the camera.
        # Get the incoming message.
        ReceivedMessage = inboundqueue.get()
        CamLog.Log("camerahandler: Communication flush: Ignoring:",ReceivedMessage,terminal=False)
        FlushedCount += 1
    if FlushedCount > 0:
        CameraWindow.Print("Flushed",FlushedCount,"old messages.")
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
        CameraInUse.CurrentTask = LoopTask
        LoopStartTimestamp = NowUTC() # How much time has been spent on this task?
        PrevTaskList = CameraInUse.CameraTasks # This will be restored if the camera receives an override task from the main loop. So we don't miss anything.
        CameraInUse.CameraTasks = CameraInUse.CameraTasks[1:] # Shift the task list ready for the next loop. 
        CameraInUse.CameraTasks.append(LoopTask)
        CamLog.Log('CameraHandler: Loop task:',LoopTask,terminal=False)
        
        # This will run through all queued commands in sequence before capturing images if allowed.
        # This is performed regardless of which task is being performed in this loop.
        while inboundqueue.empty() == False: # There are some commands available from ObservationRun to the camera.
            # Get the incoming message.
            ReceivedMessage = inboundqueue.get()
            CameraInUse.RxCount += 1
            CamLog.Log('CameraHandler received command: ' + str(ReceivedMessage),terminal=False)
            CameraTxWindow.Print(DictionaryToString(ReceivedMessage)) # Report communications from Main to Camera. 
            if 'Stop' in ReceivedMessage: # Main routine has told camera to shutdown. 
                RunThread = False
                ReplyMessage = {'TimeStamp' : NowUTC(), 'Stop' : 'acknowledged'} # Confirm back to main thread that STOP will be attempted.
                outboundqueue.put(ReplyMessage)
                CameraInUse.TxCount += 1
                CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.
            if 'LoopTask' in ReceivedMessage: # Main routine has requested an immediate preview image or some other task override.
                # If multiple overrides are received in the same loop, only the latest one is actioned.
                LoopTask = ReceivedMessage['Task'] # Overwrite LoopTask to make it do whatever the main routine wants.
                CameraInUse.CameraTasks  = PrevTaskList # We have overridden the planned task sequence, restore the planned list to it's previous state so nothing is missed.
                DevWindow.Print(NowHMS() + ' LoopTask override "' + LoopTask + '" received.')
                CamLog.Log('CameraHandler.inboundqueue: LoopTask overridden with',LoopTask,terminal=False)
            if 'BatchSize' in ReceivedMessage: # Main routine is updating the batch size.
                batch_size = ReceivedMessage['BatchSize']
            if 'ReadyToObserve' in ReceivedMessage: # Main routine is updating the ReadyToObserve status.
                ReadyToObserve = ReceivedMessage['ReadyToObserve']
                CamLog.Log('CameraHandler.inboundqueue: ReadyToObserve =',ReadyToObserve,terminal=False)
            if 'Reset' in ReceivedMessage: # Instruction to reset image buffers.
                CameraInUse.Reset() # Reset the image buffers.
                CameraWindow.Print(NowHMS() + ' Reset image buffers.')
                CamLog.Log('CameraHandler.inboundqueue: reset received.',terminal=False)
            if 'PhotoCount' in ReceivedMessage: # Main routine is updating the current photo count.
                PhotoCount = ReceivedMessage['PhotoCount']
                ReplyMessage = {'TimeStamp' : NowUTC(), 'PhotoCountReset' : True} # Acknowledge that the photo count has been reset.
                outboundqueue.put(ReplyMessage)
                CameraInUse.TxCount += 1
                CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.

        if LoopTask == 'image': # Taking an actual photo.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=textcolor.BLACK,bg=OSW_TEXT_GOOD) # Tell the image status window what the camera is currently doing.
        elif LoopTask == 'tracking': # Taking a tracking photo.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=textcolor.BLACK,bg=textcolor.CYAN)
        elif LoopTask == 'preview': # Generate preview image.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=textcolor.BLACK,bg=textcolor.MAGENTA)
        else: # Doing something else.
            ImageStatusWindow.FieldValue('CTASK',LoopTask,fg=textcolor.BLACK,bg=OSW_TEXT_POOR) # Tell the image status window what the camera is currently doing.

        # If the Microcontroller stops working or talking, we cannot be sure that ReadyToObserve is still valid.
        # So after xx seconds of no microcontroller messages, reset ReadyToObserve.
        if ReadyToObserve and Mctl.RxAge() > Mctl.CommsTimeout:
            CamLog.Log('CameraHandler: (CamLog) No recent messages from microcontroller (', Mctl.CommsTimeout, 's), assuming ReadyToObserve is nolonger valid.',level='warning',terminal=False)
            ReadyToObserve = False
            CamLog.Log('CameraHandler. Microcontroller comms timeout: ReadyToObserve = False',terminal=False)
            ErrorWindow.Print(NowHMS() + ' Microcontroller comms timeout.')

        if ReadyToObserve != PrevReadyToObserve: # Note the change in status of ReadyToObserve.
            CameraWindow.Print (NowHMS() + ' ReadyToObserve ' + str(ReadyToObserve))
            PrevReadyToObserve = ReadyToObserve
            CamLog.Log('CameraHandler. Change of state: ReadyToObserve from ',PrevReadyToObserve,'to',ReadyToObserve,terminal=False)
        
        if ReadyToObserve:
            # Calculate drift.
            if LoopTask == 'tracking': # Time to consider a tracking check, and it's enabled.
                if DriftTracker.TrackingAge() == None or DriftTracker.TrackingAge() > DriftTracker.TrackingInterval: TrackingDue = True
                else: TrackingDue = False
                if Parameters.UseTracking == False: # Tracking currently disabled. (User can dynamically change this switch during observation).
                    if TrackingDue: DriftWindow.Print(NowHMS() + ' Drift tracking disabled.') # Warn the user.
                elif TrackingDue:
                    # First update the DriftTracker 
                    obs_start = NowUTC()
                    CamLog.Log('CameraHandler: Begin tracking image capture',terminal=False)
                    DriftWindow.Print(NowHMS() + ' Begin tracking image capture.')
                    if Session.DebugMode:
                        print(NowHMS() + ' Begin ' + textcolor.cyan('tracking') + ' image capture.')
                    try: 
                        result = CameraInUse.TakeTrackingPhoto(batch_size,terminal=False)
                    except:
                        CamLog.Log('CameraHandler: CameraInUse.TakeTrackingPhoto failed.',level='error')
                        result = False
                    CamLog.Log('CameraHandler: End tracking image capture',terminal=False)
                    CamLog.Log('CameraHandler: Storing latest tracking image.',terminal=False)
                    DriftTracker.SetLatestImage(CameraInUse.Image.ImageBuffer,obs_start) # OpenCV (numpy) array of the camera image it is saved in DriftTracker as Grayscale and reduced and enhanced.
                    CamLog.Log( 'CameraHandler: Consider storing target image...',terminal=False)
                    CamLog.Log( 'CameraHandler: Begin CreateTargetImage',terminal=False)
                    if Parameters.TrackingTargetGrayscale: # Generate simplified tracking target.
                        TempCvBuffer,TempStarCount,TempStarList = CreateTargetImage(color=False,MinMagnitude=Parameters.TargetMinMagnitude,StarLimit=2000) # Create a completely calculated mock target image (grayscale). Used for image tracking.
                    else: # Use more realistic tracking target.
                        TempCvBuffer,TempStarCount,TempStarList = CreateTargetImage(color=True,MinMagnitude=Parameters.TargetMinMagnitude,StarLimit=2000) # Create a completely calculated mock target image (grayscale). Used for image tracking.
                    CamLog.Log( 'CameraHandler: End CreateTargetImage',terminal=False)
                    CamLog.Log( 'CameraHandler: Stars',TempStarCount,':',TempStarList,terminal=False)
                    CamLog.Log( 'CameraHandler: Calling SetTargetImage after CreateTargetImage',terminal=False)
                    DriftTracker.SetTargetImage(TempCvBuffer,starcount=TempStarCount,starlist=TempStarList,timestamp=obs_start) # CvImage is an OpenCV (numpy) array of the camera image in grayscale.
                    CamLog.Log( 'CameraHandler: Completed SetTargetImage after CreateTargetImage',terminal=False)
                    CamLog.Log( 'CameraHandler: Begin drift calculation',terminal=False)
                    DriftWindow.Print(NowHMS() + ' Updating drift calculation for tracking.')
                    AzDriftSteps = 0 # No drift unless we safely calculate one.
                    AltDriftSteps = 0
                    if Parameters.TrackingPrediction: # Project drift forward over time.
                        #DriftX, DriftY, tempdelta = DriftTracker.PredictedTransform(NowUTC()) # Predict the drift by using the measured drift between 2 images and extrapolating forward to now.
                        DriftX, DriftY, _ = DriftTracker.PredictedTransform(NowUTC()) # Predict the drift by using the measured drift between 2 images and extrapolating forward to now.
                    else: # Use directly measured drift.
                        DriftX = DriftTracker.dx
                        DriftY = DriftTracker.dy
                    CamLog.Log('CameraHandler: DriftTracker PredictedTransform driftx', str(DriftX), 'drifty', str(DriftY), terminal=False)
                    #temp = min(len(DriftTracker.TargetImage.StarList),len(DriftTracker.LatestImage.StarList))
                    temp = len(DriftTracker.LatestStarMatchList)
                    if DriftX != None and temp < Parameters.TrackingMatchThreshold: # At least 6 stars must have been matched.
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
                            if AzDriftSteps != None and abs(AzDriftSteps) > Parameters.MinimumDriftCorrection: # Drift is large enough to do something.
                                DriftWindow.Print(NowHMS() + ' Tuning ' + i.MotorName)
                                CamLog.Log(NowHMS() + ' Tuning ' + i.MotorName,terminal=False)
                                i.TunePosition(AzDriftSteps)
                            else: # Drift is too small to worry about.
                                DriftWindow.Print(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.')
                                CamLog.Log(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.',terminal=False)
                        elif i.MotorName == 'altitude': # Altitude motor.
                            if AltDriftSteps != None and abs(AltDriftSteps) > Parameters.MinimumDriftCorrection: # Drift is large enough to do something.
                                DriftWindow.Print(NowHMS() + ' Tuning ' + i.MotorName)
                                CamLog.Log(NowHMS() + ' Tuning ' + i.MotorName,terminal=False)
                                i.TunePosition(AltDriftSteps)
                            else: # Drift is too small to worry about.
                                DriftWindow.Print(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.')
                                CamLog.Log(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.',terminal=False)
                    ReplyMessage = {'TimeStamp' : NowUTC(), 'DriftX' : DriftX, 'DriftY' : DriftY, 'AzDriftSteps' : AzDriftSteps, 'AltDriftSteps' : AltDriftSteps} 
                    outboundqueue.put(ReplyMessage)
                    CameraInUse.TxCount += 1
                    CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.
                    CamLog.Log('CameraHandler: End drift calculation',terminal=False)
            if LoopTask == 'image': # Time to take an actual image. (If timelapse is active, only when it's due, otherwise every time.)
                # Now take the actual observation photo ('light' image).
                obs_start = NowUTC()
                CamLog.Log('CameraHandler: Begin image capture',terminal=False)
                if Session.DebugMode:
                    print(NowHMS() + ' Begin ' + textcolor.green('image') + ' capture (' + str(PhotoCount + 1) + ') ' + str(CameraInUse.ExposureSeconds) + 's.')
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
                    CameraInUse.TxCount += 1
                    CameraRxWindow.Print(DictionaryToString(ReplyMessage))
                    CamLog.Log("Folder for image details:", FolderList['session'],terminal=False)
                    detailsfile = FolderList['session'] + 'imagedetails.txt'
                    tempra, tempdec = Session.Target.RaDecHours() # Current RA and DEC of target.
                    tempaz, tempalt = Session.Target.AzAltDegrees() # Current AZ and ALT of target.
                    if Parameters.ScanForMeteors and CameraInUse.Image.ContainsMeteors(): # Scan latest CvImage buffer for meteors or aircraft trails.
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
                if PreviewTimer.Due() and CameraInUse.Image.ImageExists(): # Periodically prepare a new preview image. This is slow, so don't do it very frequently.
                    CamLog.Log('CameraHandler: Begin preview image markup',terminal=False)
                    if Session.DebugMode:
                        print (NowHMS() + ' Begin ' + textcolor.magenta('preview') + ' image generation.')
                    # astrocamera.CaptureSet will have loaded the image into OpenCV compatible buffer. This is available to mark up with more information.
                    MarkupPreview(drift_pixels_x=DriftTracker.dx,drift_pixels_y=DriftTracker.dy,astrotime=CameraInUse.AstrotimeEnd) # Use last image buffer from CameraInUse.Image to generate a marked up copy of the image on disc.
                    CamLog.Log('CameraHandler: End image markup',terminal=False)

            # Stop taking photos when the limit is reached. The main thread will also command the photos to stop, but it may be delayed.
            if PhotoCount >= Parameters.BatchSize:
                CamLog.Log('CameraHandler: Batch size reached.', PhotoCount, 'images captured.',terminal=False)
                CameraWindow.Print(NowHMS() + ' CameraHandler: Batch size reached. ' + str(PhotoCount) + ' images captured.')
                ReadyToObserve = False
                CamLog.Log('CameraHandler. BatchSize limit: ReadyToObserve = False',terminal=False)
        else: # ReadyToObserve = False - No camera tasks performed.
            ImageStatusWindow.FieldValue('CTASK','WAITING',fg=textcolor.WHITE,bg=textcolor.RED)

        if RunThread and LoopTask == 'pause': time.sleep(0.25) # Small delay in each loop to relax things.

        # How much time has been spent on this task?
        LoopDuration = (NowUTC() - LoopStartTimestamp).total_seconds()
        TimeAllocation[LoopTask] = LoopDuration + TimeAllocation.get(LoopTask,0.0)
        LoopCounter += 1
        if LoopTask != 'pause': # Record CPU usage for the latest task.
            CamLog.Log("CameraHandler: Loop completed",LoopTask,"in",round(LoopDuration,2),"seconds",terminal=False)
        if AllocationTimer.Due(): # Report how much time has been spent on each type of task.
            CamLog.Log("CameraHandler: Completed loop",LoopCounter,terminal=False)
            totaltime = 0
            for key,value in TimeAllocation.items():
                totaltime += value
            for key,value in TimeAllocation.items():
                if totaltime > 0: timepc = int(100 * value / totaltime) # Calculate % share.
                else: timepc = 0
                CamLog.Log("CameraHandler: TimeAllocation:",key,value,"seconds (",timepc,"%)",terminal=False)

    CameraInUse.CurrentTask = None # No task currently active.
    ReplyMessage = {'TimeStamp' : NowUTC(), 'RunThread' : False}
    outboundqueue.put(ReplyMessage)
    CameraInUse.TxCount += 1
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

def StartCameraThread():
    global CameraThread # Must be global because it must persist after this function completes. 
    if CameraThread == None or CameraThread.is_alive() != True:
        CameraThread = threading.Thread(target=CameraHandler,args=(CameraStatusQueue,CameraControlQueue))
        CameraThread.start()
    return True

# ------------------------------------------------------------------------------------------------------

def ShutdownCamera():
    """ Close the camerahandler thread. """
    global CameraThread
    global CameraStatusQueue
    global CameraControlQueue
    success = True # Assume success unless we fail to shut down the handler correctly. 
    print ('\n' + textcolor.yellow('Stopping CameraHandler...')) # force newline before printing text.
    if CameraInUse.CurrentTask != None:
        print ('The camera is currently processing the "' + str(CameraInUse.CurrentTask) + '" task.')
    print ('Waiting for CameraHandler to confirm it has completed (telescope may continue to move until this is finished) ...')
    CameraControlQueue.put({'Stop' : True}) # Post a shutdown message to the CameraHandler
    Session.CameraTxCount += 1 # We sent another message to the camera.
    # This waits for confirmation and warn to powercycle the RPi if the STOP command is unsuccessful after xxx seconds.
    # We'll give the CameraHandler some time to shut down.
    # - Some tasks are quite slow, for example long exposures, or complex tracking operations.
    CameraShutdownTimer = timer(max(200,CameraInUse.ExposureSeconds * 4)) 
    while True: # Loop until CameraShutdownTimer expires.
        if CameraThread.is_alive() == False: break # Camera thread is completely stopped so OK to proceed.
        if CameraStatusQueue.empty() == False: 
            StatusMessage = CameraStatusQueue.get() # We have some feedback.
            Session.CameraRxCount += 1 # We received another message from the camera.
        else: StatusMessage = {} # Nothing from CameraHandler.
        if 'RunThread' in StatusMessage: # RunThread status message received.
            if StatusMessage['RunThread'] == False: # CameraHandler is shutting down.
                print ("CameraThread stopping...")
                if CameraThread.is_alive():
                    CameraThread.join() # Wait for it to complete.
                print (textcolor.yellow("CameraThread successfully stopped."))
                break # OK to proceed.
        if CameraShutdownTimer.Due(): # Timeout has expired, something's wrong.
            CamLog.Log("The CameraHandler did not stop in a reasonable time.",terminal=False,level='error')
            lines = ['Please POWER CYCLE the RPi to clear a potentially hung camera board.',
                     '(Just restarting the program may not solve the problem.',
                     ' Just rebooting the RPi may not solve the problem either.)',
                     'You may need to CTRL-C now to break out of the stuck camerahandler thread.',
                     'The process stack has been recorded in the camera log file:',
                     CamLog.FileName]
            textcolor.TextBox(lines,fg=textcolor.RED,bg=textcolor.BLACK)
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

StartCameraThread() # Fire up the camera handler as a separate thread. 

# ------------------------------------------------------------------------------------------------------

# Run the message handler as a separate thread.
# - This keeps traffic between RPi and Microcontroller running independently.
MessageThread = None # Pointer to the message handler.

# ------------------------------------------------------------------------------------------------------

def StartMessageThread(): 
    global MessageThread # Must be global because it must persist after this function completes. 
    Session.TerminateMctlHandler = False # Clear any existing shutdown flag.
    if MessageThread == None or MessageThread.is_alive() != True:
        MessageThread = threading.Thread(target=Session.MctlHandler)
        MessageThread.start()
    return True

# ------------------------------------------------------------------------------------------------------

def ShutdownMessage(): 
    """ Close the messagehandler thread. """
    global MessageThread
    success = True # Assume success unless we fail to shut down the handler correctly. 
    print ('\n' + textcolor.yellow('Stopping MessageHandler...')) # force newline before printing text.
    print ('Waiting for MessageHandler to confirm it has completed...')
    Session.TerminateMctlHandler = True # Post a shutdown message to the MessageHandler
    # This waits for confirmation and warn to powercycle the RPi if the STOP command is unsuccessful after xxx seconds.
    # We'll give the MessageHandler some time to shut down.
    # - Some tasks are quite slow, for example long exposures, or complex tracking operations.
    MessageShutdownTimer = timer(200) 
    while True: # Loop until MessageShutdownTimer expires.
        if MessageThread.is_alive() == False: break # Message thread is completely stopped so OK to proceed.
        if MessageShutdownTimer.Due(): # Timeout has expired, something's wrong.
            MainLog.Log("The MessageHandler did not stop in a reasonable time.",terminal=False,level='error')
            success = False # A terminal error occurred.
            break # OK to proceed.
        else: 
            temp = int(MessageShutdownTimer.Remaining()) # How many seconds left?
            if temp < 60: print ('Timeout in ' + textcolor.red(HRSeconds(temp)) + textcolor.cursorup())
            elif temp < 120: print ('Timeout in ' + textcolor.yellow(HRSeconds(temp)) + textcolor.cursorup())
            else: print ('Timeout in ' + textcolor.green(HRSeconds(temp)) + textcolor.cursorup())
        time.sleep(0.5) # Slight pause between loops.
    return success

# ------------------------------------------------------------------------------------------------------

StartMessageThread()

# ------------------------------------------------------------------------------------------------------

def GoToTarget(target_object):
    """ Point camera at the target. But don't begin an observation. 
        Observations can only start once the microcontroller has a trajectory available to follow. """
    print (textcolor.yellow("GoToTarget: Pointing camera at target."))
    
    StopMotors() # Clear anything that's still programmed for the motors. 
    Session.SetMotorControlMode('direct') # We will directly control the movement of the microcontroller, no trajectory needs sending.

    # Prelocate the motors if case we need to handle gear backlash. It is good to go to a slightly lower azimuth position before starting the observation.
    if Parameters.BacklashEnabled: # We're handling gear backlash.
        currentalt, currentaz = LastReportedAltAz() # What is current position of the camera?
        az, alt = Session.Target.AzAltDegrees() # What is the current position of the target?
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
                    MainLog.Log("GoToTarget: Pre alignment of " + i.MotorName + " motor to allow for gear backlash. Moving to " + Deg3dp(targetangle,DegreeSymbol))
                    i.MonitorMove = True # Display movement progress on the terminal.
                    temp = i.GoToAngle(targetangle) # Move the motor PAST the target position, so that it will have to reverse to get on target. This will take up the slack in the gears.
                    i.MonitorMove = False # Do not display movement progress on the terminal.
                    if not temp: # Move failed.
                        MainLog.Log('GoToTarget: GoToAngle() call failed. Pre alignment of ' + i.MotorName + ' failed.',level='error')
                        return False # Failed!
            else: MainLog.Log('GoToTarget: No backlash adjustment required for ' + i.MotorName)

    # GoTo the target. 
    az, alt = Session.Target.AzAltDegrees() # What is the current position of the target?
    currentalt, currentaz = LastReportedAltAz() # What is the current position of the camera?
    MainLog.Log('GoToTarget: Alignment: From ' + AzAltText(currentaz,currentalt) + " to " + AzAltText(az,alt))
    for i in MotorControls: # Check every motor.
        targetangle = i.CurrentAngle # Default is the current position.
        if i.MotorName == "azimuth": # Compare target azimuth with current azimuth
            targetangle = az # Position the motor ON the target.
        elif i.MotorName == "altitude": 
            targetangle = alt # Position the motor ON the target.
        if i.CompareAngles(i.CurrentAngle,targetangle) == False: # There's a big enough position difference that it's worth moving the camera.
            MainLog.Log("GoToTarget: Target", i.MotorName, "from", Deg3dp(i.CurrentAngle,DegreeSymbol),"to",Deg3dp(targetangle,DegreeSymbol))
            i.MonitorMove = True # Display movement progress on the terminal.
            temp = i.GoToAngle(targetangle) # Move the motor now.
            i.MonitorMove = False # Do not display movement progress on the terminal.
            if not temp: # Move failed.
                MainLog.Log('GoToTarget: GoToAngle() call failed. Alignment of ' + i.MotorName + ' failed (From angle',Deg3dp(i.CurrentAngle,DegreeSymbol),'to',Deg3dp(targetangle,DegreeSymbol),').',level='error')
                MainLog.Log('GoToTarget: GoToAngle() call failed. Alignment of ' + i.MotorName + ' failed (From position',i.AngleToStep(i.CurrentAngle),'to',i.AngleToStep(targetangle),').',level='error')
                return False # Failed!
        else: MainLog.Log('GoToTarget: Motor ' + i.MotorName + ' already on target.')
    StopMotors() # Reset motor condition to prevent further movement.
    print ("NOTE: The camera is now positioned, but it is not tracking or photographing the target yet.")
    print ("      (Pi-lomar must calculate a trajectory before photography can start.)")
    print (textcolor.yellow("Done."))
    return True
  
# ------------------------------------------------------------------------------------------------------

def StopMotors(): 
    """ Send a fresh STOP command to the motorcontroller. 
        This is called automatically at the end of an observation, 
        it can also be sent manually from the Motor Controls menu. """
    Mctl.WriteFlush(send=False) # Scrap all outstanding messages to the microcontroller.
    Mctl.Write('stop') # Tell the motors to immediately stop.
    Mctl.Write('clear trajectory') # Remove any existing trajectory from the motors.
    Session.SetMotorControlMode('idle') # We nolonger need to maintain a trajectory.

# ------------------------------------------------------------------------------------------------------

def RestartMicrocontroller(): # For menu
    global MctlThread
    global Mctl
    if MctlThread.is_alive() != True: 
        MainLog.Log("ResetMctl: MctlThread is missing. Restarting...")
        Mctl = InitiateMctl() # Restart the microcontroller thread.
        MctlThread = threading.Thread(target=StartMctlComms,args=(),daemon=True) # Run microcontroller communication independently, quit automatically.
        MctlThread.start()
    Mctl.Reset(planned=True) # Restart the microcontroller manually. 

# ------------------------------------------------------------------------------------------------------


def MotorStatusOff():
    """ Turn motor status messages off.
        Feature to support 'fast' configuration of a complete trajectory for a motor. """
    MainLog.Log("MotorStatusOff: Turn off motor status messages.",terminal=False)
    print ("Microcontroller will not send motor status messages back to the RPi.")
    Mctl.Write('sendstatus ' + CleanDatetimeString(str(NowUTC())) + ' n ') # Turn off motor status responses.

# ------------------------------------------------------------------------------------------------------

def MotorStatusOn():
    """ Turn motor status messages on.
        Feature to support 'fast' configuration of a complete trajectory for a motor. """
    MainLog.Log("MotorStatusOff: Turn on motor status messages.",terminal=False)
    print ("Microcontroller will send motor status messages back to the RPi.")
    Mctl.Write('sendstatus ' + CleanDatetimeString(str(NowUTC())) + ' y ') # Turn on motor status responses.


# ------------------------------------------------------------------------------------------------------

def MicrocontrollerLedsOff(): # For menu
    Parameters.MctlLedStatus = False
    SetGlobalLedStatus()
    lines = ["Microcontroller LEDs are now off.",
             " ",
             "The RGB LED will remain off throughout operation.",
             " ",
             "This reduces the stray light within the",
             "observatory dome."]
    textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK)

# ------------------------------------------------------------------------------------------------------

def MicrocontrollerLedsOn(): # For menu
    Parameters.MctlLedStatus = True
    SetGlobalLedStatus()
    lines = ["Microcontroller LEDs are now on.",
             " ",
             "The RGB LED will be active throughout operation.",
             " ",
             "This increases the stray light within the",
             "observatory dome."]
    textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK)

# ------------------------------------------------------------------------------------------------------

def TrackingOn():
    """ Turn drift tracking on. """
    MainLog.Log("Turning drift tracking on.",terminal=True)
    Parameters.UseTracking = True

# ------------------------------------------------------------------------------------------------------

def TrackingOff():
    """ Turn drift tracking off. """
    MainLog.Log("Turning drift tracking off.",terminal=True)
    Parameters.UseTracking = False

# ------------------------------------------------------------------------------------------------------

def ObservationSubmenu(drifttracker=None): 
    """ Submenu of options that can be used DURING an observation. """
    ClearScreen() # Clear the screen and force window refresh.
    
    if drifttracker == None: temp = None # There is no drifttracker object to call.
    else: temp = drifttracker.Reset # There is a drifttracker object to call.
    SubMenuOptions = {
        'ProgramStatus':          {'label':'Status',                    'call':ProgramStatus, 'break':True},
        'TuneAzimuth':            {'label':'Tune azimuth',              'call':TunePositionAzimuth},
        'TuneAltitude':           {'label':'Tune altitude',             'call':TunePositionAltitude, 'break':True},
        'MctlLedsOff':            {'label':'Microcontroller LEDS off',  'call':MicrocontrollerLedsOff},
        'MctlLedsOn':             {'label':'Microcontroller LEDS on',   'call':MicrocontrollerLedsOn},
        'RestartMicrocontroller': {'label':'Restart microcontroller',   'call':RestartMicrocontroller, 'break':True},
        'TrackingOn':             {'label':'Tracking on',               'call':TrackingOn},
        'TrackingOff':            {'label':'Tracking off',              'call':TrackingOff},
        'ResetDriftTracking':     {'label':'Reset drift tracking',      'call':temp}
    }
    SubMenu = proceduremenu(SubMenuOptions,'Pilomar observation submenu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    # Run sub menu.
    SubMenu.Prompt()

# ------------------------------------------------------------------------------------------------------

def UpdateStorageStatus():
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
    MainLog.Log("Storage available=" + HRBytes(fb),terminal=False)
    return result

# ------------------------------------------------------------------------------------------------------

def UpdateCameraStatus():
    if Parameters.CameraEnabled: # Camera is enabled, report the selected exposure time.
        ObservationStatusWindow.FieldValue('CEN',Parameters.CameraEnabled,fg=OSW_TEXT_GOOD) # Green
        ObservationStatusWindow.FieldValue('EXP',str(CameraInUse.ExposureSeconds) + "s.",fg=OSW_TEXT_GOOD) # Exposure duration.
    else: # Camera is disabled, warn about this.
        ObservationStatusWindow.FieldValue('CEN',Parameters.CameraEnabled,fg=OSW_TEXT_POOR) # Red
        ObservationStatusWindow.FieldValue('EXP',str(CameraInUse.ExposureSeconds) + "s.",fg=OSW_TEXT_POOR) # Red - Blank out Exposure duration.
    if SensorInUse.OnChipCleanup: ObservationStatusWindow.FieldValue('OCC',SensorInUse.OnChipCleanup,fg=OSW_TEXT_POOR) # Red
    else: ObservationStatusWindow.FieldValue('OCC',SensorInUse.OnChipCleanup,fg=OSW_TEXT_GOOD) # Green
    return True

# ------------------------------------------------------------------------------------------------------

def UpdateCameraCaptureStatus():      
    if CameraInUse.CaptureStart != None: # Monitor the progress of the current photograph.
        if CameraInUse.CaptureEnd == None or CameraInUse.CaptureEnd <= CameraInUse.CaptureStart:
            # Latest image capture has started but not finished yet.
            ImageStatusWindow.FieldValue("CAMERASTATE","Started",fg=OSW_TEXT_GOOD)
            ImageStatusWindow.FieldValue("STATETIMES",str(CameraInUse.CaptureStart).split(".")[0])
            ImageAge = (NowUTC() - CameraInUse.CaptureStart).total_seconds()
            ImageStatusWindow.FieldValue("STATEAGE",HRSeconds(ImageAge))
        else: # Last image capture is complete. Waiting for next one to start.
            ImageStatusWindow.FieldValue("CAMERASTATE","Ended",fg=OSW_TEXT_GOOD)
            ImageStatusWindow.FieldValue("STATETIMES",str(CameraInUse.CaptureEnd).split(".")[0])
            ImageAge = (NowUTC() - CameraInUse.CaptureEnd).total_seconds()
            ImageStatusWindow.FieldValue("STATEAGE",HRSeconds(ImageAge))
    else: # No capture even started yet.
        ImageStatusWindow.FieldValue("CAMERASTATE","Pending",fg=OSW_TEXT_POOR)
        ImageStatusWindow.FieldValue("STATETIMES","")
        ImageStatusWindow.FieldValue("STATEAGE","")
    return True

# ------------------------------------------------------------------------------------------------------

# ------------------------------------------------------------------------------------------------------
        
def GeneratePreviewMovie(folder=None,filename=None):    
    MainLog.Log("Generating animation of observation previews...",terminal=False)
    print(textcolor.yellow("Generating animation of observation previews (if available)..."))
    print('May take some time...')
    if folder == None: # No folder named, default to current one.
        folder = FolderList.get('preview')
    sourcefilepattern = folder + 'preview_*.jpg'
    avifilename = folder + 'preview_' + CleanDatetimeString(str(NowUTC())) + '.mp4'
    if filename != None: # Override target filename.
        avifilename = filename
    # *Q* GLOB facility may disappear from later versions of ffmpeg, this will need revising when that happens.
    cmd = "ffmpeg -y -framerate 10 -pattern_type glob -i '" + sourcefilepattern + "' -vf scale='iw/2:ih/2' " + avifilename
    osCmd(cmd)
    print(textcolor.yellow("Generated"), avifilename)
    MainLog.Log("GeneratePreviewAvi: Completed animation of observation previews.",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------
   
def ReportObservationErrors():
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

def GetPositionAges():
    """ Return the age of the position measurements of each motor.
        Returns values in rounded whole seconds. """
    AzAge = AltAge = 0
    for i in MotorControls:
        if i.MotorName == 'azimuth':
            AzAge = i.PositionAge()
        else:
            AltAge = i.PositionAge()
    return AzAge, AltAge
    
# ------------------------------------------------------------------------------------------------------

def IncompleteObservationCheck():
    """ If the previous observation didn't complete,
        warn that camera positions may be incorrect
        and ask for permission to continue. """
    if os.path.exists(ObservationRunningFile):
        lines = ["The previous observation run did not complete properly.",
                 "This may mean that the camera positions are out of date",
                 "you may need to reset the camera altitude and azimuth."]
        textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.ORANGERED1)
        result = AskYesNo("Continue with this observation? [y/N]",default=False)
    else:
        result = True
    return result
    
# ------------------------------------------------------------------------------------------------------

def FlagObservationStart():
    """ Create a flag to show that ObservationRun has started. 
        This warns a following instance of the program in case this one fails 
        and leaves a mess. """
    MainLog.Log("FlagObservationStart(): Begin",terminal=False)
    with open(ObservationRunningFile,'w') as f:
        f.write("ObservationRun started " + str(NowUTC()) + " UTC\n")
    MainLog.Log("FlagObservationStart(): End",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def FlagObservationEnd():
    """ Remove the flag for a running ObservationRun because it's now completed. """
    MainLog.Log("FlagObservationEnd(): Begin",terminal=False)
    Session.SetMotorControlMode('idle') # This will suppress further trajectory info being sent.
    # Session.EndObservation() # Make sure that the observation is stopped! Even if the procedure crashed. This stops trajectories.
    # Send trajectory clear commands to the microcontroller.
    StopMotors() # Tell the microcontroller to stop and drop any existing trajectory immediately.
    if os.path.exists(ObservationRunningFile):
        os.remove(ObservationRunningFile)
    MainLog.Log("FlagObservationEnd(): End",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def ObservationRun():
    """ Perform an observation run. Take a set of photographs and keep the camera pointing at the target. 
        This is the core of the program. This is the main loop that tracks a target and captures photos. 
        It loops until 
            the set number of photos are reached,
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
                        It can also be done from the Miscellaneous Tools menu, or by pressing 'd' key during an observation.

        There are 4 threads operating at this point.
        - The main processing thread is this ObservationRun routine which has overall coordination and maintains the display/dashboard.
        - The Camera thread controls the camera activities.
        - The Mctl thread handles UART communication between the RPi and Microcontroller.
        - The Message thread deals with the actual messages received from the microcontroller and their responses.

                        """
    MainLog.Log("ObservationRun: Beginning observation.",terminal=False)
    
    RunObservation = True # We are OK to run the observation loop.
    observationresult = True # Was observation completed successfully?
    
    # Mark that an observation has started. If the program fails during an observation we can warn that 
    # camera position etc may be misaligned when it restarts.
    if IncompleteObservationCheck() == False:
        # There is an existing observation already running. Check this should proceed and warn that positions may be wrong.
        # The user chose to abandon this run.
        return False
    FlagObservationStart() # Mark that an observation run has started. Used this to warn if recovering from a failed run.
    
    # Don't start an observation if the target is not yet in range.
    if not Session.Target.Visible(): # The target isn't yet within the visibility range of the telescope.
        MainLog.Log("ObservationRun: The target is not within the visibility range of the telescope.",terminal=False)
        textcolor.TextBox(["The target is not visible to the telescope at the moment."],fg=textcolor.RED,bg=textcolor.BLACK)
        observationresult = False
        RunObservation = False # Not OK to run the observation loop.
        return observationresult # Quit the run.
        
    # Setup campaign information.
    DocumentSession() # Create text file listing the details of this session.
    DriftTracker.Reset() # Clear the drift tracking object for this new observation target.
    
    if Parameters.UseTracking: DriftWindow.Print(NowHMS() + ' Drift tracking is active.')
    else: DriftWindow.Print(NowHMS() + ' Drift tracking is inactive.')
    MainLog.ErrorList = [] # Clear out any old error summaries. We only want to report NEW instances.
    CamLog.ErrorList = [] # Clear out any old error summaries. We only want to report NEW instances.
    ReadyToObserve = False # We are not on-target yet.
    MainLog.Log('ObservationRun.initial: ReadyToObserve = False',terminal=False)
    temp = GetTerminalSize() # Note the size of the window. If it changes, we'll clear the screen.
    TerminalCols = temp[0] # Current screen columns.
    TerminalRows = temp[1] # Current screen rows.
    temp = colordisplay.GlobalWindowLimits() # How much screen space do all the windows required?
    if TerminalCols < temp[0] or TerminalRows < temp[1]:
        MainLog.Log("ObservationRun: Terminal", TerminalCols,"*",TerminalRows,", Windows",temp[0],"*",temp[1],terminal=False)
        MainLog.Log("ObservationRun: The terminal window is not big enough to display ALL available data. Stretch if possible.",terminal=False)
    obsstart = NowUTC() # Note the start of the observation run.
    PhotoCount = 0 # How many photos have been taken? We can exit the loop when the limit is reached. If Camera is disabled, it will loop forever.
    SlowLoopCounter = 0 # Count how often we have slow processing loops, it can be the sign of storage problems. 
    
    # Reset PhotoCount in the camera and wait for acknowledgement.
    # PhotoCount is maintained by the CameraThread, so we must communicate with it.
    StartCameraThread() # Fire up the camera thread if it's not running.
    time.sleep(0.5) # Pause briefly before sending the control message to the camera handler.
    ControlMessage = {'TimeStamp' : NowUTC(), 'PhotoCount' : 0} # *Q* Can be common attribute now rather than message queues.
    CameraControlQueue.put(ControlMessage) # Tell the camera to reset the photo count.
    Session.CameraTxCount += 1 # We sent another message to the camera.
    ControlMessage = {'Reset':True} # Tell the camera to reset buffers.
    CameraControlQueue.put(ControlMessage) # Tell the camera to reset the photo count.
    Session.CameraTxCount += 1 # We sent another message to the camera.
    # Wait for acknowledgement
    MainLog.Log("ObservationRun: Resetting camera PhotoCount.",terminal=False)
    ack = False # No acknowledgement from the camera yet.
    AckTimer = timer(600) # Set a timer for an acknowledgement. Camera is considered 'hung' or 'dead' after that.
    MainLog.Log("ObservationRun: Reset camera photo count and wait for acknowledgement.",terminal=False)
    while ack == False: # Loop until we receive acknowledgement.
        # Quit if the CameraThread has failed.
        if CameraThread.is_alive() == False: # If the camera thread is dead, then quit immediately.
            MainLog.Log("ObservationRun: CameraThread is not running!",level='error')
            print ("If the camera thread is dead you can try to restart it from the Camera Tools menu.")
            RunObservation = False # We cannot perform the observation. We will have to return to the menu.
            observationresult = False # Don't continue.
            return observationresult # Return to the menu.
        if CameraStatusQueue.empty() == False: # The CameraThread has sent a message that needs processing.
            StatusMessage = CameraStatusQueue.get() # Retrieve the first available message.
            Session.CameraRxCount += 1 # We received another message.
            if 'PhotoCountReset' in StatusMessage: # Is it acknowledging that the PhotoCount has been reset?
                ack = True # Acknowledged, OK to proceed.
                MainLog.Log("Reset camera PhotoCount acknowledged.",terminal=False)
            else: # The message is for some other purpose, we ignore it for now.
                MainLog.Log("Reset camera PhotoCount ignored " + str(StatusMessage),terminal=False)
        # If the camera has not acknowledged in a reasonable time, assume something is wrong and quit.
        if AckTimer.Due(): # Timeout on the acknowledgement.
            MainLog.Log("Reset camera Photocount. Acknowledgement timed out. Camera considered unresponsive.",level='error')
            lines = ["Camera is considered unresponsive.",
                     "The camera thread is still alive.",
                     "- The camera subsystem may have hung,",
                     "  in which case you should power cycle the RPi to clear the problem.",
                     "- The camera may have taken too long to initialize,",
                     "  in which case please try again.",
                     "- There may be an error from the camera handler,",
                     "  in which case check the camera log file or re-run in debug mode."]
            textcolor.TextBox(lines,fg=textcolor.RED,bg=textcolor.BLACK)
            observationresult = False # Don't continue.
            RunObservation = False # We cannot perform the observation. We will have to return to the menu.
            return observationresult # Return to the menu.
        if ack == False: 
            time.sleep(0.5) # Pause half a second before checking again.
            print("Waiting for camera acknowledgement.",int(AckTimer.Remaining()),"seconds left.",textcolor.cursorup())
    print(textcolor.clearforward()) 

    # Check that the UART communication with the motor microcontroller is alive.
    if MctlThread.is_alive() == False: # UART comms thread has failed.
        MainLog.Log("ObservationRun (startup): MctlThread is not running!",level='error')
        observationresult = False # Don't continue.
        RunObservation = False # We cannot perform the observation. We will have to return to the menu.
        return observationresult # Return to the menu.
    # Check that the message handler between the RPi and microcontroller is alive.
    if MessageThread.is_alive() == False: # Message handler thread has failed.
        MainLog.Log("ObservationRun (startup): MessageThread is not running!",level='error')
        observationresult = False # Don't continue.
        RunObservation = False # We cannot perform the observation. We will have to return to the menu.
        return observationresult # Return to the menu.

    # Set parameters used during the observation run.
    CameraAlt = None # The current altitude of the camera (reported by the motor microcontroller). Unknown at first.
    CameraAz = None # The current azimuth of the camera (reported by the motor microcontroller). Unknown at first.
    PrevAlt = None # The previous altitude of the telescope. Uninitialised until the main loop has started. 
    PrevReadyToObserve = False # We are not ready to observe until the whole telescope is synchronised and on target.
    ObservationStartUTC = None # The UTC timestamp when the image capture begins.
    LoopTimeList = [] # Show how quickly recent loops have completed. 
    cumulativelooptime = 0 # Cumulative total of all the loop times.
    cumulativeloopcount = 0 # Count of all the loops executed.
    MainLog.Log('ObservationRun: Initializing motorcontroller...',terminal=False)
    MainLog.Log('ObservationRun: Stopping any previous motor instructions.',terminal=False)
    if Parameters.ObservationResetsMctl: # Do we just force a full reset of the microcontroller to clean it up each time an observation starts?
        MainLog.Log('ObservationRun: Resetting microcontroller at start of observation (ObservationResetsMctl parameter)',terminal=False)
        Mctl.Reset(planned=True) # Perform a planned reset of the microcontroller to clear it ready for a new observation. 
        time.sleep(2) # Pause briefly before setting the microcontroller clock.
        Mctl.SetClock() # Set the clock on the microcontroller.
    else:
        StopMotors() # Clear any existing plan that the motors may have.
        Mctl.ReadFlush() # Flush any unprocessed messages. If a large backlog exists it can delay the initial move and make it look like a motor/comms problem.
    if Mctl.BytesReceived < 10: time.sleep(3) # Wait for microcontroller UART communication to get running.
    if Mctl.BytesReceived < 10: # Not much sign of activity from the microcontroller!
        MainLog.Log("ObservationRun: Microcontroller UART link does not appear to be communicating. Please check.",level='error',terminal=True)
        print("1) Is microcontroller installed?")
        print("2) Is microcontroller connected via UART pins / GPIO header?")
        print("3) Is microcontroller software installed?")
        print("4) Microcontroller connection via USB alone will not support UART communication.")
        observationresult = False # Don't continue.
        RunObservation = False # We cannot perform the observation. We will have to return to the menu.
        return observationresult # Return to the menu.
    if Parameters.InitialGoTo: # Does an observation run start with a GOTO?
        MainLog.Log('ObservationRun: Performing initial GOTO performed before creating trajectory.',terminal=False)
        az, alt = Session.Target.AzAltDegrees() # Calculations for target from observer's location.
        temp = GoToTarget(Session.Target) # Go directly to the target before starting the trajectory mechanism.
        if temp == False:
            MainLog.Log("ObservationRun: Initial GOTO failed.",level='error')
            temp = AskYesNo("Do you want to continue anyway? [y/N]",False)
            if not temp: return # Quit immediately.
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
    SessionWindow.Clear(immediate=False) # Clear old messages from the session window.
    MiscTimer = timer(240) # Slow changing miscellaneous details are updated according to this timer. Immediately due.
    DebugTimer = timer(120) # In debug mode, update summary status every 2 minutes.
    # After this point all messages to the terminal should respect WINDOW and DEBUG MODE selections, otherwise they get overwritten/corrupted.
    if Session.DebugMode: 
        # Do not clear the screen in debug mode. We don't want to lose error messages.
        print (textcolor.orange('In DEBUG MODE. The dashboard display is suppressed so that any errors are more clear.')) # In debug mode, nothing is displayed except error messages.
        print (textcolor.yellow("In DEBUG MODE. Press 'x' to quit, 'd' toggle debug, 'm' submenu, 'r' refresh.")) # In debug mode, nothing is displayed except error messages.
    else:
        # Not in debug mode. Specific window layout will be used to show information.
        # Any output from error messages or regular print() commands will be lost as the display frequently refreshes.
        ClearScreen() # Clear the screen and force window refresh.
    if Session.DebugMode:
        MainLog.Log('ObservationRun: (DebugMode) Starting main loop...')
    #keyboardcount = 0 # Count the iterations between keyboard scans.
    colordisplay.GlobalForceRedraw() # Force all window buffers to fully redraw initially.
    while RunObservation: # Main loop of the observation.

        MainLog.Log("ObservationRun: Loop starts",terminal=False)
        # Check for keyboard commands...
        MainLog.Log("ObservationRun: Check for keyboard input...",terminal=False)
        # *Q* The following keyboard scan uses the curses library. It can cause the terminal display to blink sometimes. Not cured yet.
        if KeyboardTimer.Due(): # It's time to scan the keyboard.
            keypress = Keyboard.Check().lower() # Non-blocking scan for keyboard input. 
        else:
            keypress = "" # Don't check keyboard this time round.
        if keypress != "": # Some keyboard input detected. 
            if ord(keypress) == 410: pass # Ignore the 410 character, it is associated with screen resizing.
        if keypress == "x" or keypress == chr(27): # Break with 'x' or 'esc' key.
            MainLog.Log("Keyboard interrupt: Terminating.",level='warning',terminal=False)
            ErrorWindow.Print(NowHMS() + ' Keyboard interrupt. Terminating observation.')
            observationresult = False # Don't continue.
            RunObservation = False # This will quit the loop and shut down the motors and camera.
        elif keypress == "m": # Submenu.
            MainLog.Log("Keyboard interrupt: Submenu selected.",terminal=False)
            ObservationSubmenu(drifttracker=DriftTracker) # Pass the drifttracker object because the submenu can access its methods.
            ClearScreen() # Clear screen afterwards.
        elif keypress == "t": # Turn drift tracking on/off.
            MainLog.Log("Keyboard interrupt: Toggle DriftTracking status.",terminal=False)
            Parameters.UseTracking = not Parameters.UseTracking # Toggle the value.
            if Parameters.UseTracking: 
                DriftWindow.Print(NowHMS() + ' Drift tracking ON.')
                MainLog.Log("Keyboard interrupt: Drift tracking ON.",terminal=False)
            else: 
                DriftWindow.Print(NowHMS() + ' Drift tracking OFF.')
                MainLog.Log("Keyboard interrupt: Drift tracking OFF.",terminal=False)
        elif keypress == "p": # Trigger immediate PREVIEW image.
            MainLog.Log("Keyboard interrupt: User requested immediate PREVIEW image.",terminal=False)
            PreviewTimer.Trigger() # Mark the 'preview' timer as Due already.
            DevWindow.Print(NowHMS() + ' Immediate PREVIEW requested.')
        elif keypress == "d": # Toggle debug mode.
            MainLog.Log("Keyboard interrupt: Toggle debug mode.",terminal=False)
            Parameters.DebugMode = not Parameters.DebugMode # Toggle the value.
            Session.DebugMode = Parameters.DebugMode # Tell the session about it too!
            MainLog.Log("Keyboard interrupt: DebugMode now", Parameters.DebugMode,terminal=False)
            ClearScreen() # Clear screen afterwards.
            if Session.DebugMode:
                print(textcolor.yellow("Debug mode ON."))
            else:
                print(textcolor.yellow("Debug mode OFF."))
        elif keypress == "r": # Refresh screen.
            MainLog.Log("Keyboard interrupt: Refresh selected.",terminal=False)
            ClearScreen() # Clear screen afterwards.
        # # Start fresh move/capture iteration.
        # If the window dimensions have changed, clear the screen and let it redraw automatically.
        if not Session.DebugMode: 
            temp = GetTerminalSize() # Note the size of the window. If it changes, we'll clear the screen.
            if TerminalCols != temp[0] or TerminalRows != temp[1]: # Screen size has changed. Trigger refresh.
                ClearScreen() # Clear screen afterwards.
                TerminalCols = temp[0] # Note the new display dimensions.
                TerminalRows = temp[1]
        MainLog.Log("ObservationRun: Check CameraThread is alive...",terminal=False)
        if CameraThread.is_alive() == False: # If the CameraThread has died, quit.
            MainLog.Log("ObservationRun: CameraThread (Camera handler) is not running!",level='error')
            CameraWindow.Print(NowHMS() + " CameraThread is not running.")
            observationresult = False # Don't continue.
            RunObservation = False # Observation cannot continue.
        MainLog.Log("ObservationRun: Check MessageThread (message handler) is alive...",terminal=False)
        if MessageThread.is_alive() == False: # If message handler thread has died, quit.
            MainLog.Log("ObservationRun: (loop) MessageThread is not running!",level='error')
            observationresult = False # Don't continue.
            RunObservation = False # Observation cannot continue.
        MainLog.Log("ObservationRun: Check MctlThread (UART comms) is alive...",terminal=False)
        if MctlThread.is_alive() == False: # If the motor microcontroller communication thread has died, quit.
            MainLog.Log("ObservationRun: (loop) MctlThread is not running!",level='error')
            observationresult = False # Don't continue.
            RunObservation = False # Observation cannot continue.
        MainLog.Log("ObservationRun: Check CameraStatusQueue...",terminal=False)
        if CameraStatusQueue.empty() == False: # The CameraThread has sent messages that need to be processed.
            StatusMessage = CameraStatusQueue.get() # Retrieve the first message in the queue.
            Session.CameraRxCount += 1 # We received another message from the camera.
            # Extract any useful information from the received messages.
            if 'PhotoCount' in StatusMessage: PhotoCount = StatusMessage['PhotoCount'] # Camera has updated the number of photographs taken during this run.
        MainLog.Log("ObservationRun: Calculate current target position...",terminal=False)
        # Calculate the current position of the target. This also updates the cached values, which remain valid for the duration of this loop.
        dtnow = NowUTC() # In datetime format. 
        ra, dec = Session.Target.RaDecDegrees() # Target's position. Right Ascension and Declination.
        az, alt = Session.Target.AzAltDegrees(updatespeed=True) # Target's position. Altitude and Azimuth from observer's location. Update angular velocity too.
        MainLog.Log("ObservationRun: Update ObservationStatusWindow...",terminal=False)
        ObservationDuration = (dtnow - obsstart).total_seconds() # How long has this observation run been running for?
        ObservationStatusWindow.FieldValue('TARGET',Session.Target.Name,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Update the target name. 
        ObservationStatusWindow.FieldValue('FOLDER',FolderList.get('session'),fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Which folder is the observation data saved in. 
        if ClockOffset != None: # The clock is not running in realtime.
            ObservationStatusWindow.FieldValue('CLOCK',str(NowUTC()).split("+")[0],fg=textcolor.WHITE,bg=textcolor.RED) # System clock in UTC. 
        else: # Clock IS running in realtime.
            ObservationStatusWindow.FieldValue('CLOCK',str(NowUTC()).split("+")[0],fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # System clock in UTC. 
        ObservationStatusWindow.FieldValue('DURATION',HRSeconds(ObservationDuration),fg=OSW_TEXT_GOOD) # How long has this observation been running.
        # Calculate storage available.    
        if not UpdateStorageStatus(): # Update storage space available, and decide if it's safe to continue.
            observationresult = False # Don't continue.
            RunObservation = False # Quit the observation run.
            MainLog.Log("ObservationRun: Insufficient storage space terminating the observation.",level="error")
        # Motor status.
#        if Parameters.MotorsEnabled: ObservationStatusWindow.FieldValue('MEN',Parameters.MotorsEnabled,fg=OSW_TEXT_GOOD) # Green
#        else: ObservationStatusWindow.FieldValue('MEN',Parameters.MotorsEnabled,fg=OSW_TEXT_BAD) # Red
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
        if Session.Target.Visible() == False: fgc = fgd = OSW_TEXT_BAD # Field colour if target is not visible. (Red)
        elif Session.Target.ApproachingLimit(): fgc = fgd = OSW_TEXT_POOR # Field colour if target is approaching limits. (Yellow)
        else: 
            fgc = OSW_TEXT_GOOD # Field colour if target is visible. (Green)
            fgd = OSW_TEXT_FG # Field colour if target is visible. (Green)
        dh, dm, ds = AngleToHMS(ra) # Convert target Right Ascension angle into hours, minutes, seconds.
        if Parameters.UseLiveLocation: # Use the live target location rather than the last reported camera position for image processing.
            CameraAz, CameraAlt = Session.Target.AzAltDegrees() # What is the alt/az location of the centre of the image?
            CameraLatestAlt, CameraLatestAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
        else: # Use the last reported camera position. Deprecated.
            CameraAlt, CameraAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
            CameraLatestAlt = CameraAlt
            CameraLatestAz = CameraAz
        EstimatedAlt, EstimatedAz = EstimatedAltAz() # Where is the camera estimated to be pointing at given it's latest speed?
        ObservationStatusWindow.FieldValue('CAMAZ',DisplayDegree(CameraLatestAz,15,symbol=DegreeSymbol),fg=fgc,bg=textcolor.BLACK) # Camera's last reported position.
        ObservationStatusWindow.FieldValue('CAMALT',DisplayDegree(CameraLatestAlt,15,symbol=DegreeSymbol),fg=fgc,bg=textcolor.BLACK) 
        ObservationStatusWindow.FieldValue('ESTAZ',DisplayDegree(EstimatedAz,15,symbol=DegreeSymbol),fg=fgd,bg=textcolor.BLACK) # Camera's estimated current position.
        ObservationStatusWindow.FieldValue('ESTALT',DisplayDegree(EstimatedAlt,15,symbol=DegreeSymbol),fg=fgd,bg=textcolor.BLACK) 
        ObservationStatusWindow.FieldValue('TARAZ',DisplayDegree(az,15,symbol=DegreeSymbol),fg=fgc,bg=textcolor.BLACK) # Current target position.
        ObservationStatusWindow.FieldValue('TARALT',DisplayDegree(alt,15,symbol=DegreeSymbol),fg=fgc,bg=textcolor.BLACK) 
        ObservationStatusWindow.FieldValue('COMP',CompassPoint(az),fg=fgc,bg=textcolor.BLACK) # Azimuth as compass point.
        ObservationStatusWindow.FieldValue('RA',DisplayHMS(dh,dm,ds,15),fg=OSW_TEXT_GOOD,bg=textcolor.BLACK) # RA and DEC of target.
        ObservationStatusWindow.FieldValue('DEC',DisplayDegree(dec,15,symbol=DegreeSymbol),fg=OSW_TEXT_GOOD,bg=textcolor.BLACK) 
        MainLog.Log("ObservationRun: Target: Acquired=",ReadyToObserve,", Alt=",alt,", Az=",az,", ra=",ra,", dec=",dec,", AltSpeed=",Session.Target.AltSpeed,", AzSpeed=",Session.Target.AzSpeed,terminal=False) 

        # If we're on target, then activate the camera (it runs in a separate thread until told to stop).
        if True: # Was Parameters.CameraEnabled:
            if PrevReadyToObserve != ReadyToObserve: # 'on target' status has changed.
                # It is always safe to turn OFF the camera.
                # But only turn the camera ON if the microcontroller reports that it has got AutonomousControl (ie a valid trajectory in place).
                if ReadyToObserve == False or Session.AutonomousControl or Session.Target.IsFixedPoint(): # Only change status if turning OFF or if AutonomousControl is ready, or it's a fixed point.
                    ControlMessage = {'TimeStamp' : NowUTC(), 'ReadyToObserve' : ReadyToObserve, 'BatchSize' : 1}
                    CameraControlQueue.put(ControlMessage) # Keep sending the CameraEnabled status to the camera.
                    Session.CameraTxCount += 1 # We sent another message to the camera.
                    if Session.DebugMode:
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
        # Calculate total accumulated image time.
        AccumulatedTime = PhotoCount * CameraInUse.ExposureSeconds
        ImageStatusWindow.FieldValue('ACCTIME',HRSeconds(AccumulatedTime),fg=OSW_TEXT_GOOD)
        if True: # Was Parameters.CameraEnabled:
            pceta = '' # Don't know the estimated completion time yet.
            if PhotoCount > 0 and ObservationStartUTC != None: # We can estimate when the batch of photographs will be completed.
                pcprogress = float(PhotoCount) / Parameters.BatchSize # Percentage of way through the image batch.
                if pcprogress > 0.0: # We've made some progress, so estimate the completion time.
                    pcelapsed = (NowUTC() - ObservationStartUTC).total_seconds() # Elapsed time so far (seconds).
                    pcend = ObservationStartUTC + timedelta(seconds = int(pcelapsed / pcprogress)) # Roughly when will the batch be completed?
                    pceta = str(pcend)[:16] # YYYY.MM.DD HH:MM
            ImageStatusWindow.FieldValue('RUN',str(PhotoCount) + " of " + str(Parameters.BatchSize),fg=OSW_TEXT_GOOD) 
            ImageStatusWindow.FieldValue('ETA',pceta,fg=OSW_TEXT_GOOD) 
        else:
            ImageStatusWindow.FieldValue('RUN',str(PhotoCount) + " of " + str(Parameters.BatchSize) + '(dis.)',fg=textcolor.RED1) # Red
            ImageStatusWindow.FieldValue('ETA','n/a',fg=OSW_TEXT_GOOD) 
        if GPIO.input(StopBCM) == 0: # Emergency stop pin on RPi has been grounded. 
            print(textcolor.red('STOP BUTTON: Break observation'))
            observationresult = False # Don't continue
            RunObservation = False # Quit loop.
        MainLog.Log("ObservationRun: Update ImageStatusWindow...",terminal=False)
        UpdateCameraCaptureStatus()
        # Explain what is in the 'last captured image' buffer.
        if CameraInUse.Image.ImageExists(): # openCV image buffer is loaded.
            if len(CameraInUse.Image.ImageBuffer.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            ImageStatusWindow.FieldValue("OCVIB","loaded " + HmsFromStamp(CameraInUse.LastImageDateTime) + " " + str(CameraInUse.Image.ImageBuffer.shape[0]).rjust(4) + "*" + str(CameraInUse.Image.ImageBuffer.shape[1]).rjust(4) + " " + fmt,fg=OSW_TEXT_GOOD)
        else:
            ImageStatusWindow.FieldValue("OCVIB","empty",fg=OSW_TEXT_POOR)
        # Explain the status of the TARGET tracking image.
        if DriftTracker.TargetImage.ImageExists(): # openCV image buffer is loaded.
            temp = "matched " + str(len(DriftTracker.TargetStarMatchList)) + " of " + str(DriftTracker.TargetImage.StarCount) + " stars"
            if len(DriftTracker.TargetImage.ImageBuffer.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            temp = str(DriftTracker.TargetImage.ImageBuffer.shape[0]).rjust(4) + "*" + str(DriftTracker.TargetImage.ImageBuffer.shape[1]).rjust(4) + " " + fmt + " " + temp
            ImageStatusWindow.FieldValue("DTI","loaded " + HmsFromStamp(DriftTracker.TargetTimeStamp) + " " + temp,fg=OSW_TEXT_GOOD)
        else: # No drift target image available.
            ImageStatusWindow.FieldValue("DTI","empty",fg=OSW_TEXT_POOR)
        # Explain the status of the LATEST tracking image.
        if DriftTracker.LatestImage.ImageExists(): # openCV image buffers are loaded.
            temp = "matched " + str(len(DriftTracker.LatestStarMatchList)) + " of " + str(DriftTracker.LatestImage.StarCount) + " stars"
            if len(DriftTracker.LatestImage.ImageBuffer.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            temp = str(DriftTracker.LatestImage.ImageBuffer.shape[0]).rjust(4) + "*" + str(DriftTracker.LatestImage.ImageBuffer.shape[1]).rjust(4) + " " + fmt + " " + temp
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
                line = str(i.LatestTuneSteps) + " steps at " + str(i.LatestTuneTime).split("+")[0] + " UTC"
            else: # This motor has not been tuned.
                line = 'None'
            if i.MotorName == 'azimuth':
                ImageStatusWindow.FieldValue("LAZT",line,fg=OSW_TEXT_GOOD)
            else:
                ImageStatusWindow.FieldValue("LALT",line,fg=OSW_TEXT_GOOD)
        
        if Session.DebugMode: # We're in debug mode, just summary status update.
            if DebugTimer.Due(): # It's time to publish a summary status.
                print (NowHMS() + " Target " + textcolor.white(Session.Target.Name) + " " + AzAltText(az,alt))
                print (NowHMS() + " Session images: " + ImageCount_Session()) # Count images in the current SESSION!
                for line in StorageStrings(): print (NowHMS() + line)
                print (NowHMS() + " Session: " + FolderList.get("session"))
                if ClockOffset != None: # Warn that tracking clock is not running in realtime.
                    print(textcolor.red(NowHMS() + " Tracking clock is offset to",str(NowUTC()).split('.')[0]))
        else: # Not in debug mode, update the color display.
            MainLog.Log("ObservationRun: Refresh display windows...",terminal=False)
            # Refresh status and debug windows.
            # These will draw if their allocated terminal space is available.
            ObservationStatusWindow.Display(TerminalRows,TerminalCols) # Refresh the actual display.
            ImageStatusWindow.Display(TerminalRows,TerminalCols)
            InstructionWindow.Display(TerminalRows,TerminalCols) # Display session status.
            # - Column 2
            ErrorWindow.Display(TerminalRows,TerminalCols) # Display latest error messages.
            Session.ShowRemoteStatus() # Update status measures in the window buffers.
            SessionWindow.Display(TerminalRows,TerminalCols) # Display instructions.
            MctlRxWindow.Display(TerminalRows,TerminalCols) # Display Microcontroller UART RX traffic.
            MctlTxWindow.Display(TerminalRows,TerminalCols) # Display Microcontroller UART TX traffic.
            CameraWindow.Display(TerminalRows,TerminalCols) # Display camera status.
            # - Column 3
            DriftWindow.Display(TerminalRows,TerminalCols) # Display drift calculation log.
            CameraTxWindow.Display(TerminalRows,TerminalCols) # Display Camera command TX traffic.
            CameraRxWindow.Display(TerminalRows,TerminalCols) # Display Camera command RX traffic.
            DevWindow.Display(TerminalRows,TerminalCols) # Display developer events messages.

        # Calculate how long this loop took to execute.
        ltts = (NowUTC() - dtnow).total_seconds() # How long did the loop take?
        cumulativelooptime += ltts # Total processing time of all loops.
        cumulativeloopcount += 1 # Number of loops.
        averagelooptime = cumulativelooptime / cumulativeloopcount # Average loop time.
        MainLog.Log("ObservationRun: Total LOOP time=" + str(round(ltts * 1000,3)) + "ms. Ave LOOP time=" + str(round(averagelooptime * 1000,3)) + "ms.",terminal=False)
        LoopTimeList.append(round(ltts,1)) # Add to the list of recent loop times.
        if ltts > 20: # Exceedingly long loop time. O/S is busy with something else! If frequent it can be a sign that the memory card is aging/fragmented/damaged. Time to reinstall.
            SlowLoopCounter += 1 # Increment the count of slow loops, if we get a lot, there's maybe a problem.
            # ErrorWindow.Print(NowHMS() + ' slow loop time ' + str(round(ltts,0)) + "s.")
            if SlowLoopCounter % 10 == 0:
                DevWindow.Print(NowHMS() + ' Detected ' + str(SlowLoopCounter) + ' slow loops.')
                # A lot of slow loops suggests that the O/S is getting distracted with other tasks.
                # It can be a sign that the memory card is aging and needs replacing.
        LoopTimeList = LoopTimeList[-10:] # Limit list to last 10 entries.

        # End of main ObservationRun loop.
        MainLog.Log("ObservationRun: End of main loop...",terminal=False)
        
    # Observation is over at this point.
    print(textcolor.clearforward()) # Clear the screen from the current location forward, makes the following messages easier to read.
    ReadyToObserve = False
    if True: # Was Parameters.CameraEnabled: # Tell the camera it is all over.
        ControlMessage = {'TimeStamp' : NowUTC(), 'ReadyToObserve' : False}
        CameraControlQueue.put(ControlMessage) # Keep sending the CameraEnabled status to the camera.
        Session.CameraTxCount += 1 # We sent another message to the camera.
        ShutdownCamera() # Wait for the camera thread to terminate.
    # Tell the motors it is all over now that the camera is completed. 
    StopMotors() # Tell the motors to immediately stop. 
    print ('\n' + textcolor.cursordown(10) + textcolor.clearforward()) # Move cursor below the ObservationRun display and clear the rest of the screen to make way for the menu.
    if Parameters.GeneratePreview: # Preview images were requested.
        if AskYesNo("Do you want to generate an AVI animation of the preview files? [y/N]",False): # We can generate a small animation of the observation from the preview images.
            GeneratePreviewMovie()
    ReportObservationErrors()

    textcolor.TextBox("The images are stored in " + FolderList.get('session'),fg=textcolor.YELLOW,bg=textcolor.BLACK)
        
    # End of observation...    
    Session.SetMotorControlMode('idle') # The motors should now be idle.
    FlagObservationEnd() # Mark that the observation run has completed successfully. This tells the next observationrun that all is OK. It's also called by the menu for safety.
    
    MainLog.Log("ObservationRun: end.",terminal=False)
    return observationresult

# ----------------------------------------------------------------------------------------------------- 


def DisableCleanup(): # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        print ("The Raspberry Pi HQ sensor performs some on-chip image cleanup.")
        print ("On-chip cleanup may degrade the raw image data.")
        print ("It is recommended to disable this feature for astrophotography.")
        print ("- You may get warning messages displayed by this action, they are generally OK to ignore.")
        if AskYesNo("Disable on-sensor cleanup? [y/N]",False):
            SensorInUse.DisableCleanup()
            Parameters.DisableCleanup = True
            FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
            DocumentSession()
            DriftTracker.Reset()

# ------------------------------------------------------------------------------------------------

def EnableCleanup(): # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        print ("The Raspberry Pi High Quality camera can perform some on-chip image cleanup.")
        print ("It is often disabled for astrophotography because it degrades the raw image data slightly.")
        print ("It is recommended to enable this for regular photography.")
        print ("- You may get warning messages displayed by this action, they are generally OK to ignore.")
        if AskYesNo("Enable on-sensor cleanup? [y/N]",False):
            Parameters.DisableCleanup = False
            SensorInUse.EnableCleanup()
            FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
            DocumentSession()
            DriftTracker.Reset()
    
# ------------------------------------------------------------------------------------------------------

def PositionStrings():
    """ Return a string listing the current motor positions. 
        For display purposes. """
    PS = " Camera:"
    for i in MotorControls:
        PS += " " + i.MotorName + ": " + str(i.AngleToStep(i.CurrentAngle)) + " (" + Deg3dp(i.CurrentAngle) + DegreeSymbol + ")"
    PS = " " + PS.strip()
    return [PS]

# ------------------------------------------------------------------------------------------------------

def TargetStrings(): 
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

def SensorStrings():
    """ Return a string showing the current sensor/image settings. """
    SS = " Sensor: Mode " + str(SensorInUse.Mode) + ", Dimensions " + str(SensorInUse.PixelWidth) + "x" + str(SensorInUse.PixelHeight)
    if SensorInUse.OnChipCleanup:
        SS += " OnChipCleanup enabled."
    else:
        SS += " OnChipCleanup disabled."
    return [SS]
    
# ------------------------------------------------------------------------------------------------------

def ExposureStrings():
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
    if ES != "": 
        returnlist.append(ES)
    return returnlist

# ------------------------------------------------------------------------------------------------------

def SessionStrings():
    """ Return a string listing current session details. """
    SS = " Session: " + FolderList.get("session")
    return [SS]
    
# ------------------------------------------------------------------------------------------------------

def ImageStrings():
    """ Return a string listing current session's images. """
    returnlist = []
    SS = " Campaign images: " + ImageCount_Campaign() # Count images in the CAMPAIGN! (Multiple sessions)
    returnlist.append(SS)
    SS = " Session images: " + ImageCount_Session() # Count images in the current SESSION!
    returnlist.append(SS)
    return returnlist
    
# ------------------------------------------------------------------------------------------------------

def StorageStrings():
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

def ProgramStartStrings():
    """ Return a string listing when the program started. """
    delta = HRSeconds((NowUTC() - Session.ProgramStartTime).total_seconds())
    #delta = HRSeconds(delta)
    PS = " Program started: " + str(Session.ProgramStartTime).split('.')[0] + " UTC        (" + delta + ")"
    return [PS]

# ------------------------------------------------------------------------------------------------------

def MicrocontrollerStrings():
    """ Return a string listing microcontroller status. """
    PS = " Microcontroller: RPi>Mctl " + HRBytes(Mctl.BytesSent) + ", Mctl>RPi " + HRBytes(Mctl.BytesReceived) + "."
    return [PS]
    
# ------------------------------------------------------------------------------------------------------

def DocumentSession():
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
        f.write("Sensor mode\t" + str(SensorInUse.Mode) + "\n")
        f.write("Image width\t" + str(SensorInUse.PixelWidth) + "\n")
        f.write("Image height\t" + str(SensorInUse.PixelHeight) + "\n")
        f.write("Maximum exposure time\t" + str(SensorInUse.MaxExposureSeconds) + "seconds\n")
        f.write("Sensor type\t" + SensorInUse.Type + "\n")
        f.write("Pixels per FOV degree width\t" + str(CameraInUse.PixelsPerFovDegreeWidth) + "\n")
        f.write("Pixels per FOV degree height\t" + str(CameraInUse.PixelsPerFovDegreeHeight) + "\n")
        f.write("Seconds per pixel\t" + str(CameraInUse.SecondsPerPixel) + "\n")
        f.write("Infra red filter\t" + str(Parameters.IRFilter) + "\n")
        f.write("Light pollution filter\t" + str(Parameters.PollutionFilter) + "\n")
    # Append key values to 'recent target list'. This is useful if recovering from system failure, or resuming a previous observation at a later date.
    # When selecting a new target, this recent target list is offered as a short-cut to duplicate previous observations.
    with open(HistoryFile,'a') as f:
        f.write(str(NowUTC()).split('.')[0] + "\t" + \
                Session.Target.Name + "\t" + \
                Session.Target.SearchGroup + "\t" + \
                Session.Target.SearchTerm + "\t" + \
                str(float(CameraInUse.ExposureSeconds)) + "\t" + \
                str(SensorInUse.Mode) + "\n")
    return

# ------------------------------------------------------------------------------------------------------

def SummariseObservationParameters():
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

def FlushCommandQueue(): # For menu
    Mctl.WriteFlush(send=False)
    Mctl.ReadFlush()

# ------------------------------------------------------------------------------------------------------

def ReloadParameters(): # For menu
    global Parameters
    Parameters = parameters(filename=ParameterFileName,log=MainLog.Log) # Create and load parameters.
    Parameters.Show()

# ------------------------------------------------------------------------------------------------------

def ShowParameters(): # For menu
    Parameters.Show()

# ------------------------------------------------------------------------------------------------------

def EditParameters(): # For menu
    global Parameters
    Parameters.SaveAttributes(Parameters.ParamFileName) # Save current values.
    osCmd("cp " + Parameters.ParamFileName + " " + Parameters.ParamFileName.split(".")[0] + "_" + CleanDatetimeString(UtcTimeStamp()) + ".bak") # Backup current values.
    os.system("nano " + Parameters.ParamFileName) # Edit
    Parameters = parameters(filename=ParameterFileName,log=MainLog.Log) # Create and load parameters.
    Parameters.Show()
    lines = ["If  you  have  changed  values  in the  parameter  file",
             "you should restart this program and the microcontroller",
             "to be sure that all changes take effect."]
    textcolor.TextBox(line,fg=textcolor.YELLOW,bg=textcolor.BLACK)    

# ------------------------------------------------------------------------------------------------------

def EditTargetHistory(): # For menu
    osCmd("cp " + HistoryFile + " " + HistoryFile.split(".")[0] + "_" + CleanDatetimeString(UtcTimeStamp()) + ".bak") # Backup current values
    os.system("nano " + HistoryFile) # Edit

# ------------------------------------------------------------------------------------------------------

def DebugModeOff(): # For menu
    Parameters.DebugMode = False # Full dynamic display enabled.
    Session.DebugMode = Parameters.DebugMode
    MainLog.Log("ObservationRun debug mode disabled.")
    print(textcolor.yellow("The full dashboard will be shown. This refreshes very quickly."))
    print(textcolor.yellow("This will make it difficult to see any error messages generated by the software."))
    print(textcolor.yellow("If you have problems that need to be investigated, please turn DebugMode back on."))

# ------------------------------------------------------------------------------------------------------

def DebugModeOn(): # For menu
    Parameters.DebugMode = True # Dynamic display disabled. Error messages only shown.
    Session.DebugMode = Parameters.DebugMode 
    MainLog.Log("ObservationRun debug mode activated.")
    print(textcolor.yellow("The dashboard will not be shown, a simpler list of actions will appear instead."))
    print(textcolor.yellow("This will make it easier to see any error messages generated by the software."))

# ------------------------------------------------------------------------------------------------------

def SelectTarget(): # For menu
    global FolderList
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        Session.Target = TargetSelection() # Returns a Target class.
        CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
        FolderList = CreateFolderList(Session.Target.Name,CameraInUse.ExposureSeconds) # This creates a list of folders to use, and initializes them.
        DocumentSession()
        DriftTracker.Reset()
        ProgramStatus() # Show current situation of the telescope and target.

# ------------------------------------------------------------------------------------------------------

def BeginObservation(): # For menu
    print(textcolor.yellow(SummariseObservationParameters()))
    if AskYesNo('OK to start observation? [y/N]',default=False):
        ObservationRun()

# ------------------------------------------------------------------------------------------------------

def MenuGoToTarget(): # For menu
    GoToTarget(Session.Target)

# ------------------------------------------------------------------------------------------------------

def MenuSetBatchSize(): # For menu
    Parameters.BatchSize = SetBatchSize(Parameters.BatchSize)

# ------------------------------------------------------------------------------------------------------

def MenuSetControlBatchSize(): # For menu
    Parameters.ControlBatchSize = SetControlBatchSize(Parameters.ControlBatchSize)

# ------------------------------------------------------------------------------------------------------

def MenuDarkSet(): # For menu
    StartCameraThread()
    CameraInUse.DarkSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuFlatSet(): # For menu            
    StartCameraThread()
    CameraInUse.FlatSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuBiasSet(): # For menu
    StartCameraThread()
    CameraInUse.BiasSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuDarkFlatSet(): # For menu
    StartCameraThread()
    CameraInUse.DarkFlatSet(batch_size=Parameters.ControlBatchSize)
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuManualPreview(): # For Menu
    StartCameraThread()
    ManualPreview() # *Q* should be within AstroCamera class eventually. Some work needed first though.
    ShutdownCamera()

# ------------------------------------------------------------------------------------------------------

def MenuAutoPhoto(): # For menu
    if Parameters.CameraEnabled:
        StartCameraThread()
        CameraInUse.AutoPhoto() # Take a series of completely automatic exposures (for focus testing etc in daylight).
        ShutdownCamera()
    else:
        MainLog.Log("MenuAutoPhoto: Camera is disabled. Cannot capture images.",level='warning',terminal=True)

# ------------------------------------------------------------------------------------------------------

def ProcessImageFiles(): # For menu
    CameraInUse.ProcessImageFiles()
        
# ------------------------------------------------------------------------------------------------------

def MenuShutdownMessage():
    print(textcolor.yellow("Shutdown message handler."))
    ShutdownMessage()
    
# ------------------------------------------------------------------------------------------------------

def MenuStartMessage():
    print(textcolor.yellow("Start message handler."))
    StartMessageThread()

# ------------------------------------------------------------------------------------------------------

def CommunicationWarnings():
    """ Quick check that communication is up and running.
        Report to the terminal if not. """    
    try:
        temp = int((NowUTC() - Mctl.LastRxTime).total_seconds())
        if temp >= Parameters.MctlCommsTimeout: # Line has been open long enough to expect some traffic.
            print(textcolor.fgbgcolor(textcolor.WHITE,textcolor.ORANGERED1," WARNING: No data received from microcontroller for " + str(temp) + " seconds. "))
    except Exception as e:
        MainLog.Log("CommunicationWarnings(): Failed to calculate Rx age.",Mctl.LineOpenedTime,Parameters.MctlCommsTimeout,terminal=False)
        MainLog.RecordTraceback(None) # Record the stack at this point.
    try:
        if Mctl.BytesReceived <= 0 or Mctl.LinesReceived <= 0:
            print(textcolor.yellow("No data received from microcontroller since last startup."))
    except Exception as e:
        MainLog.Log("CommunicationWarnings(): Failed to report Rx volume.",Mctl.BytesReceived,Mctl.LinesReceived,terminal=False)
        MainLog.RecordTraceback(None) # Record the stack at this point.

# ------------------------------------------------------------------------------------------------------

def ProgramStatus(): # For menu
    """ Show a status summary of the telescope and session.
        What's the target?
        What are the settings?
        What's the current position of the telescope? """
    listlines = []
    temp = (" " + ProgramTitle.upper() + " " + VERSION + " " + (str(NowUTC()).split('.')[0]) + " UTC")
    if Session.DebugMode: # In debug mode, warn the user.
        temp += ' (DEBUG MODE)'
    listlines.extend([temp])
    listlines.extend(TargetStrings())
    listlines.extend([RiseSetString(Session.Target)])
    listlines.extend(SessionStrings())
    listlines.extend(PositionStrings())
    listlines.extend(ExposureStrings())
    listlines.extend(ImageStrings())
    listlines.extend(SensorStrings())
    listlines.extend(StorageStrings())
    listlines.extend(ProgramStartStrings())
    listlines.extend(MicrocontrollerStrings())
    temp = " Observer's location: Latitude: " + Deg3dp(Parameters._HomeLatVal,DegreeSymbol) + " Longitude: " + Deg3dp(Parameters._HomeLonVal,DegreeSymbol)
    listlines.extend([temp])
    textcolor.TextBox(listlines,fg=MENU_SUBTITLE_FG,bg=MENU_SUBTITLE_BG)
    CommunicationWarnings() # Add some warnings if the communication doesn't look healthy.

# ------------------------------------------------------------------------------------------------------

def ScanForMeteors(): # For menu
    print (textcolor.yellow("This will scan all available 'light' image files for potential meteor trails."))
    print (textcolor.yellow("Press 'x' to quit"))
    CameraInUse.MeteorFileScan() # Scan all available 'light' jpg files for potential meteor traces. Ignore the returned list of filenames.
    
# ------------------------------------------------------------------------------------------------------

def ShowFolderList():
    """ Show FolderList contents. """
    for key,value in FolderList.items():
        print(key.rjust(20," "),":",value)
    
# ------------------------------------------------------------------------------------------------------

def ZipCommsLog():
    """ Extract communication summary from the main log file and zip it. """
    MainLog.Log("ZipCommsLog",terminal=True)
    zipfile = MainLog.PackageSearchResult('RPi received|RPi queueing|warning|error',ignorecase=True)
    MainLog.Log("ZipCommsLog: Generated",zipfile,terminal=True)

# ------------------------------------------------------------------------------------------------------

def ZipTrajectoryLog():
    MainLog.Log("ZipTrajectoryLog",terminal=True)
    zipfile = MainLog.PackageSearchResult('RPi queueing.*): trajectory ',ignorecase=True)
    MainLog.Log("ZipTrajectoryLog: Generated",zipfile,terminal=True)

# ------------------------------------------------------------------------------------------------------

def MonitorComms():
    """ For a period mirror microcontroller communication to the terminal. """
    print(textcolor.yellow("MonitorComms"))
    print("This will show communication traffic.")
    print("Press 'x' to return to the menu.")
    print("Press 'r' to reset microcontroller.")
    print("Press 'f' to flash LED Yellow.")
    if Mctl.PowerIsOn() or Mctl.PoweredByUsb: # Warn if the microcontroller is not powered. 
        print(textcolor.green("The microcontroller power is ON. Communication should be running."))
    else:
        print(textcolor.red("The microcontroller is OFF. No communication expected."))
    Mctl.StartMonitor() # Turn on replication to the terminal.
    while True:
        keypress = Keyboard.Check().lower()
        if keypress == 'x': break
        elif keypress == 'r': # Reset microcontroller. 
            print(textcolor.yellow("Restarting microcontroller."))
            RestartMicrocontroller() # Force the microcontroller to restart.
        elif keypress == 'f': # Flash RGB LED YELLOW for 1 second.
            print(textcolor.yellow("Sending YELLOW flash to microcontroller LED."))
            Mctl.Write("set rgb " + CleanDatetimeString(str(NowUTC())) + " y y n 1")
        time.sleep(0.5)
    Mctl.EndMonitor() # Turn off replication to the terminal.

# ------------------------------------------------------------------------------------------------------

def ShowMotorStatus():
    """ Show the status of all the motors. """
    print(textcolor.yellow("Motor status"))
    
    #print("    Motors enabled:",Parameters.MotorsEnabled)
    print("  Backlash enabled:",Parameters.BacklashEnabled)
    print("   Fault sensitive:",Parameters.FaultSensitive)
    #print(" Use microstepping:",Parameters.UseMicrostepping)
    print("Motor status delay:",Parameters.MotorStatusDelay,"s")
    print("    Optimise moves:",Parameters.OptimiseMoves)
    print(" ")
    for i in MotorControls:
        i.ShowMotorStatus()

# ------------------------------------------------------------------------------------------------------

def TrackingStatus():
    """ Show tracking parameters and results.
        This is to help tuning the tracking parameters.
        It is highly likely that every instance of the telescope will need
        different parameter settings to optimise the tracking depending upon
        the camera/lens in use and the quality of the sky visible.
        This shows the key parameters that affect the way tracking works to 
        help you tune the values.                                                   """
    print(textcolor.yellow("Tracking status"))
    print("This shows tracking system parameters and any recent tracking results.")
    print("Use this information to finetune tracking performance.")
    print("")
    
    if Parameters.UseTracking: print(textcolor.green("Tracking is currently enabled."),textcolor.blue("(UseTracking parameter)"))
    else: print(textcolor.red("Tracking is currently disabled."),textcolor.blue("(UseTracking parameter)"))
    print("")

    print(textcolor.white("Camera"))
    print("      Image size:",CameraInUse.Sensor.PixelWidth,"w","*",CameraInUse.Sensor.PixelHeight,"h","pixels")
    print("            Lens:",CameraInUse.Lens.Length,"mm","(35mm equiv:",CameraInUse.Lens.EquivLength,"mm)")
    print("   Field of View:","Horizontal",Deg3dp(CameraInUse.Lens.FovHorizontal,DegreeSymbol),
                              "Vertical",Deg3dp(CameraInUse.Lens.FovVertical,DegreeSymbol))
    print("")

    print(textcolor.white("Target parameters (calculated image)"))
    if Parameters.LocalStarsMagnitude < Parameters.TargetMinMagnitude:
        bNote = textcolor.red("Clipped to mag",Parameters.LocalStarsMagnitude,"in Hipparcos selection.")
    else:
        bNote = ""
    print("      Brightness: mag",Parameters.TargetMinMagnitude,textcolor.blue("(TargetMinMagnitude parameter)"),bNote)
    print("                  mag",Parameters.TargetMinMagnitude - 0.2,"would generate fewer stars.")
    print("                  mag",Parameters.TargetMinMagnitude + 0.2,"would generate more stars.")
    print(" Hipparcos limit: mag",Parameters.LocalStarsMagnitude,textcolor.blue("(LocalStarsMagnitude parameter)")) # Cannot exceed this value without reloading LocalStars list.
    print("")

    print(textcolor.white("Latest parameters (captured image)"))
    print("   Exposure time:",Parameters.TrackingExposureSeconds,"s",textcolor.blue("(TrackingExposureSeconds parameter)"))
    print("                 ",round(Parameters.TrackingExposureSeconds / 2,1),"s would capture fewer stars.")
    print("                 ",round(Parameters.TrackingExposureSeconds * 2,1),"s would capture more stars.")
    print("")
    
    # Results of latest drift calculation.
    print(textcolor.white("Drift calculation"))
    sm_fg = OSW_TEXT_GOOD
    ltemp = len(DriftTracker.TargetStarMatchList)
    if ltemp < 1: sm_fg = OSW_TEXT_BAD
    elif ltemp < 10: sm_fg = OSW_TEXT_POOR
    print("     Star matches:",textcolor.fgbgcolor(sm_fg,textcolor.BLACK,str(ltemp)))
    if DriftTracker.dx != None:
        print("  Drift dx,dy,rot:",round(DriftTracker.dx,0),",",round(DriftTracker.dy,0),",",Deg3dp(DriftTracker.rotation,DegreeSymbol))
    else:
        print("  Drift dx,dy,rot: NOT CALCULATED YET.")
    print("")

    print(textcolor.white("Star generation/detection"))
    # Star detection.
    print("  Enhance images:",Parameters.LatestTrackingFilter,textcolor.blue("(LatestTrackingFilter parameter)"))
    #if Parameters.PrepImagesForTracking: # What does this parameter do?
    #    print("                     The target image is generated in grayscale.")
    #    print("                     The latest image is converted to grayscale and contrast enhanced.")
    #else:
    #    print("                     The target image is generated in color.")
    #    print("                     The latest image has no enhancement.")
    #print("Apply Urban filter:",Parameters.TrackingUrbanFilter,textcolor.blue("(TrackingUrbanFilter parameter)"))
    #if Parameters.TrackingUrbanFilter: # What does this parameter do?
    #    print("                     The latest image has general haze reduced.")
    #    print("                     The latest image has contrast enhanced.")
    #else:
    #    print("                     The latest image has no haze reduction.")
    #    print("                     The latest image has no contrast enhancement.")
    
    # Processing of the TARGET image.
    print("     Target image: Loaded",DriftTracker.TargetImage.ImageExists(),DriftTracker.TargetTimeStamp)
    BadThreshold = 50
    PoorThreshold = 70
    #hs,vs,imgs = CalculateStarSpread(DriftTracker.TargetImage) # Calculate the spread of stars in the target image.
    DriftTracker.TargetImage.CalculateStarSpread() # Calculate the spread of stars in the target image.
    hs = round(DriftTracker.TargetImage.HorizontalSpread,0)
    vs = round(DriftTracker.TargetImage.VerticalSpread,0)
    imgs = round(DriftTracker.TargetImage.AreaSpread,0)
    hs_fg = vs_fg = imgs_fg = OSW_TEXT_GOOD # What color to show for GOOD star spread percentages?
    if hs < BadThreshold: hs_fg = OSW_TEXT_BAD # Horizontal star spread is BAD.
    elif hs < PoorThreshold: hs_fg = OSW_TEXT_POOR # Horizontal star spread is POOR.
    if vs < BadThreshold: vs_fg = OSW_TEXT_BAD # Vertical star spread is BAD.
    elif vs < PoorThreshold: vs_fg = OSW_TEXT_POOR # Vertical star spread is POOR.
    if imgs < BadThreshold: imgs_fg = OSW_TEXT_BAD # Area star spread is BAD.
    elif imgs < PoorThreshold: imgs_fg = OSW_TEXT_POOR # Area star spread is POOR.
    print("       Star count:",DriftTracker.TargetImage.StarCount,"Spread:",
          "Horiz",textcolor.fgbgcolor(hs_fg,textcolor.BLACK,str(hs)),
          "%, Vert",textcolor.fgbgcolor(vs_fg,textcolor.BLACK,str(vs)),
          "%, Area",textcolor.fgbgcolor(imgs_fg,textcolor.BLACK,str(imgs)),"%")
          
    # Processing of the LATEST image.          
    print("     Latest image: Loaded",DriftTracker.LatestImage.ImageExists(),DriftTracker.LatestTimeStamp)
    #hs,vs,imgs = CalculateStarSpread(DriftTracker.LatestImage) # Calculate the spread of stars in the latest image.
    DriftTracker.LatestImage.CalculateStarSpread() # Calculate the spread of stars in the target image.
    hs = round(DriftTracker.LatestImage.HorizontalSpread,0)
    vs = round(DriftTracker.LatestImage.VerticalSpread,0)
    imgs = round(DriftTracker.LatestImage.AreaSpread,0)
    hs_fg = vs_fg = imgs_fg = OSW_TEXT_GOOD # What color to show for GOOD star spread percentages?
    if hs < BadThreshold: hs_fg = OSW_TEXT_BAD # Horizontal star spread is BAD.
    elif hs < PoorThreshold: hs_fg = OSW_TEXT_POOR # Horizontal star spread is POOR.
    if vs < BadThreshold: vs_fg = OSW_TEXT_BAD # Vertical star spread is BAD.
    elif vs < PoorThreshold: vs_fg = OSW_TEXT_POOR # Vertical star spread is POOR.
    if imgs < BadThreshold: imgs_fg = OSW_TEXT_BAD # Area star spread is BAD.
    elif imgs < PoorThreshold: imgs_fg = OSW_TEXT_POOR # Area star spread is POOR.
    print("       Star count:",DriftTracker.LatestImage.StarCount,"Spread:",
          "Horiz",textcolor.fgbgcolor(hs_fg,textcolor.BLACK,str(hs)),
          "%, Vert",textcolor.fgbgcolor(vs_fg,textcolor.BLACK,str(vs)),
          "%, Area",textcolor.fgbgcolor(imgs_fg,textcolor.BLACK,str(imgs)),"%")

# ------------------------------------------------------------------------------------------------------

def MicrocontrollerStatus():
    """ Display information about the microcontroller and communications. """
    print(textcolor.yellow("Microcontroller status"))
    
    print("Board type:",Parameters.BoardType)
    print("Supports Voltmeter:",Mctl.SupportsVoltmeter) # Motorcontrol voltage will be NOT monitored on adc0.
    if Session.ValidControllerVersion():
        print("Microcontroller program version:",textcolor.green(Session.ControllerVersion),"(good)") # We like this version.
    else:
        print("Microcontroller program version:",textcolor.red(Session.ControllerVersion),"(check)") # We don't trust this version.
    print("Acceptable microcontroller versions:",ACCEPTABLECONTROLLERVERSIONS) # What microcontroller versions are acceptable?
    print("Reset PIN:",Mctl.ResetPin) # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
    print("Received line queue:",len(Mctl.Lines)) # No lines received yet.
    print("Write chunk size:",Mctl.WriteChunkBytes,"bytes")
    print("Write chunk gap:",Mctl.WriteChunkSeconds,"s") # Seconds between chunks written to microcontroller.
    print("Current receiving line:",Mctl.InputLine)
    print("Write queue length:",len(Mctl.WriteQueue))
    temp = str(Mctl.LinesReceived)
    if Mctl.LinesReceived < 1:
        temp = textcolor.red(temp) # Highlight in RED that nothing received.
    print("Lines received:",temp)
    print("Lines sent:",Mctl.LinesSent)
    temp = str(Mctl.BytesReceived)
    if Mctl.BytesReceived < 1:
        temp = textcolor.red(temp) # Highlight in RED that nothing received.
    print("Bytes received:",temp)
    print("Bytes sent",Mctl.BytesSent)
    print("Monitor communications:",Mctl.PrintComms) # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
    print("LEDs active:",Mctl.LedStatus) # LEDS on by default.
    print("UART line opened:",str(Mctl.LineOpenedTime).split('.')[0],"UTC")
    print("UART Last Tx:",str(Mctl.LastTxTime).split('.')[0],"UTC") # When was data last sent?
    temp = str(Mctl.LastRxTime).split('.')[0]
    if Mctl.LastRxTime == None or Mctl.LastRxTime <= Mctl.LineOpenedTime: # Nothing received.
        temp = textcolor.red(temp) # Highlight nothing received.
    print("UART Last Rx:",temp,"UTC") # When was data last received?
    temp = str(Mctl.RxErrors)
    if Mctl.RxErrors > 10:
        temp = textcolor.red(temp) # Lots of errors.
    elif Mctl.RxErrors > 0:
        temp = textcolor.yellow(temp) # A few errors.
    print("UART Rx errors:",temp)
    print("Comms timeout:",Mctl.CommsTimeout,"s") # Seconds. microcontroller is restarted if no data received after this period.
    temp = str(Mctl.ForcedRestarts)
    if Mctl.ForcedRestarts > 4:
        temp = textcolor.red(temp)
    elif Mctl.ForcedRestarts > 0:
        temp = textcolor.yellow(temp)
    print("Forced restarts:",temp) # How many restarts have been forced by this software?
    temp = str(Mctl.RemoteRestarts)
    if Mctl.RemoteRestarts > 4:
        temp = textcolor.red(temp)
    elif Mctl.RemoteRestarts > 0:
        temp = textcolor.yellow(temp)
    print("Remote restarts:",temp) # How many restarts have been registered by the remote device itself?
    temp = str(Mctl.ResetAttempts)
    if Mctl.ResetAttempts > 4:
        temp = textcolor.red(temp)
    elif Mctl.ResetAttempts > 0:
        temp = textcolor.yellow(temp)
    print("Reset attempts:",temp) # Increment for each sequential attempt to reset communication with the remote microcontroller board.
    print("Powered by USB:",Mctl.PoweredByUsb) # Don't allow GPIO power pin to be used.
    if Mctl.DeviceFailure: temp = textcolor.red(str(Mctl.DeviceFailure))
    else: temp = str(Mctl.DeviceFailure)
    print("Device failure:",temp) # Set to TRUE if device seems to be irrecoverably lost.
    print("Write queue prohibit:",Mctl.WriteProhibited) # OK to add to the write queue.
    if Session.MctlExceptionCount != 0: # The microcontroller has handled some exceptions.
        print("Exceptions handled:",textcolor.yellow(Session.MctlExceptionCount))
    else: # No exceptions have been caught by the microcontroller.
        print("Exceptions handled:",Session.MctlExceptionCount)
    print("Outbound message counter:",Mctl.SendId) # Incremental counter, the message number being sent to the microcontroller.
    
# ------------------------------------------------------------------------------------------------------

def AboutCamera():
    """ Display information about the camera. """
    print(textcolor.yellow("About Camera"))
    
    print(textcolor.white(" O/S"))
    print("  CameraDriver:",CameraDriver,"(",OS_name,")")

    print(textcolor.white(" Sensor"))
    print("  Sensor width:",SensorInUse.PixelWidth,"px")
    print("  Sensor height:",SensorInUse.PixelHeight,"px")
    print("  Max exposure:",SensorInUse.MaxExposureSeconds,"s")
    print("  Min exposure:",SensorInUse.MinExposureSeconds,"s")
    print("  Sensor type:",SensorInUse.Type)
    print("  Sensor ID:",SensorInUse.ID)
    print("  Sensor mode:",SensorInUse.Mode)
    print("  On chip cleanup:",SensorInUse.OnChipCleanup)
    print("  Infra red filter:",Parameters.IRFilter) # Is Infra Red filter fitted?

    print(textcolor.white(" Lens"))
    print("  Base focal length:",LensInUse.BaseLength,"mm (before converters)")
    print("  Focal length:",LensInUse.Length,"mm (including converters)")
    print("  35mm equivalent focal length:",LensInUse.EquivLength,"mm")
    print("  Horizontal Field of View:",LensInUse.FovHorizontal,DegreeSymbol)
    print("  Vertical Field of View:",LensInUse.FovVertical,DegreeSymbol)
    print("  Field of View:",LensInUse.Fov,DegreeSymbol)
    print("  Aperture:","f",LensInUse.Aperture)
    print("  Pollution filter:",Parameters.PollutionFilter) # Is light pollution filter fitted?
    
    print(textcolor.white(" Camera"))
    if Parameters.CameraEnabled:
        print("  Camera enabled:",textcolor.green(Parameters.CameraEnabled))
    else:
        print("  Camera enabled:",textcolor.red(Parameters.CameraEnabled))
    print("  Exposure time:",CameraInUse.ExposureSeconds,"s")
    print("  Tracking exposure time:",CameraInUse.TrackingExposureSeconds,"s")
    print("  Pixels per FoV degree width:",CameraInUse.PixelsPerFovDegreeWidth)
    print("  Pixels per FoV degree height:",CameraInUse.PixelsPerFovDegreeHeight)
    print("  Pixel FoV width:",round(CameraInUse.PixelFovWidth,4),DegreeSymbol)
    print("  Pixel FoV height:",round(CameraInUse.PixelFovHeight,4),DegreeSymbol)
    print("  Motion:",round(CameraInUse.SecondsPerPixel,4),"s/px")

    print(textcolor.white(" Command templates"))
    print("  Light:",Parameters.CameraLightCommand)
    print("  Dark:",Parameters.CameraDarkCommand)
    print("  Bias/Offset:",Parameters.CameraBiasCommand)
    print("  Flat:",Parameters.CameraFlatCommand)
    print("  Dark flat:",Parameters.CameraDarkFlatCommand)
    print("  Auto:",Parameters.CameraAutoCommand)
    print("  Tracking:",Parameters.CameraTrackingCommand)
    print("  Raw switch:",Parameters.CameraRawSwitch)

# ------------------------------------------------------------------------------------------------------

def About():
    """ Display version information. """
    print(textcolor.yellow("About",ProgramTitle))
    # Print timestamp.
    MainLog.Log("Now:",NowUTC(),"UTC",terminal=True)
    # Print O/S and hardware
    MainLog.Log("RPi model:",RPIMODEL)
    MainLog.Log("RPi model number:",RPiNum)
    MainLog.Log("RPi OS ID:",OS_id)
    MainLog.Log("RPi OS name:",OS_name)
    MainLog.Log("RPi OS type:",OS_type)
    MainLog.Log("RPi OS bits:",OS_bits)
    MainLog.Log("RPi processor:",OS_processor)
    MainLog.Log("RPi systemkey:",OS_systemkey)
    
    for line in osCmd('cat /sys/firmware/devicetree/base/model'):
        if len(line) > 0: MainLog.Log("Firmware:",line,terminal=True)
    for line in osCmd('cat /etc/os-release'):
        if len(line) > 0: MainLog.Log("OS release:",line,terminal=True)
    for line in osCmd('cat /proc/version'):
        if len(line) > 0: MainLog.Log("OS version:",line,terminal=True)
    for line in osCmd('cat /proc/cpuinfo'):
        if len(line) > 0: MainLog.Log("CPU info:",line,terminal=True)
    for line in osCmd('vcgencmd get_mem arm'):
        if len(line) > 0: MainLog.Log("CPU memory allocation:",line,terminal=True)
    for line in osCmd('vcgencmd get_mem gpu'):
        if len(line) > 0: MainLog.Log("GPU memory allocation:",line,terminal=True)
    for line in osCmd('uptime'):
        if len(line) > 0: MainLog.Log("Uptime:",line,terminal=True)
    # Print program ID
    MainLog.Log("Program:",ProgramTitle,terminal=True) # What program name is running?
    MainLog.Log("Program version:",VERSION,terminal=True) # Print RPi software version.
    MainLog.Log("Project root:",ProjectRoot,terminal=True) # What is the project root?
    if Session.ValidControllerVersion():
        MainLog.Log("Microcontroller program version:",textcolor.green(Session.ControllerVersion),"(good)",terminal=True) # We like this version.
    else:
        MainLog.Log("Microcontroller program version:",textcolor.red(Session.ControllerVersion),"(check)",terminal=True) # We don't trust this version.
    MainLog.Log("Acceptable microcontroller versions:",ACCEPTABLECONTROLLERVERSIONS,terminal=True) # What microcontroller versions are acceptable?
    MainLog.Log("Python version:",sys.version_info,terminal=True) # What version of Python is this?
    # Print any package versions available. 
    MainLog.Log("Skyfield version:",SkyfieldVersion,terminal=True) # What version of Skyfield is in use?
    MainLog.Log("Astroalign version:",astroalign.__version__,terminal=True) # What version of Astroalign is in use?
    MainLog.Log("Numpy version:",np.__version__,terminal=True) # What version of Numpy is in use?
    MainLog.Log("Pandas version:",pandas.__version__,terminal=True) # What version of pandas is in use?
    MainLog.Log("PiDNG version:","Unknown",terminal=True) # What version of piDNG is in use?
    
# ------------------------------------------------------------------------------------------------------

# Create menu structure.

MotorMenuOptions = {
    'ShowMotorStatus':        {'label':'About motors',              'call':ShowMotorStatus},
    'HomeAllMotors':          {'label':'Home all motors',           'call':HomePosition},
    'TuneAzimuth':            {'label':'Tune azimuth position',     'call':TunePositionAzimuth},
    'TuneAltitude':           {'label':'Tune altitude position',    'call':TunePositionAltitude},
    'AzimuthAngle':           {'label':'Move azimuth to angle',     'call':AzimuthAngle},
    'AltitudeAngle':          {'label':'Move altitude to angle',    'call':AltitudeAngle},
    'StopAllMotors':          {'label':'Stop all motors',           'call':StopMotors},
}
MotorMenu = proceduremenu(MotorMenuOptions,'Motor tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

CameraMenuOptions = {
    'AboutCamera':               {'label':'About camera',               'call':AboutCamera},
    'StartCameraThread':         {'label':'Start camera thread',        'call':StartCameraThread},
    'StopCameraThread':          {'label':'Stop camera thread',         'call':ShutdownCamera},
    'SensorCleanupOff':          {'label':'Sensor cleanup off',         'call':DisableCleanup},
    'SensorCleanupOn':           {'label':'Sensor cleanup on',          'call':EnableCleanup},
    'AutoDetectCamera':          {'label':'Auto detect camera',         'call':AutoDetectCamera},
    'CalibrateFov':              {'label':'Calibrate FoV',              'call':CalibrateFovMenu},
    'EnableCamera':              {'label':'Enable camera',              'call':EnableCamera},
    'DisableCamera':             {'label':'Disable camera',             'call':DisableCamera}
}
CameraMenu = proceduremenu(CameraMenuOptions,'Camera tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MctlMenuOptions = {
    'MicrocontrollerStatus':   {'label':'About motorcontroller',           'call':MicrocontrollerStatus},
    'RestartMicrocontroller':  {'label':'Restart microcontroller',         'call':RestartMicrocontroller},
    'StartMessage':            {'label':'Start message handler',           'call':MenuStartMessage},
    'ShutdownMessage':         {'label':'Shutdown message handler',        'call':MenuShutdownMessage},
    'FlushCommandQueue':       {'label':'Flush command queue',             'call':FlushCommandQueue},
    'ZipCommsLog':             {'label':'Zip comms log',                   'call':ZipCommsLog},
    'MonitorComms':            {'label':'Monitor communication',           'call':MonitorComms},
    'MicrocontrollerLedsOn':   {'label':'Microcontroller LEDs on',         'call':MicrocontrollerLedsOn},
    'MicrocontrollerLedsOff':  {'label':'Microcontroller LEDs off',        'call':MicrocontrollerLedsOff},
    'MicrocontrollerPowerOn':  {'label':'Microcontroller GPIO power ON',   'call':Mctl.PowerOn},
    'MicrocontrollerPowerOff': {'label':'Microcontroller GPIO power OFF',  'call':Mctl.PowerOff}
}
MctlMenu = proceduremenu(MctlMenuOptions,'Microcontroller tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MiscMenuOptions = {
    'About':                  {'label':'About system',               'call':About},
    'ShowParameters':         {'label':'Show parameters',            'call':ShowParameters},
    'EditParameters':         {'label':'Edit parameters',            'call':EditParameters},
    'ReloadParameters':       {'label':'Reload parameters',          'call':ReloadParameters},
    'TrackingStatus':         {'label':'Tracking status',            'call':TrackingStatus},
    #'TrackingEnhanceOn':      {'label':'Tracking enhancement on',    'call':TrackingEnhanceOn},
    #'TrackingEnhanceOff':     {'label':'Tracking enhancement off',   'call':TrackingEnhanceOff},
    #'TrackingUrbanOn':        {'label':'Tracking urban filter on',   'call':TrackingUrbanOn},
    #'TrackingUrbanOff':       {'label':'Tracking urban filter off',  'call':TrackingUrbanOff},
    'SetLocalTZ':             {'label':'Set local timezone',         'call':DefineLocalTZ},
    'ShowFolderList':         {'label':'Show folder list',           'call':ShowFolderList},
    'EditTargetHistory':      {'label':'Edit target history',        'call':EditTargetHistory},
    'DebugModeOn':            {'label':'Debug mode on',              'call':DebugModeOn},
    'DebugModeOff':           {'label':'Debug mode off',             'call':DebugModeOff},
    'ChooseColorScheme':      {'label':'Choose color scheme',        'call':Parameters.ChooseColorScheme},
    'ChooseColor':            {'label':'Choose individual color',    'call':Parameters.ChooseColor}
}
MiscMenu = proceduremenu(MiscMenuOptions,'Miscellaneous tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

DevMenuOptions = {
    'LatestTrackingFilter':   {'label':'Set Latest Tracking filter', 'call':SelectLatestFilter},
    'TestLatestFilter':       {'label':'Test Latest Tracking filter','call':TestLatestFilter},
    'RecheckDisc':            {'label':'Check / remount storage',    'call':RecheckDisc},
    'ZipTrajectories':        {'label':'Zip trajectory log',         'call':ZipTrajectoryLog},
    'ShowParameters':         {'label':'Show parameters',            'call':ShowParameters},
    'EditParameters':         {'label':'Edit parameters',            'call':EditParameters},
    'ReloadParameters':       {'label':'Reload parameters',          'call':ReloadParameters}
}

DevMenu = proceduremenu(DevMenuOptions,'Development tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MainMenuOptions = {
    'SelectTarget':           {'label':'Select target',             'bold':True,  'call':SelectTarget},
    'BeginObservation':       {'label':'Begin observation',         'bold':True,  'call':BeginObservation, 'postcall':FlagObservationEnd},
    'ProgramStatus':          {'label':'Status',                    'call':ProgramStatus},
    'GotoTarget':             {'label':'GOTO target',               'call':MenuGoToTarget},
    'HomeAllMotors':          {'label':'Home all motors',           'call':HomePosition},
    'SetExposureTime':        {'label':'Set exposure time',         'call':MenuSetExposureTime},
    'SetLightBatchSize':      {'label':'Set light batch size',      'call':MenuSetBatchSize},
    'SetControlBatchSize':    {'label':'Set control batch size',    'call':MenuSetControlBatchSize},
    'TakeDarkFrameSet':       {'label':'Take dark frame set',       'call':MenuDarkSet},
    'TakeFlatFrameSet':       {'label':'Take flat frame set',       'call':MenuFlatSet},
    'TakeBiasFrameSet':       {'label':'Take bias/offset frame set','call':MenuBiasSet},
    'TakeDarkFlatFrameSet':   {'label':'Take dark flat frame set',  'call':MenuDarkFlatSet},
    'TakePreviewFrames':      {'label':'Take preview frames',       'call':MenuManualPreview},
    'TakeAutoFrames':         {'label':'Take auto frames',          'call':MenuAutoPhoto},
    'MotorMenu':              {'label':'Motor tools',               'call':MotorMenu},
    'MicrocontrollerMenu':    {'label':'Microcontroller tools',     'call':MctlMenu},
    'CameraMenu':             {'label':'Camera tools',              'call':CameraMenu},
    'MiscMenu':               {'label':'Miscellaneous tools',       'call':MiscMenu},
    'DevMenu':                {'label':'Development tools',         'call':DevMenu}
}

ProgramStatus() # Show current situation of the telescope and target at startup.
MainMenu = proceduremenu(MainMenuOptions,'Pilomar main menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

# Run main menu.
while True:
    MainMenu.Prompt()
    if AskYesNo("Do you really want to shut down? [y/N]",default=False): break # OK to quit.

# Cleanup.
MainLog.Log("MAIN: CLOSING",terminal=False)

FlagObservationEnd() # Make sure that any observation is stopped. This prevents further trajectories being sent to the microcontroller.

# Offer to return camera to the HOME position.
# Use the last reported camera position.
CameraAlt, CameraAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
HomeAlt, HomeAz = HomeAltAz() # Home position for camera.
if round(CameraAlt,1) != round(HomeAlt,1) or round(CameraAz,1) != round(HomeAz,1): # Camera is not at home position.
    print(textcolor.yellow("The camera is currently at " + AzAltText(CameraAz,CameraAlt)))
    answer = AskYesNo("Would you like to home the camera before powering off? [y/N]",False)
    if answer:
        print ("Returning camera to home position...")
        HomePosition()
        # Use the last reported camera position.
        CameraAlt, CameraAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
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
Mctl.Reset(planned=True) # For safety, reset the microcontroller. This prevents the stepper motors triggering due to out-of-date instructions. 
MainLog.Log('Stopping microcontroller communication: send STOP...')
UartControlQueue.put('stop') # Tell MctlThread to shut down.
if MctlThread.is_alive():
    MainLog.Log('Stopping microcontroller communication: wait for end...')
    MctlThread.join() # Wait MctlThread to complete.
else:
    MainLog.Log('Stopping microcontroller communication: MctlThread already stopped.')
print (' ')
ShutdownCamera() # Terminate the CameraHandler thread.
ShutdownMessage() # Terminate the MessageHandler thread.
print (' ')
GPIO.cleanup() # Reset the GPIO state.
print (textcolor.yellow("Saving parameters..."))
Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
print (textcolor.yellow("Done."))
print (textcolor.fgbgcolor(textcolor.BLACK,textcolor.GREEN," PILOMAR COMPLETE. OK TO SHUTDOWN "))
MainLog.Log("MAIN: PROGRAM COMPLETE",terminal=False)

# Camera settings....
# - From https://github.com/RemovedMoney326/Hubble-Pi/blob/master/HubblePiDocumentation.pdf
#  *) If recording video, you can set the framerate to max 0.005 frames / second-  which results in 200second exposures! See Page 110 of the official guide.
#  *) Developer is also planning an astroguider - using the camera to keep track of the object.
#  *) It uses KStars (free) for sky-guiding. Research this.

