"""CLI: python -m summarizer [PATH|-] [--no-judge] [--compact]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError
from .core import summarize
from .errors import SummarizerError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m summarizer",
        description="Summarize a text file (or stdin) into a summary and action items as JSON.",
    )
    parser.add_argument("path", nargs="?", default="-", help="text file to read, or '-' for stdin (default)")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM-as-judge evaluation call")
    parser.add_argument("--compact", action="store_true", help="single-line JSON instead of indented")
    args = parser.parse_args(argv)

    try:
        text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
        result = summarize(text, include_evaluation=not args.no_judge)
    except (SummarizerError, ConfigError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
