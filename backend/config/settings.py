import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB_NAME", "chatbot_db")
INTENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "intents.json")
BOOK_INTENTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "book_intents.json"
)
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model", "chatbot_model.pt")
LABEL_ENCODER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "model", "label_encoder.npy"
)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
FACEBOOK_PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN", "")
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
ZALO_API_KEY = os.getenv("ZALO_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
