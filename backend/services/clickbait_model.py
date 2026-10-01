from __future__ import annotations

import re
from typing import Any

from services.cloudflare_ai import assess_news


ABSOLUTE_CLAIM = re.compile(
    r"\b(all|every|never|always|everyone|nobody|entire|completely)\b", re.I
)
SENSATIONAL_WORD = re.compile(
    r"\b(giant|shocking|secret|unbelievable|massive|stunning|jaw[- ]dropping|bombshell|miracle|instantly)\b",
    re.I,
)
CURIOSITY_PHRASE = re.compile(
    r"\b(you won't believe|what happens next|the truth about|here's why|this is what|must see)\b",
    re.I,
)
EXTREME_CLAIM = re.compile(
    r"\b(replace (every|all)|end .{1,30} forever|change everything|one weird trick)\b",
    re.I,
)


def format_clickbait_result(text: str, model_score: float) -> dict[str, Any]:
    text = text.strip()
    signals: list[str] = []
    heuristic_score = 0.0
    for pattern, points, label in (
        (ABSOLUTE_CLAIM, 0.20, "absolute wording"),
        (SENSATIONAL_WORD, 0.20, "sensational wording"),
        (CURIOSITY_PHRASE, 0.28, "curiosity hook"),
        (EXTREME_CLAIM, 0.22, "sweeping claim"),
    ):
        if pattern.search(text):
            heuristic_score += points
            signals.append(label)
    if "!" in text or "?" in text:
        heuristic_score += 0.08
        signals.append("emphatic punctuation")

    heuristic_score = min(1.0, heuristic_score)
    model_score = min(1.0, max(0.0, float(model_score)))
    score = min(1.0, 0.60 * model_score + 0.40 * heuristic_score)
    if score < 0.33:
        level = "LOW"
    elif score < 0.66:
        level = "MODERATE"
    elif score < 0.85:
        level = "HIGH"
    else:
        level = "VERY HIGH"

    return {
        "score": round(score, 4),
        "score_percent": round(score * 100, 2),
        "model_score_percent": round(model_score * 100, 2),
        "headline_signals": signals,
        "level": level,
        "model": {
            "name": "Cloudflare Workers AI + wording cues",
            "base_model": "@cf/meta/llama-3.2-1b-instruct",
            "task": "Uncalibrated clickbait-pattern estimate",
        },
        "input": {"text": text, "word_count": len(text.split())},
        "status": "success",
    }


def predict_clickbait(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Text cannot be empty.")
    assessment = assess_news(text[:800], text[:1200])
    return format_clickbait_result(text, assessment["clickbait_score"])
