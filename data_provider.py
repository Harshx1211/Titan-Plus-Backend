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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataProvider:
    """
    Modular data provider to fetch market data from various sources.
    Defaults to NSElib/Jugaad-Data for dry-run, can be upgraded to Kite Connect.
    """
    def __init__(self):
        self.kite_api_key = os.getenv("KITE_API_KEY")
        self.kite_api_secret = os.getenv("KITE_API_SECRET")
        self.use_kite = self.kite_api_key and self.kite_api_secret
        
        if self.use_kite:
            logger.info("DATA: Initializing Kite Connect...")
            # Placeholder for Kite initialization
            # from kiteconnect import KiteConnect
            # self.kite = KiteConnect(api_key=self.kite_api_key)
        else:
            logger.warning("DATA: kite credentials missing. Falling back to public scrapers (Latency expected).")

    def get_market_snapshot(self, symbol: str) -> MarketData:
        """
        Fetches current spot, future, and OI for a given symbol.
        """
        if self.use_kite:
            # High-speed WebSocket or Quote fetch
            return self._fetch_from_kite(symbol)
        else:
            # Public scraper fallback
            return self._fetch_from_public(symbol)

    def _fetch_from_public(self, symbol: str) -> MarketData:
        """
        Fallback fetcher using nselib or mocks for Nifty/Sensex.
        """
        try:
            if symbol == "NIFTY":
                # Use nselib for near real-time snapshot
                data = capital_market.market_watch_all_indices()
                nifty_row = data[data['index'] == 'NIFTY 50'].iloc[0]
                spot = float(str(nifty_row['last']).replace(',', ''))
            elif symbol == "SENSEX":
                # Sensex is BSE. Mocking for now as nselib is NSE-focused.
                # In real setup, this would be a BSE scraper or Broker API.
                spot = 81500.0 + (datetime.now().second * 0.1) # Simulating movement
            else:
                spot = 24500.0

            # Mocking future/oi for now
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

    def _fetch_from_kite(self, symbol: str) -> MarketData:
        # Implementation for Kite Connect goes here
        # For now, placeholder
        return self._fetch_from_public(symbol)

    def get_history(self, symbol: str, interval: str = "5minute", days: int = 5) -> pd.DataFrame:
        """
        Fetches historical data using jugaad-data or fallback.
        Supports '5minute' and '60minute' (1h) for MTF.
        """
        try:
            if symbol == "NIFTY":
                from datetime import date, timedelta
                # For MTF, we might need more days for the 1h chart
                fetch_days = 30 if interval == "60minute" else days
                end_date = date.today()
                start_date = end_date - timedelta(days=fetch_days)
                
                raw_data = index_raw(symbol="NIFTY 50", from_date=start_date, to_date=end_date)
                df = pd.DataFrame(raw_data)
                
                if df.empty:
                    raise ValueError("Empty data from jugaad-data")

                # Clean up columns and index
                df.columns = [c.lower() for c in df.columns]
                df['timestamp'] = pd.to_datetime(df['historicaldate'])
                df.set_index('timestamp', inplace=True)
                df.sort_index(inplace=True)
                
                # Match models.py expected names
                df = df[['index open', 'index high', 'index low', 'closing index value']]
                df.columns = ['open', 'high', 'low', 'close']
                df['volume'] = 0 

                # If interval is 1h, resample the data (since jugaad usually gives EOD or raw ticks)
                if interval == "60minute":
                    # In a real setup, we'd fetch 1h bars. Here we simulate by resampling if possible
                    # or returning the raw for now as a structural placeholder.
                    return df 
                
                return df
            else:
                # Sensex/Other Fallback
                raise ValueError(f"History fetch not implemented for {symbol}")

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
            vix_row = data[data['index'] == 'INDIA VIX'].iloc[0]
            return float(str(vix_row['last']).replace(',', ''))
        except Exception:
            return 15.0 # Stable baseline fallback

    def get_breadth(self, symbol: str) -> Dict[str, int]:
        """ 
        Fetches Advance/Decline ratio for the index.
        Mocked for dry-run as full constituent health requires broker API.
        """
        import random
        advances = random.randint(20, 35) if symbol == "NIFTY" else random.randint(12, 18)
        declines = (50 if symbol == "NIFTY" else 30) - advances
        return {"advances": advances, "declines": declines}

    def get_option_chain(self, symbol: str) -> pd.DataFrame:
        """
        Fetches the live option chain.
        Currently using mock for stable dry-run since public scrapers are unreliable.
        """
        try:
            # Placeholder for actual Shoonya/nselib call
            # For now, generate a synthetic chain around the current spot price
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
        except Exception as e:
            logger.error(f"DATA ERROR: Option Chain fetch failed: {e}")
            return pd.DataFrame()

if __name__ == "__main__":
    provider = DataProvider()
    print(provider.get_market_snapshot("NIFTY"))
