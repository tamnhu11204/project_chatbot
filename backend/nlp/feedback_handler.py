from pymongo import MongoClient
try:
    from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
except ImportError:
    from config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
try:
    from backend.nlp.utils import is_valid_sentence, clean_text, suggest_intent
except ImportError:
    from nlp.utils import is_valid_sentence, clean_text, suggest_intent
from datetime import datetime
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kết nối MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client[MONGO_DB]
    logger.info("MongoDB connected successfully for FeedbackHandler")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

chat_logs = db["chat_logs"]
wrong_responses = db["wrong_responses"]
suggestions = db["suggestions"]

class FeedbackHandler:
    def save_feedback(self, user_input, bot_response, feedback, user_id=None):
        """Save feedback to wrong_responses if negative."""
        try:
            if "negative" in feedback.lower():
                cleaned_input = clean_text(user_input)
                if is_valid_sentence(cleaned_input):
                    suggested_intent = suggest_intent(cleaned_input, threshold=0.6)
                    wrong_responses.insert_one({
                        "user_input": user_input,
                        "cleaned_input": cleaned_input,
                        "bot_response": bot_response,
                        "feedback": feedback,
                        "user_id": user_id,
                        "suggested_intent": suggested_intent,
                        "timestamp": datetime.now()
                    })
                    logger.info(f"Saved negative feedback for input: {user_input}, Suggested intent: {suggested_intent}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            return {"status": "error", "message": str(e)}

    def process_negative_feedback(self):
        """Process negative feedback and save to suggestions."""
        try:
            negative_logs = list(chat_logs.find(
                {"user_feedback": "negative"},
                {"user": 1, "intent": 1}
            ).limit(100))
            negative_responses = list(wrong_responses.find(
                {},
                {"user_input": 1, "cleaned_input": 1, "suggested_intent": 1}
            ).limit(100))
            
            suggestions_data = []
            for log in negative_logs:
                user_text = log.get("user")
                intent = log.get("intent")
                if is_valid_sentence(user_text):
                    cleaned_text = clean_text(user_text)
                    suggested_intent = suggest_intent(cleaned_text, threshold=0.6) or intent
                    suggestions_data.append({"tag": suggested_intent, "pattern": user_text})
            
            for response in negative_responses:
                user_input = response.get("user_input")
                intent = response.get("suggested_intent")
                if is_valid_sentence(user_input) and intent:
                    suggestions_data.append({"tag": intent, "pattern": user_input})
            
            if suggestions_data:
                suggestions.insert_one({
                    "suggestions": suggestions_data,
                    "timestamp": datetime.now()
                })
                logger.info(f"Saved {len(suggestions_data)} negative feedback suggestions")
                
                chat_logs.delete_many({"user_feedback": "negative"})
                wrong_responses.delete_many({})
        except Exception as e:
            logger.error(f"Error processing negative feedback: {e}")