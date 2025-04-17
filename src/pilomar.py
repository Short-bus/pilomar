#!/usr/bin/python

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.
# Examples
# - SKYFIELD is issued and used under the "MIT License" terms.
# - HIPPARCOS data is used under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License.
# - JPL data for planet positions will have its own licence.
# - NGC (New General Catalog) is gathered from multiple sources including the Saguaro Astronomy Club Database version 8.1.
# - IC catalog is gathered from multiple sources.
# - PGC (Principle Galaxies Catalog) is based upon the Hyperleda list from the Strasbourg astronomical Data Center.
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
# - RaspberryPi microcomputer (V3 or V4) 2GB or greater.
# - Raspbian BUSTER 32BIT or BOOKWORM 64BIT operating system.
# - Pimoroni Tiny2040 8MB as a microcontroller of the motors
# - Nema 17 stepper motors (ideally 0.9degree per full step but 1.8degree is supported too).
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
# This version runs on only certain Raspberry Pi configurations.
# Working combinations :-
#   RASPBERRY PI 3B + BUSTER 32Bit <-------------- NOT RECOMMENDED
#   RASPBERRY PI 4B + BUSTER 32Bit
#   RASPBERRY PI 4B + BOOKWORM 64Bit <------------ RECOMMENDED
#   RASPBERRY PI 5B + BOOKWORM 64Bit
#   RASPBERRY PI CM4 + BOOKWORM 64Bit
# Unsupported combinations :-
#   RASPBERRY PI + Any O/S
#   RASPBERRY PI 2 + Any O/S
#   RASPBERRY PI [all] + BULLSEYE
# ================================================================================================================================================

# This program uses THREADS. It has to handle UI, MOVEMENT, COMMUNICATIONS and PHOTOGRAPHY in parallel.
# Thread 1 (MAIN Process) handles:
#   - User interface, astro calculations, observation control.
# Thread 2 handles:
#   - Image capture, image preparation, preview generation, tracking image processing, motor position tuning.
# Thread 3 handles:
#   - UART communication flow between RPi and microcontroller, including trajectory calculation and updates.

# KNOWN ISSUES -----------------------------------------------------------------------------------------------------------------------------------------------------------
# *Q* On rare occasions, the camera process can hang completely, it does not complete image capture, requiring a power cycle of the RPi.
#     The cause is not known, but the camera board stops responding for a very long time, it may recover after 20-30 minutes but the observation will terminate earlier. 
#     I have read online that power problems to the camera can cause this.
#     This is detected and reported, but this does not recover the situation programmatically.
#     Problem is more rare in builds from 2023 onwards.
# *Q* Some microcontrollers sometimes randomly reset. The software is relatively reset tolerant and recovers automatically, but the cause of the resets is not yet identified.
#     Resets are reported, and generally only cause brief delays while the system recovers.
#     Resets are more common with RPi Pico 2040 and Adafruit Feather 2040.
#     Resets do not occur with Pimoroni Tiny2040 8MB or Pimoroni Tiny2350 4MB.
# *Q* During observations the keyboard scanning routine can cause the display to blink sometimes. 
#     If you are sensitive to flashing images you can slow down the keyboard scanning so that the image is more stable, but it will react to keyboard input more slowly.
#     See the KeyboardScanDelay delay parameter (number of seconds between checking the keyboard).

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
# 0.3.0    12.03.2024 2024-03-issues items addressed.
# 1.0.0    20.04.2024 Refactored code.
#                     Preparations for RPi5 support.
# 1.1.0    07.05.2024 Bookworm/64bit can now generate .fits image files.
# 1.2.0    09.09.2024 PGC catalog support, further develoment of .fits support, RPi5 OK.
#                     Preparations for Compute Module 4 support.
#                     Pimoroni Tiny2350 support.
#                     Faster calculation solution for generating preview, tracking target and simulated images.


# Versioning
# MAJOR.MINOR.MICRO
# - MAJOR = Breaking change. Not fully compatible with previous versions. Usually requires RPI and MICROCONTROLLER updates together.
# - MINOR = New features but backwards compatible. Usually allows RPI or MICROCONTROLLER to be updated independently.
# - MICRO = Development/bugfix releases.
VERSION = '1.2.0' # Shared with microcontroller. # Make sure the microcontroller accepts any new version number.

import sys # For version verification.

# ------------------------------------------------------------------------------------------------------

def SourceCode() -> str: 
    """ Return the filename of the source code being executed. """
    return sys.argv[0]

# ------------------------------------------------------------------------------------------------------

ProgramTitle = SourceCode().split('/')[-1].split('.')[0].lower() # Used in display titles and also filenaming to separate different generations of the program.
print(ProgramTitle,VERSION)

#print("Version:",VERSION)
ACCEPTABLECONTROLLERVERSIONS = ['1.0','1.1','1.2'] # Microcontroller versions that this will work with. Ignore patch level.

# Import required libraries
import serial # UART communication with a microcontroller.
import time # sleep functionality for pauses in execution. 
import locale # Internationalisation support.
import glob # file system.
import os # OS Command execution.
import math # Math and trig functions. 
import json # json file handling.
import random # random number generator.
import cv2 # openCV for image file handling.  
from pathlib import Path # For navigating folder structure.
import astroalign # Image alignment routines.
from datetime import datetime, timedelta, timezone
from pilomarlib import attributemaster # Import some helper classes.
from pilomarlib import UTCStringToDatetime,DTSToDatetime,StringToDatetime,IsFloat,IsInt,TextToInt,TextToFloat
from pilomartrig import * # Trigonometry functions.
from pilomartimer import timer, progresstimer # Pilomar's timer classes.
from pilomarlogfile import logfile # Pilomar's logging class.
from pilomaroscommand import oscommand # Pilomar's OS command executor.
from pilomardisc import discmonitor # Pilomar's disc storage monitor.
from pilomarimage import pilomarimage # Pilomar's IMAGE BUFFER handler (combines numpy, OpenCV and pilomar specific routines)
from pilomarcelestrak import celestrak # Pilomar's CELESTRAK satellite data handler.
from pilomarcamera import astrosensor, astrolens, astrocamera # Pilomar's CAMERA elements.
from pilomarmemory import memorymonitor # Pilomar's memory capacity monitor.
from pilomarcpu import cpumonitor # Pilomar's CPU monitor.
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
# textcolor is a homegrown simplified terminal display library. 
# There are other libraries available for groovy character displays ('colorama', 'termcolor', 'blessing', 'rich' etc).
from textcolor import textcolor # Basic colour and cursor control codes for terminal displays.
from textcolor import colordisplay # Basic colour character graphics for window display on terminal.
from textcolor import keyboardscanner # Simple non-blocking keyboard scanner.
from textcolor import proceduremenu, optionmenu # Basic menu handlers.
from textcolor import listchooser, filechooser # Allow user to filter through a list of names or select a file from disc.
import numpy as np # Fast array handling
import pandas # Dataframe handling.
import sep # This is used by astroalign, it is only imported here to flush out any problems with the package. (It has suffered from the classic 'numpy.ndarray size changed' in the past.)
import threading # Run the image capture in a separate thread so that motor movement can continue. *Q* Drift calculation and targetting could also move to separate thread.
from queue import Queue # Use queue mechanism to communicate between ObservationRun and Camera threads because they run in parallel.
import pilomargpio # GPIO wrappers to support different GPIO libraries.
if pilomargpio.GPIO_DRIVER == 'GPIO': # Original GPIO handlers needed for IO.
    # Select the GPIO specific drivers for IO functions.
    inputpin = pilomargpio.inputpin_gpio
    outputpin = pilomargpio.outputpin_gpio
    GPIOCleanup = pilomargpio.cleanup_gpio
elif pilomargpio.GPIO_DRIVER == 'GPIOD': # Bookworm GPIOD handlers needed for IO.
    # Select the GPIOD specific drivers for IO functions.
    inputpin = pilomargpio.inputpin_gpiod
    outputpin = pilomargpio.outputpin_gpiod
    GPIOCleanup = pilomargpio.cleanup_gpiod
else:
    raise Exception("Could not identify a suitable GPIO driver for this installation.")

# ------------------------------------------------------------------------------------------------------

textcolor.SetCurrentLocale() # Get the user's locale. Without this the program runs assuming eu_US decimals and UTF-8 from the O/S which causes problems. 

# Check the locale for the application. (Language and Character set). Will not adapt the textcolor.SYMBOLS list.
LOCALE = textcolor.CheckLocale(switch=True) # This makes textcolor.SYMBOLS compatible with environment character set.
# Special characters.
# The terminal will need to be UTF-8 too. If not, these will look corrupted.
#Symbol = {'degree' : '\u00B0', 'left' : '\u2190', 'right' : '\u2192', 'up' : '\u2191', 'down' : '\u2193', 'delta' : '\u0394', 'sun' : '\u2609', 'moon' : '\u263D', 'mercury' : '\u263F',
#'venus' : '\u2640', 'earth' : '\u2641', 'mars' : '\u2642', 'jupiter' : '\u2643', 'saturn' : '\u2644', 'uranus' : '\u2645', 'neptune' : '\u2646', 'pluto' : '\u2647', 'ceres' : '\u26B3', 
#'pallas' : '\u26B4', 'juno' : '\u26B5', 'vesta' : '\u26B6', 'astraea' : '\u2BD9', 'flora' : '\u2698', 'hygiea' : '\u2695', 'chiron' : '\u26B7', 'pholus' : '\u2BDB', 'aries' : '\u2648',
#'taurus' : '\u2649', 'gemini' : '\u264A', 'cancer' : '\u264B', 'leo' : '\u264C', 'virgo' : '\u264D', 'libra' : '\u264E', 'scorpio' : '\u264F', 'sagittarius' : '\u2650', 'capricorn' : '\u2651',
#'aquarius' : '\u2652', 'pisces' : '\u2653', 'ophiuchus' : '\u26CE', 'comet' : '\u2604', 'star' : '\u2736', 'camera' : '\u00A9', 'target' : 'T', 'iss' : 'H', 'css' : '#'}
Symbol = textcolor.SYMBOLS # Shortcut to the special characters list from textcolor.
# Add some extra ones specific to this program.
Symbol['camera'] = 'c'
Symbol['target'] = 'T'
Symbol['iss'] = 'H'
Symbol['css'] = '#'
DegreeSymbol = Symbol['degree'] # For typing speed, it's used a lot.

# ------------------------------------------------------------------------------------------------------

WarningFlags = {} # Dictionary of 'toggles' so that warnings do not repeat too often. 

def FirstWarningFlag(flagname):
    """ Given a flag name, return True if this is the first time it's been triggered.
        This is used to prevent warning messages repeating when a condition is triggered.
        Using this mechanism we know that the warning is already issued, so don't repeat it. """
    result = WarningFlags.get(flagname,False)
    if not result: WarningFlags[flagname] = True # 1st occurrence, so flag it as such. 
    return result
    
def ResetWarningFlag(flagname):
    """ Given a flag name, reset it to False.
        This is used to prevent warning messages repeating when a condition is triggered.
        Using this mechanism we know that the warning is already issued, so don't repeat it. """
    WarningFlags[flagname] = False

# ------------------------------------------------------------------------------------------------------

ReloadData = False # Set this to TRUE to cause the data files to be reloaded from the online resources. Can be set by 'reload' runtime argument too.
ResumeObservation = False # Set this to TRUE to automatically load the previous observation and resume.
StartupClock = None # No initial datetime set for start of program. Means we use the current system clock.
ClockOffset = None # Number of seconds to apply to clocks to make the program appear to run in a different period of time.  Use with caution.

# Extract runtime parameters.
RunArgs = sys.argv[1:] # Ignore 1st argument which is this program name.
if len(RunArgs) > 0:
    print ("Runtime arguments :-")
    for i in RunArgs:
        print('>', i)
        if i == 'reload': 
            print(textcolor.yellow("Reloading data caches."))
            print("Data files will be reloaded from original sources.")
            ReloadData = True
        elif i == 'resume': 
            print(textcolor.yellow("Automatically resuming previous observation."))
            ResumeObservation = True
        elif i.startswith('clock='): 
            StartupClock = i.split('=')[1] # Pull ISO8601 format datetime from runtime parameters.
            print(textcolor.red("Startup clock was set:",StartupClock))
            print("- This is a development feature. Use with caution.")
            print("- It may cause unexpected or inconsistent behaviour.")
        else: print (textcolor.red('Ignored startup parameter "' + str(i) + '"'))
        
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
HOSTNAME = os.uname().nodename
print("Hostname:",HOSTNAME)
print("Locale:",LOCALE) # Character encoding.
if not LOCALE[0].startswith("en_"): # Pi-lomar expects 'English' languages (because of number parsing). Issue a warning only.
    print(textcolor.orange("THE ENVIRONMENT MAY HAVE THE WRONG LANGUAGE SET"))
    lines = ["THE ENVIRONMENT MAY HAVE THE WRONG LANGUAGE SET",
             "",
             "Pi-lomar expects the 'English' languages set.",
             "(Current limitations on parsing some values from the O/S.)",
             "",
             "You can set this in Raspberry Pi Configuration",
             "> localisation",
             "  > Set locale",
             "    > Language",
             "",
             "You can continue, however the system may not behave as expected."]
    textcolor.TextBox(lines,fg=textcolor.ORANGE,bg=textcolor.BLACK)
if not LOCALE[1] in ["UTF-8"]: # Pi-lomar expects UTF-8 character set. Issue error and quit.
    print(textcolor.red("THE ENVIRONMENT HAS THE WRONG CHARACTER ENCODING"))
    lines = ["THE ENVIRONMENT HAS THE WRONG CHARACTER ENCODING",
             "",
             "Pi-lomar expects the character encoding to be UTF-8",
             "",
             "You can set this in Raspberry Pi Configuration",
             "> localisation",
             "  > Set locale",
             "    > Character set : UTF-8",
             "",
             "The application may fail with encoding errors."]
    textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.RED)
print (textcolor.yellow("Make sure that your TERMINAL is configured for UTF-8 character encoding too."))

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

def PleaseRestart():
    """ Display banner asking the user to restart the program. """
    lines = ["","Please restart the program",""]
    textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.RED)

# ------------------------------------------------------------------------------------------------------

if StartupClock != None:
    textcolor.TextBox(["StartupClock specified " + StartupClock],fg=textcolor.WHITE,bg=textcolor.RED)
    SetTimeOffset(starttime=StartupClock)
else:
    print("Using realtime clock.")

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

print("Current time is:",NowUTC(),' UTC. (offset is',ClockOffset,"seconds.)")

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

def HRBytes(bytecount: int) -> str:
    """ Turn a large number into human readable format.
        Turns 1024 * 1024 into 1MB etc. """
    try:    
        line, _, _ = textcolor.HRNumber(bytecount,base=1024,decimals=1)
        line += "b"
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        print("HRBytes: textcolor.HRNumber(",bytecount,") failed.")
        raise Exception("HRBytes() failed.") from e # Continue with regular exception stack.
    return line

# ------------------------------------------------------------------------------------------------------

def HRHertz(hertz: int) -> str:
    """ Turn a large number into human readable format.
        Turns 1,000,000 into 1MHz etc. """
    try:    
        line, _, _ = textcolor.HRNumber(hertz,base=1000,decimals=1)
        line += "Hz"
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        print("HRHertz: textcolor.HRNumber(",hertz,") failed.")
        raise Exception("HRHertz() failed.") from e # Continue with regular exception stack.
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
        dateaware = True. If the date is not today, then it shows 'DD HH:MM' instead.
        This works with UTC timezone. """
    result = None
    try:
        if timestamp is None: # Protect from null values.
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

def DisplayHmsFromStamp(timestamp: datetime,dateaware=False) -> str:
    """ Return the HH:MM:SS part of a timestamp as a string.
        Works with datetime input. 
        dateaware = True. If the date is not today, then it shows 'DD HH:MM' instead.
        This works with DisplayTZ timezone. """
    result = None
    try:
        if timestamp is None: # Protect from null values.
            result = ""
        else:
            timestamp = UTCtoDisplay(timestamp) # Convert to display timezone.
            result = str(timestamp)
            if dateaware and timestamp.date() != UTCtoDisplay(NowUTC()).date(): # The date is not today.
                result = result[8:16] # Extract "DD HH:MM"
            else: # The date is today. Extract "HH:MM:SS"
                result = result.split(" ")[1]
                result = result.split(".")[0]
    except Exception as e:
        print(e) # Trap all the exception information in the main log file.
        raise Exception("DisplayHmsFromStamp() failed.") from e # Continue with regular exception stack.
    return result

# ------------------------------------------------------------------------------------------------------

def NowHMS() -> str:
    """ Return current time as formatted string. 
        Returns HH:MM:SS string for the current time (UTC) """
    return HmsFromStamp(NowUTC())

# ------------------------------------------------------------------------------------------------------

def DisplayNowHMS() -> str:
    """ Return current time as formatted string. 
        Returns HH:MM:SS string for the current display timezone. """
    return DisplayHmsFromStamp(NowUTC())

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

def Ts2Datetime(tsvalue):
    """ Convert skyfield time value into datetime value. """
    dtvalue = tsvalue.utc_datetime()
    return dtvalue

# ------------------------------------------------------------------------------------------------------

def Datetime2Ts(dtvalue):
    """ Convert datetime value into skyfield time value. """
    if dtvalue.tzinfo is None: dtvalue = dtvalue.replace(tzinfo=pytz.UTC) # If timezone is not set, assign UTC.
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

def SubtractList(list1,list2):
    """ Subtract list 2 from list 1 """
    result = [a for a in list1 if a not in list2]
    return result

# ------------------------------------------------------------------------------------------------------
    
def UniqueList(list1):
    """ Return only unique entries from a list. 
        Does not preserve order. """
    result = list(set(list1)) # Convert via 'set()' which reduces to unique hashable entries.
    return result
    
# ------------------------------------------------------------------------------------------------------

# During an observation run we need to interrupt the processing. Python doesn't do this natively and
# <ctrl-c> will stop the program brutally, so we use the curses library to provide a keyboard scanner. 
Keyboard = keyboardscanner() # Non-Blocking reader of the keyboard (via curses library). 

# Initialize Logging.
logdir = ProjectRoot + "/log"
# Main log file.
LogFileName = logdir + "/" + ProgramTitle + "_" + UtcTimeStamp() + ".log"
print("Main log to", LogFileName)
MainLog = logfile(LogFileName,clockoffset=ClockOffset) # Create a MAIN log file object.
MainLog.Log(SourceCode(),VERSION,SourceDate(),terminal=False) # Identify the program and version to the user.

# Camera log file.
CamLogFileName = logdir + "/" + ProgramTitle + "_camera_" + UtcTimeStamp() + ".log"
print("Camera log to", CamLogFileName)
CamLog = logfile(CamLogFileName,clockoffset=ClockOffset) # Create a CAMERA specific log file. (This runs in separate thread, unsure if logging would be thread-safe.)
CamLog.Log(SourceCode(),VERSION,SourceDate(),terminal=False) # Identify the program and version to the user.

MainLog.Log("Python version:",sys.version,terminal=False)
MainLog.Log("Main: ReloadData",ReloadData,terminal=False) # Record that 'reload' has been triggered.
MainLog.Log("Hostname:",HOSTNAME,terminal=False)
MainLog.Log("Locale:",LOCALE,terminal=False)
MainLog.Log("GPIO driver chosen:",pilomargpio.GPIO_DRIVER,terminal=False)

MainLog.Log("Startup parameters:", RunArgs,terminal=False)
HistoryJsonFile = ProjectRoot + '/data/' + ProgramTitle + '_sessions.json' # Chosen observation targets and settings are stored in this file.

# ------------------------------------------------------------------------------------------------------

OSCommand = oscommand(MainLog.Log) # Create OS Command executor. 
osCmd = OSCommand.Execute # Shortcut point to the execution method which returns the output.
osCmdCode = OSCommand.ExecuteCode # Shortcut point to the execution method which returns the termination code.

# ------------------------------------------------------------------------------------------------------

class hardware(attributemaster):
    """ Class defining the hardware. """
    
    RASPISTILL_SYSTEMS = ['wheezy','jessie','stretch','buster'] # These all came with raspistill for camera support.
    SUPPORTED_SYSTEMS = ['3/buster/32','4/buster/32','4/bookworm/64','CM4/bookworm/64','5/bookworm/64'] # The software is designed to run under these hardware/os combinations.

    def __init__(self,oscmd,logger=None):
        """ Create new instance of the hardware and initialise values.
            Parameters ----------------------------------------------------
            logger = Handle to a logfile instance.
            oscmd = Handle to a oscommand.Execute method. """
        self.SetLogger(logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.osCmd = oscmd
        self.set_program_title()
        self.set_rpi_model()
        self.set_os_version()
        self.native_camera_driver()
        # Some configuration checks.
        if self.i2c_enabled(): # Warn if i2c interface is on.
            self.Log("hardware.__init__():",str(self.program_title) + " is not designed to run with i2c interface enabled. Please disable it.",level='error',terminal=True)
            raise Exception(str(self.program_title) + " is not designed to run with i2c interface enabled. Please disable it.")
        if self.spi_enabled(): # Warn if spi interface is on.
            self.Log("hardware.__init__():",str(self.program_title) + " is not designed to run with spi interface enabled. Please disable it.",level='error',terminal=True)
            raise Exception(str(self.program_title) + " is not designed to run with spi interface enabled. Please disable it.")
         # Safe to start checking GPIO pins for other information.
        self.identify_pcb()
        self.Log("hardware.__init__(): RPi: Model:",self.rpi_model,
                 "Num:",self.rpi_num,
                 "OStype:",self.os_type,
                 "OSid:",self.os_version_id,
                 "OSname:",self.os_version_name,
                 "OSbits:",self.os_bits,
                 "OSproc:",self.os_proc,
                 "SysKey:",self.os_systemkey,terminal=False)
                
    def identify_pcb(self,autodetect=True):
        """ Check the GPIO pins that identify the PCB capabilities.
            There are currently 2 GPIO pins allocated for identifying the PCB capabilities.
            This allows up to 4 different PCBs to be detected.
            
            Currently the 2 pins have specific meanings, but this may change in the future.
            - Combinations HIGH+HIGH = Original (revision 0) board.
            -              LOW+LOW   = Revision 1 board.
            -              HIGH+LOW  = Undefined.
            -              LOW+HIGH  = Undefined.
            
            GPIO 22 on header (pin 13): LOW signifies Raspberry Pi Pico microcontroller. (GND)
                                        HIGH signifies Pimoroni Tiny microcontroller. (HIGH or UNCONNECTED)
            GPIO 27 on header (pin 15): LOW signifies hardware protection from USB power conflicts. (GND)
                                        HIGH signifies no hardware protection from USB power conflicts. (HIGH or UNCONNECTED)

            Parameters --------------------------------------------------------------------------------------
            autodetect : When TRUE the code checks the two jumper pins to identify the board.
                         When FALSE, it assumes an original (gen 0) board. """
        self.tiny_flag_pin = 22 # LOW = Raspberry Pi PICO on the PCB. # HIGH = Pimoroni Tiny on the PCB.
        self.usb_protect_flag_pin = 27 # LOW = PCB is protected from power conflicts. # HIGH = PCB is NOT protected from power conflicts.
        self.pcb_revision = 0
        
        if autodetect:
            self.Log("hardware.identify_pcb(): Begin. TinyFlagPin",self.tiny_flag_pin,"UsbProtectFlagPin",self.usb_protect_flag_pin,terminal=False)
            
            # Are we using a TINY or PICO format microcontroller?
            TFP = inputpin(self.tiny_flag_pin,"TinyFlag",pull='up') # When pin is HIGH (default) we're using TINY, when LOW we're using PICO.
            if TFP.IsHigh(): 
                self.pcb_mctl_family = "tiny" # We're working with a Pimoroni Tiny microcontroller.
            else: 
                self.pcb_mctl_family = "pico" # We're working with a Raspberry Pi Pico microcontroller.
            
            # Does the PCB offer 'safe power' if USB and GPIO headers are connected at the same time?
            UPFP = inputpin(self.usb_protect_flag_pin,"UsbProtectFlag",pull='up') # When pin is HIGH (default) we must protect conflicting power, when LOW it's safe.
            if UPFP.IsHigh(): 
                self.pcb_protect_usb = True # Need to protect conflicting USB power.
            else: 
                self.pcb_protect_usb = False # Conflicting USB power is not a problem.

            if self.pcb_protect_usb and self.pcb_mctl_family == 'tiny': 
                self.pcb_revision = 0 # Original PCB. Needs Power protection and has tiny microcontroller.
            elif not self.pcb_protect_usb and self.pcb_mctl_family == 'pico': 
                self.pcb_revision = 1 # 1st revision of PCB. Power is protected and has pico microcontroller.
            else: 
                self.pcb_revision = 4 # Unknown PCB design.
            
        else: # Default to traditional microcontroller and PCB.
            self.Log("hardware.identify_pcb(): Skipped",terminal=False)
            self.pcb_mctl_family = "tiny" # Assume Pimoroni Tiny (original design's microcontroller)
            self.pcb_protect_usb = True # Assume no protection for conflicting power sources.
            
        self.Log("hardware.identify_pcb(): Family",self.pcb_mctl_family,"UsbProtect",self.pcb_protect_usb,"pcb revision",self.pcb_revision,terminal=False)
        
    def set_program_title(self):
        """ Establish the program title from the source code name. """
        self.program_title = sys.argv[0].split('/')[-1].split('.')[0].lower() # Used in display titles and also filenaming to separate different generations of the program.        
        
    def set_rpi_model(self):
        """ Establish the model of Raspberry Pi computer. """
        lines = self.osCmd('cat /sys/firmware/devicetree/base/model')
        # Expect results like 
        # "Raspberry Pi Compute Module 4 Rev 1.0"
        #        Returns rpimodel 'RPi CM4 1.0' rpinum 'CM4'
        # "Raspberry Pi 4 Model B Rev 1.1"
        #        Returns rpimodel 'RPi 4 B 1.1' rpinum '4'
        rpimodel = 'Raspberry Pi'
        for line in lines:
            if len(line) > 0: rpimodel = line
        rpimodel = rpimodel.replace('Raspberry Pi ','RPi ')
        rpimodel = rpimodel.replace('Compute Module ','CM')
        rpimodel = rpimodel.replace('Model ','')
        rpimodel = rpimodel.replace('Rev ','')
        # Remove non printing characters.
        temp = ''
        for char in rpimodel:
            if char >= ' ': temp += char
        self.rpi_model = temp
        rm_list = self.rpi_model.split(' ') # Break into elements. 
        if len(rm_list) > 1:
            self.rpi_num = self.rpi_model.split(' ')[1] # Pull the '4' out of "RPi 4 B 1.4" format response, or 'CM4' out of a compute module value.
        else:
            self.rpi_num = 'unknown'
        if len(rm_list) > 1:
            self.rpi_rev = self.rpi_model.split(' ')[-1] # Revision is the last entry in the rpimodel value.
        else:
            self.rpi_rev = 'unknown'

    def set_os_version(self):
        """ Establish the version of operating system.
            Outputs --------------------------------------------------------------------
            Sets :
                os_version_id   eg  12
                os_version_name eg  bookworm
                os_type         eg  debian
                os_bits         eg  64
                os_proc         eg  aarch64
                os_systemkey    eg  4/bookworm/64
                """
        self.os_version_id = None
        self.os_version_name = None
        self.os_type = None
        for line in self.osCmd('cat /etc/os-release'):
            if len(line) > 0:
                elements = line.split('=')
                if elements[0] == 'VERSION_ID': self.os_version_id = int(elements[1].replace('"',''))
                elif elements[0] == 'VERSION_CODENAME': self.os_version_name = elements[1]
                elif elements[0] == 'ID': self.os_type = elements[1]
        self.os_bits = int(self.osCmd('getconf LONG_BIT')[0]) # Check 32 vs 64 bit O/S
        self.os_proc = self.osCmd('uname -m')[0]
        self.os_systemkey = self.rpi_num + "/" + self.os_version_name + "/" + str(self.os_bits)
        
    def native_camera_driver(self):
        """ Choose the native camera driver expected for this hardware/os combination. 
            Outputs ---------------------------------------------------------------------
            Sets: self.camera_driver """
        if self.os_version_name in hardware.RASPISTILL_SYSTEMS: self.camera_driver = 'raspistill'
        else: self.camera_driver = 'libcamera' # 'bullseye' and 'bookworm' come with libcamera installed.
        self.Log(self.os_version_name,"O/S found, assuming camera driver is",self.camera_driver,terminal=False)

    def i2c_enabled(self): 
        """ Return TRUE if i2c is enabled."""
        #lines = osCmd('sudo i2cdetect -y 1')
        result = False
        returncode = osCmdCode('sudo i2cdetect -y 1')
        if returncode == 0: # This command will only succeed if i2c is enabled.
            result = True
        return result

    def spi_enabled(self):
        """ Return TRUE if SPI is enabled. """
        lines = osCmd('lsmod')
        result = False
        for line in lines:
            if 'spi_' in line:
                result = True
                break
        return result
        
    def hardware_is_supported(self,allow_fail=True):
        """ Return TRUE if the hardware and OS combination is valid. 
            else return FALSE, and raise an error.
            Parameters ------------------------------------------------------------------
            allow_fail: TRUE the program will terminate with an exception if the hardware is NOT supported.
                        FALSE the program will continue even if the hardware is not supported.
            Outputs ---------------------------------------------------------------------
            Returns: TRUE/FALSE 
            Sets: self.system_supported            """
        if self.os_systemkey in hardware.SUPPORTED_SYSTEMS:
            self.Log(self.program_title,"OK to run under",self.os_systemkey,terminal=False)
            self.system_supported = True
            result = True
        else: # Cannot proceed, wrong O/S & hardware combination.
            self.Log(self.program_title,"is only designed to run under",hardware.SUPPORTED_SYSTEMS,level='error',terminal=True)
            self.Log(self.program_title,"is not designed to run under",self.os_version_name,self.os_bits,"bit on",self.rpi_model,"(",self.os_systemkey,")",level='error',terminal=True)
            self.system_supported = False
            if allow_fail: raise Exception(str(self.program_title) + " is not designed to run under this combination of hardware and O/S.")
            result = False
        return result

Hardware = hardware(oscmd=osCmd,logger=MainLog) # Create instance of the hardware class. Identifies what we are dealing with.     
if not Hardware.hardware_is_supported():
    raise Exception(str(Hardware.program_title) + " is not designed to run under this combination of hardware and O/S.")

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
    MainLog.Log("Pilomar is developed with Skyfield version 1.39: This version",str(SkyfieldVersion[0]) + "." + str(SkyfieldVersion[1]),terminal=False)

textcolor.GetTermType()
MainLog.Log("Terminal type:", textcolor.TermType, textcolor.Mode,terminal=False)

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

    def __init__(self,filename,logger=None):
        self.SetLogger(logger=logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self._Dictionary = {} # The json parameter file loaded from disc at start, saved to disc at end.
        self._Defaults = {} # Maintain a list of default values, used to highlight changes when reviewing parameters.
        self.ParamFileName = filename # The disc copy of the parameter file. This is overwritten if the program completes correctly.
        self.LoadParameters()
        self.RequireRestart = False # These parameters are safe to consistently configure microcontroller and run observations.
                                    # Set to FALSE if they change and require a software restart.
        
    def LoadParameters(self):
        """ If parameter file exists, it's loaded into the parameters. 
            If anything is missing it's defaulted to initial values. 
            Called during __init__(), and can be called again if needed. """
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
        self.Owner = self.GetParmVal('Owner','telescope owner') # Who owns the telescope? This can be saved in image metadata.
        self.ImagePrivacy = self.GetParmVal('ImagePrivacy','high') # 'low','med','high' privacy for meta data stored in images.
        self.StepperDriverData = self.GetParmVal('StepperDriverData',sdd) # Dictionary containing stepper driver types and parameters.
        self.BoardType = self.GetParmVal('BoardType',None) # Define alternative motorcontroller board type here. Changes behaviour of board/microcontroller.
        self.BatchSize = self.GetParmVal('BatchSize',100) # How many photos to take in a batch.
        self.UARTOverride = self.GetParmVal('UARTOverride',None) # If set, this contains the UART device string to use for opening UART comms (eg '/dev/ttyAMA0'. If None, the software chooses.
        self.ControlBatchSize = self.GetParmVal('ControlBatchSize',20) # How many images to capture in each 'control set' (DARK, BIAS etc). High values offer limited gains.
        self.ColorScheme = self.GetParmVal('ColorScheme','green') # What colour scheme to use? (green, blue, red, white)
        
        # The following parameters control hardware features.
        self.CameraEnabled = self.GetParmVal('CameraEnabled',True) # Is the camera on?
        self.BacklashEnabled = self.GetParmVal('BacklashEnabled',False) # ENABLE to let the motors make extra moves to cope with gear backlash.
        self.FaultSensitive = self.GetParmVal('FaultSensitive',False) # ENABLE to make motorcontroller respect the DRV8825 'fault' signal.
        self.MctlLedStatus = self.GetParmVal('MctlLedStatus',True) # Turn on STATUS LEDs on microcontroller.
        self.ObservationResetsMctl = self.GetParmVal('ObservationResetsMctl',False) # Force a reset of the microcontroller each time a new ObservationRun begins?
        self.ObservationStopPin = self.GetParmVal('ObservationStopPin',25,oldnames=['StopPin']) # Which RPi4 GPIO pin is used as the OBSERVATION STOP button? (Not an EMERGENCY STOP!)
        self.IRControlPin = self.GetParmVal('IRControlPin',None) # If using the Arducam High Quality camera with IR Cutoff control you can assign this to GP4.
        self.IRCutoff = self.GetParmVal('IRCutoff',True) # Is the IR Cutoff filter in place? TRUE : Camera does not see IR. FALSE: Camera sees IR too.

        self.TuneOn32Bit = self.GetParmVal('TuneOn32Bit',True) # If running on 32bit O/S tune for performance.
        
        # MctlResetPin controls power OR reset signal to microcontroller.
        # On 1st generation boards it is GP4.
        # On later boards it is GP23 because GP4 is now available for the Arducam HiQuality camera with switchable IR Cutoff filter.
        self.MctlResetPin = self.GetParmVal('MctlResetPin',4) # Which RPi4 GPIO pin is used to RESET the microcontroller? On first gen boards.
        self.UartRxQueueLimit = self.GetParmVal('UartRxQueueLimit',50) # How many messages can be held in the input queue from the Microcontroller? Kill older entries.
        # Azimuth motor parameters.
        self.MinAzimuthAngle = self.GetParmVal('MinAzimuthAngle',0)
        self.MaxAzimuthAngle = min(self.GetParmVal('MaxAzimuthAngle',360),360)
        self.AzimuthDriver = self.GetParmVal('AzimuthDriver','drv8825') # Which steppermotor driver does the Azimuth motor use?
        self.AzimuthGearRatio = self.GetParmVal('AzimuthGearRatio',240)
        self.AzimuthMotorStepsPerRev = self.GetParmVal('AzimuthMotorStepsPerRev',400) # Full step count for the motor (ignore any microstepping multiplier)
        self.AzimuthSlewMicrostepRatio = self.GetParmVal('AzimuthSlewMicrostepRatio',1) # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
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
        self.AltitudeMicrostepRatio = self.GetParmVal('AltitudeMicrostepRatio',1) # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.AltitudeSlewMicrostepRatio = self.GetParmVal('AltitudeSlewMicrostepRatio',1) # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.AltitudeRestAngle = self.GetParmVal('AltitudeRestAngle',0.0)
        self.AltitudeBacklashAngle = self.GetParmVal('AltitudeBacklashAngle',0.0)
        self.AltitudeOrientation = self.GetParmVal('AltitudeOrientation',-1)
        self.AltitudeLimitAngle = self.GetParmVal('AltitudeLimitAngle',None) # Set motion limit for rotation.
        # Motor pulse speed and acceleration (applies to both motors)
        self.FastTime = self.GetParmVal('FastTime',0.001) # Fastest pulse to the motor STEP signal. (Full speed in large move.)
        self.SlowTime = self.GetParmVal('SlowTime',0.05) # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
        self.TimeDelta = self.GetParmVal('TimeDelta',0.003) # Acceleration rate for the motor STEP signal. 
        speedlist = {
            'Slow':    {'label':'Slow (4ms / step)', 'FastTime':0.002,  'SlowTime':0.05, 'TimeDelta':0.003},
            'Medium':  {'label':'Medium (2ms / step)', 'FastTime':0.001,  'SlowTime':0.05, 'TimeDelta':0.003},
            'Fast':    {'label':'Fast (1ms / step)', 'FastTime':0.0005, 'SlowTime':0.05, 'TimeDelta':0.003},
            'Turbo':   {'label':'Turbo (0.2ms / step)', 'FastTime':0.0001, 'SlowTime':0.05, 'TimeDelta':0.003}
        }
        self.SpeedList = self.GetParmVal('SpeedList',speedlist) # Motor step speed profiles.
        

        self.MotorStatusDelay = self.GetParmVal('MotorStatusDelay',10) # Microcontroller should send motor status messages every 'xxx' seconds. (Don't overload UART comms!)
        self.SlewEnabled = self.GetParmVal('SlewEnabled',False) # Do we allow microstepping to be replaced by FULL STEPS when moving large distances?
        self.TraceMove = self.GetParmVal('TraceMove',False,oldnames=['TraceMotor']) # Does the microcontroller send extra development log messages back from the motors?
        self.OptimiseMoves = self.GetParmVal('OptimiseMoves',False) # Can the motorcontroller optimise large moves? (ie switch direction if it's faster)
        self.MctlCommsTimeout = self.GetParmVal('MctlCommsTimeout',120) # How many seconds of inactivity before resetting microcontroller communication?
        self.UseUSBStorage = self.GetParmVal('UseUSBStorage',True) # If USB storage is mounted then images are stored there instead of the SD card.
        self.SDPath = self.GetParmVal('SDPath','/') # The 'path' used by discmonitor for monitoring space on the SD card.
        self.USBPath = self.GetParmVal('USBPath','/media/pi') # The 'path' used by discmonitor for monitoring space on attached USB storage.
        self.FastFlush = self.GetParmVal('FastFlush',False) # When TRUE disc writes are flushed immediately - That hits the SD card hard, but may catch more info for fatal errors.
        self.FastImageCapture = self.GetParmVal('FastImageCapture',False) # Do not extract raw data during observation, do it later. Captures data more quickly.
        self.HorizonAltitude = self.GetParmVal('HorizonAltitude',0.0) # What altitude angle is considered the horizon? Observations cannot go below this even if the motor allows it.
        self._Horizon = max(self.HorizonAltitude,self.MinAltitudeAngle) # Targets will not be followed below this altitude.
        
        # The following parameters decide which types of images are stored.
        self.CameraSaveJpg = self.GetParmVal('CameraSaveJpg',True) # Save the jpg image from observations, but will strip out the embedded RAW data.
        self.CameraSaveDng = self.GetParmVal('CameraSaveDng',True) # Save the raw image data as .dng file.
        self.CameraSaveFits = self.GetParmVal('CameraSaveFits',False) # Save the raw image data as a .fit file. # Needs libcamera & Picamera2.
        if self.CameraSaveJpg or self.CameraSaveDng or self.CameraSaveFits: pass # OK
        else: self.Log("No image types are saved according to the parameters.",level='warning')
        
        cameracommands = {
            'raspistill': { # These are the default commands for raspistill captures.
                'light':'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}',
                'dark':'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}',
                'bias':'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}',
                'flat':'raspistill -o {&output} -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0',
                'darkflat':'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}',
                'auto':'raspistill -o {&output} -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height}',
                'tracking':'raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ss {&shutter}', 
                'imagetypes':['jpg','dng'],
                'osnames':['buster'],
                'rawswitch':'-r'},
            'pilomarfits': { # If picamera2 and astropy are installed you can get 'fits' images with pilomarfits.py
                'light':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477.json --analoggain 16.0',
                'dark':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477.json --analoggain 16.0',
                'bias':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477.json --analoggain 16.0',
                'flat':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --tuning-file imx477.json --analoggain 16.0',
                'darkflat':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477.json --analoggain 16.0',
                'auto':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --tuning-file imx477.json --analoggain 16.0',
                'tracking':'python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477.json --analoggain 16.0',
                'imagetypes':['jpg','fits'],
                'osnames':['bullseye','bookworm'],
                'rawswitch':'--raw'}, # No raw image extraction switch needed.
            'libcamera': { # These are the default Commands for libcamera-still captures.
                'light':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}',
                'dark':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}',
                'bias':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}',
                'flat':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0',
                'darkflat':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}',
                'auto':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off',
                'tracking':'rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --shutter {&shutter}',
                'imagetypes':['jpg','dng'],
                'osnames':['bullseye','bookworm'],
                'rawswitch':'--raw'}, # How do you turn on RAW image extraction?
            }
        self.CameraCommands = self.GetParmVal('CameraCommands',cameracommands)
        for key,value in self.CameraCommands.items():
            if not 'livepreview' in value: # Livepreview command is not in the list yet. Add it.
                if key == 'raspistill': value['livepreview'] = 'raspistill --preview 100,100,812,608 --timeout 100000 --focus' # *Q* To test: "raspistill -t 0 -roi 0.4,0.4,0.2,0.2 -vf -hf"
                else: value['livepreview'] = 'libcamera-still --preview 100,100,812,608 --timeout 100000 --info-text %focus'
        self.DisableCleanup = self.GetParmVal('DisableCleanup',True) # Set to TRUE to disable the on-chip cleanup. (More pure RAW image is captured.) # Applies to raspistill only!
        self.CameraDriver = self.GetParmVal('CameraDriver',Hardware.camera_driver) # Set outside the Parameters object.
        self.SetCameraDriver(self.CameraDriver) # Load appropriate camera commands into working fields.
        
        # The following parameters control DriftTracking activity.
        self.UseTracking = self.GetParmVal('UseTracking',True) # TRUE = Use image tracking. FALSE = No tracking.
        # LatestTrackingFilter and RunFilterScript are new features being tested. If used, they override PrepImagesForTracking and TrackingUrbanFilter parameters.
        self.TrackingTargetGrayscale = self.GetParmVal('TrackingTargetGrayscale',False) # Generate grayscale tracking target?
        # The following 2 parameters are replaced by the general purpose LatestTrackingFilter parameter. This upgrades automatically.
        PrepImagesForTracking = self.GetParmVal('PrepImagesForTracking',False) # TRUE = latest image is simplified. FALSE = latest image is used as is.
        TrackingUrbanFilter = self.GetParmVal('TrackingUrbanFilter',False) # Apply the 'UrbanFilter' method to live images before passing to the drift tracking calculation.
        self.LatestTrackingFilter = self.GetParmVal("LatestTrackingFilter",None) # Which (if any) script is run through pilomarimage.RunFilterScript() when LATEST tracking images are taken.
        if self.LatestTrackingFilter is None: # No LatestTrackingFilter is set. Look for old parameters to upgrade.
            if PrepImagesForTracking: # The old PrepImagesForTracking was in use, convert this to the EnhanceStars filter script.
                self.LatestTrackingFilter = 'EnhanceStars' # This is the equivalent to the previous behaviour.
                self.Log("parameters.__init__(): Upgrading old PrepImagesForTracking parameter to new LatestTrackingFilter parameter.",terminal=True)
            elif TrackingUrbanFilter: # The old TrackingUrbanFilter was in use, convert this to the UrbanFilter script.
                self.LatestTrackingFilter = 'UrbanFilter'
                self.Log("parameters.__init__(): Upgrading old TrackingUrbanFilter parameter to new LatestTrackingFilter parameter.",terminal=True)
        self.TrackingDebug = self.GetParmVal('TrackingDebug',False) # Produce tracking development/debug artifacts?
        self.FilterTestImage = self.GetParmVal('FilterTestImage',None) # Remember where source images are found for testing filters.
        self.TrackingMatchThreshold = self.GetParmVal('TrackingMatchThreshold',5) # Minimum number of stars that must be matched before drift calculation is trusted.
        self.MinimumDriftCorrection = self.GetParmVal('MinimumDriftCorrection',50) # Minimum number of drift pixels that's worth compensating. Doesn't need to be too small.
        self.TrackingInterval = self.GetParmVal('TrackingInterval',600) # How many seconds between each target tracking check?
        self.TrackingExposureSeconds = self.GetParmVal('TrackingExposureSeconds',5.0) # How long is the exposure when capturing a tracking photo. It must be standardised rather than using the variable 'light' image exposure time.
        self.TrackingMapSpan = self.GetParmVal('TrackingMapSpan',1.0) # Tracking master target map is this times larger on each axis than the camera field of view (min 1.0)
        self.TrackingMapSpan = max(self.TrackingMapSpan,1.0)
        self.TrackingZoneMatches = self.GetParmVal('TrackingZoneMatches',3) # After 3 matching zones found in master map it's OK to stop searching.
        self.TrackingZoneShift = self.GetParmVal('TrackingZoneShift',0.33) # When splitting master map into sub-target maps, what percentage 'shift' does each zone have from the previous?
        self.TrackingZoneShift = max(0.1,self.TrackingZoneShift) # Must be at least 10%
        self.ShowPGCEntries = self.GetParmVal('ShowPGCEntries',False) # The NGC catalog includes NGC, IC and PGC items. The PGC list is large and slow to process, but generates a more realistic star field.
        self.GeneratePreview = self.GetParmVal('GeneratePreview',True) # TRUE = Preview images are generated periodically, and can be turned into AVI file when observation ends.
        self.GeneratePreviewVideo = self.GetParmVal('GeneratePreviewVideo',True) # TRUE = IF GeneratePreview enabled, this will save a VIDEO of the images too.
        self.GenerateKeogram = self.GetParmVal('GenerateKeogram',False) # TRUE = Keogram is generated at the end of all observations automatically. Aurora always does.
        self.InitialGoTo = self.GetParmVal('InitialGoTo',True) # Perform initial GOTO before downloading the trajectory. (Eases comms with microcontroller.)
        self.TargetInclusionRadius = self.GetParmVal('TargetInclusionRadius',15) # Angle (radius) for inclusion of neighbouring stars when generating target image.
        # The following parameters control how bright the stars are if they are selected in the LocalStars or ConstellationStars lists.
        self.LocalStarsMagnitude = self.GetParmVal('LocalStarsMagnitude',10.0) # Max magnitude when selecting local stars.
        self.ConstellationStarsMagnitude = self.GetParmVal('ConstellationStarsMagnitude',7.0) # Max magnitude when selecting stars in a constellation.
        self.TargetMinMagnitude = self.GetParmVal('TargetMinMagnitude',9.0) # Minimum magnitude for stars to display. At a 2 second exposure, Magnitude 5.0 is a good value, at 5 seconds, Mag 9, over 10 seconds, Mag 10 is about as good as it gets.
        self.MarkAllStars = self.GetParmVal('MarkAllStars',False) # When TRUE ALL stars in the LocalStars cache below TargetMinMagnitude are minimally indicated on the images.
        self.UseLiveLocation = self.GetParmVal('UseLiveLocation',True) # Use live target location rather than last reported location for image processing.
        self.DebugMode = self.GetParmVal('DebugMode',True) # In DebugMode ObservationRun does not display the status windows. This makes error messages easier to read.
        self.KeyboardScanDelay = self.GetParmVal('KeyboardScanDelay',2) # How many seconds between keyboard scans when running an observation?
        self.SessionHistoryLimit = self.GetParmVal('SessionHistoryLimit',30) # How many recent session targets are kept in history?

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

        # Warn if magnitude limits are incorrectly set.
        if self.TargetMinMagnitude > self.LocalStarsMagnitude:
            self.Log("parameters.__init__(): TargetMinMagnitude",self.TargetMinMagnitude,"is dimmer than stars listed in Hipparcos catalog (",self.LocalStarsMagnitude,").",level='warning',terminal=True)

        # The following parameters set position and localisation.
        # List of locations, used for examples, but can also be extended if you want to store your own set of locations.
        location_list = { # Set default values. Edit the parameter file to add your own entries.
            'Australia,Alice Springs': {"HomeLat": "23.810 S", "HomeLon": "133.902 E", "LocalTZ": "utc"},
            'France,Paris':            {"HomeLat": "48.864 N", "HomeLon":   "2.349 E", "LocalTZ": "utc"},
            'Japan,Tokyo':             {"HomeLat": "35.652 N", "HomeLon": "139.839 E", "LocalTZ": "utc"},
            'USA,Atlanta':             {"HomeLat": "33.753 N", "HomeLon":  "84.386 W", "LocalTZ": "utc"}
        }
        self.LocationList = self.GetParmVal('LocationList',location_list) # List of home locations.
        self.LocalTZ = self.GetParmVal('LocalTZ','UTC') # What's the local timezone (pytz values). pytz.all_timezones() lists all available. Sets display timezone.
        self.DisplayTZ = self.GetParmVal('DisplayTZ','UTC') # The dashboard can switch between timezones.
        if self.LocalTZ == 'utc': self.LocalTZ = 'UTC' # Fix any earlier case error.
        if self.DisplayTZ == 'utc': self.DisplayTZ = 'UTC'
        if not self.LocalTZ in pytz.all_timezones: # The timezone is not recognised.
            self.Log('parameters.LoadParameters(): Invalid LocalTZ',self.LocalTZ,level='warning')
            lines = ['INVALID LocalTZ PARAMETER',
                     ' ',
                     'The Parameter file defines LocalTZ as ' + str(self.LocalTZ),
                     ' ',
                     'This is not recognised. It has been reset to UTC',
                     'for safety. You can select a new LocalTZ value from the',
                     'Miscellaneous tools menu.']
            self.LocalTZ = 'UTC' # Reset to safe default.
            textcolor.TextBox(lines,fg=textcolor.BLACK,bg=textcolor.YELLOW,justify='c')
        self.HomeLat = self.GetParmVal('HomeLat',None) # Latitude of the observer.
        self.HomeLon = self.GetParmVal('HomeLon',None) # Longitude of the observer.
        if self.HomeLat == None or self.HomeLon == None:
            self.ExplainLocationRequest() # Explain that values need to be given.
            if not self.ChooseHome(): # Prompt and set home location.
               # No choice was made.
               self.Log("Home location was not set. Please set it manually in the parameter file.",level='error')
               exit() # Quit the program.
        self.HomeAltitude = self.GetParmVal('HomeAltitude',100) # Altitude of the observer in metres.
        self.EvaluateHomeLocation()
    
        # The following parameters dictate how various graphical images are generated.
        self.MarkupInterval = self.GetParmVal('MarkupInterval',300) # How often do we generate a preview image (seconds).
        self.MarkupShowNames = self.GetParmVal('MarkupShowNames',True,oldnames=['MarkupShowLabels']) # Add names to markup images, such as star names.
        self.MarkupShowCoordinates = self.GetParmVal('MarkupShowCoordinates',True,oldnames=['MarkupShowLabels']) # Add coordinates to markup images, such as Ra/Dec and AltAz.
        self.MarkupStarLabelLimit = self.GetParmVal('MarkupStarLabelLimit',100) # Maximum number of star labels to add to the image. Keep it readable.
        self.MarkupAvoidCollisions = self.GetParmVal('MarkupAvoidCollisions',True) # Does image markup avoid text overlaps? Star labels are skipped if they overwrite an existing one.
        self.FakeStars = self.GetParmVal('FakeStars',True) # Do simulated images includes stars, nebulae etc?
        self.FakeNoise = self.GetParmVal('FakeNoise',False) # Do simulated images also simulate sensor noise?
        self.FakeField = self.GetParmVal('FakeField',False) # Do simulated images also simulate electronic field noise?
        self.FakePollution = self.GetParmVal('FakePollution',False) # Do simulated images also simulate light pollution? # Don't run this on small 3Bs!
        self.FakeAurora = self.GetParmVal('FakeAurora',True) # Does simulated aurora target actually fake an aurora?
        #self.FakeMeteor = self.GetParmVal('FakeMeteor',True) # Do simulated images also fake meteor streaks?
        self.FakeMeteorPercent = self.GetParmVal('FakeMeteorPercent',2) # What percentage of simulated images get fake meteor streaks?

        # The following parameters describe the camera and lens.
        self.LensLength = self.GetParmVal('LensLength',16.0) # Focal length of lens
        self.LensHorizontalFov = self.GetParmVal('LensHorizontalFov',21.8) # Degrees FoV horizontally
        self.LensVerticalFov = self.GetParmVal('LensVerticalFov',16.4) # Degrees FoV vertically.
        self.SensorType = self.GetParmVal('SensorType','imx477') # Sensor type. 
        self.EquivMultiplier = self.GetParmVal('EquivMultiplier',5.6) # Multiplier to get 35mm equivelent lens focal length.
        self.IRFilter = self.GetParmVal('IRFilter',True) # Is Infrared filter fitted?
        self.PollutionFilter = self.GetParmVal('PollutionFilter',False) # Is light pollution filter fitted?
        self.SolarFilter = self.GetParmVal('SolarFilter',False) # Is a solar filter fitted?
        lenslist = {
            '6mm': {'label':' 6mm lens (34mm equivalent)',  'LensLength': 6.0, 'LensHorizontalFov': 63.0,'LensVerticalFov': 47.4},
            '16mm':{'label':'16mm lens (90mm equivalent)',  'LensLength': 16.0,'LensHorizontalFov': 21.8,'LensVerticalFov': 16.4},
            '25mm':{'label':'25mm lens (140mm equivalent)', 'LensLength': 25.0,'LensHorizontalFov': 14.5,'LensVerticalFov': 10.5},
            '35mm':{'label':'35mm lens (195mm equivalent)', 'LensLength': 35.0,'LensHorizontalFov': 10.5,'LensVerticalFov': 7.9},
            '50mm':{'label':'50mm lens (280mm equivalent)', 'LensLength': 50.0,'LensHorizontalFov': 7.0, 'LensVerticalFov': 5.2}
        }
        self.LensList = self.GetParmVal('LensList',lenslist) # List of defined lenses.
        
        # The following parameters dictate how the trajectory is calculated for the motorcontroller.
        self.TrajectoryWindow = self.GetParmVal('TrajectoryWindow',1200) # How many seconds into the future should the motor trajectory last?
        self.UseDynamicTrajectoryPeriods = self.GetParmVal('UseDynamicTrajectoryPeriods',True) # Can we use flexible time periods in the trajectory plan?
        
        self.ScanForMeteors = self.GetParmVal('ScanForMeteors',True) # Scan light images for streaks, report them if found.
        self.MinSatelliteAltitude = self.GetParmVal('MinSatelliteAltitude',30) # Satellite's are only considered to RISE if they will culminate above this altitude. (Else too brief and low to see)
        self.AuroraCameraAltitude = self.GetParmVal('AuroraCameraAltitude',5) # When selecting an AURORA target this is the altitude for the camera position.
        self.SuggestionMagnitude = self.GetParmVal('SuggestionMagnitude',11) # Don't suggest targets dimmer than this.
        self.SuggestionPixels = self.GetParmVal('SuggestionPixels',100) # Don't suggest targets smaller than this.
        self.SavedUTC = self.GetParmVal('SavedUTC',NowUTC()) # When were the parameters written?

        # Load/Save image filters for pilomarimage objects.
        self.FilterScripts = self.GetParmVal('FilterScripts',pilomarimage.FILTERSCRIPTS) # Default is the initial set of filter scripts defined in the pilomarimage class.
        pilomarimage.FILTERSCRIPTS = self.FilterScripts # Now assign whatever we have loaded back to pilomarimage.

    def EvaluateHomeLocation(self):
        """ Convert 'human entered' home latitude and longitude into the numeric values that the program needs. """
        self._HomeLatVal = 0.0
        if self.HomeLat != None:
            self._HomeLatVal = float(self.HomeLat.split(" ")[0]) # Convert to float value.
            if self.HomeLat.split(" ")[1] == "S": self._HomeLatVal = self._HomeLatVal * -1 # -ve for southern hemisphere in Skyfield.
        self._HomeLonVal = 0.0
        if self.HomeLon != None:
            self._HomeLonVal = float(self.HomeLon.split(" ")[0]) # Convert to float value.
            if self.HomeLon.split(" ")[1] == "W": self._HomeLonVal = self._HomeLonVal * -1 # -ve for western hemisphere in Skyfield.
        self.Log("Parameters: Home:", self.HomeLat, self.HomeLon, ":", self._HomeLatVal, self._HomeLonVal,terminal=False)

    def ExplainLocationRequest(self):
        # Home location is not yet set. Save the parameter file for editing then quit.
        # The user has to manually enter the home latitude and longitude into the paramter file.
        lines = ['YOUR HOME LOCATION IS NOT SET',
                 ' ',
                 'Give the coordinates of YOUR location now.',
                 ' ']
        textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.RED,justify='c')
        print('')
        print('eg:')
        print(textcolor.white('HomeLat'.ljust(16)),textcolor.white('HomeLon'.ljust(16)),textcolor.white('Location'))
        for key,value in self.LocationList.items():
            print(value['HomeLat'].ljust(16),value['HomeLon'].ljust(16),key)

    def ChooseHome(self):
        """ Present a list of known home locations to choose from, let the user create their own too. """
        # Present list of known locations.
        location_list = {}
        for key,value in self.LocationList.items():
            location_list[key] = {'label':key, 'value':key, 'HomeLat':value['HomeLat'], 'HomeLon':value['HomeLon']}
        # Add 'new' as an option.
        location_list['Add new'] = {'label':'Add new','value':'AddNew','bold':True}
        # Choose option.
        LocationMenu = optionmenu(location_list,'Select home location',titlefg=self.MenuTitleFG,titlebg=self.MenuTitleBG)
        option, found = LocationMenu.Prompt() # Ask the user to select an option from the menu.
        if found: # A choice was made.
            MainLog.Log("ChooseHome: Chose:",option)
        else: # A choice was NOT made.
            MainLog.Log("ChooseHome: No choice made.",terminal=False)
            return False
        if option == 'AddNew': # Prompt the user for the values, add it to the official list.
            # Save 'new' in location list.
            new_name,self.HomeLat,self.HomeLon = self.PromptForLocation()
            self.LocationList[new_name] = {'HomeLat':self.HomeLat, 'HomeLon':self.HomeLon}
        else: # Select from existing list.
            self.HomeLat = location_list[option]['HomeLat']
            self.HomeLon = location_list[option]['HomeLon']
        return True

    def PromptForLocation(self):
        """ Prompt for name, lat and lon of home location. """
        home_name = None
        while home_name == None:
            home_name = input(textcolor.cyan("Name of location: "))
            home_name = home_name.strip()
        home_lat = self.PromptForAngle('latitude',points=['N','S'],min_angle=0,max_angle=180,default=None)
        home_lon = self.PromptForAngle('longitude',points=['E','W'],min_angle=0,max_angle=180,default=None)
        return home_name, home_lat, home_lon

    def PromptForAngle(self,label,points=['N','S'],min_angle=0,max_angle=90,default=None):
        """ Prompt the user for an angle and validate it.
            This is used for the setting the home location. """
        print(textcolor.yellow("Please provide the",label,"position"))
        prompt = "Enter " + label + " (" + str(min_angle) + " to " + str(max_angle) + " " + str(points) + ") : "
        result = None
        while result == None:
            temp = input(textcolor.cyan(prompt))
            temp = temp.strip() # Remove whitespace
            if len(temp) == 0: # Use default
                result = default
                continue
            tempitems = temp.split(' ') # Split to components.
            if len(tempitems) != 2: # Wrong number of elements.
                print(textcolor.red("Must be in format   'ddd.dddddd X'   eg:",str(max_angle),points[0]))
                continue
            tempfloat = TextToFloat(tempitems[0])
            tempdir = tempitems[1].upper()
            if not tempdir in points:
                print(textcolor.red("Cardinal point must be one of",points))
                continue # Repeat prompt
            if tempfloat < min_angle or tempfloat > max_angle:
                print(textcolor.red("Angle must be between",min_angle,"and",max_angle))
                continue # Repeat prompt
            result = str(tempfloat) + " " + tempdir
        return result            

    def SetCameraDriver(self,cameradriver):
        """ This will set cameradriver (raspistill,libcamera,pilomarfits) then 
            load the correct camera commands from the Parameters table. """
        if cameradriver in self.CameraCommands: # CameraDriver is recognised.
            self.CameraDriver = cameradriver # Select the camera driver.
            self.CameraImageTypes = self.CameraCommands[self.CameraDriver]['imagetypes']
            self._CameraLivePreviewCommand = self.CameraCommands[self.CameraDriver]['livepreview'] # Camera command for producing live preview image.
            self._CameraLightCommand = self.CameraCommands[self.CameraDriver]['light'] # Camera settings for 'light' images.
            self._CameraDarkCommand = self.CameraCommands[self.CameraDriver]['dark'] # Camera settings for 'dark' images.
            self._CameraBiasCommand = self.CameraCommands[self.CameraDriver]['bias'] # Camera settings for 'bias' images.
            self._CameraFlatCommand = self.CameraCommands[self.CameraDriver]['flat'] # Camera settings for 'flat' images.
            self._CameraDarkFlatCommand = self.CameraCommands[self.CameraDriver]['darkflat'] # Camera settings for 'darkflat' images.
            self._CameraAutoCommand = self.CameraCommands[self.CameraDriver]['auto'] # Camera settings for 'auto' images.
            self._CameraTrackingCommand = self.CameraCommands[self.CameraDriver]['tracking'] # Camera settings for 'tracking' images.
            self._CameraRawSwitch = self.CameraCommands[self.CameraDriver]['rawswitch'] # How do you turn on RAW image extraction?
        else: # Camera driver is not recognised.
            MainLog.Log("**ERROR**: parameters.SetCameraDriver: Does not recognise:",cameradriver,level='error',terminal=True)
            exit()
        
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
                    self.Log("parameters.GetParmVal(",name,") migrating from",oldname,"with value",result,terminal=False)
                    break # Look no further.
        # Now get/initialise the current parameter name.
        result = self._Dictionary.get(name,result)
        if result != default: # Default value has been overridden.
            self.Log("parameters.GetParmVal(",name,") default",default,"overridden with",result,terminal=False)
        return result
               
    def ChooseColorScheme(self):
        """ Prompt for and set a standard color scheme. """
        ItemList = ['white','blue','green','red']
        objectchooser = listchooser(ItemList,compress=False) # Always show the full list.
        print (textcolor.yellow('Choose color scheme to apply.'))
        ChosenItem = objectchooser.Prompt()
        if ChosenItem is None: return # Nothing to change.
        else: self.SetColorScheme(ChosenItem)
        self.ShowColorScheme() # Show the current color scheme.
        PleaseRestart() # Show banner requesting a restart.
        return
        
    def ChooseColor(self):
        """ Prompt for color and update display characteristics to match. """
        # Prompt for color item to change.
        ItemList = ['MenuTitleFG','MenuTitleBG','MenuSubtitleFG','MenuSubtitleBG','TitleFG','TitleBG','TextFG','TextBG','TextGood','TextPoor','TextBad','BorderFG','BorderBG']
        objectchooser = listchooser(ItemList,compress=False) # Always show the full list.
        print (textcolor.yellow('Choose color item to change.'))
        ChosenItem = objectchooser.Prompt()
        if ChosenItem is None: return # Nothing to change.
        print (textcolor.yellow('Chosen',ChosenItem))
        print (textcolor.yellow('Available colors:-'))
        textcolor.listcolors()
        Result = None
        while Result is None:
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
        textcolor.TextBox('You must restart the program for these changes to take effect.',fg=textcolor.YELLOW,bg=textcolor.BLACK)
        return

    def SetColorScheme(self,scheme='green'):
        """ Given the name of a color scheme, 
            set the individual color items to their appropriate values. """
        if scheme == "white": # Chosen schemes.
            self.MenuTitleFG = textcolor.WHITE
            self.MenuTitleBG = textcolor.GREY50
            self.MenuSubtitleFG = textcolor.WHITE
            self.MenuSubtitleBG = textcolor.GREY30
            self.TitleFG = textcolor.WHITE
            self.TitleBG = textcolor.GREY30
            self.TextFG = textcolor.WHITE
            self.TextBG = textcolor.BLACK
            self.TextGood = textcolor.WHITE
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.RED
            self.BorderFG = textcolor.GREY66
            self.BorderBG = textcolor.BLACK
        elif scheme == "blue": # Chosen schemes.
            self.MenuTitleFG = textcolor.WHITE
            self.MenuTitleBG = textcolor.DEEPSKYBLUE4A
            self.MenuSubtitleFG = textcolor.BLACK
            self.MenuSubtitleBG = textcolor.DEEPSKYBLUE3
            self.TitleFG = textcolor.WHITE
            self.TitleBG = textcolor.DEEPSKYBLUE4A
            self.TextFG = textcolor.CYAN
            self.TextBG = textcolor.GREY15
            self.TextGood = textcolor.LIGHTSKYBLUE1
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.NAVYBLUE
            self.BorderBG = textcolor.GREY15
        elif scheme == "green": # Chosen schemes.
            self.MenuTitleFG = textcolor.LIME
            self.MenuTitleBG = textcolor.DARKGREEN
            self.MenuSubtitleFG = textcolor.BLACK
            self.MenuSubtitleBG = textcolor.GREEN
            self.TitleFG = textcolor.LIME
            self.TitleBG = textcolor.DARKGREEN
            self.TextFG = textcolor.GREEN
            self.TextBG = textcolor.GREY15
            self.TextGood = textcolor.LIGHTGREEN
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.DARKGREEN
            self.BorderBG = textcolor.GREY15
        elif scheme == "red": # Chosen schemes.
            self.MenuTitleFG = textcolor.WHITE
            self.MenuTitleBG = textcolor.DARKRED
            self.MenuSubtitleFG = textcolor.BLACK
            self.MenuSubtitleBG = textcolor.RED3
            self.TitleFG = textcolor.WHITE
            self.TitleBG = textcolor.RED3
            self.TextFG = textcolor.RED
            self.TextBG = textcolor.GREY15
            self.TextGood = textcolor.LIGHTPINK1
            self.TextPoor = textcolor.YELLOW
            self.TextBad = textcolor.ORANGERED1
            self.BorderFG = textcolor.DARKRED
            self.BorderBG = textcolor.GREY15
        else: return # Assume custom settings, don't override them.
        self.ColorScheme = scheme
        return

    def ShowColorScheme(self):
        """ Demonstrate current color scheme. """
        print(textcolor.yellow("Current color scheme (" + str(self.ColorScheme) + "):"))
        print(textcolor.fgbgcolor(self.MenuTitleFG,   self.MenuTitleBG,   " Menu title    "),self.MenuTitleFG,"/",self.MenuTitleBG)
        print(textcolor.fgbgcolor(self.MenuSubtitleFG,self.MenuSubtitleBG," Menu subtitle "),self.MenuSubtitleFG,"/",self.MenuSubtitleBG)
        print(textcolor.fgbgcolor(self.TitleFG,       self.TitleBG,       " Title         "),self.TitleFG,"/",self.TitleBG)
        print(textcolor.fgbgcolor(self.TextFG,        self.TextBG,        " Text          "),self.TextFG,"/",self.TextBG)
        print(textcolor.fgbgcolor(self.TextGood,      self.TextBG,        " Good value    "),self.TextGood,"/",self.TextBG)
        print(textcolor.fgbgcolor(self.TextPoor,      self.TextBG,        " Poor value    "),self.TextPoor,"/",self.TextBG)
        print(textcolor.fgbgcolor(self.TextBad,       self.TextBG,        " Bad value     "),self.TextBad,"/",self.TextBG)
        print(textcolor.fgbgcolor(self.BorderFG,      self.BorderBG,      " Border        "),self.BorderFG,"/",self.BorderBG)
        return

    def Show(self):
        """ List parameters. """
        print (textcolor.yellow("List parameters",ProgramTitle,VERSION,":"))
        print (textcolor.red("(*)"),"indicates a modified parameter value.")
        tempd = vars(self) # Load instance variables into a temporary dictionary.
        ignorelist = [method for method in dir(self) if callable(getattr(self, method))] # Don't export callable attributes (= methods).
        ignorelist.append('Logger') # Ignore the Logger attribute too.
        for key,value in tempd.items():
            if key.startswith('_'): continue # Ignore internals.
            if key in ignorelist: continue # Ignore the link to the Log instance.
            defaultflag = '' # Mark if the value is not the default.
            if type(value) == dict: # Don't show dictionaries, they can be large.
                if key in self._Defaults: # A default value is known. 
                    if self._Defaults[key] != value: # The default is different to the current value.
                        defaultflag = textcolor.red(' (*) Has changed from default.')
                print (textcolor.yellow(key.rjust(30)) + " : " + textcolor.yellow("dictionary " + defaultflag + "(for detail open in editor)"))
            else:
                if key in self._Defaults: # A default value is known.
                    if self._Defaults[key] != value: # The default is different to the current value.
                        defaultflag = textcolor.red(' (*) Was ' + str(self._Defaults[key]))
                print (textcolor.yellow(key.rjust(30)) + " : " + str(value) + defaultflag)
        print("")
        print("Any timestamps will be in UTC")
        input(textcolor.cyan("Press [enter] to continue:"))

# Establish the filename of the parameters file that will be loaded.
ParameterFileName = ProjectRoot + '/data/' + ProgramTitle + '_params.json'
Parameters = parameters(filename=ParameterFileName,logger=MainLog) # Create and load parameters.

# Set the log file flush strategy from the parameter file.
MainLog.FastFlush = CamLog.FastFlush = Parameters.FastFlush

# Issue any warnings about specific parameter settings.
if Parameters.HomeLat is None or Parameters.HomeLon is None: 
    # This check is only in case the user did not provide values when prompted as the parameters were loaded.
    Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
    lines = ['HOME LOCATION IS NOT SET',
             ' ',
             Parameters.ParamFileName,
             ' ',
             'Edit the HomeLat and HomeLon values in the parameter file.',
             'Give the co-ordinates of your location.',
             'Then restart this program.']
    textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.RED,justify='c')
    ExplainLocationRequest()
    exit() # Quit the program.

if Parameters._HomeLatVal < 0 and Parameters.OptimiseMoves == False: # We're in the Southern Hemisphere.
    linelist = ["Home Latitude (" + str(Parameters._HomeLatVal) + DegreeSymbol + ") is in the Southern Hemisphere.",
                "NOTE: Pi-lomar may perform an unwinding manoeuvre as targets pass through due North.",
                "      This is normal behaviour, but will pause image capture while it happens.",
                "Consider enabling the OptimiseMoves and/or SlewEnabled parameters to mitigate this."]
    textcolor.TextBox(linelist,fg=textcolor.YELLOW,bg=textcolor.BLACK)
if abs(Parameters._HomeLatVal) >= 90.0: # Things break down at the poles.
    linelist = ["Home Latitude (" + str(Parameters._HomeLatVal) + DegreeSymbol + ") is at a pole.",
                "Please use the 0" + DegreeSymbol + " longitude line as due North/South."]
    textcolor.TextBox(linelist,fg=textcolor.YELLOW,bg=textcolor.BLACK)

if Parameters.SlewEnabled: # If allowed to mix full and microsteps, warn the user.
    MainLog.Log("SlewEnabled: The telescope can make large moves more quickly.",terminal=True)
    
if Parameters.OptimiseMoves: # If allowed to optimise moves, warn the user.
    MainLog.Log("OptimiseMoves IS ENABLED: Continuous rotation in the same direction may eventually twist the power cables.",level='warning',terminal=False)
    print(textcolor.orange("OptimiseMoves IS ENABLED: Continuous rotation in the same direction may eventually twist the power cables.",invert=True))

# Create global timers.
PreviewTimer = timer(period=Parameters.MarkupInterval) # ObservationRun will generate a Preview image every nnn seconds. 

# Shortcuts to color scheme for displays.
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

# ------------------------------------------------------------------------------------------------------

# Create a timer for the keyboard scanner.
KeyboardTimer = timer(period=Parameters.KeyboardScanDelay) # This says how frequently the keyboard is checked for input during observations.

# ------------------------------------------------------------------------------------------------------

def RestartRequired():
    lines = ["THE PARAMETER FILE HAS BEEN EDITED",
             " ",
             "For safety you must restart the software to make",
             "sure all new values are consistently applied."]
    textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK,justify="c")
    
# ------------------------------------------------------------------------------------------------------

def UTCtoLocal(dt: datetime) -> datetime:
    """ Convert a timezone aware datetime into the local timezone. 
        Will only convert the timezone if the value is timezone aware.
        If the timestamp is None or timezone is missing (naive) then nothing changes. """
    if hasattr(dt,'tzinfo') and dt.tzinfo != None: 
        try:
            dt = dt.astimezone(pytz.timezone(Parameters.LocalTZ))
        except Exception as e:
            MainLog.ReportException(e,"UTCtoLocal cannot convert datetime to " + str(Parameters.LocalTZ))
    return dt

# ------------------------------------------------------------------------------------------------------

def UTCtoDisplay(dt: datetime) -> datetime:
    """ Convert a timezone aware datetime into the local timezone. 
        Will only convert the timezone if the value is timezone aware.
        If the timestamp is None or timezone is missing (naive) then nothing changes. """
    if hasattr(dt,'tzinfo') and dt.tzinfo != None: 
        try:
            if Parameters.DisplayTZ != "UTC": dt = dt.astimezone(pytz.timezone(Parameters.DisplayTZ))
        except Exception as e:
            MainLog.ReportException(e,"UTCtoDisplay cannot convert datetime to " + str(Parameters.DisplayTZ))
    return dt

# ------------------------------------------------------------------------------------------------------


def LocaltoUTC(dt: datetime) -> datetime:
    """ Convert a timezone aware datetime into UTC timezone. 
        Will only convert the timezone if the value is timezone aware.
        If the timezone is missing (naive) then nothing changes. """
    if hasattr(dt,'tzinfo') and dt.tzinfo != None: dt = dt.astimezone(pytz.timezone('UTC'))
    return dt

# ------------------------------------------------------------------------------------------------------

def DisplayDT(dt: datetime,zonename=None,decimals=False) -> str:
    """ Generate a standard display text of a datetime in whichever timezone 
        the user has selected as the local timezone. 
        If the timezone is missing (naive) then nothing changes.
        
        Parameters ----------------------------------------
        dt is a timezone aware datetime stamp.
        zonename is an overriding timezone name, if given. Otherwise the Parameters.DisplayTZ is used.
        decimals: When True fractions of a second are included.
        
        Output --------------------------------------------
        Returns a text string in the format 
        
                  yyyy.mm.dd hh:mm:ss Europe/London """
    #if Parameters.DisplayTZ != 'UTC': # Convert from UTC to some other timezone.
    #    dt = UTCtoLocal(dt) # Convert to local Timezone.
    dt = UTCtoDisplay(dt) # Convert to display timezone.
    if zonename == None: zonename = Parameters.DisplayTZ # Establish the timezone name to display.
    if decimals: temp = str(dt).split('+')[0] + ' ' + zonename # Include fractions of a second.
    else: temp = str(dt).split('.')[0] + ' ' + zonename # Whole seconds only.
    return temp
        
# ------------------------------------------------------------------------------------------------------

dt = NowUTC()
print('Current UTC time is:',dt)
print('Local time is:',DisplayDT(dt))

def CalculateCacheAltAz(alt: float, az: float):
    """ Given the home latitude, calculate a cacheable alt/az position for an object. 
        This is the current alt/az position but with the observer's latitude removed. 
        The resulting x,y,z position can then be rotated with time and then shifted back to the 
        observer's latitude. Giving a fast 'cached' star position that rotates in the sky with time. """
    # Convert the current alt/az to an xyz position in space.
    x,y,z = AltAzToXYZ(alt,az)
    # Remove the observer's latitude so that the positions are rotating around the zenith rather than the north pole.
    x,y,z = RotateXYZonXaxis(x,y,z,90 - Parameters._HomeLatVal)
    return x,y,z

# ------------------------------------------------------------------------------------------------------

def AltAzFromCache(x: float, y: float, z: float, timeangle):
    """ Given the a cached position for an object rotate it with time and return the apparent alt/az for the observer.
        The cached values have the observer's latitude removed, so they are ready to rotate by the time angle.
        The resulting alt/az position can then be rotated with time and then shifted back to the 
        observer's position. Giving a fast 'cached' star position that rotates in the sky with time.
        Returns an apparent alt/az pair for the object from the observer's position. """
    # Rotate the cached location by an angle representing elapsed time.
    x,y,z = RotateXYZonZ(x,y,z,timeangle)
    # Add the observer's latitude so that the positions represent the view for the observer.
    x,y,z = RotateXYZonXaxis(x,y,z,Parameters._HomeLatVal - 90)
    # Convert this to an alt/az pair. This is the position in the sky as seen by the observer.
    alt,az = XYZToAltAz(x,y,z)
    return alt, az

# ------------------------------------------------------------------------------------------------------

class quickstar():
    """ A fast-calculating star position. 
        Used for caching star locations when repeatedly drawing charts. 
        Not as precise as Skyfield or Astropy in the longterm, but precise enough for the 
        duration of an observation run. """
        
    def __init__(self,alt,az,timestamp):
        """ Parameters ------------------------------------- 
            alt       = The known altitude (degrees) at timestamp. 
            az        = The known azimuth (degrees) at timestamp.
            timestamp = datatime timestamp when alt/az were known. """
        self.BaseX, self.BaseY, self.BaseZ = self.CalculateBaseXYZ(alt,az)
        self.BaseTime = timestamp
        
    def CalculateBaseXYZ(self, alt: float, az: float):
        """ Calculate a cacheable x,y,z position for an object from its alt/az coordinates. 
            This is the current alt/az position but with the observer's latitude removed. 
            The resulting x,y,z position can then be rotated with time and then shifted back to the 
            observer's latitude. Giving a fast 'cached' star position that rotates in the sky with time. """
        # Convert the current alt/az to an xyz position in space.
        x,y,z = AltAzToXYZ(alt,az)
        # Remove the observer's latitude so that the positions are rotating around the zenith rather than the north pole.
        x,y,z = RotateXYZonXaxis(x,y,z,90 - Parameters._HomeLatVal)
        return x,y,z

    def AltAz(self,timestamp):
        """ Given the a cached position for an object rotate it with time and return the apparent alt/az for the observer.
            The cached values have the observer's latitude removed, so they are ready to rotate by the time angle.
            The resulting alt/az position can then be rotated with time and then shifted back to the 
            observer's position. Giving a fast 'cached' star position that rotates in the sky with time.
            Returns an apparent alt/az pair for the object from the observer's position. """
        elapsedseconds = (timestamp - self.BaseTime).total_seconds()
        timeangle = 360 * elapsedseconds / 86164.0905 # Use siderial period of axial rotation for the Earth (just under 24 hours!).
        # Rotate the cached location by an angle representing elapsed time.
        x,y,z = RotateXYZonZaxis(self.BaseX,self.BaseY,self.BaseZ,timeangle)
        # Add the observer's latitude so that the positions represent the view for the observer.
        x,y,z = RotateXYZonXaxis(x,y,z,Parameters._HomeLatVal - 90)
        # Convert this to an alt/az pair. This is the position in the sky as seen by the observer.
        alt,az = XYZToAltAz(x,y,z)
        return alt, az

# ------------------------------------------------------------------------------------------------------


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
        width = pixel width of the image. """
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

# ------------------------------------------------------------------------------------------------------

def GetTerminalSize():
    """ Return tuple of the current screen dimensions. (cols,rows) 
        This is used to dynamically build the ObservationRun display. 
        More information can be shown if the screen is large enough,
        but the system still works on a relatively small display space. """
    return textcolor.terminalsize() # returns (cols,rows)

# ------------------------------------------------------------------------------------------------------

CpuMonitor = cpumonitor(logger=MainLog,name='MainCpuMonitor') # Create new CPU monitor. Monitors overall load regardless of task.
CpuMonitor.LogCpuInfo() # Note details about the CPU.
#CameraCpuMonitor = cpumonitor(logger=CamLog,name='CameraCpuMonitor') # Create a CPU monitor specific to the camera thread. Can detect load per camera task this way.

MemoryMonitor = memorymonitor(logger=MainLog.Log) # Create new memory monitor.
MainLog.Log("Memory available",MemoryMonitor.MemoryTotal,terminal=False)

SDCardMonitor = discmonitor(name='root',devname='/dev/root',path=Parameters.SDPath,disctype='boot',logger=MainLog.Log) # Create new disc space monitor for the SD card.
MainLog.Log("Defaulting to SD card for images.",SDCardMonitor.DfPath,terminal=False) # Default to SD card for images unless we then find a USB storage device.
ImageStorageMonitor = SDCardMonitor # Point to the SD card storage when checking available space.

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
    
# Try to create a disc monitor for any attached USB memory.    
try:
    usbdev = ChooseUSBMemory()  
    USBDiscMonitor = discmonitor(name='usb',devname=usbdev,path=Parameters.USBPath,disctype='usb',logger=MainLog.Log) # Create USB memory card monitor (if it exists).
    # Decide which of the two above monitors will be the one that images are stored in. Create a pointer to that one for the status monitoring later on.
    if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable: 
        MainLog.Log("Switching to USB storage for images.",USBDiscMonitor.DfPath,terminal=False)
        ImageStorageMonitor = USBDiscMonitor # Point to USB storage when checking available space.
except Exception as e: # Failed to create USBDiscMonitor. Could be many reasons.
    MainLog.ReportException(e,comment="Failed to create USBDiscMonitor. A suitable USB device was not successfully selected.")
    textlist = ["USBDiscMonitor can fail for many reasons.",
                "Common causes are:",
                "1) USB device is not formatted suitably.",
                "2) USB device does not have a suitable volume name.",
                "   'USBMEMORY' is expected.",
                "3) USB memory may be mounted in an unexpected path.",
                "   '/media/pi' is expected.",
                " ",
                "The log file will show which devices were considered."]
    textcolor.TextBox(textlist,fg=textcolor.ORANGERED1,bg=textcolor.BLACK)

MainLog.Log("Image storage:",ImageStorageMonitor.DfPath,terminal=True)

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

def VerifyFolder(FN):
    """ Check that all directorys in the list exist. 
        If they don't create them. """
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

def DefineSessionFolders(campaign_name,exposure=None):
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
        If exposure time is provided as 2nd parameter it is combined into the campaign folder name. 
    """
    # FolderHandler :-
    sessionvalue = "session_" + UtcTimeStamp()
    if exposure is None: # No exposure, so don't include it in the campaign name.
        campaign = "campaign_" + campaign_name + "/" # Folder specific to the campaign (the target). All images related to the campaign are stored here.
    else: # We know the exposure, so include it in the campaign name.
        campaign = "campaign_" + campaign_name + '_e' + str(exposure) + "s/" # Folder specific to the campaign (the target). All images related to the campaign are stored here.
    campaignvalue = campaign
    FolderHandler.NewSession(campaign=campaignvalue,session=sessionvalue) # Update folder structures for the current target and session.
    
# ------------------------------------------------------------------------------------------------------

def AskYesNo(text,default=True,fg=None,bg=None):
    """ Ask any question that needs a simple Y/N answer.
        Returns logical value ('yes' returns True, 'no' returns False)
        Returns default value if user just presses ENTER. 
        Ignores 2nd and subsequent characters.
        Rejects all other input. """
    while True: # Loop until a satisfactory answer is given.
        if fg is None: # Use default color.
            temp = input(textcolor.cyan(text.strip() + " ")) # Ensure 1 character space between text and response cursor.
        else:
            temp = input(textcolor.fgbgcolor(fg,bg,text.strip() + " "))
        if len(temp) == 0:
            result = default
            break
        elif temp.lower()[0] in ["n"]: # NO recognised.
            result = False
            break
        elif temp.lower()[0] in ["y"]: # YES recognised.
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

temp = 'Observation status ' + ProgramTitle.upper() + ' ' + VERSION + " on " + os.uname().nodename
ObservationStatusWindow = colordisplay(rows=14,cdlayout=0,name='OSW',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title=temp,rjtitle="(" + Parameters.DisplayTZ + ")") # This is the text window that displays current progress of an observation.
ObservationStatusWindow.DrawBorder = True # Draw border around window.
ObservationStatusWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
ObservationStatusWindow.ClipWindow = True # Clip the display if the terminal area is insufficient. This means we see at least something.
ObservationStatusWindow.PlaceString('           Target: [TARGET                                                           ]',row=1,col=0)
ObservationStatusWindow.PlaceString('   Session folder: [FOLDER                                                           ]',row=2,col=0)
ObservationStatusWindow.PlaceString('   Tracking clock: [CLOCK                    ]    Duration: [DURATION         ]       ',row=3,col=0)
ObservationStatusWindow.PlaceString('         CPU load: [CPU                  ]Memory available: [MEMORY              ]    ',row=4,col=0)
ObservationStatusWindow.PlaceString('Storage available: [STORAGE               ]    Image types: [IMAGETYPES             ] ',row=5,col=0)
ObservationStatusWindow.PlaceString('   Camera Enabled: [CEN ] Exposure: [EXP       ] Timelapse: [TLAPSE   ] Capture:[FAST]',row=6,col=0)
ObservationStatusWindow.PlaceString('   OnChip cleanup: [OCC ]                     Control mode: [CMODE           ]        ',row=7,col=0)
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
SessionWindow = colordisplay(rows=12,cdlayout=1,name='SESSION',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title='Communication status',rjtitle="(" + Parameters.DisplayTZ + ")") 
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
SessionWindow.PlaceString('                [ZMODE           ]:[ZD]   Expires:[ZU    ]     [ZRM         ]  ',row=8,col=0)
SessionWindow.PlaceString('  altitude:Conf:[LC ]     Angle:[LA     ] [CALTA ]  OnTarget:[LT ] [LDPS    ]/s',row=9,col=0)
SessionWindow.PlaceString('                [LMODE           ]:[LD]   Expires:[LU    ]     [LRM         ]  ',row=10,col=0)
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
MctlRxWindow = colordisplay(rows=17,cdlayout=1,name='MCTLRX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Receive from microcontroller",rjtitle='(UTC)')
MctlRxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlRxWindow.DrawBorder = True # Draw border around window.
MctlRxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# - The MICROCONTROLLER TX WINDOW shows the latest messages sent to the microcontroller.
MctlTxWindow = colordisplay(rows=13,cdlayout=1,name='MCTLTX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Transmit to microcontroller",rjtitle='(UTC)') 
MctlTxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlTxWindow.DrawBorder = True # Draw border around window.
MctlTxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# - The CAMERA WINDOW shows the activities of the CAMERA THREAD which runs separately to the main thread of the software.
CameraWindow = colordisplay(rows=11,cdlayout=2,name='CAMERA',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Camera events",rjtitle='(UTC)') 
CameraWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraWindow.DrawBorder = True # Draw border around window.
CameraWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

ImageStatusWindow = colordisplay(rows=9,cdlayout=0,name='IMAGE',fg=OSW_TEXT_FG,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Image Status",rjtitle="(" + Parameters.DisplayTZ + ")")
ImageStatusWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
ImageStatusWindow.DrawBorder = True # Draw border around window.
ImageStatusWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# This is the text window that displays image and tracking progress of an observation.
ImageStatusWindow.PlaceString('       Capture state: [CAMERASTATE   ][STATETIMES       ]     [STATEAGE           ]   ',row=1,col=0)
ImageStatusWindow.PlaceString('        Image buffer: [OCVIB                            ] Camera task: [CTASK     ]   ',row=2,col=0)
ImageStatusWindow.PlaceString('  Drift target image: [DTI                                                        ]   ',row=3,col=0)
ImageStatusWindow.PlaceString('  Drift latest image: [DLI                                                        ]   ',row=4,col=0)
ImageStatusWindow.PlaceString(' Last azimuth tuning: [LAZT                                                       ]   ',row=5,col=0)
ImageStatusWindow.PlaceString('Last altitude tuning: [LALT                                                       ]   ',row=6,col=0)
ImageStatusWindow.PlaceString('      Session images: [IMAGES                                                     ]   ',row=7,col=0)
ImageStatusWindow.PlaceString('   Current image run: [RUN                  ] Acc:[ACCTIME  ]  ETA:[ETA           ] ',row=8,col=0)

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
InstructionWindow.PlaceString('  [+]/[-]Exposure                      [u]Timezone                  [x]Quit           ',row=2,col=0)
InstructionWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
InstructionWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
InstructionWindow.DrawBorder = True # Draw border around window.

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
DriftWindow = colordisplay(rows=10,cdlayout=2,name='DRIFT',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Drift tracking",rjtitle='(UTC)')
DriftWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DriftWindow.DrawBorder = True # Draw border around window.
DriftWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# - Camera thread communications windows.
# Window showing communication from the camera handler thread to the main observation routine.
CameraRxWindow = colordisplay(rows=10,cdlayout=2,name='CAMERARX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Receive from camera handler",rjtitle='(UTC)')
CameraRxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraRxWindow.DrawBorder = True # Draw border around window.
CameraRxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.
# Window showing communications sent TO the camera handler from the main observation routine.
CameraTxWindow = colordisplay(rows=10,cdlayout=2,name='CAMERATX',fg=PrintColorList,bg=OSW_TEXT_BG,titlefg=OSW_TITLE_FG,titlebg=OSW_TITLE_BG,title="Transmit to camera handler",rjtitle='(UTC)')
CameraTxWindow.ClipWindow = True # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraTxWindow.DrawBorder = True # Draw border around window.
CameraTxWindow.SetBorderColors(OSW_BORDER_FG,OSW_BORDER_BG) # Set border colors.

# All windows are defined. Turn on the 'reduceio' feature in them all.
colordisplay.GlobalReduceIO(True) # When redrawing windows, only the changed lines are repainted. 

# ------------------------------------------------------------------------------------------------------

class folderhandler(attributemaster):
    """ Class to define folders for various images. 
        This can also ensure that a folder exists when needed.
        
        Usage:
        
            FolderHandler = folderhandler(projectroot=ProjectRoot,logger=MainLog) # Create FolderHandler instance. Defines and create folder structures.
            FolderHandler.NewSession(campaign='mycampaign',session='mysession') # Define dummy structures until target chosen.
            filename = FolderHandler.PrepFile('light','image.jpg') # Return full path where a 'light' image is to be stored. This will also check that the structure exists.
            image.save(filename)
        
        "imageroot" = imageroot # Don't 'verify' the root structure. (For safety!) # Root of folders for campaign (image) data. If it's missing, it's an error.
        "dataroot" = dataroot # Don't 'verify' the root structure. (For safety!) # Root of folders for other data (target lists, parameters etc). If it's missing it's an error.
        "campaign" = imageroot + campaign # The parent folder for the campaign. Which could store work over several nights.
        "temp" = ProjectRoot + "temp" # Temporary folder for experiments.
        "session" = imageroot + session # The folder for an individual session.
        "tracking" = imageroot + session + "tracking" # This is the folder where tracking images are stored.
        "auto" = imageroot + session + "auto" # This is the folder where automatic images are stored (Normally during commissioning).
        "dark" = imageroot + session + "dark" # The Pi-lomar folder for the DARK images.
        "darkflat" = imageroot + session + "darkflat" # The folder for the DARK FLAT images.
        "light" = imageroot + session + "light" # The Pi-lomar folder for the LIGHT images. (The actual observations)
        "flat" = imageroot + session + "flat" # The Pi-lomar folder for the FLAT images.
        "bias" = imageroot + session + "bias" # The Pi-Lomar folder for the BIAS/OFFSET images.
        "preview" = imageroot + session + "preview" # The folder for the PREVIEW images.

        *Q* Potential methods to incorporate if needed.
            # O/S aware file/folder path operations :-
            from pathlib import Path
            folder = Path("/home/foldera/folderb") # Auto converts separators.
            filepath = Path.joinpath(folder,"filename.txt") # Appends the filename to the path automatically.
            filepath.parts returns ("/","home","foldera","folderb","filename.txt")
            filepath.root returns "/"
            filepath.parents returns list of parent structure, must use an index though! parents[1], parents[2], doesn't return entire list.
            filepath.parent returns immediate parent directory
            filepath.name = filename element
            filepath.suffix = filetype
            filepath.stem = filename without suffix
            Path.cwd() returns current working directory
            Path.home() returns user's home directory
            folder.chmod(...) change mode.
            filepath.exists() return True if file exists.
            filepath.is_dir()
            filepath.is_file()
            # filepath.walk(top_down=True) return tuple of structure. - Not in current RPi Python.
            filepath.mkdir(mode=0o777, parents=True, exist_ok=True) # Create directory and any required parents, don't complain if already exists.
            filepath.touch(mode=0o777, exist_ok=True) # Create / modify file.
        
        Methods -----------------------------------------------------------------------------------------
        ListCampaignFolders       : Return list of campaign folders available.
        ListSessionFolders        : Return list of session folders available.
        ListImageFolders          : Return list of image folders available.
        JoinPath                  : O/S compatible join of two path elements.
        ValidKey                  : Does a 'key' to a folder path exist?
        PrepFile                  : Assign and complete a complete new path for a given file type.
        NewSession                : Calculates the folder paths for a new campaign & session.
        PrintFolderList           : Terminal display of the current folder paths.
        ToPathType                : Convert text file paths into Path instances.
        GetPath                   : Return the folder path for any given 'key'.
        AddProjectFolder          : Create an entry in the folder list.
        CleanFilename             : Remove bad characters from filenames and paths.
        PathExists                : Return true if a path exists (Regardless of type).
        IsFile                    : Is the given filename a FILE?
        IsDir                     : Is the given filename a DIRECTORY/FOLDER?
        IsType                    : Return true if file is of a specific type (or in a list of types).
        CreateFolderFromListEntry : Given a folder 'key', make sure it exists and mark the entry accordingly.
        CreateFolderByPath        : Given a filepath, make sure it exists.

        """
        
    def __init__(self,projectroot,logger=None):
        """ Initialize the instance. """
        self.SetLogger(logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        if not Path(projectroot).exists(): # Project root is missing.
            raise Exception("folderhandler.__init__(" + str(projectroot) + ") does not exist.")
        self.oscommand = oscommand(logger=logger.Log) # Create OS command executor.
        self.osCmd = self.oscommand.Execute # Point to the chosen Execute method for os commands.
        self.ErrorWindow = None # Handle to optional error window.
        #self.FolderList = {} # Initial empty list of folders and attributes.
        self.ProjectRoot = projectroot # The base of all folders. Only folders beneath this level are created/modified.
        if Parameters.UseUSBStorage and USBDiscMonitor.DriveAvailable:
            temp = USBDiscMonitor.DfPath
            self.ImageRoot = temp
            MainLog.Log("folderhandler.__init__(): UsbFolder is specified for image storage. Using ",temp,terminal=False)
        else:
            temp = self.ProjectRoot # Default to the system SD card for storage.
            self.ImageRoot = self.JoinPath(temp,'data')
            MainLog.Log("folderhandler.__init__(): No UsbFolder is secified for image storage. Using ",temp,terminal=False)
        self.DataRoot = self.JoinPath(projectroot,'data') # This structure should be setup and configured BEFORE running this program. For safety we don't mess with this here.
        # Create some default folders to get things running until the full structure is defined.
        self.NewSession(campaign='campaign',session='session') # Create default folder entries. Will be updated when target chosen.

    def ListCampaignFolders(self):
        """ Return a list of campaign folders currently on disc. """
        rootpath = self.GetPath('imageroot') + "/campaign_*" # Where are the campaign folders held?
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def ListSessionFolders(self):
        """ Return a list of session folders currently on disc. """
        rootpath = self.GetPath('imageroot') + "/campaign_*/session_*" # Where are the session folders held?
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def ListImageFolders(self,imagetype='light'):
        """ Return a list of image folders currently on disc.
            imagetype says which type of image folders to return. """
        rootpath = self.GetPath('imageroot') + "/campaign_*/session_*/" + imagetype  # Where are the image folders held?
        folderlist = [f for f in glob.glob(rootpath) if os.path.isdir(f)]
        return folderlist

    def JoinPath(self,patha,pathb):
        """ Perform JoinPath on both 'Path' and 'str' names.
            Return as str.

            Usage:
            fullpath = FolderList.JoinPath('/home/pi/pilomar','test.txt')
            sets fullpath to '/homepi/pilomar/test.txt' """
        patha = self.ToPathType(patha)
        pathb = self.ToPathType(pathb)
        return str(Path.joinpath(patha,pathb))

    def ValidKey(self,key):
        """ Return TRUE if the key is recognised. """
        if key in self.FolderList:
            result = True
        else:
            result = False
        return result
        
    def PrepFile(self,key,filename):
        """ Given a folder KEY and a FILENAME construct the full path to the file
            and ensure that the destination folder exists.
            returns the fully qualified file path. """
        fullpath = self.JoinPath(self.GetPath(key),filename) # Construct full qualified path for the file.
        self.CreateFolderFromListEntry(key) # Make sure that the destination folder exists.
        return fullpath
        
    def NewSession(self,campaign,session):
        """ Given new campaign and session info, create the directory structure in the dictionary. 
            Actual folders are not created yet. They are made on-demand.
            This creates the standard list of folders based upon the current campaign and session.
            To create a folder you must call 

                folderhandler.PrepFile(key,filename)
                        This creates the folder if required and returns the fully qualified path to the filename.
              or
                folderhandler.CreateFolderFromListEntry(key)
                        This creates the folder if required. """
        self.FolderList = {} # Initial empty list of folders and attributes.
        campaign = self.CleanFilename(campaign).lower() # Standardise on lower case for campaign.
        session = self.CleanFilename(session).lower() # Standardise on lower case for session.
        self.AddProjectFolder(key="imageroot",foldername=self.ImageRoot) # Root of folders for campaign (image) data.
        self.AddProjectFolder(key="dataroot",foldername=self.DataRoot) # # Root of folders for other data (target lists, parameters etc). 
        self.AddProjectFolder(key="log",foldername=self.JoinPath(self.ProjectRoot,'log')) # Create folder relative to the Project root.
        self.AddProjectFolder(key="campaign",foldername=self.JoinPath(self.ImageRoot,campaign)) # The parent folder for the campaign. Which could store work over several nights.
        self.AddProjectFolder(key="temp",foldername=self.JoinPath(ProjectRoot,'temp')) # Temporary folder for experiments.
        self.AddProjectFolder(key="session",foldername=self.JoinPath(self.GetPath('campaign'),session)) # The folder for an individual session.
        self.AddProjectFolder(key="tracking",foldername=self.JoinPath(self.GetPath('session'),'tracking')) # This is the folder where tracking images are stored.
        self.AddProjectFolder(key="photometry",foldername=self.JoinPath(self.GetPath('session'),'photometry')) # This is the folder where photometry images are stored.
        self.AddProjectFolder(key="auto",foldername=self.JoinPath(self.GetPath('session'),'auto')) # This is the folder where automatic images are stored.
        self.AddProjectFolder(key="dark",foldername=self.JoinPath(self.GetPath('session'),'dark')) # The Pi-lomar folder for the DARK images.
        self.AddProjectFolder(key="darkflat",foldername=self.JoinPath(self.GetPath('session'),'darkflat')) # The folder for the DARK FLAT images.
        self.AddProjectFolder(key="light",foldername=self.JoinPath(self.GetPath('session'),'light')) # The Pi-lomar folder for the LIGHT images. (The actual observations)
        self.AddProjectFolder(key="flat",foldername=self.JoinPath(self.GetPath('session'),'flat')) # The Pi-lomar folder for the FLAT images.
        self.AddProjectFolder(key="bias",foldername=self.JoinPath(self.GetPath('session'),'bias')) # The Pi-Lomar folder for the BIAS/OFFSET images.
        self.AddProjectFolder(key="preview",foldername=self.JoinPath(self.GetPath('session'),'preview')) # The folder for the PREVIEW images.
        
    def PrintFolderList(self):
        """ Simple print of the current folder list. """
        print(textcolor.yellow("Current folder structure"))
        for key,value in self.FolderList.items():
            line = '- '
            line += key.ljust(10)[:10] + ' ' # Column for key.
            if value['exists']: # Directory already exists.
                line += textcolor.green("exists ")
            else:
                line += textcolor.yellow("       ")
            line += textcolor.white(value['path'])
            print(line)

    def ToPathType(self,filepath):
        """ Make sure filepath is a Path type.
            When referring to file and folder names in the code it is easy to confuse string and Path objects.
            This makes sure that you are always using a Path object by converting string values to Path objects. """
        if type(filepath) != Path:
            filepath = Path(filepath)
        return filepath

    def FileAge(filename):
        """ Return timedelta object with age of file. """
        result = None
        if self.IsFile(filename):
            result = NowUTC() - os.path.getmtime(filename)
        return result 
            
    def FileExpired(filename,days=0,hours=0,minutes=0,seconds=0):
        """ Return TRUE if a file is too old. """
        result = True
        if self.FileAge(filename) >= timedelta(days=days,hours=hours,minutes=minutes,seconds=seconds): result = True
        return result 
            
    def GetDictionaryCache(self,filename,days=0,hours=0,minutes=0,seconds=0):
        """ If filename exists and is within age limit, import and return it as a dictionary. 
            Otherwise return None. """
        result = None
        if self.IsFile(filename) and self.IsType(filename,'json') and not self.FileExpired(filename,days=days,hours=hours,minutes=minutes,seconds=seconds): 
            with open(filename,'r') as f:
                result = json.load(f)
        return result

    def GetPath(self,key): 
        """ Given a folder key, return the folder name.

            The path for various folders changes with each observation session.
            This allows you to refer to a folder by it's purpose, and retrieve the current dynamic value.

            Usage:
                current_light_image_folder = folderhandler.GetPath('light')
                Returns something like '/home/pi/pilomar/data/campaign_saturn/session_20220514201436/light'
            """
        result = None
        if key in self.FolderList:
            result = self.FolderList[key].get("path",None)
        else:
            MainLog.Log("folderhandler.GetPath(",key,") Key is not recognised.",level='error')
        return result
        
    def AddProjectFolder(self,key,foldername):
        """ Create a folder entry in FolderList.
            Does not immediately create the Folder. """
        foldername = self.CleanFilename(foldername) # Remove dangerous characters.
        foldername = self.ToPathType(foldername) # Convert to Path object.
        folderpath = self.JoinPath(self.ProjectRoot,foldername)
        entry = {'path': str(folderpath),
                 'exists': self.PathExists(folderpath)}
        self.FolderList[key] = entry
        
    def CleanFilename(self,filename):
        """ Remove dangerous characters from a filename or path. """
        filename = filename.replace(" ","").replace("-","").replace(":","")
        filename = filename.replace("(","").replace(")","")        
        return filename

    def PathExists(self,folderpath):
        """ Return TRUE if a path exists. Else False. """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.exists()
        
    def NameOnly(self,folderpath):
        """ Strip full path, return only the name of the file. """        
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.name

    def IsFile(self,folderpath):
        """ Return TRUE if a path points to a file. Else False. """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.is_file()

    def GetParent(self,folderpath):
        """ Return PARENT of a folder. """
        folderpath = self.ToPathType(folderpath)        
        return folderpath.parent

    def IsDir(self,folderpath):
        """ Return TRUE if a path points to a file. Else False. """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.is_dir()
        
    def IsType(self,filepath, filetype, casesensitive=False):
        """ Return TRUE if the path is a file matching filetype. 
            filepath is the path to check.
            filetype can be a single value or a list that must be matched.
            casesensitive controls whether case must match. 
            File does not need to exist on disc. """
        if type(filetype) == str: filetype = [filetype] # Convert to list in all cases.
        filepath = self.ToPathType(filepath) # Convert to Path object.
        foundtype = filepath.suffix.replace('.','') # Get suffix (file type) and drop the '.' separator.
        result = False 
        #print("folderhandler.IsType(): Comparing",foundtype,"with",filetype,",cs:",casesensitive)
        if casesensitive: # Perform case sensitive match.
            if foundtype in filetype: # We found a match.
                result = True
        else: # Not case sensitive.
            filetype = [ft.lower() for ft in filetype] # Convert to lower case.
            if foundtype.lower() in filetype:
                result = True
        return result

    def CreateFolderFromListEntry(self,key):
        """ Given a folder key, make sure it exists and mark the entry accordingly. """
        if key in self.FolderList: # Recognised entry in FolderList.
            if not self.FolderList[key]['exists']: # The folder does not exist yet.
                folderpath = self.GetPath(key) # Get the full path.
                self.CreateFolderByPath(folderpath) # Create the actual folder.
                self.FolderList[key]['exists'] = True # Mark that the folder now exists.
                self.Log("folderhandler.CreateFolderFromListEntry(",key,") created folder:",folderpath,terminal=False)
        else:
            self.Log("folderhandler.CreateFolderFromListEntry(",key,") key does not exist.",terminal=False)

    def CreateFolderByPath(self,folderpath):
        """ Make sure a directory exists.
            folderpath can include a destination filename, but it's ignored. """
        try:
            self.Log("folderhandler.CreateFolderByPath(",folderpath,")",terminal=False)
            folderpath = self.ToPathType(folderpath) # Convert to Path object.
            if folderpath.is_file(): folderpath = folderpath.parent # Strip off any file name. Just want the folder structure.
            folderpath.mkdir(mode=0o777, parents=True, exist_ok=True) # Create folder and all parent folders if missing.
        except Exception as e:
            MainLog.ReportException(e,command='folderhandler.CreateFolderByPath') # Trap all the exception information in the main log file.
        
FolderHandler = folderhandler(projectroot=ProjectRoot,logger=MainLog) # Create FolderHandler instance. Defines folder structures and creates them as needed.

# ///////////////////////////////////////////////////////////////////////////////////
# Camera assets. 
# ///////////////////////////////////////////////////////////////////////////////////
        
# Create camera related objects.
# Parameters taken from https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
# RPiHQ16mm
#    Lens Length = 16.0 # Official lens focal length.
#    Lens horizontal field of view 21.8 degrees.
#    Lens vertical field of view 16.4 degrees.
# Arducam50mm
#    Lens Length = 50.0 # Official lens focal length.
#    Lens horizontal field of view 7.0 degrees.
#    Lens vertical field of view 5.2 degrees.
# Sensor image width 4056 pixels
# Sensor image height 3040 pixels
LensInUse = astrolens(length=Parameters.LensLength, 
                      horizontal_fov=Parameters.LensHorizontalFov, 
                      vertical_fov=Parameters.LensVerticalFov,
                      multiplier=Parameters.EquivMultiplier,
                      logger=CamLog,
                      parameters=Parameters)
LensInUse.ErrorWindow = ErrorWindow # Point LensInUse to a window for displaying error messages.
LensInUse.CameraWindow = CameraWindow # Point LensInUse to a window for displaying camera events.
SensorInUse = astrosensor(sensor_type=Parameters.SensorType,
                          logger=CamLog,
                          parameters=Parameters)
SensorInUse.ErrorWindow = ErrorWindow # Point SensorInUse to a window for displaying error messages.
SensorInUse.CameraWindow = CameraWindow # Point SensorInUse to a window for displaying camera events.
CameraInUse = astrocamera(inp_sensor=SensorInUse, 
                          inp_lens=LensInUse, 
                          exposure=10.0, 
                          trackingexposure=Parameters.TrackingExposureSeconds,
                          logger=CamLog,
                          parameters=Parameters)
CameraInUse.ErrorWindow = ErrorWindow # Point CameraInUse to a window for displaying error messages.
CameraInUse.CameraWindow = CameraWindow # Point CameraInUse to a window for displaying camera events.
CameraInUse.StorageMonitor = ImageStorageMonitor # Point CameraInUse to the ImageStorageMonitor instance to check available storage.
astrocamera.SetGlobalFolderHandler(FolderHandler) # Update all the declared cameras with the latest copy of FolderHandler. This doesn't need explicitly refreshing if target changes.
astrocamera.SetGlobalKeyboard(Keyboard) # Point the cameras to the keyboard handler (to allow user to interrupt processes).

# Summarise camera settings...
CameraWindow.Print("Lens:",LensInUse.Length,"mm (35mm equiv.",LensInUse.EquivLength,"mm)")
CameraWindow.Print("Lens: FoV:",str(LensInUse.FovHorizontal) + DegreeSymbol,"*",str(LensInUse.FovVertical) + DegreeSymbol)
CameraWindow.Print("Sensor: Width",SensorInUse.PixelWidth,"* Height",SensorInUse.PixelHeight,"pixels")

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
            MainLog.Log("Camera is accessible and enabled.",terminal=False)
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
    MainLog.Log("DetectRaspistill:",tempresult,terminal=False)
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
            MainLog.Log("Camera is accessible and enabled.",terminal=False)
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
    MainLog.Log("DetectLibcamera:",tempresult,terminal=False)
    return tempresult

# ---------------------------------------------------------------------------------------------------- 

def DetectCamera(canenable=False,candisable=False):
    """ Test for presence of a camera via raspistill or libcamera. """
    if Parameters.CameraDriver == 'raspistill': #if OS_name in ['buster']:
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
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        CameraInUse.CalibrateFov()
        CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
        DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
        DocumentSession()
        DriftTracker.Reset()
        
# ---------------------------------------------------------------------------------------------------- 

def CameraEnabledChange():
    """ Call this when setting CameraEnabled flag. 
        It handles some related changes and messages. """
    if Parameters.CameraEnabled:
        print (textcolor.green("Camera enabled"))
        MainLog.Log("The camera can be disabled in the parameters file if you don't want to take actual photographs.",terminal=False)
        if Parameters.CameraDriver == 'raspistill': # Only raspistill does this, libcamera handles denoise via the command line.
            if Parameters.DisableCleanup: SensorInUse.DisableCleanup()
            else: MainLog.Log("NOTE: on-chip cleanup has not changed state.",terminal=True)
        if not DetectCamera(): # Check there really IS a camera connected!
            MainLog.Log("CameraEnabledChange(): Camera has been enabled. But there is no camera detected. You may get errors.",level='error')
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

# Check if camera is available.
tempresult = DetectCamera(candisable=True)
CameraEnabledChange() # Handle related changes.

# ---------------------------------------------------------------------------------------------------- 

def EnableCamera():
    """ This enables the camera, even if it is not installed. """
    Parameters.CameraEnabled = True
    MainLog.Log("Camera has been manually enabled.",level='warning',terminal=True)
    CameraEnabledChange() # Handle related changes.

# ---------------------------------------------------------------------------------------------------- 

def DisableCamera():
    """ This disables the camera. """
    Parameters.CameraEnabled = False
    MainLog.Log("Camera has been manually disabled.",level='warning',terminal=True)
    CameraEnabledChange() # Handle related changes.

# ---------------------------------------------------------------------------------------------------- 

# Create a stop button.
if Parameters.ObservationStopPin != None: ObservationStopButton = inputpin(Parameters.ObservationStopPin,"ObservationStopButton",pull='up') # Pin is HIGH by default, must be grounded to trigger.
else: ObservationStopButton = None

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

    def GetSerialPorts(self):
        """ Return a list of serial ports recognised on the machine. """
        portlist = []
        lines = osCmd('dmesg | grep base_baud') # Try this list of serial ports too.
        MainLog.Log("GetSerialPorts(): serial ports via dmesg:",terminal=False)
        for i,line in enumerate(lines):
            # [    0.638181] 1f00030000.serial: ttyAMA0 at MMIO 0x1f00030000 (irq = 125, base_baud = 0) is a PL011 AXI
            lf = line.find(".serial:")
            if lf >= 0: # Likely serial device.
                portid = line[lf + 9:].strip().split(' ')[0]
                #print("GSP:",line,lf,portid)
                portlist.append(portid) # Pull the device name.
            MainLog.Log("GetSerialPorts(): serial port entry:",i,line,terminal=False)
        MainLog.Log("GetSerialPorts(): Currently selected serial port for UART:",self.Port,terminal=False)
        return portlist

    def ListSerialPorts(self,terminal=False):
        """ Display a list of serial ports recognised on the machine. 
            This list may not show all available UART options. 
            Parameters ----------------------------------------------
            terminal : True : Output to screen and log file. 
                       False: Output to log file only. """
        if terminal: print(textcolor.yellow("List potential serial ports:"))
        MainLog.Log("Recognised serial ports on this computer:",terminal=terminal,showtime=False)
        portlist = self.GetSerialPorts()
        foundit = False
        for i,line in enumerate(portlist):
            MainLog.Log("serial port entry:",i,line,terminal=False,showtime=False)
            if terminal:
                text = str(i).rjust(2) + " "
                if "/dev/" + line == self.Port: 
                    text += textcolor.green(line) + " (This is currently selected as the UART port)"
                    foundit = True
                else: text += line
                print(text)
        if foundit == False: # The currently selected port is NOT in the list.
            MainLog.Log(self.Port,"(This is currently selected as the UART port - but not in the system list)",terminal=False)
        MainLog.Log("Currently selected serial port for UART:",self.Port,terminal=terminal,showtime=False)

    def MenuListSerialPorts(self):
        """ List serial ports to log file and terminal. """
        self.ListSerialPorts(terminal=True)
        
    def __init__(self,port='/dev/serial0',resetpin=4,boardtype=None,logger=None):
        """ 
            port = serial port to use for UART communication. 
            resetpin = pin used to control reset or power for the microcontroller. 
            boardtype = Identifier of specific motorcontroller board. 
                        Motorcontrol board behaviour may change depending upon the board type.
                None = Default 
                "Ton-2023-12" = Raspberry Pi 4 HAT format with onboard 5V power source. 
                "Matt-2023-12-06"  = Basic PCB board design published just after Instructables project published.

            UART ports.
                 RPi 3, 4 & 5:         /dev/ttyAMA0                  (when using just GPIO connection to project PCB) ** RECOMMENDED **
                 RPi 3 & 4:            /dev/serial0 or /dev/ttyAMA0  (when using just GPIO connection to project PCB)
                 RPi5 UART/Debug port: /dev/serial0 or /dev/ttyAMA10 (If using UART port for some other PCB design.)  """
        self.SetLogger(logger=logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.BoardType = boardtype # Can be one of [None,'Ton-2023-12','Matt-2023-12-06'], or add your own.
        self.Port = port # Note which UART port was chosen.
        # Check the chosen serial port exists!
        if not os.path.exists(port):
            self.Log("microcontroller.__init__(",port,") device does not exist. Cannot create UART communication.",terminal=True,level='error')
            self.Log("Check that the serial ports are configured and enabled as required.",terminal=True)
            self.ListSerialPorts() # List any recognised serial ports.
            raise Exception("UART device does not exist. File not found error.",port)
        if not port in self.GetSerialPorts(): # Is the port recognised in the serial port list?
            self.Log("microcontroller.__init__(",port,") NOTE: Device is not in the list of recognised serial ports.",terminal=False)
            self.ListSerialPorts() # List any recognised serial ports.
        # Now initiate communication with the microcontroller.
        self.uart = serial.Serial(port,115200,timeout=0,exclusive=True)
        self.QueueToMctl = Queue() # Use queue mechanism to SEND commands TO the microcontroller communication thread. 
        self.QueueFromMctl = Queue() # Use queue mechanism to RECEIVE commands FROM the microcontroller communication thread. 
        self.ResetBCM = resetpin # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
        self.ResetPin = outputpin(self.ResetBCM,"MctlReset") # Create GPIO pin if a pin is specified, else create dummy pin. All pins start OFF.
        self.Lines = [] # No lines received yet.
        self.WriteChunkBytes = 32 # Maximum number of characters to send in a batch.
        self.WriteChunkSeconds = 0.2 # Seconds between chunks written to microcontroller.
        self.InputLine = '' # This is the line currently being received. Completed lines are added to Lines list.
        self.WriteQueue = [] # No output to send yet.
        self.LinesReceived = 0 # total number of lines received from the microcontroller.
        self.LinesSent = 0 # Total count of lines sent to the microcontroller.
        self.BytesReceived = 0 # Byte count from microcontroller.
        self.BytesSent = 0 # Byte count sent to the microcontroller.
        self.PrintComms = False # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
        self.LedStatus = True # LEDS on by default.
        self.LineOpenedTime = NowUTC() # When did the UART comms start?
        self.LastTxTime = NowUTC() # When was data last sent?
        self.LastRxTime = NowUTC() # When was data last received?
        self.RxErrors = 0 # How many receive errors have been detected.
        self.LastLineSent = None # We get 'reflection' on the UART port if the remote device isn't ready. This helps us to detect that.
        self.CommsTimeout = Parameters.MctlCommsTimeout # Seconds. microcontroller is restarted if no data received after this period.
        self.ForcedRestarts = 0 # How many restarts have been forced by this software?
        self.RemoteRestarts = 0 # How many restarts have been registered by the remote device itself?
        self.ResetAttempts = 0 # Increment for each sequential attempt to reset communication with the remote microcontroller board.
        self.PoweredByUsb = False # If the device is connected by USB, then power handling is different.
                                    # Power to Microcontroller comes through USB cable, DO NOT enable power via the GPIO!
        if Hardware.pcb_protect_usb: # We must protect the devices from conflicting power sources.
            UsbList = SDCardMonitor.ListUSBdevices() # List all the potential devices. If the CIRCUITPYTHON device is connected via USB, say so here!
            for dn,dl in UsbList: # Check all connected USB devices.
                if dl in ['CIRCUITPY']: # Circuit Python device has USB connection. We cannot power it by GPIO at the same time!
                    self.PoweredByUsb = True # Don't allow GPIO power pin to be used.
                    print("microcontroller.__init__(): Detected that the microcontroller",dl,"is potentially being powered over USB. (WARNING)")
                    lines = ["DETECTED A CONNECTED USB DEVICE LABELLED " + str(dl) + ".",
                             "This looks like it's a microcontroller.",
                             " ",
                             "The microcontroller could receive conflicting voltages via the",
                             "USB line and the GPIO header. These may damage the devices.",
                             " ",
                             "For safety, the 'enable' pin for microcontroller power will not be used.",
                             "It will be permanently powered via the USB cable instead.",
                             " ",
                             "This means pi-lomar cannot power cycle the microcontroller if it needs to",
                             "reset it. It also means that the microcontroller clock may get independently",
                             "synchronised by the USB connection as well as by the pi-lomar software.",
                             " ",
                             "The software will continue to run, but there is a risk of unexpected behaviour.",
                             " ",
                             "Concurrent USB + GPIO connections to the microcontroller are recommended only",
                             "during development or debugging with special care taken to protect the devices."]
                    textcolor.TextBox(lines,fg=textcolor.WHITE,bg=textcolor.ORANGERED1,justify='c')  
                    break                    
        if self.PoweredByUsb: # Never turn on second power source to the microcontroller if it's already got USB power.
            self.Log("microcontroller.__init__(): PoweredByUsb:True",terminal=False)
        else:
            self.Log("microcontroller.__init__(): PoweredByUsb:False",terminal=False)
            self.ResetPin.On() # Turn the microcontroller ON if we're in charge of the power supply.
        self.DeviceFailure = False # Set to TRUE if device seems to be irrecoverably lost.
        self.ErrorWindow = None # Link to a display window that can show error messages.
        self.WriteProhibited = False # OK to write again to the write queue.
        self.SendId = 0 # Incremental counter, the message number being sent to the microcontroller. The microcontroller will respond that this message number has been received.
        self.ReportedResetReason = 'UNKNOWN' # RESET REASON if reported.
        self.ReportedClockspeed = 0 # Clock speed in MHz
        self.ReportedVoltage = 0 # CPU voltage if known
        self.ReportedMemAlloc = 0 # Memory allocated (bytes)
        self.ReportedMemFree = 0 # Memory free (bytes)
        self.ReportedTemperature = 0.0 # CPU temperature (C)
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

    def ToggleMonitor(self):
        """ Toggle message replication to the terminal. 
            From On to Off or Off to On."""
        if self.Log != None:
            self.Log("microcontroller.ToggleMonitor()",terminal=False)
        self.PrintComms = not self.PrintComms

    def PowerOn(self):
        """ Overrides all safeties, turns power GPIO power pin on for microcontroller. """
        if self.ResetBCM is None:
            self.Log("microcontroller.PowerOn(): No Reset pin defined. Cannot turn microcontroller on via GPIO.",terminal=True)
            return
        authority = AskYesNo("No safety checks. Do you want to turn ON GPIO power for the microcontroller [y/N]?",False,fg=textcolor.BLACK,bg=textcolor.ORANGERED1)
        if authority:
            self.Log("microcontroller.PowerOn(): No safety checks. GPIO POWER PIN turned on for Microcontroller.",terminal=True)
            self.ResetPin.On()

    def PowerOff(self):
        """ Overrides all safeties, turns power GPIO power pin off for microcontroller. """
        if self.ResetBCM is None:
            self.Log("microcontroller.PowerOff(): No Reset pin defined. Cannot turn microcontroller off via GPIO.",terminal=True)
            return
        authority = AskYesNo("No safety checks. Do you want to turn OFF GPIO power for the microcontroller [y/N]?",False,fg=textcolor.BLACK,bg=textcolor.ORANGERED1)
        if authority:
            self.Log("microcontroller.PowerOff(): No safety checks. GPIO POWER PIN turned off for Microcontroller.",terminal=True)
            self.Log("microcontroller.PowerOff(): Note: If the messagehandler is still running, it will restart the microcontroller automatically.",terminal=True)
            self.ResetPin.Off()

    def PowerIsOn(self):
        """ Return TRUE if power is on, FALSE otherwise. 
            This uses GPIO.input(self.ResetBCM) even though the pin is defined as an output,
            it still works and returns the state of the pin. """
        return self.ResetPin.State

    def SendManualCommand(self):
        """ Prompt the user for a manual command to send to the microcontroller. 
            There is no validation performed on this, if you get the syntax wrong you may crash the 
            microcontroller. Use at your own risk. """
        print(textcolor.yellow("Manual command to microcontroller."))
        print("Enter your commands ('&now' will be replaced with current timestamp.)")
        print("There is no error checking on manual commands. Be careful.")
        command = input(textcolor.cyan("command ['x' to exit]: ")).strip()
        if command.lower() == 'x': return True # Quit.
        if command != '': # There's something to send.
            command = command.replace('&now',CleanDatetimeString(str(NowUTC()))) # Substitude any reference to the current clock.
            self.Log("microcontroller.SendManualCommand():",command,terminal=True)
            self.Write(command) # Sent.
        return True
            
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
                exit() # Quit the program. (*Q* Other threads don't get stopped however!)
                return False
            else:
                self.ResetAttempts += 1 # Try again.
        # The behaviour will depend upon the circuitry supporting the chosen microcontroller.
        MainLog.Log("microcontroller.Reset(): PoweredByUsb",self.PoweredByUsb,"PROTECT_USB",Hardware.pcb_protect_usb,terminal=False)
        if self.PoweredByUsb: # Powered by USB and PCB doesn't support conflicting power source, so cannot power cycle it. Send a RESET command instead.
            MainLog.Log("microcontroller.Reset(): Device is connected via USB, will not enable power via GPIO for safety.",terminal=False)
            DevWindow.Print(NowHMS() + " Microcontroller is powered by USB, performing software reset.")
            if self.PrintComms: print(textcolor.yellow("GPIO not in use. Software reset."))
            # Send software 'reset' command instead.
            self.Write('reset')
            # self.WriteFlush() # Make sure all commands are flushed through. When initializing for the first time, the write process isn't running! This won't flush.
        else: # Not USB power or PCB circuitry is safe, so can power cycle the microcontroller to reset it.
            # GPIO pin is driven low for a second. This either triggers the microcontroller's reset pin directly (eg Pico RP2040, Feather RP2040 etc),
            # or it can simply switch off the power to a microcontroller that lacks a reset pin (eg Tiny2040).
            DevWindow.Print(NowHMS() + " Microcontroller is powered by GPIO, performing power reset.")
            if self.PrintComms: print(textcolor.yellow("GPIO pin",self.ResetBCM,"low."))
            self.ResetPin.Off() # If it's a real pin, turn it off, else do nothing.
            time.sleep(1) # Pause 1 second.
            if self.PrintComms: print(textcolor.yellow("GPIO pin",self.ResetBCM,"high."))
            self.ResetPin.On() # If it's a real pin and enabled, turn it on, else do nothing.
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
        # *Q* This could store the 'controller log' messages directly here automatically. 
        result = ''
        while len(result) == 0 and len(self.Lines) > 0: # No valid line to return yet, and still lines available in the receive buffer.
            result = self.Lines.pop(0).strip()
            if self.ValidateChecksum(result): # Line is good, remove the checksum.
                cleanresult = self.RemoveChecksum(result)
            else: # Line is bad. Don't clean it.
                cleanresult = result
            self.Log('RPi received: ' + cleanresult,terminal=False)
            if self.PrintComms: print(textcolor.magenta('RPi received: ' + cleanresult))

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
            if send parameter is false, the write queue is flushed without sending anything further.
            - Send = True: This routine will trigger WritePoll() directly. Assume that the main sending routine is stopped.
            - Send = False: This routine just flushes."""
        result = True
        if send: # We should try to send outstanding messages.
            self.Log('WriteFlush: Flushing microcontroller output queue (',len(self.WriteQueue),'pending messages will be sent)...',terminal=False)
            self.Log('WriteFlush: WriteProhibited:',self.WriteProhibited,terminal=False)
            TryCount = 0
            self.WriteProhibited = True # Don't allow anything further to be added to the queue at the moment.
            while len(self.WriteQueue) > 0:
                TryCount += 1
                self.Log("WriteFlush: Queue currently",len(self.WriteQueue),"entries",terminal=False)
                self.Log("WriteFlush: 1st in queue:",self.WriteQueue[0],terminal=False)
                self.WritePoll() # Send next chunk of data from output buffer if allowed.
                time.sleep(0.1) # Pause until the CommsLoop thread has cleared the buffer.
                if TryCount >= 500:
                    self.Log('WriteFlush: Flush timeout. Maximum loops.',len(self.WriteQueue),'Remaining messages will be dropped.',terminal=False)
                    result = False
                    break
            self.WriteProhibited = False # OK to write again to the write queue.
        else: 
            self.Log('WriteFlush: Flushing microcontroller output queue (',len(self.WriteQueue),'pending messages will be dropped)...',terminal=False)
        self.WriteQueue = [] # Delete any remaining messages in the queue.
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
                self.Log("microcontroller.CommsLoop(): Parent thread is nolonger alive. Stopping.",level='error')
                break # Parent thread died, so terminate this thread too.
            if commandqueue.empty() == False: # This queue allows the main thread to send commands to the microcontroller comms controller itself.
                ReceivedMessage = commandqueue.get()
                if ReceivedMessage == "stop":
                    self.Log("microcontroller.CommsLoop(): Received 'stop' command.",terminal=False)
                    break # Terminate this loop. Will require restart by main thread.
            time.sleep(0.01) # Need a tiny pause otherwise this hogs the processor.
        self.WriteFlush(send=True) # Flush any outbound comms to the microcontroller before closing.
        self.Log('microcontroller.CommsLoop(): End',terminal=False)

UartControlQueue = Queue() # Command queue to the CommsLoop, use this to shut it down by sending 'stop'.

# ------------------------------------------------------------------------------------------------------

def SystemUARTPort():
    """ Return the suggested UART port based upon the RPi model. """
    if Hardware.rpi_num in ['3','4','CM4']: # The software can use the default UART port depending upon the RPi model.
        port='/dev/serial0'
    else:
        port='/dev/ttyAMA0'
    return port
    
# ------------------------------------------------------------------------------------------------------

def InitiateMctl():
    """ Start up fresh communication with the microcontroller. """
    MainLog.Log('Establishing serial UART communication with microcontroller...',terminal=False)
    mctl = None
    try:
        if Parameters.UARTOverride != None: # The owner has chosen a specific UART port to use.
            MainLog.Log('RPi model',Hardware.rpi_num,'using UART',Parameters.UARTOverride,'(via UART override parameter)',terminal=False)
            mctl = microcontroller(port=Parameters.UARTOverride,
                                   resetpin=Parameters.MctlResetPin,
                                   boardtype=Parameters.BoardType,
                                   logger=MainLog) # Create communication with microcontroller over uart0 serial port.
        else: # Use the default for this device.
            uartport = SystemUARTPort()
            MainLog.Log('RPi model',Hardware.rpi_num,'using UART",uartport,"(via GPIO header)',terminal=False)
            mctl = microcontroller(port=uartport,
                                   resetpin=Parameters.MctlResetPin,
                                   boardtype=Parameters.BoardType,
                                   logger=MainLog) # Create communication with microcontroller over uart0 serial port.
        mctl.ReportBoard() # Log the board type now that the log file is defined.
        mctl.Initiate() # Initiate communication.
        
    except PermissionError as e: 
        MainLog.Log('InitiateMctl: Failed: PermissionError.',level='error')
        print ("")
        linelist = [
                 "           THE MICROCONTROLLER FAILED TO INITIALISE.",
                 "                    PERMISSION ERROR.",
                 "This may be because the permissions are incorrectly set in"
                 "raspi-config. ",
                 "1) Check SERIAL PORT is ENABLED"
                 "2) Check SERIAL CONSOLE is DISABLED"]
        textcolor.TextBox(linelist,fg=textcolor.WHITE,bg=textcolor.RED)
        print ("")
        MainLog.RaiseException(e,comment='InitiateMctl:PermissionError') # Trap all the exception information in the main log file.
    except Exception as e:
        MainLog.Log('InitiateMctl: Failed: Is another instance already running?',level='error')
        print ("")
        linelist = [
                 "           THE MICROCONTROLLER FAILED TO INITIALISE.",
                 "                    EXCEPTION.",
                 "This may be because another copy of pilomar is already running.",
                 "or because the Serial Port is misconfigured in raspi-config.",
                 "1) Check for duplicate processes and terminate them if needed.",
                 "2) Check SERIAL PORT is ENABLED"
                 "3) Check SERIAL CONSOLE is DISABLED"]
        textcolor.TextBox(linelist,fg=textcolor.WHITE,bg=textcolor.RED)
        print ("")
        print (textcolor.yellow("pilomar processes currently running:-"))
        osCmd('ps -ef | grep pilomar',output='terminal')
        print (textcolor.yellow("This copy of the pilomar is pid",os.getpid()))
        MainLog.RaiseException(e,comment='InitiateMctl:Exception') # Trap all the exception information in the main log file.
    return mctl
    
# ------------------------------------------------------------------------------------------------------

Mctl = InitiateMctl() # Create new microcontroller instance. 
if Mctl is None: # Microcontroller couldn't start.
    MainLog.Log("InitiateMctl failed to create Microcontroller instance.",level='error')
    exit() # Quit the program.

astrocamera.SetGlobalMctl(Mctl) # Point the cameras to the microcontroller instance (to monitor restarts)

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

    def __init__(self,name,gearratio,fullstepsperrev,microstepratio,minangle,maxangle,restangle,currentangle,backlashangle,orientation=1,limitangle=None,horizon=None,fasttime=0.001,slowtime=0.05,timedelta=0.003,driver='drv8825',slewmicrosteps=1,optimisemoves=False,logger=None):
        """ Create an instance of a stepper motor.
            Set up the physical configuration of the gears.
            Set up the electrical configuration of the stepper motor driver.            """
        self.SetLogger(logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.MotorName = name # A unique name to identify the motor, should be the same as the motor's name in the microcontroller side too.
        self.Driver = driver # What driver board is being used?
        self.TuneCommandCount = 0 # Keep a count of how many TUNE commands have been sent.
        self.OpenTuneCommands = [] # Keep a list of all TUNE commands sent until they have been acknowledged.
        self.OptimiseMoves = optimisemoves # Is the motor allowed to move freely across the 0/360 movement limit to track targets?
        self.GearRatio = gearratio
        motorstepsperrev = fullstepsperrev * microstepratio # Calculate motorstepsperrev to include microstep ratio.
        self.MotorStepsPerRev = motorstepsperrev # FullStepsPerRev of the motor * any microstepping multiplier.
        self.MicrostepRatio = microstepratio # Just for documentation from this point onwards. Used for observation runs (Smoothest).
        self.SlewMicrosteps = slewmicrosteps # When making fast SLEW moves, what microstepping do we use? Used for GOTO and HOME moves.
        self.SlewMicrosteps = min(self.SlewMicrosteps,self.MicrostepRatio) # Slew cannot use finer microstepping than the observation!
        if self.SlewMicrosteps != slewmicrosteps:
            self.Log("motorcontrol(",name,") Slew microsteps (",slewmicrosteps,") restricted to",self.MicrostepRatio,level='warning',terminal=True)
        self.SlewStepMultiplier = int(round(self.MicrostepRatio / self.SlewMicrosteps,0))
        self.Log("motorcontrol(",name,") microstepping=",self.MicrostepRatio,"(observation speed), slew steps=",self.SlewMicrosteps,"(goto speed), multiplier=",self.SlewStepMultiplier,terminal=False)
        modesignals = 'nnn' # Default full-step mode signals for the motor driver. (Used during observations).
        slewsignals = 'nnn' # Default full-step mode signals for the motor driver. (Used during large slew/GOTO moves).
        if driver in Parameters.StepperDriverData: # Driver is recognised.
            modelist = Parameters.StepperDriverData[driver]['modelist'] # Pull the driver's modelist.
            # What are the mode signals for the selected microstepping ratio of the motor?
            if not str(microstepratio) in modelist: # Keys are strings, not integers.
                self.Log("motorcontrol(",name,") observation microstepratio",microstepratio,"is not in",driver,"modelist.",level='error',terminal=True)
                raise Exception("motorcontrol(" + str(name) + ") observation microstepratio " + str(microstepratio) + " is not in " + str(driver) + "modelist.")
            # microstep ratio is recognised. Pull the modepin settings.
            modesignals = modelist[str(microstepratio)]['modesignals']
            self.Log("motorcontrol(",name,") observation microstep ratio",microstepratio,"for",driver,"uses mode settings",modesignals,terminal=False)
            # What are the mode signals for the selected full step (slew) ratio of the motor?
            if not str(self.SlewMicrosteps) in modelist: # Keys are strings, not integers.
                self.Log("motorcontrol(",name,") slew microstepratio",self.SlewMicrosteps,"is not in",driver,"modelist.",level='error',terminal=True)
                raise Exception("motorcontrol(" + str(name) + ") slew microstepratio",self.SlewMicrosteps,"is not in " + str(driver) + "modelist.")
            # microstep ratio is recognised. Pull the modepin settings.
            slewsignals = modelist[str(self.SlewMicrosteps)]['modesignals']
            self.Log("motorcontrol(",name,") slew microstep ratio",self.SlewMicrosteps,"for",driver,"uses mode settings",slewsignals,terminal=False)
        else: # Driver is not recognised.
            self.Log("motorcontrol(",name,") steppermotor driver",driver,"is not recognised.",level='error',terminal=True)
            raise Exception("Steppermotor driver " + str(driver) + " is not recognised.")
        self.SlewSignals = slewsignals # What are the settings for the mode pins to the driver board? (Large SLEW, GOTO and HOME moves)
        self.ModeSignals = modesignals # What are the settings for the mode pins to the driver board? (Find movements during observations)
        self.WarningAngle = 10 # Can warn if position is within this angle of a limit.
        self.Horizon = horizon # If set the motor will not go below this angle when tracking a target. Allows motor to move below the horizon for other reasons, but not track a target below the horizon. If set to None, this has no effect.
        self.MinAngle = minangle # Physical minimum angle that this motor is allowed to go to.
        self.MinObservationAngle = minangle # Minimum angle that an observation is allowed to go to.
        if self.Horizon != None: self.MinObservationAngle = max(self.MinAngle,self.Horizon) # How low can an observation be made?
        self.MinWarningAngle = self.MinObservationAngle + self.WarningAngle # Can warn if within xx degrees of minimum position.
        self.MaxAngle = maxangle
        self.MaxWarningAngle = maxangle - self.WarningAngle # Can warn if within xx degrees of maximum position.
        self.LimitAngle = limitangle # The motor will reverse around a limit rather than crossing it.
        self.Orientation = orientation
        self.BacklashAngle = backlashangle
        self.CurrentAngle = currentangle # This will be updated by the microcontroller once running. 
        self.PreviousAngle = None # Holds angle from previous status message.
        self.PreviousMctlTimestamp = None # Says when the previous angle was set.
        self.RestAngle = restangle
        self.MotorStepsPerAxisDegree = self.MotorStepsPerRev / 360.0
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
        self.AxisSpeed = 0.0 # Currently calculated telescope speed (degrees/second).
        self.MonitorMove = False # Set to True to enable text updates as moves are performed. False to suppress. GoToAngle(), HomePosition(), SetMotorAngle respect this.
        self.Restarted() # Make sure that status flags are reset for a 'new' unconfigured motor.

    def __del__(self):
        """ When deleted, remove this motor from the global list of all available motors. """
        self.AllMotors.remove(self) # Class attribute AllMotors points to ALL sibling motors. Remove this motor from the list when deleted.

    def ShowMotorStatus(self):
        """ Print general status of the motor. """
        print(textcolor.yellow("Motor:",self.MotorName))
        print("- RecoveryFileName:",self.RecoveryFileName)
        print("- Driver:",self.Driver)
        print(textcolor.white("Current status:"))
        print("- MotorConfigured:",self.MotorConfigured)
        print("  Microcontroller acknowledges receipt of configuration")
        print("- CurrentAngle:",Deg3dp(self.CurrentAngle,DegreeSymbol))
        print("- Position:",self.AngleToStep(self.CurrentAngle),"steps")
        if self.AxisSpeed != None and self.AxisSpeed != 0:
            print("- Latest AxisSpeed:",str(round(self.AxisSpeed,4)) + DegreeSymbol + "/s")
            print("  (Last reported movement rate of the telescope)")
        else:
            print("- Latest AxisSpeed:",self.AxisSpeed,DegreeSymbol + "/s")
            print("  (Last reported movement rate of the telescope)")
        print(textcolor.white("Gearing"))
        print("- GearRatio:",self.GearRatio)
        print("- MotorStepsPerRev:",self.MotorStepsPerRev)
        print("  Motor native full steps per rev:",round(self.MotorStepsPerRev / self.MicrostepRatio,0))
        print("- MotorStepsPerAxisDegree:",round(self.MotorStepsPerAxisDegree,3))
        print("  (Motor needs this many steps to move itself 1 degree)")
        print("- AxisStepsPerRev:",self.AxisStepsPerRev)
        print("  (Motor steps required to move telescope one full revolution)")
        print(textcolor.white("Fine motor movements (during observations):"))
        print("- MicrostepRatio:",self.MicrostepRatio)
        print("  (Included in MotorStepsPerRev)")
        print("- ModeSignals:",self.ModeSignals)
        print("  (Mode pin settings for driver during observations)")
        print(textcolor.white("Large motor movements (GOTO and HOME):"))
        print("- Enabled:",Parameters.SlewEnabled)
        print("- SlewMicrosteps:",self.SlewMicrosteps)
        print("- SlewSignals:",self.SlewSignals)
        print("  (Mode pin settings for driver during large GOTO moves)")
        print(textcolor.white("Configuration:"))
        print("- MinAngle:",Deg3dp(self.MinAngle,DegreeSymbol))
        print("  Telescope will not move below this angle")        
        print("- Horizon:",Deg3dp(self.Horizon,DegreeSymbol))
        print("- MinObservationAngle:",Deg3dp(self.MinObservationAngle,DegreeSymbol))
        print("  (Observations not allowed below this angle)")
        print("- MinWarningAngle:",Deg3dp(self.MinWarningAngle,DegreeSymbol))
        print("  (Warning when telescope gets this close to minimum observation angle)")
        print("- MaxAngle:",Deg3dp(self.MaxAngle,DegreeSymbol))
        print("  (Telescope will not move above this angle)")        
        print("- MaxWarningAngle:",Deg3dp(self.MaxWarningAngle,DegreeSymbol))
        print("  (Warning when telescope gets this close to maximum angle)")   
        print("- OptimiseMoves:",self.OptimiseMoves)
        if self.OptimiseMoves:
            print("  (Trajectories can cross 0/360 limit if the movement is more efficient)")
        else:
            print("  (Trajectories cannot cross cross 0/360 movement limits")
            print("   Telescope will 'reverse' from a limit to track objects which cross it)")
        print("- Orientation:",self.Orientation)
        print("  (+1 / -1 flips rotation direction of motor)")
        print("- BacklashEnabled:",Parameters.BacklashEnabled)
        print("  (Allow extra motor movement when changing direction)")
        print("- BacklashAngle:",Deg3dp(self.BacklashAngle,DegreeSymbol))
        print("  (Size of extra motor movement when changing direction)")
        print("- RestAngle:",Deg3dp(self.RestAngle,DegreeSymbol))
        print("  (Home/Parking position of the telescope)")
        print("- FastTime:",self.FastTime,"s")
        print("  Approximate steps per second:",round((1 / (2 * self.FastTime)),2))
        print("  Approximate time for full revolution:",HRSeconds(self.AxisStepsPerRev * 2 * self.FastTime),"(",self.AxisStepsPerRev,"steps",")")
        print("  Approximate time for telescope to move 10 degrees:",HRSeconds(self.AxisStepsPerRev * 2 * self.FastTime / 36),"(",int(self.AxisStepsPerRev / 36),"steps",")")
        print("- SlowTime:",self.SlowTime,"s")
        print("  Approximate steps per second:",round((1 / (2 * self.SlowTime)),2))
        print("- TimeDelta:",self.TimeDelta,"s")
        print(textcolor.white("Trajectory:"))
        print("- TrajectorySegmentSize:",self.TrajectorySegmentSize,"s")
        print("- TrajectoryValid:",self.TrajectoryValid)
        print("- TrajectoryEntries:",self.TrajectoryEntries)
        print("- TrajectoryValidUntil:",DisplayDT(self.TrajectoryValidUntil))
        print("- OnTarget:",self.OnTarget)
        print(textcolor.white("Tuning:"))
        print("- LatestTuneStart:",DisplayDT(self.LatestTuneStart))
        print("- LatestTuneTime:",DisplayDT(self.LatestTuneTime))
        print("- LatestTuneSteps:",self.LatestTuneSteps)
        print("- TuneCommandCount:",self.TuneCommandCount)
        print("- OpenTuneCommands:",self.OpenTuneCommands)
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
            Expects input like          tune complete azimuth yyyymmddhhmmss -342 yyyymmddhhmmss 101   
                                          0     1        2          3          4        5         6   """
        self.Log("Motor",self.MotorName,"received tune acknowledgement:",line,terminal=False)
        lineitems = line.split(" ") # Separate each element of the line. 
        self.LatestTuneTime = MctlStringToDatetime(lineitems[3]) # Element #3 is the timestamp of the last tune command completed.
        steps = TextToInt(lineitems[4])
        endtime = lineitems[3] # When did the tune complete?
        if len(lineitems) > 5: # When did the tune start?
            self.LatestTuneStart = MctlStringToDatetime(lineitems[5]) # Start time known.
        else:
            self.LatestTuneStart = self.LatestTuneTime # Start time not known.
        if len(lineitems) > 6: # TuneCommandCount reference is returned. We know which original tune command this was.
            tcc = TextToInt(lineitems[6])
            if tcc != None:
                if tcc in self.OpenTuneCommands: # We've found this tune command in the pending list, we can remove it now.
                    self.OpenTuneCommands.remove(tcc) # Remove it from the list, it's now complete.
                    self.Log("Motor",self.MotorName,"received acknowledgement #",tcc,terminal=False)
                else:
                    self.Log("Motor",self.MotorName,"received unexpected tune acknowledgement #",tcc,"ignored.",terminal=False)
            if len(self.OpenTuneCommands) > 0: # Some tune commands still outstanding.
                self.Log("Motor",self.MotorName,"has outstanding tune commands remaining:",self.OpenTuneCommands,terminal=False)

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
                self.Log("motorcontrol.GoToAngle(", self.MotorName, "): Check RPi<>Mctl communication if problem persists.",terminal=False)
            mcl = 0 # How many attempts to configure the motor?
            while self.MotorConfigured == False: # Send configuration to the motor until it's acknowldeged. (May take a few seconds).
                mcl += 1 # Count how many times we've sent the configuration.
                if mcl > 15: # Too many attempts.
                    self.Log("motorcontrol.GoToAngle(", self.MotorName, "): Motor has failed to configure. Abandoning GOTO. (RPi<>Mctl comms?)",level='error')
                    return False # Report failure.
                self.SendConfig() # Send the motor configuration regularly.
                if self.MotorConfigured: 
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): CheckMotorConfig: Motor reports it is now configured.',terminal=False)
                    break # All motors configured. OK to proceed.
                time.sleep(5) # Pause a moment.
                if rt.Due(): # It's time to try resetting the microcontroller.
                    self.Log('motorcontrol.GoToAngle(', self.MotorName, '): CheckMotorConfig: Motor config not acknowledged. Resetting microcontroller. (RPi<>Mctl comms?)',terminal=True)
                    Mctl.Reset(planned=True)
                self.Log("motorcontrol.GoToAngle(",self.MotorName,"): Not yet configured. Trying to configure again.",terminal=False)
                self.Log("motorcontrol.GoToAngle(", self.MotorName, "): Check RPi<>Mctl communication if problem persists.",terminal=False)
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
                print(NowHMS(),self.MotorName,textcolor.white(Deg3dp(self.CurrentAngle,DegreeSymbol)),textcolor.clearlineforward())
            while True:
                if prevangle != self.CurrentAngle: # The motor has moved.
                    prevangle = self.CurrentAngle
                    prevangletime = NowUTC()
                    if self.MonitorMove: # Display movement progress.
                        print(textcolor.cursorup(),NowHMS(),self.MotorName,textcolor.white(Deg3dp(self.CurrentAngle,DegreeSymbol)),textcolor.clearlineforward())
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

    def CalculateAxisSpeed(self):
        """ Based upon last 2 valid status messages, what speed is the motor currently moving at? 
            Degrees per second returned. """
        anglechange = 0.0
        timechange = 0.0
        self.AxisSpeed = 0.0 # No speed unless we know it!
        if self.CurrentAngle != None and self.PreviousAngle != None:
            anglechange = self.CurrentAngle - self.PreviousAngle
        if self.StatusMctlTimestamp != None and self.PreviousMctlTimestamp != None:
            timechange = (self.StatusMctlTimestamp - self.PreviousMctlTimestamp).total_seconds()
        if timechange != 0.0:
            self.AxisSpeed = anglechange / timechange

    def EstimateCurrentAngle(self):
        """ Given current system clock and the latest status information from the motorcontroller, estimate the current angle of the motor. """
        if self.AxisSpeed != None and self.StatusMctlTimestamp != None:
            timechange = (NowUTC() - self.StatusMctlTimestamp).total_seconds() # Seconds since last position sent. 
            anglechange = self.AxisSpeed * timechange # How many degrees has the telescope probably moved in this time?
            angle = (self.CurrentAngle + anglechange) % 360 # Where is the telescope likely to be now (0-360 degree range)
        else:
            angle = self.CurrentAngle # Just use latest static angle we know.
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
            self.Log("motorcontrol.ReceiveStatus(", self.MotorName, "): Check RPi<>Mctl communication if problem persists.",terminal=False)
            self.SendConfig() # Send motor configuration now.

        # Calculate the following attributes regardless of configuration status.
        self.PreviousMctlTimestamp = self.StatusMctlTimestamp # Store previous timestamp
        self.StatusMctlTimestamp = MctlStringToDatetime(lineitems[2]) # When did the Microcontroller send the status message?
        #self.Log("motorcontrol.ReceiveStatus(",self.MotorName,"): StatusMctlTimestamp now",self.StatusMctlTimestamp,"from",line,terminal=False)
        self.StatusLocalTimestamp = NowUTC() # When did the RPi process the status message?
        _ = self.CalculateAxisSpeed() # Check motor speed.

        return True
        
    def SendConfig(self):
        """ Send configuration information from this motor image to the microcontroller
            where it will be loaded into the motor control there. 
                    
            configure motor 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n  n 90.0 240 400  1 180.0 nnn n nnn n
                0       1         2           3       4    5  6   7  8   9     10    11  12 13 14 15   16 17  18 19    20  21 22 23
                
                 2 = UTC timestamp when message sent.
                 3 = Motor name.
                 4 = Last reported (Current) angle.
                 5 = Minimum allowed angle.
                 6 = Maximum allowed angle.
                 7 = Backlash angle.
                 8 = Motor orientation.
                 9 = FastTime.
                10 = SlowTime.
                11 = TimeDelta.
                12 = Delay between automatic status messages.
                13 = FaultSensitive (stop if fault signal from driver).
                14 = OptimiseMoves (allows unlimited full rotation).
                15 = LimitAngle (motor will not cross this angle) - under development.
                16 = Gear ratio.
                17 = Motor steps per revolution (1 revolution of motor).
                18 = Slew Steps (the number of 'microsteps' taken when making large moves).
                19 = Motor rest angle (when homed).
                20 = Microstepping mode signals (used when making observation).
                21 = SlewEnabled flag (Can motor make FULL STEP moves during large position changes). <- Experimental feature.
                22 = Slew stepping mode signals (used when making large position changes). <- Experimental feature.
                23 = TraceMove flag (Enhanced log messages back from the motor)
                    """
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
        line += BoolToString(self.OptimiseMoves) + ' ' # Field 14: When 'y' the microcontroller can take shortcuts for large moves.
        line += str(self.LimitAngle) + ' ' # Field 15: Movement limit, motor will reverse around rather than crossing this limit.
        line += str(self.GearRatio) + ' ' # Field 16: GearRatio.
        line += str(self.MotorStepsPerRev) + ' ' # Field 17 MotorStepsPerRev
        line += str(self.SlewStepMultiplier) + ' ' # Field 18 SlewStepMultiplier (The number of microsteps taken when making large Slew moves).
        line += str(self.RestAngle) + ' ' # Field 19 RestAngle
        line += self.ModeSignals + ' ' # Field 20 Steppermotor mode signals for microstepping.
        line += BoolToString(Parameters.SlewEnabled) + ' ' # Field 21 SlewEnabled flat. (Can motor make FULL STEP moves during large position changes)
        line += self.SlewSignals + ' ' # Field 22 Steppermotor mode signals for full steps (Fast slew).
        line += BoolToString(Parameters.TraceMove) + ' ' # Field 23 TraceMove. (Enhanced log messages from the motors)
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
            tune 20210410154530 azimuth -234 1
              0        1           2      3  4

            0 : always 'tune'
            1 : timestamp
            2 : motorname
            3 : steps to move
            4 : tune command reference (for acknowledgements) """
              
              
        # This first makes sure that the motor is configured, it waits for that to be acknowledged before sending the tune command.
        # Check that the motors are configured before proceeding.
        self.Log('motorcontrol.TunePosition(', self.MotorName,') by',delta,'steps.',terminal=False)
        # There can be input queued from the microcontroller waiting to be handled.
        # - We should check in case the motor has lost its configuration before proceeding.
        self.Log('motorcontrol.TunePosition(', self.MotorName, '): CheckMotorConfig: Precheck motor is still configured.',terminal=False)
                
        # Motor is now configured. Perform the actual move now. 
        if self.MotorConfigured: # Only allow tuning if the motor is configured.
            dtn = NowUTC()
            self.TuneCommandCount += 1 # Unique reference sent with each tune command for debug/acknowledgement.
            self.OpenTuneCommands.append(self.TuneCommandCount) # Not this is a pending tune command, has not been completed yet.
            line = "tune " + CleanDatetimeString(str(dtn)) + ' ' + self.MotorName + " " + str(delta) + " " + str(self.TuneCommandCount)
            Mctl.Write(line)
            # This doesn't wait for feedback, it is up to the motorcontroller to deal with the message when it sees fit.
            # This program may send further tune messages if it still needs to change things.
        else:
            self.Log("motorcontrol.TunePosition(", self.MotorName, "): Motor is not yet configured. Tune command will not be sent.",level='error')
            self.Log("motorcontrol.TunePosition(", self.MotorName, "): Check RPi<>Mctl communication if problem persists.",terminal=True)
            
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
        
            trajectory 20210409104504 azimuth 20210325223342 181.6003 20210325223442 181.7003 45000 47500
                0             1          2           3          4            5           6      7     8
                
                1 = UTC timestamp when record sent.
                2 = Motorname
                3 = Start UTC of segment.
                4 = Start angle of segment.
                5 = End UTC of segment.
                6 = End angle of segment.
                7 = Start motorposition of segment.
                8 = End motorposition of segment.
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
        if self.TrajectoryValidUntil is None: # Where does previously downloaded trajectory end? = Start of this chunk.
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
            while MaxIterations > 0: # Time out if max iterations hit.
                MaxIterations -= 1 # Reduce timeout.
                segmentsize += int(self.TrajectorySegmentSize / 4) # Increase the segment size.
                nextutc = startutc + timedelta(seconds=segmentsize) # Timestamp of the larger segment size.
                az, alt = targetobj.AzAltDegrees(time=Datetime2Ts(nextutc)) # Needs to be Skyfield time!
                if self.MotorName == 'altitude': nextangle = alt
                else: nextangle = az
                #if self.MinAngle > nextangle or self.MaxAngle < nextangle: break # Cannot extend any further. *!*
                if self.MinObservationAngle > nextangle or self.MaxAngle < nextangle: break # Cannot extend any further. *!*
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
        startpos = int(self.AngleToStep(startangle))
        endpos = int(self.AngleToStep(endangle))
        line += str(startpos) + ' ' # Add actual stepper position for START of segment.
        line += str(endpos) + ' ' # Add actual stepper position for END of segment.
        self.Log('motorcontroller.ExtendTrajectory(',self.MotorName, \
                 ') Segment',(endutc - startutc).total_seconds(),'seconds,', \
                 startutc,round(startangle,4),'deg -',endutc,round(endangle,4),'deg,', \
                 startpos,'-',endpos,'steps', \
                 terminal=False)
        #if endangle >= self.MinAngle and endangle <= self.MaxAngle: # We're still within range. *!*
        if endangle >= self.MinObservationAngle and endangle <= self.MaxAngle: # We're still within range. *!*
            Mctl.Write(line)
            self.LastSentTrajectoryKey = self.TrajectoryValidUntil # Cache the trajectory calculation, if the same calculation is triggered, we can re-use the earlier copy for speed.
            self.LastSentTrajectoryData = line[26:] # Store the data sent (without the leading timestamp, a fresh timestamp will be used if resent). 
            self.Log('motorcontroller.ExtendTrajectory(', self.MotorName, '): Cached trajectory calculation:', "'" + self.LastSentTrajectoryData + "'",terminal=False)
        else:
            self.Log('motorcontroller.ExtendTrajectory(' + self.MotorName + '): Trajectory is now complete.',terminal=False)

# ------------------------------------------------------------------------------------------------------

# Create and initialize motor instances.
AzimuthControl = motorcontrol('azimuth',
                              gearratio=Parameters.AzimuthGearRatio, # 240 # Gearing of the drive system ignoring motor steps.
                              fullstepsperrev=Parameters.AzimuthMotorStepsPerRev, # 400 # FullStep count of the motor before microstepping added.
                              microstepratio=Parameters.AzimuthMicrostepRatio, # 1 # Level of microstepping to be added for observations. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
                              minangle=Parameters.MinAzimuthAngle, # 0 - Physical minimum angle motor will move to. 
                              maxangle=Parameters.MaxAzimuthAngle, # 360 - Physical maximum angle motor will move to.
                              restangle=Parameters.AzimuthRestAngle, # 180.0,
                              currentangle=Parameters.AzimuthRestAngle, # 180.0 # Yes it's the same as above!
                              backlashangle=Parameters.AzimuthBacklashAngle, # 0.0
                              orientation=Parameters.AzimuthOrientation, # -1,
                              limitangle=Parameters.AzimuthLimitAngle,
                              horizon=None, # None # There is no tracking horizon applied to this motor.
                              fasttime=Parameters.FastTime,
                              slowtime=Parameters.SlowTime,
                              timedelta=Parameters.TimeDelta,
                              slewmicrosteps=Parameters.AzimuthSlewMicrostepRatio, # 1 # Level of microstepping to be added for GOTO/HOME moves. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
                              optimisemoves=Parameters.OptimiseMoves, # Can motor move freely across the 0-360 limit to keep tracking targets?
                              logger=MainLog)
AltitudeControl = motorcontrol('altitude',
                              gearratio=Parameters.AltitudeGearRatio, # 240,
                              fullstepsperrev=Parameters.AltitudeMotorStepsPerRev, # 400 # FullStep count of the motor before microstepping added.
                              microstepratio=Parameters.AltitudeMicrostepRatio, # 1 # Level of microstepping to be added for observations. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
                              minangle=Parameters.MinAltitudeAngle, # 0 - Physical minimum angle motor will move to.
                              maxangle=Parameters.MaxAltitudeAngle, # 90 - Physical maximum angle motor will move to.
                              restangle=Parameters.AltitudeRestAngle, # 0.0,
                              currentangle=Parameters.AltitudeRestAngle, # 0.0,
                              backlashangle=Parameters.AltitudeBacklashAngle, # 0.0,
                              orientation=Parameters.AltitudeOrientation, # -1,
                              limitangle=Parameters.AltitudeLimitAngle,
                              horizon=Parameters._Horizon, # 0 # There is a tracking horizon. Even if motor can physically move below the horizon, observations are not made.
                              fasttime=Parameters.FastTime,
                              slowtime=Parameters.SlowTime,
                              timedelta=Parameters.TimeDelta,
                              slewmicrosteps=Parameters.AltitudeSlewMicrostepRatio, # 1 # Level of microstepping to be added for GOTO/HOME moves. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
                              optimisemoves = False, # Motor must respect movement limits.
                              logger=MainLog)
MotorControls = motorcontrol.AllMotors #  Alias for the list of ALL defined motors held in the motorcontrol class.

# Assign filename for the 'observation running' flag file. Thie file indicates that an observation started, but has not yet cleanly finished.
ObservationRunningFile = FolderHandler.PrepFile('dataroot','observationrunningflag.txt') # Work out where to store the ObservationRunning file.

# ------------------------------------------------------------------------------------------------------

def LastReportedLocationDatetime():
    """ What's the oldest datetime stamp of the reported camera locations? """
    result = None
    for i in MotorControls:
        if result is None or (i.StatusMctlTimestamp != None and result > i.StatusMctlTimestamp): result = i.StatusMctlTimestamp
    return result
    
# ------------------------------------------------------------------------------------------------------

def LastReportedAltAz():
    """ Retrieve the current physical position of the camera. 
        Returns values based upon the data stored in the MotorControl objects. """
    az_degree = 0.0
    alt_degree = 0.0
    for i in MotorControls:
        WarningFlagName = "LastReportedAltAz_Stale_" + i.MotorName # Which warning message are we considering?
        if i.StatusMctlTimestamp != None:
            td = abs(NowUTC() - i.StatusMctlTimestamp).total_seconds()
            if td > 20: # Position is > 20 seconds old. Expect an update more regularly than this.
                if FirstWarningFlag(WarningFlagName): # Only issue the warning message once, don't keep repeating it.
                    MainLog.Log("LastReportedAltAz(",i.MotorName,") position ",Deg3dp(i.CurrentAngle),"deg is stale.",td,"s since",i.StatusMctlTimestamp,"UTC",terminal=False)
            else: ResetWarningFlag(WarningFlagName) # Reset so that warning will be reissued if the condition arises again.
        else: MainLog.Log("LastReportedAltAz(",i.MotorName,") StatusMctlTimestamp is None.",terminal=False)
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
    def __init__(self,logger=None):
        """ Initialize status fields. """
        self._FileNames = []
        self.SetLogger(logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.ProgramStartTime = NowUTC() # When the program starts.
        self.Target = None # No target yet. This gets set to a valid target object when the target is selected.
        self.TechFitsTagsFile = None # Which 'technical' fits tags file are we using (if any?)
        self.WeatherFitsTagsFile = None # Which 'weather' fits tags file are we using (if any?)
        self.TechExifTagsFile = None # Which 'technical' jpg exif tags file are we using (if any?)
        self.WeatherExifTagsFile = None # Which 'weather' jpg exif tags file are we using (if any?)
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
        self.MotorControlMode = 'idle' # What mode are we in? 'idle'/'remote'/'trajectory'. This controls the responses to some automated status messages.
        # Define the different motor control modes. idle, direct, trajectory.
        self.MCMdict = {'idle' : {'description' : 'motors at rest.', 'trajectory' : False},
                        'direct' : {'description' : 'motor movement controlled directly from this software.', 'trajectory' : False},
                        'trajectory' : {'description' : 'motor movement is autonomous following trajectory.', 'trajectory' : True}}
        self.MaintainTrajectory = None
        self.MctlPinDict = {} # Used to store microcontroller pin status if it's received from Tiny2350. (Not available from Tiny2040)
        self.SetMotorControlMode(self.MotorControlMode) # Updates self.MaintainTrajectory
        self.TerminateMctlHandler = False # Set to TRUE to cause MctlHandler loop to terminate.
        self.ControllerVersion = 'unknown' # The microcontroller should report its software version number and store it here.
        self.TimeDiff = None # Timedelta between remote clock and local clock (includes messaging delays).
        Mctl.ReportedResetReason = '' # eg 'POWER_ON' # RESET REASON if reported.
        Mctl.ReportedClockspeed = 0.0 # Clock speed in MHz
        Mctl.ReportedVoltage = 0.0 # CPU voltage if known
        Mctl.ReportedMemAlloc = 0 # Memory allocated (bytes)
        Mctl.ReportedMemFree = 0 # Memory free (bytes)
        Mctl.ReportedTemperature = 0.0 # CPU temperature (C)
        Mctl.ReportedFeatures = [] # Microcontroller's code.py version number.

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

    def CheckCpuStatus(self,line):
        """ RP2350 sends cpu status messages back too. 
            Monitor these especially if heavily overclocking the microcontroller.
        
            cpu status 20240819190830 POWER_ON 200.0 0.0 249904 141840 31
             
            cpu status 20241202220908 POWER_ON 200.0 0.0 245040 138768 21 RP2350_PICO
             0    1         2            3       4    5     6     7     8     9
             
             3 = Reset reason (if available)
             4 = Clockspeed in MHz
             5 = CPU voltage (V) (if available)
             6 = Memory allocated (bytes)
             7 = Memory free (bytes)
             8 = CPU temperature (C) (if available)
             9 = Feature list from microcontroller. ('_' separated)
            
            """
        #self.Log('sessionstatus.CheckCpuStatus: Received',line,terminal=False)
        lineitems = line.split(' ')
        Mctl.ReportedResetReason = lineitems[3] # eg 'POWER_ON' # RESET REASON if reported.
        Mctl.ReportedClockspeed = 1e6 * float(lineitems[4]) # Clock speed in MHz
        if IsFloat(lineitems[5]): Mctl.ReportedVoltage = float(lineitems[5]) # CPU voltage if known
        else: Mctl.ReportedVoltage = 0.0 # Nothing reported.
        Mctl.ReportedMemAlloc = int(lineitems[6]) # Memory allocated (bytes)
        Mctl.ReportedMemFree = int(lineitems[7]) # Memory free (bytes)
        Mctl.ReportedTemperature = float(lineitems[8]) # CPU temperature (C)
        if len(lineitems) > 9: # Get the feature list from the microcontroller software.
            Mctl.ReportedFeatures = lineitems[9].split('_')
        
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

                 session status 20241202220208 y n y 247 0 tmr 0 1.2.0
                    0      1           2       3 4 5   6 7  8  9   10
                    
        2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        3: BoolToString(Clock.ClockSynchronised) Do the RPi and Microcontroller clocks agree?
        4: BoolToString(self.AutonomousControl) Can motors drive themselves? Fully configured and trajectory known.
        5: BoolToString(self.RemoteControl) Can motors be commanded remotely? Fully configured.
        6: str(utime.time() - RPi.StartTime) Alive seconds.
        7: Flush count
        8: Code indicating the reason the message was sent.
        9: Microcontroller exception count (if available) 
        10: Microcontroller code.py version (if available) """
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
        if len(lineitems) > 10: # Code.py version number is available.
           self.ControllerVersion = lineitems[10]
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
                   if duration.total_seconds() < Parameters.TrajectoryWindow and self.ClockSynchronised: # We need to add time to the trajectory plan.
                       self.Log('sessionstatus.CheckTrajectory: Decided to extend.',terminal=False)
                       i.ExtendTrajectory(targetobj)
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
        """ Handle controller version message. 
            Message looks like this :-
            
              controller version 0.0.0
              
            pilomar has a list of acceptable versions (MAJOR.MINOR), it doesn't care about .MICRO version number.
            It reports to the log file if the controller is reporting an incompatible version. 
            
              """
        self.Log('sessionstatus:CheckControllerVersion(): ' + line,terminal=False)
        lineitems = line.split(' ')
        result = False
        if len(lineitems) > 2:
            self.ControllerVersion = lineitems[2]
            try:
                compversion = self.ControllerVersion[:self.ControllerVersion.rindex('.')] # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
                if compversion in ACCEPTABLECONTROLLERVERSIONS:
                    result = True # Version is good.
                else:
                    self.Log('sessionstatus.CheckControllerVersion():',self.ControllerVersion,'is not in',ACCEPTABLECONTROLLERVERSIONS,terminal=True)
                    ErrorWindow.Print(NowHMS() + ' Controller version ' + compversion + ' is not in ' + str(ACCEPTABLECONTROLLERVERSIONS))
            except Exception as e:
                self.Log('sessionstatus.CheckControllerVersion(): Failed to check',self.ControllerVersion,level='error')
                self.Log('sessionstatus.CheckControllerVersion(): Failed with',str(e),level='error')
        else:
            self.Log('sessionstatus.CheckControllerVersion(): Response is incomplete:',line,level='warning')
        return result

    def MctlPinStatus(self,line):
        """ Save the status of the pins from the microcontroller locally. 
            This is a development feature supported by Tiny2350. (Not on Tiny2040 version).
            Received a line like this from the microcontroller....
            pin status 20241130202951 A3 azstep n A2 altstep n A1 dir n GP3 mode0 n GP4 mode1 n GP5 mode2 n GP2 enable n GP6 azfault y GP7 altfault y USER_SW boot y LED_R red y LED_G green y LED_B blue y """
        self.Log('sessionstatus.MctlPinStatus(): Received',line,terminal=False)
        i = 3 # Start reading the entries out of the received message and update the information in a local dictionary.
        lineitems = line.split(' ')
        while i < len(lineitems): # Keep reading pin status entries until the whole line has been processed.
            p_num = lineitems[i]
            p_name = lineitems[i + 1]
            p_status = StringToBool(lineitems[i + 2])
            dict_entry = {'name':p_name, 'state':p_status, 'updated':StringToDatetime(lineitems[2])}
            self.Log('sessionstatus.MctlPinStatus(): Storing',dict_entry,'from',dict_entry['updated'],terminal=False)
            self.MctlPinDict[p_num] = dict_entry
            i += 3 # Move on to next entry.

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
                if threading.main_thread().is_alive() == False: # Check if parent is still alive. Quit if it is nolonger there.
                    self.Log('sessionstatus.MctlHandler(): Main thread nolonger alive.',terminal=False)
                    break
                if len(Mctl.Lines) > 0: # Something to handle.
                    line = Mctl.Read() # Pull next available message from microcontroller.
                    # Are all the same messages received, processed, logged or ignored in the same way?
                    if len(line) > 0: # Data to process.
                        if line.startswith('session'): self.CheckSessionStatus(line) # Gather information about the microcontroller general health.
                        elif line.startswith('comms'): self.CheckCommsStats(line) # Gather statistics about UART communication handling.
                        elif line.startswith('controller log'): pass # Just log messages from the microcontroller. No action needed.
                        elif line.startswith('log'): pass # Just log messages from the microcontroller. No action needed.
                        elif line.startswith('cleared trajectory'): pass # Just log these.
                        elif line.startswith('cpu status'): self.CheckCpuStatus(line) # Check CPU status information from the microcontroller.
                        elif line.startswith('motor'): self.CheckMotorStatus(line) # Check motor info from microcontroller, respond with missing config etc.
                        elif line.startswith('controller heartbeat'): pass # Just log these.
                        elif line.startswith('heartbeat'): pass # Just log these.
                        elif line.startswith('acknowledged'): pass # Just log these.
                        elif line.startswith('#'): pass # Comments from microcontroller, ignore them.
                        elif line.startswith('controller version'): self.CheckControllerVersion(line) # Check that software is compatible across devices.
                        elif line.startswith('goto rejected'): self.CheckGotoRejected(line) # A goto command was rejected.
                        elif line.startswith('tune complete'): self.CheckTuneComplete(line) # A tune command has been processed.
                        elif line.startswith('controller started'): self.CheckControllerStarted(line) # Microcontroller reports a restart. Trigger chain of updates.
                        elif line.startswith('pin status'): self.MctlPinStatus(line) # Store the reported pin status from the microcontroller. 
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
        self.Log('sessionstatus.MctlHandler(): End.',terminal=False)

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
        SessionWindow.FieldValue('CAZA',"(" + str(AzAge) + "s)",fg=azafg,bg=OSW_TEXT_BG) # Age of camera reported position.
        SessionWindow.FieldValue('CALTA',"(" + str(AltAge) + "s)",fg=altafg,bg=OSW_TEXT_BG) # Age of camera reported position.
        SessionWindow.FieldValue('CLKDIF',str(self.TimeDiffSecs()) + "s") # Time difference/delay between RPi and Microcontroller.
        for i in MotorControls: # Report trajectory information for each motor.
            if i.MotorName == 'azimuth': fnp = 'Z'
            else: fnp = 'L'
            SessionWindow.FieldValue(fnp + 'C',i.MotorConfigured)
            if i.MotorConfigured: SessionWindow.FieldColor(fnp + 'C',fg=OSW_TEXT_GOOD)
            else: SessionWindow.FieldColor(fnp + 'C',fg=OSW_TEXT_POOR)
            SessionWindow.FieldValue(fnp + 'A',"{:07.3f}".format(i.CurrentAngle) + DegreeSymbol)
            if Parameters.UseDynamicTrajectoryPeriods:
                SessionWindow.FieldValue(fnp + 'MODE','Dynamic trajectory')
            else:
                SessionWindow.FieldValue(fnp + 'MODE',"Fixed trajectory")
            if i.AxisSpeed is None:
                SessionWindow.FieldValue(fnp + 'DPS','0.0' + DegreeSymbol)
            else:
                SessionWindow.FieldValue(fnp + 'DPS',str(i.AxisSpeed)[:6] + DegreeSymbol)
            SessionWindow.FieldValue(fnp + 'D',i.TrajectoryEntries)
            if i.TrajectoryEntries > 0: SessionWindow.FieldColor(fnp + 'D',fg=OSW_TEXT_GOOD)
            else: SessionWindow.FieldColor(fnp + 'D',fg=OSW_TEXT_POOR)
            if self.MotorControlMode == 'trajectory':
                SessionWindow.FieldValue(fnp + 'T',i.OnTarget)
                if i.OnTarget: SessionWindow.FieldColor(fnp + 'T',fg=OSW_TEXT_GOOD)
                else: SessionWindow.FieldColor(fnp + 'T',fg=OSW_TEXT_POOR)
                if i.TrajectoryValidUntil != None:
                    temphms = DisplayHmsFromStamp(i.TrajectoryValidUntil,dateaware=True) # Show HH:MM:SS unless it's another day, then show DD HH:MM
                    tempsec = (i.TrajectoryValidUntil - nowutc).total_seconds() # How long does the trajectory last (seconds)?
                    if tempsec > Parameters.TrajectoryWindow: # Valid far enough into the future.
                        SessionWindow.FieldValue(fnp + 'U',temphms,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG)
                        temp = "(" + HRSeconds(tempsec) + ")"
                        SessionWindow.FieldValue(fnp + 'RM',temp,fg=OSW_TEXT_FG,bg=OSW_TEXT_BG)
                    elif tempsec > 0: # Running out soon, needs extending.
                        SessionWindow.FieldValue(fnp + 'U',temphms,fg=OSW_TEXT_POOR,bg=OSW_TEXT_BG)
                        temp = "(" + HRSeconds(tempsec) + ")"
                        SessionWindow.FieldValue(fnp + 'RM',temp,fg=OSW_TEXT_POOR,bg=OSW_TEXT_BG)
                    else: # Already run out.
                        SessionWindow.FieldValue(fnp + 'U',temphms,fg=OSW_TEXT_BAD,bg=OSW_TEXT_BG)
                        temp = "(" + HRSeconds(-1 * tempsec) + ")"
                        SessionWindow.FieldValue(fnp + 'RM',temp,fg=OSW_TEXT_BAD,bg=OSW_TEXT_BG)
                else: # No trajectory data yet.
                    temp = HRSeconds(0)
                    SessionWindow.FieldValue(fnp + 'U',temp,fg=OSW_TEXT_POOR,bg=OSW_TEXT_BG)
                    SessionWindow.FieldValue(fnp + 'RM',"(" + temp + ")",fg=OSW_TEXT_POOR,bg=OSW_TEXT_BG)
            else: # Trajectories not used for this target. Don't show validity.
                SessionWindow.FieldValue(fnp + 'T',"Fixed",fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # OnTarget does not apply for stationary targets.
                SessionWindow.FieldValue(fnp + 'U',"--:--:--",fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Trajectory not needed, so no expiry.
                SessionWindow.FieldValue(fnp + 'RM',"n/a",fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Trajectory not needed, so no expiry.

Session = sessionstatus(logger=MainLog) # Create new session status object.
CameraInUse.Session = Session # Point the camera handler to the session instance too. It pulls data from here.

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Image processing (OpenCV) 
# ///////////////////////////////////////////////////////////////////////////////////

class imagetracker(attributemaster):
    """ ImageTracker uses OpenCV and AstroAlign packages to measure the drift of the 
        stars between images. This may be useful for autocorrecting position or basic image tracking. """
        
    def __init__(self,logger=None):
        self.SetLogger(logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.TrackingInterval = Parameters.TrackingInterval # Check target tracking every nnn seconds.
        self.PreparedImages = 0 # Incrementing counter of images handled.
        self.TargetMinMagnitude = Parameters.TargetMinMagnitude # The actual minimum star magnitude finally selected for the target image.
        self.Reset() # Initialize other storage, including image buffers and attributes.

    def Reset(self):
        """ Reset image cache and related data. """
        self.Log("ImageTracker.Reset: Begin",terminal=False)
        # Reset TargetImage
        self.TargetImage = pilomarimage(name='target',logger=CamLog) # This will be the opencv image buffer.
        self.TargetTimeStamp = None
        self.TargetStarMatchList = []
        self.TargetStarCount = 0
        # Reset MasterImage (Master target map)
        self.MasterImage = pilomarimage(name='master',logger=CamLog) # This will be the opencv image buffer.
        self.MasterTimeStamp = None
        self.MasterStarMatchList = []
        self.MasterStarCount = 0
        # Reset LatestImage
        self.LatestImage = pilomarimage(name='latest',logger=CamLog) # This will be the opencv image buffer.
        self.LatestTimeStamp = None
        self.LatestStarMatchList = []
        self.LatestStarCount = 0
        self.dx = None # Measured delta-x between images.
        self.dy = None # Measured delta-y between images.
        self.ZoneList = [] # No search zones defined.
        self.Log("ImageTracker.Reset: End",terminal=False)

    def SetMasterImage(self,cvimagebuffer,starcount=None,starlist=None,timestamp=None,MinMagnitude=None):
        """ This registers a new master target reference image. """
        self.Log("ImageTracker.SetMasterImage: Begin",terminal=False)
        self.Log("ImageTracker.SetMasterImage: Received image buffer type", str(type(cvimagebuffer)),terminal=False)
        if isinstance(cvimagebuffer,type(None)):
            self.Log("ImageTracker.SetMasterImage: Received None type image buffer. Nothing set.",terminal=False)
            return
        if timestamp is None: # If we don't know the timestamp of the image, use the current clock.
            timestamp = NowUTC() # Assume current clock time.
        self.MasterTimeStamp = timestamp
        self.MasterImage.LoadBuffer(cvimagebuffer)
        self.Log("ImageTracker.SetMasterImage: Loaded image",self.MasterImage.GetDimensions(),terminal=False)
        self.MasterImage.ChangeType('grayscale')
        self.Log("ImageTracker.SetMasterImage: About to measure contrast.",terminal=False)
        contrast_m, contrast_s = self.MasterImage.MeasureContrast() # Calculate contrast for latest image.
        self.Log("ImageTracker.SetMasterImage: Contrast measures",contrast_m, contrast_s,terminal=False)
        self.Log("ImageTracker.SetMasterImage: Prepared image: type", 
                 str(type(self.MasterImage.ImageBuffer)), 
                 "shape", self.MasterImage.GetHeight(), 
                 "x", self.MasterImage.GetWidth(), 
                 "depth",self.MasterImage.GetDepth(),terminal=False)
        self.dx = None
        self.dy = None
        self.MasterStarMatchList = []
        if MinMagnitude != None: 
            self.Log("ImageTracker.SetMasterImage: Setting MinMagnitude to", MinMagnitude,terminal=False)
            self.TargetMinMagnitude = MinMagnitude # The actual minimum star magnitude finally selected for the target image.
        self.Log("ImageTracker.SetMasterImage: registered new target image",terminal=False)
        if starcount is None or starlist is None: # StarCount or StarList not provided, calculate one from the image instead. 
            self.Log("ImageTracker.SetMasterImage: Did not receive StarCount or StarList. Calculating them from image.",terminal=False)
            _,_ = self.MasterImage.CountStars()
        else: # StarCount and StarList already available, just use those.
            self.Log("ImageTracker.SetTargetImage: Received StarCount and StarList. Not recalculating them.",terminal=False)
            self.MasterImage.StarCount = starcount
            self.MasterImage.StarList = starlist
        self.Log("ImageTracker.SetMasterImage: Counted", self.MasterImage.StarCount, "stars.",terminal=False)
        # No need to clean up the image. It was generated to match the standardised image already.
        # Save target image for reference.
        filename = FolderHandler.PrepFile('tracking','MasterTrackingImage_' + UtcTimeStamp() + '.jpg')
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        self.MasterImage.SaveFile(filename)
        # Calculate the transformation between TARGET and LATEST images.
        self.Log("ImageTracker.SetMasterImage: Calling SearchMasterImage...",terminal=False)
        result = self.SearchMasterImage() # Try each target zone for a match.
        self.Log("ImageTracker.SetMasterImage: SearchMasterImage returned " + str(result),terminal=False)

    def SetTargetImage(self,cvimagebuffer,timestamp=None,zone=0):
        """ This registers a new target reference image. """
        self.Log("ImageTracker.SetTargetImage: Begin: Zone",i,terminal=False)
        self.Log("ImageTracker.SetTargetImage: Received image buffer type", str(type(cvimagebuffer)),terminal=False)
        if isinstance(cvimagebuffer,type(None)):
            self.Log("ImageTracker.SetTargetImage: Received None type image buffer. Nothing set.",terminal=False)
            return
        if timestamp is None: # If we don't know the timestamp of the image, use the current clock.
            timestamp = NowUTC() # Assume current clock time.
        self.TargetTimeStamp = timestamp
        self.TargetImage.LoadBuffer(cvimagebuffer)
        self.Log("ImageTracker.SetTargetImage: Loaded image",self.TargetImage.GetDimensions(),terminal=False)
        self.TargetImage.ChangeType('grayscale')
        self.Log("ImageTracker.SetTargetImage: About to measure contrast.",terminal=False)
        contrast_m, contrast_s = self.TargetImage.MeasureContrast() # Calculate contrast for latest image.
        self.Log("ImageTracker.SetTargetImage: Contrast measures",contrast_m, contrast_s,terminal=False)
        self.Log("ImageTracker.SetTargetImage: Prepared image: type", str(type(self.TargetImage.ImageBuffer)), "shape", self.TargetImage.GetHeight(), "x", self.TargetImage.GetWidth(), "depth",self.TargetImage.GetDepth(),terminal=False)
        self.Log("ImageTracker.SetTargetImage: registered new target image",terminal=False)
        _,_ = self.TargetImage.CountStars()
        self.Log("ImageTracker.SetTargetImage: Counted", self.TargetImage.StarCount, "stars.",terminal=False)
        # Save target image for reference.
        filename = FolderHandler.PrepFile('tracking','TargetTrackingImage_' + str(zone).rjust(3,'0') + '_' + UtcTimeStamp() + '.jpg')
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        self.TargetImage.SaveFile(filename)

    def CreateTargetZones(self):
        """ Given a SearchSequence (See ChooseSearchSequence) create a series of search target files from a larger target map.
            This creates a batch of search zone images on disc.
            All available zone images are created even if they are not needed. """
        self.Log("imagetracker.CreateTargetZones: This function should be redundant now.",level='error',terminal=False)
        for i,sequence_entry in enumerate(self.ZoneList):
            self.Log("pilomarimage.CreateTargetZones:",i,sequence_entry,terminal=False)
            distance = sequence_entry[0] # Distance to centre of master map (for sorting)
            zone_width = sequence_entry[1] # Search area width.
            zone_height = sequence_entry[2] # Search area height. 
            zone_centre_x = sequence_entry[3] # Search area centre (on master map). 
            zone_centre_y = sequence_entry[4] # Search area centre (on master map).
            drift_offset_x = sequence_entry[5] # Search result x offset.
            drift_offset_y = sequence_entry[6] # Search result y offset.
            x_start = sequence_entry[7] # Starting pixel for this zone on the master target map.
            y_start = sequence_entry[8] # Starting pixel for this zone on the master target map.
            filename = sequence_entry[9] # Filename to generate on disc.
            NewImageBuffer = pilomarimage(name='searchsequence',logger=CamLog) # Create image handler.
            NewImageBuffer.New(self.LatestImage.GetHeight(),self.LatestImage.GetWidth()) # Create new image buffer.
            self.Log("pilomarimage.CreateTargetZones: Creating",
                     "[",y_start,":",y_start + zone_height,",",
                     "[",x_start,":",x_start + zone_width,",",
                     ":","]",filename,terminal=False)
            NewImageBuffer.ImageBuffer = self.MasterImage.ImageBuffer[y_start:y_start + zone_height,x_start:x_start + zone_width,...] # Pull JUST the selected zone from the master map.
            self.Log("pilomarimage.CreateTargetZones: Created",
                     "(",NewImageBuffer.GetWidth(),"w by",NewImageBuffer.GetHeight()," h)","pixel image.",terminal=False)
            if NewImageBuffer.GetDimensions() != self.LatestImage.GetDimensions():
                self.Log("pilomarimage.CreateTargetZones: Dimension mismatch:",i,
                         "zone:",NewImageBuffer.GetDimensions(),
                         "latest:",self.LatestImage.GetDimensions(),terminal=True)
            NewImageBuffer.SaveFile(filename)

    def CreateTargetZoneBuffer(self,zone):
        """ Given a SearchSequence (See ChooseSearchSequence) create an image buffer for a selected zone.
            returns an opencv compatible image buffer (NOT a pilomarimage object) """
        self.Log("pilomarimage.CreateTargetZoneBuffer: Begin: zone",zone,terminal=False)
        if zone < 0 or zone >= len(self.ZoneList):
            self.Log("pilomarimage.CreateTargetZoneBuffer: zone must be in range",0,"to",len(self.ZoneList) - 1,level='error',terminal=True)
            return None
        sequence_entry = self.ZoneList[zone]
        distance = sequence_entry[0] # Distance to centre of master map (for sorting)
        zone_width = sequence_entry[1] # Search area width.
        zone_height = sequence_entry[2] # Search area height. 
        zone_centre_x = sequence_entry[3] # Search area centre (on master map). 
        zone_centre_y = sequence_entry[4] # Search area centre (on master map).
        drift_offset_x = sequence_entry[5] # Search result x offset.
        drift_offset_y = sequence_entry[6] # Search result y offset.
        x_start = sequence_entry[7] # Starting pixel for this zone on the master target map.
        y_start = sequence_entry[8] # Starting pixel for this zone on the master target map.
        self.Log("pilomarimage.CreateTargetZoneBuffer: Creating",
                 "[",y_start,":",y_start + zone_height,",",
                 "[",x_start,":",x_start + zone_width,",",
                 ":","]",terminal=False)
        image_buffer = self.MasterImage.ImageBuffer[y_start:y_start + zone_height,x_start:x_start + zone_width,...] # Pull JUST the selected zone from the master map.
        self.Log("pilomarimage.CreateTargetZoneBuffer: Created",
                 "(",image_buffer.shape,"pixel image.",terminal=False)
        if image_buffer.shape != self.LatestImage.ImageBuffer.shape:
            self.Log("pilomarimage.CreateTargetZoneBuffer: Dimension mismatch:",i,
                     "zone:",image_buffer.shape,
                     "latest:",self.LatestImage.ImageBuffer.shape,terminal=True)
        return image_buffer

    def ChooseSearchSequence(self):
        """ If LatestImage and MasterImage are different sizes, calculate a search sequence, comparing LatestImage with 
            different 'TargetImage' areas of the MasterImage map. If they are the same size, then only a single TargetImage is returned.
            self.ZoneList is a list of search areas to compare in sequence. 
            The search sequence starts at the centre and moves out.
            The closer a zone is to the centre of the master map the earlier in the search sequence it will appear. """
        self.Log("imagetracker.ChooseSearchSequence: Begin",terminal=False)
        self.ZoneList = []
        master_image_width = self.MasterImage.GetWidth()
        master_image_height = self.MasterImage.GetHeight()
        latest_image_width = self.LatestImage.GetWidth()
        latest_image_height = self.LatestImage.GetHeight()
        master_center_x = int(master_image_width / 2) # Centre of the target map.
        master_center_y = int(master_image_height / 2)
        search_shift = Parameters.TrackingZoneShift # 0.33 # 33% shift between search areas (=67% overlap).
        x_shift = int(latest_image_width * search_shift) # How many pixels do we shift the search area across the map each time?
        y_shift = int(latest_image_height * search_shift) # How many pixels do we shift the search area up the map each time?
        self.Log("imagetracker.ChooseSearchSequence: Master dims:","(",master_image_width,master_image_height,")","Latest dims:","(",latest_image_width,latest_image_height,")",terminal=False)
        self.Log("imagetracker.ChooseSearchSequence: Centre of master map:","(",master_center_x,master_center_y,")",terminal=False)
        self.Log("imagetracker.ChooseSearchSequence: Search shift:",search_shift,"=","(",x_shift,y_shift,")",terminal=False)
        zone_center_x = master_center_x # Centre of search zone starts in centre of target map.
        col_count = 0 # Note how many columns we have calculated.
        while True: # Keep looping until no more columns available in the target map.
            if col_count > 10: break # Safety check, runaway calculations stop at 10 columns.
            zone_center_y = master_center_y # Centre of search zone starts in centre of target map.
            row_count = 0 # Note how many rows we have calculated.
            while True: # Keep looping until no more rows available in the target map.
                if row_count > 10: break # Safety check, runaway calculations stop at 10 rows.
                # Create this as a search zone.
                dist = math.sqrt((zone_center_x - master_center_x) ** 2 + (zone_center_y - master_center_y) ** 2) # How far is the search area from the centre of the target map?
                self.Log("imagetracker.ChooseSearchSequence: Search area centre:","(",zone_center_x,zone_center_y,")","=",dist,terminal=False)
                mirrorlist = [[zone_center_x,zone_center_y]] # Always generate 1st zone.
                zone_filename = '' # Complete this in sorted sequence. FolderHandler.PrepFile('tracking',"ZoneTarget_" + str(i).rjust(3,"0") + "_" + UtcTimeStamp() + ".jpg")
                if row_count > 0: mirrorlist.append([zone_center_x,master_image_height - zone_center_y]) # Create a mirror in the opposite row.
                if col_count > 0: mirrorlist.append([master_image_width - zone_center_x,zone_center_y]) # Create a mirror in the opposite column.
                if row_count > 0 and col_count > 0: mirrorlist.append([master_image_width - zone_center_x,master_image_height - zone_center_y]) # Create a mirror in the opposite corner.
                for zone in mirrorlist:
                    search_entry = [dist, # [0] Distance to centre of target image (for sorting)
                                    int(latest_image_width), # [1] Search area width.
                                    int(latest_image_height), # [2] Search area height. 
                                    zone[0], # [3] Search area centre. 
                                    zone[1], # [4] Search area centre. 
                                    zone[0] - master_center_x, # [5] Search result x offset.
                                    zone[1] - master_center_y, # [6] Search result y offset.
                                    zone[0] - int(latest_image_width / 2), # [7] Start pixel for this zone on the master target map.
                                    zone[1] - int(latest_image_height / 2), # [8] Start pixel for this zone on the master target map.
                                    zone_filename] # [9] Zone filename on disc.
                    self.ZoneList.append(search_entry)
                zone_center_y -= y_shift # Move to next row.
                if zone_center_y - int(latest_image_height / 2) < 0: # Not enough target map left.
                    break
                row_count += 1
            zone_center_x -= x_shift # Move to next column.
            if zone_center_x - int(latest_image_width / 2) < 0: # not enough target map left.
                break
            col_count += 1
        self.ZoneList = sorted(self.ZoneList)
        # Populate filename now that sequence is known.
        for i,ss in enumerate(self.ZoneList):
            ss[9] = FolderHandler.PrepFile('tracking',"ZoneTarget_" + str(i).rjust(3,"0") + "_" + UtcTimeStamp() + ".jpg")
        self.Log("ImageTracker.ChooseSearchSequence:",len(self.ZoneList),"areas:",self.ZoneList,terminal=False)

    def SearchMasterImage(self):
        """ Use astroalign.find_transform to calculate transform between TARGET and LATEST images.
            The target image is generated by the program and represents the star layout we expect to photograph.
            The latest image is the one captured by the camera.
            Find Transform compares the two images and decides if they match.
            It measures any shift between the two images, this can be used to correct for drift in the telescope motion. 
            
            If the TARGET image covers a wider area than the LATEST image then we 
            can try finding a transform my comparing against different regions of the wider target. This has a higher chance of
            finding a solution if the telescope is off by a larger amount than expected, eg at initial startup. """
        self.Log("ImageTracker.SearchMasterImage: Begin",terminal=False)
        self.ChooseSearchSequence() # Map how we would break a large master map into search chunks.
        num_zones = len(self.ZoneList)
        self.Log("ImageTracker.SearchMasterImage:",num_zones,"available.",terminal=False)
        result = False
        self.dx = None
        self.dy = None
        good_calculations = 0 # How many successful drift calculations do we achieve?
        total_true_dx = 0 # Sum of all successful true_dx values.
        total_true_dy = 0 # Sum of all successful true_dy values.
        for i,sequence_entry in enumerate(self.ZoneList): # Go through each search zone of the master map in sequence. 
            self.Log("ImageTracker.SearchMasterImage:",i,sequence_entry,terminal=False)
            distance = sequence_entry[0] # Distance to centre of master map (for sorting)
            zone_width = sequence_entry[1] # Search area width.
            zone_height = sequence_entry[2] # Search area height. 
            zone_centre_x = sequence_entry[3] # Search area centre (on master map). 
            zone_centre_y = sequence_entry[4] # Search area centre (on master map).
            drift_offset_x = sequence_entry[5] # Search result x offset.
            drift_offset_y = sequence_entry[6] # Search result y offset.
            x_start = sequence_entry[7] # Starting x pixel for this zone on the master target map.
            y_start = sequence_entry[8] # Starting y pixel for this zone on the master target map.
            filename = sequence_entry[9] # Filename to generate on disc.
            zone_buffer = self.CreateTargetZoneBuffer(zone=i) # Pull the search zone from the master map.
            self.SetTargetImage(zone_buffer,timestamp=self.LatestTimeStamp,zone=i)
            try: # The transform object is a numpy structure, if the transform calculation fails you can get weird problems that I couldn't always detect cleanly.
                 # So for now ignore any errors at this stage, and assume that no transform could be calculated.
                 # Sometimes it returned a NoneType (numpy array peculiarity), and sometimes it returned an empty array.
                self.Log("ImageTracker.SearchMasterImage:(",i,") TargetImage: type",type(self.TargetImage.ImageBuffer), "shape", self.TargetImage.GetHeight(), "x", self.TargetImage.GetWidth(), "depth", self.TargetImage.GetDepth(), "len[0]", len(self.TargetImage.ImageBuffer[0]), '(2 = (x,y), else image)', "datatype", str(self.TargetImage.ImageBuffer.dtype),terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") LatestImage: type",type(self.LatestImage.ImageBuffer), "shape", self.LatestImage.GetHeight(), "x", self.LatestImage.GetWidth(), "depth", self.LatestImage.GetDepth(), "len[0]", len(self.LatestImage.ImageBuffer[0]), '(2 = (x,y), else image)', "datatype", str(self.LatestImage.ImageBuffer.dtype),terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") Calling astroalign.find_transform()...",terminal=False)
                # If find_transform fails, it reports that the input images are not supported, but this seems to be a general error for ANY failure at all.
                # Check the astroalign source code online and dig deeper... I've seen where _find_sources() fails due to 'sep' package versioning problems.
                transform, (LSL, TSL) = astroalign.find_transform(source=self.LatestImage.ImageBuffer,target=self.TargetImage.ImageBuffer) # In Astroalign terms, this is source=LatestImage, target=TargetImage...
                self.TargetStarMatchList = TSL
                self.LatestStarMatchList = LSL
                self.Log("ImageTracker.SearchMasterImage:(",i,") Received",type(transform),"type in return.",terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") Identified",len(TSL),"suitable stars in target image.",terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") TargetStarMatchList",TSL,terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") Identified",len(LSL),"suitable stars in latest image.",terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") LatestStarMatchList",LSL,".",terminal=False)
                dx = int(-1 * transform.translation[0]) # X-Difference scaled back up to compensate for any image scaling.
                true_dx = dx - drift_offset_x # The real drift needs to include the x offset of the target zone too.
                dy = int(-1 * transform.translation[1]) # Y-Difference scaled back up to compensate for any image scaling.
                true_dy = dy - drift_offset_y # The real drift needs to include the y offset of the target zone too.
                good_calculations += 1 # How many successful drift calculations do we achieve?
                total_true_dx += true_dx # Sum of all successful true_dx values.
                total_true_dy += true_dy # Sum of all successful true_dy values.
                self.Log("ImageTracker.SearchMasterImage:(",i,") Calculated transform: dx=",dx,"dy=",dy,terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") Calculated transform: x_offset=",drift_offset_x,"y_offset=",drift_offset_y,terminal=False)
                self.Log("ImageTracker.SearchMasterImage:(",i,") Calculated transform: true_dx=",true_dx,"true_dy=",true_dy,terminal=False)
                self.SaveTrackingAnalysis(zone=i) # Plot the matches found in this search.
                result = True
            except Exception as e:
                # The most likely explanation is that the lens cap is ON, or there are not enough stars visible in the observation.
                self.Log("ImageTracker.SearchMasterImage:(",i,") Ignored error:",e,terminal=False) # Enable this line if you want to see what error is being ignored!
                self.Log("ImageTracker.SearchMasterImage:(",i,") No transform matrix created. Too few stars, lens cap on, no transformation identified or fault in astroalign and dependencies?",terminal=False)
            if good_calculations >= Parameters.TrackingZoneMatches: # We have enough matches to be confident. No point going further.
                self.Log("ImageTracker.SearchMasterImage:(",i,")",good_calculations,"matches found, not checking further.",terminal=False)
                break

        if good_calculations > 0:
            self.dx = int(round(total_true_dx / good_calculations,0)) # Average all the good matches.
            self.dy = int(round(total_true_dy / good_calculations,0)) 
        else:
            self.dx = self.dy = None
        DriftWindow.Print(NowHMS() + " Matched " + str(good_calculations) + " zones.")
        self.Log("ImageTracker.SearchMasterImage: Averaged drift: x",self.dx,"y",self.dy,"pixels across",good_calculations,"successful alignments.",terminal=False)
            
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
        
    def SaveTrackingAnalysis(self,zone=0):
        """ Combine LATEST, TARGET star lists and show which stars were matched up in FindTransform.
            This is a debug/development feature, but shows how the drift tracking is actually interpreting the images. 
            If latestlist and targetlist are provided by the calling routine those are used for markup.
            Otherwise the existing values from the imagetracker instance are used. """
        self.Log("ImageTracker.SaveTrackingAnalysis: Begin",terminal=False)
        height = SensorInUse.PixelHeight
        width = SensorInUse.PixelWidth

        # If images are different sizes, make sure they are all centered.
        lh = self.LatestImage.GetHeight()
        lw = self.LatestImage.GetWidth()
        th = self.TargetImage.GetHeight()
        tw = self.TargetImage.GetWidth()
        height = max(lh,th)
        width = max(lw,tw)
        Latest_x_offset = 0
        Latest_y_offset = 0
        Target_x_offset = 0
        Target_y_offset = 0
        if lh > th: Target_y_offset = int((lh - th) / 2)
        if th > lh: Latest_y_offset = int((th - lh) / 2)
        if lw > tw: Target_x_offset = int((lw - tw) / 2)
        if tw > lw: Latest_x_offset = int((tw - lw) / 2)

        NewImageBuffer = pilomarimage(name='trackinganalysis',logger=CamLog) # Color full frame blank image.
        NewImageBuffer.New(height,width,imagetype='bgr',datatype=np.uint8)
        NewImageBuffer.FillColor(pilomarimage.BGR('Black'))
        # Draw image frames.
        NewImageBuffer.DrawRectangle((Latest_x_offset,Latest_y_offset),(Latest_x_offset + lw - 1, Latest_y_offset + lh - 1),color=pilomarimage.BGR('Red')) # Border of latest image.
        NewImageBuffer.DrawRectangle((Target_x_offset,Target_y_offset),(Target_x_offset + tw - 1, Target_y_offset + th - 1),color=pilomarimage.BGR('Green')) # Border of target image.
        # Match lists must be the same length.
        if type(self.LatestStarMatchList) != type(None) and \
           type(self.TargetStarMatchList) != type(None) and \
           len(self.LatestStarMatchList) == len(self.TargetStarMatchList):
            # Mark the matched stars first, and an arrow linking the TARGET and LATEST locations.
            for i, lstar in enumerate(self.LatestStarMatchList): 
                tstar = self.TargetStarMatchList[i]
                lx = int(lstar[0]) + Latest_x_offset # Latest star X
                ly = int(lstar[1]) + Latest_y_offset # Latest star Y
                tx = int(tstar[0]) + Target_x_offset # Target star X
                ty = int(tstar[1]) + Target_y_offset # Target star Y
                if self.ValidStarValues(tstar): NewImageBuffer.DrawCircle(tx,ty,15,pilomarimage.BGR('Green'),thickness=2) # Green circle around matched Target stars.
                else: self.Log("imagetracker.SaveTrackingAnalysis: TargetStarMatchList. tstar",tstar,"bad values.",terminal=True)
                if self.ValidStarValues(lstar): NewImageBuffer.DrawCircle(lx,ly,15,pilomarimage.BGR('Red'),thickness=2) # Red circle around matched Latest stars.
                else: self.Log("imagetracker.SaveTrackingAnalysis: LatestStarMatchList. lstar",lstar,"bad values.",terminal=True)
                if self.ValidStarValues(tstar) and self.ValidStarValues(lstar): 
                    NewImageBuffer.DrawLine((lx,ly),(tx,ty),color=pilomarimage.BGR('White'),arrowpixels=20) # Green circle around matched Target stars.
                NewImageBuffer.DrawDumbbell((lx,ly),(tx,ty),20,pilomarimage.BGR('Red'),pilomarimage.BGR('Green'),pilomarimage.BGR('Yellow'),arrow=True)
        else: # Lists don't agree, so don't try to map them.
            self.Log("imagetracker.SaveTrackingAnalysis: Conflicting length of star lists: Target", type(self.TargetStarMatchList), len(self.TargetStarMatchList), "vs Latest", type(self.LatestStarMatchList), len(self.LatestStarMatchList),terminal=False)
            DriftWindow.Print(NowHMS() + " drift analysis image not done.") # Note analysis not done.
        # Superimpose all the TARGET stars. (Stars we expect to see)
        if self.TargetImage.StarList != None:
            for i,star in enumerate(self.TargetImage.StarList): 
                if self.ValidStarValues(star): 
                    starx = int(star[0]) + Target_x_offset
                    stary = int(star[1]) + Target_y_offset
                    magtext = "(" + str(starx) + "," + str(stary) + ")"
                    NewImageBuffer.DrawCircle(starx,stary,5,color=pilomarimage.BGR('Green')) # Green dot for Target stars.
                    self.MarkLocation(NewImageBuffer,starx,stary,pilomarimage.BGR('Green'),"[" + str(i) + "]",magtext) # Mark location, brightness ranking (Brightest -> Dimmest) and magnitude if known.
                else: self.Log("imagetracker.SaveTrackingAnalysis: TargetImage.StarList. star",star,"bad values.",terminal=True)
        # Superimpose all the LATEST stars. (Stars we actually see)
        if self.LatestImage.StarList != None:
            for i,star in enumerate(self.LatestImage.StarList): 
                if self.ValidStarValues(star): 
                    starx = int(star[0]) + Latest_x_offset
                    stary = int(star[1]) + Latest_y_offset
                    NewImageBuffer.DrawCircle(starx,stary,5,color=pilomarimage.BGR('Red')) # Red dot for Latest stars.
                    magtext = "(" + str(starx) + "," + str(stary) + ")"
                    self.MarkLocation(NewImageBuffer,starx,stary,pilomarimage.BGR('Red'),"[" + str(i) + "]",magtext)
                else: self.Log("imagetracker.SaveTrackingAnalysis: LatestImage.StarList. star",star,"bad values.",terminal=True)
        # Add key.
        timestamp = str(NowUTC()).split('.')[0] + " UTC"
        NewImageBuffer.AddText("Tracking Analysis " + timestamp,1300,100,size=2,color=pilomarimage.BGR('White'),bgcolor=pilomarimage.BGR('Black'),thickness=2)
        NewImageBuffer.AddText(str(self.TargetImage.StarCount) + " Target stars",100,100,size=1,color=pilomarimage.BGR('Green'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText(str(self.LatestImage.StarCount) + " Latest stars",100,140,size=1,color=pilomarimage.BGR('Red'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText(str(len(self.LatestStarMatchList)) + " Matches",100,180,size=1,color=pilomarimage.BGR('Yellow'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Match threshold: " + str(Parameters.TrackingMatchThreshold) + " stars.",100,260,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Min correction: " + str(Parameters.MinimumDriftCorrection) + " steps.",100,280,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Tracking interval: " + str(Parameters.TrackingInterval) + " s.",100,300,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        #NewImageBuffer.AddText("Star radius: " + str(Parameters.TrackingStarRadius) + " px.",100,340,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Exposure: " + str(Parameters.TrackingExposureSeconds) + " s.",100,360,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Master time: " + str(DriftTracker.MasterTimeStamp) + " UTC",100,380,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Target time: " + str(DriftTracker.TargetTimeStamp) + " UTC",100,400,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Latest time: " + str(DriftTracker.LatestTimeStamp) + " UTC",100,420,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("T.Min.Mag: "  + str(DriftTracker.TargetMinMagnitude),100,440,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Zone: "  + str(zone),100,460,size=0.5,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'))
        
        # Program ID in bottom right corner.
        xpos = int(width - 10)
        ypos = int(height - 10)
        NewImageBuffer.AddText(ProgramTitle + " " + VERSION + " on " + str(os.uname().nodename),xpos,ypos,color=pilomarimage.BGR('White'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
        # Save the file.
        filename = FolderHandler.PrepFile('tracking',"TrackingAnalysis_" + str(zone).rjust(3,'0') + '_' + UtcTimeStamp() + ".jpg")
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the filename that's been generated.
        DriftWindow.Print(NowHMS() + " Drift analysis image " + str(zone) + " done.") # Note analysis done.
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
        if timestamp is None: timestamp = NowUTC() # Assume current clock time.
        uts = UtcTimeStamp()
        self.LatestTimeStamp = None # Clear the timestamp until we've completed preparing the image. This is accessed concurrently by the CameraHandler.
        self.LatestImage.LoadBuffer(cvimagebuffer) # This makes a copy of the original image rather than just creating a pointer to it.
        self.Log("ImageTracker.SetLatestImage: Loaded image",self.LatestImage.GetDimensions(),terminal=False)
        self.Log("ImageTracker.SetLatestImage: About to measure contrast.",terminal=False)
        contrast_m, contrast_s = self.LatestImage.MeasureContrast() # Calculate contrast for latest image.
        self.Log("ImageTracker.SetLatestImage: Contrast measures",contrast_m, contrast_s,terminal=False)
        self.LatestImage.ChangeType('grayscale') # Always convert to grayscale at this point.
        if Parameters.LatestTrackingFilter == None: # No filter script is selected for latest tracking images.
            self.Log("ImageTracker.SetLatestImage: No LatestTrackingFilter defined. Not refining the image.",terminal=False)
            DevWindow.Print(NowHMS() + " SetLatestImage: No LatestTrackingFilter")
        else: # A filter script is selected for latest tracking images, process that instead of the old hardcoded filter code.
            if self.LatestImage.RunFilterScript(scriptname=Parameters.LatestTrackingFilter,window=DevWindow): # If the script succeeds or fails. It can output to DevWindow.
                self.Log("ImageTracker.SetLatestImage: LatestTrackingFilter(",Parameters.LatestTrackingFilter,") success.",terminal=False)
            else: # Failed.
                self.Log("ImageTracker.SetLatestImage: LatestTrackingFilter(",Parameters.LatestTrackingFilter,") failed.",level='warning')
        self.Log("ImageTracker.SetLatestImage: Prepared image:","type", str(type(self.LatestImage.ImageBuffer)),"shape", self.LatestImage.GetHeight(), "x", self.LatestImage.GetWidth(),"depth", self.LatestImage.GetDepth(),terminal=False)
        self.LatestTimeStamp = timestamp # The image is now prepared, update the timestamp.
        self.LatestStarMatchList = [] # Clear the list of matched stars, this is set later when the find_transform call is made.
        self.Log("ImageTracker.SetLatestImage: Registered latest image",terminal=False)
        _,_ = self.LatestImage.CountStars()
        self.Log("ImageTracker.SetLatestImage: Counted",self.LatestImage.StarCount,"stars.",terminal=False)
        # Save target image for reference.
        filename = FolderHandler.PrepFile('tracking','LatestTrackingImage_' + uts + '.jpg')
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Note the file that's being created.
        self.LatestImage.SaveFile(filename)

# ------------------------------------------------------------------------------------------------------

DriftTracker = imagetracker(logger=CamLog) # Create an instance of the image tracker to measure drift between subsequent images. 

# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Initialize Skyfield 
# ///////////////////////////////////////////////////////////////////////////////////

# Load dictionary listing star NAMES, CONSTELLATION and Hipparcos catalog number. 
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
    MainLog.Log("hipex_load_dataframe: Estimating",len(df),"star colors from",len(BVList),"unique B-V values...",terminal=True)
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
            #print(textcolor.cursorup() + NowHMS(),textcolor.white(str(round(prgt.GetPercent(),1))),"%. Record",i,"of",total,"( HIP" + str(hip),"). ETA",str(prgt.GetETA()).split('.')[0],"UTC",textcolor.clearlineforward())
            print(prgt.MakeProgressBar(color=True,text='',length=20,show_start=True,show_eta=True))
    return df

# If Hipparcos data already cached, use that, otherwise load and prepare the data cache now.
if ReloadData == False and os.path.exists(HipparcosCacheFile): # A cache of the hipparcos data already exists, use it.
    MainLog.Log("Hipparcos data cache exists, using that.",terminal=False)
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
        PleaseRestart() # Show banner requesting a restart.
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
MainLog.Log('Loading constellation patterns and names...',terminal=True)
ConstellationLinks = [] # Start new empty list of constellation patterns. [ [from hip num, to hip num, constellation], [from hip num, to hip num, constellation], ... ]
ConstellationNames = {} # Used to turn abbreviations into full names. {'aql': 'Aquila', 'and': 'Andromeda', 'scl': 'Sculptor', ...
for cn in load_constellation_names(): # Make it a lookup dictionary, but keys in lower case for standardisation.
    ConstellationNames[cn[0].lower()] = cn[1]
MainLog.Log('Recognised constellation codes:',ConstellationNames,terminal=False)

def ConstellationName(code):
    """ Convert a constellation code into a name. """
    code = code.lower()
    return ConstellationNames.get(code,"")

ConstellationStarList = [] # List of HIP numbers for stars in constellation patterns. Used to find MarkupPreview stars which can be joined up.
for cons in StellariumConstellations: # Process each constellation in turn.
    # cons contains something like 'And',[(star1, star2), (star3, star4),...]
    c_code = cons[0] # Constellation code ('And')
    # Expand constellation code into a name if possible.
    c_name = ConstellationName(c_code)
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

def PerformanceTrim():
    """ Return TRUE if the O/S and hardware will be under strain. 
        In these cases the software can reduce the workload. """
    result = False
    if Parameters.TuneOn32Bit and Hardware.os_bits < 64:
        result = True
    return result
    
def GenerateNGCDataframe(source_url):
    """ Use the Python dictionary to generate a Pandas dataframe.
        Having the data in a dataframe can speed up selection and
        processing of large lists, and moves closer to having common
        routines for handling all the different object lists. """
    MainLog.Log('GenerateNGCDataframe(',source_url,')...',terminal=False)
    NGCDict = DictionaryLoader(source_url)
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

    if PerformanceTrim(): # On 32bit systems, improve performance by removing 'pgc' entries from the NGC galaxy catalog. 
        deleted = 0
        MainLog.Log("GenerateNGCDataframe: PerformanceTrim: Removing pgc entries for performance.",terminal=False)
        for k in list(NGCDict.keys()): # Check each entry's key. Remove 'pgc' ones.
            if k.startswith('pgc'): 
                del NGCDict[k]
                deleted += 1
        MainLog.Log("GenerateNGCDataframe: PerformanceTrim: Removed",deleted,"entries.",len(NGCDict),"remain.",terminal=False)
        
    # Store some repeated calculations in the dictionary to improve performance later on.
    count = 0
    for NGCEntry,NGCValues in NGCDict.items():
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
        count += 1

    # Convert the dictionary to a pandas dataframe.
    dframe = pandas.DataFrame.from_dict(NGCDict) # Convert from dictionary to pandas dataframe (but the rows/columns are transposed).
    dframe = dframe.transpose() # Swap rows/columns the right way round.

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
    dframe.to_pickle(NGCCacheFile) # Save the processed file as a cache to speed things up next time.

    return dframe

# Load NGC list.
MainLog.Log('Loading New General Catalog (NGC) entries from', NGCUrl, '...',terminal=True)
if ReloadData == False and os.path.exists(NGCCacheFile): # A cache of the NGC data already exists, use it.
    MainLog.Log("NGC data cache exists, using that.",terminal=False)
    NGC_DF = pandas.read_pickle(NGCCacheFile)
else:
    MainLog.Log("No NGC data cache, creating one now.",terminal=True)
    NGC_DF = GenerateNGCDataframe(source_url=NGCUrl)

def TrimDimNGC(dframe):
    # Eliminate any entries which will never be selected.
    MainLog.Log("TrimDimNGC: Before removing dim objects.",len(dframe),"records.",terminal=False)
    # Filter out dim NGC objects, but make the limit dimmer than the star selection because they are interesting objects.
    mag_cutoff = Parameters.TargetMinMagnitude * 1.5
    boolseries = dframe['magnitude'].between(-100,mag_cutoff, inclusive='both') # Create filter for items within Magnitude range.
    dframe = dframe[boolseries] # Apply filter.
    MainLog.Log("TrimDimNGC: After removing dim objects.",len(dframe),"records. (Magnitude",mag_cutoff,")",terminal=False)
    return dframe

# Remove dim objects from NGC dataframe.
NGC_DF = TrimDimNGC(dframe=NGC_DF)
MainLog.Log("NGC dataframe contains: Rows",len(NGC_DF),"Columns",NGC_DF.columns,terminal=False)
NGC_Namelist = NGC_DF['name'].tolist() # List of object names for target chooser.

# Load Meteor shower list.
MainLog.Log('Loading meteor shower list from', MeteorDictUrl, '...',terminal=True)
Meteor_dictionary = DictionaryLoader(MeteorDictUrl)
MainLog.Log('Loaded',len(Meteor_dictionary),'meteor shower entries.',terminal=False)

# Load comet data.
# Comet data comes from the Minor Planet Center. 
# Format is :-
#     CJ95O010  1997 03 30.7270  0.890333  0.994981  130.2195  282.3128   89.4615  20240223  -2.0  4.0  C/1995 O1 (Hale-Bopp)                                    MPEC 2022-S20
# 012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012
#           1         2         3         4         5         6         7         8         9        10        11        12        13        14        15        16        17        18
#                                                                                  YYYYMMDD stamp of the data.
MainLog.Log('Loading comet list from',mpc.COMET_URL,'...',terminal=True)
with load.open(mpc.COMET_URL,reload=ReloadData) as f: # Don't keep reloading it if it is already on disc.
    comets = mpc.load_comets_dataframe(f) # Comet data loaded as a Pandas dataframe.
MainLog.Log(len(comets), 'comets loaded.',terminal=False)
MainLog.Log("Comet dataframe contents:",comets.columns.tolist(),terminal=False)
# Keep only the most recent comet trajectory and index by designation for fast lookup.
comets = (comets.sort_values('reference')
          .groupby('designation', as_index=False).last()
          .set_index('designation', drop=False))
# Example lookups.
#row = comets.loc['1P/Halley']
#row = comets.loc['C/1995 O1 (Hale-Bopp)']

CometList = comets['designation'].tolist() # Convert comet designations column into a list for searching later on.

def CometDataAge():
    """ Report the age of the comet trajectory data from the Minor Planet Center. 
        warn = True : Will issue warning here. """
    filename = ProjectRoot + '/data/CometEls.txt' 
    filedays = None
    if os.path.exists(filename): # The cache data exists, check its age.
        with open(filename,'r') as f:
            line = f.readline() # Take 1st line as an example.
            filedt = MctlStringToDatetime(line[81:89] + "000000") # YYYYMMDD portion of the record.
            filedays = round((NowUTC() - filedt).total_seconds() / (24 * 60 * 60),0)
            MainLog.Log("Comet data cache is from",filedt,",",filedays,"days old.",terminal=False)
            if filedays > 60: # After 2 months, consider refreshing the file.
                MainLog.Log("Comet data cache is",int(filedays),"days old. Consider refreshing it to maintain accuracy.",level='warning',terminal=True)
    return filedays

CometDataAge() # If the data cache exists, how old is the content?

# ----------------------------------------------------------------------------------------------------------

if PerformanceTrim(): # Check for any performance issues in the setup.
    if Parameters.CameraEnabled == False: # Software will generate artificial images.
        if Parameters.FakePollution: # FakePollution performs a Gaussian blur which takes a lot of memory on small machines.
            MainLog.Log("PerformanceTrim: Recommend disabling FakePollution parameter.",level='warning',terminal=True)
        if Parameters.FakeField: # FakeField is not needed on small machines.
            MainLog.Log("PerformanceTrim: Recommend disabling FakeField parameter.",level='warning',terminal=True)
        if Parameters.FakeAurora: # FakeAurora is not needed on small machines.
            MainLog.Log("PerformanceTrim: Recommend disabling FakeAurora parameter.",level='warning',terminal=True)
    if Parameters.UseTracking:
        if Parameters.TrackingInterval < 900: # Tracking should not be performed too often on slow machines. 900 seconds is good minimum.
            MainLog.Log("PerformanceTrim: Recommend increasing TrackingInterval parameter. Perform drift tracking less often, it will be slow.",level='warning',terminal=True)
        if Parameters.TrackingMapSpan > 2: # Keep the tracking master map small to speed up the calculation.
            MainLog.Log("PerformanceTrim: Recommend reducing TrackingMapSpan parameters. A smaller master map will improve performance.",level='warning',terminal=True)
    if Parameters.GeneratePreview:
        if Parameters.MarkupInterval < 900: # Preview images should not be generated too often on slow machines. 900 seconds is a good minimum.
            MainLog.Log("PerformanceTrim: Recommend increasing MarkupInterval parameter. Generate Preview images less often, they can be slow.",level='warning',terminal=True)
            
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

        Using some online AI coding tools has sometimes been useful to solve problems when getting Pandas to behave as expected.
        The Pandas code here is unlikely to be perfect - I'm not an expert in it, it works, but can certainly be improved.

        Finding a specific HIP star row using     MyRow = self._df.loc[hip_num] 
        Finding a specific row using index        MyRow = self._df.iloc[row_num] 
        Finding a specific cell using             MyCell = self._df.loc[hip_num,'magnitude'] 
                                                  MyCell = self._df.iloc[row_num]['magnitude']
                                                  MyCell = self._df.iat[row_num,col_num]
        Find col_num for a specific column using localstars.ColumnIndex('magnitude')
        - This returns None if the column name is not known.        """
    
    def __init__(self,ra,dec,radius,magnitude,maxstars=1000,logger=None):
        self.SetLogger(logger) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
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
        # Clip to maxstars.
        self.Log("localstars.Update(): Clipping dataframe.",terminal=False)
        self._df = self._df[:self.maxstars]
        self.update = NowUTC() # Update timestamp.
        self.Log("localstars.Update(): Selected",len(self._df.index),"rows.",terminal=False)
        self.Log("localstars.Update(): Setting index.",terminal=False)
        self._df = self._df.set_index('hip',drop=False) # Make 'hip' the index of the DataFrame, but keep the 'hip' column for reference.
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
LocalStars = localstars(ra=0.0,dec=0.0,radius=inclusionradius,magnitude=Parameters.LocalStarsMagnitude,maxstars=10000,logger=CamLog) # Narrow field of view, list of all visible stars.
MainLog.Log("LocalStars df columns:",LocalStars.MasterDf.columns.values.tolist(),terminal=False)
MainLog.Log("LocalStars df values:",LocalStars.MasterDf.loc[0].values.tolist(),terminal=False)
ConstellationStars = localstars(ra=0.0,dec=0.0,radius=inclusionradius + 5,magnitude=Parameters.ConstellationStarsMagnitude,maxstars=10000,logger=CamLog) # Wider field of view, but filtered to just key constellation stars.
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
    print(textcolor.yellow("Reload complete."))
    PleaseRestart() # Show banner requesting a restart.
    exit() # Quit the program. This is a workaround to a problem where the Python 'input' statements fail after the hipex_load_dataframe() function has executed for a long time.

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
        self.SetLogger(MainLog) # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.Handle = handle # Skyfield object for target. This is usually provided directly by the calling routine, but in the case of 'comets' it is calculated here during initialisation.
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
        self.SetHome() # Initialize the Skyfield object representing the Observer's location on the surface of the Earth.
        self.CometPandasRow = cometpandasrow # Comets don't have a skyfield object in 'Handle', we calculate the position differently, so store their pandas row here. 
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
        self.ScheduledStart = None # Holds the UTC timestamp when the observation should start (if one is set).
        self.ScheduledEnd = None # Holds the UTC timestamp when the observation should end (if one is set).
        self.QuickStarCache = {} # Holds surrounding objects for rapid calculations when generating images and maps.
        self.TrackingMapSpan = Parameters.TrackingMapSpan # New targets can start with a large master map for the drift tracking function. It gets smaller as the telescope zeros in on the target.

    def TwilightLevel(self,time=None):
        """ Return the twilight level for the current location.
            NOTE: The target needs to be the sun!
            If 'time' parameter given, it's the lightlevel at that time.
            If 'time' is None, then the current time is used. """
        az, alt = self.AzAltDegrees(time=time)
        if alt > 0: result = "daytime"
        elif alt >= -6: result = "civil twilight"
        elif alt >= -12: result = "nautical twilight"
        elif alt >= -18: result = "astronomical twilight"
        else: result = "nighttime"
        return result
    
    def Datetime2Ts(self,dt): # Referenced by external dependencies.
        """ Convert datetime into TS (skyfield) timestamp. """
        t = Datetime2Ts(dt) # Convert to skyfield time type.
        return t

    def CurrentMagnitude(self,time=None):
        """ Calculate the current magnitude (or for a specific time) if possible. """
        if time is None: time = self.CurrentTime()
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
            self.Log('target.NextRiseSetObject(',self.Name,'): zipped',ti, yi, terminal=False)
            tidt = ti.utc_datetime()
            if tidt < NowUTC(): continue # In the past, ignore it.
            if yi and risetime is None: # First future rise time.
                risetime = tidt
            elif settime is None: # First future set time.
                settime = tidt
        return risetime, settime
    
    def NextRiseSetSatellite(self):
        """ Return next horizon event and time for satellites. """
        self.Log("target.NextRiseSetSatellite(",self.Name,")",terminal=False)
        if not hasattr(self.Handle,'find_events'): # This object doesn't support satellite pass calculations.
            self.Log("Cannot calculate next Rise Set times for this type of target(",self.Name,self.ObjectType,")",terminal=True)
            self.Log("target.NextRiseSetSatellite: find_events method not in this target type.",terminal=True)
            return
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
            if eventtype == 2 and settime is None and risetime != None: settime = eventtime.utc_datetime()
            if eventtype == 0 and risetime is None: risetime = eventtime.utc_datetime()
            if risetime != None and settime != None: break # We have our earliest acceptable set of values.
        self.Log("target.NextRiseSetSatellite: Rise",risetime,"set",settime,terminal=False)
        return risetime, settime

    def CurrentRiseSetObject(self):
        """ Return current horizon event and time for distant objects. (Moon and beyond)
            When DID the object rise?
            When WILL the object set? """
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
            self.Log('target.CurrentRiseSetObject(',self.Name,'): zipped',ti, yi, terminal=False)
            tidt = ti.utc_datetime()
            if yi: # We have a RISE TIME.
                if tidt < NowUTC(): risetime = tidt # Latest RISE TIME in the past.
            else: # We have a SET TIME.
                if tidt > NowUTC() and settime is None: settime = tidt # First SET TIME in the future.
        return risetime, settime
    
    def CurrentRiseSetSatellite(self):
        """ Return current horizon event and time for satellites. 
            When DID the satellite rise?
            When WILL the satellite set? """
        self.Log("target.CurrentRiseSetSatellite(",self.Name,")",terminal=False)
        if not hasattr(self.Handle,'find_events'): # This object doesn't support satellite pass calculations.
            self.Log("Cannot calculate next Rise Set times for this type of target(",self.Name,self.ObjectType,")",terminal=True)
            self.Log("target.CurrentRiseSetSatellite: find_events method not in this target type.",terminal=True)
            return
        risetime = settime = None
        t_from = self.CurrentTime() # Start now.
        t_to = TsDelta(t_from,dd=1) # Stop in 24hours time.
        self.Log("target.CurrentRiseSetSatellite: t_from",str(t_from),"t_to",str(t_to),terminal=False)
        times, events = self.Handle.find_events(self.HomeSiteTopos, t_from, t_to, Parameters.MinSatelliteAltitude) # What events occur above horizon in next 24 hours?
        self.Log("target.CurrentRiseSetSatellite: times",times,"events",events,terminal=False)
        telist = zip(times,events)
        for te in telist:
            self.Log("target.CurrentRiseSetSatellite: Entry:",te,terminal=False)
            eventtime = te[0]
            eventtype = te[1] # 0=Rise, 1=Culminate, 2=Set
            if eventtype == 2 and settime is None and settime > NowUTC(): settime = eventtime.utc_datetime()
            if eventtype == 0 and risetime < NowUTC(): risetime = eventtime.utc_datetime()
            if risetime != None and settime != None: break # We have our earliest acceptable set of values.
        self.Log("target.CurrentRiseSetSatellite: Rise",risetime,"set",settime,terminal=False)
        return risetime, settime

    def SatellitePasses(self,window=24):
        """ Print table of satellite pass information for next xx hours. """
        self.Log("target.SatellitePasses: NOT YET IMPLEMENTED.",terminal=False)
        t_from = self.CurrentTime() # Start now.
        t_to = TsDelta(t_from,dd=1) # Stop in 24hours time.
        self.Log("target.SatellitePasses: t_from",str(t_from),"t_to",str(t_to),terminal=False)
        if not hasattr(self.Handle,'find_events'): # This object doesn't support satellite pass calculations.
            self.Log("Cannot calculate next pass times for this type of target(",self.Name,")",terminal=True)
            self.Log("target.SatellitePasses: find_events method not in this target type.",terminal=False)
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
            if eventtime is None or eventtime > settime:
                eventtime = settime
                eventtype = 'set'
        self.Log("target.NextRiseSet(",self.Name,"): rise",risetime,"set",settime,"eventtime",eventtime,"eventtype",eventtype,terminal=False)
        return eventtype, eventtime

    def NextRiseSetHHMM(self,window=None):
        """ Returns next RISE or SET time as HH:MM string. 
            window says how many hours into the future is acceptable. 
            Outside this window it returns '--:--'
            Respects LocalTZ & DisplayTZ """
        eventtype, eventtime = self.NextRiseSet()
        result = ''
        if eventtype == 'rise':
            result = str(UTCtoDisplay(eventtime))[11:16] + Symbol['up']
        elif eventtype == 'set':
            result = str(UTCtoDisplay(eventtime))[11:16] + Symbol['down']
        if window != None and eventtime != None:
            cutoff = NowUTC() + timedelta(hours=window)
            if eventtime > cutoff: # Outside window.
                result = '--:--'
        self.Log("target.NextRiseSetHHMM(",self.Name,"): eventtime",eventtime,"(UTC)","eventtype",eventtype,"result",result,terminal=False)
        return result

    def RiseSet(self):
        """ Return next rise and set times for the object. 
            - This is the NEXT visibility, when WILL it rise? when WILL it set?
            Uses Skyfield's almanac functions for this. """
        risetime = None # No RISE time until identified.
        settime = None # No SET time until identified.
        if self.IsFixedPoint(): # No risetime/settime time for fixed point. 
            pass
        elif self.ObjectType == 'earth satellite':
            risetime, settime = self.NextRiseSetSatellite()
        else: # Moving target, so check for rise/set times.
            risetime, settime = self.NextRiseSetObject()
        self.Log("target.RiseSet(",self.Name,"): rise",risetime,"set",settime,"UTC",terminal=False)
        return risetime, settime

    def CurrentRiseSet(self):
        """ Return next rise and set times for the object. 
            - This is the CURRENT visibility, when DID it rise? when WILL it set?
            Uses Skyfield's almanac functions for this. """
        risetime = None # No RISE time until identified.
        settime = None # No SET time until identified.
        if self.IsFixedPoint(): # No risetime/settime time for fixed point. 
            pass
        elif self.ObjectType == 'earth satellite':
            risetime, settime = self.CurrentRiseSetSatellite()
        else: # Moving target, so check for rise/set times.
            risetime, settime = self.CurrentRiseSetObject()
        self.Log("target.CurrentRiseSet(",self.Name,"): rise",risetime,"set",settime,terminal=False)
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
        lookingat = self.HomeSite.at(t).from_altaz(alt_degrees=alt, az_degrees=az)
        ra, dec, _ = lookingat.radec()
        if asdegrees: # Convert to pure degree values.
            ra = ra._degrees
            dec = dec.degrees
        return ra,dec

    def RaDecToAltAz(self,ra,dec,time=None,asdegrees=True):
        """ Given any ra,dec coordinates (in degrees) return alt-az values.
            asdegrees TRUE = ra is a float degree value.
            asdegrees FALSE = ra is a list of H,M,S values. """
        if time is None: time = self.CurrentTime() # Current time.
        if asdegrees: # Receiving input parameters as degree values. 
            rah,ram,ras = AngleToHMS(ra)
        else: # Receiving input as list.
            rah = ra[0]
            ram = ra[1]
            ras = ra[2]
        TempStar = Star(ra_hours=(rah,ram,ras), dec=Angle(degrees=dec)) # Create a Skyfield target object.
        TempStarAlt, TempStarAz, TempStardistance = self.HomeSite.at(time).observe(TempStar).apparent().altaz()
        return TempStarAlt.degrees,TempStarAz.degrees

    def ChooseRotationPoint(self,offsetdeg=2.0):
        """ Setup the rotation reference point that we measure field rotation against.
            This is a point in the sky offset from the main target.
            We measure the relative position of this point to establish field rotation metrics. 
            offsetdeg is the declination offset (in degrees) from the primary target's location. """
        # Calculate field rotation for target.
        CentreRa, CentreDec = self.RaDecHours() # Calculations for target from observer's location. 
        CentreDec = CentreDec.degrees # Convert to pure float degree value.
        # Offset by offsetdeg declination from the target. We'll measure how this point moves around the target to calculate the rotation rate.
        # Offset BELOW if we're in the northern hemisphere, ABOVE if we're in the southern hemisphere.
        if Parameters._HomeLatVal > 0: OffsetDec = CentreDec - offsetdeg
        else: OffsetDec = CentreDec + offsetdeg
        # Define a fixed radec point offset from the target, we use this to measure field rotation.
        self.RotationPoint = Star(ra_hours=(CentreRa.hms()[0],CentreRa.hms()[1],CentreRa.hms()[2]), dec=Angle(degrees=OffsetDec)) # Create an offset point relative to the main target.
        return True

    def RotationPointAltAzDegrees(self,time=None):
        if time is None: time = self.CurrentTime() # Current time.
        if self.RotationPoint is None: self.ChooseRotationPoint() # Choose a rotation point if not already done.
        TempStarAlt, TempStarAz, TempStardistance = self.HomeSite.at(time).observe(self.RotationPoint).apparent().altaz() # Work out where the rotation point is.
        return TempStarAlt.degrees,TempStarAz.degrees

    def PlotRotationPoint(self,time=None):
        """ Return the image x,y co-ordinates of the field rotation reference point. """
        if time is None: time = self.CurrentTime() # Current time.
        RotationAltDeg, RotationAzDeg = self.RotationPointAltAzDegrees(time=time) # Altitude and Azimuth in degrees of the field rotation reference point.
        az_degree, alt_degree = self.AzAltDegrees(time=time) # Get current position of the target.
        PlotStarAlt, PlotStarAz = RelativeAltAz(RotationAltDeg,RotationAzDeg,alt_degree,az_degree) # Location of rotation reference point relative to the observation target.
        TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,SensorInUse.PixelHeight,SensorInUse.PixelWidth)
        return TempStarX,TempStarY
        
    def RotationPointBearing(self,time=None):
        """ Calculate the bearing of the field rotation reference point relative to the target. """
        # AltAz mounts suffer from a characteristic rotation of the field of view as the telescope tracks an object.
        # - This field rotation can cause star trails to appear in stars on the outer edges of the image if the exposure is too long.
        # The calculated point is xx degrees of declination above/below the target object.
        if time is None: time = self.CurrentTime() # Current time.
        RotationAltDeg, RotationAzDeg = self.RotationPointAltAzDegrees(time=time) # Altitude and Azimuth in degrees of the field rotation reference point.
        az_degree, alt_degree = self.AzAltDegrees(time=time) # Get current position of the target.
        PlotStarAlt, PlotStarAz = RelativeAltAz(RotationAltDeg,RotationAzDeg,alt_degree,az_degree) # Location of rotation reference point relative to the observation target.
        TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,SensorInUse.PixelHeight,SensorInUse.PixelWidth)
        xpos = round(SensorInUse.PixelWidth/2)
        ypos = round(SensorInUse.PixelHeight/2)
        # Calculate rotation angle.
        opposite = TempStarX - xpos
        adjacent = TempStarY - ypos
        rotation = math.degrees(math.atan2(opposite,adjacent))
        return rotation

    def RotationPixels(self,angle=None,radius=None):
        """ Convert a field rotation into worst-case pixel count in the corner of the image. 
            radius parameter is the number of pixels radius from the centre of the image. If None, sensor size is used.
            span is the timespan to calculate rotation over. """
        # Convert the field rotation angle into the number of pixels in the most extreme corner of the image. That will show the maximum smearing due to rotation.
        # If no angle, calculate one based upon current selected exposure.
        if angle is None:
            angle = self.RotationArc(span=CameraInUse.ExposureSeconds)
        # Radius of worst case rotation is the distance from the centre of the image to the corner.
        if radius is None:
            radius = math.sqrt(((SensorInUse.PixelWidth / 2) ** 2) + ((SensorInUse.PixelHeight / 2) ** 2))
        self.Log('target.RotationPixels: radius',radius,terminal=False)
        circumference = radius * 2 * math.pi # How many pixels in total for the circumference of the circle defined by radius?
        arclength = circumference * angle / 360 # How many pixels in the arc defined by radius and angle.
        return arclength

    def RotationArc(self,span=3600,time=None):
        """ Return field rotation rate.
            This calculates the rate over an hour, but returns a result scaled to the requested time span.
            Calculation is centred upon the current time unless time parameter has a value. """
        if time is None: time = self.CurrentTime()
        calcperiod = 3600 # Calculate the rotation over an hour and then scale to the requested period. This reduces some inherent precision issues with small periods.
        t1 = TsDelta(time,s=-1 * round(calcperiod / 2)) # Start rotation at 30minutes ago.
        t2 = TsDelta(t1,s=calcperiod) # End rotation 30minutes ahead.
        #self.Log('target.RotationArc: Times',t1.utc_strftime(),t2.utc_strftime(),terminal=False)
        a1 = self.RotationPointBearing(t1) # Rotation angle at start.
        a2 = self.RotationPointBearing(t2) # Rotation angle at end.
        rate = a2 - a1 # Delta of rotation angle.
        #self.Log('target.RotationArc: gross rate=',rate,DegreeSymbol,terminal=False)
        rate = rate * span / calcperiod
        return rate # Field rotates at 'rate' degrees per 'span' seconds.

    def PlanetAzAltDegrees(self,name='moon',time=None):
        """ Returns the current altitude and azimuth of any planetary object from Skyfield calculations. 
            - Default is the Moon.
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used. """
        if self.HomeSite is None:
            raise Exception ("Target.AzAltDegrees:",name," HomeSite is not defined. Set Target.HomeSite before calling this function.")
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

    def SetHome(self):
        """ Initialize the Skyfield home references. """
        self.HomeSiteTopos = Topos(Parameters.HomeLat,Parameters.HomeLon)
        self.HomeSite = planets['earth'] + self.HomeSiteTopos # Define HomeSite as a point on earth. Could be from GPS too.

    def AzAltDegrees(self,time=None,updatespeed=False):
        """ Returns the current altitude and azimuth of the target from Skyfield calculations. 
            An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
            updatespeed = True The angular velocity of the target is updated too. """
        if self.HomeSite is None:
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
                if alt < i.MinObservationAngle or alt > i.MaxAngle: result = False # *!*
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
        if self.HomeSite is None:
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
        if self.HomeSite is None:
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
        if time is None: time = self.CurrentTime()
        result = almanac.moon_phase(planets, time)
        return result.degrees

    def MoonFull(self,time=None):
        """ Return the % of full moon.
            Used to indicate light pollution from the moon. """
        moonphase = self.LunarPhase(time=time)
        # Convert moonphase into an approximate % full. We're interested in light pollution levels.
        if moonphase > 180: 
            moonphase = 360 - moonphase
        moonphase = 100 * moonphase / 180
        return moonphase

    def MoonWaxing(self):
        """ Return TRUE if moon is Waxing. 
            Return FALSE if moon is Waning. """
        if self.LunarPhase() <= 180: result = True
        else: result = False
        return result

    def ForecastPath(self,time=None,days=30,stephours=24,fov=None):
        """ Calculate the path that the target will take through the sky for the next xxx days. 
            Returns list of timestamps, ra and dec co-ordinates (both as degree values).
            time = start timestamp for forecast.
            days = number of days to forecast.
            stephours = number of hours between each forecast position. 
            fov = field of view (degrees). Forecast stops when path leaves FOV.
                  If None, the camera values are used as a basis. """
        Points = [] # List of points on the path.
        if time != None: temp_ts = time
        else: temp_ts = self.CurrentTime()
        temp_ts = TsDelta(self.CurrentTime(),s=0) # This truncates the fractions of a second from the timestamp, makes display cleaner.
        cutoff_ts = TsDelta(temp_ts,dd=days) # When does the forecast stop?
        if fov is None: # Default the field of view.
            # Use 80% of the narrowest field-of-view of the configured lens.
            fov = min(CameraInUse.Lens.FovHorizontal,CameraInUse.Lens.FovHorizontal) * 0.8
        min_ra = max_ra = None
        min_dec = max_dec = None
        while temp_ts.utc_datetime() <= cutoff_ts.utc_datetime(): # Run forwards xxx days.
            ra, dec = self.RaDecDegrees(time=temp_ts)
            # Check the span of motion. It cannot exceed the image field of view.
            if min_ra is None or min_ra > ra: min_ra = ra
            if max_ra is None or max_ra < ra: max_ra = ra
            if min_dec is None or min_dec > dec: min_dec = dec
            if max_dec is None or max_dec < dec: max_dec = dec
            if abs(max_ra - min_ra) > fov or abs(max_dec - min_dec) > fov: # Motion exceeds the field of view.
                break # Quit the loop.
            Points.append((temp_ts, ra, dec))
            temp_ts = TsDelta(temp_ts,h=stephours) # Roll forward xxx hours for the next position.
        print ('ForecastPath',self.Name,':')
        print('Date'.rjust(10),'RA'.rjust(14),'Dec'.rjust(10),'Min RA'.rjust(14),'Max RA'.rjust(14),'Min Dec'.rjust(10),'Max Dec'.rjust(10),sep='\t')
        iah, iam, ias = AngleToHMS(min_ra) # Convert degrees to H,M,S units.
        aah, aam, aas = AngleToHMS(max_ra)
        for tt,ra,dec in Points:
            rah, ram, ras = AngleToHMS(ra) # Convert degrees to H,M,S units.
            self.Log(str(tt.utc_datetime()).split(' ')[0],DisplayHMS(rah,ram,ras,14),DisplayDegree(dec,9) + DegreeSymbol,DisplayHMS(iah,iam,ias,14),DisplayHMS(aah,aam,aas,14),DisplayDegree(min_dec,9) + DegreeSymbol,DisplayDegree(max_dec,9) + DegreeSymbol,sep='\t',terminal=False)
        return Points
    
    def ForecastRange(self,time=None,days=30):
        """ Forecast the path of the target for xxx days and return the min/max ra/dec of the target during that period. """
        Points = self.ForecastPath(time=time,days=days)
        min_ra = max_ra = Points[0][1]
        min_dec = max_dec = Points[0][2]
        for tt,ra,dec in Points:
            min_ra = min(min_ra,ra)
            iah, iam, ias = AngleToHMS(min_ra)
            max_ra = max(max_ra,ra)
            aah, aam, aas = AngleToHMS(max_ra)
            min_dec = min(min_dec,dec)
            max_dec = max(max_dec,dec)
        return min_ra, min_dec, max_ra, max_dec

    def ForecastCentre(self,time=None,days=30):
        """ Forecast the path of the target for xxx days and return the centre of it's motion during that period. 
            Returned as ra/dec (both as degree values) """
        min_ra, min_dec, max_ra, max_dec = self.ForecastRange(time=time,days=days)
        return ((min_ra + max_ra) / 2), ((min_dec + max_dec) / 2)

    def ApparentCometMagnitudeGK(self):
        """ Calculate comet apparent magnitude using GK model. 
        
            Code based upon example by Bernmeister https://github.com/skyfielders/python-skyfield/issues/416 

             def getApparentMagnitude_gk( g_absoluteMagnitude, k_luminosityIndex, bodyEarthDistanceAU, bodySunDistanceAU ):
                 return g_absoluteMagnitude + \
                        5 * math.log10( bodyEarthDistanceAU ) + \
                        2.5 * k_luminosityIndex * math.log10( bodySunDistanceAU ) 
                        
            """
                        
        # Field names for MPC comet data were corrected in Skyfield after Nov.2020, _h and _g column names have been corrected to _g, _k
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
        if prechosen is None:
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
        for key,value in Messier_dictionary.items(): # Python3: Check every item in the Messier catalog.
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
        if sizemin is None or width > sizemin: sizemin = width
    if height != None: 
        if sizemin is None or height > sizemin: sizemin = height
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
    MainLog.Log("ChooseMeteor:Begin, prechosen:",prechosen,terminal=False)
    Result = ""
    desc = None
    const = None
    magnitude= 0.0
    obstarget = None
    MainLog.Log("ChooseMeteor:Create MeteorChooser",terminal=False)
    MeteorChooser = listchooser(Meteor_namelist)
    MainLog.Log("ChooseMeteor:Begin prompt loop",terminal=False)
    while Result == "": # Loop until a target has been selected. 
        if prechosen is None:
            MainLog.Log("ChooseMeteor:Prompting",terminal=False)
            SearchValue = MeteorChooser.Prompt()
            MainLog.Log("ChooseMeteor:Prompt returned",SearchValue,terminal=False)
        else:
            SearchValue = prechosen
        MainLog.Log("ChooseMeteor:Search for",SearchValue,terminal=False)
        for key,value in Meteor_dictionary.items(): # Python3: Check every item in the meteor shower list.
            sub_dictionary = value
            if key == SearchValue:
                Result = key.lower()
                p = Star(ra_hours=(sub_dictionary['rah'], sub_dictionary['ram'], 0), dec_degrees=(sub_dictionary['dec'], 0, 0))
                const = sub_dictionary['constellation']
                desc = key + ' meteor shower'
                MainLog.Log("ChooseMeteor: Found by meteor shower name (" + key+ ").",terminal=False)
                break
        MainLog.Log("ChooseMeteor:Search returned",Result,terminal=False)
        if Result == "": # Still no match. Give up and ask again. 
            if prechosen != None:
                MainLog.Log("ChooseMeteor: Prechosen " + str(prechosen) + " not recognised. Ignored.",terminal=False)
                return None # Scrap the attempt.
            print("Meteor: Nothing matched, try again.")
    NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
    # Find location of origin.
    MainLog.Log("ChooseMeteor:Establish radec position",terminal=False)
    obstarget = target(handle=p,name=NeatName,objecttype='meteor',constellation=const,description=desc,magnitude=magnitude,searchgroup='meteor',searchterm=SearchValue)
    az, alt = obstarget.AzAltDegrees() # Get initial position in the sky. We'll turn this into a fixed point.
    # Move a useful angle away from the origin.
    MainLog.Log("ChooseMeteor:Establish fixed point",terminal=False)
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
        if prechosen is None:
            NGCChooser = listchooser(NGC_Namelist)
            SearchValue = NGCChooser.Prompt()
        else:
            SearchValue = prechosen
        if SearchValue is None: # User quit the search.
            return None # Scrap the attempt.
        for key in NGC_Namelist: # Check all available NGC catalog items.
            if key == SearchValue:
                Result = key.lower()
                temp_df = NGC_DF.loc[NGC_DF['name'] == key].iloc[0] # Development test, get same record from Dataframe.
                MainLog.Log("ChooseNGC: Matching dataframe entry:",temp_df,terminal=False)
                MainLog.Log("ChooseNGC: Matching dataframe fields:",temp_df['rah'],temp_df['ram'],temp_df['ras'],temp_df['ded'],temp_df['dem'],temp_df['des'],terminal=False)
                p = Star(ra_hours=(temp_df['rah'], temp_df['ram'], temp_df['ras']), dec_degrees=(temp_df['ded'], temp_df['dem'], temp_df['des']))
                magnitude = temp_df['magnitude']
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
        
    CometDataAge() # If the data cache exists, how old is the content?
    Result = ""
    desc = None
    obstarget = None
    p = None
    while Result == "": # Loop until a target has been selected. 
        if prechosen is None:
            CometChooser = listchooser(CometList)
            SearchValue = CometChooser.Prompt()
        else:
            SearchValue = prechosen
        if SearchValue is None: # User quit the search.
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
        if prechosen is None: # We've not received a target name, so ask the user.
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
        if prechosen is None: # We've not received a prechosen name, so ask the user.
            Result = PlanetChooser.Prompt()
        else: # We've received a prechosen name. Don't ask the user.
            Result = prechosen
        if Result is None: # Nothing selected.
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
        if Result is None:
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
        if Parameters.DisplayTZ != 'UTC': Parameters.DisplayTZ = Result
        Parameters.LocalTZ = Result
        print("Local Timezone set to",Parameters.LocalTZ)
        nutc = NowUTC()
        print("UTC time is",nutc)
        print("Local time is",DisplayDT(nutc))
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
        if prechosen is None: # We've not received a prechosen name, so ask the user.
            Result = SatelliteChooser.Prompt()
        else: # We've received a prechosen name. Don't ask the user.
            Result = prechosen
        if Result is None: # Nothing selected.
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
    if prechosen is None:
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
        if rah is None or rah < 0 or rah > 23:
            print (textcolor.red("2nd term must be integer RIGHT ASCENSION hours (0 to 23). Try again"))
            continue # Try again.
        ram = TextToInt(lineitems[2])
        if ram is None or ram < 0 or ram > 59:
            print (textcolor.red("3rd term must be integer RIGHT ASCENSION minutes (0 to 59). Try again"))
            continue # Try again.
        ras = TextToFloat(lineitems[3])
        if ras is None or ras < 0 or ras >= 60:
            print (textcolor.red("4th term must be decimal RIGHT ASCENSION seconds (0.000 to 59.999). Try again"))
            continue # Try again.
        ded = TextToInt(lineitems[5])
        if ded is None or ded < -90 or ded > 90:
            print (textcolor.red("6th term must be integer DECLINATION degrees (-90 to 90). Try again"))
            continue # Try again.
        dem = TextToInt(lineitems[6])
        if dem is None or dem <= -60 or dem >= 60:
            print (textcolor.red("7th term must be integer DECLINATION minutes (-59 to 59). Try again"))
            continue # Try again.
        des = TextToFloat(lineitems[7])
        if des is None or des <= -60 or des >= 60:
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
    if prechosen is None:
        print ("AltazObject: Create a target from Altitude and Azimuth values.")
        print ("Definition format: ALT ddd.dddd AZ ddd.dddd name")
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
        if alt is None or alt < minalt or alt > maxalt:
            print (textcolor.red('2nd term must be float ALTITUDE degrees (',minalt,'to',maxalt,'). Try again'))
            continue # Try again.
        az = TextToFloat(lineitems[3])
        if az is None or az < minaz or az > maxaz:
            print (textcolor.red('4th term must be float AZIMUTH degrees (',minaz,'to',maxaz,'). Try again'))
            continue # Try again.
        break
    MainLog.Log('AltazObject: Coordinates of', name, 'are', AzAltText(az,alt,"deg"),terminal=False)
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
    if Parameters.LatestTrackingFilter is None:
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
    if Parameters.LatestTrackingFilter in Parameters.FilterScripts: # The script exists.
        MainLog.Log("TestLatestFilter: LatestTrackingFilter (",Parameters.LatestTrackingFilter,") exists.",terminal=True)
    else:
        MainLog.Log("TestLatestFilter: LatestTrackingFilter (",Parameters.LatestTrackingFilter,") does not exist.",terminal=True)
        MainLog.Log("TestLatestFilter: LatestTrackingFilter: Please select a filter first.",terminal=True)
        temp = [str(key) for key in Parameters.FilterScripts.keys()]
        MainLog.Log("TestLatestFilter: LatestTrackingFilter: These filters are available:",temp,terminal=True)
        return
    sourcefile = Parameters.FilterTestImage # Start the search in the same place we left off.
    FC = filechooser(title="Select an image file",default=sourcefile,types=['jpg','jpeg'])
    sourcefile, success = FC.ChooseFile()
    if not success: # No file chosen.
        print("No file chosen.")
        return
    Parameters.FilterTestImage = FC.CurrentDir # Remember the location for next time.
    # Create pilomarimage instance for the file.
    image = pilomarimage(name='testlatestfilter',logger=MainLog)
    image.LoadFile(sourcefile)
    outputfile = FolderHandler.PrepFile('temp',"StepThruFilterScript_INITIAL.jpg")
    image.SaveFile(outputfile)
    print("Running",Parameters.LatestTrackingFilter,"against",sourcefile,"...")
    image.StepThruFilterScript(Parameters.LatestTrackingFilter,outputdir=FolderHandler.GetPath('temp'))
    outputfile = FolderHandler.PrepFile('temp',"StepThruFilterScript_FINAL.jpg")
    image.SaveFile(outputfile)
    print("Result is saved in",outputfile)
    
# ------------------------------------------------------------------------------------------------------

def ChooseAurora(prechosen=None):
    """ Set up to create a video of the Aurora. """
    if prechosen is None: print(textcolor.yellow("Choosing Aurora:"))
    if Parameters._HomeLatVal >= 0: # Due North.
        TargetAz = max(0.0,AzimuthControl.MinAngle) # Cannot be below minimum allowed angle.
        Name = "aurora_borealis"
    else: # Due South.
        TargetAz = min(180,AzimuthControl.MaxAngle)
        Name = "aurora_australis"
    TargetAlt = Parameters.AuroraCameraAltitude # Altitude angle for the camera.
    TargetAlt = max(TargetAlt,AltitudeControl.MinObservationAngle) # Cannot be below the minimum allowed angle. *!*
    es = FixedPoint(name=Name,alt=TargetAlt,az=TargetAz)
    obstarget = target(es,name=Name,objecttype='aurora',description=Name,magnitude=2.0,searchgroup='aurora',searchterm='aurora')
    if prechosen is None:
        print(textcolor.yellow("Choosen:",Name))
        print("Camera will point at",AzAltText(TargetAz,TargetAlt,symbol=DegreeSymbol),"to capture potential aurora.")
    return obstarget

# ------------------------------------------------------------------------------------------------------

def GetTarget(searchgroup,searchterm):
    """ Given a searchgroup and searchterm return a target object. """
    if searchgroup == 'solar': temptarget = ChooseSolar(searchterm) # Create a solar system target.
    elif searchgroup == 'satellite': temptarget = ChooseSatellite(searchterm) # Create a satellite target.
    elif searchgroup == 'hipparcos': temptarget = ChooseHipparcos(searchterm) # Create a hipparcos star target.
    elif searchgroup == 'messier': temptarget = ChooseMessier(searchterm,sizewarning=False) # Create a Messier object target. Don't warn about small targets at this point.
    elif searchgroup == 'radec': temptarget = RadecObject(searchterm) # Create an object from radec co-ordinates.
    elif searchgroup == 'altaz': temptarget = AltazObject(searchterm) # Create an object from alt/az co-ordinates.
    elif searchgroup == 'aurora': temptarget = ChooseAurora(searchterm) # Create an object from alt/az co-ordinates.
    elif searchgroup == 'meteor': temptarget = ChooseMeteor(searchterm) # Create an object from meteor shower details.
    elif searchgroup == 'comet': temptarget = ChooseComet(searchterm) # Create an object from comet data.
    elif searchgroup == 'ngc': temptarget = ChooseNGC(searchterm) # Create an object from ngc data.
    else: temptarget = None
    return temptarget

# ------------------------------------------------------------------------------------------------------

class sessionentry(attributemaster):
    """ A single entry in a list of observations. 
        Used for recording past observations, and also to construct lists of future observation schedules. """
        
    def __init__(self,dictionary):
        self._Dictionary = dictionary # Populate the dictionary to load key attributes.
        self.ExtractDictionary() # Pull the attributes out of the dictionary.
        self.Reset() # Initialise other attributes.
        
    def Reset(self):
        """ Initialize/reset other attributes. 
            These are calculation results and are not loaded/saved via the dictionary. """
        pass

    def ExtractDictionary(self,dictionary=None):
        """ Import values from the _Dictionary attribute.
            Dictionary can be given in the call, or can be already set.
            This is called in the __init__() phase and creates the basic attributes of the instance.            """
        if dictionary != None: self._Dictionary = dictionary # Update the dictionary attribute with the latest version.
        # Attributes that can be saved/loaded via a dictionary.
        self.ImportExportList = ['Name','LastObserved','SearchTerm','SearchGroup','TargetType',
                                 'RA','Dec','Alt','Az','ExposureSeconds','TimelapsePeriod', # 'SensorMode',
                                 'ObservationStart','ObservationEnd','ObservationFrames',
                                 'RiseTime','PeakTime','SetTime','RiseAz','PeakAz','PeakAlt','SetAz',
                                 'Magnitude','DiameterDegrees','DiameterPixels']
        self.Name = self.GetParmVal("Name",None)
        self.LastObserved = self.GetDatetimeVal("LastObserved",None) # Needs converting from string to datetime with UTC tz.
        self.SearchTerm = self.GetParmVal("SearchTerm",None)
        self.SearchGroup = self.GetParmVal("SearchGroup",None)
        self.TargetType = self.GetParmVal("TargetType",None)
        self.RA = self.GetParmVal("RA",None)
        self._radeg = None # Calculated RA in degrees. Not stored externally.
        self.Dec = self.GetParmVal("Dec",None)
        self.Alt = self.GetParmVal("Alt",None)
        self.Az = self.GetParmVal("Az",None)
        self.ExposureSeconds = self.GetParmVal("ExposureSeconds",None)
        self.TimelapsePeriod = self.GetParmVal("TimelapseSeconds",None)
        self.ObservationStart = self.GetDatetimeVal("ObservationStart",None) # Needs converting from string to datetime with UTC tz.
        self.ObservationEnd = self.GetDatetimeVal("ObservationEnd",None) # Needs converting from string to datetime with UTC tz.
        self.ObservationDuration = self.GetParmVal("ObservationDuration",None)
        self.ObservationFrames = self.GetParmVal("ObservationFrames",None)
        # Values for suggested target lists.
        self.RiseTime = self.GetDatetimeVal("RiseTime",None) # UTC when target rises.
        self.PeakTime = self.GetDatetimeVal("PeakTime",None) # UTC when target at highest.
        self.SetTime = self.GetDatetimeVal("SetTime",None) # UTC when target sets.
        self.RiseAz = self.GetParmVal("RiseAz",None)  # Azimuth when target rises.
        self.PeakAz = self.GetParmVal("PeakAz",None) # Azimuth when target at peak.
        self.PeakAlt = self.GetParmVal("PeakAlt",None) # Altitude when target at peak.
        self.SetAz = self.GetParmVal("SetAz",None) # Azimuth when target sets.
        self.Magnitude = self.GetParmVal("Magnitude",None) # Apparent magnitude of the target.
        self.DiameterDegrees = self.GetParmVal("DiameterDegrees",None) # Apparent diameter in degrees.
        self.DiameterPixels = self.GetParmVal("DiameterPixels",None) # Apparent diameter in pixels.

    @staticmethod
    def GetSignature(dictionary):
        """ Calculate a signature for the entry based upon critical attributes. 
            This is so we can recognise duplicates. """
        signature = ''
        # Which attributes are used to identify an entry uniquely?
        fieldlist = ['SearchTerm','TargetType','ExposureSeconds','TimelapsePeriod','ObservationStart','ObservationEnd','ObservationDuration','ObservationFrames']
        for i,fieldname in enumerate(fieldlist):
            fieldvalue = dictionary.get(fieldname,None)
            if i > 0: signature += "/"
            if fieldvalue != None: signature += str(fieldvalue)
        return signature

    def BuildDictionary(self) -> dict:
        """ Save the instance attributes which have values to the _Dictionary dictionary.
            - Will not save any values with None.
            It ignores any attributes starting with '_' character, and any references to methods. """
        self._Dictionary = {} # Start an empty dictionary. 
        for attr, value in vars(self).items():
            if value == None: continue # Don't save 'None' values.
            if attr in self.ImportExportList:
                self._Dictionary[attr] = value
        
    def GetParmVal(self,name,default,oldnames=None):
        """ Get a value from a dictionary. 
        
            name: The parameter name.
            default: The default parameter value if it is not in the dictionary yet.
            oldnames: optional list of previous parameter names, these are used to migrate values from old parameter names to new ones.
            
            If the value does not exist, create it with the default value. """
        result = default
        if type(oldnames) == list: # Check for earlier parameter values.
            for oldname in oldnames: # Check each name in turn.
                if oldname in self._Dictionary: # oldname exists in the dictionary (can migrate from oldname to new name).
                    result = self._Dictionary[oldname] # Retrieve the value from the oldname entry.
                    MainLog.Log("sessionentry.GetParmVal(",name,") migrating from",oldname,"with value",result,terminal=False)
                    break # Look no further.
        # Now get/initialise the current parameter name.
        result = self._Dictionary.get(name,result)
        return result
        
    def GetDatetimeVal(self,name,default,oldnames=None):
        """ Pull a string datetime and return the converted datetime value. """
        sval = self.GetParmVal(name,default,oldnames=oldnames)
        if type(sval) != str: # Return None and datetime values without conversion.
            result = sval
        else: # String values need converting.
            result = DTSToDatetime(sval)
        return result
        
    def SimpleDisplay(self):
        """ Create simple display of the entry. """
        self.BuildDictionary() # Store all the attributes back into the dictionary.
        count = 0
        for key,value in self._Dictionary.items():
            print(str(count).rjust(3," "),key.rjust(20," "),":",textcolor.white(str(value)))
            count += 1

class sessionlist(attributemaster):
    """ A class that manages a list of observation sessions/targets. 
        Use it to maintain things like :-
        - A list of past observations, so the user can repeat them. 
        - A list of suggested targets for the current location and time.
        - A list of future observations, so an observation schedule can be followed. """
        
    def __init__(self,name):
        """ Initialize an instance. """
        self.Name = name
        self.Reset()
        
    def Reset(self):
        self.SessionList = [] # List of sessions.
        self.SortOptions = ['SearchTerm','Az','Alt','Magnitude','DiameterPixels']
        self.SortChoice = 4 # Sort by size initially.
        self.DirtyBit = False # Set to True if data is modified.
        self.UpdatedTimestamp = NowUTC() # Reset timestamp

    def AgeMinutes(self):
        """ How many minutes old is the data? """
        result = int((NowUTC() - self.UpdatedTimestamp).total_seconds() / 60)
        return result 
        
    def Add(self,dictionary):
        """ Create a new session entry.
            Optional dictionary will be used to load the entry."""
        signature = sessionentry.GetSignature(dictionary) # Calculate the signature of the entry.
        self.Delete(signature) # Delete any earlier entry with the same set of attributes. Don't allow duplicates, and don't merge conflicting details.
        self.SessionList.append(sessionentry(dictionary))
        self.UpdatedTimestamp = NowUTC() # Reset timestamp
        self.DirtyBit = True # Mark that the list has changed.

    def Delete(self,signature):
        """ Remove a session entry from the list. """
        newlist = [] # The list after cleaning.
        for se in self.SessionList: # Check each entry in turn. 
            temp = sessionentry.GetSignature(se._Dictionary) # Calculate its unique signature.
            if temp == signature: 
                continue # Don't add duplicates.
            newlist.append(se)
        self.SessionList = newlist
        self.UpdatedTimestamp = NowUTC() # Reset timestamp
        self.DirtyBit = True # Mark that the list has changed.
        
    def SortByAge(self):
        """ Sort the list of session entries youngest first.
            This sorts self.SessionList by the LastObserved attribute of each sessionentry. """
        # Sort dictionary by LastObserved value.
        for se in self.SessionList: # Make sure that the dates all exist!
            if se.LastObserved == None: # No date set.
                MainLog.Log("sessionlist(",self.Name,").SortByAge:",se.Name,"LastObserved is not set. Cannot sort the list.",level='error')
                return
        self.SessionList = sorted(self.SessionList,reverse=True,key = lambda x: (x.LastObserved))
        
    def SortByStartTime(self):
        """ Sort the list of session entries in the scheduled start.
            This sorts self.SessionList by the ObservationStart attribute of each sessionentry. """
        # Sort dictionary by ObservationStart value.
        for se in self.SessionList: # Make sure that the dates all exist!
            if se.ObservationStart == None: # No date set.
                MainLog.Log("sessionlist(",self.Name,").SortByStartTime:",se.Name,"ObservationStart is not set. Cannot sort the list.",level='error')
                return
        try: # Only succeeds if all entries have a start time set.
            self.SessionList = sorted(self.SessionList,key = lambda x: (x.ObservationStart))
        except Exception as e:
            MainLog.ReportException(e,comment='sessionlist.SortByStartTime. Unable to sort all values.')
    
    def ValidateList(self):
        """ Check each entry can create a valid target. """
        MainLog.Log("sessionlist.ValidateList(",self.Name,"): Begin",terminal=False)
        print(textcolor.yellow("Validating",self.Name,"list..."))
        for i,se in enumerate(self.SessionList):
            temptarget = GetTarget(se.SearchGroup,se.SearchTerm) # Get the target instance.
            if temptarget == None: # Could not create a target instance.
                print(i,se.SearchGroup,se.SearchTerm,textcolor.red("Not a valid target."))
                MainLog.Log("sessionlist.ValidateList(",self.Name,")",i,se.Name,se.SearchGroup,se.SearchTerm,"is not a valid target.",terminal=False)
            else:
                print(i,se.Name,se.SearchGroup,se.SearchTerm,textcolor.green("OK"))

    def PopulateRADeg(self):
        """ Populate the _radeg field with the current right ascension (in degrees) """
        for se in self.SessionList:
            temptarget = GetTarget(se.SearchGroup,se.SearchTerm) # Get the target instance.
            if temptarget != None:
                result, _ = temptarget.RaDecDegrees()
            else:
                result = None
            se._Dictionary['_radeg'] = result
            se._radeg = result
            
    def SortByRADeg(self):
        """ Sort the list of session entries by the RightAscension (in degrees).
            This calculates the current RA (DEG) of the each target, then sorts by it. """
        # Update/populate _radeg value with current right ascension.
        self.PopulateRADeg()
        # Sort dictionary by RightAscension(degrees) value.
        for se in self.SessionList: # Make sure that the dates all exist!
            if se._radeg == None: # No date set.
                MainLog.Log("sessionlist(",self.Name,").SortByRADeg:",se.Name,"_radeg is not set. Cannot sort the list.",level='error')
                return
        try: # Only succeeds if all entries have a start time set.
            self.SessionList = sorted(self.SessionList,key = lambda x: (x._radeg))
        except Exception as e:
            MainLog.ReportException(e,comment='sessionlist.SortByRADeg. Unable to sort all values.')

    def SortByField(self,fieldname):
        """ Sort the list of session entries by an arbitrary field name. """
        # Sort dictionary by ObservationStart value.
        for se in self.SessionList: # Make sure that the dates all exist!
            if se.GetParmVal(fieldname,None) == None: # Field is not set.
                MainLog.Log("sessionlist(",self.Name,").SortByField:",se.Name,fieldname,"is not set. Cannot sort the list.",level='error')
                return
        try: # Only succeeds if all entries have the field value set.
            self.SessionList = sorted(self.SessionList,key = lambda x: (x._Dictionary[fieldname]))
        except Exception as e:
            MainLog.ReportException(e,comment='sessionlist.SortByField. Unable to sort all values.')

    def NextSortOption(self,option=None):
        """ Rotate through available sort options.
            option: Use a specific sort option.
                    If None, then the next available sort option is chosen. """
        if option == None:
            self.SortChoice = (self.SortChoice + 1) % len(self.SortOptions)
        else:
            self.SortChoice = option % len(self.SortOptions)
        self.SortByField(self.SortOptions[self.SortChoice])            

    def DisplaySuggestionList(self):
        """ Display list in the format used for suggested targets. """
        i = 0 # Maintain a line count for the items listed.
        print(" ")
        print(textcolor.yellow( # Heading.
              " " * 63,
              Parameters.DisplayTZ.ljust(20," ")[:20]))
        print(textcolor.yellow( # Heading.
              "id".rjust(4," ")[:4],
              "name".ljust(20," ")[:20],
              "az".rjust(8," ")[:8],
              "alt".rjust(9," ")[:9],
              "mag".rjust(9," ")[:9],
              "pixels".rjust(8," ")[:8],
              "rose".ljust(5," ")[:5],
              "set".ljust(5," ")[:5]))
        for se in self.SessionList: # Check each SessionEntry instance in turn from the SessionList.
            rs = ""
            #if se.RiseTime != None: rs += HmsFromStamp(se.RiseTime)[:5] + " " 
            if se.RiseTime != None: rs += HmsFromStamp(UTCtoDisplay(se.RiseTime))[:5] + " " 
            else: rs += "--:-- "
            #if se.SetTime != None: rs += HmsFromStamp(se.SetTime)[:5] + " UTC"
            if se.SetTime != None: rs += HmsFromStamp(UTCtoDisplay(se.SetTime))[:5] + " "
            else: rs += "--:-- "
            if se.Az != None: az = se.Az
            else: az = 0
            if se.Alt != None: alt = se.Alt
            else: alt = 0
            if se.Magnitude != None: mag = se.Magnitude
            else: mag = 0
            if se.DiameterPixels != None: dpix = se.DiameterPixels
            else: dpix = 0
            print(textcolor.white(str(i).rjust(4)),
                  se.SearchTerm.ljust(20," ")[:20],
                  str(round(az,1)).rjust(8," ")[:8] + DegreeSymbol,
                  str(round(alt,1)).rjust(8," ")[:8] + DegreeSymbol,
                  str(round(float(mag),1)).rjust(8," ")[:8],
                  str(int(dpix)).rjust(8," ")[:8],
                  rs)
            i += 1
            if i % 5 == 0: print(" ")
        print("( Sorted by",self.SortOptions[self.SortChoice],")") # Explain what sequence is used.        

    def DisplayScheduleList(self):
        """ Display list in the format used for observation schedules. """
        print("")
        print(textcolor.yellow("Observation schedule:-"))
        print("")
        i = 0 # Maintain a line count for the items listed.
        print("id".rjust(4," ")[:4],
              "name".ljust(20," ")[:20],
              "frames".rjust(9," ")[:9],
              "secs".rjust(8," ")[:8],
              "group".ljust(8," ")[:8],
              "term".ljust(40," ")[:40])
        for se in self.SessionList: # Check each SessionEntry instance in turn from the SessionList.
            print(textcolor.white(str(i).rjust(4)),
                  se.Name.ljust(20," ")[:20],
                  str(se.ObservationFrames).rjust(9," ")[:9],
                  str(se.ExposureSeconds).rjust(8," ")[:8],
                  se.SearchGroup.ljust(8," ")[:8],
                  se.SearchTerm.ljust(40," ")[:40]
                  )
            i += 1
            if i % 5 == 0: print(" ")
        print("")

    def LoadFromJson(self,filename):
        """ Load the json file as a dictionary. """
        if os.path.exists(filename): # File exists to load.
            with open(filename,'r') as f:
                dictionary = json.load(f)
                for name,subdict in dictionary.items(): # Now parse the json file and load the sessions up.
                    self.Add(subdict) # Convert each item into a sessionentry instance. {'Name':'Moon-10','SearchTerm':'moon','SearchGroup':'solar','TargetType':'solar','ExposureSeconds':0.00000001, 'LastObserved':NowUTC()}    
            self.DirtyBit = False # List is pristine.
        else: # File doesn't exist.
            MainLog.Log("sessionlist.LoadFromJson:",filename,"does not exist.",terminal=False)

    def LoadScheduleFromJson(self):
        """ Load the json file as a dictionary.
            This loads the observation schedule list and validates the contents. """
        filename = FolderHandler.PrepFile('dataroot','observationschedule.json')
        if os.path.exists(filename):
            MainLog.Log("Loading:",filename)
            self.LoadFromJson(filename)
            self.ValidateList() # Validate the list.
        else:
            MainLog.Log("LoadScheduleFromJson: File does not exist.",filename,level='error')

    def SaveAsJson(self,filename,limit=None):
        """ Save the session list as a json file. 
            Save it in an easily read/edited format.
            This saves 1 line per sessionentry.
            If limit is given, the export only writes that many entries. """
        savelist = self.SessionList
        if limit != None and len(savelist) > limit: savelist = savelist[:limit] # Truncate the number of records saved.
        with open(filename,'w') as f:
            f.write('{\n')
            for i,se in enumerate(savelist):
                se.BuildDictionary()
                f.write('    "' + str(i).rjust(4,"0") + '" : ' + json.dumps(se._Dictionary,default=str))
                if i + 1 < len(savelist): f.write(',')
                f.write('\n')
            f.write('}\n')
        self.DirtyBit = False # List is editable.

    def SaveScheduleAsJson(self):
        """ Save the session list as a json file. 
            Save it in an easily read/edited format.
            This saves 1 line per sessionentry. """
        filename = FolderHandler.PrepFile('dataroot','observationschedule.json')
        self.SaveAsJson(filename)
        MainLog.Log("Saved:",filename)

    def CloneSessionList(self,donor):
        """ Clone sessionlist from another sessionlist donor. 
            donor = an instance of sessionlist. """
        self.SessionList = donor.SessionList.copy()
        self.DirtyBit = True # List has been modified.
        
    def CheckDirtyBit(self):
        """ If DirtyBit is set, then offer to save the list. """
        if self.DirtyBit:
            if AskYesNo("The " + self.Name + " target list has changed but not been saved. Save it now? [y/N]",False):
                self.SaveScheduleAsJson()
        
# ------------------------------------------------------------------------------------------------------

SessionHistory = sessionlist('History') # Create a session history instance.
SessionHistory.LoadFromJson(HistoryJsonFile) # Load any previous history entries from the json disc file.
SuggestedTargets = sessionlist('Suggested') # Create target list to store suggestions.
        
# ------------------------------------------------------------------------------------------------------

def ChooseHistory(selection=None):
    """ User can retrieve earlier target selections and the exposure time.
        This allows resuming earlier observations more safely. """
    obstarget = None # No target selected yet.
    cols,rows = GetTerminalSize() # How wide is the display? Format the options list to fit. *Q* TO COMPLETE
    print (textcolor.yellow("Choose an object from an earlier observation."))
    print ("Listing from " + HistoryJsonFile)
    if not os.path.exists(HistoryJsonFile):
        print (textcolor.red("ChooseHistory: " + HistoryJsonFile + " does not yet exist."))
        print (textcolor.red("You have not chosen any targets yet."))
        print (textcolor.red("Choose a target some other way first."))
        return obstarget
    # Construct a list of unique observation options from history.
    SessionHistory.LoadFromJson(HistoryJsonFile) # Refresh the history list.
            
    # List the unique options. 'Lines' contains the unique observation details on offer.
    print ('')
    temptime = SkyfieldNow() # Use the same timestamp for everything in the list, otherwise repeated objects show inconsistent positions.
    print ('       ' + Parameters.DisplayTZ)
    print (' Line  Last used           Name                 Category   Exposure  Current alt / az       RiseSet Other')
    #       123456 1234567890123456789 12345678901234567890 1234567890 12345678901234567890123456789012345678901234567890
    spacecount = 0 # Put a gap every 5 lines for readability.
    count = 0
    for se in SessionHistory.SessionList:
        displine = '' # Empty line until we have constructed all the details.
        displine = DisplayDT(se.LastObserved)[:19] + ' ' # Timestamp
        displine += se.Name.ljust(20)[:20] + ' ' # Name
        displine += se.SearchGroup.ljust(10)[:10] + ' ' # Category
        displine += str(se.ExposureSeconds).rjust(5)[:5] + 's. ' # Exposure
        miscline = '' # Miscellaneous info.
        if se.TimelapsePeriod != None and se.TimelapsePeriod > 0: # Timelapse is available.
            miscline += 'Timelapse ' + str(se.TimelapsePeriod) + 's. '
        temptarget = GetTarget(se.SearchGroup,se.SearchTerm) # Get the target instance.
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
        count += 1
        if count % 5 == 0: print ('') # Blank line to make the table more readable if it is very large.
    MainLog.Log("ChooseHistory: Selected " + str(count) + " unique options from history.",terminal=False)
    # User must select one of the listed options.
    temp = '' # No choice made yet.
    while temp == '':
        temp = input(textcolor.cyan("Select history line (x to quit): "))
        if temp.lower() == "x": # Cancel selection.
            break
        i = TextToInt(temp) # Make sure it is a valid choice.
        if i != None and i >= 0 and i < count:
            MainLog.Log("ChooseHistory: Selected entry ",i,terminal=False)
            # Get the record.
            se = None
            for j,sf in enumerate(SessionHistory.SessionList):
                if i == j: se = sf # Found the requested entry.
            if se == None: # Didn't select an entry.
                MainLog.Log("ChooseHistory: Failed to select line",i,level='error')
                break
            CameraInUse.SetTimelapse(se.TimelapsePeriod)
            CameraInUse.ExposureSeconds = se.ExposureSeconds
            if se.SearchGroup == 'solar':
                obstarget = ChooseSolar(se.SearchTerm) # Create a solar system target.
                break
            elif se.SearchGroup == 'satellite':
                obstarget = ChooseSatellite(se.SearchTerm) # Create a satellite target.
                break
            elif se.SearchGroup == 'hipparcos':
                obstarget = ChooseHipparcos(se.SearchTerm) # Create a hipparcos star target.
                break
            elif se.SearchGroup == 'messier':
                obstarget = ChooseMessier(se.SearchTerm) # Create a Messier object target.
                break
            elif se.SearchGroup == 'radec':
                obstarget = RadecObject(se.SearchTerm) # Create an object from radec co-ordinates.
                break
            elif se.SearchGroup == 'altaz':
                obstarget = AltazObject(se.SearchTerm) # Create an object from alt/az co-ordinates.
                break
            elif se.SearchGroup == 'aurora':
                obstarget = ChooseAurora(se.SearchTerm) # Create an object from alt/az co-ordinates.
                break
            elif se.SearchGroup == 'meteor':
                obstarget = ChooseMeteor(se.SearchTerm) # Create an object from meteor shower details.
                break
            elif se.SearchGroup == 'comet':
                obstarget = ChooseComet(se.SearchTerm) # Create an object from comet details.
                break
            elif se.SearchGroup == 'ngc':
                obstarget = ChooseNGC(se.SearchTerm) # Create an object from NGC details.
                break
            else:
                MainLog.Log("ChooseHistory: Unrecognised searchgroup: Line " + str(temp),level='error')
        # If we got this far, the choice was not valid. Reset and ask again.
        temp = '' # Reset and ask again. 
    return obstarget

# ------------------------------------------------------------------------------------------------------

def ChooseLastTarget():
    """ Resume previous observation target and settings. """
    MainLog.Log("ChooseLastTarget: Begin",terminal=False)
    obstarget = None # No target selected yet.
    if not os.path.exists(HistoryJsonFile): # No file to process yet.
        print (textcolor.red("ChooseLastTarget: " + HistoryJsonFile + " does not yet exist."))
        print (textcolor.red("You have not chosen any targets yet."))
        print (textcolor.red("Choose a target some other way first."))
        return obstarget
    # Construct a list of unique observation options from history.
    SessionHistory.LoadFromJson(HistoryJsonFile) # Refresh the history list.

    se = SessionHistory.SessionList[0] # Read first entry.
    CameraInUse.SetTimelapse(se.TimelapsePeriod)
    CameraInUse.ExposureSeconds = se.ExposureSeconds
    MainLog.Log("ChooseLastTarget: Selected " + line,terminal=False)
    if se.SearchGroup == 'solar': obstarget = ChooseSolar(se.SearchTerm) # Create a solar system target.
    elif se.SearchGroup == 'satellite': obstarget = ChooseSatellite(se.SearchTerm) # Create a satellite target.
    elif se.SearchGroup == 'hipparcos': obstarget = ChooseHipparcos(se.SearchTerm) # Create a hipparcos star target.
    elif se.SearchGroup == 'messier': obstarget = ChooseMessier(se.SearchTerm) # Create a Messier object target.
    elif se.SearchGroup == 'radec': obstarget = RadecObject(se.SearchTerm) # Create an object from radec co-ordinates.
    elif se.SearchGroup == 'altaz': obstarget = AltazObject(se.SearchTerm) # Create an object from alt/az co-ordinates.
    elif se.SearchGroup == 'aurora': obstarget = ChooseAurora(se.SearchTerm) # Create an object from alt/az co-ordinates.
    elif se.SearchGroup == 'meteor': obstarget = ChooseMeteor(se.SearchTerm) # Create an object from meteor shower details.
    elif se.SearchGroup == 'comet': obstarget = ChooseComet(se.SearchTerm) # Create an object from comet details.
    elif se.SearchGroup == 'ngc': obstarget = ChooseNGC(se.SearchTerm) # Create an object from NGC details.
    else: MainLog.Log("ChooseLastTarget: Unrecognised searchgroup: Line " + str(temp),level='error')
    return obstarget

# ------------------------------------------------------------------------------------------------------

def RiseSetString(otarget):
    """ Return a string listing RISE and SET times of target.
        otarget should be an instance of the target class.
        EARTH CENTRIC objects raise an error here. So they are ignored.
        The timestamps are shown in UTC or local timezone depending upon Parameters.DisplayTZ value. """
    try:
        risetime, settime = otarget.RiseSet()
    except Exception:
        risetime = settime = None
        MainLog.Log("RiseSetString(): Failed. rise/set set to None.",terminal=False,level='warning')
    if risetime != None:
        if risetime < settime: # Put resulting RISE and SET times in chronological sequence. 
            #RS = ' Target Rise: ' + str(risetime).split('.')[0] + ' UTC , Set: ' + str(settime).split('.')[0] + " UTC"
            RS = ' Target Rise: ' + DisplayDT(risetime) + ', Set: ' + DisplayDT(settime)
        else:
            #RS = ' Target Set: ' + str(settime).split('.')[0] + ' UTC , Rise: ' + str(risetime).split('.')[0] + " UTC"
            RS = ' Target Set: ' + DisplayDT(settime) + ', Rise: ' + DisplayDT(risetime)
    else:
        if otarget.Visible(): RS = ' Target is permanently above the horizon, it will not set.'
        else: RS = ' Target is permanently below the horizon, it will not rise.'
    return RS
    
# ------------------------------------------------------------------------------------------------------

def SuggestTarget_Solar(suggestedtargets):
    """ suggestedtargets = an instance of the sessionlist class. 
        This adds suitable solar system viewing targets to the list. """
    planet_data = {
        'sun': {
            'name': 'sun',
            'objecttype':'sun', 
            'magnitude':-26.7,
            'sizedeg': 0.5 # 0.5 degrees.
        },
        'moon': {
            'name': 'moon',
            'objecttype': 'moon', 
            'magnitude': -12.5,
            'sizedeg': 0.5 # 0.5 degrees.
        },
        'mercury barycenter': {
            'name': 'mercury',
            'objecttype':'planet', 
            'magnitude': 0.23,
            'sizedeg': 13 / 3600 # 13 arcseconds to degrees.
        },
        'venus barycenter': {
            'name': 'venus',
            'objecttype':'planet', 
            'magnitude': -4.4,
            'sizedeg': 30 / 3600 # 30 arcseconds to degrees.
        },
        'mars barycenter': {
            'name': 'mars',
            'objecttype':'planet', 
            'magnitude': -2.91,
            'sizedeg': 10 / 3600 # 10 arcseconds to degrees.
        },
        'jupiter barycenter': {
            'name': 'jupiter',
            'objecttype':'planet', 
            'magnitude': -2.7,
            'sizedeg': 40 / 3600 # 40 arcseconds to degrees.
        },
        'saturn barycenter': {
            'name': 'saturn',
            'objecttype':'planet', 
            'magnitude': -0.55,
            'sizedeg': 40 / 3600 # 60 arcseconds (inc rings) to degrees.
        },
        'uranus barycenter': {
            'name': 'uranus',
            'objecttype':'planet', 
            'magnitude': 5.68,
            'sizedeg': 3.5 / 3600 # 3.5 arcseconds to degrees.
        },
        'neptune barycenter': {
            'name': 'neptune',
            'objecttype':'planet', 
            'magnitude': 7.78,
            'sizedeg': 2.3 / 3600 # 2.3 arcseconds to degrees.
        },
        'pluto barycenter': {
            'name': 'pluto',
            'objecttype':'planet', 
            'magnitude': 15.1, # Pluto. I know, it's not officially a planet, but hey! We know where it is!
            'sizedeg': 0.1 / 60 / 60 # 0.1 arcseconds         
        }
    }
    MainLog.Log("SuggestTarget_Solar: Checking",len(planet_data),"Solar System objects.")
    for key, planet_entry in planet_data.items():
        name = planet_entry.get('name','unknown')
        objtyp = planet_entry.get('objecttype','planet')
        mag = planet_entry.get('magnitude',15.1)
        sizedeg = planet_entry.get('sizedeg',0.1 / 60 / 60)
        if mag > Parameters.SuggestionMagnitude: continue # Too dim to recommend.
        tt = target(planets[key],name=name,objecttype=objtyp,description=name,magnitude=mag,searchgroup='solar',searchterm=name)
        az, alt = tt.AzAltDegrees() # Target's position. Altitude and Azimuth from observer's location.
        if alt <= Parameters.HorizonAltitude or alt > AltitudeControl.MaxAngle: continue # Not within scope.
        if az <= AzimuthControl.MinAngle or az > AzimuthControl.MaxAngle: continue # Not within scope.
        risetime,settime = tt.CurrentRiseSet() # Target's next RISE/SET times.
        temp_dictionary = {#"LastObserved":None,
                           "SearchTerm":name,
                           "SearchGroup":'solar',
                           #"TargetType":None, 
                           #"RA":None,
                           #"Dec":None,
                           "Alt":alt, # Current position
                           "Az":az,
                           #"ExposureSeconds":None,
                           #"TimelapseSeconds":None,
                           #"ObservationStart":None,
                           #"ObservationEnd":None,
                           #"ObservationDuration":None,
                           #"ObservationFrames":None,
                           "RiseTime":str(risetime), # UTC when target rises.
                           "PeakTime":None, # UTC when target at highest.
                           "SetTime":str(settime), # UTC when target sets.
                           "RiseAz":None,  # Azimuth when target rises.
                           "PeakAz":None, # Azimuth when target at peak.
                           "PeakAlt":None, # Altitude when target at peak.
                           "SetAz":None, # Azimuth when target sets.
                           "Magnitude":mag, # Apparent magnitude of the target.
                           "DiameterDegrees":sizedeg, # Apparent diameter in degrees.
                           "DiameterPixels":sizedeg * CameraInUse.PixelsPerFovDegreeWidth} # Apparent diameter in pixels.
        suggestedtargets.Add(temp_dictionary) # Add details of the target to the list.
        #return suggestedtargets

def SuggestTarget_Messier(suggestedtargets):
    """ suggestedtargets = an instance of the sessionlist class. 
        This adds suitable Messier catalog targets to the list. """ 
    # List of MESSIER objects
    MainLog.Log("SuggestTarget_Messier: Checking",len(Messier_dictionary),"Messier objects.")
    for key,sub_dictionary in Messier_dictionary.items(): # Python3: Check every item in the Messier catalog.
        magnitude = sub_dictionary['magnitude']
        if magnitude > Parameters.SuggestionMagnitude: continue # Too dim to recommend.
        Result = key.lower()
        desc = sub_dictionary['description']
        objecttype = sub_dictionary['type']
        width = sub_dictionary['width']
        height = sub_dictionary['height']
        NeatName = SafeName(Result)
        p = Star(ra_hours=(sub_dictionary['ra'][0], sub_dictionary['ra'][1], sub_dictionary['ra'][2]), dec_degrees=(sub_dictionary['dec'][0], sub_dictionary['dec'][1], sub_dictionary['dec'][2]))
        tt = target(p,name=NeatName,objecttype=objecttype,constellation=None,description=desc,magnitude=magnitude,searchgroup='messier',searchterm=Result)
        az, alt = tt.AzAltDegrees() # Target's position. Altitude and Azimuth from observer's location.
        if alt <= Parameters.HorizonAltitude or alt > AltitudeControl.MaxAngle: continue # Not within scope.
        if az <= AzimuthControl.MinAngle or az > AzimuthControl.MaxAngle: continue # Not within scope.
        # Establish a size for the object if known.
        sizemin = None
        if width != None: 
            if sizemin is None or width > sizemin: sizemin = width
        if height != None: 
            if sizemin is None or height > sizemin: sizemin = height
        if sizemin != None: 
            sizedeg = DMSToAngle(minutes=sizemin) # Convert from minutes to degrees.
            sizepix = sizedeg * CameraInUse.PixelsPerFovDegreeWidth # How many pixels is this size?
        if sizepix < Parameters.SuggestionPixels: continue # Only suggest LARGE objects.
        risetime,settime = tt.CurrentRiseSet() # Target's next RISE/SET times.
        temp_dictionary = {#"LastObserved":None,
                           "SearchTerm":NeatName,
                           "SearchGroup":'messier',
                           #"TargetType":None, # *Q* Does not appear to be used anywhere. Remove it?
                           #"RA":None,
                           #"Dec":None,
                           "Alt":alt, # Current position
                           "Az":az,
                           #"ExposureSeconds":None,
                           #"TimelapseSeconds":None,
                           #"ObservationStart":None,
                           #"ObservationEnd":None,
                           #"ObservationDuration":None,
                           #"ObservationFrames":None,
                           "RiseTime":str(risetime), # UTC when target rises.
                           "PeakTime":None, # UTC when target at highest.
                           "SetTime":str(settime), # UTC when target sets.
                           "RiseAz":None,  # Azimuth when target rises.
                           "PeakAz":None, # Azimuth when target at peak.
                           "PeakAlt":None, # Altitude when target at peak.
                           "SetAz":None, # Azimuth when target sets.
                           "Magnitude":magnitude, # Apparent magnitude of the target.
                           "DiameterDegrees":sizedeg, # Apparent diameter in degrees.
                           "DiameterPixels":sizepix} # Apparent diameter in pixels.
        suggestedtargets.Add(temp_dictionary) # Add details of the target to the list.
        #return suggestedtargets

def SuggestTarget_NGC(suggestedtargets):
    """ suggestedtargets = an instance of the sessionlist class. 
        This adds suitable NGC catalog targets to the list. """ 
    # List of NGC objects
    ngccount = len(NGC_Namelist)
    MainLog.Log("SuggestTarget_NGC: Checking",ngccount,"NGC & IC objects.")
    print(" ") # Clear a line for the progress timer.
    prgt = progresstimer('ngc',target=ngccount) # Report progress and ETA.  
    i = 0    
    for key in NGC_Namelist: # Check all available NGC items.
        i += 1
        prgt.UpdateCount(i) # How far have we got so far? prgt will then produce ETA and % complete for us.
        temp_df = NGC_DF.loc[NGC_DF['name'] == key].iloc[0] # Development test, get same record from Dataframe.
        #MainLog.Log("SuggestTargetNGC: Matching dataframe entry:",temp_df,terminal=False)
        #MainLog.Log("SuggestTargetNGC: Matching dataframe fields:",temp_df['rah'],temp_df['ram'],temp_df['ras'],temp_df['ded'],temp_df['dem'],temp_df['des'],terminal=False)
        print(prgt.MakeProgressBar(color=True,text='',length=20,show_start=True,show_eta=True))
        #print(textcolor.cursorup() + NowHMS(),textcolor.white(str(round(prgt.GetPercent(),1))),"%. Record",i,"of",prgt.Target,". ETA",str(prgt.GetETA()).split('.')[0],"UTC",textcolor.clearlineforward())        
        magnitude = temp_df['magnitude']
        if magnitude > Parameters.SuggestionMagnitude: continue # Too dim, ignore.
        Result = key.lower()
        p = Star(ra_hours=(temp_df['rah'], temp_df['ram'], temp_df['ras']), dec_degrees=(temp_df['ded'], temp_df['dem'], temp_df['des']))
        desc = key + ' NGC'
        NeatName = SafeName(Result) # No spaces in name, it is used to create folders, keep it simple.
        tt = target(handle=p,name=NeatName,objecttype="ngc",constellation=None,description=desc,magnitude=magnitude,searchgroup='ngc',searchterm=Result)
        az, alt = tt.AzAltDegrees() # Target's position. Altitude and Azimuth from observer's location.
        if alt <= Parameters.HorizonAltitude or alt > AltitudeControl.MaxAngle: continue # Not within scope.
        if az <= AzimuthControl.MinAngle or az > AzimuthControl.MaxAngle: continue # Not within scope.
        width = temp_df['width'] / 60 # From arcseconds to minutes.
        height = temp_df['height'] / 60 # From arcseconds to minutes.
        # Establish a size for the object if known.
        sizemin = None
        if width != None: 
            if sizemin is None or width > sizemin: sizemin = width
        if height != None: 
            if sizemin is None or height > sizemin: sizemin = height
        if sizemin != None: 
            sizedeg = DMSToAngle(minutes=sizemin) # Convert from minutes to degrees.
            sizepix = sizedeg * CameraInUse.PixelsPerFovDegreeWidth # How many pixels is this size?
        if sizepix < Parameters.SuggestionPixels: continue # Only suggest LARGE objects.
        risetime,settime = tt.CurrentRiseSet() # Target's next RISE/SET times.
        temp_dictionary = {#"LastObserved":None,
                           "SearchTerm":NeatName,
                           "SearchGroup":'ngc',
                           #"TargetType":None, # *Q* Does not appear to be used anywhere. Remove it?
                           #"RA":None,
                           #"Dec":None,
                           "Alt":alt, # Current position
                           "Az":az,
                           #"ExposureSeconds":None,
                           #"TimelapseSeconds":None,
                           #"ObservationStart":None,
                           #"ObservationEnd":None,
                           #"ObservationDuration":None,
                           #"ObservationFrames":None,
                           "RiseTime":str(risetime), # UTC when target rises.
                           "PeakTime":None, # UTC when target at highest.
                           "SetTime":str(settime), # UTC when target sets.
                           "RiseAz":None,  # Azimuth when target rises.
                           "PeakAz":None, # Azimuth when target at peak.
                           "PeakAlt":None, # Altitude when target at peak.
                           "SetAz":None, # Azimuth when target sets.
                           "Magnitude":magnitude, # Apparent magnitude of the target.
                           "DiameterDegrees":sizedeg, # Apparent diameter in degrees.
                           "DiameterPixels":sizepix} # Apparent diameter in pixels.
        suggestedtargets.Add(temp_dictionary) # Add details of the target to the list.
        #return suggestedtargets

def SuggestTarget_Comet(suggestedtargets):
    """ suggestedtargets = an instance of the sessionlist class. 
        This adds suitable comets to the list.
        (This is the slowest of the suggestion lists to process) """ 
    # List of COMETS: *Q* Relatively slow, can this calculation be faster?
    cometcount = len(comets)
    MainLog.Log("SuggestTarget_Comet: Checking ",cometcount,"comets.")
    print("") # Clear a line for the progress timer message.
    prgt = progresstimer('comets',target=cometcount) # Report progress and ETA.    
    for i,c in enumerate(comets['designation']): # Python3: Check every item in the comet list.
        prgt.Increment() # How far have we got so far? prgt will then produce ETA and % complete for us.
        print(prgt.MakeProgressBar(color=True,text='',length=20,show_start=True,show_eta=True))
        #print(textcolor.cursorup() + NowHMS(),textcolor.white(str(round(prgt.GetPercent(),1))),"%. Record",i,"of",prgt.Target,". ETA",str(prgt.GetETA()).split('.')[0],"UTC",textcolor.clearlineforward())
        row = comets.loc[c] # Store the Pandas row in the TargetObject because we don't immediately create the 'Star' object.
        MainLog.Log("ChooseComet: Pandas row available data for the comet:", str(list(comets.columns)),terminal=False) # Show available data.
        p = planets['sun'] + mpc.comet_orbit( row, ts, GM_SUN)
        desc = "Comet " + c
        NeatName = SafeName(c) # No spaces in name, it is used to create folders, keep it simple.
        tt = target(handle=p,name=NeatName,objecttype="comet",description=desc,constellation=None,magnitude=None,searchgroup='comet',searchterm=c,cometpandasrow=row)
        az, alt = tt.AzAltDegrees() # Target's position. Altitude and Azimuth from observer's location.
        if alt <= Parameters.HorizonAltitude or alt > AltitudeControl.MaxAngle: continue # Not within scope.
        if az <= AzimuthControl.MinAngle or az > AzimuthControl.MaxAngle: continue # Not within scope.
        magnitude = tt.ApparentCometMagnitudeGK() 
        if magnitude > Parameters.SuggestionMagnitude: continue # Estimated magnitude is probably not bright enough.
        risetime,settime = tt.CurrentRiseSet() # Target's next RISE/SET times.
        temp_dictionary = {#"LastObserved":None,
                           "SearchTerm":c,
                           "SearchGroup":'comet',
                           #"TargetType":None, # *Q* Does not appear to be used anywhere. Remove it?
                           #"RA":None,
                           #"Dec":None,
                           "Alt":alt, # Current position
                           "Az":az,
                           #"ExposureSeconds":None,
                           #"TimelapseSeconds":None,
                           #"ObservationStart":None,
                           #"ObservationEnd":None,
                           #"ObservationDuration":None,
                           #"ObservationFrames":None,
                           "RiseTime":str(risetime), # UTC when target rises.
                           "PeakTime":None, # UTC when target at highest.
                           "SetTime":str(settime), # UTC when target sets.
                           "RiseAz":None,  # Azimuth when target rises.
                           "PeakAz":None, # Azimuth when target at peak.
                           "PeakAlt":None, # Altitude when target at peak.
                           "SetAz":None, # Azimuth when target sets.
                           "Magnitude":magnitude, # Apparent magnitude of the target.
                           "DiameterDegrees":0.1, # Apparent diameter in degrees.
                           "DiameterPixels":0.1 * CameraInUse.PixelsPerFovDegreeWidth} # Apparent diameter in pixels.
        suggestedtargets.Add(temp_dictionary) # Add details of the target to the list.
    
        #return suggestedtargets
    
#def SuggestTarget_xxx():
#    """ Look through list of potential targets and identify which ones are suitable for immediate observation.
#        Checks SOLAR,MESSIER,NGC and COMET catalogs for potential targets.
#        Must be bright enough, high enough and large enough. """
#    print(textcolor.yellow("Suggest a target:"))
#    print("This will list major targets from known catalogs")
#    print("which are currently visible from your home location.")
#    print("")
#    print("Analysing...")
#    obstarget = None # Selected target.
#    SuggestedTargets = sessionlist('Suggested') # Create target list to store suggestions.
#    SuggestedTargets = SuggestTarget_Solar(SuggestedTargets) # Add solar system targets. 
#    SuggestedTargets = SuggestTarget_Messier(SuggestedTargets) # Add Messier objects.
#    SuggestedTargets = SuggestTarget_NGC(SuggestedTargets) # Add NGC objects.
#    SuggestedTargets = SuggestTarget_Comet(SuggestedTargets) # Add potential comets.
#    MainLog.Log("SuggestTarget: Selected",len(SuggestedTargets.SessionList),"potential targets.",terminal=False)
#    print("Have selected",len(SuggestedTargets.SessionList),"potential targets.")
#    
#    # Now present the list of suggested targets, allow sorting and selection.
#    # User selects a target by ID number in the display.
#    SuggestedTargets.SortOptions = ['SearchTerm','Az','Alt','Magnitude','DiameterPixels']
#    SuggestedTargets.SortChoice = 4 # Sort by size initially.
#    SuggestedTargets.SortByField(SuggestedTargets.SortOptions[SuggestedTargets.SortChoice])
#    
#    # Display the list.
#    while obstarget == None: # Repeat until a target is successfully chosen or the user quits.
#        SuggestedTargets.DisplaySuggestionList()
#        choice = input(textcolor.cyan("Enter row number, '@' to change sorting order, 'x' to quit:")).lower() # Ask the user.
#        if choice == '@': 
#            SuggestedTargets.NextSortOption() # Change sort.
#            continue # Redraw the list in the new sort sequence.
#        if choice == 'x': # Quit.
#            break # No choice made.
#        if IsInt(choice): # Validate the choice.
#            temp = int(choice)
#            if temp < 0 or temp >= len(SuggestedTargets.SessionList):
#                print(textcolor.red("Out of range (",0,"-",len(SuggestedTargets.SessionList) - 1,"). Try again."))
#                continue
#            se = SuggestedTargets.SessionList[temp] # Pull the suggested sessionentry instance.
#            print("Selected row",temp,",",se.SearchGroup,se.SearchTerm) # Confirm the choice.
#            # Use standard functions to formally select the chosen target.
#            if se.SearchGroup == 'solar': obstarget = ChooseSolar(se.SearchTerm) # Create a solar system target.
#            elif se.SearchGroup == 'satellite': obstarget = ChooseSatellite(se.SearchTerm) # Create a satellite target.
#            elif se.SearchGroup == 'hipparcos': obstarget = ChooseHipparcos(se.SearchTerm) # Create a hipparcos star target.
#            elif se.SearchGroup == 'messier': obstarget = ChooseMessier(se.SearchTerm) # Create a Messier object target.
#            elif se.SearchGroup == 'radec': obstarget = RadecObject(se.SearchTerm) # Create an object from radec co-ordinates.
#            elif se.SearchGroup == 'altaz': obstarget = AltazObject(se.SearchTerm) # Create an object from alt/az co-ordinates.
#            elif se.SearchGroup == 'aurora': obstarget = ChooseAurora(se.SearchTerm) # Create an object from alt/az co-ordinates.
#            elif se.SearchGroup == 'meteor': obstarget = ChooseMeteor(se.SearchTerm) # Create an object from meteor shower details.
#            elif se.SearchGroup == 'comet': obstarget = ChooseComet(se.SearchTerm) # Create an object from comet details.
#            elif se.SearchGroup == 'ngc': obstarget = ChooseNGC(se.SearchTerm) # Create an object from NGC details.
#            else: 
#                MainLog.Log("SuggestTarget: Unrecognised searchgroup: Line " + str(temp),level='error')
#                continue
#            break # We have a winner.
#        print(textcolor.red("?",choice,"? Please try again."))
#
#    # Save result.
#    outputfile = FolderHandler.PrepFile('temp',"suggested_targets.json")
#    SuggestedTargets.SaveAsJson(outputfile)
#    
#    return obstarget
    
# ------------------------------------------------------------------------------------------------------

def SuggestTarget():
    """ Look through list of potential targets and identify which ones are suitable for immediate observation.
        Checks SOLAR,MESSIER,NGC and COMET catalogs for potential targets.
        Must be bright enough, high enough and large enough. 
        The list is retained for up to 2 hours once calculated.
        Inputs ---------------------------------------------------
        SuggestedTargets: Global instance of sessionlist object. """
    print(textcolor.yellow("Suggest a target:"))
    print("This will list major targets from known catalogs")
    print("which are currently visible from your home location.")
    print("")
    if len(SuggestedTargets.SessionList) == 0 or SuggestedTargets.AgeMinutes() > 120: # Nothing in the list yet, or too old to reuse, calculate the suggestions.
        print("Analysing...")
        #SuggestedTargets = sessionlist('Suggested') # Create target list to store suggestions.
        SuggestTarget_Solar(SuggestedTargets) # Add solar system targets. 
        SuggestTarget_Messier(SuggestedTargets) # Add Messier objects.
        SuggestTarget_NGC(SuggestedTargets) # Add NGC objects.
        SuggestTarget_Comet(SuggestedTargets) # Add potential comets.
        MainLog.Log("SuggestTarget: Selected",len(SuggestedTargets.SessionList),"potential targets.",terminal=False)
        print("Have selected",len(SuggestedTargets.SessionList),"potential targets.")
        # Save result.
        outputfile = FolderHandler.PrepFile('dataroot',"suggested_targets.json")
        SuggestedTargets.SaveAsJson(outputfile)
    else:
        print("Using previously calculated list...")
    
    # Now present the list of suggested targets, allow sorting and selection.
    # User selects a target by ID number in the display.
    SuggestedTargets.SortOptions = ['SearchTerm','Az','Alt','Magnitude','DiameterPixels']
    SuggestedTargets.SortChoice = 4 # Sort by size initially.
    SuggestedTargets.SortByField(SuggestedTargets.SortOptions[SuggestedTargets.SortChoice])
    
    obstarget = None # Selected target.

    # Display the list.
    while obstarget == None: # Repeat until a target is successfully chosen or the user quits.
        SuggestedTargets.DisplaySuggestionList()
        choice = input(textcolor.cyan("Enter row number, '@' to change sorting order, 'x' to quit: ")).lower() # Ask the user.
        if choice == '@': 
            SuggestedTargets.NextSortOption() # Change sort.
            continue # Redraw the list in the new sort sequence.
        if choice == 'x': # Quit.
            break # No choice made.
        if IsInt(choice): # Validate the choice.
            temp = int(choice)
            if temp < 0 or temp >= len(SuggestedTargets.SessionList):
                print(textcolor.red("Out of range (",0,"-",len(SuggestedTargets.SessionList) - 1,"). Try again."))
                continue
            se = SuggestedTargets.SessionList[temp] # Pull the suggested sessionentry instance.
            print("Selected row",temp,",",se.SearchGroup,se.SearchTerm) # Confirm the choice.
            # Use standard functions to formally select the chosen target.
            if se.SearchGroup == 'solar': obstarget = ChooseSolar(se.SearchTerm) # Create a solar system target.
            elif se.SearchGroup == 'satellite': obstarget = ChooseSatellite(se.SearchTerm) # Create a satellite target.
            elif se.SearchGroup == 'hipparcos': obstarget = ChooseHipparcos(se.SearchTerm) # Create a hipparcos star target.
            elif se.SearchGroup == 'messier': obstarget = ChooseMessier(se.SearchTerm) # Create a Messier object target.
            elif se.SearchGroup == 'radec': obstarget = RadecObject(se.SearchTerm) # Create an object from radec co-ordinates.
            elif se.SearchGroup == 'altaz': obstarget = AltazObject(se.SearchTerm) # Create an object from alt/az co-ordinates.
            elif se.SearchGroup == 'aurora': obstarget = ChooseAurora(se.SearchTerm) # Create an object from alt/az co-ordinates.
            elif se.SearchGroup == 'meteor': obstarget = ChooseMeteor(se.SearchTerm) # Create an object from meteor shower details.
            elif se.SearchGroup == 'comet': obstarget = ChooseComet(se.SearchTerm) # Create an object from comet details.
            elif se.SearchGroup == 'ngc': obstarget = ChooseNGC(se.SearchTerm) # Create an object from NGC details.
            else: 
                MainLog.Log("SuggestTarget: Unrecognised searchgroup: Line " + str(temp),level='error')
                continue
            break # We have a winner.
        print(textcolor.red("?",choice,"? Please try again."))

    return obstarget

# ------------------------------------------------------------------------------------------------------

def TargetSelection(optional=False):
    """ Submenu to allow target selection.
        Several different groups of target are available. 
        Select the group here, then pass control to a specific selection routine.
        optional: When True the user can exit and select No target. """
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
        'Aurora':                     {'label':'Aurora',                      'value':'AURORA'},
        'EarthSatellite':             {'label':'Space stations/satellites',   'value':'SATELLITE'},
        'RADEC':                      {'label':'RA-DEC co-ordinates',         'value':'RADEC'},
        'ALTAZ':                      {'label':'Fixed ALT-AZ point',          'value':'ALTAZ'},
        'Suggest':                    {'label':'Suggest target',              'value':'SUGGEST'},
        'ResetSuggestions':           {'label':'Reset suggestions',           'value':'RESET_SUGGEST'}
    }
    TargetMenu = optionmenu(TargetOptions,'Select target',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    while option is None:
        obstarget = None
        option, _ = TargetMenu.Prompt() # Ask the user to select an option from the menu.
        # option contains the selected target, or None.
        if optional and option == None: # User can quit the menu without selecting anything.
            return None # No choice made.
        if option is None: option = 'LAST' # If the user quit the menu without selecting anything, default to the last target.
        if option == "LAST": obstarget = ChooseLastTarget()
        elif option == "HISTORY": obstarget = ChooseHistory()
        elif option == "SOLAR": obstarget = ChooseSolar()
        elif option == "SATELLITE": obstarget = ChooseSatellite()
        elif option == "HIP": obstarget = ChooseHipparcos()
        elif option == "MESSIER": obstarget = ChooseMessier()
        elif option == "RADEC": obstarget = RadecObject()
        elif option == "METEOR": obstarget = ChooseMeteor()
        elif option == "COMET": obstarget = ChooseComet()
        elif option == "AURORA": obstarget = ChooseAurora()
        elif option == "ALTAZ": obstarget = AltazObject()
        elif option == "NGC": obstarget = ChooseNGC()
        elif option == "SUGGEST": obstarget = SuggestTarget()
        elif option == "RESET_SUGGEST": 
            SuggestedTargets.Reset()
            option = None
            continue
        else: option = None
        if obstarget != None and obstarget.Visible() == False: # Target was chosen, but is not currently visible.
            if option == "SATELLITE" or obstarget.Name in ['iss','css']: # RiseSet calc does not work for these yet.
                pass # Satellites don't matter, they may become visible very soon.
            else: # Other targets probably are not visible for some time, warn the user.
                az,alt = obstarget.AzAltDegrees() # Current az/alt of the target.
                ra,dec = obstarget.RaDecDegrees() # Current RA/DEC of the target.
                rh,rm,rs = AngleToHMS(ra) # Convert RA degrees into Hrs, Mins, Secs
                dd,dm,ds = AngleToDMS(dec) # Convert DEC degrees into Deg, Mins, Secs
                linelist = [obstarget.Name + " is not currently in range (" + AzAltText(az,alt,DegreeSymbol) + ").",
                            "RA: " + str(rh) + "h " + str(rm) + "' " + str(round(rs,3)) + '" ' + 
                            "Dec: " + str(dd) + DegreeSymbol + " " + str(dm) + "' " + str(round(ds,3)) + '"', 
                            RiseSetString(obstarget)]
                textcolor.TextBox(linelist,fg=textcolor.RED,bg=textcolor.BLACK)
                temp = AskYesNo(textcolor.cyan("Do you want to continue ?[y/N]"),False)
                if not temp: option = None # User wants to try a different target, ask the user again.
        if obstarget is None: option = None # No target selected, so ask the user again.
        if option is None: print(textcolor.red("No target selected: Please try again.")) # No success, so ask the user again.

    return obstarget

# ------------------------------------------------------------------------------------------------------

# User MUST select a target to proceed.
Session.Target = None # No target yet.
if ResumeObservation: # Try to resume with last known target.
    Session.Target = ChooseLastTarget()
if Session.Target is None: # Still no valid target. Ask the user.
    print(textcolor.yellow("You must select a target to start the program."))
    Session.Target = TargetSelection()
CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
# Create some other major objects to be included in the TargetChart window.
DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # # This assigns folder names for all the image types.

# ----------------------------------------------------------
# Menu options
# ----------------------------------------------------------

def HomePosition():
    """ Return the whole mechanism to its home position.
        If the Microcontroller resets at any time, this repeats until successful. """
    print (textcolor.yellow("HomePosition"))
    if Parameters.RequireRestart:
        RestartRequired()
        return
    
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
    if Parameters.RequireRestart: # Warn that movements cannot be made until software is restarted.
        RestartRequired()
        return
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
                if v != None: # Is it a valid float?
                    if v < i.MinAngle or v > i.MaxAngle: # It is out of range for the motor.
                        print ("Out of range. Try again.")
                        continue # Restart loop.
                    # Value is acceptable, let's move the motor.
                    a = v % 360 # Convert to the angle that the microcontroller will report.
                    if a != v:
                        print("NOTE: " + str(v) + DegreeSymbol + " = " + str(a) + DegreeSymbol)
                    i.MonitorMove = True
                    d = abs(a - i.CurrentAngle) # How far are we moving?
                    starttime = NowUTC() # When did the move start?
                    i.GoToAngle(a) # Set the new target position.
                    endtime = NowUTC() # When did the move complete?
                    i.MonitorMove = False
                    print("Moved",str(d) + DegreeSymbol,"in",(endtime - starttime).total_seconds(),"seconds.")
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

def ExerciseMotor(motor_name=None):
    print (textcolor.yellow("ExerciseMotor " + str(motor_name)+ "."))
    if Parameters.RequireRestart: # Warn that movements cannot be made until software is restarted.
        RestartRequired()
        return
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

# ------------------------------------------------------------------------------------------------------

def ExerciseMotorAzimuth(): # For menu
    ExerciseMotor('azimuth')
    
# ------------------------------------------------------------------------------------------------------

def ExerciseMotorAltitude(): # For menu
    ExerciseMotor('altitude')

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
    if Parameters.RequireRestart: # Warn that movements cannot be made until software is restarted.
        RestartRequired()
        return
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
            if i.MotorName == 'azimuth':
                print ("- Circumference of body circle is " + str(round(circumference,0)) + "mm.")
                print ("- 10mm of circumference movement is " + str(round(10 * fullrevsteps / circumference,0)) + "steps.")
            adj = None
            while adj != "x":
                adj = input(textcolor.cyan(motor_name.capitalize() + " steps to move (+/-), 'x' to exit : ")).strip().lower() # Python3
                if adj == "x":
                    break
                delta = TextToInt(adj)
                if delta is None:
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

def AskTrackingExposureTime(p):
    print (textcolor.yellow("SetTrackingExposureTime (Currently " + str(p)+ " seconds)."))
    v = input(textcolor.cyan("New tracking exposure time in seconds (or RETURN) : ")) # Python3
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
    MainLog.Log("SetTrackingExposureTime: Value=" + str(p) + " seconds.",terminal=False)
    return p

# ------------------------------------------------------------------------------------------------------

def AdjustTrackingExposureTime(factor=1.0): # Double exposure time.
    oldtime = Parameters.TrackingExposureSeconds
    newtime = round(min(SensorInUse.MaxExposureSeconds,oldtime * float(factor)),7)
    CamLog.Log("AdjustTrackingExposureTime(): From",oldtime,"s","to",newtime,"s",terminal=False)
    Parameters.TrackingExposureSeconds = newtime
    if factor >= 1.0:
        DriftWindow.Print(NowHMS() + " Increase exposure to " + str(Parameters.ExposureSeconds) + "s")
        DevWindow.Print(NowHMS() + " Increase exposure to " + str(Parameters.ExposureSeconds) + "s")
    else:
        DriftWindow.Print(NowHMS() + " Decrease exposure to " + str(Parameters.ExposureSeconds) + "s")
        DevWindow.Print(NowHMS() + " Decrease exposure to " + str(Parameters.ExposureSeconds) + "s")

# ------------------------------------------------------------------------------------------------------

def SetTrackingExposureTime(): # For menu
    Parameters.TrackingExposureSeconds = AskTrackingExposureTime(Parameters.TrackingExposureSeconds)

# ------------------------------------------------------------------------------------------------------

def AskExposureTime(p):
    print (textcolor.yellow("SetExposureTime (Currently " + str(p)+ " seconds)."))
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

def AdjustExposureTime(factor=1.0): # Double exposure time.
    oldtime = CameraInUse.ExposureSeconds
    newtime = round(min(SensorInUse.MaxExposureSeconds,oldtime * float(factor)),7)
    CamLog.Log("AdjustExposureTime(): From",oldtime,"s","to",newtime,"s",terminal=False)
    CameraInUse.ExposureSeconds = newtime
    DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
    DocumentSession()
    if factor >= 1.0:
        CameraWindow.Print(NowHMS() + " Increase exposure to " + str(CameraInUse.ExposureSeconds) + "s")
        DevWindow.Print(NowHMS() + " Increase exposure to " + str(CameraInUse.ExposureSeconds) + "s")
    else:
        CameraWindow.Print(NowHMS() + " Decrease exposure to " + str(CameraInUse.ExposureSeconds) + "s")
        DevWindow.Print(NowHMS() + " Decrease exposure to " + str(CameraInUse.ExposureSeconds) + "s")

# ------------------------------------------------------------------------------------------------------

def MenuSetExposureTime(): # For menu
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        CameraInUse.ExposureSeconds = AskExposureTime(CameraInUse.ExposureSeconds)
        DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
        DocumentSession()
        DriftTracker.Reset()

# ------------------------------------------------------------------------------------------------------

def SetCameraTimelapse(p):
    print (textcolor.yellow("SetTimelapse (Currently " + str(p)+ " seconds)."))
    print ("This is the number of seconds BETWEEN each LIGHT image captured.")
    print ("0 means there is no delay.")
    v = input(textcolor.cyan("New timelapse delay in seconds (or RETURN) : ")) # Python3
    if len(v) > 0: # Input given
        v = TextToFloat(v) # Convert to float or None.
        if v != None: # Can use the value.
            p = v
    if p == 0.0: p = None # 0 values stored as None, 'inactive'.
    if p < 0:
        print ("Timelapse delay cannot be negative.")
        p = CameraInUse.TimelapseSeconds
    MainLog.Log("SetTimelapse: Value=" + str(p) + " seconds.",terminal=True)
    return p

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

def DynamicStepScale(targetpix,pixelsperunit,unit='steps'):
    """ For MarkupPreview: Calculate an appropriate stepscale depending upon the movement mechanism resolution. 
    
        The Preview images show a scale indicating how far motor steps will move the camera relative to the image.
        Depending upon the gearing, motor and microstepping chosen this scale can be very variable. 
        - Some scales can be too large to help the user choose values.
        - Some scales can be too small to make out the scales at all.
        This function tries to find a scale that is readable on the image. Typically showing labels at least every 200pixels apart.
    
        targetpix = An initial target pixel gap between tick marks. 
        pixelsperunit = How many image pixels represent a single stepper motor step in the current arrangement. 

        Returns the number of motor steps to use between tickmarks.
        - The value is returned as semi-logarithmic to be useful to the users.
          It will be multiples of 1,2 or 5 at an appropriate power of 10.
            100,200,500,1000,2000,5000,10000,20000,50000,... etc
        """
    # *Q* Merge DynamicDegreeScale and DynamicStepScale functions into one.
    try:
        unitsperpixel = 1 / pixelsperunit # How many steps represent a single pixel?
    except:
        unitsperpixel = targetpix # If the above fails, use the target anyway.
    unitspertargetpixels = unitsperpixel * targetpix # How many steps represent the ideal tick mark gap?
    # Clean the steps to a rounded value (1,2,5,10,20,50,100,200,500,1000,2000,5000,10000,20000,50000,...)
    gaps = [100,200,500,1000,2000,5000,10000,20000,50000,100000] # These are acceptable gaps, they would make sense to a user.
    for gap in gaps:
        if unitspertargetpixels < gap:
            unitspertargetpixels = gap # Round up to nearest acceptable gap.
            break
    CamLog.Log("DynamicStepScale: tp",targetpix,"pps",pixelsperunit,"ip",unitsperpixel,"sptp",unitspertargetpixels,terminal=False)
    CamLog.Log("DynamicStepScale: For",unit,"labels to be at least",targetpix,"pixels apart, labels will be every",unitspertargetpixels,unit,terminal=False)
    CamLog.Log("DynamicStepScale: Labels will be every",int(pixelsperunit * unitspertargetpixels),"pixels",terminal=False)
    return int(unitspertargetpixels)

# ------------------------------------------------------------------------------------------------------

def DynamicDegreeScale(targetpix,pixelsperunit,unit='degrees'):
    """ For MarkupPreview: Calculate an appropriate stepscale depending upon the movement mechanism resolution. 
    
        The Preview images show a scale indicating degrees from the center of the image.
        This function tries to find a scale that is readable on the image. Typically showing labels at least every 200pixels apart.
    
        targetpix = An initial target pixel gap between tick marks. 
        pixelsperunit = How many image pixels represent a single degree in the image. 

        Returns the number of degree steps to use between tickmarks.
        - The value is returned as semi-logarithmic to be useful to the users.
          It will be multiples of 1,2 or 5 at an appropriate power of 10.
            1,2,5,10,20,50,100,200,500,1000,2000,5000,10000,20000,50000,... etc
        """
    # *Q* Merge DynamicDegreeScale and DynamicStepScale functions into one.
    try:
        unitsperpixel = 1 / pixelsperunit # How many steps represent a single pixel?
    except:
        unitsperpixel = targetpix # If the above fails, use the target anyway.
    unitspertargetpixels = unitsperpixel * targetpix # How many steps represent the ideal tick mark gap?
    # Clean the degrees to a rounded value (1,2,5,10,20,50,100,200,500,1000,2000,5000,10000,20000,50000,...)
    gaps = [1,2,5,10,20,50,100,200,500,1000,2000,5000,10000,20000,50000,100000] # These are acceptable gaps, they would make sense to a user.
    for gap in gaps:
        if unitspertargetpixels < gap:
            unitspertargetpixels = gap # Round up to nearest acceptable gap.
            break
    CamLog.Log("DynamicDegreeScale: tp",targetpix,"ppu",pixelsperunit,"upp",unitsperpixel,"uptp",unitspertargetpixels,terminal=False)
    CamLog.Log("DynamicDegreeScale: For",unit,"labels to be at least",targetpix,"pixels apart, labels will be every",unitspertargetpixels,unit,terminal=False)
    CamLog.Log("DynamicDegreeScale: Labels will be every",int(pixelsperunit * unitspertargetpixels),"pixels",terminal=False)
    return int(unitspertargetpixels)

# ------------------------------------------------------------------------------------------------------

def SplitText(inputline,separators=[' ']):
    """ Take a single line of text and split it into 2 lines. 
        inputline = Raw text to split. 
        separators = List of characters that the line can be split on. """
    linelist = []
    il_length = len(inputline) # How many characters do we have to split?
    midpoint = int(il_length/2) # Where's the approximate midpoint of the line?
    sep_locations = [] # Locations where separators exist in original line.
    for i,char in enumerate(inputline):
        if char in separators:
            sep_locations.append(i)
    # Which character is the closest to the midpoint?
    sep_location = il_length
    for i in sep_locations:
        if abs(i - midpoint) < abs(sep_location - midpoint): 
            sep_location = i # We've found a separator closer to the midpoint.
    if sep_location < il_length: # Split the line along the chosen separator. 
        linelist = [inputline[:sep_location],inputline[sep_location + 1:]]
    else:
        linelist = [inputline]
    return linelist

# ------------------------------------------------------------------------------------------------------

def MarkupPreview(drift_pixels_x=None,drift_pixels_y=None,astrotime=None,overlay=False,filename=None):
    """ Take the last image registered in CameraInUse.Image and mark up various alignment indicators and labels.
        OpenCV version of MarkupPreview. 
        astrotime = You can specify the date/time that the preview is calculated for.
        overlay = True: A 4 channel transparent image is created, can be used as an overlay. 
        filename = Override default filename with a specific value. """
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
    if overlay: # In overlay mode, create bgra image with all pixels transparent by default.
        NewImageBuffer.ChangeType('bgra') # Make sure it's a colour image.
        NewImageBuffer.FillColor((0,0,0,0)) # Set all pixels to transparent.
    else:
        NewImageBuffer.ChangeType('bgr') # Make sure it's a colour image. All pixels will default to BLACK.
    width = NewImageBuffer.GetWidth()
    height = NewImageBuffer.GetHeight()
    centrex = int(width / 2)
    centrey = int(height / 2)
    if filename == None: filename = FolderHandler.PrepFile('preview',"preview_" + UtcTimeStamp() + ".jpg")
    lineheight = 40 # Pixels high per line of text.
    ## Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - Parameters.TargetInclusionRadius
    MaxRADeg = CentreRa + Parameters.TargetInclusionRadius
    MinDecDeg = CentreDec - Parameters.TargetInclusionRadius
    MaxDecDeg = CentreDec + Parameters.TargetInclusionRadius
    QuickStarTime = Ts2Datetime(t)
    
    if True: # Alt/Az spherical grid.
        CamLog.Log("MarkupPreview: ShowGrid",terminal=False)
        linestep = 1 # Grid lines every 1 degree
        compasslabels = {0:'NORTH',45:'NORTH-EAST',90:'EAST',135:'SOUTH-EAST',180:'SOUTH',225:'SOUTH-WEST',270:'WEST',315:'NORTH-WEST'}
        for iAlt in range (-10,90,linestep):
            for iAz in range(0,360,linestep):
                # Is the point 'in front' or 'behind' the camera?
                rComp = CompoundRelativeAngle(to_alt=iAlt,to_az=iAz,from_alt=CentreAlt,from_az=CentreAz)
                if rComp > 80: continue # Don't plot the grid more than 80 degrees from the centre of the image. (Prevent wrap around artifacts for lines BEHIND the camera.)
                # Grid element is IN FRONT of the camera so we can plot it.
                
                # Draw 2 sides of the grid square. Neighbouring grid squares will complete the two missing sides.
                PlotAlt, PlotAz = RelativeAltAz(iAlt,iAz,CentreAlt,CentreAz) # Plot point relative to centre of image.
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
                        NewImageBuffer.AddText(label,x,y,color=pilomarimage.BGR('Black'),bgcolor=pilomarimage.BGR('Green'),size=2,thickness=2,border=10,vjust='c',hjust='c')

    if True: # Mark Right Ascension direction on the image.
        CamLog.Log("MarkupPreview: Show ra/dec grid.",terminal=False)
        # Given target RA/DEC values - establish points either side to show the plane of equal Right Ascension values.
        NewImageBuffer.SetPenColor(pilomarimage.BGR('LightBlue'))
        ra_unit = CameraInUse.Lens.FovVertical / 6 # Scale the size of the RA markers, keep centre clear but don't go off edge of image.
        RA_L1 = CentreRa - (2 * ra_unit) # 2 degrees behind the target.
        RA_L2 = CentreRa - ra_unit # 1 degrees behind the target.
        RA_L3 = CentreRa + ra_unit # 1 degrees ahead the target.
        RA_L4 = CentreRa + (2 * ra_unit) # 2 degrees ahead the target.
        AltL1,AzL1 = Session.Target.RaDecToAltAz(RA_L1,CentreDec,asdegrees=True) # Convert these location to Alt/Az positions.
        AltL2,AzL2 = Session.Target.RaDecToAltAz(RA_L2,CentreDec,asdegrees=True)
        AltL3,AzL3 = Session.Target.RaDecToAltAz(RA_L3,CentreDec,asdegrees=True)
        AltL4,AzL4 = Session.Target.RaDecToAltAz(RA_L4,CentreDec,asdegrees=True)
        PlotAlt1, PlotAz1 = RelativeAltAz(AltL1,AzL1,CentreAlt,CentreAz) # Convert the alt/az positions to be relative to the center of the image.
        PlotAlt2, PlotAz2 = RelativeAltAz(AltL2,AzL2,CentreAlt,CentreAz)
        PlotAlt3, PlotAz3 = RelativeAltAz(AltL3,AzL3,CentreAlt,CentreAz)
        PlotAlt4, PlotAz4 = RelativeAltAz(AltL4,AzL4,CentreAlt,CentreAz)
        XL1, YL1 = PlotRelativeAltAz(PlotAlt1,PlotAz1,height,width) # Convert the relative positions into pixel locations.
        XL2, YL2 = PlotRelativeAltAz(PlotAlt2,PlotAz2,height,width)
        XL3, YL3 = PlotRelativeAltAz(PlotAlt3,PlotAz3,height,width)
        XL4, YL4 = PlotRelativeAltAz(PlotAlt4,PlotAz4,height,width)
        NewImageBuffer.DrawEdgeLine((XL2,YL2),(XL1,YL1),edgecolor=pilomarimage.BGR('Black'),arrowpixels=20) # The -ve line ends with an arrow to show direction.
        NewImageBuffer.DrawEdgeLine((XL3,YL3),(XL4,YL4),edgecolor=pilomarimage.BGR('Black'),arrowpixels=20) # The +ve line ends with an arrow to show direction.
        if XL4 > XL3: # Add +ve and -ve labels at the ends of the lines.
            NewImageBuffer.AddEdgeText("RA+",XL4 + 10,YL4,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c')
            NewImageBuffer.AddEdgeText("RA-",XL1 - 10,YL1,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c',hjust='r')
        else: 
            NewImageBuffer.AddEdgeText("RA+",XL4 - 10,YL4,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c',hjust='r')
            NewImageBuffer.AddEdgeText("RA-",XL1 + 10,YL1,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c')
        DEC_L1 = CentreDec - (2 * ra_unit) # 2 degrees below the target.
        DEC_L2 = CentreDec - ra_unit # 1 degrees below the target.
        DEC_L3 = CentreDec + ra_unit # 1 degrees above the target.
        DEC_L4 = CentreDec + (2 * ra_unit) # 2 degrees above the target.
        AltL1,AzL1 = Session.Target.RaDecToAltAz(CentreRa,DEC_L1,asdegrees=True) # Convert these location to Alt/Az positions.
        AltL2,AzL2 = Session.Target.RaDecToAltAz(CentreRa,DEC_L2,asdegrees=True)
        AltL3,AzL3 = Session.Target.RaDecToAltAz(CentreRa,DEC_L3,asdegrees=True)
        AltL4,AzL4 = Session.Target.RaDecToAltAz(CentreRa,DEC_L4,asdegrees=True)
        PlotAlt1, PlotAz1 = RelativeAltAz(AltL1,AzL1,CentreAlt,CentreAz) # Convert the alt/az positions to be relative to the center of the image.
        PlotAlt2, PlotAz2 = RelativeAltAz(AltL2,AzL2,CentreAlt,CentreAz)
        PlotAlt3, PlotAz3 = RelativeAltAz(AltL3,AzL3,CentreAlt,CentreAz)
        PlotAlt4, PlotAz4 = RelativeAltAz(AltL4,AzL4,CentreAlt,CentreAz)
        XL1, YL1 = PlotRelativeAltAz(PlotAlt1,PlotAz1,height,width) # Convert the relative positions into pixel locations.
        XL2, YL2 = PlotRelativeAltAz(PlotAlt2,PlotAz2,height,width)
        XL3, YL3 = PlotRelativeAltAz(PlotAlt3,PlotAz3,height,width)
        XL4, YL4 = PlotRelativeAltAz(PlotAlt4,PlotAz4,height,width)
        NewImageBuffer.DrawEdgeLine((XL2,YL2),(XL1,YL1),edgecolor=pilomarimage.BGR('Black'),arrowpixels=20) # The -ve line ends with an arrow to show direction.
        NewImageBuffer.DrawEdgeLine((XL3,YL3),(XL4,YL4),edgecolor=pilomarimage.BGR('Black'),arrowpixels=20) # The +ve line ends with an arrow to show direction.
        if XL4 > XL3: # Add +ve and -ve labels at the ends of the lines.
            NewImageBuffer.AddEdgeText("Dec+",XL4 + 10,YL4,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c')
            NewImageBuffer.AddEdgeText("Dec-",XL1 - 10,YL1,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c',hjust='r')
        else: 
            NewImageBuffer.AddEdgeText("Dec+",XL4 - 10,YL4,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c',hjust='r')
            NewImageBuffer.AddEdgeText("Dec-",XL1 + 10,YL1,thickness=2,edgecolor=pilomarimage.BGR('Black'),vjust='c')

    if True: # Draw arcs to show field rotation over differing timescales.
        # To do this, choose another point in the sky slightly offset from the target.
        # Then estimate how this point rotates around the target as the sky/telescope moves.
        CamLog.Log("MarkupPreview: FieldRotation.",terminal=False)
        xpos = int(width/2)
        ypos = int(height/2)
        gap = 60
        NewImageBuffer.SetPenColor(pilomarimage.BGR('HotPink'))
        for i,span in enumerate([3600,1800,CameraInUse.ExposureSeconds]): # List of exposure times, including the selected exposure time.
            rotation = Session.Target.RotationArc(span=span) # Calculate field rotation angle over the chosen timespan.
            CamLog.Log("MarkupPreview: Calculated rotation",span,rotation,DegreeSymbol,terminal=False)
            if rotation > 0: 
                textpos = xpos - 10 # To left of vertical axis.
                hjust = 'r' # Justify right.
            else: 
                hjust = 'l' # Justify left.
                textpos = xpos + 10 # To right of vertical axis.
            CamLog.Log("MarkupPreview: Calculated rotation",span,rotation,DegreeSymbol,"label justification",hjust,terminal=False)
            r = (i + 10) * gap # How far down the 'y' axis do we draw this arc?
            # Put label left or right of the arc depending upon which way it is moving.
            if i == 0: # Print header above first instance.
                NewImageBuffer.AddEdgeText("Field rotation",textpos,ypos + (9 * gap),color=pilomarimage.BGR('HotPink'),edgecolor=pilomarimage.BGR('Black'),hjust=hjust,bgcolor=pilomarimage.BGR('Black')) # Explain and demonstrate the field rotation that the telescope is currently experiencing.
            NewImageBuffer.AddEdgeText(HRSeconds(span) + " is " + str(round(rotation,2)) + "deg",textpos,ypos + r,color=pilomarimage.BGR('HotPink'),edgecolor=pilomarimage.BGR('Black'),hjust=hjust,vjust='c',bgcolor=pilomarimage.BGR('Black')) # Show rotation value.
            if abs(rotation) > 180: # Too big to be useful  
                NewImageBuffer.AddEdgeText(Deg3dp(rotation),textpos,ypos + r,color=pilomarimage.BGR('HotPink'),edgecolor=pilomarimage.BGR('Black'),hjust=hjust,bgcolor=pilomarimage.BGR('Black')) # Explain and demonstrate the field rotation that the telescope is currently experiencing.
            elif abs(rotation) > 0.1: # Big enough for an arc to appear.
                NewImageBuffer.DrawEdgeEllipse(xpos,ypos,r,r,90,0                    ,rotation * -1,thickness=3,edgecolor=pilomarimage.BGR('Black')) # Draw arc representing the rotation.
            else: # Too short for an arc to appear. Draw a dot instead.
                NewImageBuffer.DrawEdgeCircle(xpos,ypos + r,1,thickness=2,edgecolor=pilomarimage.BGR('Black')) # Draw dot representing insignificant rotation.

    if True: # Parameters.MarkupShowCrosshairs: # Target cross hairs
        CamLog.Log("MarkupPreview: ShowCrosshairs",terminal=False)
        # Draw cross hairs. Gap in the centre so that target is still visible.
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Yellow'))
        NewImageBuffer.DrawLine((int(width/2),     0),            (int(width/2),        int(height/2 - 20)))
        NewImageBuffer.DrawLine((int(width/2),     height),       (int(width/2),        int(height/2 + 20)))
        NewImageBuffer.DrawLine((0,                int(height/2)),(int(width/2 - 20),   int(height/2))     )
        NewImageBuffer.DrawLine((int(width/2) + 20,int(height/2)),(width,int(height/2))                    )

    if True: # Parameters.MarkupShowDegreeScale: # Mark DEGREE scale. This is degrees movement of the camera, NOT degrees in the sky!
        CamLog.Log("MarkupPreview: ShowDegreeScale",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Yellow'))
        c = 0 # Counter used to stagger the text to reduce overlapping.
        MajorDegreeSteps = DynamicDegreeScale(targetpix=200,pixelsperunit=CameraInUse.PixelsPerFovDegreeHeight,unit='degrees')
        # Calibration - Azimuth
        for i in range(MajorDegreeSteps, MajorDegreeSteps * 6,MajorDegreeSteps):
            for mult in [-1,1]: # Mark +ve and -ve side of scale.
                im = i * mult
                c = 1 - c
                xpos = int(width/2) + (im * CameraInUse.PixelsPerFovDegreeWidth) # 1 degree markers
                ypos = int(height/2)
                text = str(im) + "deg" # DegreeSymbol
                if im > 0: text = "+" + text
                NewImageBuffer.DrawLine((xpos,ypos - 100),(xpos,ypos))
                NewImageBuffer.AddText(text,xpos,ypos - 100 + (c * 25),hjust='c',vjust='t') 
        # Calibration - Altitude
        for i in range(MajorDegreeSteps, MajorDegreeSteps * 6,MajorDegreeSteps):
            for mult in [-1,1]: # Mark +ve and -ve side of scale.
                im = i * mult
                xpos = int(width/2) 
                ypos = int(height/2) + (im * CameraInUse.PixelsPerFovDegreeHeight) # 1 degree markers
                NewImageBuffer.DrawLine((xpos - 100,ypos),(xpos,ypos))
                text = str(im * -1) + "deg" # DegreeSymbol - Invert scale because image Y positions are inverted.
                if im < 0: text = "+" + text
                NewImageBuffer.AddText(text,xpos - 100,ypos,vjust='c',hjust='r') 

    if True: # Parameters.MarkupShowFullStepScale: # Mark FULL STEP scale.
        CamLog.Log("MarkupPreview: azpx/step",az_pixels_per_fullstep,"altpx/step",alt_pixels_per_fullstep,"HFOV",LensInUse.FovHorizontal,"VFOV",LensInUse.FovVertical,"Wpx",width,"Hpx",height,terminal=False)
        # Calibration - Azimuth
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Cyan'))
        c = 0 # Counter used to stagger the text to reduce overlapping.
        MajorTickSteps = DynamicStepScale(targetpix=200,pixelsperunit=az_pixels_per_fullstep,unit='steps')
        for i in range(int(-10 * MajorTickSteps),int(10 * MajorTickSteps + 1),MajorTickSteps): # Major tick marks only.
            c = 1 - c
            xpos = int((width/2) + (i * az_pixels_per_fullstep))
            ypos = int(height/2)
            NewImageBuffer.DrawLine((xpos,ypos),(xpos,ypos + 100),thickness=3)
            text = str(i) + "Steps"
            if i > 0: text = "+" + text
            NewImageBuffer.AddText(text,xpos,ypos + 110 + (c * 25),size=1.0,hjust='c',vjust='b') # Offset alternate markings to keep legible.
        # Calibration - Altitude
        MajorTickSteps = DynamicStepScale(targetpix=200,pixelsperunit=alt_pixels_per_fullstep,unit='steps')
        for i in range(int(-10 * MajorTickSteps),int(10 * MajorTickSteps + 1),MajorTickSteps): # Major tick marks only.
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
            NewImageBuffer.DrawCircle(xpos,ypos,int(az_pixels_per_fullstep),color=pilomarimage.BGR('Gold'),thickness=3)
            NewImageBuffer.DrawCircle(xpos,ypos,int(az_pixels_per_fullstep),color=pilomarimage.BGR('Black'))

    if True: # Draw angular scale for reference.
        ScaleList = [['10deg',   10.0, 0.0, 0.0],
                     ['5deg',     5.0, 0.0, 0.0],
                     ['2deg',     2.0, 0.0, 0.0],
                     ['1deg',     1.0, 0.0, 0.0],
                     ['30arcmin', 0.0,30.0, 0.0],
                     ['10arcmin', 0.0,10.0, 0.0],
                     ['1arcmin',  0.0, 1.0, 0.0],
                     ['30arcsec', 0.0, 0.0,30.0],
                     ['10arcsec', 0.0, 0.0,10.0]]
        NewImageBuffer.SetPenColor(pilomarimage.BGR('White'))
        x = 200
        y = int(height / 2) + 200
        NewImageBuffer.AddEdgeText("Angular scale",x,y,size=0.5,edgecolor=pilomarimage.BGR('Black'))
        for i,scale in enumerate(ScaleList):
            label = scale[0]
            d = float(scale[1]) + (scale[2] / 60) + (scale[3] / (60 ** 2)) # Convert DMS into float degrees.
            p = int(d * CameraInUse.PixelsPerFovDegreeWidth)
            if p > (width / 3) or p < 20: continue # Line is too short or long to be useful.
            y += 20
            NewImageBuffer.AddEdgeText(label,x,y,size=0.5,hjust='r',vjust='c',edgecolor=pilomarimage.BGR('Black'))
            NewImageBuffer.DrawLine((x + 10,y),(x + 10 + p,y),thickness=3)
            NewImageBuffer.DrawLine((x + 10,y - 10),(x + 10,y + 10),thickness=1)
            NewImageBuffer.DrawLine((x + 10 + p,y - 10),(x + 10 + p,y + 10),thickness=1)
            MainLog.Log("MarkupPreview:Image scale:",label,"(",scale[1],":",scale[2],":",scale[3],"d:m:s)","=",d,"deg","=",p,"pixels",terminal=False)

    if True: # Parameters.MarkupShowMessier: # Mark neighbouring Messier objects ....
        CamLog.Log("MarkupPreview: ShowMessier",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Green'))
        # Find that alt/az locations of all the objects.
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            TempStarRA = TempStarParms['radeg']
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempStarDec = TempStarParms['decdeg']
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Width given in arcminutes.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz(TempStarRA,TempStarDec,time=t,asdegrees=True)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            if TempStarAz < 0: # Below horizon, don't mark it up.
                continue # Skip to next object.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempTextX = TempStarX + TempStarWidth + 5 # Put Messier labels on the RIGHT of the object so they don't clash with NGC labels for the same thing.
            NewImageBuffer.DrawEllipse(TempStarX,TempStarY,int(TempStarWidth),int(TempStarHeight),0,0,360)
            #if Parameters.MarkupShowLabels:
            if Parameters.MarkupShowCoordinates:
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                NewImageBuffer.AddText(text,TempTextX,TempStarY + lineheight,size=0.5)
                text = "RA:" + TempStarParms['ralabel'] + " Dec:" + TempStarParms['declabel']
                NewImageBuffer.AddText(text,TempTextX,NewImageBuffer.NextTextY,size=0.5)
            if Parameters.MarkupShowNames and TempStarName != None:
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
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarName = TempStarParms['name']
            CamLog.Log("MarkupPreview: NGCItems: Considering:",i,TempStarName,terminal=False)
            if TempStarName.startswith('pgc') and not Parameters.ShowPGCEntries: 
                CamLog.Log("MarkupPreview: NGCItems: Not showing PGC entries.",terminal=False)
                continue # Don't process all the PGC entries, it's REALLY slow.
            if TempStarName.lower().startswith('pgc'): NewImageBuffer.SetPenColor(pilomarimage.BGR('DarkBlue'))
            elif TempStarName.lower().startswith('ic'): NewImageBuffer.SetPenColor(pilomarimage.BGR('Blue'))
            else: NewImageBuffer.SetPenColor(pilomarimage.BGR('LightBlue'))
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from arcseconds to degrees & radius.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            if TempStarName.lower().startswith('pgc'): 
                CamLog.Log("MarkupPreview: NGCItems: Considering",TempStarName,"w",TempStarWidth,"h",TempStarHeight,terminal=False)
            if TempStarWidth < 1 and TempStarHeight < 1: 
                CamLog.Log("MarkupPreview: NGCItems: Object too small.",terminal=False)
                continue # Too small to display.
            try: # Earlier versions of the data file may not have this column.
                TempStarName2 = TempStarParms['knownas']
            except:
                TempStarName2 = '' # Field not available in this data set.
            try: # Earlier versions of the data file may not have this column.
                NGCType = TempStarParms['typelabel']
            except:
                NGCType = TempStarParms['type']
            CamLog.Log("MarkupPreview: NGCItems: Creating TempStar instance.",terminal=False)
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarDec = TempStarParms['ded'] + TempStarParms['dem'] / 60 + TempStarParms['des'] / 3600
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz([TempStarParms['rah'],TempStarParms['ram'],TempStarParms['ras']],TempStarDec,time=t,asdegrees=False)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            if TempStarAz < 0: # Below horizon, don't mark it up.
                CamLog.Log("MarkupPreview: NGCItems: Object below horizon.",terminal=False)
                continue # Skip to next object.
            CamLog.Log("MarkupPreview: NGCItems: Plotting",TempStarName,terminal=False)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            NewImageBuffer.DrawEllipse(TempStarX,TempStarY, int(TempStarWidth),int(TempStarHeight), angle=0, startAngle=0, endAngle=360)
            CamLog.Log("MarkupPreview: NGCItems: Processing entry",i,TempStarName,TempStarName2,";",TempStarWidth,"*",TempStarHeight,";",TempStarX,",",TempStarY,terminal=False)
            if not TempStarName.startswith('pgc'): # Don't label PGC entries, there are too many.
                TempTextX = TempStarX - TempStarWidth - 5 # Put NGC labels on the LEFT of the object so they don't clash with any matching Messier label for the same thing.
                if Parameters.MarkupShowCoordinates:
                    text = AzAltText(TempStarAz,TempStarAlt,'deg')
                    NewImageBuffer.AddText(text,TempTextX,TempStarY + lineheight,size=0.5,hjust='r')
                    text = "RA:" + TempStarParms['ralabel'] + " Dec:" + TempStarParms['declabel']
                    NewImageBuffer.AddText(text,TempTextX,NewImageBuffer.NextTextY,size=0.5,hjust='r')
                    if NGCType != None: # Describe the object type.
                        NewImageBuffer.AddText(NGCType.title(),TempTextX,NewImageBuffer.NextTextY,size=0.5,hjust='r')
                if Parameters.MarkupShowNames:
                    if TempStarName != None: # Name - ie NGCxxx
                        NewImageBuffer.AddText(TempStarName.upper(),TempTextX,TempStarY -30,size=1,hjust='r')
                    if TempStarName2 != None: # Known as - ie Whirlpool Galaxy
                        NewImageBuffer.AddText(TempStarName2.title(),TempTextX,NewImageBuffer.NextTextY,size=1,hjust='r')
        CamLog.Log("MarkupPreview: NGCItems: Plot NGC objects end. (",len(tempdf),"/",len(NGC_DF),"objects selected)",terminal=False)
    
    
    if True: # Parameters.MarkupShowStars: # Mark neighbouring stars.
        CamLog.Log("MarkupPreview: ShowStars",terminal=False)
        NewImageBuffer.AvoidTextCollisions = Parameters.MarkupAvoidCollisions # Do we allow star labels to overlap?
        # Mark neighbouring stars on the picture too. This will help with alignment.
        # Select a subset of the Hipparcos catalog which is within 10Deg of the target (=centre of image)
        CamLog.Log("MarkupPreview: SelectStars start",terminal=False)
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        NeighbouringStarCount = len(NeighbouringStars)
        CamLog.Log("MarkupPreview: NeighbouringStars contains",NeighbouringStarCount,"entries.",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('PaleGreen'))
        # Now convert this list of ra/dec locations into alt/az positions for plotting on the preview image.
        PlottedStarCount = 0 # How many stars have been plotted? We don't want to swamp the display.
        for i in range(NeighbouringStarCount):
            if i % 400 == 0:
                CamLog.Log("MarkupPreview: ShowStars. Processing star",i,terminal=False)
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe, probably makes a COPY, not a pointer to the original row.
            TempStarName = TempStarRec['label']
            TempStarCommonName = TempStarRec['starname']
            # Calculate the location in the preview image.
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz(TempStarRec['ra_degrees'],TempStarRec['dec_degrees'],time=t,asdegrees=True)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            if NewImageBuffer.OutOfBounds(TempStarX,TempStarY): continue # This star is off the edge of the image, skip it.
            # We're going to plot this one.
            PlottedStarCount += 1
            TempStarWidth = int(TempStarRec['markupradius'])
            NewImageBuffer.DrawCircle(TempStarX,TempStarY,TempStarWidth,thickness=1) # cyan # circle where the star is.
            labelx = TempStarX + TempStarWidth + 5 # X location of labels.
            if Parameters.MarkupShowNames:
                try:
                    TempStarConstellation = TempStarRec['constellation'].title() # Capitalise 1st letter of each word.
                except:
                    TempStarConstellation = ''
                if TempStarConstellation != '' and TempStarConstellation != None:
                    TempStarCommonName += " (" + TempStarConstellation + ")"
                NewImageBuffer.AddText(TempStarRec['label'],labelx,TempStarY -20) # Hipparcos ID
                if len(TempStarCommonName) > 0: # Add star name.
                    NewImageBuffer.AddText(TempStarCommonName.title(),labelx,NewImageBuffer.NextTextY,thickness=2,size=1) 
            if Parameters.MarkupShowCoordinates: # Show position labels. Alt/Az and Ra/Dec
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                NewImageBuffer.AddText(text,labelx,NewImageBuffer.NextTextY,size=0.5) 
                text = "RA: " + TempStarRec['ralabel'] + " Dec:" + TempStarRec['declabel']
                NewImageBuffer.AddText(text,labelx,NewImageBuffer.NextTextY,size=0.5) 
                text = "Magnitude: " + str(TempStarRec['magnitude'])
                NewImageBuffer.AddText(text,labelx,NewImageBuffer.NextTextY,size=0.5) 
            if PlottedStarCount >= Parameters.MarkupStarLabelLimit: # We're plotted enough, don't swamp the image.
                CamLog.Log("MarkupPreview: ShowStars: Plotted maximum",PlottedStarCount,"star labels.",terminal=False)
                break
        NewImageBuffer.AvoidTextCollisions = False # Turn off the label collision protection.

    #hsat = HomeSite.at(t)
    if True: #Parameters.MarkupConstellations: # Mark constellation patterns... # Workaround for post skyfield 1.39. Fault not fully understood yet.
        CamLog.Log("MarkupPreview: ShowConstellations POST OCT.2023 version. Post Skyfield 1.39 etc.",terminal=False)
        rad = 10 # 10 pixel gap between line and star.
        cclist = {} # We place the name of the constellation in the middle of the visible stars. This list builds up where those locations are.
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Red'))
        ConstellationsDf = ConstellationStars.Get(CentreRa,CentreDec)
        CamLog.Log("MarkupPreview: ShowConstellations: Columns available:",list(ConstellationsDf.columns),terminal=False)
        linkcount = 0
        successcount = 0
        for entryfrom, entryto, entryname in ConstellationLinks:
            linkcount += 1
            if int(entryfrom) in ConstellationsDf.index and int(entryto) in ConstellationsDf.index: 
                #CamLog.Log("MarkupPreview: ShowConstellations: from",int(entryfrom),"to",int(entryto),terminal=False)
                try:
                    FromRec = ConstellationsDf.loc[int(entryfrom)] # See how many records are returned. Expect 1: 15.10.2023
                    ToRec = ConstellationsDf.loc[int(entryto)] # See how many records are returned. Expect 1: 15.10.2023
                except Exception as e:
                    CamLog.Log("MarkupPreview:MarkConstellations: Failed: Skipping FromStar",entryfrom,"ToStar",entryto,terminal=False)
                    CamLog.Log("MarkupPreview:MarkConstellations: Error:",e,terminal=False)
                    continue
                successcount += 1
                FromAlt, FromAz = Session.Target.RaDecToAltAz(FromRec['ra_degrees'],FromRec['dec_degrees'],time=t,asdegrees=True)
                PlotFromAlt, PlotFromAz = RelativeAltAz(FromAlt,FromAz,CentreAlt,CentreAz)
                fromx, fromy = PlotRelativeAltAz(PlotFromAlt,PlotFromAz,height,width)
                ToAlt, ToAz = Session.Target.RaDecToAltAz(ToRec['ra_degrees'],ToRec['dec_degrees'],time=t,asdegrees=True)
                PlotToAlt, PlotToAz = RelativeAltAz(ToAlt,ToAz,CentreAlt,CentreAz)
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
                    CamLog.Log("MarkupPreview: ShowConstellations: Too close to plot",entryfrom,"(",fromx,",",fromy," ) to",entryto,"(",tox,",",toy," ).",terminal=False)
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
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Gold'))
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
            if Parameters.MarkupShowCoordinates:
                text = AzAltText(TempStarAz,TempStarAlt,'deg')
                NewImageBuffer.AddText(text,TempStarX + TempStarWidth + 5,TempStarY + 40)
                text = RaDecText(TempStarRA,TempStarDec,'deg')
                NewImageBuffer.AddText(text,TempStarX + TempStarWidth + 5,NewImageBuffer.NextTextY)
            if Parameters.MarkupShowNames and TempStarName != None:
                NewImageBuffer.AddText(TempStarName.split()[0].title(),TempStarX + TempStarWidth + 5,TempStarY -20) 
        
    if False: # Parameters.MarkupShowRegistration: # Reference marks on preview image...
        CamLog.Log("MarkupPreview: ShowRegistration",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Red'))
        NewImageBuffer.DrawLine((10,10),(100,10),thickness=3) # Red
        NewImageBuffer.DrawLine((10,10),(10,100),thickness=3) # Red
        text = "(10,10)"
        NewImageBuffer.AddText(text,40, 60,color=pilomarimage.BGR('Red')) # red
        
    if True: # Parameters.MarkupShowDrift: # Mark last measured DRIFT indicator.
        CamLog.Log("MarkupPreview: ShowDrift:",drift_pixels_x,",",drift_pixels_y,terminal=False)
        if drift_pixels_x != None and drift_pixels_y != None:
            text = "Drift: " + str(drift_pixels_x) + "," + str(drift_pixels_y) + " pixels"
            NewImageBuffer.DrawEdgeLine((int(width/2),int(height/2)),(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y)),color=pilomarimage.BGR('Red'),edgecolor=pilomarimage.BGR('Black')) # Black outline showing last measured drift.
            NewImageBuffer.DrawCircle(int(width/2) + int(drift_pixels_x),int(height/2) + int(drift_pixels_y),10,color=pilomarimage.BGR('Red')) # Black outline showing last measured drift.
            NewImageBuffer.AddEdgeText(text,int(width/2) + int(drift_pixels_x) + 10,int(height/2) + int(drift_pixels_y) + 10,color=pilomarimage.BGR('Red'),edgecolor=pilomarimage.BGR('Black'),thickness=2,edgethickness=2) # Red line
        else:
            NewImageBuffer.AddEdgeText("NO DRIFT AVAILABLE",int(width/2) + 150,int(height/2) + 150,color=pilomarimage.BGR('Red'),edgecolor=pilomarimage.BGR('Black'),thickness=2,edgethickness=2) # Red line

    if True: # Parameters.MarkupShowCurrentPosition: # Show current position. 
        CamLog.Log("MarkupPreview: CurrentPosition",terminal=False)
        cRa ,cDec = Session.Target.RaDecHours() # Calculations for target from observer's location. Returns HMS and Degree values.
        # Timestamp bottom center.
        xpos = int(width / 2)
        ypos = int(height - 70)
        text = str(CameraInUse.LastImageDateTime)
        NewImageBuffer.AddText(text,xpos,ypos,size=2.0,color=pilomarimage.BGR('White'),bgcolor=pilomarimage.BGR('Black'),hjust='c')
        # Filename in bottom left corner.
        xpos = int(10)
        ypos = int(height - 10)
        text = "File: " + filename
        NewImageBuffer.AddText(text,xpos,ypos,color=pilomarimage.BGR('White'),bgcolor=pilomarimage.BGR('Black'))
        # Program ID in bottom right corner.
        xpos = int(width - 10)
        ypos = int(height - 10)
        text = ProgramTitle + " " + VERSION + " on " + str(os.uname().nodename)
        NewImageBuffer.AddText(text,xpos,ypos,color=pilomarimage.BGR('White'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
        # Camera options in top center, split into 2 lines if it's really long.
        xpos = int(width / 2)
        ypos = int(40)
        text = "Camera options: " + str(CameraInUse.LastLightCommand)
        textlines = SplitText(text) # Split into 2 lines.
        NewImageBuffer.AddText(textlines[0],xpos,ypos,color=pilomarimage.BGR('Yellow'),bgcolor=pilomarimage.BGR('Black'),hjust='c')
        if len(textlines) > 1: # There's a 2nd line.
            NewImageBuffer.AddText(textlines[1],xpos,NewImageBuffer.NextTextY,color=pilomarimage.BGR('Yellow'),bgcolor=pilomarimage.BGR('Black'),hjust='c')
        # Key in top right corner.
        xpos = width - 50
        ypos = 50
        NewImageBuffer.AddText("KEY",xpos,ypos,color=pilomarimage.BGR('White'),hjust='r',bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Hipparcos O",xpos,NewImageBuffer.NextTextY,color=pilomarimage.BGR('PaleGreen'),hjust='r',bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Messier O",xpos,NewImageBuffer.NextTextY,color=pilomarimage.BGR('Green'),hjust='r',bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("NGC O",xpos,NewImageBuffer.NextTextY,color=pilomarimage.BGR('LightBlue'),hjust='r',bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Planet O",xpos,NewImageBuffer.NextTextY,color=pilomarimage.BGR('Gold'),hjust='r',bgcolor=pilomarimage.BGR('Black'))
        NewImageBuffer.AddText("Constellation -",xpos,NewImageBuffer.NextTextY,color=pilomarimage.BGR('Red'),hjust='r',bgcolor=pilomarimage.BGR('Black'))
        # More detail in bottom right corner. 
        xpos = int(width - 50)
        ypos = int(height - 100)
        NewImageBuffer.PrevTextY = ypos # Initialize line pointer for a text block.
        for i in MotorControls:
            text = "Motor: " + i.MotorName + " "
            text += Deg3dp(i.CurrentAngle) + "deg, " # DegreeSymbol 
            text += "position " + str(i.AngleToStep(i.CurrentAngle)) + " of " + str(i.AxisStepsPerRev)
            NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('LimeGreen'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
        text = "Marking objects above magnitude " + str(round(Parameters.TargetMinMagnitude,1)) # Object magnitude filter.
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('Gold'),bgcolor=pilomarimage.BGR('Black'),hjust='r') 
        # Astro location.
        if Session.Target.ObjectType != 'meteor': # *Q* This doesn't work for meteor shower observations, so don't show it until fixed. 
            text = AzAltText(CentreAz, CentreAlt,'deg')
            NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('HotPink'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
            text = "RA: " + str(cRa) + " Dec: " + str(cDec)
            NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('HotPink'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
        # Lens characteristics
        text = "FOV: " + Deg3dp(LensInUse.FovHorizontal) + "deg * " + Deg3dp(LensInUse.FovVertical) + "deg" # DegreeSymbol
        text += " (" + str(LensInUse.Length) + "mm)"
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('Gold'),bgcolor=pilomarimage.BGR('Black'),hjust='r') 
        # Exposure details
        NewImageBuffer.AddText("Exposure: " + str(CameraInUse.ExposureSeconds) + " seconds.",xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('Gold'),bgcolor=pilomarimage.BGR('Black'),hjust='r') 
        # Photo capture time.
        NewImageBuffer.AddText("Captured: " + str(CameraInUse.LastImageDateTime),xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('Gold'),bgcolor=pilomarimage.BGR('Black'),hjust='r') 
        if CameraInUse.CaptureStart > CameraInUse.CaptureEnd: # *Q* Timestamp range is sometimes invalid. Needs investigating.
            CamLog.Log("MarkupPreview: Capture timestamps invalid:",str(CameraInUse.CaptureStart),"-",str(CameraInUse.CaptureEnd),level='warning',terminal=False)
        text = "ImageCaptureEnd: " + str(CameraInUse.CaptureEnd)
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('Cyan'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
        text = "Markup time: " + str(Ts2Datetime(t))
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('Orange'),bgcolor=pilomarimage.BGR('Black'),hjust='r')
        text = "Target: " + Session.Target.Name # Target
        if Session.Target.Magnitude != None: # Magnitude of the target.
            text += " (mag. " + str(round(Session.Target.Magnitude,1)) + ")"
        NewImageBuffer.AddText(text,xpos,NewImageBuffer.PrevTextY,color=pilomarimage.BGR('White'),thickness=2,bgcolor=pilomarimage.BGR('Black'),hjust='r') 

    if True: # Parameters.MarkupSaveDraft:
        CamLog.Log("MarkupPreview: SaveDraft",filename,terminal=False)
        CameraWindow.Print(NowHMS() + " " + filename.split('/')[-1]) # Show the preview filename that's being generated.
        NewImageBuffer.SaveFile(filename)
        CameraInUse.Previewjpg = filename # Record the filename so that the web interface can access it.

    CamLog.Log("MarkupPreview: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("MarkupPreview: End",terminal=False)
    return True

def TuningOverlay(astrotime=None,filename=None,maxstars=20):
    """ Create a simplified tuning overlay image.
        astrotime = You can specify the date/time that the preview is calculated for.
        filename = Override default filename with a specific value.
        maxstars = Maximum number of stars (brightest first) to mark. """
    CamLog.Log("TuningOverlay: Start(",astrotime,")",terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime != None: # Calculate for a specific timestamp.
        t = astrotime
    else: 
        t = SkyfieldNow() # Current timestamp in 'astro' time. If there's a delay then there may be some mismatch in placing objects. # Offset supported.
    CamLog.Log("TuningOverlay: MarkupTime:",Ts2Datetime(t),terminal=False)
    CamLog.Log("TuningOverlay: CameraInUse.CaptureStart:",CameraInUse.CaptureStart,terminal=False)
    CamLog.Log("TuningOverlay: CameraInUse.CaptureEnd:",CameraInUse.CaptureEnd,terminal=False)
    # The time should be the time of the actual photo! If several seconds have passed, then things will already have drifted!
    if Parameters.UseLiveLocation: # Use the live target location rather than the last reported camera position for image processing.
        CentreAz, CentreAlt = Session.Target.AzAltDegrees() # What is the alt/az location of the centre of the image?
    else: # Use the last reported camera position. Deprecated.
        CentreAlt, CentreAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
    CentreRa, CentreDec = Session.Target.RaDecDegrees() # Calculations for target from observer's location. Returns decimal degree values. *Q* Does this ever vary with time?
    CamLog.Log("TuningOverlay: Centre coordinates: alt/az:",CentreAlt,"/",CentreAz,"ra/dec:",CentreRa,CentreDec,terminal=False)
    width = SensorInUse.PixelWidth
    height = SensorInUse.PixelHeight
    # load the image
    NewImageBuffer = pilomarimage(name='overlay',logger=CamLog)
    NewImageBuffer.New(height=height,width=width,imagetype='bgra',datatype=np.uint8)
    NewImageBuffer.FillColor((0,0,0,0)) # Set all pixels to transparent.
    centrex = int(width / 2)
    centrey = int(height / 2)
    if filename == None: filename = FolderHandler.PrepFile('preview',"overlay_" + UtcTimeStamp() + ".png")
    ## Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - Parameters.TargetInclusionRadius
    MaxRADeg = CentreRa + Parameters.TargetInclusionRadius
    MinDecDeg = CentreDec - Parameters.TargetInclusionRadius
    MaxDecDeg = CentreDec + Parameters.TargetInclusionRadius
    QuickStarTime = Ts2Datetime(t)

    if True: # Parameters.MarkupShowDegreeScale: # Mark DEGREE scale. This is degrees movement of the camera, NOT degrees in the sky!
        CamLog.Log("TuningOverlay: ShowDegreeScale",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Yellow'))
        # Calibration - Azimuth
        for i in range(-10,11):
            xpos = int(width/2) + (i * CameraInUse.PixelsPerFovDegreeWidth) # 1 degree markers
            ypos = int(height/2)
            NewImageBuffer.DrawLine((xpos,ypos - 100),(xpos,ypos),thickness=10)
        # Calibration - Altitude
        for i in range(-10,11):
            xpos = int(width/2) 
            ypos = int(height/2) + (i * CameraInUse.PixelsPerFovDegreeHeight) # 1 degree markers
            NewImageBuffer.DrawLine((xpos - 100,ypos),(xpos,ypos),thickness=10)

    if True: # Parameters.MarkupShowFullStepScale: # Mark FULL STEP scale.
        CamLog.Log("TuningOverlay: azpx/step",az_pixels_per_fullstep,"altpx/step",alt_pixels_per_fullstep,"HFOV",LensInUse.FovHorizontal,"VFOV",LensInUse.FovVertical,"Wpx",width,"Hpx",height,terminal=False)
        # Calibration - Azimuth
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Cyan'))
        c = 0 # Counter used to stagger the text to reduce overlapping.
        MajorTickSteps = DynamicStepScale(targetpix=200,pixelsperunit=az_pixels_per_fullstep,unit='steps')
        for i in range(int(-10 * MajorTickSteps),int(10 * MajorTickSteps + 1),MajorTickSteps): # Major tick marks only.
            c = 1 - c
            xpos = int((width/2) + (i * az_pixels_per_fullstep))
            ypos = int(height/2)
            NewImageBuffer.DrawLine((xpos,ypos),(xpos,ypos + 100),thickness=10)
        # Calibration - Altitude
        MajorTickSteps = DynamicStepScale(targetpix=200,pixelsperunit=alt_pixels_per_fullstep,unit='steps')
        for i in range(int(-10 * MajorTickSteps),int(10 * MajorTickSteps + 1),MajorTickSteps): # Major tick marks only.
            xpos = int(width/2)
            ypos = int((height/2) + (i * alt_pixels_per_fullstep))
            NewImageBuffer.DrawLine((xpos,ypos),(xpos + 100,ypos),thickness=10)

    if True: # Parameters.MarkupShowMessier: # Mark neighbouring Messier objects ....
        CamLog.Log("TuningOverlay: ShowMessier",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Green'))
        # Find that alt/az locations of all the objects.
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            TempStarRA = TempStarParms['radeg']
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg: # Outside drawing area.
                continue # Skip to next object
            TempStarDec = TempStarParms['decdeg']
            if TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg: # Outside drawing area.
                continue # Skip to next object
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) 
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz(TempStarRA,TempStarDec,time=t,asdegrees=True)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            if TempStarAz < 0: # Below horizon, don't mark it up.
                continue # Skip to next object.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            NewImageBuffer.DrawEllipse(TempStarX,TempStarY,int(TempStarWidth),int(TempStarHeight),0,0,360,thickness=10)

    if True: # Mark neighbouring NGC items ...
        # Find the alt/az locations of all the objects.
        # NGC catalog is large, eliminate as much as possible first.
        CamLog.Log("TuningOverlay: NGCItems: CentreRa",CentreRa,DegreeSymbol,"CentreDec",CentreDec,DegreeSymbol,terminal=False)
        boolseries = NGC_DF['radeg'].between(MinRADeg, MaxRADeg, inclusive='both') # Create filter for items within RA range.
        tempdf = NGC_DF[boolseries] # Apply filter.
        boolseries = tempdf['decdeg'].between(MinDecDeg, MaxDecDeg, inclusive='both') # Create filter for items with Dec range.
        tempdf = tempdf[boolseries] # Apply filter.
        NewImageBuffer.SetPenColor(pilomarimage.BGR('LightBlue'))
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarName = TempStarParms['name']
            if TempStarName.startswith('pgc'): continue # Don't process all the PGC entries, it's REALLY slow.
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from arcseconds to degrees & radius.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            if TempStarWidth < 1 and TempStarHeight < 1: continue # Too small to display.
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarDec = TempStarParms['ded'] + TempStarParms['dem'] / 60 + TempStarParms['des'] / 3600
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz([TempStarParms['rah'],TempStarParms['ram'],TempStarParms['ras']],TempStarDec,time=t,asdegrees=False)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            if TempStarAz < 0: continue # Below horizon, don't mark it up.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            NewImageBuffer.DrawEllipse(TempStarX,TempStarY, int(TempStarWidth),int(TempStarHeight), angle=0, startAngle=0, endAngle=360, thickness=10)
    
    if True: # Parameters.MarkupShowStars: # Mark neighbouring stars.
        CamLog.Log("TuningOverlay: ShowStars",terminal=False)
        NewImageBuffer.AvoidTextCollisions = Parameters.MarkupAvoidCollisions # Do we allow star labels to overlap?
        # Mark neighbouring stars on the picture too. This will help with alignment.
        # Select a subset of the Hipparcos catalog which is within 10Deg of the target (=centre of image)
        CamLog.Log("TuningOverlay: SelectStars start",terminal=False)
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        NeighbouringStarCount = len(NeighbouringStars)
        CamLog.Log("TuningOverlay: NeighbouringStars contains",NeighbouringStarCount,"entries.",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('PaleGreen'))
        # Now convert this list of ra/dec locations into alt/az positions for plotting on the overlay image.
        starcount = 0
        for i in range(NeighbouringStarCount):
            if i % 400 == 0:
                CamLog.Log("TuningOverlay: ShowStars. Processing star",i,terminal=False)
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe, probably makes a COPY, not a pointer to the original row.
            TempStarName = TempStarRec['label']
            # Calculate the location in the overlay image.
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz(TempStarRec['ra_degrees'],TempStarRec['dec_degrees'],time=t,asdegrees=True)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            if NewImageBuffer.OutOfBounds(TempStarX,TempStarY): continue # This star is off the edge of the image, skip it.
            # We're going to plot this one.
            TempStarWidth = int(TempStarRec['markupradius'])
            NewImageBuffer.DrawCircle(TempStarX,TempStarY,TempStarWidth,thickness=10) # cyan # circle where the star is.
            starcount += 1
            if starcount >= maxstars: break # Maximum number of stars successfully plotted.
        NewImageBuffer.AvoidTextCollisions = False # Turn off the label collision protection.

    if True: # Parameters.MarkupShowPlanets: # Mark neighbouring planets ....
        CamLog.Log("TuningOverlay: ShowPlanets",terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR('Gold'))
        # Find the alt/az locations of all the planets.
        for TempStarName in ['sun','mercury barycenter','venus barycenter','moon','mars barycenter','jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']:
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = target(TempStar,name=TempStarName,objecttype="planet",description=TempStarDescription,magnitude=0.0)
            TempStarAz, TempStarAlt = temptarget.AzAltDegrees(time=t) 
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,CentreAlt,CentreAz)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            TempStarWidth = 40 # Planets are by default 40 pixel radius circles.
            if TempStarName == 'moon':
                TempStarWidth = int(ConvertArcsecondsToPixels((0.5286 / 2) * 3600)) # Moon is approx 0.26 degrees angular radius.
            NewImageBuffer.DrawCircle(TempStarX,TempStarY,TempStarWidth,thickness=3) # cyan # circle where the planet is.
        
    CamLog.Log("TuningOverlay: Saving:",filename,terminal=True)
    NewImageBuffer.SaveFile(filename)
    CameraInUse.Overlayjpg = filename # Record the filename so that the web interface can access it.

    CamLog.Log("TuningOverlay: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("TuningOverlay: End",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def CreateOverlay():
    """ For menu. Call the TuningOverlay() function to generate an overlay image to disc. """
    MainLog.Log("CreateOverlay: Creating overlay image",terminal=True)
    TuningOverlay()

# ------------------------------------------------------------------------------------------------------

def SkyfieldToAstropyRaDec(ra,dec):
    """ Convert Skyfield friendly ra/dec coordinates into Astropy friendly format.
        Converts 
             (4,42,0),(-38,-6,-50.8) into '4h42m0s','-38d6m50.8s' """
    a_ra = str(ra[0]) + "h" + str(ra[1]) + "m" + str(ra[2]) + "s"
    a_dec = str(dec[0]) + "d" + str(abs(dec[1])) + "m" + str(abs(dec[2])) + "s"
    return a_ra,a_dec # As strings.
    
# ------------------------------------------------------------------------------------------------------

def CreateTargetImage(color=False,MinMagnitude=None,MarkAllStars=False,astrotime=None,StarLimit=2000,textlabel=None,mapspan=1.0,overlay=False):
    """ Create a mockup target image based purely upon the expected view. 
        Parameters ------------------------------------------------------------------------
        color = True generates a colour image, star colours are estimated from the Hipparcos catalog data (B-V measure).
                Color images are generated when simulating a photograph (when the camera is disabled).
                Grayscale images are generated when creating a target star map for AstroAlign.
        MinMagnitude = If specified, overrides the minimum magnitude of stars selected for inclusion.
                       Otherwise Parameters.TargetMinMagnitude is used.
        MarkAllStars = If True, all stars in the LocalStars cache are marked. If they are below the MinMagnitude then they are only minimally indicated in images.
                       This applies to the NGC/IC/PGC and Hipparcos catalogs.
        astrotime = If specified, a specific Skyfield datetime that the image represents.
        StarLimit = Maximum number of stars to include in the image.
        textlabel = Optional additional text to write at the top of the image.
        mapspan = Default 1.0: Multiplies each axis of the image to include more or less of the sky.
                               eg 2.0 doubles each axis making the image include 4 times the area.
        overlay = True: A 4 channel transparent image is created, can be used as an overlay. """
    CamLog.Log("CreateTargetImage: Start. color",color,", MinMagnitude",MinMagnitude,", StarLimit",StarLimit,",mapspan",mapspan,terminal=False)
    if astrotime != None: CamLog.Log("CreateTargetImage: Start. Astrotime", Ts2Datetime(astrotime),terminal=False)
    else: CamLog.Log("CreateTargetImage: Start. Astrotime", astrotime,terminal=False)
    RoutineStart = NowUTC() # Note the time that this routine starts.
    if astrotime is None: # No specific time given, so we're live! Use current time and current camera position.
        t = SkyfieldNow() # Current timestamp in 'astro' time. As close as possible to the time of the photograph itself. Could develop this further! # Offset supported.
        if Parameters.UseLiveLocation: # Use the live target location rather than the last reported camera position for image processing.
            az_degree, alt_degree = Session.Target.AzAltDegrees(time=t) # What is the alt/az location of the centre of the image?
            CamLog.Log("CreateTargetImage: No astrotime received. Using current target position, at",Ts2Datetime(t),
                       "alt",Deg3dp(alt_degree),"deg, az",Deg3dp(az_degree),"deg. at",Ts2Datetime(t),"for calculations",terminal=False)
        else: # Use the last reported camera position. Deprecated.
            alt_degree, az_degree = LastReportedAltAz() # What is the alt/az location of the centre of the image?
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
    if mapspan > 1.0: # The map should include a wider area than the camera sensor. Cannot currently go smaller.
        width = int(width * mapspan)
        height = int(height * mapspan)
    if overlay: # Create overlay with transparent background.
        NewTargetImage.New(height,width,imagetype='bgra',datatype=np.uint8)
        NewTargetImage.FillColor((0,0,0,0))
    else: # Conventional image with black background.
        NewTargetImage.New(height,width,imagetype='bgr',datatype=np.uint8)
    if MinMagnitude is None: # Calling procedure can override the minimum magnitude parameter.
        MinMagnitude = Parameters.TargetMinMagnitude
    CamLog.Log("CreateTargetImage: MinMagnitude:", MinMagnitude,terminal=False)
    starlist = [] # Create star list. This will be used by astroalign.find_transform() in tracking.
    QuickStarTime = Ts2Datetime(t)

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
        # Find the alt/az locations of all the objects.
        ItemCount = 0
        FullCount = 0
        for TempStarName,TempStarParms in Messier_dictionary.items(): # Python3 
            FullCount += 1
            TempStarMagnitude = TempStarParms['magnitude']
            if TempStarMagnitude > MinMagnitude: # Too dim to show.
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
            TempStarType = TempStarParms['type']
            if TempStarType in ['galaxy','cluster','milky way']: TempStarColor = pilomarimage.BGR('MidnightBlue')
            else: TempStarColor = pilomarimage.BGR('HotPink')
            TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from degree diameter to pixel radius.
            TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz(TempStarRA,TempStarDec,time=t,asdegrees=True)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            NewTargetImage.FillEllipse(TempStarX,TempStarY, TempStarWidth,TempStarHeight, angle=0, startAngle=0, endAngle=360, color=TempStarColor)
            ItemCount += 1
        CamLog.Log("CreateTargetImage: Plot Messier objects end. (",ItemCount,"/",FullCount,"objects selected)",terminal=False)

    if color: # Mark neighbouring NGC items ...
        # Find the alt/az locations of all the objects.
        # NGC catalog is large, eliminate as much as possible first.
        boolseries = NGC_DF['radeg'].between(MinRADeg, MaxRADeg, inclusive='both') # Create filter for items within RA range.
        tempdf = NGC_DF[boolseries] # Apply filter.
        boolseries = tempdf['decdeg'].between(MinDecDeg, MaxDecDeg, inclusive='both') # Create filter for items with Dec range.
        tempdf = tempdf[boolseries] # Apply filter.
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarName = TempStarParms['name']
            if TempStarName.lower().startswith('pgc') and not Parameters.ShowPGCEntries: continue # Don't process all the PGC catalog entries.
            TempStarMagnitude = TempStarParms['magnitude']
            if not MarkAllStars and TempStarMagnitude > MinMagnitude: # This is too dim to show in any circumstances.
                continue # Skip to the next object.
            if TempStarMagnitude <= MinMagnitude: # Simulate brightness and size.
                TempStarWidth = int((TempStarParms['widthdeg'] * CameraInUse.PixelsPerFovDegreeWidth) / 2) # Convert from degree diameter to pixel radius.
                TempStarHeight = int((TempStarParms['heightdeg'] * CameraInUse.PixelsPerFovDegreeHeight) / 2)
                TempStarColor = pilomarimage.BGR('DarkGreen')
            else: # Mark the object with the smallest and dimmest object.
                TempStarWidth = 1
                TempStarHeight = 1
                TempStarColor = pilomarimage.BGR('DeepEmeraldGreen')
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarDec = TempStarParms['ded'] + TempStarParms['dem'] / 60 + TempStarParms['des'] / 3600
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz([TempStarParms['rah'],TempStarParms['ram'],TempStarParms['ras']],TempStarDec,time=t,asdegrees=False)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree)
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            #CamLog.Log("CreateTargetImage: Plot NGC ",i,TempStarParms['name'],"at",TempStarX,TempStarY,"radius",TempStarWidth,TempStarHeight,terminal=False)
            NewTargetImage.FillEllipse(TempStarX,TempStarY, TempStarWidth,TempStarHeight, angle=0, startAngle=0, endAngle=360, color=pilomarimage.BGR('DarkGreen'))

        CamLog.Log("CreateTargetImage: NGCItems: Plot NGC objects end. (",len(tempdf),"/",len(NGC_DF),"objects selected)",terminal=False)
        
    ## Decide on a cutoff for the number of stars to plot.
    ## If not specified by calling routine, try to match the number of stars detected in the latest live image.
    ## (When simulating images, the first tracking pass will have 0 stars in the LatestStarCount, because it doesn't exist until we create it here.)
    CamLog.Log("CreateTargetImage: StarLimit:", StarLimit,terminal=False)
    #TempStarRadius = int(Parameters.TrackingStarRadius) # Default is that all stars are the same size in this image.
    
    if True: # Parameters.TargetShowStars: # Mark neighbouring stars.
        StarCount = 0 # How many stars have we plotted?
        NeighbouringStars = LocalStars.Get(CentreRa,CentreDec)
        CamLog.Log("CreateTargetImage: NeighbouringStars contains",len(NeighbouringStars),"entries.",terminal=False)
        TotalStars = len(NeighbouringStars)
        TempStarColor = pilomarimage.BGR('White') # B&W tracking images are just simple white dots.
        # Performance measures to help with development :-
        MagnitudeRejects = 0 # How many stars were rejected due to magnitude limit?
        HorizonRejects = 0 # How many stars were rejected because they are below the horizon?
        BoundsRejects = 0 # How many stars were rejected because they are out of image bounds?
        DimStars = 0 # How many 'dim' items were rendered?
        
        for i in range(TotalStars):
            if i % 400 == 0: 
                CamLog.Log("CreateTargetImage.ShowStars: Processing star",i,terminal=False) # Monitor performance
                time.sleep(0.1) # Put a small pause in occassionally to let other processes get a chance!
            TempStarRec = NeighbouringStars.iloc[i] # Select each row in turn from the Pandas dataframe.
            TempStarName = TempStarRec['label'] # eg "HIP1"
            TempStarMagnitude = TempStarRec['magnitude'] # Note the brightness of the star.
            if not MarkAllStars and TempStarMagnitude > MinMagnitude: # This is too dim to show in any circumstances.
                MagnitudeRejects += 1 # Count how many stars were rejected because they are too dim.
                continue # The star is too dim, ignore it.
            if not TempStarName in Session.Target.QuickStarCache: # Add this object to the QuickStarCache.
                TempStarAlt, TempStarAz = Session.Target.RaDecToAltAz(TempStarRec['ra_degrees'],TempStarRec['dec_degrees'],time=t,asdegrees=True)
                Session.Target.QuickStarCache[TempStarName] = quickstar(TempStarAlt,TempStarAz,QuickStarTime)
            else: # Retrieve precalculated star position from cache for speed.
                TempStarAlt, TempStarAz = Session.Target.QuickStarCache[TempStarName].AltAz(QuickStarTime)
            if color == False and TempStarAlt < 0: # Below horizon 
                HorizonRejects += 1 # Count how many stars were below the horizon.
                continue # Don't plot it.
            PlotStarAlt, PlotStarAz = RelativeAltAz(TempStarAlt,TempStarAz,alt_degree,az_degree) # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            TempStarX, TempStarY = PlotRelativeAltAz(PlotStarAlt,PlotStarAz,height,width)
            if NewTargetImage.OutOfBounds(TempStarX,TempStarY): # The star is off the edge of the image, ignore it.
                BoundsRejects += 1 # Count how many stars were rejected because they were out of bounds.
                continue # The star is off the edge of the image, ignore it.
            if color: # Colour images should approximate star colour.
                TempStarColor = (int(TempStarRec['color_b']),int(TempStarRec['color_g']),int(TempStarRec['color_r']))
            if TempStarMagnitude > MinMagnitude: # Only the simplest of markers for VERY dim objects if we are showing them.
                TempStarColor = pilomarimage.BGR('Charcoal')
                DimStars += 1 # Count how many DIM stars we added to the image.
                TempStarRadius = 1 # Very small circle.
            else: TempStarRadius = int(TempStarRec['starradius'])
            NewTargetImage.FillCircle(TempStarX,TempStarY,TempStarRadius,color=TempStarColor)
            starlist.append([TempStarX,TempStarY]) # *Q* Does latest drift calculation need Radius or Magnitude anymore?
            StarCount += 1 # Increment the count of stars plotted. 
            if not MarkAllStars and StarCount >= StarLimit: # *Q* Should only apply to TRACKING TARGET images, not FAKE live images!
                CamLog.Log("CreateTargetImage: DriftTracker star limit " + str(StarLimit) + " reached.",terminal=False)
                CamLog.Log("CreateTargetImage: DriftTracker star limit reached HIP",TempStarRec.name,", magnitude",TempStarRec['magnitude'],terminal=False)
                break
        CamLog.Log("CreateTargetImage: Marked",StarCount,"of",StarLimit,"Stars,",TotalStars,"available.",DimStars," were 'dim'.",terminal=False)
        if StarCount < StarLimit:
            CamLog.Log("CreateTargetImage: Exhausted NeighbouringStars cache after selecting",StarCount,"stars.",terminal=False)
        CamLog.Log("CreateTargetImage: Rejected: Magnitude:",MagnitudeRejects,"Horizon:",HorizonRejects,"Bounds:",BoundsRejects,terminal=False)
    else:
        CamLog.Log("CreateTargetImage: No stars plotted.",terminal=False)

    if True: # Parameters.TargetShowPlanets: # Mark neighbouring planets ....
        # Find the alt/az locations of all the planets.
        CamLog.Log("CreateTargetImage: Plot planets start.",terminal=False)
        PlanetRadii = [40,4,6,40,6,10,10,4,4,4] # Radius to draw solar system objects. Must match list below.
        PlanetColors = [pilomarimage.BGR('Yellow'),
                        pilomarimage.BGR('White'),
                        pilomarimage.BGR('White'),
                        pilomarimage.BGR('White'),
                        pilomarimage.BGR('Red'),
                        pilomarimage.BGR('Yellow'),
                        pilomarimage.BGR('Gold'),
                        pilomarimage.BGR('White'),
                        pilomarimage.BGR('Blue'),
                        pilomarimage.BGR('White')] # Color to draw solar system objects. Must match list below.
        for i,TempStarName in enumerate(['sun','mercury barycenter','venus barycenter','moon','mars barycenter','jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']):
            TempStarMagnitude = 0.0
            if not MarkAllStars and TempStarMagnitude > MinMagnitude: # This is too dim to show in any circumstances.
                continue # Skip to next planet.
            TempStarRadius = PlanetRadii[i]
            if color: # Color images try to be vaguelly realistic.
                TempStarColor = PlanetColors[i]
            else: # Grayscale images just need to show dots for items.
                TempStarColor = pilomarimage.BGR('White')
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
        NewTargetImage.AddText(textlabel,10,50,color=pilomarimage.BGR('White'),size=1.0,thickness=1)

    if color: # Return a colour image.
        pass
    else: # Return Grayscale image.
        NewTargetImage.ChangeType('grayscale') # Convert BGR to grayscale.
    CamLog.Log("CreateTargetImage: Elapsed time ",str((NowUTC() - RoutineStart).total_seconds()),terminal=False)
    CamLog.Log("CreateTargetImage: Complete.",terminal=False)
    return NewTargetImage.ImageBuffer,StarCount,starlist

CameraInUse.ImageSimulator = CreateTargetImage # Tell astrocamera how to generate simulated images. 
CameraInUse.RelativeAltAz = RelativeAltAz # Point to utility functions.
CameraInUse.PlotRelativeAltAz = PlotRelativeAltAz # Point to utility functions.

# ------------------------------------------------------------------------------------------------------

def AutoPreview():
    """ Take immediate automatic photograph and mark it up with the expected objects in view. 
        This is normally used for calibration and testing. """
    MainLog.Log("AutoPreview",terminal=True)
    FileRoot = FolderHandler.PrepFile('preview','preview_')
    CameraInUse.SetImageType('auto')
    # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
    # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
    CameraCommand = Parameters._CameraAutoCommand
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
    campaignkey = FolderHandler.GetPath('campaign') # Only interested in files within the campaign structure.
    imagetypes = ['jpg','dng','fits']
    for key,value in FolderHandler.FolderList.items(): # Python3: Check each folder.
        vpath = value['path'] # Get the path.
        if not value['exists']: continue # Folder hasn't been created yet.
        if vpath.startswith(campaignkey):
            filelist = []
            try:
                for file in os.listdir(vpath): # List files in folder.
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
    result = ''
    if Parameters.CameraEnabled != True: selext = '.jpg' # No camera, so only count the simulated jpgs.
    elif CameraInUse.FastImageCapture: selext = '.jpg' # Fast image capture, only initial jpgs exist so far.
    elif CameraInUse.CameraSaveJpg: selext = '.jpg' # Looking for .jpg will detect more than .dng
    elif CameraInUse.CameraSaveFits: select = '.fits'
    elif CameraInUse.CameraSaveDng: selext = '.dng'
    else: selext = '.jpg'
    basedir = FolderHandler.GetPath('campaign')
    MainLog.Log("ImageCount_Campaign: basedir",basedir,terminal=False)
    searchpath = basedir + "/**/*" + selext
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

def CheckImageSet():
    """ Check that we have a full set of images. 
        Call this before allowing a change of target, session parameters or ending a session.
        If the user selects YES, then we allow the target/session to change.
        If the user selects NO, then we keep the session alive with the current target and settings. 
        If the folder has been deleted, then there are no images to worry about! """
    imagelist = ImageCount_Session()
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

    #CamLog.Log('CameraHandler: Start TrackingTimer for',DriftTracker.TrackingInterval,"s.",terminal=False)
    TrackingTimer = timer(DriftTracker.TrackingInterval) # Create a timer for drift tracking.
    TrackingTimer.Trigger() # Force immediate action.
   
    CamLog.Log("camerahandler: Begin main loop.",terminal=False)
    while RunThread: # This will run through all queued commands in sequence, then start polling periodically for new ones.
        if threading.main_thread().is_alive() == False: # Check if parent thread is still alive. Quit if it is nolonger there.
            CamLog.Log('CameraHandler: Parent thread is nolonger alive. Stopping.',level='error')
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
        #CamLog.Log('CameraHandler: Loop task:',LoopTask,terminal=False)
        
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
                TrackingDue = TrackingTimer.Due() # Note if the tracking is due, it's referred to a couple of times here.
                if Parameters.UseTracking == False: # Tracking currently disabled. (User can dynamically change this switch during observation).
                    if TrackingDue: DriftWindow.Print(NowHMS() + ' Drift tracking disabled.') # Warn the user.
                elif TrackingDue:
                    obs_start = NowUTC()
                    CamLog.Log('CameraHandler: Tracking: Begin tracking image capture',terminal=False)
                    DriftWindow.Print(NowHMS() + ' Begin tracking image capture.')
                    if Session.DebugMode:
                        print(NowHMS() + ' Begin ' + textcolor.cyan('tracking') + ' image capture.')
                    try: 
                        result = CameraInUse.TakeTrackingPhoto(batch_size,terminal=False)
                    except Exception as e:
                        CamLog.Log('CameraHandler: Tracking: CameraInUse.TakeTrackingPhoto failed with:',str(e),level='error')
                        CamLog.ReportException(e,comment='CameraHandler: Call to TakeTrackingPhoto()')
                        result = False
                    CamLog.Log('CameraHandler: Tracking: End tracking image capture',terminal=False)
                    CamLog.Log('CameraHandler: Tracking: Storing latest tracking image.',terminal=False)
                    DriftTracker.SetLatestImage(CameraInUse.Image.ImageBuffer,obs_start) # OpenCV (numpy) array of the camera image it is saved in DriftTracker as Grayscale and reduced and enhanced.
                    CamLog.Log( 'CameraHandler: Tracking: Begin CreateTargetImage',terminal=False)
                    if Parameters.TrackingTargetGrayscale: # Generate simplified tracking target.
                        colorflag = False
                    else: # Simulate an actual image.
                        colorflag = True
                    map_span = Session.Target.TrackingMapSpan
                    TempCvBuffer,TempStarCount,TempStarList = CreateTargetImage(color=colorflag,MinMagnitude=Parameters.TargetMinMagnitude,astrotime=Datetime2Ts(obs_start),StarLimit=2000 * map_span,mapspan=map_span) # Create a completely
                    CamLog.Log( 'CameraHandler: Tracking: End CreateTargetImage',terminal=False)
                    CamLog.Log( 'CameraHandler: Tracking: Stars',TempStarCount,':',TempStarList,terminal=False)
                    CamLog.Log( 'CameraHandler: Tracking: Calling SetMasterImage after CreateTargetImage',terminal=False)
                    DriftTracker.SetMasterImage(TempCvBuffer,starcount=TempStarCount,starlist=TempStarList,timestamp=obs_start) # CvImage is an OpenCV (numpy) array of the camera image in grayscale.
                    CamLog.Log( 'CameraHandler: Tracking: Completed SetMasterImage',terminal=False)
                    CamLog.Log( 'CameraHandler: Tracking: DriftTracker: Prep for drift calculation',terminal=False)
                    AzDriftSteps = 0 # No drift unless we safely calculate one.
                    AltDriftSteps = 0
                    DriftX = DriftTracker.dx
                    DriftY = DriftTracker.dy
                    if Session.DebugMode:
                        print(NowHMS(),'Drift',DriftX,"x ,",DriftY,"y pixels")
                    CamLog.Log('CameraHandler: Tracking: Detected driftx',DriftX,'drifty',DriftY, terminal=False)
                    temp = len(DriftTracker.LatestStarMatchList) # *Q* Make sure good values don't get overwritten by later bad ones during search.
                    if DriftX != None and temp < Parameters.TrackingMatchThreshold: # Must match a reasonable number of stars for confidence.
                        CamLog.Log( 'CameraHandler: Tracking: low confidence.',temp,'star(s).',terminal=False)
                        DriftWindow.Print(NowHMS() + ' Tracking: Low confidence. Matched ' + str(temp) + ' star(s).' )
                        DriftX = None
                        DriftY = None
                    CamLog.Log('CameraHandler: Tracking: DriftTracker trusted driftx',DriftX,'drifty',DriftY,terminal=False)
                    if DriftX != None:
                        AzDriftSteps = int(DriftX / az_pixels_per_fullstep)
                        AltDriftSteps = int(DriftY / alt_pixels_per_fullstep) * -1 # Invert result to convert from IMAGE Y direction to Motor Alt direction.
                        CamLog.Log('CameraHandler: Tracking: DriftTracker Predicted drift: x=' + str(round(DriftX,2)) + '(' + str(AzDriftSteps) + 'steps), y=' + str(round(DriftY,2)) + '(' + str(AltDriftSteps) + 'steps)',terminal=False)
                    DriftWindow.Print(NowHMS() + ' DriftTracker Drift result: ' + str(DriftX) + ',' + str(DriftY) + ' px; ' + str(AzDriftSteps) + ',' + str(AltDriftSteps) + ' steps.')
                    # Assign latest drift values back to the motors.
                    for i in MotorControls: # Run through all the motors selecting those that need tuning.
                        if i.MotorName == 'azimuth': # Azimuth motor.
                            if AzDriftSteps != None and abs(AzDriftSteps) > Parameters.MinimumDriftCorrection: # Drift is large enough to do something.
                                DriftWindow.Print(NowHMS() + ' Tuning ' + i.MotorName)
                                CamLog.Log('CameraHandler: Tracking: Tuning ' + i.MotorName,terminal=False)
                                if Session.DebugMode:
                                    print(NowHMS() + ' Tuning',i.MotorName,AzDriftSteps,'steps')
                                i.TunePosition(AzDriftSteps)
                            else: # Drift is too small to worry about.
                                DriftWindow.Print(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.')
                                CamLog.Log('CameraHandler: Tracking: Not tuning ' + i.MotorName + ', drift is too small.',terminal=False)
                        elif i.MotorName == 'altitude': # Altitude motor.
                            if AltDriftSteps != None and abs(AltDriftSteps) > Parameters.MinimumDriftCorrection: # Drift is large enough to do something.
                                DriftWindow.Print(NowHMS() + ' Tuning ' + i.MotorName)
                                CamLog.Log('CameraHandler: Tracking: Tuning ' + i.MotorName,terminal=False)
                                if Session.DebugMode:
                                    print(NowHMS() + ' Tuning',i.MotorName,AltDriftSteps,'steps')
                                i.TunePosition(AltDriftSteps)
                            else: # Drift is too small to worry about.
                                DriftWindow.Print(NowHMS() + ' Not tuning ' + i.MotorName + ', drift is too small.')
                                CamLog.Log('CameraHandler: Tracking: Not tuning ' + i.MotorName + ', drift is too small.',terminal=False)
                    ReplyMessage = {'TimeStamp' : NowUTC(), 'DriftX' : DriftX, 'DriftY' : DriftY, 'AzDriftSteps' : AzDriftSteps, 'AltDriftSteps' : AltDriftSteps} 
                    outboundqueue.put(ReplyMessage)
                    CameraInUse.TxCount += 1
                    CameraRxWindow.Print(DictionaryToString(ReplyMessage)) # Report communications from Camera to Main.
                    TrackingTimer.Restart() # Start new countdown timer from the moment this finishes.
                    CamLog.Log('CameraHandler: Tracking: End drift calculation',terminal=False)
            if LoopTask == 'image': # Time to take an actual image. (If timelapse is active, only when it's due, otherwise every time.)
                if not CameraInUse.TimelapseDue(): # Check timelapse mechanism.
                    CamLog.Log('CameraHandler: Image task. Timelapse is active but not due.',terminal=False)
                else: # Timelapse doesn't apply, or it's due. Either way, it's time to capture an image.
                    CamLog.Log('CameraHandler: Image task. Timelapse does not apply or is due, OK to capture an image.',terminal=False)
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
                        CamLog.Log("Folder for image details:", FolderHandler.GetPath('session'),terminal=False)
                        detailsfile = FolderHandler.PrepFile('session','imagedetails.txt')
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
                        CamLog.Log("CameraHandler: Image capture did not succeed. Stopping.",level='error')
                        RunThread = False # Something went wrong, quit!

            # Generate a labelled copy of the image periodically. For monitoring.
            if LoopTask == 'preview': # Time to consider making a preview markup.
                if PreviewTimer.Due() and CameraInUse.Image.ImageExists(): # Periodically prepare a new preview image. This is slow, so don't do it very frequently.
                    CamLog.Log('CameraHandler: Begin preview image markup',terminal=False)
                    if Session.DebugMode:
                        print (NowHMS() + ' Begin ' + textcolor.magenta('preview') + ' image generation.')
                    # astrocamera.CaptureSet will have loaded the image into OpenCV compatible buffer. This is available to mark up with more information.
                    astrotimeend = Datetime2Ts(CameraInUse.CaptureEnd)
                    MarkupPreview(drift_pixels_x=DriftTracker.dx,drift_pixels_y=DriftTracker.dy,astrotime=astrotimeend) # Use last image buffer from CameraInUse.Image to generate a marked up copy of the image on disc.
                    CamLog.Log('CameraHandler: End image markup',terminal=False)
                    PreviewTimer.Restart() # The countdown to the next preview image begins NOW, so we don't repeat too often and crowd out actual images.

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
        LoopDuration = round((NowUTC() - LoopStartTimestamp).total_seconds(),2)
        TimeAllocation[LoopTask] = LoopDuration + TimeAllocation.get(LoopTask,0.0)
        LoopCounter += 1
        if LoopDuration > 0.0 and LoopTask != 'pause': # Record overall processing time for this task. Ignore pauses.
            CamLog.Log("CameraHandler: Loop completed",LoopTask,"in",LoopDuration,"seconds",terminal=False)
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
    """ This creates a communication channel between the main process and the camera handler. 
        The camera handler can autonomously capture images of different types as required. """
    global CameraThread # Must be global because it must persist after this function completes. 
    if CameraThread is None or CameraThread.is_alive() != True:
        CameraThread = threading.Thread(target=CameraHandler,args=(CameraStatusQueue,CameraControlQueue))
        CameraThread.start()
        time.sleep(2) # Wait a moment before returning.
    return True

# ------------------------------------------------------------------------------------------------------

def ShutdownCamera():
    """ Close the camerahandler thread.
        This terminates communication between the main process and the camera handler. """
    global CameraThread
    global CameraStatusQueue
    global CameraControlQueue
    success = True # Assume success unless we fail to shut down the handler correctly. 
    print ('\n' + textcolor.yellow('Stopping CameraHandler...')) # force newline before printing text.
    if not CameraInUse.CurrentTask in [None,'pause']:
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
    """ Create a separate thread to handle communication between the RPi and the microcontroller 
        over the UART channel. """
    global MessageThread # Must be global because it must persist after this function completes. 
    Session.TerminateMctlHandler = False # Clear any existing shutdown flag.
    if MessageThread is None or MessageThread.is_alive() != True:
        MessageThread = threading.Thread(target=Session.MctlHandler)
        MessageThread.start()
    return True

# ------------------------------------------------------------------------------------------------------

def ShutdownMessage(): 
    """ Close the messagehandler thread.
        This terminates communication between the RPi and the microcontroller over the UART channel. """
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

StartMessageThread() # Fire up communication between the RPi and the microcontroller. 

# ------------------------------------------------------------------------------------------------------

def GoToTarget(target_object):
    """ Point camera at the target. But don't begin an observation. 
        Observations can only start once the microcontroller has a trajectory available to follow. """
    print (textcolor.yellow("GoToTarget: Pointing camera at target."))
    if Parameters.RequireRestart: # Warn that movements cannot be made until software is restarted.
        RestartRequired()
        return
    
    StopMotors() # Clear anything that's still programmed for the motors. 
    Session.SetMotorControlMode('direct') # We will directly control the movement of the microcontroller, no trajectory needs sending.

    # Prelocate the motors if case we need to handle gear backlash. It is good to go to a slightly lower azimuth position before starting the observation.
    if Parameters.BacklashEnabled: # We're handling gear backlash.
        currentalt, currentaz = LastReportedAltAz() # What is current position of the camera?
        az, alt = Session.Target.AzAltDegrees() # What is the current position of the target?
        MainLog.Log('GoToTarget: Backlash prealignment: From (' + AzAltText(currentaz,currentalt,DegreeSymbol) + ") to (" + AzAltText(az,alt,DegreeSymbol) + ")")
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
    MainLog.Log('GoToTarget: Alignment: From ' + AzAltText(currentaz,currentalt,DegreeSymbol) + " to " + AzAltText(az,alt,DegreeSymbol))
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
    
    if drifttracker is None: temp = None # There is no drifttracker object to call.
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
    memtot, memuse, memfree = MemoryMonitor.GetMemory() # Get system memory usage - memory is usually low because of Linux cache, so this may cause undue panic!
    mempercent = int(100 * (float(memfree) / float(memtot)))
    memrange = MemoryMonitor.GetFreeRange()
    if mempercent > 20: ObservationStatusWindow.FieldValue('MEMORY',str(mempercent) + "% " + memrange,fg=OSW_TEXT_GOOD)
    elif mempercent > 5: ObservationStatusWindow.FieldValue('MEMORY',str(mempercent) + "% " + memrange,fg=OSW_TEXT_POOR) # Yellow
    else:
        ObservationStatusWindow.FieldValue('MEMORY',str(mempercent) + "% " + memrange,fg=OSW_TEXT_BAD) # Red
        MainLog.Log("Free memory is very low (" + HRBytes(memfree) + "bytes)",level='warning')
    return result

# ------------------------------------------------------------------------------------------------------

def UpdateCpuLoad():
    """ Display state of overall CPU. 
        % busy, temperature.

        Also update individual core load to the dev window. """
    # Total CPU load...
    CpuMonitor.PollAll() # Update stats.
    cpupercent = CpuMonitor.PercentBusy() # Get the most up-to-date CPU percent busy figures.
    cputemp = CpuMonitor.CpuTemp
    currfreq = CpuMonitor.CurrFreq
    if currfreq != None:
        cpuclock = HRHertz(currfreq)
    else:
        cpuclock = ''
    cputext = str(int(cpupercent)) + "% " + str(int(cputemp)) + "C " + cpuclock
    if cputemp == 0: ObservationStatusWindow.FieldValue('CPU','measuring',fg=OSW_TEXT_POOR) # No measures yet.
    elif cpupercent > 90 or cputemp > 80 or CpuMonitor.MinSpeed(): ObservationStatusWindow.FieldValue('CPU',cputext,fg=OSW_TEXT_BAD) # Red
    elif cpupercent > 70 or cputemp > 65 or CpuMonitor.IsThrottled(): ObservationStatusWindow.FieldValue('CPU',cputext,fg=OSW_TEXT_POOR) # Yellow
    else: ObservationStatusWindow.FieldValue('CPU',cputext,fg=OSW_TEXT_GOOD) # Green
    if CpuMonitor.FreqChanged(): # The clock frequency changed since last checked.
        DevWindow.Print(NowHMS() + " Clock freq. now:",HRHertz(CpuMonitor.CurrFreq))
    return True

# ------------------------------------------------------------------------------------------------------

def UpdateCameraStatus():
    if Parameters.CameraEnabled: # Camera is enabled, report the selected exposure time.
        ObservationStatusWindow.FieldValue('CEN',Parameters.CameraEnabled,fg=OSW_TEXT_GOOD) # Green
        ObservationStatusWindow.FieldValue('EXP',str(CameraInUse.ExposureSeconds) + "s.",fg=OSW_TEXT_GOOD) # Exposure duration.
    else: # Camera is disabled, warn about this.
        ObservationStatusWindow.FieldValue('CEN',Parameters.CameraEnabled,fg=OSW_TEXT_POOR) # Red
        ObservationStatusWindow.FieldValue('EXP',str(CameraInUse.ExposureSeconds) + "s.",fg=OSW_TEXT_POOR) # Red - Blank out Exposure duration.
    if CameraInUse.TimelapseSeconds != None and CameraInUse.TimelapseSeconds > 0.0:
        ObservationStatusWindow.FieldValue('TLAPSE',HRSeconds(CameraInUse.TimelapseTimer.Remaining()),fg=OSW_TEXT_GOOD) # Exposure duration.
    else:
        ObservationStatusWindow.FieldValue('TLAPSE','Off',fg=OSW_TEXT_GOOD) # Exposure duration.
    if CameraInUse.FastImageCapture: # Warn that shortcuts are being taken to get photos as quickly as possible. (Means delaying some processing until after the observation).
        ObservationStatusWindow.FieldValue('FAST','Fast',fg=OSW_TEXT_POOR) # Fast Image Capture is active
    else:
        ObservationStatusWindow.FieldValue('FAST','Full',fg=OSW_TEXT_GOOD) # Fast Image Capture is not active
    if SensorInUse.OnChipCleanup: ObservationStatusWindow.FieldValue('OCC','On',fg=OSW_TEXT_POOR) # Red # Only applies to raspistill instances.
    else: ObservationStatusWindow.FieldValue('OCC','Off',fg=OSW_TEXT_GOOD) # Green # Only applies to raspistill instances.
    return True

# ------------------------------------------------------------------------------------------------------

def UpdateCameraCaptureStatus():      
    if CameraInUse.CaptureStart != None: # Monitor the progress of the current photograph.
        if CameraInUse.CaptureEnd is None or CameraInUse.CaptureEnd <= CameraInUse.CaptureStart:
            # Latest image capture has started but not finished yet.
            ImageStatusWindow.FieldValue("CAMERASTATE","Started",fg=OSW_TEXT_GOOD)
            ImageStatusWindow.FieldValue("STATETIMES",str(DisplayDT(CameraInUse.CaptureStart)).split(".")[0])
            ImageAge = (NowUTC() - CameraInUse.CaptureStart).total_seconds()
            ImageStatusWindow.FieldValue("STATEAGE",HRSeconds(ImageAge))
        else: # Last image capture is complete. Waiting for next one to start.
            ImageStatusWindow.FieldValue("CAMERASTATE","Ended",fg=OSW_TEXT_GOOD)
            ImageStatusWindow.FieldValue("STATETIMES",str(DisplayDT(CameraInUse.CaptureEnd)).split(".")[0])
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
    if folder is None: # No folder named, default to current one.
        folder = FolderHandler.GetPath('preview')
    sourcefilepattern = folder + '/preview_*.jpg'
    avifilename = FolderHandler.PrepFile('preview','preview_' + CleanDatetimeString(str(NowUTC())) + '.mp4')
    if filename != None: # Override target filename.
        avifilename = filename
    # *Q* GLOB facility may disappear from later versions of ffmpeg, this will need revising when that happens.
    cmd = "ffmpeg -y -framerate 10 -pattern_type glob -i '" + sourcefilepattern + "' -vf scale='iw/2:ih/2' " + avifilename
    osCmd(cmd)
    print(textcolor.yellow("Generated"), avifilename)
    MainLog.Log("GeneratePreviewMovie: Completed animation of observation previews.",terminal=False)
    return True

# ------------------------------------------------------------------------------------------------------

def GenerateLightMovie(folder=None,filename=None):    
    MainLog.Log("Generating animation of observation light images...",terminal=False)
    print (textcolor.yellow("Generating animation of observation light images..."))
    print('May take some time...')
    if folder is None: # No folder named, default to current one.
        folder = FolderHandler.GetPath('light')
    sourcefilepattern = folder + '/light_*.jpg'
    avifilename = FolderHandler.PrepFile('light','light_' + CleanDatetimeString(str(NowUTC())) + '.mp4')
    if filename != None: # Override target filename.
        avifilename = filename
    # *Q* GLOB facility may disappear from later versions of ffmpeg, this will need revising when that happens.
    cmd = "ffmpeg -y -framerate 10 -pattern_type glob -i '" + sourcefilepattern + "' -vf scale='iw/2:ih/2' " + avifilename
    osCmd(cmd)
    print(textcolor.yellow("Generated"), avifilename)
    MainLog.Log("GenerateLightAvi: Completed animation of observation light images.",terminal=False)
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

# Define a default 'schedule' list of targets. This is for scheduled observations.
ObservationSchedule = sessionlist('ObservationSchedule') # An empty new list for scheduled observations.

# ------------------------------------------------------------------------------------------------------

def DummyMenuProcess():
    """ For development, a dummy menu process. """
    print(textcolor.red("Placeholder for unfinished menu process."))
    
# ------------------------------------------------------------------------------------------------------

def AlternateDisplayTZ():
    """ Alternate the timezone used in the dashboard between LOCAL and UTC. """
    if Parameters.DisplayTZ == 'UTC': Parameters.DisplayTZ = Parameters.LocalTZ # Switch from UTC to Local timezone.
    else: Parameters.DisplayTZ = 'UTC' # Switch from local timezone to UTC.
    MainLog.Log("AlternateDisplayTZ: Switched display timezone to",Parameters.DisplayTZ,terminal=False)
    # Now update some dashboard information.
    temp = "(" + Parameters.DisplayTZ + ") "
    ObservationStatusWindow.RJTitle = temp
    ObservationStatusWindow.SetTitle() 
    ImageStatusWindow.RJTitle = temp
    ImageStatusWindow.SetTitle()
    #MainLog.Log("AlternateDisplayTZ: Before update, titlerow=",SessionWindow.ReadTitleRow(),terminal=False)    
    SessionWindow.RJTitle = temp
    SessionWindow.SetTitle() 
    #MainLog.Log("AlternateDisplayTZ: After update, titlerow=",SessionWindow.ReadTitleRow(),terminal=False)    
    #MainLog.Log("AlternateDisplayTZ: SessionWindow.WindowTitle=",SessionWindow.WindowTitle,"RJTitle=",SessionWindow.RJTitle,terminal=False)
    DevWindow.Print(NowHMS() + " Display timezone switched to " + str(Parameters.DisplayTZ))
    
# ------------------------------------------------------------------------------------------------------

def DisplayLocalTZ():
    if Parameters.DisplayTZ == 'UTC': AlternateDisplayTZ()
    MainLog.Log("DisplayLocalTZ: Now showing times for",Parameters.DisplayTZ,"timezone.")

# ------------------------------------------------------------------------------------------------------

def DisplayUTCTZ():
    if Parameters.DisplayTZ != 'UTC': AlternateDisplayTZ()
    MainLog.Log("DisplayUTCTZ: Now showing times for",Parameters.DisplayTZ,"timezone.")

# ------------------------------------------------------------------------------------------------------

def ObservationRun(batchmode=False):
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

        Parameters -------------------------------------------------------
        batchmode: True : User is not prompted for low priority questions.
        
        Output -----------------------------------------------------------
        success: True/False: Did the observation succeed?
        statuslist: List of status codes from the observation. 

                        """
    MainLog.Log("ObservationRun: Beginning observation.",terminal=False)
    
    RunObservation = True # We are OK to run the observation loop.
    observationresult = True # Was observation completed successfully?
    observationstatuslist = [] # Status codes can be returned to the calling procedure through this.
    
    # Mark that an observation has started. If the program fails during an observation we can warn that 
    # camera position etc may be misaligned when it restarts.
    if IncompleteObservationCheck() == False:
        # There is an existing observation already running. Check this should proceed and warn that positions may be wrong.
        # The user chose to abandon this run.
        observationstatuslist.append("user:previousincomplete")
        return False, observationstatuslist
    FlagObservationStart() # Mark that an observation run has started. Used this to warn if recovering from a failed run.
    
    # Don't start an observation if the target is not yet in range.
    if not Session.Target.Visible(): # The target isn't yet within the visibility range of the telescope.
        MainLog.Log("ObservationRun: The target is not within the visibility range of the telescope.",terminal=False)
        textcolor.TextBox(["The target is not visible to the telescope at the moment."],fg=textcolor.RED,bg=textcolor.BLACK)
        observationresult = False
        RunObservation = False # Not OK to run the observation loop.
        observationstatuslist.append("system:notvisible")
        return observationresult, observationstatuslist # Quit the run.
        
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
            observationstatuslist.append("system:nocamerathread")
            return observationresult,observationstatuslist # Return to the menu.
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
            observationstatuslist.append("system:cameraresettimeout")
            return observationresult,observationstatuslist # Return to the menu.
        if ack == False: 
            time.sleep(0.5) # Pause half a second before checking again.
            print("Waiting for camera acknowledgement.",int(AckTimer.Remaining()),"seconds left.",textcolor.cursorup())
    print(textcolor.clearforward()) 

    # Check that the UART communication with the motor microcontroller is alive.
    if MctlThread.is_alive() == False: # UART comms thread has failed.
        MainLog.Log("ObservationRun (startup): MctlThread is not running!",level='error')
        observationresult = False # Don't continue.
        RunObservation = False # We cannot perform the observation. We will have to return to the menu.
        observationstatuslist.append("system:nomicrocontrollerthread")
        return observationresult,observationstatuslist # Return to the menu.
    # Check that the message handler between the RPi and microcontroller is alive.
    if MessageThread.is_alive() == False: # Message handler thread has failed.
        MainLog.Log("ObservationRun (startup): MessageThread is not running!",level='error')
        observationresult = False # Don't continue.
        RunObservation = False # We cannot perform the observation. We will have to return to the menu.
        observationstatuslist.append("system:nomessagethread")
        return observationresult,observationstatuslist # Return to the menu.

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
        observationstatuslist.append("system:microcontrollercommsfail")
        return observationresult,observationstatuslist # Return to the menu.
    if Parameters.InitialGoTo: # Does an observation run start with a GOTO?
        MainLog.Log('ObservationRun: Performing initial GOTO performed before creating trajectory.',terminal=False)
        az, alt = Session.Target.AzAltDegrees() # Calculations for target from observer's location.
        temp = GoToTarget(Session.Target) # Go directly to the target before starting the trajectory mechanism.
        if temp == False:
            MainLog.Log("ObservationRun: Initial GOTO failed.",level='error')
            temp = AskYesNo("Do you want to continue anyway? [y/N]",False)
            if not temp: 
                observationstatuslist.append("user:gotofailed")
                return False, observationstatuslist # Quit immediately.
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
    if CameraInUse.TimelapseTimer is None:
        MainLog.Log("Timelapse inactive.",terminal=False)
    else:
        MainLog.Log("Timelapse active (",CameraInUse.TimelapseSeconds,"s)",terminal=True)
    if CameraInUse.FastImageCapture: # We're taking shortcuts to get as many images as possible in a short time span.
        print(textcolor.yellow("NOTE: FastImageCapture is active. Images will be captured as quickly as possible."))
        print(textcolor.yellow("Low priority image processing will not be done during the observation."))
        print(textcolor.yellow("If you want to extract raw (.dng) data you must do it separately after the observation."))
    SessionWindow.Clear(immediate=False) # Clear old messages from the session window.
    DebugTimer = timer(120) # In debug mode, update summary status every 2 minutes.
    _ = ImageStorageMonitor.FreeBytes(force=True) # Force disc space refresh.
    # After this point all messages to the terminal should respect WINDOW and DEBUG MODE selections, otherwise they get overwritten/corrupted.
    if Session.DebugMode: 
        # Do not clear the screen in debug mode. We don't want to lose error messages.
        print (textcolor.orange('In DEBUG MODE. The dashboard display is suppressed so that any errors are more clear.')) # In debug mode, nothing is displayed except error messages.
        print (textcolor.yellow("In DEBUG MODE. Press 'x' to quit, 'd' toggle debug/dashboard, 'm' submenu, 'r' refresh.")) # In debug mode, nothing is displayed except error messages.
    else:
        # Not in debug mode. Specific window layout will be used to show information.
        # Any output from error messages or regular print() commands will be lost as the display frequently refreshes.
        ClearScreen() # Clear the screen and force window refresh.
    if Session.DebugMode:
        MainLog.Log('ObservationRun: (DebugMode) Starting main loop...')
    #keyboardcount = 0 # Count the iterations between keyboard scans.
    colordisplay.GlobalForceRedraw() # Force all window buffers to fully redraw initially.
    while RunObservation: # Main loop of the observation.

        #MainLog.Log("ObservationRun: Loop starts",terminal=False)
        # Check for keyboard commands...
        #MainLog.Log("ObservationRun: Check for keyboard input...",terminal=False)
        # *Q* The following keyboard scan uses the curses library. It can cause the terminal display to blink sometimes. Not cured yet, worse on earlier RPis.
        if KeyboardTimer.Due(): # It's time to scan the keyboard.
            keypress = Keyboard.Check().lower() # Non-blocking scan for keyboard input. 
        else:
            keypress = "" # Don't check keyboard this time round.
        if keypress != "": # Some keyboard input detected. 
            if ord(keypress) == 410: pass # Ignore the 410 character, it is associated with screen resizing.
        if keypress == "x" or keypress == chr(27): # Break with 'x' or 'esc' key.
            MainLog.Log("Keyboard interrupt: Terminating.",level='warning',terminal=False)
            ErrorWindow.Print(NowHMS() + ' Keyboard interrupt. Terminating observation.')
            observationresult = True # Don't continue, but it's not an error.
            observationstatuslist.append("user:exit")
            RunObservation = False # This will quit the loop and shut down the motors and camera.
        elif keypress == "m": # Submenu.
            MainLog.Log("Keyboard interrupt: Submenu selected.",terminal=False)
            ObservationSubmenu(drifttracker=DriftTracker) # Pass the drifttracker object because the submenu can access its methods.
            ClearScreen() # Clear screen afterwards.
        elif keypress == "+": # Exposure compensation. Increase exposure. (200% exposure time).
            MainLog.Log("Keyboard interrupt: Increase exposure time.",terminal=False)
            AdjustExposureTime(2.0)
        elif keypress == "-": # Exposure compensation. Decrease exposure. (50% exposure time).
            MainLog.Log("Keyboard interrupt: Decrease exposure time.",terminal=False)
            AdjustExposureTime(0.5)
        elif keypress == "t": # Turn drift tracking on/off.
            MainLog.Log("Keyboard interrupt: Toggle DriftTracking status.",terminal=False)
            Parameters.UseTracking = not Parameters.UseTracking # Toggle the value.
            if Parameters.UseTracking: 
                DriftWindow.Print(NowHMS() + ' Drift tracking ON.')
                MainLog.Log("Keyboard interrupt: Drift tracking ON.",terminal=False)
            else: 
                DriftWindow.Print(NowHMS() + ' Drift tracking OFF.')
                MainLog.Log("Keyboard interrupt: Drift tracking OFF.",terminal=False)
        elif keypress == "u": # Switch dashboard timezone. (alternate between LocalTZ and 'UTC')
            MainLog.Log("Keyboard interrupt: Alternate display timezone.",terminal=False)
            AlternateDisplayTZ()
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
        if CameraThread.is_alive() == False: # If the CameraThread has died, quit.
            MainLog.Log("ObservationRun: CameraThread (Camera handler) is not running!",level='error')
            CameraWindow.Print(NowHMS() + " CameraThread is not running.")
            observationresult = False # Don't continue.
            observationstatuslist.append("system:camerathreadlost")
            RunObservation = False # Observation cannot continue.
        if MessageThread.is_alive() == False: # If message handler thread has died, quit.
            MainLog.Log("ObservationRun: (loop) MessageThread is not running!",level='error')
            observationresult = False # Don't continue.
            observationstatuslist.append("system:messagethreadlost")
            RunObservation = False # Observation cannot continue.
        if MctlThread.is_alive() == False: # If the motor microcontroller communication thread has died, quit.
            MainLog.Log("ObservationRun: (loop) MctlThread is not running!",level='error')
            observationresult = False # Don't continue.
            observationstatuslist.append("system:microcontrollerthreadlost")
            RunObservation = False # Observation cannot continue.
        if CameraStatusQueue.empty() == False: # The CameraThread has sent messages that need to be processed.
            StatusMessage = CameraStatusQueue.get() # Retrieve the first message in the queue.
            Session.CameraRxCount += 1 # We received another message from the camera.
            # Extract any useful information from the received messages.
            if 'PhotoCount' in StatusMessage: PhotoCount = StatusMessage['PhotoCount'] # Camera has updated the number of photographs taken during this run.
        # Calculate the current position of the target. This also updates the cached values, which remain valid for the duration of this loop.
        dtnow = NowUTC() # In datetime format. 
        ra, dec = Session.Target.RaDecDegrees() # Target's position. Right Ascension and Declination.
        az, alt = Session.Target.AzAltDegrees(updatespeed=True) # Target's position. Altitude and Azimuth from observer's location. Update angular velocity too.
        ObservationDuration = (dtnow - obsstart).total_seconds() # How long has this observation run been running for?
        ObservationStatusWindow.FieldValue('TARGET',Session.Target.Name,fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Update the target name. 
        ObservationStatusWindow.FieldValue('FOLDER',FolderHandler.GetPath('session'),fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # Which folder is the observation data saved in. 
        if ClockOffset != None: # The clock is not running in realtime.
            ObservationStatusWindow.FieldValue('CLOCK',str(DisplayDT(NowUTC(),decimals=True)).split("+")[0],fg=textcolor.WHITE,bg=textcolor.RED) # System clock in display timezone. 
        else: # Clock IS running in realtime.
            ObservationStatusWindow.FieldValue('CLOCK',str(DisplayDT(NowUTC(),decimals=True)).split("+")[0],fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # System clock in display timezone. 
        ObservationStatusWindow.FieldValue('DURATION',HRSeconds(ObservationDuration),fg=OSW_TEXT_GOOD) # How long has this observation been running.
        ObservationStatusWindow.FieldValue('IMAGETYPES',CameraInUse.ImageTypes(),fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # What image types are being recorded?
        # Calculate storage available.    
        if not UpdateStorageStatus(): # Update storage space available, and decide if it's safe to continue.
            observationresult = False # Don't continue.
            RunObservation = False # Quit the observation run.
            observationstatuslist.append("system:discspace")
            MainLog.Log("ObservationRun: Insufficient storage space terminating the observation.",level="error")
        UpdateCpuLoad() # Update the CPU load figures.
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
        ObservationStatusWindow.FieldValue('CAMAZ',DisplayDegree(CameraLatestAz,15,symbol=DegreeSymbol),fg=fgc,bg=OSW_TEXT_BG) # Camera's last reported position.
        ObservationStatusWindow.FieldValue('CAMALT',DisplayDegree(CameraLatestAlt,15,symbol=DegreeSymbol),fg=fgc,bg=OSW_TEXT_BG) 
        ObservationStatusWindow.FieldValue('ESTAZ',DisplayDegree(EstimatedAz,15,symbol=DegreeSymbol),fg=fgd,bg=OSW_TEXT_BG) # Camera's estimated current position.
        ObservationStatusWindow.FieldValue('ESTALT',DisplayDegree(EstimatedAlt,15,symbol=DegreeSymbol),fg=fgd,bg=OSW_TEXT_BG) 
        ObservationStatusWindow.FieldValue('TARAZ',DisplayDegree(az,15,symbol=DegreeSymbol),fg=fgc,bg=OSW_TEXT_BG) # Current target position.
        ObservationStatusWindow.FieldValue('TARALT',DisplayDegree(alt,15,symbol=DegreeSymbol),fg=fgc,bg=OSW_TEXT_BG) 
        ObservationStatusWindow.FieldValue('COMP',CompassPoint(az),fg=fgc,bg=OSW_TEXT_BG) # Azimuth as compass point.
        ObservationStatusWindow.FieldValue('RA',DisplayHMS(dh,dm,ds,15),fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) # RA and DEC of target.
        ObservationStatusWindow.FieldValue('DEC',DisplayDegree(dec,15,symbol=DegreeSymbol),fg=OSW_TEXT_GOOD,bg=OSW_TEXT_BG) 

        # If we're on target, then activate the camera (it runs in a separate thread until told to stop).
        if True: 
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
                if ObservationStartUTC is None: ObservationStartUTC = NowUTC() # Note when the observation starts.
                if CameraInUse.CameraFault(): # The camera isn't behaving itself. We may need to power cycle the RPi.
                    MainLog.Log("CameraInUse.CameraFault: You probably need to power cycle the RPi.",level='error')
                    CamLog.Log("CameraInUse.CameraFault: You probably need to power cycle the RPi.",level='error')
                    observationresult = False # Don't continue
                    observationstatuslist.append("system:camerafault")
                    RunObservation = False # Terminate the observation.
                    
        if PhotoCount >= Parameters.BatchSize:
            # We've taken the required number of photos as defined by BatchSize.
            # The CameraHandler thread is probably already working on the next one, so you may get an extra freebie!
            MainLog.Log("ObservationRun: BatchSize reached. Observation run complete.")
            observationstatuslist.append("system:batchsize")
            RunObservation = False

        if Mctl.DeviceFailure: # Communication with microcontroller has failed completely.
            MainLog.Log("ObservationRun: Mctl.DeviceFailure reported. Stopping observation.",level='error')
            observationresult = False # Don't continue.
            observationstatuslist.append("system:microcontrollerfailure")
            RunObservation = False

        # Check that the target is within observation range of the motors and above the horizon.
        if alt < 0.0 and PrevAlt != None: # Target is below horizon!
            if alt < PrevAlt or alt < 5.0: # The target has set and won't rise for a while!
                MainLog.Log("ObservationRun: Object below horizon. Stopping observation.",level='warning')
                observationresult = False # Don't continue.
                observationstatuslist.append("system:belowhorizon")
                RunObservation = False
        PrevAlt = alt
        for i in MotorControls: # Check also it is within range of the motor movement limits.
            if i.MotorName == "altitude": # Check range of Altitude motor.
                if alt < i.MinObservationAngle or alt > i.MaxAngle: # Target is out of scope of the motors. *!*
                    MainLog.Log("ObservationRun: The target is outside the",i.MotorName,"range of the telescope. Terminating observation.",level='warning')
                    observationstatuslist.append("system:altituderange")
                    observationresult = False # Don't continue.
                    RunObservation = False
            if i.MotorName == "azimuth": # Check range of Azimuth motor.
                if az < i.MinObservationAngle or az > i.MaxAngle: # Target is out of scope of the motors. *!*
                    MainLog.Log("ObservationRun: The target is outside the",i.MotorName,"range of the telescope. Terminating observation.",level='warning')
                    observationresult = False # Don't continue.
                    observationstatuslist.append("system:azimuthrange")
                    RunObservation = False

        ImageStatusWindow.FieldValue('IMAGES',str(ImageCount_Session()),fg=OSW_TEXT_GOOD) 
        # Calculate total accumulated image time.
        AccumulatedTime = PhotoCount * CameraInUse.ExposureSeconds
        if AccumulatedTime >= 1: # Show in HH:MM:SS
            ImageStatusWindow.FieldValue('ACCTIME',HRSeconds(AccumulatedTime),fg=OSW_TEXT_GOOD)
        else: # Show in 0.00000s
            ImageStatusWindow.FieldValue('ACCTIME',str(AccumulatedTime) + "s",fg=OSW_TEXT_GOOD)
        if True:
            pceta = '' # Don't know the estimated completion time yet.
            if PhotoCount > 0 and ObservationStartUTC != None: # We can estimate when the batch of photographs will be completed.
                pcprogress = float(PhotoCount) / Parameters.BatchSize # Percentage of way through the image batch.
                if pcprogress > 0.0: # We've made some progress, so estimate the completion time.
                    pcelapsed = (NowUTC() - ObservationStartUTC).total_seconds() # Elapsed time so far (seconds).
                    pcend = ObservationStartUTC + timedelta(seconds = int(pcelapsed / pcprogress)) # Roughly when will the batch be completed?
                    pceta = str(DisplayDT(pcend))[:16] # YYYY.MM.DD HH:MM
            ImageStatusWindow.FieldValue('RUN',str(PhotoCount) + " of " + str(Parameters.BatchSize),fg=OSW_TEXT_GOOD)
            if PhotoCount >= Parameters.BatchSize: # We've hit the target.
                ImageStatusWindow.FieldColor('RUN',fg=textcolor.BLACK,bg=textcolor.LIGHTGREEN) # Highlight we've made it.
            ImageStatusWindow.FieldValue('ETA',pceta,fg=OSW_TEXT_GOOD) 
        else:
            ImageStatusWindow.FieldValue('RUN',str(PhotoCount) + " of " + str(Parameters.BatchSize) + '(dis.)',fg=textcolor.RED1) # Red
            ImageStatusWindow.FieldValue('ETA','n/a',fg=OSW_TEXT_GOOD) 
        if ObservationStopButton != None and ObservationStopButton.IsLow(): # Emergency stop pin on RPi has been grounded. 
            print(textcolor.red('OBSERVATION STOP BUTTON: Break observation'))
            ErrorWindow.Print(NowHMS() + " OBSERVATION STOP BUTTON pressed.")
            observationresult = False # Don't continue. Consider the stop button to be a 'fail'.
            observationstatuslist.append("user:observationstopbutton")
            RunObservation = False # Quit loop.
        UpdateCameraCaptureStatus()
        # Explain what is in the 'last captured image' buffer.
        if CameraInUse.Image.ImageExists(): # openCV image buffer is loaded.
            if len(CameraInUse.Image.ImageBuffer.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            ImageStatusWindow.FieldValue("OCVIB","loaded " + DisplayHmsFromStamp(CameraInUse.LastImageDateTime) + " " + str(CameraInUse.Image.ImageBuffer.shape[0]).rjust(4) + "*" + str(CameraInUse.Image.ImageBuffer.shape[1]).rjust(4) + " " + fmt,fg=OSW_TEXT_GOOD)
        else:
            ImageStatusWindow.FieldValue("OCVIB","empty",fg=OSW_TEXT_POOR)
        # Explain the status of the TARGET tracking image.
        if DriftTracker.TargetImage.ImageExists(): # openCV image buffer is loaded.
            temp = "matched " + str(len(DriftTracker.TargetStarMatchList)) + " of " + str(DriftTracker.TargetImage.StarCount) + " stars"
            if len(DriftTracker.TargetImage.ImageBuffer.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            temp = str(DriftTracker.TargetImage.ImageBuffer.shape[0]).rjust(4) + "*" + str(DriftTracker.TargetImage.ImageBuffer.shape[1]).rjust(4) + " " + fmt + " " + temp
            ImageStatusWindow.FieldValue("DTI","loaded " + DisplayHmsFromStamp(DriftTracker.TargetTimeStamp) + " " + temp,fg=OSW_TEXT_GOOD)
        else: # No drift target image available.
            ImageStatusWindow.FieldValue("DTI","empty",fg=OSW_TEXT_POOR)
        # Explain the status of the LATEST tracking image.
        if DriftTracker.LatestImage.ImageExists(): # openCV image buffers are loaded.
            temp = "matched " + str(len(DriftTracker.LatestStarMatchList)) + " of " + str(DriftTracker.LatestImage.StarCount) + " stars"
            if len(DriftTracker.LatestImage.ImageBuffer.shape) > 2: fmt = "color" # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else: fmt = "gray"
            temp = str(DriftTracker.LatestImage.ImageBuffer.shape[0]).rjust(4) + "*" + str(DriftTracker.LatestImage.ImageBuffer.shape[1]).rjust(4) + " " + fmt + " " + temp
            ImageStatusWindow.FieldValue("DLI","loaded " + DisplayHmsFromStamp(DriftTracker.LatestTimeStamp) + " " + temp,fg=OSW_TEXT_GOOD)
        else: # No current drift image available.
            ImageStatusWindow.FieldValue("DLI","empty",fg=OSW_TEXT_POOR)
        ReadyToObserve = True # Work out if all the motors are on target!
        for i in MotorControls: # Report tuning status of each motor in turn.
            if Session.Target.IsFixedPoint(): # Fixed point, doesn't need the motor to report 'OnTarget' - we decide in this program instead.
                pass # Take no action here. Motor was already placed 'on target' when ObservationRun started. It doesn't move after that.
            elif not i.OnTarget: 
                if ReadyToObserve != False: # Only display when changing, it reduces duplicate log messages.
                    ReadyToObserve = False # This motor is not on target yet. So we're not ready to observe.
                    MainLog.Log('ObservationRun.',i.MotorName,'Not on target: ReadyToObserve = False',terminal=False)
            if i.LatestTuneTime != None: # This motor has been tuned. 
                line = str(i.LatestTuneSteps) + " steps at " + str(DisplayDT(i.LatestTuneTime)).split("+")[0] + " UTC"
            else: # This motor has not been tuned.
                line = 'None'
            if i.MotorName == 'azimuth':
                ImageStatusWindow.FieldValue("LAZT",line,fg=OSW_TEXT_GOOD)
            else:
                ImageStatusWindow.FieldValue("LALT",line,fg=OSW_TEXT_GOOD)
        
        if Session.DebugMode: # We're in debug mode, just summary status update.
            if DebugTimer.Due(): # It's time to publish a summary status.
                print (NowHMS() + " Target " + textcolor.white(Session.Target.Name) + " " + AzAltText(az,alt,DegreeSymbol))
                print (NowHMS() + " Session images: " + ImageCount_Session()) # Count images in the current SESSION!
                for line in StorageStrings(): print (NowHMS() + line)
                print (NowHMS() + " Session: " + FolderHandler.GetPath("session"))
                if ClockOffset != None: # Warn that tracking clock is not running in realtime.
                    print(textcolor.red(NowHMS() + " Tracking clock is offset to",str(NowUTC()).split('.')[0]))
        else: # Not in debug mode, update the color display.
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
        #MainLog.Log("ObservationRun: Total LOOP time=" + str(round(ltts * 1000,3)) + "ms. Ave LOOP time=" + str(round(averagelooptime * 1000,3)) + "ms.",terminal=False)
        LoopTimeList.append(round(ltts,1)) # Add to the list of recent loop times.
        if ltts > 20: # Exceedingly long loop time. O/S is busy with something else! If frequent it can be a sign that the memory card is aging/fragmented/damaged. Time to reinstall.
            SlowLoopCounter += 1 # Increment the count of slow loops, if we get a lot, there's maybe a problem.
            if SlowLoopCounter % 10 == 0:
                DevWindow.Print(NowHMS() + ' Detected ' + str(SlowLoopCounter) + ' slow loops.')
                # A lot of slow loops suggests that the O/S is getting distracted with other tasks.
                # It can be a sign that the memory card is aging and needs replacing.
        LoopTimeList = LoopTimeList[-10:] # Limit list to last 10 entries.

        # End of main ObservationRun loop.
        
    # Observation is over at this point.
    print(textcolor.clearforward()) # Clear the screen from the current location forward, makes the following messages easier to read.
    ReadyToObserve = False
    if True: # Tell the camera it is all over.
        ControlMessage = {'TimeStamp' : NowUTC(), 'ReadyToObserve' : False}
        CameraControlQueue.put(ControlMessage) # Keep sending the CameraEnabled status to the camera.
        Session.CameraTxCount += 1 # We sent another message to the camera.
        ShutdownCamera() # Wait for the camera thread to terminate.
    # Tell the motors it is all over now that the camera is completed. 
    StopMotors() # Tell the motors to immediately stop. 
    print ('\n' + textcolor.cursordown(10) + textcolor.clearforward()) # Move cursor below the ObservationRun display and clear the rest of the screen to make way for the menu.
    if Parameters.GeneratePreview and Parameters.GeneratePreviewVideo and not CameraInUse.FastImageCapture: # Preview images were requested, and could have been captured.
        #if AskYesNo("Do you want to generate an AVI animation of the preview files? [y/N]",False): # We can generate a small animation of the observation from the preview images.
        #    GeneratePreviewMovie()
        GeneratePreviewMovie()
    if Parameters.GenerateKeogram or Session.Target.ObjectType in ['aurora']: # Generate Keogram at end of observation.
        MainLog.Log("Generating Keogram from observation images.",terminal=True)
        CameraInUse.BuildKeogram(altitude=alt,azimuth=az)
    is_filename = FolderHandler.PrepFile('light','BatchData_' + UtcTimeStamp() + '.json')
    CameraInUse.SaveBatchData(is_filename) # Save the list of image files as .json document.

    ReportObservationErrors()

    textcolor.TextBox("The images are stored in " + FolderHandler.GetPath('session'),fg=textcolor.YELLOW,bg=textcolor.BLACK)
    if CameraInUse.FastImageCapture and CameraInUse.CameraSaveDng: # Only JPG files have been created so far.
        print(textcolor.yellow("FastImageCapture is active. Only the raw JPG data files have been created so far."))
        print(textcolor.yellow("If you want to create separate DNG files, or pure JPG files you still need to process them."))
        
    # End of observation...    
    Session.SetMotorControlMode('idle') # The motors should now be idle.
    FlagObservationEnd() # Mark that the observation run has completed successfully. This tells the next observationrun that all is OK. It's also called by the menu for safety.
    
    MainLog.Log("ObservationRun: end.",terminal=False)
    return observationresult,observationstatuslist

# ----------------------------------------------------------------------------------------------------- 

def AddAngles(angle1,angle2):
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


def DisableCleanup(): # For menu
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        print ("The Raspberry Pi HQ sensor performs some on-chip image cleanup.")
        print ("On-chip cleanup may degrade the raw image data.")
        print ("It is recommended to disable this feature for astrophotography.")
        if Parameters.CameraDriver == 'raspistill':
            print ("- You may get warning messages displayed by this action, they are generally OK to ignore.")
            if AskYesNo("Disable on-sensor cleanup? [y/N]",False):
                SensorInUse.DisableCleanup()
                DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
                DocumentSession()
                DriftTracker.Reset()
        else:
            print ("- With libcamera installations you should edit the --denoise parameter in the command templates.")
            print ("  The '--denoise off' option will disable cleanup.")

# ------------------------------------------------------------------------------------------------

def EnableCleanup(): # For menu
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        print ("The Raspberry Pi High Quality camera can perform some on-chip image cleanup.")
        print ("It is often disabled for astrophotography because it degrades the raw image data slightly.")
        print ("It is recommended to enable this for regular photography.")
        if Parameters.CameraDriver == 'raspistill':
            if AskYesNo("Enable on-sensor cleanup? [y/N]",False):
                print ("- You may get warning messages displayed by this action, they are generally OK to ignore.")
                SensorInUse.EnableCleanup()
                DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
                DocumentSession()
                DriftTracker.Reset()
        else:
            print ("- With libcamera installations you should edit the --denoise parameter in the command templates.")
            print ("  Removing the '--denoise off' option will enable cleanup.")
    
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
    if constellation is None:
        constellation = ''
    else:
        constellation = "(" + constellation + ") "
    type = Session.Target.ObjectType
    if type is None:
        type = ''
    else:
        type = '(' + type + ') '
    TS = " Target: " + Session.Target.Name + " "
    TS += type
    TS += constellation
    result.append(TS)
    TS = " Mag: " + str(Session.Target.Magnitude) + " "
    az, alt = Session.Target.AzAltDegrees()
    TS += AzAltText(az,alt,DegreeSymbol)
    if Session.Target.Visible(): TS += " (in range)"
    else: TS += " (out of range)"
    result.append(TS)
    return result

# ------------------------------------------------------------------------------------------------------

def SensorStrings():
    """ Return a string showing the current sensor/image settings. """
    SS = " Sensor: Mode " + str(SensorInUse.Mode) + ", Dimensions " + str(SensorInUse.PixelWidth) + "x" + str(SensorInUse.PixelHeight)
    if SensorInUse.OnChipCleanup:
        SS += " OnChipCleanup ON."
    else:
        SS += " OnChipCleanup OFF."
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
    if CameraInUse.CameraSaveFits: ES += "fits "
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

def SessionStrings():
    """ Return a string listing current session details. """
    SS = " Session: " + FolderHandler.GetPath("session")
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
    PS = " Program started: " + DisplayDT(Session.ProgramStartTime) + " (" + delta + ")" # Show in local time.
    return [PS]

# ------------------------------------------------------------------------------------------------------

def MicrocontrollerStrings():
    """ Return a string listing microcontroller status. """
    PS = " Microcontroller: RPi>Mctl " + HRBytes(Mctl.BytesSent) + ", Mctl>RPi " + HRBytes(Mctl.BytesReceived) + "."
    return [PS]
    
# ------------------------------------------------------------------------------------------------------

def SimplifyRaDec(string):
    """ Take strings like .... 
           09h 11m 04.19s
           +16deg 14' 32.8"
        And return just the numbers and spaces.
           09h 11m 04.19s         -> 09 11 04.19
           +16deg 14' 32.8"       -> 16 14 32.8
           -16deg 14' 32.8"       -> -16 14 32.8
    """
    validcharacters = [' ','-','0','1','2','3','4','5','6','7','8','9']
    result = ''
    for c in string:
        if c in validcharacters:
            result += c
    return result
        
# ------------------------------------------------------------------------------------------------------

def TechFitsHeaderTags(filename):
    """ Generate a file with the technical details recorded ready for 
        pilomarfits.py to generate the correct .FITS file headers. """
    # Write FITS file header tags for the session. This provides data for the observation target, observer's location and equipment used.
    # This is used by pilomarfits to populate some of the .FITs file header tags.
    # - NOTE: src/pilomarfits.py will add further tags taken from the image metadata when an exposure is made.
    #         the tags created here are generally related to other image attributes which the camera is unaware of.
    ra,dec = Session.Target.RaDecHours() # Current ra/dec of target.
    # Calculate the FILTER tags for any .FITS files that are generated.
    filtercode = ''
    filtercomment = ''
    if Parameters.IRFilter: # Infrared cutoff filter is in place.
        filtercode = 'IR'
        filtercomment = 'IR cutoff filter'
    else: # Infrared cutoff filter is not in place.
        filtercode = 'NOIR'
        filtercomment = 'No IR cutoff filter'
    if Parameters.PollutionFilter: # A pollution filter is in place.
        if filtercode != '':
            filtercode += ','
            filtercomment += ','
        filtercode += 'POLLUTION'
        filtercomment += 'Light pollution'
    if Parameters.SolarFilter: # A solar filter is in place.
        if filtercode != '':
            filtercode += ','
            filtercomment += ','
        filtercode += 'SOLAR'
        filtercomment += 'Solar filter'
    # Construct fits tag dictionary. 
    # There are all applied 'as is' to the FITS header.
    lov = Parameters._HomeLonVal
    lav = Parameters._HomeLatVal
    if Parameters.ImagePrivacy.lower().startswith('h'): # High
        lov = lav = 0
    elif Parameters.ImagePrivacy.lower().startswith('m'): # Medium
        lov = int(lov)
        lav = int(lav)
    fitstags = {
        "TELESCOP":{'value':ProgramTitle.upper(), 
                    'comment':"Pilomar minature observatory."},
        "FOCALLEN":{'value':LensInUse.Length, 
                    'comment':str(LensInUse.Length) + "mm (" + str(LensInUse.EquivLength) + " 35mm equivalent)."},
        "FOVHOR":  {'value':LensInUse.FovHorizontal,
                    'comment':'Horizontal field of view (deg).'},
        "FOVVER":  {'value':LensInUse.FovVertical,
                    'comment':'Vertical field of view (deg).'},
        "OBJECT":  {'value':Session.Target.Name.upper(), 
                    'comment':Session.Target.Name},
        "RA":      {'value':SimplifyRaDec(str(ra)),
                    'comment':'Target right ascension (hh mm ss.ss).'},
        "DEC":     {'value':SimplifyRaDec(str(dec)),
                    'comment':'Target declination (ddd mm ss.ss).'},
        "LONG-OBS":{'value':round(lov,1),
                    'comment':"Observer's longitude (deg)."},
        "LAT-OBS": {'value':round(lav,1),
                    'comment':"Observer's latitude (deg)."},
        "SITELONG":{'value':round(lov,1),
                    'comment':"Observer's longitude (deg)."},
        "SITELAT": {'value':round(lav,1),
                    'comment':"Observer's latitude (deg)."},
        "FILTER":  {'value':filtercode,
                    'comment':filtercomment},
        "COMMENT": {'value':SourceCode().upper() + " " + VERSION + " " + str(SourceDate()),
                    'comment':"Observatory software."}
    }
    # Write fits header tags as .json file. This is picked up by src/pilomarfits.py when generating .fits images.
    with open(filename,'w') as f:
        json.dump(fitstags, f)
        
# ------------------------------------------------------------------------------------------------------

def TechExifHeaderTags(filename):
    """ Generate a file with the technical details recorded ready for 
        pilomarfits.py to generate the correct .jpg file exif tags. """
    # Write exif file header tags for the session. This provides data for the observation target, observer's location and equipment used.
    # This is used by pilomarfits to populate some of the .JPG exif tags.
    # - NOTE: src/pilomarfits.py will add further tags taken from the image metadata when an exposure is made.
    #         the tags created here are generally related to other image attributes which the camera is unaware of.
    # Construct exif tag dictionary. 
    lad, lam, las = AngleToDMS(abs(Parameters._HomeLatVal))
    if Parameters._HomeLatVal >= 0: lar = "N"
    else: lar = "S"
    lod, lom, los = AngleToDMS(abs(Parameters._HomeLonVal))
    if Parameters._HomeLonVal >= 0: lor = "E"
    else: lor = "W"
    hc = os.uname().nodename
    ow = Parameters.Owner
    if Parameters.ImagePrivacy.lower().startswith('h'): # High
        hc = "pilomar" # For privacy don't give the hostname.
        lad = lam = las = lod = lom = los = 0 # Don't give home location.
        lar = "N"
        lor = "E"
        ow = "pilomar"
    elif Parameters.ImagePrivacy.lower().startswith('m'): # Medium
        lad = int(round(lad,0)) # Home location only to degree accuracy.
        lod = int(round(lod,0))
        lam = las = lom = los = 0
    # Otherwise ImagePrivacy is 'low' and full location is stored in the exif metadata.
    exiftags = {
     "Copyright": ow, # Who owns the photograph?
     "HostComputer": hc, # 'pilomar'
     "ImageDescription": Session.Target.SearchGroup + ":" + Session.Target.Name + " " + str(CameraInUse.ExposureSeconds) + "s",
     "ImageHistory": "pilomar_image", # 'pilomar image'
     "Make": "Sony", # "sony"
     "Model": SensorInUse.Type,
     "ProcessingSoftware": ProgramTitle + " " + VERSION,
     "Software": ProgramTitle + " " + VERSION,
     "GPSDateStamp": str(NowUTC()),
     "GPSLatitude": [int(lad),int(lam),int(las)],
     "GPSLatitudeRef": lar,
     "GPSLongitude": [int(lod),int(lom),int(los)],
     "GPSLongitudeRef": lor,
     "CameraOwnerName": ow,
     "FocalLength": LensInUse.Length, # mm
     "FocalLengthIn35mmFilm": LensInUse.EquivLength # mm
     # Tags provided by image capture routine (eg pilomarfits)...
     #"DateTime": NowUTC(),
     #"DocumentName": exif_dict["0th"][piexif.ImageIFD.DocumentName] = self.exif_string(value) # "light_yyyymmddhhmmss_01")
     #"ExposureTime": exif_dict["0th"][piexif.ImageIFD.ExposureTime] = self.exif_float(value) # 0.5) # seconds. (Store as numerator/denominator, so 0.5 = (5,10)
     #"ImageID" # "light_yyyymmddhhmmss_01"
     #"DateTimeOriginal": exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = self.exif_datetime(value) # self.NowUTC())
     #"DateTimeDigitized": exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = self.exif_datetime(value) # self.NowUTC())
     #"ExposureMode": exif_dict["Exif"][piexif.ExifIFD.ExposureMode] = self.exif_int(value) # 1) # Exposure mode - manual.
     #"ShutterSpeedValue": exif_dict["Exif"][piexif.ExifIFD.ShutterSpeedValue] = self.exif_float(value) # 0.5) # Exposure seconds.
     # Tags provided by weather service...
     #"Humidity": exif_dict["Exif"][piexif.ExifIFD.Humidity] = self.exif_float(value) # 80.0) # Percentage
     #"Pressure": exif_dict["Exif"][piexif.ExifIFD.Pressure] = self.exif_float(value) # 990.0) # hPa.
     #"Temperature": exif_dict["Exif"][piexif.ExifIFD.Temperature] = self.exif_float(value) # -10.0) # C 
    }
    # Write exif header tags as .json file. This is picked up by src/pilomarfits.py when generating .jpg images.
    with open(filename,'w') as f:
        json.dump(exiftags, f)
        
# ------------------------------------------------------------------------------------------------------

def DocumentSession():
    """ Create a brief description of the session and key parameters.
        Details are written to a disc file.    """
        
    # Write FITS file header tags for the session. This provides data for the observation target, observer's location and equipment used.
    # This is used by pilomarfits to populate some of the .FITs file header tags.
    # - NOTE: src/pilomarfits.py will add further tags taken from the image metadata when an exposure is made.
    #         the tags created here are generally related to other image attributes which the camera is unaware of.
    Session.TechFitsTagsFile = FolderHandler.PrepFile('session','fitstags_t.json') # What file will be used to share the data across processes?
    TechFitsHeaderTags(Session.TechFitsTagsFile)
    # Write jpeg EXIF file with tags for the session. This provides data for the observation target, observer's location and equipment used.
    # This is used by pilomarfits to populate some of the .JPG exif tags.
    # - NOTE: src/pilomarfits.py may add further tags taken from the image metadata when an exposure is made.
    #         the tags created here are generally related to other image attributes which the camera is unaware of.
    Session.TechExifTagsFile = FolderHandler.PrepFile('session','exiftags_t.json') # What file will be used to share the data across processes?
    TechExifHeaderTags(Session.TechExifTagsFile)
    
    # Write a text file listing current parameters and settings for the observation session.
    with open(FolderHandler.PrepFile('session','info.txt'),'w') as f:
        f.write("# " + ProgramTitle.upper() + " session settings:\n")
        f.write("Program started\t" + str(Session.ProgramStartTime) + "\n")
        f.write("Source code\t" + SourceCode() + "\n")
        f.write("Source version\t" + str(SourceDate()) + "\n")
        f.write("Session started\t" + str(NowUTC()) + "\n")
        f.write("Session path\t" + FolderHandler.GetPath("session") + "\n")
        f.write("Target\t" + Session.Target.Name + "\n")
        f.write("SearchGroup\t" + Session.Target.SearchGroup + "\n")
        f.write("SearchTerm\t" + Session.Target.SearchTerm + "\n")
        f.write("Exposure time\t" + str(CameraInUse.ExposureSeconds) + "seconds\n")
        f.write("Sensor mode\t" + str(SensorInUse.Mode) + "\n")
        f.write("Image width\t" + str(SensorInUse.PixelWidth) + "\n")
        f.write("Image height\t" + str(SensorInUse.PixelHeight) + "\n")
        f.write("Maximum exposure time\t" + str(SensorInUse.MaxExposureSeconds) + "seconds\n")
        f.write("Sensor type\t" + SensorInUse.Type + "\n")
        f.write("Focal length\t" + str(LensInUse.Length) + "\n")
        f.write("35mm Equivalent focal length\t" + str(LensInUse.EquivLength) + "\n")
        f.write("Pixels per FOV degree width\t" + str(CameraInUse.PixelsPerFovDegreeWidth) + "\n")
        f.write("Pixels per FOV degree height\t" + str(CameraInUse.PixelsPerFovDegreeHeight) + "\n")
        f.write("Infrared filter\t" + str(Parameters.IRFilter) + "\n")
        f.write("Light pollution filter\t" + str(Parameters.PollutionFilter) + "\n")
        f.write("Timelapse delay\t" + str(CameraInUse.TimelapseSeconds) + "seconds\n")
    # Append key values to 'recent target list'. This is useful if recovering from system failure, or resuming a previous observation at a later date.
    # When selecting a new target, this recent target list is offered as a short-cut to duplicate previous observations.
    if CameraInUse.TimelapseSeconds == 0.0: CIU_TS = None # Timelapse value 0.0  needs to be None! Set to None in the sessionentry.
    else: CIU_TS = CameraInUse.TimelapseSeconds
    SessionHistory.Add({'Name':Session.Target.Name,
                        'SearchGroup':Session.Target.SearchGroup,
                        'SearchTerm':Session.Target.SearchTerm,
                        'ExposureSeconds':CameraInUse.ExposureSeconds,
                        # 'SensorMode':SensorInUse.Mode,
                        'LastObserved':str(NowUTC()),
                        'TimelapsePeriod':CameraInUse.TimelapseSeconds})
    SessionHistory.SortByAge() # Sort youngest first.
    SessionHistory.SaveAsJson(HistoryJsonFile,limit=Parameters.SessionHistoryLimit) # Only save the xxx most recent targets.

    return

# ------------------------------------------------------------------------------------------------------

def SummariseObservationParameters():
    """ Construct a string listing the observation parameters. 
        Used to confirm that it's OK to start an observation. """
    result = ''
    result += 'Observation of ' + Session.Target.Name + ' will capture ' + str(int(Parameters.BatchSize)) + " images of " + str(CameraInUse.ExposureSeconds) + 's. ('
    if CameraInUse.CameraSaveJpg: result += "jpg "
    if CameraInUse.CameraSaveDng: result += "dng "
    if CameraInUse.CameraSaveFits: result += "fits "
    result = result.strip() + ")"
    return result

# ------------------------------------------------------------------------------------------------------

# Document the default session which has been defined by the startup questions.
# If the menu is used to change key parameters, a fresh session will be created at the same time.
DocumentSession() # Write a summary document with key info into the session folder.

# ------------------------------------------------------------------------------------------------------

def FlushCommandQueue(): # For menu
    Mctl.WriteFlush(send=False)
    Mctl.ReadFlush()

# ------------------------------------------------------------------------------------------------------

def ShowParameters(): # For menu
    Parameters.Show()

# ------------------------------------------------------------------------------------------------------

def EditParameters(): # For menu
    # global Parameters
    Parameters.SaveAttributes(Parameters.ParamFileName) # Save current values.
    osCmd("cp " + Parameters.ParamFileName + " " + Parameters.ParamFileName.split(".")[0] + "_" + CleanDatetimeString(UtcTimeStamp()) + ".bak") # Backup current values.
    os.system("nano " + Parameters.ParamFileName) # Edit
    Parameters.LoadParameters() # Reload into memory - this prevents OLD values overwriting the new ones when you exit the program.
    Parameters.RequireRestart = True # Flag that the parameters are nolonger safe until the program is restarted.
    RestartRequired() # Warn the user that the software now needs to be restarted.
    _ = input(textcolor.cyan("[ENTER] to continue"))    

# ------------------------------------------------------------------------------------------------------

def EditTargetHistory(): # For menu
    osCmd("cp " + HistoryJsonFile + " " + HistoryJsonFile.split(".")[0] + "_" + CleanDatetimeString(UtcTimeStamp()) + ".bak") # Backup current values
    os.system("nano " + HistoryJsonFile) # Edit

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
    if CheckImageSet(): # Only allow a change if the current image set is acceptable.
        Session.Target = TargetSelection() # Returns a Target class.
        CameraInUse.SetObservationParameters() # Set target specific parameters for the camera.
        DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
        DocumentSession()
        DriftTracker.Reset()
        ProgramStatus() # Show current situation of the telescope and target.

# ------------------------------------------------------------------------------------------------------

def BeginObservation(): # For menu
    if Parameters.RequireRestart: # Warn that movements cannot be made until software is restarted.
        RestartRequired()
        return
    print(textcolor.yellow(SummariseObservationParameters()))
    if AskYesNo('OK to start observation? [y/N]',default=False):
        result, statuslist = ObservationRun()
        if not result:
            MainLog.Log("BeginObservation: ObservationRun returned False.",terminal=False)
        MainLog.Log("BeginObservation: Status list:",statuslist,terminal=False)

# ------------------------------------------------------------------------------------------------------

def MenuGoToTarget(): # For menu
    GoToTarget(Session.Target)

# ------------------------------------------------------------------------------------------------------

def SetTimelapseDelay(): # For menu
    CameraInUse.SetTimelapse(SetCameraTimelapse(CameraInUse.TimelapseSeconds))

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
    print(textcolor.yellow("Process image files:"))
    print("If you used FastImageCapture the image files have not been fully processed.")
    print("For example now RAW (.dng) extraction may have been done yet.")
    print("This option will run through all the image files captured so far")
    print("and make sure that each image is fully processed.")
    if AskYesNo("Do you want to continue? [y/N]",False):
        CameraInUse.ProcessImageFiles()
    else:
        print("No further processing done.")
        
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
    tNow = NowUTC()
    #tLoc = UTCtoLocal(tNow)
    temp = " " + ProgramTitle.upper() + " " + VERSION + " "
    ltemp = len(temp) # Remember where the timestamp begins in the line, the 2nd line aligns with it.
    temp += str(tNow).split('.')[0] + " UTC"
    if Session.DebugMode: # In debug mode, warn the user.
        temp += ' (DEBUG MODE)'
    #temp = (" " + ProgramTitle.upper() + " " + VERSION + " " + (str(tNow).split('.')[0]) + " UTC")
    listlines.extend([temp])
    if Parameters.DisplayTZ != 'UTC': # User has selected a non UTC timezone for displays.
        temp2 = " " * ltemp # Place local timestamp directly underneath UTC timestamp.
        temp2 += DisplayDT(tNow)
        listlines.extend([temp2]) # Display in local timezone.
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

def ShowColorMap(): # For menu
    """ Development utility. Show the textcolor colors available. """
    textcolor.listcolors()
    Parameters.ShowColorScheme()

# ------------------------------------------------------------------------------------------------------

def ScanForMeteors(): # For menu
    print (textcolor.yellow("This will scan all available 'light' image files for potential meteor trails."))
    print (textcolor.yellow("Press 'x' to quit"))
    CameraInUse.MeteorFileScan() # Scan all available 'light' jpg files for potential meteor traces. Ignore the returned list of filenames.
    
# ------------------------------------------------------------------------------------------------------

def MenuSatellitePasses():
    """ Run the SatellitePasses method to list satellite passes in the next few days. """
    Session.Target.SatellitePasses(window=144)

# ------------------------------------------------------------------------------------------------------


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

def ZipMotorStatusLog():
    MainLog.Log("ZipMotorStatusLog",terminal=True)
    zipfile = MainLog.PackageSearchResult('RPi received: motor status',ignorecase=True)
    MainLog.Log("ZipMotorStatusLog: Generated",zipfile,terminal=True)

# ------------------------------------------------------------------------------------------------------

def MonitorCommsHelp():
    """ Show the functions available in the MonitorComms utility. """
    lines = ["         Monitor Microcontroller Communication",
             " ",
             "This shows UART traffic between RPi and Microcontroller.",
             " ",
             "'r' Reset microcontroller  'p' Pause monitoring",
             "'f' Flash LED Yellow       'c' Send manual command",
             "'x' Exit                   '?' This help."
            ]
    textcolor.TextBox(lines,fg=textcolor.YELLOW,bg=textcolor.BLACK)

# ------------------------------------------------------------------------------------------------------

def MonitorComms():
    """ For a period mirror microcontroller communication to the terminal. """
    MonitorCommsHelp() # Show initial help.
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
        elif keypress == 'c': # Send manual commands to the microcontroller.
            Mctl.SendManualCommand()
            print("To send another command press 'c' again.")
        elif keypress == '?': # Reprint the help list of commands.
            MonitorCommsHelp()
        elif keypress == 'p': # Pause display.
            Mctl.ToggleMonitor() # Toggle replication on/off.
            if Mctl.PrintComms:
                print("Resumed.")
            else:
                print("Paused: New messages ignored. 'p' to restart.")
                print("You can still send commands, reset etc.")
        time.sleep(0.5)
    Mctl.EndMonitor() # Turn off replication to the terminal.

# ------------------------------------------------------------------------------------------------------

def ShowMotorStatus():
    """ Show the status of all the motors. """
    print(textcolor.yellow("Motor status"))
    
    print("  Backlash enabled:",Parameters.BacklashEnabled)
    print("   Fault sensitive:",Parameters.FaultSensitive)
    print("Motor status delay:",Parameters.MotorStatusDelay,"s")
    print("  Restart required:",Parameters.RequireRestart) # Parameters have been changed, system needs restart.
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
    
    if Parameters.UseTracking: print(textcolor.green("Tracking is currently enabled."),textcolor.cyan("(UseTracking parameter)"))
    else: print(textcolor.red("Tracking is currently disabled."),textcolor.cyan("(UseTracking parameter)"))
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
    print("      Brightness: mag",Parameters.TargetMinMagnitude,textcolor.cyan("(TargetMinMagnitude parameter)"),bNote)
    print("                  mag",Parameters.TargetMinMagnitude - 0.2,"would generate fewer stars.")
    print("                  mag",Parameters.TargetMinMagnitude + 0.2,"would generate more stars.")
    print(" Hipparcos limit: mag",Parameters.LocalStarsMagnitude,textcolor.cyan("(LocalStarsMagnitude parameter)")) # Cannot exceed this value without reloading LocalStars list.
    print("")

    print(textcolor.white("Search zones"))
    print("        Map span:",Session.Target.TrackingMapSpan,textcolor.cyan("(TrackingMapSpan parameter)"))
    print("        Map span: (",(Session.Target.TrackingMapSpan ** 2),"times the camera's field of view)")
    print("Max zone matches:",Parameters.TrackingZoneMatches)
    print("      Zone shift:",int(100 * Parameters.TrackingZoneShift),"%",textcolor.cyan("(TargetZoneShift parameter:",Parameters.TrackingZoneShift,")"))
    print("  (Zone overlap):",int(100 * (1 - Parameters.TrackingZoneShift)),"%")
    print("")
    DescribeSearchParameters() # Explain the result of the above parameters.

    print(textcolor.white("Latest parameters (captured image)"))
    print("   Exposure time:",Parameters.TrackingExposureSeconds,"s",textcolor.cyan("(TrackingExposureSeconds parameter)"))
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
        print("      Drift dx,dy:",round(DriftTracker.dx,0),",",round(DriftTracker.dy,0))
    else:
        print("      Drift dx,dy: NOT CALCULATED YET.")
    print("")

    print(textcolor.white("Star generation/detection"))
    # Star detection.
    print("  Enhance images:",Parameters.LatestTrackingFilter,textcolor.cyan("(LatestTrackingFilter parameter)"))
    
    # Processing of the TARGET image.
    print("     Target image: Loaded",DriftTracker.TargetImage.ImageExists(),DriftTracker.TargetTimeStamp)
    BadThreshold = 50
    PoorThreshold = 70
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
    print("")
    
    print("Board type:",Parameters.BoardType)
    if Session.ValidControllerVersion():
        print("Microcontroller program version:",textcolor.green(Session.ControllerVersion),"(good)") # We like this version.
    else:
        print("Microcontroller program version:",textcolor.red(Session.ControllerVersion),"(check)") # We don't trust this version.
    print("Acceptable microcontroller versions:",ACCEPTABLECONTROLLERVERSIONS) # What microcontroller versions are acceptable?
    print("  (",SourceCode(),VERSION,"is compatible with these microcontroller software versions.)")
    print("Reset PIN:",Mctl.ResetBCM) # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
    print("  (Controls RESET / Power via the GPIO connection.)")
    print("Received line queue:",len(Mctl.Lines)) # Number of lines received but not yet processed.
    print("  (Messages received from microcontroller but not yet processed.)")
    print("Write chunk size:",Mctl.WriteChunkBytes,"bytes")
    print("  (Data is sent to microcontroller in packets of this size.)")
    print("Write chunk gap:",Mctl.WriteChunkSeconds,"s") # Seconds between chunks written to microcontroller.
    print("  (Seconds between each packet sent to the microcontroller.)")
    print("Current receiving line:",Mctl.InputLine)
    print("Write queue length:",len(Mctl.WriteQueue))
    print("  (Messages waiting to be transmitted to the microcontroller.)")
    temp = str(Mctl.LinesReceived)
    if Mctl.LinesReceived < 1:
        temp = textcolor.red(temp) # Highlight in RED that nothing received.
    print("Lines received:",temp)
    print("  (Number of messages received since last reset.)")
    print("Lines sent:",Mctl.LinesSent)
    print("  (Number of messages sent since last reset.)")
    temp = str(Mctl.BytesReceived)
    if Mctl.BytesReceived < 1:
        temp = textcolor.red(temp) # Highlight in RED that nothing received.
    print("Bytes received:",temp)
    print("Bytes sent",Mctl.BytesSent)
    print("Monitor communications:",Mctl.PrintComms) # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
    print("LEDs active:",Mctl.LedStatus) # LEDS on by default.
    print("  (LEDs can be disabled to reduce light pollution in the dome.)")
    print("")
    if os.path.exists(Mctl.Port): temp = "(port path found.)"
    else: temp = textcolor.red("(port path not found)")
    #print("UART port:",Mctl.Port,temp)
    Mctl.ListSerialPorts(terminal=True) # List any recognised serial ports.
    print("    Default for RPi",Hardware.rpi_num,":",SystemUARTPort())
    print("    UART override parameter:",Parameters.UARTOverride)
    print("UART line opened:",DisplayDT(Mctl.LineOpenedTime))
    print("UART Last Tx:",DisplayDT(Mctl.LastTxTime)) # When was data last sent?
    temp = DisplayDT(Mctl.LastRxTime)
    if Mctl.LastRxTime is None or Mctl.LastRxTime <= Mctl.LineOpenedTime: # Nothing received.
        temp = textcolor.red(temp) # Highlight nothing received.
    print("UART Last Rx:",temp) # When was data last received?
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
    print("Protect USB:",Hardware.pcb_protect_usb) # Don't allow GPIO power pin to be activated.
    if Mctl.PoweredByUsb:
        print("  The Reset pin will not be enabled.")
        print("  (The microcontroller is powered via the USB connection.)")
    if Mctl.DeviceFailure: temp = textcolor.red(str(Mctl.DeviceFailure))
    else: temp = str(Mctl.DeviceFailure)
    print("Device failure:",temp) # Set to TRUE if device seems to be irrecoverably lost.
    if Mctl.DeviceFailure:
        print(textcolor.red("  The microcontroller is considered irrecoverably lost."))
    print("Write queue prohibit:",Mctl.WriteProhibited) # OK to add to the write queue.
    if Mctl.WriteProhibited:
        print("  (The program will not send data to the microcontroller.)")
    if Session.MctlExceptionCount != 0: # The microcontroller has handled some exceptions.
        print("Exceptions handled:",textcolor.yellow(Session.MctlExceptionCount))
        print("  (The microcontroller has caught some runtime exceptions.)")
    else: # No exceptions have been caught by the microcontroller.
        print("Exceptions handled:",Session.MctlExceptionCount)
        print("  (The microcontroller has not reported any runtime exceptions.)")
    print("Outbound message counter:",Mctl.SendId) # Incremental counter, the message number being sent to the microcontroller.
    print(textcolor.yellow("Reported measures (if available):"))
    print("Reset reason:",Mctl.ReportedResetReason) # eg 'POWER_ON' # RESET REASON if reported.
    print("Clockspeed:",int(Mctl.ReportedClockspeed),"Hz") # Clock speed in MHz
    print("Voltage:",Mctl.ReportedVoltage,"V") # CPU voltage if known
    print("Allocated memory:",Mctl.ReportedMemAlloc) # Memory allocated (bytes)
    print("Free memory:",Mctl.ReportedMemFree) # Memory free (bytes)
    print("Temperature:",Mctl.ReportedTemperature,"C") # CPU temperature (C)
    print("Features:",Mctl.ReportedFeatures) # Features reported by code.py on microcontroller.
    
    print(textcolor.yellow("PCB indicators (if available):"))
    #print("PCB autodetect:",Parameters.PCBAutoDetect)
    #print("Tiny flag pin:",Parameters.TinyFlagPin)
    print("Microcontroller family:",Hardware.pcb_mctl_family)
    #print("USB protect flag pin:",Parameters.UsbProtectFlagPin)
    print("Protect USB power:",Hardware.pcb_protect_usb)
        
# ------------------------------------------------------------------------------------------------------

def AboutCamera():
    """ Display information about the camera. """
    print(textcolor.yellow("About Camera"))
    
    print(textcolor.white(" O/S"))
    print("  CameraDriver:",Parameters.CameraDriver,"(",Hardware.os_version_name,")")
    print("  CameraDetected:",textcolor.booltocolor(DetectCamera()))
    
    print(textcolor.white(" CameraHandler"))
    try:
        print("  CameraHandler running:",textcolor.booltocolor(CameraThread.is_alive()))
    except:
        print("  CameraHandler running:",textcolor.red("False"),"(not found)")

    print(textcolor.white(" Sensor"))
    print("  Sensor width:",SensorInUse.PixelWidth,"px")
    print("  Sensor height:",SensorInUse.PixelHeight,"px")
    print("  Max exposure:",SensorInUse.MaxExposureSeconds,"s")
    print("    The longest exposure time supported by the camera.")
    print("  Min exposure:",SensorInUse.MinExposureSeconds,"s")
    print("    The shortest exposure time supported by the camera.")
    print("  Sensor type:",SensorInUse.Type)
    print("    Defines characteristics of the camera.")
    #print("  Sensor ID:",SensorInUse.ID)
    print("  Sensor mode:",SensorInUse.Mode)
    if Parameters.CameraDriver == 'raspistill': # DisableCleanup / OnChipCleanup is handled differently between raspistill and libcamera.
        print("  On chip cleanup:",SensorInUse.OnChipCleanup,textcolor.cyan("(DisableCleanup parameter)"))
    else:
        print("  On chip cleanup:",SensorInUse.OnChipCleanup,textcolor.cyan("(Libcamera command template parameter)"))
    print("  Infrared filter:",Parameters.IRFilter) # Is Infrared filter fitted?
    print("    Information only.")

    print(textcolor.white(" Lens"))
    print("  Base focal length:",LensInUse.BaseLength,"mm (before converters)")
    print("  Focal length:",LensInUse.Length,"mm (including converters) ",
          textcolor.cyan("(Param:",Parameters.LensLength,"mm)"))
    if LensInUse.Length > 16 and Parameters.UseTracking: # Drift tracking doesn't work well with long focal length lenses.
        print(textcolor.yellow("  NOTE: Drift Tracking is active, but less effective with",LensInUse.Length,"mm lenses."))
    print("  35mm equivalent focal length:",LensInUse.EquivLength,"mm")
    print("  Horizontal Field of View:",LensInUse.FovHorizontal,DegreeSymbol,
          textcolor.cyan("(Param:",Parameters.LensHorizontalFov,DegreeSymbol,")"))
    print("  Vertical Field of View:",LensInUse.FovVertical,DegreeSymbol,
              textcolor.cyan("(Param:",Parameters.LensVerticalFov,DegreeSymbol,")"))

    print("  Field of View:",LensInUse.Fov,DegreeSymbol)
    print("  Aperture:","f",LensInUse.Aperture)
    print("    Information only.")
    print("  Pollution filter:",Parameters.PollutionFilter) # Is light pollution filter fitted?
    print("    Information only.")
    
    print(textcolor.white(" Camera"))
    if Parameters.CameraEnabled:
        print("  Camera enabled:",textcolor.green(Parameters.CameraEnabled))
        print("    Live images will be captured by the camera.")
    else:
        print("  Camera enabled:",textcolor.red(Parameters.CameraEnabled))
        print("    Images will be simulated.")
    print("  Exposure time:",CameraInUse.ExposureSeconds,"s")
    print("    Used for live image capture.")
    print("  Tracking exposure time:",CameraInUse.TrackingExposureSeconds,"s")
    print("    Used for drift tracking image capture.")
    print("  Timelapse delay:",CameraInUse.TimelapseSeconds,"s")
    print("    When active this is the delay between each LIGHT image captured.")
    print("  Pixels per horizontal degree:",CameraInUse.PixelsPerFovDegreeWidth)
    print("  Pixels per vertical degree:",CameraInUse.PixelsPerFovDegreeHeight)
    print("  Degrees per horizontal pixel:",round(CameraInUse.PixelFovWidth,4),DegreeSymbol)
    print("  Degrees per vertical pixel:",round(CameraInUse.PixelFovHeight,4),DegreeSymbol)

    print(textcolor.white(" Command templates"))
    print("        Light:",Parameters._CameraLightCommand)
    print("         Dark:",Parameters._CameraDarkCommand)
    print("  Bias/Offset:",Parameters._CameraBiasCommand)
    print("         Flat:",Parameters._CameraFlatCommand)
    print("    Dark flat:",Parameters._CameraDarkFlatCommand)
    print("         Auto:",Parameters._CameraAutoCommand)
    print("     Tracking:",Parameters._CameraTrackingCommand)
    print(" Live preview:",Parameters._CameraLivePreviewCommand)
    print("   Raw switch:",Parameters._CameraRawSwitch)
    
    print(textcolor.white(" Camera handler"))
    print("  Fast image capture parameter:",Parameters.FastImageCapture)
    print("    Default for regular targets.")
    print("  Fast image capture current setting:",CameraInUse.FastImageCapture)
    print("    Setting for the current target.")
    print("  Image types:")
    print("    jpg:",CameraInUse.CameraSaveJpg,textcolor.cyan("(Param:",Parameters.CameraSaveJpg,")"))
    print("    dng:",CameraInUse.CameraSaveDng,textcolor.cyan("(Param:",Parameters.CameraSaveDng,")"))
    print("    fits:",CameraInUse.CameraSaveFits,textcolor.cyan("(Param:",Parameters.CameraSaveFits,")"))

# ------------------------------------------------------------------------------------------------------

def About():
    """ Display version information. """
    print(textcolor.yellow("About",ProgramTitle))
    # Print timestamp.
    tNow = NowUTC()
    MainLog.Log("Started:",DisplayDT(Session.ProgramStartTime),terminal=True)
    MainLog.Log("Now:",tNow,"UTC",terminal=True)
    MainLog.Log("Now:",DisplayDT(tNow),terminal=True)
    # Print O/S and hardware
    MainLog.Log("RPi model:",Hardware.rpi_model)
    MainLog.Log("RPi model number:",Hardware.rpi_num)
    MainLog.Log("RPi OS ID:",Hardware.os_version_id)
    MainLog.Log("RPi OS name:",Hardware.os_version_name)
    MainLog.Log("RPi OS type:",Hardware.os_type)
    MainLog.Log("RPi OS bits:",Hardware.os_bits)
    MainLog.Log("RPi processor:",Hardware.os_proc)
    MainLog.Log("RPi systemkey:",Hardware.os_systemkey)
    MainLog.Log("RPi hostname:",HOSTNAME)
    MainLog.Log("RPi locale:",LOCALE)
    MainLog.Log("TuneOn32Bit parameter:",Parameters.TuneOn32Bit)
    if not LOCALE[1] in ["UTF-8"]: MainLog.Log("RPi locale: Character encoding should be UTF-8.",level='error')
    if not LOCALE[0].startswith('en_'): MainLog.Log("RPi locale: Language should be English.",level='warning')
    
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
    MainLog.Log("GPIO driver:",pilomargpio.GPIO_DRIVER,terminal=True) # What GPIO library is in use?
    
# ------------------------------------------------------------------------------------------------------

def PromptPhotoSettingsMenu():
    """ Capture a LIGHT image, but allow the user to experiment with different settings. 
        The user can overwrite the default settings sent to the raspistill utility. """
    CameraInUse.PromptPhotoSettings(batch_size=1)

# ------------------------------------------------------------------------------------------------------

def ChooseImageTypes():
    """ User can decide which images types to record.
        The image types supported depends upon the operating system.
        Old 32bit operating systems support raspistill and PiDNG. They can generate JPG and DNG files.
        Newer 64bit operating systems support libcamera-still and pilomarfits. They can generate JPG, DNG and FITS files.
        This offers the operating system specific file types available to the user.
        Depending upon the combination of file types chosen it then selects an appropriate camerahandler (raspistill, libcamera, pilomarfits) """
    MainLog.Log("ChooseImageTypes:",terminal=False)
    MainLog.Log("Currently: O/S=",Hardware.os_version_name,", Driver=",Parameters.CameraDriver,
                ": jpg",Parameters.CameraSaveJpg,
                ": dng",Parameters.CameraSaveDng,
                ": fits",Parameters.CameraSaveFits,terminal=False)
    option = None
    AllOptions = {
        'r_jpg':{'label':'JPG only', 'value':'r_jpg', 'SaveJpg':True, 'SaveDng':False, 'SaveFits':False, 'oslist':['buster'], 'handlers':['raspistill']},
        'r_dng':{'label':'DNG only', 'value':'r_dng', 'SaveJpg':False, 'SaveDng':True, 'SaveFits':False, 'oslist':['buster'], 'handlers':['raspistill']},
        'r_jpgdng':{'label':'JPG & DNG', 'value':'r_jpgdng', 'SaveJpg':True, 'SaveDng':True, 'SaveFits':False, 'oslist':['buster'], 'handlers':['raspistill']},
        'l_jpg':{'label':'JPG only', 'value':'l_jpg', 'SaveJpg':True, 'SaveDng':False, 'SaveFits':False, 'oslist':['bookworm'], 'handlers':['libcamera']},
        'l_dng':{'label':'DNG only', 'value':'l_dng', 'SaveJpg':False, 'SaveDng':True, 'SaveFits':False, 'oslist':['bookworm'], 'handlers':['libcamera']},
        'l_jpgdng':{'label':'JPG & DNG', 'value':'l_jpgdng', 'SaveJpg':True, 'SaveDng':True, 'SaveFits':False, 'oslist':['bookworm'], 'handlers':['libcamera']},
        'l_fits':{'label':'FITS only', 'value':'l_fits', 'SaveJpg':False, 'SaveDng':False, 'SaveFits':True, 'oslist':['bookworm'], 'handlers':['pilomarfits']},
        'l_jpgfits':{'label':'JPG & FITS', 'value':'l_jpgfits', 'SaveJpg':True, 'SaveDng':False, 'SaveFits':True, 'oslist':['bookworm'], 'handlers':['pilomarfits']}
    }
    FilteredOptions = {}
    for key,value in AllOptions.items(): # Consider all available combinations of type, OS and driver.
        MainLog.Log("ChooseImageTypes(): Considering",Hardware.os_version_name,"against",key,value['oslist'],terminal=False)
        if Hardware.os_version_name in value['oslist']: # Offer those supported by this OS.
            FilteredOptions[key] = value
            MainLog.Log("ChooseImageTypes(): Accepted",key,terminal=False)
        else:
            MainLog.Log("ChooseImageTypes(): Rejected",key,terminal=False)
    MainLog.Log("ChooseImageTypes: Offering:",FilteredOptions,terminal=False)
    if len(FilteredOptions) < 1: # Didn't find any options to offer.
        MainLog.Log("WARNING: Could not find any options for",Hardware.os_version_name,"o/s",level='warning',terminal=True)
            
    OptionMenu = optionmenu(FilteredOptions,'Select combination',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)
    option, found = OptionMenu.Prompt() # Ask the user to select an option from the menu.
    MainLog.Log("ChooseImageTypes: Chose:", option, found,terminal=False)
    
    if found: # A choice was made.
        Parameters.CameraSaveJpg = AllOptions[option]['SaveJpg']
        Parameters.CameraSaveDng = AllOptions[option]['SaveDng']
        Parameters.CameraSaveFits = AllOptions[option]['SaveFits']
        if not Parameters.CameraDriver in AllOptions[option]['handlers']: # Need to switch handler.
            newdriver = AllOptions[option]['handlers'][0]
            MainLog.Log("ChooseImageTypes: Switching cameradriver from",Parameters.CameraDriver,"to",newdriver,terminal=True)
            Parameters.SetCameraDriver(newdriver)
        CameraInUse.SetObservationParameters() # Update camera settings.
    MainLog.Log("Finally: O/S=",Hardware.os_version_name,", Driver=",Parameters.CameraDriver,
                ": jpg",CameraInUse.CameraSaveJpg,
                ": dng",CameraInUse.CameraSaveDng,
                ": fits",CameraInUse.CameraSaveFits,terminal=True)
    
    return

# ------------------------------------------------------------------------------------------------------

def LivePreview():
    """ Show live preview window of the camera. """
    print(textcolor.yellow('Live preview image from camera'))
    cmd = Parameters._CameraLivePreviewCommand
    print(cmd)
    osCmd(cmd)

# ------------------------------------------------------------------------------------------------------

def ChooseCaptureMode():
    """ User can switch between FULL and FAST capture modes. """
    option = None
    ModeOptions = {
        'full':{'label':'Full capture and process images.', 'value':'full', 'fastmode':False},
        'fast':{'label':'Fast capture, no image processing', 'value':'fast', 'fastmode':True}
    }
    ModeMenu = optionmenu(ModeOptions,'Select capture mode',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

    option, found = ModeMenu.Prompt() # Ask the user to select an option from the menu.
    if found: # A choice was made.
        Parameters.FastImageCapture = ModeOptions[option]['fastmode']
        MainLog.Log("ChooseCaptureMode: FastImageCapture:",Parameters.FastImageCapture)
    return

# ------------------------------------------------------------------------------------------------------

def BuildKeogram():
    """ Build a keogram from the current LIGHT folder. """
    print(textcolor.yellow("Build keogram from current light folder"))
    az, alt = Session.Target.AzAltDegrees() # Get current az/alt of target.
    CameraInUse.BuildKeogram(altitude=alt,azimuth=az) # Center of the image is needed.
    
# ------------------------------------------------------------------------------------------------------

def GpioStatus():
    """ Display the status of any defined GPIO pins. """
    print(textcolor.yellow("GPIO status"))
    for pin in outputpin.OutputPins:
        print(pin.Status(),pin.Name)
    for pin in inputpin.InputPins:
        print(pin.Status(),pin.Name)
    
# ------------------------------------------------------------------------------------------------------

def CurrentStepSettings():
    """ Show current slew and microstep settings. """
    print(textcolor.yellow("Current step/microstep settings"))
    print("Slew enabled:",Parameters.SlewEnabled)
    if Parameters.AzimuthMicrostepRatio == 1:
        print("Observation steps:","Full steps")
    else:
        print("Observation steps:","1/" + str(int(Parameters.AzimuthMicrostepRatio)),"steps")
    if Parameters.AzimuthSlewMicrostepRatio == 1:
        print("Slew steps:","Full steps")
    else:
        print("Slew steps:","1/" + str(int(Parameters.AzimuthSlewMicrostepRatio)),"steps")
    
# ------------------------------------------------------------------------------------------------------

def ConfigMicrostepping(slewmicrosteps,observemicrosteps):
    """ Given slew and observe microstep values, change motor config. """
    MainLog.Log("ConfigMicrostepping: Slew",slewmicrosteps,"Observe",observemicrosteps,terminal=True)
    if slewmicrosteps != 1:
        print("When slewing the telescope for large moves (GOTO/HOME) the motors will use",slewmicrosteps,"microsteps")
    else:
        print("When slewing the telescope for large moves (GOTO/HOME) the motors will use FULL steps")
    if observemicrosteps != 1:
        print("When the telescope is observing the motors will use",observemicrosteps,"microsteps")
    else:
        print("When the telescope is observing the motors will use FULL steps.")

    # Check we're homed.
    CameraAlt, CameraAz = LastReportedAltAz() # What is the last reported alt/az location of the centre of the image?
    HomeAlt, HomeAz = HomeAltAz() # Home position for camera.
    if round(CameraAlt,1) != round(HomeAlt,1) or round(CameraAz,1) != round(HomeAz,1): # Camera is not at home position.
        MainLog.Log("ConfigMicrostepping: The camera needs to be HOMED before changing microstepping.",terminal=True,level='warning')
        return
        
    # Set parameters.
    if slewmicrosteps != observemicrosteps:
        Parameters.SlewEnabled = True # Allow SLEW moves to be faster than OBSERVE moves.
    else:
        Parameters.SlewEnabled = False # SLEW and OBSERVE moves use the same microstepping values.
    Parameters.AzimuthMicrostepRatio = observemicrosteps # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    Parameters.AzimuthSlewMicrostepRatio = slewmicrosteps # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    Parameters.AltitudeMicrostepRatio = observemicrosteps # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    Parameters.AltitudeSlewMicrostepRatio = slewmicrosteps # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.

    if slewmicrosteps == 1 or observemicrosteps == 1:
        if slewmicrosteps == 1: print("Slew moves will use FULL STEPS.")
        if observemicrosteps == 1: print("Observation moves will use FULL STEPS.")
        print("NOTE: FULL STEPS are fast, but noisy.")
        print("      Increasing microstepping values slows the telescope down, but gives quieter and smoother motion.")
    
    # Flag restart required.
    Parameters.RequireRestart = True # Flag that the parameters are nolonger safe until the program is restarted.
    RestartRequired() # Warn the user that the software now needs to be restarted.
    
    # Save parameters.
    print (textcolor.yellow("Saving parameters..."))
    Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
    print (textcolor.yellow("Done."))
    
# ------------------------------------------------------------------------------------------------------

def DescribeSearchParameters(): 
    """ Explain the result of TrackingZoneShift and TrackingMapSpan parameters.
        How many different tracking match attempts will be made? """
    overall_span = Parameters.TrackingMapSpan #  1.0 to 4.0 values.
    span_excess = overall_span - 1.0
    if span_excess > 0: # There can be multiple searches performed to fit the entire span of the search area.
        shifts = 2 * math.floor(span_excess / (2 * Parameters.TrackingZoneShift))
    else:
        shifts = 0 # No extra searches are possible.
    searches_per_axis = 1 + shifts
    searches_per_map = searches_per_axis ** 2
    print(textcolor.white("Search performance:"))
    print("     Tracking map span:",Parameters.TrackingMapSpan,"times the size of the camera field of view.")
    print("   Tracking zone shift:",Parameters.TrackingZoneShift * 100,"% shift between successive searches on each axis.")
    print("     Searches per axis:",searches_per_axis)
    print("      Searches per map:",searches_per_map,"maximum searches performed in a single drift analysis.")
    print("Maximum zones to match:",Parameters.TrackingZoneMatches,"(drift calculation stops when this many matching zones are found, to save time.)")
    print("                        Searches always start in the centre of the map then spread outwards by")
    print("                       ",Parameters.TrackingZoneShift * 100,"% in each direction until the edge of the tracking")
    print("                        map has been reached.")
    print("")
        
# ------------------------------------------------------------------------------------------------------

def SetSearchArea():
    """ Define the search area for tracking to use.
        It's a multiple of the image dimensions. """
    MainLog.Log("SetSearchArea(): Begin",terminal=False)
    print(textcolor.yellow("Set search area size"))
    print("Drift Tracking can search an area larger than the field of view of the camera.")
    print("Pi-lomar generates a target map matching the search area, then tries to find")
    print("the current view within the target map.")
    print(" ")
    print("Select size of the search area here:")
    option = None
    AreaOptions = {
        'a':{'label':'Match the camera field of view (fastest).', 'value':1.0},
        'b':{'label':'4 times the camera field of view (slower).', 'value':2.0},
        'c':{'label':'9 times the camera field of view (slower).', 'value':3.0},
        'd':{'label':'16 times the camera field of view (slowest).', 'value':4.0}
    }
    AreaMenu = optionmenu(AreaOptions,'Select search area size',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG,columns=1)
    option, found = AreaMenu.Prompt() # Ask the user to select an option from the menu.
    if found: # A choice was made.
        Parameters.TrackingMapSpan = option
        MainLog.Log("SetSearchArea: TrackingMapSpan:",Parameters.TrackingMapSpan)
        DescribeSearchParameters() # Explain the outcome of the new parameter.

# ------------------------------------------------------------------------------------------------------
        
def SetSearchOverlap():
    """ Define the overlap between successive samples of the search area. """
    MainLog.Log("SetSearchOverlap(): Begin",terminal=False)
    print(textcolor.yellow("Set search area shift/overlap"))

    print("When drift tracking is searching a large area it performs multiple searches.")
    print("You can select how successive search areas shift from each other here.")
    print("Smaller shifts mean more searches.")
    print(" ")
    print("Select the shift ratio here:")
    option = None
    ShiftOptions = {
        'a':{'label':'Shift 10% between searches (90% overlap) - slowest', 'value':0.1},
        'b':{'label':'Shift 30% between searches (70% overlap)',           'value':0.3},
        'c':{'label':'Shift 50% between searches (50% overlap)',           'value':0.5},
        'd':{'label':'Shift 70% between searches (30% overlap)',           'value':0.7},
        'e':{'label':'Shift 90% between searches (10% overlap) - fastest', 'value':0.9},
    }
    ShiftMenu = optionmenu(ShiftOptions,'Select search shift ratio',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG,columns=1)
    option, found = ShiftMenu.Prompt() # Ask the user to select an option from the menu.
    if found: # A choice was made.
        Parameters.TrackingZoneShift = option
        MainLog.Log("SetSearchOverlap: TrackingZoneShift:",Parameters.TrackingZoneShift)
        DescribeSearchParameters() # Explain the outcome of the new parameter.
        
# ------------------------------------------------------------------------------------------------------

def ChangeHomeLocation():
    """ Allow the user to change the home location and update references to match. """
    MainLog.Log("ChangeHomeLocation(): Begin",terminal=False)
    print(textcolor.yellow("Change home location:"))
    print("You can change the observer's home location here.")
    print("This is useful if you are using pi-lomar in multiple locations.")
    if AskYesNo("Do you want to change your home location? (y/N)",default=False):
        MainLog.Log("ChangeHomeLocation(): Proceeding",terminal=False)
        Parameters.ChooseHome() # Select a new location (from existing, or create new).
        Parameters.EvaluateHomeLocation() # Set dependent parameters.
        Session.Target.SetHome() # Update the Target object for the new home location.
        MainLog.Log("ChangeHomeLocation(): Done",terminal=False)
    else:
        MainLog.Log("ChangeHomeLocation(): No changes made.",terminal=False)

# ------------------------------------------------------------------------------------------------------

def Microstepping_1_1():
    print(textcolor.yellow("No microstepping"))
    ConfigMicrostepping(slewmicrosteps=1,observemicrosteps=1)

# ------------------------------------------------------------------------------------------------------

def Microstepping_2_2():
    print(textcolor.yellow("Slew 1/2 microsteps, Observe 1/2 microsteps."))
    ConfigMicrostepping(slewmicrosteps=2,observemicrosteps=2)

# ------------------------------------------------------------------------------------------------------

def Microstepping_4_4():
    print(textcolor.yellow("Slew 1/4 microsteps, Observe 1/4 microsteps."))
    ConfigMicrostepping(slewmicrosteps=4,observemicrosteps=4)

# ------------------------------------------------------------------------------------------------------

def Microstepping_1_2():
    print(textcolor.yellow("Slew full steps, Observe 1/2 microsteps."))
    ConfigMicrostepping(slewmicrosteps=1,observemicrosteps=2)

# ------------------------------------------------------------------------------------------------------

def Microstepping_1_4():
    print(textcolor.yellow("Slew full steps, Observe 1/4 microsteps."))
    ConfigMicrostepping(slewmicrosteps=1,observemicrosteps=4)

# ------------------------------------------------------------------------------------------------------

def Microstepping_2_4():
    print(textcolor.yellow("Slew 1/2 microsteps, Observe 1/4 microsteps."))
    ConfigMicrostepping(slewmicrosteps=2,observemicrosteps=4)

# ------------------------------------------------------------------------------------------------------

def Microstepping_4_8():
    print(textcolor.yellow("Slew 1/4 microsteps, Observe 1/8 microsteps."))
    ConfigMicrostepping(slewmicrosteps=4,observemicrosteps=8)

# ------------------------------------------------------------------------------------------------------

def MenuAddScheduledTarget():
    """ Choose a target and add it to the observation schedule. """
    temptarget = TargetSelection(optional=True) # User may choose a target, or nothing.
    if temptarget != None:
        temp = "Add " + temptarget.Name + " (" + str(Parameters.BatchSize) + "frames x " + str(CameraInUse.ExposureSeconds) + "s)? [y/N]"
    else:
        temp = "No target selected."
    if temptarget != None and AskYesNo(temp,False):
        ObservationSchedule.Add({'Name':temptarget.Name,
                                 'SearchGroup':temptarget.SearchGroup,
                                 'SearchTerm':temptarget.SearchTerm,
                                 'ObservationFrames':Parameters.BatchSize,
                                 'ExposureSeconds':CameraInUse.ExposureSeconds})
    else:
        MainLog.Log("No additional target added to the schedule.")
    MainLog.Log("Target schedule is currently",len(ObservationSchedule.SessionList),"entries.")

# ------------------------------------------------------------------------------------------------------

def RunObservationSchedule():
    """ Run through the current observation schedule. 
        For each item in the list, set the current target and related parameters.
        Then perform the observation. """
    print(textcolor.yellow("Run observation schedule"))
    MainLog.Log("RunObservationSchedule: Begin",terminal=False)
    ObservationSchedule.DisplayScheduleList()
    for i,se in enumerate(ObservationSchedule.SessionList): # Each one in turn.
        MainLog.Log("RunObservationSchedule: Observation",i,se.Name,se.ObservationFrames,"frames",se.ExposureSeconds,"secs.")
        DevWindow.Print(NowHMS() + " Observation schedule " + str(i) + " " + se.Name)
        DevWindow.Print(NowHMS() + " - " + str(se.ObservationFrames) + "frames @ " + str(se.ExposureSeconds) + "s each.")
        # Set the target.
        obstarget = GetTarget(se.SearchGroup,se.SearchTerm) # Get the target instance.
        if obstarget == None:
            DevWindow.Print(NowHMS() + " Cannot initialize target",i,se.Name,". Skipped")
            MainLog.Log("RunObservationSchedule: Cannot initialize target",i,se.SearchTerm,level='error')
            continue
        Session.Target = obstarget
        # Set the observation parameters.
        CameraInUse.ExposureSeconds = se.ExposureSeconds
        Parameters.BatchSize = se.ObservationFrames
        DefineSessionFolders(Session.Target.Name,CameraInUse.ExposureSeconds) # This assigns folder names for all the image types.
        DocumentSession()
        DriftTracker.Reset()
        # Perform the observation.
        result,statuslist = ObservationRun(batchmode=True) # Batchmode, don't ask low priority questions.
        DevWindow.Print(NowHMS() + " - Observation",i,se.Name,"Result:" + str(statuslist))
        if not result: # Failure
            MainLog.Log("RunObservationSchedule: Target",i,se.Name,"observation failed. Terminating.",terminal=False)
            break
        if 'user:exit' in statuslist: # User chose to terminate the observation. Do they want to continue with the schedule?
            if AskYesNo("Do you want to stop the entire schedule? [y/N]",False):
                MainLog.Log("RunObservationSchedule: User chose to terminate the observation schedule.",terminal=False)
                break
            else:
                MainLog.Log("RunObservationSchedule: User chose to continue the remaining observation schedule.",terminal=False)

    MainLog.Log("RunObservationSchedule: Completed",terminal=False)

# ------------------------------------------------------------------------------------------------------
# Create menu structure.

def SpeedMenuSummary():
    """ Show the current speed settings. """
    print(textcolor.yellow('Current motor speed settings'))
    MainLog.Log("Start step pulse",Parameters.SlowTime * 2,"seconds per step (SlowTime",Parameters.SlowTime,"s)",terminal=True)
    MainLog.Log("Maximum step rate",Parameters.FastTime * 2,"seconds per step (FastTime",Parameters.FastTime,"s)",terminal=True)
    MainLog.Log("Linear acceleration rate",Parameters.TimeDelta * 2,"seconds per step (TimeDelta",Parameters.TimeDelta,"s)",terminal=True)

def SpeedMenu():
    """ Present a list of different motor speed configurations. """
    # Present list of motor speed configurations.
    speed_list = {}
    for key,value in Parameters.SpeedList.items():
        label = value.get('label',key) # If label exists, use that, otherwise show the key.
        speed_list[key] = {'label':label, 'value':key, 'FastTime':value['FastTime'], 'SlowTime':value['SlowTime'], 'TimeDelta':value['TimeDelta']}
    # Choose option.
    SpeedMenu = optionmenu(speed_list,'Select motor step speed',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG,columns=1)
    option, found = SpeedMenu.Prompt() # Ask the user to select an option from the menu.
    if found: # A choice was made.
        MainLog.Log("SpeedMenu: Chose:",option)
    else: # A choice was NOT made.
        MainLog.Log("SpeedMenu: No choice made.",terminal=False)
        return False
    # Select from existing list.
    Parameters.FastTime = speed_list[option]['FastTime']
    Parameters.SlowTime = speed_list[option]['SlowTime']
    Parameters.TimeDelta = speed_list[option]['TimeDelta']
    SpeedMenuSummary() # Show result.
    # Flag restart required. The camera objects need to be renewed.
    Parameters.RequireRestart = True # Flag that the parameters are nolonger safe until the program is restarted.
    RestartRequired() # Warn the user that the software now needs to be restarted.
    return True

StepMenuOptions = {
    'ShowMotorStatus':        {'label':'About motors',              'call':ShowMotorStatus},
    'CurrentStepSettings':    {'label':'Current settings',          'call':CurrentStepSettings},
    'Microstepping_1_1':      {'label':'No microstepping',          'call':Microstepping_1_1},
    'Microstepping_2_2':      {'label':'Slew 1/2, Observe 1/2',     'call':Microstepping_2_2},
    'Microstepping_4_4':      {'label':'Slew 1/4, Observe 1/4',     'call':Microstepping_4_4},
    'Microstepping_1_2':      {'label':'Slew full, Observe 1/2',    'call':Microstepping_1_2},
    'Microstepping_1_4':      {'label':'Slew full, Observe 1/4',    'call':Microstepping_1_4},
    'Microstepping_2_4':      {'label':'Slew 1/2, Observe 1/4',     'call':Microstepping_2_4},
    'Microstepping_4_8':      {'label':'Slew 1/4, Observe 1/8',     'call':Microstepping_4_8}
}
StepMenu = proceduremenu(StepMenuOptions,'Microstepping options',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)
    
MotorMenuOptions = {
    'ShowMotorStatus':        {'label':'About motors',              'call':ShowMotorStatus},
    'HomeAllMotors':          {'label':'Home all motors',           'call':HomePosition},
    'TuneAzimuth':            {'label':'Tune azimuth position',     'call':TunePositionAzimuth},
    'TuneAltitude':           {'label':'Tune altitude position',    'call':TunePositionAltitude},
    'AzimuthAngle':           {'label':'Move azimuth to angle',     'call':AzimuthAngle},
    'AltitudeAngle':          {'label':'Move altitude to angle',    'call':AltitudeAngle},
    'ExerciseAzimuth':        {'label':'Exercise azimuth motor',    'call':ExerciseMotorAzimuth},
    'ExerciseAltitude':       {'label':'Exercise altitude motor',   'call':ExerciseMotorAltitude},
    'MicrosteppingOptions':   {'label':'Microstepping options',     'call':StepMenu},
    'SpeedOptions':           {'label':'Set motor stepping speed',  'call':SpeedMenu},
    'ZipMotorStatusLog':      {'label':'Zip motor status log',      'call':ZipMotorStatusLog},
    'StopAllMotors':          {'label':'Stop all motors',           'call':StopMotors},
}
MotorMenu = proceduremenu(MotorMenuOptions,'Motor tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

def LensMenuSummary():
    """ Show the current lens settings. """
    print(textcolor.yellow('Current lens settings'))
    MainLog.Log("Lens length",str(Parameters.LensLength) + "mm",terminal=True)
    MainLog.Log("Lens horizontal field of view",str(Parameters.LensHorizontalFov) + DegreeSymbol,terminal=True)
    MainLog.Log("Lens vertical field of view",str(Parameters.LensVerticalFov) + DegreeSymbol,terminal=True)

def LensMenu():
    """ Present a list of different lens configurations. """
    # Present list of lens configurations.
    lens_list = {}
    for key,value in Parameters.LensList.items():
        label = value.get('label',key) # If label exists, use that, otherwise show the key.
        lens_list[key] = {'label':label, 'value':key, 'LensLength':value['LensLength'], 'LensHorizontalFov':value['LensHorizontalFov'], 'LensVerticalFov':value['LensVerticalFov']}
    # Choose option.
    LensMenu = optionmenu(lens_list,'Select lens',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG,columns=1)
    option, found = LensMenu.Prompt() # Ask the user to select an option from the menu.
    if found: # A choice was made.
        MainLog.Log("LensMenu: Chose:",option)
    else: # A choice was NOT made.
        MainLog.Log("LensMenu: No choice made.",terminal=False)
        return False
    # Select from existing list.
    Parameters.LensLength = lens_list[option]['LensLength']
    Parameters.LensHorizontalFov = lens_list[option]['LensHorizontalFov']
    Parameters.LensVerticalFov = lens_list[option]['LensVerticalFov']
    LensMenuSummary() # Show result.
    # Flag restart required. The camera objects need to be renewed.
    Parameters.RequireRestart = True # Flag that the parameters are nolonger safe until the program is restarted.
    RestartRequired() # Warn the user that the software now needs to be restarted.
    return True
    
CameraMenuOptions = {
    'AboutCamera':               {'label':'About camera',               'call':AboutCamera},
    'ChooseImageTypes':          {'label':'Choose image types',         'call':ChooseImageTypes},
    'ChooseCaptureMode':         {'label':'Choose capture mode',        'call':ChooseCaptureMode},
    'StartCameraThread':         {'label':'Start camera thread',        'call':StartCameraThread},
    'StopCameraThread':          {'label':'Stop camera thread',         'call':ShutdownCamera},
    'PromptPhotoSettings':       {'label':'Prompt for photo settings',  'call':PromptPhotoSettingsMenu},
    'SensorCleanupOff':          {'label':'Sensor cleanup off',         'call':DisableCleanup},
    'SensorCleanupOn':           {'label':'Sensor cleanup on',          'call':EnableCleanup},
    'AutoDetectCamera':          {'label':'Auto detect camera',         'call':AutoDetectCamera},
    'ChooseLens':                {'label':'Choose lens',                'call':LensMenu},
    'CalibrateFov':              {'label':'Calibrate FoV',              'call':CalibrateFovMenu},
    'LivePreview':               {'label':'Show live preview image',    'call':LivePreview},
    'ProcessImageFiles':         {'label':'Process image files',        'call':ProcessImageFiles},
    'BuildKeogram':              {'label':'Build keogram',              'call':BuildKeogram},
    'EnableCamera':              {'label':'Enable camera',              'call':EnableCamera},
    'DisableCamera':             {'label':'Disable camera',             'call':DisableCamera}
}

CameraMenu = proceduremenu(CameraMenuOptions,'Camera tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MctlMenuOptions = {
    'MicrocontrollerStatus':   {'label':'About motorcontroller',           'call':MicrocontrollerStatus},
    'RestartMicrocontroller':  {'label':'Restart microcontroller',         'call':RestartMicrocontroller},
    'ListSerialPorts':         {'label':'List serial ports',               'call':Mctl.MenuListSerialPorts},

    'StartMessage':            {'label':'Start message handler',           'call':MenuStartMessage},
    'ShutdownMessage':         {'label':'Shutdown message handler',        'call':MenuShutdownMessage},
    'FlushCommandQueue':       {'label':'Flush command queue',             'call':FlushCommandQueue},
    'ZipCommsLog':             {'label':'Zip comms log',                   'call':ZipCommsLog},
    'MonitorComms':            {'label':'Monitor communication',           'call':MonitorComms},
    'MicrocontrollerLedsOn':   {'label':'Microcontroller LEDs on',         'call':MicrocontrollerLedsOn},
    'MicrocontrollerLedsOff':  {'label':'Microcontroller LEDs off',        'call':MicrocontrollerLedsOff},
    'MicrocontrollerPowerOn':  {'label':'Microcontroller GPIO power ON',   'call':Mctl.PowerOn},
    'MicrocontrollerPowerOff': {'label':'Microcontroller GPIO power OFF',  'call':Mctl.PowerOff},
}
MctlMenu = proceduremenu(MctlMenuOptions,'Microcontroller tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

MiscMenuOptions = {
    'About':                  {'label':'About system',               'call':About},
    'ShowParameters':         {'label':'Show parameters',            'call':ShowParameters},
    'EditParameters':         {'label':'Edit parameters',            'call':EditParameters},
    'SetLocalTZ':             {'label':'Set local timezone',         'call':DefineLocalTZ},
    'DisplayLocalTZ':         {'label':'Display local times',        'call':DisplayLocalTZ},
    'DisplayUTCTZ':           {'label':'Display UTC times',          'call':DisplayUTCTZ},
    'EditTargetHistory':      {'label':'Edit target history',        'call':EditTargetHistory},
    'ShowFolderStructure':    {'label':'Show folder structure',      'call':FolderHandler.PrintFolderList},
    'DebugModeOn':            {'label':'Debug mode on',              'call':DebugModeOn},
    'DebugModeOff':           {'label':'Debug mode off',             'call':DebugModeOff},
    'ChangeHomeLocation':     {'label':'Change home location',       'call':ChangeHomeLocation},
    'ShowColorMap':           {'label':'Show color map',             'call':ShowColorMap},
    'ChooseColorScheme':      {'label':'Choose color scheme',        'call':Parameters.ChooseColorScheme},
    'ChooseColor':            {'label':'Choose individual color',    'call':Parameters.ChooseColor}
}
MiscMenu = proceduremenu(MiscMenuOptions,'Miscellaneous tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

TrackingMenuOptions = {
    'TrackingStatus':         {'label':'Tracking status',            'call':TrackingStatus},
    'TrackingExposureTime':   {'label':'Set tracking exposure time', 'call':SetTrackingExposureTime},
    'TrackingSearchArea':     {'label':'Set search area',            'call':SetSearchArea},
    'TrackingSearchOverlap':  {'label':'Set search overlap',         'call':SetSearchOverlap},
    'LatestTrackingFilter':   {'label':'Set Latest Tracking filter', 'call':SelectLatestFilter},
    'TestLatestFilter':       {'label':'Test Latest Tracking filter','call':TestLatestFilter},
}

TrackingMenu = proceduremenu(TrackingMenuOptions,'Tracking tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

DevMenuOptions = {
    'CreateOverlay':           {'label':'Create overlay',             'call':CreateOverlay},
    'SatellitePasses':         {'label':'Satellite passes',           'call':MenuSatellitePasses},
    'RecheckDisc':             {'label':'Check / remount storage',    'call':RecheckDisc},
    'ZipTrajectories':         {'label':'Zip trajectory log',         'call':ZipTrajectoryLog},
    'GpioStatus':              {'label':'GPIO status',                'call':GpioStatus},
    'ShowParameters':          {'label':'Show parameters',            'call':ShowParameters},
    'EditParameters':          {'label':'Edit parameters',            'call':EditParameters},
}

DevMenu = proceduremenu(DevMenuOptions,'Development tools menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)

ScheduleOptions = {
    'Add':      {'label':'Add target',        'call':MenuAddScheduledTarget, 'bold':True},
    'Run':      {'label':'Run schedule',      'call':RunObservationSchedule, 'bold':True, 'break':True},
    'Exposure': {'label':'Set exposure time', 'call':MenuSetExposureTime},
    'Frames':   {'label':'Set frame count',   'call':MenuSetBatchSize},
    'View':     {'label':'View schedule',     'call':ObservationSchedule.DisplayScheduleList},
    'Clear':    {'label':'Clear schedule',    'call':ObservationSchedule.Reset},
    'Load':     {'label':'Load schedule',     'call':ObservationSchedule.LoadScheduleFromJson},
    'Save':     {'label':'Save schedule',     'call':ObservationSchedule.SaveScheduleAsJson},
    'Sort':     {'label':'Sort by RA',        'call':ObservationSchedule.SortByRADeg}
    }

ScheduleMenu = proceduremenu(ScheduleOptions,'Observation schedule menu',titlefg=MENU_TITLE_FG,titlebg=MENU_TITLE_BG)
    
MainMenuOptions = {
    'SelectTarget':           {'label':'Select target',             'bold':True,  'call':SelectTarget},
    'BeginObservation':       {'label':'Begin observation',         'bold':True,  'call':BeginObservation, 'postcall':FlagObservationEnd},
    'ProgramStatus':          {'label':'Status',                    'call':ProgramStatus},
    'GotoTarget':             {'label':'GOTO target',               'call':MenuGoToTarget},
    'HomeAllMotors':          {'label':'Home all motors',           'call':HomePosition},
    'SetExposureTime':        {'label':'Set exposure time',         'call':MenuSetExposureTime, 'break':True},
    'SetLightBatchSize':      {'label':'Set light batch size',      'call':MenuSetBatchSize},
    'SetControlBatchSize':    {'label':'Set control batch size',    'call':MenuSetControlBatchSize},
    'TakeDarkFrameSet':       {'label':'Take dark frame set',       'call':MenuDarkSet},
    'TakeFlatFrameSet':       {'label':'Take flat frame set',       'call':MenuFlatSet},
    'TakeBiasFrameSet':       {'label':'Take bias/offset frame set','call':MenuBiasSet},
    'TakeDarkFlatFrameSet':   {'label':'Take dark flat frame set',  'call':MenuDarkFlatSet},
    'TakePreviewFrames':      {'label':'Take preview frames',       'call':MenuManualPreview},
    'TakeAutoFrames':         {'label':'Take auto frames',          'call':MenuAutoPhoto},
    'SetTimelapseDelay':      {'label':'Set timelapse delay',       'call':SetTimelapseDelay},
    'ScanForMeteors':         {'label':'Scan images for meteors',   'call':ScanForMeteors},
    'ScheduleMenu':           {'label':'Observation schedule menu', 'call':ScheduleMenu},
    'TrackingMenu':           {'label':'Tracking tools',            'call':TrackingMenu},
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
CameraAlt, CameraAz = LastReportedAltAz() # What is the last reported alt/az location of the centre of the image?
HomeAlt, HomeAz = HomeAltAz() # Home position for camera.
if round(CameraAlt,1) != round(HomeAlt,1) or round(CameraAz,1) != round(HomeAz,1): # Camera is not at home position.
    print(textcolor.yellow("The camera is currently at " + AzAltText(CameraAz,CameraAlt,DegreeSymbol)))
    if Parameters.RequireRestart: answer = False # Do not offer to move the motors if parameter file has been changed.
    else: answer = AskYesNo("Would you like to home the camera before powering off? [y/N]",False)
    if answer:
        print ("Returning camera to home position...")
        HomePosition()
        # Use the last reported camera position.
        CameraAlt, CameraAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
        if round(CameraAlt,1) != round(HomeAlt,1) or round(CameraAz,1) != round(HomeAz,1): # Camera is not at home position.
            textcolor.TextBox(["The camera did not successfully return to the home position.",
                               'The camera is left at ' + AzAltText(CameraAz,CameraAlt,DegreeSymbol)],
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
    
print ('')
ShutdownCamera() # Terminate the CameraHandler thread.
print ('')
print (textcolor.yellow('Stopping microcontroller communication...'))
Mctl.Reset(planned=True) # For safety, reset the microcontroller. This prevents the stepper motors triggering due to out-of-date instructions. 
MainLog.Log('Stopping microcontroller communication: send STOP...')
UartControlQueue.put('stop') # Tell MctlThread to shut down.
if MctlThread.is_alive():
    MainLog.Log('Stopping microcontroller communication: wait for end...')
    MctlThread.join() # Wait MctlThread to complete.
else:
    MainLog.Log('Stopping microcontroller communication: MctlThread already stopped.')
print ('')
ShutdownMessage() # Terminate the MessageHandler thread.
print ('')
MainLog.Log('Powering off the microcontroller.',terminal=False)
Mctl.ResetPin.Off() # Turn off the microcontroller power. Turn off regardless of GPIO/USB connectivity.
GPIOCleanup() # Reset the GPIO state.
print (textcolor.yellow("Saving parameters..."))
Parameters.SavedUTC = NowUTC() # Write when the parameter file was saved.
Parameters.SaveAttributes(Parameters.ParamFileName) # Write current operating parameters back to disc.
ObservationSchedule.CheckDirtyBit() # If the ObservationSchedule has been modified but not saved, offer to do it now.
print (textcolor.yellow("Done."))
print (textcolor.fgbgcolor(textcolor.BLACK,textcolor.GREEN," PILOMAR COMPLETE. OK TO SHUTDOWN "))

MainLog.Log("MAIN: PROGRAM COMPLETE",terminal=False)

