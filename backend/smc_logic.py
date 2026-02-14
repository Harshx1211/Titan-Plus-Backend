import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')

class TrendBias(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

@dataclass
class OrderBlock:
    """Represents a validated institutional order block"""
    type: str  # BULLISH_OB or BEARISH_OB
    price_top: float
    price_bottom: float
    volume: float
    strength: float  # 0-100 score
    timestamp: int
    timeframe: str
    touched: bool = False
    
@dataclass
class LiquidityZone:
    """Represents a liquidity pool or sweep zone"""
    type: str  # EQUAL_HIGHS, EQUAL_LOWS, SWEEP
    price: float
    strength: float
    candle_index: int

class InstitutionalSMC:
    """
    Advanced Smart Money Concepts Engine
    Implements institutional-grade price action analysis
    """
    
    def __init__(self):
        self.order_blocks: List[OrderBlock] = []
        self.liquidity_zones: List[LiquidityZone] = []
        
    def analyze_market_structure(self, df: pd.DataFrame, timeframe: str = '15m') -> Dict:
        """
        Complete market structure analysis
        Returns comprehensive SMC intelligence
        """
        if len(df) < 100:
            return self._empty_analysis()
            
        analysis = {
            'timeframe': timeframe,
            'trend_bias': self._determine_trend_bias(df),
            'order_blocks': self._find_premium_order_blocks(df, timeframe),
            'liquidity_zones': self._map_liquidity(df),
            'structure_breaks': self._detect_structure_breaks(df),
            'fair_value_gaps': self._identify_fvg_premium(df),
            'traditional_sr': self._find_traditional_sr(df),
            'chart_patterns': self._detect_chart_patterns(df),
            'market_regime': self._classify_regime(df),
            'confluence_score': 0.0
        }
        
        # Calculate confluence score
        analysis['confluence_score'] = self._calculate_confluence(analysis)
        
        return analysis
    
    def _determine_trend_bias(self, df: pd.DataFrame) -> TrendBias:
        """
        Multi-layer trend determination using structure and moving averages
        """
        # EMA ribbon analysis
        ema_20 = df['close'].ewm(span=20).mean()
        ema_50 = df['close'].ewm(span=50).mean()
        ema_200 = df['close'].ewm(span=200).mean()
        
        current_price = df['close'].iloc[-1]
        
        # Higher timeframe bias
        if current_price > ema_200.iloc[-1] and ema_20.iloc[-1] > ema_50.iloc[-1]:
            return TrendBias.BULLISH
        elif current_price < ema_200.iloc[-1] and ema_20.iloc[-1] < ema_50.iloc[-1]:
            return TrendBias.BEARISH
        else:
            return TrendBias.NEUTRAL
    
    def _find_premium_order_blocks(self, df: pd.DataFrame, timeframe: str) -> List[OrderBlock]:
        """
        Identifies high-probability order blocks with volume validation
        Only returns OBs that meet institutional criteria
        """
        order_blocks = []
        lookback = min(50, len(df) - 10)
        
        # Calculate volume profile
        avg_volume = df['volume'].rolling(20).mean()
        
        for i in range(len(df) - lookback, len(df) - 3):
            candle = df.iloc[i]
            next_candle = df.iloc[i + 1]
            volume_ratio = candle['volume'] / avg_volume.iloc[i] if avg_volume.iloc[i] > 0 else 0
            
            # Bullish OB: Last bearish candle before strong bullish move
            if (candle['close'] < candle['open'] and  # Bearish candle
                next_candle['close'] > candle['high'] and  # Strong break above
                volume_ratio > 1.5):  # Above-average volume
                
                strength = min(100, volume_ratio * 30 + 
                             ((next_candle['close'] - candle['high']) / candle['high'] * 1000))
                
                ob = OrderBlock(
                    type="BULLISH_OB",
                    price_top=candle['high'],
                    price_bottom=candle['low'],
                    volume=candle['volume'],
                    strength=strength,
                    timestamp=i,
                    timeframe=timeframe
                )
                order_blocks.append(ob)
            
            # Bearish OB: Last bullish candle before strong bearish move
            elif (candle['close'] > candle['open'] and  # Bullish candle
                  next_candle['close'] < candle['low'] and  # Strong break below
                  volume_ratio > 1.5):
                
                strength = min(100, volume_ratio * 30 + 
                             ((candle['low'] - next_candle['close']) / candle['low'] * 1000))
                
                ob = OrderBlock(
                    type="BEARISH_OB",
                    price_top=candle['high'],
                    price_bottom=candle['low'],
                    volume=candle['volume'],
                    strength=strength,
                    timestamp=i,
                    timeframe=timeframe
                )
                order_blocks.append(ob)
        
        # Return only the strongest OBs
        order_blocks.sort(key=lambda x: x.strength, reverse=True)
        return order_blocks[:5]  # Top 5 strongest
    
    def _map_liquidity(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """
        Maps liquidity zones: equal highs/lows and potential sweep areas
        """
        liquidity_zones = []
        tolerance = 0.002  # 0.2% price tolerance for "equal" levels
        
        # Find equal highs (liquidity above)
        highs = df['high'].values
        for i in range(len(df) - 20, len(df) - 2):
            for j in range(i + 1, min(i + 10, len(df))):
                if abs(highs[i] - highs[j]) / highs[i] < tolerance:
                    strength = 50 + (df['volume'].iloc[i] / df['volume'].mean() * 20)
                    liquidity_zones.append(LiquidityZone(
                        type="EQUAL_HIGHS",
                        price=highs[i],
                        strength=min(100, strength),
                        candle_index=i
                    ))
                    break
        
        # Find equal lows (liquidity below)
        lows = df['low'].values
        for i in range(len(df) - 20, len(df) - 2):
            for j in range(i + 1, min(i + 10, len(df))):
                if abs(lows[i] - lows[j]) / lows[i] < tolerance:
                    strength = 50 + (df['volume'].iloc[i] / df['volume'].mean() * 20)
                    liquidity_zones.append(LiquidityZone(
                        type="EQUAL_LOWS",
                        price=lows[i],
                        strength=min(100, strength),
                        candle_index=i
                    ))
                    break
        
        return liquidity_zones
    
    def _detect_structure_breaks(self, df: pd.DataFrame) -> Dict:
        """
        Detects BOS (Break of Structure) and CHoCH (Change of Character)
        with proper swing point validation
        """
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(5, len(df) - 5):
            # Swing high: higher than 5 candles on each side
            if all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, 6)) and \
               all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, 6)):
                swing_highs.append((i, df['high'].iloc[i]))
            
            # Swing low: lower than 5 candles on each side
            if all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, 6)) and \
               all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, 6)):
                swing_lows.append((i, df['low'].iloc[i]))
        
        current_price = df['close'].iloc[-1]
        
        # Check for BOS or CHoCH
        bos_type = None
        choch_type = None
        
        if swing_highs:
            last_swing_high = swing_highs[-1][1]
            if current_price > last_swing_high:
                bos_type = "BOS_BULLISH"
        
        if swing_lows:
            last_swing_low = swing_lows[-1][1]
            if current_price < last_swing_low:
                bos_type = "BOS_BEARISH"
        
        # CHoCH detection (trend reversal)
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if swing_highs[-1][1] < swing_highs[-2][1] and swing_lows[-1][1] < swing_lows[-2][1]:
                choch_type = "CHOCH_BEARISH"
            elif swing_highs[-1][1] > swing_highs[-2][1] and swing_lows[-1][1] > swing_lows[-2][1]:
                choch_type = "CHOCH_BULLISH"
        
        return {
            'bos': bos_type,
            'choch': choch_type,
            'swing_highs': swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs,
            'swing_lows': swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        }
    
    def _identify_fvg_premium(self, df: pd.DataFrame) -> List[Dict]:
        """
        Identifies Fair Value Gaps with institutional validation
        Only returns FVGs that haven't been filled
        """
        fvgs = []
        
        for i in range(len(df) - 10, len(df) - 2):
            # Bullish FVG: Gap between candle i high and candle i+2 low
            if df['low'].iloc[i+2] > df['high'].iloc[i]:
                gap_size = df['low'].iloc[i+2] - df['high'].iloc[i]
                gap_percent = (gap_size / df['high'].iloc[i]) * 100
                
                # Only significant gaps
                if gap_percent > 0.1:
                    fvgs.append({
                        'type': 'BULLISH_FVG',
                        'top': df['low'].iloc[i+2],
                        'bottom': df['high'].iloc[i],
                        'size': gap_size,
                        'index': i,
                        'filled': self._is_fvg_filled(df, i+2, df['high'].iloc[i], df['low'].iloc[i+2])
                    })
            
            # Bearish FVG
            elif df['high'].iloc[i+2] < df['low'].iloc[i]:
                gap_size = df['low'].iloc[i] - df['high'].iloc[i+2]
                gap_percent = (gap_size / df['low'].iloc[i]) * 100
                
                if gap_percent > 0.1:
                    fvgs.append({
                        'type': 'BEARISH_FVG',
                        'top': df['low'].iloc[i],
                        'bottom': df['high'].iloc[i+2],
                        'size': gap_size,
                        'index': i,
                        'filled': self._is_fvg_filled(df, i+2, df['high'].iloc[i+2], df['low'].iloc[i])
                    })
        
        # Return only unfilled FVGs
        return [fvg for fvg in fvgs if not fvg['filled']]
    
    def _is_fvg_filled(self, df: pd.DataFrame, start_idx: int, bottom: float, top: float) -> bool:
        """Check if FVG has been filled by subsequent price action"""
        for i in range(start_idx, len(df)):
            if df['low'].iloc[i] <= bottom or df['high'].iloc[i] >= top:
                return True
        return False
    
    def _classify_regime(self, df: pd.DataFrame) -> str:
        """
        Classifies market regime: TRENDING, RANGING, VOLATILE
        """
        # ATR for volatility
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        atr = ranges.max(axis=1).rolling(14).mean()
        
        current_atr = atr.iloc[-1]
        avg_atr = atr.mean()
        
        # ADX for trend strength
        adx = self._calculate_adx(df)
        
        if adx > 25 and current_atr < avg_atr * 1.5:
            return "TRENDING"
        elif adx < 20:
            return "RANGING"
        else:
            return "VOLATILE"
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([high - low, 
                       abs(high - close.shift()), 
                       abs(low - close.shift())], axis=1).max(axis=1)
        
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
    
    def _calculate_confluence(self, analysis: Dict) -> float:
        """
        Calculates overall confluence score (0-100)
        Higher score = higher probability setup
        """
        score = 0.0
        
        # Trend alignment (30 points)
        if analysis['trend_bias'] != TrendBias.NEUTRAL:
            score += 30
        
        # Order block presence (25 points)
        if analysis['order_blocks']:
            ob_strength = sum(ob.strength for ob in analysis['order_blocks'][:2]) / 2
            score += min(25, ob_strength / 4)
        
        # Structure breaks (20 points)
        if analysis['structure_breaks']['bos']:
            score += 20
        elif analysis['structure_breaks']['choch']:
            score += 10
        
        # Liquidity zones (15 points)
        if analysis['liquidity_zones']:
            liq_strength = sum(lz.strength for lz in analysis['liquidity_zones'][:2]) / 2
            score += min(15, liq_strength / 6.67)
        
        # FVG presence (10 points)
        if analysis['fair_value_gaps']:
            score += 10
        
        return min(100, score)
    
    def _find_traditional_sr(self, df: pd.DataFrame) -> List[Dict]:
        """
        Institutional-grade Support & Resistance detection
        Uses peak finding and density clustering (KDE-style logic)
        🔧 IMPROVED: Adaptive clustering threshold based on ATR
        """
        prices = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # 1. Find all significant pivots using signal processing
        peaks, _ = find_peaks(highs, distance=5, prominence=df['high'].std() * 0.1)
        troughs, _ = find_peaks(-lows, distance=5, prominence=df['low'].std() * 0.1)
        
        pivots = []
        for p in peaks: pivots.append({'price': highs[p], 'type': 'RESISTANCE'})
        for t in troughs: pivots.append({'price': lows[t], 'type': 'SUPPORT'})
        
        if not pivots: return []
        
        # 🔧 IMPROVED: Calculate adaptive threshold based on ATR
        # This makes clustering work better for both high and low-priced assets
        atr = self._calculate_atr_simple(df)
        avg_price = df['close'].mean()
        atr_pct = (atr / avg_price) if avg_price > 0 else 0.01
        
        # Threshold should be between 0.3% and 1.0% based on volatility
        base_threshold_pct = max(0.003, min(0.01, atr_pct))
        
        # 2. Cluster pivots that are close to each other
        pivots.sort(key=lambda x: x['price'])
        clustered_levels = []
        
        if pivots:
            curr_cluster = [pivots[0]]
            # Adaptive threshold for first pivot
            threshold = pivots[0]['price'] * base_threshold_pct
            
            for i in range(1, len(pivots)):
                if pivots[i]['price'] - curr_cluster[-1]['price'] < threshold:
                    curr_cluster.append(pivots[i])
                else:
                    # Finalize cluster
                    avg_price_lvl = np.mean([p['price'] for p in curr_cluster])
                    touches = len(curr_cluster)
                    # A strong level has multiple touches
                    if touches >= 2:
                        level_type = "SUPPORT" if sum(1 for p in curr_cluster if p['type'] == 'SUPPORT') > \
                                              sum(1 for p in curr_cluster if p['type'] == 'RESISTANCE') else "RESISTANCE"
                        clustered_levels.append({
                            'price': avg_price_lvl,
                            'type': level_type,
                            'strength': min(100, touches * 20),
                            'touches': touches
                        })
                    curr_cluster = [pivots[i]]
                    # Update threshold for next pivot (adaptive)
                    threshold = pivots[i]['price'] * base_threshold_pct
            
        return sorted(clustered_levels, key=lambda x: x['strength'], reverse=True)[:5]
    
    def _calculate_atr_simple(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate simple ATR for adaptive thresholding
        """
        try:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(period).mean()
            
            return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else df['close'].mean() * 0.02
        except:
            return df['close'].mean() * 0.02  # Default to 2% of price

    def _detect_chart_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """
        Advanced Chart Pattern Recognition
        Detects: Double Top/Bottom, Triple Top/Bottom
        """
        patterns = []
        highs = df['high'].values
        lows = df['low'].values
        
        # Look for Double Top in the last 60 candles
        window = 60
        if len(df) > window:
            recent_highs = highs[-window:]
            recent_lows = lows[-window:]
            
            # Find the two highest peaks in the window
            peaks, _ = find_peaks(recent_highs, distance=10, prominence=recent_highs.std() * 0.2)
            if len(peaks) >= 2:
                # Get the two most recent prominent peaks
                p1_idx, p2_idx = peaks[-2], peaks[-1]
                p1_val, p2_val = recent_highs[p1_idx], recent_highs[p2_idx]
                
                # Check for "equality" (Double Top)
                if abs(p1_val - p2_val) / p1_val < 0.003:
                    patterns.append({'type': 'DOUBLE_TOP', 'strength': 85})
                # Check for "descending" peaks (Triple or complex) - simplistic
                elif len(peaks) >= 3:
                    p3_idx = peaks[-3]
                    p3_val = recent_highs[p3_idx]
                    if abs(p1_val - p2_val) / p1_val < 0.005 and abs(p2_val - p3_val) / p2_val < 0.005:
                        patterns.append({'type': 'TRIPLE_TOP', 'strength': 95})

            # Look for Double Bottom
            troughs, _ = find_peaks(-recent_lows, distance=10, prominence=recent_lows.std() * 0.2)
            if len(troughs) >= 2:
                t1_idx, t2_idx = troughs[-2], troughs[-1]
                t1_val, t2_val = recent_lows[t1_idx], recent_lows[t2_idx]
                
                if abs(t1_val - t2_val) / t1_val < 0.003:
                    patterns.append({'type': 'DOUBLE_BOTTOM', 'strength': 85})
        
        return patterns

    def _empty_analysis(self) -> Dict:
        """Returns empty analysis structure"""
        return {
            'timeframe': 'unknown',
            'trend_bias': TrendBias.NEUTRAL,
            'order_blocks': [],
            'liquidity_zones': [],
            'structure_breaks': {'bos': None, 'choch': None},
            'fair_value_gaps': [],
            'traditional_sr': [],
            'chart_patterns': [],
            'market_regime': 'UNKNOWN',
            'confluence_score': 0.0
        }

# Singleton instance
smc_engine = InstitutionalSMC()
