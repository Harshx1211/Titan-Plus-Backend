# HELIOS v15.3.7 - Quick Start Guide
🎯 Goal: Enforce 3 safety layers (Position, Risk, Data Health) in 30 minutes.

### ⚡ Quick Steps
1. **Verify Files**: Ensure `critical_safety_systems.py` is in the root.
2. **Setup Env**: `export PAPER_TRADING_MODE=True`
3. **Run Tests**: `python test_safety_systems.py`
4. **Deploy**: Follow `api_integration_patch.py` for exact code injection points.

### 🛡️ What you get:
- **Circuit Breaker**: Stops all trading if 5% daily loss hit.
- **Stale Protection**: Blocks trades if data is >5s old.
- **Position Tracking**: Real-time PnL on every open signal.
