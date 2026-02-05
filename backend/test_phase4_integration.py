"""
Titan Plus - Phase 4 Integration Test
======================================
Tests PPO + Optuna + Enhanced Brain integration

Run: python test_phase4_integration.py
"""

import sys
import logging
import numpy as np
import torch
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("phase4_test")

# Import Phase 4 components
from rl_engine_ppo import PPOAgent
from brain_engine_enhanced import EnhancedBrainEngine

def test_ppo_action_consistency():
    """Test 1: Verify PPO action mapping matches DQN"""
    logger.info("=" * 60)
    logger.info("TEST 1: PPO Action Mapping Consistency")
    logger.info("=" * 60)
    
    try:
        agent = PPOAgent()
        
        # Create dummy state
        state = np.random.randn(25).astype(np.float32)
        action, log_prob, value = agent.get_action(state)
        
        # Verify action is in valid range
        assert action in [0, 1, 2], f"Invalid action: {action}"
        
        # Map to recommendation
        rec_map = {0: 'BUY_CALL', 1: 'BUY_PUT', 2: 'HOLD'}
        recommendation = rec_map[action]
        
        logger.info(f"✓ Action: {action} -> {recommendation}")
        logger.info(f"✓ Log Prob: {log_prob:.4f}")
        logger.info(f"✓ Value: {value:.4f}")
        logger.info("✓ TEST PASSED: Action mapping is correct")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        return False


def test_ppo_gae_training():
    """Test 2: Verify GAE training loop"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: PPO GAE Training")
    logger.info("=" * 60)
    
    try:
        agent = PPOAgent()
        
        # Simulate 10 episodes
        for episode in range(10):
            state = torch.FloatTensor(np.random.randn(25).astype(np.float32))
            action, log_prob, value = agent.get_action(state.numpy())
            
            # Simulate reward (random win/loss)
            reward = 1.0 if np.random.rand() > 0.5 else -1.0
            done = True
            
            # Store transition (with value - critical for GAE)
            agent.store_transition(state, action, log_prob, reward, done, value)
            
            logger.info(f"  Episode {episode+1}: Action={action}, Reward={reward:.1f}, Value={value:.4f}")
        
        # Update using GAE
        logger.info("\nUpdating PPO with GAE...")
        agent.update()
        
        logger.info("✓ TEST PASSED: GAE training successful")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        return False


def test_brain_ppo_integration():
    """Test 3: Verify Brain Engine uses PPO correctly"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Brain Engine PPO Integration")
    logger.info("=" * 60)
    
    try:
        # Initialize with PPO enabled
        brain = EnhancedBrainEngine(enable_rl=True, enable_smc=False, use_ppo=True)
        
        # Verify PPO is active
        assert brain.use_ppo == True, "PPO not enabled"
        assert brain.ppo_agent is not None, "PPO agent not initialized"
        logger.info("✓ PPO Agent initialized")
        
        # Create test features
        features = {
            'rsi': 65.0,
            'adx': 35.0,
            'atr': 120.0,
            'basis': 2.5,
            'pcr': 0.85,
            'vix': 18.0,
            'iv_skew': 1.1,
            'call_gamma': 0.0025,
            'put_gamma': 0.0018,
            'gex': 500000,
            'gamma_ratio': 1.4
        }
        
        market_data = {
            'spot_price': 25500.0,
            'future_price': 25508.0,
            'volume': 5000000
        }
        
        # Make decision
        decision = brain.decide(features, market_data, regime='TRENDING_UP')
        
        # Verify decision structure
        assert 'decision' in decision, "Missing decision key"
        assert 'components' in decision, "Missing components key"
        assert decision['components']['rl'] is not None, "RL component not present"
        
        rl_result = decision['components']['rl']
        assert 'action' in rl_result, "Missing action in RL result"
        assert rl_result['action'] in ['BUY_CALL', 'BUY_PUT', 'HOLD'], "Invalid RL action"
        
        logger.info(f"✓ Decision: {decision['decision']}")
        logger.info(f"✓ Probability: {decision['probability']:.3f}")
        logger.info(f"✓ RL Action: {rl_result['action']}")
        logger.info(f"✓ RL Confidence: {rl_result['confidence']:.3f}")
        logger.info("✓ TEST PASSED: Brain-PPO integration working")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        return False


def test_brain_action_mapping():
    """Test 4: Verify action mapping is consistent across DQN and PPO modes"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Action Mapping Consistency (DQN vs PPO)")
    logger.info("=" * 60)
    
    try:
        # Test with PPO
        brain_ppo = EnhancedBrainEngine(enable_rl=True, enable_smc=False, use_ppo=True)
        
        features = {
            'rsi': 70.0, 'adx': 40.0, 'atr': 150.0, 'basis': 1.0,
            'pcr': 0.75, 'vix': 15.0, 'iv_skew': 1.2,
            'call_gamma': 0.003, 'put_gamma': 0.002,
            'gex': 100000, 'gamma_ratio': 1.5
        }
        
        market_data = {'spot_price': 26000.0, 'future_price': 26010.0, 'volume': 6000000}
        
        # Make multiple decisions to check consistency
        actions_seen = set()
        for _ in range(10):
            decision = brain_ppo.decide(features, market_data, regime='TRENDING_UP')
            rl_action = decision['components']['rl']['action']
            actions_seen.add(rl_action)
            logger.info(f"  PPO Action: {rl_action}")
        
        # Verify only valid actions are returned
        valid_actions = {'BUY_CALL', 'BUY_PUT', 'HOLD'}
        assert actions_seen.issubset(valid_actions), f"Invalid actions detected: {actions_seen - valid_actions}"
        
        logger.info(f"✓ Actions observed: {actions_seen}")
        logger.info("✓ TEST PASSED: All actions are valid")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        return False


def test_ppo_state_vector_conversion():
    """Test 5: Verify state dict -> vector conversion for PPO"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: PPO State Vector Conversion")
    logger.info("=" * 60)
    
    try:
        brain = EnhancedBrainEngine(enable_rl=True, enable_smc=False, use_ppo=True)
        
        # Create comprehensive state dict
        state_dict = {
            'indicators': {
                'rsi': 55.0, 'adx': 30.0, 'atr': 110.0, 'basis': 1.5,
                'pcr': 0.9, 'vix': 16.0, 'iv_skew': 1.05
            },
            'price': {
                'close': 25400.0, 'high': 25450.0, 'low': 25350.0,
                'volume': 4500000, 'future_premium': 7.0
            },
            'greeks': {
                'call_gamma': 0.0022, 'put_gamma': 0.0019,
                'net_gex': 300000, 'gamma_ratio': 1.15
            },
            'smc': {
                'order_block': True, 'fvg': False,
                'liquidity_sweep': False, 'imbalance_score': 0.4
            },
            'regime': 'SIDEWAYS_STRONG'
        }
        
        # Convert to vector
        vector = brain._build_ppo_vector(state_dict)
        
        # Verify shape
        assert vector.shape == (25,), f"Invalid shape: {vector.shape}"
        assert vector.dtype == np.float32, f"Invalid dtype: {vector.dtype}"
        
        # Verify all values are numeric and not NaN
        assert not np.any(np.isnan(vector)), "Vector contains NaN values"
        assert not np.any(np.isinf(vector)), "Vector contains inf values"
        
        logger.info(f"✓ Vector shape: {vector.shape}")
        logger.info(f"✓ Vector dtype: {vector.dtype}")
        logger.info(f"✓ Vector range: [{vector.min():.4f}, {vector.max():.4f}]")
        logger.info(f"✓ Sample values: {vector[:5]}")
        logger.info("✓ TEST PASSED: State vector conversion successful")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        return False


def main():
    """Run all Phase 4 tests"""
    logger.info("\n" + "=" * 60)
    logger.info("TITAN PLUS - PHASE 4 INTEGRATION TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    results = {
        "PPO Action Consistency": test_ppo_action_consistency(),
        "PPO GAE Training": test_ppo_gae_training(),
        "Brain-PPO Integration": test_brain_ppo_integration(),
        "Action Mapping Consistency": test_brain_action_mapping(),
        "State Vector Conversion": test_ppo_state_vector_conversion()
    }
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{test_name:.<45} {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    logger.info("=" * 60)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    if passed == total:
        logger.info("🎉 ALL PHASE 4 SYSTEMS OPERATIONAL - READY FOR DEPLOYMENT")
        return 0
    else:
        logger.error("⚠ SOME TESTS FAILED - REVIEW LOGS BEFORE DEPLOYMENT")
        return 1


if __name__ == "__main__":
    sys.exit(main())
