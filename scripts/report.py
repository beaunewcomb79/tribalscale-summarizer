"""Summarise logs/requests.jsonl: latency, cost, judge scores, check pass rates.

Usage: uv run python scripts/report.py [path]
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
    return s[k]


def main(path: str = "logs/requests.jsonl") -> int:
    p = Path(path)
    if not p.exists():
        print(f"no log at {p}")
        return 1
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    if not rows:
        print("log is empty")
        return 1

    totals = [r["timing_ms"]["total"] for r in rows]
    costs = [
        r.get("total_cost_usd")
        if r.get("total_cost_usd") is not None
        else (r["usage"]["estimated_cost_usd"] or 0.0)
        + (((r.get("evaluation") or {}).get("usage") or {}).get("estimated_cost_usd") or 0.0)
        for r in rows
    ]
    evals = [r["evaluation"] for r in rows if r.get("evaluation")]
    print(f"requests          {len(rows)}")
    print(f"latency ms        p50 {pct(totals, 0.5):.0f}   p95 {pct(totals, 0.95):.0f}")
    print(f"cost usd (incl. judge) mean {statistics.mean(costs):.4f}   total {sum(costs):.4f}")
    if evals:
        for dim in ("faithfulness", "coverage", "actionability"):
            print(f"judge {dim:<13} mean {statistics.mean(e[dim] for e in evals):.2f}  (n={len(evals)})")
    print("checks pass rate")
    for key in ("action_item_count_ok", "summary_length_ok", "summary_shorter_than_input", "items_verb_first"):
        vals = [r["checks"][key] for r in rows if key in r["checks"]]
        if vals:
            print(f"  {key:<28} {100 * sum(vals) / len(vals):5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
