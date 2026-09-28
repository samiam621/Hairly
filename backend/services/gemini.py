"""Gemini calls. Prompt text lives here and nowhere else."""

import base64

import httpx
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.errors import HairlyError


# ponytail: Flash-Lite for the free-tier quota; switch to gemini-3.8-flash if small print reads poorly
MODEL = "gemini-3.5-flash-lite"
GENERATE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
MAX_IMAGE_BYTES = settings.max_image_mb * 1024 * 1024

READ_LABEL_PROMPT = (
    "This is a photo of a hair product's packaging. Copy its ingredient list exactly as printed, in order, "
    "separated by commas. Do not add, guess, translate, or correct any ingredient. "
    "Set readable to false if there is no ingredient list, or if any part of it is blurry, cut off, or hidden "
    "by glare: a partial list could leave out the one ingredient the user has to avoid."
)
READ_LABEL_SCHEMA = {
    "type": "OBJECT",
    "properties": {"readable": {"type": "BOOLEAN"}, "ingredients": {"type": "STRING"}},
    "required": ["readable", "ingredients"],
}

# The key goes in a header, not the URL, so it never lands in a logged URL.
_client = httpx.Client(timeout=30.0, headers={"x-goog-api-key": settings.gemini_api_key})


class LabelRead(BaseModel):
    readable: bool
    ingredients: str


def image_type(image: bytes) -> str:
    """Reject a bad upload before it costs a Gemini call. Returns the MIME type, sniffed from the bytes."""
    if not image:
        raise HairlyError("INVALID_INPUT", "That photo is empty. Take it again.", 400)
    if len(image) > MAX_IMAGE_BYTES:
        raise HairlyError("INVALID_INPUT", f"That photo is too large. Keep it under {settings.max_image_mb} MB.", 413)
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    if image[4:12] in (b"ftypheic", b"ftypheix"):
        return "image/heic"
    raise HairlyError("INVALID_INPUT", "That file isn't a photo we can read. Use a JPEG, PNG, WebP, or HEIC image.", 415)


def read_label(image: bytes) -> str:
    """Photo of an ingredient label in, the ingredient list as printed out (raw text, for normalize())."""
    body = {
        "contents": [{"parts": [
            {"inlineData": {"mimeType": image_type(image), "data": base64.b64encode(image).decode()}},
            {"text": READ_LABEL_PROMPT},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": READ_LABEL_SCHEMA},
    }
    try:
        response = _client.post(GENERATE_URL, json=body)
        response.raise_for_status()
        # No text back means Gemini blocked the image: that's an unreadable photo, not an outage.
        candidates = response.json().get("candidates") or [{}]
        text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
        label = LabelRead.model_validate_json(text) if text else None
    except (httpx.HTTPError, ValueError) as exc:  # ValueError covers bad JSON and pydantic's ValidationError
        # ponytail: 429s and timeouts are AI_UNAVAILABLE until Phase 4's rate-limit item adds RATE_LIMITED
        raise HairlyError("AI_UNAVAILABLE", "We can't read labels right now. Try again in a minute.", 503) from exc

    if label is None or not label.readable or not label.ingredients.strip():
        raise HairlyError(
            "LABEL_UNREADABLE",
            "We couldn't read the whole ingredient list. Retake the photo close up, in good light, with the full list in frame.",
            422,
        )
    return label.ingredients
