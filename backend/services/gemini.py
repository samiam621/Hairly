"""Gemini calls. Prompt text lives here and nowhere else."""

import base64

import httpx
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.errors import HairlyError


# ponytail: Flash-Lite for the free-tier quota; switch to gemini-3.8-flash if small print reads poorly
MODEL = "gemini-3.5-flash-lite"
GENERATE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
MAX_IMAGE_BYTES = settings.max_image_mb * 1024 * 1024  # all photos together; Gemini caps a request at 20 MB
MAX_PHOTOS = 10  # plenty of angles for one bottle; also bounds the cost of a single Gemini call

READ_LABEL_PROMPT = (
    "These photos show one hair product's packaging, possibly from several angles. Copy its ingredient list "
    "exactly as printed, in order, separated by commas, as one list: where photos overlap, include each "
    "ingredient once. Do not add, guess, translate, or correct any ingredient. "
    "Set readable to false if there is no ingredient list, or if any part of it is blurry, cut off, or hidden "
    "by glare in every photo: a partial list could leave out the one ingredient the user has to avoid."
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


def check_photos(images: list[bytes]) -> list[str]:
    """Reject a bad upload before it costs a Gemini call. Returns each photo's MIME type."""
    if len(images) > MAX_PHOTOS:
        raise HairlyError("INVALID_INPUT", f"That's too many photos. Use up to {MAX_PHOTOS}.", 400)
    if sum(map(len, images)) > MAX_IMAGE_BYTES:
        raise HairlyError("INVALID_INPUT", f"Those photos are too large. Keep them under {settings.max_image_mb} MB in total.", 413)
    return [image_type(image) for image in images]


def image_type(image: bytes) -> str:
    """The photo's MIME type, sniffed from its bytes (the upload's own Content-Type can't be trusted)."""
    if not image:
        raise HairlyError("INVALID_INPUT", "That photo is empty. Take it again.", 400)
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    if image[4:12] in (b"ftypheic", b"ftypheix"):
        return "image/heic"
    raise HairlyError("INVALID_INPUT", "That file isn't a photo we can read. Use a JPEG, PNG, WebP, or HEIC image.", 415)


def read_label(images: list[bytes]) -> str:
    """Photos of an ingredient label in, the ingredient list as printed out (raw text, for normalize())."""
    photos = [
        {"inlineData": {"mimeType": mime, "data": base64.b64encode(image).decode()}}
        for image, mime in zip(images, check_photos(images))
    ]
    body = {
        "contents": [{"parts": [*photos, {"text": READ_LABEL_PROMPT}]}],  # one call sees every angle at once
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
            "We couldn't read the whole ingredient list. Take more photos close up, in good light, until every part of the list is clear.",
            422,
        )
    return label.ingredients
