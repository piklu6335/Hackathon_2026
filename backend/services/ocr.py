from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image
from rapidocr import RapidOCR


# Load the OCR engine once.
# Do NOT initialize this for every request.
ocr_engine = RapidOCR()


def extract_text_from_image(image_bytes: bytes) -> dict[str, Any]:
    """
    Extract text from an image using local RapidOCR.

    Returns:
        text:
            Combined OCR text.

        lines:
            Individual recognized lines and confidence.

        average_confidence:
            Mean OCR confidence.

        image:
            Basic image information.
    """

    # -----------------------------
    # Open image
    # -----------------------------

    try:
        image = Image.open(
            BytesIO(image_bytes)
        ).convert("RGB")
    except Exception as exc:
        raise ValueError(
            f"Invalid image: {exc}"
        ) from exc

    # -----------------------------
    # Convert PIL -> NumPy
    # -----------------------------

    image_array = np.array(image)

    # -----------------------------
    # Run RapidOCR
    # -----------------------------

    result = ocr_engine(image_array)

    texts = result.txts or ()
    scores = result.scores or ()

    lines = []

    for text, score in zip(texts, scores):

        text = str(text).strip()

        if not text:
            continue

        lines.append({
            "text": text,
            "confidence": round(
                float(score),
                4
            ),
        })

    # -----------------------------
    # Combine lines
    # -----------------------------

    combined_text = "\n".join(
        item["text"]
        for item in lines
    )

    # -----------------------------
    # Average confidence
    # -----------------------------

    if lines:
        average_confidence = (
            sum(
                item["confidence"]
                for item in lines
            )
            / len(lines)
        )
    else:
        average_confidence = 0.0

    # -----------------------------
    # Return structured result
    # -----------------------------

    return {
        "text": combined_text,
        "lines": lines,
        "average_confidence": round(
            average_confidence,
            4
        ),
        "image": {
            "width": image.width,
            "height": image.height,
        },
    }