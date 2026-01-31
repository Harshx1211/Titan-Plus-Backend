import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger("quality_filter")

class QualityFilter:
    """
    Multi-layer confluence filter to ensure only HIGH-CONVICTION trades execute.
    Target: 70%+ win rate by being extremely selective.
    """
    
    def __init__(self):
        self.min_confluence_score = 2.2  # Out of 5 (balanced for profitability)
        
    def evaluate_trade_quality(self, 
                               signal_data: Dict,
                               df_1m: pd.DataFrame,
                               df_5m: pd.DataFrame,
                               news_sentiment: float = 0.0) -> Dict:
        """
        Scores a potential trade on multiple dimensions.
        Returns: {"approved": bool, "score": float, "reasons": list}
        """
        score = 0.0
        reasons = []
        
        # 1. Volume Confirmation (1 point)
        if 'volume' in df_1m.columns and len(df_1m) > 20:
            vol_ma = df_1m['volume'].rolling(20).mean().iloc[-1]
            curr_vol = df_1m['volume'].iloc[-1]
            if curr_vol > vol_ma * 1.5:
                score += 1.0
                reasons.append("Strong Volume")
            elif curr_vol > vol_ma:
                score += 0.5
                reasons.append("Above-Avg Volume")
        
        # 2. Trend Alignment (1 point)
        # Check if 5m EMA is aligned with signal direction
        if len(df_5m) > 20:
            ema_9 = df_5m['close'].ewm(span=9).mean().iloc[-1]
            ema_21 = df_5m['close'].ewm(span=21).mean().iloc[-1]
            curr_price = df_5m['close'].iloc[-1]
            
            if "BULLISH" in signal_data.get("type", ""):
                if ema_9 > ema_21 and curr_price > ema_9:
                    score += 1.0
                    reasons.append("Bullish Trend Aligned")
                elif curr_price > ema_21:
                    score += 0.5
            else:
                if ema_9 < ema_21 and curr_price < ema_9:
                    score += 1.0
                    reasons.append("Bearish Trend Aligned")
                elif curr_price < ema_21:
                    score += 0.5
        
        # 3. Momentum Confirmation (1 point)
        if len(df_1m) > 14:
            # RSI should be in favorable zone
            delta = df_1m['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            curr_rsi = rsi.iloc[-1]
            
            if "BULLISH" in signal_data.get("type", ""):
                if 30 <= curr_rsi <= 50:  # Oversold recovery
                    score += 1.0
                    reasons.append("RSI Bullish Zone")
                elif curr_rsi < 70:
                    score += 0.5
            else:
                if 50 <= curr_rsi <= 70:  # Overbought rejection
                    score += 1.0
                    reasons.append("RSI Bearish Zone")
                elif curr_rsi > 30:
                    score += 0.5
        
        # 4. Risk:Reward Quality (1 point)
        rr = signal_data.get("rr_ratio", 0)
        if rr >= 2.5:
            score += 1.0
            reasons.append(f"Excellent R:R ({rr:.1f})")
        elif rr >= 2.0:
            score += 0.9
            reasons.append(f"Great R:R ({rr:.1f})")
        elif rr >= 1.5:
            score += 0.8
            reasons.append(f"Good R:R ({rr:.1f})")
        elif rr >= 1.2:
            score += 0.4
        
        # 5. News Confluence (1 point)
        if abs(news_sentiment) > 0.3:
            if "BULLISH" in signal_data.get("type", "") and news_sentiment > 0:
                score += 1.0
                reasons.append("News Bullish Confluence")
            elif "BEARISH" in signal_data.get("type", "") and news_sentiment < 0:
                score += 1.0
                reasons.append("News Bearish Confluence")
            else:
                score -= 0.3  # Reduced penalty
                reasons.append("News Friction")
        
        # 6. Time-Based Filter (Bonus/Penalty)
        # Avoid first 15 mins (9:15-9:30) and last 30 mins (15:00-15:30)
        # These are typically choppy
        
        approved = score >= self.min_confluence_score
        
        return {
            "approved": approved,
            "score": round(score, 2),
            "reasons": reasons
        }
