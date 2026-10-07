import os
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

class PayvesselService:
    BASE_URL = "https://api.payvessel.com/api/v1"

    def __init__(self):
        self.api_key = os.getenv("PAYVESSEL_API_KEY", "").strip()
        self.secret_key = os.getenv("PAYVESSEL_SECRET_KEY", "").strip()
        self.business_id = os.getenv("PAYVESSEL_BUSINESS_ID", "").strip()

    def get_headers(self) -> Dict[str, str]:
        return {
            "api-key": self.api_key,
            "api-secret": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def verify_signature(self, payload_bytes: bytes, received_signature: str) -> bool:
        """
        Validates HMAC SHA-512 signature sent in HTTP headers by Payvessel.
        Guarantees that the webhook payload originated strictly from Payvessel.
        """
        if not self.secret_key or not received_signature:
            return False

        computed_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed_signature, received_signature)

    def create_virtual_account(self, name: str, phone: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Requests a permanent dedicated NUBAN account tied to the customer's phone number.
        """
        url = f"{self.BASE_URL}/create-virtual-account"
        
        # Payvessel requires an email; generate deterministic placeholder if absent
        user_email = email if email else f"{phone}@swiftwave.ng"

        payload = {
            "email": user_email,
            "name": name if name else f"Customer {phone}",
            "phoneNumber": phone,
            "bankcode": ["120001", "000017"],  # 9PSB / Wema Bank codes
            "account_type": "STATIC",
            "businessid": self.business_id
        }

        try:
            res = requests.post(url, json=payload, headers=self.get_headers(), timeout=15)
            data = res.json()
            if res.status_code in [200, 201] and data.get("status"):
                banks = data.get("banks", [])
                primary_bank = banks[0] if banks else {}
                return {
                    "success": True,
                    "bank_name": primary_bank.get("bankName", "Virtual Bank"),
                    "account_number": primary_bank.get("accountNumber"),
                    "account_name": primary_bank.get("accountName"),
                    "tracking_reference": data.get("order", {}).get("trackingReference")
                }
            return {
                "success": False,
                "error": data.get("message", "Unable to create virtual account")
            }
        except Exception as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}