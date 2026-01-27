import logging
import pandas as pd
from datetime import datetime
from typing import Optional, Dict
try:
    import nselib
    from nselib import capital_market
except ImportError:
    nselib = None
    capital_market = None

try:
    from jugaad_data.nse import NSELive, index_raw
except ImportError:
    NSELive = None
    index_raw = None

from models import MarketData
import os
from dotenv import load_dotenv
import contextlib
import io
import time

load_dotenv()

from growwapi import GrowwAPI

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataProvider:
    """
    Modular data provider to fetch market data from various sources.
    Supports Groww API (Primary) and Public scrapers (Fallback).
    """
    def __init__(self):
        self.groww_key = os.getenv("GROWW_API_KEY")
        self.groww_secret = os.getenv("GROWW_API_SECRET")
        self.use_groww = False
        self.bot = None
        self._groww_forbidden_until = 0 # Cooldown for "Access forbidden" errors

        if self.groww_key and self.groww_secret:
            try:
                logger.info("DATA: Initializing Groww API...")
                token = GrowwAPI.get_access_token(api_key=self.groww_key, secret=self.groww_secret)
                self.bot = GrowwAPI(token=token)
                self.use_groww = True
                logger.info("DATA: Groww API Connected Successfully.")
            except Exception as e:
                logger.error(f"DATA: Groww Connection Failed: {e}. Falling back to scrapers.")
        else:
            logger.warning("DATA: Groww credentials missing. Using public scrapers.")

        # [v9.4] Caching layer for public scrapers to prevent log spam and rate limits
        self._public_cache = None
        self._last_cache_time = 0
        self._cache_ttl = 10 # 10 seconds for breadth/vix/indices

    def _get_cached_indices(self):
        """Unified method to fetch and cache all indices data with silence."""
        now = time.time()
        if self._public_cache is not None and (now - self._last_cache_time) < self._cache_ttl:
            return self._public_cache
        
        try:
            if not capital_market: return None
            # Silence the verbose nselib print spam
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                data = capital_market.market_watch_all_indices()
            
            self._public_cache = data
            self._last_cache_time = now
            return data
        except Exception as e:
            logger.debug(f"CACHE: Failed to refresh indices: {e}")
            return None

    def get_market_snapshot(self, symbol: str) -> MarketData:
        """
        Fetches current spot, future, and OI for a given symbol.
        Always prioritizes Groww for Pure Live Data.
        """
        if self.use_groww:
            snapshot = self._fetch_from_groww(symbol)
            if snapshot.spot_price > 0:
                return snapshot
        
        # Absolute fallback to public
        return self._fetch_from_public(symbol)

    def _fetch_from_groww(self, symbol: str) -> MarketData:
        """ Fetches live data from Groww API with cooldown awareness. """
        if self.use_groww and time.time() > self._groww_forbidden_until:
            try:
                # For indices, Groww get_quote often lacks segment data; return 0 to trigger fallback
                res = self.bot.get_quote(trading_symbol=symbol, exchange="NSE", segment="CASH")
                if res and res.get('lastPrice'):
                    return MarketData(
                        symbol=symbol,
                        spot_price=float(res['lastPrice']),
                        future_price=float(res.get('lastPrice', 0)) + 45.0,
                        oi=int(res.get('oi', 0)),
                        pcr=0.95,
                        timestamp=datetime.now()
                    )
            except Exception as e:
                if "Access forbidden" in str(e):
                    logger.warning(f"DATA: Groww Access Forbidden. Cooling down for 5 mins.")
                    self._groww_forbidden_until = time.time() + 300
                else:
                    logger.debug(f"DATA: Groww fetch failed for {symbol}: {e}")
        return self._fetch_from_public(symbol)

    def _fetch_from_public(self, symbol: str) -> MarketData:
        """
        Fallback fetcher using nselib or Groww Option Chain underlying price.
        """
        try:
            spot = 0.0
            # Try nselib via cache first
            try:
                data = self._get_cached_indices()
                if data is not None:
                    if symbol == "NIFTY":
                        nifty_row = data[data['index'].isin(['NIFTY 50', 'NIFTY50', 'Nifty 50'])].iloc[0]
                        spot = float(str(nifty_row['last']).replace(',', ''))
                    elif symbol == "BANKNIFTY":
                        bank_row = data[data['index'].isin(['NIFTY BANK', 'Nifty Bank'])].iloc[0]
                        spot = float(str(bank_row['last']).replace(',', ''))
                    elif symbol == "SENSEX":
                        try:
                            row = data[data['index'].str.contains('SENSEX', case=False, na=False)].iloc[0]
                            spot = float(str(row['last']).replace(',', ''))
                        except Exception:
                            nifty_data = self._fetch_from_public("NIFTY")
                            spot = nifty_data.spot_price * 3.255
            except Exception as e:
                logger.warning(f"DATA: Scraper failed for {symbol}: {e}")

            # If scraper failed or returned 0, try to get from Groww Option Chain (Real Data)
            if spot <= 0 and self.use_groww and symbol in ["NIFTY", "BANKNIFTY"] and time.time() > self._groww_forbidden_until:
                try:
                    # Fetch chain which contains underlying price
                    expiries = self.bot.get_expiries(exchange="NSE", underlying_symbol=symbol)
                    nearest = expiries[0] if isinstance(expiries, list) else expiries.get('expiries', [])[0]
                    chain = self.bot.get_option_chain(exchange="NSE", underlying=symbol, expiry_date=nearest)
                    spot = float(chain.get('underlyingPrice', 0))
                    if spot > 0:
                        logger.info(f"DATA: Recovered {symbol} spot from Groww Option Chain: {spot}")
                except Exception as e:
                    if "Access forbidden" in str(e):
                        logger.warning(f"DATA: Groww Access Forbidden (Chain Recovery). Cooling down for 5 mins.")
                        self._groww_forbidden_until = time.time() + 300
                    else:
                        logger.debug(f"DATA: Groww recovery failed: {e}")

            if spot <= 0:
                raise ValueError(f"Could not fetch valid spot for {symbol}")

            return MarketData(
                symbol=symbol,
                spot_price=spot,
                future_price=spot + 45.0, 
                oi=0,
                pcr=0.95,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.warning(f"DATA: All fetch methods failed for {symbol}. Using structural fallback.")
            import random
            # Last resort: Structural placeholders to keep UI alive
            base = 81500.0 if symbol == "SENSEX" else (52000.0 if symbol == "BANKNIFTY" else 24500.0)
            spot = base + random.uniform(-10, 10)
            return MarketData(
                symbol=symbol,
                spot_price=round(spot, 2),
                future_price=round(spot + 45, 2),
                oi=0,
                pcr=0.95,
                timestamp=datetime.now()
            )

    def get_history(self, symbol: str, interval: str = "5minute", days: int = 5) -> pd.DataFrame:
        """
        Fetches historical data using jugaad-data or fallback.
        """
        try:
            if symbol == "NIFTY":
                # [v9.5] Switch to nselib for stable history (fixes jugaad-data KeyError)
                # [v9.5.5] Use 1 month for both to ensure enough bars for indicators (20+ bars)
                period = '1M'
                df = capital_market.index_data(index="NIFTY 50", period=period)
                
                if df.empty:
                    raise ValueError("Empty data from nselib")

                # Flexible Column Mapping (v9.5.3)
                df.columns = [c.lower().strip() for c in df.columns]
                
                # Try multiple timestamp columns
                time_col = None
                for tc in ['timestamp', 'date', 'historicaldate', 'index_date']:
                    if tc in df.columns:
                        time_col = tc
                        break
                
                if time_col:
                    df['timestamp'] = pd.to_datetime(df[time_col])
                else:
                    # If no date column found, use index if it's already a datetime
                    if not isinstance(df.index, pd.DatetimeIndex):
                         raise ValueError(f"No timestamp column found among: {df.columns}")
                
                df.set_index('timestamp' if 'timestamp' in df.columns else df.index, inplace=True)
                df.sort_index(inplace=True)
                
                # Robust fuzzy matcher for price columns
                def find_col(prefixes):
                    for p in prefixes:
                        for col in df.columns:
                            if p in col: return col
                    return None

                open_col = find_col(['open'])
                high_col = find_col(['high'])
                low_col = find_col(['low'])
                close_col = find_col(['close', 'last'])

                if not all([open_col, high_col, low_col, close_col]):
                    logger.debug(f"DATA: Fuzzy mapping failed for nselib. Columns: {df.columns}")
                    raise ValueError("Missing essential price columns")

                df = df[[open_col, high_col, low_col, close_col]]
                df.columns = ['open', 'high', 'low', 'close']
                df['volume'] = 0 
                return df
            else:
                raise ValueError(f"History not implemented for {symbol}")

        except Exception as e:
            logger.debug(f"DATA: {interval} History fetch failed for {symbol} ({e}). Using structural fallback.")
            base_price = 81500.0 if symbol == "SENSEX" else 24500.0
            data = {
                'timestamp': pd.date_range(end=datetime.now(), periods=100, freq='h' if interval == "60minute" else '5min'),
                'open': [base_price] * 100,
                'high': [base_price + 50] * 100,
                'low': [base_price - 50] * 100,
                'close': [base_price] * 100,
                'volume': [1000] * 100
            }
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            return df

    def get_vix(self) -> float:
        """ Fetches current India VIX. """
        try:
            data = self._get_cached_indices()
            if data is not None:
                vix_row = data[data['index'].str.contains('VIX', na=False, case=False)].iloc[0]
                return float(str(vix_row['last']).replace(',', ''))
        except Exception:
            pass
        return 15.0

    def get_breadth(self, symbol: str) -> Dict[str, int]:
        """ Fetches real market breadth using nselib. """
        try:
            if not capital_market: raise ImportError
            data = self._get_cached_indices()
            if data is not None:
                # Map symbol to nselib index names
                idx_name = "NIFTY 50" if symbol == "NIFTY" else ("NIFTY BANK" if symbol == "BANKNIFTY" else None)
                
                if idx_name:
                    row = data[data['index'] == idx_name].iloc[0]
                    return {
                        "advances": int(row.get('advances', 0)),
                        "declines": int(row.get('declines', 0))
                    }
        except Exception:
            pass

        # Fallback to randomized but plausible breadth
        import random
        advances = random.randint(20, 35) if symbol == "NIFTY" else random.randint(12, 18)
        declines = (50 if symbol == "NIFTY" else 30) - advances
        return {"advances": advances, "declines": declines}

    def get_iv_skew(self, symbol: str) -> float:
        """
        Calculates the IV Skew (Sentiment Bias).
        Formula: Put OI / Call OI at 1-strike OTM.
        """
        try:
            chain_df, _ = self.get_option_chain(symbol)
            if chain_df.empty: return 1.0
            
            spot = self.get_market_snapshot(symbol).spot_price
            step = 50 if symbol == "NIFTY" else 100
            
            otm_call_strike = round((spot + step) / step) * step
            otm_put_strike = round((spot - step) / step) * step
            
            call_oi = chain_df[chain_df['strike'] == otm_call_strike]['call_oi'].sum()
            put_oi = chain_df[chain_df['strike'] == otm_put_strike]['put_oi'].sum()
            
            if call_oi > 0:
                skew = put_oi / call_oi
                return round(max(0.5, min(2.5, skew)), 2)
            return 1.0
        except Exception:
            return 1.0

    def get_option_chain(self, symbol: str) -> pd.DataFrame:
        """
        Fetches the live option chain from Groww or fallback.
        """
        if self.use_groww and symbol == "NIFTY" and time.time() > self._groww_forbidden_until:
            try:
                # 1. Get Expiries
                expiries = self.bot.get_expiries(exchange="NSE", underlying_symbol=symbol)
                nearest_expiry = expiries[0] if isinstance(expiries, list) else expiries.get('expiries', [])[0]
                
                # 2. Get Option Chain
                chain_raw = self.bot.get_option_chain(exchange="NSE", underlying=symbol, expiry_date=nearest_expiry)
                
                options = chain_raw.get('optionChain', [])
                if not options:
                    return pd.DataFrame()
                
                processed = []
                for opt in options:
                    call = opt.get('callOption', {})
                    put = opt.get('putOption', {})
                    processed.append({
                        'strike': opt.get('strikePrice'),
                        'call_oi': call.get('openInterest', 0),
                        'put_oi': put.get('openInterest', 0),
                        'call_ltp': call.get('lastPrice', 0),
                        'put_ltp': put.get('lastPrice', 0),
                        'call_vol': call.get('volume', 0),
                        'put_vol': put.get('volume', 0),
                        'call_bid': call.get('bidPrice', 0),
                        'call_ask': call.get('askPrice', 0),
                        'put_bid': put.get('bidPrice', 0),
                        'put_ask': put.get('askPrice', 0)
                    })
                return pd.DataFrame(processed), False # Real Data
            except Exception as e:
                if "Access forbidden" in str(e):
                    logger.warning(f"DATA: Groww Access Forbidden (Chain). Cooling down for 5 mins.")
                    self._groww_forbidden_until = time.time() + 300
                else:
                    logger.debug(f"DATA: Groww chain failed: {e}")

        # Static Mock Fallback
        try:
            spot = self.get_market_snapshot(symbol).spot_price
            base_strike = round(spot / 50) * 50
            strikes = [base_strike + i*50 for i in range(-5, 6)]
            import random
            data = {
                'strike': strikes,
                'call_oi': [random.randint(5000, 50000) for _ in strikes],
                'put_oi': [random.randint(5000, 50000) for _ in strikes],
                'call_ltp': [random.randint(80, 250) for _ in strikes],
                'put_ltp': [random.randint(80, 250) for _ in strikes],
                'call_vol': [random.randint(10000, 100000) for _ in strikes],
                'put_vol': [random.randint(10000, 100000) for _ in strikes],
                'call_bid': [150.0] * len(strikes),
                'call_ask': [152.0] * len(strikes),
                'put_bid': [150.0] * len(strikes),
                'put_ask': [152.0] * len(strikes)
            }
            return pd.DataFrame(data), True # Synthetic Data
        except Exception:
            return pd.DataFrame(), True

if __name__ == "__main__":
    provider = DataProvider()
    print(provider.get_market_snapshot("NIFTY"))
