
print("Starting import debug...")
try:
    print("Importing Yi...")
    from velvet.shen.yi import Yi
    print("Yi imported.")
    
    print("Importing devices...")
    from velvet.devices import Device
    print("Devices imported.")
    
    print("Importing fabric...")
    from velvet.fabric import MessageType
    print("Fabric imported.")
    
    print("Importing Po...")
    from velvet.shen.po import Po
    print("Po imported.")
    
    print("Importing Hun...")
    from velvet.shen.hun import Hun
    print("Hun imported.")
    
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()

print("Done.")
