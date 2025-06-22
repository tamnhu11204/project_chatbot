import os
import json
import joblib
import torch
from transformers import AutoTokenizer
from backend.nlp.intent_model import IntentModel
from backend.config.settings import INTENTS_PATH, BOOK_INTENTS_PATH, LABEL_ENCODER_PATH

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "phobert_finetuned")

def load_intents():
    intents_data = []
    if os.path.exists(INTENTS_PATH):
        try:
            with open(INTENTS_PATH, "r", encoding="utf-8") as f:
                intents_data.extend(json.load(f)["intents"])
        except Exception as e:
            raise Exception(f"Failed to load intents.json: {e}")
    else:
        raise FileNotFoundError(f"intents.json not found at {INTENTS_PATH}")

    if os.path.exists(BOOK_INTENTS_PATH):
        try:
            with open(BOOK_INTENTS_PATH, "r", encoding="utf-8") as f:
                intents_data.extend(json.load(f)["intents"])
        except Exception as e:
            print(f"Warning: Failed to load book_intents.json: {e}")
    return intents_data

def load_model():
    if not os.path.exists(MODEL_DIR):
        raise FileNotFoundError(f"Model directory not found at {MODEL_DIR}. Run `python -m backend.nlp.train_model`")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    label_encoder = joblib.load(LABEL_ENCODER_PATH)
    model = IntentModel(num_classes=len(label_encoder), dropout=0.3)
    model_path = os.path.join(MODEL_DIR, "model.pt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at {model_path}. Run `python -m backend.nlp.train_model`")
    model.load_state_dict(torch.load(model_path, map_location=torch.device("cpu")))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    print(f"Debug: Loaded Transformer model from {MODEL_DIR}")
    return model, tokenizer, label_encoder, device

def get_response(intent, intents_data, context=None):
    for intent_data in intents_data:
        if intent_data["tag"] == intent:
            response = intent_data["responses"][0] if intent_data["responses"] else "Xin lỗi, tôi không hiểu."
            if context and "book" in context:
                response = f"{response} (Sách: {context['book']})"
            return response
    return "Xin lỗi, tôi không hiểu."

def predict_intent(text, context=None):
    print(f"Debug: Processing text='{text}', context={context}")
    intents_data = load_intents()
    model, tokenizer, label_encoder, device = load_model()
    
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=64
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(inputs["input_ids"], inputs["attention_mask"])
        probabilities = torch.softmax(outputs, dim=1)
        confidence, predicted = torch.max(probabilities, 1)
    
    intent = label_encoder[predicted.item()]
    confidence = confidence.item()
    response = get_response(intent, intents_data, context)
    print(f"Debug: Transformer predicts intent={intent}, confidence={confidence}")
    return intent, confidence, response