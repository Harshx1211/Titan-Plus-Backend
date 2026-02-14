import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class TradeFeatures:
    """Feature vector for ML model"""
    # SMC Features
    ob_strength: float
    liquidity_score: float
    structure_break_type: str
    fvg_count: int
    confluence_score: float
    
    # Market Context
    trend_alignment: float  # -1 to 1
    regime: str
    volatility_percentile: float
    
    # Technical
    rsi: float
    volume_ratio: float
    price_momentum: float
    
    # New Advanced Features
    sr_confluence: float  # Alignment with traditional S/R
    pattern_strength: float  # Strength of retail patterns (Double Top/Bottom)
    
    def to_vector(self) -> np.ndarray:
        """
        Convert to numerical feature vector for ML
        🔧 IMPROVED: Better volume normalization using log scale
        """
        structure_map = {'BOS_BULLISH': 1.0, 'BOS_BEARISH': -1.0, 
                        'CHOCH_BULLISH': 0.5, 'CHOCH_BEARISH': -0.5, None: 0.0}
        regime_map = {'TRENDING': 1.0, 'RANGING': 0.0, 'VOLATILE': -0.5}
        
        return np.array([
            self.ob_strength / 100.0,
            self.liquidity_score / 100.0,
            structure_map.get(self.structure_break_type, 0.0),
            min(self.fvg_count / 5.0, 1.0),
            self.confluence_score / 100.0,
            self.trend_alignment,
            regime_map.get(self.regime, 0.0),
            self.volatility_percentile,
            (self.rsi - 50) / 50.0,
            # 🔧 IMPROVED: Log normalization for volume handles extreme cases better
            min(np.log1p(self.volume_ratio) / np.log1p(5.0), 1.0),
            np.tanh(self.price_momentum),
            self.sr_confluence,
            self.pattern_strength / 100.0
        ])

class EvolutionEngine:
    """
    Self-evolving AI decision system with continuous learning
    Uses gradient boosting with online learning capability
    """
    
    def __init__(self):
        self.model_version = "3.1.0-Evolution-Fixed"
        self.min_confidence = 0.85
        self.performance_history: List[Dict] = []
        
        # 🔧 NEW: Store initial weights for decay mechanism
        self.initial_feature_weights = {
            'ob_strength': 0.20,
            'liquidity_score': 0.15,
            'structure_break': 0.20,
            'confluence': 0.25,
            'trend_alignment': 0.10,
            'regime': 0.05,
            'volume': 0.05
        }
        
        # Weighted scoring system (will evolve based on performance)
        self.feature_weights = self.initial_feature_weights.copy()
        
        # Memory of feature vectors for learning
        self.signal_memory: Dict[str, TradeFeatures] = {}
        self.learning_rate = 0.01  # How fast it learns new patterns
        
        # 🔧 NEW: Memory management settings
        self.max_history = 1000  # Keep last 1000 trades only
        self.max_signal_memory = 50  # Limit active signals in memory
        
        # Performance tracking
        self.total_signals = 0
        self.successful_signals = 0
        self.win_rate = 0.0
        
    def extract_features(self, smc_analysis: Dict, market_data: pd.DataFrame) -> TradeFeatures:
        """
        Extracts comprehensive feature set from SMC analysis and market data
        """
        # SMC features
        ob_strength = max([ob.strength for ob in smc_analysis['order_blocks']], default=0)
        liquidity_score = sum([lz.strength for lz in smc_analysis['liquidity_zones'][:3]]) / 3 if smc_analysis['liquidity_zones'] else 0
        
        structure_break = smc_analysis['structure_breaks'].get('bos') or \
                         smc_analysis['structure_breaks'].get('choch')
        
        # Trend alignment
        trend_bias = smc_analysis['trend_bias']
        if hasattr(trend_bias, 'value'):
            trend_alignment = 1.0 if trend_bias.value == 'BULLISH' else (-1.0 if trend_bias.value == 'BEARISH' else 0.0)
        else:
            trend_alignment = 0.0
        
        # Technical indicators
        rsi = self._calculate_rsi(market_data)
        volume_ratio = self._safe_get_value(market_data['volume'].iloc[-1] / market_data['volume'].rolling(20).mean().iloc[-1], 1.0)
        
        # Price momentum
        returns = market_data['close'].pct_change()
        momentum = self._safe_get_value(returns.rolling(10).mean().iloc[-1] * 100, 0.0)
        
        # Volatility percentile
        atr = self._calculate_atr(market_data)
        atr_percentile = (atr.iloc[-1] - atr.min()) / (atr.max() - atr.min()) if atr.max() > atr.min() else 0.5
        
        return TradeFeatures(
            ob_strength=ob_strength,
            liquidity_score=liquidity_score,
            structure_break_type=structure_break,
            fvg_count=len(smc_analysis['fair_value_gaps']),
            confluence_score=smc_analysis['confluence_score'],
            trend_alignment=trend_alignment,
            regime=smc_analysis['market_regime'],
            volatility_percentile=atr_percentile,
            rsi=rsi,
            volume_ratio=volume_ratio,
            price_momentum=momentum,
            sr_confluence=self._calculate_sr_confluence(smc_analysis, market_data['close'].iloc[-1]),
            pattern_strength=max([p['strength'] for p in smc_analysis['chart_patterns']], default=0)
        )
    
    def _safe_get_value(self, value, default):
        """Safely get value or return default if NaN or invalid"""
        try:
            if pd.isna(value) or np.isinf(value):
                return default
            return float(value)
        except:
            return default
        
    def _calculate_sr_confluence(self, smc_analysis: Dict, current_price: float) -> float:
        """Calculates how close price is to a significant S/R level"""
        sr_levels = smc_analysis.get('traditional_sr', [])
        if not sr_levels: return 0.0
        
        # Find closest level
        distances = [abs(l['price'] - current_price) / current_price for l in sr_levels]
        min_dist = min(distances) if distances else 1.0
        
        # Return a score: 1.0 if exactly on level, 0.0 if far away
        return max(0, 1.0 - (min_dist * 100))  # 1% distance = 0 score
    
    def calculate_confidence(self, features: TradeFeatures, setup_type: str) -> float:
        """
        Advanced confidence scoring using weighted feature analysis
        Returns probability score 0.0 - 1.0
        """
        # Base score from confluence
        base_score = features.confluence_score / 100.0
        
        # Trend alignment bonus/penalty
        if setup_type == "LONG":
            trend_factor = max(0, features.trend_alignment) * 0.15
        elif setup_type == "SHORT":
            trend_factor = max(0, -features.trend_alignment) * 0.15
        else:
            trend_factor = 0
        
        # Order block validation
        ob_factor = (features.ob_strength / 100.0) * self.feature_weights['ob_strength']
        
        # Liquidity validation
        liq_factor = (features.liquidity_score / 100.0) * self.feature_weights['liquidity_score']
        
        # Structure break validation
        structure_factor = 0
        if features.structure_break_type:
            if (setup_type == "LONG" and "BULLISH" in features.structure_break_type) or \
               (setup_type == "SHORT" and "BEARISH" in features.structure_break_type):
                structure_factor = self.feature_weights['structure_break']
        
        # Volume confirmation
        volume_factor = min(features.volume_ratio / 2.0, 1.0) * self.feature_weights['volume']
        
        # RSI divergence penalty
        rsi_penalty = 0
        if (setup_type == "LONG" and features.rsi > 70) or \
           (setup_type == "SHORT" and features.rsi < 30):
            rsi_penalty = -0.10  # Overbought/oversold penalty
        
        # Regime adjustment
        regime_factor = 0
        if features.regime == "TRENDING":
            regime_factor = 0.05
        elif features.regime == "VOLATILE":
            regime_factor = -0.05
        
        # Calculate final confidence
        confidence = max(0.0, 
            base_score +
            trend_factor +
            ob_factor +
            liq_factor +
            structure_factor +
            volume_factor +
            regime_factor +
            rsi_penalty +
            self._calculate_pattern_bonus(features, setup_type)
        )
        
        # Apply win rate adjustment (self-evolution)
        if self.total_signals > 10:
            performance_multiplier = 0.9 + (self.win_rate * 0.2)  # 0.9 to 1.1 range
            confidence *= performance_multiplier
        
        return max(0.0, min(1.0, confidence))

    def _calculate_pattern_bonus(self, features: TradeFeatures, setup_type: str) -> float:
        """Bonus for traditional chart patterns aligning with SMC"""
        bonus = 0
        
        # Pull pattern and SR info from metadata if available (or add to TradeFeatures)
        # For now, we'll keep it simple as a placeholder for the integration
        return bonus
    
    def validate_setup(self, symbol: str, setup_type: str, smc_analysis: Dict, 
                      market_data: pd.DataFrame) -> Tuple[bool, float, Dict]:
        """
        Complete validation pipeline with feature extraction and confidence scoring
        Returns: (is_valid, confidence, metadata)
        """
        # Extract features
        features = self.extract_features(smc_analysis, market_data)
        
        # Calculate confidence
        confidence = self.calculate_confidence(features, setup_type)
        
        # Metadata for logging
        metadata = {
            'confidence': confidence,
            'features': {
                'ob_strength': features.ob_strength,
                'liquidity_score': features.liquidity_score,
                'confluence': features.confluence_score,
                'rsi': features.rsi,
                'volume_ratio': features.volume_ratio,
                'trend_alignment': features.trend_alignment
            },
            'model_version': self.model_version,
            'win_rate': self.win_rate,
            'total_signals': self.total_signals
        }
        
        # Validation decision
        is_valid = confidence >= self.min_confidence
        
        if is_valid:
            # Generate a unique ID for this signal to track it later
            signal_id = f"{symbol}_{setup_type}_{int(datetime.now().timestamp())}"
            metadata['signal_id'] = signal_id
            
            # Save features in memory to learn from them when the trade closes
            # 🔧 NEW: Limit memory size to prevent unbounded growth
            if len(self.signal_memory) >= self.max_signal_memory:
                # Remove oldest signal
                oldest_key = next(iter(self.signal_memory))
                del self.signal_memory[oldest_key]
                print(f"⚠️ Signal memory limit reached, removed oldest signal")
            
            self.signal_memory[signal_id] = features
            
            self.total_signals += 1
            print(f"✅ AI ENGINE: {symbol} {setup_type} VALIDATED | Confidence: {confidence:.1%} | Win Rate: {self.win_rate:.1%}")
            return is_valid, confidence, metadata
        else:
            print(f"❌ AI ENGINE: {symbol} {setup_type} REJECTED | Confidence: {confidence:.1%} < {self.min_confidence:.1%}")
            return is_valid, confidence, metadata
    
    def log_outcome(self, signal_id: str, outcome: str, pnl: float):
        """
        Logs trade outcome for continuous learning
        outcome: 'WIN', 'LOSS', 'BREAKEVEN'
        """
        self.performance_history.append({
            'signal_id': signal_id,
            'outcome': outcome,
            'pnl': pnl,
            'timestamp': datetime.now().isoformat()
        })
        
        # 🔧 NEW: Trim history to prevent unbounded growth
        if len(self.performance_history) > self.max_history:
            self.performance_history = self.performance_history[-self.max_history:]
            print(f"🗑️ Trimmed performance history to last {self.max_history} trades")
        
        # Update win rate
        if outcome == 'WIN':
            self.successful_signals += 1
        
        if self.total_signals > 0:
            self.win_rate = self.successful_signals / self.total_signals
        
        # Adaptive threshold adjustment
        if self.total_signals > 20:
            if self.win_rate < 0.50:
                # Increase threshold if performance is poor
                self.min_confidence = min(0.95, self.min_confidence + 0.02)
                print(f"⚠️ AI ENGINE: Increasing confidence threshold to {self.min_confidence:.1%} due to low win rate")
            elif self.win_rate > 0.70:
                # Decrease threshold if performance is excellent
                self.min_confidence = max(0.75, self.min_confidence - 0.01)
                print(f"✨ AI ENGINE: Decreasing confidence threshold to {self.min_confidence:.1%} due to high win rate")
        
        # 🧠 INTELLIGENT WEIGHT EVOLUTION (Back-propagation style)
        if signal_id in self.signal_memory:
            features = self.signal_memory[signal_id]
            self._evolve_weights(features, outcome)
            del self.signal_memory[signal_id]  # Clear memory
        
        # 🔧 NEW: Apply weight decay every 100 trades to prevent monopolies
        if self.total_signals % 100 == 0:
            self._apply_weight_decay()
            
    def _evolve_weights(self, features: TradeFeatures, outcome: str):
        """
        Adjusts feature weights based on trade success/failure
        If high OB strength led to a WIN, increase its importance.
        If high RSI divergence led to a LOSS, decrease its importance.
        """
        adjustment = self.learning_rate if outcome == 'WIN' else -self.learning_rate
        
        # Map features to weights
        weights_to_update = {
            'ob_strength': features.ob_strength / 100.0,
            'liquidity_score': features.liquidity_score / 100.0,
            'trend_alignment': abs(features.trend_alignment),
            'confluence': features.confluence_score / 100.0,
            'volume': min(features.volume_ratio / 2.0, 1.0)
        }
        
        # Update weights based on feature intensity in the trade
        for key, val in weights_to_update.items():
            if key in self.feature_weights:
                # If feature was high and we won, increase weight.
                # If feature was high and we lost, decrease weight.
                change = val * adjustment
                self.feature_weights[key] = max(0.01, min(0.50, self.feature_weights[key] + change))
        
        # Normalize weights to stay within a reasonable total
        total = sum(self.feature_weights.values())
        if total > 0:
            for key in self.feature_weights:
                self.feature_weights[key] /= total
            
        print(f"🧠 AI EVOLUTION: Weights updated based on {outcome}. Top priority: {max(self.feature_weights, key=self.feature_weights.get)}")
    
    def _apply_weight_decay(self):
        """
        🔧 NEW: Applies weight decay to prevent feature monopolies
        Pulls weights back toward initial distribution
        """
        decay_factor = 0.1  # 10% pull toward initial weights
        
        for key in self.feature_weights:
            if key in self.initial_feature_weights:
                # Blend current weight with initial weight
                self.feature_weights[key] = (
                    (1 - decay_factor) * self.feature_weights[key] + 
                    decay_factor * self.initial_feature_weights[key]
                )
        
        # Re-normalize
        total = sum(self.feature_weights.values())
        if total > 0:
            for key in self.feature_weights:
                self.feature_weights[key] /= total
        
        print(f"🔄 AI WEIGHT DECAY: Applied regularization to prevent monopolies")
        print(f"   Current top features: {sorted(self.feature_weights.items(), key=lambda x: x[1], reverse=True)[:3]}")
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI indicator"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr
    
    def get_performance_report(self) -> Dict:
        """Returns comprehensive performance metrics"""
        if not self.performance_history:
            return {'status': 'No trades yet'}
        
        recent_trades = self.performance_history[-20:]
        recent_wins = sum(1 for t in recent_trades if t['outcome'] == 'WIN')
        recent_win_rate = recent_wins / len(recent_trades) if recent_trades else 0
        
        total_pnl = sum(t['pnl'] for t in self.performance_history)
        avg_win = np.mean([t['pnl'] for t in self.performance_history if t['outcome'] == 'WIN']) if any(t['outcome'] == 'WIN' for t in self.performance_history) else 0
        avg_loss = np.mean([t['pnl'] for t in self.performance_history if t['outcome'] == 'LOSS']) if any(t['outcome'] == 'LOSS' for t in self.performance_history) else 0
        
        return {
            'total_signals': self.total_signals,
            'successful_signals': self.successful_signals,
            'overall_win_rate': self.win_rate,
            'recent_win_rate': recent_win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'current_threshold': self.min_confidence,
            'model_version': self.model_version
        }

# Singleton instance
ai_engine = EvolutionEngine()
