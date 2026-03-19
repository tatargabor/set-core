## 1. Package Setup

- [x] 1.1 Create `lib/set_orch/__init__.py` with package docstring and version
- [x] 1.2 Create `bin/set-orch-core` CLI entry point with argparse subcommands (`process`, `state`, `template`) — initially just argument parsing and help text
- [x] 1.3 Add `set-orch-core` to `[project.scripts]` in pyproject.toml and add `psutil` to main dependencies
- [x] 1.4 Verify `set-orch-core --help` works and shows subcommands

## 2. Process Module

- [x] 2.1 Create `lib/set_orch/process.py` with `check_pid(pid, expected_cmdline_pattern)` using psutil with `/proc/cmdline` fast path and `kill -0` fallback
- [x] 2.2 Add `safe_kill(pid, expected_cmdline_pattern, timeout=10)` — SIGTERM → wait → verify identity → SIGKILL sequence, returning a KillResult dataclass
- [x] 2.3 Add `find_orphans(expected_pattern, known_pids)` — psutil process iteration with cmdline matching, fallback to `/proc/*/cmdline` scanning
- [x] 2.4 Wire `process` subcommands in `bin/set-orch-core`: `check-pid`, `safe-kill`, `find-orphans` — JSON output on stdout, exit codes per spec
- [x] 2.5 Create `tests/unit/test_process.py` — test check_pid (alive+match, alive+mismatch, dead), safe_kill (SIGTERM success, SIGKILL escalation, already dead), find_orphans (with/without matches)

## 3. State Module

- [x] 3.1 Create `lib/set_orch/state.py` with dataclasses: `Change`, `WatchdogState`, `TokenStats`, `OrchestratorState` — all fields matching current orchestration-state.json schema
- [x] 3.2 Add `load_state(path)` — JSON parse + dataclass deserialization with `StateCorruptionError` on invalid/corrupt JSON, unknown fields preserved in extras dict
- [x] 3.3 Add `save_state(state, path)` — serialize to JSON, atomic write via tempfile+rename in same directory, validate non-empty before rename
- [x] 3.4 Add `init_state(plan_file, output_path)` — replaces the 40-line jq filter in state.sh, reads plan JSON and transforms to state schema with all defaults
- [x] 3.5 Add `query_changes(state, status)` and `aggregate_tokens(state)` — typed query/aggregation replacing complex jq filters
- [x] 3.6 Wire `state` subcommands in `bin/set-orch-core`: `init`, `query`, `get` — JSON output on stdout
- [x] 3.7 Create `tests/unit/test_state.py` — test load/save round-trip, corrupt JSON rejection, init_state from plan fixture, query_changes filtering, aggregate_tokens, unknown field preservation

## 4. Template Module

- [x] 4.1 Create `lib/set_orch/templates.py` with `escape_for_prompt(text)` — neutralizes `$`, backtick, EOF markers in text destined for shell heredocs or Claude prompts
- [x] 4.2 Add `render_proposal(change_name, scope, roadmap_item, memory_ctx, spec_ref)` — replaces the 3 concatenated heredocs in dispatcher.sh (PROPOSAL_EOF, MEMORY_EOF, SPECREF_EOF)
- [x] 4.3 Add `render_review_prompt(scope, diff_output, req_section)` — replaces verifier.sh REVIEW_EOF heredoc, with truncation of diff_output at 50,000 characters
- [x] 4.4 Add `render_fix_prompt(change_name, scope, output_tail, smoke_cmd)` — replaces merger.sh SMOKE_FIX_EOF and verifier.sh SCOPED_FIX_EOF heredocs
- [x] 4.5 Add `render_planning_prompt(input_content, specs, memory, replan_ctx, mode="spec")` — replaces both the spec-mode heredoc (planner.sh:882-1074, PROMPT_EOF + 4 sub-heredocs) and the brief-mode heredoc (planner.sh:1078-1120, PROMPT_EOF + MEM_CTX)
- [x] 4.6 Wire `template` subcommands in `bin/set-orch-core`: `proposal`, `review`, `fix`, `planning` — stdout output, `--input-file -` for large args via stdin
- [x] 4.7 Create `tests/unit/test_templates.py` — test escape_for_prompt (dollar, backtick, EOF, passthrough), render_proposal (all fields, optional fields empty), render_review_prompt (special chars in diff), render_planning_prompt (replan vs initial)

## 5. Bash Migration — Process Operations

- [x] 5.1 Replace `kill -0 "$ralph_pid"` in dispatcher.sh (lines 232, 715, 866, 869, 1096) with `set-orch-core process check-pid` calls
- [x] 5.2 Replace `kill -0` in verifier.sh (lines 674, 746) with `set-orch-core process check-pid` calls
- [x] 5.3 Replace `kill -0` in watchdog.sh (lines 114, 132) with `set-orch-core process check-pid` calls
- [x] 5.4 Replace manual `kill -TERM; sleep 2; kill -0; kill -KILL` sequence in dispatcher.sh `redispatch_change()` (lines 866-872) with `set-orch-core process safe-kill` — note: `pause_change()` only has a bare `kill -TERM` (line 715) which stays as-is but gets identity verification via check-pid in task 5.1
- [x] 5.5 Replace `kill -0 "$ralph_pid"` guard in dispatcher.sh `recover_orphaned_changes()` (line 232) with `set-orch-core process check-pid` — note: the orphan recovery logic is state-based iteration, not process scanning, so `find-orphans` is not a fit here

## 6. Bash Migration — State Operations

- [x] 6.1 Replace `init_state()` jq filter in state.sh with `set-orch-core state init` call
- [x] 6.2 Replace compound state computation in monitor.sh `all_resolved` check (line ~348, combines truly_complete + failed + active counts) with `set-orch-core state query --summary` — individual status counts (`jq '[.changes[] | select(.status == "X")] | length'`) are simple filters and stay in bash per design — **SKIPPED: already clean bash arithmetic on simple jq counts, no Python migration needed**
- [x] 6.3 Replace watchdog nested jq reads (`.changes[].watchdog` subobject extraction) in watchdog.sh with `set-orch-core state get`

## 7. Bash Migration — Template Operations

- [x] 7.1 Replace 3 heredocs in dispatcher.sh `dispatch_change()` (PROPOSAL_EOF, MEMORY_EOF, SPECREF_EOF) with `set-orch-core template proposal`
- [x] 7.2 Replace REVIEW_EOF heredoc in verifier.sh with `set-orch-core template review`
- [x] 7.3 Replace SMOKE_FIX_EOF in merger.sh and SCOPED_FIX_EOF in verifier.sh with `set-orch-core template fix`
- [x] 7.4 Replace both planning prompt heredocs in planner.sh: spec-mode PROMPT_EOF (line 882, + 4 sub-heredocs) and brief-mode PROMPT_EOF (line 1078, + MEM_CTX sub-heredoc) with `set-orch-core template planning --mode spec|brief`

## 8. Integration Testing

- [x] 8.1 Create integration test: full init_state → load_state round-trip with a real plan.json fixture from production
- [x] 8.2 Create integration test: bash script calls `set-orch-core process check-pid` on own PID and verifies JSON output
- [x] 8.3 Create integration test: bash script calls `set-orch-core template proposal` and verifies output matches expected markdown structure
- [x] 8.4 Run existing orchestration test suite (`tests/unit/test_safe_jq.sh`, `tests/orchestrator/`) to verify no regressions
