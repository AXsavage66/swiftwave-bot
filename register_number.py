import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/register"

headers = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json",
}

# The pin can be any 6-digit two-step verification code of your choice
payload = {
    "messaging_product": "whatsapp",
    "pin": "123456"
}

response = requests.post(url, headers=headers, json=payload)
print(f"Status Code: {response.status_code}")
print(response.json())