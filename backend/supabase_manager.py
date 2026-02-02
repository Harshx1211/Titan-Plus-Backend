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
import json

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
        
        # Track which columns exist in the schema
        self.has_decision_column = False
        self.has_persistence_column = False
        self.schema_checked = False
        
        if not url or not key:
            logger.error("SUPABASE: URL or KEY missing in environment variables.")
        else:
            try:
                self.supabase = create_client(url, key)
                logger.info("SUPABASE: Connection Established.")
                self._check_schema()
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

    def _check_schema(self):
        """Check which columns exist in the Supabase tables."""
        if not self.supabase or self.schema_checked:
            return
            
        try:
            # Try to query with decision column
            test_query = self.supabase.table("brain_snapshots").select("decision").limit(1).execute()
            self.has_decision_column = True
            logger.info("SUPABASE: 'decision' column found in brain_snapshots")
        except Exception as e:
            if "PGRST204" in str(e) or "decision" in str(e).lower():
                logger.warning("SUPABASE: 'decision' column NOT found in brain_snapshots - will skip")
                self.has_decision_column = False
            else:
                logger.debug(f"SUPABASE: Schema check error (non-critical): {e}")
        
        try:
            # Try to query with persistence column
            test_query = self.supabase.table("signal_ledger").select("persistence").limit(1).execute()
            self.has_persistence_column = True
            logger.info("SUPABASE: 'persistence' column found in signal_ledger")
        except Exception as e:
            if "PGRST204" in str(e) or "persistence" in str(e).lower():
                logger.warning("SUPABASE: 'persistence' column NOT found in signal_ledger - will skip")
                self.has_persistence_column = False
            else:
                logger.debug(f"SUPABASE: Schema check error (non-critical): {e}")
        
        self.schema_checked = True

    def _get_next_seq(self) -> int:
        with self.seq_lock:
            self.seq_id += 1
            return self.seq_id

    def _worker(self):
        """Background worker to process the logging queue."""
        while True:
            try:
                task_type, data = self.queue.get(timeout=1)
                
                if not self.supabase:
                    logger.warning("SUPABASE WORKER: No active client. Dropping task.")
                    self.queue.task_done()
                    continue

                if task_type == "intent":
                    try:
                        self.supabase.table("signal_ledger").insert(data).execute()
                    except Exception as e:
                        if "PGRST204" in str(e):
                            # Column doesn't exist - remove it and retry
                            logger.debug(f"SUPABASE: Adapting intent insert due to schema mismatch")
                            if "decision" in data:
                                data.pop("decision", None)
                            if "persistence" in data and not self.has_persistence_column:
                                data.pop("persistence", None)
                            try:
                                self.supabase.table("signal_ledger").insert(data).execute()
                            except Exception as e2:
                                logger.error(f"SUPABASE WORKER: Intent insert failed after adaptation: {e2}")
                        else:
                            raise
                            
                elif task_type == "outcome":
                    try:
                        self.supabase.table("signal_ledger").insert(data).execute()
                    except Exception as e:
                        if "PGRST204" in str(e) or "persistence" in str(e):
                            # Remove persistence column if it doesn't exist
                            logger.debug(f"SUPABASE: Adapting outcome insert due to schema mismatch")
                            if "persistence" in data:
                                data.pop("persistence", None)
                            try:
                                self.supabase.table("signal_ledger").insert(data).execute()
                            except Exception as e2:
                                logger.error(f"SUPABASE WORKER: Outcome insert failed after adaptation: {e2}")
                        else:
                            raise
                            
                elif task_type == "snapshot":
                    try:
                        self.supabase.table("brain_snapshots").insert(data).execute()
                    except Exception as e:
                        if "PGRST204" in str(e) or "decision" in str(e):
                            # Remove decision column if it doesn't exist
                            logger.debug(f"SUPABASE: Adapting snapshot insert due to schema mismatch")
                            if "decision" in data:
                                data.pop("decision", None)
                            try:
                                self.supabase.table("brain_snapshots").insert(data).execute()
                            except Exception as e2:
                                logger.error(f"SUPABASE WORKER: Snapshot insert failed after adaptation: {e2}")
                        else:
                            raise
                
                self.queue.task_done()
                
            except queue.Empty:
                # Normal timeout - continue loop
                continue
            except Exception as e:
                logger.error(f"SUPABASE WORKER ERROR: {e}")
                # Don't sleep on every error - only on repeated failures
                time.sleep(1)

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
                "patterns": signal_data.get('patterns', "")
            }
            
            # Only add columns that exist in schema
            if self.has_decision_column and 'decision_id' in signal_data:
                data['decision'] = signal_data.get('decision_id', "")
            
            if self.queue.full():
                logger.warning("SUPABASE: Queue full, dropping oldest task")
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
            
            self.queue.put(("intent", data), block=False)
            
        except queue.Full:
            logger.error("SUPABASE: Queue full, cannot log intent")
        except Exception as e:
            logger.error(f"SUPABASE: Failed to queue intent: {e}")

    def log_outcome(self, signal_id: str, outcome: str, persistence: bool = False):
        """Logs outcome with schema-aware persistence handling."""
        try:
            data = {
                "signal_id": signal_id,
                "timestamp": datetime.now().isoformat(),
                "timestamp_ns": time.time_ns(),
                "seq_id": self._get_next_seq(),
                "state": "OUTCOME",
                "value": outcome
            }
            
            # Only add persistence if column exists
            if self.has_persistence_column:
                data["persistence"] = persistence
            else:
                # Store in a custom field or ignore
                logger.debug(f"SUPABASE: Persistence value {persistence} not logged (column missing)")
            
            if self.queue.full():
                logger.warning("SUPABASE: Queue full, dropping oldest task")
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
            
            self.queue.put(("outcome", data), block=False)
            
        except queue.Full:
            logger.error("SUPABASE: Queue full, cannot log outcome")
        except Exception as e:
            logger.error(f"SUPABASE: Failed to queue outcome: {e}")

    def get_accuracy_report(self) -> Dict:
        """Calculates accuracy from cloud ledger."""
        try:
            if not self.supabase:
                return {
                    "win_rate": 0.0, 
                    "total_trades": 0, 
                    "wins": 0,
                    "losses": 0,
                    "status": "OFFLINE"
                }
            
            response = self.supabase.table("signal_ledger").select("value").eq("state", "OUTCOME").execute()
            
            if not response.data:
                return {
                    "win_rate": 0.0, 
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "status": "NO_DATA"
                }
            
            df = pd.DataFrame(response.data)
            wins = len(df[df['value'] == 'WIN'])
            total = len(df)
            
            return {
                "win_rate": round((wins / total) * 100, 2) if total > 0 else 0.0,
                "total_trades": total,
                "wins": wins,
                "losses": total - wins,
                "status": "ONLINE"
            }
        except Exception as e:
            logger.error(f"SUPABASE: Failed to get accuracy report: {e}")
            return {
                "win_rate": 0.0, 
                "total_trades": 0, 
                "wins": 0,
                "losses": 0,
                "error": str(e)
            }

    def log_snapshot(self, signal_data: Dict, outcome: int, stage: int = 1):
        """Logs brain decision context to cloud with schema awareness."""
        try:
            data = {
                "signal_id": f"BRAIN_{int(datetime.now().timestamp())}_{signal_data.get('decision_id', 'UNK')}",
                "timestamp": datetime.now().isoformat(),
                "timestamp_ns": time.time_ns(),
                "seq_id": self._get_next_seq(),
                "symbol": signal_data.get("symbol", "INDEX"),
                "regime": signal_data.get("regime", "UNCERTAIN"),
                "efficacy": signal_data.get("efficacy", 0),
                "features": json.dumps(signal_data.get("features", {})),
                "outcome": outcome,
                "stage": stage
            }
            
            # Only add decision if column exists
            if self.has_decision_column:
                data["decision"] = signal_data.get("decision", "BLOCK")
            
            if self.queue.full():
                logger.warning("SUPABASE: Queue full, dropping oldest task")
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
            
            self.queue.put(("snapshot", data), block=False)
            
        except queue.Full:
            logger.error("SUPABASE: Queue full, cannot log snapshot")
        except Exception as e:
            logger.error(f"SUPABASE: Failed to queue snapshot: {e}")

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Fetches latest signals from cloud."""
        try:
            if not self.supabase:
                return []
            response = self.supabase.table("signal_ledger").select("*").order("timestamp", desc=True).limit(limit).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"SUPABASE: Failed to fetch history: {e}")
            return []

if __name__ == "__main__":
    sm = SupabaseManager()
    print("Supabase Manager initialized")
    print(f"Schema check: decision={sm.has_decision_column}, persistence={sm.has_persistence_column}")
    
    # Test accuracy report
    report = sm.get_accuracy_report()
    print(f"Accuracy Report: {report}")
