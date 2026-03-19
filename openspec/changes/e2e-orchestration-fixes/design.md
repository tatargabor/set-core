## Decisions

### 1. Scaffold branch rename — option A (in scaffold script)

Rename `spec-only` → `main` at the end of `run-complex.sh`, right after the `v1-ready` tag. This is the simplest fix — one line.

**Why not option B (orchestrator handles any branch):** The orchestrator's merge target logic is used everywhere (merger.py, dispatcher.py, verifier.py). Changing it to detect the current branch would require touching 10+ files and could break existing projects.

### 2. build_broken_on_main — periodic auto-retry

Add a check in the Python monitor's poll loop: every 5th poll (75s), if `build_broken_on_main` is set, re-run the build command on main. If it passes, clear the flag. This way, when conflict markers are fixed manually, dispatch resumes automatically.

**Why not clear on any commit:** A commit on main doesn't guarantee build passes. Must actually test.

### 3. Memory project resolution — use CLAUDE_PROJECT_DIR

The memory hooks receive `CLAUDE_PROJECT_DIR` as env var (set by MCP registration and dispatch). Use this instead of resolving from git toplevel. If not set, fall back to git toplevel.

**Why not disable memory entirely for E2E:** Memory is valuable — it helps agents avoid repeating mistakes. The bug is wrong project resolution, not memory itself.

### 4. Config template default model — add opus-1m

Update `wt/orchestration/config.yaml` template to include `default_model: opus-1m` as a commented-out option alongside `default_model: opus`.

### 5. Python monitor heartbeat — emit to bash log

The Python `engine.py` monitor should write a heartbeat line to the orchestration log every poll cycle. The bash sentinel reads this log — if it sees recent entries, it won't trigger "no progress" watchdog.
