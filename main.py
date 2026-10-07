import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Swiftwave WhatsApp Bot")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "swiftwave_secret_token")

@app.get("/")
def home():
    return {"status": "Swiftwave API is running"}

# 1. Meta Webhook Verification Handshake
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully by Meta.")
        return PlainTextResponse(content=str(challenge), status_code=200)

    print("Webhook verification rejected. Token mismatch.")
    raise HTTPException(status_code=403, detail="Verification failed")

# 2. Inbound WhatsApp Messages
@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()

    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            message = messages[0]
            from_number = message.get("from")
            text_body = message.get("text", {}).get("body", "").strip().lower()

            print(f"Received message: '{text_body}' from {from_number}")

            # Automated Reply Logic
            reply_text = (
                "👋 Welcome to Swiftwave Data & Airtime Services!\n\n"
                "Reply with an option to proceed:\n"
                "1. Buy MTN Data\n"
                "2. Buy Airtel Data\n"
                "3. Check Wallet Balance\n"
                "4. Speak to Support"
            )

            # Send response back via Meta Graph API
            send_url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": "text",
                "text": {"body": reply_text},
            }
            res = requests.post(send_url, headers=headers, json=payload)
            print(f"Sent reply status: {res.status_code}")

    except Exception as e:
        print(f"Error handling webhook event: {e}")

    # Meta requires a rapid 200 OK response
    return {"status": "EVENT_RECEIVED"}