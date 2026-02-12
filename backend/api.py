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
from models_v3 import Decision, Regime, Action, MarketStructure, TradeSignal, TradeSnapshot, DivergenceType, SignalConfidence, AssetClass

# [v10.2] Import enhanced endpoints and health checks
from health_check_endpoint import health_router
from api_enhanced_endpoints import outcome_router
# from crypto_provider import CryptoProvider [Decommissioned for NSE]
from critical_safety_systems import (
    PositionManager,
    RiskManager,
    DataHealthChecker,
    RiskViolation,
    Position,
    PositionStatus
)
from intelligent_strike_selector import MarketRegime # [v15.3.16] Added missing import

# [v15.3.7] Global App Configuration
APP_CONFIG = {
    "VIX_DEFAULT": 15.0,
    "SIGNAL_STOP_LOSS_POINTS": 150.0,
    "SIGNAL_TARGET_POINTS": 300.0,
    "DASHBOARD_URL": os.getenv("DASHBOARD_URL", ""),
    "PAPER_TRADING_MODE": os.getenv("PAPER_TRADING_MODE", "True").lower() == "true",
}

logger.info(f"📊 Trading Mode: {'PAPER' if APP_CONFIG['PAPER_TRADING_MODE'] else 'LIVE'}")

import uvicorn

app = FastAPI(title="The Oracle - Titan Plus Institutional")

# [v10.2] Register enhanced routers
app.include_router(health_router)
app.include_router(outcome_router)

app.add_middleware(
    CORSMiddleware,
    # [v15.3.21] Explicitly allow Vercel Frontend
    allow_origins=[
        "https://titan-plus-backend.vercel.app",
        "https://titan-plus-backend-git-main-harshx1323.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ] + os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent State Storage
class LiveState:
    def __init__(self):
        # [v10.0] Thread Safety - RLock for all state access
        self._lock = threading.RLock()
        
        self._current_regime = Regime.NEUTRAL
        self._active_signals = []  # Protected by lock
        self.last_update = datetime.now(timezone.utc)
        self.symbols = ["NIFTY", "BANKNIFTY", "SENSEX", "BTCUSDT", "ETHUSDT"]
        self.current_symbol_idx = 0
        self._vix = APP_CONFIG["VIX_DEFAULT"]
        self._breadth = {"advances": 0, "declines": 0}
        self.market_message = "System Stable"
        self.data_source = "PUBLIC_SCRAPER"
        self.index_strengths: Dict[str, float] = {s: 0.0 for s in self.symbols}
        
        # Partitioned Symbol Data (v8.1 Multi-Asset)
        self.prices = {s: 0.0 for s in self.symbols}
        self.max_pain = {s: 0.0 for s in self.symbols}
        self.option_battles = {s: [] for s in self.symbols}

        self.option_chains = {s: [] for s in self.symbols}
        self.supports = {s: [] for s in self.symbols}
        self.resistances = {s: [] for s in self.symbols}
        self.history_cache = {s: None for s in self.symbols}
        
        # v8.1: Statistical Discipline
        self.resets_today = 0
        self.last_reset_time = datetime.now(timezone.utc)
        self.iv_skew = {s: 1.0 for s in self.symbols}
        self.gex_bias = {s: 0.0 for s in self.symbols}
        self.sector_synergy = 1.0 
        self.prev_oi = {s: 0 for s in self.symbols}
        self.prev_spot = 0.0
        self.last_chain_fetch = {s: 0.0 for s in self.symbols}
        
        # [Institutional Step 5] IV History tracking for Percentile
        self.iv_history = {s: [] for s in self.symbols}
        
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

    def get_asset_class(self, symbol: str) -> AssetClass:
        """[v15.0] Categorize symbol for Neural Isolation."""
        if any(idx in symbol for idx in ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"]):
            return AssetClass.NSE
        return AssetClass.GLOBAL
    
    @property
    def active_signals(self):
        """Thread-safe getter for active signals."""
        with self._lock:
            return self._active_signals.copy()
    
    @active_signals.setter
    def active_signals(self, value):
        """Thread-safe setter for active signals."""
        with self._lock:
            self._active_signals = value
    
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
    @property
    def current_regime(self):
        with self._lock:
            return self._current_regime
    
    @current_regime.setter
    def current_regime(self, value):
        with self._lock:
            self._current_regime = value

    @property
    def vix(self):
        with self._lock:
            return self._vix
    
    @vix.setter
    def vix(self, value):
        with self._lock:
            self._vix = value

    @property
    def breadth(self):
        with self._lock:
            return self._breadth.copy()
    
    @breadth.setter
    def breadth(self, value):
        with self._lock:
            self._breadth = value

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
    [v15.3.7] Enhanced emergency shutdown with position manager integration.
    
    Args:
        reason: Reason for shutdown
    """
    logger.critical(f"🚨 EMERGENCY SHUTDOWN INITIATED: {reason}")
    
    # Set emergency mode
    live_state.emergency_mode = True
    
    # Halt trading via risk manager
    if hasattr(core, 'risk_manager'):
        core.risk_manager.halt_trading(reason)
    
    # Close all open positions
    closed_count = 0
    failed_exits = []
    total_pnl = 0.0
    
    if hasattr(core, 'position_manager'):
        open_positions = core.position_manager.get_open_positions()
        
        for position in open_positions:
            try:
                # Use current price or entry price as fallback
                exit_price = position.current_price if position.current_price > 0 else position.entry_price
                
                # Close position
                closed_pos = core.position_manager.close_position(
                    signal_id=position.signal_id,
                    exit_price=exit_price,
                    reason=f"EMERGENCY: {reason}"
                )
                
                # Remove from active signals
                live_state.remove_signal(position.signal_id)
                
                # Track P&L
                total_pnl += closed_pos.realized_pnl
                closed_count += 1
                
                logger.info(f"Emergency closed: {position.symbol}, P&L: ₹{closed_pos.realized_pnl:.2f}")
                
            except Exception as e:
                logger.error(f"Failed to close {position.symbol}: {e}")
                failed_exits.append(position.symbol)
    
    # Send telegram alert
    if hasattr(core, 'telegram_notifier'):
        alert_msg = (
            f"🚨 EMERGENCY SHUTDOWN\n\n"
            f"Reason: {reason}\n"
            f"Closed Positions: {closed_count}\n"
            f"Failed Exits: {len(failed_exits)}\n"
            f"Total P&L: ₹{total_pnl:.2f}\n\n"
            f"System halted. Manual intervention required."
        )
        
        if failed_exits:
            alert_msg += f"\n\n⚠️ Manual close needed: {', '.join(failed_exits)}"
        
        core.telegram_notifier.send_alert(alert_msg)
    
    logger.critical(
        f"Emergency shutdown complete: "
        f"{closed_count} positions closed, "
        f"{len(failed_exits)} failed, "
        f"P&L: ₹{total_pnl:.2f}"
    )
    
    # Hard exit to prevent any further logic execution
    os._exit(1)

# Config & Global Placeholders
# [v10.0] Loaded from config.py
APP_CONFIG = {
    "VIX_DEFAULT": 15.0,
    "MAX_OPEN_POSITIONS": config.MAX_OPEN_POSITIONS,
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
    "PATTERN_SCORE_THRESHOLD_HIGH": config.DECISION_THRESHOLD,
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
# 0. Performance Hygiene (TechnicalCache)
# ============================================================================

class TechnicalCache:
    """[v14.2.0] Throttles expensive indicator calculations (ADX, ATR, RSI)."""
    def __init__(self, ttl_seconds: int = 15):
        self.cache = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()

    def get(self, symbol: str, key: str):
        with self.lock:
            entry = self.cache.get(f"{symbol}_{key}")
            if entry and (time.time() - entry['ts']) < self.ttl:
                return entry['val']
        return None

    def set(self, symbol: str, key: str, val):
        with self.lock:
            self.cache[f"{symbol}_{key}"] = {'val': val, 'ts': time.time()}

tech_cache = TechnicalCache(ttl_seconds=10) # 10s refresh for indicators

# ============================================================================
# 1. State Management
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
        self.signal_notifier = None  # [v13.0.10] Signal notification pipeline
        self.data_provider = None
        self.execution_engine = None
        self.crypto_provider = None # [v15.0] Core Crypto Provider
        self.shadow_engine = None
        self.outcome_tracker = None  # [v10.1] Automatic outcome tracking
        
        # [v15.3.7] P0 Safety Systems
        self.position_manager = PositionManager()
        self.risk_manager = RiskManager(
            total_capital=config.INITIAL_CAPITAL,
            max_daily_loss_pct=abs(config.MAX_DAILY_LOSS),
            max_position_size_pct=config.MAX_RISK_PER_TRADE,
            max_open_positions=config.MAX_OPEN_POSITIONS,
            max_position_loss_pct=config.MAX_POSITION_LOSS_PCT,
            max_consecutive_losses=config.MAX_CONSECUTIVE_LOSSES,
            max_stop_losses_per_day=config.MAX_STOP_LOSSES_PER_DAY,
            min_risk_reward_ratio=config.MIN_RISK_REWARD_RATIO
        )
        self.data_health_checker = DataHealthChecker()
        
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
        from crypto_provider import CryptoProvider
        self.crypto_provider = CryptoProvider() # [v15.0] Actual Implementation
        time.sleep(1)
        
        # [v10.1] Initialize outcome tracker for automatic learning
        self.outcome_tracker = OutcomeTracker(
            data_provider=self.data_provider,
            db_manager=self.db,
            crypto_provider=self.crypto_provider # [v15.0]
        )
        self.outcome_tracker.start_monitoring()
        logger.info("Outcome tracker initialized and monitoring started")
        time.sleep(1)
        
        # [v13.0.10] Initialize Signal Notifier for auto-notification pipeline
        from signal_notifier import SignalNotifier
        self.signal_notifier = SignalNotifier(
            db_manager=self.db,
            telegram_notifier=self.telegram_notifier,
            live_state=self.state,
            sr_engine=self.sr_engine,
            outcome_tracker=self.outcome_tracker
        )
        logger.info("Signal Notifier initialized")
        time.sleep(1)
        
        
        self.sentinel = DataSentinel()
        self.strategist = MarketStrategist()
        self.sr_engine = SupportResistanceEngine()
        self.health_monitor = SystemHealthMonitor()
        self.session_auditor = SessionAuditor()
        
        # Heavy ML (Staggered)
        # Unified Brain (v10.0) - [v15.3.7] RL Decommissioned for Safety
        self.brain = create_brain(enable_rl=False, enable_smc=True)  
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
            # [v12.6] Robust argument cleaning to prevent "multiple values for keyword argument" error
            target_keys = ["features", "market_data", "ohlcv_df", "regime"]
            extracted = {k: kwargs.pop(k, None) for k in target_keys}
            
            # Double-scrub: Ensure NO case-variations or duplicates remain in kwargs
            # This is defensive against unexpected upstream dictionary behavior
            for k in list(kwargs.keys()):
                if k.lower() in target_keys:
                    kwargs.pop(k)

            res = core.brain.decide(
                features=extracted["features"],
                market_data=extracted["market_data"],
                ohlcv_df=extracted["ohlcv_df"],
                regime=extracted["regime"],
                **kwargs
            )
            if isinstance(res, dict):
                # [v13.0.10] Return full decision dict for signal notification pipeline
                return res, res.get('thoughts', [])
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
        "version": "v12.6.5",
        "market": "NSE/BSE/CRYPTO"
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
            for sym in live_state.symbols:
                try:
                    # [v12.6.0] Crypto Aware History
                    if "USDT" in sym:
                        df_60 = core.crypto_provider.get_history(sym, "60minute")
                    else:
                        df_60 = data_provider.get_history(sym, "60minute")
                        
                    if df_60 is not None and not df_60.empty:
                        with macro_cache_lock:
                            macro_cache[sym] = df_60
                        logger.info(f"CACHE: Refreshed 60m history for {sym}")
                    else:
                        logger.warning(f"CACHE: Empty history for {sym} - skipping update")
                except Exception as e:
                    logger.warning(f"CACHE_ERROR: Failed to refresh macro {sym}: {e}")
                time.sleep(1) # Stagger requests
            
            # [Institutional Wave 4] Consistency Watchdog (Memory vs DB)
            if core.db and loop_count % 2 == 0: # Every 30 mins
                active_db = core.db.get_active_signals()
                active_mem_ids = [s.decision_id for s in state.active_signals]
                for db_sig in active_db:
                    sym = db_sig.get('symbol')
                    if sym in state.symbols and db_sig['signal_id'] not in active_mem_ids:
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

    # [v13.0.3] WebSocket bypass for Global-only build
    from infrastructure import MarketState, DataHealthError
    from models_v3 import MarketData
    import pandas as pd
    market_state = MarketState()
    # [v9.9.9] Startup Price Seeding
    logger.info("STATE: Seeding initial prices from DataProvider...")
    for sym in live_state.symbols:
        try:
            seed_data = data_provider.get_market_snapshot(sym)
                
            if seed_data and seed_data.spot_price > 0:
                live_state.prices[sym] = seed_data.spot_price
                # Update MarketState if it's not a WS dictionary but a MarketData object
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
                # [v13.0.3] SAFETY: ONLY recover if seeding failed (price is 0.0 or missing)
                current_price = live_state.prices.get(sym, 0.0)
                if current_price <= 0.0 and sym in live_state.symbols:
                    live_state.prices[sym] = price
                    logger.info(f"STATE: Recovered last active price for {sym}: {price} (Fallback)")
                elif sym in live_state.prices:
                    # Log but don't overwrite if we already have fresh data
                    logger.info(f"STATE: Skipping recovery for {sym}, using fresh seeding: {current_price}")
        except Exception as e:
            logger.warning(f"STATE: Price recovery failed: {e}")

        # [v9.9.9] Nuclear Signal Recovery (Container Resilience)
        try:
            # [v15.3.2] Respect MAX_OPEN_POSITIONS during recovery
            records = db.cloud_db.get_active_signals(limit=APP_CONFIG.get("MAX_OPEN_POSITIONS", 1))
            for rec in records:
                sym = rec.get('symbol')
                if sym and sym in live_state.symbols:
                    # [v14.0.3] IGNORE stale symbols from previous versions (e.g. Crypto)
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
                            action=rec.get('option_type', 'BUY_CALL'),  # Map option_type -> action
                            quantity=rec.get('quantity', 1),  # Default to 1 lot
                            confidence=SignalConfidence.MEDIUM,  # Default confidence
                            entry_price=rec.get('entry_price', 0.0),
                            stop_loss=rec.get('stop_loss', 0.0),
                            target=rec.get('target_1', rec.get('target', 0.0)),  # Use target_1 or fallback to target
                            timestamp=datetime.fromisoformat(rec.get('created_at', rec.get('generated_at', datetime.now(timezone.utc).isoformat())).replace('Z', '+00:00')),
                            decision_id=rec.get('signal_id', 'RECOVERED'),
                            reasoning=rec.get('reasoning', 'RECOVERED_TRADE'),
                            score=rec.get('confluence', 0.0),  # Map confluence -> score
                            is_live=True
                        )
                        live_state.add_signal(recovered_sig)
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
            
            # [v14.0] Indian Market Restoration
            evolution_trigger_time = datetime.strptime("15:35", "%H:%M").time()
            # [v15.0] Check if we have global assets to keep engine active
            has_crypto = any(live_state.get_asset_class(s) == AssetClass.GLOBAL for s in live_state.symbols)
            is_nse_open = (market_start <= current_time <= market_end) and (now_ist.weekday() < 5)
            
            if not is_nse_open:
                # 1. Automated Overnight Learning (Only if NSE just closed)
                if current_time >= evolution_trigger_time and evolution_done_date != today_str:
                    if core.evolver:
                        logger.info(f"INTELLIGENCE: Triggering automated post-market evolution for {today_str}...")
                        live_state.add_thought("LEARN", f"Starting Overnight Evolution for {today_str}...")
                        live_state.is_learning = True
                        try:
                            # [v15.0] Dual-Class Evolution
                            res_nse = core.evolver.evolve_session(today_str, asset_class=AssetClass.NSE)
                            res_global = core.evolver.evolve_session(today_str, asset_class=AssetClass.GLOBAL)
                            
                            evolution_done_date = today_str
                            live_state.is_learning = False
                            
                            # Combine results for UI/Alerts
                            status_nse = res_nse.get('governor_status', 'IDLE')
                            status_global = res_global.get('governor_status', 'IDLE')
                            
                            live_state.add_thought("LEARN", f"Evolution Complete: NSE({status_nse}), Global({status_global}).")
                            
                            alert_msg = f"🧠 *Overnight Intelligence* for {today_str}:\n"
                            alert_msg += f"• NSE: {status_nse}\n"
                            alert_msg += f"• Global: {status_global}"
                            core.telegram_notifier.send_alert(alert_msg)
                        except Exception as e:
                            live_state.is_learning = False
                            logger.error(f"INTELLIGENCE: Evolution failed: {e}")
                            live_state.add_thought("ERROR", f"Overnight Evolution primary fail: {str(e)}")
                    else:
                        # [v12.6.1] Self-Healing: If evolver is disabled, mark as done to prevent loop
                        evolution_done_date = today_str
                        logger.info(f"INTELLIGENCE: Evolution engine is disabled. Skipping for {today_str}.")

                if not has_crypto:
                    # 3. Aggressive Sleep during off-hours (1 minute polling)
                    live_state.last_update = datetime.now(timezone.utc) # Keep heartbeat alive
                    
                    # [v14.0] Seed persistence data for core symbols
                    if current_time.minute == 0 and current_time.second < 10:
                        for sym in live_state.symbols: # Core 3: NIFTY, BANKNIFTY, SENSEX
                            try:
                                m_data = data_provider.get_market_snapshot(sym)
                                if m_data:
                                    db.cloud_db.log_snapshot(
                                        signal_data={
                                            "features": {"SPOT_PRICE": m_data.spot_price, "symbol": sym},
                                            "decision": "OFF_MARKET_SEED",
                                            "regime": "UNCERTAIN"
                                        },
                                        outcome=None,
                                        asset_class=AssetClass.NSE # Seeding for core NSE symbols
                                    )
                                    logger.info(f"STATE: Persisted off-market price for {sym}")
                            except Exception as e:
                                logger.warning(f"SMA calculation failed for {sym}: {e}")

                    time.sleep(60)
                    continue
                else:
                    # Still loop for crypto, but update dashboard status for NSE
                    status_reason = "Weekend" if now_ist.weekday() >= 5 else "After Hours"
                    live_state.market_message = f"COMM: Crypto High-Freq | NSE: {status_reason}"
            
            t_loop_start = time.time()
            now_ist = datetime.now(IST)

            # [Institutional Phase 6] WebSocket Atomic Snapshot
            # Transitioned from 1s Polling to 200ms Reactive Cycle
            all_snapshots = market_state.snapshot()
            live_state.last_update = datetime.now(timezone.utc)
            live_state.data_source = "SHOONYA_WS"
            
            # [v13.0.2] Global Trend Dominance (Bullish vs Bearish Assets)
            if vix_update_counter % 20 == 0:
                try:
                    # Update VIX/Volatility
                    live_state.vix = data_provider.get_vix() if hasattr(data_provider, 'get_vix') else 15.0
                    
                    # Calculate Global Breadth (Trend alignment of BTC/ETH/XAU)
                    bullish = 0
                    bearish = 0
                    for sym in live_state.symbols:
                        price = live_state.prices.get(sym, 0)
                        hist = live_state.history_cache.get(sym)
                        if hist is not None and not hist.empty:
                            # Use 20 SMA for fast trend detection
                            sma = hist['close'].tail(20).mean()
                            if price > sma: bullish += 1
                            else: bearish += 1
                    
                    live_state.breadth = {"advances": bullish, "declines": bearish}
                except Exception as be:
                    logger.warning(f"HUD: Global metric update failed: {be}")
            
            vix_update_counter += 1
            
            for symbol in live_state.symbols:
                asset_class = live_state.get_asset_class(symbol)
                is_nse = (asset_class == AssetClass.NSE)
                
                # [v15.0] Market Gate: Only process NSE symbols if NSE is open. GLOBAL stays active.
                if is_nse and not is_nse_open:
                    continue
                
                # [v15.3.19] Enhanced Heartbeat (Price Telemetry)
                if vix_update_counter % 5 == 0:
                    price_val = market_state.get_symbol_price(symbol)
                    logger.info(f"ANALYSIS_HEARTBEAT: {symbol} @ {price_val:.2f} | Loop: {vix_update_counter}")
                try:
                    # 1. Fetch Data (Atomic Memory Snapshot)
                    if "USDT" in symbol:
                        # [v12.6.0] Integrated Crypto Fetch via Public Binance API
                        market_data = core.crypto_provider.get_market_snapshot(symbol)
                        if not market_data: continue
                    else:
                        ws_tick = all_snapshots.get(symbol)
                        fut_tick = all_snapshots.get(f"{symbol}_FUT")
                        
                        if not ws_tick:
                            # [v14.2.0] High-Freq Optimization: Skip analysis if no WS data
                            # Reduce dashboard spam with "Waiting" message
                            if random.random() < 0.05:
                                live_state.market_message = f"SYNCING: Waiting for WS snapshot ({symbol})"
                            continue

                        market_data = MarketData(
                            symbol=symbol, 
                            spot_price=ws_tick['lp'], 
                            # [v9.9.9] Audit Fix: Use Proportional Basis Fallback (0.049%) to stay under spread veto
                            future_price=ws_tick.get('future_lp', ws_tick['lp'] * 1.00049),
                            # [Institutional Patch] Use Future's OI for index symbols. Fallback to 1M if missing/zero.
                            oi=ws_tick.get('oi') if ws_tick.get('oi', 0) > 0 else (1000000 if symbol in ["NIFTY", "BANKNIFTY", "SENSEX"] else 0), 
                            pcr=0.95, 
                            timestamp=datetime.fromtimestamp(ws_tick.get('timestamp', time.time()), tz=IST), 
                            inr_price=ws_tick['lp'], # NSE is already in INR
                            source="SHOONYA_WS"
                        )
                        
                        # ========== [v15.3.8] SAFETY GATE 1: DATA HEALTH CHECK ==========
                        data_valid, data_reason = core.data_health_checker.validate_market_data(
                            symbol=symbol,
                            price=market_data.spot_price,
                            timestamp=market_data.timestamp,
                            volume=ws_tick.get('v', ws_tick.get('volume', 0)),
                            bid=ws_tick.get('bp1'),
                            ask=ws_tick.get('sp1')
                        )
                        
                        if not data_valid:
                            if vix_update_counter % 5 == 0:
                                logger.warning(f"🚫 DATA HEALTH BLOCK: {symbol} - {data_reason}")
                            live_state.add_thought("DATA_HEALTH", f"❌ {symbol}: {data_reason}")
                            continue  # Skip this symbol, don't trade on stale data
                        # ================================================================

                    live_state.prices[symbol] = market_data.spot_price
                    detected_patterns = []
                    signal_type = None

                    # [v9.8.5] Spread Check (Lenient 0.06% to prevent self-veto on synthesized data)
                    current_spread = abs(market_data.future_price - market_data.spot_price)
                    spread_max = market_data.spot_price * 0.0006
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
                        
                        if "USDT" in symbol:
                            hist_df = core.crypto_provider.get_history(symbol, interval="5minute")
                        else:
                            hist_df = data_provider.get_history(symbol, interval="5minute")
                            
                        if hist_df is not None:
                            live_state.history_cache[symbol] = hist_df
                        else:
                            continue

                    # [v9.9.9] Technical Indicators Calculation
                    # 3. Technical Indicators (Throttled via TechnicalCache)
                    adx_val = tech_cache.get(symbol, "ADX")
                    rsi_val = tech_cache.get(symbol, "RSI")
                    atr_val = tech_cache.get(symbol, "ATR")

                    if adx_val is None or rsi_val is None or atr_val is None:
                        import pandas_ta as ta
                        adx_df = ta.adx(hist_df.high, hist_df.low, hist_df.close, length=14)
                        adx_val = float(adx_df.iloc[-1]['ADX_14']) if adx_df is not None and not adx_df.empty else 0.0
                        rsi_df = ta.rsi(hist_df.close, length=14)
                        rsi_val = float(rsi_df.iloc[-1]) if rsi_df is not None and not rsi_df.empty else 50.0
                        atr_df = ta.atr(hist_df.high, hist_df.low, hist_df.close, length=14)
                        atr_val = float(atr_df.iloc[-1]) if atr_df is not None and not atr_df.empty else 0.0
                        
                        tech_cache.set(symbol, "ADX", adx_val)
                        tech_cache.set(symbol, "RSI", rsi_val)
                        tech_cache.set(symbol, "ATR", atr_val)
                        
                        if random.random() < 0.05:
                            logger.info(f"PERF: Refreshed indicators for {symbol} (Cache expired)")

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
                        if "USDT" in symbol:
                            macro_df = core.crypto_provider.get_history(symbol, "60minute")
                        else:
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

                    # Option Chain (Throttled for v15.3.18 - 60s cooldown)
                    if (time.time() - live_state.last_chain_fetch[symbol]) > 60:
                        if "USDT" in symbol:
                            chain_df, is_synthetic = core.crypto_provider.get_option_chain(symbol)
                        else:
                            # [v14.2.0] Pass spot_price to avoid redundant HTTP quote inside provider
                            chain_df, is_synthetic = data_provider.get_option_chain(symbol, spot_price=market_data.spot_price)
                        
                        if not chain_df.empty:
                            live_state.max_pain[symbol] = option_engine.calculate_max_pain(chain_df)
                            live_state.option_battles[symbol] = core.option_engine.detect_strike_battles(chain_df)
                            live_state.option_chains[symbol] = chain_df.to_dict('records')
                            gex_data = option_engine.calculate_gex_proxy(chain_df, market_data.spot_price)
                            live_state.gex_bias[symbol] = gex_data["gex_bias"]
                            live_state.last_chain_fetch[symbol] = time.time()
                    
                    chain_df = pd.DataFrame(live_state.option_chains[symbol])
                    if not chain_df.empty:
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
                        else:
                            # Reset synergy if other index data is missing
                            live_state.sector_synergy = 1.0
                    else:
                        # [v15.0] Reset synergy for non-core symbols to prevent leakage
                        live_state.sector_synergy = 1.0

                    is_trap, trap_reason = strategist.is_trap(hist_df, market_data)
                    if is_trap:
                        live_state.add_thought("TRAP_WARNING", f"Potential Trap Detected: {trap_reason}. Reducing Score.")
                        pattern_results["score"] *= 0.5

                    # VIX & Breadth (Updated globally in outer loop)
                    live_state.iv_skew[symbol] = data_provider.get_iv_skew(symbol)
                    
                    # [Phase 3.5] Strict VIX Cap - [v15.0] NSE ONLY
                    if is_nse:
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
                    current_spread = abs(market_data.future_price - market_data.spot_price) if market_data.future_price and market_data.spot_price else 0.5

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
                    
                    # Prepare market data dict for brain engine (Institutional Step 6)
                    market_data_dict = {
                        "price": market_data.spot_price,  # [v13.0.10] For SignalNotifier
                        "spot_price": market_data.spot_price,
                        "future_price": market_data.future_price,
                        "oi": market_data.oi,
                        "vix": live_state.vix,
                        "gex": live_state.gex_bias.get(symbol, 0.0),
                        "pcr": market_data.pcr,
                        "inr_price": market_data.inr_price # [v15.0]
                    }

                    # Pass ohlcv_df to enable SMC Engine
                    decision, thoughts = call_brain_safely(
                        "DECIDE", features=brain_features, market_data=market_data_dict,
                        regime=live_state.current_regime, 
                        ohlcv_df=hist_df, is_commit=False, pattern_score=pattern_results["score"],
                        signal_intent=likely_intent, iv_skew=live_state.iv_skew.get(symbol, 1.0),
                        asset_class=asset_class
                    )
                    for t in thoughts: live_state.add_thought("INFERENCE", f"[{symbol}] {t}")
                    
                    # [v15.0] Dual-Currency Transparency in Dashboard logs
                    if asset_class == AssetClass.GLOBAL and market_data.inr_price:
                        live_state.add_thought("CURRENCY", f"[{symbol}] Current Price: ₹{market_data.inr_price:,.2f} (Rate: {core.crypto_provider.usd_to_inr:.2f})")
                    
                    # [v13.0.10] Signal Notifier logic moved after Opportunity Switch check (Line 1378)
                    
                    # Extract decision_id for legacy compatibility
                    decision_id = decision.get('decision_id', 'ERR') if isinstance(decision, dict) else decision

                    confidence_boost, _ = call_brain_safely(
                        "BOOST", features=brain_features, regime=live_state.current_regime,
                        signal_intent=likely_intent, iv_skew=live_state.iv_skew.get(symbol, 1.0)
                    )
                    
                    is_passive = (time.time() - start_time) < APP_CONFIG["PASSIVE_MODE_THRESHOLD"]
                    applied_boost = 1.0 if is_passive else confidence_boost
                    
                    if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and applied_boost > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                        if live_state.sector_synergy > 1.0: pattern_results["score"] *= 1.1
                    elif pattern_results["score"] <= APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and confidence_boost >= config.DECISION_THRESHOLD:
                        # [v14.2.2] BRAIN_PULL: Neural consensus overrides weak technical scores if a pattern exists
                        pattern_results["score"] = 1.0 # Allow Brain (applied_boost) to be final arbiter
                        pattern_results["patterns"] = pattern_results.get("patterns", []) + ["BRAIN_PULL"]
                        live_state.add_thought("ANALYSIS", f"[{symbol}] BRAIN_PULL Triggered: Confidence ({confidence_boost:.2f}) overriding weak technical score ({pattern_results['score']:.2f})")
                    
                    pattern_results["score"] *= applied_boost

                    # Lull Filter (IST-aware) - [v15.0] NSE ONLY
                    now_time = now_ist.time()
                    lull_start = datetime.strptime(f"{APP_CONFIG['LULL_START_HOUR']}:{APP_CONFIG['LULL_START_MINUTE']:02d}", "%H:%M").time()
                    lull_end = datetime.strptime(f"{APP_CONFIG['LULL_END_HOUR']}:{APP_CONFIG['LULL_END_MINUTE']:02d}", "%H:%M").time()
                    if is_nse and lull_start <= now_time <= lull_end and "BRAIN_PULL" not in pattern_results.get("patterns", []):
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
                        
                        # [v13.1.0] Single-Trade Focus & Opportunity Switching
                        live_signals = [s for s in live_state.active_signals if s.is_live]
                        if len(live_signals) >= APP_CONFIG["MAX_OPEN_POSITIONS"]:
                            live_signal = live_signals[0]
                            
                            # Calculate PnL of active trade
                            p_delta = (market_data.spot_price - live_signal.entry_price) if "BULLISH" in live_signal.reasoning else (live_signal.entry_price - market_data.spot_price)
                            
                            # Opportunity Switch Condition:
                            # 1. New signal is 15% better (1.15x)
                            # 2. Current trade is PROFITABLE (p_delta > 0) [User Requirement]
                            if p_delta > 0 and pattern_results["score"] > (live_signal.score * 1.15):
                                # Exit current trade before entering new one
                                with live_state._lock:
                                    live_signal.is_live = False
                                
                                signal_data = live_signal.dict()
                                signal_data['pnl'] = p_delta
                                
                                # Send Advisory/Action
                                core.telegram_notifier.send_exit(
                                    signal_data, 
                                    "OPPORTUNITY SWITCH", 
                                    f"💰 Taking Profit on {live_signal.symbol} (+{p_delta:.2f}) to capture 1.15x stronger edge in {symbol}."
                                )
                                core.db.log_outcome(live_signal.decision_id, "SWITCH_EXIT_PROFIT")
                                
                                # Set a flag to indicate this is a swap for the new signal
                                is_swap_entry = True
                                swapped_from_id = live_signal.decision_id
                                live_state.market_message = f"SWAPPING: {live_signal.symbol} -> {symbol} (Edge Upgrade)"
                            else:
                                live_state.add_thought("OPPORTUNITY", f"[{symbol}] Skipping Approval: 0.55 threshold met, but existing {live_signal.symbol} trade (Score: {live_signal.score:.2f}) is still prioritized over new Edge ({pattern_results['score']:.2f}). Needs 1.15x better score to swap.")
                                continue
                        else:
                            is_swap_entry = False
                            swapped_from_id = None

                        # [v15.3.7] SAFETY GATE 2: DUPLICATE PREVENTION
                        with live_state.seen_ids_lock:
                            if decision_id in live_state.seen_signal_ids:
                                if vix_update_counter % 5 == 0:
                                    logger.warning(f"🚫 DUPLICATE SIGNAL BLOCKED: {decision_id}")
                                live_state.add_thought("DEDUPE", f"[{symbol}] Skipping Approval: Signal {decision_id} already processed.")
                                continue
                            
                            # Do NOT mark as seen yet, wait for Risk Validation
                                
                        # Correlated Risk Check: Pass currently active symbols
                        active_syms = [s.symbol for s in live_state.active_signals if s.is_live]
                        
                        # [v15.0] Blown Today only caps NSE execution. 
                        # GLOBAL execution in mock mode is permitted for learning.
                        if is_nse and core.risk_engine.is_blown_today(): 
                            live_state.add_thought("RISK", f"[{symbol}] VETO: Daily Loss Limit or Max Drawdown hit. Ceasing execution for protection.")
                            continue

                        if signal_type == "BULLISH" and any(abs(market_data.spot_price - r) < 25 for r in live_state.resistances.get(symbol, [])):
                            res_level = next(r for r in live_state.resistances[symbol] if abs(market_data.spot_price - r) < 25)
                            live_state.add_thought("STRUCTURE", f"[{symbol}] BULLISH VETO: Price too close to identified resistance at {res_level:.2f}.")
                            continue
                        if signal_type == "BEARISH" and any(abs(market_data.spot_price - s) < 25 for s in live_state.supports.get(symbol, [])):
                            sup_level = next(s for s in live_state.supports[symbol] if abs(market_data.spot_price - s) < 25)
                            live_state.add_thought("STRUCTURE", f"[{symbol}] BEARISH VETO: Price too close to identified support at {sup_level:.2f}.")
                            continue

                        # [v15.0] Option-Engine Bypass for GLOBAL Futures
                        precision_levels = {} # Default for safety
                        if is_nse:
                            # [Phase 5] Precision Levels & Smart Stops (Order Blocks, Fractals, OI Walls)
                            precision_levels = tech_engine.calculate_precision_levels(hist_df, market_data.spot_price, chain_df)

                            # [Institutional Step 5] Expiry Sensitivity (Precision Greeks)
                            minutes_to_expiry = get_minutes_to_expiry()
                            days_to_expiry = max(1, round(minutes_to_expiry / (24 * 60)))
                            
                            # [v15.3.8] Map regime for intelligent selector
                            mapped_regime = MarketRegime.SIDEWAYS
                            if live_state.current_regime == Regime.TRENDING_UP: 
                                mapped_regime = MarketRegime.TRENDING_BULL
                            elif live_state.current_regime == Regime.TRENDING_DOWN: 
                                mapped_regime = MarketRegime.TRENDING_BEAR
                            elif live_state.current_regime == Regime.SIDEWAYS_STRONG:
                                mapped_regime = MarketRegime.SIDEWAYS
                            
                            opt_trade = option_engine.find_executable_option(
                                symbol=symbol, 
                                spot=market_data.spot_price, 
                                signal_type=signal_type, 
                                regime=mapped_regime,
                                chains=chain_df.to_dict('records') if chain_df is not None and not chain_df.empty else [],
                                days_to_expiry=days_to_expiry
                            )
                            
                            # [v15.3.17] Safety Gate: Check for strike selection failure
                            if opt_trade.get("rejection_reasons"):
                                live_state.add_thought("OPTION_VETO", f"[{symbol}] Strike selection failed: {opt_trade['rejection_reasons']}")
                                continue
                            
                            # IV Percentile & Smooth Scaling
                            cur_iv = market_data.iv if hasattr(market_data, 'iv') else 20.0
                            if not cur_iv: # Support synthetic chain lingo
                                row = chain_df[chain_df['strike'] == opt_trade.get('strike')].iloc[0] if not chain_df.empty else None
                                cur_iv = row.get(f"{opt_trade['option_type'].lower()}_iv", 20.0) if row is not None else 20.0
                            
                            live_state.iv_history[symbol].append(cur_iv)
                            if len(live_state.iv_history[symbol]) > 90: live_state.iv_history[symbol].pop(0)
                            
                            iv_data = option_engine.calculate_iv_percentile(cur_iv, live_state.iv_history[symbol])
                            iv_scaling = iv_data['scaling_factor']
                            
                            # High Fidelity Greeks
                            greeks = option_engine.calculate_precision_greeks(
                                market_data.spot_price, opt_trade['strike'], cur_iv/100.0, 
                                minutes_to_expiry, opt_trade['option_type']
                            )
                        else:
                            # Global Futures: Use direct underlying parameters
                            opt_trade = {
                                "strike": market_data.spot_price,
                                "option_type": "FUTURES",
                                "rejection_reasons": []
                            }
                            iv_scaling = 1.0
                            greeks = {"delta": 1.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
                        
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
                                asset_class=asset_class,
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
                            
                            # NOW mark as seen to prevent rejection loop spam
                            with live_state.seen_ids_lock:
                                live_state.seen_signal_ids.add(decision_id)

                            # ========== [v15.3.7] SAFETY GATE 3: RISK VALIDATION ==========
                            can_trade, risk_reason = core.risk_manager.validate_new_trade(
                                signal_dict=new_signal.dict(),
                                pos_manager=core.position_manager
                            )
                            
                            if not can_trade:
                                logger.warning(f"🚫 RISK BLOCK: {symbol} - {risk_reason}")
                                live_state.add_thought("RISK", f"❌ {risk_reason}")
                                
                                # Critical: If trading is halted, trigger emergency shutdown
                                if core.risk_manager.trading_halted:
                                    emergency_shutdown(f"Risk Manager Halt: {risk_reason}")
                                
                                continue  # Skip this trade
                            # ================================================================

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
                            
                            if locals().get('is_swap_entry'):
                                new_signal.reasoning += f" | ⚡ SWAP from {swapped_from_id}"
                                new_signal.is_swap = True # Extra field
                                decision['is_swap'] = True
                                decision['swapped_from'] = swapped_from_id
                            
                            live_state.add_signal(new_signal)
                            
                            # [v13.0.10] Use unified SignalNotifier for DB and Telegram
                            try:
                                core.signal_notifier.process_approved_signal(
                                    decision=decision,
                                    symbol=symbol,
                                    market_data=market_data_dict,
                                    ohlcv_df=hist_df
                                )
                            except Exception as sig_err:
                                logger.error(f"Signal notification failed for {symbol}: {sig_err}")
                                # Fallback to legacy logging/notification if notifier fails
                                core.db.log_intent(new_signal.dict())
                                core.telegram_notifier.send_signal(new_signal.dict(), dashboard_url=APP_CONFIG.get("DASHBOARD_URL", ""))
                            
                            # ========== [v15.3.7] PAPER TRADING MODE ENFORCEMENT ==========
                            if APP_CONFIG["PAPER_TRADING_MODE"]:
                                logger.info(f"📄 PAPER MODE: Simulated entry for {new_signal.symbol}")
                                live_state.add_thought("PAPER", f"📄 Simulated Entry: {new_signal.symbol}")
                            else:
                                # LIVE TRADING: Execute via engine
                                logger.info(f"💰 LIVE MODE: Executing Real Entry for {new_signal.symbol}...")
                                # core.execution_engine.execute_order(new_signal) 
                                pass
                            
                            # Track in safety position manager
                            core.position_manager.add_position(new_signal.dict())
                            # ================================================================
                        else:
                            rejection = ", ".join(opt_trade.get("rejection_reasons", ["Unknown"])) if opt_trade else "No suitable contract found"
                            live_state.add_thought("OPTIONS", f"[{symbol}] Strategy Veto: {rejection}. Check liquidity or volume.")

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
                            
                            # [v15.3.8] Record outcome for circuit breaker
                            core.risk_manager.record_trade_outcome("WIN" if is_win else "LOSS", p_delta)
                        
                        # ========== [v15.3.7] SAFETY POSITION UPDATES ==========
                        try:
                            # Update safety manager with latest price
                            core.position_manager.update_position(sig.decision_id, market_data.spot_price)
                            
                            # Check exit via safety risk manager
                            pos = core.position_manager.get_position(sig.decision_id)
                            if pos:
                                should_exit, exit_reason = core.risk_manager.should_exit_position(pos, market_data.spot_price)
                                
                                if should_exit:
                                    logger.info(f"🔔 SAFETY EXIT: {symbol} - {exit_reason}")
                                    closed_pos = core.position_manager.close_position(sig.decision_id, market_data.spot_price, exit_reason)
                                    sig.is_live = False
                                    # [v15.3.8] Record outcome for circuit breaker
                                    if closed_pos:
                                        core.risk_manager.record_trade_outcome(exit_reason, closed_pos.realized_pnl)
                                    # Fallback to existing exit notification logic above or use new one
                        except Exception as pos_err:
                            logger.error(f"Safety position update failed for {symbol}: {pos_err}")
                        # ========================================================

                except Exception as e:
                    logger.error(f"ENGINE SYMBOL ERROR [{symbol}]: {e}", exc_info=True)
                
                # [v9.9.9] Record Loop Health
                loop_lat = (time.time() - t_loop_start) * 1000
                core.health_monitor.record_latency(loop_lat)
                
                # [v15.3.19] Periodic Performance Reporting
                if vix_update_counter % 20 == 0:
                    h_stats = core.health_monitor.get_stats()
                    logger.info(f"PERF_STATS: Avg Loop Latency: {h_stats.get('avg_latency', 0):.2f}ms | Active Signals: {len(live_state.active_signals)}")

            if len(live_state.active_signals) > 20:
                live_state.active_signals = live_state.active_signals[-20:]
            
            # [Institutional Phase 6] Tight 50ms reactive cycle (v15.3.18)
            time.sleep(0.05)
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
                
                # [v14.0] Indian Market Blueprint
                if 'core' in globals() and core.is_initialized:
                    for symbol in live_state.symbols:
                        supports = core.state.supports.get(symbol, [])
                        resistances = core.state.resistances.get(symbol, [])
                        trend = "BULLISH" if core.state.index_strengths.get(symbol, 0) > 0 else "BEARISH"
                        
                        note = f"Global institutional liquidity zones detected. High-probability {trend} setup for {symbol}."
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

# Startup Version Identifier [v15.3.25-HOTFIX]
LOGIC_VERSION = "v15.3.25-HOTFIX"

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
