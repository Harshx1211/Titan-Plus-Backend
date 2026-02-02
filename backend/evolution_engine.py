import logging
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from supabase_manager import SupabaseManager
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
        if not history: return
        
        df = pd.DataFrame(history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        session_df = df[df['timestamp'].dt.strftime('%Y-%m-%d') == date_str]
        
        if session_df.empty: return
        
        # [v9.6.1] Robust Feature Parsing
        def _safe_parse(val):
            if isinstance(val, str):
                try: return json.loads(val)
                except: return {}
            return val if isinstance(val, dict) else {}
            
        if 'features' in session_df.columns:
            session_df['features'] = session_df['features'].apply(_safe_parse)
        
        # [Safety] If 'decision' column is missing (old records or empty fetch), bypass
        if 'decision' not in session_df.columns:
            logger.warning(f"EVOLUTION: 'decision' column missing in session data. Check Supabase schema.")
            return

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
                    # Penalize the feature that caused the block
                    if min_feat in rep_adjustments:
                        rep_adjustments[min_feat] -= 0.02

        # Analyze Bad Approvals (Losses)
        for _, row in approvals.iterrows():
            if row.get('efficacy') == 0: # Bad Trade
                features = row.get('features', {})
                if features:
                    max_feat = max(features, key=features.get)
                    # Penalize the feature that lied
                    if max_feat in rep_adjustments:
                        rep_adjustments[max_feat] -= 0.05
        
        # Analyze Good Approvals (Wins) - Conditional Credit
        # Only credit if context matches (e.g. Gamma near expiry)
        for _, row in approvals.iterrows():
            if row.get('efficacy') == 1:
                features = row.get('features', {})
                # Simple credit for now, will refine context in v9.1
                for f in features:
                    if f in rep_adjustments:
                         rep_adjustments[f] += 0.01

        # 4. Apply Reputation Updates (Inertial & Bounded)
        for feat, adj in rep_adjustments.items():
            current_rep = self.brain.feature_reputation.get(feat, 1.0)
            
            # Apply Decay (Return to Mean)
            current_rep = 1.0 + (current_rep - 1.0) * self.reputation_decay
            
            # Apply Adjustment
            new_rep = current_rep + adj
            
            # Hard Bounds [0.5, 1.5]
            new_rep = max(0.5, min(1.5, new_rep))
            self.brain.feature_reputation[feat] = new_rep
            
            logger.info(f"EVOLUTION: {feat} Reputation -> {new_rep:.2f}")

        # 5. Governor Audit for Thresholds
        # Calculate metrics for the Governor
        total_trades = len(approvals)
        wins = len(approvals[approvals['efficacy'] == 1])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 50.0
        
        # Simple missed alpha calc
        missed = len(blocks[blocks['efficacy'] == 0]) 
        total_opps = missed + wins
        missed_alpha_pct = (missed / total_opps * 100) if total_opps > 0 else 0.0
        
        metrics = {"win_rate": win_rate, "missed_alpha": missed_alpha_pct}
        
        # Check if we need to TIGHTEN thresholds (One-Way)
        # Note: In a real implementation, we'd update specific regime thresholds
        # For this prototype, we just log the Governor's decree.
        new_threshold = self.governor.audit_threshold_proposal(0.75, metrics)
        if new_threshold > 0.75:
             logger.warning(f"GOVERNOR DECREE: System needs tightening to {new_threshold}")
             self.brain.update_threshold(new_threshold) # [v9.7] Active Enforcement

        # Save State
        self.brain.save_state()
        
        return {
            "reputation_updates": self.brain.feature_reputation,
            "governor_status": self.governor.lock_status,
            "metrics": metrics
        }

if __name__ == "__main__":
    from brain_engine import BrainEngine
    brain = BrainEngine()
    evolver = EvolutionEngine(brain)
    evolver.evolve_session()
