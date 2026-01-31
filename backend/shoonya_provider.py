import logging
import os
import pyotp
import time
import threading
from typing import Optional, Dict, List
from api_helper import ShoonyaApiPy
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ShoonyaProvider:
    def __init__(self):
        self.user_id = os.getenv("SHOONYA_USER_ID")
        self.password = os.getenv("SHOONYA_PASSWORD")
        self.api_key = os.getenv("SHOONYA_API_KEY")
        # Handle the typo in the Render dashboard just in case
        self.imei = os.getenv("SHOONYA_IMEI") or os.getenv("SHOONYA_INEI") or 'ab234'
        self.vendor_code = os.getenv("SHOONYA_VENDOR_CODE")
        self.totp_secret = os.getenv("SHOONYA_TOTP_SECRET")
        
        # Use the verified endpoint from api_helper
        self.api = ShoonyaApiPy()
        self.authenticated = False
        self._login_lock = threading.Lock()
        self._last_login_attempt = 0
        self._login_cooldown = 10 # Seconds
        
        # Standard Index Token Mappings (Exchange, Token)
        self.index_tokens = {
            "NIFTY": ("NSE", "26000"),
            "BANKNIFTY": ("NSE", "26009"),
            "FINNIFTY": ("NSE", "26037"),
            "SENSEX": ("BSE", "1")
        }

    def login(self):
        with self._login_lock:
            # Check if another thread already logged in while we were waiting for the lock
            if self.authenticated and (time.time() - self._last_login_attempt) < 60:
                return True
                
            now = time.time()
            if (now - self._last_login_attempt) < self._login_cooldown:
                logger.warning(f"Shoonya login throttled. Waiting {self._login_cooldown}s between attempts.")
                return False
                
            self._last_login_attempt = now
            
            if not self.totp_secret:
                logger.error("No SHOONYA_TOTP_SECRET found in .env")
                return False
                
            totp_key = self.totp_secret.replace(" ", "").upper()
            totp = pyotp.TOTP(totp_key)
            
            # Try multiple time windows (±2 minutes) to account for clock drift
            offsets = [0, -30, 30, -60, 60, -90, 90, -120, 120]
            
            for offset in offsets:
                try:
                    code = totp.at(int(now) + offset)
                    
                    res = self.api.login(
                        userid=self.user_id,
                        password=self.password,
                        twoFA=code,
                        vendor_code=self.vendor_code,
                        api_secret=self.api_key,
                        imei=self.imei
                    )
                    
                    if res and res.get('stat') == 'Ok':
                        self.authenticated = True
                        logger.info(f"Shoonya Login SUCCESSFUL! (Offset: {offset}s)")
                        return True
                    
                    error_msg = res.get('emsg') if res else 'No response'
                    logger.info(f"Login attempt failed (Offset {offset}s): {error_msg}")
                    
                    if res and 'Invalid OTP' not in str(error_msg):
                        logger.warning(f"Aborting login retries due to non-OTP error: {error_msg}")
                        break
                        
                except Exception as e:
                    logger.error(f"Critical exception during login attempt: {e}")
                    break
                    
            logger.error(f"Shoonya login failed for all offsets. Last error: {error_msg if 'error_msg' in locals() else 'None'}")
            return False

    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Fetch market data for a given symbol or index."""
        if not self.authenticated:
            if not self.login():
                return None
        
        try:
            mapping = self.index_tokens.get(symbol)
            if not mapping:
                return None
                
            exchange, token = mapping
            
            # Deep Diagnostic for Render
            logger.debug(f"Fetching quotes for {symbol} ({exchange}:{token})...")
            res = self.api.get_quotes(exchange=exchange, token=token)
            
            if res and res.get('stat') == 'Ok':
                return {
                    'symbol': symbol,
                    'lp': float(res.get('lp', 0)),
                    'pc': float(res.get('pc', 0)),
                    'v': int(res.get('v', 0)),
                    'timestamp': res.get('request_time')
                }
            else:
                emsg = res.get('emsg', '') if res else 'No response'
                
                # [v9.6.3] Session Management: Handle Session Expiry
                if "Session Expired" in str(emsg):
                    logger.warning(f"Shoonya Session Expired. Attempting auto-relogin...")
                    self.authenticated = False 
                    if self.login():
                        return self.get_market_data(symbol) # Retry once
                
                # [v9.6.1] SDK Patch results in detailed error reporting
                logger.error(f"Failed to fetch quotes for {symbol}: {emsg}")
                
                if not res or emsg == 'No response':
                    try:
                        import requests
                        test_res = requests.get("https://api.shoonya.com/NorenWClientTP/", timeout=5)
                        logger.info(f"Shoonya Connectivity Test: Status {test_res.status_code}")
                    except Exception as con_err:
                        logger.error(f"Shoonya Connectivity Test FAILED: {con_err}")
                return None
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    def get_live_data(self, symbols: List[str]):
        """Websocket implementation to be added in next phase"""
        return {}
