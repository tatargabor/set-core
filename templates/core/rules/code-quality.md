# Code Quality Rules

## Logging — mandatory for all new code

Every new Python module MUST include logging:

```python
import logging
logger = logging.getLogger(__name__)
```

### Log levels

- **INFO** — Operational events: state transitions, lifecycle start/stop, gate outcomes, key decisions. These are visible during normal runs.
- **DEBUG** — Internal details: hash values, search paths, binding scores, lock acquire/release. Only visible when investigating specific subsystems.
- **WARNING** — Anomalies: missing files, fallback paths, unexpected state, crash recovery, unbound items.
- **ERROR** — Failures that block progress: gate failures, process crashes, hook rejections.

### Log message rules

- Include contextual fields: change name, PID, file path, old→new values. Logs without context are useless in multi-change parallel orchestration.
- NEVER silently swallow errors (`except: pass`). At minimum, log at WARNING level.
- State mutations MUST log the field name, old value, and new value.
- Process lifecycle events (start, kill, crash) MUST log PID and signal/exit code.

### Bash scripts

- Source `set-common.sh` and use `info()`, `warn()`, `error()` for key operations.
- Log script start, key operations (file copy, git, API calls), and exit status.

### Audit logs (per-project state)

Some subsystems maintain append-only JSONL audit trails under `.set/state/` for telemetry, cache, and post-merge aggregation:

- `category-classifications.jsonl` — every category-resolver invocation (deterministic + LLM breakdown, agreement diff, timing). Inspect with `jq` to debug surprising category injections (`jq 'select(.cache_hit==false) | {change: .change_name, det: .deterministic.categories, llm: .llm.categories}' < .set/state/category-classifications.jsonl`).
- `project-insights.json` — aggregated trends, rewritten after each merge.

Both files are gitignored under `.set/` and safe to delete; the resolver runs cold on absence.

## Abstraction layers

When this project uses a modular architecture (core + plugins/modules):

- **Core code** must remain abstract — no project-type-specific patterns (web frameworks, test runners, package managers).
- **Modules/plugins** implement project-type specifics.
- New project-aware behavior goes through the abstract interface first, then gets implemented in the appropriate module.
- A single change can touch both core and module — clearly mark which files are which layer.
