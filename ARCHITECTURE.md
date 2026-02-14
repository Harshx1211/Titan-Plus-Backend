# Titan Crypto Brain V3 - System Architecture

## 🧠 Core Philosophy
This system implements **institutional-grade Smart Money Concepts (SMC)** combined with **self-evolving AI** to generate high-probability trading signals for manual execution.

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    TITAN BRAIN V3                           │
│                  (brain.py - Orchestrator)                  │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ SMC Engine   │    │  AI Engine   │    │ Risk Engine  │
│ (smc_logic)  │    │(ai_decision) │    │(risk_engine) │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │ Data Engine  │        │  Supabase    │
        │  (engine.py) │        │ (database.py)│
        └──────────────┘        └──────────────┘
                │                       │
                ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │ CCXT/Binance │        │ Cloud Storage│
        │  (Public API)│        │ (Logs/Trades)│
        └──────────────┘        └──────────────┘
```

## 🎯 Signal Generation Pipeline

### 1. Data Ingestion (engine.py)
- Fetches 200 candles of 15m data from Binance Futures
- Retry logic with exponential backoff
- Data quality validation

### 2. SMC Analysis (smc_logic.py)
**Institutional Price Action Detection:**
- ✅ Volume-weighted Order Blocks (1.5x+ volume required)
- ✅ Swing-point structure analysis (5-candle confirmation)
- ✅ Liquidity zone mapping (equal highs/lows)
- ✅ BOS/CHoCH detection (proper swing validation)
- ✅ ADX-based regime classification
- ✅ Unfilled FVG tracking
- ✅ Confluence scoring (0-100 scale)

### 3. AI Validation (ai_decision.py)
**Self-Evolving Intelligence:**
- 11-dimensional feature extraction
- Adaptive confidence thresholds (75%-95%)
- Performance-based learning
- RSI divergence detection
- Regime adjustments
- Win rate tracking & auto-adjustment

### 4. Risk Calculation (risk_engine.py)
**Professional Position Management:**
- Multi-target system (1.5R / 2.5R / 4R)
- SMC-aligned stop placement
- Structure-aligned targets
- ATR-based dynamic sizing
- Fixed 1% risk per trade
- R-multiple performance tracking

### 5. Signal Generation (brain.py)
**Triple-Gate System:**
1. ✅ Confluence Score > 60%
2. ✅ AI Confidence > 85%
3. ✅ Risk:Reward > 2.0

Only when ALL three gates pass → Advisory signal generated

## 📈 Performance Metrics

### AI Engine Tracks:
- Overall win rate
- Recent win rate (last 20 trades)
- Average R-multiple
- Profit factor
- Adaptive threshold adjustments

### Risk Engine Tracks:
- Total P&L
- Win rate by setup type
- Average win vs average loss
- Expectancy
- R-multiple distribution

## 🔄 Continuous Learning Loop

```
Signal Generated → Manual Execution → Outcome Logged → AI Learns
     ↑                                                      │
     └──────────────── Threshold Adjusted ─────────────────┘
```

- Win rate < 50%: Raises confidence threshold (+2%)
- Win rate > 70%: Lowers confidence threshold (-1%)

## 🛡️ Safety Features

1. **One Live Position Rule**: Hardware-enforced
2. **Public API Only**: No exchange keys = No execution risk
3. **Advisory Mode**: All signals require manual confirmation
4. **Multi-Target Exits**: Reduces emotional decision-making
5. **Adaptive Thresholds**: System becomes more conservative if losing

## 🚀 Usage

### Start the Brain:
```python
from backend.brain import titan_brain
import asyncio

asyncio.run(titan_brain.run_247())
```

### Monitor Performance:
```python
from backend.ai_decision import ai_engine
from backend.risk_engine import risk_engine

print(ai_engine.get_performance_report())
print(risk_engine.get_performance_metrics())
```

## 📝 Key Concepts

### Smart Money Concepts (SMC)
- **Order Blocks**: Last opposite candle before strong move
- **Liquidity Sweeps**: Stop hunts before reversals
- **BOS**: Break of Structure (trend continuation)
- **CHoCH**: Change of Character (trend reversal)
- **FVG**: Fair Value Gaps (price inefficiencies)

### Risk Management
- **R-Multiple**: Profit/loss measured in units of initial risk
- **Fractional Kelly**: Conservative position sizing
- **Multi-Target**: Scaling out at multiple levels
- **Structure-Aligned**: Stops/targets at SMC levels

## 🔧 Configuration

Edit these values in the respective files:

**brain.py:**
- `analysis_interval`: Scan frequency (default: 60s)
- `monitored_symbols`: Coins to track

**ai_decision.py:**
- `min_confidence`: Starting threshold (default: 0.85)
- `feature_weights`: Importance of each feature

**risk_engine.py:**
- `risk_per_trade_pct`: Risk per trade (default: 0.01 = 1%)
- `tp1_rr`, `tp2_rr`, `tp3_rr`: Target ratios

## 📚 Research Foundation

This system integrates concepts from:
- ICT (Inner Circle Trader) methodology
- Institutional order flow analysis
- Professional risk management frameworks
- Machine learning feature engineering
- Fractional Kelly Criterion
- Multi-timeframe confluence analysis

---

**Built for:** Manual execution with institutional-grade analysis
**Risk Level:** Advisory only - you control all execution
**Learning:** Continuously improves from your trading outcomes
