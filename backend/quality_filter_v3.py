import pandas as pd
from typing import Dict
import logging
from institutional_flow import get_institutional_analyzer

logger = logging.getLogger("quality_filter_v3")

class QualityFilterV3:
    """
    COMPLETE Multi-layer confluence filter with ALL institutional indicators.
    Max Score: 8.0 points (up from 5.5 in V2)
    """
    
    def __init__(self):
        self.min_confluence_score = 3.5  # Out of 8.0 (43.75%)
        self.adaptive_mode = True
        self.institutional = get_institutional_analyzer()
        
    def evaluate_trade_quality(self, 
                               signal_data: Dict,
                               df_1m: pd.DataFrame,
                               df_5m: pd.DataFrame,
                               news_sentiment: float = 0.0,
                               current_regime: str = "SIDEWAYS_NORMAL",
                               vix_value: float = 15.0,
                               pcr_value: float = 1.0,
                               iv_skew: float = 1.0) -> Dict:
        """
        Scores a potential trade with ALL institutional indicators.
        Returns: {"approved": bool, "score": float, "reasons": list}
        """
        score = 0.0
        reasons = []
        
        # ===== TECHNICAL INDICATORS (Max 3.5 pts) =====
        
        # 1. Volume Confirmation (Max 1.0 pt)
        if 'volume' in df_1m.columns and len(df_1m) > 20:
            vol_ma = df_1m['volume'].rolling(20).mean().iloc[-1]
            curr_vol = df_1m['volume'].iloc[-1]
            
            if curr_vol > vol_ma * 2.0:
                score += 1.0
                reasons.append("Explosive Volume")
            elif curr_vol > vol_ma * 1.5:
                score += 0.8
                reasons.append("Strong Volume")
            elif curr_vol > vol_ma * 1.2:
                score += 0.6
                reasons.append("Above-Avg Volume")
            elif curr_vol > vol_ma:
                score += 0.3
                reasons.append("Positive Volume")
        
        # 2. Trend Alignment (Max 1.0 pt)
        if len(df_5m) > 21:
            ema_9 = df_5m['close'].ewm(span=9).mean().iloc[-1]
            ema_21 = df_5m['close'].ewm(span=21).mean().iloc[-1]
            curr_price = df_5m['close'].iloc[-1]
            
            if len(df_1m) > 9:
                ema_1m = df_1m['close'].ewm(span=9).mean().iloc[-1]
                price_1m = df_1m['close'].iloc[-1]
            else:
                ema_1m = curr_price
                price_1m = curr_price
            
            if "BULLISH" in signal_data.get("type", ""):
                if ema_9 > ema_21 and curr_price > ema_9 and price_1m > ema_1m:
                    score += 1.0
                    reasons.append("Perfect Bullish Alignment")
                elif ema_9 > ema_21 and curr_price > ema_9:
                    score += 0.7
                    reasons.append("Bullish Trend (5m)")
                elif curr_price > ema_21:
                    score += 0.4
                    reasons.append("Above Key EMA")
            else:
                if ema_9 < ema_21 and curr_price < ema_9 and price_1m < ema_1m:
                    score += 1.0
                    reasons.append("Perfect Bearish Alignment")
                elif ema_9 < ema_21 and curr_price < ema_9:
                    score += 0.7
                    reasons.append("Bearish Trend (5m)")
                elif curr_price < ema_21:
                    score += 0.4
                    reasons.append("Below Key EMA")
        
        # 3. Momentum (Max 1.0 pt)
        if len(df_1m) > 26:
            delta = df_1m['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            curr_rsi = rsi.iloc[-1]
            
            ema_12 = df_1m['close'].ewm(span=12).mean()
            ema_26 = df_1m['close'].ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal_line = macd.ewm(span=9).mean()
            macd_cross = macd.iloc[-1] > signal_line.iloc[-1]
            
            if "BULLISH" in signal_data.get("type", ""):
                if 25 <= curr_rsi <= 45 and macd_cross:
                    score += 1.0
                    reasons.append("Perfect Bullish Momentum")
                elif 30 <= curr_rsi <= 50:
                    score += 0.7
                    reasons.append("RSI Bullish Zone")
                elif curr_rsi < 70:
                    score += 0.3
            else:
                if 55 <= curr_rsi <= 75 and not macd_cross:
                    score += 1.0
                    reasons.append("Perfect Bearish Momentum")
                elif 50 <= curr_rsi <= 70:
                    score += 0.7
                    reasons.append("RSI Bearish Zone")
                elif curr_rsi > 30:
                    score += 0.3
        
        # 4. Risk:Reward Quality (Max 1.5 pt)
        rr = signal_data.get("rr_ratio", 0)
        if rr >= 3.0:
            score += 1.5
            reasons.append(f"Exceptional R:R ({rr:.1f})")
        elif rr >= 2.5:
            score += 1.3
            reasons.append(f"Excellent R:R ({rr:.1f})")
        elif rr >= 2.0:
            score += 1.1
            reasons.append(f"Great R:R ({rr:.1f})")
        elif rr >= 1.5:
            score += 0.9
            reasons.append(f"Good R:R ({rr:.1f})")
        elif rr >= 1.2:
            score += 0.5
            reasons.append(f"Acceptable R:R ({rr:.1f})")
        
        # ===== INSTITUTIONAL INDICATORS (Max 4.5 pts) =====
        
        # 5. India VIX (Max 0.5 pt)
        vix_result = self.institutional.get_vix_score(vix_value)
        score += vix_result['score']
        reasons.extend(vix_result['reasons'])
        
        # 6. FII/DII Flow + Market Breadth (Max 0.8 pt)
        inst_result = self.institutional.evaluate_institutional_sentiment(
            signal_data.get("type", "")
        )
        score += inst_result['score']
        reasons.extend(inst_result['reasons'])
        
        # 7. PCR Confluence (Max 0.5 pt)
        if "BULLISH" in signal_data.get("type", ""):
            if pcr_value > 1.2:
                score += 0.5
                reasons.append(f"PCR Bullish ({pcr_value:.2f})")
            elif pcr_value > 1.0:
                score += 0.3
                reasons.append(f"PCR Positive ({pcr_value:.2f})")
            elif pcr_value < 0.7:
                score -= 0.2
                reasons.append(f"PCR Bearish ({pcr_value:.2f})")
        else:  # BEARISH
            if pcr_value < 0.7:
                score += 0.5
                reasons.append(f"PCR Bearish ({pcr_value:.2f})")
            elif pcr_value < 0.9:
                score += 0.3
                reasons.append(f"PCR Negative ({pcr_value:.2f})")
            elif pcr_value > 1.2:
                score -= 0.2
                reasons.append(f"PCR Bullish ({pcr_value:.2f})")
        
        # 8. IV Skew (Max 0.4 pt)
        if "BULLISH" in signal_data.get("type", ""):
            if iv_skew > 1.3:
                # High put demand = fear = contrarian bullish
                score += 0.4
                reasons.append(f"IV Skew Bullish ({iv_skew:.2f})")
            elif iv_skew > 1.1:
                score += 0.2
            elif iv_skew < 0.8:
                # High call demand = complacency
                score -= 0.2
                reasons.append(f"IV Skew Warning ({iv_skew:.2f})")
        else:  # BEARISH
            if iv_skew < 0.8:
                # High call demand = complacency = bearish
                score += 0.4
                reasons.append(f"IV Skew Bearish ({iv_skew:.2f})")
            elif iv_skew < 1.0:
                score += 0.2
            elif iv_skew > 1.3:
                # High put demand = fear
                score -= 0.2
                reasons.append(f"IV Skew Warning ({iv_skew:.2f})")
        
        # 9. News Sentiment (Max 1.0 pt)
        if abs(news_sentiment) > 0.3:
            if "BULLISH" in signal_data.get("type", "") and news_sentiment > 0:
                score += min(abs(news_sentiment), 1.0)
                reasons.append("News Bullish Confluence")
            elif "BEARISH" in signal_data.get("type", "") and news_sentiment < 0:
                score += min(abs(news_sentiment), 1.0)
                reasons.append("News Bearish Confluence")
            else:
                score -= 0.2
                reasons.append("News Neutral")
        
        # ===== ADAPTIVE THRESHOLD =====
        regime_adjusted = False
        threshold = self.min_confluence_score
        
        if self.adaptive_mode:
            if current_regime == "TRENDING":
                threshold = 3.0  # 37.5% of max
                regime_adjusted = True
                reasons.append("[Trending: Lower threshold]")
            elif current_regime == "SIDEWAYS_STRONG":
                threshold = 3.5  # 43.75%
            elif current_regime == "SIDEWAYS_NORMAL":
                threshold = 4.0  # 50%
            elif current_regime == "SIDEWAYS_WEAK":
                threshold = 4.5  # 56.25%
                regime_adjusted = True
                reasons.append("[Weak: Higher threshold]")
            elif current_regime == "UNCERTAIN":
                threshold = 5.0  # 62.5%
                regime_adjusted = True
                reasons.append("[Uncertain: Strict filter]")
        
        approved = score >= threshold
        
        return {
            "approved": approved,
            "score": round(score, 2),
            "threshold": threshold,
            "max_score": 8.0,
            "reasons": reasons,
            "regime_adjusted": regime_adjusted,
            "institutional_data": {
                'vix': vix_value,
                'pcr': pcr_value,
                'iv_skew': iv_skew,
                'fii_net': inst_result.get('fii_net', 0),
                'ad_ratio': inst_result.get('ad_ratio', 1.0)
            }
        }
    
    def get_market_regime(self, df: pd.DataFrame) -> str:
        """
        Determine current market regime for adaptive thresholds.
        """
        if len(df) < 50:
            return "UNCERTAIN"
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
        
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean().iloc[-1]
        
        if adx > 30:
            return "TRENDING"
        elif adx > 25:
            return "SIDEWAYS_STRONG"
        elif adx > 20:
            return "SIDEWAYS_NORMAL"
        elif adx > 15:
            return "SIDEWAYS_WEAK"
        else:
            return "UNCERTAIN"
