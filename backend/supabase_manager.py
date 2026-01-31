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
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.supabase: Optional[Client] = None
        url: str = os.getenv("SUPABASE_URL")
        key: str = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            logger.error("SUPABASE: URL or KEY missing in environment variables.")
        else:
            try:
                self.supabase = create_client(url, key)
                logger.info("SUPABASE: Connection Established.")
            except Exception as e:
                logger.error(f"SUPABASE: Client Initialization Failed: {e}")

        # Async Logging Infrastructure (Hardened)
        self.queue = queue.Queue(maxsize=10000)
        self.seq_id = 0
        self.seq_lock = threading.Lock()
        
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info("SUPABASE: Hardened async worker initialized.")
        self._initialized = True

    def _get_next_seq(self) -> int:
        with self.seq_lock:
            self.seq_id += 1
            return self.seq_id

    def _worker(self):
        """Background worker to process the logging queue."""
        while True:
            try:
                task_type, data = self.queue.get()
                if not self.supabase:
                    logger.warning("SUPABASE WORKER: No active client. Dropping task.")
                    self.queue.task_done()
                    continue

                if task_type == "intent":
                    self.supabase.table("signal_ledger").insert(data).execute()
                elif task_type == "outcome":
                    self.supabase.table("signal_ledger").insert(data).execute()
                elif task_type == "snapshot":
                    self.supabase.table("brain_snapshots").insert(data).execute()
                
                self.queue.task_done()
            except Exception as e:
                logger.error(f"SUPABASE WORKER ERROR: {e}")
                time.sleep(5)

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
            if self.queue.full():
                self.queue.get_nowait()
            self.queue.put(("intent", data), block=False)
        except Exception as e:
            logger.error(f"SUPABASE CRITICAL: {e}")

    def log_outcome(self, signal_id: str, outcome: str, persistence: bool = False):
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
            if self.queue.full():
                self.queue.get_nowait()
            self.queue.put(("outcome", data), block=False)
        except Exception as e:
            logger.error(f"SUPABASE CRITICAL: {e}")

    def get_accuracy_report(self) -> Dict:
        """Calculates accuracy from cloud ledger."""
        try:
            if not self.supabase:
                return {"win_rate": 0.0, "total_trades": 0, "status": "OFFLINE"}
            
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

    def log_snapshot(self, signal_data: Dict, outcome: int, stage: int = 1):
        """Logs brain decision context to cloud."""
        try:
            data = {
                "signal_id": f"BRAIN_{int(datetime.now().timestamp())}_{signal_data.get('decision_id', 'UNK')}",
                "timestamp": datetime.now().isoformat(),
                "timestamp_ns": time.time_ns(),
                "seq_id": self._get_next_seq(),
                "symbol": signal_data.get("symbol", "INDEX"),
                "regime": signal_data.get("regime", "UNCERTAIN"),
                "decision": signal_data.get("decision", "BLOCK"),
                "efficacy": signal_data.get("efficacy", 0),
                "confidence_boost": signal_data.get("confidence_boost", 0.0),
                "features": json.dumps(signal_data.get("features", {})),
                "outcome": outcome,
                "stage": stage,
                "auth": signal_data.get("regime_authority", 1.0)
            }
            if self.queue.full():
                self.queue.get_nowait()
            self.queue.put(("snapshot", data), block=False)
        except Exception as e:
            logger.error(f"SUPABASE SNAPSHOT ERROR: {e}")

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Fetches latest signals from cloud."""
        try:
            if not self.supabase:
                return []
            response = self.supabase.table("signal_ledger").select("*").order("timestamp", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"SUPABASE ERROR: Failed to fetch history: {e}")
            return []

if __name__ == "__main__":
    sm = SupabaseManager()
    print("Supabase Initialization Triggered")
