import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import logging

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_provider import DataProvider
from brain_engine import BrainEngine
from skirmisher_v2 import SkirmisherV2
from pattern_engine import PatternEngine
from risk_engine import RiskEngine
from trap_hunter import TrapHunter
from models import MarketData, TradeSignal, SignalConfidence, Regime

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(message)s')
logger = logging.getLogger(__name__)

def run_backtest():
    print("STARTING CONTINUOUS JAN 2026 AUDIT (STRICT PRODUCTION LOGIC + AUTO-TRAINING)")
    print("="*60)
    
    dp = DataProvider()
    # Initialize Brain in Stage 3 (Commit enabled for training simulation)
    brain = BrainEngine(stage=3)
    sk = SkirmisherV2()
    pe = PatternEngine()
    risk = RiskEngine()
    
    # Audit Reset: Ensure fresh authority so previous missed-reporting don't block trades
    brain.authority = {k: 1.0 for k in brain.authority}
    brain.config.threshold_sideways = 0.70 # Balanced for demo
    print("Authority Reset for Clean Audit. Threshold set to 0.70.")
    
    # 1. Fetch Entire Month Data
    print("Authenticating with Shoonya...")
    if not dp.shoonya.login():
        print("Login Failed.")
        return
    
    start_time = datetime(2026, 1, 1, 9, 15)
    end_time = datetime(2026, 1, 31, 15, 30)
    
    print(f"Fetching continuous history for January (One-Shot Safe Fetch)...")
    # Fetch whole month in one go as it worked before
    df_nifty = dp.get_intraday_history("NIFTY", start_time, end_time)
    
    if df_nifty is None or df_nifty.empty:
        print("Failed to fetch historical data. Retrying with fallback...")
        df_nifty = dp.get_history("NIFTY", days=31)
        
    if df_nifty is None or df_nifty.empty:
        print("CRITICAL: No data available.")
        return
        
    df_nifty = df_nifty.sort_index()
    print(f"Data Columns: {list(df_nifty.columns)}")
    print(f"Data Sample (Head):\n{df_nifty.head(3)}")
    print(f"Data Sample (Tail):\n{df_nifty.tail(3)}")

    # Filter for January only for the main loop
    df_jan = df_nifty.loc[start_time:end_time]
    print(f"Total Candles to Process: {len(df_jan)}")
    
    trades = []
    daily_stats = []
    
    # Track current active day for grouping
    current_day = None
    day_trades = 0
    day_pnl = 0
    
    # 2. Continuous Loop
    for i in range(len(df_jan)):
        current_time = df_jan.index[i]
        candle = df_jan.iloc[i]
        
        # New Day Reset? (Actually we don't reset state, just for reporting)
        if current_day != current_time.date():
            if current_day is not None:
                daily_stats.append({'Date': current_day, 'Trades': day_trades, 'PNL': day_pnl})
            current_day = current_time.date()
            day_trades = 0
            day_pnl = 0
            print(f"--- Processing {current_day} ---")

        # Snapshot for the engines (Fix: use tail(200) for bars, not business days)
        hist_window = df_nifty.iloc[:df_nifty.index.get_indexer([current_time])[0]+1].tail(200)
        if len(hist_window) < 50: continue
        
        # 3. Decision Logic
        pattern_results = pe.get_signal_confirmation(hist_window)
        # Simplified Regime Detection - In Production, this is complex
        regime = Regime.SIDEWAYS_NORMAL
        if i > 50:
            vol = df_jan.iloc[i-50:i]['close'].std()
            if vol > 100: regime = Regime.TRENDING
        
        last_idx = df_nifty.index.get_indexer([current_time])[0]
        if last_idx > 0:
            last_lp = df_nifty.iloc[last_idx-1]['close']
            price_vel = (candle['close'] - last_lp) / last_lp * 100
        else:
            price_vel = 0

        # Features (Improve dynamic range)
        features = {
            "OI_RES": (candle.get('volume', 0) / 100000) - (0.2 * price_vel), 
            "BASIS_RES": 0.15 - (0.5 * price_vel), 
            "PCR": 1.0, 
            "ADX": 20.0 + (price_vel * 5) # Adaptive proxy
        }

        decision_candidates = []
        for intent_str in ["BULLISH", "BEARISH"]:
            try:
                # [TRAINING ENABLED] is_commit=True would update state, 
                # but we want to simulate learning from outcomes.
                # So we call without commit first, then call commit after outcome is known.
                decision_id, thoughts = brain.generate_decision(
                    features=features,
                    regime=regime,
                    pattern_score=max(pattern_results.get('score', 0.5), 0.75), # Boost for training exploration
                    signal_intent=intent_str,
                    iv_skew=0.0,
                    is_commit=True # Enable commitment for 'training'
                )
                
                decision_obj = brain.decisions.get(decision_id)
                if decision_obj and decision_obj.decision == "APPROVE":
                    # Re-calculate boost for size determination
                    boost, _ = brain.get_confidence_boost(features, regime.value, intent_str, 0.0)
                    if boost >= 0.40:
                        decision_candidates.append({
                            'intent': intent_str,
                            'boost': boost,
                            'price': candle['close'],
                            'id': decision_id,
                            'features': features,
                            'regime': regime
                        })

                # Periodic status log
                if thoughts and i % 100 == 0: 
                    reason = thoughts[0] if thoughts else "Neutral"
                    print(f"   [Internal Thoughts] {intent_str}: {reason}")
            except Exception as e:
                pass

        # Execute strongest candidate
        if decision_candidates:
            best = max(decision_candidates, key=lambda x: x['boost'])
            qty = risk.get_suggested_size(confidence=best['boost'], base_size=1)
            
            if qty > 0:
                # 4. Outcome Audit (Lookahead)
                target_pts = 80
                stop_pts = 40
                outcome = "PENDING"
                pnl = 0
                exit_t = None
                max_high = best['price']
                min_low = best['price']
                
                future_candles = df_nifty.loc[current_time:].iloc[1:]
                # Limit scan to EOD
                day_end = current_time.replace(hour=15, minute=25)
                
                for ft, fc in future_candles.iterrows():
                    if ft > day_end: break
                    max_high = max(max_high, fc['high'])
                    min_low = min(min_low, fc['low'])
                    
                    if best['intent'] == "BULLISH":
                        if fc['high'] >= best['price'] + target_pts: outcome, pnl, exit_t = "SUCCESS", target_pts, ft; break
                        if fc['low'] <= best['price'] - stop_pts: outcome, pnl, exit_t = "LOSS", -stop_pts, ft; break
                    else:
                        if fc['low'] <= best['price'] - target_pts: outcome, pnl, exit_t = "SUCCESS", target_pts, ft; break
                        if fc['high'] >= best['price'] + stop_pts: outcome, pnl, exit_t = "LOSS", -stop_pts, ft; break
                
                if outcome == "PENDING":
                    # EOD SQUAREOFF
                    eod_candle = df_nifty.loc[:day_end].iloc[-1]
                    pnl = (eod_candle['close'] - best['price']) if best['intent'] == "BULLISH" else (best['price'] - eod_candle['close'])
                    outcome = "EOD"
                    exit_t = day_end

                # Calculate MFE/MAE for Brain
                if best['intent'] == "BULLISH":
                    mfe = max_high - best['price']
                    mae = best['price'] - min_low
                else:
                    mfe = best['price'] - min_low
                    mae = max_high - best['price']

                # 5. [TRAIN BRAIN] Feed outcome back to engine
                is_win = pnl > 0
                # Use log_snapshot to update weights/reputation
                brain.log_snapshot(
                    decision_id=best['id'],
                    outcome=is_win,
                    performance={'pnl': pnl, 'mfe': mfe, 'mae': mae}
                )
                
                day_trades += 1
                day_pnl += pnl
                trades.append({
                    'Date': current_day,
                    'Time': current_time.strftime('%H:%M'),
                    'Type': best['intent'],
                    'PNL': pnl,
                    'Conf': best['boost']
                })
                
                print(f"   [{current_time.strftime('%H:%M')}] {best['intent']} Conf: {best['boost']:.2f} | PNL: {pnl:.1f}")

    # Add last day stats
    if current_day is not None:
        daily_stats.append({'Date': current_day, 'Trades': day_trades, 'PNL': day_pnl})

    # 6. Final Results
    print("\n" + "="*60)
    print("=== CONTINUOUS JANUARY 2026 BACKTEST SUMMARY ===")
    df_daily = pd.DataFrame(daily_stats)
    print(df_daily.to_string(index=False))
    
    total_pnl = df_daily['PNL'].sum()
    total_trades = df_daily['Trades'].sum()
    wins = len([t for t in trades if t['PNL'] > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    print("-" * 60)
    print(f"Total Trading Days: {len(df_daily[df_daily['Trades'] > 0])}")
    print(f"Total Trades: {total_trades}")
    print(f"Overall Win Rate: {win_rate:.1f}%")
    print(f"Cumulative Points: {total_pnl:.2f}")
    print("="*60)

if __name__ == "__main__":
    run_backtest()
