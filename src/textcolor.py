#!/usr/bin/python

# textcolor library. For formatting simple puTTY terminal text.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import subprocess
import curses # For non-blocking keyboard scan.
from datetime import datetime,timezone
import pytz # Timezone handling.
import time
import traceback # For exception handling in menu.
import json # To dump dictionaries for export.
import locale # Internationalisation support.
from pathlib import Path # For navigating folder structure.
import os 

class keyboardscanner(): # Curses class to scan keyboard.
    """ Use curses library to scan the keyboard (non-blocking).
        Example: if keyboardscanner.Check().lower() == "x": break
    """
    
    __version__ = '0.0.1'
    
    def __init__(self):
        """    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          
            
            Usage --------------------------------------------
            
            from textcolor import keyboardscanner
            Keyboard = keyboardscanner() # Non-Blocking reader of the keyboard (via curses library).
            while True:
                keypress = Keyboard.Check().lower()
                if keypress != "": print(keypress)
                
        """
        self.CurrentKeyCode = -1
        self.CurrentCharacter = ''
        self.Translations = { # Character sequences can be translated into these more meaningful values.
            chr(9): 'tab',
            chr(10): 'enter',
            chr(27): 'esc',
            chr(27) + chr(91) + chr(97): 'cursorup',
            chr(27) + chr(91) + chr(98): 'cursordown',
            chr(27) + chr(91) + chr(99): 'cursorright',
            chr(27) + chr(91) + chr(100): 'cursorleft',
            chr(265): 'f1',
            chr(267): 'f2'
        }

    def Scan(self,stdscr): # Non-blocking check for keypress.
        """ Non-blocking check for keypress. 
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        stdscr.nodelay(True)  # do not wait for input when calling getch
        self.CurrentKeyCode = stdscr.getch()
        self.CurrentCharacter = ''
        if self.CurrentKeyCode > -1:
            self.CurrentCharacter = chr(self.CurrentKeyCode)

    def WaitForKeypress(self,timeout): # Pause set number of seconds, waiting for keyboard input.
        """ Pause for a set number of seconds, but scan the keyboard. 
            Any input will interrupt the delay and be returned.
            timeout = number of seconds to wait.
            Keyboard is checked every second.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        keypress = ""
        while keypress == "" and timeout > 0:
            time.sleep(1)
            timeout -= 1
            keypress = self.Scan()
        return keypress

    def Check(self): # Return any currently pressed key
        """    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        curses.wrapper(self.Scan)
        return self.CurrentCharacter

    def Translate(self,string): # Translate escape codes into human readable name.
        """ Translate a string of character codes into descriptive text. 
            eg code 27 becomes 'esc'    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        result = self.Translations(string,string) # If the character string can be translated, convert it here.
        return result
        
    def StringCheck(self,translate=False): # Non-blocking check for keypress. Handles complex strings.
        """ Non-blocking check for keypress. 
            Concatenates entire queue of keypresses into a single value.
            translate=True: Some character sequences are translated into more meaningful values.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        keypress = ''
        key_a = self.Check()
        while key_a != '': # Pull entire buffer of characters in one go.
            keypress += key_a
            key_a = self.Check()    
        if translate: keypress = self.Translate(keypress)
        return keypress

    def Flush(self): # Flush any pending keypresses from the buffer.
        """ Flush any pending keypresses from the buffer.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        while self.Check() != '': pass

# ------------------------------------------------------------------------------------------------

class textcolor: # Color text handler for terminal interfaces.
    """ Class with lots of static methods to help with writing to terminals with position and formatting. 
        This is primarily designed to work under puTTY remote terminal connections.
        Behaviour is different under a command line window opened from the desktop.
        
        You don't need to create an instance, it's OK to use textcolor.method() calls directly in your
        code.
                from textcolor import textcolor
                textcolor.clearscreen() 
                print(textcolor.red('Hello'))
                
        It includes various constants such as names of colors.
        It also makes some unicode symbols available via a dictionary so you can refer to them by name.

        Usage :-

            from textcolor import textcolor
            print(textcolor.yellow("Hello") 
                     Would print "Hello" in yellow text on default background. 
                     
            """

    __version__ = '0.0.8'
    TermType = None
    Mode = 'putty' # 'putty' = full color remote terminal, 'simple' = No color, 'local' = Direct connection color.
    # Some standard color names (XTERM names & a couple of common aliases).
    BLACK = 0
    MAROON = 1
    GREEN = 2
    OLIVE = 3
    NAVY = 4
    PURPLE = 5
    TEAL = 6
    SILVER = 7
    GRAY = GREY = 8
    RED = 9
    LIME = 10
    YELLOW = 11
    BLUE = 12
    FUCHSIA = MAGENTA = 13
    AQUA = CYAN = 14
    WHITE = 15
    GREY0 = 16
    NAVYBLUE = 17
    DARKBLUE = 18
    BLUE3 = 19
    BLUE3A = 20
    BLUE1 = 21
    DARKGREEN = 22
    DEEPSKYBLUE4 = 23
    DEEPSKYBLUE4A = 24
    DEEPSKYBLUE4B = 25
    DODGERBLUE3 = 26
    DODGERBLUE2 = 27
    GREEN4 = 28
    SPRINGGREEN4 = 29
    TURQUOISE4 = 30
    DEEPSKYBLUE3 = 31
    DEEPSKYBLUE3A = 32
    DODGERBLUE1 = 33
    GREEN3 = 34
    SPRINGGREEN3 = 35
    DARKCYAN = 36
    LIGHTSEAGREEN = 37
    DEEPSKYBLUE2 = 38
    DEEPSKYBLUE1 = 39
    GREEN3A = 40
    SPRINGGREEN3A = 41
    SPRINGGREEN2 = 42
    CYAN3 = 43
    DARKTURQUOISE = 44
    TURQUOISE2 = 45
    GREEN1 = 46
    SPRINGGREEN2A = 47
    SPRINGGREEN1 = 48
    MEDIUMSPRINGGREEN = 49
    CYAN2 = 50
    CYAN1 = 51
    DARKREDA = 52
    DEEPPINK4 = 53
    PURPLE4 = 54
    PURPLE4A = 55
    PURPLE3 = 56
    BLUEVIOLET = 57
    ORANGE4 = ORANGE = 58
    GREY37 = 59
    MEDIUMPURPLE4 = 60
    SLATEBLUE3 = 61
    SLATEBLUE3A = 62
    ROYALBLUE1 = 63
    CHARTREUSE4 = 64
    DARKSEAGREEN4 = 65
    PALETURQUOISE4 = 66
    STEELBLUE = 67
    STEELBLUE3 = 68
    CORNFLOWERBLUE = 69
    CHARTREUSE3 = 70
    DARKSEAGREEN4A = 71
    CADETBLUE = 72
    CADETBLUEA = 73
    SKYBLUE3 = 74
    STEELBLUE1 = 75
    CHARTREUSE3A = 76
    PALEGREEN3 = 77
    SEAGREEN3 = 78
    AQUAMARINE3 = 79
    MEDIUMTURQUOISE = 80
    STEELBLUE1A = 81
    CHARTREUSE2 = 82
    SEAGREEN2 = 83
    SEAGREEN1 = 84
    SEAGREEN1A = 85
    AQUAMARINE1 = 86
    DARKSLATEGRAY2 = 87
    DARKRED = 88
    DEEPPINK4A = 89
    DARKMAGENTA = 90
    DARKMAGENTAA = 91
    DARKVIOLET = 92
    PURPLE2 = 93
    ORANGE4 = 94
    LIGHTPINK4 = 95
    PLUM4 = 96
    MEDIUMPURPLE3 = 97
    MEDIUMPURPLE3A = 98
    SLATEBLUE1 = 99
    YELLOW4 = 100
    WHEAT4 = 101
    GREY53 = 102
    LIGHTSLATEGREY = 103
    MEDIUMPURPLE = 104
    LIGHTSLATEBLUE = 105
    YELLOW4A = 106
    DARKOLIVEGREEN3 = 107
    DARKSEAGREEN = 108
    LIGHTSKYBLUE3 = 109
    LIGHTSKYBLUE3A = 110
    SKYBLUE2 = 111
    CHARTREUSE2A = 112
    DARKOLIVEGREEN3A = 113
    PALEGREEN3A = 114
    DARKSEAGREEN3 = 115
    DARKSLATEGRAY3 = 116
    SKYBLUE1 = 117
    CHARTREUSE1 = 118
    LIGHTGREEN = 119
    LIGHTGREENA = 120
    PALEGREEN1 = 121
    AQUAMARINE1A = 122
    DARKSLATEGRAY1 = 123
    RED3 = 124
    DEEPPINK4B = 125
    MEDIUMVIOLETRED = 126
    MAGENTA3 = 127
    DARKVIOLETA = 128
    PURPLE5 = 129
    DARKORANGE3 = 130
    INDIANRED = 131
    HOTPINK3 = 132
    MEDIUMORCHID3 = 133
    MEDIUMORCHID = 134
    MEDIUMPURPLE2 = 135
    DARKGOLDENROD = 136
    LIGHTSALMON3 = 137
    ROSYBROWN = 138
    GREY63 = 139
    MEDIUMPURPLE2A = 140
    MEDIUMPURPLE1 = 141
    GOLD3 = 142
    DARKKHAKI = 143
    NAVAJOWHITE3 = 144
    GREY69 = 145
    LIGHTSTEELBLUE3 = 146
    LIGHTSTEELBLUE = 147
    YELLOW3 = 148
    DARKOLIVEGREEN3B = 149
    DARKSEAGREEN3A = 150
    DARKSEAGREEN2 = 151
    LIGHTCYAN3 = 152
    LIGHTSKYBLUE1 = 153
    GREENYELLOW = 154
    DARKOLIVEGREEN2 = 155
    PALEGREEN1A = 156
    DARKSEAGREEN2A = 157
    DARKSEAGREEN1 = 158
    PALETURQUOISE1 = 159
    RED3A = 160
    DEEPPINK3 = 161
    DEEPPINK3A = 162
    MAGENTA3B = 163
    MAGENTA3A = 164
    MAGENTA2 = 165
    DARKORANGE3A = 166
    INDIANREDB = 167
    HOTPINK3A = 168
    HOTPINK2 = 169
    ORCHID = 170
    MEDIUMORCHID1 = 171
    ORANGE3 = 172
    LIGHTSALMON3A = 173
    LIGHTPINK3 = 174
    PINK3 = 175
    PLUM3 = 176
    VIOLET = 177
    GOLD3A = 178
    LIGHTGOLDENROD3 = 179
    TAN = 180
    MISTYROSE3 = 181
    THISTLE3 = 182
    PLUM2 = 183
    YELLOW3A = 184
    KHAKI3 = 185
    LIGHTGOLDENROD2 = 186
    LIGHTYELLOW3 = 187
    GREY84 = 188
    LIGHTSTEELBLUE1 = 189
    YELLOW2 = 190
    DARKOLIVEGREEN1 = 191
    DARKOLIVEGREEN1A = 192
    DARKSEAGREEN1A = 193
    HONEYDEW2 = 194
    LIGHTCYAN1 = 195
    RED1 = 196
    DEEPPINK2 = 197
    DEEPPINK1 = 198
    DEEPPINK1A = 199
    MAGENTA2A = 200
    MAGENTA1 = 201
    ORANGERED1 = 202
    INDIANRED1 = 203
    INDIANRED1A = 204
    HOTPINK = 205
    HOTPINKA = 206
    MEDIUMORCHID1A = 207
    DARKORANGE = 208
    SALMON1 = 209
    LIGHTCORAL = 210
    PALEVIOLETRED1 = 211
    ORCHID2 = 212
    ORCHID1 = 213
    ORANGE1 = 214
    SANDYBROWN = 215
    LIGHTSALMON1 = 216
    LIGHTPINK1 = 217
    PINK1 = 218
    PLUM1 = 219
    GOLD1 = 220
    LIGHTGOLDENROD2B = 221
    LIGHTGOLDENROD2A = 222
    NAVAJOWHITE1 = 223
    MISTYROSE1 = 224
    THISTLE1 = 225
    YELLOW1 = 226
    LIGHTGOLDENROD1 = 227
    KHAKI1 = 228
    WHEAT1 = 229
    CORNSILK1 = 230
    GREY100 = 231
    GREY3 = 232
    GREY7 = 233
    GREY11 = 234
    GREY15 = 235
    GREY19 = 236
    GREY23 = 237
    GREY27 = 238
    GREY30 = 239
    GREY35 = 240
    GREY39 = 241
    GREY42 = 242
    GREY46 = 243
    GREY50 = 244
    GREY54 = 245
    GREY58 = 246
    GREY62 = 247
    GREY66 = 248
    GREY70 = 249
    GREY74 = 250
    GREY78 = 251
    GREY82 = 252
    GREY85 = 253
    GREY89 = 254
    GREY93 = 255
    
    XTERM_COLOR_NAMES = {
        'BLACK':0,
        'MAROON':1,
        'GREEN':2,
        'OLIVE':3,
        'NAVY':4,
        'PURPLE':5,
        'TEAL':6,
        'SILVER':7,
        'GREY':8,
        'GRAY':8,
        'RED':9,
        'LIME':10,
        'YELLOW':11,
        'BLUE':12,
        'FUCHSIA':13,
        'MAGENTA':13,
        'AQUA':14,
        'CYAN':14,
        'WHITE':15,
        'GREY0':16,
        'NAVYBLUE':17,
        'DARKBLUE':18,
        'BLUE3':19,
        'BLUE3A':20,
        'BLUE1':21,
        'DARKGREEN':22,
        'DEEPSKYBLUE4':23,
        'DEEPSKYBLUE4A':24,
        'DEEPSKYBLUE4B':25,
        'DODGERBLUE3':26,
        'DODGERBLUE2':27,
        'GREEN4':28,
        'SPRINGGREEN4':29,
        'TURQUOISE4':30,
        'DEEPSKYBLUE3':31,
        'DEEPSKYBLUE3A':32,
        'DODGERBLUE1':33,
        'GREEN3':34,
        'SPRINGGREEN3':35,
        'DARKCYAN':36,
        'LIGHTSEAGREEN':37,
        'DEEPSKYBLUE2':38,
        'DEEPSKYBLUE1':39,
        'GREEN3A':40,
        'SPRINGGREEN3A':41,
        'SPRINGGREEN2':42,
        'CYAN3':43,
        'DARKTURQUOISE':44,
        'TURQUOISE2':45,
        'GREEN1':46,
        'SPRINGGREEN2A':47,
        'SPRINGGREEN1':48,
        'MEDIUMSPRINGGREEN':49,
        'CYAN2':50,
        'CYAN1':51,
        'DARKREDA':52,
        'DEEPPINK4':53,
        'PURPLE4':54,
        'PURPLE4A':55,
        'PURPLE3':56,
        'BLUEVIOLET':57,
        'ORANGE':58,
        'ORANGE4':58,
        'GREY37':59,
        'MEDIUMPURPLE4':60,
        'SLATEBLUE3':61,
        'SLATEBLUE3A':62,
        'ROYALBLUE1':63,
        'CHARTREUSE4':64,
        'DARKSEAGREEN4':65,
        'PALETURQUOISE4':66,
        'STEELBLUE':67,
        'STEELBLUE3':68,
        'CORNFLOWERBLUE':69,
        'CHARTREUSE3':70,
        'DARKSEAGREEN4A':71,
        'CADETBLUE':72,
        'CADETBLUEA':73,
        'SKYBLUE3':74,
        'STEELBLUE1':75,
        'CHARTREUSE3A':76,
        'PALEGREEN3':77,
        'SEAGREEN3':78,
        'AQUAMARINE3':79,
        'MEDIUMTURQUOISE':80,
        'STEELBLUE1A':81,
        'CHARTREUSE2':82,
        'SEAGREEN2':83,
        'SEAGREEN1':84,
        'SEAGREEN1A':85,
        'AQUAMARINE1':86,
        'DARKSLATEGRAY2':87,
        'DARKRED':88,
        'DEEPPINK4A':89,
        'DARKMAGENTA':90,
        'DARKMAGENTAA':91,
        'DARKVIOLET':92,
        'PURPLE2':93,
        'ORANGE4':94,
        'LIGHTPINK4':95,
        'PLUM4':96,
        'MEDIUMPURPLE3':97,
        'MEDIUMPURPLE3A':98,
        'SLATEBLUE1':99,
        'YELLOW4':100,
        'WHEAT4':101,
        'GREY53':102,
        'LIGHTSLATEGREY':103,
        'MEDIUMPURPLE':104,
        'LIGHTSLATEBLUE':105,
        'YELLOW4A':106,
        'DARKOLIVEGREEN3':107,
        'DARKSEAGREEN':108,
        'LIGHTSKYBLUE3':109,
        'LIGHTSKYBLUE3A':110,
        'SKYBLUE2':111,
        'CHARTREUSE2A':112,
        'DARKOLIVEGREEN3A':113,
        'PALEGREEN3A':114,
        'DARKSEAGREEN3':115,
        'DARKSLATEGRAY3':116,
        'SKYBLUE1':117,
        'CHARTREUSE1':118,
        'LIGHTGREEN':119,
        'LIGHTGREENA':120,
        'PALEGREEN1':121,
        'AQUAMARINE1A':122,
        'DARKSLATEGRAY1':123,
        'RED3':124,
        'DEEPPINK4B':125,
        'MEDIUMVIOLETRED':126,
        'MAGENTA3':127,
        'DARKVIOLETA':128,
        'PURPLE5':129,
        'DARKORANGE3':130,
        'INDIANRED':131,
        'HOTPINK3':132,
        'MEDIUMORCHID3':133,
        'MEDIUMORCHID':134,
        'MEDIUMPURPLE2':135,
        'DARKGOLDENROD':136,
        'LIGHTSALMON3':137,
        'ROSYBROWN':138,
        'GREY63':139,
        'MEDIUMPURPLE2A':140,
        'MEDIUMPURPLE1':141,
        'GOLD3':142,
        'DARKKHAKI':143,
        'NAVAJOWHITE3':144,
        'GREY69':145,
        'LIGHTSTEELBLUE3':146,
        'LIGHTSTEELBLUE':147,
        'YELLOW3':148,
        'DARKOLIVEGREEN3B':149,
        'DARKSEAGREEN3A':150,
        'DARKSEAGREEN2':151,
        'LIGHTCYAN3':152,
        'LIGHTSKYBLUE1':153,
        'GREENYELLOW':154,
        'DARKOLIVEGREEN2':155,
        'PALEGREEN1A':156,
        'DARKSEAGREEN2A':157,
        'DARKSEAGREEN1':158,
        'PALETURQUOISE1':159,
        'RED3A':160,
        'DEEPPINK3':161,
        'DEEPPINK3A':162,
        'MAGENTA3B':163,
        'MAGENTA3A':164,
        'MAGENTA2':165,
        'DARKORANGE3A':166,
        'INDIANREDB':167,
        'HOTPINK3A':168,
        'HOTPINK2':169,
        'ORCHID':170,
        'MEDIUMORCHID1':171,
        'ORANGE3':172,
        'LIGHTSALMON3A':173,
        'LIGHTPINK3':174,
        'PINK3':175,
        'PLUM3':176,
        'VIOLET':177,
        'GOLD3A':178,
        'LIGHTGOLDENROD3':179,
        'TAN':180,
        'MISTYROSE3':181,
        'THISTLE3':182,
        'PLUM2':183,
        'YELLOW3A':184,
        'KHAKI3':185,
        'LIGHTGOLDENROD2':186,
        'LIGHTYELLOW3':187,
        'GREY84':188,
        'LIGHTSTEELBLUE1':189,
        'YELLOW2':190,
        'DARKOLIVEGREEN1':191,
        'DARKOLIVEGREEN1A':192,
        'DARKSEAGREEN1A':193,
        'HONEYDEW2':194,
        'LIGHTCYAN1':195,
        'RED1':196,
        'DEEPPINK2':197,
        'DEEPPINK1':198,
        'DEEPPINK1A':199,
        'MAGENTA2A':200,
        'MAGENTA1':201,
        'ORANGERED1':202,
        'INDIANRED1':203,
        'INDIANRED1A':204,
        'HOTPINK':205,
        'HOTPINKA':206,
        'MEDIUMORCHID1A':207,
        'DARKORANGE':208,
        'SALMON1':209,
        'LIGHTCORAL':210,
        'PALEVIOLETRED1':211,
        'ORCHID2':212,
        'ORCHID1':213,
        'ORANGE1':214,
        'SANDYBROWN':215,
        'LIGHTSALMON1':216,
        'LIGHTPINK1':217,
        'PINK1':218,
        'PLUM1':219,
        'GOLD1':220,
        'LIGHTGOLDENROD2B':221,
        'LIGHTGOLDENROD2A':222,
        'NAVAJOWHITE1':223,
        'MISTYROSE1':224,
        'THISTLE1':225,
        'YELLOW1':226,
        'LIGHTGOLDENROD1':227,
        'KHAKI1':228,
        'WHEAT1':229,
        'CORNSILK1':230,
        'GREY100':231,
        'GREY3':232,
        'GREY7':233,
        'GREY11':234,
        'GREY15':235,
        'GREY19':236,
        'GREY23':237,
        'GREY27':238,
        'GREY30':239,
        'GREY35':240,
        'GREY39':241,
        'GREY42':242,
        'GREY46':243,
        'GREY50':244,
        'GREY54':245,
        'GREY58':246,
        'GREY62':247,
        'GREY66':248,
        'GREY70':249,
        'GREY74':250,
        'GREY78':251,
        'GREY82':252,
        'GREY85':253,
        'GREY89':254,
        'GREY93':255
    }

    XTERM_COLORS = {
        0: {'names': ['BLACK'], 'rgb': (0, 0, 0), 'hsv': (0, 0, 0.0)},
        1: {'names': ['MAROON'], 'rgb': (128, 0, 0), 'hsv': (0.0, 1.0, 0.5019607843137255)},
        2: {'names': ['GREEN'], 'rgb': (0, 128, 0), 'hsv': (120.0, 1.0, 0.5019607843137255)},
        3: {'names': ['OLIVE'], 'rgb': (128, 128, 0), 'hsv': (60.0, 1.0, 0.5019607843137255)},
        4: {'names': ['NAVY'], 'rgb': (0, 0, 128), 'hsv': (240.0, 1.0, 0.5019607843137255)},
        5: {'names': ['PURPLE'], 'rgb': (128, 0, 128), 'hsv': (300.0, 1.0, 0.5019607843137255)},
        6: {'names': ['TEAL'], 'rgb': (0, 128, 128), 'hsv': (180.0, 1.0, 0.5019607843137255)},
        7: {'names': ['SILVER'], 'rgb': (192, 192, 192), 'hsv': (0, 0.0, 0.7529411764705882)},
        8: {'names': ['GREY', 'GRAY'], 'rgb': (128, 128, 128), 'hsv': (0, 0.0, 0.5019607843137255)},
        9: {'names': ['RED'], 'rgb': (255, 0, 0), 'hsv': (0.0, 1.0, 1.0)},
        10: {'names': ['LIME'], 'rgb': (0, 255, 0), 'hsv': (120.0, 1.0, 1.0)},
        11: {'names': ['YELLOW'], 'rgb': (255, 255, 0), 'hsv': (60.0, 1.0, 1.0)},
        12: {'names': ['BLUE'], 'rgb': (0, 0, 255), 'hsv': (240.0, 1.0, 1.0)},
        13: {'names': ['FUCHSIA', 'MAGENTA'], 'rgb': (255, 0, 255), 'hsv': (300.0, 1.0, 1.0)},
        14: {'names': ['AQUA', 'CYAN'], 'rgb': (0, 255, 255), 'hsv': (180.0, 1.0, 1.0)},
        15: {'names': ['WHITE'], 'rgb': (255, 255, 255), 'hsv': (0, 0.0, 1.0)},
        16: {'names': ['GREY0'], 'rgb': (0, 0, 0), 'hsv': (0, 0, 0.0)},
        17: {'names': ['NAVYBLUE'], 'rgb': (0, 0, 95), 'hsv': (240.0, 1.0, 0.37254901960784315)},
        18: {'names': ['DARKBLUE'], 'rgb': (0, 0, 135), 'hsv': (240.0, 1.0, 0.5294117647058824)},
        19: {'names': ['BLUE3'], 'rgb': (0, 0, 175), 'hsv': (240.0, 1.0, 0.6862745098039216)},
        20: {'names': ['BLUE3A'], 'rgb': (0, 0, 215), 'hsv': (240.0, 1.0, 0.8431372549019608)},
        21: {'names': ['BLUE1'], 'rgb': (0, 0, 255), 'hsv': (240.0, 1.0, 1.0)},
        22: {'names': ['DARKGREEN'], 'rgb': (0, 95, 0), 'hsv': (120.0, 1.0, 0.37254901960784315)},
        23: {'names': ['DEEPSKYBLUE4'], 'rgb': (0, 95, 95), 'hsv': (180.0, 1.0, 0.37254901960784315)},
        24: {'names': ['DEEPSKYBLUE4A'], 'rgb': (0, 95, 135), 'hsv': (197.77777777777777, 1.0, 0.5294117647058824)},
        25: {'names': ['DEEPSKYBLUE4B'], 'rgb': (0, 95, 175), 'hsv': (207.42857142857144, 1.0, 0.6862745098039216)},
        26: {'names': ['DODGERBLUE3'], 'rgb': (0, 95, 215), 'hsv': (213.48837209302326, 1.0, 0.8431372549019608)},
        27: {'names': ['DODGERBLUE2'], 'rgb': (0, 95, 255), 'hsv': (217.64705882352942, 1.0, 1.0)},
        28: {'names': ['GREEN4'], 'rgb': (0, 135, 0), 'hsv': (120.0, 1.0, 0.5294117647058824)},
        29: {'names': ['SPRINGGREEN4'], 'rgb': (0, 135, 95), 'hsv': (162.22222222222223, 1.0, 0.5294117647058824)},
        30: {'names': ['TURQUOISE4'], 'rgb': (0, 135, 135), 'hsv': (180.0, 1.0, 0.5294117647058824)},
        31: {'names': ['DEEPSKYBLUE3'], 'rgb': (0, 135, 175), 'hsv': (193.71428571428572, 1.0, 0.6862745098039216)},
        32: {'names': ['DEEPSKYBLUE3A'], 'rgb': (0, 135, 215), 'hsv': (202.32558139534882, 1.0, 0.8431372549019608)},
        33: {'names': ['DODGERBLUE1'], 'rgb': (0, 135, 255), 'hsv': (208.23529411764707, 1.0, 1.0)},
        34: {'names': ['GREEN3'], 'rgb': (0, 175, 0), 'hsv': (120.0, 1.0, 0.6862745098039216)},
        35: {'names': ['SPRINGGREEN3'], 'rgb': (0, 175, 95), 'hsv': (152.57142857142856, 1.0, 0.6862745098039216)},
        36: {'names': ['DARKCYAN'], 'rgb': (0, 175, 135), 'hsv': (166.28571428571428, 1.0, 0.6862745098039216)},
        37: {'names': ['LIGHTSEAGREEN'], 'rgb': (0, 175, 175), 'hsv': (180.0, 1.0, 0.6862745098039216)},
        38: {'names': ['DEEPSKYBLUE2'], 'rgb': (0, 175, 215), 'hsv': (191.1627906976744, 1.0, 0.8431372549019608)},
        39: {'names': ['DEEPSKYBLUE1'], 'rgb': (0, 175, 255), 'hsv': (198.8235294117647, 1.0, 1.0)},
        40: {'names': ['GREEN3A'], 'rgb': (0, 215, 0), 'hsv': (120.0, 1.0, 0.8431372549019608)},
        41: {'names': ['SPRINGGREEN3A'], 'rgb': (0, 215, 95), 'hsv': (146.51162790697674, 1.0, 0.8431372549019608)},
        42: {'names': ['SPRINGGREEN2'], 'rgb': (0, 215, 135), 'hsv': (157.67441860465118, 1.0, 0.8431372549019608)},
        43: {'names': ['CYAN3'], 'rgb': (0, 215, 175), 'hsv': (168.8372093023256, 1.0, 0.8431372549019608)},
        44: {'names': ['DARKTURQUOISE'], 'rgb': (0, 215, 215), 'hsv': (180.0, 1.0, 0.8431372549019608)},
        45: {'names': ['TURQUOISE2'], 'rgb': (0, 215, 255), 'hsv': (189.41176470588235, 1.0, 1.0)},
        46: {'names': ['GREEN1'], 'rgb': (0, 255, 0), 'hsv': (120.0, 1.0, 1.0)},
        47: {'names': ['SPRINGGREEN2A'], 'rgb': (0, 255, 95), 'hsv': (142.35294117647058, 1.0, 1.0)},
        48: {'names': ['SPRINGGREEN1'], 'rgb': (0, 255, 135), 'hsv': (151.76470588235293, 1.0, 1.0)},
        49: {'names': ['MEDIUMSPRINGGREEN'], 'rgb': (0, 255, 175), 'hsv': (161.1764705882353, 1.0, 1.0)},
        50: {'names': ['CYAN2'], 'rgb': (0, 255, 215), 'hsv': (170.58823529411765, 1.0, 1.0)},
        51: {'names': ['CYAN1'], 'rgb': (0, 255, 255), 'hsv': (180.0, 1.0, 1.0)},
        52: {'names': ['DARKREDA'], 'rgb': (95, 0, 0), 'hsv': (0.0, 1.0, 0.37254901960784315)},
        53: {'names': ['DEEPPINK4'], 'rgb': (95, 0, 95), 'hsv': (300.0, 1.0, 0.37254901960784315)},
        54: {'names': ['PURPLE4'], 'rgb': (95, 0, 135), 'hsv': (282.22222222222223, 1.0, 0.5294117647058824)},
        55: {'names': ['PURPLE4A'], 'rgb': (95, 0, 175), 'hsv': (272.57142857142856, 1.0, 0.6862745098039216)},
        56: {'names': ['PURPLE3'], 'rgb': (95, 0, 215), 'hsv': (266.51162790697674, 1.0, 0.8431372549019608)},
        57: {'names': ['BLUEVIOLET'], 'rgb': (95, 0, 255), 'hsv': (262.3529411764706, 1.0, 1.0)},
        58: {'names': ['ORANGE'], 'rgb': (95, 95, 0), 'hsv': (60.0, 1.0, 0.37254901960784315)},
        94: {'names': ['ORANGE4'], 'rgb': (135, 95, 0), 'hsv': (42.22222222222223, 1.0, 0.5294117647058824)},
        59: {'names': ['GREY37'], 'rgb': (95, 95, 95), 'hsv': (0, 0.0, 0.37254901960784315)},
        60: {'names': ['MEDIUMPURPLE4'], 'rgb': (95, 95, 135), 'hsv': (240.0, 0.2962962962962963, 0.5294117647058824)},
        61: {'names': ['SLATEBLUE3'], 'rgb': (95, 95, 175), 'hsv': (240.0, 0.45714285714285713, 0.6862745098039216)},
        62: {'names': ['SLATEBLUE3A'], 'rgb': (95, 95, 215), 'hsv': (240.0, 0.5581395348837209, 0.8431372549019608)},
        63: {'names': ['ROYALBLUE1'], 'rgb': (95, 95, 255), 'hsv': (240.0, 0.6274509803921569, 1.0)},
        64: {'names': ['CHARTREUSE4'], 'rgb': (95, 135, 0), 'hsv': (77.77777777777777, 1.0, 0.5294117647058824)},
        65: {'names': ['DARKSEAGREEN4'], 'rgb': (95, 135, 95), 'hsv': (120.0, 0.2962962962962963, 0.5294117647058824)},
        66: {'names': ['PALETURQUOISE4'], 'rgb': (95, 135, 135), 'hsv': (180.0, 0.2962962962962963, 0.5294117647058824)},
        67: {'names': ['STEELBLUE'], 'rgb': (95, 135, 175), 'hsv': (210.0, 0.45714285714285713, 0.6862745098039216)},
        68: {'names': ['STEELBLUE3'], 'rgb': (95, 135, 215), 'hsv': (220.0, 0.5581395348837209, 0.8431372549019608)},
        69: {'names': ['CORNFLOWERBLUE'], 'rgb': (95, 135, 255), 'hsv': (225.0, 0.6274509803921569, 1.0)},
        70: {'names': ['CHARTREUSE3'], 'rgb': (95, 175, 0), 'hsv': (87.42857142857144, 1.0, 0.6862745098039216)},
        71: {'names': ['DARKSEAGREEN4A'], 'rgb': (95, 175, 95), 'hsv': (120.0, 0.45714285714285713, 0.6862745098039216)},
        72: {'names': ['CADETBLUE'], 'rgb': (95, 175, 135), 'hsv': (150.0, 0.45714285714285713, 0.6862745098039216)},
        73: {'names': ['CADETBLUEA'], 'rgb': (95, 175, 175), 'hsv': (180.0, 0.45714285714285713, 0.6862745098039216)},
        74: {'names': ['SKYBLUE3'], 'rgb': (95, 175, 215), 'hsv': (200.0, 0.5581395348837209, 0.8431372549019608)},
        75: {'names': ['STEELBLUE1'], 'rgb': (95, 175, 255), 'hsv': (210.0, 0.6274509803921569, 1.0)},
        76: {'names': ['CHARTREUSE3A'], 'rgb': (95, 215, 0), 'hsv': (93.48837209302326, 1.0, 0.8431372549019608)},
        77: {'names': ['PALEGREEN3'], 'rgb': (95, 215, 95), 'hsv': (120.0, 0.5581395348837209, 0.8431372549019608)},
        78: {'names': ['SEAGREEN3'], 'rgb': (95, 215, 135), 'hsv': (140.0, 0.5581395348837209, 0.8431372549019608)},
        79: {'names': ['AQUAMARINE3'], 'rgb': (95, 215, 175), 'hsv': (160.0, 0.5581395348837209, 0.8431372549019608)},
        80: {'names': ['MEDIUMTURQUOISE'], 'rgb': (95, 215, 215), 'hsv': (180.0, 0.5581395348837209, 0.8431372549019608)},
        81: {'names': ['STEELBLUE1A'], 'rgb': (95, 215, 255), 'hsv': (195.0, 0.6274509803921569, 1.0)},
        82: {'names': ['CHARTREUSE2'], 'rgb': (95, 255, 0), 'hsv': (97.6470588235294, 1.0, 1.0)},
        83: {'names': ['SEAGREEN2'], 'rgb': (95, 255, 95), 'hsv': (120.0, 0.6274509803921569, 1.0)},
        84: {'names': ['SEAGREEN1'], 'rgb': (95, 255, 135), 'hsv': (135.0, 0.6274509803921569, 1.0)},
        85: {'names': ['SEAGREEN1A'], 'rgb': (95, 255, 175), 'hsv': (150.0, 0.6274509803921569, 1.0)},
        86: {'names': ['AQUAMARINE1'], 'rgb': (95, 255, 215), 'hsv': (165.0, 0.6274509803921569, 1.0)},
        87: {'names': ['DARKSLATEGRAY2'], 'rgb': (95, 255, 255), 'hsv': (180.0, 0.6274509803921569, 1.0)},
        88: {'names': ['DARKRED'], 'rgb': (135, 0, 0), 'hsv': (0.0, 1.0, 0.5294117647058824)},
        89: {'names': ['DEEPPINK4A'], 'rgb': (135, 0, 95), 'hsv': (317.77777777777777, 1.0, 0.5294117647058824)},
        90: {'names': ['DARKMAGENTA'], 'rgb': (135, 0, 135), 'hsv': (300.0, 1.0, 0.5294117647058824)},
        91: {'names': ['DARKMAGENTAA'], 'rgb': (135, 0, 175), 'hsv': (286.2857142857143, 1.0, 0.6862745098039216)},
        92: {'names': ['DARKVIOLET'], 'rgb': (135, 0, 215), 'hsv': (277.6744186046512, 1.0, 0.8431372549019608)},
        93: {'names': ['PURPLE2'], 'rgb': (135, 0, 255), 'hsv': (271.7647058823529, 1.0, 1.0)},
        95: {'names': ['LIGHTPINK4'], 'rgb': (135, 95, 95), 'hsv': (0.0, 0.2962962962962963, 0.5294117647058824)},
        96: {'names': ['PLUM4'], 'rgb': (135, 95, 135), 'hsv': (300.0, 0.2962962962962963, 0.5294117647058824)},
        97: {'names': ['MEDIUMPURPLE3'], 'rgb': (135, 95, 175), 'hsv': (270.0, 0.45714285714285713, 0.6862745098039216)},
        98: {'names': ['MEDIUMPURPLE3A'], 'rgb': (135, 95, 215), 'hsv': (260.0, 0.5581395348837209, 0.8431372549019608)},
        99: {'names': ['SLATEBLUE1'], 'rgb': (135, 95, 255), 'hsv': (255.0, 0.6274509803921569, 1.0)},
        100: {'names': ['YELLOW4'], 'rgb': (135, 135, 0), 'hsv': (60.0, 1.0, 0.5294117647058824)},
        101: {'names': ['WHEAT4'], 'rgb': (135, 135, 95), 'hsv': (60.0, 0.2962962962962963, 0.5294117647058824)},
        102: {'names': ['GREY53'], 'rgb': (135, 135, 135), 'hsv': (0, 0.0, 0.5294117647058824)},
        103: {'names': ['LIGHTSLATEGREY'], 'rgb': (135, 135, 175), 'hsv': (240.0, 0.22857142857142856, 0.6862745098039216)},
        104: {'names': ['MEDIUMPURPLE'], 'rgb': (135, 135, 215), 'hsv': (240.0, 0.37209302325581395, 0.8431372549019608)},
        105: {'names': ['LIGHTSLATEBLUE'], 'rgb': (135, 135, 255), 'hsv': (240.0, 0.47058823529411764, 1.0)},
        106: {'names': ['YELLOW4A'], 'rgb': (135, 175, 0), 'hsv': (73.71428571428572, 1.0, 0.6862745098039216)},
        107: {'names': ['DARKOLIVEGREEN3'], 'rgb': (135, 175, 95), 'hsv': (90.0, 0.45714285714285713, 0.6862745098039216)},
        108: {'names': ['DARKSEAGREEN'], 'rgb': (135, 175, 135), 'hsv': (120.0, 0.22857142857142856, 0.6862745098039216)},
        109: {'names': ['LIGHTSKYBLUE3'], 'rgb': (135, 175, 175), 'hsv': (180.0, 0.22857142857142856, 0.6862745098039216)},
        110: {'names': ['LIGHTSKYBLUE3A'], 'rgb': (135, 175, 215), 'hsv': (210.0, 0.37209302325581395, 0.8431372549019608)},
        111: {'names': ['SKYBLUE2'], 'rgb': (135, 175, 255), 'hsv': (220.0, 0.47058823529411764, 1.0)},
        112: {'names': ['CHARTREUSE2A'], 'rgb': (135, 215, 0), 'hsv': (82.32558139534883, 1.0, 0.8431372549019608)},
        113: {'names': ['DARKOLIVEGREEN3A'], 'rgb': (135, 215, 95), 'hsv': (100.0, 0.5581395348837209, 0.8431372549019608)},
        114: {'names': ['PALEGREEN3A'], 'rgb': (135, 215, 135), 'hsv': (120.0, 0.37209302325581395, 0.8431372549019608)},
        115: {'names': ['DARKSEAGREEN3'], 'rgb': (135, 215, 175), 'hsv': (150.0, 0.37209302325581395, 0.8431372549019608)},
        116: {'names': ['DARKSLATEGRAY3'], 'rgb': (135, 215, 215), 'hsv': (180.0, 0.37209302325581395, 0.8431372549019608)},
        117: {'names': ['SKYBLUE1'], 'rgb': (135, 215, 255), 'hsv': (200.0, 0.47058823529411764, 1.0)},
        118: {'names': ['CHARTREUSE1'], 'rgb': (135, 255, 0), 'hsv': (88.23529411764707, 1.0, 1.0)},
        119: {'names': ['LIGHTGREEN'], 'rgb': (135, 255, 95), 'hsv': (105.0, 0.6274509803921569, 1.0)},
        120: {'names': ['LIGHTGREENA'], 'rgb': (135, 255, 135), 'hsv': (120.0, 0.47058823529411764, 1.0)},
        121: {'names': ['PALEGREEN1'], 'rgb': (135, 255, 175), 'hsv': (140.0, 0.47058823529411764, 1.0)},
        122: {'names': ['AQUAMARINE1A'], 'rgb': (135, 255, 215), 'hsv': (160.0, 0.47058823529411764, 1.0)},
        123: {'names': ['DARKSLATEGRAY1'], 'rgb': (135, 255, 255), 'hsv': (180.0, 0.47058823529411764, 1.0)},
        124: {'names': ['RED3'], 'rgb': (175, 0, 0), 'hsv': (0.0, 1.0, 0.6862745098039216)},
        125: {'names': ['DEEPPINK4B'], 'rgb': (175, 0, 95), 'hsv': (327.42857142857144, 1.0, 0.6862745098039216)},
        126: {'names': ['MEDIUMVIOLETRED'], 'rgb': (175, 0, 135), 'hsv': (313.7142857142857, 1.0, 0.6862745098039216)},
        127: {'names': ['MAGENTA3'], 'rgb': (175, 0, 175), 'hsv': (300.0, 1.0, 0.6862745098039216)},
        128: {'names': ['DARKVIOLETA'], 'rgb': (175, 0, 215), 'hsv': (288.83720930232556, 1.0, 0.8431372549019608)},
        129: {'names': ['PURPLE5'], 'rgb': (175, 0, 255), 'hsv': (281.1764705882353, 1.0, 1.0)},
        130: {'names': ['DARKORANGE3'], 'rgb': (175, 95, 0), 'hsv': (32.571428571428555, 1.0, 0.6862745098039216)},
        131: {'names': ['INDIANRED'], 'rgb': (175, 95, 95), 'hsv': (0.0, 0.45714285714285713, 0.6862745098039216)},
        132: {'names': ['HOTPINK3'], 'rgb': (175, 95, 135), 'hsv': (330.0, 0.45714285714285713, 0.6862745098039216)},
        133: {'names': ['MEDIUMORCHID3'], 'rgb': (175, 95, 175), 'hsv': (300.0, 0.45714285714285713, 0.6862745098039216)},
        134: {'names': ['MEDIUMORCHID'], 'rgb': (175, 95, 215), 'hsv': (280.0, 0.5581395348837209, 0.8431372549019608)},
        135: {'names': ['MEDIUMPURPLE2'], 'rgb': (175, 95, 255), 'hsv': (270.0, 0.6274509803921569, 1.0)},
        136: {'names': ['DARKGOLDENROD'], 'rgb': (175, 135, 0), 'hsv': (46.28571428571428, 1.0, 0.6862745098039216)},
        137: {'names': ['LIGHTSALMON3'], 'rgb': (175, 135, 95), 'hsv': (30.0, 0.45714285714285713, 0.6862745098039216)},
        138: {'names': ['ROSYBROWN'], 'rgb': (175, 135, 135), 'hsv': (0.0, 0.22857142857142856, 0.6862745098039216)},
        139: {'names': ['GREY63'], 'rgb': (175, 135, 175), 'hsv': (300.0, 0.22857142857142856, 0.6862745098039216)},
        140: {'names': ['MEDIUMPURPLE2A'], 'rgb': (175, 135, 215), 'hsv': (270.0, 0.37209302325581395, 0.8431372549019608)},
        141: {'names': ['MEDIUMPURPLE1'], 'rgb': (175, 135, 255), 'hsv': (260.0, 0.47058823529411764, 1.0)},
        142: {'names': ['GOLD3'], 'rgb': (175, 175, 0), 'hsv': (60.0, 1.0, 0.6862745098039216)},
        143: {'names': ['DARKKHAKI'], 'rgb': (175, 175, 95), 'hsv': (60.0, 0.45714285714285713, 0.6862745098039216)},
        144: {'names': ['NAVAJOWHITE3'], 'rgb': (175, 175, 135), 'hsv': (60.0, 0.22857142857142856, 0.6862745098039216)},
        145: {'names': ['GREY69'], 'rgb': (175, 175, 175), 'hsv': (0, 0.0, 0.6862745098039216)},
        146: {'names': ['LIGHTSTEELBLUE3'], 'rgb': (175, 175, 215), 'hsv': (240.0, 0.18604651162790697, 0.8431372549019608)},
        147: {'names': ['LIGHTSTEELBLUE'], 'rgb': (175, 175, 255), 'hsv': (240.0, 0.3137254901960784, 1.0)},
        148: {'names': ['YELLOW3'], 'rgb': (175, 215, 0), 'hsv': (71.16279069767441, 1.0, 0.8431372549019608)},
        149: {'names': ['DARKOLIVEGREEN3B'], 'rgb': (175, 215, 95), 'hsv': (80.00000000000001, 0.5581395348837209, 0.8431372549019608)},
        150: {'names': ['DARKSEAGREEN3A'], 'rgb': (175, 215, 135), 'hsv': (90.0, 0.37209302325581395, 0.8431372549019608)},
        151: {'names': ['DARKSEAGREEN2'], 'rgb': (175, 215, 175), 'hsv': (120.0, 0.18604651162790697, 0.8431372549019608)},
        152: {'names': ['LIGHTCYAN3'], 'rgb': (175, 215, 215), 'hsv': (180.0, 0.18604651162790697, 0.8431372549019608)},
        153: {'names': ['LIGHTSKYBLUE1'], 'rgb': (175, 215, 255), 'hsv': (210.0, 0.3137254901960784, 1.0)},
        154: {'names': ['GREENYELLOW'], 'rgb': (175, 255, 0), 'hsv': (78.82352941176471, 1.0, 1.0)},
        155: {'names': ['DARKOLIVEGREEN2'], 'rgb': (175, 255, 95), 'hsv': (90.0, 0.6274509803921569, 1.0)},
        156: {'names': ['PALEGREEN1A'], 'rgb': (175, 255, 135), 'hsv': (100.0, 0.47058823529411764, 1.0)},
        157: {'names': ['DARKSEAGREEN2A'], 'rgb': (175, 255, 175), 'hsv': (120.0, 0.3137254901960784, 1.0)},
        158: {'names': ['DARKSEAGREEN1'], 'rgb': (175, 255, 215), 'hsv': (150.0, 0.3137254901960784, 1.0)},
        159: {'names': ['PALETURQUOISE1'], 'rgb': (175, 255, 255), 'hsv': (180.0, 0.3137254901960784, 1.0)},
        160: {'names': ['RED3A'], 'rgb': (215, 0, 0), 'hsv': (0.0, 1.0, 0.8431372549019608)},
        161: {'names': ['DEEPPINK3'], 'rgb': (215, 0, 95), 'hsv': (333.48837209302326, 1.0, 0.8431372549019608)},
        162: {'names': ['DEEPPINK3A'], 'rgb': (215, 0, 135), 'hsv': (322.3255813953488, 1.0, 0.8431372549019608)},
        163: {'names': ['MAGENTA3B'], 'rgb': (215, 0, 175), 'hsv': (311.16279069767444, 1.0, 0.8431372549019608)},
        164: {'names': ['MAGENTA3A'], 'rgb': (215, 0, 215), 'hsv': (300.0, 1.0, 0.8431372549019608)},
        165: {'names': ['MAGENTA2'], 'rgb': (215, 0, 255), 'hsv': (290.5882352941176, 1.0, 1.0)},
        166: {'names': ['DARKORANGE3A'], 'rgb': (215, 95, 0), 'hsv': (26.51162790697674, 1.0, 0.8431372549019608)},
        167: {'names': ['INDIANREDB'], 'rgb': (215, 95, 95), 'hsv': (0.0, 0.5581395348837209, 0.8431372549019608)},
        168: {'names': ['HOTPINK3A'], 'rgb': (215, 95, 135), 'hsv': (340.0, 0.5581395348837209, 0.8431372549019608)},
        169: {'names': ['HOTPINK2'], 'rgb': (215, 95, 175), 'hsv': (320.0, 0.5581395348837209, 0.8431372549019608)},
        170: {'names': ['ORCHID'], 'rgb': (215, 95, 215), 'hsv': (300.0, 0.5581395348837209, 0.8431372549019608)},
        171: {'names': ['MEDIUMORCHID1'], 'rgb': (215, 95, 255), 'hsv': (285.0, 0.6274509803921569, 1.0)},
        172: {'names': ['ORANGE3'], 'rgb': (215, 135, 0), 'hsv': (37.67441860465118, 1.0, 0.8431372549019608)},
        173: {'names': ['LIGHTSALMON3A'], 'rgb': (215, 135, 95), 'hsv': (20.0, 0.5581395348837209, 0.8431372549019608)},
        174: {'names': ['LIGHTPINK3'], 'rgb': (215, 135, 135), 'hsv': (0.0, 0.37209302325581395, 0.8431372549019608)},
        175: {'names': ['PINK3'], 'rgb': (215, 135, 175), 'hsv': (330.0, 0.37209302325581395, 0.8431372549019608)},
        176: {'names': ['PLUM3'], 'rgb': (215, 135, 215), 'hsv': (300.0, 0.37209302325581395, 0.8431372549019608)},
        177: {'names': ['VIOLET'], 'rgb': (215, 135, 255), 'hsv': (280.0, 0.47058823529411764, 1.0)},
        178: {'names': ['GOLD3A'], 'rgb': (215, 175, 0), 'hsv': (48.83720930232556, 1.0, 0.8431372549019608)},
        179: {'names': ['LIGHTGOLDENROD3'], 'rgb': (215, 175, 95), 'hsv': (40.0, 0.5581395348837209, 0.8431372549019608)},
        180: {'names': ['TAN'], 'rgb': (215, 175, 135), 'hsv': (30.0, 0.37209302325581395, 0.8431372549019608)},
        181: {'names': ['MISTYROSE3'], 'rgb': (215, 175, 175), 'hsv': (0.0, 0.18604651162790697, 0.8431372549019608)},
        182: {'names': ['THISTLE3'], 'rgb': (215, 175, 215), 'hsv': (300.0, 0.18604651162790697, 0.8431372549019608)},
        183: {'names': ['PLUM2'], 'rgb': (215, 175, 255), 'hsv': (270.0, 0.3137254901960784, 1.0)},
        184: {'names': ['YELLOW3A'], 'rgb': (215, 215, 0), 'hsv': (60.0, 1.0, 0.8431372549019608)},
        185: {'names': ['KHAKI3'], 'rgb': (215, 215, 95), 'hsv': (60.0, 0.5581395348837209, 0.8431372549019608)},
        186: {'names': ['LIGHTGOLDENROD2'], 'rgb': (215, 215, 135), 'hsv': (60.0, 0.37209302325581395, 0.8431372549019608)},
        187: {'names': ['LIGHTYELLOW3'], 'rgb': (215, 215, 175), 'hsv': (60.0, 0.18604651162790697, 0.8431372549019608)},
        188: {'names': ['GREY84'], 'rgb': (215, 215, 215), 'hsv': (0, 0.0, 0.8431372549019608)},
        189: {'names': ['LIGHTSTEELBLUE1'], 'rgb': (215, 215, 255), 'hsv': (240.0, 0.1568627450980392, 1.0)},
        190: {'names': ['YELLOW2'], 'rgb': (215, 255, 0), 'hsv': (69.41176470588235, 1.0, 1.0)},
        191: {'names': ['DARKOLIVEGREEN1'], 'rgb': (215, 255, 95), 'hsv': (75.0, 0.6274509803921569, 1.0)},
        192: {'names': ['DARKOLIVEGREEN1A'], 'rgb': (215, 255, 135), 'hsv': (80.00000000000001, 0.47058823529411764, 1.0)},
        193: {'names': ['DARKSEAGREEN1A'], 'rgb': (215, 255, 175), 'hsv': (90.0, 0.3137254901960784, 1.0)},
        194: {'names': ['HONEYDEW2'], 'rgb': (215, 255, 215), 'hsv': (120.0, 0.1568627450980392, 1.0)},
        195: {'names': ['LIGHTCYAN1'], 'rgb': (215, 255, 255), 'hsv': (180.0, 0.1568627450980392, 1.0)},
        196: {'names': ['RED1'], 'rgb': (255, 0, 0), 'hsv': (0.0, 1.0, 1.0)},
        197: {'names': ['DEEPPINK2'], 'rgb': (255, 0, 95), 'hsv': (337.6470588235294, 1.0, 1.0)},
        198: {'names': ['DEEPPINK1'], 'rgb': (255, 0, 135), 'hsv': (328.2352941176471, 1.0, 1.0)},
        199: {'names': ['DEEPPINK1A'], 'rgb': (255, 0, 175), 'hsv': (318.8235294117647, 1.0, 1.0)},
        200: {'names': ['MAGENTA2A'], 'rgb': (255, 0, 215), 'hsv': (309.4117647058824, 1.0, 1.0)},
        201: {'names': ['MAGENTA1'], 'rgb': (255, 0, 255), 'hsv': (300.0, 1.0, 1.0)},
        202: {'names': ['ORANGERED1'], 'rgb': (255, 95, 0), 'hsv': (22.35294117647061, 1.0, 1.0)},
        203: {'names': ['INDIANRED1'], 'rgb': (255, 95, 95), 'hsv': (0.0, 0.6274509803921569, 1.0)},
        204: {'names': ['INDIANRED1A'], 'rgb': (255, 95, 135), 'hsv': (345.0, 0.6274509803921569, 1.0)},
        205: {'names': ['HOTPINK'], 'rgb': (255, 95, 175), 'hsv': (330.0, 0.6274509803921569, 1.0)},
        206: {'names': ['HOTPINKA'], 'rgb': (255, 95, 215), 'hsv': (315.0, 0.6274509803921569, 1.0)},
        207: {'names': ['MEDIUMORCHID1A'], 'rgb': (255, 95, 255), 'hsv': (300.0, 0.6274509803921569, 1.0)},
        208: {'names': ['DARKORANGE'], 'rgb': (255, 135, 0), 'hsv': (31.764705882352928, 1.0, 1.0)},
        209: {'names': ['SALMON1'], 'rgb': (255, 135, 95), 'hsv': (15.0, 0.6274509803921569, 1.0)},
        210: {'names': ['LIGHTCORAL'], 'rgb': (255, 135, 135), 'hsv': (0.0, 0.47058823529411764, 1.0)},
        211: {'names': ['PALEVIOLETRED1'], 'rgb': (255, 135, 175), 'hsv': (340.0, 0.47058823529411764, 1.0)},
        212: {'names': ['ORCHID2'], 'rgb': (255, 135, 215), 'hsv': (320.0, 0.47058823529411764, 1.0)},
        213: {'names': ['ORCHID1'], 'rgb': (255, 135, 255), 'hsv': (300.0, 0.47058823529411764, 1.0)},
        214: {'names': ['ORANGE1'], 'rgb': (255, 175, 0), 'hsv': (41.176470588235304, 1.0, 1.0)},
        215: {'names': ['SANDYBROWN'], 'rgb': (255, 175, 95), 'hsv': (30.0, 0.6274509803921569, 1.0)},
        216: {'names': ['LIGHTSALMON1'], 'rgb': (255, 175, 135), 'hsv': (20.0, 0.47058823529411764, 1.0)},
        217: {'names': ['LIGHTPINK1'], 'rgb': (255, 175, 175), 'hsv': (0.0, 0.3137254901960784, 1.0)},
        218: {'names': ['PINK1'], 'rgb': (255, 175, 215), 'hsv': (330.0, 0.3137254901960784, 1.0)},
        219: {'names': ['PLUM1'], 'rgb': (255, 175, 255), 'hsv': (300.0, 0.3137254901960784, 1.0)},
        220: {'names': ['GOLD1'], 'rgb': (255, 215, 0), 'hsv': (50.588235294117624, 1.0, 1.0)},
        221: {'names': ['LIGHTGOLDENROD2B'], 'rgb': (255, 215, 95), 'hsv': (45.0, 0.6274509803921569, 1.0)},
        222: {'names': ['LIGHTGOLDENROD2A'], 'rgb': (255, 215, 135), 'hsv': (40.0, 0.47058823529411764, 1.0)},
        223: {'names': ['NAVAJOWHITE1'], 'rgb': (255, 215, 175), 'hsv': (30.0, 0.3137254901960784, 1.0)},
        224: {'names': ['MISTYROSE1'], 'rgb': (255, 215, 215), 'hsv': (0.0, 0.1568627450980392, 1.0)},
        225: {'names': ['THISTLE1'], 'rgb': (255, 215, 255), 'hsv': (300.0, 0.1568627450980392, 1.0)},
        226: {'names': ['YELLOW1'], 'rgb': (255, 255, 0), 'hsv': (60.0, 1.0, 1.0)},
        227: {'names': ['LIGHTGOLDENROD1'], 'rgb': (255, 255, 95), 'hsv': (60.0, 0.6274509803921569, 1.0)},
        228: {'names': ['KHAKI1'], 'rgb': (255, 255, 135), 'hsv': (60.0, 0.47058823529411764, 1.0)},
        229: {'names': ['WHEAT1'], 'rgb': (255, 255, 175), 'hsv': (60.0, 0.3137254901960784, 1.0)},
        230: {'names': ['CORNSILK1'], 'rgb': (255, 255, 215), 'hsv': (60.0, 0.1568627450980392, 1.0)},
        231: {'names': ['GREY100'], 'rgb': (255, 255, 255), 'hsv': (0, 0.0, 1.0)},
        232: {'names': ['GREY3'], 'rgb': (8, 8, 8), 'hsv': (0, 0.0, 0.03137254901960784)},
        233: {'names': ['GREY7'], 'rgb': (18, 18, 18), 'hsv': (0, 0.0, 0.07058823529411765)},
        234: {'names': ['GREY11'], 'rgb': (28, 28, 28), 'hsv': (0, 0.0, 0.10980392156862745)},
        235: {'names': ['GREY15'], 'rgb': (38, 38, 38), 'hsv': (0, 0.0, 0.14901960784313725)},
        236: {'names': ['GREY19'], 'rgb': (48, 48, 48), 'hsv': (0, 0.0, 0.18823529411764706)},
        237: {'names': ['GREY23'], 'rgb': (58, 58, 58), 'hsv': (0, 0.0, 0.22745098039215686)},
        238: {'names': ['GREY27'], 'rgb': (68, 68, 68), 'hsv': (0, 0.0, 0.26666666666666666)},
        239: {'names': ['GREY30'], 'rgb': (78, 78, 78), 'hsv': (0, 0.0, 0.3058823529411765)},
        240: {'names': ['GREY35'], 'rgb': (88, 88, 88), 'hsv': (0, 0.0, 0.34509803921568627)},
        241: {'names': ['GREY39'], 'rgb': (98, 98, 98), 'hsv': (0, 0.0, 0.3843137254901961)},
        242: {'names': ['GREY42'], 'rgb': (108, 108, 108), 'hsv': (0, 0.0, 0.4235294117647059)},
        243: {'names': ['GREY46'], 'rgb': (118, 118, 118), 'hsv': (0, 0.0, 0.4627450980392157)},
        244: {'names': ['GREY50'], 'rgb': (128, 128, 128), 'hsv': (0, 0.0, 0.5019607843137255)},
        245: {'names': ['GREY54'], 'rgb': (138, 138, 138), 'hsv': (0, 0.0, 0.5411764705882353)},
        246: {'names': ['GREY58'], 'rgb': (148, 148, 148), 'hsv': (0, 0.0, 0.5803921568627451)},
        247: {'names': ['GREY62'], 'rgb': (158, 158, 158), 'hsv': (0, 0.0, 0.6196078431372549)},
        248: {'names': ['GREY66'], 'rgb': (168, 168, 168), 'hsv': (0, 0.0, 0.6588235294117647)},
        249: {'names': ['GREY70'], 'rgb': (178, 178, 178), 'hsv': (0, 0.0, 0.6980392156862745)},
        250: {'names': ['GREY74'], 'rgb': (188, 188, 188), 'hsv': (0, 0.0, 0.7372549019607844)},
        251: {'names': ['GREY78'], 'rgb': (198, 198, 198), 'hsv': (0, 0.0, 0.7764705882352941)},
        252: {'names': ['GREY82'], 'rgb': (208, 208, 208), 'hsv': (0, 0.0, 0.8156862745098039)},
        253: {'names': ['GREY85'], 'rgb': (218, 218, 218), 'hsv': (0, 0.0, 0.8549019607843137)},
        254: {'names': ['GREY89'], 'rgb': (228, 228, 228), 'hsv': (0, 0.0, 0.8941176470588236)},
        255: {'names': ['GREY93'], 'rgb': (238, 238, 238), 'hsv': (0, 0.0, 0.9333333333333333)}
        }
    
    @staticmethod
    def listshades(levels=6):
        """
        List all xterm colors and suggest some associated shades. To help with chosing color schemes.
        """
        print(textcolor.yellow("List of shades for each xterm color:"))
        for xterm_num, values in textcolor.XTERM_COLORS.items():
            line = ""
            line += (values['names'][0]).rjust(17," ") + " = "
            line += textcolor.bgcolor(xterm_num,(" " * 4 + str(xterm_num))[-4:]) + " : "
            h,s,v = values['hsv']
            for i in range(levels):
                j = (i + 2) / (levels + 1)
                rgb = textcolor.HSV2RGB((h,s,j))
                idx = textcolor.rgb_to_xterm(rgb)
                line += textcolor.bgcolor(idx,(" " * 4 + str(idx))[-4:]) + " "
            print(line)                

    @staticmethod
    def getshades(xterm_num,levels=6):
        """
        Given an xterm color number, return a list of 'shades' of that color.
        """
        values = textcolor.XTERM_COLORS[xterm_num]
        h,s,v = values['hsv']
        result = []
        for i in range(levels):
            j = (i + 2) / (levels + 1)
            rgb = textcolor.HSV2RGB((h,s,j))
            idx = textcolor.rgb_to_xterm(rgb)
            result.append(idx)
        return result
                
    @staticmethod
    def RGB2HSV(rgb):
        """
        Receive (r,g,b) tuple, return (h,s,v) tuple.
        """
        # Normalize RGB values to [0, 1]
        r_, g_, b_ = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0

        cmax = max(r_, g_, b_)
        cmin = min(r_, g_, b_)
        delta = cmax - cmin

        # Hue calculation
        if delta == 0:
            h = 0
        elif cmax == r_:
            h = (60 * ((g_ - b_) / delta) + 360) % 360
        elif cmax == g_:
            h = 60 * ((b_ - r_) / delta + 2)
        else:  # cmax == b_
            h = 60 * ((r_ - g_) / delta + 4)

        # Saturation calculation
        s = 0 if cmax == 0 else (delta / cmax)

        # Value calculation
        v = cmax

        return (h, s, v)

    @staticmethod
    def HSV2RGB(hsv):
        """
        Receive (h,s,v) tuple, return (r,g,b) tuple.
        """
        h,s,v = hsv
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if 0 <= h < 60:
            r_, g_, b_ = c, x, 0
        elif 60 <= h < 120:
            r_, g_, b_ = x, c, 0
        elif 120 <= h < 180:
            r_, g_, b_ = 0, c, x
        elif 180 <= h < 240:
            r_, g_, b_ = 0, x, c
        elif 240 <= h < 300:
            r_, g_, b_ = x, 0, c
        else:  # 300 <= h < 360
            r_, g_, b_ = c, 0, x

        r = int(round((r_ + m) * 255))
        g = int(round((g_ + m) * 255))
        b = int(round((b_ + m) * 255))

        return (r, g, b)

    @staticmethod
    def _populate_XTERM_COLORS():
        """
        Used only in development to populate the XTERM_COLORS dictionary with initial values.
        """
        for key,value in textcolor.XTERM_COLOR_NAMES.items():
            entry = textcolor.XTERM_COLORS.get(value,{})
            names = entry.get('names',[])
            if not key in names: names.append(key) # Don't duplicate.
            entry['names'] = names
            r,g,b = textcolor.xterm_to_rgb(value)
            entry['rgb'] = (r,g,b)
            hsv = textcolor.RGB2HSV(entry['rgb'])
            entry['hsv'] = hsv
            textcolor.XTERM_COLORS[value] = entry
        with open('xtermdict.json','w') as f:
            f.write(str(textcolor.XTERM_COLORS))
        for key,value in textcolor.XTERM_COLORS.items():
            if value['names'] == []: print("Failed for",key,value,"duplicates?")
            
    # UTF-8 symbols for special items.
    SYMBOLS = {'left' : '\u2190', 'right' : '\u2192', 'up' : '\u2191', 'down' : '\u2193', 
               'degree' : '\u00B0', 'delta' : '\u0394', 
               'horizontal' : '\u2500', 'vertical' : '\u2502', 'corner_tl' : '\u250c', 'corner_tr' : '\u2510', 'corner_bl' : '\u2514', 'corner_br' : '\u2518', 'crossover' : '\u253c',
               'left_junction' : '\u2524', 'right_junction' : '\u251c', 'top_junction' : '\u2534', 'bottom_junction' : '\u252c',
               'solid' : '\u2588', '0.75' : '\u2593', '0.50' : '\u2592', '0.25' : 'u\2591',
               'sun' : '\u2609', 'moon' : '\u263D', 'mercury' : '\u263F', 'venus' : '\u2640', 'earth' : '\u2641', 'mars' : '\u2642', 'jupiter' : '\u2643', 'saturn' : '\u2644', 'uranus' : '\u2645', 'neptune' : '\u2646', 'pluto' : '\u2647', 'comet' : '\u2604', 'star' : '\u2736'
              }
    # Alternative 7bit character symbols for special items. (If environment doesn't support UTF-8)
    SYMBOLS8 = {'left' : '<', 'right' : '>', 'up' : '^', 'down' : 'v', 
               'degree' : 'd', 'delta' : '~', 
               'horizontal' : '-', 'vertical' : '|', 'corner_tl' : '+', 'corner_tr' : '+', 'corner_bl' : '+', 'corner_br' : '+', 'crossover' : '+',
               'left_junction' : '+', 'right_junction' : '+', 'top_junction' : '+', 'bottom_junction' : '+',
               'solid' : '@', '0.75' : '#', '0.50' : 'X', '0.25' : ':',
               'sun' : 'S', 'moon' : 'l', 'mercury' : 'm', 'venus' : 'v', 'earth' : 'e', 'mars' : 'M', 'jupiter' : 'J', 'saturn' : 's', 'uranus' : 'u', 'neptune' : 'n', 'pluto' : 'p', 'comet' : '@', 'star' : '*'
              }

    @staticmethod
    def SetCurrentLocale(): # Load the locale into the library.
        """ Load the locale into the textcolor library.
            Python may assume it's in UTF-8 unless we load the current environment's settings.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        locale.setlocale(locale.LC_ALL, '')
        
    @staticmethod
    def GetLocale(): # Retrieve the current locale setting for the session.
        """ Retrieve the current locale setting for the session.
            Output -------------------------------------------------------------------
            Returns the detected locale (Language, Characterset) tuple.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        Lang, CharSet = locale.getlocale()
        return (Lang, CharSet)

    @staticmethod
    def CheckLocale(switch=False): # Validate locale capabilities.
        """ If the character set is not UTF-8 then special characters won't print. 
            In that case, convert the SYMBOLS list to safer ISO8859-1 characters.
            Call this at the start of a session before using other textcolor methods.
            Parameters ---------------------------------------------------------------
            switch: False. No changes are made.
            switch: True. The SYMBOLS list is switched to a simpler version that will work with more character sets.
            Output -------------------------------------------------------------------
            Returns the detected locale (Language, Characterset) tuple.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        Lang, CharSet = textcolor.GetLocale()
        if not CharSet in ["UTF-8"] and switch: # Special characters won't work, but we can switch to an alternative list.
            print("textcolor.CheckLocale(): Downgrading special characters for character set",CharSet)
            textcolor.SYMBOLS = textcolor.SYMBOLS8
        return (Lang, CharSet)

    @staticmethod
    def TextBox(linelist,row=None,col=None,fg=None,bg=None,textfg=None,textbg=None,borderfg=None,borderbg=None,minwidth=None,justify=None): # Create pop-up text box from list of strings.
        """ Receive a single string or list of strings.
            Embedded newline characters will also split the text into separate lines within the bounding box.
            Make all lines the same length, surrounded with a box using line drawing characters.
            Print the resulting text box. 
            - row/col specify the location of the top-left corner of the box.
            Colors are applied if specified. 
            - fg/bg applies to text and border. 
            - textfg/textbg applies to text only. 
            - borderfg/borderbg applies to border only.
            - minwidth = minimum character width.
            - justify = 'l'(left),'c'(center),'r'(right) 
            
            If the O/S character set is not UTF-8 the line drawing can fail. 
            So if the print() statements fail, this routine will just print the lines individually instead.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        if type(linelist) != list: linelist = [linelist] # Convert single values to list for simpler processing.
        if justify != None: justify = justify[0].lower() # standardise code.
        # Convert embedded newline characters into separate list elements.
        templinelist = []
        for line in linelist: # Read all the input lines.
            if type(line) != str: line = str(line) # Protect from input errors.
            for newline in line.split('\n'): # Break on newline character.
                templinelist.append(newline)
        linelist = templinelist
        if textfg == None: textfg = fg # Use same color scheme for text and border.
        if textbg == None: textbg = bg # Use same color scheme for text and border.
        if borderfg == None: borderfg = fg # Use same color scheme for text and border.
        if borderbg == None: borderbg = bg # Use same color scheme for text and border.
        maxlen = 0
        for line in linelist: maxlen = max(maxlen,len(line)) # What's the longest line?
        if minwidth != None: maxlen = max(maxlen,minwidth) # Respect minwidth.
        #lines = [line.ljust(maxlen) for line in linelist] # Make all lines the same length.
        printlines = [] # List of color constructed lines to print.
        # 1: Construct top of box.
        if borderfg != None and borderbg != None: # Border color is specified.
            temp = textcolor.fgbgcolor(borderfg,borderbg,textcolor.SYMBOLS['corner_tl'] + (textcolor.SYMBOLS['horizontal'] * maxlen) + textcolor.SYMBOLS['corner_tr'])
            printlines.append(temp)
        else: # No colors specified.
            temp = textcolor.SYMBOLS['corner_tl'] + (textcolor.SYMBOLS['horizontal'] * maxlen) + textcolor.SYMBOLS['corner_tr']
            printlines.append(temp)
        # 2: Construct text lines and box edges.
        for line in linelist:
            temp = ''
            # Vertical edge on left. Color if needed.
            if borderfg != None and borderbg != None: # Border color is specified.
                temp += textcolor.fgbgcolor(borderfg,borderbg,textcolor.SYMBOLS['vertical'])
            else: temp += textcolor.SYMBOLS['vertical']
            # Text inside box. Color if needed.
            # - Justify.
            if justify == 'l': line = line.strip().ljust(maxlen) # left justify (default).
            elif justify == 'c': line = line.strip().center(maxlen) # center justify.
            elif justify == 'r': line = line.strip().rjust(maxlen) # right justify.
            else: line = (line + " " * maxlen)[:maxlen] # Just pad whatever we were given.
            # - Add color.
            if textfg != None and textbg != None: # Text color is specified.
                temp += textcolor.fgbgcolor(textfg,textbg,line)
            else: temp += line
            # Vertical edge on right. Color if needed.
            if borderfg != None and borderbg != None: # Border color is specified.
                temp += textcolor.fgbgcolor(borderfg,borderbg,textcolor.SYMBOLS['vertical'])
            else: temp += textcolor.SYMBOLS['vertical']
            printlines.append(temp)
        # 3: Construct bottom of box.
        if borderfg != None and borderbg != None: # Border color is specified.
            temp = textcolor.fgbgcolor(borderfg,borderbg,textcolor.SYMBOLS['corner_bl'] + (textcolor.SYMBOLS['horizontal'] * maxlen) + textcolor.SYMBOLS['corner_br'])
            printlines.append(temp)
        else: # No colors specified.
            temp = textcolor.SYMBOLS['corner_bl'] + (textcolor.SYMBOLS['horizontal'] * maxlen) + textcolor.SYMBOLS['corner_br']
            printlines.append(temp)
        try: # Try to print with full graphics, but if character set does not allow it, print basic text instead.
            for i,line in enumerate(printlines): # Now display the whole box.
                if row != None and col != None: line = textcolor.cursor(col=col,row=row + i) + line # Add screen location (row and column).
                elif col != None: line = textcolor.cursorright(cols=col) + line # Add screen location (column only).
                textcolor.safeprint(line)
                #textcolor.safeprint(line) # This would reduce to latin1 even if the characters are utf-8
        except Exception as e: # Print simple text if the display won't allow UTF-8 characters.
            print(textcolor.red("textcolor.TextBox():",str(e)))
            for line in linelist:
                print(line)

    @staticmethod
    def ListSymbols(): # List predefined symbols. 
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        for key,value in textcolor.SYMBOLS.items():
            print (key, value)
        
    @staticmethod
    def safetype(raw): # Make sure any value is a string.
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        if type(raw) != type(str): raw = str(raw)
        return raw     

    @staticmethod
    def booltocolor(value,fgtrue=None,fgfalse=None): # Convert boolean value to TRUE or FALSE color.
        """ Given a boolean (or text) value, return it as colored text. 
            True values are colored fgtrue color. 
            False valuse are colored fgfalse color. 
            None values are not colored.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        if fgtrue == None: fgtrue = textcolor.GREEN
        if fgfalse == None: fgfalse = textcolor.RED
        temp = str(value)
        temp = temp.replace("True",textcolor.fgbgcolor(fgtrue,textcolor.BLACK,"True"))
        temp = temp.replace("False",textcolor.fgbgcolor(fgfalse,textcolor.BLACK,"False"))
        return temp

    @staticmethod
    def dictprint(dictionary,level=0,indent=4): # Very simple equivalent to pprint to display a dictionary.
        """
        Very simple dump of dictionary content to terminal.
        Consider using pprint module instead.
        """
        indent = " " * level * 4 
        for key,value in dictionary.items():
            if type(value) == dict: textcolor.dictprint(value,level=level + 1)
            else: print(indent,key,":",value)
            
    @staticmethod
    def listtotext(arglist,sep=' '): # Convert arbitrary list of parameters into a single string.
        """ Given a list of arguments, append all of them into a single string.
            This behaves like the 'print' command for stringing together a list of items
            into a single string. All arguments are converted to 'str' type before adding
            to the output string. 
            sep parameter says what separator is inserted between each element. (default ' ')     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        result = ''
        for a in arglist:
            if a != '':
                if result != '': result += sep
                result += str(a)
        return result

    @staticmethod
    def ascii_only(text,substitute=''): # Strip non ASCII characters from a string.
        """ Return ONLY the ascii (0-127) characters in a string. 
            This removes unicode characters etc. 
            Parameters -------------------------------------------------------------
            text : The text string to be filtered. 
            substitute : The character to use instead of filtered characters. 
                         (Default is no character)     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        return ''.join([i if ord(i) < 128 else substitute for i in text])

    @staticmethod
    def neatprint(*args,**kwargs): # Equivalent of print() for early python versions.
        """ Own 'print' function. 
            Formats neatly in early Python versions.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        sep = ' '
        end = '\n'
        for key,value in kwargs.items():
            if key == 'sep': sep = value
            elif key == 'end': end = value
        line = ''
        for a in args:
            a = textcolor.safetype(a)
            if len(line) > 0: line += sep
            line += a
        print(line,end=end)

    @staticmethod
    def safeprint(*args,**kwargs): # print() statement which converts string to latin1
        """ Own 'print' function. 
            Formats neatly in early Python versions, and reduces utf8 to latin1.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        sep = ' '
        end = '\n'
        for key,value in kwargs.items():
            if key == 'sep': sep = value
            elif key == 'end': end = value
        line = ''
        for a in args:
            a = textcolor.safetype(a)
            if len(line) > 0: line += sep
            line += a
        _, CharSet = locale.getlocale()
        if not CharSet in ["UTF-8"]: # We cannot use utf-8 full set, reduce to simpler iso-8859-1 character set.
            line = line.encode('iso-8859-1', errors='replace').decode()
        print(line,end=end)

    @staticmethod
    def getterminalsize(): # Read terminal size (columns,rows)
        """ Return tuple of the current screen dimensions. 
              (cols,rows)    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ

            Returns ------------------------------------------
            n/a           """
        print('textcolor.getterminalsize() is deprecated. Use textcolor.terminalsize()')
        cols = 80
        rows = 24
        cols = int(textcolor.oscommand('tput cols')[0])
        rows = int(textcolor.oscommand('tput lines')[0])
        return (cols,rows)

    @staticmethod
    def HRNumber(value,base=1000,decimals=1): # Convert number to human readable format.
        """ Given a number return a human readable text version.
            Eg, turning 1,000,000 into 1.0M 
            
            inputs :-
                value = The number to be converted.
                base = 1000. Runs in thousands.
                     = 1024. Runs in IT measurements.
                decimals = The number of decimal places to return.

            HRNumber(56312703,1000) returns :-
                result = '56.3M'
                prefix = 'mega'
                symbol = 'M' 
                    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          
                """
        valdic = {'yocto':{'power':-8,'symbol':'y','name':'septillionth'},
                  'zepto':{'power':-7,'symbol':'z','name':'sextillionth'},
                  'atto' :{'power':-6,'symbol':'a','name':'quintillionth'},
                  'femto':{'power':-5,'symbol':'f','name':'quadrillionth'},
                  'pico': {'power':-4,'symbol':'p','name':'trillionth'},
                  'nano': {'power':-3,'symbol':'n','name':'billionth'},
                  'micro':{'power':-2,'symbol':'u','name':'millionth'},
                  'milli':{'power':-1,'symbol':'m','name':'thousandth'},
                  '':     {'power':0, 'symbol':'','name':''},
                  'kilo': {'power':1, 'symbol':'k','name':'thousand'},
                  'mega': {'power':2, 'symbol':'M','name':'million'},
                  'giga': {'power':3, 'symbol':'G','name':'billion'},
                  'tera': {'power':4, 'symbol':'T','name':'trillion'},
                  'peta': {'power':5, 'symbol':'P','name':'quadrillion'},
                  'exa':  {'power':6, 'symbol':'E','name':'quintillion'},
                  'zetta':{'power':7, 'symbol':'Z','name':'sextillion'},
                  'yotta':{'power':8, 'symbol':'Y','name':'septillion'}}
                  # Not used here...
                  #'centi':{'power':-2, 'symbol':'c','name':'hundredth'},
                  #'deci': {'power':-1, 'symbol':'d','name':'tenth'},
                  #'deca': {'power':1,  'symbol':'da','name':'ten'},
                  #'hecto':{'power':2,  'symbol':'h','name':'hundred'},
        # Default return values.
        result = str(value) # Default has no conversion.
        prefix = ''
        symbol = ''
        # Find better return conversion if possible.
        for key,subdict in valdic.items():
            scale = base ** subdict['power']
            ranged = round(value / scale,decimals)
            if 1.0 <= ranged < 1000: # This is a good fit.
                result = str(ranged) + subdict['symbol']
                prefix = key
                symbol = subdict['symbol']
                break
        return result, prefix, symbol

    @staticmethod
    def stripcodes(line): # Remove embedded terminal display codes from a line of text.
        """ Remove embedded terminal display codes from a line of text.
            Removes any text starting with "\033[" up to the first letter. (A-Z,a-z)    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        result = ''
        CodeStart = "\033["
        InCode = False
        if line is None or line == '': result = line
        else: # Need to process the characters.
            for i in range(len(line)):
                if line[i:].startswith(CodeStart): InCode = True # We've started a code sequence.
                if not InCode: # We have printable characters.
                    result += line[i]
                if InCode: # We're in a code sequence. Check for it ending.
                    if "a" <= line[i].lower() <= "z": # Code terminator.
                        InCode = False
        return result
        
    @staticmethod
    def oscommand(cmd): # Execute a command,result is returned as clean list of lines.   
        """ Execute a command,result is returned as clean list of lines.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        try:
            result = subprocess.check_output(cmd,shell=True,stderr=subprocess.DEVNULL).decode('utf-8')
        except subprocess.CalledProcessError as e:
            print("textcolor.oscommand(" + cmd + ") returned " + str(e))
            print("textcolor.oscommand(" + cmd + ") returned returncode " + str(e.returncode))
            print("textcolor.oscommand(" + cmd + ") returned output " + str(e.output))
            print("textcolor.oscommand(" + cmd + ") returned cmd " + str(e.cmd))
            print("textcolor.oscommand(" + cmd + ") returned stdout " + str(e.stdout))
            print("textcolor.oscommand(" + cmd + ") returned stderr " + str(e.stderr))
            result = "" # We lose result output, even if some was generated before the error was reached.
        lines = result.split('\n')
        returnlist = []
        for line in lines:
            returnlist.append(line) # Construct clean returnlist of the output.
        return returnlist

    @staticmethod
    def GetTermType(): # Common
        """ Return the termtype and also set the global variable TermType.     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a          """
        textcolor.TermType = textcolor.oscommand('echo $TERM')[0]
        return textcolor.TermType

    @staticmethod
    def terminalsize(): # Common
        """ Return tuple of the current screen dimensions (in characters) = (cols,rows)    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ

            Returns ------------------------------------------
            n/a           """
        cols = 80
        rows = 24
        cols = int(textcolor.oscommand('tput cols')[0])
        rows = int(textcolor.oscommand('tput lines')[0])
        return (cols,rows)

    @staticmethod
    def hidecursor(): # Common
        """ Make the cursor invisible.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        textcolor.oscommand('tput civis')

    @staticmethod
    def showcursor(): # Common
        """ Make the cursor visible.    
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Parameters.DisplayTZ
            ObservationStatusWindow
            ImageStatusWindow
            SessionWindow

            Returns ------------------------------------------
            n/a           """
        textcolor.oscommand('tput cnorm')

    @staticmethod
    def cursorhome():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return textcolor.cursor(0,0)

    @staticmethod
    def cursor(col=0,row=0):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(row) + ";" + str(col) + "H"

    @staticmethod
    def cursorup(rows=1):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(rows) + "A"

    @staticmethod
    def cursordown(rows=1):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(rows) + "B"

    @staticmethod
    def cursorleft(cols=1):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(cols) + "D"

    @staticmethod
    def cursorright(cols=1):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(cols) + "C"

    @staticmethod
    def nextline(rows=1):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(rows) + "E"

    @staticmethod
    def prevline(rows=1):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[" + str(rows) + "F"

    @staticmethod
    def clearlineforward():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[0K"

    @staticmethod
    def clearlinebackward():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[1K"

    @staticmethod
    def clearline():
        """     
           Parameters ---------------------------------------
           n/a
            References ---------------------------------------
           n/a
            Sets ---------------------------------------------
            Returns ------------------------------------------
           n/a          """
        return "\033[2K"

    @staticmethod
    def clearforward():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[0J"

    @staticmethod
    def clearbackward():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        
        return "\033[1J"

    @staticmethod
    def clearall():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[2J"

    @staticmethod
    def clearscreen():
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return textcolor.cursorhome() + textcolor.clearall()

    @staticmethod
    def reset(text=""):
        """     
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        return "\033[0m" + text

    @staticmethod
    def color(value=7,text=''):
        """ XTERM 256 color mode supported. 

            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if textcolor.Mode == 'simple':
            return text
        else:
            return "\033[38;5;" + str(value) + "m" + text + textcolor.reset()

    @staticmethod
    def truecolor(r,g,b,text=''):
        """ Truecolor color mode supported. 
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if textcolor.Mode == 'simple':
            return text
        else:
            return "\033[38;2;" + str(r)+ ";" + str(g) + ";" + str(b) + "mtext\033[0m" + text + textcolor.reset()

    @staticmethod
    def bgcolor(value=0,text=''):
        """ XTERM 256 color mode supported.
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if textcolor.Mode == 'simple':
            return text
        else:
            return "\033[48;5;" + str(value) + "m" + text + textcolor.reset()

    @staticmethod
    def rgbassign(r):
        """ change r(or g or b) value from 0.0-1.0 range into 0-5 range
            This assigns the 0-5 range more evenly depending upon the input 0.0-1.0 value.
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        #if r <= 0.167: re = 0
        #elif r <= 0.333: re = 1
        #elif r <= 0.500: re = 2
        #elif r <= 0.668: re = 3
        #elif r <= 0.833: re = 4
        #else: re = 5
        re = min(int(r // (1/6)),5)
        return re

    @staticmethod
    def rgbdecimal(r,g,b):
        """ Take rgb values (scale 0.00-1.00) and calculate nearest 215 color scheme value.

            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        re = textcolor.rgbassign(r)
        ge = textcolor.rgbassign(g)
        be = textcolor.rgbassign(b)
        v = int(re * 6 * 6) + int(ge * 6) + int(be) + 16
        return v
        
    @staticmethod
    def rgbditherdecimal(r,g,b):
        """ Take rgb values (scale 0.00-1.00) and calculate 2 nearest 215 color scheme values. 
            This is to support using 'dithering' to match colors better.
            Returns 2 colors.            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        # How close is the closest single available color?
        ri = round(r * 5) / 5 # What are the rounded r,g,b levels for input values.
        gi = round(g * 5) / 5
        bi = round(b * 5) / 5
        # What's the difference?
        rd = r - ri
        gd = g - gi
        bd = b - bi
        # Calculate colors each side of the nearest color.
        r1 = max(r - rd,0.0)
        g1 = max(g - gd,0.0)
        b1 = max(b - bd,0.0)
        r2 = min(r + rd,1.0)
        g2 = min(g + gd,1.0)
        b2 = min(b + bd,1.0)
        # Establish the TWO colors either side of the NEAREST color. When mixed is this closer to the original.
        #v1 = int(round(r1 * 5) * 6 * 6) + int(round(g1 * 5) * 6) + int(round(b1 * 5)) + 16
        #v2 = int(round(r2 * 5) * 6 * 6) + int(round(g2 * 5) * 6) + int(round(b2 * 5)) + 16
        v1 = textcolor.rgbdecimal(r1,g1,b1)
        v2 = textcolor.rgbdecimal(r2,g2,b2)
        return v1, v2
        
    @staticmethod
    def rgbpure(r,g,b):
        """ Take RGB values (scale 0-5) and calculate nearest XTERM 256 color scheme value. 
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        v = (r * 6 * 6) + (g * 6) + b + 16
        v = v % 256 # Clip for safety.
        return v

    @staticmethod
    def fgbgcolor(fg=7,bg=0,*args,sep=' ',reset=True):
        """ XTERM 256 color mode supported. 
            fg = foreground color (0-255)
            bg = background color (0-255)
            args = unlimited comma separated list of items to print.
            sep = ' ' separator placed between each argument when printed.
            if reset=True, the color is stopped at the end of the text. 
            if reset=False, the color setting remains active after the text. 
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        text = textcolor.listtotext(args,sep=sep)
        if textcolor.Mode == 'simple':
            return text
        else:
            if reset: 
                return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text + textcolor.reset() # Stop using this color after the text.
            else:
                return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text # Leave the color active.

    @staticmethod
    def xterm_to_rgb(n):
        """
        Convert an xterm 256 color code (0–255) to an (R, G, B) tuple.
        (Based upon AI suggested code)
        
        The 256 color table is split into 3 color ranges.
        16 standard terminal colors.
        216 r,g,b combinations.
        24 grayscale combinations.
        
            Parameters ---------------------------------------
            n (int) : XTERM color code.

            Returns ------------------------------------------
            (r,g,b) tuple of integers. """

        # --- 0–15: System colors (hard coded) ---
        system_colors = [
            (0, 0, 0),         # 0
            (128, 0, 0),       # 1
            (0, 128, 0),       # 2
            (128, 128, 0),     # 3
            (0, 0, 128),       # 4
            (128, 0, 128),     # 5
            (0, 128, 128),     # 6
            (192, 192, 192),   # 7
            (128, 128, 128),   # 8
            (255, 0, 0),       # 9
            (0, 255, 0),       # 10
            (255, 255, 0),     # 11
            (0, 0, 255),       # 12
            (255, 0, 255),     # 13
            (0, 255, 255),     # 14
            (255, 255, 255),   # 15
        ]

        if n < 16:
            return system_colors[n]

        # --- 16–231: 6×6×6 color cube ---
        if 16 <= n <= 231:
            n -= 16
            r = n // 36
            g = (n % 36) // 6
            b = n % 6

            # xterm uses this specific 6 level intensity table:
            levels = [0, 95, 135, 175, 215, 255]

            return (levels[r], levels[g], levels[b])

        # --- 232–255: Grayscale ramp ---
        if 232 <= n <= 255:
            level = 8 + (n - 232) * 10
            return (level, level, level)

        raise ValueError("textcolor.xterm_to_rgb(" + str(n) + "): Color index must be in range 0–255")

    @staticmethod
    def color_distance(c1, c2):
        """
        squared distance helper
        
        Parameters ---------------------------------------
            c1(list/tuple of 3 values):
            c2(list/tuple of 3 values):

            Returns ------------------------------------------
            measure of 'distance' between c1 and c2.
        """
        return (c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2

    @staticmethod
    def rgb_to_xterm(rgb):
        """
        Convert an (R, G, B) tuple (0-255 each) to the nearest xterm 256 color index (0-255).
        (Based upon AI suggested code)
        
        The 256 color table is split into 3 color ranges.
        16 standard terminal colors.
        216 r,g,b combinations.
        24 grayscale combinations.
        
            Parameters ---------------------------------------
            rgb (tuple) : (r,g,b) Channel values (0-255)

            Returns ------------------------------------------
            XTERM color (int) : 0 - 255 """

        # clamp inputs to valid range
        r = max(0, min(255, int(rgb[0])))
        g = max(0, min(255, int(rgb[1])))
        b = max(0, min(255, int(rgb[2])))

        # --- 0..15 system colors (xterm defaults) ---
        system_colors = [
            (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
            (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
            (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
        ]

        target = (r, g, b)

        # 1) Start by checking system colors
        best_index = 0
        best_dist = textcolor.color_distance(target, system_colors[0])
        for i, col in enumerate(system_colors):
            d = textcolor.color_distance(target, col)
            if d < best_dist:
                best_dist = d
                best_index = i

        # 2) Check 6x6x6 color cube (indices 16..231)
        levels = [0, 95, 135, 175, 215, 255]
        for ri in range(6):
            vr = levels[ri]
            for gi in range(6):
                vg = levels[gi]
                for bi in range(6):
                    vb = levels[bi]
                    idx = 16 + 36 * ri + 6 * gi + bi
                    d = textcolor.color_distance(target, (vr, vg, vb))
                    if d < best_dist:
                        best_dist = d
                        best_index = idx

        # 3) Check grayscale ramp (indices 232..255)
        for i in range(24):
            level = 8 + i * 10
            idx = 232 + i
            d = textcolor.color_distance(target, (level, level, level))
            if d < best_dist:
                best_dist = d
                best_index = idx

        return best_index

    @staticmethod
    def colortextline(entries,sep=" "):
        """
        Build a line of text with differing colors. 
        
            Parameters ---------------------------------------
            entries (list) : List of entries [(fg,bg,text),(fg,bg,text),...] 
            sep (str) : Separator to use between entries.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a 
            
            Returns ------------------------------------------
            string """
        result = ""
        for fg,bg,text in entries:
            if result != "": text = sep + text
            result += textcolor.fgbgcolor(fg,bg,text)
        return result
            
    @staticmethod
    def listcolors():
        """ Display matrix all colors available on terminal.
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a 
            
            Returns ------------------------------------------
            n/a """
        # First list on BLACK background.
        for i in range(0, 16):
            line = ""
            for j in range(0, 16):
                code = i * 16 + j
                line += textcolor.fgbgcolor(code, 0, str(code).rjust(4))
            print (line)
        # Second show BLACK characters on colored background.
        for i in range(0, 16):
            line = ""
            for j in range(0, 16):
                code = i * 16 + j
                line += textcolor.fgbgcolor(0,code, str(code).rjust(4))
            print (line)
        print (textcolor.reset())
        print (textcolor.black('Black'))
        print (textcolor.red('Red'))
        print (textcolor.green('Green'))
        print (textcolor.blue('Blue'))
        print (textcolor.yellow('Yellow'))
        print (textcolor.aqua('Aqua'))
        print (textcolor.white('White'))
        print (textcolor.magenta('Magenta'))
        print ("termtype",textcolor.GetTermType())

    @staticmethod
    def coloredlist(words,colors,sep=None,reverse=False):
        """ Return a colored string representing word list. 
            (Used for nesting labels etc)
            Level 1 / Level 2 / Level 3 / Level 4 
            
            Parameters --------------------------------------
            words (list of str) : Words to color code.
            colors (list of tuple) : FG,BG pairs to color the list with. 
            sep (str) : Optional. Separator characters to put between entries. Default is chr(0x25e4)
            reverse (bool) : Optional. When FALSE color list is used in sequence received.
                                       (If showing multiple lists, the colors match
                                        Good for listing file structures.)
                                       When TRUE color list is used in reverse sequence.
                                       (If highlighting menu location the last entry is always 1st color tuple.
                                        Good for navigating menus.)
            Result ------------------------------------------
            line (str) : color coded list """
        line = ""
        prev_bg = None
        # Make sure color list is as long as word list.
        while len(colors) < len(words): 
            colors += colors # Pad color list to match word list.
        colors = colors[:len(words)]
        # Decide how color list is applied.
        if reverse: colors.reverse() # Work backwards through the list of colors so that the latest item is always color 1 in the list.
        # Set default separator character.
        if sep == None: sep = chr(0x25e4) # Half triangle symbol
        # Construct colored list.
        if textcolor.Mode == 'simple': # Make simple uncolored list in this mode.
            for word in words:
                if line != "": line += sep # Add separator.
                line += " " + word + " " # Add text.
        else: # Use full color.
            for i,word in enumerate(words):
                fg = colors[i][0]
                bg = colors[i][1]
                if line != "": line += textcolor.fgbgcolor(prev_bg,bg,sep) # Add separator.
                line += textcolor.fgbgcolor(fg,bg," " + word + " ") # Add text.
                prev_bg = bg
        return line 

    @staticmethod
    def opposite(colnum,color=False):
        """ Return an opposing color to the proposed one. 

            *Q* Not finished yet.
            
            Parameters ---------------------------------------
            colnum : int (0 - 255) color to invert.
            color : bool : True return opposing color.
                           False return BLACK or WHITE

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        # *Q* Not finished yet.
        if colnum == textcolor.BLACK: oppcol = textcolor.WHITE
        else: oppcol = textcolor.BLACK
        return oppcol

    @staticmethod
    def black(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for BLACK on WHITE text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return BLACK on WHITE.
                            True : Return WHITE on BLACK.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.WHITE,textcolor.BLACK,text)
        else:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.WHITE,text)

    @staticmethod
    def red(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for RED on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return RED on BLACK.
                            True : Return BLACK on RED.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.RED,text)
        else:
            return textcolor.fgbgcolor(textcolor.RED,textcolor.BLACK,text)

    @staticmethod
    def green(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for GREEN on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return GREEN on BLACK.
                            True : Return BLACK on GREEN.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.GREEN,text)
        else:
            return textcolor.fgbgcolor(textcolor.GREEN,textcolor.BLACK,text)

    @staticmethod
    def yellow(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for YELLOW on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return YELLOW on BLACK.
                            True : Return BLACK on YELLOW.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.YELLOW,text)
        else:
            return textcolor.fgbgcolor(textcolor.YELLOW,textcolor.BLACK,text)

    @staticmethod
    def yellow4(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for YELLOW4 on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return YELLOW4 on BLACK.
                            True : Return BLACK on YELLOW4.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.YELLOW4,text)
        else:
            return textcolor.fgbgcolor(textcolor.YELLOW4,textcolor.BLACK,text)

    @staticmethod
    def orange(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for ORANGE1 on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return ORANGE1 on BLACK.
                            True : Return BLACK on ORANGE1.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.ORANGE1,text)
        else:
            return textcolor.fgbgcolor(textcolor.ORANGE1,textcolor.BLACK,text)

    @staticmethod
    def blue(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for BLUE on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return BLUE on BLACK.
                            True : Return BLACK on BLUE.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.BLUE,text)
        else:
            return textcolor.fgbgcolor(textcolor.BLUE,textcolor.BLACK,text)

    @staticmethod
    def magenta(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for MAGENTA on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return MAGENTA on BLACK.
                            True : Return BLACK on MAGENTA.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.MAGENTA,text)
        else:
            return textcolor.fgbgcolor(textcolor.MAGENTA,textcolor.BLACK,text)

    @staticmethod
    def cyan(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for CYAN on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return CYAN on BLACK.
                            True : Return BLACK on CYAN.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.CYAN,text)
        else:
            return textcolor.fgbgcolor(textcolor.CYAN,textcolor.BLACK,text)

    @staticmethod
    def aqua(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for AQUA on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return AQUA on BLACK.
                            True : Return BLACK on AQUA.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.AQUA,text)
        else:
            return textcolor.fgbgcolor(textcolor.AQUA,textcolor.BLACK,text)

    @staticmethod
    def navy(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for NAVY on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return NAVY on BLACK.
                            True : Return BLACK on NAVY.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.NAVY,text)
        else:
            return textcolor.fgbgcolor(textcolor.NAVY,textcolor.BLACK,text)

    @staticmethod
    def teal(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for TEAL on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return TEAL on BLACK.
                            True : Return BLACK on TEAL.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.TEAL,text)
        else:
            return textcolor.fgbgcolor(textcolor.TEAL,textcolor.BLACK,text)

    @staticmethod
    def white(*args,sep=' ',invert=False):
        """ Return all input values as space separated string.
            String includes terminal display codes for WHITE on BLACK text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.
            invert : bool : False : Return WHITE on BLACK.
                            True : Return BLACK on WHITE.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.WHITE,text)
        else:
            return textcolor.fgbgcolor(textcolor.WHITE,textcolor.BLACK,text)

    @staticmethod
    def bold(*args,sep=' '):
        """ Return all input values as space separated string.
            String includes terminal display codes for BOLD text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        return "\033[1m" + text + textcolor.reset()

    @staticmethod
    def underline(*args,sep=' '):
        """ Return all input values as space separated string.
            String includes terminal display codes for UNDERLINED text.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        return "\033[4m" + text + textcolor.reset()

    @staticmethod
    def blink(*args,sep=' '):
        """ Return all input values as space separated string.
            String includes terminal display codes for BLINKING text.
            Terminal must support this.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        return "\033[5m" + text + textcolor.reset()

    @staticmethod
    def framed(*args,sep=' '):
        """ Return all input values as space separated string.
            String is returned with frame around it.
            
            Parameters ---------------------------------------
            *args : any type : Elements to construct into string.
            sep : str : Separator character between each element.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string : Color coded compound string. """
        text = textcolor.listtotext(args,sep=sep)
        return "\033[51m" + text + textcolor.reset()

    @staticmethod
    def reversed(*args,sep=' '):
        """
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """        
        text = textcolor.listtotext(args)
        return "\033[7m" + text + textcolor.reset()

# ------------------------------------------------------------------------------------------------

class cdsprite():
    """ This is a subclass of the colordisplay class.
        It represents 'sprites' that can be defined to move across the colordisplay buffer. 
        Originally intended to create moving markers against a set background grid. """
        
    __version__ = '0.0.1'
        
    def __init__(self,name,symbol,row=None,col=None,fg=0,bg=15,level=0):
        """
            Parameters ---------------------------------------
            name : Identifying name of sprite.
            symbol : Which character to use for the sprite.
            row : Which row of the colordisplay window does it appear on?
            col : Which column of the colordisplay window does it appear on?
            fg : Foreground color (0-255) - optional.
            bg : Background color (0-255) - optional.
            level : Display sequence.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """        
        self.row = row
        self.column = col
        self.fg = fg
        self.bg = bg
        self.symbol = symbol
        self.name = name
        self.display = False
        self.level = level

    def ColoredSymbol(self):
        """ Return symbol with embedded terminal color codes set. 
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            Character surrounded by color codes. """
        result = result = textcolor.fgbgcolor(self.fg,self.bg,self.symbol)
        return result
        
    def Label(self,color=False):
        """ Return color coded label for the sprite. 
            Used in the key to a display.
            color=False means color is not set, plaintext is returned instead.         
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            string with symbol and name in sprite colors.          """        

        if color: result = textcolor.fgbgcolor(self.fg,self.bg,self.symbol)
        else: result = self.symbol
        result += ' = ' + self.name
        return result

# -------------------------------------------------------------------------------------------------------------------------------- 

class messagewindow():
    """ Class to create a simple scrolling text window and to display on the terminal as needed. 
        Superceded by colordisplay class now - which contains all same functionalities. """
    
    __version__ = '0.0.1'
    
    def __init__(self,rows,columns,row=None,col=None,fg=15,bg=0,title=None):
        """ Parameters ---------------------------------------
            rows : How many rows high is the window?
            columns : How many columns wide is the window? 
            row : Which TERMINAL row does the window start on?
            col : Which TERMINAL column does the window start on?
            fg : Default foreground color for all text.
            bg : Default background color for all text.
            title : An optional title to appear at the top of the window.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        print (textcolor.red('textcolor.messagewindow(): Deprecated in favour of textcolor.colordisplay().'))
        self.DisplayRows = rows # How many rows deep is the display?
        self.DisplayColumns = columns # How many columns wide is the display?
        self.DisplayRow = row # What's the location of the 1st cell in the display on the actual terminal?
        self.DisplayCol = col
        if row == None: # Location of the last row in the display.
            self.LastDisplayRow = None
        else:
            self.LastDisplayRow = row + rows - 1
        if col == None: # Location of the last column in the display.
            self.LastDisplayCol = None
        else:
            self.LastDisplayCol = col + columns - 1
        self.DefaultFG = fg # What's the default foreground color?
        self.DefaultBG = bg # What's the default background color?
        self.DefaultChar = ' '
        self.Lines = []
        self.Title = title # Is there a title to the window? (Will keep 1st row static)
        if self.Title != None:
            self.Lines.append(' ') # Occupy the first line of the display, because the title will overwrite it.
            if len(self.Title) > self.DisplayColumns: # Title cannot exceed window width.
                self.Title = self.Title[:self.DisplayColumns]
        self.Wrap = True # Long text will wrap onto multiple lines.
        self.Log = None # Can store handle to a 'Log' method for logging messages. Needs to be defined and assigned by the calling program.
        self.RefreshRate = None # Can specify how quickly the display refreshes (in seconds).
        self.LastRefresh = None # When did the display last update?

    def SetRefreshRate(self,rate):
        """ Set selected refresh rate and reset the refresh timer. 
            Parameters ---------------------------------------
            rate : How many second between display refreshes if terminal IO is being optimised.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        self.RefreshRate = rate
        self.LastRefresh = None
        
    def RefreshDue(self):
        """ Return True if refresh is due, else False.
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            refresh_due (boolean) """
        result = False
        if self.RefreshRate == None: result = True # There's no restriction so always refresh. 
        elif self.LastRefresh == None: result = True # Need to do initial drawing. 
        elif (datetime.now() - self.LastRefresh).total_seconds() >= self.RefreshRate: result = True # Refresh is due.
        return result 

    def Clear(self,immediate=False):
        """ Clear the window.             
            Parameters ---------------------------------------
            immediate : bool : When TRUE the window is cleared immediately.
                               When FALSE the window is cleared at next refresh.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        self.Lines = []
        if self.Title != None: self.Lines.append(' ')
        if immediate: self.Display()

    def Display(self,screenheight=None,screenwidth=None,immediate=False):
        """ Display the window.
            If specific location has been given for the window AND the current screen size is given in screenheight/screenwidth
            this can check that the space exists in the current display size. It will only draw the window if there is enough space.             
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if immediate == False and self.RefreshDue() == False: return # Don't perform a refresh yet.
        if self.LastDisplayRow != None and screenheight != None: # We have a specific location to use, check if that location is in the current display dimensions.
            if screenheight < self.LastDisplayRow: # Not enough height.
                return # Don't try to display.
        if self.LastDisplayCol != None and screenwidth != None:
            if screenwidth < self.LastDisplayCol: # Not enough width.
                return # Don't try to display.
        for r in range(self.DisplayRows):
            if len(self.Lines) >= r + 1:
                line = self.Lines[r]
            else:
                line = ' '
            if r == 0 and self.Title != None:
                line = self.Title # 1st row is always the 'title' if specified. 
                line = textcolor.fgbgcolor(self.DefaultBG,self.DefaultFG,line.ljust(self.DisplayColumns,' '))
            else:
                line = textcolor.fgbgcolor(self.DefaultFG,self.DefaultBG,line.ljust(self.DisplayColumns,' '))
            if self.DisplayRow != None and self.DisplayCol != None:
                # The display has a specific location on the terminal window. Place it there.
                dr = self.DisplayRow + r
                dc = self.DisplayCol
                line = textcolor.cursor(dc,dr) + line
            print(line)
        self.LastRefresh = datetime.now()

    def Print(self,*args,sep=' '):
        """ Parameters ---------------------------------------
            args : List of elements to print. Can be used like Python print() command to comma separate multiple items.
            sep : The separator to use when concatenating multiple args.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        line = ''
        for i in args:
            if len(line) > 0: line += sep
            line += str(i)
        if not self.Wrap: # Don't wrap text, just truncate if it is wider than display.
            line = line[:self.DisplayColumns] # Truncate the line.
        else: # Wrap long text onto multiple display lines.
            while len(line) > 0:
                self.Lines.append(line[:self.DisplayColumns])
                if len(line) > self.DisplayColumns:
                    line = line[self.DisplayColumns:] # Remainder of text not yet displayed.
                else:
                    line = '' # Nothing left to display.
        while len(self.Lines) > self.DisplayRows:
            # temp = self.Lines.pop(0)
            self.Lines.pop(0)

# -------------------------------------------------------------------------------------------------------------------------------- 

class bigletters():
    """ Primitive large font sizes. """
    def __init__(self):
        """ Create instance.
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        self.LetterDictionary = {}
        self.InitialiseLD()
        
    def InitialiseLD(self):
        """ Initialize the dictionary with supported characters. 
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        self.LetterDictionary = {}
        self.LetterDictionary['unknown'] = ["#####","# # #","## ##","# # #","#####"]
        self.LetterDictionary[' '] =       ["     ","     ","     ","     ","     "]
        self.LetterDictionary['"'] =       [" # # "," # # ","     ","     ","     "]
        self.LetterDictionary["'"] =       ["  #  ","  #  ","     ","     ","     "]
        self.LetterDictionary['0'] =       ["#####","#  ##","# # #","##  #","#####"]
        self.LetterDictionary['1'] =       ["   # ","  ## ","   # ","   # "," ####"]                                      
        self.LetterDictionary['2'] =       ["#####","    #","#####","#    ","#####"]                                      
        self.LetterDictionary['3'] =       ["#####","    #","#####","    #","#####"]                                      
        self.LetterDictionary['4'] =       ["#   #","#   #","#####","    #","    #"]                                      
        self.LetterDictionary['5'] =       ["#####","#    ","#####","    #","#####"]                                      
        self.LetterDictionary['6'] =       ["#####","#    ","#####","#   #","#####"]                                      
        self.LetterDictionary['7'] =       ["#####","    #","    #","    #","    #"]                                      
        self.LetterDictionary['8'] =       ["#####","#   #","#####","#   #","#####"]                                      
        self.LetterDictionary['9'] =       ["#####","#   #","#####","    #","    #"]                                      
        self.LetterDictionary['.'] =       ["     ","     ","     ","     ","  #  "]                                      
        self.LetterDictionary[','] =       ["     ","     ","     ","  ## ","   # "]                                      
        self.LetterDictionary[':'] =       ["     ","  #  ","     ","  #  ","     "]                                      
        self.LetterDictionary['!'] =       ["  #  ","  #  ","  #  ","     ","  #  "]                                      
        self.LetterDictionary['-'] =       ["     ","     "," ### ","     ","     "]                                      
        self.LetterDictionary['+'] =       ["     ","  #  "," ### ","  #  ","     "]                                      
        self.LetterDictionary['*'] =       ["  #  ","# # #"," ### "," # # ","#   #"]                                      
        self.LetterDictionary['='] =       ["     "," ### ","     "," ### ","     "]                                      
        self.LetterDictionary['?'] =       [" ### ","#   #","  ## ","     ","  #  "]                                      

    def GetLetter(self,letter):
        """ Return letter pattern.             
        
            Parameters ---------------------------------------
            letter : The character to return.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            list of character elements.           """
        if letter in self.LetterDictionary: return self.LetterDictionary[letter]
        else: return self.LetterDictionary['unkown']
        
    def GenerateText(self,originaltext):
        """ Given original text, generate the BigLetters version of it.             
        
            Parameters ---------------------------------------
            originaltext : The string to convert.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            List of strings to display each row of the large format letters. """
        lines = [[] for i in range(5)] # Create 5 empty lines.
        for character in originaltext:
            LD = self.GetLetter(character) # Returns 5 character lines.
            for i,LL in enumerate(LD): # Parse each line in turn.
                lines[i].append(LL + ' ')
        return lines

# -------------------------------------------------------------------------------------------------------------------------------- 

class field():
    """ A data field in a colordisplay window.

        Field can be regular data fields or progress bars.

        This lets you define form layouts in a colordisplay window easily in the source code.
        You can define where data fields appear in the display and then update them directly as needed. """
    
    __version__ = '0.0.2'
    
    def __init__(self,name,row,col,length=10,justify='l',animations=[]):
        """ justify = 'l' left, 'r' right.             
            
            Parameters ---------------------------------------
            name : The name of the field (used to update the contents).
            row : The row where the field starts in the colordisplay window.
            col : The column where the field starts in the colordisplay window.
            length : The length of the field. 
            justify : Is the content justified left,right or centre.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        # Common attributes
        self.Name = name
        self.Row = row
        self.Column = col
        self.Length = length
        self.Value = None
        self.Justify = justify # 'left','centre','right'
        self.Animations = animations # List of required animations.
        self.Type = 'Data' # 'Data' field or 'ProgressBar'
        self.FGColor = None # Current color if it differs from the display defaults.
        self.BGColor = None
        # Progress bar specific attributes.
        self.PBMin = None # Minimum value of a progress bar field.
        self.PBMax = None # Maximum value of a progress bar field.
        self.PBFG = textcolor.GREEN # 'done' color of bar.
        self.PBBG = textcolor.YELLOW # 'todo' color of bar.
        # Colors used for ranges of values.
        self.BadFG = None # LOWLOW and HIGHHIGH values use these colors
        self.BadBG = None # LOWLOW and HIGHHIGH values use these colors
        self.PoorFG = None # LOW and HIGH values use these colors
        self.PoorBG = None # LOW and HIGH values use these colors
        # Special effects.
        self.BlinkRate = 0 # Seconds between changing FG/BG colors when blinking. 0 = No blink.
        self.BlinkColors = [[textcolor.WHITE,textcolor.BLACK],
                            [textcolor.RED,textcolor.BLACK]] # FG/BG pairs to alternate between when blinking.
        self.PulseIndex = None # No color pulse animation active.
        self.PulseColors = [[textcolor.BLACK,textcolor.WHITE],
                            [textcolor.BLACK,textcolor.GREY82],
                            [textcolor.BLACK,textcolor.GREY62],
                            [textcolor.BLACK,textcolor.GREY42],
                            [textcolor.WHITE,textcolor.GREY23],
                            [textcolor.WHITE,textcolor.GREY7]]

    def Justified(self):
        """ Return a formatted and justified string for the content of the field.
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            Formatted and justified string representing self.Value """
        sval = str(self.Value) # Convert to string.
        jcode = self.Justify[0].lower()
        if len(sval) < self.Length: # Does the field need padding?
            if jcode == 'r': sval = sval.strip().rjust(self.Length)
            elif jcode == 'c': sval = sval.strip().center(self.Length)
            else: sval = sval.strip().ljust(self.Length)
        return sval

# -------------------------------------------------------------------------------------------------------------------------------- 

class colordisplay():
    """ Class to create a colored character display buffer, and to display on the terminal as needed.
    
        Offers three basic modes of operation:
        1) Operate as addressible screen space
        2) Operate as simple scrolling text windows
        3) Operate as a form with defined data fields
        
        Supports sprites. """
    
    __version__ = '0.0.6'
    DefinedWindows = [] # Handles of all defined windows. Useful for scanning/updating all available windows.
                        # The defining class contains some methods which can perform general updates via this list.
    CDLayout = [] # Array of major rows/columns that colordisplay instances can self-align with.
                  # Each entry defines a high level 'column' of colordisplay locations. [[fromcol,colwidth],[fromcol,colwidth],...]
                  # When defining new colordisplay instances you can then just refer to these columns rather than tailoring the coordinates of each individual window.
    BRAILLE_MAP = {
        (0, 0): 0,
        (0, 1): 1,
        (0, 2): 2,
        (0, 3): 6,
        (1, 0): 3,
        (1, 1): 4,
        (1, 2): 5,
        (1, 3): 7,
    } # Pixel bit pattern for Braille character set plotting.
                  

    @staticmethod
    def AddCDEntry(colwidth,startcol=None):
        """ Add new entry to the colordisplay.CDLayout list.
            You must assign colwidth, but startcol is optional.
            If startcol is not specified, the next available one is assigned. 
            
            CDLayout is a list of display columns that individual colordisplay instances can be placed in. 
            This is used to simplify the creation of multi-panel displays. 
            This lets you split the terminal window into vertical groups.
            You can then simply append a colordisplay instance to one of these vertical groups
            it will then be automatically placed in the terminal window.

            from textcolor import colordisplay            
            colordisplay.AddCDEntry(colwidth=87,startcol=1) # Create left hand column 87 characters wide starting in 1st terminal column.
            colordisplay.AddCDEntry(colwidth=80,startcol=None) # Create a 2nd column 80 characters wide, will be automatically next to the 1st column.
            colordisplay.AddCDEntry(colwidth=55,startcol=None) # Create a 3rd column 55 characters wide, will be automatically next to the 2nd column.
            
            Parameters ---------------------------------------
            colwidth : The width of the display column that colordisplay windows can be placed in.
            startcol : The start column of the display column that the colordisplay windows can be placed in.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if startcol == None: # Starting column isn't specified, so calculate the next available one.
            startcol = 1 # Find the next free one. 1st column if nothing exists yet.
            for cd in colordisplay.CDLayout: # Check each layout already defined.
                temp = cd[0] + cd[1]
                if temp >= startcol: startcol = temp + 1 # Start at next free column (with 1 space for border).
        startcol = max(startcol,1) # Must be at least 1 (1st column)
        colordisplay.CDLayout.append([startcol,colwidth])
        return True
    
    def __init__(self,rows,columns=None,name='',row=None,col=None,fg=15,bg=0,FirstScrollRow=0,title=None,rjtitle=None,titlefg=None,titlebg=None,borderfg=None,borderbg=None,cdlayout=None):
        """ fg and bg parameters can be single integer value (0-255) or a list of values [(0-255),(0-255),..] 
            The Print() method will cycle through the colors if lists are given. 
            Other modes operate with just the first given fg and bg values, the rest of any lists are ignored. 

            After instantiation, you can also set self.ClipWindow = True to allow the window to truncate display if insufficient realestate available.
               Otherwise the entire window will be suppressed until the display is big enough to accomodate the entire window.                         
               
               
            Parameters ---------------------------------------
            rows = Number of ROWS in the window.
            columns = Number of COLUMNS in the window.
            row = Display ROW number where window starts.
            col = Display COLUMN number where window starts.
            fg = Foreground. Single color code (0-255) or list of values to cycle through.
            bg = Background. Single color code (0-255) of list of values to cycle through.
            FirstScrollRow = When printing to window, this is the first row that will scroll up as new lines are printed. (allows titles to stay fixed etc)
            title = Window title.
            rjtitle = Extra text for window title that will be right justified. It overwrites basic window title.
            titlefg = Title foreground. Single color code (0-255). None will use window bg value.
            titlebg = Title background. Single color code (0-255). None will use window fg value. 
            cdlayout = index of the colordisplay.CDLayout list. A shortcut to set col and or row values more dynamically.
            
            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        self.DisplayName = name # A label for the display instance.
        if columns == None and cdlayout == None:
            raise Exception("colordisplay.__init__(): You must specify columns or cdlayout parameter to define a window.")
        if self.DisplayName == '':
            self.DisplayName = "win_" + str(len(colordisplay.DefinedWindows)) # Generate a default name.
        self.DisplayRows = rows # How many rows deep is the display? # *Q* Rename to WindowColumns and WindowRows for clarity?
        self.CDEntry = cdlayout # If using predefined columns, make a note which one we're using.
        if self.CDEntry != None and self.CDEntry >= 0 and self.CDEntry < len(colordisplay.CDLayout): # Automatically assign location on the screen.
            # Use the CDLayout list of window columns to define the start column.
            col = colordisplay.CDLayout[self.CDEntry][0] # Pull the start character column from the CDLayout list.
            columns = colordisplay.CDLayout[self.CDEntry][1] # Pull the character column width from the CDLayout list.
            row = 1
            for cd in colordisplay.DefinedWindows: # Stack each new window beneath previous ones in a column.
                if cd.CDEntry == self.CDEntry and cd.LastDisplayRow >= row: row = cd.LastDisplayRow + 2 # Start at next free row (with 1 row for border).
        self.DisplayColumns = columns # How many columns wide is the display? # *Q* Rename to WindowColumns and WindowRows for clarity?
        self.DisplayRow = row # What's the location of the 1st cell in the display on the actual terminal?
        self.DisplayCol = col
        if self.DisplayRow != None and self.DisplayRows != None:
            self.LastDisplayRow = self.DisplayRow + self.DisplayRows - 1 # Where does the display END ?  
        else:
            self.LastDisplayRow = None
        if self.DisplayCol != None and self.DisplayColumns != None:
            self.LastDisplayCol = self.DisplayCol + self.DisplayColumns
        else:
            self.LastDisplayCol = None
        if type(fg) == list: # For scrolling displays you can provide a list of alternating text colors to use. This visually separates individual entries.
            self.DefaultFG = fg[0] # What's the default foreground color?
            self.DefaultFGs = fg
        else:
            self.DefaultFG = fg # What's the default foreground color?
            self.DefaultFGs = [fg]
        self.FGColorCount = len(self.DefaultFGs) # How many colors are available?
        self.FGColorIndex = 0 # Which color do we start with if multiple available?
        if type(bg) == list: # For scrolling displays you can provide a list of alternating background colors to use. This visually separates individual entries.
            self.DefaultBG = bg[0] # What's the default background color?
            self.DefaultBGs = bg # List of all background colors.
        else:
            self.DefaultBG = bg # What's the default background color?
            self.DefaultBGs = [bg] # List of all background colors.
        self.BGColorCount = len(self.DefaultBGs) # How many colors are available?
        self.BGColorIndex = 0 # Which color do we start with if multiple available?
        self.TitleFG = titlefg # What color is the title row?
        if self.TitleFG == None: self.TitleFG = self.DefaultBG # Default to inverse.
        self.TitleBG = titlebg # What color is the title row?
        if self.TitleBG == None: self.TitleBG = self.DefaultFG # Default to inverse.
        self.BorderFG = borderfg # What color is the border?
        if self.BorderFG == None: self.BorderFG = self.DefaultFG # Default is same as general window.
        self.BorderBG = borderbg # What color is the border.
        if self.BorderBG == None: self.BorderBG = self.DefaultBG # Default is same as general window.
        # Create array of each cell in the window, we need character, foreground color and background color.
        self.fgcolor = [[self.DefaultFG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Foreground color of each character.
        self.bgcolor = [[self.DefaultBG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Background color of each character.
        self.character = [[" " for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Characters to display.
        # Store the default state of the window here. This is used if the window is 'cleared'.
        self.default_fgcolor = [[self.DefaultFG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Foreground color of each character.
        self.default_bgcolor = [[self.DefaultBG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Background color of each character.
        self.default_character = [[" " for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Characters to display.
        self.PrevLineStrings = [None for r in range(self.DisplayRows)] # List of the display commands last issued to paint the display. Used to check for changes.
        self.ReduceIO = False # If set to true, Display() method will only update lines of the display that it thinks have changed.
        self.sprites = [] # List of any active sprites in the display.
        self.PrintHistory = [] # Cache of recently printed lines, used for repainting and exporting.
        self.FirstScrollRow = FirstScrollRow # 0 means data starts at the first row of the window, 1 means there's a title or something in row 0, etc. Scrolling takes this into account.
        self.Log = None # Can store handle to a 'Log' method for logging messages. Needs to be defined and assigned by the calling program.
        self.RefreshRate = None # Can specify how quickly the display refreshes (in seconds).
        self.LastRefresh = None # When did the display last update?
        self.Fields = [] # List of fields if defined.
        self.AnimatedFields = [] # List of fields which require some form of animation. *Q* Under development.
        self.MarkDisplay = False # If TRUE the corners are highlighted in RED, and the FIELDS are highlighted in YELLOW(for layout checking)
        if title != None: self.WindowTitle = ' ' + title.strip()
        else: self.WindowTitle = None
        if rjtitle != None: self.RJTitle = rjtitle.strip() + ' ' # A secondary title that is right justified on top of the title line.
        else: self.RJTitle = None
        if self.WindowTitle != None: self.SetTitle()
        self.ClipWindow = False # If TRUE, the window can be clipped to fit available terminal display. This will simply truncate.
        self.DrawBorder = False # If TRUE, an additional single line border is drawn on the RIGHT and BOTTOM of the window. Takes 1 extra character in each dimension.
        self.BorderFG = self.DefaultFG
        self.BorderBG = self.DefaultBG
        colordisplay.DefinedWindows.append(self) # Add this window to the global list of all windows.

    def __del__(self):
        """ Remove this window from the list of defined windows.
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            colordisplay.DefinedWindows

            Returns ------------------------------------------
            n/a          """
        for i,w in enumerate(colordisplay.DefinedWindows):
            if w == self: # Found myself in the list. Remove and quit.
                del colordisplay.DefinedWindows[i]
                break

    def SetTitle(self):
        """ Turn first row of a window into a title row.
            Color appropriately and change the scroll behaviour of the window.
            1st line nolonger scrolls.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            self.WindowTitle
            self.RJTitle

            Sets ---------------------------------------------
            self.FirstScrollRow
            self.character array
            self.fgcolor
            self.bgcolor

            Returns ------------------------------------------
            n/a          """
        if self.WindowTitle == None: # Deactivate the title line.
            self.FirstScrollRow = 0
            for c in range(self.DisplayColumns):
                self.fgcolor[0][c] = self.DefaultFG # Regular colors if no title.
                self.bgcolor[0][c] = self.DefaultBG # Regular colors if no title.
        else: # Activate the title line.
            self.FirstScrollRow = 1
            temp = (self.WindowTitle + (' ' * self.DisplayColumns))[:self.DisplayColumns] # Pad out to full window width.
            for c in range(self.DisplayColumns):
                self.character[0][c] = temp[c] # Add title to window display top line.
                self.fgcolor[0][c] = self.TitleFG # Invert colors for titles.
                self.bgcolor[0][c] = self.TitleBG # Invert colors for titles.
            if self.RJTitle != None: # There is a right justified element to the title to add.
                sc = self.DisplayColumns - len(self.RJTitle)
                for i in range(len(self.RJTitle)): # Work backwards because we are right justifying this on top of existing title.
                    c = sc + i # Where does the character go?
                    self.character[0][c] = self.RJTitle[i]

    def ReadTitleRow(self):
        """ Read the title row directly from the buffer.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            self.character array

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            string containing current title row content. """
        line = ''
        for c in range(self.DisplayColumns):
            line += self.character[0][c]
        return line

    def AddField(self,name,row,column,length=10,justify='l'):
        """ Add a field to the list of fields recognised in this window. 
            Duplicates are allowed, they all get updated if referenced.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.Fields list.

            Returns ------------------------------------------
            success (boolean)          """
        self.Fields.append(field(name=name,row=row,col=column,length=length,justify=justify))
        return True

    def InitializeProgressBar(self,name,minval,maxval,fg=None,bg=None):
        """ Define a field as a progress bar.                         
        
            Parameters ---------------------------------------
            name : The fieldname to convert.
            minval : Lowest value to represent.
            maxval : Highest value to represent.
            fg : FG color for progress bar (% DONE)
            bg : BG color for progress bar (% TODO)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.Fields members

            Returns ------------------------------------------
            success (boolean) """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will initialize multiple fields with same name.
                FoundIt = True
                f.PBMin = minval
                f.PBMax = maxval
                f.Type = 'ProgressBar'
                if fg != None: f.PBFG = fg # Set the 'DONE' color
                if bg != None: f.PBBG = bg # Set the 'TODO' color
        return FoundIt
    
    def ScanForFields(self,startchar='[',endchar=']'):
        """ Scan the current display looking for fields.
            Fields are marked by '[name    ]' strings.
            If no name, then a sequence number is assigned as a name. 
            '[]' would represent a 2 character field (assigned a sequence number name automatically). 
            ']' would represent a 1 character field (assigned a sequence number name automatically).
            Set the 'default' display before calling this. 
            Start and End field characters are '[' and ']' by default, but you can change 'em if needed
            via the startchar and endchar parameters.                         
            
            Parameters ---------------------------------------
            startchar : str : Optional character that represents the START of a datafield. Default "["
            endchar : str : Optional character that represents the END of a datafield. Default "]"

            References ---------------------------------------
            self.character array.

            Sets ---------------------------------------------
            self.Fields array.

            Returns ------------------------------------------
            success (boolean)          """
        startchar = (startchar.strip() + '[')[0] # 1 character only, and failsafe to the default char.
        endchar = (endchar.strip() + ']')[0] # 1 character only, and failsafe to the default char.
        nextid = 0 # Default ID for fields with no name.
        for r in range(self.DisplayRows): # Process each display row individually.
            start = None # Fields cannot span multiple lines.
            name = ''
            for c in range(self.DisplayColumns): # Scan across the characters of the line.
                if self.character[r][c] == endchar and start != None: # End of field marker, and there was a start marker!
                    nextid += 1
                    if name == '': # No name yet. Assign default.
                        name = str(nextid)
                    self.AddField(name=name,row=r,column=start,length=(c - start) + 1)
                    start = None # Clear the 'working' field name values ready for next field we find.
                    name = ''
                if self.character[r][c] == startchar: # Start of field marker.
                    start = c
                if start != None: # We're in a field.
                    if not self.character[r][c] in [startchar,endchar,' ']:
                        name += self.character[r][c] # Add to name.
        return True

    def GetFloatValue(self,inval):
        """ Convert an inval value into a float.
            Removing special characters such as "%","C" etc.                         
            
            Parameters ---------------------------------------
            inval

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            result (float) """
        allowedchars = ['0','1','2','3','4','5','6','7','8','9','.']
        sinp = str(inval) # Make sure it's a string.
        cinp = '' # Cleaned input.
        for s in sinp:
            if s in allowedchars: cinp += s
        finp = float(cinp)
        return finp

    def ExportFields(self,filename,initialdictionary={}):
        """ Export field values to json file.
            Data is appended to any values already existing in initialdictionary.                         
            
            Parameters ---------------------------------------
            filename : str : The filename to generate.
            initialdictionary : The dictionary that is exported, usually empty, but can contain preexisting data if needed.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Creates named file on disc as json file.
                         {"DisplayName.FieldName":{'value':value,'type':'str'},
                          "DisplayName.FieldName":{'value':value,'type':'str'}, 
                          ...
                          "DisplayName.PrintHistory":[line0, line1, line2, line3 ...}

            Returns ------------------------------------------
            success (Boolean)          """
        tempdict = {}
        if len(initialdictionary) > 0: # Transfer entries from initial dictionary into output dictionary first.
            for key,value in initialdictionary.items():
                tempdict[key] = value
        for field in self.Fields: # Dump any display fields.
            tempdict[self.DisplayName + "." + field.Name] = {"value":field.Value,"type":str(type(field.Value))}
        tempdict[self.DisplayName + '.PrintHistory'] = self.PrintHistory # Also dump the scrolling print history of the window.
        with open(filename,'w') as f:
            json.dump(tempdict,f)
        return True

    def ImportFields(self,dictionary):
        """ Import field values from a dictionary file.
            
            Parameters ---------------------------------------
            dictionary : The dictionary that is imported.
                         Dictionary must match the export format from ExportFields() method.
                         {"DisplayName.FieldName":{'value':value,'type':'str'},
                          "DisplayName.FieldName":{'value':value,'type':'str'}, 
                          ...
                          "DisplayName.PrintHistory":[line0, line1, line2, line3 ...}

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (Boolean)          """
        for key,entry in dictionary.items():
            fieldname = key.split('.')[-1] # Extract fieldname from "DisplayName.FieldName" formatted key.
            if fieldname == 'PrintHistory': self.PrintHistory = entry
            elif type(entry) == dict:
                if 'value' in entry: self.FieldValue(fieldname,entry['value'])
        return True

    def UpdateBlinkStatus(self):
        """ Check for any fields with 'BlinkRate' set. 
            Adjust colors accordingly.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            self.Fields members.

            Sets ---------------------------------------------
            self.Fields members.

            Returns ------------------------------------------
            n/a          """
        for f in self.Fields:
            if f.BlinkRate != 0: # This field is in BLINK mode.
                # Choose an appropriate color scheme.
                t = datetime.now().timestamp() # Current time as seconds.
                c = round(t / f.BlinkRate,0) % len(self.BlinkColors) # Cycle through the list of BlinkColor pairs.
                self.FieldValue(f.name,fg=self.BlinkColors[c][0],bg=self.BlinkColors[c][1])
        return True

    def SetBlinkStatus(self,name,blinkrate,blinkcolors=[[textcolor.WHITE,textcolor.BLACK],[textcolor.BLACK,textcolor.WHITE]]):
        """ Setup blink data.
                                            
            Parameters ---------------------------------------
            name : str : Name of field(s)
            blinkrate : str : How many seconds before color change.
            blinkcolors : list : Color pairs used for color changes.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.Fields members.

            Returns ------------------------------------------
            n/a          """
        # Validate the color list.
        lOK = True
        for a in blinkcolors:
            if len(a) != 2: # Must be 2 colors listed in each entry.
                lOK = False
                break
        if lOK: 
            for f in self.Fields:
                if f.Name == name:
                    f.BlinkRate = blinkrate
                    f.BlinkColors = blinkcolors

    def DisplayAnimation(self): # Run through any animations required for data fields.
        """
        Run through any animations required for data fields.
        """
        for f in self.Fields:
            if f.PulseIndex != None: # Pulse the colors.
                if f.PulseIndex >= len(f.PulseColors): f.PulseIndex = None # Finished return to main colors.
                fg = f.FGColor # Tell the field what color it is.
                if fg == None: fg = self.DefaultFG
                bg = f.BGColor # Tell the field what color it is.
                if bg == None: bg = self.DefaultBG
                if f.PulseIndex != None: # Override with current pulse color. For fields that briefly pulse when the value changes.
                    fg = f.PulseColors[f.PulseIndex][0]
                    bg = f.PulseColors[f.PulseIndex][1]
                    f.PulseIndex += 1 # Advance to next color pair. When off the end of the list this triggers the normal colors to be returned.
                sValue = f.Justified() # Make sure the value is a character string and correctly formatted.
                for i in range(f.Length): # Set the characters one at a time.
                    self.character[f.Row][f.Column + i] = sValue[i]
                    if fg != None: self.fgcolor[f.Row][f.Column + i] = fg
                    if bg != None: self.bgcolor[f.Row][f.Column + i] = bg

    def ValidateAnimations(self,animations):
        """
        Report if any animation codes are unacceptable.
        """
        result = True
        for a in animations:
            if not a in ['pulse']: 
                result = False
                print("textcolor.colordisplay(",self.Name,"): Animation code '" + str(a) + "' is not recognised.")
        return result 
        
    def FieldAnimations(self,name,animations):
        """
        Set new list of animations for a field.        
        """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                f.Animations = animations
        return FoundIt

    def AddFieldAnimation(self,name,animation):
        """
        Add new animation command to a field.
        """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                for a in animation: 
                    if not a in f.Animations: f.Animations.append(a)
        return FoundIt
        
    def DelFieldAnimation(self,name,animation):
        """
        Remove existing animation command from a field.
        """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                if a in f.Animations: f.Animations.remove(a)
        return FoundIt
        
    def FieldValue(self,name,value,fg=None,bg=None,animations=None):
        """ Update the value of a field and display it.                         
        
            Parameters ---------------------------------------
            name : str : Field name(s) to update.
            value : (any) : The value to be shown in the field (will be formatted here)
            fg : int : Foreground color for the field (optional)
            bg : int : Background color for the field (optional)
            animations : list of str : Optional list of animations to apply.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.Fields members
            self.character 
            self.fgcolor
            self.bgcolor 

            Returns ------------------------------------------
            success (boolean)         """
        FoundIt = False
        if animations != None: self.FieldAnimations(name,animations=animations)
        for f in self.Fields:
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                prev_value = f.Value
                f.Value = value
                if fg != None: f.FGColor = fg # Tell the field what color it is.
                if bg != None: f.BGColor = bg # Tell the field what color it is.
                sValue = f.Justified() # Make sure the value is a character string and correctly formatted.
                if f.Type == "ProgressBar":
                    pval = float(max(min(self.GetFloatValue(value),f.PBMax),f.PBMin)) # Limit value to progress bar limits.
                    if fg == None: fg = f.PBFG # Default to predefined progress bar colors.
                    if bg == None: bg = f.PBBG
                    pc = round(f.Length * (pval - f.PBMin) / (f.PBMax - f.PBMin)) - 1 # Calculate % complete (offset by -1 to allow for Python 'range' function)
                    for i in range(f.Length):
                        if i <= pc: # 'completed' section of progress bar.
                            self.fgcolor[f.Row][f.Column + i] = fg
                            self.bgcolor[f.Row][f.Column + i] = bg
                        else: # 'todo' section of progress bar (colors swapped).
                            self.fgcolor[f.Row][f.Column + i] = bg
                            self.bgcolor[f.Row][f.Column + i] = fg
                        self.character[f.Row][f.Column + i] = sValue[i]
                else: # 'Data' field.
                    if 'pulse' in f.Animations and prev_value != value: # Field requires animation
                        f.PulseIndex = 0 # Set up to pulse as the field actually updates.
                    for i in range(f.Length): # Set the characters one at a time.
                        self.character[f.Row][f.Column + i] = sValue[i]
                        if fg != None: self.fgcolor[f.Row][f.Column + i] = fg
                        if bg != None: self.bgcolor[f.Row][f.Column + i] = bg
        return FoundIt

    def RenameField(self,oldname,newname):
        """ Change the name of a data field to something more useful.     
            If the field is small it may only have a short name, you can change it 
            to something more meaningful here.            
        
            Parameters ---------------------------------------
            oldname : str : Existing name of field(s)
            newname : str : New name of field(s)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (boolean)          """
        FoundIt = False
        for f in self.Fields: # Check all fields. 
            if f.Name == oldname: # Found original fieldname.
                FoundIt = True
                f.Name = newname # Assign new fieldname. 
        return FoundIt

    def FieldFormat(self,name, justify=None, pattern=None, bwz=None):
        """ Change the format of a data field to something more useful.                         
        
            Parameters ---------------------------------------
            name : str : Name of the field(s)
            justify : str : Field justification to apply ('left','right','centre')
            pattern : str : Display pattern to apply to value (*Q* NOT YET IMPLEMENTED)
            bwz : boolean : When TRUE ZERO values will leave the field BLANK.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (boolean)          """
        FoundIt = False
        if pattern != None: 
            print("textcolor.colordisplay.FieldFormat: pattern argument not yet implemented. Ignored.")
        if bwz != None: 
            print("textcolor.colordisplay.FieldFormat: bwz argument not yet implemented. Ignored.")
        for f in self.Fields: # Check all fields. 
            if f.Name == name: # Found original fieldname.
                FoundIt = True
                if justify != None: f.Justify = justify
        return FoundIt

    def CopyFieldColor(self,fromname,toname):
        """ Copy color of one field to another.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (boolean)          """
        FoundIt = False
        fromfield = None # Handle to the FROM instance.
        tofield = None # Handle to the TO instance.
        for f in self.Fields: # Find the source field.
            if f.Name == fromname: # Found the FROM instance.
                fromfield = f
                break
        for g in self.Fields: # Find the target field.
            if g.Name == toname: # Found the TO instance.
                tofield = g
                break
        if fromfield != None and tofield != None: # Transfer the colors.
            FoundIt = self.FieldColor(toname,fg=f.FGColor,bg=f.BGColor)
        return FoundIt

    def FieldColor(self,name, fg=None, bg=None):
        """ Update the color of a field and display it.                         
        
            Parameters ---------------------------------------
            name : str : Fieldname to update.
            fg : int : 0-255 foreground color to apply to field(s).
            bg : int : 0-255 background color to apply to field(s).

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (boolean)          """
        FoundIt = False
        if fg == None: fg = self.DefaultFG # Set defaults if no value given.
        if bg == None: bg = self.DefaultBG
        for f in self.Fields: # Find the field(s) by name.
            if f.Type in ['ProgressBar']: continue # ProgressBars select their color differently.
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
                if fg != None: f.FGColor = fg # Tell the field what color it is.
                if bg != None: f.BGColor = bg # Tell the field what color it is.
                for i in range(f.Length): # Color every character in the field.
                    self.fgcolor[f.Row][f.Column + i] = fg
                    self.bgcolor[f.Row][f.Column + i] = bg
                f.FGColor = fg
                f.BGColor = bg
        return FoundIt

    def InitializeColorRange(self,name,badfg=None,badbg=None,poorfg=None,poorbg=None):
        """ Set color range for a field. A field can have a range of colors assigned to it
            which are to be used in certain cases.
            The colors are actually assigned to the field via that RangeFieldColor() method.            
        
            Parameters ---------------------------------------
            name : str : Field name to update.
            badfg : int : 0-255 Foreground color to be used for 'BAD' values (ie in ERROR state)
            badbg : int : 0-255 Background color to be used for 'BAD' values (ie in ERROR state)
            poorfg : int : 0-255 Foreground color to be used for 'POOR' values (ie in WARNING state)
            poorbg : int : 0-255 Background color to be used for 'POOR' values (ie in WARNING state)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (boolean)          """
        FoundIt = False # Not found the field yet.
        for f in self.Fields: # Search the field list.
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True # Found the field.
                f.BadFG = badfg # Set the color values for each range.
                f.BadBG = badbg
                f.PoorFG = poorfg
                f.PoorBG = poorbg
        return FoundIt
        
    def RangeFieldColor(self,name,lowlow=None,low=None,high=None,highhigh=None):
        """ Update the color of a field based upon a range of values.    
            The colors are defined using the InitializeColorRange() method.        
        
            Parameters ---------------------------------------
            name : str : Name of the field(s) to update.
            lowlow : float : Any value BELOW this is considered a BAD value.
            low : float : Any value BELOW this is considered a POOR value.
            high : float : Any value ABOVE this is considered a POOR value.
            highhigh : float : Any value ABOVE this is considered a BAD value.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (boolean)          """
        FoundIt = False # Not found the field yet.
        for f in self.Fields: # Find the field in the field list.
            if f.Type in ['ProgressBar']: continue # ProgressBars select their color differently.
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True # Found the field.
                if f.Value <= lowlow or f.Value >= highhigh: # We have a LOW LOW or HIGH HIGH value, this is BAD.
                    fg = f.BadFG
                    bg = f.BadBG
                elif f.Value <= low or f.Value >= high: # We have a LOW or HIGH value, this is POOR.
                    fg = f.PoorFG
                    bg = f.PoorBG
                else: # We have a GOOD value.
                    fg = self.DefaultFG
                    bg = self.DefaultBG
                self.FieldColor(name,fg=fg,bg=bg)
        return FoundIt

    def ListFields(self):
        """ Return dictionary of fields recognised in the window.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            dictionary (dict) """
        dict = {}
        for f in self.Fields:
            dict[f.Name] = {'row': f.Row, 'col': f.Column, 'len': f.Length, 'just': f.Justify, 'type': f.Type}
        return dict

    def SetRefreshRate(self,rate):
        """ Set selected refresh rate and reset the refresh timer.                         
        
            Parameters ---------------------------------------
            rate : float : How many seconds between forced refresh of entire display.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        self.RefreshRate = rate
        self.LastRefresh = None

    def SetDefault(self):
        """ Store the current display as a default image. 
            When the display is cleared, this default image is restored. 
            This is used to optimise display rendering.            
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.default_character
            self.default_fgcolor
            self.default_bgcolor

            Returns ------------------------------------------
            n/a          """
        for c in range(self.DisplayColumns):
            for r in range(self.DisplayRows):
                self.default_fgcolor[r][c] = self.fgcolor[r][c]
                self.default_bgcolor[r][c] = self.bgcolor[r][c]
                self.default_character[r][c] = self.character[r][c]

    def ConvertLines(self):
        """ Scan the current layout for '-','|','+' symbols and convert to primitive line drawing.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            result (boolean)          """
        # Not yet implemented.
        return True

    def ClipRow(self,row):
        """ Given a row number make sure it is within the range of the display. """
        if row < 0: row = 0
        if row >= self.DisplayRows: row = self.DisplayRows - 1
        return row
        
    def ClipCol(self,col):
        """ Given a column number make sure it is within the range of the display. """
        if col < 0: col = 0
        if col >= self.DisplayColumns: col = self.DisplayColumns - 1
        return col
        
    def DrawBox(self,fromloc,toloc,fg=None,bg=None,border=True,fill=True,overwritelist=['+','-','|',' ']):
        """ Use unicode line characters to draw a box on a colordisplay window. 
                            
            Parameters ---------------------------------------
            fromloc = tuple (fromrow,fromcol)
            toloc = tuple (torow,tocol) 
            fg = Optional Foreground color.
            bg = Optional Background color.
            border = True : Draw border line. 
                   = False : Just color the box. 
            fill = True : Color the interior cells of the box.
                   False : Leave interior cell colors unchanged. 
            overwritelist = [] List of characters that linedrawing is allowed to overwrite. 
                            So you can 'draw' the box using these characters when you define 
                            the display and ONLY these characters get overwritten, this lets
                            you have overlapping titles or gaps in the box if needed by using
                            other characters that are not in the overwritelist                         

            References ---------------------------------------
            textcolor.SYMBOLS list of special characters.

            Sets ---------------------------------------------
            self.character

            Returns ------------------------------------------
            n/a          """
        (fromrow, fromcol) = fromloc
        (torow, tocol) = toloc
        fromrow = self.ClipRow(fromrow)
        torow = self.ClipRow(torow)
        fromcol = self.ClipCol(fromcol)
        tocol = self.ClipCol(tocol)
        if border: # Draw lines around box.
            for c in range(fromcol,tocol + 1):
                # Draw top
                if c == fromcol: char = textcolor.SYMBOLS['corner_tl']
                elif c == tocol: char = textcolor.SYMBOLS['corner_tr']
                else: char = textcolor.SYMBOLS['horizontal']
                cv, _ , _ = self.CellValue(fromrow,c)
                if cv in overwritelist:
                    self.PlaceString(char,fromrow,c,fg=fg,bg=bg)
                # Draw bottom
                if c == fromcol: char = textcolor.SYMBOLS['corner_bl']
                elif c == tocol: char = textcolor.SYMBOLS['corner_br']
                else: char = textcolor.SYMBOLS['horizontal']
                cv , _ , _ = self.CellValue(torow,c)
                if cv in overwritelist:
                    self.PlaceString(char,torow,c,fg=fg,bg=bg)
            char = textcolor.SYMBOLS['vertical']
            if (torow - fromrow) > 1:
                for r in range(fromrow + 1,torow):
                    # Draw left
                    cv , _ , _ = self.CellValue(r,fromcol)
                    if cv in overwritelist:
                        self.PlaceString(char,r,fromcol,fg=fg,bg=bg)
                    # Draw right
                    cv , _ , _ = self.CellValue(r,tocol)
                    if cv in overwritelist:
                        self.PlaceString(char,r,tocol,fg=fg,bg=bg)
        if fill: # Fill the rectangle with the color.
            for c in range(fromcol,tocol + 1):
                for r in range(fromrow,torow + 1):
                    self.ColorCell(r,c,fg,bg)

    def RefreshDue(self):
        """ Return True if refresh is due, else False.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result (boolean)          """
        result = False
        if self.RefreshRate == None: result = True # There's no restriction so always refresh. 
        elif self.LastRefresh == None: result = True # Need to do initial drawing. 
        elif (datetime.now() - self.LastRefresh).total_seconds() > self.RefreshRate: result = True # Refresh is due.
        return result 
        
    def AddSprite(self,name,text,row=None,col=None,fg=15,bg=0,level=0):
        """ Create a sprite. 
            If name is unique, it creates an instance of cdsprite subclass and adds it to the 
            list of sprites managed by this display buffer.                         
            
            Parameters ---------------------------------------
            name : str : Unique name of sprite. Duplicates are rejected.
            text : int : Character to be used for the sprite.
            row : int : Initial row location of sprite.
            col : int : Initial column location of sprite.
            fg : int : Optional foreground color for sprite.
            bg : int : Optional background color for sprite.
            level : int : Rendering sequence. Higher the number the later it is rendered.
                          Sprites always overwrite any other sprites with lower level.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        lFound = False
        for s in self.sprites:
            if s.name == name:
                lFound = True
        if lFound == False: # Safe to add.
            self.sprites.append(cdsprite(name,text,row,col,fg,bg,level))
            # Sort the sprites by level. The higher the level the more to the foreground it is.
            self.sprites = sorted(self.sprites, key=lambda sprite: sprite.level)
        else:
            print ("colordisplay: addsprite (" + name + ") rejected because a sprite by this name already exists.")

    def SpriteLabel(self,name,color=False):
        """ Return sprite label (optionally colored).                         
        
            Parameters ---------------------------------------
            name : str : Name of sprite.
            color : bool : Return label colored or not.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            label (str) : Optionally colored.          """
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.Label(color=color)
        return result

    def ColoredSprite(self,name):
        """ Return sprite character with embedded color codes.                         
        
            Parameters ---------------------------------------
            name : str : Name of sprite.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result : str : sprite character colored with its default colors."""
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.ColoredSymbol()
        return result

    def MoveSprite(self,name,row,col):
        for s in self.sprites:
            if s.name == name:
                s.row = row
                s.column = col

    def ColorSprite(self,name,fg=None,bg=None):
        for s in self.sprites:
            if s.name == name:
                if fg != None: s.fg = fg
                if bg != None: s.bg = bg

    def HideSprite(self,name):
        for s in self.sprites:
            if s.name == name:
                s.display = False

    def ShowSprite(self,name):
        for s in self.sprites:
            if s.name == name:
                s.display = True
                
    def ClearSprites(self):
        self.sprites = []

    def ChangeSprite(self,name,symbol):
        for s in self.sprites:
            if s.name == name:
                s.symbol = symbol

    def SetBorderColors(self,borderfg,borderbg):
        if borderfg == None: self.BorderFG = self.DefaultFG
        else: self.BorderFG = borderfg
        if borderbg == None: self.BorderBG = self.DefaultBG
        else: self.BorderBG = borderbg

    def Clear(self,fg=None,bg=None,immediate=False):
        """ Clear the display buffer, setting all characters to back to their defaults.
            Default image can be updated using the SetDefault() method if needed.
            It does not clear the sprites! You need to do that separately (ClearSprites() method.)        
            Jan.2022 0.0.2 : fg and bg parameters nolonger used.                         
            
            Parameters ---------------------------------------
            fg : int : Foreground color.
            bg : int : Background color.
            immediate : bool : TRUE means display is repainted immediately.
                               FALSE means system waits for next refresh time.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if fg != None: print ('textcolor.colordisplay.Clear() fg parameter is nolonger supported.')
        if bg != None: print ('textcolor.colordisplay.Clear() bg parameter is nolonger supported.')
        for r in range(self.DisplayRows):
            for c in range(self.DisplayColumns):
                self.character[r][c] = self.default_character[r][c]
                self.fgcolor[r][c] = self.default_fgcolor[r][c]
                self.bgcolor[r][c] = self.default_bgcolor[r][c]
        # Reconstruct the title if it is set.
        self.SetTitle()
        if immediate: self.Draw() # Clear the display immediately.

    def CellValue(self,row,col):
        """ Return cell contents. Character, fg and bg colors.                         
        
            Parameters ---------------------------------------
            row : int : Row of the cell.
            col : int : Column of the cell.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            cell character : str : 
            cell foreground color : int :
            cell background color : int :             """
        fg, bg = self.CellColor(row,col)
        char = self.character[row][col]
        return char,fg,bg
        
    def ColorCell(self,row,col,fg,bg):
        """ Change color of a cell, but don't change the text.                         
        
            Parameters ---------------------------------------
            row (int)
            col (int)
            fg (int)
            bg (int)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.fgcolor
            self.bgcolor

            Returns ------------------------------------------
            n/a          """
        self.fgcolor[row][col] = fg
        self.bgcolor[row][col] = bg

    def CellColor(self,row,col):
        """ Return current color of a cell.                         
        
            Parameters ---------------------------------------
            row (int)
            col (int)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            fg (int)
            bg (int)            """
        if row < 0 or row >= self.DisplayRows: fg = self.DefaultFG
        else: fg = self.fgcolor[row][col]
        if col < 0 or col >= self.DisplayColumns: bg = self.DefaultBG
        else: bg = self.bgcolor[row][col]
        return fg, bg

    def ScrollUp(self,lines=1,immediate=False):
        """ Scroll the display up by a number of lines. 
            Drops lines at the top,
            adds new blank lines at the bottom.                         
            
            Parameters ---------------------------------------
            lines (int)
            immediate (bool)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if lines < 1: lines = 1
        if lines > self.DisplayRows: lines = self.DisplayRows
        for i in range(lines):
            self.character.pop(self.FirstScrollRow) # Remove entire 1st data row.
            self.fgcolor.pop(self.FirstScrollRow)
            self.bgcolor.pop(self.FirstScrollRow)
            self.character.append([' ' for c in range(self.DisplayColumns)]) # Add empty row at end of window.
            self.fgcolor.append([self.DefaultFGs[self.FGColorIndex] for c in range(self.DisplayColumns)])
            self.bgcolor.append([self.DefaultBGs[self.BGColorIndex] for c in range(self.DisplayColumns)])
        if immediate: self.Display(immediate=immediate)

    def Concat(self,*args,sep=' '):
        """ Convert all the input arguments into a single string.                         
        
            Parameters ---------------------------------------
            *args : unnamed arguments to be used to construct the string.
            sep (str) : separator between arguments when concatenating.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            concatenated string.          """
        result = ''
        for arg in args:
            if result != '': result = result.strip() + sep # add single clean separator between existing values and the new one.
            result += str(arg) # Add new value.
        result = result.strip() # Clean up.
        return result

    def Print(self,*args,fg=None,bg=None,immediate=False):
        """ Simple scrolling print function. 
            Appends text to bottom of window display and scrolls up as required.
            This allows the retirement of the messagewindow class. 
            
            Parameters ---------------------------------------
            *args unnamed arguments to be used to construct the string.
            immediate=True: Display is immediately refreshed. 
            immediate=False: Display needs to be refreshed elsewhere.
            if fg or bg colors are specified, they override the default color scheme of the display.                         

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (bool)          """
        text = '' # Constructed line of text to display.
        for i in args: # Concatenate all the elements into a single text line.
            if len(text) > 0: text += ' ' # Default to space between each element.
            text += str(i) # All elements must be str type.
        self.PrintHistory.append(text) # Retain recent lines printed. Can be exported, or used to repaint the display if resized.
        while len(self.PrintHistory) > self.DisplayRows: # Drop unwanted lines.
            self.PrintHistory.pop(0) # Drop the first line.
        while len(text) > 0: # Display text, allowing wraparound onto multiple lines.
            if len(text) > self.DisplayColumns: # Too much text to fit on one line.
                print_text = text[:self.DisplayColumns] # Print 1 line's worth of text.
                text = text[self.DisplayColumns:] # Save the rest for the following line(s).
            else: # Remaining text fits on a single line.
                print_text = text # Print what's left.
                text = '' # Nothing else to print after this.
            self.ScrollUp() # No need to pass 'immediate' parameter, it's handled below.
            r = self.DisplayRows - 1
            for i in range(len(print_text)):
                self.character[r][i] = print_text[i]
            if fg != None: # fg color specified.
                for i in range(self.DisplayColumns):
                    self.fgcolor[r][i] = fg
            if bg != None: # bg color specified.
                for i in range(self.DisplayColumns):
                    self.bgcolor[r][i] = bg
        if immediate: self.Display(immediate=immediate) # Update the display immediately.
        self.FGColorIndex = (self.FGColorIndex + 1) % self.FGColorCount # If multiple colors supported, then move on to next available color.
        self.BGColorIndex = (self.BGColorIndex + 1) % self.BGColorCount
        return True

    def PlaceString(self,text,row=None,col=None,fg=None,bg=None):
        """ Place a string at any given location in the display buffer. 
            +ve co-ordinates are top-to-bottom, left-to-right
            -ve co-ordinates are bottom-to-top, right-to-left                         
            
            Parameters ---------------------------------------
            text (str)
            row (int)
            col (int)
            fg (int)
            bg (int)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        if row < 0: row = self.DisplayRows + row # Allow -ve values to work up from the bottom of the window.
        if col < 0: col = self.DisplayColumns + col # Allow -ve values to work left from the right of the window.
        if len(text) > 0 and row >= 0 and row < self.DisplayRows:
            for i in range(len(text)):
                c = col + i # Place in the correct column.
                if c >= 0 and c < self.DisplayColumns:
                    self.character[row][c] = text[i]
                    if fg != None:
                        self.fgcolor[row][c] = fg
                    if bg != None:
                        self.bgcolor[row][c] = bg

    def Draw(self,screenheight=None,screenwidth=None,immediate=False):
        """ Alias for Display() method. For backwards compatibility.                         
        
            Parameters ---------------------------------------
            screenheight (int)
            screenwidth (int)
            immediate (bool)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        print ("***** colordisplay.Draw() method called. Depricated. Use colordisplay.Display() method instead.")
        self.Display(screenheight=screenheight,screenwidth=screenwidth,immediate=immediate)

    def _MarkDisplay(self):
        """ Quickly highlights window dimensions and fields.
            Helps when defining displays in new applications.
            Debug/Dev only.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (bool)         """
        # Mark all the fields clearly.
        for key,value in self.ListFields.items():
            self.FieldColor(key,fg=textcolor.BLACK,bg=textcolor.CYAN)
        # Mark all the corners clearly.
        for c in range(self.DisplayColumns):
            self.fgcolor[0][c] = textcolor.BLACK
            self.fgcolor[self.DisplayRows - 1][c] = textcolor.BLACK
            self.bgcolor[0][c] = textcolor.RED
            self.bgcolor[self.DisplayRows - 1][c] = textcolor.RED
        for r in range(self.DisplayRows):
            self.fgcolor[r][0] = textcolor.BLACK
            self.fgcolor[r][self.DisplayColumns - 1] = textcolor.BLACK
            self.bgcolor[r][0] = textcolor.RED
            self.bgcolor[r][self.DisplayColumns - 1] = textcolor.RED
        return True

    def Transfer(self,targetbuffer,displayrow=None,displaycol=None):
        """ Transfer the current display to another buffer.
            
            Parameters ---------------------------------------
            targetbuffer is the handle to another colordisplay object. 
            displayrow = first row in targetbuffer. If None, then this object's value is used. 
            displaycol = first column in targetbuffer. If None, then this object's value is used.                         

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (bool)          """
        maxscreenrow = targetbuffer.DisplayRows - 1
        maxscreencol = targetbuffer.DisplayColumns - 1
        if displayrow == None: displayrow = self.DisplayRow # Location in target defaults to the location of this object.
        if displaycol == None: displaycol = self.DisplayCol # Location in target defaults to the location of this object.
        for r in range(self.DisplayRows):
            rt = r + displayrow # Where is this display in the new one?
            if rt > maxscreenrow: break # No space for this row.
            for c in range(self.DisplayColumns):
                ct = c + displaycol # Where is this display in the new one?
                if ct > maxscreencol: break # No space for this column.
                targetbuffer.character[rt][ct] = self.character[r][c][0:1] # Select the character for current position. Max 1 char.
                targetbuffer.fgcolor[rt][ct] = self.fgcolor[r][c] # Current foreground color of the chosen character.
                targetbuffer.bgcolor[rt][ct] = self.bgcolor[r][c] # Current background color of the chosen character.
        return True

    def TestBraillePlot(self):
        """ Set a series of pixels around the current window using the BraillePlot method. 
        
            To test
            
                from textcolor import * 
                d = colordisplay(rows=40,columns=80,name='BrailleTest',row=1,col=1,fg=15,bg=0,title="BraillePlot test")
                d.TestBraillePlot()

                """
        self.AddField('graph_corner',20,10,length=1) # Create a field as an anchor point for the pixel plotting.
        self.FieldColor('graph_corner',fg=textcolor.RED,bg=textcolor.WHITE) # Create a field as an anchor point for the pixel plotting.
        ymax = self.LastDisplayRow * 4 - 1
        xmax = (self.LastDisplayCol - 1) * 2 - 1
        for y in range(ymax):
            x = y
            y1 = ymax - y
            self.BraillePlot(y,0,fg=textcolor.CYAN) # Vertical from 0,0
            self.BraillePlot(0,x,fg=textcolor.ORANGE) # Horizontal from 0,0
            self.BraillePlot(y,x,invert=True,fg=textcolor.GRAY) # Diagonal from 0,0
            self.BraillePlot(y1,x,invert=True,fg=textcolor.GREEN) # Diagonal opposite
            self.BraillePlot(ymax,x,fg=textcolor.GREEN) # Horizontal at bottom.
            self.BraillePlot(y,xmax,fg=textcolor.YELLOW) # Vertical on right.
            #self.BraillePlot(y,xmax - 2,fg=textcolor.YELLOW) # Vertical on right.
            #self.BraillePlot(y,xmax - 4,fg=textcolor.YELLOW) # Vertical on right.
            #self.BraillePlot(y,xmax - 6,fg=textcolor.YELLOW) # Vertical on right.
            #self.BraillePlot(y,xmax - 8,fg=textcolor.YELLOW) # Vertical on right.
            self.BraillePlot(y,x,value=True, invert=True,fieldname='graph_corner',fg=textcolor.RED) # Set
            self.Display()
            time.sleep(0.05)
            self.BraillePlot(y,x,value=False,invert=True,fieldname='graph_corner',fg=textcolor.TEAL) # Clear
            self.Display()
            time.sleep(0.05)
        self.FieldValue('graph_corner',"*")
        self.FieldColor('graph_corner',fg=textcolor.RED,bg=textcolor.WHITE) # Create a field as an anchor point for the pixel plotting.
        self.Display()
        print("")
        #print(chr(0x2588) + chr(0x25b6))
        #print(chr(0x2588) + chr(0x25e4))
        #print(chr(0x25c0) + chr(0x2588))
        print(textcolor.coloredlist(['Level 1','Level 2','Level 3','Level 4','Level 5','Level 6'],
                                    [(textcolor.WHITE,textcolor.GREEN),
                                     (textcolor.WHITE,textcolor.TEAL),
                                     (textcolor.WHITE,textcolor.RED),
                                     (textcolor.WHITE,textcolor.BLUE),
                                     (textcolor.WHITE,textcolor.ORANGE1)]))
        
    def BraillePlotLimits(self):
        """ Return max plot coordinates for BraillePlot() 
            Returns max row, max col. """
        return self.LastDisplayRow * 4, self.LastDisplayCol * 2

    def ListToBraillePlot(self,input_list,threshold=0,invert=False,fg=None,bg=None,fieldname=None):
        """ 
        Convert a list to textcolor.colordisplay() object.
        """
        for y,alt_list in enumerate(input_list):
            alt_list = input_list[y] # Input list is a list of rows. Each of those rows is a list of cells in the row.
            for x,value in enumerate(alt_list):
                if value > threshold: self.BraillePlot(y,x,value=True,invert=invert,fg=fg,bg=bg,fieldname=fieldname)
                else: self.BraillePlot(y,x,value=False,invert=invert,fg=fg,bg=bg,fieldname=fieldname)
        return True
        
    def FieldLocation(self,fieldname):
        """
        Return row/col of field.
        """
        row = None
        col = None
        if fieldname != None: # An offset fieldname is given.
            for f in self.Fields: # Search for the field.
                if f.Name == fieldname: # Found a matching fieldname.
                    # Add field location offset to the location.
                    col = f.Column
                    row = f.Row
                    #print("BraillePlot found offset field at",f.Row,f.Column)
                    break
        return row,col
        

    def BraillePlot(self,row,col,value=True,invert=False,fg=None,bg=None,fieldname=None):
        """ Set sub-pixels in characters using the Braille extended character set. 
            This increases the plot resolution by 2*columns and 4*rows. 
            
            (*) The invert parameter flips the counting direction for rows.
            (**) When colouring a parent character the entire 2*4 pixel block will assume the same color.
            
            Parameters ---------------------------------------------------------- 
            row (int) : Pixel row counting from top (*) of window. 
            col (int) : Pixel col counting from left of window. 
            value (bool) : True = Set pixel, False = Clear pixel. 
            invert (bool) : True row parameter counts from BOTTOM of window up. 
                            False row parameter counts from TOP of window down. 
            fg (int) : textcolor color for parent character (**) 
            bg (int) : textcolor color for parent character (**)
            fieldname (str) : Optional name of field which is used as the (0,0) point that the pixel address references.
                              This lets you define screen layouts more easily and add pixel graphics inline with other items. """
        # Get existing character from the window.
        if invert: # Switch from TOP DOWN to BOTTOM UP.
            limit_row, limit_col = self.BraillePlotLimits()
            row = limit_row - row
            
        char_row = row // 4
        char_col = col // 2
        
        if fieldname != None: # An offset fieldname is given.
            for f in self.Fields: # Search for the field.
                if f.Name == fieldname: # Found a matching fieldname.
                    # Add field location offset to the location.
                    char_col += f.Column
                    if invert: char_row -= f.Row
                    else: char_row += f.Row
                    #print("BraillePlot found offset field at",f.Row,f.Column)
                    break
                    
        if char_row < 0 or char_row >= self.DisplayRows or char_col < 0 or char_col >= self.DisplayColumns: 
            #print("BraillePlot:",char_row,char_col,"out of range",self.DisplayRows,self.DisplayColumns)
            return # Out of range, do nothing.
        orig_char = self.character[char_row][char_col] # What existing character are we updating?
        if 0x2800 <= ord(orig_char) <= 0x28ff: bits = ord(orig_char) - 0x2800
        else: bits = 0
        
        dx = col % 2 # Which pixel WITHIN the character cell?
        dy = row % 4 
        dot_index = colordisplay.BRAILLE_MAP[(dx, dy)] # Convert location to the 'bit' that needs to be set.
        if value: bits |= 1 << dot_index # Set the bit. (Use OR operator)
        else: bits &=~(1 << dot_index) # Clear the bit. (Use NAND operation)
                            
        self.character[char_row][char_col] = chr(bits + 0x2800) # Update the display character.
        if fg != None: self.fgcolor[char_row][char_col] = fg
        if bg != None: self.bgcolor[char_row][char_col] = bg

    def SetBit(value,bit):
        """ Set specific bit in an integer value.
            Parameters ---------------------------------
            value (int) : The value to be modified.
            bit (int) : The bit to be set in the value parameter.
            Returns ------------------------------------
            value (int) : The modified value with appropriate bit set. """
        value |= 1 << bit # Set the bit. (Use OR operator)
        return value
        
    def ClearBit(value,bit):
        """ Clear specific bit in an integer value.
            Parameters ---------------------------------
            value (int) : The value to be modified.
            bit (int) : The bit to be cleared in the value parameter.
            Returns ------------------------------------
            value (int) : The modified value with appropriate bit cleared. """
        value &=~(1 << bit) # Clear the bit. (Use NAND operation)
        return value
        
    def ForceRedraw(self):
        """ Flushes old values from self.PrevLineStrings[] forcing a full refresh.
            Normally when calling the Display() method, only changes are sent to the terminal window.
            If you ForceRedraw() then the whole window is sent fresh.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            self.PrevLineStrings

            Returns ------------------------------------------
            n/a          """
        self.PrevLineStrings = [' ' for i in self.PrevLineStrings]
    
    @staticmethod
    def GlobalForceRedraw(): # Common
        """ Flushes old values from self.PrevLineStrings[] forcing a full refresh in all registered windows.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Calls ForceRedraw() method in all defined windows.

            Returns ------------------------------------------
            n/a          """
        for w in colordisplay.DefinedWindows:
            try:
                w.ForceRedraw()
            except:
                pass # Window nonlonger exists.

    def GetTextLines(self):
        """ Returns the display layout as a list of strings.
            No color or cursor codes are included, just the basic monotone display text.
            Sprites are shown in their latest position too.                         
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            list of current display buffer lines.          """
        linelist = []
        for r in range(self.DisplayRows): # Go through all the rows in turn.
            line = ''
            for c in range(self.DisplayColumns): # Go through each column in turn. 
                line += self.character[r][c][0:1] # Select the character for current position. Max 1 char too!
            linelist.append(line)
        # Overlay sprites if they exist.
        for s in self.sprites: # Check all sprites in turn.
            if s.row != None and s.column != None and s.row >= 0 and s.row < self.DisplayRows and s.column >= 0 and s.column < self.DisplayColumns: # In range.
                linelist[s.row] = linelist[s.row][:s.column] + s.symbol[0:1] + linelist[s.row][s.column + 1:]
        return linelist
    
    def DisplayTextLines(self):
        """ Display current contents of the window in a text box.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        textcolor.TextBox(self.GetTextLines())
        
    @staticmethod
    def GlobalViewWindows(titlefg=None,titlebg=None):
        """ Construct a menu of all available windows
            then choose which window to display.                         
            
            Parameters ---------------------------------------
            titlefg (int)
            titlebg (int)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        # Dynamically construct menu entries.
        dictionary = {}
        for w in colordisplay.DefinedWindows:
            itemdict = {}
            if w.WindowTitle != None: itemdict['label'] = w.WindowTitle
            else: itemdict['label'] = w.DisplayName
            itemdict['bold'] = False
            itemdict['call'] = w.DisplayTextLines
            itemdict['docurl'] = None
            itemdict['helpdoc'] = 'help.txt'
            dictionary[w.DisplayName] = itemdict
        WindowMenu = proceduremenu(dictionary,'Window contents menu',titlefg=None,titlebg=None,labelwidth=30)
        WindowMenu.Prompt()
        
    def Display(self,screenheight=None,screenwidth=None,immediate=False):
        """ Take the display buffer and output it to the terminal. 
            This places the image at a specific location in the window.
                       
            Parameters ---------------------------------------
            screenheight: Tells the number of rows available in the terminal display. 
            screenwidth: Tells the number of columns available in the terminal display. 
            immediate: (True) Forces immediate update of the terminal display.
                       (False) Only updates the display if the refresh timer is due.                         

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """

        if immediate == False and self.RefreshDue() == False: return # Don't perform a refresh yet.
        # Define the maximum ROW and COLUMN number that can be addressed with the current window size.
        if screenheight == None: maxscreenrow = None
        else: maxscreenrow = screenheight - 1
        if screenwidth == None: maxscreencol = None
        else: maxscreencol = screenwidth - 1
        if self.LastDisplayRow != None and maxscreenrow != None: # We have a specific location to use, check if that location is in the current display dimensions.
            if self.ClipWindow == False and maxscreenrow <= self.LastDisplayRow: # Not enough height for the ENTIRE window and not allowed to clip.
                return # Don't try to display.
            if maxscreenrow < self.DisplayRow: # None of the window fits on the terminal at all even if clipping allowed.
                return # Don't try to display.
        if self.LastDisplayCol != None and maxscreencol != None: # We have a specific location to use, check if that location is in the current display dimensions.
            if self.ClipWindow == False and maxscreencol <= self.LastDisplayCol: # Not enough width for the ENTIRE window and not allowed to clip.
                return # Don't try to display.
            if maxscreencol < self.DisplayCol: # None of the window fits on the terminal at all even if clipping allowed.
                return # Don't try to display.
        if maxscreencol == None: maxscreencol = 1000 # Allow any size.
        if maxscreenrow == None: maxscreenrow = 1000
        HorizontalChar = textcolor.SYMBOLS['horizontal'] # '\u2500'
        VerticalChar = textcolor.SYMBOLS['vertical'] # '\u2502'
        CornerChar = textcolor.SYMBOLS['corner_br'] # '\u2518'
        self.UpdateBlinkStatus() # If any fields are supposed to blink, check their color now.
        self.DisplayAnimation() # Update any animations in the display (pulse etc).
        if self.MarkDisplay: # We need to mark up the corners and fields.
            self._MarkDisplay()
        for r in range(self.DisplayRows): # Go through all the rows in turn. *Q* Should respect 'ClipWindow' too.
            if self.ClipWindow and self.DisplayRow != None and (r + self.DisplayRow) > maxscreenrow: break # We're off the end of the available display.
            try:
                # The following code has occassionally failed with an IndexError. Added some debugging in case it occurs again to aid solving.
                runningfg = self.fgcolor[r][0] # Note what color we're printing at the start of the line. Color control codes change when this value changes.
                runningbg = self.bgcolor[r][0]
            except IndexError as e:
                print("colordisplay.Display() fault: Index out of range?",r,0)
                print("colordisplay.Display() fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor))
                print("colordisplay.Display() fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol)
                print("colordisplay.Display() fault: LastDisplayRow",self.LastDisplayRow,"LastDisplayCol",self.LastDisplayRow)
                print("colordisplay.Display() fault: DisplayRow",self.DisplayRow,"DisplayCol",self.DisplayCol)
                print("colordisplay.Display() fault: DisplayRows",self.DisplayRows,"DisplayColumns",self.DisplayColumns)
                print("colordisplay.Display() fault: ClipWindow",self.ClipWindow)
                if self.Log != None:
                    self.Log("colordisplay.Display() fault: Index out of range?",r,0,level='error',terminal=True)
                    self.Log("colordisplay.Display() fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor),level='error',terminal=True)
                    self.Log("colordisplay.Display() fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol,level='error',terminal=True)
                    self.Log("colordisplay.Display() fault: LastDisplayRow",self.LastDisplayRow,"LastDisplayCol",self.LastDisplayRow,level='error',terminal=True)
                    self.Log("colordisplay.Display() fault: DisplayRow",self.DisplayRow,"DisplayCol",self.DisplayCol,level='error',terminal=True)
                    self.Log("colordisplay.Display() fault: DisplayRows",self.DisplayRows,"DisplayColumns",self.DisplayColumns,level='error',terminal=True)
                    self.Log("colordisplay.Display() fault: ClipWindow",self.ClipWindow,level='error',terminal=True)
                raise Exception("Index out of range") from e # Terminate through the regular exception routine.
            line = textcolor.fgbgcolor(runningfg,runningbg,"",reset=False) # Start line off with initial color scheme. Leave the control code 'open' for more text to be added.
            for c in range(self.DisplayColumns): # Go through each column in turn. 
                if self.ClipWindow and self.DisplayCol != None and (c + self.DisplayCol) > maxscreencol: break # We're off the end of the available display.
                ch = self.character[r][c][0:1] # Select the character for current position. Max 1 char too!
                f = self.fgcolor[r][c] # Current foreground color of the chosen character.
                b = self.bgcolor[r][c] # Current background color of the chosen character.
                # Check if any sprites override this character.
                for s in self.sprites: # Check all sprites in turn.
                    if s.row == r and s.column == c and s.display: # Same location and visible.
                        ch = s.symbol[0:1] # Only 1 character allowed for the sprite at the moment.
                        f = s.fg # Sprite fg and bg colors override the background.
                        b = s.bg
                if runningfg != f or runningbg != b: # Color scheme has changed. Insert appropriate code.
                    runningfg = f # Note new colors we're now printing with.
                    runningbg = b
                    line += textcolor.fgbgcolor(runningfg,runningbg,"",reset=False) # Insert open-ended color change code.
                if len(ch) < 1: # Make sure that the character is the right length.
                    ch = " "
                line += ch # Add the character.
            if self.DisplayRow != None and self.DisplayCol != None:
                # The display has a specific location on the terminal window. Place it there.
                dr = self.DisplayRow + r
                dc = self.DisplayCol
                line = textcolor.cursor(dc,dr) + line # Locate the line on the terminal layout.
            line += textcolor.reset()
            if self.DrawBorder and self.LastDisplayCol + 1 < maxscreencol: line += textcolor.fgbgcolor(self.BorderFG,self.BorderBG,VerticalChar)
            if self.ReduceIO == False or self.PrevLineStrings[r] != line: # The line has changed. So display the new string. Otherwise save display time and leave it unchanged.
                print (line,end='',flush=True) # Do not add newline character at end of the printed text. Always flush the print buffer.
            self.PrevLineStrings[r] = line # Store the print command so we can compare next time if anything changed.
        if self.DrawBorder and self.LastDisplayRow + 1 < maxscreenrow: 
            visiblecolumns = maxscreencol - self.DisplayCol + 1
            if visiblecolumns < self.DisplayColumns + 1: # We cannot fit the entire bottom border line and corner in the display, just show what's possible.
                line = textcolor.fgbgcolor(self.BorderFG,self.BorderBG,(HorizontalChar * visiblecolumns)) # Truncate the line.
            else:#  The whole border line and corner should fit in the display.
                line = textcolor.fgbgcolor(self.BorderFG,self.BorderBG,(HorizontalChar * self.DisplayColumns) + CornerChar) # Full line including corner character.
            print(textcolor.cursor(self.DisplayCol,self.DisplayRow + self.DisplayRows) + line)
        self.LastRefresh = datetime.now()

    def InlineDisplay(self,border=False):
        """ Take the display buffer and output it to the terminal. 
            This just appends the image to the current terminal text, it does not PLACE the image anywhere specifically. 
                     
            Parameters ---------------------------------------
            border : False, no border is added. 
                     True, simple border is added.                         

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            Sends output to terminal display.

            Returns ------------------------------------------
            n/a          """

        #print("textcolor.py:colordisplay(",self.DisplayName,").InlineDisplay(): DisplayRows=",self.DisplayRows,", DisplayColumns=",self.DisplayColumns)
        for r in range(self.DisplayRows): # Go through all the rows in turn. 
            try:
                # The following code has occassionally failed with an IndexError. Added some debugging in case it occurs again to aid solving.
                runningfg = self.fgcolor[r][0] # Note what color we're printing at the start of the line. Color control codes change when this value changes.
                runningbg = self.bgcolor[r][0]
            except IndexError as e:
                print("colordisplay.InlineDisplay() fault: Index out of range?",r,0)
                print("colordisplay.InlineDisplay() fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor))
                print("colordisplay.InlineDisplay() fault: LastDisplayRow",self.LastDisplayRow,"LastDisplayCol",self.LastDisplayRow)
                print("colordisplay.InlineDisplay() fault: DisplayRow",self.DisplayRow,"DisplayCol",self.DisplayCol)
                print("colordisplay.InlineDisplay() fault: DisplayRows",self.DisplayRows,"DisplayColumns",self.DisplayColumns)
                if self.Log != None:
                    self.Log("colordisplay.InlineDisplay() fault: Index out of range?",r,0,level='error',terminal=True)
                    self.Log("colordisplay.InlineDisplay() fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor),level='error',terminal=True)
                    self.Log("colordisplay.InlineDisplay() fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol,level='error',terminal=True)
                    self.Log("colordisplay.InlineDisplay() fault: LastDisplayRow",self.LastDisplayRow,"LastDisplayCol",self.LastDisplayRow,level='error',terminal=True)
                    self.Log("colordisplay.InlineDisplay() fault: DisplayRow",self.DisplayRow,"DisplayCol",self.DisplayCol,level='error',terminal=True)
                    self.Log("colordisplay.InlineDisplay() fault: DisplayRows",self.DisplayRows,"DisplayColumns",self.DisplayColumns,level='error',terminal=True)
                raise Exception("Index out of range") from e # Terminate through the regular exception routine.
            line = textcolor.fgbgcolor(runningfg,runningbg,"",reset=False) # Start line off with initial color scheme. Leave the control code 'open' for more text to be added.
            for c in range(self.DisplayColumns): # Go through each column in turn. 
                ch = self.character[r][c][0:1] # Select the character for current position. Max 1 char too!
                f = self.fgcolor[r][c] # Current foreground color of the chosen character.
                b = self.bgcolor[r][c] # Current background color of the chosen character.
                # Check if any sprites override this character.
                for s in self.sprites: # Check all sprites in turn.
                    if s.row == r and s.column == c and s.display: # Same location and visible.
                        ch = s.symbol[0:1] # Only 1 character allowed for the sprite at the moment.
                        f = s.fg # Sprite fg and bg colors override the background.
                        b = s.bg
                if runningfg != f or runningbg != b: # Color scheme has changed. Insert appropriate code.
                    runningfg = f # Note new colors we're now printing with.
                    runningbg = b
                    line += textcolor.fgbgcolor(runningfg,runningbg,"",reset=False) # Insert open-ended color change code.
                if len(ch) < 1: # Make sure that the character is the right length.
                    ch = " "
                line += ch # Add the character.
            line += textcolor.reset()
            print(line)

    @staticmethod
    def GlobalExportFields(filename,initialdictionary={}):
        """ Export field values from all windows to json file.
            Data is appended to any values already existing in initialdictionary.                         
            
            Parameters ---------------------------------------
            fieldname (str)
            initialdictionary (dict)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (bool)          """
        tempdict = colordisplay.GlobalSaveToDictionary(initialdictionary=initialdictionary)
        with open(filename,'w') as f:
            json.dump(tempdict,f,default=str)
        return True
        
    @staticmethod
    def GlobalSaveToDictionary(initialdictionary={}):
        """ Export field values from all windows to dictionary.
            Data is appended to any values already existing in initialdictionary.                         
            
            Parameters ---------------------------------------
            initialdictionary (dict)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            tempdict (dict)          """
        tempdict = initialdictionary
        for w in colordisplay.DefinedWindows:
            for field in w.Fields:
                tempdict[w.DisplayName + "." + field.Name] = field.Value
            tempdict[w.DisplayName + '.PrintHistory'] = w.PrintHistory
        return tempdict
        
    @staticmethod
    def GlobalFieldFormat(name, justify=None, pattern=None, bwz=None): # Common
        """ Update the format of a field in all defined windows.                         
            
            Parameters ---------------------------------------
            name (str)
            justify (str)
            pattern (str)
            bwz (bool)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            FieldFormat of named fields in each window.

            Returns ------------------------------------------
            success (bool)          """
        FoundIt = False
        for w in colordisplay.DefinedWindows:
            try:
                temp = w.FieldFormat(name=name, justify=justify, pattern=pattern, bwz=bwz)
                if temp: FoundIt = True
            except:
                pass # Window nonlonger exists.
        return FoundIt
    
    @staticmethod
    def GlobalFieldValue(name,value,fg=None,bg=None): # Common
        """ Update the value of a field in all defined windows and display it.                         
        
            Parameters ---------------------------------------
            name (str)
            value (str)
            fg (int)
            bg (int)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (bool)          """
        FoundIt = False
        for w in colordisplay.DefinedWindows:
            try:
                temp = w.FieldValue(name=name,value=value,fg=fg,bg=bg)
                if temp: FoundIt = True
            except:
                pass # Window nonlonger exists.
        return FoundIt
    
    @staticmethod
    def GlobalFieldColor(name,fg=None,bg=None): # Common
        """ Update the color of a field in all defined windows.                         
        
            Parameters ---------------------------------------
            name (str)
            fg (int)
            bg (int)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            success (bool)          """
        FoundIt = False
        for w in colordisplay.DefinedWindows:
            try:
                temp = w.FieldColor(name=name,fg=fg,bg=bg)
                if temp: FoundIt = True
            except:
                pass # Window nolonger exists.
        return FoundIt
        

    @staticmethod
    def GlobalReduceIO(reduce=True):
        """ Turn on/off the ReduceIO function in all defined windows. 
            reduce = True turns it on.
            reduce = False turns it off. 
                                   
            Parameters ---------------------------------------
            reduce (bool)
                When True: All defined display windows will apply the ReduceIO rules. 
                           When refreshing the display ONLY the changed characters are 
                           updated to the terminal. This makes the refresh considerably
                           faster for displays where only a few characters change each time. 
                           In most cases this is the most efficient way to refresh the displays.
                When False: All the defined display windows will completely redraw
                           all their contents each time the display is refreshed, even if
                           nothing has changed.                         

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        for w in colordisplay.DefinedWindows:
            try:
                w.ReduceIO = reduce
            except:
                pass # Window nolonger exists.
        return

    @staticmethod
    def GlobalDisplay(screenheight=None,screenwidth=None,immediate=False): # Common
        """ Display ALL defined windows in a single call.                         
        
            Parameters ---------------------------------------
            screenheight (int)
            screenwidth (int)
            immediate (bool)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        for w in colordisplay.DefinedWindows:
            try:
                w.Display(screenheight=screenheight,screenwidth=screenwidth,immediate=immediate)
            except:
                pass # Window nolonger exists.
        return
        
    @staticmethod
    def GlobalWindowLimits():
        """ Return maximum ROW and COLUMN that any of the current windows extend into.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            tuple (maxcol (int), maxrow (int))           """
        maxrow = 0
        maxcol = 0
        for w in colordisplay.DefinedWindows:
            try:
                maxrow = max(maxrow,w.LastDisplayRow)
                maxcol = max(maxcol,w.LastDisplayCol)
            except:
                pass # Window nolonger exists.
        return (maxcol, maxrow)
    

# -------------------------------------------------------------------------------------------------------------------------------- 

class menu():
    """ Original menu class. Now replaced by proceduremenu class. """

    __version__ = '0.0.2'

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None):
        """ Raise an error if this is called.
            Calling code needs to switch to newer version. """
        raise NotImplementedError('textcolor.menu: NOTE: This is replaced by the textcolor.proceduremenu class now!')

# -------------------------------------------------------------------------------------------------------------------------------- 

class proceduremenu():
    """ Menu driver.
        Create a menu object.
        Give it a dictionary of menu items, including labels and functions/methods to call.
        Call the Prompt() method to execute the menu. 
        Menu quits when user selects 'x' option. 
        
        dictionary format 
                {'menuitem1key':{'label':'menu item 1 label', 'bold':True/False, 'call': ProcedureName to call, 'break': False, 'color': textcolor.yellow},
                 'menuitem2key':{'label':'menu item 2 label', 'bold':True/False, 'call': ProcedureName to call}
                }
                
                'docurl' = URL for help documentation about the menu option.
                'helpdoc' = Local text file location for help documentation about the menu option.
                'break' = Insert a blank line separator in the menu after the option.
                'call' = Procedure to call if option is selected. (No parameters supported)
                'bold' = Print the menu option in bold text.
                'label' = The label to appear in the menu.
                'precall' = Optional: Procedure call to make BEFORE the 'call' procedure is called. If this fails, the 'call' and 'postcall' procedures are not called.
                'postcall' = Optional: Procedure call to make AFTER the 'call' procedure is called. This is executed even if the 'call' procedure fails.
                'color' = The name of the textcolor color to use for the label. If missing the default is used.
                'close' = True = Menu will close once the selected option is complete.
                           False or missing = User remains in the menu until they choose to return.

                'id' is added automatically. It is the menu ID number.
                'enabled' is added automatically. It indicates that the menu option is currently visible and selectable.
                
        You can also specify global PRE and POST procedure calls by setting the procedure handle in 
        self.PreCall and self.PostCall attributes.
        - self.PreCall is called for all menu options BEFORE any of the procedures defined in the dictionary.
        - self.PostCall is called for all menu options AFTER all the procedures defined in the dictionary.
        
        Therefore a single menu option can execute up to 5 procedures in sequence.
        - self.PreCall gives a global 'preparation' routine to run before all menu options.
            If self.PreCall fails, the 'precall' and 'call' procedures are skipped, execution passes
            immediately to the 'postcall' and self.PostCall procedures.
        - 'precall' gives an option specific preparation routine to run before the main option.
            If 'precall' fails, the 'call' procedure does not get executed, control passes immediately
            to the 'postcall' and self.PostCall procedures.
        - 'call' is the main routine to run for the menu option.
            If self.PreCall or 'precall' options fail, the 'call' option is not executed, execution passes
            immediately to the cleanup 'postcall' and self.PostCall procedures.
        - 'postcall' gives an option specific cleanup routine to run after the menu option even if it failed.
        - self.PostCall gives a global cleanup routine to run after all menu options even if they failed.
        - 'close' when True the menu closes when the procedure completes. Otherwise the user returns to the menu.
                
        You can trigger user input via the Prompt() method.
        You can directly run a menu option without user input via the Run() method.
        """

    __version__ = '0.0.3'
    menu_stack = [] # List of active menus in sequence. Shows nesting of menus.

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None,labelwidth=23,showmenupath=False):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            
            Parameters ---------------------------------------
            dictionary (dict) : Dictionary containing menu definition.
            title (str) : Title of menu.
            titlebg/fg (int) : colors of menu title.
            helpdir (str) : directory where help text files exist. 
            helpurl (str) : url to help file.   
            logger (logfile instance) : Handle to pilomar logfile handler.
            labelwidth (int) : Minimum character width of menu labels, automatically increased if any menu item requires more space.         
            showmenupath (bool) : When TRUE the menu title includes color coded reference to all preceeding menus.
                                  This is useful when nesting menus where overall context is important.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        self.Dictionary = dictionary
        self.Title = title
        self.IdWidth = 2
        self.LabelWidth = labelwidth
        self.TitleFG = titlefg
        self.Columns = 2 # How many columns to draw?
        self.Log = logger # Can define a logging function to use.
        self.PreCall = None # Specify a procedure to call before ALL options.
        self.PostCall = None # Specify a procedure to call AFTER ALL options.
        if titlefg == None: self.TitleFG = textcolor.BLACK
        self.TitleBG = titlebg
        if titlebg == None: self.TitleBG = textcolor.YELLOW
        #self.TitleColorList = [(self.TitleFG,self.TitleBG)] # *Q* Calculate colorlist for nested menu colors here?
        self.ShowMenuPath = showmenupath # When TRUE the menu title shows all proceeding menu levels too, but color coded.
        self.TitleColorList = [(self.TitleFG,self.TitleBG), # Shades of green. (fg,bg) tuples.
                               (textcolor.WHITE,textcolor.GREEN4),
                               (textcolor.WHITE,textcolor.GREEN3),
                               (textcolor.WHITE,textcolor.GREEN3A),
                               (textcolor.WHITE,textcolor.CHARTREUSE3A),
                               (textcolor.BLACK,textcolor.CHARTREUSE2),
                               (textcolor.BLACK,textcolor.CHARTREUSE1)
                              ]
        Counter = 0
        for key,value in self.Dictionary.items(): # Assign menu ID number to each entry.
            Counter += 1
            value['id'] = Counter
            value['enabled'] = True # All menu options are enabled and visible by default.
            self.LabelWidth = max(self.LabelWidth,len(value['label']))
            
            try: # Check that the procedure name to be called looks valid.
                if type(value['call']) != None: # This will fail if the procedure name is wrong.
                    pass
            except Exception as e:
                # The procedure call will not succeed if called.
                print (textcolor.red(self.Title,'Cannot execute procedure',value['label']))
                print (textcolor.red(str(e)))
                traceback.print_exc()
                
            try: # Check that the pre-procedure name to be called looks valid.
                if type(value.get('precall',None)) != None: # This will fail if the procedure name is wrong.
                    pass
            except Exception as e:
                # The procedure call will not succeed if called.
                print (textcolor.red(self.Title,'Cannot execute pre-procedure',value['label']))
                print (textcolor.red(str(e)))
                traceback.print_exc()
                
            try: # Check that the post-procedure name to be called looks valid.
                if type(value.get('postcall',None)) != None: # This will fail if the procedure name is wrong.
                    pass
            except Exception as e:
                # The procedure call will not succeed if called.
                print (textcolor.red(self.Title,'Cannot execute post-procedure',value['label']))
                print (textcolor.red(str(e)))
                traceback.print_exc()
        self.HelpDir = helpdir
        self.HelpUrl = helpurl

    def GetHelpFile(self,menuid):
        """ Given an ID number, retrieve and display the help text if it exists.                         
        
            Parameters ---------------------------------------
            menuid

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            url (str)          """
        filename = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                filename = value.get('helpdoc',None) # Get the helpdoc filename.
                break # Look no further.
        if filename != None and self.HelpDir != None:
            filename = self.HelpDir + filename # Construct path to file.
        return filename
        
    def ShowHelpText(self,menuid):
        """ Given an ID number, display text help documentation.                         
        
            Parameters ---------------------------------------
            menuid

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        filename = self.GetHelpFile(menuid)
        if filename != None:
            try:
                with open(filename,'r') as f:
                    for line in f.readlines():
                        print (textcolor.cyan(line))
            except Exception as e:
                print(textcolor.red('Sorry, unable to show the help file.'))
                print(str(e))
        else:
            print (textcolor.red('Sorry, no help file is defined for menu item',menuid))
        
    def GetHelpUrl(self,menuid):
        """ Given an ID number, return URL associated with the help documentation.                         
        
            Parameters ---------------------------------------
            menuid

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            url (str)          """
        helpurl = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                helpurl = value.get('helpurl',None) # Get the helpdoc helpurl.
                break # Look no further.
        if helpurl != None and self.HelpDir != None:
            helpurl = self.HelpDir + helpurl # Construct path to file.
        return helpurl
        
    def ColorMenuPath(self):
        """ Return textcolored path through preceeding menus to this one. """
        m_list = [m.Title for m in proceduremenu.menu_stack]
        cmp = textcolor.coloredlist(words=m_list,colors=self.TitleColorList,reverse=True)
        return cmp
            
        
    def Draw(self,menuprefix=''):
        """ Draw the menu on the terminal.
            The menu list from the dictionary will automatically gain '?' and 'x' options too.                         
            
            Parameters ---------------------------------------
            menuprefix (str) : Arbitrary prefix placed in front of menu title. Deprecated.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
        count = 0
        print (textcolor.clearforward()) # Blank line before menu and clear everything below that.
        if self.ShowMenuPath: print (self.ColorMenuPath()) # Title showing menu tree to get where you are.
        else: print (textcolor.fgbgcolor(self.TitleFG,self.TitleBG,' ' + self.Title + ' ')) # Menu title is painted in inverse colors. 
        for key,value in self.Dictionary.items(): # Go through each menu item in turn.
            if value['enabled'] == False: continue # Not visible or selectable, skip it.
            entry = textcolor.yellow(str(value['id']).rjust(self.IdWidth,' ')) + ' ' # ID number in yellow. 
            if value.get('color',None) != None: # Menu item has a specific label color.
                entry += value['color'](value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            elif value.get('bold',False): # If the menu item is in bold, make it so.
                entry += textcolor.white(value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            else: # Menu item is not in bold.
                entry += value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth]
            entry += ' ' # Space between columns of menu entries. 
            print (entry,end='') # Print the menu entry column, don't include 'newline' yet.
            count += 1 # Count how many entries.
            if count % self.Columns == 0: # Print 'newline' after 2nd column entry.
                print ('')
            if value.get('break',False): 
                if count % self.Columns != 0: # We're terminating the line early.
                    print ('')
                    count = 0
                print ('') # Insert a blank line break in the menu.
        if count % self.Columns != 0: # Print 'newline' if we didn't complete the 2nd column when the menu list ran out.
            print ('') # Terminate line if not already done.
        # Always include 'x' and '?' menu options automatically.
        print (textcolor.yellow('x'.rjust(self.IdWidth,' ')) + ' ' + 'Exit'.ljust(self.LabelWidth,' ')[:self.LabelWidth] + ' ',end='')
        print (textcolor.yellow('?'.rjust(self.IdWidth,' ')) + ' ' + 'Refresh'.ljust(self.LabelWidth,' ')[:self.LabelWidth])
        
    def Run(self,key):
        """ Given a menu option key, execute the procedure or sub-menu associated with it.
            if PRE and/or POST procedures are defined, execute those too. 
            These allow you to prepare and/or cleanup even if the main call fails.                         
            
            Parameters ---------------------------------------
            key

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            success (bool)          """
            
        ExecuteMain = True
        Success = True # Set the return code.
        
        # Global Pre procedure. # Execute BEFORE the main procedure call.
        if self.PreCall != None: # See if it's a callable function.
            try: # See if the pre-procedure will execute. 
                self.PreCall() # Call it.
            except Exception as e:
                # Procedure didn't execute. Report the error and return to the menu.
                print(textcolor.red(' *** OOPS! *** ',invert=True))
                print(textcolor.red('** Menu failed to execute ' + str(key) + " ; global pre-call " + str(self.PreCall)))
                print(textcolor.red(str(e)))
                traceback.print_exc()
                ExecuteMain = False # Do not execute the main call.
                Success = False # Set the return code.
                
        # Option Pre procedure. # Execute BEFORE the main procedure call.
        if ExecuteMain: # OK to proceed.
            Procedure = self.Dictionary[key].get('precall',None) # What pre-procedure is to be called?
            if Procedure != None: # See if it's a callable function.
                try: # See if the pre-procedure will execute. 
                    Procedure() # Call it.
                except Exception as e:
                    # Procedure didn't execute. Report the error and return to the menu.
                    print(textcolor.red(' *** OOPS! *** ',invert=True))
                    print(textcolor.red('** Menu failed to execute ' + str(key) + " ; option pre-call " + str(Procedure)))
                    print(textcolor.red(str(e)))
                    traceback.print_exc()
                    ExecuteMain = False # Do not execute the main call.
                    Success = False # Set the return code.
                
        # Main procedure.
        if ExecuteMain: # OK to proceed.
            Procedure = self.Dictionary[key]['call'] # What procedure is to be called?
            if Procedure == None: # No option to run.
                print(textcolor.yellow(str(key) + " does not have a related procedure to call."))
            elif type(Procedure) == type(self): # A submenu, so we trigger the nested submenu instead. 
                Procedure.Prompt() # Execute the submenu.
            else: # See if it's a callable function.
                try: # See if the procedure will execute. 
                    Procedure() # Call it.
                except Exception as e:
                    # Procedure didn't execute. Report the error and return to the menu.
                    print(textcolor.red(' *** OOPS! *** ',invert=True))
                    print(textcolor.red('** Menu failed to execute ' + str(key) + " ; call " + str(Procedure)))
                    print(textcolor.red(str(e)))
                    traceback.print_exc()
                    Success = False # Set the return code.

        # Option Post procedure. # Execute AFTER the main procedure call.
        Procedure = self.Dictionary[key].get('postcall',None) # What post-procedure is to be called?
        if Procedure != None: # See if it's a callable function.
            try: # See if the post-procedure will execute. 
                Procedure() # Call it.
            except Exception as e:
                # Procedure didn't execute. Report the error and return to the menu.
                print(textcolor.red(' *** OOPS! *** ',invert=True))
                print(textcolor.red('** Menu failed to execute ' + str(key) + " ; option post-call " + str(Procedure)))
                print(textcolor.red(str(e)))
                traceback.print_exc()
                Success = False # Set the return code.

        # Global Post procedure. # Execute AFTER the main procedure call.
        if self.PostCall != None: # See if it's a callable function.
            try: # See if the post-procedure will execute. 
                self.PostCall() # Call it.
            except Exception as e:
                # Procedure didn't execute. Report the error and return to the menu.
                print(textcolor.red(' *** OOPS! *** ',invert=True))
                print(textcolor.red('** Menu failed to execute ' + str(key) + " ; global post-call " + str(self.PostCall)))
                print(textcolor.red(str(e)))
                traceback.print_exc()
                Success = False # Set the return code.

        return Success # True if all succeeded, False if any failed.
        
    def ProcessHelpRequest(self,rawtext):
        """ Receive a text type menu id as text.
            if it converts to an integer successfully, 
            show the help text associated with that menu item.                         
            
            Parameters ---------------------------------------
            rawtext (str)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        rawtext = rawtext.replace('?','') # Remove any question mark.
        try:
            menuid = int(rawtext)
        except:
            menuid = None
        if menuid != None:
            self.ShowHelpText(menuid)
        
    def Prompt(self,menuprefix=''):
        """ Execute the menu. 
            This paints the menu on the terminal and deals with user selections. 
            Menu items are numbered dynamically, the user selects an item by selecting the number.
            If the user enters the number plus a '?' symbol then help text is displayed if it can be found.
            The method closes when the user selects the 'x' option. 
            
            Note, you can also trigger options from the menu without user prompting by using the menu.Run(name) method.                        
            
            Parameters ---------------------------------------
            menuprefix (str) : Arbitrary prefix prepended to menu title. Deprecated.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a           """
        # Now paint the menu and ask the user what to do.
        proceduremenu.menu_stack.append(self) # Add this menu to the currently active stack of menus. Traces the current path through the menu structure to this point.
        #self.Draw(menuprefix=menuprefix) # Paint the menu.
        self.Draw() # Paint the menu.
        closeflag = False
        while True: # Loop until explicitly told to terminate.
            if self.Log != None: self.Log('Menu waiting for user input.',terminal=False)
            answer = input(textcolor.cyan('Menu option : ')) # Prompt for input.
            if self.Log != None: self.Log('Menu received user input',answer,'.',terminal=False)
            if answer == '?': # Refresh the menu.
                self.Draw() # Refresh the menu.
                continue
            if answer == ">": # Increase columns in display.
                self.Columns += 1
                self.Draw() # Refresh the menu.
                continue
            if answer == "<": # Increase columns in display.
                self.Columns -= 1
                self.Columns = max(self.Columns,1) # must be at least 1 column.
                self.Draw() # Refresh the menu.
                continue
            if '?' in answer: # User wants help about an option.
                self.ProcessHelpRequest(answer)
                continue # Prompt again.
            # Process menu choice.
            try: # Convert text into integer if possible.
                menuid = int(answer)
            except Exception:
                # Text would not convert into integer. 
                menuid = None
            if menuid != None: # 
                found = False # Have we found and executed the menu option?
                closeflag = False # Don't close the menu.
                for key,value in self.Dictionary.items():
                    if value['enabled'] == False: continue # Not visible or selectable, skip it.
                    closeflag = self.Dictionary[key].get('close',False) # Should the menu close immediately?
                    if value['id'] == menuid:
                        self.Run(key) # Execute the option.
                        found = True # We have found and executed the option. OK to return to ask user for new input.
                        self.Draw() # Refresh the menu.
                        break # No need to check other key value pairs.
                if found: # Option was found and executed. Return to user input.
                    continue # Next user input.
            if closeflag: # The menu should shut down once the procedure has completed.
                break
            if answer.lower() == '?': # Refresh option chosen.
                self.Draw() # Refresh the menu.
                continue # Next user input.
            if answer.lower() == 'x': # User chose to quit the menu. Terminate the loop.
                break # Go UP a level, quit if at root.
            # User input was not recognised. Try again.
            print (textcolor.red("'" + str(answer) + "' Unrecognised. Try again."))
        proceduremenu.menu_stack = proceduremenu.menu_stack[:-1] # Pop this menu off the active stack.

# -------------------------------------------------------------------------------------------------------------------------------- 

class optionmenu():
    """ Simple menu driver.
        Create a menu object.
        Give it a dictionary of menu items. Labels and the value to be returned for each item.
        Call the Prompt() method to execute the menu. 
        Menu quits when user selects 'x' option. 
        It returns the user's choice from the menu.
        It returns None if the user didn't select anything.
        
        dictionary format 
                {'menuitem1key':{'label':'menu item 1 label', 'bold':True/False, 'value': 'value1' to return, 'break': False},
                 'menuitem2key':{'label':'menu item 2 label', 'bold':True/False, 'value': 'value2' to return}
                }
                
                'docurl' = URL for help documentation about the menu option.
                'helpdoc' = Local text file location for help documentation about the menu option.
                'break' = Insert a blank line separator in the menu after the option.
                'value' = The value to return from the menu if option is selected.
                'bold' = Print the menu option in bold text.
                'label' = The label to appear in the menu.
                
                'id' is added automatically. It is the menu ID number.
                'enabled' is added automatically. It indicates that the menu option is currently visible and selectable.
                
        You can trigger user input via the Prompt() method.
        You can directly run a menu option without user input via the Run() method.
        """

    __version__ = '0.0.2'

    def __init__(self,dictionary,title='Options',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None,columns=2):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. 
            logger = pilomarlog.Log() instance (optional)
            columns = Initial number of columns to display the menu in.                        
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        self.Dictionary = dictionary
        self.Title = title
        self.IdWidth = 2
        self.LabelWidth = 26
        self.TitleFG = titlefg
        self.Columns = columns # How many columns to draw?
        self.Log = logger # Can define a logging function to use.
        if titlefg == None: self.TitleFG = textcolor.BLACK
        self.TitleBG = titlebg
        if titlebg == None: self.TitleBG = textcolor.YELLOW
        Counter = 0
        for key,value in self.Dictionary.items(): # Assign menu ID number to each entry.
            Counter += 1
            #print("Adding:",Counter,value)
            value['id'] = Counter
            value['enabled'] = True # All menu options are enabled and visible by default.
            self.LabelWidth = max(self.LabelWidth,len(value['label']))
        self.HelpDir = helpdir
        self.HelpUrl = helpurl

    def GetHelpFile(self,menuid):
        """ Given an ID number, retrieve and display the help text if it exists.                         
        
            Parameters ---------------------------------------
            menuid

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            filename (str)          """
        filename = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                filename = value.get('helpdoc',None) # Get the helpdoc filename.
                break # Look no further.
        if filename != None and self.HelpDir != None:
            filename = self.HelpDir + filename # Construct path to file.
        return filename
        
    def ShowHelpText(self,menuid):
        filename = self.GetHelpFile(menuid)
        if filename != None:
            try:
                with open(filename,'r') as f:
                    for line in f.readlines():
                        print (textcolor.cyan(line))
            except Exception as e:
                print(textcolor.red('Sorry, unable to show the help file.'))
                print(str(e))
        else:
            print (textcolor.red('Sorry, no help file is defined for menu item',menuid))
        
    def GetHelpUrl(self,menuid):
        """ Given an ID number, return URL associated with the help documentation.                         
        
            Parameters ---------------------------------------
            menuid

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            url (str)         """
        helpurl = None
        for key,value in self.Dictionary.items(): # Find entry with matching ID.
            if value['id'] == menuid: # Found a match.
                helpurl = value.get('helpurl',None) # Get the helpdoc helpurl.
                break # Look no further.
        if helpurl != None and self.HelpDir != None:
            helpurl = self.HelpDir + helpurl # Construct path to file.
        return helpurl
        
    def Draw(self,menuprefix=''):
        """ Draw the menu on the terminal.
            The menu list from the dictionary will automatically gain '?' and 'x' options too.                         
            
            Parameters ---------------------------------------
            menuprefix : str : Optional text to display before the menu title.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a          """
        # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
        count = 0
        print (textcolor.clearforward()) # Blank line before menu and clear everything below that.
        print (textcolor.fgbgcolor(self.TitleFG,self.TitleBG,' ' + menuprefix + self.Title + ' ')) # Menu title is painted in inverse colors. 
        for key,value in self.Dictionary.items(): # Go through each menu item in turn.
            if value['enabled'] == False: continue # Not visible or selectable, skip it.
            entry = textcolor.yellow(str(value['id']).rjust(self.IdWidth,' ')) + ' ' # ID number in yellow. 
            if value.get('color',None) != None: # Menu item has a specific label color.
                entry += value['color'](value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            elif value.get('bold',False): # If the menu item is in bold, make it so.
                entry += textcolor.white(value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            else: # Menu item is not in bold.
                entry += value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth]
            entry += ' ' # Space between columns of menu entries. 
            print (entry,end='') # Print the menu entry column, don't include 'newline' yet.
            count += 1 # Count how many entries.
            if count % self.Columns == 0: # Print 'newline' after 2nd column entry.
                print ('')
            if value.get('break',False): 
                if count % self.Columns != 0: # We're terminating the line early.
                    print ('')
                    count = 0
                print ('') # Insert a blank line break in the menu.
        if count % self.Columns != 0: # Print 'newline' if we didn't complete the 2nd column when the menu list ran out.
            print ('') # Terminate line if not already done.
        # Always include 'x' and '?' menu options automatically.
        print (textcolor.yellow('x'.rjust(self.IdWidth,' ')) + ' ' + 'Exit'.ljust(self.LabelWidth,' ')[:self.LabelWidth] + ' ',end='')
        print (textcolor.yellow('?'.rjust(self.IdWidth,' ')) + ' ' + 'Refresh'.ljust(self.LabelWidth,' ')[:self.LabelWidth])
        
    def Select(self,key):
        """ Given a menu option key, extract the selected value.                         
        
            Parameters ---------------------------------------
            key : str : Return a dictionary entry for the given key.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            dictionary value. """
        result = self.Dictionary[key]['value'] # What procedure is to be called?
        return result

    def ProcessHelpRequest(self,answer):
        """ Receive a text type menu id. 
            if it converts to an integer successfully, 
            show the help text associated with that menu item.                        
            
            Parameters ---------------------------------------
            answer : str : menu entry that needs help text displaying.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a           """
        answer = answer.replace('?','') # Remove any question mark.
        try:
            menuid = int(answer)
        except:
            menuid = None
        if menuid != None:
            self.ShowHelpText(menuid)
        
    def Prompt(self,menuprefix=''):
        """ Execute the menu. 
            This paints the menu on the terminal and deals with user selections. 
            Menu items are numbered dynamically, the user selects an item by selecting the number.
            
            If the user enters the number plus a '?' symbol then help text is displayed if it can be found.
            The method closes when the user selects the 'x' option. 
            '>' key makes the menu 1 column wider.
            '<' key makes the menu 1 column narrower.

            Return values are :
                result: Returns the option value that was chosen, or None if no option was chosen.
                found:  Returns TRUE if an option was selected, returns FALSE if nothing was chosen.

            Parameters ---------------------------------------
            menuprefix : str : Prefix displayed before menu title.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            n/a           """
        # Now paint the menu and ask the user what to do.
        self.Draw(menuprefix=menuprefix) # Paint the menu.
        result = None # The actual choice. None if nothing chosen.
        found = False # Set to True if a choice is successfully made, else False is returned.
        while True: # Loop until explicitly told to terminate.
            if self.Log != None: self.Log('Menu waiting for user input.',terminal=False)
            answer = input(textcolor.cyan('Choose option : ')) # Prompt for input.
            if self.Log != None: self.Log('Menu received user input',answer,'.',terminal=False)
            if answer == '?': # Refresh the menu.
                self.Draw() # Refresh the menu.
                continue
            if answer == ">": # Increase columns in display.
                self.Columns += 1
                self.Draw() # Refresh the menu.
                continue
            if answer == "<": # Increase columns in display.
                self.Columns -= 1
                self.Columns = max(self.Columns,1) # must be at least 1 column.
                self.Draw() # Refresh the menu.
                continue
            if '?' in answer: # User wants help about an option.
                self.ProcessHelpRequest(answer)
                continue # Prompt again.
            # Process menu choice.
            try: # Convert text into integer if possible.
                menuid = int(answer)
            except Exception:
                # Text would not convert into integer. 
                menuid = None
            if menuid != None: # 
                found = False # Have we found and executed the menu option?
                for key,value in self.Dictionary.items():
                    if value['enabled'] == False: continue # Not visible or selectable, skip it.
                    if value['id'] == menuid:
                        result = self.Select(key) # Choose the selected value to return.
                        found = True # We have found and selected the option.
                        break # Next
                if found: break
            if answer.lower() == '?': # Refresh option chosen.
                self.Draw() # Refresh the menu.
                continue # Next user input.
            if answer.lower() == 'x': # User chose to quit without selecting anything. Terminate the loop.
                found = None # Nothing was chosen.
                break # Go UP a level, quit if at root.
            # User input was not recognised. Try again.
            print (textcolor.red("'" + str(answer) + "' Unrecognised. Try again."))
        return result, found

# -------------------------------------------------------------------------------------------------------------------------------- 

class listchooser():
    """ Create a list of values and allow the user to select within that list.
        The search is recursive. 
        List entries are matched on anything containing the user's string. 
        If multiple entries remain, they are presented as a new list to choose from. 
        '?' to show list. 
        'x' to return to previous selection. """

    __version__ = '0.0.4'
        
    def __init__(self,inputlist,title=None,default=None,compress=True):
        self.FullList = inputlist
        self.Title = title
        self.Default = default
        self.Compress = compress # Long lists get compressed.
    
    def Print(self,inputlist,abbr_limit=10,sep=', '):
        """ Supports self.Filter() method. 
            Lists the choices to select from. 
            Abbreviates the list if > abbr_limit entries, otherwise shows them all.  
            
            Parameters ---------------------------------------
            inputlist : list : List of values to be chosen from.
            abbr_limit : int : Max number of entries to show, list is abbreviated after that.
            sep : str : Separator to use between entries in the list.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        printlist = ''
        if self.Compress and len(inputlist) > abbr_limit: # Big list and we're allowed to compress it.
            a = int(abbr_limit / 2)
            b = 0 - a
            for i in range(a):
                printlist += inputlist[i] + sep
            printlist += ' ... to ... '
            for i in range(b,0):
                printlist += sep + inputlist[i]
        else: # Short list or we're not allowed to compress it, so show everything.
            for i,n in enumerate(inputlist):
                if i > 0: printlist += sep
                printlist += n
        print(printlist)
        
    def Filter(self,inputlist):
        """ Recursive!!! 
            Receive a list of text items.
            User must select one of them.
            This lists the choices and lets the user narrow down the list if it's big.
            Returns when the user has selected a single item or decided to select nothing.                         
            
            Parameters ---------------------------------------
            inputlist : list : List of items to choose from.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            choice : str : Chosen value.
                     list : List of remaining values to choose from.
                            List is empty if nothing chosen. """
        #choice = []
        while True:
            choice = []
            self.Print(inputlist)
            inputtext = input(textcolor.cyan("Choice ('x' to return) : "))
            inputtext = inputtext.lower()
            if inputtext == 'x': break # Quit.
            if len(inputtext) < 1: continue # Nothing to check, ask again.
            for i in inputlist:
                if inputtext in i.lower(): choice.append(i)
                if inputtext == i.lower(): 
                    choice = [i] # Exact match.
                    break # Look no further.
            if len(choice) < 1: 
                print(textcolor.red("'" + inputtext + "' is not in the list."))
                continue # Nothing matched, ask again.
            if len(choice) > 1 and choice != inputlist: choice = self.Filter(choice) # Refine the list further. Recursion.
            if len(choice) == 1: break # Choice made, return.
        return choice

    def Prompt(self):
        """ Receive a list and return the user's selection or None value.                         
        
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            Selection : str or None          """
        result = self.Filter(self.FullList)
        if len(result) == 0: result = None # Return None value, nothing chosen. 
        elif len(result) == 1: result = result[0] # Strip the list structure off.
        # In all other cases return the selected list.
        return result
    
# -------------------------------------------------------------------------------------------------------------------------------- 

class filechooser():
    """ Allow a user to browse and select a file from disc. 
    
        Define where you want to start the search. 
        User selects a file from there, or navigates the directory structure.
        
        Returns the chosen file and a 'success' flag. 
        
        Example ------------------------------------------------------
        FC = filechooser(title='Choose an image file',default='/home/pi/pilomar/data/',types=['jpg','jpeg'])
        chosen_file, success = FC.ChooseFile()
        if success: 
            print("Chose",chosen_file)
        else:
            print("No file chosen")
            
        """
    
    def __init__(self,title,default=None,types=None):
        """ Create instance of file chooser.
        
            Parameters ---------------------------------------
            title : Title for selection.
            default : Default location to open browser.
                      If NONE: pwd is used.
                      If folder is not found, the parent is chosen.
            types : optional list of file types.
                    If NONE: All files are listed.                         
                        

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            n/a          """
        self.Title = title
        self.DefaultDir = default
        self.CurrentDir = default
        self.FileTypes = types

    def ToPathType(self,filepath):
        """ Make sure filepath is a Path type.
            When referring to file and folder names in the code it is easy to confuse string and Path objects.
            This makes sure that you are always using a Path object by converting string values to Path objects.                         
            
            Parameters ---------------------------------------
            filepath : str or Path datatype.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            filepath : Path datatype.           """
        if type(filepath) != Path:
            filepath = Path(filepath)
        return filepath
    
    def PathExists(self,folderpath):
        """ Return TRUE if a path exists. Else False.                         
        
            Parameters ---------------------------------------
            folderpath

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result (bool)         """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.exists()
        
    def NameOnly(self,folderpath):
        """ Strip full path, return only the name of the file.                         
        
            Parameters ---------------------------------------
            folderpath

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            filename          """        
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.name

    def IsFile(self,folderpath):
        """ Return TRUE if a path points to a file. Else False.                         
        
            Parameters ---------------------------------------
            folderpath

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result (boolean)         """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.is_file()

    def IsDir(self,folderpath):
        """ Return TRUE if a path points to a file. Else False.                        
        
            Parameters ---------------------------------------
            folderpath

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result (boolean)           """
        folderpath = self.ToPathType(folderpath) # Convert to Path object.
        return folderpath.is_dir()
        
    def GetParent(self,filepath):
        """ Return PARENT of a folder.
            Parameters ---------------------------------------
            filepath

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            filepath          """

        filepath = self.ToPathType(filepath)        
        return filepath.parent
        
    def IsType(self,filepath, filetype, casesensitive=False):
        """ Return TRUE if the path is a file matching filetype. 
            filepath is the path to check.
            filetype can be a single value or a list that must be matched.
            casesensitive controls whether case must match. 
            File does not need to exist on disc.                         
            
            Parameters ---------------------------------------
            filepath
            filetype : list of str filetypes.
            casesensitive : boolean : Case sensitive or not?

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result (boolean)          """
        if type(filetype) == str: filetype = [filetype] # Convert to list in all cases.
        filepath = self.ToPathType(filepath) # Convert to Path object.
        foundtype = filepath.suffix.replace('.','') # Get suffix (file type) and drop the '.' separator.
        result = False 
        if casesensitive: # Perform case sensitive match.
            if foundtype in filetype: # We found a match.
                result = True
        else: # Not case sensitive.
            filetype = [ft.lower() for ft in filetype] # Convert to lower case.
            if foundtype.lower() in filetype:
                result = True
        return result

    def VerifyFolder(self,folder=None):
        """ Given a folder name, make sure it exists, if it doesn't return the closest parent. 
            If none exist, return home directory.                         
            
            Parameters ---------------------------------------
            folder : str (folder name)

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------

            Returns ------------------------------------------
            result (boolean)          """
        if folder == None: 
            folder = Path.home() # returns user's home directory
        folder = self.ToPathType(folder)
        keeplooking = True # Keep searching for a valid path?
        while keeplooking:
            if self.PathExists(folder) and self.IsDir(folder): # Found valid folder.
                keeplooking = False
                break
            # This isn't valid, try parent.
            try:
                folder = folder.parent
            except:
                folder = None
                break
        if folder == None: 
            folder = Path.home() # returns user's home directory
        return folder
    
    def FileList(self,show_files=True,show_folders=True,must_exist=True):
        """ Return dictionary of files and subfolders in current folder. 
            
            The list is sorted,
              1st entry is always the parent directory. 
              2nd set of entries are always the sub-directories. 
              3rd set of entries are the files. 
              directory and file groups are alphabetically sorted.                         
            
            Parameters ------------------------------------------------------
            show_files : True - will list files found.
            show_folders : True - will list folders found.
            must_exist : True - can only select existing files.
                         False - user can enter a filename that does not exist.

            References ---------------------------------------
            n/a

            Sets ---------------------------------------------
            n/a

            Returns ------------------------------------------
            Dictionary list of files and folders identified.  """
        self.CurrentDir = self.VerifyFolder(self.CurrentDir)
        dirs = []
        files = []
        result = {}
        if show_folders: result[".."] = {'value':str(self.GetParent(self.CurrentDir)), 'label':'..', 'type':'dir', 'color':textcolor.cyan} # Always allow UP to parent.
        for root, dirs, files in os.walk(str(self.CurrentDir)):
            if show_folders:
                for entry in sorted(dirs):
                    fn = entry.split("/")[-1]
                    result[fn] = {'value':root + "/" + entry, 'label':fn, 'type':'dir', 'color':textcolor.cyan} # Folders show in CYAN.
            if show_files:
                for entry in sorted(files):
                    fn = entry.split("/")[-1]
                    ty = fn.split(".")[-1] # Get file type.
                    filepath = root + "/" + entry
                    if self.FileTypes == None or self.IsType(filepath, self.FileTypes, casesensitive=False):
                        result[fn] = {'value':filepath, 'label':fn, 'type':'file'}
            break
        if not must_exist:
            result['+'] = {'value':'+', 'label':'New file', 'type':'file', 'color':textcolor.yellow} # NEW file option is in YELLOW.
        return result

    def ChooseFile(self):
        """ Use the listchooser class to present a list of files and folders, 
            let the user select one.
            User can navigate up/down directory tree looking for appropriate files.
            
            Parameters ---------------------------------------
            n/a

            References ---------------------------------------
            self.CurrentFile

            Sets ---------------------------------------------

            Returns ------------------------------------------
            chosen_file (str) : Full path to chosen file.
                          None if nothing selected.
            found (bool) : True if file chosen.
                    False if file was not found.
                    None if user quit without choosing anything.                        """
        chosen_file = None
        found = False
        title = self.Title 
        if type(self.FileTypes) == list and len(self.FileTypes) > 0:
            title = (title + " " + str(self.FileTypes)).strip()
        while chosen_file == None:
            options = self.FileList() # List all the files and subfolders in the chosen directory.
            OptionMenu = optionmenu(options,title) # Create new option menu for the current directory.
            chosen_file, found = OptionMenu.Prompt() # Ask the user to select a file from the list.
            # chosen_file = full path chosen.
            # found = Was a choice made?
            if found and self.IsDir(chosen_file): # Directory
                self.CurrentDir = chosen_file # Switch to chosen directory
                chosen_file = None
                continue # Try again.
            if found and chosen_file == '+': # User can create new file here.
                tf = input(textcolor.cyan("Enter filename:")).trim()
                if tf == '': # Nothing entered.
                    chosen_file = None
                    continue # Try again.
                chosen_file = self.CurrentDir + "/" + tf
            #print("ChosenItem:",chosen_file,found)
            break # The choice is made.
        return chosen_file, found
        
# -------------------------------------------------------------------------------------------------------------------------------- 

if __name__ == "__main__": # Example display.
    textcolor.listcolors()
    