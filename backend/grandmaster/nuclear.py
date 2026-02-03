"""
Nuclear Scorecard: Master Decision Engine
Combines all Grandmaster module outputs into a single trade decision.
Uses weighted scorecard: (SMC*0.25) + (Zones*0.20) + (Liquidity*0.15) + (Greeks*0.15) + (Time*0.10) + (GEX*0.10) + (Macro*0.05)
"""

from typing import Dict, Optional
from datetime import datetime
import numpy as np


class NuclearScorecard:
    """The final judge - combines signals into actionable decisions."""
    
    def __init__(self, nuclear_threshold=0.85, standard_threshold=0.70):
        self.thresholds = {'nuclear': nuclear_threshold, 'standard': standard_threshold}
        self.weights = {
            'smc_structure': 0.25, 'order_blocks': 0.20, 'liquidity': 0.15,
            'greeks_flow': 0.15, 'session_time': 0.10, 'gex_regime': 0.10, 'macro': 0.05
        }
    
    def evaluate(self, smc_output: Dict, greeks_output: Dict, macro_score: float, current_time: Optional[datetime] = None) -> Dict:
        """Main evaluation function."""
        if current_time is None: current_time = datetime.now()
        
        # Determine adaptive weights based on Regime
        current_weights = self.weights.copy()
        
        # High Volatility Adjustment (VIX > 20 implied by Macro Score being Risk-Off)
        if macro_score < -0.3:  # Risk Off / Fear
            # Macro and GEX become dominant
            current_weights['macro'] = 0.20        # Was 0.05
            current_weights['gex_regime'] = 0.20   # Was 0.10
            # Reduce technicals logic
            current_weights['smc_structure'] = 0.15 # Was 0.25
            current_weights['liquidity'] = 0.10     # Was 0.15
        
        # Calculate individual component scores
        smc_score = self._score_smc(smc_output)
        zones_score = self._score_zones(smc_output)
        liquidity_score = self._score_liquidity(smc_output)
        greeks_score = self._score_greeks(greeks_output)
        time_score = self._score_timing(current_time)
        gex_score = self._score_gex(greeks_output)
        macro_norm = self._normalize_macro(macro_score)
        
        scores = {
            'smc_structure': smc_score,
            'order_blocks': zones_score,
            'liquidity': liquidity_score,
            'greeks_flow': greeks_score,
            'session_time': time_score,
            'gex_regime': gex_score,
            'macro': macro_norm
        }
        
        # Weighted composite score using ADAPTIVE weights
        # Normalize weights to sum to 1.0 first
        weight_sum = sum(current_weights.values())
        
        total_score = (
            smc_score * current_weights['smc_structure'] +
            zones_score * current_weights['order_blocks'] +
            liquidity_score * current_weights['liquidity'] +
            greeks_score * current_weights['greeks_flow'] +
            time_score * current_weights['session_time'] +
            gex_score * current_weights['gex_regime'] +
            macro_norm * current_weights['macro']
        ) / weight_sum
        
        quality, size, signal = self._determine_action(total_score)
        
        return {
            'entry_signal': signal, 'position_size': size, 'signal_quality': quality,
            'total_score': total_score, 'breakdown': scores,
            'direction': self._determine_direction(smc_output, greeks_output)
        }
    
    def _score_smc(self, smc: Dict) -> float:
        score = 0.6 if smc.get('is_bos') else 0.0
        score += 0.5 if smc.get('is_choch') else 0.0
        if smc.get('trend') in ['bullish', 'bearish']: score += 0.3
        return min(score, 1.0)
    
    def _score_zones(self, smc: Dict) -> float:
        zones = smc.get('zones', [])
        return min(len(zones) * 0.3 + sum(0.2 for z in zones[:2] if z.get('strength', 0) > 0.005), 1.0)

    def _score_greeks(self, greeks: Dict) -> float:
        score = 0.4 if greeks.get('dealer_bias') == 'long_gamma' else (0.2 if greeks.get('dealer_bias') == 'short_gamma' else 0.0)
        return min(score + 0.4, 1.0) # Simplified logic

    def _score_timing(self, t: datetime) -> float:
        m = t.hour * 60 + t.minute
        if 560 <= m <= 600 or 855 <= m <= 900: return 1.0 # Prime times: 9:20-10:00, 14:15-15:00
        return 0.6 # Default

    def _determine_action(self, score: float):
        if score >= self.thresholds['nuclear']: return 'NUCLEAR', 1.0, True
        elif score >= self.thresholds['standard']: return 'STANDARD', 0.5 + 0.5 * ((score - self.thresholds['standard']) / (self.thresholds['nuclear'] - self.thresholds['standard'])), True
        return 'NO_TRADE', 0.0, False

    def _determine_direction(self, smc: Dict, greeks: Dict) -> str:
        longs = (2 if smc.get('trend') == 'bullish' else 0) + (1 if smc.get('is_bos') and smc.get('trend')=='bullish' else 0)
        shorts = (2 if smc.get('trend') == 'bearish' else 0) + (1 if smc.get('is_bos') and smc.get('trend')=='bearish' else 0)
        return 'LONG' if longs > shorts else ('SHORT' if shorts > longs else 'NEUTRAL')
