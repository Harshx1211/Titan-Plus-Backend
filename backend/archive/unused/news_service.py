import os
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("news_service")

class NewsService:
    """
    Fetches and analyzes financial news to provide sentiment bias for the Brain.
    """
    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY") # e.g. from newsapi.org
        self.enabled = self.api_key is not None
        
    def get_market_sentiment(self, symbol: str = "NIFTY") -> Dict:
        """
        Fetches latest headlines and calculates a sentiment score (-1 to 1).
        -1: Extremely Bearish
         0: Neutral
         1: Extremely Bullish
        """
        if not self.enabled:
            # Fallback to neutral if no API key
            return {"score": 0.0, "reason": "News API Disabled", "headline_sample": "News API Offline"}
            
        try:
            # Placeholder for real NewsAPI call
            # url = f"https://newsapi.org/v2/everything?q={symbol}%20market&apiKey={self.api_key}"
            # response = requests.get(url)
            # headlines = [art['title'] for art in response.json().get('articles', [])[:10]]
            
            # Simple keyword-based sentiment for demonstration
            # In production, this would use a transformer model (BERT/RoBERTa)
            headlines = [
                "Nifty hits record high on strong earnings",
                "Global markets cautious ahead of Fed meeting",
                "FII selling continues in Indian markets"
            ]
            
            score = 0.0
            bull_keywords = ["high", "strong", "growth", "rally", "recovery", "positive"]
            bear_keywords = ["low", "weak", "fall", "drop", "negative", "cautious", "selling"]
            
            for h in headlines:
                for w in bull_keywords:
                    if w in h.lower(): score += 0.2
                for w in bear_keywords:
                    if w in h.lower(): score -= 0.2
            
            score = max(-1.0, min(1.0, score))
            
            return {
                "score": round(score, 2),
                "headline_sample": headlines[0] if headlines else "No news",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"NEWS: Failed to fetch sentiment: {e}")
            return {"score": 0.0, "reason": str(e)}

if __name__ == "__main__":
    ns = NewsService()
    print(ns.get_market_sentiment())
