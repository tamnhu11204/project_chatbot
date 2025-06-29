import os
import json
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from torch.optim.lr_scheduler import LambdaLR
import joblib
from backend.nlp.intent_model import IntentModel
from backend.config.settings import INTENTS_PATH, LABEL_ENCODER_PATH, MODEL_PATH
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=64):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        encoding = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": torch.tensor(label, dtype=torch.long),
        }

def load_intents():
    """Load intents from a single JSON file."""
    intents = []
    logger.info(f"Checking INTENTS_PATH: {INTENTS_PATH}")
    if os.path.exists(INTENTS_PATH):
        try:
            with open(INTENTS_PATH, "r", encoding="utf-8-sig") as f:
                intents.extend(json.load(f)["intents"])
            logger.info(f"Loaded {len(intents)} intents from intents.json")
        except Exception as e:
            raise Exception(f"Failed to load intents.json: {str(e)}")
    else:
        raise FileNotFoundError(f"intents.json not found at {INTENTS_PATH}")

    texts, labels = [], []
    for intent in intents:
        tag = intent.get("tag")
        if not tag:
            logger.warning(f"Intent missing tag: {intent}")
            continue
        for pattern in intent.get("patterns", []):
            if pattern.strip():
                texts.append(pattern)
                labels.append(tag)
    logger.info(f"Loaded {len(texts)} patterns and {len(labels)} labels")
    return texts, labels

def train_intent_model(intents_path=INTENTS_PATH, model_dir=None):
    """Train intent model and save artifacts."""
    try:
        tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
        texts, labels = load_intents()
        
        if not texts or not labels:
            raise ValueError("No valid patterns or labels found")
        
        # Create LabelEncoder
        label_encoder = LabelEncoder()
        encoded_labels = label_encoder.fit_transform(labels)
        
        if len(label_encoder.classes_) == 0:
            raise ValueError("label_encoder is empty")
        logger.info(f"label_encoder classes: {label_encoder.classes_}")
        
        if len(texts) != len(encoded_labels):
            raise ValueError(f"Mismatch between texts ({len(texts)}) and labels ({len(encoded_labels)})")
        
        if model_dir is None:
            model_dir = os.path.dirname(MODEL_PATH)
        os.makedirs(model_dir, exist_ok=True)
        
        # Save LabelEncoder
        os.makedirs(os.path.dirname(LABEL_ENCODER_PATH), exist_ok=True)
        joblib.dump(label_encoder, LABEL_ENCODER_PATH)
        logger.info(f"Saved label_encoder to {LABEL_ENCODER_PATH}")

        train_texts, val_texts, train_labels, val_labels = train_test_split(
            texts, encoded_labels, test_size=0.2, random_state=42
        )

        train_dataset = IntentDataset(train_texts, train_labels, tokenizer)
        val_dataset = IntentDataset(val_texts, val_labels, tokenizer)
        train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=8)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = IntentModel(num_classes=len(label_encoder.classes_)).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=5e-5)
        criterion = torch.nn.CrossEntropyLoss()

        def lr_lambda(step):
            warmup_steps = 50
            if step < warmup_steps:
                return float(step) / float(max(1, warmup_steps))
            return 1.0

        scheduler = LambdaLR(optimizer, lr_lambda)
        best_val_acc = 0.0
        patience = 20
        patience_counter = 0
        num_epochs = 100

        for epoch in range(num_epochs):
            model.train()
            total_loss = 0
            for batch in train_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)

                optimizer.zero_grad()
                outputs = model(input_ids, attention_mask)
                loss = criterion(outputs, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                total_loss += loss.item()

            model.eval()
            val_loss = 0
            correct = 0
            total = 0
            with torch.no_grad():
                for batch in val_loader:
                    input_ids = batch["input_ids"].to(device)
                    attention_mask = batch["attention_mask"].to(device)
                    labels = batch["labels"].to(device)

                    outputs = model(input_ids, attention_mask)
                    loss = criterion(outputs, labels)
                    val_loss += loss.item()

                    _, predicted = torch.max(outputs, 1)
                    total += labels.size(0)
                    correct += (predicted == labels).sum().item()

            val_acc = correct / total
            val_loss /= len(val_loader)
            logger.info(f"Epoch {epoch + 1} | Train Loss: {total_loss / len(train_loader):.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save(model.state_dict(), MODEL_PATH)
                tokenizer.save_pretrained(model_dir)
                logger.info(f"Saved model and tokenizer to {MODEL_PATH}")
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                logger.info(f"Early stopping at epoch {epoch + 1}")
                break

        logger.info(f"Training completed! Model saved at {MODEL_PATH}")
        return model, tokenizer
    except Exception as e:
        logger.error(f"Training failed: {str(e)}")
        raise

if __name__ == "__main__":
    train_intent_model()