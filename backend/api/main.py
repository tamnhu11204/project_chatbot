from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.nlp.intent_predictor import predict_intent
from backend.logic.rules import get_response_from_rules
from backend.nlp.intent_updater import add_pattern_to_intent
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


class Message(BaseModel):
    message: str


class Feedback(BaseModel):
    user_input: str
    bot_response: str
    feedback: str


@app.post("/predict")
async def predict_message(message: Message):
    intent, confidence = predict_intent(message.message)
    response = get_response_from_rules(intent, confidence)
    return {"response": response, "intent": "fallback" if confidence < 0.5 else intent}


@app.post("/feedback")
async def feedback(feedback: Feedback):
    if feedback.feedback == "dislike":
        print(
            f"Feedback: {feedback.user_input} -> {feedback.bot_response} ({feedback.feedback})"
        )
    return {"status": "success"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"status": "success", "filename": file.filename}


@app.get("/chatbot-ui", response_class=HTMLResponse)
async def get_chatbot_ui():
    try:
        with open("frontend/templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="Error: index.html not found in frontend/templates", status_code=404
        )


@app.get("/static/widget.js")
async def get_widget():
    return FileResponse("frontend/static/widget.js")
