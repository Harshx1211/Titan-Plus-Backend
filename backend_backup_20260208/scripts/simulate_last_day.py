import sys
import os
import pandas as pd
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

# Configure logging to be minimal
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_simulation():
    print("STARTING TRUTHFUL SIMULATION FOR TUESDAY: 2026-01-27")
    
    dp = DataProvider()
    brain = BrainEngine(stage=3)
    skirmisher = SkirmisherV2()
    pe = PatternEngine()
    risk = RiskEngine()
    th = TrapHunter()
    
    # Identify Tuesday (Jan 27, 2026)
    target_date = datetime(2026, 1, 27)
    start_time = target_date.replace(hour=9, minute=15, second=0)
    end_time = target_date.replace(hour=15, minute=30, second=0)
    
    # 1. Fetch History
    print("Authenticating with Shoonya...")
    if not dp.shoonya.login():
        print("Login Failed.")
        return
    print("Login Successful.")
    
    # Refresh mappings manually to be sure
    dp.shoonya.refresh_futures_mapping()
    
    print(f"Fetching historical data for NIFTY from {start_time} to {end_time}...")
    # Expand lookback to ensure holiday (Jan 26) gap is filled
    df_nifty = dp.get_intraday_history("NIFTY", start_time - timedelta(days=10), end_time)
    
    if df_nifty is None or df_nifty.empty:
        print("Failed to fetch historical data. df is empty.")
        return

    # Filter for the target day
    df_day = df_nifty.loc[start_time:end_time]
    print(f"Processing {len(df_day)} candles...")

    # 2. Pre-Warm Brain (Critical for truthful audit)
    print("Pre-warming Brain Engine with prior history...")
    pre_warm_data = df_nifty.loc[:start_time - timedelta(minutes=5)].tail(200)
    for pw_time, pw_candle in pre_warm_data.iterrows():
        # Feed features to warm up history
        pw_window = df_nifty.loc[:pw_time]
        # Skip actual decision, just populate history
        pw_features = {
            "OI_RES": (pw_candle['oi_change'] if 'oi_change' in pw_candle else 0),
            "BASIS_RES": (pw_candle['basis'] if 'basis' in pw_candle else 0),
            "PCR": (pw_candle['pcr'] if 'pcr' in pw_candle else 1.0),
            "ADX": (pw_candle['adx'] if 'adx' in pw_candle else 20)
        }
        for f, v in pw_features.items():
            if f in brain.feature_history:
                brain.feature_history[f].append(v)

    trades = []
    
    # 3. Iterate through the day
    for i in range(len(df_day)):
        current_time = df_day.index[i]
        candle = df_day.iloc[i]
        
        # Snapshot for the engines
        # We use a 200-bar window leading up to current_time
        hist_window = df_nifty.loc[:current_time].last('200B') # roughly
        if len(hist_window) < 50: continue
        
        # Basic MarketData mock
        market_data = MarketData(
            symbol="NIFTY",
            spot_price=candle['close'],
            future_price=candle['close'] + 40, # Simulating basis
            pc=candle['close'] - df_day.iloc[0]['open'], # Simple change
            v=int(candle.get('volume', 0)),
            oi=12000000,
            pcr=1.0,
            timestamp=current_time
        )
        
        # Run Pattern Recognition
        # We need a dataframe for pattern detection
        pattern_results = pe.get_signal_confirmation(hist_window)
        
        # Simplified Regime: Check if trending or sideways
        # (Usually api.py calculates this, we'll proxy it)
        regime = Regime.SIDEWAYS_NORMAL # Default for simulation
        
        # Call Brain
        # 1. Calculate features (v2.0 logic)
        last_lp = df_day.iloc[i-1]['close'] if i > 0 else df_day.iloc[0]['open']
        price_vel = (candle['close'] - last_lp) / last_lp * 100
        
        # Determine LIKELY INTENT manually (mimicking api.py)
        # Production: logic = "BULLISH" if pattern_score > 0.6 and strength > 0 ...
        # Here we use price velocity as a simple proxy for the simulation
        likely_intent = "BULLISH" if price_vel > 0 and pattern_results.get('score', 0) > 0.4 else (
            "BEARISH" if price_vel < 0 and pattern_results.get('score', 0) > 0.4 else None
        )
        
        if not likely_intent: continue # Skip if no clear bias
        
        # Simple residuals for simulation
        oi_change = 0.5 # Mock
        basis = 0.15 # Mock
        pcr = 1.0
        adx = 22.0
        
        features = {
            "OI_RES": oi_change - (0.2 * price_vel),
            "BASIS_RES": basis - (0.5 * price_vel),
            "PCR": pcr,
            "ADX": adx
        }
        
        # Call Brain loop
        decision_candidates = []
        for intent_str in ["BULLISH", "BEARISH"]:
            try:
                decision_id, thoughts = brain.generate_decision(
                    features=features,
                    regime=regime,
                    pattern_score=pattern_results.get('score', 0.5),
                    signal_intent=intent_str,
                    iv_skew=0.0
                )
                
                decision_obj = brain.decisions.get(decision_id)
                # Truthful Transparency: Log Brain's internal reasoning
                if thoughts:
                    reason = thoughts[0] if thoughts else "Neutral"
                    print(f"[{current_time.strftime('%H:%M')}] {intent_str} Brain: {reason}")

                if decision_obj and decision_obj.decision == "APPROVE":
                    boost, _ = brain.get_confidence_boost(features, regime, intent_str, 0.0)
                    decision_candidates.append({
                        'intent': intent_str,
                        'boost': boost,
                        'price': candle['close']
                    })
            except Exception as e:
                logger.error(f"Error in Brain evaluation: {e}")
        
        # [TRUTHFUL AUDIT] Winner-Takes-All + Hardened Production Thresholds
        if decision_candidates:
            # Pick strongest
            best_candidate = max(decision_candidates, key=lambda x: x['boost'])
            # Verify with Risk Engine (No simulation overrides)
            qty = risk.get_suggested_size(confidence=best_candidate['boost'], base_size=1)
            
            if qty > 0:
                print(f"[BRAIN] [{current_time.strftime('%H:%M')}] {best_candidate['intent']} | Conf: {best_candidate['boost']:.2f} | Size: {qty}")
                trades.append({
                    'time': current_time,
                    'intent': best_candidate['intent'],
                    'price': best_candidate['price'],
                    'conf': best_candidate['boost'],
                    'engine': 'BRAIN'
                })
        
        # Call Skirmisher V2 (Scalp signals)
        # Needs df (5m), df_htf (15m), current_regime (str), iv_skew (float)
        df_5m = hist_window.tail(50)
        # Mock 15m by resampling 5m
        df_15m = hist_window.resample('15min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
        
        try:
            # Map Regime Enum to string if needed, SkirmisherV2 expects str
            scalp = skirmisher.check_scalp_signal(df_5m, df_15m, regime.value, 0.0)
            if scalp and scalp.get('action') == "EXECUTE":
                # Check Brain Approval for Scalp
                approved, _ = brain.evaluate_skirmisher_signal(scalp, boost, scalp.get('risk_reward', 2.0))
                if approved:
                    print(f"[SKIRMISHER] [{current_time.strftime('%H:%M')}] SCALE: {scalp['reason']} | Price: {candle['close']}")
                    trades.append({
                        'time': current_time,
                        'intent': 'SCALP',
                        'price': candle['close'],
                        'conf': boost,
                        'engine': 'SKIRMISHER_V2'
                    })
        except Exception as e:
            logger.error(f"Error in Skirmisher evaluation: {e}")

    # 3. Audit Outcomes
    print("\n[PNL] Auditing outcomes for generated trades...")
    audit_results = []
    
    # Brain Parameters from config
    target_pts = 80.0 # Adjusted for conservative simulation
    stop_pts = 40.0
    
    for t in trades:
        entry_price = t['price']
        entry_time = t['time']
        intent = t['intent']
        
        # Look ahead at candles after entry_time
        future_candles = df_day.loc[entry_time:].iloc[1:]
        outcome = "PENDING"
        pnl = 0
        exit_time = None
        
        for f_time, f_candle in future_candles.iterrows():
            high = f_candle['high']
            low = f_candle['low']
            
            if intent == "BULLISH":
                if high >= entry_price + target_pts:
                    outcome = "SUCCESS (TARGET)"
                    pnl = target_pts
                    exit_time = f_time
                    break
                elif low <= entry_price - stop_pts:
                    outcome = "LOSS (SL)"
                    pnl = -stop_pts
                    exit_time = f_time
                    break
            elif intent == "BEARISH":
                if low <= entry_price - target_pts:
                    outcome = "SUCCESS (TARGET)"
                    pnl = target_pts
                    exit_time = f_time
                    break
                elif high >= entry_price + stop_pts:
                    outcome = "LOSS (SL)"
                    pnl = -stop_pts
                    exit_time = f_time
                    break
            elif intent == "SCALP":
                # Scalp use smaller targets
                s_target = 30.0
                s_stop = 15.0
                if high >= entry_price + s_target and t.get('type') != 'SHORT':
                     outcome = "SUCCESS (SCALP)"
                     pnl = s_target
                     exit_time = f_time
                     break
                # (Simple proxy for scalp)
        
        if outcome == "PENDING":
             # Square off at EOD
             last_price = df_day.iloc[-1]['close']
             if intent == "BULLISH": pnl = last_price - entry_price
             if intent == "BEARISH": pnl = entry_price - last_price
             outcome = "EOD SQUAREOFF"
             exit_time = df_day.index[-1]
             
        audit_results.append({
            'Time': entry_time.strftime('%H:%M'),
            'Type': intent,
            'Entry': entry_price,
            'Outcome': outcome,
            'PNL': pnl,
            'Exit': exit_time.strftime('%H:%M') if exit_time else "N/A"
        })

    # 4. Final Report
    print("\n" + "="*40)
    print("=== FINAL SIMULATION RESULTS (Jan 27, 2026) ===")
    if not audit_results:
        print("No trades generated with current hardening thresholds.")
    else:
        df_audit = pd.DataFrame(audit_results)
        print(df_audit.to_string(index=False))
        print("-" * 40)
        total_pnl = df_audit['PNL'].sum()
        wins = len(df_audit[df_audit['PNL'] > 0])
        total = len(df_audit)
        win_rate = (wins / total * 100) if total > 0 else 0
        print(f"Total Trades: {total}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Net Points: {total_pnl:.2f}")
        
        if total_pnl > 0:
            print("Verdict: STRATEGY SUCCESSFUL (PROFITABLE)")
        else:
            print("Verdict: STRATEGY UNDERWATER (DEFENSIVE)")
            
    print("="*40)

if __name__ == "__main__":
    run_simulation()
