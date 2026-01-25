import time
import logging
from datetime import datetime
from typing import Tuple, List
from models import MarketData, DivergenceType

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataSentinel:
    """
    The Sentinel is the foundation of truth. 
    It triangulates data and reconciles time-drifts.
    """
    def __init__(self, tolerance_pct: float = 0.5, sync_window: int = 3):
        self.tolerance_pct = tolerance_pct
        self.sync_window = sync_window # allow divergence for N cycles
        self.divergence_history: List[float] = []
        self.last_update_time = time.time()
        
    def check_integrity(self, spot: float, future: float) -> DivergenceType:
        """
        Calculates divergence with Time-Window Reconciliation.
        """
        basis = abs(future - spot) / spot * 100
        self.divergence_history.append(basis)
        
        # Keep history within sync window
        if len(self.divergence_history) > self.sync_window:
            self.divergence_history.pop(0)

        # Institutional logic: Only quarantine if divergence PERSISTS
        avg_basis = sum(self.divergence_history) / len(self.divergence_history)
        
        if avg_basis > 2.5: 
            logger.warning(f"HARD DIVERGENCE (PERSISTENT): {avg_basis:.2f}%")
            return DivergenceType.HARD
        
        if avg_basis > self.tolerance_pct:
            # If it's a spike but not yet persistent, classify as SOFT
            if basis > self.tolerance_pct * 2:
                logger.info(f"TRANSIENT SPIKE DETECTED - RECONCILING...")
                return DivergenceType.SOFT
            return DivergenceType.SOFT
            
        return DivergenceType.NONE

    def validate_oi_sanity(self, current_oi: int, prev_oi: int) -> bool:
        """
        Detects ghost conviction (abnormal OI jumps).
        """
        if prev_oi == 0: return True
        
        change_pct = abs(current_oi - prev_oi) / prev_oi * 100
        if change_pct > 300: # 300% jump in one refresh is likely a data error
            logger.error(f"OI SANITY FAIL: {change_pct:.2f}% jump")
            return False
        return True

    def get_data_latency(self) -> float:
        return time.time() - self.last_update_time

if __name__ == "__main__":
    # Test cases
    sentinel = DataSentinel()
    print(f"Normal Case: {sentinel.check_integrity(25000, 25050, (150, 150))}")
    print(f"Hard Divergence: {sentinel.check_integrity(25000, 26000, (150, 150))}")
