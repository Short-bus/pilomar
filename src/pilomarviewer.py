#!/usr/bin/python

# image class for use in Pilomar project.
# Builds upon opencv and textcolor features to provide a primitive 
# character based image viewer.
# These routines are primarily to help with development, they are not 
# intended to provide high quality graphical images through a character interface!

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from pilomarimage import pilomarimage # Image handlers.
from textcolor import textcolor, colordisplay, keyboardscanner # Character UI handlers.
import time
import math 
import glob
import os
from datetime import timedelta

class imageviewer():
    """ Primitive image viewer for character interfaces. 
        Converts an image file into a 256 color character approximation. """
    __version__ = '0.0.1'

    def __init__(self,name,row=None,col=None,rows=20,cols=40,cdlayout=None,fg=15,bg=0,logger=None,autorefresh=False):
        """ Create new instance. 
            name = A name for the instance.
            row/col = Optionally positions the window on the screen. If missing, the display is just printed wherever the cursor is.
            rows/cols = Size of the screen in characters.
            cdlayout = index of the colordisplay.CDLayout list. A shortcut to set col and or row values more dynamically.
            fg/bg = Default foreground/background color of the screen (0-255)
            logger = The pilomarlog instance to be used for logging.
            autorefresh = Update the image automatically if the source file changes.

            Examples:

                1) Very simple, quick view of a file.
                
                        from pilomarviewer import imageviewer
                        # Includes zoom and pan navigation.
                        v = imageviewer('test',row=1,col=1,rows=40,cols=160,fg=15,bg=0)
                        v.QuickFileView('/home/pi/pilomar/temp/temp10_shapes.jpg')

                2) View a file as a sub-window in another display.
                
                        from pilomarviewer import imageviewer
                        # Parent program responsible for passing zoom/pan navigation commands to the window.
                        v = imageviewer('test',row=1,col=1,rows=40,cols=160,fg=15,bg=0)
                        v.LoadFile('/home/pi/pilomar/temp/temp10_shapes.jpg')
                        ...
                        ...
                        while True:
                            # Accept a variable to store {command} string.
                            if v.RecognisedCommand( {command} ): # Image viewer recognises the command.
                                v.CommandHandler( {command} ) # Image viewer processes the command.
                                v.Display(immediate=True) # Refresh the display.

                3) Pixel rendering of B&W image file using Braille character set.
                
                        from pilomarviewer import imageviewer
                        v = imageviewer('test',row=1,col=1,rows=40,cols=160,fg=15,bg=0)
                        v.LoadFile('/home/pi/pilomar/src/simple.bmp')
                        v.ImageToBrailleWindow()
                        v.Window.Display()                        

                4) Inline rendering of B&W image file using Braille character set.
                
                        from pilomarviewer import imageviewer
                        v = imageviewer('test',row=1,col=1,rows=40,cols=160,fg=15,bg=0)
                        v.LoadFile('/home/pi/pilomar/src/simple.bmp')
                        v.ImageToBrailleWindow()
                        v.Window.InlineDisplay()                        

            """
        self.Name = name
        self.Filename = None # Which file are we handling?
        self.FileModTime = None
        self.AutoRefresh = autorefresh
        self.Logger = logger # Logger instance.
        self.Log = None
        self.ReportException = None # Report exception details to logfile.
        self.RaiseException = None # Report and raise exception. 
        self.SetLogger(logger)
        self.OrigImage = pilomarimage(name='original',logger=logger) # Image handler to store original image buffer.
        self.WorkImage = pilomarimage(name='work',logger=logger) # Image handler to store working image buffer.
        c,r = textcolor.terminalsize() # How big is the terminal area?
        if rows == None: rows = r - 2 # Default window size to terminal size.
        if cols == None: cols = c - 2  
        self.Window = colordisplay(rows=rows,columns=cols,cdlayout=cdlayout,name=name,row=row,col=col,fg=fg,bg=bg) # Character display.
        self.Window.ClipWindow = True # If not enough terminal space, limit the size of the image.
        self.Commands = ['[',']','0','1','2','3','4','5','6','7','8','9','<','>',',','.'] # These are the commands that the viewer is listening for.
        self.StartX = 0 # Cropped area of the image to display.
        self.StartY = 0
        self.EndX = None
        self.EndY = None
        self.DiffX = None # Size of cropped area.
        self.DiffY = None
        self.AspectRatio = 1.4 # In case the characters are not entirely square. This can adjust the aspect ratio.

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        self.Logger = logger # Logger instance.
        self.Log = None
        self.ReportException = None # Report exception details to logfile.
        self.RaiseException = None # Report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        if self.Log != None: self.Log("imageviewer(",self.Name,").SetLogger(): Linked to this log file.",terminal=False)
        return True

    def NewestFile(self,path_pattern):
        """
        Return the absolute path of the most recently modified file
        matching the given pattern or path. Returns None if no matches.
        """
        # Expand glob patterns (this also works if the input is a literal path)
        matches = glob.glob(path_pattern, recursive=True)

        if not matches:
            return None

        # Pick the file with the latest modification time
        newest = max(matches, key=os.path.getmtime)

        # Return absolute path for consistency
        return os.path.abspath(newest)

    def SetImageValues(self):
        """ Whenever a new image is loaded this initializes values that depend upon it.
            reset = False: Zoom and scroll setting are retained with new image.
                           (Only if image buffer already exists.) """
        self.StartX = 0 # Start co-ordinates of view crop. (Whole image at first)
        self.StartY = 0
        self.EndX = self.OrigImage.GetWidth() # End co-ordinates of view crop. (Whole image at first)
        self.EndY = self.OrigImage.GetHeight()
        self.DiffX = self.EndX - self.StartX # Width of view crop.
        self.DiffY = self.EndY - self.StartY # Height of view crop.
   
    def GetFileModTime(self):
        """
        Return file modified time of current file.
        """
        try:
            modtime = os.path.getmtime(self.Filename)
        except:
            modtime = None
        return modtime
   
    def LoadFile(self,filename,reset=True):
        """ Load image from disc.
            filename = opencv numpy array representing an image. 
            reset = True: The viewer resets to the 'full image' view. 
            reset = False: Previous viewer settings are retained (if they exist) """
        self.OrigImage.LoadFile(filename)
        if self.OrigImage.ImageMissing():
            print('** imageviewer(',self.Name,').LoadFile(',filename,') failed. **')
            return False
        self.Filename = filename
        self.FileModTime = self.GetFileModTime()
        if self.DiffX == None or reset: # Only update values if we need/want to.
            self.SetImageValues()
        return True
    
    def LoadBuffer(self,buffer,reset=True):
        """ Load image buffer. 
            buffer = opencv numpy array representing an image. 
            reset = True: The viewer resets to the 'full image' view. 
            reset = False: Previous viewer settings are retained (if they exist) """
        self.OrigImage.LoadBuffer(buffer)
        if self.OrigImage.ImageMissing():
            print('** imageviewer(',self.Name,').LoadBuffer() failed. **')
            return False
        self.Filename = None # No file name.
        if self.DiffX == None or reset: # Only update values if we need/want to.
            self.SetImageValues()
        return True
        
    def AddGuidelines(self):
        """ Add guidelines to the WorkImage buffer. 
            To help with development. 
            Draws a border around the image edge and a diagonal cross through the centre. """
        max_x = self.WorkImage.GetWidth()
        max_y = self.WorkImage.GetHeight()
        for x in [0,max_x]: # start x
            for y in [0,max_y]: # start y 
                for x1 in [0,max_x]: # end x 
                    for y1 in [0,max_y]: # end y
                        if x1 == x and y1 == y: continue # End points must be different.
                        if self.Log != None: self.Log("imageviewer(",self.Name,").AddGuidelines(): Adding (",x,y,") - (",x1,y1,") to WorkImage (",self.WorkImage.GetHeight(),self.WorkImage.GetWidth(),")",terminal=False)
                        self.WorkImage.DrawEdgeLine(startcoord=(x,y),endcoord=(x1,y1),color=(255,255,255),edgecolor=(0,0,255),thickness=10,edgethickness=10)

    #def ListToBrailleWindow(self,input_list,threshold=0,fg=None,bg=None):
    #    """
    #    Convert a list to textcolor.colordisplay() object.
    #    """
    #    for y,alt_list in enumerate(input_list):
    #        alt_list = input_list[y] # Input list is a list of rows. Each of those rows is a list of cells in the row.
    #        for x,value in enumerate(alt_list):
    #            if value > threshold: self.Window.BraillePlot(y,x,value=True,fg=fg,bg=bg)
    #    return True

    def ImageToBrailleWindow(self,threshold=127):
        """ Convert an image buffer into a textcolor.colordisplay() object. 
            Use the UTF-8 Braille character set to increase pixel density, makes 1 character represent 8 pixels. 
            Same idea as ImageToWindow() method, but uses 'Braille' characters to render more detailed pixelated images. 
            *Q* Currently generates simple B&W image with 50% brightness threshold. 

            Parameters ---------------------------------------------------------------
            None 

            References ---------------------------------------------------------------
            self.OrigImage : Instance of pilomarimage class.

            Updates ------------------------------------------------------------------
            self.WorkImage 
            self.Window : Instance of colordisplay class.
            
            Returns ------------------------------------------------------------------
            success (bool)
            
            Example usage ------------------------------------------------------------ 
                self.LoadFile('/home/pi/pilomar/data/pilomar_icon.jpg') # Load chosen image into imageviewer instance.
                self.ImageToBrailleWindow() # Convert the image buffer into Braille character B&W representation in the display buffer.
                self.Window.Display() # Draw the display.
            """
        # Map (x, y) within the 2x4 cell to braille dot index (1..8)
        dot_map = {
            (0, 0): 1,
            (0, 1): 2,
            (0, 2): 3,
            (0, 3): 7,
            (1, 0): 4,
            (1, 1): 5,
            (1, 2): 6,
            (1, 3): 8,
        }
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): Begin",terminal=False)
        if self.OrigImage.ImageMissing():
            print("OrigImage is missing")
            return False
        self.WorkImage.CloneImage(self.OrigImage) # Refresh work image buffer.
        if self.WorkImage.ImageMissing():
            print("WorkImage is missing")
            return False
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): WorkImage loaded (",self.WorkImage.GetHeight(),self.WorkImage.GetWidth(),")",terminal=False)

        # Prepare the source image for scanning. It must reflect the dimensions of the available display.
        if self.DiffX < self.WorkImage.GetWidth() or self.DiffY < self.WorkImage.GetHeight():
            # We're selecting a region of the whole image.
            # Clip the image buffer to match the selected area.
            self.WorkImage.ClipImage(self.StartX,self.StartY,self.EndX,self.EndY)
        s_w_PixelRows = self.Window.DisplayRows * 4 # Each character represents 4 pixel rows.
        s_w_PixelColumns = self.Window.DisplayColumns * 2 # Each character represents 2 pixel rows.
        vscale = float(s_w_PixelRows) / self.WorkImage.GetHeight() # Scale for WIDTH to fit.
        hscale = float(s_w_PixelColumns) / self.WorkImage.GetWidth() # Scale for HEIGHT to fit.
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): vscale",vscale,"aspectratio",self.AspectRatio,"hscale",hscale,"on h",self.WorkImage.GetHeight(),"x w",self.WorkImage.GetWidth(),terminal=False)
        self.WorkImage.ScaleImage(vscale=vscale,hscale=hscale / self.AspectRatio) # Scale down the image.
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): After scaling h",self.WorkImage.GetHeight(),"x w",self.WorkImage.GetWidth(),terminal=False)

        # Now start transferring pixels into characters.
        self.Window.Clear()
        if self.Log != None: 
            self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): Image dimensions: Rows",self.WorkImage.GetHeight(),",Cols",self.WorkImage.GetWidth(),terminal=False)
            self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): Window size: Rows",self.Window.DisplayRows,",Cols",self.Window.DisplayColumns,terminal=False)
        max_x = self.WorkImage.GetWidth() # Number of columns to transfer
        max_y = self.WorkImage.GetHeight() # Number of rows to transfer
        for row in range(0,max_y,4): # Each row in turn.
            for col in range(0,max_x,2): # Each column in turn.
                bits = 0 # No pixels set yet.
                for dy in range(4): # Work through the 4 rows per character
                    for dx in range(2): # Work through the 2 columns per character
                        x = col + dx # Source pixel address.
                        y = row + dy
                        if x >= max_x or y >= max_y: continue # Off the end of the image.
                        b,g,r = self.WorkImage.GetPixelColor(y,x) # Get pixel color (Returned b,g,r order).
                        value = max(b,g,r) # What's the brightest channel of the pixel?
                        if value >= threshold: # Light pixel.
                            dot_index = dot_map[(dx, dy)]
                            bits |= 1 << (dot_index - 1)
                braille_char = chr(0x2800 + bits)
                self.Window.PlaceString(row=int(row//4),col=int(col//2),text=braille_char) # Use default colors at present.
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToBrailleWindow(): End",terminal=False)
        return True
        
    def ImageToWindow(self):
        """ Convert an image file into a textcolor.colordisplay() object 
            Allows very rudimentary image viewing via a character interface. 
            This doesn't directly display the image, it merely creates a character 
            representation in 256 colors that can be displayed via the .Display() and .InlineDisplay() methods. 

            Parameters ---------------------------------------------------------------
            None 

            References ---------------------------------------------------------------
            self.OrigImage : Instance of pilomarimage class.

            Updates ------------------------------------------------------------------
            self.WorkImage 
            self.Window : Instance of colordisplay class.
            
            Returns ------------------------------------------------------------------
            success (bool)
            
            Scales and clips into self.WorkImage 
            Transfers resulting self.WorkImage into the display buffer. """
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): Begin",terminal=False)
        LightShade = '\u2591' # Checker pattern characters to help with color dithering.
        MediumShade = '\u2592'
        DarkShade = '\u2593'
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): cloning OrigImage",terminal=False)
        self.WorkImage.CloneImage(self.OrigImage) # Refresh work image buffer.
        if self.WorkImage.ImageMissing():
            return False
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): WorkImage loaded (",self.WorkImage.GetHeight(),self.WorkImage.GetWidth(),")",terminal=False)
        #self.AddGuidelines() # During development, add guidelines to the image to help with registration. *Q* Remove for release.
        # Apply image filters here if needed.
        if self.DiffX < self.WorkImage.GetWidth() or self.DiffY < self.WorkImage.GetHeight():
            # We're selecting a region of the whole image.
            # Clip the image buffer to match the selected area.
            self.WorkImage.ClipImage(self.StartX,self.StartY,self.EndX,self.EndY)
        vscale = float(self.Window.DisplayRows) / self.WorkImage.GetHeight() # Scale for WIDTH to fit.
        hscale = float(self.Window.DisplayColumns) / self.WorkImage.GetWidth() # Scale for HEIGHT to fit.
        tscale = min(vscale,hscale) # Make sure smallest axis scale wins, otherwise the image is further clipped.
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): vscale",vscale,"aspectratio",self.AspectRatio,"hscale",hscale,"=tscale",tscale,"on h",self.WorkImage.GetHeight(),"x w",self.WorkImage.GetWidth(),terminal=False)
        #self.WorkImage.ScaleImage(vscale=vscale * self.AspectRatio,hscale=hscale) # Scale down the image.
        self.WorkImage.ScaleImage(vscale=vscale,hscale=hscale / self.AspectRatio) # Scale down the image.
        #self.WorkImage.ScaleImage(vscale=tscale * self.AspectRatio,hscale=tscale) # Scale down the image.
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): After scaling h",self.WorkImage.GetHeight(),"x w",self.WorkImage.GetWidth(),terminal=False)
        # Now start transferring pixels into characters.
        self.Window.Clear()
        if self.Log != None: 
            self.Log("imageviewer(",self.Name,").ImageToWindow(): Image dimensions: Rows",self.WorkImage.GetHeight(),",Cols",self.WorkImage.GetWidth(),terminal=False)
            self.Log("imageviewer(",self.Name,").ImageToWindow(): Window size: Rows",self.Window.DisplayRows,",Cols",self.Window.DisplayColumns,terminal=False)
        for row in range(self.WorkImage.GetHeight()): # Each row in turn.
            if row >= self.Window.DisplayRows: 
                if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): row",row,">= DisplayRows",self.Window.DisplayRows,", end row.",terminal=False)
                break # Off the end of the display!
            for col in range(self.WorkImage.GetWidth()): # Each column in turn.
                if col >= self.Window.DisplayColumns: 
                    if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): col",col,">= DisplayColumns",self.Window.DisplayRows,", end column.",terminal=False)
                    break # Off the end of the display!
                b,g,r = self.WorkImage.GetPixelColor(row,col) # Get pixel color (Returned b,g,r order).
                r = float(r) / 255 # Scale needs to be 0.0 - 1.0 instead of original 0 - 255
                g = float(g) / 255
                b = float(b) / 255
                color1,color2 = textcolor.rgbditherdecimal(r,g,b) # Convert to 2 color codes for dithering.
                self.Window.PlaceString(row=row,col=col,text=LightShade,fg=color2,bg=color1)
        if self.Log != None: self.Log("imageviewer(",self.Name,").ImageToWindow(): End",terminal=False)
        return True

    def Display(self,immediate=False):
        """ Refresh the display. """
        if self.Log != None: self.Log("imageviewer(",self.Name,").Display(): Begin",terminal=False)
        self.ImageToWindow() # Transfer the currently selected image area into the window display.
        # Add descriptive labels.
        name = self.Filename # filename if available, else window name.
        if name == None: name = self.Name
        if self.WorkImage.ImageMissing(): # No image available.
            name = "NO IMAGE LOADED (" + str(name) + ")"
            self.Window.PlaceString(row=0,col=0,text=name,fg=0,bg=textcolor.RED) # Show name.
        else: # Image available.
            self.Window.PlaceString(row=0,col=0,text=name,fg=0,bg=textcolor.YELLOW) # Show name.
            self.Window.PlaceString(row=1,col=0,text='View (' + str(self.StartX) + "," + str(self.StartY) + ");(" + 
                                                     str(self.EndX) + "," + str(self.EndY) + "), aspect " + str(round(self.AspectRatio,1)) + ", Interpolation " + str(self.WorkImage.ResizeMethod),
                                    fg=0,bg=textcolor.YELLOW) # Show filename.
            self.Window.PlaceString(row=-1,col=0,text=" 'x'quit '['zoom out ']'zoom in 'numpad'navigate '<>'aspect  '.'interpolation ",
                                    fg=textcolor.BLACK,bg=textcolor.CYAN) # instructions at bottom of image.
        c,r = textcolor.terminalsize() # How big is the terminal area?
        self.Window.Display(screenheight=r,screenwidth=c,immediate=False) # Display window.
        print(textcolor.cursorhome())
        if self.Log != None: self.Log("imageviewer(",self.Name,").Display(): End",terminal=False)
        return True
        
    def InlineDisplay(self,border=False):
        """ Refresh the display. 
            Copy OrigImage, scale and crop into WorkImage.             """
        if self.Log != None: self.Log("imageviewer(",self.Name,").InlineDisplay(): Begin",terminal=False)
        self.ImageToWindow() # Zooms and clips OrigImage into WorkImage, then transfers into character display buffer.
        # Add descriptive labels.
        name = self.Filename # filename if available, else window name.
        if name == None: name = self.Name
        if self.WorkImage.ImageMissing(): # No image available.
            name = "NO IMAGE LOADED (" + str(name) + ")"
            self.Window.PlaceString(row=0,col=0,text=name,fg=0,bg=textcolor.RED) # Show name.
        self.Window.InlineDisplay() # Display window.
        if self.Log != None: self.Log("imageviewer(",self.Name,").InlineDisplay(): End",terminal=False)
        return True

    def QuickBufferView(self,imagebuffer,inline=False):
        """ Call this to display any OpenCV image buffer via the terminal interface.
            This allows zoom and pan. 
            This is the quick-view format, it just clears the screen and doesn't care what else is out there. 
            
            imagebuffer : OpenCV image buffer.
            inline : When TRUE image is shown inline and no keyboard input required.
                     When FALSE image is shown in display location and 'x' must be pressed to resume. """
        self.LoadBuffer(imagebuffer)
        if inline: # Display inline with no user input required.
            self.InlineDisplay()
        else: # Display in screen location and wait for user to dismiss the display.
            self.Display(immediate=True) # Display window - initial display.
            Keyboard = keyboardscanner() # Non-Blocking reader of the keyboard (via curses library). 
            while True: # Loop until told to quit.
                keypress = Keyboard.Check().lower() # Non blocking scan for keyboard input.
                if keypress == '': # Wait a moment then scan again.
                    time.sleep(0.5)
                    continue
                if keypress == 'x': # Quit
                    break # Quit
                if self.RecognisedCommand(keypress):
                    self.CommandHandler(keypress) # Process command and redisplay.
                    self.Display(immediate=True) # Display window.
        return
        
    def QuickFileView(self,filepath,inline=False,autorefresh=None):
        """ Call this to select and view .jpg files via the terminal interface.
            This allows zoom and pan. 
            This is the quick-view format, it just clears the screen and doesn't care what else is out there. 
            
            filename : Name of image file to display.
            inline : When TRUE image is shown inline and no keyboard input required.
                     When FALSE image is shown in display location and 'x' must be pressed to resume.
            autorefresh : Override the self.AutoRefresh option. """
        if autorefresh != None: AutoRefresh = autorefresh
        else: autorefresh = self.AutoRefresh
        filename = self.NewestFile(filepath)
        if filename == None: 
            print("Waiting for a file matching:",filepath)
            while filename == None:
                filename = self.NewestFile(filepath)
                time.sleep(2)
        self.LoadFile(filename)
        screen_cols, screen_rows = textcolor.terminalsize()
        prev_cols = screen_cols
        prev_rows = screen_rows
        screen_size_poll = 10
        if inline: # Display inline with no user input required.
            self.InlineDisplay()
        else: # Display in screen location and wait for user to dismiss the display.
            self.Display(immediate=True) # Display window - initial display.
            Keyboard = keyboardscanner() # Non-Blocking reader of the keyboard (via curses library). 
            while True: # Loop until told to quit.
                if screen_size_poll < 0: # Time to check window size again.
                    screen_size_poll = 10
                    screen_cols, screen_rows = textcolor.terminalsize()
                    if prev_cols != screen_cols or prev_rows != screen_rows: # window size changed.
                        prev_cols = screen_cols
                        prev_rows = screen_rows 
                        self.Display(immediate=True)
                else: screen_size_poll -= 1
                keypress = Keyboard.Check().lower() # Non blocking scan for keyboard input.
                if keypress == 'x': # Quit
                    break # Quit
                if self.RecognisedCommand(keypress):
                    self.CommandHandler(keypress) # Process command and redisplay.
                    self.Display(immediate=True) # Display window.
                latestfile = self.NewestFile(filepath)
                if latestfile != filename: # New file has appeared, switch to that.
                    filename = latestfile
                    self.LoadFile(filename)
                    self.Display(immediate=True)
                    continue
                filemodtime = self.GetFileModTime() # Has the file changed?
                if autorefresh and filemodtime > self.FileModTime and timedelta(filemodtime - self.FileModTime).total_seconds() > 5:
                    # File has changed on disc, we should automatically refresh the display.
                    self.LoadFile(filename)
                    self.Display(immediate=True)
                if keypress == '': # Wait a moment then scan again.
                    time.sleep(0.5)
                    continue
        return

    def RecognisedCommand(self,cmd):
        """ Return TRUE if a command is recognised by this module. """
        result = False
        if cmd in self.Commands: result = True
        return result

    def PreCommand(self):
        """ Before executing a command, check that we know the current crop size. """
        self.DiffX = self.EndX - self.StartX
        self.DiffY = self.EndY - self.StartY

    def GetViewCenter(self):
        """ Return the X,Y co-ordinates of the center of the selected area. """
        x = self.StartX + int(self.DiffX / 2)
        y = self.StartY + int(self.DiffY / 2)
        return x,y

    def GetStartFromCenter(self,x,y):
        """ Given the co-ordinates of the center of the view area
            return the start co-ordinates. """
        newx = x - int(self.DiffX / 2)
        newy = y - int(self.DiffY / 2)
        return newx, newy

    def PostCommand(self):
        """ After executing a command, check that everything matches up still. """
        # Check we remain within the bounds of the original image.    
        w = self.OrigImage.GetWidth()
        h = self.OrigImage.GetHeight()
        if self.DiffX > w: self.DiffX = w
        if self.DiffY > h: self.DiffY = h
        if (self.StartX + self.DiffX) > w: self.StartX = w - self.DiffX
        if (self.StartY + self.DiffY) > h: self.StartX = h - self.DiffY
        self.StartX = max(self.StartX,0)
        self.StartY = max(self.StartY,0)
        self.EndX = min(self.StartX + self.DiffX,w)
        self.EndY = min(self.StartY + self.DiffY,w)
        self.DiffX = self.EndX - self.StartX
        self.DiffY = self.EndY - self.StartY

    def ZoomIn(self):   
        """ Increase the zoom level. """
        x,y = self.GetViewCenter() # Where's the current center of the view?
        # Resize the selection area.
        self.DiffX = max(int(self.DiffX * 0.5),10)
        self.DiffY = max(int(self.DiffY * 0.5),10)
        sx,sy = self.GetStartFromCenter(x,y) # Where's the new start location if we keep the view center?
        self.StartX = sx
        self.StartY = sy
        
    def ZoomOut(self):      
        """ Reduce the zoom level. """
        x,y = self.GetViewCenter() # Where's the current center of the view?
        # Resize the selection area.
        self.DiffX = int(self.DiffX * 1.5)
        self.DiffY = int(self.DiffY * 1.5)
        sx,sy = self.GetStartFromCenter(x,y) # Where's the new start location if we keep the view center?
        self.StartX = sx
        self.StartY = sy

    def Pan0(self):
        """ Move UP. """
        self.StartY = max(self.StartY - int(self.DiffY * 0.25),0)
        
    def Pan315(self):
        """ Move UP and LEFT. """
        self.Pan0()
        self.Pan270()

    def Pan270(self):
        """ Move LEFT. """
        self.StartX = max(self.StartX - int(self.DiffX * 0.25),0)

    def Pan225(self):
        """ Move LEFT and DOWN. """
        self.Pan270()
        self.Pan180()

    def Pan180(self):
        """ Move DOWN. """
        self.StartY = min(self.StartY + int(self.DiffY * 0.25),self.OrigImage.GetHeight() - self.DiffY)

    def Pan135(self):
        """ Move RIGHT and DOWN. """ 
        self.Pan90()
        self.Pan180()

    def Pan90(self):
        """ Move RIGHT. """
        self.StartX = min(self.StartX + int(self.DiffX * 0.25),self.OrigImage.GetWidth() - self.DiffX)

    def Pan45(self):
        """ Move UP and RIGHT. """
        self.Pan0()
        self.Pan90()

    def PanCentre(self):
        """ Move to CENTRE of image. """
        self.StartX = int(self.OrigImage.GetWidth() / 2) - int(self.DiffX / 2)
        self.StartY = int(self.OrigImage.GetHeight() / 2) - int(self.DiffY / 2)
        
    def IncRatio(self):
        """ Increase the character aspect ratio. 
            Make squares more square, circles more circular! """
        self.AspectRatio = self.AspectRatio + 0.1
        self.AspectRatio = min(self.AspectRatio,3.0)

    def DecRatio(self):
        """ Decrease the character aspect ratio. 
            Make squares more square, circles more circular! """
        self.AspectRatio = self.AspectRatio - 0.1
        self.AspectRatio = max(self.AspectRatio,0.1)
        
    def CommandHandler(self,cmd):
        """ Given a command, modify the settings. """
        self.PreCommand() # Check attributes are OK for executing a command.
        if cmd == ']': self.ZoomIn() # Zoom in. (Select smaller block of pixels)
        elif cmd == '[': self.ZoomOut() # Zoom out. (select larger block of pixels)
        elif cmd == '8': self.Pan0() # Pan up.
        elif cmd == '9': self.Pan45() # Pan up and right.
        elif cmd == '6': self.Pan90() # Pan right
        elif cmd == '3': self.Pan135() # Pan down and right.
        elif cmd == '2': self.Pan180() # Pan down
        elif cmd == '1': self.Pan225() # Pan down and left.
        elif cmd == '4': self.Pan270() # Pan left.
        elif cmd == '7': self.Pan315() # Pan up and left.
        elif cmd == '5': self.PanCentre() # Centre.
        elif cmd == '0': self.SetImageValues() # Reset zoom and pan.
        elif cmd == '<': self.DecRatio() # Decrease the character aspect ratio.
        elif cmd == '>': self.IncRatio() # Increase the character aspect ratio.
        elif cmd == '.': self.WorkImage.NextInterpolation() # Move on to next sampling method for resizing (zooming)
        elif cmd == ',': self.WorkImage.PrevInterpolation() # Move on to next sampling method for resizing (zooming)
        self.PostCommand() # Check everything is balanced once the command it complete.
        return True

if __name__ == '__main__': # Demonstrate on a given file.
    import sys
    RunArgs = sys.argv[1:] # Ignore 1st argument which is this program name.
    if len(RunArgs) < 1:
        raise Exception("Give filepath as command line parameter.")
    else: 
        filename = RunArgs[0]
        for c in ['"',"'"]: # Strip leading/trailing quotes.
            if filename[0] == c == filename[-1]: filename = filename[1:-1]
    if len(RunArgs) > 1: # Rows available.
        rows = int(RunArgs[1])
    else:
        rows = 40
    if len(RunArgs) > 2: # Columns available.
        cols = int(RunArgs[2])
    else:
        cols = 160
    Viewer = imageviewer(name="demo",row=1,col=1,rows=rows,cols=cols,fg=15,bg=0,autorefresh=True)
    print(textcolor.clearall())
    Viewer.QuickFileView(filename)
    print(textcolor.clearforward())
