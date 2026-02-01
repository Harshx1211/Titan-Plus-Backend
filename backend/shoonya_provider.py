import logging
import random
import string
import os
import pyotp
import time
import threading
from datetime import datetime
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
        self.vendor_code = os.getenv("SHOONYA_VENDOR_CODE")
        self.totp_secret = os.getenv("SHOONYA_TOTP_SECRET")
        
        # [v9.6.5] Unique Identity: Randomize IMEI suffix to prevent session collisions
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        raw_imei = os.getenv("SHOONYA_IMEI") or os.getenv("SHOONYA_INEI") or 'ab234'
        self.imei = f"{raw_imei}_{suffix}"
        
        logger.info(f"Shoonya: Identity initialized as {self.imei}")
        
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
        
        # [v9.7] Dynamic Futures Discovery
        self.future_tokens = {} # {symbol: (exchange, token)}

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
            
            # 1. Get Spot Data
            res = self.api.get_quotes(exchange=exchange, token=token)
            
            data = {'symbol': symbol, 'lp': 0, 'pc': 0, 'v': 0, 'future_lp': 0, 'oi': 0}
            
            if res and res.get('stat') == 'Ok':
                data['lp'] = float(res.get('lp', 0))
                data['pc'] = float(res.get('pc', 0))
                data['v'] = int(res.get('v', 0))
                data['timestamp'] = res.get('request_time')
            
            # 2. Get Future Data (v9.7 - Hardened Basis)
            fut_mapping = self.future_tokens.get(symbol)
            if fut_mapping:
                f_exch, f_token = fut_mapping
                res_f = self.api.get_quotes(exchange=f_exch, token=f_token)
                if res_f and res_f.get('stat') == 'Ok':
                    data['future_lp'] = float(res_f.get('lp', 0))
                    data['oi'] = int(res_f.get('oi', 0))
                    logger.debug(f"Shoonya: Fetched real future for {symbol}: {data['future_lp']}")
            
            if data['lp'] > 0:
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    def refresh_futures_mapping(self):
        """
        [v9.7] Discovers the current month's future tokens for indices.
        """
        try:
            from datetime import datetime
            for symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                # Shoonya search format: Nifty <MONTH><YY> FUT (No space sometimes or specific format)
                # Actually, NIFTY <MONTH> FUT is common.
                current_month = datetime.now().strftime("%b%y").upper()
                search_text = f"{symbol} {current_month} FUT"
                
                res = self.api.searchscrip(exchange="NFO", searchtext=search_text)
                if res and res.get('stat') == 'Ok' and res.get('values'):
                    for val in res['values']:
                        if "FUT" in val.get('tsym', ''):
                            self.future_tokens[symbol] = ("NFO", val['token'])
                            logger.info(f"Shoonya: Mapped {symbol} Future -> {val['tsym']} ({val['token']})")
                            break
        except Exception as e:
            logger.error(f"Shoonya: Failed to refresh futures mapping: {e}")

    def login(self):
        with self._login_lock:
            # Check if another thread already logged in while we were waiting for the lock
            if self.authenticated and (time.time() - self._last_login_attempt) < 300: # 5 mins
                return True
                
            now = time.time()
            if (now - self._last_login_attempt) < self._login_cooldown:
                logger.warning(f"Shoonya login throttled. Waiting {self._login_cooldown}s between attempts.")
                return False
                
            self._last_login_attempt = now
            self.authenticated = False # Reset before attempt
            
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
                        # [v9.7] Discover futures after login
                        self.refresh_futures_mapping()
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

    def get_historical_data(self, symbol: str, interval: int = 5, start_time: datetime = None, end_time: datetime = None) -> List[Dict]:
        """
        [v9.8] Fetches intraday historical data for simulation.
        interval: 1, 3, 5, 10, 15, 30, 60, 120, 240
        """
        if not self.authenticated:
            if not self.login():
                 return []
                 
        mapping = self.index_tokens.get(symbol)
        if not mapping:
            return []
            
        exchange, token = mapping
        
        # Format times for Shoonya (Epoch)
        s_time = int(start_time.timestamp()) if start_time else int(time.time()) - 86400
        e_time = int(end_time.timestamp()) if end_time else int(time.time())
        
        try:
            # [Fix] Shoonya sometimes fails if start_time is too far back or too close.
            # Convert to strings as required by some versions of the helper
            res = self.api.get_time_price_series(
                exchange=exchange,
                token=token,
                starttime=str(s_time),
                endtime=str(e_time),
                interval=str(interval)
            )
            
            if isinstance(res, list):
                logger.info(f"Shoonya: Fetched {len(res)} candles for {symbol}")
                return res
            elif isinstance(res, dict) and res.get('stat') == 'Ok':
                data = res.get('values', [])
                logger.info(f"Shoonya: Fetched {len(data)} candles (Ok) for {symbol}")
                return data
            else:
                # If NIFTY fails, sometimes it needs the INDEX token check
                logger.warning(f"Shoonya: Retry history for {symbol} with direct token... Raw Res: {res}")
                return []
        except Exception as e:
            logger.error(f"Shoonya: History exception for {symbol}: {e}")
            return []

    def get_live_data(self, symbols: List[str]):
        """Websocket implementation to be added in next phase"""
        return {}
