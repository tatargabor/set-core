# Design: Runtime Directory Cleanup

## Decisions

### D1: Single line change in SetRuntime drives everything

```python
# paths.py line 92 — BEFORE:
self.root = os.path.join(SET_TOOLS_DATA_DIR, self._project_name)

# AFTER:
self.root = os.path.join(SET_TOOLS_DATA_DIR, "runtime", self._project_name)
```

14+ Python files using SetRuntime properties update with zero code changes.

### D2: Bash equivalent in set-paths

```bash
# bin/set-paths line 39 — BEFORE:
WT_RUNTIME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/set-core/$WT_PROJECT_NAME"

# AFTER:
WT_RUNTIME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/set-core/runtime/$WT_PROJECT_NAME"
```

### D3: Auto-migration on first access

`SetRuntime.__init__()` checks if old-style dir exists but new doesn't, and moves it:

```python
old_root = os.path.join(SET_TOOLS_DATA_DIR, self._project_name)
new_root = os.path.join(SET_TOOLS_DATA_DIR, "runtime", self._project_name)
if os.path.isdir(old_root) and not os.path.isdir(new_root):
    os.makedirs(os.path.dirname(new_root), exist_ok=True)
    shutil.move(old_root, new_root)
self.root = new_root
```

### D4: Watcher uses SetRuntime instead of hardcoded paths

The `_find_state()` and `_find_log()` methods currently hardcode `wt/orchestration/orchestration-state.json` and `orchestration-state.json`. They should try SetRuntime first, then fall back to legacy project-local paths.

### D5: Shell scripts use set-paths variables

Shell scripts in `lib/orchestration/`, `bin/set-sentinel`, `bin/set-orchestrate` that hardcode `wt/orchestration/` paths should use `$WT_ORCHESTRATION_DIR` etc. from set-paths where possible.

## Files Changed

### Automatic (via SetRuntime — 0 code changes):
- api.py (11 endpoints), engine.py, dispatcher.py, verifier.py, merger.py
- gate_runner.py, events.py, reporter.py, logging_config.py, planner.py
- sentinel/set_dir.py, digest.py

### Manual fixes needed:
- `paths.py` — SetRuntime.root + auto-migration
- `bin/set-paths` — WT_RUNTIME_DIR
- `watcher.py` — _find_state(), _find_log() → use SetRuntime
- `bin/set-sentinel` — archive paths
- `bin/set-orchestrate` — run archive paths
- `bin/set-cleanup` — state file discovery
- `lib/orchestration/digest.sh` — DIGEST_DIR default
- `auditor.py` — default digest_dir parameter
- `tests/unit/test_paths.py` — assertion updates
