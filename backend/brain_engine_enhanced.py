"""
Titan Plus: Enhanced Brain Engine (Phase 3)
============================================
Neural decision core that combines:
1. XGBoost Classification (probability estimation)
2. RL Evolution Engine (spontaneous strategy discovery)
3. SMC Engine (institutional order flow)
4. Meta-Governor (safety valve)

Version: 9.9.9 (Phase 3 - Nuclear Edition)
Author: Titan Plus Development Team
"""

import logging
import pickle
import os
import numpy as np
import warnings
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

# [v9.9.9] Suppress legacy model version warnings
warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

# Import ML engines
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logging.warning("XGBoost not available. Using fallback logic.")

# Import custom engines
# Import custom engines
from rl_engine import RLEvolutionEngine
from rl_engine_ppo import PPOAgent
from smc_engine import GrandmasterSMCEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brain_engine")


class EnhancedBrainEngine:
    """
    The Nuclear Decision Core
    
    Three-layer intelligence:
    1. XGBoost: Pattern recognition and probability estimation
    2. RL Engine: Self-learning and strategy discovery (DQN/PPO)
    3. SMC Engine: Institutional order flow analysis
    
    Final decision requires confluence across all three layers.
    """
    
    def __init__(self, enable_rl: bool = True, enable_smc: bool = True, use_ppo: bool = True):
        # Configuration
        self.enable_rl = enable_rl
        self.use_ppo = use_ppo # [Phase 4] PPO Toggle
        self.enable_smc = enable_smc
        self.decision_threshold = 0.75  # Probability threshold for XGBoost
        self.rl_weight = 0.3  # Weight of RL recommendation
        self.smc_weight = 0.3  # Weight of SMC score
        self.xgb_weight = 0.4  # Weight of XGBoost score
        
        # Feature reputation (bounded weights for adaptive importance)
        self.feature_reputation = {
            'rsi': 1.0,
            'adx': 1.0,
            'basis': 1.0,
            'pcr': 1.0,
            'vix': 1.0,
            'gex': 1.0,
            'volume': 1.0
        }
        
        # Initialize XGBoost model
        self.model: Optional[XGBClassifier] = None
        self._load_xgboost_model()
        
        # Initialize RL Engine
        self.rl_engine = None
        self.ppo_agent = None
        
        if self.enable_rl:
            try:
                if self.use_ppo:
                    self.ppo_agent = PPOAgent()
                    logger.info("BRAIN: RL Engine (PPO) activated - Phase 4")
                else:
                    self.rl_engine = RLEvolutionEngine()
                    self.rl_engine.load_state("rl_state.pt")
                    logger.info("BRAIN: RL Engine (DQN) activated")
            except Exception as e:
                logger.warning(f"BRAIN: RL Engine initialization failed: {e}")
                self.enable_rl = False
        
        # Initialize SMC Engine
        self.smc_engine: Optional[GrandmasterSMCEngine] = None
        if self.enable_smc:
            try:
                self.smc_engine = GrandmasterSMCEngine()
                logger.info("BRAIN: SMC Engine activated")
            except Exception as e:
                logger.warning(f"BRAIN: SMC Engine initialization failed: {e}")
                self.enable_smc = False
        
        # Meta-vetoes (institutional safety checks)
        self.meta_vetoes = {
            'basis_instability': True,
            'vix_spike': True,
            'low_liquidity': True,
            'extreme_gex': True
        }
        
        logger.info(f"BRAIN: Enhanced Brain Engine initialized (RL={enable_rl}, SMC={enable_smc})")
    
    def _load_xgboost_model(self):
        """Load pre-trained XGBoost model (Optuna > Legacy)"""
        # [Phase 4] Prioritize Optimized Model
        model_paths = [
            'models/xgboost_optimized.json', 
            'brain_model.pkl', 
            '/home/claude/brain_model.pkl', 
            'models/brain_model.pkl'
        ]
        
        for path in model_paths:
            if os.path.exists(path):
                try:
                    # [Phase 4] JSON Support for XGBoost Native Format
                    if path.endswith('.json'):
                        import xgboost as xgb
                        self.model = xgb.XGBClassifier()
                        self.model.load_model(path)
                        logger.info(f"BRAIN: Optimized XGBoost loaded from {path}")
                        return

                    # Legacy Pickle Support
                    with open(path, 'rb') as f:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            data = pickle.load(f)
                    
                    if isinstance(data, dict) and 'model' in data:
                        self.model = data['model']
                    else:
                        self.model = data
                    
                    logger.info(f"BRAIN: Legacy XGBoost model loaded from {path}")
                    return
                except Exception as e:
                    logger.warning(f"BRAIN: Failed to load model from {path}: {e}")
        
        logger.warning("BRAIN: No XGBoost model found. Operating in heuristic mode.")
    
    
    def update_raw_history(self, raw_data: Dict):
        """Legacy method for API compatibility - no-op in Phase 3"""
        pass

    def analyze_institutional_logic(self, *args, **kwargs):
        """Legacy method for API compatibility - no-op in Phase 3"""
        return {}

    def decide(self, features: Dict, market_data: Dict = {}, ohlcv_df=None, regime: str = "NEUTRAL", **kwargs) -> Dict:
        """
        Nuclear Decision Function
        
        Args:
            features: Technical indicators and Greeks
            market_data: Current market snapshot
            ohlcv_df: Historical OHLCV data for SMC analysis
            regime: Current market regime
        """
        # [HARSH AUDIT FIX] Robust Feature Normalization
        # 1. Merge kwargs into features (api.py passes iv_skew via kwargs sometimes)
        if kwargs.get('iv_skew'): features['iv_skew'] = kwargs['iv_skew']
        
        # 2. Normalize Keys (Legacy API sends UPPERCASE, Brain needs lowercase)
        norm_features = {k.lower(): v for k, v in features.items()}
        
        # 3. Map Legacy Keys to Internal Names
        if 'basis_res' in norm_features: norm_features['basis'] = norm_features['basis_res']
        if 'spot_price' in norm_features: 
            norm_features['close'] = norm_features['spot_price'] # RL state needs close
            # Populate market_data if empty (api.py sends empty dict in generate_decision)
            if not market_data:
                market_data = {
                    'spot_price': norm_features['spot_price'],
                    'future_price': norm_features.get('future_price', norm_features['spot_price']),
                    'volume': norm_features.get('volume', 100000)
                }
        
        # Replace original features with normalized ones for internal consumption
        features = norm_features

        # Initialize decision components
        xgb_score = 0.5
        rl_score = 0.5
        smc_score = 0.5
        veto_reasons = []
        
        # === LAYER 1: XGBoost Probability Estimation ===
        xgb_result = self._xgboost_analysis(features)
        xgb_score = xgb_result['probability']
        
        # === LAYER 2: Meta-Vetoes (Institutional Safety) ===
        veto_result = self._apply_meta_vetoes(features, market_data)
        if veto_result['vetoed']:
            veto_reasons.extend(veto_result['reasons'])
            # Hard veto = override everything
            if veto_result['hard_veto']:
                return {
                    'decision': 'BLOCK',
                    'probability': 0.0,
                    'confidence': 1.0,
                    'components': {
                        'xgboost': xgb_result,
                        'rl': None,
                        'smc': None,
                        'vetoes': veto_result
                    },
                    'veto_reasons': veto_reasons,
                    'recommendation': 'HOLD',
                    'source': 'META_VETO'
                }
        
        # === LAYER 3: RL Engine Analysis ===
        rl_result = None
        if self.enable_rl:
            try:
                # Build RL state from features and market data
                rl_state_dict = self._build_rl_state(features, market_data, regime)
                
                # [Phase 4] PPO vs DQN Logic
                if self.use_ppo and self.ppo_agent:
                    # PPO expects a vector, not a dict. Helper needed.
                    state_vec = self._build_ppo_vector(rl_state_dict)
                    action, log_prob, _ = self.ppo_agent.get_action(state_vec)
                    
                    # [Audit Fix] Correct Action Mapping to match DQN
                    # 0=BUY_CALL, 1=BUY_PUT, 2=HOLD
                    rec_map = {0: 'BUY_CALL', 1: 'BUY_PUT', 2: 'HOLD'}
                    recommendation = rec_map.get(action, 'HOLD')
                    
                    # Confidence Logic: Active trades get higher base confidence
                    conf = 0.7 if recommendation != 'HOLD' else 0.5
                    
                    rl_result = {
                        "action": recommendation,
                        "confidence": conf,
                        "q_values": [log_prob] # Logging log_prob as "Value"
                    }
                elif self.rl_engine:
                    rl_result = self.rl_engine.get_recommendation(rl_state_dict)
                
                # Convert RL confidence to score
                rl_score = rl_result['confidence'] if rl_result else 0.5
            except Exception as e:
                logger.error(f"BRAIN: RL analysis failed: {e}")
                rl_score = 0.5
        
        # === LAYER 4: SMC Engine Analysis ===
        smc_result = None
        if self.enable_smc and self.smc_engine and ohlcv_df is not None:
            try:
                smc_result = self.smc_engine.analyze(ohlcv_df)
                
                # Convert confluence score to normalized score
                smc_score = smc_result['confluence_score'] / 100.0
            except Exception as e:
                logger.error(f"BRAIN: SMC analysis failed: {e}")
                smc_score = 0.5
        
        # === CONFLUENCE CALCULATION ===
        # Weighted average of all three components
        final_score = (
            self.xgb_weight * xgb_score +
            self.rl_weight * rl_score +
            self.smc_weight * smc_score
        )
        
        # Determine decision
        decision = 'APPROVE' if final_score >= self.decision_threshold else 'BLOCK'
        
        # Calculate confidence (how far from threshold)
        confidence = abs(final_score - self.decision_threshold) / self.decision_threshold
        confidence = min(1.0, confidence)
        
        # Determine recommendation (action to take if approved)
        recommendation = 'HOLD'
        if decision == 'APPROVE':
            if rl_result and rl_result['action'] in ['BUY_CALL', 'BUY_PUT']:
                recommendation = rl_result['action']
            elif smc_result:
                # Use SMC market structure
                if smc_result['market_structure'] == 'BULLISH':
                    recommendation = 'BUY_CALL'
                elif smc_result['market_structure'] == 'BEARISH':
                    recommendation = 'BUY_PUT'
            else:
                # Fallback to regime
                if regime == 'TRENDING_UP':
                    recommendation = 'BUY_CALL'
                elif regime == 'TRENDING_DOWN':
                    recommendation = 'BUY_PUT'
        
        result = {
            'decision': decision,
            'probability': final_score,
            'confidence': confidence,
            'components': {
                'xgboost': xgb_result,
                'rl': rl_result,
                'smc': smc_result
            },
            'weights': {
                'xgboost': self.xgb_weight,
                'rl': self.rl_weight,
                'smc': self.smc_weight
            },
            'veto_reasons': veto_reasons,
            'recommendation': recommendation,
            'source': 'ENHANCED_BRAIN',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"BRAIN DECISION: {decision} (prob={final_score:.3f}, conf={confidence:.3f}) -> {recommendation}")
        
        return result
    
    
    def _build_ppo_vector(self, state_dict: Dict) -> np.ndarray:
        """
        [Phase 4] Converts state dictionary to 25-dim vector for PPO Agent.
        Must match the schema in RLEvolutionEngine.state_to_tensor
        """
        vector = []
        
        # Technical indicators (normalized)
        indicators = state_dict.get('indicators', {})
        vector.extend([
            indicators.get('rsi', 50.0) / 100.0,
            indicators.get('adx', 20.0) / 100.0,
            indicators.get('atr', 100.0) / 500.0,
            indicators.get('basis', 0.0) / 10.0,
            indicators.get('pcr', 1.0),
            indicators.get('vix', 15.0) / 50.0,
            indicators.get('iv_skew', 1.0)
        ])
        
        # Price action
        price = state_dict.get('price', {})
        vector.extend([
            price.get('close', 25000.0) / 30000.0,
            price.get('high', 25100.0) / 30000.0,
            price.get('low', 24900.0) / 30000.0,
            price.get('volume', 1000000) / 10000000.0,
            price.get('future_premium', 5.0) / 100.0
        ])
        
        # Greeks
        greeks = state_dict.get('greeks', {})
        vector.extend([
            greeks.get('call_gamma', 0.002) * 1000,
            greeks.get('put_gamma', 0.002) * 1000,
            greeks.get('net_gex', 0.0) / 1000000.0,
            greeks.get('gamma_ratio', 1.0)
        ])
        
        # SMC Signals (binary/continuous)
        smc = state_dict.get('smc', {})
        vector.extend([
            1.0 if smc.get('order_block', False) else 0.0,
            1.0 if smc.get('fvg', False) else 0.0,
            1.0 if smc.get('liquidity_sweep', False) else 0.0,
            smc.get('imbalance_score', 0.0)
        ])
        
        # Regime (one-hot encoding of 5 regimes)
        regime = state_dict.get('regime', 'NEUTRAL')
        regime_map = {
            'TRENDING_UP': [1, 0, 0, 0, 0],
            'TRENDING_DOWN': [0, 1, 0, 0, 0],
            'SIDEWAYS_STRONG': [0, 0, 1, 0, 0],
            'SIDEWAYS_WEAK': [0, 0, 0, 1, 0],
            'NEUTRAL': [0, 0, 0, 0, 1]
        }
        vector.extend(regime_map.get(regime, [0, 0, 0, 0, 1]))
        
        return np.array(vector, dtype=np.float32)

    def _xgboost_analysis(self, features: Dict) -> Dict:
        """Run XGBoost model inference"""
        if self.model is None:
            # Fallback heuristic
            return {
                'probability': 0.6,
                'features_used': [],
                'source': 'HEURISTIC_FALLBACK'
            }
        
        try:
            # Extract and normalize features with reputation weighting
            feature_vector = self._extract_feature_vector(features)
            
            # Predict probability
            proba = self.model.predict_proba([feature_vector])[0]
            success_prob = proba[1] if len(proba) > 1 else proba[0]
            
            return {
                'probability': float(success_prob),
                'features_used': list(features.keys()),
                'feature_vector': feature_vector,
                'source': 'XGBOOST_MODEL'
            }
        except Exception as e:
            logger.error(f"BRAIN: XGBoost inference failed: {e}")
            return {
                'probability': 0.5,
                'features_used': [],
                'source': 'ERROR_FALLBACK',
                'error': str(e)
            }
    
    def _extract_feature_vector(self, features: Dict) -> List[float]:
        """
        Extract normalized feature vector from features dict
        Expected features: [rsi, adx, atr, basis, pcr, vix, iv_skew]
        """
        vector = []
        
        # Apply reputation weighting (adaptive importance)
        for key in ['rsi', 'adx', 'atr', 'basis', 'pcr', 'vix', 'iv_skew']:
            raw_value = features.get(key, 0.0)
            reputation = self.feature_reputation.get(key, 1.0)
            weighted_value = raw_value * reputation
            vector.append(weighted_value)
        
        return vector
    
    def _apply_meta_vetoes(self, features: Dict, market_data: Dict) -> Dict:
        """
        Apply institutional meta-vetoes (safety checks)
        
        Returns:
            {
                'vetoed': bool,
                'hard_veto': bool,  # If True, override everything
                'reasons': List[str]
            }
        """
        vetoed = False
        hard_veto = False
        reasons = []
        
        # Veto 1: Basis Instability (spread too wide)
        if self.meta_vetoes.get('basis_instability'):
            basis = features.get('basis', 0.0)
            if abs(basis) > 5.0:  # Basis > 5 points
                vetoed = True
                reasons.append(f"BASIS_INSTABILITY: {basis:.2f}")
        
        # Veto 2: VIX Spike (market panic)
        if self.meta_vetoes.get('vix_spike'):
            vix = features.get('vix', 15.0)
            if vix > 30.0:
                vetoed = True
                hard_veto = True  # VIX spike = hard stop
                reasons.append(f"VIX_SPIKE: {vix:.2f}")
        
        # Veto 3: Low Liquidity (low volume)
        if self.meta_vetoes.get('low_liquidity'):
            volume = market_data.get('volume', 0)
            # Check if volume is significantly below average (simplified)
            if volume < 100000:
                vetoed = True
                reasons.append(f"LOW_LIQUIDITY: {volume}")
        
        # Veto 4: Extreme GEX (gamma imbalance)
        if self.meta_vetoes.get('extreme_gex'):
            gex = features.get('gex', 0.0)
            if abs(gex) > 10000000:  # 10M+ gamma exposure
                vetoed = True
                reasons.append(f"EXTREME_GEX: {gex:.0f}")
        
        return {
            'vetoed': vetoed,
            'hard_veto': hard_veto,
            'reasons': reasons
        }
    
    def _build_rl_state(self, features: Dict, market_data: Dict, regime: str) -> Dict:
        """Build RL state dictionary from features and market data"""
        return {
            'indicators': {
                'rsi': features.get('rsi', 50.0),
                'adx': features.get('adx', 20.0),
                'atr': features.get('atr', 100.0),
                'basis': features.get('basis', 0.0),
                'pcr': features.get('pcr', 1.0),
                'vix': features.get('vix', 15.0),
                'iv_skew': features.get('iv_skew', 1.0)
            },
            'price': {
                'close': market_data.get('spot_price', 25000.0),
                'high': market_data.get('spot_price', 25000.0) * 1.002,
                'low': market_data.get('spot_price', 25000.0) * 0.998,
                'volume': market_data.get('volume', 1000000),
                'future_premium': market_data.get('future_price', 25005.0) - market_data.get('spot_price', 25000.0)
            },
            'greeks': {
                'call_gamma': features.get('call_gamma', 0.002),
                'put_gamma': features.get('put_gamma', 0.002),
                'net_gex': features.get('gex', 0.0),
                'gamma_ratio': features.get('gamma_ratio', 1.0)
            },
            'smc': {
                'order_block': False,  # Filled by SMC engine if available
                'fvg': False,
                'liquidity_sweep': False,
                'imbalance_score': 0.0
            },
            'regime': regime
        }
    
    def update_threshold(self, new_threshold: float):
        """Update decision threshold (called by Governor)"""
        old_threshold = self.decision_threshold
        self.decision_threshold = max(0.5, min(0.95, new_threshold))
        logger.warning(f"BRAIN: Threshold updated {old_threshold:.2f} -> {self.decision_threshold:.2f}")
    
    def save_state(self, path: str = "brain_state.json"):
        """Save brain state to disk"""
        state = {
            'decision_threshold': self.decision_threshold,
            'feature_reputation': self.feature_reputation,
            'meta_vetoes': self.meta_vetoes,
            'weights': {
                'xgboost': self.xgb_weight,
                'rl': self.rl_weight,
                'smc': self.smc_weight
            },
            'timestamp': datetime.now().isoformat()
        }
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
        
        # Save RL state if enabled
        if self.enable_rl and self.rl_engine:
            self.rl_engine.save_state("rl_state.pt")
        
        logger.info(f"BRAIN: State saved to {path}")
    
    def load_state(self, path: str = "brain_state.json"):
        """Load brain state from disk"""
        try:
            with open(path, 'r') as f:
                state = json.load(f)
            
            self.decision_threshold = state.get('decision_threshold', 0.75)
            self.feature_reputation = state.get('feature_reputation', self.feature_reputation)
            self.meta_vetoes = state.get('meta_vetoes', self.meta_vetoes)
            
            weights = state.get('weights', {})
            self.xgb_weight = weights.get('xgboost', 0.4)
            self.rl_weight = weights.get('rl', 0.3)
            self.smc_weight = weights.get('smc', 0.3)
            
            logger.info(f"BRAIN: State loaded from {path}")
            return True
        except FileNotFoundError:
            logger.warning(f"BRAIN: No saved state found at {path}")
            return False
        except Exception as e:
            logger.error(f"BRAIN: Error loading state: {e}")
            return False

    def check_basis_stability(self, basis: float) -> Dict:
        """
        Check if basis (spot-future spread) is stable.
        Legacy support for API v1.
        """
        threshold = 5.0  # Implicit threshold from vetoes
        is_unstable = abs(basis) > threshold
        return {
            "is_unstable": is_unstable,
            "basis": basis,
            "threshold": threshold,
            "msg": f"Basis {basis:.2f}% > {threshold}%" if is_unstable else "Stable"
        }

    def log_snapshot(self, decision_id: str, outcome: bool, performance: Dict, freeze_authority: bool = False):
        """
        Log trade outcome and update RL engine if applicable.
        """
        logger.info(f"BRAIN SNAPSHOT: ID={decision_id} | WIN={outcome} | PERF={performance}")
        
        # Update RL Experience if available
        # Phase 3: Calculate reward and log for offline training
        if self.enable_rl and self.rl_engine:
            # Reward Calculation: +1 for Win, -1 for Loss
            # Bonus: +0.1 for every 1% MFE (Maximum Favorable Excursion)
            mfe_bonus = (performance.get('mfe', 0.0) / 100.0) * 0.1
            reward = (1.0 if outcome else -1.0) + mfe_bonus
            
            logger.info(f"BRAIN: Calculated Reward: {reward:.2f}")
            # In future: self.rl_engine.update(reward)

    def generate_decision(self, features: Dict, regime: str, is_commit: bool = False, pattern_score: float = 0.0, **kwargs) -> Tuple[str, List[str]]:
        """
        Legacy alias for decide() to support API backward compatibility.
        """
        result = self.decide(features, market_data={}, regime=regime)
        reasons = result['veto_reasons']
        
        # Format for legacy API: (DECISION, [reasons])
        # Legacy API expected "GO" or "WAIT"
        decision = "GO" if result['decision'] == 'APPROVE' else "WAIT"
        
        return decision, reasons


if __name__ == "__main__":
    # Test Enhanced Brain Engine
    logger.info("Testing Enhanced Brain Engine...")
    
    brain = EnhancedBrainEngine(enable_rl=True, enable_smc=True)
    
    # Test data
    features = {
        'rsi': 65.0,
        'adx': 35.0,
        'atr': 120.0,
        'basis': 2.5,
        'pcr': 0.85,
        'vix': 18.0,
        'iv_skew': 1.1,
        'call_gamma': 0.0025,
        'put_gamma': 0.0018,
        'gex': 500000,
        'gamma_ratio': 1.4
    }
    
    market_data = {
        'spot_price': 25500.0,
        'future_price': 25508.0,
        'volume': 5000000,
        'pcr': 0.85
    }
    
    # Make decision
    decision = brain.decide(features, market_data, regime='TRENDING_UP')
    
    print("\n=== Brain Decision ===")
    print(json.dumps(decision, indent=2))
    
    # Save state
    brain.save_state("/home/claude/test_brain_state.json")
    
    print("\nEnhanced Brain Engine test complete!")
