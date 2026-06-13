import asyncio
import time
import os
import random
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from snn_model import NeuromorphicEngine

MONITORED_DIR = r"m:\Spike\monitored_directory"

app = FastAPI(title="AEGIS-SPIKE Neuromorphic EDR Backend")

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Neuromorphic Engine instance
engine = NeuromorphicEngine()

# Keep track of active dashboard connections and client connections
dashboard_sockets: Set[WebSocket] = set()
lockdown_active = False
simulation_running = False

class StatusResponse(BaseModel):
    lockdown: bool
    calibrated: bool
    calibration_progress: float

@app.get("/api/status", response_model=StatusResponse)
def get_status():
    return {
        "lockdown": lockdown_active,
        "calibrated": engine.calibrated,
        "calibration_progress": min(100.0, (len(engine.membrane_history) / engine.calibration_size) * 100.0)
    }

@app.post("/api/reset")
async def post_reset():
    global lockdown_active
    lockdown_active = False
    engine.reset()
    # Broadcast reset to dashboard
    asyncio.create_task(broadcast_to_dashboards({
        "type": "reset",
        "lockdown": False,
        "calibrated": engine.calibrated,
        "calibration_progress": min(100.0, (len(engine.membrane_history) / engine.calibration_size) * 100.0)
    }))
    return {"status": "ok", "message": "Engine reset complete"}

@app.post("/api/recalibrate")
def post_recalibrate():
    global lockdown_active
    lockdown_active = False
    engine.calibrated = False
    engine.membrane_history.clear()
    engine.mean_mem = None
    engine.std_mem = None
    engine.reset()
    return {"status": "ok", "message": "Recalibration started"}

async def broadcast_to_dashboards(data: dict):
    if not dashboard_sockets:
        return
    disconnected = set()
    for ws in dashboard_sockets:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        dashboard_sockets.remove(ws)

async def handle_processed_step(input_vector, simulated_latency=None, filepath="", process=""):
    global lockdown_active
    t0 = time.perf_counter()
    # Process the step
    metrics = engine.process_step(input_vector)
    actual_latency_us = (time.perf_counter() - t0) * 1_000_000
    
    metrics["latency_us"] = simulated_latency if simulated_latency is not None else actual_latency_us
    metrics["input_vector"] = input_vector
    metrics["filepath"] = filepath
    metrics["process"] = process
    
    # Check if lockdown is triggered
    if metrics["alert_triggered"]:
        lockdown_active = True
        
    metrics["lockdown"] = lockdown_active
    metrics["type"] = "metrics"
    
    # Broadcast to frontend dashboard
    await broadcast_to_dashboards(metrics)

@app.post("/api/simulate")
async def post_simulate():
    """Trigger the Zero-Day Ransomware Burst Simulation in the background."""
    global simulation_running
    if simulation_running:
        return {"status": "error", "message": "Simulation already running"}
    
    asyncio.create_task(run_ransomware_burst())
    return {"status": "ok", "message": "Simulation burst started"}

async def run_ransomware_burst():
    global simulation_running, lockdown_active
    simulation_running = True
    
    # Broadcast warning to dashboard that simulation is starting
    await broadcast_to_dashboards({
        "type": "log",
        "message": "!!! SIMULATOR: INJECTING ZERO-DAY RANSOMWARE BURST !!!"
    })
    
    # Ransomware behavior: High-frequency bursts of activity
    for i in range(100):
        # Continuous high activity pattern (95% chance of spikes)
        file_io_spike = 1 if random.random() < 0.95 else 0
        thread_spike = 1 if random.random() < 0.95 else 0
        pulse = [file_io_spike, thread_spike]
        
        filepath = f"C:\\Users\\Sapra\\Documents\\sensitive_file_{i}.xlsx" if file_io_spike else ""
        process = "ransomware_burst.exe" if thread_spike else ""
        
        await handle_processed_step(pulse, filepath=filepath, process=process)
        
        # Compress intervals violently (simulate 5-10ms delay between actions)
        await asyncio.sleep(0.01)
        
        # Break early if lockdown is triggered to simulate stopping the threat
        if lockdown_active:
            await broadcast_to_dashboards({
                "type": "log",
                "message": f"!!! LOCKDOWN ENGAGED AT ITERATION {i+1} !!! Threat neutralized."
              })
            break
            
    simulation_running = False

@app.get("/api/files")
def get_files():
    if not os.path.exists(MONITORED_DIR):
        return {"files": []}
    
    files_list = []
    try:
        for f in os.listdir(MONITORED_DIR):
            file_path = os.path.join(MONITORED_DIR, f)
            if os.path.isfile(file_path):
                files_list.append({
                    "name": f,
                    "locked": f.endswith(".locked"),
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
    except Exception as e:
        print(f"Error reading files: {e}")
    # Sort alphabetically so order is stable
    files_list.sort(key=lambda x: x["name"])
    return {"files": files_list}

@app.post("/api/generate-files")
async def generate_files():
    if not os.path.exists(MONITORED_DIR):
        os.makedirs(MONITORED_DIR)
        
    # First, clean existing files in the directory
    for file in os.listdir(MONITORED_DIR):
        file_path = os.path.join(MONITORED_DIR, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception:
            pass
            
    # 1. Generate customer_database.db SQLite file
    db_path_cust = os.path.join(MONITORED_DIR, "customer_database.db")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path_cust)
        c = conn.cursor()
        c.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, company TEXT, phone TEXT)")
        customers = [
            ("Alice Johnson", "alice.j@innovatech.com", "InnovaTech", "+1-555-0199"),
            ("Bob Smith", "b.smith@cybershield.net", "CyberShield", "+1-555-0142"),
            ("Charlie Brown", "charlie.b@apexcorp.org", "Apex Corp", "+1-555-0185"),
            ("David Miller", "d.miller@quantumsolutions.io", "Quantum Solutions", "+1-555-0177"),
            ("Emma Davis", "emma.davis@financesync.com", "FinanceSync", "+1-555-0121")
        ]
        c.executemany("INSERT INTO customers (name, email, company, phone) VALUES (?, ?, ?, ?)", customers)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating customer_database.db: {e}")

    # 2. Generate user_credentials.db SQLite file
    db_path_user = os.path.join(MONITORED_DIR, "user_credentials.db")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path_user)
        c = conn.cursor()
        c.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, role TEXT, last_login TEXT)")
        users = [
            ("admin", "pbkdf2:sha256:600000$admin_salt$9b0a1f0d3...", "Administrator", "2026-06-13 10:22:15"),
            ("analyst_01", "pbkdf2:sha256:600000$analyst_salt$4c8f92...", "SecurityAnalyst", "2026-06-13 14:15:30"),
            ("operator_05", "pbkdf2:sha256:600000$operator_salt$e5d3c8...", "SystemOperator", "2026-06-12 18:44:12")
        ]
        c.executemany("INSERT INTO users (username, password_hash, role, last_login) VALUES (?, ?, ?, ?)", users)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating user_credentials.db: {e}")

    # 3. Generate text-based mock files with realistic data
    file_contents = {
        "employee_records.csv": (
            "EmployeeID,Name,Department,Email,Salary,Status\n"
            "EMP001,Sarah Jenkins,Engineering,sarah.j@aegisedr.internal,135000,Active\n"
            "EMP002,Michael Chang,Security,m.chang@aegisedr.internal,142000,Active\n"
            "EMP003,Jessica Taylor,Marketing,jessica.t@aegisedr.internal,85000,Active\n"
            "EMP004,David Ross,Finance,d.ross@aegisedr.internal,115000,Active\n"
            "EMP005,Amanda Martinez,Operations,amanda.m@aegisedr.internal,92000,Active"
        ),
        "annual_budget.xlsx": (
            "Category,Q1_Budget,Q1_Actual,Q2_Budget,Q2_Actual,Variance\n"
            "Infrastructure,45000,43200,48000,0,1800\n"
            "Personnel,120000,121500,125000,0,-1500\n"
            "Licensing,15000,14850,15000,0,150\n"
            "Travel,8000,9200,8000,0,-1200\n"
            "Marketing,25000,24600,30000,0,400"
        ),
        "payroll_q2.xlsx": (
            "PayPeriod,GrossSalary,Taxes,Deductions,NetPay,Status\n"
            "2026-04-15,64500.00,18500.00,3200.00,42800.00,Disbursed\n"
            "2026-04-30,64500.00,18500.00,3200.00,42800.00,Disbursed\n"
            "2026-05-15,65200.00,18700.00,3250.00,43250.00,Disbursed\n"
            "2026-05-30,65200.00,18700.00,3250.00,43250.00,Disbursed\n"
            "2026-06-15,65800.00,18900.00,3300.00,43600.00,Pending"
        ),
        "inventory_list.xlsx": (
            "ItemID,ItemName,Quantity,UnitPrice,Supplier,Category\n"
            "INV-091,Edge Threat Sensor v4,120,450.00,CyberHardware Ltd,Hardware\n"
            "INV-092,LIF Core Module (SNN),40,1200.00,NeuroSilicon Corp,Hardware\n"
            "INV-093,Category-6 Ethernet 100m,15,85.00,Global Cables,Network\n"
            "INV-094,Rack Mount Chassis 2U,8,220.00,ServerRack Inc,Hardware"
        ),
        "financial_report.xlsx": (
            "Metrics,Fiscal_2024,Fiscal_2025,YoY_Growth_Pct\n"
            "Total Revenue,4850000,5620000,15.87\n"
            "Operating Costs,3120000,3450000,10.57\n"
            "Research & Dev,650000,880000,35.38\n"
            "Net Profit Margin,18.2,21.5,18.13"
        ),
        "server_configuration.yaml": (
            "server:\n"
            "  host: 127.0.0.1\n"
            "  port: 8000\n"
            "  workers: 4\n"
            "  timeout: 60\n"
            "database:\n"
            "  engine: sqlite\n"
            "  path: m:/Spike/monitored_directory/customer_database.db\n"
            "security:\n"
            "  lockdown_threshold: 4.0\n"
            "  alert_email: security-ops@aegisedr.internal\n"
            "  retries: 3\n"
            "  logging:\n"
            "    level: INFO\n"
            "    output: console"
        ),
        "api_documentation.md": (
            "# AEGIS-SPIKE Core Agent API Documentation\n\n"
            "This repository manages the EDR threat detection pipelines.\n\n"
            "## Ingress API Pathways\n\n"
            "### 1. Ingress Status\n"
            "`GET /api/status`\n"
            "Returns engine calibration progress, system locking, and active guard metrics.\n\n"
            "### 2. Simulation Trigger\n"
            "`POST /api/simulate-attack`\n"
            "Initiates safe local directory encryption scans for validation testing."
        ),
        "corporate_strategy.docx": (
            "AEGIS CORPORATION STRATEGIC INITIATIVES (2026-2028)\n"
            "===================================================\n"
            "Focus Area 1: Deep edge neuromorphic integration.\n"
            "Deploy SNN models directly onto hardware-level ASIC accelerators to drop latency below 5us.\n"
            "Focus Area 2: Autonomous endpoint self-healing.\n"
            "Expand local file restoration indices using cryptographic shadow backups to guarantee zero loss."
        ),
        "hiring_plan.docx": (
            "AEGIS SECURITY Q3-Q4 HIRING REQUISITION PLAN\n\n"
            "- Senior Neuromorphic Research Scientist (2 open roles) - Focus on snnTorch LIF models.\n"
            "- Senior Endpoint EDR Developer (3 open roles) - Focus on low-level process monitoring.\n"
            "- Threat Intel Response Specialist (1 open role) - Focus on zero-day behavior analysis."
        ),
        "branding_guide.pdf": (
            "AEGIS BRAND IDENTITY & COLOR DESIGN SYSTEM\n\n"
            "Core Color Palette:\n"
            "- Primary Cyber Cyan: #00f0ff (Represents active scanning and signals)\n"
            "- Warning Neon Yellow: #ffb300 (Represents membrane potential warnings)\n"
            "- Critical Alarm Red: #ff3b30 (Represents system lockdowns)\n"
            "- Success Bio Green: #39ff14 (Represents baseline normal telemetry)"
        ),
        "patent_draft.pdf": (
            "PATENT APPLICATION DRAFT: AUTONOMOUS TEMPORAL BEHAVIOR ANALYSIS\n\n"
            "Inventor: Aegis EDR Engineering Team\n"
            "Abstract: This invention relates to methods for detecting polymorphic threats by feeding host system event intervals into an online-learning Leaky Integrate-and-Fire spiking neural network, calculating Shannon Entropy changes, and halting process thread streams when statistical z-score bounds are breached."
        ),
        "legal_contracts.pdf": (
            "MUTUAL NON-DISCLOSURE AGREEMENT (NDA)\n\n"
            "This Agreement is entered into between Aegis EDR Inc. and partner entities.\n"
            "Purpose: To allow collaborative research and testing of online-learning EDR neuromorphic systems without exposing proprietary weights and network model architecture details."
        ),
        "press_release.txt": (
            "FOR IMMEDIATE RELEASE: AEGIS EDR LAUNCHES COGNITIVE NEUROMORPHIC PROTECTION\n\n"
            "SAN JOSE, CA - Aegis EDR today announced the launch of AEGIS-SPIKE, the first cybersecurity software utilizing biological spiking neural networks (SNNs) on CPU/GPU endpoints to defeat zero-day polymorphic ransomware at the edge with zero external network dependencies."
        ),
        "product_roadmap.pptx": (
            "AEGIS-SPIKE PRODUCT DEVELOPMENT ROADMAP\n"
            "----------------------------------------\n"
            "Milestone 1 (Q3 2026): Ingest client integration with Windows Event Tracing (ETW).\n"
            "Milestone 2 (Q4 2026): Linux kernel eBPF driver implementation.\n"
            "Milestone 3 (Q1 2027): Hardware-level ASIC neuromorphic accelerator support."
        ),
        "keynote_presentation.pptx": (
            "NEUROMORPHIC EDGE EDR KEYNOTE PRESENTATION\n\n"
            "Slide 1: The Zero-Day Threat Dilemma (Signature databases are too slow).\n"
            "Slide 2: Enter Spiking Neural Networks (Evaluating behavior through temporal interval compression).\n"
            "Slide 3: Real-Time Results (EDR response times under 100 microseconds, stopping threat execution)."
        ),
        "marketing_assets.zip": (
            "Archive: marketing_assets.zip\n"
            "  Files:\n"
            "   - logo_neon.png (104 KB)\n"
            "   - product_brochure.pdf (2.4 MB)\n"
            "   - intro_video_draft.mp4 (45 MB)"
        ),
        "source_code_backup.zip": (
            "Archive: source_code_backup.zip\n"
            "  Files:\n"
            "   - snn_model.py (13.2 KB)\n"
            "   - ingest_client.py (5.6 KB)\n"
            "   - main.py (6.7 KB)\n"
            "   - config.json (1.2 KB)"
        ),
        "design_mockups.fig": (
            "FIGMA DESIGN FILE: AEGIS-SPIKE COMMAND CONSOLE v2\n\n"
            "Artboards:\n"
            " 1. Main Dashboard Grid (Dark theme, HSL vibrant nodes)\n"
            " 2. Synaptic Weights Matrix Overlay\n"
            " 3. Interactive Incident Report Exporter"
        )
    }

    for name, content in file_contents.items():
        full_path = os.path.join(MONITORED_DIR, name)
        try:
            with open(full_path, "w") as f:
                f.write(content)
        except Exception as e:
            print(f"Error generating file {name}: {e}")
            
    asyncio.create_task(broadcast_to_dashboards({
        "type": "files_update",
        "files": get_files()["files"]
    }))
    
    return {"status": "ok", "message": "Generated 20 clean test files in monitored directory."}

class AttackRequest(BaseModel):
    profile: str = "ransomware"

attack_running = False

@app.post("/api/simulate-attack")
async def post_simulate_attack(req: AttackRequest):
    global attack_running, lockdown_active
    if attack_running:
        return {"status": "error", "message": "Simulation already running"}
        
    # Auto reset if system is locked down
    if lockdown_active:
        await post_restore_files()
        
    # Auto configure files if empty
    if not os.path.exists(MONITORED_DIR) or len([f for f in os.listdir(MONITORED_DIR) if os.path.isfile(os.path.join(MONITORED_DIR, f))]) == 0:
        await generate_files()
        
    asyncio.create_task(run_profiled_attack(req.profile))
    return {"status": "ok", "message": f"{req.profile.upper()} threat simulation initiated"}

async def run_profiled_attack(profile: str):
    global attack_running
    attack_running = True
    
    await broadcast_to_dashboards({
        "type": "log",
        "message": f"!!! WARNING: EDR SIMULATION COMMENCING - PROFILE: {profile.upper()} !!!"
    })
    
    if not os.path.exists(MONITORED_DIR):
        attack_running = False
        return
        
    if profile == "ransomware":
        files_to_encrypt = [f for f in os.listdir(MONITORED_DIR) if not f.endswith(".locked")]
        random.shuffle(files_to_encrypt)
        
        for file in files_to_encrypt:
            if lockdown_active:
                await broadcast_to_dashboards({
                    "type": "log",
                    "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! cryptowrecker.exe isolated."
                })
                break
                
            old_path = os.path.join(MONITORED_DIR, file)
            new_path = os.path.join(MONITORED_DIR, f"{file}.locked")
            
            try:
                if os.path.exists(old_path):
                    with open(old_path, "r") as f:
                        content = f.read()
                    with open(new_path, "w") as f:
                        f.write(f"ENCRYPTED_BY_RANSOMWARE_SIMULATION_{random.randint(1000, 9999)}\n" + content[::-1])
                    os.remove(old_path)
                    
                    await broadcast_to_dashboards({
                        "type": "log",
                        "message": f"ATTACKER: Encrypted file {file} -> {file}.locked"
                    })
                    
                    await broadcast_to_dashboards({
                        "type": "files_update",
                        "files": get_files()["files"]
                    })
                    
                    await handle_processed_step([1, 1], filepath=old_path, process="cryptowrecker.exe")
            except Exception as e:
                print(f"Error encrypting file: {e}")
                
            await asyncio.sleep(0.12)
            
    elif profile == "spyware":
        files_to_harvest = [f for f in os.listdir(MONITORED_DIR) if not f.endswith(".locked")]
        random.shuffle(files_to_harvest)
        
        for file in files_to_harvest:
            if lockdown_active:
                await broadcast_to_dashboards({
                    "type": "log",
                    "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! spyharvest.dll isolated."
                })
                break
                
            file_path = os.path.join(MONITORED_DIR, file)
            try:
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        _ = f.read()
                        
                    await broadcast_to_dashboards({
                        "type": "log",
                        "message": f"ATTACKER: Harvested sensitive data from {file}"
                    })
                    
                    await handle_processed_step([1, 0], filepath=file_path, process="spyharvest.dll")
            except Exception as e:
                print(f"Error reading file: {e}")
                
            await asyncio.sleep(0.45)
            
    elif profile == "fork_bomb":
        interval = 0.15
        for i in range(40):
            if lockdown_active:
                await broadcast_to_dashboards({
                    "type": "log",
                    "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! process_spawn.sh terminated."
                })
                break
                
            await broadcast_to_dashboards({
                "type": "log",
                "message": f"ATTACKER: Forked child process [PID: {random.randint(1000, 9999)}] -> Thread count: {i*8 + 10}"
            })
            
            await handle_processed_step([0, 1], filepath="", process="process_spawn.sh")
            
            interval = max(0.01, interval * 0.85)
            await asyncio.sleep(interval)
            
    elif profile == "delayed_crypto":
        # Slow-periodic file encryption to evade simple burst detectors
        files_to_encrypt = [f for f in os.listdir(MONITORED_DIR) if not f.endswith(".locked")]
        random.shuffle(files_to_encrypt)
        
        for file in files_to_encrypt:
            if lockdown_active:
                await broadcast_to_dashboards({
                    "type": "log",
                    "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! delayed_crypto.exe isolated."
                })
                break
                
            old_path = os.path.join(MONITORED_DIR, file)
            new_path = os.path.join(MONITORED_DIR, f"{file}.locked")
            
            try:
                if os.path.exists(old_path):
                    with open(old_path, "r") as f:
                        content = f.read()
                    with open(new_path, "w") as f:
                        f.write(f"ENCRYPTED_BY_DELAYED_CRYPTO_SIMULATION_{random.randint(1000, 9999)}\n" + content[::-1])
                    os.remove(old_path)
                    
                    await broadcast_to_dashboards({
                        "type": "log",
                        "message": f"ATTACKER: Encrypted file {file} -> {file}.locked (delayed scan)"
                    })
                    
                    await broadcast_to_dashboards({
                        "type": "files_update",
                        "files": get_files()["files"]
                    })
                    
                    await handle_processed_step([1, 1], filepath=old_path, process="delayed_crypto.exe")
            except Exception as e:
                print(f"Error encrypting file: {e}")
                
            await asyncio.sleep(1.2)
            
    elif profile == "dropper":
        # 5 rapid process/thread spikes representing downloader/installer activity
        for i in range(5):
            if lockdown_active:
                await broadcast_to_dashboards({
                    "type": "log",
                    "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! dropper.exe isolated."
                })
                break
            await broadcast_to_dashboards({
                "type": "log",
                "message": f"ATTACKER: dropper.exe executing setup subprocess {i+1}/5..."
            })
            await handle_processed_step([0, 1], filepath="", process="dropper.exe")
            await asyncio.sleep(0.1)
            
        # 15 rapid file spikes representing unpacking/dropping of binary payloads
        if not lockdown_active:
            for i in range(15):
                if lockdown_active:
                    await broadcast_to_dashboards({
                        "type": "log",
                        "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! dropper.exe payload extraction blocked."
                    })
                    break
                payload_name = f"extracted_payload_{i+1}.bin"
                payload_path = os.path.join(MONITORED_DIR, payload_name)
                try:
                    with open(payload_path, "w") as f:
                        f.write(f"MZ_MOCK_PAYLOAD_DATA_{random.randint(1000, 9999)}")
                    await broadcast_to_dashboards({
                        "type": "log",
                        "message": f"ATTACKER: dropper.exe extracted payload {payload_name} to monitored folder"
                    })
                    await broadcast_to_dashboards({
                        "type": "files_update",
                        "files": get_files()["files"]
                    })
                    await handle_processed_step([1, 0], filepath=payload_path, process="dropper.exe")
                except Exception as e:
                    print(f"Error dropping file: {e}")
                await asyncio.sleep(0.1)
                
    elif profile == "net_worm":
        # 30 steady thread/socket creation spikes
        for i in range(30):
            if lockdown_active:
                await broadcast_to_dashboards({
                    "type": "log",
                    "message": "!!! EDR LOCKDOWN SHIELD ENGAGED !!! net_worm.exe isolated."
                })
                break
            await broadcast_to_dashboards({
                "type": "log",
                "message": f"ATTACKER: net_worm.exe replicating connection socket thread {i+1}/30 on port {random.randint(1024, 65535)}"
            })
            await handle_processed_step([0, 1], filepath="", process="net_worm.exe")
            await asyncio.sleep(0.15)
            
    attack_running = False

@app.post("/api/restore-files")
async def post_restore_files():
    global lockdown_active
    lockdown_active = False
    engine.reset()
    
    if not os.path.exists(MONITORED_DIR):
        return {"status": "ok", "message": "Nothing to restore."}
        
    restored_count = 0
    try:
        files = os.listdir(MONITORED_DIR)
        for file in files:
            file_path = os.path.join(MONITORED_DIR, file)
            if file.endswith(".locked"):
                original_name = file[:-7]  # Strip ".locked"
                original_path = os.path.join(MONITORED_DIR, original_name)
                
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        lines = f.readlines()
                    if len(lines) > 1:
                        restored_content = "".join(lines[1:])[::-1]
                    else:
                        restored_content = "AEGIS-SPIKE RESTORED DATA"
                        
                    with open(original_path, "w") as f:
                        f.write(restored_content)
                    os.remove(file_path)
                    restored_count += 1
            elif file.endswith(".bin") or file.startswith("extracted_payload_"):
                if os.path.exists(file_path):
                    os.remove(file_path)
    except Exception as e:
        print(f"Error restoring files: {e}")
        
    # Broadcast reset to dashboards
    asyncio.create_task(broadcast_to_dashboards({
        "type": "reset",
        "lockdown": False,
        "calibrated": engine.calibrated,
        "calibration_progress": min(100.0, (len(engine.membrane_history) / engine.calibration_size) * 100.0),
        "files": get_files()["files"]
    }))
    
    return {"status": "ok", "message": f"Restored {restored_count} files back to clean state. EDR Reset."}

@app.websocket("/ws/client")
async def websocket_client(websocket: WebSocket):
    await websocket.accept()
    print("Ingestion client connected.")
    try:
        while True:
            data = await websocket.receive_json()
            pulse_vector = [0, 0]
            filepath = ""
            process = ""
            
            if isinstance(data, list) and len(data) == 2:
                pulse_vector = data
            elif isinstance(data, dict):
                pulse_vector = data.get("spike", [0, 0])
                filepath = data.get("filepath", "")
                process = data.get("process", "")
            else:
                continue

            # If lockdown is active, we don't process further client events or we show them as blocked
            if lockdown_active:
                start_time = time.perf_counter()
                latency_us = (time.perf_counter() - start_time) * 1_000_000
                await broadcast_to_dashboards({
                    "type": "metrics_blocked",
                    "input_vector": pulse_vector,
                    "filepath": filepath,
                    "process": process,
                    "lockdown": True,
                    "latency_us": latency_us
                })
                continue
            
            # Perform SNN update and broadcast metrics
            await handle_processed_step(pulse_vector, filepath=filepath, process=process)
                
    except WebSocketDisconnect:
        print("Ingestion client disconnected.")
    except Exception as e:
        print(f"Error in client WebSocket: {e}")

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    dashboard_sockets.add(websocket)
    print(f"Dashboard connected. Total dashboards: {len(dashboard_sockets)}")
    
    # Send initial status
    await websocket.send_json({
        "type": "init",
        "lockdown": lockdown_active,
        "calibrated": engine.calibrated,
        "calibration_progress": min(100.0, (len(engine.membrane_history) / engine.calibration_size) * 100.0),
        "files": get_files()["files"]
    })
    
    try:
        while True:
            # Keep socket alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_sockets.remove(websocket)
        print("Dashboard disconnected.")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info")
