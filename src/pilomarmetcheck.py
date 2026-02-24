#!/usr/bin/python

# ------------------------------------------------------------------------------------------------------
# There are online resources to forecast the 'seeing' conditions for astronomy. This forecasts things like the wind, temperature, cloud 
# and the atmospheric turbulence that can degrade the quality of an image. Turbulance will blur a star out for example.
# The metcheck.com service provides a 3hourly forecast. Define a class which can read this over the internet and output some 
# human readable explanation of the forecast. This can be saved in the observation notes (DocumentSession function) and displayed
# in the ObservationRun display if there is enough space.
# Weather forecast class for use in Pilomar project.
#
# 1) This reads the JSON forecast data from the Metcheck.com website.
# 2) It caches the JSON file on disc for short-term efficiency and to reduce the requests to the website.
# 3) It appends to a permanent list of forecast data for historic analysis.
# 4) It translates and transforms the JSON forecast data into a matrix of measures vs times.
# 5) It can then output the data in various forms.
#    a) It can populate textcolor.colordisplay instances if given the instance handle. UpdateWindow() method.
#    b) It can show a color coded list of forecast data to the terminal. TwelveHourForecast() method.
#    c) It can return the forecast matrix to the calling program for further processing. CurrentMeasures() method.
#
# ------------------------------------------------------------------------------------------------------

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import requests # To handle json response for seeing conditions from online services.
from requests.exceptions import HTTPError # Error handling.
from datetime import datetime, timezone, timedelta
from datetime import time as datetime_time # rename this class to avoid ambiguity in the code.
import pytz
import os
from textcolor import textcolor
from pilomartimer import timer
import json

class metcheck_handler(): # 1 references.
    """ Load and maintain Astronomical Seeing conditions from www.metcheck.com 
        Other sources are available, this demonstrates what is possible. 
        
        Metcheck.com provides various forecast datasets.
        This combines the ASTRO and NORMAL data sets to produce a matrix of measures vs times.
        
        """

    VERSION = "0.0.3" # Version number for the class.
    
    def __init__(self,logger,cachedir,enabled,lonval,latval,suntarget,moontarget):
        """ Parameters -------------------------------------------------------------------
            logger: Reference to a pilomarlogfile instance. It will be used to create .Log, .ReportException and .RaiseException methods.
            cachedir: The directory where the persistent data cache files are stored. eg '/home/pi/pilomar/data'
            enabled: Is the weather service active or not?
            lonval: Observer's longitude.
            latval: Observer's latitude.
            suntarget: Instance of pilomar 'target' class which references the Sun.
                       Position of the Sun is used to establish twilight leve.
            moontarget: Instance of pilomar 'target' class which references the Moon.
                        Used to calculate if Moon is visible and how bright it is. """
        self.SetLogger(logger) # Setup links to logging instance and shortcuts to logging methods.
        self.SourceTitle = 'metcheck.com'
        self.ClockOffset = None
        self.UseWeatherService = enabled # Turn on/off the service.
        self.WebServiceOK = False # Indicates that last web service call was successful. 
        self.MoonTarget = moontarget # Optional link to pilomar 'target' instance for moon measurements.
        self.SunTarget = suntarget # Optional link to pilomar 'target' instance for sun measurements.
        self.Lat = latval
        self.Lon = lonval
        # Available products are 'As' (astro), 'No' (normal) and others...
        self.AstroURL = 'http://ws1.metcheck.com/ENGINE/v9_0/json.asp?lat={lat}&lon={lon}&Fc=As' # Template for request URL.
        self.AstroURL = self.AstroURL.format(lon=lonval,lat=latval) # Insert the current location into the request.
        self.AstroResult = {} # Empty result dictionary. 
        self.CivilURL = 'http://ws1.metcheck.com/ENGINE/v9_0/json.asp?lat={lat}&lon={lon}&Fc=No' # Template for request URL.
        self.CivilURL = self.CivilURL.format(lon=lonval,lat=latval) # Insert the current location into the request.
        self.CivilResult = {} # Empty result dictionary. 
        self.AstroCacheFilename = cachedir + 'astrocache.json' # Store latest data on disc, good for debug/development and reduces calls to web service.
        self.CivilCacheFilename = cachedir + 'civilcache.json'
        self.RequestHeader = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"} # Metcheck needs headers specifying otherwise the request is denied.
        self.ArchiveFile = cachedir + 'weatherarchive.csv' # Data is archived on disc in this csv file.
        self.Timer = timer(3600) # Set refresh timer for every 60 minutes (=3600 seconds).
        self.ForecastMatrix = None # Will contain a matrix of all the forecast data vs time when populated.
                                   # self.ForecastMatrix[MeasureKey][Timestamp]
                                   #   The list of MeasureKey values can be found in self.MatrixKeys
                                   #   The list of Timestamp values can be found in self.MatrixDates
        self.MatrixKeys = None # Will contain a list of the data values in the ForecastMatrix.
                               # self.MatrixKeys = list of MeasureKey values, the same sequence as self.ForecastMatrix.           
                               # An entry for each measure received from Metcheck in the JSON files, plus some additional calculated values (eg Fog related estimates)
        self.MatrixDates = None # Will contain a list of the timestamp values in the ForecastMatrix.
                                # self.MatrixDates = list of Timestamp values, the same sequence as self.ForecastMatrix.
                                # An entry for each forecast timeslot received from Metcheck in the JSON files.
        self.CurrentMeasuresCache = None # Dictionary of the current forecast data.
        self.CurrentMeasuresExpiry = None # Datetime when the current forecast data expires.
        self.MaxCacheFileAge = 2 * 60 * 60 # Only use the cache if younger than this. (2hours in seconds.)
        self.Refresh() # Try to update the information immediately.
        self.TextFG = textcolor.SILVER
        self.TextBG = textcolor.GREY11
        # Define a standard range of colours which can be applied to all the 'percentage' measurement values.
        percentage_low_good = {-100000: textcolor.GREEN, 25: textcolor.LIGHTGREEN, 50: textcolor.YELLOW, 75: textcolor.ORANGE1, 90: textcolor.RED}
        percentage_verylow_good = {-100000: textcolor.GREEN, 10: textcolor.YELLOW, 40: textcolor.ORANGE1, 75: textcolor.RED}
        # Consolidated color and translation tables for both ASTRO and CIVIL measurements.
        # Colors dictionary contains an entry per 'measure'.
        # The entry can provide
        # - '{value}' = When 'quoted', it's the display color associated with a specific value.
        # - {value} = When a float/int, it's the display color associated with values >= {value} (This allows colors to be assigned to ranges of values rather than specific values).
        self.MeasureColours = {
            'seeingIndex': {'0': textcolor.RED, '1': textcolor.RED, '2': textcolor.ORANGE1, 
                            '3': textcolor.ORANGE1, '4': textcolor.ORANGE1, '5': textcolor.YELLOW, 
                            '6': textcolor.YELLOW, '7': textcolor.LIGHTGREEN, '8': textcolor.LIGHTGREEN, 
                            '9': textcolor.GREEN, '10': textcolor.GREEN},
            'pickeringIndex': {'0': textcolor.RED, '1': textcolor.RED, '2': textcolor.ORANGE1, 
                               '3': textcolor.ORANGE1, '4': textcolor.ORANGE1, '5': textcolor.ORANGE1, 
                               '6': textcolor.YELLOW, '7': textcolor.YELLOW, '8': textcolor.LIGHTGREEN, 
                               '9': textcolor.LIGHTGREEN, '10': textcolor.LIGHTGREEN, '11': textcolor.LIGHTGREEN, 
                               '12': textcolor.GREEN},
            'transIndex': {'0': textcolor.RED, '1': textcolor.RED, '2': textcolor.ORANGE1, 
                           '3': textcolor.ORANGE1, '4': textcolor.ORANGE1, '5': textcolor.ORANGE1, 
                           '6': textcolor.YELLOW, '7': textcolor.YELLOW, '8': textcolor.LIGHTGREEN, 
                           '9': textcolor.LIGHTGREEN, '10': textcolor.LIGHTGREEN, '11': textcolor.LIGHTGREEN, 
                           '12': textcolor.GREEN},
            'temperature': {-100: textcolor.PURPLE, -30: textcolor.MAGENTA, -20: textcolor.BLUE, 
                            -10: textcolor.CYAN, 0: textcolor.GREEN, 15: textcolor.LIGHTGREEN, 
                            20: textcolor.YELLOW, 25: textcolor.ORANGE1, 30: textcolor.RED},
            'lowcloud': percentage_low_good,
            'medcloud': percentage_low_good,
            'highcloud': percentage_low_good,
            'totalcloud': percentage_verylow_good,
            'humidity': percentage_low_good,
            'dayOrNight': {'D': textcolor.RED, 'N': textcolor.GREEN},
            'windspeed': {0: textcolor.GREEN, 10: textcolor.LIGHTGREEN, 15: textcolor.YELLOW, 
                          20: textcolor.ORANGE1, 25: textcolor.RED},
            'windgustspeed': {0: textcolor.GREEN, 10: textcolor.LIGHTGREEN, 20: textcolor.YELLOW, 
                              30: textcolor.ORANGE1, 40: textcolor.RED},
            'chanceofrain': percentage_low_good,
            'chanceofsnow': percentage_low_good,
            'lightLevel': {'day': textcolor.RED, 'civil': textcolor.ORANGE1, 'naut': textcolor.YELLOW, 'astro': textcolor.LIGHTGREEN, 'night': textcolor.GREEN},
            'moonLight': percentage_verylow_good,
            'fogRisk': {'0': textcolor.GREEN, '1': textcolor.GREEN, '2': textcolor.LIGHTGREEN, '3': textcolor.YELLOW, 
                        '4': textcolor.YELLOW, '5': textcolor.ORANGE1, '6': textcolor.ORANGE1, 
                        '7': textcolor.ORANGE1, '8': textcolor.RED, '9': textcolor.RED}
            }
        # Translation dictionary contains an entry per 'measure'.
        # The entry can provide
        # - 'desc' = Description of the measure.
        # - '{value}' = Translation of specific values.
        # - 'pattern' = Formatting pattern for the value (use it to add UOM for example).
        # - 'fieldnames' = List of textcolor.colordisplay fieldnames that can be auto-populated by the UpdateWindow() class.
        self.MeasureTranslation = {
            # Seeing index is one measure of blurring due to atmospheric turbulence.
            "seeingIndex": {'desc': 'Seeing index', 
                            '0':'Worst', '1':'Terrible', '2':'Bad', '3':'Bad', 
                            '2-3':'Bad', '4':'Poor', '5':'Poor', '6':'Poor', 
                            '4-6':'Poor', '7':'Fair', '8':'Fair', '7-8':'Fair', 
                            '9':'Excellent', '10':'Excellent', '9-10':'Excellent', 'pattern': None, 'fieldnames': ['SI']},
            # Pickering seeing index one measure of blurring due to atmospheric turbulence.                
            # Pickering seeing index of 1 to 3 is considered very poor, 4 to 5 is poor, 6 to 7 is good, and 8 to 10 is excellent. (Wikipedia definitions)
            "pickeringIndex": {'desc': 'Pickering seeing', 
                               '0':'Very poor', '1':'Very poor', '2':'Very poor', '3':'Very poor', 
                               '4':'Poor', '5':'Poor', '6':'Good', '7':'Good', 
                               '8':'Excellent','9':'Excellent', '10':'Excellent', '11':'Excellent', 
                               '12':'Excellent', 'pattern': None, 'fieldnames': ['PI']},
            "temperature": {'desc': 'Temp', 'pattern': '{0}C', 'fieldnames': ['TE']},
            "dewpoint": {'desc': 'Dewpoint', 'pattern': '{0}C', 'fieldnames': ['DP']},
            "rain": {'desc': 'Rain', 'pattern': '{0}mm', 'fieldnames': ['RD']},
            "freezinglevel": {'desc': 'Freezing level', 'pattern': '{0}m', 'fieldnames': ['FL']},
            "totalcloud": {'desc': 'Cloud: Total cover', 'pattern': '{0}%', 'fieldnames': ['CT']},
            "lowcloud": {'desc': 'Cloud: Low cover', 'pattern': '{0}%', 'fieldnames': ['CL']},
            "medcloud": {'desc': 'Cloud: Medium cover', 'pattern': '{0}%', 'fieldnames': ['CM']},
            "highcloud": {'desc': 'Cloud: High cover', 'pattern': '{0}%', 'fieldnames': ['CH']},
            "humidity": {'desc': 'Humidity', 'pattern': '{0}%', 'fieldnames': ['HU']},
            "windspeed": {'desc': 'Windspeed (mph)', 'pattern': '{0}mph', 'fieldnames': ['WS']},
            "meansealevelpressure": {'desc': 'Pressure (hPa)', 'pattern': '{0}hPa', 'fieldnames': ['PR']},
            "windgustspeed": {'desc': 'Wind gusts (mph)', 'pattern': '{0}mph', 'fieldnames': ['WG']},
            "winddirection": {'desc': 'Wind angle', 'pattern': '{0}deg', 'fieldnames': ['WA']},
            "chanceofrain": {'desc': 'Rain chance', 'pattern': '{0}%', 'fieldnames': ['RC','RPB']},
            "chanceofsnow": {'desc': 'Snow chance', 'pattern': '{0}%', 'fieldnames': ['SC','SPB']},
            "fogRisk": {'desc': 'Fog risk', 'pattern': None, 'fieldnames': ['FOG']},
            "lightLevel": {'desc': 'Light level', 'pattern': None, 'fieldnames': []},
            "moonLight": {'desc': 'Moonlight', 'pattern': '{0}%', 'fieldnames': []}
            }
        
    def SetLogger(self,logger): # Set up link to logging class and shortcuts to common methods.
        """ Set up link to logging class and shortcuts to common methods. """
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.Logger = logger # Logger instance.
        self.Log = self._NullLogger # No log method.
        self.ReportException = self._NullLogger # Cannot report exception details to logfile.
        self.RaiseException = self._NullLogger # Cannor report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 

    def _NullLogger(self,*args, **kwargs): # Null logger. Absorbs parameters and .Log call but does nothing. 
        """ Null logger. Absorbs parameters and .Log call but does nothing. 
            Use this when there is no logger defined. """
        return

    def NowUTC(self,real=False) -> datetime: # Get system clock as UTC (timezone aware) 
        """ Get system clock as UTC (timezone aware) 
            Microcontroller and Skyfield are operated in UTC vales. 
            All clock-times used in this program use the UTC timestamped clock.
            This should be the only reference to datetime.now() method in the entire
            program. All other uses should refer to this NowUTC() function.
            real=True means that no time offset is applied, you get the true realtime clock value.
            real=False means that any time offset is applied, making the clock run at some other point in time.
            NOTE: Changing the clock offset for a live feed from the internet probably results in mismatched data!
            """
        dt = datetime.now(timezone.utc) # Offset supported.
        if real == False and self.ClockOffset != None: # Can apply time offset.
            dt = dt + timedelta(seconds=self.ClockOffset)
        return dt
        
    def DateToColumn(self,searchdate): # Convert any datetime into the correct column from the forecast data.
        """
        Convert any datetime into the correct column from the forecast data.
        """
        selectedcolumn = None
        for iCol,entry in enumerate(self.MatrixDatetimes):
            if entry <= searchdate: 
                selectedcolumn = iCol
        return selectedcolumn        

    def ColumnExpiry(self,column): # Return expiry datetime for a given column.
        """
        Return expiry datetime for a given column.
        """
        column += 1 # Select datetime of NEXT column.
        if column >= len(self.MatrixDatetimes): # There is no next column.
            expires = self.MatrixDatetimes[-1] + timedelta(hours=1)
        else:
            expires = self.MatrixDatetimes[column]
        return expires
        
    def SelectForecast(self): # Return current entry from forecast.
        """ From a matrix of forecasts, return the current entry.
            This adds a 'timestamp' entry to the forecast data. """
        # Creates a dictionary with the 'current' raw values from the metcheck data feed.
        # {'windspeed':'30', 'windgustspeed':'50',... etc}
        # Which column (timeslot) from the matix do we need?
        selectedcolumn = None
        expires = None
        tn = self.NowUTC()
        for iCol,entry in enumerate(self.MatrixDatetimes):
            if entry <= tn: 
                selectedcolumn = iCol
            elif expires == None:
                expires = entry # When does this forecast slot expire?
        result = {}
        # Pull all the values from that column.
        for iRow,key in enumerate(self.MatrixKeys): # Poll through each entry in the dataseries.
            result[key] = self.ForecastMatrix[iRow][selectedcolumn]
        if selectedcolumn != None:
            result['timestamp'] = self.MatrixDatetimes[selectedcolumn] # Add timestamp when this forecast begins.
        else:
            result['timestamp'] = self.NowUTC()
        if expires != None:
            result['expires'] = expires # Add timestamp when this forecast expires.
        else:
            result['expires'] = self.NowUTC()
        return result
        
    def ExifHeaderTags(self,filename): # Generate json file with weather readings for jpeg EXIF headers.
        """ This generates a json file with weather readings that can be 
            added to .json exif tag headers.
            Select from :
                {'TE': {'value': '20C', 'fg': 11, 'bg': None, 'title': 'temperature', 'desc': '', 'numeric':20, 'unit':'C'}, 
                 'DP': {'value': '10C', 'fg': None, 'bg': None, 'title': 'dewpoint', 'desc': ''}, 
                 'RD': {'value': '0.0mm', 'fg': None, 'bg': None, 'title': 'rain', 'desc': ''}, 
                 'FL': {'value': '3902m', 'fg': None, 'bg': None, 'title': 'freezinglevel', 'desc': ''}, 
                 'CT': {'value': '99%', 'fg': 9, 'bg': None, 'title': 'totalcloud', 'desc': ''}, 
                 'CL': {'value': '6%', 'fg': 2, 'bg': None, 'title': 'lowcloud', 'desc': ''}, 
                 'CM': {'value': '98%', 'fg': 9, 'bg': None, 'title': 'medcloud', 'desc': ''}, 
                 'CH': {'value': '99%', 'fg': 9, 'bg': None, 'title': 'highcloud', 'desc': ''}, 
                 'HU': {'value': '69%', 'fg': 11, 'bg': None, 'title': 'humidity', 'desc': ''}, 
                 'WS': {'value': '6mph', 'fg': 2, 'bg': None, 'title': 'windspeed', 'desc': ''}, 
                 'PR': {'value': '1011hPa', 'fg': None, 'bg': None, 'title': 'meansealevelpressure', 'desc': ''}, 
                 'WG': {'value': '15mph', 'fg': 119, 'bg': None, 'title': 'windgustspeed', 'desc': ''}, 
                 'WA': {'value': '238deg', 'fg': None, 'bg': None, 'title': 'winddirection', 'desc': ''}, 
                 'RC': {'value': '47%', 'fg': 119, 'bg': None, 'title': 'chanceofrain', 'desc': ''}, 
                 'RPB': {'value': '47%', 'fg': 119, 'bg': None, 'title': 'chanceofrain', 'desc': ''}, 
                 'SC': {'value': '0%', 'fg': 2, 'bg': None, 'title': 'chanceofsnow', 'desc': ''}, 
                 'SPB': {'value': '0%', 'fg': 2, 'bg': None, 'title': 'chanceofsnow', 'desc': ''}, 
                 'SI': {'value': '0', 'fg': 9, 'bg': None, 'title': 'seeingIndex', 'desc': ''}, 
                 'PI': {'value': '7', 'fg': 11, 'bg': None, 'title': 'pickeringIndex', 'desc': ''}, 
                 'FOG': {'value': '3', 'fg': 11, 'bg': None, 'title': 'fogRisk', 'desc': ''}}

            This file is used by pilomarfits.py utility to add weather conditions to 
            the header information in new .jpg image files generated by pi-lomar. """
                
        currentmeasures = self.CurrentMeasures() # Get latest measurements. 
        
        # Construct exif tag dictionary. 
        # There are all applied 'as is' to the FITS header.
        exiftags = {
             "Humidity": currentmeasures['HU']['numeric'], # Percentage
             "Pressure": currentmeasures['PR']['numeric'], # hPa.
             "Temperature": currentmeasures['TE']['numeric'] # C 
        }
        
        # Write fits header tags as .json file. This is picked up by src/pilomarfits.py when generating .jpeg images.
        with open(filename,'w') as f:
            json.dump(exiftags, f)

    def FitsHeaderTags(self,filename): # Generate JSON file with weather readings for FITS file headers.
        """ This generates a json file with weather readings that can be 
            added to .FITS file headers.
            Select from :
                {'TE': {'value': '20C', 'fg': 11, 'bg': None, 'title': 'temperature', 'desc': '', 'numeric':20, 'unit':'C'}, 
                 'DP': {'value': '10C', 'fg': None, 'bg': None, 'title': 'dewpoint', 'desc': ''}, 
                 'RD': {'value': '0.0mm', 'fg': None, 'bg': None, 'title': 'rain', 'desc': ''}, 
                 'FL': {'value': '3902m', 'fg': None, 'bg': None, 'title': 'freezinglevel', 'desc': ''}, 
                 'CT': {'value': '99%', 'fg': 9, 'bg': None, 'title': 'totalcloud', 'desc': ''}, 
                 'CL': {'value': '6%', 'fg': 2, 'bg': None, 'title': 'lowcloud', 'desc': ''}, 
                 'CM': {'value': '98%', 'fg': 9, 'bg': None, 'title': 'medcloud', 'desc': ''}, 
                 'CH': {'value': '99%', 'fg': 9, 'bg': None, 'title': 'highcloud', 'desc': ''}, 
                 'HU': {'value': '69%', 'fg': 11, 'bg': None, 'title': 'humidity', 'desc': ''}, 
                 'WS': {'value': '6mph', 'fg': 2, 'bg': None, 'title': 'windspeed', 'desc': ''}, 
                 'PR': {'value': '1011hPa', 'fg': None, 'bg': None, 'title': 'meansealevelpressure', 'desc': ''}, 
                 'WG': {'value': '15mph', 'fg': 119, 'bg': None, 'title': 'windgustspeed', 'desc': ''}, 
                 'WA': {'value': '238deg', 'fg': None, 'bg': None, 'title': 'winddirection', 'desc': ''}, 
                 'RC': {'value': '47%', 'fg': 119, 'bg': None, 'title': 'chanceofrain', 'desc': ''}, 
                 'RPB': {'value': '47%', 'fg': 119, 'bg': None, 'title': 'chanceofrain', 'desc': ''}, 
                 'SC': {'value': '0%', 'fg': 2, 'bg': None, 'title': 'chanceofsnow', 'desc': ''}, 
                 'SPB': {'value': '0%', 'fg': 2, 'bg': None, 'title': 'chanceofsnow', 'desc': ''}, 
                 'SI': {'value': '0', 'fg': 9, 'bg': None, 'title': 'seeingIndex', 'desc': ''}, 
                 'PI': {'value': '7', 'fg': 11, 'bg': None, 'title': 'pickeringIndex', 'desc': ''}, 
                 'FOG': {'value': '3', 'fg': 11, 'bg': None, 'title': 'fogRisk', 'desc': ''}}

            This file is used by pilomarfits.py utility to add weather conditions to 
            the header information in new .fits image files generated by pi-lomar. """
                
        currentmeasures = self.CurrentMeasures() # Get latest measurements. 
        
        # Construct fits tag dictionary. 
        # There are all applied 'as is' to the FITS header.
        WGV = int(currentmeasures['WG']['numeric'] * 1.60934)
        WSV = int(currentmeasures['WS']['numeric'] * 1.60934)
        WSAV = int(currentmeasures['WS']['numeric'] * 1609.34 / 3600)
        WGAV = int(currentmeasures['WG']['numeric'] * 1609.34 / 3600)
        fitstags = {
            "CLOUDCVR":{'value':currentmeasures['CT']['numeric'], 
                        'comment':'Cloud cover (%)'},
            "DEWPOINT":{'value':currentmeasures['DP']['numeric'],
                        'comment':'Dewpoint (C)'},
            "HUMIDITY":{'value':currentmeasures['HU']['numeric'], 
                        'comment':'Humidity (%)'},
            "PRESSURE":{'value':currentmeasures['PR']['numeric'],
                        'comment':'Air pressure (hPa)'},
            "AMBTEMP": {'value':currentmeasures['TE']['numeric'],
                        'comment':'Ambient temperature (C)'},
            "WINDDIR": {'value':currentmeasures['WA']['numeric'],
                        'comment':'Wind direction (deg)'},
            "WINDGUST":{'value':WGV,
                        'comment':'Wind gust speed (kph)'},
            "WINDSPD": {'value':WSV,
                        'comment':'Windspeed (kph)'},
            "AOCAMBT": {'value':currentmeasures['TE']['numeric'],
                        'comment':'Ambient temperature (C)'},
            "AOCDEW":  {'value':currentmeasures['DP']['numeric'],
                        'comment':'Dew point (C)'},
            "AOCRAIN": {'value':0,                        
                        'comment':'Rain (mm/hr)'},
            "AOCHUM":  {'value':currentmeasures['HU']['numeric'],
                        'comment':'Humidity (%)'},
            "AOCWIND": {'value':WSAV,
                        'comment':'Wind speed (m/s)'},
            "AOCWINDD":{'value':currentmeasures['WA']['numeric'],
                        'comment':'Wind direction in (deg)'},
            "AOCWINDG":{'value':WGAV,
                        'comment':'Wind gust speed (m/s)'},
            "AOCBAROM":{'value':currentmeasures['PR']['numeric'],
                        'comment':'Barometric pressure (hPa)'},
            "AOCCLOUD":{'value':currentmeasures['CT']['numeric'],
                        'comment':'Cloud coverage (%)'}
        }
        # SKYBRGHT: Sky brightness in lux
        # MPSAS: Sky quality in mags/arcsecs^2
        # STARFWHM: Star FWHM - A measure of the crispness of stars.
        
        # Write fits header tags as .json file. This is picked up by src/pilomarfits.py when generating .fits images.
        with open(filename,'w') as f:
            json.dump(fitstags, f)
        
    def SplitNU(self,dval): # Split VALUE and UNIT from a combined string.
        """ Turn something like '20mph' into (20, 'mph') 
            Parameters -------------------------------------------------------
            dval: String of value and uom. Eg '20mph' 
            Outputs ----------------------------------------------------------
            numeric: The numeric value extracted from the input dval.
            unit: The uom extracted from the input dval. """
        numeric = 0 
        numbers = ''
        unit = ''
        for c in dval: # Process each character in turn.
            if self.IsInt(c): numbers += c
            else: unit += c
        numeric = int(numbers)
        return numeric, unit
        
    def CurrentMeasures(self): # Get dictionary of name, value and color for current forecast.
        """ Return dictionary of fieldname, value, colour for transferring to a colordisplay() window. 
            value is the formatted value, it applies any pattern defined in the MeasureTranslation dictionary. 
            It sets self.CurrentMeasuresCache with the dictionary and also returns it.
            
            Parameters ----------------------------------------------------------------------------------------------
            None: But uses self.CurrentMeasuresCache as a data source. 
            
            Outputs -------------------------------------------------------------------------------------------------
            sets self.CurrentMeasuresCache with the result and returns it as a dictionary too. 
            returndict contains entries per 'fieldname'
                'fieldname': The name of a field in colordisplay instance (ie a field in a formatted display window.)
            Each entry contains 
                'value': String (possibly formatted) representation of the value.
                'fg': suggested foreground color for colordisplay instances.
                'bg': Suggested background color for colordisplay instances.
                'title': The measure name in the original JSON file received from metcheck.
                'desc': A text explanation of the value if available. (eg 'poor','excellent' for seeing measures)
                'numeric': The numeric form of the value. (eg 20 for 20mph)
                'unit': The measurement unit for the value. (eg mph for 20mph) 
                
                {'TE': {'value': '20C', 'fg': 11, 'bg': None, 'title': 'temperature', 'desc': '', 'numeric':20, 'unit':'C'}, 
                 'DP': {'value': '10C', 'fg': None, 'bg': None, 'title': 'dewpoint', 'desc': ''}, 
                 'RD': {'value': '0.0mm', 'fg': None, 'bg': None, 'title': 'rain', 'desc': ''}, 
                 'FL': {'value': '3902m', 'fg': None, 'bg': None, 'title': 'freezinglevel', 'desc': ''}, 
                 'CT': {'value': '99%', 'fg': 9, 'bg': None, 'title': 'totalcloud', 'desc': ''}, 
                 'CL': {'value': '6%', 'fg': 2, 'bg': None, 'title': 'lowcloud', 'desc': ''}, 
                 'CM': {'value': '98%', 'fg': 9, 'bg': None, 'title': 'medcloud', 'desc': ''}, 
                 'CH': {'value': '99%', 'fg': 9, 'bg': None, 'title': 'highcloud', 'desc': ''}, 
                 'HU': {'value': '69%', 'fg': 11, 'bg': None, 'title': 'humidity', 'desc': ''}, 
                 'WS': {'value': '6mph', 'fg': 2, 'bg': None, 'title': 'windspeed', 'desc': ''}, 
                 'PR': {'value': '1011hPa', 'fg': None, 'bg': None, 'title': 'meansealevelpressure', 'desc': ''}, 
                 'WG': {'value': '15mph', 'fg': 119, 'bg': None, 'title': 'windgustspeed', 'desc': ''}, 
                 'WA': {'value': '238deg', 'fg': None, 'bg': None, 'title': 'winddirection', 'desc': ''}, 
                 'RC': {'value': '47%', 'fg': 119, 'bg': None, 'title': 'chanceofrain', 'desc': ''}, 
                 'RPB': {'value': '47%', 'fg': 119, 'bg': None, 'title': 'chanceofrain', 'desc': ''}, 
                 'SC': {'value': '0%', 'fg': 2, 'bg': None, 'title': 'chanceofsnow', 'desc': ''}, 
                 'SPB': {'value': '0%', 'fg': 2, 'bg': None, 'title': 'chanceofsnow', 'desc': ''}, 
                 'SI': {'value': '0', 'fg': 9, 'bg': None, 'title': 'seeingIndex', 'desc': ''}, 
                 'PI': {'value': '7', 'fg': 11, 'bg': None, 'title': 'pickeringIndex', 'desc': ''}, 
                 'FOG': {'value': '3', 'fg': 11, 'bg': None, 'title': 'fogRisk', 'desc': ''}}                """
        returndict = {} # The resulting dictionary will be stored here. 
        # Return a dictionary with current metcheck values converted into display attributes.
        # Only includes items which have entries in the translation table.
        # {'windspeed':{'value': 20, 'fg': 15, 'bg': 0, 'title': 'windspeed', 'desc': 'Windspeed (mph)'},
        #  'temperature':{'value': .....           },
        #  ... etc}
        #        {'value': dval, 'fg': fg, 'bg': bg, 'title': dkey, 'desc': desc}
        if self.CurrentMeasuresCache != None and self.CurrentMeasuresExpiry > self.NowUTC(): # Cached value is still valid.
            returndict = self.CurrentMeasuresCache
        else: # Need to calculate new current measures.
            self.Log("metcheck_handler.CurrentMeasures: Refreshing cache.",terminal=False)
            fulldict = self.SelectForecast() # Get the most current forecast from the forecast matrix.
            for key,value in fulldict.items(): # Process the KEY and VALUE pairs for the weather forecast source data.
                dkey = str(key) # Ensure key is a string.
                transvalue = self.MeasureTranslation.get(dkey,{}) # Get the translation entry for the key if it exists.
                if 'fieldnames' in transvalue: # The translation dictionary provides a fieldname for the colordisplay() instance.
                    fieldnames = transvalue['fieldnames'] # Get LIST of fieldnames.
                    pattern = transvalue.get('pattern',"") # This pattern will format the value in the display.
                    desc = transvalue.get(str(value),"") # If the value has a translation, get it here.
                    if pattern != None and len(pattern) > 0: # The pattern is valid.
                        dval = str(pattern).format(value) # Format the display string for the value.
                    else: # No valid pattern, so present the value as is.
                        dval = str(value)
                    for fieldname in fieldnames:
                        fg = self.SelectColor(key, value) # If the color rules exist for the weather value, set the foreground color appropriately.
                        numeric, unit = self.SplitNU(dval) # Separate out the NUMERIC and UNIT values from the value given.
                        returndict[fieldname] = {'value': dval, 'fg': fg, 'bg': None, 'title': dkey, 'desc': desc, 'numeric': numeric, 'unit': unit} # Create new entry for the defined window field.
                        self.Log("metcheck_handler.CurrentMeasures: Entry:",returndict[fieldname],terminal=False)
            self.CurrentMeasuresCache = returndict
            self.CurrentMeasuresExpiry = fulldict['expires']
        return returndict

    def ShowDictionaries(self): # Print all data calculated.
        """ Print out all the data that's been calculated so far. """
        self.Log("metcheck_handler.ShowDictionaries(): CurrentMeasuresCache:",self.CurrentMeasuresCache,terminal=True)
        print("")
        self.Log("metcheck_handler.ShowDictionaries(): MeasureTranslation:",self.MeasureTranslation,terminal=True)
        print("")
        self.Log("metcheck_handler.ShowDictionaries(): MeasureColours:",self.MeasureColours,terminal=True)
        print("")
        self.Log("metcheck_handler.ShowDictionaries(): AstroResult:",self.AstroResult,terminal=True)
        print("")
        self.Log("metcheck_handler.ShowDictionaries(): CivilResult:",self.CivilResult,terminal=True)
        print("")
        self.Log("metcheck_handler.ShowDictionaries(): MatrixKeys:",self.MatrixKeys,terminal=True)
        print("")
        self.Log("metcheck_handler.ShowDictionaries(): MatrixDates:",self.MatrixDates,terminal=True)
        print("")
        
    def UTCToDatetime(self,utcstring): # Convert ISO UTC timestamp to datetime.
        """ Convert ISO UTC style datetime string into datetime datatype. """
        dt = datetime.fromisoformat(utcstring.split('.')[0] + '+00:00')
        dt = dt.replace(tzinfo=pytz.UTC) # Clarify it's UTC timezone.
        return dt
        
    def UpdateWindow(self,windowhandle,notes=''): # Update fields directly in a colordisplay window instance.
        """ Update the fields in a colordisplay window. This is a public method called by the parent program.
            The windowhandle instance must have FieldValue(), FieldColor() and CopyFieldColor() methods implemented.
            - for example textcolor library's colordisplay() class does this. 
            
            CurrentMeasures contains a dictionary which tells what fields and colors to use...
                The dictionary key is the defined fieldname in the colordisplay instance.
                {'TE': {'value': '4C', 'fg': 2, 'bg': None, 'title': 'temperature', 'desc': '', 'numeric': 4, 'unit': 'C'}, 
                 'DP': {'value': '1C', 'fg': None, 'bg': None, 'title': 'dewpoint', 'desc': '', 'numeric': 1, 'unit': 'C'}, 
                 'RD': {'value': '0.0mm', 'fg': None, 'bg': None, 'title': 'rain', 'desc': '', 'numeric': 0, ... """
        self.Refresh() # Update from the web if needed.
        dictionary = self.CurrentMeasures() # Get the current values, formatting and color coding is calculated here too, no need to do it again.
        for key, details in dictionary.items(): # Go through each field in turn.
            windowhandle.FieldValue(key,details['value']) # Update any field with the dictionary defined values.
            if details['fg'] != None: # Only change display colour if there's reason.
                windowhandle.FieldColor(key,details['fg'],details['bg'])
            # Also handle some exceptions that need specific processing.
            if key == 'SI': # Update SeeingIndex description too.
                windowhandle.FieldValue('SID',details['desc'])
                # Copy color from SI to SID field too.
                windowhandle.CopyFieldColor('SI','SID')
            if key == 'PI': # Update PickeringIndex description too.
                windowhandle.FieldValue('PID',details['desc'])
                windowhandle.CopyFieldColor('PI','PID')
            if key == 'WA': # Convert wind angle into compass point.
                windowhandle.FieldValue('WC',self.CompassPoint(int(details['value'].replace('deg',''))))
        return True

    def GetMeasure(self,measurename): # Return the current value of a measure from downloaded data. 
        """ Return a measure from the downloaded data. 
            eg: GetMeasure('winddirection'). 
            
            Parameters -----------------------------------------
            measurename: The Metcheck JSON name of the measurement. eg 'temperature'
            
            Outputs --------------------------------------------
            Always returns a string representation of the current measure value. 
            This does NOT apply formatting, see the FormatValue() method if you require formatting. """
        self.Refresh() # Update from the web if needed.
        dictionary = self.CurrentMeasures() # Get the current values as a dictionary.
        result = ''
        for _, details in dictionary.items(): # Find the measure.
            if details['title'] == measurename:
                result = str(details['value'])
                break
        return result

    def TextToFloat(self,text) -> float: # Convert text to float.
        """ Convert a character string into a FLOAT value.
            Returns None if it can't be done. """
        try:
            a = float(text)
        except ValueError:
            a = None
        return a
    
    def SelectColor(self,key,value): # Choose color based upon key and value.
        """ Forecast values can have colors associated with them. 
            This calculates the appropriate color to assign to a value.
            Parameters -------------------------------------------------
            key: Metcheck JSON name of the measure. eg 'temperature'
            value: Metcheck VALUE from the JSON file. eg '2'
            
            Uses self.MeasureColors as a data source...
                self.MeasureColours = {
                    'seeingIndex': {'0': textcolor.RED, '1': textcolor.RED, '2': textcolor.ORANGE1, 
                                    '3': textcolor.ORANGE1, '4': textcolor.ORANGE1, '5': textcolor.YELLOW, 
                                    '6': textcolor.YELLOW, '7': textcolor.LIGHTGREEN, '8': textcolor.LIGHTGREEN, 
                                    '9': textcolor.GREEN, '10': textcolor.GREEN},
                    'temperature': {-100: textcolor.PURPLE, -30: textcolor.MAGENTA, -20: textcolor.BLUE, 
                                    -10: textcolor.CYAN, 0: textcolor.GREEN, 15: textcolor.LIGHTGREEN, 
                                    20: textcolor.YELLOW, 25: textcolor.ORANGE1, 30: textcolor.RED},
                    'lowcloud': percentage_low_good, ...
            """ 
        # Colour the translation.
        sel_color = None # No colour selected.
        dval = str(value)
        dfloat = self.TextToFloat(dval) # Convert to a float too if possible. # Easier to find 'nearest match' in incomplete lists.
        if key in self.MeasureColours: # There are colors defined for this forecast measure (such as temperature).
            if value in self.MeasureColours[key]: # Exact match, value can be coloured.
                sel_color = self.MeasureColours[key][value] # Note the colour selected.
            elif dfloat != None: # No precise match, try range match.
                for ckey, cval in self.MeasureColours[key].items(): # Try the range of colours in the dictionary looking for nearest lowest match.
                    cFloat = self.TextToFloat(ckey) # Convert values to float for numeric comparison.
                    if cFloat != None and cFloat <= dfloat: # Use the closest colour <= the value.
                        sel_color = cval # Note the colour selected.
        return sel_color

    def FormatValue(self,key,value): # Apply formats to each value.
        """ Forecast values can have formats associated with them. 
            This calculates the appropriate formatted version of a value.
            The optional formatting in MeasureTranslation must work with the Python .format() method.
            - eg   '{0}%'  would turn '2' into '2%'
            
            Parameters --------------------------------------------------------------------
            key : The metcheck measure name. Eg 'temperature'.
            value : The metcheck value. Eg '2'.
            
            MeasureTranslation contains a dictionary in this format...

            {'seeingIndex': {'desc': 'Seeing index', '0': 'Worst', '1': 'Terrible', ...
                             'pattern': None, 'fieldnames': ['SI']}, 
             'pickeringIndex': {'desc': 'Pickering seeing', '0': 'Very poor', '1': 'Very poor', .... 

            Outputs -----------------------------------------------------------------------
            dval : Formatted display value for the measure. eg "2C"

            """
        # Format the value, adding UOM etc.
        dkey = str(key) # Ensure key is a string. (This is the forecast measure eg 'temperature')
        dval = str(value) # Default value string. (This is the forecast value eg 2.4)
        transvalue = self.MeasureTranslation.get(dkey,{}) # Get the translation entry for the key if it exists. Tells us the formatting required.
        pattern = transvalue.get('pattern',None) # This pattern will format the value in the display.
        if pattern != None and len(pattern) > 0: # The pattern is valid.
            dval = str(pattern).format(value) # Format the display string for the value.
        return dval

    def Refresh(self): # Update caches with latest data (from disc or online)
        """ Use the 'requests' module to request the forecast from www.metcheck.com.
            The result is returned as a JSON object, and stored as a Python dictionary.
            This requests the ASTRO and CIVIL forecasts. There is useful info in both.

            Received data is in this structure.... we're interested in the list of 'forecast' entries.
            {
                "metcheckData": {
                    "forecastLocation": {
                        "forecast": [
                            {
                                "temperature": "10",
                                "dewpoint": "6",
                                "rain": "0.000",
                                "freezinglevel": "3300",
                                "uvIndex": "0",
                                "totalcloud": "0",
                                "lowcloud": "0",

            """
        r = False # We won't download fresh data unless there's a good reason for it.
        upr = False # Should we update the permanent record with refreshed data from the online source?
        if self.Timer.Due(): r = True # OK to refresh.
        if self.AstroResult == {}: r = True # OK to refresh.
        if self.CivilResult == {}: r = True # OK to refresh.
        if self.UseWeatherService != True: # *Q* Controlled externally by Parameters.UseWeatherService
            r = False # NOT OK to refresh.
            self.Log("metcheck_handler.Refresh(): self.UseWeatherService is False. Not polling remote weather service.",terminal=False)
        if r: # We should refresh.
            # Can we use the caches?
            self.LoadCaches() # If the disc cache of the data exists and is recent enough, this will load from disc instead of web service.
            if self.AstroResult != {}:
                self.Log("metcheck_handler.Refresh(): Astro forecast taken from disc cache.",terminal=False)
            if self.CivilResult != {}:
                self.Log("metcheck_handler.Refresh(): Civil forecast taken from disc cache.",terminal=False)
            
            WSOK = True # WebService needs to be proven.
            
            if self.AstroResult == {}: # No cached data available.
                self.Log('metcheck_handler.Refresh: Start: Astro product from web.',terminal=False)
                self.Log('metcheck_handler.Refresh:',self.AstroURL,terminal=False)
                try: # Trap and report errors, but don't allow the entire program to abort.
                    response = requests.get(self.AstroURL,headers=self.RequestHeader) # Try to retrieve the response from the remote server.
                    response.raise_for_status() # Check for errors in the request.
                    self.AstroResult = response.json() # Convert the response into a dictionary. 
                    #self.Log(str(self.AstroResult),terminal=False)
                    # Cache the response on disc to save web calls.
                    with open(self.AstroCacheFilename,'w') as f:
                        json.dump(self.AstroResult,f,indent=4,default=str)
                    upr = True # We've loaded fresh data from online, append this to the permanent weather record.
                except HTTPError as e: # There was an HTTP error.
                    self.Log('metcheck_handler.Refresh Astro: HTTPError: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
                except Exception as e: # There was some other sort of error.
                    self.Log('metcheck_handler.Refresh Astro: Error: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
            else: self.Log('metcheck_handler.Refresh: Used cached Astro data.',terminal=False)
            
            if self.CivilResult == {}: # No cached data available.
                self.Log('metcheck_handler.Refresh: Start: Civil product from web.',terminal=False)
                self.Log('metcheck_handler.Refresh:',self.CivilURL,terminal=False)
                try: # Trap and report errors, but don't allow the entire program to abort.
                    response = requests.get(self.CivilURL,headers=self.RequestHeader) # Try to retrieve the response from the remote server.
                    response.raise_for_status() # Check for errors in the request.
                    self.CivilResult = response.json() # Convert the response into a dictionary. 
                    #self.Log(str(self.CivilResult),terminal=False)
                    # Cache the response on disc to save web calls.
                    with open(self.CivilCacheFilename,'w') as f:
                        json.dump(self.CivilResult,f,indent=4,default=str)
                    upr = True # We've loaded fresh data from online, append this to the permanent weather record.
                except HTTPError as e: # There was an HTTP error.
                    self.Log('metcheck_handler.Refresh Civil: HTTPError: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
                except Exception as e: # There was some other sort of error.
                    self.Log('metcheck_handler.Refresh Civil: Error: ' + str(e),level='warning',window=True,terminal=False)
                    WSOK = False
            else: self.Log('metcheck_handler.Refresh: Used cached Civil data.',terminal=False)
            self.WebServiceOK = WSOK
            self.Log('metcheck_handler.Refresh: Done. WebServiceOK:',self.WebServiceOK,terminal=False)
            self.ForecastTable() # Prepare a matrix table of times and values. # Calculated values may be incomplete if target instances missing.
            if upr: self.PermanentRecord() # Append the weather readings to a permanent record of weather measurements.

    def PermanentRecord(self): # Append current measures to a permanent disc file.
        """ Call this to store a permanent record of the weather measurements.
            This transposes the ForecastMatrix table into timeslot specific rows 
            and exports it as a CSV file for permanent reference.

            There will be duplicates in the resulting file, created by overlapping 
            time slots in successive refreshes.
            This method does not attempt to resolve those. """
        # Write the ForecastTable entries to disc.
        # Use 
        # self.MatrixKeys = [] # List of data values available.
        # self.MatrixDates = [] # List of timestamps available.
        # self.MatrixDatetimes = [] # List of equivalent python datetime timestamps available.
        # self.ForecastMatrix = [r][c] [r] = List of values. [c] = Time slot each value represents.
        self.Log("metcheck_handler.PermanentRecord(): Begin",terminal=False)
        ExtractDT = metcheck_handler.VERSION + "\t" + str(self.NowUTC()) + "\t" # Fixed value for each line exported.
        if not os.path.exists(self.ArchiveFile): # New file.
            self.Log("metcheck_handler.PermanentRecord(): Create CSV file",self.ArchiveFile,terminal=False)
            line = 'Version\tExtracted\t' # Fixed value pre-pended to each exported data line.
            for mk in self.MatrixKeys:
                line += mk + "\t"
            line += "\n"
            with open(self.ArchiveFile,'w') as f:
                f.write(line)
        self.Log("metcheck_handler.PermanentRecord(): Append data",self.ArchiveFile,terminal=False)
        with open(self.ArchiveFile,'a') as f:
            for i in range(len(self.MatrixDatetimes)): # Go through the data one time column at a time. 
                line = ExtractDT # Start with standard initial data columns for each line.
                for row in self.ForecastMatrix:
                    line += str(row[i]) + "\t" # Pull the weather value for the given timeslot.
                line += "\n"
                f.write(line)
        self.Log("metcheck_handler.PermanentRecord(): End",terminal=False)
        return True
        
    def FileAge(self,filename): # Return file age (seconds).
        """ How many seconds old is a file? """
        if os.path.exists(filename): # File exists.
            mtime = os.path.getmtime(filename)
            td = datetime.now() - datetime.fromtimestamp(mtime)
            result = int(td.total_seconds())
        else: # No such file, so no result.
            result = None
        return result

    def LoadCache(self,filename): # Load cache from disc.
        """ Load a single cache if available and recent enough. """
        result = {} # Return empty cache.
        if os.path.exists(filename):
            fa = self.FileAge(filename)
            self.Log("metcheck_handler.LoadCache:",filename,fa,"seconds old",terminal=False)
            if fa < self.MaxCacheFileAge: # 2 * 60 * 60: # Only use the cache if younger than this (seconds).
                with open(filename,'r') as f:
                    self.Log("metcheck_handler.LoadCache: Loading Cache: " + filename,terminal=False)
                    result = json.load(f) # Overwrite the default parameter values with anything from file.
        else:
            self.Log("metcheck_handler.LoadCache:",filename,"cache does not exist.",terminal=False)
        return result

    def CompassPoint(self,value,points=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']): # Convert angle to cardinal point.
        """ Convert a degree value into a compass point.
            Default is 16 point compass.
            8 and 4 point compass can be generated by changing the points parameter.
            points=['N','E','S','W']
            or
            points=['N','NE','E','SE','S','SW','W','NW']             . """
        locn = int(round((value / 360) * len(points),0)) % len(points)
        return points[locn]

    def LoadCaches(self): # Load caches from disc.
        """ If disc caches of data are available and recent enough, load them instead of downloading from the web. """
        self.AstroResult = self.LoadCache(self.AstroCacheFilename)
        self.CivilResult = self.LoadCache(self.CivilCacheFilename)

    def CalculateLightlevel(self): # Calculate daylight level for each timeslot.
        """ Calculate lightlevel measures for each timeslot. """
        r = self.MatrixKeys.index('lightLevel') # Which row are we filling?
        if self.SunTarget != None:
            for c,matrixdate in enumerate(self.MatrixDatetimes): # Go through each timeslot column in turn.
                t = self.SunTarget.Datetime2Ts(matrixdate) # Convert to skyfield time type.
                value = self.SunTarget.TwilightLevel(time=t)[:2] # 1st 2 characters of twilight level.
                if value == 'as': value = 'astro'
                elif value == 'ci': value = 'civil'
                elif value == 'na': value = 'naut'
                elif value == 'ni': value = 'night'
                elif value == 'da': value = 'day'
                else: value = 'None'
                self.ForecastMatrix[r][c] = value # Populate column.

    def CalculateMoonlight(self): # Calculate moonlight level for each timeslot.
        """ Calculate moonlight measures for each timeslot. """
        r = self.MatrixKeys.index('moonLight') # Which row are we filling?
        if self.MoonTarget != None:
            for c,matrixdate in enumerate(self.MatrixDatetimes): # Go through each timeslot column in turn.
                t = self.MoonTarget.Datetime2Ts(matrixdate) # Convert to skyfield time type.
                _, malt = self.MoonTarget.AzAltDegrees(time=t) # Moon altitude.
                if malt < 0: # Moon is not visible.
                    value = '0'
                else:
                    value = str(round(self.MoonTarget.MoonFull(time=t))) # % fullmoon visible.
                self.ForecastMatrix[r][c] = value # Populate column.

    def CalculateFogrisk(self): # Calculate estimated fog risk for each timeslot.
        """ Calculate fog risk for weather timeslot.
            This isn't an official calculation, just an estimate based upon various discussions of 'fog risk' found online.
            It could change in the future if a more recognised calculation is found. """
        r = self.MatrixKeys.index('fogRisk') # Which data row are we filling with fogRisk values?
        for c in range(len(self.MatrixDates)): # Go through each timeslot column in turn.
            score = 0 # Calculate a score 0 - 9 for the risk of fog.
            # 0-3 points for approaching dewpoint.
            t2 = self.MatrixKeys.index('dewpoint')
            temp = float(self.ForecastMatrix[self.MatrixKeys.index('temperature')][c]) # Get temperature
            dewp = float(self.ForecastMatrix[self.MatrixKeys.index('dewpoint')][c]) # Get dewpoint
            dpd = temp - dewp # How close is temperature to dewpoint?
            if dpd < 1: score += 3
            elif dpd < 3: score += 2
            elif dpd < 4: score += 1
            # 0-3 points for humidity
            humid = float(self.ForecastMatrix[self.MatrixKeys.index('humidity')][c]) # Get humidity
            if humid >= 85: score += 3
            elif humid >= 75: score += 2
            elif humid >= 65: score += 1
            # 0-3 points for wind speed
            speed = float(self.ForecastMatrix[self.MatrixKeys.index('windspeed')][c]) # Get windspeed
            if speed < 5: score += 3
            elif speed < 10: score += 2
            elif speed < 15: score += 1
            self.ForecastMatrix[r][c] = str(score) # Populate column (all values are 'str' type).

    def IsInt(self,text): # Will string convert to integer?
        """ Return True if string is integer. """
        try:
            _ = int(text)
            return True
        except ValueError:
            return False
        
    def IsFloat(self,text): # will string convert to float?
        """ Return True if string is float. """
        try:
            _ = float(text)
            return True
        except ValueError:
            return False

    def ActiveEntry(self): # Column of currently active data.
        """ Return the column number from the forecast matrix that is currently active! """
        result = 0
        tnow = self.NowUTC()
        for i,tempDT in enumerate(self.MatrixDatetimes):
            if tempDT <= tnow: result = i # This column is valid.
            else: break # All future columns can be ignored.
        return result
        
    def ActiveDatetime(self): # Datetime of currently active slot.
        """ Return the datetime from the forecast matrix that is currently active! """
        return self.MatrixDatetimes[self.ActiveEntry()]
        
    def RolloverDatetime(self): # Datetime of next slot from currently active one.
        """ Return the datetime from the forecast matrix for the next slot after the currently active one. """
        return self.MatrixDatetimes[self.ActiveEntry() + 1]
    
    def BuildKeyLists(self): # Build key lists for the forecast table. 
        """
        Build key lists for the forecast table. 
        """
        self.MatrixKeys = [] # List of measures available.
        self.MatrixDates = [] # List of timestamps available.
        self.MatrixDatetimes = [] # List of equivalent python datetime timestamps available.
        # Identify all the DATES and MEASURES available in the forecasts.
        # Civil forecast.
        forecast = self.CivilResult['metcheckData']['forecastLocation']['forecast'] # An array of sub dictionaries.
        for dictionary in forecast: # Check each sub-dictionary in turn. Each represents an hourly forecast.
            for key,value in dictionary.items(): # Check each item in the sub-dictionary.
                if not key in self.MatrixKeys: self.MatrixKeys.append(key) # Add to the list of measures available.
                if key == 'utcTime': # Add to the list of timeslots available. "utcTime": "2023-06-14T05:00:00.00"
                    if not value in self.MatrixDates: 
                        self.MatrixDates.append(value)
                        self.MatrixDatetimes.append(self.UTCToDatetime(value)) # Convert to datetime type too.
        # Astro forecast.
        forecast = self.AstroResult['metcheckData']['forecastLocation']['forecast'] # An array of sub dictionaries.
        for dictionary in forecast: # Check each sub-dictionary in turn. Each represents an hourly forecast.
            for key,value in dictionary.items(): # Check each item in the sub-dictionary.
                if not key in self.MatrixKeys: self.MatrixKeys.append(key) # Add to the list of measures available.
                if key == 'utcTime': # Add to the list of timeslots available. "utcTime": "2023-06-14T05:00:00.00"
                    if not value in self.MatrixDates: 
                        self.MatrixDates.append(value)
                        self.MatrixDatetimes.append(self.UTCToDatetime(value)) # Convert to datetime type too.
        # Append values that will be calculated by this program.
        self.MatrixKeys.append('lightLevel') # A light level will be calculated based upon the sun's location.
        self.MatrixKeys.append('moonLight') # Is the moon visible, and if so how bright?
        self.MatrixKeys.append('fogRisk') # Assessment of fog/mist risk.

        self.MatrixDates.sort() # Make sure dates are in ascending sequence.
        self.MatrixDatetimes.sort() # Make sure datetimes are in ascending sequence.
        
        # In the log file, show what data has been produced.
        self.Log('metcheck_handler.BuildKeyLists: MatrixKeys:',self.MatrixKeys,terminal=False)
        self.Log('metcheck_handler.BuildKeyLists: MatrixDates:',self.MatrixDates,terminal=False)
        self.Log('metcheck_handler.BuildKeyLists: MatrixDatetimes:',self.MatrixDatetimes,terminal=False)
        
    def ForecastTable(self): # Populate the key lists and forecast matrix.
        """ Use the metcheck data stored in CivilResult and AstroResult dictionaries to generate a
            matrix of forecast elements against time. This is used in other routines to retrieve
            weather values for specific timeslots.
            
            {
                "metcheckData": {
                    "forecastLocation": {
                        "forecast": [
                            {
                                "temperature": "10",
                                "dewpoint": "6",
                                "rain": "0.000",
                                "freezinglevel": "3300",
                                "uvIndex": "0",
                                "totalcloud": "0",
                                "lowcloud": "0",
                        ...
                        
            It calculates various lists.
            self.MatrixKeys = A list of the different weather measurements available (windspeed,temperature etc.)
            self.MatrixDates = A list of the times that measurements are available for.
            self.MatrixDatetimes = A list of the times that measurements are available for in python datetime datatype.
            self.ForecastMatrix = A matrix of times vs measurements for the forecast.
                                  Each 'line' represents a specific measurement (eg temperature).
                                  The 'line' contains a list of values for each timeslot the forecast provides.
                                  You can access a specific measurement by referencing self.ForecastMatrix['temperature'][datetimecolumn]
                                  (You can identify datetimecolumn by examining self.MatrixDates or self.MatrixDatetimes.)

        """

        #self.MatrixKeys = [] # List of data values available.
        #self.MatrixDates = [] # List of timestamps available.
        #self.MatrixDatetimes = [] # List of equivalent python datetime timestamps available.
        
        if self.CivilResult == None or self.CivilResult == {}: # No data available.
            self.Log('metcheck_handler.ForecastTable: No self.CivilResult values available.',terminal=False)
            return
        if self.AstroResult == None or self.AstroResult == {}: # No data available.
            self.Log('metcheck_handler.ForecastTable: No self.AstroResult values available.',terminal=False)
            return

        self.BuildKeyLists() # Create empty matrix for the known dates and measures.
        
        # Create empty matrix for the known dates and measures.
        self.Log('metcheck_handler.ForecastTable: Create Matrix...',terminal=False)
        self.ForecastMatrix = [[' ' for d in self.MatrixDates] for k in self.MatrixKeys] # Create matrix to hold all values vs dates. [measure][date]
        
        # Pull all the details out of the Civil forecast.
        self.Log('metcheck_handler.ForecastTable: Pull civil data...',terminal=False)
        forecast = self.CivilResult['metcheckData']['forecastLocation']['forecast'] # An array of sub dictionaries.
        for dictionary in forecast:
            if not dictionary['utcTime'] in self.MatrixDates: continue # Skip this entry.
            c = self.MatrixDates.index(dictionary['utcTime']) # Which column are we filling?
            for key,value in dictionary.items():
                if not key in self.MatrixKeys: continue # Skip this item.
                r = self.MatrixKeys.index(key) # Which row are we filling?
                self.ForecastMatrix[r][c] = value # Populate column.
        # Append all the details out of the Astro forecast.
        self.Log('metcheck_handler.ForecastTable: Pull astro data...',terminal=False)
        forecast = self.AstroResult['metcheckData']['forecastLocation']['forecast'] # An array of sub dictionaries.
        for dictionary in forecast:
            if not dictionary['utcTime'] in self.MatrixDates: continue # Skip this entry.
            c = self.MatrixDates.index(dictionary['utcTime']) # Which column are we filling?
            for key,value in dictionary.items():
                if not key in self.MatrixKeys: continue # Skip this item.
                r = self.MatrixKeys.index(key) # Which row are we filling?
                self.ForecastMatrix[r][c] = value # Populate column.
        
        # Calculate additional data points that metcheck does not provide.
        # 'lightLevel' indicates the level of sky brightness.
        self.Log('metcheck_handler.ForecastTable: Calculate light levels...',terminal=False)
        self.CalculateLightlevel()
        # 'moonLight' indicates interference of the moon.
        self.Log('metcheck_handler.ForecastTable: Calculate moonlight...',terminal=False)
        self.CalculateMoonlight()
        # 'fogRisk' indicates risk of mist/fog forming even if cloudless sky.
        self.Log('metcheck_handler.ForecastTable: Calculate fogrisk...',terminal=False)
        self.CalculateFogrisk()
                
        # Convert datatypes. Convert values from STR to more appropriate datatypes.
        self.Log('metcheck_handler.ForecastTable: Convert datatypes...',terminal=False)
        for r in range(len(self.ForecastMatrix)): # [r][c] [r] = Values (row), [c] = Times (column)
            if self.MatrixKeys[r] == 'timestamp': continue # Don't bother converting timestamp data, it's already done, and not a string!
            for c in range(len(self.ForecastMatrix[r])):
                v = self.ForecastMatrix[r][c] # Get raw value from matrix.
                vlist = v.split(':') # Prepare list of ':' separated elements.
                vlen  = len(vlist) # How many ':' separated elements are there?
                if self.IsInt(v): v = int(v) # Can we convert to integer?
                elif self.IsFloat(v): v = float(v) # Can we convert to float?
                elif vlen == 3: # Can we convert to datetime?
                    #v = datetime.fromisoformat(v.split('.')[0] + '+00:00') # Convert from ISO string into datetime.
                    v = self.UTCToDatetime(v) # Convert from ISO string into datetime.
                    v = v.replace(tzinfo=pytz.UTC) # Clarify it's UTC timezone.
                elif vlen == 2: # Can we convert to time?
                    v = datetime_time(hour=int(vlist[0]),minute=int(vlist[1]),tzinfo=pytz.UTC) # Convert to time datatype - *Q* not sure that this is UTC though!
                self.ForecastMatrix[r][c] = v

        self.Log('metcheck_handler.ForecastTable: Arrange rows...',terminal=False)
        # Move weekday to first row.
        i = self.MatrixKeys.index('weekday') # This is the ROW for the utcTime value. We'll pull it out of the list and make it the first entry.
        temprow = self.MatrixKeys.pop(i) # Update the list of key names.
        self.MatrixKeys.insert(0,temprow)
        temprow = self.ForecastMatrix.pop(i) # Update the list of values.
        self.ForecastMatrix.insert(0,temprow)
        # Move utcTime to first row. This shunts weekday to 2nd row.
        i = self.MatrixKeys.index('utcTime') # This is the ROW for the utcTime value. We'll pull it out of the list and make it the first entry.
        temprow = self.MatrixKeys.pop(i) # Update the list of key names.
        self.MatrixKeys.insert(0,temprow)
        temprow = self.ForecastMatrix.pop(i) # Update the list of values.
        self.ForecastMatrix.insert(0,temprow)

    def SelectColumns(self): # Decide which columns to show.
        """ Decide which data columns to show. """
        ColNum = self.ActiveEntry() # First column. #
        ColCount = 0 # How many columns have we selected so far?
        ColInc = 1 # How many columns do we advance for the next selection?
        Columns = []
        while True:
            Columns.append(ColNum)
            ColCount += 1
            if ColCount % 6 == 0: ColInc += 1 # Every 6 columns, make the time increments larger.
            ColNum += ColInc # Move on to the next column.
            if ColNum > len(self.MatrixDatetimes): break # Off the list.
        self.Log("metcheck_handler.SelectColumns: Chose",Columns,terminal=False)
        return Columns

    def ObservationOpportunities(self,cloudlimit=10,moonlimit=10,gustlimit=25): # Display upcoming observation opportunities.
        """ Go forward through the available forecast and list all the 
            upcoming observation opportunities. 
            
            A good opportunity is :-
                - Astronomical twilight / nighttime.        self.ForecastMatrix['lightLevel'][timeslot]
                - <= 10% total cloud.                       self.ForecastMatrix['totalcloud'][timeslot]
                - <= 10% moon.                              self.ForecastMatrix['moonLight'][timeslot]
                - <= 20mph wind gusts.                      self.ForecastMatrix['windgustspeed'][timeslot]



            Period start (UTC)     Light   Cloud    Moon      Gust  Quality
            2023-11-05 18:00:00    astro      0%      0%     13mph     GOOD
            2023-11-05 19:00:00    night      0%      0%     13mph     GOOD
            2023-11-05 20:00:00    night      0%      0%     13mph     GOOD
            2023-11-05 21:00:00    night      4%      0%     13mph     GOOD
            
            2023-11-06 19:00:00    night      7%      0%     15mph     GOOD
            
            2023-11-07 23:00:00    night      5%      0%     15mph     GOOD
            
            2023-11-08 00:00:00    night      3%      0%     13mph     GOOD
            2023-11-08 01:00:00    night      5%      0%     15mph     GOOD

                
            """
        if self.MoonTarget == None or self.SunTarget == None: # Not enough information available.
            self.Log("metcheck_handler.ObservationOpportunities(): No Skyfield targets available.",terminal=True)
            return 
        print(textcolor.fgbgcolor(self.TextFG,self.TextBG,"Period start (UTC)     Light   Cloud    Moon      Gust  Quality"))
        lli = self.MatrixKeys.index('lightLevel')
        tci = self.MatrixKeys.index('totalcloud')
        mli = self.MatrixKeys.index('moonLight')
        wgi = self.MatrixKeys.index('windgustspeed')
        next_d = None # Put a blank line whenever there's a break in an observation window.
        for i,d in enumerate(self.MatrixDatetimes):
            lightlevel = self.ForecastMatrix[lli][i]
            totalcloud = self.ForecastMatrix[tci][i]
            moonlight = self.ForecastMatrix[mli][i]
            windgustspeed = self.ForecastMatrix[wgi][i]
            quality = 'BAD'
            if lightlevel in ['astro','night'] and totalcloud <= cloudlimit and moonlight <= moonlimit and windgustspeed <= gustlimit:
                quality = 'GOOD'
                if next_d != None and next_d != d: print(" ") # We've a break in an observation window.
                print(textcolor.fgbgcolor(self.TextFG,self.TextBG, str(d).split('+')[0]),
                      textcolor.fgbgcolor(self.TextFG,self.TextBG, str(lightlevel).rjust(8)),
                      textcolor.fgbgcolor(self.TextFG,self.TextBG, str(totalcloud).rjust(6) + "%"),
                      textcolor.fgbgcolor(self.TextFG,self.TextBG, str(moonlight).rjust(6) + "%"),
                      textcolor.fgbgcolor(self.TextFG,self.TextBG, str(windgustspeed).rjust(6) + "mph"),
                      textcolor.fgbgcolor(self.TextFG,self.TextBG, quality.rjust(8)))
                if (i + 1) <= len(self.MatrixDatetimes): # Calculate when this forecast ends.
                    next_d = self.MatrixDatetimes[i + 1]
                else:
                    next_d = None
        
    def TwelveHourForecast(self,terminalwidth): # Display color coded forecase matrix to the terminal.
        """ Display a color coded forecast matrix to the terminal.
            The matrix adapts to the width of the terminal screen.
            The forecast is produced in 1hr timeslots for the immediate future, then the timeslots gradually increase. """
        print('')
        if self.ForecastMatrix == None: # No forecast yet.
            self.Log('metcheck_handler.TwelveHourForecast(): ForecastMatrix is not populated.',level='warning')
            return
        # Clip forecast to match available window space. # *Q* GetTerminalSize needs to come externally.
        if terminalwidth == None: terminalwidth = GetTerminalSize()[0] # How wide is the window?
        temp = terminalwidth - 21 # Remove label width.
        maxhours = temp // 12 # How many 12 character columns fit the window width?
        # Decide which columns of data to show.
        ColumnList = self.SelectColumns() # Select which forecast columns (times) to show. The further ahead, the more spaced out.
        ColumnList = ColumnList[:maxhours] # Clip the list to the available screen width.
        locstr = "lat:" + str(self.Lat) + " lon:" + str(self.Lon)
        print (textcolor.yellow('METCHECK.COM Observing conditions at ' + locstr + ' until ' + str(self.MatrixDatetimes[ColumnList[-1]]).split('+')[0] + ' UTC'))
        # ForecastMatrix is created when the Metcheck data is loaded. It's a matrix of time slots vs weather measurements.
        
        # Skip some fields.
        SkipFields = ['uvIndex','icon','iconName','dayOrNight','dayOfWeek']
        
        if self.MoonTarget == None: SkipFields.append('moonLight')
        if self.SunTarget == None: SkipFields.append('lightLevel')
        if len(self.MatrixDatetimes) > 0: statusline = 'Data downloaded ' + str(self.MatrixDatetimes[0]).split('+')[0] + ' UTC'
        else: statusline = 'No data available'
        
        for i,row in enumerate(self.ForecastMatrix): # Each row represents a single weather measurement across multiple timeslots.
            valuename = self.MatrixKeys[i] # The weather 'measure' for this row in the forecast matrix.
            if valuename in SkipFields: continue # Skip this measure.
            line = valuename.rjust(20)[-20:] + ' ' # Construct a line to display. Start each line with measure name.
            trimmedrow = [row[selcol] for selcol in ColumnList] # Only select the times (columns) that we have selected earlier.
            for e in trimmedrow: # Construct the display line with a column for each timeslot.
                f = e # Default measurement value.
                f = self.FormatValue(valuename,e) # Format the measure value.
                # Some exceptional formatting to fit the column space available.
                if valuename == 'utcTime': # Compress a UTC timestamp string to MM.DD HH:MM
                    f = str(e.month).rjust(2,'0') + '.' + str(e.day).rjust(2,'0') + ' ' + str(e.hour).rjust(2,'0') + ':' + str(e.minute).rjust(2,'0')
                elif valuename in ['sunrise','sunset']: # Compress to HH:MM
                    f = str(e.hour).rjust(2,'0') + ':' + str(e.minute).rjust(2,'0')
                column_e = str(f).rjust(11)[-11:] + ' ' # 11 characters per column.
                color = self.SelectColor(valuename,e) # Is there any specific color associated with this measure?
                if color != None: column_e = textcolor.fgbgcolor(color,self.TextBG,column_e) # color code the value.
                else: column_e = textcolor.fgbgcolor(self.TextFG,self.TextBG,column_e) # Default colors.
                line += column_e # Add the measure column to the display line.
            print(line) # Print the line of measure columns.
        print(statusline) # Summarise the state of the data.
        print(' ') # Blank line to finish.

    def Translate(self,separator=': ',color=False): # Return the combined results of TranslateAstro and TranslateCivil.
        """ Return the combined results of TranslateAstro and TranslateCivil.
            Value is returned as a list of text lines. """
        temp = self.CurrentMeasures() # Get a dictionary of weather measurements and their values.
        result = [] # Start with an empty return list.
        prevline = '' # There are some duplicates in the dictionary, filter them out.
        for key,details in temp.items(): # Go through each weather measurement in turn.
            cvalue = str(details['value']) # Get the measurement value.
            if color: # The value should be colored.
                fg = details['fg'] # Get the foreground color.
                bg = details['bg'] # Get the background color.
                if bg != None: # Only colour the measurement value if valid colors are available.
                    cvalue = textcolor.fgbgcolor(fg,bg,str(details['value']))
            line = details['title'] + separator + cvalue
            if line != prevline: # Only return unique entries.
                result.append(line) # Add to the return list.
                prevline = line
        return result
        
class metcheckdashboard(): # Example terminal UI for metcheck_handler
    """
    Example terminal UI for metcheck_handler
    """
    
    def __init__(self,logger=None,cachedir='/home/pi/pilomar/data/',enabled=True,suntarget=None,moontarget=None):
        """
        """
        from textcolor import colordisplay, keyboardscanner, textcolor
        self.keyboard = keyboardscanner()
        self.RefreshTimestamp = None
        self.RolloverDatetime = None
        self.ParameterFileName = None
        self.ClockOffset = None
        self.Lat = 0.0
        self.Lon = 0.0
        self.ParameterFileName = cachedir + "pilomar_params.json" # Default parameter filename.
        self.establish_location()
        self.mch = metcheck_handler(logger=logger,cachedir=cachedir,enabled=enabled,lonval=self.Lon,latval=self.Lat,suntarget=suntarget,moontarget=moontarget) # Create metcheck data instance

    def NowUTC(self,real=False) -> datetime: # Return current timestamp in UTC timezone.
        """ Get system clock as UTC (timezone aware) 
            Microcontroller and Skyfield are operated in UTC vales. 
            All clock-times used in this program use the UTC timestamped clock.
            This should be the only reference to datetime.now() method in the entire
            program. All other uses should refer to this NowUTC() function.
            real=True means that no time offset is applied, you get the true realtime clock value.
            real=False means that any time offset is applied, making the clock run at some other point in time.
            NOTE: Changing the clock offset for a live feed from the internet probably results in mismatched data!
            """
        dt = datetime.now(timezone.utc) # Offset supported.
        if real == False and self.ClockOffset != None: # Can apply time offset.
            dt = dt + timedelta(seconds=self.ClockOffset)
        return dt
    
    def Display(self): # Refresh the data and display.
        """
        """
        print(textcolor.clearscreen()) # Wipe the display clean.
        self.mch.Refresh() # Update from the web if needed.
        self.RefreshTimestamp = self.NowUTC()
        self.RolloverDatetime = self.mch.RolloverDatetime() # What's the datetime (UTC) of the current data column?
        self.mch.TwelveHourForecast(terminalwidth=textcolor.terminalsize()[0])
        print("Refreshed:",str(self.RefreshTimestamp).split('.')[0],"Rollover:",str(self.RolloverDatetime).split('+')[0])
        print(textcolor.cyan("Press 'x' to exit, 'r' to refresh"))
        
    def io_loop(self): # IO Loop to run the display and react to the keyboard.
        """
        """
        while True:
            now = self.NowUTC()
            keypress = self.keyboard.Check().lower()
            if keypress != "":
                if keypress in ["x"]: break
                elif keypress == 'r': pass # Trigger refresh.
                else: continue # Unrecognised. Start new loop.
                self.Display() # Update display
            elif (now - self.RefreshTimestamp).total_seconds() > 15*60: # Refresh every 15 minutes.
                self.Display()
            elif now > self.RolloverDatetime: # First column has expired. Refresh anyway.
                self.Display()
            time.sleep(0.25)
            
    def establish_location(self): # Where is the user?
        """
        If startup parameters specify location (lat/lon) use that.
        Else if parameter file exists, use that.
        Else default to 0,0
        """
        import sys
        import os
        run_args = sys.argv[1:] # Ignore 1st argument which is this program name.
        for i in run_args:
            if i.startswith('?') or i.startswith('h'): # Help
                print(textcolor.yellow("HELP"))
                print(" paramfile={pilomar parameterfile name}")
                print(" lat={latitude degrees}")
                print(" lon={longitude degrees}")
                exit()
            if i.startswith('paramfile='): # Specify parameter filename to use.
                # Alternative parameter files are useful for test/dev/debug and also for
                # supporting alternative configurations.
                self.ParameterFileName = i.split('=')[1]
                print(textcolor.orange("Startup parameter file is:",self.ParameterFileName))
            elif i.startswith('lat='):
                self.Lat = float(i.split("=")[1])
            elif i.startswith('lon='):
                self.Lon = float(i.split("=")[1])
            else: print (textcolor.red('Ignored startup parameter "' + str(i) + '"'))
        if self.ParameterFileName != None: # If Pilomar parameter file exists, use that.
            if os.path.exists(self.ParameterFileName):
                with open(self.ParameterFileName,'r') as f:
                    param_dict = json.load(f)
                # Extract latitude degrees from parameter list.
                home_lat_str = param_dict.get('HomeLat','0.0 N')
                self.Lat = float(home_lat_str.split(" ")[0]) # Convert to float value.
                if home_lat_str.split(" ")[1] == "S": self.Lat = self.Lat * -1 # -ve for southern hemisphere in Skyfield.
                # Extract longitude degrees from parameter list.
                home_lon_str = param_dict.get('HomeLon','0.0 E')
                self.Lon = float(home_lon_str.split(" ")[0]) # Convert to float value.
                if home_lon_str.split(" ")[1] == "W": self.Lon = self.Lon * -1 # -ve for southern hemisphere in Skyfield.
                print("From",self.ParameterFileName,"lat/lon",self.Lat,self.Lon)
        
if __name__ == "__main__": # Example display.
    from textcolor import textcolor
    import time
    print(textcolor.yellow("pilomarmetcheck..."))
    mcd = metcheckdashboard(logger=None,cachedir='/home/pi/pilomar/data/',enabled=True,suntarget=None,moontarget=None) # Create metcheck data instance.
    mcd.Display() # Initial display.
    mcd.io_loop() # Loop through updates and user input.
