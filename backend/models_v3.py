"""
Titan Plus - Data Models
=========================
Pydantic models for type safety and validation

Version: 9.9.9
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class MarketSource(str, Enum):
    """Data source identifier"""
    SHOONYA = "SHOONYA"
    GROWW_API = "GROWW_API"
    FALLBACK = "FALLBACK"


class Decision(str, Enum):
    """Trading decision"""
    APPROVE = "APPROVE"
    BLOCK = "BLOCK"


class Action(str, Enum):
    """RL Actions"""
    BUY_CALL = "BUY_CALL"
    BUY_PUT = "BUY_PUT"
    HOLD = "HOLD"


class Regime(str, Enum):
    """Market regime types"""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    SIDEWAYS_STRONG = "SIDEWAYS_STRONG"
    SIDEWAYS_WEAK = "SIDEWAYS_WEAK"
    NEUTRAL = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


class MarketStructure(str, Enum):
    """SMC market structure"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class DivergenceType(str, Enum):
    """Data integrity/Divergence status"""
    NONE = "NONE"
    SOFT = "SOFT"
    HARD = "HARD"


class SignalConfidence(str, Enum):
    """Trading signal confidence level"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


# ============================================================================
# Market Data Models
# ============================================================================

class MarketData(BaseModel):
    """Market snapshot data"""
    symbol: str
    spot_price: float
    future_price: float
    oi: float = 0.0
    pcr: float = 0.95
    timestamp: datetime
    source: MarketSource = MarketSource.FALLBACK
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class OHLCVCandle(BaseModel):
    """Single OHLCV candle"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Option Chain Models
# ============================================================================

class OptionStrike(BaseModel):
    """Single option strike data"""
    strike: float
    call_ltp: float
    put_ltp: float
    call_oi: float
    put_oi: float
    call_volume: int
    put_volume: int
    call_iv: float
    put_iv: float
    call_gamma: float = 0.0
    put_gamma: float = 0.0


class OptionChain(BaseModel):
    """Complete option chain"""
    symbol: str
    expiry: str
    spot_price: float
    strikes: List[OptionStrike]
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Technical Analysis Models
# ============================================================================

class TechnicalFeatures(BaseModel):
    """Technical indicator features"""
    rsi: float = Field(ge=0, le=100)
    adx: float = Field(ge=0, le=100)
    atr: float = Field(gt=0)
    basis: float
    pcr: float = Field(gt=0)
    vix: float = Field(gt=0)
    iv_skew: float = Field(gt=0)


class Greeks(BaseModel):
    """Option Greeks"""
    call_gamma: float
    put_gamma: float
    net_gex: float
    gamma_ratio: float


# ============================================================================
# SMC Models
# ============================================================================

class OrderBlockData(BaseModel):
    """Order Block detected by SMC"""
    timestamp: datetime
    price_high: float
    price_low: float
    price_mid: float
    direction: str  # BULLISH or BEARISH
    strength: float = Field(ge=0, le=1)
    volume: float
    confidence: float = Field(ge=0, le=1)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FairValueGapData(BaseModel):
    """Fair Value Gap detected by SMC"""
    timestamp: datetime
    gap_high: float
    gap_low: float
    gap_size: float
    direction: str  # BULLISH or BEARISH
    filled: bool = False
    fill_percentage: float = Field(ge=0, le=100)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LiquiditySweepData(BaseModel):
    """Liquidity Sweep detected by SMC"""
    timestamp: datetime
    swept_level: float
    sweep_type: str  # LONG_LIQUIDITY or SHORT_LIQUIDITY
    reversal: bool
    strength: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SMCAnalysis(BaseModel):
    """Complete SMC analysis result"""
    order_blocks: List[OrderBlockData]
    fair_value_gaps: List[FairValueGapData]
    liquidity_sweeps: List[LiquiditySweepData]
    market_structure: MarketStructure
    confluence_score: float = Field(ge=0, le=100)
    signals: Dict[str, bool]
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# RL Models
# ============================================================================

class RLState(BaseModel):
    """RL engine state representation"""
    indicators: TechnicalFeatures
    price: Dict[str, float]
    greeks: Greeks
    smc: Dict[str, Any]
    regime: Regime


class RLRecommendation(BaseModel):
    """RL engine recommendation"""
    action: Action
    confidence: float = Field(ge=0, le=1)
    q_values: Dict[str, float]
    source: str = "RL_ENGINE"
    epsilon: float
    episode: int


# ============================================================================
# Brain Decision Models
# ============================================================================

class XGBoostResult(BaseModel):
    """XGBoost model result"""
    probability: float = Field(ge=0, le=1)
    features_used: List[str]
    source: str


class BrainDecision(BaseModel):
    """Complete brain decision"""
    decision: Decision
    probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    components: Dict[str, Any]
    weights: Dict[str, float]
    veto_reasons: List[str]
    recommendation: Action
    source: str
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Trading Signal Models
# ============================================================================

class TradeSignal(BaseModel):
    """Trading signal for execution"""
    symbol: str
    action: Action
    strike: Optional[float] = None
    option_type: Optional[str] = None  # CE or PE
    option_symbol: Optional[str] = None
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    confidence: SignalConfidence
    regime: Optional[Regime] = None
    reasoning: Optional[str] = None
    decision_id: str
    timestamp: datetime
    divergence: DivergenceType = DivergenceType.NONE
    is_live: bool = True
    mfe: float = 0.0
    mae: float = 0.0
    is_tsl_active: bool = False
    
    # Audit & Tracking
    score: float = 0.0
    logic_version: str = "v9.9.9"
    spread_at_entry: float = 0.0
    
    # Premium Fields
    premium_entry: Optional[float] = None
    premium_sl: Optional[float] = None
    premium_target: Optional[float] = None
    
    class Config:
        extra = "allow"
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradeExecution(BaseModel):
    """Trade execution result"""
    signal_id: str
    order_id: Optional[str] = None
    status: str  # PENDING, EXECUTED, FAILED, REJECTED
    executed_price: Optional[float] = None
    executed_quantity: Optional[int] = None
    execution_time: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Snapshot Models (for database storage)
# ============================================================================

class TradeSnapshot(BaseModel):
    """Complete snapshot of a trading decision"""
    id: Optional[str] = None
    symbol: str
    regime: Regime
    features: TechnicalFeatures
    market_data: MarketData
    decision: Decision
    probability: float
    recommendation: Action
    smc_score: Optional[float] = None
    rl_action: Optional[Action] = None
    veto_reasons: List[str]
    efficacy: Optional[int] = None  # 1=win, 0=loss, None=pending
    pnl: Optional[float] = None
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Configuration Models
# ============================================================================

class SystemConfig(BaseModel):
    """System configuration"""
    decision_threshold: float = Field(ge=0.5, le=0.95, default=0.75)
    enable_rl: bool = True
    enable_smc: bool = True
    enable_telegram: bool = True
    rl_weight: float = Field(ge=0, le=1, default=0.3)
    smc_weight: float = Field(ge=0, le=1, default=0.3)
    xgb_weight: float = Field(ge=0, le=1, default=0.4)
    meta_vetoes: Dict[str, bool] = {
        'basis_instability': True,
        'vix_spike': True,
        'low_liquidity': True,
        'extreme_gex': True
    }


class EvolutionResult(BaseModel):
    """Evolution session result"""
    status: str
    date: str
    reputation_updates: Dict[str, float]
    governor_status: str
    metrics: Dict[str, float]
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# API Request/Response Models
# ============================================================================

class AnalysisRequest(BaseModel):
    """Request for SMC analysis"""
    symbol: str = "NIFTY"
    interval: str = "5minute"


class TradeSignalRequest(BaseModel):
    """Request for trade signal"""
    symbol: str = "NIFTY"
    features: Optional[TechnicalFeatures] = None


class ThresholdUpdateRequest(BaseModel):
    """Request to update decision threshold"""
    threshold: float = Field(ge=0.5, le=0.95)


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    components: Dict[str, str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
