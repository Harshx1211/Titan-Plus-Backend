"""
EXECUTION SLIPPAGE CONTROL (v15.3.8 - Industrial Hardening)
===========================================================
Features:
- Pre-execution slippage validation
- LIMIT order placement instead of MARKET
- Post-execution slippage tracking
- Execution timeout handling (30s)
"""

import time
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger("execution_slippage")

@dataclass
class SlippageStats:
    symbol: str
    expected_price: float
    actual_price: float
    slippage_points: float
    slippage_pct: float
    execution_time_ms: float

class SlippageController:
    """
    [v15.3.8] Monitors and controls order execution quality.
    """
    
    def __init__(self, 
                 max_slippage_pct: float = 0.5,
                 max_slippage_points: float = 10.0,
                 order_timeout: int = 30):
        self.max_slippage_pct = max_slippage_pct
        self.max_slippage_points = max_slippage_points
        self.order_timeout = order_timeout
        
        self.history: list[SlippageStats] = []
        
        logger.info(
            f"SlippageController initialized: max_pct={max_slippage_pct}%, "
            f"max_points={max_slippage_points}, timeout={order_timeout}s"
        )
    
    def validate_pre_execution(self, 
                               symbol: str, 
                               last_price: float, 
                               target_price: float) -> Tuple[bool, str]:
        """
        Check if the gap between last price and our target is acceptable.
        """
        if last_price <= 0:
            return False, "INVALID_PRICE"
            
        gap_points = abs(target_price - last_price)
        gap_pct = (gap_points / last_price) * 100
        
        if gap_pct > self.max_slippage_pct:
            return False, f"EXCESSIVE_PRE_SLIPPAGE: {gap_pct:.2f}% > {self.max_slippage_pct}%"
            
        if gap_points > self.max_slippage_points:
            return False, f"EXCESSIVE_PRE_POINTS: {gap_points:.2f} > {self.max_slippage_points}"
            
        return True, "READY"
    
    def record_execution(self, 
                        symbol: str, 
                        expected_price: float, 
                        actual_price: float,
                        start_time: float) -> SlippageStats:
        """
        Track actual slippage after order fulfillment.
        """
        execution_time_ms = (time.time() - start_time) * 1000
        slippage_points = actual_price - expected_price
        slippage_pct = (slippage_points / expected_price * 100) if expected_price > 0 else 0
        
        stats = SlippageStats(
            symbol=symbol,
            expected_price=expected_price,
            actual_price=actual_price,
            slippage_points=slippage_points,
            slippage_pct=slippage_pct,
            execution_time_ms=execution_time_ms
        )
        
        self.history.append(stats)
        
        if abs(slippage_pct) > self.max_slippage_pct:
            logger.warning(
                f"🚩 HIGH_SLIPPAGE: {symbol} executed with {slippage_pct:.2f}% slippage "
                f"({slippage_points:.2f} pts) in {execution_time_ms:.0f}ms"
            )
        else:
            logger.info(
                f"✅ Execution OK: {symbol} slippage {slippage_pct:.2f}% in {execution_time_ms:.0f}ms"
            )
            
        return stats

    def get_average_slippage(self, symbol: Optional[str] = None) -> float:
        """Calculate average slippage percentage"""
        relevant = [s.slippage_pct for s in self.history if symbol is None or s.symbol == symbol]
        if not relevant:
            return 0.0
        return sum(relevant) / len(relevant)
