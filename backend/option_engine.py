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
        self.risk_free_rate = 0.07 
        
    def calculate_gex(self, chain_df: pd.DataFrame, spot: float) -> Dict:
        """
        [v8.8] Estimates Net Gamma Exposure (GEX).
        GEX = Gamma * Open Interest.
        Helps identify the 'Gamma Flip' zone where market behavior changes.
        """
        if chain_df.empty: return {"net_gex": 0, "gex_bias": 0}
        
        # Simplified Black-Scholes Gamma approximation for ATM options
        # Gamma = N'(d1) / (S * sigma * sqrt(T))
        # Since we don't have exact IV/T here, we use a relative proxy:
        # Distance from Spot weighting.
        
        net_gex = 0
        gex_data = []
        
        for _, row in chain_df.iterrows():
            strike = row['strike']
            dist = abs(strike - spot)
            if dist > 300: continue # Only ATM matter for Gamma
            
            # Distance weight (Inverse proportional to spot distance)
            weight = 1 / (1 + (dist/50)**2) 
            
            call_oi = row.get('call_oi', 0)
            put_oi = row.get('put_oi', 0)
            
            # Net GEX: Call Gamma is (+) and Put Gamma is (+) for the long side.
            # However, Market Makers are typically SHORT the retail-heavy side.
            # If Calls > Puts, MM are short gamma -> Volatility increase.
            # Simplified GEX proxy: (Call_OI * weight) - (Put_OI * weight)
            strike_gex = (call_oi - put_oi) * weight
            net_gex += strike_gex
            gex_data.append({"strike": strike, "gex": strike_gex})
            
        gex_bias = max(-1.0, min(1.0, net_gex / 500000)) # Normalized bias
        
        return {
            "net_gex": net_gex,
            "gex_bias": gex_bias,
            "gamma_flip_zone": spot if abs(gex_bias) < 0.1 else None
        }

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
                                is_momentum_dominant: bool = False,
                                days_to_expiry: int = 5,
                                max_spread_pct: float = 0.05,
                                chain_df: pd.DataFrame = None,
                                is_synthetic: bool = False) -> Dict:
        """
        [v8.6] Institutional Strike Selection Engine.
        Prioritizes Epistemic Integrity and Adaptive Strike Pool Scanning.
        """
        rejection_reasons = []
        if is_synthetic:
            rejection_reasons.append("DATA_SYNTHETIC_VETO")
            return {"rejection_reasons": rejection_reasons}

        if chain_df is None or chain_df.empty:
            rejection_reasons.append("MISSING_CHAIN_DATA")
            return {"rejection_reasons": rejection_reasons}

        strike_step = 50 if symbol == "NIFTY" else 100
        atm_strike = int(round(spot / strike_step) * strike_step)
        
        # 1. Adaptive Strike Pool Scanning (Phase 28)
        # Start with ATM pool [ATM-1, ATM, ATM+1]
        # Expand if liquidity is below 'Dominance Threshold'
        option_type = "CE" if signal_type == "BULLISH" else "PE"
        LIQUIDITY_DOMINANCE_THRESHOLD = 50000000 # Heuristic for OI * Vol (Adjustable)
        
        selected_strike = None
        base_premium = 0
        selection_logic = "ATM_LIQUIDITY_DOMINANT"

        for radius in [1, 2, 3]: # Scan up to 3 strikes away
            pool_strikes = [atm_strike + i*strike_step for i in range(-radius, radius + 1)]
            candidates = []
            
            for strike in pool_strikes:
                row = chain_df[chain_df['strike'] == strike]
                if row.empty: continue
                
                row = row.iloc[0]
                ltp = row.get(f'{option_type.lower()}_ltp', 0)
                oi = row.get(f'{option_type.lower()}_oi', 0)
                vol = row.get(f'{option_type.lower()}_vol', 0)
                bid = row.get(f'{option_type.lower()}_bid', 0)
                ask = row.get(f'{option_type.lower()}_ask', 0)
                
                # Mid-Price Spread Normalization (v8.5)
                mid_price = (ask + bid) / 2
                spread = (ask - bid) / mid_price if mid_price > 0 else 1.0
                
                if spread > max_spread_pct:
                    continue 
                    
                liquidity_score = oi * max(1, vol)
                candidates.append({
                    "strike": strike,
                    "ltp": ltp,
                    "score": liquidity_score,
                    "spread": spread
                })
                
            if candidates:
                best_cand = sorted(candidates, key=lambda x: x['score'], reverse=True)[0]
                if best_cand['score'] >= LIQUIDITY_DOMINANCE_THRESHOLD or radius == 3:
                    selected_strike = best_cand['strike']
                    base_premium = best_cand['ltp']
                    if radius > 1: selection_logic = f"EXPANDED_POOL_R{radius}"
                    break
        
        if not selected_strike or base_premium <= 0:
            rejection_reasons.append("INSUFFICIENT_LIQUIDITY_OR_SPREAD_VETO")
            return {"rejection_reasons": rejection_reasons}

        # 2. Strike Competition: Pick the Liquidity-Dominant candidate
        # Note: Competition now happens inside the adaptive pool loop above.
        
        # 3. Premium Risk Band Constraint (₹250 Ceiling)
        # Note: In institutional setups, we don't just shift strike because of price,
        # but for this prototype, we maintain the cap for capital preservation.
        if base_premium > 250:
            # Shift one step further OTM if too expensive
            otm_step = strike_step if signal_type == "BULLISH" else -strike_step
            selected_strike += otm_step
            # Re-fetch LTP for the new strike
            new_row = chain_df[chain_df['strike'] == selected_strike]
            if not new_row.empty:
                base_premium = new_row.iloc[0].get(f'{option_type.lower()}_ltp', base_premium * 0.7)
                selection_logic = "CAPITAL_PRESERVATION_SHIFT"

        # --- DYNAMIC TARGET ENGINE (Adaptive Alpha) ---
        target_pct = 0.30 

        # 4. Expiry Sensitivity Check (Gamma Protection)
        if days_to_expiry <= 1:
            target_pct *= 0.7
            selection_logic += "_EXP_SENSITIVE"

        # 5. Zone-Aware Modification
        if macro_zones:
            if signal_type == "BULLISH":
                next_zones = [z for z in macro_zones if z > spot]
                if next_zones:
                    dist_to_zone = (next_zones[0] - spot) / spot
                    if dist_to_zone < 0.005: 
                        target_pct = 0.15
                        selection_logic += "_ZONE_CAPPED"
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

        # 6. Momentum Stretching
        if is_momentum_dominant:
            target_pct += 0.15 
            selection_logic += "_MOM_BOOST"

        # Final Cap (Institutional Risk Guardrail)
        target_pct = max(0.10, min(0.65, target_pct))
        
        return {
            "option_symbol": f"{symbol} {selected_strike} {option_type}",
            "strike": selected_strike,
            "option_type": option_type,
            "premium_entry": float(base_premium),
            "premium_sl": round(base_premium * 0.88, 1), 
            "premium_target": round(base_premium * (1 + target_pct), 1),
            "selection_logic": selection_logic,
            "days_to_expiry": days_to_expiry,
            "rejection_reasons": []
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
