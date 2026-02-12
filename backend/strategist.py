import pandas as pd
import pandas_ta as ta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging
from models_v3 import Regime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class RegimeConfig:
    """Configuration for regime detection thresholds [v9.7.0 Institutional]"""
    # Trend thresholds
    adx_trending_threshold: float = 25.0
    adx_momentum_threshold: float = 35.0
    
    # Sideways Quality Tiers (v2.0)
    adx_sideways_strong: float = 25.0    # Upper bound for range
    adx_sideways_weak: float = 20.0      # Lower bound for range
    adx_chop_zone: float = 15.0          # Absolute chop
    
    # ATR Compression
    atr_compression_multiplier: float = 0.001
    volatility_shock_atr_multiple: float = 2.0
    velocity_shock_sigma: float = 3.0
    
    # Breadth
    breadth_bullish_threshold: int = 25
    breadth_veto_threshold: int = 15
    
    # Asymmetric Confirmation
    regime_confirmation_trending: int = 3
    regime_confirmation_sideways: int = 5  # [v15.3.14] Increased from 1 to prevent flip-flop flicker
    
    min_bars_required: int = 30

class MarketStrategist:
    """
    Classifies Market Regime and determines strategy state. [Upgrade v9.7.0]
    Features:
    - Multi-tier Sideways Detection (Strong/Normal/Weak)
    - Asymmetric Confirmation (Fast scaling into ranges)
    """
    
    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self.regime_history: List[Regime] = []
        
    def _check_volatility_shock(self, df: pd.DataFrame) -> bool:
        """Detects sudden expansion or price velocity collapse."""
        if len(df) < 20: return False
        
        # 1. ATR Expansion
        atr = df.ta.atr(length=14)
        if atr is not None and len(atr) > 1:
            curr_range = df['high'].iloc[-1] - df['low'].iloc[-1]
            if curr_range > self.config.volatility_shock_atr_multiple * atr.iloc[-2]:
                return True
                
        # 2. Velocity Shock
        velocity = df['close'].diff(3)
        if len(velocity) > 20:
            vel_std = velocity.rolling(20).std().iloc[-2]
            if vel_std > 0 and abs(velocity.iloc[-1] - velocity.rolling(20).mean().iloc[-2]) / vel_std > self.config.velocity_shock_sigma:
                return True
        return False

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        indicators = {'adx': 25.0, 'atr': 0.0, 'price_mean': df['close'].mean() if len(df) > 0 else 0.0}
        adx_df = df.ta.adx(length=14)
        if adx_df is not None and 'ADX_14' in adx_df.columns:
            indicators['adx'] = adx_df['ADX_14'].iloc[-1]
        atr_s = df.ta.atr(length=14)
        if atr_s is not None and len(atr_s) > 0:
            indicators['atr'] = atr_s.iloc[-1]
        return indicators

    def classify_regime(self, df: pd.DataFrame, breadth: Optional[Dict] = None) -> Regime:
        """Multi-tier Classification with Asymmetric Confirmation."""
        if df is None or len(df) < self.config.min_bars_required:
            return Regime.UNCERTAIN
            
        last_regime = self.regime_history[-1] if self.regime_history else Regime.UNCERTAIN
        if last_regime == Regime.TRENDING and self._check_volatility_shock(df):
            self.regime_history.append(Regime.UNCERTAIN)
            return Regime.UNCERTAIN

        inds = self._calculate_indicators(df)
        adx, atr, p_mean = inds['adx'], inds['atr'], inds['price_mean']
        
        # 1. Determine Raw Regime Target
        raw_target = Regime.UNCERTAIN
        if adx > self.config.adx_trending_threshold:
            raw_target = Regime.TRENDING
        elif self.config.adx_sideways_weak <= adx < self.config.adx_sideways_strong:
            # Quality Tiering
            if atr < (p_mean * self.config.atr_compression_multiplier):
                raw_target = Regime.SIDEWAYS_STRONG
            else:
                raw_target = Regime.SIDEWAYS_NORMAL
        elif adx < self.config.adx_sideways_weak:
            raw_target = Regime.SIDEWAYS_WEAK

        # 2. Breadth Oversight
        raw_target = self._assess_breadth(breadth, raw_target, last_regime)
        
        # 3. Asymmetric Confirmation Logic
        self.regime_history.append(raw_target)
        if len(self.regime_history) > 10: self.regime_history = self.regime_history[-10:]
        
        # Confirmation length depends on the target
        is_sideways = "SIDEWAYS" in raw_target.value
        conf_len = self.config.regime_confirmation_sideways if is_sideways else self.config.regime_confirmation_trending
        
        recent = self.regime_history[-conf_len:]
        if len(recent) >= conf_len and all(r == raw_target for r in recent):
            if raw_target != last_regime:
                logger.info(f"STRATEGIST: Regime confirmed: {last_regime.value} -> {raw_target.value}")
            return raw_target
            
        return last_regime if last_regime != Regime.UNCERTAIN else Regime.UNCERTAIN

    def _assess_breadth(self, breadth: Optional[Dict], raw: Regime, last: Regime) -> Regime:
        if not breadth or raw != Regime.TRENDING: return raw
        adv, dec = breadth.get("advances", 50), breadth.get("declines", 50)
        if adv + dec == 0: return raw
        if adv < self.config.breadth_veto_threshold: return Regime.UNCERTAIN
        if last != Regime.TRENDING and not (adv > dec and adv > self.config.breadth_bullish_threshold):
            return Regime.UNCERTAIN
        return raw

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

    def is_trap(self, df: pd.DataFrame, market_data: Any) -> Tuple[bool, str]:
        """
        Detects Institutional Traps (Price/Momentum Divergence).
        [v2.0.0] High-Conviction Veto Gate.
        """
        if len(df) < 20: return False, "STABILIZING"
        
        # 1. RSI-Price Trap (Bull Trap)
        # Price is high but RSI is collapsing
        rsi = df.ta.rsi(length=14)
        if rsi is not None and len(rsi) > 5:
            curr_rsi = rsi.iloc[-1]
            prev_rsi = rsi.iloc[-5]
            price_delta = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]
            
            # Rising Price + Falling RSI = Bull Trap
            if price_delta > 0.005 and curr_rsi < prev_rsi - 10:
                return True, "BULL_TRAP: Momentum Exhaustion"
            
            # Falling Price + Rising RSI = Bear Trap
            if price_delta < -0.005 and curr_rsi > prev_rsi + 10:
                return True, "BEAR_TRAP: Stealth Accumulation"
                
        # 2. Volume Trap
        # Price breakout on much lower volume than average
        if 'volume' in df.columns:
            avg_vol = df['volume'].rolling(20).mean().iloc[-2]
            curr_vol = df['volume'].iloc[-1]
            if curr_vol < 0.5 * avg_vol and abs(df['close'].iloc[-1] - df['open'].iloc[-1]) > (df['high'].mean() * 0.002):
                return True, "LOW_VOLUME_TRAP"
                
        return False, "STABLE"

    def get_macro_bias(self, df_macro: pd.DataFrame) -> float:
        """
        Calculates the trend bias on a higher timeframe.
        Returns: 1.0 (Bullish), -1.0 (Bearish), 0.0 (Neutral)
        """
        if df_macro is None or len(df_macro) < 50:
            return 0.0
            
        # Calculate EMAs
        ema20 = df_macro.ta.ema(length=20)
        ema50 = df_macro.ta.ema(length=50)
        
        if ema20 is None or ema50 is None or len(ema20) == 0 or len(ema50) == 0:
            return 0.0
            
        curr_price = df_macro['close'].iloc[-1]
        e20 = ema20.iloc[-1]
        e50 = ema50.iloc[-1]
        
        if pd.isna(curr_price) or pd.isna(e20) or pd.isna(e50):
            return 0.0
        
        if curr_price > e20 > e50:
            return 1.0
        elif curr_price < e20 < e50:
            return -1.0
        else:
            return 0.0

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
