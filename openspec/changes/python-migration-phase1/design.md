## Context

The orchestration engine (`lib/orchestration/*.sh`, ~18,000 LOC) is being migrated to Python in phases. Phase 1 establishes the foundational infrastructure: logging, subprocess wrappers, config parsing, and event system. The existing Python bridge (`lib/wt_orch/`, 10 modules) provides the package structure, CLI dispatch via `wt-orch-core`, and dataclass patterns.

**Current state:**
- `lib/wt_orch/cli.py` dispatches subcommands: `process`, `state`, `template`, `serve`
- `lib/orchestration/utils.sh` (~820 LOC): directive parsing, duration utilities, file hashing, input resolution
- `lib/orchestration/events.sh` (~155 LOC): JSONL event emission, rotation, querying
- Python >= 3.10, stdlib only (no new external deps)

**Constraints:**
- JSON format for events.jsonl and directives output MUST remain byte-compatible
- Bash callers transition via `wt-orch-core` CLI — no direct Python imports from bash
- All existing tests must continue to pass

## Goals / Non-Goals

**Goals:**
- 4 new Python modules in `lib/wt_orch/` with full test coverage
- 1:1 behavioral parity with bash originals (every edge case preserved)
- Bash functions replaced with `wt-orch-core` CLI calls
- Structured logging ready for all future Python modules

**Non-Goals:**
- Migrating state.sh, planner.sh, dispatcher.sh, verifier.sh (future phases)
- Changing the directive schema or adding new directives
- Async/await patterns (not needed for these modules)
- Replacing `safe_jq_update()` or `with_state_lock()` (these stay in bash until state.sh migration)

## Decisions

### 1. Module structure: flat in wt_orch/

New files added to `lib/wt_orch/`:
```
lib/wt_orch/
├── logging_config.py      # NEW
├── subprocess_utils.py    # NEW
├── config.py              # NEW
├── events.py              # NEW
├── cli.py                 # MODIFIED (add config, events subcommands)
├── state.py               # existing
├── templates.py           # existing
├── process.py             # existing
└── ...
```

**Why flat:** The package already has 10 modules at the same level. Sub-packages would be premature — wait until module count exceeds ~20.

### 2. Logging: stdlib logging with custom formatter

```python
# logging_config.py
class ExtraFormatter(logging.Formatter):
    """Appends extra dict keys as key=value pairs."""
    def format(self, record):
        base = super().format(record)
        extras = {k: v for k, v in record.__dict__.items()
                  if k not in logging.LogRecord('').__dict__ and k != 'message'}
        if extras:
            pairs = ' '.join(f'{k}={v}' for k, v in extras.items())
            return f'{base} {pairs}'
        return base
```

**Why custom formatter over structlog/JSON:** The orchestration.log is read by humans (sentinel, user). Plain text with extras is the right format. JSON logging can be added later as an option.

**Alternative considered:** `structlog` — rejected because it adds an external dependency and the stdlib `logging` module is sufficient.

### 3. Subprocess wrappers: dataclass results, not exceptions

```python
@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
```

**Why dataclass over exceptions:** The orchestration engine treats non-zero exit codes as data (e.g., test failures are expected). Raising exceptions for every non-zero would require try/except everywhere. Return the result, let callers decide.

**Alternative considered:** Raising `subprocess.CalledProcessError` — rejected because most callers check exit_code explicitly.

### 4. Config parsing: Pydantic-free, dataclass + validation

Directives are validated inline with type coercion and default fallback, matching the bash `case` statement exactly. No Pydantic — stdlib `dataclasses` suffice.

```python
@dataclass
class Directives:
    max_parallel: int = 2
    merge_policy: str = "eager"  # eager|checkpoint|manual
    # ... all 50+ fields with defaults matching DEFAULT_* from config.sh
```

**Why not Pydantic:** Adding Pydantic as a dependency for config parsing alone is overkill. The validation logic is simple (regex + type coercion) and maps 1:1 from the bash case statements.

### 5. Events: file writer + in-process bus

Two concerns, one module:
1. **JSONL writer** — `emit()` appends to file (replaces `events.sh:emit_event()`)
2. **Event bus** — `subscribe(type, handler)` for in-process consumers (future use by monitor, watcher)

```python
class EventBus:
    _subscribers: dict[str, list[Callable]]  # type → handlers
    _log_path: Path | None
    _emit_count: int  # for rotation check every 100

    def emit(self, type: str, change: str = "", data: dict = None): ...
    def subscribe(self, type: str, handler: Callable): ...
```

**Why combined:** The event bus is the natural owner of the JSONL file. Separating them would create coordination issues (who owns the file handle?).

### 6. CLI dispatch: extend existing argparse in cli.py

Add two new subcommands to `cli.py`:
- `wt-orch-core config parse-directives --input-file <path>`
- `wt-orch-core config resolve-directives --input-file <path> [--cli-overrides '{"max_parallel":5}']`
- `wt-orch-core events --type <TYPE> --change <NAME> --last <N> --json`

**Why extend cli.py:** Consistent with existing pattern (`process`, `state`, `template`). No new entry points needed.

### 7. Bash transition: source → wt-orch-core calls

Migrated bash functions are replaced with `wt-orch-core` calls:

```bash
# Before (utils.sh):
directives=$(parse_directives "$brief_file")

# After:
directives=$(wt-orch-core config parse-directives --input-file "$brief_file")
```

The bash functions are deleted entirely (not wrapped). Callers in `bin/wt-orchestrate` and `lib/orchestration/*.sh` are updated.

### 8. Test command auto-detection

Moved as-is from bash. Checks:
1. `package.json` → scripts.test → detect pm (npm/pnpm/yarn/bun)
2. `Makefile` → test target
3. `pytest.ini` / `pyproject.toml [tool.pytest]` → pytest

## Risks / Trade-offs

**[Risk] Subprocess overhead for CLI calls** → The `wt-orch-core` process startup adds ~100ms per call. Acceptable for directive parsing (called 1-2 times at start), but would be problematic for high-frequency operations (e.g., `emit_event` called 100s of times). Mitigation: events.sh stays in bash for now; Python `events.py` is used when the caller is already Python.

**[Risk] Directive JSON format drift** → If Python serializes JSON differently (key ordering, null handling). Mitigation: Test with exact byte comparison against bash output for known inputs.

**[Risk] YAML parsing fallback** → PyYAML may not be installed. Mitigation: Keep the simple `key: value` fallback parser (ported from bash) — same behavior as current bash version.

**[Risk] Cross-platform stat for file size** → Linux uses `stat -c %s`, macOS uses `stat -f %z`. Mitigation: Python's `os.path.getsize()` is cross-platform — this is a Python win.

## Migration Plan

1. Create the 4 Python modules with tests
2. Add CLI subcommands to `cli.py`
3. Verify output parity: run both bash and Python for same inputs, diff results
4. Update bash callers to use `wt-orch-core` commands
5. Delete migrated bash functions from `utils.sh` and `events.sh`
6. Run full test suite (bash + Python)

**Rollback:** If issues are found, bash callers can be reverted to source the original functions. The Python modules are additive until step 5.

## Open Questions

_(none — all decisions resolved)_
