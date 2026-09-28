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


def post(images: tuple[bytes, ...] = (JPEG,), concern: str = "dye allergy") -> httpx.Response:
    files = [("image", (f"label-{i}.jpg", image, "image/jpeg")) for i, image in enumerate(images)]
    return client.post("/api/analyze/label", files=files, data={"concern": concern})


def test_readable_label_returns_verdict(ai, unrecognized) -> None:
    calls = ai(label(True, "Aqua, Cetearyl Alcohol, p-Phenylenediamine"))
    response = post()

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "avoid"
    assert body["flagged_ingredients"][0]["name"] == "p-phenylenediamine"
    assert json.loads(calls[0].content)["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "image/jpeg"
    assert unrecognized  # the label path feeds the curation backlog too


def test_several_angles_go_to_gemini_in_one_call(ai) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
    calls = ai(label(True, "Aqua, Resorcinol"))
    response = post((JPEG, png, JPEG))

    assert response.json()["verdict"] == "caution"
    assert len(calls) == 1
    parts = json.loads(calls[0].content)["contents"][0]["parts"]
    assert [p["inlineData"]["mimeType"] for p in parts[:-1]] == ["image/jpeg", "image/png", "image/jpeg"]
    assert "several angles" in parts[-1]["text"]  # the prompt comes after every photo


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


HALF = JPEG + b"\0" * (gemini.MAX_IMAGE_BYTES // 2)


@pytest.mark.parametrize(
    ("images", "concern", "status"),
    [
        ((b"",), "dye allergy", 400),
        ((JPEG, b""), "dye allergy", 400),  # one bad photo among good ones
        ((JPEG + b"\0" * gemini.MAX_IMAGE_BYTES,), "dye allergy", 413),
        ((HALF, HALF), "dye allergy", 413),  # each fits, together they don't
        ((JPEG,) * (gemini.MAX_PHOTOS + 1), "dye allergy", 400),
        ((b"GIF89a" + b"\0" * 16,), "dye allergy", 415),
        ((b"<svg xmlns='http://www.w3.org/2000/svg'/>",), "dye allergy", 415),
        ((JPEG,), "not a concern", 400),
    ],
)
def test_bad_input_never_reaches_gemini(ai, images: tuple[bytes, ...], concern: str, status: int) -> None:
    calls = ai(label(True, "Aqua"))
    response = post(images, concern)

    assert response.status_code == status
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert calls == []
