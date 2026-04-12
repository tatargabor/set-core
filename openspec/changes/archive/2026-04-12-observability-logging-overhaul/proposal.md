# Proposal: Observability Logging Overhaul

## Why

The orchestration engine has critical blind spots — 20 Python files containing essential business logic have zero logging. State mutations, sentinel operations, loop task detection, process lifecycle, and gate execution are completely invisible. Debugging anomalies requires manual code-tracing because there are no log trails. The recent orchestration logging hardening (850e9dd) added 20 log points to the pipeline, but the coverage is still sparse. This change systematically instruments every critical path so that post-mortem analysis and live monitoring become possible without code changes.

## What Changes

- Add `logging.getLogger(__name__)` and structured INFO/DEBUG log statements to all 20 Python files with zero logging coverage
- Increase log density in 5 files with partial coverage (planner, dispatcher, watchdog, gate_runner, test_coverage)
- Add structured log output to ~15 silent bash scripts in `bin/`
- Standardize log format across all modules (consistent prefix, context fields)
- **No new dependencies** — uses Python stdlib `logging` throughout
- **No behavioral changes** — pure observability addition, all existing logic unchanged

## Capabilities

### New Capabilities

- `orchestration-observability`: Comprehensive logging across the orchestration pipeline

### Modified Capabilities

_(none — this adds logging without changing any existing requirements)_

## Impact

- **Files touched**: ~40 (20 Python files needing new logging, 5 Python files needing more logging, ~15 bash scripts)
- **Core (`lib/set_orch/`)**: state.py, process.py, loop_tasks.py, loop_state.py, profile_types.py, reporter.py, paths.py, gate_runner.py, test_coverage.py, watchdog.py, planner.py, dispatcher.py
- **Sentinel (`lib/set_orch/sentinel/`)**: findings.py, status.py, events.py
- **Modules**: No module changes — this is all Layer 1 core
- **Bash (`bin/`)**: ~15 scripts get logging functions via set-common.sh sourcing
- **Risk**: Low — additive-only changes, no logic modifications
- **Performance**: Negligible — Python logging is lazy-evaluated at INFO level
