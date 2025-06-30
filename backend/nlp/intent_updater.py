import logging
from pymongo import MongoClient
try:
    from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
except ImportError:
    from config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
import json
import os

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_intents():
    """Update intents.json with new patterns from suggestions."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        suggestions = db["suggestions"].find()

        intents = {"intents": []}
        if os.path.exists(INTENTS_PATH):
            with open(INTENTS_PATH, "r", encoding="utf-8-sig") as f:
                intents = json.load(f)
        else:
            logger.error(f"Intents file not found at {INTENTS_PATH}")
            return False

        for suggestion in suggestions:
            intent_tag = suggestion.get("intent")
            pattern = suggestion.get("pattern")
            if not intent_tag or not pattern:
                logger.warning(f"Invalid suggestion: {suggestion}")
                continue

            # Find or create intent
            intent_found = False
            for intent in intents["intents"]:
                if intent["tag"] == intent_tag:
                    if pattern not in intent["patterns"]:
                        intent["patterns"].append(pattern)
                        logger.info(f"Added pattern '{pattern}' to intent '{intent_tag}'")
                    intent_found = True
                    break

            if not intent_found:
                intents["intents"].append({
                    "tag": intent_tag,
                    "patterns": [pattern],
                    "responses": [f"Đã thêm intent mới cho {intent_tag}"]
                })
                logger.info(f"Created new intent '{intent_tag}' with pattern '{pattern}'")

        # Save updated intents
        os.makedirs(os.path.dirname(INTENTS_PATH), exist_ok=True)
        with open(INTENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(intents, f, ensure_ascii=False, indent=4)
        logger.info(f"Updated intents saved to {INTENTS_PATH}")

        # Clear suggestions after updating
        db["suggestions"].delete_many({})
        logger.info("Cleared suggestions collection")
        client.close()
        return True
    except Exception as e:
        logger.error(f"Error updating intents: {str(e)}")
        client.close()
        return False