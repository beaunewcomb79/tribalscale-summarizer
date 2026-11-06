import json

from summarizer import __main__ as cli
from summarizer.errors import EmptyInputError

from .test_api import RESPONSE


def test_cli_reads_file_and_prints_json(tmp_path, monkeypatch, capsys):
    p = tmp_path / "in.txt"
    p.write_text("hello")
    monkeypatch.setattr(cli, "summarize", lambda text, include_evaluation=True: RESPONSE)
    assert cli.main([str(p), "--no-judge"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"] == RESPONSE.summary


def test_cli_error_exit_code(tmp_path, monkeypatch, capsys):
    p = tmp_path / "in.txt"
    p.write_text("   ")

    def raiser(*a, **k):
        raise EmptyInputError("text is empty")

    monkeypatch.setattr(cli, "summarize", raiser)
    assert cli.main([str(p)]) == 1 and "text is empty" in capsys.readouterr().err


def test_cli_missing_file_is_a_clean_error(tmp_path, capsys):
    assert cli.main([str(tmp_path / "nope.txt")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error:") and "nope.txt" in err
