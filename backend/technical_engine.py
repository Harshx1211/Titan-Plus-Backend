
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("technical_engine")

class TechnicalEngine:
    """
    Titan Plus - Precision Technical Analysis Engine (Phase 5)
    Calculates Pin-Point Support/Resistance, Fibonacci Levels, and OI Walls.
    """
    
    def __init__(self):
        pass

    def calculate_precision_levels(self, ohlcv_df: pd.DataFrame, current_price: float, oi_data: Dict = None) -> Dict:
        """
        Master function to compute all critical levels.
        Returns: { 'support': [], 'resistance': [], 'fibs': [], 'walls': [] }
        """
        if ohlcv_df is None or ohlcv_df.empty:
            return {}

        levels = {
            'fractals': self._find_fractal_zones(ohlcv_df),
            'fibs': self._calculate_fibonacci(ohlcv_df),
            'oi_walls': self._find_oi_walls(oi_data) if (oi_data is not None and len(oi_data) > 0) else [],
            'pivots': self._calculate_pivot_points(ohlcv_df),
            'order_blocks': self._find_order_blocks(ohlcv_df)
        }
        
        # Merge and scoring logic can be added here
        # For now, return raw components
        return levels

    def _find_fractal_zones(self, df: pd.DataFrame, window: int = 3) -> List[Dict]:
        """
        Identify Fractal Highs and Lows (Williams Fractals).
        A fractal high is a high surrounded by 2 lower highs on each side.
        """
        zones = []
        try:
            # We need at least 2*window + 1 candles
            if len(df) < window * 2 + 1: return []
            
            for i in range(window, len(df) - window):
                # Fractal High
                is_high = True
                curr_high = df['high'].iloc[i]
                for j in range(1, window + 1):
                    if df['high'].iloc[i-j] >= curr_high or df['high'].iloc[i+j] >= curr_high:
                        is_high = False
                        break
                
                if is_high:
                    zones.append({'price': curr_high, 'type': 'RESISTANCE', 'strength': 'FRACTAL'})
                
                # Fractal Low
                is_low = True
                curr_low = df['low'].iloc[i]
                for j in range(1, window + 1):
                    if df['low'].iloc[i-j] <= curr_low or df['low'].iloc[i+j] <= curr_low:
                        is_low = False
                        break
                
                if is_low:
                    zones.append({'price': curr_low, 'type': 'SUPPORT', 'strength': 'FRACTAL'})
                    
            # Return only the most recent/relevant ones (e.g., last 5)
            return zones[-10:]
        except Exception as e:
            logger.error(f"Fractal Calc Failed: {str(e)}", exc_info=True)
            return []

    def _calculate_fibonacci(self, df: pd.DataFrame) -> Dict:
        """
        Auto-Draw Fibonacci Retracements based on recent major Trend.
        """
        try:
            if df.empty: return {}
            
            # Dynamic Lookback: Use 50 or full length if shorter
            lookback = min(len(df), 50)
            if lookback < 2: return {}
            
            recent_high = df['high'].tail(lookback).max()
            recent_low = df['low'].tail(lookback).min()
            
            # Determine trend direction (Last close vs Start of window)
            start_price = df['close'].iloc[-lookback]
            end_price = df['close'].iloc[-1]
            trend_up = end_price > start_price
            
            diff = recent_high - recent_low
            if diff == 0: return {}
            
            levels = {}
            if trend_up:
                # Retracements from Low(0%) to High(100%)
                # Normal Fib: Retracing DOWN from High
                levels['0.236'] = recent_high - (diff * 0.236)
                levels['0.382'] = recent_high - (diff * 0.382)
                levels['0.5']   = recent_high - (diff * 0.5)
                levels['0.618'] = recent_high - (diff * 0.618)
            else:
                # Retracements from High(0%) to Low(100%)
                # Normal Fib: Retracing UP from Low
                levels['0.236'] = recent_low + (diff * 0.236)
                levels['0.382'] = recent_low + (diff * 0.382)
                levels['0.5']   = recent_low + (diff * 0.5)
                levels['0.618'] = recent_low + (diff * 0.618)
                
            return levels
        except Exception as e:
            logger.error(f"Fib Calc Failed: {e}", exc_info=True)
            return {}

    def _find_oi_walls(self, oi_data: Dict) -> List[Dict]:
        """
        Identify Strikes with massive Call/Put Open Interest.
        These act as strong Support (Put OI) and Resistance (Call OI).
        """
        walls = []
        try:
            if oi_data is None or len(oi_data) == 0: return []
            
            # Example OI Data Structure: { 'calls': {22000: 50000, ...}, 'puts': {22000: 40000, ...} }
            
            # Use 'calls' and 'puts' keys correctly
            calls = oi_data.get('calls', {})
            puts = oi_data.get('puts', {})
            
            # Find Top 3 Call Strikes (Resistance)
            if calls:
                sorted_calls = sorted(calls.items(), key=lambda x: x[1], reverse=True)[:3]
                for strike, oi in sorted_calls:
                     walls.append({'price': float(strike), 'type': 'RESISTANCE', 'strength': 'OI_WALL', 'oi': oi})
            
            # Find Top 3 Put Strikes (Support)
            if puts:
                sorted_puts = sorted(puts.items(), key=lambda x: x[1], reverse=True)[:3]
                for strike, oi in sorted_puts:
                     walls.append({'price': float(strike), 'type': 'SUPPORT', 'strength': 'OI_WALL', 'oi': oi})
                     
            return walls
        except Exception as e:
            logger.error(f"OI Wall Calc Failed: {e}")
            return []
            
    def _find_order_blocks(self, df: pd.DataFrame, atr_period: int = 14) -> List[Dict]:
        """
        [Phase 5.5] Expert Order Block Detection:
        1. Consolidation: 5 candles with body < 0.5 * ATR.
        2. Breakout: High momentum candle (> 2x Volume or Large Body).
        3. Zone: 50% Retracement level of the consolidation block.
        """
        obs = []
        try:
            if len(df) < 50: return []
            
            # Helper: Calculate ATR manually if not present
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(atr_period).mean()
            
            # Helper: Volume SMA
            vol_sma = df['volume'].rolling(20).mean()

            for i in range(20, len(df)-1):
                # Check Breakout (Candle i)
                is_breakout_up = df['close'].iloc[i] > df['open'].iloc[i] and df['volume'].iloc[i] > (1.5 * vol_sma.iloc[i])
                is_breakout_down = df['close'].iloc[i] < df['open'].iloc[i] and df['volume'].iloc[i] > (1.5 * vol_sma.iloc[i])
                
                if not (is_breakout_up or is_breakout_down): continue
                
                # Check Consolidation (Previous 5 candles: i-5 to i-1)
                is_consolidating = True
                consolidation_high = -1.0
                consolidation_low = 1000000.0
                
                for j in range(1, 6):
                    body = abs(df['close'].iloc[i-j] - df['open'].iloc[i-j])
                    if body > (0.6 * atr.iloc[i]): # Slightly relaxed from 0.5
                        is_consolidating = False
                        break
                    
                    consolidation_high = max(consolidation_high, df['high'].iloc[i-j])
                    consolidation_low = min(consolidation_low, df['low'].iloc[i-j])
                
                if is_consolidating:
                    # Found an OB!
                    # OTE (Optimal Trade Entry) = 50% of the block
                    ote_level = (consolidation_high + consolidation_low) / 2
                    
                    if is_breakout_up:
                        obs.append({
                            'price': ote_level, 
                            'type': 'SUPPORT', 
                            'strength': 'ORDER_BLOCK',
                            'zone_top': consolidation_high,
                            'zone_bottom': consolidation_low
                        })
                    else:
                        obs.append({
                            'price': ote_level, 
                            'type': 'RESISTANCE', 
                            'strength': 'ORDER_BLOCK',
                            'zone_top': consolidation_high,
                            'zone_bottom': consolidation_low
                        })
                        
            # Return last 3 observed OBs
            return obs[-3:]
            
        except Exception as e:
            logger.error(f"OB Calc Failed: {str(e)}", exc_info=True)
            return []

    def _calculate_pivot_points(self, df: pd.DataFrame) -> Dict:
        """
        Calculate Standard Daily Pivot Points (P, R1, S1, R2, S2).
        Uses the *previous* day's High, Low, Close.
        Assuming daily data or resampling is passed, but for intraday we often take High/Low of prev day.
        Here we approximate with last closed candle if it represents a day, or pass prev day explicitly.
        For safety, we'll calculate based on the LAST candle in the DF assuming it's the prev period.
        """
        try:
            last_candle = df.iloc[-1] # This is current. We need prev.
            if len(df) > 1:
                prev = df.iloc[-2]
                H, L, C = prev['high'], prev['low'], prev['close']
                
                P = (H + L + C) / 3
                R1 = (2 * P) - L
                S1 = (2 * P) - H
                R2 = P + (H - L)
                S2 = P - (H - L)
                
                return {'P': P, 'R1': R1, 'S1': S1, 'R2': R2, 'S2': S2}
            return {}
        except Exception as e:
            return {}

