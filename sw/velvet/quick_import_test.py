import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    import velvet
    print(f"Imported velvet: {velvet}")
    from velvet.devices import Device
    print("Imported Device")
except ImportError as e:
    print(f"Error: {e}")
