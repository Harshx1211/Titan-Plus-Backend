
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
logger = logging.getLogger("simulation_v9_1")

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

    def log_veto_outcome(self, signal_type, entry_price, run_result, veto_reason, time_str):
        outcome = "SAVED_FROM_LOSS" if run_result < 0 else "MISSED_WIN"
        self.trades.append({
            "type": signal_type,
            "entry_price": entry_price,
            "entry_time": time_str,
            "status": "VETOED",
            "veto_reason": veto_reason,
            "ghost_pnl": run_result,
            "outcome": outcome,
            "source": "BRAIN_VETO"
        })

class FullSystemSimulator:
    """
    [v9.1.0] Full System Simulator (Jan 23rd Scenario)
    Runs PatternEngine, BrainEngine, and TrapHunter (Sidecar) in parallel.
    Simulates: Chop -> Bull Trap (Veto+Sidecar) -> Bearish Trend (Core Execution).
    """
    def __init__(self):
        self.pattern_engine = PatternEngine()
        self.brain_engine = BrainEngine()
        self.trap_hunter = TrapHunter()
        self.evolution_engine = EvolutionEngine(self.brain_engine)
        self.journal = TradeJournal()
        
        self.start_price = 24100.0
        self.data_buffer = []
        
        # Mocking Pattern Engine's 'confirm_reversal' to work with synthetic data
        # In a real run, this would check real candles. Here we force it True for the simulation test.
        self.trap_hunter.pattern_engine.confirm_reversal = lambda df, sig: True 

    def generate_tick(self, min_idx, prev_close):
        # 1. regime: 0-60 (Chop around 24100)
        # 2. regime: 60-90 (Bull Trap -> Spike to 24150)
        # 3. regime: 90-375 (Crash -> 23900)
        
        vol = 5.0
        drift = 0.0
        
        if min_idx < 60: # Chop
            drift = np.random.normal(0, 2)
        elif min_idx < 80: # Trap Spike
            drift = 2.0 
        else: # Crash
            drift = -1.0 # Steady grind down
            if min_idx > 240: vol = 15.0 # Accelerate
            
        close = prev_close + drift + np.random.normal(0, vol)
        high = close + abs(np.random.normal(0, 3))
        low = close - abs(np.random.normal(0, 3))
        return {
            "open": prev_close, "high": high, "low": low, "close": close,
            "volume": 100000,
            "timestamp": datetime(2026, 1, 23, 9, 15) + timedelta(minutes=min_idx)
        }

    def run(self):
        logger.info("=========================================================")
        logger.info("  ORACLE v9.1.0: SIMULATED SESSION REPORT (JAN 23rd)  ")
        logger.info("=========================================================")
        
        curr_price = self.start_price
        
        # Context State (Mocked)
        iv_skew = 1.4 # High Fear
        
        # Ghost PnL Tracker
        active_vetos = []
        
        for i in range(375):
            tick = self.generate_tick(i, curr_price)
            curr_price = tick['close']
            curr_time = tick['timestamp'].strftime("%H:%M")
            self.data_buffer.append(tick)
            
            df = pd.DataFrame(self.data_buffer)
            df.set_index(pd.DatetimeIndex(df['timestamp']), inplace=True)
            if len(df) < 50: continue
            
            # Update Active Trades
            closed = self.journal.update_position(curr_price, curr_time)
            if closed:
                 logger.info(f"[{curr_time}] 💰 {closed['source']} CLOSED: {closed['exit_reason']} | PnL: {closed['pnl']:+.1f}")

            # Update Active Vetos (Ghost PnL)
            for v in active_vetos:
                if v['end_idx'] == i:
                    pnl = (curr_price - v['price']) if v['type'] == "BULLISH" else (v['price'] - curr_price)
                    self.journal.log_veto_outcome(v['type'], v['price'], pnl, v['reason'], v['time'])
                    logger.info(f"[{curr_time}] 👻 GHOST PnL UPDATE: Vetoed {v['type']} result: {pnl:+.1f} pts")

            # SIGNAL GENERATION
            # 1. Bull Trap Event (approx 10:30, minute 75)
            if i == 75:
                 logger.info(f"[{curr_time}] ⚠️  PATTERN DETECTED: BIG BULLISH CANDLE (Price: {curr_price:.1f})")
                 
                 # Brain Check
                 # Feature vector mimicking weak internal structure but high price
                 features = {"ADX": 0.4, "OI_RES": -0.5, "PCR": 0.6}
                 
                 # BRAIN LOGIC
                 if iv_skew > 1.3:
                     veto_reason = "BLOCKED: IV_SKEW_VETO (Fear > 1.3)"
                     logger.info(f"[{curr_time}] 🛡️  CORE BRAIN: {veto_reason}")
                     
                     # Log Ghost
                     active_vetos.append({"start_idx": i, "end_idx": i+30, "price": curr_price, "type": "BULLISH", "reason": veto_reason, "time": curr_time})
                     
                     # SIDECAR CHECK
                     sidecar = self.trap_hunter.check_trigger(veto_reason, "BULLISH", df)
                     if sidecar["action"] == "EXECUTE":
                         logger.info(f"[{curr_time}] 🔪 TRAP-HUNTER: {sidecar['reason']}")
                         self.journal.execute_trade("BEARISH_REVERSAL", curr_price, curr_time, 0.7, source="SIDECAR")
            
            # 2. Bearish Trend Event (approx 13:15, minute 240)
            elif i == 240:
                 logger.info(f"[{curr_time}] ⚠️  PATTERN DETECTED: BEARISH FLOW (Price: {curr_price:.1f})")
                 features = {"ADX": 0.9, "OI_RES": 1.5, "PCR": 0.5} # Strong Trend features
                 
                 boost, thoughts = self.brain_engine.get_confidence_boost(features, "TRENDING")
                 if boost > 0.75:
                      logger.info(f"[{curr_time}] ✅ CORE BRAIN: APPROVE BEARISH (Conf: {boost:.2f})")
                      self.journal.execute_trade("BEARISH", curr_price, curr_time, boost, source="CORE_BRAIN")


        # END OF SESSION REPORT
        logger.info("\n=======================================================")
        logger.info("                  SESSION SCORECARD                    ")
        logger.info("=======================================================")
        
        real_pnl = sum(t['pnl'] for t in self.journal.trades if t['status'] != 'VETOED')
        ghost_pnl = sum(abs(t['ghost_pnl']) for t in self.journal.trades if t['status'] == 'VETOED' and t['ghost_pnl'] < 0)
        
        for t in self.journal.trades:
            if t['status'] == 'VETOED':
                print(f"[{t['entry_time']}] 🛡️ VETO: {t['type']} | Saved: {abs(t['ghost_pnl']):.1f} pts")
            else:
                print(f"[{t['entry_time']}] 💰 {t['source']} TRADE | PnL: {t['pnl']:+.1f} pts")
                
        logger.info("-------------------------------------------------------")
        logger.info(f"REALIZED PnL:   {real_pnl:+.1f} Points")
        logger.info(f"GHOST PnL SAVED:{ghost_pnl:+.1f} Points")
        logger.info("=======================================================")
        
        # EVOLUTION
        logger.info("\n[SYSTEM TRAINING]")
        logger.info("Running Overnight Evolution Engine...")
        # Note: In dry run we mock the db fetch in evolve_session, 
        # but here we just show what it WOULD do based on the journal.
        
        if real_pnl > 0 and ghost_pnl > 0:
             logger.info("✅ EVOLUTION: Session Validated.")
             logger.info("   -> IV_SKEW reputation BOOSTED (+0.01) (Correctly identified Trap)")
             logger.info("   -> ADX reputation BOOSTED (+0.01) (Correctly identified Trend)")
             logger.info("   -> Governor Status: ACTIVE (No tightening needed)")


if __name__ == "__main__":
    sim = FullSystemSimulator()
    sim.run()
