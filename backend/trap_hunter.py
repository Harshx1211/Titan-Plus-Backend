
import json
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from pattern_engine import PatternEngine

# Configure Sidecar Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trap_hunter")

class TrapHunter:
    """
    [v9.1.0] THE TRAP-HUNTER (SIDECAR MODULE).
    Physically isolated execution engine for Counter-Attack trades.
    
    Guiding Principles:
    1. Isolation: Does not pollute the Core Brain's logic or stats.
    2. Discipline: Strict daily caps and kill switches.
    3. Specificity: Only hunts Vetoed Institutional Traps (IV Skew / Sector).
    """
    def __init__(self):
        self.state_file = "sidecar_state.json"
        self.ledger_file = "sidecar_trades.json"
        self.pattern_engine = PatternEngine()
        
        # Load or Init State
        self.state = self._load_state()
        
        # Reset state if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state = {
                "date": today,
                "daily_trades": 0,
                "consecutive_losses": 0,
                "kill_switch_active": False
            }
            self._save_state()

    def check_trigger(self, veto_reason: str, signal_type: str, df: pd.DataFrame) -> Dict:
        """
        Evaluates if a Vetoed Signal qualifies for a Counter-Attack.
        Returns: {"action": "EXECUTE" | "BLOCK", "reason": str}
        """
        # 1. Check Kill Switch & Cap
        if self.state["kill_switch_active"]:
            return {"action": "BLOCK", "reason": "KILL_SWITCH_ACTIVE"}
        
        if self.state["daily_trades"] >= 2:
            return {"action": "BLOCK", "reason": "DAILY_CAP_REACHED"}

        # 2. Check Institutional Veto Type
        # Only Counter-Attack specific institutional traps
        valid_vetoes = ["IV_SKEW_VETO", "SECTOR_DIVERGENCE_VETO", "GEX_BIAS_VETO"]
        is_inst_trap = any(v in veto_reason for v in valid_vetoes)
        
        if not is_inst_trap:
            return {"action": "BLOCK", "reason": "NOT_INSTITUTIONAL_TRAP"}

        # 3. Structural Reversal Confirmation (Dual Handshake)
        # We need to confirm the Reversal Logic (SFP / Divergence)
        # Note: signal_type is the ORIGINAL signal (e.g., BULLISH breakout).
        # We want to know if we can SHORT it (BEARISH Reversal).
        reversal_confirmed = self.pattern_engine.confirm_reversal(df, signal_type)
        
        if reversal_confirmed:
            return {"action": "EXECUTE", "reason": f"TRAP_HUNTER_CONFIRMED ({veto_reason})"}
        else:
            return {"action": "BLOCK", "reason": "NO_STRUCTURAL_CONFIRMATION"}

    def log_execution(self, trade_type: str, entry_price: float, reason: str):
        """
        Logs a Sidecar Execution and increments counters.
        """
        self.state["daily_trades"] += 1
        self._save_state()
        
        trade = {
            "id": f"sc_{datetime.now().strftime('%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "type": trade_type,
            "entry": entry_price,
            "reason": reason,
            "status": "OPEN"
        }
        
        # Append to Ledger
        try:
            with open(self.ledger_file, "r+") as f:
                trades = json.load(f)
                trades.append(trade)
                f.seek(0)
                json.dump(trades, f, indent=4)
        except FileNotFoundError:
            with open(self.ledger_file, "w") as f:
                json.dump([trade], f, indent=4)
                
        logger.warning(f"SIDECAR: 🔪 EXECUTING {trade_type} (Counter-Attack). Daily: {self.state['daily_trades']}/2")
        return trade["id"]

    def update_outcome(self, trade_id: str, pnl: float):
        """
        Updates the outcome of a sidecar trade. 
        Triggers Kill Switch if losses pile up.
        """
        # Update Ledger
        # (Simplified logic for reading/writing ledger)
        # In a real system, we'd find the trade by ID.
        
        if pnl < 0:
            self.state["consecutive_losses"] += 1
            logger.warning(f"SIDECAR: Loss detected. Consecutive: {self.state['consecutive_losses']}")
            if self.state["consecutive_losses"] >= 2:
                 self.state["kill_switch_active"] = True
                 logger.critical("SIDECAR: ⛔ KILL SWITCH ACTIVATED. TRAP-HUNTER DISABLED FOR SESSION.")
        else:
            self.state["consecutive_losses"] = 0 # Reset streak on win
            
        self._save_state()

    def _load_state(self) -> Dict:
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"date": "", "daily_trades": 0, "consecutive_losses": 0, "kill_switch_active": False}

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=4)

if __name__ == "__main__":
    # Test
    hunter = TrapHunter()
    print(f"TrapHunter Active. State: {hunter.state}")
