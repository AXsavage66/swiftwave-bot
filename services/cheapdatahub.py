import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

class CheapDataHubService:
    BASE_URL = "https://www.cheapdatahub.ng/api/v1/resellers"

    def __init__(self):
        raw_key = os.getenv("CHEAPDATAHUB_API_KEY", "")
        self.api_key = raw_key.strip().strip('"').strip("'")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_wallet_balance(self):
        """Fetches the live reseller wallet balance."""
        url = f"{self.BASE_URL}/wallet/balance/"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            data = response.json()
            if response.status_code == 200:
                balance = data.get("data", {}).get("balance", 0.0)
                return {"success": True, "balance": float(balance)}
            return {"success": False, "error": data.get("detail") or data.get("message")}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network error: {str(e)}"}

    def buy_data(self, network: str, plan_id: int, phone_number: str):
        """
        Submits data order with dual-payload compatibility:
        Sends both (bundle_id/phone_number) and (network/plan_id/phone).
        """
        url = f"{self.BASE_URL}/data/purchase/"
        clean_phone = phone_number.strip().replace(" ", "").replace("-", "")

        payload = {
            "network": network.lower(),
            "plan_id": int(plan_id),
            "bundle_id": int(plan_id),
            "phone": clean_phone,
            "phone_number": clean_phone
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=20)
            data = response.json()

            # Inspect success indicators
            is_success = (
                response.status_code in [200, 201] and
                str(data.get("status", "")).lower() in ["true", "success"]
            )

            if is_success:
                return {
                    "success": True,
                    "message": data.get("message", "Data delivered successfully"),
                    "reference": data.get("reference") or data.get("data", {}).get("reference"),
                    "raw": data
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message") or data.get("detail", "Data Purchase Failed"),
                    "raw": data
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}