# Design: Process Manager UI

## Context

The orchestration pipeline spawns a tree of processes: sentinel → orchestrator → ralph loops → claude agents. Currently there's no way to see or stop these from the web UI. The Settings page shows PIDs but no kill buttons.

## Goals / Non-Goals

**Goals:** Process tree discovery API, tree visualization on Settings, graceful shutdown button
**Non-Goals:** Process starting (sentinel page handles that), log viewing, auto-restart

## Decisions

### D1: Process discovery via PID files + ps tree

The sentinel writes its PID to `.set/sentinel.pid`, the orchestrator to `.set/orchestrator.pid`. From these root PIDs, use `ps --ppid` recursively to find the full child tree. This avoids grep-based discovery which is fragile.

```python
def _get_process_tree(root_pid: int) -> dict:
    info = _process_info(root_pid)  # pid, cmd, uptime, cpu, mem
    children = _get_children(root_pid)  # ps --ppid
    info["children"] = [_get_process_tree(c) for c in children]
    return info
```

### D2: Stop order — bottom-up with timeout

Stop All sends SIGTERM to leaves first, waits 3s, then moves up. If a process doesn't exit after SIGTERM + 3s, send SIGKILL. Order: claude agents → ralph loops → orchestrator → sentinel. Finally set orchestration state to "stopped".

### D3: UI on Settings page

Add a "Processes" section after the "Runtime" section. Uses a recursive tree component with indentation. Each row: `PID  command (truncated)  uptime  CPU%  MEM  [Stop]`. Top-level "Stop All" button with confirmation.

### D4: Polling — 5s refresh

The process tree auto-refreshes every 5 seconds (matches the state polling interval). After Stop All, immediately refetch.

## Risks / Trade-offs

- [Risk] PID files stale after crash → check if PID is alive before showing
- [Risk] Permission issues killing processes → API runs as same user, should be fine
