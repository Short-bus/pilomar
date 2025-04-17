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

import os # OS Command execution.
import json # json file handling.
from datetime import datetime, timezone
import pytz # Timezone handling.

# -----------------------------------------------------------------------------------------------------------

class attributemaster(): # A parent class containing some common methods that other classes can inherit from.
    """ General base class that other classes can be based upon.
        Provides useful methods that many classes may use. """

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self._NullLoggerCalls = 0 # How many times is _NullLogger called?
        self.Logger = logger # Logger instance.
        self.Log = self._NullLogger # No log method.
        self.ReportException = self._NullLogger # Cannot report exception details to logfile.
        self.RaiseException = self._NullLogger # Cannot report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 

    def _NullLogger(self,*args, **kwargs):
        """ Null logger. Absorbs parameters and does nothing. 
            Use this when there is no logger defined.
            It prevents logging messages causing failure if no logger is defined. """
        self._NullLoggerCalls += 1 # increment count of how many times this was called.
        return

    def SaveAttributes(self,filename : str):
        """ Pull parameter attribute values out of the object and store back into the parameter dictionary.
            Save the parameter dictionary back to disc.
            If the target file exists it will be overwritten by the 'mv' command. """
        tempfilename = filename.replace(".json",".tmp") # During creation, the file is given a temporary filename, so that any reading process doesn't pick it up too soon.
        tempdictionary = self.SaveToDictionary() # Save to a working dictionary. 
        with open(tempfilename,'w') as f: # Dump as json to disc.
            json.dump(tempdictionary,f,indent=4,default=str) # Save the updated dictionary back to disc.
        os.replace(tempfilename,filename)            

    def SaveToDictionary(self,allowlist = None, denylist = None, initialdictionary={}, nameprefix=None) -> dict:
        """ Adds the ability to save attributes of the object to a dictionary.
            It ignores any attributes starting with '_' character.
            allowlist: If specified lists the fieldnames that should be saved. If missing, all fields are saved.
            denylist: If specified lists fieldnames that will NOT be saved, all others are.
            initialdictionary provides initial values that this method will append to.
            nameprefix provides an optional prefix to all the fieldnames.
            It will also ignore certain datatypes which don't save well or are typically very large (numpy arrays). """
        confdict = initialdictionary # Start an empty dictionary. 
        methodlist = [method for method in dir(self) if callable(getattr(self, method))] # Don't export callable attributes (= methods).
        for attr, value in vars(self).items():
            if attr[0] == '_': continue # Don't send internals.
            if attr in methodlist: continue # Don't list methods.
            if denylist != None and attr in denylist: continue # Blocked item. Don't save.
            if allowlist is None or attr in allowlist: # Allowed item, save.
                if nameprefix != None: attr = nameprefix + attr # Add optional prefix to fieldname.
                confdict[attr] = value
        return confdict

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

def DTSToDatetime(utcvalue) -> datetime:
    """ Accept a str(datetime) string and convert it into datetime. 
        Eg 2023-06-23 04:00:00.00000+00:00
        Regardless of any timezone info, UTC is assumed. """
    try:
        if '+' in utcvalue: utcvalue = utcvalue.split('+')[0] # Remove timezone.
        if '.' in utcvalue: utcvalue = utcvalue.split('.')[0] # Remove decimal seconds.
        dt = datetime.strptime(utcvalue,'%Y-%m-%d %H:%M:%S')
        dt = dt.replace(tzinfo=pytz.UTC) # Add UTC timezone.
    except:
        dt = None
    return dt

# ------------------------------------------------------------------------------------------------------

def StringToDatetime(utcvalue) -> datetime:
    """ Accept any string containing a timestampand convert it into datetime. 
        Eg 2023-06-23 04:00:00.00000+00:00
        Eg 2023-06-23T04:00:00.00000
        Eg 2023.06.23 04:00:00
        etc.
        Regardless of any timezone info, UTC is assumed.
        This is less fussy about the format that the string contains. """
    try:
        clean = ''
        # Strip all non-digit characters.
        for c in utcvalue:
            if '0' <= c <= '9': clean += c
        clean = clean + '00000000000000000000' # Pad right with zeros
        clean = clean[:14] # Take yyyymmddhhmmss portion.
                           #      01234567890123
        year = int(clean[:4])
        month = int(clean[4:6])
        day = int(clean[6:8])
        hour = int(clean[8:10])
        minute = int(clean[10:12])
        second = int(clean[12:])
        dt = datetime(year,month,day,hour,minute,second,0)
        dt = dt.replace(tzinfo=pytz.UTC) # Add UTC timezone.
    except:
        dt = None
    return dt

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
