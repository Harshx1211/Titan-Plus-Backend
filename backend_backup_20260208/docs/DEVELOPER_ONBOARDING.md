# Titan Plus: Full Developer Onboarding & System Specification

**Objective:** This document provides a high-fidelity blueprint for a developer joining the **Titan Plus** project. It outlines the "inner workings" of the neural engines and the cross-platform integration requirements.

---

## 1. The Technology Stack

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Backend** | Python 3.12 (FastAPI) | High-concurrency async server. |
| **Logic** | Pandas, Pandas-TA | Statistical & Technical indicator processing. |
| **Intelligence** | XGBoost, PyTorch (RL) | Probability estimation (Classification) and Strategy Discovery. |
| **Frontend** | Next.js 14, TailwindCSS | Premium institutional dashboard with real-time WebSocket/Polling connectivity. |
| **Storage** | Supabase (PostgreSQL) | Persistence for signals, trade history, and "Brain" states. |
| **Infrastructure** | Docker | Deployment to Hugging Face Spaces. |

---

## 2. System Architecture & Information Flow

The system operates on a **High-Frequency Analysis Loop** (1-3 second ticks):

1.  **Data Acquisition (`providers.py`)**: Fetches snapshots from Shoonya (Primary) or Groww (Fallback).
2.  **Structural Cleaning (`engines.py`)**: Converts raw ticks into OHLCV time-series with an ordered `DatetimeIndex` for indicators.
3.  **Regime Classification (`strategist.py`)**: Analyzes market state (e.g., `SIDEWAYS_STRONG` vs `TRENDING_UP`).
4.  **Neural Inference (`api.py` / `brain_engine_ml.py`)**: 
    - **SMC Engine**: Looks for institutional concepts (Order Blocks, FVG).
    - **Pattern Engine**: Scans for price action patterns (Hammer, Engulfing).
    - **XGBoost Brain**: Combines Greeks (GEX/Gamma), PCR, and Volume to output a success probability.
5.  **Execution Logging**: Signals are logged to Supabase and pushed to the Dashboard and Telegram.

---

## 3. Key Intelligence Modules

### `BrainEngineML` (The Logical Hub)
- **Classification**: Uses a pre-trained `brain_model.pkl` to verify entry signals.
- **Normalization**: Applies Sigmoid-scaling to Z-scores of indicators (ADX, Basis, PCR) to keep logic stable during volatility.
- **Veto Logic**: Contains institutional "Meta-Vetoes" (e.g., Basis instability, VIX spikes).

### `RLEvolutionEngine` (The Learning Core)
- **Spontaneous Discovery**: Uses a Deep Q-Network (DQN) to learn from its own mistakes.
- **Efficacy Tracking**: Maps "Decision + Regime" to "Outcome (PnL)" to discover strategies the developer didn't explicitly program.

### `Grandmaster Engine` (SMC/Institutional)
- **Nuclear Scorecard**: A final confluence filter that requires agreement between Price Action, Option Flow, and Macro sentiment.

---

## 4. Requirements & Knowledge Base

### Technical Knowledge
1.  **Financial API Logic**: Understanding of tick-by-tick data streaming and option chain aggregation.
2.  **Vectorized Operations**: Proficiency in `pandas` for processing thousands of market rows without latency.
3.  **ML Persistence**: Knowledge of how to save/restore model states and handle version shifts in Python pickling.

### Environment Requirements
Developers must configure a `.env` file with:
- `SUPABASE_URL` / `SUPABASE_KEY`
- `SHOONYA_USER` / `SHOONYA_PWD` / `SHOONYA_TOKEN`
- `TELEGRAM_BOT_TOKEN` / `CHAT_ID`

---

## 5. Development Roadmap (Phase 3)
1.  **Full RL Activation**: Fully coupling the `rl_state.pt` into the `DECIDE` path for self-correcting strategies.
2.  **Institutional Confluence**: Bringing more SMC logic (Liquidity Sweeps) into the `PatternEngine`.
3.  **Sentiment Processing**: Integrating NLP for real-time news impact analysis.
