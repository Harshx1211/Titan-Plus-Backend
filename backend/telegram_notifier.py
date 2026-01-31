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
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("TELEGRAM: Bot Token or Chat ID missing. Notifications DISABLED.")

    def send_signal(self, signal: Dict, dashboard_url: str = "") -> bool:
        """
        Sends a formatted trade signal to the user.
        """
        if not self.enabled:
            return False
            
        try:
            # Format message with emojis and clear structure
            direction = "🟢 BULLISH" if "BULLISH" in signal.get('type', '') else "🔴 BEARISH"
            quality_stars = "⭐" * int(signal.get('confidence_val', 0) * 5)
            
            # Construct message
            message = (
                f"🎯 <b>NEW SIGNAL #{signal.get('decision_id', 'N/A')}</b>\n\n"
                f"{direction} {signal.get('symbol', 'NIFTY')}\n"
                f"<b>{signal.get('option_symbol', 'OPTION')}</b>\n\n"
                f"💰 <b>Entry:</b> ₹{signal.get('premium_entry', 0)}\n"
                f"🛑 <b>SL:</b> ₹{signal.get('premium_sl', 0)}\n"
                f"🎯 <b>Target:</b> ₹{signal.get('premium_target', 0)}\n\n"
                f"📊 <b>Quality:</b> {signal.get('confidence', 'MEDIUM')} ({signal.get('confidence_val', 0)*10:.1f}/10)\n"
                f"{quality_stars}\n"
                f"⚖️ <b>R:R:</b> 1:{signal.get('rr_ratio', 0)}\n\n"
                f"<i>{signal.get('reasoning', '')}</i>\n\n"
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
            
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.info(f"TELEGRAM: Sent signal #{signal.get('decision_id')} successfully.")
            return True
            
        except Exception as e:
            logger.error(f"TELEGRAM: Failed to send notification: {e}")
            return False

    def send_alert(self, message: str) -> bool:
        """
        Sends a general system alert (e.g. Risk Limit Reached).
        """
        if not self.enabled: return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": f"⚠️ <b>SYSTEM ALERT</b>\n\n{message}",
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=5)
            return True
        except Exception as e:
            logger.error(f"TELEGRAM: Failed to send alert: {e}")
            return False
