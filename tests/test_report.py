import json
import runpy
from pathlib import Path

REPORT = Path(__file__).resolve().parent.parent / "scripts" / "report.py"


def _row(summ_cost, judge_cost, total_ms):
    return {
        "timing_ms": {"total": total_ms, "summarize": total_ms, "judge": None},
        "usage": {"input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0, "estimated_cost_usd": summ_cost},
        "total_cost_usd": summ_cost + (judge_cost or 0),
        "evaluation": None if judge_cost is None else {
            "faithfulness": 5, "coverage": 4, "actionability": 3,
            "usage": {"input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0, "estimated_cost_usd": judge_cost},
        },
        "checks": {"action_item_count_ok": True, "summary_length_ok": False,
                   "summary_shorter_than_input": True, "items_verb_first": True},
    }


def test_report_totals_include_judge_cost(tmp_path, capsys):
    log = tmp_path / "l.jsonl"
    log.write_text(json.dumps(_row(0.010, 0.005, 100)) + "\n" + json.dumps(_row(0.020, None, 300)) + "\n")
    mod = runpy.run_path(str(REPORT))
    assert mod["main"](str(log)) == 0
    out = capsys.readouterr().out
    assert "total 0.0350" in out and "requests          2" in out
    assert "summary_length_ok" in out and "  0.0%" in out
