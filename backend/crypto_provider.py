import requests
import pandas as pd
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from models_v3 import MarketData

logger = logging.getLogger("crypto_provider")

class CryptoProvider:
    """
    Public Data Provider for Crypto Markets (Binance Public API)
    Requires ZERO API keys for market data analysis.
    """
    
    BASE_URL = "https://fapi.binance.com/fapi/v1"
    
    def __init__(self):
        self.session = requests.Session()
        # Common headers
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Titan-Plus-Institutional/12.6.0"
        })

    def get_market_snapshot(self, symbol: str) -> Optional[MarketData]:
        """Fetch real-time price from Binance Futures."""
        try:
            # Using Binance Futures Ticker (USDT pairs)
            endpoint = f"{self.BASE_URL}/ticker/price"
            params = {"symbol": symbol}
            
            res = self.session.get(endpoint, params=params, timeout=5)
            if res.status_code != 200:
                logger.error(f"Binance Error: {res.text}")
                return None
                
            data = res.json()
            price = float(data['price'])
            
            # For Crypto, we model spot and future as very close 
            # (or we can use the premium index if needed)
            return MarketData(
                symbol=symbol,
                spot_price=price,
                future_price=price, # Simple parity for initial analysis
                oi=1000000, # Crypto liquidity is massive, 1M is safe baseline
                pcr=1.0, 
                timestamp=datetime.now(),
                source="BINANCE_PUBLIC"
            )
        except Exception as e:
            logger.error(f"Crypto fetch failed for {symbol}: {e}")
            return None

    def get_history(self, symbol: str, interval: str = "5m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLCV history for technical analysis."""
        # Map internal interval names to Binance format
        interval_map = {
            "5minute": "5m",
            "60minute": "1h",
            "5m": "5m",
            "1h": "1h",
            "1d": "1d"
        }
        binance_interval = interval_map.get(interval, interval)
        
        try:
            endpoint = f"{self.BASE_URL}/klines"
            params = {
                "symbol": symbol,
                "interval": binance_interval,
                "limit": limit
            }
            
            res = self.session.get(endpoint, params=params, timeout=10)
            if res.status_code != 200:
                logger.error(f"Binance History Error: {res.text}")
                return None
                
            data = res.json()
            
            # Binance klines format: [Open time, Open, High, Low, Close, Volume, ...]
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            
            # Convert types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            logger.error(f"Crypto history failed for {symbol}: {e}")
            return None

    def get_option_chain(self, symbol: str) -> Tuple[pd.DataFrame, bool]:
        """Returns empty df as crypto uses Perpetual Futures primarily."""
        return pd.DataFrame(), False

if __name__ == "__main__":
    # Test script
    logging.basicConfig(level=logging.INFO)
    provider = CryptoProvider()
    print("\n--- Testing BTC Live ---")
    data = provider.get_market_snapshot("BTCUSDT")
    print(data)
    
    print("\n--- Testing BTC History ---")
    df = provider.get_history("BTCUSDT", limit=5)
    print(df)
