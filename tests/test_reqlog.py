import json

from summarizer.reqlog import append_request_log

from .test_api import RESPONSE


def test_append_request_log_writes_one_line_per_call(tmp_path):
    path = tmp_path / "logs" / "l.jsonl"
    append_request_log(str(path), RESPONSE, "text")
    append_request_log(str(path), RESPONSE, "text")
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert len(row["input_sha256"]) == 64 and all(c in "0123456789abcdef" for c in row["input_sha256"])
    assert "text" not in row and row["request_id"] == RESPONSE.metadata.request_id and "ts" in row


def test_append_request_log_noop_when_path_falsy(tmp_path):
    append_request_log(None, RESPONSE, "text")  # must not raise
