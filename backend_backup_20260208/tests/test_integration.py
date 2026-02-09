"""
Integration test to verify all components work together. [v2.1 Fix]
Run this BEFORE deploying to production.
"""
import sys
import os

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_full_sideways_flow():
    """Test complete sideways market flow"""
    from strategist import MarketStrategist
    from brain_engine import BrainEngine
    from skirmisher_v2 import SkirmisherV2
    from models import Regime
    import pandas as pd
    import numpy as np

    print("🚀 Starting Integration Test...")
    
    # 1. Create components
    strategist = MarketStrategist()
    brain = BrainEngine(stage=3)
    skirmisher = SkirmisherV2()
    
    # 2. Mock sideways data (Slight fluctuations for indicators)
    np.random.seed(42)
    base_price = 25000
    noise = np.random.normal(0, 2, 200)
    prices = base_price + np.cumsum(noise) # Random walk
    
    df = pd.DataFrame({
        'close': prices,
        'high': prices + 5,
        'low': prices - 5,
        'volume': [1000000] * 200
    })
    
    # 3. Test regime classification
    regime = strategist.classify_regime(df)
    print(f"DEBUG: Classified Regime: {regime}")
    assert "SIDEWAYS" in regime.value, f"Expected SIDEWAYS, got {regime}"
    
    # 4. Test brain authority lookup (backward compatibility check)
    features = {"ADX": 0.5, "PCR": 1.0, "BASIS_RES": 0.2, "OI_RES": 0.3}
    boost, thoughts = brain.get_confidence_boost(
        features, 
        regime_val=regime.value,
        signal_intent="BULLISH"
    )
    print(f"DEBUG: Brain Boost: {boost:.2f}")
    assert 0.0 <= boost <= 1.0, f"Invalid boost: {boost}"
    
    # 5. Test skirmisher call
    # Mock HTF
    df_htf = df.copy() 
    scalp = skirmisher.check_scalp_signal(
        df=df,
        df_htf=df_htf,
        current_regime=regime.value,
        iv_skew=1.0
    )
    print(f"DEBUG: Skirmisher Scalp: {scalp['action']}")
    assert "action" in scalp, "Scalp response missing 'action'"
    
    # 6. Test brain evaluation bridge
    if scalp["action"] == "EXECUTE":
        approved, brain_thoughts = brain.evaluate_skirmisher_signal(
            signal=scalp,
            regime=regime,
            iv_skew=1.0
        )
        print(f"DEBUG: Brain Evaluation: {approved}")
        assert isinstance(approved, bool), "Brain approval not boolean"
    
    print("✅ Integration test passed!")

if __name__ == "__main__":
    try:
        test_full_sideways_flow()
    except Exception as e:
        print(f"❌ Integration test FAILED: {e}")
        sys.exit(1)
