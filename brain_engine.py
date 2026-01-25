import pandas as pd
import logging
import sqlite3
import json
from supabase_manager import SupabaseManager
from datetime import datetime
from typing import Dict, List, Optional
from models import TradeSignal, SignalConfidence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BrainEngine:
    """
    The Filter Model. Tracks rolling feature importance.
    Starts as Stage 1 (Passive Observer).
    """
    def __init__(self, stage: int = 1):
        self.stage = stage # 1: Passive, 2: Shadow, 3: Filter
        self.cloud_db = SupabaseManager()
        self.feature_weights: Dict[str, float] = {
            "OI_CHG": 1.0,
            "PCR": 1.0,
            "BASIS": 1.0,
            "ADX": 1.0
        }

    # Remove _init_db as Supabase handles schema via dashboard
        
    def get_confidence_boost(self, features: Dict[str, float]) -> float:
        """
        Calculates score but logic varies by STAGE.
        """
        score = 0.0
        for feat, val in features.items():
            score += self.feature_weights.get(feat, 0.0) * val
        boost = min(max(score / 4.0, 0.0), 1.0)
        
        if self.stage == 1:
            # Stage 1: Passive observer - value is logged but NEVER affects the signal
            logger.info(f"BRAIN: Stage 1 (Passive) - Internal Confidence: {boost:.2f}")
            return 1.0 # No filtering effect
            
        return boost

    def log_snapshot(self, features: Dict[str, float], outcome: Optional[bool] = None):
        """
        Logs snapshots for Stage 1 & 2 training to Supabase.
        """
        try:
            outcome_int = 1 if outcome is True else 0 if outcome is False else None
            self.cloud_db.log_snapshot(features, outcome_int, self.stage)
            logger.info(f"BRAIN: Snapshot recorded in Supabase for {len(features)} features.")
        except Exception as e:
            logger.error(f"BRAIN ERROR: Failed to log snapshot to Supabase: {e}")

if __name__ == "__main__":
    brain = BrainEngine()
    feats = {"OI_CHG": 0.8, "PCR": 0.5, "BASIS": 0.2, "ADX": 0.9}
    print(f"Initial Confidence: {brain.get_confidence_boost(feats)}")
    # Simulate a loss where ADX was high
    brain.adjust_weights(False, feats)
    print(f"Post-Loss Weights: {brain.feature_weights}")
    print(f"Post-Loss Confidence: {brain.get_confidence_boost(feats)}")
