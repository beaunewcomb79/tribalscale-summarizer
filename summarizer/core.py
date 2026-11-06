"""The product: `summarize(text) -> SummaryResponse`.

One structured-output call to Claude, cheap local checks, an optional
second call to a judge model, and a metadata block that makes the whole
thing observable. The HTTP and CLI layers are thin wrappers around this.
"""

from __future__ import annotations

import time
import uuid

import anthropic
from pydantic import ValidationError

from .checks import input_stats, output_stats, run_checks
from .config import Settings, estimate_cost_usd, get_client, load_settings
from .errors import EmptyInputError, InputTooLargeError, RateLimitedError, RefusedError, UpstreamError
from .judge import evaluate
from .reqlog import append_request_log
from .prompts import PROMPT_VERSION, SUMMARIZER_SYSTEM, build_summarizer_user
from .schemas import Metadata, SummaryOutput, SummaryResponse, TimingMs, UsageInfo

# Thinking tokens count against max_tokens on this model family, so leave room.
SUMMARIZER_MAX_TOKENS = 16000


def usage_from_response(response, model: str) -> UsageInfo:
    """Lift `response.usage` into our UsageInfo with an estimated cost."""
    u = response.usage
    details = getattr(u, "output_tokens_details", None)
    thinking = getattr(details, "thinking_tokens", None) if details is not None else None
    return UsageInfo(
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        thinking_tokens=thinking,
        estimated_cost_usd=estimate_cost_usd(model, u.input_tokens, u.output_tokens),
    )


def _call_summarizer(client, settings: Settings, text: str) -> tuple[SummaryOutput, UsageInfo, str | None, int]:
    """Returns (output, usage, stop_reason, app_retries). Raises SummarizerError subclasses."""
    retries = 0
    while True:
        try:
            response = client.messages.parse(
                model=settings.model,
                max_tokens=SUMMARIZER_MAX_TOKENS,
                system=SUMMARIZER_SYSTEM,
                messages=[{"role": "user", "content": build_summarizer_user(text)}],
                output_format=SummaryOutput,
                output_config={"effort": settings.effort},
            )
        except anthropic.RateLimitError as e:
            raise RateLimitedError(str(e)) from e
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            raise UpstreamError(f"{type(e).__name__}: {e}") from e
        except ValidationError as e:
            # The SDK raises when the model's JSON does not match the schema
            # (including truncated JSON at max_tokens). Retry once, then give up.
            if retries >= 1:
                raise UpstreamError("model returned no parsable output") from e
            retries += 1
            continue

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise RefusedError(f"model declined the request (category={category})", category=category)
        if response.stop_reason == "max_tokens":
            raise UpstreamError("response truncated at max_tokens")

        output = response.parsed_output
        if output is not None:
            return output, usage_from_response(response, settings.model), response.stop_reason, retries
        if retries >= 1:
            raise UpstreamError("model returned no parsable output")
        retries += 1


def summarize(
    text: str,
    *,
    include_evaluation: bool = True,
    settings: Settings | None = None,
    client: anthropic.Anthropic | None = None,
) -> SummaryResponse:
    settings = settings or load_settings()
    if not text or not text.strip():
        raise EmptyInputError("text is empty")
    if len(text) > settings.max_input_chars:
        raise InputTooLargeError(f"text is {len(text)} chars; limit is {settings.max_input_chars}")
    client = client or get_client(settings)

    t0 = time.perf_counter()
    output, usage, stop_reason, app_retries = _call_summarizer(client, settings, text)
    t_summarize = time.perf_counter()

    evaluation = None
    evaluation_error = None
    judge_ms: int | None = None
    if include_evaluation and settings.judge_enabled:
        evaluation, evaluation_error = evaluate(text, output, settings=settings, client=client)
        judge_ms = int((time.perf_counter() - t_summarize) * 1000)

    total_ms = int((time.perf_counter() - t0) * 1000)
    judge_cost = evaluation.usage.estimated_cost_usd if evaluation else None
    total_cost = None
    if usage.estimated_cost_usd is not None:
        total_cost = round(usage.estimated_cost_usd + (judge_cost or 0.0), 6)
    metadata = Metadata(
        request_id=str(uuid.uuid4()),
        model=settings.model,
        prompt_version=PROMPT_VERSION,
        stop_reason=stop_reason,
        app_retries=app_retries,
        timing_ms=TimingMs(total=total_ms, summarize=int((t_summarize - t0) * 1000), judge=judge_ms),
        usage=usage,
        total_cost_usd=total_cost,
        input_stats=input_stats(text),
        output_stats=output_stats(text, output),
        checks=run_checks(text, output),
        evaluation=evaluation,
        evaluation_error=evaluation_error,
    )
    result = SummaryResponse(summary=output.summary, action_items=output.action_items, metadata=metadata)
    append_request_log(settings.request_log_path, result, text)
    return result
