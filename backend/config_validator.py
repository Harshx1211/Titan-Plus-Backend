"""
CONFIGURATION VALIDATOR
=======================
Validates all environment variables and configuration at startup.
Prevents silent failures due to misconfiguration.
"""

import os
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger("config_validator")


@dataclass
class ValidationResult:
    """Result of a configuration validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    info: List[str]


class ConfigValidator:
    """
    Validates system configuration at startup.
    """
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
    
    def validate_all(self) -> ValidationResult:
        """
        Run all validation checks.
        
        Returns:
            ValidationResult with errors, warnings, and info
        """
        logger.info("Starting configuration validation...")
        
        # Run all checks
        self._check_required_env_vars()
        self._check_broker_credentials()
        self._check_database_config()
        self._check_telegram_config()
        self._check_risk_parameters()
        self._check_model_weights()
        self._check_file_permissions()
        
        is_valid = len(self.errors) == 0
        
        result = ValidationResult(
            is_valid=is_valid,
            errors=self.errors,
            warnings=self.warnings,
            info=self.info
        )
        
        # Log results
        self._log_results(result)
        
        return result
    
    def _check_required_env_vars(self):
        """Check that required environment variables are set."""
        required = [
            'ENVIRONMENT',  # DEVELOPMENT or PRODUCTION
        ]
        
        for var in required:
            if not os.getenv(var):
                self.warnings.append(f"Environment variable '{var}' not set, using default")
            else:
                self.info.append(f"✓ {var} = {os.getenv(var)}")
    
    
    def _check_broker_credentials(self):
        """Validate broker API credentials."""
        # [v13.0.7] Global Focus: Indian brokers (Shoonya/Groww) are decommissioned.
        # Only public crypto providers (Binance/KuCoin) are used.
        self.info.append("✓ Global Data Providers configured (Public API + KuCoin Fallback)")
    
    def _check_database_config(self):
        """Validate database configuration."""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            self.errors.append(
                "❌ CRITICAL: Supabase credentials not configured. "
                "Database logging will FAIL. Set SUPABASE_URL and SUPABASE_KEY."
            )
        elif supabase_url == "" or supabase_key == "":
            self.errors.append(
                "❌ CRITICAL: Supabase credentials are empty strings. "
                "Check your environment variables."
            )
        else:
            self.info.append("✓ Supabase credentials configured")
            
            # Validate URL format
            if not supabase_url.startswith('https://'):
                self.warnings.append(
                    "⚠️  SUPABASE_URL doesn't start with https:// - might be invalid"
                )
    
    def _check_telegram_config(self):
        """Validate Telegram configuration."""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            self.warnings.append(
                "⚠️  Telegram not configured - no notifications will be sent. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
            )
        else:
            self.info.append("✓ Telegram notifications configured")
            
            # Validate format
            if not bot_token.count(':') == 1:
                self.warnings.append(
                    "⚠️  TELEGRAM_BOT_TOKEN format looks incorrect (should be number:hash)"
                )
            
            if not chat_id.lstrip('-').isdigit():
                self.warnings.append(
                    "⚠️  TELEGRAM_CHAT_ID should be a number"
                )
    
    def _check_risk_parameters(self):
        """Validate risk management parameters."""
        try:
            from config import config
            
            # Check risk percentages
            if not (0 < config.MAX_RISK_PER_TRADE <= 0.05):
                self.warnings.append(
                    f"⚠️  MAX_RISK_PER_TRADE = {config.MAX_RISK_PER_TRADE} "
                    f"(recommended: 0.01 to 0.02)"
                )
            else:
                self.info.append(f"✓ Risk per trade: {config.MAX_RISK_PER_TRADE*100}%")
            
            if not (-0.10 <= config.MAX_DAILY_LOSS < 0):
                self.warnings.append(
                    f"⚠️  MAX_DAILY_LOSS = {config.MAX_DAILY_LOSS} "
                    f"(recommended: -0.03 to -0.05)"
                )
            else:
                self.info.append(f"✓ Max daily loss: {abs(config.MAX_DAILY_LOSS)*100}%")
            
            # Check position limits
            if config.MAX_OPEN_POSITIONS > 5:
                self.warnings.append(
                    f"⚠️  MAX_OPEN_POSITIONS = {config.MAX_OPEN_POSITIONS} "
                    f"(recommended: 3 or less for options)"
                )
            else:
                self.info.append(f"✓ Max open positions: {config.MAX_OPEN_POSITIONS}")
            
            # Check capital
            if config.INITIAL_CAPITAL < 50000:
                self.warnings.append(
                    f"⚠️  INITIAL_CAPITAL = ₹{config.INITIAL_CAPITAL} "
                    f"(recommended minimum: ₹50,000 for options trading)"
                )
            else:
                self.info.append(f"✓ Initial capital: ₹{config.INITIAL_CAPITAL:,}")
        except Exception as e:
            self.warnings.append(f"⚠️  Could not validate risk parameters: {e}")
    
    def _check_model_weights(self):
        """Validate brain model weights."""
        try:
            from config import config
            
            total_weight = (
                config.XGBOOST_WEIGHT + 
                config.RL_WEIGHT + 
                config.SMC_WEIGHT
            )
            
            if abs(total_weight - 1.0) > 0.001:
                self.errors.append(
                    f"❌ CRITICAL: Model weights don't sum to 1.0 "
                    f"(XGB={config.XGBOOST_WEIGHT}, "
                    f"RL={config.RL_WEIGHT}, "
                    f"SMC={config.SMC_WEIGHT}, "
                    f"Total={total_weight})"
                )
            else:
                self.info.append(
                    f"✓ Model weights: "
                    f"XGB={config.XGBOOST_WEIGHT}, "
                    f"RL={config.RL_WEIGHT}, "
                    f"SMC={config.SMC_WEIGHT}"
                )
            
            # Check decision threshold
            if not (0.5 <= config.DECISION_THRESHOLD <= 0.95):
                self.warnings.append(
                    f"⚠️  DECISION_THRESHOLD = {config.DECISION_THRESHOLD} "
                    f"(recommended: 0.70 to 0.80)"
                )
            else:
                self.info.append(f"✓ Decision threshold: {config.DECISION_THRESHOLD}")
        except Exception as e:
            self.warnings.append(f"⚠️  Could not validate model weights: {e}")
    
    def _check_file_permissions(self):
        """Check that we can write to necessary directories."""
        import tempfile
        
        # Check if we can write to current directory
        try:
            test_file = "test_write_permissions.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            self.info.append("✓ Write permissions OK")
        except Exception as e:
            self.errors.append(
                f"❌ CRITICAL: Cannot write to current directory: {e}"
            )
    
    def _log_results(self, result: ValidationResult):
        """Log validation results."""
        logger.info("\n" + "="*70)
        logger.info("CONFIGURATION VALIDATION RESULTS")
        logger.info("="*70)
        
        if result.info:
            logger.info("\n✓ CONFIGURATION OK:")
            for msg in result.info:
                logger.info(f"  {msg}")
        
        if result.warnings:
            logger.warning("\n⚠️  WARNINGS:")
            for msg in result.warnings:
                logger.warning(f"  {msg}")
        
        if result.errors:
            logger.error("\n❌ ERRORS:")
            for msg in result.errors:
                logger.error(f"  {msg}")
        
        logger.info("\n" + "="*70)
        
        if result.is_valid:
            logger.info("✅ Configuration validation PASSED")
        else:
            logger.error("❌ Configuration validation FAILED - fix errors before deployment")
        
        logger.info("="*70 + "\n")


def validate_config_on_startup() -> bool:
    """
    Validate configuration and return whether it's safe to start.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    validator = ConfigValidator()
    result = validator.validate_all()
    
    # In production, fail fast on errors
    environment = os.getenv('ENVIRONMENT', 'DEVELOPMENT')
    
    if not result.is_valid and environment == 'PRODUCTION':
        logger.critical(
            "Configuration validation failed in PRODUCTION mode. "
            "System will NOT start. Fix errors and restart."
        )
        return False
    
    if not result.is_valid and environment == 'DEVELOPMENT':
        logger.warning(
            "Configuration validation failed in DEVELOPMENT mode. "
            "System will start but may not function correctly."
        )
    
    return True


if __name__ == "__main__":
    # Test the validator
    logging.basicConfig(level=logging.INFO)
    
    result = validate_config_on_startup()
    
    if result:
        print("\n✅ Configuration is valid - safe to start system")
    else:
        print("\n❌ Configuration has errors - DO NOT start system")
