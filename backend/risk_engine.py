import time
import logging
from typing import Dict, List, Any, Union
from models import TradeSignal, SignalConfidence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Manages Correlated Risk and psychological guardrails.
    Includes Winning Streak Dampeners and Meta-Buckets.
    """
    def __init__(self):
        self.active_positions: List[TradeSignal] = []
        self.last_loss_time: float = 0
        self.win_streak = 0
        self.max_index_exposure = 2 # Max correlated signals

    def reset(self):
        """Clears loss history and win streaks (Emergency Reset)."""
        self.last_loss_time = 0
        self.win_streak = 0
        self.active_positions = []
        logger.info("RISK: Psychological and streak history cleared.")
        
    def check_meta_bucket(self, index_symbol: str) -> bool:
        """
        Prevents index-wide overexposure.
        """
        correlated = sum(1 for p in self.active_positions if p.symbol.startswith(index_symbol))
        return correlated < self.max_index_exposure

    def is_in_recovery(self) -> bool:
        """
        Checks if the human is in 'Psychological Recovery' after a loss.
        """
        if self.last_loss_time == 0: return False
        return (time.time() - self.last_loss_time) < 3600

    def log_trade(self, is_win: bool):
        if is_win:
            self.win_streak += 1
        else:
            self.win_streak = 0
            self.last_loss_time = time.time()

    def get_suggested_size(self, confidence: Any, base_size: int = 1) -> int:
        """
        Implements Winning Streak Dampening and Recovery Mode logic.
        """
        # 1. Map confidence to multiplier
        if isinstance(confidence, (float, int)):
             mult = 1.0 if confidence > 0.8 else (0.75 if confidence > 0.6 else 0.5)
             if confidence < 0.20: mult = 0.0
        else:
             # Handle SignalConfidence Enum (Legacy/Hybrid)
             mult = {
                SignalConfidence.LOW: 0.1,
                SignalConfidence.MEDIUM: 0.5,
                SignalConfidence.HIGH: 0.75,
                SignalConfidence.EXTREME: 1.0
             }.get(confidence, 0.0)
             
        size = float(base_size) * mult
        
        # 2. Recovery Mode (Post-Loss)
        if time.time() - self.last_loss_time < 3600:
            size *= 0.25 # Aggressive reduction
            
        # 3. Institutional Dampener: Protect against overconfidence after wins
        if self.win_streak >= 3:
            logger.info(f"WINNING STREAK DAMPENER ACTIVE: {self.win_streak} wins")
            size *= 0.5
            
        if mult == 0: return 0
        return max(1, round(size))

if __name__ == "__main__":
    risk = RiskEngine()
    print(f"Initial Win Streak: {risk.win_streak}")
    risk.log_trade(True)
    risk.log_trade(True)
    risk.log_trade(True)
    print(f"Win Streak after 3 wins: {risk.win_streak}")
    print(f"Suggested Size: {risk.get_suggested_size(SignalConfidence.HIGH)}")
