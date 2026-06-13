import asyncio
import os
import sys
import time
import threading
import json
import websockets
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
MONITORED_DIR = r"m:\Spike\monitored_directory"
BACKEND_WS_URL = "ws://127.0.0.1:8000/ws/client"
TICK_INTERVAL_SEC = 0.05  # 50ms rolling window

# State variables
file_system_spike = 0
last_file_path = ""
thread_activity_spike = 0
last_process_name = ""

# Lock for thread safety
state_lock = threading.Lock()

# Watchdog event handler
class AegisFileSystemHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        # Ignore directory events, only monitor file activity
        if not event.is_directory:
            global file_system_spike, last_file_path
            with state_lock:
                file_system_spike = 1
                last_file_path = event.src_path

# Background thread to monitor psutil process thread activity
current_thread_count = 0
thread_monitoring_active = True

def track_system_threads():
    global current_thread_count, thread_activity_spike, thread_monitoring_active, last_process_name
    
    # Initialize baseline
    last_thread_count = 0
    process_thread_map = {}
    try:
        for p in psutil.process_iter(['name', 'num_threads']):
            if p.pid != os.getpid() and p.info['num_threads'] is not None:
                process_thread_map[p.pid] = p.info['num_threads']
        last_thread_count = sum(process_thread_map.values())
    except Exception:
        pass
        
    while thread_monitoring_active:
        try:
            # Query active system threads (excluding our own process to avoid feedback loops)
            active_threads = 0
            current_map = {}
            for p in psutil.process_iter(['name', 'num_threads']):
                if p.pid == os.getpid():
                    continue
                try:
                    threads = p.info['num_threads']
                    if threads is not None:
                        active_threads += threads
                        current_map[p.pid] = (p.info['name'], threads)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            with state_lock:
                current_thread_count = active_threads
                # If thread count changed, flag thread activity spike and find the process culprit
                if active_threads != last_thread_count:
                    thread_activity_spike = 1
                    last_thread_count = active_threads
                    
                    # Try to locate the process that caused the thread shift
                    culprit = ""
                    max_diff = 0
                    for pid, (name, threads) in current_map.items():
                        prev_threads = process_thread_map.get(pid, 0)
                        diff = abs(threads - prev_threads)
                        if diff > max_diff:
                            max_diff = diff
                            culprit = name
                    
                    if culprit:
                        last_process_name = culprit
            
            # Update history map
            process_thread_map = {pid: val[1] for pid, val in current_map.items()}
        except Exception:
            # Silence process-iter errors if process exits mid-query
            pass
            
        time.sleep(0.04)  # Sample slightly faster than the tick interval

async def delta_filter_loop():
    global file_system_spike, thread_activity_spike, last_file_path, last_process_name
    
    # Ensure the monitored directory exists
    if not os.path.exists(MONITORED_DIR):
        os.makedirs(MONITORED_DIR)
        print(f"Created monitored directory at: {MONITORED_DIR}")
        
    # Start the watchdog observer
    event_handler = AegisFileSystemHandler()
    observer = Observer()
    observer.schedule(event_handler, path=MONITORED_DIR, recursive=True)
    observer.start()
    print(f"Watchdog monitoring folder: {MONITORED_DIR}")
    
    # Start the psutil background thread
    t_thread = threading.Thread(target=track_system_threads, daemon=True)
    t_thread.start()
    print("Process thread activity monitor running...")
    
    # Main loop connecting to backend WebSocket
    print(f"Connecting to EDR Backend at {BACKEND_WS_URL}...")
    
    reconnect_delay = 1.0
    while True:
        try:
            async with websockets.connect(BACKEND_WS_URL) as ws:
                print("Successfully connected to EDR Backend WebSocket.")
                reconnect_delay = 1.0  # Reset backoff on successful connection
                
                ticks = 0
                spikes_sent = 0
                
                while True:
                    start_time = time.perf_counter()
                    
                    # 1. Read spikes & reset state variables atomically
                    with state_lock:
                        fs_val = file_system_spike
                        thread_val = thread_activity_spike
                        fs_path = last_file_path
                        thread_proc = last_process_name
                        
                        file_system_spike = 0
                        thread_activity_spike = 0
                        last_file_path = ""
                        last_process_name = ""
                        
                    pulse_vector = [fs_val, thread_val]
                    
                    # 2. Stream to Backend
                    payload = {
                        "spike": pulse_vector,
                        "filepath": fs_path,
                        "process": thread_proc
                    }
                    await ws.send(json.dumps(payload))
                    
                    ticks += 1
                    if sum(pulse_vector) > 0:
                        spikes_sent += 1
                        
                    # Calculate rolling sparsity in client console every 5 seconds (100 ticks)
                    if ticks >= 100:
                        sparsity = (1.0 - (spikes_sent / ticks)) * 100
                        print(f"[EDR Client] Spikes processed. Rolling Sparsity: {sparsity:.1f}% | Active Threads: {current_thread_count}")
                        ticks = 0
                        spikes_sent = 0
                        
                    # 3. Precision tick timer to align with TICK_INTERVAL_SEC
                    elapsed = time.perf_counter() - start_time
                    sleep_time = max(0.001, TICK_INTERVAL_SEC - elapsed)
                    await asyncio.sleep(sleep_time)
                    
        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"WebSocket disconnected or backend offline. Retrying in {reconnect_delay:.1f}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(10.0, reconnect_delay * 1.5)  # Exponential backoff
            
    # Clean up (unreachable but good practice)
    observer.stop()
    observer.join()

if __name__ == "__main__":
    try:
        asyncio.run(delta_filter_loop())
    except KeyboardInterrupt:
        print("\nStopping OS Ingestion Client.")
        thread_monitoring_active = False
        sys.exit(0)
