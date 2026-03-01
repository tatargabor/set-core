# Sentinel — Intelligent Orchestration Supervisor

Start and supervise a `wt-orchestrate` run with intelligent crash recovery, checkpoint handling, and completion reporting.

**Arguments:** `[wt-orchestrate start options...]`

## Instructions

You are the sentinel — an intelligent supervisor for `wt-orchestrate`. Your job is to start the orchestrator, monitor it, and make informed decisions when things go wrong or need attention.

### Step 1: Start the orchestrator in background

```bash
# Start orchestrator — all arguments are passed through
wt-orchestrate start $ARGUMENTS &
ORCH_PID=$!
echo "Orchestrator started (PID: $ORCH_PID)"
```

### Step 2: Run the poll loop

Run this bash poll script. It stays in bash (no LLM cost) and only breaks out when a decision is needed:

```bash
STATE_FILE="orchestration-state.json"
LOG_FILE="orchestration.log"
ORCH_PID=<the PID from step 1>
RAPID_CRASHES=0
MAX_RAPID=5
SUSTAINED_SECS=300

while true; do
    sleep 15

    # Check if orchestrator process is still alive
    if ! kill -0 "$ORCH_PID" 2>/dev/null; then
        wait "$ORCH_PID" 2>/dev/null || true
        EXIT_CODE=$?
        STATUS=$(jq -r '.status // "unknown"' "$STATE_FILE" 2>/dev/null || echo "unknown")
        echo "EVENT:process_exit|exit_code=$EXIT_CODE|status=$STATUS"
        break
    fi

    # Read current state
    STATUS=$(jq -r '.status // "unknown"' "$STATE_FILE" 2>/dev/null || echo "unknown")

    # Terminal states
    if [[ "$STATUS" == "done" || "$STATUS" == "stopped" || "$STATUS" == "time_limit" ]]; then
        echo "EVENT:terminal|status=$STATUS"
        break
    fi

    # Checkpoint needs decision
    if [[ "$STATUS" == "checkpoint" ]]; then
        REASON=$(jq -r '.checkpoints[-1].reason // "unknown"' "$STATE_FILE" 2>/dev/null || echo "unknown")
        APPROVED=$(jq -r '.checkpoints[-1].approved // false' "$STATE_FILE" 2>/dev/null || echo "false")
        if [[ "$APPROVED" == "true" ]]; then
            true  # already approved, continue polling
        else
            echo "EVENT:checkpoint|reason=$REASON"
            break
        fi
    fi

    # Stale detection: state says running but file hasn't been updated in >120s
    if [[ "$STATUS" == "running" && -f "$STATE_FILE" ]]; then
        MTIME=$(stat -c %Y "$STATE_FILE" 2>/dev/null || stat -f %m "$STATE_FILE" 2>/dev/null || echo 0)
        NOW=$(date +%s)
        AGE=$(( NOW - MTIME ))
        if [[ $AGE -gt 120 ]]; then
            echo "EVENT:stale|age=${AGE}s|status=$STATUS"
            break
        fi
    fi
done
```

When the poll loop breaks, **you decide what to do** based on the EVENT line.

### Step 3: Decision tree

Process the event returned by the poll loop:

#### EVENT: terminal

| Status | Action |
|--------|--------|
| `done` | Produce final report (see Step 5), stop |
| `stopped` | Report "User stopped orchestration", stop |
| `time_limit` | Summarize progress (changes done/total, tokens, time elapsed), stop |

#### EVENT: process_exit (crash)

The orchestrator exited unexpectedly. **Read the last 50 lines of orchestration.log** and the state.json to diagnose:

1. Read the logs:
   ```bash
   tail -50 orchestration.log
   ```
2. Read the state:
   ```bash
   cat orchestration-state.json
   ```
3. Classify the error:

   **Recoverable** (restart after 30s):
   - `jq: error` — transient JSON parse failure
   - `flock` timeout — temporary lock contention
   - Network/DNS errors — transient connectivity
   - `SIGPIPE` or `broken pipe` — ephemeral I/O issue
   - Claude API rate limit or 5xx errors

   **Fatal** (stop and report):
   - `No such file or directory` for critical paths
   - Authentication/permission errors
   - `command not found` — missing dependency
   - Disk space errors
   - State file corruption (invalid JSON in state.json)

   **Unknown** — restart once. If the same error recurs on the next crash, stop and report.

4. Track rapid crashes: if the orchestrator ran less than 5 minutes before crashing, increment the counter. After 5 rapid crashes, **stop regardless of diagnosis**.

5. Before restarting, fix stale state:
   - If state is `running` → reset to `stopped` (so orchestrator can resume)
   - If state is `checkpoint` → leave as-is
   - Other states → leave as-is

6. Restart:
   ```bash
   sleep 30
   wt-orchestrate start $ARGUMENTS &
   ORCH_PID=$!
   ```
   Then go back to Step 2 (poll loop).

#### EVENT: checkpoint

Read the checkpoint reason from the event. Decision:

**If reason is `periodic`** — auto-approve:
```bash
# Read state, approve latest checkpoint, atomic write
python3 -c "
import json, os, tempfile
from datetime import datetime, timezone
with open('orchestration-state.json') as f:
    data = json.load(f)
if data.get('checkpoints'):
    data['checkpoints'][-1]['approved'] = True
    data['checkpoints'][-1]['approved_at'] = datetime.now(timezone.utc).isoformat()
fd, tmp = tempfile.mkstemp(dir='.', suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(data, f, indent=2)
os.rename(tmp, 'orchestration-state.json')
print('Checkpoint auto-approved (reason: periodic)')
"
```
Then go back to Step 2 (poll loop).

**If reason is anything else** (e.g., `budget_exceeded`, `too_many_failures`, `manual`):
- Report the checkpoint reason and current orchestration status to the user
- Wait for user input on whether to approve or stop
- Do NOT auto-approve non-periodic checkpoints

#### EVENT: stale

The state file hasn't been updated in >120s while status is "running":

1. Check if the orchestrator PID is still alive:
   ```bash
   kill -0 $ORCH_PID 2>/dev/null && echo "alive" || echo "dead"
   ```
2. Read last 20 log lines to understand what's happening
3. If PID alive + logs show activity → likely a long operation, continue monitoring (go back to Step 2)
4. If PID dead → treat as crash (go to process_exit handling)
5. If PID alive but no log activity for >5 minutes → report to user as potential hang

### Step 4: Restart tracking

Maintain these counters across the session:
- `restart_count`: total restarts in this sentinel session
- `rapid_crashes`: consecutive crashes with <5min runtime (reset on sustained run)
- `last_error`: summary of last crash for the report

### Step 5: Completion report

When the orchestration reaches a terminal state, produce this report by reading state.json:

```bash
cat orchestration-state.json
```

Then format:

```
## Orchestration Report

- **Status**: done / time_limit / failed / stopped
- **Duration**: Xh Ym active / Xh Ym wall clock
- **Changes**: N/M complete (list failed ones if any)
- **Tokens**: X.XM total
- **Replan cycles**: N
- **Sentinel restarts**: N (with reasons if any)
- **Issues**: Notable errors or warnings from the run
```

Read `active_seconds`, `started_epoch`, `changes[]`, `prev_total_tokens`, `replan_cycle` from state.json to fill in the report.

## Examples

```bash
# Basic — supervise orchestration with defaults
/wt:sentinel

# With spec and parallel limit
/wt:sentinel --spec docs/v5.md --max-parallel 3

# With time limit
/wt:sentinel --time-limit 4h
```

## What happens

1. Orchestrator starts in background
2. Sentinel polls state.json every 15 seconds (no LLM cost during normal operation)
3. On events (crash, checkpoint, completion, stale), the agent makes a decision
4. Periodic checkpoints are auto-approved
5. Crashes are diagnosed from log analysis before restarting
6. On completion or failure, a summary report is produced
