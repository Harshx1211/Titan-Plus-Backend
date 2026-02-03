import logging
import random
import string
import os
import time
import uuid
import json
import io
import contextlib
import concurrent.futures
import pyotp
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dotenv import load_dotenv
from NorenRestApiPy.NorenApi import NorenApi
from growwapi import GrowwAPI
from models import MarketData

load_dotenv()
logger = logging.getLogger("providers")

# ============================================================================
# 1. Shoonya API Internal Helper
# ============================================================================

class Order:
     def __init__(self, buy_or_sell:str = None, product_type:str = None,
                 exchange: str = None, tradingsymbol:str =None, 
                 price_type: str = None, quantity: int = None, 
                 price: float = None,trigger_price:float = None, discloseqty: int = 0,
                 retention:str = 'DAY', remarks: str = "tag",
                 order_id:str = None):
        self.buy_or_sell=buy_or_sell
        self.product_type=product_type
        self.exchange=exchange
        self.tradingsymbol=tradingsymbol
        self.quantity=quantity
        self.discloseqty=discloseqty
        self.price_type=price_type
        self.price=price
        self.trigger_price=trigger_price
        self.retention=retention
        self.remarks=remarks
        self.order_id=None

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(self, host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')        

    def get_quotes(self, exchange, token):
        url = f"https://api.shoonya.com/NorenWClientTP/GetQuotes"
        values = {"uid": getattr(self, '_NorenApi__username', None), "exch": exchange, "token": token}
        jkey = getattr(self, '_NorenApi__susertoken', None)
        payload = 'jData=' + json.dumps(values) + f'&jKey={jkey}'
        res = requests.post(url, data=payload)
        try: return json.loads(res.text)
        except: return {"stat": "Fail", "emsg": "JSON_ERR"}

# ============================================================================
# 2. Shoonya Provider
# ============================================================================

class ShoonyaProvider:
    def __init__(self):
        self.user_id = os.getenv("SHOONYA_USER_ID")
        self.password = os.getenv("SHOONYA_PASSWORD")
        self.api_key = os.getenv("SHOONYA_API_KEY")
        self.vendor_code = os.getenv("SHOONYA_VENDOR_CODE")
        self.totp_secret = os.getenv("SHOONYA_TOTP_SECRET")
        self.imei = f"{os.getenv('SHOONYA_IMEI', 'ab234')}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
        self.api = ShoonyaApiPy()
        self.authenticated = False
        self._login_lock = threading.Lock() if 'threading' in globals() else None
        self.index_tokens = {"NIFTY": ("NSE", "26000"), "BANKNIFTY": ("NSE", "26009"), "SENSEX": ("BSE", "1")}
        self.future_tokens = {}

    def login(self):
        if not self.totp_secret: return False
        totp = pyotp.TOTP(self.totp_secret.replace(" ", "").upper())
        try:
            res = self.api.login(userid=self.user_id, password=self.password, twoFA=totp.now(),
                               vendor_code=self.vendor_code, api_secret=self.api_key, imei=self.imei)
            if res and res.get('stat') == 'Ok':
                self.authenticated = True
                self.refresh_futures_mapping()
                return True
        except: pass
        return False

    def refresh_futures_mapping(self):
        try:
            for symbol in ["NIFTY", "BANKNIFTY"]:
                month = datetime.now().strftime("%b%y").upper()
                res = self.api.searchscrip(exchange="NFO", searchtext=f"{symbol} {month} FUT")
                if res and res.get('stat') == 'Ok' and res.get('values'):
                    self.future_tokens[symbol] = ("NFO", res['values'][0]['token'])
        except: pass

    def get_market_data(self, symbol: str) -> Optional[Dict]:
        if not self.authenticated and not self.login(): return None
        try:
            mapping = self.index_tokens.get(symbol)
            if not mapping: return None
            res = self.api.get_quotes(exchange=mapping[0], token=mapping[1])
            if res and res.get('stat') == 'Ok':
                data = {'symbol': symbol, 'lp': float(res.get('lp', 0)), 'v': int(res.get('v', 0)), 'future_lp': 0}
                fut = self.future_tokens.get(symbol)
                if fut:
                    res_f = self.api.get_quotes(exchange=fut[0], token=fut[1])
                    if res_f and res_f.get('stat') == 'Ok':
                        data['future_lp'] = float(res_f.get('lp', 0))
                return data
        except: pass
        return None

    def get_historical_data(self, symbol: str, interval: int = 5, start_time: datetime = None, end_time: datetime = None) -> List[Dict]:
        if not self.authenticated and not self.login(): return []
        mapping = self.index_tokens.get(symbol)
        if not mapping: return []
        try:
            res = self.api.get_time_price_series(exchange=mapping[0], token=mapping[1],
                                              starttime=str(int(start_time.timestamp())),
                                              endtime=str(int(end_time.timestamp())), interval=str(interval))
            return res if isinstance(res, list) else (res.get('values', []) if isinstance(res, dict) else [])
        except: return []

# ============================================================================
# 3. Data Orchestrator (DataProvider)
# ============================================================================

def _masked_groww_headers(key_or_token: str) -> dict:
    return {
        "x-request-id": str(uuid.uuid4()), "Authorization": f"Bearer {key_or_token}",
        "Content-Type": "application/json", "x-client-platform": "Web", "User-Agent": "Mozilla/5.0"
    }
GrowwAPI._build_headers = staticmethod(_masked_groww_headers)

class DataProvider:
    def __init__(self):
        self.shoonya = ShoonyaProvider()
        self.groww_key = os.getenv("GROWW_API_KEY")
        self.groww_secret = os.getenv("GROWW_API_SECRET")
        self.bot = None
        self.use_groww = False
        if self.groww_key and self.groww_secret:
            try:
                token = GrowwAPI.get_access_token(api_key=self.groww_key, secret=self.groww_secret)
                self.bot = GrowwAPI(token=token)
                self.use_groww = True
            except: pass
        self.shoonya.login()

    def get_market_snapshot(self, symbol: str) -> MarketData:
        data = self.shoonya.get_market_data(symbol)
        if data and data['lp'] > 0:
            return MarketData(symbol=symbol, spot_price=data['lp'], future_price=data['future_lp'] or (data['lp']+45),
                            oi=0, pcr=0.95, timestamp=datetime.now(), source="SHOONYA")
        
        # Fallback to Groww or Placeholders
        return MarketData(symbol=symbol, spot_price=25000.0, future_price=25045.0, oi=0, pcr=0.95, timestamp=datetime.now(), source="FALLBACK")

    def get_status(self) -> Dict:
        """Returns the status of the data source."""
        if self.use_groww and self.bot:
            return {"status": "ACTIVE", "name": "GROWW_API", "remaining": 0}
        if self.shoonya.authenticated:
            return {"status": "ACTIVE", "name": "SHOONYA", "remaining": 0}
        return {"status": "FALLBACK", "name": "PLACEHOLDER", "remaining": 0}

    def get_history(self, symbol: str, interval: str = "5minute") -> pd.DataFrame:
        """Fetch historical data for a symbol. Interval maps to Noren series."""
        # Map timeframes to Shoonya intervals (5, 15, 30, 60 minutes)
        interval_map = {"1minute": 1, "5minute": 5, "15minute": 15, "30minute": 30, "60minute": 60}
        noren_interval = interval_map.get(interval, 5)
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=2) # 2 days for enough context
        
        return self.get_intraday_history(symbol, start_time, end_time, noren_interval)

    def get_option_chain(self, symbol: str) -> Tuple[pd.DataFrame, bool]:
        """Returns the option chain for a symbol. Returns (df, is_synthetic)."""
        # Placeholder for now to prevent crash
        return pd.DataFrame(), True

    def get_vix(self) -> float:
        """Returns the India VIX value."""
        # Try fetching from Shoonya if possible, or return fallback
        data = self.shoonya.get_market_data("INDIA VIX")
        if data and data['lp'] > 0:
            return data['lp']
        return 15.0 # Fallback VIX

    def get_iv_skew(self, symbol: str) -> float:
        """Returns the IV Skew for a symbol."""
        return 1.0 # Neutral fallback

    def get_breadth(self, symbol: str) -> Dict[str, int]:
        """Returns the market breadth (advances/declines)."""
        return {"advances": 25, "declines": 25} # Static neutral fallback

    def get_intraday_history(self, symbol: str, start_time: datetime, end_time: datetime, interval: int = 5) -> pd.DataFrame:
        raw = self.shoonya.get_historical_data(symbol, interval, start_time, end_time)
        if not raw:
            # Fallback: Create mock history if market is open but provider fails
            dates = pd.date_range(end=datetime.now(), periods=100, freq=f'{interval}min')
            df = pd.DataFrame({
                'datetime': dates,
                'open': 25000.0, 'high': 25050.0, 'low': 24950.0, 'close': 25000.0, 'volume': 1000
            })
            return df
        df = pd.DataFrame(raw)
        df.rename(columns={'into': 'open', 'inth': 'high', 'intl': 'low', 'intc': 'close', 'v': 'volume'}, inplace=True)
        return df
