"""
Titan Plus: Institutional Book Strategies
=========================================
Implementation of rule-based trading setups derived from world-class literature.

Book: Nifty & Bank Nifty Option Trading Strategies (Chetan Singh)
Book: Option Volatility & Pricing (Sheldon Natenberg)
Book: Trading in the Zone (Mark Douglas)
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger("book_strategies")

# ============================================================================
# PHASE A: Chetan Singh (Nifty/BankNifty Intraday Edge)
# ============================================================================

def _parse_ist_time(current_time_str: str):
    """Internal helper to parse timestamp strings for killzone checking."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(current_time_str.replace("Z", "+00:00"))
    except:
        return None

def chetan_hammer_s1(df: pd.DataFrame, smc_zones: Dict, current_time: str) -> pd.Series:
    """
    STRATEGY #1: Hammer Reversal Scalp (Page 45-47)
    Targets: NIFTY/BANKNIFTY CE (0 DTE)
    Killzone: 09:15 - 10:30 IST
    """
    try:
        dt = _parse_ist_time(current_time)
        if not dt or not (dt.hour == 9 or (dt.hour == 10 and dt.minute < 30)):
            return pd.Series([0] * len(df))

        # 1. S1 Pivot Logic (Standard)
        prev_high, prev_low, prev_close = df['high'].shift(1), df['low'].shift(1), df['close'].shift(1)
        pivot = (prev_high + prev_low + prev_close) / 3
        s1 = (2 * pivot) - prev_high
        in_zone = df['low'] <= s1 * 1.005 # ±0.5% tolerance

        # 2. Institutional Hammer (Singh Spec: Wick > 2.5x Body)
        body = abs(df['close'] - df['open'])
        lower_wick = np.where(df['close'] > df['open'], df['open'] - df['low'], df['close'] - df['low'])
        upper_wick = np.where(df['close'] > df['open'], df['high'] - df['close'], df['high'] - df['open'])
        
        is_hammer = (lower_wick > 2.5 * body) & (upper_wick < body * 0.3) & (body > 0)
        
        # 3. Indicators: RSI < 35 + Vol > 2.5x 20MA
        avg_vol = df['volume'].rolling(20).mean()
        volume_spike = df['volume'] > (avg_vol * 2.5)
        # Using a simple RSI placeholder for standalone logic (Engine uses pre-calc)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain/loss)))
        oversold = rsi < 35

        # 4. SMC Alignment (Order Block touch)
        smc_trigger = (df['low'] <= smc_zones.get('support', 0)) | in_zone

        signal = in_zone & is_hammer & oversold & volume_spike & smc_trigger
        return signal.astype(int)
    except Exception as e:
        logger.error(f"STRATEGY: Hammer S1 Error: {e}")
        return pd.Series([0] * len(df))

def chetan_engulfing_r1(df: pd.DataFrame, smc_zones: Dict, current_time: str) -> pd.Series:
    """
    STRATEGY #2: Bullish Engulfing R1 Rejection
    Killzone: 14:15 - 15:00 IST
    """
    try:
        dt = _parse_ist_time(current_time)
        if not dt or not (dt.hour == 14 and dt.minute >= 15) and not (dt.hour == 15 and dt.minute == 0):
            return pd.Series([0] * len(df))

        # 1. R1 Pivot Detection
        prev_high, prev_low, prev_close = df['high'].shift(1), df['low'].shift(1), df['close'].shift(1)
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        at_r1 = (df['high'] >= r1 * 0.998) # Proximity to R1

        # 2. Bullish Engulfing Logic
        prev_open, prev_close_candle = df['open'].shift(1), df['close'].shift(1)
        curr_open, curr_close = df['open'], df['close']
        
        is_bullish_engulfing = (prev_close_candle < prev_open) & \
                               (curr_close > curr_open) & \
                               (curr_close >= prev_open) & \
                               (curr_open <= prev_close_candle)

        # 3. Stochastic Proxy (Placeholder Logic)
        low_stoch = True # In real engine, we check indicator_engine.stoch
        
        signal = at_r1 & is_bullish_engulfing & low_stoch
        return signal.astype(int)
    except:
        return pd.Series([0] * len(df))

def chetan_doji_pivot(df: pd.DataFrame) -> pd.Series:
    """
    STRATEGY #3: Doji Reversal at Central Pivot (±0.2%)
    """
    try:
        prev_high, prev_low, prev_close = df['high'].shift(1), df['low'].shift(1), df['close'].shift(1)
        pivot = (prev_high + prev_low + prev_close) / 3
        
        # Doji: body < 10% of total range
        range_val = df['high'] - df['low']
        body = abs(df['close'] - df['open'])
        is_doji = (body <= range_val * 0.1) & (range_val > 0)
        
        at_pivot = (df['low'] <= pivot * 1.002) & (df['high'] >= pivot * 0.998)
        
        # Confirmation candle (Close above Doji high)
        confirmation = (df['close'] > df['high'].shift(1)) & is_doji.shift(1)
        
        signal = at_pivot.shift(1) & is_doji.shift(1) & confirmation
        return signal.astype(int)
    except:
        return pd.Series([0] * len(df))

def chetan_white_soldiers(df: pd.DataFrame) -> pd.Series:
    """
    STRATEGY #4: Three White Soldiers Breakout
    Requires 3 consecutive bullish candles closing near highs.
    """
    try:
        bullish = (df['close'] > df['open'])
        strong_close = (df['close'] - df['low']) / (df['high'] - df['low']) > 0.7
        
        three_soldiers = bullish & strong_close & \
                         bullish.shift(1) & strong_close.shift(1) & \
                         bullish.shift(2) & strong_close.shift(2)
        
        return three_soldiers.astype(int)
    except:
        return pd.Series([0] * len(df))

def chetan_evening_star_r2(df: pd.DataFrame) -> pd.Series:
    """
    STRATEGY #5: Evening Star + R2 Rejection (Bearish)
    """
    try:
        prev_high, prev_low, prev_close = df['high'].shift(1), df['low'].shift(1), df['close'].shift(1)
        pivot = (prev_high + prev_low + prev_close) / 3
        r2 = pivot + (prev_high - prev_low)
        
        at_r2 = df['high'] >= r2 * 0.998
        
        # Evening Star: Large Green -> Small Candle -> Large Red
        c1_bull = (df['close'].shift(2) > df['open'].shift(2))
        c2_small = abs(df['close'].shift(1) - df['open'].shift(1)) < abs(df['close'].shift(2) - df['open'].shift(2)) * 0.3
        c3_bear = (df['close'] < df['open']) & (df['close'] < df['open'].shift(2))
        
        signal = at_r2.shift(1) & c1_bull & c2_small & c3_bear
        return signal.astype(int)
    except:
        return pd.Series([0] * len(df))

# ============================================================================
# PHASE B: Sheldon Natenberg (Volatility Precision)
# ============================================================================

def natenberg_vol_stop_limit(current_price: float, iv: float, time_to_expiry: float = 1/252) -> float:
    """
    [CONCEPT] Precision Stop Loss based on Volatility Cone.
    Allows the engine to stay in trades longer during high-vol regimes.
    """
    # 1 Standard Deviation move for the timeframe
    # price * iv * sqrt(t)
    daily_move_std = current_price * iv * np.sqrt(time_to_expiry)
    return daily_move_std * 1.5 # 1.5 SD Stop

def titan_vol_stop(current_price: float, iv: float, atr: float) -> float:
    """
    [HYBRID] Natenberg Volatility + ATR Guardrail.
    Uses institutional math but caps risk with actual market realized range (ATR).
    """
    natenberg_base = natenberg_vol_stop_limit(current_price, iv)
    # Cap with 1.2x ATR logic for maximum safety
    return min(natenberg_base, atr * 1.2)

# ============================================================================
# PHASE C: Psychological & Risk Logic (Douglas/Link)
# ============================================================================

class StrategicRiskManager:
    """
    Implements Mark Douglas's 'Probabilistic Mindset' via code.
    Prevents overtrading after streaks and adjusts size based on edge confidence.
    """
    def __init__(self):
        self.streak_counter = 0
        self.max_daily_trades = 5
        
    def check_trade_readiness(self, current_trades_today: int) -> bool:
        if current_trades_today >= self.max_daily_trades:
            return False # Veto for emotional stability
        return True
