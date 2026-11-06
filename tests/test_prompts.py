import re

from summarizer.prompts import PROMPT_VERSION, build_judge_user, build_summarizer_user
from summarizer.schemas import SummaryOutput


def test_summarizer_user_wraps_document_and_instruction_last():
    msg = build_summarizer_user("hello world")
    assert msg.index("<document>") < msg.index("hello world") < msg.index("</document>") < msg.rindex("action items")


def test_judge_user_contains_output_json():
    msg = build_judge_user("src", SummaryOutput(summary="s", action_items=[]))
    assert '"summary": "s"' in msg and msg.index("<document>") < msg.index("<output>")


def test_prompt_version_is_string():
    assert re.fullmatch(r"v\d+", PROMPT_VERSION)
