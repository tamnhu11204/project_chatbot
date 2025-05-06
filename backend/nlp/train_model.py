import os
import sys
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer
import numpy as np
import json
from torch.optim.lr_scheduler import LambdaLR

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.nlp.intent_model import IntentModel
from backend.config.settings import MODEL_PATH, LABEL_ENCODER_PATH, INTENTS_PATH
from sklearn.model_selection import train_test_split


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
    with open(INTENTS_PATH, "r", encoding="utf-8") as f:
        intents = json.load(f)["intents"]
    texts, labels = [], []
    label_map = {intent["tag"]: idx for idx, intent in enumerate(intents)}
    for intent in intents:
        for pattern in intent["patterns"]:
            texts.append(pattern)
            labels.append(label_map[intent["tag"]])
    return texts, labels, label_map


def train_and_save_model():
    tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
    texts, labels, label_map = load_intents()
    label_encoder = list(label_map.keys())
    np.save(LABEL_ENCODER_PATH, label_encoder)

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42
    )

    train_dataset = IntentDataset(train_texts, train_labels, tokenizer)
    val_dataset = IntentDataset(val_texts, val_labels, tokenizer)
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = IntentModel(num_classes=len(label_encoder), dropout=0.3).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=5e-6, weight_decay=1e-3)
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
                val_loss += criterion(outputs, labels).item()
                _, predicted = torch.max(outputs, dim=1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        val_acc = correct / total
        print(
            f"Epoch {epoch+1} | Train Loss: {total_loss/len(train_loader):.4f} | "
            f"Val Loss: {val_loss/len(val_loader):.4f} | Val Acc: {val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_PATH)
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print("Early stopping triggered.")
                break

    print("✅ Huấn luyện thành công! Model đã được lưu.")


if __name__ == "__main__":
    train_and_save_model()
