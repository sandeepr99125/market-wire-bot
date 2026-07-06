"""
Delivery layer: sends the formatted alert somewhere.

Right now this just prints to the terminal, so you can verify the
whole pipeline works before wiring up WhatsApp. In step 2, this file
is the ONLY thing that changes - post_alert() will call the WAHA API
instead of print(). Nothing else in the project needs to know.
"""


def post_alert(message):
    print(message)
    print("-" * 50)
    # --- Step 2 will replace the two lines above with something like: ---
    # import requests
    # requests.post(
    #     "http://localhost:3000/api/sendText",
    #     json={"chatId": WAHA_CHANNEL_ID, "text": message},
    #     headers={"X-Api-Key": WAHA_API_KEY},
    # )
