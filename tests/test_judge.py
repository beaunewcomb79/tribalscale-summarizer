import anthropic
import httpx
from pydantic import ValidationError

from summarizer.config import load_settings
from summarizer.judge import evaluate
from summarizer.schemas import JudgeOutput, JudgeRationale

from .conftest import FakeClient, make_parsed
from .test_core import OUT, TEXT

S = load_settings(env={"REQUEST_LOG_PATH": ""})
JO = JudgeOutput(
    faithfulness=5, coverage=4, actionability=5,
    rationale=JudgeRationale(faithfulness="a", coverage="b", actionability="c"), unsupported_claims=[],
)


def test_judge_happy_path():
    client = FakeClient([make_parsed(JO, input_tokens=300, output_tokens=60)])
    ev, err = evaluate(TEXT, OUT, settings=S, client=client)
    assert err is None and ev.faithfulness == 5 and ev.model == "claude-opus-5-5"
    assert ev.usage.estimated_cost_usd == 0.0024
    call = client.calls[0]
    assert call["output_format"] is JudgeOutput and call["output_config"] == {"effort": "low"} and call["max_tokens"] == 4096


def test_judge_sdk_error_is_captured():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
    ev, msg = evaluate(TEXT, OUT, settings=S, client=FakeClient([err]))
    assert ev is None and "APIConnectionError" in msg


def test_judge_out_of_range_score_is_captured():
    client = FakeClient([])

    def boom(**kw):
        raise ValidationError.from_exception_data("JudgeOutput", [])

    client.messages.parse = boom
    ev, msg = evaluate(TEXT, OUT, settings=S, client=client)
    assert ev is None and "ValidationError" in msg


def test_judge_no_parsed_output_is_captured():
    ev, msg = evaluate(TEXT, OUT, settings=S, client=FakeClient([make_parsed(None)]))
    assert ev is None and "no parsable output" in msg
