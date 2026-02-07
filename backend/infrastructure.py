import os
import logging
import threading
import queue
import time
import json
import requests
import socket
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
# import pandas as pd (Moved to local scope)
from supabase import create_client, Client
from dotenv import load_dotenv
from models import TradeSignal

load_dotenv()

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
    "DIRECT_EXECUTION_ENABLED": os.getenv("DIRECT_EXECUTION_ENABLED", "FALSE").upper() == "TRUE",
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
        else:
            logging.warning("TELEGRAM: Notifications DISABLED (Check .env for TOKEN/CHAT_ID)")

    def _should_send(self, content: str) -> bool:
        """[v9.9.9] Prevents sending the same message more than twice."""
        if not self.enabled: return False
        count = self.sent_messages.get(content, 0)
        if count >= 2:
            logging.warning(f"TELEGRAM SPAM VETO: Message already sent {count} times.")
            return False
        self.sent_messages[content] = count + 1
        return True

    def _test_connection(self):
        # [v9.9.9] Atomic DNS Bypass: If standard DNS fails, use DoH fallback
        try:
            socket.gethostbyname("api.telegram.org")
        except socket.gaierror:
            self._apply_doh_bypass()
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                self.enabled = False
                logging.error(f"TELEGRAM: Connection failed ({response.status_code}): {response.text}")
            else:
                logging.info("TELEGRAM: Connection verified successfully.")
        except requests.exceptions.ConnectionError:
            # [v9.9.9] Silently handle DNS/Connection issues - typical in Restricted/HF Environments
            pass
        except Exception as e:
            self.enabled = False
            logging.error(f"TELEGRAM: Permanent initialization failure: {e}")

    def _apply_doh_bypass(self):
        """[v9.9.9] Nuclear DNS Fix: Resolves api.telegram.org via DoH and patches socket layer."""
        try:
            logging.info("TELEGRAM: Standard DNS failed. Attempting Institutional DNS Bypass (DoH)...")
            doh_url = "https://cloudflare-dns.com/dns-query"
            params = {"name": "api.telegram.org", "type": "A"}
            headers = {"Accept": "application/dns-json"}
            resp = requests.get(doh_url, params=params, headers=headers, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                ips = [a["data"] for a in data.get("Answer", []) if a["type"] == 1]
                if ips:
                    target_ip = ips[0]
                    # Patching socket for this specific domain
                    import socket
                    orig_getaddrinfo = socket.getaddrinfo
                    def patched_getaddrinfo(host, port, *args, **kwargs):
                        if host == "api.telegram.org":
                            return orig_getaddrinfo(target_ip, port, *args, **kwargs)
                        return orig_getaddrinfo(host, port, *args, **kwargs)
                    socket.getaddrinfo = patched_getaddrinfo
                    logging.info(f"TELEGRAM: Institutional DNS Bypass SUCCESS. Mapped to {target_ip}")
                    return True
        except Exception as e:
            logging.error(f"TELEGRAM: DNS Bypass Failed: {e}")
        return False

    def send_signal(self, signal: Dict, dashboard_url: str = "") -> bool:
        if not self.enabled: return False
        # [Anti-Spam] Track signals by decision_id or content
        msg_id = f"SIGNAL_{signal.get('decision_id', 'UNKNOWN')}"
        if not self._should_send(msg_id): return False
        
        try:
            direction = "🟢 BULLISH" if "BULLISH" in signal.get('reasoning', '') or "BULLISH" in signal.get('type', '') else "🔴 BEARISH"
            conf_val = signal.get('confidence_val', 0.85)
            conf_pct = f"({conf_val*100:.0f}%)" if conf_val else ""
            
            message = (
                f"💎 <b>TITAN INSTITUTIONAL SIGNAL</b> 💎\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📟 <b>ID:</b> #{signal.get('decision_id', 'N/A')}\n"
                f"📈 <b>Direction:</b> {direction}\n"
                f"🏦 <b>Symbol:</b> {signal.get('symbol', 'NIFTY')}\n"
                f"📦 <b>Instrument:</b> {signal.get('option_symbol', 'OPTION')}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>EXECUTION MATRIX</b>\n"
                f"├─ <b>Entry:</b> ₹{(signal.get('premium_entry') or 0.0):.2f}\n"
                f"├─ <b>SL:</b> ₹{(signal.get('premium_sl') or 0.0):.2f}\n"
                f"└─ <b>Target:</b> ₹{(signal.get('premium_target') or 0.0):.2f}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>BRAIN INTELLIGENCE</b>\n"
                f"├─ <b>Confidence:</b> {signal.get('confidence', 'MEDIUM')} {conf_pct}\n"
                f"└─ <b>Regime:</b> {signal.get('regime', 'TRENDING')}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )
            if dashboard_url: message += f"🔗 <a href='{dashboard_url}'>COMMAND CENTER</a>"
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(url, json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            if resp.status_code != 200:
                logging.error(f"TELEGRAM: Signal failed ({resp.status_code}): {resp.text}")
                return False
            return True
        except Exception as e:
            msg = f"TELEGRAM: Signal exception: {e}"
            if "NameResolutionError" in str(e) or "ConnectionError" in str(e):
                logging.warning(msg)
            else:
                logging.error(msg)
            return False

    def send_alert(self, message: str) -> bool:
        if not self.enabled: return False
        if not self._should_send(message): return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            rich_message = (
                f"🛡️ <b>TITAN SYSTEM ALERT</b> 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>MESSAGE:</b>\n"
                f"{message}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            resp = requests.post(url, json={"chat_id": self.chat_id, "text": rich_message, "parse_mode": "HTML"}, timeout=10)
            if resp.status_code != 200:
                logging.getLogger("infrastructure").error(f"TELEGRAM: Alert failed ({resp.status_code}): {resp.text}")
                return False
            return True
        except Exception as e:
            msg = f"TELEGRAM: Alert exception: {e}"
            if "NameResolutionError" in str(e) or "ConnectionError" in str(e):
                logging.warning(msg)
            else:
                logging.error(msg)
            return False

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
        self.table_columns = {"signal_ledger": set(), "trade_snapshots": set()}
        self.queue = queue.Queue(maxsize=10000)
        self.seq_id = 0
        self.seq_lock = threading.Lock()
        
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        if url and key:
            try:
                self.supabase = create_client(url, key)
                self._check_schema()
                threading.Thread(target=self._worker, daemon=True).start()
                self._initialized = True
            except Exception as e:
                logging.getLogger("infrastructure").error(f"SUPABASE: Init failed: {e}")

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
                table = "signal_ledger" if task_type in ["intent", "outcome"] else "trade_snapshots"
                allowed = self.table_columns.get(table, set())
                safe_data = {k: v for k, v in data.items() if k in allowed} if allowed else data
                self.supabase.table(table).insert(safe_data).execute()
                self.queue.task_done()
            except: time.sleep(1)

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

    def get_last_known_prices(self) -> Dict[str, float]:
        """Recovers the most recent prices from trade snapshots."""
        prices = {}
        try:
            snapshots = self.get_snapshots(limit=200)
            for snap in snapshots:
                feat = snap.get("features", {})
                # Look for symbols in snapshots (v9.8 logs symbol in features usually)
                symbol = feat.get("symbol")
                if not symbol: continue
                if symbol not in prices and "SPOT_PRICE" in feat:
                    prices[symbol] = float(feat["SPOT_PRICE"])
                if len(prices) >= 2: break # Found both NIFTY and SENSEX
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
