"""Deterministic, local measurements of the input and the model's output.

Rule of thumb: if Python can answer it in under a millisecond, it does not
go to the model. These checks are the cheap guardrail; the LLM judge in
`judge.py` is the expensive one. Both land in `metadata` so a reader can
compare them.
"""

from __future__ import annotations

import re

from .schemas import Checks, InputStats, OutputStats, SummaryOutput

_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)")
_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_QUOTE_CHARS = str.maketrans("", "", "\"“”'‘’")

NON_VERB_STARTERS = {
    "the", "a", "an", "it", "this", "that", "there", "we", "they",
    "he", "she", "i", "you", "our", "their",
}


def _words(text: str) -> int:
    return len(text.split())


def input_stats(text: str) -> InputStats:
    words = _words(text)
    sentences = len(_SENTENCE_END.findall(text))
    if words > 0:
        sentences = max(1, sentences)
    return InputStats(
        chars=len(text),
        words=words,
        sentences=sentences,
        est_tokens=max(1, len(text) // 4),
    )


def output_stats(text: str, output: SummaryOutput) -> OutputStats:
    summary_words = _words(output.summary)
    return OutputStats(
        summary_words=summary_words,
        compression_ratio=round(summary_words / max(1, _words(text)), 3),
        action_item_count=len(output.action_items),
    )


def _norm(s: str) -> str:
    return " ".join(s.casefold().translate(_QUOTE_CHARS).split())


def _first_word(s: str) -> str:
    stripped = s.strip()
    if not stripped:
        return ""
    return re.sub(r"[^\w]", "", stripped.split()[0]).lower()


def _quotes_found(text: str, output: SummaryOutput) -> str:
    quotes = [i.source_quote for i in output.action_items if i.source_quote is not None]
    haystack = _norm(text)
    found = sum(1 for q in quotes if _norm(q) in haystack)
    return f"{found}/{len(quotes)}"


def _novel_numbers(text: str, summary: str) -> list[str]:
    source = text.replace(",", "")
    seen: list[str] = []
    for n in _NUMBER.findall(summary):
        if n.replace(",", "") not in source and n not in seen:
            seen.append(n)
    return seen


def run_checks(text: str, output: SummaryOutput) -> Checks:
    stats = output_stats(text, output)
    return Checks(
        action_item_count_ok=len(output.action_items) == 3,
        summary_length_ok=15 <= stats.summary_words <= 150,
        summary_shorter_than_input=stats.compression_ratio < 1.0,
        items_verb_first=all(_first_word(i.text) not in NON_VERB_STARTERS for i in output.action_items),
        quotes_found_in_source=_quotes_found(text, output),
        novel_numbers_in_summary=_novel_numbers(text, output.summary),
    )
