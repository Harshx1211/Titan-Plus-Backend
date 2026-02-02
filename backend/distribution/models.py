from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class Regime(Enum):
    TRENDING = "TRENDING"
    SIDEWAYS = "SIDEWAYS"
    SIDEWAYS_STRONG = "SIDEWAYS_STRONG"
    SIDEWAYS_NORMAL = "SIDEWAYS_NORMAL"
    SIDEWAYS_WEAK = "SIDEWAYS_WEAK"
    UNCERTAIN = "UNCERTAIN"

@dataclass
class DecisionObject:
    decision_id: str
    timestamp: datetime
    features: dict
    regime: Regime
    threshold: float
    confidence_boost: float
    decision: str
    efficacy: int = 0
    is_actionable: bool = False
