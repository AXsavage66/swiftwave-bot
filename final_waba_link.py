import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("WHATSAPP_TOKEN")

# Paste the 15-digit WABA ID you copied from the dashboard here
WABA_ID = "1416388323243621" 

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

url = f"https://graph.facebook.com/v26.0/{WABA_ID}/subscribed_apps"
response = requests.post(url, headers=headers)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")