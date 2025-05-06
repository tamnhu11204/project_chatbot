from pymongo import MongoClient
import json
import os
from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
from datetime import datetime

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
chat_logs = db["chat_logs"]
suggestions = db["suggestions"]


def analyze_logs():
    low_conf_logs = chat_logs.find({"confidence": {"$lt": 0.5}}).sort("timestamp", -1)
    suggestions_data = []
    for log in low_conf_logs:
        user_text = log["user"]
        intent = log["intent"]
        if is_valid_sentence(user_text):
            suggestions_data.append({"tag": intent, "pattern": user_text})
    if suggestions_data:
        suggestions.insert_one(
            {"suggestions": suggestions_data, "timestamp": datetime.now()}
        )
        print("✅ Đã lưu gợi ý vào MongoDB.")


def collect_logs_for_training():
    high_conf_logs = chat_logs.find({"confidence": {"$gte": 0.8}})
    augmented_data = {"intents": []}
    for log in high_conf_logs:
        intent = log["intent"]
        user_text = log["user"]
        if is_valid_sentence(user_text):
            augmented_data["intents"].append(
                {"tag": intent, "patterns": [user_text], "responses": []}
            )
    with open(
        os.path.join(os.path.dirname(INTENTS_PATH), "augmented_training_data.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(augmented_data, f, ensure_ascii=False, indent=2)
    print("✅ Đã lưu dữ liệu bổ sung.")


def merge_suggestions():
    latest_suggestions = suggestions.find_one(sort=[("timestamp", -1)])
    if not latest_suggestions:
        print("❌ Không có gợi ý để merge.")
        return
    with open(INTENTS_PATH, "r", encoding="utf-8") as f:
        intents_data = json.load(f)
    tag_to_intent = {intent["tag"]: intent for intent in intents_data["intents"]}
    merged_count = 0
    for suggestion in latest_suggestions["suggestions"]:
        tag = suggestion["tag"]
        pattern = suggestion["pattern"]
        if tag in tag_to_intent and is_valid_sentence(pattern):
            if pattern not in tag_to_intent[tag]["patterns"]:
                tag_to_intent[tag]["patterns"].append(pattern)
                merged_count += 1
    if merged_count:
        with open(INTENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(intents_data, f, ensure_ascii=False, indent=2)
        suggestions.delete_one({"_id": latest_suggestions["_id"]})
        print(f"✅ Đã merge {merged_count} mẫu mới.")
    else:
        print("✅ Không có gì mới để merge.")


def is_valid_sentence(sentence):
    return len(sentence.strip()) >= 3 and not sentence.isspace()
