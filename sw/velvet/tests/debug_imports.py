import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    from velvet.devices import Device
    print("SUCCESS: Imported velvet.devices")
except ImportError as e:
    print(f"FAIL: {e}")

try:
    from velvet.tool_parsing import extract_tool_calls
    print("SUCCESS: Imported velvet.tool_parsing")
except ImportError as e:
    print(f"FAIL: {e}")

import velvet
print(f"Velvet package: {velvet}")
