## Purpose

Migrate `lib/loop/engine.sh` (903 LOC) to `lib/set_orch/loop.py`. The main Ralph iteration loop: runs Claude CLI repeatedly in a worktree, handles API errors with exponential backoff, enforces token budgets, detects completion, and manages iteration lifecycle.

## Requirements

### LOOP-01: Main Iteration Loop
- `cmd_run(config)` runs the main loop: init state → iterate → check done → repeat
- Each iteration: build prompt → call Claude CLI → parse output → update state
- Respect `max_iterations` limit from config
- Clean exit on completion, error, or user interrupt (SIGINT/SIGTERM)

### LOOP-02: API Error Classification and Backoff
- `classify_api_error(log_file, exit_code)` scans log for error patterns
- Detect: 429/rate-limit, overloaded, server errors (5xx), network errors
- Exponential backoff: base=30s, max=240s, max_attempts=10
- Non-API errors (claude crash, permission denied) → immediate fail, no retry

### LOOP-03: Iteration Lifecycle
- Pre-iteration: write `activity.json` with current state for monitoring
- Run Claude CLI via `script(1)` PTY wrapper for proper terminal handling
- Post-iteration: parse exit code, update token count, check for errors
- Log iteration output to `iter-NNN.log` files

### LOOP-04: Completion Detection
- Check tasks.md for all checkboxes complete (`- [x]`)
- Check for "done" marker in Claude output
- Check for OpenSpec archive action (change completed)
- Return `LoopResult(status, iterations, tokens_used, reason)`

### LOOP-05: Token Budget Enforcement
- Track cumulative token usage across iterations (from Claude CLI output)
- Warn at 80% of budget, stop at 100%
- Budget configurable via `--token-budget` flag or orchestration directive
- Report tokens in loop state file

### LOOP-06: CLI Subcommands
- `set-orch-core loop run --wt-path <path> [--change <name>] [--max-iter <n>] [--token-budget <n>]`
- `set-orch-core loop status --wt-path <path>` — show current loop state
- Registered in `cli.py` under `loop` group

### LOOP-07: Unit Tests
- Test API error classification with mock log content
- Test backoff timing calculation
- Test completion detection with various tasks.md states
- Test token budget enforcement thresholds
