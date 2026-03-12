## Tasks

### 1. New auditor.sh module

- [ ] Create `lib/orchestration/auditor.sh` with source guard and `source` of shared utils
- [ ] Implement `build_audit_prompt()`: two modes — digest (requirements.json + coverage.json) and spec/brief (raw spec text). Include merged change names, scopes, and file lists (git log, max 50 files per change). Truncate spec to 30000 chars.
- [ ] Implement `run_post_phase_audit()`: call `build_audit_prompt()`, pipe to `run_claude` with review_model, parse JSON from output (same `extract_json_block` pattern as planner.sh). Store result in state as `phase_audit_result`. Emit `AUDIT_GAPS` event if gaps found. Export `_REPLAN_AUDIT_GAPS` with gap descriptions. Timeout 120s. On parse failure, store raw output as `phase_audit_raw` and log warning (no block).

### 2. Directive and default constant

- [ ] In `bin/wt-orchestrate`, add `DEFAULT_POST_PHASE_AUDIT="auto"` (meaning: true when auto_replan=true, false otherwise)
- [ ] In `lib/orchestration/utils.sh` `parse_directives()`, add `post_phase_audit` directive parsing (valid values: true, false, auto)
- [ ] In `lib/orchestration/monitor.sh`, read `post_phase_audit` from directives and resolve `auto` to true/false based on `auto_replan` value

### 3. Monitor loop integration

- [ ] In `monitor.sh`, after phase-end E2E (~line 354-356) and before auto-replan check (~line 358), insert: if `post_phase_audit` is true, call `run_post_phase_audit()`
- [ ] In the terminal state path (auto_replan=false, ~line 433-443), if `post_phase_audit` is true, call `run_post_phase_audit()` and include gap summary in the completion log

### 4. Replan prompt integration

- [ ] In `planner.sh` `auto_replan_cycle()`, after the existing `_REPLAN_E2E_FAILURES` injection (~line 1576-1583), add injection of `_REPLAN_AUDIT_GAPS` with header: "Post-phase audit found these implementation gaps — prioritize them in the next plan:"
- [ ] In the plan prompt template (wherever `_REPLAN_COMPLETED` is consumed), add a section for audit gaps that instructs: "Create dedicated changes for each critical gap. Minor gaps may be folded into related changes."

### 5. Source and test wiring

- [ ] Source `auditor.sh` from `bin/wt-orchestrate` (alongside other lib files)
- [ ] In `tests/test_wt_directory.sh`, add `DEFAULT_POST_PHASE_AUDIT` and verify `auditor.sh` exists in the directory structure test
- [ ] In `tests/orchestrator/test-orchestrate-integration.sh`, add `DEFAULT_POST_PHASE_AUDIT` constant
