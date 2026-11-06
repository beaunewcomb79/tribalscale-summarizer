from fastapi.testclient import TestClient

from summarizer import api
from summarizer.errors import EmptyInputError, InputTooLargeError, RateLimitedError, RefusedError, UpstreamError

from .test_core import OUT, S, TEXT, make_parsed, FakeClient
from summarizer.core import summarize as real_summarize

client = TestClient(api.app)
RESPONSE = real_summarize(TEXT, settings=S, client=FakeClient([make_parsed(OUT)]))


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_summarize_200(monkeypatch):
    monkeypatch.setattr(api, "summarize", lambda text, include_evaluation=True: RESPONSE)
    r = client.post("/summarize", json={"text": "hello", "include_evaluation": False})
    assert r.status_code == 200 and r.json()["metadata"]["prompt_version"] == RESPONSE.metadata.prompt_version


def test_missing_text_is_422():
    assert client.post("/summarize", json={}).status_code == 422


def test_summarizer_errors_map_to_status(monkeypatch):
    cases = [
        (EmptyInputError("empty"), 422),
        (InputTooLargeError("big"), 413),
        (RefusedError("refused", category="cyber"), 422),
        (RateLimitedError("rl"), 429),
        (UpstreamError("up"), 502),
    ]
    for exc, code in cases:
        def raiser(*a, _e=exc, **k):
            raise _e
        monkeypatch.setattr(api, "summarize", raiser)
        r = client.post("/summarize", json={"text": "x"})
        assert (r.status_code, "detail" in r.json()) == (code, True), exc
