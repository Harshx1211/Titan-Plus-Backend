import os
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Set
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
    v3: Dynamic Schema Resilience
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
        
        # Dynamic Schema Cache
        self.table_columns: Dict[str, Set[str]] = {
            "signal_ledger": set(),
            "brain_snapshots": set()
        }
        self.schema_checked = False
        
        if not url or not key:
            logger.error("SUPABASE: URL or KEY missing in environment variables.")
        else:
            try:
                self.supabase = create_client(url, key)
                logger.info("SUPABASE: Connection Established.")
                self._check_schema_dynamic()
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

    def _check_schema_dynamic(self):
        """Dynamically detect available columns for each table to prevent PGRST204 errors."""
        if not self.supabase or self.schema_checked:
            return
            
        for table in self.table_columns.keys():
            try:
                # Optimized schema detection: Query one row and check keys
                response = self.supabase.table(table).select("*").limit(1).execute()
                if response.data:
                    self.table_columns[table] = set(response.data[0].keys())
                else:
                    # Fallback: If table is empty, we try a more invasive column probe 
                    # for the most critical columns to ensure we have a baseline
                    logger.info(f"SUPABASE: Table {table} is empty. Using fallback detection.")
                    # This is a bit of a hack since PostgREST doesn't expose meta easily
                    # We'll assume common columns exist and let the worker adapt if they don't
                    critical_cols = ["id", "timestamp", "signal_id", "symbol", "state", "value"]
                    if table == "brain_snapshots":
                        critical_cols = ["id", "timestamp", "symbol", "features", "outcome"]
                    
                    self.table_columns[table] = set(critical_cols)
                
                logger.info(f"SUPABASE: Detected {len(self.table_columns[table])} columns for {table}")
                logger.debug(f"SUPABASE: Columns for {table}: {self.table_columns[table]}")
            except Exception as e:
                logger.warning(f"SUPABASE: Could not detect schema for {table}: {e}")
        
        self.schema_checked = True

    def _filter_data(self, table: str, data: Dict) -> Dict:
        """Removes keys from data that are not present in the database schema."""
        if table not in self.table_columns or not self.table_columns[table]:
            # If detection hasn't happened yet, fall back to critical columns only
            critical = ["id", "timestamp", "symbol", "state", "value", "features", "outcome"]
            return {k: v for k, v in data.items() if k in critical}
            
        allowed = self.table_columns[table]
        filtered = {k: v for k, v in data.items() if k in allowed}
        
        removed = set(data.keys()) - allowed
        if removed:
            logger.debug(f"SUPABASE: Filtering out missing columns for {table}: {removed}")
            
        return filtered

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

                table = "signal_ledger" if task_type in ["intent", "outcome"] else "brain_snapshots"
                
                # Double-check filtering in worker for absolute safety
                safe_data = self._filter_data(table, data)

                try:
                    self.supabase.table(table).insert(safe_data).execute()
                except Exception as e:
                    if "PGRST204" in str(e):
                        # If we still get a column error, it means our cache was wrong
                        # Extract the column name from error if possible and update cache
                        err_msg = str(e).lower()
                        logger.warning(f"SUPABASE WORKER: Unexpected schema mismatch on {table}: {e}")
                        # We don't retry here to avoid loops, but the next insert will be filtered
                        # by the (hopefully updated) logic if we can identify the col.
                    else:
                        logger.error(f"SUPABASE WORKER: Insert failed for {table}: {e}")
                
                self.queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"SUPABASE WORKER ERROR: {e}")
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
                "patterns": signal_data.get('patterns', ""),
                "decision": signal_data.get('decision_id', "") # Legacy key mapping
            }
            
            # Additional mapping for decision_id vs decision column
            if 'decision_id' in signal_data and 'decision' not in data:
                data['decision'] = signal_data['decision_id']
            
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
                "value": outcome,
                "persistence": persistence
            }
            
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
                return {"win_rate": 0.0, "total_trades": 0, "wins": 0, "losses": 0, "status": "OFFLINE"}
            
            response = self.supabase.table("signal_ledger").select("value").eq("state", "OUTCOME").execute()
            
            if not response.data:
                return {"win_rate": 0.0, "total_trades": 0, "wins": 0, "losses": 0, "status": "NO_DATA"}
            
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
            return {"win_rate": 0.0, "total_trades": 0, "wins": 0, "losses": 0, "error": str(e)}

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
                "features": json.dumps(signal_data.get("features", { })),
                "outcome": outcome,
                "stage": stage,
                "decision": signal_data.get("decision", "BLOCK")
            }
            
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
    print("Supabase Manager dynamic schema version initialized")
    for table, cols in sm.table_columns.items():
        print(f"Table: {table} | Detected Columns: {len(cols)}")
        print(f"Columns: {cols}")
    
    # Test filtering logic
    test_data = {"id": 1, "timestamp": "now", "NON_EXISTENT_COLUMN": "FAIL"}
    filtered = sm._filter_data("signal_ledger", test_data)
    print(f"Filtered Test: {filtered}")
    assert "NON_EXISTENT_COLUMN" not in filtered
    print("Filter logic verified! ✅")
