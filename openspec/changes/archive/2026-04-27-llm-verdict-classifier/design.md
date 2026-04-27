# Design: LLM Verdict Classifier

## Context

Two silent-pass incidents (reproduced in proposal.md) exposed the same structural weakness in the set-core gate pipeline: every gate that calls an LLM and derives a verdict from the LLM's prose output is vulnerable to format drift. When the LLM decides to write findings as `### Finding N:` headers instead of `ISSUE: [CRITICAL]` inline tags, the regex parser emits zero findings and the gate silently passes.

The spec-verify gate was fixed in 701bdbc2 by asking the LLM to self-report a `CRITICAL_COUNT: N` sentinel. That fix works when the LLM cooperates, but it has a known escape hatch: if the sentinel is missing (model forgot, truncation, prompt regression), the gate defaults to pass on the assumption that "probably fine". In light of the two incidents on the review gate, the "probably fine" default is too generous.

The correct long-term pattern is format-agnostic: a second LLM pass reads the primary output as unstructured text and classifies it into a structured verdict. A small model (Sonnet) is more than capable of reading 5-30k tokens of review narrative and returning a JSON object describing the findings. This decouples the verdict extraction from the prompt format of the primary call, and the same helper can be reused wherever the same pattern applies.

## Goals

1. **Zero silent passes on gate verdicts.** If the LLM says "3 NOT_FIXED [CRITICAL]" anywhere in its output, the gate must fail.
2. **Format-agnostic verdict extraction.** The classifier must work on first-round reviews, retry reviews, markdown tables, `### Finding` headers, `ISSUE: [TAG]` inline, and plain narrative.
3. **One shared helper.** Review gate, investigator, and spec-verify fallback all call the same `classify_verdict()` function with different schemas.
4. **Deterministic fast-path.** Keep the cheap regex fast-path for structured first-round reviews so the classifier only runs when needed.
5. **Fail-safe on classifier errors.** Network timeout, JSON decode error, missing fields, exit-nonzero — any classifier failure must treat the gate as FAIL, not PASS.
6. **Reversible rollout.** `llm_verdict_classifier_enabled` directive allows operators to disable the feature if cost or latency becomes a concern.

## Non-goals

- Replacing every LLM call with a classifier. Planner, digest, and auditor already request JSON from the primary call — adding a classifier would just double the cost for no robustness gain.
- Replacing subprocess-based gate verdicts (build, test, e2e, rules). Those derive verdicts from exit codes and do not use LLM output.
- Retraining or fine-tuning the classifier model — Sonnet with a clear prompt is sufficient.
- Severity rubric harmonization across models. If Claude decides an issue is LOW on first review and CRITICAL on retry, that is a prompt-design problem, not a parser problem. The classifier captures whatever the model says; the gate verdict honors the classifier's output.

## Decisions

### 1. Single `classify_verdict()` helper in a new module

The helper lives in `lib/set_orch/llm_verdict.py`. It is deliberately thin — no gate-specific logic, no retry policy, no severity rubric. Callers pass in the primary output, the JSON schema they want back, and an optional `purpose` string for logging.

```python
def classify_verdict(
    primary_output: str,
    schema: dict,
    *,
    model: str = "sonnet",
    purpose: str = "",
    timeout: int = 120,
) -> ClassifierResult:
    """Run a second LLM pass to classify primary_output into structured JSON.

    Returns ClassifierResult with .verdict (str), .critical_count (int),
    .high_count (int), .medium_count (int), .low_count (int), .findings (list),
    .raw_json (dict), .error (str | None), .elapsed_ms (int).

    On ANY error (timeout, non-JSON, missing required fields, empty output)
    returns a conservative fail-safe result with verdict="fail", critical_count=1,
    error=<reason> so callers can decide whether to block.
    """
```

The return type is a dataclass rather than a raw dict so that typo-ing a key at the call site fails at import time, not at runtime.

### 2. Classifier prompt structure

The classifier prompt is constructed from the schema dict. It always contains:

1. A role statement: "You are a gate verdict extractor. Your job is to read the output of another LLM and produce a structured JSON verdict."
2. The schema — literal JSON schema text — prefixed with "Return a JSON object matching this exact shape:".
3. The primary output verbatim, wrapped in `<<<BEGIN OUTPUT>>>` / `<<<END OUTPUT>>>` delimiters.
4. A closing instruction: "Respond with ONLY the JSON object. No preamble, no markdown fences, no commentary."

This is deliberately minimal — the classifier has no knowledge of what kind of gate is running or what severity rubric applies. It only extracts what is already in the text. The primary LLM's prose IS the source of truth; the classifier just gives it structure.

### 3. Review gate: fast-path + classifier fallback (defense in depth)

The review gate execution flow becomes:

1. Run the primary review via Claude as today.
2. Run the existing regex fast-path (`_parse_review_issues`) — cheap, deterministic, handles first-round reviews correctly.
3. If the fast-path returns zero findings AND the review output length is ≥ 500 characters AND the operator has the classifier enabled: invoke the classifier with the review schema.
4. If the classifier reports `critical_count > 0`: override the fast-path and mark the gate as fail with the classifier's finding list.
5. If the classifier reports `critical_count == 0` AND `error is None`: pass.
6. If the classifier errors out: log WARNING and pass (backward compat — the fast-path already said zero critical, and we treat classifier error as "no new information").

Removing the `re.search(r"REVIEW\s+PASS")` early exit is essential. That check short-circuits the entire verdict derivation the moment the LLM writes the literal phrase "REVIEW PASS" anywhere — including in a quoted heading, a reference to a prior review, or an acknowledgement like "REVIEW PASSED for previous findings, but new ones found…". The classifier + fast-path together already handle the PASS signal; the regex just adds a false-positive window.

### 4. Investigator: sentinel preferred, classifier fallback

The investigator's proposal parser becomes:

1. Read `proposal.md` (already committed to the change directory by the investigation agent).
2. Look for explicit sentinels: `**Impact:** (low|medium|high)`, `**Fix-Scope:** (single_file|multi_file|config_override)`, `**Target:** (framework|consumer|both)`, `**Confidence:** (0-100)`.
3. For any sentinel found, use the sentinel value verbatim.
4. For any sentinel NOT found AND the classifier is enabled: invoke the classifier on the proposal text with the investigator schema.
5. Classifier output fills in missing fields.
6. If the classifier errors out: fall back to the old keyword heuristics as a last resort so the investigator can still make a decision.

This preserves determinism for operators who write proposals with the explicit sentinel format (used by `/opsx:ff` templates) while fixing the silent-drift case where the LLM writes free-form markdown.

### 5. Spec-verify: classifier fallback on missing sentinel

The spec-verify gate currently has three branches:

1. `VERIFY_RESULT: PASS` + `CRITICAL_COUNT: 0` → pass (the happy path).
2. `VERIFY_RESULT: FAIL` + `CRITICAL_COUNT: 0` → downgrade to pass with WARNING (warnings-only).
3. `VERIFY_RESULT: FAIL` + `CRITICAL_COUNT > 0` → fail.
4. No sentinel → pass with `[ANOMALY]` WARNING log (backward compat).

Branch 4 is the silent-pass escape hatch. Replace it with: if no sentinel AND classifier enabled → invoke the classifier on the verify output with the spec-verify schema → use its verdict. If the classifier also finds zero critical, then pass (the warning log still fires). If the classifier finds critical findings, the gate fails. If the classifier errors out, fail closed (since there is no trustworthy signal at all).

### 6. Severity drift: single source of truth

`_parse_review_issues` currently sets severity from TWO sources (inline `[TAG]` prefix AND a separate summary scan), which the log audit showed disagree 9 out of ~30 times. The fix is simple: remove the summary scan, keep only the inline `[TAG]` prefix check. The classifier fallback already returns canonical severities (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), so the two paths converge on the same rubric.

### 7. Rollout directive

New `Directives.llm_verdict_classifier_enabled: bool = True` plus `parse_directives` update. When set to `False`, every gate that would call the classifier skips it and falls back to the old regex-only path. The directive is checked at gate entry, not at module import, so operators can toggle it mid-run by editing the state file.

### 8. Events and observability

- Emit `CLASSIFIER_CALL` event on every classifier invocation with fields `purpose`, `primary_output_bytes`, `verdict`, `critical_count`, `elapsed_ms`, `error`.
- Log INFO line at gate entry: `Gate[review] classifier fallback — fast-path found 0 issues, running classifier on N bytes`.
- Log WARNING line on classifier error: `Gate[review] classifier failed (timeout|decode|missing): <detail>`.
- Log ERROR line when the classifier OVERRIDES the fast-path: `Gate[review] classifier found N critical issues that fast-path missed — merge blocked. Pattern: <first finding summary>`. This ERROR is the observability signal that will drive future fixes to the fast-path.

### 9. Unit test fixtures from the two incidents

Both silent-pass incidents are preserved as test fixtures:

- `tests/unit/fixtures/review_output_micro_create_task_2026_04_11.txt` — the full 3×NOT_FIXED review output from micro/create-task 17:09:54. The test passes this to the classifier mock and asserts `critical_count == 3`.
- `tests/unit/fixtures/review_output_minishop_0410_product_catalog_attempt4.txt` — the full review output from minishop_0410/product-catalog attempt 4 21:16:01. Same shape test.
- `tests/unit/fixtures/review_output_first_round_inline_format.txt` — a first-round review with `ISSUE: [CRITICAL]` inline format. Asserts the fast-path catches it without needing the classifier.

The classifier tests use a mocked `run_claude_logged` that returns a deterministic JSON response. The gate integration tests use both the mocked classifier and the mocked primary review to simulate a full pipeline run.

### 10. Directive naming

`llm_verdict_classifier_enabled` is verbose but unambiguous. Alternatives considered:
- `classifier_enabled` — too generic
- `review_classifier_enabled` — misleading once investigator and spec-verify also use it
- `verdict_classifier` — ambiguous (enabled? required?)

The long name makes the intent obvious at config time. The directive parser already handles snake_case fields via `_bool(raw, "llm_verdict_classifier_enabled", d.llm_verdict_classifier_enabled)`.

## Alternatives considered

### A. Sentinel-only fix (like 701bdbc2 for spec-verify)

**Rejected.** The spec-verify sentinel fix is elegant but depends on the primary LLM cooperating with the exact sentinel format. The two review-gate incidents both happened AFTER the spec-verify sentinel fix was in place — a retry review is conceptually the same pattern, but the LLM emitted `**NOT_FIXED** [CRITICAL]` as a header instead of `ISSUE: [CRITICAL]` inline, and any sentinel addition would be vulnerable to the same drift. The classifier approach is format-agnostic by construction and does not depend on the primary call following a template.

### B. Fail closed when fast-path finds 0 issues on long output

**Rejected.** This would fail the gate on every review that legitimately finds no issues. Zero findings is the common case on well-written changes. A blanket "0 issues = suspicious = fail" rule would produce false positives several times per day.

### C. Structured output mode (tool-use / JSON mode) on the primary review

**Considered for future work.** Anthropic's tool-use feature lets the primary call emit structured JSON directly, eliminating the need for a parser. This is strictly better than the current approach for new calls. However, retrofitting every review prompt is a significant refactor and the current change needs to ship quickly to unblock the video demo. The classifier approach lets us fix the silent-pass class today without rewriting existing prompts; tool-use can migrate call sites incrementally afterwards.

### D. Regex the retry-review format explicitly

**Rejected.** We could add a second regex that matches `### Finding N: ... **NOT_FIXED** [CRITICAL]`, but that just moves the goalposts. The next LLM prompt revision will invent another format and we will have the same class of bug. The commit message of 701bdbc2 already warned explicitly: "Deliberately NOT body-regex heuristics — per prior incident, pattern matching on CRITICAL body text has misdiagnosed real findings." Adding more regex goes in the wrong direction.

## Risks

1. **Classifier hallucination.** The classifier could fabricate findings that were not in the primary output. Mitigation: prompt explicitly says "extract ONLY findings that are in the primary output, do not invent or infer". Unit tests verify that on a "REVIEW PASS — no issues" primary output, the classifier returns `critical_count: 0`.
2. **Classifier cost.** Every review gate run incurs an extra Sonnet call. At ~5-20k input tokens and ~500 output tokens, cost is well under $0.01 per call. Directive flag provides an off switch.
3. **Classifier latency.** Adds ~5-15 seconds per review gate run on the fallback path. Not a concern for human-scale orchestration (a single change already takes 5-10 minutes).
4. **False positives.** The classifier might classify a warning as critical. Mitigation: the fast-path is tried FIRST and only triggers the classifier when it finds zero issues. If the fast-path sees a `[MEDIUM]` or `[LOW]` finding, the classifier is not invoked, so its opinion cannot override a correctly-classified low-severity finding.
5. **Rollback.** If the classifier misbehaves in production, the directive flag disables it immediately. The fast-path alone is the pre-fix behavior, so disabling the classifier returns to the known-buggy-but-usable state while a fix lands.
