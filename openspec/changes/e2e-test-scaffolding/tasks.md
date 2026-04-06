## 1. Core — Scaffold Generator (`lib/set_orch/test_scaffold.py`)

- [ ] 1.1 Create `test_scaffold.py` with `generate_skeleton(test_plan_entries, change_name, worktree_path, profile) -> tuple[str, int]`. Groups entries by `req_id`, calls `profile.render_test_skeleton()`, writes file, returns `(path, test_count)`.
- [ ] 1.2 Group logic: collect entries by `req_id`, sort REQs alphabetically. Each REQ group becomes a `test.describe` block. Entries within group become `test()` blocks.
- [ ] 1.3 Skip generation if `test_plan_entries` is empty. Skip if spec file already exists in worktree (redispatch safety).

## 2. Web Module — Playwright Skeleton Renderer

- [ ] 2.1 Add `render_test_skeleton(entries: list, change_name: str) -> str` method to `WebProjectType` in `modules/web/set_project_web/project_type.py`.
- [ ] 2.2 Output format: Playwright imports, `test.describe` per REQ, `test()` per entry with `// TODO: implement` body. Smoke entries get `{ tag: '@smoke' }`.
- [ ] 2.3 Include header comment: `// AUTO-GENERATED from test-plan.json — fill test bodies, do not delete test blocks`

## 3. Core ABC — Profile Method

- [ ] 3.1 Add `render_test_skeleton(entries, change_name) -> str` to `ProjectType` ABC in `profile_types.py` with default returning `""` (no-op for profiles without E2E).

## 4. Dispatcher Integration

- [ ] 4.1 In `dispatcher.py`, after writing input.md: if `test_plan_entries` and profile has `render_test_skeleton`, call `generate_skeleton()`. Log result at INFO.
- [ ] 4.2 Skip if spec file already exists in worktree (redispatch preserves agent work).
- [ ] 4.3 Update Required Tests section in input.md to reference the skeleton: "Test skeleton already created at tests/e2e/<name>.spec.ts — fill the // TODO blocks."

## 5. Task Rewriting

- [ ] 5.1 After skeleton generation, post-process `tasks.md` in the worktree: find lines matching `tests/e2e/` or `Create.*spec.ts` or section headers like `## N. E2E Tests`.
- [ ] 5.2 Replace matched E2E task lines with single: `"- [ ] Fill test bodies in tests/e2e/<name>.spec.ts (<count> test blocks marked // TODO: implement)"`
- [ ] 5.3 Preserve non-E2E tasks and section structure.

## 6. TODO Count Warning (optional)

- [ ] 6.1 In `merger.py`, before E2E gate: read the spec file, count `// TODO: implement` occurrences. If > 0, log WARNING with count.

## 7. Model Routing — Sonnet for Safe Phases

### 7a. Fix overrides that block sonnet

- [x] 7.1 `dispatcher.py` L623-629: the sonnet guard (`overriding planner model=sonnet → opus for code change`) blocks ALL code changes. Add exception: allow sonnet when change has `has_test_skeleton=True` or when `change_type` is not `"feature"` (infrastructure, cleanup).
- [x] 7.2 `templates.py` L382-386: update planner model suggestion to allow sonnet for E2E-fill tasks and S-complexity non-feature changes. Change "sonnet ONLY for doc-only" to include E2E skeleton fill.
- [x] 7.3 `engine.py` L65: change `review_model` default from `"opus"` to `"sonnet"` — code review is checklist-based pattern matching, sonnet handles it well. Also added `digest_model` and `investigation_model` directives with sonnet defaults.

### 7b. Add sonnet to phases that don't have model param

- [x] 7.4 `issues/investigator.py` L69: add `"--model", "sonnet"` to the claude spawn command. ISS investigation is log reading + diagnosis — sonnet is sufficient.
- [x] 7.5 `engine.py`: add `digest_model: str = "sonnet"` and `investigation_model: str = "sonnet"` to Directives dataclass. Parse from directives.json.
- [x] 7.6 Digest model: already flows via CLI `--model` param from sentinel. Directive exists for user override.

### 7c. Directive-level control

- [x] 7.7 Directives dataclass supports `review_model`, `digest_model`, `investigation_model` — all parsed from directives.json, all default to sonnet, all overridable to opus.

## 8. Dashboard — LLM Call Log Table (Tokens tab)

- [ ] 8.1 API: add `GET /api/{project}/llm-calls` endpoint that reads Claude session JSONL files + orchestration events to build a chronological list of all LLM calls: `[{timestamp, purpose, model, change, input_tokens, output_tokens, cache_tokens, duration_ms}]`.
- [ ] 8.2 Web: in the Tokens tab (`TokenChart.tsx`), below the existing bar chart, add a sortable table: columns = Time, Purpose, Model, Change, Input, Output, Cache, Duration. Each row = one LLM call.
- [ ] 8.3 Parse LLM calls from: (a) `run_claude_logged` entries in python.log (purpose=digest/decompose/review/replan), (b) Ralph agent session files (purpose=implementation), (c) ISS investigation/fix sessions.
- [ ] 8.4 Color-code model column: opus=blue, sonnet=green, haiku=gray — so it's immediately visible which calls used which model.
