import pandas as pd
import pandas_ta as ta
from typing import List
from models import Regime

class MarketStrategist:
    """
    Classifies Market Regime and determines the strategy state.
    Prioritizes Confirmation Over Early Entry.
    """
    def __init__(self, adx_threshold: int = 25, volatility_compression: float = 1.0):
        self.adx_threshold = adx_threshold
        self.volatility_compression = volatility_compression
        self.regime_history: List[Regime] = []
        
    def _check_volatility_shock(self, df: pd.DataFrame) -> bool:
        """
        Detects sudden expansion or price velocity collapse.
        Returns True if a shock is detected (Aggressive Exit Trigger).
        """
        if len(df) < 20: return False
        
        # 1. ATR Expansion Shock
        atr = df.ta.atr(length=14)
        if atr is not None and len(atr) > 1:
            # If current bar range is > 2x average ATR, it's a shock
            curr_range = df.high.iloc[-1] - df.low.iloc[-1]
            if curr_range > 2.0 * atr.iloc[-2]:
                return True
                
        # 2. Price Velocity Shock (3-Sigma break)
        velocity = df.close.diff(3) # 3-period velocity
        if len(velocity) > 20:
            std = velocity.rolling(20).std().iloc[-2]
            mean = velocity.rolling(20).mean().iloc[-2]
            curr_vel = velocity.iloc[-1]
            
            # If current velocity is > 3 standard deviations from mean
            if abs(curr_vel - mean) > 3.0 * std:
                return True
                
        return False

    def classify_regime(self, df: pd.DataFrame, breadth: dict = None) -> Regime:
        """
        Uses ADX, ATR, and BREADTH for Regime Classification.
        Implements Non-Price Orthogonality (Fix Audit v8 Failure #6).
        """
        if len(df) < 20:
            return Regime.UNCERTAIN
            
        # 0. Volatility Shock Exit
        last_regime = self.regime_history[-1] if self.regime_history else Regime.UNCERTAIN
        if last_regime == Regime.TRENDING and self._check_volatility_shock(df):
            self.regime_history.append(Regime.UNCERTAIN)
            return Regime.UNCERTAIN

        # Calculate Indicators
        adx = df.ta.adx()
        current_adx = adx['ADX_14'].iloc[-1] if adx is not None else 25.0
        atr = df.ta.atr()
        current_atr = atr.iloc[-1] if atr is not None else 0.0
        
        # 1. Raw Price Logic
        raw_regime = Regime.UNCERTAIN
        if current_adx > self.adx_threshold:
            raw_regime = Regime.TRENDING
        elif current_adx < 20 and current_atr < (df['close'].mean() * 0.001): 
            raw_regime = Regime.SIDEWAYS
            
        # 2. Balanced Breadth Logic (Fix Audit v8.1 #3)
        # Entry: Advisory (Veto-only)
        # Continuation: Mandatory
        if breadth:
            adv, dec = breadth.get("advances", 50), breadth.get("declines", 0)
            is_breadth_bullish = adv > dec and adv > 25
            
            if raw_regime == Regime.TRENDING:
                if last_regime != Regime.TRENDING: # Entry Phase
                    if not is_breadth_bullish and adv < 15: # Extreme weakness vetoes entry
                        raw_regime = Regime.UNCERTAIN
                else: # Continuation Phase
                    if not is_breadth_bullish: # Mandatory agreement for staying in trend
                        raw_regime = Regime.UNCERTAIN
            
        # 3. Transitions
        if last_regime == Regime.TRENDING and raw_regime != Regime.TRENDING:
            self.regime_history.append(Regime.UNCERTAIN)
            return Regime.UNCERTAIN
            
        self.regime_history.append(raw_regime)
        if len(self.regime_history) > 3:
            if all(r == raw_regime for r in self.regime_history[-3:]):
                return raw_regime
            return Regime.UNCERTAIN
            
        return raw_regime

    def is_momentum_dominant(self, df: pd.DataFrame) -> bool:
        """
        Checks if momentum is strong enough to override Mean Reversion (Max Pain).
        (Fix Audit v8 Failure #5)
        """
        if len(df) < 30: return False
        adx = df.ta.adx()
        if adx is None: return False
        
        curr_adx = adx['ADX_14'].iloc[-1]
        adx_slope = adx['ADX_14'].diff(5).iloc[-1]
        
        # Momentum Dominance Threshold: ADX > 35 and rising
        return curr_adx > 35 and adx_slope > 0

    def get_macro_bias(self, df_macro: pd.DataFrame) -> str:
        """
        Calculates the trend bias on a higher timeframe (e.g. 1h).
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        if len(df_macro) < 50:
            return "NEUTRAL"
            
        # Use simple EMA 20/50 crossover or relationship
        ema20 = df_macro.ta.ema(length=20)
        ema50 = df_macro.ta.ema(length=50)
        
        if ema20 is None or ema50 is None:
            return "NEUTRAL"
            
        curr_price = df_macro.close.iloc[-1]
        e20 = ema20.iloc[-1]
        e50 = ema50.iloc[-1]
        
        if curr_price > e20 > e50:
            return "BULLISH"
        elif curr_price < e20 < e50:
            return "BEARISH"
        else:
            return "NEUTRAL"

if __name__ == "__main__":
    # Mock DF
    data = {
        'high': [25010]*30,
        'low': [24990]*30,
        'close': [25000]*30
    }
    df = pd.DataFrame(data)
    strategist = MarketStrategist()
    print(f"Regime: {strategist.classify_regime(df)}")
