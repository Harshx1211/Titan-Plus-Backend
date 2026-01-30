from growwapi import GrowwAPI
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GROWW_API_KEY")
secret = os.getenv("GROWW_API_SECRET")

try:
    token = GrowwAPI.get_access_token(api_key=key, secret=secret)
    bot = GrowwAPI(token=token)
    
    # Try different symbols for Nifty 50
    symbols = ["NIFTY 50", "NIFTY", "Nifty 50"]
    for sym in symbols:
        try:
            print(f"Trying {sym} (NSE/INDEX)...")
            res = bot.get_quote(trading_symbol=sym, exchange="NSE", segment="INDEX")
            print(f"RESULT: {res}\n")
        except Exception as e:
            print(f"FAILED: {e}\n")
            
    # Try NSE/CASH as fallback?
    print("Trying NIFTY 50 (NSE/CASH)...")
    try:
        res = bot.get_quote(trading_symbol="NIFTY 50", exchange="NSE", segment="CASH")
        print(f"RESULT: {res}\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

except Exception as e:
    print(f"INITIALIZATION FAILED: {e}")
