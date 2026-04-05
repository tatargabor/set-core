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

## Abstraction layers

- **`lib/set_orch/` (Layer 1, core)** must remain abstract — NEVER put web-specific patterns (Playwright, Next.js, Prisma, package.json) here.
- **`modules/web/` (Layer 2)** implements web-specific logic. **`modules/example/`** is the reference plugin.
- New project-aware behavior goes through `ProjectType` ABC in `profile_types.py` first, then gets implemented in the appropriate module.
- A single change can touch both core and module — clearly mark which files are which layer in task lists and commit messages.
