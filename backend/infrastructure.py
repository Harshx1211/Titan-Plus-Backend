import os
import logging
import threading
import queue
import time
import json
import requests
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
    "ENGINE_POLLING_BASE_SECONDS": int(os.getenv("ENGINE_POLLING_BASE_SECONDS", "5")),
    "ENGINE_POLLING_JITTER_SECONDS": int(os.getenv("ENGINE_POLLING_JITTER_SECONDS", "2")),
    "SIDECAR_STOP_LOSS_POINTS": float(os.getenv("SIDECAR_STOP_LOSS_POINTS", "30.0")),
    "SIDECAR_TARGET_POINTS": float(os.getenv("SIDECAR_TARGET_POINTS", "100.0")),
    "SKIRMISHER_STOP_LOSS_POINTS": float(os.getenv("SKIRMISHER_STOP_LOSS_POINTS", "15.0")),
    "SKIRMISHER_TARGET_POINTS": float(os.getenv("SKIRMISHER_TARGET_POINTS", "30.0")),
    "MARKET_START_HOUR": int(os.getenv("MARKET_START_HOUR", "9")),
    "MARKET_START_MINUTE": int(os.getenv("MARKET_START_MINUTE", "0")),
    "MARKET_END_HOUR": int(os.getenv("MARKET_END_HOUR", "15")),
    "MARKET_END_MINUTE": int(os.getenv("MARKET_END_MINUTE", "30")),
    "ENGINE_ERROR_SLEEP_TIME": int(os.getenv("ENGINE_ERROR_SLEEP_TIME", "5")),
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
            logging.getLogger("infrastructure").info("TELEGRAM: Notifications ENABLED")
            self._test_connection()
        else:
            logging.getLogger("infrastructure").warning("TELEGRAM: Notifications DISABLED")

    def _test_connection(self):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                self.enabled = False
                logging.getLogger("infrastructure").error(f"TELEGRAM: Connection failed ({response.status_code})")
        except:
            self.enabled = False

    def send_signal(self, signal: Dict, dashboard_url: str = "") -> bool:
        if not self.enabled: return False
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
                f"├─ <b>Entry:</b> ₹{signal.get('premium_entry', 0):.2f}\n"
                f"├─ <b>SL:</b> ₹{signal.get('premium_sl', 0):.2f}\n"
                f"└─ <b>Target:</b> ₹{signal.get('premium_target', 0):.2f}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>BRAIN INTELLIGENCE</b>\n"
                f"├─ <b>Confidence:</b> {signal.get('confidence', 'MEDIUM')} {conf_pct}\n"
                f"└─ <b>Regime:</b> {signal.get('regime', 'TRENDING')}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )
            if dashboard_url: message += f"🔗 <a href='{dashboard_url}'>COMMAND CENTER</a>"
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            requests.post(url, json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            return True
        except Exception as e:
            logging.getLogger("infrastructure").error(f"TELEGRAM: Signal failed: {e}")
            return False

    def send_alert(self, message: str) -> bool:
        if not self.enabled: return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            rich_message = (
                f"🛡️ <b>TITAN SYSTEM ALERT</b> 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>MESSAGE:</b>\n"
                f"{message}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            requests.post(url, json={"chat_id": self.chat_id, "text": rich_message, "parse_mode": "HTML"}, timeout=10)
            return True
        except: return False

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
    """Bridge to Supabase to maintain legacy compatibility."""
    def __init__(self):
        self.cloud_db = SupabaseManager()
    def log_intent(self, signal: TradeSignal, patterns: List[str] = []):
        data = signal.dict()
        data['patterns'] = ",".join(patterns)
        self.cloud_db.log_intent(data)
    def log_outcome(self, signal_id: str, outcome: str):
        self.cloud_db.log_outcome(signal_id, outcome)
    def get_accuracy_report(self) -> Dict:
        return self.cloud_db.get_accuracy_report()
    @property
    def db_path(self): return "SUPABASE_CLOUD"
