import subprocess
import time
import sys
import threading
from typing import Dict

# Configuration
PYTHON_EXE = sys.executable
VELVET_MODULE = "velvet.main"

# Processes to manage
# Name -> List of arguments
PROCESSES = {
    "vision": ["--module", "vision", "run"],
    "audio": ["--module", "audio", "run"],
    "gateway": ["--module", "gateway", "--module", "discovery", "run"],
}

procs: Dict[str, subprocess.Popen] = {}
stop_event = threading.Event()

def start_process(name: str):
    """Start a process."""
    cmd = [PYTHON_EXE, "-m", VELVET_MODULE] + PROCESSES[name]
    print(f"[Supervisor] Starting {name}...")
    try:
        # Use new console for each process on Windows so they don't share stdin/out messily?
        # Or just pipe output. Let's pipe output to keep it in one window for now.
        procs[name] = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
    except Exception as e:
        print(f"[Supervisor] Failed to start {name}: {e}")

def monitor_loop():
    """Monitor processes and restart if they crash."""
    while not stop_event.is_set():
        for name, proc in list(procs.items()):
            ret = proc.poll()
            if ret is not None:
                print(f"[Supervisor] Process {name} exited with code {ret}. Restarting in 5s...")
                del procs[name]
                time.sleep(5)
                if not stop_event.is_set():
                    start_process(name)
        
        time.sleep(1)

def main():
    print("🟣 VELVET NADIR SUPERVISOR")
    print("="*40)
    print("Starting subsystems...")
    
    # Start all
    for name in PROCESSES:
        start_process(name)
        time.sleep(1) # Stagger start
        
    print("All systems running. Press Ctrl+C to stop.")
    
    try:
        monitor_loop()
    except KeyboardInterrupt:
        print("\n[Supervisor] Stopping all processes...")
        stop_event.set()
        for name, proc in procs.items():
            print(f"Killing {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutError:
                proc.kill()
        print("Goodbye.")

if __name__ == "__main__":
    main()
