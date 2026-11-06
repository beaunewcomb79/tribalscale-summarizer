"""Opt-in tests against the real API. Run with: uv run pytest -m live"""

import os
from pathlib import Path

import pytest

from summarizer.config import load_settings
from summarizer.core import summarize

pytestmark = pytest.mark.live

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture(autouse=True)
def _real_key():
    # conftest leaves the environment alone for live tests, so load_settings()
    # sees the exported key or the one in .env.
    if not load_settings().api_key:
        pytest.skip("ANTHROPIC_API_KEY not set (export it or put it in .env)")


def test_live_meeting_notes():
    r = summarize((EXAMPLES / "meeting_notes.txt").read_text(), settings=load_settings())
    assert 1 <= len(r.action_items) <= 3 and r.metadata.checks.summary_length_ok
    assert r.metadata.evaluation is not None and r.metadata.evaluation.faithfulness >= 3
    assert r.metadata.usage.estimated_cost_usd > 0


def test_live_thin_input_does_not_invent_three():
    r = summarize((EXAMPLES / "thin_input.txt").read_text(), settings=load_settings())
    assert len(r.action_items) < 3 or all(i.grounded for i in r.action_items)
