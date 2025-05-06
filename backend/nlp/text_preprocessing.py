import re
import unicodedata

ABBREVIATIONS = {
    "ko": "không",
    "k": "không",
    "hok": "không",
    "mk": "mình",
    "bt": "bình thường",
    "j": "gì",
    "z": "vậy",
    "vs": "với",
    "dc": "được",
    "ok": "okay",
    "oke": "okay",
    "chao": "chào",
    "hi": "chào",
    "hiii": "chào",
    "helo": "chào",
    "hello": "chào",
    "xin chao": "chào",
    "hey": "chào",
    "alo": "chào",
}


def clean_text(text, replace_abbreviations=True):
    text = text.lower()
    text = unicodedata.normalize("NFC", text)  # Chuẩn hóa trước
    if replace_abbreviations:
        for abbr, full in ABBREVIATIONS.items():
            text = re.sub(rf"\b{abbr}\b", full, text)
    text = re.sub(r"[^\w\s#0-9]", "", text)
    return text.strip()
