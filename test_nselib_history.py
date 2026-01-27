from nselib import capital_market
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_history():
    try:
        print("Fetching NIFTY 50 history via nselib...")
        df = capital_market.index_data(index="NIFTY 50", period="1D")
        print("\nColumns found:", df.columns.tolist())
        print("\nFirst 2 rows:\n", df.head(2))
        
        df.columns = [c.lower() for c in df.columns]
        if 'date' in df.columns:
            df['timestamp'] = pd.to_datetime(df['date'])
        elif 'historicaldate' in df.columns:
             df['timestamp'] = pd.to_datetime(df['historicaldate'])
        
        print("\nProcessed Timestamp sample:", df['timestamp'].iloc[0])
    except Exception as e:
        print(f"\nTEST FAILED: {e}")

if __name__ == "__main__":
    test_history()
