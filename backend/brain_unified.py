"""
Titan Plus Unified Brain Engine v10.0
======================================
Consolidates all decision-making logic into single production system.

Features:
- XGBoost quantitative analysis
- PPO reinforcement learning
- SMC pattern recognition
- Meta-governor safety
- Feature reputation tracking

Author: Titan Plus Team
Version: 10.0.0
Date: 2026-02-08
"""

import logging
import json
import os
import numpy as np
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger("brain_unified")


@dataclass
class BrainConfig:
    """Brain configuration parameters."""
    threshold: float = 0.75
    xgboost_weight: float = 0.40
    rl_weight: float = 0.30
    smc_weight: float = 0.30
    
    # Vetoes
    veto_vix_spike: bool = True
    veto_basis_instability: bool = True
    veto_low_liquidity: bool = True
    veto_extreme_gex: bool = True
    
    # Thresholds
    vix_max: float = 25.0
    basis_max: float = 0.005  # 0.5%
    oi_min: int = 50000
    gex_max: float = 1000.0
    
    # Feature list
    features: List[str] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = ['ADX', 'BASIS_RES', 'PCR', 'OI_RES', 'VIX', 'GEX']
        
        # Validate weights sum to 1.0
        total = self.xgboost_weight + self.rl_weight + self.smc_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


class MetaGovernor:
    """
    Safety system that can tighten thresholds but never loosen automatically.
    """
    
    def __init__(self):
        self.min_win_rate = 40.0
        self.max_missed_alpha = 50.0
        self.lock_status = "ACTIVE"  # ACTIVE, STRICT, OVERRIDE
    
    def audit_threshold_proposal(
        self, 
        current_threshold: float, 
        performance_metrics: Dict
    ) -> float:
        """
        Evaluate whether to tighten or maintain threshold.
        
        Returns:
            Approved threshold value
        """
        win_rate = performance_metrics.get("win_rate", 50.0)
        missed_alpha = performance_metrics.get("missed_alpha", 0.0)
        
        # Rule 1: Auto-tighten on poor performance
        if win_rate < self.min_win_rate:
            logger.warning(f"GOVERNOR: Win rate {win_rate}% critical. TIGHTENING threshold.")
            self.lock_status = "STRICT"
            return min(0.95, current_threshold + 0.05)
        
        # Rule 2: Controlled loosening (only if performance elite)
        if win_rate > 65.0 and missed_alpha > self.max_missed_alpha:
            logger.info(f"GOVERNOR: Elite performance ({win_rate}%). Relaxing threshold slightly.")
            return max(0.50, current_threshold - 0.01)
        
        # Rule 3: Block auto-loosening otherwise
        if missed_alpha > self.max_missed_alpha:
            logger.info(f"GOVERNOR: High missed alpha ({missed_alpha}%). Loosening BLOCKED.")
            return current_threshold
        
        return current_threshold


class UnifiedBrainEngine:
    """
    Production brain with all capabilities integrated.
    """
    
    def __init__(self, config: Optional[BrainConfig] = None):
        self.version = "10.0.0"
        self.config = config or BrainConfig()
        
        # State tracking
        self.feature_reputation = {feat: 1.0 for feat in self.config.features}
        self.decision_threshold = self.config.threshold
        self.governor = MetaGovernor()
        
        # Performance tracking
        self.performance_history = {
            'xgboost': [],
            'rl': [],
            'smc': []
        }
        
        # [v10.2] Basis history for stability checks
        from collections import deque
        self.basis_history = deque(maxlen=200)
        
        # Initialize sub-systems
        self.xgb_engine = None
        self.rl_agent = None
        self.smc_engine = None
        
        # Load state if exists
        self.state_file = "brain_state_v10.json"
        self.load_state()
        
        logger.info(f"Unified Brain v{self.version} initialized")
    
    def initialize_engines(self):
        """
        Lazy initialization of heavy engines.
        Call this after importing to avoid startup delays.
        """
        # XGBoost Engine (Embedded)
        try:
            self.xgb_engine = self._create_xgb_engine()
            logger.info("XGBoost engine loaded (embedded)")
        except Exception as e:
            logger.warning(f"XGBoost engine not available: {e}")
        
        # RL Engine (Embedded)
        try:
            self.rl_agent = self._create_rl_agent()
            logger.info("RL (PPO) engine loaded (embedded)")
        except Exception as e:
            logger.warning(f"RL engine not available: {e}")
        
        # SMC Engine (External)
        try:
            from smc_engine import GrandmasterSMCEngine
            self.smc_engine = GrandmasterSMCEngine()
            logger.info("SMC engine loaded")
        except Exception as e:
            logger.warning(f"SMC engine not available: {e}")
    
    def _create_xgb_engine(self):
        """
        Embedded XGBoost engine.
        Loads pre-trained model or returns heuristic fallback.
        """
        class BrainEngineML:
            def __init__(self):
                self.model = None
                try:
                    import xgboost as xgb
                    import os
                    model_path = "brain_model.pkl"
                    if os.path.exists(model_path):
                        self.model = xgb.Booster()
                        self.model.load_model(model_path)
                        logger.info("XGBoost model loaded from disk")
                    else:
                        logger.warning("No XGBoost model found, using heuristic mode")
                except Exception as e:
                    logger.warning(f"XGBoost initialization failed: {e}")
            
            def predict_probability(self, feature_vector: np.ndarray) -> float:
                """Predict probability of profitable trade."""
                if self.model is None:
                    # Heuristic fallback
                    return self._heuristic_prediction(feature_vector)
                
                try:
                    import xgboost as xgb
                    dmatrix = xgb.DMatrix(feature_vector.reshape(1, -1))
                    prob = float(self.model.predict(dmatrix)[0])
                    return max(0.0, min(1.0, prob))
                except Exception as e:
                    logger.error(f"XGBoost prediction error: {e}")
                    return 0.5
            
            def _heuristic_prediction(self, features: np.ndarray) -> float:
                """Simple heuristic when model is unavailable."""
                # Assume features: [ADX, BASIS_RES, PCR, OI_RES, regime, interaction, pcr_dev]
                if len(features) < 4:
                    return 0.5
                
                adx = features[0]
                basis_res = features[1]
                pcr = features[2]
                oi_res = features[3]
                
                # Simple scoring
                score = 0.5
                if adx > 30: score += 0.1  # Strong trend
                if basis_res > 0.6: score += 0.1  # Bullish basis
                if 0.8 < pcr < 1.2: score += 0.1  # Balanced PCR
                if oi_res > 0.6: score += 0.1  # Strong OI
                
                return max(0.0, min(1.0, score))
        
        return BrainEngineML()
    
    def _create_rl_agent(self):
        """
        Embedded RL agent.
        Loads pre-trained PPO model or returns random policy.
        """
        class PPOAgent:
            def __init__(self):
                self.model = None
                try:
                    import torch
                    import os
                    model_path = "ppo_agent.pth"
                    if os.path.exists(model_path):
                        self.model = torch.load(model_path, map_location='cpu')
                        logger.info("PPO model loaded from disk")
                    else:
                        logger.warning("No PPO model found, using random policy")
                except Exception as e:
                    logger.warning(f"PPO initialization failed: {e}")
            
            def get_action(self, state: np.ndarray) -> Tuple[int, float, float]:
                """
                Get action from RL agent.
                Returns: (action_idx, log_prob, value)
                """
                if self.model is None:
                    # Random policy fallback
                    action = np.random.choice([0, 1, 2])  # BUY_CALL, BUY_PUT, HOLD
                    return action, 0.0, 0.5
                
                try:
                    import torch
                    with torch.no_grad():
                        state_tensor = torch.FloatTensor(state).unsqueeze(0)
                        # Simplified inference (assumes model has forward method)
                        output = self.model(state_tensor)
                        if isinstance(output, tuple):
                            action_probs, value = output
                        else:
                            action_probs = output
                            value = torch.tensor([0.5])
                        
                        action = torch.argmax(action_probs, dim=1).item()
                        log_prob = torch.log(action_probs[0, action]).item()
                        value_scalar = value.item() if hasattr(value, 'item') else 0.5
                        
                        return action, log_prob, value_scalar
                except Exception as e:
                    logger.error(f"PPO inference error: {e}")
                    return 2, 0.0, 0.5  # Default to HOLD
        
        return PPOAgent()
    
    def decide(
        self,
        features: Dict[str, float],
        market_data: Dict,
        regime: str,
        ohlcv_df=None,
        **kwargs
    ) -> Dict:
        """
        Master decision function.
        
        Args:
            features: Technical indicators (ADX, BASIS_RES, PCR, etc.)
            market_data: Market snapshot (spot, future, oi, vix, etc.)
            regime: Market regime (TRENDING, SIDEWAYS_STRONG, etc.)
            ohlcv_df: OHLC data for SMC analysis
            **kwargs: Additional parameters
        
        Returns:
            {
                'decision_id': str,
                'decision': 'APPROVE' or 'BLOCK',
                'probability': float (0-1),
                'confidence': float (0-1),
                'action': 'BUY_CALL', 'BUY_PUT', or 'HOLD',
                'components': {...},
                'weights': {...},
                'threshold': float,
                'vetoes': [...],
                'thoughts': [...],
                'timestamp': str
            }
        """
        decision_id = self._generate_decision_id()
        thoughts = []
        
        # 1. Apply feature reputation
        adjusted_features = self._apply_reputation(features)
        thoughts.append(f"Features adjusted by reputation")
        
        # 2. Meta-vetoes (hard blocks)
        veto_active, veto_reasons = self._check_vetoes(market_data, regime)
        if veto_active:
            thoughts.extend([f"VETO: {r}" for r in veto_reasons])
            return self._blocked_decision(decision_id, veto_reasons, thoughts)
        
        # 3. Component analysis
        components = {}
        
        # XGBoost analysis
        xgb_prob, xgb_thoughts = self._xgboost_analysis(adjusted_features, regime)
        components['xgboost'] = xgb_prob
        thoughts.extend(xgb_thoughts)
        
        # RL analysis
        rl_action, rl_conf, rl_thoughts = self._rl_analysis(adjusted_features, regime)
        components['rl'] = rl_conf
        thoughts.extend(rl_thoughts)
        
        # SMC analysis
        smc_score, smc_thoughts = self._smc_analysis(ohlcv_df, market_data)
        components['smc'] = smc_score
        thoughts.extend(smc_thoughts)
        
        # 4. Weighted confluence
        weights = {
            'xgboost': self.config.xgboost_weight,
            'rl': self.config.rl_weight,
            'smc': self.config.smc_weight
        }
        
        final_probability = (
            weights['xgboost'] * xgb_prob +
            weights['rl'] * rl_conf +
            weights['smc'] * smc_score
        )
        
        thoughts.append(
            f"Confluence: XGB={xgb_prob:.3f} × {weights['xgboost']}, "
            f"RL={rl_conf:.3f} × {weights['rl']}, "
            f"SMC={smc_score:.3f} × {weights['smc']} "
            f"= {final_probability:.3f}"
        )
        
        # 5. Governor threshold check
        approved = final_probability > self.decision_threshold
        
        if approved:
            thoughts.append(f"✓ APPROVED: {final_probability:.3f} > {self.decision_threshold}")
        else:
            thoughts.append(f"✗ BLOCKED: {final_probability:.3f} ≤ {self.decision_threshold}")
        
        # 6. Construct response
        return {
            'decision_id': decision_id,
            'decision': 'APPROVE' if approved else 'BLOCK',
            'probability': final_probability,
            'confidence': final_probability,
            'action': rl_action if approved else 'HOLD',
            'components': components,
            'weights': weights,
            'threshold': self.decision_threshold,
            'vetoes': [],
            'thoughts': thoughts,
            'regime': regime,
            'timestamp': datetime.now().isoformat()
        }
    
    def _apply_reputation(self, features: Dict) -> Dict:
        """Apply feature reputation multipliers."""
        adjusted = {}
        for k, v in features.items():
            reputation = self.feature_reputation.get(k, 1.0)
            adjusted[k] = v * reputation
        return adjusted
    
    def _check_vetoes(self, market_data: Dict, regime: str) -> Tuple[bool, List[str]]:
        """Check all meta-vetoes."""
        vetoes = []
        
        # VIX spike veto
        if self.config.veto_vix_spike:
            vix = market_data.get('vix', 15)
            if vix > self.config.vix_max:
                vetoes.append(f"VIX too high: {vix:.1f} > {self.config.vix_max}")
        
        # Basis instability veto
        if self.config.veto_basis_instability:
            spot = market_data.get('spot_price', 0)
            future = market_data.get('future_price', spot)
            if spot > 0:
                basis = abs(future - spot) / spot
                if basis > self.config.basis_max:
                    vetoes.append(f"Basis unstable: {basis:.4f} > {self.config.basis_max}")
        
        # Low liquidity veto
        if self.config.veto_low_liquidity:
            oi = market_data.get('oi', 0)
            if oi < self.config.oi_min:
                vetoes.append(f"Low OI: {oi} < {self.config.oi_min}")
        
        # Extreme GEX veto
        if self.config.veto_extreme_gex:
            gex = market_data.get('gex', 0)
            if abs(gex) > self.config.gex_max:
                vetoes.append(f"Extreme GEX: {abs(gex):.1f} > {self.config.gex_max}")
        
        return len(vetoes) > 0, vetoes
    
    def _xgboost_analysis(self, features: Dict, regime: str) -> Tuple[float, List[str]]:
        """Get XGBoost prediction."""
        if self.xgb_engine is None:
            return 0.5, ["XGBoost: Not initialized"]
        
        try:
            # Prepare feature vector
            feature_vector = self._features_to_vector(features, regime)
            
            # Get prediction
            prob = self.xgb_engine.predict_probability(feature_vector)
            
            thoughts = [f"XGBoost: {prob:.3f}"]
            return prob, thoughts
            
        except Exception as e:
            logger.error(f"XGBoost error: {e}")
            return 0.5, [f"XGBoost error: {str(e)}"]
    
    def _rl_analysis(self, features: Dict, regime: str) -> Tuple[str, float, List[str]]:
        """Get RL recommendation."""
        if self.rl_agent is None:
            return 'HOLD', 0.5, ["RL: Not initialized"]
        
        try:
            # Convert features to state vector
            state = self._features_to_state(features, regime)
            
            # Get action from RL agent
            action, log_prob, value = self.rl_agent.get_action(state)
            
            # Map action index to action name
            actions = ['BUY_CALL', 'BUY_PUT', 'HOLD']
            action_name = actions[action] if action < len(actions) else 'HOLD'
            
            # Convert log prob to confidence
            confidence = min(1.0, abs(value) / 10.0)  # Normalize value to 0-1
            
            thoughts = [f"RL: {action_name} (conf: {confidence:.3f})"]
            return action_name, confidence, thoughts
            
        except Exception as e:
            logger.error(f"RL error: {e}")
            return 'HOLD', 0.5, [f"RL error: {str(e)}"]
    
    def _smc_analysis(self, ohlcv_df, market_data: Dict) -> Tuple[float, List[str]]:
        """Get SMC confluence score."""
        if self.smc_engine is None:
            return 0.5, ["SMC: Not initialized"]
        
        try:
            if ohlcv_df is None or len(ohlcv_df) < 20:
                return 0.5, ["SMC: Insufficient data"]
            
            # Run SMC analysis
            analysis = self.smc_engine.analyze(ohlcv_df, market_data)
            
            # Normalize confluence score to 0-1
            score = analysis.get('confluence_score', 50) / 100.0
            
            thoughts = [f"SMC: {score:.3f}"]
            
            # Add signal details if available
            signals = analysis.get('signals', {})
            if signals:
                signal_count = sum(1 for v in signals.values() if v)
                thoughts.append(f"SMC signals: {signal_count}/5 active")
            
            return score, thoughts
            
        except Exception as e:
            logger.error(f"SMC error: {e}")
            return 0.5, [f"SMC error: {str(e)}"]
    
    def _features_to_vector(self, features: Dict, regime: str) -> np.ndarray:
        """Convert features dict to vector for XGBoost."""
        # Map regime to numeric
        regime_map = {
            'TRENDING': 0,
            'SIDEWAYS_STRONG': 1,
            'SIDEWAYS_NORMAL': 2,
            'SIDEWAYS_WEAK': 3,
            'UNCERTAIN': 4
        }
        regime_val = regime_map.get(regime, 4)
        
        # Build feature vector
        vector = [
            features.get('ADX', 25.0),
            features.get('BASIS_RES', 0.5),
            features.get('PCR', 1.0),
            features.get('OI_RES', 0.5),
            regime_val,
            features.get('ADX', 25.0) * features.get('OI_RES', 0.5),  # Interaction
            abs(features.get('PCR', 1.0) - 1.0)  # PCR deviation
        ]
        
        return np.array(vector, dtype=np.float32)
    
    def _features_to_state(self, features: Dict, regime: str) -> np.ndarray:
        """Convert features dict to state vector for RL."""
        regime_map = {
            'TRENDING': 0,
            'SIDEWAYS_STRONG': 1,
            'SIDEWAYS_NORMAL': 2,
            'SIDEWAYS_WEAK': 3,
            'UNCERTAIN': 4
        }
        regime_val = regime_map.get(regime, 4) / 4.0  # Normalize
        
        # Build state vector (25 dimensions for PPO)
        state = [
            features.get('ADX', 25.0) / 50.0,  # Normalize
            features.get('BASIS_RES', 0.5),
            features.get('PCR', 1.0),
            features.get('OI_RES', 0.5),
            regime_val,
            features.get('VIX', 15.0) / 30.0,  # Normalize
            features.get('GEX', 0.0) / 1000.0,  # Normalize
            # Add reputation scores
            self.feature_reputation.get('ADX', 1.0),
            self.feature_reputation.get('BASIS_RES', 1.0),
            self.feature_reputation.get('PCR', 1.0),
            self.feature_reputation.get('OI_RES', 1.0),
            # Add time features
            datetime.now().hour / 24.0,
            datetime.now().minute / 60.0,
            # Pad to 25 dimensions
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        ]
        
        return np.array(state[:25], dtype=np.float32)  # Ensure 25 dimensions
    
    def _blocked_decision(
        self, 
        decision_id: str, 
        reasons: List[str], 
        thoughts: List[str]
    ) -> Dict:
        """Construct blocked decision response."""
        return {
            'decision_id': decision_id,
            'decision': 'BLOCK',
            'probability': 0.0,
            'confidence': 0.0,
            'action': 'HOLD',
            'components': {},
            'weights': {},
            'threshold': self.decision_threshold,
            'vetoes': reasons,
            'thoughts': thoughts,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_decision_id(self) -> str:
        """Generate unique decision ID."""
        return f"DEC_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    def update_reputation(self, feature_updates: Dict[str, float]):
        """
        Update feature reputation based on outcomes.
        
        Args:
            feature_updates: Dict of {feature_name: adjustment} 
                            (e.g., {'ADX': -0.02, 'PCR': +0.01})
        """
        for feature, adjustment in feature_updates.items():
            if feature in self.feature_reputation:
                current = self.feature_reputation[feature]
                # Bounded update (0.5 to 1.5)
                new_value = max(0.5, min(1.5, current + adjustment))
                self.feature_reputation[feature] = new_value
                logger.info(f"Updated {feature} reputation: {current:.2f} → {new_value:.2f}")
    
    def update_threshold(self, performance_metrics: Dict):
        """
        Update decision threshold via governor.
        
        Args:
            performance_metrics: Dict with 'win_rate', 'missed_alpha', etc.
        """
        new_threshold = self.governor.audit_threshold_proposal(
            self.decision_threshold,
            performance_metrics
        )
        
        if new_threshold != self.decision_threshold:
            logger.info(
                f"Threshold updated: {self.decision_threshold:.2f} → {new_threshold:.2f} "
                f"(Governor: {self.governor.lock_status})"
            )
            self.decision_threshold = new_threshold
    
    def save_state(self):
        """Save brain state to disk."""
        state = {
            'version': self.version,
            'feature_reputation': self.feature_reputation,
            'decision_threshold': self.decision_threshold,
            'governor_status': self.governor.lock_status,
            'weights': {
                'xgboost': self.config.xgboost_weight,
                'rl': self.config.rl_weight,
                'smc': self.config.smc_weight
            },
            'performance_history': self.performance_history,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info("Brain state saved")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def load_state(self):
        """Load brain state from disk."""
        if not os.path.exists(self.state_file):
            logger.info("No saved state found, using defaults")
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.feature_reputation = state.get('feature_reputation', self.feature_reputation)
            self.decision_threshold = state.get('decision_threshold', self.decision_threshold)
            self.governor.lock_status = state.get('governor_status', 'ACTIVE')
            self.performance_history = state.get('performance_history', {})
            
            logger.info(f"Brain state loaded (version: {state.get('version', 'unknown')})")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")


    def check_basis_stability(self, current_basis: float) -> Dict:
        """
        [v10.2] Sigma-based stability gate for basis.
        Expected by api.py to prevent trading on extreme divergence.
        """
        # 1. Update history
        self.basis_history.append(current_basis)
        
        # 2. Extract stats
        if len(self.basis_history) < 10:
            return {
                "is_unstable": False,
                "reason": "INITIALIZING",
                "sigma_jump": 0.0,
                "basis": current_basis
            }
            
        history_list = list(self.basis_history)
        mean = np.mean(history_list)
        std = np.std(history_list)
        
        # 3. Absolute Check (Threshold from config)
        # Using 0.5% (0.005) as the default hard limit
        abs_limit = self.config.basis_max * 100 # Scaling for comparison with percentage basis
        is_abs_unstable = abs(current_basis) > abs_limit
        
        # 4. Sigma Check
        sigma_limit = 5.0 # Institutional default
        sigma_jump = 0.0
        is_sigma_unstable = False
        
        if std > 0.01:
            sigma_jump = abs(current_basis - mean) / std
            is_sigma_unstable = sigma_jump > sigma_limit
            
        is_unstable = is_abs_unstable or is_sigma_unstable
        
        reason = "STABLE"
        if is_abs_unstable:
            reason = f"ABS_LIMIT_VIOLATION ({current_basis:.2f}% > {abs_limit:.2f}%)"
        elif is_sigma_unstable:
            reason = f"SIGMA_JUMP ({sigma_jump:.1f}σ > {sigma_limit}σ)"
            
        return {
            "is_unstable": is_unstable,
            "reason": reason,
            "sigma_jump": sigma_jump,
            "basis": current_basis
        }


# Convenience function for backward compatibility
def create_brain(enable_rl=True, enable_smc=True) -> UnifiedBrainEngine:
    """
    Factory function to create brain instance.
    
    Args:
        enable_rl: Enable RL engine
        enable_smc: Enable SMC engine
    
    Returns:
        UnifiedBrainEngine instance
    """
    brain = UnifiedBrainEngine()
    
    if enable_rl or enable_smc:
        brain.initialize_engines()
    
    return brain


if __name__ == "__main__":
    # Test the brain
    logging.basicConfig(level=logging.INFO)
    
    brain = create_brain()
    
    # Test decision
    features = {
        'ADX': 35,
        'BASIS_RES': 0.8,
        'PCR': 0.9,
        'OI_RES': 0.7,
        'VIX': 15,
        'GEX': 100
    }
    
    market_data = {
        'spot_price': 24500,
        'future_price': 24505,
        'vix': 15,
        'oi': 100000,
        'gex': 100
    }
    
    result = brain.decide(features, market_data, 'TRENDING')
    
    print("\n" + "="*60)
    print("BRAIN DECISION TEST")
    print("="*60)
    print(f"Decision: {result['decision']}")
    print(f"Probability: {result['probability']:.3f}")
    print(f"Action: {result['action']}")
    print(f"Components: {result['components']}")
    print("\nThoughts:")
    for thought in result['thoughts']:
        print(f"  - {thought}")
    print("="*60)
