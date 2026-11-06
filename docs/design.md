# Design: text to summary and action items

The brief: build a function or API that takes a block of text, uses an AI model to produce a short summary and up to three key action items, and returns structured JSON. The evaluation criteria are how the solution is structured, how the AI tools are used, and how clearly the thinking is communicated. This document is the thinking; the README is the walkthrough.

## Goals

- One clean Python function, `summarize(text) -> SummaryResponse`, that is the whole product. The HTTP endpoint and the CLI are thin wrappers around it.
- Output is schema-validated JSON every time, via structured outputs, not regex over prose.
- A `metadata` block that makes each call observable: what it cost, how long it took, how big the input was, and how much the output can be trusted.
- The write-up reads as an engineering log: decisions, prompts, what went wrong, what to improve.

## Non-goals

- Auth, rate limiting, persistence, deployment, streaming, batching.
- Providers other than Anthropic. A provider seam is listed under improvements, not built.
- Chunking inputs that exceed the context window. Input is capped and a 413 is returned instead.

## Anti-goals

These would make the result a failure even if it technically works:

- Hallucinated action items presented with the same confidence as grounded ones.
- A response that is valid JSON but silently truncated or partially filled.
- The API key anywhere in git, logs, or a response.
- A write-up that lists what was built but not what went wrong.

## Decisions

### Stack

| Piece | Choice | Why |
|---|---|---|
| Core | `summarizer/core.py` with `summarize()` | The deliverable is a function or API. The function is the product; the API is a wrapper. |
| Schema | Pydantic models | One model is both the structured-output schema handed to the SDK and the response model for FastAPI. |
| HTTP | FastAPI, single `POST /summarize` | Free OpenAPI docs at `/docs`, typed request and response, about thirty lines. |
| CLI | `python -m summarizer` | A reviewer can run it without starting a server. |
| Tests | pytest with a fake SDK client, plus opt-in live tests | Deterministic tests for the local checks; the live tests prove the real call works. |
| Packaging | `uv` and `pyproject.toml` | Fast, lockfile, one command to run. |

### API key

- Read from `ANTHROPIC_API_KEY`. Local development loads a git-ignored `.env` through `python-dotenv`; `.env.example` is committed with placeholders.
- The client constructor fails fast with a clear message if the key is missing. The key is never echoed in logs or errors.
- In production the same variable would be injected by a secrets manager (AWS Secrets Manager or SSM), not a file on disk.

### Model and request shape

- `SUMMARIZER_MODEL` defaults to `claude-opus-5-5`, `SUMMARIZER_EFFORT` to `medium`. Summarization is routine work and that model defaults to medium anyway. Thinking is always on for this model family, so no `thinking` parameter is sent.
- `client.messages.parse(..., output_format=SummaryOutput)`: the SDK validates the response against the Pydantic schema and returns a typed object. No assistant prefill and no `temperature`, both of which the current API rejects.
- `max_tokens` is 16000 for the summarizer and 4096 for the judge. The outputs are short, but thinking tokens count against the limit on this model family, so the ceiling leaves room; it only bounds a runaway response.
- Refusals: `stop_reason == "refusal"` becomes a 422 carrying the `stop_details` category. No server-side fallback beta header; an explicit error is easier to reason about in a take-home, and the fallback is listed under improvements.
- Prompt caching does not apply: every request body is unique and the system prompt is below the minimum cacheable size.

### Prompt design

- The system prompt is a versioned constant (`PROMPT_VERSION`), recorded in every response's metadata, so an output can always be traced to the prompt that produced it.
- It sets a role (careful analyst writing for someone who has not read the text), a summary length target, and the action-item rules: imperative and verb-first, concrete, each tied to a short verbatim `source_quote`, `owner` and `due` only when stated, `grounded: false` when inferred, and return fewer than three rather than invent.
- The document goes in the user turn wrapped in `<document>` tags with the instruction after it. The prompt says the document is data, not instructions, as a basic injection guard.

### Action item count

The brief says three. The schema allows zero to three. Forcing three on a text that only supports one produces invented items with the same confidence as real ones, which is the anti-goal above. Instead, each item carries `grounded` and `source_quote`, and the local check `action_item_count_ok` is false whenever fewer than three come back, so a thin input is visible in `metadata` rather than hidden.

### LLM as judge

- A second, independent call. `JUDGE_MODEL` defaults to the same model, `JUDGE_EFFORT` to `low`. Toggled per request with `include_evaluation` and globally with `JUDGE_ENABLED`.
- The judge sees the source text and the produced JSON, never the summarizer's prompt, and returns integer scores from 1 to 5 for faithfulness, coverage and actionability, a one-line rationale for each, and `unsupported_claims`: anything it could not find in the source. An empty list is the pass signal.
- Judge failure never fails the request: `evaluation` becomes null and `evaluation_error` says why.
- Known weakness: a model grading its own output has self-preference bias. See improvements.

### What comes from the model and what is measured locally

| From the model (judgement, non-deterministic) | Measured locally (deterministic, cheap) |
|---|---|
| `summary` | Wall-clock timing: total, summarizer call, judge call |
| `action_items[]`: `text`, `owner`, `due`, `priority`, `source_quote`, `grounded` | Token usage from the response, including thinking tokens, and an estimated USD cost from a small price table keyed by model, per call and as `total_cost_usd` |
| Judge: `faithfulness`, `coverage`, `actionability`, rationales, `unsupported_claims` | Input stats: chars, words, sentences, rough token estimate |
| | Output stats: summary word count, compression ratio, action item count |
| | `checks`: item count is three, summary length in band, summary shorter than input, items verb-first, each `source_quote` found verbatim in the source after whitespace normalisation, numbers in the summary that do not appear in the source |
| | Provenance: `request_id`, `model`, `prompt_version`, `stop_reason`, application-level retries |

Rule of thumb: if Python can answer it in under a millisecond, it does not go to the model. The local checks are the cheap guardrail and the judge is the expensive one. Both land in `metadata` so a reader can compare them.

### Input handling and errors

| Condition | Behaviour |
|---|---|
| Empty or whitespace-only text (including Unicode spaces) | 422 before any API call |
| Text longer than `MAX_INPUT_CHARS` (default 100k) | 413, no API call |
| SDK rate limit | 429 |
| SDK 5xx or connection error | 502, after the SDK's own two retries |
| `stop_reason == "refusal"` | 422 with the category |
| `stop_reason == "max_tokens"` | 502, response treated as truncated |
| Output fails schema validation (the SDK raises; should be rare with structured outputs) | one application retry, then 502 |

### Analytics beyond the response

Every request appends one JSON line to `logs/requests.jsonl` (git-ignored) containing the `metadata` block and a hash of the input, never the input itself (judge rationales inside `metadata` may quote it). `scripts/report.py` prints p50 and p95 latency, mean cost, mean judge scores and check pass rates across the log. Logging failures never fail a request.

## Improvements with more time

Listed in the README. In short: a provider seam, server-side refusal fallback, chunking for long inputs, calibrating the judge against a small human-labelled set, a different model family as judge, prompt caching for batch runs, an async or batch endpoint, and OpenTelemetry spans.
