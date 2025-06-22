from pymongo import MongoClient
import json
import os
from backend.config.settings import MONGO_URI, MONGO_DB, INTENTS_PATH
from datetime import datetime
import nlpaug.augmenter.word as naw

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

def generate_patterns_from_backend():
    patterns = {
        "find_book": [],
        "book_price": [],
        "stock_check": [],
        "promotion": []
    }
    # Lấy dữ liệu sản phẩm
    products = db["Product"].find()
    for product in products:
        name = product["name"]
        author = product["author"]
        category = product.get("category", "")
        patterns["find_book"].extend([
            f"Tìm sách {name}",
            f"Sách của {author} có không?",
            f"Tìm sách thuộc danh mục {category}"
        ])
        patterns["book_price"].extend([
            f"Sách {name} giá bao nhiêu?",
            f"Giá cuốn {name} là bao nhiêu?",
            f"Sách {name} có giảm giá không?"
        ])
        patterns["stock_check"].extend([
            f"Sách {name} còn hàng không?",
            f"Còn bao nhiêu cuốn {name}?"
        ])
    # Lấy dữ liệu khuyến mãi
    promotions = db["Promotion"].find()
    for promo in promotions:
        value = promo["value"]
        patterns["promotion"].extend([
            f"Có mã giảm giá {value}% không?",
            f"Khuyến mãi {value}% còn áp dụng không?"
        ])
    return patterns

def extract_from_live_chat():
    messages = db["LiveChatMessage"].find({"sender": "user", "isHandled": True})
    new_patterns = []
    for msg in messages:
        message = msg["message"]
        # Phân loại dựa trên từ khóa (logic programming)
        if any(kw in message.lower() for kw in ["tìm", "sách", "có"]):
            new_patterns.append({"intent": "find_book", "pattern": message})
        elif any(kw in message.lower() for kw in ["giá", "bao nhiêu"]):
            new_patterns.append({"intent": "book_price", "pattern": message})
        elif any(kw in message.lower() for kw in ["còn hàng", "tồn kho"]):
            new_patterns.append({"intent": "stock_check", "pattern": message})
        elif any(kw in message.lower() for kw in ["khuyến mãi", "giảm giá"]):
            new_patterns.append({"intent": "promotion", "pattern": message})
    return new_patterns

def save_patterns():
    backend_patterns = generate_patterns_from_backend()
    live_chat_patterns = extract_from_live_chat()
    intents = []
    for intent in backend_patterns:
        patterns = backend_patterns[intent] + [p["pattern"] for p in live_chat_patterns if p["intent"] == intent]
        intents.append({"tag": intent, "patterns": patterns, "responses": []})
    with open("new_intents.json", "w", encoding="utf-8") as f:
        json.dump({"intents": intents}, f, ensure_ascii=False, indent=2)

def analyze_live_chat():
    messages = db["LiveChatMessage"].find({"sender": "user"})
    patterns = []
    for msg in messages:
        message = msg["message"]
        user_id = msg["user"]
        admin_reply = db["LiveChatMessage"].find_one({
            "sender": "admin",
            "user": user_id,
            "timestamp": {"$gt": msg["timestamp"]}
        })
        if admin_reply:
            intent, _ = predict_intent(message)
            patterns.append({
                "intent": intent,
                "pattern": message,
                "response": admin_reply["message"]
            })
    return patterns

def augment_patterns(patterns):
    aug = naw.SynonymAug(aug_src='wordnet', lang='vie')
    augmented = []
    for pattern in patterns:
        augmented.extend(aug.augment(pattern["pattern"], n=3))
    return [{"intent": pattern["intent"], "pattern": aug} for aug in augmented]

def update_intents():
    patterns = analyze_live_chat()
    augmented_patterns = augment_patterns(patterns)
    intents = load_intents("intents.json")
    for p in patterns + augmented_patterns:
        for intent in intents["intents"]:
            if intent["tag"] == p["intent"]:
                intent["patterns"].append(p["pattern"])
                if "response" in p:
                    intent["responses"].append(p["response"])
    with open("intents.json", "w", encoding="utf-8") as f:
        json.dump(intents, f, ensure_ascii=False, indent=2)