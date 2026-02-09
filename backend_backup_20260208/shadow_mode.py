#!/usr/bin/env python3
"""
Shadow mode: Run ML and Statistical engines in parallel
Compares predictions without affecting actual trading
"""

import os
import json
from datetime import datetime
from brain_engine import BrainEngine
from brain_engine_ml import BrainEngineML

class ShadowMode:
    """Run both engines and compare results"""
    
    def __init__(self):
        self.brain_stats = BrainEngine(stage=2)
        self.brain_ml = BrainEngineML(stage=2)
        self.comparison_log = "shadow_comparisons.json"
        self.comparisons = []
        
    def compare_predictions(self, features, regime, **kwargs):
        """Get predictions from both engines"""
        
        # Statistical prediction
        stat_conf, stat_thoughts = self.brain_stats.get_confidence_boost(
            features, regime.value
        )
        
        # ML prediction
        ml_conf, ml_thoughts = self.brain_ml.get_confidence_boost_ml(
            features, regime.value
        )
        
        # Calculate agreement
        threshold = 0.60
        stat_decision = "APPROVE" if stat_conf > threshold else "BLOCK"
        ml_decision = "APPROVE" if ml_conf > threshold else "BLOCK"
        agree = stat_decision == ml_decision
        
        # Log comparison
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "stat_confidence": round(stat_conf, 3),
            "ml_confidence": round(ml_conf, 3),
            "stat_decision": stat_decision,
            "ml_decision": ml_decision,
            "agreement": agree,
            "diff": round(abs(stat_conf - ml_conf), 3),
            "regime": regime.value,
            "features": features
        }
        
        self.comparisons.append(comparison)
        self._save_comparison()
        
        # Print real-time comparison
        print(f"\nSHADOW MODE COMPARISON - {datetime.now().strftime('%H:%M:%S')}")
        print(f"Regime: {regime.value}")
        print(f"Statistical: {stat_conf:.3f} ({stat_decision})")
        print(f"ML: {ml_conf:.3f} ({ml_decision})")
        print(f"Agreement: {'✓' if agree else '✗'}")
        
        return stat_conf, stat_thoughts
    
    def _save_comparison(self):
        try:
            with open(self.comparison_log, 'w') as f:
                json.dump(self.comparisons, f, indent=2)
        except: pass

if __name__ == "__main__":
    from models import Regime
    shadow = ShadowMode()
    test_features = {"ADX": 35, "BASIS_RES": 0.8, "PCR": 0.9, "OI_RES": 0.7}
    shadow.compare_predictions(test_features, Regime.TRENDING)
