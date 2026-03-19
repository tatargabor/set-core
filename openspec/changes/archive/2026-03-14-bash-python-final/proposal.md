## Why

The `orch-python-cutover` change migrated the monitor loop, merge pipeline, and replan logic to Python, but ~2,950 lines of active bash orchestration remain in 5 files. This creates maintenance burden (two languages for the same system), makes testing harder (bash functions can't be unit-tested), and blocks future improvements like typed state and async dispatch. Completing the migration now unifies the orchestration engine in Python.

## What Changes

- **digest.sh** (~1,300 lines): Port spec scanning, Claude API digestion, triage gate, coverage mapping, and freshness detection to `lib/set_orch/digest.py`. Bash becomes thin CLI wrapper.
- **planner.sh** (~770 lines): Port `cmd_plan()` orchestration (design bridge, triage gate, Claude decomposition, JSON validation, coverage) and `plan_via_agent()` to `lib/set_orch/planner.py`. Keep bash entry point for CLI dispatch only.
- **watchdog.sh** (~420 lines): Port watchdog state machine (action hash ring, stuck/spinning detection, escalation levels L1-L4, partial salvage) to `lib/set_orch/watchdog.py`. Bash becomes stub.
- **auditor.sh** (~300 lines): Port audit prompt building, Claude gap detection, and replan context injection to `lib/set_orch/auditor.py`. Bash becomes stub.
- **builder.sh** (~150 lines): Port base build check and LLM-assisted fix (sonnet→opus escalation) to `lib/set_orch/builder.py`. Bash becomes stub.
- **CLI wiring**: Extend `set-orch-core` CLI with new subcommands for digest, plan, watchdog, audit, builder.
- **Remove bash fallbacks**: Delete active bash logic after Python equivalents are validated.

## Capabilities

### New Capabilities

- `orch-digest-python`: Python implementation of spec digestion pipeline (scan, API call, triage, coverage)
- `orch-plan-python-final`: Python implementation of full planning orchestration (cmd_plan, plan_via_agent)
- `orch-watchdog-python`: Python implementation of watchdog state machine and escalation
- `orch-audit-python`: Python implementation of post-phase audit pipeline
- `orch-builder-python`: Python implementation of base build check and LLM-assisted fix

### Modified Capabilities

- `orchestration-engine`: Bash entry points become thin wrappers delegating to Python

## Impact

- **lib/orchestration/**: 5 bash files reduced to thin stubs (~10-20 lines each)
- **lib/set_orch/**: 5 Python modules gain full implementations (~2,500 lines of new Python)
- **lib/set_orch/cli.py**: New subcommands registered
- **External calls**: Claude API calls, jq usage, md5sum replaced with Python equivalents (hashlib, json)
- **Dependencies**: No new pip dependencies (uses stdlib: hashlib, json, subprocess, pathlib)
