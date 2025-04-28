#!/usr/bin/python

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# -------------------------------------------------------------------------------------------------------------------
# This script is intended to create a simple 'libcamera-still' type of interface to the Picamera2 library.
# - The difference is that this can save raw sensor data as .FITS format files instead of .dng files.
# - It does not replicate all the functions of libcamera-still or libcamera-jpg, only those needed for the pilomar project.
#
# Usage:
#   Instead of the command :
#        libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
#   You can call this with :
#        python3 pilomarfits.py --output {&output} --width {&width} --height (&height} --denoise off --awbgains 1.0,1.0 --shutter {&shutter} --metadata --tuning-file imx477_noir.json
#
#   It outputs up to 4 files.
#      {&output} as .jpg             - Contains a normalised color jpeg image. (Will have some image compression due to JPEG)
#      {&output} as .fits            - Contains raw bayer data in fits format.
#      {&output} as .npy             - Contains a compressed numpy array of the debayered raw image. (Should not have any image compression)
#      {&output} as .json            - Contains a json dictionary of metadata associated with the image, camera and call.
#
#   The routine can append log messages in pilomarlog format to any specified pilomar log file.
#
# Supported libcamera style parameters are :
#   --output           Output filename. Use the .jpg filename.
#                      If missing, default is 'output.jpg' in current directory.
#                      The filetype is always replaced with one appropriate to the file format being saved.
#   --width            Image width. Use the sensor maximum width.
#   --height           Image height. Use the sensor maximum height.
#   --denoise          'off' to remove on-chip image cleaning.
#   --awbgains         red,blue gains for color image.
#   --analoggain       Now respected for color image.
#   --gain             (Synonym for analoggain parameter)
#   --shutter          Exposure time in microseconds.
#   --metadata         Metadata file will be saved, can be followed by optional filename(s) for the .json file.
#                      If no filename is given, one is generated automatically to match the .fits/.jpg filenames.
#                      You can save multiple copies so that 1 can be permanently saved with each individual image
#                      plus another can be saved with a standard name so that your controlling program can read in the results too.
#   --raw              Will save .fits file.
#                      (*) Can be followed by optional filename, if specified that is used instead of the default.
#                          If not specified, the .fits filename defaults to the same structure as the .jpg filename.
#   --tuning-file      imx477.json (default if not specified)
#                      imx477_noir.json (recommended if infrared cutoff filter has been removed)
#   --rotate           -90,0,90,180,270 degrees. Angles are clockwise.
#                      Rotates only the .jpg buffer. The RAW and NUMPY output files are not modified.
#                      (*) This physically rotates the image, unlike some utilities which crop the image instead.
#                      - If you physically rotate the sensor 90degrees clockwise, you need to rotate the image 90degrees counter-clockwise to compensate.
#   --config           Filename of options. Used instead of command line options.
#                      Same format as 'libcamera' options listed above. Options can be in a single line or multiple lines.
#                      If command line options are specified too, the command line values take precedence.
#                      Lines in the config file can contain comments, anything after '#' character is ignored.
#   
# Parameters that only pilomarfits recognises:
#   --log-file         Filename for logfile. It records log messages in pilomarlog format (appends: existing files are appended to).
#                      If not specified log messages are written to pilomarfits.py in the current directory (replaces: existing files are removed first).
#   --numpy-file       Numpy .npy 12bit debayered data will be saved.
#                      Can be followed by optional filename for the .npy file.
#                      If no filename is given, one is generated automatically to match the .fits/.jpg filenames.
#                      These are BIG files, don't save a lot of them!
#   --fits-tag-file    Filename(s) of json file(s) containing observation tags for the FITS header. Generated by external processes (eg pilomar.py itself).
#                      This dictionary contains additional 'tag' values for the FITS files that describe the target and equipment in more detail.
#                      All tags in the dictionary are added to the FITS header.
#                      You can specify multiple tag files in a space separated list.
#                                --fits-tag-file filename1.json filename2.json filename3.json 
#                      Multiple files are supported because there may be several different sources of tags.
#                          for example WEATHER from one process, TECHNICAL data from another, TARGET data from another.
#   --exif-tag-file    Filename(s) of json file(s) containing observation tags for EXIF header. Generated by external processes (eg pilomar.py itself).
#                      This dictionary contains additional 'tag' values for the JPEG files that describe the target and equipment in more detail.
#                      All tags in the dictionary are added to the JPEG header.
#                      You can specify multiple tag files in a space separated list.
#                                --exif-tag-file filename1.json filename2.json filename3.json
#                      Multiple files are supported beause there may be several different sources of tags.
#   --image-type       The type of image being captured (eg LIGHT, DARK, BIAS etc). Default is 'LIGHT' if nothing specified.
#   --verbose          Log messages are copied to the terminal display.
#   --debug            Extra analysis during processing. (Slows processing down.)
# 
#   Any other parameters will be ignored (many are not needed for just dumping raw bayer data from the sensor).
#
# Dependencies :
#   You must have astropy installed on your raspberry pi. It provides the 'fits' libraries needed.
#        sudo apt install python3-astropy
#
# Notes :
#   This is quite a slow process to run, you will get better performance and quality using raspistill or libcamera-still commands if you 
#   are just saving .jpg images. This will however generate .FITS files for astro-processing and can add EXIF tags to .jpg files also.
#   - This routine is a good candidate for performance improvements if it proves useful.
#
# Currently FITS files are written with the following tags in the header.
#  'EXPTIME' The exposure time if it's known.
#  'EXPOSURE' The exposure time if it's known.
#  'XBINNING' 1.0 No X binning
#  'YBINNING' 1.0 No Y binning
#  'ROWORDER' TOP-DOWN : Image data builds from top row downwards.
#  'BAYERPAT' RGGB Bayer pattern
#  'CCD-TEMP' Sensor temperature (C)
#  'IMAGETYP' The type of image being captured
#  'XPIXSZ' X pixel size (um)
#  'YPIXSZ' Y pixel size (um)
#  'GAIN' Analog gain
#  'RGAIN' Red gain
#  'BGAIN' Blue gain
#  'INSTRUME' Camera sensor model
#  'TIMESYS' UTC timezone
#  'SWCREATE Created by pilomarfits.py + VERSION
#  'JD' Julian date.
#  'DATE-OBS' Start of exposure.
#  'MIDPOINT' Midpoint of exposure.
#  Plus any additional tags provided by external FITS TAG files.
#
#
# Currently JPEG files are written with the following EXIF tags.
# *Q* Provide list!
#
# -------------------------------------------------------------------------------------------------------------------

# TODO:
# *Q* Improve tracking of dtype and bit-depth for future expansion.
# *Q* Validate 'FITS' file using online validation tools.
# *Q* Validate the 'rotation' processing.
# *Q* Complete EXIF tag setting.
# *Q* Validate Julian Date conversion.

VERSION = "0.2.0"

import os
os.environ["LIBCAMERA_LOG_LEVELS"] = "3" # Report errors only. Supresses a lot of unwanted messages to the terminal.
import time
import math
import numpy as np
from picamera2 import Picamera2
from astropy.io import fits
from datetime import datetime, timedelta, timezone
import cv2
import struct
import sys
import json
from pilomarlogfile import logfile # Pilomar's logging class.
from pilomarimage import pilomarimage # Pilomar's IMAGE BUFFER handler (combines numpy, OpenCV, some PIL and pilomar specific routines)

ProcessingData = {} # Build up statistics from the image processing.

# -----------------------------------------------------------------------------------------

def NowUTC():
    """ Return system UTC timestamp as a datetime object. """
    return datetime.now(timezone.utc)

# -----------------------------------------------------------------------------------------

def date_to_jd(input_datetime):
    """
    Based upon: https://gist.github.com/jiffyclub/1294443
    
    Convert a datetime to Julian Day.
    
    Algorithm from 'Practical Astronomy with your Calculator or Spreadsheet', 
        4th ed., Duffet-Smith and Zwart, 2011.
    
    Parameters
    ----------
    input_datetime (datetime datatype, can be TZ aware)
    
    Returns
    -------
    jd : float
        Julian Day
        
    Examples
    --------
    Convert 6 a.m., February 17, 1985 to Julian Day
    
    >>> date_to_jd(1985.02.17 06:00:00.000)
    2446113.75
    
    """
    year = input_datetime.year
    month = input_datetime.month
    day = input_datetime.day
    timeoffset = (float(input_datetime.hour) + float(input_datetime.minute / 60) + float(input_datetime.second / 3600)) / 24
    day = float(day) + timeoffset
    
    if month == 1 or month == 2:
        yearp = year - 1
        monthp = month + 12
    else:
        yearp = year
        monthp = month
    
    # this checks where we are in relation to October 15, 1582, the beginning
    # of the Gregorian calendar.
    if ((year < 1582) or
        (year == 1582 and month < 10) or
        (year == 1582 and month == 10 and day < 15)):
        # before start of Gregorian calendar
        B = 0
    else:
        # after start of Gregorian calendar
        A = math.trunc(yearp / 100.)
        B = 2 - A + math.trunc(A / 4.)
        
    if yearp < 0:
        C = math.trunc((365.25 * yearp) - 0.75)
    else:
        C = math.trunc(365.25 * yearp)
        
    D = math.trunc(30.6001 * (monthp + 1))
    
    jd = B + C + D + day + 1720994.5
    
    return jd
    
# -----------------------------------------------------------------------------------------    

StartupTime = NowUTC() # When did the program start?

PROGRAMNAME = sys.argv[0] # Get the program name.
RunArgs = sys.argv[1:] # Ignore 1st argument which is this program name.
ArgumentDict = {} # Convert the runtime arguments into a dictionary.
# ArgumentDict dictionary is in the format...
#  {'--argument1':{0:'value1', 1:'value2', 2:'value3', 'all':'value1,value2,value3'},
#   '--argument2':{0:'value1', 1:'value2', 2:'value3', 'all':'value1,value2,value3'}}
optlist = []

# -----------------------------------------------------------------------------------------

def ArgSplit(argline):
    """ Take an argument line and split it on spaces, but preserve anything in quotes.
        Also, ignore comments marked by '#'. 
        Result is returned as a list.
        
        --argname arg1 arg2 arg3              becomes         ['--argname','arg1','arg2','arg3'] 
        --argname arg1 arg2      arg3         becomes         ['--argname','arg1','arg2','arg3'] 
        --argname arg1 arg2 'arg"3'           becomes         ['--argname','arg1','arg2','arg"3'] 
        --argname arg1 arg2 # arg3            becomes         ['--argname','arg1,'arg2'] 
        --argname arg1 "arg2 arg3"            becomes         ['--argname','arg1','arg2 arg3'] 
        --argname arg1 'arg2 "arg3"'          becomes         ['--argname','arg1','arg2 "arg3"'] 
        
        """
    argline = argline.strip('\n') # Remove end of line markers.
    argline = argline.strip() # Remove start/end spaces.
    returnlist = [] # The list of arguments that will be returned.
    inquote = False # We are not initially handling a quoted argument.
    inquotechar = ['"',"'"] # What character can TRIGGER quote mode? (We ignore spaces inside quoted strings)
    currentarg = '' # The current argument being read.
    for c in argline: # Check each character in turn.
        if c in inquotechar: # What quote marks are we looking for?
            inquote = not inquote # We've found a quote mark, move IN or OUT of quote mode.
            if inquote: inquotechar = [c] # Only the same quote mark can terminate a quoted string.
            continue # Don't process this quote mark any further, move on to the next available character.
        if not inquote and c == '#': # We're starting a comment, ignore the rest of the line.
            break
        if not inquote and c == ' ': # We have an unquoted space character. Split.
            if currentarg != '': # We have a current argument that needs storing now.
                returnlist.append(currentarg) # Add what we have to the argument list.
                currentarg = '' # Start building a new current argument.
                inquotechar = ['"',"'"] # What character can TRIGGER quote mode?
        else: currentarg += c # We have an argument character, add it.
    if currentarg != '': # Cleanup any final argument.
        returnlist.append(currentarg) 
    return returnlist
    
# -----------------------------------------------------------------------------------------

def AddArgs(arglist,argumentdict={}):
    """ Given a list of command line arguments extract the information and append it to the ArgumentDict dictionary.

        Parameters -------------------------------------------------------------------------------------------
        arglist : Argument list is in the form
            ['--switchname1','value1','value2','value3','--switchname2','value4,value5,value6','--switchname3','value7','--switchname4','--switchname5','value8', ...]
        argumentdict : Optional initial dictionary values.
    
        Outputs ----------------------------------------------------------------------------------------------
        Dictionary is in the format...
            {'--argument1':{0:'value1', 1:'value2', 2:'value3', 'all':'value1,value2,value3'},
             '--argument2':{0:'value1', 1:'value2', 2:'value3', 'all':'value1,value2,value3'}} """
    Argument = '' 
    if len(arglist) > 0: # Arguments given.
        for raw_arg in arglist: # Run through all the arguments entered at runtime.
            arg = raw_arg.strip() # Remove leading/trailing spaces.
            arg = arg.strip('\n') # Remove newline characters.
            if len(arg) < 1: continue # Nothing to process.
            if arg[:2] == '--' and arg in argumentdict: continue # Already exists, don't merge.
            if arg[:2] == '--': # Found an argument name.
                Argument = arg # Note that this is the argument name we're working on.
                argumentdict[arg] = {'all':'','list':[]} # Make fresh entry for this argument and its options as 
                optlist = [] # Options as a list.
            else:
                if Argument != '': # A current argument being constructed.
                    optlist.append(arg) # Maintain a list of options for the argument too. Easier to process multiple items like filenames.
                    argumentdict[Argument]['list'] = optlist # Update the option list in the dictionary.
                    cs = argumentdict[Argument]['all'] # Get existing comma separated list of options.
                    if cs != '': cs += ',' # comma separate entries.
                    cs += arg.strip() # Append this option.
                    while ',,' in cs: cs = cs.replace(',,',',') # Make sure no repeated separators.
                    argumentdict[Argument]['all'] = cs # Get existing comma separated list of options.
                else: # No argument under construction. Reject this.
                    print(PROGRAMNAME,"AddArgs (",arglist,") Cannot assign",arg,"to an instruction.")
    return argumentdict

# -----------------------------------------------------------------------------------------                    

if len(RunArgs) > 0: # Arguments given in command line, add them to ArgumentDict.
    ArgumentDict = AddArgs(RunArgs, ArgumentDict)

GlobalCameraInfo = Picamera2.global_camera_info() # Get list of attached cameras.
CameraModel = "IMX477" # Default to Hi Quality Camera sensor.
for c in GlobalCameraInfo:
    CameraModel = c.get('Model',"IMX477").upper()

# Is an options file specified?
if '--config' in ArgumentDict: # An options file(s) exist. Use that to add more options/switches. Most recent command line option always win if there's a conflict.
    # Add to ArgumentDict if not already specified.
    config_files = []
    if len(ArgumentDict['--config']['list']) < 1: config_files = ['config.txt'] # Default to single standard config.txt file if nothing specified.
    for filename in config_files:
        if filename == '': filename = 'config.txt' # Mimic default behaviour of libcamera command line.
        if os.path.exists(filename):
            with open(filename,'r') as f:
                for line in f.readlines():
                    # Strip out any comments.
                    cleanline = ''
                    in_quote = False
                    for c in line:
                        if c == '"' or "'": # Quote mark.
                           in_quote = not in_quote
                        if not in_quote and c == '#': break # Don't process any further, we're now into comments.
                        cleanline += c # This is still a valid character to add to the option list.
                    ArgumentDict = AddArgs(ArgSplit(cleanline),ArgumentDict)

if '--verbose' in ArgumentDict: VerboseMode = True # Show all log messages to the display.
else: VerboseMode = False # Log messages ONLY to the log file.
if '--debug' in ArgumentDict: DebugMode = True # Extra analysis during processing.
else: DebugMode = False # No extra analysis, just core processing.

# Is a logfile specified?
if '--log-file' in ArgumentDict:
    MainLog = logfile(ArgumentDict['--log-file']['all']) # This will append to any existing file.
else:
    lfn = PROGRAMNAME.replace(".py",".log")
    if os.path.exists(lfn): os.remove(lfn) # Delete any previous copy. We only save the current run.
    MainLog = logfile(lfn) # Start new file.

MainLog.Log(PROGRAMNAME + ": ArgumentDict:",ArgumentDict,terminal=VerboseMode)

# -----------------------------------------------------------------------------------------    

def ColorGain(array,red=1.0,green=1.0,blue=1.0):
    """ Given a BGR image array, boost the BLUE, GREEN and RED channels by different factors. 
        Parameters ------------------------------------------------------------------------
        red : red gain. 
        green : green gain. 
        blue : blue gain. """
    MainLog.Log(PROGRAMNAME + ":ColorGain(",red,green,blue,")",terminal=VerboseMode)
    array[:,:,2] = array[:,:,2] * red # red channel
    array[:,:,1] = array[:,:,1] * green # green channel
    array[:,:,0] = array[:,:,0] * blue # blue channel
    return array

# -----------------------------------------------------------------------------------------    

def AnalogGain(array,analoggain=1.0):
    """ Apply an analog gain ratio to each colour channel. 
        Parameters ------------------------------------------------------------------------
        array : The array of colours to adjust. 
        analoggain : The analog gain to apply to each channel of each cell. """
    MainLog.Log(PROGRAMNAME + ":AnalogGain(",analoggain,")",terminal=VerboseMode)
    array[:,:,:] = array[:,:,:] * analoggain # *Q* Can this just be 'array *= analoggain' ?
    return array

# -----------------------------------------------------------------------------------------    

def HistogramArray(inputarray,bins=256):
    """ Write a histogram of the values in an array to the log file.
        Parameters ------------------------------------------------------------------------
        inputarray : The array to analyse. 
        bins : The number of 'bins' to divide the values into. 
        Outputs ---------------------------------------------------------------------------
        Results are written to logfile only. """
    histogram, _ = np.histogram(inputarray, bins=bins, range=(0, bins - 1))
    for i,entry in enumerate(histogram):
        MainLog.Log("HistogramArray:",i,entry,terminal=VerboseMode)

# -----------------------------------------------------------------------------------------    

def NormalizeArray(input_array,min_out,max_out,min_in=None,max_in=None):
    """ Normalize values of an array to between min_out and max_out.
        Parameters ------------------------------------
        input_array : The array to normalise.
        min_out     : The minimum value in the normalised result.
        max_out     : The maximum value in the normalised result.
        min_in      : Default None: If set, forces the minimum value for input numbers.
        max_in      : Default None: If set, forces the maximum value for input numbers.
        Output ----------------------------------------
        output_array : Normalised version of input_array. """
    input_array = input_array.astype(np.float32) # Convert to floating point.
    c_min = np.min(input_array)
    c_max = np.max(input_array)
    if min_in != None: c_min = min(c_min,min_in) # Force a minimum input value even if it's not in the array.
    if max_in != None: c_max = max(c_max,max_in) # Firce a maximum input value even if it's not in the array.
    c_span = c_max - c_min
    MainLog.Log(PROGRAMNAME + ": NormalizeArray: Output limits: min:",min_out,"max:",max_out,"span:",(max_out - min_out),terminal=VerboseMode)
    MainLog.Log(PROGRAMNAME + ": NormalizeArray: Input limits: min:",c_min,"max:",c_max,"span:",c_span,terminal=VerboseMode)
    try:
        output_array = ((max_out - min_out) * (input_array - c_min) / c_span) + min_out # Normalize to new range.
    except Exception as e:
        print(PROGRAMNAME + ":NormalizeArray(",min_out,max_out,") failed:",e)
        MainLog.Log(PROGRAMNAME + ": error_NormalizeArray_001:",e,terminal=True)
        MainLog.Log(PROGRAMNAME + ": NormalizeArray",min_out,max_out,')failed.',terminal=True)
        output_array = np.clip(input_array.astype(np.float32),0,max_out) # Couldn't normalize, so clip instead.
    return output_array
    
# -----------------------------------------------------------------------------------------    

# List of potential control parameters that can be used in set_controls.
# These are pulled from the runtime arguments and used to construct the set_controls call.
# It translates the command line option into the set_controls attribute.
# Command line options try to match the libcamera-still command line structure as much as possible.
# The KEY is the command line switch,
# 'Attribute' is the name of the control option to pass to picamera2.
# 'Default' is the default value of the option.
# 'Type' is the datatype for the values passed to picamera2.
ControlDict = {
    '--shutter':    {"Attribute":"ExposureTime",       
                     "Default":5000, 
                     "Type":int},
    '--gain':       {"Attribute":"AnalogueGain",
                     "Default":1.0,
                     "Type":float},
    '--analoggain': {"Attribute":"AnalogueGain",
                     "Default":1.0,
                     "Type":float},
    }

MainLog.Log(PROGRAMNAME + ": ControlDict:",ControlDict,terminal=VerboseMode)

# For speed ....
#           --gain 1 --awbgains 1,1 --immediate

# Create the dictionary of control settings for the camera.
ControlsToApply = {}
for argument,elementdict in ArgumentDict.items(): # Process all the runtime arguments received.
    if argument in ControlDict: # We should use this argument.
        CDE = ControlDict[argument] # Get the entry.
        CDV = CDE['Default'] # There's a default value if no options are given.
        CDT = CDE['Type'] # What datatype to use for options.
        if 'list' in elementdict: # User specified options that we should use.
            option = elementdict['list'][0] # Get the first option.
            if 'Translate' in CDE and option in CDE['Translate']: # We can directly translate the options.
                option = CDE['Translate'][option] # Use translation.
            if CDT == float: # Option must be float datatype.
                CDV = float(option)
            elif CDT == int: # Option must be int datatype
                CDV = int(float(option)) # Protect from 'float' values.
            else: CDV = option # Use the option as is.
        ControlsToApply[CDE['Attribute']] = CDV # Add the option to the control list.
# Add any unspecified controls.
#ControlsToApply['NoiseReductionMode'] = libcamera.controls.draft.NoiseReductionModeEnum.Off # Turn off on-chip noise reduction routines. This didn't result in a number, just a string.
# NoiseReductionMode values are: NoiseReductionModeOff = 0, NoiseReductionModeFast = 1, NoiseReductionModeHighQuality = 2, NoiseReductionModeMinimal = 3, NoiseReductionModeZSL = 4
ControlsToApply['NoiseReductionMode'] = 0 # Turn off on-chip noise reduction routines.

if not '--shutter' in ArgumentDict: # Shutter speed not given, so go for AE auto.
    ControlsToApply['AeEnable'] = True # Turn on Automatic Exposure mode.     
else:    
    # For raw data we need to disable the auto-exposure and gains. This will speed up image capture significantly for long exposures.
    ControlsToApply['HdrMode'] = 0 # Turn off HDR processing.
    ControlsToApply['AeEnable'] = False # Turn off Automatic Exposure mode.     
    ControlsToApply['AwbEnable'] = False # Turn off auto white balance.
    if not 'ColourGains' in ControlsToApply: ControlsToApply['ColourGains'] = (1.0,1.0) # No colour gains. # Will be applied later if specified.
    if not 'AnalogueGain' in ControlsToApply: ControlsToApply['AnalogueGain'] = 1.0 # Max analogue gain. # No impact upon RAW data?

MainLog.Log(PROGRAMNAME + ": ControlsToApply:",ControlsToApply,terminal=VerboseMode)

if '--image-type' in ArgumentDict: # What type of image are we capturing?
    ImageType = ArgumentDict['--image-type']['list'][0].upper()
else:
    ImageType = 'LIGHT'

if '--tuning-file' in ArgumentDict:
    tuning = Picamera2.load_tuning_file(ArgumentDict['--tuning-file']['list'][0])
else:
    # tuning = Picamera2.load_tuning_file("imx477_noir.json")
    tuning = Picamera2.load_tuning_file("imx477.json")
picam2 = Picamera2(tuning=tuning)
PropertyDict = picam2.camera_properties # Get camera properties.

# Image dimensions
width = 4056
if '--width' in ArgumentDict: width = int(ArgumentDict['--width']['list'][0])
height = 3040
if '--height' in ArgumentDict: height = int(ArgumentDict['--height']['list'][0])

# Image quality (for jpg)
quality = 100
if '--quality' in ArgumentDict: quality = int(ArgumentDict['--quality']['list'][0])

# Sensor data format.
sensor_format = 'SBGGR12'
if '--format' in ArgumentDict: sensor_format = ArgumentDict['--format']['list'][0]

# Filenames
jpgfilename = ArgumentDict.get('--output',{'all':'output.fits'})['all']
jpgfilename = jpgfilename.replace('.fits','.jpg') # In case user puts wrong filetype.
fitsfilename = jpgfilename.replace('.jpg','.fits')
jsonfilenames = [jpgfilename.replace('.jpg','.json')] # Default to a list of filenames containing just the default filename.
numpyfilename = jpgfilename.replace('.jpg','.npy')

# Red/Blue gains.
redgain = 1.0
bluegain = 1.0
if '--awbgains' in ArgumentDict: 
    csl = ArgumentDict['--awbgains']['all'].split(',') # Get all options as comma-separated-list (no whitespace).
    redgain = float(csl[0]) # red channel
    bluegain = float(csl[1]) # blue channel
    
analoggain = 1.0
if '--gain' in ArgumentDict:
    analoggain = float(ArgumentDict['--gain']['all']) 
if '--analoggain' in ArgumentDict:
    analoggain = float(ArgumentDict['--analoggain']['all']) 

# Set up the camera.
config = picam2.create_still_configuration(raw={'format': sensor_format, 'size': (width, height)})
picam2.configure(config)
picam2.set_controls(ControlsToApply)
picam2.start()
# Allow the camera time to start up and accept config and control settings. It takes time!
time.sleep(2) # Wait for control propogation.
# Extract bayer data from the sensor.
CaptureStartTime = NowUTC() # When did capture begin?
CameraRequest = picam2.capture_request()
rawarray8 = CameraRequest.make_array('raw') # Retrieve bayer matrix, it's 12bit data but packed in 8bit chunks initially.
RequestMetadata = CameraRequest.get_metadata() # Retrieve sensor metadata as a dictionary.
CaptureEndTime = NowUTC() # When did capture complete?
CaptureMidpoint = CaptureStartTime + (CaptureEndTime - CaptureStartTime) / 2 # Midpoint of the exposure.
CameraRequest.release() # Release the camera buffers, otherwise we may run out of memory.

# OK Pay attention! The data received from the sensor is 12bits per pixel, but it's split across 8bit boundaries.
# We have to unpack this data so that we have proper separate 12bit values to work with. 

if DebugMode: # What does the original 'packed' raw data look like? It's an 8bit array, but contains 12bit packed data.
    MainLog.Log(PROGRAMNAME + ": rawarray8:",
                'min:',np.min(rawarray8), 'max:',np.max(rawarray8),
                'shape:',rawarray8.shape,'dtype:',rawarray8.dtype, 'unique_count:',len(np.unique(rawarray8)),terminal=VerboseMode)

# Unpack 12bit values from 8bit stream, store as 16bit. Values are left shifted 4 bits, ie 2 ^ 4 too large. Will be in range 0 - 65535
rawarray12 = rawarray8.view(np.uint16).astype(np.uint16) 
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": rawarray12:",
                'min:',np.min(rawarray12), 'max:',np.max(rawarray12),
                'shape:',rawarray12.shape,'dtype:',rawarray12.dtype, 'unique_count',len(np.unique(rawarray12)),terminal=VerboseMode)

# Convert to 32bit storage to reduce rounding errors in math operations.
data32 = rawarray12.astype(np.float32) # Convert to float 32bit storage. Will contain numbers in range 0 - 65535
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": data32 (as 16bit):",
                'min:',np.min(data32),'max:',np.max(data32),
                'shape:',data32.shape,'dtype:',data32.dtype,'unique_count:',len(np.unique(data32)),terminal=VerboseMode)

# The data is still 12 bit data left shifted in a 16bit item, so it's 2^4 times too large.
data32 = data32 / (2 ^ 4) # Right shift from 16 bit back to 12 bit. Will contain numbers in range 0 - 4095
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": data32 (as 12bit):",
                'min:',np.min(data32),'max:',np.max(data32),
                'shape:',data32.shape,'dtype:',data32.dtype,'unique_count:',len(np.unique(data32)),terminal=VerboseMode)

# ------------------------
# Create FITS image file.
# ------------------------

# Are there any json files specified for additional FITS header tags?
FitsTagDict = {} # Start with empty observation data dictionary.
if '--fits-tag-file' in ArgumentDict:
    ft_file_list = ArgumentDict['--fits-tag-file']['list'] # Pull the --fits-tag-file option and it's parameters. Could be one or more filenames listed sequentially.
    for obsfilename in ft_file_list: # Check for multiple tag files, different utilities could provide individual tag files contributing different metadata to the header.
        if obsfilename in ['None',None]: # Nothing to process here.
            continue
        if os.path.exists(obsfilename): 
            with open(obsfilename,'r') as f:
                ttd = json.load(f)
            for key,value in ttd.items(): # Consolidate all the tags into a single dictionary.
                FitsTagDict[key] = value 
        else: # Can't find the specified tag file.
            print("** " + PROGRAMNAME + ": Cannot find fits header tag file",obsfilename)

RawSaveStartTime = NowUTC() # When did FITS file generation start?
if '--raw' in ArgumentDict:
    temp = ArgumentDict['--raw']['all'] # Was an overriding filename specified?
    if temp != '': fitsfilename = temp # Override the default filename.
    MainLog.Log(PROGRAMNAME + ": fitsfilename:",fitsfilename,terminal=VerboseMode)
    # Write image data.
    hdulist = fits.HDUList()
    hdulist.append(fits.ImageHDU(data=cv2.flip(data32,0),name='SCI')) # Flip vertically. Makes it BOTTOM-UP?
    # Write header tags.
    hh = hdulist[0].header
    xt = ControlsToApply.get('ExposureTime',None) # Did command line specify the exposure time?
    xtc = 'Specified exposure time (s).'
    if xt == None: # No command line exposure time, so use the value from the metadata.
        xt = RequestMetadata.get('ExposureTime',None) # Get the exposure from the image capture itself.
        xtc = 'Actual exposure time (s).'
    if xt != None: # Set both recognised exposure time tags.
        xt = float(xt) / 1.0e6 # Scale from microseconds to seconds.
        FitsTagDict['EXPTIME'] = {'value':xt,'comment':xtc} # Only set the exposure time if it's known.
        FitsTagDict['EXPOSURE'] = {'value':xt,'comment':xtc} # Only set the exposure time if it's known.
    FitsTagDict['XBINNING'] = {'value':1.0,'comment':"No X binning."}
    FitsTagDict['YBINNING'] = {'value':1.0,'comment':"No Y binning."}
    FitsTagDict['ROWORDER'] = {'value':'TOP-DOWN','comment':"Image data builds from top row downwards."}
    FitsTagDict['BAYERPAT'] = {'value':'RGGB','comment':"RGGB Bayer pattern."}
    ccdt = RequestMetadata.get('SensorTemperature',None) # Is the sensor temperature available?
    if ccdt != None: # Sensor temp is known, record it.
        FitsTagDict['CCD-TEMP'] = {'value':ccdt,'comment':"Sensor temperature (C)"}
    FitsTagDict['IMAGETYP'] = {'value':ImageType,'comment':"The type of image being captured."} # *Q* Can this come in one of the external FITS TAG files?
    FitsTagDict['XPIXSZ'] = {'value':3.76,'comment':"X pixel size (um)"}
    FitsTagDict['YPIXSZ'] = {'value':3.76,'comment':"Y pixel size (um)"}
    FitsTagDict['GAIN'] = {'value':analoggain,'comment':"Analog gain"}
    FitsTagDict['RGAIN'] = {'value':redgain,'comment':"Red gain"}
    FitsTagDict['BGAIN'] = {'value':bluegain,'comment':"Blue gain"}
    FitsTagDict['INSTRUME'] = {'value':CameraModel,'comment':"Camera sensor model"}
    FitsTagDict['TIMESYS'] = {'value':'UTC','comment':"UTC timezone"}
    FitsTagDict['SWCREATE'] = {'value':'PILOMARFITS ' + str(VERSION),'comment':"Created by pilomarfits.py " + VERSION}
    FitsTagDict['JD'] = {'value':date_to_jd(CaptureStartTime),'comment':'Julian date.'}
    FitsTagDict['DATE-OBS'] = {'value':CaptureStartTime.isoformat(),'comment':'Start of exposure.'}
    FitsTagDict['MIDPOINT'] = {'value':CaptureMidpoint.isoformat(),'comment':'Midpoint of exposure.'}
    # Add any externally specified tags too. (Calling program may provide other environment/equipment info)
    if type(FitsTagDict) == dict: # We have a dictionary of observation/technical/weather tags to handle too.
        for key,details in FitsTagDict.items(): # Go through all the listed tags.
            hh.append((key,details['value'],details['comment']),end=True)
    # ROWORDER - 'TOP-DOWN' / 'BOTTOM-UP' ?
    # BAYERPAT - 'RGGB' (BOTTOM-UP?), 'GBRG' (TOP-DOWN?) - Check?
    hdulist.writeto(fitsfilename,overwrite=True) # Save fits.
RawSaveEndTime = NowUTC() # When did FITS file generation finish?
    
# Now convert to colour. Debayer the matrix.
BayerStartTime = NowUTC() # When did debayer processing start?
#bayer = data32.clip(0,(2 ** 16 - 1)).astype(np.uint16) # Make sure image fits in integer16 datatype.
#if DebugMode:
#    MainLog.Log(PROGRAMNAME + ": clipped pre_debayer:",
#                'min:',np.min(bayer), 'max:',np.max(bayer),
#                'shape:',bayer.shape,'dtype:',bayer.dtype, 'unique_count:',len(np.unique(bayer)),terminal=VerboseMode)
bayer = data32.astype(np.uint16) # Convert to unsigned 16 bit. Will contain numbers in range 0 - 4095 (2 ^ 12)

# This appears to leave a 9 pixel wide strip at the right of the image BLACK, which confuses later stages.  
colour = (cv2.cvtColor(bayer, cv2.COLOR_BAYER_BGGR2BGR)) # Demosaic. Generates uint16 array. Will contain numbers in range 0 - 4095 (2 ^ 12)
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": colour_post_debayer:",
                'min:',np.min(colour),'max:',np.max(colour),
                'shape:',colour.shape,'dtype:',colour.dtype,'unique_count:',len(np.unique(colour)),terminal=VerboseMode)

#RightDeadColumns = 10 # The 10 rightmost columns are 'dead' after the debayering. These are generally value '[0,0,0]' which can distort later normalisation.
RightDeadColumns = 8 # The 8 rightmost columns are 'dead' after the debayering. These are generally value '[0,0,0]' which can distort later normalisation.
colour = colour[:,:-1 * RightDeadColumns,:] # Loose the 'dead' right hand columns. Will contain numbers in range 0 - 4095 (2 ^ 12)
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": colour_post_trim:",
                'min:',np.min(colour),'max:',np.max(colour),
                'shape:',colour.shape,'dtype:',colour.dtype,'unique_count:',len(np.unique(colour)),terminal=VerboseMode)

# Apply any gains.
if redgain != 1.0 or bluegain != 1.0:
    colour = ColorGain(colour,red=redgain,blue=bluegain) # Boost channels to get more realistic colours.
    # Colours can now exceed 0 - 4095 range. (2 ^ 12)
if analoggain != 1.0:
    colour = AnalogGain(colour,analoggain=analoggain) # Boost analog gain.
    # Colours can now exceed 0 - 4095 range. (2 ^ 12)
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": colour_post_gains:",
                'min:',np.min(colour),'max:',np.max(colour),
                'shape:',colour.shape,'dtype:',colour.dtype,'unique_count:',len(np.unique(colour)),terminal=VerboseMode)

BayerEndTime = NowUTC() # When did debayer processing end?

NumpyStartTime = NowUTC() # When did numpy save start?
# Save the debayered data as a numpy array. Allow values to be 16bit still.
if '--numpy-file' in ArgumentDict: # Save the debayered data as a .npy array file too. For live image stacking experiments.
    temp = ArgumentDict['--numpy-file']['all'] # Is there a filename?
    if temp != '': numpyfilename = temp # Use specified filename rather than default.
    MainLog.Log(PROGRAMNAME + ": numpyfilename:",numpyfilename,terminal=VerboseMode)
    np.save(numpyfilename,colour.astype(np.uint16))
NumpyEndTime = NowUTC() # When did numpy save complete?

colour = colour.clip(0,(2 ** 12 - 1)) # Limit back to 0 - 4095 range. (2 ^ 12) This is in case the gains have pushed the values above int12 space, we consider any excess to be 'overblown', otherwise they can distort the normalised image saved in the jpeg file.
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": colour_clipped:",
                'min:',np.min(colour),'max:',np.max(colour),
                'shape:',colour.shape,'dtype:',colour.dtype,'unique_count:',len(np.unique(colour)),terminal=VerboseMode)

#colour = np.rint(NormalizeArray8Bit(colour,255)) # Normalize to 8 bit range.
colour = np.rint(NormalizeArray(colour,min_out=0,max_out=255,min_in=0)) # Normalize to 8 bit range.
#print("Colour (normalized to 8 bit): Min",np.min(colour),"Max",np.max(colour),colour.dtype,"Unq",len(np.unique(colour)))
if DebugMode:
    MainLog.Log(PROGRAMNAME + ": colour_normalized_to_8bit integers:",
                'min:',np.min(colour),'max:',np.max(colour),
                'shape:',colour.shape,'dtype:',colour.dtype,'unique_count:',len(np.unique(colour)),terminal=VerboseMode)
    HistogramArray(colour,bins=256) # Write a histogram of the values in the array.            
# colour array is still float64.

def RotateImage(buffer,angle):    
    if angle == 90: buffer = cv2.rotate(buffer, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180: buffer = cv2.rotate(buffer, cv2.ROTATE_180)
    elif angle == 270: buffer = cv2.rotate(buffer, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif angle == 0: pass # Don't rotate.
    else: MainLog.Log(PROGRAMNAME + ":","WARNING: --rotate",angle,"is not recognised. Ignored.",terminal=VerboseMode)
    return buffer

if '--rotate' in ArgumentDict: # Image should be rotated.
    angle = int(ArgumentDict['--rotate']['all']) % 360
    colour = RotateImage(colour,angle)

ExifTagDict = {} # Start with empty observation data dictionary.
if '--exif-tag-file' in ArgumentDict:
    ade = ArgumentDict['--exif-tag-file']['list'] # Pull the --exif-tag-file option and it's parameters. Could be one or more filenames listed sequentially.
    for obsfilename in ade: # Check for multiple tag files, different utilities could provide individual tag files contributing different metadata to the header.
        if obsfilename in ['None',None]: # Nothing to process here.
            continue
        if os.path.exists(obsfilename): 
            with open(obsfilename,'r') as f:
                ttd = json.load(f)
            for key,value in ttd.items(): # Consolidate all the tags into a single dictionary.
                ExifTagDict[key] = value 
        else: # Can't find the specified tag file.
            print("** pilomarfits: Cannot find exif header tag file",obsfilename)

## Add back the right hand border to retain original image dimensions.
##                           source   top    bottom    left     right      bordertype        filltype   value
#colour = cv2.copyMakeBorder(colour,   0,      0,        0,      RightDeadColumns,   cv2.BORDER_CONSTANT,   None) # , value = [0,0,0])     

# Always save the .jpg file.
JpgStartTime = NowUTC() # When did jpg save start?
MainLog.Log(PROGRAMNAME + ": jpgfilename:",jpgfilename,"(shape",colour.shape,")",terminal=VerboseMode)
cv2.imwrite(jpgfilename,colour,[int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
JpgEndTime = NowUTC() # When did jpg save end?

# Optionally add EXIF tags to the .jpg file if tags exist. (*Q* This is SLOW!)
ExifStartTime = NowUTC() # When did EXIF handling start?
if len(ExifTagDict) > 0: # Exif tags exist, add those to the image. (Done separately via PIL)
    pim = pilomarimage(name='camera',logger=MainLog)
    pim.AddExifTags(jpgfilename,ExifTagDict) # Works directly on the disc file, no need to load/save.
ExifEndTime = NowUTC() # When did EXIF handling end?

# Finally write metadata if needed.
MetaStartTime = NowUTC() # When did metadata save start?
if '--metadata' in ArgumentDict: # Extract and save metadata.
    temp = ArgumentDict['--metadata']['list'] # Is there a specific metadata filename specified?
    if temp != []: jsonfilenames = temp # metadata filename(s) were specifically given. Overwrite the default.
    metadata = RequestMetadata
    metadata['program'] = PROGRAMNAME # Program name.
    metadata['pilomarfits_version'] = VERSION
    metadata['pilomar_set_controls'] = ControlsToApply # What control settings were applied to picamera2?
    metadata['pilomar_runtime_args'] = ArgumentDict # What runtime switches were received?
    metadata['pilomar_control_dict'] = ControlDict # What control settings rules are known?
    metadata['fits_header_tags'] = FitsTagDict # What FITS header tags were identified?
    metadata['exif_header_tags'] = ExifTagDict # What EXIF header tags were identified?
    metadata['jpgfilename'] = jpgfilename
    metadata['numpyfilename'] = numpyfilename
    metadata['fitsfilename'] = fitsfilename
    metadata['jsonfilenames'] = jsonfilenames
    metadata['StartupTime'] = StartupTime # When did program start?
    metadata['CaptureStartTime'] = CaptureStartTime # When did image capture start?
    metadata['CaptureEndTime'] = CaptureEndTime # When did image capture complete?
    metadata['CaptureMidpoint'] = CaptureMidpoint # Midpoint of image capture.
    metadata['CaptureDuration'] = (CaptureEndTime - CaptureStartTime).total_seconds() # How long did capture take?
    metadata['RawSaveDuration'] = (RawSaveEndTime - RawSaveStartTime).total_seconds() # How long did FITS file generation take?
    metadata['BayerDuration'] = (BayerEndTime - BayerStartTime).total_seconds() # How long did debayer take?
    metadata['NumpyDuration'] = (NumpyEndTime - NumpyStartTime).total_seconds() # How long did numpy save take?
    metadata['JpgDuration'] = (JpgEndTime - JpgStartTime).total_seconds() # How long did jpg save take?
    metadata['ExifDuration'] = (ExifEndTime - ExifStartTime).total_seconds() # How long did EXIF tag handling take?
    metadata['camera_properties'] = PropertyDict # Export camera properties too.
        
    # Cleanup.
    for key in ['Bcm2835StatsOutput']: # Some entries can be removed.
        if key in metadata: del metadata[key]
        
    temp = NowUTC() # Consider this the end time of the process.
    metadata['ProcessDuration'] = (temp - StartupTime).total_seconds() # How long did the entire process take up to here?
    metadata['OverheadDuration'] = (temp - StartupTime).total_seconds() - (CaptureEndTime - CaptureStartTime).total_seconds() # How much time was taken on top of exposure time?
    metadata['CompletionTime'] = temp # When did generation end?
    MainLog.Log(PROGRAMNAME + ": metadata:",metadata,terminal=VerboseMode)
    MainLog.Log(PROGRAMNAME + ": jsonfilenames:",jsonfilenames,terminal=VerboseMode) 
    for fname in jsonfilenames: # Write json metadata to as many filenames as required.
        with open(fname,'w') as f: # Dump as json to disc.
            json.dump(metadata,f,indent=4,default=str) # Save the updated dictionary back to disc.

exit()
