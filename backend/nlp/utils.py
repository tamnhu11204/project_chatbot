import re
import json
import os
import logging
from transformers import AutoTokenizer
try:
    from backend.config.settings import  INTENTS_PATH
except ImportError:
    from config.settings import  INTENTS_PATH

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_text(text):
    """Clean input text for processing while preserving proper nouns."""
    try:
        # Chỉ loại bỏ ký tự đặc biệt, giữ khoảng trắng và chữ hoa
        text = re.sub(r'[^\w\s]', '', text).strip()
        return text
    except Exception as e:
        logger.error(f"Error cleaning text: {e}")
        return text

def is_valid_sentence(text):
    """Check if the input text is a valid sentence."""
    try:
        cleaned_text = clean_text(text)
        if not cleaned_text or len(cleaned_text.split()) < 1:
            return False
        return True
    except Exception as e:
        logger.error(f"Error validating sentence: {e}")
        return False

def suggest_intent(text, threshold=0.6):
    """Suggest intent based on pattern matching."""
    try:
        cleaned_text = clean_text(text)
        with open(INTENTS_PATH, 'r', encoding='utf-8-sig') as f:
            intents = json.load(f)
        
        best_match = None
        best_score = 0.0
        
        for intent in intents['intents']:
            for pattern in intent['patterns']:
                pattern_cleaned = clean_text(pattern)
                common_words = set(cleaned_text.lower().split()) & set(pattern_cleaned.lower().split())
                score = len(common_words) / max(len(pattern_cleaned.split()), 1)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = intent['tag']
        
        logger.info(f"Suggested intent for '{cleaned_text}': {best_match}, Score: {best_score}")
        return best_match
    except Exception as e:
        logger.error(f"Error in suggest_intent: {e}")
        return None

# Load PhoBERT tokenizer
try:
    tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
    logger.info("Loaded PhoBERT tokenizer")
except Exception as e:
    logger.error(f"Error loading PhoBERT: {e}")