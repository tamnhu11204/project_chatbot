import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MongoDB settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB_NAME", "chatbot_db")

# Paths
INTENTS_PATH = os.path.join(BASE_DIR, "data", "intents.json")
BOOK_INTENTS_PATH = os.path.join(BASE_DIR, "data", "book_intents.json")
MODEL_PATH = os.path.join(BASE_DIR, "nlp", "phobert_finetuned", "model.pt")
LABEL_ENCODER_PATH = os.path.join(BASE_DIR, "nlp", "models", "label_encoder.pkl")

# API settings
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Social media settings
FACEBOOK_PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN", "")
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
ZALO_API_KEY = os.getenv("ZALO_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")