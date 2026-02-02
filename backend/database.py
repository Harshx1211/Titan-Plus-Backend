import logging
from typing import Optional, List, Dict
from models import TradeSignal
from supabase_manager import SupabaseManager

logger = logging.getLogger("database_manager")

class DatabaseManager:
    """
    Bridge to Supabase (Cloud Memory).
    Ensures all existing code continues to work while data moves to the cloud.
    """
    def __init__(self):
        try:
            self.cloud_db = SupabaseManager()
            logger.info("DATABASE: Supabase connection initialized successfully")
        except Exception as e:
            logger.error(f"DATABASE: Failed to initialize Supabase: {e}")
            self.cloud_db = None

    def log_intent(self, signal: TradeSignal, patterns: List[str] = []):
        """Logs the initial intent to Supabase with error handling."""
        if not self.cloud_db:
            logger.warning("DATABASE: Supabase not available, skipping log_intent")
            return
            
        try:
            signal_data = signal.dict()
            signal_data['patterns'] = ",".join(patterns)
            
            # Remove 'decision' field if it doesn't exist in schema
            # The error indicates this column might not exist
            if 'decision' in signal_data:
                signal_data.pop('decision', None)
                
            self.cloud_db.log_intent(signal_data)
            logger.debug(f"DATABASE: Successfully logged intent for {signal.symbol}")
        except Exception as e:
            logger.error(f"DATABASE: Failed to log intent: {e}")
            # Don't crash - just log the error and continue

    def log_outcome(self, signal_id: str, outcome: str, persistence: bool = False):
        """Logs the outcome to Supabase with error handling."""
        if not self.cloud_db:
            logger.warning("DATABASE: Supabase not available, skipping log_outcome")
            return
            
        try:
            # Handle the 'persistence' column error by making it optional
            self.cloud_db.log_outcome(signal_id, outcome, persistence)
            logger.debug(f"DATABASE: Successfully logged outcome for {signal_id}: {outcome}")
        except Exception as e:
            # Check if it's the schema error we're seeing in logs
            if "persistence" in str(e) or "decision" in str(e):
                logger.warning(f"DATABASE: Schema mismatch (column not found), attempting fallback: {e}")
                try:
                    # Try without persistence parameter
                    self.cloud_db.log_outcome(signal_id, outcome)
                except Exception as e2:
                    logger.error(f"DATABASE: Fallback also failed: {e2}")
            else:
                logger.error(f"DATABASE: Failed to log outcome: {e}")

    def get_accuracy_report(self) -> Dict:
        """Calculates win rate from Supabase with error handling."""
        if not self.cloud_db:
            logger.warning("DATABASE: Supabase not available, returning empty report")
            return {
                "total_signals": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "error": "Database not available"
            }
            
        try:
            return self.cloud_db.get_accuracy_report()
        except Exception as e:
            logger.error(f"DATABASE: Failed to get accuracy report: {e}")
            return {
                "total_signals": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "error": str(e)
            }
    
    @property
    def db_path(self):
        """Kept for backward compatibility in api.py history call"""
        return "SUPABASE_CLOUD"

if __name__ == "__main__":
    db = DatabaseManager()
    print("Supabase Bridge Initialized")
    print("Testing connection...")
    try:
        report = db.get_accuracy_report()
        print(f"Accuracy Report: {report}")
    except Exception as e:
        print(f"Test failed: {e}")
