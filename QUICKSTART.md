# Titan Crypto Brain V3 - Quick Start Guide

## 🚀 Installation

### 1. Install Dependencies
```bash
cd f:\FnO
pip install -r backend\requirements.txt
```

### 2. Configure Environment
Create/verify `.env` file in the root directory:
```env
SUPABASE_URL="https://eiafuzgqbtfstaparhpe.supabase.co"
SUPABASE_KEY="your_supabase_anon_key_here"
```

### 3. Verify Database
Ensure Supabase tables exist:
- `trades` - Position tracking
- `brain_logs` - AI learning data
- `market_state` - Real-time market snapshots

## 🎯 Running the System

### Start the Brain
```bash
python start_brain.py
```

### What You'll See:
```
🧠 TITAN CRYPTO BRAIN V3 - INSTITUTIONAL INTELLIGENCE CORE
📊 Monitoring: BTC/USDT, ETH/USDT, SOL/USDT
🤖 AI Model: 3.0.0-Evolution
⚡ Analysis Interval: 60s
```

### Signal Generation:
When all criteria are met (Confluence > 60%, AI > 85%, R:R > 2.0):
```
✨ ADVISORY SIGNAL GENERATED ✨
📍 Position ID: BTC/USDT_LONG_1739512345
🎯 Entry: $45,000 | SL: $44,500
   Targets: $45,750 / $46,250 / $47,000
   R:R = 1:2.5
```

## 📊 Manual Execution Workflow

1. **Wait for Signal**: Brain scans 24/7
2. **Review Signal**: Check confluence score, AI confidence, R:R
3. **Execute Manually**: Place order on your broker
4. **Monitor Targets**: Brain tracks position and suggests exits
5. **Log Outcome**: System learns from result

## 🔧 Configuration

### Adjust Risk (risk_engine.py):
```python
self.risk_per_trade_pct = 0.01  # 1% risk
self.tp1_rr = 1.5  # First target
self.tp2_rr = 2.5  # Second target
self.tp3_rr = 4.0  # Runner
```

### Adjust AI Threshold (ai_decision.py):
```python
self.min_confidence = 0.85  # 85% minimum
```

### Change Symbols (brain.py):
```python
self.monitored_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
```

## 📈 Performance Monitoring

### Check AI Stats:
```python
from backend.ai_decision import ai_engine
print(ai_engine.get_performance_report())
```

### Check Risk Stats:
```python
from backend.risk_engine import risk_engine
print(risk_engine.get_performance_metrics())
```

## 🛡️ Safety Notes

- ✅ **Public API Only**: No exchange keys required
- ✅ **No Auto-Execution**: All trades are advisory
- ✅ **One Position Rule**: Enforced by risk engine
- ✅ **Adaptive Learning**: System adjusts based on performance

## 🐛 Troubleshooting

### "Database connection failed"
- Check `.env` file has correct Supabase credentials
- Verify Supabase project is active

### "Insufficient data"
- Check internet connection
- Binance API may be rate-limited (wait 1 minute)

### "No signals generated"
- Normal! System is very selective
- Requires confluence > 60% + AI > 85% + R:R > 2.0
- May take hours to find perfect setup

## 📚 Understanding the Output

### Scanning Mode:
```
🔍 BTC/USDT: Confluence 45% | Regime: RANGING
```
No signal - confluence too low

### Filtered Mode:
```
❌ AI ENGINE: ETH/USDT LONG REJECTED | Confidence: 78% < 85%
```
Setup found but AI confidence insufficient

### Signal Generated:
```
✅ AI ENGINE: SOL/USDT LONG VALIDATED | Confidence: 91%
🎯 RISK ENGINE: Position opened - SOL/USDT LONG
```
All gates passed - ready for manual execution!

## 🎓 Next Steps

1. **Run for 24-48 hours** to see signal generation
2. **Paper trade first** to validate strategy
3. **Review AI performance** after 10+ signals
4. **Adjust thresholds** based on your risk tolerance

---

**Remember**: This is an advisory system. You have full control over execution!
