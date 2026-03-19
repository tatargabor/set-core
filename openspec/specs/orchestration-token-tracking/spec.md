## ADDED Requirements

### R1: Token Tracking Resilience
- `get_current_tokens()` in `lib/loop/state.sh` SHALL return the token count from `wt-usage` when available
- When `wt-usage` is unavailable or fails, `get_current_tokens()` SHALL return 0 rather than failing
- The orchestrator uses iteration count (`--max 30`) as the primary safety net, not token tracking

### R2: wt-usage Import Fix
- `bin/wt-usage` must resolve its Python import path correctly regardless of CWD
- Add `sys.path.insert(0, script_dir)` or equivalent to resolve the `gui` module relative to set-core installation
- If the gui module is not available (e.g., headless install), wt-usage should exit with a clear error instead of an unhandled ImportError
