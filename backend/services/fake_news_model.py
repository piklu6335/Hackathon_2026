from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from transformers import AutoModel, BertTokenizerFast

# The hosted instance has one CPU core; avoid PyTorch oversubscribing it.
torch.set_num_threads(max(1, int(os.getenv("TORCH_NUM_THREADS", "2"))))


# ============================================================
# Configuration
# ============================================================

BASE_MODEL = "bert-base-uncased"

MAX_LENGTH = 15

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "c2_new_model_weights.pt"
)


# The WELFake dataset's published label convention is 0 = fake, 1 = real.
# Keep the class IDs, displayed labels, and probability fields aligned with it.
# (The training/preprocessing script is not in this repository, so verify this
# convention if the model checkpoint was trained with remapped labels.)

LABEL_MAP = {
    0: "FAKE",
    1: "REAL",
}


# Use GPU if available, otherwise CPU.
DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# Model Architecture
# ============================================================

class BERT_Arch(nn.Module):

    def __init__(self, bert):
        super(BERT_Arch, self).__init__()

        self.bert = bert

        self.dropout = nn.Dropout(0.1)

        self.relu = nn.ReLU()

        self.fc1 = nn.Linear(
            768,
            512
        )

        self.fc2 = nn.Linear(
            512,
            2
        )

        self.softmax = nn.LogSoftmax(
            dim=1
        )

    def forward(
        self,
        sent_id,
        mask
    ):

        cls_hs = self.bert(
            sent_id,
            attention_mask=mask
        )["pooler_output"]

        x = self.fc1(cls_hs)

        x = self.relu(x)

        x = self.dropout(x)

        x = self.fc2(x)

        x = self.softmax(x)

        return x


# ============================================================
# Load Tokenizer + Model
# ============================================================

print(
    f"[NewsCred] Loading tokenizer: {BASE_MODEL}"
)

tokenizer = BertTokenizerFast.from_pretrained(
    BASE_MODEL
)


print(
    f"[NewsCred] Loading BERT: {BASE_MODEL}"
)

bert = AutoModel.from_pretrained(
    BASE_MODEL
)


# Recreate your exact architecture.
model = BERT_Arch(
    bert
)


# ============================================================
# Load Trained Weights
# ============================================================

if not MODEL_PATH.exists():

    raise FileNotFoundError(
        f"Model weights not found at:\n{MODEL_PATH}"
    )


print(
    f"[NewsCred] Loading weights:\n{MODEL_PATH}"
)

state_dict = torch.load(
    MODEL_PATH,
    map_location=DEVICE
)

model.load_state_dict(
    state_dict
)


# Move model to device.
model.to(DEVICE)

# Disable training behavior.
model.eval()


print(
    f"[NewsCred] Model loaded on {DEVICE}"
)


# ============================================================
# Prediction
# ============================================================

def predict_fake_news(
    text: str
) -> dict[str, Any]:
    """
    Predict whether text is REAL or FAKE.

    IMPORTANT:
    The original model was trained on news HEADLINES
    (`data['title']`) with max sequence length 15.

    Therefore, this function treats the provided text
    primarily as headline-style input.
    """

    text = text.strip()

    if not text:

        raise ValueError(
            "Text cannot be empty."
        )

    # --------------------------------------------------------
    # Tokenize exactly as during training
    # --------------------------------------------------------

    tokens = tokenizer(
    [text],
    max_length=MAX_LENGTH,
    padding="max_length",
    truncation=True,
    return_tensors="pt",
)

    input_ids = tokens[
        "input_ids"
    ].to(DEVICE)

    attention_mask = tokens[
        "attention_mask"
    ].to(DEVICE)

    # --------------------------------------------------------
    # Inference
    # --------------------------------------------------------

    with torch.inference_mode():

        output = model(
            input_ids,
            attention_mask
        )

    # Model returns LogSoftmax.
    probabilities = torch.exp(
        output
    )

    probabilities = probabilities[
        0
    ].detach().cpu()

    predicted_class = int(
        torch.argmax(
            probabilities
        ).item()
    )

    fake_probability = float(
        probabilities[0].item()
    )

    real_probability = float(
        probabilities[1].item()
    )

    confidence = float(
        probabilities[
            predicted_class
        ].item()
    )

    label = LABEL_MAP[
        predicted_class
    ]

    return {
    "prediction": {
        "label": label,
        "class_id": predicted_class,
        "confidence": round(confidence, 4),
        "confidence_percent": round(
            confidence * 100,
            2
        ),
    },

    "probabilities": {
        "fake": round(
            fake_probability,
            4
        ),
        "fake_percent": round(
            fake_probability * 100,
            2
        ),
        "real": round(
            real_probability,
            4
        ),
        "real_percent": round(
            real_probability * 100,
            2
        ),
    },

    "input": {
        "text": text,
        "character_count": len(text),
        "word_count": len(text.split()),
        "token_limit": MAX_LENGTH,
    },

    "model": {
        "name": "NewsCred WELFake Classifier",
        "dataset": "WELFake",
        "architecture": "BERT + Custom Classification Head",
        "base_model": BASE_MODEL,
        "max_length": MAX_LENGTH,
        "device": str(DEVICE),
    },

    "status": "success",
}
