
import unittest
import pandas as pd
import numpy as np
import os
import json
import pandas_ta as ta
from skirmisher import Skirmisher
from unittest.mock import MagicMock

class TestSkirmisher(unittest.TestCase):
    def setUp(self):
        # Reset state file for clean test
        if os.path.exists("skirmisher_state.json"):
            os.remove("skirmisher_state.json")
        if os.path.exists("skirmisher_ledger.json"):
            os.remove("skirmisher_ledger.json")
            
        self.skirmisher = Skirmisher()
        
        # Create Mock DataFrame
        # 50 candles
        self.df = pd.DataFrame({
            "close": np.random.normal(100, 1, 50),
            "high": np.random.normal(101, 1, 50),
            "low": np.random.normal(99, 1, 50),
            "open": np.random.normal(100, 1, 50),
            "volume": np.random.normal(1000, 100, 50)
        })
        
    def test_trend_kill_switch_adx(self):
        """Verify ADX > 25 kills the signal."""
        # Inject High ADX
        # We need to construct price data that generates high ADX
        # Easiest way is to mock the ta.adx output if possible, 
        # but skirmisher calls df.ta.adx internally.
        # Alternatively, we create a strong trend.
        
        trend_prices = [100 + i*2 for i in range(50)]
        df = pd.DataFrame({
            "close": trend_prices, "high": [p+1 for p in trend_prices], "low": [p-1 for p in trend_prices], "open": trend_prices, "volume": [1000]*50
        })
        
        # Verify ADX is high
        adx = df.ta.adx(length=14)
        curr_adx = adx["ADX_14"].iloc[-1]
        self.assertTrue(curr_adx > 25, f"ADX {curr_adx} should be > 25 for test")
        
        res = self.skirmisher.check_scalp_signal(df, "SIDEWAYS")
        self.assertTrue("BLOCK" in res["action"])
        self.assertTrue("TREND_RISK" in res["reason"])

    def test_daily_cap(self):
        """Verify Max 3 Trades Per Day."""
        # Force 3 trades
        self.skirmisher.log_execution("TEST", 100, "T1")
        self.skirmisher.log_execution("TEST", 100, "T2")
        self.skirmisher.log_execution("TEST", 100, "T3")
        
        # Mock a flat dataframe suitable for scalping
        flat_prices = [100]*50
        df = pd.DataFrame({"close": flat_prices, "high": flat_prices, "low": flat_prices, "open": flat_prices, "volume": [1000]*50})
        
        res = self.skirmisher.check_scalp_signal(df, "SIDEWAYS")
        self.assertEqual(res["action"], "BLOCK")
        self.assertEqual(res["reason"], "DAILY_CAP_REACHED")
        
    def test_regime_mismatch(self):
        """Verify Skirmisher only runs in SIDEWAYS/CHOP."""
        flat_prices = [100]*50
        df = pd.DataFrame({"close": flat_prices, "high": flat_prices, "low": flat_prices, "open": flat_prices, "volume": [1000]*50})
        
        res = self.skirmisher.check_scalp_signal(df, "TRENDING")
        self.assertEqual(res["action"], "BLOCK")
        self.assertEqual(res["reason"], "REGIME_MISMATCH")

if __name__ == "__main__":
    unittest.main()
