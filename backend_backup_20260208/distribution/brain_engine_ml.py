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
import xgboost as xgb
from sklearn.preprocessing import StandardScaler

from infrastructure import SupabaseManager, APP_CONFIG
from models import TradeSignal, SignalConfidence, DecisionObject, Regime

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
        
        # Load state and model
        self.load_state()
        self.load_model()

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
            thoughts.append("ML: Using statistical fallback (No model)")
            return self._get_confidence_boost_statistical(features, regime_val, thoughts)
        
        try:
            X = self._prepare_features(features, regime_val)
            X_scaled = self.scaler.transform(X)
            
            # Predict probability
            prob = self.model.predict_proba(X_scaled)[0][1]
            confidence = float(prob)
            
            thoughts.append(f"ML Confidence: {confidence:.2f}")
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
        thoughts.append(f"Statistical: {boost:.2f}")
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

    def train_model(self, X_train, y_train):
        """Train XGBoost model"""
        X_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_scaled, y_train)
        self.is_trained = True
        self.save_model()

    def generate_decision(self, features: Dict[str, float], regime: Regime) -> Tuple[str, List[str]]:
        """Generate trade decision"""
        decision_id = str(uuid.uuid4())[:8]
        boost, thoughts = self.get_confidence_boost_ml(features, regime.value)
        
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

if __name__ == "__main__":
    brain = BrainEngineML()
    print(brain.health_check())
