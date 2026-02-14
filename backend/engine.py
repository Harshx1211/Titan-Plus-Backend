import ccxt
import pandas as pd
import pandas_ta as ta
import asyncio
from typing import Optional

class CryptoEngine:
    """
    24/7 Crypto Market Data Engine
    Handles real-time data fetching via CCXT with institutional-grade reliability
    """
    def __init__(self):
        # Public API only - no keys required for market data
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use futures data for better liquidity
            }
        })
        self.monitored_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
    async def fetch_data(self, symbol: str, timeframe: str = '15m', limit: int = 200) -> Optional[pd.DataFrame]:
        """
        Fetches OHLCV data with error handling and retry logic
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Ensure data quality
                if len(df) < 50:
                    print(f"⚠️  Insufficient data for {symbol}: {len(df)} candles")
                    return None
                
                return df
                
            except ccxt.NetworkError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                print(f"❌ Network error fetching {symbol}: {e}")
                return None
                
            except ccxt.ExchangeError as e:
                print(f"❌ Exchange error for {symbol}: {e}")
                return None
                
            except Exception as e:
                print(f"❌ Unexpected error fetching {symbol}: {e}")
                return None
        
        return None
    
    def get_market_info(self, symbol: str) -> dict:
        """
        Fetches market metadata (tick size, min order size, etc.)
        """
        try:
            market = self.exchange.market(symbol)
            return {
                'tick_size': market['precision']['price'],
                'min_order': market['limits']['amount']['min'],
                'contract_size': market.get('contractSize', 1)
            }
        except Exception as e:
            print(f"Error fetching market info for {symbol}: {e}")
            return {}

# Singleton instance
engine = CryptoEngine()
