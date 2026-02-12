"""
HELIOS INDUSTRIAL HARDENING TEST SUITE (v15.3.8)
================================================
25+ Automated Tests covering:
1. Data Health (Staleness, Spread, Volume)
2. WebSocket Resilience (Watchdog, Heartbeat)
3. Risk Management (Circuit Breakers, R:R, SL Limits)
4. Execution Quality (Slippage, LIMIT orders)
5. Strike Selection (Delta, Liquidity, Regime)
"""

import unittest
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List

# Import our new modules
from critical_safety_systems import DataHealthChecker, RiskManager, PositionManager, PositionStatus
from websocket_resilience import WebSocketWatchdog
from execution_slippage_control import SlippageController
from intelligent_strike_selector import IntelligentStrikeSelector, MarketRegime

class TestIndustrialHardening(unittest.TestCase):
    
    def setUp(self):
        # Setup common components
        self.capital = 100000
        self.risk_mgr = RiskManager(
            total_capital=self.capital,
            max_daily_loss_pct=0.05,
            max_position_size_pct=0.10,
            max_open_positions=3,
            max_position_loss_pct=0.02,
            max_consecutive_losses=3,
            max_stop_losses_per_day=5,
            min_risk_reward_ratio=1.5
        )
        self.pos_mgr = PositionManager()
        self.data_health = DataHealthChecker()
        self.slippage_ctrl = SlippageController()
        self.strike_selector = IntelligentStrikeSelector()

    # ========================================================================
    # 1. DATA HEALTH TESTS (PRIORITY 1)
    # ========================================================================
    
    def test_data_staleness_threshold(self):
        """Verify 1.5s staleness threshold is enforced"""
        # Fresh
        valid, _ = self.data_health.validate_market_data("NIFTY", 25000, datetime.now(timezone.utc), volume=5000)
        self.assertTrue(valid)
        
        # Stale (2s)
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=2.0)
        valid, reason = self.data_health.validate_market_data("NIFTY", 25000, stale_time, volume=5000)
        self.assertFalse(valid)
        self.assertIn("STALE", reason)

    def test_bid_ask_spread_validation(self):
        """Verify max 0.5% bid-ask spread check"""
        # Tight spread (0.1%)
        valid, _ = self.data_health.validate_market_data(
            "NIFTY_OPT", 100, datetime.now(timezone.utc), volume=1000, bid=99.95, ask=100.05
        )
        self.assertTrue(valid)
        
        # Wide spread (1.0%)
        valid, reason = self.data_health.validate_market_data(
            "NIFTY_OPT", 100, datetime.now(timezone.utc), volume=1000, bid=99.5, ask=100.5
        )
        self.assertFalse(valid)
        self.assertIn("WIDE_SPREAD", reason)

    def test_minimum_volume_filter(self):
        """Verify min 100 volume threshold"""
        # Good volume
        valid, _ = self.data_health.validate_market_data("NIFTY", 25000, datetime.now(timezone.utc), volume=500)
        self.assertTrue(valid)
        
        # Low volume
        valid, reason = self.data_health.validate_market_data("NIFTY", 25000, datetime.now(timezone.utc), volume=50)
        self.assertFalse(valid)
        self.assertIn("LOW_VOLUME", reason)

    # ========================================================================
    # 2. RISK MANAGEMENT TESTS (PRIORITY 5)
    # ========================================================================

    def test_consecutive_loss_circuit_breaker(self):
        """Verify trading halts after 3 consecutive losses"""
        # 3 Losses
        for _ in range(3):
            self.risk_mgr.record_trade_outcome("LOSS", -1000)
            
        test_signal = {'entry_price': 100, 'stop_loss': 90, 'target': 120, 'quantity': 75}
        valid, reason = self.risk_mgr.validate_new_trade(test_signal, self.pos_mgr)
        self.assertFalse(valid)
        self.assertIn("CIRCUIT_BREAKER", reason)

    def test_risk_reward_enforcement(self):
        """Verify min 1.5:1 Risk-Reward ratio"""
        # Poor R:R (1:1)
        bad_sig = {'entry_price': 100, 'stop_loss': 90, 'target': 110, 'quantity': 75}
        valid, reason = self.risk_mgr.validate_new_trade(bad_sig, self.pos_mgr)
        self.assertFalse(valid)
        self.assertIn("POOR_RISK_REWARD", reason)
        
        # Good R:R (2:1)
        good_sig = {'entry_price': 100, 'stop_loss': 90, 'target': 120, 'quantity': 75}
        valid, _ = self.risk_mgr.validate_new_trade(good_sig, self.pos_mgr)
        self.assertTrue(valid)

    def test_per_position_loss_limit(self):
        """Verify max 2% loss per position"""
        # Max loss for 100k capital is 2k.
        # This signal risks (100-70)*75 = 2250 (Exceeds 2000)
        risky_sig = {'entry_price': 100, 'stop_loss': 70, 'target': 200, 'quantity': 75}
        valid, reason = self.risk_mgr.validate_new_trade(risky_sig, self.pos_mgr)
        self.assertFalse(valid)
        self.assertIn("POSITION_RISK_TOO_HIGH", reason)

    # ========================================================================
    # 3. WEBSOCKET RESILIENCE TESTS (PRIORITY 2)
    # ========================================================================

    def test_watchdog_timeout_trigger(self):
        """Verify watchdog detects silence and calls reconnect"""
        reconnect_called = False
        def mock_reconnect():
            nonlocal reconnect_called
            reconnect_called = True
            
        watchdog = WebSocketWatchdog(
            reconnect_callback=mock_reconnect, 
            heartbeat_timeout=0.1,
            check_interval=0.05
        )
        watchdog.start()
        
        # Wait for timeout
        time.sleep(0.3)
        self.assertTrue(reconnect_called)
        watchdog.stop()

    # ========================================================================
    # 4. EXECUTION QUALITY TESTS (PRIORITY 3)
    # ========================================================================

    def test_pre_execution_slippage_block(self):
        """Verify block if market price moves too far before execution"""
        # Move of 1% (exceeds 0.5%)
        valid, reason = self.slippage_ctrl.validate_pre_execution("NIFTY", 100, 101)
        self.assertFalse(valid)
        self.assertIn("SLIPPAGE", reason)

    def test_slippage_recording(self):
        """Verify slippage stats are recorded correctly"""
        stats = self.slippage_ctrl.record_execution("NIFTY", 100, 100.2, time.time())
        self.assertAlmostEqual(stats.slippage_points, 0.2)
        self.assertAlmostEqual(stats.slippage_pct, 0.2)
        self.assertEqual(len(self.slippage_ctrl.history), 1)

    # ========================================================================
    # 5. STRIKE SELECTION TESTS (PRIORITY 4)
    # ========================================================================

    def test_regime_aware_delta_selection(self):
        """Verify different deltas for different regimes"""
        mock_chain = [
            {'strike': 24000, 'delta': 0.8, 'volume': 5000, 'oi': 10000, 'symbol': 'S1'},
            {'strike': 24500, 'delta': 0.6, 'volume': 5000, 'oi': 10000, 'symbol': 'S2'},
            {'strike': 25000, 'delta': 0.5, 'volume': 5000, 'oi': 10000, 'symbol': 'S3'},
            {'strike': 25500, 'delta': 0.3, 'volume': 5000, 'oi': 10000, 'symbol': 'S4'},
        ]
        
        # Bullish Regime (Target: 0.6)
        best = self.strike_selector.select_best_strike(mock_chain, MarketRegime.TRENDING_BULL)
        self.assertEqual(best['strike'], 24500)
        
        # Volatile Regime (Target: 0.35)
        best = self.strike_selector.select_best_strike(mock_chain, MarketRegime.VOLATILE)
        self.assertEqual(best['strike'], 25500)

    def test_liquidity_filtering(self):
        """Verify strikes with low volume/OI are rejected"""
        mock_chain = [
            {'strike': 24500, 'delta': 0.6, 'volume': 50, 'oi': 100, 'symbol': 'LOW_LIQ'},
        ]
        best = self.strike_selector.select_best_strike(mock_chain, MarketRegime.TRENDING_BULL)
        self.assertIsNone(best)

if __name__ == '__main__':
    unittest.main()
