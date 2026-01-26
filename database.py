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
        self.cloud_db = SupabaseManager()

    def log_intent(self, signal: TradeSignal, patterns: List[str] = []):
        """Logs the initial intent to Supabase."""
        signal_data = signal.dict()
        signal_data['patterns'] = ",".join(patterns)
        self.cloud_db.log_intent(signal_data)

    def log_outcome(self, signal_id: str, outcome: str, persistence: bool = False):
        """Logs the outcome to Supabase."""
        self.cloud_db.log_outcome(signal_id, outcome, persistence)

    def get_accuracy_report(self) -> Dict:
        """Calculates win rate from Supabase."""
        return self.cloud_db.get_accuracy_report()
    
    @property
    def db_path(self):
        # Kept for backward compatibility in api.py history call
        return "SUPABASE_CLOUD"

if __name__ == "__main__":
    db = DatabaseManager()
    print("Supabase Bridge Initialized")
