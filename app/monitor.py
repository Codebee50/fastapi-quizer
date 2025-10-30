import threading
import time
import psutil
import os

def log_memory_usage(label=""):
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    cpu = process.cpu_percent(interval=None)
    print(f"[{label}] Memory: {mem_info.rss / 1024 ** 2:.2f} MB | CPU: {cpu}%")
    

def start_monitoring(interval: int = 10):
    """Starts a background thread that logs memory and CPU usage periodically."""
    def monitor():
        while True:
            log_memory_usage("FastAPI Backend")
            time.sleep(interval)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    print(f"✅ Monitoring thread started (every {interval}s)")