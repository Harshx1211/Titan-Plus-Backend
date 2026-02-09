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
from news_service import NewsService
from quality_filter import QualityFilter
from models import Regime

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_predator_backtest():
    print("STARTING 'PREDATOR SCALPER' JAN 2026 AUDIT (1m MTF + NEWS)")
    print("="*60)
    
    dp = DataProvider()
    print("Authenticating with Shoonya...")
    if not dp.shoonya.login():
        print("Login Failed.")
        return
    
    brain = BrainEngine(stage=3)
    ns = NewsService()
    pe = PatternEngine()
    qf = QualityFilter()  # NEW: High-conviction filter
    
    # [v2.5] Predator Config
    predator_config = SkirmisherConfig(
        predator_mode=True,
        predator_min_target=25.0, # Target 25 pts consistently
        max_scalps_strong=15,    # High frequency
        min_risk_reward=0.8      # Scalper can take 1:1 or slightly less if high accuracy
    )
    sk = SkirmisherV2(config=predator_config)
    
    # 1. Fetch 1m Data
    start_time = datetime(2026, 1, 1, 9, 15)
    end_time = datetime(2026, 1, 31, 15, 30)
    
    print("Fetching 1-minute historical data (This takes a moment)...")
    df_1m = dp.get_intraday_history("NIFTY", start_time, end_time, interval=1)
    
    if df_1m.empty:
        print("Critical: No 1m data fetched.")
        return
        
    # Aggregate 5m for 'Macro' view
    df_5m = dp.aggregate_to_tf(df_1m, "5min")
    
    trades = []
    current_day = None
    day_pnl = 0
    total_pnl = 0
    last_trade_time = None  # Cooldown tracker
    
    # 2. Main Simulation Loop (1-minute granularity)
    for i in range(len(df_1m)):
        current_time = df_1m.index[i]
        candle = df_1m.iloc[i]
        
        if current_day != current_time.date():
            if current_day:
                print(f"--- {current_day} CLOSE. Day PNL: {day_pnl:.2f} ---")
            current_day = current_time.date()
            day_pnl = 0
            sk.state["daily_scalps"] = 0 
            
            # Fetch Daily Sentiment
            sentiment = ns.get_market_sentiment()
            print(f"[{current_day}] Market News: {sentiment['headline_sample']} (Score: {sentiment['score']})")

        # Context windows
        hist_1m = df_1m.iloc[:i+1].tail(100)
        if len(hist_1m) < 50: continue
        
        # SCALPER DECISION (1m Chart)
        # Using 5m context for regime
        last_5m_idx = df_5m.index.get_indexer([current_time], method='pad')[0]
        context_5m = df_5m.iloc[:last_5m_idx+1].tail(50)
        
        signal = sk.check_scalp_signal(
            df=hist_1m,
            df_htf=context_5m,
            current_regime="SIDEWAYS_NORMAL",
            iv_skew=1.0
        )
        
        if signal["action"] == "EXECUTE" and abs(sentiment['score']) < 0.8:
            # THE PREDATOR ENTRY
            entry = candle['close']
            
            # PERFECT STRUCTURAL SL
            sl = pe.find_structural_sl(hist_1m, "BULLISH" if "BULLISH" in signal["type"] else "BEARISH")
            
            # CALCULATED DYNAMIC TARGET (New v2.6 logic)
            tp = pe.find_structural_tp(hist_1m, "BULLISH" if "BULLISH" in signal["type"] else "BEARISH")
            
            # Risk:Reward Filter
            risk_pts = abs(entry - sl)
            reward_pts = abs(tp - entry)
            rr_ratio = reward_pts / risk_pts if risk_pts > 0 else 0
            
            if rr_ratio < 1.2:
                continue
            
            # QUALITY GATE: Multi-layer confluence check (with correct RR)
            quality = qf.evaluate_trade_quality(
                signal_data={"type": signal["type"], "rr_ratio": rr_ratio},
                df_1m=hist_1m,
                df_5m=context_5m,
                news_sentiment=sentiment['score']
            )
            
            if not quality["approved"]:
                # print(f"   [{current_time.strftime('%H:%M')}] VETO: Low Quality ({quality['score']}/5.0)")
                continue
            
            # COOLDOWN: Prevent rapid-fire trades (3-min spacing)
            if last_trade_time and (current_time - last_trade_time).total_seconds() < 180:
                continue
            
            last_trade_time = current_time

            # Outcome (1m Lookahead)
            pnl = 0
            outcome = "PENDING"
            future_1m = df_1m.loc[current_time:].iloc[1:]
            day_end = current_time.replace(hour=15, minute=28)
            
            curr_sl = sl
            trail_triggered = False
            
            for ft, fc in future_1m.iterrows():
                if ft > day_end: break
                
                # Check Trailing SL Trigger (+15 pts)
                if not trail_triggered:
                    if "BULLISH" in signal["type"]:
                        if fc['high'] >= entry + 15:
                            curr_sl = entry + 2 # Lock in small profit/breakeven
                            trail_triggered = True
                    else:
                        if fc['low'] <= entry - 15:
                            curr_sl = entry - 2
                            trail_triggered = True

                if "BULLISH" in signal["type"]:
                    if fc['high'] >= tp: outcome, pnl = "SUCCESS", (tp - entry); break
                    if fc['low'] <= curr_sl: outcome, pnl = "STOP", (curr_sl - entry); break
                else:
                    if fc['low'] <= tp: outcome, pnl = "SUCCESS", (entry - tp); break
                    if fc['high'] >= curr_sl: outcome, pnl = "STOP", (entry - curr_sl); break
            
            if outcome == "PENDING":
                eod = df_1m.loc[:day_end].iloc[-1]['close']
                pnl = (eod - entry) if "BULLISH" in signal["type"] else (entry - eod)
            
            day_pnl += pnl
            total_pnl += pnl
            sk.state["daily_scalps"] += 1
            trades.append(pnl)
            
            trail_flag = " [TRAILED]" if trail_triggered else ""
            print(f"   [{current_time.strftime('%H:%M')}] {signal['type']} @ {entry:.1f} | Q:{quality['score']}/5 | SL: {curr_sl:.1f} | TP: {tp:.1f} | RR: {rr_ratio:.1f} | PNL: {pnl:.1f}{trail_flag}")

    print("\n" + "="*60)
    print(f"PREDATOR AUDIT SUMMARY")
    print(f"Total Trades: {len(trades)}")
    print(f"Win Rate: {len([p for p in trades if p > 0])/len(trades)*100:.1f}%" if trades else "0%")
    print(f"Net Points: {total_pnl:.2f}")
    print("="*60)

if __name__ == "__main__":
    run_predator_backtest()
