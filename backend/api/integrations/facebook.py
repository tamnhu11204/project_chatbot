from fastapi import APIRouter, Request, HTTPException
from backend.nlp.intent_predictor import predict_intent
from backend.logic.rules import get_response_from_rules
from backend.config.settings import FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN
import requests
from pymongo import MongoClient
from datetime import datetime

router = APIRouter()

# MongoDB connection
client = MongoClient("mongodb+srv://tamnhu11204:nhunguyen11204@cluster0.kezkc.mongodb.net/")
db = client["chatbot_db"]

def save_message(user_id, message, response, intent, confidence, context=None, platform="messenger"):
    db["LiveChatMessage"].insert_one({
        "sender": "user",
        "user": user_id,
        "message": message,
        "timestamp": datetime.now(),
        "isHandled": False,
        "context": context or {},
        "platform": platform
    })
    db["LiveChatMessage"].insert_one({
        "sender": "bot",
        "user": user_id,
        "message": response,
        "timestamp": datetime.now(),
        "isHandled": True,
        "context": context or {},
        "platform": platform
    })

def extract_book_name(message):
    return message.split("sách")[-1].strip() if "sách" in message.lower() else ""

@router.get("/webhook")
async def facebook_verify(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == FACEBOOK_VERIFY_TOKEN:
        return params.get("hub.challenge")
    raise HTTPException(status_code=403, detail="Invalid verify token")

@router.post("/webhook")
async def facebook_webhook(request: Request):
    body = await request.json()
    for entry in body.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            user_input = messaging.get("message", {}).get("text")
            if user_input:
                # Lấy context từ tin nhắn gần nhất
                last_message = db["LiveChatMessage"].find_one(
                    {"user": sender_id, "platform": "messenger"},
                    sort=[("timestamp", -1)]
                )
                context = last_message["context"] if last_message else {}
                
                intent, confidence, response = predict_intent(user_input, context)
                if intent == "book_price" and context.get("book"):
                    async with httpx.AsyncClient() as client:
                        product_response = await client.get(
                            f"http://localhost:3001/api/product/get-all?filter=name,{context['book']}"
                        )
                        if product_response.status_code == 200 and product_response.json()["data"]:
                            response = f"Giá sách {context['book']} là {product_response.json()['data'][0]['price']} VND."
                
                new_context = context.copy()
                if intent == "find_book":
                    new_context["book"] = extract_book_name(user_input)
                
                save_message(sender_id, user_input, response, intent, confidence, new_context, platform="messenger")
                send_facebook_message(sender_id, response)
                
                # Gửi đến server Node.js
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "http://localhost:3001/api/chat/send",
                        json={
                            "userId": sender_id,
                            "message": user_input,
                            "sender": "user",
                            "context": new_context,
                            "platform": "messenger"
                        }
                    )
                    await client.post(
                        "http://localhost:3001/api/chat/send",
                        json={
                            "userId": sender_id,
                            "message": response,
                            "sender": "bot",
                            "context": new_context,
                            "platform": "messenger"
                        }
                    )
    return {"status": "success"}

def send_facebook_message(sender_id, message):
    url = f"https://graph.facebook.com/v13.0/me/messages?access_token={FACEBOOK_PAGE_TOKEN}"
    data = {"recipient": {"id": sender_id}, "message": {"text": message}}
    requests.post(url, json=data)