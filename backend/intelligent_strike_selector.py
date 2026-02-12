"""
INTELLIGENT STRIKE SELECTION (v15.3.8 - Industrial Hardening)
=============================================================
Features:
- Adaptive Delta Targeting (Regime-aware)
- Liquidity Filtering (Volume & OI)
- Gamma Risk Management (Near-expiry protection)
- Spread Optimization
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger("strike_selector")

class MarketRegime(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    SIDEWAYS = "SIDEWAYS"
    VOLATILE = "VOLATILE"

class IntelligentStrikeSelector:
    """
    [v15.3.8] Selects the optimal option strike based on market context.
    """
    
    def __init__(self):
        # Target deltas for different regimes
        self.regime_deltas = {
            MarketRegime.TRENDING_BULL: 0.60,   # ITM/Deep ITM for trend following
            MarketRegime.TRENDING_BEAR: 0.60,
            MarketRegime.SIDEWAYS: 0.45,      # Near ATM
            MarketRegime.VOLATILE: 0.35       # OTM for lower absolute risk
        }
        
        # Liquidity thresholds
        self.min_volume = 1000
        self.min_oi = 5000
        
        # Gamma risk
        self.max_gamma_pct = 0.05 # Prevent picking gamma-bombs near expiry
        
        logger.info("IntelligentStrikeSelector initialized (v15.3.8)")
    
    def select_best_strike(self, 
                          option_chain: List[Dict], 
                          regime: MarketRegime,
                          option_type: str = "CE",
                          expiry_days: int = 7) -> Optional[Dict]:
        """
        [v15.3.8] Optimized selection algorithm
        """
        if not option_chain:
            return None
            
        target_delta = self.regime_deltas.get(regime, 0.50)
        
        # Adjust delta for near-expiry (reduce theta decay exposure)
        if expiry_days <= 1:
            target_delta += 0.10 # Go deeper ITM to reduce extrinsic value %
            
        best_match = None
        min_delta_diff = float('inf')
        
        for strike in option_chain:
            # 1. Filter by Liquidity
            vol = strike.get('volume', 0)
            oi = strike.get('oi', 0)
            
            if vol < self.min_volume or oi < self.min_oi:
                continue
                
            # 2. Delta Matching
            delta = abs(strike.get('delta', 0))
            if delta == 0: continue # Skip if delta not calculated
            
            diff = abs(delta - target_delta)
            
            # 3. Spread Check
            bid = strike.get('bid', 0)
            ask = strike.get('ask', 0)
            if ask > 0:
                spread_pct = ((ask - bid) / ask) * 100
                if spread_pct > 2.0: # Max 2% spread for options
                    continue
            
            # 4. Gamma Check (if near expiry)
            if expiry_days <= 1:
                gamma = strike.get('gamma', 0)
                if gamma > self.max_gamma_pct:
                    continue
            
            if diff < min_delta_diff:
                min_delta_diff = diff
                best_match = strike
        
        if best_match:
            logger.info(
                f"Selected {best_match['symbol']} (Delta: {best_match.get('delta'):.2f}, "
                f"Regime: {regime}, Target: {target_delta})"
            )
            
        return best_match

    def filter_liquid_strikes(self, strikes: List[Dict]) -> List[Dict]:
        """Filters a list of strikes for minimum liquidity requirements"""
        return [
            s for s in strikes 
            if s.get('volume', 0) >= self.min_volume 
            and s.get('oi', 0) >= self.min_oi
        ]
