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
from datetime import datetime
import traceback # For exception handling in menu.
import json # To dump dictionaries for export.

class keyboardscanner():
    """ Use curses library to scan the keyboard (non-blocking).
        Example: if keyboardscanner.Check().lower() == "x": break
    """
    
    __version__ = '0.0.1'
    
    def __init__(self):
        self.CurrentKeyCode = -1
        self.CurrentCharacter = ''

    def Scan(self,stdscr):
        """ Non-blocking check for keypress. """
        stdscr.nodelay(True)  # do not wait for input when calling getch
        self.CurrentKeyCode = stdscr.getch()
        self.CurrentCharacter = ''
        if self.CurrentKeyCode > -1:
            self.CurrentCharacter = chr(self.CurrentKeyCode)

    def Check(self):
        curses.wrapper(self.Scan)
        return self.CurrentCharacter
        
    def Flush(self):
        """ Flush any pending keypresses from the buffer. """
        while self.Check() != '': pass

# ------------------------------------------------------------------------------------------------

class textcolor:
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

    __version__ = '0.0.6'
    TermType = None
    Mode = 'putty' # 'putty' = full colour remote terminal, 'simple' = No colour, 'local' = Direct connection colour.
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
    SPRINGGREEN2 = 47
    SPRINGGREEN1 = 48
    MEDIUMSPRINGGREEN = 49
    CYAN2 = 50
    CYAN1 = 51
    DARKRED = 52
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
    STEELBLUE1 = 81
    CHARTREUSE2 = 82
    SEAGREEN2 = 83
    SEAGREEN1 = 84
    SEAGREEN1A = 85
    AQUAMARINE1 = 86
    DARKSLATEGRAY2 = 87
    DARKRED = 88
    DEEPPINK4 = 89
    DARKMAGENTA = 90
    DARKMAGENTAA = 91
    DARKVIOLET = 92
    PURPLE = 93
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
    YELLOW4 = 106
    DARKOLIVEGREEN3 = 107
    DARKSEAGREEN = 108
    LIGHTSKYBLUE3 = 109
    LIGHTSKYBLUE3A = 110
    SKYBLUE2 = 111
    CHARTREUSE2 = 112
    DARKOLIVEGREEN3A = 113
    PALEGREEN3 = 114
    DARKSEAGREEN3 = 115
    DARKSLATEGRAY3 = 116
    SKYBLUE1 = 117
    CHARTREUSE1 = 118
    LIGHTGREEN = 119
    LIGHTGREENA = 120
    PALEGREEN1 = 121
    AQUAMARINE1 = 122
    DARKSLATEGRAY1 = 123
    RED3 = 124
    DEEPPINK4 = 125
    MEDIUMVIOLETRED = 126
    MAGENTA3 = 127
    DARKVIOLET = 128
    PURPLE = 129
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
    MEDIUMPURPLE2 = 140
    MEDIUMPURPLE1 = 141
    GOLD3 = 142
    DARKKHAKI = 143
    NAVAJOWHITE3 = 144
    GREY69 = 145
    LIGHTSTEELBLUE3 = 146
    LIGHTSTEELBLUE = 147
    YELLOW3 = 148
    DARKOLIVEGREEN3 = 149
    DARKSEAGREEN3A = 150
    DARKSEAGREEN2 = 151
    LIGHTCYAN3 = 152
    LIGHTSKYBLUE1 = 153
    GREENYELLOW = 154
    DARKOLIVEGREEN2 = 155
    PALEGREEN1 = 156
    DARKSEAGREEN2A = 157
    DARKSEAGREEN1 = 158
    PALETURQUOISE1 = 159
    RED3A = 160
    DEEPPINK3 = 161
    DEEPPINK3A = 162
    MAGENTA3 = 163
    MAGENTA3A = 164
    MAGENTA2 = 165
    DARKORANGE3 = 166
    INDIANRED = 167
    HOTPINK3 = 168
    HOTPINK2 = 169
    ORCHID = 170
    MEDIUMORCHID1 = 171
    ORANGE3 = 172
    LIGHTSALMON3 = 173
    LIGHTPINK3 = 174
    PINK3 = 175
    PLUM3 = 176
    VIOLET = 177
    GOLD3 = 178
    LIGHTGOLDENROD3 = 179
    TAN = 180
    MISTYROSE3 = 181
    THISTLE3 = 182
    PLUM2 = 183
    YELLOW3 = 184
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
    MAGENTA2 = 200
    MAGENTA1 = 201
    ORANGERED1 = 202
    INDIANRED1 = 203
    INDIANRED1A = 204
    HOTPINK = 205
    HOTPINKA = 206
    MEDIUMORCHID1 = 207
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
    LIGHTGOLDENROD2 = 221
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
    SYMBOLS = {'left' : '\u2190', 'right' : '\u2192', 'up' : '\u2191', 'down' : '\u2193', 
               'degree' : '\u00B0', 'delta' : '\u0394', 
               'horizontal' : '\u2500', 'vertical' : '\u2502', 'corner_tl' : '\u250c', 'corner_tr' : '\u2510', 'corner_bl' : '\u2514', 'corner_br' : '\u2518', 'crossover' : '\u253c',
               'left_junction' : '\u2524', 'right_junction' : '\u251c', 'top_junction' : '\u2534', 'bottom_junction' : '\u252c',
               'sun' : '\u2609', 'moon' : '\u263D', 'mercury' : '\u263F', 'venus' : '\u2640', 'earth' : '\u2641', 'mars' : '\u2642', 'jupiter' : '\u2643', 'saturn' : '\u2644', 'uranus' : '\u2645', 'neptune' : '\u2646', 'pluto' : '\u2647', 'comet' : '\u2604', 'star' : '\u2736'
              }

    @staticmethod
    def TextBox(linelist,row=None,col=None,fg=None,bg=None,textfg=None,textbg=None,borderfg=None,borderbg=None,minwidth=None,justify=None):
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
            - justify = 'l'(left),'c'(center),'r'(right) """
        if type(linelist) != type([]): linelist = [linelist] # Convert single values to list for simpler processing.
        if justify != None: justify = justify[0].lower() # standardise code.
        # Convert embedded newline characters into separate list elements.
        templinelist = []
        for line in linelist: # Read all the input lines.
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
        for i,line in enumerate(printlines): # Now display the whole box.
            if row != None and col != None: line = textcolor.cursor(col=col,row=row + i) + line # Add screen location (row and column).
            elif col != None: line = textcolor.cursorright(cols=col) + line # Add screen location (column only).
            print(line)

    @staticmethod
    def ListSymbols():
        for key,value in textcolor.SYMBOLS.items():
            print (key, value)
        
    @staticmethod
    def safetype(raw):
        if type(raw) != type(str): raw = str(raw)
        return raw     

    @staticmethod
    def booltocolor(value,fgtrue=None,fgfalse=None):
        """ Given a boolean (or text) value, return it as colored text. 
            True values are colored fgtrue color. 
            False valuse are colored fgfalse color. 
            None values are not colored. """
        if fgtrue == None: fgtrue = textcolor.GREEN
        if fgfalse == None: fgfalse = textcolor.RED
        temp = str(value)
        temp = temp.replace("True",textcolor.fgbgcolor(fgtrue,textcolor.BLACK,"True"))
        temp = temp.replace("False",textcolor.fgbgcolor(fgfalse,textcolor.BLACK,"False"))
        return temp

    @staticmethod
    def listtotext(arglist,sep=' '):
        """ Given a list of arguments, append all of them into a single string.
            This behaves like the 'print' command for stringing together a list of items
            into a single string. All arguments are converted to 'str' type before adding
            to the output string. 
            sep parameter says what separator is inserted between each element. (default ' ') """
        result = ''
        for a in arglist:
            if a != '':
                if result != '': result += sep
                result += str(a)
        return result

    @staticmethod
    def neatprint(*args,**kwargs):
        """ Own 'print' function. 
            Formats neatly in early Python versions. """
        if True: # Output to terminal/stdout.
            line = ''
            for a in args:
                a = textcolor.safetype(a)
                if len(line) > 0: line += ' '
                line += a
            print(line)
        else: # Suppress output.
            pass

    @staticmethod
    def getterminalsize(): # Common
        """ Return tuple of the current screen dimensions. 
              (cols,rows) """
        print('textcolor.getterminalsize() is deprecated in favour of textcolor.terminalsize()')
        cols = 80
        rows = 24
        cols = int(textcolor.oscommand('tput cols')[0])
        rows = int(textcolor.oscommand('tput lines')[0])
        return (cols,rows)

    @staticmethod
    def HRNumber(value,base=1000,decimals=1):
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
    def stripcodes(line):
        """ Remove embedded terminal display codes from a line of text.
            Removes any text starting with "\033[" up to the first letter. (A-Z,a-z) """
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
    def oscommand(cmd): # Common
        """ Execute a command,result is returned as clean list of lines. """
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
        """ Return the termtype and also set the global variable TermType. """
        textcolor.TermType = textcolor.oscommand('echo $TERM')[0]
        return textcolor.TermType

    @staticmethod
    def terminalsize(): # Common
        """ Return tuple of the current screen dimensions (in characters) = (cols,rows) """
        cols = 80
        rows = 24
        cols = int(textcolor.oscommand('tput cols')[0])
        rows = int(textcolor.oscommand('tput lines')[0])
        return (cols,rows)

    @staticmethod
    def hidecursor(): # Common
        """ Make the cursor invisible. """
        textcolor.oscommand('tput civis')

    @staticmethod
    def showcursor(): # Common
        """ Make the cursor visible. """
        textcolor.oscommand('tput cnorm')

    @staticmethod
    def cursorhome():
        return textcolor.cursor(0,0)

    @staticmethod
    def cursor(col=0,row=0):
        return "\033[" + str(row) + ";" + str(col) + "H"

    @staticmethod
    def cursorup(rows=1):
        return "\033[" + str(rows) + "A"

    @staticmethod
    def cursordown(rows=1):
        return "\033[" + str(rows) + "B"

    @staticmethod
    def cursorleft(cols=1):
        return "\033[" + str(cols) + "D"

    @staticmethod
    def cursorright(cols=1):
        return "\033[" + str(cols) + "C"

    @staticmethod
    def nextline(rows=1):
        return "\033[" + str(rows) + "E"

    @staticmethod
    def prevline(rows=1):
        return "\033[" + str(rows) + "F"

    @staticmethod
    def clearlineforward():
        return "\033[0K"

    @staticmethod
    def clearlinebackward():
        return "\033[1K"

    @staticmethod
    def clearline():
        return "\033[2K"

    @staticmethod
    def clearforward():
        return "\033[0J"

    @staticmethod
    def clearbackward():
        return "\033[1J"

    @staticmethod
    def clearall():
        return "\033[2J"

    @staticmethod
    def clearscreen():
        return textcolor.cursorhome() + textcolor.clearall()

    @staticmethod
    def reset(text=""):
        return "\033[0m" + text

    @staticmethod
    def color(value=7,text=''):
        """ 256 colour mode supported. """
        if textcolor.Mode == 'simple':
            return text
        else:
            return "\033[38;5;" + str(value) + "m" + text + textcolor.reset()

    @staticmethod
    def truecolor(r,g,b,text=''):
        """ Truecolor colour mode supported. """
        if textcolor.Mode == 'simple':
            return text
        else:
            return "\033[38;2;" + str(r)+ ";" + str(g) + ";" + str(b) + "mtext\033[0m" + text + textcolor.reset()

    @staticmethod
    def bgcolor(value=0,text=''):
        """ 256 colour mode supported."""
        if textcolor.Mode == 'simple':
            return text
        else:
            return "\033[48;5;" + str(value) + "m" + text + textcolor.reset()

    @staticmethod
    def rgbassign(r):
        """ change r(or g or b) value from 0.0-1.0 range into 0-5 range
            This assigns the 0-5 range more evenly depending upon the input 0.0-1.0 value. """
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
            method parameter allows for alternative calculations.        """
        # 0.0 = Level 0
        # 1.0 = Level 5
        #re = round(r * 5)
        #ge = round(g * 5)
        #be = round(b * 5)
        re = textcolor.rgbassign(r)
        ge = textcolor.rgbassign(g)
        be = textcolor.rgbassign(b)
        v = int(re * 6 * 6) + int(ge * 6) + int(be) + 16
        return v
        
    @staticmethod
    def rgbditherdecimal(r,g,b):
        """ Take rgb values (scale 0.00-1.00) and calculate 2 nearest 215 color scheme values. 
            This is to support using 'dithering' to match colors better.
            Returns 2 colors.            """
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
        """ Take RGB values (scale 0-5) and calculate nearest 256 color scheme value. """
        v = (r * 6 * 6) + (g * 6) + b + 16
        v = v % 256 # Clip for safety.
        return v

    #@staticmethod
    #def fgbgcolorxxx(fg=7,bg=0,text='',reset=True):
    #    """ 256 colour mode supported. 
    #        if reset=True, the color is stopped at the end of the text. 
    #        if reset=False, the color setting remains active after the text. """
    #    print ('fgbgcolorxxx is a depricated version of fgbgcolor()')
    #    if textcolor.Mode == 'simple':
    #        return text
    #    else:
    #        if reset: 
    #            return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text + textcolor.reset() # Stop using this color after the text.
    #        else:
    #            return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text # Leave the color active.

    @staticmethod
    def fgbgcolor(fg=7,bg=0,*args,sep=' ',reset=True):
        """ 256 colour mode supported. 
            fg = foreground color (0-255)
            bg = background color (0-255)
            args = unlimited comma separated list of items to print.
            sep = ' ' separator placed between each argument when printed.
            if reset=True, the color is stopped at the end of the text. 
            if reset=False, the color setting remains active after the text. """
        text = textcolor.listtotext(args,sep=sep)
        if textcolor.Mode == 'simple':
            return text
        else:
            if reset: 
                return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text + textcolor.reset() # Stop using this color after the text.
            else:
                return "\033[38;5;" + str(fg) + "m" + "\033[48;5;" + str(bg) + "m" + text # Leave the color active.

    @staticmethod
    def listcolors():
        """ List all colours available. """
        # First list on BLACK background.
        for i in range(0, 16):
            line = ""
            for j in range(0, 16):
                code = i * 16 + j
                line += textcolor.fgbgcolor(code, 0, str(code).rjust(4))
            print (line)
        # Second show BLACK characters on coloured background.
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
    def opposite(colnum,color=False):
        """ Return an opposing color to the proposed one. 
            color = True: Return the 'negative' color. 
            coloer = False: Return BLACK or WHITE. """
        # *Q* Not finished yet.
        if colnum == textcolor.BLACK: oppcol = textcolor.WHITE
        else: oppcol = textcolor.BLACK
        return oppcol

    @staticmethod
    def black(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.WHITE,textcolor.BLACK,text)
        else:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.WHITE,text)

    @staticmethod
    def red(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.RED,text)
        else:
            return textcolor.fgbgcolor(textcolor.RED,textcolor.BLACK,text)

    @staticmethod
    def green(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.GREEN,text)
        else:
            return textcolor.fgbgcolor(textcolor.GREEN,textcolor.BLACK,text)

    @staticmethod
    def yellowxxx(text="",invert=False):
        print('yellowxxx is a depricated version of yellow()')
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.YELLOW,text)
        else:
            return textcolor.fgbgcolor(textcolor.YELLOW,textcolor.BLACK,text)

    @staticmethod
    def yellow(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.YELLOW,text)
        else:
            return textcolor.fgbgcolor(textcolor.YELLOW,textcolor.BLACK,text)

    @staticmethod
    def yellow4(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.YELLOW4,text)
        else:
            return textcolor.fgbgcolor(textcolor.YELLOW4,textcolor.BLACK,text)

    @staticmethod
    def orange(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.ORANGE1,text)
        else:
            return textcolor.fgbgcolor(textcolor.ORANGE1,textcolor.BLACK,text)

    @staticmethod
    def blue(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.BLUE,text)
        else:
            return textcolor.fgbgcolor(textcolor.BLUE,textcolor.BLACK,text)

    @staticmethod
    def magenta(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.MAGENTA,text)
        else:
            return textcolor.fgbgcolor(textcolor.MAGENTA,textcolor.BLACK,text)

    @staticmethod
    def cyan(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.CYAN,text)
        else:
            return textcolor.fgbgcolor(textcolor.CYAN,textcolor.BLACK,text)

    @staticmethod
    def aqua(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.AQUA,text)
        else:
            return textcolor.fgbgcolor(textcolor.AQUA,textcolor.BLACK,text)

    @staticmethod
    def navy(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.NAVY,text)
        else:
            return textcolor.fgbgcolor(textcolor.NAVY,textcolor.BLACK,text)

    @staticmethod
    def teal(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.TEAL,text)
        else:
            return textcolor.fgbgcolor(textcolor.TEAL,textcolor.BLACK,text)

    @staticmethod
    def white(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        if invert:
            return textcolor.fgbgcolor(textcolor.BLACK,textcolor.WHITE,text)
        else:
            return textcolor.fgbgcolor(textcolor.WHITE,textcolor.BLACK,text)

    @staticmethod
    def bold(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        return "\033[1m" + text + textcolor.reset()

    @staticmethod
    def underline(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        return "\033[4m" + text + textcolor.reset()

    @staticmethod
    def blink(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        return "\033[5m" + text + textcolor.reset()

    @staticmethod
    def framed(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args,sep=sep)
        return "\033[51m" + text + textcolor.reset()

    @staticmethod
    def reversed(*args,sep=' ',invert=False):
        text = textcolor.listtotext(args)
        return "\033[7m" + text + textcolor.reset()

# ------------------------------------------------------------------------------------------------

class cdsprite():
    """ This is a subclass of the colordisplay class.
        It represents 'sprites' that can be defined to move across the colordisplay buffer. 
        Originally intended to create moving markers against a set background grid. """
        
    __version__ = '0.0.1'
        
    def __init__(self,name,symbol,row=None,col=None,fg=0,bg=15,level=0):
        self.row = row
        self.column = col
        self.fg = fg
        self.bg = bg
        self.symbol = symbol
        self.name = name
        self.display = False
        self.level = level

    def ColoredSymbol(self):
        """ Return symbol with embedded terminal colour codes set. """
        result = result = textcolor.fgbgcolor(self.fg,self.bg,self.symbol)
        return result
        
    def Label(self,color=False):
        """ Return colour coded label for the sprite. 
            Used in the key to a display.
            color=False means color is not set, plaintext is returned instead. """
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
        self.DefaultFG = fg # What's the default foreground colour?
        self.DefaultBG = bg # What's the default background colour?
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
        """ Set selected refresh rate and reset the refresh timer. """
        self.RefreshRate = rate
        self.LastRefresh = None
        
    def RefreshDue(self):
        """ Return True if refresh is due, else False. """
        result = False
        if self.RefreshRate == None: result = True # There's no restriction so always refresh. 
        elif self.LastRefresh == None: result = True # Need to do initial drawing. 
        elif (datetime.now() - self.LastRefresh).total_seconds() >= self.RefreshRate: result = True # Refresh is due.
        return result 
        

    def Clear(self,immediate=False):
        """ Clear the window. """
        self.Lines = []
        if self.Title != None: self.Lines.append(' ')
        if immediate: self.Display()

    def Display(self,screenheight=None,screenwidth=None,immediate=False):
        """ Display the window.
            If specific location has been given for the window AND the current screen size is given in screenheight/screenwidth
            this can check that the space exists in the current display size. It will only draw the window if there is enough space. """
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

    def Print(self,*args):
        line = ''
        for i in args:
            if len(line) > 0: line += ' '
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
        self.LetterDictionary = {}
        self.InitialiseLD()
        
    def InitialiseLD(self):
        self.LetterDictionary = {}
        self.LetterDictionary['unknown'] = ["#####","# # #","## ##","# # #","#####"]
        self.LetterDictionary[' '] = ["     ","     ","     ","     ","     "]
        self.LetterDictionary['"'] = [" # # "," # # ","     ","     ","     "]
        self.LetterDictionary["'"] = ["  #  ","  #  ","     ","     ","     "]
        self.LetterDictionary['0'] = ["#####","#  ##","# # #","##  #","#####"]
        self.LetterDictionary['1'] = ["   # ","  ## ","   # ","   # "," ####"]                                      
        self.LetterDictionary['2'] = ["#####","    #","#####","#    ","#####"]                                      
        self.LetterDictionary['3'] = ["#####","    #","#####","    #","#####"]                                      
        self.LetterDictionary['4'] = ["#   #","#   #","#####","    #","    #"]                                      
        self.LetterDictionary['5'] = ["#####","#    ","#####","    #","#####"]                                      
        self.LetterDictionary['6'] = ["#####","#    ","#####","#   #","#####"]                                      
        self.LetterDictionary['7'] = ["#####","    #","    #","    #","    #"]                                      
        self.LetterDictionary['8'] = ["#####","#   #","#####","#   #","#####"]                                      
        self.LetterDictionary['9'] = ["#####","#   #","#####","    #","    #"]                                      
        self.LetterDictionary['.'] = ["     ","     ","     ","     ","  #  "]                                      
        self.LetterDictionary[','] = ["     ","     ","     ","  ## ","   # "]                                      
        self.LetterDictionary[':'] = ["     ",
                                      "  #  ",
                                      "     ",
                                      "  #  ",
                                      "     "]                                      
        self.LetterDictionary['!'] = ["  #  ",
                                      "  #  ",
                                      "  #  ",
                                      "     ",
                                      "  #  "]                                      
        self.LetterDictionary['-'] = ["     ",
                                      "     ",
                                      " ### ",
                                      "     ",
                                      "     "]                                      
        self.LetterDictionary['+'] = ["     ",
                                      "  #  ",
                                      " ### ",
                                      "  #  ",
                                      "     "]                                      
        self.LetterDictionary['*'] = ["  #  ",
                                      "# # #",
                                      " ### ",
                                      " # # ",
                                      "#   #"]                                      
        self.LetterDictionary['='] = ["     ",
                                      " ### ",
                                      "     ",
                                      " ### ",
                                      "     "]                                      
        self.LetterDictionary['?'] = [" ### ",
                                      "#   #",
                                      "  ## ",
                                      "     ",
                                      "  #  "]                                      
        #for key,item in self.LetterDictionary.items():
        #    # item is a list of 5 lines. Convert the '#' characters into BLOCKS.
        #    newitem = []
        #    for lineitem in item:
        #        newline = ''
        #        for i in range(len(lineitem)):
        #            if lineitem[i] == ' ': newline += ' '
        #            else: newline += '\u2588'
        #        newitem.append(newline)
        #    self.LetterDictionary[key] = newitem

    def GetLetter(self,letter):
        """ Return letter pattern. """
        if letter in self.LetterDictionary: return self.LetterDictionary[letter]
        else: return self.LetterDictionary['unkown']
        
    def GenerateText(self,originaltext):
        """ Given original text, generate the BigLetters version of it. """
        lines = [[] for i in range(5)] # Create 5 empty lines.
        for character in originaltext:
            LD = self.GetLetter(character) # Returns 5 character lines.
            for i,LL in enumerate(LD): # Parse each line in turn.
                lines[i].append(LL + ' ')
        return lines
                                      
# -------------------------------------------------------------------------------------------------------------------------------- 

class field():
    """ A data field in a colordisplay window.

        Field can be regular data fields or progress bars. """
    
    __version__ = '0.0.2'
    
    def __init__(self,name,row,col,length=10,justify='l'):
        """ justify = 'l' left, 'r' right. """
        # Common attributes
        self.Name = name
        self.Row = row
        self.Column = col
        self.Length = length
        self.Value = None
        self.Justify = justify # 'left','centre','right'
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
        self.BlinkColors = [[textcolor.WHITE,textcolor.BLACK],[textcolor.RED,textcolor.BLACK]] # FG/BG pairs to alternate between when blinking.
        
    def Justified(self):
        sval = str(self.Value) # Convert to string.
        jcode = self.Justify[0].lower()
        if len(sval) < self.Length: # Does the field need padding?
            if jcode == 'r': sval = sval.strip().rjust(self.Length)
            elif jcode == 'c': sval = sval.strip().center(self.Length)
            else: sval = sval.strip().ljust(self.Length)
        return sval

# -------------------------------------------------------------------------------------------------------------------------------- 

class colordisplay():
    """ Class to create a coloured character display buffer, and to display on the terminal as needed.
        Can operate as addressible screen space, or
        can operate as simple scrolling text windows.
        Supports sprites.
        Supports labelled data fields. """
    
    __version__ = '0.0.6'
    DefinedWindows = [] # Handles of all defined windows. Useful for scanning/updating all available windows.
                        # The defining class contains some methods which can perform general updates via this list.
    CDLayout = [] # Array of major rows/columns that colordisplay instances can self-align with.
                  # Each entry defines a high level 'column' of colordisplay locations. [[fromcol,colwidth],[fromcol,colwidth],...]
                  # When defining new colordisplay instances you can then just refer to these columns rather than tailoring the coordinates of each individual window.

    @staticmethod
    def AddCDEntry(colwidth,startcol=None):
        """ Add new entry to the colordisplay.CDLayout list.
            You must assign colwidth, but startcol is optional.
            If startcol is not specified, the next available one is assigned. """
        if startcol == None: # Starting column isn't specified, so calculate the next available one.
            startcol = 1 # Find the next free one. 1st column if nothing exists yet.
            for cd in colordisplay.CDLayout: # Check each layout already defined.
                temp = cd[0] + cd[1]
                if temp >= startcol: startcol = temp + 1 # Start at next free column (with 1 space for border).
        startcol = max(startcol,1) # Must be at least 1 (1st column)
        colordisplay.CDLayout.append([startcol,colwidth])
        return True
    
    def __init__(self,rows,columns=None,name='',row=None,col=None,fg=15,bg=0,FirstScrollRow=0,title=None,titlefg=None,titlebg=None,borderfg=None,borderbg=None,cdlayout=None):
        """ fg and bg parameters can be single integer value (0-255) or a list of values [(0-255),(0-255),..] 
            The Print() method will cycle through the colors if lists are given. 
            Other modes operate with just the first given fg and bg values, the rest of any lists are ignored. 
            rows = Number of ROWS in the window.
            columns = Number of COLUMNS in the window.
            row = Display ROW number where window starts.
            col = Display COLUMN number where window starts.
            fg = Foreground. Single color code (0-255) or list of values to cycle through.
            bg = Background. Single color code (0-255) of list of values to cycle through.
            FirstScrollRow = When printing to window, this is the first row that will scroll up as new lines are printed. (allows titles to stay fixed etc)
            title = Window title.
            titlefg = Title foreground. Single color code (0-255). None will use window bg value.
            titlebg = Title background. Single color code (0-255). None will use window fg value. 
            cdlayout = index of the colordisplay.CDLayout list. A shortcut to set col and or row values more dynamically.
            -------------------------
            After instantiation, you can also set self.ClipWindow = True to allow the window to truncate display if insufficient realestate available.
               Otherwise the entire window will be suppressed until the display is big enough to accomodate the entire window. """
        self.DisplayName = name # A label for the display instance.
        if columns == None and cdlayout == None:
            raise Exception("colordisplay.__init__(): You must specify columns or cdlayout parameter to define a window.")
        if self.DisplayName == '':
            self.DisplayName = "win_" + str(len(colordisplay.DefinedWindows)) # Generate a default name.
        self.DisplayRows = rows # How many rows deep is the display?
        self.CDEntry = cdlayout # If using predefined columns, make a note which one we're using.
        if self.CDEntry != None and self.CDEntry >= 0 and self.CDEntry < len(colordisplay.CDLayout): # Automatically assign location on the screen.
            # Use the CDLayout list of window columns to define the start column.
            col = colordisplay.CDLayout[self.CDEntry][0] # Pull the start character column from the CDLayout list.
            columns = colordisplay.CDLayout[self.CDEntry][1] # Pull the character column width from the CDLayout list.
            row = 1
            for cd in colordisplay.DefinedWindows: # Stack each new window beneath previous ones in a column.
                if cd.CDEntry == self.CDEntry and cd.LastDisplayRow >= row: row = cd.LastDisplayRow + 2 # Start at next free row (with 1 row for border).
        self.DisplayColumns = columns # How many columns wide is the display?
        self.DisplayRow = row # What's the location of the 1st cell in the display on the actual terminal?
        self.DisplayCol = col
        if self.DisplayRow != None and self.DisplayRows != None:
            self.LastDisplayRow = self.DisplayRow + self.DisplayRows - 1 # Where does the display END ?  
        else:
            self.LastDisplayRow = None
        if self.DisplayCol != None and self.DisplayColumns != None:
            #self.LastDisplayCol = self.DisplayCol + self.DisplayColumns - 1
            self.LastDisplayCol = self.DisplayCol + self.DisplayColumns
        else:
            self.LastDisplayCol = None
        if type(fg) == list:
            self.DefaultFG = fg[0] # What's the default foreground color?
            self.DefaultFGs = fg
        else:
            self.DefaultFG = fg # What's the default foreground color?
            self.DefaultFGs = [fg]
        self.FGColorCount = len(self.DefaultFGs) # How many colors are available?
        self.FGColorIndex = 0 # Which color do we start with if multiple available?
        if type(bg) == list:
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
        self.fgcolor = [[self.DefaultFG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Foreground colour of each character.
        self.bgcolor = [[self.DefaultBG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Background colour of each character.
        self.character = [[" " for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Characters to display.
        # Store the default state of the window here. This is used if the window is 'cleared'.
        self.default_fgcolor = [[self.DefaultFG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Foreground colour of each character.
        self.default_bgcolor = [[self.DefaultBG for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Background colour of each character.
        self.default_character = [[" " for c in range(self.DisplayColumns)] for r in range(self.DisplayRows)] # Characters to display.
        self.PrevLineStrings = [None for r in range(self.DisplayRows)] # List of the display commands last issued to paint the display. Used to check for changes.
        self.ReduceIO = False # If set to true, Display() method will only update lines of the display that it thinks have changed.
        self.sprites = [] # List of any active sprites in the display.
        self.PrintHistory = [] # Cache of recently printed lines, used for repainting and exporting.
        self.FirstScrollRow = FirstScrollRow # 0 means data starts at the first row of the window, 1 means there's a title or something in row 0, etc. Scrolling takes this into account.
        self.Log = None # Can store handle to a 'Log' method for logging messages. Needs to be defined and assigned by the calling program.
        self.RefreshRate = None # Can specify how quickly the display refreshes (in seconds).
        self.LastRefresh = None # When did the display last update?
        #self.Metadata = {} # Dictionary of metadata for fields in the display. (Experimental)
        #                   # {'name' : 'xxx', 'row' : nn, 'col' : nn, 'fg' : nn, 'bg' : nn}
        self.Fields = [] # List of fields if defined.
        self.MarkDisplay = False # If TRUE the corners are highlighted in RED, and the FIELDS are highlighted in YELLOW(for layout checking)
        if title == None: self.WindowTitle = None # Does the window have a title row?
        else: self.SetTitle(title)
        self.ClipWindow = False # If TRUE, the window can be clipped to fit available terminal display. This will simply truncate.
        self.DrawBorder = False # If TRUE, an additional single line border is drawn on the RIGHT and BOTTOM of the window. Takes 1 extra character in each dimension.
        self.BorderFG = self.DefaultFG
        self.BorderBG = self.DefaultBG
        colordisplay.DefinedWindows.append(self) # Add this window to the global list of all windows.

    def __del__(self):
        """ Remove this window from the list of defined windows.
            *Q* This is called by the garbage collector (not guaranteed), so may not be the smartest way to do this. """
        for i,w in enumerate(colordisplay.DefinedWindows):
            if w == self: # Found myself in the list. Remove and quit.
                del colordisplay.DefinedWindows[i]
                break

    def SetTitle(self,title):
        """ Turn first row of a window into a title row.
            Color appropriately and change the scroll behaviour of the window.
            1st line nolonger scrolls. """
        self.WindowTitle = ' ' + title.strip()
        if self.WindowTitle != None: 
            temp = self.WindowTitle
            self.FirstScrollRow = 1
        else:
            temp = ''
            self.FirstScrollRow = 0
        temp = (temp + (' ' * self.DisplayColumns))[:self.DisplayColumns]
        for c in range(self.DisplayColumns):
            self.character[0][c] = temp[c]
            if self.WindowTitle != None:
                self.fgcolor[0][c] = self.TitleFG # Invert colors for titles.
                self.bgcolor[0][c] = self.TitleBG # Invert colors for titles.
            else:
                self.fgcolor[0][c] = self.DefaultFG # Regular colors if no title.
                self.bgcolor[0][c] = self.DefaultBG # Regular colors if no title.

    def AddField(self,name,row,column,length=10,justify='l'):
        """ Add a field to the list of fields recognised in this window. 
            Duplicates are allowed. """
        self.Fields.append(field(name=name,row=row,col=column,length=length,justify=justify))
        return True

    def InitializeProgressBar(self,name,minval,maxval,fg=None,bg=None):
        """ Prime a field as a progress bar. """
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
            via the startchar and endchar parameters. """
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

    def GetFloatValue(self,input):
        """ Convert an input value into a float.
            Removing special characters such as "%","C" etc. """
        allowedchars = ['0','1','2','3','4','5','6','7','8','9','.']
        sinp = str(input) # Make sure it's a string.
        cinp = '' # Cleaned input.
        for s in sinp:
            if s in allowedchars: cinp += s
        finp = float(cinp)
        return finp

    def ExportFields(self,filename,initialdictionary={}):
        """ Export field values to json file.
            Data is appended to any values already existing in initialdictionary. """
        tempdict = initialdictionary
        for field in self.Fields:
            tempdict[self.DisplayName + "." + field.Name] = field.Value
        tempdict[self.DisplayName + '.PrintHistory'] = self.PrintHistory
        with open(filename,'w') as f:
            json.dump(tempdict,f)
        return True

    def UpdateBlinkStatus(self):
        """ Check for any fields with 'BlinkRate' set. 
            Adjust colors accordingly. """
        for f in self.Fields:
            if f.BlinkRate != 0: # This field is in BLINK mode.
                # Choose an appropriate color scheme.
                t = datetime.now().timestamp() # Current time as seconds.
                c = round(t / f.BlinkRate,0) % len(self.BlinkColors) # Cycle through the list of BlinkColor pairs.
                self.FieldValue(f.name,fg=self.BlinkColors[c][0],bg=self.BlinkColors[c][1])
        return True

    def SetBlinkStatus(self,name,blinkrate,blinkcolors=[[textcolor.WHITE,textcolor.BLACK],[textcolor.BLACK,textcolor.WHITE]]):
        """ Setup blink data.
                    """
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
        
    def FieldValue(self,name,value,fg=None,bg=None):
        """ Update the value of a field and display it. """
        FoundIt = False
        for f in self.Fields:
            if f.Name == name: # Will update multiple fields with the same name.
                FoundIt = True
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
                    for i in range(f.Length): # Set the characters one at a time.
                        self.character[f.Row][f.Column + i] = sValue[i]
                        if fg != None: self.fgcolor[f.Row][f.Column + i] = fg
                        if bg != None: self.bgcolor[f.Row][f.Column + i] = bg
        return FoundIt

    def RenameField(self,oldname,newname):
        """ Change the name of a data field to something more useful. """
        FoundIt = False
        for f in self.Fields: # Check all fields. 
            if f.Name == oldname: # Found original fieldname.
                FoundIt = True
                f.Name = newname # Assign new fieldname. 
        return FoundIt

    def FieldFormat(self,name, justify=None, pattern=None, bwz=None):
        """ Change the format of a data field to something more useful. """
        FoundIt = False
        for f in self.Fields: # Check all fields. 
            if f.Name == name: # Found original fieldname.
                FoundIt = True
                if justify != None: f.Justify = justify
        return FoundIt

    def CopyFieldColor(self,fromname,toname):
        """ Copy color of one field to another. """
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
        """ Update the color of a field and display it. """
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
        """ Set colour range for a field. """
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
        """ Update the color of a field based upon a range of values. """
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
        """ Return dictionary of fields recognised in the window. """
        dict = {}
        for f in self.Fields:
            dict[f.Name] = {'row': f.Row, 'col': f.Column, 'len': f.Length, 'just': f.Justify, 'type': f.Type}
        return dict

    def SetRefreshRate(self,rate):
        """ Set selected refresh rate and reset the refresh timer. """
        self.RefreshRate = rate
        self.LastRefresh = None

    def SetDefault(self):
        """ Store the current display as a default image. 
            When the display is cleared, this default image is restored. """
        for c in range(self.DisplayColumns):
            for r in range(self.DisplayRows):
                self.default_fgcolor[r][c] = self.fgcolor[r][c]
                self.default_bgcolor[r][c] = self.bgcolor[r][c]
                self.default_character[r][c] = self.character[r][c]

    def ConvertLines(self):
        """ Scan the current layout for '-','|','+' symbols and convert to primitive line drawing. """
        # Not yet implemented.
        return True

    def ClipRow(self,row):
        if row < 0: row = 0
        if row >= self.DisplayRows: row = self.DisplayRows - 1
        return row
        
    def ClipCol(self,col):
        if col < 0: col = 0
        if col >= self.DisplayColumns: col = self.DisplayColumns - 1
        return col
        
    def DrawBox(self,fromloc,toloc,fg=None,bg=None,border=True,fill=True,overwritelist=['+','-','|',' ']):
        """ Use unicode line characters to draw a box on a colordisplay window. 
            fromloc = (fromrow,fromcol)
            toloc = (torow,tocol) 
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
                            other characters that are not in the overwritelist """
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
        """ Return True if refresh is due, else False. """
        result = False
        if self.RefreshRate == None: result = True # There's no restriction so always refresh. 
        elif self.LastRefresh == None: result = True # Need to do initial drawing. 
        elif (datetime.now() - self.LastRefresh).total_seconds() > self.RefreshRate: result = True # Refresh is due.
        return result 
        
    def AddSprite(self,name,text,row=None,col=None,fg=15,bg=0,level=0):
        """ Create a sprite. 
            If name is unique, it creates an instance of cdsprite subclass and adds it to the 
            list of sprites managed by this display buffer. """
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
        """ Return sprite label (optionally colored). """
        result = None
        for s in self.sprites:
            if s.name == name:
                result = s.Label(color=color)
        return result

    def ColoredSprite(self,name):
        """ Return sprite character with embedded colour codes. """
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
            Jan.2022 0.0.2 : fg and bg parameters nolonger used. """
        if fg != None: print ('textcolor.colordisplay.Clear() fg parameter is nolonger supported.')
        if bg != None: print ('textcolor.colordisplay.Clear() bg parameter is nolonger supported.')
        for r in range(self.DisplayRows):
            for c in range(self.DisplayColumns):
                self.character[r][c] = self.default_character[r][c]
                self.fgcolor[r][c] = self.default_fgcolor[r][c]
                self.bgcolor[r][c] = self.default_bgcolor[r][c]
        if immediate: self.Draw() # Clear the display immediately.

    def CellValue(self,row,col):
        """ Return cell contents. Character, fg and bg colors. """
        fg, bg = self.CellColor(row,col)
        char = self.character[row][col]
        return char,fg,bg
        
    def ColorCell(self,row,col,fg,bg):
        """ Change colour of a cell, but don't change the text. """
        self.fgcolor[row][col] = fg
        self.bgcolor[row][col] = bg

    def CellColor(self,row,col):
        """ Return current color of a cell. """
        if row < 0 or row >= self.DisplayRows: fg = self.DefaultFG
        else: fg = self.fgcolor[row][col]
        if col < 0 or col >= self.DisplayColumns: bg = self.DefaultBG
        else: bg = self.bgcolor[row][col]
        return fg, bg

    def ScrollUp(self,lines=1,immediate=False):
        """ Scroll the display up by a number of lines. 
            Drops lines at the top,
            adds new blank lines at the bottom. """
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

    def Print(self,*args,fg=None,bg=None,immediate=False):
        """ Simple scrolling print function. 
            Appends text to bottom of window display and scrolls up as required.
            This allows the retirement of the messagewindow class. 
            immediate=True: Display is immediately refreshed. 
            immediate=False: Display needs to be refreshed elsewhere.
            if fg or bg colors are specified, they override the default color scheme of the display. """
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
            -ve co-ordinates are bottom-to-top, right-to-left """
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
        """ Alias for Display() method. For backwards compatibility. """
        print ("***** colordisplay.Draw() method called. Depricated. Use colordisplay.Display() method instead.")
        self.Display(screenheight=screenheight,screenwidth=screenwidth,immediate=immediate)

    def _MarkDisplay(self):
        """ Quickly highlights window dimensions and fields.
            Helps when defining displays in new applications.
            Debug/Dev only. """
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
            targetbuffer is the handle to another colordisplay object. 
            displayrow = first row in targetbuffer. If None, then this object's value is used. 
            displaycol = first column in targetbuffer. If None, then this object's value is used. """
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

    def ForceRedraw(self):
        """ Flushes old values from self.PrevLineStrings[] forcing a full refresh.
            Normally when calling the Display() method, only changes are sent to the terminal window.
            If you ForceRedraw() then the whole window is sent fresh. """
        self.PrevLineStrings = [' ' for i in self.PrevLineStrings]
    
    @staticmethod
    def GlobalForceRedraw(): # Common
        """ Flushes old values from self.PrevLineStrings[] forcing a full refresh in all registered windows. """
        for w in colordisplay.DefinedWindows:
            try:
                w.ForceRedraw()
            except:
                pass # Window nonlonger exists.

    def GetTextLines(self):
        """ Returns the display layout as a list of strings.
            No color or cursor codes are included, just the basic monotone display text.
            Sprites are shown in their latest position too. """
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
        """ Display current contents of the window in a text box. """
        textcolor.TextBox(self.GetTextLines())
        
    @staticmethod
    def GlobalViewWindows(titlefg=None,titlebg=None):
        """ Construct a menu of all available windows
            then choose which window to display. """
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
            screenheight: Tells the number of rows available in the terminal display. 
            screenwidth: Tells the number of columns available in the terminal display. 
            immediate: (True) Forces immediate update of the terminal display.
                       (False) Only updates the display if the refresh timer is due. """

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
        HorizontalChar = textcolor.SYMBOLS['horizontal'] # '\u2500'
        VerticalChar = textcolor.SYMBOLS['vertical'] # '\u2502'
        CornerChar = textcolor.SYMBOLS['corner_br'] # '\u2518'
        self.UpdateBlinkStatus() # If any fields are supposed to blink, check their color now.
        if self.MarkDisplay: # We need to mark up the corners and fields.
            self._MarkDisplay()
        for r in range(self.DisplayRows): # Go through all the rows in turn. *Q* Should respect 'ClipWindow' too.
            if self.ClipWindow and self.DisplayRow != None and (r + self.DisplayRow) > maxscreenrow: break # We're off the end of the available display.
            try:
                # The following code has occassionally failed with an IndexError. Added some debugging in case it occurs again to aid solving.
                runningfg = self.fgcolor[r][0] # Note what color we're printing at the start of the line. Color control codes change when this value changes.
                runningbg = self.bgcolor[r][0]
            except IndexError as e:
                print("colordisplay fault: Index out of range?",r,0)
                print("colordisplay fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor))
                print("colordisplay fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol)
                print("colordisplay fault: LastDisplayRow",self.LastDisplayRow,"LastDisplayCol",self.LastDisplayRow)
                print("colordisplay fault: DisplayRow",self.DisplayRow,"DisplayCol",self.DisplayCol)
                print("colordisplay fault: DisplayRows",self.DisplayRows,"DisplayColumns",self.DisplayColumns)
                print("colordisplay fault: ClipWindow",self.ClipWindow)
                if self.Log != None:
                    self.Log("colordisplay fault: Index out of range?",r,0,level='error',terminal=True)
                    self.Log("colordisplay fault: Available range fg",len(self.fgcolor),"bg",len(self.bgcolor),level='error',terminal=True)
                    self.Log("colordisplay fault: maxscreenrow",maxscreenrow,"maxscreencol",maxscreencol,level='error',terminal=True)
                    self.Log("colordisplay fault: LastDisplayRow",self.LastDisplayRow,"LastDisplayCol",self.LastDisplayRow,level='error',terminal=True)
                    self.Log("colordisplay fault: DisplayRow",self.DisplayRow,"DisplayCol",self.DisplayCol,level='error',terminal=True)
                    self.Log("colordisplay fault: DisplayRows",self.DisplayRows,"DisplayColumns",self.DisplayColumns,level='error',terminal=True)
                    self.Log("colordisplay fault: ClipWindow",self.ClipWindow,level='error',terminal=True)
                raise Exception("Index out of range") from e # Terminate through the regular exception routine.
            line = textcolor.fgbgcolor(runningfg,runningbg,"",reset=False) # Start line off with initial color scheme. Leave the control code 'open' for more text to be added.
            for c in range(self.DisplayColumns): # Go through each column in turn. *Q* Should respect 'ClipWindow' too.
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
                if runningfg != f or runningbg != b: # Colour scheme has changed. Insert appropriate code.
                    runningfg = f # Note new colours we're now printing with.
                    runningbg = b
                    line += textcolor.fgbgcolor(runningfg,runningbg,"",reset=False) # Insert open-ended colour change code.
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

    @staticmethod
    def GlobalExportFields(filename,initialdictionary={}):
        """ Export field values from all windows to json file.
            Data is appended to any values already existing in initialdictionary. """
        tempdict = colordisplay.GlobalSaveToDictionary(initialdictionary=initialdictionary)
        with open(filename,'w') as f:
            json.dump(tempdict,f,default=str)
        return True
        
    @staticmethod
    def GlobalSaveToDictionary(initialdictionary={}):
        """ Export field values from all windows to dictionary.
            Data is appended to any values already existing in initialdictionary. """
        tempdict = initialdictionary
        for w in colordisplay.DefinedWindows:
            for field in w.Fields:
                tempdict[w.DisplayName + "." + field.Name] = field.Value
            tempdict[w.DisplayName + '.PrintHistory'] = w.PrintHistory
        return tempdict
        
    @staticmethod
    def GlobalFieldFormat(name, justify=None, pattern=None, bwz=None): # Common
        """ Update the format of a field in all defined windows. """
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
        """ Update the value of a field in all defined windows and display it. """
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
        """ Update the color of a field in all defined windows. """
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
            True turns it on.
            False turns it off. """
        for w in colordisplay.DefinedWindows:
            try:
                w.ReduceIO = reduce
            except:
                pass # Window nolonger exists.
        return

    @staticmethod
    def GlobalDisplay(screenheight=None,screenwidth=None,immediate=False): # Common
        """ Display ALL defined windows in a single call. """
        for w in colordisplay.DefinedWindows:
            try:
                w.Display(screenheight=screenheight,screenwidth=screenwidth,immediate=immediate)
            except:
                pass # Window nolonger exists.
        return
        
    @staticmethod
    def GlobalWindowLimits():
        """ Return maximum ROW and COLUMN that any of the current windows extend into. """
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

    __version__ = '0.0.1'

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. """
        print ('textcolor.menu: NOTE: This is replaced by the textcolor.proceduremenu class now!')

# -------------------------------------------------------------------------------------------------------------------------------- 

class proceduremenu():
    """ Menu driver.
        Create a menu object.
        Give it a dictionary of menu items, including labels and functions/methods to call.
        Call the Prompt() method to execute the menu. 
        Menu quits when user selects 'x' option. 
        
        dictionary format 
                {'menuitem1key':{'label':'menu item 1 label', 'bold':True/False, 'call': ProcedureName to call, 'break': False},
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
                
        You can trigger user input via the Prompt() method.
        You can directly run a menu option without user input via the Run() method.
        """

    __version__ = '0.0.3'

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None,labelwidth=23):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. """
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
        Counter = 0
        for key,value in self.Dictionary.items(): # Assign menu ID number to each entry.
            Counter += 1
            value['id'] = Counter
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
        """ Given an ID number, retrieve and display the help text if it exists. """
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
        """ Given an ID number, return URL associated with the help documentation. """
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
            The menu list from the dictionary will automatically gain '?' and 'x' options too. """
        # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
        count = 0
        print (textcolor.clearforward()) # Blank line before menu and clear everything below that.
        print (textcolor.fgbgcolor(self.TitleFG,self.TitleBG,' ' + menuprefix + self.Title + ' ')) # Menu title is painted in inverse colours. 
        for key,value in self.Dictionary.items(): # Go through each menu item in turn.
            entry = textcolor.yellow(str(value['id']).rjust(self.IdWidth,' ')) + ' ' # ID number in yellow. 
            if 'bold' in value and value['bold']: # If the menu item is in bold, make it so.
                entry += textcolor.white(value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            else: # Menu item is not in bold.
                entry += value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth]
            entry += ' ' # Space between columns of menu entries. 
            print (entry,end='') # Print the menu entry column, don't include 'newline' yet.
            count += 1 # Count how many entries.
            if count % self.Columns == 0: # Print 'newline' after 2nd column entry.
                print ('')
            if 'break' in value and value['break']: 
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
            These allow you to prepare and/or cleanup even if the main call fails. """
            
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
        if self.PreCall != None: # See if it's a callable function.
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
        
    def ProcessHelpRequest(self,answer):
        """ Receive a text type menu id. 
            if it converts to an integer successfully, 
            show the help text associated with that menu item. """
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
            
            Note, you can also trigger options from the menu without user prompting by using the menu.Run(name) method. """
        # Now paint the menu and ask the user what to do.
        self.Draw(menuprefix=menuprefix) # Paint the menu.
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
            # except Exception as e:
            except Exception:
                # Text would not convert into integer. 
                menuid = None
            if menuid != None: # 
                found = False # Have we found and executed the menu option?
                for key,value in self.Dictionary.items():
                    if value['id'] == menuid:
                        self.Run(key) # Execute the option.
                        self.Draw() # Refresh the menu.
                        found = True # We have found and executed the option. OK to return to ask user for new input.
                        break # Next
                if found: # Option was found and executed. Return to user input.
                    continue # Next user input.
            if answer.lower() == '?': # Refresh option chosen.
                self.Draw() # Refresh the menu.
                continue # Next user input.
            if answer.lower() == 'x': # User chose to quit the menu. Terminate the loop.
                break # Go UP a level, quit if at root.
            # User input was not recognised. Try again.
            print (textcolor.red("'" + str(answer) + "' Unrecognised. Try again."))

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
                
        You can trigger user input via the Prompt() method.
        You can directly run a menu option without user input via the Run() method.
        """

    __version__ = '0.0.2'

    def __init__(self,dictionary,title='Menu',titlefg=None,titlebg=None,helpdir=None,helpurl=None,logger=None):
        """ Create the menu, load the dictionary.
            Initialize and validate the data.
            title = Title of menu.
            titlebg/fg colors of menu title.
            helpdir = directory where help text files exist. 
            helpurl = url to help file. """
        self.Dictionary = dictionary
        self.Title = title
        self.IdWidth = 2
        self.LabelWidth = 26
        self.TitleFG = titlefg
        self.Columns = 2 # How many columns to draw?
        self.Log = logger # Can define a logging function to use.
        if titlefg == None: self.TitleFG = textcolor.BLACK
        self.TitleBG = titlebg
        if titlebg == None: self.TitleBG = textcolor.YELLOW
        Counter = 0
        for key,value in self.Dictionary.items(): # Assign menu ID number to each entry.
            Counter += 1
            value['id'] = Counter
            self.LabelWidth = max(self.LabelWidth,len(value['label']))
        self.HelpDir = helpdir
        self.HelpUrl = helpurl

    def GetHelpFile(self,menuid):
        """ Given an ID number, retrieve and display the help text if it exists. """
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
        """ Given an ID number, return URL associated with the help documentation. """
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
            The menu list from the dictionary will automatically gain '?' and 'x' options too. """
        # In Python 3.7 onwards, dictionaries should retain the sequence in which items are added. No sorting required.
        count = 0
        print (textcolor.clearforward()) # Blank line before menu and clear everything below that.
        print (textcolor.fgbgcolor(self.TitleFG,self.TitleBG,' ' + menuprefix + self.Title + ' ')) # Menu title is painted in inverse colours. 
        for key,value in self.Dictionary.items(): # Go through each menu item in turn.
            entry = textcolor.yellow(str(value['id']).rjust(self.IdWidth,' ')) + ' ' # ID number in yellow. 
            if 'bold' in value and value['bold']: # If the menu item is in bold, make it so.
                entry += textcolor.white(value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth])
            else: # Menu item is not in bold.
                entry += value['label'].ljust(self.LabelWidth,' ')[:self.LabelWidth]
            entry += ' ' # Space between columns of menu entries. 
            print (entry,end='') # Print the menu entry column, don't include 'newline' yet.
            count += 1 # Count how many entries.
            if count % self.Columns == 0: # Print 'newline' after 2nd column entry.
                print ('')
            if 'break' in value and value['break']: 
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
        """ Given a menu option key, extract the selected value. """
        result = self.Dictionary[key]['value'] # What procedure is to be called?
        return result

    def ProcessHelpRequest(self,answer):
        """ Receive a text type menu id. 
            if it converts to an integer successfully, 
            show the help text associated with that menu item. """
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

            """
        # Now paint the menu and ask the user what to do.
        self.Draw(menuprefix=menuprefix) # Paint the menu.
        result = None # The actual choice. None if nothing chosen.
        found = False # Set to True if a choice is successfully made, else False is returned.
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
            # except Exception as e:
            except Exception:
                # Text would not convert into integer. 
                menuid = None
            if menuid != None: # 
                found = False # Have we found and executed the menu option?
                for key,value in self.Dictionary.items():
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
    
    def Print(self,inputlist):
        """ Supports self.Filter method. 
            Lists the choices to select from. 
            Abbreviates the list if > 10 entries, otherwise shows them all. """
        printlist = ''
        if self.Compress and len(inputlist) > 10: # Big list and we're allowed to compress it.
            for i in range(5):
                printlist += inputlist[i] + ', '
            printlist += ' ... to ... '
            for i in range(-5,0):
                printlist += ', ' + inputlist[i]
        else: # Short list or we're not allowed to compress it, so show everything.
            for i,n in enumerate(inputlist):
                if i > 0: printlist += ', '
                printlist += n
        print(printlist)
        
    def Filter(self,inputlist):
        """ Recursive!!! 
            Receive a list of text items.
            User must select one of them.
            This lists the choices and lets the user narrow down the list if it's big.
            Returns when the user has selected a single item or decided to select nothing. """
        choice = []
        while True:
            choice = []
            self.Print(inputlist)
            inputtext = input("Choice ('x' to return) : ")
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
            if len(choice) > 1 and choice != inputlist: choice = self.Filter(choice) # Refine the list further.
            if len(choice) == 1: break # Choice made, return.
        return choice

    def Prompt(self):
        """ Receive a list and return the user's selection or None value. """
        result = self.Filter(self.FullList)
        if len(result) == 0: result = None # Return None value, nothing chosen. 
        elif len(result) == 1: result = result[0] # Strip the list structure off.
        # In all other cases return the selected list.
        return result
    
# -------------------------------------------------------------------------------------------------------------------------------- 