from pymongo import MongoClient
import json
import os
from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from datetime import datetime

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
chat_logs = db["chat_logs"]
wrong_responses = db["wrong_responses"]
suggestions = db["suggestions"]

tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
model = AutoModel.from_pretrained("vinai/phobert-base")


def update_intents_from_feedback():
    with open(INTENTS_PATH, "r", encoding="utf-8") as f:
        intents_data = json.load(f)
    tag_to_intent = {intent["tag"]: intent for intent in intents_data["intents"]}
    updated = False

    # Từ chat_logs (negative feedback)
    for log in chat_logs.find({"user_feedback": "negative"}):
        sentence = log["user"].strip()
        intent = suggest_intent(sentence, intents_data) or log["intent"]
        if is_valid_sentence(sentence) and intent in tag_to_intent:
            if sentence not in tag_to_intent[intent]["patterns"]:
                tag_to_intent[intent]["patterns"].append(sentence)
                updated = True

    # Từ wrong_responses
    for log in wrong_responses.find():
        sentence = log["user_input"].strip()
        intent = suggest_intent(sentence, intents_data) or log["intent"]
        if is_valid_sentence(sentence) and intent in tag_to_intent:
            if sentence not in tag_to_intent[intent]["patterns"]:
                tag_to_intent[intent]["patterns"].append(sentence)
                updated = True

    if updated:
        with open(INTENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(intents_data, f, ensure_ascii=False, indent=4)
        chat_logs.delete_many({"user_feedback": "negative"})
        wrong_responses.delete_many({})
        print("✅ Đã cập nhật intents.")
        from backend.nlp.retrain_manager import auto_retrain

        auto_retrain()


def suggest_intent(user_input, intents_data):
    user_embedding = get_embedding(user_input)
    best_score = -1
    best_intent = None
    for intent in intents_data["intents"]:
        for pattern in intent["patterns"]:
            pattern_embedding = get_embedding(pattern)
            score = cosine_similarity(user_embedding, pattern_embedding)
            if score > best_score:
                best_score = score
                best_intent = intent["tag"]
    return best_intent if best_score > 0.7 else None


def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state[:, 0, :].numpy()


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def is_valid_sentence(sentence):
    return len(sentence.strip()) >= 3 and not sentence.isspace()
