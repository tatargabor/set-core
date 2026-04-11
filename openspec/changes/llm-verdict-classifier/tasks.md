# Tasks

## 1. New module — LLM verdict classifier helper

- [ ] 1.1 Create `lib/set_orch/llm_verdict.py` with a `ClassifierResult` dataclass: `verdict: str` (pass|fail), `critical_count: int`, `high_count: int`, `medium_count: int`, `low_count: int`, `findings: list[dict]`, `raw_json: dict`, `error: str | None`, `elapsed_ms: int` [REQ: Review gate verdict is format-agnostic]
- [ ] 1.2 Implement `classify_verdict(primary_output, schema, *, model="sonnet", purpose="", timeout=120) -> ClassifierResult`. Build the classifier prompt from schema + primary_output using `<<<BEGIN OUTPUT>>>` / `<<<END OUTPUT>>>` delimiters. Invoke `run_claude_logged` with `--output-format text` (classifier returns raw JSON, not tool use) [REQ: Review gate verdict is format-agnostic]
- [ ] 1.3 Parse the classifier response as JSON. If it is wrapped in markdown fences, strip them. If it contains preamble before the `{`, extract the JSON object by brace-matching (reuse the existing helper in `planner.py` if available, or implement a minimal version) [REQ: Review gate verdict is format-agnostic]
- [ ] 1.4 Validate required fields against the schema. Missing required fields → return fail-safe ClassifierResult with `verdict="fail"`, `critical_count=1`, `error="missing_field: <name>"` [REQ: Review gate verdict is format-agnostic]
- [ ] 1.5 On any exception (timeout, non-zero exit, JSON decode error) return a fail-safe ClassifierResult with `verdict="fail"`, `critical_count=1`, `error=<reason>`. Log WARNING with purpose and reason [REQ: Review gate verdict is format-agnostic]
- [ ] 1.6 Emit `CLASSIFIER_CALL` event on every invocation with fields `purpose`, `primary_output_bytes`, `verdict`, `critical_count`, `elapsed_ms`, `error`. Use the existing `event_bus.emit()` pattern; accept an optional `event_bus` parameter on `classify_verdict()` [REQ: Review gate verdict is format-agnostic]
- [ ] 1.7 Add module-level schemas: `REVIEW_SCHEMA`, `INVESTIGATOR_SCHEMA`, `SPEC_VERIFY_SCHEMA`. Each is a dict literal suitable for JSON-dumping into the classifier prompt. Document the expected severities and field names in a module docstring [REQ: Review gate verdict is format-agnostic]

## 2. Directives — rollout flag

- [ ] 2.1 Add `llm_verdict_classifier_enabled: bool = True` to the `Directives` dataclass in `lib/set_orch/engine.py`, near the other boolean gate flags (around `integration_smoke_blocking`) [REQ: Review gate verdict is format-agnostic]
- [ ] 2.2 Add `d.llm_verdict_classifier_enabled = _bool(raw, "llm_verdict_classifier_enabled", d.llm_verdict_classifier_enabled)` to `parse_directives` [REQ: Review gate verdict is format-agnostic]
- [ ] 2.3 Document the new directive in the template `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` as a commented-out option with a brief explanation of what it controls [REQ: Review gate verdict is format-agnostic]

## 3. Review gate refactor

- [ ] 3.1 In `lib/set_orch/verifier.py` `review_change()` (around line 1320-1332), remove the `re.search(r"REVIEW\s+PASS", review_output)` early-exit block entirely [REQ: Review gate no longer short-circuits on REVIEW PASS regex]
- [ ] 3.2 After the existing `_parse_review_issues` call, if `has_critical is False` AND `len(review_output) >= 500` AND the directive `llm_verdict_classifier_enabled` is True: invoke `classify_verdict` with `REVIEW_SCHEMA`, `purpose="review"`. [REQ: Review gate verdict is format-agnostic]
- [ ] 3.3 If the classifier returns `critical_count > 0` with `error is None`: override `has_critical=True`, override the `parsed_issues` list with the classifier-reported findings, log an ERROR line identifying that the classifier caught issues the fast-path missed. The ERROR line includes the first finding summary as the "pattern" for future fast-path hardening [REQ: Review gate verdict is format-agnostic]
- [ ] 3.4 If the classifier returns `critical_count == 0` with `error is None`: keep `has_critical=False` (both paths agree, safe to pass). Log INFO "review classifier confirmed 0 critical findings" [REQ: Review gate verdict is format-agnostic]
- [ ] 3.5 If the classifier returns with `error is not None`: log WARNING, keep `has_critical=False` (backward compat — fast-path already said clean, classifier error is "no new info") [REQ: Review gate verdict is format-agnostic]
- [ ] 3.6 In `_parse_review_issues` (around verifier.py:152), remove any severity source other than the inline `[TAG]` prefix check. Audit for any body-scan or summary-scan logic that contributes to severity; delete it [REQ: Review gate severity has a single source of truth]
- [ ] 3.7 Read the directive via `state.extras.get("directives", {}).get("llm_verdict_classifier_enabled", True)` or pass it through from the gate executor — pick the path that matches the existing pattern for `integration_smoke_blocking` [REQ: Review gate verdict is format-agnostic]

## 4. Investigator refactor

- [ ] 4.1 In `lib/set_orch/issues/investigator.py` `_parse_proposal` (around line 190), add an initial scan for explicit sentinels: `**Impact:** (low|medium|high)`, `**Fix-Scope:** (single_file|multi_file|config_override)`, `**Target:** (framework|consumer|both)`, `**Confidence:** (0-100|0\.[0-9]+|1\.0)` [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 4.2 For each sentinel found, use the sentinel value and skip the heuristic for that field [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 4.3 If any field is missing after the sentinel scan AND the classifier is enabled: invoke `classify_verdict` with `INVESTIGATOR_SCHEMA`, `purpose="investigator"`. Merge the classifier output into the missing fields [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 4.4 If the classifier errors out, fall through to the existing keyword heuristics (`if "critical" in lines` etc.) AND reduce `confidence` by 0.1 to reflect the degraded extraction path [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 4.5 Replace the `if "critical" in lines` substring matching with word-boundary matching using `re.search(r"\bcritical\b", …)` so that "criticality" and "not critical" do not trigger. Same for `"minor"`, `"blocker"`, etc. [REQ: Investigator keyword heuristics no longer trigger on word-substring matches]
- [ ] 4.6 Unit test: word "criticality" in the proposal body does NOT upgrade impact to high when classifier is disabled [REQ: Investigator keyword heuristics no longer trigger on word-substring matches]

## 5. Spec-verify classifier fallback

- [ ] 5.1 In `lib/set_orch/verifier.py` `_execute_spec_verify_gate` (around line 2478), locate the "no sentinel" branch — currently it passes with `[ANOMALY]` WARNING [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 5.2 When `llm_verdict_classifier_enabled` is True AND the sentinel is absent: invoke `classify_verdict` with `SPEC_VERIFY_SCHEMA`, `purpose="spec_verify_fallback"` [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 5.3 If the classifier returns `critical_count == 0`: pass with a WARNING log noting the sentinel was missing but the classifier confirmed no critical findings [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 5.4 If the classifier returns `critical_count > 0`: fail, build a retry context from the classifier's finding list [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 5.5 If the classifier errors out: fail closed (no sentinel AND no classifier verdict means no trustworthy signal) [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 5.6 When `llm_verdict_classifier_enabled` is False: preserve the old behavior (pass with `[ANOMALY]` WARNING) [REQ: Spec-verify gate has classifier fallback when sentinel missing]

## 6. Unit tests — classifier helper

- [ ] 6.1 Create `tests/unit/test_llm_verdict.py` with standard imports and a `FakeClaudeResult` helper that returns a `CommandResult` with the specified stdout [REQ: Review gate verdict is format-agnostic]
- [ ] 6.2 `test_classify_verdict_happy_path`: mock `run_claude_logged` to return `{"verdict": "pass", "critical_count": 0, "findings": []}`. Assert `ClassifierResult.verdict == "pass"`, `critical_count == 0`, `error is None` [REQ: Review gate verdict is format-agnostic]
- [ ] 6.3 `test_classify_verdict_critical_findings`: mock to return `{"verdict": "fail", "critical_count": 3, "findings": [{"severity": "CRITICAL", ...}, ...]}`. Assert `critical_count == 3` and findings list is 3 items [REQ: Review gate verdict is format-agnostic]
- [ ] 6.4 `test_classify_verdict_json_in_fences`: mock returns `` ```json\n{...}\n``` ``. Assert the fence stripping logic extracts the JSON and parses it [REQ: Review gate verdict is format-agnostic]
- [ ] 6.5 `test_classify_verdict_preamble_before_json`: mock returns `"Here is the JSON:\n{...}"`. Assert brace-matching extracts it [REQ: Review gate verdict is format-agnostic]
- [ ] 6.6 `test_classify_verdict_timeout_fail_safe`: mock to raise TimeoutError. Assert `ClassifierResult.verdict == "fail"`, `critical_count == 1`, `error is not None` [REQ: Review gate verdict is format-agnostic]
- [ ] 6.7 `test_classify_verdict_invalid_json_fail_safe`: mock returns `"not json at all"`. Assert fail-safe result with `error="json_decode_error"` [REQ: Review gate verdict is format-agnostic]
- [ ] 6.8 `test_classify_verdict_missing_required_field_fail_safe`: mock returns `{"verdict": "pass"}` (no critical_count). Assert fail-safe result with `error="missing_field: critical_count"` [REQ: Review gate verdict is format-agnostic]

## 7. Unit tests — review gate regression fossils

- [ ] 7.1 Create `tests/unit/fixtures/review_output_micro_create_task_2026_04_11.txt` containing the full review_output text from `/home/tg/demo/micro/set/orchestration/python.log` lines 5169-5181, starting with `## Retry Review — Verifying 3 Previous Findings` and including all three NOT_FIXED findings and the summary line [REQ: Review gate verdict is format-agnostic]
- [ ] 7.2 Create `tests/unit/fixtures/review_output_minishop_0410_product_catalog_attempt4.txt` containing the review output from minishop_0410 attempt 4 (lines 3811-3821 of its python.log), including the `### Finding 5` header + `**REVIEW BLOCKED** — 1 unique critical issue remains` [REQ: Review gate verdict is format-agnostic]
- [ ] 7.3 Create `tests/unit/fixtures/review_output_first_round_inline_format.txt` containing a synthetic first-round review with `ISSUE: [CRITICAL]` inline format to exercise the fast-path [REQ: Review gate verdict is format-agnostic]
- [ ] 7.4 `test_review_gate_silent_pass_fossil_micro`: load the micro fixture, mock the classifier to return `critical_count: 3`, call `review_change()` with a monkeypatched `_parse_review_issues` (which returns 0 findings) AND a monkeypatched `classify_verdict`. Assert `has_critical == True` (classifier overrode) [REQ: Review gate verdict is format-agnostic]
- [ ] 7.5 `test_review_gate_silent_pass_fossil_minishop`: same pattern with the minishop fossil. Assert `has_critical == True` [REQ: Review gate verdict is format-agnostic]
- [ ] 7.6 `test_review_gate_first_round_fast_path_still_works`: load the inline-format fixture, DO NOT mock the classifier. Assert the fast-path finds the CRITICAL issue and the classifier is NOT invoked [REQ: Review gate verdict is format-agnostic]
- [ ] 7.7 `test_review_gate_removes_review_pass_regex`: a review output containing `The previous review said "REVIEW PASS" but I now find 2 new CRITICAL issues: ISSUE: [CRITICAL] blah`. Assert the fast-path detects the new CRITICAL and the gate returns FAIL (not PASS on the quoted phrase) [REQ: Review gate no longer short-circuits on REVIEW PASS regex]
- [ ] 7.8 `test_review_gate_severity_single_source`: a review with `ISSUE: [LOW]` where the summary body contains the word "critical". Assert `severity == "LOW"` (inline tag wins) [REQ: Review gate severity has a single source of truth]

## 8. Unit tests — investigator

- [ ] 8.1 `test_investigator_sentinels_preferred`: proposal.md with `**Impact:** high` + `**Fix-Scope:** config_override` + `**Target:** framework`. Assert classifier is NOT invoked, Diagnosis has those exact values [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 8.2 `test_investigator_missing_sentinels_uses_classifier`: proposal.md without sentinels, classifier mocked to return `{"impact": "high", "fix_scope": "multi_file", "fix_target": "framework", "confidence": 0.8}`. Assert Diagnosis matches classifier output [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 8.3 `test_investigator_classifier_error_fallback_heuristic`: proposal.md without sentinels, classifier raises TimeoutError, body contains "critical issue". Assert keyword heuristic runs, `impact == "high"`, `confidence` reduced by 0.1 [REQ: Investigator diagnosis uses sentinels then classifier fallback]
- [ ] 8.4 `test_investigator_word_boundary_matching`: proposal.md without sentinels, classifier disabled, body contains the word "criticality" (not "critical"). Assert `impact != "high"` (word-boundary match does NOT trip) [REQ: Investigator keyword heuristics no longer trigger on word-substring matches]

## 9. Unit tests — spec-verify fallback

- [ ] 9.1 `test_spec_verify_missing_sentinel_classifier_pass`: mock primary verify output with no sentinel, classifier returns `critical_count: 0`. Assert gate passes with WARNING log [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 9.2 `test_spec_verify_missing_sentinel_classifier_fail`: mock primary verify output with no sentinel, classifier returns `critical_count: 2`. Assert gate fails and retry_context lists the classifier findings [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 9.3 `test_spec_verify_missing_sentinel_classifier_error_fails_closed`: classifier raises TimeoutError. Assert gate FAILS (no trustworthy signal) [REQ: Spec-verify gate has classifier fallback when sentinel missing]
- [ ] 9.4 `test_spec_verify_classifier_disabled_keeps_anomaly_pass`: directive is False, no sentinel. Assert gate passes with `[ANOMALY]` WARNING (old behavior) [REQ: Spec-verify gate has classifier fallback when sentinel missing]

## 10. Regression check

- [ ] 10.1 Run `pytest tests/unit/test_llm_verdict.py tests/unit/test_verifier.py tests/unit/test_investigator.py` — all new tests pass
- [ ] 10.2 Run the full `pytest tests/unit/` (excluding the 3 known-broken web-api collection errors) and confirm no new regressions compared to the pre-change baseline
- [ ] 10.3 Grep `lib/set_orch/` for any remaining `re.search.*PASS|re.search.*FAIL|if.*critical.*in.*lines|startswith..ISSUE` outside of `_parse_review_issues` and document any intentional exceptions in code comments

## 11. Documentation

- [ ] 11.1 Add an entry to `docs/` explaining when to call the classifier and when a sentinel is sufficient. Reference the two silent-pass incidents as motivation
- [ ] 11.2 Update `.claude/rules/code-quality.md` or the equivalent rule file to forbid future body-regex heuristics on LLM verdict text — redirect contributors to `llm_verdict.classify_verdict`

## 12. Deploy + validation

- [ ] 12.1 Commit all code + tests in a single commit with reference to the two silent-pass incidents as motivation
- [ ] 12.2 Redeploy to ~/demo/micro via file copy (sentinel.md + llm_verdict.py + verifier.py + investigator.py + engine.py all need to be picked up on restart)
- [ ] 12.3 Reset the micro state (if it still has the corrupt create-task merge state) or start a fresh init
- [ ] 12.4 Start the sentinel and monitor via cron. Watch for CLASSIFIER_CALL events + any ERROR log lines indicating classifier-override hits
- [ ] 12.5 Confirm all three changes (foundation, create-task, mark-done) merge cleanly with 0 silent-pass incidents
- [ ] 12.6 If any classifier false positive is observed, capture the review output and add it as a new fixture, tune the classifier prompt, re-test
