import torch
import torch.nn as nn
import snntorch as snn
from snntorch import surrogate
import numpy as np
import math
from collections import deque

class AegisSNN(nn.Module):
    def __init__(self, input_dim=5, hidden_dim=16, output_dim=5, beta=0.85):
        super().__init__()
        self.spike_grad = surrogate.fast_sigmoid(slope=25)
        
        # Heterogeneous Membrane Time Constants optimized to prevent saturation (0.60 to 0.90)
        self.register_buffer('beta1', torch.linspace(0.60, 0.90, hidden_dim))
        self.beta2 = 0.85
        
        # SNN Network Layers
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.lif1 = snn.Leaky(beta=self.beta1, spike_grad=self.spike_grad)
        
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.lif2 = snn.Leaky(beta=self.beta2, spike_grad=self.spike_grad)
        
        # State variables for LIF membrane potentials (kept for compatibility, though we track externally)
        self.mem1 = None
        self.mem2 = None
        
        self.init_states()

    def init_states(self):
        """Reset membrane potentials to zero."""
        self.mem1 = None
        self.mem2 = None

    def forward(self, x, mem1=None, mem2=None):
        """
        Forward pass for a single time step.
        x: Tensor of shape (1, input_dim) representing input spikes.
        mem1, mem2: Optional membrane potentials from the previous step.
        Returns:
            spk2: Output spikes (1, output_dim)
            next_mem2: Output membrane potentials (1, output_dim)
            spk1: Hidden spikes (1, hidden_dim)
            next_mem1: Hidden membrane potentials (1, hidden_dim)
        """
        if mem1 is None:
            if self.mem1 is None or self.mem1.shape[0] != x.shape[0]:
                self.mem1 = self.lif1.init_leaky()
            mem1 = self.mem1
        if mem2 is None:
            if self.mem2 is None or self.mem2.shape[0] != x.shape[0]:
                self.mem2 = self.lif2.init_leaky()
            mem2 = self.mem2
            
        # Detach membrane potentials to prevent infinite backpropagation through time (BPTT) online
        mem1 = mem1.detach()
        mem2 = mem2.detach()

        cur1 = self.fc1(x)
        spk1, next_mem1 = self.lif1(cur1, mem1)
        
        cur2 = self.fc2(spk1)
        spk2, next_mem2 = self.lif2(cur2, mem2)
        
        # If using internal state, update it
        if mem1 is self.mem1:
            self.mem1 = next_mem1.detach()
        if mem2 is self.mem2:
            self.mem2 = next_mem2.detach()
            
        return spk2, next_mem2, spk1, next_mem1


class NeuromorphicEngine:
    def __init__(self, input_dim=5, hidden_dim=16, output_dim=5, learning_rate=0.01, window_size=100, calibration_size=200):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AegisSNN(input_dim, hidden_dim, output_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        
        self.window_size = window_size
        self.calibration_size = calibration_size
        
        # Explicit states for SNN to prevent online state corruption
        self.mem1 = None
        self.mem2 = None
        self.prev_state_mem1 = None
        self.prev_state_mem2 = None
        
        # Rolling spike histories for Entropy calculations
        self.input_spike_history = deque(maxlen=window_size)
        self.output_spike_history = deque(maxlen=window_size)
        
        # Membrane potentials history for Z-Score calibration and calculations
        # Stores concatenated (mem1, mem2) arrays
        self.membrane_history = []
        self.calibrated = False
        
        # Statistical baseline metrics
        self.mean_mem = None
        self.std_mem = None
        self.cov_mem = None
        self.inv_cov_mem = None
        
        # Cache for next step prediction online training
        self.prev_input = None
        self.prev_prediction = None  # Sigmoid of output membrane potential from last step
        
        # Rolling prediction errors to smooth out anomalies
        self.rolling_errors = deque(maxlen=20)
        
        # Calibration phase lists for dynamic thresholds calculation
        self.calibration_pred_errors = []
        self.calibration_entropies = []
        
        # Baselines for alert triggers
        self.baseline_pred_error = 0.15
        self.error_threshold_multiplier = 3.0  # Alert if error > threshold * baseline
        self.z_score_threshold = 8.0           # Alert if Mahalanobis distance > 8.0
        self.entropy_deviation_threshold = 0.4 # Alert if entropy differs significantly from calibration
        self.error_limit = 0.45                # Dynamic error limit threshold
        
        self.calibrated_entropy_mean = 0.0
        self.calibrated_entropy_std = 1.0

    def calculate_shannon_entropy(self, spike_history):
        """
        Calculate rolling Shannon Entropy of the spike trains.
        spike_history: deque of numpy arrays, shape (W, D)
        Returns:
            Average Shannon Entropy across all channels
        """
        if len(spike_history) < 10:
            return 0.0
        
        history_arr = np.array(spike_history) # shape (W, D)
        W, D = history_arr.shape
        
        # Calculate joint probability of each unique binary state vector
        from collections import Counter
        state_counts = Counter(tuple(row) for row in history_arr)
        
        entropy = 0.0
        for count in state_counts.values():
            p = count / W
            if p > 0.0:
                entropy -= p * math.log2(p)
                
        return float(entropy)

    def update_calibration(self):
        """Calibrate the baseline membrane potentials and entropy."""
        if len(self.membrane_history) < self.calibration_size:
            return False
            
        mems_arr = np.array(self.membrane_history) # shape (calibration_size, total_neurons)
        self.mean_mem = np.mean(mems_arr, axis=0)
        self.std_mem = np.std(mems_arr, axis=0)
        # Prevent division by zero
        self.std_mem[self.std_mem < 1e-4] = 1e-4
        
        # Calculate covariance matrix for Mahalanobis Distance
        self.cov_mem = np.cov(mems_arr, rowvar=False)
        # Regularization to prevent matrix singularity and stabilize low-variance dimensions
        self.cov_mem += np.eye(self.cov_mem.shape[0]) * 0.1
        self.inv_cov_mem = np.linalg.inv(self.cov_mem)
        
        # Back-calculate Z-scores (Mahalanobis distances) for the calibration data to determine dynamic bounds
        calib_z_scores = []
        for mem_c in self.membrane_history:
            diff = mem_c - self.mean_mem
            mahalanobis_dist = np.sqrt(np.dot(np.dot(diff, self.inv_cov_mem), diff.T))
            calib_z_scores.append(mahalanobis_dist)
        mean_z = np.mean(calib_z_scores) if calib_z_scores else 0.0
        std_z = np.std(calib_z_scores) if calib_z_scores else 1.0
        
        # Dynamic Z-score threshold
        self.z_score_threshold = max(11.0, float(mean_z + 4.5 * std_z))
        
        # Calibrate prediction error dynamically
        if self.calibration_pred_errors:
            self.baseline_pred_error = float(np.mean(self.calibration_pred_errors))
            pred_error_std = float(np.std(self.calibration_pred_errors))
            self.error_limit = max(0.40, self.baseline_pred_error + 4.0 * pred_error_std)
        else:
            self.baseline_pred_error = 0.15
            self.error_limit = 0.45
            
        # Also calibrate entropy baseline and deviation dynamically
        if self.calibration_entropies:
            self.calibrated_entropy_mean = float(np.mean(self.calibration_entropies))
            entropy_std = float(np.std(self.calibration_entropies))
            self.entropy_deviation_threshold = max(0.35, float(4.5 * entropy_std))
        else:
            # We look at rolling input entropy as a backup
            history_len = len(self.input_spike_history)
            if history_len >= 10:
                self.calibrated_entropy_mean = self.calculate_shannon_entropy(self.input_spike_history)
            self.entropy_deviation_threshold = 0.4
            
        self.calibrated = True
        return True

    def process_step(self, input_vector):
        """
        Process a single step of OS events.
        input_vector: list or numpy array of shape (input_dim,) containing binary events [file_io, process_thread]
        Returns:
            A dictionary containing:
                prediction_error: float
                shannon_entropy: float
                z_score_deviation: float
                alert_triggered: bool
                sparsity: float
                latency_us: float (to be measured externally)
        """
        # Convert input to float tensor
        x_tensor = torch.tensor([input_vector], dtype=torch.float32, device=self.device)
        
        # 1. Measure Sparsity
        self.input_spike_history.append(input_vector)
        sparsity = (1.0 - np.mean(self.input_spike_history)) * 100.0 if len(self.input_spike_history) > 0 else 100.0
        
        # Initialize membrane potentials if they don't exist
        if self.mem1 is None:
            self.mem1 = torch.zeros((1, 16), device=self.device) # hidden_dim=16
        if self.mem2 is None:
            self.mem2 = torch.zeros((1, 2), device=self.device)  # output_dim=2
            
        # 2. Online training: Next-step prediction
        # If we have a previous input, we train the network to predict current input from it
        if self.prev_input is not None:
            self.model.train()
            self.optimizer.zero_grad()
            
            # SNN forward pass starting from the previous state (needs to run with grad)
            # Restore state to the one BEFORE prev_input was processed
            m1_train = self.prev_state_mem1.detach().clone()
            m2_train = self.prev_state_mem2.detach().clone()
            
            prev_tensor = torch.tensor([self.prev_input], dtype=torch.float32, device=self.device)
            spk2_train, mem2_train, _, mem1_train = self.model(prev_tensor, m1_train, m2_train)
            
            # Target is the current input
            target_tensor = torch.tensor([input_vector], dtype=torch.float32, device=self.device)
            
            # Loss is MSE between predicted output spikes or membrane potentials and target
            # Using sigmoid of membrane potential yields a smooth differentiable output
            pred_train = torch.sigmoid(mem2_train)
            loss = self.criterion(pred_train, target_tensor)
            
            loss.backward()
            self.optimizer.step()
            
            # Update current state (self.mem1, self.mem2) to the state AFTER prev_input was processed,
            # using the updated states from the forward pass
            self.mem1 = mem1_train.detach()
            self.mem2 = mem2_train.detach()
            
        # Save the current state BEFORE we process the current input x_tensor
        self.prev_state_mem1 = self.mem1.clone()
        self.prev_state_mem2 = self.mem2.clone()
        
        # 3. Run Forward Pass to generate prediction for the NEXT step (using updated weights)
        self.model.eval()
        with torch.no_grad():
            spk2, next_mem2, spk1, next_mem1 = self.model(x_tensor, self.mem1, self.mem2)
            
        # Update current state to the state AFTER current input is processed
        self.mem1 = next_mem1.detach()
        self.mem2 = next_mem2.detach()
        
        # Store membrane potentials of this step for calibration/Z-score
        mem_combined = np.concatenate([next_mem1.cpu().numpy()[0], next_mem2.cpu().numpy()[0]])
        
        # Store output spikes
        output_vector = spk2.cpu().numpy()[0]
        self.output_spike_history.append(output_vector)
        
        # Calculate Rolling Entropy
        entropy = self.calculate_shannon_entropy(self.input_spike_history)
        
        # Calculate Z-Score Deviation using Mahalanobis Distance
        z_score_dev = 0.0
        if self.calibrated:
            diff = mem_combined - self.mean_mem
            mahalanobis_dist = np.sqrt(np.dot(np.dot(diff, self.inv_cov_mem), diff.T))
            z_score_dev = float(mahalanobis_dist)
            
        # 4. Calculate Prediction Error for this step using the PREVIOUS step's prediction
        pred_error = 0.0
        if self.prev_prediction is not None:
            # We predict current input x_tensor using previous step's output prediction
            pred_error = float(np.mean(np.abs(input_vector - self.prev_prediction)))
            self.rolling_errors.append(pred_error)
            
        avg_pred_error = np.mean(self.rolling_errors) if len(self.rolling_errors) > 0 else pred_error
        
        # Update previous prediction for next step
        # We use a sigmoid over output membrane potential as prediction score [0, 1] for next step
        self.prev_prediction = torch.sigmoid(next_mem2).cpu().numpy()[0]
        
        self.prev_input = input_vector
        
        # Collect calibration data if not calibrated
        if not self.calibrated:
            self.membrane_history.append(mem_combined)
            if len(self.input_spike_history) >= 10:
                self.calibration_entropies.append(entropy)
            if self.prev_input is not None and self.prev_prediction is not None:
                self.calibration_pred_errors.append(pred_error)
            
            if len(self.membrane_history) >= self.calibration_size:
                self.update_calibration()
        
        # 5. Alert Decision Logic (CRITICAL GUARDRAILS WITH DYNAMIC BOUNDS & REFINED CLASSIFICATION)
        # "The system only triggers an alert if the temporal sequence collapses (Prediction Error spikes) AND the statistical bounds are breached."
        alert_triggered = False
        if self.calibrated:
            # Check if prediction error spikes (using dynamic baseline & limit)
            error_spiked = avg_pred_error > (self.baseline_pred_error * self.error_threshold_multiplier) or avg_pred_error > self.error_limit
            
            # Check if statistical bounds are breached dynamically
            z_score_breached = z_score_dev > self.z_score_threshold
            
            # Entropy collapses or expands violently
            entropy_breached = False
            # Only evaluate entropy breach if the history has warmed up (len >= 20)
            if len(self.input_spike_history) >= 20:
                entropy_breached = abs(entropy - self.calibrated_entropy_mean) > self.entropy_deviation_threshold
            
            # Alert condition logic with dual warm-up gates:
            # 1. Direct Z-Score deviation alarms with active telemetry can trigger after 5 steps
            if len(self.input_spike_history) >= 5:
                if z_score_breached and sum(input_vector) > 0:
                    alert_triggered = True
                    
            # 2. Prediction error sequence collapse alerts trigger after 20 steps (to clear startup transients)
            if len(self.input_spike_history) >= 20:
                if error_spiked and (z_score_breached or entropy_breached):
                    alert_triggered = True
                
        return {
            "prediction_error": avg_pred_error,
            "shannon_entropy": entropy,
            "z_score_deviation": z_score_dev,
            "z_score_threshold": self.z_score_threshold,
            "alert_triggered": alert_triggered,
            "sparsity": sparsity,
            "calibrated": self.calibrated,
            "calibration_progress": min(100.0, (len(self.membrane_history) / self.calibration_size) * 100.0),
            "spk1": spk1.cpu().numpy()[0].tolist(),
            "spk2": spk2.cpu().numpy()[0].tolist(),
            "mem1": next_mem1.cpu().numpy()[0].tolist(),
            "mem2": next_mem2.cpu().numpy()[0].tolist(),
            "weights_fc1": self.model.fc1.weight.cpu().detach().numpy().tolist(),
            "weights_fc2": self.model.fc2.weight.cpu().detach().numpy().tolist()
        }

    def reset(self):
        """Reset the engine states, histories, and model states."""
        self.model.init_states()
        self.mem1 = None
        self.mem2 = None
        self.prev_state_mem1 = None
        self.prev_state_mem2 = None
        self.input_spike_history.clear()
        self.output_spike_history.clear()
        self.rolling_errors.clear()
        self.prev_input = None
        self.prev_prediction = None
        if not self.calibrated:
            self.calibration_pred_errors.clear()
            self.calibration_entropies.clear()
        # Keep calibration data unless explicit recalibration is requested
