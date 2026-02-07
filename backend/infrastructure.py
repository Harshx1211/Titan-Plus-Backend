import os
import logging
import pytz
import threading
import queue
from collections import deque
import time
import json
import requests
import socket
import random
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
# import pandas as pd (Moved to local scope)
from supabase import create_client, Client
from dotenv import load_dotenv
from models_v3 import TradeSignal

class DataHealthError(Exception):
    """[v9.9.9] Raised when no valid real-time data sources are available."""
    pass

load_dotenv()
IST = pytz.timezone('Asia/Kolkata')

# ============================================================================
# 0. System Sentinel (Watchdog for Background Threads)
# ============================================================================

class SystemSentinel:
    """[v10.0.0] The Overseer. Monitors thread health and heartbeats."""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemSentinel, cls).__new__(cls)
            cls._instance.heartbeats = {}
            cls._instance.lock = threading.Lock()
        return cls._instance

    def record_heartbeat(self, thread_name: str):
        with self.lock:
            self.heartbeats[thread_name] = time.time()

    def get_status(self) -> Dict[str, bool]:
        now = time.time()
        status = {}
        with self.lock:
            for name, last_time in self.heartbeats.items():
                # If more than 5 minutes since last heartbeat, consider dead
                status[name] = (now - last_time) < 300
        return status

global_sentinel = SystemSentinel()
INSTITUTIONAL_WISDOM = [
    "Greed makes you loss money at the end.",
    "The winner is the one who does not know when and how to win; the true winner is the one who know when to stop.",
    "The market is a device for transferring money from the impatient to the patient.",
    "In trading, the best losers are the ultimate winners.",
    "Your discipline is your edge. Don't let your emotions dull it.",
    "Risk comes from not knowing what you're doing.",
    "Trading is 10% execution and 90% waiting.",
    "Protect your capital like your life depends on it. Because in this game, it does."
]

# ============================================================================
# 1. Global Configuration
# ============================================================================

APP_CONFIG = {
    "VIX_DEFAULT": float(os.getenv("VIX_DEFAULT", "15.0")),
    "MAX_PAIN_THRESHOLD": float(os.getenv("MAX_PAIN_THRESHOLD", "20.0")),
    "HIGH_VOLATILITY_VIX": float(os.getenv("HIGH_VOLATILITY_VIX", "20.0")),
    "LULL_START_HOUR": int(os.getenv("LULL_START_HOUR", "12")),
    "LULL_START_MINUTE": int(os.getenv("LULL_START_MINUTE", "0")),
    "LULL_END_HOUR": int(os.getenv("LULL_END_HOUR", "13")),
    "LULL_END_MINUTE": int(os.getenv("LULL_END_MINUTE", "30")),
    "PASSIVE_MODE_THRESHOLD": int(os.getenv("PASSIVE_MODE_THRESHOLD", "60")),
    "PATTERN_SCORE_THRESHOLD_HIGH": float(os.getenv("PATTERN_SCORE_THRESHOLD_HIGH", "0.15")),
    "PATTERN_SCORE_THRESHOLD_MEDIUM": float(os.getenv("PATTERN_SCORE_THRESHOLD_MEDIUM", "0.10")),
    "SIGNAL_TARGET_POINTS": float(os.getenv("SIGNAL_TARGET_POINTS", "100.0")),
    "BASE_LOTS": int(os.getenv("BASE_LOTS", "1")),
    "MIN_CONFIDENCE_TO_TRADE": float(os.getenv("MIN_CONFIDENCE_TO_TRADE", "0.15")),
    "SIGNAL_STOP_LOSS_POINTS": float(os.getenv("SIGNAL_STOP_LOSS_POINTS", "50.0")),
    "ATR_MAE_MULTIPLIER": float(os.getenv("ATR_MAE_MULTIPLIER", "2.0")),
    "ATR_MAE_MIN_THRESHOLD": float(os.getenv("ATR_MAE_MIN_THRESHOLD", "20.0")),
    "DECAY_PRICE_ADVERSE_THRESHOLD": float(os.getenv("DECAY_PRICE_ADVERSE_THRESHOLD", "15.0")),
    "SIGNAL_ACTIVE_CAP": int(os.getenv("SIGNAL_ACTIVE_CAP", "20")),
    "ENGINE_POLLING_BASE_SECONDS": int(os.getenv("ENGINE_POLLING_BASE_SECONDS", "1")),
    "ENGINE_POLLING_JITTER_SECONDS": int(os.getenv("ENGINE_POLLING_JITTER_SECONDS", "1")),
    "SIDECAR_STOP_LOSS_POINTS": float(os.getenv("SIDECAR_STOP_LOSS_POINTS", "30.0")),
    "SIDECAR_TARGET_POINTS": float(os.getenv("SIDECAR_TARGET_POINTS", "100.0")),
    "SKIRMISHER_STOP_LOSS_POINTS": float(os.getenv("SKIRMISHER_STOP_LOSS_POINTS", "15.0")),
    "SKIRMISHER_TARGET_POINTS": float(os.getenv("SKIRMISHER_TARGET_POINTS", "30.0")),
    "MARKET_START_HOUR": int(os.getenv("MARKET_START_HOUR", "9")),
    "MARKET_START_MINUTE": int(os.getenv("MARKET_START_MINUTE", "0")),
    "MARKET_END_HOUR": int(os.getenv("MARKET_END_HOUR", "15")),
    "MARKET_END_MINUTE": int(os.getenv("MARKET_END_MINUTE", "30")),
    "ENGINE_ERROR_SLEEP_TIME": int(os.getenv("ENGINE_ERROR_SLEEP_TIME", "5")),
    # [Institutional Lockdown] Force False per user request; must change in code to enable.
    "DIRECT_EXECUTION_ENABLED": False,
    "MAX_DAILY_LOSS": float(os.getenv("MAX_DAILY_LOSS", "-500.0")),
    "MAX_TRADES_PER_DAY": int(os.getenv("MAX_TRADES_PER_DAY", "20")),
}

# ============================================================================
# 2. Telegram Notifications
# ============================================================================

class TelegramNotifier:
    """Sends real-time trade signals and alerts via Telegram."""
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = False
        
        if self.bot_token and self.chat_id:
            if ":" in self.bot_token and len(self.bot_token) > 20:
                self.enabled = True
        
        if self.enabled:
            masked_token = f"{self.bot_token[:5]}...{self.bot_token[-5:]}" if self.bot_token else "****"
            masked_chat = str(self.chat_id)[-4:] if self.chat_id else "****"
            logging.info(f"TELEGRAM: Notifications ENABLED | Bot: {masked_token} | Chat: {masked_chat}")
            self._test_connection()
            # [v9.9.9] Anti-Spam Gate
            self.sent_messages: Dict[str, int] = {}
            self.circuit = CircuitBreaker("TELEGRAM", threshold=5, recovery_timeout=3600) # Reset after 1hr if failed
        else:
            logging.warning("TELEGRAM: Notifications DISABLED (Check .env for TOKEN/CHAT_ID)")

from notifier import TitanNotifier

class TelegramNotifier:
    """
    [v9.9.9] High-Level Notifier Wrapper.
    Proxies to the specialized notifier package for premium formatting.
    """
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = all([self.bot_token, self.chat_id])
        self.engine = TitanNotifier(self.bot_token, self.chat_id) if self.enabled else None
        
        if self.enabled:
            # Check DNS stability for Hugging Face
            self._verify_dns()

    def _verify_dns(self):
        """Institutional DNS Bypass for Hugging Face."""
        try:
            import socket
            socket.gethostbyname("api.telegram.org")
            logging.info("TELEGRAM: DNS resolved normally.")
        except Exception:
            logging.info("TELEGRAM: Standard DNS failed. Attempting Institutional DNS Bypass (DoH)...")
            try:
                import requests
                doh_url = "https://1.1.1.1/dns-query?name=api.telegram.org"
                resp = requests.get(doh_url, headers={"accept": "application/dns-json"}, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    for answer in data.get("Answer", []):
                        if answer["type"] == 1:
                            target_ip = answer["data"]
                            import socket
                            orig_getaddrinfo = socket.getaddrinfo
                            def patched_getaddrinfo(host, port, *args, **kwargs):
                                if host == "api.telegram.org":
                                    return orig_getaddrinfo(target_ip, port, *args, **kwargs)
                                return orig_getaddrinfo(host, port, *args, **kwargs)
                            socket.getaddrinfo = patched_getaddrinfo
                            logging.info(f"TELEGRAM: Institutional DNS Bypass SUCCESS. Mapped to {target_ip}")
                            break
            except Exception as e:
                logging.error(f"TELEGRAM: DNS Bypass Failed: {e}")

    def send_signal(self, signal: dict, dashboard_url: str = ""):
        if not self.enabled: return
        # Inject dashboard URL link text
        if dashboard_url:
            signal['reasoning'] += f"\n• <a href='{dashboard_url}'>COMMAND CENTER</a>"
        self.engine.send_entry(signal)

    def send_exit(self, signal_data: dict, reason: str, analysis: str):
        if not self.enabled: return
        self.engine.send_exit(signal_data, reason, analysis)

    def send_alert(self, message: str):
        if not self.enabled: return
        self.engine.send_alert("SYSTEM ALERT", message)

    def send_personalized_greeting(self, name: str, stats: dict = None):
        if not self.enabled: return
        # INSTITUTIONAL_WISDOM is already defined globally in infrastructure.py
        import random
        wisdom = random.choice(INSTITUTIONAL_WISDOM)
        self.engine.send_greeting(stats or {}, wisdom)

    def send_random_wisdom(self):
        if not self.enabled: return
        import random
        wisdom = random.choice(INSTITUTIONAL_WISDOM)
        msg = f"💡 <b>Institutional Wisdom</b>\n\n<i>\"{wisdom}\"</i>"
        self.engine.client.send(msg)

# ============================================================================
# 3. Supabase Cloud Memory
# ============================================================================

class SupabaseManager:
    """Cloud Memory with Dynamic Schema Resilience."""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.supabase: Optional[Client] = None
        self.table_columns = {"signal_ledger": set(), "trade_snapshots": set(), "system_heartbeat": set()}
        self.queue = queue.Queue(maxsize=10000)
        self.seq_id = 0
        self.seq_lock = threading.Lock()
        self.instance_id = str(uuid.uuid4())[:8]
        self.is_leader = False
        
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        if url and key:
            try:
                self.supabase = create_client(url, key)
                self._check_schema()
                self._elect_leader()
                threading.Thread(target=self._worker, daemon=True).start()
                threading.Thread(target=self._heartbeat_loop, daemon=True).start()
                self._initialized = True
            except Exception as e:
                logging.getLogger("infrastructure").error(f"SUPABASE: Init failed: {e}")

    def _elect_leader(self):
        """[v12.0.0] Hardened 2-Phase Leader Election with Jitter."""
        try:
            # 1. Broad query for active leaders (Lease concept)
            threshold = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
            res = self.supabase.table("system_heartbeat").select("*").gt("last_heartbeat", threshold).execute()
            
            # 2. Check for LEADER status explicitly
            active_leaders = [r['instance_id'] for r in res.data if r.get('status') == 'LEADER']
            if active_leaders:
                self.is_leader = False
                logging.warning(f"SUPABASE: Active LEADER {active_leaders[0]} detected. Staying in FOLLOWER mode.")
                return

            # 3. Phase 1: Announce Candidacy
            self.supabase.table("system_heartbeat").upsert({
                "instance_id": self.instance_id,
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "status": "CANDIDATE"
            }).execute()

            # 4. Randomized Jitter to break simultaneous start ties (2-Phase Commit concept)
            jitter = random.uniform(0.5, 2.5)
            time.sleep(jitter)

            # 5. Phase 2: Verify Candidacy
            res = self.supabase.table("system_heartbeat").select("*").gt("last_heartbeat", threshold).execute()
            # Sort by instance_id as a deterministic tie-breaker
            potential_leaders = sorted([r for r in res.data if r.get('status') in ['LEADER', 'CANDIDATE']], 
                                        key=lambda x: x['instance_id'])
            
            if potential_leaders and potential_leaders[0]['instance_id'] == self.instance_id:
                self.is_leader = True
                self.supabase.table("system_heartbeat").update({
                    "status": "LEADER",
                    "last_heartbeat": datetime.now(timezone.utc).isoformat()
                }).eq("instance_id", self.instance_id).execute()
                logging.info(f"SUPABASE: Instance {self.instance_id} WON election. Promoted to LEADER.")
            else:
                self.is_leader = False
                winner = potential_leaders[0]['instance_id'] if potential_leaders else "Unknown"
                logging.warning(f"SUPABASE: Instance {self.instance_id} LOST election to {winner}. Staying FOLLOWER.")

        except Exception as e:
            logging.error(f"SUPABASE: Leader election failure: {e}. Defaulting to FOLLOWER safety.")
            self.is_leader = False

    def _heartbeat_loop(self):
        """Keeps the lease alive."""
        while True:
            try:
                if self.is_leader:
                    self.supabase.table("system_heartbeat").update({
                        "last_heartbeat": datetime.now(timezone.utc).isoformat()
                    }).eq("instance_id", self.instance_id).execute()
                time.sleep(60)
            except Exception as e:
                logging.error(f"SUPABASE: Heartbeat failed: {e}")
                time.sleep(10)

    def _check_schema(self):
        for table in self.table_columns.keys():
            try:
                res = self.supabase.table(table).select("*").limit(1).execute()
                if res.data: self.table_columns[table] = set(res.data[0].keys())
            except: pass

    def _worker(self):
        while True:
            try:
                task_type, data = self.queue.get()
                global_sentinel.record_heartbeat("supabase_worker")
                table = "signal_ledger" if task_type in ["intent", "outcome", "update"] else "trade_snapshots"
                
                # Dynamic Schema filtering
                allowed = self.table_columns.get(table, set())
                safe_data = {k: v for k, v in data.items() if k in allowed} if allowed else data
                
                # [v10.0.0] Ghost-Instance Safety: Only LEADER can write Intents
                if task_type == "intent" and not self.is_leader:
                    logging.warning(f"SUPABASE: FOLLOWER instance tried to log intent. BLOCKING.")
                    self.queue.task_done()
                    continue

                # Logic Switch: Insert vs Update
                if task_type == "update":
                    sig_id = safe_data.pop("signal_id", None)
                    if sig_id:
                        self.supabase.table(table).update(safe_data).eq("signal_id", sig_id).execute()
                else:
                    self.supabase.table(table).insert(safe_data).execute()
                
                self.queue.task_done()
            except Exception as e:
                logging.getLogger("infrastructure").warning(f"SUPABASE: Write failed (Retrying in 5s): {e}")
                time.sleep(5) # Backoff

    def log_intent(self, signal_data: Dict):
        with self.seq_lock: self.seq_id += 1
        data = {
            "signal_id": f"{signal_data['symbol']}_{int(time.time())}",
            "timestamp": datetime.now().isoformat(), "seq_id": self.seq_id,
            "symbol": signal_data['symbol'], "state": "INTENT", "value": "PENDING",
            "decision": signal_data.get('decision_id', "")
        }
        self.queue.put(("intent", data))

    def log_outcome(self, signal_id: str, outcome: str):
        with self.seq_lock: self.seq_id += 1
        data = {"signal_id": signal_id, "timestamp": datetime.now().isoformat(), "seq_id": self.seq_id, "state": "OUTCOME", "value": outcome}
        self.queue.put(("outcome", data))

    def update_signal_state(self, signal_id: str, state: str, value: Any = None):
        """Update an existing signal record instead of inserting a new row."""
        data = {"signal_id": signal_id, "state": state, "timestamp": datetime.now().isoformat()}
        if value is not None:
            data["value"] = value
        self.queue.put(("update", data))

    def log_snapshot(self, signal_data: Dict, outcome: int, stage: int = 1, efficacy: Optional[int] = None):
        with self.seq_lock: self.seq_id += 1
        features = signal_data.get("features", {})
        
        # Ensure we log the ML-specific features for training later
        data = {
            "timestamp": datetime.now().isoformat(),
            "features": features,
            "decision": signal_data.get("decision", "BLOCK"),
            "outcome": outcome,
            "efficacy": efficacy,
            "stage": stage,
            "regime": signal_data.get("regime", "UNCERTAIN")
        }
        self.queue.put(("snapshot", data))

    def get_accuracy_report(self) -> Dict:
        try:
            import pandas as pd
            res = self.supabase.table("signal_ledger").select("value").eq("state", "OUTCOME").execute()
            df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
            wins = len(df[df['value'] == 'WIN']) if not df.empty else 0
            total = len(df) if not df.empty else 0
            ratio = wins / total if total > 0 else 0.0
            return {"win_rate": round(ratio, 4), "accuracy": round(ratio, 4), "total_trades": total, "wins": wins, "status": "ONLINE"}
        except: return {"win_rate": 0.0, "total_trades": 0, "status": "ERROR"}

    def get_history(self, limit: int = 50) -> List[Dict]:
        try:
            res = self.supabase.table("signal_ledger").select("*").order("timestamp", desc=True).limit(limit).execute()
            return res.data or []
        except: return []

    def get_snapshots(self, limit: int = 500) -> List[Dict]:
        try:
            res = self.supabase.table("trade_snapshots").select("*").order("timestamp", desc=True).limit(limit).execute()
            return res.data or []
        except: return []

    def get_active_signals(self) -> List[Dict]:
        """Recovers signals that haven't been CLOSED or given an OUTCOME."""
        try:
            # Fetch last 100 signals and filter locally for simplicity/resilience
            res = self.supabase.table("signal_ledger").select("*").order("timestamp", desc=True).limit(100).execute()
            if not res.data: return []
            
            # Map by ID to find ones without OUTCOME state
            id_map = {}
            for row in res.data:
                sid = row['signal_id']
                if sid not in id_map: id_map[sid] = []
                id_map[sid].append(row['state'])
            
            active_ids = [sid for sid, states in id_map.items() if "OUTCOME" not in states]
            return [row for row in res.data if row['signal_id'] in active_ids and row['state'] == "INTENT"]
        except Exception as e:
            logging.getLogger("infrastructure").error(f"SUPABASE: Signal recovery failed: {e}")
            return []

    def get_last_known_prices(self) -> Dict[str, float]:
        """Recovers the most recent prices from trade snapshots."""
        prices = {}
        try:
            snapshots = self.get_snapshots(limit=300)
            for snap in snapshots:
                feat = snap.get("features", {})
                symbol = feat.get("symbol")
                if not symbol: continue
                
                # Check multiple possible keys for the price
                price = None
                for key in ["SPOT_PRICE", "spot_price", "price", "lp"]:
                    if key in feat:
                        price = float(feat[key])
                        break
                
                if symbol not in prices and price is not None:
                    prices[symbol] = price
            
            if prices:
                logging.getLogger("infrastructure").info(f"SUPABASE: Recovered prices for {list(prices.keys())}")
        except Exception as e:
            logging.getLogger("infrastructure").error(f"SUPABASE: Price recovery failed: {e}")
        return prices

# ============================================================================
# 4. Database Bridge (Legacy Support)
# ============================================================================

class DatabaseManager:
    """
    [v9.9.9] Unified Data Access Layer.
    Bridges the gap between Legacy API calls and the new Supabase Cloud Memory.
    """
    def __init__(self):
        self.cloud_db = SupabaseManager()
        logging.getLogger("infrastructure").info("DB: Database Bridge initialized.")

    def log_intent(self, signal: Dict, patterns: List[str]):
        """Proxies intent logging to Cloud Memory."""
        signal['patterns'] = patterns
        self.cloud_db.log_intent(signal)

    def log_outcome(self, signal_id: str, outcome: str):
        """Proxies outcome logging to Cloud Memory."""
        self.cloud_db.log_outcome(signal_id, outcome)

    def get_accuracy_report(self) -> Dict:
        return self.cloud_db.get_accuracy_report()

# 5. [Institutional Phase 6] Market State (Atomic Snapshot)
# ============================================================================

class MarketState:
    """
    Thread-safe latest market snapshot for event-driven execution.
    Prevents race conditions between WS thread and Brain decisions.
    """
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MarketState, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.lock = threading.Lock()
        self.data: Dict[str, Dict] = {}
        self.last_update_ts = 0.0
        self._initialized = True
        logging.info("INFRA: Atomic MarketState initialized.")

    def update(self, tick: Dict):
        """Update state with a new tick. Tick should have 'symbol' and 'lp'."""
        symbol = tick.get('symbol')
        if not symbol: return
        
        with self.lock:
            if symbol not in self.data:
                self.data[symbol] = {}
            
            # Atomic update of fields
            self.data[symbol].update(tick)
            self.data[symbol]['last_tick_time'] = time.time()
            self.last_update_ts = time.time()

    def snapshot(self) -> Dict[str, Dict]:
        """Provides a safe copy of the current state for the Brain."""
        with self.lock:
            return {k: v.copy() for k, v in self.data.items()}

    def get_symbol_price(self, symbol: str) -> float:
        """Quick lookup for a single price."""
        with self.lock:
            return self.data.get(symbol, {}).get('lp', 0.0)

# ============================================================================
# 6. Circuit Breaker (Stability Pattern)
# ============================================================================

class CircuitBreaker:
    """
    [v9.9.9] Prevents cascading failures by tripping when an API is unstable.
    States: CLOSED (Normal), OPEN (Failed, Bypassed), HALF-OPEN (Testing)
    """
    def __init__(self, name: str, threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.threshold = threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = 0
        self.lock = threading.Lock()

    def record_failure(self):
        with self.lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                if self.state != "OPEN":
                    logging.error(f"CIRCUIT_BREAKER: {self.name} tripped! Switching to OPEN (Bypass).")
                    self.state = "OPEN"

    def record_success(self):
        with self.lock:
            if self.state == "HALF-OPEN":
                logging.info(f"CIRCUIT_BREAKER: {self.name} recovered. Switching to CLOSED.")
                self.state = "CLOSED"
                self.failures = 0
            elif self.state == "CLOSED":
                self.failures = max(0, self.failures - 1)

    def can_proceed(self) -> bool:
        with self.lock:
            if self.state == "CLOSED":
                return True
            
            # Check for recovery timeout
            if self.state == "OPEN":
                if (time.time() - self.last_failure_time) > self.recovery_timeout:
                    logging.warning(f"CIRCUIT_BREAKER: {self.name} in HALF-OPEN state. Testing recovery...")
                    self.state = "HALF-OPEN"
                    return True
                return False
            
            return True # HALF-OPEN

# ============================================================================
# 7. System Health Monitor (Observability)
# ============================================================================

class SystemHealthMonitor:
    """
    [v9.9.9] Tracks aggregate loop latency and health metrics for the dashboard.
    """
    def __init__(self, window_size: int = 100):
        self.latency_samples = deque(maxlen=window_size)
        self.last_healthy_time = time.time()
        self.errors = {"API": 0, "DB": 0, "ML": 0}
        self.lock = threading.Lock()

    def record_latency(self, ms: float):
        with self.lock:
            self.latency_samples.append(ms)
            self.last_healthy_time = time.time()

    def record_error(self, category: str):
        with self.lock:
            if category in self.errors:
                self.errors[category] += 1

    def get_stats(self) -> Dict:
        with self.lock:
            avg_lat = sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0.0
            return {
                "avg_latency_ms": round(avg_lat, 2),
                "last_health_check": datetime.fromtimestamp(self.last_healthy_time).isoformat(),
                "error_counts": self.errors,
                "uptime_status": "STABLE" if avg_lat < 500 else "DEGRADED"
            }
