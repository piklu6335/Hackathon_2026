from __future__ import annotations

from typing import Any

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
)


# ============================================================
# Configuration
# ============================================================

MODEL_ID = "caush/Clickbait4"

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# Load tokenizer
# ============================================================

print(
    f"[NewsCred] Loading Clickbait tokenizer: {MODEL_ID}"
)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID,
    use_fast=False,
)

print(
    "[NewsCred] Clickbait tokenizer loaded"
)


# ============================================================
# Load model
# ============================================================

print(
    f"[NewsCred] Loading Clickbait model: {MODEL_ID}"
)

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_ID
)

model.to(DEVICE)
model.eval()

print(
    f"[NewsCred] Clickbait model loaded on {DEVICE}"
)


# ============================================================
# Prediction
# ============================================================

def predict_clickbait(
    text: str,
) -> dict[str, Any]:

    text = text.strip()

    if not text:
        raise ValueError(
            "Text cannot be empty."
        )

    # --------------------------------------------------------
    # Tokenization
    # --------------------------------------------------------

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=128,
    )

    inputs = {
        key: value.to(DEVICE)
        for key, value in inputs.items()
    }

    # --------------------------------------------------------
    # Inference
    # --------------------------------------------------------

    with torch.no_grad():

        outputs = model(
            **inputs
        )

    # IMPORTANT:
    # Clickbait4 outputs ONE scalar regression value.
    score = float(
        outputs.logits
        .squeeze()
        .item()
    )

    # Keep raw model score.
    # The 0-100 value is only a UI representation.
    display_score = score * 100

    # --------------------------------------------------------
    # Display band
    # --------------------------------------------------------

    if score < 0.33:

        level = "LOW"

    elif score < 0.66:

        level = "MODERATE"

    elif score < 0.85:

        level = "HIGH"

    else:

        level = "VERY HIGH"

    return {

        "score": round(
            score,
            4,
        ),

        "score_percent": round(
            display_score,
            2,
        ),

        "level": level,

        "model": {
            "name": "Clickbait4",
            "base_model": MODEL_ID,
            "task": "clickbait intensity regression",
            "max_length": 128,
            "device": str(DEVICE),
        },

        "input": {
            "text": text,
            "word_count": len(
                text.split()
            ),
        },

        "status": "success",
    }