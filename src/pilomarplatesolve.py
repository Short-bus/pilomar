# astrometry.net platesolver code.

"""
platesolve.py

Minimal, self-contained wrapper around astrometry.net's `solve-field`
for use on a Raspberry Pi with the HQ camera.

- No external Python deps beyond the standard library
- Uses `solve-field` installed on the system
- Parses the generated .wcs file to extract basic WCS info

Tested conceptually for wide-field lenses (e.g. 16mm, 50mm on IMX477).

Requires that pilomar project is installed.
Requires that astrometry.net is installed.
Requires that astrometry.net data files are installed.

sudo apt update
sudo apt upgrade
sudo apt install astrometry.net
sudo apt install astrometry-data-2mass-08-19
#sudo apt install astrometry-data-4206 astrometry-data-4207 astrometry-data-4208 \
#                 astrometry-data-4209 astrometry-data-4210 astrometry-data-4211 \
#                 astrometry-data-4212

"""

from pathlib import Path
#from typing import Optional, Dict
from pilomarlib import IsFloat,IsInt,TextToInt,TextToFloat,attributemaster # Import some helper classes.
from pilomaroscommand import oscommand # Pilomar's OS command executor.
from astropy.io import fits 
from pilomarimage import pilomarimage
from datetime import datetime, timedelta 
from pilomartrig import AngleToHMS, AngleToDMS
import math 
import numpy as np
import pandas 
import json

class PlateSolver(attributemaster):
    """
    Wrapper for astrometry.net library to perform platesolving on images captured by pilomar telescope.
    """

    def __init__(self,name,logger=None,pilomarsession=None,projectroot=None,parameterfile=None,filter_script='PrepForPlateSolving',script_source=None,debug=False):
        """
        Create instance of PlateSolver
        
        Parameters --------------------------------------
        name (str) : Name for the instance. (For debugging messages)
        logger (pilomarlog instance) : optional: Links to a pilomar logging mechanism.
        pilomarsession (pilomarsession instance) : optional : Links to a pilomarsession instance.
        projectroot (str) : Path to pilomar project root folder (ie '/home/pi/pilomar/')
        parameterfile (str) : Path to parameter file. Default will be assumed if not set.
        filterscript (str) : Name of pilomarimage filter to use for cleaning images. (Default is used if not set.)
        """
        self.Name = name 
        self.SetLogger(logger) # Inherited from attributemaster
        if projectroot == None:
            self.ProjectRoot = '/home/pi/pilomar' # Root of the pilomar project, can be changed at runtime or when instantiated.
        else:
            self.ProjectRoot = projectroot # Root of the pilomar project, can be changed at runtime or when instantiated.
        if parameterfile != None: self.ParameterFileName = parameterfile
        else: self.ParameterFileName = self.ProjectRoot + '/data/pilomar_params.json'
        self.TempDir = self.ProjectRoot + '/temp/' # Where are temporary files stored?
        self.FilterScript = filter_script # Name of PilomarImage filterscript to execute.
        self.ScriptSource = script_source # File containing filter scripts (uses pilomarimage defaults if missing).
        self.HipparcosCacheFile = self.ProjectRoot + '/data/hipparcos.pkl' 
        self.Session = pilomarsession # Link to parent session instance (Gives access to everything else in the session)
        self.OSCommand = oscommand(logger=logger) # Create OS Command executor. Pass handle to the 'log' method.
        self.osCmd = self.OSCommand.Execute # Shortcut point to the execution method which returns the output.
        self.osCmdCode = self.OSCommand.ExecuteCode # Shortcut point to the execution method which returns the termination code.
        self.DebugMode = debug # Activate additional development/debugging features.
        # Create and load PilomarParameters dictionary.
        self.ReadParameterFile(self.ParameterFileName)
        self.Reset()
        
    def Reset(self):
        """
        Reset any image and solution.
        """
        self.SolutionDict = {} # Processed dictionary of solution details.
        self.FitsHeader = {} # Intermediate dictionary of details from solver's FITS header.
        self.StarCount = 0 # How many stars in image.
        self.StarList = [] # x,y,r of each identified star.
        self.IdentityList = [] # Calculate list of RADEC locations based upon StarList.        
        self.HipparcosDf = None # Pandas dataframe of Hipparcos catalog.
        self.Image = None # Pilomarimage instance for the image being processed.
        self.OrigImageFile = None # The original image file on disc.
        self.ExifData = {} # No EXIF data loaded.
        self.SolveSeconds = 0 # Elapsed seconds for calculating the solution.

    def LoadHipparcosDf(self):    
        """
        Hipparcos catalog is loaded as Pandas dataframe. 
        The file is loaded from disc (self.HipparcosCacheFile), it is installed as part of the pilomar installation.
        """
        if self.HipparcosDf is None:
            self.HipparcosDf = pandas.read_pickle(self.HipparcosCacheFile)
            self.HipparcosDf["ra_rad"] = np.radians(self.HipparcosDf["ra_degrees"]) 
            self.HipparcosDf["dec_rad"] = np.radians(self.HipparcosDf["dec_degrees"]) 
            self.HipparcosDf["cos_dec"] = np.cos(self.HipparcosDf["dec_rad"])            
        self.Log("Hipparcos dataframe loaded",len(self.HipparcosDf),"stars from cache.",terminal=False)
        self.Log("Hipparcos dataframe contains",list(self.HipparcosDf.columns),"columns.",terminal=False)
        return True

    def NearestStar(self, ra_deg, dec_deg):
        """
        Return dictionary of the nearest star from the Hipparcos dictionary to any RADEC coordinates.
        """
        # Convert query point to radians
        ra_q  = np.radians(ra_deg)
        dec_q = np.radians(dec_deg)

        # Differences
        dra  = self.HipparcosDf["ra_rad"].values  - ra_q
        ddec = self.HipparcosDf["dec_rad"].values - dec_q

        # Small-angle spherical distance
        dist = np.sqrt((dra * np.cos(dec_q))**2 + ddec**2)

        # Index of closest star
        idx = np.argmin(dist)

        row = self.HipparcosDf.iloc[idx]
        return {
            "hip": row.hip,
            "name": row.label,
            "starname": row.starname,
            "distance_rad": dist[idx],
            "ra_degrees": row.ra_degrees,
            "dec_degrees": row.dec_degrees,
        }

    def FitsTableToDict(self,filename):
        """
        Convert a simple table in a binary fits header into a dictionary.
        Exports the file in json format too.
        """
        dictionary = {}
        with fits.open(filename) as hdul:
            table = hdul[1].data
            cols = table.columns.names
            for i,row in enumerate(table):
                try: # Not everything can convert this easily.
                    dictionary[i] = {col: row[col].item() for col in cols}
                except: # If it fails, what datatypes were we trying to convert?
                    #dictionary[i] = {col: str(type(row[col].item())) for col in cols}
                    dictionary[i] = {col: str(type(row[col])) for col in cols}
        filename += ".json"
        with open(filename,'w') as f:
            json.dump(dictionary, f,indent=4)
        return dictionary
        
    def RunSolveField(self,
                      image_path,
                      downsample = 2,
                      scale_low = None, # Optional
                      scale_high = None,
                      scale_units = "degwidth",
                      #timeout: int = 120,
                      hint_ra = None,    # --ra <deg> # Hint RA guess in degrees.
                      hint_dec = None, # --dec <deg> # Hint DEC guess in degrees.
                      hint_radius = None # --radius <deg> # Radius of guess in degrees.
                      ):
        """
        Run astrometrynet's solve-field utility on the given image and return the path to the .wcs file.

        scale_low / scale_high are optional hints:
          - scale_units = 'degwidth' means image width in degrees
          - for IMX477 + 16mm: ~40 deg, 50mm: ~13 deg
        """

            # -h, --help
            # -v, --verbose
            # --overwrite # Replace any existing output files.
            # --no-plots # Don't generate diagnostic images.
            # --dir <path> # Write all output to specific directory
            # --scale-units <units> # arcsecperpix / degwidth / arcminwidth / focal_mm
            # --scale-low <value> # Min value
            # --scale-high <value> # Max value
            # --ra <deg> # Hint RA guess in degrees.
            # --dec <deg> # Hint DEC guess in degrees.
            # --radius <deg> # Radius of guess in degrees.
            # --downsample <factor> # 2 and 4 can speed things up.
            # --objs <n> # Limit number of extracted sources.
            # --sigma <value> # Detection threshold
            # --uniformize <n> # Enforce uniform spatial distribution.
            # --parity pos|neg # Restrict image parity.
            # --no-verify # Skip verification stage, even weak solutions are accepted.
            # --new-fits <file> # Write new FITS with WCS.
            # --wcs <file> # Write WCS to specific file.
            # --corr <file> # Write matched star list to specific file.
            # --match <file> # Write matched catalog stars to specific file.
            # --rdls <file> # write RA/DEC list to extracted sources to specific file.
            # --solved <file> # Generate this file if solution found to specific file.
            # --index <n> # Solve with specific index number.
            # --index-xyls <file> # Use specific index file.
            
            # For 50mm lens recommendation is 
            #  --objs 80 # Brightest 80 stars.
            #  --uniformize 80 # Pick evenly spread across image.
            #  --sigma 8 # Strength of 'peak' identified as a star.

            # For 16mm lens recommendation is 
            #  --objs 120 # Brightest 120 stars.
            #  --uniformize 120 # Pick evenly across image.
            #  --sigma 6 # Strength of the 'peak' identified as a star.

        #cmd = "solve-field --overwrite --no-plots --downsample " + str(downsample)
        #cmd = "solve-field --overwrite --no-verify --downsample " + str(downsample)
        cmd = "solve-field --overwrite --no-plots --no-verify --downsample " + str(downsample)

        # Add scale hints if provided
        if scale_low is not None and scale_high is not None:
            cmd += " --scale-units " + str(scale_units)
            cmd += " --scale-low " + str(scale_low)
            cmd += " --scale-high " + str(scale_high)
            
        if hint_ra is not None: cmd += " --ra " + str(hint_ra)
        if hint_dec is not None: cmd += " --dec " + str(hint_dec)
        if hint_radius is not None: cmd += " --radius " + str(hint_radius)

        cmd += " " + str(image_path)
        #print("PlateSolver.RunSolveField(",self.Name,"): Command",cmd)

        templist = self.osCmd(cmd)
        cmd_filename = self.TempDir + "PlateSolver.output.txt" # Store command output.
        with open(cmd_filename,"w") as f:
            for line in templist:
                f.write(line + "\n")

        # solve-field writes a .wcs file with the same base name
        wcs_filename = str(image_path).replace(".jpg",".wcs")
        #print("PlateSolver.RunSolveField(",self.Name,"): WCS file",wcs_filename)
        
        if True:
            for ending in [".axy",".corr",".match",".rdls"]:
                tab_filename = str(image_path).replace(".jpg",ending)
                #print("PlateSolver.RunSolveField(",self.Name,"):",ending,tab_filename,"converting to json.")
                self.FitsTableToDict(tab_filename) # Convert the file into a .json file on disc.
        
        # Files generated 
        # *.axy - extracted star list (pixel coordinates)
        # *rdls - radec list of extracted stars.
        # *.match - list of which stars were matched against catalog.
        # *.corr - Lower level geometric matches used during solving.
        
        return Path(wcs_filename)

    def WCSRotationDeg(self, cd11, cd12, cd21, cd22):
        """
        Returns the rotation angle of the WCS in degrees.
        Positive angle = image is rotated counter‑clockwise on the sky.
        """
        # Scale factors (arcsec/pixel)
        sx = math.sqrt(cd11*cd11 + cd21*cd21)
        sy = math.sqrt(cd12*cd12 + cd22*cd22)

        # Normalised CD matrix
        r11 = cd11 / sx
        r12 = cd12 / sy
        r21 = cd21 / sx
        r22 = cd22 / sy

        # Rotation angle (radians)
        theta = math.atan2(r21, r11)

        return math.degrees(theta)

    def ListFITSTab(self,filename):
        """
        List content of binary fits table to screen.
        """
        with fits.open(filename) as hdul: 
            data = hdul[1].data 
            print(data.columns) 
            print(data[0])

    def ParseWCSHeader(self,wcs_path: Path):
        """
        Very lightweight FITS header parser for the WCS file.

        We only care about a few keywords:
          - CRVAL1, CRVAL2: RA/Dec of reference pixel (deg)
          - CDELT1, CDELT2 or CD1_1, CD2_2: plate scale (deg/pixel)
          - CROTA2 or derived from CD matrix: rotation (deg)

        This is intentionally minimal and not a full FITS/WCS implementation.
        """

        self.FitsHeader = {}
        with wcs_path.open("rb") as f:
            # FITS header is ASCII in 80-char cards, ends with 'END'
            while True:
                card = f.read(80)
                if not card:
                    break
                text = card.decode("ascii", errors="ignore")
                key = text[:8].strip()
                if key == "END":
                    break
                if "=" in text:
                    k = text[:8].strip()
                    v = text[10:30].strip()
                    # Try to parse numeric values
                    try:
                        self.FitsHeader[k] = float(v)
                    except ValueError:
                        self.FitsHeader[k] = v.strip("' ")

        # RA/Dec center
        ra = self.FitsHeader.get("CRVAL1", None)
        dec = self.FitsHeader.get("CRVAL2", None)

        cd11 = self.FitsHeader.get("CD1_1", None)
        cd12 = self.FitsHeader.get("CD1_2", None)
        cd21 = self.FitsHeader.get("CD2_1", None)
        cd22 = self.FitsHeader.get("CD2_2", None)
        CRPIX1 = self.FitsHeader.get("CRPIX1",None)
        CRPIX2 = self.FitsHeader.get("CRPIX2",None)

        if cd11 is not None and cd22 is not None:
            scale_x_deg = abs(cd11)
            scale_y_deg = abs(cd22)
        else:
            scale_x_deg = scale_y_deg = None

        rot = self.WCSRotationDeg(cd11, cd12, cd21, cd22) # Rotation (ie direction of +RA, +ve x axis = 0 deg).

        self.SolutionDict = {
            "timestamp": str(datetime.now()),
            "orig_file": self.OrigImageFile,
            "calculation_seconds":round(self.SolveSeconds,2),
            "ra_deg": ra,
            "dec_deg": dec,
            "scale_x_arcsec": scale_x_deg * 3600 if scale_x_deg is not None else None,
            "scale_y_arcsec": scale_y_deg * 3600 if scale_y_deg is not None else None,
            "rotation_deg": rot,
            "ref_x": CRPIX1,
            "ref_y": CRPIX2,
            "CRPIX1": CRPIX1,
            "CRPIX2": CRPIX2,
            "CRVAL1": ra, 
            "CRVAL2": dec,
            "CD1_1": cd11, 
            "CD1_2": cd12,
            "CD2_1": cd21,
            "CD2_2": cd22,
        }
        return True # Success

    def PlateSolve(self,
                   image_path,
                   downsample = 4,
                   fov_deg_width_low = None,
                   fov_deg_width_high = None,
                   hint_ra = None, # --ra <deg> # Hint RA guess in degrees.
                   hint_dec = None, # --dec <deg> # Hint DEC guess in degrees.
                   hint_radius = None # --radius <deg> # Radius of guess in degrees.
                   ):
        """
        High-level function to plate-solve an image and return basic WCS info.

        Parameters
        ----------
        image_path : str
            Path to the captured image (JPEG/PNG/FITS supported by solve-field).
        downsample : int
            Downsampling factor for speed. 2 or 4 is usually fine for wide fields.
        fov_deg_width_low / fov_deg_width_high : float, optional
            Hints for image width in degrees. For IMX477:
              - 16mm lens: ~40 deg
              - 50mm lens: ~13 deg
            Example: low=10, high=50 to cover both.
        timeout : int
            Max seconds to allow solve-field to run.

        Returns
        -------
        dict with keys:
            - ra_deg
            - dec_deg
            - scale_x_arcsec
            - scale_y_arcsec
            - rotation_deg
        """

        start_time = datetime.now()
        image_path = Path(image_path).resolve()

        wcs_path = self.RunSolveField(
            image_path=image_path,
            downsample=downsample,
            scale_low=fov_deg_width_low,
            scale_high=fov_deg_width_high,
            scale_units="degwidth",
            hint_ra=hint_ra,
            hint_dec=hint_dec,
            hint_radius=hint_radius
        )
        self.SolveSeconds = (datetime.now() - start_time).total_seconds() # How long did it take?

        if not self.ParseWCSHeader(wcs_path): print("plateSolver.PlateSolve(): Failed in ParseWCSHeader().")
        

        self.Markup(star_limit=400) # Create disc copy of image marked up with known information.
        return True # Success

    def GetImageCentreRADEC(self):
        centre_y,centre_x = self.Image.GetImageCenter() # Where is the centre of the image?
        centre_ra,centre_dec = self.PixelToRadec(centre_x,centre_y)
        return centre_ra, centre_dec
        
    def Markup(self,maxdistance=1e-3,star_limit=200):
        """
        Markup the original image with the solution.        
        """
        
        if self.SolutionDict is None:
            print("PlateSolver.Markup(): SolutionDict is None")
            return False
            
        # Mark up the image with the solution too.
        starid_minval = 100 # Star must be at least ?? pixels.
        starid_maxval = 10000 # Star cannot be more than ?? pixels.
        starid_maxstars = 500 # Stop at 500 stars.
        starid_threshold = 200 # Brightness to be counted as a star.
        self.LoadHipparcosDf() # Load HipparcosDf if not already loaded, identifies specific stars.
        centre_y,centre_x = self.Image.GetImageCenter() # Where is the centre of the image?
        centre_ra,centre_dec = self.PixelToRadec(centre_x,centre_y)
        
        self.CalculateStarList(minval=starid_minval,maxval=starid_maxval,maxstars=starid_maxstars,threshold=starid_threshold) # Count and locate stars.
        self.Image.ChangeType('bgr') # Make sure the buffer is in color for the markup.

        # Identify the centre of the image.
        self.Image.DrawEdgeCrosshairs(x=centre_x,y=centre_y,radius=100,outerradius=200,color=(255,255,255),edgecolor=(0,0,0),spoke_angle=0,thickness=2,edgethickness=2)
        temp = "Centre: " + str(round(centre_x,4)) + "," + str(round(centre_y,4))
        self.Image.AddText(text=temp,fromx=int(centre_x),fromy=int(centre_y) - 450,size=2,thickness=2,color=(255,255,255),hjust='c',vjust='b')
        h,m,s = AngleToHMS(centre_ra)
        temp = "RA: " + str(h) + "h " + str(m) + "m " + str(round(s,2)) + "s, Dec: " + str(round(centre_dec,4))
        self.Image.AddText(text=temp,fromx=int(centre_x),fromy=self.Image.NextTextY,size=2,thickness=2,color=(255,255,255),hjust='c',vjust='b')

        if self.SolutionDict is not None: # Markup image.
            ref_x = self.SolutionDict.get('ref_x',None)
            ref_y = self.SolutionDict.get('ref_y',None)
            ra_deg = self.SolutionDict.get('ra_deg',None)
            dec_deg = self.SolutionDict.get('dec_deg',None)
            rot = self.SolutionDict.get('rotation_deg',None)
            if True:
                if ref_x is not None and ref_y is not None: 
                    ref_x = int(ref_x)
                    ref_y = int(ref_y)
                    self.Image.DrawEdgeCrosshairs(x=ref_x,y=ref_y,radius=100,outerradius=200,color=(0,0,255),edgecolor=(0,0,0),spoke_angle=45,thickness=2,edgethickness=2)
                    temp = "Reference: " + str(round(ref_x,4)) + "," + str(round(ref_y,4))
                    self.Image.AddText(text=temp,fromx=int(ref_x),fromy=int(ref_y) - 450,size=2,thickness=2,color=(0,0,255),hjust='c',vjust='b')
                    if ra_deg is not None and dec_deg is not None:
                        h,m,s = AngleToHMS(ra_deg)
                        temp = "RA: " + str(h) + "h " + str(m) + "m " + str(round(s,2)) + "s, Dec: " + str(round(dec_deg,4))
                        self.Image.AddText(text=temp,fromx=int(ref_x),fromy=self.Image.NextTextY,size=2,thickness=2,color=(0,0,255),hjust='c',vjust='b')
                    if rot is not None:
                        temp = "Rotation: " + str(round(rot,4)) + " deg. (+ve RA)"
                        self.Image.AddText(text=temp,fromx=int(ref_x),fromy=self.Image.NextTextY,size=2,thickness=2,color=(0,0,255),hjust='c',vjust='b')
                        self.Image.DrawEdgeVector(startcoord=(int(ref_x),int(ref_y)),length=400,angle=rot,zero=(1,0),anticlockwise=True,color=(0,0,255),thickness=2,edgecolor=(0,0,0),edgethickness=1,arrowpixels=50)
            # Draw grid of ra/dec positions. To see how the conversion is working.
            if False:
                ra_int = int(round(ra_deg,0))
                dec_int = int(round(dec_deg,0))
                for ra_i in range(ra_int - 5,ra_int + 6):
                    for dec_i in range(dec_int - 5, dec_int + 6):
                        x,y = self.RadecToPixel(ra_deg = ra_i, dec_deg = dec_i)
                        #print("Plotting grid:","ra:",ra_i,"dec:",dec_i,"=",(x,y))
                        self.Image.DrawEdgeCrosshairs(x=x,y=y,radius=25,outerradius=50,color=(0,255,255),edgecolor=(0,0,0),thickness=1,edgethickness=1)
                        temp = "RA:" + str(ra_i) + ", DEC:" + str(dec_i)
                        self.Image.AddText(text=temp,fromx=int(x),fromy=int(y) - 100,size=1,thickness=1,color=(0,255,255),hjust='c',vjust='b')
            # Identify location of stars.
            if True: # Earlier version.
                for entry in self.IdentityList[:star_limit]: # Only xx brightest stars to start with.
                    # entry = [x,y,r,ra,dec,hip,delta]
                    x = int(entry[0])
                    y = int(entry[1])
                    r = int(entry[2])
                    star_ra = float(entry[3])
                    star_dec = float(entry[4])
                    hip = entry[5]
                    delta = float(entry[6])
                    if delta < maxdistance: # Gotta be close!
                        self.Image.DrawEdgeCrosshairs(x=x,y=y,radius=r*2,outerradius=r*4,color=(0,255,0),edgecolor=(0,0,0),thickness=1,edgethickness=1)
                        self.Image.AddText(text=hip,fromx=int(x),fromy=int(y) - 100,size=1,thickness=1,color=(0,255,0),hjust='c',vjust='b')
                    else:
                        self.Image.DrawEdgeCrosshairs(x=x,y=y,radius=r*2,outerradius=r*4,color=(255,255,0),edgecolor=(0,0,0),thickness=1,edgethickness=1)
                        temp = "RA: " + str(round(star_ra,3)) + ", Dec:" + str(round(star_dec,3))
                        self.Image.AddText(text=temp,fromx=int(x),fromy=int(y) - 100,size=1,thickness=1,color=(255,255,0),hjust='c',vjust='b')
        else: # No solution available.
            text = "No solution available"
            self.Image.AddText(text=text,fromx=centre_x,fromy=centre_y,size=3,thickness=2,color=(0,0,255),hjust='c',vjust='c')
        self.Image.AddText(text="source:" + str(self.OrigImageFile),fromx=centre_x,fromy=self.Image.GetHeight() - 50,color=(255,255,255),bgcolor=(0,0,0),hjust='c',vjust='b')
        #outputfile = str(image_path).replace(".jpg","_solution.jpg")
        outputfile = str(self.OrigImageFile) + ".solution.jpg"
        
        # If exif data available include that.
        if True:
            from_x = 100
            from_y = 100
            if len(self.ExifData) > 0:
                self.Image.AddText(text="EXIF data:",fromx=from_x,fromy=from_y,color=(255,255,255),hjust='l',vjust='t')
            else:
                self.Image.AddText(text="No EXIF data available:",fromx=from_x,fromy=from_y,color=(255,255,255),hjust='l',vjust='t')
            for key,value in self.ExifData.items():
                text = str(key) + ":" + str(value)
                self.Image.AddText(text=text,fromx=from_x,fromy=self.Image.NextTextY,color=(255,255,255),hjust='l',vjust='t')
            
        self.Image.SaveFile(outputfile)
        return True

    def CalculateStarList(self,minval=100,maxval=10000,maxstars=500,threshold=200):
        """
        Populate self.StarList. Needs handle to pilomarimage instance.
        Where multiple stars match a HIP identity only the closest match is made.
        
        Parameters -----------------------------------------------------------
        minval (int) :     100 # Star must be at least ?? pixels.
        maxval (int) :   10000 # Star cannot be more than ?? pixels.
        maxstars (int) :   500 # Stop at 500 stars.
        threshold (int) :  200 # Brightness to be counted as a star.
        
        References -----------------------------------------------------------
        self.Image (pilomarimage): Instance containing cleaned image to analyse.
        
        Sets -----------------------------------------------------------------
        
        self.StarCount
        self.StarList [(x,y,r),(x,y,r),...
        self.IdentityList [[x,y,r,ra,dec,hip,delta),(x,y,r,ra,dec,hip,delta],...]
            where x = image pixel x location
                  y = image pixel y location
                  r = image radius of star
                  ra = calculated RA of star (degrees)
                  dec = calculated Dec of star (degrees)
                  hip = Closest HIPPARCOS number identified or ''.
                  delta = Radian distance between image star and nearest catalog location. Helps to select good matches.
                  
        Returns --------------------------------------------------------------
        Success (bool) : True if succeeded. 
        
        """
        # Mark up the image with the solution too.
        self.StarCount, self.StarList = self.Image.CountStars(minval=minval,maxval=maxval,maxstars=maxstars,threshold=threshold) # Count and locate stars.
        self.StarList = sorted(self.StarList, key=lambda t: t[2], reverse=True) # Descending radius.
        self.IdentityList = [] # Calculate list of RADEC locations based upon StarList.
        for entry in self.StarList:
            x = entry[0]
            y = entry[1]
            r = entry[2]
            ra,dec = self.PixelToRadec(x,y)
            nearest_dict = self.NearestStar(ra,dec) # Get {"hip","name","starname","distance_rad","ra_degrees","dec_degrees"}
            distance = nearest_dict["distance_rad"]
            self.IdentityList.append([x,y,r,ra,dec,nearest_dict["name"],nearest_dict["distance_rad"]])
            
        # Eliminate duplicates, so that only the closest match is retained.
        # Some objects are not in the hipparcos list because they are NGC/IC items etc, the list will still link to the closest Hipparcos star so we must eliminate them.
        self.IdentityList = sorted(self.IdentityList, key=lambda t: (t[5], t[6])) # Sort by NAME and DISTANCE. We want only the closest entry for each name.
        prev_name = ""
        name_count = 0
        for i,entry in enumerate(self.IdentityList):
            if entry[5] != prev_name: # Name has changed.
                name_count = 0
                prev_name = entry[5]
            name_count += 1 # Increment count for the current name.
            if prev_name != "" and name_count > 1: # We don't consider this a match, we have a closer one.
                self.Log("PlateSolver(",self.Name,").CalculateStarList(): Removed duplicate",entry,", there is a better match.",terminal=False)
                self.IdentityList[i][5] = ""

        # Revert back to descending size (so brightest first)
        self.IdentityList = sorted(self.IdentityList, key=lambda t: t[2], reverse=True) # Descending radius.
        
        return True
    
    def IdentitiesToDict(self):
        """
        Convert self.IdentityList into a dictionary. 
        {
            "0": {
                "x": 3011,
                "y": 1181,
                "r": 41,
                "ra": 84.05008823320837,
                "dec": -1.2015084749102523,
                "hip": "HIP26311",
                "delta": 5.7979972516340647e-05
            }
        """
        dictionary = {}
        for i,entry in enumerate(self.IdentityList):
            dictionary[i] = {
                "x":int(entry[0]),
                "y":int(entry[1]),
                "r":int(entry[2]),
                "ra":float(entry[3]),
                "dec":float(entry[4]),
                "hip":str(entry[5]),
                "delta":float(entry[6])
                }
        return dictionary 
        
    def ExportAllJSON(self,filename):
        """
        Export a JSON file with all the details (solution and identities).
        
        Parameters -----------------------------------------
        filename (str) : Path to the file that will be written.
        
        Returns --------------------------------------------
        success (bool)
        
        {
            "solution": {
                "timestamp": "2026-03-12 12:28:59.122846",
                "orig_file": "/home/pi/pilomar/temp/light_20260113231133_00.jpg",
                "calculation_time": 66.84,
                "ra_deg": 83.8947650848,
                "dec_deg": -1.41646814546,
                "scale_x_arcsec": 6.12685762596,
                "scale_y_arcsec": 6.134291736552,
                "rotation_deg": 172.07088456545415,
                "ref_x": 3083.17537435,
                "ref_y": 1317.19063314,
                "CRPIX1": 3083.17537435,
                "CRPIX2": 1317.19063314,
                "CRVAL1": 83.8947650848,
                "CRVAL2": -1.41646814546,
                "CD1_1": -0.0017019048961,
                "CD1_2": -0.000238304551978,
                "CD2_1": 0.000237040374646,
                "CD2_2": -0.00170396992682
            },
            "identities": {
                "0": {
                    "x": 3011,
                    "y": 1181,
                    "r": 41,
                    "ra": 84.05008823320837,
                    "dec": -1.2015084749102523,
                    "hip": "HIP26311",
                    "delta": 5.7979972516340647e-05
                },        
        """
        master = {"solution":self.SolutionDict,"identities":self.IdentitiesToDict()}
        with open(filename,'w') as f:
            json.dump(master,f,indent=4)
        return True

    def ExportIdentitiesJSON(self,filename):
        """
        Export identities as JSON dictionary for other programs to use.
        
        Parameters -----------------------------------------
        filename (str) : Path to the file that will be written.
        
        Returns --------------------------------------------
        success (bool)
        {
            "0": {
                "x": 3011,
                "y": 1181,
                "r": 41,
                "ra": 84.05008823320837,
                "dec": -1.2015084749102523,
                "hip": "HIP26311",
                "delta": 5.7979972516340647e-05
            },        
        """
        self.Log("PlateSolver(",self.Name,").ExportIdentitiesJSON(",filename,")",terminal=False)
        dictionary = self.IdentitiesToDict()
        with open(filename,'w') as f:
            json.dump(dictionary,f,indent=4)
        return True
    
    def ExportSolutionJSON(self,filename):
        """
        Export Solution dictionary as a JSON dictionary for other programs to use.
        
        Parameters -----------------------------------------
        filename (str) : Path to the file that will be written.
        
        Returns --------------------------------------------
        success (bool)
        
        {
            "solution": {
                "timestamp": "2026-03-12 12:28:59.122846",
                "orig_file": "/home/pi/pilomar/temp/light_20260113231133_00.jpg",
                "calculation_time": 66.84,
                "ra_deg": 83.8947650848,
                "dec_deg": -1.41646814546,
                "scale_x_arcsec": 6.12685762596,
                "scale_y_arcsec": 6.134291736552,
                "rotation_deg": 172.07088456545415,
                "ref_x": 3083.17537435,
                "ref_y": 1317.19063314,
                "CRPIX1": 3083.17537435,
                "CRPIX2": 1317.19063314,
                "CRVAL1": 83.8947650848,
                "CRVAL2": -1.41646814546,
                "CD1_1": -0.0017019048961,
                "CD1_2": -0.000238304551978,
                "CD2_1": 0.000237040374646,
                "CD2_2": -0.00170396992682
            }        
        """
        with open(filename,'w') as f:
            json.dump(self.SolutionDict,f,indent=4)
        return True
        
    def PrepImage(self,filename): # Clean the image as required.
        self.OrigImageFile = filename # Record the original filename.
        workfilename = self.TempDir + 'platesolver_clean_input.jpg'
        self.Image = pilomarimage(name='prep_for_platesolver')
        self.Image.LoadFile(filename)
        if self.ScriptSource != None: # User has specified alternative filter scripts.
            self.Image.SetScriptSource(self.ScriptSource)
        self.Image.RunFilterScript(self.FilterScript) # Use specific filter script.
        self.Image.SaveFile(workfilename)
        self.Image.GetExif(self.OrigImageFile) # Load EXIF data from original image as dictionary.
        
        return workfilename
        
    def PixelToRadec(self, x, y):
        """
        Convert pixel coordinates (x, y) into RA/Dec using a WCS dictionary
        containing:
            CRPIX1, CRPIX2
            CRVAL1, CRVAL2
            CD1_1, CD1_2, CD2_1, CD2_2
        Returns (RA_deg, DEC_deg)
        """

        # Shift relative to reference pixel
        dx = x - self.SolutionDict["CRPIX1"]
        dy = y - self.SolutionDict["CRPIX2"]

        # Apply CD matrix to get intermediate world coords (degrees)
        X = self.SolutionDict["CD1_1"] * dx + self.SolutionDict["CD1_2"] * dy
        Y = self.SolutionDict["CD2_1"] * dx + self.SolutionDict["CD2_2"] * dy

        # Convert reference RA/Dec to radians
        ra0  = math.radians(self.SolutionDict["CRVAL1"])
        dec0 = math.radians(self.SolutionDict["CRVAL2"])

        # Convert intermediate coords to radians
        Xr = math.radians(X)
        Yr = math.radians(Y)

        # TAN (gnomonic) projection inversion
        denom = math.cos(dec0) - Yr * math.sin(dec0)
        ra  = ra0 + math.atan2(Xr, denom)
        dec = math.atan2(
            math.sin(dec0) + Yr * math.cos(dec0),
            math.sqrt(denom*denom + Xr*Xr)
        )

        # Convert back to degrees
        return math.degrees(ra), math.degrees(dec)
        
    def RadecToPixel(self, ra_deg, dec_deg):
        """
        Convert RA/Dec (degrees) into pixel coordinates using a WCS dictionary
        containing:
            CRPIX1, CRPIX2
            CRVAL1, CRVAL2
            CD1_1, CD1_2, CD2_1, CD2_2
        Returns (x, y) pixel coordinates.
        """

        # Convert to radians
        ra  = math.radians(ra_deg)
        dec = math.radians(dec_deg)
        ra0  = math.radians(self.SolutionDict["CRVAL1"])
        dec0 = math.radians(self.SolutionDict["CRVAL2"])

        # TAN projection forward transform
        cosc = math.sin(dec0) * math.sin(dec) + math.cos(dec0) * math.cos(dec) * math.cos(ra - ra0)
        Xr = (math.cos(dec) * math.sin(ra - ra0)) / cosc
        Yr = (math.sin(dec) * math.cos(dec0) - math.cos(dec) * math.sin(dec0) * math.cos(ra - ra0)) / cosc

        # Convert radians back to degrees
        X = math.degrees(Xr)
        Y = math.degrees(Yr)

        # Invert the CD matrix
        det = self.SolutionDict["CD1_1"] * self.SolutionDict["CD2_2"] - self.SolutionDict["CD1_2"] * self.SolutionDict["CD2_1"]
        dx = ( self.SolutionDict["CD2_2"] * X - self.SolutionDict["CD1_2"] * Y) / det
        dy = (-self.SolutionDict["CD2_1"] * X + self.SolutionDict["CD1_1"] * Y) / det

        # Add reference pixel
        x = int(dx + self.SolutionDict["CRPIX1"])
        y = int(dy + self.SolutionDict["CRPIX2"])

        return x, y
        
    def ReadParameterFile(self,filename):
        """
        Read a pilomar project parameter file.
        
        Parameters ----------------------------------------
        filename (str) : Path to parameter file.
        
        Sets ----------------------------------------------
        self.Parameters (dict) is set.
        
        Outputs -------------------------------------------
        success (bool)
        """
        with open (filename,'r') as f:
            self.PilomarParameters = json.load(f)

        return True
        
    def SolveFile(self,filename):
        """
        Solve an image file.
        Receive filename
        Return Success (bool) and dictionary of results.
        """
        result = True
        self.Log("PlateSolver(",self.Name,").SolveFile(",filename,")",terminal=False)
        work_image = self.PrepImage(filename) # Clean the image as required, loads the clean image into a pilomarimage instance as self.Image.
        if not self.PlateSolve(work_image,
                               downsample=2,
                               fov_deg_width_low=5.0, # 10 for 50mm, 25 for 16mm, 10 for both
                               fov_deg_width_high=60.0): # 20 for 50mm, 55 for 16mm, 50 for both
            self.Log("PlateSolver(",self.Name,").SolveFile(",filename,") failed.",level='warning',terminal=False)
            result = False
        
        stop_time = datetime.now()
        self.Log("PlateSolver(",self.Name,").SolveFile() Solver took",round(self.SolveSeconds,2),"seconds for",filename,terminal=False)
        centre_ra, centre_dec = self.GetImageCentreRADEC()
        h,m,s = AngleToHMS(centre_ra)
        d,m1,s1 = AngleToDMS(centre_dec)
        temp = "Image centre RA: " + str(h) + "h " + str(m) + "m " + str(round(s,2)) + "s, "
        temp += "Dec: " + str(d) + "deg " + str(m1) + "' " + str(round(s1,3)) + '"'
        self.Log("PlateSolver(",self.Name,").SolveFile() Centre location:",temp,terminal=False)
        self.ExportAllJSON(filename + ".solution.json")
        master = {"solution":self.SolutionDict,"identities":self.IdentitiesToDict()}
        return result, master

if __name__ == "__main__":
    # Example usage:
    # For IMX477 + 16mm/50mm, a safe FOV width range might be 10–50 deg.
    
    import sys
    import argparse
    import os

    def argument_parser():
        parser = argparse.ArgumentParser(description="Plate solving pipeline")
        parser.add_argument("input_file", default="../temp/light_20260113231133_00.jpg", nargs="+", help="Path to the jpeg file")
        parser.add_argument("--project_root", default=str(Path(sys.argv[0]).absolute().parent.parent), help="Root of the pilomar project installation")
        parser.add_argument("--filter_script", default='PrepForPlateSolving', help="Name of filter script to run")
        parser.add_argument("--script_source", default=None, help="Source of filter scripts (JSON file)")
        parser.add_argument("--debug", default=False, help="Trigger additional debugging features.")
        # parser.add_argument("--time_out", type=int, default=90, help="Solver time out (seconds)")
        runtime_args = parser.parse_args()

        return runtime_args

    runtime_args = argument_parser()
    # Find the project folder structure.
    ProjectRoot = runtime_args.project_root
    filter_script = runtime_args.filter_script
    script_source = runtime_args.script_source 
    debug_mode = runtime_args.debug
    
    img_list = runtime_args.input_file
    if type(img_list) is str: img_list = [img_list] # This must always be a list.
    
    for img in img_list: # Process all listed files.
        if not os.path.isfile(img):
            print("Ignored",img,"because it does not exist.")
            continue # Does not exist.
        if not img.split(".")[-1].lower() in ["jpg","jpeg"]: 
            print("Ignored",img,"because it is not a jpg file.")
            continue # Not a jpeg file.
        output_image = False
        for i in [".jpg.",".jpeg."]:
            if i in img: output_image = True
        if output_image: 
            print("Ignored",img,"because it looks like an output image.")
            continue
        
        print("Solving:",img)
        mysolver = PlateSolver(name='mysolver',projectroot=ProjectRoot,filter_script=filter_script,script_source=script_source,debug=debug_mode)
        success,result = mysolver.SolveFile(img) # Clean the image as required, loads the clean image into a pilomarimage instance as self.Image.
        if not success: print("Failed to solve",img)
        # result = Dictionary of solver output.

# """
# wcs file looks like this ....
# 
# SIMPLE  =                    T / Standard FITS file                         
# BITPIX  =                    8 / ASCII or bytes array                       
# NAXIS   =                    0 / Minimal header    
# EXTEND  =                    T / There may be FITS ext                      
# WCSAXES =                    2 / no comment        
# CTYPE1  = 'RA---TAN-SIP' / TAN (gnomic) projection + SIP distortions        
# CTYPE2  = 'DEC--TAN-SIP' / TAN (gnomic) projection + SIP distortions        
# EQUINOX =               2000.0 / Equatorial coordinates definition (yr)     
# LONPOLE =                180.0 / no comment        
# LATPOLE =                  0.0 / no comment        
# CRVAL1  =        82.2903552559 / RA  of reference point                     
# CRVAL2  =       -3.10251578802 / DEC of reference point                     
# CRPIX1  =        3434.41682943 / X reference pixel 
# CRPIX2  =        1036.22324626 / Y reference pixel 
# CUNIT1  = 'deg     ' / X pixel scale units         
# CUNIT2  = 'deg     ' / Y pixel scale units         
# CD1_1   =    -0.00161493272276 / Transformation matrix 11
# CD1_2   =    0.000576225073359 / Transformation matrix 12
# CD2_1   =   -0.000577109392169 / Transformation matrix 21
# CD2_2   =    -0.00162022299234 / Transformation matrix 22
# IMAGEW  =                 4056 / Image width,  in pixels.                   
# IMAGEH  =                 3040 / Image height, in pixels.                   
# A_ORDER =                    2 / Polynomial order, axis 1                   
# A_0_0   =                    0 / no comment        
# A_0_1   =                    0 / no comment        
# A_0_2   =    1.56292282598E-07 / no comment        
# A_1_0   =                    0 / no comment        
# A_1_1   =    7.88646929145E-07 / no comment        
# A_2_0   =   -1.42354167297E-06 / no comment        
# B_ORDER =                    2 / Polynomial order, axis 2                   
# B_0_0   =                    0 / no comment        
# B_0_1   =                    0 / no comment        
# B_0_2   =    5.95683057393E-07 / no comment        
# B_1_0   =                    0 / no comment        
# B_1_1   =   -1.10129355786E-06 / no comment        
# B_2_0   =   -6.23110777348E-09 / no comment        
# AP_ORDER=                    2 / Inv polynomial order, axis 1               
# AP_0_0  =     0.00269439951202 / no comment        
# AP_0_1  =    2.81394620675E-06 / no comment        
# AP_0_2  =   -1.56259422826E-07 / no comment        
# AP_1_0  =   -1.88294596289E-05 / no comment        
# AP_1_1  =   -7.76541537904E-07 / no comment        
# AP_2_0  =    1.40456874541E-06 / no comment        
# BP_ORDER=                    2 / Inv polynomial order, axis 2               
# BP_0_0  =    -0.00195033022303 / no comment        
# BP_0_1  =   -4.85747358438E-06 / no comment        
# BP_0_2  =    -5.9092761979E-07 / no comment        
# BP_1_0  =    1.99746069203E-06 / no comment        
# BP_1_1  =    1.09083623284E-06 / no comment        
# BP_2_0  =    7.44776306328E-09 / no comment        
# HISTORY Created by the Astrometry.net suite.       
# HISTORY For more details, see http://astrometry.net.                        
# HISTORY Git URL https://github.com/dstndstn/astrometry.net                  
# HISTORY Git revision 0.93                          
# HISTORY Git date Mon_Dec_19_16:41:15_2022_-0500    
# HISTORY This is a WCS header was created by Astrometry.net.                 
# DATE    = '2026-03-02T09:55:37' / Date this file was created.               
# COMMENT -- onefield solver parameters: --          
# COMMENT Index(0): /usr/share/astrometry/index-2mass-19.fits                 
# COMMENT Index(1): /usr/share/astrometry/index-2mass-18.fits                 
# COMMENT Index(2): /usr/share/astrometry/index-2mass-17.fits                 
# COMMENT Index(3): /usr/share/astrometry/index-2mass-16.fits                 
# COMMENT Index(4): /usr/share/astrometry/index-2mass-15.fits                 
# COMMENT Index(5): /usr/share/astrometry/index-2mass-14.fits                 
# COMMENT Index(6): /usr/share/astrometry/index-2mass-13.fits                 
# COMMENT Index(7): /usr/share/astrometry/index-2mass-12.fits                 
# COMMENT Index(8): /usr/share/astrometry/index-2mass-11.fits                 
# COMMENT Index(9): /usr/share/astrometry/index-2mass-10.fits                 
# COMMENT Index(10): /usr/share/astrometry/index-2mass-09.fits                
# COMMENT Index(11): /usr/share/astrometry/index-2mass-08.fits                
# COMMENT Field name: ./LatestTrackingImage_20260113200812.axy                
# COMMENT Field scale lower: 0.0887574 arcsec/pixel  
# COMMENT Field scale upper: 159.763 arcsec/pixel    
# COMMENT X col name: X 
# COMMENT Y col name: Y 
# COMMENT Start obj: 0  
# COMMENT End obj: 10   
# COMMENT Solved_in: (null)                          
# COMMENT Solved_out: ./LatestTrackingImage_20260113200812.solved             
# COMMENT Parity: 2     
# COMMENT Codetol: 0.01 
# COMMENT Verify pixels: 1 pix                       
# COMMENT Maxquads: 0   
# COMMENT Maxmatches: 0 
# COMMENT Cpu limit: 300.000000 s                    
# COMMENT Time limit: 0 s                            
# COMMENT Total time limit: 0 s                      
# COMMENT Total CPU limit: 300.000000 s              
# COMMENT Tweak: yes    
# COMMENT Tweak AB order: 2                          
# COMMENT Tweak ABP order: 2                         
# COMMENT --            
# COMMENT -- properties of the matching quad: --     
# COMMENT index id: 4212                             
# COMMENT index healpix: -1                          
# COMMENT index hpnside: 0                           
# COMMENT log odds: 176.577                          
# COMMENT odds: 4.85782e+76                          
# COMMENT quadno: 129028                             
# COMMENT stars: 77523,77504,77514,0                 
# COMMENT field: 9,8,2,0                             
# COMMENT code error: 0.00101278                     
# COMMENT nmatch: 24    
# COMMENT nconflict: 1  
# COMMENT nfield: 51    
# COMMENT nindex: 89    
# COMMENT scale: 6.18226 arcsec/pix                  
# COMMENT parity: 1     
# COMMENT quads tried: 97                            
# COMMENT quads matched: 11729                       
# COMMENT quads verified: 11728                      
# COMMENT objs tried: 10                             
# COMMENT cpu time: 0.451886                         
# COMMENT --            
# END
# """