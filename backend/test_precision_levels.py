
import unittest
import pandas as pd
import numpy as np
import logging
from technical_engine import TechnicalEngine
from engines import RiskEngine

logging.basicConfig(level=logging.ERROR)

class TestPrecisionLevels(unittest.TestCase):
    def setUp(self):
        self.tech_engine = TechnicalEngine()
        self.risk_engine = RiskEngine()
        
        # Create Mock OHLCV Data (Uptrend with Pullback)
        # Price goes 100 -> 110 -> 105 -> 120
        data = []
        for i in range(100, 110): data.append({'high': i+1, 'low': i-1, 'close': i, 'volume': 1000}) # Up
        for i in range(110, 105, -1): data.append({'high': i+1, 'low': i-1, 'close': i, 'volume': 1000}) # Pullback
        for i in range(105, 120): data.append({'high': i+1, 'low': i-1, 'close': i, 'volume': 1000}) # Up again
        
        self.df = pd.DataFrame(data)
        
        # Mock OI Data (Resistance at 125, Support at 100)
        self.oi_data = {
            'calls': {125: 50000, 130: 20000},
            'puts': {100: 60000, 90: 10000}
        }

    def test_fractal_calculation(self):
        print("\n[TEST] Fractal Calculation")
        levels = self.tech_engine.calculate_precision_levels(self.df, 120, self.oi_data)
        fractals = levels.get('fractals', [])
        
        print(f"Fractals Found: {len(fractals)}")
        for f in fractals: print(f" - {f['type']} @ {f['price']}")
        
        self.assertTrue(len(fractals) > 0, "Should detect some fractals")
        
    def test_oi_walls(self):
        print("\n[TEST] OI Walls")
        levels = self.tech_engine.calculate_precision_levels(self.df, 120, self.oi_data)
        walls = levels.get('oi_walls', [])
        
        print(f"Walls Found: {len(walls)}")
        for w in walls: print(f" - {w['type']} @ {w['price']} (OI: {w['oi']})")
        
        # Check for Resistance at 125
        res_125 = next((w for w in walls if w['price'] == 125 and w['type'] == 'RESISTANCE'), None)
        self.assertIsNotNone(res_125, "Should identify 125 Call Wall as Resistance")

    def test_smart_stops_long(self):
        print("\n[TEST] Smart Stops (Long)")
        levels = self.tech_engine.calculate_precision_levels(self.df, 115, self.oi_data)
        
        # Simulate Entry at 115 (just above 110 breakout)
        risk = self.risk_engine.calculate_dynamic_stops(115, "BUY_CALL", atr=2.0, precision_levels=levels)
        
        print(f"Entry: 115")
        print(f"Stop Loss: {risk['stop_loss']}")
        print(f"Targets: {risk['targets']}")
        
        # Stop should be below entry
        self.assertTrue(risk['stop_loss'] < 115, "Stop Loss provided is not below entry")
        
        # Target 1 should be likely at 125 (OI Wall)
        if risk['targets']:
            print(f"Target 1 Distance: {risk['targets'][0] - 115}")
            
    def test_smart_stops_short(self):
        print("\n[TEST] Smart Stops (Short)")
        levels = self.tech_engine.calculate_precision_levels(self.df, 108, self.oi_data)
        
        # Simulate Short at 108
        risk = self.risk_engine.calculate_dynamic_stops(108, "BUY_PUT", atr=2.0, precision_levels=levels)
        
        print(f"Entry: 108")
        print(f"Stop Loss: {risk['stop_loss']}")
        print(f"Targets: {risk['targets']}")
        
        self.assertTrue(risk['stop_loss'] > 108, "Stop Loss provided is not above entry")

if __name__ == '__main__':
    unittest.main()
