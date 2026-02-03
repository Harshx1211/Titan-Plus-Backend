"""
Enhanced Test Suite for BrainEngine v2.0
Covers statistics, IV skew, NaN safety, migration, and learning.
"""
import unittest
import numpy as np
import pandas as pd
import math
import os
import json
import sys
from datetime import datetime

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

from brain_engine import BrainEngine, BrainConfig, Regime
from models import DecisionObject

class TestBrainV2(unittest.TestCase):
    
    def setUp(self):
        # Create a fresh brain for each test
        self.brain = BrainEngine(stage=3)
        # Ensure clean state for unit tests (ignore local brain_state.json)
        self.brain.feature_reputation = {f: 1.0 for f in self.brain.feature_weights}
        self.brain.authority = {k: 1.0 for k in self.brain.authority}
        
        # Suppress long logs during tests
        import logging
        logging.getLogger("brain_engine").setLevel(logging.ERROR)

    def test_bessel_correction(self):
        """Verify statistical correctness (Sample vs Population std)"""
        # Create known distribution: [10, 20, 30]
        # Population Std: 8.16
        # Sample Std (Bessel): 10.0
        history = [10.0, 20.0, 30.0]
        
        # Test Brain's normalization internal
        norm_val = self.brain._normalize_feature(40.0, history)
        
        # Manual Calculation with Bessel (ddof=1)
        mean = 20.0
        std = 10.0 # sqrt(((10-20)^2 + (20-20)^2 + (30-20)^2) / (3-1)) = sqrt(200/2) = 10
        z_score = (40.0 - mean) / std # (40-20)/10 = 2.0
        expected = 1 / (1 + math.exp(-1.5 * 2.0)) # 1 / (1 + e^-3) = 0.952
        
        self.assertAlmostEqual(norm_val, expected, places=3)
        print("Bessel Correction: Correct")

    def test_iv_skew_regime_awareness(self):
        """IV skew should treat trending differently from uncertain"""
        # 1. Trending Case
        boost_trend, _ = self.brain._apply_iv_skew_adjustment(
            boost=0.8, signal_intent="BULLISH", iv_skew=3.0, regime=Regime.TRENDING
        )
        # Expected: 0.8 * 0.85 = 0.68
        self.assertAlmostEqual(boost_trend, 0.68)
        
        # 2. Uncertain Case
        boost_uncert, _ = self.brain._apply_iv_skew_adjustment(
            boost=0.8, signal_intent="BULLISH", iv_skew=3.0, regime=Regime.UNCERTAIN
        )
        # Expected: 0.8 * 0.7 = 0.56
        self.assertAlmostEqual(boost_uncert, 0.56)
        
        self.assertGreater(boost_trend, boost_uncert)
        print("IV Skew Regime Awareness: Correct")

    def test_nan_handling(self):
        """Ensure NaN doesn't crash or corrupt state"""
        # Inject NaN
        val = self.brain._validate_feature_value(float('nan'), "ADX")
        self.assertIsNone(val)
        self.assertEqual(self.brain.metrics.nan_rejections, 1)
        
        # State should remain clean
        boost, thoughts = self.brain.get_confidence_boost({"ADX": float('nan')}, "TRENDING")
        self.assertEqual(boost, 0.5)
        self.assertTrue(any("Brain Warmup" in t for t in thoughts))
        print("NaN Safety: Correct")

    def test_migration_roundtrip(self):
        """State migration should preserve and bound values"""
        v1_state = {
            "logic_version": "v1.2.9_STATISTICAL_CAUDALITY_FREEZE",
            "feature_weights": {"ADX": 1.0, "OI_RES": 1.5},
            "feature_reputation": {"ADX": 2.0, "OI_RES": 0.4}, # Out of bounds
            "authority": {"TRENDING": 0.9}
        }
        
        migrated = self.brain.migrate_state_v1_to_v2(v1_state)
        
        # Check version
        self.assertTrue(migrated["logic_version"].startswith("v2."))
        
        # Check bounds: max 1.5, min 0.5
        self.assertEqual(migrated["feature_reputation"]["ADX"], 1.5)
        self.assertEqual(migrated["feature_reputation"]["OI_RES"], 0.5)
        
        # Check fill-in
        self.assertIn("SIDEWAYS_NORMAL", migrated["authority"])
        self.assertEqual(migrated["authority"]["SIDEWAYS_NORMAL"], 1.0)
        print("State Migration: Correct")

    def test_learning_updates(self):
        """Verify reputation and authority update correctly after log_snapshot"""
        # Manually lower authority to see growth (since it's capped at 1.0)
        self.brain.authority["TRENDING"] = 0.8
        
        # 1. Setup a decision
        decision_id, _ = self.brain.generate_decision(
            {"ADX": 30.0, "OI_RES": 0.5}, Regime.TRENDING, is_commit=False
        )
        initial_rep = self.brain.feature_reputation["ADX"]
        initial_auth = self.brain.authority["TRENDING"]
        
        # 2. Log a 'Win' outcome (Efficacy 1)
        # Since it was an APPROVE (boost 0.5 > 0.2 threshold), 
        # an outcome=True + is_actionable would be a win.
        self.brain.log_snapshot(decision_id, outcome=True, performance={"mfe": 20.0, "mae": 0.0})
        
        self.assertGreater(self.brain.feature_reputation["ADX"], initial_rep)
        self.assertGreater(self.brain.authority["TRENDING"], initial_auth)
        print("Learning Updates: Correct")

    def test_health_check(self):
        """Verify health check reporting"""
        health = self.brain.health_check()
        self.assertEqual(health["status"], "HEALTHY")
        self.assertEqual(health["version"], self.brain.LOGIC_VERSION)
        
        # Force degradation
        self.brain.authority["TRENDING"] = 0.1
        health = self.brain.health_check()
        self.assertEqual(health["status"], "DEGRADED")
        print("Health Checks: Correct")

    def test_cold_start_distinction(self):
        """v9.8: Both modes get neutral 0.5 boost during warmup"""
        # Filter mode (stage 3)
        boost_f, _ = self.brain.get_confidence_boost({"ADX": 25.0}, "TRENDING")
        self.assertEqual(boost_f, 0.5)
        
        # Passive mode (stage 1)
        self.brain.stage = 1
        boost_p, _ = self.brain.get_confidence_boost({"ADX": 25.0}, "TRENDING")
        self.assertEqual(boost_p, 0.5)
        print("Cold Start Logic: Correct (v9.8 Neutral)")

if __name__ == "__main__":
    unittest.main()
