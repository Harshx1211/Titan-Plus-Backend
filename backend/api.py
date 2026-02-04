# Standard lightweight imports
import os
import asyncio
import threading
import logging
import time
import pytz
import random
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Delay heavy library imports
# import pandas as pd
# import pandas_ta as ta
from pytz import timezone as pytz_timezone

# Configure logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from models import Regime, DivergenceType, TradeSignal, SignalConfidence
import uvicorn

app = FastAPI(title="The Oracle - Titan Plus Institutional")

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
        self.current_regime = Regime.UNCERTAIN
        self.integrity = DivergenceType.NONE
        self.active_signals = []
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
        
        # v8.1: Statistical Discipline
        self.resets_today = 0
        self.last_reset_time = datetime.now(timezone.utc)  # FIX: Use timezone-aware
        self.beta_history = {"OI": [], "BASIS": []}
        self.iv_skew = {"NIFTY": 1.0, "SENSEX": 1.0, "BANKNIFTY": 1.0}
        self.gex_bias = {"NIFTY": 0.0, "BANKNIFTY": 0.0, "SENSEX": 0.0}
        self.sector_synergy = 1.0 
        self.prev_oi = {"NIFTY": 0, "BANKNIFTY": 0, "SENSEX": 0}
        self.prev_spot = 0.0
        
        # [v9.4] Epistemic Transparency: Digital Stream of Consciousness
        self.thought_logs = [] # List of { "timestamp": iso, "type": "VETO|LEARN|SIGNAL", "msg": "..." }
        self.is_learning = False

    def add_thought(self, thought_type: str, msg: str):
        """[v9.5.4] Standardized thought logger with de-duplication and capping."""
        if self.thought_logs:
            last = self.thought_logs[-1]
            # De-duplicate identical messages if they occur within 30 seconds of each other
            if last['msg'] == msg:
                 return
        
        self.thought_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "type": thought_type,
            "msg": msg
        })
        
        # Keep logs lean for dashboard stability
        if len(self.thought_logs) > 40:
            self.thought_logs.pop(0)

# Config & Global Placeholders
# [v9.9.7] Essential defaults for LiveState before background thread fills it
APP_CONFIG = {
    "VIX_DEFAULT": 15.0,
    "SIGNAL_ACTIVE_CAP": 20,
    "ENGINE_POLLING_BASE_SECONDS": 1,
    "ENGINE_POLLING_JITTER_SECONDS": 1,
    "ENGINE_ERROR_SLEEP_TIME": 5,
    "MARKET_START_HOUR": 9,
    "MARKET_START_MINUTE": 0,
    "MARKET_END_HOUR": 15,
    "MARKET_END_MINUTE": 30
}
evolution_done_date = None

shadow_mode_enabled = os.getenv("SHADOW_MODE", "false").lower() == "true"
admin_token = os.getenv("ADMIN_TOKEN", "titan_admin_123") # Simple auth

# State & Monitoring
IST = pytz.timezone('Asia/Kolkata')
live_state = LiveState()

# Engines (Global placeholders initialized lazily in background thread)
sentinel = None
strategist = None
skirmisher = None
sr_engine = None
brain = None
evolver = None
pattern_engine = None
risk_engine = None
trap_hunter = None
option_engine = None
session_auditor = None
db = None
telegram_notifier = None
data_provider = None
shadow_engine = None
# Helper: Safe Brain Interface
def call_brain_safely(action: str, **kwargs):
    if brain is None:
        return None, []
    
    try:
        if action == "DECIDE":
            return brain.generate_decision(
                features=kwargs.get("features"),
                regime=kwargs.get("regime"),
                is_commit=kwargs.get("is_commit", False),
                pattern_score=kwargs.get("pattern_score", 0.0),
                signal_intent=kwargs.get("signal_intent"),
                iv_skew=kwargs.get("iv_skew", 1.0),
                grandmaster_data=kwargs.get("grandmaster_data") # [v3.0] Pass GM Data
            )
        elif action == "BOOST":
            if shadow_mode_enabled and shadow_engine:
                shadow_engine.compare_predictions(kwargs.get("features"), kwargs.get("regime"))
            
            return brain.get_confidence_boost_ml(
                features=kwargs.get("features"),
                regime_val=kwargs.get("regime").value if hasattr(kwargs.get("regime"), 'value') else kwargs.get("regime"),
                signal_intent=kwargs.get("signal_intent"),
                iv_skew=kwargs.get("iv_skew", 1.0)
            )
    except TypeError:
        # Fallback to V1 signatures
        try:
            if action == "DECIDE":
                return brain.generate_decision(
                    features=kwargs.get("features"),
                    regime=kwargs.get("regime"),
                    is_commit=kwargs.get("is_commit", False),
                    pattern_score=kwargs.get("pattern_score", 0.0)
                )
            elif action == "BOOST":
                return brain.get_confidence_boost_ml(
                    features=kwargs.get("features"),
                    regime_val=kwargs.get("regime").value if hasattr(kwargs.get("regime"), 'value') else kwargs.get("regime")
                )
        except Exception as e:
            logger.error(f"BRAIN: V1 fallback failed: {e}")
            
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

def is_market_open():
    """Check if Indian stock market is currently open (IST timezone-aware)."""
    # CRITICAL FIX: Use IST timezone for accurate market hours detection
    ist = pytz_timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Market hours: Monday-Friday, 9:00 AM - 3:30 PM IST
    # [HOTFIX] Special Budget Day Session (Feb 1st is Sunday)
    # if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
    #     return False
    
    market_start = now.replace(hour=APP_CONFIG["MARKET_START_HOUR"], minute=APP_CONFIG["MARKET_START_MINUTE"], second=0, microsecond=0)
    market_end = now.replace(hour=APP_CONFIG["MARKET_END_HOUR"], minute=APP_CONFIG["MARKET_END_MINUTE"], second=0, microsecond=0)
    
    return market_start <= now <= market_end

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
    if brain is None:
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
            "health": brain.health_check(),
            "metrics": {
                "total_decisions": brain.metrics.total_decisions,
                "approvals": brain.metrics.approvals,
                "blocks": brain.metrics.blocks,
                "avg_confidence": round(brain.metrics.avg_confidence, 3),
                "nan_rejections": brain.metrics.nan_rejections,
                "version": brain.LOGIC_VERSION
            }
        }
    }

@app.get("/state", response_model=SystemState)
async def get_state():
    return SystemState(
        regime=live_state.current_regime,
        is_in_recovery=risk_engine.is_in_recovery() if risk_engine else False,
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
        market_open=is_market_open()
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
    if db is None:
        raise HTTPException(status_code=503, detail="Database engine initializing")
    db.log_outcome(signal_id, outcome)
    return {"status": "outcome_logged"}

@app.get("/history")
async def get_history():
    """Returns the Truth Ledger (Immutable Records) from Supabase."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database engine initializing")
    return db.cloud_db.get_history()

@app.get("/accuracy")
async def get_accuracy():
    if db is None:
        raise HTTPException(status_code=503, detail="Database engine initializing")
    return db.get_accuracy_report()

@app.get("/audit")
async def get_session_audit(date: Optional[str] = None):
    """Returns the Institutional Session Audit report."""
    if session_auditor is None:
        raise HTTPException(status_code=503, detail="Session Auditor initializing")
    return session_auditor.generate_daily_report(date)

@app.post("/feedback")
async def post_feedback(signal_id: int, outcome: str, override: bool = False):
    # Logic to log feedback and retrain brain
    return {"status": "success"}

@app.post("/execute_trade")
async def execute_trade(signal_id: str, token: str = None):
    if token != admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    logger.info(f"API: Trade execution requested for Signal ID: {signal_id}")
    try:
        # In a real system, this would involve integration with a broker API
        # For now, we just log and return a success status
        live_state.add_thought("TRADE", f"Simulating trade execution for {signal_id}")
        return {"status": "trade_executed", "signal_id": signal_id}
    except Exception as e:
        logger.error(f"API: Failed to execute trade for Signal ID {signal_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute trade: {e}")

@app.post("/evolve")
async def trigger_evolution(date: Optional[str] = None, token: str = None):
    """Triggers the Overnight Learning (Evolution) process."""
    if token != admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if evolver is None:
        raise HTTPException(status_code=503, detail="Evolution engine initializing")
    
    live_state.is_learning = True
    live_state.add_thought("LEARN", f"Starting Overnight Evolutionary Audit for {date or 'today'}...")
    try:
        result = evolver.evolve_session(date)

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
    if token != admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if risk_engine is None:
        raise HTTPException(status_code=503, detail="Risk engine initializing")
    try:
        risk_engine.reset()
        live_state.active_signals = []
        live_state.market_message = "SYSTEM RESET: Lockout Cleared"
        logger.info("API: Emergency System Reset Triggered")
        live_state.add_thought("SYSTEM", "Emergency System Reset Triggered. Lockout Cleared.")
        return {"status": "system_reset_complete"}
    except Exception as e:
        logger.error(f"API: System reset failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"System reset failed: {e}")

def run_engine_loop():
    """
    The background loop that handles extreme lazy initialization AND the analysis loop.
    This ensures the API starts instantly while heavy work happens in the background.
    """
    global sentinel, strategist, skirmisher, sr_engine, brain, evolver, pattern_engine, risk_engine, trap_hunter, shadow_engine
    global option_engine, db, telegram_notifier, data_provider, session_auditor, APP_CONFIG, evolution_done_date
    
    logger.info("ENGINE: Initializing background services (Lazy Phase)...")
    
    try:
        import gc
        import random
        import pandas as pd
        import pandas_ta as ta
        
        # [v9.9.6] Restrict CPU threads to prevent scheduler kills
        try:
            import torch
            torch.set_num_threads(1)
        except: pass
        
        # Strategy & Infrastructure Imports (STAGGERED)
        from infrastructure import APP_CONFIG, SupabaseManager, DatabaseManager, TelegramNotifier
        from providers import DataProvider
        from engines import DataSentinel, RiskEngine, PatternEngine, TrapHunter, SessionAuditor
        from skirmisher_v2 import SkirmisherV2
        from brain_engine_ml import BrainEngineML
        from evolution_engine import EvolutionEngine
        from strategist import MarketStrategist
        from support_resistance import SupportResistanceEngine
        from option_engine import OptionEngine
        
        # Sequence initialization with GC to prevent peak RAM spikes
        db = DatabaseManager()
        time.sleep(1)
        telegram_notifier = TelegramNotifier()
        time.sleep(1)
        data_provider = DataProvider()
        time.sleep(1)
        
        if data_provider.use_groww:
            live_state.data_source = "GROWW_API"
            
        sentinel = DataSentinel()
        strategist = MarketStrategist()
        skirmisher = SkirmisherV2()
        sr_engine = SupportResistanceEngine()
        time.sleep(1)
        
        # Heavy ML Component 1
        brain = BrainEngineML(stage=3)
        gc.collect() 
        time.sleep(2) # Give more room for RL
        
        # Heavy ML Component 2
        evolver = EvolutionEngine(brain)
        session_auditor = SessionAuditor()
        gc.collect()
        time.sleep(1)
        
        pattern_engine = PatternEngine()
        risk_engine = RiskEngine()
        trap_hunter = TrapHunter()
        option_engine = OptionEngine()
        
        if shadow_mode_enabled:
            from shadow_mode import ShadowMode
            shadow_engine = ShadowMode()
            
        # [v9.9.8] State Recovery: Load last active prices if market is closed/fresh restart
        try:
            last_prices = db.cloud_db.get_last_known_prices()
            for sym, price in last_prices.items():
                if sym in live_state.prices:
                    live_state.prices[sym] = price
                    logger.info(f"STATE: Recovered last active price for {sym}: {price}")
        except Exception as e:
            logger.warning(f"STATE: Price recovery failed: {e}")

        logger.info("ENGINE: All strategy engines initialized. Starting analysis loop.")
        evolution_done_date = None
        
        # [AUDIT FIX] Initialize timing for passive checks
        start_time = time.time()
        
    except Exception as init_err:
        logger.error(f"ENGINE INIT ERROR: {init_err}", exc_info=True)
        return

    while True:
        try:
            # [v9.9.9] Connectivity Heartbeat
            source_info = data_provider.get_status()
            live_state.add_thought("MONITOR", f"Data Source Status: {source_info['status']} ({source_info['name']})")
            
            # Phase 0: Operational Hygiene (Market Hours & Evolution)
            now_ist = datetime.now(IST)
            current_time = now_ist.time()
            today_str = now_ist.strftime("%Y-%m-%d")
            
            market_start = datetime.strptime(f"{APP_CONFIG['MARKET_START_HOUR']}:{APP_CONFIG['MARKET_START_MINUTE']:02d}", "%H:%M").time()
            market_end = datetime.strptime(f"{APP_CONFIG['MARKET_END_HOUR']}:{APP_CONFIG['MARKET_END_MINUTE']:02d}", "%H:%M").time()
            
            # Post-Market Intelligence Trigger (3:35 PM IST)
            evolution_trigger_time = datetime.strptime("15:35", "%H:%M").time()
            
            is_market_open = market_start <= current_time <= market_end
            
            if not is_market_open:
                # 1. Dashboard Status
                live_state.market_message = f"DORMANT: Market Closed ({current_time.strftime('%H:%M')} IST)"
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
                                live_state.add_thought("LEARN", f"Session Review: {results['metrics']['win_rate']:.1f}% Win Rate analyzed.")
                        else:
                            reason = results.get("reason", "No data") if results else "Empty Response"
                            live_state.add_thought("LEARN", f"Evolution Skipped: {reason}")
                            logger.info(f"INTELLIGENCE: Evolution skipped: {reason}")
                            
                        if results and results.get("governor_status"):
                            telegram_notifier.send_alert(f"🧠 *Overnight Intelligence*: Evolution process finished for {today_str}.\nStatus: {results.get('governor_status')}")
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

            # [v9.9.9] High-Frequency Parallel Data Ticker
            all_snapshots = data_provider.get_multiple_market_snapshots(live_state.symbols)
            live_state.last_update = datetime.now(timezone.utc)
            
            for symbol in live_state.symbols:
                try:
                    # 1. Fetch Data (Priority Ticker Update)
                    detected_patterns = []
                    signal_type = None
                    market_data = all_snapshots.get(symbol)
                    
                    if market_data and market_data.spot_price > 0:
                        live_state.prices[symbol] = market_data.spot_price

                    src_status = data_provider.get_status()
                    live_state.data_source = src_status["name"]

                    if not market_data:
                        logger.warning(f"ENGINE: Snapshot missing for {symbol}. Skipping.")
                        continue

                    # [v9.8.5] Spread Check
                    current_spread = abs(market_data.future_price - market_data.spot_price)
                    spread_max = market_data.spot_price * 0.0005
                    if current_spread > spread_max:
                        if "SPREAD" not in live_state.market_message:
                            live_state.add_thought("SPREAD_VETO", f"Spread Spike: {current_spread:.2f} > {spread_max:.2f}. Vetoing.")
                            live_state.market_message = f"SPREAD VETO: {symbol} Basis Stability Alert"
                        continue

                    # 2. Triangulation (Sentinel v2)
                    live_state.integrity = sentinel.check_integrity(
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
                    hist_df = data_provider.get_history(symbol, interval="5minute")
                    if hist_df.empty:
                        continue

                    adx_df = hist_df.ta.adx()
                    if adx_df is not None and 'ADX_14' in adx_df.columns:
                        val = adx_df['ADX_14'].iloc[-1]
                        adx_val = 25.0 if pd.isna(val) or val != val else float(val)
                    else: adx_val = 25.0
                    
                    atr_df = hist_df.ta.atr()
                    atr_val = atr_df.iloc[-1] if atr_df is not None and not atr_df.empty else 0.0

                    live_state.current_regime = strategist.classify_regime(hist_df)
                    curr_strength = (market_data.spot_price - hist_df.open.iloc[0]) / hist_df.open.iloc[0] * 100
                    live_state.index_strengths[symbol] = curr_strength

                    # S/R Analysis
                    now_minute = datetime.now().minute
                    if now_minute % 5 == 0 or not live_state.supports.get(symbol):
                        try:
                            sr_levels = sr_engine.find_pivot_levels(hist_df, lookback=10)
                            s_levels = [s['level'] for s in sr_levels['supports']] or [hist_df.low.min()]
                            r_levels = [r['level'] for r in sr_levels['resistances']] or [hist_df.high.max()]
                            live_state.supports[symbol] = s_levels
                            live_state.resistances[symbol] = r_levels
                        except Exception as e:
                            logger.warning(f"S/R Calc Failed for {symbol}: {e}")

                    # Macro Context
                    macro_df = data_provider.get_history(symbol, interval="60minute")
                    macro_bias = strategist.get_macro_bias(macro_df)
                    macro_zones = pattern_engine.detect_macro_zones(macro_df)
                    
                    # Pattern Recognition
                    pattern_results = pattern_engine.get_signal_confirmation(
                        hist_df, macro_bias=macro_bias, macro_zones=macro_zones, atr=atr_val
                    )
                    live_state.add_thought("ANALYSIS", f"Chart Pattern Score: {pattern_results['score']:.2f}. Found: {', '.join(pattern_results.get('patterns', ['NONE']))}")

                    # Option Chain
                    chain_df, is_synthetic = data_provider.get_option_chain(symbol)
                    if not chain_df.empty:
                        live_state.max_pain[symbol] = option_engine.calculate_max_pain(chain_df)
                        live_state.option_battles[symbol] = option_engine.detect_strike_battles(chain_df)
                        live_state.option_chains[symbol] = chain_df.to_dict('records')
                        gex_data = option_engine.calculate_gex(chain_df, market_data.spot_price)
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
                            my_delta = (market_data.spot_price - market_data.future_price + 45)
                            other_delta = (other_data.spot_price - other_data.future_price + 45)
                            is_aligned = (my_delta > 0 and other_delta > 0) or (my_delta < 0 and other_delta < 0)
                            live_state.sector_synergy = 1.3 if is_aligned else 0.4
                            if not is_aligned: pattern_results["score"] *= 0.6

                    is_trap, trap_reason = strategist.is_trap(hist_df, market_data)
                    if is_trap:
                        live_state.add_thought("TRAP_WARNING", f"Potential Trap Detected: {trap_reason}. Reducing Score.")
                        pattern_results["score"] *= 0.5

                    # VIX & Breadth
                    live_state.vix = data_provider.get_vix()
                    live_state.iv_skew[symbol] = data_provider.get_iv_skew(symbol)
                    if live_state.vix > APP_CONFIG.get("HIGH_VOLATILITY_VIX", 20.0):
                        pattern_results["score"] *= 0.8
                    live_state.breadth = data_provider.get_breadth(symbol)
                    
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
                        "SPOT_PRICE": market_data.spot_price, "FUTURE_PRICE": market_data.future_price,
                        "MACRO_BIAS": macro_bias, "symbol": symbol
                    }

                    # 5. Brain Inference
                    grandmaster_data = {}
                    if brain and not hist_df.empty and not chain_df.empty:
                        macro_snap = {"VIX": live_state.vix, "DXY": 103.5, "FII_NET": 0.0, "CRUDE": 75.0, "USDINR": 84.0}
                        grandmaster_data = brain.analyze_institutional_logic(hist_df, chain_df, macro_snap)

                    likely_intent = "BULLISH" if (pattern_results.get("score", 0) > 0.45 and curr_strength > 0.1) or price_vel_curr > 0.08 else (
                        "BEARISH" if (pattern_results.get("score", 0) > 0.45 and curr_strength < -0.1) or price_vel_curr < -0.08 else "BULLISH"
                    )
                    
                    decision_id, thoughts = call_brain_safely(
                        "DECIDE", features=brain_features, regime=live_state.current_regime, 
                        grandmaster_data=grandmaster_data, is_commit=False, pattern_score=pattern_results["score"],
                        signal_intent=likely_intent, iv_skew=live_state.iv_skew.get(symbol, 1.0)
                    )
                    for t in thoughts: live_state.add_thought("INFERENCE", t)

                    confidence_boost, _ = call_brain_safely(
                        "BOOST", features=brain_features, regime=live_state.current_regime,
                        signal_intent=likely_intent, iv_skew=live_state.iv_skew.get(symbol, 1.0)
                    )
                    
                    is_passive = (time.time() - start_time) < APP_CONFIG["PASSIVE_MODE_THRESHOLD"]
                    applied_boost = 1.0 if is_passive else confidence_boost
                    
                    if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and applied_boost > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                        if live_state.sector_synergy > 1.0: pattern_results["score"] *= 1.1
                    elif pattern_results["score"] <= APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and confidence_boost > 0.50:
                        pattern_results["score"] = 0.95 
                        pattern_results["patterns"] = pattern_results.get("patterns", []) + ["BRAIN_PULL"]
                    
                    pattern_results["score"] *= applied_boost

                    # Lull Filter
                    now_time = datetime.now().time()
                    lull_start = datetime.strptime(f"{APP_CONFIG['LULL_START_HOUR']}:{APP_CONFIG['LULL_START_MINUTE']:02d}", "%H:%M").time()
                    lull_end = datetime.strptime(f"{APP_CONFIG['LULL_END_HOUR']}:{APP_CONFIG['LULL_END_MINUTE']:02d}", "%H:%M").time()
                    if lull_start <= now_time <= lull_end and "BRAIN_PULL" not in pattern_results.get("patterns", []):
                        pattern_results["score"] *= 0.5

                    # 6. Signal Execution
                    if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                        detected_patterns = pattern_results.get("patterns", [])
                        signal_type = likely_intent if "BRAIN_PULL" in detected_patterns else (
                            "BULLISH" if any(p in ["VWAP_CROSSOVER", "HAMMER", "BULLISH_ENGULFING", "CPR_BREAKOUT"] for p in detected_patterns) else "BEARISH"
                        )
                        
                        live_signal = next((s for s in live_state.active_signals if s.is_live), None)
                        is_takeover = False
                        if live_signal:
                            if pattern_results["score"] > (live_signal.score * 1.15): is_takeover = True
                            else: continue

                        if risk_engine.is_blown_today(): continue
                        
                        if is_takeover and live_signal:
                            live_signal.is_live = False
                            db.log_outcome(live_signal.decision_id, "SWAP_EXIT")
                            telegram_notifier.send_alert(f"🔄 SWAP: Closing {live_signal.symbol} for better setup in {symbol}.")

                        if signal_type == "BULLISH" and any(abs(market_data.spot_price - r) < 25 for r in live_state.resistances.get(symbol, [])): continue
                        if signal_type == "BEARISH" and any(abs(market_data.spot_price - s) < 25 for s in live_state.supports.get(symbol, [])): continue

                        opt_trade = option_engine.find_executable_option(
                            symbol, market_data.spot_price, signal_type, macro_zones=macro_zones,
                            is_momentum_dominant=strategist.is_momentum_dominant(hist_df), days_to_expiry=5, 
                            chain_df=chain_df, is_synthetic=is_synthetic
                        )
                        
                        if not opt_trade.get("rejection_reasons"):
                            new_signal = TradeSignal(
                                symbol=symbol, entry_price=market_data.spot_price,
                                stop_loss=max(APP_CONFIG["SIGNAL_STOP_LOSS_POINTS"], round(1.0 * atr_val)), 
                                target=max(APP_CONFIG["SIGNAL_TARGET_POINTS"], round(1.5 * atr_val)),
                                confidence=SignalConfidence.HIGH if pattern_results["score"] > 0.9 else SignalConfidence.MEDIUM,
                                regime=live_state.current_regime, reasoning=f"{signal_type} | {', '.join(detected_patterns)}",
                                timestamp=datetime.now(timezone.utc), decision_id=decision_id,
                                logic_version="v9.9.9_HF", spread_at_entry=current_spread,
                                quantity=risk_engine.get_suggested_size(applied_boost, APP_CONFIG.get("BASE_LOTS", 1)),
                                score=pattern_results["score"], **opt_trade
                            )
                            live_state.active_signals.append(new_signal)
                            telegram_notifier.send_signal(new_signal.dict(), dashboard_url=APP_CONFIG.get("DASHBOARD_URL", ""))

                    # 7. Management
                    for sig in live_state.active_signals:
                        if not sig.is_live or sig.symbol != symbol: continue
                        
                        p_delta = (market_data.spot_price - sig.entry_price) if "BULLISH" in sig.reasoning else (sig.entry_price - market_data.spot_price)
                        p_adv = (sig.entry_price - market_data.spot_price) if "BULLISH" in sig.reasoning else (market_data.spot_price - sig.entry_price)
                        
                        if p_delta > sig.mfe:
                            sig.mfe = p_delta
                            sig.time_to_mfe = (datetime.now(timezone.utc) - sig.timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                        if p_adv > sig.mae: sig.mae = p_adv
                        
                        if not sig.is_tsl_active and p_delta >= (0.5 * sig.target):
                            sig.is_tsl_active = True
                            sig.stop_loss = 0.0
                            telegram_notifier.send_alert(f"🛡️ TSL: {sig.symbol} at Break-Even.")

                        is_target, is_sl = p_delta >= sig.target, p_adv >= (sig.stop_loss if not sig.is_tsl_active else 0.0)
                        if is_target or is_sl:
                            sig.is_live = False
                            is_win = p_delta > 0
                            brain.log_snapshot(sig.decision_id, outcome=is_win, performance={"mfe": sig.mfe, "mae": sig.mae}, freeze_authority=is_passive)
                            db.log_outcome(sig.decision_id, "WIN" if is_win else "LOSS")
                            telegram_notifier.send_alert(f"{'✅' if is_win else '❌'} EXIT: {sig.symbol} | PnL: {p_delta:.1f}")

                except Exception as e:
                    logger.error(f"ENGINE SYMBOL ERROR [{symbol}]: {e}", exc_info=True)

            if len(live_state.active_signals) > 20:
                live_state.active_signals = live_state.active_signals[-20:]
            
            time.sleep(APP_CONFIG["ENGINE_POLLING_BASE_SECONDS"] + random.uniform(0, APP_CONFIG["ENGINE_POLLING_JITTER_SECONDS"]))
        except Exception as e:
            logger.error(f"ENGINE CRITICAL: {e}", exc_info=True)
            time.sleep(10)

@app.on_event("startup")
async def startup_event():
    logger.info("API: Launching background initialization thread...")
    # Immediately spawn background thread and return
    # This ensures the API binds to its port in milliseconds
    thread = threading.Thread(target=run_engine_loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    logger.info(f"API: Initializing server on port {port}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.critical(f"API CRITICAL ERROR: {e}", exc_info=True)
