# Titan Plus: Phase 3 ML Upgrade Roadmap
**Objective:** Evolve `BrainEngineML` from a Technical Analysis model to an Institutional Logic model.

---

## 1. The Current State ("The Retail Trader")
*   **Model:** XGBoost Classifier
*   **Features:** `ADX`, `PCR`, `Basis`, `Open Interest`.
*   **Limitations:** Reacts to price (lagging). Doesn't understand *why* price is moving (Liquidity/Greeks).

## 2. The Upgrade ("The Grandmaster")
We will inject the specific outputs from your new `grandmaster` module as **Core Features** for the AI.

### New Feature Vector (X)
| Feature Name | Source | Description |
| :--- | :--- | :--- |
| `nuclear_score` | `nuclear.py` | The master 0-1 confidence score. |
| `net_gex` | `greeks.py` | Total Gamma Exposure (in Crores). |
| `dealer_bias` | `greeks.py` | -1 (Short Gamma) to +1 (Long Gamma). |
| `smc_trend` | `smc.py` | -1 (Bear) to +1 (Bull). |
| `bos_detected` | `smc.py` | Boolean (0/1). |
| `macro_regime` | `macro.py` | -1 (Risk Off) to +1 (Risk On). |
| *Legacy Features* | *Existing* | ADX, RSI, PCR (kept as fallback). |

## 3. Implementation Steps

### Step A: Update `BrainEngineML` Features
1.  Import `SMCAnalyzer`, `GammaEngine`, `MacroRegime`.
2.  In `decide()`, run these analyzers *before* the ML prediction.
3.  Append their outputs to the `features` array.

### Step B: The "Hybrid" Decision Logic
Instead of just `if ml_prob > 0.5`, we will use a **Tiered Logic**:
```python
if nuclear_score > 0.85:
    return "NUCLEAR_ENTRY" (Full Size, ignore ML doubt)
elif ml_prob > 0.60 AND nuclear_score > 0.70:
    return "STANDARD_ENTRY"
else:
    return "NO_TRADE"
```

### Step C: Evolution (Retraining)
1.  Update `EvolutionEngine` to log these new feature columns to the CSV.
2.  Allow the model to "learn" naturally that `High GEX + Risk Off` = **Crash**.

---

## 4. Recommendation
*   **Immediate Action:** We should implement **Step B (Hybrid Logic)** first. This gives you immediate benefit of the new math without waiting for weeks of ML training data.
*   **Long Term:** Let the ML model retrain on this new rich data for 30 days.
