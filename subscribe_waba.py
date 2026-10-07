import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
BUSINESS_ID = "919803914317097"

headers = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}

waba_id = None

# 1. Check WABAs assigned to this System User
res1 = requests.get("https://graph.facebook.com/v26.0/me/whatsapp_business_accounts", headers=headers).json()
if "data" in res1 and res1["data"]:
    waba_id = res1["data"][0]["id"]
    print(f"Found WABA ID via user assignments: {waba_id}")

# 2. Check WABAs owned by the Business Portfolio
if not waba_id:
    res2 = requests.get(f"https://graph.facebook.com/v26.0/{BUSINESS_ID}/owned_whatsapp_business_accounts", headers=headers).json()
    if "data" in res2 and res2["data"]:
        waba_id = res2["data"][0]["id"]
        print(f"Found WABA ID via Business Portfolio: {waba_id}")

# 3. Check Token metadata targets
if not waba_id:
    debug_url = f"https://graph.facebook.com/v26.0/debug_token?input_token={WHATSAPP_TOKEN}&access_token={WHATSAPP_TOKEN}"
    res3 = requests.get(debug_url).json()
    scopes = res3.get("data", {}).get("granular_scopes", [])
    for s in scopes:
        if s.get("target_ids"):
            waba_id = s["target_ids"][0]
            print(f"Found WABA ID via Token metadata: {waba_id}")
            break

if not waba_id:
    print("Could not automatically locate WABA ID. API Responses:")
    print("Method 1:", res1)
    exit(1)

# 4. Subscribe the WABA to your App
sub_url = f"https://graph.facebook.com/v26.0/{waba_id}/subscribed_apps"
sub_res = requests.post(sub_url, headers=headers)

print("\n--- Linking Result ---")
print(f"Status Code: {sub_res.status_code}")
print(f"Response: {sub_res.json()}")