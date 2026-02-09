import requests
import pandas as pd
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from models_v3 import MarketData

logger = logging.getLogger("crypto_provider")

class CryptoProvider:
    """
    Public Data Provider for Crypto Markets (Binance Public API)
    Requires ZERO API keys for market data analysis.
    """
    
    BASE_URL = "https://fapi.binance.com/fapi/v1"
    KUCOIN_URL = "https://api-futures.kucoin.com"
    
    def __init__(self):
        self.session = requests.Session()
        # Common headers
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Titan-Plus-Institutional/12.6.4"
        })
        self.use_kucoin = False # Global fallback trigger

    def get_market_snapshot(self, symbol: str) -> Optional[MarketData]:
        """Fetch real-time price with automatic multi-source fallback."""
        if self.use_kucoin:
            return self._get_kucoin_snapshot(symbol)
            
        try:
            # Source 1: Binance
            endpoint = f"{self.BASE_URL}/ticker/price"
            params = {"symbol": symbol}
            
            res = self.session.get(endpoint, params=params, timeout=5)
            
            # Detect Geo-Restriction (451 Unavailable For Legal Reasons or specific JSON msg)
            if res.status_code == 451 or (res.status_code == 400 and "restricted location" in res.text):
                logger.warning(f"GEO_BLOCK: Binance restricted. Switching to KuCoin for {symbol}.")
                self.use_kucoin = True
                return self._get_kucoin_snapshot(symbol)

            if res.status_code != 200:
                logger.error(f"Binance Error: {res.text}")
                return None
                
            data = res.json()
            price = float(data['price'])
            
            return MarketData(
                symbol=symbol,
                spot_price=price,
                future_price=price,
                oi=1000000, 
                pcr=1.0, 
                timestamp=datetime.now(),
                source="BINANCE"
            )
        except Exception as e:
            logger.error(f"Crypto fetch failed for {symbol}: {e}")
            self.use_kucoin = True # Failover on network error too
            return self._get_kucoin_snapshot(symbol)

    def _get_kucoin_snapshot(self, symbol: str) -> Optional[MarketData]:
        """Fallback: Fetch from KuCoin Futures."""
        try:
            # KuCoin Futures symbols:
            # BTC -> XBTUSDTM, ETH -> ETHUSDTM, XAU (Gold) -> GUAUSDT
            kucoin_sym = symbol.replace("USDT", "USDTM")
            if "BTC" in kucoin_sym:
                kucoin_sym = kucoin_sym.replace("BTC", "XBT")
            elif "XAU" in symbol:
                kucoin_sym = "GUAUSDTM" # Unique Gold mapping
                
            endpoint = f"{self.KUCOIN_URL}/api/v1/ticker"
            params = {"symbol": kucoin_sym}
            
            res = self.session.get(endpoint, params=params, timeout=5)
            if res.status_code != 200:
                logger.error(f"KuCoin Error: {res.text}")
                return None
                
            data = res.json()
            if not data.get('data'): 
                logger.error(f"KuCoin Data Missing for {kucoin_sym}: {data}")
                return None
            
            price = float(data['data']['price'])
            return MarketData(
                symbol=symbol,
                spot_price=price,
                future_price=price,
                oi=1000000,
                pcr=1.0,
                timestamp=datetime.now(),
                source="KUCOIN"
            )
        except Exception as e:
            logger.error(f"KuCoin fallback failed: {e}")
            return None

    def get_history(self, symbol: str, interval: str = "5m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch history with automatic provider switching."""
        if self.use_kucoin:
            return self._get_kucoin_history(symbol, interval, limit)
            
        # Map internal interval names to Binance format
        interval_map = {"5minute": "5m", "60minute": "1h", "5m": "5m", "1h": "1h", "1d": "1d"}
        binance_interval = interval_map.get(interval, interval)
        
        try:
            endpoint = f"{self.BASE_URL}/klines"
            params = {"symbol": symbol, "interval": binance_interval, "limit": limit}
            
            res = self.session.get(endpoint, params=params, timeout=10)
            if res.status_code != 200:
                return self._get_kucoin_history(symbol, interval, limit)
                
            data = res.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df[['open', 'high', 'low', 'close', 'volume']]
        except:
            return self._get_kucoin_history(symbol, interval, limit)

    def _get_kucoin_history(self, symbol: str, interval: str = "5m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Fallback History: KuCoin Futures."""
        try:
            kucoin_sym = symbol.replace("USDT", "USDTM")
            if "BTC" in kucoin_sym:
                kucoin_sym = kucoin_sym.replace("BTC", "XBT")
            elif "XAU" in symbol:
                kucoin_sym = "GUAUSDTM"
                
            # KuCoin granularity is in minutes
            gran_map = {"5m": 5, "1h": 60, "1d": 1440, "5minute": 5, "60minute": 60}
            gran = gran_map.get(interval, 5)
            
            endpoint = f"{self.KUCOIN_URL}/api/v1/kline/query"
            params = {"symbol": kucoin_sym, "granularity": gran, "limit": limit}
            
            res = self.session.get(endpoint, params=params, timeout=10)
            data = res.json()
            if not data.get('data'): 
                logger.error(f"KuCoin History Data Missing: {data}")
                return None
            
            # KuCoin kline: [time, open, close, high, low, volume, turnover]
            df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df[['open', 'high', 'low', 'close', 'volume']].sort_index().tail(limit)
        except Exception as e:
            logger.error(f"KuCoin history failed: {e}")
            return None

    def get_option_chain(self, symbol: str) -> Tuple[pd.DataFrame, bool]:
        """Returns empty df as crypto uses Perpetual Futures primarily."""
        return pd.DataFrame(), False

if __name__ == "__main__":
    # Test script
    logging.basicConfig(level=logging.INFO)
    provider = CryptoProvider()
    print("\n--- Testing Binance (May fail if restricted) ---")
    data = provider.get_market_snapshot("BTCUSDT")
    print(f"Source: {data.source if data else 'None'} | Price: {data.spot_price if data else 'None'}")
    
    print("\n--- Testing KuCoin Fallback ---")
    provider.use_kucoin = True
    data = provider._get_kucoin_snapshot("BTCUSDT")
    print(f"Source: {data.source if data else 'None'} | Price: {data.spot_price if data else 'None'}")
