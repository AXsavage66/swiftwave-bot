import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response, HTTPException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

def send_menu(sender_phone):
    """Helper function to send the main menu to the user."""
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    menu_text = (
        "👋 Welcome to Swiftwave Data & Airtime Services!\n\n"
        "Reply with an option to proceed:\n"
        "1. Buy MTN Data\n"
        "2. Buy Airtel Data\n"
        "3. Check Wallet Balance\n"
        "4. Speak to Support"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": sender_phone,
        "type": "text",
        "text": {"body": menu_text},
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Message sent status: {response.status_code}")
    except Exception as e:
        print(f"Failed to send message: {e}")

@app.get("/")
async def root():
    return {"status": "Swiftwave Bot is running!"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Endpoint for Meta to verify the webhook."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return Response(content=challenge, status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Endpoint to receive incoming WhatsApp messages and drop status updates."""
    body = await request.json()
    
    try:
        if "entry" in body:
            for entry in body["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    
                    # 1. FIREWALL: Ignore read receipts and delivery statuses
                    if "statuses" in value:
                        print("Received a status update. Dropping to prevent loops.")
                        continue 
                        
                    # 2. PROCESS ACTUAL MESSAGES
                    if "messages" in value:
                        for message in value["messages"]:
                            sender_phone = message["from"]
                            
                            if message["type"] == "text":
                                message_text = message["text"]["body"].strip()
                                print(f"User {sender_phone} sent: {message_text}")
                                
                                # 3. BACKGROUND PROCESSING: Hand off the heavy lifting
                                background_tasks.add_task(send_menu, sender_phone)
                            else:
                                print(f"Ignored non-text message type: {message.get('type')}")

    except Exception as e:
        print(f"Error parsing webhook payload: {e}")
        
    # 4. INSTANT RETURN: Send 200 OK immediately so Meta doesn't retry
    return Response(content="OK", status_code=200)