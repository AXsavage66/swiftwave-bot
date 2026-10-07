import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

headers = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}"
}

# Query the phone number endpoint to pull its parent WABA ID directly
url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}?fields=account_id"
response = requests.get(url, headers=headers)
data = response.json()

print("API Response:", data)

waba_id = data.get("account_id")

if waba_id:
    print(f"\nSUCCESS! Your WABA ID is: {waba_id}")
    
    # Automatically subscribe this WABA to your app
    sub_url = f"https://graph.facebook.com/v26.0/{waba_id}/subscribed_apps"
    sub_res = requests.post(sub_url, headers=headers).json()
    print("Subscription Result:", sub_res)
else:
    print("\nCould not find account_id. Trying alternative endpoint...")