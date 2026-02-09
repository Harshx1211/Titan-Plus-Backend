# [v9.9.9] Telegram Multi-Layer Client
import requests
import logging
import time
from typing import Optional

logger = logging.getLogger("notifier.telegram")

class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.last_sent_msg = ""
        self.last_sent_time = 0

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Sends a message with a basic Spam Guard."""
        # Anti-Spam: Don't repeat the exact same message within 30 seconds
        if text == self.last_sent_msg and (time.time() - self.last_sent_time) < 30:
            return False
            
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            resp = requests.post(self.base_url, json=payload, timeout=10)
            if resp.status_code == 200:
                self.last_sent_msg = text
                self.last_sent_time = time.time()
                return True
            else:
                logger.error(f"TELEGRAM_ERROR: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"TELEGRAM_CRITICAL: {e}")
            return False
