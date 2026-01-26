
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
logger = logging.getLogger("monthly_sim")

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

class MonthlySimulator:
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
        
        if day_type == "TREND_BULL":
             drift = 0.5 + np.random.normal(0, 2)
             if min_idx > 60: drift = 1.0 # Acceleration
             
        elif day_type == "CHOP":
             mean = 24000
             dist = prev_close - mean
             drift = -0.05 * dist + np.random.normal(0, 8)
             
        elif day_type == "TRAP_BEAR":
             if min_idx < 90: drift = -1.5 # Trap
             elif min_idx < 120: drift = 0.5 # Stabilization
             else: drift = 1.5 # Moon
             
        elif day_type == "TRAP_BULL":
             if min_idx < 90: drift = 1.5 # Trap Up
             elif min_idx < 120: drift = -0.5 
             else: drift = -1.5 # Dump
             
        elif day_type == "TREND_BEAR":
             drift = -0.8 + np.random.normal(0, 2)
             if min_idx > 180: drift = -1.5 
             
        elif day_type == "VOLATILE_MIXED":
             drift = np.random.normal(0, 10) # Pure noise / Event
             
        close = prev_close + drift
        high = close + abs(np.random.normal(0, 4))
        low = close - abs(np.random.normal(0, 4))
        
        return {
            "open": prev_close, "high": high, "low": low, "close": close,
            "volume": 100000,
            "timestamp": date_obj + timedelta(minutes=min_idx)
        }

    def run_month(self):
        logger.info("=========================================================")
        logger.info("  ORACLE v9.1.0: MONTHLY STRESS TEST (20-DAY CYCLE)  ")
        logger.info("=========================================================")
        
        # 4 Weeks Regime Calendar
        days = []
        # Week 1: Trend & Chop (Easy Week)
        days.extend([("W1-MON", "TREND_BULL"), ("W1-TUE", "CHOP"), ("W1-WED", "TREND_BULL"), ("W1-THU", "CHOP"), ("W1-FRI", "VOLATILE_MIXED")])
        # Week 2: Trap Heavy (Testing Sidecar)
        days.extend([("W2-MON", "TRAP_BULL"), ("W2-TUE", "TREND_BEAR"), ("W2-WED", "TRAP_BEAR"), ("W2-THU", "TRAP_BULL"), ("W2-FRI", "CHOP")])
        # Week 3: The Death Chop (Patience Test)
        days.extend([("W3-MON", "CHOP"), ("W3-TUE", "CHOP"), ("W3-WED", "CHOP"), ("W3-THU", "TREND_BULL"), ("W3-FRI", "TREND_BEAR")])
        # Week 4: Black Swan & Event (High Risk)
        days.extend([("W4-MON", "VOLATILE_MIXED"), ("W4-TUE", "TRAP_BULL"), ("W4-WED", "TRAP_BEAR"), ("W4-THU", "TREND_BULL"), ("W4-FRI", "TREND_BEAR")])
        
        curr_price = 24000.0
        start_date = datetime(2026, 1, 1, 9, 15)
        
        for day_idx, (day_name, day_type) in enumerate(days):
            logger.info(f"\n>>> [DAY {day_idx+1}: {day_name}] REGIME: {day_type}")
            day_start = start_date + timedelta(days=day_idx)
            data_buffer = []
            
            self.trap_hunter.state["daily_trades"] = 0
            self.trap_hunter.state["kill_switch_active"] = False
            
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
                
                # SCENARIO INJECTION (After buffer fill, i > 50)
                
                # TREND DAYS
                if day_type == "TREND_BULL" and i == 60:
                     self.journal.execute_trade("BULLISH", curr_price, curr_time, 0.85, "CORE_BRAIN", day_name)
                     logger.info(f"[{day_name}] 📈 CORE BUY EXEC")
                elif day_type == "TREND_BEAR" and i == 60:
                     self.journal.execute_trade("BEARISH", curr_price, curr_time, 0.90, "CORE_BRAIN", day_name)
                     logger.info(f"[{day_name}] 📉 CORE SELL EXEC")
                     
                # CHOP DAYS (Silence)
                elif day_type == "CHOP" and i == 120:
                     # Simulate blocked signal
                     logger.info(f"[{day_name}] 🛡️ CORE BRAIN: SILENCE (Chop Blocked)")
                     
                # TRAP DAYS (Sidecar Tests)
                elif day_type == "TRAP_BULL" and i == 70:
                     # Bull Trap -> Short Reversal
                     veto = "BLOCKED: IV_SKEW_VETO"
                     sidecar = self.trap_hunter.check_trigger(veto, "BULLISH", df)
                     if sidecar["action"] == "EXECUTE":
                          logger.info(f"[{day_name}] 🔪 TRAP-HUNTER: SHORT REVERSAL")
                          self.journal.execute_trade("BEARISH_REVERSAL", curr_price, curr_time, 0.7, "SIDECAR", day_name)
                          
                elif day_type == "TRAP_BEAR" and i == 70:
                     # Bear Trap -> Buy Reversal
                     veto = "BLOCKED: IV_SKEW_VETO"
                     sidecar = self.trap_hunter.check_trigger(veto, "BEARISH", df)
                     if sidecar["action"] == "EXECUTE":
                          logger.info(f"[{day_name}] 🔪 TRAP-HUNTER: BUY REVERSAL")
                          self.journal.execute_trade("BULLISH_REVERSAL", curr_price, curr_time, 0.7, "SIDECAR", day_name)
                          
                # VOLATILE (Black Swan Risk)
                elif day_type == "VOLATILE_MIXED" and i == 200:
                     # Simulate a whipsaw loss
                     # 50% chance system takes a trade and gets stopped
                     if day_idx == 4: # W1-FRI: Loss
                         self.journal.execute_trade("BULLISH", curr_price, curr_time, 0.81, "CORE_BRAIN", day_name)
                         logger.info(f"[{day_name}] ⚠️ RISKY TRADE TAKEN (High Vol)")

        # --- MONTHLY REPORT ---
        logger.info("\n=======================================================")
        logger.info("               MONTHLY PERFORMANCE REPORT               ")
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
                 print(f"[{t['date']}] {t['type']} ({t['source']}) | Outcome: {t['exit_reason']} | PnL: {t['pnl']:+.1f}")

if __name__ == "__main__":
    sim = MonthlySimulator()
    sim.run_month()
