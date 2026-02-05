"""
Titan Plus - System Verification (Phase 3)
===========================================
Tests the integration of:
1. Enhanced Brain Engine (XGBoost + RL + SMC)
2. RL Evolution Engine
3. Grandmaster SMC Engine
4. Safe Fallback Mechanisms

Usage: python test_system.py
"""

import logging
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Add current directory to path
sys.path.append(os.getcwd())

# Import Engines
from brain_engine_enhanced import EnhancedBrainEngine
from rl_engine import RLEvolutionEngine
from smc_engine import GrandmasterSMCEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TEST_SYSTEM")


def create_dummy_market_data():
    """Create synthetic market data for testing"""
    logger.info("Generating synthetic market data...")
    
    # 1. Market Snapshot
    market_data = {
        'spot_price': 25000.0,
        'future_price': 25010.0,
        'volume': 1500000,
        'pcr': 0.85
    }
    
    # 2. Technical Features
    features = {
        'rsi': 65.0,
        'adx': 35.0,
        'atr': 120.0,
        'basis': 10.0,
        'pcr': 0.85,
        'vix': 16.5,
        'iv_skew': 1.1,
        'call_gamma': 0.0025,
        'put_gamma': 0.0018,
        'gex': 500000.0,
        'gamma_ratio': 1.4
    }
    
    # 3. OHLCV Data for SMC (100 candles)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    np.random.seed(42)
    
    base_price = 25000
    noise = np.random.randn(100) * 20
    trend = np.linspace(0, 100, 100)  # Upward trend
    
    df = pd.DataFrame({
        'open': base_price + trend + noise,
        'high': base_price + trend + noise + 30,
        'low': base_price + trend + noise - 30,
        'close': base_price + trend + noise + 10,
        'volume': np.random.randint(50000, 200000, 100)
    }, index=dates)
    
    # Add a massive volume spike for Order Block detection
    df.iloc[-5, df.columns.get_loc('volume')] = 1000000
    df.iloc[-5, df.columns.get_loc('close')] = df.iloc[-5]['open'] + 50  # Big green candle
    
    return features, market_data, df


def test_rl_engine():
    """Test Reinforcement Learning Module"""
    logger.info("\n=== TEST 1: RL Evolution Engine ===")
    try:
        rl_engine = RLEvolutionEngine()
        
        # Test 1: Network Initialization
        logger.info(f"Networks initialized. Device: {rl_engine.device}")
        
        # Test 2: Action Selection
        features, market_data, _ = create_dummy_market_data()
        
        # Mock state creation (normally done by Brain)
        state_dict = {
            'indicators': features,
            'price': {
                'close': market_data['spot_price'],
                'high': market_data['spot_price'] * 1.01,
                'low': market_data['spot_price'] * 0.99,
                'volume': market_data['volume'],
                'future_premium': 10.0
            },
            'greeks': {
                'call_gamma': 0.002,
                'put_gamma': 0.002,
                'net_gex': 0.0,
                'gamma_ratio': 1.0
            },
            'smc': {'order_block': True, 'fvg': False},
            'regime': 'TRENDING_UP'
        }
        
        recommendation = rl_engine.get_recommendation(state_dict)
        logger.info(f"RL Recommendation: {recommendation['action']} (Conf: {recommendation['confidence']:.2f})")
        
        if recommendation['action'] in ['BUY_CALL', 'BUY_PUT', 'HOLD']:
            logger.info("✅ RL Engine Action Selection: PASS")
        else:
            logger.error("❌ RL Engine Action Selection: FAIL")
            
    except Exception as e:
        logger.error(f"❌ RL Engine Test Failed: {e}", exc_info=True)


def test_smc_engine():
    """Test Smart Money Concepts Module"""
    logger.info("\n=== TEST 2: Grandmaster SMC Engine ===")
    try:
        smc_engine = GrandmasterSMCEngine()
        _, _, df = create_dummy_market_data()
        
        result = smc_engine.analyze(df)
        
        logger.info(f"Market Structure: {result['market_structure']}")
        logger.info(f"Confluence Score: {result['confluence_score']}")
        logger.info(f"Order Blocks Detected: {len(result['order_blocks'])}")
        
        if result['market_structure'] in ['BULLISH', 'BEARISH', 'NEUTRAL']:
             logger.info("✅ SMC Analysis: PASS")
        else:
             logger.error("❌ SMC Analysis: FAIL")
             
    except Exception as e:
        logger.error(f"❌ SMC Engine Test Failed: {e}", exc_info=True)


def test_enhanced_brain():
    """Test Integration (The Nuclear Core)"""
    logger.info("\n=== TEST 3: Enhanced Brain Engine Integration ===")
    try:
        brain = EnhancedBrainEngine(enable_rl=True, enable_smc=True)
        
        features, market_data, df = create_dummy_market_data()
        
        # Test Decision Making
        decision = brain.decide(
            features=features,
            market_data=market_data,
            ohlcv_df=df,
            regime="TRENDING_UP"
        )
        
        logger.info(f"Final Decision: {decision['decision']}")
        logger.info(f"Probability: {decision['probability']:.3f}")
        logger.info(f"Source: {decision['source']}")
        
        # Verify Components
        comps = decision['components']
        logger.info(f"XGBoost Score: {comps['xgboost']['probability']:.3f} (Weight: {decision['weights']['xgboost']})")
        
        if comps['rl']:
            logger.info(f"RL Score: {comps['rl']['confidence']:.3f} (Weight: {decision['weights']['rl']})")
        else:
            logger.warning("RL component missing (Training mode?)")
            
        if comps['smc']:
            market_structure = comps['smc']['market_structure']
            logger.info(f"SMC Structure: {market_structure} (Weight: {decision['weights']['smc']})")
        else:
            logger.warning("SMC component missing")
            
        if decision['decision'] in ['APPROVE', 'BLOCK']:
            logger.info("✅ Brain Integration: PASS")
        else:
            logger.error("❌ Brain Integration: FAIL")
            
    except Exception as e:
        logger.error(f"❌ Brain Engine Test Failed: {e}", exc_info=True)


def test_meta_vetoes():
    """Test Safety Systems"""
    logger.info("\n=== TEST 4: Meta-Governor Safety Checks ===")
    try:
        brain = EnhancedBrainEngine()
        features, market_data, _ = create_dummy_market_data()
        
        # Simulating dangerous VIX spike
        features['vix'] = 45.0  # Excessive VIX
        
        decision = brain.decide(features, market_data, regime="NEUTRAL")
        
        if decision['decision'] == 'BLOCK' and any("VIX_SPIKE" in r for r in decision['veto_reasons']):
            logger.info("✅ VIX Veto Triggered: PASS")
        else:
            logger.error(f"❌ VIX Veto Failed. Decision: {decision['decision']}")
            
    except Exception as e:
        logger.error(f"❌ Meta-Veto Test Failed: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("Starting Titan Plus Phase 3 Verification...")
    
    test_rl_engine()
    test_smc_engine()
    test_enhanced_brain()
    test_meta_vetoes()
    
    logger.info("\nAll System Verification Tests Complete.")
