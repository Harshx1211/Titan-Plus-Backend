import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("option_engine")

class OptionEngine:
    """
    X-Ray Vision for Option Chains.
    Calculates Max Pain, Strike Battles, and Intraday COI.
    """
    def __init__(self):
        self.last_max_pain: float = 0.0

    def calculate_max_pain(self, chain_df: pd.DataFrame) -> float:
        """
        Calculates the strike price where option buyers feel the most 'pain' 
        (i.0. the strike where total loss for option buyers is minimized).
        Required columns in chain_df: ['strike', 'call_oi', 'put_oi']
        """
        if chain_df.empty:
            return 0.0
        
        strikes = chain_df['strike'].unique()
        losses = []
        
        for strike in strikes:
            # Loss for call buyers if market closes at 'strike'
            call_loss = chain_df[chain_df['strike'] > strike].apply(
                lambda x: (x['strike'] - strike) * x['call_oi'], axis=1
            ).sum()
            
            # Loss for put buyers if market closes at 'strike'
            put_loss = chain_df[chain_df['strike'] < strike].apply(
                lambda x: (strike - x['strike']) * x['put_oi'], axis=1
            ).sum()
            
            losses.append(call_loss + put_loss)
            
        max_pain_strike = strikes[np.argmin(losses)]
        self.last_max_pain = float(max_pain_strike)
        return self.last_max_pain

    def detect_strike_battles(self, chain_df: pd.DataFrame) -> List[Dict]:
        """
        Identifies strikes where huge OI is clustered (Institutional Walls).
        """
        if chain_df.empty:
            return []
            
        # Find top 3 strikes with highest OI for Calls and Puts
        call_walls = chain_df.nlargest(3, 'call_oi')[['strike', 'call_oi']].to_dict('records')
        put_walls = chain_df.nlargest(3, 'put_oi')[['strike', 'put_oi']].to_dict('records')
        
        battles = []
        for cw in call_walls:
            battles.append({"strike": cw['strike'], "type": "CE_RESISTANCE", "strength": cw['call_oi']})
        for pw in put_walls:
            battles.append({"strike": pw['strike'], "type": "PE_SUPPORT", "strength": pw['put_oi']})
            
        return battles

    def get_market_sentiment(self, chain_df: pd.DataFrame) -> str:
        """
        Aggregates option chain data into a single sentiment string.
        """
        if chain_df.empty:
            return "NEUTRAL"
            
        total_call_oi = chain_df['call_oi'].sum()
        total_put_oi = chain_df['put_oi'].sum()
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        
        if pcr > 1.2: return "BULLISH_OVERBOUGHT"
        if pcr > 0.9: return "BULLISH_STRENGTH"
        if pcr < 0.7: return "BEARISH_STRENGTH"
        return "NEUTRAL"

    def find_executable_option(self, symbol: str, spot: float, signal_type: str, 
                                macro_zones: List[float] = [], 
                                is_momentum_dominant: bool = False) -> Dict:
        """
        [v8.2] Translates an Index Signal into the "Optimal Balance" Option Strike.
        Now with Adaptive Dynamic Target Engine.
        """
        strike_step = 50 if symbol == "NIFTY" else 100
        atm_strike = int(round(spot / strike_step) * strike_step)
        
        # Determine the "Optimal" Strike
        import random
        base_premium = random.randint(110, 190) # Simulated current premium
        
        target_strike = atm_strike
        if base_premium > 250:
            if signal_type == "BULLISH": target_strike += strike_step
            else: target_strike -= strike_step
            base_premium *= 0.7 
        
        option_type = "CE" if signal_type == "BULLISH" else "PE"
        
        # --- DYNAMIC TARGET ENGINE ---
        # 1. Baseline Target
        target_pct = 0.30 
        selection_logic = "ATM_OPTIMAL" if target_strike == atm_strike else "COST_BALANCED_OTM"

        # 2. Zone-Aware Modification
        # Find distance to next logical macro zone
        if macro_zones:
            if signal_type == "BULLISH":
                next_zones = [z for z in macro_zones if z > spot]
                if next_zones:
                    dist_to_zone = (next_zones[0] - spot) / spot
                    # If zone is close (< 0.5%), tighten target to ensures banking
                    if dist_to_zone < 0.005: 
                        target_pct = 0.15
                        selection_logic += "_ZONE_CAPPED"
                    # If zone is far (> 1.5%), expand target
                    elif dist_to_zone > 0.015:
                        target_pct = 0.45
                        selection_logic += "_ZONE_EXPANDED"
            else: # BEARISH
                next_zones = [z for z in macro_zones if z < spot]
                if next_zones:
                    dist_to_zone = (spot - next_zones[-1]) / spot
                    if dist_to_zone < 0.005:
                        target_pct = 0.15
                        selection_logic += "_ZONE_CAPPED"
                    elif dist_to_zone > 0.015:
                        target_pct = 0.45
                        selection_logic += "_ZONE_EXPANDED"

        # 3. Momentum Stretching
        if is_momentum_dominant:
            target_pct += 0.15 # Massive expansion for structural breakouts
            selection_logic += "_MOMENTUM_BOOST"

        # Final Cap (Risk Guardrail)
        target_pct = max(0.10, min(0.65, target_pct))
        
        return {
            "option_symbol": f"{symbol} {target_strike} {option_type}",
            "strike": target_strike,
            "option_type": option_type,
            "premium_entry": float(base_premium),
            "premium_sl": round(base_premium * 0.88, 1), # 12% SL is Fixed (Capital Protection)
            "premium_target": round(base_premium * (1 + target_pct), 1),
            "selection_logic": selection_logic
        }

if __name__ == "__main__":
    # Mock for testing
    data = {
        'strike': [24400, 24500, 24600, 24700, 24800],
        'call_oi': [1000, 5000, 10000, 15000, 20000],
        'put_oi': [20000, 15000, 10000, 5000, 1000]
    }
    df = pd.DataFrame(data)
    engine = OptionEngine()
    print(f"Max Pain: {engine.calculate_max_pain(df)}")
    print(f"Battles: {engine.detect_strike_battles(df)}")
    print(f"Sentiment: {engine.get_market_sentiment(df)}")
