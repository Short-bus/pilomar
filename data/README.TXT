This folder contains data files that Pilomar uses.

constellationship.fab is a cached copy of the Stellarium constellation patterns ('modern').
- Skyfield automatically downloads this from the stellarium GitHub site.
- By early 2025 it appears that Stellarium has changed the name/format/location of the file
  so the skyfield routine fails.
- As a workaround there is now a preloaded copy of the original file here.
- All rights/ownership etc remain with Stellarium, this only exists until Skyfield 
  provides support for the newer Stellarium solution.

de421.bsp is the planetary ephemera file from NASA.
- This is normally downloaded automatically in a new installation by Skyfield.
- At times the download fails due to HTTP issues of various sorts.
- As a workaround the file is now preloaded with this GitHub package.

messierobjects.json is a catalog of messier objects.

meteors.json is a catalog of meteor showers.

ngc.json is a catalog of NGC, PGC and IC deep space objects.

starnames.json is a cross-reference list of common star names.
