# Use these commands to erase the file system on the pico.
# You may have to type this manually if you cannot download or open the file in Thonny on the pico.

print("------------------------------------")
print("---   ERASING PICO FILE SYSTEM   ---")
print("------------------------------------")

import storage
storage.erase_filesystem()
