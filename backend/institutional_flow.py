"""
Institutional Flow Analyzer
Fetches and analyzes FII/DII data, market breadth, and other institutional metrics
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional

logger = logging.getLogger("institutional_flow")

class InstitutionalAnalyzer:
    """
    Analyzes institutional money flow and market breadth indicators
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_expiry = None
        
    def get_fii_dii_data(self) -> Dict:
        """
        Fetch FII/DII data from NSE
        Returns net buying/selling in crores
        """
        # Check cache (valid for 1 hour)
        if self.cache_expiry and datetime.now() < self.cache_expiry:
            if 'fii_dii' in self.cache:
                return self.cache['fii_dii']
        
        try:
            # NSE API endpoint for participant-wise trading
            url = "https://www.nseindia.com/api/fiidiiTradeReact"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract latest data
                if data and len(data) > 0:
                    latest = data[0]
                    
                    result = {
                        'fii_net': float(latest.get('fii', {}).get('net', 0)),
                        'dii_net': float(latest.get('dii', {}).get('net', 0)),
                        'fii_buy': float(latest.get('fii', {}).get('buy', 0)),
                        'fii_sell': float(latest.get('fii', {}).get('sell', 0)),
                        'dii_buy': float(latest.get('dii', {}).get('buy', 0)),
                        'dii_sell': float(latest.get('dii', {}).get('sell', 0)),
                        'timestamp': datetime.now()
                    }
                    
                    # Cache for 1 hour
                    self.cache['fii_dii'] = result
                    self.cache_expiry = datetime.now() + timedelta(hours=1)
                    
                    return result
        
        except Exception as e:
            logger.warning(f"Failed to fetch FII/DII data: {e}")
        
        # Fallback
        return {
            'fii_net': 0.0,
            'dii_net': 0.0,
            'fii_buy': 0.0,
            'fii_sell': 0.0,
            'dii_buy': 0.0,
            'dii_sell': 0.0,
            'timestamp': datetime.now()
        }
    
    def get_market_breadth(self) -> Dict:
        """
        Get advance-decline ratio and other breadth metrics
        """
        try:
            # NSE market status API
            url = "https://www.nseindia.com/api/market-data-pre-open?key=ALL"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                advancing = 0
                declining = 0
                unchanged = 0
                
                if 'data' in data:
                    for stock in data['data']:
                        change = float(stock.get('perChange', 0))
                        if change > 0:
                            advancing += 1
                        elif change < 0:
                            declining += 1
                        else:
                            unchanged += 1
                
                ad_ratio = advancing / declining if declining > 0 else 2.0
                
                return {
                    'advancing': advancing,
                    'declining': declining,
                    'unchanged': unchanged,
                    'ad_ratio': ad_ratio,
                    'timestamp': datetime.now()
                }
        
        except Exception as e:
            logger.warning(f"Failed to fetch market breadth: {e}")
        
        # Fallback
        return {
            'advancing': 0,
            'declining': 0,
            'unchanged': 0,
            'ad_ratio': 1.0,
            'timestamp': datetime.now()
        }
    
    def evaluate_institutional_sentiment(self, signal_type: str) -> Dict:
        """
        Evaluate institutional sentiment for a given signal
        Returns score and reasons
        """
        score = 0.0
        reasons = []
        
        # Get FII/DII data
        fii_dii = self.get_fii_dii_data()
        fii_net = fii_dii['fii_net']
        dii_net = fii_dii['dii_net']
        
        # FII/DII Confluence (Max 0.5 pt)
        if "BULLISH" in signal_type:
            if fii_net > 1000:  # Strong FII buying
                score += 0.5
                reasons.append(f"FII Buying ({fii_net:.0f}Cr)")
            elif fii_net > 500:
                score += 0.3
                reasons.append(f"FII Positive ({fii_net:.0f}Cr)")
            elif fii_net < -1000:
                score -= 0.3
                reasons.append(f"FII Selling ({fii_net:.0f}Cr)")
        else:  # BEARISH
            if fii_net < -1000:  # Strong FII selling
                score += 0.5
                reasons.append(f"FII Selling ({fii_net:.0f}Cr)")
            elif fii_net < -500:
                score += 0.3
                reasons.append(f"FII Negative ({fii_net:.0f}Cr)")
            elif fii_net > 1000:
                score -= 0.3
                reasons.append(f"FII Buying ({fii_net:.0f}Cr)")
        
        # Market Breadth (Max 0.3 pt)
        breadth = self.get_market_breadth()
        ad_ratio = breadth['ad_ratio']
        
        if "BULLISH" in signal_type:
            if ad_ratio > 2.0:
                score += 0.3
                reasons.append(f"Strong Breadth ({ad_ratio:.1f})")
            elif ad_ratio > 1.5:
                score += 0.2
                reasons.append(f"Positive Breadth ({ad_ratio:.1f})")
            elif ad_ratio < 0.5:
                score -= 0.2
                reasons.append(f"Weak Breadth ({ad_ratio:.1f})")
        else:  # BEARISH
            if ad_ratio < 0.5:
                score += 0.3
                reasons.append(f"Weak Breadth ({ad_ratio:.1f})")
            elif ad_ratio < 0.7:
                score += 0.2
                reasons.append(f"Negative Breadth ({ad_ratio:.1f})")
            elif ad_ratio > 2.0:
                score -= 0.2
                reasons.append(f"Strong Breadth ({ad_ratio:.1f})")
        
        return {
            'score': score,
            'reasons': reasons,
            'fii_net': fii_net,
            'dii_net': dii_net,
            'ad_ratio': ad_ratio
        }
    
    def get_vix_score(self, vix_value: float) -> Dict:
        """
        Score based on India VIX level
        """
        score = 0.0
        reasons = []
        
        if vix_value < 10:
            # Dead market - very risky for scalping
            score = -0.5
            reasons.append(f"VIX Too Low ({vix_value:.1f}) - Dead Market")
        elif 10 <= vix_value < 12:
            # Low volatility - not ideal
            score = -0.2
            reasons.append(f"VIX Low ({vix_value:.1f})")
        elif 12 <= vix_value <= 18:
            # Optimal range for scalping
            score = 0.5
            reasons.append(f"VIX Optimal ({vix_value:.1f})")
        elif 18 < vix_value <= 22:
            # Moderate volatility - acceptable
            score = 0.3
            reasons.append(f"VIX Moderate ({vix_value:.1f})")
        elif 22 < vix_value <= 28:
            # High volatility - risky
            score = 0.0
            reasons.append(f"VIX High ({vix_value:.1f})")
        else:
            # Panic mode - avoid trading
            score = -0.7
            reasons.append(f"VIX Panic ({vix_value:.1f}) - Avoid")
        
        return {
            'score': score,
            'reasons': reasons,
            'vix': vix_value
        }

# Singleton instance
_institutional_analyzer = None

def get_institutional_analyzer() -> InstitutionalAnalyzer:
    """Get singleton instance"""
    global _institutional_analyzer
    if _institutional_analyzer is None:
        _institutional_analyzer = InstitutionalAnalyzer()
    return _institutional_analyzer
