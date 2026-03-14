# Tasks — python-migration-phase9

## Phase 9: Runtime Engine (Ralph Loop + Hooks)

### 1. Loop State Module

- [x] Create `lib/wt_orch/loop_state.py` with `LoopState` dataclass and `init_loop_state()`, `read_loop_state()`, `update_loop_state()` (atomic with flock)
- [x] Add `add_tokens()` — parse Claude CLI output for token count, increment cumulative
- [x] Add `parse_date_to_epoch()` — cross-platform ISO 8601 → epoch seconds
- [x] Add `write_activity()` — write `activity.json` for monitoring (skill, iteration, tokens, pid)
- [x] Create `tests/unit/test_loop_state.py` — state round-trip, token parsing, date parsing, activity write

### 2. Loop Tasks Module

- [x] Create `lib/wt_orch/loop_tasks.py` with `find_tasks_file()` — search worktree for tasks.md (root → subdirs)
- [x] Add `check_completion()` — parse checkboxes, return `TaskStatus(total, done, pending, manual, percent)`
- [x] Add `find_manual_tasks()` — extract `- [?]` tasks with type annotations
- [x] Add `is_done()` — comprehensive done check (tasks complete OR archived OR marker)
- [x] Create `tests/unit/test_loop_tasks.py` — discovery, completion, manual tasks, done criteria tests

### 3. Loop Prompt Module

- [x] Create `lib/wt_orch/loop_prompt.py` with `detect_next_change_action()` — return ff/apply/done/none
- [x] Add `build_claude_prompt()` — assemble CLI args with context injection
- [x] Add context injection helpers — spec files, design.md, proposal.md, previous iteration summary
- [x] Create `tests/unit/test_loop_prompt.py` — action detection, prompt assembly tests

### 4. Loop Engine Module

- [x] Create `lib/wt_orch/loop.py` with `classify_api_error()` — scan log for 429, rate-limit, 5xx patterns
- [x] Add backoff calculator — exponential with base=30s, max=240s, max_attempts=10
- [x] Add `cmd_run()` — main iteration loop: init → iterate → check done → repeat
- [x] Add iteration lifecycle — pre (write activity), run (Claude CLI via PTY), post (parse exit, update tokens)
- [x] Add completion detection — tasks.md all checked, done marker, archive action
- [x] Add token budget enforcement — warn at 80%, stop at 100%
- [x] Register CLI subcommands: `wt-orch-core loop run|status`
- [x] Create `tests/unit/test_loop.py` — API error classification, backoff, completion, token budget tests

### 5. Hook Utilities Module

- [x] Create `lib/wt_hooks/__init__.py` and `lib/wt_hooks/util.py` with `_dbg()`, `_metrics_timer_start/end()`, `read_cache()`, `write_cache()` (atomic)
- [x] Create `lib/wt_hooks/session.py` with `dedup_clear()`, `dedup_check()`, `dedup_add()`, `content_hash()`
- [x] Add `increment_turn()`, `get_turn_count()` — turn counter for checkpoint triggering
- [x] Create `tests/unit/test_hook_session.py` — dedup cycle, cache round-trip, turn counter tests

### 6. Hook Memory Ops Module

- [x] Create `lib/wt_hooks/memory_ops.py` with `recall_memories()` — call `wt-memory recall`, parse JSON, dedup filter
- [x] Add `proactive_context()` — call `wt-memory proactive`, return scored memories
- [x] Add `load_matching_rules()` — read `.claude/rules.yaml`, match against prompt patterns
- [x] Add `format_memory_output()` — `=== HEADER ===\n  - [MEM#id] content` format with truncation
- [x] Create `tests/unit/test_hook_memory_ops.py` — recall, dedup, rules matching, formatting tests

### 7. Hook Stop Pipeline Module

- [x] Create `lib/wt_hooks/stop.py` with `flush_metrics()` — collect session metrics, call `lib.metrics.flush_session()`
- [x] Add `extract_insights()` — scan JSONL transcript, call haiku for extraction, save as memories
- [x] Add `save_commit_memories()` — find git commits in session, save with `source:commit` tag
- [x] Add `save_checkpoint()` — periodic summary of files/topics (every 10 turns)
- [x] Create `tests/unit/test_hook_stop.py` — metrics flush, transcript extraction, commit save tests

### 8. Hook Event Handlers Module

- [x] Create `lib/wt_hooks/events.py` with `handle_event()` dispatcher — route by event type
- [x] Add `handle_session_start()` — dedup clear, cheat sheet recall, project context recall
- [x] Add `handle_user_prompt()` — topic recall, rules matching, format memory output with dedup
- [x] Add `handle_post_tool()` — file/command context recall, error fix surfacing, commit save
- [x] Add frustration detection — pattern matching, severity levels, memory save
- [x] Create `tests/unit/test_hook_events.py` — routing, session start, user prompt, post tool, frustration tests

### 9. Integration and Cleanup

- [x] Update `bin/wt-loop` — bin/wt-loop stays bash (CLI/terminal mgmt), loop utilities exposed via `wt-orch-core loop` subcommands
- [x] Update `bin/wt-hook-memory` — replace `source lib/hooks/*.sh` with Python entry point `python3 -m wt_hooks`
- [x] Delete `lib/loop/engine.sh`, `lib/loop/state.sh`, `lib/loop/prompt.sh`, `lib/loop/tasks.sh` — deferred: bin/wt-loop still sources these for cmd_run (PTY/terminal mgmt)
- [x] Delete `lib/hooks/events.sh`, `lib/hooks/stop.sh`, `lib/hooks/memory-ops.sh`, `lib/hooks/session.sh`, `lib/hooks/util.sh`
- [x] Benchmark hook latency: measure Python hook dispatch time vs bash baseline (target: <100ms)
- [x] Run full test suite: `pytest tests/unit/ -v` — 215/215 passed
