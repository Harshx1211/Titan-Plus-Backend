"""
SAFETY SYSTEMS TEST SUITE - v15.3.7
==================================
Automated tests to verify all safety systems work correctly.

Run this BEFORE going live to ensure everything is working.

Usage:
    python test_safety_systems.py

Author: Safety Integration Team
"""

import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("safety_tests")

# Import safety systems
from critical_safety_systems import (
    PositionManager,
    RiskManager,
    DataHealthChecker,
    Position,
    PositionStatus
)


# ============================================================================
# TEST UTILITIES
# ============================================================================

class TestResult:
    """Test result tracker"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []
    
    def add_pass(self, test_name: str):
        self.passed += 1
        logger.info(f"✅ PASS: {test_name}")
    
    def add_fail(self, test_name: str, reason: str):
        self.failed += 1
        self.failures.append((test_name, reason))
        logger.error(f"❌ FAIL: {test_name} - {reason}")
    
    def print_summary(self):
        total = self.passed + self.failed
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed} ({self.passed/total*100:.1f}%)")
        print(f"Failed: {self.failed} ({self.failed/total*100:.1f}%)")
        
        if self.failures:
            print("\nFailed Tests:")
            for name, reason in self.failures:
                print(f"  ❌ {name}: {reason}")
        
        print("="*70)
        
        return self.failed == 0


results = TestResult()


def assert_equal(actual, expected, test_name):
    """Assert equality and record result"""
    if actual == expected:
        results.add_pass(test_name)
        return True
    else:
        results.add_fail(test_name, f"Expected {expected}, got {actual}")
        return False


def assert_true(condition, test_name, reason=""):
    """Assert condition is true"""
    if condition:
        results.add_pass(test_name)
        return True
    else:
        results.add_fail(test_name, reason or "Condition was False")
        return False


def assert_false(condition, test_name, reason=""):
    """Assert condition is false"""
    return assert_true(not condition, test_name, reason or "Condition was True")


# ============================================================================
# TEST SUITE 1: POSITION MANAGER
# ============================================================================

def test_position_manager():
    """Test Position Manager functionality"""
    logger.info("\n" + "="*70)
    logger.info("TEST SUITE 1: POSITION MANAGER")
    logger.info("="*70)
    
    pm = PositionManager()
    
    # Test 1: Initialize empty
    assert_equal(len(pm.positions), 0, "PositionManager initializes empty")
    assert_equal(pm.daily_pnl, 0.0, "Daily P&L starts at zero")
    
    # Test 2: Add position
    signal = {
        'signal_id': 'TEST_001',
        'symbol': 'NIFTY',
        'option_symbol': 'NIFTY25FEB2424500CE',
        'option_type': 'CE',
        'strike': 24500,
        'entry_price': 125.50,
        'quantity': 75,
        'stop_loss': 100.0,
        'target_1': 175.0
    }
    
    position = pm.add_position(signal)
    assert_equal(len(pm.positions), 1, "Position added successfully")
    assert_equal(position.entry_price, 125.50, "Entry price recorded correctly")
    
    # Test 3: Update position price
    pm.update_position('TEST_001', 140.0)
    pos = pm.get_position('TEST_001')
    
    expected_pnl = (140.0 - 125.50) * 75  # ₹1087.50
    assert_equal(pos.current_price, 140.0, "Price updated correctly")
    assert_equal(pos.unrealized_pnl, expected_pnl, f"Unrealized P&L calculated correctly (₹{expected_pnl})")
    
    # Test 4: Track MFE/MAE
    assert_equal(pos.max_profit, expected_pnl, "MFE tracked correctly")
    
    # Update with loss
    pm.update_position('TEST_001', 110.0)
    pos = pm.get_position('TEST_001')
    expected_loss = (110.0 - 125.50) * 75  # -₹1162.50
    
    assert_equal(pos.unrealized_pnl, expected_loss, "Loss calculated correctly")
    assert_true(pos.max_loss < 0, "MAE tracked correctly", f"MAE = ₹{pos.max_loss}")
    
    # Test 5: Close position
    closed_pos = pm.close_position('TEST_001', 135.0, "TARGET_HIT")
    
    assert_equal(closed_pos.exit_price, 135.0, "Exit price recorded")
    assert_equal(closed_pos.status, PositionStatus.CLOSED, "Status changed to CLOSED")
    assert_equal(len(pm.positions), 0, "Position removed from open positions")
    assert_equal(len(pm.closed_positions), 1, "Position moved to closed positions")
    
    expected_realized_pnl = (135.0 - 125.50) * 75  # ₹712.50
    assert_equal(closed_pos.realized_pnl, expected_realized_pnl, f"Realized P&L correct (₹{expected_realized_pnl})")
    
    # Test 6: Summary
    summary = pm.get_summary()
    assert_equal(summary['open_count'], 0, "Summary shows 0 open positions")
    assert_equal(summary['daily_trades'], 1, "Summary shows 1 trade today")
    
    logger.info("Position Manager tests complete")


# ============================================================================
# TEST SUITE 2: RISK MANAGER
# ============================================================================

def test_risk_manager():
    """Test Risk Manager functionality"""
    logger.info("\n" + "="*70)
    logger.info("TEST SUITE 2: RISK MANAGER")
    logger.info("="*70)
    
    rm = RiskManager(
        total_capital=100000,
        max_daily_loss_pct=0.05,
        max_position_size_pct=0.02,
        max_open_positions=3
    )
    
    pm = PositionManager()
    
    # Test 1: Validate limits initialized
    assert_equal(rm.max_daily_loss, 5000, "Daily loss limit set correctly")
    assert_equal(rm.max_position_size, 2000, "Position size limit set correctly")
    assert_equal(rm.max_open_positions, 3, "Max positions set correctly")
    
    # Test 2: Accept first valid trade
    signal = {
        'symbol': 'NIFTY',
        'entry_price': 125.0,
        'quantity': 15,  # ₹1875 total (under ₹2000 limit)
        'stop_loss': 100.0
    }
    
    can_trade, reason = rm.validate_new_trade(signal, pm)
    assert_true(can_trade, "First trade accepted", reason)
    
    # Add position to manager
    pm.add_position({
        'signal_id': 'TEST_001',
        'symbol': 'NIFTY',
        'option_symbol': 'NIFTY25FEB2424500CE',
        'option_type': 'CE',
        'strike': 24500,
        'entry_price': 125.0,
        'quantity': 15,
        'stop_loss': 100.0,
        'target_1': 175.0
    })
    
    # Test 3: Reject duplicate underlying
    can_trade, reason = rm.validate_new_trade(signal, pm)
    assert_false(can_trade, "Duplicate underlying rejected", reason)
    assert_true("DUPLICATE_EXPOSURE" in reason, "Correct rejection reason", reason)
    
    # Test 4: Max positions limit
    # Add 2 more positions (different underlyings)
    for i, symbol in enumerate(['BANKNIFTY', 'SENSEX'], start=2):
        pm.add_position({
            'signal_id': f'TEST_00{i}',
            'symbol': symbol,
            'option_symbol': f'{symbol}25FEB2424500CE',
            'option_type': 'CE',
            'strike': 24500,
            'entry_price': 125.0,
            'quantity': 15,
            'stop_loss': 100.0,
            'target_1': 175.0
        })
    
    # Try to add 4th position
    signal_4 = {
        'symbol': 'FINNIFTY',
        'entry_price': 125.0,
        'quantity': 15,
        'stop_loss': 100.0
    }
    
    can_trade, reason = rm.validate_new_trade(signal_4, pm)
    assert_false(can_trade, "Max positions limit enforced", reason)
    assert_true("MAX_POSITIONS_REACHED" in reason, "Correct rejection reason", reason)
    
    # Test 5: Position size limit
    pm_empty = PositionManager()
    signal_large = {
        'symbol': 'NIFTY',
        'entry_price': 250.0,
        'quantity': 20,  # ₹5000 total (exceeds ₹2000 limit)
        'stop_loss': 200.0
    }
    
    can_trade, reason = rm.validate_new_trade(signal_large, pm_empty)
    assert_false(can_trade, "Position size limit enforced", reason)
    assert_true("POSITION_TOO_LARGE" in reason, "Correct rejection reason", reason)
    
    # Test 6: Daily loss limit
    # Simulate heavy losses
    pm_loss = PositionManager()
    pm_loss.daily_pnl = -6000  # Exceeds -₹5000 limit
    
    signal_normal = {
        'symbol': 'NIFTY',
        'entry_price': 125.0,
        'quantity': 15,
        'stop_loss': 100.0
    }
    
    can_trade, reason = rm.validate_new_trade(signal_normal, pm_loss)
    assert_false(can_trade, "Daily loss limit enforced", reason)
    assert_true("DAILY_LOSS_LIMIT" in reason, "Correct rejection reason", reason)
    assert_true(rm.trading_halted, "Trading automatically halted", "")
    
    # Test 7: Exit conditions - Stop Loss
    position = Position(
        signal_id='EXIT_TEST',
        symbol='NIFTY25FEB2424500CE',
        underlying='NIFTY',
        option_type='CE',
        strike=24500,
        entry_price=125.0,
        quantity=75,
        entry_time=datetime.now(timezone.utc),
        stop_loss=100.0,
        target=175.0
    )
    
    should_exit, reason = rm.should_exit_position(position, 98.0)
    assert_true(should_exit, "Stop loss exit triggered", reason)
    assert_true("STOP_LOSS" in reason, "Correct exit reason", reason)
    
    # Test 8: Exit conditions - Target
    should_exit, reason = rm.should_exit_position(position, 176.0)
    assert_true(should_exit, "Target hit exit triggered", reason)
    assert_true("TARGET" in reason, "Correct exit reason", reason)
    
    # Test 9: Exit conditions - Time based
    old_position = Position(
        signal_id='OLD_TEST',
        symbol='NIFTY25FEB2424500CE',
        underlying='NIFTY',
        option_type='CE',
        strike=24500,
        entry_price=125.0,
        quantity=75,
        entry_time=datetime.now(timezone.utc) - timedelta(hours=7),  # 7 hours ago
        stop_loss=100.0,
        target=175.0
    )
    
    should_exit, reason = rm.should_exit_position(old_position, 130.0)
    assert_true(should_exit, "Time-based exit triggered", reason)
    assert_true("TIME_BASED" in reason, "Correct exit reason", reason)
    
    logger.info("Risk Manager tests complete")


# ============================================================================
# TEST SUITE 3: DATA HEALTH CHECKER
# ============================================================================

def test_data_health_checker():
    """Test Data Health Checker functionality"""
    logger.info("\n" + "="*70)
    logger.info("TEST SUITE 3: DATA HEALTH CHECKER")
    logger.info("="*70)
    
    dhc = DataHealthChecker()
    
    # Test 1: Accept fresh data
    is_valid, reason = dhc.validate_market_data(
        symbol='NIFTY',
        price=24500.0,
        timestamp=datetime.now(timezone.utc)
    )
    assert_true(is_valid, "Fresh data accepted", reason)
    
    # Test 2: Reject stale data
    old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=10)
    is_valid, reason = dhc.validate_market_data(
        symbol='NIFTY',
        price=24500.0,
        timestamp=old_timestamp
    )
    assert_false(is_valid, "Stale data rejected", reason)
    assert_true("STALE_DATA" in reason, "Correct rejection reason", reason)
    
    # Test 3: Reject invalid price
    is_valid, reason = dhc.validate_market_data(
        symbol='NIFTY',
        price=0.0,
        timestamp=datetime.now(timezone.utc)
    )
    assert_false(is_valid, "Zero price rejected", reason)
    assert_true("INVALID_PRICE" in reason, "Correct rejection reason", reason)
    
    # Test 4: Reject negative price
    is_valid, reason = dhc.validate_market_data(
        symbol='NIFTY',
        price=-100.0,
        timestamp=datetime.now(timezone.utc)
    )
    assert_false(is_valid, "Negative price rejected", reason)
    
    # Test 5: Warn on large price move
    # First establish baseline
    dhc.validate_market_data('NIFTY', 24500.0, datetime.now(timezone.utc))
    
    # Then large move (>2%)
    is_valid, reason = dhc.validate_market_data(
        symbol='NIFTY',
        price=25000.0,  # ~2% move
        timestamp=datetime.now(timezone.utc)
    )
    # Should still be valid but log warning
    
    # Test 6: WebSocket health check
    is_healthy, reason = dhc.check_websocket_health(None)
    assert_false(is_healthy, "No messages detected", reason)
    
    recent_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    is_healthy, reason = dhc.check_websocket_health(recent_time)
    assert_true(is_healthy, "Recent message accepted", reason)
    
    old_time = datetime.now(timezone.utc) - timedelta(seconds=15)
    is_healthy, reason = dhc.check_websocket_health(old_time)
    assert_false(is_healthy, "Old message rejected", reason)
    assert_true("STALE" in reason, "Correct rejection reason", reason)
    
    logger.info("Data Health Checker tests complete")


# ============================================================================
# TEST SUITE 4: INTEGRATION TESTS
# ============================================================================

def test_integration():
    """Test integrated workflow"""
    logger.info("\n" + "="*70)
    logger.info("TEST SUITE 4: INTEGRATION TESTS")
    logger.info("="*70)
    
    # Create all managers
    pm = PositionManager()
    rm = RiskManager(total_capital=100000)
    dhc = DataHealthChecker()
    
    # Test 1: Complete trade lifecycle
    # Step 1: Validate data
    is_valid, _ = dhc.validate_market_data(
        'NIFTY', 24500.0, datetime.now(timezone.utc)
    )
    assert_true(is_valid, "Integration Test 1: Data validation passed", "")
    
    # Step 2: Risk check
    signal = {
        'signal_id': 'INTEG_001',
        'symbol': 'NIFTY',
        'option_symbol': 'NIFTY25FEB2424500CE',
        'option_type': 'CE',
        'strike': 24500,
        'entry_price': 125.0,
        'quantity': 75,
        'stop_loss': 100.0,
        'target_1': 175.0
    }
    
    can_trade, _ = rm.validate_new_trade(signal, pm)
    assert_true(can_trade, "Integration Test 1: Risk check passed", "")
    
    # Step 3: Enter position
    position = pm.add_position(signal)
    assert_equal(len(pm.positions), 1, "Integration Test 1: Position opened", "")
    
    # Step 4: Update price
    pm.update_position('INTEG_001', 140.0)
    
    # Step 5: Check exit (should not exit yet)
    should_exit, _ = rm.should_exit_position(position, 140.0)
    assert_false(should_exit, "Integration Test 1: Position holding", "")
    
    # Step 6: Hit target
    pm.update_position('INTEG_001', 176.0)
    should_exit, reason = rm.should_exit_position(position, 176.0)
    assert_true(should_exit, "Integration Test 1: Target hit", reason)
    
    # Step 7: Close position
    closed = pm.close_position('INTEG_001', 176.0, reason)
    assert_equal(closed.status, PositionStatus.CLOSED, "Integration Test 1: Position closed", "")
    assert_true(closed.realized_pnl > 0, "Integration Test 1: Profitable trade", f"P&L: ₹{closed.realized_pnl}")
    
    logger.info("Integration tests complete")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*70)
    print("SAFETY SYSTEMS AUTOMATED TEST SUITE")
    print("Version: v15.3.7")
    print("="*70)
    
    try:
        # Run all test suites
        test_position_manager()
        test_risk_manager()
        test_data_health_checker()
        test_integration()
        
        # Print summary
        success = results.print_summary()
        
        if success:
            print("\n✅ ALL TESTS PASSED - System is ready for paper trading")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED - Fix issues before deployment")
            return 1
    
    except Exception as e:
        logger.error(f"Test suite crashed: {e}", exc_info=True)
        print(f"\n❌ TEST SUITE CRASHED: {e}")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
