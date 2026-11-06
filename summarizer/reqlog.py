"""Append-only JSONL log of request metadata, for offline analytics.

One line per request: timestamp, a hash of the input (never the input
itself; note that judge rationales inside `metadata` may quote it), and
the full `metadata` block. Logging never fails a request.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .schemas import SummaryResponse


def append_request_log(path: str | None, response: SummaryResponse, input_text: str) -> None:
    if not path:
        return
    row = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "input_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        **response.metadata.model_dump(mode="json"),
    }
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        return
