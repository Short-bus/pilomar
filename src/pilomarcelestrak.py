#!/usr/bin/python

# Class to handle satellite TLE data from Celestrak online source.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# 11.Dec.2023 / projectroot is now received from calling program and respected.

import os
from datetime import datetime, timedelta
from textcolor import textcolor
import json
import requests # To handle json response for seeing conditions from online services.
from requests.exceptions import HTTPError # Error handling.

class celestrak():
    """ Download celestrak TLE data. 
        Data is cached on disc and only updated once the disc cache is > 30 days old. """
    def __init__(self,url,logger=None,projectroot=None):
        self.SetLogger(logger) # Define which logging stream to use.
        self.URL = url # "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle" # Where to find the latest TLE data
        self.TLEDict = {} # TLE data converted into a dictionary for easy searching.
        if projectroot == None:
            self.CelestrakCacheFileName = '/home/pi/pilomar/data/celestrakcache.json' # The disc cache filename used to store the data locally.
        else: # ProjectRoot = '/home/pi/pilomar'
            self.CelestrakCacheFileName = projectroot + '/data/celestrakcache.json' # The disc cache filename used to store the data locally.
        self.SatelliteList = [] # List of satellite names, use for selecting objects.
        self.Refresh() # Refresh the data, load from CelesTrak if needed else use the disc cache.

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        self.Logger = logger # Logger instance.
        self.Log = logger.Log # Log method.
        self.ReportException = logger.ReportException # Report exception details to logfile.
        self.RaiseException = logger.RaiseException # Report and raise exception. 
        self.Log("celestrak.SetLogger: Linked to this log file.",terminal=False)
        
    def HRSeconds(self,seconds: int) -> str: # 15 references.
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

    def TleAgeWarning(self,name): # *Q* Is this still used?
        """ Extract the epoch datetime from the 1st line of a TLE entry.
            Warn if it's > 30days old. It will need updating. """
        line1, line2 = self.GetTleLines(name)
        if line1 == None:
            if self.Log != None: self.Log("celestrak.TleAgeWarning:",name,"is not recognised.",level='error',terminal=True)
            return
        epochyear = int(line1[18:20]) + 2000
        epochday = float(line1[20:32])
        epochdate = datetime(year=epochyear,month=1,day=1)
        epochdate += timedelta(days=int(epochday) - 1)
        daysold = (datetime.now() - epochdate).days # *Q* Offset not supported.
        if self.Log != None: self.Log(name,"TLE data was updated",epochdate,terminal=False)
        if daysold > 30:
            print(textcolor.YELLOW("WARNING: " + name + " TLE data is " + str(daysold) + " days old. It may now be inaccurate. Consider refreshing it."))
            print(textcolor.YELLOW("Check the source of data from the celestrak.org website."))
        else:
            print(textcolor.GREEN(name + " TLE data is " + str(daysold) + " days old."))
            
    def Refresh(self):
        """ Load data from cache if recent enough, else from celestrak.org website. """
        if self.Log != None: 
            self.Log("celestrak.Refresh: Begin",terminal=False)
            self.Log("celestrak.Refresh: Try disc cache",terminal=False)
        self.TLEDict = {} # No data until refreshed.
        self.LoadCache(self.CelestrakCacheFileName) # Try to load from disc if recent enough.
        if self.TLEDict == {}: # Empty, get a fresh copy.
            if self.Log != None: self.Log("celestrak.Refresh: Download fresh from internet.",terminal=False)
            if self.DownloadData():
                if self.Log != None: self.Log("celestrak.Refresh: Successful.",terminal=False)
            else:
                if self.Log != None: self.Log("celestrak.Refresh: Failed to download from internet, using cache anyway.",terminal=False)
                else: print("celestrak.Refresh: Failed to download from internet. Using cache anyway.")
                self.LoadCache(self.CelestrakCacheFileName,force=True) # Load the cache regardless of age.
        else:
            if self.Log != None: 
                self.Log("celestrak.Refresh: Used cached data instead of downloading from internet.",terminal=False)
        self.SatelliteList = [] # Make new list of satellite names.
        for key,value in self.TLEDict.items():
            self.SatelliteList.append(key)
        if len(self.SatelliteList) < 1: # The list is empty, something went wrong.
            if self.Log != None:
                self.Log("celestrak.Refresh: Failed to identify any satellies.",level='error')
            else:
                print("celestrak.Refresh: Failed to identify any satellies.")
        if self.Log != None:     
            self.Log("celestrak.Refresh: Satellites:", self.SatelliteList, terminal=False)
            self.Log("celestrak.Refresh: done",terminal=False)
        
    def DownloadData(self):
        """ Download fresh data from CelesTrak directly. """
        if self.Log != None: self.Log("celestrak.DownloadData: begin",terminal=False)
        WSOK = True
        try: # Trap and report errors, but don't allow the entire program to abort.
            response = requests.get(self.URL) # Try to retrieve the response from the remote server.
            response.raise_for_status() # Check for errors in the request.
            TLEText = response.text # Convert the response into a text object. 
            self.ExtractData(TLEText) # Convert text into dictionary.
        except HTTPError as e: # There was an HTTP error.
            if self.Log != None: self.Log('celestrak.DownloadData: HTTPError: ' + str(e),level='warning',terminal=False)
            WSOK = False
        except Exception as e: # There was some other sort of error.
            if self.Log != None: self.Log('celestrak.DownloadData: Error: ' + str(e),level='warning',terminal=True)
            WSOK = False
        self.Log("celestrak.DownloadData: end",WSOK,terminal=False)
        return WSOK

    def FileAge(self,filename): # 2 references.
        """ How many seconds old is a file? """
        if os.path.exists(filename):
            mtime = os.path.getmtime(filename)
            td = datetime.now() - datetime.fromtimestamp(mtime) # *Q* Offset not supported.
            result = int(td.total_seconds())
        else:
            result = None
        return result

    def LoadCache(self,filename,force=False):
        """ Load a single cache if available and recent enough.
            force=False: A blank dictionary is returned if the cache is too old.
            force=True: Dictionary is returned from cache regardless of age. """
        if os.path.exists(filename):
            fa = self.FileAge(filename)
            self.Log("celestrak.LoadCache:",filename,"is",self.HRSeconds(fa),"old",terminal=False)
            if force or fa < (5 * 24 * 60 * 60): # Only use the cache if less than 5 days old.
                with open(filename,'r') as f:
                    self.Log("celestrak.LoadCache: Loading Cache:",filename,"force",force,terminal=False)
                    self.TLEDict = json.load(f)
        else:
            if self.Log != None: self.Log("celestrak.LoadCache:",filename,"cache does not exist.",terminal=False)
        
    def ExtractData(self,TLEText):
        """ Given the TLEText list of satellites, extract each satellite entry into a dictionary.
            Save the dictionary as a json file so it can be reused without more web calls. """
        if self.Log != None: self.Log("celestrak.ExtractData: Begin",terminal=False)
        itemdict = {}
        itemname = ''
        for line in TLEText.split('\n'): # Split the text by newline characters.
            line = line.strip() # Remove all other line terminators.
            if line.startswith('1 '): #1st data line of tle data.
                itemdict['1'] = line # Set TLE line 1 element.
            elif line.startswith('2 '): #last data line of tle data.
                itemdict['2'] = line # Set TLE line 2 element.
                self.TLEDict[itemname] = itemdict # This completes the TLE entry, add it to the dictionary.
                itemdict = {} # clear for building next entry.
            else: # 1st line of tle data.
                itemname = line # Set the name of the satellite.
        with open(self.CelestrakCacheFileName,'w') as f: # Dump as json to disc.
            json.dump(self.TLEDict,f,indent=4,default=str) # Save the updated dictionary back to disc.
                
    def GetTleLines(self,name):
        """ Return the two TLE lines for any given satellite name.
            Returns None values if the name does not exist.        """
        line1 = None
        line2 = None
        if name in self.TLEDict:
            line1 = self.TLEDict[name]['1']
            line2 = self.TLEDict[name]['2']
        else:
            if self.Log != None: self.Log("celestrak.GetTleLines: '" + str(name) + "' not found.",terminal=False)
        return line1, line2
        
