# Titan Plus: "Grandmaster" Logic Specification

**FINAL ROADMAP**
*Based on Expert Review (Feb 3, 2026)*

This document contains the proprietary institutional logic, mathematical formulas, and "Nuclear" entry filters required to build the Phase 3-5 BrainEngine. These features separate retail execution from professional edge.

---

## Phase 3: Institutional Structure Mathematics (The Engine)

### 1. Advanced BOS/ChoCh Detection (Multi-Timeframe)
*   **Traditional BOS**: `Close > max(High[i-20:i-1])` (Lags too much).
*   **Institutional BOS (True)**: Requires 3x Confirmation.
    1.  `HTF_BOS = Close_1H > max(High_1H[i-10:i-1])` (Trend Align)
    2.  `LTF_Structure = Close_5M > max(High_5M[i-5:i-1])` (Signal)
    3.  `Displacement = (Close - Open) / ATR(14) > 1.8` (Commitment)
*   **ChoCh Precision**:
    *   `ChoCh_Bear = Close < (Recent_HH + Recent_LH)/2` (50% Fair Value retracement).
    *   **Validity Check**: `ChoCh_Bear` AND `Liquidity_Grab (Low < SSL)` AND `Volume > 1.5x Avg`.

### 2. Order Block (OB) Precision Engineering
*   **Definition**: NOT a single candle. It is a **Candle Cluster**.
*   **Criteria**:
    *   `Candles`: 2-5 consecutive down-closes before impulse.
    *   `Displacement`: Impulse Leg > 3x OB Range.
    *   `Unmitigated`: Price never returned to 50% of OB zone.
    *   `Reaction`: Previous history of >= 2 bounces off this zone.
*   **Zone**: `[max(Opens), min(Closes)]`.
*   **Entry Trigger**: Price touches Zone AND `RSI(7) < 35` AND `Delta > 0`.

### 3. FVG Institutional Filtering
*   **Logic**: `Low[0] > High[-2]` (Bullish Gap).
*   **Strength Score (0.0 - 1.0)**:
    *   `Gap_Size / ATR(20) * 0.4`
    *   `Distance_Struct * 0.3`
    *   `Time_Unfilled * 0.2`
    *   `Vol_Profile_Supp * 0.1`
*   **Rule**: Trade only if `Score > 0.7`.

---

## Phase 4: Dealer Options Flow (The Mechanics)

### 1. Gamma Exposure Grid (GEX)
*   **Formula**: `GEX[strike] = Σ[Gamma(K) * OI(K) * 100 * (Spot/1000)²]`
*   **Flip Zones**: Strike where `∂GEX/∂spot` changes sign.
*   **Volatility Explosion**: `|Spot - Flip_Zone| < 0.5%` AND `|GEX| > Threshold`.
*   **Pinning**: `Max_Pain = Strike with Max(CallOI + PutOI)`.

### 2. Vanna & Charm (Second-Order Greeks)
*   **Vanna Flow**: Dealer buys when Vol drops (`Spot * Vol * Gamma`).
*   **Charm Decay**: Dealer adjusts for time (`-Theta / Spot`).
*   **Institutional Signal**:
    *   *Squeeze*: `Vol < 15` AND `Spot moves 1%` -> Dealers forced to buy 3x Delta.
    *   *OPEX*: If `GEX * Charm > Threshold` -> Avoid Counter-Trend.

---

## Phase 5: Multi-Asset Regime & Confluence (The Judge)

### 1. Correlation Regime Switching
*   **Nifty Score**: `w1*DXY_Corr + w2*Yield_Corr + w3*Crude_Impact`.
*   **Weights (Risk On)**: `DXY(-0.4)`, `10Y(-0.6)`, `Crude(+0.3)`.
*   **Weights (Risk Off)**: `DXY(+0.2)`, `10Y(-0.8)`, `Crude(-0.1)`.
*   *VIX Adjustment*: If `VIX > 20`, amplify weights by 1.5x.

### 2. FII Flow Momentum
*   **FII_Bias**: `(Net_FII - EMA(10)) / StdDev(20)`.
*   **Institutional Edge**: `0.7 * FII_Bias + 0.3 * DII_Bias`.
*   **Rule**: Only trade Macro Bias if `|Inst_Edge| > 1.2σ`.

---

## PROPRIETARY CONFLUENCE ENGINE
### The "Nuclear" Entry Filter (>65% Win Rate)

**Entry_Score = Σ (Weight * Condition)**

| Condition | Weight | Logic |
| :--- | :--- | :--- |
| **SMC Alignment** | **0.25** | BOS/ChoCh Direction |
| **Zone Confluence** | **0.20** | OB + FVG + Fib(0.618) |
| **Liquidity Confirmed** | **0.15** | Stop Hunt Complete (SSL/BSL) |
| **Volume Delta** | **0.15** | CVD Divergence |
| **Time Filter** | **0.10** | Killzone Active |
| **GEX Alignment** | **0.10** | Gamma Flip Support |
| **Regime Bias** | **0.05** | Macro Alignment |

**Decision Gate**:
*   `Entry_Score > 0.85` -> **NUCLEAR ENTRY (Full Size)**
*   `Entry_Score > 0.70` -> **Standard Entry (Half Size)**
*   `Entry_Score < 0.70` -> **NO TRADE**

### Killzone Precision (IST)
1.  **Primary**: 09:20 - 10:00 (80% Daily Range estab).
2.  **Secondary**: 13:25 - 14:00 (London Close flow).
3.  **Tertiary**: 15:10 - 15:25 (Close Auction).

---

## MISSING INSTITUTIONAL CONCEPTS ADDED

### 1. Market Maker Inventory Model
*   `Inventory = Σ (Open_Contracts * (Spot - Strike)/Spot)`.
*   `Rebalance_Flow = -∂Inventory/∂Spot`.
*   **Signal**: Heavy Dealer Buying when `Spot > 50th Percentile` AND `Rebalance > 0`.

### 2. Optimal Trade Location (OTL)
*   `OTL_Score[Price] = 0.4*Zone + 0.2*Fib + 0.2*POC + 0.1*GEX + 0.1*Delta`.
*   **Execution**: Limit Order at `argmax(OTL_Score)` with 0.3% tolerance.

---

## Phase 6: Chetan Singh Institutional Integration
*Based on Strategy Deployment Pack (Feb 5, 2026)*

Integration of 5 core intraday/scalping setups from Chetan Singh's Nifty/BankNifty literature, reinforced with Titan Plus SMC filters.

### 1. Hammer Reversal Scalp (S1 Support)
*   **Killzone**: 09:15 - 10:30 IST.
*   **Trigger**: Hammer at S1 Pivot (±0.5%).
*   **Nuclear Filter**: `Wick > 2.5x Body` AND `RSI < 35` AND `Volume > 2.5x 20MA`.
*   **Alignment**: Bullish Order Block touch or proximity.

### 2. Bullish Engulfing R1 Rejection
*   **Killzone**: 14:15 - 15:00 IST.
*   **Condition**: Prior bearish candle fully engulfed at R1 resistance level.
*   **Bias**: Counter-trend rejection or breakout support flip.

### 3. Doji Central Pivot Reversal
*   **Logic**: Doji formation within 0.2% of Central Pivot.
*   **Confirmation**: Next candle close above Doji high + Positive MACD Histogram.

### 4. Three White Soldiers (Institutional Breakout)
*   **Pattern**: 3 consecutive bullish candles with closes > 70% of candle range.
*   **Confluence**: Price above VWAP + RSI Divergence resolution.

### 5. Evening Star R2 Rejection (Bearish)
*   **Setup**: Evening star sequence (Large Bull -> Star -> Large Bear) at R2.
*   **Filter**: `RSI > 70` AND `Volume Declining` on Star candle.

---

### Implementation Target
*   **Input Layer**: 127 Features (42 SMC, 35 Vol, 25 Options, 15 Macro, 10 Time).
*   **Strategy Core**: `book_strategies.py` (Hammer, Engulfing, Doji, Soldiers, Evening Star).
*   **Backtest Goal**: >70% Combined Win Rate (SMC + Chetan Hybrid).
