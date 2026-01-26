from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import uuid

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
    
    # Phase 20: Performance & Actionability (Audit v6)
    decision_id: Optional[str] = None         # Immutable Causal Link
    mfe: float = 0.0          
    mae: float = 0.0          
    time_to_mfe: float = 0.0  
    spread_at_entry: float = 0.0 
    logic_version: str = "v1.2.7"

class DecisionObject(BaseModel):
    """
    Immutable binder of causality.
    Ensures that every block/approval is grounded in context.
    """
    decision_id: str
    timestamp: datetime
    features: Dict[str, float]      # Input Z-scores
    regime: Regime
    threshold: float
    confidence_boost: float
    decision: str                   # APPROVE or BLOCK
    is_actionable: bool = True
    efficacy: Optional[int] = None  # Correct (1) or Incorrect (0)
