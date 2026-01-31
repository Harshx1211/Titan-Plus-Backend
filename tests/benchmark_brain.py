import time
import sys
import os
from collections import deque

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from brain_engine import BrainEngine, Regime

def benchmark_v1_style(iterations=10000):
    """Simulate v1 logic (List-based appends and pops)."""
    history = []
    window_size = 500
    start = time.perf_counter()
    for i in range(iterations):
        history.append(float(i))
        if len(history) > window_size:
            history.pop(0) # O(N) operation
    elapsed = time.perf_counter() - start
    return elapsed

def benchmark_v2_style(iterations=10000):
    """Simulate v2 logic (Deque-based)."""
    history = deque(maxlen=500)
    start = time.perf_counter()
    for i in range(iterations):
        history.append(float(i)) # O(1) operation
    elapsed = time.perf_counter() - start
    return elapsed

def full_engine_benchmark(iterations=1000):
    brain = BrainEngine(stage=3)
    features = {"ADX": 30.0, "PCR": 0.5, "BASIS_RES": 0.1, "OI_RES": 0.5}
    
    start = time.perf_counter()
    for i in range(iterations):
        brain.update_raw_history(features)
        brain.get_confidence_boost(features, Regime.TRENDING.value)
    elapsed = time.perf_counter() - start
    return elapsed

if __name__ == "__main__":
    v1_time = benchmark_v1_style(50000)
    v2_time = benchmark_v2_style(50000)
    
    print(f"V1 (List) 50k ops: {v1_time:.4f}s")
    print(f"V2 (Deque) 50k ops: {v2_time:.4f}s")
    print(f"Speedup: {v1_time/v2_time:.1f}x")
    
    engine_time = full_engine_benchmark(5000)
    print(f"Full Engine 5k inferences: {engine_time:.4f}s ({5000/engine_time:.0f} inf/sec)")
