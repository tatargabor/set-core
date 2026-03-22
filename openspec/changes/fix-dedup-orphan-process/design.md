# Design: fix-dedup-orphan-process

## Context

The dedup process chain looks like this:

```
caller (MCP/orch_memory)
  └─ subprocess.run(["set-memory", "dedup"], timeout=30)
       └─ bash: cmd_dedup()
            └─ run_shodh_python -c "$_DEDUP_PYTHON"
                 └─ python3 -c "...SequenceMatcher O(n²)..."
```

When `subprocess.run` times out, it sends SIGTERM to the direct child (bash). But `run_shodh_python` spawns a new `python3` process which is NOT in the same process group — so it survives as an orphan adopted by systemd (PID 1), spinning at 100% CPU forever.

## Goals

- Orphan python processes are impossible after timeout
- Defense in depth: timeout at multiple layers (bash + caller)
- No behavior change for normal (fast) dedup runs

## Non-Goals

- Algorithmic optimization of the O(n²) dedup (separate change)
- Changing the dedup scoring or clustering logic

## Decisions

### Decision 1: Process group kill in `_run_memory()`

Use `start_new_session=True` in `subprocess.Popen` so the child gets its own process group. On timeout, kill the entire group with `os.killpg()`.

**Why not just `subprocess.run()`?** `subprocess.run` with timeout only kills the direct child PID, not grandchildren. We need `Popen` + manual `killpg` for correct cleanup.

**Alternative considered:** Using `setsid` wrapper in bash — rejected because the Python caller is the right place to own lifecycle.

### Decision 2: Bash-level `timeout` in `cmd_dedup()`

Wrap the `run_shodh_python` call with the `timeout` coreutils command. This provides defense-in-depth: even if called directly from CLI without the MCP timeout layer, the python process cannot run forever.

The bash timeout should be slightly less than the caller timeout (25s vs 30s) so the bash layer cleans up before the caller force-kills.

### Decision 3: Apply same pattern to `cmd_audit()`

The audit command uses the same inline Python with the same O(n²) algorithm. Apply identical timeout protection.

## Risks / Trade-offs

- [Risk] Legitimate large dedup may be killed by timeout → Mitigation: 25s is generous for normal stores (<500 memories). For larger stores, the O(n²) algorithm needs replacement anyway (separate change).
- [Risk] `os.killpg` on wrong PGID → Mitigation: Only called inside timeout exception handler, PGID comes from the process we spawned with `start_new_session=True`.
