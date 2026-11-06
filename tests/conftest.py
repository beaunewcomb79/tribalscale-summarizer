import os
from types import SimpleNamespace

import pytest

# Captured before the autouse fixture below replaces it, so the opt-in live
# tests can still see a key that was exported in the shell.
REAL_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def _test_env(request, monkeypatch, tmp_path):
    if "live" in request.keywords:
        return
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("REQUEST_LOG_PATH", str(tmp_path / "requests.jsonl"))


def make_parsed(
    parsed_output,
    *,
    model="claude-opus-5-5",
    stop_reason="end_turn",
    input_tokens=100,
    output_tokens=50,
    thinking_tokens=None,
    category=None,
):
    """A SimpleNamespace shaped like anthropic.types.ParsedMessage."""
    details = SimpleNamespace(thinking_tokens=thinking_tokens) if thinking_tokens is not None else None
    return SimpleNamespace(
        parsed_output=parsed_output,
        model=model,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if stop_reason == "refusal" else None,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            output_tokens_details=details,
        ),
    )


class _FakeMessages:
    def __init__(self, responses, calls):
        self._responses = list(responses)
        self._calls = calls

    def parse(self, **kwargs):
        self._calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeClient ran out of scripted responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class FakeClient:
    """Stands in for anthropic.Anthropic: `.messages.parse(**kw)` pops scripted responses."""

    def __init__(self, responses):
        self.calls: list[dict] = []
        self.messages = _FakeMessages(responses, self.calls)
