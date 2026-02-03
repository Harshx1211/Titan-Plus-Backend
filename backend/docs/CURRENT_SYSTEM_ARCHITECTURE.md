# Titan Plus: Current System Architecture (Phase 2)

**To:** External Developer / Collaborator  
**Date:** Feb 3, 2026  
**Version:** v9.9.8 (Live Production)

---

## 1. High-Level Overview
Titan Plus is an **Autonomous AI Trading System** specialized for Indian Derivative Markets (NIFTY/BANKNIFTY). It uses a "Human-in-the-Loop" architecture where an AI Brain processes market data, makes decisions using Price Action + ML, and presents them on a Real-Time Dashboard.

**Current Status:** "Phase 2" (Intermediate).
*   **Strengths:** Excellent technical analysis (Indicators), basic Price Action, robust risk management.
*   **Limitations:** Lacks deep institutional logic (SMC, Advanced Greeks, Macro) - *This is where we need your help.*

---

## 2. Technology Stack

*   **Backend:** Python 3.12 (FastAPI)
*   **Frontend:** Next.js + TailwindCSS (Real-time Dashboard)
*   **Database:** Supabase (PostgreSQL) for Trade/Signal Logging
*   **ML Engine:** XGBoost + Scikit-Learn (Classification Models)
*   **Brokers:** Shoonya (Finvasia) for Data, Groww for Execution (simulated for now).
*   **Deployment:** Hugging Face Spaces (Dockerized)

---

## 3. Core Modules (The "Brain")

The system logic is divided into these key Python files:

### A. Data Layer (`providers.py`)
*   **Role:** The "Senses".
*   **Function:** Fetches Live LTP, Option Chain (all strikes), and OI Data every 3 seconds.
*   **Features:** Auto-switch fallbacks (if Broker A fails -> switch to Broker B).

### B. The Strategist (`strategist.py`)
*   **Role:** The "Analyst".
*   **Function:** Determines the **Market Regime** (Trending vs. Sideways vs. Choppy) using ADX, RSI, and Bollinger Bands.
*   **Output:** `REGIME_TRENDING_UP`, `REGIME_SIDEWAYS`, etc.

### C. The Brain (`brain_engine_ml.py`)
*   **Role:** The "Decision Maker".
*   **Function:** Aggregates inputs -> Runs Rules + ML Model -> Outputs Signal.
*   **Current Logic (Phase 2):**
    *   *Rule Gate:* "Is RSI < 70? Is Trend Up? Is VWAP Supporting?"
    *   *ML Gate:* XGBoost Model predicts probability of success.
    *   *Risk Gate:* "Is VIX safe? Is Stop Loss acceptable?"

### D. Option Engine (`option_engine.py`)
*   **Role:** The "Sniper".
*   **Function:** Selects the *exact* strike price to trade.
*   **Logic:** Scans for Liquidity, Gamma Safety, and Premium Pricing (fair value).

### E. Evolution Engine (`evolution_engine.py`)
*   **Role:** The "Teacher".
*   **Function:** Runs at 3:30 PM. Reviews all decisions, calculates "Regret" (Missed Moves), and re-trains the ML model overnight.

---

## 4. The Data Flow Pipeline

1.  **Ingestion:** `api.py` triggers a loop every 3 seconds.
2.  **Processing:** `BrainEngine` receives OHLCV + Option Chain.
3.  **Analysis:**
    *   `Strategist` defines the Regime.
    *   `Brain` checks "Hard Rules" (Vetoes).
    *   `Brain` generates "Soft Score" (Probability).
4.  **Execution:** If `Score > Threshold`, a Signal is logged to Supabase.
5.  **Feedback:** The Frontend polls the API and lights up "ACTIVE" or displays the Trade Card.

---

## 5. Where "Grandmaster" Fits In (Phase 3)
We want to insert your new logic **between Step 2 and Step 3**.
Instead of just relying on "RSI" or "VWAP," the Brain will query your new `Grandmaster` module:
*   *"Do we have an Order Block?"* (SMC)
*   *"Is GEX positive?"* (Greeks)
*   *"Is DXY crashing?"* (Macro)

This new inputs will massively increase the accuracy of the **Entry Signal**.
