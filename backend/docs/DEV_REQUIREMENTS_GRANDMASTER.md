# Titan Plus: Grandmaster Engine - Development Requirements

**To:** Lead Developer / Quantitative Strategist  
**From:** Titan Plus Architecture Team  
**Subject:** Technical Requirements for "Grandmaster" Logic Module (Phases 3-5)

---

## 1. Project Overview
We are adding a modular **"Grandmaster Engine"** to an existing Python-based AI trading system (Titan Plus).
**Goal:** Integrate institutional-grade logic (SMC, Advanced Greeks, Macro) without destabilizing the core execution engine.
**Architecture:** The new code must exist as a standalone library (`grandmaster/`) that the main `BrainEngine` imports and queries.

## 2. Technical Standards
*   **Language:** Python 3.10+
*   **Core Libraries:** `pandas`, `numpy`, `scipy` (if needed).
*   **Style:** Functional or Class-based. **Must use Type Hinting.**
*   **Performance:** All calculations must be vectorized (no slow `for` loops over DataFrames). Goal: <200ms execution time per cycle.

## 3. Data Inputs Available
Your code will receive the following data structures. Please design your functions to accept these inputs:

1.  **`ohlcv_df` (Pandas DataFrame)**:
    *   Columns: `['timestamp', 'open', 'high', 'low', 'close', 'volume']`
    *   Timeframes: 1min, 5min, 15min, 1Hour (Multi-timeframe access provided).
2.  **`option_chain` (Pandas DataFrame)**:
    *   Columns: `['strike', 'expiry', 'call_oi', 'call_ltp', 'call_iv', 'call_delta', 'call_gamma', 'put_oi', ...]`
3.  **`macro_data` (Dictionary)**:
    *   Keys: `{'VIX': float, 'DXY': float, 'USDINR': float, 'CRUDE': float, 'FII_NET': float}`

## 4. Required Modules & Logic Specifications

We need "clean, basic code" for the following four modules. We will optimize and integrate them.

### Module A: `SMC_Analyzer` (Price Action)
**Input:** `ohlcv_df` (Multi-timeframe)
**Output:** Dictionary with keys `['is_bos', 'is_choch', 'zones', 'liquidity_grab']`
**Requirements:**
*   **BOS/ChoCh**: Function to identify "true" breaks vs. fakeouts.
*   **Order Blocks**: Identify consecutive candle clusters (as detailed in our `KNOWLEDGE.md`) that are unmitigated. Return a list of `{'price_range': (low, high), 'type': 'bull/bear'}`.
*   **FVG**: Detect Fair Value Gaps and track if they are filled or open.

### Module B: `Gamma_Engine` (Option Flows)
**Input:** `option_chain`, `current_spot`
**Output:** Dictionary `{'net_gex': float, 'flip_level': float, 'dealer_bias': str}`
**Requirements:**
*   **GEX Calc**: Implement the formula: `Σ [Gamma * OI * 100 * (Spot² * 0.01)]`.
*   **Flip Zone**: Find the strike where GEX flips from positive to negative.
*   **Vanna/Charm**: Estimate second-order flow (optional, if math allows).

### Module C: `Macro_Regime` (Confluence)
**Input:** `macro_data`
**Output:** `regime_score` (-1.0 to +1.0)
**Requirements:**
*   **Weighted Scoring**: Combine VIX, DXY, and Crude correlations into a single sentiment score.
*   **FII Momentum**: standardized score of FII flows (Z-score).

### Module D: `Nuclear_Scorecard` (The Judge)
**Input:** Outputs from Modules A, B, C + `current_time`
**Output:** `Entry_Signal` (bool), `Position_Sizing` (float 0.0 - 1.0)
**Requirements:**
*   **Weighted Logic**: Implement the scorecard:
    *   `Score = (SMC*0.25) + (Zones*0.2) + (Liquidity*0.15) + (Delta*0.15) + (Time*0.1) + (GEX*0.1) + (Macro*0.05)`
*   **Thresholds**:
    *   `> 0.85`: Nuclear Entry (Size 1.0)
    *   `> 0.70`: Standard Entry (Size 0.5)
    *   `< 0.70`: No Trade

## 5. Deliverable Format
Please provide Python files (e.g., `smc.py`, `greeks.py`) containing the logic classes.
*   Docs strings are appreciated.
*   **Prioritize correctness over speed** (we can optimize later).

---

**Note to Developer:**
The definitions for all concepts (BOS, OB, GEX, etc.) are strictly defined in the attached `KNOWLEDGE.md`. Please adhere **strictly** to those mathematical definitions.
