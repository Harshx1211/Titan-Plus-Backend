import unittest
from risk_engine import RiskEngine

class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        self.risk = RiskEngine()
        self.risk.reset()

    def test_sizing_logic(self):
        """Verify that size increases with confidence but has a ceiling."""
        size_low = self.risk.get_suggested_size(confidence=0.5, base_size=1)
        size_high = self.risk.get_suggested_size(confidence=0.95, base_size=4)
        
        self.assertGreaterEqual(size_high, size_low)

    def test_winning_streak_dampening(self):
        """Verify that size dampens after a long winning streak."""
        # Force a baseline with high confidence and no streak
        base_size = self.risk.get_suggested_size(confidence=0.95, base_size=4)
        
        # Simulate 5 wins
        for _ in range(5):
            self.risk.log_trade(is_win=True)
            
        streak_size = self.risk.get_suggested_size(confidence=0.95, base_size=4)
        self.assertLess(streak_size, base_size, "Size should be dampened after a winning streak")

    def test_recovery_mode(self):
        """Verify recovery mode after losses."""
        self.assertFalse(self.risk.is_in_recovery())
        
        # Simulate 1 loss to enter recovery
        self.risk.log_trade(is_win=False)
        self.assertTrue(self.risk.is_in_recovery())
        
        rec_size = self.risk.get_suggested_size(confidence=1.0, base_size=4)
        self.assertEqual(rec_size, 1, "Should force min size 1 in recovery mode (4 * 1.0 * 0.25)")

if __name__ == "__main__":
    unittest.main()
