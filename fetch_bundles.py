import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("CHEAPDATAHUB_API_KEY", "").strip().strip('"').strip("'")
BASE_URL = "https://www.cheapdatahub.ng/api/v1/resellers"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_bundles():
    # Standard endpoints used by aggregators for data bundles
    endpoints = [
        f"{BASE_URL}/data/bundles/",
        f"{BASE_URL}/data/plans/",
        f"{BASE_URL}/data/"
    ]

    for url in endpoints:
        print(f"Checking endpoint: {url}...")
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                print(f"✅ Success on {url}!\n")
                data = res.json()
                print("Sample Data Structure:")
                # Print first 3 plans to inspect structure
                bundles = data if isinstance(data, list) else data.get("data", [])
                for item in bundles[:5]:
                    print(item)
                return
            else:
                print(f"Status {res.status_code}: {res.text[:100]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    get_bundles()