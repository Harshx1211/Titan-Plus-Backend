from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

load_dotenv()

class DatabaseManager:
    """
    Handles all Supabase interactions for the Titan Crypto Brain.
    """
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
        
        self.supabase: Client = create_client(url, key)
        self.client = self.supabase  # Alias for compatibility
        print("Database connection initialized.")

    # --- Position & Trade History ---
    
    def log_trade(self, symbol: str, side: str, entry_price: float, entry_reason: str, 
                  stop_loss: float = 0, targets: Dict = None, confidence: float = 0) -> str:
        """Logs a new open trade with risk parameters."""
        data = {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "targets": targets or {},
            "confidence": confidence,
            "entry_reason": entry_reason,
            "status": "OPEN",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        # We use a try-except here in case the user hasn't added the new columns yet
        try:
            res = self.supabase.table("trades").insert(data).execute()
        except Exception as e:
            print(f"⚠️ Database Error (Missing Columns?): {e}")
            # Fallback to legacy schema if insertion fails
            legacy_data = {k: v for k, v in data.items() if k in ["symbol", "side", "entry_price", "entry_reason", "status", "created_at"]}
            res = self.supabase.table("trades").insert(legacy_data).execute()
            
        return res.data[0]['id'] if res.data else ""

    def close_trade(self, trade_id: str, exit_price: float, exit_reason: str, pnl: float):
        """Closes an existing trade and updates PnL."""
        data = {
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "status": "CLOSED",
            "closed_at": datetime.now(timezone.utc).isoformat()
        }
        self.supabase.table("trades").update(data).eq("id", trade_id).execute()

    def get_active_trade(self) -> Optional[Dict]:
        """Returns the currently open trade, if any."""
        res = self.supabase.table("trades").select("*").eq("status", "OPEN").order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    # --- Brain Logs (Thinking Process) ---

    def log_brain_thought(self, symbol: str, sentiment: str, logic_details: Dict, market_regime: str):
        """Logs the detailed thinking process for AI training."""
        data = {
            "symbol": symbol,
            "sentiment": sentiment,
            "logic_details": logic_details,
            "market_regime": market_regime,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.supabase.table("brain_logs").insert(data).execute()

    # --- Market State ---

    def update_market_state(self, symbol: str, price: float, volume: float = 0, rsi: float = 0):
        """Updates the real-time market state for a coin."""
        data = {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "rsi": rsi,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        self.supabase.table("market_state").upsert(data).execute()

# Singleton instance
db = DatabaseManager()
