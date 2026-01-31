"""
Advanced Support & Resistance Detection
Multi-timeframe, Volume Profile, Fibonacci, and Psychological Levels
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger("support_resistance")

class SupportResistanceEngine:
    """
    Comprehensive S/R detection using multiple methods
    """
    
    def __init__(self):
        self.cache = {}
        
    def find_pivot_levels(self, df: pd.DataFrame, lookback: int = 5) -> Dict:
        """
        Finds pivot-based support and resistance levels
        """
        if len(df) < lookback * 2:
            return {"supports": [], "resistances": []}
        
        supports = []
        resistances = []
        
        # Find pivot highs (resistance)
        for i in range(lookback, len(df) - lookback):
            if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
                resistances.append({
                    'level': df['high'].iloc[i],
                    'timestamp': df.index[i],
                    'type': 'PIVOT_HIGH',
                    'strength': 1.0
                })
        
        # Find pivot lows (support)
        for i in range(lookback, len(df) - lookback):
            if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
                supports.append({
                    'level': df['low'].iloc[i],
                    'timestamp': df.index[i],
                    'type': 'PIVOT_LOW',
                    'strength': 1.0
                })
        
        return {
            "supports": supports[-5:],  # Last 5 support levels
            "resistances": resistances[-5:]  # Last 5 resistance levels
        }
    
    def find_multi_timeframe_sr(self, df_dict: Dict[str, pd.DataFrame], 
                                 current_price: float) -> Dict:
        """
        Finds S/R across multiple timeframes and identifies confluence zones
        
        df_dict: {"1D": df_daily, "60m": df_60m, "15m": df_15m, "5m": df_5m}
        """
        all_levels = []
        
        timeframe_weights = {
            "1D": 3.0,
            "60m": 2.0,
            "15m": 1.5,
            "5m": 1.0
        }
        
        for tf, df in df_dict.items():
            if df is None or df.empty:
                continue
            
            weight = timeframe_weights.get(tf, 1.0)
            pivots = self.find_pivot_levels(df)
            
            for support in pivots['supports']:
                all_levels.append({
                    'level': support['level'],
                    'type': 'SUPPORT',
                    'timeframe': tf,
                    'weight': weight
                })
            
            for resistance in pivots['resistances']:
                all_levels.append({
                    'level': resistance['level'],
                    'type': 'RESISTANCE',
                    'timeframe': tf,
                    'weight': weight
                })
        
        # Find confluence zones (levels within 50 points)
        confluence_zones = self._find_confluence_zones(all_levels, tolerance=50)
        
        # Get nearest levels
        nearest_support = self._find_nearest_level(all_levels, current_price, 'SUPPORT')
        nearest_resistance = self._find_nearest_level(all_levels, current_price, 'RESISTANCE')
        
        return {
            "all_levels": all_levels,
            "confluence_zones": confluence_zones,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance
        }
    
    def calculate_fibonacci_levels(self, df: pd.DataFrame, lookback: int = 50) -> Dict:
        """
        Calculates Fibonacci retracement levels from recent swing high/low
        """
        if len(df) < lookback:
            return {"levels": [], "swing_high": 0, "swing_low": 0}
        
        recent_df = df.tail(lookback)
        swing_high = recent_df['high'].max()
        swing_low = recent_df['low'].min()
        
        diff = swing_high - swing_low
        
        fib_levels = {
            "0.0": swing_low,
            "23.6": swing_low + diff * 0.236,
            "38.2": swing_low + diff * 0.382,
            "50.0": swing_low + diff * 0.500,
            "61.8": swing_low + diff * 0.618,
            "78.6": swing_low + diff * 0.786,
            "100.0": swing_high
        }
        
        return {
            "levels": fib_levels,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "range": diff
        }
    
    def find_volume_profile_levels(self, df: pd.DataFrame, bins: int = 20) -> Dict:
        """
        Finds Point of Control (POC) and Value Area using volume profile
        """
        if len(df) < 50 or 'volume' not in df.columns:
            return {"poc": 0, "value_area_high": 0, "value_area_low": 0}
        
        # Create price bins
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_range = price_max - price_min
        bin_size = price_range / bins
        
        # Calculate volume at each price level
        volume_profile = {}
        
        for _, row in df.iterrows():
            # Distribute volume across the candle's range
            candle_range = row['high'] - row['low']
            if candle_range == 0:
                bin_idx = int((row['close'] - price_min) / bin_size)
                volume_profile[bin_idx] = volume_profile.get(bin_idx, 0) + row['volume']
            else:
                # Distribute volume proportionally
                for price in np.linspace(row['low'], row['high'], 10):
                    bin_idx = int((price - price_min) / bin_size)
                    volume_profile[bin_idx] = volume_profile.get(bin_idx, 0) + row['volume'] / 10
        
        # Find POC (highest volume bin)
        poc_bin = max(volume_profile, key=volume_profile.get)
        poc_price = price_min + (poc_bin * bin_size) + (bin_size / 2)
        
        # Find Value Area (70% of volume)
        total_volume = sum(volume_profile.values())
        target_volume = total_volume * 0.70
        
        # Start from POC and expand
        sorted_bins = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        value_area_volume = 0
        value_area_bins = []
        
        for bin_idx, vol in sorted_bins:
            value_area_bins.append(bin_idx)
            value_area_volume += vol
            if value_area_volume >= target_volume:
                break
        
        value_area_high = price_min + (max(value_area_bins) * bin_size) + bin_size
        value_area_low = price_min + (min(value_area_bins) * bin_size)
        
        return {
            "poc": round(poc_price, 2),
            "value_area_high": round(value_area_high, 2),
            "value_area_low": round(value_area_low, 2),
            "volume_profile": volume_profile
        }
    
    def find_psychological_levels(self, current_price: float) -> Dict:
        """
        Finds round number psychological levels (25000, 25500, etc.)
        """
        # Round to nearest 100
        base = int(current_price / 100) * 100
        
        levels = {
            "major": [],  # 500-point intervals
            "minor": []   # 100-point intervals
        }
        
        # Major levels (500 intervals)
        for i in range(-2, 3):
            level = int(current_price / 500) * 500 + (i * 500)
            if abs(level - current_price) <= 1000:
                levels["major"].append(level)
        
        # Minor levels (100 intervals)
        for i in range(-5, 6):
            level = base + (i * 100)
            if abs(level - current_price) <= 500 and level not in levels["major"]:
                levels["minor"].append(level)
        
        return levels
    
    def find_previous_day_levels(self, df_daily: pd.DataFrame) -> Dict:
        """
        Finds previous day/week/month high/low levels
        """
        if df_daily is None or len(df_daily) < 2:
            return {}
        
        prev_day = df_daily.iloc[-2]
        
        levels = {
            "prev_day_high": prev_day['high'],
            "prev_day_low": prev_day['low'],
            "prev_day_close": prev_day['close']
        }
        
        # Previous week (if available)
        if len(df_daily) >= 7:
            prev_week = df_daily.tail(7)
            levels["prev_week_high"] = prev_week['high'].max()
            levels["prev_week_low"] = prev_week['low'].min()
        
        # Previous month (if available)
        if len(df_daily) >= 30:
            prev_month = df_daily.tail(30)
            levels["prev_month_high"] = prev_month['high'].max()
            levels["prev_month_low"] = prev_month['low'].min()
        
        return levels
    
    def get_comprehensive_sr(self, df_dict: Dict[str, pd.DataFrame], 
                            current_price: float,
                            option_chain_sr: List[Dict] = None) -> Dict:
        """
        Combines all S/R methods into a comprehensive analysis
        
        Returns prioritized S/R levels with strength scores
        """
        all_supports = []
        all_resistances = []
        
        # 1. Multi-timeframe pivots
        mtf_sr = self.find_multi_timeframe_sr(df_dict, current_price)
        
        # 2. Fibonacci levels
        if "5m" in df_dict and df_dict["5m"] is not None:
            fib = self.calculate_fibonacci_levels(df_dict["5m"])
            for level_name, level_price in fib['levels'].items():
                if level_price < current_price:
                    all_supports.append({
                        'level': level_price,
                        'type': f'FIB_{level_name}',
                        'strength': 0.8
                    })
                else:
                    all_resistances.append({
                        'level': level_price,
                        'type': f'FIB_{level_name}',
                        'strength': 0.8
                    })
        
        # 3. Volume profile
        if "5m" in df_dict and df_dict["5m"] is not None:
            vp = self.find_volume_profile_levels(df_dict["5m"])
            if vp['poc'] < current_price:
                all_supports.append({
                    'level': vp['poc'],
                    'type': 'POC',
                    'strength': 1.5  # Strong level
                })
            else:
                all_resistances.append({
                    'level': vp['poc'],
                    'type': 'POC',
                    'strength': 1.5
                })
        
        # 4. Psychological levels
        psych = self.find_psychological_levels(current_price)
        for level in psych['major']:
            if level < current_price:
                all_supports.append({'level': level, 'type': 'PSYCHOLOGICAL_MAJOR', 'strength': 1.0})
            else:
                all_resistances.append({'level': level, 'type': 'PSYCHOLOGICAL_MAJOR', 'strength': 1.0})
        
        # 5. Previous day levels
        if "1D" in df_dict and df_dict["1D"] is not None:
            prev_levels = self.find_previous_day_levels(df_dict["1D"])
            if 'prev_day_high' in prev_levels:
                all_resistances.append({
                    'level': prev_levels['prev_day_high'],
                    'type': 'PREV_DAY_HIGH',
                    'strength': 1.2
                })
            if 'prev_day_low' in prev_levels:
                all_supports.append({
                    'level': prev_levels['prev_day_low'],
                    'type': 'PREV_DAY_LOW',
                    'strength': 1.2
                })
        
        # 6. Option chain S/R (if provided)
        if option_chain_sr:
            for level in option_chain_sr:
                if level['type'] == 'CE_RESISTANCE':
                    all_resistances.append({
                        'level': level['strike'],
                        'type': 'OPTION_RESISTANCE',
                        'strength': min(level['strength'] / 100000, 2.0)
                    })
                elif level['type'] == 'PE_SUPPORT':
                    all_supports.append({
                        'level': level['strike'],
                        'type': 'OPTION_SUPPORT',
                        'strength': min(level['strength'] / 100000, 2.0)
                    })
        
        # Sort and deduplicate
        all_supports = self._deduplicate_levels(all_supports, tolerance=20)
        all_resistances = self._deduplicate_levels(all_resistances, tolerance=20)
        
        # Find nearest levels
        nearest_support = min([s for s in all_supports if s['level'] < current_price],
                             key=lambda x: current_price - x['level'], default=None)
        nearest_resistance = min([r for r in all_resistances if r['level'] > current_price],
                                key=lambda x: x['level'] - current_price, default=None)
        
        return {
            "all_supports": sorted(all_supports, key=lambda x: x['level'], reverse=True),
            "all_resistances": sorted(all_resistances, key=lambda x: x['level']),
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "confluence_zones": mtf_sr.get('confluence_zones', [])
        }
    
    def _find_confluence_zones(self, levels: List[Dict], tolerance: float = 50) -> List[Dict]:
        """Find zones where multiple S/R levels cluster"""
        if not levels:
            return []
        
        zones = []
        sorted_levels = sorted(levels, key=lambda x: x['level'])
        
        current_zone = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level['level'] - current_zone[-1]['level']) <= tolerance:
                current_zone.append(level)
            else:
                if len(current_zone) >= 2:  # At least 2 levels for confluence
                    avg_level = sum(l['level'] for l in current_zone) / len(current_zone)
                    total_weight = sum(l['weight'] for l in current_zone)
                    zones.append({
                        'level': round(avg_level, 2),
                        'strength': total_weight,
                        'count': len(current_zone),
                        'timeframes': [l['timeframe'] for l in current_zone]
                    })
                current_zone = [level]
        
        # Check last zone
        if len(current_zone) >= 2:
            avg_level = sum(l['level'] for l in current_zone) / len(current_zone)
            total_weight = sum(l['weight'] for l in current_zone)
            zones.append({
                'level': round(avg_level, 2),
                'strength': total_weight,
                'count': len(current_zone),
                'timeframes': [l['timeframe'] for l in current_zone]
            })
        
        return sorted(zones, key=lambda x: x['strength'], reverse=True)
    
    def _find_nearest_level(self, levels: List[Dict], price: float, level_type: str) -> Dict:
        """Find nearest support or resistance"""
        filtered = [l for l in levels if l['type'] == level_type]
        
        if level_type == 'SUPPORT':
            below = [l for l in filtered if l['level'] < price]
            return max(below, key=lambda x: x['level'], default=None) if below else None
        else:
            above = [l for l in filtered if l['level'] > price]
            return min(above, key=lambda x: x['level'], default=None) if above else None
    
    def _deduplicate_levels(self, levels: List[Dict], tolerance: float = 20) -> List[Dict]:
        """Merge levels that are very close together"""
        if not levels:
            return []
        
        sorted_levels = sorted(levels, key=lambda x: x['level'])
        deduped = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level['level'] - deduped[-1]['level']) > tolerance:
                deduped.append(level)
            else:
                # Merge: keep higher strength
                if level['strength'] > deduped[-1]['strength']:
                    deduped[-1] = level
        
        return deduped
