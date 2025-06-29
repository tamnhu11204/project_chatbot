import re
import json
import os
import logging
import aiohttp
from datetime import datetime
from backend.config.settings import INTENTS_PATH, BACKEND_API_URL
from backend.nlp.utils import clean_text
from pymongo import MongoClient
from backend.config.settings import MONGO_URI, MONGO_DB

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load intents
intents = {"intents": []}
try:
    if os.path.exists(INTENTS_PATH):
        with open(INTENTS_PATH, "r", encoding="utf-8-sig") as f:
            intents = json.load(f)
        logger.info(f"Loaded intents from {INTENTS_PATH}")
    else:
        logger.error(f"Intents file not found at {INTENTS_PATH}")
except Exception as e:
    logger.error(f"Error loading intents: {e}")

def extract_book_name(user_input):
    """Extract book name from user input."""
    try:
        cleaned_input = clean_text(user_input)
        patterns = [
            r"tìm\s+sách\s+(.+)",
            r"chi\s+tiết\s+sách\s+(.+)",
            r"sách\s+(.+)",
            r"tìm\s+(.+)",
            r"(.+)\s+sách",
            r"(.+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned_input, re.IGNORECASE)
            if match:
                book_name = match.group(1).strip()
                keywords_to_remove = [
                    r"\btìm\b", r"\bsách\b", r"\bchi\s+tiết\b", 
                    r"\bthông\s+tin\b", r"\btập\b", r"\bcuốn\b"
                ]
                for keyword in keywords_to_remove:
                    book_name = re.sub(keyword, "", book_name, flags=re.IGNORECASE).strip()
                if book_name:
                    logger.info(f"Extracted book name: {book_name}")
                    return book_name
        return None
    except Exception as e:
        logger.error(f"Error extracting book name from '{user_input}': {e}")
        return None

async def fetch_book_details(book_name):
    """Fetch book details from backend API by name."""
    try:
        async with aiohttp.ClientSession() as session:
            # Bước 1: Tìm sách theo tên qua endpoint /get-all
            encoded_book_name = book_name.replace(" ", "%20")
            filter_param = f'["name","{encoded_book_name}"]'
            url = f"{BACKEND_API_URL}/api/product/get-all?filter={filter_param}"
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"API call failed for get-all '{book_name}': {response.status}")
                    return None
                data = await response.json()
                if data.get("status") != "OK" or not data.get("data"):
                    logger.error(f"No product found for '{book_name}'")
                    return None
                product = data["data"][0]  # Lấy sản phẩm đầu tiên khớp
                product_id = str(product["_id"])

            # Bước 2: Gọi API get-detail với _id
            url = f"{BACKEND_API_URL}/api/product/get-detail/{product_id}"
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("status") == "OK":
                        return result
                    else:
                        logger.error(f"API get-detail returned non-OK status for ID '{product_id}'")
                        return None
                else:
                    logger.error(f"API call failed for get-detail '{product_id}': {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching book details for '{book_name}': {e}")
        return None

async def get_response_from_rules(user_input, session_id, user_id, context):
    """Generate response based on rules and intent."""
    try:
        from backend.nlp.intent_predictor import predict_intent
        intent, confidence = predict_intent(user_input)
        logger.info(f"Predicted intent: {intent}, Confidence: {confidence}")

        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        response_data = {
            "response": "Xin lỗi, mình không hiểu ý bạn. Hãy thử lại nhé!",
            "intent": intent,
            "confidence": confidence,
            "context": context or {}
        }

        if context:
            db["chat_logs"].update_one(
                {"session_id": session_id},
                {"$set": {"context": context, "last_intent": intent, "last_input": user_input}},
                upsert=True
            )

        for intent_data in intents["intents"]:
            if intent_data["tag"] == intent:
                if intent == "book_find_book" or intent == "book_book_details":
                    book_name = extract_book_name(user_input)
                    if book_name:
                        book_details = await fetch_book_details(book_name)
                        if book_details and book_details.get("status") == "OK":
                            book = book_details["data"]
                            response_data["response"] = (
                                f"Thông tin sách {book['name']}: {book['description']} Giá: {book['price']} VND."
                                if intent == "book_book_details"
                                else f"Tìm thấy sách: {book['name']}!"
                            )
                            response_data["context"] = {"book_name": book['name'], "book_id": str(book['_id'])}
                        else:
                            response_data["response"] = f"Không tìm thấy sách '{book_name}'. Bạn kiểm tra lại tên sách nhé!"
                    else:
                        response_data["response"] = "Vui lòng cung cấp tên sách để tìm!"
                elif intent == "book_promotion":
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{BACKEND_API_URL}/api/promotion") as response:
                            if response.status == 200:
                                promotions = await response.json()
                                if promotions:
                                    promo = promotions[0]
                                    response_data["response"] = f"Khuyến mãi hiện tại: {promo['description']} (Giảm {promo['value']}%)."
                                else:
                                    response_data["response"] = "Hiện tại không có khuyến mãi nào."
                            else:
                                response_data["response"] = "Không thể lấy thông tin khuyến mãi. Vui lòng thử lại sau!"
                elif intent == "general_accept":
                    chat_log = db["chat_logs"].find_one({"session_id": session_id})
                    if chat_log and "context" in chat_log and "book_name" in chat_log["context"]:
                        book_name = chat_log["context"]["book_name"]
                        book_details = await fetch_book_details(book_name)
                        if book_details and book_details.get("status") == "OK":
                            book = book_details["data"]
                            response_data["response"] = f"Thông tin sách {book['name']}: {book['description']} Giá: {book['price']} VND."
                            response_data["context"] = {"book_name": book['name'], "book_id": str(book['_id'])}
                        else:
                            response_data["response"] = f"Không tìm thấy chi tiết sách '{book_name}'. Bạn kiểm tra lại tên sách nhé!"
                    else:
                        response_data["response"] = "Bạn đang xác nhận điều gì? Vui lòng cung cấp thêm thông tin!"
                else:
                    response_data["response"] = intent_data["responses"][0]
                break

        db["chat_logs"].update_one(
            {"session_id": session_id},
            {"$set": {
                "user_id": user_id,
                "user_input": user_input,
                "bot_response": response_data["response"],
                "intent": intent,
                "confidence": confidence,
                "timestamp": datetime.now()
            }},
            upsert=True
        )
        client.close()
        return response_data
    except Exception as e:
        logger.error(f"Error in get_response_from_rules: {e}")
        client.close()
        return {"response": "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại!", "intent": "error", "confidence": 0.0}