from dataclasses import replace

import anthropic
import httpx
import pytest

from summarizer.config import load_settings
from summarizer.core import summarize
from summarizer.prompts import PROMPT_VERSION
from summarizer.errors import EmptyInputError, InputTooLargeError, RateLimitedError, RefusedError, UpstreamError
from summarizer.schemas import ActionItem, SummaryOutput

from .conftest import FakeClient, make_parsed

TEXT = (
    "Project sync, Tuesday. Dana will send the revised SOW to the client by Friday. "
    "Marcus agreed to schedule the security review for next sprint. "
    "Everyone should update their tickets before the Thursday standup. "
    "Budget remains at 40k for Q4 and the launch date is still November 20."
)
OUT = SummaryOutput(
    summary=(
        "The team met on Tuesday to review project status and commitments. Dana owns the revised SOW, "
        "Marcus owns the security review, and tickets need updating before Thursday. Budget and launch date are unchanged."
    ),
    action_items=[
        ActionItem(text="Send the revised SOW to the client by Friday", owner="Dana", due="Friday", priority="high",
                   source_quote="Dana will send the revised SOW to the client by Friday", grounded=True),
        ActionItem(text="Schedule the security review for next sprint", owner="Marcus", due="next sprint", priority="medium",
                   source_quote="schedule the security review for next sprint", grounded=True),
        ActionItem(text="Update tickets before the Thursday standup", owner=None, due="Thursday", priority="low",
                   source_quote="update their tickets before the Thursday standup", grounded=True),
    ],
)
NO_LOG = {"REQUEST_LOG_PATH": ""}
S = load_settings(env={**NO_LOG, "JUDGE_ENABLED": "false"})


def test_happy_path_assembles_response():
    client = FakeClient([make_parsed(OUT, input_tokens=1000, output_tokens=200, thinking_tokens=50)])
    r = summarize(TEXT, settings=S, client=client)
    assert r.summary == OUT.summary and len(r.action_items) == 3
    m = r.metadata
    assert m.model == "claude-opus-5-5" and m.prompt_version == PROMPT_VERSION and m.stop_reason == "end_turn"
    assert m.usage.input_tokens == 1000 and m.usage.thinking_tokens == 50
    assert m.usage.estimated_cost_usd == pytest.approx(0.008)
    assert m.checks.action_item_count_ok and m.checks.quotes_found_in_source == "3/3"
    assert m.evaluation is None and m.timing_ms.judge is None
    call = client.calls[0]
    assert call["output_format"] is SummaryOutput and call["output_config"] == {"effort": "medium"} and call["max_tokens"] == 16000
    assert "thinking" not in call and "temperature" not in call


def test_unicode_whitespace_is_empty():
    client = FakeClient([])
    with pytest.raises(EmptyInputError):
        summarize("  \n", settings=S, client=client)
    assert client.calls == []


def test_input_cap_boundary():
    s = replace(S, max_input_chars=10)
    assert summarize("x" * 10, settings=s, client=FakeClient([make_parsed(OUT)])).summary
    with pytest.raises(InputTooLargeError):
        summarize("x" * 11, settings=s, client=FakeClient([]))


def test_refusal_maps_to_refused_error():
    with pytest.raises(RefusedError) as ei:
        summarize(TEXT, settings=S, client=FakeClient([make_parsed(None, stop_reason="refusal", category="cyber")]))
    assert ei.value.category == "cyber"


def test_no_parsed_output_retries_once_then_fails():
    client = FakeClient([make_parsed(None), make_parsed(None)])
    with pytest.raises(UpstreamError):
        summarize(TEXT, settings=S, client=client)
    assert len(client.calls) == 2


def test_retry_success_sets_app_retries():
    r = summarize(TEXT, settings=S, client=FakeClient([make_parsed(None), make_parsed(OUT)]))
    assert r.metadata.app_retries == 1


def test_rate_limit_maps():
    err = anthropic.RateLimitError(
        message="slow down", response=httpx.Response(429, request=httpx.Request("POST", "http://x")), body=None
    )
    with pytest.raises(RateLimitedError):
        summarize(TEXT, settings=S, client=FakeClient([err]))


def test_connection_error_maps_to_upstream():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
    with pytest.raises(UpstreamError):
        summarize(TEXT, settings=S, client=FakeClient([err]))


def test_judge_wired_into_metadata():
    from .test_judge import JO

    s = load_settings(env={**NO_LOG, "JUDGE_ENABLED": "true"})
    r = summarize(TEXT, settings=s, client=FakeClient([make_parsed(OUT), make_parsed(JO)]))
    assert r.metadata.evaluation.coverage == 4 and r.metadata.timing_ms.judge is not None


def test_include_evaluation_false_skips_judge():
    client = FakeClient([make_parsed(OUT)])
    r = summarize(TEXT, include_evaluation=False, settings=load_settings(env=NO_LOG), client=client)
    assert len(client.calls) == 1 and r.metadata.evaluation is None


def test_judge_failure_does_not_fail_request():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
    r = summarize(TEXT, settings=load_settings(env=NO_LOG), client=FakeClient([make_parsed(OUT), err]))
    assert r.metadata.evaluation is None and "APIConnectionError" in r.metadata.evaluation_error


def _validation_error():
    from pydantic import ValidationError

    return ValidationError.from_exception_data("SummaryOutput", [])


def test_validation_error_retries_once_then_fails():
    client = FakeClient([_validation_error(), _validation_error()])
    with pytest.raises(UpstreamError, match="parsable"):
        summarize(TEXT, settings=S, client=client)
    assert len(client.calls) == 2


def test_validation_error_then_success_sets_app_retries():
    r = summarize(TEXT, settings=S, client=FakeClient([_validation_error(), make_parsed(OUT)]))
    assert r.metadata.app_retries == 1


def test_total_cost_sums_summarizer_and_judge():
    from .test_judge import JO

    s = load_settings(env={**NO_LOG, "JUDGE_ENABLED": "true"})
    client = FakeClient([make_parsed(OUT, input_tokens=1000, output_tokens=200), make_parsed(JO, input_tokens=300, output_tokens=60)])
    r = summarize(TEXT, settings=s, client=client)
    assert r.metadata.total_cost_usd == pytest.approx(0.0104)


def test_total_cost_without_judge_is_summarizer_cost():
    r = summarize(TEXT, settings=S, client=FakeClient([make_parsed(OUT, input_tokens=1000, output_tokens=200)]))
    assert r.metadata.total_cost_usd == pytest.approx(0.008)
