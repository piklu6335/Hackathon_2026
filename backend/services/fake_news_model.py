from __future__ import annotations

from typing import Any

from services.cloudflare_ai import assess_news


def format_fake_news_result(text: str, label: str, confidence: float) -> dict[str, Any]:
    text = text.strip()
    class_id = 0 if label == "FAKE" else 1
    fake_probability = confidence if label == "FAKE" else 1 - confidence
    real_probability = 1 - fake_probability
    return {
        "prediction": {
            "label": label,
            "class_id": class_id,
            "confidence": round(confidence, 4),
            "confidence_percent": round(confidence * 100, 2),
        },
        "probabilities": {
            "fake": round(fake_probability, 4),
            "fake_percent": round(fake_probability * 100, 2),
            "real": round(real_probability, 4),
            "real_percent": round(real_probability * 100, 2),
        },
        "input": {
            "text": text,
            "character_count": len(text),
            "word_count": len(text.split()),
            "token_limit": 800,
        },
        "model": {
            "name": "Cloudflare Workers AI news-pattern estimate",
            "provider": "Cloudflare Workers AI",
            "base_model": "@cf/meta/llama-3.2-1b-instruct",
            "calibration": "Uncalibrated language-model estimate; not fact verification",
        },
        "status": "success",
    }


def predict_fake_news(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Text cannot be empty.")
    assessment = assess_news(text[:800], text[:3000])
    result = format_fake_news_result(
        text,
        assessment["label"],
        assessment["confidence"],
    )
    result["assessment_reason"] = assessment["reason"]
    return result
