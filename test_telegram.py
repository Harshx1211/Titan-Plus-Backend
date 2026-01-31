import os
import requests
import sys

# Hardcoded for testing (Replace with your actual Chat ID if you have it)
# Or set env var: $env:TELEGRAM_CHAT_ID="your_id"
BOT_TOKEN = "8491359765:AAGgRh7_3CjIUpzJq4cKzPeb58Ztbx2iU8Q"
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not CHAT_ID:
    print("❌ Error: TELEGRAM_CHAT_ID environment variable not set.")
    print("Please set it or paste it here to test.")
    sys.exit(1)

def send_test_message():
    print(f"Testing Telegram Bot...")
    print(f"Token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
    print(f"Chat ID: {CHAT_ID}")

    message = (
        "<b>🚀 TITAN PLUS: SYSTEM TEST</b>\n\n"
        "✅ Telegram Notifications: <b>ONLINE</b>\n"
        "🟢 System Status: <b>PRODUCTION READY</b>\n\n"
        "<i>Waiting for market open (09:15 AM)...</i>"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("\n✅ SUCCESS! Check your Telegram.")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        if hasattr(e, 'response') and e.response:
             print(f"Response: {e.response.text}")

if __name__ == "__main__":
    send_test_message()
