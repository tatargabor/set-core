## MODIFIED Requirements

### R2: Action Hash Loop Detection (MODIFIED)
- Each poll cycle, compute hash of observable change state: `(loop-state mtime, tokens_used, ralph_status)`
- **Skip hash-based loop detection when loop-state.json does not exist yet** — this indicates the change is in artifact creation phase (proposal, design, specs, tasks) before the Ralph loop starts
- Maintain a ring buffer of last N hashes per change (default N=5)
- If `watchdog_loop_threshold` (default 5) consecutive hashes are identical, the change is stuck
- Stuck detection triggers escalation (R4)

### R7: Artifact Creation Grace (ADDED)
- When a change has status `running` but no `loop-state.json` file exists, the watchdog skips hash-based loop detection
- The existing timeout detection (R1) with PID-alive guard remains active as the safety net
- Once `loop-state.json` appears, normal hash-based detection resumes
- This prevents false-positive kills during the 1-2 minute artifact creation phase after dispatch
