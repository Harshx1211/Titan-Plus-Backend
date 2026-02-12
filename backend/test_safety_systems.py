"""
Automated Test Suite for Helios Safety Systems (v15.3.7)
Tests: DataHealthChecker, RiskManager, PositionManager
"""

import unittest
from datetime import datetime, timezone, timedelta
from critical_safety_systems import (
    DataHealthChecker, 
    RiskManager, 
    PositionManager, 
    PositionStatus
)

class TestSafetySystems(unittest.TestCase):
    
    def setUp(self):
        self.data_health = DataHealthChecker()
        self.risk_manager = RiskManager(
            total_capital=100000,
            max_daily_loss_pct=0.05,
            max_position_size_pct=0.1,
            max_open_positions=3
        )
        self.pos_manager = PositionManager()

    # --- DataHealthChecker Tests ---
    
    def test_data_freshness_pass(self):
        """Pass if data is recent (within 5s)"""
        now = datetime.now(timezone.utc)
        valid, reason = self.data_health.validate_market_data("NIFTY", 22000, now)
        self.assertTrue(valid)
        self.assertEqual(reason, "VALID")

    def test_data_stale_fail(self):
        """Fail if data is older than 5s"""
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        valid, reason = self.data_health.validate_market_data("NIFTY", 22000, stale_time)
        self.assertFalse(valid)
        self.assertIn("STALE_DATA", reason)

    def test_price_move_sanity_warning(self):
        """Should log warning but remain VALID unless it's a hard rejection (implied)"""
        now = datetime.now(timezone.utc)
        # First price
        self.data_health.validate_market_data("NIFTY", 20000, now)
        # 5% move (limit is 2%)
        valid, reason = self.data_health.validate_market_data("NIFTY", 21000, now)
        # Note: Current implementation logs warning but returns VALID for price move
        self.assertTrue(valid)

    # --- RiskManager Tests ---

    def test_daily_loss_limit(self):
        """Fail if daily loss limit (5k) hit"""
        # Simulate a 6k loss
        mock_signal = {'signal_id': 'lost_1', 'entry_price': 100, 'quantity': 100}
        pos = self.pos_manager.add_position(mock_signal)
        self.pos_manager.close_position(pos.signal_id, 40, "LOSS") # -6000 loss
        
        # New trade should fail
        valid, reason = self.risk_manager.validate_new_trade(mock_signal, self.pos_manager)
        self.assertFalse(valid)
        self.assertEqual(reason, "DAILY_LOSS_LIMIT_EXCEEDED")
        self.assertTrue(self.risk_manager.trading_halted)

    def test_max_positions_limit(self):
        """Fail if 4th position opened (limit is 3)"""
        for i in range(3):
            sig = {'signal_id': f's_{i}', 'symbol': f'SYM_{i}', 'entry_price': 100}
            self.pos_manager.add_position(sig)
        
        new_sig = {'signal_id': 's_new', 'symbol': 'SYM_NEW', 'entry_price': 100}
        valid, reason = self.risk_manager.validate_new_trade(new_sig, self.pos_manager)
        self.assertFalse(valid)
        self.assertIn("MAX_POSITIONS_REACHED", reason)

    def test_position_size_limit(self):
        """Fail if position cost > 10% of capital (10k)"""
        large_sig = {'signal_id': 'large', 'entry_price': 200, 'quantity': 100} # 20k
        valid, reason = self.risk_manager.validate_new_trade(large_sig, self.pos_manager)
        self.assertFalse(valid)
        self.assertIn("POSITION_TOO_LARGE", reason)

    # --- PositionManager Tests ---

    def test_pnl_calculation(self):
        """Verify unrealized and realized P&L"""
        sig = {'signal_id': 'pnl_test', 'symbol': 'TEST', 'entry_price': 100, 'quantity': 100}
        self.pos_manager.add_position(sig)
        
        # Unrealized
        self.pos_manager.update_position('pnl_test', 110)
        self.assertEqual(self.pos_manager.daily_pnl, 1000)
        
        # Realized
        self.pos_manager.close_position('pnl_test', 115, "TEST_EXIT")
        self.assertEqual(self.pos_manager.total_pnl, 1500)
        self.assertEqual(self.pos_manager.daily_pnl, 1500)

    def test_exit_evaluation(self):
        """Verify RiskManager identifies SL and Target hits"""
        pos = self.pos_manager.add_position({
            'signal_id': 'exit_test', 'symbol': 'TEST', 
            'entry_price': 100, 'option_type': 'CE',
            'stop_loss': 80, 'target': 150
        })
        
        # SL Hit
        should_exit, reason = self.risk_manager.should_exit_position(pos, 75)
        self.assertTrue(should_exit)
        self.assertEqual(reason, "STOP_LOSS_HIT")
        
        # Target Hit
        should_exit, reason = self.risk_manager.should_exit_position(pos, 160)
        self.assertTrue(should_exit)
        self.assertEqual(reason, "TARGET_HIT")

if __name__ == '__main__':
    unittest.main()
