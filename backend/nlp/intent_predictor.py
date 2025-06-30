import torch
import joblib
import logging
from transformers import AutoTokenizer

try:
    from backend.config.settings import MODEL_PATH, LABEL_ENCODER_PATH
except ImportError:
    from config.settings import MODEL_PATH, LABEL_ENCODER_PATH
try:
    from backend.nlp.utils import  clean_text, suggest_intent
except ImportError:
    from nlp.utils import  clean_text, suggest_intent
try:
    from backend.nlp.intent_model import IntentModel
except ImportError:
    from nlp.intent_model import IntentModel


# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentPredictor:
    def __init__(self):
        try:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
            self.model = IntentModel(num_classes=12).to(self.device)
            self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
            self.model.eval()
            self.label_encoder = joblib.load(LABEL_ENCODER_PATH)
            logger.info("IntentPredictor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize IntentPredictor: {str(e)}")
            raise

    def predict(self, text):
        try:
            cleaned_text = clean_text(text)
            if not cleaned_text:
                return "general_unknown", 0.0

            # Dự đoán bằng mô hình PhoBERT
            inputs = self.tokenizer(
                cleaned_text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=64
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(inputs["input_ids"], inputs["attention_mask"])
                probabilities = torch.softmax(outputs, dim=1)
                confidence, predicted_idx = torch.max(probabilities, dim=1)
                predicted_intent = self.label_encoder.inverse_transform([predicted_idx.item()])[0]

            # Sử dụng suggest_intent nếu confidence thấp
            if confidence < 0.85:
                suggested_intent = suggest_intent(cleaned_text, threshold=0.6)
                if suggested_intent:
                    logger.info(f"Fallback to suggested intent: {suggested_intent}, Original: {predicted_intent}, Confidence: {confidence}")
                    return suggested_intent, 0.8

            logger.info(f"Model predicted intent: {predicted_intent}, Confidence: {confidence}")
            return predicted_intent, float(confidence)
        except Exception as e:
            logger.error(f"Error predicting intent: {e}")
            return "general_unknown", 0.0

def predict_intent(text):
    """Wrapper function to predict intent."""
    try:
        predictor = IntentPredictor()
        return predictor.predict(text)
    except Exception as e:
        logger.error(f"Error in predict_intent: {e}")
        return "general_unknown", 0.0