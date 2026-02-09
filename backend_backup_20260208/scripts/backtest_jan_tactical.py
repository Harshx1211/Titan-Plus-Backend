import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_provider import DataProvider
from brain_engine import BrainEngine
from skirmisher_v2 import SkirmisherV2, SkirmisherConfig
from pattern_engine import PatternEngine
from models import Regime

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_tactical_backtest():
    print("STARTING TACTICAL SCALPER AUDIT (HIGH FREQUENCY MODE)")
    print("="*60)
    
    dp = DataProvider()
    print("Authenticating with Shoonya...")
    if not dp.shoonya.login():
        print("Login Failed.")
        return
    
    brain = BrainEngine(stage=3)
    
    # [v2.5] High-Frequency Scalper Config
    tactical_config = SkirmisherConfig(
        max_scalps_strong=12,  # Boosted for everyday chances
        max_scalps_normal=8,
        min_risk_reward=1.0,    # Scalper-style 1:1 RR
        bb_touch_threshold=0.99 # Be more sensitive to band touches
    )
    sk = SkirmisherV2(config=tactical_config)
    pe = PatternEngine()
    
    # 1. Fetch Data
    start_time = datetime(2026, 1, 1, 9, 15)
    end_time = datetime(2026, 1, 31, 15, 30)
    
    df_nifty = dp.get_intraday_history("NIFTY", start_time, end_time)
    if df_nifty is None or df_nifty.empty:
        print("No Data.")
        return
    
    df_jan = df_nifty.loc[start_time:end_time]
    
    trades = []
    current_day = None
    day_pnl = 0
    total_pnl = 0
    
    # 2. Loop
    for i in range(len(df_jan)):
        current_time = df_jan.index[i]
        candle = df_jan.iloc[i]
        
        if current_day != current_time.date():
            if current_day: print(f"--- Day {current_day} End. PNL: {day_pnl:.2f} ---")
            current_day = current_time.date()
            day_pnl = 0
            sk.state["daily_scalps"] = 0 # Manual reset for backtest
            sk.state["daily_pnl"] = 0
        
        # Window for indicators
        hist_window = df_nifty.iloc[:df_nifty.index.get_indexer([current_time])[0]+1].tail(100)
        if len(hist_window) < 50: continue
        
        # TACTICAL TRIGGER: SkirmisherV2 (The Scalper)
        # Using a fixed normal regime for the scalper test
        signal = sk.check_scalp_signal(
            df=hist_window,
            df_htf=hist_window, # Simplified
            current_regime="SIDEWAYS_NORMAL",
            iv_skew=1.0
        )
        
        if signal["action"] == "EXECUTE":
            # Scalper Exit logic (30 Target / 25 Stop)
            entry = candle['close']
            tp = entry + 30 if signal["type"] == "BULLISH_SCALP" else entry - 30
            sl = entry - 25 if signal["type"] == "BULLISH_SCALP" else entry + 25
            
            pnl = 0
            outcome = "PENDING"
            future_candles = df_nifty.loc[current_time:].iloc[1:]
            day_end = current_time.replace(hour=15, minute=20)
            
            for ft, fc in future_candles.iterrows():
                if ft > day_end: break
                if signal["type"] == "BULLISH_SCALP":
                    if fc['high'] >= tp: outcome, pnl = "SUCCESS", 30; break
                    if fc['low'] <= sl: outcome, pnl = "LOSS", -25; break
                else:
                    if fc['low'] <= tp: outcome, pnl = "SUCCESS", 30; break
                    if fc['high'] >= sl: outcome, pnl = "LOSS", -25; break
            
            if outcome == "PENDING":
                eod = df_nifty.loc[:day_end].iloc[-1]['close']
                pnl = (eod - entry) if signal["type"] == "BULLISH_SCALP" else (entry - eod)
            
            day_pnl += pnl
            total_pnl += pnl
            sk.state["daily_scalps"] += 1
            trades.append({'Date': current_day, 'Time': current_time.strftime('%H:%M'), 'Type': signal["type"], 'PNL': pnl})
            print(f"   [{current_time.strftime('%H:%M')}] {signal['type']} -> {pnl:.1f}")

    print("\n" + "="*60)
    print(f"FINAL TACTICAL PNL: {total_pnl:.2f}")
    print(f"TOTAL TRADES: {len(trades)}")
    print("="*60)

if __name__ == "__main__":
    run_tactical_backtest()
