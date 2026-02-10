# Startup Version Identifier [v14.0.4_NSE]
LOGIC_VERSION = "v14.0.4_NSE"

from dataclasses import dataclass
from typing import List, Dict
import os

@dataclass
class Config:
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "DEVELOPMENT")  # "DEVELOPMENT" or "PRODUCTION"
    
    # Capital & Risk
    INITIAL_CAPITAL = 100000
    MAX_RISK_PER_TRADE = 0.02  # 2%
    MAX_DAILY_LOSS = -0.05  # -5%
    MAX_OPEN_POSITIONS = 1
    
    # Brain
    DECISION_THRESHOLD = 0.60  # [v13.0.7] Lowered from 0.65 to allow more signals in sideways markets
    XGBOOST_WEIGHT = 0.40
    RL_WEIGHT = 0.30
    SMC_WEIGHT = 0.30
    
    # Execution
    ORDER_TIMEOUT = 30  # seconds
    MAX_SLIPPAGE = 10  # points
    LOT_SIZE = 75
    
    # Backtesting
    BACKTEST_START = "2024-01-01"
    BACKTEST_END = "2024-12-31"
    TRANSACTION_COST_PER_ORDER = 20.0
    
    # Broker API (Shoonya) - Load from env or use placeholders
    SHOONYA_USER = os.getenv("SHOONYA_USER", "dummy_user")
    SHOONYA_PWD = os.getenv("SHOONYA_PASSWORD", "dummy_pwd")
    SHOONYA_FACTOR2 = os.getenv("SHOONYA_FACTOR2", "dummy_dob")
    SHOONYA_VC = os.getenv("SHOONYA_VC", "dummy_vc")
    SHOONYA_API_KEY = os.getenv("SHOONYA_API_KEY", "dummy_key")
    
    # Database (Supabase)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

config = Config()
