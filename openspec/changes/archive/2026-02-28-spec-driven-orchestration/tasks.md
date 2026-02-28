## 1. CLI Argument Parsing

- [x] 1.1 Add `--spec <path>` flag to argument parser in `wt-orchestrate` (alongside existing `--brief`)
- [x] 1.2 Add `--phase <hint>` flag — accepts number or string, only valid with `--spec`
- [x] 1.3 Add `--max-parallel <N>` flag as CLI directive override
- [x] 1.4 Update `usage()` help text to document new flags with examples

## 2. Input Discovery

- [x] 2.1 Create `find_input()` function that returns both the file path and the input mode (`spec` or `brief`)
- [x] 2.2 Implement resolution order: `--spec` → `--brief` → auto-detect `project-brief.md` → `project.md` fallback → error
- [x] 2.3 In auto-detect: check if brief has `### Next` items — if yes use brief mode, if no exit with helpful error suggesting `--spec`
- [x] 2.4 Replace `find_brief()` call in main flow with `find_input()`, preserve backward compat

## 3. Orchestration Config File

- [x] 3.1 Add `load_config_file()` function that reads `.claude/orchestration.yaml` using `python3 -c 'import yaml; ...'`
- [x] 3.2 Add validation: check types, ranges, enum values for each directive key — warn on unknown keys
- [x] 3.3 Add `resolve_directives()` function implementing the 4-level precedence chain: CLI flags > yaml config > in-document directives > defaults
- [x] 3.4 Replace direct `parse_directives()` usage in `generate_plan()` with `resolve_directives()` output

## 4. Spec Summarization

- [x] 4.1 Add `estimate_tokens()` function: `wc -w` × 1.3, returns integer
- [x] 4.2 Add `summarize_spec()` function: calls `claude -p` with a summarization prompt that outputs TOC + status + relevant section (target ~4k tokens output)
- [x] 4.3 Integrate into `generate_plan()`: if spec mode AND tokens > 8000, run summarization before decomposition

## 5. Decomposition Prompt Rewrite

- [x] 5.1 Create spec-mode prompt template: instructs Claude to (a) identify completed items via status markers, (b) determine next batch, (c) decompose into changes — with `phase_detected` and `reasoning` fields in JSON output
- [x] 5.2 Inject `--phase` hint into prompt when provided: "The user requested phase: <hint>. Focus on this phase."
- [x] 5.3 Keep existing brief-mode prompt as-is — selected based on `input_mode` from `find_input()`
- [x] 5.4 Ensure both modes inject existing specs, active changes, and memory context into the prompt
- [x] 5.5 Update JSON extraction in `generate_plan()` to accept the extended output format (`phase_detected`, `reasoning`) without breaking existing `changes` parsing

## 6. State & Plan Metadata

- [x] 6.1 Add `input_mode` and `input_path` fields to `plan.json` metadata (alongside existing `brief_hash`, `plan_version`)
- [x] 6.2 Add `phase_detected` and `reasoning` to `plan.json` when available (spec mode)
- [x] 6.3 Display `phase_detected` in the plan approval output so the user can verify the right phase was selected

## 7. Template & Docs

- [x] 7.1 Update `openspec/project-brief.md.template` to add a comment mentioning `--spec` as an alternative
- [x] 7.2 Update `wt-orchestrate --help` output with usage examples for `--spec` and `--phase`

## 8. Tests

- [x] 8.1 Add test in `tests/orchestrator/` for `find_input()` — covers all resolution paths (--spec, --brief, auto-detect, error)
- [x] 8.2 Add test for `load_config_file()` — valid YAML, missing file, malformed YAML, unknown keys
- [x] 8.3 Add test for `resolve_directives()` — precedence chain with various combinations
- [x] 8.4 Add test for `estimate_tokens()` — verify word-to-token calculation
- [x] 8.5 Add sample spec file (`tests/orchestrator/sample-spec.md`) with phases, status markers, multi-language content for integration testing
- [x] 8.6 Add plan generation test with sample spec — verify `phase_detected` and `changes` in output
