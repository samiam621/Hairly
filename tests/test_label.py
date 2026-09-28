import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import gemini


client = TestClient(app)
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 16


@pytest.fixture
def ai(monkeypatch):
    """Replace Gemini with one canned response; returns the requests it received."""
    calls = []

    def use(response: httpx.Response) -> list[httpx.Request]:
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return response
        monkeypatch.setattr(gemini, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
        return calls
    return use


def label(readable: bool, ingredients: str) -> httpx.Response:
    text = json.dumps({"readable": readable, "ingredients": ingredients})
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def post(image: bytes = JPEG, concern: str = "dye allergy") -> httpx.Response:
    return client.post("/api/analyze/label", files={"image": ("label.jpg", image, "image/jpeg")}, data={"concern": concern})


def test_readable_label_returns_verdict(ai, unrecognized) -> None:
    calls = ai(label(True, "Aqua, Cetearyl Alcohol, p-Phenylenediamine"))
    response = post()

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "avoid"
    assert body["flagged_ingredients"][0]["name"] == "p-phenylenediamine"
    assert json.loads(calls[0].content)["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "image/jpeg"
    assert unrecognized  # the label path feeds the curation backlog too


@pytest.mark.parametrize(
    ("response", "status", "code"),
    [
        (label(False, "Aqua, Parfum"), 422, "LABEL_UNREADABLE"),  # partial list: never judged
        (label(True, "  "), 422, "LABEL_UNREADABLE"),
        (httpx.Response(200, json={"promptFeedback": {"blockReason": "OTHER"}}), 422, "LABEL_UNREADABLE"),
        (httpx.Response(500), 503, "AI_UNAVAILABLE"),
        (httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{not json"}]}}]}), 503, "AI_UNAVAILABLE"),
    ],
)
def test_gemini_cannot_read(ai, response: httpx.Response, status: int, code: str) -> None:
    ai(response)
    response = post()

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    ("image", "concern", "status"),
    [
        (b"", "dye allergy", 400),
        (JPEG + b"\0" * gemini.MAX_IMAGE_BYTES, "dye allergy", 413),
        (b"GIF89a" + b"\0" * 16, "dye allergy", 415),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "dye allergy", 415),
        (JPEG, "not a concern", 400),
    ],
)
def test_bad_input_never_reaches_gemini(ai, image: bytes, concern: str, status: int) -> None:
    calls = ai(label(True, "Aqua"))
    response = post(image, concern)

    assert response.status_code == status
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert calls == []
