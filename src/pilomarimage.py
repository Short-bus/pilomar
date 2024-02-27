#!/usr/bin/python

# image class for use in Pilomar project.
# Builds upon opencv features to provide pilomar specific routines.
# Some methods are just simplifications of existing opencv routines, such as line drawing, circles, etc.
# Some methods are enhancements adding some more features to existing opencv functions.
# There are also some methods which are very specific to the pilomar miniature observatory project.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import cv2 # OpenCV.
import numpy as np # Numpy array handling.
#from scipy.spatial.distance import pdist, squareform # For ArrangeLabels physics modelling. Included in ChatGPT generated code, but not actually used!
from datetime import datetime, timezone, timedelta
import math
import random # random number generator.
import os


class data_set():
    """ Data set list of data points. """
    def __init__(self,name,color=None,style=['line']):
        self.Name = name
        self.DataPoints = []
        self.Color = color
        self.Style = style
        
    def Add(self,point):
        self.DataPoints.append(point)
        
    def Clear(self):
        self.DataPoints = []
        
class data_point():
    """ Datapoint. """
    def __init__(self,x,y,color=None,label=None,style=['dot'],xname=None,yname=None):
        self.X = x
        self.Y = y
        self.Color = color
        self.Label = label
        self.Style = style
        self.XName = xname
        self.YName = yname

### BEGIN DEVELOPMENT ###
class fd_object():
    """ Object to be placed in an image (for force directed graphs). """
    def __init__(self):
        self.Name = None
        self.Type = None
        self.Width = None # Dimensions of object.
        self.Height = None
        self.InitialX = None # Centre of object.
        self.InitialY = None
        self.Fixed = False
        self.CurrentX = self.InitialX # Centre of object.
        self.CurrentY = self.InitialY
        self.TargetX = self.InitialX # Centre of object.
        self.TargetY = self.InitialY
        
class fd_edge():
    """ Link between to objects (for force directed graphs). """
    def __init__(self):
        self.Name = None
        self.ObjectA = None # Handle to object at one end of the edge.
        self.ObjectB = None # Handle to object at the other end of the edge.
### END DEVELOPMENT ###

class pilomarimage():

    # Constants.
    __version__ = '0.0.2'
    IMAGETYPES = ['bgr','bgra','grayscale']
    COLORPOINTS = [(-0.33,[0x70,0x6f,0xfe]),
                   (-0.3,[0x51,0x9f,0xfe]),
                   (-0.02,[0xbf,0xd0,0xff]),
                   (0.3,[0xcd,0xfd,0xff]),
                   (0.58,[0xee,0xff,0xdf]),
                   (0.81,[0xff,0xff,0x7f]),
                   (1.4,[0xfe,0x7f,0x7d])]
    # Color names for OpenCV drawing. (Beware colors are BGR not RGB!)
    # Official HTML colors 3 Channel BGR colors only. 
    BGRBlack = (0,0,0)
    BGRNight = (10,9,12)
    BGRCharcoal = (44,40,52)
    BGROil = (49,49,59)
    BGRDarkGray = (60,59,58)
    BGRLightBlack = (69,69,69)
    BGRBlackCat = (57,56,65)
    BGRIridium = (58,60,61)
    BGRBlackEel = (63,62,70)
    BGRBlackCow = (70,70,76)
    BGRGrayWolf = (75,74,80)
    BGRVampireGray = (81,80,86)
    BGRIronGray = (93,89,82)
    BGRGrayDolphin = (88,88,92)
    BGRCarbonGray = (93,93,98)
    BGRAshGray = (98,99,102)
    BGRDimGray = (105,105,105)
    BGRNardoGray = (108,106,104)
    BGRCloudyGray = (104,105,109)
    BGRSmokeyGray = (109,110,114)
    BGRAlienGray = (110,111,115)
    BGRSonicSilver = (117,117,117)
    BGRPlatinumGray = (121,121,121)
    BGRGranite = (124,126,131)
    BGRGray = (128,128,128)
    BGRBattleshipGray = (130,132,132)
    BGRGunmetalGray = (141,145,141)
    BGRDarkGray = (169,169,169)
    BGRGrayCloud = (180,182,182)
    BGRSilver = (192,192,192)
    BGRPaleSilver = (187,192,201)
    BGRGrayGoose = (206,208,209)
    BGRPlatinumSilver = (206,206,206)
    BGRLightGray = (211,211,211)
    BGRSilverWhite = (221,219,218)
    BGRGainsboro = (220,220,220)
    BGRPlatinum = (226,228,229)
    BGRMetallicSilver = (204,198,188)
    BGRBlueGray = (199,175,152)
    BGRRomanSilver = (150,137,131)
    BGRLightSlateGray = (153,136,119)
    BGRSlateGray = (144,128,112)
    BGRRatGray = (141,123,109)
    BGRSlateGraniteGray = (131,115,101)
    BGRJetGray = (126,109,97)
    BGRMistBlue = (126,109,100)
    BGRMarbleBlue = (126,109,86)
    BGRSlateBlueGrey = (161,124,115)
    BGRLightPurpleBlue = (206,143,114)
    BGRAzureBlue = (160,99,72)
    BGRBlueJay = (126,84,43)
    BGRCharcoalBlue = (79,69,54)
    BGRDarkBlueGrey = (91,70,41)
    BGRDarkSlate = (86,56,43)
    BGRDeepSeaBlue = (86,52,18)
    BGRNightBlue = (84,27,21)
    BGRMidnightBlue = (112,25,25)
    BGRNavy = (128,0,0)
    BGRDenimDarkBlue = (141,27,21)
    BGRDarkBlue = (139,0,0)
    BGRLapisBlue = (126,49,21)
    BGRNewMidnightBlue = (160,0,0)
    BGREarthBlue = (165,0,0)
    BGRCobaltBlue = (194,32,0)
    BGRMediumBlue = (205,0,0)
    BGRBlueberryBlue = (194,65,0)
    BGRCanaryBlue = (245,22,41)
    BGRBlue = (255,0,0)
    BGRSamcoBlue = (255,2,0)
    BGRBrightBlue = (255,9,9)
    BGRBlueOrchid = (252,69,31)
    BGRSapphireBlue = (199,84,37)
    BGRBlueEyes = (199,105,21)
    BGRBrightNavyBlue = (210,116,25)
    BGRBalloonBlue = (222,96,43)
    BGRRoyalBlue = (225,105,65)
    BGROceanBlue = (236,101,43)
    BGRBlueRibbon = (255,110,48)
    BGRBlueDress = (236,125,21)
    BGRNeonBlue = (255,137,21)
    BGRDodgerBlue = (255,144,30)
    BGRGlacialBlueIce = (193,139,54)
    BGRSteelBlue = (180,130,70)
    BGRSilkBlue = (199,138,72)
    BGRWindowsBlue = (199,126,53)
    BGRBlueIvy = (199,144,48)
    BGRBlueKoi = (199,158,101)
    BGRColumbiaBlue = (199,175,135)
    BGRBabyBlue = (199,185,149)
    BGRCornflowerBlue = (237,149,100)
    BGRSkyBlueDress = (255,152,102)
    BGRIceberg = (236,165,86)
    BGRButterflyBlue = (236,172,56)
    BGRDeepSkyBlue = (255,191,0)
    BGRMiddayBlue = (255,185,59)
    BGRCrystalBlue = (255,179,92)
    BGRDenimBlue = (236,186,121)
    BGRDaySkyBlue = (255,202,130)
    BGRLightSkyBlue = (250,206,135)
    BGRSkyBlue = (235,206,135)
    BGRJeansBlue = (236,207,160)
    BGRBlueAngel = (236,206,183)
    BGRPastelBlue = (236,207,180)
    BGRLightDayBlue = (255,223,173)
    BGRSeaBlue = (255,223,194)
    BGRHeavenlyBlue = (255,222,198)
    BGRRobinEggBlue = (255,237,189)
    BGRPowderBlue = (230,224,176)
    BGRCoralBlue = (236,220,175)
    BGRLightBlue = (230,216,173)
    BGRLightSteelBlue = (222,207,176)
    BGRGulfBlue = (236,223,201)
    BGRPastelLightBlue = (234,214,213)
    BGRLavenderBlue = (250,228,227)
    BGRWhiteBlue = (250,233,219)
    BGRLavender = (250,230,230)
    BGRWater = (250,244,235)
    BGRAliceBlue = (255,248,240)
    BGRGhostWhite = (255,248,248)
    BGRAzure = (255,255,240)
    BGRLightCyan = (255,255,224)
    BGRLightSlate = (255,255,204)
    BGRElectricBlue = (255,254,154)
    BGRTronBlue = (254,253,125)
    BGRBlueZircon = (255,254,87)
    BGRAqua = (255,255,0)
    BGRCyan = (255,255,0)
    BGRBrightCyan = (255,255,10)
    BGRCeleste = (236,235,80)
    BGRBlueDiamond = (236,226,78)
    BGRBrightTurquoise = (245,226,22)
    BGRBlueLagoon = (236,235,142)
    BGRPaleTurquoise = (238,238,175)
    BGRPaleBlueLily = (236,236,207)
    BGRLightTeal = (217,217,179)
    BGRTiffanyBlue = (208,216,129)
    BGRBlueHosta = (199,191,119)
    BGRCyanOpaque = (199,199,146)
    BGRNorthernLightsBlue = (199,199,120)
    BGRBlueGreen = (181,204,123)
    BGRMediumAquaMarine = (170,205,102)
    BGRMagicMint = (209,240,170)
    BGRLightAquamarine = (232,255,147)
    BGRAquamarine = (212,255,127)
    BGRBrightTeal = (198,249,1)
    BGRTurquoise = (208,224,64)
    BGRMediumTurquoise = (204,209,72)
    BGRDeepTurquoise = (205,204,72)
    BGRJellyfish = (199,199,70)
    BGRBlueTurquoise = (219,198,67)
    BGRDarkTurquoise = (209,206,0)
    BGRMacawBlueGreen = (199,191,67)
    BGRLightSeaGreen = (170,178,32)
    BGRSeafoamGreen = (159,169,62)
    BGRCadetBlue = (160,158,95)
    BGRDeepSea = (156,156,59)
    BGRDarkCyan = (139,139,0)
    BGRTealGreen = (127,130,0)
    BGRTeal = (128,128,0)
    BGRTealBlue = (128,124,0)
    BGRMediumTeal = (95,95,4)
    BGRDarkTeal = (93,93,4)
    BGRDeepTeal = (62,62,3)
    BGRDarkSlateGray = (60,56,37)
    BGRGunmetal = (57,53,44)
    BGRBlueMossGreen = (91,86,60)
    BGRBeetleGreen = (126,120,76)
    BGRGrayishTurquoise = (126,125,94)
    BGRGreenishBlue = (126,125,48)
    BGRAquamarineStone = (129,135,52)
    BGRSeaTurtleGreen = (128,141,67)
    BGRDullSeaGreen = (117,137,78)
    BGRDarkGreenBlue = (87,99,31)
    BGRDeepSeaGreen = (84,103,48)
    BGRBottleGreen = (78,106,0)
    BGRSeaGreen = (87,139,46)
    BGRElfGreen = (107,138,27)
    BGRDarkMint = (110,144,49)
    BGRJade = (108,163,0)
    BGREarthGreen = (111,165,52)
    BGRChromeGreen = (96,162,26)
    BGREmerald = (120,200,80)
    BGRMint = (137,180,62)
    BGRMediumSeaGreen = (113,179,60)
    BGRMetallicGreen = (142,157,124)
    BGRCamouflageGreen = (107,134,120)
    BGRSageGreen = (121,139,132)
    BGRHazelGreen = (88,124,97)
    BGRVenomGreen = (0,140,114)
    BGROliveDrab = (35,142,107)
    BGROlive = (0,128,128)
    BGRDarkOliveGreen = (47,107,85)
    BGRMilitaryGreen = (49,91,78)
    BGRGreenLeaves = (11,95,58)
    BGRArmyGreen = (32,83,75)
    BGRFernGreen = (38,124,102)
    BGRFallForestGreen = (88,146,78)
    BGRIrishGreen = (75,160,8)
    BGRPineGreen = (68,124,56)
    BGRMediumForestGreen = (53,114,52)
    BGRJungleGreen = (44,124,52)
    BGRCactusGreen = (66,116,34)
    BGRForestGreen = (34,139,34)
    BGRGreen = (0,128,0)
    BGRDarkGreen = (0,100,0)
    BGRDeepGreen = (8,102,5)
    BGRDeepEmeraldGreen = (7,99,4)
    BGRHunterGreen = (59,94,53)
    BGRDarkForestGreen = (23,65,37)
    BGRLotusGreen = (37,66,0)
    BGRSeaweedGreen = (23,124,67)
    BGRShamrockGreen = (23,124,52)
    BGRGreenOnion = (33,161,106)
    BGRMossGreen = (91,154,138)
    BGRGrassGreen = (11,155,63)
    BGRGreenPepper = (44,160,74)
    BGRDarkLimeGreen = (23,163,65)
    BGRParrotGreen = (43,173,18)
    BGRCloverGreen = (85,160,62)
    BGRDinosaurGreen = (108,161,115)
    BGRGreenSnake = (60,187,108)
    BGRAlienGreen = (23,196,108)
    BGRGreenApple = (23,196,76)
    BGRLimeGreen = (50,205,50)
    BGRPeaGreen = (23,208,82)
    BGRKellyGreen = (82,197,76)
    BGRZombieGreen = (113,197,84)
    BGRGreenPeas = (92,195,137)
    BGRDollarBillGreen = (101,187,133)
    BGRFrogGreen = (142,198,153)
    BGRTurquoiseGreen = (180,214,160)
    BGRDarkSeaGreen = (143,188,143)
    BGRBasilGreen = (130,159,130)
    BGRGrayGreen = (156,173,162)
    BGRIguanaGreen = (113,176,156)
    BGRCitronGreen = (29,179,143)
    BGRAcidGreen = (26,191,176)
    BGRAvocadoGreen = (72,194,178)
    BGRPistachioGreen = (9,194,157)
    BGRSaladGreen = (53,201,161)
    BGRYellowGreen = (50,205,154)
    BGRPastelGreen = (119,221,119)
    BGRHummingbirdGreen = (23,232,127)
    BGRNebulaGreen = (23,232,89)
    BGRStoplightGoGreen = (100,233,87)
    BGRNeonGreen = (41,245,22)
    BGRJadeGreen = (110,251,94)
    BGRLimeMintGreen = (127,245,54)
    BGRSpringGreen = (127,255,0)
    BGRMediumSpringGreen = (154,250,0)
    BGREmeraldGreen = (23,251,95)
    BGRLime = (0,255,0)
    BGRLawnGreen = (0,252,124)
    BGRBrightGreen = (0,255,102)
    BGRChartreuse = (0,255,127)
    BGRYellowLawnGreen = (23,247,135)
    BGRAloeVeraGreen = (22,245,152)
    BGRDullGreenYellow = (23,251,177)
    BGRLemonGreen = (2,248,173)
    BGRGreenYellow = (47,255,173)
    BGRChameleonGreen = (22,245,189)
    BGRNeonYellowGreen = (1,238,218)
    BGRYellowGreenGrosbeak = (22,245,226)
    BGRTeaGreen = (93,251,204)
    BGRSlimeGreen = (84,233,188)
    BGRAlgaeGreen = (134,233,100)
    BGRLightGreen = (144,238,144)
    BGRDragonGreen = (146,251,106)
    BGRPaleGreen = (152,251,152)
    BGRMintGreen = (152,255,152)
    BGRGreenThumb = (170,234,181)
    BGROrganicBrown = (166,249,227)
    BGRLightJade = (184,253,195)
    BGRLightMintGreen = (211,229,194)
    BGRLightRoseGreen = (219,249,219)
    BGRChromeWhite = (212,241,232)
    BGRHoneyDew = (240,255,240)
    BGRMintCream = (250,255,245)
    BGRLemonChiffon = (205,250,255)
    BGRParchment = (194,255,255)
    BGRCream = (204,255,255)
    BGRCreamWhite = (208,253,255)
    BGRLightGoldenRodYellow = (210,250,250)
    BGRLightYellow = (224,255,255)
    BGRBeige = (220,245,245)
    BGRCornsilk = (220,248,255)
    BGRBlonde = (217,246,251)
    BGRChampagne = (206,231,247)
    BGRAntiqueWhite = (215,235,250)
    BGRPapayaWhip = (213,239,255)
    BGRBlanchedAlmond = (205,235,255)
    BGRBisque = (196,228,255)
    BGRWheat = (179,222,245)
    BGRMoccasin = (181,228,255)
    BGRPeach = (180,229,255)
    BGRLightOrange = (177,216,254)
    BGRPeachPuff = (185,218,255)
    BGRCoralPeach = (171,213,251)
    BGRNavajoWhite = (173,222,255)
    BGRGoldenBlonde = (161,231,251)
    BGRGoldenSilk = (195,227,243)
    BGRDarkBlonde = (182,226,240)
    BGRLightGold = (172,229,241)
    BGRVanilla = (171,229,243)
    BGRTanBrown = (182,229,236)
    BGRDirtyWhite = (201,228,232)
    BGRPaleGoldenRod = (170,232,238)
    BGRKhaki = (140,230,240)
    BGRCardboardBrown = (116,218,237)
    BGRHarvestGold = (117,226,237)
    BGRSunYellow = (124,232,255)
    BGRCornYellow = (128,243,255)
    BGRPastelYellow = (132,248,250)
    BGRNeonYellow = (51,255,255)
    BGRYellow = (0,255,255)
    BGRCanaryYellow = (0,239,255)
    BGRBananaYellow = (22,226,245)
    BGRMustardYellow = (88,219,255)
    BGRGoldenYellow = (0,223,255)
    BGRBoldYellow = (36,219,249)
    BGRRubberDuckyYellow = (1,216,255)
    BGRGold = (0,215,255)
    BGRBrightGold = (23,208,253)
    BGRChromeGold = (68,206,255)
    BGRGoldenBrown = (23,193,234)
    BGRDeepYellow = (0,190,246)
    BGRMacaroniandCheese = (102,187,242)
    BGRSaffron = (23,185,251)
    BGRNeonGold = (1,189,253)
    BGRBeer = (23,177,251)
    BGROrangeYellow = (66,174,255)
    BGRYellowOrange = (66,174,255)
    BGRCantaloupe = (47,166,255)
    BGRCheeseOrange = (0,166,255)
    BGROrange = (0,165,255)
    BGRBrownSand = (77,154,238)
    BGRSandyBrown = (96,164,244)
    BGRBrownSugar = (111,167,226)
    BGRCamelBrown = (107,154,193)
    BGRDeerBrown = (131,191,230)
    BGRBurlyWood = (135,184,222)
    BGRTan = (140,180,210)
    BGRLightFrenchBeige = (127,173,200)
    BGRSand = (128,178,194)
    BGRSage = (138,184,188)
    BGRFallLeafBrown = (96,181,200)
    BGRGingerBrown = (98,190,201)
    BGRBronzeGold = (93,174,201)
    BGRDarkKhaki = (107,183,189)
    BGROliveGreen = (108,184,186)
    BGRBrass = (66,166,181)
    BGRCookieBrown = (23,163,199)
    BGRMetallicGold = (55,175,212)
    BGRBeeYellow = (23,171,233)
    BGRSchoolBusYellow = (23,163,232)
    BGRGoldenRod = (32,165,218)
    BGROrangeGold = (23,160,212)
    BGRCaramel = (23,142,198)
    BGRDarkGoldenRod = (11,134,184)
    BGRCinnamon = (23,137,197)
    BGRPeru = (63,133,205)
    BGRBronze = (50,127,205)
    BGRTigerOrange = (65,129,200)
    BGRCopper = (51,115,184)
    BGRDarkGold = (57,108,170)
    BGRMetallicBronze = (66,113,169)
    BGRDarkAlmond = (78,120,171)
    BGRWood = (51,111,150)
    BGROakBrown = (23,101,128)
    BGRAntiqueBronze = (30,93,102)
    BGRHazel = (24,118,142)
    BGRDarkYellow = (0,128,139)
    BGRDarkMoccasin = (57,120,130)
    BGRKhakiGreen = (93,134,138)
    BGRMillenniumJade = (124,145,147)
    BGRDarkBeige = (118,140,159)
    BGRBulletShell = (96,155,175)
    BGRArmyBrown = (96,123,130)
    BGRSandstone = (95,109,120)
    BGRTaupe = (50,60,72)
    BGRMocha = (38,61,73)
    BGRMilkChocolate = (28,59,81)
    BGRGrayBrown = (53,54,61)
    BGRDarkCoffee = (47,47,59)
    BGROldBurgundy = (46,48,67)
    BGRWesternCharcoal = (63,65,73)
    BGRBakersBrown = (23,51,92)
    BGRDarkBrown = (33,67,101)
    BGRSepiaBrown = (20,66,112)
    BGRDarkBronze = (0,74,128)
    BGRCoffee = (55,78,111)
    BGRBrownBear = (59,92,131)
    BGRRedDirt = (23,82,127)
    BGRSepia = (44,70,127)
    BGRSienna = (45,82,160)
    BGRSaddleBrown = (19,69,139)
    BGRDarkSienna = (23,65,138)
    BGRSangria = (23,56,126)
    BGRBloodRed = (23,53,126)
    BGRChestnut = (53,69,149)
    BGRCoralBrown = (56,70,158)
    BGRChestnutRed = (44,74,195)
    BGRMahogany = (0,64,192)
    BGRRedGold = (6,84,235)
    BGRRedFox = (23,88,195)
    BGRDarkBisque = (0,101,184)
    BGRLightBrown = (29,101,181)
    BGRPetraGold = (52,103,183)
    BGRRust = (65,98,195)
    BGRCopperRed = (81,109,203)
    BGROrangeSalmon = (81,116,196)
    BGRChocolate = (30,105,210)
    BGRSedona = (0,102,204)
    BGRPapayaOrange = (23,103,229)
    BGRHalloweenOrange = (44,108,230)
    BGRNeonOrange = (0,103,255)
    BGRBrightOrange = (31,95,255)
    BGRPumpkinOrange = (23,114,248)
    BGRCarrotOrange = (23,128,248)
    BGRDarkOrange = (0,140,255)
    BGRConstructionConeOrange = (49,116,248)
    BGRIndianSaffron = (34,119,255)
    BGRSunriseOrange = (81,116,230)
    BGRMangoOrange = (64,128,255)
    BGRCoral = (80,127,255)
    BGRBasketBallOrange = (88,129,248)
    BGRLightSalmonRose = (107,150,249)
    BGRLightSalmon = (122,160,255)
    BGRDarkSalmon = (122,150,233)
    BGRTangerine = (97,138,231)
    BGRLightCopper = (103,138,218)
    BGRSalmonPink = (116,134,255)
    BGRSalmon = (114,128,250)
    BGRPeachPink = (136,139,249)
    BGRLightCoral = (128,128,240)
    BGRPastelRed = (128,114,246)
    BGRPinkCoral = (113,116,231)
    BGRBeanRed = (89,93,247)
    BGRValentineRed = (81,84,229)
    BGRIndianRed = (92,92,205)
    BGRTomato = (71,99,255)
    BGRShockingOrange = (60,91,229)
    BGROrangeRed = (0,69,255)
    BGRRed = (0,0,255)
    BGRNeonRed = (3,28,253)
    BGRScarletRed = (0,36,255)
    BGRRubyRed = (23,34,246)
    BGRFerrariRed = (26,13,247)
    BGRFireEngineRed = (23,40,246)
    BGRLavaRed = (23,34,228)
    BGRLoveRed = (23,27,228)
    BGRGrapefruit = (31,56,220)
    BGRCherryRed = (65,70,194)
    BGRChilliPepper = (23,27,193)
    BGRFireBrick = (34,34,178)
    BGRTomatoSauceRed = (7,24,178)
    BGRBrown = (42,42,165)
    BGRCarbonRed = (42,13,167)
    BGRCranberry = (15,0,159)
    BGRSaffronRed = (20,19,147)
    BGRCrimsonRed = (0,0,153)
    BGRRedWine = (18,0,153)
    BGRWineRed = (18,0,153)
    BGRDarkRed = (0,0,139)
    BGRVeryDarkRed = (0,0,10) # Pilomar specific color.
    BGRMaroon = (0,0,128)
    BGRBurgundy = (26,0,140)
    BGRVermilion = (27,25,126)
    BGRDeepRed = (23,5,128)
    BGRRedBlood = (0,0,102)
    BGRBloodNight = (6,22,85)
    BGRDarkScarlet = (25,3,86)
    BGRBlackBean = (2,12,61)
    BGRChocolateBrown = (15,0,63)
    BGRMidnight = (23,27,43)
    BGRPurpleLily = (53,10,85)
    BGRPurpleMaroon = (65,5,129)
    BGRPlumPie = (65,5,125)
    BGRPlumVelvet = (82,5,125)
    BGRDarkRaspberry = (87,38,135)
    BGRVelvetMaroon = (77,53,126)
    BGRRosyFinch = (82,78,127)
    BGRDullPurple = (93,82,127)
    BGRPuce = (88,90,127)
    BGRRoseDust = (112,112,153)
    BGRPastelBrown = (127,144,177)
    BGRRosyPink = (129,132,179)
    BGRRosyBrown = (143,143,188)
    BGRKhakiRose = (142,144,197)
    BGRLipstickPink = (147,135,196)
    BGRPinkBrown = (137,129,196)
    BGROldRose = (129,128,192)
    BGRDustyPink = (148,138,213)
    BGRPinkDaisy = (163,153,231)
    BGRRose = (170,173,232)
    BGRDustyRose = (166,169,201)
    BGRSilverPink = (173,174,196)
    BGRGoldPink = (194,199,230)
    BGRRoseGold = (192,197,236)
    BGRDeepPeach = (164,203,255)
    BGRPastelOrange = (139,184,248)
    BGRDesertSand = (175,201,237)
    BGRUnbleachedSilk = (202,221,255)
    BGRPigPink = (228,215,253)
    BGRPalePink = (215,212,242)
    BGRBlush = (232,230,255)
    BGRMistyRose = (225,228,255)
    BGRPinkBubbleGum = (221,223,255)
    BGRLightRose = (205,207,251)
    BGRLightRed = (203,204,255)
    BGRWarmPink = (189,198,246)
    BGRDeepRose = (185,187,251)
    BGRPink = (203,192,255)
    BGRLightPink = (193,182,255)
    BGRSoftPink = (191,184,255)
    BGRDonutPink = (190,175,250)
    BGRBabyPink = (186,175,250)
    BGRFlamingoPink = (176,167,249)
    BGRPastelPink = (170,163,254)
    BGRRosePink = (176,161,231)
    BGRPinkRose = (176,161,231)
    BGRCadillacPink = (174,138,227)
    BGRCarnationPink = (161,120,247)
    BGRPastelRose = (143,120,229)
    BGRBlushRed = (148,110,229)
    BGRPaleVioletRed = (147,112,219)
    BGRPurplePink = (135,101,209)
    BGRTulipPink = (124,90,194)
    BGRBashfulPink = (131,82,194)
    BGRDarkPink = (128,84,231)
    BGRDarkHotPink = (171,96,246)
    BGRHotPink = (180,105,255)
    BGRWatermelonPink = (133,108,252)
    BGRVioletRed = (138,53,246)
    BGRHotDeepPink = (135,40,245)
    BGRBrightPink = (127,0,255)
    BGRDeepPink = (147,20,255)
    BGRNeonPink = (170,53,245)
    BGRChromePink = (170,51,255)
    BGRNeonHotPink = (156,52,253)
    BGRPinkCupcake = (157,94,228)
    BGRRoyalPink = (172,89,231)
    BGRDimorphothecaMagenta = (157,49,227)
    BGRPinkLemonade = (124,40,228)
    BGRRedPink = (85,42,250)
    BGRRaspberry = (93,11,227)
    BGRCrimson = (60,20,220)
    BGRBrightMaroon = (72,33,195)
    BGRRoseRed = (86,30,194)
    BGRRoguePink = (105,40,193)
    BGRBurntPink = (103,34,193)
    BGRPinkViolet = (107,34,202)
    BGRMagentaPink = (139,51,204)
    BGRMediumVioletRed = (133,21,199)
    BGRDarkCarnationPink = (131,34,193)
    BGRRaspberryPurple = (108,68,179)
    BGRPinkPlum = (143,59,185)
    BGROrchid = (214,112,218)
    BGRDeepMauve = (212,115,223)
    BGRViolet = (238,130,238)
    BGRFuchsiaPink = (255,119,255)
    BGRBrightNeonPink = (255,51,244)
    BGRFuchsia = (255,0,255)
    BGRMagenta = (255,0,255)
    BGRCrimsonPurple = (236,56,226)
    BGRHeliotropePurple = (255,98,212)
    BGRTyrianPurple = (236,90,196)
    BGRMediumOrchid = (211,85,186)
    BGRPurpleFlower = (199,74,167)
    BGROrchidPurple = (181,72,176)
    BGRRichLilac = (210,102,182)
    BGRPastelViolet = (188,145,210)
    BGRMauveTaupe = (109,95,145)
    BGRViolaPurple = (126,88,126)
    BGREggplant = (81,64,97)
    BGRPlumPurple = (89,55,88)
    BGRGrape = (128,90,94)
    BGRPurpleNavy = (128,81,78)
    BGRSlateBlue = (205,90,106)
    BGRBlueLotus = (236,96,105)
    BGRBlurple = (242,101,88)
    BGRLightSlateBlue = (255,106,115)
    BGRMediumSlateBlue = (238,104,123)
    BGRPeriwinklePurple = (207,117,117)
    BGRVeryPeri = (171,103,102)
    BGRBrightGrape = (168,45,111)
    BGRPurpleAmethyst = (199,45,108)
    BGRBrightPurple = (173,13,106)
    BGRDeepPeriwinkle = (166,83,84)
    BGRDarkSlateBlue = (139,61,72)
    BGRPurpleHaze = (126,56,78)
    BGRPurpleIris = (126,27,87)
    BGRDarkPurple = (80,1,75)
    BGRDeepPurple = (63,1,54)
    BGRMidnightPurple = (71,26,46)
    BGRPurpleMonster = (126,27,70)
    BGRIndigo = (130,0,75)
    BGRBlueWhale = (126,45,52)
    BGRRebeccaPurple = (153,51,102)
    BGRPurpleJam = (126,40,106)
    BGRDarkMagenta = (139,0,139)
    BGRPurple = (128,0,128)
    BGRFrenchLilac = (142,96,134)
    BGRDarkOrchid = (204,50,153)
    BGRDarkViolet = (211,0,148)
    BGRPurpleViolet = (201,56,141)
    BGRJasminePurple = (236,59,162)
    BGRPurpleDaffodil = (255,65,176)
    BGRClematisViolet = (206,45,132)
    BGRBlueViolet = (226,43,138)
    BGRPurpleSageBush = (199,93,122)
    BGRLovelyPurple = (236,56,127)
    BGRNeonPurple = (255,0,157)
    BGRPurplePlum = (239,53,142)
    BGRAztechPurple = (255,59,137)
    BGRMediumPurple = (219,112,147)
    BGRLightPurple = (215,103,132)
    BGRCrocusPurple = (236,114,145)
    BGRPurpleMimosa = (255,123,158)
    BGRPeriwinkle = (255,204,204)
    BGRPaleLilac = (255,208,220)
    BGRLavenderPurple = (182,123,150)
    BGRRosePurple = (202,159,176)
    BGRLilac = (200,162,200)
    BGRMauve = (255,176,224)
    BGRBrightLilac = (239,145,216)
    BGRPurpleDragon = (199,142,195)
    BGRPlum = (221,160,221)
    BGRBlushPink = (236,169,230)
    BGRPastelPurple = (232,162,242)
    BGRBlossomPink = (255,183,249)
    BGRWisteriaPurple = (199,174,198)
    BGRPurpleThistle = (211,185,210)
    BGRThistle = (216,191,216)
    BGRPurpleWhite = (227,211,223)
    BGRPeriwinklePink = (236,207,233)
    BGRCottonCandy = (255,223,252)
    BGRLavenderPinocchio = (226,221,235)
    BGRDarkWhite = (209,217,225)
    BGRAshWhite = (212,228,233)
    BGRWhiteChocolate = (214,230,237)
    BGRSoftIvory = (221,240,250)
    BGROffWhite = (227,240,248)
    BGRPearlWhite = (240,246,248)
    BGRRedWhite = (234,232,243)
    BGRLavenderBlush = (245,240,255)
    BGRPearl = (244,238,253)
    BGREggShell = (227,249,255)
    BGROldLace = (227,240,254)
    BGRLinen = (230,240,250)
    BGRSeaShell = (238,245,255)
    BGRBoneWhite = (238,246,249)
    BGRRice = (239,245,250)
    BGRFloralWhite = (240,250,255)
    BGRIvory = (240,255,255)
    BGRWhiteGold = (244,255,255)
    BGRLightWhite = (247,255,255)
    BGRWhiteSmoke = (245,245,245)
    BGRCotton = (249,251,251)
    BGRSnow = (250,250,255)
    BGRMilkWhite = (255,252,254)
    BGRHalfWhite = (250,254,255)
    BGRWhite = (255,255,255)
    
    # Define default filter scripts.
    # - You can overwrite this with your own set of scripts by assigning pilomarimage.FILTERSCRIPTS = {.....}
    # - This default script includes some example scripts to test, and also some specific scripts designed to achieve specific image enhancements.
    # - To run a script against the current image buffer call self.RunFilterScript( filtername )
    # -  eg self.RunFilterScript('ExampleThreshold') to run the ExampleThreshold script.
    # The scripts consist of a series of opencv actions that you can run against the current image buffer.
    # A script contains at least 1 action. Actions are executed their sequence in the script. The result is always stored in the current image buffer.
    # Where an action supports parameters those can be defined inside each step in this script.
    # If parameters are not given, defaults will be used.
    FILTERSCRIPTS = {
        'ExampleThreshold':{ # Example script to perform thresholding on an image. Call this with self.RunFilterScript('ExampleThreshold')
            'ThresholdStep':{
                'method':'threshold',
                'threshold':100,
                'maxval':255,
                'type': cv2.THRESH_BINARY,
                'comment': 'Use simple binary threshold to detect any pixels > 100 and consider them to be stars.',
                } # /ThresholdStep
            }, # /ExampleThreshold
        'ExampleDehaze':{ # Example script to remove haze from the background of an image. Call this with self.RunFilterScript('ExampleDehaze')
            'DeHaze': {
                'method': 'dehaze',
                'samples': 1,
                'strength': 100,
                'comment': 'Remove urban haze from the image background.'
                } # /ExampleDehaze
            },
        'ExampleBlur':{ # Example script to perform gaussian blurring on the image. Call this with self.RunFilterScript('ExampleBlur')
            'BlurStep':{
                'method':'gaussianblur',
                'radius':100,
                'comment':'Apply Gaussian blur to widen remaining items',
                } # /BlurStep
            }, # /ExampleBlur
        'ExampleGrayscale':{ # Example script to convert an image to grayscale. Call this with self.RunFilterScript('ExampleGrayscale')
            'GrayStep':{
                'method':'grayscale',
                'comment':'Reduce an image to grayscale.',
                } # /GrayStep
            }, # /ExampleGrayscale
        'EnhanceClouds':{ # Enhance clouds in the image.  Call this with self.RunFilterScript('EnhanceClouds')
            'CloudThreshold':{
                'method':'threshold',
                'threshold':100,
                'maxval':255,
                'type': cv2.THRESH_BINARY,
                'comment': 'Use simple binary threshold to detect any pixels > 100 and consider them to be potential clouds.',
                } # /CloudThreshold
            }, # /CloudDetection
        'EnhanceStars':{ # Enhance stars in the image.  Call this with self.RunFilterScript('EnhanceStars')
            'ToGrayscale':{ # Convert to grayscale image.
                'method':'grayscale',
                }, # /ToGrayscale
            'EliminateClouds':{ # Set low threshold to remove clouds and low level light.
                'method':'threshold',
                'threshold':100,
                'maxval':255,
                'type': cv2.THRESH_BINARY,
                'comment':'Apply low threshold to remove dim objects such as clouds.',
                }, # /EliminateClouds
            'BlurStars':{ # Use blur to enlarge remaining stars.
                'method':'gaussianblur',
                'radius':13,
                'comment':'Apply Gaussian blur to widen remaining items',
                }, # /BlurStars
            'BoostStars':{ # Enhance remaining stars.
                'method':'threshold',
                'threshold':16,
                'maxval':255,
                'type': cv2.THRESH_BINARY + cv2.THRESH_OTSU,
                'comment':'Apply adaptive threshold to boost remaining stars.',
                } # /BoostStars
            }, # /EnhanceStars
        'UrbanFilter':{ # UrbanFilter script. Reduce haze and enhance stars. Call this with self.RunFilterScript('UrbanFilter')
            'ToGrayscale':{ # Convert to grayscale image.
                'method':'grayscale',
                }, # /ToGrayscale
            'DeHaze':{ # Reduce haze across the image.
                'method':'dehaze',
                'samples':1, # Just a single sample value is generated from the entire width of the line.
                'strength':100,
                'comment': 'Remove urban haze from the image background.',
                }, # /DeHaze
            'BlurStars':{ # Use blur to enlarge remaining stars.
                'method':'gaussianblur',
                'radius':2,
                'comment':'Apply Gaussian blur to widen remaining items',
                }, # /BlurStars
            'BoostStars':{ # Enhance remaining stars.
                'method':'threshold',
                'threshold':16,
                'maxval':255,
                'type': cv2.THRESH_BINARY + cv2.THRESH_OTSU,
                'comment':'Apply adaptive threshold to boost remaining stars.',
                } # /BoostStars
            } # /UrbanFilter
    } # /FILTERSCRIPTS
    
    def __init__(self,name=None,logger=None):
        """ Create new image item. 
            name = any arbitrary name for the image.
            width = pixel width.
            height = pixel height.
            depth = image depth (2 = Grayscale, 3 = BGR, 4 = BGRA) 
            datatype = the storage type for each cell. default uint8 = unsigned 8 bit values. """
        self.Name = name
        self.SetLogger(logger) # Any method which supports pilomar's .Log() methods.
        self.LogDrawing = False # Record individual drawing commands in the log file?
        self.Font = cv2.FONT_HERSHEY_SIMPLEX
        self.InvertHeight = False # When set to TRUE, height pixel values are inverted, so they count UP FROM THE BOTTOM instead of DOWN FROM THE TOP.
        self._initialize()
        self.ResetGraph() # Create structures for graphing data.

    def OrientHeight(self,y,height=None):
        """ If InvertHeight is TRUE, invert the value of the 'y' pixel locations.
            This is good to convert a single 'y' dimension.
            If you have a tuple of (x,y) values, use OrientCoord() instead.

            Only apply this to coordinates which are being passed directly to opencv function calls.
            If you apply it to higher level method calls in this class you may end up applying it twice which will cancel the effect out. """
        if self.InvertHeight: # Co-ordinates provided are from BOTTOM UP, convert to TOP DOWN for OpenCV.
            if height == None: height = self.GetHeight()
            y = height - y # Pixel locations count UP instead of DOWN. 
        return int(y)

    def OrientCoord(self,location,yloc=1,angle=0,height=None):
        """ If InvertHeight is TRUE, this returns a coordinate pair with the height dimension inverted. 
            yloc says which entry in the location pair is the height one.
            This converts tuples (x,y) and (y,x) style.
            If you have a single 'y' value, use OrientHeight(y) instead.
            If you specify angle: It's the rotation angle of the image (when using AddAngleText() for example. 90, 270 rotations orient along X axis instead.

            Only apply this to coordinates which are being passed directly to opencv function calls.
            If you apply it to higher level method calls in this class you may end up applying it twice which will cancel the effect out.            """
        if yloc == 1: # y location is at position 1 in the tuple, convert that.
            x = location[0]
            y = self.OrientHeight(location[1])
            r = (x,y)
        else: # y location is at position 0 in the tuple, convert that.
            x = location[1]
            y = self.OrientHeight(location[0])
            r = (y,x)
        return r
        
    def ResetGraph(self):
        """ Create data structure for basic charting/graphing. 
            This also clears any existing graphing data. """
        self.Graph_DataSets = [] # DataPoint = [x,y,color,label,style] # DataSet = list of DataPoint # DataSets = list of DataSet
        self.Graph_Title = 'title'
        self.Graph_XAxisTitle = 'x axis'
        self.Graph_YAxisTitle = 'y axis'
        self.Graph_XMinVal = None # Lowest X value in data points.
        self.Graph_XMaxVal = None # Highest X value in data points.
        self.Graph_YMinVal = None # Lowest Y value in data points.
        self.Graph_YMaxVal = None # Highest Y value in data points.
        self.Graph_XBorder = None # Width of left/right border.
        self.Graph_YBorder = None # Height of top/bottom border.
        self.Graph_XValueSpan = None # Span of X values.
        self.Graph_YValueSpan = None # Span of Y values.
        self.Graph_XTicks = None # Value of X axis ticks.
        self.Graph_YTicks = None # Value of Y axis ticks.
        
    def Interpolate(self,inp1,res1,inp2,res2,inp3):
        """ Linear interpolation from 2 points. """
        inpdelta = inp2 - inp1
        resdelta = res2 - res1
        if inpdelta != 0.0: # Input points are different, so result can be calculated.
            res3 = ((inp3 - inp1) * float(resdelta / inpdelta)) + res1
        else: # 2 input points are the same, result is unknown.
            res3 = res1 # Default to first result.
        return res3

    def MapToGraph(self,xpoint,ypoint):
        """ Given an x/y pair, find the pixel locations on a graph image.
            xpoint and ypoint are the data values stored in the Datasets. """
        x = int(self.Interpolate(self.Graph_XMinVal,self.Graph_XBorder,self.Graph_XMaxVal,self.GetWidth() - self.Graph_XBorder,xpoint)) # Scale it to the size of the canvas.
        y = int(self.Interpolate(self.Graph_YMinVal,self.Graph_YBorder,self.Graph_YMaxVal,self.GetHeight() - self.Graph_YBorder,ypoint)) # Scale it to the size of the canvas.
        return x,y
        
    def DrawXAxis(self):
        """ Draw X axis, scale and label """
        # Draw X scale where Y = 0 or at min Y
        if self.Graph_YMinVal < 0 and self.Graph_YMaxVal > 0: y = 0 # Where does x axis cross Y?
        elif self.Graph_YMaxVal < 0: y = self.Graph_YMaxVal
        else: y = self.Graph_YMinVal
        x1,y1 = self.MapToGraph(self.Graph_XMinVal,y)
        x2,y2 = self.MapToGraph(self.Graph_XMaxVal,y)
        self.DrawLine((x1,y1),(x2,y2),color=pilomarimage.BGRBlack) # x-axis
        # Mark scale.
        i = self.Graph_XMinVal
        while i <= self.Graph_XMaxVal:
            # Mark this location and value.
            x1,y1 = self.MapToGraph(i,y)
            y2 = y1 - 20
            self.DrawLine((x1,y1),(x1,y2),color=pilomarimage.BGRBlack) # Tick mark.
            self.AddText(str(round(i,3)),x1,y1 - 30,color=pilomarimage.BGRBlack,hjust='c',vjust='t')
            i += self.Graph_XTicks
        # Label the axis.
        cx, _ = self.CenterCoordinates()
        self.AddText(self.Graph_XAxisTitle,cx,int(self.Graph_YBorder / 2),color=pilomarimage.BGRBlack,size=2.0,hjust='c',vjust='c',thickness=2)
        return True

    def DrawYAxis(self):
        """ Draw X axis, scale and label """
        # Draw Y scale where X = 0 or at min X
        if self.Graph_XMinVal < 0 and self.Graph_XMaxVal > 0: x = 0 # Where does Y axis cross X?
        elif self.Graph_XMaxVal < 0: x = self.Graph_XMaxVal
        else: x = self.Graph_XMinVal
        x1,y1 = self.MapToGraph(x,self.Graph_YMinVal)
        x2,y2 = self.MapToGraph(x,self.Graph_YMaxVal)
        self.DrawLine((x1,y1),(x2,y2),color=pilomarimage.BGRBlack) # y-axis
        # Mark scale.
        i = self.Graph_YMinVal
        while i <= self.Graph_YMaxVal:
            # Mark this location and value.
            x1,y1 = self.MapToGraph(x,i)
            x2 = x1 - 20
            self.DrawLine((x1,y1),(x2,y1),color=pilomarimage.BGRBlack) # Tick mark.
            self.AddText(str(round(i,3)),x1 - 30,y1,color=pilomarimage.BGRBlack,hjust='r',vjust='c')
            i += self.Graph_YTicks
        # Label the axis.
        _, cy = self.CenterCoordinates()
        self.AddAngleText(self.Graph_YAxisTitle,int(self.Graph_XBorder / 2),cy,color=pilomarimage.BGRBlack,size=2.0,hjust='c',vjust='c',thickness=2,angle=90) # Rotated. Not working smoothly yet.
        return True

    def ListDataSets(self):
        """ Generate a key on the graph.
            List the names of the available data sets in the image. """
        x = self.GetWidth() - self.Graph_XBorder + 50
        self.AddText("Datasets:-",x,self.GetHeight() - 500,color=pilomarimage.BGRBlack)
        for dataset in self.Graph_DataSets:
            self.AddText(dataset.Name,x,self.PrevTextY,color=dataset.Color)
        return True
            
    def Adddata_point(self,name,x,y,color=None,label=None,style=['dot'],xname=None,yname=None,xtolerance=0,ytolerance=0):
        """ Find/add dataset and add this to it. 
            color is specific to this single datapoint. Dataset color is used otherwise.
            xtolerance/ytolerance: point is not added if x,y is closer than this to the previous one. 
            """
        # Check that the named dataset exists.
        foundit = False
        for dataset in self.Graph_DataSets:
            if dataset.Name == name: foundit = True
        if foundit == False: # Dataset does not exist yet, add it.
            dataset = data_set(name)
            self.Graph_DataSets.append(dataset)
        # Check for tolerance limits. Don't add if too close to last entry.
        oktoadd = True
        if xtolerance != 0 or ytolerance != 0:
            for dataset in self.Graph_DataSets:
                if dataset.Name == name:
                    datapointcount = len(dataset.DataPoints)
                    if datapointcount > 0:
                        datapoint = dataset.DataPoints[-1] # Get last point.
                        if abs(datapoint.X - x) < xtolerance and abs(datapoint.Y - y) < ytolerance:
                            oktoadd = False # New point is too close to old point. Don't add it.
        if oktoadd: # Datapoint is OK to add.
            for dataset in self.Graph_DataSets:
                if dataset.Name == name:
                    if color == None: color = dataset.Color # Inherit color from parent dataset.
                    datapoint = data_point(x,y,color,label,style,xname,yname)
                    dataset.Add(datapoint)
        #else: print("pilomarimage.Adddata_point():",x,y,"too close to last point. Ignored.")
        return True
    
    def Adddata_set(self,name,color=None,style=['line']):
        """ Create new dataset. """
        foundit = False
        for dataset in self.Graph_DataSets:
            if dataset.Name == name: foundit = True
        if foundit == False: # Dataset does not exist yet, add it.
            dataset = data_set(name,color,style)
            self.Graph_DataSets.append(dataset)
        result = not foundit
        return result
        
    def AnalyseDataPoints(self):
        # Go through the graph datapoints and extract limits.
        self.Graph_XMinVal = self.Graph_XMaxVal = self.Graph_YMinVal = self.Graph_YMaxVal = None
        if len(self.Graph_DataSets) > 0: # There are datasets to handle.
            for dataset in self.Graph_DataSets: # Data point = [x,y,color,label,style] # DataSet = list of DataPoints, # DataSets = list of DataSets
                if len(dataset.DataPoints) > 0: # There are datapoints to handle.
                    for point in dataset.DataPoints: # Check each point.
                        if self.Graph_XMinVal == None or self.Graph_XMinVal > point.X: self.Graph_XMinVal = point.X
                        if self.Graph_YMinVal == None or self.Graph_YMinVal > point.Y: self.Graph_YMinVal = point.Y
                        if self.Graph_XMaxVal == None or self.Graph_XMaxVal < point.X: self.Graph_XMaxVal = point.X
                        if self.Graph_YMaxVal == None or self.Graph_YMaxVal < point.Y: self.Graph_YMaxVal = point.Y
        if self.Graph_XMinVal == None: # No values were found.
            self.Graph_XMinVal = -1
            self.Graph_XMaxVal = 1
            self.Graph_YMinVal = -1
            self.Graph_YMaxVal = 1
        # Check that each axis does span at least a small distance.
        if self.Graph_XMinVal == self.Graph_XMaxVal: 
            self.Graph_XMinVal -= 1
            self.Graph_XMaxVal += 1
        if self.Graph_YMinVal == self.Graph_YMaxVal: 
            self.Graph_YMinVal -= 1
            self.Graph_YMaxVal += 1
        return True
        
    def EstablishGraphScale(self):
        """ What scale to use on each axis. 
            Where to place tickmarks on each axis. """
        self.Graph_XValueSpan = self.Graph_XMaxVal - self.Graph_XMinVal
        self.Graph_YValueSpan = self.Graph_YMaxVal - self.Graph_YMinVal
        self.Graph_XTicks = self.Graph_XValueSpan / 10
        self.Graph_YTicks = self.Graph_YValueSpan / 10
        return True

    def PlotData(self):
        """ Plot the actual data points on the graph.

            self.X = x
            self.Y = y
            self.Color = color
            self.Label = label
            self.Style = Style
            self.XName = xname
            self.YName = yname
            """
        for dataset in self.Graph_DataSets:
            prevx = None
            prevy = None
            for i,datapoint in enumerate(dataset.DataPoints):
                x,y = self.MapToGraph(datapoint.X,datapoint.Y)
                r = 5
                color = self.SafeColor(datapoint.Color,default=pilomarimage.BGRFuchsia)
                if 'line' in dataset.Style and i > 0: # Line between points.
                    self.DrawLine((prevx,prevy),(x,y),color=self.SafeColor(dataset.Color,default=pilomarimage.BGRCyan))
                if 'dot' in datapoint.Style: # Draw a small dot where the datapoint is.
                    self.FillCircle(x,y,r,color) # Dot on the datapoint.
                if 'point' in datapoint.Style: # Draw a single pixel where the datapoint is.
                    self.SetPixel(x,y,color) # Single pixel at the datapoint.
                prevx = x
                prevy = y
        return True

    def ExportData(self,filename):
        """ Dump the graph data. """
        ft = filename.rindex('.')
        filename = filename[:ft] + ".dat"
        #print("ExportData:",filename)
        if self.Log != None: self.Log("pilomarimage",self.Name,".ExportData:",str(filename),terminal=False)
        with open(filename,'w') as f:
            line = "dataset.Name\t"
            line += "datapoint.X\t"
            line += "datapoint.Y\t"
            line += "datapoint.Label\t"
            line += "datapoint.XName\t"
            line += "datapoint.YName\t"
            line += '\n'
            f.write(line)
            for dataset in self.Graph_DataSets:
                for datapoint in dataset.DataPoints:
                    line = str(dataset.Name) + "\t"
                    line += str(datapoint.X) + "\t"
                    line += str(datapoint.Y) + "\t"
                    line += str(datapoint.Label) + "\t"
                    line += str(datapoint.XName) + "\t"
                    line += str(datapoint.YName) + "\t"
                    line += '\n'
                    f.write(line)
        return True
        
    def PlotGraph(self,height,width,filename,export=False):
        """ Create very simplistic graph.
            If height/width not given, the current buffer is used.
            This is VERY crude! IF you want proper graphing capabilities then install matplotlib!
            This is really to support development/debugging work sometimes while avoiding having to install extra packages.
            export=True means a datafile is dumped too. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".PlotGraph:",str(filename),str(export),terminal=False)
        self.InvertHeight = True # Easier to plot graphs if HEIGHT pixels count from the bottom up.
        # Find axis limits.
        self.AnalyseDataPoints()
        # Establish scale
        self.EstablishGraphScale()
        # Establish graph space
        self.New(height,width,'bgr') # New BGR image.
        self.FillColor(pilomarimage.BGRWhite) # White canvas
        self.Graph_XBorder = int(width * 0.1)
        self.Graph_YBorder = int(height * 0.1)
        self.DrawRectangle((self.Graph_XBorder,self.Graph_YBorder),(width - self.Graph_XBorder,height - self.Graph_YBorder),color=pilomarimage.BGRDarkGray)
        self.DrawXAxis() # Draw X axis on graph.
        self.DrawYAxis() # Draw Y axis on graph.
        x,y = self.CenterCoordinates()
        self.AddText(self.Graph_Title,x,int(height - self.Graph_YBorder / 2),size=3,color=pilomarimage.BGRBlack,thickness=3,hjust='c',vjust='c')
        self.ListDataSets() # Add labels for the available datasets.
        self.PlotData() # Plot the data on the graph.
        self.DrawGraphID() # Write footing information onto the graph.
        # Save the result.
        self.SaveFile(filename)
        if export: self.ExportData(filename) # Export the data.
        self.InvertHeight = False # Revert to counting height locations from the top down.
        return True
        
    def DrawGraphID(self):
        """ Write footing information onto the graph. """
        line = ' pilomarimage.PlotGraph ' + str(datetime.now()).split('.')[0] + ' UTC '
        self.AddText(line,self.GetWidth() - 10, 20, color=pilomarimage.BGRBlack,hjust='r')
        return True
        
    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        self.Logger = logger # Logger instance.
        self.Log = None
        self.ReportException = None # Report exception details to logfile.
        self.RaiseException = None # Report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        if self.Log != None: self.Log("pilomarimage.SetLogger(",self.Name,"): Linked to this log file.",terminal=False)
        return True

    def _initialize(self):
        """ Create default values for the object. 
            This creates initial values for new instances, and also clears them out if you want to reset an existing one. """
        self.ImageBuffer = None # This is the actual OpenCV / Numpy image buffer.
        self.ImageMask = None # Array identifying which cells are occupied and which to ignore.
        self.ImageAccumulator = None # Array of cumulative image values. (For live stacking)
        self.ImageCounter = None # Array of how many values are accumulated into each pixel of self.ImageAccumulator. (For live stacking)
        self.ActionList = [] # List of actions performed on the image.
        self.CreatedTimestamp = self.Now()
        self.ModifiedTimestamp = None
        self.StarList = [] # Was None
        self.StarCount = 0
        self.StarMatchList = None
        self.HorizontalSpread = 0 # % of horizonal spread of stars.
        self.VerticalSpread = 0 # % of vertical spread of stars.
        self.AreaSpread = 0 # % of area spread of stars.
        self.PenColor = None # Default color for drawing.
        self.PenThickness = 1 # Default pen thickness for drawing.
        self.LineType = cv2.LINE_AA # Default line_type for drawing.
        self.ResizeMethod = cv2.INTER_AREA # Which sampling method is used for resizing? (3)
        self.ResizeMethods = [cv2.INTER_NEAREST, # nearest neighbor interpolation technique (0)
                              cv2.INTER_LINEAR, # bilinear interpolation (default) (1)
                              cv2.INTER_AREA, # resampling using pixel area relation (3)
                              cv2.INTER_CUBIC, # bicubic interpolation over 4 x 4 pixel neighborhood (2)
                              cv2.INTER_LANCZOS4] # Lanczos interpolation over 8 x 8 pixel neighborhood (4)
                              # cv2.INTER_LINEAR_EXACT, cv2.INTER_NEAREST_EXACT, cv2.INTER_MAX, cv2.WARP_FILL_OUTLIERS, cv2.WARP_INVERSE_MAP] # (16) Not in this version.
        self.NextTextY = None # When text is printed, this holds the 'y' position of the next line of text if you want to print a block of text.
        self.NextTextX = None # When text is printed, this holds the 'x' position of the next line of text if you want to print a block of text.
        self.PrevTextY = None # When text is printed, this holds the 'y' position of the next line of text if you want to print a block of text going UPWARDS.
        self.PrevTextX = None # When text is printed, this holds the 'x' position of the next line of text if you want to print a block of text goind UPWARDS.
        # Text collision avoidance...
        self.TextList = [] # When text is printed, this holds the co-ordinates of each block of text added [[fromx,fromy,tox,toy],[fromx,fromy,tox,toy],[fromx,fromy,tox,toy],...]
        self.AvoidTextCollisions = False # When TRUE, new text is only created if it doesn't overlap existing text.
        
    def TextCollision(self,fromx,fromy,tox,toy):
        """ Return TRUE if proposed text area collides with an existing one. """
        result = False
        if self.AvoidTextCollisions: # Collision avoidance is active.
            fromx, tox = min(fromx,tox), max(fromx,tox) # Make sure FROM is less than TO
            fromy, toy = min(fromy,toy), max(fromy,toy)
            for items in self.TextList: # Go through existing text items.
                ifx = items[0] # Pull co-ordinates.
                ify = items[1]
                itx = items[2]
                ity = items[3]
                if (tox < ifx or fromx > itx or toy < ify or fromy > ity):
                    # Right side of proposed text is < left side of existing text
                    # Left side of proposed text is > right side of existing text
                    # Top of proposed text is < bottom of existing text
                    # Bottom of proposed text is > top of existing text
                    pass # No collision.
                else: # Collision!
                    result = True
                    break
            if not result: # Text does not collide, we'll at it to the list of allowed text.
                self.TextList.append([fromx,fromy,tox,toy])
        return result

    def CalculateStarSpread(self):
        """ Calculate an approximation for the % of the frame that contains stars. 
            LOW values mean that the stars are not spread out evenly across the frame. 
            HIGH values mean that the stars are spread out more evenly across the frame.
            Sets % value for each axis and the total image. """
        if self.ImageExists() and len(self.StarList) > 0: # There's an image loaded and stars were identified.
            HMin = None # Lowest 'X' position of a star.
            HMax = None # Highest 'X' position of a star.
            VMin = None # Lowest 'Y' position of a star.
            VMax = None # Highest 'Y' position of a star.
            for star in self.StarList: # Each star is a list of [x, y, radius]
                if HMin == None or HMin > star[0]: HMin = star[0]
                if HMax == None or HMax < star[0]: HMax = star[0]
                if VMin == None or VMin > star[1]: VMin = star[1]
                if VMax == None or VMax < star[1]: VMax = star[1]
            self.HorizontalSpread = 100 * (HMax - HMin) / self.GetWidth()
            self.VerticalSpread = 100 * (VMax - VMin) / self.GetHeight()
            self.AreaSpread = 100 * ((self.HorizontalSpread / 100) * (self.VerticalSpread / 100))
            result = True
        else: # There's no image, or no stars were identified.
            self.HorizontalSpread = self.VerticalSpread = self.AreaSpread = 0 # No spread to measure.
            result = False
        return result

    def NextInterpolation(self):
        """ Move on to the next available sampling method. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".NextInterpolation()",terminal=False)
        i = (self.ResizeMethods.index(self.ResizeMethod) + 1) % len(self.ResizeMethods)
        self.ResizeMethod = self.ResizeMethods[i]
        self.ActionList.append(['nextinterpolation',self.ResizeMethod])
        
    def PrevInterpolation(self):
        """ Move back to the previous available sampling method. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".PrevInterpolation()",terminal=False)
        i = (self.ResizeMethods.index(self.ResizeMethod) - 1) % len(self.ResizeMethods)
        self.ResizeMethod = self.ResizeMethods[i]
        self.ActionList.append(['previnterpolation',self.ResizeMethod])
    
    def Now(self):
        """ Return system UTC timestamp. """
        return datetime.now(timezone.utc)
        
    def Clear(self):
        """ Clear the image buffer and related attributes. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".Clear()",terminal=False)
        self._initialize()
        self.ActionList.append(['clear'])
        self.CreatedTimestamp = self.Now()
        self.ModifiedTimestamp = self.Now()
        
    def LoadBuffer(self,imagebuffer):
        """ Import an existing OpenCV/Numpy image buffer. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".LoadBuffer()",terminal=False)
        self.Clear()
        self.ImageBuffer = imagebuffer.copy()
        self.ModifiedTimestamp = self.Now()
        return self.ImageExists()
        
    def AccumulateBuffer(self,buffer):
        """ Accumulate values in a buffer into a running total buffer. 
            buffer is a reference to another pilomarimage instance."""
        if self.Log != None: self.Log("pilomarimage",self.Name,".AccumulateBuffer()",terminal=False)
        if isinstance(self.ImageAccumulator,type(None)): # Initialize accumulator.
            self.ImageAccumulator = np.zeros_like(buffer.ImageBuffer,np.uint16) # Create array of same dimensions, but with larger storage type.
            self.ImageCounter = np.zeros_like(buffer.ImageBuffer,np.uint8) # Create array of same dimensions but with uint8 storage type.
        # Now accumulate the values.
        self.ImageAccumulator.add(self.ImageAccumulator,buffer.ImageBuffer)
        self.ImageCount += 1
        self.ActionList.append(['accumulatebuffer',buffer.Name])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def ResolveAccumulator(self):
        if self.Log != None: self.Log("pilomarimage",self.Name,".ResolveAccumulator()",terminal=False)
        if isinstance(self.ImageAccumulator,type(None)):
            print("pilomarimage.ResolveAccumulator(): ImageAccumulator is not initialised.")
            return False
        # Create fresh image buffer.
        self.ImageBuffer = np.zeros_like(self.ImageAccumulator,np.uint8) # Create array of same dimensions, but with regular image datatype.
        self.ImageBuffer[self.ImageCount != 0] = self.ImageAccumulator / self.ImageCount
        self.ActionList.append(['resolveaccumulator'])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def LoadFile(self,filename):
        """ Load image buffer from disc. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".LoadFile(",filename,")",terminal=False)
        self._initialize()
        self.ImageBuffer = cv2.imread(filename,cv2.IMREAD_COLOR)
        if self.ImageExists():
            self.ImageMask = np.ones_like(self.ImageBuffer,np.uint8) # All cells are active.
            self.ActionList.append(['load',filename])
            self.CreatedTimestamp = self.Now()
            result = True
        else:
            # File didn't load!
            if self.Log != None: self.Log("pilomarimage",self.Name,".LoadFile(",filename,") failed.",terminal=False)
            result = False
        return result

    def ImageFileType(self,filename):
        """ Given a filename, return a lower case file type. """
        return filename.split('.')[-1].lower()

    def SaveFile(self,filename):
        """ Save image buffer to disc.
            To specify the quality for jpeg files you can use a call like this...
                cv2.imwrite(filename,self.ImageBuffer,[int(cv2.IMWRITE_JPEG_QUALITY), 90] # 90% image quality. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".SaveFile(",filename,")",terminal=False)
        if self.ImageExists():
            cv2.imwrite(filename,self.ImageBuffer) # Doesn't report errors very well, beware.
            self.ActionList.append(['save',filename])
        else:
            print("pilomarimage.SaveFile(",filename,"): No ImageBuffer.")
        height,width = self.GetDimensions()
        maxdim = max(height,width) # Which is the largest dimension? Some file formats have limits.
        ift = self.ImageFileType(filename) # What file type are we generating?
        if ift in ['bmp'] and maxdim > 32768: # bmp dimensions can't exceed this size.
            print("pilomarimage.SaveFile(",filename,"): Image dimensions exceed bmp limits.(",height,width,")")
        elif ift in ['jpg','jpeg'] and maxdim > 65535: # jpeg dimensions can't exceed this size.
            print("pilomarimage.SaveFile(",filename,"): Image dimensions exceed jpeg limits.(",height,width,")")
        # Check it worked. Big images fail silently!
        result = False # Failed unless a file exists which contains something.
        if os.path.exists(filename):
            if os.path.getsize(filename) == 0:
                print("pilomarimage.SaveFile(",filename,"): The file exists but it is empty.")
            else:
                result = True
        else:
            print("pilomarimage.SaveFile(",filename,"): The file was not saved.")
        return result

    def ClipImage(self,xstart,ystart,xend,yend):
        """ Clip the image. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".ClipImage(",xstart,ystart,xend,yend,")",terminal=False)
        gt = self.GetType()
        if gt == 'grayscale': self.ImageBuffer = self.ImageBuffer[ystart:yend,xstart:xend]
        else: self.ImageBuffer = self.ImageBuffer[ystart:yend,xstart:xend,:]
        self.ActionList.append(['clip',xstart,ystart,xend,yend])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def ScaleImage(self,scale=None,vscale=None,hscale=None):
        """ Scale the current image buffer by 'scale' ratio.
            scale is applied in both dimensions.
            vscale is applied to vertical only.
            hscale is applied to horizontal only. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".ScaleImage(",scale,")",terminal=False)
        if scale != None: # Same scale in both directions.
            vscale = scale
            hscale = scale
        if vscale <= 0.0:
            print("pilomarimage.ScaleImage(vscale",vscale,") must be > 0.0")
            return False
        if hscale <= 0.0:
            print("pilomarimage.ScaleImage(hscale",hscale,") must be > 0.0")
            return False
        height = int(self.ImageBuffer.shape[0] * vscale)
        width = int(self.ImageBuffer.shape[1] * hscale)
        if self.Log != None: self.Log("pilomarimage",self.Name,".ScaleImage: Dimensions h",height,"w",width,terminal=False)
        self.ImageBuffer = cv2.resize(self.ImageBuffer,(width,height),interpolation=self.ResizeMethod) # Note RESIZE takes (width,height) rather than usual openCV (height,width)!
        self.ActionList.append(['scale',scale,vscale,hscale,(width,height)])
        self.ModifiedTimestamp = self.Now()
        return True
    
    def HorizontalBlurImage(self,band):
        """ Shrink the current image buffer horizontally, averaging the colors. 
            Then return the image buffer to the correct width, blurring that average across the image. 
            band = the pixel width that the image is horizontally compressed to. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".HorizontalBlurImage(",band,")",terminal=False)
        height = int(self.ImageBuffer.shape[0])
        originalwidth = int(self.ImageBuffer.shape[1])
        scale = band / originalwidth
        if scale <= 0.0:
            print("pilomarimage.HorizontalBlurImage(scale",scale,") must be > 0.0")
            return False
        width = int(originalwidth * scale)
        if self.Log != None: self.Log("pilomarimage",self.Name,".HorizontalBlureImage: Dimensions h",height,"w",width,terminal=False)
        self.ImageBuffer = cv2.resize(self.ImageBuffer,(width,height),interpolation=cv2.INTER_AREA) # INTER_AREA better for SHRINKING.
        self.ImageBuffer = cv2.resize(self.ImageBuffer,(originalwidth,height),interpolation=cv2.INTER_LINEAR) # INTER_LINEAR and INTER_CUBIC best for STRETCHING.
        self.ActionList.append(['horizontalblurimage',scale,(width,height)])
        self.ModifiedTimestamp = self.Now()
        return True

    def HorizontalBlurBuffer(self,buffer,band):
        """ Shrink the current image buffer horizontally, averaging the colors. 
            Then return the image buffer to the correct width, blurring that average across the image. 
            buffer = the image buffer to work on.
            band = the pixel width that the image is horizontally compressed to. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".HorizontalBlurBuffer(",band,")",terminal=False)
        height = int(buffer.shape[0])
        originalwidth = int(buffer.shape[1])
        scale = band / originalwidth
        if scale <= 0.0:
            print("pilomarimage.HorizontalBlurBuffer(scale",scale,") must be > 0.0")
            return False
        width = int(originalwidth * scale)
        if self.Log != None: self.Log("pilomarimage",self.Name,".HorizontalBlureImage: Dimensions h",height,"w",width,terminal=False)
        buffer = cv2.resize(buffer,(width,height),interpolation=cv2.INTER_AREA) # INTER_AREA better for SHRINKING.
        buffer = cv2.resize(buffer,(originalwidth,height),interpolation=cv2.INTER_LINEAR) # INTER_LINEAR and INTER_CUBIC best for STRETCHING.
        self.ActionList.append(['horizontalblurimage',scale,(width,height)])
        self.ModifiedTimestamp = self.Now()
        return buffer

    def PercentageBuffer(self,buffer,percentage):
        """ Dim a buffer to input percentage. 
            percentage = 0 : Buffer is fully black. 
            percentage = 50 : Buffer is reduced by 50%. 
            percentage = 100 : Buffer is returned unchanged. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".PercentageBuffer()",terminal=False)
        pc = percentage / 100
        buffer = cv2.multiply(buffer,(pc,pc,pc,1.0))
        return buffer 
        
    def SubtractBuffer(self,buffer):
        """ Subtract 'buffer' from the main image buffer. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".SubtractBuffer()",terminal=False)
        self.ImageBuffer = cv2.subtract(self.ImageBuffer,buffer)
        self.ActionList.append(['subtractbuffer'])
        self.ModifiedTimestamp = self.Now()
        return True
    
    def CloneImage(self,donor):
        """ Make this a copy of some other buffer.
            donor is a reference to another pilomarimage instance. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".CloneImage(",donor.Name,")",terminal=False)
        if isinstance(donor.ImageBuffer,type(None)): self.ImageBuffer = None 
        else: self.ImageBuffer = donor.ImageBuffer.copy()
        if isinstance(donor.ImageMask,type(None)): self.ImageMask = None 
        else: self.ImageMask = donor.ImageMask.copy()
        if isinstance(donor.ImageAccumulator,type(None)): self.ImageAccumulator = None 
        else: self.ImageAccumulator = donor.ImageAccumulator.copy()
        if isinstance(donor.ImageCounter,type(None)): self.ImageCounter = None 
        else: self.ImageCounter = donor.ImageCounter.copy()
        self.ActionList = []
        self.CreatedTimestamp = self.CreatedTimestamp
        self.ModifiedTimestamp = donor.ModifiedTimestamp
        self.StarList = donor.StarList
        self.StarCount = donor.StarCount
        self.ActionList.append(['cloneimage',donor.Name])
        return self.ImageExists()

    def Sharpness(self):
        """ Assess the crispness of an image. 
            Some images will be sharper than others.
            *Q* UNDER DEVELOPMENT! 
            This is a solution found online .... 
            https://stackoverflow.com/questions/28717054/calculating-sharpness-of-an-image (Vektorsoft)
            low return values = More blurred. 
            high return values = More crisp. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".Sharpness()",terminal=False)
        canny = cv2.Canny(self.NewBufferType('grayscale'), 50,250) # Use canny edge detection.
        sharpness = np.mean(canny)
        return sharpness
    
    def CombineImage(self,donor):
        """ Add donor image to this image. 
            Performs simple addition of the two images. 
            Values clipped between 0 and 255 though. """
        tempimage = self.ImageBuffer.copy().astype(np.uint16)
        tempimage = np.add(tempimage,donor)
        tempimage = np.clip(tempimage,0,255).astype(np.uint8) # Clip to uint8 values.
        self.ImageBuffer = tempimage
        self.ActionList.append(['combineimage',donor.Name])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def MergeLayer(self,donor):
        """ Merge a donor image as a new layer on top of the current buffer. 
            *Q* UNDER DEVELOPMENT! 
            Several ways to perform a merge. This is testing a couple of them. 
            Likely to change in the future. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".MergeLayer(",donor.Name,")",terminal=False)
        gt = self.GetType()
        if gt == 'grayscale': # Grayscale images inherit the average of the two arrays.
            self.ImageBuffer = ((self.ImageBuffer + donor.ImageBuffer) / 2).astype(np.uint8)
        elif gt == 'bgr': # BGR images inherit average of the two arrays.
            self.ImageBuffer = ((self.ImageBuffer + donor.ImageBuffer) / 2).astype(np.uint8)
        else: # BGRA can use the 'A' channel to decide how much to inherit.
            b1 = self.ImageBuffer.copy().astype(np.float16) / 255 # Scale everything 0.0 - 1.0
            b2 = donor.ImageBuffer.copy.astype(np.float16) / 255
            alpha = b2[:,:,3] # Extract alpha channel.
            b1[:,:,:3] = b1 * (1 - alpha) # Apply alpha to BGR channels (All X, All Y and 0,1,2 channels. Not Alpha channel (3).
            b2[:,:,:3] = b2 * alpha
            self.ImageBuffer = np.add(b1,b2) # Add two arrays.
            self.ImageBuffer = self.ImageBuffer * 255 # Scale back up to 0-255
            self.ImageBuffer = self.ImageBuffer.astype(np.uint8) # Convert from float back to uint8
        self.ActionList.append(['mergelayer',donor.Name])
        self.ModifiedTimestamp = self.Now()

    def CenterCoordinates(self):
        """ Return current center of the image. """
        x = int(round(self.GetWidth() / 2,0))
        y = int(round(self.GetHeight() / 2,0))
        return x,y

    def RotateCoordinates(self,x,y,angle):
        """ Transpose coordinates to account for image rotating.
            Only supports 0,90,180,270 rotations at the moment. """
        angle = angle % 360 # Convert to 0-359 degrees.
        if angle == 270:
            newx = y
            newy = self.GetHeight() - x
        elif angle == 180:
            newx = self.GetWidth() - x
            newy = self.GetHeight() - y
        elif angle == 90:
            newx = self.GetWidth() - y
            newy = x
        else: # Angle = 0, which means don't rotate anything.
            newx = x
            newy = y
        return newx,newy

    def CenterVectorToPixel(self, PixDist, PixAngle):
        """ Given ANGLE and PIXEL DISTANCE from current centre of image, return the resulting point. """
        FromX, FromY = self.CenterCoordinates()
        ToX, ToY = self.VectorToPixel(FromX, FromY, PixDist, PixAngle)
        return ToX, ToY

    def VectorToPixel(self, FromX, FromY, PixDist, PixAngle): # 0 references.
        """ Given ANGLE and PIXEL DISTANCE from 1 point, return the resulting point. """
        rad = math.radians(PixAngle)
        ToX = int(FromX + PixDist * math.sin(rad))
        ToY = int(FromY - PixDist * math.cos(rad)) # Y is inverted.
        return ToX, ToY

    def CalculateVector(self, FromX, FromY, ToX, ToY): # 4 references.
        """ Return ANGLE and PIXEL DISTANCE from 1 point to another. """
        XDist = ToX - FromX
        YDist = FromY - ToY # Y values are inverted Y=0 at top.
        PixDist = round(math.sqrt((XDist ** 2) + (YDist ** 2)),0)
        PixAngle = round(math.degrees(math.atan2(XDist,YDist)),0)
        return PixDist, PixAngle

    def RotateAboutCenter(self,x,y,angle):
        """ Take any point in the image and rotate it about the center of the image. """
        pixd, pixa = self.PixelToCenterVector(x,y)
        pixa += angle
        cx, cy = self.CenterCoordinates()
        x,y = self.VectorToPixel(cx, cy, pixd, pixa)
        return x,y
    
    def PixelToCenterVector(self, ToX, ToY): # 0 references.
        """ Given any pixel location in an image, return its vector relative to the center of the image.
            Image UP (Y=0) is 0 Degrees.
            Image RIGHT (X=Max) is 90 Degrees.
            Image DOWN (Y=Max) is 180 Degrees.
            Image LEFT (X=0) is 270 Degrees. """
        cx, cy = self.CenterCoordinates()
        PixDist, PixAngle = self.CalculateVector(cx, cy, ToX, ToY)
        return PixDist, PixAngle

    def ContainsMeteors(self):
        """ Return TRUE if meteors or aircraft trails are detected in an image. """
        if len(self.LineDetection()) > 0: return True
        else: return False

    def LineDetection(self):
        """ Detect lines (satellites, meteors). """
        if self.Log != None: self.Log("pilomarimage",self.Name,".LineDetection()",terminal=False)
        # Code based upon https://www.meteornews.net/2020/05/05/d64-nl-meteor-detecting-project/
        # Make a gray-scale copy and save the result in the variable 'gray'
        gray = self.NewBufferType('grayscale')
        # Apply blur and save the result in the variable 'blur'
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        # Apply the Canny edge algorithm
        canny = cv2.Canny(blur, 100, 200, 3)
        # The Hough line detection algorithm.
        lines = cv2.HoughLinesP(canny, 1, np.pi/180, 25, minLineLength=50, maxLineGap=5)
        linereturn = [] # The list of selected lines that will be returned.
        longest = 0 # Length of longest line.
        if type(lines) != type(None): # We have something to process.
            for i,line in enumerate(lines): # Check each detected line in turn.
                x1, y1, x2, y2 = line[0] # Coordinates of each end of the line.
                length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) # Length of the line.
                if length < 10: continue # Too short.
                if self.Log != None: self.Log("astrocamera",self.Name,".LineDetection: Line", i, ",", line[0], ", length", length,terminal=False)
                longest = max(length,longest) # Is this the longest line found so far?
                linereturn.append([x1,y1,x2,y2]) # Add to the list of detected lines.
        return linereturn

    def CloudDetection(self,threshold=127): # In pilomarimage
        """ Detect clouds in image. 
            *Q* UNDER DEVELOPMENT 
            threshold = minimum brightness at which a pixel could be a cloud. """
        cloudlist = []
        mincloudpixels = 400
        # Simplify image
        # - Grayscale
        imagebuffer = self.NewBufferType('grayscale') # Convert to grayscale.
        cv2.imwrite('/home/pi/pilomar/data/CloudDetectionGrayscale.jpg',imagebuffer)
        # - Blur
        imagebuffer = cv2.GaussianBlur(imagebuffer,(5,5),0)
        cv2.imwrite('/home/pi/pilomar/data/CloudDetectionBlurred.jpg',imagebuffer)
        # - Threshold
        ret,imagebuffer = cv2.threshold(imagebuffer,threshold,255,0)
        cv2.imwrite('/home/pi/pilomar/data/CloudDetectionThreshold.jpg',imagebuffer)
        # Analyse image
        contours = cv2.findContours(imagebuffer,1,2)
        for contour in contours:
            moments = cv2.moments(contour)
            center_x = int(moments['m10']/moments['m00'])
            center_y = int(moments['m01']/moments['m00'])
            area = int(moments['m00']) # Contour area.
            if area > mincloudpixels: 
                cloudlist.append([center_x,center_y,area])
                if self.Log != None: self.Log("astrocamera",self.Name,".CloudDetection (",center_x,",",center_y,")",area,"pixels",terminal=False)
        return cloudlist
    
    def GetType(self):
        """ Are we dealing with grayscale, bgr or bgra image? """
        result = None
        if type(self.ImageBuffer) == type(None):
            result = None
        elif len(self.ImageBuffer.shape) < 3:
            result = 'grayscale'
        elif self.ImageBuffer.shape[2] == 3:
            result = 'bgr'
        elif self.ImageBuffer.shape[2] == 4:
            result = 'bgra'
        return result

    def ImageAge(self):
        """ Return age of the image buffer in seconds. """
        td = None
        if self.CreatedTimestamp != None: td = int((self.NowUTC() - self.CreatedTimestamp).total_seconds())
        return td
        
    def NewBufferType(self,newtype):
        """ Turn current ImageBuffer into a new type, but return as new buffer,
            doesn't overwrite the original image buffer. """
        cvimagebuffer = self.ImageBuffer.copy()
        if not newtype in pilomarimage.IMAGETYPES:
            if self.Log != None: self.Log("pilomarimage",self.Name,".ChangeType(",newtype,") must be in ",pilomarimage.IMAGETYPES,terminal=False)
            return cvimagebuffer
        oldtype = self.GetType()
        if oldtype == 'bgra':
            if newtype == 'bgr': cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGRA2BGR)
            elif newtype == 'grayscale': cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGRA2GRAY)
        elif oldtype == 'bgr':
            if newtype == 'bgra': cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2BGRA)
            elif newtype == 'grayscale': cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_BGR2GRAY)
        elif oldtype == 'grayscale':
            if newtype == 'bgr': cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_GRAY2BGR)
            elif newtype == 'bgra': cvimagebuffer = cv2.cvtColor(cvimagebuffer, cv2.COLOR_GRAY2BGRA)
        checktype = None
        if type(cvimagebuffer) == type(None):
            checktype = None
        elif len(cvimagebuffer.shape) < 3:
            checktype = 'grayscale'
        elif cvimagebuffer.shape[2] == 3:
            checktype = 'bgr'
        elif cvimagebuffer.shape[2] == 4:
            checktype = 'bgra'
        if checktype != newtype:
            if self.Log != None: self.Log("pilomarimage",self.Name,".ChangeType: Failed. From",oldtype,"to",newtype,"Found",checktype,terminal=False)
        return cvimagebuffer
        
    def ChangeType(self,newtype):
        """ Change ImageBuffer type. """
        self.ImageBuffer = self.NewBufferType(newtype)
        self.ImageMask = np.ones_like(self.ImageBuffer,np.uint8)
        self.ActionList.append(['changetype',self.GetType()])
        return True

    def GetHeight(self):
        """ Return the ImageBuffer height in pixels. """
        height = self.ImageBuffer.shape[0]
        return height
        
    def GetWidth(self):
        """ Return the ImageBuffer width in pixels. """
        width = self.ImageBuffer.shape[1]
        return width

    def GetDepth(self):
        """ Return the ImageBuffer depth in pixels. """
        if len(self.ImageBuffer.shape) < 3: # Grayscale
            depth = 1
        else: depth = self.ImageBuffer.shape[2] # BGR = 3 or BGRA = 4
        return depth

    def GetDimensions(self):
        """ Return the ImageBuffer dimensions in pixels. """
        return (self.GetHeight(),self.GetWidth())
    
    def GetPixelColor(self,y,x):
        """ Return color of pixel.
            y = row
            x = column
            Converts datatype to int() """
        tg = self.GetType()
        #if tg == 'grayscale': color = (int(self.ImageBuffer[x,y]),int(self.ImageBuffer[x,y]),int(self.ImageBuffer[x,y]))
        #else: color = (int(self.ImageBuffer[x,y,0]),int(self.ImageBuffer[x,y,1]),int(self.ImageBuffer[x,y,2]))
        try:
            if tg == 'grayscale': color = (int(self.ImageBuffer[y,x]),int(self.ImageBuffer[y,x]),int(self.ImageBuffer[y,x]))
            else: color = (int(self.ImageBuffer[y,x,0]),int(self.ImageBuffer[y,x,1]),int(self.ImageBuffer[y,x,2]))
        except Exception as e:
            if self.Log != None: 
                self.Log("pilomarimage.GetPixelColor(",self.Name,",row",y,",col",x,") failed.",terminal=False)
                self.ReportException(e,comment='pilomarimage.GetPixelColor()')
            color = (0,0,0)
        return color
    
    def New(self,height,width,imagetype='bgr',datatype=np.uint8):
        """ Create a new empty ImageBuffer. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".New(",height,width,imagetype,datatype,")",terminal=False)
        if not imagetype in pilomarimage.IMAGETYPES:
            if self.Log != None: self.Log("pilomarimage",self.Name,".New(",imagetype,") must be in ",pilomarimage.IMAGETYPES,terminal=False)
            else: print("pilomarimage",self.Name,".New(",imagetype,") must be in ",pilomarimage.IMAGETYPES)
            return False
        if max(height,width) > 65535: # Maximum jpeg size.
            if self.Log != None: self.Log("pilomarimage: Dimensions exceed jpeg limits (",height,width,").",terminal=False)
        if imagetype == 'bgr': self.ImageBuffer = np.zeros((height,width,3), datatype) # bgr image.
        elif imagetype == 'bgra': self.ImageBuffer = np.zeros((height,width,4), datatype) # bgra image.
        else: self.ImageBuffer = np.zeros((height,width), datatype) # grayscale image.
        self.ImageMask = np.ones_like(self.ImageBuffer,np.uint8)
        self.CreatedTimestamp = self.Now()
        self.ModifiedTimestamp = self.Now()
        self.ActionList = [['new',(height,width),imagetype,datatype]]
        return True

    def ArrangeObjects(self, positions, objects, attractions, k=0.1, dt=0.1, iterations=100, delta_min=4.0):
        """
        Arrange Objects on an image using basic physics model (attractive and repulsive forces).
        This is a force directed model for distributing objects, it only avoids overlaps, it doesn't equally space items out.
        
        :param positions: List of [x, y] initial positions of the Objects. [[x,y],...]
        :param objects: List of object sizes as [[width, height , fixed],...]
            : width: pixel width of object.
            : height: pixel height of object.
            : fixed: boolean to say this object cannot move.
        :param attractions: List of objects which are attracted to each other [[obj1, obj2],...].
        :param k: Repulsive constant
        :param dt: Time step for simulation
        :param iterations: Sets limit on time spent finding a solution.
        :param delta_min: When the largest movement in an iteration falls below this number of pixels, the loop terminates.
        :return: List of new object positions as [[x, y],...]
        
        """
        # The basis of this code was generated by Bing ChatGPT Sep.2023.
        width = self.GetWidth()
        height = self.GetHeight()
        
        # Initialize label positions at the object positions
        object_positions = np.array(positions,dtype=np.float)

        # Iteratively apply forces to the object list until the locations stabilise.
        for m in range(iterations): # Set limit to processing.
            
            # Note the positions at the start of the iteration.
            previous_positions = object_positions.copy()
            
            # Compute the force matrix between all pairs of objects
            forces = np.zeros_like(object_positions)
            
            # Calculate repulsive forces between objects.
            for i in range(len(objects)):
                for j in range(i+1, len(objects)):
                    # Compute the overlap between objects i and j
                    object_i = objects[i] # Retrieve object attributes.
                    object_j = objects[j]
                    object_i_fixed = object_i[2] # Can the object move?
                    object_j_fixed = object_j[2]  # Can the object move?
                    overlap_x = max(0, (object_i[0] + object_j[0])/2 - abs(object_positions[i][0] - object_positions[j][0]))
                    overlap_y = max(0, (object_i[1] + object_j[1])/2 - abs(object_positions[i][1] - object_positions[j][1]))
                    
                    # If there is an overlap, apply a repelling force
                    if overlap_x > 0 and overlap_y > 0:
                        direction = object_positions[i] - object_positions[j] # Subtract [j] positions from [i] positions.
                        direction /= np.linalg.norm(direction) # Convert to -1.0 <> 1.0 direction (array of (x,y) still).
                        force = direction * overlap_x * overlap_y * k # Apply force to both axes (x,y).
                        if object_i_fixed == False: forces[i] += force # Apply force if object can move.
                        if object_j_fixed == False: forces[j] -= force # Apply force if object can move.
            
            # Apply a spring force between any attracted objects.
            for i in range(len(attractions)): # Go through the list of attractions.
                index_a = attractions[i][0] # Find the two objects being attracted to each other.
                index_b = attractions[i][1]
                object_a = objects[index_a] # Get the object attributes.
                object_b = objects[index_b]
                position_a = object_positions[index_a] # Get the object positions.
                position_b = object_positions[index_b]
                object_a_fixed = object_a[2] # Can the object move?
                object_b_fixed = object_b[2] # Can the object move?
                displacement = position_a - position_b
                dk = displacement * k
                if object_a_fixed == False: forces[index_a] = forces[index_a] - dk # Apply attraction forces.
                if object_b_fixed == False: forces[index_b] = forces[index_b] + dk
            
            # Update the label positions using the computed forces
            fd = forces * dt
            object_positions = object_positions + fd
            
            # Keep the objects within the image bounds
            for i in range(len(objects)):
                object_positions[i][0] = min(max(object_positions[i][0], objects[i][0]/2), width - objects[i][0]/2)
                object_positions[i][1] = min(max(object_positions[i][1], objects[i][1]/2), height - objects[i][1]/2)

            delta = 0 # What's the largest move detected after this iteration?
            for i,origpos in enumerate(previous_positions): # Check how far each object has moved in this iteration.
                newpos = object_positions[i]
                move = ( ( (newpos[0] - origpos[0]) ** 2) + ( (newpos[1] - origpos[1]) ** 2)) ** 0.5
                delta = max(move, delta) # Keep the largest move detected so far.
            if delta < delta_min: break # Stable solution found, nothing is moving enough.
        
        return object_positions.tolist() # Return updated position list.
    
    def SeparateObjects(self, positions, objects, k=0.1, dt=0.1, iterations=100, delta_min=4.0):
        """
        Arrange Objects on an image without overlapping using physics calculations.
        !! This is NOT a full force-directed model. It just reduces overlaps.
        
        :param positions: List of [[x, y],...] initial positions of the Objects.
        :param objects: List of object sizes as [[width, height , fixed],...]
            : width: pixel width of object.
            : height: pixel height of object.
            : fixed: boolean to say this object cannot move.
        :param k: Repulsive constant
        :param dt: Time step for simulation
        :param iterations: Sets limit on time spent finding a solution.
        :param delta_min: When the largest movement in an iteration falls below this number of pixels, the loop terminates.
        :return: List of new object positions as [[x, y],...]
        
        """
        # The basis of this code was generated by Bing ChatGPT Sep.2023.
        width = self.GetWidth()
        height = self.GetHeight()
        
        # Initialize label positions at the object positions
        object_positions = np.array(positions,dtype=np.float)

        # Compute the distance matrix between all pairs of objects
        # pdist() generates a 'compressed' matrix of the distances between each object.
        # squareform() converts the compressed matrix into a 'redundant' matrix, but it's easier to find the distances between specific objects in this format.
        # distances = squareform(pdist(object_positions)) # Calculated in ChatGPT but not used.
        for m in range(iterations): # Set limit to processing.
            
            # Note the positions at the start of the iteration.
            previous_positions = object_positions.copy()
            
            # Compute the force matrix between all pairs of objects
            forces = np.zeros_like(object_positions)
            
            # Calculate repulsive forces between objects.
            for i in range(len(objects)):
                for j in range(i+1, len(objects)):
                    # Compute the overlap between objects i and j
                    object_i = objects[i]
                    object_j = objects[j]
                    object_i_fixed = object_i[2] 
                    object_j_fixed = object_j[2] 
                    overlap_x = max(0, (object_i[0] + object_j[0])/2 - abs(object_positions[i][0] - object_positions[j][0]))
                    overlap_y = max(0, (object_i[1] + object_j[1])/2 - abs(object_positions[i][1] - object_positions[j][1]))
                    
                    # If there is an overlap, apply a repelling force
                    if overlap_x > 0 and overlap_y > 0:
                        direction = object_positions[i] - object_positions[j] # Subtract [j] positions from [i] positions.
                        direction /= np.linalg.norm(direction) # Convert to -1.0 <> 1.0 direction (array of (x,y) still).
                        force = direction * overlap_x * overlap_y * k # Apply force to both axes (x,y).
                        if object_i_fixed == False: forces[i] += force # Apply force if object can move.
                        if object_j_fixed == False: forces[j] -= force # Apply force if object can move.
            
            # Apply a spring force to attract the label to the object
            for i in range(len(objects)):
                displacement = object_positions[i] - positions[i]
                dk = displacement * k
                forces[i] = forces[i] - dk
            
            # Update the label positions using the computed forces
            fd = forces * dt
            object_positions = object_positions + fd
            
            # Keep the objects within the image bounds
            for i in range(len(objects)):
                object_positions[i][0] = min(max(object_positions[i][0], objects[i][0]/2), width - objects[i][0]/2)
                object_positions[i][1] = min(max(object_positions[i][1], objects[i][1]/2), height - objects[i][1]/2)

            delta = 0 # What's the largest move detected after this iteration?
            for i,origpos in enumerate(previous_positions): # Check how far each object has moved in this iteration.
                newpos = object_positions[i]
                move = ( ( (newpos[0] - origpos[0]) ** 2) + ( (newpos[1] - origpos[1]) ** 2)) ** 0.5
                delta = max(move, delta) # Keep the largest move detected so far.
            #print ("SeparateObjects_full: m",m,"delta",delta)
            if delta < delta_min: break # Stable solution found, nothing is moving enough.
        
        return object_positions.tolist()# , max_overlap # Return updated position list & a measure of the maximum overlap.
        
    def RotateBufferAboutPoint(self,imagebuffer,location,angle):
        """ WIP: Building better angle text feature.
                location is (x,y) tuple

            Based upon code sample from https://theailearner.com/2020/11/02/how-to-write-rotated-text-using-opencv-python/ """
        # *Q* Just a holder for a code snippet while under development.
         
        # Rotate the image using cv2.warpAffine()
        M = cv2.getRotationMatrix2D(location, angle, 1)
        imagebuffer = cv2.warpAffine(imagebuffer, M, (imagebuffer.shape[1], imagebuffer.shape[0]))
        return imagebuffer

    def OverlayBuffer(imagebuffer, overlaybuffer, x, y):
        """ WIP: Building better overlay/merge function.
            Based upon https://stackoverflow.com/questions/40895785/using-opencv-to-overlay-transparent-image-onto-another-image 
            Take an overlaybuffer with transparency and apply it to the imagebuffer. 
            imagebuffer is the original image that the overlay is applied to.
            overlaybuffer is the image to be placed on top of imagebuffer.
            overlaybuffer supports transparency channel (such as bgra format) 
            x,y are the co-ordinates where the overlay will be placed on the original image. """

        imagebuffer_width = imagebuffer.shape[1]
        imagebuffer_height = imagebuffer.shape[0]
        if x >= imagebuffer_width or y >= imagebuffer_height: # overlay is off the edge of the image.
            return imagebuffer
        h, w = overlaybuffer.shape[0], overlaybuffer.shape[1] # Size of overlay.
        if x + w > imagebuffer_width: # Clip overlay if it doesn't all fit.
            w = imagebuffer_width - x
            overlaybuffer = overlaybuffer[:, :w, :]
        if y + h > imagebuffer_height: # Clip overlay if it doesn't all fit.
            h = imagebuffer_height - y
            overlaybuffer = overlaybuffer[:h, :, :]
        if overlaybuffer.shape[2] < 4: # No transparency so just combine the two images directly.
            overlaybuffer = np.concatenate(
                [
                    overlaybuffer,
                    np.ones((overlaybuffer.shape[0], overlaybuffer.shape[1], 1), dtype = overlaybuffer.dtype) * 255
                ],
                axis = 2,
            )
        overlaybuffer_image = overlaybuffer[..., :3] # Get the bgr channels of the overlay.
        mask = overlaybuffer[..., 3:] / 255.0 # Create a mask per pixel of the overlay based upon transparency of each pixel.
        # Apply the overlay.
        imagebuffer[y:y+h, x:x+w] = (1.0 - mask) * imagebuffer[y:y+h, x:x+w] + mask * overlaybuffer_image
        return imagebuffer
    
    def RotateImage(self,angle):
        """ Accepts 0,90,180,270 """
        if self.Log != None: self.Log("pilomarimage",self.Name,".RotateImage(",angle,")",terminal=False)
        angle = angle % 360 # Always in range 0-360 degrees.
        if angle >= 45 and angle < 135: rotateCode = cv2.ROTATE_90_CLOCKWISE
        elif angle >= 135 and angle < 225: rotateCode = cv2.ROTATE_180
        elif angle >= 225 and angle < 315: rotateCode = cv2.ROTATE_90_COUNTERCLOCKWISE
        else: rotateCode = None
        if rotateCode != None:
            self.ImageBuffer = cv2.rotate(self.ImageBuffer, rotateCode)
            self.ModifiedTimestamp = self.Now()
            self.ActionList.append(['rotateimage',angle])
        return True
        
    def CountStars(self,minval=3,maxval=650,maxstars=500,threshold=100):
        """ Count the number of stars in an image. 
            From: https://stackoverflow.com/questions/48154642/how-to-count-number-of-dots-in-an-image-using-python-and-opencv

            Doesn't modify ImageBuffer. 
            
            minval = Minimum area of stars. 
            maxval = Maximum area of stars. 
            maxstars = Maximum number of stars to return .
            threshold = The brightness level (0-255) above which something is considered a star. """
            
        if self.Log != None: self.Log("pilomarimage",self.Name,".CountStars(",minval,',',maxval,")",terminal=False)
        cvimagebuffer = self.NewBufferType('grayscale') # Return a copy of the image buffer in grayscale.
        # Threshold the image to make it more crisp.
        temp, threshed = cv2.threshold(cvimagebuffer, threshold, 255, cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
        # findcontours to identify 'dots' (contours) in the image. This will recognise STARS and also some patterns made by stars. So it needs filtering.
        dots = cv2.findContours(threshed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[-2]
        # filter the 'dots' by their area. Small ones are stars, large ones are some other artifact.
        starcount = 0
        starlist = []
        for dot in dots: # Check each dot in turn.
            if minval < cv2.contourArea(dot) < maxval: # We only want small dots to count as stars.
                starcount += 1 # Increment count.
                dot_x, dot_y, dot_w, dot_h = cv2.boundingRect(dot) # Bordering rectangle of dot.
                dot_radius = int((dot_w + dot_h) / 4) # Half average of width and height.
                ctr_x = int(dot_x + dot_w / 2) # x center of dot.
                ctr_y = int(dot_y + dot_h / 2) # y center of dot.
                staritem = [ctr_x, ctr_y, dot_radius]
                starlist.append(staritem) # Construct list of star locations.
            if starcount >= maxstars:
                if self.Log != None: self.Log("pilomarimage",self.Name,".CountStars:",maxstars,"star limit hit.",terminal=False)
                break
        self.StarList = starlist
        self.StarCount = starcount
        self.CalculateStarSpread() # How widely spread are the stars across the image? Indicates good/bad tracking tuning.
        if self.Log != None: self.Log("pilomarimage",self.Name,".CountStars: End. Counted",starcount,terminal=False)
        return starcount, starlist

    def BVrange(self,BV):
        # Given a B-V value, pick the pair of pilomarimage.COLORPOINTS that will be used to calculate the RGB equivalent.
        fromi = 0
        toi = 1 # If BV is too low, we use the lowest pair of entries. (We will extrapolate a value)
        try:
            for i,cp in enumerate(pilomarimage.COLORPOINTS): # Consider each sample point in turn.
                if BV >= cp[0]: # Above lower threshold of this sample point.
                    fromi = i # Interpolation starts with this lower entry.
                    toi = i + 1 # Interpolation ends with the next entry.
            if toi >= len(pilomarimage.COLORPOINTS): # If BV is too high, we are off the end of the list, so use the highest pair of entries.
                toi = len(pilomarimage.COLORPOINTS) - 1
                fromi = toi - 1
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage",self.Name,".BVRange:",str(BV),"failed:",str(e),level='error')
            fromi = 0
            toi = 1
        return fromi, toi

    def BVdX(self,fromi,toi):
        # Span of BV values from LOWER to UPPER sample limits.
        try:
            result = pilomarimage.COLORPOINTS[toi][0] - pilomarimage.COLORPOINTS[fromi][0]
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage",self.Name,".BVdX:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVdR(self,fromi,toi):
        # Span of BLUE channel values from LOWER to UPPER sample limits.
        try:
            result = pilomarimage.COLORPOINTS[toi][1][0] - pilomarimage.COLORPOINTS[fromi][1][0]
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage",self.Name,".BVdR:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVdG(self,fromi,toi):
        # Span of GREEN channel values from LOWER to UPPER sample limits.
        try:
            result = pilomarimage.COLORPOINTS[toi][1][1] - pilomarimage.COLORPOINTS[fromi][1][1]
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage",self.Name,".BVdG:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVdB(self,fromi,toi):
        # Span of BLUE channel values from LOWER to UPPER sample limits.
        try:
            result = pilomarimage.COLORPOINTS[toi][1][2] - pilomarimage.COLORPOINTS[fromi][1][2]
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage.",self.Name,"BVdB:",str(fromi),str(toi),"failed:",str(e),level='error')
            result = 0
        return result

    def BVInterpolate(self,BV,fromi,toi):
        try:
            BVProportion = (BV - pilomarimage.COLORPOINTS[fromi][0]) / BVdX(fromi,toi) # Position of our point between the two reference points. This is the scale applied to R,G,B channels.
            r = round((BVProportion * BVdR(fromi,toi)) + pilomarimage.COLORPOINTS[fromi][1][0],0) # Scale RED channel relative to the BV position.
            r = max(0,r) # Colour channel values must be 0-255
            r = min(255,r)
            g = round((BVProportion * BVdG(fromi,toi)) + pilomarimage.COLORPOINTS[fromi][1][1],0) # Scale GREEN channel relative to the BV position.
            g = max(0,g)
            g = min(255,g)
            b = round((BVProportion * BVdB(fromi,toi)) + pilomarimage.COLORPOINTS[fromi][1][2],0) # Scale BLUE channel relative to the BV position.
            b = max(0,b)
            b = min(255,b)
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage.",self.Name,"BVInterpolate:",str(BV),str(fromi),str(toi),"failed:",str(e),level='error')
            r = b = g = 255
        return (int(b),int(g),int(r))

    def BVtoBGR(self,BV): # 1 references.
        """ Convert a B-V color value from Hipparcos catalog to an approximate BGR color code.
            B-V     R G B (hex)
            -0.33   706ffe
            -0.3    519ffe
            -0.02   bfd0ff
            0.3     cdfdff
            0.58    eeffdf
            0.81    ffff7f
            1.40    fe7f7d
        """
        r = g = b = 255
        try:
            fromi, toi = self.BVrange(BV) # Which pair of sample colour points do we interpolate from?
            b,g,r = self.BVInterpolate(BV,fromi,toi)
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage.",self.Name,"BVtoBGR:",str(BV),"failed:",str(e),level='warning')
            b = g = r = 255
        return (b,g,r)
    
    def MarkLocation(self,starx,stary,color,uppertext=None,lowertext=None):
        """ Write the location text next to the star.
            Places the text left/right depending upon it's location in the image.
            Write any 'text' value above center of star. """
        starx = int(starx)
        stary = int(stary)
        if starx < (self.GetWidth() / 2): xloc = starx + 10
        else: xloc = starx - 120
        yloc = stary
        loctext = "(" + str(starx) + "," + str(stary) + ")"
        self.AddText(loctext,xloc,yloc,color,0.5)
        if uppertext != None: # There's additional info to print above the star.
            self.AddText(uppertext,starx - 10,yloc - 20,color,0.5)
        if lowertext != None: # There's additional info to print above the star.
            self.AddText(lowertext,starx - 10,yloc + 30,color,0.5)
        return True

    def ScaleStarList(self,scalefactor):
        """ Take a list of star locations and scale the first two terms.
            Any additional terms are left unmodified. 
            Each star in the list consists of x,y image positions.
                [xpos,ypos] 
            Only the xpos and ypos entries are scaled, any extra terms remain unchanged. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".ScaleStarList: Scale:",scalefactor,terminal=False)
        newlist = [] # The resulting list.
        for star in self.StarList: # Go through each star in turn.
            newstar = []
            for i,term in enumerate(star):
                if i < 2: newterm = term * scalefactor
                else: newterm = term
                newstar.append(int(newterm))
            newlist.append(newstar)
        self.StarList = newlist
        self.ActionList = [['scalestarlist',scalefactor]]
        if self.Log != None: self.Log("pilomarimage",self.Name,".ScaleStarList: Result:",newlist,terminal=False)
        return True
        
    def ImageExists(self):
        """ Return True if the ImageBuffer is initialised. """
        if isinstance(self.ImageBuffer,type(None)): return False
        else: return True

    def ImageMissing(self):
        """ Return TRUE if ImageBuffer is not initialized. """
        result = False
        if isinstance(self.ImageBuffer,type(None)): result = True
        return result
        
    def SimplifyImage(self,blurradius=13):
        """ Backwards compatibility with earlier versions. """
        print("pilomarimage.SimplifyImage(): Deprecated. Please use pilomarimage.EnhanceStars() method now.")
        if self.Log != None: self.Log("pilomarimage",self.Name,".SimplifyImage -> EnhanceStars: Begin",terminal=False)
        return self.EnhanceStars(blurradius=blurradius)

    def PrepareImage(self,blurradius=13):
        """ Backwards compatibility with earlier versions. """
        print("pilomarimage.PrepareImage(): Deprecated. Please use pilomarimage.EnhanceStars() method now.")
        if self.Log != None: self.Log("pilomarimage",self.Name,".PrepareImage -> EnhanceStars: Begin",terminal=False)
        return self.EnhanceStars(blurradius=blurradius)

    def EnhanceStars(self,blurradius=13,cloudthresh=100,starthresh=16,maxval=255):
        """ Enhance the stars in the image. 
            Was 'SimplifyImage' and 'PrepareImage' in earlier pilomar versions.
            - blurradius is the GaussianBlur radius.
            - cloudthresh is the threshold to remove cloud (experimental).
            - starthresh is the threshold to single out the stars.    
            - maxval is the saturated value set for cells above the threshold. """
        if self.Log != None: 
            self.Log("pilomarimage",self.Name,".EnhanceStars: blurradius",blurradius,"cloudthresh",cloudthresh,"starthresh",starthresh,"maxval",maxval,terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.EnhanceStars: No image in the buffer.')
        self.ChangeType('grayscale') # Convert to grayscale.
        retval, self.ImageBuffer = cv2.threshold(self.ImageBuffer,cloudthresh,maxval,cv2.THRESH_BINARY) # 100 should ignore clouds more easily and just recognise brighter stars.
        if blurradius % 2 == 0: blurradius += 1 # Must be odd.
        # 2nd enlarge the stars using a blur filter.
        # - This increases the radius of each star, so when we reduce the image size, the star survives the shrinking.
        self.ImageBuffer = cv2.GaussianBlur(self.ImageBuffer,(blurradius,blurradius),0)
        # 3rd sharpen these larger star dots back into more definite black-or-white.
        # - Use adaptive thresholding now to make the stars more crisp.
        # - Adaptive means that the threshold limit between BLACK and WHITE is chosen by the function.
        retval, self.ImageBuffer = cv2.threshold(self.ImageBuffer,starthresh,maxval,cv2.THRESH_BINARY + cv2.THRESH_OTSU) # OTSU is adaptive threshold limits.
        self.ActionList.append(['enhancestars',blurradius])
        self.ModifiedTimestamp = self.Now()
        if self.Log != None: self.Log("pilomarimage",self.Name,".EnhanceStars: End.",terminal=False)
        return True

    def FS_Save(self,filterdata):
        """ Save the current image buffer and write the current filter data on it. 
            A debugging feature.
            
            filterdata is the data you want writing as a dictionary. 
            'saveas' entry must exist in the filterdata.
                """
        if 'saveas' in filterdata: # There is a filename to use.
            filename = filterdata['saveas']
            if filename != None and len(filename) > 0:
                # Add filterdata information to the image.
                self.AddText("filterdata:",x=10,y=int(self.GetHeight() / 2),color=pilomarimage.BGRWhite,bgcolor=pilomarimage.BGRBlack)
                for key,value in filterdata.items():
                    self.AddText(" " + str(key) + ":" + str(value),x=10,y=self.NextTextY,color=pilomarimage.BGRWhite,bgcolor=BGRBlack)
                self.Save(filename)
        return True
        
    def FS_Grayscale(self,filterdata):
        """ Convert buffer to grayscale.
            {'method':'grayscale',
             'comment':''}            """
        comment = filterdata.get('comment','') # Get any associated comment, default ''.
        if self.Log != None: 
            if comment != '': self.Log("pilomarimage",self.Name,".FS_Grayscale: Comment:",comment,terminal=False)
            self.Log("pilomarimage",self.Name,".FS_Grayscale:",terminal=False)
        self.ChangeType('grayscale') # Convert to grayscale.
        self.ActionList.append(['FS_Grayscale'])
        self.ModifiedTimestamp = self.Now()
        return True
             
    def FS_Threshold(self,filterdata):
        """ Run OpenCV threshold filter on current image buffer using input parameters. 
            filterdata = dictionary of parameters. 
            
            {'method':'threshold',
             'threshold': 127,
             'maxval': 255,
             'type': cv2.THRESH_BINARY,
             'comment': ''}
            
            """
        threshold = filterdata.get('threshold',127) # Get threshold level, default 127.
        maxval = filterdata.get('maxval',255) # Get output value for pixels above the threshold, default 255.
        threshold_type = filterdata.get('type',cv2.THRESH_BINARY) # Get threshold calculation type, default THRESH_BINARY.
        if threshold_type == None: threshold_type = cv2.THRESH_BINARY
        comment = filterdata.get('comment','') # Get any associated comment, default ''.
        if self.Log != None: 
            if comment != '': self.Log("pilomarimage",self.Name,".FS_Threshold: Comment:",comment,terminal=False)
            self.Log("pilomarimage",self.Name,".FS_Threshold(",threshold,",",maxval,",",threshold_type,")",terminal=False)
        calculatedthreshold, self.ImageBuffer = cv2.threshold(self.ImageBuffer,threshold,maxval,threshold_type)
        self.ActionList.append(['FS_Threshold',threshold,maxval,threshold_type])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def FS_GaussianBlur(self,filterdata):
        """ Run OpenCV gaussianblur filter on current image buffer using input parameters. 
            filterdata = dictionary of parameters. 
            
            {'method':'gaussianblur',
             'radius': 5, # Must be 0 or an odd integer.
             'comment': ''}
            
            """
        radius = filterdata.get('radius',5) # Get blur radius, default 5.
        if radius < 0: radius = 0 # Cannot be negative.
        if radius > 0 and radius % 2 == 0: radius += 1 # Must be odd if > 0.
        comment = filterdata.get('comment','') # Get any associated comment, default ''.
        if self.Log != None: 
            if comment != '': self.Log("pilomarimage",self.Name,".FS_GaussianBlur: Comment:",comment,terminal=False)
            self.Log("pilomarimage",self.Name,".FS_GaussianBlur(",radius,")",terminal=False)
        self.ImageBuffer = cv2.GaussianBlur(self.ImageBuffer,(radius,radius),0)    
        self.ActionList.append(['FS_GaussianBlur',radius])
        self.ModifiedTimestamp = self.Now()
        return True

    def FS_Dehaze(self,filterdata):
        """ Remove general haze gradient from an image buffer. 
            filterdata = dictionary of parameters.
            
            {'method':'dehaze',
             'samples':1, # Compress horizontal pixel values down to this number of samples per line.
             'strength':100 # 0 - 100 (%) strength. How much of the identified haze will be removed.
             'comment': ''}
             """
        samples = filterdata.get('samples',1) # Number of samples along each image row, default 1
        strength = filterdata.get('strength',100) # How strong is the filter, default 100 (%).
        comment = filterdata.get('comment','') # Get any associated comment, default ''.
        if self.Log != None: 
            if comment != '': self.Log("pilomarimage",self.Name,".FS_Dehaze: Comment:",comment,terminal=False)
            self.Log("pilomarimage",self.Name,".FS_Dehaze(",samples,",",strength,")",terminal=False)
        # Create a working buffer to construct the haze filter.
        buffer = self.ImageBuffer.copy() # Copy the image buffer, we will blur this copy.
        buffer = self.HorizontalBlurBuffer(buffer,band=samples) # Horizontally blur the buffer.
        if strength > 0: # There needs to be some effect.
            if strength != 100: # Multiply all the channels appropriately.
                buffer = self.PercentageBuffer(buffer,strength) # Reduce the strength of the buffer.
            self.SubtractBuffer(buffer) # Subtract the blurred buffer from the master image buffer.
        self.ActionList.append(['FS_Dehaze',samples,strength])
        self.ModifiedTimestamp = self.Now()
        return True

    def RunFilterScript(self,scriptname):
        """ Given a script name, apply the filters and parameters defined in the script.
            filterrules is a dictionary """
        if self.Log != None: self.Log("pilomarimage",self.Name,".RunFilterScript()",terminal=False)
        if not type(scriptname) == str: # Nothing useful set.
            if self.Log != None: self.Log("RunFilterScript(): No valid script name.",terminal=False)
            else: print("RunFilterScript(): No valid script name.")
            return False 
        if not scriptname in pilomarimage.FILTERSCRIPTS: # Script doesn't exist.
            if self.Log != None: self.Log("RunFilterScript(",scriptname,"). Script does not exist.",terminal=False)        
            print("RunFilterScript(",scriptname,"). Script does not exist.")
            return False
        filterscript = pilomarimage.FILTERSCRIPTS[scriptname]
            
        filtercount = 0
        result = True
        
        for entryname,filterdata in filterscript.items(): # Go through each set of filters in turn.
            if self.Log != None: self.Log("pilomarimage.RunFilterScript(",filtercount,entryname,") Running script...",terminal=False) # Report the name of the filter
            # Each 'item' should be a sub-dictionary of a filter and its parameters to apply to the current image.
            filtermethod = filterdata['method']
            result = True
            if filtermethod == 'dehaze': result = self.FS_Dehaze(filterdata) # Remove haze from the image.
            elif filtermethod == 'gaussianblur': result = self.FS_GaussianBlur(filterdata) # Apply a Gaussian blur filter.
            elif filtermethod == 'grayscale': result = self.FS_Grayscale(filterdata) # Convert image to grayscale.
            elif filtermethod == 'save': result = self.FS_Save(filterdata) # Apply a threshold filter.
            elif filtermethod == 'threshold': result = self.FS_Threshold(filterdata) # Apply a threshold filter.
            else: # Filter method is not recognised.
                if self.Log != None: self.Log("pilomarimage.RunFilterScript(",filtercount,entryname,") filtermethod",filtermethod,"does not exist.",level='error')
                else: print("**ERROR** pilomarimage.RunFilterScript(",filtercount,entryname,") filtermethod",filtermethod,"does not exist.")
                result = False
            if not result: break # Failure.
            filtercount += 1 # Increment count.
        if not result:
            if self.Log != None: self.Log("pilomarimage.RunFilterScript(",scriptname,") did not complete successfully.",level='warning')
            else: print("WARNING: pilomarimage.RunFilterScript(",scriptname,") did not complete successfully.")
        return result

    #def UrbanFilterScript(self):
    #    """ Experimental usage of RunFilterScript to replicate hardcoded filter solution. """
    #    if self.Log != None: self.Log("pilomarimage",self.Name,".UrbanFilterScript(): start",terminal=False)
    #    result = self.RunFilterScript('UrbanFilter') # Fund the UrbanFilter script against the current image buffer.
    #    if self.Log != None: self.Log("pilomarimage",self.Name,".UrbanFilterScript(): result",result,terminal=False)
    #    return result
    
    def UrbanFilter(self,band=1,blurradius=2,cloudthresh=50,starthresh=16,maxval=255,strength=100):
        """ Primitive 'urban skies' filter. 
            This is used for star drift tracking. 
            A live image is cleaned to remove common urban haze before enhancing the remaining stars. 
            band = Blurring factor. '1' is the highest blurring. 
            blurradius, cloudthresh, starthresh, maxval are all values for the EnhanceStars() method. 
            strength is the percentage strength of the haze filter. 
            0 = No haze reduction.
            50 = 50% haze reduction.
            100 = Full haze reduction. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".UrbanFilter(): band",band,
                                      "blurradius",blurradius,"cloudthresh",cloudthresh,"starthresh",starthresh,
                                      "maxval",maxval,"strength",strength,terminal=False)
        buffer = self.ImageBuffer.copy() # Copy the image buffer, we will blur this copy.
        buffer = self.HorizontalBlurBuffer(buffer,band=band) # Horizontally blur the buffer.
        if strength > 0: # There needs to be some effect.
            if strength != 100: # Multiply all the channels appropriately.
                buffer = self.PercentageBuffer(buffer,strength) # Reduce the strength of the buffer.
            self.SubtractBuffer(buffer) # Subtract the blurred buffer from the master image buffer.
        self.EnhanceStars(blurradius=blurradius,cloudthresh=cloudthresh,starthresh=starthresh,maxval=maxval) # Enhance the stars that remain.
        return True
        
    def HSV2BGR(self,hue,sat,val):
        """ Convert 3 separate Hue,Saturation,Value values into Blue,Green,Red. """
        hsv = np.uint8([[[hue,sat,val]]]) # a 1x1 pixel image.
        bgr = cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
        b = int(bgr[0][0][0])
        g = int(bgr[0][0][1])
        r = int(bgr[0][0][2])
        return b, g, r 

    def DimChannel(self,channel,ratio): # 3 references.
        """ simple multiplier for single color channel. """
        channel = channel * ratio
        channel = min(max(channel,0),255) # 0 <= x <= 255
        return channel

    def DimColor(self,color,ratio): # 4 references.
        """ Simple multiplier for BGR or BGRA color tuples. """
        if len(color) == 4: # Adjust BGR, but not A.
            return (self.DimChannel(color[0],ratio),self.DimChannel(color[1],ratio),self.DimChannel(color[2],ratio),color[3])
        elif len(color) == 3: # Adjust BGR
            return (self.DimChannel(color[0],ratio),self.DimChannel(color[1],ratio),self.DimChannel(color[2],ratio))
        else: return DimChannel(color,ratio) # Assume single channel.

    def FakeField(self): # Generate fake field noise.
        """ Create a small blank image and add some fake electronic noise to it. 
            Then enlarge the image to match the size of the target image. 
            Then combine the two images.
            *Q* Only handles bgr images at the moment.  """
        if self.Log != None: self.Log("astrocamera.FakeField: Simulating electrical field noise.",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FakeField: No image in the buffer.')
        height = self.GetHeight()
        width = self.GetWidth()
        fieldimg = np.zeros((int(height/100),int(width/100),3),np.uint16) # 'bgr' at 1% of original size.
        fieldimg = cv2.circle(fieldimg,(fieldimg.shape[1],fieldimg.shape[0]),int(fieldimg.shape[1]/3),pilomarimage.BGRVeryDarkRed,thickness=-1) # Simulate an electric field shadow.
        fieldimg = cv2.resize(fieldimg,(width,height),interpolation=self.ResizeMethod) # Scale back up to full image size.
        fieldimg = np.add(self.ImageBuffer,fieldimg) # Combine
        self.ImageBuffer = np.clip(fieldimg,0,255).astype(np.uint8) # Clip to uint8 values.
        self.ActionList.append(['fakefield'])
        self.ModifiedTimestamp = self.Now()
        return True

    def FakeNoise(self): # Generate fake image noise.
        """ Create a small blank image and add some fake image noise to it. 
            Return the combined image. 
            *Q* Only handles bgr images at the moment. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".FakeNoise()",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FakeNoise: No image in the buffer.')
        fieldimg = np.random.randint(0,25,(self.GetHeight(),self.GetWidth(),3),np.uint16) # 'bgr' buffer of random values.
        fieldimg = np.add(fieldimg,self.ImageBuffer)
        self.ImageBuffer = np.clip(fieldimg,0,255).astype(np.uint8) # Clip to uint8 values.
        self.ActionList.append(['fakenoise'])
        self.ModifiedTimestamp = self.Now()
        return True

    def TrimLine(self,x1,y1,x2,y2,trimfactor=None,trimpixels=None):
        """ Trim an amount off each end of a line. 
            Given start and end locations and the amount to trim.
            trimfactor = 0.0 - 0.5 The proportion of the line to remove from each end. 
            trimpixels = nnn The number of pixels to trim from each end. """
        #if self.Log != None: self.Log("pilomarimage",self.Name,".TrimLine()",terminal=False)
        if trimpixels != None: # Convert pixel count to factor.
            length = int(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
            if length != 0.0: trimfactor = trimpixels / length
            else: trimfactor = 0.0
        if trimfactor == None: # No value.
            return False
        xstart = int(self.Interpolate(y1,x1,y2,x2,y1 + ( (y2 - y1) * trimfactor) ) ) # start xx% into the path.
        ystart = int(self.Interpolate(x1,y1,x2,y2,x1 + ( (x2 - x1) * trimfactor) ) ) # start xx% into the path.
        xend = int(self.Interpolate(y1,x1,y2,x2,y1 + ( (y2 - y1) * (1 - trimfactor) ) ) ) # end xx% from end of the path.
        yend = int(self.Interpolate(x1,y1,x2,y2,x1 + ( (x2 - x1) * (1 - trimfactor) ) ) ) # end xx% from end of the path.
        return xstart,ystart,xend,yend

    def FakeMeteor(self): # Generate fake meteor streak
        """ Add a random meteor like streak to an image.
            *Q* Only handles bgr images at the moment. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".FakeMeteor()",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FakeMeteor: No image in the buffer.')
        color = self.SafeColor(pilomarimage.BGRWhite)
        width = self.GetWidth()
        height = self.GetHeight()
        meteorimg = np.zeros((height,width,3),np.uint16) # 'bgr' buffer of zeros.
        length = 0
        while length < 500: # Make the meteor streak long enough to see.
            x1 = random.randint(0,width)
            x2 = random.randint(0,width)
            y1 = random.randint(0,height)
            y2 = random.randint(0,height)
            length = int(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
        meteorimg = cv2.line(meteorimg, (x1, y1), (x2, y2), color, 1) # Mark the thin main trail on the image.
        # Flare the meteor mid path...
        xstart, ystart, xend, yend = self.TrimLine(x1,y1,x2,y2,0.3) # Find the central part of the line to create a flare in the trail.
        #xstart = int(self.Interpolate(y1,x1,y2,x2,y1 + ( (y2 - y1) * 0.3) ) ) # start 30% into the path.
        #ystart = int(self.Interpolate(x1,y1,x2,y2,x1 + ( (x2 - x1) * 0.3) ) ) # start 30% into the path.
        #xend = int(self.Interpolate(y1,x1,y2,x2,y1 + ( (y2 - y1) * 0.7) ) ) # end 30% from end of the path.
        #yend = int(self.Interpolate(x1,y1,x2,y2,x1 + ( (x2 - x1) * 0.7) ) ) # end 30% from end of the path.
        meteorimg = cv2.line(meteorimg, (xstart, ystart), (xend, yend), color, 3) # Mark a thicker flare trail on the image.
        meteorimg = np.add(meteorimg,self.ImageBuffer)
        self.ImageBuffer = np.clip(meteorimg,0,255).astype(np.uint8) # Clip to uint8 values.
        self.ActionList.append(['fakemeteor'])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def PlotStars(self,radius,starlist):
        """ Given an existing image buffer and a list of stars, create a clean version of the image.
            Inherit the dimensions from the source image, and place the stars according to the starlist. 
            This returns a GRAYSCALE image with all stars depicted at the same size.
            The size is the same for LATEST and TARGET images (Parameters.TrackingStarRadius), so that the 
            FindTransform() method has consistent images to compare. """
        if self.Log != None: self.Log("pilomarimage",self.Name,".PlotStars(",radius,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.PlotStars: No image in the buffer.')
        GrayscaleWhite = (255)
        self.New(self.GetDimensions(),'grayscale',np.uint8) # GRAYSCALE image. HEIGHT, WIDTH inherited from reference image.
        for star_x, star_y, star_r in starlist:
            self.ImageBuffer = cv2.circle(self.ImageBuffer,(star_x,star_y),radius,GrayscaleWhite,thickness=-1) # White. All stars converted to standard 7 pixel radius.
        self.ActionList.append(['plotstars',radius])
        self.ModifiedTimestamp = self.Now()
        return True

    def MeasureContrast(self):
        """ Return values representing contrast of overall image. 
            2 contrast calculations are returned.
            1) Michelson contrast (0.0 - 1.0) 
            2) standard deviation contrast
            Doesn't modify ImageBuffer
            """
        if self.Log != None: self.Log("pilomarimage",self.Name,".MeasureContrast()",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.MeasureContrast: No image in the buffer.')
        michelson_contrast = None
        stddev_contrast = None
        cvimagebuffer = self.NewBufferType('grayscale') # Needs grayscale buffer.
        try:
            stddev_contrast = cvimagebuffer.std() # Standard deviation.
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage",self.Name,".MeasureContrast: stddev_contrast failed.",terminal=False)
        try:
            min = float(np.min(cvimagebuffer))
            max = float(np.max(cvimagebuffer))
            michelson_contrast = (max - min) / (max + min) # 
        except Exception as e:
            if self.Log != None: self.Log("pilomarimage",self.Name,".MeasureContrast: michelson_contrast failed.",terminal=False)
        if self.Log != None: self.Log("pilomarimage",self.Name,".MeasureContrast: min",min,", max",max,", michelson_contrast",michelson_contrast,"stddev_contrast",stddev_contrast,terminal=False)
        return michelson_contrast, stddev_contrast
    
    def FillColor(self,color):
        """ Fill the image buffer with a specific color. """
        if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FillColor(",color,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FillColor: No image in the buffer.')
        color = self.SafeColor(color)
        if self.GetType == 'grayscale': # Single depth grayscale image. Just fill all cells with the same value.
            self.ImageBuffer[:,:] = color[0]
        else: # Multiple channels.
            for i,c in enumerate(color): # Handle each channel separately.
                if self.ImageBuffer.shape[2] > i: # Channel must exist.
                    self.ImageBuffer[:,:,i] = c # Set all values of the channel.
        self.ActionList.append(['fillcolor',color])
        self.ModifiedTimestamp = self.Now()
        return True

    def InBounds(self,x,y):
        """ Return TRUE if (x,y) is within the bounds of the image. """
        width = self.GetWidth()
        height = self.GetHeight()
        if x >= 0 and x <= width and y >= 0 and y <= height: result = True
        else: result = False
        return result
        
    def OutOfBounds(self,x,y):
        """ Return TRUE if (x,y) is outside the bounds of the image. """
        result = not self.InBounds(x,y)
        return result 
        
    def SafeThickness(self,thickness):
        """ Default line thickness if not specified. """
        if thickness == None: thickness = 1
        return thickness

    def GetPenColor(self):
        """ Return current pen color. """
        return self.PenColor

    def SetPenColor(self,color):
        """ Set current pen color. """
        self.PenColor = self.SafeColor(color) # Make sure color depth matches image depth.
        self.ActionList.append(['setpencolor',color])
        return True

    def SetPenOpacity(self,opacity):
        """ Change the opacity of the current color. """
        if self.GetDepth() == 4: # Opacity supported.
            color = self.GetPenColor()
            color = (color[0],color[1],color[2],opacity)
            self.SetPenColor(color)
        self.ActionList.append(['setpenopacity',opacity])
        return True

    def SafeColor(self,color,default=None):
        """ Default color if not specified. """
        depth = self.GetDepth()
        if type(color) == type(None): color = default
        if type(color) == type(None): color = self.GetPenColor()
        if type(color) == type(None):
            if depth == 1: color = 255 # Grayscale
            elif depth == 3: color = pilomarimage.BGRBlack # BGR
            elif depth == 4: color = (255,255,255,255) # BGRA
        # Convert color (received as int or tuple) into a list for looping through.
        if isinstance(color,int): ct = [color]
        else: ct = list(color)
        ctl = len(ct)
        if ctl != depth: # We need to adjust the color tuple to match the image depth.
            if ctl == 1:
                if depth == 3: color = (ct[0],ct[0],ct[0]) # From 1 to 3
                elif depth == 4: color = (ct[0],ct[0],ct[0],255) # From 1 to 4
            elif ctl == 3:
                if depth == 1: color = int((ct[0] + ct[1] + ct[2]) / 3) # From 3 to 1
                elif depth == 4: color = (ct[0],ct[1],ct[2],255) # From 3 to 4
            elif ctl == 4:
                if depth == 1: color = int((ct[0] + ct[1] + ct[2]) / 3) # From 4 to 1
                elif depth == 3: color = tuple(color[:3]) # From 4 to 3
        return color
        
    def DeltaColor(self,color,delta):
        """ Apply delta values to a color.
            Use this to nudge colors up/down slightly. """
        color = self.SafeColor(color)
        color = list(color) # Convert to list.
        delta = list(delta) # Convert to list.
        for i in range(len(delta)):
            channel = color[i] + delta[i] # Apply delta.
            channel = min(255,max(0,channel)) # Clip to 0-255 range.
            newcol[i]= channel # Reapply
        if len(color) < 2:
            newcolor = newcol[0] # single channel colors return just an integer.
        else: # Multiple channel colors return a tuple.
            newcolor = tuple(newcol)
        return newcolor
        
    def DrawLine(self,startcoord,endcoord,color=None,thickness=None,arrowpixels=None):
        """ Use opencv linedrawing. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawLine(",startcoord,endcoord,color,thickness,arrowpixels,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawLine: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        startcoord = self.OrientCoord(startcoord) # Make sure HEIGHT is right way up.
        endcoord = self.OrientCoord(endcoord) # Make sure HEIGHT is right way up.
        distance = math.sqrt(((endcoord[0] - startcoord[0]) ** 2) + ((endcoord[1] - startcoord[1]) ** 2))
        if arrowpixels == None or distance <= 0:
            self.ImageBuffer = cv2.line(self.ImageBuffer, startcoord, endcoord, color, thickness=thickness, lineType=cv2.LINE_AA)
        else:
            arrowproportion = arrowpixels / distance # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
            self.ImageBuffer = cv2.arrowedLine(self.ImageBuffer, startcoord, endcoord, color, thickness=thickness, line_type=cv2.LINE_AA, tipLength=arrowproportion)
        self.ActionList.append(['drawline',startcoord,endcoord,color,thickness,arrowpixels])
        self.ModifiedTimestamp = self.Now()
        return True

    def DrawEdgeLine(self,startcoord,endcoord,color=None,edgecolor=None,thickness=None,edgethickness=1,arrowpixels=None):
        """ Use opencv linedrawing. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawEdgeLine(",startcoord,endcoord,color,edgecolor,thickness,edgethickness,arrowpixels,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawEdgeLine: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        edgecolor = self.SafeColor(edgecolor)
        startcoord = self.OrientCoord(startcoord) # Make sure HEIGHT is right way up.
        endcoord = self.OrientCoord(endcoord) # Make sure HEIGHT is right way up.
        if arrowpixels == None:
            self.ImageBuffer = cv2.line(self.ImageBuffer, startcoord, endcoord, edgecolor, thickness=int(thickness + (2 * edgethickness)), lineType=cv2.LINE_AA)
            self.ImageBuffer = cv2.line(self.ImageBuffer, startcoord, endcoord, color, thickness=thickness, lineType=cv2.LINE_AA)
        else:
            distance = math.sqrt(((endcoord[0] - startcoord[0]) ** 2) + ((endcoord[1] - startcoord[1]) ** 2))
            arrowproportion = arrowpixels / distance # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
            self.ImageBuffer = cv2.arrowedLine(self.ImageBuffer, startcoord, endcoord, edgecolor, thickness=int(thickness + (2 * edgethickness)), line_type=cv2.LINE_AA, tipLength=arrowproportion)
            self.ImageBuffer = cv2.arrowedLine(self.ImageBuffer, startcoord, endcoord, color, thickness=thickness, line_type=cv2.LINE_AA, tipLength=arrowproportion)
        self.ActionList.append(['drawedgeline',startcoord,endcoord,color,edgecolor,thickness,edgethickness,arrowpixels])
        self.ModifiedTimestamp = self.Now()
        return True

    def DrawCircle(self,center_x,center_y,rad,color=None,thickness=None):
        """ Draw a circle on the image. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawCircle(",center_x,center_y,color,rad,thickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawCircle: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        center_y = self.OrientHeight(center_y) # Make sure HEIGHT is right way up.
        self.ImageBuffer = cv2.circle(self.ImageBuffer,(center_x, center_y), rad, color, thickness=thickness, lineType=cv2.LINE_AA)
        self.ActionList.append(['drawcircle',center_x,center_y,rad,color,thickness])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def DrawEdgeCircle(self,center_x,center_y,rad,color=None,thickness=None,edgecolor=None,edgethickness=1):
        """ Draw a circle on the image with a colored edge. """
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawCircle: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        center_y = self.OrientHeight(center_y) # Make sure HEIGHT is right way up.
        self.ImageBuffer = cv2.circle(self.ImageBuffer,(center_x, center_y), rad, edgecolor, thickness=thickness + (2 * edgethickness), lineType=cv2.LINE_AA)
        self.ImageBuffer = cv2.circle(self.ImageBuffer,(center_x, center_y), rad, color, thickness=thickness, lineType=cv2.LINE_AA)
        self.ActionList.append(['drawedgecircle',center_x,center_y,rad,color,thickness])
        self.ModifiedTimestamp = self.Now()
        return True

    def FillCircle(self,center_x,center_y,rad,color=None):
        """ Fill a circle on the image. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FillCircle(",center_x,center_y,color,rad,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FillCircle: No image in the buffer.')
        color = self.SafeColor(color)
        #print("pilomarimage.FillCircle:",center_x,center_y,rad,color)
        center_y = self.OrientHeight(center_y) # Make sure HEIGHT is right way up.
        self.ImageBuffer = cv2.circle(self.ImageBuffer,(center_x, center_y), rad, color, thickness=-1, lineType=cv2.LINE_AA)
        self.ActionList.append(['fillcircle',center_x,center_y,rad,color])
        self.ModifiedTimestamp = self.Now()
        return True

    def SetPixel(self,center_x,center_y,color=None):
        """ Set a single pixel on the image. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".SetPixel(",center_x,center_y,color,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.SetPixel: No image in the buffer.')
        color = self.SafeColor(color)
        center_y = self.OrientHeight(center_y) # Make sure HEIGHT is right way up.
        self.ImageBuffer[center_y,center_x] = color
        self.ActionList.append(['setpixel',center_x,center_y,color])
        self.ModifiedTimestamp = self.Now()
        return True

    def GetPixel(self,center_x,center_y):
        """ Return value of a single pixel on the image.
            Doesn't convert datatype! """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".GetPixel(",center_x,center_y,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.GetPixel: No image in the buffer.')
        center_y = self.OrientHeight(center_y) # Make sure HEIGHT is right way up.
        color = tuple(self.ImageBuffer[center_y,center_x])
        return color

    def BlendColor(self,fromcolor,tocolor,ratio):
        """ Find color between two values. Ratio says how much of each color to use.
            0.0 = All FROM COLOR
            1.0 = All TO COLOR """
        ratio = min(max(ratio,0.0),1.0) # Clip value.
        fromratio = ratio
        toratio = 1.0 - ratio
        gt = self.GetType()
        if gt == 'grayscale':
            color = int(min(fromcolor * fromratio + tocolor * toratio),255)
        elif gt == 'bgr':
            color = (min(fromcolor[0] * fromratio + tocolor[0] * toratio,255),
                     min(fromcolor[1] * fromratio + tocolor[1] * toratio,255),
                     min(fromcolor[2] * fromratio + tocolor[2] * toratio,255))
        else: # 'bgra'
            color = (min(fromcolor[0] * fromratio + tocolor[0] * toratio,255),
                     min(fromcolor[1] * fromratio + tocolor[1] * toratio,255),
                     min(fromcolor[2] * fromratio + tocolor[2] * toratio,255),
                     min(fromcolor[3] * fromratio + tocolor[3] * toratio,255))
        return color

    def FadeCircle(self,center_x,center_y,rad,color=None,fadecolor=None):
        """ Fill a circle on the image, but the color fades from center to edge """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FadeCircle(",center_x,center_y,color,rad,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FadeCircle: No image in the buffer.')
        color = self.SafeColor(color)
        center_y = self.OrientHeight(center_y) # Make sure HEIGHT is right way up.
        if fadecolor == None: fadecolor = self.SafeColor(0) # Default to Black.
        else: fadecolor = self.SafeColor(fadecolor)
        prevcolor = None # Only draw circles when the color changes.
        for i in range(rad, 0, -2):
            ratio = (rad - i) / float(rad) # Ratio is ZERO at the edge.
            gradedcolor = self.BlendColor(color,fadecolor,ratio)
            if gradedcolor != prevcolor:
                self.ImageBuffer = cv2.circle(self.ImageBuffer,(center_x, center_y), i, gradedcolor, thickness=-1, lineType=cv2.LINE_AA)
                prevcolor = gradedcolor
        self.ActionList.append(['fadecircle',center_x,center_y,rad,color,fadecolor])
        self.ModifiedTimestamp = self.Now()
        return True

    def GetTextArea(self,text,size=1.0,thickness=None):
        """ Calculate the pixel area covered by a text line.
            xdim = overall pixel width.
            ydim = overall pixel height including tails of letters.
            baseline = y pixel offset to account for tails of letters. """
        (label_width, label_height), baseline = cv2.getTextSize(text, self.Font, size, thickness)
        xdim = label_width
        ydim = label_height + baseline
        return xdim,ydim,baseline

    ### BEGIN DEVELOPMENT ###
    def TextBoundary(self,text,fromx,fromy,size=1.0,thickness=None,hjust='l',vjust='t',border=None):
        """ Return boundaries of a text line.
            Given a single line, this returns the two corners of the surrounding text box
            and also the next/prev starting height for any following line. """
        thickness = self.SafeThickness(thickness)
        xdim,ydim,ybase = self.GetTextArea(text,size=size,thickness=thickness) # Boundaries of the text.
        if hjust == 'c': # Center the text horizontally on the location.
            x = int(fromx - xdim / 2)
        elif hjust == 'r': # text ends horizontally at the location.
            x = int(fromx - xdim)
        else: 
            x = fromx # text starts horizontally at the location.
        if vjust == 'c': # Center the text vertically on the location.
            y = int(fromy + ydim / 2) - ybase
        elif vjust == 'b': # Text is below the location.
            y = int(fromy + ydim) - ybase
        else: 
            y = fromy - ybase # Test is above the location.
        if border != None: b = border
        else: b = 0
        x1 = x - b
        y1 = y + ybase + b
        x2 = x + xdim + b
        y2 = y - ydim + ybase + b
        nexty = fromy + ydim # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        prevy = fromy - ydim # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        return x1,y1,x2,y2,nexty,prevy

    def AddTextBlock(self,textlines,fromx,fromy,color=None,size=1.0,thickness=None,hjust='l',vjust='t',border=None,bgcolor=None):
        """ Take a list of text lines and paint as a block. 
            Lines can be provided as a list or as a single item with newline characters inserted. 
            
            -----------------------------------
            *Q* Justification doesn't work yet.
            -----------------------------------

            """
        thickness = self.SafeThickness(thickness)
        if type(textlines) != type(list): textlines = [textlines] # Make sure it's a list we're handling.
        nl = []
        for line in textlines: # Split on newline character too.
            nlines = line.split('\n')
            nl = nl + nlines
        textlines = nl 
        minx = maxx = fromx # Start/stop x dimensions of text block.
        miny = maxy = fromy # Start/stop y dimensions of text block.
        for i,line in enumerate(textlines): # Now calculate the total size of the entire text block.
            if i == 0: # 1st line.
                xa1, ya1, xa2, ya2, nexty, prevy = self.TextBoundary(line,fromx,fromy,size,thickness,hjust,vjust)
            else:
                xa1, ya1, xa2, ya2, nexty, prevy = self.TextBoundary(line,fromx,nexty,size,thickness,hjust,vjust)
            minx = min(minx,xa1,xa2)
            maxx = max(maxx,xa1,xa2)
            miny = min(miny,ya1,ya2)
            maxy = max(maxy,ya1,ya2)
        spanx = maxx - minx
        spany = maxy - miny
        if border != None:
            minx = minx - border
            maxx = maxx + border
            miny = miny - border
            maxy = maxy + border
        self.FillRectangle((minx,miny),(maxx,maxy),color=bgcolor)
        # Add border.
        if border != None: #Draw a border around the text.
            self.DrawRectangle((minx,miny),(maxx,maxy),color=color,thickness=thickness)
        # Now add text.
        for i,line in enumerate(textlines):
            if i == 0: # 1st line. # Take over painting of border and background to make it a block instead.
                self.AddText(line,fromx,fromy,color=color,size=size,thickness=thickness,hjust=hjust,vjust=vjust,border=None,bgcolor=None)
            else: # subsequent lines.
                self.AddText(line,fromx,self.NextTextY,color=color,size=size,thickness=thickness,hjust=hjust,vjust=vjust,border=None,bgcolor=None)
        return True
    ### END DEVELOPMENT ###

    def AddText(self,text,fromx,fromy,color=None,size=1.0,thickness=None,hjust='l',vjust='t',border=None,bgcolor=None):
        """ Add text to an image.
            vjust = vertical justification. 'bottom','center','top'
                    bottom = text is 'below' the location.
                    
                                    *
                                      Text
                                     
                    center = text is 'beside' the location.
                    
                                    * Text
                    top = text is 'above' the location.
                    
                                      Text
                                    *
                    
            hjust = horizontal justification. 'left','center','right' 
                    left = text starts at the location.

                                    *
                                      Text
                                      
                    center = text spread across the location.
                    
                                    *
                                   Text
                                   
                    right = text ends at the location.
                    
                                    *
                               Text
                               
            bgcolor = color of background for the text. If missing, no background is generated. 
            
            border = draw a border. Value is the spacing between the letters and the border. 
            
            If you want to create a block of text, use self.NextTextY and self.PrevTextY to find the 
            y co-ordinate of the next/prev line of text to generate. This takes font size into account.
            
                self.AddText('line1',x,y) # Print line 1 as usual.
                self.AddText('line2',x,self.NextTextY) # NextTextY contains the starting Y coordinate for the next line.
            
            If you are changing font sizes, it is best to work bottom-up using self.PrevTextY, the spacing works more dynamically this way.
            
                self.AddText('lastline',x,y,size=1) # Print last line as usual.
                self.AddText('prevline',x,self.PrevTextY,size=2) # Print previous (higher) line next.
                
                
            *Q* TODO: OpenCV only supports basic 127 ASCII characters, to add UNICODE etc convert to PIL,
                add the extended characters there, then convert back. 
                """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".AddText(",text,fromx,fromy,color,size,thickness,hjust,vjust,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.AddText: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        xdim,ydim,ybase = self.GetTextArea(text,size=size,thickness=thickness) # Boundaries of the text.
        if hjust == 'c': # Center the text horizontally on the location.
            x = int(fromx - xdim / 2)
        elif hjust == 'r': # text ends horizontally at the location.
            x = int(fromx - xdim)
        else: 
            x = fromx # text starts horizontally at the location.
        if vjust == 'c': # Center the text vertically on the location.
            y = int(fromy + ydim / 2) - ybase
        elif vjust == 'b': # Text is below the location.
            y = int(fromy + ydim) - ybase
        else: 
            y = fromy - ybase # Test is above the location.
        if border != None: b = border
        else: b = 0
        if self.TextCollision(x - b,y + ybase + b,x + xdim + b,y - ydim + ybase - b): # This would collide with existing text, so don't add it.
            #self.DrawRectangle((x - b,y + ybase + b),(x + xdim + b,y - ydim + ybase - b),color=self.SafeColor(pilomarimage.BGROrangeRed),thickness=thickness)
            OK2Draw = False # It's not safe to draw.
        else:
            OK2Draw = True # It's safe to draw.
        if OK2Draw: # Proceed with the drawing.
            if bgcolor != None: # Draw background under the text.
                bgcolor = self.SafeColor(bgcolor)
                self.FillRectangle((x - b,y + ybase + b),(x + xdim + b,y - ydim + ybase - b),color=bgcolor)
            # We're OK to add the text at this point.
            if border != None: #Draw a border around the text.
                self.DrawRectangle((x - border,y + ybase + border),(x + xdim + border,y - ydim + ybase - border),color=color,thickness=thickness)
            # Store where the 'next' line of text would go if we're printing multiple lines. (Text must remain same size!)
            self.ImageBuffer = cv2.putText(self.ImageBuffer,text,self.OrientCoord((x,y)),self.Font,size,color,thickness,lineType=cv2.LINE_AA)
            self.ActionList.append(['addtext',text,fromx,fromy,color,size,thickness,hjust,vjust])
            self.ModifiedTimestamp = self.Now()
        self.NextTextX = fromx # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.NextTextY = fromy + ydim + 1 # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.PrevTextX = fromx # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        self.PrevTextY = fromy - ydim - 1 # If printing multiple lines of text, this is the start point for the previous line if you're printing upwards.
        return True

    def AddAngleText(self,text,fromx,fromy,color=None,size=1.0,thickness=None,hjust='l',vjust='t',border=None,bgcolor=None,angle=90):
        """ Add text to an image at an angle from horizontal.
        
            This is very limited functionality. OpenCV text handling is very basic, it is primarily there for development/debugging support
            with image analysis tasks - which is OpenCV's primary purpose. Adding complexity to it creates a big overhead, but if you REALLY
            need the occasional angled text, this is the place to create it.
            
            *Q* A future version could perhaps switch this to PIL handling, which may have more facilities. To be checked.
            
            vjust = vertical justification. 'bottom','center','top'
                    bottom = text is 'below' the location.
                    
                                    *
                                      Text
                                     
                    center = text is 'beside' the location.
                    
                                    * Text
                    top = text is 'above' the location.
                    
                                      Text
                                    *
                    
            hjust = horizontal justification. 'left','center','right' 
                    left = text starts at the location.

                                    *
                                      Text
                                      
                    center = text spread across the location.
                    
                                    *
                                   Text
                                   
                    right = text ends at the location.
                    
                                    *
                               Text
                               
            bgcolor = color of background for the text. If missing, no background is generated. 
            
            border = draw a border. Value is the spacing between the letters and the border. 
            
            If you want to create a block of text, use self.NextTextY and self.PrevTextY to find the 
            y co-ordinate of the next/prev line of text to generate. This takes font size into account.
            
                self.AddText('line1',x,y) # Print line 1 as usual.
                self.AddText('line2',x,self.NextTextY) # NextTextY contains the starting Y coordinate for the next line.
            
            If you are changing font sizes, it is best to work bottom-up using self.PrevTextY, the spacing works more dynamically this way.
            
                self.AddText('lastline',x,y,size=1) # Print last line as usual.
                self.AddText('prevline',x,self.PrevTextY,size=2) # Print previous (higher) line next.
                
            angle = 0 (No rotation), 90 (clockwise 90Deg), 180 (rotate 180deg) and 270 (anticlockwise 90deg).
            - Other angles will give unpredictable results.
            
            To achieve this, the image is rotated, the text is added, then the image is returned to original orientation.
            
            *Q* STILL UNDER DEVELOPMENT. NOT FINISHED YET.
                ONLY SUPPORTS 90DEGREE ANGLE SO FAR. 
                
            NOTE: This is SLOW!! """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".AddAngleText(",text,fromx,fromy,color,size,thickness,hjust,vjust,angle,")",terminal=False)
        angle = angle % 360
        supportedangles = [0,90] # Which angles are supported?
        if not angle in supportedangles:
            print("pilomarimage.AddAngleText() only supports these angles",str(supportedangles))
            return False
        if self.ImageMissing(): print('pilomarimage',self.Name,'.AddAngleText: No image in the buffer.')
        fromx = int(fromx)
        fromy = int(self.OrientHeight(fromy)) # Handle vertical orientation of pixel address here. Then it's simpler for all the following maths.
        if angle == 90:
            # 1st rotate the image to accept the text. Opposite direction to the text angle!
            self.RotateImage(360 - angle)
            # Translate rotated vector to new co-ordinates based upon new dimensions.
            fromx,fromy = self.RotateCoordinates(fromx,fromy,360 - angle) # We counterrotated the image so that the text is written at the desired angle, so counterrotate the text coordinates too.
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        xdim,ydim,ybase = self.GetTextArea(text,size=size,thickness=thickness) # Boundaries of the text.
        # Establish x,y as the actual co-ordinates at which to print the text in order to achieve justification.
        if angle == 90:
            # With a 90 degree rotation the justification instructions must rotate too. Swap hjust and vjust appropriately.
            if vjust == 'c': # hjust == 'c': # Center the text horizontally on the location.
                x = int(fromx - xdim / 2)
            elif vjust == 't': # hjust == 'r': # text ends horizontally at the location.
                x = int(fromx - xdim)
            else: 
                x = fromx # text starts horizontally at the location.
            if hjust == 'c': # vjust == 'c': # Center the text vertically on the location.
                y = int(fromy + ydim / 2) - ybase
            elif hjust == 'l': # vjust == 'b': # Text is below the location.
                y = int(fromy + ydim) - ybase
            else: 
                y = fromy - ybase # Test is above the location.
        else:
            if hjust == 'c': # Center the text horizontally on the location.
                x = int(fromx - xdim / 2)
            elif hjust == 'r': # text ends horizontally at the location.
                x = int(fromx - xdim)
            else: 
                x = fromx # text starts horizontally at the location.
            if vjust == 'c': # Center the text vertically on the location.
                y = int(fromy + ydim / 2) - ybase
            elif vjust == 'b': # Text is below the location.
                y = int(fromy + ydim) - ybase
            else: 
                y = fromy - ybase # Test is above the location.
        if bgcolor != None: # Draw background under the text.
            bgcolor = self.SafeColor(bgcolor)
            if border != None: b = border
            else: b = 0
            self.FillRectangle((x - b,y + ybase + b),(x + xdim + b,y - ydim + ybase + b),color=bgcolor)
        if border != None: #Draw a border around the text.
            self.DrawRectangle((x - border,y + ybase + border),(x + xdim + border,y - ydim + ybase + border),color=color,thickness=thickness)
        self.ImageBuffer = cv2.putText(self.ImageBuffer,text,(x,y),self.Font,size,color,thickness,lineType=cv2.LINE_AA) # *Q* <- Not implemented for angled text yet.
        # Store where the 'next' line of text would go if we're printing multiple lines. (Text must remain same size!)
        if angle == 90:
            # Now turn image the right way round again.
            self.RotateImage(angle)
        self.ActionList.append(['addangletext',text,fromx,fromy,color,size,thickness,hjust,vjust,angle])
        self.ModifiedTimestamp = self.Now()
        return True

    def AddEdgeText(self,text,fromx,fromy,color=None,edgecolor=None,size=1.0,thickness=None,edgethickness=None,hjust='l',vjust='t',border=None,bgcolor=None):
        """ Add text to an image with an outline around it.
            vjust = vertical justification. 'bottom','center','top'
                    bottom = text is 'below' the location.
                    
                                    *
                                      Text
                                     
                    center = text is 'beside' the location.
                    
                                    * Text
                    top = text is 'above' the location.
                    
                                      Text
                                    *
                    
            hjust = horizontal justification. 'left','center','right' 
                    left = text starts at the location.

                                    *
                                      Text
                                      
                    center = text spread across the location.
                    
                                    *
                                   Text
                                   
                    right = text ends at the location.
                    
                                    *
                               Text
                               
            bgcolor = color of background for the text. If missing, no background is generated. 
            
            border = draw a border. Value is the spacing between the letters and the border. 
            
            If you want to create a block of text, use self.NextTextY and self.PrevTextY to find the 
            y co-ordinate of the next/prev line of text to generate. This takes font size into account.
            
                self.AddText('line1',x,y) # Print line 1 as usual.
                self.AddText('line2',x,self.NextTextY) # NextTextY contains the starting Y coordinate for the next line.
            
            If you are changing font sizes, it is best to work bottom-up using self.PrevTextY, the spacing works more dynamically this way.
            
                self.AddText('lastline',x,y,size=1) # Print last line as usual.
                self.AddText('prevline',x,self.PrevTextY,size=2) # Print previous (higher) line next.
                
                """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".AddText(",text,fromx,fromy,color,size,thickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.AddEdgeText: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        if edgethickness == None: edgethickness = 1 # center thickness + 1 pixel either side.
        color = self.SafeColor(color)
        xdim,ydim,ybase = self.GetTextArea(text,size=size,thickness=int(thickness + (2 * edgethickness))) # Boundaries of the text.
        edgecolor = self.SafeColor(edgecolor)
        if hjust == 'c': # Center the text horizontally on the location.
            x = int(fromx - xdim / 2)
        elif hjust == 'r': # text ends horizontally at the location.
            x = int(fromx - xdim)
        else: 
            x = fromx # text starts horizontally at the location.
        if vjust == 'c': # Center the text vertically on the location.
            y = int(fromy + ydim / 2) - ybase
        elif vjust == 'b': # Text is below the location.
            y = int(fromy + ydim) - ybase
        else: 
            y = fromy - ybase # Test is above the location.
        if bgcolor != None: # Draw background under the text.
            bgcolor = self.SafeColor(bgcolor)
            if border != None: b = border
            else: b = 0
            self.FillRectangle((x - b,y + ybase + b),(x + xdim + b,y - ydim + ybase + b),color=bgcolor)
        if border != None: #Draw a border around the text.
            self.DrawRectangle((x - border,y + ybase + border),(x + xdim + border,y - ydim + ybase + border),color=edgecolor,thickness=edgethickness)
            self.DrawRectangle((x - border,y + ybase + border),(x + xdim + border,y - ydim + ybase + border),color=color,thickness=thickness)
        self.ImageBuffer = cv2.putText(self.ImageBuffer,text,self.OrientCoord((x,y)),self.Font,size,edgecolor,int(thickness + (2 * edgethickness)),lineType=cv2.LINE_AA)
        self.ImageBuffer = cv2.putText(self.ImageBuffer,text,self.OrientCoord((x,y)),self.Font,size,color,thickness,lineType=cv2.LINE_AA)
        # Store where the 'next' line of text would go if we're printing multiple lines. (Text must remain same size!)
        self.NextTextX = fromx # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.NextTextY = fromy + ydim # If printing multiple lines of text, this is the start point for the next line if you're printing downwards.
        self.PrevTextX = fromx # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        self.PrevTextY = fromy - ydim # If printing multiple lines of text, this is the start point for the previous line if your printing upwards.
        self.ActionList.append(['addedgetext',text,fromx,fromy,color,size,thickness])
        self.ModifiedTimestamp = self.Now()
        return True

    def DrawPolygon(self,pointlist,color=None,thickness=None):
        """ Draw polygon. 
            pointlist is a list of (x,y) tuples. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawPolygon(",pointlist,color,thickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawPolygon: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        # *Q* OrientCoord() to do.
        cv2.drawPoly(self.ImageBuffer, np.array([pointlist]), color=color,thickness=thickness)
        self.ActionList.append(['drawpolygon',pointlist,color,thickness])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def DrawEdgePolygon(self,pointlist,color=None,edgecolor=None,thickness=None,edgethickness=None):
        """ Draw polygon. 
            pointlist is a list of (x,y) tuples. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawEdgePolygon(",pointlist,color,edgecolor,thickness,edgethickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage",self.Name,''.DrawEdgePolygon: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        if edgethickness == None: edgethickness = 1 # center thickness + 1 pixel either side.
        color = self.SafeColor(color)
        edgecolor = self.SafeColor(edgecolor)
        # *Q* OrientCoord() to do.
        cv2.drawPoly(self.ImageBuffer, np.array([pointlist]), color=edgecolor,thickness=int(thickness + (2 * edgethickness)))
        cv2.drawPoly(self.ImageBuffer, np.array([pointlist]), color=color,thickness=thickness)
        self.ActionList.append(['drawedgepolygon',pointlist,color,edgecolor,thickness,edgethickness])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def FillPolygon(self,pointlist,color=None):
        """ Draw filled polygon. 
            pointlist is a list of (x,y) tuples. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FillPolygon(",pointlist,color,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FillPolygon: No image in the buffer.')
        color = self.SafeColor(color)
        # *Q* OrientCoord() to do.
        cv2.fillPoly(self.ImageBuffer, np.array([pointlist]), color=color)
        self.ActionList.append(['fillpolygon',pointlist,color])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def DrawRectangle(self,startcoord,endcoord,color=None,thickness=None):
        """ Draw a Rectangle on the image. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawRectangle(",startcoord,endcoord,color,thickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawRectangle: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        startcoord = self.OrientCoord(startcoord) # Get height right way up.
        endcoord = self.OrientCoord(endcoord) # Get height right way up.
        self.ImageBuffer = cv2.rectangle(self.ImageBuffer, startcoord, endcoord, color, thickness)
        self.ActionList.append(['drawrectangle',startcoord, endcoord, color, thickness])
        self.ModifiedTimestamp = self.Now()
        return True
        
    def FillRectangle(self,startcoord,endcoord,color=None):
        """ Draw a filled Rectangle on the image. """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FillRectangle(",startcoord,endcoord,color,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FillRectangle: No image in the buffer.')
        color = self.SafeColor(color)
        startcoord = self.OrientCoord(startcoord) # Get height right way up.
        endcoord = self.OrientCoord(endcoord) # Get height right way up.
        self.ImageBuffer = cv2.rectangle(self.ImageBuffer, startcoord, endcoord, color, thickness=-1)
        self.ActionList.append(['fillrectangle',startcoord, endcoord, color])
        self.ModifiedTimestamp = self.Now()
        return True

    def FadeRectangle(self,startcoord,endcoord,color=None,fadecolor=None):
        """ Fill a ractangle on the image, but the color fades from center to edge """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FadeRectangle(",center_x,center_y,color,rad,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FadeRectangle: No image in the buffer.')
        color = self.SafeColor(color)
        if fadecolor == None: fadecolor = self.SafeColor(0) # Default to Black.
        else: fadecolor = self.SafeColor(fadecolor)
        prevcolor = None # Only draw rectangles when the color changes.
        side_x = endcoord[0] - startcoord[0]
        side_y = endcoord[1] - startcoord[1]
        center_x = int((endcoord[0] + startcoord[0]) / 2)
        center_y = int((endcoord[1] + startcoord[1]) / 2)
        rad = max(abs(side_x), abs(side_y))
        for i in range(rad, 0, -4):
            colorratio = (rad - i) / float(rad) # Ratio is ZERO at the edge.
            sizeratio = i / float(rad) 
            gradedcolor = self.BlendColor(color,fadecolor,colorratio)
            if gradedcolor != prevcolor:
                startcoord = (int(center_x - (side_x * sizeratio / 2)),int(center_y - (side_y * sizeratio / 2)))
                endcoord = (int(center_x + (side_x * sizeratio / 2)),int(center_y + (side_y * sizeratio / 2)))
                startcoord = self.OrientCoord(startcoord) # Get height right way up.
                endcoord = self.OrientCoord(endcoord) # Get height right way up.
                self.ImageBuffer = cv2.rectangle(self.ImageBuffer, startcoord, endcoord, gradedcolor, thickness=-1)
                prevcolor = gradedcolor
        self.ActionList.append(['faderectangle',startcoord,endcoord,color,fadecolor])
        self.ModifiedTimestamp = self.Now()
        return True

    def DrawEllipse(self,center_x, center_y, axis_x, axis_y, angle=0, startAngle=0, endAngle=360, color=None, thickness=None):
        """ Draw an ellipse on the image. 
            center_coordinates = (x,y)
            axeslength = (a,b)
            angle = 0-360
            startAngle = 0-360
            endAngle = 0-360 """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawEllipse",self.Name,"(", center_x, center_y, axis_x, axis_y, angle, startAngle, endAngle, color, thickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawEllipse: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
        center_y = self.OrientHeight(center_y)
        # *Q* OrientHeight needs to switch angles too.
        self.ImageBuffer = cv2.ellipse(self.ImageBuffer, (int(center_x), int(center_y)), (int(axis_x), int(axis_y)), int(angle), int(startAngle), int(endAngle), color, thickness, lineType=cv2.LINE_AA)
        self.ActionList.append(['drawellipse',center_x,center_y,axis_x,axis_y,angle,startAngle,endAngle,color,thickness])
        self.ModifiedTimestamp = self.Now()
        return True

    def DrawEdgeEllipse(self,center_x, center_y, axis_x, axis_y, angle=0, startAngle=0, endAngle=360, color=None, edgecolor=None, thickness=None, edgethickness=1):
        """ Draw an ellipse on the image. 
            center_coordinates = (x,y)
            axeslength = (a,b)
            angle = 0-360
            startAngle = 0-360
            endAngle = 0-360 """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawEllipse",self.Name,"(", center_x, center_y, axis_x, axis_y, angle, startAngle, endAngle, color, thickness,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.DrawEdgeEllipse: No image in the buffer.')
        thickness = self.SafeThickness(thickness)
        color = self.SafeColor(color)
        edgethickness = self.SafeThickness(edgethickness)
        edgecolor = self.SafeColor(edgecolor)
        # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
        center_y = self.OrientHeight(center_y)
        # *Q* OrientHeight needs to switch angles too.
        self.ImageBuffer = cv2.ellipse(self.ImageBuffer, (int(center_x), int(center_y)), (int(axis_x), int(axis_y)), int(angle), int(startAngle), int(endAngle), edgecolor, (thickness + 2 * edgethickness), lineType=cv2.LINE_AA)
        self.ImageBuffer = cv2.ellipse(self.ImageBuffer, (int(center_x), int(center_y)), (int(axis_x), int(axis_y)), int(angle), int(startAngle), int(endAngle), color, thickness, lineType=cv2.LINE_AA)
        self.ActionList.append(['drawedgeellipse',center_x,center_y,axis_x,axis_y,angle,startAngle,endAngle,color,thickness])
        self.ModifiedTimestamp = self.Now()
        return True

    def FillEllipse(self,center_x, center_y, axis_x, axis_y, angle=0, startAngle=0, endAngle=360, color=None):
        """ Draw an ellipse on the image. 
            center_coordinates = (x,y)
            axeslength = (a,b)
            angle = 0-360
            startAngle = 0-360
            endAngle = 0-360 """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FillEllipse(", center_x, center_y, axis_x, axis_y, angle, startAngle, endAngle, color,")",terminal=False)
        if self.ImageMissing(): print('pilomarimage',self.Name,'.FillEllipse: No image in the buffer.')
        color = self.SafeColor(color)
        center_y = self.OrientHeight(center_y)
        # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
        self.ImageBuffer = cv2.ellipse(self.ImageBuffer, (int(center_x), int(center_y)), (int(axis_x), int(axis_y)), int(angle), int(startAngle), int(endAngle), color, thickness=-1, lineType=cv2.LINE_AA)
        self.ActionList.append(['fillellipse', center_x, center_y, axis_x, axis_y, angle, startAngle, endAngle, color])
        self.ModifiedTimestamp = self.Now()
        return True

    def FadeEllipse(self,center_x, center_y, axis_x, axis_y, angle=0, startAngle=0, endAngle=360, color=None, fadecolor=None):
        """ Fill an ellipse on the image, but the color fades from center to edge """
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".FadeEllipse(", center_x, center_y, axis_x, axis_y, angle, startAngle, endAngle, color,")",terminal=False)
        if self.ImageMissing(): 
            print('pilomarimage',self.Name,'.FadeEllipse: No image in the buffer.')
            if self.Log != None: self.Log('pilomarimage',self.Name,'.FadeEllipse: No image in the buffer.',level='error',terminal=True)

        color = self.SafeColor(color)
        if fadecolor == None: fadecolor = self.SafeColor(0) # Default to Black.
        else: fadecolor = self.SafeColor(fadecolor)
        prevcolor = None # Only draw ellipses when the color changes.
        rad = max(axis_x, axis_y)
        for i in range(rad, 0, -2):
            colorratio = (rad - i) / float(rad) # Ratio is ZERO at the edge.
            sizeratio = i / float(rad) 
            gradedcolor = self.BlendColor(color,fadecolor,colorratio)
            if gradedcolor != prevcolor:
                # Weird behaviour of this function in Python3 (See online) - parameters very fussy about grouping and datatype.
                xt = int(axis_x * sizeratio)
                yt = int(axis_y * sizeratio)
                center_y = self.OrientHeight(center_y)
                self.ImageBuffer = cv2.ellipse(self.ImageBuffer, (int(center_x), int(center_y)), (xt, yt), int(angle), int(startAngle), int(endAngle), gradedcolor, thickness=-1, lineType=cv2.LINE_AA)
                prevcolor = gradedcolor
        self.ActionList.append(['fadeellipse', center_x, center_y, axis_x, axis_y, angle, startAngle, endAngle, color, fadecolor])
        self.ModifiedTimestamp = self.Now()
        return True

    def DrawDumbbell(self,drawfrom,drawto,rad,fromcolor,tocolor,linecolor,arrow,thickness=None):
        """ Add a 'dumbbell' to an image between two different points.
        
            from = tuple (x,y)
            to = tuple (x,y)
            fromcolor = tuple (b,g,r,a) 
            tocolor = tuple (b,g,r,a)
            linecolor = tuple (b,g,r,a)
            arrow = boolean 6
        
              xxx                     .    xxx
             x   x                     .  x   x
            x     x                     .x     x
            x  O  x----------------------x  o  x
            x     x                     .x     x 
             x   x                     .  x   x
              xxx                     .    xxx                   """
            
        #if self.Log != None and self.LogDrawing: self.Log("pilomarimage",self.Name,".DrawDumbbell(", drawfrom,drawto,rad,fromcolor,tocolor,linecolor,arrow,thickness,")",terminal=False)
        if self.ImageMissing(): 
            print('pilomarimage',self.Name,'.DrawDumbbell: No image in the buffer.')
            if self.Log != None: self.Log('pilomarimage',self.Name,'.DrawDumbbell: No image in the buffer.',level='error',terminal=True)
        drawfrom = self.OrientCoord(drawfrom) # Get height right way around.
        drawto = self.OrientCoord(drawto)
        fromx = drawfrom[0] # center of the FROM circle.
        fromy = drawfrom[1]
        tox = drawto[0] # center of the TO circle.
        toy = drawto[1]
        fromcolor = self.SafeColor(fromcolor)
        tocolor = self.SafeColor(tocolor)
        linecolor = self.SafeColor(linecolor)
        thickness = self.SafeThickness(thickness)
        # Calculate distance between FROM and TO points.
        dx = tox - fromx
        dy = toy - fromy
        distance = math.sqrt((dx **2) + (dy **2))
        angle = math.atan2(dy,dx) # What angle is the joining line at?
        # Line does not cross the boundary circle drawn around each point.
        # Calculate the points on the circumference of each circle that the arrowed line will start and end on.
        rc = rad * math.cos(angle) # x offset for circle edge where line starts.
        rs = rad * math.sin(angle) # y offset for circle edge where line starts.
        startx = int(fromx + rc) # Draw line from this point on the starting circle.
        starty = int(fromy + rs)
        endx = int(tox - rc) # Draw line to this point on the ending circle.
        endy = int(toy - rs)
        dia = rad * 2 # Only draw the line if there's a big enough gap between the two circles.
        if distance > dia: # Enough space to draw a line.
            arrowproportion = 10.0 / (distance - dia) # ArrowedLine specifies arrow size as proportion of line length. We need constant 10pixel arrow heads.
            if arrow: self.ImageBuffer = cv2.arrowedLine(self.ImageBuffer, (startx,starty), (endx,endy), linecolor, thickness=thickness, line_type=cv2.LINE_AA, tipLength=arrowproportion)
            else: self.ImageBuffer = cv2.line(self.ImageBuffer, (startx,starty), (endx,endy), linecolor, thickness=thickness, lineType=cv2.LINE_AA)
        self.ImageBuffer = cv2.circle(self.ImageBuffer,(fromx, fromy), rad, fromcolor, thickness=thickness, lineType=cv2.LINE_AA)
        self.ImageBuffer = cv2.circle(self.ImageBuffer,(tox, toy), rad, tocolor, thickness=thickness, lineType=cv2.LINE_AA)
        self.ActionList.append(['drawdumbbell',drawfrom,drawto,rad,fromcolor,tocolor,linecolor,arrow,thickness])
        self.ModifiedTimestamp = self.Now()
        return True # The image now has the 'dumbbell' drawn on it.

    ### BEGIN DEVELOPMENT ###
    
    def BrightnessHistogram(self):
        """ Return array of brightness levels. 
            Uses a grayscale representation of the current image to calculate the brightness.
            Returns an integer list of 256 entries, each entry is the number of pixels of that brightness. """
        tempbuffer = self.NewBufferType('grayscale') # Create grayscale copy of the buffer.
        hist = cv2.calcHist([tempbuffer],[0],None,[256],[0,256])
        return hist

    def WeightedBrightness(self):
        """ For the current image, calculate the brightness histogram and return the weighted brightness of the image.
            Returns a value in the range 0-255 indicating the weighted average brightness of all the pixels in the image. """
        weightedtotal = 0
        pixeltotal = self.GetWidth() * self.GetHeight()
        for pixelvalue,pixelcount in enumerate(self.BrightnessHistogram()):
            weightedtotal += (pixelvalue + 1) * pixelcount # Add 1 to pixelvalue so that '0' brightness pixels still count.
        wb = round(weightedtotal / pixeltotal,0) - 1 # Calculate weighted average, but subtract 1 to return '0' brightness pixels within range again.
        return wb

    ### END DEVELOPMENT ###
    
    def DescribeImage(self):
        """ Print information about the current image buffer. """
        print("Describe image:")
        print("Name:",self.Name)
        print("Created:",self.CreatedTimestamp,
              "Modified:",self.ModifiedTimestamp)
        if self.ImageExists():
            print("Shape:",self.ImageBuffer.shape)
        else:
            print("ImageBuffer is empty")
        print("Type:",self.GetType())
        michelson_contrast, stddev_contrast = self.MeasureContrast()
        print("Michelson contrast:",michelson_contrast,
              "STD DEV contrast:",stddev_contrast)
        print("Sharpness:",self.Sharpness())
        print("Pen: Color:",self.PenColor,"Thickness:",self.PenThickness)
        print("ActionList:",self.ActionList)

### BEGIN DEVELOPMENT ###
class keograph():
    """ Experimental 'keograph' object. 
        Takes a strip of pixels from a series of images and aligns them side-by-side to create a keograph. 
        Really designed for plotting aurora activity.
        Done as an experiment here. """
        
    def Now(self):
        """ Return system UTC timestamp. """
        return datetime.now(timezone.utc)
        
    def __init__(self,height,width,logger=None,durationhours=6):
        height = int(height)
        width = int(width)
        if height < 1 or width < 1:
            raise Exception("keograph.__init__() invalid dimensions",height,width)
        self.SetLogger(logger) # Any method which supports pilomar's .Log() methods.
        self.Keograph = pilomarimage(name='keograph',logger=logger)
        self.Keograph.New(height,width) # ,imagetype='bgr')
        self.Keograph.FillColor((0,0,0,255)) # Fill black.
        self.StartTime = self.Now()
        self.EndTime = self.StartTime + timedelta(hours=durationhours) # What's the time span of the keograph?
        self.Radius = 0 # Pixel additional radius to extract color from. 0 = target pixel only.
        self.MeanRatio = 1.0 # Proportion of 'mean' sample to apply.
        self.MinRatio = 0.0 # Proportion of 'minimum' sample to apply.
        self.MaxRatio = 0.0 # Proportion of 'maximum' sample to apply.

    def SetLogger(self,logger):
        """ Set up link to logging class and shortcuts to common methods. """
        self.Logger = logger # Logger instance.
        self.Log = None
        self.ReportException = None # Report exception details to logfile.
        self.RaiseException = None # Report and raise exception. 
        if hasattr(logger,'Log'): self.Log = logger.Log # Log method.
        if hasattr(logger,'ReportException'): self.ReportException = logger.ReportException # Report exception details to logfile.
        if hasattr(logger,'RaiseException'): self.RaiseException = logger.RaiseException # Report and raise exception. 
        if self.Log != None: self.Log("pilomarimage.SetLogger(",self.Name,"): Linked to this log file.",terminal=False)
        return True

    def GetPixelColor(self,source,col,row):
        """ Extract pixel value from given location.
            Can apply various sampling methods if needed.
            This currently handles bgr colors only. """
        if self.Radius < 1: # Simple single pixel extraction.
            color = source.GetPixelColor(row,col) # What color is the source image providing?
        else: # More complex analysis of surrounding pixels.
            colortotal = colormean = colormin = colormax = [0,0,0]
            pixelcount = 0
            height, width = source.GetDimensions()
            for c in range(col - self.Radius, col + self.Radius + 1): # Go through all the columns in range.
                for r in range(row - self.Radius, row + self.Radius + 1): # Go through all the rows in range.
                    if (0 <= r < height) and (0 <= c < width): # Pixel exists.
                        cellcolor = source.GetPixelColor(r,c)
                        for i in range(3): 
                            colortotal[i] += cellcolor[i] # Total color.
                            if pixelcount == 0 or cellcolor[i] < colormin[i]: colormin[i] = cellcolor[i] # Select dimmest color.
                            if pixelcount == 0 or cellcolor[i] > colormax[i]: colormax[i] = cellcolor[i] # Select brightest color.
                        pixelcount += 1
            # Now calculate the final value as bgr values.
            for i in range(3):
                colormean[i] = int(self.MeanRatio * colortotal[i] / pixelcount) # Ratio the possible return values.
                colormin[i] = int(self.MinRatio * colormin[i])
                colormax[i] = int(self.MaxRatio * colormax[i])
            color = (colormean[0] + colormin[0] + colormax[0], # Construct final return color.
                     colormean[1] + colormin[1] + colormax[1],
                     colormean[2] + colormin[2] + colormax[2])
        return color

    def ExtractStrip(self,source):
        """ Given another pilomarimage object as a source, extract the strip of pixels and apply it to the keograph. """
        height,width = source.GetDimensions()
        column = int(width / 2) # Select centre column.
        now = self.Now()
        if now > self.EndTime: return False # Off the end of the image.
        timeslot = (self.Now() - self.StartTime) / (self.EndTime - self.StartTime) # Proportion of timespan that this column represents.
        endcolumn = self.Keograph.GetWidth()
        targetcolumn = int(endcolumn * timeslot) # Convert to a specific column.
        if self.Log != None: self.Log("keograph.ExtractStrip(): TargetColumn",targetcolumn,"TimeSlot",timeslot,"Start",self.StartTime,"End",self.EndTime,"Columns",endcolumn,terminal=False)
        for r in range(height): # Go through each pixel in the column in turn.
            color = self.GetPixelColor(source,r,column) # What color is the source image providing?
            #print("ExtractStrip: color",color,"row",r)
            self.Keograph.DrawLine((targetcolumn,r),(endcolumn,r),color) # Apply that color from the timeslot forward to the keograph.
        # Draw time marker during development.
        self.Keograph.DrawLine((targetcolumn,height),(targetcolumn,height - 50),color=self.Keograph.BGRWhite)

    def SaveFile(self,filename,text=None):
        """ Save the keograph. """
        # Add time range to image.
        self.Keograph.AddText("Start: " + str(self.StartTime).split(".")[0] + " UTC",10,self.Keograph.GetHeight() - 10,size=0.5,color=self.Keograph.BGRWhite,bgcolor=self.Keograph.BGRBlack)
        self.Keograph.AddText("End: " + str(self.EndTime).split(".")[0] + " UTC",self.Keograph.GetWidth() - 10,self.Keograph.GetHeight() - 10,size=0.5,color=self.Keograph.BGRWhite,bgcolor=self.Keograph.BGRBlack,hjust='r')
        if text != None: 
            self.Keograph.AddText(text,int(self.Keograph.GetWidth() / 2),self.Keograph.GetHeight() - 10,size=1,color=self.Keograph.BGRWhite,bgcolor=self.Keograph.BGRBlack,hjust='c')
        self.Keograph.SaveFile(filename)
        
### END DEVELOPMENT ###

if __name__ == '__main__':
    pi = pilomarimage()
