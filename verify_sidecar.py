
import unittest
import pandas as pd
import os
import json
from trap_hunter import TrapHunter
from unittest.mock import MagicMock

class TestTrapHunter(unittest.TestCase):
    def setUp(self):
        # Reset state file for clean test
        if os.path.exists("sidecar_state.json"):
            os.remove("sidecar_state.json")
        if os.path.exists("sidecar_trades.json"):
            os.remove("sidecar_trades.json")
            
        self.hunter = TrapHunter()
        
        # Mock Pattern Engine checks
        # We assume confirmation is TRUE for these tests to check trigger logic
        self.hunter.pattern_engine.confirm_reversal = MagicMock(return_value=True)
        
        # Mock DataFrame
        self.mock_df = pd.DataFrame({"close": [100.0]*50})

    def test_institutional_veto_filter(self):
        """Verify that ONLY institutional vetoes trigger the hunter."""
        
        # 1. Technical Veto (Should BLOCK)
        res = self.hunter.check_trigger("BLOCKED: Score 0.6 < 0.75", "BULLISH", self.mock_df)
        self.assertEqual(res["action"], "BLOCK")
        self.assertEqual(res["reason"], "NOT_INSTITUTIONAL_TRAP")
        
        # 2. Institutional Veto (Should EXECUTE)
        res = self.hunter.check_trigger("BLOCKED: IV_SKEW_VETO active", "BULLISH", self.mock_df)
        self.assertEqual(res["action"], "EXECUTE")
        
    def test_daily_cap(self):
        """Verify Max 2 Trades Per Day."""
        
        # Trade 1
        self.hunter.log_execution("BEARISH_REVERSAL", 100, "Test 1")
        res = self.hunter.check_trigger("BLOCKED: IV_SKEW_VETO", "BULLISH", self.mock_df)
        self.assertEqual(res["action"], "EXECUTE")
        
        # Trade 2
        self.hunter.log_execution("BEARISH_REVERSAL", 100, "Test 2")
        
        # Trade 3 (Should Block)
        # Note: log_execution increments 'daily_trades'.
        # Current state: 2 trades logged. Next check_trigger should block.
        res = self.hunter.check_trigger("BLOCKED: IV_SKEW_VETO", "BULLISH", self.mock_df)
        self.assertEqual(res["action"], "BLOCK")
        self.assertEqual(res["reason"], "DAILY_CAP_REACHED")
        
    def test_kill_switch(self):
        """Verify Kill Switch after 2 Consecutive Losses."""
        
        # Loss 1
        self.hunter.update_outcome("t1", -50.0)
        self.assertFalse(self.hunter.state["kill_switch_active"])
        
        # Loss 2
        self.hunter.update_outcome("t2", -50.0)
        self.assertTrue(self.hunter.state["kill_switch_active"])
        
        # Next Trade Should Block
        res = self.hunter.check_trigger("BLOCKED: IV_SKEW_VETO", "BULLISH", self.mock_df)
        self.assertEqual(res["action"], "BLOCK")
        self.assertEqual(res["reason"], "KILL_SWITCH_ACTIVE")

if __name__ == "__main__":
    unittest.main()
