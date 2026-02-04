import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import os
import json
import logging
from collections import deque
from typing import Dict, List, Tuple

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rl_ppo")

# Device Config
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Hyperparameters
LR_ACTOR = 0.0003
LR_CRITIC = 0.001
GAMMA = 0.99
K_EPOCHS = 4          # Update policy for K epochs
EPS_CLIP = 0.2        # Clip parameter for PPO
STATE_DIM = 25        # Matches current feature vector
ACTION_DIM = 3        # Buy Call, Buy Put, Hold
HIDDEN_DIM = 128

class ActorCritic(nn.Module):
    def __init__(self):
        super(ActorCritic, self).__init__()
        
        # Shared Feature Extractor
        self.fc1 = nn.Linear(STATE_DIM, HIDDEN_DIM)
        self.fc2 = nn.Linear(HIDDEN_DIM, HIDDEN_DIM)
        
        # Actor Head (Policy)
        self.actor = nn.Linear(HIDDEN_DIM, ACTION_DIM)
        
        # Critic Head (Value)
        self.critic = nn.Linear(HIDDEN_DIM, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return x

    def act(self, state):
        x = self.forward(state)
        action_probs = F.softmax(self.actor(x), dim=-1)
        dist = torch.distributions.Categorical(action_probs)
        
        action = dist.sample()
        action_logprob = dist.log_prob(action)
        
        return action.item(), action_logprob.item(), self.critic(x)

    def evaluate(self, state, action):
        x = self.forward(state)
        action_probs = F.softmax(self.actor(x), dim=-1)
        dist = torch.distributions.Categorical(action_probs)
        
        action_logprobs = dist.log_prob(action)
        dist_entropy = dist.entropy()
        state_values = self.critic(x)
        
        return action_logprobs, state_values, dist_entropy

class PPOAgent:
    def __init__(self, model_path="ppo_agent.pth"):
        self.policy = ActorCritic().to(device)
        self.optimizer = optim.Adam([
            {'params': self.policy.actor.parameters(), 'lr': LR_ACTOR},
            {'params': self.policy.critic.parameters(), 'lr': LR_CRITIC}
        ])
        
        self.policy_old = ActorCritic().to(device)
        self.policy_old.load_state_dict(self.policy.state_dict())
        
        self.buffer = [] # Stores (state, action, log_prob, reward, is_term, value)
        self.model_path = model_path
        self.load_model()

    def get_action(self, state_vector):
        """Select action using the current policy (Actor)"""
        if isinstance(state_vector, np.ndarray):
            state_vector = torch.FloatTensor(state_vector).to(device)
        
        with torch.no_grad():
            action, log_prob, value = self.policy_old.act(state_vector)
            
        return action, log_prob, value.item()

    def store_transition(self, state, action, log_prob, reward, done, value):
        self.buffer.append((state, action, log_prob, reward, done, value))

    def update(self):
        """PPO Update Step with GAE"""
        if not self.buffer: return
        
        # Convert buffer to tensors
        states = torch.stack([x[0] for x in self.buffer]).detach().to(device).squeeze()
        actions = torch.tensor([x[1] for x in self.buffer], dtype=torch.float32).to(device)
        old_log_probs = torch.tensor([x[2] for x in self.buffer], dtype=torch.float32).to(device)
        rewards = [x[3] for x in self.buffer]
        dones = [x[4] for x in self.buffer]
        values = [x[5] for x in self.buffer]
        
        # GAE (Generalized Advantage Estimation)
        returns = []
        gae = 0
        lambda_val = 0.95
        
        # Calculate advantages and returns (Reverse Loop)
        # Note: We need next_value for the last step. Assuming 0 for now if terminal, 
        # or we could bootstrap from the last observed state value if available.
        next_value = 0 
        
        for i in reversed(range(len(rewards))):
            if dones[i]: next_value = 0
            
            delta = rewards[i] + GAMMA * next_value - values[i]
            gae = delta + GAMMA * lambda_val * gae * (0 if dones[i] else 1)
            
            # Return = Advantage + Value
            returns.insert(0, gae + values[i])
            next_value = values[i]
            
        returns = torch.tensor(returns, dtype=torch.float32).to(device)
        
        # Normalize returns for stability
        returns = (returns - returns.mean()) / (returns.std() + 1e-7)

        # Optimize for K epochs
        for _ in range(K_EPOCHS):
            # Evaluate using current policy
            log_probs, state_values, dist_entropy = self.policy.evaluate(states, actions)
            state_values = torch.squeeze(state_values)
            
            # Ratios and Advantages
            ratios = torch.exp(log_probs - old_log_probs)
            advantages = returns - state_values.detach()
            
            # Surrogate Loss (Clipped)
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1-EPS_CLIP, 1+EPS_CLIP) * advantages
            
            # Loss Components
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = 0.5 * F.mse_loss(state_values, returns)
            entropy_loss = -0.01 * dist_entropy.mean()
            
            loss = actor_loss + critic_loss + entropy_loss
            
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            
        # Synch Old Policy
        self.policy_old.load_state_dict(self.policy.state_dict())
        self.buffer.clear()
        self.save_model()
        logger.info("PPO Update Complete (GAE).")

    def save_model(self):
        torch.save(self.policy.state_dict(), self.model_path)

    def load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.policy.load_state_dict(torch.load(self.model_path))
                self.policy_old.load_state_dict(self.policy.state_dict())
                logger.info(f"Loaded PPO Model from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load PPO model: {e}")
