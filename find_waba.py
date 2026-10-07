import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("WHATSAPP_TOKEN")
BUSINESS_ID = "919803914317097"
headers = {"Authorization": f"Bearer {TOKEN}"}

print("--- Checking Token Permissions & Target WABAs ---")
debug_url = f"https://graph.facebook.com/debug_token?input_token={TOKEN}&access_token={TOKEN}"
res = requests.get(debug_url).json()

waba_id = None
scopes = res.get("data", {}).get("granular_scopes", [])
for s in scopes:
    if s.get("target_ids"):
        waba_id = s["target_ids"][0]
        print(f"Discovered WABA ID from token scopes: {waba_id}")
        break

if not waba_id:
    # Query business portfolio directly
    biz_url = f"https://graph.facebook.com/v26.0/{BUSINESS_ID}/owned_whatsapp_business_accounts"
    biz_res = requests.get(biz_url, headers=headers).json()
    print("Business Portfolio check:", biz_res)
    if "data" in biz_res and biz_res["data"]:
        waba_id = biz_res["data"][0]["id"]
        print(f"Discovered WABA ID from portfolio: {waba_id}")

if waba_id:
    print(f"\nSubscribing WABA {waba_id} to Swiftwave App...")
    sub_url = f"https://graph.facebook.com/v26.0/{waba_id}/subscribed_apps"
    sub_res = requests.post(sub_url, headers=headers).json()
    print("Result:", sub_res)
else:
    print("\nCould not extract WABA ID automatically. Full token debug data:")
    print(res)