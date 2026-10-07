import requests

APP_ID = "1109411568144361"
APP_SECRET = "WbUnt02fuI5mVqMK8436oMHIso4"
CALLBACK_URL = "https://kuwvl-102-91-77-113.free.pinggy.net/webhook"
VERIFY_TOKEN = "swiftwave_secret_token"

url = f"https://graph.facebook.com/v26.0/{APP_ID}/subscriptions"

payload = {
    "object": "whatsapp_business_account",
    "callback_url": CALLBACK_URL,
    "verify_token": VERIFY_TOKEN,
    "fields": "messages",
    "access_token": f"{APP_ID}|{APP_SECRET}"
}

response = requests.post(url, data=payload)
print(f"Status Code: {response.status_code}")
print(response.json())