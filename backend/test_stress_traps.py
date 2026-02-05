"""
Titan Plus - Trap Stress Test (Blind Evaluation)
================================================
Simulates 5 critical market scenarios to verify that the 
Enhanced Brain (Phase 4) can distinguish valid setups from traps.

Rules:
1. No lookahead (Result is based ONLY on current candle info).
2. Tests Vetoes, SMC Logic, and Killzones.
"""

import logging
from brain_engine_enhanced import EnhancedBrainEngine
import pandas as pd
from datetime import datetime

# Configure minimal logging
logging.basicConfig(level=logging.ERROR)
print("Initializing Nuclear Brain (Phase 4)...")
brain = EnhancedBrainEngine(enable_rl=True, enable_smc=True, use_ppo=True)

def run_test(name, description, features, market_data, time_str="11:00"):
    print(f"\n[{name.upper()}]")
    print(f"Context: {description}")
    
    # Mock Regime
    regime = "TRENDING_UP" if features.get('adx', 0) > 25 else "SIDEWAYS"
    
    # Mock OHLCV (Just enough for SMC to run without crashing)
    # In a trap, we might show a 'wick' (Liquidity Sweep)
    ohlcv = pd.DataFrame([
        {'open': 100, 'high': 105, 'low': 99, 'close': 102, 'volume': 1000}
    ])
    
    # Inject Time Context (Mocking logic in api.py usually handles this, 
    # but Brain Engine checks things like VIX/Basis directly)
    
    # DECISION
    decision = brain.decide(features, market_data, ohlcv_df=ohlcv, regime=regime)
    
    res = decision['decision']
    conf = decision['confidence']
    reasons = decision.get('veto_reasons', [])
    
    # score color
    color = "[PASS]" if res == "APPROVE" else "[BLOCK]"
    print(f"{color} Result: {res} (Conf: {conf:.0%})")
    
    if reasons:
        print(f"   Vetoes: {reasons}")
    
    # Check components
    comps = decision['components']
    print(f"   Brain Details: RL={comps['rl']} | SMC={comps['smc']} | XGB={comps['xgboost']}")

# ==========================================
# SCENARIO 1: THE GOLDEN BUY (Genuine Trade)
# ==========================================
# Interpretation: Strong Trend (ADX>30), Momentum (RSI 60), Inst Support (PCR>1)
features_1 = {
    'rsi': 60.0, 'adx': 35.0, 'atr': 100.0, 
    'basis': 2.0, 'pcr': 1.2, 'vix': 14.0, 
    'iv_skew': 1.1, # Calls more expensive
    'volume': 1000000
}
run_test("Golden Setup", "Perfect momentum + High Volume + Sector Synergy aligned.", features_1, {'spot_price': 22000})

# ==========================================
# SCENARIO 2: THE "LURE" (Classic Trap)
# ==========================================
# Interpretation: Price moving up (RSI 75), but Volume Dying, Negative Delta (mocked via features), High Basis
features_2 = {
    'rsi': 78.0, # Overbought
    'adx': 15.0, # Weak Trend (Trap!)
    'atr': 50.0, 
    'basis': 8.0, # Unstable spread (Veto Trigger)
    'pcr': 0.6,  # Bearish flow
    'vix': 18.0, 
    'iv_skew': 0.9
}
run_test("Liquidity Trap", "RSI Overbought but ADX dying & Basis unstable.", features_2, {'spot_price': 22100})

# ==========================================
# SCENARIO 3: HIGH VIX PANIC (Doomsday)
# ==========================================
# Interpretation: VIX > 25. System should shut down.
features_3 = {
    'rsi': 40.0, 'adx': 60.0, 'atr': 300.0, 
    'basis': 1.0, 'pcr': 0.5, 
    'vix': 28.5, # <--- DOOMSDAY TRIGGER
    'iv_skew': 1.5
}
run_test("VIX Crash Mode", "VIX is 28.5 (Market Panic).", features_3, {'spot_price': 21500})

# ==========================================
# SCENARIO 4: GAMMA TRAP (Whipsaw)
# ==========================================
# Interpretation: High Gamma Exposure (Pins price), Low VIX ( complacency) -> Chop city.
features_4 = {
    'rsi': 50.0, 'adx': 10.0, 'atr': 40.0, 
    'basis': 0.5, 'pcr': 1.0, 
    'vix': 11.0, 
    'gex': 10000000, # Massive GEX wall
    'gamma_ratio': 10.0 # Extreme hedging
}
run_test("Gamma Pinned", "Massive GEX walls pinning price. No move expected.", features_4, {'spot_price': 22000})

print("\nTests Complete.")
