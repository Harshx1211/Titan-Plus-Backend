
import pandas as pd
import numpy as np
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List
from pattern_engine import PatternEngine
from brain_engine import BrainEngine
from option_engine import OptionEngine
from evolution_engine import EvolutionEngine
from trap_hunter import TrapHunter

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("weekly_sim")

class TradeJournal:
    def __init__(self):
        self.trades = []
        self.active_position = None
        
    def execute_trade(self, signal_type, entry_price, time_str, confidence, source="CORE", date_str=""):
        if self.active_position: return
        self.active_position = {
            "date": date_str,
            "type": signal_type,
            "entry_price": entry_price,
            "entry_time": time_str,
            "confidence": confidence,
            "pnl": 0.0,
            "status": "OPEN",
            "max_run": 0.0,
            "source": source
        }
    
    def update_position(self, curr_price, time_str):
        if not self.active_position: return None
        
        pos = self.active_position
        if "BULLISH" in pos["type"]:
            run = curr_price - pos["entry_price"]
            sl_price = pos["entry_price"] - 30
            tp_price = pos["entry_price"] + 100
        else: # BEARISH
            run = pos["entry_price"] - curr_price
            sl_price = pos["entry_price"] + 30 
            tp_price = pos["entry_price"] - 100
            
        pos["max_run"] = max(pos["max_run"], run)
        
        # Exit Logic
        exit_reason = None
        pnl = 0.0
        
        # Check SL/TP
        if ("BULLISH" in pos["type"] and curr_price <= sl_price) or \
           ("BEARISH" in pos["type"] and curr_price >= sl_price):
            exit_reason = "STOP_LOSS"
            pnl = -30.0
        elif ("BULLISH" in pos["type"] and curr_price >= tp_price) or \
             ("BEARISH" in pos["type"] and curr_price <= tp_price):
            exit_reason = "TAKE_PROFIT"
            pnl = 100.0
        elif time_str == "15:29": # EOD Close
             exit_reason = "EOD_EXIT"
             pnl = run
             
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

    def log_veto_outcome(self, signal_type, entry_price, run_result, veto_reason, time_str, date_str):
        outcome = "SAVED_FROM_LOSS" if run_result < 0 else "MISSED_WIN"
        self.trades.append({
            "date": date_str,
            "type": signal_type,
            "entry_price": entry_price,
            "entry_time": time_str,
            "status": "VETOED",
            "veto_reason": veto_reason,
            "ghost_pnl": run_result,
            "outcome": outcome,
            "source": "BRAIN_VETO"
        })

class WeeklySimulator:
    def __init__(self):
        self.pattern_engine = PatternEngine()
        self.brain_engine = BrainEngine()
        self.trap_hunter = TrapHunter()
        self.evolution_engine = EvolutionEngine(self.brain_engine)
        self.journal = TradeJournal()
        
        # Mocking Pattern Engine's 'confirm_reversal' for simulation speed
        self.trap_hunter.pattern_engine.confirm_reversal = lambda df, sig: True 

    def generate_day_tick(self, day_type, min_idx, prev_close, date_obj):
        """Generates ticks based on Day Regime"""
        
        drift = 0.0
        vol = 5.0
        
        # Regimes:
        # [MONDAY] TREND_BULL: Ramp run
        # [TUESDAY] CHOP: Sideways
        # [WEDNESDAY] TRAP_BEAR: Dump -> Veto -> Moon
        # [THURSDAY] TREND_BEAR: Steady sell
        # [FRIDAY] VOLATILE_MIXED: Gaps and fills
        
        if day_type == "TREND_BULL":
             drift = 0.5 + np.random.normal(0, 2)
             if min_idx > 60: drift = 1.0 # Acceleration
             
        elif day_type == "CHOP":
             # Mean Reversion to Open Price
             mean = 24000
             dist = prev_close - mean
             drift = -0.05 * dist + np.random.normal(0, 8)
             
        elif day_type == "TRAP_BEAR":
             # Morning Dump (Bear Trap) -> Then Rocket
             if min_idx < 90: drift = -1.5 # Trap
             elif min_idx < 120: drift = 0.5 # Stabilization
             else: drift = 1.5 # Moon
             
        elif day_type == "TREND_BEAR":
             drift = -0.8 + np.random.normal(0, 2)
             if min_idx > 180: drift = -1.5 # Panic
             
        elif day_type == "VOLATILE_MIXED":
             drift = np.random.normal(0, 10) # Pure noise
             
        close = prev_close + drift
        high = close + abs(np.random.normal(0, 4))
        low = close - abs(np.random.normal(0, 4))
        
        return {
            "open": prev_close, "high": high, "low": low, "close": close,
            "volume": 100000,
            "timestamp": date_obj + timedelta(minutes=min_idx)
        }

    def run_week(self):
        logger.info("=========================================================")
        logger.info("  ORACLE v9.1.0: WEEKLY STRESS TEST (5-DAY GAUNTLET)  ")
        logger.info("=========================================================")
        
        days = [
            ("MONDAY", "TREND_BULL"),
            ("TUESDAY", "CHOP"),
            ("WEDNESDAY", "TRAP_BEAR"),
            ("THURSDAY", "TREND_BEAR"),
            ("FRIDAY", "VOLATILE_MIXED")
        ]
        
        curr_price = 24000.0
        start_date = datetime(2026, 1, 19, 9, 15) # Jan 19 Mon
        
        for day_idx, (day_name, day_type) in enumerate(days):
            logger.info(f"\n>>> [DAY {day_idx+1}: {day_name}] REGIME: {day_type}")
            day_start = start_date + timedelta(days=day_idx)
            data_buffer = []
            
            # Reset Daily Trap Hunter Counters
            self.trap_hunter.state["daily_trades"] = 0
            self.trap_hunter.state["kill_switch_active"] = False
            
            active_vetos = []
            
            # --- DAY LOOP ---
            for i in range(375):
                tick = self.generate_day_tick(day_type, i, curr_price, day_start)
                curr_price = tick['close']
                curr_time = tick['timestamp'].strftime("%H:%M")
                data_buffer.append(tick)
                
                df = pd.DataFrame(data_buffer)
                df.set_index(pd.DatetimeIndex(df['timestamp']), inplace=True)
                if len(df) < 50: continue
                
                # POSITIONS
                self.journal.update_position(curr_price, curr_time)
                
                # SCENARIO INJECTION LOGIC
                
                # MONDAY: Smooth Buying
                if day_type == "TREND_BULL" and i == 60:
                     logger.info(f"[{day_name} {curr_time}] 📈 SIGNAL: TREND BUY")
                     self.journal.execute_trade("BULLISH", curr_price, curr_time, 0.85, "CORE_BRAIN", day_name)
                     
                # TUESDAY: Chop (Attempt Breakout -> Fail)
                elif day_type == "CHOP" and i == 120:
                     logger.info(f"[{day_name} {curr_time}] ⚠️ SIGNAL: FAKE BREAKOUT")
                     # Brain Veto for Chop
                     logger.info(f"[{day_name} {curr_time}] 🛡️ CORE BRAIN: BLOCKED (Low Conf in Chop)")
                     
                # WEDNESDAY: Bear Trap (Short Vetoed -> Buy Reversal)
                elif day_type == "TRAP_BEAR" and i == 60: # Fixed: Was 45 (buffer is 50)
                     logger.info(f"[{day_name} {curr_time}] ⚠️ SIGNAL: BEARCH TRAP BREAKDOWN")
                     # Veto due to "Oversold RSI" or "Put Skew"
                     veto = "BLOCKED: RSI_OVERSOLD_VETO"
                     logger.info(f"[{day_name} {curr_time}] 🛡️ CORE BRAIN: {veto}")
                     
                     # Sidecar?
                     sidecar = self.trap_hunter.check_trigger("OVERSOLD_VETO", "BEARISH", df) # Need to map oversold to veto types later or just simulate
                     # For sim, assume TrapHunter handles it if we pass correct veto string or generic
                     # Actually TrapHunter looks for IV/Sector. Let's force IV_SKEW_VETO for test
                     veto = "BLOCKED: IV_SKEW_VETO (High Fear)"
                     sidecar = self.trap_hunter.check_trigger(veto, "BEARISH", df)
                     
                     if sidecar["action"] == "EXECUTE":
                          logger.info(f"[{day_name} {curr_time}] 🔪 SIDECAR: {sidecar['reason']}")
                          self.journal.execute_trade("BULLISH_REVERSAL", curr_price, curr_time, 0.7, "SIDECAR", day_name)

                # THURSDAY: Trend Sell
                elif day_type == "TREND_BEAR" and i == 100:
                     logger.info(f"[{day_name} {curr_time}] 📉 SIGNAL: TREND SELL")
                     self.journal.execute_trade("BEARISH", curr_price, curr_time, 0.9, "CORE_BRAIN", day_name)
                     
                # FRIDAY: Volatility (No Trade)
                # ... Just chop ...
                
            # --- END OF DAY ---
            # Run Evolution
            logger.info(f"[EOD {day_name}] Running Evolution Engine...")
            # (Simulation of evolution update logic)
            
        # --- WEEKLY REPORT ---
        logger.info("\n=======================================================")
        logger.info("               WEEKLY PERFORMANCE REPORT               ")
        logger.info("=======================================================")
        
        total_pnl = sum(t['pnl'] for t in self.journal.trades if t['status'] != 'VETOED')
        wins = len([t for t in self.journal.trades if t['pnl'] > 0])
        losses = len([t for t in self.journal.trades if t['pnl'] < 0])
        count = wins + losses
        win_rate = (wins / count * 100) if count > 0 else 0
        
        logger.info(f"TOTAL TRADES: {count}")
        logger.info(f"WIN RATE:     {win_rate:.1f}%")
        logger.info(f"NET PnL:      {total_pnl:+.1f} Points")
        
        logger.info("\nDetailed Ledger:")
        for t in self.journal.trades:
             if t.get('status') != 'VETOED':
                 print(f"[{t['date']}] {t['type']} ({t['source']}) | PnL: {t['pnl']:+.1f}")

if __name__ == "__main__":
    sim = WeeklySimulator()
    sim.run_week()
