## 1. Watchdog — Python migration

- [x] 1.1 Port `watchdog_check()` full pipeline to `watchdog.py`: init state, activity detection, action hash computation (hashlib.md5), timeout check, and return structured result
- [x] 1.2 Port action hash ring buffer logic to `watchdog.py`: ring append, consecutive duplicate detection, grace period for missing loop-state.json
- [x] 1.3 Port `_watchdog_check_progress()` spinning detection to `watchdog.py`: 3+ iterations without commits trend analysis
- [x] 1.4 Port `_watchdog_escalate()` chain (L1=warn, L2=resume, L3=redispatch, L4=fail) and `_watchdog_salvage_partial_work()` to `watchdog.py`
- [x] 1.5 Port `watchdog_heartbeat()` to emit WATCHDOG_HEARTBEAT via `events.emit()`
- [x] 1.6 Wire `set-orch-core watchdog check` CLI subcommand to call new Python functions (extend existing cli.py cmd_watchdog)
- [x] 1.7 Reduce `watchdog.sh` to thin wrapper: source guard + `set-orch-core watchdog check "$@"`

## 2. Builder — Python migration

- [x] 2.1 Port `check_base_build()` to `builder.py`: package manager detection (npm/pnpm/yarn/bun), build script lookup, execution, session-level caching
- [x] 2.2 Port `fix_base_build_with_llm()` to `builder.py`: sonnet→opus escalation via `subprocess_utils.run_claude()`, non-blocking return
- [x] 2.3 Wire `set-orch-core build check` CLI subcommand to call new Python functions (extend existing cli.py cmd_build)
- [x] 2.4 Reduce `builder.sh` to thin wrapper: source guard + `set-orch-core build check "$@"`

## 3. Auditor — Python migration

- [x] 3.1 Port `build_audit_prompt()` to `auditor.py` as `build_audit_input()`: construct JSON input from state (merged changes, scopes, requirements, git diff-tree data), support spec vs digest mode
- [x] 3.2 Port `parse_audit_result()` to `auditor.py`: extract JSON from Claude response, classify findings by severity (critical/minor), handle parse failures gracefully
- [x] 3.3 Port `run_post_phase_audit()` to `auditor.py`: full pipeline (build input → call Claude via run_claude → parse → update state with `_REPLAN_AUDIT_GAPS` context), non-blocking on failure
- [x] 3.4 Wire `set-orch-core audit run` CLI subcommand (extend existing cli.py cmd_audit)
- [x] 3.5 Reduce `auditor.sh` to thin wrapper: source guard + `set-orch-core audit run "$@"`

## 4. Planner orchestration — Python migration

- [x] 4.1 Port `cmd_plan()` orchestration to `planner.py` as `run_plan()`: digest freshness check, triage gate, design bridge setup, directives resolution, Claude decomposition call, JSON extraction/validation, coverage mapping
- [x] 4.2 Port `plan_via_agent()` to `planner.py`: worktree creation via subprocess (wt-new), Ralph loop dispatch with decomposition skill
- [x] 4.3 Port remaining helper functions: `find_project_knowledge_file()`, `estimate_tokens()` (or remove if unused)
- [x] 4.4 Wire `set-orch-core plan run` CLI subcommand (extend existing cli.py cmd_plan)
- [x] 4.5 Reduce `planner.sh` to thin wrapper: `cmd_plan()` → `set-orch-core plan run "$@"`, keep `cmd_replan()` if it still delegates separately

## 5. Digest pipeline — Python migration

- [x] 5.1 Port `scan_spec_directory()` to `digest.py`: directory walking, file classification (spec/config/brief), content hashing
- [x] 5.2 Port `check_digest_freshness()` to `digest.py`: hash comparison against last digest, skip logic
- [x] 5.3 Port `build_digest_prompt()` and `call_digest_api()` to `digest.py`: prompt construction from scanned files, Claude API invocation via run_claude, JSON response parsing
- [x] 5.4 Port `write_digest_output()` to `digest.py`: write index.json, requirements.json, and other output files
- [x] 5.5 Port `validate_digest()` and `stabilize_ids()` to `digest.py`: digest validation logic and requirement ID generation
- [x] 5.6 Port triage pipeline to `digest.py`: `generate_triage_md()`, `parse_triage_md()`, `merge_triage_to_ambiguities()`, `merge_planner_resolutions()`
- [x] 5.7 Port coverage functions to `digest.py`: `populate_coverage()`, `check_coverage_gaps()`, `update_coverage_status()`
- [x] 5.8 Port `cmd_digest()` orchestration to `digest.py` as `run_digest()`: full pipeline entry point
- [x] 5.9 Wire `set-orch-core digest run` CLI subcommand (extend existing cli.py cmd_digest)
- [x] 5.10 Reduce `digest.sh` to thin wrapper: source guard + `set-orch-core digest run "$@"`

## 6. Cleanup and validation

- [x] 6.1 Verify all 5 bash files are thin wrappers (< 20 lines of active code each)
- [x] 6.2 Remove all inline `python3 -c` snippets from bash files
- [x] 6.3 Remove dead bash functions that are no longer called
- [x] 6.4 Verify `set-orch-core` CLI help shows all new subcommands
- [x] 6.5 Run a test orchestration to validate end-to-end behavior
