"""FastAPI wrapper around `summarize()`.

Run with: uv run uvicorn summarizer.api:app --reload
Docs at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import ConfigError
from .core import summarize
from .errors import SummarizerError
from .schemas import SummarizeRequest, SummaryResponse

app = FastAPI(
    title="Text Summarizer",
    version="0.1.0",
    description="Turns a block of text into a short summary and up to three grounded action items.",
)


@app.exception_handler(SummarizerError)
async def _summarizer_error(_: Request, exc: SummarizerError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(ConfigError)
async def _config_error(_: Request, exc: ConfigError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/summarize", response_model=SummaryResponse)
def summarize_endpoint(body: SummarizeRequest) -> SummaryResponse:
    # `summarize` is looked up on this module at call time so tests can patch it.
    return summarize(body.text, include_evaluation=body.include_evaluation)
