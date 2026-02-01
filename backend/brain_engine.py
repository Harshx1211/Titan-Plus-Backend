import pandas as pd
import numpy as np
import logging
import json
import math
import os
import uuid
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from supabase_manager import SupabaseManager
from models import TradeSignal, SignalConfidence, DecisionObject, Regime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Feature Flag for Rollback
USE_V2_LOGIC = os.getenv("BRAIN_V2_ENABLED", "true").lower() == "true"

@dataclass
class BrainConfig:
    """Configuration for regime detection thresholds [v2.0.0]"""
    # Window sizes (v2.0 - FAST Sideways, SLOW Trending)
    window_size_trending: int = 500  # Slow tracking for persistence
    window_size_sideways: int = 200  # Fast adaptation for ranges
    window_size_uncertain: int = 200
    
    # Statistical thresholds
    min_history_bars: int = 12  # Reduced to 1m (12 * 5s) for faster startup
    variance_floor: float = 1e-6
    z_score_clip: float = 3.0
    sigmoid_scale: float = 1.5
    
    # Confidence thresholds
    threshold_trending: float = 0.60
    threshold_sideways: float = 0.75
    threshold_sideways_strong: float = 0.70 # More lenient in high quality
    threshold_sideways_weak: float = 0.85   # Very strict in chop
    threshold_uncertain: float = 0.75       # [v9.6] Lowered from 0.90 to capture volatility
    
    # Skirmisher evaluation (v2.1)
    min_risk_reward: float = 1.5
    skirmisher_authority_floor: float = 0.5
    skirmisher_quality_floor: float = 0.6
    
    # IV Skew thresholds
    iv_skew_high: float = 1.3
    iv_skew_bullish_discount: float = 0.7  # Reduce to 70% in bullish + high skew
    iv_skew_bearish_boost: float = 1.2     # Increase to 120% in bearish + high skew
    
    # Persistence checks
    persistence_mfe_mae_ratio: float = 2.0
    persistence_mfe_absolute: float = 10.0
    persistence_max_time_to_mfe: int = 10  # bars
    
    # Basis Stability Check (v9.5)
    basis_hard_floor: float = 5.0      # Max allowed % Basis
    basis_min_std: float = 0.5         # Minimum volatility to consider sigma
    basis_sigma_threshold: float = 3.0 # Max allowed sigma jump
    
    # Feature defaults
    default_feature_weight: float = 1.0
    
    # Learning Rates (v2.1)
    reputation_lr: float = 0.05
    authority_lr_approve_win: float = 0.02
    authority_lr_approve_loss: float = 0.10 # Aggressively penalize bad approvals
    authority_lr_block_win: float = 0.01
    authority_lr_block_loss: float = 0.01
    authority_decay: float = 0.99
    
    # Validation Bounds
    reputation_floor: float = 0.5
    reputation_ceiling: float = 1.5
    authority_floor: float = 0.3
    authority_ceiling: float = 1.0
    basis_hard_floor: float = 0.02
    basis_min_std: float = 0.01
    basis_sigma_threshold: float = 3.0

@dataclass
class BrainMetrics:
    """Production metrics for observability"""
    total_decisions: int = 0
    approvals: int = 0
    blocks: int = 0
    cold_starts: int = 0
    nan_rejections: int = 0
    total_latency_ms: float = 0.0
    avg_confidence: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

class BrainEngine:
    """
    Intelligent decision engine with statistical feature weighting. [v2.0.0]
    
    Features:
    - Adaptive feature importance learning
    - Regime-aware authority tracking
    - Statistical outlier detection with Bessel's correction
    - IV skew context awareness
    - Persistence-based efficacy scoring
    - [NEW] Rolling rollback flag for safety
    """
    LOGIC_VERSION = "v2.0.0_PRODUCTION_STABLE" if USE_V2_LOGIC else "v1.2.9_ROLLBACK_ENABLED"

    def __init__(self, stage: int = 1, config: Optional[BrainConfig] = None):
        if not USE_V2_LOGIC:
            logger.warning("BRAIN: RUNNING IN V1 COMPATIBILITY MODE (FLAG ENABLED)")
            
        self.stage = stage # 1: Passive, 2: Shadow, 3: Filter
        self.config = config or BrainConfig()
        self.cloud_db = SupabaseManager()
        self.state_file = "brain_state.json"
        self.metrics = BrainMetrics()
        self._last_regime = None
        
        # Feature weights (baseline importance)
        self.feature_weights: Dict[str, float] = {
            "ADX": 1.0, "BASIS_RES": 1.2, "PCR": 1.0, "OI_RES": 1.5
        }
        
        # Feature reputation (learned reliability)
        self.feature_reputation: Dict[str, float] = {f: 1.0 for f in self.feature_weights}
        
        # Regime authority (confidence in each regime's decisions)
        self.authority: Dict[str, float] = {
            "TRENDING": 1.0, 
            "SIDEWAYS_STRONG": 1.0, 
            "SIDEWAYS_NORMAL": 1.0, 
            "SIDEWAYS_WEAK": 1.0,
            "UNCERTAIN": 1.0
        }
        
        # Rolling feature history (using deque for O(1) performance)
        self.feature_history: Dict[str, deque] = {
            f: deque(maxlen=self.config.window_size_trending) for f in self.feature_weights
        }
        
        self.raw_history: Dict[str, deque] = {
            "OI_RAW": deque(maxlen=self.config.window_size_trending),
            "BASIS_RAW": deque(maxlen=self.config.window_size_trending),
            "PCR_RAW": deque(maxlen=self.config.window_size_trending),
            "ADX_RAW": deque(maxlen=self.config.window_size_trending)
        }
        
        self.decisions: Dict[str, DecisionObject] = {}
        
        # [v2.5] Intelligence Layer
        from news_service import NewsService
        self.news = NewsService()
        
        # Load and migrate state
        self.load_state()

    def health_check(self) -> Dict[str, Any]:
        """Load balancer / system health monitoring"""
        # Assuming authority_floor and authority_ceiling are defined in config
        # For now, using a placeholder if not present in BrainConfig
        authority_floor = getattr(self.config, 'authority_floor', 0.0)
        authority_ceiling = getattr(self.config, 'authority_ceiling', 1.0)
        auth_health = all(authority_floor <= v <= authority_ceiling for v in self.authority.values())
        return {
            "status": "HEALTHY" if auth_health else "DEGRADED",
            "version": self.LOGIC_VERSION,
            "stage": self.stage,
            "auth_drift": not auth_health,
            "state_file_ok": os.path.exists(self.state_file),
            "last_metrics_update": self.metrics.last_update.isoformat()
        }

    def migrate_state_v1_to_v2(self, old_state: dict) -> dict:
        """Migrate brain_state.json from v1.x to v2.0"""
        version = old_state.get("logic_version", "")
        if version.startswith("v1.") or "STATISTICAL_CAUDALITY_FREEZE" in version:
            logger.warning(f"BRAIN: Migrating v1 state ({version}) to v2.0")
            
            # 1. Backup old state
            backup_file = f"brain_state.v1_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(backup_file, "w") as f:
                    json.dump(old_state, f, indent=4)
                logger.info(f"BRAIN: V1 Backup created at {backup_file}")
            except Exception as e:
                logger.error(f"BRAIN: Failed to create backup during migration: {e}")

            new_state = old_state.copy()
            new_state["logic_version"] = self.LOGIC_VERSION
            
            # 2. Ensure authority has all regimes in correct format
            valid_regimes = ["TRENDING", "SIDEWAYS_STRONG", "SIDEWAYS_NORMAL", "SIDEWAYS_WEAK", "UNCERTAIN"]
            for r in valid_regimes:
                if r not in new_state.get("authority", {}):
                    # Map old SIDEWAYS to NORMAL if migrating
                    if r == "SIDEWAYS_NORMAL" and "SIDEWAYS" in new_state.get("authority", {}):
                        new_state.setdefault("authority", {})[r] = new_state["authority"]["SIDEWAYS"]
                    else:
                        new_state.setdefault("authority", {})[r] = 1.0
            
            # 3. Handle reputation bounds if needed
            reps = new_state.get("feature_reputation", {})
            # Assuming reputation_floor and reputation_ceiling are defined in config
            reputation_floor = getattr(self.config, 'reputation_floor', 0.0)
            reputation_ceiling = getattr(self.config, 'reputation_ceiling', 1.0)
            for f in reps:
                reps[f] = max(reputation_floor, min(reputation_ceiling, reps[f]))
            
            return new_state
        return old_state

    def save_state(self):
        """Saves current weights, authority, and reputation to disk."""
        try:
            state = {
                "feature_weights": self.feature_weights,
                "feature_reputation": self.feature_reputation,
                "authority": self.authority,
                "logic_version": self.LOGIC_VERSION,
                "stage": self.stage,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=4)
            logger.debug("BRAIN: State saved.")
        except Exception as e:
            logger.error(f"BRAIN: Save failed: {e}")

    def load_state(self):
        """Loads weights, authority, and reputation from disk with migration."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    
                state = self.migrate_state_v1_to_v2(state)
                
                self.feature_weights = state.get("feature_weights", self.feature_weights)
                self.feature_reputation = state.get("feature_reputation", self.feature_reputation)
                self.authority = state.get("authority", self.authority)
                
                logger.info(f"BRAIN: State loaded (v2.0).")
            except Exception as e:
                logger.error(f"BRAIN: Load failed: {e}")

    def _validate_feature_value(self, value: float, feature_name: str) -> Optional[float]:
        """Validate feature value and handle edge cases (NaN/Inf)."""
        if not math.isfinite(value):
            self.metrics.nan_rejections += 1
            logger.warning(f"BRAIN: Invalid {feature_name}: {value}")
            return None
            
        if "BASIS" in feature_name:
            # Assuming basis_hard_floor is defined in config
            basis_hard_floor = getattr(self.config, 'basis_hard_floor', 0.0)
            if value <= basis_hard_floor or value >= 100.0:
                logger.debug(f"BRAIN: Suspicious basis: {value}")
                return None
        return value

    def _ensure_window_size(self, regime: Regime):
        """Update deque sizes only when regime changes (Optimized)."""
        if self._last_regime == regime:
            return
            
        window_size = {
            Regime.TRENDING: self.config.window_size_trending,
            Regime.SIDEWAYS: self.config.window_size_sideways,
            Regime.SIDEWAYS_STRONG: self.config.window_size_sideways,
            Regime.SIDEWAYS_NORMAL: self.config.window_size_sideways,
            Regime.SIDEWAYS_WEAK: self.config.window_size_sideways,
            Regime.UNCERTAIN: self.config.window_size_uncertain
        }.get(regime, self.config.window_size_uncertain)
        
        for feat in self.feature_history:
            if self.feature_history[feat].maxlen != window_size:
                old_data = list(self.feature_history[feat])
                self.feature_history[feat] = deque(old_data[-window_size:], maxlen=window_size)
        
        for feat in self.raw_history:
            if self.raw_history[feat].maxlen != window_size:
                old_data = list(self.raw_history[feat])
                self.raw_history[feat] = deque(old_data[-window_size:], maxlen=window_size)
                
        self._last_regime = regime

    def update_raw_history(self, features: Dict[str, float]):
        """Maintains un-residualized raw history."""
        for feat, val in features.items():
            if feat not in self.raw_history:
                continue
            validated = self._validate_feature_value(val, feat)
            if validated is not None:
                self.raw_history[feat].append(validated)

    def check_basis_stability(self, current_basis: float) -> Dict[str, Any]:
        """Two-Tier Sigma Gate for basis stability."""
        history = list(self.raw_history.get("BASIS_RAW", []))
        if len(history) < 10:
            return {"is_unstable": False, "reason": "STABILIZING", "sigma_jump": 0.0, "abs_diff": 0.0}

        series = pd.Series(history)
        mean = series.mean()
        std = series.std() 
        
        # Assuming basis_hard_floor and basis_min_std, basis_sigma_threshold are defined in config
        # [v9.5] Fix: Use safe defaults in getattr in case config is stale
        basis_hard_floor = getattr(self.config, 'basis_hard_floor', 5.0)
        basis_min_std = getattr(self.config, 'basis_min_std', 0.5)
        basis_sigma_threshold = getattr(self.config, 'basis_sigma_threshold', 3.0)

        abs_diff = abs(current_basis - mean)
        is_abs_unstable = abs_diff > basis_hard_floor
        
        is_sigma_unstable = False
        sigma_jump = 0.0
        if std > basis_min_std:
            sigma_jump = abs_diff / std
            is_sigma_unstable = sigma_jump > basis_sigma_threshold
        
        # Only flag unstable if basis is NOT near expiration (0.0) -> actually usually < 1.0 is near expiry
        # But we use < 99.0 to just enable the check generally? 
        # Original logic: and current_basis < 99.0
        is_unstable = (is_abs_unstable or is_sigma_unstable) and current_basis < 99.0
        
        if is_unstable:
            logger.warning(f"BRAIN: Basis unstable ({abs_diff:.3f}, {sigma_jump:.1f}σ)")

        return {
            "is_unstable": is_unstable,
            "sigma_jump": sigma_jump,
            "abs_diff": abs_diff,
            "reason": "SIGMA_JUMP" if is_sigma_unstable else ("ABS_FLOOR_JUMP" if is_abs_unstable else "STABLE")
        }

    def _apply_iv_skew_adjustment(self, boost: float, signal_intent: Optional[str], iv_skew: float, regime: Regime) -> Tuple[float, List[str]]:
        """Signal-Aware IV Intelligence."""
        if not USE_V2_LOGIC: return boost, [] # Legacy skip
        
        thoughts = []
        if iv_skew <= self.config.iv_skew_high or not signal_intent:
            return boost, thoughts
            
        if regime == Regime.TRENDING:
            if signal_intent == "BULLISH":
                boost *= 0.85 
                thoughts.append(f"VETO: Put Skew ({iv_skew:.2f}) hint hedging in trend.")
            elif signal_intent == "BEARISH":
                boost = min(1.0, boost * 1.1)
                thoughts.append(f"BOOST: Put Skew ({iv_skew:.2f}) confirms trend fear.")
        else:
            if signal_intent == "BULLISH":
                boost *= self.config.iv_skew_bullish_discount
                thoughts.append(f"VETO: High Put Skew ({iv_skew:.2f}) - Fear factor strong.")
            elif signal_intent == "BEARISH":
                boost = min(1.0, boost * self.config.iv_skew_bearish_boost)
                thoughts.append(f"BOOST: High Put Skew ({iv_skew:.2f}) - Market crumbling.")
                
        return boost, thoughts

    def _normalize_feature(self, value: float, history: List[float]) -> Optional[float]:
        """Normalize a single feature value using sample statistics."""
        series = pd.Series(history)
        mean = series.mean()
        std = series.std() # Bessel's correction (ddof=1)
        
        if std < self.config.variance_floor:
            return 0.5
            
        z_score = (value - mean) / std
        z_score = np.clip(z_score, -self.config.z_score_clip, self.config.z_score_clip)
        
        return 1 / (1 + math.exp(-self.config.sigmoid_scale * z_score))

    def _get_authority(self, regime: Regime) -> float:
        """Get authority with backward compatibility (C2 Fix)"""
        key = regime.value
        if key == "SIDEWAYS" and key not in self.authority:
            return self.authority.get("SIDEWAYS_NORMAL", 1.0)
        return self.authority.get(key, 1.0)

    def get_confidence_boost(self, features: Dict[str, float], regime_val: str, 
                                signal_intent: Optional[str] = None, iv_skew: float = 1.0) -> Tuple[float, List[str]]:
        """Stateless confidence calculation with V2 statistical rigor."""
        start_time = time.perf_counter()
        
        # Determine regime enum
        target_regime = Regime.UNCERTAIN
        try:
            target_regime = Regime(regime_val)
        except ValueError:
            logger.warning(f"BRAIN: Invalid regime '{regime_val}' -> Defaults to UNCERTAIN")

        # Sync window size
        self._ensure_window_size(target_regime)

        norm_features = {}
        thoughts = []

        for feat, val in features.items():
            if feat not in self.feature_weights: continue
            
            validated = self._validate_feature_value(val, feat)
            if validated is None: continue
            
            self.feature_history[feat].append(validated)
            
            history = list(self.feature_history[feat])
            if len(history) < self.config.min_history_bars:
                continue 
            
            norm_val = self._normalize_feature(validated, history)
            if norm_val is not None:
                norm_features[feat] = norm_val
        
        # Process cold start
        if not norm_features: 
            self.metrics.cold_starts += 1
            # [v9.6] Enhanced Transparency: Show warmup progress
            max_hist = 0
            for f in self.feature_history:
                max_hist = max(max_hist, len(self.feature_history[f]))
            
            progress_msg = f"({max_hist}/{self.config.min_history_bars} bars)"
            
            if self.stage == 1:
                return 0.5, [f"Cold start: Learning mode {progress_msg}"]
            else:
                return 0.0, [f"VETO: Cold start - accumulating history {progress_msg}"]
        
        # Weighted Scoring
        weighted_score = 0.0
        total_weight = 0.0
        for f, v in norm_features.items():
             w_adj = self.feature_weights[f] * self.feature_reputation.get(f, 1.0)
             weighted_score += w_adj * v
             total_weight += w_adj
             
        boost = weighted_score / total_weight if total_weight > 0 else 0.5
        boost = np.clip(boost, 0.0, 1.0)
        
        # Thoughts
        if boost > 0.8: thoughts.append(f"High conviction ({boost:.2f}).")
        elif boost < 0.4: thoughts.append(f"Low synergy ({boost:.2f}).")

        boost, iv_thoughts = self._apply_iv_skew_adjustment(boost, signal_intent, iv_skew, target_regime)
        thoughts.extend(iv_thoughts)

        # Authority Scaling
        regime_auth = self._get_authority(target_regime)
        if regime_auth < 0.5: # Assuming 0.5 is a reasonable floor for general authority
            boost *= 0.6
            thoughts.append(f"AUTH VETO: {regime_auth:.2f} too low.")
            
        # Update metrics
        self.metrics.total_decisions += 1
        self.metrics.avg_confidence = (self.metrics.avg_confidence * 99 + boost) / 100
        self.metrics.total_latency_ms += (time.perf_counter() - start_time) * 1000
        self.metrics.last_update = datetime.now()
        
        return boost, thoughts

    def generate_decision(self, features: Dict[str, float], regime: Regime, is_commit: bool = False, 
                          pattern_score: float = 0.0, signal_intent: Optional[str] = None, iv_skew: float = 1.0,
                          news_sentiment: float = 0.0) -> Tuple[Optional[str], List[str]]:
        """Trade decision path."""
        if self.stage == 1 and is_commit:
            return None, ["Passive Mode: Decision suppressed."]

        # News Veto Logic
        if abs(news_sentiment) > 0.8:
            # If news is extreme, only allow if signal aligns perfectly
            if news_sentiment > 0.8 and signal_intent != "BULLISH":
                return None, [f"Blocked: Extreme Bearish News Veto ({news_sentiment})"]
            if news_sentiment < -0.8 and signal_intent != "BEARISH":
                return None, [f"Blocked: Extreme Bullish News Veto ({news_sentiment})"]

        if is_commit and pattern_score < 0.7:
            return None, [f"Blocked: Pattern {pattern_score:.2f} < 0.70."]

        decision_id = str(uuid.uuid4())[:8]
        boost, thoughts = self.get_confidence_boost(features, regime.value, signal_intent, iv_skew)
        
        # Apply news influence
        if news_sentiment != 0.0:
            if (news_sentiment > 0 and signal_intent == "BULLISH") or (news_sentiment < 0 and signal_intent == "BEARISH"):
                boost *= 1.2
                thoughts.append(f"News Confluence: +20% boost ({news_sentiment})")
            else:
                boost *= 0.8
                thoughts.append(f"News Friction: -20% penalty ({news_sentiment})")
        
        # 2. Threshold determination (Regime-aware)
        threshold = {
            Regime.TRENDING: self.config.threshold_trending,
            Regime.SIDEWAYS_STRONG: self.config.threshold_sideways_strong,
            Regime.SIDEWAYS_NORMAL: self.config.threshold_sideways,
            Regime.SIDEWAYS_WEAK: self.config.threshold_sideways_weak,
            Regime.UNCERTAIN: self.config.threshold_uncertain
        }.get(regime, self.config.threshold_sideways)
        
        decision_str = "APPROVE" if boost > threshold else "BLOCK"
        
        if decision_str == "APPROVE":
            self.metrics.approvals += 1
            thoughts.append(f"APPROVED: {boost:.2f} > {threshold:.2f}")
        else:
            self.metrics.blocks += 1
            thoughts.append(f"BLOCKED: {boost:.2f} < {threshold:.2f}")
        
        self.decisions[decision_id] = DecisionObject(
            decision_id=decision_id,
            timestamp=datetime.now(),
            features=features.copy(),
            regime=regime,
            threshold=threshold,
            confidence_boost=boost,
            decision=decision_str
        )
        return decision_id, thoughts

    def log_snapshot(self, decision_id: str, outcome: Optional[bool] = None, performance: Dict[str, float] = {}, freeze_authority: bool = False):
        """ Accountability tracker. """
        try:
            decision_obj = self.decisions.pop(decision_id, None)
            if not decision_obj: return

            mfe, mae = performance.get("mfe", 0.0), performance.get("mae", 0.0)
            time_to_mfe = performance.get("time_to_mfe", 999)
            
            is_actionable = (mfe > self.config.persistence_mfe_mae_ratio * mae) if mae > 1 else (mfe > self.config.persistence_mfe_absolute)
            if time_to_mfe < self.config.persistence_max_time_to_mfe and mfe > 15:
                is_actionable = True
            
            decision_obj.is_actionable = is_actionable
            efficacy = 0
            
            if outcome is not None:
                if decision_obj.decision == "APPROVE":
                    efficacy = 1 if (outcome is True and is_actionable) else 0
                else: 
                    efficacy = 1 if (outcome is False or (outcome is True and not is_actionable)) else 0

                for f in decision_obj.features:
                    if f in self.feature_reputation:
                        delta = self.config.reputation_lr if efficacy == 1 else -self.config.reputation_lr
                        new_rep = self.feature_reputation[f] + delta
                        self.feature_reputation[f] = max(self.config.reputation_floor, min(self.config.reputation_ceiling, new_rep))

                if not freeze_authority:
                    bucket = decision_obj.regime.value
                    if decision_obj.decision == "APPROVE":
                        delta = self.config.authority_lr_approve_win if efficacy == 1 else -self.config.authority_lr_approve_loss
                    else: 
                        delta = self.config.authority_lr_block_win if efficacy == 1 else -self.config.authority_lr_block_loss
                    
                    # Use get() and setdefault for safety against missing regime keys in authority map
                    curr_auth = self.authority.get(bucket, 1.0)
                    new_auth = curr_auth + delta
                    new_auth = new_auth * self.config.authority_decay + 1.0 * (1 - self.config.authority_decay)
                    self.authority[bucket] = max(self.config.authority_floor, min(self.config.authority_ceiling, new_auth))

            decision_obj.efficacy = efficacy
            
            features_to_log = decision_obj.features.copy()
            features_to_log.update({
                "logic_version": self.LOGIC_VERSION,
                "regime_authority": round(self.authority.get(decision_obj.regime.value, 1.0), 3),
                "decision": decision_obj.decision,
                "efficacy": efficacy,
                "mfe": mfe, "mae": mae
            })
            self.cloud_db.log_snapshot(features_to_log, 1 if outcome is True else 0, self.stage)
            self.save_state()
            
        except Exception as e:
            logger.error(f"BRAIN: Log failed: {e}")

    def evaluate_skirmisher_signal(
        self,
        signal: Dict,
        regime: Regime,
        iv_skew: float
    ) -> Tuple[bool, List[str]]:
        """
        Brain's statistical oversight for Skirmisher tactical signals. [Institutional v2.0]
        """
        thoughts = []
        
        # 1. Regime alignment check
        if not ("SIDEWAYS" in regime.value or regime == Regime.UNCERTAIN):
            return False, ["BRAIN: VETO - Skirmisher active outside Sideways/Uncertain regime."]
        
        # 2. Risk:Reward Validation
        rr = signal.get("risk_reward", 0)
        if rr < self.config.min_risk_reward:
            return False, [f"BRAIN: VETO - R:R {rr:.2f} below threshold {self.config.min_risk_reward}"]
            
        # 3. Authority Check (Learned reliability in this regime)
        auth = self.authority.get(regime.value, 1.0)
        if auth < self.config.authority_floor:
             return False, [f"BRAIN: VETO - Authority in {regime.value} too low ({auth:.2f})"]
             
        # 4. IV Skew Bias Check (Meta-Consistency)
        # Use brain's existing IV adjustment logic to see if it would boost/suppress this direction
        sig_type = "BULLISH" if "BULLISH" in signal["type"] else "BEARISH"
        # Dummy boost check
        if iv_skew > self.config.iv_skew_high and sig_type == "BULLISH":
             thoughts.append("BRAIN: Caution - Squaring long scalp against high put skew.")
        
        # 5. Quality Filter
        conf = signal.get("confidence", 0)
        if conf < 0.6:
             return False, [f"BRAIN: VETO - Signal quality {conf:.2f} below floor."]

        thoughts.append(f"BRAIN: ✅ APPROVE Scalp (Auth: {auth:.2f}, R:R: {rr:.2f})")
        return True, thoughts

    def update_threshold(self, new_val: float):
        """
        [v9.7] One-Way Tightening.
        Allows the Evolution Governor to increase system strictness.
        """
        old_val = self.config.threshold_sideways
        if new_val > old_val:
            self.config.threshold_sideways = new_val
            self.config.threshold_sideways_weak = min(0.95, new_val + 0.10)
            logger.warning(f"BRAIN: GOVERNOR tightening threshold {old_val} -> {new_val}")

if __name__ == "__main__":
    # Internal Health Check / Stress Test
    brain = BrainEngine(stage=3)
    print(f"Health Check: {brain.health_check()}")
    feats = {"OI_RES": 0.8, "PCR": 0.5, "BASIS_RES": 0.2, "ADX": 30}
    
    # 1. Test Cold Start
    boost, thoughts = brain.get_confidence_boost(feats, Regime.TRENDING.value)
    print(f"Cold Start: {boost:.2f} ({thoughts})")
    
    # 2. Simulate Load
    print("Simulating 1000 inferences...")
    for i in range(1000):
        brain.get_confidence_boost({k: v + (i%10)*0.01 for k,v in feats.items()}, Regime.TRENDING.value)
        
    print(f"Final Health: {brain.health_check()}")
    print(f"Metrics: {brain.metrics}")
