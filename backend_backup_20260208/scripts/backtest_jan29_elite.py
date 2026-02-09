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

def run_single_day_elite():
    print("ELITE SCALPER - JAN 29, 2026 AUDIT")
    print("="*60)
    
    dp = DataProvider()
    print("Authenticating with Shoonya...")
    if not dp.shoonya.login():
        print("Login Failed.")
        return
    
    brain = BrainEngine(stage=3)
    ns = NewsService()
    pe = PatternEngine()
    qf = QualityFilter()
    qf.min_confluence_score = 1.8  # Lower for demo (normally 2.2)
    
    # Predator Config
    predator_config = SkirmisherConfig(
        predator_mode=True,
        predator_min_target=25.0,
        max_scalps_strong=15,
        min_risk_reward=0.8
    )
    sk = SkirmisherV2(config=predator_config)
    
    # Fetch 5m Data for Jan 29 (More reliable than 1m for backtesting)
    start_time = datetime(2026, 1, 29, 9, 15)
    end_time = datetime(2026, 1, 29, 15, 30)
    
    print(f"Fetching 5-minute data for {start_time.date()}...")
    df_5m = dp.get_intraday_history("NIFTY", start_time, end_time, interval=5)
    
    if df_5m.empty:
        print("Critical: No data available.")
        return
    
    print(f"Data fetched: {len(df_5m)} candles")
    
    # Use 5m as primary, no need for separate aggregation
    df_1m = df_5m  # For compatibility with existing code
    
    trades = []
    day_pnl = 0
    last_trade_time = None
    
    # Get daily sentiment
    sentiment = ns.get_market_sentiment()
    print(f"Market Sentiment: {sentiment['headline_sample']} (Score: {sentiment['score']})")
    print()
    
    # Main Loop
    for i in range(len(df_1m)):
        current_time = df_1m.index[i]
        candle = df_1m.iloc[i]
        
        # Skip first 15 mins and last 30 mins (choppy periods)
        hour, minute = current_time.hour, current_time.minute
        if (hour == 9 and minute < 30) or (hour == 15 and minute >= 0):
            continue
        
        # Context windows
        hist_1m = df_1m.iloc[:i+1].tail(100)
        if len(hist_1m) < 50:
            continue
        
        # 5m context
        last_5m_idx = df_5m.index.get_indexer([current_time], method='pad')[0]
        context_5m = df_5m.iloc[:last_5m_idx+1].tail(50) if last_5m_idx >= 0 else df_5m.tail(50)
        
        # Scalper Signal
        signal = sk.check_scalp_signal(
            df=hist_1m,
            df_htf=context_5m,
            current_regime="SIDEWAYS_NORMAL",
            iv_skew=1.0
        )
        
        if signal["action"] == "EXECUTE" and abs(sentiment['score']) < 0.8:
            # Entry & SL
            entry = candle['close']
            sl = pe.find_structural_sl(hist_1m, "BULLISH" if "BULLISH" in signal["type"] else "BEARISH")
            tp = pe.find_structural_tp(hist_1m, "BULLISH" if "BULLISH" in signal["type"] else "BEARISH")
            
            # R:R Filter
            risk_pts = abs(entry - sl)
            reward_pts = abs(tp - entry)
            rr_ratio = reward_pts / risk_pts if risk_pts > 0 else 0
            
            if rr_ratio < 1.2:
                continue
            
            # QUALITY GATE
            quality = qf.evaluate_trade_quality(
                signal_data={"type": signal["type"], "rr_ratio": rr_ratio},
                df_1m=hist_1m,
                df_5m=context_5m,
                news_sentiment=sentiment['score']
            )
            
            if not quality["approved"]:
                print(f"   [{current_time.strftime('%H:%M')}] VETO: Quality {quality['score']:.1f}/5.0 - {', '.join(quality['reasons'][:3])}")
                continue
            
            # Cooldown
            if last_trade_time and (current_time - last_trade_time).total_seconds() < 180:
                continue
            
            last_trade_time = current_time
            
            # Simulate Outcome
            pnl = 0
            outcome = "PENDING"
            future_1m = df_1m.loc[current_time:].iloc[1:]
            day_end = current_time.replace(hour=15, minute=28)
            
            curr_sl = sl
            trail_triggered = False
            
            for ft, fc in future_1m.iterrows():
                if ft > day_end:
                    break
                
                # Trailing SL
                if not trail_triggered:
                    if "BULLISH" in signal["type"]:
                        if fc['high'] >= entry + 15:
                            curr_sl = entry + 2
                            trail_triggered = True
                    else:
                        if fc['low'] <= entry - 15:
                            curr_sl = entry - 2
                            trail_triggered = True
                
                # Check TP/SL
                if "BULLISH" in signal["type"]:
                    if fc['high'] >= tp:
                        outcome, pnl = "SUCCESS", (tp - entry)
                        break
                    if fc['low'] <= curr_sl:
                        outcome, pnl = "STOP", (curr_sl - entry)
                        break
                else:
                    if fc['low'] <= tp:
                        outcome, pnl = "SUCCESS", (entry - tp)
                        break
                    if fc['high'] >= curr_sl:
                        outcome, pnl = "STOP", (entry - curr_sl)
                        break
            
            if outcome == "PENDING":
                eod = df_1m.loc[:day_end].iloc[-1]['close']
                pnl = (eod - entry) if "BULLISH" in signal["type"] else (entry - eod)
            
            day_pnl += pnl
            trades.append(pnl)
            
            trail_flag = " [TRAILED]" if trail_triggered else ""
            print(f"✓ [{current_time.strftime('%H:%M')}] {signal['type']} @ {entry:.1f} | Q:{quality['score']}/5 | SL:{curr_sl:.1f} | TP:{tp:.1f} | RR:{rr_ratio:.1f} | PNL:{pnl:+.1f}{trail_flag}")
            print(f"   Reasons: {', '.join(quality['reasons'])}")
    
    print("\n" + "="*60)
    print(f"ELITE SCALPER SUMMARY - JAN 29, 2026")
    print(f"Total Trades: {len(trades)}")
    if trades:
        wins = [p for p in trades if p > 0]
        print(f"Win Rate: {len(wins)/len(trades)*100:.1f}%")
        print(f"Gross Points: {day_pnl:+.2f}")
        print(f"Avg Win: {np.mean(wins):.1f} pts" if wins else "Avg Win: N/A")
        losses = [p for p in trades if p < 0]
        print(f"Avg Loss: {np.mean(losses):.1f} pts" if losses else "Avg Loss: N/A")
        
        # Cost Analysis
        cost_per_trade = 55  # Brokerage + taxes
        total_cost = len(trades) * cost_per_trade
        net_pnl_inr = (day_pnl * 75) - total_cost  # Assuming ₹75 per point
        print(f"\nCost Analysis:")
        print(f"  Brokerage/Taxes: ₹{total_cost}")
        print(f"  Net P&L (after costs): ₹{net_pnl_inr:+,.0f}")
    else:
        print("No trades executed (Quality filter too strict)")
    print("="*60)

if __name__ == "__main__":
    run_single_day_elite()
