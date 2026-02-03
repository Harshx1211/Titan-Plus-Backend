"""
Gamma Engine: Options Flow Analyzer
Calculates institutional options positioning metrics:
- Net Gamma Exposure (GEX)
- Zero Gamma (flip) levels
- Dealer bias and positioning
- Vanna and Charm flow estimates
"""

from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np


class GammaEngine:
    """
    Analyzes options flow and dealer positioning using Greek exposures.
    """
    
    def __init__(
        self,
        contracts_per_lot: int = 50,  # NIFTY = 50, BANKNIFTY = 15
        spot_move_pct: float = 0.01     # 1% move for GEX calculation
    ):
        self.contracts_per_lot = contracts_per_lot
        self.spot_move_pct = spot_move_pct
    
    def analyze(
        self,
        option_chain: pd.DataFrame,
        current_spot: float
    ) -> Dict:
        """
        Main analysis function for options positioning.
        """
        if option_chain.empty or current_spot <= 0:
            return self._empty_result()
        
        df = option_chain.copy()
        
        # Calculate GEX per strike
        gex_data = self._calculate_gex(df, current_spot)
        
        # Find zero gamma level
        flip_level = self._find_flip_level(gex_data, current_spot)
        
        # Determine dealer bias
        dealer_bias = self._determine_dealer_bias(gex_data, current_spot)
        
        # Find key support/resistance from OI
        support, resistance = self._find_key_levels(df, current_spot)
        
        # Calculate net GEX
        net_gex = sum(gex_data.values())
        
        # Estimate Vanna exposure
        vanna_flow = self._estimate_vanna(df, current_spot)
        
        return {
            'net_gex': float(net_gex),
            'flip_level': float(flip_level),
            'dealer_bias': dealer_bias,
            'gex_by_strike': {k: float(v) for k, v in gex_data.items()},
            'resistance_zone': float(resistance),
            'support_zone': float(support),
            'vanna_exposure': float(vanna_flow)
        }
    
    def _calculate_gex(self, df: pd.DataFrame, spot: float) -> Dict[float, float]:
        """
        Calculate Gamma Exposure per strike.
        GEX = Gamma × OI × Contracts × (Spot² × Move%)
        """
        gex_by_strike = {}
        for _, row in df.iterrows():
            strike = row['strike']
            # [Q23 Fix] Safe Column Access
            c_gamma = row.get('call_gamma')
            p_gamma = row.get('put_gamma')
            
            if pd.isna(c_gamma) or pd.isna(p_gamma): continue
            
            call_oi = row.get('call_oi', 0) or 0
            put_oi = row.get('put_oi', 0) or 0
            spot_factor = (spot ** 2) * self.spot_move_pct
            
            # Use safe gamma values
            call_gex = -1 * c_gamma * call_oi * self.contracts_per_lot * spot_factor
            put_gex = p_gamma * put_oi * self.contracts_per_lot * spot_factor
            
            gex_by_strike[float(strike)] = call_gex + put_gex
        return gex_by_strike
    
    def _find_flip_level(self, gex_data: Dict[float, float], spot: float) -> float:
        """Find the strike where GEX flips from positive to negative."""
        if not gex_data: return spot
        sorted_strikes = sorted(gex_data.keys())
        
        for i in range(len(sorted_strikes) - 1):
            s_low, s_high = sorted_strikes[i], sorted_strikes[i+1]
            if s_low <= spot <= s_high:
                g_low, g_high = gex_data[s_low], gex_data[s_high]
                if (g_low > 0 and g_high < 0) or (g_low < 0 and g_high > 0):
                    return s_low + (s_high - s_low) * (abs(g_low) / (abs(g_low) + abs(g_high)))
        
        return min(gex_data.keys(), key=lambda k: abs(gex_data[k]))
    
    def _determine_dealer_bias(self, gex_data: Dict[float, float], spot: float) -> str:
        """Determine if dealers are long or short gamma."""
        if not gex_data: return 'neutral'
        range_gex = [v for k, v in gex_data.items() if spot * 0.95 <= k <= spot * 1.05]
        if not range_gex: return 'neutral'
        net = sum(range_gex)
        threshold = abs(net) * 0.1
        if net > threshold: return 'long_gamma'
        elif net < -threshold: return 'short_gamma'
        return 'neutral'

    def _find_key_levels(self, df: pd.DataFrame, spot: float) -> Tuple[float, float]:
        """Find key support (Put Wall) and resistance (Call Wall)."""
        df_filt = df[(df['strike'] >= spot * 0.8) & (df['strike'] <= spot * 1.2)].copy()
        if df_filt.empty: return spot * 0.98, spot * 1.02
        
        puts = df_filt[df_filt['strike'] < spot].copy()
        support = puts.loc[puts['put_oi'].fillna(0).idxmax(), 'strike'] if not puts.empty else spot * 0.98
        
        calls = df_filt[df_filt['strike'] > spot].copy()
        resistance = calls.loc[calls['call_oi'].fillna(0).idxmax(), 'strike'] if not calls.empty else spot * 1.02
        
        return float(support), float(resistance)

    def _estimate_vanna(self, df: pd.DataFrame, spot: float) -> float:
        """Estimate Vanna exposure (Delta * IV * OI)."""
        atm = df[(df['strike'] >= spot * 0.95) & (df['strike'] <= spot * 1.05)].copy()
        if atm.empty: return 0.0
        vanna_sum = 0.0
        for _, row in atm.iterrows():
            if not pd.isna(row.get('call_delta')) and not pd.isna(row.get('call_iv')):
                vanna_sum += -1 * row['call_delta'] * row['call_iv'] * (row.get('call_oi', 0) or 0)
            if not pd.isna(row.get('put_delta')) and not pd.isna(row.get('put_iv')):
                vanna_sum += row['put_delta'] * row['put_iv'] * (row.get('put_oi', 0) or 0)
        return vanna_sum

    def _empty_result(self) -> Dict:
        return {'net_gex': 0.0, 'flip_level': 0.0, 'dealer_bias': 'neutral', 'gex_by_strike': {}, 'resistance_zone': 0.0, 'support_zone': 0.0, 'vanna_exposure': 0.0}
