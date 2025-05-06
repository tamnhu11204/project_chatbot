import torch
import numpy as np
from transformers import AutoTokenizer
from backend.nlp.intent_model import IntentModel
from backend.nlp.text_preprocessing import clean_text
from backend.config.settings import MODEL_PATH, LABEL_ENCODER_PATH


class IntentPredictor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
        self.model = IntentModel(
            num_classes=len(np.load(LABEL_ENCODER_PATH, allow_pickle=True))
        )
        self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()
        self.label_encoder = np.load(LABEL_ENCODER_PATH, allow_pickle=True)
        print(f"Debug: Loaded intents = {self.label_encoder}")

    def predict(self, text):
        text = clean_text(text)
        print(f"Debug: Cleaned text = {text}")
        encoding = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=64,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)
            probabilities = torch.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, dim=1)
            print(f"Debug: Probabilities = {probabilities.cpu().numpy()}")

        intent = self.label_encoder[predicted.item()]
        confidence_value = confidence.item()
        if confidence_value < 0.15 and intent not in ["greeting", "support"]:
            print(
                f"Debug: Fallback triggered for intent = {intent}, confidence = {confidence_value}"
            )
            return "fallback", confidence_value
        return intent, confidence_value


predictor = IntentPredictor()


def predict_intent(text):
    return predictor.predict(text)
