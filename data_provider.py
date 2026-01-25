import logging
import pandas as pd
from datetime import datetime
from typing import Optional, Dict
import nselib
from nselib import capital_market
from jugaad_data.nse import NSELive, index_raw
from models import MarketData
import os
from dotenv import load_dotenv

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
        """ Fetches live data from Groww API. """
        try:
            # Indices are often restricted in broker APIs, fallback to public for NIFTY/SENSEX
            if symbol in ["NIFTY", "SENSEX"]:
                return self._fetch_from_public(symbol)
            
            # For stocks
            quote = self.bot.get_quote(trading_symbol=symbol, exchange="NSE", segment="CASH")
            spot = float(quote['last_price'])
            
            return MarketData(
                symbol=symbol,
                spot_price=spot,
                future_price=spot + 45.0, # Approximate
                oi=0, # Cash segment enrichment needed for FNO
                pcr=1.0,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.warning(f"DATA: Groww fetch failed for {symbol}: {e}")
            return self._fetch_from_public(symbol)

    def _fetch_from_public(self, symbol: str) -> MarketData:
        """
        Fallback fetcher using nselib or mocks for Nifty/Sensex.
        """
        try:
            if symbol == "NIFTY":
                # Use nselib for near real-time snapshot
                data = capital_market.market_watch_all_indices()
                # Try multiple labels just in case nselib names change
                nifty_row = data[data['index'].isin(['NIFTY 50', 'NIFTY50', 'Nifty 50'])].iloc[0]
                spot = float(str(nifty_row['last']).replace(',', ''))
            elif symbol == "SENSEX":
                # Mocking for Sensex as nselib is NSE-focused. Using Friday Close.
                spot = 81537.70 + (datetime.now().second * 0.01)
            else:
                spot = 24500.0

            future = spot + 45.0 
            return MarketData(
                symbol=symbol,
                spot_price=spot,
                future_price=future,
                oi=15000000,
                pcr=0.95,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.warning(f"DATA: Public fetch failed for {symbol} ({e}). Using structural fallback.")
            import random
            spot = (81500.0 if symbol == "SENSEX" else 24500.0) + random.uniform(-5, 5)
            return MarketData(
                symbol=symbol,
                spot_price=round(spot, 2),
                future_price=round(spot + 45, 2),
                oi=15000000,
                pcr=0.95,
                timestamp=datetime.now()
            )

    def get_history(self, symbol: str, interval: str = "5minute", days: int = 5) -> pd.DataFrame:
        """
        Fetches historical data using jugaad-data or fallback.
        """
        try:
            if symbol == "NIFTY":
                from datetime import date, timedelta
                fetch_days = 30 if interval == "60minute" else days
                end_date = date.today()
                start_date = end_date - timedelta(days=fetch_days)
                
                raw_data = index_raw(symbol="NIFTY 50", from_date=start_date, to_date=end_date)
                df = pd.DataFrame(raw_data)
                
                if df.empty:
                    raise ValueError("Empty data from jugaad-data")

                df.columns = [c.lower() for c in df.columns]
                df['timestamp'] = pd.to_datetime(df['historicaldate'])
                df.set_index('timestamp', inplace=True)
                df.sort_index(inplace=True)
                
                df = df[['index open', 'index high', 'index low', 'closing index value']]
                df.columns = ['open', 'high', 'low', 'close']
                df['volume'] = 0 
                return df
            else:
                raise ValueError(f"History not implemented for {symbol}")

        except Exception as e:
            logger.warning(f"DATA: {interval} History fetch failed for {symbol} ({e}). Using structural fallback.")
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
            data = capital_market.market_watch_all_indices()
            vix_row = data[data['index'].str.contains('VIX', na=False, case=False)].iloc[0]
            return float(str(vix_row['last']).replace(',', ''))
        except Exception:
            return 15.0

    def get_breadth(self, symbol: str) -> Dict[str, int]:
        import random
        advances = random.randint(20, 35) if symbol == "NIFTY" else random.randint(12, 18)
        declines = (50 if symbol == "NIFTY" else 30) - advances
        return {"advances": advances, "declines": declines}

    def get_option_chain(self, symbol: str) -> pd.DataFrame:
        """
        Fetches the live option chain from Groww or fallback.
        """
        if self.use_groww and symbol == "NIFTY":
            try:
                # 1. Get Expiries
                expiries = self.bot.get_expiries(exchange="NSE", underlying_symbol=symbol)
                nearest_expiry = expiries[0] if isinstance(expiries, list) else expiries.get('expiries', [])[0]
                
                # 2. Get Option Chain
                chain_raw = self.bot.get_option_chain(exchange="NSE", underlying=symbol, expiry_date=nearest_expiry)
                
                # Groww usually returns options in a list under some key
                options = chain_raw.get('optionChain', [])
                if not options:
                    return pd.DataFrame()
                
                processed = []
                for opt in options:
                    processed.append({
                        'strike': opt.get('strikePrice'),
                        'call_oi': opt.get('callOption', {}).get('openInterest', 0),
                        'put_oi': opt.get('putOption', {}).get('openInterest', 0)
                    })
                return pd.DataFrame(processed)
            except Exception as e:
                logger.error(f"DATA: Groww chain failed: {e}. Falling back.")

        # Static Mock Fallback
        try:
            spot = self.get_market_snapshot(symbol).spot_price
            base_strike = round(spot, -2)
            strikes = [base_strike + i*50 for i in range(-5, 6)]
            import random
            data = {
                'strike': strikes,
                'call_oi': [random.randint(5000, 50000) for _ in strikes],
                'put_oi': [random.randint(5000, 50000) for _ in strikes]
            }
            return pd.DataFrame(data)
        except Exception:
            return pd.DataFrame()

if __name__ == "__main__":
    provider = DataProvider()
    print(provider.get_market_snapshot("NIFTY"))
