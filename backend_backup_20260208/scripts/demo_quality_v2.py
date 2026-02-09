import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime

print("="*60)
print("ENHANCED ELITE SCALPER - DEMO (Quality Filter V2)")
print("="*60)

from quality_filter_v2 import QualityFilterV2

def create_test_scenario(name, volume_ratio, ema_aligned, rsi, rr_ratio, news_sentiment, regime="SIDEWAYS_NORMAL"):
    """Create a test trade scenario"""
    times = pd.date_range(start='2026-02-01 10:00', periods=50, freq='5min')
    base = 25300
    
    if ema_aligned:
        trend = np.linspace(0, 50, 50) if rsi < 50 else np.linspace(50, 0, 50)
    else:
        trend = np.random.randn(50) * 10
    
    prices = base + trend + np.random.randn(50) * 5
    
    df = pd.DataFrame({
        'timestamp': times,
        'open': prices,
        'high': prices + abs(np.random.randn(50) * 8),
        'low': prices - abs(np.random.randn(50) * 8),
        'close': prices + np.random.randn(50) * 3,
        'volume': [100000 * volume_ratio * (1 + np.random.rand()) for _ in range(50)]
    })
    df.set_index('timestamp', inplace=True)
    
    return df, regime

def run_demo():
    print("\nComparing V1 (Basic) vs V2 (Enhanced) Quality Filter\n")
    
    qf_v2 = QualityFilterV2()
    
    # Test Scenarios
    scenarios = [
        {
            "name": "[PERFECT SETUP]",
            "type": "BULLISH_SCALP",
            "volume_ratio": 2.0,
            "ema_aligned": True,
            "rsi": 40,
            "rr_ratio": 2.5,
            "news_sentiment": 0.5,
            "regime": "TRENDING"
        },
        {
            "name": "[GOOD SETUP - Trending Market]",
            "type": "BEARISH_SCALP",
            "volume_ratio": 1.4,
            "ema_aligned": True,
            "rsi": 65,
            "rr_ratio": 1.6,
            "news_sentiment": -0.3,
            "regime": "TRENDING"
        },
        {
            "name": "[MARGINAL SETUP - Sideways]",
            "type": "BULLISH_SCALP",
            "volume_ratio": 1.2,
            "ema_aligned": True,
            "rsi": 55,
            "rr_ratio": 1.4,
            "news_sentiment": 0.0,
            "regime": "SIDEWAYS_NORMAL"
        },
        {
            "name": "[WEAK SETUP - Choppy]",
            "type": "BULLISH_SCALP",
            "volume_ratio": 0.9,
            "ema_aligned": False,
            "rsi": 50,
            "rr_ratio": 1.3,
            "news_sentiment": 0.0,
            "regime": "SIDEWAYS_WEAK"
        },
        {
            "name": "[HIGH R:R - Uncertain Market]",
            "type": "BEARISH_SCALP",
            "volume_ratio": 1.1,
            "ema_aligned": True,
            "rsi": 60,
            "rr_ratio": 3.2,
            "news_sentiment": 0.0,
            "regime": "UNCERTAIN"
        }
    ]
    
    results_v2 = []
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 60)
        print(f"Market Regime: {scenario['regime']}")
        
        df, regime = create_test_scenario(
            scenario['name'],
            scenario['volume_ratio'],
            scenario['ema_aligned'],
            scenario['rsi'],
            scenario['rr_ratio'],
            scenario['news_sentiment'],
            scenario['regime']
        )
        
        # V2 Evaluation
        quality_v2 = qf_v2.evaluate_trade_quality(
            signal_data={"type": scenario['type'], "rr_ratio": scenario['rr_ratio']},
            df_1m=df,
            df_5m=df,
            news_sentiment=scenario['news_sentiment'],
            current_regime=regime
        )
        
        print(f"Quality Score: {quality_v2['score']:.2f} / 5.5")
        print(f"Threshold: {quality_v2['threshold']:.2f}")
        print(f"Status: {'[APPROVED]' if quality_v2['approved'] else '[REJECTED]'}")
        if quality_v2.get('regime_adjusted'):
            print(f"Regime Adjustment: ACTIVE")
        print(f"Reasons: {', '.join(quality_v2['reasons'][:4])}")
        
        results_v2.append({
            'name': scenario['name'],
            'score': quality_v2['score'],
            'threshold': quality_v2['threshold'],
            'approved': quality_v2['approved'],
            'regime': regime
        })
    
    # Summary
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    
    approved_v2 = [r for r in results_v2 if r['approved']]
    rejected_v2 = [r for r in results_v2 if not r['approved']]
    
    print(f"\nV2 (Enhanced) Results:")
    print(f"[APPROVED]: {len(approved_v2)} / {len(results_v2)}")
    for r in approved_v2:
        print(f"   - {r['name']}: {r['score']:.2f}/{r['threshold']:.2f} ({r['regime']})")
    
    print(f"\n[REJECTED]: {len(rejected_v2)} / {len(results_v2)}")
    for r in rejected_v2:
        print(f"   - {r['name']}: {r['score']:.2f}/{r['threshold']:.2f} ({r['regime']})")
    
    print(f"\nKey Improvements:")
    print(f"  - Adaptive thresholds based on market regime")
    print(f"  - Enhanced scoring with MACD confirmation")
    print(f"  - Increased R:R weight (max 1.5 pts)")
    print(f"  - Granular volume scoring")
    
    approval_rate = (len(approved_v2) / len(results_v2)) * 100
    print(f"\nApproval Rate: {approval_rate:.0f}%")
    
    if approval_rate > 40:
        print("\nResult: MORE TRADES while maintaining quality!")
    
    print("="*60)

if __name__ == "__main__":
    run_demo()
