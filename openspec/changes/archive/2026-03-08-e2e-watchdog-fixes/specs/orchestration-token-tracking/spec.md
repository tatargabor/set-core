## ADDED Requirements

### R1: Token Tracking Resilience
- `get_current_tokens()` in `lib/loop/state.sh` must not silently return 0 when `wt-usage` fails
- When `wt-usage` is unavailable or crashes, fall back to JSONL session file size estimation
- The fallback reads Claude session JSONL files from `~/.claude/projects/` for the current project
- Estimates tokens at ~4 tokens per byte of JSONL (existing `estimate_tokens_from_files()` function)

### R2: wt-usage Import Fix
- `bin/wt-usage` must resolve its Python import path correctly regardless of CWD
- Add `sys.path.insert(0, script_dir)` or equivalent to resolve the `gui` module relative to set-core installation
- If the gui module is not available (e.g., headless install), wt-usage should exit with a clear error instead of an unhandled ImportError
