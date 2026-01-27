try:
    from nselib import capital_market
    import pandas as pd
    
    print("Fetching indices via nselib...")
    data = capital_market.market_watch_all_indices()
    print("Columns available:", data.columns.tolist())
    print("\nNIFTY 50 Row:")
    nifty = data[data['index'].str.contains('NIFTY 50', na=False, case=False)]
    print(nifty)
    
    print("\nAll Indices:")
    print(data[['index', 'last', 'variation', 'percentChange']])

except Exception as e:
    print(f"FAILED: {e}")
