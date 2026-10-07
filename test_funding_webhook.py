import uuid
import requests

WEBHOOK_URL = "http://127.0.0.1:8000/webhook/payvessel"

payload = {
    "order": {
        "amount": 2000.0,
        "settlement_amount": 1950.0,  # ₦50 provider fee deducted
        "fee": 50.0,
        "reference": f"PV_TEST_{uuid.uuid4().hex[:10].upper()}",
        "description": "Transfer from Bank to Dedicated NUBAN",
        "recipient": {
            "account_number": "0123456789",
            "phoneNumber": "2348000000000"
        }
    }
}

print("Simulating bank transfer webhook from Payvessel...")
response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
print(f"Status Code: {response.status_code}")

try:
    print("Response JSON:", response.json())
except Exception:
    print("Raw Response Text:", response.text)