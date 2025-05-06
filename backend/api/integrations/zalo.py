from fastapi import APIRouter, Request, HTTPException
from backend.nlp.intent_predictor import predict_intent
from backend.logic.rules import get_response
from backend.logic.mongo_logger import log_conversation
import uuid
from backend.config.settings import ZALO_API_KEY
import requests

router = APIRouter()


@router.post("/webhook")
async def zalo_webhook(request: Request):
    body = await request.json()
    session_id = str(uuid.uuid4())[:8]
    user_input = body.get("message", {}).get("text")
    user_id = body.get("userId")

    if user_input and user_id:
        intent, confidence = predict_intent(user_input)
        response = get_response(intent, confidence)
        log_conversation(user_input, intent, confidence, response, session_id)
        send_zalo_message(user_id, response)

    return {"status": "success"}


def send_zalo_message(user_id, message):
    url = "https://openapi.zalo.me/v2.0/oa/message"
    headers = {"access_token": ZALO_API_KEY}
    data = {"recipient": {"user_id": user_id}, "message": {"text": message}}
    requests.post(url, headers=headers, json=data)
