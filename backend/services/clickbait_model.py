from __future__ import annotations

import os
import re
from typing import Any

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
)

# The hosted instance has one CPU core; avoid PyTorch oversubscribing it.
torch.set_num_threads(max(1, int(os.getenv("TORCH_NUM_THREADS", "2"))))


# ============================================================
# Configuration
# ============================================================

MODEL_ID = "caush/Clickbait4"

ABSOLUTE_CLAIM = re.compile(r"\b(all|every|never|always|everyone|nobody|entire|completely)\b", re.I)
SENSATIONAL_WORD = re.compile(
    r"\b(giant|shocking|secret|unbelievable|massive|stunning|jaw[- ]dropping|bombshell|miracle|instantly)\b",
    re.I,
)
CURIOSITY_PHRASE = re.compile(
    r"\b(you won't believe|what happens next|the truth about|here's why|this is what|must see)\b",
    re.I,
)
EXTREME_CLAIM = re.compile(r"\b(replace (every|all)|end .{1,30} forever|change everything|one weird trick)\b", re.I)

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

    with torch.inference_mode():

        outputs = model(
            **inputs
        )

    # Clickbait4 predicts clickbait strength as a regression value.
    model_score = float(
        outputs.logits
        .squeeze()
        .item()
    )
    model_score = min(1.0, max(0.0, model_score))

    # Add a lightweight, inspectable headline heuristic. The regression model
    # can miss exaggerated claims; explicit wording cues help catch these cases.
    signals: list[str] = []
    heuristic_score = 0.0
    if ABSOLUTE_CLAIM.search(text):
        heuristic_score += 0.20
        signals.append("absolute wording")
    if SENSATIONAL_WORD.search(text):
        heuristic_score += 0.20
        signals.append("sensational wording")
    if CURIOSITY_PHRASE.search(text):
        heuristic_score += 0.28
        signals.append("curiosity hook")
    if EXTREME_CLAIM.search(text):
        heuristic_score += 0.22
        signals.append("sweeping claim")
    if text.count("!") >= 1 or text.count("?") >= 1:
        heuristic_score += 0.08
        signals.append("emphatic punctuation")
    heuristic_score = min(1.0, heuristic_score)

    score = min(1.0, 0.60 * model_score + 0.40 * heuristic_score)
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

        "model_score_percent": round(model_score * 100, 2),
        "headline_signals": signals,

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
