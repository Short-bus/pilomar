#!/usr/bin/python

# Class to execute OS commands, return command output, exit code and/or log output.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Import required libraries
import subprocess # Threadsafe os command execution with access to command output.
import locale

class oscommand():
    """ object to execute OS commands. """
    
    @staticmethod
    def Delocalize(text):
        """ Convert a text from the locale number format into a standardised en_US format.
            The parent program must have already set the local environment before calling this.
                import locale
                locale.setlocale(locale.LC_ALL, '') # Get user's locale.                """
        text = text.strip() # Remove blanks and special characters.
        #locale.localeconv()['decimal_point']
        text = locale.delocalize(text)
        #dp = locale.localeconv()['decimal_point']
        #ts = locale.localeconv()['thousands_sep']
        #if dp != '.' or ts != ',': 
        #    text = text.replace(ts,'') # Remove thousands separators. We don't need them.
        #    text = text.replace(dp,'.') # Make sure the DECIMAL point is used.
        return text

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.Log = logger # Log method instance. Default to original solution, logger = a logfile.Log() method handle.
        self.ReportException = None # Cannot report exception details to logfile.
        self.RaiseException = None # Cannot report and raise exception. 
        # Support new solution, if logger is a logfile instance, assign method handles dynamically.
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        #self.Log("astrocamera.SetLogger: Linked to this log file.",terminal=False)

    def _NullLogger(self,*args, **kwargs):
        """ Null logger. Absorbs parameters and .Log call but does nothing. 
            Use this when there is no logger defined. """
        return

    def __init__(self,logger=None):
        self.SetLogger(logger) # CamLog # Handle to the class that handles logging and error tracing.
        #self.Log = logger # Must be a reference to a .Log() style method.
        self.LastError = None
        self.ReturnCode = 0
        self.LastOutput = []

    def Execute(self,cmd,output: str='none') -> list:
        """ Execute a command and record it to the log file.
            command and result is always recorded in the log file,
            return parameter is a clean list of output lines,
            output='terminal' : Default output is to the terminal. 
            output='none' : Suppresses output.
            output contains '.' : Output is written to that file. 
            This should be thread safe.
            """
        if self.Log != None: self.Log(cmd,terminal=False)
        self.LastError = None
        returncode = 0 # Assume success.
        try:
            result = subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode('utf-8')
        except subprocess.CalledProcessError as e:
            self.LastError = e
            returncode = e.returncode
            if self.Log != None:
                self.Log("oscommand.execute(" + cmd + ") returned " + str(e),terminal=False)
                self.Log("oscommand.execute(" + cmd + ") returned returncode " + str(e.returncode),terminal=False)
                self.Log("oscommand.execute(" + cmd + ") returned output " + str(e.output),terminal=False)
                self.Log("oscommand.execute(" + cmd + ") returned cmd " + str(e.cmd),terminal=False)
                self.Log("oscommand.execute(" + cmd + ") returned stdout " + str(e.stdout),terminal=False)
                self.Log("oscommand.execute(" + cmd + ") returned stderr " + str(e.stderr),terminal=False)
            result = "" # We lose result output, even if some was generated before the error was reached.
        lines = result.split('\n')
        returnlist = []
        for line in lines:
            if '.' in output: # Assume output is a disc file.
                with open(output,'a') as f: # Create or append to the specified file.
                    f.write(line + "\n")
            if output == 'terminal': print (line) # display to the terminal
            if self.Log != None: self.Log("cmd output '" + line + "'",terminal=False)
            returnlist.append(line) # Construct clean returnlist of the output.
        self.LastOutput = returnlist
        self.ReturnCode = returncode
        return returnlist

    def ExecuteCode(self,cmd,output : str = 'none') -> list: # Common # 1 references.
        """ Execute a command and record it to the log file.
            command and result is always recorded in the log file,
            Return parameter is the return code, 0 = Success, <> 0 is error.
            output='terminal' : Default output is to the terminal. 
            output='none' : Suppresses output.
            output contains '.' : Output is written to that file. 
            This should be thread safe.
            """
        if self.Log != None: self.Log(cmd,terminal=False)
        self.LastError = None
        returncode = 0 # Assume success.
        try:
            result = subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode('utf-8')
        except subprocess.CalledProcessError as e:
            self.LastError = e
            if self.Log != None:
                self.Log("oscommand.ExecuteCode(" + cmd + ") returned " + str(e),terminal=False)
                self.Log("oscommand.ExecuteCode(" + cmd + ") returned returncode " + str(e.returncode),terminal=False)
                self.Log("oscommand.ExecuteCode(" + cmd + ") returned output " + str(e.output),terminal=False)
                self.Log("oscommand.ExecuteCode(" + cmd + ") returned cmd " + str(e.cmd),terminal=False)
                self.Log("oscommand.ExecuteCode(" + cmd + ") returned stdout " + str(e.stdout),terminal=False)
                self.Log("oscommand.ExecuteCode(" + cmd + ") returned stderr " + str(e.stderr),terminal=False)
            returncode = e.returncode # return the return code.
            result = "" # We lose result output, even if some was generated before the error was reached.
        returnlist = []
        lines = result.split('\n')
        for line in lines:
            if '.' in output:
                with open(output,'a') as f: # Create or append to the specified file.
                    f.write(line + "\n")
            if output == 'terminal': print (line) # display to the terminal
            if self.Log != None: self.Log("cmd output '" + line + "'",terminal=False)
            returnlist.append(line)
        self.LastOutput = returnlist
        self.ReturnCode = returncode
        return returncode
