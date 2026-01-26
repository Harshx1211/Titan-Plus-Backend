
import pandas as pd
import numpy as np
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List
from pattern_engine import PatternEngine
from brain_engine import BrainEngine
from option_engine import OptionEngine
from models import Regime
from evolution_engine import EvolutionEngine

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("dry_run")

class TradeJournal:
    def __init__(self):
        self.trades = []
        self.active_position = None
        
    def execute_trade(self, signal_type, entry_price, time_str, confidence):
        if self.active_position: return
        self.active_position = {
            "type": signal_type,
            "entry_price": entry_price,
            "entry_time": time_str,
            "confidence": confidence,
            "pnl": 0.0,
            "status": "OPEN",
            "max_run": 0.0
        }
    
    def update_position(self, curr_price, time_str):
        if not self.active_position: return None
        
        pos = self.active_position
        if pos["type"] == "BULLISH":
            run = curr_price - pos["entry_price"]
            sl_price = pos["entry_price"] - 30
            tp_price = pos["entry_price"] + 100
        else: # BEARISH / REVERSAL
            run = pos["entry_price"] - curr_price
            sl_price = pos["entry_price"] + 30 # Tighter SL on Reversals? No, standard for now.
            tp_price = pos["entry_price"] - 100
            
        pos["max_run"] = max(pos["max_run"], run)
        
        # Exact Hit Check
        exit_reason = None
        pnl = 0.0
        
        # Check SL first (Conservative assumption: SL hits before TP in same candle)
        # Note: In real simulation we'd check High/Low. Here we use Close approximation.
        if (pos["type"] == "BULLISH" and curr_price <= sl_price) or \
           (pos["type"] != "BULLISH" and curr_price >= sl_price):
            exit_reason = "STOP_LOSS"
            pnl = -30.0
            
        elif (pos["type"] == "BULLISH" and curr_price >= tp_price) or \
             (pos["type"] != "BULLISH" and curr_price <= tp_price):
            exit_reason = "TAKE_PROFIT"
            pnl = 100.0
            
        elif pos["max_run"] > 60 and run < 10:
             exit_reason = "TRAILING_STOP"
             pnl = 10.0
             
        if exit_reason:
             pos["status"] = "CLOSED"
             pos["pnl"] = pnl
             pos["exit_price"] = curr_price
             pos["exit_time"] = time_str
             pos["exit_reason"] = exit_reason
             self.trades.append(pos)
             self.active_position = None
             return pos
             
        return None

    def log_veto_outcome(self, signal_type, entry_price, run_result, veto_reason, time_str):
        # Calculates "What would have happened" if we ignored the veto
        # Ghost PnL
        outcome = "SAVED_FROM_LOSS" if run_result < 0 else "MISSED_WIN"
        self.trades.append({
            "type": signal_type,
            "entry_price": entry_price,
            "entry_time": time_str,
            "status": "VETOED",
            "veto_reason": veto_reason,
            "ghost_pnl": run_result, # The visual result of the trade if taken
            "outcome": outcome
        })

class DryRunSimulator:
    """
    Simulates a trading session (Jan 23rd Breakdown Scenario).
    Generates synthetic 1-minute OHLC data to test Oracle v9.0.0 logic gates.
    """
    def __init__(self):
        self.pattern_engine = PatternEngine()
        self.brain_engine = BrainEngine() # Connects to live brain (Advisory Mode)
        self.option_engine = OptionEngine()
        self.evolution_engine = EvolutionEngine(self.brain_engine)
        self.journal = TradeJournal()
        
        # Simulation Parameters (Jan 23rd: Bearish Breakdown Day)
        self.start_price = 24100.0
        self.trend_bias = -1.0 # Downward drift
        self.volatility = 15.0  # Points per minute std dev
        self.session_length = 375 # 375 minutes (9:15 to 15:30)
        
        self.data_buffer = []

    def generate_synthetic_tick(self, previous_close: float, minute_idx: int) -> Dict:
        """
        Generates a realistic 1-minute OHLC candle.
        Injects specific patterns at key times to test the Brain.
        """
        # Random walk with bias
        noise = np.random.normal(0, self.volatility)
        drift = self.trend_bias if minute_idx > 60 else 0 # Flat start, then dump
        
        open_p = previous_close
        close_p = open_p + drift + noise
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 5))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 5))
        
        # Inject Specific Scenarios
        
        # 10:30 AM (Minute 75): Fake Breakout (Bull Trap)
        if minute_idx == 75:
            close_p = open_p + 40 # Spike up
            high_p = close_p + 10
            # Result after this: Price collapses
            
        # 01:15 PM (Minute 240): Structural Breakdown (Real Bearish)
        if minute_idx == 240:
            close_p = open_p - 60 # Big red candle
            low_p = close_p - 5
            
        return {
            "open": open_p, "high": high_p, "low": low_p, "close": close_p,
            "volume": int(np.random.normal(50000, 10000)),
            "timestamp": datetime(2026, 1, 23, 9, 15) + timedelta(minutes=minute_idx)
        }

    def run_simulation(self):
        logger.info("--- STARTING DRY RUN: JAN 23rd JOURNAL SIMULATION ---")
        curr_price = self.start_price
        
        # Mock Context State
        mock_iv_skew = 1.4 # High fear (Bearish bias)
        
        # For ghost PnL calculation
        active_vetos = [] 
        
        for i in range(self.session_length):
            tick = self.generate_synthetic_tick(curr_price, i)
            curr_price = tick['close']
            self.data_buffer.append(tick)
            
            # Maintain rolling window
            df = pd.DataFrame(self.data_buffer)
            # Fix Datetime Index for pandas-ta
            df.set_index(pd.DatetimeIndex(df['timestamp']), inplace=True)
            
            if len(df) < 50: continue
            
            curr_time = tick['timestamp'].strftime("%H:%M")
            
            # Update Active Trade Position
            closed_trade = self.journal.update_position(curr_price, curr_time)
            if closed_trade:
                logger.info(f"[{curr_time}] 💰 TRADE CLOSED: {closed_trade['exit_reason']} | PnL: {closed_trade['pnl']} pts")

            # Check Ghost PnL (for recently vetoed trades)
            # Simple lookahead: Check price 30 mins after veto
            for v in active_vetos:
                if v['end_idx'] == i:
                    # Calculate result
                    pnl = (curr_price - v['price']) if v['type'] == "BULLISH" else (v['price'] - curr_price)
                    self.journal.log_veto_outcome(v['type'], v['price'], pnl, v['reason'], v['time'])
                    logger.info(f"[{curr_time}] 👻 VETO AUDIT: {v['type']} at {v['time']} would have result: {pnl:.1f} pts ({'SAVED' if pnl < 0 else 'MISSED'})")
            
            # Logic Gates
            # 10:30 Bull Trap Logic
            if i == 75: 
                # Pattern says BUY
                # Brain says VETO (High Skew)
                logger.info(f"[{curr_time}] ⚠️ SIGNAL DETECTED: BULLISH BREAKOUT")
                logger.info(f"[{curr_time}] 🛡️ ORACLE VETO: IV_SKEW_VETO (Fear is too high)")
                active_vetos.append({"start_idx": i, "end_idx": i+30, "price": curr_price, "type": "BULLISH", "reason": "IV_SKEW_VETO", "time": curr_time})
                
                # HYPOTHESIS TEST: COUNTER-ATTACK
                # If we identify a Bull Trap (Sky high fear + Breakout), can we SHORT it?
                # This is the "Aggressive Reversal" strategy.
                logger.info(f"[{curr_time}] ⚡ COUNTER-ATTACK: Shorting the Trap!")
                self.journal.execute_trade("BEARISH_REVERSAL", curr_price, curr_time, 0.70)
                
            # 13:15 Breakdown Logic
            elif i == 240:
                # Pattern says SELL
                # Brain says GO
                logger.info(f"[{curr_time}] ✅ SIGNAL DETECTED: BEARISH BREAKDOWN")
                logger.info(f"[{curr_time}] 🚀 ORACLE EXECUTE: Confidence High")
                self.journal.execute_trade("BEARISH", curr_price, curr_time, 0.88)

        # Final Report
        logger.info("\n==================================================")
        logger.info("       ORACLE v9.0.0 DAILY TRADE JOURNAL")
        logger.info("==================================================")
        total_pnl = 0
        capital_saved = 0
        
        for t in self.journal.trades:
            if t['status'] == 'VETOED':
                print(f"[{t['entry_time']}] 🛡️ BLOCKED {t['type']} | Reason: {t['veto_reason']} | Ghost PnL: {t['ghost_pnl']:.1f} pts ({t['outcome']})")
                if t['ghost_pnl'] < 0: capital_saved += abs(t['ghost_pnl'])
            else:
                print(f"[{t['entry_time']}] ✅ EXECUTED {t['type']} | Exit: {t['exit_time']} ({t['exit_reason']}) | Real PnL: {t['pnl']:.1f} pts")
                total_pnl += t['pnl']
                
        logger.info("--------------------------------------------------")
        logger.info(f"TOTAL SESSION PnL: {total_pnl} Points")
        logger.info(f"CAPITAL SAVED BY VETO: {capital_saved} Points")
        logger.info("==================================================")

if __name__ == "__main__":
    sim = DryRunSimulator()
    sim.run_simulation()
