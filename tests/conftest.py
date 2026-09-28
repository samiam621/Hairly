import httpx
import pytest

from backend.services import product_lookup


@pytest.fixture
def obf(monkeypatch):
    """Replace Open Beauty Facts with a handler: request in, httpx.Response out."""
    def use(handler) -> None:
        monkeypatch.setattr(product_lookup, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    return use
