import logging
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from infrastructure import SupabaseManager
from brain_engine import BrainEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evolution_engine")

class MetaGovernor:
    """
    [v9.0] The One-Way Safety Valve.
    Audits all proposed changes. Can TIGHTEN thresholds automatically, 
    but NEVER LOOSEN them without manual override.
    """
    def __init__(self):
        self.min_win_rate = 40.0
        self.max_missed_alpha = 50.0 # Percentage
        self.lock_status = "ACTIVE" # ACTIVE, STRICT, OVERRIDE

    def audit_threshold_proposal(self, current_threshold: float, performance_metrics: Dict) -> float:
        """
        Evaluating whether to tighten or keep the threshold.
        Loosening is aggressively blocked.
        """
        win_rate = performance_metrics.get("win_rate", 50.0)
        missed_alpha = performance_metrics.get("missed_alpha", 0.0)
        
        # Rule 1: Auto-Tighten on poor performance
        if win_rate < self.min_win_rate:
            logger.warning(f"GOVERNOR: Win Rate {win_rate}% Critical. TIGHTENING threshold.")
            self.lock_status = "STRICT"
            return min(0.95, current_threshold + 0.05)
            
        # Rule 2: Block Auto-Loosening based on missed moves alone
        # Institutional Doctrine: Silence > False Confidence.
        if missed_alpha > self.max_missed_alpha:
            logger.info(f"GOVERNOR: High Missed Alpha ({missed_alpha}%). Loosening BLOCKED by Safety Valve.")
            return current_threshold # Return existing, do not lower.

        return current_threshold

class EvolutionEngine:
    """
    [v9.0.0] The Evolutionary Organism (Advisory Mode).
    Uses Feature Reputation (Bounded) instead of permanent mutation.
    """
    def __init__(self, brain: BrainEngine):
        self.db = SupabaseManager()
        self.brain = brain
        self.governor = MetaGovernor()
        # Reputation decays towards 1.0 (Half-life logic)
        self.reputation_decay = 0.95 

    def evolve_session(self, date_str: Optional[str] = None):
        """
        Runs the post-session post-mortem and updates Feature Reputation.
        """
        if not date_str:
            date_str = (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d")

        logger.info(f"EVOLUTION: Starting Advisory Audit for {date_str}...")
        
        # 1. Fetch History (Snapshots)
        history = self.db.get_snapshots(limit=500)
        if not history: return {"status": "SKIPPED", "reason": "No snapshots found in DB."}
        
        # [v9.6.2] FOOLPROOF DATA CLEANING
        cleaned_history = []
        for h in history:
            row = h.copy()
            feat = row.get('features')
            if isinstance(feat, str):
                try: row['features'] = json.loads(feat.replace("'", '"'))
                except: row['features'] = {}
            elif not isinstance(feat, dict):
                row['features'] = {}
            cleaned_history.append(row)

        df = pd.DataFrame(cleaned_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        session_df = df[df['timestamp'].dt.strftime('%Y-%m-%d') == date_str]
        
        if session_df.empty: 
            logger.info(f"EVOLUTION: No snapshot data found for {date_str}. Skipping.")
            return {"status": "SKIPPED", "reason": f"No signals found for {date_str}", "governor_status": "IDLE"}
        
        # [Safety] If 'decision' column is missing (old records or empty fetch), bypass
        if 'decision' not in session_df.columns:
            logger.warning(f"EVOLUTION: 'decision' column missing in session data. Check Supabase schema.")
            return {"status": "SKIPPED", "reason": "Missing 'decision' column.", "governor_status": "VETOED"}

        # 2. Extract Blocks & Approvals
        blocks = session_df[session_df['decision'] == 'BLOCK']
        approvals = session_df[session_df['decision'] == 'APPROVE']
        
        # 3. Calculate Reputation Adjustments (Bounded)
        rep_adjustments = {f: 0.0 for f in self.brain.feature_reputation}

        # Analyze Missed Alphas (Blocks that persisted)
        for _, row in blocks.iterrows():
            if row.get('efficacy') == 0: # Missed Win
                features = row.get('features', {})
                if features:
                    min_feat = min(features, key=features.get)
                    if min_feat in rep_adjustments:
                        rep_adjustments[min_feat] -= 0.02

        # Analyze Bad Approvals (Losses)
        for _, row in approvals.iterrows():
            if row.get('efficacy') == 0: # Bad Trade
                features = row.get('features', {})
                if features:
                    max_feat = max(features, key=features.get)
                    if max_feat in rep_adjustments:
                        rep_adjustments[max_feat] -= 0.05
        
        # Analyze Good Approvals (Wins)
        for _, row in approvals.iterrows():
            if row.get('efficacy') == 1:
                features = row.get('features', {})
                for f in features:
                    if f in rep_adjustments:
                         rep_adjustments[f] += 0.01

        # 4. Apply Reputation Updates (Inertial & Bounded)
        for feat, adj in rep_adjustments.items():
            current_rep = self.brain.feature_reputation.get(feat, 1.0)
            current_rep = 1.0 + (current_rep - 1.0) * self.reputation_decay
            new_rep = max(0.5, min(1.5, current_rep + adj))
            self.brain.feature_reputation[feat] = new_rep
            logger.info(f"EVOLUTION: {feat} Reputation -> {new_rep:.2f}")

        # 5. Governor Audit for Thresholds
        total_trades = len(approvals)
        wins = len(approvals[approvals['efficacy'] == 1])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 50.0
        
        missed = len(blocks[blocks['efficacy'] == 0]) 
        total_opps = missed + wins
        missed_alpha_pct = (missed / total_opps * 100) if total_opps > 0 else 0.0
        
        metrics = {"win_rate": win_rate, "missed_alpha": missed_alpha_pct}
        new_threshold = self.governor.audit_threshold_proposal(0.75, metrics)
        if new_threshold > 0.75:
             logger.warning(f"GOVERNOR DECREE: System needs tightening to {new_threshold}")
             self.brain.update_threshold(new_threshold)

        # Save State
        self.brain.save_state()
        
        return {
            "status": "SUCCESS",
            "reputation_updates": self.brain.feature_reputation,
            "governor_status": self.governor.lock_status,
            "metrics": metrics
        }

if __name__ == "__main__":
    from brain_engine import BrainEngine
    brain = BrainEngine()
    evolver = EvolutionEngine(brain)
    evolver.evolve_session()
