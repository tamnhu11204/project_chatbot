from fastapi import APIRouter, Request, HTTPException
from backend.nlp.intent_predictor import predict_intent
from backend.logic.rules import get_response
from backend.logic.mongo_logger import log_conversation
import uuid
from backend.config.settings import FACEBOOK_PAGE_TOKEN, FACEBOOK_VERIFY_TOKEN
import requests

router = APIRouter()


@router.get("/webhook")
async def facebook_verify(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == FACEBOOK_VERIFY_TOKEN:
        return params.get("hub.challenge")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("/webhook")
async def facebook_webhook(request: Request):
    body = await request.json()
    session_id = str(uuid.uuid4())[:8]
    for entry in body.get("entry", []):
        for messaging in entry.get("messaging", []):
            user_input = messaging.get("message", {}).get("text")
            if user_input:
                intent, confidence = predict_intent(user_input)
                response = get_response(intent, confidence)
                log_conversation(user_input, intent, confidence, response, session_id)
                send_facebook_message(messaging["sender"]["id"], response)
    return {"status": "success"}


def send_facebook_message(sender_id, message):
    url = f"https://graph.facebook.com/v13.0/me/messages?access_token={FACEBOOK_PAGE_TOKEN}"
    data = {"recipient": {"id": sender_id}, "message": {"text": message}}
    requests.post(url, json=data)
