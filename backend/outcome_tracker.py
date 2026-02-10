"""
Titan Plus: Enhanced Automatic Signal Outcome Tracker
======================================================
IMPROVEMENTS:
- Retry logic for failed price fetches
- Better option symbol parsing
- Fallback mechanisms
- Enhanced logging
- Statistics caching

Version: 10.2.0
Author: Titan Plus Development Team
"""

import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import re

logger = logging.getLogger("outcome_tracker")


@dataclass
class SignalOutcome:
    """Represents the final outcome of a signal"""
    signal_id: str
    symbol: str
    entry_price: float
    stop_loss: float
    target: float
    direction: str  # CALL or PUT
    
    # Outcome tracking
    outcome: str  # WIN, LOSS, BREAKEVEN, EXPIRED, MONITORING
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    max_favorable: Optional[float] = None
    max_adverse: Optional[float] = None
    
    # Metadata
    generated_at: datetime = None
    closed_at: Optional[datetime] = None
    monitoring_duration_hours: int = 24
    
    # NEW: Retry tracking
    fetch_failures: int = 0
    last_fetch_time: Optional[datetime] = None


class OutcomeTracker:
    """
    ENHANCED: Automatically tracks signal outcomes with improved reliability.
    """
    
    def __init__(self, data_provider, db_manager):
        self.data_provider = data_provider
        self.db = db_manager
        
        self.active_monitors: Dict[str, SignalOutcome] = {}
        self.completed_outcomes: List[SignalOutcome] = []
        
        self.monitoring_thread = None
        self.is_running = False
        
        # Configuration
        self.check_interval_seconds = 60
        self.max_monitoring_hours = 24
        self.max_fetch_retries = 5  # NEW: Max retries before giving up
        self.retry_cooldown_seconds = 300  # NEW: Wait 5 minutes before retry
        
        # NEW: Statistics cache
        self._stats_cache = None
        self._stats_cache_time = None
        self._stats_cache_ttl = 60  # Cache for 60 seconds
        
        logger.info("Enhanced OutcomeTracker initialized")
    
    def start_monitoring(self):
        """Start the background monitoring thread"""
        if self.is_running:
            logger.warning("OutcomeTracker already running")
            return
        
        self.is_running = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="OutcomeMonitor"
        )
        self.monitoring_thread.start()
        logger.info("OutcomeTracker monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("OutcomeTracker stopped")
    
    def track_signal(self, signal):
        """
        Start tracking a new signal.
        
        Args:
            signal: TradeSignal object from brain
        """
        outcome = SignalOutcome(
            signal_id=signal.decision_id,
            symbol=signal.symbol,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target=signal.target,
            direction=signal.option_type,
            outcome="MONITORING",
            generated_at=datetime.now(timezone.utc)
        )
        
        self.active_monitors[signal.decision_id] = outcome
        
        logger.info(
            f"Tracking signal {signal.decision_id}: "
            f"{signal.symbol} {signal.option_type} @ {signal.entry_price}, "
            f"SL={signal.stop_loss}, Target={signal.target}"
        )
        
        # Log to database
        if self.db:
            try:
                self.db.log_signal_tracking(outcome)
            except Exception as e:
                logger.error(f"Failed to log signal tracking: {e}")
    
    def _monitoring_loop(self):
        """Background loop that checks signal outcomes"""
        logger.info("Outcome monitoring loop started")
        
        while self.is_running:
            try:
                self._check_all_signals()
                time.sleep(self.check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(self.check_interval_seconds)
    
    def _check_all_signals(self):
        """Check outcomes for all active signals"""
        if not self.active_monitors:
            return
        
        now = datetime.now(timezone.utc)
        completed_ids = []
        
        for signal_id, outcome in self.active_monitors.items():
            try:
                # Check if monitoring period expired
                elapsed = (now - outcome.generated_at).total_seconds() / 3600
                if elapsed > self.max_monitoring_hours:
                    outcome.outcome = "EXPIRED"
                    outcome.closed_at = now
                    completed_ids.append(signal_id)
                    logger.info(f"Signal {signal_id} expired after {elapsed:.1f}h")
                    continue
                
                # NEW: Check retry cooldown
                if outcome.fetch_failures >= self.max_fetch_retries:
                    logger.warning(f"Signal {signal_id} exceeded max retries, marking as EXPIRED")
                    outcome.outcome = "EXPIRED"
                    outcome.closed_at = now
                    completed_ids.append(signal_id)
                    continue
                
                # NEW: Enforce cooldown between retries
                if outcome.last_fetch_time:
                    cooldown_elapsed = (now - outcome.last_fetch_time).total_seconds()
                    if cooldown_elapsed < self.retry_cooldown_seconds:
                        continue  # Skip this check, wait for cooldown
                
                # Get current market price for the option
                current_price = self._get_current_option_price(outcome)
                
                # NEW: Track fetch failures
                outcome.last_fetch_time = now
                
                if current_price is None:
                    outcome.fetch_failures += 1
                    logger.warning(
                        f"Failed to fetch price for {signal_id} "
                        f"(attempt {outcome.fetch_failures}/{self.max_fetch_retries})"
                    )
                    continue
                
                # Reset failure counter on successful fetch
                outcome.fetch_failures = 0
                
                # Update max favorable/adverse
                if outcome.max_favorable is None or current_price > outcome.max_favorable:
                    outcome.max_favorable = current_price
                if outcome.max_adverse is None or current_price < outcome.max_adverse:
                    outcome.max_adverse = current_price
                
                # Check if target hit (WIN)
                if current_price >= outcome.target:
                    outcome.outcome = "WIN"
                    outcome.exit_price = current_price
                    outcome.closed_at = now
                    completed_ids.append(signal_id)
                    logger.info(
                        f"✅ Signal {signal_id} HIT TARGET: "
                        f"{outcome.entry_price} → {current_price} "
                        f"(Target: {outcome.target})"
                    )
                
                # Check if stop loss hit (LOSS)
                elif current_price <= outcome.stop_loss:
                    outcome.outcome = "LOSS"
                    outcome.exit_price = current_price
                    outcome.closed_at = now
                    completed_ids.append(signal_id)
                    logger.info(
                        f"❌ Signal {signal_id} HIT STOP LOSS: "
                        f"{outcome.entry_price} → {current_price} "
                        f"(SL: {outcome.stop_loss})"
                    )
            
            except Exception as e:
                logger.error(f"Error checking signal {signal_id}: {e}", exc_info=True)
        
        # Move completed signals to history
        for signal_id in completed_ids:
            outcome = self.active_monitors.pop(signal_id)
            self.completed_outcomes.append(outcome)
            
            # Invalidate stats cache
            self._stats_cache = None
            
            # Log to database
            if self.db:
                try:
                    self.db.log_signal_outcome(outcome)
                except Exception as e:
                    logger.error(f"Failed to log outcome: {e}")
    
    def _get_current_option_price(self, outcome: SignalOutcome) -> Optional[float]:
        """
        IMPROVED: Fetch current option premium with better parsing and fallbacks.
        """
        try:
            # NEW: Better symbol parsing with regex
            base_symbol = self._extract_base_symbol(outcome.symbol)
            
            if not base_symbol:
                logger.error(f"Cannot extract base symbol from: {outcome.symbol}")
                return None
            
            # Get option chain for the base symbol
            chain = self.data_provider.get_option_chain(base_symbol)
            
            if chain is None or (hasattr(chain, 'empty') and chain.empty):
                logger.debug(f"No option chain data for {base_symbol}")
                return None
            
            # NEW: Better strike and type extraction
            strike, option_type = self._parse_option_symbol(outcome.symbol)
            
            if not strike or not option_type:
                logger.error(f"Cannot parse option symbol: {outcome.symbol}")
                return None
            
            # Find the matching row in option chain
            matching_rows = chain[chain['strike'] == strike]
            
            if matching_rows.empty:
                logger.debug(f"Strike {strike} not found in option chain")
                return None
            
            # Get the first matching row
            row = matching_rows.iloc[0]
            
            # NEW: Try multiple column name variations
            ltp = self._extract_ltp(row, option_type)
            
            if ltp is None or ltp == 0:
                logger.debug(f"No LTP data for {outcome.symbol}")
                return None
            
            return float(ltp)
            
        except Exception as e:
            logger.error(f"Failed to fetch option price for {outcome.symbol}: {e}", exc_info=True)
            return None
    
    def _extract_base_symbol(self, symbol: str) -> Optional[str]:
        """
        NEW: Extract base symbol with improved logic.
        
        Examples:
            NIFTY28FEB2424500CE -> NIFTY
            BANKNIFTY28FEB2450000PE -> BANKNIFTY
            SENSEX28FEB2483000CE -> SENSEX
        """
        known_symbols = ["BANKNIFTY", "NIFTY", "SENSEX"]
        
        for sym in known_symbols:
            if symbol.startswith(sym):
                return sym
        
        # Fallback: Use regex to extract alphabetic prefix
        match = re.match(r'^([A-Z]+)', symbol)
        if match:
            return match.group(1)
        
        return None
    
    def _parse_option_symbol(self, symbol: str) -> tuple:
        """
        NEW: Parse option symbol to extract strike and type.
        
        Returns:
            (strike, option_type) or (None, None) if parsing fails
        
        Examples:
            NIFTY28FEB2424500CE -> (24500, 'CE')
            BANKNIFTY28FEB2450000PE -> (50000, 'PE')
        """
        # Try standard format: ...DDMMMYYSTRIKEPE/CE
        match = re.search(r'(\d+)(CE|PE)$', symbol)
        
        if match:
            strike = int(match.group(1))
            option_type = match.group(2)
            return strike, option_type
        
        logger.error(f"Cannot parse option symbol format: {symbol}")
        return None, None
    
    def _extract_ltp(self, row, option_type: str) -> Optional[float]:
        """
        NEW: Extract LTP with multiple fallback column names.
        
        Different data providers use different column names.
        """
        # Possible column name variations
        if option_type == "CE":
            possible_columns = [
                'call_ltp', 'CE_LTP', 'calls_ltp', 'CE_ltp',
                'call_LTP', 'Call_LTP', 'CALL_LTP'
            ]
        else:  # PE
            possible_columns = [
                'put_ltp', 'PE_LTP', 'puts_ltp', 'PE_ltp',
                'put_LTP', 'Put_LTP', 'PUT_LTP'
            ]
        
        # Try each possible column name
        for col in possible_columns:
            if col in row:
                ltp = row[col]
                if ltp is not None and ltp != 0:
                    return float(ltp)
        
        # Log available columns for debugging
        logger.warning(
            f"No LTP column found for {option_type}. "
            f"Available columns: {list(row.index)}"
        )
        
        return None
    
    def get_statistics(self) -> Dict:
        """
        NEW: Get outcome statistics with caching.
        """
        # Check cache
        now = time.time()
        if (self._stats_cache is not None and 
            self._stats_cache_time is not None and
            (now - self._stats_cache_time) < self._stats_cache_ttl):
            return self._stats_cache
        
        # Calculate fresh statistics
        total = len(self.completed_outcomes)
        
        if total == 0:
            stats = {
                "total_tracked": 0,
                "win_rate": 0.0,
                "wins": 0,
                "losses": 0,
                "expired": 0,
                "monitoring": len(self.active_monitors),
                "avg_win_pnl": 0.0,
                "avg_loss_pnl": 0.0,
                "profit_factor": 0.0
            }
        else:
            wins = [o for o in self.completed_outcomes if o.outcome == "WIN"]
            losses = [o for o in self.completed_outcomes if o.outcome == "LOSS"]
            expired = [o for o in self.completed_outcomes if o.outcome == "EXPIRED"]
            
            # Calculate PnL statistics
            win_pnls = [o.exit_price - o.entry_price for o in wins if o.exit_price]
            loss_pnls = [o.entry_price - o.exit_price for o in losses if o.exit_price]
            
            avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
            avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
            
            total_wins = sum(win_pnls) if win_pnls else 0.0
            total_losses = sum(loss_pnls) if loss_pnls else 0.0
            
            profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0
            
            stats = {
                "total_tracked": total,
                "win_rate": (len(wins) / total * 100) if total > 0 else 0.0,
                "wins": len(wins),
                "losses": len(losses),
                "expired": len(expired),
                "monitoring": len(self.active_monitors),
                "avg_win_pnl": avg_win,
                "avg_loss_pnl": avg_loss,
                "profit_factor": profit_factor
            }
        
        # Update cache
        self._stats_cache = stats
        self._stats_cache_time = now
        
        return stats
    
    def get_recent_outcomes(self, limit: int = 10) -> List[Dict]:
        """Get recent completed outcomes for display"""
        recent = sorted(
            self.completed_outcomes,
            key=lambda x: x.closed_at or x.generated_at,
            reverse=True
        )[:limit]
        
        return [
            {
                "signal_id": o.signal_id,
                "symbol": o.symbol,
                "direction": o.direction,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "outcome": o.outcome,
                "pnl": (o.exit_price - o.entry_price) if o.exit_price else 0.0,
                "generated_at": o.generated_at.isoformat() if o.generated_at else None,
                "closed_at": o.closed_at.isoformat() if o.closed_at else None,
                "duration_hours": ((o.closed_at - o.generated_at).total_seconds() / 3600) 
                                 if (o.closed_at and o.generated_at) else 0.0
            }
            for o in recent
        ]
    
    def get_monitoring_status(self) -> Dict:
        """
        NEW: Get detailed monitoring status for debugging.
        """
        return {
            "is_running": self.is_running,
            "active_monitors": len(self.active_monitors),
            "completed_outcomes": len(self.completed_outcomes),
            "signals_by_status": {
                signal_id: {
                    "symbol": outcome.symbol,
                    "outcome": outcome.outcome,
                    "fetch_failures": outcome.fetch_failures,
                    "monitoring_hours": ((datetime.now(timezone.utc) - outcome.generated_at).total_seconds() / 3600)
                                       if outcome.generated_at else 0.0
                }
                for signal_id, outcome in self.active_monitors.items()
            }
        }


if __name__ == "__main__":
    # Test the enhanced outcome tracker
    logging.basicConfig(level=logging.INFO)
    
    print("Enhanced OutcomeTracker module loaded successfully")
    print("\nIMPROVEMENTS:")
    print("✅ Retry logic for failed price fetches")
    print("✅ Better option symbol parsing")
    print("✅ Multiple column name fallbacks")
    print("✅ Statistics caching")
    print("✅ Enhanced logging")
    print("✅ Monitoring status endpoint")
