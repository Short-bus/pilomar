#!/usr/bin/python

# Pilomar's logging class.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# 09.Dec.2023 Added PackageSearchResult() function to help with analysing functionality.

from datetime import datetime, timedelta, timezone
from textcolor import textcolor
import os # OS Command execution
import traceback # Used to record the stacktrace if recording an error.

class logfile(): # 2 references.
    """ An object to maintain a log file recording the activities and events in the program.
        This writes to a disc file and flushes the write buffers as quickly as it can.
        It can also copy ERROR messages to any nominated error window object (which must support a 'Print()' method. )        """

    __version__ = '0.1.0'

    def __init__(self,filename : str, clockoffset=None):
        self.FileName = filename
        self.ClockOffset = clockoffset # Can establish a clock offset when replicating/simulating specific situations.
        self.PrevLogTime = self.NowUTC()
        self.ErrorWindow = None # Reference to window object for displaying errors. Must offer a 'Print()' method.
        self.ErrorList = [] # Maintain list of any errors raised. These can then be summarised and reported if needed.
        # The following filters specify which types of messages are logged.
        # - If you change these lists, some messages may be ignored from file and displays.
        self.DetailFilter = ['u','f','d'] # Specify the detail levels that are recorded (user choices, flow, detail).
        self.LevelFilter = ['i','w','e'] # Specify which message types are recorded (info, warning, error).

    #def NowUTC(self) -> datetime: # Many references.
    #    """ Get system clock as UTC (timezone aware) 
    #        Microcontroller and Skyfield are operated in UTC vales. 
    #        All clock-times used in this program use the UTC timestamped clock.
    #        This should be the only reference to datetime.now() method in the entire
    #        module. All other uses should refer to this NowUTC() function.
    #        """
    #    return datetime.now(timezone.utc)

    def NowUTC(self,real=False) -> datetime: # Many references.
        """ Get system clock as UTC (timezone aware) 
            Microcontroller and Skyfield are operated in UTC vales. 
            All clock-times used in this program use the UTC timestamped clock.
            This should be the only reference to datetime.now() method in the entire
            program. All other uses should refer to this NowUTC() function.
            real=True means that no time offset is applied, you get the true realtime clock value.
            real=False means that any time offset is applied, making the clock run at some other point in time.
            """
        dt = datetime.now(timezone.utc) # Offset supported.
        if real == False and self.ClockOffset != None: # Can apply time offset.
            dt = dt + timedelta(seconds=self.ClockOffset)
        return dt

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
        dtNow = self.NowUTC()
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
            if self.ErrorWindow != None: self.ErrorWindow.Print(printline,fg=textcolor.RED,bg=textcolor.BLACK) # Error color.
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
        self.PrevLogTime = self.NowUTC() # Note the last time a message was logged. This is used to report the elapsed time between messages in the log file. 
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

    def UniqueFilename(self,filename):
        """ Given a filename, create a unique version of it. 
            This appends '.1', '.2', '.3' etc to the filename until it finds
            an unused name. """
        fileelements = filename.split('.')
        uniquefilename = filename + ".err" # Something's gone wrong if this makes it through!
        available = False
        counter = 0
        while True:
            counter += 1 # Try next available filename. 
            if counter > 100:
                self.Log("logfile.UniqueFilename(",filename,"). Exhausted allowed range of names.",level='error')
                break
            uniquefilename = fileelements[0] + "_" + str(counter) + '.' + fileelements[1] # bla/bla/bla/bla/filename_{count}.filetype
            if os.path.exists(uniquefilename) == False: # The name is unused.
                break
        return uniquefilename

    #def PackageSearchResultXXX(self,searchterms,ignorecase=False):
    #    """ Generate a ZIP file with a selection of entries from the current log file. 
    #        searchterms = the selection phrase for grep.
    #            Examples: "RPi received|RPi queueing" - Lists lines containing either phrase.        
    #        Returns a ZIP filename. """
    #    path = os.path.dirname(self.FileName)
    #    timestamp = str(self.NowUTC())
    #    for c in ['-',':','.',' ']:
    #        timestamp = timestamp.replace(c,'')
    #    timestamp = timestamp.split('+')[0]
    #    resultfile = os.path.join(path,'result_' + timestamp + '.log')
    #    zipfile = os.path.join(path,'result_' + timestamp + '.zip')
    #    self.Log("logfile.PackageSearchResult(",searchterms,") Begin.",terminal=False)
    #    if ignorecase:
    #        # -a : Treat file as text.
    #        # -i : ignore case.
    #        cmd = 'egrep -a -i "' + searchterms + '" ' + self.FileName + '>' + resultfile
    #    else:
    #        cmd = 'egrep -a "' + searchterms + '" ' + self.FileName + '>' + resultfile
    #    self.Log("logfile.PackageSearchResult:",cmd,terminal=False)
    #    os.system(cmd)
    #    cmd = 'zip ' + zipfile + ' ' + resultfile
    #    self.Log("logfile.PackageSearchResult:",cmd,terminal=False)
    #    os.system(cmd)
    #    return zipfile

    def PackageSearchResult(self,searchterms,ignorecase=False):
        """ Generate a ZIP file with a selection of entries from the current log file. 
            searchterms = the selection phrase for grep.
                Examples: "RPi received|RPi queueing" - Lists lines containing either phrase.        
            Returns a ZIP filename. """
        resultfile = self.UniqueFilename(self.FileName)
        zipfile = resultfile.split('.')[0] + '.zip'
        self.Log("logfile.PackageSearchResult(",searchterms,") Begin.",terminal=False)
        if ignorecase:
            # -a : Treat file as text.
            # -i : ignore case.
            cmd = 'egrep -a -i "' + searchterms + '" ' + self.FileName + '>' + resultfile
        else:
            cmd = 'egrep -a "' + searchterms + '" ' + self.FileName + '>' + resultfile
        self.Log("logfile.PackageSearchResult:",cmd,terminal=False)
        os.system(cmd)
        cmd = 'zip ' + zipfile + ' ' + resultfile
        self.Log("logfile.PackageSearchResult:",cmd,terminal=False)
        os.system(cmd)
        return zipfile

#
        