from pymongo import MongoClient
import json
import os
from backend.config.settings import (
    MONGO_URI,
    MONGO_DB,
    INTENTS_PATH,
    MODEL_PATH,
    LABEL_ENCODER_PATH,
)
from backend.nlp.train_model import train_intent_model
from datetime import datetime

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
retrain_history = db["retrain_history"]


def should_retrain(last_count):
    current_count = count_total_patterns()
    return (current_count - last_count) >= 50


def count_total_patterns():
    with open(INTENTS_PATH, "r") as f:
        intents = json.load(f)
    return sum(len(intent["patterns"]) for intent in intents["intents"])


def get_last_count():
    last_record = retrain_history.find_one(sort=[("timestamp", -1)])
    return last_record["total_patterns"] if last_record else 0


def save_current_count(count):
    retrain_history.insert_one({"total_patterns": count, "timestamp": datetime.now()})


def auto_retrain():
    last_count = get_last_count()
    if should_retrain(last_count):
        print("🚀 Đang huấn luyện lại mô hình...")
        try:
            train_intent_model(INTENTS_PATH, os.path.dirname(MODEL_PATH))
            save_current_count(count_total_patterns())
            print("✅ Đã huấn luyện lại mô hình.")
        except Exception as e:
            print(f"❌ Lỗi khi huấn luyện: {e}")
    else:
        print("⏳ Chưa cần retrain mô hình.")
