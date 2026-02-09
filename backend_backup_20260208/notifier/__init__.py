# [v9.9.9] Notifier Package Init
from .formatter import NotifierFormatter
from .telegram_client import TelegramClient

class TitanNotifier:
    """Institutional Notification Interface"""
    def __init__(self, bot_token: str, chat_id: str):
        self.client = TelegramClient(bot_token, chat_id)
        self.formatter = NotifierFormatter()

    def send_entry(self, signal: dict):
        msg = self.formatter.format_entry(signal)
        return self.client.send(msg)

    def send_exit(self, signal_data: dict, reason: str, analysis: str):
        msg = self.formatter.format_exit(signal_data, reason, analysis)
        return self.client.send(msg)

    def send_greeting(self, stats: dict, wisdom: str):
        msg = self.formatter.format_greeting(stats, wisdom)
        return self.client.send(msg)

    def send_market_blueprint(self, symbol: str, trend: str, supports: list, resistances: list, note: str):
        msg = self.formatter.format_blueprint(symbol, trend, supports, resistances, note)
        return self.client.send(msg)

    def send_alert(self, title: str, body: str):
        msg = f"🛡️ <b>{title}</b>\n━━━━━━━━━━━━━\n{body}"
        return self.client.send(msg)
