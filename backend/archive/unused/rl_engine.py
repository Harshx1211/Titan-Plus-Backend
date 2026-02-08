"""
Titan Plus: Reinforcement Learning Evolution Engine
====================================================
Deep Q-Network (DQN) for spontaneous strategy discovery.
Learns from its own mistakes to discover trading patterns not explicitly programmed.

Version: 9.9.9 (Phase 3)
Author: Titan Plus Development Team
"""

import logging
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque, namedtuple
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rl_engine")

# Experience Tuple for Replay Buffer
Experience = namedtuple('Experience', ['state', 'action', 'reward', 'next_state', 'done'])

class DQNetwork(nn.Module):
    """
    Deep Q-Network Architecture
    Input: Market state vector (25 dimensions)
    Output: Q-values for each action (BUY_CALL, BUY_PUT, HOLD)
    """
    def __init__(self, state_dim: int = 25, action_dim: int = 3):
        super(DQNetwork, self).__init__()
        
        # Neural architecture optimized for financial time series
        self.network = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),  # Regularization to prevent overfitting
            
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            
            nn.Linear(128, 64),
            nn.ReLU(),
            
            nn.Linear(64, action_dim)
        )
        
        # Initialize weights using He initialization
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Xavier/He initialization for better gradient flow"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, state):
        """Forward pass through the network"""
        return self.network(state)


class ReplayBuffer:
    """
    Experience Replay Buffer with Prioritization
    Stores experiences and samples them for training to break correlation
    """
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
    
    def push(self, experience: Experience, priority: float = 1.0):
        """Add experience to buffer"""
        self.buffer.append(experience)
        self.priorities.append(priority)
    
    def sample(self, batch_size: int) -> List[Experience]:
        """Sample batch with priority weighting"""
        if len(self.buffer) < batch_size:
            return list(self.buffer)
        
        # Convert priorities to probabilities
        priorities = np.array(self.priorities)
        probabilities = priorities / priorities.sum()
        
        # Sample indices based on priorities
        indices = np.random.choice(len(self.buffer), batch_size, p=probabilities, replace=False)
        
        return [self.buffer[i] for i in indices]
    
    def __len__(self):
        return len(self.buffer)


class RLEvolutionEngine:
    """
    The Learning Core - Spontaneous Strategy Discovery
    
    Uses Deep Q-Learning to:
    1. Learn from winning/losing trades
    2. Discover patterns in regime + decision combinations
    3. Self-correct institutional biases
    """
    
    def __init__(self, state_dim: int = 25, action_dim: int = 3, learning_rate: float = 0.0001):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"RL_ENGINE: Initialized on {self.device}")
        
        # Hyperparameters
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = 0.95  # Discount factor for future rewards
        self.epsilon = 1.0  # Exploration rate (starts high)
        self.epsilon_min = 0.05  # Minimum exploration
        self.epsilon_decay = 0.995  # Decay rate per episode
        self.learning_rate = learning_rate
        self.batch_size = 64
        self.target_update_freq = 10  # Update target network every N episodes
        
        # Networks
        self.policy_net = DQNetwork(state_dim, action_dim).to(self.device)
        self.target_net = DQNetwork(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()  # Target network is not trained directly
        
        # Optimizer and loss
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        self.criterion = nn.SmoothL1Loss()  # Huber loss for stability
        
        # Experience replay
        self.memory = ReplayBuffer(capacity=10000)
        
        # Efficacy tracking: Map (decision, regime) → outcome history
        self.efficacy_map: Dict[str, List[float]] = {}
        
        # Training metrics
        self.episode_count = 0
        self.total_rewards = []
        self.loss_history = []
        
        # Action mapping
        self.action_map = {
            0: "BUY_CALL",
            1: "BUY_PUT", 
            2: "HOLD"
        }
    
    def state_to_tensor(self, state_dict: Dict) -> torch.Tensor:
        """
        Convert market state dictionary to tensor
        
        State components:
        - Technical indicators (7): RSI, ADX, ATR, Basis, PCR, VIX, IV_Skew
        - Price action (5): Close, High, Low, Volume, Future_Premium
        - Greeks (4): Call_Gamma, Put_Gamma, Net_GEX, Gamma_Ratio
        - SMC signals (4): Order_Block, FVG, Liquidity_Sweep, Imbalance
        - Regime (5): One-hot encoded market regime
        """
        vector = []
        
        # Technical indicators (normalized)
        indicators = state_dict.get('indicators', {})
        vector.extend([
            indicators.get('rsi', 50.0) / 100.0,
            indicators.get('adx', 20.0) / 100.0,
            indicators.get('atr', 100.0) / 500.0,
            indicators.get('basis', 0.0) / 10.0,
            indicators.get('pcr', 1.0),
            indicators.get('vix', 15.0) / 50.0,
            indicators.get('iv_skew', 1.0)
        ])
        
        # Price action
        price = state_dict.get('price', {})
        base_price = price.get('close', 25000.0)
        vector.extend([
            price.get('close', 25000.0) / 30000.0,
            price.get('high', 25100.0) / 30000.0,
            price.get('low', 24900.0) / 30000.0,
            price.get('volume', 1000000) / 10000000.0,
            price.get('future_premium', 5.0) / 100.0
        ])
        
        # Greeks
        greeks = state_dict.get('greeks', {})
        vector.extend([
            greeks.get('call_gamma', 0.002) * 1000,
            greeks.get('put_gamma', 0.002) * 1000,
            greeks.get('net_gex', 0.0) / 1000000.0,
            greeks.get('gamma_ratio', 1.0)
        ])
        
        # SMC Signals (binary/continuous)
        smc = state_dict.get('smc', {})
        vector.extend([
            1.0 if smc.get('order_block', False) else 0.0,
            1.0 if smc.get('fvg', False) else 0.0,
            1.0 if smc.get('liquidity_sweep', False) else 0.0,
            smc.get('imbalance_score', 0.0)
        ])
        
        # Regime (one-hot encoding of 5 regimes)
        regime = state_dict.get('regime', 'NEUTRAL')
        regime_map = {
            'TRENDING_UP': [1, 0, 0, 0, 0],
            'TRENDING_DOWN': [0, 1, 0, 0, 0],
            'SIDEWAYS_STRONG': [0, 0, 1, 0, 0],
            'SIDEWAYS_WEAK': [0, 0, 0, 1, 0],
            'NEUTRAL': [0, 0, 0, 0, 1]
        }
        vector.extend(regime_map.get(regime, [0, 0, 0, 0, 1]))
        
        # Convert to tensor
        return torch.FloatTensor(vector).unsqueeze(0).to(self.device)
    
    def select_action(self, state_dict: Dict, training: bool = True) -> int:
        """
        Epsilon-greedy action selection
        
        Args:
            state_dict: Current market state
            training: If True, uses epsilon-greedy; if False, uses pure exploitation
        
        Returns:
            Action index (0=BUY_CALL, 1=BUY_PUT, 2=HOLD)
        """
        if training and random.random() < self.epsilon:
            # Exploration: Random action
            action = random.randrange(self.action_dim)
            logger.debug(f"RL_EXPLORE: Random action = {self.action_map[action]}")
            return action
        
        # Exploitation: Use policy network
        state = self.state_to_tensor(state_dict)
        with torch.no_grad():
            q_values = self.policy_net(state)
            action = q_values.max(1)[1].item()
        
        logger.debug(f"RL_EXPLOIT: Q-values = {q_values.cpu().numpy()}, Action = {self.action_map[action]}")
        return action
    
    def store_experience(self, state_dict: Dict, action: int, reward: float, 
                        next_state_dict: Dict, done: bool):
        """Store experience in replay buffer"""
        state = self.state_to_tensor(state_dict)
        next_state = self.state_to_tensor(next_state_dict)
        
        experience = Experience(
            state.cpu(),
            action,
            reward,
            next_state.cpu(),
            done
        )
        
        # Priority based on absolute reward (learn more from big wins/losses)
        priority = abs(reward) + 0.1
        self.memory.push(experience, priority)
    
    def train_step(self) -> Optional[float]:
        """
        Perform one training step using experience replay
        
        Returns:
            Loss value if training occurred, None otherwise
        """
        if len(self.memory) < self.batch_size:
            return None
        
        # Sample batch
        experiences = self.memory.sample(self.batch_size)
        
        # Unpack batch
        states = torch.cat([e.state for e in experiences]).to(self.device)
        actions = torch.LongTensor([e.action for e in experiences]).to(self.device)
        rewards = torch.FloatTensor([e.reward for e in experiences]).to(self.device)
        next_states = torch.cat([e.next_state for e in experiences]).to(self.device)
        dones = torch.FloatTensor([e.done for e in experiences]).to(self.device)
        
        # Current Q-values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # Target Q-values (using target network for stability)
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            target_q = rewards + (1 - dones) * self.gamma * next_q
        
        # Compute loss
        loss = self.criterion(current_q, target_q)
        
        # Backpropagation
        self.optimizer.zero_grad()
        loss.backward()
        
        # Gradient clipping to prevent exploding gradients
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
        
        self.optimizer.step()
        
        # Record loss
        loss_value = loss.item()
        self.loss_history.append(loss_value)
        
        return loss_value
    
    def update_target_network(self):
        """Sync target network with policy network"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
        logger.info("RL_ENGINE: Target network updated")
    
    def decay_epsilon(self):
        """Reduce exploration rate over time"""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
    
    def track_efficacy(self, decision: str, regime: str, outcome: float):
        """
        Track efficacy of decision in given regime
        
        Args:
            decision: BUY_CALL, BUY_PUT, HOLD
            regime: Market regime
            outcome: 1.0 for win, 0.0 for loss, 0.5 for neutral
        """
        key = f"{decision}_{regime}"
        if key not in self.efficacy_map:
            self.efficacy_map[key] = []
        
        self.efficacy_map[key].append(outcome)
        
        # Keep only last 100 outcomes for each combination
        if len(self.efficacy_map[key]) > 100:
            self.efficacy_map[key] = self.efficacy_map[key][-100:]
    
    def get_efficacy_report(self) -> Dict:
        """Generate efficacy report for all tracked combinations"""
        report = {}
        for key, outcomes in self.efficacy_map.items():
            if len(outcomes) > 0:
                report[key] = {
                    'win_rate': sum(outcomes) / len(outcomes) * 100,
                    'total_trades': len(outcomes),
                    'confidence': min(100, len(outcomes) * 2)  # More trades = higher confidence
                }
        return report
    
    def save_state(self, path: str = "rl_state.pt"):
        """Save RL engine state to disk"""
        state = {
            'policy_net_state_dict': self.policy_net.state_dict(),
            'target_net_state_dict': self.target_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'episode_count': self.episode_count,
            'efficacy_map': self.efficacy_map,
            'total_rewards': self.total_rewards,
            'loss_history': self.loss_history[-1000:]  # Keep last 1000 losses
        }
        
        torch.save(state, path)
        logger.info(f"RL_ENGINE: State saved to {path}")
    
    def load_state(self, path: str = "rl_state.pt"):
        """Load RL engine state from disk"""
        try:
            state = torch.load(path, map_location=self.device)
            
            self.policy_net.load_state_dict(state['policy_net_state_dict'])
            self.target_net.load_state_dict(state['target_net_state_dict'])
            self.optimizer.load_state_dict(state['optimizer_state_dict'])
            self.epsilon = state.get('epsilon', 1.0)
            self.episode_count = state.get('episode_count', 0)
            self.efficacy_map = state.get('efficacy_map', {})
            self.total_rewards = state.get('total_rewards', [])
            self.loss_history = state.get('loss_history', [])
            
            logger.info(f"RL_ENGINE: State loaded from {path} (Episode {self.episode_count})")
            return True
        except FileNotFoundError:
            logger.warning(f"RL_ENGINE: No saved state found at {path}. Starting fresh.")
            return False
        except Exception as e:
            logger.error(f"RL_ENGINE: Error loading state: {e}")
            return False
    
    def get_recommendation(self, state_dict: Dict) -> Dict:
        """
        Get RL recommendation for current state (inference mode)
        
        Returns:
            {
                'action': 'BUY_CALL' | 'BUY_PUT' | 'HOLD',
                'confidence': 0.0-1.0,
                'q_values': {...},
                'source': 'RL_ENGINE'
            }
        """
        state = self.state_to_tensor(state_dict)
        
        with torch.no_grad():
            q_values = self.policy_net(state).cpu().numpy()[0]
        
        # Select action with highest Q-value
        action_idx = int(np.argmax(q_values))
        action = self.action_map[action_idx]
        
        # Confidence = softmax of Q-values
        exp_q = np.exp(q_values - np.max(q_values))
        softmax = exp_q / exp_q.sum()
        confidence = float(softmax[action_idx])
        
        return {
            'action': action,
            'confidence': confidence,
            'q_values': {self.action_map[i]: float(q_values[i]) for i in range(self.action_dim)},
            'source': 'RL_ENGINE',
            'epsilon': self.epsilon,
            'episode': self.episode_count
        }


if __name__ == "__main__":
    # Test RL Engine
    logger.info("Testing RL Evolution Engine...")
    
    engine = RLEvolutionEngine()
    
    # Create dummy state
    test_state = {
        'indicators': {'rsi': 65.0, 'adx': 35.0, 'atr': 120.0, 'basis': 2.5, 'pcr': 0.85, 'vix': 18.0, 'iv_skew': 1.1},
        'price': {'close': 25500.0, 'high': 25550.0, 'low': 25450.0, 'volume': 5000000, 'future_premium': 8.0},
        'greeks': {'call_gamma': 0.0025, 'put_gamma': 0.0018, 'net_gex': 500000, 'gamma_ratio': 1.4},
        'smc': {'order_block': True, 'fvg': False, 'liquidity_sweep': False, 'imbalance_score': 0.3},
        'regime': 'TRENDING_UP'
    }
    
    # Get recommendation
    recommendation = engine.get_recommendation(test_state)
    print(f"\nRL Recommendation: {json.dumps(recommendation, indent=2)}")
    
    print("\nRL Engine test complete!")
