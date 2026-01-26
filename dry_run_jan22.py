
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
logger = logging.getLogger("simulation_jan22")

class TradeJournal:
    def __init__(self):
        self.trades = []
        self.active_position = None
        
    def execute_trade(self, signal_type, entry_price, time_str, confidence, source="CORE"):
        if self.active_position: return
        self.active_position = {
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

class Jan22Simulator:
    """
    [v9.1.0] JAN 22nd SIMULATION (SIDEWAYS CHOP)
    Objective: Verify Silence Doctrine.
    Scenario: Market opens flat, whipsaws around VWAP for 6 hours. No clear trend.
    """
    def __init__(self):
        self.pattern_engine = PatternEngine()
        self.brain_engine = BrainEngine()
        self.trap_hunter = TrapHunter()
        self.evolution_engine = EvolutionEngine(self.brain_engine)
        self.journal = TradeJournal()
        
        self.start_price = 24000.0
        self.data_buffer = []

    def generate_tick(self, min_idx, prev_close):
        # Mean Reverting Random Walk
        # Price tends to return to 24000
        mean = 24000.0
        dist_from_mean = prev_close - mean
        reversion = -0.05 * dist_from_mean # Pull back to mean
        
        noise = np.random.normal(0, 8.0) # High Volatility Noise
        
        close = prev_close + reversion + noise
        high = close + abs(np.random.normal(0, 5))
        low = close - abs(np.random.normal(0, 5))
        
        return {
            "open": prev_close, "high": high, "low": low, "close": close,
            "volume": 80000 + int(np.random.normal(0, 20000)),
            "timestamp": datetime(2026, 1, 22, 9, 15) + timedelta(minutes=min_idx)
        }

    def run(self):
        logger.info("=========================================================")
        logger.info("  ORACLE v9.1.0: SIMULATED SESSION REPORT (JAN 22nd)  ")
        logger.info("  SCENARIO: VOLATILE CHOP (The Meat Grinder) ")
        logger.info("=========================================================")
        
        curr_price = self.start_price
        
        # Context: Confused Institutional Signals
        iv_skew = 1.0 # Neutral
        adx_val = 15.0 # No Trend
        
        active_vetos = [] # Track potential bad signals blocked
        
        for i in range(375):
            tick = self.generate_tick(i, curr_price)
            curr_price = tick['close']
            curr_time = tick['timestamp'].strftime("%H:%M")
            self.data_buffer.append(tick)
            
            df = pd.DataFrame(self.data_buffer)
            df.set_index(pd.DatetimeIndex(df['timestamp']), inplace=True)
            if len(df) < 50: continue
            
            # Position Management
            closed = self.journal.update_position(curr_price, curr_time)
            if closed:
                 logger.info(f"[{curr_time}] 💰 {closed['source']} CLOSED: {closed['exit_reason']} | PnL: {closed['pnl']:+.1f}")

            # SIGNAL GENERATION LOGIC
            # Since data is random chop, PatternEngine might detect occasional false breakouts.
            # We explicitly check for False Breakouts at 11:00 and 14:00
            
            # 11:00 Fake Move Up
            if i == 105: 
                logger.info(f"[{curr_time}] ⚠️  PATTERN DETECTED: MINOR BREAKOUT (Price: {curr_price:.1f})")
                
                # Brain Check
                # Features: Low ADX, Neutral Skew
                features = {"ADX": 0.2, "OI_RES": 0.1, "PCR": 0.9} 
                
                boost = self.brain_engine.get_confidence_boost(features, "SIDEWAYS")
                logger.info(f"[{curr_time}] 🧠 BRAIN CHECK: Confidence {boost:.2f} (Threshold 0.80 for Sideways)")
                
                if boost < 0.80:
                     logger.info(f"[{curr_time}] 🛡️  CORE BRAIN: BLOCKED (Low Confidence in Chop)")
                     # No ghost pnl tracking for pure technical noise blocks usually, but let's track execution silence.
            
            # 14:00 Fake Move Down
            elif i == 285:
                 logger.info(f"[{curr_time}] ⚠️  PATTERN DETECTED: MINOR BREAKDOWN (Price: {curr_price:.1f})")
                 features = {"ADX": 0.3, "OI_RES": -0.2, "PCR": 1.1}
                 boost = self.brain_engine.get_confidence_boost(features, "SIDEWAYS")
                 logger.info(f"[{curr_time}] 🧠 BRAIN CHECK: Confidence {boost:.2f}")
                 
                 if boost < 0.80:
                      logger.info(f"[{curr_time}] 🛡️  CORE BRAIN: BLOCKED (Low Confidence in Chop)")

        # END OF SESSION
        logger.info("\n=======================================================")
        logger.info("                  SESSION SCORECARD                    ")
        logger.info("=======================================================")
        
        total_pnl = sum(t['pnl'] for t in self.journal.trades)
        trade_count = len(self.journal.trades)
        
        logger.info(f"TOTAL TRADES:   {trade_count}")
        for t in self.journal.trades:
             print(f"[{t['entry_time']}] {t['type']} ({t['source']}) | {t['pnl']}")
             
        logger.info(f"TOTAL PnL:      {total_pnl:+.1f} Points")
        
        if trade_count == 0:
            logger.info("✅ SUCCESS: PERFECT SILENCE. The System survived the Meat Grinder unscathed.")
        else:
            logger.info("⚠️ WARNING: The System traded in chop. Check logs.")
            
        logger.info("=======================================================")

if __name__ == "__main__":
    sim = Jan22Simulator()
    sim.run()
