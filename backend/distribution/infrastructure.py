from supabase import create_client, Client
import os
from datetime import datetime

class SupabaseManager:
    def __init__(self):
        # Friend should add their own credentials in .env
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            print("WARNING: SUPABASE_URL or SUPABASE_KEY missing in .env")
        self.client: Client = create_client(url, key)
    
    def get_snapshots(self, limit=1000):
        """Fetch trade snapshots for training"""
        try:
            response = self.client.table('trade_snapshots').select('*').limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"DB Error: {e}")
            return []
    
    def log_snapshot(self, features, outcome, stage):
        """Log decision for training"""
        try:
            self.client.table('trade_snapshots').insert({
                'features': features,
                'outcome': outcome,
                'stage': stage,
                'timestamp': datetime.now().isoformat()
            }).execute()
        except Exception as e:
            print(f"DB Log Error: {e}")

# App config (if needed)
APP_CONFIG = {
    "stage": int(os.getenv("STAGE", "2")),
    "shadow_mode": os.getenv("SHADOW_MODE", "false").lower() == "true"
}
