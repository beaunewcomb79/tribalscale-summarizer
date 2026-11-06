import pytest
from pydantic import ValidationError

from summarizer.schemas import ActionItem, JudgeOutput, SummaryOutput


def test_summary_output_rejects_four_items():
    item = dict(text="Do x", owner=None, due=None, priority="low", source_quote=None, grounded=False)
    with pytest.raises(ValidationError):
        SummaryOutput(summary="s", action_items=[item] * 4)


def test_summary_output_allows_zero_items():
    assert SummaryOutput(summary="s", action_items=[]).action_items == []


def test_judge_output_rejects_score_out_of_range():
    with pytest.raises(ValidationError):
        JudgeOutput(
            faithfulness=7, coverage=5, actionability=5,
            rationale=dict(faithfulness="", coverage="", actionability=""), unsupported_claims=[],
        )


def test_priority_enum():
    with pytest.raises(ValidationError):
        ActionItem(text="t", owner=None, due=None, priority="urgent", source_quote=None, grounded=True)
