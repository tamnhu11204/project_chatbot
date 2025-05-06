import torch
import torch.nn as nn
from transformers import AutoModel


class IntentModel(nn.Module):
    def __init__(self, num_classes, dropout=0.3):
        super(IntentModel, self).__init__()
        self.bert = AutoModel.from_pretrained("vinai/phobert-base")
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(self.bert.config.hidden_size, num_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs[1]
        pooled_output = self.dropout(pooled_output)
        logits = self.fc(pooled_output)
        return logits
