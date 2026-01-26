import pandas as pd
import logging
import sqlite3
import json
from supabase_manager import SupabaseManager
from datetime import datetime
from typing import Dict, List, Optional
from models import TradeSignal, SignalConfidence, DecisionObject, Regime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BrainEngine:
    """
    The Filter Model. Tracks rolling feature importance.
    Starts as Stage 1 (Passive Observer).
    """
    LOGIC_VERSION = "v1.2.9_STATISTICAL_CAUDALITY_FREEZE"

    def __init__(self, stage: int = 1):
        self.stage = stage # 1: Passive, 2: Shadow, 3: Filter
        self.cloud_db = SupabaseManager()
        self.state_file = "brain_state.json"
        
        # Default Weights
        self.feature_weights: Dict[str, float] = {
            "ADX": 1.0, "BASIS_RES": 1.2, "PCR": 1.0, "OI_RES": 1.5
        }
        self.feature_reputation: Dict[str, float] = {f: 1.0 for f in self.feature_weights}
        
        # Default Authority
        self.authority: Dict[str, float] = {
            "TRENDING": 1.0,
            "SIDEWAYS": 1.0,
            "UNCERTAIN": 1.0
        }
        
        # Load saved state if exists (Overnight learning persistence)
        self.load_state()
        self.feature_history: Dict[str, List[float]] = {f: [] for f in self.feature_weights}
        self.raw_history: Dict[str, List[float]] = {
            "OI_RAW": [], "BASIS_RAW": [], "PCR_RAW": [], "ADX_RAW": []
        }
        self.window_size = 500
        self.decisions: Dict[str, DecisionObject] = {}

    def save_state(self):
        """Saves current weights, authority, and reputation to disk."""
        try:
            state = {
                "feature_weights": self.feature_weights,
                "feature_reputation": self.feature_reputation,
                "authority": self.authority,
                "logic_version": self.LOGIC_VERSION,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=4)
            logger.info("BRAIN: State saved successfully.")
        except Exception as e:
            logger.error(f"BRAIN: Failed to save state: {e}")

    def load_state(self):
        """Loads weights, authority, and reputation from disk."""
        import os
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    self.feature_weights = state.get("feature_weights", self.feature_weights)
                    self.feature_reputation = state.get("feature_reputation", self.feature_reputation)
                    self.authority = state.get("authority", self.authority)
                logger.info("BRAIN: State loaded from disk.")
            except Exception as e:
                logger.error(f"BRAIN: Failed to load state: {e}")

    def update_raw_history(self, features: Dict[str, float]):
        """
        [v8.5] Maintains un-residualized raw feature history for correct Beta calculation.
        """
        for feat, val in features.items():
            if feat not in self.raw_history:
                self.raw_history[feat] = []
            
            self.raw_history[feat].append(val)
            if len(self.raw_history[feat]) > self.window_size:
                self.raw_history[feat].pop(0)

    def check_basis_stability(self, current_basis: float, hard_floor: float = 0.05) -> Dict:
        """
        [v8.6] Two-Tier Sigma Gate.
        Protects against low-variance traps using an absolute floor + relative dispersion.
        """
        history = self.raw_history.get("BASIS_RAW", [])
        if len(history) < 10:
            return {"is_unstable": False, "reason": "STABILIZING"}

        series = pd.Series(history)
        mean = series.mean()
        std = series.std()
        
        # Absolute check (Hard Floor)
        abs_diff = abs(current_basis - mean)
        is_abs_unstable = abs_diff > hard_floor
        
        # Relative check (Sigma Dispersion)
        # v8.6: Only use Sigma if std is significant
        is_sigma_unstable = (abs_diff > 2.5 * std) if std > 0.005 else False
        
        is_unstable = is_abs_unstable or is_sigma_unstable
        
        return {
            "is_unstable": is_unstable,
            "sigma_jump": abs_diff / std if std > 0 else 0,
            "abs_diff": abs_diff,
            "reason": "SIGMA_JUMP" if is_sigma_unstable else ("ABS_FLOOR_JUMP" if is_abs_unstable else "STABLE")
        }

    def get_confidence_boost(self, features: Dict[str, float], regime: str = "UNCERTAIN", 
                               signal_intent: Optional[str] = None, iv_skew: float = 1.0) -> Tuple[float, List[str]]:
        """
        [v8.6] Stateless confidence score with Signal-Aware IV Intelligence.
        """
        norm_features = {}
        for feat, val in features.items():
            if feat not in self.feature_weights: continue
            
            # Maintain history
            self.feature_history[feat].append(val)
            if len(self.feature_history[feat]) > self.window_size:
                self.feature_history[feat].pop(0)
            
            history = self.feature_history[feat]
            if len(history) < 50:
                norm_features[feat] = 0.5 
                continue
                
            mean = sum(history) / len(history)
            variance = sum((x - mean)**2 for x in history) / len(history)
            std = variance**0.5
            
            # Bounded Z-Score
            z_score = (val - mean) / std if std > 1e-4 else 0
            z_score = max(-2.5, min(2.5, z_score)) # Hard clip to prevent outliers from boosting
            
            import math
            norm_val = 1 / (1 + math.exp(-1.5 * z_score))
            norm_features[feat] = norm_val
        
        if not norm_features: return 1.0
        
        # Apply Feature Reputation Multiplier (v9.0.0 Advisory Mode)
        weighted_score = 0.0
        total_weight = 0.0
        
        for f, v in norm_features.items():
             w = self.feature_weights[f]
             rep = self.feature_reputation.get(f, 1.0) # [0.5, 1.5]
             w_adj = w * rep
             weighted_score += w_adj * v
             total_weight += w_adj
             
        score = weighted_score
        boost = min(max(score / total_weight, 0.0), 1.0) if total_weight > 0 else 1.0
        
        thoughts = []
        if boost > 0.8:
            thoughts.append(f"High conviction ({boost:.2f}) across features: {list(norm_features.keys())}")
        elif boost < 0.5:
            thoughts.append(f"Low feature synergy ({boost:.2f}). Market noise levels elevated.")

        # Phase 28: Signal-Aware IV Intelligence (Meta-Awareness)
        if signal_intent and iv_skew > 1.3:
            # High Put Skew = Fear.
            if signal_intent == "BULLISH":
                # Fear in Bullish context is a veto (Fighting the wall)
                boost *= 0.5
                thoughts.append(f"VETO: High Put Skew ({iv_skew:.2f}) detected while attempting Bullish entry. Fighting fear wall.")
            elif signal_intent == "BEARISH":
                # Fear in Bearish context is confirmation (Asymmetric momentm)
                boost = min(1.0, boost * 1.2)
                thoughts.append(f"BOOST: High Put Skew ({iv_skew:.2f}) confirms Bearish momentum.")

        # Authority Veto (Non-Boosting)
        regime_auth = self.authority.get(regime, 1.0)
        if regime_auth < 0.5:
            boost *= 0.5
            thoughts.append(f"VETO: Regime Authority ({regime_auth:.2f}) too low for {regime}. System in caution mode.")
            
        return boost, thoughts

    def generate_decision(self, features: Dict[str, float], regime: Regime, is_commit: bool = False, pattern_score: float = 0.0, iv_skew: float = 1.0) -> Tuple[Optional[str], List[str]]:
        """
        [v8.1] Stateless Inference. Returns (decision_id, thoughts).
        """
        # Identity Guard: Only generate identity for signals or high-conviction pattern detections
        if not is_commit and pattern_score < 0.7:
            return None, ["Technical pattern score too low for high-conviction decision."]

        import uuid
        decision_id = str(uuid.uuid4())[:8]
        
        boost, thoughts = self.get_confidence_boost(features, regime.value, iv_skew=iv_skew)
        threshold_map = {"TRENDING": 0.60, "SIDEWAYS": 0.80, "UNCERTAIN": 0.90}
        threshold = threshold_map.get(regime.value, 0.75)
        
        decision_str = "APPROVE" if boost > threshold else "BLOCK"
        
        if decision_str == "BLOCK":
            thoughts.append(f"Blocked: Confidence {boost:.2f} below regime threshold {threshold:.2f}.")
        
        self.decisions[decision_id] = DecisionObject(
            decision_id=decision_id,
            timestamp=datetime.now(),
            features=features,
            regime=regime,
            threshold=threshold,
            confidence_boost=boost,
            decision=decision_str
        )
        return decision_id, thoughts

    def log_snapshot(self, decision_id: str, outcome: Optional[bool] = None, performance: Dict[str, float] = {}, freeze_authority: bool = False):
        """
        [v8.1] Persistence-Aware Accountability.
        (Fix Audit v8.1 #3: MFE > 2x MAE)
        """
        try:
            decision_obj = self.decisions.pop(decision_id, None)
            if not decision_obj: return

            # 1. Structural Persistence Rule
            mfe, mae = performance.get("mfe", 0.0), performance.get("mae", 0.0)
            time_to_mfe = performance.get("time_to_mfe", 1000)
            
            # Actionability must show structural persistence (MFE > 2x MAE)
            persistence_alpha = (mfe > 2 * mae) if mae > 1 else (mfe > 10)
            
            # Waiver for hyper-speed momentum structure
            if time_to_mfe < 5.0 and mfe > (2 * mae) and mfe > 15:
                is_actionable = True
            else:
                is_actionable = persistence_alpha
            
            decision_obj.is_actionable = is_actionable
            
            # 2. Accountability
            efficacy = 0
            if outcome is not None:
                if decision_obj.decision == "APPROVE":
                    efficacy = 1 if (outcome is True and is_actionable) else 0
                else: # BLOCK
                    efficacy = 1 if (outcome is False or (outcome is True and not is_actionable)) else 0

                # 3. Regime-Scoped Authority (Rate-Limited Context)
                if not freeze_authority:
                    bucket = decision_obj.regime.value
                    if decision_obj.decision == "APPROVE":
                        if efficacy == 1:
                            self.authority[bucket] = min(1.0, self.authority[bucket] + 0.02)
                        else:
                            self.authority[bucket] = max(0.4, self.authority[bucket] - 0.05)
                    else: # BLOCK
                        if efficacy == 1:
                            self.authority[bucket] = min(1.0, self.authority[bucket] + 0.01)
                        else:
                            self.authority[bucket] = max(0.4, self.authority[bucket] - 0.02)

            decision_obj.efficacy = efficacy
            
            # 4. Transmit
            features_to_log = decision_obj.features.copy()
            features_to_log.update({
                "logic_version": self.LOGIC_VERSION,
                "decision_id": decision_obj.decision_id,
                "regime_authority": round(self.authority.get(decision_obj.regime.value, 1.0), 3),
                "persistence": persistence_alpha,
                "decision": decision_obj.decision,
                "efficacy": efficacy,
                "mfe": mfe,
                "mae": mae,
                "time_to_mfe": time_to_mfe,
                "frozen": freeze_authority
            })
            
            self.cloud_db.log_snapshot(features_to_log, 1 if outcome is True else 0, self.stage)
            
            # Phase 29: Save state after authority update
            self.save_state()
            
            logger.info(f"BRAIN: {decision_id} Finalized. Auth[{decision_obj.regime.value}]: {self.authority.get(decision_obj.regime.value, 0):.2f}")
            
        except Exception as e:
            logger.error(f"BRAIN ACCOUNTABILITY ERROR: {e}")

if __name__ == "__main__":
    brain = BrainEngine()
    feats = {"OI_CHG": 0.8, "PCR": 0.5, "BASIS": 0.2, "ADX": 0.9}
    print(f"Initial Confidence: {brain.get_confidence_boost(feats)}")
    # Simulate a loss where ADX was high
    brain.adjust_weights(False, feats)
    print(f"Post-Loss Weights: {brain.feature_weights}")
    print(f"Post-Loss Confidence: {brain.get_confidence_boost(feats)}")
