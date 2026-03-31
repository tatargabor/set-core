## Context

The dispatcher's `dispatch_via_wt_loop()` function reads `loop-state.json` after launching `set-loop` to extract the agent's terminal PID. A broad exception handler (`except (json.JSONDecodeError, OSError, ValueError, TypeError): pass`) swallows all errors, defaulting `terminal_pid` to 0. The change is then marked as "running" with `ralph_pid=0`, creating an orphaned change that sits stuck indefinitely.

The watchdog's PID-alive checks use `if ralph_pid and _is_pid_alive(ralph_pid)` — when `ralph_pid=0`, the falsy guard short-circuits and the watchdog treats it as a dead PID, but only after the normal timeout (120s+). There's no fast-path for "never had a valid PID."

## Goals / Non-Goals

**Goals:**
- Fail dispatch immediately when PID extraction yields 0/null
- Make PID extraction failures visible in logs
- Watchdog detects null-PID running changes immediately

**Non-Goals:**
- Changing how set-loop writes loop-state.json
- Modifying recover_orphaned_changes() (already handles PID=0 correctly)

## Decisions

**1. Fail dispatch on invalid PID rather than retry**
After the existing 10-second poll for loop-state.json, if PID extraction fails, mark as "failed" immediately. Rationale: if the JSON exists but lacks a valid PID, retrying won't help — the underlying set-loop launch likely failed. The orchestrator's existing retry/redispatch logic handles failed changes.

**2. Add early null-PID check in watchdog before timeout/loop checks**
Insert a check at the top of the running-change evaluation path: if `ralph_pid` is 0/null and status is "running", immediately escalate. This catches any edge case where a change slipped through with PID=0 (e.g., state file was manually edited).

## Risks / Trade-offs

- [Risk] A transient delay in loop-state.json writing could cause terminal_pid to be 0 momentarily → Mitigation: The existing 10-second poll already waits for the file to appear. By the time we read it, set-loop has had time to write the PID.
- [Risk] Changing exception handler could surface noisy errors for non-critical parse issues → Mitigation: Only log at error level, existing log rotation handles volume.
