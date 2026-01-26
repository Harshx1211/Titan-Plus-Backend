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
        self.feature_weights: Dict[str, float] = {
            "ADX": 1.0, "BASIS_RES": 1.2, "PCR": 1.0, "OI_RES": 1.5
        }
        self.feature_history: Dict[str, List[float]] = {f: [] for f in self.feature_weights}
        self.window_size = 500
        
        # 5. Regime-Scoped Authority
        self.authority: Dict[str, float] = {
            "TRENDING": 1.0,
            "SIDEWAYS": 1.0,
            "UNCERTAIN": 1.0
        }
        self.decisions: Dict[str, DecisionObject] = {}

    def get_confidence_boost(self, features: Dict[str, float], regime: str = "UNCERTAIN") -> float:
        """
        [v8.1] Calculates stateless confidence score with Bounded Z-Scores.
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
            
            # Bounded Z-Score (Fix Audit v8.1 #1)
            z_score = (val - mean) / std if std > 1e-4 else 0
            z_score = max(-2.5, min(2.5, z_score)) # Hard clip to prevent outliers from boosting
            
            import math
            norm_val = 1 / (1 + math.exp(-1.5 * z_score))
            norm_features[feat] = norm_val
        
        if not norm_features: return 1.0
        
        score = sum(self.feature_weights[f] * v for f, v in norm_features.items())
        boost = min(max(score / sum(self.feature_weights.values()), 0.0), 1.0)
        
        # Authority Veto (Non-Boosting)
        regime_auth = self.authority.get(regime, 1.0)
        if regime_auth < 0.5:
            boost *= 0.5
            
        return boost

    def generate_decision(self, features: Dict[str, float], regime: Regime, is_commit: bool = False, pattern_score: float = 0.0) -> Optional[str]:
        """
        [v8.1] Stateless Inference. Identity is only granted if Pattern Score is serious.
        (Fix Audit v8.1 #4)
        """
        # Identity Guard: Only generate identity for signals or high-conviction pattern detections
        if not is_commit and pattern_score < 0.7:
            return None 

        import uuid
        decision_id = str(uuid.uuid4())[:8]
        
        boost = self.get_confidence_boost(features, regime.value)
        threshold_map = {"TRENDING": 0.60, "SIDEWAYS": 0.80, "UNCERTAIN": 0.90}
        threshold = threshold_map.get(regime.value, 0.75)
        
        decision_str = "APPROVE" if boost > threshold else "BLOCK"
        
        self.decisions[decision_id] = DecisionObject(
            decision_id=decision_id,
            timestamp=datetime.now(),
            features=features,
            regime=regime,
            threshold=threshold,
            confidence_boost=boost,
            decision=decision_str
        )
        return decision_id

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
