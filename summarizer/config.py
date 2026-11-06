"""Settings, client construction and a small price table.

Everything configurable comes from environment variables. For local
development a `.env` file is merged underneath the real environment
(the environment always wins).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

import anthropic
from dotenv import dotenv_values

# USD per million tokens: (input, output). Checked against the pricing
# page on 2026-11-06. Unknown models get `None` for cost rather than a guess.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

_TRUE = {"1", "true", "yes", "on"}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    effort: str
    judge_model: str
    judge_effort: str
    judge_enabled: bool
    max_input_chars: int
    request_log_path: str | None


def _merged_env() -> dict[str, str]:
    file_values = {k: v for k, v in dotenv_values(".env").items() if v is not None}
    return {**file_values, **os.environ}


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from `env`, or from `.env` + os.environ when None."""
    e = _merged_env() if env is None else env
    return Settings(
        api_key=e.get("ANTHROPIC_API_KEY") or None,
        model=e.get("SUMMARIZER_MODEL", "claude-opus-5-5"),
        effort=e.get("SUMMARIZER_EFFORT", "medium"),
        judge_model=e.get("JUDGE_MODEL", "claude-opus-5-5"),
        judge_effort=e.get("JUDGE_EFFORT", "low"),
        judge_enabled=e.get("JUDGE_ENABLED", "true").strip().lower() in _TRUE,
        max_input_chars=int(e.get("MAX_INPUT_CHARS", "100000")),
        request_log_path=e.get("REQUEST_LOG_PATH", "logs/requests.jsonl") or None,
    )


def get_client(settings: Settings) -> anthropic.Anthropic:
    if not settings.api_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in, "
            "or export the variable."
        )
    return anthropic.Anthropic(api_key=settings.api_key)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    in_price, out_price = prices
    return round((input_tokens * in_price + output_tokens * out_price) / 1_000_000, 6)
