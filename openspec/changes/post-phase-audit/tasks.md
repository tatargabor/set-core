## Tasks

### 1. New auditor.sh module

- [x] Create `lib/orchestration/auditor.sh` with source guard and `source` of shared utils
- [x] Implement `build_audit_prompt()`: two modes — digest (requirements.json + coverage.json) and spec/brief (raw spec text). Include merged change names, scopes, and file lists (git log on main, max 50 files per change). Truncate spec to 30000 chars. Build input JSON and pipe through `wt-orch-core template audit --input-file -`.
- [x] Implement `run_post_phase_audit()`: emit `AUDIT_START` event. Call `build_audit_prompt()`, pipe to `run_claude` with review_model (sonnet default), parse JSON from output (same `extract_json_block` pattern as planner.sh). Store result in state `phase_audit_results[]` array (append, not overwrite) with cycle number, timestamp, model, duration_ms, input_tokens. Emit `AUDIT_GAPS` or `AUDIT_CLEAN` event. Export `_REPLAN_AUDIT_GAPS` with gap descriptions. Timeout 120s. On parse failure, store raw output as `phase_audit_raw` and log warning (no block).

### 2. Directive and default constant

- [x] In `bin/wt-orchestrate`, add `DEFAULT_POST_PHASE_AUDIT="true"` (after existing DEFAULT_ constants, ~line 66)
- [x] In `lib/orchestration/utils.sh` `parse_directives()` (~line 259), add `post_phase_audit` directive parsing (valid values: true, false). Follow the same pattern as `team_mode` (~line 544).
- [x] Source `auditor.sh` from `bin/wt-orchestrate` (alongside other lib sources, ~line 136-137)

### 3. Monitor loop integration

- [x] In `monitor.sh`, after phase-end E2E (~line 357-359) and before auto-replan check (~line 362), insert: if `post_phase_audit` is not `false`, call `run_post_phase_audit()`. Pass current replan cycle number.
- [x] In the terminal state path (`auto_replan=false`, ~line 436-451), if `post_phase_audit` is not `false`, call `run_post_phase_audit()` before `generate_report` and include gap summary in the completion log and email.
- [x] In the replan-no-new-work path (~line 391-405), same audit call before `generate_report`.
- [x] In the replan-exhausted path (~line 413-429), same audit call before `generate_report`.

### 4. Replan prompt integration

- [x] In `planner.sh` `render_planning_prompt()` replan_ctx handling (~templates.py line 436-469), add injection of `_REPLAN_AUDIT_GAPS`: if `replan_ctx.get("audit_gaps")` is non-empty, add section: "Post-phase audit found these implementation gaps — prioritize them in the next plan:" with the gap list.
- [x] In `monitor.sh` where `_REPLAN_E2E_FAILURES` is referenced (~line 901), also pass `_REPLAN_AUDIT_GAPS` into the replan_json.
- [x] In `planner.sh` `auto_replan_cycle()` (~line 1257), add `_REPLAN_AUDIT_GAPS` to the unset list (~line 1343-1346).

### 5. Audit prompt template (wt-orch-core)

- [x] Add `render_audit_prompt()` to `lib/wt_orch/templates.py`. Receives: `spec_text` OR `requirements[]`, `changes[]` with name/scope/status/file_list, `coverage` data, `mode` ("digest"/"spec"). Output format instructions: JSON with audit_result, gaps[], summary. Follow the same Python f-string pattern as `render_planning_prompt()`.
- [x] Register `audit` subcommand in `lib/wt_orch/cli.py` `cmd_template()` (~line 76-129): add `elif args.template_cmd == "audit":` dispatching to `templates.render_audit_prompt()`. Pass input_data fields.
- [x] Add argparse `audit` subparser in the template parser section of cli.py (follow existing proposal/review/fix/planning pattern).

### 6. Audit logging

- [x] In `run_post_phase_audit()`: log one-line summary to orchestration log ("Post-phase audit cycle N: X gaps (Y critical, Z minor) in Ns")
- [x] Write full audit prompt and raw LLM response to `wt/orchestration/audit-cycle-N.log` for debug
- [x] Emit events: `AUDIT_START` with `{cycle, mode: "digest"|"spec", model}`, `AUDIT_GAPS` with `{cycle, gap_count, critical_count, minor_count, duration_ms}` or `AUDIT_CLEAN` with `{cycle, duration_ms}`

### 7. HTML report section

- [x] In `reporter.sh`, add `render_audit_section()` function. Read `phase_audit_results[]` from state. For each entry: show result badge (gaps_found=red, clean=green), model, duration, gap table with severity color coding (critical=red bg, minor=yellow bg), spec reference, suggested scope.
- [x] Call `render_audit_section()` from `generate_report()` between `render_execution_section` and `render_coverage_section` (~line 16-17)
- [x] Add CSS classes: `.gap-critical { background: #4e2a2a; }`, `.gap-minor { background: #3a3a2a; }`, `.audit-clean { color: #4caf50; font-weight: bold; }`

### 8. Web dashboard AuditPanel

- [x] Create `web/src/components/AuditPanel.tsx`: read `phase_audit_results[]` from state (passed as prop). Show summary bar per cycle with gap count + severity badge. Gap table: ID, severity (color chip), description, spec reference, suggested scope. Clean state: green "All spec sections covered" banner. Multiple phases: collapsible accordion.
- [x] Integrate AuditPanel into `web/src/pages/Dashboard.tsx`: import and render inside the `top` section of `ResizableSplit`, after `ChangeTable` (~line 100-105). Only render if `phase_audit_results` exists and is non-empty in state. Add collapsible toggle button alongside Plan/Tokens buttons (~line 74-89).
- [x] Add `phase_audit_results` type to `web/src/lib/api.ts` `StateData` interface.

### 9. Test wiring

- [x] In `tests/test_wt_directory.sh`, add `DEFAULT_POST_PHASE_AUDIT` constant and verify `auditor.sh` exists in the directory structure test
- [x] In `tests/orchestrator/test-orchestrate-integration.sh`, add `DEFAULT_POST_PHASE_AUDIT` constant
- [x] Add unit test for `build_audit_prompt()` in spec mode (mock spec text, mock state with merged changes → verify prompt contains spec + change list)
- [x] Add unit test for `parse_audit_result()` (mock LLM JSON output → verify gap extraction)
