from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import uvicorn
import pandas as pd
import logging
import time
from datetime import datetime
import pandas_ta as ta
from models import TradeSignal, Regime, SignalConfidence, DivergenceType
from sentinel import DataSentinel
from strategist import MarketStrategist
from risk_engine import RiskEngine
from brain_engine import BrainEngine
from pattern_engine import PatternEngine
from option_engine import OptionEngine
from database import DatabaseManager
from data_provider import DataProvider
import asyncio
import threading
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        self.last_update = datetime.now()
        self.symbols = ["NIFTY", "SENSEX"]
        self.current_symbol_idx = 0
        self.vix = 15.0
        self.breadth = {"advances": 0, "declines": 0}
        self.market_message = "System Stable"
        self.data_source = "PUBLIC_SCRAPER"
        self.index_strengths: Dict[str, float] = {"NIFTY": 0.0, "SENSEX": 0.0}
        self.max_pain = 0.0
        self.option_battles = []
        # Fallback to last known Friday close prices
        self.nifty_price = 25048.65
        self.sensex_price = 81537.70
        self.option_chain = []
        # v8.1: Statistical Discipline
        self.resets_today = 0
        self.last_reset_time = datetime.now()
        self.beta_history = {"OI": [], "BASIS": []}
        self.iv_skew = 1.0 # 1.0 is neutral

live_state = LiveState()

# Engines
sentinel = DataSentinel()
strategist = MarketStrategist()
pattern_engine = PatternEngine()
risk_engine = RiskEngine()
brain = BrainEngine()
option_engine = OptionEngine()
db = DatabaseManager()
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
    nifty_price: float
    sensex_price: float
    max_pain: float
    option_battles: List[Dict]
    option_chain: List[Dict]

@app.get("/health")
async def health_check():
    """Heartbeat endpoint for the external pinger (cron-job.org)."""
    return {
        "status": "active",
        "engine": "Titan Plus",
        "timestamp": datetime.now().isoformat(),
        "cloud_memory": "Supabase Linked"
    }

@app.get("/state", response_model=SystemState)
async def get_state():
    return SystemState(
        regime=live_state.current_regime,
        is_in_recovery=risk_engine.is_in_recovery(),
        data_latency=(datetime.now() - live_state.last_update).total_seconds(),
        integrity_status=live_state.integrity,
        active_signals=live_state.active_signals,
        last_update=live_state.last_update,
        vix=live_state.vix,
        breadth=live_state.breadth,
        market_message=live_state.market_message,
        data_source=live_state.data_source,
        max_pain=live_state.max_pain,
        option_battles=live_state.option_battles,
        nifty_price=live_state.nifty_price,
        sensex_price=live_state.sensex_price,
        option_chain=live_state.option_chain
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

@app.post("/feedback")
async def post_feedback(signal_id: int, outcome: str, override: bool = False):
    # Logic to log feedback and retrain brain
    return {"status": "success"}

@app.post("/reset")
async def reset_system():
    """Emergency Reset: Clears recovery mode and active signals."""
    risk_engine.reset()
    live_state.active_signals = []
    live_state.market_message = "SYSTEM RESET: Lockout Cleared"
    logger.info("API: Emergency System Reset Triggered")
    return {"status": "system_reset_complete"}

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

            # 1. Fetch Data (Priority Ticker Update)
            try:
                # Use a very short timeout for ticker updates
                market_data = data_provider.get_market_snapshot(symbol)
                
                # Update specific price tracking for Ticker (DO FIRST)
                if symbol == "NIFTY" and market_data.spot_price > 0:
                    live_state.nifty_price = market_data.spot_price
                elif symbol == "SENSEX" and market_data.spot_price > 0:
                    live_state.sensex_price = market_data.spot_price

                if data_provider.use_groww and live_state.data_source != "GROWW_API":
                    live_state.data_source = "GROWW_API"
                elif not data_provider.use_groww and live_state.data_source != "PUBLIC_SCRAPER":
                    live_state.data_source = "PUBLIC_SCRAPER"
            except Exception as e:
                logger.warning(f"ENGINE: Snapshot fetch failed for {symbol}: {e}")
                # Use hardcoded fallback to keep ticker alive even if everything fails
                if symbol == "NIFTY" and live_state.nifty_price == 0: live_state.nifty_price = 24500.0
                if symbol == "SENSEX" and live_state.sensex_price == 0: live_state.sensex_price = 81500.0
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
            
            # 3. Regime Detection (Strategist)
            try:
                # Execute Timeframe (5m)
                hist_df = data_provider.get_history(symbol, interval="5minute")
                live_state.current_regime = strategist.classify_regime(hist_df)
                
                # Calculate simple strength
                live_state.index_strengths[symbol] = (market_data.spot_price - hist_df.open.iloc[0]) / hist_df.open.iloc[0] * 100

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
                logger.warning(f"ENGINE: Analysis failed for {symbol}: {e}")
                pattern_results = {"score": 0.0, "patterns": []}
                macro_bias = 0
            
            # Phase 14: Option Chain X-Ray
            try:
                chain_df = data_provider.get_option_chain(symbol)
                if not chain_df.empty:
                    live_state.max_pain = option_engine.calculate_max_pain(chain_df)
                    live_state.option_battles = option_engine.detect_strike_battles(chain_df)
                    live_state.option_chain = chain_df.to_dict('records')
                    
                    # Boost pattern score if price is near Max Pain (The Magnet)
                    if abs(market_data.spot_price - live_state.max_pain) < 20: # Close to magnet
                        pattern_results["score"] *= 1.2
                        live_state.market_message = "MAX PAIN SYNC: Large Confluence Near Strike"
            except Exception as e:
                logger.warning(f"ENGINE: Option chain failed for {symbol}: {e}")

            # Phase 11: Inter-Market Correlation Filter
            other_symbol = "SENSEX" if symbol == "NIFTY" else "NIFTY"
            other_strength = live_state.index_strengths.get(other_symbol, 0.0)
            curr_strength = live_state.index_strengths[symbol]
            
            # If they are moving in opposite directions, it's a weak signal
            if (curr_strength > 0 and other_strength < -0.1) or (curr_strength < 0 and other_strength > 0.1):
                pattern_results["score"] *= 0.6
                live_state.market_message = f"DIVERGENCE: {symbol} vs {other_symbol} Mismatch"

            # Phase 9: VIX Sensitivity Adjustment
            try:
                live_state.vix = data_provider.get_vix()
                if live_state.vix > 20:
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
            now = datetime.now().time()
            lull_start = datetime.strptime("12:00", "%H:%M").time()
            lull_end = datetime.strptime("13:30", "%H:%M").time()
            is_lull = lull_start <= now <= lull_end
            if is_lull:
                pattern_results["score"] *= 0.5
                live_state.market_message = "INSTITUTIONAL LULL: Low Confidence Zone"

            # v8.1: Orthogonal Feature Engineering (Fix Audit v8.1 #1)
            try:
                # 1. Price Velocity & Variance Gate
                price_velocities = hist_df.close.pct_change(5).dropna() * 100
                price_var = price_velocities.var()
                price_vel_curr = price_velocities.iloc[-1] if not price_velocities.empty else 0.0
                
                # 2. Bounded Beta Calculation (No Heuristics)
                # Formula: Beta = Cov(X,Y) / Var(Y)
                if price_var > 1e-4:
                    # OI Beta
                    oi_chgs = pd.Series(brain.feature_history.get("OI_RES", [])[-20:])
                    if len(oi_chgs) == len(price_velocities.iloc[-len(oi_chgs):]):
                        oi_beta = oi_chgs.cov(price_velocities.iloc[-len(oi_chgs):]) / price_var
                        # Clip Beta (Fix Audit v8.1 #1)
                        oi_beta = max(-1.5, min(1.5, oi_beta))
                    else: oi_beta = 0.2
                    
                    # Basis Beta
                    basis_vals = pd.Series(brain.feature_history.get("BASIS_RES", [])[-20:])
                    if len(basis_vals) == len(price_velocities.iloc[-len(basis_vals):]):
                        basis_beta = basis_vals.cov(price_velocities.iloc[-len(basis_vals):]) / price_var
                        basis_beta = max(-2.0, min(2.0, basis_beta))
                    else: basis_beta = 0.5
                else:
                    oi_beta = 0.0
                    basis_beta = 0.0
                
                # 3. Residual Generation
                last_oi = live_state.prev_oi.get(symbol, market_data.oi)
                oi_change = ((market_data.oi - last_oi) / last_oi * 100) if last_oi > 0 else 0.0
                raw_basis = abs(market_data.future_price - market_data.spot_price) / market_data.spot_price * 100
                
                oi_res = oi_change - (oi_beta * price_vel_curr)
                basis_res = raw_basis - (basis_beta * price_vel_curr)
                
                live_state.prev_oi[symbol] = market_data.oi
                live_state.prev_spot = market_data.spot_price

                brain_features = {
                    "OI_RES": oi_res,
                    "PCR": market_data.pcr,
                    "BASIS_RES": basis_res,
                    "ADX": hist_df.ta.adx()['ADX_14'].iloc[-1] if 'ADX_14' in hist_df.ta.adx() else 25.0
                }
            except Exception as e:
                logger.error(f"FEATURE ERROR: {e}")
                brain_features = {"OI_RES": 0, "PCR": 1.0, "BASIS_RES": 0, "ADX": 25.0}
            
            # v8.1: Stateless Inference (Compute-only unless pattern detects)
            decision_id = brain.generate_decision(
                brain_features, 
                regime=live_state.current_regime, 
                is_commit=False,
                pattern_score=pattern_results["score"]
            )

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

            # Calculate Brain Boost
            confidence_boost = brain.get_confidence_boost(brain_features, regime=live_state.current_regime.value)
            
            # Non-Price Orthogonal Veto (Fix Audit v8.1 #3)
            # IV Skew as Veto-Only.
            live_state.iv_skew = data_provider.get_iv_skew(symbol)
            if live_state.iv_skew > 1.3: # Extreme Put-buying skew
                confidence_boost *= 0.5
                live_state.market_message = "RISK VETO: Extreme IV Skew Detected"
            
            # Timing Guardrails
            now_ts = time.time()
            elapsed = now_ts - start_time
            is_passive = elapsed < 800
            
            applied_boost = 1.0 if is_passive else confidence_boost
            
            # Timing Guardrails (Calibration/Stabilization)
            now_ts = time.time()
            elapsed = now_ts - start_time
            is_passive = elapsed < 800
            
            applied_boost = 1.0 if is_passive else confidence_boost
            
            # v8: Momentum Dominance Check (Fix Audit v8 Failure #5)
            # If momentum is dominant, we ignore Max Pain in patterns.
            is_dominant = strategist.is_momentum_dominant(hist_df)
            if is_dominant:
                live_state.market_message = "MOMENTUM DOMINANT: Ignoring Mean Reversion"

            # THE v8 DOUBLE-HANDSHAKE
            if not is_passive:
                if pattern_results["score"] > 0.8 and applied_boost > 0.8:
                    # Both agree -> High conviction
                    pattern_results["score"] *= 1.2 # Synergy boost
                    live_state.market_message = "ORTHOGONAL CONFIRMATION: Dual Edge Active"
                elif pattern_results["score"] < 0.6 and applied_boost > 0.8:
                    # Brain sees it but chart is ugly -> Mute
                    applied_boost *= 0.5
                    live_state.market_message = "DIVERGENCE: Brain Disagrees with Price"
                
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
                
                # Check for Exit
                if price_adverse > 50 or price_delta > 100:
                    sig.is_live = False
                    # Finalize with Accountability (Guardrail #1: Freeze authority during calibration)
                    brain.log_snapshot(
                        decision_id=sig.decision_id if hasattr(sig, 'decision_id') else decision_id,
                        outcome=True if price_delta > 100 else False,
                        performance={
                            "mfe": sig.mfe,
                            "mae": sig.mae,
                            "spread": 0.5, # Placeholder
                            "time_to_mfe": sig.time_to_mfe
                        },
                        freeze_authority=is_passive
                    )

            # 6. Signal Generation
            if pattern_results["score"] > 0.8:
                signal_type = "BULLISH" if any(p in ["VWAP_CROSSOVER", "HAMMER", "BULLISH_ENGULFING", "CPR_BREAKOUT"] for p in detected_patterns) else "BEARISH"
                
                # Guardrail: Avoid duplicate active signals
                if not any(s.symbol == symbol and s.is_live for s in live_state.active_signals):
                    opt_trade = option_engine.find_executable_option(symbol, market_data.spot_price, signal_type)
                    
                    new_signal = TradeSignal(
                        symbol=symbol,
                        entry_price=market_data.spot_price,
                        stop_loss=50, 
                        target=100,
                        confidence=SignalConfidence.HIGH if pattern_results["score"] > 0.9 else SignalConfidence.MEDIUM,
                        regime=live_state.current_regime,
                        reasoning=f"{signal_type} | {', '.join(detected_patterns)}",
                        timestamp=datetime.now(),
                        decision_id=decision_id,
                        spread_at_entry=abs(market_data.future_price - market_data.spot_price),
                        **opt_trade
                    )
                    live_state.active_signals.append(new_signal)
                    logger.info(f"SIGNAL: {new_signal.option_symbol} bound to Decision {decision_id}")
            
            # 7. Rotation & Sleep
            live_state.last_update = datetime.now()
            time.sleep(1)
        except Exception as e:
            logger.error(f"ENGINE ERROR: {e}")
            time.sleep(5)

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
        logger.error(f"API CRITICAL ERROR: {e}")
