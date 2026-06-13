import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// LaTeX formula strings to avoid compilation escapes
const SPARSITY_FORMULA = "S = \\\\left( 1 - \\\\frac{\\\\sum_{t=1}^{T} \\\\sum_{i=1}^{N} s_i(t)}{N \\\\times T} \\\\right) \\\\times 100";
const ENTROPY_FORMULA = "H(X) = - \\\\sum_{i} P(s_i) \\\\log_2 P(s_i)";
const ZSCORE_FORMULA = "z_i = \\\\frac{v_i - \\\\mu_i}{\\\\sigma_i} \\\\quad ; \\\\quad Z = \\\\frac{1}{M} \\\\sum_{i} |z_i|";
const LATENCY_FORMULA = "T_p = t_{end} - t_{start}";

// Cyberpunk color palette
const COLORS = {
  cyan: '#00f0ff',
  green: '#39ff14',
  yellow: '#ffb300',
  red: '#ff3b30',
  purple: '#af40ff',
  grid: 'rgba(255, 255, 255, 0.05)',
  textMuted: '#8a9cae'
};

// Pure Web Audio Synth Sound Engine (No assets required, synthesised on the fly)
const SoundSynth = {
  ctx: null,
  
  init() {
    if (!this.ctx) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
  },
  
  playHum() {
    this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    
    // Background cyber startup hum (low frequency sawtooth with low-pass sweep)
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    const filter = this.ctx.createBiquadFilter();
    
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(55, this.ctx.currentTime); // A1 note
    
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(100, this.ctx.currentTime);
    filter.frequency.exponentialRampToValueAtTime(300, this.ctx.currentTime + 1.5);
    
    gain.gain.setValueAtTime(0.015, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + 2.5);
    
    osc.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);
    
    osc.start();
    osc.stop(this.ctx.currentTime + 2.5);
  },
  
  playClick() {
    this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    
    // Cyber tech click sound
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    
    osc.type = 'sine';
    osc.frequency.setValueAtTime(900, this.ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(200, this.ctx.currentTime + 0.07);
    
    gain.gain.setValueAtTime(0.03, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + 0.07);
    
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    
    osc.start();
    osc.stop(this.ctx.currentTime + 0.07);
  },
  
  playSiren() {
    this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    
    // Pulsating cyber lock alert siren (dual oscillator modulated)
    const osc1 = this.ctx.createOscillator();
    const osc2 = this.ctx.createOscillator();
    const gain1 = this.ctx.createGain();
    const gain2 = this.ctx.createGain();
    
    osc1.type = 'sawtooth';
    osc2.type = 'square';
    
    const t = this.ctx.currentTime;
    osc1.frequency.setValueAtTime(220, t);
    osc2.frequency.setValueAtTime(223, t);
    
    osc1.frequency.linearRampToValueAtTime(380, t + 0.3);
    osc1.frequency.linearRampToValueAtTime(220, t + 0.6);
    osc1.frequency.linearRampToValueAtTime(380, t + 0.9);
    osc1.frequency.linearRampToValueAtTime(220, t + 1.2);
    
    osc2.frequency.linearRampToValueAtTime(385, t + 0.3);
    osc2.frequency.linearRampToValueAtTime(225, t + 0.6);
    osc2.frequency.linearRampToValueAtTime(385, t + 0.9);
    osc2.frequency.linearRampToValueAtTime(225, t + 1.2);
    
    gain1.gain.setValueAtTime(0.015, t);
    gain2.gain.setValueAtTime(0.008, t);
    gain1.gain.linearRampToValueAtTime(0.0001, t + 1.4);
    gain2.gain.linearRampToValueAtTime(0.0001, t + 1.4);
    
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(500, t);
    
    osc1.connect(filter);
    osc2.connect(filter);
    filter.connect(gain1);
    gain1.connect(this.ctx.destination);
    
    osc1.start();
    osc2.start();
    osc1.stop(t + 1.4);
    osc2.stop(t + 1.4);
  },
  
  playChime() {
    this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    
    // Server flush reset chime (arpeggio sequence)
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    
    osc.type = 'sine';
    const t = this.ctx.currentTime;
    osc.frequency.setValueAtTime(523.25, t); // C5
    osc.frequency.setValueAtTime(659.25, t + 0.08); // E5
    osc.frequency.setValueAtTime(783.99, t + 0.16); // G5
    osc.frequency.setValueAtTime(1046.50, t + 0.24); // C6
    
    gain.gain.setValueAtTime(0.025, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.7);
    
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    
    osc.start();
    osc.stop(t + 0.7);
  }
};

function App() {
  const [lockdown, setLockdown] = useState(false);
  const [calibrated, setCalibrated] = useState(false);
  const [calibrationProgress, setCalibrationProgress] = useState(0.0);
  
  // Real-time metric states
  const [sparsity, setSparsity] = useState(100.0);
  const [entropy, setEntropy] = useState(0.0);
  const [zScore, setZScore] = useState(0.0);
  const [latency, setLatency] = useState(0.0);
  
  // Endpoint files state
  const [files, setFiles] = useState([]);
  const [attackingProcess, setAttackingProcess] = useState('');
  const [attackedFilePath, setAttackedFilePath] = useState('');
  
  // Simulation config
  const [attackProfile, setAttackProfile] = useState('ransomware');
  const [showReport, setShowReport] = useState(false);
  
  // Historical logs and WebSocket status
  const [logs, setLogs] = useState([]);
  const [wsStatus, setWsStatus] = useState('connecting');
  
  // Canvas refs
  const snnCanvasRef = useRef(null);
  const heatmapCanvasRef = useRef(null);
  const entropyCanvasRef = useRef(null);
  const zScoreCanvasRef = useRef(null);
  
  // Historical buffers
  const entropyHistoryRef = useRef([]);
  const zScoreHistoryRef = useRef([]);
  
  // Cache for SNN weights and spiking states
  const lastSNNDataRef = useRef({
    spk1: Array(16).fill(0),
    mem1: Array(16).fill(0),
    spk2: Array(2).fill(0),
    mem2: Array(2).fill(0),
    weights_fc1: Array(16).fill().map(() => [0, 0]),
    weights_fc2: Array(2).fill().map(() => Array(16).fill(0))
  });
  
  // API details
  const BASE_URL = 'http://127.0.0.1:8000';
  const WS_URL = 'ws://127.0.0.1:8000/ws/dashboard';
  
  // Logger helper
  const addLog = (message, isError = false) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [
      { text: message, timestamp, isError },
      ...prev.slice(0, 99)
    ]);
  };
  
  // Fetch file list
  const fetchFiles = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/files`);
      const data = await res.json();
      if (data.files) {
        setFiles(data.files);
      }
    } catch (e) {
      console.error("Failed to fetch files list", e);
    }
  };

  // Connect WebSockets and poll initial status
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;
    
    function connect() {
      setWsStatus('connecting');
      ws = new WebSocket(WS_URL);
      
      ws.onopen = () => {
        setWsStatus('connected');
        SoundSynth.playHum();
        addLog("EDR Terminal: Established core data connection to SNN backend.");
        fetchFiles();
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'init') {
            setLockdown(data.lockdown);
            setCalibrated(data.calibrated);
            setCalibrationProgress(data.calibration_progress);
            if (data.files) {
              setFiles(data.files);
            }
            addLog(`System Ingress Online. Model Calibrated: ${data.calibrated}`);
          }
          else if (data.type === 'reset') {
            setLockdown(data.lockdown);
            setCalibrated(data.calibrated);
            setCalibrationProgress(data.calibration_progress);
            setAttackingProcess('');
            setAttackedFilePath('');
            if (data.files) {
              setFiles(data.files);
            }
            entropyHistoryRef.current = [];
            zScoreHistoryRef.current = [];
            
            // Reset cache
            lastSNNDataRef.current = {
              spk1: Array(16).fill(0),
              mem1: Array(16).fill(0),
              spk2: Array(2).fill(0),
              mem2: Array(2).fill(0),
              weights_fc1: Array(16).fill().map(() => [0, 0]),
              weights_fc2: Array(2).fill().map(() => Array(16).fill(0))
            };
            
            drawSNNPlot(
              lastSNNDataRef.current.spk1,
              lastSNNDataRef.current.mem1,
              lastSNNDataRef.current.spk2,
              lastSNNDataRef.current.mem2,
              lastSNNDataRef.current.weights_fc1,
              lastSNNDataRef.current.weights_fc2,
              [0, 0]
            );
            drawHeatmapPlot(lastSNNDataRef.current.weights_fc1);
            
            addLog("EDR Command: Agent state and baseline memory flushed.");
          }
          else if (data.type === 'log') {
            const isCritical = data.message.includes('!!!');
            addLog(data.message, isCritical);
          }
          else if (data.type === 'files_update') {
            if (data.files) {
              setFiles(data.files);
            }
          }
          else if (data.type === 'metrics' || data.type === 'metrics_blocked') {
            // Update metrics
            setSparsity(data.sparsity ?? 100);
            setEntropy(data.shannon_entropy ?? 0);
            setZScore(data.z_score_deviation ?? 0);
            setLatency(data.latency_us ?? 0);
            setLockdown(data.lockdown ?? false);
            setCalibrated(data.calibrated ?? false);
            setCalibrationProgress(data.calibration_progress ?? 0);
            
            // Set metadata
            if (data.process) setAttackingProcess(data.process);
            if (data.filepath) setAttackedFilePath(data.filepath);
            
            // Push values to sparklines
            entropyHistoryRef.current.push(data.shannon_entropy ?? 0);
            if (entropyHistoryRef.current.length > 50) entropyHistoryRef.current.shift();
            
            zScoreHistoryRef.current.push(data.z_score_deviation ?? 0);
            if (zScoreHistoryRef.current.length > 50) zScoreHistoryRef.current.shift();
            
            // Cache SNN structural data
            const inputVector = data.input_vector || [0, 0];
            lastSNNDataRef.current = {
              spk1: data.spk1 || lastSNNDataRef.current.spk1,
              mem1: data.mem1 || lastSNNDataRef.current.mem1,
              spk2: data.spk2 || lastSNNDataRef.current.spk2,
              mem2: data.mem2 || lastSNNDataRef.current.mem2,
              weights_fc1: data.weights_fc1 || lastSNNDataRef.current.weights_fc1,
              weights_fc2: data.weights_fc2 || lastSNNDataRef.current.weights_fc2
            };
            
            // Render plots
            drawEntropyPlot();
            drawZScorePlot();
            drawSNNPlot(
              lastSNNDataRef.current.spk1,
              lastSNNDataRef.current.mem1,
              lastSNNDataRef.current.spk2,
              lastSNNDataRef.current.mem2,
              lastSNNDataRef.current.weights_fc1,
              lastSNNDataRef.current.weights_fc2,
              inputVector
            );
            drawHeatmapPlot(lastSNNDataRef.current.weights_fc1);
            
            if (data.alert_triggered) {
              SoundSynth.playSiren();
              setShowReport(true);
              addLog(`🚨 NEUROMORPHIC ALARM: Spatial-temporal shift detected! Entropy: ${data.shannon_entropy.toFixed(3)} | Z-Score: ${data.z_score_deviation.toFixed(2)} | Latency: ${data.latency_us.toFixed(1)} µs`, true);
            }
          }
        } catch (e) {
          console.error("Failed to parse websocket payload", e);
        }
      };
      
      ws.onclose = () => {
        setWsStatus('disconnected');
        addLog("EDR Terminal: connection closed by host. Retrying in 2s...", true);
        reconnectTimeout = setTimeout(connect, 2000);
      };
      
      ws.onerror = (err) => {
        ws.close();
      };
    }
    
    connect();
    
    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [attackProfile]);

  // Visualizers: Sparklines & Graphs
  const drawEntropyPlot = () => {
    const canvas = entropyCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.clientWidth;
    const height = canvas.height = canvas.clientHeight;
    
    ctx.clearRect(0, 0, width, height);
    
    const history = entropyHistoryRef.current;
    if (history.length < 2) return;
    
    const maxVal = 1.0;
    const points = history.map((val, idx) => ({
      x: (idx / (history.length - 1)) * width,
      y: height - ((val / maxVal) * (height - 8)) - 4
    }));
    
    ctx.strokeStyle = COLORS.cyan;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.stroke();
    
    ctx.fillStyle = 'rgba(0, 240, 255, 0.08)';
    ctx.lineTo(points[points.length - 1].x, height);
    ctx.lineTo(points[0].x, height);
    ctx.closePath();
    ctx.fill();
  };
  
  const drawZScorePlot = () => {
    const canvas = zScoreCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.clientWidth;
    const height = canvas.height = canvas.clientHeight;
    
    ctx.clearRect(0, 0, width, height);
    
    const history = zScoreHistoryRef.current;
    if (history.length < 2) return;
    
    const maxVal = 8.0;
    const points = history.map((val, idx) => ({
      x: (idx / (history.length - 1)) * width,
      y: height - ((Math.min(val, maxVal) / maxVal) * (height - 8)) - 4
    }));
    
    const isHigh = zScore > 4.0;
    ctx.strokeStyle = isHigh ? COLORS.red : COLORS.yellow;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.stroke();
    
    ctx.fillStyle = isHigh ? 'rgba(255, 59, 48, 0.08)' : 'rgba(255, 179, 0, 0.06)';
    ctx.lineTo(points[points.length - 1].x, height);
    ctx.lineTo(points[0].x, height);
    ctx.closePath();
    ctx.fill();
  };

  const drawSNNPlot = (spk1, mem1, spk2, mem2, w1, w2, input_vector) => {
    const canvas = snnCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.clientWidth;
    const height = canvas.height = canvas.clientHeight;
    
    ctx.fillStyle = '#020305';
    ctx.fillRect(0, 0, width, height);
    
    const inputX = width * 0.12;
    const hiddenX = width * 0.5;
    const outputX = width * 0.88;
    
    const inputNodes = [
      { name: 'FILE I/O', x: inputX, y: height * 0.35, active: input_vector[0] === 1, color: COLORS.green },
      { name: 'THREADS', x: inputX, y: height * 0.65, active: input_vector[1] === 1, color: COLORS.cyan }
    ];
    
    const hiddenNodes = [];
    const numHidden = 16;
    for (let i = 0; i < numHidden; i++) {
      const y = height * (0.06 + 0.88 * i / (numHidden - 1));
      hiddenNodes.push({
        x: hiddenX,
        y: y,
        spike: spk1 ? spk1[i] === 1 : false,
        mem: mem1 ? mem1[i] : 0.0
      });
    }
    
    const outputNodes = [
      { name: 'ANOMALY', x: outputX, y: height * 0.35, spike: spk2 ? spk2[0] === 1 : false, mem: mem2 ? mem2[0] : 0, color: COLORS.red },
      { name: 'SPARSITY', x: outputX, y: height * 0.65, spike: spk2 ? spk2[1] === 1 : false, mem: mem2 ? mem2[1] : 0, color: COLORS.yellow }
    ];
    
    // Draw Synaptic Connections: Input -> Hidden
    if (w1) {
      for (let i = 0; i < numHidden; i++) {
        for (let j = 0; j < 2; j++) {
          const weight = w1[i][j];
          const start = inputNodes[j];
          const end = hiddenNodes[i];
          
          ctx.beginPath();
          ctx.moveTo(start.x, start.y);
          ctx.lineTo(end.x, end.y);
          
          const positive = weight >= 0;
          ctx.strokeStyle = positive ? 'rgba(0, 240, 255,' : 'rgba(175, 64, 255,';
          
          const absWeight = Math.abs(weight);
          const alpha = Math.min(0.4, absWeight * 0.7 + 0.03);
          ctx.lineWidth = Math.min(2.5, absWeight * 3 + 0.2);
          ctx.strokeStyle += ` ${alpha})`;
          ctx.stroke();
          
          // Draw signal particles
          if (start.active) {
            const time = (Date.now() / 450) % 1;
            const px = start.x + (end.x - start.x) * time;
            const py = start.y + (end.y - start.y) * time;
            ctx.fillStyle = start.color;
            ctx.beginPath();
            ctx.arc(px, py, 2.5, 0, 2 * Math.PI);
            ctx.fill();
          }
        }
      }
    }
    
    // Draw Synaptic Connections: Hidden -> Output
    if (w2) {
      for (let k = 0; k < 2; k++) {
        for (let i = 0; i < numHidden; i++) {
          const weight = w2[k][i];
          const start = hiddenNodes[i];
          const end = outputNodes[k];
          
          ctx.beginPath();
          ctx.moveTo(start.x, start.y);
          ctx.lineTo(end.x, end.y);
          
          const positive = weight >= 0;
          ctx.strokeStyle = positive ? 'rgba(57, 255, 20,' : 'rgba(255, 59, 48,';
          
          const absWeight = Math.abs(weight);
          const alpha = Math.min(0.4, absWeight * 0.7 + 0.03);
          ctx.lineWidth = Math.min(2.5, absWeight * 3 + 0.2);
          ctx.strokeStyle += ` ${alpha})`;
          ctx.stroke();
          
          if (start.spike) {
            const time = (Date.now() / 350) % 1;
            const px = start.x + (end.x - start.x) * time;
            const py = start.y + (end.y - start.y) * time;
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(px, py, 2.5, 0, 2 * Math.PI);
            ctx.fill();
          }
        }
      }
    }
    
    // Draw Input Neurons
    inputNodes.forEach(node => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
      ctx.fillStyle = node.active ? node.color : '#0d1117';
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 1.5;
      ctx.fill();
      ctx.stroke();
      
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 8px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(node.name, node.x - 12, node.y + 3);
    });
    
    // Draw Hidden LIF Reservoir Neurons
    hiddenNodes.forEach(node => {
      ctx.beginPath();
      const r = Math.max(2.5, 4.5 + node.mem * 4);
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      
      if (node.spike) {
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = COLORS.cyan;
        ctx.lineWidth = 1.5;
        ctx.fill();
        ctx.stroke();
        
        ctx.shadowBlur = 8;
        ctx.shadowColor = '#ffffff';
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 1.5, 0, 2 * Math.PI);
        ctx.stroke();
        ctx.shadowBlur = 0;
      } else {
        const fillAlpha = Math.min(1.0, 0.2 + node.mem * 0.7);
        ctx.fillStyle = `rgba(0, 240, 255, ${fillAlpha})`;
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();
      }
    });
    
    // Draw Output Neurons
    outputNodes.forEach(node => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 9, 0, 2 * Math.PI);
      ctx.fillStyle = node.spike ? node.color : '#0d1117';
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 1.5;
      ctx.fill();
      ctx.stroke();
      
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 8px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(node.name, node.x + 12, node.y + 3);
    });
  };

  const drawHeatmapPlot = (w1) => {
    const canvas = heatmapCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.clientWidth;
    const height = canvas.height = canvas.clientHeight;
    
    ctx.fillStyle = '#020305';
    ctx.fillRect(0, 0, width, height);
    
    if (!w1 || w1.length === 0) return;
    
    const numRows = 16;
    const numCols = 2;
    const cellWidth = width / numCols;
    const cellHeight = height / numRows;
    
    for (let r = 0; r < numRows; r++) {
      for (let c = 0; c < numCols; c++) {
        const val = w1[r][c];
        const positive = val >= 0;
        const absVal = Math.min(1.0, Math.abs(val));
        
        ctx.fillStyle = positive 
          ? `rgba(0, 240, 255, ${absVal})`
          : `rgba(175, 64, 255, ${absVal})`;
          
        ctx.fillRect(c * cellWidth, r * cellHeight, cellWidth - 1, cellHeight - 1);
      }
    }
  };

  // Re-draw canvases if layout updates
  useEffect(() => {
    drawSNNPlot(
      lastSNNDataRef.current.spk1,
      lastSNNDataRef.current.mem1,
      lastSNNDataRef.current.spk2,
      lastSNNDataRef.current.mem2,
      lastSNNDataRef.current.weights_fc1,
      lastSNNDataRef.current.weights_fc2,
      [0, 0]
    );
    drawHeatmapPlot(lastSNNDataRef.current.weights_fc1);
    drawEntropyPlot();
    drawZScorePlot();
  }, [lockdown]);

  // Command handlers
  const handleGenerateFiles = async () => {
    SoundSynth.playClick();
    addLog("EDR Command: Requesting sandbox environment configuration...");
    try {
      const res = await fetch(`${BASE_URL}/api/generate-files`, { method: 'POST' });
      const data = await res.json();
      addLog(data.message);
      fetchFiles();
    } catch (e) {
      addLog("Failed to reach API endpoint /api/generate-files", true);
    }
  };

  const handleSimulateAttack = async () => {
    SoundSynth.playClick();
    addLog(`EDR Command: Initiating simulated ${attackProfile.toUpperCase()} execution thread...`);
    try {
      const res = await fetch(`${BASE_URL}/api/simulate-attack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile: attackProfile })
      });
      const data = await res.json();
      if (data.status === 'error') {
        addLog(data.message, true);
      } else {
        addLog(data.message);
      }
      fetchFiles();
    } catch (e) {
      addLog("Failed to reach API endpoint /api/simulate-attack", true);
    }
  };

  const handleRestoreFiles = async () => {
    SoundSynth.playChime();
    addLog("EDR Command: Injecting roll-back key to restore endpoint files...");
    try {
      const res = await fetch(`${BASE_URL}/api/restore-files`, { method: 'POST' });
      const data = await res.json();
      addLog(data.message);
      setAttackingProcess('');
      setAttackedFilePath('');
      setShowReport(false);
      fetchFiles();
    } catch (e) {
      addLog("Failed to reach API endpoint /api/restore-files", true);
    }
  };

  const handleReset = async () => {
    SoundSynth.playChime();
    addLog("EDR Command: Transmitting RESET directive to agent...");
    try {
      const res = await fetch(`${BASE_URL}/api/reset`, { method: 'POST' });
      const data = await res.json();
      addLog(data.message);
      setAttackingProcess('');
      setAttackedFilePath('');
      setShowReport(false);
      fetchFiles();
    } catch (e) {
      addLog("Failed to reach API endpoint /api/reset", true);
    }
  };

  const handleRecalibrate = async () => {
    SoundSynth.playClick();
    addLog("EDR Command: Triggering SNN baseline recalibration...");
    try {
      const res = await fetch(`${BASE_URL}/api/recalibrate`, { method: 'POST' });
      const data = await res.json();
      addLog(data.message);
      setCalibrated(false);
      setCalibrationProgress(0);
    } catch (e) {
      addLog("Failed to reach API endpoint /api/recalibrate", true);
    }
  };

  // Export EDR report in Markdown format
  const downloadReport = () => {
    SoundSynth.playClick();
    const totalFilesCount = files.length;
    const lockedCount = files.filter(f => f.locked).length;
    const protectedCount = totalFilesCount - lockedCount;
    const rate = totalFilesCount > 0 ? ((protectedCount / totalFilesCount) * 100).toFixed(0) : 100;
    
    const reportContent = `# AEGIS-SPIKE COGNITIVE NEUROMORPHIC EDR REPORT
===================================================
GENERATED: ${new Date().toLocaleString()}
STATUS: Threat Neutralized & Contained

## 1. Executive Summary
The AEGIS-SPIKE Spiking Neural Network (SNN) engine detected a critical spatial-temporal sequence anomaly on this host. Incoming event sequences matching known threat behaviors violated calibrated statistical boundaries of the baseline reservoir model. To prevent system-wide compromise, EDR defensive lockdowns immediately terminated targeted file encryption and thread processes.

## 2. Threat Vector Details
- Target Process: ${attackingProcess || 'unknown'}
- Attack Classification Profile: ${attackProfile.toUpperCase()}
- SNN Inference Clock Speed: ${latency.toFixed(1)} µs
- Monitored Sandbox Directory: m:\\Spike\\monitored_directory

## 3. Cognitive SNN Telemetry Data
- Inference Firing Sparsity: ${sparsity.toFixed(1)}% (Inference Density)
- Shannon Information Entropy: ${entropy.toFixed(4)} (Sequence Dispersion Limit Exceeded)
- LIF Membrane potential Z-Score: ${zScore.toFixed(2)} (Statistical Bounds Limit: 4.00)

## 4. Endpoint Protection Statistics
- Total Sandbox Target Files: ${totalFilesCount}
- Compromised / Encrypted Documents: ${lockedCount}
- Protected / Shielded Documents: ${protectedCount} (${rate}% Protection Index)

## 5. Synaptic Signature Grid
The adaptive SGD backpropagation weight adjustment shifted SNN network parameters to inhibit malicious stimulus.
- Excitatory connection baseline (FC1 Row 0): ${JSON.stringify(lastSNNDataRef.current.weights_fc1[0] || [])}
- Inhibitory connection baseline (FC1 Row 1): ${JSON.stringify(lastSNNDataRef.current.weights_fc1[1] || [])}

===================================================
AEGIS-SPIKE COMMAND CENTER - THREAT INTEGRITY GUARANTEED
`;

    const blob = new Blob([reportContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `AEGIS_SPIKE_THREAT_REPORT_${attackProfile}_${Date.now()}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    addLog("EDR Terminal: Incident report file written to disk successfully.");
  };

  // Stats calculation
  const totalFiles = files.length;
  const lockedFiles = files.filter(f => f.locked).length;
  const protectedFiles = totalFiles - lockedFiles;
  const protectionPercentage = totalFiles > 0 ? ((protectedFiles / totalFiles) * 100).toFixed(0) : 100;

  return (
    <div className={`dashboard-wrapper ${lockdown ? 'lockdown-active' : ''}`}>
      
      {/* HEADER BAR */}
      <header className={`header-bar ${lockdown ? 'lockdown' : ''}`}>
        <div className="title-area">
          <h1 className={lockdown ? 'lockdown' : ''}>
            {lockdown ? '☣ AEGIS-SPIKE :: SECURED_LOCKDOWN' : '🛡 AEGIS-SPIKE :: NEUROMORPHIC_GUARD'}
          </h1>
          <p>Cognitive Neuromorphic Threat Detection & Active Sandbox Protection</p>
        </div>
        
        <div className="control-actions">
          <button className="btn" onClick={handleGenerateFiles} disabled={lockdown}>
            📁 CONFIG SANDBOX
          </button>
          
          <div className="attack-control-group">
            <select 
              className="profile-select" 
              value={attackProfile} 
              onChange={(e) => { SoundSynth.playClick(); setAttackProfile(e.target.value); }}
              disabled={lockdown}
            >
              <option value="ransomware">Ransomware (cryptowrecker)</option>
              <option value="spyware">Spyware (spyharvest)</option>
              <option value="fork_bomb">Fork Bomb (process_spawn)</option>
              <option value="delayed_crypto">Delayed Ransomware (delayed_crypto)</option>
              <option value="dropper">Trojan Dropper (dropper)</option>
              <option value="net_worm">Network Worm (net_worm)</option>
            </select>
            <button className="btn btn-danger" onClick={handleSimulateAttack} style={{ borderTopLeftRadius: 0, borderBottomLeftRadius: 0 }}>
              💥 INJECT ATTACK
            </button>
          </div>

          <button className="btn btn-success" onClick={handleRestoreFiles}>
            ⚡ RECOVER FILES
          </button>
          <button className="btn btn-warning" onClick={handleRecalibrate}>
            🔁 RECALIBRATE
          </button>
          <button className="btn" onClick={handleReset}>
            ⚙ RESET EDR
          </button>
          
          <div className="status-indicator">
            <div className={`status-dot ${
              wsStatus === 'disconnected' ? 'disconnected' :
              lockdown ? 'lockdown' :
              !calibrated ? 'calibrating' : 'active'
            }`} />
            <span className={`status-text ${
              wsStatus === 'disconnected' ? 'disconnected' :
              lockdown ? 'lockdown' :
              !calibrated ? 'calibrating' : 'active'
            }`}>
              {wsStatus === 'disconnected' ? 'OFFLINE' :
               lockdown ? 'LOCKDOWN ENGAGED' :
               !calibrated ? `CALIBRATING (${Math.round(calibrationProgress)}%)` : 'ACTIVE GUARD'}
            </span>
          </div>
        </div>
      </header>
      
      {/* FOUR REAL-TIME METRIC CARDS WITH FORMULA TOOLTIPS */}
      <section className="metrics-grid">
        
        {/* Metric 1: Firing Sparsity */}
        <div className="metric-card sparsity">
          <div className="metric-header">
            <span className="metric-title">Inference Sparsity</span>
            <span className="math-badge">S(x)</span>
          </div>
          <p className="metric-value">
            {sparsity.toFixed(1)} <span className="unit">%</span>
          </p>
          <span className="metric-subtitle">
            {sparsity > 90 ? 'HEALTHY (SPARSE SPATIAL LOAD)' : 'HIGH FREQUENCY FIRING'}
          </span>
          
          <div className="math-tooltip">
            <strong>Neuromorphic Sparsity Equation</strong>
            <span className="math-formula">{SPARSITY_FORMULA}</span>
            Calculates the fraction of inactive biological clock cycles. EDR shuts down paths when dense spike trains ($S \ll 90\%$) collapse system entropy.
          </div>
        </div>
        
        {/* Metric 2: Shannon Entropy */}
        <div className="metric-card entropy">
          <div className="metric-header">
            <span className="metric-title">Shannon Entropy</span>
            <span className="math-badge">H(X)</span>
          </div>
          <p className="metric-value">
            {entropy.toFixed(3)}
          </p>
          <div className="metric-sparkline-container">
            <canvas ref={entropyCanvasRef} />
          </div>
          <span className="metric-subtitle">Spike Information Density</span>
          
          <div className="math-tooltip">
            <strong>Shannon Entropy Formula</strong>
            <span className="math-formula">{ENTROPY_FORMULA}</span>
            Measures uncertainty/dispersion of events. Anomalous encryption patterns compress intervals, causing $H(X)$ to deviate violently from calibrated baseline bounds.
          </div>
        </div>
        
        {/* Metric 3: Membrane Potential Deviation */}
        <div className={`metric-card zscore ${zScore > 4.0 ? 'breached' : ''}`}>
          <div className="metric-header">
            <span className="metric-title">LIF Potential Dev.</span>
            <span className="math-badge">Z(v)</span>
          </div>
          <p className="metric-value">
            {zScore.toFixed(2)}
          </p>
          <div className="metric-sparkline-container">
            <canvas ref={zScoreCanvasRef} />
          </div>
          <span className="metric-subtitle">
            {zScore > 4.0 ? 'STATISTICAL BOUNDS BREACHED' : 'STABLE LIF BASIN'}
          </span>
          
          <div className="math-tooltip">
            <strong>Z-Score Potential Deviation</strong>
            <span className="math-formula">{ZSCORE_FORMULA}</span>
            Measures current LIF membrane potentials ($v_i$) against mean ($\mu_i$) and standard deviation ($\sigma_i$) calibrated values. Alert triggers when $Z &gt; 4.0$.
          </div>
        </div>
        
        {/* Metric 4: Clock Speed / Latency */}
        <div className="metric-card latency">
          <div className="metric-header">
            <span className="metric-title">Inference Delay</span>
            <span className="math-badge">T_p</span>
          </div>
          <p className="metric-value">
            {latency.toFixed(1)} <span className="unit">µs</span>
          </p>
          <span className="metric-subtitle">SNN Clock Processing Time</span>
          
          <div className="math-tooltip">
            <strong>Biological Integration Latency</strong>
            <span className="math-formula">{LATENCY_FORMULA}</span>
            Represents the physical time taken for backpropagation weight updates and forward leaky potential integrations. Typically &le; 100 microseconds on standard hardware.
          </div>
        </div>
      </section>
      
      {/* MAIN TWO-COLUMN VIEW */}
      <div className="dashboard-main-content">
        
        {/* Column 1: SNN Architecture Map */}
        <section className={`panel-container network-panel ${lockdown ? 'lockdown' : ''}`}>
          <div className="panel-header">
            <div className={`panel-title ${lockdown ? 'lockdown' : ''}`}>
              🧠 SNN ACTIVE DEEP TOPOLOGY & INF ARCS
            </div>
            <div className="panel-subtitle">Real-time Surrogate Gradient SGD Synaptic Shift Map</div>
          </div>
          <div className="canvas-area">
            <canvas ref={snnCanvasRef} className="snn-canvas" />
          </div>
          <div className="canvas-legend">
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: COLORS.green }} />
              <span>File Spikes</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: COLORS.cyan }} />
              <span>Thread Spikes</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: COLORS.purple }} />
              <span>Inhibitory Connection (w &lt; 0)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: COLORS.green }} />
              <span>Excitatory Connection (w &ge; 0)</span>
            </div>
          </div>
        </section>
        
        {/* Column 2: Endpoint File Security Grid */}
        <section className={`panel-container shield-panel ${lockdown ? 'lockdown' : ''}`}>
          <div className="panel-header">
            <div className={`panel-title shield-title ${lockdown ? 'lockdown' : ''}`}>
              🖧 ENDPOINT FILE GRID: SANDBOX SANDBOX
            </div>
            {lockdown && <button className="btn btn-warning btn-show-report" onClick={() => { SoundSynth.playClick(); setShowReport(true); }}>VIEW REPORT</button>}
          </div>
          
          <div className="files-grid-container">
            {totalFiles === 0 ? (
              <div className="files-empty">
                <div className="files-empty-icon">📂</div>
                <p>No sandbox files loaded. EDR will auto-create files on <strong>INJECT ATTACK</strong>.</p>
              </div>
            ) : (
              <div className="files-grid">
                {files.map((file, idx) => (
                  <div key={idx} className={`file-node ${file.locked ? 'locked' : ''}`}>
                    <div className="file-icon">{file.locked ? '🔒' : '📄'}</div>
                    <div className="file-name" title={file.name}>{file.name}</div>
                    <div className="file-status">{file.locked ? 'Encrypted' : 'Secured'}</div>
                  </div>
                ))}
              </div>
            )}
            
            {/* Circular Protection Shield */}
            {lockdown && (
              <div className="shield-lockdown-overlay">
                <div className="shield-graphic-container">
                  <div className="shield-ring" />
                  <div className="shield-ring-inner" />
                  <div className="shield-icon-locked">🛡️</div>
                </div>
                <h3>EDR SHIELD ENGAGED</h3>
                <p style={{ fontSize: '11px', color: '#e5e7eb', marginTop: '6px' }}>
                  Zero-Day ransomware behavior matching sequence thresholds was deflected. Cryptographic execution channels have been blocked.
                </p>
                <button className="btn btn-success" onClick={() => { SoundSynth.playClick(); setShowReport(true); }} style={{ marginTop: '10px' }}>
                  📋 VIEW DIAGNOSTICS REPORT
                </button>
              </div>
            )}
          </div>
        </section>
      </div>
      
      {/* LOWER CONSOLE PANEL */}
      <div className="lower-console-grid">
        
        {/* Terminal Logs */}
        <div className="console-card">
          <div className="terminal-header">
            <div className={`terminal-title ${lockdown ? 'lockdown' : ''}`}>
              &gt;_ AEGIS-SPIKE COGNITIVE INGRESS
            </div>
            <div className="panel-subtitle">live agent telemetry</div>
          </div>
          <div className={`terminal-body ${lockdown ? 'lockdown' : ''}`}>
            {logs.length === 0 ? (
              <div className="terminal-log-line">
                <span className="timestamp">[{new Date().toLocaleTimeString()}]</span>
                <span>Active EDR Agent pipeline connected. Awaiting host metrics...</span>
              </div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className={`terminal-log-line ${log.isError ? 'error' : ''}`}>
                  <span className="timestamp">[{log.timestamp}]</span>
                  <span>{log.text}</span>
                </div>
              ))
            )}
          </div>
        </div>
        
        {/* Real-time Synaptic Heatmap panel */}
        <div className="console-card">
          <div className="terminal-header">
            <span className="terminal-title" style={{ color: COLORS.cyan }}>
              🔬 REAL-TIME SYNAPSE HEATMAP (FC1)
            </span>
            <div className="panel-subtitle">weight metrics matrix</div>
          </div>
          
          <div className="diagnostics-panel">
            <div className="heatmap-container">
              <div className="heatmap-grid-title">16 Hidden LIF Nodes &times; 2 Stimuli Channels</div>
              <div className="heatmap-canvas-container">
                <canvas ref={heatmapCanvasRef} className="heatmap-canvas" />
              </div>
              <div className="diag-details" style={{ marginTop: '6px' }}>
                <span>Columns: File system (Left) | Process (Right)</span>
                <span>Pink: Inhibitory | Blue: Excitatory</span>
              </div>
            </div>
            
            <div className={`diagnostic-row ${zScore > 4.0 ? 'breached' : ''}`}>
              <div className="diag-title">
                <span>SNN Entropy Bounds Check</span>
                <span className={`status ${zScore > 4.0 ? 'breached' : 'normal'}`}>
                  {zScore > 4.0 ? 'LIMIT BREACHED' : 'SAFE STATS BASIN'}
                </span>
              </div>
              <div className="diag-bar-bg">
                <div 
                  className={`diag-bar-fill ${zScore > 4.0 ? 'breached' : zScore > 2.5 ? 'warning' : 'normal'}`} 
                  style={{ width: `${Math.min(100, (zScore / 8.0) * 100)}%` }} 
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* INCIDENT REPORT MODAL */}
      {showReport && (
        <div className="report-modal-overlay">
          <div className="report-modal">
            <div className="report-modal-header">
              <h2>☣ COGNITIVE THREAT INCIDENT REPORT</h2>
              <button className="btn-close-modal" onClick={() => { SoundSynth.playClick(); setShowReport(false); }}>&times;</button>
            </div>
            
            <div className="report-modal-body">
              <div className="report-alert-banner">
                <span className="banner-icon">⚠️</span>
                <div>
                  <strong>EDR LOCKDOWN ACTIVE - THREAT CONTAINED</strong>
                  <p>Model classification logic terminated active pathways to prevent system-wide encryption.</p>
                </div>
              </div>
              
              <div className="report-grid">
                <div className="report-section">
                  <h3>EXECUTIVE SUMMARY</h3>
                  <p>
                    AEGIS-SPIKE's online Spiking Neural Network (SNN) detected a critical temporal sequence collapse. 
                    Targeted events matching <strong>{attackProfile.toUpperCase()}</strong> signatures violated statistical boundaries of the calibrated baseline.
                  </p>
                </div>
                
                <div className="report-section">
                  <h3>THREAT METADATA</h3>
                  <div className="report-meta-grid">
                    <div><span className="lbl">Culprit Process:</span> <span className="val breached">{attackingProcess || 'unknown'}</span></div>
                    <div><span className="lbl">Response Latency:</span> <span className="val secured">{latency.toFixed(1)} µs</span></div>
                    <div><span className="lbl">Target Directory:</span> <span className="val font-mono" style={{ fontSize: '9px' }}>m:\Spike\monitored_directory</span></div>
                    <div><span className="lbl">System Status:</span> <span className="val breached font-mono">LOCKDOWN ACTIVE</span></div>
                  </div>
                </div>
              </div>
              
              <div className="report-section" style={{ marginTop: '14px' }}>
                <h3>NEUROMORPHIC DETECTOR ANALYSIS</h3>
                <div className="report-metrics-grid">
                  <div className="report-metric-box">
                    <span className="box-title">Inference Sparsity</span>
                    <span className="box-val">{sparsity.toFixed(1)}%</span>
                  </div>
                  <div className="report-metric-box">
                    <span className="box-title">Shannon Entropy</span>
                    <span className="box-val">{entropy.toFixed(4)}</span>
                  </div>
                  <div className="report-metric-box">
                    <span className="box-title">Membrane Z-Score</span>
                    <span className="box-val breached">{zScore.toFixed(2)}</span>
                  </div>
                </div>
              </div>
              
              <div className="report-section" style={{ marginTop: '14px' }}>
                <h3>ENDPOINT FILES PROTECTION INDEX</h3>
                <div className="report-files-summary">
                  <div className="files-summary-bar-bg">
                    <div className="files-summary-bar-fill" style={{ width: `${protectionPercentage}%` }} />
                  </div>
                  <div className="files-summary-details">
                    <span>Compromised: <strong className="breached">{lockedFiles}</strong></span>
                    <span>Protected: <strong className="secured">{protectedFiles} ({protectionPercentage}%)</strong></span>
                    <span>Total Target Files: <strong>{totalFiles}</strong></span>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="report-modal-footer">
              <button className="btn btn-warning" onClick={() => { SoundSynth.playClick(); setShowReport(false); }}>
                CLOSE PREVIEW
              </button>
              <button className="btn btn-success" onClick={downloadReport}>
                📥 DOWNLOAD MARKDOWN REPORT
              </button>
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
}

export default App;
