# Proposal: Unified LLM Verdict Classifier

## Why

Over the last two weeks we had two confirmed silent gate pass incidents where the review gate explicitly saw the LLM report CRITICAL findings and still let the change merge:

1. **2026-04-11 micro/create-task** — the review LLM emitted `### Finding 1: … **NOT_FIXED** [CRITICAL]` × 3 plus a summary `**Summary: 0/3 fixed, 3 NOT_FIXED [CRITICAL].**`. The gate returned `review_result=pass`. Three real issues (missing `waitUntil: 'networkidle'`, missing blank-input validation test, no title length limit in the server action) merged into main with no downstream safety net catching them.
2. **2026-04-10 minishop_0410/product-catalog attempt 4** — the review LLM emitted `### Finding 5: [CRITICAL] E2E test file still does not exist … **NOT_FIXED** [CRITICAL]` plus `**REVIEW BLOCKED** — 1 unique critical issue remains`. The gate returned `review_result=pass`. Attempt 5 happened to create the missing file for unrelated reasons, so the incident never produced a visible failure — but the gate would have released a broken diff.

Root cause in both cases is the same: the review-gate verdict is derived from a body-regex heuristic (`_parse_review_issues` at `lib/set_orch/verifier.py:152`) that only matches lines starting with `ISSUE:` or `**ISSUE:`. First-round reviews follow that format. Retry reviews use a different markdown structure — `### Finding N:` headers, `**NOT_FIXED** [CRITICAL]` annotations, `**REVIEW BLOCKED**` summaries, or markdown table rows — and the regex matches nothing, so the parser returns zero issues, `has_critical=False`, and the gate passes.

An earlier commit (`701bdbc2`, 2026-04-09) fixed the same class of bug in the spec-verify gate by switching to a sentinel-based self-report (`CRITICAL_COUNT: N` + `VERIFY_RESULT: PASS|FAIL`) with an explicit warning:

> Deliberately NOT body-regex heuristics — per prior incident, pattern matching on CRITICAL body text has misdiagnosed real findings. The model now self-reports the count and the parser is dumb.

The review gate never received the same treatment. The issue investigator (`lib/set_orch/issues/investigator.py:190`) uses the same keyword-heuristic pattern for `impact`, `fix_scope`, and `fix_target` — driving auto-fix policy decisions — and has the same latent failure mode.

A sentinel-only fix leaves us exposed to any LLM prompt that emits findings in an unexpected format. Two separate production bugs have already slipped through sentinel-style parsers because the LLM decided to use a different shape. We need a format-agnostic verdict extraction that does not depend on the primary LLM cooperating with a specific template.

## What

Introduce a unified **LLM verdict classifier** — a single helper that takes an arbitrary primary-LLM narrative and a JSON schema, invokes a second cheap Sonnet pass to classify the narrative into structured fields, and returns a typed verdict. Apply it across every gate surface where an LLM decision currently flows through body-regex or keyword-heuristic parsing:

1. New module `lib/set_orch/llm_verdict.py` with `classify_verdict(primary_output, schema, *, model="sonnet", purpose="", timeout=120)` returning a typed dict. The second pass reads the primary output verbatim, is instructed to extract structured findings, and emits pure JSON. The helper parses the JSON, validates the schema, and surfaces a conservative fail-safe result if anything goes wrong (network error, JSON decode error, missing fields, timeout).

2. **Review gate refactor** — keep `_parse_review_issues` as a fast-path for the structured first-round format (cheap, no extra LLM call) but fall through to the classifier when the fast-path returns zero issues on a non-trivial review output. Remove the `re.search(r"REVIEW\s+PASS", …)` early exit entirely; it has always been a false-positive risk (quoted references, "REVIEW PASSED all previous" phrasing) and is now redundant. Both silent-pass incidents are covered by the classifier fallback.

3. **Issue investigator refactor** — replace the keyword lists (`if "critical" in lines`, `if "minor" in lines`, `framework_indicators`) with a classifier call on proposal.md. Keep the existing `**Target:**`, `**Impact:**`, `**Fix-Scope:**` sentinel lookup as a preferred override — when present, trust the sentinel; otherwise fall through to the classifier. This preserves determinism for operators who write proposals in the explicit format.

4. **Spec-verify defense in depth** — add a classifier fallback for the case where the spec-verify LLM fails to emit the sentinel lines. Today this path silently passes because the gate's backward-compat escape assumes "no sentinel = probably OK". In a world where we already had two classifier-missed bugs, that is too generous. When the sentinel is absent, invoke the classifier on the verify output and use its structured verdict; only pass if the classifier also reports zero critical findings.

5. **Severity drift fix** — `_parse_review_issues` currently assigns severity from two sources (inline `[TAG]` tag AND a summary scan), and the two disagree in ~9 out of ~30 findings. Make the inline `[TAG]` tag the single source of truth and drop the summary scan. The classifier fallback already returns canonical severities, so drift between the two paths becomes impossible.

6. **Rollout directive** — add `llm_verdict_classifier_enabled: bool = True` to `Directives` so operators can disable the feature if Sonnet cost becomes a problem. The default is `True`; only operators who explicitly set `False` revert to the old regex-only path.

7. **Unit tests** — capture the two silent-pass incidents as regression fossils using the exact `review_output` text extracted from the log audit. These tests must fail on pre-fix code (documenting the bug) and pass on post-fix code (proving the fix).

## Impact

- **Affected specs**: `verifier-review-gate` (new requirements around classifier fallback and removal of `REVIEW PASS` regex), `verifier-spec-verify` (new requirement around classifier fallback for missing sentinel), `issue-investigation` (new requirements around classifier-driven diagnosis).
- **Affected code**: `lib/set_orch/verifier.py` (review gate + spec_verify fallback), `lib/set_orch/issues/investigator.py` (proposal parsing), `lib/set_orch/engine.py` (Directives field + parser), new `lib/set_orch/llm_verdict.py` module.
- **New tests**: `tests/unit/test_llm_verdict.py` (6 classifier unit tests including mocked Sonnet responses), new tests in `tests/unit/test_verifier.py` (3 review gate tests including both silent-pass fossils), new tests in `tests/unit/test_investigator.py` or equivalent (2 investigator classifier tests).
- **Runtime cost**: one extra Sonnet call per review-gate execution when the fast-path finds zero issues (typical review output is ~5-20k tokens, Sonnet input cost is negligible compared to the primary review). Estimated overhead: <1 cent per change.
- **Migration**: no state or config migration required. The directive default of `True` is the new behavior; operators can opt out.
- **Observability**: every classifier call logs INFO with purpose, primary output size, and verdict counts. A new `CLASSIFIER_CALL` event is emitted for post-run analysis.
