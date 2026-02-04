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

    def is_blown_today(self, current_balance: float = 100000.0) -> bool:
        """[v9.8.5] Daily Circuit Breaker with 5% Max Drawdown Cap"""
        max_loss_limit = -(current_balance * 0.05) # 5% cap
        # Use the tighter of the fixed limit or the percentage limit
        effective_limit = max(max_loss_limit, self.max_daily_loss) 
        return self.daily_pnl <= effective_limit

    def calculate_atr_size(self, account_balance: float, risk_pct: float, atr: float, lot_size_value: float = 25.0) -> int:
        """
        Calculates position size based on ATR volatility.
        Size = (Account Balance * Risk %) / (ATR * Lot Value)
        Example: (100k * 1%) / (50pts * 25) = 1000 / 1250 = 0.8 lots -> 1 lot
        """
        if atr <= 0: return 1
        risk_amount = account_balance * (risk_pct / 100.0)
        stop_loss_value = atr * lot_size_value
        
        raw_quantity = risk_amount / stop_loss_value
        return max(1, round(raw_quantity))

    def get_suggested_size(self, confidence: Any, base_size: int = 1, atr: float = 0.0, account_balance: float = 100000.0) -> int:
        """
        Smart Sizing: Uses ATR if available, else falls back to conviction multiplier.
        """
        # [Phase 3.5] ATR-based Sizing
        if atr > 0:
            risk_per_trade = 2.0 if (isinstance(confidence, float) and confidence > 0.8) else 1.0
            # Adjust risk based on recovery mode
            if self.is_in_recovery(): risk_per_trade *= 0.5
            
            return self.calculate_atr_size(account_balance, risk_per_trade, atr)

        # Fallback Logic
        mult = 0.5
        if isinstance(confidence, float): mult = 1.0 if confidence > 0.7 else 0.5
        
        if self.win_streak >= 5: mult *= 0.7
        size = base_size * mult
        
        if self.is_in_recovery():  size *= 0.25
            
        return max(1, round(size))

    def calculate_dynamic_stops(self, entry_price: float, signal_type: str, atr: float, precision_levels: Dict) -> Dict:
        """
        [Phase 5.5] Expert Stop/Target Logic (SMC + Pivots + OBs)
        """
        try:
            is_buy = signal_type in ["BUY_CALL", "LONG", "BUY"]
            stop_loss = 0.0
            targets = []
            
            # Default ATR Buffer (1.2x as per Friend's Request for Stops)
            sl_buffer = 1.2 * atr if atr > 0 else 20.0
            tp_buffer = 0.5 * atr if atr > 0 else 10.0
            
            # Extract Levels
            obs = precision_levels.get('order_blocks', [])
            fractals = precision_levels.get('fractals', [])
            oi_walls = precision_levels.get('oi_walls', [])
            pivots = precision_levels.get('pivots', {})
            
            # --- Stop Loss Logic ---
            if is_buy:
                # Priority 1: Nearest Bullish Order Block below entry
                valid_obs = [ob['zone_bottom'] for ob in obs if ob['type'] == 'SUPPORT' and ob['price'] < entry_price]
                # Priority 2: Fractals / OI
                valid_struct = [f['price'] for f in fractals if f['type'] == 'SUPPORT' and f['price'] < entry_price]
                valid_struct += [w['price'] for w in oi_walls if w['type'] == 'SUPPORT' and w['price'] < entry_price] # Fixed dict extraction
                
                if valid_obs:
                     # Stop below the OB Zone
                     valid_obs.sort(reverse=True)
                     stop_loss = valid_obs[0] - sl_buffer
                elif valid_struct:
                     valid_struct.sort(reverse=True)
                     stop_loss = valid_struct[0] - sl_buffer
                else:
                     stop_loss = entry_price - (2.0 * atr)
            else:
                # Priority 1: Nearest Bearish Order Block above entry
                valid_obs = [ob['zone_top'] for ob in obs if ob['type'] == 'RESISTANCE' and ob['price'] > entry_price]
                # Priority 2: Fractals / OI
                valid_struct = [f['price'] for f in fractals if f['type'] == 'RESISTANCE' and f['price'] > entry_price]
                valid_struct += [w['price'] for w in oi_walls if w['type'] == 'RESISTANCE' and w['price'] > entry_price] # Fixed dict extraction
                
                if valid_obs:
                     valid_obs.sort()
                     stop_loss = valid_obs[0] + sl_buffer
                elif valid_struct:
                     valid_struct.sort()
                     stop_loss = valid_struct[0] + sl_buffer
                else:
                     stop_loss = entry_price + (2.0 * atr)

            # --- Target Logic ---
            # 1. Next Structural Level (OB, Pivot, OI Wall)
            # 2. 1:2 RR Minimum
            
            min_target_dist = (entry_price - stop_loss) * 2 if is_buy else (stop_loss - entry_price) * 2
            min_target_price = entry_price + min_target_dist if is_buy else entry_price - min_target_dist
            
            discovered_targets = []
            
            if is_buy:
                # Potential Resistances
                candidates = [ob['zone_bottom'] for ob in obs if ob['type'] == 'RESISTANCE' and ob['price'] > entry_price]
                candidates += [f['price'] for f in fractals if f['type'] == 'RESISTANCE' and f['price'] > entry_price]
                cand_pivots = [v for k,v in pivots.items() if k.startswith('R') and v > entry_price]
                candidates += cand_pivots
                
                candidates.sort()
                
                for c in candidates:
                    if c > (entry_price + tp_buffer) and c not in discovered_targets:
                        discovered_targets.append(c)
            else:
                # Potential Supports
                candidates = [ob['zone_top'] for ob in obs if ob['type'] == 'SUPPORT' and ob['price'] < entry_price]
                candidates += [f['price'] for f in fractals if f['type'] == 'SUPPORT' and f['price'] < entry_price]
                cand_pivots = [v for k,v in pivots.items() if k.startswith('S') and v < entry_price]
                candidates += cand_pivots
                
                candidates.sort(reverse=True)
                
                for c in candidates:
                    if c < (entry_price - tp_buffer) and c not in discovered_targets:
                        discovered_targets.append(c)
            
            # Filter targets to ensure at least near 1:1 or 1:1.5 RR for the first target
            # Use discovered targets if they are reasonable, else use purely RR based
            
            final_targets = []
            for t in discovered_targets[:3]:
                final_targets.append(t)
            
            if not final_targets:
                final_targets = [min_target_price, min_target_price + atr*2]

            return {
                "stop_loss": round(stop_loss, 2),
                "targets": [round(t, 2) for t in final_targets],
                "risk_reward": round((final_targets[0] - entry_price) / (entry_price - stop_loss), 2) if is_buy and final_targets else 0.0
            }
        except Exception as e:
            logger.error(f"Dynamic Stop Calc Failed: {e}")
            return {"stop_loss": entry_price, "targets": []}

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
