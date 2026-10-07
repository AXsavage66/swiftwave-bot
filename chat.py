import requests

SERVER_URL = "http://127.0.0.1:8000/test-chat"
TEST_PHONE = "2348000000000"

print("=" * 50)
print("     🌊 SWIFTWAVE BOT CHAT SIMULATOR 🌊")
print("  Type your message below and press Enter.")
print("  Type 'exit' to quit.")
print("=" * 50)

while True:
    try:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("Session ended.")
            break

        response = requests.post(
            SERVER_URL,
            json={"phone": TEST_PHONE, "message": user_input},
            timeout=30  # Allow enough time for telco API handshake
        )

        if response.status_code == 200:
            data = response.json()
            print(f"\n{data.get('bot_reply')}")
        else:
            print(f"\n⚠️ Server returned error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to the bot server.")
        print("👉 Make sure 'uvicorn main:app --reload' is running in Terminal 1.")
    except Exception as e:
        print(f"\n❌ Error: {e}")