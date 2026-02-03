"""
SMC Analyzer: Smart Money Concepts
Detects institutional price action patterns including:
- Break of Structure (BOS) and Change of Character (ChoCh)
- Order Blocks (unmitigated demand/supply zones)
- Fair Value Gaps (FVG)
- Liquidity grabs
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np


class SMCAnalyzer:
    """
    Analyzes price action using Smart Money Concepts methodology.
    
    All calculations are vectorized for performance.
    """
    
    def __init__(
        self, 
        swing_length: int = 5,
        fvg_threshold: float = 0.001,  # 0.1% minimum gap
        ob_lookback: int = 20
    ):
        """
        Initialize SMC Analyzer.
        
        Args:
            swing_length: Number of candles to define swing highs/lows
            fvg_threshold: Minimum percentage gap to qualify as FVG
            ob_lookback: Number of candles to look back for order blocks
        """
        self.swing_length = swing_length
        self.fvg_threshold = fvg_threshold
        self.ob_lookback = ob_lookback
    
    def analyze(
        self, 
        ohlcv_df: pd.DataFrame,
        current_price: Optional[float] = None
    ) -> Dict:
        """
        Main analysis function.
        
        Args:
            ohlcv_df: DataFrame with columns ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            current_price: Current market price (if None, uses last close)
        
        Returns:
            Dictionary containing:
                - is_bos: bool (Break of Structure detected)
                - is_choch: bool (Change of Character detected)
                - zones: List of active order blocks
                - liquidity_grab: bool (Recent liquidity sweep detected)
                - fvg_open: List of unfilled Fair Value Gaps
        """
        if len(ohlcv_df) < self.swing_length * 2:
            return self._empty_result()
        
        df = ohlcv_df.copy()
        
        if current_price is None:
            current_price = df['close'].iloc[-1]
        
        # Detect swing highs and lows
        swings = self._detect_swings(df)
        
        # Check for BOS and ChoCh
        bos, choch = self._detect_structure_breaks(df, swings, current_price)
        
        # Identify order blocks
        order_blocks = self._identify_order_blocks(df, swings)
        
        # Detect Fair Value Gaps
        fvg_list = self._detect_fvg(df, current_price)
        
        # Check for liquidity grabs
        liquidity_grab = self._detect_liquidity_grab(df, swings)
        
        return {
            'is_bos': bos,
            'is_choch': choch,
            'zones': order_blocks,
            'liquidity_grab': liquidity_grab,
            'fvg_open': fvg_list,
            'trend': self._determine_trend(swings)
        }
    
    def _detect_swings(self, df: pd.DataFrame) -> Dict:
        """
        Detect swing highs and lows using vectorized operations.
        
        Returns:
            Dictionary with 'highs' and 'lows' as lists of (index, price) tuples
        """
        high = df['high'].values
        low = df['low'].values
        n = len(df)
        
        swing_highs = []
        swing_lows = []
        
        # Vectorized swing detection
        for i in range(self.swing_length, n - self.swing_length):
            # Check if current high is highest in window
            window_high = high[i - self.swing_length:i + self.swing_length + 1]
            if high[i] == np.max(window_high):
                swing_highs.append((i, high[i]))
            
            # Check if current low is lowest in window
            window_low = low[i - self.swing_length:i + self.swing_length + 1]
            if low[i] == np.min(window_low):
                swing_lows.append((i, low[i]))
        
        return {
            'highs': swing_highs,
            'lows': swing_lows
        }
    
    def _detect_structure_breaks(
        self, 
        df: pd.DataFrame, 
        swings: Dict,
        current_price: float
    ) -> Tuple[bool, bool]:
        """
        Detect Break of Structure (BOS) and Change of Character (ChoCh).
        
        BOS: Price breaks beyond previous swing high/low in trend direction
        ChoCh: Price breaks counter-trend swing point (potential reversal)
        
        Returns:
            (is_bos, is_choch) tuple
        """
        if len(swings['highs']) < 2 or len(swings['lows']) < 2:
            return False, False
        
        recent_highs = swings['highs'][-3:]
        recent_lows = swings['lows'][-3:]
        
        # Determine current trend
        # Uptrend: Higher highs and higher lows
        higher_highs = recent_highs[-1][1] > recent_highs[-2][1]
        higher_lows = recent_lows[-1][1] > recent_lows[-2][1]
        
        # Downtrend: Lower highs and lower lows
        lower_highs = recent_highs[-1][1] < recent_highs[-2][1]
        lower_lows = recent_lows[-1][1] < recent_lows[-2][1]
        
        # BOS Detection
        is_bos = False
        if higher_highs and higher_lows:  # Uptrend
            # BOS if current price breaks above last swing high
            if current_price > recent_highs[-1][1]:
                is_bos = True
        elif lower_highs and lower_lows:  # Downtrend
            # BOS if current price breaks below last swing low
            if current_price < recent_lows[-1][1]:
                is_bos = True
        
        # ChoCh Detection (trend reversal)
        is_choch = False
        if higher_highs and higher_lows:  # Was uptrend
            # ChoCh if breaks below recent swing low
            if current_price < recent_lows[-1][1]:
                is_choch = True
        elif lower_highs and lower_lows:  # Was downtrend
            # ChoCh if breaks above recent swing high
            if current_price > recent_highs[-1][1]:
                is_choch = True
        
        return is_bos, is_choch
    
    def _identify_order_blocks(
        self, 
        df: pd.DataFrame, 
        swings: Dict
    ) -> List[Dict]:
        """
        Identify unmitigated order blocks.
        
        Returns:
            List of order blocks with structure:
            {'price_range': (low, high), 'type': 'bull/bear', 'strength': float}
        """
        order_blocks = []
        
        if len(df) < self.ob_lookback:
            return order_blocks
        
        df_recent = df.tail(self.ob_lookback).reset_index(drop=True)
        
        # Calculate 20-period Volume MA for validation
        vol_ma = df['volume'].rolling(20).mean()
        
        for i in range(1, len(df_recent) - 1):
            curr = df_recent.iloc[i]
            next_candle = df_recent.iloc[i + 1]
            idx_full = df_recent.index[i]
            
            # Volume Validation: Move sequence must have significant volume
            # We check if the impulse candle (next one) has above-average volume
            # If original index is preserved, use it to look up MA
            # Fallback to local calculation if needed
            vol_threshold = 0
            if not vol_ma.empty:
               try:
                   vol_threshold = vol_ma.iloc[- (len(df_recent) - i)] * 1.2 # 1.2x average volume required
               except:
                   pass

            # Skip if volume is weak (institutional footprints are heavy)
            if next_candle['volume'] < vol_threshold:
                continue

            # Bullish Order Block
            if curr['close'] < curr['open']:  # Down candle
                if next_candle['close'] > next_candle['open']:  # Up candle
                    move_strength = (next_candle['high'] - curr['low']) / curr['low']
                    if move_strength > 0.002:  # 0.2% minimum move
                        subsequent_lows = df_recent.iloc[i + 1:]['low'].values
                        if len(subsequent_lows) > 0 and np.min(subsequent_lows) > curr['low']:
                            order_blocks.append({
                                'price_range': (float(curr['low']), float(curr['high'])),
                                'type': 'bull',
                                'strength': float(move_strength),
                                'age': len(df_recent) - i,
                                'volume_mult': float(next_candle['volume'] / (vol_threshold if vol_threshold > 0 else 1))
                            })
            
            # Bearish Order Block
            elif curr['close'] > curr['open']:  # Up candle
                if next_candle['close'] < next_candle['open']:  # Down candle
                    move_strength = (curr['high'] - next_candle['low']) / curr['high']
                    if move_strength > 0.002:
                        subsequent_highs = df_recent.iloc[i + 1:]['high'].values
                        if len(subsequent_highs) > 0 and np.max(subsequent_highs) < curr['high']:
                            order_blocks.append({
                                'price_range': (float(curr['low']), float(curr['high'])),
                                'type': 'bear',
                                'strength': float(move_strength),
                                'age': len(df_recent) - i,
                                'volume_mult': float(next_candle['volume'] / (vol_threshold if vol_threshold > 0 else 1))
                            })
        
        # Sort by (Strength * Volume) score
        order_blocks.sort(key=lambda x: (x['strength'] * x.get('volume_mult', 1.0), -x['age']), reverse=True)
        return order_blocks[:3]
    
    def _detect_fvg(
        self, 
        df: pd.DataFrame, 
        current_price: float
    ) -> List[Dict]:
        """
        Detect Fair Value Gaps (FVG).
        """
        fvg_list = []
        
        if len(df) < 3:
            return fvg_list
        
        df_recent = df.tail(20).reset_index(drop=True)
        
        for i in range(1, len(df_recent) - 1):
            prev_candle = df_recent.iloc[i - 1]
            next_candle = df_recent.iloc[i + 1]
            
            # Bullish FVG
            if prev_candle['high'] < next_candle['low']:
                gap_size = (next_candle['low'] - prev_candle['high']) / prev_candle['high']
                if gap_size > self.fvg_threshold:
                    if current_price < prev_candle['high'] or current_price > next_candle['low']:
                        fvg_list.append({
                            'type': 'bullish',
                            'gap_range': (float(prev_candle['high']), float(next_candle['low'])),
                            'size': float(gap_size),
                            'filled': current_price > prev_candle['high'] and current_price < next_candle['low']
                        })
            
            # Bearish FVG
            elif prev_candle['low'] > next_candle['high']:
                gap_size = (prev_candle['low'] - next_candle['high']) / next_candle['high']
                if gap_size > self.fvg_threshold:
                    if current_price > prev_candle['low'] or current_price < next_candle['high']:
                        fvg_list.append({
                            'type': 'bearish',
                            'gap_range': (float(next_candle['high']), float(prev_candle['low'])),
                            'size': float(gap_size),
                            'filled': current_price < prev_candle['low'] and current_price > next_candle['high']
                        })
        
        return [fvg for fvg in fvg_list if not fvg['filled']]
    
    def _detect_liquidity_grab(self, df: pd.DataFrame, swings: Dict) -> bool:
        """
        Detect liquidity grabs (stop hunts).
        """
        if len(df) < 5: return False
        recent_candles = df.tail(5)
        
        for i in range(len(recent_candles) - 1, max(0, len(recent_candles) - 4), -1):
            candle = recent_candles.iloc[i]
            body_size = abs(candle['close'] - candle['open'])
            lower_wick = min(candle['open'], candle['close']) - candle['low']
            upper_wick = candle['high'] - max(candle['open'], candle['close'])
            
            if lower_wick > body_size * 2 and upper_wick < body_size * 0.5:
                if swings['lows']:
                    if candle['low'] < swings['lows'][-1][1] and candle['close'] > swings['lows'][-1][1]:
                        return True
            
            if upper_wick > body_size * 2 and lower_wick < body_size * 0.5:
                if swings['highs']:
                    if candle['high'] > swings['highs'][-1][1] and candle['close'] < swings['highs'][-1][1]:
                        return True
        return False
    
    def _determine_trend(self, swings: Dict) -> str:
        """Determine overall trend."""
        if len(swings['highs']) < 2 or len(swings['lows']) < 2: return 'neutral'
        
        recent_highs = swings['highs'][-2:]
        recent_lows = swings['lows'][-2:]
        if recent_highs[-1][1] > recent_highs[-2][1] and recent_lows[-1][1] > recent_lows[-2][1]:
            return 'bullish'
        elif recent_highs[-1][1] < recent_highs[-2][1] and recent_lows[-1][1] < recent_lows[-2][1]:
            return 'bearish'
        return 'neutral'

    def _empty_result(self) -> Dict:
        return {'is_bos': False, 'is_choch': False, 'zones': [], 'liquidity_grab': False, 'fvg_open': [], 'trend': 'neutral'}
