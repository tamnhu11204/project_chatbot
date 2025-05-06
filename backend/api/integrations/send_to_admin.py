import requests
import os
from backend.config.settings import API_BASE_URL


def send_to_admin(message):
    token = os.getenv("ADMIN_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/chat/send", headers=headers, json={"message": message}
        )
        if response.ok:
            print("📨 Đã gửi yêu cầu hỗ trợ đến admin.")
        else:
            print(f"❌ Lỗi khi gửi yêu cầu: {response.text}")
    except Exception as e:
        print(f"🚨 Lỗi khi gửi yêu cầu hỗ trợ: {e}")
