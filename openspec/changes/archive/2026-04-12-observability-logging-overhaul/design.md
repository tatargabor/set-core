# Design: Observability Logging Overhaul

## Context

The orchestration engine currently has 20 Python files with zero logging and ~15 silent bash scripts. The recent 850e9dd commit added 20 log points to the pipeline, proving the pattern works. This change extends that pattern systematically to every critical path.

The existing logging in well-covered files (merger.py at 6.2%, engine.py at 4.5%) uses `logger = logging.getLogger(__name__)` consistently — we follow the same convention everywhere.

## Goals

- Every state mutation, process lifecycle event, gate decision, and sentinel operation produces a log line
- Post-mortem analysis of any orchestration run is possible from logs alone
- No behavioral changes — pure additive instrumentation

## Non-Goals

- Log aggregation infrastructure (ELK, etc.)
- Structured JSON logging (plain text is fine)
- Performance metrics or tracing spans
- Log rotation changes

## Decisions

### 1. Python stdlib logging only
**Choice**: `logging.getLogger(__name__)` in every file.
**Why**: Already the established pattern in 29 files. No new dependencies. Logger hierarchy follows module structure automatically.
**Alternative**: structlog for structured logging — rejected because it adds a dependency and all existing code uses stdlib.

### 2. Log level strategy
**Choice**:
- **INFO**: Operational events visible during normal runs (state transitions, gate outcomes, process start/stop, findings, events)
- **DEBUG**: Internal details useful only during investigation (hash values, search paths, binding scores, lock acquire/release)
- **WARNING**: Anomalies that might indicate problems (missing files, fallback paths, zombie processes, unbound tests, crash recovery)

**Why**: INFO is the default level in orchestration runs. DEBUG can be enabled per-module via logging config when investigating specific subsystems.

### 3. Contextual log messages
**Choice**: Include relevant context in every log message — change name, PID, field name, old/new values.
**Why**: Logs without context are useless in multi-change orchestration where 3-5 changes run in parallel. Grepping for a change name must show its full lifecycle.

### 4. Bash scripts source set-common.sh
**Choice**: Silent scripts source `set-common.sh` to get `log_info()`, `log_warn()`, `log_error()` functions.
**Why**: set-common.sh already defines these functions and is used by ~18 scripts. Adding it to the remaining ~15 is consistent.

## Risks / Trade-offs

- **[Risk] Log volume increase** → INFO-level logging adds ~2-5 lines per state transition. In a 6-change orchestration run this might add ~200 lines. Acceptable — the orchestration log already contains thousands of lines.
- **[Risk] Large diff size** → ~40 files touched. Each file gets 5-20 new log lines. Mitigated by pure additive changes — no logic modifications, easy to review.
- **[Risk] Sensitive data in logs** → State values could contain file paths or change names. These are not secrets — orchestration logs are local only.

## Open Questions

None — the pattern is established, this is systematic application.
