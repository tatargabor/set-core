# Proposal: fix-dedup-orphan-process

## Why

The `set-memory dedup` command spawns a Python grandchild process for O(n²) pairwise similarity computation. When callers (MCP server, orchestration hooks) apply a timeout, the intermediate bash process is killed but the Python grandchild becomes an orphan running at 100% CPU indefinitely. This has been observed repeatedly in production — the orphan must be manually killed each time.

## What Changes

- **Process group kill**: Ensure timeout kills the entire process tree (bash + python grandchild), not just the direct child
- **Bash-level timeout**: Add a timeout guard inside `cmd_dedup()` itself so the Python process cannot run unboundedly even when called directly
- **MCP subprocess handling**: Use `start_new_session=True` in `_run_memory()` so `subprocess.run` timeout kills the whole process group

## Capabilities

### Modified Capabilities
- `memory-dedup` — Add process lifecycle requirements (timeout, orphan prevention)

## Impact

- `lib/memory/maintenance.sh` — `cmd_dedup()` gets timeout wrapper
- `mcp-server/set_mcp_server.py` — `_run_memory()` gets process group kill
- `lib/set_orch/orch_memory.py` — verify timeout propagation works correctly
