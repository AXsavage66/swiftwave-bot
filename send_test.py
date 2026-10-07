import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# REPLACE WITH YOUR ACTUAL WHATSAPP NUMBER (format: 234 followed by the rest, no '+' and no leading '0')
# Example: If your number is 08012345678, write "2348012345678"
RECIPIENT_PHONE = "234XXXXXXXXXX"

url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json",
}

payload = {
    "messaging_product": "whatsapp",
    "to": 2347046470954,
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {"code": "en_US"}
    }
}

response = requests.post(url, headers=headers, json=payload)
print(f"Status Code: {response.status_code}")
print(response.json())