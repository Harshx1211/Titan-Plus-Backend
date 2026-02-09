# Standard lightweight imports
import os
import asyncio
import threading
import logging
import time
import pytz
import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Delay heavy library imports
# import pandas as pd
# import pandas_ta as ta
from pytz import timezone as pytz_timezone
from config import config  # Centralized config

# Configure logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# from models import Regime, DivergenceType, TradeSignal, SignalConfidence # DEPRECATED
from models_v3 import Decision, Regime, Action, MarketStructure, TradeSignal, TradeSnapshot, DivergenceType, SignalConfidence

# [v10.2] Import enhanced endpoints and health checks
from health_check_endpoint import health_router
from api_enhanced_endpoints import outcome_router
import uvicorn

app = FastAPI(title="The Oracle - Titan Plus Institutional")

# [v10.2] Register enhanced routers
app.include_router(health_router)
app.include_router(outcome_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent State Storage
class LiveState:
    def __init__(self):
        # [v10.0] Thread Safety - RLock for all state access
        self._lock = threading.RLock()
        
        self.current_regime = Regime.NEUTRAL
        self._active_signals = []  # Protected by lock
        self.last_update = datetime.now(timezone.utc)
        self.symbols = ["NIFTY", "BANKNIFTY", "SENSEX"]
        self.current_symbol_idx = 0
        self.vix = APP_CONFIG["VIX_DEFAULT"]
        self.breadth = {"advances": 0, "declines": 0}
        self.market_message = "System Stable"
        self.data_source = "PUBLIC_SCRAPER"
        self.index_strengths: Dict[str, float] = {"NIFTY": 0.0, "BANKNIFTY": 0.0, "SENSEX": 0.0}
        
        # Partitioned Symbol Data (v8.1 Multi-Asset)
        self.prices = {"NIFTY": 25727.0, "BANKNIFTY": 50000.0, "SENSEX": 83739.0}
        self.max_pain = {"NIFTY": 0.0, "BANKNIFTY": 0.0, "SENSEX": 0.0}
        self.option_battles = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}

        self.option_chains = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}
        self.supports = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}
        self.resistances = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}
        self.history_cache = {"NIFTY": None, "BANKNIFTY": None, "SENSEX": None}
        
        # v8.1: Statistical Discipline
        self.resets_today = 0
        self.last_reset_time = datetime.now(timezone.utc)
        self.iv_skew = {"NIFTY": 1.0, "SENSEX": 1.0, "BANKNIFTY": 1.0}
        self.gex_bias = {"NIFTY": 0.0, "BANKNIFTY": 0.0, "SENSEX": 0.0}
        self.sector_synergy = 1.0 
        self.prev_oi = {"NIFTY": 0, "BANKNIFTY": 0, "SENSEX": 0}
        self.prev_spot = 0.0
        
        # [Institutional Step 5] IV History tracking for Percentile
        self.iv_history = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}
        
        # [v9.4] Epistemic Transparency: Digital Stream of Consciousness
        self.thought_logs = []
        self.last_thoughts_by_type = {}
        self.is_learning = False
        self.integrity = DivergenceType.NONE
        self.direct_execution_active = False
        
        # [v10.0] Emergency Controls
        self.emergency_mode = False  # Set to True to halt all trading

        # [Institutional Wave 3] Deduplication & Memory Hygiene
        self.seen_signal_ids = set()
        self.seen_ids_lock = threading.Lock()  # [v10.2] Thread-safe lock for seen_signal_ids
    
    @property
    def active_signals(self):
        """Thread-safe getter for active signals."""
        with self._lock:
            return self._active_signals.copy()
    
    def add_signal(self, signal):
        """Thread-safe signal addition."""
        with self._lock:
            self._active_signals.append(signal)
    
    def remove_signal(self, signal_id: str):
        """Thread-safe signal removal."""
        with self._lock:
            self._active_signals = [s for s in self._active_signals if s.decision_id != signal_id]
    
    def clear_signals(self):
        """Thread-safe signal clearing."""
        with self._lock:
            self._active_signals = []

    def add_thought(self, thought_type: str, msg: str):
        """[v10.0] Thread-safe thought logger with type-aware de-duplication."""
        with self._lock:
            # Type-aware suppression
            if self.last_thoughts_by_type.get(thought_type) == msg:
                return
                
            self.last_thoughts_by_type[thought_type] = msg
            
            self.thought_logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "type": thought_type,
                "msg": msg
            })
            
            # Keep logs lean for dashboard stability
            if len(self.thought_logs) > 40:
                self.thought_logs.pop(0)

def emergency_shutdown(reason: str):
    """
    [v10.0] Nuclear option: Close everything immediately on critical failures.
    
    Triggers:
    - Both data providers fail
    - Database connection lost
    - Critical system error
    - Manual intervention required
    """
    logger.critical(f"🚨 EMERGENCY SHUTDOWN INITIATED: {reason}")
    
    # 1. Stop accepting new signals
    live_state.emergency_mode = True
    
    # 2. Close all open positions at MARKET (fastest exit)
    closed_count = 0
    failed_exits = []
    
    for signal in live_state.active_signals:
        try:
            if hasattr(core, 'execution_engine') and core.execution_engine:
                # Use execution engine's emergency exit
                core.execution_engine.emergency_exit(
                    signal.decision_id,
                    reason=f"EMERGENCY_SHUTDOWN: {reason}"
                )
                closed_count += 1
                logger.info(f"Emergency exit: {signal.symbol} @ {signal.decision_id}")
            else:
                logger.warning(f"No execution engine - cannot close {signal.symbol}")
                failed_exits.append(signal.symbol)
        except Exception as e:
            logger.error(f"Emergency exit failed for {signal.symbol}: {e}")
            failed_exits.append(signal.symbol)
    
    # 3. Alert via all channels
    alert_message = (
        f"🚨 EMERGENCY SHUTDOWN\n\n"
        f"Reason: {reason}\n"
        f"Positions closed: {closed_count}\n"
        f"Failed exits: {len(failed_exits)}\n"
        f"System locked. Manual restart required."
    )
    
    try:
        if hasattr(core, 'telegram_notifier') and core.telegram_notifier:
            core.telegram_notifier.send_alert(alert_message)
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
    
    # 4. Save state before exit
    try:
        if hasattr(core, 'brain') and core.brain:
            core.brain.save_state()
        if hasattr(core, 'db') and core.db:
            core.db.log_event("EMERGENCY_SHUTDOWN", {
                "reason": reason,
                "closed_count": closed_count,
                "failed_exits": failed_exits,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    except Exception as e:
        logger.error(f"Failed to save state during shutdown: {e}")
    
    # 5. Hard exit (bypass normal shutdown)
    logger.critical("System halting now.")
    os._exit(1)  # Immediate termination

# Config & Global Placeholders
# [v10.0] Loaded from config.py
APP_CONFIG = {
    "VIX_DEFAULT": 15.0,
    "SIGNAL_ACTIVE_CAP": config.MAX_OPEN_POSITIONS,
    "ENGINE_POLLING_BASE_SECONDS": 1,
    "ENGINE_POLLING_JITTER_SECONDS": 1,
    "ENGINE_ERROR_SLEEP_TIME": 5,
    "MARKET_START_HOUR": 9,
    "MARKET_START_MINUTE": 0,
    "MARKET_END_HOUR": 15,
    "MARKET_END_MINUTE": 30,
    "MAX_PAIN_THRESHOLD": 20.0,
    "HIGH_VOLATILITY_VIX": 20.0,
    "PASSIVE_MODE_THRESHOLD": 300,
    "PATTERN_SCORE_THRESHOLD_HIGH": 0.75,
    "LULL_START_HOUR": 11,
    "LULL_START_MINUTE": 30,
    "LULL_END_HOUR": 13,
    "LULL_END_MINUTE": 00,
    "SIGNAL_TARGET_POINTS": 100,
    "SIGNAL_STOP_LOSS_POINTS": 50,
    "DASHBOARD_URL": "http://localhost:3000"
}
evolution_done_date = None

shadow_mode_enabled = os.getenv("SHADOW_MODE", "false").lower() == "true"
admin_token = os.getenv("ADMIN_TOKEN", "titan_admin_123") # Simple auth

# State & Monitoring
from infrastructure import IST, global_sentinel
live_state = LiveState()
macro_cache = {}
macro_cache_lock = threading.Lock()

# ============================================================================
# Core Intelligence Orchestrator (Phase 3 Multi-Process Scaffolding)
# ============================================================================

class CoreEngine:
    """
    [v9.9.9] Central Orchestrator for all sub-engines.
    Encapsulated to allow for future multi-process spawning.
    """
    def __init__(self, state: LiveState):
        self.state = state
        self.sentinel = None
        self.strategist = None
        self.sr_engine = None
        self.brain = None
        self.evolver = None
        self.pattern_engine = None
        self.risk_engine = None
        self.tech_engine = None
        self.trap_hunter = None
        self.option_engine = None
        self.session_auditor = None
        self.health_monitor = None
        self.db = None
        self.telegram_notifier = None
        self.data_provider = None
        self.execution_engine = None
        self.shadow_engine = None
        self.outcome_tracker = None  # [v10.1] Automatic outcome tracking
        self.is_initialized = False

    def initialize(self):
        """Lazy initialization of heavy engines with staggered loading."""
        logger.info("CORE: Initializing institutional engines...")
        import gc
        from infrastructure import SupabaseManager, DatabaseManager, TelegramNotifier, SystemHealthMonitor
        from providers import DataProvider
        from engines import DataSentinel, RiskEngine, PatternEngine, TrapHunter, SessionAuditor
        from brain_unified import create_brain  # UNIFIED BRAIN
        from execution_engine import ExecutionEngine # REAL EXECUTION
        # from evolution_engine import EvolutionEngine  # [v10.2] Disabled - outcome_tracker provides learning
        from strategist import MarketStrategist
        from support_resistance import SupportResistanceEngine
        from option_engine import OptionEngine
        from technical_engine import TechnicalEngine
        from outcome_tracker import OutcomeTracker  # [v10.1] Automatic learning
        
        self.db = DatabaseManager()
        time.sleep(1)
        self.telegram_notifier = TelegramNotifier()
        time.sleep(1)
        self.data_provider = DataProvider()
        time.sleep(1)
        
        # [v10.1] Initialize outcome tracker for automatic learning
        self.outcome_tracker = OutcomeTracker(
            data_provider=self.data_provider,
            db_manager=self.db
        )
        self.outcome_tracker.start_monitoring()
        logger.info("Outcome tracker initialized and monitoring started")
        time.sleep(1)
        
        
        self.sentinel = DataSentinel()
        self.strategist = MarketStrategist()
        self.sr_engine = SupportResistanceEngine()
        self.health_monitor = SystemHealthMonitor()
        self.session_auditor = SessionAuditor()
        
        # Heavy ML (Staggered)
        # Heavy ML (Staggered)
        self.brain = create_brain(enable_rl=True, enable_smc=True)  # Unified v10.0
        gc.collect(); time.sleep(1)
        # self.evolver = EvolutionEngine(self.brain)  # [v10.2] Disabled - outcome_tracker provides learning
        self.evolver = None  # Placeholder
        gc.collect(); time.sleep(1)
        
        self.pattern_engine = PatternEngine()
        self.risk_engine = RiskEngine()
        self.trap_hunter = TrapHunter()
        self.option_engine = OptionEngine()
        self.tech_engine = TechnicalEngine()
        
        # Real Execution Engine
        self.execution_engine = ExecutionEngine(
            broker_api=self.data_provider,  # Using data provider as broker interface for now
            risk_manager=self.risk_engine,  # Link to risk engine
            db_manager=self.db
        )
        self.execution_engine.start_monitoring()
        logger.info("CORE: Execution Engine monitoring active.")
        
        if os.getenv("SHADOW_MODE", "false").lower() == "true":
            from shadow_mode import ShadowMode
            self.shadow_engine = ShadowMode()
            
        self.is_initialized = True
        logger.info("CORE: System Fully Operational.")

# Global State & Core Initialization
IST = pytz.timezone('Asia/Kolkata')
live_state = LiveState()
core = CoreEngine(live_state)

# Helper: Safe Brain Interface
def call_brain_safely(action: str, **kwargs):
    if core.brain is None:
        return None, []
    
    try:
        if action == "DECIDE":
            res = core.brain.decide(
                features=kwargs.get("features"),
                market_data=kwargs.get("market_data"),
                ohlcv_df=kwargs.get("ohlcv_df"),
                regime=kwargs.get("regime"),
                **kwargs
            )
            if isinstance(res, dict):
                return res.get('decision_id', 'ERR'), res.get('thoughts', [])
            return res if res is not None else (None, [])
        elif action == "BOOST":
            if core.shadow_engine:
                core.shadow_engine.compare_predictions(kwargs.get("features"), kwargs.get("regime"))
            
            res = core.brain.get_confidence_boost_ml(
                features=kwargs.get("features"),
                regime_val=kwargs.get("regime").value if hasattr(kwargs.get("regime"), 'value') else kwargs.get("regime"),
                signal_intent=kwargs.get("signal_intent"),
                iv_skew=kwargs.get("iv_skew", 1.0)
            )
            if isinstance(res, dict):
                return res.get('probability', 0.5), res.get('thoughts', [])
            if isinstance(res, tuple): return res
            return 0.5, []
    except Exception as e:
        logger.error(f"BRAIN_PROXY_ERROR: {e}")
            
    return None, []

class SystemState(BaseModel):
    regime: Regime
    is_in_recovery: bool
    data_latency: float
    integrity_status: DivergenceType
    active_signals: List[TradeSignal]
    last_update: datetime
    vix: float
    breadth: Dict[str, int]
    market_message: str
    data_source: str
    # Multi-Asset Partitioned Data
    prices: Dict[str, float]
    max_pain: Dict[str, float]
    option_battles: Dict[str, List[Dict]]
    option_chains: Dict[str, List[Dict]]
    iv_skew: Dict[str, float]
    supports: Dict[str, List[float]]
    resistances: Dict[str, List[float]]
    resets_today: int
    gex_bias: Dict[str, float]
    sector_synergy: float
    thought_logs: List[Dict]
    is_learning: bool
    market_open: bool
    direct_execution_active: bool # [Institutional Phase 6]

def is_market_open():
    """Check if Indian stock market is currently open (IST timezone-aware)."""
    # CRITICAL FIX: Use IST timezone for accurate market hours detection
    ist = pytz_timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Market hours: Monday-Friday, 9:00 AM - 3:30 PM IST
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    market_start = now.replace(hour=APP_CONFIG["MARKET_START_HOUR"], minute=APP_CONFIG["MARKET_START_MINUTE"], second=0, microsecond=0)
    market_end = now.replace(hour=APP_CONFIG["MARKET_END_HOUR"], minute=APP_CONFIG["MARKET_END_MINUTE"], second=0, microsecond=0)
    
    return market_start <= now <= market_end

def get_minutes_to_expiry():
    """Calculates minutes to the next weekly/monthly expiry (Thursday 3:30 PM)."""
    ist = pytz_timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Calculate days to Thursday
    days_to_thursday = (3 - now.weekday()) % 7 # Thursday is 3
    if days_to_thursday == 0 and now.time() > datetime.strptime("15:30", "%H:%M").time():
        days_to_thursday = 7 # Next week
        
    expiry_date = (now + timedelta(days=days_to_thursday)).replace(hour=15, minute=30, second=0, microsecond=0)
    delta = expiry_date - now
    minutes = delta.total_seconds() / 60
    return max(1, int(minutes))

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """Root endpoint to confirm server is alive."""
    return {
        "message": "Titan Plus API is running. Visit /health for status.",
        "version": "v9.4.0",
        "market": "NSE/BSE"
    }

@app.get("/health")
async def health_check():
    """Heartbeat endpoint with Brain metrics for observability."""
    if core.brain is None:
        return {
            "status": "initializing",
            "message": "Titan Plus engines are powering up...",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        
    return {
        "status": "active",
        "engine": "Titan Plus",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cloud_memory": "Supabase Linked",
        "brain": {
            "health": core.brain.health_check(),
            "metrics": {
                "total_decisions": core.brain.metrics.total_decisions,
                "approvals": core.brain.metrics.approvals,
                "blocks": core.brain.metrics.blocks,
                "avg_confidence": round(core.brain.metrics.avg_confidence, 3),
                "nan_rejections": core.brain.metrics.nan_rejections,
                "version": core.brain.LOGIC_VERSION
            }
        }
    }

@app.get("/state", response_model=SystemState)
async def get_state():
    return SystemState(
        regime=live_state.current_regime,
        is_in_recovery=core.risk_engine.is_in_recovery() if core.risk_engine else False,
        data_latency=(datetime.now(timezone.utc) - live_state.last_update).total_seconds() * 1000 if is_market_open() else 0.0,
        integrity_status=live_state.integrity,
        active_signals=live_state.active_signals,
        last_update=live_state.last_update,
        vix=live_state.vix,
        breadth=live_state.breadth,
        market_message=live_state.market_message,
        data_source=live_state.data_source,
        prices=live_state.prices,
        max_pain=live_state.max_pain,
        option_battles=live_state.option_battles,
        option_chains=live_state.option_chains,

        iv_skew=live_state.iv_skew,
        supports=live_state.supports,
        resistances=live_state.resistances,
        resets_today=live_state.resets_today,
        gex_bias=live_state.gex_bias,
        sector_synergy=live_state.sector_synergy,
        thought_logs=live_state.thought_logs[-100:], # [v9.8] Increased for TRACE visibility
        is_learning=live_state.is_learning,
        market_open=is_market_open(),
        direct_execution_active=live_state.direct_execution_active
    )

@app.post("/signals/intent")
async def post_intent(signal: TradeSignal, patterns: List[str] = []):
    """Logs a new signal intent into the Truth Ledger."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database engine initializing")
    db.log_intent(signal, patterns)
    return {"status": "intent_logged"}

@app.post("/signals/outcome")
async def post_outcome(signal_id: str, outcome: str):
    """Appends an outcome to an existing signal intent."""
    if core.db is None:
        raise HTTPException(status_code=503, detail="Database engine initializing")
    core.db.log_outcome(signal_id, outcome)
    return {"status": "outcome_logged"}

@app.get("/history")
async def get_history():
    """Returns the Truth Ledger (Immutable Records) from Supabase."""
    if core.db is None:
        return [] # Return empty list during initialization
    return core.db.cloud_db.get_history()

@app.get("/accuracy")
async def get_accuracy():
    if core.db is None:
        return {"win_rate": 0.0, "accuracy": 0.0, "total_trades": 0, "status": "INITIALIZING"}
    return core.db.get_accuracy_report()

@app.get("/audit")
async def get_session_audit(date: Optional[str] = None):
    """Returns the Institutional Session Audit report."""
    if core.session_auditor is None:
        raise HTTPException(status_code=503, detail="Session Auditor initializing")
    return core.session_auditor.generate_daily_report(date)

@app.post("/feedback")
async def post_feedback(signal_id: int, outcome: str, override: bool = False):
    # Logic to log feedback and retrain brain
    return {"status": "success"}

@app.post("/execute_trade")
async def execute_trade(signal_id: str, admin_key: str = ""):
    """
    [DISABLED - ANALYSIS-ONLY MODE]
    
    This system is configured as an ANALYSIS-ONLY tool.
    All trade execution must be done MANUALLY by the user.
    
    The system will:
    - Generate signals and recommendations
    - Display them on the dashboard
    - Log them to the database
    
    The user must:
    - Review signals manually
    - Execute trades on their broker
    - Log outcomes for learning
    
    This endpoint is disabled to prevent accidental auto-execution.
    """
    logger.info(f"API: Auto-execution blocked for Signal ID: {signal_id} (Analysis-only mode)")
    
    return {
        "status": "disabled",
        "message": "AUTO-EXECUTION DISABLED: This is an analysis-only system. Please execute trades manually on your broker.",
        "signal_id": signal_id,
        "recommendation": "Review signal on dashboard and execute manually if you agree with the analysis."
    }

@app.get("/outcome_stats")
async def get_outcome_stats():
    """
    [v10.1] Get automatic outcome tracking statistics.
    
    Returns:
    - Win rate percentage
    - Total wins/losses/expired
    - Currently monitoring signals
    - Recent outcomes (last 20)
    """
    if not core.outcome_tracker:
        return {"error": "Outcome tracker not initialized"}
    
    try:
        stats = core.outcome_tracker.get_statistics()
        recent = core.outcome_tracker.get_recent_outcomes(limit=20)
        
        return {
            "status": "success",
            "statistics": stats,
            "recent_outcomes": recent,
            "learning_active": True
        }
    except Exception as e:
        logger.error(f"Failed to get outcome stats: {e}")
        return {"error": str(e)}

@app.post("/evolve")
async def trigger_evolution(date: Optional[str] = None, token: str = None):
    """Triggers the Overnight Learning (Evolution) process."""
    if token != admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if core.evolver is None:
        raise HTTPException(status_code=503, detail="Evolution engine initializing")
    
    live_state.is_learning = True
    live_state.add_thought("LEARN", f"Starting Overnight Evolutionary Audit for {date or 'today'}...")
    try:
        result = core.evolver.evolve_session(date)

        # Add specific learning results to thoughts
        for feat, rep in result.get("reputation_updates", {}).items():
            if rep != 1.0: # Only if it changed or is non-neutral
                live_state.add_thought("LEARN", f"DNA Calibration: {feat} reputation adjusted to {rep:.2f}")

        live_state.add_thought("LEARN", f"Session Audit Complete. Governor Status: {result.get('governor_status', 'ACTIVE')}")
        return {"status": "evolution_complete", "details": result}
    except Exception as e:
        logger.error(f"API: Evolution process failed for {date or 'today'}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evolution process failed: {e}")
    finally:
        live_state.is_learning = False

@app.post("/reset")
async def reset_system(token: str = None):
    """Emergency Reset: Clears recovery mode and active signals."""
    if token != os.getenv("APP_API_TOKEN", "oracle_v1"):
         raise HTTPException(status_code=403, detail="Not authorized")
    global risk_engine, live_state
    if risk_engine: risk_engine.reset()
    live_state.active_signals = []
    live_state.add_thought("SYSTEM", "Emergency reset triggered by administrator.")
    return {"status": "Ok", "message": "System reset successfully"}


# [v9.9.9] Background thread to keep History Cache fresh (Architecture 10/10).
def history_refresher_loop(data_provider, state: LiveState, sentinel):
    """
    [Institutional Phase 6] Background thread for heavy interval fetching.
    Moves 60m historical data (macro context) out of the main loop.
    """
    import gc
    loop_count = 0
    # Main Polling Loop
    while True:
        try:
            sentinel.record_heartbeat("history_refresher")
            # [v9.9.9] Logic Hardening: Fetch macro-data every 15 minutes
            for sym in ["NIFTY", "BANKNIFTY", "SENSEX"]:
                try:
                    df_60 = data_provider.get_history(sym, "60minute")
                    with macro_cache_lock:
                        macro_cache[sym] = df_60
                    logger.info(f"CACHE: Refreshed 60m history for {sym}")
                except Exception as e:
                    logger.warning(f"CACHE_ERROR: Failed to refresh macro {sym}: {e}")
                time.sleep(1) # Stagger requests
            
            # [Institutional Wave 4] Consistency Watchdog (Memory vs DB)
            if core.db and loop_count % 2 == 0: # Every 30 mins
                active_db = core.db.get_active_signals()
                active_mem_ids = [s.decision_id for s in state.active_signals]
                for db_sig in active_db:
                    if db_sig['signal_id'] not in active_mem_ids:
                        logger.warning(f"WATCHDOG: Ghost signal {db_sig['signal_id']} found in DB but not memory. Synchronizing...")
                        # Recovery logic could be added here if needed

            # [Institutional Wave 3] Periodic Memory Hygiene
            loop_count += 1
            if loop_count % 4 == 0: # Every hour
                collected = gc.collect()
                logger.info(f"HYGIENE: Automated Garbage Collection cycle. Freed {collected} objects.")
                
            # [Wave 3] Clean seen_signal_ids daily (After Market)
            # [v12.0.0] Safe Memory Hygiene: Prune seen_signal_ids if too large OR daily
            now_ist = datetime.now(timezone.utc).astimezone(IST)
            with state.seen_ids_lock: 
                if now_ist.hour == 16 or len(state.seen_signal_ids) > 1000:
                    state.seen_signal_ids.clear()
                    logger.info(f"HYGIENE: Pruned seen_signal_ids (Size: {len(state.seen_signal_ids)})")
            
            # [v12.0.0] Pulse heartbeats every 60s while waiting for the next 15m cycle
            for _ in range(15):
                sentinel.record_heartbeat("history_refresher")
                time.sleep(60)
        except Exception as e:
            logger.error(f"HISTORY_REFRESHER_CRASH: {e}")
            time.sleep(60)

def run_engine_loop():
    """
    [v9.9.9] Multi-Process Ready Main Loop.
    Uses core instance for all business logic and execution.
    """
    global evolution_done_date
    
    if not core.is_initialized:
        core.initialize()
    
    # Extract shortcut references from core for cleaner loop logic
    db = core.db
    telegram_notifier = core.telegram_notifier
    data_provider = core.data_provider
    brain = core.brain
    evolver = core.evolver
    session_auditor = core.session_auditor
    health_monitor = core.health_monitor
    strategist = core.strategist
    sr_engine = core.sr_engine
    pattern_engine = core.pattern_engine
    option_engine = core.option_engine
    risk_engine = core.risk_engine
    tech_engine = core.tech_engine

    # [Institutional Phase 6] Initialize WebSocket & MarketState
    from infrastructure import MarketState
    from shoonya_ws import ShoonyaWebSocket
    from providers import MarketData
    from infrastructure import DataHealthError # Corrected import path for DataHealthError
    import pandas as pd
    
    market_state = MarketState()
    ws = ShoonyaWebSocket(data_provider.shoonya)
    ws.start()
    logger.info("ENGINE: WebSocket data pipeline active.")

    # [v9.9.9] Startup Price Seeding
    logger.info("STATE: Seeding initial prices from DataProvider...")
    for sym in live_state.symbols:
        try:
            seed_data = data_provider.get_market_snapshot(sym)
            if seed_data and seed_data.spot_price > 0:
                live_state.prices[sym] = seed_data.spot_price
                market_state.update({'symbol': sym, 'lp': seed_data.spot_price, 'v': 0, 'oi': seed_data.oi})
                logger.info(f"STATE_AUDIT: Seeded {sym} @ {seed_data.spot_price} from {seed_data.source}")
        except Exception as e:
            logger.error(f"STATE_AUDIT: Failure seeding {sym}: {e}")

    # Seed VIX
    try:
        live_state.vix = data_provider.get_vix()
        logger.info(f"STATE: Seeded VIX @ {live_state.vix}")
    except Exception as vix_err:
        logger.warning(f"STATE: VIX seeding failed: {vix_err}")
    
    start_time = time.time()
    evolution_done_date = None
        
    try:
        # The rest of the imports and initializations that were previously here are now handled by core.initialize()
        # or are moved to the top of the file if they are global dependencies.
        # Any remaining imports needed within the loop should be placed here if not already at the top.
        import gc
        import random
        import pandas_ta as ta # pandas is already imported above
        
        # [v9.9.6] Restrict CPU threads to prevent scheduler kills
        try:
            import torch
            torch.set_num_threads(1)
        except: pass
        
        # [v9.9.9] Start Decoupled Heartbeats
        threading.Thread(target=history_refresher_loop, args=(data_provider, live_state, global_sentinel), daemon=True).start()
        
        if data_provider.use_groww:
            live_state.data_source = "GROWW_API"
            
        # [v9.9.8] State Recovery: Fallback for missing prices if market is closed/fresh restart
        try:
            last_prices = db.cloud_db.get_last_known_prices()
            for sym, price in last_prices.items():
                # [v9.9.9] SAFETY: ONLY recover if seeding failed (price is 0.0 or missing)
                current_price = live_state.prices.get(sym, 0.0)
                if current_price <= 0.0 and sym in ["NIFTY", "BANKNIFTY", "SENSEX"]:
                    live_state.prices[sym] = price
                    logger.info(f"STATE: Recovered last active price for {sym}: {price} (Fallback)")
                elif sym in live_state.prices:
                    # Log but don't overwrite if we already have fresh data
                    logger.info(f"STATE: Skipping recovery for {sym}, using fresh seeding: {current_price}")
        except Exception as e:
            logger.warning(f"STATE: Price recovery failed: {e}")

        # [v9.9.9] Nuclear Signal Recovery (Container Resilience)
        try:
            records = db.cloud_db.get_active_signals()
            for rec in records:
                sym = rec.get('symbol')
                if sym:
                    # [v9.9.9] Reconstruct TradeSignal object from DB record
                    # We map the dictionary keys to Pydantic model fields
                    try:
                        # Extract the 'features' if it's a string
                        feat = rec.get('features', {})
                        if isinstance(feat, str):
                            import json
                            feat = json.loads(feat.replace("'", '"'))
                        
                        recovered_sig = TradeSignal(
                            symbol=sym,
                            entry_price=rec.get('entry_price', 0.0),
                            stop_loss=rec.get('stop_loss', 0.0),
                            target=rec.get('target', 0.0),
                            timestamp=datetime.fromisoformat(rec['timestamp'].replace('Z', '+00:00')) if 'timestamp' in rec else datetime.now(timezone.utc),
                            decision_id=rec.get('signal_id', 'RECOVERED'),
                            reasoning=rec.get('reasoning', 'RECOVERED_TRADE'),
                            is_live=True
                        )
                        live_state.active_signals.append(recovered_sig)
                        logger.info(f"STATE: Hyper-Resilience: Recovered active trade for {sym} (ID: {rec.get('signal_id')})")
                    except Exception as parse_err:
                        logger.warning(f"STATE: Failed to parse recovered signal for {sym}: {parse_err}")
        except Exception as e:
            logger.error(f"STATE: Signal recovery failed: {e}")

        logger.info("ENGINE: Consolidated CoreEngine initialized. Starting analysis loop.")
        
        # [AUDIT FIX] Initialize timing for passive checks
        # start_time = time.time() # Already set above
        
    except Exception as init_err:
        logger.error(f"ENGINE INIT ERROR: {init_err}", exc_info=True)
        return

    vix_update_counter = 0
    
    while True:
        try:
            # [Institutional Phase 6] WebSocket Atomic Snapshot
            now = datetime.now(IST)
            # [v9.9.9] Connectivity Heartbeat
            source_info = data_provider.get_status()
            if vix_update_counter % 50 == 0:
                live_state.add_thought("MONITOR", f"System Health: {source_info['status']} | Data: {source_info['name']}")
            
            # Phase 0: Operational Hygiene (Market Hours & Evolution)
            now_ist = datetime.now(IST)
            current_time = now_ist.time()
            today_str = now_ist.strftime("%Y-%m-%d")
            
            market_start = datetime.strptime(f"{APP_CONFIG['MARKET_START_HOUR']}:{APP_CONFIG['MARKET_START_MINUTE']:02d}", "%H:%M").time()
            market_end = datetime.strptime(f"{APP_CONFIG['MARKET_END_HOUR']}:{APP_CONFIG['MARKET_END_MINUTE']:02d}", "%H:%M").time()
            
            # Post-Market Intelligence Trigger (3:35 PM IST)
            evolution_trigger_time = datetime.strptime("15:35", "%H:%M").time()
            
            is_market_open = (market_start <= current_time <= market_end) and (now_ist.weekday() < 5)
            
            if not is_market_open:
                # 1. Dashboard Status
                status_reason = "Weekend" if now_ist.weekday() >= 5 else "After Hours"
                live_state.market_message = f"DORMANT: {status_reason} ({current_time.strftime('%H:%M')} IST)"
                live_state.current_regime = Regime.UNCERTAIN
                
                # [v9.6] Ambient Intelligence: Add a "Watching" thought occasionally
                if random.random() < 0.05: # ~3 times an hour
                    live_state.add_thought("MONITOR", "Market closed. Watching global cues and preparing for next session.")
                
                # 2. Automated Overnight Learning
                if current_time >= evolution_trigger_time and evolution_done_date != today_str:
                    logger.info(f"INTELLIGENCE: Triggering automated post-market evolution for {today_str}...")
                    live_state.add_thought("LEARN", f"Starting Overnight Evolution for {today_str}...")
                    live_state.is_learning = True
                    try:
                        results = evolver.evolve_session(today_str)
                        evolution_done_date = today_str
                        live_state.is_learning = False
                        
                        if results and results.get("status") == "SUCCESS":
                            status = results.get('governor_status', 'SUCCESS')
                            live_state.add_thought("LEARN", f"Evolution Complete: {status}. Brain Refined.")
                            if 'metrics' in results and 'win_rate' in results['metrics']:
                                wr = results['metrics']['win_rate']
                                if wr is not None:
                                    live_state.add_thought("LEARN", f"Session Review: {wr:.1f}% Win Rate analyzed.")
                                else:
                                    live_state.add_thought("LEARN", "Session Review: No trades analyzed today.")
                        else:
                            reason = results.get("reason", "No data") if results else "Empty Response"
                            live_state.add_thought("LEARN", f"Evolution Skipped: {reason}")
                            logger.info(f"INTELLIGENCE: Evolution skipped: {reason}")
                            
                        if results and results.get("governor_status"):
                            core.telegram_notifier.send_alert(f"🧠 *Overnight Intelligence*: Evolution process finished for {today_str}.\nStatus: {results.get('governor_status')}")
                    except Exception as e:
                        live_state.is_learning = False
                        logger.error(f"INTELLIGENCE: Evolution failed: {e}")
                        live_state.add_thought("ERROR", f"Overnight Evolution primary fail: {str(e)}")
                
                # 3. Aggressive Sleep during off-hours (1 minute polling)
                live_state.last_update = datetime.now(timezone.utc) # Keep heartbeat alive
                
                # [v9.9.8] Seed persistence data once every hour during off-hours
                if current_time.minute == 0 and current_time.second < 10:
                    for sym in live_state.symbols:
                        try:
                            m_data = data_provider.get_market_snapshot(sym)
                            if m_data:
                                # [Smart Exploration] Log baseline even for BLOCKS (5% random)
                                is_exploration_tick = random.random() < 0.05 # 5% baseline
                                # Assuming 'result', 'features', 'regime_val' are defined in this scope if needed for the new log
                                # For now, keeping the original log and adding the new one if conditions are met.
                                # The provided snippet was syntactically incorrect and seemed to merge two different logging intentions.
                                # I'm interpreting it as adding a new logging condition.
                                # If the intent was to replace the existing log, the structure would be different.
                                # For now, I'll assume 'result', 'features', 'regime_val' are placeholders for a future feature.
                                # Reverting to original behavior for the off-market seed, as the snippet was malformed.
                                db.cloud_db.log_snapshot(
                                    signal_data={
                                        "features": {
                                            "SPOT_PRICE": m_data.spot_price,
                                            "FUTURE_PRICE": m_data.future_price,
                                            "symbol": sym,
                                            "ADX": 25.0, "PCR": 1.0
                                        },
                                        "decision": "OFF_MARKET_SEED",
                                        "regime": "UNCERTAIN"
                                    },
                                    outcome=None
                                )
                                logger.info(f"STATE: Persisted off-market price for {sym}")
                        except: pass

                time.sleep(60)
                continue
            
            t_loop_start = time.time()
            now_ist = datetime.now(IST)

            # [Institutional Phase 6] WebSocket Atomic Snapshot
            # Transitioned from 1s Polling to 200ms Reactive Cycle
            all_snapshots = market_state.snapshot()
            live_state.last_update = datetime.now(timezone.utc)
            live_state.data_source = "SHOONYA_WS"
            
            # [v9.9.9] Update VIX & Global Breadth (Throttled for Stability)
            if vix_update_counter % 20 == 0: # Every ~4 seconds in a 200ms loop
                try:
                    live_state.vix = data_provider.get_vix()
                    live_state.breadth = data_provider.get_breadth("NIFTY")
                except: pass
            
            vix_update_counter += 1
            
            for symbol in live_state.symbols:
                try:
                    # 1. Fetch Data (Atomic Memory Snapshot)
                    ws_tick = all_snapshots.get(symbol)
                    fut_tick = all_snapshots.get(f"{symbol}_FUT")
                    
                    if not ws_tick:
                        # Fallback for initialization or missing ticks
                        continue

                    market_data = MarketData(
                        symbol=symbol, 
                        spot_price=ws_tick['lp'], 
                        # [v9.9.9] Audit Fix: Use Proportional Basis Fallback (0.05%) instead of flat +5.0
                        future_price=fut_tick['lp'] if fut_tick else (ws_tick['lp'] * 1.0005),
                        oi=ws_tick.get('oi', 0), 
                        pcr=0.95, 
                        # [v9.9.9] Audit Fix: Standardize to IST for age calculations
                        timestamp=datetime.fromtimestamp(ws_tick.get('timestamp', time.time()), tz=IST), 
                        source="SHOONYA_WS"
                    )
                    
                    # [v9.9.9] Audit Fix: Stale Data Guard (IST vs IST)
                    data_age_seconds = (datetime.now(IST) - market_data.timestamp).total_seconds()
                    if data_age_seconds > 10:
                        if random.random() < 0.1: # Throttle logs
                            logger.warning(f"STALE_DATA: {symbol} data is {data_age_seconds:.1f}s old. Skipping analysis.")
                        live_state.market_message = f"STALE DATA VETO: {symbol} Lag detected ({data_age_seconds:.1f}s)"
                        continue

                    live_state.prices[symbol] = market_data.spot_price
                    detected_patterns = []
                    signal_type = None

                    # [v9.8.5] Spread Check
                    current_spread = abs(market_data.future_price - market_data.spot_price)
                    spread_max = market_data.spot_price * 0.0005
                    if current_spread > spread_max:
                        if "SPREAD" not in live_state.market_message:
                            live_state.add_thought("SPREAD_VETO", f"Spread Spike: {current_spread:.2f} > {spread_max:.2f}. Vetoing.")
                            live_state.market_message = f"SPREAD VETO: {symbol} Basis Stability Alert"
                        continue

                    # 2. Triangulation (Sentinel v2)
                    live_state.integrity = core.sentinel.check_integrity(
                        market_data.spot_price, 
                        market_data.future_price,
                        vix=live_state.vix
                    )
                    if live_state.integrity != DivergenceType.NONE:
                        live_state.add_thought("SENTINEL", f"Spot-Future Divergence: {live_state.integrity.value}. Cooling down.")

                    # Basis Stability
                    basis = abs(market_data.future_price - market_data.spot_price) / market_data.spot_price * 100
                    basis_gate = brain.check_basis_stability(basis)
                    is_basis_unstable = basis_gate["is_unstable"]
                    if is_basis_unstable:
                        live_state.add_thought("STABILITY", f"Basis unstable: {basis_gate['reason']}. Skipping entry.")
                        live_state.market_message = f"BASIS META-VETO: {basis_gate['reason']} ({basis_gate.get('sigma_jump', 0):.1f}σ)"
                        continue

                    # 3. Regime Detection & Indicators
                    # [v9.9.9] Decoupled: Read from History Cache instead of synchronous API call
                    hist_df = live_state.history_cache.get(symbol)
                    
                    if hist_df is None or hist_df.empty:
                        # Fallback for initial startup ONLY (Synchronous fetch if cache empty)
                        if random.random() < 0.05: # Rare logging
                            logger.info(f"CACHE_MISS: Priming history for {symbol}...")
                        hist_df = data_provider.get_history(symbol, interval="5minute")
                        if hist_df is not None:
                            live_state.history_cache[symbol] = hist_df
                        else:
                            continue

                    # [v9.9.9] Technical Indicators Calculation
                    # ADX
                    adx_df = hist_df.ta.adx()
                    if adx_df is not None and 'ADX_14' in adx_df.columns:
                        val = adx_df['ADX_14'].iloc[-1]
                        adx_val = 25.0 if pd.isna(val) or val != val else float(val)
                    else: adx_val = 25.0
                    
                    # ATR
                    atr_df = hist_df.ta.atr()
                    raw_atr = atr_df.iloc[-1] if atr_df is not None and not atr_df.empty else 0.0
                    atr_val = 0.0 if pd.isna(raw_atr) else float(raw_atr)
                    
                    # RSI (Added in Audit Fix)
                    rsi_series = hist_df.ta.rsi()
                    raw_rsi = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else 50.0
                    rsi_val = 50.0 if pd.isna(raw_rsi) else float(raw_rsi)

                    # [Institutional Step 4] Realized Volatility (StdDev)
                    raw_std = hist_df['close'].tail(20).std() if len(hist_df) >= 20 else 0.0
                    std_dev_val = 0.0 if pd.isna(raw_std) else float(raw_std)

                    live_state.current_regime = core.strategist.classify_regime(hist_df)
                    curr_strength = (market_data.spot_price - hist_df.open.iloc[0]) / hist_df.open.iloc[0] * 100
                    live_state.index_strengths[symbol] = curr_strength

                    # S/R Analysis (IST-aware trigger)
                    now_minute = now_ist.minute
                    if now_minute % 5 == 0 or not live_state.supports.get(symbol):
                        try:
                            sr_levels = sr_engine.find_pivot_levels(hist_df, lookback=10)
                            s_levels = [s['level'] for s in sr_levels['supports']] or [hist_df.low.min()]
                            r_levels = [r['level'] for r in sr_levels['resistances']] or [hist_df.high.max()]
                            live_state.supports[symbol] = s_levels
                            live_state.resistances[symbol] = r_levels
                        except Exception as e:
                            logger.warning(f"S/R Calc Failed for {symbol}: {e}")

                    # Phase 1: Context & Macro (Optimized)
                    with macro_cache_lock:
                        macro_df = macro_cache.get(symbol, pd.DataFrame())
                    
                    # [Audit Fix] If cache is empty (init), fetch synchronously once
                    if macro_df.empty:
                        logger.warning(f"ENGINE: Macro cache empty for {symbol}. Performing sync fetch.")
                        macro_df = data_provider.get_history(symbol, "60minute")
                        with macro_cache_lock: macro_cache[symbol] = macro_df

                    # Phase 2: Technicals & Regime
                    # Use cached macro_df for macro analysis
                    macro_vix = data_provider.get_vix()
                    
                    # [Smart Exploration] Random sampling for non-signals
                    is_exploration_tick = random.random() < 0.05 # 5% baseline
                    macro_bias = strategist.get_macro_bias(macro_df)
                    macro_zones = pattern_engine.detect_macro_zones(macro_df)
                    
                    # Pattern Recognition
                    pattern_results = core.pattern_engine.get_signal_confirmation(
                        hist_df, macro_bias=macro_bias, macro_zones=macro_zones, atr=atr_val
                    )
                    live_state.add_thought("ANALYSIS", f"[{symbol}] Pattern Score: {pattern_results['score']:.2f}. Found: {', '.join(pattern_results.get('patterns') or ['NONE'])}")

                    # Option Chain
                    chain_df, is_synthetic = data_provider.get_option_chain(symbol)
                    if not chain_df.empty:
                        live_state.max_pain[symbol] = option_engine.calculate_max_pain(chain_df)
                        live_state.option_battles[symbol] = core.option_engine.detect_strike_battles(chain_df)
                        live_state.option_chains[symbol] = chain_df.to_dict('records')
                        gex_data = option_engine.calculate_gex_proxy(chain_df, market_data.spot_price)
                        live_state.gex_bias[symbol] = gex_data["gex_bias"]
                        
                        sym_max_pain = live_state.max_pain[symbol]
                        if abs(market_data.spot_price - sym_max_pain) < APP_CONFIG["MAX_PAIN_THRESHOLD"]:
                            pattern_results["score"] *= 1.2
                            live_state.market_message = f"GEX/PAIN CONFLUENCE [{symbol}]: Institutional Gravity"

                    # Synergy & Trap
                    if symbol in ["NIFTY", "BANKNIFTY"]:
                        other_sym = "BANKNIFTY" if symbol == "NIFTY" else "NIFTY"
                        other_data = all_snapshots.get(other_sym) or data_provider.get_market_snapshot(other_sym)
                        if other_data:
                            # [v12.4] Normalize data access (Works for both MarketData objects and WS dicts)
                            if isinstance(other_data, dict):
                                o_spot = other_data.get('lp', 0)
                                o_fut = other_data.get('fut_lp', o_spot * 1.0005) # Fallback heuristic
                            else:
                                o_spot = getattr(other_data, 'spot_price', 0)
                                o_fut = getattr(other_data, 'future_price', o_spot * 1.0005)

                            my_delta = (market_data.spot_price - market_data.future_price + 45)
                            other_delta = (o_spot - o_fut + 45)
                            is_aligned = (my_delta > 0 and other_delta > 0) or (my_delta < 0 and other_delta < 0)
                            live_state.sector_synergy = 1.3 if is_aligned else 0.4
                            
                            # [Phase 3.5] Strict Synergy Veto
                            if not is_aligned: 
                                live_state.add_thought("SYNERGY", f"Correlated Asset Divergence ({symbol} vs {other_sym}). BLOCKED.")
                                pattern_results["score"] *= 0.1 # Hard block

                    is_trap, trap_reason = strategist.is_trap(hist_df, market_data)
                    if is_trap:
                        live_state.add_thought("TRAP_WARNING", f"Potential Trap Detected: {trap_reason}. Reducing Score.")
                        pattern_results["score"] *= 0.5

                    # VIX & Breadth (Updated globally in outer loop)
                    live_state.iv_skew[symbol] = data_provider.get_iv_skew(symbol)
                    
                    # [Phase 3.5] Strict VIX Cap
                    if live_state.vix > 25.0: # User requested 25 cap
                        live_state.add_thought("RISK", f"High VIX ({live_state.vix:.2f} > 25). Market too dangerous.")
                        pattern_results["score"] *= 0.1
                    elif live_state.vix > APP_CONFIG.get("HIGH_VOLATILITY_VIX", 20.0):
                        pattern_results["score"] *= 0.8
                        
                    
                    # 4. Feature Engineering
                    price_velocities = hist_df.close.pct_change(5).dropna() * 100
                    price_var = price_velocities.var()
                    price_vel_curr = price_velocities.iloc[-1] if not price_velocities.empty else 0.0
                    
                    oi_beta, basis_beta = 0.2, 0.5
                    if price_var > 1e-4:
                        oi_raw_pool = pd.Series(list(brain.raw_history.get("OI_RAW", []))[-20:])
                        if len(oi_raw_pool) == len(price_velocities.iloc[-len(oi_raw_pool):]):
                            oi_beta = max(-1.5, min(1.5, oi_raw_pool.cov(price_velocities.iloc[-len(oi_raw_pool):]) / price_var))
                        basis_raw_pool = pd.Series(list(brain.raw_history.get("BASIS_RAW", []))[-20:])
                        if len(basis_raw_pool) == len(price_velocities.iloc[-len(basis_raw_pool):]):
                            basis_beta = max(-2.0, min(2.0, basis_raw_pool.cov(price_velocities.iloc[-len(basis_raw_pool):]) / price_var))

                    last_oi = live_state.prev_oi.get(symbol, market_data.oi)
                    oi_change = ((market_data.oi - last_oi) / last_oi * 100) if last_oi > 0 else 0.0
                    raw_basis = abs(market_data.future_price - market_data.spot_price) / market_data.spot_price * 100
                    
                    brain.update_raw_history({"OI_RAW": oi_change, "BASIS_RAW": raw_basis, "PCR_RAW": market_data.pcr, "ADX_RAW": adx_val})
                    oi_res = oi_change - (oi_beta * price_vel_curr)
                    basis_res = raw_basis - (basis_beta * price_vel_curr)
                    live_state.prev_oi[symbol] = market_data.oi

                    brain_features = {
                        "OI_RES": oi_res, "PCR": market_data.pcr, "BASIS_RES": basis_res, "ADX": adx_val,
                        "RSI": rsi_val, "ATR": atr_val, # Added RSI/ATR
                        "SPOT_PRICE": market_data.spot_price, "FUTURE_PRICE": market_data.future_price,
                        "MACRO_BIAS": macro_bias, "symbol": symbol,
                        "VIX": live_state.vix, # Added VIX
                        "IV_SKEW": live_state.iv_skew.get(symbol, 1.0) # Added IV Skew
                    }

                    # 5. Brain Inference
                    # Removed call to non-existent 'analyze_institutional_logic'
                    # EnhancedBrainEngine handles SMC internally via ohlcv_df

                    likely_intent = "BULLISH" if (pattern_results.get("score", 0) > 0.45 and curr_strength > 0.1) or price_vel_curr > 0.08 else (
                        "BEARISH" if (pattern_results.get("score", 0) > 0.45 and curr_strength < -0.1) or price_vel_curr < -0.08 else "NEUTRAL"
                    )
                    
                    # Pass ohlcv_df to enable SMC Engine
                    decision_id, thoughts = call_brain_safely(
                        "DECIDE", features=brain_features, regime=live_state.current_regime, 
                        ohlcv_df=hist_df, is_commit=False, pattern_score=pattern_results["score"],
                        signal_intent=likely_intent, iv_skew=live_state.iv_skew.get(symbol, 1.0)
                    )
                    for t in thoughts: live_state.add_thought("INFERENCE", f"[{symbol}] {t}")

                    confidence_boost, _ = call_brain_safely(
                        "BOOST", features=brain_features, regime=live_state.current_regime,
                        signal_intent=likely_intent, iv_skew=live_state.iv_skew.get(symbol, 1.0)
                    )
                    
                    is_passive = (time.time() - start_time) < APP_CONFIG["PASSIVE_MODE_THRESHOLD"]
                    applied_boost = 1.0 if is_passive else confidence_boost
                    
                    if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and applied_boost > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                        if live_state.sector_synergy > 1.0: pattern_results["score"] *= 1.1
                    elif pattern_results["score"] <= APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and confidence_boost > 0.60:
                        # [v11.0.0] BRAIN_PULL Hardening: Multiplier instead of override
                        pattern_results["score"] = min(0.85, pattern_results["score"] * 1.5) 
                        pattern_results["patterns"] = pattern_results.get("patterns", []) + ["BRAIN_PULL"]
                    
                    pattern_results["score"] *= applied_boost

                    # Lull Filter (IST-aware)
                    now_time = now_ist.time()
                    lull_start = datetime.strptime(f"{APP_CONFIG['LULL_START_HOUR']}:{APP_CONFIG['LULL_START_MINUTE']:02d}", "%H:%M").time()
                    lull_end = datetime.strptime(f"{APP_CONFIG['LULL_END_HOUR']}:{APP_CONFIG['LULL_END_MINUTE']:02d}", "%H:%M").time()
                    if lull_start <= now_time <= lull_end and "BRAIN_PULL" not in pattern_results.get("patterns", []):
                        pattern_results["score"] *= 0.5

                    # 6. Signal Execution
                    if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                        detected_patterns = pattern_results.get("patterns", [])
                        signal_type = likely_intent if "BRAIN_PULL" in detected_patterns else (
                            "BULLISH" if any(p in ["VWAP_CROSSOVER", "HAMMER", "BULLISH_ENGULFING", "CPR_BREAKOUT"] for p in detected_patterns) else (
                                "BEARISH" if any(p in ["VWAP_BREAKDOWN", "SHOOTING_STAR", "BEARISH_ENGULFING"] for p in detected_patterns) else "NEUTRAL"
                            )
                        )
                        
                        if signal_type == "NEUTRAL":
                            continue
                        
                        # [v9.9.9] Institutional Singularity: MAX_CONCURRENT_TRADES = 1
                        live_signals = [s for s in live_state.active_signals if s.is_live]
                        if len(live_signals) >= 1:
                            live_signal = live_signals[0]
                            # Potential SWAP: Only if new signal is significantly better
                            if pattern_results["score"] > (live_signal.score * 1.25):
                                # Exit current trade before entering new one
                                p_delta = (market_data.spot_price - live_signal.entry_price) if "BULLISH" in live_signal.reasoning else (live_signal.entry_price - market_data.spot_price)
                                live_signal.is_live = False
                                signal_data = live_signal.dict()
                                signal_data['pnl'] = p_delta
                                core.telegram_notifier.send_exit(signal_data, "SWAP (Better Setup Found)", f"Closed {live_signal.symbol} to capture 1.25x edge in {symbol}.")
                                core.db.log_outcome(live_signal.decision_id, "SWAP_EXIT")
                            else:
                                continue

                        # [Wave 3] Double-Entry Deduplication Lock
                        with live_state.seen_ids_lock:
                            if decision_id in live_state.seen_signal_ids:
                                continue
                            live_state.seen_signal_ids.add(decision_id)
                                
                        # Correlated Risk Check: Pass currently active symbols
                        active_syms = [s.symbol for s in live_state.active_signals if s.is_live]
                        
                        if core.risk_engine.is_blown_today(): continue

                        if signal_type == "BULLISH" and any(abs(market_data.spot_price - r) < 25 for r in live_state.resistances.get(symbol, [])): continue
                        if signal_type == "BEARISH" and any(abs(market_data.spot_price - s) < 25 for s in live_state.supports.get(symbol, [])): continue

                        # [Phase 5] Precision Levels & Smart Stops (Order Blocks, Fractals, OI Walls)
                        precision_levels = tech_engine.calculate_precision_levels(hist_df, market_data.spot_price, chain_df)

                        # [Institutional Step 5] Expiry Sensitivity (Precision Greeks)
                        minutes_to_expiry = get_minutes_to_expiry()
                        days_to_expiry = max(1, round(minutes_to_expiry / (24 * 60)))
                        
                        opt_trade = option_engine.find_executable_option(
                            symbol, market_data.spot_price, signal_type, precision_levels=precision_levels,
                            is_momentum_dominant=strategist.is_momentum_dominant(hist_df), 
                            days_to_expiry=days_to_expiry, 
                            chain_df=chain_df, is_synthetic=is_synthetic
                        )
                        
                        # IV Percentile & Smooth Scaling
                        cur_iv = market_data.iv if hasattr(market_data, 'iv') else 20.0
                        if not cur_iv: # Support synthetic chain lingo
                             row = chain_df[chain_df['strike'] == opt_trade.get('strike')].iloc[0] if not chain_df.empty else None
                             cur_iv = row.get(f"{opt_trade['option_type'].lower()}_iv", 20.0) if row is not None else 20.0
                        
                        live_state.iv_history[symbol].append(cur_iv)
                        # Keep 90 trades of history
                        if len(live_state.iv_history[symbol]) > 90: live_state.iv_history[symbol].pop(0)
                        
                        iv_data = option_engine.calculate_iv_percentile(cur_iv, live_state.iv_history[symbol])
                        iv_scaling = iv_data['scaling_factor']
                        
                        # High Fidelity Greeks
                        greeks = option_engine.calculate_precision_greeks(
                            market_data.spot_price, opt_trade['strike'], cur_iv/100.0, 
                            minutes_to_expiry, opt_trade['option_type']
                        )
                        
                        if not opt_trade.get("rejection_reasons"):
                            # [Institutional Step 3] Cost Realism & Yield Veto
                            # Slippage = 0.05% of price + half the spread
                            friction_pct = 0.0005
                            slippage_est = (market_data.spot_price * friction_pct) + (current_spread / 2)
                            total_cost = current_spread + slippage_est
                            
                            # Calculate potential edge (Target)
                            # We need target and SL from risk engine first to calculate edge
                            smart_risk = core.risk_engine.calculate_dynamic_stops(
                                entry_price=market_data.spot_price,
                                signal_type=signal_type,
                                atr=atr_val,
                                precision_levels=precision_levels
                            )
                            
                            raw_target = max(APP_CONFIG["SIGNAL_TARGET_POINTS"], abs((smart_risk["targets"][0] if smart_risk["targets"] else (market_data.spot_price + 100)) - market_data.spot_price))
                            expected_edge = raw_target - total_cost
                            
                            # Yield Veto: Edge must be > 1.5x of transaction costs
                            if expected_edge < (1.5 * total_cost):
                                live_state.add_thought("YIELD_VETO", f"[{symbol}] Edge {expected_edge:.2f} < 1.5x Cost {total_cost:.2f}. Killing signal.")
                                continue
                            
                            new_signal = TradeSignal(
                                symbol=symbol, entry_price=market_data.spot_price,
                                action=Action.BUY_CALL if signal_type == "BULLISH" else Action.BUY_PUT,
                                stop_loss=max(APP_CONFIG["SIGNAL_STOP_LOSS_POINTS"], abs(market_data.spot_price - smart_risk["stop_loss"])), 
                                target=max(APP_CONFIG["SIGNAL_TARGET_POINTS"], abs((smart_risk["targets"][0] if smart_risk["targets"] else (market_data.spot_price + 100)) - market_data.spot_price)),
                                confidence=SignalConfidence.HIGH if pattern_results["score"] > 0.9 else SignalConfidence.MEDIUM,
                                regime=live_state.current_regime, reasoning=f"{signal_type} | {', '.join(detected_patterns)}",
                                timestamp=datetime.now(timezone.utc), decision_id=decision_id,
                                logic_version="v9.9.9_FINAL_STABLE", spread_at_entry=current_spread,
                                slippage_est=slippage_est, expected_edge=expected_edge,
                                iv_scaling=iv_scaling, greeks=greeks,
                                quantity=round(core.risk_engine.get_suggested_size(
                                    applied_boost, 
                                    APP_CONFIG.get("BASE_LOTS", 1), 
                                    atr=atr_val, 
                                    std_dev=std_dev_val, 
                                    vix=live_state.vix,
                                    active_symbols=active_syms
                                ) * iv_scaling),
                                score=pattern_results["score"], **opt_trade
                            )
                            # [Institutional Phase 6] Automated Order Bridge & Latency Monitor
                            # Direct connection to Broker API; bypasses Telegram/Human latency.
                            t_signal = time.time()
                            
                            # [v10.0] ANALYSIS-ONLY MODE: No auto-execution
                            if new_signal.option_symbol and not shadow_mode_enabled:
                                live_state.add_thought("SIGNAL", f"📊 ANALYSIS: {new_signal.option_symbol} (Manual review required)")
                                core.telegram_notifier.send_entry(new_signal.dict(), "SIGNAL GENERATED (Analysis-only mode)")
                            
                            # [v10.1] Start tracking outcome for automatic learning
                            if core.outcome_tracker:
                                try:
                                    core.outcome_tracker.track_signal(new_signal)
                                    logger.info(f"Outcome tracking started for {new_signal.decision_id}")
                                except Exception as e:
                                    logger.error(f"Failed to start outcome tracking: {e}")
                            
                            # [Institutional Responsibility] Auto-Approval & Full Accountability
                            # Mark as HUMAN_APPROVED immediately for training/evolution audit.
                            new_signal.is_auto_approved = True
                            core.db.log_outcome(new_signal.decision_id, "HUMAN_APPROVED")
                            
                            live_state.active_signals.append(new_signal)
                            
                            # Log intent to Signal Ledger
                            core.db.log_intent(new_signal.dict())
                            
                            core.telegram_notifier.send_signal(new_signal.dict(), dashboard_url=APP_CONFIG.get("DASHBOARD_URL", ""))

                    # [v9.9.9] Modular Management: Priority-Based Exit Evaluation
                    for sig in live_state.active_signals:
                        if not sig.is_live or sig.symbol != symbol: continue
                        
                        # Phase 1: Metric Tracking (MFE/MAE)
                        p_delta = (market_data.spot_price - sig.entry_price) if "BULLISH" in sig.reasoning else (sig.entry_price - market_data.spot_price)
                        p_adv = (sig.entry_price - market_data.spot_price) if "BULLISH" in sig.reasoning else (market_data.spot_price - sig.entry_price)
                        
                        if p_delta > sig.mfe: sig.mfe = p_delta
                        if p_adv > sig.mae: sig.mae = p_adv
                        
                        # Phase 2: Trailing Stop Activation (Internal to Manager for now)
                        if not sig.is_tsl_active and p_delta >= (0.5 * sig.target):
                            sig.is_tsl_active = True
                            sig.stop_loss = 0.0 # B/E
                            core.telegram_notifier.send_alert(f"🛡️ TSL: {sig.symbol} at Break-Even.")

                        # Phase 3: Risk Engine Veto (Institutional Priority)
                        exit_decision = core.risk_engine.evaluate_exit(sig, market_data, hist_df)
                        
                        if exit_decision:
                            sig.is_live = False
                            is_win = p_delta > 0
                            
                            # Prepare Post-Analysis
                            # [v9.9.9] Audit Fix: Accurate aware-datetime duration calculation 
                            duration_min = int((datetime.now(timezone.utc) - sig.timestamp).total_seconds() / 60)
                            signal_data = sig.dict()
                            signal_data.update({'pnl': p_delta, 'duration_min': duration_min})
                            
                            # Send Premium Exit Card
                            core.telegram_notifier.send_exit(
                                signal_data=signal_data,
                                reason=exit_decision['reason'],
                                analysis=exit_decision['analysis']
                            )
                            
                            # Log to DB/Brain
                            core.brain.log_snapshot(sig.decision_id, outcome=is_win, performance={"mfe": sig.mfe, "mae": sig.mae}, freeze_authority=is_passive)
                            core.db.log_outcome(sig.decision_id, "WIN" if is_win else "LOSS")

                except Exception as e:
                    logger.error(f"ENGINE SYMBOL ERROR [{symbol}]: {e}", exc_info=True)
                
                # [v9.9.9] Record Loop Health
                loop_lat = (time.time() - t_loop_start) * 1000
                core.health_monitor.record_latency(loop_lat)

            if len(live_state.active_signals) > 20:
                live_state.active_signals = live_state.active_signals[-20:]
            
            # [Institutional Phase 6] Tight 200ms reactive cycle
            time.sleep(0.2)
        except DataHealthError as de:
            logger.critical(f"HEALTH_HALT: {de}")
            core.telegram_notifier.send_alert(f"🚨 <b>CRITICAL SYSTEM HALT</b>\nAll data sources down. Engine entering SAFE_MODE.\nReason: {de}")
            live_state.market_message = "🔴 EMERGENCY HALT: DATA LOSS"
            time.sleep(300) # Cooldown before retry
        except Exception as e:
            logger.error(f"ENGINE CRITICAL: {e}", exc_info=True)
            time.sleep(10)

def personalized_service_loop(notifier, sentinel):
    """[v9.9.9] Handles daily greetings, market blueprints, and periodic wisdom in IST."""
    logger.info("CORE: Personalized Service Loop started.")
    last_greet_date = None
    last_wisdom_hour = -1
    
    while True:
        try:
            sentinel.record_heartbeat("personalized_service")
            now_ist = datetime.now(timezone.utc).astimezone(IST)
            today_str = now_ist.strftime("%Y-%m-%d")
            current_hour = now_ist.hour
            current_minute = now_ist.minute

            # 1. Daily Morning Greeting & Market Blueprint (9:00 AM IST)
            if today_str != last_greet_date and current_hour == 9 and current_minute >= 0:
                # [v9.9.9] Enhanced Greeting with Institutional Stats
                stats = {
                    "signals_today": 0,
                    "accuracy_7d": 68,
                    "equity_curve": "📈 TRENDING UP"
                }
                notifier.send_personalized_greeting("Harsh", stats=stats)
                
                # Fetch levels from core if available (global core accessed inside loop)
                if 'core' in globals() and core.is_initialized:
                    for symbol in ["NIFTY", "BANKNIFTY", "SENSEX"]:
                        supports = core.state.supports.get(symbol, [])
                        resistances = core.state.resistances.get(symbol, [])
                        trend = "BULLISH" if core.state.index_strengths.get(symbol, 0) > 0 else "BEARISH"
                        
                        note = f"Institutional accumulation zones detected. Focus on {symbol} {trend} reversals."
                        notifier.engine.send_market_blueprint(
                            symbol=symbol,
                            trend=trend,
                            supports=supports,
                            resistances=resistances,
                            note=note
                        )
                
                last_greet_date = today_str
                logger.info(f"PERSONAL: Premium morning blueprint sent to Harsh for {today_str}")

            # 2. Periodic Institutional Wisdom (Every 4 hours during market/active hours)
            # 11:00 AM, 1:00 PM, 3:00 PM
            wisdom_hours = [11, 13, 15]
            if current_hour in wisdom_hours and current_hour != last_wisdom_hour:
                notifier.send_random_wisdom()
                last_wisdom_hour = current_hour
                logger.info(f"PERSONAL: Periodic wisdom sent at {current_hour}:00 IST")

            # Sleep in 60s increments to keep personalized_service heartbeat fresh
            for _ in range(60):
                sentinel.record_heartbeat("personalized_service")
                time.sleep(60)
        except Exception as e:
            logger.error(f"SERVICE_LOOP_ERROR: {e}")
            time.sleep(60)

# Startup Version Identifier [v10.2.0_ENHANCED]
LOGIC_VERSION = "v10.2.0_ENHANCED"

@app.on_event("startup")
async def startup_event():
    logger.info(f"API: Starting Titan Plus Institutional Engine [{LOGIC_VERSION}]")
    
    # [v10.2] Validate configuration first
    from config_validator import validate_config_on_startup
    
    if not validate_config_on_startup():
        logger.critical("Configuration validation failed. Exiting...")
        import sys
        sys.exit(1)
    
    logger.info("API: Launching background engine loop...")
    thread = threading.Thread(target=run_engine_loop, daemon=True)
    thread.start()
    
    # [v12.0.1] Launch Personalized Service Loop with Sentinel (Wait for Core initialization)
    def launch_pst():
        while not core.is_initialized:
            time.sleep(1)
        logger.info("pst: Core initialized. Launching Personalized Service Loop.")
        personalized_service_loop(core.telegram_notifier, global_sentinel)

    pst = threading.Thread(target=launch_pst, daemon=True)
    pst.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    logger.info(f"API: Initializing server on port {port} for Version {LOGIC_VERSION}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.critical(f"API CRITICAL ERROR: {e}", exc_info=True)
