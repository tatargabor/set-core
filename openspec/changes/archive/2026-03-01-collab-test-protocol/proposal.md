## Why

We need a reproducible end-to-end integration test for wt-tools cross-machine collaboration features (team sync, messaging, broadcasting, ralph loop). These features were developed on Linux and need validation on macOS, and more importantly, we need to verify the full collaboration pipeline works when two agents on different machines coordinate real work together. There is currently no way to systematically test this — only manual ad-hoc checks.

## What Changes

- Create a separate test repository (`wt-sharing-teszt`) with a structured collaboration protocol
- Two agents (on Mac + Linux) each run ralph loop with role-specific task files
- Developer agent builds a restaurant website, Tester agent writes tests — coordinating via `wt:msg`, `wt:broadcast`, `wt:status`, `wt:inbox`
- A `reset.sh` script enables repeatable test runs
- Protocol refinements are tracked here in wt-tools via OpenSpec; the test repo contains only the protocol files and generated work products

## Capabilities

### New Capabilities
- `collab-test-protocol`: The test protocol itself — spec.md (business requirements), tasks-dev.md (developer ralph loop tasks), tasks-test.md (tester ralph loop tasks), CLAUDE.md (agent rules), reset.sh (cleanup script). Lives in the external `wt-sharing-teszt` repo.

### Modified Capabilities
<!-- No wt-tools spec changes needed — this is a test protocol, not a feature change -->

## Impact

- **External repo**: `tatargabor/wt-sharing-teszt` on GitHub — contains all test protocol files
- **wt-tools features exercised**: `wt:msg`, `wt:inbox`, `wt:broadcast`, `wt:status`, ralph loop (`wt:loop`), team sync (`wt-control-sync`), worktree operations (`wt-new`, `wt-work`)
- **Machines needed**: Minimum 2 (currently Mac Mini + Linux desktop), both with wt-tools installed
- **No code changes to wt-tools** — this change documents and refines the test protocol. Bug fixes found during testing become separate changes.
