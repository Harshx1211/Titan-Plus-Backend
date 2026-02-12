"""
CRITICAL SAFETY SYSTEMS (v15.3.8 - Industrial Hardening)
=========================================================
Enhanced with:
- 1.5s data staleness threshold
- Bid-ask spread validation
- Volume validation
- Per-position max loss
- Consecutive loss circuit breaker
- Stop loss frequency limits
- Risk-reward minimum enforcement
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("critical_safety")


# ============================================================================
# ENUMS & EXCEPTIONS
# ============================================================================

class RiskViolation(Exception):
    """Exception raised when a trade violates risk parameters"""
    pass


class PositionStatus(str, Enum):
    """Position lifecycle states"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"
    TARGET_HIT = "TARGET_HIT"


# ============================================================================
# DATA HEALTH CHECKER (PRIORITY 1)
# ============================================================================

class DataHealthChecker:
    """
    [v15.3.8] INDUSTRIAL HARDENING
    - Tightened staleness: 5s → 1.5s
    - Bid-ask spread validation: max 0.5%
    - Volume validation: min 100
    """
    
    def __init__(self):
        # [HARDENED] Much tighter threshold for F&O
        self.max_data_age_seconds = 1.5  # Down from 5.0
        
        # [NEW] Spread and volume validation
        self.max_spread_pct = 0.5  # Max 0.5% bid-ask spread
        self.min_volume_threshold = 100  # Minimum volume for valid quote
        
        # Price move validation (existing)
        self.max_price_move_pct = 2.0  # 2% sanity check
        
        # State tracking
        self.last_valid_prices: Dict[str, float] = {}
        self.last_valid_times: Dict[str, datetime] = {}
        
        logger.info(
            f"DataHealthChecker initialized: "
            f"max_age={self.max_data_age_seconds}s, "
            f"max_spread={self.max_spread_pct}%, "
            f"min_volume={self.min_volume_threshold}"
        )
    
    def validate_market_data(self, 
                            symbol: str, 
                            price: float, 
                            timestamp: datetime,
                            volume: int = 0,
                            bid: Optional[float] = None,
                            ask: Optional[float] = None) -> Tuple[bool, str]:
        """
        [v15.3.8] ENHANCED VALIDATION
        
        Returns:
            (is_valid, reason)
        """
        
        # ========================================
        # CHECK 1: Data Freshness (HARDENED: 1.5s)
        # ========================================
        age_seconds = (datetime.now(timezone.utc) - timestamp).total_seconds()
        
        if age_seconds > self.max_data_age_seconds:
            logger.error(
                f"STALE_DATA: {symbol} data is {age_seconds:.2f}s old "
                f"(max: {self.max_data_age_seconds}s)"
            )
            return False, f"STALE_DATA: {age_seconds:.2f}s > {self.max_data_age_seconds}s"
        
        # ========================================
        # CHECK 2: Volume Validation (NEW)
        # ========================================
        if volume < self.min_volume_threshold:
            logger.warning(
                f"LOW_VOLUME: {symbol} volume {volume} < {self.min_volume_threshold}"
            )
            return False, f"LOW_VOLUME: {volume} < {self.min_volume_threshold}"
        
        # ========================================
        # CHECK 3: Bid-Ask Spread Validation (NEW)
        # ========================================
        if bid is not None and ask is not None and price > 0:
            spread_pct = ((ask - bid) / price) * 100
            
            if spread_pct > self.max_spread_pct:
                logger.warning(
                    f"WIDE_SPREAD: {symbol} spread {spread_pct:.2f}% "
                    f"> {self.max_spread_pct}%"
                )
                return False, f"WIDE_SPREAD: {spread_pct:.2f}% > {self.max_spread_pct}%"
        
        # ========================================
        # CHECK 4: Price Move Sanity (EXISTING)
        # ========================================
        last_price = self.last_valid_prices.get(symbol)
        
        if last_price is not None and price > 0:
            price_move_pct = abs((price - last_price) / last_price) * 100
            
            if price_move_pct > self.max_price_move_pct:
                logger.warning(
                    f"LARGE_MOVE: {symbol} moved {price_move_pct:.2f}% "
                    f"(from {last_price:.2f} to {price:.2f})"
                )
                # Note: We LOG but don't BLOCK - legitimate moves can be large
        
        # Update state
        self.last_valid_prices[symbol] = price
        self.last_valid_times[symbol] = timestamp
        
        return True, "VALID"
    
    def get_last_valid_price(self, symbol: str) -> Optional[float]:
        """Get last validated price for symbol"""
        return self.last_valid_prices.get(symbol)
    
    def get_data_age(self, symbol: str) -> Optional[float]:
        """Get age of last valid data in seconds"""
        last_time = self.last_valid_times.get(symbol)
        if last_time:
            return (datetime.now(timezone.utc) - last_time).total_seconds()
        return None


# ============================================================================
# POSITION (Enhanced with Greeks tracking)
# ============================================================================

@dataclass
class Position:
    """
    [v15.3.8] Enhanced with per-position risk tracking
    """
    signal_id: str
    symbol: str
    option_type: str  # CE or PE
    entry_price: float
    current_price: float
    quantity: int
    stop_loss: float
    target: float
    entry_time: datetime
    status: PositionStatus
    
    # Greeks (for future enhancement)
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # MFE/MAE tracking
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    
    def update_price(self, new_price: float):
        """Update position with new market price"""
        self.current_price = new_price
        self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        
        # Track MFE/MAE
        if self.unrealized_pnl > self.max_favorable_excursion:
            self.max_favorable_excursion = self.unrealized_pnl
        
        if self.unrealized_pnl < self.max_adverse_excursion:
            self.max_adverse_excursion = self.unrealized_pnl
    
    def get_unrealized_pnl(self) -> float:
        """Calculate current unrealized P&L"""
        return (self.current_price - self.entry_price) * self.quantity
    
    def get_unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L as percentage"""
        if self.entry_price > 0:
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        return 0.0


# ============================================================================
# POSITION MANAGER
# ============================================================================

class PositionManager:
    """Manages open positions and P&L tracking"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.closed_positions: list = []
        
        # P&L tracking
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.daily_trades = 0
        
        logger.info("PositionManager initialized")
    
    def add_position(self, signal_dict: Dict) -> Position:
        """Create and track new position"""
        position = Position(
            signal_id=signal_dict['signal_id'],
            symbol=signal_dict.get('symbol', 'UNKNOWN'),
            option_type=signal_dict.get('option_type', 'CE'),
            entry_price=signal_dict['entry_price'],
            current_price=signal_dict['entry_price'],
            quantity=signal_dict.get('quantity', 75),
            stop_loss=signal_dict.get('stop_loss', 0),
            target=signal_dict.get('target', 0),
            entry_time=datetime.now(timezone.utc),
            status=PositionStatus.OPEN
        )
        
        self.positions[position.signal_id] = position
        self.daily_trades += 1
        
        logger.info(
            f"Position added: {position.signal_id} - {position.symbol} @ {position.entry_price}"
        )
        
        return position
    
    def update_position(self, signal_id: str, current_price: float):
        """Update position with current market price"""
        if signal_id in self.positions:
            position = self.positions[signal_id]
            position.update_price(current_price)
            
            # Recalculate daily P&L
            self.daily_pnl = sum(pos.get_unrealized_pnl() for pos in self.positions.values())
    
    def close_position(self, signal_id: str, exit_price: float, reason: str):
        """Close position and realize P&L"""
        if signal_id in self.positions:
            position = self.positions[signal_id]
            position.current_price = exit_price
            position.realized_pnl = (exit_price - position.entry_price) * position.quantity
            
            if "STOP" in reason.upper():
                position.status = PositionStatus.STOPPED
            elif "TARGET" in reason.upper():
                position.status = PositionStatus.TARGET_HIT
            else:
                position.status = PositionStatus.CLOSED
            
            # Update totals
            self.total_pnl += position.realized_pnl
            self.daily_pnl += position.realized_pnl
            
            # Move to closed
            self.closed_positions.append(position)
            del self.positions[signal_id]
            
            logger.info(
                f"Position closed: {signal_id} - {reason} - "
                f"P&L: ₹{position.realized_pnl:.2f}"
            )
            
            return position
        
        return None
    
    def get_position(self, signal_id: str) -> Optional[Position]:
        """Get open position by signal_id"""
        return self.positions.get(signal_id)
        
    def get_all_positions(self) -> Dict[str, Position]:
        """Get all open positions"""
        return self.positions.copy()
    
    def get_daily_pnl(self) -> float:
        """Get total daily P&L (realized + unrealized)"""
        return self.daily_pnl
    
    def reset_daily_stats(self):
        """Reset daily counters (call at market open)"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("Daily stats reset")


# ============================================================================
# RISK MANAGER (PRIORITY 5 - MICRO-RISK HARDENING)
# ============================================================================

class RiskManager:
    """
    [v15.3.8] MICRO-RISK HARDENING
    - Per-position max loss (2%)
    - Consecutive loss circuit breaker (3 losses)
    - Stop loss frequency limit (5/day)
    - Risk-reward minimum enforcement (1.5:1)
    """
    
    def __init__(self, 
                 total_capital: float,
                 max_daily_loss_pct: float = 0.05,
                 max_position_size_pct: float = 0.10,
                 max_open_positions: int = 3,
                 max_position_loss_pct: float = 0.02,        # NEW
                 max_consecutive_losses: int = 3,            # NEW
                 max_stop_losses_per_day: int = 5,           # NEW
                 min_risk_reward_ratio: float = 1.5):        # NEW
        
        self.total_capital = total_capital
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_open_positions = max_open_positions
        
        # [NEW] Per-position limits
        self.max_position_loss_pct = max_position_loss_pct
        self.max_position_loss = total_capital * max_position_loss_pct
        
        # [NEW] Circuit breakers
        self.max_consecutive_losses = max_consecutive_losses
        self.max_stop_losses_per_day = max_stop_losses_per_day
        self.min_risk_reward_ratio = min_risk_reward_ratio
        
        # Calculated limits
        self.max_daily_loss = total_capital * max_daily_loss_pct
        self.max_position_size = total_capital * max_position_size_pct
        
        # [NEW] State tracking
        self.consecutive_losses = 0
        self.stop_losses_today = 0
        self.trades_today = 0
        
        # Halt state
        self.trading_halted = False
        self.halt_reason = None
        
        logger.info(
            f"RiskManager initialized: "
            f"Capital=₹{total_capital:,.0f}, "
            f"MaxDailyLoss=₹{self.max_daily_loss:,.0f} ({max_daily_loss_pct*100}%), "
            f"MaxPositionLoss=₹{self.max_position_loss:,.0f} ({max_position_loss_pct*100}%), "
            f"MaxConsecLosses={max_consecutive_losses}, "
            f"MaxStopLosses/day={max_stop_losses_per_day}"
        )
    
    def validate_new_trade(self, 
                          signal_dict: Dict, 
                          pos_manager: PositionManager) -> Tuple[bool, str]:
        """
        [v15.3.8] COMPREHENSIVE PRE-TRADE VALIDATION
        
        Returns:
            (approved, reason)
        """
        
        # =============================================
        # CHECK 1: Trading Halt Status
        # =============================================
        if self.trading_halted:
            return False, f"TRADING_HALTED: {self.halt_reason}"
        
        # =============================================
        # CHECK 2: Daily Loss Limit
        # =============================================
        current_daily_pnl = pos_manager.get_daily_pnl()
        
        if current_daily_pnl <= -self.max_daily_loss:
            self.halt_trading("DAILY_LOSS_LIMIT_EXCEEDED")
            return False, (
                f"DAILY_LOSS_LIMIT_EXCEEDED: "
                f"Loss ₹{abs(current_daily_pnl):,.2f} >= "
                f"Max ₹{self.max_daily_loss:,.2f}"
            )
        
        # =============================================
        # CHECK 3: [NEW] Consecutive Loss Circuit Breaker
        # =============================================
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.halt_trading(f"CIRCUIT_BREAKER_{self.consecutive_losses}_CONSECUTIVE_LOSSES")
            return False, (
                f"CIRCUIT_BREAKER: {self.consecutive_losses} consecutive losses. "
                f"Max allowed: {self.max_consecutive_losses}. Trading halted."
            )
        
        # =============================================
        # CHECK 4: [NEW] Stop Loss Frequency Limit
        # =============================================
        if self.stop_losses_today >= self.max_stop_losses_per_day:
            self.halt_trading(f"STOP_LOSS_LIMIT_{self.stop_losses_today}_HITS")
            return False, (
                f"STOP_LOSS_LIMIT: Hit {self.stop_losses_today} stop losses today. "
                f"Max allowed: {self.max_stop_losses_per_day}"
            )
        
        # =============================================
        # CHECK 5: Max Open Positions
        # =============================================
        open_positions = len(pos_manager.positions)
        
        if open_positions >= self.max_open_positions:
            return False, (
                f"MAX_POSITIONS_REACHED: {open_positions} >= {self.max_open_positions}"
            )
        
        # =============================================
        # CHECK 6: Position Size Limit
        # =============================================
        position_cost = signal_dict['entry_price'] * signal_dict.get('quantity', 75)
        
        if position_cost > self.max_position_size:
            return False, (
                f"POSITION_TOO_LARGE: Cost ₹{position_cost:,.2f} > "
                f"Max ₹{self.max_position_size:,.2f}"
            )
        
        # =============================================
        # CHECK 7: [NEW] Per-Position Risk Validation
        # =============================================
        entry_price = signal_dict['entry_price']
        stop_loss = signal_dict.get('stop_loss', 0)
        quantity = signal_dict.get('quantity', 75)
        
        position_risk = abs(entry_price - stop_loss) * quantity
        
        if position_risk > self.max_position_loss:
            return False, (
                f"POSITION_RISK_TOO_HIGH: Risk ₹{position_risk:,.2f} > "
                f"Max ₹{self.max_position_loss:,.2f}"
            )
        
        # =============================================
        # CHECK 8: [NEW] Risk-Reward Ratio Minimum
        # =============================================
        target = signal_dict.get('target', 0)
        
        if stop_loss > 0 and target > 0:
            position_reward = abs(target - entry_price) * quantity
            
            if position_risk > 0:
                risk_reward_ratio = position_reward / position_risk
                
                if risk_reward_ratio < self.min_risk_reward_ratio:
                    return False, (
                        f"POOR_RISK_REWARD: R:R ratio {risk_reward_ratio:.2f} < "
                        f"Minimum {self.min_risk_reward_ratio}"
                    )
        
        # All checks passed
        return True, "APPROVED"
    
    def should_exit_position(self, 
                            position: Position, 
                            current_price: float) -> Tuple[bool, str]:
        """Check if position should be exited"""
        
        # Stop loss hit
        if position.option_type == 'CE':
            if current_price <= position.stop_loss:
                return True, "STOP_LOSS_HIT"
        else:  # PE
            if current_price >= position.stop_loss:
                return True, "STOP_LOSS_HIT"
        
        # Target hit
        if position.option_type == 'CE':
            if current_price >= position.target:
                return True, "TARGET_HIT"
        else:  # PE
            if current_price <= position.target:
                return True, "TARGET_HIT"
        
        return False, "HOLD"
    
    def record_trade_outcome(self, outcome: str, pnl: float):
        """
        [NEW] Track trade outcomes for circuit breaker logic
        
        Args:
            outcome: "WIN", "LOSS", "STOP_LOSS_HIT", "TARGET_HIT"
            pnl: Realized P&L in rupees
        """
        
        self.trades_today += 1
        
        if outcome in ["LOSS", "STOP_LOSS_HIT"] or pnl < 0:
            # Record loss
            self.consecutive_losses += 1
            
            if outcome == "STOP_LOSS_HIT":
                self.stop_losses_today += 1
            
            logger.warning(
                f"⚠️ Loss recorded: Outcome={outcome}, P&L=₹{pnl:.2f}, "
                f"ConsecLosses={self.consecutive_losses}, "
                f"StopLossesToday={self.stop_losses_today}"
            )
            
            # Check if we hit circuit breaker
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.halt_trading(f"CIRCUIT_BREAKER_{self.consecutive_losses}_LOSSES")
        
        elif outcome in ["WIN", "TARGET_HIT"] or pnl > 0:
            # Record win - reset consecutive losses
            previous_streak = self.consecutive_losses
            self.consecutive_losses = 0
            
            logger.info(
                f"✅ Win recorded: Outcome={outcome}, P&L=₹{pnl:.2f}, "
                f"ConsecLossStreak={previous_streak} → RESET"
            )
    
    def halt_trading(self, reason: str):
        """Halt all trading"""
        self.trading_halted = True
        self.halt_reason = reason
        
        logger.critical(
            f"🛑 TRADING HALTED: {reason}"
        )
    
    def resume_trading(self, override_code: str = None):
        """Resume trading (requires manual override)"""
        if override_code == "MANUAL_OVERRIDE_APPROVED":
            self.trading_halted = False
            self.halt_reason = None
            self.consecutive_losses = 0
            self.stop_losses_today = 0
            
            logger.warning("✅ Trading resumed via manual override")
            return True
        
        return False
    
    def reset_daily_counters(self):
        """Reset daily counters (call at market open)"""
        self.stop_losses_today = 0
        self.trades_today = 0
        # Note: Don't reset consecutive_losses - that persists across days
        
        logger.info("Daily risk counters reset")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Test the enhanced systems
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print("TESTING INDUSTRIAL HARDENING (v15.3.8)")
    print("="*70)
    
    # Test 1: Data Health Checker
    print("\n--- Test 1: Data Staleness (1.5s threshold) ---")
    checker = DataHealthChecker()
    
    # Fresh data
    valid, reason = checker.validate_market_data(
        "NIFTY", 25000, datetime.now(timezone.utc), volume=5000
    )
    print(f"Fresh data: {valid} - {reason}")
    
    # Stale data (2s old)
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    valid, reason = checker.validate_market_data(
        "NIFTY", 25000, stale_time, volume=5000
    )
    print(f"Stale data (2s): {valid} - {reason}")
    
    # Test 2: Risk Manager Circuit Breaker
    print("\n--- Test 2: Consecutive Loss Circuit Breaker ---")
    risk_mgr = RiskManager(total_capital=100000, max_consecutive_losses=3)
    pos_mgr = PositionManager()
    
    # Simulate 3 losses
    for i in range(3):
        risk_mgr.record_trade_outcome("LOSS", -1000)
        print(f"Loss {i+1} recorded. Consecutive: {risk_mgr.consecutive_losses}")
    
    # Try to place 4th trade
    test_signal = {
        'signal_id': 'test_4',
        'entry_price': 100,
        'quantity': 75,
        'stop_loss': 90,
        'target': 120
    }
    
    valid, reason = risk_mgr.validate_new_trade(test_signal, pos_mgr)
    print(f"4th trade after 3 losses: {valid} - {reason}")
    
    # Test 3: Risk-Reward Enforcement
    print("\n--- Test 3: Risk-Reward Ratio Enforcement ---")
    risk_mgr2 = RiskManager(total_capital=100000)
    
    bad_rr_signal = {
        'signal_id': 'bad_rr',
        'entry_price': 100,
        'quantity': 75,
        'stop_loss': 90,  # 10 points risk
        'target': 110     # 10 points reward (1:1)
    }
    
    valid, reason = risk_mgr2.validate_new_trade(bad_rr_signal, pos_mgr)
    print(f"Bad R:R (1:1): {valid} - {reason}")
    
    good_rr_signal = {
        'signal_id': 'good_rr',
        'entry_price': 100,
        'quantity': 75,
        'stop_loss': 90,  # 10 points risk
        'target': 125     # 25 points reward (2.5:1)
    }
    
    valid, reason = risk_mgr2.validate_new_trade(good_rr_signal, pos_mgr)
    print(f"Good R:R (2.5:1): {valid} - {reason}")
    
    print("\n" + "="*70)
    print("✅ Industrial Hardening Tests Complete")
    print("="*70 + "\n")
