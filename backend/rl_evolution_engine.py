#!/usr/bin/env python3
"""
Reinforcement Learning Evolution Engine
Uses Deep Q-Network (DQN) for continuous learning from live trades
"""

import logging
import numpy as np
import json
import random
import os
from datetime import datetime
from collections import deque

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Mocking nn.Module to prevent NameError at class definition time
    class MockModule: pass
    class MockNN: Module = MockModule
    nn = MockNN

from brain_engine_ml import BrainEngineML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rl_evolution")

class QNetwork(nn.Module):
    def __init__(self, state_size=15, action_size=2, hidden_size=128):
        super(QNetwork, self).__init__()
        self.fc1 = nn.Linear(state_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, action_size)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)

class RLEvolutionEngine:
    def __init__(self, brain: BrainEngineML):
        self.brain = brain
        self.rl_enabled = TORCH_AVAILABLE
        
        if not TORCH_AVAILABLE:
            logger.warning("RL: PyTorch not available, using basic reputation learning")
            return
            
        self.state_size = 15
        self.action_size = 2
        self.gamma, self.epsilon = 0.95, 1.0
        self.epsilon_min, self.epsilon_decay = 0.01, 0.995
        self.learning_rate = 0.001
        self.batch_size, self.target_update = 32, 100
        
        self.memory = deque(maxlen=10000)
        self.steps = 0
        
        self.policy_net = QNetwork(self.state_size, self.action_size)
        self.target_net = QNetwork(self.state_size, self.action_size)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.learning_rate)
        self.criterion = nn.MSELoss()
        self.state_file = "rl_state.pt"
        self.load_state()

    def _prepare_state(self, features, regime):
        regime_map = {'TRENDING': 0, 'SIDEWAYS_STRONG': 1, 'SIDEWAYS_NORMAL': 2, 'SIDEWAYS_WEAK': 3, 'UNCERTAIN': 4}
        state = [
            features.get('ADX', 25.0) / 50.0, features.get('BASIS_RES', 0.5),
            features.get('PCR', 1.0), features.get('OI_RES', 0.5),
            regime_map.get(regime, 4) / 4.0,
            self.brain.authority.get('TRENDING', 1.0), self.brain.authority.get('SIDEWAYS_NORMAL', 1.0),
            self.brain.authority.get('UNCERTAIN', 1.0),
            self.brain.feature_reputation.get('ADX', 1.0), self.brain.feature_reputation.get('BASIS_RES', 1.0),
            self.brain.feature_reputation.get('PCR', 1.0), self.brain.feature_reputation.get('OI_RES', 1.0),
            datetime.now().hour / 24.0, datetime.now().minute / 60.0, self.epsilon
        ]
        return np.array(state, dtype=np.float32)

    def calculate_reward(self, decision, outcome, performance):
        mfe, mae = performance.get('mfe', 0), performance.get('mae', 0)
        if decision == 1: # APPROVE
            return min(mfe * 0.1, 10.0) if outcome else -mae * 0.2
        else: # BLOCK
            return 2.0 if (not outcome or mfe < 10) else -5.0

    def replay(self):
        if len(self.memory) < self.batch_size: return
        batch = random.sample(self.memory, self.batch_size)
        states = torch.FloatTensor(np.array([exp[0] for exp in batch]))
        actions = torch.LongTensor([exp[1] for exp in batch])
        rewards = torch.FloatTensor([exp[2] for exp in batch])
        next_states = torch.FloatTensor(np.array([exp[3] for exp in batch]))
        dones = torch.FloatTensor([exp[4] for exp in batch])
        
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1))
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            target_q = rewards + (1 - dones) * self.gamma * next_q
        
        loss = self.criterion(current_q.squeeze(), target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        if self.epsilon > self.epsilon_min: self.epsilon *= self.epsilon_decay
        self.steps += 1
        if self.steps % self.target_update == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def log_trade_outcome(self, state, action, outcome, performance):
        if not self.rl_enabled: return
        reward = self.calculate_reward(action, outcome, performance)
        self.memory.append((state, action, reward, state, False))
        self.replay()

    def save_state(self):
        if self.rl_enabled:
            torch.save({'policy_net': self.policy_net.state_dict(), 'epsilon': self.epsilon, 'steps': self.steps}, self.state_file)

    def load_state(self):
        if self.rl_enabled and os.path.exists(self.state_file):
            checkpoint = torch.load(self.state_file)
            self.policy_net.load_state_dict(checkpoint['policy_net'])
            self.epsilon, self.steps = checkpoint['epsilon'], checkpoint['steps']

if __name__ == "__main__":
    brain = BrainEngineML()
    rl = RLEvolutionEngine(brain)
    print(f"RL Enabled: {rl.rl_enabled}")
