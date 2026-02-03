"""
Macro Regime Analyzer
Evaluates macro market conditions and assigns sentiment score.
Inputs: VIX, DXY, Crude Oil, USDINR, FII Net flows
Output: Regime score from -1.0 (bearish) to +1.0 (bullish)
"""

from typing import Dict, Optional
import numpy as np


class MacroRegime:
    """
    Analyzes macro market conditions and produces sentiment score.
    """
    
    def __init__(self, vix_weight=0.3, dxy_weight=0.25, crude_weight=0.2, fii_weight=0.25):
        self.weights = {'vix': vix_weight, 'dxy': dxy_weight, 'crude': crude_weight, 'fii': fii_weight}
        self.vix_neutral, self.vix_high = 15.0, 25.0
        self.dxy_neutral = 103.0
        self.crude_neutral = 75.0

    def analyze(self, macro_data: Dict) -> float:
        """Calculate macro regime score (-1.0 to +1.0)."""
        vix, dxy, usdinr, crude, fii = [macro_data.get(k) for k in ['VIX', 'DXY', 'USDINR', 'CRUDE', 'FII_NET']]
        if any(v is None for v in [vix, dxy, crude, fii]): return 0.0

        scores = {
            'vix': self._score_vix(vix),
            'dxy': self._score_dxy(dxy, usdinr),
            'crude': self._score_crude(crude),
            'fii': self._score_fii(fii)
        }
        
        regime_score = sum(scores[k] * self.weights[k] for k in scores)
        return float(np.clip(regime_score, -1.0, 1.0))

    def _score_vix(self, vix: float) -> float:
        if vix <= self.vix_neutral:
            return 0.3 if vix < 10 else float(np.clip((self.vix_neutral - vix)/self.vix_neutral, 0.0, 1.0))
        return float(np.clip(-1 * (vix - self.vix_neutral)/(self.vix_high - self.vix_neutral), -1.0, 0.0))

    def _score_dxy(self, dxy: float, usdinr: Optional[float]) -> float:
        base = -1 * (dxy - self.dxy_neutral) / 5.0
        if usdinr:
            base = 0.7 * base + 0.3 * (-1 * (usdinr - 83.0) / 2.0)
        return float(np.clip(base, -1.0, 1.0))

    def _score_crude(self, crude: float) -> float:
        score = -1 * (crude - self.crude_neutral) / 15.0
        if crude > 90: score = -1.0
        elif crude < 60: score = 1.0
        return float(np.clip(score, -1.0, 1.0))

    def _score_fii(self, fii_net: float) -> float:
        return float(np.tanh(fii_net / 2000.0 * 0.5))

    def analyze_detailed(self, macro_data: Dict) -> Dict:
        score = self.analyze(macro_data)
        labels = {True: 'RISK_ON', False: 'RISK_OFF'} # Simplified label logic for brevity
        return {'overall_score': score, 'regime_label': 'NEUTRAL'} # Placeholder, implementation mirrors analyze
