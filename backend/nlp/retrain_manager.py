from pymongo import MongoClient
import json
import os
from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
from backend.nlp.train_model import train_intent_model
from datetime import datetime

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
retrain_history = db["retrain_history"]

def should_retrain(last_count):
    current_count = count_total_patterns()
    return (current_count - last_count) >= 50

def count_total_patterns():
    try:
        with open(INTENTS_PATH, "r", encoding="utf-8-sig") as f:
            intents = json.load(f)
        return sum(len(intent["patterns"]) for intent in intents["intents"])
    except Exception as e:
        print(f"Error reading intents.json: {e}")
        raise

def get_last_count():
    last_record = retrain_history.find_one(sort=[("timestamp", -1)])
    return last_record["total_patterns"] if last_record else 0

def save_current_count(count):
    retrain_history.insert_one({"total_patterns": count, "timestamp": datetime.now()})

def auto_retrain():
    last_count = get_last_count()
    if should_retrain(last_count):
        print("🚀 Đang huấn luyện lại mô hình Transformer...")
        try:
            train_intent_model()
            save_current_count(count_total_patterns())
            print("✅ Đã huấn luyện lại mô hình Transformer.")
        except Exception as e:
            print(f"❌ Lỗi khi huấn luyện: {e}")
            raise
    else:
        print("⏳ Chưa cần retrain mô hình.")