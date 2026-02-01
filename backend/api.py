from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple
import uvicorn
from config import APP_CONFIG
import pandas as pd
import logging
import time
from datetime import datetime, timezone
import pandas_ta as ta
from models import TradeSignal, Regime, SignalConfidence, DivergenceType
from sentinel import DataSentinel
from strategist import MarketStrategist
from risk_engine import RiskEngine
from brain_engine import BrainEngine
from evolution_engine import EvolutionEngine
from pattern_engine import PatternEngine
from option_engine import OptionEngine
from session_auditor import SessionAuditor
from data_provider import DataProvider
from trap_hunter import TrapHunter
from skirmisher_v2 import SkirmisherV2
from telegram_notifier import TelegramNotifier
from database import DatabaseManager
from support_resistance import SupportResistanceEngine
import asyncio
import threading
import os
from pytz import timezone as pytz_timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# [v9.5] Silence verbose third-party logs to keep Render console clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("postgrest").setLevel(logging.WARNING)

app = FastAPI(title="The Oracle - Titan Plus Institutional")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        self.symbols = ["NIFTY", "SENSEX"]
        self.current_symbol_idx = 0
        self.vix = APP_CONFIG["VIX_DEFAULT"]
        self.breadth = {"advances": 0, "declines": 0}
        self.market_message = "System Stable"
        self.data_source = "PUBLIC_SCRAPER"
        self.index_strengths: Dict[str, float] = {"NIFTY": 0.0, "SENSEX": 0.0}
        
        # Partitioned Symbol Data (v8.1 Multi-Asset)
        self.prices = {"NIFTY": 25000.0, "SENSEX": 81500.0}
        self.max_pain = {"NIFTY": 0.0, "SENSEX": 0.0}
        self.option_battles = {"NIFTY": [], "SENSEX": []}

        self.option_chains = {"NIFTY": [], "SENSEX": []}
        self.supports = {"NIFTY": [], "SENSEX": []}
        self.resistances = {"NIFTY": [], "SENSEX": []}
        
        # v8.1: Statistical Discipline
        self.resets_today = 0
        self.last_reset_time = datetime.now()
        self.beta_history = {"OI": [], "BASIS": []}
        self.iv_skew = {"NIFTY": 1.0, "SENSEX": 1.0, "BANKNIFTY": 1.0}
        self.gex_bias = {"NIFTY": 0.0, "SENSEX": 0.0}
        self.sector_synergy = 1.0 
        self.prev_oi = {"NIFTY": 0, "SENSEX": 0}
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

live_state = LiveState()
session_auditor = SessionAuditor()

# Engines
# Global Strategy Components
sentinel = DataSentinel()
strategist = MarketStrategist()
skirmisher = SkirmisherV2()
sr_engine = SupportResistanceEngine()
brain = BrainEngine(stage=3) # Stage 3: Full Filter Mode
pattern_engine = PatternEngine()
risk_engine = RiskEngine()
trap_hunter = TrapHunter() # [v9.1] Sidecar Module
# Helper: Safe Brain Interface (Phase 28 Compatibility)
def call_brain_safely(action: str, **kwargs):
    """
    Wrapper to handle v1 vs v2 signature differences.
    v2 requires signal_intent, iv_skew, etc.
    """
    try:
        if action == "DECIDE":
            return brain.generate_decision(
                features=kwargs.get("features"),
                regime=kwargs.get("regime"),
                is_commit=kwargs.get("is_commit", False),
                pattern_score=kwargs.get("pattern_score", 0.0),
                signal_intent=kwargs.get("signal_intent"),
                iv_skew=kwargs.get("iv_skew", 1.0)
            )
        elif action == "BOOST":
            return brain.get_confidence_boost(
                features=kwargs.get("features"),
                regime_val=kwargs.get("regime").value if hasattr(kwargs.get("regime"), 'value') else kwargs.get("regime"),
                signal_intent=kwargs.get("signal_intent"),
                iv_skew=kwargs.get("iv_skew", 1.0)
            )
    except TypeError as e:
        logger.warning(f"BRAIN: V2 call failed, falling back to v1 signature: {e}")
        if action == "DECIDE":
            return brain.generate_decision(
                features=kwargs.get("features"),
                regime=kwargs.get("regime"),
                is_commit=kwargs.get("is_commit", False),
                pattern_score=kwargs.get("pattern_score", 0.0)
            )
        elif action == "BOOST":
            return brain.get_confidence_boost(
                features=kwargs.get("features"),
                regime_val=kwargs.get("regime").value if hasattr(kwargs.get("regime"), 'value') else kwargs.get("regime")
            )
    return None, []

# evolution_engine = EvolutionEngine(brain)  # Initialized later if needed
evolution_engine = EvolutionEngine(brain)
option_engine = OptionEngine()
db = DatabaseManager()
telegram_notifier = TelegramNotifier()
data_provider = DataProvider()

if data_provider.use_groww:
    live_state.data_source = "GROWW_API"

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
    
    # Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST
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
    market_open = is_market_open()
    
    # When market is closed, return "-" for all metrics except closing prices
    if not market_open:
        return SystemState(
            regime=Regime.UNCERTAIN,
            is_in_recovery=False,
            data_latency=0.0,
            integrity_status=DivergenceType.NONE,
            active_signals=[],
            last_update=live_state.last_update,
            vix=0.0,  
            breadth={"advances": 0, "declines": 0},
            market_message="MARKET_CLOSED",
            data_source=live_state.data_source,
            prices=live_state.prices, 
            max_pain={"NIFTY": 0.0, "SENSEX": 0.0},
            option_battles={"NIFTY": [], "SENSEX": []},
            option_chains={"NIFTY": [], "SENSEX": []},
            iv_skew={"NIFTY": 0.0, "SENSEX": 0.0, "BANKNIFTY": 0.0},
            resets_today=0,
            gex_bias={"NIFTY": 0.0, "SENSEX": 0.0},
            sector_synergy=0.0,
            thought_logs=[],
            is_learning=False,
            market_open=False,
            supports={"NIFTY": [], "SENSEX": []},
            resistances={"NIFTY": [], "SENSEX": []}
        )
    
    # Market is open - return live data
    return SystemState(
        regime=live_state.current_regime,
        is_in_recovery=risk_engine.is_in_recovery(),
        data_latency=(datetime.now(timezone.utc) - live_state.last_update).total_seconds() * 1000,
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
        thought_logs=live_state.thought_logs[-10:], # Last 10 thoughts
        is_learning=live_state.is_learning,
        market_open=True
    )

@app.post("/signals/intent")
async def post_intent(signal: TradeSignal, patterns: List[str] = []):
    """Logs a new signal intent into the Truth Ledger."""
    db.log_intent(signal, patterns)
    return {"status": "intent_logged"}

@app.post("/signals/outcome")
async def post_outcome(signal_id: str, outcome: str):
    """Appends an outcome to an existing signal intent."""
    db.log_outcome(signal_id, outcome)
    return {"status": "outcome_logged"}

@app.get("/history")
async def get_history():
    """Returns the Truth Ledger (Immutable Records) from Supabase."""
    return db.cloud_db.get_history()

@app.get("/accuracy")
async def get_accuracy():
    return db.get_accuracy_report()

@app.get("/audit")
async def get_session_audit(date: Optional[str] = None):
    """Returns the Institutional Session Audit report."""
    return session_auditor.generate_daily_report(date)

@app.post("/feedback")
async def post_feedback(signal_id: int, outcome: str, override: bool = False):
    # Logic to log feedback and retrain brain
    return {"status": "success"}

@app.post("/execute_trade")
async def execute_trade(signal_id: str):
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
async def trigger_evolution(date: Optional[str] = None):
    """Triggers the Overnight Learning (Evolution) process."""
    live_state.is_learning = True
    live_state.add_thought("LEARN", f"Starting Overnight Evolutionary Audit for {date or 'today'}...")
    try:
        result = evolution_engine.evolve_session(date)

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
async def reset_system():
    """Emergency Reset: Clears recovery mode and active signals."""
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
    The background loop that fetches data and runs the Titan Plus logic.
    """
    logger = logging.getLogger("api_engine")
    logger.info("ENGINE: Starting background loop...")
    start_time = time.time() # Guardrail #1: Initialized once
    
    while True:
        try:
            # Rotate through symbols
            symbol = live_state.symbols[live_state.current_symbol_idx]
            live_state.current_symbol_idx = (live_state.current_symbol_idx + 1) % len(live_state.symbols)
            
            # [v9.8] Latency Pulse: Update timestamp per symbol to keep dashboard alive
            live_state.last_update = datetime.now(timezone.utc)

            # 1. Fetch Data (Priority Ticker Update)
            detected_patterns = []
            signal_type = None
            try:
                # Use a very short timeout for ticker updates
                market_data = data_provider.get_market_snapshot(symbol)
                
                # Update specific price tracking
                if market_data.spot_price > 0:
                    live_state.prices[symbol] = market_data.spot_price

                # [v9.5.6] Dynamic Data Source Status for Dashboard
                src_status = data_provider.get_status()
                if src_status["status"] == "COOLDOWN":
                    live_state.data_source = f"GROWW (COOLDOWN: {src_status['remaining']}s)"
                    if "COOLDOWN" not in live_state.market_message:
                        live_state.add_thought("DATA", "Groww in Cooldown. Using Scraper Fallback.")
                else:
                    live_state.data_source = src_status["name"]
            except Exception as e:
                logger.warning(f"ENGINE: Snapshot fetch failed for {symbol}: {e}", exc_info=True)
                live_state.add_thought("DATA_ERROR", f"Snapshot failed for {symbol}. Source issues?")
                continue
                # Use hardcoded fallback to keep ticker alive even if everything fails
                if symbol == "NIFTY" and live_state.prices["NIFTY"] == 0: live_state.prices["NIFTY"] = 24500.0
                if symbol == "SENSEX" and live_state.prices["SENSEX"] == 0: live_state.prices["SENSEX"] = 81500.0
                market_data = None

            if not market_data:
                time.sleep(2)
                continue

            # 2. Triangulation (Sentinel v2 with VIX Adaptivity)
            live_state.integrity = sentinel.check_integrity(
                market_data.spot_price, 
                market_data.future_price,
                vix=live_state.vix
            )

            # Phase 25/26/27/28: Spot-Futures Basis Stability Validation (Unified)
            basis = abs(market_data.future_price - market_data.spot_price) / market_data.spot_price * 100
            
            # Brain now owns the Epistemic State
            basis_gate = brain.check_basis_stability(basis)
            is_basis_unstable = basis_gate["is_unstable"]
            
            if is_basis_unstable:
                live_state.market_message = f"BASIS META-VETO: {basis_gate['reason']} ({basis_gate.get('sigma_jump', 0):.1f}σ)"
            
            # 3. Regime Detection (Strategist)
            try:
                # Execute Timeframe (5m)
                hist_df = data_provider.get_history(symbol, interval="5minute")
                
                # Phase 26: Cache Indicators once per loop (v9.5.5: Added guards)
                adx_df = hist_df.ta.adx()
                if adx_df is not None and 'ADX_14' in adx_df.columns:
                    val = adx_df['ADX_14'].iloc[-1]
                    # Paranoid NaN check: pd.isna OR value inequality (standard float nan behavior)
                    if pd.isna(val) or val != val:
                        adx_val = 25.0
                    else:
                        adx_val = float(val)
                else:
                    adx_val = 25.0
                atr_df = hist_df.ta.atr()
                atr_val = atr_df.iloc[-1] if atr_df is not None and not atr_df.empty else 0.0

                live_state.current_regime = strategist.classify_regime(hist_df)
                
                # Calculate simple strength
                curr_strength = (market_data.spot_price - hist_df.open.iloc[0]) / hist_df.open.iloc[0] * 100
                live_state.index_strengths[symbol] = curr_strength

                # [v9.9.5] Support & Resistance Analysis (Every 5 mins or on first run)
                now_minute = datetime.now().minute
                if now_minute % 5 == 0 or not live_state.supports.get(symbol):
                    try:
                        sr_levels = sr_engine.find_pivot_levels(hist_df, lookback=10)
                        
                        # Extract levels
                        s_levels = [s['level'] for s in sr_levels['supports']]
                        r_levels = [r['level'] for r in sr_levels['resistances']]
                        
                        # [Fallback] If no pivots found (Cold Start), use Period High/Low
                        if not s_levels and not hist_df.empty:
                            s_levels = [hist_df.low.min()]
                        if not r_levels and not hist_df.empty:
                            r_levels = [hist_df.high.max()]
                            
                        live_state.supports[symbol] = s_levels
                        live_state.resistances[symbol] = r_levels
                    except Exception as e:
                        logger.warning(f"S/R Calc Failed for {symbol}: {e}")

                # Macro Timeframe Alignment (1h)
                macro_df = data_provider.get_history(symbol, interval="60minute")
                macro_bias = strategist.get_macro_bias(macro_df)
                
                # Phase 13: Macro S/R Zones (Big Charts)
                macro_zones = pattern_engine.detect_macro_zones(macro_df)
                
                # 4. Pattern Recognition (Now with MTF Boost, Advanced Patterns, and Macro Zones)
                pattern_results = pattern_engine.get_signal_confirmation(
                    hist_df, 
                    macro_bias=macro_bias, 
                    macro_zones=macro_zones
                )
            except Exception as e:
                logger.warning(f"ENGINE: Analysis failed for {symbol}: {e}", exc_info=True)
                live_state.add_thought("ANALYZE_ERROR", f"Feature analysis crashed for {symbol}. NaN?")
                continue

            if not pattern_results["patterns"]:
                # [v9.7] Visibility: Log that we searched but found nothing
                if now_minute % 5 == 0:
                    live_state.add_thought("SEARCH", f"Scanning {symbol}... No patterns found.")
                pattern_results = {"score": 0.0, "patterns": []}
                macro_bias = 0
                macro_zones = []
            
            # Phase 14: Option Chain X-Ray (Partitioned)
            try:
                # Phase 27: Handling (df, synthetic) return
                chain_df, is_synthetic = data_provider.get_option_chain(symbol)
                if not chain_df.empty:
                    sym_max_pain = option_engine.calculate_max_pain(chain_df)
                    live_state.max_pain[symbol] = sym_max_pain
                    live_state.option_battles[symbol] = option_engine.detect_strike_battles(chain_df)
                    live_state.option_chains[symbol] = chain_df.to_dict('records')
                    
                    # Phase 30: Gamma Exposure (GEX) Tracking
                    gex_data = option_engine.calculate_gex(chain_df, market_data.spot_price)
                    live_state.gex_bias[symbol] = gex_data["gex_bias"]
                    
                    # Confluence: Max Pain + GEX Bias
                    sym_max_pain = live_state.max_pain[symbol]
                    if abs(market_data.spot_price - sym_max_pain) < APP_CONFIG["MAX_PAIN_THRESHOLD"]:
                        pattern_results["score"] *= 1.2
                        live_state.market_message = f"GEX/PAIN CONFLUENCE [{symbol}]: Institutional Gravity"
            except Exception as e:
                logger.warning(f"ENGINE: Option chain failed for {symbol}: {e}", exc_info=True)
                live_state.add_thought("CHAIN_ERROR", f"Option chain fetch failed for {symbol}.")
                continue
                chain_df, is_synthetic = pd.DataFrame(), True

            # Phase 11/30: Inter-Market Synergy (BankNifty vs Nifty)
            try:
                if symbol in ["NIFTY", "BANKNIFTY"]:
                    other_sym = "BANKNIFTY" if symbol == "NIFTY" else "NIFTY"
                    other_data = data_provider.get_market_snapshot(other_sym)
                    
                    # Simplified Sector Synergy Score
                    # If both are up/down together, synergy = High
                    # If diverging, synergy = Veto
                    my_delta = (market_data.spot_price - market_data.future_price + 45) # Proxy to daily delta
                    other_delta = (other_data.spot_price - other_data.future_price + 45)
                    
                    is_aligned = (my_delta > 0 and other_delta > 0) or (my_delta < 0 and other_delta < 0)
                    live_state.sector_synergy = 1.3 if is_aligned else 0.4
                    
                    if not is_aligned:
                        pattern_results["score"] *= 0.6
                        live_state.market_message = f"SECTOR DIVERGENCE: {symbol} vs {other_sym} Conflict"
            except Exception:
                pass

            # Phase 9/27/28: VIX & IV Skew Tracking (Unified)
            try:
                live_state.vix = data_provider.get_vix()
                live_state.iv_skew[symbol] = data_provider.get_iv_skew(symbol)
                
                # Note: Directional IV Veto relocated to post-pattern generation 
                # to ensure signal_intent awareness (Meta-Awareness v8.6.0)
                
                if live_state.vix > APP_CONFIG["HIGH_VOLATILITY_VIX"]:
                    pattern_results["score"] *= 0.8 # Tighten requirements in high volatility
                    live_state.market_message = "VIX HIGH: Use Defensive Guardrails"
                else:
                    live_state.market_message = "Volatility Normal"
            except Exception:
                pass

            # Phase 9: Market Breadth
            live_state.breadth = data_provider.get_breadth(symbol)
            adv, dec = live_state.breadth["advances"], live_state.breadth["declines"]
            
            # v8: Regime Veto (Fix Audit v8 Failure #6)
            live_state.current_regime = strategist.classify_regime(hist_df, breadth=live_state.breadth)
            
            # Phase 9: Time-Based Institutional Filter
            now_time = datetime.now().time()
            lull_start = datetime.strptime(f"{APP_CONFIG['LULL_START_HOUR']}:{APP_CONFIG['LULL_START_MINUTE']:02d}", "%H:%M").time()
            lull_end = datetime.strptime(f"{APP_CONFIG['LULL_END_HOUR']}:{APP_CONFIG['LULL_END_MINUTE']:02d}", "%H:%M").time()
            is_lull = lull_start <= now_time <= lull_end
            if is_lull:
                pattern_results["score"] *= 0.5
                live_state.market_message = "INSTITUTIONAL LULL: Low Confidence Zone"

            # v8.1: Orthogonal Feature Engineering (Fix Audit v8.1 #1)
            try:
                # 1. Price Velocity & Variance Gate
                price_velocities = hist_df.close.pct_change(5).dropna() * 100
                price_var = price_velocities.var()
                price_vel_curr = price_velocities.iloc[-1] if not price_velocities.empty else 0.0
                
                # 2. Institutional Beta Calculation (Phase 27: Raw-Feature Basis)
                # Formula: Beta = Cov(Raw_X, Raw_Y) / Var(Y)
                if price_var > 1e-4:
                    # OI Beta (Now using Raw OI history)
                    # FIX: List slicing on deque/list before pd.Series conversion
                    oi_raw_list = list(brain.raw_history.get("OI_RAW", []))
                    oi_raw_pool = pd.Series(oi_raw_list[-20:])
                    
                    if len(oi_raw_pool) == len(price_velocities.iloc[-len(oi_raw_pool):]):
                        oi_beta = oi_raw_pool.cov(price_velocities.iloc[-len(oi_raw_pool):]) / price_var
                        oi_beta = max(-1.5, min(1.5, oi_beta))
                    else: oi_beta = 0.2
                    
                    # Basis Beta (Now using Raw Basis history)
                    basis_raw_list = list(brain.raw_history.get("BASIS_RAW", []))
                    basis_raw_pool = pd.Series(basis_raw_list[-20:])
                    
                    if len(basis_raw_pool) == len(price_velocities.iloc[-len(basis_raw_pool):]):
                        basis_beta = basis_raw_pool.cov(price_velocities.iloc[-len(basis_raw_pool):]) / price_var
                        basis_beta = max(-2.0, min(2.0, basis_beta))
                    else: basis_beta = 0.5
                else:
                    oi_beta = 0.0
                    basis_beta = 0.0
                
                # 3. Residual Generation & Raw Sync
                last_oi = live_state.prev_oi.get(symbol, market_data.oi)
                oi_change = ((market_data.oi - last_oi) / last_oi * 100) if last_oi > 0 else 0.0
                raw_basis = abs(market_data.future_price - market_data.spot_price) / market_data.spot_price * 100
                
                # Phase 27 Fix: Update Brain Raw History BEFORE residualizing
                brain.update_raw_history({
                    "OI_RAW": oi_change,
                    "BASIS_RAW": raw_basis,
                    "PCR_RAW": market_data.pcr,
                    "ADX_RAW": adx_val
                })
                
                oi_res = oi_change - (oi_beta * price_vel_curr)
                basis_res = raw_basis - (basis_beta * price_vel_curr)
                
                live_state.prev_oi[symbol] = market_data.oi
                live_state.prev_spot = market_data.spot_price

                brain_features = {
                    "OI_RES": oi_res,
                    "PCR": market_data.pcr,
                    "BASIS_RES": basis_res,
                    "ADX": adx_val
                }
                
            except Exception as e:
                logger.error(f"FEATURE ERROR: {e}", exc_info=True)
                brain_features = {"OI_RES": 0, "PCR": 1.0, "BASIS_RES": 0, "ADX": 25.0}
            
            # v8.1: Stateless Inference (Phase 28: Now Signal-Aware)
            # [C8 Fix] Calculate intent BEFORE first usage
            # Fix UnboundLocalError: Ensure likely_intent is always defined
            likely_intent = "BULLISH" if pattern_results and pattern_results.get("score", 0) > 0.6 and curr_strength > 0 else (
                "BEARISH" if pattern_results and pattern_results.get("score", 0) > 0.6 else None
            )

            decision_id, thoughts = call_brain_safely(
                "DECIDE",
                features=brain_features, 
                regime=live_state.current_regime, 
                is_commit=False,
                pattern_score=pattern_results["score"],
                signal_intent=likely_intent,
                iv_skew=live_state.iv_skew.get(symbol, 1.0)
            )
            
            # v9.5.4: Use standardized de-duped logger
            for t in thoughts:
                live_state.add_thought("INFERENCE", t)

            # v8.1: Shape-Shifting Sentinel (Fix Audit v8.1 #2)
            # Monitor Mean, Std, and Kurtosis. Rate-limited to 1 reset/session.
            if len(brain.feature_history.get("OI_RES", [])) > 100 and live_state.resets_today < 1:
                hist = pd.Series(brain.feature_history["OI_RES"])
                recent = hist.iloc[-20:]
                
                # Drift Check (Mean and Kurtosis)
                mean_drift = abs(recent.mean() - hist.mean()) > 3.0
                kurt_drift = abs(recent.kurt() - hist.kurt()) > 5.0
                
                if mean_drift or kurt_drift:
                    brain.feature_history["OI_RES"] = [] 
                    live_state.resets_today += 1
                    logger.warning("BRAIN: SHAPE DRIFT DETECTED. Soft reset triggered.")

            # Calculate Brain Boost (Phase 28: Using Safe Wrapper)
            confidence_boost, boost_thoughts = call_brain_safely(
                "BOOST",
                features=brain_features, 
                regime=live_state.current_regime,
                signal_intent=likely_intent,
                iv_skew=live_state.iv_skew.get(symbol, 1.0)
            )
            
            for t in boost_thoughts:
                # Avoid duplicates from generate_decision
                if t not in thoughts:
                    live_state.add_thought("VETO" if "VETO" in t else "ANALYSIS", t)
            
            # v8.5/8.6 Epistemic Overhaul: Unified IV logic in BrainEngine.
            
            # Timing Guardrails (Calibration/Stabilization)
            now_ts = time.time()
            elapsed = now_ts - start_time
            is_passive = elapsed < APP_CONFIG["PASSIVE_MODE_THRESHOLD"]
            
            applied_boost = 1.0 if is_passive else confidence_boost
            
            # v8: Momentum Dominance Check (Fix Audit v8 Failure #5)
            # If momentum is dominant, we ignore Max Pain in patterns.
            is_dominant = strategist.is_momentum_dominant(hist_df)
            if is_dominant:
                live_state.market_message = "MOMENTUM DOMINANT: Ignoring Mean Reversion"

            # THE v8 DOUBLE-HANDSHAKE
            if not is_passive:
                if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"] and applied_boost > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                    # Phase 30: Synergy Boost
                    if live_state.sector_synergy > 1.0:
                        pattern_results["score"] *= 1.1 # Synergy boost
                    live_state.market_message = "SYNERGY CONFIRMATION: Dual Edge Active"
                elif pattern_results["score"] < APP_CONFIG["PATTERN_SCORE_THRESHOLD_MEDIUM"] and applied_boost > 0.50:
                    # [v9.8] Brain Override: Pure Statistical Entry
                    # If chart is quiet but Brain screams "GO", we execute.
                    live_state.market_message = f"BRAIN FORCE: Statistical Alpha ({applied_boost:.2f})"
                    pattern_results["score"] = 0.95 # Force approval
                    pattern_results["patterns"] = pattern_results.get("patterns", []) + ["BRAIN_PULL"]
                
            pattern_results["score"] *= applied_boost

            # 5. Update Active Signals (Performance Tracking)
            for sig in live_state.active_signals:
                if not sig.is_live: continue
                
                # Update Performance Context
                price_delta = (market_data.spot_price - sig.entry_price) if "BULLISH" in sig.reasoning else (sig.entry_price - market_data.spot_price)
                if price_delta > sig.mfe:
                    sig.mfe = price_delta
                    sig.time_to_mfe = (datetime.now() - sig.timestamp).total_seconds()
                
                price_adverse = (sig.entry_price - market_data.spot_price) if "BULLISH" in sig.reasoning else (market_data.spot_price - sig.entry_price)
                if price_adverse > sig.mae: sig.mae = price_adverse
                
                # Phase 27/28: Volatility-Normalized Persistence Decay
                # MAE must be bounded relative to ATR to allow for natural breakout rotations.
                # Threshold: MAE > Max(20, 2 * ATR)
                atr_threshold = max(APP_CONFIG["ATR_MAE_MIN_THRESHOLD"], APP_CONFIG["ATR_MAE_MULTIPLIER"] * atr_val)
                integrity_decay = (sig.mae > atr_threshold) and (sig.mfe < 0.5 * atr_threshold)
                
                # Check for Exit
                is_target = price_delta >= APP_CONFIG["SIGNAL_TARGET_POINTS"]
                is_sl = price_adverse >= APP_CONFIG["SIGNAL_STOP_LOSS_POINTS"]
                is_decay = integrity_decay and price_adverse > APP_CONFIG["DECAY_PRICE_ADVERSE_THRESHOLD"]
                
                if is_target or is_sl or is_decay:
                    sig.is_live = False
                    reason = "TARGET" if is_target else ("SL" if is_sl else "DECAY")
                    logger.info(f"SIGNAL EXIT: {sig.option_symbol} closed due to {reason}")
                    
                    # Persistence Calculation (v8.1 Mirror)
                    is_structural = (sig.mfe > 2 * sig.mae) if sig.mae > 1 else (sig.mfe > 10)
                    if sig.time_to_mfe < 5.0 and sig.mfe > (2 * sig.mae) and sig.mfe > 15:
                        is_structural = True

                    # Finalize with Accountability
                    brain_decision_id = sig.decision_id if hasattr(sig, 'decision_id') else decision_id
                    is_win = True if price_delta > APP_CONFIG["SIGNAL_TARGET_POINTS"] else False
                    
                    brain.log_snapshot(
                        decision_id=brain_decision_id,
                        outcome=is_win,
                        performance={
                            "mfe": sig.mfe,
                            "mae": sig.mae,
                            "spread": 0.5, # Placeholder
                            "time_to_mfe": sig.time_to_mfe
                        },
                        freeze_authority=is_passive
                    )
                    
                    # [v9.7] Risk & Sidecar Feedback Loop
                    pnl_sim = price_delta if is_win else -price_adverse
                    if "SIDECAR" in sig.logic_version:
                        trap_hunter.update_outcome(brain_decision_id, pnl_sim)
                    else:
                        risk_engine.log_trade(is_win)
                    
                    # Log to Truth Ledger (for Dashboard UI)
                    db.log_outcome(brain_decision_id, "WIN" if is_win else "LOSS", persistence=is_structural)

            # 6. Signal Generation
            if pattern_results["score"] > APP_CONFIG["PATTERN_SCORE_THRESHOLD_HIGH"]:
                detected_patterns = pattern_results.get("patterns", [])
                signal_type = "BULLISH" if any(p in ["VWAP_CROSSOVER", "HAMMER", "BULLISH_ENGULFING", "CPR_BREAKOUT"] for p in detected_patterns) else "BEARISH"
                
                # Guardrail: Avoid duplicate active signals
                if not any(s.symbol == symbol and s.is_live for s in live_state.active_signals):
                    # Phase 25/27: Hard Veto Gates
                    if is_basis_unstable:
                        logger.warning(f"SIGNAL VETO: Basis Dispersion unstable for {symbol}.")
                    elif is_synthetic:
                        logger.warning(f"SIGNAL VETO: DATA_SYNTHETIC for {symbol}. Blocking execution.")
                        live_state.market_message = f"DATA_OUTAGE: Synthetic Veto Active for {symbol}"
                    else:
                        opt_trade = option_engine.find_executable_option(
                            symbol, 
                            market_data.spot_price, 
                            signal_type,
                            macro_zones=macro_zones,
                            is_momentum_dominant=is_dominant,
                            days_to_expiry=5,
                            chain_df=chain_df,
                            is_synthetic=is_synthetic
                        )
                        
                        if opt_trade.get("rejection_reasons"):
                             # [v9.8] DEBUG: Log why option failed
                             reasons = ", ".join(opt_trade.get("rejection_reasons", []))
                             live_state.add_thought("OPTION_REJECT", f"Execution Failed: {reasons}")
                             if "LIQUIDITY" in reasons:
                                 # Fallback: Trying to find *any* option just to prove signal works?
                                 # For now, just warn.
                                 logger.warning(f"OPTION VETO: {symbol} rejected due to {reasons}")
                        else:
                            # [v9.7] Risk-Adjusted Sizing
                            suggested_size = risk_engine.get_suggested_size(
                                confidence=applied_boost,
                                base_size=APP_CONFIG.get("BASE_LOTS", 1)
                            )
                            
                            new_signal = TradeSignal(
                                symbol=symbol,
                                entry_price=market_data.spot_price,
                                stop_loss=APP_CONFIG["SIGNAL_STOP_LOSS_POINTS"], 
                                target=APP_CONFIG["SIGNAL_TARGET_POINTS"],
                                confidence=SignalConfidence.HIGH if pattern_results["score"] > 0.9 else SignalConfidence.MEDIUM,
                                regime=live_state.current_regime,
                                reasoning=f"{signal_type} | {', '.join(detected_patterns)}",
                                timestamp=datetime.now(timezone.utc),
                                decision_id=decision_id,
                                logic_version="v8.5.0",
                                spread_at_entry=abs(market_data.future_price - market_data.spot_price),
                                quantity=suggested_size, # Applied Risk logic
                                **opt_trade
                            )
                            live_state.active_signals.append(new_signal)
                            logger.info(f"SIGNAL: {new_signal.option_symbol} bound to Decision {decision_id}. Size: {suggested_size}")
                            
                            # [TELEGRAM NOTIFICATION]
                            try:
                                telegram_notifier.send_signal(
                                    new_signal.dict(), 
                                    dashboard_url=APP_CONFIG.get("DASHBOARD_URL", "")
                                )
                            except Exception as e:
                                logger.error(f"TELEGRAM: Failed to send signal: {e}")
            
            else:
                # [v9.1] Sidecar Route for Vetoed Signals
                # If score was blocked (e.g. Brain Veto), check for Trap Hunter
                detected_patterns = pattern_results.get("patterns", [])
                if detected_patterns: # Only if technicals existed but were approved
                    signal_type = "BULLISH" if any(p in ["VWAP_CROSSOVER", "HAMMER", "BULLISH_ENGULFING", "CPR_BREAKOUT"] for p in detected_patterns) else "BEARISH"
                    
                    sidecar_decision = trap_hunter.check_trigger(
                        veto_reason=live_state.market_message,
                        signal_type=signal_type,
                        df=hist_df
                    )
                    
                    if sidecar_decision["action"] == "EXECUTE":
                         # Log Trap Hunter Execution
                         trade_id = trap_hunter.log_execution(
                             trade_type="BEARISH_REVERSAL" if signal_type == "BULLISH" else "BULLISH_REVERSAL",
                             entry_price=market_data.spot_price,
                             reason=sidecar_decision["reason"]
                         )
                         live_state.active_signals.append(TradeSignal(
                             symbol=symbol,
                             entry_price=market_data.spot_price,
                             stop_loss=APP_CONFIG["SIDECAR_STOP_LOSS_POINTS"], # Strict Sidecar SL
                             target=APP_CONFIG["SIDECAR_TARGET_POINTS"],
                             confidence=SignalConfidence.MEDIUM,
                             regime=Regime.SIDEWAYS, # Traps usually in sideways/confused interaction
                             reasoning=f"SIDECAR: {sidecar_decision['reason']}",
                             timestamp=datetime.now(timezone.utc),
                             decision_id=trade_id,
                             logic_version="v9.1_SIDECAR",
                             spread_at_entry=0.0,
                             option_symbol=f"SIDECAR_{symbol}" # Placeholder
                         ))
                         logger.warning(f"SIDECAR EXECUTE: {sidecar_decision['reason']}")
                
                # [v9.7] The Skirmisher V2 (Institutional Upgrade)
                # If brain/sidecar are silent, check for tactical activity scalps in sideways regimes
                is_sideways = "SIDEWAYS" in live_state.current_regime.value
                if is_sideways and not detected_patterns:
                    # [C3 Fix] Provide proper 15m HTF data and actual IV skew
                    try:
                        hist_15m = data_provider.get_history(symbol, interval="15minute")
                    except:
                        hist_15m = hist_df # Fallback if provider fails
                    
                    actual_iv_skew = live_state.iv_skew.get(symbol, 1.0)
                    
                    scalp = skirmisher.check_scalp_signal(
                        df=hist_df,
                        df_htf=hist_15m, 
                        current_regime=live_state.current_regime.value,
                        iv_skew=actual_iv_skew
                    )
                    
                    if scalp["action"] == "EXECUTE":
                        # 0. Brain Statistical Oversight
                        approved, thoughts = brain.evaluate_skirmisher_signal(
                            signal=scalp,
                            regime=live_state.current_regime,
                            iv_skew=actual_iv_skew
                        )
                        
                        for t in thoughts: live_state.add_thought("BRAIN", t)
                        
                        if approved:
                            # Log Scalp (Activity Only)
                            trade_id = skirmisher.log_execution(scalp)
                            live_state.active_signals.append(TradeSignal(
                                 symbol=symbol,
                                 entry_price=market_data.spot_price,
                                 stop_loss=scalp["stop_loss"],
                                 target=scalp["take_profit"],
                                 confidence=SignalConfidence.LOW,
                                 regime=live_state.current_regime,
                                 reasoning=f"⚠️ V2 SCALP: {scalp['reason']} (Qual: {scalp['quality']})",
                                 timestamp=datetime.now(timezone.utc),
                                 decision_id=trade_id,
                                 logic_version="v2.0_SKIRMISHER_INSTITUTIONAL",
                                 spread_at_entry=0.0,
                                 option_symbol=f"SCALP_{symbol}" 
                            ))
                            logger.warning(f"SKIRMISHER V2 EXECUTE: {scalp['reason']}")
                        else:
                            logger.info(f"SKIRMISHER V2 VETOED by Brain.")


            
            # 7. Rotation & Sleep
            # live_state.last_update = datetime.now(timezone.utc) # Moved to start of loop for accuracy
            
            # [v9.5] Memory Safety: Cap active signals to last 20 to prevent memory leak
            if len(live_state.active_signals) > APP_CONFIG["SIGNAL_ACTIVE_CAP"]:
                live_state.active_signals = live_state.active_signals[-20:]
                
            # [v9.5.7] Stealth Polling: 3s Base + 0-2s Jitter
            import random
            sleep_time = APP_CONFIG["ENGINE_POLLING_BASE_SECONDS"] + random.uniform(0, APP_CONFIG["ENGINE_POLLING_JITTER_SECONDS"])
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"ENGINE ERROR: {e}", exc_info=True)
            live_state.add_thought("ERROR", f"Engine experienced critical error: {e}. Restarting loop...")
            time.sleep(APP_CONFIG["ENGINE_ERROR_SLEEP_TIME"])

@app.on_event("startup")
async def startup_event():
    # Start engine in a separate thread to not block the API
    engine_thread = threading.Thread(target=run_engine_loop, daemon=True)
    engine_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    logger.info(f"API: Initializing server on port {port}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.critical(f"API CRITICAL ERROR: {e}", exc_info=True)
