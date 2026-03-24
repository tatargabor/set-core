# Design: Issue Management Engine (set-manager service)

## Context

set-core has grown from a simple orchestration tool to a multi-project management system. Today, sentinels run as ad-hoc agent sessions that die when terminals close, orchestrations are started manually from CLI, and errors are handled reactively within narrow agent contexts. There is no persistent control plane, no structured issue lifecycle, and no human-in-the-loop decision points for error resolution.

The proposal defines a `set-manager` systemd service that provides process supervision (sentinel/orchestrator lifecycle) and issue management (detect → investigate → fix pipeline). This design document covers the key technical decisions.

## Goals / Non-Goals

**Goals:**
- Persistent service that survives terminal closure, auto-restarts on crash
- Deterministic Python state machine controlling all issue lifecycle transitions
- LLM agents only do investigation (read-only) and fixing (opsx workflow)
- GUI-driven process control (start/stop sentinel and orchestration from set-web)
- Max 1 fix at a time, sequential, in set-core directory
- Full audit trail for every action

**Non-Goals:**
- Distributed/multi-machine deployment (single machine only)
- Replacing the existing sentinel poll/findings mechanism (coexist, layer above)
- Real-time streaming of investigation output (poll-based is fine)
- Windows support (Linux systemd primary, macOS launchd documented as alternative)

## Decisions

### D1: Service architecture — single process with subprocess management

**Decision:** set-manager is one Python process that spawns sentinels and orchestrators as subprocesses. Not a microservice mesh.

**Alternatives considered:**
- **Separate systemd units per sentinel** — cleaner isolation but requires dynamic systemd unit creation, which is fragile and hard to debug
- **Docker containers** — overkill for a developer tool, adds deployment complexity
- **Single process, everything in-thread** — simpler but sentinel crash would take down the manager

**Rationale:** subprocess model gives process isolation (sentinel crash doesn't kill manager) with simple lifecycle management (just PIDs). The manager's tick loop checks PIDs and restarts dead processes. This matches how the orchestrator already manages worktree agents.

### D2: Issue state machine — 13 states, DIAGNOSED as deliberate pause point

**Decision:** 13 states with strict transition validation. DIAGNOSED is a waiting state where no automatic processing happens — routing is done once by `_apply_post_diagnosis_policy()` immediately after investigation completes.

**Alternatives considered:**
- **Fewer states** (merge FIXING/VERIFYING/DEPLOYING into one) — loses visibility into fix progress
- **Event-driven** instead of polling — more complex, harder to debug, overkill for 5s tick intervals

**Rationale:** The state machine must be debuggable. With 5s tick intervals, polling is fine. Each state represents a distinct phase visible in the UI. DIAGNOSED as a pause point prevents the machine from auto-routing issues on every tick, which would fight with manual user actions.

### D3: Investigation runs in set-core directory, not project directory

**Decision:** Investigation agents run with `cwd=set-core-repo`. They read project files via absolute paths from `issue.environment_path`.

**Alternatives considered:**
- **Run in project directory** — gives the agent direct access to project files, but the investigation may need to read set-core source code too (to understand framework behavior)
- **Run in a temporary directory** — isolated but too limited

**Rationale:** Most issues are caused by set-core behavior (gate logic, merge strategy, dispatch). The agent needs set-core source access. It can read project files via absolute path. Fixes also happen in set-core, so keeping both in the same cwd is consistent.

### D4: Fix runs as opsx workflow in set-core, max 1 at a time

**Decision:** Fix agent runs `claude -p` with opsx commands (`/opsx:ff`, `/opsx:apply`, `/opsx:verify`, `/opsx:archive`) in the set-core directory. Only one fix can run at a time.

**Alternatives considered:**
- **Parallel fixes in worktrees** — tempting for throughput, but git conflicts between parallel opsx changes are likely, and the whole point is careful investigation-first fixing
- **Manual fix workflow** (human runs opsx) — defeats the purpose of automation

**Rationale:** Sequential fixes are safer and simpler. Each fix is a small, focused opsx change. The bottleneck is investigation quality, not fix throughput. If a fix takes too long, the user can cancel it.

### D5: Deploy = `set-project init` to target projects

**Decision:** After a fix is verified in set-core, deployment means running `set-project init` on projects that need the update. This copies updated `.claude/` files, skills, and templates to the project.

**Alternatives considered:**
- **Git-based deployment** (push to project repo) — only works if project tracks set-core as dependency
- **Symlink-based** — fragile, cross-filesystem issues

**Rationale:** `set-project init` is the established deployment mechanism. It's idempotent, works on any project layout, and handles template merging. The deployer runs it on the source environment and optionally on all registered projects.

### D6: Sentinel spawning — claude agent with skill prompt

**Decision:** Manager spawns sentinels as `claude -p --prompt "..."` subprocesses. The prompt instructs the agent to run the sentinel skill for the specific project.

**Alternatives considered:**
- **Pure Python sentinel** (no LLM) — simpler but loses the sentinel's ability to make nuanced decisions about errors, write findings with context
- **MCP tool call** — requires MCP server running, adds dependency

**Rationale:** The sentinel's value comes from LLM-powered analysis of orchestration state. A pure Python poller could detect crashes and timeouts, but can't write nuanced findings. The existing sentinel skill works well — we just need to spawn it from a persistent service instead of a manual terminal.

### D7: Severity starts as "unknown", investigation determines it

**Decision:** All issues register with `severity: "unknown"`. The investigation agent's diagnosis sets the actual severity. Policy rules treat `unknown` as "always investigate first, never auto-fix".

**Alternatives considered:**
- **Heuristic severity from source** (gate failure = high, watchdog = medium) — pre-judges before investigation
- **LLM-based triage** before investigation — adds latency without much value, investigation does this anyway

**Rationale:** Source-based heuristics are unreliable (a gate failure could be a typo or a fundamental architecture issue). The investigation is cheap (5 min, one agent) and produces a much better severity assessment. Unknown severity naturally gates auto-fix behind investigation.

### D8: Communication — file-based with REST API

**Decision:** Sentinel writes findings to `.set/sentinel/findings.json` (existing). Manager reads this file in its tick loop (DetectionBridge). Web UI communicates via REST API to manager. No message queue or pubsub.

**Alternatives considered:**
- **Unix sockets** between sentinel and manager — faster but more complex
- **Shared SQLite** — good for queries but overkill, all data fits in JSON
- **Redis/message queue** — way overkill for single-machine

**Rationale:** File-based communication already works for sentinel → engine today. The manager just reads the same files. REST API for web → manager is standard and simple. The 5s tick interval means no need for real-time push.

### D9: Systemd for lifecycle, user-level units

**Decision:** Use `systemd --user` units (not system-level). This means no root required, works in user space.

**Alternatives considered:**
- **System-level systemd** — requires root, not appropriate for dev tools
- **supervisord** — another dependency to install
- **pm2** — Node.js based, wrong ecosystem
- **Custom daemonize** — reinventing the wheel

**Rationale:** `systemd --user` is available on all modern Linux, requires no root, supports auto-restart, logging (journalctl), and dependencies between units. For macOS, document launchd plist equivalent.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Investigation agent produces unparseable output | Issue stuck in DIAGNOSED with no diagnosis | Fallback Diagnosis with confidence=0.0, raw_output preserved for human review |
| Sentinel auto-restart loop on persistent failure | CPU waste, log spam | Crash count tracking + exponential backoff (max 5 restarts, then stop + alert) |
| Fix agent modifies set-core in unexpected ways | Broken set-core | opsx:verify gate catches regressions; max 1 fix at a time; user can cancel |
| Cross-env index race condition (2 managers?) | Corrupted index | Only one set-manager should run; PID lock file prevents duplicate |
| File-based registry grows large over time | Slow reads | Periodic archival of RESOLVED/DISMISSED issues (> 30 days) to archive.jsonl |
| macOS has no systemd | Can't auto-restart | Document launchd plist; fallback to foreground `set-manager serve` |

## Migration Plan

1. **Phase 1**: Create `lib/set_orch/issues/` module with state machine, registry, policy — testable standalone
2. **Phase 2**: Create `lib/set_orch/manager/` service with supervisor, REST API — can run in foreground
3. **Phase 3**: Add systemd unit, CLI, detection bridge integration
4. **Phase 4**: Integration test with a real sentinel + orchestration

No existing behavior changes. The manager is additive — sentinels can still be started manually as before. The manager just provides a better way.

## Open Questions

1. **PID lock file location** — `~/.local/share/set-core/manager/manager.pid` or `/run/user/$UID/set-manager.pid`?
2. **REST API framework** — reuse the existing aiohttp from set-web, or use a lightweight framework like FastAPI for the manager? Leaning toward aiohttp for consistency.
3. **Sentinel session persistence** — should the manager track claude session IDs so sentinels can be resumed after crash? Or always start fresh?
