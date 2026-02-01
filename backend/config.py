# config.py
import os

APP_CONFIG = {
    "VIX_DEFAULT": float(os.getenv("VIX_DEFAULT", "15.0")),
    "MAX_PAIN_THRESHOLD": float(os.getenv("MAX_PAIN_THRESHOLD", "20.0")),
    "HIGH_VOLATILITY_VIX": float(os.getenv("HIGH_VOLATILITY_VIX", "20.0")),
    "LULL_START_HOUR": int(os.getenv("LULL_START_HOUR", "12")),
    "LULL_START_MINUTE": int(os.getenv("LULL_START_MINUTE", "0")),
    "LULL_END_HOUR": int(os.getenv("LULL_END_HOUR", "13")),
    "LULL_END_MINUTE": int(os.getenv("LULL_END_MINUTE", "30")),
    "PASSIVE_MODE_THRESHOLD": int(os.getenv("PASSIVE_MODE_THRESHOLD", "60")), # seconds
    "PATTERN_SCORE_THRESHOLD_HIGH": float(os.getenv("PATTERN_SCORE_THRESHOLD_HIGH", "0.4")),
    "PATTERN_SCORE_THRESHOLD_MEDIUM": float(os.getenv("PATTERN_SCORE_THRESHOLD_MEDIUM", "0.2")),
    "SIGNAL_TARGET_POINTS": float(os.getenv("SIGNAL_TARGET_POINTS", "100.0")),
    "BASE_LOTS": int(os.getenv("BASE_LOTS", "1")),
    "MIN_CONFIDENCE_TO_TRADE": float(os.getenv("MIN_CONFIDENCE_TO_TRADE", "0.4")),
    "SIGNAL_STOP_LOSS_POINTS": float(os.getenv("SIGNAL_STOP_LOSS_POINTS", "50.0")),
    "ATR_MAE_MULTIPLIER": float(os.getenv("ATR_MAE_MULTIPLIER", "2.0")),
    "ATR_MAE_MIN_THRESHOLD": float(os.getenv("ATR_MAE_MIN_THRESHOLD", "20.0")),
    "DECAY_PRICE_ADVERSE_THRESHOLD": float(os.getenv("DECAY_PRICE_ADVERSE_THRESHOLD", "15.0")),
    "SIGNAL_ACTIVE_CAP": int(os.getenv("SIGNAL_ACTIVE_CAP", "20")),
    "ENGINE_POLLING_BASE_SECONDS": int(os.getenv("ENGINE_POLLING_BASE_SECONDS", "5")),
    "ENGINE_POLLING_JITTER_SECONDS": int(os.getenv("ENGINE_POLLING_JITTER_SECONDS", "2")),
    "SIDECAR_STOP_LOSS_POINTS": float(os.getenv("SIDECAR_STOP_LOSS_POINTS", "30.0")),
    "SIDECAR_TARGET_POINTS": float(os.getenv("SIDECAR_TARGET_POINTS", "100.0")),
    "SKIRMISHER_STOP_LOSS_POINTS": float(os.getenv("SKIRMISHER_STOP_LOSS_POINTS", "15.0")),
    "SKIRMISHER_TARGET_POINTS": float(os.getenv("SKIRMISHER_TARGET_POINTS", "30.0")),
    
    # Market Hours
    "MARKET_START_HOUR": int(os.getenv("MARKET_START_HOUR", "9")),
    "MARKET_START_MINUTE": int(os.getenv("MARKET_START_MINUTE", "15")),
    "MARKET_END_HOUR": int(os.getenv("MARKET_END_HOUR", "15")),
    "MARKET_END_MINUTE": int(os.getenv("MARKET_END_MINUTE", "30")),
    
    # Engine Settings
    "ENGINE_ERROR_SLEEP_TIME": int(os.getenv("ENGINE_ERROR_SLEEP_TIME", "5")),
}
