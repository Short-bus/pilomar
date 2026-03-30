Each folder in the gerber directory is a complete Gerber file set for a single PCB design.

To send the Gerber files for manufacturing you should select the PCB version you want and ZIP all the files in that folder.
Eg:
  cd gerber/PCB-2023-12-14
  zip PCB-2023-12-14.zip *

Please order the board UNPOPULATED, the GERBER files do not specify the components, you need to add those manually when you 
have received the unpopulated PCBs.

These designs are made in good faith and are best efforts, but no guarantees are provided. 
Please be sure you are happy with their function and safety before using in your project.

PCB designs ----------------------------------------------------------------------------------------------------------------

PCB-2023-12-14 
  This is the initial PCB design for the motorcontrol board.
  Microcontroller: Pimoroni Tiny2040 and Tiny2350
  Stepper driver: DRV8815

PCB-2025-12-15
  This is the V3.1.1 version of the motorcontrol board.
  Microcontroller: Raspberry Pi Pico 2 (NOT PICO 1)
  Stepper driver: TMC2209 (Recommend Big Tree Tech V1.3)

Manufacturing settings -----------------------------------------------------------------------------------------------------

Board type : Single pieces
Different design in panel： 1
Size : 111.9 x 72.5 mm
Quantity :5
Layer : 2 Layers
Material :FR-4: TG130
Thickness : 1.6 mm
Min track/spacing : 8/8mil
Min hole size : 0.3mm ↑
Solder mask : Purple
Silkscreen : White
Edge connector : No
Surface finish : HASL with lead
"HASL" to "ENIG" : No
Via process : Tenting vias
Finished copper : 1 oz Cu
Remove product No. : No
Customized Services and Advanced Options : UL marking:None,
