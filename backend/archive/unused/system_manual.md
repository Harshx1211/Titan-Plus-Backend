# Titan Plus System Manual (Phase 3)

## 1. System Overview
Titan Plus is an institutional-grade algorithmic trading system designed for the Indian Derivatives Market (NIFTY, BANKNIFTY, SENSEX). It uses a **Hybrid Intelligence Architecture** that combines traditional technical analysis, machine learning (XGBoost), Reinforcement Learning (RL), and Smart Money Concepts (SMC) to generate high-probability trade signals.

## 2. Architecture & Data Flow

### 2.1 The Nervous System (API & Orchestration)
The system runs on a **FastAPI** backend (`api.py`), but the heart of the operation is the `run_engine_loop` background thread.
*   **Polling**: Every second, it fetches real-time snapshots (Spot Price, Futures Price, OI) from multiple brokers (**Shoonya** primary, **Groww** fallback).
*   **Parallelism**: Data fetching happens in parallel threads to minimize latency.
*   **Preprocessing**: The orchestration layer calculates basic indicators instantly:
    *   **ADX**: Trend Strength
    *   **ATR**: Volatility (for Stop Loss sizing)
    *   **RSI**: Momentum
    *   **Basis**: Spot-Future Spread (a key institutional signal)

### 2.2 The Intelligence Core (Enhanced Brain)
Once data is prepared, it is sent to the `EnhancedBrainEngine`, which acts as the supreme decision-maker using a **4-Layer Analysis Process**:

#### Layer 1: The Quant (XGBoost)
*   **Role**: Pattern Recognition.
*   **Logic**: Uses a pre-trained Gradient Boosting model to analyze numerical features (OI change, PCR, Basis, GEX).
*   **Output**: A probability score (0.0 to 1.0) indicating the likelihood of trade success based on historical quantitative patterns.

#### Layer 2: The Guardian (Meta-Vetoes)
*   **Role**: Risk Management & Safety.
*   **Logic**: Applies hard rules to block trades in dangerous conditions:
    *   **Basis Instability**: If futures de-couple from spot (>5 pts spread anomaly).
    *   **VIX Spike**: If volatility explodes (>30), automatic shutdown.
    *   **Liquidity Check**: Blocks trades during low-volume lull periods.
*   **Action**: Can issue a "HARD VETO" that overrides all other signals.

#### Layer 3: The Strategist (RL Engine)
*   **Role**: Adaptive Learning.
*   **Logic**: A Deep Q-Network (DQN) that mimics a human trader learning from experience.
    *   It observes the "State" (Market Regime + Indicators).
    *   It references its "Memory" (Replay Buffer) of thousands of past trades.
    *   It recommends an action (BUY_CALL, BUY_PUT, HOLD).
*   **Phase 3 Upgrade**: Uses a self-correcting feedback loops (MFE/MAE analysis) to refine its policy overnight.

#### Layer 4: The Grandmaster (SMC Engine)
*   **Role**: Institutional Order Flow Analysis.
*   **Logic**: Scans raw price action (OHLCV) for "Smart Money" footprints:
    *   **Order Blocks (OB)**: Zones where institutions placed massive orders.
    *   **Fair Value Gaps (FVG)**: Price inefficiencies that the market often rushes to fill.
    *   **Liquidity Sweeps**: "Stop Hunts" where price briefly breaks a level to trap retail traders before reversing.
*   **Output**: A Confluence Score. A signal interacting with a valid Order Block receives a massive confidence boost.

### 2.3 The Decision (Confluence)
The Brain calculates a final weighted score:
`Score = (0.4 * XGBoost) + (0.3 * RL) + (0.3 * SMC)`

*   **APPROVE**: If Score > 0.75 (and no Vetoes).
*   **BLOCK**: If Score < 0.75.

## 3. Execution & Feedback Loop

### 3.1 Signal Generation
If the Brain approves:
1.  **Option Selection**: The `OptionEngine` selects the best strike (ITM/ATM) based on Delta, Gamma, and Liquidity.
2.  **Sizing**: The `RiskEngine` calculates lot size based on account value and conviction level.
3.  **Broadcast**: The signal is sent to the Frontend (Dashboard) and Telegram.

### 3.2 Evolution (Overnight Learning)
The system doesn't just run; it improves.
*   **Evolution Engine**: Every night (or manually triggered), it reviews the day's "Thoughts" and Trade Outcomes.
*   **Feature Reputation**: If a specific indicator (e.g., RSI) caused false signals, its "Reputation" is lowered, reducing its weight in future decisions.
*   **Governor**: A safety module ensures the system effectively learns (tightening thresholds if win-rate drops), but prevents it from becoming too loose (never lowers standards automatically).

## 4. Operational Modes
*   **Live Mode**: Real money/paper trading with active connections.
*   **Passive Mode**: "Ghost" running—analyzing and logging but not signaling (used for warm-up).
*   **Shadow Mode**: Runs a secondary "Shadow Brain" to test experimental strategies effectively without risking capital.
