import pytest

from summarizer.config import ConfigError, estimate_cost_usd, get_client, load_settings


def test_defaults_when_env_empty():
    s = load_settings(env={})
    assert s.model == "claude-opus-5-5" and s.effort == "medium"
    assert s.judge_model == "claude-opus-5-5" and s.judge_effort == "low"
    assert s.judge_enabled is True and s.max_input_chars == 100000


def test_env_overrides():
    s = load_settings(env={"SUMMARIZER_MODEL": "claude-sonnet-5-5", "JUDGE_ENABLED": "false", "MAX_INPUT_CHARS": "10"})
    assert s.model == "claude-sonnet-5-5" and s.judge_enabled is False and s.max_input_chars == 10


def test_get_client_without_key_raises():
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        get_client(load_settings(env={}))


def test_estimate_cost():
    assert estimate_cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == 24.0
    assert estimate_cost_usd("made-up", 1, 1) is None


def test_env_example_documents_every_setting():
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / ".env.example"
    text = example.read_text()
    for var in ("ANTHROPIC_API_KEY", "SUMMARIZER_MODEL", "SUMMARIZER_EFFORT", "JUDGE_MODEL",
                "JUDGE_EFFORT", "JUDGE_ENABLED", "MAX_INPUT_CHARS", "REQUEST_LOG_PATH"):
        assert var in text, var
