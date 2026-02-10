"""
Titan Plus Execution Engine
============================
Professional order execution and position management.

Features:
- Smart order placement with retry logic
- Stop loss monitoring and auto-exit
- Position tracking
- Slippage monitoring
- Margin checking
- Emergency exit procedures

Author: Titan Plus Team
Version: 1.0.0
Date: 2026-02-08
"""

import time
import logging
import threading
from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger("execution")


class OrderStatus(Enum):
    """Order lifecycle states."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ExitReason(Enum):
    """Reasons for position exit."""
    TARGET_HIT = "TARGET_HIT"
    SL_HIT = "SL_HIT"
    TRAILING_SL = "TRAILING_SL"
    EOD_SQUARE_OFF = "EOD_SQUARE_OFF"
    RISK_LIMIT = "RISK_LIMIT"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class Order:
    """Represents a single order with full lifecycle tracking."""
    
    order_id: str
    signal_id: str
    symbol: str
    quantity: int
    
    # Order details
    order_type: str  # LIMIT, MARKET, SL-M
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    product_type: str = "MIS"  # MIS or NRML
    transaction_type: str = "BUY"  # BUY or SELL
    
    # Status tracking
    status: OrderStatus = OrderStatus.PENDING
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Fill details
    filled_price: Optional[float] = None
    filled_quantity: int = 0
    average_price: Optional[float] = None
    
    # Bracket orders
    sl_order_id: Optional[str] = None
    target_order_id: Optional[str] = None
    
    # Performance
    pnl: float = 0.0
    slippage: float = 0.0
    
    # Metadata
    exchange_order_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class Position:
    """Represents an open position."""
    
    def __init__(
        self,
        symbol: str,
        entry_order: Order,
        sl_price: float,
        target_price: float
    ):
        self.symbol = symbol
        self.entry_order = entry_order
        self.quantity = entry_order.filled_quantity
        self.entry_price = entry_order.filled_price
        
        # Exit parameters
        self.sl_price = sl_price
        self.target_price = target_price
        self.current_sl = sl_price  # For trailing SL
        
        # Exit orders
        self.sl_order: Optional[Order] = None
        self.target_order: Optional[Order] = None
        
        # Performance tracking
        self.unrealized_pnl = 0.0
        self.mfe = 0.0  # Maximum Favorable Excursion
        self.mae = 0.0  # Maximum Adverse Excursion
        
        # Timing
        self.entry_time = entry_order.filled_at
        self.exit_time: Optional[datetime] = None
        self.exit_reason: Optional[ExitReason] = None
        
        # Metadata
        self.is_open = True
        self.realized_pnl = 0.0


class ExecutionEngine:
    """
    Professional order execution and management.
    """
    
    def __init__(self, broker_api, risk_manager, db_manager=None):
        """
        Initialize execution engine.
        
        Args:
            broker_api: Broker API instance (Shoonya, Groww, etc.)
            risk_manager: Risk management instance
            db_manager: Database manager for logging
        """
        self.broker = broker_api
        self.risk = risk_manager
        self.db = db_manager
        
        # Active tracking
        self.active_orders: Dict[str, Order] = {}
        self.active_positions: Dict[str, Position] = {}
        
        # Execution settings
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 2  # seconds
        self.ORDER_TIMEOUT = 30  # seconds
        self.SLIPPAGE_TOLERANCE = 10  # points
        
        # Monitoring
        self.monitor_thread: Optional[threading.Thread] = None
        self.is_monitoring = False
        
        # Statistics
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_rejected': 0,
            'total_slippage': 0.0,
            'emergency_exits': 0
        }
    
    def start_monitoring(self):
        """Start position monitoring thread."""
        if self.is_monitoring:
            logger.warning("Monitoring already active")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_positions,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Position monitoring started")
    
    def stop_monitoring(self):
        """Stop position monitoring."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Position monitoring stopped")
    
    def execute_signal(self, signal) -> Optional[str]:
        """
        Execute a trading signal with full lifecycle management.
        
        Args:
            signal: TradeSignal object with entry, SL, target
        
        Returns:
            order_id if successful, None if failed
        """
        logger.info(f"Executing signal: {signal.option_symbol}")
        
        # Pre-execution checks
        if not self._pre_execution_checks(signal):
            logger.warning("Pre-execution checks failed")
            return None
        
        # Calculate position size
        lots = self.risk.calculate_position_size(signal)
        if lots == 0:
            logger.warning("Position sizing returned 0 lots")
            return None
        
        quantity = lots * 75  # Assuming lot size 75
        
        # Create order object
        order = Order(
            order_id=self._generate_order_id(),
            signal_id=getattr(signal, 'decision_id', 'UNKNOWN'),
            symbol=signal.option_symbol,
            quantity=quantity,
            order_type="LIMIT",
            price=signal.premium_entry,
            product_type="MIS",
            transaction_type="BUY"
        )
        
        # Place entry order
        success = self._place_order(order)
        if not success:
            logger.error("Failed to place entry order")
            return None
        
        # Monitor order fill
        filled = self._wait_for_fill(order, timeout=self.ORDER_TIMEOUT)
        if not filled:
            logger.warning(f"Order {order.order_id} not filled, cancelling")
            self._cancel_order(order.order_id)
            return None
        
        # Calculate slippage
        expected = signal.premium_entry
        actual = order.filled_price
        order.slippage = actual - expected
        self.stats['total_slippage'] += abs(order.slippage)
        
        logger.info(
            f"Order filled: {order.order_id} @ {actual:.2f} "
            f"(slippage: {order.slippage:+.2f})"
        )
        
        # Create position
        position = Position(
            symbol=signal.option_symbol,
            entry_order=order,
            sl_price=signal.premium_sl,
            target_price=signal.premium_target
        )
        
        # Place bracket orders
        self._place_bracket_orders(position, signal)
        
        # Track position
        self.active_positions[signal.option_symbol] = position
        
        # Update risk manager
        self.risk.add_position(signal.option_symbol, lots, actual)
        
        # Log to database
        self._log_execution(order, signal)
        
        return order.order_id
    
    def _pre_execution_checks(self, signal) -> bool:
        """Comprehensive pre-execution validation."""
        
        # 1. Market hours check
        if not self._is_market_open():
            logger.warning("Market is closed")
            return False
        
        # 2. Risk limits
        if not self.risk.can_take_position(signal):
            logger.warning("Risk limits exceeded")
            return False
        
        # 3. Margin check
        required_margin = self._calculate_required_margin(signal)
        try:
            available_margin = self.broker.get_available_margin()
            if available_margin < required_margin:
                logger.warning(
                    f"Insufficient margin: need ₹{required_margin:.2f}, "
                    f"have ₹{available_margin:.2f}"
                )
                return False
        except Exception as e:
            logger.error(f"Margin check failed: {e}")
            return False
        
        # 4. Symbol verification and liquidity
        if not self._verify_liquidity(signal.option_symbol):
            logger.warning(f"Low liquidity: {signal.option_symbol}")
            return False
        
        # 5. No duplicate positions
        if signal.option_symbol in self.active_positions:
            logger.warning(f"Position already exists: {signal.option_symbol}")
            return False
        
        return True
    
    def _place_order(self, order: Order) -> bool:
        """
        Place order with retry logic.
        
        Returns:
            True if submitted successfully
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(
                    f"Placing order (attempt {attempt+1}/{self.MAX_RETRIES}): "
                    f"{order.transaction_type} {order.quantity} {order.symbol} @ {order.price}"
                )
                
                # Call broker API
                response = self.broker.place_order(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    order_type=order.order_type,
                    price=order.price,
                    trigger_price=order.trigger_price,
                    product_type=order.product_type,
                    transaction_type=order.transaction_type
                )
                
                # Parse response
                if response and response.get('status') == 'success':
                    order.exchange_order_id = response.get('order_id')
                    order.status = OrderStatus.SUBMITTED
                    order.submitted_at = datetime.now()
                    
                    # Track
                    self.active_orders[order.order_id] = order
                    self.stats['orders_placed'] += 1
                    
                    logger.info(f"Order submitted: {order.exchange_order_id}")
                    return True
                else:
                    error = response.get('message', 'Unknown error')
                    logger.error(f"Order placement failed: {error}")
                    order.rejection_reason = error
                    
            except Exception as e:
                logger.error(f"Order placement exception: {e}")
                order.rejection_reason = str(e)
            
            # Retry delay
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self.RETRY_DELAY)
        
        # All retries failed
        order.status = OrderStatus.FAILED
        self.stats['orders_rejected'] += 1
        return False
    
    def _wait_for_fill(self, order: Order, timeout: int = 30) -> bool:
        """
        Wait for order to be filled.
        
        Returns:
            True if filled within timeout
        """
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                # Get order status from broker
                status_response = self.broker.get_order_status(order.exchange_order_id)
                
                status = status_response.get('status', '').upper()
                
                if status in ['COMPLETE', 'FILLED']:
                    # Update order with fill details
                    order.status = OrderStatus.FILLED
                    order.filled_at = datetime.now()
                    order.filled_quantity = status_response.get('filled_qty', order.quantity)
                    order.filled_price = status_response.get('average_price', order.price)
                    order.average_price = order.filled_price
                    
                    self.stats['orders_filled'] += 1
                    return True
                    
                elif status in ['REJECTED', 'CANCELLED']:
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = status_response.get('reason', 'Unknown')
                    return False
                
                # Still pending, wait
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                time.sleep(1)
        
        # Timeout
        logger.warning(f"Order fill timeout: {order.order_id}")
        return False
    
    def _place_bracket_orders(self, position: Position, signal):
        """Place stop loss and target orders."""
        
        try:
            # Stop Loss Order
            sl_order = Order(
                order_id=self._generate_order_id(),
                signal_id=position.entry_order.signal_id,
                symbol=position.symbol,
                quantity=position.quantity,
                order_type="SL-M",  # Stop Loss Market
                trigger_price=position.sl_price,
                product_type="MIS",
                transaction_type="SELL"
            )
            
            if self._place_order(sl_order):
                position.sl_order = sl_order
                logger.info(f"SL order placed: {sl_order.exchange_order_id} @ {position.sl_price}")
            else:
                logger.error("Failed to place SL order - MANUAL INTERVENTION REQUIRED")
                self._emergency_exit(position)
                return
            
            # Target Order
            target_order = Order(
                order_id=self._generate_order_id(),
                signal_id=position.entry_order.signal_id,
                symbol=position.symbol,
                quantity=position.quantity,
                order_type="LIMIT",
                price=position.target_price,
                product_type="MIS",
                transaction_type="SELL"
            )
            
            if self._place_order(target_order):
                position.target_order = target_order
                logger.info(f"Target order placed: {target_order.exchange_order_id} @ {position.target_price}")
            else:
                logger.warning("Failed to place target order (SL active)")
            
        except Exception as e:
            logger.critical(f"Bracket order failure: {e}")
            self._emergency_exit(position)
    
    def _monitor_positions(self):
        """
        Continuously monitor all active positions.
        Runs in separate thread.
        """
        logger.info("Position monitoring loop started")
        
        while self.is_monitoring:
            try:
                # Check each position
                for symbol, position in list(self.active_positions.items()):
                    if not position.is_open:
                        continue
                    
                    # Update unrealized P&L
                    self._update_position_pnl(position)
                    
                    # Check if SL hit
                    if position.sl_order and position.sl_order.status == OrderStatus.FILLED:
                        self._handle_position_exit(position, ExitReason.SL_HIT)
                        continue
                    
                    # Check if target hit
                    if position.target_order and position.target_order.status == OrderStatus.FILLED:
                        self._handle_position_exit(position, ExitReason.TARGET_HIT)
                        continue
                    
                    # Check trailing SL (if implemented)
                    # self._check_trailing_sl(position)
                    
                    # EOD square off check (3:15 PM)
                    now = datetime.now()
                    if now.hour == 15 and now.minute >= 15:
                        logger.warning(f"EOD square off: {symbol}")
                        self._exit_position_market(position, ExitReason.EOD_SQUARE_OFF)
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
                time.sleep(5)
    
    def _update_position_pnl(self, position: Position):
        """Update position unrealized P&L and MFE/MAE."""
        try:
            # Get current market price
            quote = self.broker.get_quote(position.symbol)
            ltp = quote.get('ltp', position.entry_price)
            
            # Calculate unrealized P&L
            entry_value = position.entry_price * position.quantity
            current_value = ltp * position.quantity
            position.unrealized_pnl = current_value - entry_value
            
            # Update MFE (best profit so far)
            if position.unrealized_pnl > position.mfe:
                position.mfe = position.unrealized_pnl
            
            # Update MAE (worst loss so far)
            if position.unrealized_pnl < position.mae:
                position.mae = position.unrealized_pnl
            
        except Exception as e:
            logger.error(f"Error updating position P&L: {e}")
    
    def _handle_position_exit(self, position: Position, reason: ExitReason):
        """Handle position exit and cleanup."""
        
        logger.info(f"Position exited: {position.symbol} - {reason.value}")
        
        # Determine which order was filled
        if reason == ExitReason.SL_HIT:
            exit_order = position.sl_order
        elif reason == ExitReason.TARGET_HIT:
            exit_order = position.target_order
        else:
            exit_order = None
        
        # Calculate realized P&L
        if exit_order and exit_order.filled_price:
            entry_value = position.entry_price * position.quantity
            exit_value = exit_order.filled_price * position.quantity
            position.realized_pnl = exit_value - entry_value
        else:
            position.realized_pnl = position.unrealized_pnl
        
        # Update position
        position.is_open = False
        position.exit_time = datetime.now()
        position.exit_reason = reason
        
        # Cancel pending bracket order
        if reason == ExitReason.SL_HIT and position.target_order:
            self._cancel_order(position.target_order.order_id)
        elif reason == ExitReason.TARGET_HIT and position.sl_order:
            self._cancel_order(position.sl_order.order_id)
        
        # Remove from active
        del self.active_positions[position.symbol]
        
        # Update risk manager
        self.risk.remove_position(position.symbol, position.realized_pnl)
        
        # Log outcome
        self._log_position_exit(position)
        
        logger.info(f"Position P&L: ₹{position.realized_pnl:.2f}")
    
    def _exit_position_market(self, position: Position, reason: ExitReason):
        """Exit position with market order (emergency/EOD)."""
        
        logger.warning(f"Market exit triggered: {position.symbol} - {reason.value}")
        
        # Cancel pending orders
        if position.sl_order:
            self._cancel_order(position.sl_order.order_id)
        if position.target_order:
            self._cancel_order(position.target_order.order_id)
        
        # Place market sell order
        exit_order = Order(
            order_id=self._generate_order_id(),
            signal_id=position.entry_order.signal_id,
            symbol=position.symbol,
            quantity=position.quantity,
            order_type="MARKET",
            product_type="MIS",
            transaction_type="SELL"
        )
        
        if self._place_order(exit_order):
            # Wait for fill (market orders fill fast)
            if self._wait_for_fill(exit_order, timeout=10):
                position.exit_time = datetime.now()
                position.exit_reason = reason
                position.is_open = False
                
                # Calculate P&L
                entry_value = position.entry_price * position.quantity
                exit_value = exit_order.filled_price * position.quantity
                position.realized_pnl = exit_value - entry_value
                
                # Remove from active
                del self.active_positions[position.symbol]
                
                # Update risk manager
                self.risk.remove_position(position.symbol, position.realized_pnl)
                
                logger.info(f"Market exit successful: P&L = ₹{position.realized_pnl:.2f}")
            else:
                logger.critical(f"Market exit fill timeout: {position.symbol}")
        else:
            logger.critical(f"Market exit order failed: {position.symbol}")
    
    def _emergency_exit(self, position: Position):
        """Emergency exit when bracket orders fail."""
        logger.critical(f"EMERGENCY EXIT: {position.symbol}")
        self.stats['emergency_exits'] += 1
        self._exit_position_market(position, ExitReason.EMERGENCY)
    
    def _cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            order = self.active_orders.get(order_id)
            if not order:
                return False
            
            response = self.broker.cancel_order(order.exchange_order_id)
            
            if response and response.get('status') == 'success':
                order.status = OrderStatus.CANCELLED
                logger.info(f"Order cancelled: {order.exchange_order_id}")
                return True
            else:
                logger.warning(f"Cancel failed: {order.exchange_order_id}")
                return False
                
        except Exception as e:
            logger.error(f"Cancel error: {e}")
            return False
    
    def _calculate_required_margin(self, signal) -> float:
        """Estimate required margin for position."""
        # Simplified - actual margin varies by broker
        premium = signal.premium_entry
        lots = 1  # Conservative estimate
        lot_size = 75
        
        # Typically need ~20% of contract value as margin for options
        contract_value = premium * lots * lot_size
        margin = contract_value * 0.20
        
        return margin
    
    def _verify_liquidity(self, symbol: str) -> bool:
        """Check if option has sufficient liquidity."""
        try:
            quote = self.broker.get_quote(symbol)
            
            # Check bid-ask spread
            bid = quote.get('bid', 0)
            ask = quote.get('ask', 0)
            if ask == 0 or bid == 0:
                return False
            
            spread_pct = ((ask - bid) / bid) * 100
            if spread_pct > 5:  # 5% max spread
                logger.warning(f"Wide spread: {spread_pct:.2f}%")
                return False
            
            # Check OI
            oi = quote.get('oi', 0)
            if oi < 1000:
                logger.warning(f"Low OI: {oi}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Liquidity check failed: {e}")
            return False
    
    def _is_market_open(self) -> bool:
        """Check if market is open."""
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:
            return False
        
        # Market hours: 9:15 AM - 3:30 PM
        market_start = now.replace(hour=9, minute=15, second=0)
        market_end = now.replace(hour=15, minute=30, second=0)
        
        return market_start <= now <= market_end
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        return f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    def _log_execution(self, order: Order, signal):
        """Log trade execution to database."""
        if not self.db:
            return
        
        try:
            self.db.log_trade_execution({
                'order_id': order.order_id,
                'signal_id': order.signal_id,
                'symbol': order.symbol,
                'quantity': order.quantity,
                'entry_price': order.filled_price,
                'slippage': order.slippage,
                'timestamp': order.filled_at,
                'status': order.status.value
            })
        except Exception as e:
            logger.error(f"Failed to log execution: {e}")
    
    def _log_position_exit(self, position: Position):
        """Log position exit to database."""
        if not self.db:
            return
        
        try:
            self.db.log_trade_exit({
                'symbol': position.symbol,
                'entry_price': position.entry_price,
                'exit_price': position.sl_order.filled_price if position.sl_order else 0,
                'quantity': position.quantity,
                'realized_pnl': position.realized_pnl,
                'mfe': position.mfe,
                'mae': position.mae,
                'exit_reason': position.exit_reason.value if position.exit_reason else 'UNKNOWN',
                'duration_seconds': (position.exit_time - position.entry_time).total_seconds() if position.exit_time else 0
            })
        except Exception as e:
            logger.error(f"Failed to log exit: {e}")
    
    def get_statistics(self) -> Dict:
        """Get execution statistics."""
        return {
            **self.stats,
            'active_positions': len(self.active_positions),
            'active_orders': len(self.active_orders),
            'fill_rate': (self.stats['orders_filled'] / self.stats['orders_placed'] * 100) 
                        if self.stats['orders_placed'] > 0 else 0,
            'avg_slippage': (self.stats['total_slippage'] / self.stats['orders_filled'])
                           if self.stats['orders_filled'] > 0 else 0
        }


if __name__ == "__main__":
    # Example usage (requires actual broker API)
    logging.basicConfig(level=logging.INFO)
    
    print("Execution Engine v1.0.0")
    print("Note: Requires broker API integration to run")
