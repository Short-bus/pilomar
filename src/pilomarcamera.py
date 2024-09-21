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
# THIS SOFTWARE CAN CONTROL ELECTRICAL AND MECHANICAL DEVICES. 
# THERE IS THEREFORE A RISK OF INJURY FROM INCORRECT ASSEMBLY, OPERATION OR FAILURE OF COMPONENTS.
# IT IS YOUR RESPONSIBILITY TO ENSURE THE SAFETY OF THE DEVICES YOU CHOOSE TO CONTROL WITH THIS SOFTWARE.

# Import required libraries
import time # sleep functionality for pauses in execution. 
import glob # file system.
import os # OS Command execution.
import math # Math and trig functions. 
import random # random number generator.
import cv2 # openCV for image file handling.  
from datetime import datetime, timedelta, timezone
from pilomartimer import timer,progresstimer # Pilomar's timer classes.
from pilomaroscommand import oscommand # Pilomar's OS command executor.
from pilomarimage import pilomarimage,pilomarkeogram # Pilomar's IMAGE BUFFER handler (combines numpy, OpenCV and pilomar specific routines)
from textcolor import textcolor # Basic colour and cursor control codes for terminal displays.
#from pidng.core import RPICAM2DNG # DNG data extraction from RPi camera RAW images. From https://github.com/schoolpost/pidng Needs to be 3.4.6 version. Later versions are not compatible.
import numpy as np # Fast array handling

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

class astrolens():
    """ Object representing the LENS being used by the telescope. 
        Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example. """
        
    LensList = [] # List of declared lenses. 
    
    def __init__(self,length,horizontal_fov,vertical_fov,aperture=2.8,logger=None,parameters=None):
        self.SetLogger(logger) # CamLog # Handle to the class that handles logging and error tracing.
        self.oscommand = oscommand(logger=logger.Log) # Create OS command executor.
        self.osCmd = self.oscommand.Execute
        self.CameraWindow = None
        self.ErrorWindow = None
        self.Parameters = parameters # Must define parameter file before using instance.
        self.BaseLength = length # The length of the lense WITHOUT any multiplier effect.
        self.Length = length # 'focal length' of the lens.
        self.EquivLength = self.Length * 5.6 # From https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/ 35mm equivalent focal length (?) (AKA the Crop Factor for the sensor?
        self.FovHorizontal = horizontal_fov
        self.FovVertical = vertical_fov
        self.Fov = min(self.FovHorizontal, self.FovVertical) # When calculating the FOV for a survey, use the smaller value.
        self.Aperture = aperture # FStop of the lens. *Q* Multiplier will impact this too. Hmm...
        self.ID = str(self.Length) + "|" + str(self.FovHorizontal) + "|" + str(self.FovVertical) # Unique ID of lens features.
        self.Log("AstroLens: Length:",str(self.Length),"mm (equiv.",str(self.EquivLength),"mm) FoV:",
                 str(self.FovHorizontal),"deg","*",str(self.FovVertical),"deg",terminal=False)
        astrolens.LensList.append(self) # Add this instance to the global list of all defined lenses.

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.Logger = logger # Logger instance.
        self.Log = self._NullLogger # No log method.
        self.ReportException = self._NullLogger # Cannot report exception details to logfile.
        self.RaiseException = self._NullLogger # Cannor report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        self.Log("astrolens.SetLogger: Linked to this log file.",terminal=False)

    def _NullLogger(self,*args, **kwargs):
        """ Null logger. Absorbs parameters and .log call but does nothing. 
            Use this when there is no logger defined. """
        return
        
    def EstimateFoV(self,length):
        """ Given 35mm equivalent focal length, this estimates the FoV for the lens on the Raspberry Pi Hi Quality sensor. 
            This is just an estimation to get you started. 
            The FoV can be finetuned by comparing the diameter of the moon's disc using astrocamera.CalibrateFoV function. """
        
        # Table entries.
        # [ 35mm focal length, horizontal FoV, vertical FoV ]
        # Table was found online on a couple of forums, there are online calculators too.
        FXFoVTable = [
        [10,121.9,100.4],
        [11,117.1,95.0],
        [12,112.6,90.0],
        [14,104.3,81.2],
        [15,100.4,77.3],
        [17,93.3,70.4],
        [18,90.0,67.4],
        [19,86.9,64.6],
        [20,84.0,61.9],
        [24,73.7,53.1],
        [28,65.5,46.4],
        [30,61.9,43.6],
        [35,54.4,37.8],
        [45,43.6,29.9],
        [50,39.6,27.0],
        [55,36.2,24.6],
        [60,33.4,22.6],
        [70,28.8,19.5],
        [75,27.0,18.2],
        [80,25.3,17.1],
        [85,23.9,16.1],
        [90,22.6,15.2],
        [100,20.4,13.7],
        [105,19.5,13.0],
        [120,17.1,11.4],
        [125,16.4,11.0],
        [135,15.2,10.2],
        [150,13.7,9.1],
        [170,12.1,8.1],
        [180,11.4,7.6],
        [200,10.3,6.9],
        [210,9.8,6.5],
        [300,6.9,4.6],
        [400,5.2,3.4],
        [500,4.1,2.7],
        [600,3.4,2.3],
        [800,2.6,1.7]
        ]
        
        # Search the table for surrounding entries.
        lower_entry = None
        upper_entry = None
        for entry in FXFoVTable:
            if entry[0] <= self.EquivLength:
                lower_entry = entry
            else: 
                upper_entry = entry
                break
        
        if lower_entry != None: # We found a reasonable match.
            self.FovHorizontal = lower_entry[1] # Start with this near match.
            self.FovVertical = lower_entry[2]
            # See if we can improve it.
            if upper_entry != None and self.EquivLength != lower_entry[0]:
                # Need to estimate a value between the two known entries.
                len_range = upper_entry[0] - lower_entry[0]
                hor_range = upper_entry[1] - lower_entry[1]
                ver_range = upper_entry[2] - lower_entry[2]
                prop = (self.EquivLength - lower_entry[0]) / len_range
                self.FovHorizontal = prop * hor_range + lower_entry[1]
                self.FovVertical = prop * ver_range + lower_entry[2]
        
        self.Log("astrolens.EstimateFoV():",self.EquivLength,self.FovHorizontal,self.FovVertical,terminal=False)
                
# ------------------------------------------------------------------------------------------------------

class astrosensor():
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
    SensorList = [] # List of declared sensors.

    def DenoiseStatus(self):
        """ With libcamera the denoise / onchip cleanup is set via the command template rather than the parameter file. """
        if self.Parameters.CameraDriver == 'raspistill': # These are the default commands for raspistill captures.
            result = not self.Parameters.DisableCleanup # Onchip cleanup is ENABLED unless we can prove otherwise.
        else:
            result = True # Denoise is ON unless explicitly turned off in the command line (checked next).
        try:
            elements = self.Parameters._CameraLightCommand.split(" ") # Check all the options.
            for i,element in enumerate(elements):
                if element == '--denoise': # We've found a denoise instruction in the camera command template.
                    if elements[i + 1] == 'off': # Onchip cleanup is disabled.
                        result = False
                    else:
                        result = True
                    break # Look no further.
        except:
            self.Log("astrosensor.DenoiseStatus(): Command template is incomplete.",terminal=False)
        return result

    def __init__(self,sensor_type='',pixel_width=4056,pixel_height=3040,max_seconds=200,min_seconds=0.0000001,logger=None,parameters=None,channel=None):
        """ Create new instance of astrosensor. 
        
            sensor_type: Optional sensor type, can set some parameters automatically if recognised. eg imx477
            pixel_width: Image format - width.
            pixel_height: Image format - height.
            max_seconds: Longest exposure time supported by the sensor (seconds).
            min_seconds: Shortest exposure time supported by the sensor (seconds).
            logger: Point to logfile instance. eg MainLog or CamLog
            parameters: Point to parameter instance. eg Parameters
            driver: Use raspistill or libcamera support on the RPi?
            channel: Optional channel number if RPi5 with multiple cameras supported.
            
            """
        self.SetLogger(logger) # CamLog # Handle to the class that handles logging and error tracing.
        self.oscommand = oscommand(logger=logger.Log) # Create OS command executor.
        self.osCmd = self.oscommand.Execute
        self.CameraWindow = None
        self.ErrorWindow = None
        self.Parameters = parameters # Must declare the parameter file before you can use the instance.
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
        self.Channel = channel # If RPi has multiple camera channels, indicate the channel here.
        self.OnChipCleanup = self.DenoiseStatus() # Records whether we've got the on-chip cleanup enabled or not. Raspistill feature. Libcamera does it through the command line.
        if self.Type in astrosensor.SensorDict: self.ModeDict = astrosensor.SensorDict[self.Type] # Select mode information for the chosen sensor.
        else: self.ModeDict = astrosensor.SensorDict['imx477'] # Default sensor for the telescope design.
        self.Log("AstroSensor: Size, " + str(self.PixelWidth) + "*" + str(self.PixelHeight),terminal=False)
        astrosensor.SensorList.append(self) # Add this instance to the global list of all defined sensors.

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.Logger = logger # Logger instance.
        self.Log = self._NullLogger # No log method.
        self.ReportException = self._NullLogger # Cannot report exception details to logfile.
        self.RaiseException = self._NullLogger # Cannor report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        self.Log("astrosensor.SetLogger: Linked to this log file.",terminal=False)

    def _NullLogger(self,*args, **kwargs):
        """ Null logger. Absorbs parameters and .log call but does nothing. 
            Use this when there is no logger defined. """
        return

    def HmsFromStamp(self,timestamp,dateaware=False):
        """ Return the HH:MM:SS part of a timestamp as a string.
            Works with datetime input. 
            dateaware = True. If the date is not today, then it shows 'DD HH:MM' instead. """
        result = None
        try:
            if timestamp is None: # Protect from null values.
                result = ""
            else:
                result = str(timestamp)
                if dateaware and timestamp.date() != self.NowUTC().date(): # The date is not today.
                    result = result[8:16] # Extract "DD HH:MM"
                else: # The date is today. Extract "HH:MM:SS"
                    result = result.split(" ")[1]
                    result = result.split(".")[0]
        except Exception as e:
            print(e) # Trap all the exception information in the main log file.
            raise Exception("HmsFromStamp() failed.") from e # Continue with regular exception stack.
        return result

    def NowHMS(self):
        """ Return current time as formatted string. 
            Returns HH:MM:SS string for the current time (UTC) """
        return self.HmsFromStamp(self.NowUTC())

    def NowUTC(self):
        """ Return system UTC timestamp as a datetime object. """
        return datetime.now(timezone.utc)
        
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
        if self.CameraWindow != None: self.CameraWindow.Print("Sensor mode: " + str(mode))
        self.Log("AstroSensor: Pixel dimensions now: " + str(self.PixelWidth) + "x" + str(self.PixelHeight),terminal=False)

    def DisableCleanup(self):
        """ Disable the on-chip image cleanup for the sensor.
            Even in RAW capture mode, the sensor will perform some image cleanup by default.
            This cleanup degrades the raw data that astro photo stacking software will work with.
            Therefore it is advisable to disable this cleanup before taking photos for stacking.            """
        if self.Parameters.CameraDriver == 'raspistill': #if OS_name in ['buster']:
            print (textcolor.yellow("Disabling sensor cleanup to improve purity of sensor raw data."))
            if not self.Type in ['imx477']: # Check that the sensor cleanup function actually can be disabled.
                self.Log("AstroSensor.DisableCleanup is not supported for " + self.Type + " sensors. Ignored.",level='warning')
                return False
            cmd = 'sudo vcdbg set imx477.dpc 0' # Turn off on-chip cleaning of the image.
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored. The output is not displayed, however pilomar logs it in case other errors occur in the future.
            self.Log(cmd,terminal=False)
            self.osCmd(cmd)
            self.OnChipCleanup = False # raspistill feature. Libcamera does it through the command line.
            self.Parameters.DisableCleanup = True # Cleanup is disabled.
            self.Log("Raspberry Pi High Quality Camera, on chip image cleanup DISABLED.",terminal=False)
            if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " On Chip Cleanup - OFF")
        else: # libcamera has a command line option to disable cleanup.
            self.Log("astrosensor.DisableCleanup: Please check the '--denoise off ' option in the command templates in the parameter file.",terminal=False)
        return True

    def EnableCleanup(self):
        """ Enable the on-chip image cleanup for the sensor.
            This returns the on-chip image cleanup back to the default state (ON)
            It is recommended to have it disabled for image stacking of raw images. """
        if self.Parameters.CameraDriver == 'raspistill': #if OS_name in ['buster']:
            print (textcolor.yellow("Enabling sensor cleanup to restore factory functionality."))
            if not self.Type in ['imx477']:
                self.Log("AstroSensor.EnableCleanup is not supported for " + self.Type + " sensors. Ignored.",level='warning')
                return False
            cmd = 'sudo vcdbg set imx477.dpc 3' # Turn on on-chip cleaning of the image.
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored. The output is logged but not displayed in case other errors occur in the future.
            self.Log(cmd,terminal=False)
            self.osCmd(cmd)
            self.OnChipCleanup = True # Raspistill feature, libcamera does it through the command line.
            self.Parameters.DisableCleanup = False 
            self.Log("Raspberry Pi High Quality Camera, on chip image cleanup ENABLED.",terminal=False)
            if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " On Chip Cleanup - ON")
        else: # libcamera has a command line option to disable cleanup.
            self.Log("astrosensor.EnableCleanup(): Please check the '--denoise off ' option is removed in the command templates in the parameter file.",terminal=False)
        return True

# ------------------------------------------------------------------------------------------------------

class astrocamera():

    CameraList = [] # List of cameras declared. 
    
    #@staticmethod
    #def SetGlobalFolderList(folderlist):
    #    """ Update FolderList in all declared cameras. """
    #    for camera in astrocamera.CameraList:
    #        camera.FolderList = folderlist

    @staticmethod
    def SetGlobalFolderHandler(folderhandler):
        """ Update FolderHAndler in all declared cameras. """
        for camera in astrocamera.CameraList:
            camera.FolderHandler = folderhandler

    @staticmethod
    def SetGlobalMctl(mctl):
        """ Update Microcontroller handler in all declared cameras. """
        for camera in astrocamera.CameraList:
            camera.Mctl = mctl
    
    @staticmethod
    def SetGlobalKeyboard(keyboard):
        """ Update Keyboard scanner handle in all declared cameras. """
        for camera in astrocamera.CameraList:
            camera.Keyboard = keyboard
    
    """ Object representing the camera assembly being used.
        It contains the LENS and SENSOR objects, also various attributes and settings of the overall camera. """
    def __init__(self,inp_sensor,inp_lens,exposure=10.0,trackingexposure=5.0,logger=None,parameters=None,imagesimulator=None):
        self.SetLogger(logger) # CamLog # Handle to the class that handles logging and error tracing.
        self.oscommand = oscommand(logger=logger.Log) # Create OS command executor.
        self.osCmd = self.oscommand.Execute
        # Helper functions and attributes, should be set in calling program.
        self.ImageSimulator = None # Can be handle to image simulation procedure. Must match CreateTargetImage() signature.
        self.RelativeAltAz = None # Can be handle to RelativeAltAz calculation. Must match RelativeAltAz() signature.
        self.PlotRelativeAltAz = None # Can be handle to PlotRelativeAltAz calculation. Must match PlotRelativeAltAz() signature.
        self.Keyboard = None # Can declare a keyboard scanner (textcolor keyboard scanner instance).
        self.ErrorWindow = None # Can declare an error window (textcolor library) to copy error messages to.
        self.CameraWindow = None # Can declare a camera window (textcolor library) to copy camera events to.
        self.StorageMonitor = None # Can declare a storage monitor class here.
        self.Parameters = parameters # Must define the parameter file before using the instance.
        self.FolderHandler = None # Local copy of the FolderList telling where to store files.
        # - 
        self.FileTypes = ['jpg','dng'] # List of file types to make available.
        self.ObjectType = None # What is the target type? Set by SetObservationParameters() from session information.
        self.Mctl = None # Handle to the microcontroller. Can monitor it for restarts.
        self.Sensor = inp_sensor # The sensor that makes up the camera.
        self.Lens = inp_lens # The lens that makes up the camera.
        self.ExposureSeconds = exposure # Exposure seconds per frame for astro photos ('light' frames).
        self.TrackingExposureSeconds = trackingexposure # Tracking photos are always 5 second exposure.
        self.TimelapseSeconds = None # Delay between successive exposures if taking timelapse images.
        self.TimelapseTimer = None # Handle to timelapse timer if set.
        self.PixelsPerFovDegreeWidth = 0 # Set by ModeChange() below. How many pixels represent 1 degree image width.
        self.PixelsPerFovDegreeHeight = 0 # Set by ModeChange() below. How many pixels represent 1 degree image height.
        self.PixelFovWidth = 0 # Set by ModeChange() below. # Approximate field of view of an individual pixel.
        self.PixelFovHeight = 0 # Set by ModeChange() below.
        self.SecondsPerPixel = 0.0 # Set by ModeChange() below. Specifies how long an object takes to traverse one pixel of an image.
        self.ModeChange() # Set values based upon sensor mode. 
        self.LastImageDateTime = None # When was the latest image taken? # *Q* How widely is this attribute used?
        self.Lastjpg = None # The filename of the last jpg taken (if saved)
        self.Previewjpg = None # The filename of the last preview image generated. 
        self.Image = pilomarimage(name='camera',logger=self.Logger) # pilomarimage instance for handling OpenCV image buffer.
        self.CaptureStart = None # Timestamp when image capture started. Used to detect camera hanging.
        self.CaptureEnd = None # Timestamp when image capture completed. Used to detect camera hanging.
        self.BatchCount = 0 # How many photos taken in the current observation batch? 
        self.ID = self.Sensor.ID + "|" + self.Lens.ID # Unique ID of lens and sensor characteristics.
        self.SetImageType('light') # The type of image being captured. Links to self.FolderHandler. Tells HOW to process the image and WHERE to store it.
        self.CameraTasks = [] # No tasks to perform yet.
        self.CurrentTask = None # The current task being performed by the camera.
        self.LastLightCommand = '' # Keep a note of the camera options used for the latest light image.
        # Observation specific settings. These override the general parameters in instances where the general parameters don't make sense. Eg meteor monitoring.
        self.CameraSaveDng = True
        self.CameraSaveJpg = True
        self.CameraSaveFits = False
        self.FastImageCapture = False
        self.CameraOptions = '' # The camera options passed to raspistill. These depend upon the image type being captured.
        self.RxCount = 0 # Number of messages received by camera thread.
        self.TxCount = 0 # Number of messages sent by camera thread.
        if self.Parameters.CameraDriver == 'raspistill':
            from pidng.core import RPICAM2DNG # DNG data extraction from RPi camera RAW images. From https://github.com/schoolpost/pidng Needs to be 3.4.6 version. Later versions are not compatible.
            self.PiDNG = RPICAM2DNG() # RPICAM2DNG() needed for Buster O/S raspistill operation.
        else:
            self.PiDNG = None # RPICAM2DNG() not needed for libcamera operation.
        astrocamera.CameraList.append(self) # Add this instance to the global list of all defined cameras.

    def NowUTC(self):
        """ Return system UTC timestamp as a datetime object. """
        return datetime.now(timezone.utc)
        
    def UtcTimeStamp(self):
        """ Return current UTC datetime value as a string of digits. Discard fractions of a second.
            Returns value in string format YYYYMMDDHHMMSS. """
        ds = None
        try:
            ds = str(self.NowUTC()).split(".")[0]
            ds = self.CleanDatetimeString(ds)
        except Exception as e:
            print(e) # Trap all the exception information in the main log file.
            raise Exception("astrocamera.UtcTimeStamp() failed.") from e # Continue with regular exception stack.
        return ds

    def CleanDatetimeString(self,line):
        """ Remove all the special characters from a timestamp string.
            Converts things like YYYY-MM-DD HH:MM:SS into YYYYMMDDHHMMSS """
        try:
            if not isinstance(line,str): line = str(line) # Auto-convert into a string if it isn't already.
            for a in ['-',' ',':','.']:
                line = line.replace(a,'')
            line = line[:14] # Only accurate to SECONDS currently.
        except Exception as e:
            print(e) # Trap all the exception information in the main log file.
            raise Exception("astrocamera.CleanDatetimeString() failed.") from e # Continue with regular exception stack.
        return line

    def HmsFromStamp(self,timestamp,dateaware=False):
        """ Return the HH:MM:SS part of a timestamp as a string.
            Works with datetime input. 
            dateaware = True. If the date is not today, then it shows 'DD HH:MM' instead. """
        result = None
        try:
            if timestamp is None: # Protect from null values.
                result = ""
            else:
                result = str(timestamp)
                if dateaware and timestamp.date() != self.NowUTC().date(): # The date is not today.
                    result = result[8:16] # Extract "DD HH:MM"
                else: # The date is today. Extract "HH:MM:SS"
                    result = result.split(" ")[1]
                    result = result.split(".")[0]
        except Exception as e:
            print(e) # Trap all the exception information in the main log file.
            raise Exception("HmsFromStamp() failed.") from e # Continue with regular exception stack.
        return result

    def NowHMS(self):
        """ Return current time as formatted string. 
            Returns HH:MM:SS string for the current time (UTC) """
        return self.HmsFromStamp(self.NowUTC())

    def HRSeconds(self, seconds: int) -> str:
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

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.Logger = logger # Logger instance.
        self.Log = self._NullLogger # No log method.
        self.ReportException = self._NullLogger # Cannot report exception details to logfile.
        self.RaiseException = self._NullLogger # Cannor report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        #self.Log("astrocamera.SetLogger: Linked to this log file.",terminal=False)

    def _NullLogger(self,*args, **kwargs):
        """ Null logger. Absorbs parameters and .log call but does nothing. 
            Use this when there is no logger defined. """
        return
        
    def PixelFoV(self):
        """ Return the approximate Field Of View of a single pixel.
            This measure is useful for calibrating the tolerance of trajectory segments. """
        if self.PixelsPerFovDegreeWidth != 0: self.PixelFovWidth = 1 / self.PixelsPerFovDegreeWidth
        else: self.PixelFovWidth = 0
        if self.PixelsPerFovDegreeHeight != 0: self.PixelFovHeight = 1 / self.PixelsPerFovDegreeHeight
        else: self.PixelFovHeight = 0
        self.Log("astrocamera.PixelFoV (w/h)", self.PixelFovWidth, self.PixelFovHeight,terminal=False)

    def SetObservationParameters(self,session):
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
        self.Target = session.Target # Keep local pointer to the Target object.
        self.ObjectType = session.Target.ObjectType # What type of object are we looking at?
        if self.ObjectType in ['aurora','meteor']: # Don't generate preview images for meteors or aurora.
            if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " No preview's generated for " + self.ObjectType + " recordings.")
            self.Log("astrocamera.SetObservationParameters No preview's generated for", self.ObjectType, "recordings.",terminal=False)
        elif self.Parameters.GeneratePreview == False:
            if self.CameraWindow != None: self.Print(self.NowHMS() + " Preview generation is disabled in parameters.")
            self.Log("astrocamera.SetObservationParameters Preview generation is disabled in parameters.",terminal=False)
        else: self.CameraTasks.append('preview') 
        if self.ObjectType in ['meteor','altaz','earth satellite','aurora']: # No need to perform drift tracking for these targets.
            # Don't track for fixed targets or fast moving targets.
            if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " No tracking performed for " + self.ObjectType + " targets.")
            self.Log("astrocamera.SetObservationParameters No tracking performed for", self.ObjectType, "targets.",terminal=False)
        else: # Do track for targets that rotate with the sky. Always add tracking to the tasklist, even if it's currently disabled. The tracking routine will handle that, and it could be dynamically enabled during the observation.
            self.CameraTasks.append('tracking') 
        self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", Selected tasks:", self.CameraTasks,terminal=False)
        
        # Set observation specific parameters for the camera based upon general parameter settings.
        # Eg 'meteor' mode can override some settings, but we don't want to disturb the general settings used for other targets.
        if self.ObjectType in ['aurora','meteor']: # Disable DNG generation if taking AURORA or METEOR images. 
            if self.CameraSaveDng: 
                self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", will not capture DNG (raw) images.",terminal=False)
                self.CameraSaveDng = False
        else: self.CameraSaveDng = self.Parameters.CameraSaveDng # Revert to parameter preference.
        self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", CameraSaveDng",self.CameraSaveDng,terminal=False)

        if self.ObjectType in ['aurora','meteor']: # Disable DNG generation if taking AURORA or METEOR images. 
            if self.CameraSaveFits: 
                self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", will not capture FITS (raw) images.",terminal=False)
                self.CameraSaveFits = False
        else: self.CameraSaveFits = self.Parameters.CameraSaveFits # Revert to parameter preference.
        self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", CameraSaveFits",self.CameraSaveFits,terminal=False)

        if self.ObjectType in ['aurora','meteor']: # Turn on JPG generation if not already set.
            if not self.CameraSaveJpg:
                self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", will capture JPG images.",terminal=False)
                self.CameraSaveJpg = True
        else: self.CameraSaveJpg = self.Parameters.CameraSaveJpg # Revert to parameter preference.
        self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", CameraSaveJpg",self.CameraSaveJpg,terminal=False)

        if self.ObjectType in ['aurora','meteor']: # Turn on Fast Image Capture if not already set.
            if not self.FastImageCapture:
                self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", will use FAST image capture. (Minimal processing)",terminal=False)
                self.FastImageCapture = True
        else: self.FastImageCapture = self.Parameters.FastImageCapture # Revert to parameter preference.
        self.Log("astrocamera.SetObservationParameters Target type", self.ObjectType,", FastImageCapture",self.FastImageCapture,terminal=False)

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
                     "Horizontal field of view: " + str(self.Lens.FovHorizontal) + "deg",
                     "Vertical field of view: " + str(self.Lens.FovVertical) + "deg",
                     "Minimum field of view: " + str(self.Lens.Fov) + "deg",
                     "Horizontal pixels per degree FOV: " + str(self.PixelsPerFovDegreeWidth),
                     "Vertical pixels per degree FOV: " + str(self.PixelsPerFovDegreeHeight),
                     "",
                     "The Moon's disc is " + str(MoonMeanDiaDeg) + "deg diameter on average.",
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
        while rawtext is None:
            rawtext = input(textcolor.cyan("How many pixels is the diameter of the Moon's full disc? ('x' to quit): "))
            rawtext = rawtext.lower()
            if rawtext == 'x':
                rawtext = None
                break # Quit
            if IsInt(rawtext):
                break # We have a value to use.
                
            print(textcolor.red("Please try again. Integer values only."))
            rawtext = None # Try again.
            
        if rawtext is None: 
            self.Log("astrocamera.CalibrateFov: No moon diameter value given",terminal=False)
            return # Nothing to do.

        self.Log("astrocamera.CalibrateFov: Moon diameter",rawtext,"pixels",terminal=False)

        # We have what we need.
        moonpixels = TextToInt(rawtext) # Convert the measured diameter into integer.
        print ("The camera records the moon as",moonpixels,"pixels in diameter.")
        print ("The moon is" + str(MoonMeanDiaDeg) + "deg in diameter on average.")
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
                     "Horizontal field of view: " + str(self.Lens.FovHorizontal) + "deg",
                     "Vertical field of view: " + str(self.Lens.FovVertical) + "deg",
                     "Minimum field of view: " + str(self.Lens.Fov) + "deg",
                     "Horizontal pixels per degree FOV: " + str(self.PixelsPerFovDegreeWidth),
                     "Vertical pixels per degree FOV: " + str(self.PixelsPerFovDegreeHeight), " ",
                     "The Moon's disc is " + str(MoonMeanDiaDeg) + "deg diameter on average.",
                     "Expected diameter in an image is about " + str(ExpectedDiaPix) + " pixels."]
        textcolor.TextBox(listlines)
        result = AskYesNo("Do you want to make these changes permanent? [y/N]",False)
        if result: # Make these changes permanent by setting them in the parameter file.
            self.Log("astrocamera.CalibrateFov: Making FoV permanent.",terminal=False)
            self.Parameters.LensHorizontalFov = self.Lens.FovHorizontal
            self.Parameters.LensVerticalFov = self.Lens.FovVertical
        else: # Don't touch the parameter settings, so the system will reset when restarted.
            self.Log("astrocamera.CalibrateFov: Making FoV temporary.",terminal=False)
            print (textcolor.yellow("These values are temporary. They will reset when you restart the software."))
            print (textcolor.red("To make these values permanent please edit LensHorizontalFov and LensVerticalFov values in the parameters file."))
            print (textcolor.red("(" + ParameterFileName + ")"))
        
    def SetImageType(self,imagetype):
        """ Validate and set the ImageType attribute.
            The image type must be in the self.FolderList dictionary. """
        #if imagetype in self.FolderList:
        if self.FolderHandler != None and self.FolderHandler.ValidKey(imagetype):
            self._ImageType = imagetype # OK to accept this image type.
            self.Log("astrocamera.SetImageType(",imagetype,") new image type set.",terminal=False)
        else: # ImageType has nowhere to go.
            #self.Log("astrocamera.SetImageType(",imagetype,") is not recognised. Must be in FolderList. Defaulting to 'light'.",terminal=False)
            self.Log("astrocamera.SetImageType(",imagetype,") is not recognised. Must be in FolderHandler. Defaulting to 'light'.",terminal=False)
            self._ImageType = 'light'
    
    def GetImageType(self):
        return self._ImageType

    def SetTimelapse(self,seconds):
        """ Set timelapse delay and initiate timer. """
        if seconds is None or seconds <= 0.0:
            self.TimelapseTimer = None
            self.TimelapseSeconds = None
        else:
            self.TimelapseTimer = timer(period=seconds)
            self.TimelapseSeconds = seconds

    def TimelapseDue(self):
        """ Return TRUE if the camera timelapse is active and due.
            Return TRUE if the camera timelapse is not active at all. 
            Return FALSE if the camera timelapse is active but not due. """
        if self.TimelapseTimer is None:
            return True # No timer, so always due.
        else:
            return self.TimelapseTimer.Due() # Use the real timer.

    def Reset(self):
        """ Reset camera settings at the beginning of a new session. """
        self.LastImageDateTime = None # When was the latest image taken?
        self.Lastjpg = None # The filename of the last jpg taken (if saved)
        self.Previewjpg = None # The filename of the last preview image generated. 
        self.Image.Clear() # openCV image buffer. Loaded explicitly when needed.
        self.CaptureStart = None # Timestamp when image capture started. Used to detect camera hanging.
        self.CaptureEnd = None # Timestamp when image capture completed. Used to detect camera hanging.
        self.BatchCount = 0 # How many photos taken in the current observation batch?
        if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " astrocamera.Reset")
        
    def CaptureStartAge(self):
        """ Return a timedelta object showing how long ago the last image capture began. 
            Returns None if no image captured yet. """
        result = None
        if self.CaptureStart != None:
            result = self.NowUTC() - self.CaptureStart
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
            result = self.NowUTC() - self.LastImageDateTime
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
        if self.Parameters.CameraEnabled and self.CaptureStart != None: # An attempt has been made and the camera is on!
            if self.CaptureEnd is None or self.CaptureEnd <= self.CaptureStart: # It hasn't completed yet.
                # Decide upon a sensible 'failure' delay to accept. At least 300seconds(5 minutes)
                # We have to be very generous here because this is a linux system and can sometimes pause a lot!
                faultdelay = max(self.ExposureSeconds * 5,500)
                if self.CaptureStartAgeSeconds() > faultdelay: # It has been running too long.
                    result = True # It looks like there's something wrong.
                    line = "astrocamera.CameraFault: Image capture time " + str(round(self.CaptureStartAgeSeconds(),1)) + "s is too long. The camera may have hung. Consider power cycling the RPi."
                    if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + ' ' + line)
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
            self.osCmd(cmd)
            self.Lastjpg = None # Clear the saved filename.

    def FakeAurora(self,srcimg): # Generate a fake aurora effect.
        """ Create a series of aurura like color blocks on an image. 
            srcimg = numpy buffer.
            Return combined image. """
        height = self.Sensor.PixelHeight # Image dimensions.
        width = self.Sensor.PixelWidth
        CurtainImage = pilomarimage(name='auroracurtain',logger=self.Logger) # Create empty image.
        auroracolors = [pilomarimage.BGR('LightGreen'),pilomarimage.BGR('DarkGreen'),pilomarimage.BGR('Cyan'),pilomarimage.BGR('HotPink')]
        for i,ac in enumerate(auroracolors): # Dim all the colors.
            auroracolors[i] = CurtainImage.DimColor(ac,0.2) # Reduce color intensity to nnn%
        fieldimg = srcimg.copy().astype(np.uint16) # Black image, datatype large enough for multiple layers to be combined.
        CurtainImage.New(height,width,imagetype='bgr',datatype=np.uint8)
        if CurtainImage.ImageMissing(): self.Log("astrocamera.FakeAurora: fakeimage.New() failed.",level='error',terminal=True)
        cornerlist = [] # Build cornerlist for polygon.
        for j in range(5): # Build polygon random corners. Start with bottom edge.
            cornerlist.append( ( int(width * j / 4) , random.randint(int(height * 0.6),int(height * 0.8)) ) )
        multiplier = 0.75
        revlist = cornerlist[::-1] # Reverse the bottom edge to produce the top edge of the polygon.
        for corner in revlist: # Scale all the top edge values so they are higher in the image by 20%.
            y = int(corner[1] * multiplier)
            cornerlist.append((corner[0],y))
        for i in range(len(auroracolors)): # Poll through the colors.
            curtaincolor = auroracolors[i] # Select color for this layer.
            CurtainImage.New(height,width,imagetype='bgr',datatype=np.uint8) # Empty the buffer for each curtain.
            for j in range(1,len(cornerlist)):
                CurtainImage.FillPolygon(cornerlist,color=curtaincolor)
            fieldimg = np.add(fieldimg,CurtainImage.ImageBuffer) # Apply the curtain object on top of the base image.
            # Reduce height of all corners for next color.
            cornerlist = [(corner[0],int(corner[1] * multiplier)) for corner in cornerlist]
        fieldimg = np.clip(fieldimg,0,255).astype(np.uint8) # Clip to uint8 values.
        return fieldimg

    def FakePollution(self,srcimg): # Generate fake light pollution.
        """ Create a small blank image and add some fake light pollution to it. 
            srcimg = numpy buffer.
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
        if self.Parameters.UseLiveLocation: # Use the live target location rather than the last reported camera position for image processing.
            CentreAz, CentreAlt = self.Target.AzAltDegrees() # What is the alt/az location of the centre of the image?
        else: # Use the last reported camera position. Deprecated.
            CentreAlt, CentreAz = LastReportedAltAz() # What is the alt/az location of the centre of the image?
        self.Log("astrocamera.FakePollution: CentreAltAz",CentreAlt, CentreAz,terminal=False)
        RelAlt, RelAz = self.RelativeAltAz(0,CentreAz,CentreAlt,CentreAz) # Image pixel height of horizon. (Thickest pollution level).
        _, HorizonY = self.PlotRelativeAltAz(RelAlt,RelAz,self.Sensor.PixelHeight,self.Sensor.PixelWidth) # Covert to pixel height.
        self.Log("astrocamera.FakePollution: HorizonAltAz",RelAlt,RelAz,HorizonY,terminal=False)
        RelAlt, RelAz = self.RelativeAltAz(PollutionMaxAlt,CentreAz,CentreAlt,CentreAz) # Image pixel height of pollution upper limit. (Thinnest pollution level)
        _, TopY = self.PlotRelativeAltAz(RelAlt,RelAz,self.Sensor.PixelHeight,self.Sensor.PixelWidth) # Covert to pixel height.
        self.Log("astrocamera.FakePollution: TopAltAz",RelAlt,RelAz,TopY,terminal=False)
        self.Log("astrocamera.FakePollution: Horizon height",HorizonY,"px",terminal=False)
        self.Log("astrocamera.FakePollution: Top height",TopY,"px, (PollutionMaxAlt",PollutionMaxAlt,"deg)",terminal=False)
        fieldimg = np.zeros((self.Sensor.PixelHeight,self.Sensor.PixelWidth,3),np.uint16) # Black image.

        fieldimg[:,:] = np.array(ThinnestValue).astype(np.uint16) # Set ALL pixels to the thinnest haze value by default.

        if HorizonY < self.Sensor.PixelHeight: # Horizon is in range.
            # Fill everything below horizon with Thickest pollution value.
            for i in range(max(0,HorizonY),self.Sensor.PixelHeight):
                fieldimg[i,:] = np.array(ThickestValue).astype(np.uint16)

        # Now to calculate the gradient values where the haze builds up as it approaches the horizon. 
        
        # Remember that images count rows from top down.
        rowspan = HorizonY - TopY # How many rows to fill with the gradient if the image was infinitely tall?

        # Constrain the Top of the gradient to within the image boundary.
        if TopY < 0: startrow = 0
        elif TopY > self.Sensor.PixelHeight: startrow = self.Sensor.PixelHeight
        else: startrow = TopY

        # Constrain the Horizon to within the image boundary.
        if HorizonY < 0: endrow = 0
        elif HorizonY > self.Sensor.PixelHeight: endrow = self.Sensor.PixelHeight
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
        return fieldimg 

    def FakePhoto(self,outputfile,astrotime=None):
        # Generate false disc file to simulate a photograph being captured. 
        self.Log("astrocamera.FakePhoto: Simulating photo capture (",outputfile,")",terminal=False)
        fakeimage = pilomarimage(name='fakephoto',logger=self.Logger)
        height = self.Sensor.PixelHeight
        width = self.Sensor.PixelWidth
        fakeimage.New(height,width,imagetype='bgr',datatype=np.uint8)
        if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: fakeimage.New() failed.",level='error',terminal=True)
        #fakeimage.ImageBuffer,starcount,starlist = CreateTargetImage(color=True,MinMagnitude=self.Parameters.TargetMinMagnitude,astrotime=astrotime) # Use CreateTargetImage to make fake photo.
        fakeimage.ImageBuffer,starcount,starlist = self.ImageSimulator(color=True,MinMagnitude=self.Parameters.TargetMinMagnitude,astrotime=astrotime) # Use CreateTargetImage to make fake photo.
        if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: ImageSimulator() failed.",level='error',terminal=True)
        if self.Parameters.FakeNoise: # Simulate fake image noise.
            fakeimage.FakeNoise()
            if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: FakeNoise() failed.",level='error',terminal=True)
        if self.Parameters.FakeField: # Simulate fake electrical field noise in the image.
            fakeimage.FakeField()
            if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: FakeField() failed.",level='error',terminal=True)
        if self.Parameters.FakePollution: # Simulate fake light pollution.
            fakeimage.ImageBuffer = self.FakePollution(fakeimage.ImageBuffer)
            if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: FakePollution() failed.",level='error',terminal=True)
        if self.ObjectType in ['aurora'] and self.Parameters.FakeAurora: # Simulate aurora
            fakeimage.ImageBuffer = self.FakeAurora(fakeimage.ImageBuffer)
            if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: FakeAurora() failed.",level='error',terminal=True)
        if self.Parameters.FakeMeteor and random.randint(0,100) < self.Parameters.FakeMeteorPercent: # 2% of images get fake meteor streaks in them.
            fakeimage.FakeMeteor()
            if fakeimage.ImageMissing(): self.Log("astrocamera.FakePhoto: FakeMeteor() failed.",level='error',terminal=True)
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
        fakeimage = pilomarimage(name='fakedark',logger=self.Logger)
        height = self.Sensor.PixelHeight
        width = self.Sensor.PixelWidth
        fakeimage.New(height,width,imagetype='bgr',datatype=np.uint8)
        fakeimage.FillColor((0,0,0)) # Black.
        if self.Parameters.FakeNoise: # Simulate fake image noise.
            fakeimage.FakeNoise()
        if self.Parameters.FakeField: # Simulate fake electrical field noise in the image.
            fakeimage.FakeField()
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
        camera_command = camera_command.replace('{&mode}',str(self.Sensor.Mode)) # Camera Mode.
        camera_command = camera_command.replace('{&channel}',str(self.Sensor.Channel)) # Camera channel if multi-camera RPi.
        camera_command = camera_command.replace('{&width}',str(self.Sensor.PixelWidth)) # Image width.
        camera_command = camera_command.replace('{&height}',str(self.Sensor.PixelHeight)) # Image height.
        if self.FastImageCapture: # Just capture the images as fast as possible, don't waste time processing anything else.
            result = self.CaptureSetFast(file_root,batch_size,camera_command,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime)
        else: # Complete image capture and processing at the same time.
            result = self.CaptureSetFull(file_root,batch_size,camera_command,tempfile=tempfile,terminal=terminal,cleanup=cleanup,astrotime=astrotime)
        return result
    
    def CaptureSetFull(self,file_root,batch_size,camera_command,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take a batch of photos... 
            This captures and processes each image in turn.
            cleanup = True. means that intermediate files (.jpg) are deleted when finished with. 
                      False. means that the intermediate files (.jpg) are retained for the calling function to deal with.
                      astrocamera.Lastjpg contains the filename of the .jpg file generated. 
            tempfile = True. Means that a single temporary filename is used each time.
            terminal=True. Means that the progress message is shown on the terminal.
            astrotime = the timestamp of the image to be generated if we're faking the result.
            stacker = a handle to a live image stacker object if we're live stacking. """
        result = True
        self.Log("astrocamera.CaptureSetFull(): Capturing " + str(batch_size) + " images...",terminal=False)
        dt_start = self.NowUTC()
        self.LastLightCommand = camera_command # keep a note of the exposure options, it's reported in the preview images.
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(2) # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile: outputfile = file_root + 'temp.jpg' # This is the 'intermediate' jpg generated by the camera.
            else: outputfile = file_root + self.UtcTimeStamp() + "_" + frame + '.jpg' # This is the 'intermediate' jpg generated by the camera.
            self.Log("astrocamera.CaptureSetFull(): Capturing",outputfile,"...",terminal=False)
            cmd = camera_command.replace('{&output}',outputfile) # *Q* TODO: Perform safety check for remaining & symbols.
            if self.Mctl != None: # Microcontroller handle is defined.
                remoterestarts = self.Mctl.RemoteRestarts # If this changes during exposure, the microcontroller has reset and we should reject the image.
            else:
                remoterestarts = 0
            rejectimage = False # Set to 'true' if there's a reason to reject the image.
            self.CaptureStart = self.NowUTC()
            if self.Parameters.CameraEnabled: # Camera is enabled. Take real photo.
                self.osCmd(cmd,output='none')
                retc = self.oscommand.ReturnCode # What did the camera command exit with ?
                self.Log("astrocamera.CaptureSetFull(): Return code:",retc,terminal=False)
                if retc != 0: # Non zero return code. Did something go wrong?
                    if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " Return code " + str(retc),fg=textcolor.YELLOW)
                    if self.ErrorWindow != None: self.ErrorWindow.Print(self.NowHMS() + " capture returned code " + str(retc),fg=textcolor.YELLOW)
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
            self.CaptureEnd = self.NowUTC()
            self.Log("astrocamera.CaptureSetFull(): Capture complete. (",(self.CaptureEnd - self.CaptureStart).total_seconds(), "s).",terminal=False)
            if self.Mctl != None: # Microcontroller handle is known.
                if remoterestarts != self.Mctl.RemoteRestarts: # Microcontroller reset during exposure.
                    self.Log('astrocamera.CaptureSetFull(): Microcontroller restarted during exposure. Reject',outputfile,level='warning',terminal=False)
                    if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " Motors reset during exposure.") # Just the filename.
                    if self.ErrorWindow != None: self.ErrorWindow.Print(self.NowHMS() + " Motors reset during exposure.") # Just the filename.
                    rejectimage = True # We should reject this image.
            if not tempfile: # Display the filename if it's permanent, ignore the tempfile.
                if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " " + outputfile.split('/')[-1]) # Just the jpg filename.
            if rejectimage: # There was reason to reject the image for some cause.
                self.Log("astrocamera.CaptureSetFull(): Image should be rejected.",terminal=False)
            self.Lastjpg = outputfile # The camera can remember this file as the 'last jpg taken'
            self.Log("astrocamera.CaptureSetFull(): Load image from " + outputfile,terminal=False)
            self.Image.LoadFile(outputfile) # OpenCV format.
            if self.Image.ImageMissing(): # imread failed. The capture did not succeed for some reason?
                self.Log("astrocamera.CaptureSetFull(): imread of",outputfile,"failed.",level='error',terminal=False)
            self.LastImageDateTime = self.NowUTC() # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.Log("astrocamera.CaptureSetFull(): Image loaded.",terminal=False)
            if (" -r " in (camera_command + ' ') or " --raw " in (camera_command + ' ')) and self.Parameters.CameraEnabled: # The jpg contains RAW data in the file tags, extract it. Convert it.
                if self.Parameters.CameraDriver == 'raspistill': # We need to manually extract the DNG data.
                    # with raspistill convert to RAW. We have to extract the raw data RAW for .dng files to be saved.
                    self.Log("astrocamera.CaptureSetFull(): Converting to RAW (.DNG) file...",terminal=False)
                    dngname = outputfile.replace('.jpg','.dng')
                    try:
                        self.PiDNG.convert(outputfile) # Convert the saved .jpg file into the raw .dng format.
                    except Exception as e:
                        self.ReportException(e,comment='astrocamera.CaptureSetFull(): PiDNG.convert failed.')
                    self.Log("astrocamera.CaptureSetFull(): Converted to RAW (.DNG) file.",terminal=False)
                    # Cleanup. Remove any intermediate files that are nolonger needed.
                    if self.CameraSaveJpg: # We should save only the jpg data, stripping out any embedded additional RAW data 
                        self.Image.SaveFile(outputfile) # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else: # We're only saving the RAW data, so just delete the original jpg file.
                        self.Log("astrocamera.CaptureSetFull(): Deleting intermediate .jpg file...",terminal=False)
                        self.CleanupLastjpg() # We've finished with the original .jpg on disc.
                    if not self.CameraSaveDng: # We don't need to keep the .dng file anymore.
                        self.Log("astrocamera.CaptureSetFull(): DNG nolonger needed.",terminal=False)
                        cmd = 'rm ' + dngname
                        self.osCmd(cmd,output='log')
                    else:
                        if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " " + dngname.split('/')[-1]) # Just the dng filename.
                elif self.Parameters.CameraDriver == 'pilomarfits': # The .fits file will have been made automatically for us.
                    fitsname = outputfile.replace('.jpg','.fits') # Construct the .fits filename we expect.
                    self.Log("astrocamera.CaptureSetFull(): FITS file should have been generated too.",terminal=False)
                    if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " " + fitsname.split('/')[-1]) # Just the dng filename.
            if tempfile: # Delete the temporary file.
                cmd = 'rm ' + outputfile
                self.osCmd(cmd,output='log')
            # Estimate ETA. If we're looping through a batch of photos.
            if batch_size > 1:
                dt_now = self.NowUTC() # Current time.
                td_elapsed = dt_now - dt_start # Elapsed time.
                dt_eta = dt_start + (batch_size * td_elapsed / (i + 1)) # Estimate completion time.
                pc_complete = int(100 * (i + 1.0) / batch_size) # Estimate how far through the batch of photos we are.
                if self.StorageMonitor != None:
                    self.Log("astrocamera.CaptureSetFull:",str(i + 1),"of",str(batch_size),"(",str(pc_complete),"%), Disc:",
                             str(int(self.StorageMonitor.FreeMegaBytes())),"Mb, ETA:",str(dt_eta).split(" ")[1].split(".")[0],terminal=terminal)
                else:
                    self.Log("astrocamera.CaptureSetFull:",str(i + 1),"of",str(batch_size),"(",str(pc_complete),"%), Disc: UNKNOWN, ETA:",
                             str(dt_eta).split(" ")[1].split(".")[0],terminal=terminal)
                if i < batch_size - 1: # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print (textcolor.cursorup() + textcolor.cursorup()) # Stay on the same line for the CaptureSet message to the terminal.
            if self.StorageMonitor != None and self.StorageMonitor.DiscOK() != True: # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.Log("astrocamera.CaptureSetFull(): Out of disc space. Stopping.",level='error')
                result = False
                break
        self.Log("astrocamera.CaptureSetFull(): Completed",terminal=False)
        return result

    def CaptureSetFast(self,file_root,batch_size,camera_command,tempfile=False,terminal=True,cleanup=True,astrotime=None):
        """ Take a batch of photos... 
            This just captures the combined JPG & DNG data file. It does not perform conversion to other file types.
            This is testing if it improves performance for image capture by delaying processing until the observation is over.

            cleanup = True. means that intermediate files (.jpg) are deleted when finished with. 
                      False. means that the intermediate files (.jpg) are retained for the calling function to deal with.
                      astrocamera.Lastjpg contains the filename of the .jpg file generated. 
            tempfile = True. Means that a single temporary filename is used each time.
            terminal=True. Means that the progress message is shown on the terminal.
            astrotime = the timestamp of the image to be generated if we're faking the result.
            stacker = a handle to a live image stacker object if we're live stacking. """
        result = True
        self.Log("astrocamera.CaptureSetFast(): Capturing " + str(batch_size) + " images...",terminal=False)
        dt_start = self.NowUTC()
        self.LastLightCommand = camera_command # keep a note of the exposure options, it's reported in the preview images.
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(2) # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile: outputfile = file_root + 'temp.jpg' # This is the 'intermediate' jpg generated by the camera.
            else: outputfile = file_root + self.UtcTimeStamp() + "_" + frame + '.jpg' # This is the 'intermediate' jpg generated by the camera.
            self.Log("astrocamera.CaptureSetFast(): Capturing",outputfile,"...",terminal=False)
            cmd = camera_command.replace('{&output}',outputfile) # *Q* TODO: Perform safety check for remaining & symbols.
            if self.Mctl != None: # Microcontroller handle is defined.
                remoterestarts = self.Mctl.RemoteRestarts # If this changes during exposure, the microcontroller has reset and we should reject the image.
            else:
                remoterestarts = 0
            rejectimage = False # Set to 'true' if there's a reason to reject the image.
            self.CaptureStart = self.NowUTC()
            if self.Parameters.CameraEnabled: # Camera is in use. Take real photo.
                self.osCmd(cmd,output='none')
                retc = self.oscommand.ReturnCode # What did the camera command exit with ?
                self.Log("astrocamera.CaptureSetFast(): Return code:",retc,terminal=False)
                if retc != 0: # Non zero return code. Did something go wrong?
                    if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " Return code " + str(retc),fg=textcolor.YELLOW)
                    if self.ErrorWindow != None: self.ErrorWindow.Print(self.NowHMS() + " capture returned code " + str(retc),fg=textcolor.YELLOW)
            else: # Camera is not in use. Generate fake photo.
                self.Log("astrocamera.CaptureSetFast(): About to call FakePhoto.",terminal=False)
                tr = False # Fake image generation failed unless we are told otherwise.
                imty = self.GetImageType() # What type of image are we faking?
                DelayTimer = self.SetFakeDelay(camera_command) # Create a timer to mimic the expected real camera delay.
                if imty == 'dark': tr= self.FakeDark(outputfile=outputfile) # Fake a dark frame.
                else: tr = self.FakePhoto(outputfile=outputfile,astrotime=astrotime) # Fake a light frame.
                if not tr: # Image generation failed.
                    self.Log("astrocamera.CaptureSetFast(): Fake image call failed (",imty,").",terminal=True,level='error')
                else: # Fake the expected exposure time if a real image was being captured.
                    DelayTimer.Wait() # Wait until the fake delay timer expires. Thread pauses here.
                self.Log("astrocamera.CaptureSetFast(): Returned from FakePhoto.",terminal=False)
            self.CaptureEnd = self.NowUTC()
            self.Log("astrocamera.CaptureSetFast(): Capture complete. (",(self.CaptureEnd - self.CaptureStart).total_seconds(), "s).",terminal=False)
            if self.Mctl != None: # Microcontroller handle is known.
                if remoterestarts != self.Mctl.RemoteRestarts: # Microcontroller reset during exposure.
                    self.Log('astrocamera.CaptureSetFast(): Microcontroller restarted during exposure. Reject',outputfile,level='warning',terminal=False)
                    if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " Motors reset during exposure.") # Just the filename.
                    if self.ErrorWindow != None: self.ErrorWindow.Print(self.NowHMS() + " Motors reset during exposure.") # Just the filename.
                    rejectimage = True # We should reject this image.
            if not tempfile: # Display the filename if it's permanent, ignore the tempfile.
                if self.CameraWindow != None: self.CameraWindow.Print(self.NowHMS() + " " + outputfile.split('/')[-1]) # Just the jpg filename.
            if rejectimage: # There was reason to reject the image for some cause.
                self.Log("astrocamera.CaptureSetFast(): Image should be rejected.",terminal=False)
            self.Lastjpg = outputfile # The camera can remember this file as the 'last jpg taken'
            self.Log("astrocamera.CaptureSetFast(): Load image from " + outputfile,terminal=False)
            self.Image.LoadFile(outputfile) # OpenCV format.
            if self.Image.ImageMissing(): # imread failed. The capture did not succeed for some reason?
                self.Log("astrocamera.CaptureSetFast(): imread of",outputfile,"failed.",terminal=False)
            self.LastImageDateTime = self.NowUTC() # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.Log("astrocamera.CaptureSetFast(): Image loaded.",terminal=False)
            # Estimate ETA. If we're looping through a batch of photos.
            if batch_size > 1:
                dt_now = self.NowUTC() # Current time.
                td_elapsed = dt_now - dt_start # Elapsed time.
                dt_eta = dt_start + (batch_size * td_elapsed / (i + 1)) # Estimate completion time.
                pc_complete = int(100 * (i + 1.0) / batch_size) # Estimate how far through the batch of photos we are.
                if self.StorageMonitor != None:
                    self.Log("astrocamera.CaptureSetFast():",str(i + 1),"of",str(batch_size),"(",str(pc_complete),"%), Disc:",
                             str(int(self.StorageMonitor.FreeMegaBytes())),"Mb, ETA:",str(dt_eta).split(" ")[1].split(".")[0],terminal=terminal)
                else:
                    self.Log("astrocamera.CaptureSetFast():",str(i + 1),"of",str(batch_size),"(",str(pc_complete),"%), Disc: UNKNOWN, ETA:",
                             str(dt_eta).split(" ")[1].split(".")[0],terminal=terminal)
                if i < batch_size - 1: # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print (textcolor.cursorup() + textcolor.cursorup()) # Stay on the same line for the CaptureSet message to the terminal.
            if self.StorageMonitor != None and self.StorageMonitor.DiscOK() != True: # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.Log("astrocamera.CaptureSetFast(): Out of disc space. Stopping.",level='error')
                result = False
                break
        self.Log("astrocamera.CaptureSetFast(): Completed",terminal=False)
        return result

    def DatetimeFromFilename(self,filename):
        """ Construct a datetime value from a filename.
            eg "light_YYYYMMDDHHMMSS_nn.jpg" """
        filename = filename.split("/")[-1] # Get file from full path.
        filename = filename.split("_")[1] # Get the timestamp from full path.
        year = int(filename[:4])
        month = int(filename[4:6])
        day = int(filename[6:8])
        hour = int(filename[8:10])
        minute = int(filename[10:12])
        second = int(filename[12:14])
        dt = datetime(year,month,day,hour,minute,second,0,tzinfo=timezone.utc)
        return dt
        
    def BuildKeogram(self,altitude=None,azimuth=None):
        """ Build keogram for current /light folder contents.
            This extracts data from all /light_*.jpg files found in the folder. 
            It creates a temporary instance of pilomarkeogram() to process the data. 
            At the end it saves a /keogram.jpg file in the same /light folder. """
        self.Log("astrocamera.BuildKeogram(): Starting",terminal=False)
        rootfolder = self.FolderHandler.GetPath('light') # This is the parent data folder for all Pilomar images.
        filepattern = rootfolder + '/light_*.jpg'
        self.Log("astrocamera.BuildKeogram(): Searching",filepattern,terminal=False)
        allfiles = glob.glob(filepattern, recursive=False) # Every jpg in this folder.
        filecount = len(allfiles)
        start = None # Earliest image.
        end = None # Latest image.
        if len(allfiles) > 0:
            keogramfile = self.FolderHandler.PrepFile('light','keogram.jpg') # Target filename.
            prgt = progresstimer('keogram',target=filecount) # Report progress and ETA.
            self.Log("astrocamera.BuildKeogram(): Processing",filecount,"images.",terminal=False)
            print(" ")
            Keo = pilomarkeogram('keogram',self.Sensor.PixelWidth,self.Sensor.PixelHeight) # Define new Keogram instance.
            imagehandler = pilomarimage('keogram-input',logger=self.Logger) # Load each image in turn.
            for i,file in enumerate(allfiles): # Go through all the .jpg files found.
                prgt.UpdateCount(i + 1) # How far have we got so far? prgt will then produce ETA and % complete for us.                
                self.Log("astrocamera.BuildKeogram(): Processing",file,terminal=False)
                print(textcolor.cursorup() + 
                      self.NowHMS(),
                      textcolor.white(str(round(prgt.GetPercent(),1))),"%",
                      (i + 1),"of",filecount,
                      "ETA",str(prgt.GetETA()).split('.')[0],
                      "UTC",textcolor.clearlineforward())
                dt = self.DatetimeFromFilename(file) # Get the UTC timestamp of the image from the filename.
                if dt != None:
                    if start == None or start > dt: start = dt
                    if end == None or end < dt: end = dt
                imagehandler.LoadFile(file)
                Keo.Extract(imagehandler)
            # Markup image.
            Keo.BuildImageBuffer() # Load the resulting raw keogram into a pilomarimage instance. (For markup)
            width = Keo.Keogram.GetWidth()
            height = Keo.Keogram.GetHeight()
            # Add altitude scale
            BaseAlt = altitude - (self.Lens.FovVertical / 2) # What altitude does the bottom of the image represent?
            TopAlt = altitude + (self.Lens.FovVertical / 2) # What altitude does the top of the image represent?
            FloorAlt = math.floor(BaseAlt) # Lowest integer altitude, will be just below the bottom edge of the image.
            CeilingAlt = math.ceil(TopAlt) # Heighest integer altitude, will be just above the top edge of the image.
            Keo.Keogram.DrawLine((width - 10,0),(width - 10,height),color=pilomarimage.BGR('Yellow')) # Draw axis for altitude tick marks.
            Keo.Keogram.AddText("Altitude",width - 10,40,color=pilomarimage.BGR('Yellow'),hjust='r') # Label the altitude axis.
            for a in range(FloorAlt,CeilingAlt): # Mark off each degree of altitude.
                y = height - int(height * (a - BaseAlt) / (TopAlt - BaseAlt)) # Pixel height up the image for this degree marker.
                Keo.Keogram.DrawLine((width - 50,y),(width - 10,y),color=pilomarimage.BGR('Yellow')) # Draw tickmark for the degree marker.
                Keo.Keogram.AddText(str(a) + "deg",width - 50,y,color=pilomarimage.BGR('Yellow'),hjust='r') # Label the degree marker.
            if len(allfiles) > 1: # Need at least 2 files in order to add time scale.
                Keo.Keogram.DrawLine((0,height - 10),(width,height - 10),color=pilomarimage.BGR('Cyan')) # Draw horizontal axis for the time scale.
                Keo.Keogram.AddText("<-" + str(start)[11:19],10,height - 130,color=pilomarimage.BGR('Cyan'),hjust='l') # Mark START time.
                Keo.Keogram.AddText(str(end)[11:19] + "->",width - 10,height - 130,color=pilomarimage.BGR('Cyan'),hjust='r') # Mark END time.
                Keo.Keogram.AddText("< Time >",int(width / 2),height - 10,color=pilomarimage.BGR('Cyan'),vjust='t',hjust='c') # Label the axis.
                # Add time scale
                FloorTime = datetime(start.year,start.month,start.day,start.hour,0,0,0,tzinfo=timezone.utc) # Hour just before observation starts (Just off the left of the image)
                CeilingTime = datetime(end.year,end.month,end.day,end.hour,0,0,0,tzinfo=timezone.utc) + timedelta(hours=1) # Hour just after observation ends (Just off the right of the image)
                RangeTime = int((CeilingTime - FloorTime).total_seconds()) # What's the timespan of the Floor to Ceiling time (in seconds).
                ObservationTime = int((end - start).total_seconds()) # What's the timespan of the actual observation images (in seconds).
                PixelsPerSecond = width / ObservationTime # How many pixels represent 1 second of time?
                x_offset = (start - FloorTime).total_seconds() * PixelsPerSecond # Calculate a pixel offset for the time scale, it will start at FloorTime to the left of the image.
                if ObservationTime > 7200: RangeStep = 3600 # If observation is > 2hrs, label the Hourly tickmarks.
                elif ObservationTime > 1200: RangeStep = 600 # If Observation is > 20 minutes, label in 10 minute tickmarks.
                else: RangeStep = 300 # Label in 5 minute tickmarks.
                for a in range(0,RangeTime,RangeStep): # Mark significant time steps.
                    x = int(a * PixelsPerSecond - x_offset) # X axis location for the tickmark.
                    Keo.Keogram.DrawLine((x,height - 10),(x,height - 100),color=pilomarimage.BGR('Cyan')) # Draw tickmark.
                    text = str(FloorTime + timedelta(seconds=a))[11:19] # Calculate HH:MM:SS time of the tickmark.
                    Keo.Keogram.AddText(text,x,height - 100,color=pilomarimage.BGR('Cyan'),hjust='c') # Label the tickmark with the HH:MM:SS time.
            # Add key/labels
            linelist = [] # Start assembling a block of text.
            linelist.append("Observation start: " + str(start).split('+')[0] + " UTC")
            linelist.append("Observation end: " + str(end).split('+')[0] + " UTC")
            if start != None and end != None:
                linelist.append("Duration: " + self.HRSeconds((end - start).total_seconds()))
            linelist.append("Images captured: " + str(Keo.SampleCount))
            linelist.append("Target alt: " + str(altitude) + ", az:" + str(azimuth))
            if altitude != None:
                linelist.append("Altitude range: " + str(round(BaseAlt,1)) + "deg to " + str(round(TopAlt,1)) + "deg")
            ypos = 50 # Text box at TOP of image.
            Keo.Keogram.AddTextBlock(linelist,20,ypos,size=1,color=pilomarimage.BGR('White'),bgcolor=pilomarimage.BGR('Black'),border=3) # Write data.
            # Save resulting image.    
            Keo.SaveFile(keogramfile)
        print("") # Move cursor down so that the stats can be seen.
        return True
    
    def ProcessImageFiles(self):
        """ If image conversions were not done during capture, this can find and convert all the 
            image files currently in storage. This is used if CaptureSetFast was used to gather 
            images as quickly as possible. 
            This will convert all image files found the have the characteristics of a jpg with embedded raw data. """
        self.Log("astrocamera.ProcessImageFiles(): Starting",terminal=True)
        rawfilesize = 1024 * 1024 * 20 # Files containing raw data are quite large, set the threshold at 20Mb
        # Find all image files that need converting.
        rootfolder = self.FolderHandler.GetPath('imageroot') # This is the parent data folder for all Pilomar images.
        #allfiles = glob.glob(rootfolder + '**/*.jpg', recursive=True) # Every jpg in every folder and subfolder.
        filepattern = rootfolder + '/**/*.jpg'
        self.Log("astrocamera.ProcessImageFiles(): Searching",filepattern,terminal=True)
        allfiles = glob.glob(filepattern, recursive=True) # Every jpg in every folder and subfolder.
        files = [] # Cleaned list of files to handle.
        folders = ['/flat/','/bias/','/light/','/darkflat/','/dark/'] # Which subfolders do we want?
        for file in allfiles: # Go through all the .jpg files found.
            for folder in folders: # Check all the image folder/types.
                if folder in file: # This is an image/type that we should consider converting.
                    # How big is the file? Large ones need converting.
                    if os.stat(file).st_size > rawfilesize: # File is large enough to convert.
                        files.append(file) # Add to list of files to process.
                    break # No need to check anything else in the folder list.
        # Convert them.
        filecount = len(files)
        self.Log("astrocamera.ProcessImageFiles(): Found", filecount, "files to process.",terminal=True)
        tempimage = pilomarimage(name='temp',logger=self.Logger)
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
                            self.PiDNG.convert(file) # Convert the saved .jpg file into the raw .dng format. The .dng filename is automatically generated.
                        except Exception as e:
                            CamLog.ReportException(e,comment='astrocamera.ProcessImageFiles() error when converting to DNG file.')
                    # Replace the .jpg file with a simpler file, or delete it completely.
                    if self.CameraSaveJpg: # We should save 'JUST' the jpg data, effectively stripping out the embedded RAW data 
                        tempimage.SaveFile(file) # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else: # We're only saving the RAW data, so just delete the original jpg file.
                        self.Log("astrocamera.ProcessImageFiles: Deleting intermediate .jpg file...",terminal=False)
                        cmd = 'rm ' + file
                        self.osCmd(cmd,output='log')
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
        OptionListEntries = self.CameraOptions.split('-')
        for OLE in OptionListEntries:
            OLE = '-' + OLE # Add the lost '-' tag back to each entry.
        # Construct the new version of the option list ready for returning but ignore the deleted option.
        self.CameraOptions = ''
        for OLE in OptionListEntries:
            if OLE.split(' ')[0] != DelKey:
                self.CameraOptions += OLE
        self.Log("astrocamera.DelCameraOption: New list:",self.CameraOptions,terminal=False)
            
    def ContainsMeteors(self,image): # In pilomarimage
        """ Return TRUE if meteors or aircraft trails are detected in an image. """
        if len(self.LineDetection(image)) > 0: return True
        else: return False
        
    def TakePhoto(self,batch_size,terminal=True):
        """ Make an observation. This is a LIGHT image of the actual object under observation. """
        self.Log("astrocamera.TakePhoto: Begin",terminal=False)
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.SetImageType('light') # Tell the camera we are taking light photos.
        FileRoot=self.FolderHandler.PrepFile('light','light_')
        # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
        # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
        # python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --denoise off --shutter {&shutter}
        CameraCommand = self.Parameters._CameraLightCommand
        CameraCommand = CameraCommand.replace('{&shutter}',str(int(ExposureMicroseconds)))
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if self.CameraSaveDng or self.CameraSaveFits: # If we intend to produce DNG/FITS raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + self.Parameters._CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand,terminal=terminal,cleanup=False)
        if not result:
            self.Log("astrocamera.TakePhoto: CaptureSet failed.",level='error')
        self.Log("astrocamera.TakePhoto: Complete",terminal=False)
        return result

    def PromptPhotoSettings(self,batch_size,terminal=True):
        """ Take a single image, but prompt the user for the settings. """
        self.Log("astrocamera.PromptPhotoSettings: Begin",terminal=False)
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.SetImageType('light') # Tell the camera we are taking light photos.
        FileRoot=self.FolderHandler.PrepFile('light','light_')
        CameraOptions = ''
        CameraOptions += '-ex off ' # Exposure control off.
        CameraOptions += '-t 10 ' # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
        CameraOptions += '-n ' # Nopreview
        CameraOptions += '-md ' + str(self.Sensor.Mode) + ' ' # Mode 3 allows exposures over 10.2 seconds apparently.
        CameraOptions += '-w ' + str(self.Sensor.PixelWidth) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-h ' + str(self.Sensor.PixelHeight) + ' ' # Specify the pixel size of the image to match the maximum that the mode supports.
        CameraOptions += '-ss ' + str(ExposureMicroseconds) + ' ' # Use the global SHUTTER time to match the DARK and LIGHT frames.
        if self.CameraSaveDng and not '-r ' in CameraOptions: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            # *Q* Expand for FITS files too.
            CameraOptions += '-r ' # Raw is appended to JPEG file. Needs extracting later.
        CameraOptions += '-ag 16.0 ' # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        # Offer the default settings to the user, but let them enter something else.
        print ("PromptPhotoSettings: [ENTER] to accept default settings or create your own.")
        print ("raspistill " + CameraOptions)
        newopt = input(textcolor.cyan("raspistill "))
        if len(newopt) > 0: # User chose to overwrite the default settings.
            CameraOptions = newopt
            self.Log("astrocamera.PromptPhotoSettings:",CameraOptions,terminal=True)
        self.LastLightOptions = CameraOptions # keep a note of the exposure options, it's reported in the preview images.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_options=CameraOptions,terminal=terminal,cleanup=False)
        if not result:
            self.Log("astrocamera.PromptPhotoSettings: CaptureSet failed.",level='error')
        else:
            self.Log("Photo captured as:",self.Lastjpg,terminal=True)
        self.Log("astrocamera.PromptPhotoSettings: Complete",terminal=False)
        return result

    def MeteorFileScan(self):
        """ If image conversions were not done during capture, this can find and convert all the 
            image files currently in storage. This is used if CaptureSetFast was used to gather 
            images as quickly as possible. 
            This will convert all image files found the have the characteristics of a jpg with embedded raw data. """
        self.Log("astrocamera.MeteorFileScan(): Starting",terminal=True)
        # Find all image files that need converting.
        rootfolder = self.FolderHandler.GetPath('imageroot') # This is the parent data folder for all Pilomar images.
        self.Log("astrocamera.MeteorFileScan(): Searching for .jpgs in",rootfolder,terminal=True)
        allfiles = glob.glob(rootfolder + '/**/*.jpg', recursive=True) # Every jpg in every folder and subfolder.
        files = [] # Cleaned list of files to handle.
        folders = ['light'] # Which subfolders do we want?
        candidatefilename = self.FolderHandler.PrepFile('imageroot','MeteorCandidates_' + self.UtcTimeStamp() + '.txt')
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
            tempimage = pilomarimage(name='temp',logger=self.Logger)
            for i,file in enumerate(files):
                # Check for EXIT from keyboard.
                kcl = self.Keyboard.Check().lower()
                if kcl in ['x',chr(27)]: # Exit key pressed.
                    print ("")
                    print ("** Quit **")
                    break
                print(textcolor.cursorup() + textcolor.clearforward() + self.NowHMS(), "Scanning", (i + 1), "of", filecount, "(" + file.split("/")[-1] + ")", "Found", len(MeteorFiles), "candidates,")
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
        FileRoot=self.FolderHandler.PrepFile('tracking','tracking_')
        CameraCommand = self.Parameters._CameraTrackingCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(int(ExposureMicroseconds)))
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand,tempfile=True,terminal=terminal,cleanup=False)
        self.Log("astrocamera.TakeTrackingPhoto: Complete",terminal=False)
        return result

    def DarkSet(self,batch_size):
        """ Take a DARK set of images for photo stacking. """
        print (textcolor.yellow("DarkSet"))
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.SetImageType('dark') # Tell the camera we are taking dark photos.
        FileRoot = self.FolderHandler.PrepFile('dark','dark_')
        self.Log("Generating DARK image set.")
        self.Log("These match the LIGHT exposure time of",self.ExposureSeconds,"seconds.")
        self.Log("These are used to remove electrical noise from the images.")
        self.Log("Lens cap must be ON.")
        self.Log("Images will be stored in", FileRoot)
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Dark image set...')
        CameraCommand = self.Parameters._CameraDarkCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(int(ExposureMicroseconds)))
        if self.CameraSaveDng or self.CameraSaveFits: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + self.Parameters._CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result

    def ImageTypes(self):
        """ Return a text list of image types being captured. """
        result = ''
        if self.CameraSaveJpg: result += 'jpg,'
        if self.CameraSaveDng: result += 'dng,'
        if self.CameraSaveFits: result += 'fits,'
        result = result.strip(',')
        return result

    def DarkFlatSet(self,batch_size):
        """ Take a DARK-FLAT set of images for photo stacking. """
        print (textcolor.yellow("DarkFlatSet"))
        ExposureMicroseconds = int(0.001 * 1000000) # 1/1000th of a second.
        self.SetImageType('darkflat') # Tell the camera we are taking darkflat photos.
        FileRoot = self.FolderHandler.PrepFile('darkflat','darkflat_')
        self.Log("Generating DARK FLAT image set.")
        self.Log("These help remove electrical and manufacturing noise from the images.")
        self.Log("These match the FLAT exposure time of",ExposureMicroseconds / 1000000.0, "seconds.")
        self.Log("Lens cap must be ON.")
        self.Log("Images will be stored in", FileRoot)
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Dark-Flat image set...')
        CameraCommand = self.Parameters._CameraDarkFlatCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(int(ExposureMicroseconds)))
        if self.CameraSaveDng or self.CameraSaveFits: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + self.Parameters._CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result

    def FlatSet(self,batch_size):
        """ Take a FLAT set of images for photo stacking. """
        print (textcolor.yellow("FlatSet"))
        self.SetImageType('flat') # Tell the camera we are taking flat photos.
        FileRoot = self.FolderHandler.PrepFile('flat','flat_')
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
        CameraCommand = self.Parameters._CameraFlatCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if self.CameraSaveDng or self.CameraSaveFits: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + self.Parameters._CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result

    def BiasSet(self,batch_size):
        """ Take a BIAS/OFFSET set of images for photo stacking. """
        print (textcolor.yellow("BiasSet"))
        ExposureMicroseconds = int(0.001 * 1000000) # 1/1000th of a second.
        self.SetImageType('bias') # Tell the camera we are taking bias photos.
        FileRoot = self.FolderHandler.PrepFile('bias','bias_')
        self.Log("Generating OFFSET/BIAS image set.")
        self.Log("These will be the shortest possible exposure time (FASTEST)",ExposureMicroseconds / 1000000.0,"seconds")
        self.Log("The temperature and ISO settings must be the same as the LIGHT images.")
        self.Log("These are used to remove manufacturing defects from the images that the sensor captures.")
        self.Log("Lens cap must be ON.")
        input(textcolor.cyan("[RETURN] to begin: ")) # Python3 
        print ('Capturing Bias image set...')
        CameraCommand = self.Parameters._CameraBiasCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        CameraCommand = CameraCommand.replace('{&shutter}',str(int(ExposureMicroseconds)))
        if self.CameraSaveDng or self.CameraSaveFits: # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            CameraCommand += ' ' + self.Parameters._CameraRawSwitch + ' ' # Append RAW data to the image.
        result = self.CaptureSet(file_root=FileRoot,batch_size=batch_size,camera_command=CameraCommand)
        return result
        
    def AutoPhoto(self):
        print (textcolor.yellow("AutoPhoto"))
        if self.Parameters.CameraEnabled == False:
            self.Log("astrocamera.AutoPhoto(): Camera is disabled. No photo attempted.",level='warning')
            return False
        FileRoot = self.FolderHandler.PrepFile('auto','autophoto_')
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
            dt = self.CleanDatetimeString(str(self.NowUTC()))
            filename = FileRoot + dt + '.jpg'
            CameraCommand = self.Parameters._CameraAutoCommand
            CameraCommand = CameraCommand.replace('{&mode}',str(self.Sensor.Mode))
            CameraCommand = CameraCommand.replace('{&width}',str(self.Sensor.PixelWidth))
            CameraCommand = CameraCommand.replace('{&height}',str(self.Sensor.PixelHeight))
            CameraCommand = CameraCommand.replace('{&output}',filename)
            # *Q* TODO: Perform safety check for remaining & symbols.
            self.osCmd(CameraCommand)
            print ("-", filename)
        return True

