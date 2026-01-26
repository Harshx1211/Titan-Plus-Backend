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
    def __init__(self, base_tolerance_pct: float = 0.5, sync_window: int = 5):
        self.base_tolerance_pct = base_tolerance_pct
        self.sync_window = sync_window # allow divergence for N cycles
        self.future_window: List[float] = []
        self.divergence_history: List[float] = []
        self.last_update_time = time.time()
        
    def check_integrity(self, spot: float, future: float, vix: float = 15.0) -> DivergenceType:
        """
        Calculates divergence with Tick-Window Reconciliation and VIX-Adaptive Thresholds.
        """
        # 1. Sliding Window for Future (Reconcile Latency)
        # Instead of Spot[t] vs Future[t], we compare Spot[t] to the most favorable 
        # Future price in the recent window [t-N...t].
        self.future_window.append(future)
        if len(self.future_window) > self.sync_window:
            self.future_window.pop(0)
            
        # Find the minimum effective basis in the window
        best_basis = min([abs(f - spot) / spot * 100 for f in self.future_window])
        self.divergence_history.append(best_basis)
        
        if len(self.divergence_history) > self.sync_window:
            self.divergence_history.pop(0)

        # 2. VIX-Adaptive Thresholds
        # Volatility expands 'normal' basis. We scale our tolerance by VIX.
        vix_factor = max(vix / 15.0, 1.0)
        dynamic_tolerance = self.base_tolerance_pct * vix_factor
        hard_threshold = 2.5 * vix_factor
        
        avg_basis = sum(self.divergence_history) / len(self.divergence_history)
        
        # 3. Institutional logic: Only quarantine if divergence PERSISTS
        if avg_basis > hard_threshold: 
            logger.warning(f"SENTINEL: HARD DIVERGENCE (PERSISTENT): {avg_basis:.2f}% (Limit: {hard_threshold:.2f}%)")
            return DivergenceType.HARD
        
        if avg_basis > dynamic_tolerance:
            # If it's a spike but not yet persistent, classify as SOFT
            if best_basis > dynamic_tolerance * 2:
                logger.info(f"SENTINEL: TRANSIENT BASIS SPIKE - RECONCILING FEED LAG...")
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
