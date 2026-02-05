# Phase 4 Implementation Plan: Advanced Intelligence & Optimization

**Goal**: Elevate Titan Plus from a robust heuristic system to a state-of-the-art Adaptive AI using Policy Gradient methods (PPO) and Automated Hyperparameter Tuning.

## 1. Reinforcement Learning Upgrade (DQN -> PPO)
**Current**: Deep Q-Network (DQN). Good for discrete actions, but can be unstable and sample-inefficient.
**New**: Proximal Policy Optimization (PPO).
*   **Architecture**: Actor-Critic (Two Networks).
    *   **Actor**: Outputs probability distribution of actions (Buy/Sell/Hold).
    *   **Critic**: Estimates the value of the current state.
*   **Benefits**: More stable convergence, handles stochastic policies better, less prone to catastrophic forgetting.
*   **Inputs**: Market Regime, Normalized Technicals (RSI, ADX, Basis), Order Flow Imbalance.
*   **Outputs**: Action Probability (Confidence).

## 2. Machine Learning Optimization (Hyperopt)
**Current**: Fixed XGBoost hyperparameters.
**New**: `optimization_engine.py` using **Optuna**.
*   **Objective**: Maximize Sharpe Ratio or Win Rate over validation set.
*   **Parameters**: `max_depth`, `learning_rate`, `n_estimators`, `gamma`, `subsample`.
*   **Workflow**:
    1.  Load historical data.
    2.  Define objective function (Backtest Logic).
    3.  Run 100 trials.
    4.  Save best model to `models/xgboost_optimized.json`.

## 3. Risk Simulation (Monte Carlo)
**New**: `simulation_engine.py`.
*   **Logic**: Run 10,000 simulations of the next 100 trades based on current Win Rate and Risk/Reward parameters.
*   **Output**: Probability of Ruin (Drawdown > 20%).
*   **Action**: If Ruin Prob > 1%, force-reduce position sizing.

## Proposed File Changes

### [NEW] `backend/rl_engine_ppo.py`
*   `ActorCritic` Network (PyTorch).
*   `PPOAgent` class with `update` (learning) and `act` (inference) methods.
*   `Memory` buffer for trajectories.

### [NEW] `backend/optimization_engine.py`
*   `OptunaOptimizer` class.
*   `objective` function wrapping the `Brain` logic.

### [MODIFY] `backend/brain_engine_enhanced.py`
*   Add toggle to switch between `RLEngine` (DQN) and `PPOAgent`.
*   Integrate Monte Carlo checks in `decide()`.

### [MODIFY] `backend/requirements.txt`
*   Add `optuna`.

## Verification Plan
1.  **Unit Test**: Verify PPO loss calculation decreases over dummy data.
2.  **Integration Test**: Ensure Brain can swap DQN for PPO without crashing.
3.  **Performance Check**: Run Optimization Engine on sample data.
