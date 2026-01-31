
import json
import logging
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from typing import Dict, Optional

# Configure Skirmisher Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skirmisher")

class Skirmisher:
    """
    [v9.2.0] THE SKIRMISHER (TACTICAL SCALPING MODULE)
    
    Philosophy: "Entertainment with Seatbelts."
    A mean-reversion engine active ONLY during Sideways regimes to solve 'Boredom'.
    
    NON-NEGOTIABLE SAFEGUARDS:
    1. Trend-Precursor Kill Switch (ADX > 25 = OFF).
    2. Volatility Kill Switch (Range Expansion = OFF).
    3. Separate Ledger (skirmisher_ledger.json).
    4. Learning Firewall (Never touches EvolutionEngine).
    """
    def __init__(self):
        self.state_file = "skirmisher_state.json"
        self.ledger_file = "skirmisher_ledger.json"
        
        # Load or Init State
        self.state = self._load_state()
        
        # Reset daily counters if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state = {
                "date": today,
                "daily_scalps": 0,
                "consecutive_losses": 0,
                "kill_switch_active": False
            }
            self._save_state()

    def check_scalp_signal(self, df: pd.DataFrame, current_regime: str) -> Dict:
        """
        Evaluates potential Scalp (Mean Reversion) opportunities.
        Strictly gated by Trend Precursors.
        """
        # 0. Global Kill Switch Check
        if self.state["kill_switch_active"]:
            return {"action": "BLOCK", "reason": "KILL_SWITCH_ACTIVE"}
        
        if self.state["daily_scalps"] >= 3:
            return {"action": "BLOCK", "reason": "DAILY_CAP_REACHED"}
            
        if current_regime not in ["SIDEWAYS", "CHOP"]:
            return {"action": "BLOCK", "reason": "REGIME_MISMATCH"}

        # 1. Trend-Precursor Kill Switch (The "Seatbelt")
        if len(df) < 20: return {"action": "BLOCK", "reason": "INSUFFICIENT_DATA"}
        
        # Calculate ADX (Trend Strength)
        adx_len = 14
        try:
            adx_df = df.ta.adx(length=adx_len)
            current_adx = adx_df[f"ADX_{adx_len}"].iloc[-1]
        except:
             current_adx = 0
             
        if current_adx > 25:
             return {"action": "BLOCK", "reason": f"TREND_RISK (ADX {current_adx:.1f} > 25)"}
             
        # Calculate ATR (Volatility Expansion)
        atr_df = df.ta.atr(length=14)
        current_atr = atr_df.iloc[-1]
        avg_atr = atr_df.iloc[-20:].mean()
        
        if current_atr > 1.5 * avg_atr:
             return {"action": "BLOCK", "reason": "VOLATILITY_RISK (Range Expansion)"}

        # 2. Strategy Logic: "Band-to-Mean" Reversion
        # Bollinger Bands (2.0 SD)
        bb = df.ta.bbands(length=20, std=2.0)
        upper = bb[f"BBU_20_2.0"].iloc[-1]
        lower = bb[f"BBL_20_2.0"].iloc[-1]
        close = df.close.iloc[-1]
        
        # RSI Divergence Check
        rsi = df.ta.rsi(length=14).iloc[-1]
        
        signal = None
        reason = ""
        
        # SHORT Scalp (Hit Upper Band + Overbought)
        if close >= upper:
            if rsi > 70: 
                signal = "BEARISH_SCALP"
                reason = "BB_UPPER_REJECTION"
            else:
                return {"action": "BLOCK", "reason": "NO_RSI_CONFIRMATION"}

        # LONG Scalp (Hit Lower Band + Oversold)
        elif close <= lower:
             if rsi < 30:
                 signal = "BULLISH_SCALP"
                 reason = "BB_LOWER_REJECTION"
             else:
                 return {"action": "BLOCK", "reason": "NO_RSI_CONFIRMATION"}
                 
        else:
             return {"action": "BLOCK", "reason": "NO_SETUP"}
             
        return {"action": "EXECUTE", "type": signal, "reason": reason}

    def log_execution(self, trade_type: str, entry_price: float, reason: str):
        """
        Logs execution to the SEPARATE Skirmisher Ledger.
        Does NOT touch the Brain's database.
        """
        self.state["daily_scalps"] += 1
        self._save_state()
        
        trade = {
            "id": f"sk_{datetime.now().strftime('%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "type": trade_type,
            "entry": entry_price,
            "reason": reason,
            "status": "OPEN",
            "tag": "TACTICAL_ACTIVITY_ONLY" # Explicit Framing
        }
        
        # Append to Separate Ledger
        try:
            with open(self.ledger_file, "r+") as f:
                trades = json.load(f)
                trades.append(trade)
                f.seek(0)
                json.dump(trades, f, indent=4)
        except FileNotFoundError:
            with open(self.ledger_file, "w") as f:
                json.dump([trade], f, indent=4)
                
        logger.warning(f"SKIRMISHER: ⚠️ TACTICAL SCALP initiated ({trade_type}). Daily: {self.state['daily_scalps']}/3")
        return trade["id"]

    def update_outcome(self, trade_id: str, pnl: float):
        """
        Updates outcome. Triggers Kill Switch if 2 consecutive losses.
        """
        if pnl < 0:
            self.state["consecutive_losses"] += 1
            logger.warning(f"SKIRMISHER: Loss detected ({pnl}). Streak: {self.state['consecutive_losses']}")
            if self.state["consecutive_losses"] >= 2:
                 self.state["kill_switch_active"] = True
                 logger.critical("SKIRMISHER: ⛔ KILL SWITCH ACTIVATED. SCALPING DISABLED FOR SESSION.")
        else:
            self.state["consecutive_losses"] = 0 # Reset streak on win
            
        self._save_state()

    def _load_state(self) -> Dict:
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"date": "", "daily_scalps": 0, "consecutive_losses": 0, "kill_switch_active": False}

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=4)

if __name__ == "__main__":
    sk = Skirmisher()
    print(f"Skirmisher Active. State: {sk.state}")
