import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import engine, SessionLocal, get_db
from services.ai_agent import process_user_message

# Load environment variables
load_dotenv()

# Automatically create any missing tables (Users, Orders, Transactions, SavedContacts, PendingOrders)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Swiftwave AI VTU Bot")

# Environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")


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


def handle_incoming_whatsapp(sender_phone: str, message_text: str):
    """Background task worker: opens DB session, runs AI agent, sends WhatsApp reply."""
    db = SessionLocal()
    try:
        reply_text = process_user_message(db, sender_phone, message_text)
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

                    # 2. PROCESS ACTUAL MESSAGES
                    if "messages" in value:
                        for message in value["messages"]:
                            sender_phone = message["from"]

                            if message.get("type") == "text":
                                message_text = message["text"]["body"].strip()
                                print(f"📩 WhatsApp User {sender_phone} sent: {message_text}")

                                # 3. BACKGROUND PROCESSING: Hand off to AI Agent
                                background_tasks.add_task(
                                    handle_incoming_whatsapp,
                                    sender_phone,
                                    message_text
                                )
                            else:
                                print(f"Ignored non-text message type: {message.get('type')}")

    except Exception as e:
        print(f"Error parsing webhook payload: {e}")

    # 4. INSTANT RETURN: Send 200 OK immediately so Meta doesn't retry
    return Response(content="OK", status_code=200)