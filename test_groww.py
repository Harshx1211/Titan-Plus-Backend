import os
from dotenv import load_dotenv
from growwapi import GrowwAPI

load_dotenv()

def test_groww_connection():
    api_key = os.getenv("GROWW_API_KEY")
    api_secret = os.getenv("GROWW_API_SECRET")
    
    print(f"Testing Groww Connection...")
    
    try:
        # Get the actual session token using the API Key and Secret
        print("Fetching Access Token...")
        session_token = GrowwAPI.get_access_token(api_key=api_key, secret=api_secret)
        print(f"Session Token obtained: {session_token[:10]}...")
        
        bot = GrowwAPI(token=session_token)
        
        # Test getting market data with different formats
        test_symbols = ["NIFTY 50", "NIFTY", "RELIANCE"]
        for sym in test_symbols:
            try:
                # Based on signature: get_quote(trading_symbol, exchange, segment)
                quote = bot.get_quote(trading_symbol=sym, exchange="NSE", segment="CASH")
                print(f"Quote for {sym}: {quote}")
            except Exception as e:
                print(f"Quote for {sym} failed: {e}")
        
        # List segments and some instruments
        print("\nFetching instruments sample...")
        instruments = bot.get_all_instruments()
        print(f"Total Instruments: {len(instruments)}")
        print("Sample Segments:", instruments['segment'].unique())
        print("Sample Exchanges:", instruments['exchange'].unique())
        print(instruments.head())
        
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    test_groww_connection()
