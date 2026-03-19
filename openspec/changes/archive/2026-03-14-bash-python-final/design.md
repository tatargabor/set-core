## Context

The `orch-python-cutover` change migrated the monitor loop, merge pipeline, and replan to Python. Five bash files with ~2,950 lines of active logic remain: `digest.sh`, `planner.sh`, `watchdog.sh`, `auditor.sh`, `builder.sh`. Each has a partial or complete Python counterpart in `lib/set_orch/` (totalling 3,340 lines), but the bash versions still run. Some bash functions delegate to `set-orch-core` already; others have pure bash logic with inline `python3 -c` snippets.

Current state per file:
- **digest.sh** (1,311 LOC): Zero delegation — all logic is bash + inline python3. Python `digest.py` (1,170 LOC) exists but is only called for a few helpers.
- **planner.sh** (768 LOC): Partial delegation — subcommands like `validate`, `check-triage`, `build-context` delegate. But `cmd_plan()` (~250 LOC of orchestration) and `plan_via_agent()` (~80 LOC) are pure bash.
- **watchdog.sh** (424 LOC): Reads state via `set-orch-core state get` but all watchdog logic (hash ring, escalation, progress detection) is bash.
- **auditor.sh** (298 LOC): Uses `set-orch-core template audit` for prompt rendering but builds input JSON and parses output in bash.
- **builder.sh** (151 LOC): Pure bash — package manager detection, build caching, LLM-assisted fix with escalation.

## Goals / Non-Goals

**Goals:**
- Port all active bash logic to Python modules under `lib/set_orch/`
- Wire new Python functions into `set-orch-core` CLI subcommands
- Reduce each bash file to a thin wrapper (~10-20 lines: source guard + `set-orch-core` call)
- Maintain 100% behavioral compatibility
- No feature flag needed — the previous cutover validated the pattern

**Non-Goals:**
- Changing the `set-orchestrate` CLI interface (bash entry points stay)
- Rewriting `bin/set-orchestrate` itself (stays bash)
- Adding new features beyond parity
- Migrating `dispatcher.sh` signal handling (already done in orch-python-cutover)

## Decisions

### D1: Direct cutover without feature flag

**Decision**: Unlike `orch-python-cutover`, no `ORCH_ENGINE` flag. Each bash function gets replaced by a `set-orch-core` call directly.

**Why**: The feature flag pattern was needed for the monitor loop (critical, long-running). These are request-response functions — if Python fails, the error is immediate and obvious. The previous cutover validated that the delegation pattern works.

### D2: Extend existing Python modules, don't create new ones

**Decision**: Each bash file already has a Python counterpart. Add missing functions to those modules rather than creating new files.

| Bash file | Python module | What to add |
|---|---|---|
| digest.sh | digest.py (1,170 LOC) | `cmd_digest()` orchestration, `scan_spec_directory()`, `call_digest_api()`, `write_digest_output()`, triage pipeline |
| planner.sh | planner.py (1,154 LOC) | `cmd_plan()` orchestration, `plan_via_agent()`, design bridge setup |
| watchdog.sh | watchdog.py (443 LOC) | `watchdog_check()` full pipeline, action hash ring, escalation chain |
| auditor.sh | auditor.py (348 LOC) | `build_audit_input()`, `parse_audit_result()`, `run_post_phase_audit()` |
| builder.sh | builder.py (225 LOC) | `check_base_build()` with caching, `fix_base_build_with_llm()` escalation |

### D3: Replace jq with Python json, md5sum with hashlib

**Decision**: Bash uses `jq` for JSON manipulation and `md5sum` for hashing. Python uses stdlib `json` and `hashlib`.

**Why**: Direct stdlib equivalents — no external dependencies needed.

### D4: Claude API calls via subprocess_utils.run_claude()

**Decision**: Bash calls `run_claude()` (a bash helper that invokes Claude CLI). Python uses the existing `subprocess_utils.run_claude()` wrapper.

**Why**: Consistent with how the already-migrated functions work. The Claude CLI is the interface — no direct API SDK needed.

### D5: Bash `cmd_plan()` becomes thin wrapper calling `set-orch-core plan run`

**Decision**: The ~250 LOC `cmd_plan()` bash orchestration (digest freshness → triage gate → design bridge → Claude decomposition → validation → coverage) moves entirely to Python. Bash keeps only argument parsing and `set-orch-core plan run "$@"`.

**Why**: This is the most complex remaining bash function with many interleaved steps. Half of them already delegate to Python subcommands — consolidating removes the interleaving.

### D6: Watchdog state stays in orchestration-state.json

**Decision**: The watchdog state (action_hash_ring, escalation_level, last_activity_epoch) continues to live in the main state file under `changes[].watchdog`. Python reads/writes via `state.py` locked updates.

**Why**: Moving to a separate file would require migration. The current approach works and the Python state module already supports field-level updates.

## Risks / Trade-offs

**[Risk: digest.sh is the largest and least-migrated file]** → Mitigation: digest.py already has 1,170 LOC of helpers. The migration adds orchestration flow, not reimplementation of helpers. Port function-by-function, testing each.

**[Risk: cmd_plan() has many side effects (file writes, API calls, state updates)]** → Mitigation: Keep the same execution order. The Python version calls the same external tools (Claude CLI, git) via subprocess.

**[Risk: Watchdog timing sensitivity]** → Mitigation: Use the same polling interval and timeout values. Python `time.time()` matches bash `date +%s`. Action hash uses `hashlib.md5()` on the same inputs.

**[Risk: Inline python3 -c snippets in digest.sh may have subtle behavior]** → Mitigation: Read each inline snippet, port to named functions in digest.py, verify input/output format match.

## Migration Plan

### Phase 1: Watchdog + Builder (smallest, lowest risk)
1. Port `watchdog_check()` full pipeline to `watchdog.py`
2. Port `check_base_build()` + `fix_base_build_with_llm()` to `builder.py`
3. Add CLI subcommands: `set-orch-core watchdog check`, `set-orch-core build check`
4. Replace bash functions with thin wrappers
5. Test via orchestration run

### Phase 2: Auditor (medium, clear boundaries)
1. Port `build_audit_input()`, `parse_audit_result()`, `run_post_phase_audit()` to `auditor.py`
2. Add CLI: `set-orch-core audit run`
3. Replace bash with wrapper

### Phase 3: Planner orchestration (complex, many dependencies)
1. Port `cmd_plan()` orchestration to `planner.py:run_plan()`
2. Port `plan_via_agent()` to `planner.py:plan_via_agent()`
3. Add CLI: `set-orch-core plan run`
4. Replace bash `cmd_plan()` with thin wrapper

### Phase 4: Digest pipeline (largest, most complex)
1. Port `scan_spec_directory()`, `call_digest_api()`, `write_digest_output()` to `digest.py`
2. Port triage pipeline (`generate_triage_md`, `parse_triage_md`, etc.)
3. Port coverage functions (`populate_coverage`, `check_coverage_gaps`)
4. Add CLI: `set-orch-core digest run`
5. Replace bash `cmd_digest()` with thin wrapper

### Phase 5: Cleanup
1. Verify all bash files are thin wrappers
2. Remove dead code
3. Delete inline `python3 -c` snippets
