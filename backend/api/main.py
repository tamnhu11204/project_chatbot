import json
import os
import sys
from typing import Optional
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pymongo import MongoClient
from datetime import datetime
import logging
import aiohttp
try:
    from backend.config.settings import MONGO_URI, MONGO_DB, FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN, BACKEND_API_URL, INTENTS_PATH
except ImportError:
    from config.settings import MONGO_URI, MONGO_DB, FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN, BACKEND_API_URL, INTENTS_PATH
try:
    from backend.logic.rules import get_response_from_rules
except ImportError:
    from logic.rules import get_response_from_rules
try:
    from backend.nlp.feedback_handler import FeedbackHandler
    from backend.nlp.intent_updater import update_intents
except ImportError:
    from nlp.feedback_handler import FeedbackHandler
    from nlp.intent_updater import update_intents

# Thêm thư mục gốc vào sys.path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, base_dir)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Base directory: {base_dir}")
logger.info(f"sys.path: {sys.path}")

# Tải biến môi trường từ .env (chỉ để debug cục bộ)
try:
    load_dotenv()
except Exception as e:
    logger.warning(f"Failed to load .env file: {e}. Using environment variables from Render or settings.py.")

app = FastAPI()

# Cấu hình biến môi trường
FACEBOOK_PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN", FACEBOOK_PAGE_TOKEN)
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", FACEBOOK_VERIFY_TOKEN)
BACKEND_API_URL = os.getenv("BACKEND_API_URL", BACKEND_API_URL)
MONGO_URI = os.getenv("MONGO_URI", MONGO_URI)
MONGO_DB = os.getenv("MONGO_DB", MONGO_DB)

# Kiểm tra biến môi trường
if not all([MONGO_URI, MONGO_DB, FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN]):
    logger.error("Một hoặc nhiều biến môi trường không được cấu hình: MONGO_URI, MONGO_DB, FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN")
    raise Exception("Cần cấu hình đầy đủ các biến môi trường")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("API_BASE_URL", "https://project-chatbot-hgcl.onrender.com"),
        "http://localhost:3001",
        "http://localhost:8000"  # Để debug cục bộ
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static và templates
static_dir = os.path.join(base_dir, "frontend/static")
templates_dir = os.path.join(base_dir, "frontend/templates")
logger.info(f"Checking static directory: {static_dir}, exists: {os.path.exists(static_dir)}")
logger.info(f"Checking templates directory: {templates_dir}, exists: {os.path.exists(templates_dir)}")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.error(f"Static directory '{static_dir}' not found. Static files will not be served.")

if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
else:
    logger.error(f"Templates directory '{templates_dir}' not found. Chatbot UI may not work.")

# MongoDB connection
def get_mongo_client():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        return client
    except Exception as e:
        logger.error(f"MongoDB connection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MongoDB connection error: {str(e)}")

# Initialize FeedbackHandler
feedback_handler = FeedbackHandler()

class PredictRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    context: dict = {}

class FeedbackRequest(BaseModel):
    user_input: str
    bot_response: str
    feedback: str
    user_id: str = None

class FeedbackCorrection(BaseModel):
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

def save_message(user_id, message, response, intent, confidence, context=None, platform="website"):
    """Save user and bot messages to MongoDB."""
    client = None
    try:
        client = get_mongo_client()
        db = client[MONGO_DB]
        db["chat_logs"].insert_one({
            "sender": "user",
            "user": user_id,
            "message": message,
            "timestamp": datetime.now(),
            "isHandled": False,
            "context": context or {},
            "platform": platform
        })
        db["chat_logs"].insert_one({
            "sender": "bot",
            "user": user_id,
            "message": response,
            "timestamp": datetime.now(),
            "isHandled": True,
            "context": context or {},
            "platform": platform
        })
    except Exception as e:
        logger.error(f"Failed to save message: {e}")
    finally:
        if client:
            client.close()

@app.get("/")
async def health_check():
    logger.info("Health check requested")
    return {"status": "OK", "message": "Server is running"}

@app.get("/chatbot-ui", response_class=HTMLResponse)
async def get_chatbot_ui(request: Request):
    if not os.path.exists(templates_dir):
        logger.error("Templates directory missing, cannot serve chatbot UI")
        return JSONResponse(content={"error": "Chatbot UI unavailable"}, status_code=500)
    logger.info("Serving chatbot UI at /chatbot-ui")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict")
async def predict(request: PredictRequest):
    client = None
    try:
        logger.info(f"Received predict request: {request}")
        response_data = await get_response_from_rules(
            user_input=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            context=request.context
        )
        logger.info(f"Response: {response_data}")

        save_message(
            user_id=request.user_id,
            message=request.message,
            response=response_data["response"],
            intent=response_data["intent"],
            confidence=response_data["confidence"],
            context=response_data["context"],
            platform="website"
        )

        return response_data
    except Exception as e:
        logger.error(f"Error in /predict: {str(e)}")
        return JSONResponse(content={"error": f"Failed to process message: {str(e)}"}, status_code=500)
    finally:
        if client:
            client.close()

@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    try:
        result = feedback_handler.save_feedback(
            user_input=request.user_input,
            bot_response=request.bot_response,
            feedback=request.feedback,
            user_id=request.user_id
        )
        if result["status"] == "success":
            feedback_handler.process_negative_feedback()
            logger.info(f"Feedback saved: {request}")
            return {"status": "Feedback received"}
        raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        logger.error(f"Error in /feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

@app.get("/feedbacks")
async def get_feedbacks():
    try:
        feedbacks = feedback_handler.get_feedbacks(limit=100)
        logger.info(f"Retrieved {len(feedbacks)} feedbacks")
        return {"feedbacks": feedbacks}
    except Exception as e:
        logger.error(f"Error loading feedbacks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading feedbacks: {str(e)}")

@app.post("/correct_feedback")
async def correct_feedback(correction: FeedbackCorrection):
    try:
        result = feedback_handler.correct_intent(
            user_input=correction.user_input,
            correct_intent=correction.correct_intent
        )
        if result["status"] == "success":
            logger.info(f"Corrected feedback: {correction.user_input} -> {correction.correct_intent}")
            return {"status": "success"}
        raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

@app.post("/retrain")
async def retrain_model():
    try:
        logger.info("Starting model retraining...")
        update_intents()
        from backend.nlp.retrain_manager import auto_retrain
        auto_retrain()
        logger.info("Model retraining completed.")
        return {"status": "success", "message": "Đã cập nhật intents và huấn luyện lại mô hình."}
    except Exception as e:
        logger.error(f"Retraining failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")

@app.get("/webhook")
async def verify_webhook(request: Request):
    try:
        verify_token = FACEBOOK_VERIFY_TOKEN
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        logger.info(f"Webhook verification: mode={mode}, token={token}, challenge={challenge}")
        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook verified successfully")
            return PlainTextResponse(challenge)
        return JSONResponse(content={"error": "Invalid verification token"}, status_code=403)
    except Exception as e:
        logger.error(f"Error in webhook verification: {str(e)}")
        return JSONResponse(content={"error": f"Verification failed: {str(e)}"}, status_code=403)

@app.post("/webhook")
async def handle_webhook(request: Request):
    client = None
    try:
        body = await request.json()
        logger.info(f"Received webhook payload: {body}")
        if body.get("object") == "page":
            client = get_mongo_client()
            db = client[MONGO_DB]
            for entry in body.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event["sender"]["id"]
                    message = messaging_event["message"]["text"]
                    if not message:
                        continue
                    logger.info(f"Processing message from {sender_id}: {message}")
                    session_id = f"fb_{sender_id}_{datetime.now().timestamp()}"
                    response_data = await get_response_from_rules(
                        user_input=message,
                        session_id=session_id,
                        user_id=sender_id,
                        context={}
                    )
                    async with aiohttp.ClientSession() as session:
                        response = await session.post(
                            f"https://graph.facebook.com/v13.0/me/messages?access_token={FACEBOOK_PAGE_TOKEN}",
                            json={
                                "recipient": {"id": sender_id},
                                "message": {"text": response_data["response"]}
                            }
                        )
                        if response.status != 200:
                            logger.error(f"Failed to send message to Messenger: {response.text}")
                    save_message(
                        user_id=sender_id,
                        message=message,
                        response=response_data["response"],
                        intent=response_data["intent"],
                        confidence=response_data["confidence"],
                        context=response_data["context"],
                        platform="messenger"
                    )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
    finally:
        if client:
            client.close()

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

def suggest_intent(text: str, threshold: float = 0.6) -> str:
    """Suggest intent based on text matching."""
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