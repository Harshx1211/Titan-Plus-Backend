"""
Skirmisher v2.0 - Enhanced Mean Reversion Engine [Institutional Upgrade]
Tactical scalping for sideways markets with multi-tier quality filters.
"""

import json
import logging
import pandas as pd
import pandas_ta as ta
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from models import Regime, SignalConfidence

# Configure Skirmisher V2 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skirmisher_v2")

class SidewaysQuality(Enum):
    """Sideways regime quality tiers"""
    STRONG = "SIDEWAYS_STRONG"    # ADX 20-25, compressed range
    NORMAL = "SIDEWAYS_NORMAL"    # ADX 15-20, moderate range
    WEAK = "SIDEWAYS_WEAK"        # ADX < 15, chop zone
    INVALID = "INVALID"

@dataclass
class SkirmisherConfig:
    """Configuration for tactical scalping [v2.0.0]"""
    # Quality-based caps
    max_scalps_strong: int = 5
    max_scalps_normal: int = 3
    max_scalps_weak: int = 1
    
    # Risk management
    cooldown_minutes: int = 30
    max_daily_loss: float = -50.0  # Points in index
    min_risk_reward: float = 1.5
    
    # IV Skew boundaries
    iv_skew_min: float = 0.8
    iv_skew_max: float = 1.3
    
    # Adaptive RSI
    rsi_tight_range_threshold: float = 10.0
    rsi_tight_upper: float = 60.0
    rsi_tight_lower: float = 40.0
    rsi_wide_upper: float = 70.0
    rsi_wide_lower: float = 30.0
    
    # Bollinger Bands
    bb_length: int = 20
    bb_std: float = 2.0
    bb_touch_threshold: float = 0.98  # Within 2% of band
    
    # HTF regime filter
    htf_adx_trending_threshold: float = 25.0
    htf_adx_sideways_threshold: float = 20.0
    
    # Predator Scalper Mode [v2.5]
    predator_mode: bool = False
    predator_min_target: float = 15.0
    predator_max_target: float = 35.0

@dataclass
class ScalpSetup:
    """Complete scalp trade setup"""
    action: str  # "EXECUTE" or "BLOCK"
    type: Optional[str] = None  # "BULLISH_SCALP" or "BEARISH_SCALP"
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None

class SkirmisherV2:
    """
    Enhanced mean-reversion scalper with:
    - Multi-timeframe confirmation (HTF)
    - IV skew awareness
    - Dynamic quality-based caps
    - Complete entry/exit logic
    - Volume & momentum breakout filters
    """
    
    def __init__(self, config: Optional[SkirmisherConfig] = None):
        self.config = config or SkirmisherConfig()
        self.state_file = "skirmisher_v2_state.json"
        self.ledger_file = "skirmisher_v2_ledger.json"
        
        # Load or initialize state
        self.state = self._load_state()
        
        # Reset daily if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state = {
                "date": today,
                "daily_scalps": 0,
                "daily_pnl": 0.0,
                "consecutive_losses": 0,
                "last_trade_time": None,
                "cooldown_until": None,
                "kill_switch_active": False
            }
            self._save_state()
    
    def classify_sideways_quality(
        self,
        df: pd.DataFrame,
        current_regime: str
    ) -> SidewaysQuality:
        """
        Multi-tier sideways classification based on ADX and ATR.
        """
        # Accept any sideways sub-type or generic sideways
        if not ("SIDEWAYS" in current_regime or current_regime == "CHOP"):
            return SidewaysQuality.INVALID
        
        if len(df) < 20:
            return SidewaysQuality.INVALID
        
        # Calculate ADX (Precision Detection)
        adx_df = df.ta.adx(length=14)
        if adx_df is None or 'ADX_14' not in adx_df.columns:
            return SidewaysQuality.WEAK
        
        current_adx = adx_df['ADX_14'].iloc[-1]
        
        # Calculate ATR compression
        atr = df.ta.atr(length=14)
        if atr is None or len(atr) == 0:
            return SidewaysQuality.WEAK
        
        current_atr = atr.iloc[-1]
        price_mean = df['close'].mean()
        atr_ratio = current_atr / price_mean if price_mean > 0 else 1.0
        
        # Quality tiers defined by collaborator
        if 20 <= current_adx < 25 and atr_ratio < 0.002:
            return SidewaysQuality.STRONG  # Sweet spot for range trading
        elif 15 <= current_adx < 20:
            return SidewaysQuality.NORMAL  # Standard sideways
        else:
            return SidewaysQuality.WEAK    # Extreme chop/deadlock
    
    def check_htf_regime(self, df_htf: pd.DataFrame) -> str:
        """
        Higher timeframe regime check.
        """
        if df_htf is None or len(df_htf) < 20:
            return "UNCERTAIN"
        
        adx_df = df_htf.ta.adx(length=14)
        if adx_df is None or 'ADX_14' not in adx_df.columns:
            return "UNCERTAIN"
        
        htf_adx = adx_df['ADX_14'].iloc[-1]
        
        if htf_adx > self.config.htf_adx_trending_threshold:
            return "TRENDING"
        elif htf_adx < self.config.htf_adx_sideways_threshold:
            return "SIDEWAYS"
        else:
            return "UNCERTAIN"
    
    def _get_adaptive_rsi_levels(self, rsi_series: pd.Series) -> Tuple[float, float]:
        """
        Adaptive thresholds based on window volatility.
        """
        if len(rsi_series) < 50:
            return self.config.rsi_wide_upper, self.config.rsi_wide_lower
        
        rsi_std = rsi_series.rolling(50).std().iloc[-1]
        
        if rsi_std < self.config.rsi_tight_range_threshold:
            return self.config.rsi_tight_upper, self.config.rsi_tight_lower
        else:
            return self.config.rsi_wide_upper, self.config.rsi_wide_lower
    
    def detect_mean_reversion_setup(self, df: pd.DataFrame) -> ScalpSetup:
        """
        Enhanced core detection with breakout filtering.
        """
        bb = df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std)
        rsi = df.ta.rsi(length=14)
        
        if bb is None or rsi is None:
            return ScalpSetup(action="BLOCK", reason="INDICATOR_ERROR")
        
        close = df['close'].iloc[-1]
        upper = bb.filter(like='BBU_').iloc[-1, 0]
        lower = bb.filter(like='BBL_').iloc[-1, 0]
        mid = bb.filter(like='BBM_').iloc[-1, 0]
        
        rsi_upper, rsi_lower = self._get_adaptive_rsi_levels(rsi)
        curr_rsi = rsi.iloc[-1]
        
        # Breakout Filter 1: Volume Spike
        has_volume_spike = False
        if 'volume' in df.columns:
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            curr_vol = df['volume'].iloc[-1]
            has_volume_spike = curr_vol > 1.2 * avg_vol
        
        # Breakout Filter 2: Velocity
        momentum = df['close'].diff(3).iloc[-1]
        
        # BEARISH SCALP (Upper Rejection)
        if close >= upper * self.config.bb_touch_threshold:
            if curr_rsi > rsi_upper:
                if momentum > 0 and has_volume_spike:
                    return ScalpSetup(action="BLOCK", reason="BREAKOUT_RISK (High Velocity)")
                
                entry = close
                stop = upper * 1.005
                # Predator Target: Faster exit at mid or 20 pts
                target = mid
                if self.config.predator_mode:
                    target = entry - self.config.predator_min_target
                
                rr = abs(entry - target) / abs(stop - entry)
                
                if not self.config.predator_mode and rr < self.config.min_risk_reward:
                    return ScalpSetup(action="BLOCK", reason=f"R:R_LOW ({rr:.2f})")
                
                return ScalpSetup(
                    action="EXECUTE", type="BEARISH_SCALP",
                    entry=entry, stop_loss=stop, take_profit=target,
                    risk_reward=rr, confidence=0.8 if has_volume_spike else 0.6,
                    reason=f"BB_UPPER_RECOVERY (RSI {curr_rsi:.1f}){ ' [PREDATOR]' if self.config.predator_mode else ''}"
                )
        
        # BULLISH SCALP (Lower Rejection)
        elif close <= lower * (2 - self.config.bb_touch_threshold):
            if curr_rsi < rsi_lower:
                if momentum < 0 and has_volume_spike:
                    return ScalpSetup(action="BLOCK", reason="BREAKDOWN_RISK (High Velocity)")
                
                entry = close
                stop = lower * 0.995
                target = mid
                if self.config.predator_mode:
                    target = entry + self.config.predator_min_target
                    
                rr = abs(target - entry) / abs(entry - stop)
                
                if not self.config.predator_mode and rr < self.config.min_risk_reward:
                    return ScalpSetup(action="BLOCK", reason=f"R:R_LOW ({rr:.2f})")
                
                return ScalpSetup(
                    action="EXECUTE", type="BULLISH_SCALP",
                    entry=entry, stop_loss=stop, take_profit=target,
                    risk_reward=rr, confidence=0.8 if has_volume_spike else 0.6,
                    reason=f"BB_LOWER_RECOVERY (RSI {curr_rsi:.1f}){ ' [PREDATOR]' if self.config.predator_mode else ''}"
                )
        
        return ScalpSetup(action="BLOCK", reason="NO_BAND_INTERACTION")
    
    def check_scalp_signal(
        self,
        df: pd.DataFrame,
        df_htf: pd.DataFrame,
        current_regime: str,
        iv_skew: float
    ) -> Dict:
        """
        Institutional Grade Gateway for Sideways Scalping.
        """
        # 1. Active Cooldown
        if self.state.get("cooldown_until"):
            cooldown = datetime.fromisoformat(self.state["cooldown_until"])
            if datetime.now() < cooldown:
                remaining = (cooldown - datetime.now()).seconds // 60
                return {"action": "BLOCK", "reason": f"COOLDOWN ({remaining}m)"}
        
        # 2. Daily Performance Check
        if self.state["daily_pnl"] <= self.config.max_daily_loss:
            return {"action": "BLOCK", "reason": "DAILY_STOP_LOSS"}
        
        # 3. Quality Tiering
        quality = self.classify_sideways_quality(df, current_regime)
        if quality == SidewaysQuality.INVALID:
            return {"action": "BLOCK", "reason": "REGIME_NOT_SIDEWAYS"}
        
        # 4. Multi-Tier Daily Cap
        max_trades = {
            SidewaysQuality.STRONG: self.config.max_scalps_strong,
            SidewaysQuality.NORMAL: self.config.max_scalps_normal,
            SidewaysQuality.WEAK: self.config.max_scalps_weak
        }[quality]
        
        if self.state["daily_scalps"] >= max_trades:
            return {"action": "BLOCK", "reason": f"DAILY_LIMIT ({quality.name})"}
        
        # 5. HTF Trend Inversion Filter
        htf_regime = self.check_htf_regime(df_htf)
        if htf_regime == "TRENDING":
            return {"action": "BLOCK", "reason": "HTF_TRENDING_CONFLICT"}
        
        # 6. IV Skew Gate
        if not (self.config.iv_skew_min <= iv_skew <= self.config.iv_skew_max):
            return {"action": "BLOCK", "reason": f"IV_SKEW_UNSTABLE ({iv_skew:.2f})"}
        
        # 7. Setup Detection
        setup = self.detect_mean_reversion_setup(df)
        
        if setup.action == "EXECUTE":
            return {
                "action": "EXECUTE",
                "type": setup.type,
                "entry": setup.entry,
                "stop_loss": setup.stop_loss,
                "take_profit": setup.take_profit,
                "risk_reward": setup.risk_reward,
                "confidence": setup.confidence,
                "reason": setup.reason,
                "quality": quality.name
            }
        
        return {"action": "BLOCK", "reason": setup.reason or "NO_PATTERN"}
    
    def log_execution(self, signal: Dict) -> str:
        """Logs execution to institutional ledger"""
        trade_id = f"sk2_{datetime.now().strftime('%H%M%S')}"
        self.state["daily_scalps"] += 1
        self.state["last_trade_time"] = datetime.now().isoformat()
        self._save_state()
        
        trade = {
            "id": trade_id,
            "timestamp": datetime.now().isoformat(),
            "type": signal["type"],
            "entry": signal["entry"],
            "stop_loss": signal["stop_loss"],
            "take_profit": signal["take_profit"],
            "risk_reward": signal["risk_reward"],
            "quality": signal.get("quality", "NORMAL"),
            "reason": signal["reason"],
            "status": "OPEN",
            "tag": "SKIRMISHER_V2_TACTICAL"
        }
        
        try:
            # [Q25 Fix] Atomic Write to prevent corruption
            ledger = []
            if os.path.exists(self.ledger_file):
                try:
                    with open(self.ledger_file, "r") as f:
                        ledger = json.load(f)
                except: ledger = []
            
            ledger.append(trade)
            temp_file = f"{self.ledger_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(ledger, f, indent=4)
            os.replace(temp_file, self.ledger_file)
        except Exception as e:
            logger.error(f"SKIRMISHER V2: Failed to log execution: {e}")
        
        logger.info(f"SKIRMISHER V2: Tactical Scalp Executed: {trade_id}")
        return trade_id
    
    def update_outcome(self, trade_id: str, pnl: float):
        """Re-entry recovery logic (Smart Cooldown)"""
        self.state["daily_pnl"] += pnl
        
        if pnl < 0:
            self.state["consecutive_losses"] += 1
            if self.state["consecutive_losses"] >= 2:
                cooldown_until = datetime.now() + timedelta(minutes=self.config.cooldown_minutes)
                self.state["cooldown_until"] = cooldown_until.isoformat()
                logger.warning(f"SKIRMISHER V2: Consecutive Losses Triggered Cooldown until {cooldown_until}")
        else:
            self.state["consecutive_losses"] = 0
            self.state["cooldown_until"] = None
        
        self._save_state()

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_state(self):
        # [Q25 Fix] Atomic Write for state
        try:
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(self.state, f, indent=4)
            os.replace(temp_file, self.state_file)
        except Exception as e:
            logger.error(f"SKIRMISHER V2: State save failed: {e}")
