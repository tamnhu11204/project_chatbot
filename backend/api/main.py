from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from backend.config.settings import FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN, BACKEND_API_URL, MONGO_URI, MONGO_DB
from backend.logic.rules import get_response_from_rules
from backend.nlp.feedback_handler import FeedbackHandler
from backend.nlp.intent_updater import update_intents
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
from pymongo import MongoClient
from datetime import datetime
import logging

app = FastAPI()

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3001", "http://localhost:3000", "https://bookish-web-frontend.onrender.com", "https://chatbot-frontend.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static và templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# MongoDB connection
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise Exception(f"MongoDB connection failed: {e}")
db = client[MONGO_DB]

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

def save_message(user_id, message, response, intent, confidence, context=None, platform="website"):
    """Save user and bot messages to MongoDB."""
    try:
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
    except Exception as e:
        logger.error(f"Failed to save message: {e}")

@app.get("/chatbot-ui", response_class=HTMLResponse)
async def get_chatbot_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict")
async def predict(request: PredictRequest):
    try:
        response_data = await get_response_from_rules(
            user_input=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            context=request.context
        )
        
        save_message(
            user_id=request.user_id,
            message=request.message,
            response=response_data["response"],
            intent=response_data["intent"],
            confidence=response_data["confidence"],
            context=response_data["context"],
            platform="website"
        )

        # Chỉ gửi yêu cầu đến BACKEND_API_URL nếu nó được cấu hình
        if BACKEND_API_URL:
            async with httpx.AsyncClient() as client:
                user_response = await client.post(
                    f"{BACKEND_API_URL}/api/chat/send",
                    json={
                        "userId": request.user_id,
                        "message": request.message,
                        "sender": "user",
                        "context": response_data["context"]
                    }
                )
                if user_response.status_code != 201:
                    logger.error(f"Failed to save user message: {user_response.text}")

                bot_response = await client.post(
                    f"{BACKEND_API_URL}/api/chat/send",
                    json={
                        "userId": request.user_id,
                        "message": response_data["response"],
                        "sender": "bot",
                        "context": response_data["context"]
                    }
                )
                if bot_response.status_code != 201:
                    logger.error(f"Failed to save bot message: {bot_response.text}")

        return response_data

    except Exception as e:
        logger.error(f"Error in /predict: {e}")
        return JSONResponse(content={"error": "Failed to process message"}, status_code=500)

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
            return {"status": "Feedback received"}
        raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        logger.error(f"Error in /feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

@app.get("/feedbacks")
async def get_feedbacks():
    try:
        feedbacks = feedback_handler.get_feedbacks(limit=100)
        return {"feedbacks": feedbacks}
    except Exception as e:
        logger.error(f"Error loading feedbacks: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading feedbacks: {str(e)}")

@app.post("/correct_feedback")
async def correct_feedback(correction: FeedbackCorrection):
    try:
        result = feedback_handler.correct_intent(
            user_input=correction.user_input,
            correct_intent=correction.correct_intent
        )
        if result["status"] == "success":
            return {"status": "success"}
        raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

@app.post("/retrain")
async def retrain_model():
    try:
        logger.info("Starting model retraining...")
        update_intents()
        logger.info("Model retraining completed.")
        return {"status": "success", "message": "Đã cập nhật intents và huấn luyện lại mô hình."}
    except Exception as e:
        logger.error(f"Retraining failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")