"""Typed errors. Each carries the HTTP status the API layer should use."""

from __future__ import annotations


class SummarizerError(Exception):
    status_code: int = 500


class EmptyInputError(SummarizerError):
    status_code = 422


class InputTooLargeError(SummarizerError):
    status_code = 413


class RefusedError(SummarizerError):
    status_code = 422

    def __init__(self, message: str, *, category: str | None = None) -> None:
        super().__init__(message)
        self.category = category


class RateLimitedError(SummarizerError):
    status_code = 429


class UpstreamError(SummarizerError):
    status_code = 502
