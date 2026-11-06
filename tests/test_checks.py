from summarizer.checks import input_stats, run_checks
from summarizer.schemas import ActionItem, SummaryOutput


def mk(summary, *quotes):
    items = [
        ActionItem(text=f"Do thing {i}", owner=None, due=None, priority="low", source_quote=q, grounded=q is not None)
        for i, q in enumerate(quotes)
    ]
    return SummaryOutput(summary=summary, action_items=items)


def test_quotes_found_counts_only_non_null():
    out = mk("Alpha beta " * 10, "beta gamma", None)
    assert run_checks("alpha  BETA gamma delta", out).quotes_found_in_source == "1/1"


def test_quotes_found_zero_of_zero_when_all_null():
    assert run_checks("some text here", mk("Short summary here ok " * 4, None)).quotes_found_in_source == "0/0"


def test_count_ok_only_at_three():
    assert run_checks("t", mk("w " * 20, "a", "b", "c")).action_item_count_ok is True
    assert run_checks("t", mk("w " * 20, "a", "b")).action_item_count_ok is False


def test_summary_echoing_input_is_flagged():
    text = "one two three four five six seven eight nine ten " * 3
    assert run_checks(text, mk(text)).summary_shorter_than_input is False


def test_novel_numbers():
    out = mk("Revenue was 1,200 in Q3 and 45 in Q4 " * 2)
    assert run_checks("Revenue was 1200 in Q3.", out).novel_numbers_in_summary == ["45", "4"]


def test_verb_first_heuristic():
    assert run_checks("t", mk("w " * 20, "Send the deck")).items_verb_first is True
    bad = SummaryOutput(
        summary="w " * 20,
        action_items=[ActionItem(text="The deck should be sent", owner=None, due=None, priority="low", source_quote=None, grounded=True)],
    )
    assert run_checks("t", bad).items_verb_first is False


def test_input_stats_basic():
    s = input_stats("Hello there. How are you? Fine!")
    assert (s.words, s.sentences, s.chars) == (6, 3, 31) and s.est_tokens == 7
