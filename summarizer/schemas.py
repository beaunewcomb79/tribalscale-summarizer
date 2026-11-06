"""Pydantic models.

Two families live here:

* model-facing schemas (`SummaryOutput`, `JudgeOutput`) that are handed to
  the SDK as `output_format`; their field descriptions become part of the
  JSON schema the model sees, so they double as prompt guidance;
* response-facing models (`SummaryResponse` and the `Metadata` tree) that
  the API and CLI return.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Model-facing
# --------------------------------------------------------------------------- #


class ActionItem(BaseModel):
    text: str = Field(description="Imperative, verb-first, concrete enough to assign to a person.")
    owner: str | None = Field(description="Person or team named in the text as responsible, else null.")
    due: str | None = Field(description="Deadline exactly as stated in the text, else null.")
    priority: Literal["high", "medium", "low"] = Field(description="Relative importance within this text.")
    source_quote: str | None = Field(
        description="Short verbatim span from the text that supports this item, else null."
    )
    grounded: bool = Field(
        description="true if the text states this action explicitly; false if it is inferred."
    )


class SummaryOutput(BaseModel):
    summary: str = Field(description="2-4 plain sentences. No facts that are not in the text.")
    action_items: list[ActionItem] = Field(
        max_length=3,
        description="Up to three action items, most important first. Fewer is better than invented.",
    )


class JudgeRationale(BaseModel):
    faithfulness: str = Field(description="One sentence justifying the faithfulness score.")
    coverage: str = Field(description="One sentence justifying the coverage score.")
    actionability: str = Field(description="One sentence justifying the actionability score.")


class JudgeOutput(BaseModel):
    faithfulness: int = Field(ge=1, le=5, description="5 = every claim is supported by the document.")
    coverage: int = Field(ge=1, le=5, description="5 = nothing important from the document is missing.")
    actionability: int = Field(ge=1, le=5, description="5 = items are concrete, verb-first and assignable.")
    rationale: JudgeRationale
    unsupported_claims: list[str] = Field(
        description="Claims in the summary or action items not found in the document. Empty if none."
    )


# --------------------------------------------------------------------------- #
# Response-facing
# --------------------------------------------------------------------------- #


class TimingMs(BaseModel):
    total: int
    summarize: int
    judge: int | None


class UsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    thinking_tokens: int | None
    estimated_cost_usd: float | None


class InputStats(BaseModel):
    chars: int
    words: int
    sentences: int
    est_tokens: int


class OutputStats(BaseModel):
    summary_words: int
    compression_ratio: float
    action_item_count: int


class Checks(BaseModel):
    action_item_count_ok: bool
    summary_length_ok: bool
    summary_shorter_than_input: bool
    items_verb_first: bool
    quotes_found_in_source: str
    novel_numbers_in_summary: list[str]


class Evaluation(JudgeOutput):
    model: str
    usage: UsageInfo


class Metadata(BaseModel):
    request_id: str
    model: str
    prompt_version: str
    stop_reason: str | None
    app_retries: int
    timing_ms: TimingMs
    usage: UsageInfo
    total_cost_usd: float | None
    input_stats: InputStats
    output_stats: OutputStats
    checks: Checks
    evaluation: Evaluation | None
    evaluation_error: str | None


class SummaryResponse(BaseModel):
    summary: str
    action_items: list[ActionItem]
    metadata: Metadata


class SummarizeRequest(BaseModel):
    text: str
    include_evaluation: bool = True
