#!/usr/bin/python

# Pilomar's utility dialog class.
# Location for common dialog handlers. Eg file selection.
# - More can be added in the future for other common user inputs.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
from textcolor import textcolor 

class filedialog():
    """ Very simple character based file selector. 
    
        Example to select a file with no defaults. Will default to root.
        
            FD = filedialog()
            print( FD.SelectFile() )    

        Example to select a file with a default directory as a starting point.

            FD = filedialog('/home/pi/pilomar')
            print( FD.SelectFile() ) # Select file starting with default directory.
            print( FD.SelectFile() ) # Select another file, resuming with last chosen directory.
            print( FD.SelectFile('/media/pi/USBMEMORY') ) # Select another file overriding last chosen directory.

        Example to select JPEG files from a folder.
        
            FD = filedialog('/home/pi/pilomar')
            print( FD.SelectFile(typelist=['.jpg','jpeg']) )
        
    """
    def __init__(self,defaultchoice=None):
        self.TypeList = [] # List of file types to allow.
        self.LastChoice = defaultchoice # Last file selected. Used to resume/continue requests for multiple choices.
        self.Title = None # Text explaining what to select.
        pass
        
    def CurrentFileList(self,path):
        """ Return list of filenames for current path. 
            List is in form [['name','type'],['name','type'],...] 
              name = filename
              type = 'file' or 'folder' """
        returnlist = [['..','folder']] # Start list with 'up a level' entry.
        for file in os.listdir(path): # List files in folder.
            selectfile = True
            filename = path + "/" + file
            if os.path.isfile(filename):
                filetype = 'file'
            else:
                filetype = 'folder'
            if filetype == 'file' and len(self.TypeList) > 0: # Must select certain file types only.
                selectfile = False # We won't select the file unless we find a match.
                for tl in self.TypeList:
                    if file.lower().endswith(tl.lower()): 
                        selectfile = True
                        break
            if not selectfile: continue # We shouldn't select this file.
            returnlist.append([filename,filetype])
        return returnlist
        
    def DisplayFileList(self,path):
        if self.Title != None:
            textcolor.TextBox(self.Title,fg=textcolor.YELLOW,bg=textcolor.BLACK)
        print(textcolor.yellow("In:",path))
        displaylist = self.CurrentFileList(path)
        for i,fileentry in enumerate(displaylist):
            filename = fileentry[0]
            filetype = fileentry[1]
            if filetype == 'folder':
                filedisplay = textcolor.cyan(filename.split('/')[-1])
            else:
                filedisplay = filename.split('/')[-1]
            print(textcolor.yellow(str(i).rjust(3)),filedisplay)
        print(textcolor.yellow('  x'),textcolor.cyan('cancel'))
            
    def ChooseFile(self,path):
        if len(path) < 1: path = '/' # Cannot go higher than root!
        result = None
        cancelflag = False
        filelist = self.CurrentFileList(path) # List of [filename,filetype] entries for each file and directory in the current path.
        while result == None:
            self.DisplayFileList(path)
            inpval = input(textcolor.cyan("Enter file number to select: "))
            inpval = inpval.lower()
            if inpval == 'x': # User chose to quit.
                cancelflag = True
                result = None
            elif inpval == '..': # User wants to go 'up'.
                inpval = '0'
            try:
                temp = int(inpval)
            except:
                temp = None
            if isinstance(temp,int):
                if temp >= len(filelist) or temp < 0:
                    temp = None
                else:
                    result = filelist[temp] # Pull selected [filename,filetype] entry from list of all files and directories.
                    if result[0] == '..': # Go up a level. Use filename from [filename,filetype]
                        if path.rfind('/') >= 0: 
                            path = path[:path.rfind('/')] # Drop lowest folder name from path.
                        result,cancelflag = self.ChooseFile(path) # Cut last entry from path and search there instead.
                    if result[1] == 'folder': # Dig deeper. Check filetype from [filename,filetype]
                        path = result[0] # Use filename from [filename,filetype]
                        result,cancelflag = self.ChooseFile(path)
            if cancelflag: # User chose to cancel.
                break
        return result,cancelflag # Returns [filename,filetype] entry. And 'cancelflag' if user chose to cancel.

    def SelectFile(self,path=None,typelist=[],title=None):
        """ Return selected file or return None.
            path is initial directory to list. User can navigate away.
            typelist is optional list of filetypes to list.
            title is optional text that explains what to select. """
        self.TypeList = typelist
        self.Title = title
        if path == None: 
            path = self.LastChoice # If no path specified, use the last one selected.
            if os.path.isfile(path): # Strip out any filename, so just the directory path remains.
                path = path[:path.rfind('/')] # Drop filename from path.
        if path == None: path = '/' # Default to the root.
        result,cancelflag = self.ChooseFile(path) # Get [filename,filetype] or None 
        if result != None:
            result = result[0] # Take filename from [filename,filetype]
        self.LastChoice = result
        return result

# --------------------------------------------------------------------------------------------------------------------------

class folderdialog():
    """ Very simple character based folder selector. 
    
        Example to select a folder with no defaults. Will default to root.
        
            FD = folderdialog()
            print( FD.SelectFolder() )    

        Example to select a folder with a default directory.

            FD = folderdialog('/home/pi/pilomar')
            print( FD.SelectFolder() ) # Select folder starting with default directory.
            print( FD.SelectFolder() ) # Select another folder, resuming with last chosen directory.
            print( FD.SelectFolder('/media/pi/USBMEMORY') ) # Select another folder overriding last chosen directory.
            
        
    """
    def __init__(self,defaultchoice=None):
        self.LastChoice = defaultchoice # Populates with last chosen directory. Used to resume/continue requests for multiple choices.
        self.Title = None # Text explaining what to select.
        pass
        
    def CurrentFolderList(self,path):
        """ Return list of folder for current path. 
            List is in form [['name','type'],['name','type']s,...] 
              name = foldername
              type = 'file' or 'folder' """
        returnlist = [['..','folder']] # Start list with 'up a level' entry.
        for file in os.listdir(path): # List files in folder.
            SelectFolder = True
            filename = path + "/" + file
            if os.path.isfile(filename):
                filetype = 'file'
            else:
                filetype = 'folder'
            if filetype == 'folder': # Must select certain file types only.
                returnlist.append([filename,filetype])
        return returnlist
        
    def DisplayFolderList(self,path):
        if self.Title != None:
            textcolor.TextBox(self.Title,fg=textcolor.YELLOW,bg=textcolor.BLACK)
        print(textcolor.yellow("In:",path))
        displaylist = self.CurrentFolderList(path)
        for i,fileentry in enumerate(displaylist):
            filename = fileentry[0]
            filetype = fileentry[1]
            if filetype == 'folder':
                filedisplay = textcolor.cyan(filename.split('/')[-1])
            else:
                filedisplay = filename.split('/')[-1]
            print(textcolor.yellow(str(i).rjust(3)),filedisplay)
        print('')
        print(textcolor.yellow('  y'),textcolor.cyan('select current folder'))
        print(textcolor.yellow('  x'),textcolor.cyan('cancel'))
            
    def ChooseFolder(self,path):
        if len(path) < 1: path = '/' # Cannot go higher than root!
        result = None
        cancelflag = False
        filelist = self.CurrentFolderList(path) # List of [filename,filetype] entries for each file and directory in the current path.
        while result == None:
            self.DisplayFolderList(path)
            inpval = input(textcolor.cyan("Enter folder number to select: "))
            inpval = inpval.lower()
            if inpval == 'x': # User chose to quit.
                cancelflag = True
                result = None
            elif inpval == 'y': # User chose this folder.
                result = [path,'folder']
            elif inpval == '..': # User wants to go 'up'.
                inpval = '0'
            try:
                temp = int(inpval)
            except:
                temp = None
            if isinstance(temp,int):
                if temp >= len(filelist) or temp < 0:
                    temp = None
                else:
                    result = filelist[temp] # Pull selected [filename,filetype] entry from list of all files and directories.
                    if result[0] == '..': # Go up a level. Use filename from [filename,filetype]
                        if path.rfind('/') >= 0: 
                            path = path[:path.rfind('/')] # Drop lowest folder name from path.
                        result,cancelflag = self.ChooseFolder(path) # Cut last entry from path and search there instead.
                    if result[1] == 'folder': # Dig deeper. Check filetype from [filename,filetype]
                        path = result[0] # Use filename from [filename,filetype]
                        result,cancelflag = self.ChooseFolder(path)
            if cancelflag: # User chose to cancel.
                break
        return result,cancelflag # Returns [filename,filetype] entry. And 'cancelflag' if user chose to cancel.

    def SelectFolder(self,path=None,title=None):
        """ Return selected folder or return None.
            path is initial directory to list. User can navigate away.
            typelist is optional list of filetypes to list.
            title is optional text that explains what to select. """
        self.Title = title
        if path == None: path = self.LastChoice # If no path specified, use the last one selected.
        if path == None: path = '/' # Default to the root.
        result,cancelflag = self.ChooseFolder(path) # Get [filename,filetype] or None 
        if result != None:
            result = result[0] # Take filename from [filename,filetype]
        self.LastChoice = result
        return result

