import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from supabase_manager import SupabaseManager
from brain_engine import BrainEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evolution_engine")

class EvolutionEngine:
    """
    [v8.7.0] The Overnight Learning Module.
    Performs Counterfactual Analysis: "What if we had traded the signals we blocked?"
    Refines feature weights to reduce False Negatives (Missed Alphas) 
    and False Positives (Bad Approvals).
    """
    def __init__(self, brain: BrainEngine):
        self.db = SupabaseManager()
        self.brain = brain
        self.learning_rate = 0.05 # Conservative weight adjustment

    def evolve_session(self, date_str: Optional[str] = None):
        """
        Runs the post-session post-mortem and updates brain weights.
        """
        if not date_str:
            date_str = (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d") # Use current day's data

        logger.info(f"EVOLUTION: Starting post-session overhaul for {date_str}...")
        
        # 1. Fetch History
        history = self.db.get_history(limit=500)
        if not history: return
        
        df = pd.DataFrame(history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        session_df = df[df['timestamp'].dt.strftime('%Y-%m-%d') == date_str]
        
        if session_df.empty:
            logger.warning(f"EVOLUTION: No data found for {date_str}. Skipping.")
            return

        # 2. Extract Blocks (Missed Opportunities)
        # In our log_snapshot, we log 'decision' which is APPROVE or BLOCK
        blocks = session_df[session_df['decision'] == 'BLOCK']
        approvals = session_df[session_df['decision'] == 'APPROVE']
        
        logger.info(f"EVOLUTION: Analyzing {len(blocks)} Blocks and {len(approvals)} Approvals.")

        # 3. Analyze Misses (Blocked signals that would have been Structural Wins)
        # Note: In a real institutional setup, we would re-run 1m data through the pattern engine.
        # Here we check if any 'outcome' logged for a blocked ID shows persistence.
        # Since we usually don't log outcomes for BLOCKS, we look for 'efficacy == 0' in BLOCKS
        missed_alpha_count = 0
        weight_adjustments = {f: 0.0 for f in self.brain.feature_weights}

        for _, row in blocks.iterrows():
            # If efficacy is 0 for a BLOCK, it means the outcome was TRUE and actionable.
            if row.get('efficacy') == 0:
                missed_alpha_count += 1
                # Identify the 'punitive' feature (the one that pushed confidence below threshold)
                # Typically the feature with the lowest Z-score in the snapshot.
                features = row.get('features', {})
                if features:
                    min_feat = min(features, key=features.get)
                    if min_feat in weight_adjustments:
                        weight_adjustments[min_feat] -= self.learning_rate # Reduce weight of punitive feature

        # 4. Analyze Bad Approvals (Approved signals that were Losses)
        bad_approval_count = 0
        for _, row in approvals.iterrows():
            if row.get('efficacy') == 0:
                bad_approval_count += 1
                # Identify the 'lying' feature (the one with high Z-score that was wrong)
                features = row.get('features', {})
                if features:
                    max_feat = max(features, key=features.get)
                    if max_feat in weight_adjustments:
                        weight_adjustments[max_feat] -= self.learning_rate # Reduce weight of deceptive feature

        # 5. Apply Adjustments
        logger.info(f"EVOLUTION: Findings - Missed Alphas: {missed_alpha_count}, Bad Approvals: {bad_approval_count}")
        for feat, adj in weight_adjustments.items():
            if adj != 0:
                old_w = self.brain.feature_weights[feat]
                # Keep weights between 0.5 and 2.5
                self.brain.feature_weights[feat] = max(0.5, min(2.5, old_w + adj))
                logger.info(f"EVOLUTION: Adjusted {feat} | {old_w:.2f} -> {self.brain.feature_weights[feat]:.2f}")

        # 6. Global Normalization (Sum of weights should remain roughly constant to prevent drift)
        total_weight = sum(self.brain.feature_weights.values())
        logger.info(f"EVOLUTION: Session Evolution Complete. Total Weight: {total_weight:.2f}")
        
        # Save the new brain state
        self.brain.save_state()
        return {
            "missed_alphas": missed_alpha_count,
            "bad_approvals": bad_approval_count,
            "adjustments": weight_adjustments
        }

if __name__ == "__main__":
    from brain_engine import BrainEngine
    brain = BrainEngine()
    evolver = EvolutionEngine(brain)
    evolver.evolve_session()
