from __future__ import annotations

import gc
from io import BytesIO
from threading import Lock
from typing import Any
import os

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from rapidocr import RapidOCR


# Load the OCR engine once.
# Do NOT initialize this for every request.
ocr_engine = RapidOCR()
_easyocr_reader = None
_easyocr_language = None
_easyocr_lock = Lock()


def _run_easyocr(image: np.ndarray, languages: list[str]) -> list[dict[str, Any]]:
    """Run one EasyOCR language family at a time to limit resident memory."""
    import easyocr

    global _easyocr_reader, _easyocr_language
    language_key = "+".join(languages)
    with _easyocr_lock:
        if _easyocr_language != language_key:
            # Bengali and Hindi use different recognition networks. Drop the
            # previous one before loading another so both models don't stay in
            # memory on small Render instances.
            _easyocr_reader = None
            gc.collect()
            model_dir = os.getenv("EASYOCR_MODULE_PATH")
            reader_options = {"gpu": False, "verbose": False}
            if model_dir:
                reader_options["model_storage_directory"] = model_dir
            _easyocr_reader = easyocr.Reader(languages, **reader_options)
            _easyocr_language = language_key

        result = _easyocr_reader.readtext(
            image, detail=1, paragraph=False, batch_size=1
        )
    return [
        {"text": str(item[1]).strip(), "confidence": round(float(item[2]), 4)}
        for item in result
        if len(item) >= 3 and str(item[1]).strip()
    ]


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
        image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
    except Exception as exc:
        raise ValueError(
            f"Invalid image: {exc}"
        ) from exc

    if max(image.size) > 3200:
        scale_down = 3200 / max(image.size)
        image = image.resize(
            (round(image.width * scale_down), round(image.height * scale_down)),
            getattr(Image, "Resampling", Image).LANCZOS,
        )

    # OCR on the original can miss small print. Compare it with an upscaled,
    # contrast-enhanced pass and an inverted pass for text on dark backgrounds.
    scale = min(3.0, 2200 / max(image.size))
    if scale > 1.05:
        enhanced = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            getattr(Image, "Resampling", Image).LANCZOS,
        )
    else:
        enhanced = image.copy()

    gray = ImageOps.grayscale(enhanced)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.5)
    sharpened = gray.filter(
        ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=2)
    )
    gray = ImageEnhance.Sharpness(sharpened).enhance(1.2)
    thresholded = gray.point(lambda pixel: 255 if pixel >= 170 else 0)
    variants = [
        image,
        gray.convert("RGB"),
        ImageOps.invert(gray).convert("RGB"),
        thresholded.convert("RGB"),
    ]

    def parse_result(result: Any) -> list[dict[str, Any]]:
        lines = []
        for recognized, score in zip(result.txts or (), result.scores or ()):
            recognized = str(recognized).strip()
            if recognized:
                lines.append({"text": recognized, "confidence": round(float(score), 4)})
        return lines

    def quality(lines: list[dict[str, Any]]) -> float:
        if not lines:
            return 0.0
        text = " ".join(line["text"] for line in lines)
        average = sum(line["confidence"] for line in lines) / len(lines)
        visible = [char for char in text if not char.isspace()]
        if not visible:
            return 0.0
        alphanumeric_ratio = sum(char.isalnum() for char in visible) / len(visible)
        # Prefer readable, complete output when two OCR passes have similar
        # model confidence; symbol-heavy output is often OCR noise.
        coverage = min(1.0, len(text) / 50)
        return average * (0.85 + 0.15 * coverage) * (0.65 + 0.35 * alphanumeric_ratio)

    def contains_script(text: str, start: int, end: int) -> bool:
        return sum(start <= ord(char) <= end for char in text) >= 3

    candidate_lines = [parse_result(ocr_engine(np.array(variant))) for variant in variants]
    lines = max(candidate_lines, key=quality)
    selected_engine = "RapidOCR"

    # RapidOCR's bundled default recognizer is not specialized for Indic
    # scripts and can be confidently wrong when glyphs resemble Latin text.
    # EasyOCR's Bengali and Devanagari networks are incompatible, so try each
    # in turn and keep only one network resident in memory.
    enhanced_array = np.array(enhanced)
    has_bengali = False
    try:
        easy_lines = _run_easyocr(enhanced_array, ["bn", "en"])
        easy_text = " ".join(item["text"] for item in easy_lines)
        has_bengali = contains_script(easy_text, 0x0980, 0x09FF)
        if has_bengali or quality(easy_lines) > quality(lines):
            lines = easy_lines
            selected_engine = "EasyOCR (Bengali + English)"
    except Exception as exc:
        # A missing Bengali model should not prevent trying Hindi below.
        print(f"[NewsCred] Bengali EasyOCR unavailable: {exc}")

    # If Bengali text wasn't found, inspect with the compatible Hindi model.
    # Script evidence wins over confidence, which is not comparable between
    # OCR model families.
    if not has_bengali:
        try:
            hindi_lines = _run_easyocr(enhanced_array, ["hi", "en"])
            hindi_text = " ".join(item["text"] for item in hindi_lines)
            has_hindi = contains_script(hindi_text, 0x0900, 0x097F)
            if has_hindi or quality(hindi_lines) > quality(lines):
                lines = hindi_lines
                selected_engine = "EasyOCR (Hindi + English)"
        except Exception as exc:
            # Keep whichever local OCR result is available; don't fail analysis.
            print(f"[NewsCred] Hindi EasyOCR unavailable: {exc}")

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
        "engine": selected_engine,
        "average_confidence": round(
            average_confidence,
            4
        ),
        "image": {
            "width": image.width,
            "height": image.height,
        },
    }
