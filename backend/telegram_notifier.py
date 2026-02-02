import os
import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger("telegram_notifier")

class TelegramNotifier:
    """
    Sends real-time trade signals via Telegram.
    Acts as a lifeline when the dashboard is closed.
    """
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Validate credentials format
        if self.bot_token:
            # Check if token looks valid (should be like "123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
            if ":" not in self.bot_token or len(self.bot_token) < 20:
                logger.warning("TELEGRAM: Bot token appears invalid (wrong format)")
                self.enabled = False
            else:
                self.enabled = bool(self.chat_id)
        else:
            self.enabled = False
        
        if not self.enabled:
            logger.warning("TELEGRAM: Bot Token or Chat ID missing/invalid. Notifications DISABLED.")
            logger.info("TELEGRAM: To enable notifications, set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
        else:
            logger.info("TELEGRAM: Notifications ENABLED")
            # Test the connection on startup
            self._test_connection()

    def _test_connection(self):
        """Test if the bot token is valid by calling getMe endpoint"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 401:
                logger.error("TELEGRAM: Bot token is INVALID (401 Unauthorized). Please check your TELEGRAM_BOT_TOKEN.")
                self.enabled = False
            elif response.status_code == 200:
                bot_info = response.json()
                logger.info(f"TELEGRAM: Connection successful. Bot: @{bot_info['result']['username']}")
            else:
                logger.warning(f"TELEGRAM: Unexpected response code {response.status_code}")
        except Exception as e:
            logger.warning(f"TELEGRAM: Connection test failed: {e}")

    def send_signal(self, signal: Dict, dashboard_url: str = "") -> bool:
        """
        Sends a formatted trade signal to the user.
        """
        if not self.enabled:
            logger.debug("TELEGRAM: Notifications disabled, skipping signal send")
            return False
            
        try:
            # Format message with emojis and clear structure
            direction = "🟢 BULLISH" if "BULLISH" in signal.get('type', signal.get('reasoning', '')) else "🔴 BEARISH"
            
            # Safe confidence calculation
            confidence_val = signal.get('confidence_val', 0.5)
            if confidence_val > 1:
                confidence_val = confidence_val / 10  # Normalize if it's 0-10 scale
            quality_stars = "⭐" * max(1, min(5, int(confidence_val * 5)))
            
            # Construct message with safe defaults
            message = (
                f"🎯 <b>NEW SIGNAL #{signal.get('decision_id', 'N/A')}</b>\n\n"
                f"{direction} {signal.get('symbol', 'NIFTY')}\n"
                f"<b>{signal.get('option_symbol', 'OPTION')}</b>\n\n"
                f"💰 <b>Entry:</b> ₹{signal.get('premium_entry', signal.get('entry_price', 0)):.2f}\n"
                f"🛑 <b>SL:</b> ₹{signal.get('premium_sl', signal.get('stop_loss', 0)):.2f}\n"
                f"🎯 <b>Target:</b> ₹{signal.get('premium_target', signal.get('target', 0)):.2f}\n\n"
                f"📊 <b>Quality:</b> {signal.get('confidence', 'MEDIUM')} ({confidence_val*10:.1f}/10)\n"
                f"{quality_stars}\n"
                f"⚖️ <b>R:R:</b> 1:{signal.get('rr_ratio', 2.0):.1f}\n\n"
                f"<i>{signal.get('reasoning', 'Technical setup detected')}</i>\n\n"
            )
            
            if dashboard_url:
                message += f"🔗 <a href='{dashboard_url}'>Open Dashboard</a>"

            # Send request
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            # Handle different error codes
            if response.status_code == 401:
                logger.error("TELEGRAM: 401 Unauthorized - Bot token is invalid. Disabling notifications.")
                self.enabled = False
                return False
            elif response.status_code == 400:
                logger.error(f"TELEGRAM: 400 Bad Request - {response.text}")
                return False
            elif response.status_code != 200:
                logger.error(f"TELEGRAM: Unexpected error {response.status_code}: {response.text}")
                return False
            
            response.raise_for_status()
            
            logger.info(f"TELEGRAM: Sent signal #{signal.get('decision_id')} successfully.")
            return True
            
        except requests.exceptions.Timeout:
            logger.error("TELEGRAM: Request timeout after 10 seconds")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"TELEGRAM: Network error sending notification: {e}")
            return False
        except Exception as e:
            logger.error(f"TELEGRAM: Unexpected error sending notification: {e}")
            return False

    def send_alert(self, message: str) -> bool:
        """
        Sends a general system alert (e.g. Risk Limit Reached).
        """
        if not self.enabled:
            logger.debug("TELEGRAM: Notifications disabled, skipping alert")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": f"⚠️ <b>SYSTEM ALERT</b>\n\n{message}",
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 401:
                logger.error("TELEGRAM: 401 Unauthorized - Bot token is invalid. Disabling notifications.")
                self.enabled = False
                return False
                
            response.raise_for_status()
            logger.info("TELEGRAM: Alert sent successfully")
            return True
        except Exception as e:
            logger.error(f"TELEGRAM: Failed to send alert: {e}")
            return False

if __name__ == "__main__":
    # Test the notifier
    notifier = TelegramNotifier()
    if notifier.enabled:
        print("Telegram notifier is enabled and ready")
        # Test with a sample signal
        test_signal = {
            "decision_id": "TEST123",
            "symbol": "NIFTY",
            "option_symbol": "NIFTY 25000 CE",
            "entry_price": 150.0,
            "stop_loss": 130.0,
            "target": 180.0,
            "confidence": "HIGH",
            "confidence_val": 0.85,
            "reasoning": "Test signal",
            "rr_ratio": 1.5
        }
        success = notifier.send_alert("Test alert - system is working!")
        print(f"Test alert sent: {success}")
    else:
        print("Telegram notifier is DISABLED")
