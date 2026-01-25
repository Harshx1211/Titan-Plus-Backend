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
        
    def classify_regime(self, df: pd.DataFrame) -> Regime:
        """
        Uses ADX for Trend Strength and ATR for Volatility.
        """
        if len(df) < 20:
            return Regime.UNCERTAIN
            
        # Calculate ADX
        adx = df.ta.adx()
        if adx is None or 'ADX_14' not in adx.columns:
            return Regime.UNCERTAIN
            
        current_adx = adx['ADX_14'].iloc[-1]
        
        # Calculate ATR for Volatility
        atr = df.ta.atr()
        if atr is None or len(atr) == 0:
            return Regime.UNCERTAIN
            
        current_atr = atr.iloc[-1]
        
        # Logic for Regime
        if current_adx > self.adx_threshold:
            new_regime = Regime.TRENDING
        elif current_adx < 20 and current_atr < (df['close'].mean() * 0.001): # Arbitrary compression logic
            new_regime = Regime.SIDEWAYS
        else:
            new_regime = Regime.UNCERTAIN
            
        # Confirmation/Stickiness Logic
        self.regime_history.append(new_regime)
        if len(self.regime_history) > 3:
            # Only change regime if last 3 readings agree
            if all(r == new_regime for r in self.regime_history[-3:]):
                return new_regime
            return Regime.UNCERTAIN # Transition zone
            
        return new_regime

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
