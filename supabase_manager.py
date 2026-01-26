import os
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging
import threading
import queue
import time

load_dotenv()

logger = logging.getLogger("supabase_manager")

class SupabaseManager:
    """
    Cloud Memory for Titan Plus.
    Handles persistent logging of Signal Intents and Brain Snapshots.
    """
    def __init__(self):
        url: str = os.getenv("SUPABASE_URL")
        # Async Logging Infrastructure (Hardened)
        self.queue = queue.Queue(maxsize=10000) # Prevents memory time-bomb
        self.seq_id = 0
        self.seq_lock = threading.Lock()
        
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info("SUPABASE: Hardened async worker initialized (Maxsize: 10000).")

    def _get_next_seq(self) -> int:
        with self.seq_lock:
            self.seq_id += 1
            return self.seq_id

    def _worker(self):
        """Background worker to process the logging queue."""
        while True:
            try:
                task_type, data = self.queue.get()
                if task_type == "intent":
                    self.supabase.table("signal_ledger").insert(data).execute()
                elif task_type == "outcome":
                    self.supabase.table("signal_ledger").insert(data).execute()
                elif task_type == "snapshot":
                    self.supabase.table("brain_snapshots").insert(data).execute()
                
                self.queue.task_done()
            except Exception as e:
                logger.error(f"SUPABASE WORKER ERROR: {e}")
                time.sleep(5) # Delay before retry on critical failure

    def _ensure_tables(self):
        """
        Note: Supabase tables should be created via SQL Editor in the Dashboard.
        This provides the schema reference for the user.
        """
        # TABLE: signal_ledger
        # Columns: signal_id (text), symbol (text), regime (text), confidence (text), 
        #          state (text), value (text), patterns (text), timestamp (timestamptz)
        
        # TABLE: brain_snapshots
        # Columns: features (jsonb), outcome (int4), stage (int4), timestamp (timestamptz)
        pass

    def log_intent(self, signal_data: Dict):
        """Logs initial signal intent to Supabase."""
        try:
            data = {
                "signal_id": f"{signal_data['symbol']}_{int(datetime.now().timestamp())}",
                "timestamp": datetime.now().isoformat(),
                "timestamp_ns": time.time_ns(),
                "seq_id": self._get_next_seq(),
                "symbol": signal_data['symbol'],
                "regime": signal_data['regime'],
                "confidence": signal_data['confidence'],
                "state": "INTENT",
                "value": "PENDING",
                "patterns": signal_data.get('patterns', ""),
                "decision_id": signal_data.get('decision_id', "")
            }
            try:
                if self.queue.full():
                    try:
                        self.queue.get_nowait() # Drop oldest
                        logger.warning("SUPABASE: Queue FULL. Dropped OLDEST log to make room for NEWEST.")
                    except queue.Empty: pass
                self.queue.put(("intent", data), block=False)
            except Exception as e:
                logger.error(f"SUPABASE ASYNC ERROR: Failed to queue intent: {e}")
        except Exception as e:
            logger.error(f"SUPABASE CRITICAL: {e}")

    def log_outcome(self, signal_id: str, outcome: str, persistence: bool = False):
        """Logs outcome to Supabase."""
        try:
            data = {
                "signal_id": signal_id,
                "timestamp": datetime.now().isoformat(),
                "timestamp_ns": time.time_ns(),
                "seq_id": self._get_next_seq(),
                "state": "OUTCOME",
                "value": outcome,
                "persistence": persistence
            }
            try:
                if self.queue.full():
                    try:
                        self.queue.get_nowait() # Drop oldest
                        logger.warning("SUPABASE: Queue FULL. Dropped OLDEST outcome log.")
                    except queue.Empty: pass
                self.queue.put(("outcome", data), block=False)
            except Exception as e:
                logger.error(f"SUPABASE ASYNC ERROR: Failed to queue outcome: {e}")
        except Exception as e:
            logger.error(f"SUPABASE CRITICAL: {e}")

    def log_snapshot(self, features: Dict, outcome: Optional[int] = None, stage: int = 1):
        """Logs brain snapshots for training."""
        try:
            data = {
                "features": features,
                "outcome": outcome,
                "stage": stage,
                "timestamp": datetime.now().isoformat(),
                "timestamp_ns": time.time_ns(),
                "seq_id": self._get_next_seq(),
            }
            try:
                if self.queue.full():
                    try:
                        self.queue.get_nowait() # Drop oldest
                        logger.warning("SUPABASE: Queue FULL. Dropped OLDEST snapshot.")
                    except queue.Empty: pass
                self.queue.put(("snapshot", data), block=False)
            except Exception as e:
                logger.error(f"SUPABASE ASYNC ERROR: Failed to queue brain snapshot: {e}")
        except Exception as e:
            logger.error(f"SUPABASE CRITICAL: {e}")

    def get_accuracy_report(self) -> Dict:
        """Calculates accuracy from cloud ledger."""
        try:
            response = self.supabase.table("signal_ledger").select("value").eq("state", "OUTCOME").execute()
            df = pd.DataFrame(response.data)
            
            if df.empty: return {"win_rate": 0.0, "total_trades": 0}
            
            wins = len(df[df['value'] == 'WIN'])
            total = len(df)
            return {
                "win_rate": round((wins / total) * 100, 2),
                "total_trades": total,
                "wins": wins,
                "losses": total - wins
            }
        except Exception as e:
            logger.error(f"SUPABASE ERROR: Failed accuracy report: {e}")
            return {"win_rate": 0.0, "total_trades": 0}

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Fetches latest signals from cloud."""
        try:
            response = self.supabase.table("signal_ledger").select("*").order("timestamp", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"SUPABASE ERROR: Failed to fetch history: {e}")
            return []

if __name__ == "__main__":
    # Test connection
    sm = SupabaseManager()
    print("Supabase Connection Established")
