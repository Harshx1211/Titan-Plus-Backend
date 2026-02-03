import pandas as pd
import numpy as np
import logging
import json
import math
import os
import uuid
import time
import pickle
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# ML Libraries
# ML Libraries removed from global scope
# import xgboost as xgb
# from sklearn.preprocessing import StandardScaler

from infrastructure import SupabaseManager, APP_CONFIG
from models import TradeSignal, SignalConfidence, DecisionObject, Regime

# [v3.0] Grandmaster Engine Integration
from grandmaster import SMCAnalyzer, GammaEngine, MacroRegime, NuclearScorecard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BrainConfig:
    """Configuration for regime detection thresholds [v9.7.0 ML Enhanced]"""
    window_size_trending: int = 500
    window_size_sideways: int = 200
    window_size_uncertain: int = 200
    
    min_history_bars: int = 6
    variance_floor: float = 1e-6
    z_score_clip: float = 3.0
    sigmoid_scale: float = 1.5
    
    threshold_trending: float = 0.60  # Tightened for ML
    threshold_sideways: float = 0.55
    threshold_sideways_strong: float = 0.60
    threshold_sideways_weak: float = 0.50
    threshold_uncertain: float = 0.65
    
    min_risk_reward: float = 1.5
    skirmisher_authority_floor: float = 0.5
    skirmisher_quality_floor: float = 0.6
    
    # ML Specific
    ml_confidence_threshold: float = 0.55
    ml_min_training_samples: int = 200
    ml_retrain_interval: int = 100  # Retrain every N decisions

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
    ml_predictions: int = 0
    statistical_fallbacks: int = 0
    last_update: datetime = field(default_factory=datetime.now)

class BrainEngineML:
    """
    ML-Enhanced Brain Engine with XGBoost for decision making.
    Includes fallback to statistical methods when ML is unavailable.
    """
    LOGIC_VERSION = "v2.1.0_ML_XGBOOST"

    def __init__(self, stage: int = 1, config: Optional[BrainConfig] = None):
        self.stage = stage
        self.config = config or BrainConfig()
        self.cloud_db = SupabaseManager()
        self.state_file = "brain_state_ml.json"
        self.model_file = "brain_model.pkl"
        self.metrics = BrainMetrics()
        self._last_regime = None
        
        # ML Components
        from sklearn.preprocessing import StandardScaler
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.training_buffer = []
        self.decisions_since_retrain = 0
        
        # Feature weights (baseline importance)
        self.feature_weights: Dict[str, float] = {
            "ADX": 1.0, "BASIS_RES": 1.2, "PCR": 1.0, "OI_RES": 1.5
        }
        
        # Feature reputation (learned reliability)
        self.feature_reputation: Dict[str, float] = {f: 1.0 for f in self.feature_weights}
        
        # Regime authority
        self.authority: Dict[str, float] = {
            "TRENDING": 1.0, 
            "SIDEWAYS_STRONG": 1.0, 
            "SIDEWAYS_NORMAL": 1.0, 
            "SIDEWAYS_WEAK": 1.0,
            "UNCERTAIN": 1.0
        }
        
        # Rolling feature history
        self.feature_history: Dict[str, deque] = {
            f: deque(maxlen=self.config.window_size_trending) for f in self.feature_weights
        }
        
        self.decisions: Dict[str, DecisionObject] = {}
        
        self.raw_history: Dict[str, deque] = {
            "OI_RAW": deque(maxlen=self.config.window_size_trending),
            "BASIS_RAW": deque(maxlen=self.config.window_size_trending),
            "PCR_RAW": deque(maxlen=self.config.window_size_trending),
            "ADX_RAW": deque(maxlen=self.config.window_size_trending)
        }
        
        # Load state and model
        self.load_state()
        self.load_model()
        
        # [v3.0] Initialize Grandmaster Engines
        try:
            self.smc_engine = SMCAnalyzer(swing_length=5)
            self.gamma_engine = GammaEngine(contracts_per_lot=50 if "NIFTY" in APP_CONFIG.get("SYMBOL", "NIFTY") else 15)
            self.macro_engine = MacroRegime()
            self.nuclear_engine = NuclearScorecard(nuclear_threshold=0.85, standard_threshold=0.70)
            logger.info("Grandmaster Engine (Phase 3) Initialized Successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Grandmaster Engine: {e}")
            self.smc_engine = None

    def load_model(self):
        """Load trained XGBoost model"""
        try:
            if os.path.exists(self.model_file):
                with open(self.model_file, 'rb') as f:
                    saved_data = pickle.load(f)
                    self.model = saved_data['model']
                    self.scaler = saved_data['scaler']
                    self.is_trained = True
                logger.info(f"ML: Loaded trained model from {self.model_file}")
            else:
                logger.info("ML: No trained model found. Initializing new model.")
                self._initialize_model()
        except Exception as e:
            logger.error(f"ML: Failed to load model: {e}")
            self._initialize_model()

    def _initialize_model(self):
        """Initialize new XGBoost model"""
        import xgboost as xgb
        self.model = xgb.XGBClassifier(
            max_depth=6,
            learning_rate=0.1,
            n_estimators=100,
            objective='binary:logistic',
            eval_metric='logloss',
            random_state=42
        )
        self.is_trained = False

    def save_model(self):
        """Save trained model and scaler"""
        try:
            with open(self.model_file, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler
                }, f)
            logger.info(f"ML: Model saved to {self.model_file}")
        except Exception as e:
            logger.error(f"ML: Failed to save model: {e}")

    def _prepare_features(self, features: Dict[str, float], regime: str) -> np.ndarray:
        """Convert features dict to numpy array for ML prediction"""
        regime_encoding = {
            'TRENDING': 0,
            'SIDEWAYS_STRONG': 1,
            'SIDEWAYS_NORMAL': 2,
            'SIDEWAYS_WEAK': 3,
            'UNCERTAIN': 4
        }
        
        feature_vector = [
            features.get('ADX', 25.0),
            features.get('BASIS_RES', 0.5),
            features.get('PCR', 1.0),
            features.get('OI_RES', 0.5),
            regime_encoding.get(regime, 4),
            features.get('ADX', 25.0) * features.get('OI_RES', 0.5),  # Interaction
            abs(features.get('PCR', 1.0) - 1.0),  # PCR deviation
        ]
        
        return np.array(feature_vector).reshape(1, -1)

    def get_confidence_boost_ml(self, features: Dict[str, float], regime_val: str) -> Tuple[float, List[str]]:
        """ML-powered confidence scoring with fallback"""
        start_time = time.perf_counter()
        thoughts = []
        
        if not self.is_trained or self.model is None:
            self.metrics.statistical_fallbacks += 1
            thoughts.append("Epistemic Protocol: Transitioning to Statistical Fallback (Model Uninitialized)")
            return self._get_confidence_boost_statistical(features, regime_val, thoughts)
        
        try:
            X = self._prepare_features(features, regime_val)
            X_scaled = self.scaler.transform(X)
            
            # Predict probability
            prob = self.model.predict_proba(X_scaled)[0][1]
            confidence = float(prob)
            
            thoughts.append(f"ML Epistemic Precision: {confidence:.2f}")
            self.metrics.ml_predictions += 1
            self.metrics.total_decisions += 1
            self.metrics.avg_confidence = (self.metrics.avg_confidence * 99 + confidence) / 100
            self.metrics.total_latency_ms += (time.perf_counter() - start_time) * 1000
            
            return confidence, thoughts
            
        except Exception as e:
            logger.error(f"ML: Prediction failed: {e}")
            self.metrics.statistical_fallbacks += 1
            thoughts.append(f"ML Error: {str(e)[:40]}, using fallback")
            return self._get_confidence_boost_statistical(features, regime_val, thoughts)

    def _get_confidence_boost_statistical(self, features: Dict[str, float], 
                                         regime_val: str, thoughts: List[str]) -> Tuple[float, List[str]]:
        """Original statistical scoring logic"""
        target_regime = Regime.UNCERTAIN
        try:
            target_regime = Regime(regime_val)
        except ValueError:
            pass

        self._ensure_window_size(target_regime)

        norm_features = {}
        for feat, val in features.items():
            if feat not in self.feature_weights: continue
            
            self.feature_history[feat].append(val)
            history = list(self.feature_history[feat])
            
            if len(history) >= self.config.min_history_bars:
                norm_val = self._normalize_feature(val, history)
                if norm_val is not None:
                    norm_features[feat] = norm_val
        
        if not norm_features:
            return 0.5, thoughts + ["Warmup mode"]
        
        weighted_score = 0.0
        total_weight = 0.0
        for f, v in norm_features.items():
            w_adj = self.feature_weights[f] * self.feature_reputation.get(f, 1.0)
            weighted_score += w_adj * v
            total_weight += w_adj
        
        boost = weighted_score / total_weight if total_weight > 0 else 0.5
        thoughts.append(f"Statistical Probabilistic Bias: {boost:.2f}")
        return float(np.clip(boost, 0.0, 1.0)), thoughts

    def _ensure_window_size(self, regime: Regime):
        window_size = 200
        if regime == Regime.TRENDING: window_size = 500
        for feat in self.feature_history:
            if self.feature_history[feat].maxlen != window_size:
                old_data = list(self.feature_history[feat])
                self.feature_history[feat] = deque(old_data[-window_size:], maxlen=window_size)

    def _normalize_feature(self, value: float, history: List[float]) -> float:
        series = pd.Series(history)
        mean, std = series.mean(), series.std()
        if std < self.config.variance_floor: return 0.5
        z_score = np.clip((value - mean) / std, -self.config.z_score_clip, self.config.z_score_clip)
        return 1 / (1 + math.exp(-self.config.sigmoid_scale * z_score))

    def update_raw_history(self, raw_data: Dict[str, float]):
        """Update rolling raw feature buffers for stability checks"""
        for k, v in raw_data.items():
            if k in self.raw_history:
                self.raw_history[k].append(v)

    def check_basis_stability(self, current_basis: float) -> Dict[str, Any]:
        """Verify if basis is within statistical norms"""
        history = list(self.raw_history["BASIS_RAW"])
        if len(history) < 20:
            return {"is_unstable": False, "reason": "Warmup"}
        
        series = pd.Series(history)
        mean, std = series.mean(), series.std()
        z = abs(current_basis - mean) / std if std > 1e-6 else 0
        
        if z > 3.5:
            return {"is_unstable": True, "reason": f"Basis Spike (Z={z:.1f})"}
        return {"is_unstable": False, "reason": "Stable"}

    def train_model(self, X_train, y_train):
        """Train XGBoost model"""
        X_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_scaled, y_train)
        self.is_trained = True
        self.save_model()

    def generate_decision(self, features: Dict[str, float], regime: Regime, **kwargs) -> Tuple[str, List[str]]:
        """Generate trade decision. Accepts kwargs for api.py compatibility."""
        decision_id = str(uuid.uuid4())[:8]
        boost, thoughts = self.get_confidence_boost_ml(features, regime.value)
        
        # [v3.0] Grandmaster Logic Injection
        gm_thoughts = []
        gm_score = 0.0
        
        # We expect 'grandmaster_data' to be passed in kwargs by the API
        gm_data = kwargs.get('grandmaster_data', {})
        
        if self.nuclear_engine and gm_data:
            try:
                # Re-construct context (API pass raw data, we could re-run or just trust API)
                # Ideally, API should pass the 'decision' dict from Grandmaster
                # For now, let's assume API passes the 'nuclear_decision' object
                nuclear_decision = gm_data.get('nuclear_decision')
                
                if nuclear_decision:
                    gm_score = nuclear_decision.get('total_score', 0.0)
                    gm_signal = nuclear_decision.get('entry_signal', False)
                    gm_quality = nuclear_decision.get('signal_quality', 'WEAK')
                    
                    gm_thoughts.append(f"Grandmaster Score: {gm_score:.2f} ({gm_quality})")
                    
                    # [HYBRID LOGIC]
                    # 1. The VETO: If ML says YES but Grandmaster says NO_TRADE/WEAK (<0.5), we hesitate
                    if boost > 0.6 and gm_score < 0.5:
                        boost -= 0.15 # Penalty for institutional disagreement
                        gm_thoughts.append("WARN: Institutional Veto (Score < 0.5)")
                        
                    # 2. The BOOSTER: If Grandmaster is NUCLEAR (>0.85), we force high confidence
                    elif gm_score > 0.85:
                        boost = max(boost, 0.95) # Apply institutional authority
                        gm_thoughts.append("BOOST: Nuclear Institutional Confirmation")
            
            except Exception as e:
                logger.error(f"Grandmaster logic failed: {e}")

        # Merge thoughts
        thoughts.extend(gm_thoughts)
        
        # Merge pattern score into thoughts for logging
        pattern_score = kwargs.get("pattern_score", 0.0)
        thoughts.append(f"Chart Score: {pattern_score:.2f}")
        
        threshold = {
            Regime.TRENDING: self.config.threshold_trending,
            Regime.SIDEWAYS_STRONG: self.config.threshold_sideways_strong,
            Regime.SIDEWAYS_NORMAL: self.config.threshold_sideways,
            Regime.UNCERTAIN: self.config.threshold_uncertain
        }.get(regime, self.config.threshold_sideways)
        
        decision_str = "APPROVE" if boost > threshold else "BLOCK"
        
        self.decisions[decision_id] = DecisionObject(
            decision_id=decision_id, timestamp=datetime.now(),
            features=features.copy(), regime=regime,
            threshold=threshold, confidence_boost=boost, decision=decision_str
        )
        
        return decision_id, thoughts

    def log_snapshot(self, decision_id: str, outcome: Optional[bool] = None, 
                     performance: Dict[str, float] = {}, freeze_authority: bool = False,
                     spread: float = 0.0):
        """Accountability tracker - Logs to new trade_snapshots table"""
        try:
            # We don't pop() because we might want to log multiple stages
            decision_obj = self.decisions.get(decision_id)
            if not decision_obj: return

            mfe, mae = performance.get("mfe", 0.0), performance.get("mae", 0.0)
            
            # Simple outcome calculation for feedback loop
            efficacy = 0
            if outcome is not None:
                # 1 if choice was correct (Approve+Win or Block+Loss/Neutral)
                if decision_obj.decision == "APPROVE":
                    efficacy = 1 if (outcome is True and mfe > 5) else 0
                else: 
                    efficacy = 1 if (outcome is False or mfe < 5) else 0

                # Feedback loop: Adjust reputation
                for f in decision_obj.features:
                    if f in self.feature_reputation:
                        delta = 0.01 if efficacy == 1 else -0.01
                        self.feature_reputation[f] = max(0.5, min(1.5, self.feature_reputation[f] + delta))

            # Prepare data for Supabase
            features_to_log = decision_obj.features.copy()
            features_to_log.update({
                "decision": decision_obj.decision,
                "confidence": round(decision_obj.confidence_boost, 3),
                "mfe": round(mfe, 2), "mae": round(mae, 2),
                "spread": round(spread, 3)
            })
            
            # Use cloud_db to log to trade_snapshots (mapped in infrastructure.py)
            self.cloud_db.log_snapshot(
                signal_data={
                    "features": features_to_log,
                    "decision": decision_obj.decision,
                    "regime": decision_obj.regime.value
                },
                outcome=1 if outcome is True else (0 if outcome is False else None),
                stage=self.stage,
                efficacy=efficacy
            )
            self.save_state()
            
        except Exception as e:
            logger.error(f"ML: Log failed: {e}")

    def save_state(self):
        state = {
            "feature_reputation": self.feature_reputation,
            "authority": self.authority,
            "logic_version": self.LOGIC_VERSION,
            "is_trained": self.is_trained
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=4)

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.feature_reputation = state.get("feature_reputation", self.feature_reputation)
                self.authority = state.get("authority", self.authority)
            except: pass

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY" if self.is_trained else "WARMUP",
            "ml_trained": self.is_trained,
            "predictions": self.metrics.ml_predictions,
            "fallbacks": self.metrics.statistical_fallbacks
        }

    def update_threshold(self, new_val: float):
        """
        [v9.7] One-Way Tightening.
        Allows the Evolution Governor to increase system strictness.
        """
        old_val = self.config.threshold_sideways
        if new_val > old_val:
            self.config.threshold_sideways = new_val
            self.config.threshold_sideways_strong = min(0.95, new_val + 0.05)
            self.config.threshold_trending = max(self.config.threshold_trending, new_val)
            logger.warning(f"BRAIN: GOVERNOR tightening threshold {old_val} -> {new_val}")

    def analyze_institutional_logic(self, ohlcv_df: pd.DataFrame, option_chain: pd.DataFrame, macro_data: Dict) -> Dict:
        """
        Orchestrate the full Grandmaster Phase 3 Analysis.
        Returns a dictionary containing all module outputs and the final nuclear decision.
        """
        if not self.smc_engine:
            return {}
            
        try:
            # 1. SMC Analysis (Price Action)
            smc_result = self.smc_engine.analyze(ohlcv_df)
            
            # 2. Gamma Analysis (Flow)
            # We assume 'spot' is the last close in ohlcv
            current_spot = ohlcv_df['close'].iloc[-1] if not ohlcv_df.empty else 0
            greeks_result = self.gamma_engine.analyze(option_chain, current_spot)
            
            # 3. Macro Analysis (Regime)
            macro_score = self.macro_engine.analyze(macro_data)
            
            # 4. Nuclear Decision (The Judge)
            nuclear_decision = self.nuclear_engine.evaluate(smc_result, greeks_result, macro_score)
            
            return {
                'smc': smc_result,
                'greeks': greeks_result,
                'macro': {'score': macro_score},
                'nuclear_decision': nuclear_decision,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Grandmaster Analysis Failed: {e}")
            return {}

if __name__ == "__main__":
    brain = BrainEngineML()
    print(brain.health_check())
