#!/usr/bin/python

# Raspberry Pi GPIO library.
# Presents an interface to the GPIO handlers on the Raspberry Pi SBCs.
# - Different classes can be built to handle different GPIO handlers, 
#   but all should present the same interface to the calling programs.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

GPIO_DRIVER = None
try:
    import RPi.GPIO as GPIO # Handling IO signals. If available.
    GPIO.setmode(GPIO.BCM)
    GPIO_DRIVER = "GPIO"
except: # No support for RPi.GPIO detected.
    pass

try:
    import gpiod # Handling IO signals. If available.
    GPIO_DRIVER = "GPIOD"
except: # No support for GPIOD detected.
    pass

if GPIO_DRIVER == 'GPIOD': # Select the GPIO handling chip.
    try:
        GPIOchip = gpiod.Chip('gpiochip4') # In very early RPi5 Bookworm builds the GPIO chip is 'gpiochip4'.
    except:
        GPIOchip = gpiod.Chip('gpiochip0') # In later RPi5 Bookworm builds the GPIO chip is 'gpiochip0'.

def cleanup_gpio():
    """ Perform cleanup at end of session. """
    GPIO.cleanup()

class inputpin_gpio():
    """ Wrapper for GPIO input pin. 
        Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods. 
        Pin can be declared as None in which case it's a non-functional device. """
    
    InputPins = [] # List of all defined input pins.
    __library__ = 'RPi.GPIO' # Which GPIO library does this support?
    __version__ = '0.0.0' # What version of the library is this?
    
    def __init__(self,pinbcm,name=None,pull="up",enabled=True,invert=False):
        """ Define a GPIO input pin.
        
            The purpose is to present a common interface to an I/O pin regardless of the underlying
            GPIO package being used. You can create alternative classes which interact with different 
            packages and present the same interface to the program.
        
            pinbcm = the BCM pin number. 
            name is an optional name for the pin. 
            pull = GPIO.PUD_UP for pull up (default HIGH/ON), 
                   GPIO.PUD_DOWN for pull down. (default LOW/OFF)
            enabled = initial enabled(True)/disabled(False) state of the pin.
            invert = False: IsOn returns TRUE for HIGH signal. 
                            IsOff returns TRUE for a LOW signal.
                     True:  IsOn returns TRUE for LOW signal.
                            IsOff returns TRUE for a HIGH signal.

            if pinbcm is None then this is a fake input.
            it behaves as a GPIO input, but doesn't actually link to a GPIO port and always returns the PULL UP/DOWN value. """
        self.Pin = pinbcm # The BCM number of the pin.
        self.Name = name # A reference name of the pin.
        self.Pull = pull.lower() # Is this a PULL_UP or PULL_DOWN input.
        self.Invert = invert # IsOn/IsOff methods invert their value. IsHigh/IsLow remain unchanged.
        if self.Pin != None: self.Enabled = enabled
        else: self.Enabled = False # Dummy pins are always disabled.
        # Set the PULL UP / DOWN config for the input.
        if pull == 'up': self.State = True # Initial state HIGH.
        else: self.State = False # Initial state LOW.
        # If it's a real pin, set it up through GPIO.
        if self.Pin != None: 
            if self.Pull == 'up': GPIO.setup(self.Pin,GPIO.IN,pull_up_down=GPIO.PUD_UP) # Will EARTH when triggered.
            else: GPIO.setup(self.Pin,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # Will go HIGH when triggered.
        # Append to the global list of all input pins.
        inputpin_gpio.InputPins.append(self) # Add to list of input pins.
        
    def Refresh(self):
        """ Get and store the current state of the pin.
            GPIO.input() returns 0 = Low, 1 = High.
            Convert to 0 = False, 1 = True 
            DISABLED pins always return False (electrical LOW).
            If you want the logical state of the pin after this use IsOn() and IsOff() methods.
            If you want the physical state of the pin after this use IsHigh() and IsLow() methods. """
        if self.Enabled and GPIO.input(self.Pin) != 0: self.State = True # High
        else: self.State = False # Low
        
    def IsHigh(self):
        """ Return TRUE if input is HIGH.
            This is the true electrical state of the pin.
            It does NOT respect the self.Invert flag, use IsOn() for that. """
        self.Refresh() # Get current electrical state of the pin.
        return self.State # Return True/False.
        
    def IsLow(self):
        """ Return TRUE if input is LOW.
            This is the true electrical state of the pin.
            It does NOT respect the self.Invert flag, use IsOff() for that. """
        self.Refresh() # Get current electrical state of the pin.
        return not self.State # Return True/False.

    def IsOn(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsHigh() """
        result = self.IsHigh()
        if self.Invert: result = not result
        return result # Return True/False.

    def IsOff(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsLow() """
        result = self.IsLow()
        if self.Invert: result = not result
        return result # Return True/False.

    def Enable(self):
        """ Enable the pin and set the output accordingly. 
            Can only enable real GPIO pins. """
        if self.Pin != None: self.Enabled = True # Can only enable if it's a real pin.
        self.Refresh() # Get current electrical state of the pin.
        
    def Disable(self):
        """ Disable the pin and set the state to LOW. """
        self.Enabled = False
        self.Refresh() # Get current electrical state of the pin.
        
    def Status(self):
        """ Return a string describing the current status of the pin. """
        temp = "GPIO: BCM:" + str(self.Pin) + ", INPUT:" + \
               " Ena:" + str(self.Enabled).rjust(5) + \
               " Inv:" + str(self.Invert).rjust(5) + \
               " IsOn:" + str(self.IsOn()).rjust(5) + \
               " IsOff:" + str(self.IsOff()).rjust(5) + \
               " IsHigh:" + str(self.IsHigh()).rjust(5) + \
               " IsLow:" + str(self.IsLow()).rjust(5)
        return temp

# ---------------------------------------------------------------------------------------------------------------

class outputpin_gpio():
    """ Define a GPIO output pin.
        
            The purpose is to present a common interface to an I/O pin regardless of the underlying
            GPIO package being used. You can create alternative classes which interact with different 
            packages and present the same interface to the program.
        

        Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods.
        PIN can be declared as None, in which case it's a non-functional device. """
    
    OutputPins = [] # List of all defined output pins. 
    __library__ = 'RPi.GPIO' # Which GPIO library does this support?
    __version__ = '0.0.0' # What version of the library is this?
    
    def __init__(self,pinbcm,name=None,enabled=True,state=False,invert=False):
        """ Create a new pin. 
            pinbcm is the BCM number of the GPIO pin. 
            name is an optional name for the pin. 
            enabled = initial enabled/disabled condition of the pin. 
            state = initial on(True)/off(False) condition of the pin.
            invert = Switch HIGH/LOW electrical states for the on/off status. """
        self.Pin = pinbcm # The BCM pin number.
        self.Name = name # Reference name for the pin.
        self.State = state # It's logical on/off state.
        self.Invert = invert # Flips electrical state to be opposite of logical state. LOW=ON, HIGH=OFF.
        # Only real pins can be enabled.
        if self.Pin != None: self.Enabled = enabled
        else: self.Enabled = False # If no real pin, force it to 'disabled'.
        # Only real pins are connected to a GPIO pin.
        if self.Pin != None: GPIO.setup(self.Pin, GPIO.OUT)
        outputpin_gpio.OutputPins.append(self) # Add to list of output pins.
        self.Refresh()
    
    def On(self):
        """ Turn on (HIGH) the output pin. """
        self.State = True
        self.Refresh() # Set electrical state of the pin.
        
    def Off(self):
        """ Turn off (LOW) the output pin. """
        self.State = False
        self.Refresh() # Set the electrical state of the pin.

    def IsOn(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsHigh() """
        result = self.IsHigh() # Get the current electrical state of the pin.
        if self.Invert: result = not result # Consider the Invert flag.
        return result # REturn True/False for logical state of the pin.

    def IsOff(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsLow() """
        result = self.IsLow() # Get the current electrical state of the pin.
        if self.Invert: result = not result # Consider the Invert flag.
        return result # Return True/False for the logical state of the pin.

    def IsHigh(self):
        """ Return TRUE if the pin is HIGH. 
            The true electrical state of the pin. 
            Does not respect self.Invert flag. 
            To respect self.Invert, use IsOn()/IsOff() """
        if GPIO.input(self.Pin) != 0: result = True # The true electrical state of the pin.
        else: result = False
        return result

    def IsLow(self):
        """ Return TRUE if the pin is LOW.
            The true electrical state of the pin. 
            Does not respect self.Invert flag.
            To respect self.Invert, use IsOn()/IsOff() """
        if GPIO.input(self.Pin) != 0: result = False # The true electrical state of the pin.
        else: result = True
        return result
        
    def Refresh(self):
        """ Set the electrical state of the output pin to match the status and its enabled condition. """
        if self.Pin != None: # It's a real pin.
            if self.Enabled:
                temp = self.State # Logical state.
                if self.Invert: temp = not temp # Convert to electrical state.
                if temp: GPIO.output(self.Pin,GPIO.HIGH) # Enabled and HIGH.
                else: GPIO.output(self.Pin,GPIO.LOW) # Enabled and LOW.
            else: GPIO.output(self.Pin,GPIO.LOW) # Disabled pin should default to LOW.

    def Enable(self):
        """ Enable the pin, this allows the output to be set HIGH.
            Can only enable REAL pins. """
        if self.Pin != None: self.Enabled = True # Only ENABLE if it's a real pin.
        self.Refresh() # Set the current electrical state of the pin.
        
    def Disable(self):
        """ Disable the pin, this prevents the output being set HIGH, it is forced LOW. """
        self.Enabled = False
        self.Refresh() # Set the current electrical state of the pin.
        
    def Status(self):
        """ Return a string describing the current status of the pin. """
        temp = "GPIO: BCM:" + str(self.Pin) + ", OUTPUT:" + \
               " Ena:" + str(self.Enabled).rjust(5) + \
               " Inv:" + str(self.Invert).rjust(5) + \
               " IsOn:" + str(self.IsOn()).rjust(5) + \
               " IsOff:" + str(self.IsOff()).rjust(5) + \
               " IsHigh:" + str(self.IsHigh()).rjust(5) + \
               " IsLow:" + str(self.IsLow()).rjust(5)
        return temp

# ---------------------------------------------------------------------------------------------------------------------

class inputpin_gpiod():
    """ Wrapper for GPIOD input pin. 
        Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods. 
        Pin can be declared as None in which case it's a non-functional device.

        """
    InputPins = [] # List of all defined input pins.
    __library__ = 'GPIOD' # Which GPIO library does this support?
    __version__ = '0.0.0' # What version of the library is this?
    
    def __init__(self,pinbcm,name=None,pull='up',enabled=True,invert=False):
        """ Define a GPIO input pin.
        
            The purpose is to present a common interface to an I/O pin regardless of the underlying
            GPIO package being used. You can create alternative classes which interact with different 
            packages and present the same interface to the program.
        
            pinbcm = the BCM pin number. 
            name is an optional name for the pin. 
            pull = GPIO.PUD_UP for pull up (default HIGH/ON), 
                   GPIO.PUD_DOWN for pull down. (default LOW/OFF)
            enabled = initial enabled(True)/disabled(False) state of the pin.
            invert = False: IsOn returns TRUE for HIGH signal. 
                            IsOff returns TRUE for a LOW signal.
                     True:  IsOn returns TRUE for LOW signal.
                            IsOff returns TRUE for a HIGH signal.

            if pinbcm is None then this is a fake input.
            it behaves as a GPIO input, but doesn't actually link to a GPIO port and always returns the PULL UP/DOWN value. """
        self.Pin = pinbcm # The BCM number of the pin.
        self.Name = name # A reference name of the pin.
        self.Line = GPIOchip.get_line(pinbcm) # Grab the IO line for this input.
        self.Pull = pull # Is this a PULL_UP or PULL_DOWN input.
        self.Invert = invert # IsOn/IsOff methods invert their value. IsHigh/IsLow remain unchanged.
        if self.Pin != None: self.Enabled = enabled
        else: self.Enabled = False # Dummy pins are always disabled.
        # Set the PULL UP / DOWN config for the input.
        if pull == 'up': self.State = True # Initial state HIGH.
        else: self.State = False # Initial state LOW.
        # If it's a real pin, set it up through GPIO.
        if self.Pin != None: 
            if pull == 'up': 
                self.Line.request(consumer=self.Name, 
                                   type=gpiod.LINE_REQ_DIR_IN, 
                                   flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP) # Will EARTH when triggered.
            else: 
                self.Line.request(consumer=self.Name, 
                                   type=gpiod.LINE_REQ_DIR_IN, 
                                   flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_DOWN) # Will go HIGH when triggered.
        # Append to the global list of all input pins.
        inputpin_gpiod.InputPins.append(self) # Add to list of input pins.
        
    def Refresh(self):
        """ Get and store the current state of the pin.
            GPIO.input() returns 0 = Low, 1 = High.
            Convert to 0 = False, 1 = True 
            DISABLED pins always return False (electrical LOW).
            If you want the logical state of the pin after this use IsOn() and IsOff() methods.
            If you want the physical state of the pin after this use IsHigh() and IsLow() methods. """
        if self.Enabled and self.Line.get_value() != 0: self.State = True # High
        else: self.State = False # Low
        
    def IsHigh(self):
        """ Return TRUE if input is HIGH.
            This is the true electrical state of the pin.
            It does NOT respect the self.Invert flag, use IsOn() for that. """
        self.Refresh() # Get current electrical state of the pin.
        return self.State # Return True/False.
        
    def IsLow(self):
        """ Return TRUE if input is LOW.
            This is the true electrical state of the pin.
            It does NOT respect the self.Invert flag, use IsOff() for that. """
        self.Refresh() # Get current electrical state of the pin.
        return not self.State # Return True/False.

    def IsOn(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsHigh() """
        result = self.IsHigh()
        if self.Invert: result = not result
        return result # Return True/False.

    def IsOff(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsLow() """
        result = self.IsLow()
        if self.Invert: result = not result
        return result # Return True/False.

    def Enable(self):
        """ Enable the pin and set the output accordingly. 
            Can only enable real GPIO pins. """
        if self.Pin != None: self.Enabled = True # Can only enable if it's a real pin.
        self.Refresh() # Get current electrical state of the pin.
        
    def Disable(self):
        """ Disable the pin and set the state to LOW. """
        self.Enabled = False
        self.Refresh() # Get current electrical state of the pin.
        
    def Status(self):
        """ Return a string describing the current status of the pin. """
        temp = "GPIOD: BCM:" + str(self.Pin) + ", INPUT:" + \
               " Ena:" + str(self.Enabled).rjust(5) + \
               " Inv:" + str(self.Invert).rjust(5) + \
               " IsOn:" + str(self.IsOn()).rjust(5) + \
               " IsOff:" + str(self.IsOff()).rjust(5) + \
               " IsHigh:" + str(self.IsHigh()).rjust(5) + \
               " IsLow:" + str(self.IsLow()).rjust(5)
        return temp

# ---------------------------------------------------------------------------------------------------------------
        
def cleanup_gpiod():
    """ Perform cleanup at end of session. """
    for pin in inputpin_gpiod.InputPins:
        pin.Line.release()
    for pin in outputpin_gpiod.OutputPins:
        pin.Line.release()

class outputpin_gpiod():
    """ Define a GPIO output pin.
        
            The purpose is to present a common interface to an I/O pin regardless of the underlying
            GPIO package being used. You can create alternative classes which interact with different 
            packages and present the same interface to the program.
        

        Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods.
        PIN can be declared as None, in which case it's a non-functional device. """

    OutputPins = [] # List of defined pins. 
    __library__ = 'GPIOD' # Which GPIO library does this support?
    __version__ = '0.0.0' # What version of the library is this?
    
    @staticmethod
    def ReleaseAll():
        """ Release all defined pins. """
        for pin in outputpin_gpiod.OutputPins:
            try:
                pin.release()
            except Exception as e:
                MainLog.Log("outputpin_gpiod.ReleaseAll(): Failed to release pin:",e,level='error')
    
    def __init__(self,pinbcm,name,enabled=True,state=False,invert=False):
        """ Create a new pin. 
            pinbcm is the BCM number of the GPIO pin. 
            name is a compulsory unique name for the pin. 
            enabled = initial enabled/disabled condition of the pin. 
            state = initial on(True)/off(False) condition of the pin.
            invert = Switch HIGH/LOW electrical states for the on/off status. """
        self.Pin = pinbcm
        self.Enabled = enabled
        self.Name = name
        self.State = state
        self.Invert = invert
        self.Line = GPIOchip.get_line(self.Pin) # Allocate the line.
        self.Line.request(consumer=name, type=gpiod.LINE_REQ_DIR_OUT) # Define a consumer for the line.
        outputpin_gpiod.OutputPins.append(self) # Add this output to the list of defined pins.
        self.Refresh()
    
    def On(self):
        self.State = True
        self.Refresh()
        
    def Off(self):
        self.State = False
        self.Refresh()
        
    def Refresh(self):
        if self.Enabled and self.State:
            self.Line.set_value(1) # High
        else:
            self.Line.set_value(0) # Low
            
    def IsOn(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsHigh() """
        result = self.IsHigh()
        if self.Invert: result = not result
        return result # Return True/False.

    def IsOff(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsLow() """
        result = self.IsLow()
        if self.Invert: result = not result
        return result # Return True/False.

    def IsOn(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsHigh() """
        result = self.IsHigh() # Get the current electrical state of the pin.
        if self.Invert: result = not result # Consider the Invert flag.
        return result # Return True/False for logical state of the pin.

    def IsOff(self):
        """ Return ON/OFF state of the input, respecting the 'invert' flag.
            If you want the true electrical state of the pin use self.IsLow() """
        result = self.IsLow() # Get the current electrical state of the pin.
        if self.Invert: result = not result # Consider the Invert flag.
        return result # Return True/False for the logical state of the pin.

    def IsHigh(self):
        """ Return TRUE if the pin is HIGH. 
            The true electrical state of the pin. 
            Does not respect self.Invert flag. 
            To respect self.Invert, use IsOn()/IsOff() """
        if self.Line.get_value() != 0: result = True # The true electrical state of the pin.            
        #if GPIO.input(self.Pin) != 0: result = True # The true electrical state of the pin.
        else: result = False
        return result

    def IsLow(self):
        """ Return TRUE if the pin is LOW.
            The true electrical state of the pin. 
            Does not respect self.Invert flag.
            To respect self.Invert, use IsOn()/IsOff() """
        if self.Line.get_value() != 0: result = False # The true electrical state of the pin.            
        #if GPIO.input(self.Pin) != 0: result = False # The true electrical state of the pin.
        else: result = True
        return result

    def Enable(self):
        self.Enabled = True
        self.Refresh()
        
    def Disable(self):
        self.Enabled = False
        self.Refresh()

    def Status(self):
        """ Return a string describing the current status of the pin. """
        temp = "GPIOD: BCM:" + str(self.Pin) + ", OUTPUT:" + \
               " Ena:" + str(self.Enabled).rjust(5) + \
               " Inv:" + str(self.Invert).rjust(5) + \
               " IsOn:" + str(self.IsOn()).rjust(5) + \
               " IsOff:" + str(self.IsOff()).rjust(5) + \
               " IsHigh:" + str(self.IsHigh()).rjust(5) + \
               " IsLow:" + str(self.IsLow()).rjust(5)
        return temp
