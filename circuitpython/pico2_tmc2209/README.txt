Files for:
   RASPBERRY PI PICO2 WITH TMC2209 STEPPER DRIVERS.
   These files are not designed to work on other microcontrollers or different stepper drivers.

pi/circuitpython/pico2_tmc2209
│  
├─ README.txt # This file.
│  
├─ code.py # Primary program to run on Pico2 with tmc2209 stepper drivers.
│  
├─ tmc2209.py # Generic TMC Stepper library for communicating with tmc2209 stepper driver.
│  
├─ erase.py # Example code to erase file system on pico2 if a reset is needed.
│  
├─ as5600.py # Generic as5600 library for communicating with as5600 sensors.
│  
├─ pilomar # Pilomar project specific libraries.
│  │  
│  ├─ devices.py # Wrappers for sensors so they present common features to the project.
│  │  
│  ├─ enum.py # Used by some libraries.
│  │  
│  ├─ helpers.py # Misc functions and minor classes used by project.
│  │  
│  ├─ steppermotor.py # Main stepper motor class for the project.
│  │  
│  ├─ trajectory.py # Trajectory related classes for the project.
│  │  
│  └─ uarthost.py # UART serial communication handler for the project.
│
└─ lib # Adafruit libraries, included in project for convenience.
   │  
   ├─ adafruit_bus_device # Copy of adafruit_bus_device folder for convenience.
   │  
   ├─ adafruit_register # Copy of adafruit_register folder for convenience.
   │  
   └─ adafruit_lis3dh.mpy # Adafruit lis3dh handler included for convenience.
