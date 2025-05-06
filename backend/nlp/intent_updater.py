import json
import os
from backend.config.settings import INTENTS_PATH, BOOK_INTENTS_PATH, MODEL_PATH
from backend.nlp.train_model import train_and_save_model


def add_pattern_to_intent(intent_tag, new_pattern):
    def is_valid_sentence(sentence):
        return len(sentence.strip()) >= 3 and not sentence.isspace()

    intents_files = [
        (INTENTS_PATH, ["greeting", "goodbye", "open_hour", "accept", "unknown"]),
        (
            BOOK_INTENTS_PATH,
            [
                "book_price",
                "find_book",
                "order_book",
                "support",
                "promotion",
                "order_status",
            ],
        ),
    ]

    target_path = INTENTS_PATH
    for path, tags in intents_files:
        if intent_tag in tags:
            target_path = path
            break

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = False
    for intent in data["intents"]:
        if intent["tag"] == intent_tag:
            if is_valid_sentence(new_pattern) and new_pattern not in intent["patterns"]:
                intent["patterns"].append(new_pattern)
                updated = True
            break
    else:
        if is_valid_sentence(new_pattern):
            data["intents"].append(
                {
                    "tag": intent_tag,
                    "patterns": [new_pattern],
                    "responses": [
                        "Xin lỗi, mình chưa có phản hồi cụ thể cho yêu cầu này."
                    ],
                }
            )
            updated = True

    if updated:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ Đã thêm mẫu mới vào intent '{intent_tag}': \"{new_pattern}\"")
        print("⏳ Đang retrain model với pattern mới...")
        train_and_save_model()  # Sửa dòng này
        print("✅ Đã retrain model.")

    return updated
