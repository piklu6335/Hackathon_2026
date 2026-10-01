from __future__ import annotations

from typing import Any

from services.cloudflare_ai import extract_image_text


def extract_text_from_image(image_bytes: bytes) -> dict[str, Any]:
    """Extract image text with hosted Cloudflare Vision inference.

    Workers AI does not return per-word OCR probabilities. `average_confidence`
    is therefore `None`; callers should ask the user to review the transcription.
    """
    if not image_bytes:
        raise ValueError("Image is empty.")
    text, width, height = extract_image_text(image_bytes)
    lines = [
        {"text": line.strip(), "confidence": None}
        for line in text.splitlines()
        if line.strip()
    ]
    return {
        "text": "\n".join(line["text"] for line in lines),
        "lines": lines,
        "engine": "Cloudflare Vision (hosted OCR)",
        "average_confidence": None,
        "image": {"width": width, "height": height},
    }
