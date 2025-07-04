from pymongo import MongoClient
from datetime import datetime
try:
    from backend.config.settings import MONGO_URI, MONGO_DB
except ImportError:
    from config.settings import MONGO_URI, MONGO_DB

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
chat_logs = db["chat_logs"]
chat_feedbacks = db["chat_feedbacks"]
wrong_responses = db["wrong_responses"]

def log_conversation(user_input, intent, confidence, response, session_id):
    chat_logs.insert_one(
        {
            "user": user_input,
            "intent": intent,
            "confidence": float(confidence),
            "response": response,
            "session_id": session_id,
            "timestamp": datetime.now(),
        }
    )

def log_feedback(user_input, bot_response, feedback_type):
    feedback_record = {
        "user_input": user_input,
        "bot_response": bot_response,
        "feedback": feedback_type,
        "timestamp": datetime.now(),
    }
    chat_feedbacks.insert_one(feedback_record)

    if feedback_type == "dislike":
        wrong_responses.insert_one(
            {
                "user_input": user_input,
                "response_sai": bot_response,
                "intent": chat_logs.find_one({"user": user_input})["intent"],
                "timestamp": datetime.now(),
            }
        )

def get_wrong_responses():
    return list(wrong_responses.find())

def save_message(user_id, session_id, message, sender, platform="website", context=None):
    """Save user and bot messages to MongoDB."""
    try:
        db["LiveChatMessage"].insert_one({
            "sender": sender,
            "user": user_id,
            "message": message,
            "session_id": session_id,
            "timestamp": datetime.now(),
            "isHandled": sender == "bot",
            "context": context or {},
            "platform": platform
        })
    except Exception as e:
        print(f"Failed to save message: {e}")