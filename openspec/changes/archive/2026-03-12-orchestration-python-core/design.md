## Context

The orchestration engine (`lib/orchestration/*.sh`, ~4,500 lines across 14 files) manages parallel AI agent workflows: dispatching changes to worktrees, monitoring progress, detecting stuck processes, and merging results. After bash-hardening (safe_jq_update, flock locking), atomic JSON writes are safe. Three fragility areas remain:

1. **Process management** — 9 `kill -0` calls check PID liveness without verifying process identity. PIDs are read from `loop-state.json:.terminal_pid` and stored in `orchestration-state.json:.changes[].ralph_pid`. No `/proc/cmdline` verification means PID recycling can cause the watchdog to skip escalation on a dead process or kill an unrelated process.

2. **441 jq invocations** — 280 use `--arg`/`--argjson` safely, 27 go through `safe_jq_update`, but ~12 multi-stage pipelines and ~15 complex filters (>40 chars) remain fragile. Empty-string bugs hide behind `// empty` vs `// ""` inconsistency. The `init_state()` function alone is a 40-line jq filter.

3. **16 unquoted heredocs** embed variables containing user text, git diffs, test output, and memory context into Claude prompts and markdown files. The main planning prompt (planner.sh:882) spans 200+ lines with 5 nested heredocs. No escaping.

Existing Python infrastructure: pyproject.toml (Python >=3.10), pytest, 7 inline `python3 -c` scripts already in orchestration (topological sort, JSON extraction, YAML parsing), PySide6 GUI, MCP server. psutil is installed by install.sh for the GUI but is not currently declared in pyproject.toml main dependencies.

## Goals / Non-Goals

**Goals:**
- Eliminate PID recycling risk with `/proc/cmdline` verification and psutil-based process tree queries
- Replace the most fragile jq patterns (multi-stage pipelines, complex filters, init_state) with typed Python dataclasses
- Replace unquoted heredocs with Python template rendering that handles escaping
- Provide a `wt-orch-core` CLI bridge so bash scripts call Python without restructuring the overall orchestration flow
- Maintain full backward compatibility — no CLI or behavioral changes

**Non-Goals:**
- Rewriting the entire orchestration in Python — bash remains for git operations, worktree management, and flow control
- Replacing simple jq reads like `jq -r '.status' "$file"` — only complex/fragile patterns migrate
- Adding new orchestration features — this is a reliability refactor
- Migrating the GUI or MCP server code — those are separate Python packages
- Replacing `safe_jq_update` for simple field writes — it works well for single-field atomic updates

## Decisions

### D1: Package location — `lib/wt_orch/` (not `wt_tools/`)

The `wt_tools/` package is a minimal plugin stub. The `gui/` package is the PySide6 app. Orchestration Python code goes into `lib/wt_orch/` to live alongside the shell scripts it serves (`lib/orchestration/*.sh`). This keeps the dependency clear: orchestration shell calls orchestration Python.

**Alternative considered:** Adding to `wt_tools/` package. Rejected because `wt_tools` is the plugin system — mixing orchestration internals there creates coupling.

### D2: CLI bridge — single `bin/wt-orch-core` entry point

One Python CLI (`bin/wt-orch-core`) with subcommands: `process`, `state`, `template`. Bash calls it like:

```bash
# Instead of: kill -0 "$ralph_pid" 2>/dev/null
wt-orch-core process check-pid --pid "$ralph_pid" --expect-cmd "wt-loop"

# Instead of: 40-line jq init_state filter
wt-orch-core state init --plan-file "$plan_file" --output "$STATE_FILENAME"

# Instead of: cat <<PROPOSAL_EOF with unescaped variables
wt-orch-core template proposal --change "$change_name" --scope "$scope" --roadmap "$roadmap_item"
```

Each call is a short-lived Python process. No daemon, no socket, no persistent state.

**Alternative considered:** Python module invocation (`python3 -m wt_orch.process ...`). Rejected because a named CLI entry point is cleaner in shell scripts and can be installed via pyproject.toml `[project.scripts]`.

### D3: Process module — psutil + /proc fallback

```
process.py
├── check_pid(pid, expected_cmdline_pattern) → bool
├── find_orphans(expected_pattern, known_pids) → list[OrphanInfo]
├── safe_kill(pid, expected_cmdline_pattern, timeout=10) → KillResult
└── get_process_tree(pid) → list[ProcessInfo]
```

Uses psutil for cross-platform process queries. On Linux, also reads `/proc/<pid>/cmdline` directly as fast-path verification. `check_pid` replaces all 9 `kill -0` patterns by verifying both PID existence AND process identity.

`safe_kill` implements: verify identity → SIGTERM → wait(timeout) → verify again → SIGKILL. Replaces the dispatcher.sh pattern of `kill -TERM; sleep 2; kill -0; kill -KILL`.

**Alternative considered:** Pure `/proc` parsing without psutil. Rejected because psutil handles edge cases (zombie processes, permission errors, macOS compatibility) that raw `/proc` reads miss.

### D4: State module — dataclasses with selective migration

```
state.py
├── @dataclass OrchestratorState (status, changes, checkpoints, merge_queue, ...)
├── @dataclass Change (name, scope, status, ralph_pid, tokens_used, watchdog, ...)
├── @dataclass WatchdogState (last_activity_epoch, action_hash_ring, ...)
├── load_state(path) → OrchestratorState  (validates on read)
├── save_state(state, path)  (atomic write with temp+rename)
├── init_state(plan_file, output_path)  (replaces 40-line jq in state.sh)
├── query_changes(state, status=None) → list[Change]
├── aggregate_tokens(state) → TokenStats
└── (future: update_change — deferred, safe_jq_update handles single-field writes well)
```

Only the complex operations migrate to Python:
- `init_state()` — the 40-line jq transformation from plan.json to state.json
- Multi-change queries (count by status, filter by status, aggregate tokens)
- Watchdog state reads (extracting nested `.watchdog` subobject)
- Compound updates that currently need `with_state_lock` for multiple fields

Simple reads (`jq -r '.status'`) and simple writes (`safe_jq_update "$f" '.field = "value"'`) stay in bash. The Python state module validates the full schema on `load_state` and rejects corrupt JSON with a clear error.

**Alternative considered:** Full migration of all 441 jq calls. Rejected because 280+ are simple, safe reads with `--arg`. Migrating everything would be a massive diff with minimal reliability gain.

### D5: Template module — Python f-strings with explicit escaping

```
templates.py
├── render_proposal(change_name, scope, roadmap_item, memory_ctx, spec_ref) → str
├── render_review_prompt(scope, diff_output, req_section) → str
├── render_fix_prompt(change_name, scope, output_tail, smoke_cmd) → str
├── render_planning_prompt(input_content, specs, memory, replan_ctx, mode="spec") → str
└── escape_for_prompt(text) → str  (neutralizes $, `, EOF markers)
```

Replaces 16 unquoted heredocs. Each template is a Python function that takes typed arguments and returns a string. `escape_for_prompt()` neutralizes characters that would break shell heredoc expansion (`$`, backtick, `EOF` markers).

Templates use Python f-strings (not Jinja2). The templates are structured text, not complex enough to justify a template engine dependency.

**Alternative considered:** Jinja2. Rejected — adds an external dependency for templates that are essentially string concatenation with escaping. f-strings are sufficient and keep the dependency list clean.

### D6: psutil dependency — already available, make it explicit

psutil is installed by install.sh for the GUI but is not currently in pyproject.toml `dependencies`. Adding it to the main dependencies list means `pip install wt-tools` will pull psutil (requires C compilation on some platforms). This is a real dependency change affecting pip-only installs and CI environments.

### D7: Migration order — process first, then state, then templates

1. **Process** — Smallest scope (9 call sites), highest severity (PID recycling is a known production incident). Independent of state/template changes.
2. **State** — Medium scope (~20 complex patterns), depends on having the dataclass schema finalized. Can coexist with remaining jq calls.
3. **Templates** — Largest scope (16 heredocs across 5 files), but lowest severity (corruption requires specific special characters in variables). Benefits from state dataclasses being available for typed template arguments.

## Risks / Trade-offs

**[Startup latency]** Each `wt-orch-core` call spawns a Python interpreter (~50-100ms). The monitor loop polls every 15 seconds with 1-5 active changes, so worst case adds ~500ms per cycle. → Mitigation: Only use Python for complex operations. Keep simple jq reads in bash.

**[Two sources of truth]** Python dataclasses and jq both read/write state.json. Schema drift is possible. → Mitigation: Python `load_state()` validates against the dataclass schema. Any field added in bash must be added to the dataclass. Tests verify round-trip consistency.

**[psutil availability]** psutil requires C compilation on some platforms and is not currently in pyproject.toml (only in install.sh). Adding it to main dependencies changes the install contract for pip-only environments. → Mitigation: Process module degrades gracefully to `kill -0` if psutil import fails, with a warning log. CI environments can install without psutil if orchestration features are not tested.

**[Partial migration state]** During migration, some operations use Python and some use jq for the same file. → Mitigation: Both use atomic writes (Python: tempfile+rename, bash: safe_jq_update). The flock-based `with_state_lock` is used by bash callers before invoking Python state operations that write.

**[Testing complexity]** Python tests need orchestration state fixtures. → Mitigation: Extract representative state.json samples from production runs as test fixtures. pytest parametrize over normal/corrupt/edge-case states.
