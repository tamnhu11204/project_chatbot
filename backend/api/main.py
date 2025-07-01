from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import logging
from pymongo import MongoClient
import json
import aiohttp
import os
from typing import Dict, Optional
try:
    from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH, FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN
except ImportError:
    from config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH, FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN
try:
    from backend.logic.rules import get_response_from_rules
except ImportError:
    from logic.rules import get_response_from_rules

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Pydantic models
class PredictRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    context: dict = {}

class FeedbackRequest(BaseModel):
    user_input: str
    bot_response: str
    feedback: str

class CorrectFeedbackRequest(BaseModel):
    user_input: str
    correct_intent: str

class SupportRequest(BaseModel):
    userId: str
    message: str
    context: dict = {}
    platform: str = "website"

class ChatMessage(BaseModel):
    sender: str
    userId: str
    message: str
    timestamp: Optional[str] = None

# Kết nối MongoDB
def get_mongo_client():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        return client
    except Exception as e:
        logger.error(f"MongoDB connection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MongoDB connection error: {str(e)}")

@app.post("/predict")
async def predict(data: PredictRequest):
    """Handle prediction requests for chatbot responses."""
    try:
        logger.info(f"Received predict request: {data}")
        response = await get_response_from_rules(data.message, data.session_id, data.user_id, data.context)
        logger.info(f"Response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in /predict: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/feedback")
async def feedback(data: FeedbackRequest):
    """Handle user feedback (like/dislike)."""
    client = None
    try:
        client = get_mongo_client()
        db = client[MONGO_DB]
        feedback_entry = {
            "user_input": data.user_input,
            "bot_response": data.bot_response,
            "feedback": data.feedback,
            "timestamp": datetime.now()
        }
        db["feedback"].insert_one(feedback_entry)
        logger.info(f"Feedback saved: {feedback_entry}")
        if data.feedback == "dislike":
            suggested_intent = suggest_intent(data.user_input)  # Assume suggest_intent exists
            db["wrong_responses"].insert_one({
                "user_input": data.user_input,
                "response_sai": data.bot_response,
                "intent": suggested_intent or "unknown",
                "timestamp": datetime.now()
            })
            logger.info(f"Wrong response saved for review: {data.user_input}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")
    finally:
        if client:
            client.close()

@app.get("/intents")
async def get_intents():
    """Retrieve available intents."""
    try:
        logger.info(f"Fetching intents from {INTENTS_PATH}")
        if os.path.exists(INTENTS_PATH):
            with open(INTENTS_PATH, "r", encoding="utf-8-sig") as f:
                intents = json.load(f)
            return [{"tag": intent["tag"]} for intent in intents["intents"]]
        else:
            logger.error(f"Intents file not found at {INTENTS_PATH}")
            raise HTTPException(status_code=404, detail="Intents file not found")
    except Exception as e:
        logger.error(f"Error fetching intents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching intents: {str(e)}")

@app.post("/correct_feedback")
async def correct_feedback(data: CorrectFeedbackRequest):
    """Correct wrong intent and save as suggestion."""
    client = None
    try:
        client = get_mongo_client()
        db = client[MONGO_DB]
        db["suggestions"].insert_one({
            "pattern": data.user_input,
            "intent": data.correct_intent,
            "timestamp": datetime.now()
        })
        db["wrong_responses"].delete_one({"user_input": data.user_input})
        logger.info(f"Corrected feedback: {data.user_input} -> {data.correct_intent}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error correcting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error correcting feedback: {str(e)}")
    finally:
        if client:
            client.close()

@app.post("/retrain")
async def retrain():
    """Trigger model retraining."""
    try:
        from backend.nlp.retrain_manager import auto_retrain
        logger.info("Starting retraining process")
        auto_retrain()
        logger.info("Retraining completed")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error during retraining: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during retraining: {str(e)}")

@app.get("/webhook")
async def facebook_verify(request: Request):
    """Verify Facebook webhook."""
    try:
        query = request.query_params
        mode = query.get("hub.mode")
        token = query.get("hub.verify_token")
        challenge = query.get("hub.challenge")
        logger.info(f"Webhook verification: mode={mode}, token={token}, challenge={challenge}")
        if mode == "subscribe" and token == FACEBOOK_VERIFY_TOKEN:
            return int(challenge)
        raise HTTPException(status_code=403, detail="Invalid verify token")
    except Exception as e:
        logger.error(f"Error in webhook verification: {str(e)}")
        raise HTTPException(status_code=403, detail=f"Verification failed: {str(e)}")

@app.post("/webhook")
async def facebook_webhook(request: Request):
    """Handle incoming Facebook messages."""
    client = None
    try:
        body = await request.json()
        logger.info(f"Received webhook data: {body}")
        if body.get("object") != "page":
            raise HTTPException(status_code=400, detail="Invalid webhook object")

        client = get_mongo_client()
        db = client[MONGO_DB]
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                message_text = messaging_event["message"].get("text")
                if not message_text:
                    continue
                logger.info(f"Processing message from {sender_id}: {message_text}")
                session_id = f"fb_{sender_id}_{datetime.now().timestamp()}"
                response_data = await get_response_from_rules(message_text, session_id, sender_id, {})
                
                db["chat_logs"].insert_one({
                    "user_id": sender_id,
                    "session_id": session_id,
                    "user_input": message_text,
                    "bot_response": response_data["response"],
                    "intent": response_data["intent"],
                    "confidence": response_data["confidence"],
                    "timestamp": datetime.now(),
                    "platform": "messenger"
                })

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://graph.facebook.com/v12.0/me/messages",
                        params={"access_token": FACEBOOK_PAGE_TOKEN},
                        json={
                            "recipient": {"id": sender_id},
                            "message": {"text": response_data["response"]}
                        }
                    ) as response:
                        if response.status != 200:
                            logger.error(f"Failed to send response to {sender_id}: {await response.text()}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in webhook processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")
    finally:
        if client:
            client.close()

# Giả lập endpoint hỗ trợ admin (thay thế bookish-web-backend)
@app.post("/api/chat/support")
async def request_support(data: SupportRequest):
    """Handle support requests and store in MongoDB."""
    client = None
    try:
        client = get_mongo_client()
        db = client[MONGO_DB]
        message_entry = {
            "sender": "user",
            "user": data.userId,
            "message": data.message,
            "timestamp": datetime.now(),
            "isHandled": False,
            "context": data.context,
            "platform": data.platform
        }
        db["chat_messages"].insert_one(message_entry)
        logger.info(f"Support request saved: {message_entry}")
        return message_entry
    except Exception as e:
        logger.error(f"Error in support request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving support request: {str(e)}")
    finally:
        if client:
            client.close()

@app.get("/api/chat/conversation/{userId}")
async def get_conversation(userId: str):
    """Retrieve conversation history for a user."""
    client = None
    try:
        client = get_mongo_client()
        db = client[MONGO_DB]
        messages = db["chat_messages"].find({"user": userId}).sort("timestamp", 1)
        messages_list = [
            {
                "sender": msg["sender"],
                "message": msg["message"],
                "timestamp": msg["timestamp"],
                "platform": msg["platform"]
            } for msg in messages
        ]
        logger.info(f"Retrieved {len(messages_list)} messages for user {userId}")
        return {"messages": messages_list}
    except Exception as e:
        logger.error(f"Error retrieving conversation for {userId}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation: {str(e)}")
    finally:
        if client:
            client.close()

from datetime import datetime
# Hàm suggest_intent giả lập (di chuyển từ utils.py để độc lập)
def suggest_intent(text: str, threshold: float = 0.6) -> Optional[str]:
    try:
        cleaned_text = text.lower().strip()
        with open(INTENTS_PATH, 'r', encoding='utf-8-sig') as f:
            intents = json.load(f)
        best_match = None
        best_score = 0.0
        for intent in intents['intents']:
            for pattern in intent['patterns']:
                pattern_cleaned = pattern.lower().strip()
                common_words = set(cleaned_text.split()) & set(pattern_cleaned.split())
                score = len(common_words) / max(len(pattern_cleaned.split()), 1)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = intent['tag']
        logger.info(f"Suggested intent for '{cleaned_text}': {best_match}, Score: {best_score}")
        return best_match
    except Exception as e:
        logger.error(f"Error in suggest_intent: {e}")
        return None