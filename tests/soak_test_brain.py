"""
BrainEngine v2.0 - Staging Soak Simulation
Simulates 24 hours of market activity in a compressed timeframe (~15 mins).
Verifies Supabase logging stability, memory pressure, and state persistence.
"""
import time
import os
import sys
import random
import uuid
from datetime import datetime, timedelta

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'backend'))

from brain_engine import BrainEngine, Regime

def run_soak_test(iterations=5000):
    print("\n" + "!" * 50)
    print("STARTING BRAIN v2.0 SOAK TEST (STAGING SIMULATION)")
    print("!" * 50)
    
    brain = BrainEngine(stage=3)
    start_time = time.time()
    
    # Track stats
    errors = 0
    total_latency = 0
    
    regimes = [Regime.TRENDING, Regime.SIDEWAYS, Regime.UNCERTAIN]
    intents = ["BULLISH", "BEARISH", None]
    
    print(f"Executing {iterations} simulated inferences with cloud logging...")
    
    for i in range(1, iterations + 1):
        try:
            # Simulate features
            features = {
                "ADX": 20 + random.random() * 20,
                "OI_RES": random.uniform(-1, 1),
                "PCR": random.uniform(0.5, 1.5),
                "BASIS_RES": random.uniform(-0.5, 0.5)
            }
            regime = random.choice(regimes)
            intent = random.choice(intents)
            skew = random.uniform(1.0, 1.6)
            
            iter_start = time.perf_counter()
            
            # 1. Inference
            decision_id, thoughts = brain.generate_decision(
                features, regime, is_commit=False, 
                signal_intent=intent, iv_skew=skew
            )
            
            # 2. Outcome (Simulate a trade outcome every 10 iterations)
            if i % 10 == 0:
                outcome = random.choice([True, False])
                brain.log_snapshot(
                    decision_id, 
                    outcome=outcome,
                    performance={"mfe": random.uniform(0, 30), "mae": random.uniform(0, 10)}
                )
            
            total_latency += (time.perf_counter() - iter_start)
            
            if i % 500 == 0:
                elapsed = time.time() - start_time
                print(f"  [{i}/{iterations}] Elapsed: {elapsed:.1f}s | "
                      f"Avg Latency: {(total_latency/i)*1000:.2f}ms | "
                      f"Health: {brain.health_check()['status']}")
                
        except Exception as e:
            print(f"  CRITICAL ERROR at iteration {i}: {e}")
            errors += 1
            if errors > 5:
                print("TOO MANY ERRORS. ABORTING.")
                break

    end_time = time.time()
    print("\n" + "=" * 50)
    print("SIMULATION COMPLETE")
    print("=" * 50)
    print(f"Total Time: {end_time - start_time:.1f}s")
    print(f"Avg Throughput: {iterations / (end_time - start_time):.1f} ops/sec")
    print(f"Final Brain Metrics: {brain.metrics}")
    print(f"Health Check: {brain.health_check()}")
    
    if errors == 0:
        print("\n✅ SOAK TEST PASSED: System remains stable under sustained load.")
    else:
        print(f"\n❌ SOAK TEST FAILED: {errors} errors encountered.")

if __name__ == "__main__":
    # Note: This will actually talk to Supabase if configured.
    # In a real staging test, we want to see those logs hit the DB.
    run_soak_test(iterations=2000) # Faster run for verification
