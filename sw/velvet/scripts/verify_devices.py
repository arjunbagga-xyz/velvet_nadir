import cv2
import pyaudio

print("--- Testing Camera ---")
try:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Camera 0 failed to open. Trying cv2.CAP_DSHOW...")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"✅ Camera working. Resolution: {frame.shape}")
        else:
            print("❌ Camera opened but could not read frame.")
    else:
        print("❌ Could not open any camera.")
    cap.release()
except Exception as e:
    print(f"❌ Camera error: {e}")

print("\n--- Testing Microphone ---")
try:
    p = pyaudio.PyAudio()
    info = p.get_default_input_device_info()
    print(f"Default mic: {info.get('name')}")
    
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
    data = stream.read(1024, exception_on_overflow=False)
    if len(data) > 0:
        print("✅ Microphone working. Got data.")
    else:
        print("❌ Microphone opened but got no data.")
        
    stream.stop_stream()
    stream.close()
    p.terminate()
except Exception as e:
    print(f"❌ Microphone error: {e}")
