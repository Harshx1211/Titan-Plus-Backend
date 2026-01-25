from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

class Regime(Enum):
    TRENDING = "TRENDING"
    SIDEWAYS = "SIDEWAYS"
    UNCERTAIN = "UNCERTAIN"

class DivergenceType(Enum):
    NONE = "NONE"
    SOFT = "SOFT"
    HARD = "HARD"

class MarketData(BaseModel):
    symbol: str
    spot_price: float
    future_price: float
    oi: int
    pcr: float
    timestamp: datetime

class SignalConfidence(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class TradeSignal(BaseModel):
    symbol: str
    entry_price: float # Index Spot Price
    stop_loss: float
    target: float
    confidence: SignalConfidence
    regime: Regime
    reasoning: str
    timestamp: datetime
    is_live: bool = True
    divergence: DivergenceType = DivergenceType.NONE
    
    # Phase 15: Executable Option Fields
    option_symbol: Optional[str] = None      # e.g., NIFTY 24500 PE
    premium_entry: Optional[float] = None    # Buy @ 150
    premium_sl: Optional[float] = None       # SL @ 140
    premium_target: Optional[float] = None   # Target @ 190
    strike: Optional[int] = None
    option_type: Optional[str] = None        # CE or PE
