import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MongoDB settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://tamnhu11204:nhunguyen11204@cluster0.kezkc.mongodb.net/")
MONGO_DB = os.getenv("MONGO_DB_NAME", "chatbot_db")

# Paths
INTENTS_PATH = os.path.join(BASE_DIR, "data", "intents.json")
MODEL_PATH = os.path.join(BASE_DIR, "phobert_finetuned", "model.pt")
LABEL_ENCODER_PATH = os.path.join(BASE_DIR, "nlp", "models", "label_encoder.pkl")

# API settings
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3001")

# Social media settings
FACEBOOK_PAGE_TOKEN = "EAAI3e5lZA5S4BO3lamZCtba2UQdWoOGHekKnN6ULsirX6ZB3H6toZAx1QQp6hS32kgkKYXZBcAGOEPFy0VMH6F98WZBpNvG23P5WCF1T86PAoqumZBVyfyIl9EGZC2vnZC1eL2hZCICwwZCgYcJZAWN9Jae9mFtQRr7M1HB8d0MdTLZCxafSHVZAZANiGAb6WRid4svnuuMgGGVf8XGUwZDZD"
FACEBOOK_VERIFY_TOKEN = "my_chatbot_token"
FACEBOOK_APP_SECRET = "a8ca984de5becd8d9ee42b9a62843d18"