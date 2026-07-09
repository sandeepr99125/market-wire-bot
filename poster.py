"""
Delivery layer: sends the formatted alert somewhere.

Posts to WhatsApp via a WAHA (WhatsApp HTTP API) instance. Falls back
to printing to the terminal if WAHA isn't configured, so local runs
still work without secrets set up.
"""

import os

import requests

WAHA_URL = os.environ.get("WAHA_URL", "").rstrip("/")
WAHA_API_KEY = os.environ.get("WAHA_API_KEY", "")
WAHA_CHAT_ID = os.environ.get("WAHA_CHAT_ID", "")


def post_alert(message):
    if not (WAHA_URL and WAHA_API_KEY and WAHA_CHAT_ID):
        print(message)
        print("-" * 50)
        return

    response = requests.post(
        f"{WAHA_URL}/api/sendText",
        json={"chatId": WAHA_CHAT_ID, "text": message, "session": "default"},
        headers={"X-Api-Key": WAHA_API_KEY},
        timeout=15,
    )
    response.raise_for_status()
