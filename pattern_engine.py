import pandas as pd
import pandas_ta as ta
from typing import List, Dict

class PatternEngine:
    """
    Detects classic chart patterns and candlestick formations.
    Used as an additional confirmation layer for accuracy.
    """
    def __init__(self):
        self.confirmed_patterns = []

    def detect_candlesticks(self, df: pd.DataFrame) -> List[str]:
        """
        Detects primary candlestick formations.
        """
        if len(df) < 3: return []
        
        patterns = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Bullish Engulfing
        if last.close > prev.open and last.open < prev.close and prev.close < prev.open:
            patterns.append("BULLISH_ENGULFING")
            
        # Hammer
        body = abs(last.close - last.open)
        lower_shadow = min(last.open, last.close) - last.low
        if lower_shadow > (2 * body) and (last.high - max(last.open, last.close)) < body:
            patterns.append("HAMMER")
            
        return patterns

    def detect_structural(self, df: pd.DataFrame) -> List[str]:
        """
        Detects Support/Resistance retests and Breakout patterns.
        """
        patterns = []
        if len(df) < 50: return []
        
        # 1. Simple VWAP Breakout logic
        vwap = df.ta.vwap()
        if vwap is not None and len(vwap) > 1:
            if df.close.iloc[-1] > vwap.iloc[-1] and df.close.iloc[-2] <= vwap.iloc[-2]:
                patterns.append("VWAP_CROSSOVER")
            
        # 2. RSI Divergence (Momentum)
        rsi = df.ta.rsi(length=14)
        if rsi is not None and len(rsi) > 20:
            # Check last 20 candles for divergence
            curr_price = df.close.iloc[-1]
            prev_price_peak = df.close.iloc[-20:-1].max()
            curr_rsi = rsi.iloc[-1]
            prev_rsi_peak = rsi.iloc[-20:-1].max()
            
            if curr_price > prev_price_peak and curr_rsi < prev_rsi_peak:
                patterns.append("BEARISH_DIVERGENCE")
            elif curr_price < df.close.iloc[-20:-1].min() and curr_rsi > rsi.iloc[-20:-1].min():
                patterns.append("BULLISH_DIVERGENCE")

        # 3. Institutional Order Blocks
        if 'volume' in df.columns:
            vol_mean = df.volume.rolling(20).mean()
            for i in range(-5, -1): 
                if df.volume.iloc[i] > vol_mean.iloc[i] * 2:
                    range_sq = abs(df.close.iloc[i] - df.open.iloc[i])
                    if range_sq > (df.high.iloc[i] - df.low.iloc[i]) * 0.7:
                        patterns.append("ORDER_BLOCK_DETECTED")
                        break

        # 4. Central Pivot Range (CPR)
        # Note: In a real setup, we use the previous session's OHLC.
        # Here we approximate from the current history (assuming multi-day)
        if len(df) > 100:
            # Simple approximation of prev day
            prev_day = df.iloc[-100:-50] 
            ph, pl, pc = prev_day.high.max(), prev_day.low.min(), prev_day.close.iloc[-1]
            pivot = (ph + pl + pc) / 3
            bc = (ph + pl) / 2
            tc = (pivot - bc) + pivot
            
            curr_price = df.close.iloc[-1]
            if abs(curr_price - pivot) < (pivot * 0.001):
                patterns.append("CPR_RETEST")
            elif curr_price > max(tc, bc) and df.close.iloc[-2] <= max(tc, bc):
                patterns.append("CPR_BREAKOUT")

        # 5. Bollinger Squeeze
        bbands = df.ta.bbands(length=20, std=2)
        if bbands is not None and 'BBU_20_2.0' in bbands.columns:
            bandwidth = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0']
            if bandwidth.iloc[-1] < bandwidth.rolling(100).min().iloc[-1] * 1.1:
                patterns.append("VOLATILITY_SQUEEZE")

        # 6. Geometric Analysis (S/R and Trendlines)
        if len(df) > 50:
            # Find recent High/Low Fractals
            recent_peaks = df.high.rolling(5, center=True).apply(lambda x: x[2] == max(x), raw=True)
            recent_valleys = df.low.rolling(5, center=True).apply(lambda x: x[2] == min(x), raw=True)
            
            peaks = df.high[recent_peaks == 1].tail(3)
            valleys = df.low[recent_valleys == 1].tail(3)
            
            curr_price = df.close.iloc[-1]
            
            # Horizontal S/R
            for p in peaks:
                if abs(curr_price - p) < (p * 0.0005): 
                    patterns.append("HORIZONTAL_RESISTANCE_RETEST")
            
            # Trendline Breakout (Dynamic)
            if len(peaks) >= 2:
                # If last 2 peaks are declining (Bearish Trendline)
                if peaks.iloc[-1] < peaks.iloc[-2]:
                    # Check for breakout above the trendline slope
                    slope = (peaks.iloc[-1] - peaks.iloc[-2]) / 20 # Approximation
                    predicted_tl = peaks.iloc[-1] + slope
                    if curr_price > predicted_tl:
                        # Strong Close Validation (Marubozu check)
                        body = abs(df.close.iloc[-1] - df.open.iloc[-1])
                        total_range = df.high.iloc[-1] - df.low.iloc[-1]
                        if body > total_range * 0.8:
                            patterns.append("STRONG_TRENDLINE_BREAKOUT")

        return patterns

    def detect_liquidity_sweeps(self, df: pd.DataFrame) -> List[str]:
        """
        [v8.8] Detects Swing Failure Patterns (SFP).
        A high-conviction institutional 'stop-run' pattern.
        """
        if len(df) < 30: return []
        
        patterns = []
        last = df.iloc[-1]
        
        # 1. Bullish SFP (Sweep of a recent low)
        recent_low = df.low.iloc[-25:-1].min()
        if last.low < recent_low and last.close > recent_low:
            # Price spiked below low but closed back above
            patterns.append("LIQUIDITY_SWEEP_BULLISH")
            
        # 2. Bearish SFP (Sweep of a recent high)
        recent_high = df.high.iloc[-25:-1].max()
        if last.high > recent_high and last.close < recent_high:
            # Price spiked above high but closed back below
            patterns.append("LIQUIDITY_SWEEP_BEARISH")
            
        return patterns

    def detect_macro_zones(self, df_macro: pd.DataFrame) -> List[float]:
        """
        Scans a large timeframe (e.g. 1h for 30 days) to find 
        significant historical reversal points (Institutional Zones).
        """
        if len(df_macro) < 100:
            return []
            
        # Use fractals on the macro timeframe
        peaks = df_macro.high.rolling(21, center=True).apply(lambda x: x[10] == max(x), raw=True)
        valleys = df_macro.low.rolling(21, center=True).apply(lambda x: x[10] == min(x), raw=True)
        
        reversal_points = list(df_macro.high[peaks == 1]) + list(df_macro.low[valleys == 1])
        
        # Round to nearest 10 for clustering
        clustered = [round(p, -1) for p in reversal_points]
        
        # Keep only levels that have more than 1 reversal (strong zones)
        final_zones = []
        for level in set(clustered):
            if clustered.count(level) >= 2:
                final_zones.append(level)
                
        return sorted(final_zones)

    def get_signal_confirmation(self, df: pd.DataFrame, macro_bias: str = "NEUTRAL", macro_zones: List[float] = []) -> Dict:
        """
        Returns confirmation score and detected patterns.
        Now includes Macro Zone (Big Chart) confluence.
        """
        csticks = self.detect_candlesticks(df)
        structs = self.detect_structural(df)
        all_patterns = csticks + structs
        
        # Volume check: pattern is stronger if volume is above 20-period average
        vol_ma = df.volume.rolling(20).mean().iloc[-1] if 'volume' in df.columns else 0
        current_vol = df.volume.iloc[-1] if 'volume' in df.columns else 0
        vol_boost = 1.2 if current_vol > vol_ma else 1.0
        
        # Phase 30: Institutional Liquidity Sweep (SFP)
        sweeps = self.detect_liquidity_sweeps(df)
        all_patterns += sweeps
        sweep_boost = 1.0
        if sweeps:
            sweep_boost = 1.5
            
        # MTF Alignment Boost
        mtf_boost = 1.0
        if "BULLISH_ENGULFING" in all_patterns or "HAMMER" in all_patterns or "VWAP_CROSSOVER" in all_patterns or "LIQUIDITY_SWEEP_BULLISH" in all_patterns:
            if macro_bias == "BULLISH": mtf_boost = 1.3
            elif macro_bias == "BEARISH": mtf_boost = 0.5 

        # Phase 13: Macro Zone (Institutional S/R) Confluence
        zone_boost = 1.0
        curr_price = df.close.iloc[-1]
        for zone in macro_zones:
            if abs(curr_price - zone) < (zone * 0.001): # 0.1% buffer
                zone_boost = 1.4
                all_patterns.append("HISTORIC_ZONE_ALIGNMENT")
                break

        score = (len(csticks) * 0.2 + len(structs) * 0.4 + len(sweeps) * 0.5) * vol_boost * mtf_boost * zone_boost * sweep_boost
        
        return {
            "score": min(score, 1.0),
            "patterns": all_patterns,
            "volume_confirmed": current_vol > vol_ma,
            "mtf_aligned": mtf_boost >= 1.0,
            "historic_confluence": zone_boost > 1.0
        }

if __name__ == "__main__":
    # Mock data test
    data = {
        'open': [100, 110, 95, 105],
        'close': [105, 95, 110, 115],
        'high': [106, 111, 112, 116],
        'low': [99, 94, 94, 104]
    }
    df = pd.DataFrame(data)
    engine = PatternEngine()
    print(f"Patterns: {engine.detect_candlesticks(df)}")
