import pandas as pd
import pandas_ta as ta
from typing import List, Optional, Dict
from dataclasses import dataclass
import logging
from models import Regime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class RegimeConfig:
    """Configuration for regime detection thresholds [v9.6.6]"""
    adx_trending_threshold: float = 25.0
    adx_sideways_threshold: float = 20.0
    adx_momentum_threshold: float = 35.0
    atr_compression_multiplier: float = 0.001
    volatility_shock_atr_multiple: float = 2.0
    velocity_shock_sigma: float = 3.0
    breadth_bullish_threshold: int = 25
    breadth_veto_threshold: int = 15
    regime_confirmation_bars: int = 3
    min_bars_required: int = 30

class MarketStrategist:
    """
    Classifies Market Regime and determines strategy state.
    Prioritizes confirmation over early entry. [Refactor v9.6.6]
    
    Features:
    - Multi-indicator regime detection (ADX, ATR, Breadth)
    - Volatility shock detection for aggressive exits
    - Regime persistence requirements (anti-whipsaw)
    - Bidirectional breadth analysis
    - Macro trend bias calculation
    """
    
    def __init__(self, config: Optional[RegimeConfig] = None, adx_threshold: int = 25, volatility_compression: float = 1.0):
        # Maintain backward compatibility with old init signature if needed
        self.config = config or RegimeConfig(
            adx_trending_threshold=float(adx_threshold),
            atr_compression_multiplier=volatility_compression * 0.001
        )
        self.regime_history: List[Regime] = []
        self._last_regime_change_bar: int = 0
        
    def _check_volatility_shock(self, df: pd.DataFrame) -> bool:
        """
        Detects sudden expansion or price velocity collapse.
        Returns True if a shock is detected (Aggressive Exit Trigger).
        """
        if len(df) < 20:
            return False
        
        # 1. ATR Expansion Shock
        atr = df.ta.atr(length=14)
        if atr is not None and len(atr) > 1:
            curr_range = df['high'].iloc[-1] - df['low'].iloc[-1]
            avg_atr = atr.iloc[-2]
            
            if curr_range > self.config.volatility_shock_atr_multiple * avg_atr:
                logger.warning(f"ATR Shock detected: range={curr_range:.2f}, avg_atr={avg_atr:.2f}")
                return True
                
        # 2. Price Velocity Shock (3-Sigma break)
        velocity = df['close'].diff(3)
        if len(velocity) > 20:
            vel_std = velocity.rolling(20).std().iloc[-2]
            vel_mean = velocity.rolling(20).mean().iloc[-2]
            curr_vel = velocity.iloc[-1]
            
            if pd.notna(vel_std) and vel_std > 0:
                z_score = abs(curr_vel - vel_mean) / vel_std
                if z_score > self.config.velocity_shock_sigma:
                    logger.warning(f"Velocity Shock detected: z_score={z_score:.2f}")
                    return True
                
        return False

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Centralized indicator calculation with proper error handling.
        Returns dict with all required indicators.
        """
        indicators = {
            'adx': self.config.adx_trending_threshold,  # Default fallback
            'atr': 0.0,
            'price_mean': df['close'].mean() if len(df) > 0 else 0.0
        }
        
        # Calculate ADX
        adx_df = df.ta.adx(length=14)
        if adx_df is not None and 'ADX_14' in adx_df.columns:
            adx_value = adx_df['ADX_14'].iloc[-1]
            if pd.notna(adx_value):
                indicators['adx'] = adx_value
                
        # Calculate ATR
        atr_series = df.ta.atr(length=14)
        if atr_series is not None and len(atr_series) > 0:
            atr_value = atr_series.iloc[-1]
            if pd.notna(atr_value):
                indicators['atr'] = atr_value
                
        return indicators

    def _assess_breadth(
        self, 
        breadth: Optional[Dict], 
        raw_regime: Regime, 
        last_regime: Regime
    ) -> Regime:
        """
        Bidirectional breadth analysis with entry/continuation logic.
        """
        if not breadth:
            return raw_regime
            
        adv = breadth.get("advances", 50)
        dec = breadth.get("declines", 50)
        total = adv + dec
        
        if total == 0:
            return raw_regime
            
        # Determine breadth bias
        is_breadth_bullish = adv > dec and adv > self.config.breadth_bullish_threshold
        is_breadth_bearish = dec > adv and dec > self.config.breadth_bullish_threshold
        is_breadth_extreme_weak = adv < self.config.breadth_veto_threshold
        
        if raw_regime != Regime.TRENDING:
            return raw_regime
            
        # TRENDING regime breadth rules
        is_entry_phase = last_regime != Regime.TRENDING
        
        if is_entry_phase:
            # Entry: Only veto on extreme weakness
            if is_breadth_extreme_weak and not is_breadth_bearish:
                logger.info(f"STRATEGIST: Breadth veto on entry: adv={adv}, dec={dec}")
                return Regime.UNCERTAIN
        else:
            # Continuation: Must have breadth alignment (bullish OR bearish)
            if not is_breadth_bullish and not is_breadth_bearish:
                logger.info(f"STRATEGIST: Breadth divergence on continuation: adv={adv}, dec={dec}")
                return Regime.UNCERTAIN
                
        return raw_regime

    def classify_regime(
        self, 
        df: pd.DataFrame, 
        breadth: Optional[Dict] = None
    ) -> Regime:
        """
        Uses ADX, ATR, and BREADTH for Regime Classification.
        """
        if df is None or len(df) < self.config.min_bars_required:
            return Regime.UNCERTAIN
            
        # Get last confirmed regime
        last_regime = self.regime_history[-1] if self.regime_history else Regime.UNCERTAIN
        
        # 0. Check for volatility shock (immediate exit from trending)
        if last_regime == Regime.TRENDING and self._check_volatility_shock(df):
            self.regime_history.append(Regime.UNCERTAIN)
            return Regime.UNCERTAIN

        # 1. Calculate indicators
        indicators = self._calculate_indicators(df)
        current_adx = indicators['adx']
        current_atr = indicators['atr']
        price_mean = indicators['price_mean']
        
        # 2. Raw regime classification from price-based indicators
        raw_regime = Regime.UNCERTAIN
        
        if current_adx > self.config.adx_trending_threshold:
            raw_regime = Regime.TRENDING
        elif (current_adx < self.config.adx_sideways_threshold and 
              current_atr < (price_mean * self.config.atr_compression_multiplier)):
            raw_regime = Regime.SIDEWAYS
            
        # 3. Apply breadth filter (bidirectional)
        raw_regime = self._assess_breadth(breadth, raw_regime, last_regime)
        
        # 4. Handle transitions with confirmation requirement
        if last_regime == Regime.TRENDING and raw_regime != Regime.TRENDING:
            logger.info(f"STRATEGIST: Regime transition: {last_regime.value} -> UNCERTAIN")
            self.regime_history.append(Regime.UNCERTAIN)
            return Regime.UNCERTAIN
            
        # 5. Require confirmation bars before regime change
        self.regime_history.append(raw_regime)
        
        # Keep only recent history
        if len(self.regime_history) > 10:
            self.regime_history = self.regime_history[-10:]
            
        # Check for confirmation
        confirmation_bars = min(
            self.config.regime_confirmation_bars, 
            len(self.regime_history)
        )
        
        if confirmation_bars >= self.config.regime_confirmation_bars:
            recent_regimes = self.regime_history[-confirmation_bars:]
            if all(r == raw_regime for r in recent_regimes):
                if raw_regime != last_regime:
                    logger.info(f"STRATEGIST: Regime confirmed: {last_regime.value} -> {raw_regime.value}")
                return raw_regime
            else:
                return Regime.UNCERTAIN
        else:
            return Regime.UNCERTAIN

    def is_momentum_dominant(self, df: pd.DataFrame) -> bool:
        """
        Checks if momentum is strong enough to override mean reversion.
        """
        if len(df) < self.config.min_bars_required:
            return False
            
        adx_df = df.ta.adx(length=14)
        if adx_df is None or 'ADX_14' not in adx_df.columns:
            return False
        
        curr_adx = adx_df['ADX_14'].iloc[-1]
        adx_slope = adx_df['ADX_14'].diff(5).iloc[-1]
        
        if pd.notna(curr_adx) and pd.notna(adx_slope):
            is_dominant = (curr_adx > self.config.adx_momentum_threshold and 
                          adx_slope > 0)
            if is_dominant:
                logger.info(f"STRATEGIST: Momentum dominant: ADX={curr_adx:.1f}, slope={adx_slope:.2f}")
            return is_dominant
            
        return False

    def get_macro_bias(self, df_macro: pd.DataFrame) -> str:
        """
        Calculates the trend bias on a higher timeframe.
        """
        if df_macro is None or len(df_macro) < 50:
            return "NEUTRAL"
            
        # Calculate EMAs
        ema20 = df_macro.ta.ema(length=20)
        ema50 = df_macro.ta.ema(length=50)
        
        if ema20 is None or ema50 is None or len(ema20) == 0 or len(ema50) == 0:
            return "NEUTRAL"
            
        curr_price = df_macro['close'].iloc[-1]
        e20 = ema20.iloc[-1]
        e50 = ema50.iloc[-1]
        
        if pd.isna(curr_price) or pd.isna(e20) or pd.isna(e50):
            return "NEUTRAL"
        
        if curr_price > e20 > e50:
            return "BULLISH"
        elif curr_price < e20 < e50:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def get_regime_stability(self) -> float:
        """
        Returns regime stability score (0.0 to 1.0).
        """
        if not self.regime_history:
            return 0.0
            
        current = self.regime_history[-1]
        consecutive = 1
        
        for regime in reversed(self.regime_history[:-1]):
            if regime == current:
                consecutive += 1
            else:
                break
                
        return min(1.0, consecutive / 10.0)

if __name__ == "__main__":
    # Test data
    trending_data = {
        'high': [25000 + i*10 for i in range(40)],
        'low': [24990 + i*10 for i in range(40)],
        'close': [24995 + i*10 for i in range(40)]
    }
    df_trending = pd.DataFrame(trending_data)
    strategist = MarketStrategist()
    regime = strategist.classify_regime(df_trending, breadth={'advances': 60, 'declines': 40})
    print(f"Regime: {regime.value}, Stability: {strategist.get_regime_stability():.2f}")
