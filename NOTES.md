# Build notes: what happened, what changed, and why

Running log kept while building. Newest at the bottom.

## 2026-11-06 - first live run (prompt v1)

Inputs: `examples/meeting_notes.txt` (414 words, five explicit commitments) and
`examples/thin_input.txt` (159 words of descriptive prose, no tasks).

Meeting notes, v1:
- 3 action items, all `grounded: true`, `quotes_found_in_source: 3/3` (every quote was verbatim), all verb-first.
- Owners and dates came through correctly (Marcus / end of day Wednesday, Dana / Friday 7 November).
- Summary: 4 sentences, 131 words. Accurate (judge faithfulness 5, no unsupported claims, no novel numbers) but long for a "short summary".
- Judge coverage: 3. Its rationale penalised the *action items* for leaving out Sofia's error states, the offline-sync fix and Priya circulating notes. That is a rubric problem, not an output problem: we asked for the three most important items, so "not exhaustive" should not cost coverage points. The coverage dimension was meant to grade the summary.
- Summarizer call 1.9 cents (judge not counted here); 10.1 s total (6.6 s summarize, 3.5 s judge). `thinking_tokens: 0` at effort medium.

Thin input, v1:
- 0 action items, which is the behaviour we wanted (no invented tasks). `action_item_count_ok: false` flags it in metadata as designed.
- Judge 5/5/5 and explicitly noted "the document is purely descriptive with no tasks, so the empty action item list is correct".
- Summarizer call 1.0 cent (judge not counted here), 5.7 s.

Changes for v2:
1. Summarizer: add a length target (aim for 60 to 100 words) so "2-4 sentences" cannot become four 35-word sentences.
2. Judge: state that coverage grades the summary only, and that action items are judged on whether the chosen ones are the most important, not on whether every commitment was listed.

## 2026-11-06 - second live run (prompt v2)

Meeting notes, v2:
- Summary 89 words (was 131), now 3 sentences (was 4), still faithfulness 5 with no unsupported claims.
- Judge coverage 4 (was 3). Its remaining complaint is that the summary omits the checkout redesign and the missing error states, which is fair for a 90-word summary of a 430-word document.
- Judge actionability 4 (was 5): it now argues Sofia's error-state mockups are "arguably as important" as scheduling the security review. That is a judgement call about the third pick, not a defect, and it is exactly the kind of signal we wanted the judge to surface.
- Same three items, same owners and dates, `quotes_found_in_source` still 3/3.
- Summarizer 1.8 cents plus judge 1.4 cents, 3.2 cents in all; 7.8 s total.

Thin input, v2: unchanged behaviour (0 items, 5/5/5), 89 words.

Stopping here. Two iterations is enough to show the loop; further tuning would be chasing the judge's taste rather than fixing a problem.

Things that cost time during the build (not prompt related):
- Pinning `prompt_version == "v1"` in three test files meant the first prompt bump broke tests that had nothing to do with prompt wording. Changed them to assert the shape (`v\d+`) or compare against the constant.
- `thinking_tokens` comes back as 0 at effort `medium` on this input size. Adaptive thinking decided the task did not need it, so the cost estimate is dominated by input tokens. Worth knowing before assuming effort changes the bill.
- A local hook refuses to let tooling read `.env`, so the key was written from the password manager without ever being printed or read back. Good default; the code only ever reads it through `dotenv_values` at runtime.

## 2026-11-06 - request log

Added the JSONL request log and the report script last. First run of the report showed seven rows with zero latency: the unit tests had been building settings from an explicit empty environment, which fell through to the default log path and wrote fake rows into the real `logs/` directory. Fixed by disabling the log path in test settings. Lesson: a default that writes to disk needs a test asserting the tests themselves do not trigger it.

## 2026-11-06 - review fix pass

A fresh-context review of the whole branch found one real bug and three documentation errors:
- The SDK raises `pydantic.ValidationError` from `messages.parse` when the model's JSON does not fit the schema (including JSON truncated at `max_tokens`). The core only caught SDK transport errors, so that path escaped as a bare 500 while the design doc claimed "retry once, then 502". Fixed by catching it in the retry loop; two new tests pin it. Also raised `max_tokens` to 16000 for the summarizer and 4096 for the judge, since thinking tokens count against it on this model family.
- The live tests skipped with a misleading message when the key was exported in the shell rather than put in `.env`, because the test fixture overwrote it. The fixture now leaves live tests alone.
- Cost was reported per call but never totalled, and the README said "about 2 cents" where the real figure including the judge is about 3. Added `total_cost_usd` to metadata and to the report.
- `.env.example` was missing two variables the README said it documented.
