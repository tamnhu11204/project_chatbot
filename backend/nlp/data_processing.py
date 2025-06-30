from pymongo import MongoClient
import json
import os
try:
    from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
except ImportError:
    from config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
try:
    from backend.nlp.utils import is_valid_sentence, clean_text, suggest_intent
except ImportError:
    from nlp.utils import is_valid_sentence, clean_text, suggest_intent
from datetime import datetime
import nlpaug.augmenter.word as naw

import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kết nối MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client[MONGO_DB]
    logger.info("MongoDB connected successfully for data_processing")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

chat_logs = db["chat_logs"]
suggestions = db["suggestions"]

def analyze_logs():
    """Analyze low-confidence logs and save suggestions to MongoDB."""
    try:
        low_conf_logs = chat_logs.find(
            {"confidence": {"$lt": 0.5}},
            {"user": 1, "intent": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(100)
        suggestions_data = []
        for log in low_conf_logs:
            user_text = log.get("user")
            intent = log.get("intent")
            if is_valid_sentence(user_text):
                suggested_intent = suggest_intent(user_text, threshold=0.7)
                suggestions_data.append({"tag": suggested_intent or intent, "pattern": clean_text(user_text)})
        
        if suggestions_data:
            suggestions.insert_one({
                "suggestions": suggestions_data,
                "timestamp": datetime.now()
            })
            logger.info(f"Saved {len(suggestions_data)} suggestions to MongoDB")
    except Exception as e:
        logger.error(f"Error analyzing logs: {e}")

def collect_logs_for_training():
    """Collect high-confidence logs and save to augmented_training_data.json."""
    try:
        high_conf_logs = chat_logs.find(
            {"confidence": {"$gte": 0.8}},
            {"user": 1, "intent": 1}
        ).limit(100)
        augmented_data = {"intents": []}
        intent_patterns = {}
        
        for log in high_conf_logs:
            user_text = log.get("user")
            intent = log.get("intent")
            if is_valid_sentence(user_text):
                cleaned_text = clean_text(user_text)
                if intent not in intent_patterns:
                    intent_patterns[intent] = []
                intent_patterns[intent].append(cleaned_text)
        
        # Augment patterns
        aug = naw.SynonymAug(aug_src='wordnet', lang='vie')
        for intent, patterns in intent_patterns.items():
            augmented_patterns = []
            for pattern in patterns:
                augmented_patterns.append(pattern)
                try:
                    augmented_patterns.extend(aug.augment(pattern, n=2))
                except Exception as e:
                    logger.warning(f"Error augmenting pattern '{pattern}': {e}")
            augmented_data["intents"].append({
                "tag": intent,
                "patterns": augmented_patterns,
                "responses": []
            })
        
        output_path = os.path.join(os.path.dirname(INTENTS_PATH), "augmented_training_data.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(augmented_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved augmented data to {output_path}")
    except Exception as e:
        logger.error(f"Error collecting logs for training: {e}")

def generate_patterns_from_backend():
    """Generate patterns from Product and Promotion collections."""
    try:
        patterns = {
            "find_book": [],
            "book_price": [],
            "stock_check": [],
            "promotion": []
        }
        products = db["Product"].find({}, {"name": 1, "author": 1, "category": 1}).limit(50)
        for product in products:
            name = product.get("name", "")
            author = product.get("author", "")
            category = product.get("category", "")
            if is_valid_sentence(name):
                patterns["find_book"].extend([
                    clean_text(f"Tìm sách {name}"),
                    clean_text(f"Sách của {author} có không?") if author else "",
                    clean_text(f"Tìm sách thuộc danh mục {category}") if category else ""
                ])
                patterns["book_price"].extend([
                    clean_text(f"Sách {name} giá bao nhiêu?"),
                    clean_text(f"Giá cuốn {name} là bao nhiêu?"),
                    clean_text(f"Sách {name} có giảm giá không?")
                ])
                patterns["stock_check"].extend([
                    clean_text(f"Sách {name} còn hàng không?"),
                    clean_text(f"Còn bao nhiêu cuốn {name}?")
                ])
        
        promotions = db["Promotion"].find({}, {"value": 1}).limit(50)
        for promo in promotions:
            value = promo.get("value", "")
            if value:
                patterns["promotion"].extend([
                    clean_text(f"Có mã giảm giá {value}% không?"),
                    clean_text(f"Khuyến mãi {value}% còn áp dụng không?")
                ])
        
        return {k: [p for p in v if p] for k, v in patterns.items()}
    except Exception as e:
        logger.error(f"Error generating patterns from backend: {e}")
        return {}

def extract_from_live_chat():
    """Extract patterns from LiveChatMessage."""
    try:
        messages = db["LiveChatMessage"].find(
            {"sender": "user", "isHandled": True},
            {"message": 1}
        ).limit(100)
        new_patterns = []
        for msg in messages:
            message = msg.get("message")
            if not is_valid_sentence(message):
                continue
            cleaned_message = clean_text(message)
            intent = suggest_intent(cleaned_message, threshold=0.7)
            if intent:
                new_patterns.append({"intent": intent, "pattern": cleaned_message})
            else:
                # Phân loại dựa trên từ khóa
                message_lower = message.lower()
                if any(kw in message_lower for kw in ["tìm", "sách", "có"]):
                    new_patterns.append({"intent": "find_book", "pattern": cleaned_message})
                elif any(kw in message_lower for kw in ["giá", "bao nhiêu"]):
                    new_patterns.append({"intent": "book_price", "pattern": cleaned_message})
                elif any(kw in message_lower for kw in ["còn hàng", "tồn kho"]):
                    new_patterns.append({"intent": "stock_check", "pattern": cleaned_message})
                elif any(kw in message_lower for kw in ["khuyến mãi", "giảm giá"]):
                    new_patterns.append({"intent": "promotion", "pattern": cleaned_message})
        
        return new_patterns
    except Exception as e:
        logger.error(f"Error extracting from live chat: {e}")
        return []

def save_patterns():
    """Save generated patterns to augmented_training_data.json."""
    try:
        backend_patterns = generate_patterns_from_backend()
        live_chat_patterns = extract_from_live_chat()
        intent_patterns = {}
        
        for intent in backend_patterns:
            intent_patterns[intent] = backend_patterns[intent] + [
                p["pattern"] for p in live_chat_patterns if p["intent"] == intent
            ]
        
        intents = [{"tag": intent, "patterns": patterns, "responses": []} for intent, patterns in intent_patterns.items()]
        output_path = os.path.join(os.path.dirname(INTENTS_PATH), "augmented_training_data.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"intents": intents}, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved patterns to {output_path}")
    except Exception as e:
        logger.error(f"Error saving patterns: {e}")

if __name__ == "__main__":
    analyze_logs()
    collect_logs_for_training()
    save_patterns()