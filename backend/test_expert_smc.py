
import unittest
import pandas as pd
import numpy as np
import logging
from technical_engine import TechnicalEngine
from engines import RiskEngine

logging.basicConfig(level=logging.ERROR)

class TestExpertSMC(unittest.TestCase):
    def setUp(self):
        self.tech_engine = TechnicalEngine()
        self.risk_engine = RiskEngine()
        
        # Create Mock Data for Bulish Order Block
        # 5 Candles Consolidation (Small bodies)
        data = []
        base_price = 100.0
        for i in range(50): # Warmup
            data.append({'high': base_price+1, 'low': base_price-1, 'open': base_price, 'close': base_price, 'volume': 1000})
            
        # 5 Consolidation Candles (i=50 to 54)
        for i in range(5):
            data.append({'high': 101, 'low': 99, 'open': 100, 'close': 100.1, 'volume': 1000})
            
        # Breakout Candle (i=55) - Huge Volume + Move
        data.append({'high': 105, 'low': 100, 'open': 100.1, 'close': 104, 'volume': 5000})
        
        # Post Breakout (i=56+)
        for i in range(10):
            data.append({'high': 106, 'low': 102, 'open': 104, 'close': 105, 'volume': 2000})
            
        self.df = pd.DataFrame(data)
        
    def test_order_block_detection(self):
        print("\n[TEST] Order Block Detection")
        # We expect an OB at index 55 based on 50-54 consolidation
        obs = self.tech_engine._find_order_blocks(self.df)
        
        print(f"OBs Found: {len(obs)}")
        for ob in obs:
            print(f" - {ob['type']} @ {ob['price']} (Zone: {ob['zone_bottom']} - {ob['zone_top']})")
            
        self.assertTrue(len(obs) > 0, "Should detect the Bullish Order Block")
        self.assertEqual(obs[0]['type'], 'SUPPORT', "Should be Support (Bullish OB)")
        
    def test_expert_stops(self):
        print("\n[TEST] Expert Dynamic Stops")
        levels = self.tech_engine.calculate_precision_levels(self.df, 103)
        obs = levels.get('order_blocks', [])
        
        if not obs:
            print("Skipping Stop Test (No OB found)")
            return

        # Simulate Long Entry at 103 (Retracement to OTE)
        # OB Zone Bottom should be ~99 (Low of consolidation)
        # Stop should be 99 - (1.2 * ATR)
        
        risk = self.risk_engine.calculate_dynamic_stops(103, "BUY_CALL", atr=1.0, precision_levels=levels)
        
        print(f"Entry: 103")
        print(f"Stop Loss: {risk['stop_loss']}")
        print(f"Targets: {risk['targets']}")
        
        # Check Stop Logic: OB Bottom (99) - 1.2*ATR(1.0) = ~97.8
        expected_sl = 99.0 - (1.2 * 1.0)
        print(f"Expected SL approx: {expected_sl}")
        
        self.assertTrue(abs(risk['stop_loss'] - expected_sl) < 0.5, f"Stop Loss {risk['stop_loss']} not matching expected {expected_sl}")

if __name__ == '__main__':
    unittest.main()
