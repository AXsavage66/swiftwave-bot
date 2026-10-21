import os
import requests
import time
from fastapi import FastAPI, Request, BackgroundTasks, Response, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import engine, SessionLocal, get_db
from services.ai_agent import process_user_message

# Load environment variables
load_dotenv()

# Automatically create any missing tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Swiftwave AI VTU Bot")

# Environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# Idempotency Cache to store processed WhatsApp Message IDs to prevent Meta duplicate retries
PROCESSED_MESSAGES = {}


class ChatSimulatorRequest(BaseModel):
    phone: str
    message: str


def send_whatsapp_message(recipient_phone: str, text_body: str):
    """Sends the AI response back to the user on WhatsApp via Meta Cloud API."""
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text_body},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"📤 WhatsApp message sent to {recipient_phone} | Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")


def handle_incoming_whatsapp(sender_phone: str, message_text: str, profile_name: str = "Boss"):
    """Background task worker: opens DB session, runs AI agent, sends WhatsApp reply."""
    db = SessionLocal()
    try:
        # We pass the extracted profile_name straight into the AI brain
        reply_text = process_user_message(db, sender_phone, message_text, profile_name)
        send_whatsapp_message(sender_phone, reply_text)
    except Exception as e:
        print(f"🚨 Error processing WhatsApp message from {sender_phone}: {e}")
    finally:
        db.close()


@app.get("/")
async def root():
    return {"status": "Swiftwave AI VTU Bot is running!"}


@app.post("/test-chat")
async def test_chat_endpoint(payload: ChatSimulatorRequest, db: Session = Depends(get_db)):
    """
    Local simulator endpoint used by 'python chat.py' in VS Code terminal.
    Uses the exact same AI brain and database as live WhatsApp!
    """
    bot_reply = process_user_message(db, payload.phone.strip(), payload.message.strip())
    return {"bot_reply": bot_reply}


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Endpoint for Meta to verify the webhook."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified successfully!")
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
                        continue
                    
                    # 2. Extract the WhatsApp Profile Name (Fall back to "Boss" if hidden)
                    profile_name = "Boss"
                    if "contacts" in value and len(value["contacts"]) > 0:
                        profile_name = value["contacts"][0].get("profile", {}).get("name", "Boss")

                    # 3. PROCESS ACTUAL MESSAGES
                    if "messages" in value:
                        for message in value["messages"]:
                            message_id = message.get("id")
                            sender_phone = message.get("from")

                            # --- IDEMPOTENCY CHECK TO PREVENT DOUBLE-MESSAGES ---
                            current_time = time.time()
                            # Clean up old message IDs to prevent RAM bloat
                            for msg_id in list(PROCESSED_MESSAGES.keys()):
                                if current_time - PROCESSED_MESSAGES[msg_id] > 300: # 5 minutes
                                    del PROCESSED_MESSAGES[msg_id]

                            if message_id in PROCESSED_MESSAGES:
                                print(f"♻️ Ignored duplicate Meta retry for message: {message_id}")
                                continue

                            # Mark this exact message ID as processed
                            PROCESSED_MESSAGES[message_id] = current_time
                            # ----------------------------------------------------

                            if message.get("type") == "text":
                                message_text = message["text"]["body"].strip()
                                print(f"📩 WhatsApp User {profile_name} ({sender_phone}) sent: {message_text}")

                                # 4. BACKGROUND PROCESSING: Hand off to AI Agent
                                background_tasks.add_task(
                                    handle_incoming_whatsapp,
                                    sender_phone,
                                    message_text,
                                    profile_name
                                )
                            else:
                                print(f"Ignored non-text message type: {message.get('type')}")

    except Exception as e:
        print(f"Error parsing webhook payload: {e}")

    # 5. INSTANT RETURN: Send 200 OK immediately so Meta stops retrying
    return Response(content="OK", status_code=200)