"""
Titan Plus: Advanced Smart Money Concepts (SMC) Engine
=======================================================
Institutional-grade price action analysis including:
- Order Blocks (OB)
- Fair Value Gaps (FVG)
- Liquidity Sweeps
- Imbalances & Breaker Blocks
- Market Structure Analysis

Version: 15.3.1 (Phase 3)
Author: Titan Plus Development Team
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smc_engine")


@dataclass
class OrderBlock:
    """Represents an institutional Order Block"""
    timestamp: datetime
    price_high: float
    price_low: float
    price_mid: float
    direction: str  # 'BULLISH' or 'BEARISH'
    strength: float  # 0.0-1.0
    volume: float
    tested: bool = False
    confidence: float = 0.0
    
    def __repr__(self):
        return f"OB({self.direction}, {self.price_mid:.2f}, str={self.strength:.2f})"


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap (imbalance)"""
    timestamp: datetime
    gap_high: float
    gap_low: float
    gap_size: float
    direction: str  # 'BULLISH' or 'BEARISH'
    filled: bool = False
    fill_percentage: float = 0.0
    
    def __repr__(self):
        return f"FVG({self.direction}, {self.gap_low:.2f}-{self.gap_high:.2f})"


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event"""
    timestamp: datetime
    swept_level: float
    sweep_type: str  # 'LONG_LIQUIDITY' or 'SHORT_LIQUIDITY'
    reversal: bool
    strength: float
    
    def __repr__(self):
        return f"Sweep({self.sweep_type}, {self.swept_level:.2f})"


class GrandmasterSMCEngine:
    """
    The Institutional Logic Core
    
    Analyzes price action using Smart Money Concepts to detect:
    1. Order Blocks: Where institutions placed large orders
    2. Fair Value Gaps: Inefficiencies in price action
    3. Liquidity Sweeps: Stop hunts and accumulation/distribution
    4. Market Structure: Higher highs, lower lows, breaks of structure
    """
    
    def __init__(self):
        self.order_blocks: List[OrderBlock] = []
        self.fvgs: List[FairValueGap] = []
        self.liquidity_sweeps: List[LiquiditySweep] = []
        
        # Thresholds
        self.min_ob_volume_percentile = 75  # Order blocks need high volume
        self.min_fvg_size_pct = 0.3  # Minimum 0.3% gap
        self.liquidity_sweep_threshold = 0.2  # % beyond swing point
        
        # Market structure tracking
        self.swing_highs: List[Tuple[datetime, float]] = []
        self.swing_lows: List[Tuple[datetime, float]] = []
        self.market_structure = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Main analysis function
        
        Args:
            df: OHLCV DataFrame with DatetimeIndex
        
        Returns:
            Dictionary with SMC signals and scores
        """
        if df.empty or len(df) < 20:
            return self._empty_analysis()
        
        # Ensure proper column names
        df = df.copy()
        if not all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume']):
            logger.warning("SMC_ENGINE: Missing required OHLCV columns")
            return self._empty_analysis()
        
        # Run all detection modules
        self._detect_order_blocks(df)
        self._detect_fair_value_gaps(df)
        self._detect_liquidity_sweeps(df)
        self._analyze_market_structure(df)
        
        # [v11.0.0] Signed Confluence Model
        confluence_bullish, confluence_bearish = self._calculate_directional_confluence(df)
        net_confluence = confluence_bullish - confluence_bearish
        
        return {
            'order_blocks': self._serialize_order_blocks(),
            'fair_value_gaps': self._serialize_fvgs(),
            'liquidity_sweeps': self._serialize_sweeps(),
            'market_structure': self.market_structure,
            'confluence_score': net_confluence,
            'confluence_bullish': confluence_bullish,
            'confluence_bearish': confluence_bearish,
            'signals': self._generate_signals(df),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _get_atr(self, df: pd.DataFrame, idx: int) -> float:
        """Helper to get ATR at index"""
        atr_window = df.iloc[max(0, idx-14):idx]
        if atr_window.empty: return 0.0
        return (atr_window['high'] - atr_window['low']).mean()

    def _detect_order_blocks(self, df: pd.DataFrame):
        """
        Detect Order Blocks (OB)
        
        An Order Block is formed when:
        1. Strong directional move (engulfing candle or series of candles)
        2. High volume relative to recent average
        3. Followed by retracement or consolidation
        """
        self.order_blocks = []
        
        if len(df) < 5:
            return
        
        # Calculate volume percentile
        volume_threshold = df['volume'].quantile(self.min_ob_volume_percentile / 100)
        
        for i in range(3, len(df) - 2):
            current = df.iloc[i]
            prev = df.iloc[i-1]
            next_candle = df.iloc[i+1]
            
            # Institutional Deterministic Order Block Detection
            # Bullish_OB: Vol Spike + Break of High + Strong Close
            atr = self._get_atr(df, i)
            high_vol = current['volume'] > volume_threshold
            bos_high = current['close'] > prev['high']
            strong_close = (current['close'] - current['low']) > 0.7 * (current['high'] - current['low'])
            
            # Bearish_OB: Vol Spike + Break of Low + Strong Close
            bos_low = current['close'] < prev['low']
            strong_close_bear = (current['high'] - current['close']) > 0.7 * (current['high'] - current['low'])

            if high_vol and bos_high and strong_close:
                
                strength = self._calculate_ob_strength(df, i, 'BULLISH')
                
                ob = OrderBlock(
                    timestamp=current.name if hasattr(current.name, 'to_pydatetime') else datetime.now(timezone.utc),
                    price_high=current['high'],
                    price_low=current['low'],
                    price_mid=(current['high'] + current['low']) / 2,
                    direction='BULLISH',
                    strength=strength,
                    volume=current['volume'],
                    confidence=min(1.0, strength * (current['volume'] / volume_threshold))
                )
                self.order_blocks.append(ob)
            
            elif high_vol and bos_low and strong_close_bear:
                
                strength = self._calculate_ob_strength(df, i, 'BEARISH')
                
                ob = OrderBlock(
                    timestamp=current.name if hasattr(current.name, 'to_pydatetime') else datetime.now(timezone.utc),
                    price_high=current['high'],
                    price_low=current['low'],
                    price_mid=(current['high'] + current['low']) / 2,
                    direction='BEARISH',
                    strength=strength,
                    volume=current['volume'],
                    confidence=min(1.0, strength * (current['volume'] / volume_threshold))
                )
                self.order_blocks.append(ob)
        
        # Keep only most recent and strongest order blocks
        self.order_blocks = sorted(self.order_blocks, key=lambda x: x.confidence, reverse=True)[:10]
        
        if self.order_blocks:
            logger.info(f"SMC_ENGINE: Detected {len(self.order_blocks)} Order Blocks")
    
    def _calculate_ob_strength(self, df: pd.DataFrame, idx: int, direction: str) -> float:
        """
        Calculate Order Block strength based on:
        - Candle size relative to ATR
        - Volume spike
        - Follow-through
        """
        current = df.iloc[idx]
        
        # ATR approximation (last 14 candles)
        atr_window = df.iloc[max(0, idx-14):idx]
        atr = (atr_window['high'] - atr_window['low']).mean()
        
        candle_size = abs(current['close'] - current['open'])
        size_strength = min(1.0, candle_size / (atr * 1.5)) if atr > 0 else 0.5
        
        # Volume strength
        avg_volume = df['volume'].iloc[max(0, idx-20):idx].mean()
        volume_strength = min(1.0, current['volume'] / (avg_volume * 1.5)) if avg_volume > 0 else 0.5
        
        # Combine
        strength = (size_strength + volume_strength) / 2
        
        return strength
    
    def _detect_fair_value_gaps(self, df: pd.DataFrame):
        """
        Detect Fair Value Gaps (FVG)
        
        A FVG occurs when there's a gap between candles indicating inefficiency:
        - Bullish FVG: Gap between candle[i-1].high and candle[i+1].low
        - Bearish FVG: Gap between candle[i-1].low and candle[i+1].high
        """
        self.fvgs = []
        
        if len(df) < 3:
            return
        
        current_price = df['close'].iloc[-1]
        
        for i in range(1, len(df) - 1):
            prev_candle = df.iloc[i-1]
            current_candle = df.iloc[i]
            next_candle = df.iloc[i+1]
            
            # Bullish FVG (gap up)
            if next_candle['low'] > prev_candle['high']:
                gap_low = prev_candle['high']
                gap_high = next_candle['low']
                gap_size = gap_high - gap_low
                gap_pct = (gap_size / prev_candle['close']) * 100
                
                if gap_pct >= self.min_fvg_size_pct:
                    # Check if gap has been filled
                    filled = current_price <= gap_low
                    fill_pct = 0.0
                    if current_price < gap_high:
                        fill_pct = max(0.0, (gap_high - current_price) / gap_size * 100)
                    
                    fvg = FairValueGap(
                        timestamp=current_candle.name if hasattr(current_candle.name, 'to_pydatetime') else datetime.now(),
                        gap_high=gap_high,
                        gap_low=gap_low,
                        gap_size=gap_size,
                        direction='BULLISH',
                        filled=filled,
                        fill_percentage=fill_pct
                    )
                    self.fvgs.append(fvg)
            
            # Bearish FVG (gap down)
            elif next_candle['high'] < prev_candle['low']:
                gap_high = prev_candle['low']
                gap_low = next_candle['high']
                gap_size = gap_high - gap_low
                gap_pct = (gap_size / prev_candle['close']) * 100
                
                if gap_pct >= self.min_fvg_size_pct:
                    filled = current_price >= gap_high
                    fill_pct = 0.0
                    if current_price > gap_low:
                        fill_pct = max(0.0, (current_price - gap_low) / gap_size * 100)
                    
                    fvg = FairValueGap(
                        timestamp=current_candle.name if hasattr(current_candle.name, 'to_pydatetime') else datetime.now(),
                        gap_high=gap_high,
                        gap_low=gap_low,
                        gap_size=gap_size,
                        direction='BEARISH',
                        filled=filled,
                        fill_percentage=fill_pct
                    )
                    self.fvgs.append(fvg)
        
        # Keep only unfilled or partially filled gaps
        self.fvgs = [fvg for fvg in self.fvgs if not fvg.filled or fvg.fill_percentage < 90]
        self.fvgs = self.fvgs[-20:]  # Keep last 20
        
        if self.fvgs:
            logger.info(f"SMC_ENGINE: Detected {len(self.fvgs)} Fair Value Gaps")
    
    def _detect_liquidity_sweeps(self, df: pd.DataFrame):
        """
        Detect Liquidity Sweeps (Deterministic)
        """
        self.liquidity_sweeps = []
        
        if len(df) < 20:
            return
        
        # Identify swing points
        self._identify_swings(df)

        # Deterministic Sweep: Price breaks swing level but closes within it (wick sweep)
        # Check last 3 candles for a sweep of recent swings
        for swing_time, swing_high in self.swing_highs[-5:]:
            for i in range(len(df) - 3, len(df)):
                current = df.iloc[i]
                # High > swing level AND Close < swing level (wick rejection)
                if current['high'] > swing_high and current['close'] <= swing_high:
                    sweep = LiquiditySweep(
                        timestamp=current.name if hasattr(current.name, 'to_pydatetime') else datetime.now(timezone.utc),
                        swept_level=swing_high,
                        sweep_type='SHORT_LIQUIDITY',
                        reversal=True, # Wick rejection is a reversal sign
                        strength=(current['high'] - swing_high) / swing_high * 100
                    )
                    self.liquidity_sweeps.append(sweep)
        
        for swing_time, swing_low in self.swing_lows[-5:]:
            for i in range(len(df) - 3, len(df)):
                current = df.iloc[i]
                # Low < swing level AND Close > swing level
                if current['low'] < swing_low and current['close'] >= swing_low:
                    sweep = LiquiditySweep(
                        timestamp=current.name if hasattr(current.name, 'to_pydatetime') else datetime.now(timezone.utc),
                        swept_level=swing_low,
                        sweep_type='LONG_LIQUIDITY',
                        reversal=True,
                        strength=(swing_low - current['low']) / swing_low * 100
                    )
                    self.liquidity_sweeps.append(sweep)
        
        if self.liquidity_sweeps:
            logger.info(f"SMC_ENGINE: Detected {len(self.liquidity_sweeps)} Deterministic Liquidity Sweeps")
    
    def _identify_swings(self, df: pd.DataFrame, window: int = 5):
        """Identify swing highs and lows"""
        self.swing_highs = []
        self.swing_lows = []
        
        for i in range(window, len(df) - window):
            # Swing High: Current candle high is highest in window
            if df['high'].iloc[i] == df['high'].iloc[i-window:i+window+1].max():
                self.swing_highs.append((df.index[i], df['high'].iloc[i]))
            
            # Swing Low: Current candle low is lowest in window
            if df['low'].iloc[i] == df['low'].iloc[i-window:i+window+1].min():
                self.swing_lows.append((df.index[i], df['low'].iloc[i]))
    
    def _analyze_market_structure(self, df: pd.DataFrame):
        """
        Analyze market structure (trending vs ranging)
        
        Structure types:
        - BULLISH: Series of higher highs and higher lows
        - BEARISH: Series of lower highs and lower lows
        - NEUTRAL: Choppy, no clear structure
        """
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            self.market_structure = "NEUTRAL"
            return
        
        # Check last 3 swings
        recent_highs = [h for t, h in self.swing_highs[-3:]]
        recent_lows = [l for t, l in self.swing_lows[-3:]]
        
        # Bullish structure: Higher highs and higher lows
        higher_highs = all(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
        higher_lows = all(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        # Bearish structure: Lower highs and lower lows
        lower_highs = all(recent_highs[i] < recent_highs[i-1] for i in range(1, len(recent_highs)))
        lower_lows = all(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        if higher_highs and higher_lows:
            self.market_structure = "BULLISH"
        elif lower_highs and lower_lows:
            self.market_structure = "BEARISH"
        else:
            self.market_structure = "NEUTRAL"
    
    def _calculate_directional_confluence(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        [v11.0.0] Signed Confluence Math.
        Separates institutional pressure into Bullish and Bearish components.
        """
        bull_score = 0.0
        bear_score = 0.0
        current_price = df['close'].iloc[-1]
        
        # 1. Order Block confluence
        for ob in self.order_blocks[:3]:
            # Check price proximity to OB
            in_zone = (current_price >= ob.price_low and current_price <= ob.price_high)
            if ob.direction == 'BULLISH':
                if in_zone: bull_score += 15 * ob.confidence
                else: bull_score += 5 * ob.confidence # Nearby support
            else:
                if in_zone: bear_score += 15 * ob.confidence
                else: bear_score += 5 * ob.confidence # Nearby resistance
        
        # 2. FVG confluence
        for fvg in self.fvgs:
            if not fvg.filled:
                if fvg.direction == 'BULLISH' and current_price >= fvg.gap_low:
                    bull_score += 10
                elif fvg.direction == 'BEARISH' and current_price <= fvg.gap_high:
                    bear_score += 10
        
        # 3. Liquidity sweep confluence
        for sweep in self.liquidity_sweeps:
            if sweep.reversal:
                if sweep.sweep_type == 'LONG_LIQUIDITY': # Swept lows (Bullish reversal)
                    bull_score += 20
                else: # Swept highs (Bearish reversal)
                    bear_score += 20
        
        # 4. Market structure alignment
        if self.market_structure == "BULLISH":
            bull_score += 25
        elif self.market_structure == "BEARISH":
            bear_score += 25
            
        return min(100.0, bull_score), min(100.0, bear_score)
    
    def _generate_signals(self, df: pd.DataFrame) -> Dict:
        """Generate actionable SMC signals"""
        current_price = df['close'].iloc[-1]
        
        signals = {
            'bullish_ob_active': False,
            'bearish_ob_active': False,
            'unfilled_bullish_fvg': False,
            'unfilled_bearish_fvg': False,
            'recent_sweep': False,
            'structure_aligned': False
        }
        
        # Check for active order blocks near current price
        for ob in self.order_blocks:
            price_in_ob = ob.price_low <= current_price <= ob.price_high
            if ob.direction == 'BULLISH' and price_in_ob:
                signals['bullish_ob_active'] = True
            elif ob.direction == 'BEARISH' and price_in_ob:
                signals['bearish_ob_active'] = True
        
        # Check for unfilled FVGs
        for fvg in self.fvgs:
            if not fvg.filled:
                if fvg.direction == 'BULLISH' and current_price > fvg.gap_low:
                    signals['unfilled_bullish_fvg'] = True
                elif fvg.direction == 'BEARISH' and current_price < fvg.gap_high:
                    signals['unfilled_bearish_fvg'] = True
        
        # Check for recent sweeps
        if self.liquidity_sweeps:
            signals['recent_sweep'] = True
        
        # Structure alignment
        if self.market_structure in ['BULLISH', 'BEARISH']:
            signals['structure_aligned'] = True
        
        return signals
    
    def _serialize_order_blocks(self) -> List[Dict]:
        """Convert order blocks to JSON-serializable format"""
        return [{
            'timestamp': ob.timestamp.isoformat() if hasattr(ob.timestamp, 'isoformat') else str(ob.timestamp),
            'price_high': ob.price_high,
            'price_low': ob.price_low,
            'price_mid': ob.price_mid,
            'direction': ob.direction,
            'strength': ob.strength,
            'volume': ob.volume,
            'confidence': ob.confidence
        } for ob in self.order_blocks]
    
    def _serialize_fvgs(self) -> List[Dict]:
        """Convert FVGs to JSON-serializable format"""
        return [{
            'timestamp': fvg.timestamp.isoformat() if hasattr(fvg.timestamp, 'isoformat') else str(fvg.timestamp),
            'gap_high': fvg.gap_high,
            'gap_low': fvg.gap_low,
            'gap_size': fvg.gap_size,
            'direction': fvg.direction,
            'filled': fvg.filled,
            'fill_percentage': fvg.fill_percentage
        } for fvg in self.fvgs]
    
    def _serialize_sweeps(self) -> List[Dict]:
        """Convert sweeps to JSON-serializable format"""
        return [{
            'timestamp': sweep.timestamp.isoformat() if hasattr(sweep.timestamp, 'isoformat') else str(sweep.timestamp),
            'swept_level': sweep.swept_level,
            'sweep_type': sweep.sweep_type,
            'reversal': sweep.reversal,
            'strength': sweep.strength
        } for sweep in self.liquidity_sweeps]
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis result"""
        return {
            'order_blocks': [],
            'fair_value_gaps': [],
            'liquidity_sweeps': [],
            'market_structure': 'NEUTRAL',
            'confluence_score': 0.0,
            'signals': {
                'bullish_ob_active': False,
                'bearish_ob_active': False,
                'unfilled_bullish_fvg': False,
                'unfilled_bearish_fvg': False,
                'recent_sweep': False,
                'structure_aligned': False
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


if __name__ == "__main__":
    # Test SMC Engine
    logger.info("Testing Grandmaster SMC Engine...")
    
    # Create sample OHLCV data
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=100, freq='5min')
    np.random.seed(42)
    
    base_price = 25000
    noise = np.random.randn(100) * 50
    trend = np.linspace(0, 200, 100)
    
    df = pd.DataFrame({
        'open': base_price + trend + noise,
        'high': base_price + trend + noise + np.abs(np.random.randn(100) * 30),
        'low': base_price + trend + noise - np.abs(np.random.randn(100) * 30),
        'close': base_price + trend + noise + np.random.randn(100) * 20,
        'volume': np.random.randint(100000, 1000000, 100)
    }, index=dates)
    
    # Ensure OHLC logic
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    # Run analysis
    engine = GrandmasterSMCEngine()
    result = engine.analyze(df)
    
    print("\n=== SMC Analysis Results ===")
    print(f"Market Structure: {result['market_structure']}")
    print(f"Confluence Score: {result['confluence_score']:.2f}")
    print(f"Order Blocks: {len(result['order_blocks'])}")
    print(f"Fair Value Gaps: {len(result['fair_value_gaps'])}")
    print(f"Liquidity Sweeps: {len(result['liquidity_sweeps'])}")
    print(f"\nSignals: {result['signals']}")
    
    print("\nSMC Engine test complete!")
