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
from textcolor import textcolor # Text interface color utility.
import os

class discmonitor(): # 2 references.
    """ Class to monitor the storage capacity of the RPi.
        Basic operation monitors the 'root' disc of the system (memory card).
        But can also monitor other mounted disks, such as usb memory sticks.
        - Will attempt to mount them using the default Raspbian desktop auto-mounting behaviour if needed. """

    def __init__(self,name='root',devname='/dev/root',path='/',disctype='boot',logger=None):
        self.Log = logger # Which logger to use?
        self.oscommand = oscommand(logger=logger) 
        self.osCmd = self.oscommand.Execute
        self.osCmdCode = self.oscommand.ExecuteCode
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
        if self.Log != None: self.Log("discmonitor: Available storage on:",self.Name, self.DevName, self.Path, self.DiscFree,'bytes',terminal=False)
        
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
        lines = self.osCmd(cCmd) # Execute command and gather result.
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

    def SplitSpaces(self,origline,sep=' '):
        """ If text has been split into space separated list, but it contains quoted space values
            the list gets split incorrectly. 
            This routine recombines these embedded spaces. """
        returnlist = []
        newentry = ''
        insidequotes = False
        for i in range(len(origline)):
            character = origline[i] # Check each character in turn.
            if character == '"': insidequotes = not insidequotes # Quote mark, so start/stop quoted string.
            newentry += character # Add this character to the current list entry.
            if character == sep and insidequotes == False: # Separator only acts as separator if we are outside a quoted string.
                newentry = newentry.strip(sep) # Clean up the entry.
                if newentry != '': # If something left then append it to the output list.
                    returnlist.append(newentry)
                    newentry = '' # Prepare to construct the next entry.
        if newentry != '': returnlist.append(newentry) # Append any remaining entry.
        return returnlist
        
    def FindUSB(self,devname='/dev/sda1'):
        """ Return True if a USB memory stick exists. """
        # /dev/usb1 might mount automatically if desktop is running, but it doesn't happen when running headlessly.
        # This method tries to mount the USB storage if found while running headlessly.
        result = False # Assume there's no USB memory available at first.
        if self.Log != None: self.Log("discmonitor.FindUSB: Checking if",devname,"is recognised",terminal=False)
        validdevnames = ['/dev/sda1']
        if devname in validdevnames: # Safety check. Don't run commands with values we don't trust.
            cCmd = 'sudo blkid ' + devname
            lines = self.osCmd(cCmd) # Run the command and gather the results.
            # Example output:    /dev/sda1: LABEL="USBMEMORY" UUID="B267-53C5" TYPE="vfat" PARTUUID="c3072e18-01"
            #                    /dev/sda1: LABEL="SAMSUNG USB" UUID="64A5-F009" TYPE="exfat" 
            # This will fail if the label has spaces in it! Rename the USB stick so that it doesn't!
            for line in lines: # Run through each result line in turn.
                if len(line) == 0: continue # Ignore blanks.
                #items = line.strip().split(" ") # Clean and separate out the line elements.
                items = self.SplitSpaces(line) # Clean and separate out the line elements, respecting embedded spaces in quotes.
                if items[0][:-1] == devname: # Found the USB memory stick. Extract details. (Ignore trailing ':' character)
                    self.USBLabel = items[1].split("=")[1].replace('"','') # Volume label - Will be the folder name under /media/pi/{USBLabel}
                    self.USBUUID = items[2].split("=")[1].replace('"','') # Unique ID of the memory stick.
                    self.USBFSType = items[3].split("=")[1].replace('"','') # File system type - vfat / vfat32 etc.
                    self.USBPartUUID = items[4].split("=")[1].replace('"','') # Universal identifier.
                    if self.Log != None: self.Log("discmonitor.FindUSB: Device:",devname,"Label:",self.USBLabel,"UUID:",self.USBUUID,"FS Type:",self.USBFSType,"PARTUUID:",self.USBPartUUID,terminal=False)
                    result = True # We're happy so far.
        else: # The device value was not valid. Tell the user.
            textline = "discmonitor.FindUSB: '" + devname + "' is invalid. Must be in " + str(validdevnames)
            if self.Log != None: self.Log(textline,level='error',terminal=True)
            textcolor.TextBox(textline,fg=textcolor.RED,bg=textcolor.BLACK)
        if result: # Previous steps succeeded.
            if self.Log != None: self.Log("discmonitor.FindUSB:",devname,"is recognised as",self.USBLabel,".",terminal=False)
        else: # Previous steps failed.
            textline = "discmonitor.FindUSB: " + devname + " is NOT recognised."
            if self.Log != None: self.Log(textline,level='error',terminal=True)
            textcolor.TextBox(textline,fg=textcolor.RED,bg=textcolor.BLACK)
        if ' ' in self.USBLabel: # There's a space in the label name. Refuse to mount it.
            textline = "discmonitor.FindUSB: Media label '" + self.USBLabel + "' contains spaces, will not mount. Please rename the media."
            if self.Log != None: self.Log(textline,level='error',terminal=True)
            textcolor.TextBox(textline,fg=textcolor.RED,bg=textcolor.BLACK)
            result = False 
        
        if result: # OK so far.
            self.DfPath = self.Path + "/" + self.USBLabel # The path to the mapped drive as it will appear in 'df' command output and in directory structures later on.
            if self.Log != None: self.Log("discmonitor.FindUSB: Checking if",devname,"is mounted as",self.DfPath,terminal=False)
            if os.path.exists(self.DfPath): # The directory exists.
                if self.Log != None: self.Log("discmonitor.FindUSB:",self.DfPath,"exists.",terminal=False)
            else: # The directory does not exist. The drive is recognised by the system, but not mounted. Try to mount it now.
                if self.Log != None: self.Log("discmonitor.FindUSB:",self.DfPath,"does not exist. Will attempt to mount.",terminal=True)
                # Warn the user that the 'pi' user password will be required. The udisksctl utility requires it in order to mount the disc.
                lines = ['Mounting ' + self.USBLabel + ' under ' + self.Path]
                textcolor.TextBox(lines,fg=textcolor.GREEN,bg=textcolor.BLACK)
                lines = ['You will be prompted for the "pi" user password as part of the mount process.',
                         'If you do not give the correct password the USB storage will not be mounted.']
                textcolor.TextBox(lines,fg=textcolor.CYAN,bg=textcolor.BLACK)
                cCmd = 'udisksctl mount -b ' + devname # Construct the mount command.
                print(textcolor.yellow('Executing: ' + cCmd)) # Show the user exactly what's being executed.
                temp = self.osCmdCode(cCmd) # Check return code.
                if temp == 0: # Return code '0' means success.
                    print('Thank you.')
                    if self.Log != None: self.Log("discmonitor.FindUSB: Mount",devname,"as",self.DfPath,'success.',terminal=False)
                else: # Any other return code value means a problem.
                    result = False # Failed.
                    if self.Log != None: self.Log("discmonitor.FindUSB: Mount",devname,"as",self.DfPath,'failed.',level='error',terminal=True)
        if result: # OK so far.
            dictionary = self.GetDfDictionary() # Get the 'df' results from the operating system.
            if self.DfPath in dictionary: # We found it now in the list of mount points.
                if self.Log != None: self.Log("discmonitor.FindUSB: Check",devname,"as",self.DfPath,'found.',terminal=False)
            else: # We still can't find it. Something failed.
                if self.Log != None: self.Log("discmonitor.FindUSB: Check",devname,"as",self.DfPath,'not found.',level='error',terminal=True)
                result = False # Failed.
        self.DriveAvailable = result
        if self.Log != None: self.Log("discmonitor.FindUSB: DriveAvailable",self.DriveAvailable,terminal=False)
        return result

