"""LLM-as-judge: a second, independent call that scores the output.

The judge sees the document and the produced JSON, never the summarizer's
prompt. It never raises: any failure comes back as an error string so the
main request still succeeds.
"""

from __future__ import annotations

import anthropic

from .config import Settings
from .prompts import JUDGE_SYSTEM, build_judge_user
from .schemas import Evaluation, JudgeOutput, SummaryOutput

JUDGE_MAX_TOKENS = 4096


def evaluate(
    text: str,
    output: SummaryOutput,
    *,
    settings: Settings,
    client: anthropic.Anthropic,
) -> tuple[Evaluation | None, str | None]:
    from .core import usage_from_response  # local import avoids a cycle

    try:
        response = client.messages.parse(
            model=settings.judge_model,
            max_tokens=JUDGE_MAX_TOKENS,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": build_judge_user(text, output)}],
            output_format=JudgeOutput,
            output_config={"effort": settings.judge_effort},
        )
        if response.stop_reason == "refusal":
            return None, "judge declined the request"
        judged: JudgeOutput | None = response.parsed_output
        if judged is None:
            return None, "judge returned no parsable output"
        return (
            Evaluation(
                **judged.model_dump(),
                model=settings.judge_model,
                usage=usage_from_response(response, settings.judge_model),
            ),
            None,
        )
    except Exception as e:  # noqa: BLE001 - the judge must never fail the request
        return None, f"{type(e).__name__}: {e}"
