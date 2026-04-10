# Tasks: design-compliance-gate

## 1. Spike: verify Claude CLI vision support

- [ ] 1.1 Test whether `claude -p --output-format json` accepts image inputs via stdin or flag. If CLI mode doesn't support images, document fallback (Anthropic SDK direct call with API key from env) [REQ: gate-registration]
- [ ] 1.2 Benchmark cost: send 8 sample screenshots + design-system prompt to sonnet, record input/output tokens and dollar cost [REQ: sampling-strategy]
- [ ] 1.3 Verify vision verdict quality with 3 known-good and 3 known-bad screenshots (styled vs unstyled). Confirm the model distinguishes them reliably [REQ: llm-review-call]

## 2. Core: extend ProjectType with extra_gates() hook + named retry counters

- [ ] 2.1 In `lib/set_orch/profile_types.py`, add abstract method `extra_gates(self) -> list[GateDefinition]` to `ProjectType` ABC with default `return []` [REQ: gate-registration]
- [ ] 2.2 In `lib/set_orch/verifier.py` gate pipeline assembly (around the GateDefinition list), after declaring core gates call `profile.extra_gates()` and extend the list [REQ: gate-registration]
- [ ] 2.3 Verify with `NullProfile` that no-plugin case still works (empty extra_gates → unchanged pipeline) [REQ: non-web-project]
- [ ] 2.4 In `lib/set_orch/gate_runner.py` (or wherever `GateDefinition` is defined), add `retry_counter: str = "shared"` field. When a gate runs, look up `state.extras.get(f"{retry_counter}_retry_count", 0)` instead of always using `verify_retry_count` [REQ: retry-state-tracking]
- [ ] 2.5 On gate fail, increment the named counter: `state.extras[f"{retry_counter}_retry_count"] += 1`. For `retry_counter="shared"`, keep the existing behaviour writing to `verify_retry_count` (backwards compat) [REQ: retry-state-tracking]
- [ ] 2.6 Add unit test: two gates with different `retry_counter` values fail independently — their counters do not interfere [REQ: retry-counter-isolation]

## 3. Web module: design_compliance gate implementation

- [ ] 3.1 Create `modules/web/set_project_web/gates/__init__.py` if missing [REQ: gate-registration]
- [ ] 3.2 Create `modules/web/set_project_web/gates/design_compliance.py` with `execute_design_compliance_gate(state_file, change_name, wt_path, d, event_bus)` signature matching other gate executors [REQ: gate-registration]
- [ ] 3.3 Implement precondition check: e2e passed, design files exist, at least one PNG screenshot present. Return `("skipped", "reason")` if any fails [REQ: preconditions]
- [ ] 3.4 Implement screenshot sampling: walk configured dirs, group by parent, pick highest mtime per group, cap at max_screenshots [REQ: screenshot-sampling]
- [ ] 3.5 Build the LLM prompt: load design-system.md tokens, load design-brief.md page sections matching selected screenshots, construct JSON-output instruction [REQ: llm-review-call]
- [ ] 3.6 Invoke `run_claude_logged(prompt, purpose="design_compliance", model=config.model, timeout=config.timeout)` with image attachments [REQ: llm-review-call]
- [ ] 3.7 Parse JSON response; handle parse errors by returning `("skipped", "llm_parse_error")` — never fail the gate on LLM errors [REQ: llm-failure-handling]
- [ ] 3.8 Apply fail_on threshold logic (any | major | never) and return gate result [REQ: aggregation-and-verdict]
- [ ] 3.9 Persist findings to `.set/gates/design_compliance_findings.jsonl` and update state.extras [REQ: persistence]
- [ ] 3.10 On FAIL: build retry_context string from findings and update the change record [REQ: aggregation-and-verdict]

## 4. Web module: register gate in WebProjectType

- [ ] 4.1 In `modules/web/set_project_web/project_type.py`, override `extra_gates()` to return a single `GateDefinition` for design_compliance with position="after:e2e", extra_retries=0 [REQ: gate-registration]
- [ ] 4.2 Import `execute_design_compliance_gate` lazily inside the method to avoid import-time circular dependencies [REQ: gate-registration]

## 5. Config: directives schema + template

- [ ] 5.1 In `lib/set_orch/config.py`, add `design_compliance` schema entry (dict with keys: enabled, model, max_screenshots, fail_on, max_retries, timeout, screenshot_dirs) and defaults [REQ: configuration]
- [ ] 5.2 In `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml`, add a commented `design_compliance:` block showing defaults and fail_on options [REQ: configuration]
- [ ] 5.3 In `lib/set_orch/engine.py` parse_directives, route design_compliance sub-keys into the directives struct so gates can read them [REQ: configuration]

## 6. State: add design_compliance fields

- [ ] 6.1 In `lib/set_orch/state.py`, add `design_compliance_result: Optional[str] = None` and `gate_design_compliance_ms: int = 0` to Change dataclass [REQ: persistence]
- [ ] 6.2 Named retry counters go into `state.extras` as `{counter_name}_retry_count` — no new dataclass field needed for this, but verify the extras persist across save/load cycles [REQ: retry-state-tracking]
- [ ] 6.3 In `lib/set_orch/api/orchestration.py`, expose `design_compliance_result`, `gate_design_compliance_ms`, and `design_retry_count` (from extras) in ChangeInfo response [REQ: web-dashboard-exposure]

## 7. Web dashboard: GateBar + findings view

- [ ] 7.1 In `web/src/lib/api.ts`, add `design_compliance_result` and `gate_design_compliance_ms` to ChangeInfo type [REQ: web-dashboard-exposure]
- [ ] 7.2 In `web/src/components/GateBar.tsx`, add gate definition `{ name: 'design', status: design_compliance_result }` with label 'D' positioned between 'E' and 'R' [REQ: web-dashboard-exposure]
- [ ] 7.3 Add `skipped: 'bg-neutral-800 text-neutral-500'` style if not present [REQ: web-dashboard-exposure]
- [ ] 7.4 (Optional) Create `web/src/components/issues/DesignFindingsView.tsx` — modal listing findings with screenshot thumbnails, opened when clicking the D gate icon [REQ: web-dashboard-exposure]

## 8. Tests

- [ ] 8.1 Unit test for screenshot sampling: create a fake test-results tree with multiple groups and assert N selected files [REQ: screenshot-sampling]
- [ ] 8.2 Unit test for fail_on threshold logic: table-driven test with combinations of WARN/FAIL counts and fail_on modes [REQ: aggregation-and-verdict]
- [ ] 8.3 Integration test: run gate against a fixture worktree with a known-unstyled page and a known-styled page, assert correct verdicts (uses real LLM call — marked as slow/optional) [REQ: llm-review-call]
- [ ] 8.4 E2E test in the next craftbrew run: verify the D icon appears in GateBar and findings modal opens [REQ: web-dashboard-exposure]

## 9. Validation

- [ ] 9.1 Run the gate manually in craftbrew-run-20260409-0034 after it completes — does it catch the globals.css missing issue? [REQ: aggregation-and-verdict]
- [ ] 9.2 Measure cost on a real run (8 screenshots × sonnet) and document in the design doc [REQ: sampling-strategy]
- [ ] 9.3 Verify gate skips cleanly on a non-web project (e.g., set-core itself has no e2e screenshots) [REQ: non-web-project]
