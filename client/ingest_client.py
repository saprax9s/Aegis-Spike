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
network_connect_spike = 0
privilege_change_spike = 0
script_exec_spike = 0

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
    global network_connect_spike, privilege_change_spike, script_exec_spike
    
    # Initialize baseline
    last_thread_count = 0
    last_conn_count = 0
    process_thread_map = {}
    
    try:
        last_conn_count = len(psutil.net_connections(kind='inet'))
    except Exception:
        pass
        
    try:
        for p in psutil.process_iter(['name', 'num_threads']):
            if p.pid != os.getpid() and p.info['num_threads'] is not None:
                process_thread_map[p.pid] = p.info['num_threads']
        last_thread_count = sum(process_thread_map.values())
    except Exception:
        pass
        
    while thread_monitoring_active:
        try:
            # 1. Query active system connections
            try:
                current_conns = len(psutil.net_connections(kind='inet'))
                if current_conns != last_conn_count:
                    with state_lock:
                        network_connect_spike = 1
                    last_conn_count = current_conns
            except Exception:
                pass

            # 2. Query active system threads and scan processes
            active_threads = 0
            current_map = {}
            for p in psutil.process_iter(['name', 'num_threads', 'username', 'cmdline']):
                if p.pid == os.getpid():
                    continue
                try:
                    p_name = p.info['name']
                    # Skip tracking noisy benign applications to prevent false thread spikes
                    if p_name and (p_name.lower() in [
                        "msedge.exe", "chrome.exe", "firefox.exe", "brave.exe",
                        "code.exe", "node.exe", "git.exe", "antigravity-ide.exe", "antigravityide.exe"
                    ] or "antigravity" in p_name.lower()):
                        continue
                        
                    threads = p.info['num_threads']
                    p_username = p.info['username']
                    p_cmdline = p.info['cmdline']
                    
                    if threads is not None:
                        active_threads += threads
                        current_map[p.pid] = (p_name, threads)
                        
                    # Check privilege change (runs elevated as admin or system or root)
                    if p_username:
                        user_lower = p_username.lower()
                        if any(admin in user_lower for admin in ["administrator", "system", "root"]):
                            with state_lock:
                                privilege_change_spike = 1
                                
                    # Check script execution (command line has shell/scripts interpreters running files)
                    if p_cmdline:
                        cmdline_str = " ".join(p_cmdline).lower()
                        if any(shell in cmdline_str for shell in ["powershell", "cmd.exe", "wscript", "cscript", "bash", "sh", "python"]):
                            with state_lock:
                                script_exec_spike = 1
                                
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
                        if name and (name.lower() in [
                            "msedge.exe", "chrome.exe", "firefox.exe", "brave.exe",
                            "code.exe", "node.exe", "git.exe", "antigravity-ide.exe", "antigravityide.exe",
                            "python.exe", "python3.exe", "explorer.exe", "cmd.exe", "powershell.exe", "conhost.exe"
                        ] or "antigravity" in name.lower()):
                            continue
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
    global network_connect_spike, privilege_change_spike, script_exec_spike
    
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
                
                # Start listener task to receive containment actions from backend
                listener_task = asyncio.create_task(receive_commands(ws))
                
                try:
                    ticks = 0
                    spikes_sent = 0
                    
                    while True:
                        start_time = time.perf_counter()
                        
                        # 1. Read spikes & reset state variables atomically
                        with state_lock:
                            fs_val = file_system_spike
                            thread_val = thread_activity_spike
                            net_val = network_connect_spike
                            priv_val = privilege_change_spike
                            script_val = script_exec_spike
                            fs_path = last_file_path
                            thread_proc = last_process_name
                            
                            file_system_spike = 0
                            thread_activity_spike = 0
                            network_connect_spike = 0
                            privilege_change_spike = 0
                            script_exec_spike = 0
                            last_file_path = ""
                            last_process_name = ""
                            
                        pulse_vector = [fs_val, thread_val, net_val, priv_val, script_val]
                        
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
                finally:
                    listener_task.cancel()
                    try:
                        await listener_task
                    except asyncio.CancelledError:
                        pass
                    
        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, OSError) as e:
            print(f"WebSocket disconnected or backend offline. Retrying in {reconnect_delay:.1f}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(10.0, reconnect_delay * 1.5)  # Exponential backoff

async def receive_commands(ws):
    try:
        async for message in ws:
            try:
                data = json.loads(message)
                if data.get("action") == "lockdown":
                    process = data.get("process")
                    filepath = data.get("filepath")
                    await run_containment(ws, process, filepath)
            except Exception as e:
                print(f"[EDR Client] Error parsing backend command: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[EDR Client] WS command receiver error: {e}")

async def run_containment(ws, process_name, filepath):
    print(f"\n[EDR Containment] INITIATING CONTAINMENT ACTIONS! Culprit Process: '{process_name}', Target File: '{filepath}'")
    
    terminated_count = 0
    denied_count = 0
    details = []
    
    # 1. Process termination logic
    if process_name:
        protected = [
            "python.exe", "python3.exe", "explorer.exe", "cmd.exe", "powershell.exe", "conhost.exe",
            "msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "code.exe", "node.exe",
            "antigravity-ide.exe", "antigravityide.exe"
        ]
        proc_lower = process_name.lower()
        
        for p in psutil.process_iter(['pid', 'name']):
            try:
                p_name = p.info['name']
                if not p_name:
                    continue
                if p_name.lower() == proc_lower:
                    if p.pid == os.getpid():
                        continue
                    if p_name.lower() in protected or "antigravity" in p_name.lower():
                        details.append(f"Skipped protected process {p_name} (PID {p.pid})")
                        continue
                    
                    try:
                        p.suspend()
                        details.append(f"Suspended process {p_name} (PID {p.pid}) for SNN sandbox analysis")
                    except Exception as se:
                        details.append(f"Failed to suspend {p_name}: {str(se)}")
                    
                    p.kill()
                    terminated_count += 1
                    details.append(f"Successfully killed process {p_name} (PID {p.pid})")
            except psutil.AccessDenied:
                denied_count += 1
                details.append(f"Access Denied: Cannot terminate {p_name} (PID {p.pid}) - standard account lacks privileges. Please run client as Administrator.")
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                details.append(f"Error terminating {process_name}: {str(e)}")
                
    # 2. File Quarantine logic
    quarantine_status = "not_applicable"
    if filepath and os.path.exists(filepath):
        # We put the quarantine folder under the root workspace folder, e.g. m:\Spike\quarantine
        quarantine_dir = os.path.join(os.path.dirname(MONITORED_DIR), "quarantine")
        try:
            if not os.path.exists(quarantine_dir):
                os.makedirs(quarantine_dir)
                
            filename = os.path.basename(filepath)
            unique_name = f"{int(time.time())}_{filename}.quarantined"
            dest_path = os.path.join(quarantine_dir, unique_name)
            
            import shutil
            # Safe copy-then-delete move to avoid cross-device problems
            shutil.copy2(filepath, dest_path)
            os.remove(filepath)
            
            quarantine_status = "success"
            details.append(f"Quarantined {filename} to {dest_path}")
        except PermissionError:
            quarantine_status = "access_denied"
            details.append(f"Access Denied: Cannot move file {filepath} - standard account lacks permissions. Please run client as Administrator.")
        except Exception as e:
            quarantine_status = "error"
            details.append(f"Quarantine failed for {filepath}: {str(e)}")
            
    # Determine the status code based on privilege failures
    status = "success"
    if denied_count > 0 or quarantine_status == "access_denied":
        status = "access_denied"
    elif terminated_count == 0 and process_name and denied_count == 0:
        status = "not_found"
    elif quarantine_status == "error":
        status = "error"
        
    report = {
        "type": "containment_report",
        "status": status,
        "process_terminated": terminated_count > 0,
        "terminated_count": terminated_count,
        "quarantine_status": quarantine_status,
        "details": "; ".join(details)
    }
    
    # Send the containment report back to the backend
    try:
        await ws.send(json.dumps(report))
        print(f"[EDR Containment] Sent containment report back to backend. Status: {status.upper()}")
    except Exception as e:
        print(f"[EDR Containment] Error sending containment report to backend: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(delta_filter_loop())
    except KeyboardInterrupt:
        print("\nStopping OS Ingestion Client.")
        thread_monitoring_active = False
        sys.exit(0)
