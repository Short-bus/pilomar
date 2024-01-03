Each folder in the gerber directory is a complete GerberFile for a single PCB.

To send the Gerber files for manufacturing you should select the PCB version you want and ZIP all the files in that folder.
Eg:
  cd gerber/PCB-2023-12-14
  zip PCB-2023-12-14.zip *

Please order the board UNPOPULATED, the GERBER files do not specify the components, you need to add those manually when you 
have received the unpopulated PCBs.

PCB designs ----------------------------------------------------------------------------------------------------------------

PCB-2023-12-14 
  This is the initial PCB design for the motorcontrol board.

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
