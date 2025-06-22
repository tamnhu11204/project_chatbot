from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from backend.nlp.intent_predictor import predict_intent
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
from pymongo import MongoClient
from datetime import datetime
import json
import os
from backend.nlp.retrain_manager import auto_retrain
import logging

app = FastAPI()

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static và templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# MongoDB connection
try:
    client = MongoClient("mongodb+srv://tamnhu11204:nhunguyen11204@cluster0.kezkc.mongodb.net/", serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise Exception(f"MongoDB connection failed: {e}")
db = client["chatbot_db"]

class PredictRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    context: dict = {}

class FeedbackRequest(BaseModel):
    user_input: str
    bot_response: str
    feedback: str

class FeedbackCorrection(BaseModel):
    user_input: str
    correct_intent: str

def save_message(user_id, message, response, intent, confidence, context=None, platform="website"):
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

def extract_book_name(message):
    return message.split("sách")[-1].strip() if "sách" in message.lower() else ""

@app.get("/chatbot-ui", response_class=HTMLResponse)
async def get_chatbot_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict")
async def predict(request: PredictRequest):
    try:
        intent, confidence, response = predict_intent(request.message, request.context)
        if intent == "book_price" and request.context.get("book"):
            async with httpx.AsyncClient() as client:
                product_response = await client.get(
                    f"http://localhost:3001/api/product/get-all?filter=name,{request.context['book']}"
                )
                if product_response.status_code == 200 and product_response.json()["data"]:
                    response = f"Giá sách {request.context['book']} là {product_response.json()['data'][0]['price']} VND."
        
        new_context = request.context.copy()
        if intent == "find_book":
            new_context["book"] = extract_book_name(request.message)

        save_message(
            request.user_id,
            request.message,
            response,
            intent,
            confidence,
            new_context,
            platform="website"
        )

        async with httpx.AsyncClient() as client:
            user_response = await client.post(
                "http://localhost:3001/api/chat/send",
                json={
                    "userId": request.user_id,
                    "message": request.message,
                    "sender": "user",
                    "context": new_context
                }
            )
            if user_response.status_code != 201:
                logger.error(f"Failed to save user message: {user_response.text}")

            bot_response = await client.post(
                "http://localhost:3001/api/chat/send",
                json={
                    "userId": request.user_id,
                    "message": response,
                    "sender": "bot",
                    "context": new_context
                }
            )
            if bot_response.status_code != 201:
                logger.error(f"Failed to save bot message: {bot_response.text}")

        return {
            "response": response,
            "intent": intent,
            "confidence": confidence,
            "context": new_context
        }
    except Exception as e:
        logger.error(f"Error in /predict: {e}")
        return JSONResponse(content={"error": "Failed to process message"}, status_code=500)

@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    try:
        logger.info(f"Feedback received: {request}")
        db["feedback"].insert_one({
            "user_input": request.user_input,
            "bot_response": request.bot_response,
            "feedback": request.feedback,
            "timestamp": datetime.now()
        })
        return {"status": "Feedback received"}
    except Exception as e:
        logger.error(f"Error in /feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

@app.get("/intents")
async def get_intents():
    try:
        intents_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "intents.json")
        book_intents_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "book_intents.json")
        intents = []
        if os.path.exists(intents_path):
            with open(intents_path, "r", encoding="utf-8") as f:
                intents.extend(json.load(f)["intents"])
            logger.info(f"Loaded intents from {intents_path}")
        else:
            logger.warning(f"intents.json not found at {intents_path}")
        if os.path.exists(book_intents_path):
            with open(book_intents_path, "r", encoding="utf-8") as f:
                intents.extend(json.load(f)["intents"])
            logger.info(f"Loaded intents from {book_intents_path}")
        else:
            logger.warning(f"book_intents.json not found at {book_intents_path}")
        intent_tags = [{"tag": intent["tag"]} for intent in intents]
        return {"intents": intent_tags}
    except Exception as e:
        logger.error(f"Error loading intents: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading intents: {str(e)}")

@app.get("/feedbacks")
async def get_feedbacks():
    try:
        feedbacks = list(db.feedback.find({}, {"_id": 0, "user_input": 1, "bot_response": 1, "intent": 1, "correct_intent": 1}))
        formatted_feedbacks = [
            {
                "user_input": f["user_input"],
                "intent": f.get("intent", "unknown"),
                "response_sai": f.get("bot_response", ""),
                "correct_intent": f.get("correct_intent", "")
            } for f in feedbacks
        ]
        logger.info(f"Loaded {len(feedbacks)} feedbacks")
        return {"feedbacks": formatted_feedbacks}
    except Exception as e:
        logger.error(f"Error loading feedbacks: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading feedbacks: {str(e)}")

@app.post("/correct_feedback")
async def correct_feedback(correction: FeedbackCorrection):
    try:
        db.feedback.update_one(
            {"user_input": correction.user_input},
            {"$set": {"correct_intent": correction.correct_intent}},
            upsert=True
        )
        logger.info(f"Updated feedback for user_input: {correction.user_input}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

@app.post("/retrain")
async def retrain_model():
    try:
        logger.info("Starting model retraining...")
        auto_retrain()
        logger.info("Model retraining completed.")
        return {"status": "success", "message": "Đã kiểm tra và huấn luyện lại mô hình nếu cần."}
    except Exception as e:
        logger.error(f"Retraining failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")