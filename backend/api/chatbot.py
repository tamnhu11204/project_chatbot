import os
import sys
import requests
import uuid

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.nlp.intent_predictor import predict_intent
from backend.logic.rules import get_response_from_rules
from backend.nlp.intent_updater import add_pattern_to_intent


def request_admin_support(user_id, message):
    try:
        response = requests.post(
            "http://localhost:3001/api/chat/support",
            json={"userId": user_id, "message": message},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code == 201:
            print(f"📢 Đã gửi yêu cầu hỗ trợ đến admin cho userId: {user_id}")
            return True
        else:
            print(f"⚠️ Lỗi gửi yêu cầu hỗ trợ: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ Lỗi gửi yêu cầu hỗ trợ: {e}")
        return False


def run_chatbot():
    session_id = str(uuid.uuid4())[:8]
    user_id = f"guest_{session_id}"
    print("🤖 Chào bạn! Nhập 'exit' để thoát.")

    while True:
        user_input = input("Bạn: ").strip()
        if user_input.lower() == "exit":
            break

        intent, confidence = predict_intent(user_input)
        response = get_response_from_rules(intent, confidence)
        print(f"Bot: {response}")
        print(f"Debug: Intent = {intent}, Confidence = {confidence}")

        if intent == "fallback" or intent == "support":
            request_admin_support(user_id, f"Chatbot cần hỗ trợ: {user_input}")
            print(
                "Bot: Mình đã gửi yêu cầu hỗ trợ đến admin. Vui lòng chờ trong giây lát!"
            )
            continue

        feedback = input("Phản hồi (like/dislike): ").strip().lower()
        if feedback == "dislike":
            correct_intent = input("Intent đúng là gì? ").strip()
            if correct_intent:
                add_pattern_to_intent(correct_intent, user_input)
                print("✅ Đã cập nhật intent.")
                request_admin_support(
                    user_id, f"Khách hàng không hài lòng với phản hồi cho: {user_input}"
                )
                print(
                    "Bot: Mình đã gửi yêu cầu hỗ trợ đến admin. Vui lòng chờ trong giây lát!"
                )
        else:
            print("Bot: Cảm ơn bạn đã thích phản hồi!")


if __name__ == "__main__":
    run_chatbot()
