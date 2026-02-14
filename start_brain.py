"""
Titan Brain V3 - Startup Script
Launches the 24/7 institutional intelligence core
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.brain import titan_brain
from backend.ai_decision import ai_engine
from backend.risk_engine import risk_engine

def print_banner():
    print("\n" + "="*70)
    print("🧠 TITAN CRYPTO BRAIN V3 - INSTITUTIONAL INTELLIGENCE CORE")
    print("="*70)
    print("📊 Mode: Advisory Signal Generation (Manual Execution)")
    print("🎯 Strategy: Smart Money Concepts + Self-Evolving AI")
    print("⚡ Risk Management: Multi-Target System with SMC Alignment")
    print("="*70)
    print("\n🔧 System Status:")
    print(f"   AI Model: {ai_engine.model_version}")
    print(f"   Confidence Threshold: {ai_engine.min_confidence:.1%}")
    print(f"   Risk Per Trade: {risk_engine.risk_per_trade_pct:.1%}")
    print(f"   Monitored Symbols: {', '.join(titan_brain.monitored_symbols)}")
    print("="*70)
    print("\n🚀 Starting 24/7 monitoring...\n")

async def main():
    """Main entry point"""
    print_banner()
    
    try:
        await titan_brain.run_247()
    except KeyboardInterrupt:
        print("\n\n⚠️  Shutdown signal received...")
        print("📊 Generating performance report...\n")
        
        # Print final stats
        ai_report = ai_engine.get_performance_report()
        risk_report = risk_engine.get_performance_metrics()
        
        print("="*70)
        print("AI ENGINE PERFORMANCE:")
        print("="*70)
        for key, value in ai_report.items():
            print(f"   {key}: {value}")
        
        print("\n" + "="*70)
        print("RISK ENGINE PERFORMANCE:")
        print("="*70)
        for key, value in risk_report.items():
            print(f"   {key}: {value}")
        
        print("\n" + "="*70)
        print("🛑 Titan Brain shutdown complete.")
        print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
