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
        
    def calculate_gex_proxy(self, chain_df: pd.DataFrame, spot: float) -> Dict:
        """
        [Institutional Step 4] Estimates Net Gamma Exposure (GEX) Proxy.
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
        (i.e. the strike where total loss for option buyers is minimized).
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
                                precision_levels: Dict = {}, 
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
        if chain_df is None or chain_df.empty:
            rejection_reasons.append("MISSING_CHAIN_DATA")
            return {"rejection_reasons": rejection_reasons}

        strike_step = 50 if symbol == "NIFTY" else 100
        atm_strike = int(round(spot / strike_step) * strike_step)
        
        # 1. Adaptive Strike Pool Scanning (Phase 28)
        # Start with ATM pool [ATM-1, ATM, ATM+1]
        # Expand if liquidity is below 'Dominance Threshold'
        option_type = "CE" if signal_type == "BULLISH" else "PE"
        LIQUIDITY_DOMINANCE_THRESHOLD = 1000 # [v9.8] Dropped to 1k for total frequency 
        max_spread_pct = 0.50 # [v9.8] increased for testing
        
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
                prefix = "call" if option_type == "CE" else "put"
                ltp = row.get(f'{prefix}_ltp', 0)
                oi = row.get(f'{prefix}_oi', 0)
                vol = row.get(f'{prefix}_vol', 0)
                # [Q22 Fix] Safe Access for Bid/Ask (Fallback to LTP)
                bid = row.get(f'{prefix}_bid', ltp)
                ask = row.get(f'{prefix}_ask', ltp)
                
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

        # 5. Zone-Aware Modification (Precision Levels)
        if precision_levels:
            # Flatten all relevant zones (OBs, Fractals, Pivots)
            res_zones = [ob['price'] for ob in precision_levels.get('order_blocks', []) if ob['type'] == 'RESISTANCE']
            res_zones += [f['price'] for f in precision_levels.get('fractals', []) if f['type'] == 'RESISTANCE']
            res_zones += [v for k,v in precision_levels.get('pivots', {}).items() if k.startswith('R')]

            sup_zones = [ob['price'] for ob in precision_levels.get('order_blocks', []) if ob['type'] == 'SUPPORT']
            sup_zones += [f['price'] for f in precision_levels.get('fractals', []) if f['type'] == 'SUPPORT']
            sup_zones += [v for k,v in precision_levels.get('pivots', {}).items() if k.startswith('S')]

            if signal_type == "BULLISH":
                next_zones = sorted([z for z in res_zones if z > spot])
                if next_zones:
                    dist_to_zone = (next_zones[0] - spot) / spot
                    if dist_to_zone < 0.005: 
                        target_pct = 0.15
                        selection_logic += "_OB_CAPPED"
                    elif dist_to_zone > 0.015:
                        target_pct = 0.45
                        selection_logic += "_OB_EXPANDED"
            else: # BEARISH
                next_zones = sorted([z for z in sup_zones if z < spot], reverse=True)
                if next_zones:
                    dist_to_zone = (spot - next_zones[0]) / spot
                    if dist_to_zone < 0.005:
                        target_pct = 0.15
                        selection_logic += "_OB_CAPPED"
                    elif dist_to_zone > 0.015:
                        target_pct = 0.45
                        selection_logic += "_OB_EXPANDED"

        # 6. Momentum Stretching
        if is_momentum_dominant:
            target_pct += 0.15 
            selection_logic += "_MOM_BOOST"

        # Final Cap (Institutional Risk Guardrail)
        target_pct = max(0.10, min(0.65, target_pct))
        
        return {
            "strike": selected_strike,
            "option_symbol": f"{symbol} {selected_strike} {option_type}", # Standard format
            "premium_entry": float(base_premium),
            "premium_sl": round(base_premium * 0.8, 2), # 20% Option SL Fallback
            "premium_target": round(base_premium * 1.5, 2), # 50% Option Target Fallback
            "option_type": option_type,
            "selection_logic": selection_logic,
            "days_to_expiry": days_to_expiry,
            "rejection_reasons": []
        }
    
    def analyze_coi(self, current_chain: pd.DataFrame, previous_chain: pd.DataFrame, 
                    spot: float, price_change: float) -> Dict:
        """
        [ADVANCED] Change in OI Analysis - Detects fresh institutional positions
        
        Returns signal type and strength based on COI + price action
        """
        if current_chain.empty or previous_chain.empty:
            return {"signal": "NEUTRAL", "strength": 0.0, "reasons": []}
        
        # Merge chains on strike
        merged = current_chain.merge(previous_chain, on='strike', suffixes=('_curr', '_prev'))
        
        # Calculate COI
        merged['coi_call'] = merged['call_oi_curr'] - merged['call_oi_prev']
        merged['coi_put'] = merged['put_oi_curr'] - merged['put_oi_prev']
        
        # Focus on ATM strikes (within 200 points)
        atm_strikes = merged[abs(merged['strike'] - spot) <= 200]
        
        total_coi_call = atm_strikes['coi_call'].sum()
        total_coi_put = atm_strikes['coi_put'].sum()
        
        reasons = []
        signal = "NEUTRAL"
        strength = 0.0
        
        # Fresh Call Buying + Price Up = STRONG BULLISH
        if total_coi_call > 10000 and price_change > 0:
            signal = "FRESH_CALL_BUYING"
            strength = min(total_coi_call / 50000, 1.0)
            reasons.append(f"Fresh Call OI: +{total_coi_call:,.0f}")
        
        # Fresh Put Buying + Price Down = STRONG BEARISH
        elif total_coi_put > 10000 and price_change < 0:
            signal = "FRESH_PUT_BUYING"
            strength = min(total_coi_put / 50000, 1.0)
            reasons.append(f"Fresh Put OI: +{total_coi_put:,.0f}")
        
        # Call Unwinding + Price Up = WEAK BULLISH
        elif total_coi_call < -10000 and price_change > 0:
            signal = "CALL_UNWINDING"
            strength = 0.3
            reasons.append(f"Call Unwinding: {total_coi_call:,.0f}")
        
        # Put Unwinding + Price Down = WEAK BEARISH
        elif total_coi_put < -10000 and price_change < 0:
            signal = "PUT_UNWINDING"
            strength = 0.3
            reasons.append(f"Put Unwinding: {total_coi_put:,.0f}")
        
        # Call Writing + Price Down = BEARISH
        elif total_coi_call > 10000 and price_change < 0:
            signal = "CALL_WRITING"
            strength = 0.7
            reasons.append(f"Call Writing: +{total_coi_call:,.0f}")
        
        # Put Writing + Price Up = BULLISH
        elif total_coi_put > 10000 and price_change > 0:
            signal = "PUT_WRITING"
            strength = 0.7
            reasons.append(f"Put Writing: +{total_coi_put:,.0f}")
        
        return {
            "signal": signal,
            "strength": strength,
            "reasons": reasons,
            "coi_call": total_coi_call,
            "coi_put": total_coi_put
        }
    
    def calculate_iv_percentile(self, current_iv: float, historical_iv: List[float]) -> Dict:
        """
        [Institutional Step 5] Smooth IV Percentile Scaling
        Replaces hard veto with a continuous size-reduction factor.
        """
        if not historical_iv or len(historical_iv) < 30:
            return {"percentile": 50.0, "regime": "UNKNOWN", "score": 0.0, "scaling_factor": 1.0}
        
        # Calculate percentile
        rank = sum(1 for iv in historical_iv if current_iv > iv)
        percentile = (rank / len(historical_iv)) * 100
        
        # Smooth scaling factor: 1.0 if IV is low, down to 0.2 if IV is at 100th percentile
        # size_mult = (100 - percentile) / 100.0, but we cap it at 0.2
        scaling_factor = max(0.2, (100 - percentile) / 100.0)
        
        # Classify regime
        if percentile < 20:
            regime = "DEAD_MARKET"
        elif percentile < 30:
            regime = "LOW_VOL"
        elif 30 <= percentile <= 70:
            regime = "OPTIMAL"
        elif percentile <= 80:
            regime = "ELEVATED"
        else:
            regime = "PANIC"
        
        return {
            "percentile": round(percentile, 1),
            "regime": regime,
            "scaling_factor": round(scaling_factor, 2),
            "current_iv": current_iv
        }

    def calculate_precision_greeks(self, spot: float, strike: float, iv_decimal: float, minutes_to_expiry: int, option_type: str = "CE") -> Dict:
        """
        [Institutional Step 5] High-Fidelity Greeks (Minutes-to-Expiry)
        Crucial for gamma spikes on expiry day.
        """
        from scipy.stats import norm
        
        # T in years
        T = max(1 / (365 * 24 * 60), minutes_to_expiry / (365 * 24 * 60))
        r = self.risk_free_rate
        sigma = max(0.01, iv_decimal)
        
        d1 = (np.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == "CE":
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
            
        gamma = norm.pdf(d1) / (spot * sigma * np.sqrt(T))
        vega = spot * norm.pdf(d1) * np.sqrt(T) / 100.0 # Per 1% IV change
        theta = (- (spot * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * strike * np.exp(-r * T) * norm.cdf(d2 if option_type == "CE" else -d2)) / 365.0
        
        return {
            "delta": round(delta, 3),
            "gamma": round(gamma, 6),
            "vega": round(vega, 3),
            "theta": round(theta, 3),
            "tte_minutes": minutes_to_expiry
        }
    
    def get_implied_move(self, chain_df: pd.DataFrame, spot: float) -> Dict:
        """
        [ADVANCED] Implied Move - Expected daily range from ATM straddle
        
        Returns expected range and reversal zones
        """
        if chain_df.empty:
            return {"implied_move": 0.0, "upper_bound": spot, "lower_bound": spot}
        
        # Find ATM strike
        chain_df['dist_from_spot'] = abs(chain_df['strike'] - spot)
        atm_row = chain_df.loc[chain_df['dist_from_spot'].idxmin()]
        
        # ATM Straddle = ATM Call Premium + ATM Put Premium
        atm_call_premium = atm_row.get('call_ltp', 0)
        atm_put_premium = atm_row.get('put_ltp', 0)
        straddle_price = atm_call_premium + atm_put_premium
        
        # Implied Move = Straddle × 0.85 (statistical adjustment)
        implied_move = straddle_price * 0.85
        
        upper_bound = spot + implied_move
        lower_bound = spot - implied_move
        
        # Check if near boundary (reversal zone)
        distance_to_upper = abs(spot - upper_bound)
        distance_to_lower = abs(spot - lower_bound)
        
        if distance_to_upper < implied_move * 0.1:
            zone = "NEAR_UPPER_BOUND"
            reversal_probability = 0.7
        elif distance_to_lower < implied_move * 0.1:
            zone = "NEAR_LOWER_BOUND"
            reversal_probability = 0.7
        else:
            zone = "WITHIN_RANGE"
            reversal_probability = 0.3
        
        return {
            "implied_move": round(implied_move, 1),
            "upper_bound": round(upper_bound, 1),
            "lower_bound": round(lower_bound, 1),
            "zone": zone,
            "reversal_probability": reversal_probability,
            "straddle_price": round(straddle_price, 1)
        }
    
    def calculate_net_greeks(self, chain_df: pd.DataFrame, spot: float) -> Dict:
        """
        [ADVANCED] Net Greeks Flow - Aggregate Delta/Vega positioning
        
        Returns net delta and vega exposure
        """
        if chain_df.empty:
            return {"net_delta": 0.0, "net_vega": 0.0, "bias": "NEUTRAL"}
        
        # Simple Delta approximation (for ATM strikes)
        # Call Delta ≈ 0.5 at ATM, Put Delta ≈ -0.5 at ATM
        # Adjust based on moneyness
        
        net_delta = 0.0
        net_vega = 0.0
        
        for _, row in chain_df.iterrows():
            strike = row['strike']
            call_oi = row.get('call_oi', 0)
            put_oi = row.get('put_oi', 0)
            
            # Distance from spot
            dist = strike - spot
            
            # Approximate Delta (simplified Black-Scholes)
            if abs(dist) < 300:  # Only ATM matters
                # Call Delta increases as strike < spot
                call_delta = 0.5 + (spot - strike) / 1000
                call_delta = max(0.1, min(0.9, call_delta))
                
                # Put Delta = Call Delta - 1
                put_delta = call_delta - 1
                
                # Net Delta contribution
                net_delta += (call_oi * call_delta) + (put_oi * put_delta)
                
                # Vega is same for calls and puts (simplified)
                vega = 0.3  # Constant approximation
                net_vega += (call_oi + put_oi) * vega
        
        # Normalize
        net_delta = net_delta / 100000  # Scale down
        
        # Determine bias
        if net_delta > 0.5:
            bias = "BULLISH_POSITIONING"
        elif net_delta < -0.5:
            bias = "BEARISH_POSITIONING"
        else:
            bias = "NEUTRAL"
        
        return {
            "net_delta": round(net_delta, 2),
            "net_vega": round(net_vega, 0),
            "bias": bias
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
