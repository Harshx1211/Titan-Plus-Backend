import logging
import time
import json
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from typing import List, Dict, Optional, Any, Union
from models import TradeSignal, SignalConfidence, DivergenceType, MarketData
from infrastructure import SupabaseManager

logger = logging.getLogger("engines")

# ============================================================================
# 1. Pattern Engine (Chart & Candlestick Intelligence)
# ============================================================================

class PatternEngine:
    def detect_candlesticks(self, df: pd.DataFrame, atr: float = 0.0) -> List[str]:
        if len(df) < 3: return []
        patterns, last, prev = [], df.iloc[-1], df.iloc[-2]
        
        # v9.8: Body must be significantly larger than noise (0.1 * ATR)
        body = abs(last.close - last.open)
        is_significant = body > (0.1 * atr) if atr > 0 else True
        
        if is_significant:
            if last.close > prev.open and last.open < prev.close and prev.close < prev.open: patterns.append("BULLISH_ENGULFING")
            if (min(last.open, last.close) - last.low) > (2 * body): patterns.append("HAMMER")
        return patterns

    def detect_structural(self, df: pd.DataFrame) -> List[str]:
        patterns = []
        if len(df) < 50: return []
        
        # [v9.9.9] Robust VWAP handling: Ensure numeric scalar comparison
        try:
            vwap = df.ta.vwap()
            if vwap is not None and len(vwap) > 1:
                # If vwap is a DataFrame, select the first column (standard VWAP)
                v_series = vwap.iloc[:, 0] if isinstance(vwap, pd.DataFrame) else vwap
                
                curr_close, prev_close = float(df.close.iloc[-1]), float(df.close.iloc[-2])
                curr_vwap, prev_vwap = float(v_series.iloc[-1]), float(v_series.iloc[-2])
                
                if curr_close > curr_vwap and prev_close <= prev_vwap: 
                    patterns.append("VWAP_CROSSOVER")
        except Exception as e:
            logger.warning(f"STRUCTURAL: VWAP analysis failed: {e}")

        rsi = df.ta.rsi(length=14)
        if rsi is not None and len(rsi) > 20:
            if df.close.iloc[-1] > df.close.iloc[-20:-1].max() and rsi.iloc[-1] < rsi.iloc[-20:-1].max(): patterns.append("BEARISH_DIVERGENCE")
        return patterns

    def detect_liquidity_sweeps(self, df: pd.DataFrame) -> List[str]:
        if len(df) < 30: return []
        pts, last = [], df.iloc[-1]
        low25 = df.low.iloc[-25:-1].min()
        if last.low < low25 and last.close > low25: pts.append("LIQUIDITY_SWEEP_BULLISH")
        return pts

    def detect_macro_zones(self, df: pd.DataFrame) -> List[float]:
        """[v9.8] Identifies clustering of highs/lows on macro timeframe."""
        if len(df) < 20: return []
        recent = df.tail(20)
        potential_zones = list(recent['high']) + list(recent['low'])
        # Simple clustering: Return average of top 3 most frequent prices (rounded)
        return sorted(list(set([round(p, -1) for p in potential_zones])))

    def get_signal_confirmation(self, df: pd.DataFrame, **kwargs) -> Dict:
        atr = kwargs.get("atr", 0.0)
        pats = self.detect_candlesticks(df, atr=atr) + self.detect_structural(df) + self.detect_liquidity_sweeps(df)
        return {"score": min(len(pats) * 0.3, 1.0), "patterns": pats}

    def confirm_reversal(self, df: pd.DataFrame, signal_type: str) -> bool:
        sweeps = self.detect_liquidity_sweeps(df)
        if signal_type == "BULLISH" and "LIQUIDITY_SWEEP_BULLISH" in sweeps: return True
        return False

# ============================================================================
# 2. Risk Engine (Capital Protection)
# ============================================================================

class RiskEngine:
    def __init__(self):
        self.active_positions = []
        self.last_loss_time = 0
        self.win_streak = 0
        self.daily_pnl = 0.0
        self.max_daily_loss = -500.0 # [v9.8.5] Absolute stop if daily loss exceeds this

    def reset(self):
        """Resets all risk metrics."""
        self.active_positions = []
        self.last_loss_time = 0
        self.win_streak = 0
        self.daily_pnl = 0.0
        logger.info("RISK: Engine metrics reset.")

    def is_in_recovery(self) -> bool:
        return (time.time() - self.last_loss_time) < 3600

    def log_trade(self, is_win: bool, pnl: float = 0.0):
        if is_win: self.win_streak += 1
        else: self.win_streak = 0; self.last_loss_time = time.time()
        self.daily_pnl += pnl

    def is_blown_today(self) -> bool:
        """[v9.8.5] Daily Circuit Breaker"""
        return self.daily_pnl <= self.max_daily_loss

    def get_suggested_size(self, confidence: Any, base_size: int = 1) -> int:
        mult = 0.5
        if isinstance(confidence, float): mult = 1.0 if confidence > 0.7 else 0.5
        
        # [Audit Fix] Implement winning streak dampening (prevent overconfidence)
        if self.win_streak >= 5:
            mult *= 0.7
            
        size = base_size * mult
        
        # [Audit Fix] Stronger recovery dampening (0.25x as per test spec)
        if self.is_in_recovery(): 
            size *= 0.25
            
        return max(1, round(size))

# ============================================================================
# 3. Data Sentinel (Truth Triangulation)
# ============================================================================

class DataSentinel:
    def __init__(self):
        self.future_window = []
        self.last_update_time = time.time()

    def check_integrity(self, spot: float, future: float, vix: float = 15.0) -> DivergenceType:
        if spot <= 0 or future <= 0: return DivergenceType.NONE
        basis = abs(future - spot) / spot * 100
        return DivergenceType.HARD if basis > (5.0 * (vix/15)) else (DivergenceType.SOFT if basis > (1.0 * (vix/15)) else DivergenceType.NONE)

# ============================================================================
# 4. Session Auditor (Daily Accountability)
# ============================================================================

class SessionAuditor:
    def __init__(self):
        self.db = SupabaseManager()

    def generate_daily_report(self, date_str: str = None) -> Dict:
        history = self.db.get_history(limit=100)
        if not history: return {"status": "NO_DATA"}
        return {"status": "REPORT_PENDING", "trades": len(history)}

# ============================================================================
# 5. Trap Hunter (Sidecar Execution)
# ============================================================================

class TrapHunter:
    def __init__(self):
        self.pattern_engine = PatternEngine()
        self.daily_trades = 0

    def check_trigger(self, veto_reason: str, signal_type: str, df: pd.DataFrame) -> Dict:
        if self.daily_trades >= 2: return {"action": "BLOCK", "reason": "CAP"}
        if self.pattern_engine.confirm_reversal(df, signal_type):
            return {"action": "EXECUTE", "reason": f"TRAP_DETECTED ({veto_reason})"}
        return {"action": "BLOCK", "reason": "NO_PATTERN"}
