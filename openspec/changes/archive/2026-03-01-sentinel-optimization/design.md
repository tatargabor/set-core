# Design: Sentinel Optimization

## Current Architecture

```
User: /wt:sentinel --spec docs/v6.md
  │
  ├─ Step 1: Start orchestrator in background (bash, instant)
  │   └─ wt-orchestrate start ... &
  │
  ├─ Step 2: Run poll loop (bash, 10-min timeout, BLOCKING)
  │   └─ while true; do sleep 15; check state; done
  │   └─ User CANNOT interact during this time
  │
  ├─ Step 3: LLM decision (Opus thinking, 5-15 min)
  │   └─ Re-analyze full context to decide action
  │   └─ Often: "still running, go back to step 2"
  │
  └─ Repeat steps 2-3 until terminal state
```

**Problem**: Step 2 blocks the UI. Step 3 is expensive for trivial decisions.

## New Architecture

```
User: /wt:sentinel --spec docs/v6.md
  │
  ├─ Step 1: Start orchestrator in background (bash, instant)
  │   └─ wt-orchestrate start ... &
  │
  ├─ Step 2: Start background poller (run_in_background, NON-BLOCKING)
  │   └─ sleep 30 && read state && echo EVENT:...
  │   └─ User CAN interact while this runs
  │
  ├─ Step 3: Background task completes → notification
  │   └─ LLM reads event, makes decision
  │   └─ If "still running" → restart step 2 (no thinking needed)
  │   └─ If event needs action → handle it
  │
  └─ User can ask questions anytime between polls
```

## Key Design Decisions

### 1. Single-shot poll with `run_in_background`

Instead of a bash while-loop, each poll cycle is a single bash command run with `run_in_background: true`. This returns control to the LLM immediately.

The poll command:
```bash
sleep 30
STATE_FILE="orchestration-state.json"
STATUS=$(jq -r '.status // "unknown"' "$STATE_FILE" 2>/dev/null || echo "unknown")

# Check process alive
if ! kill -0 $ORCH_PID 2>/dev/null; then
    echo "EVENT:process_exit|status=$STATUS"
    exit 0
fi

# Terminal states
if [[ "$STATUS" == "done" || "$STATUS" == "stopped" || "$STATUS" == "time_limit" ]]; then
    echo "EVENT:terminal|status=$STATUS"
    exit 0
fi

# Checkpoint
if [[ "$STATUS" == "checkpoint" ]]; then
    REASON=$(jq -r '.checkpoints[-1].reason // "unknown"' "$STATE_FILE" 2>/dev/null)
    APPROVED=$(jq -r '.checkpoints[-1].approved // false' "$STATE_FILE" 2>/dev/null)
    if [[ "$APPROVED" == "true" ]]; then
        echo "EVENT:running|status=checkpoint_approved"
    else
        echo "EVENT:checkpoint|reason=$REASON"
    fi
    exit 0
fi

# Stale detection
if [[ "$STATUS" == "running" && -f "$STATE_FILE" ]]; then
    MTIME=$(stat -c %Y "$STATE_FILE" 2>/dev/null || stat -f %m "$STATE_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$(( NOW - MTIME ))
    if [[ $AGE -gt 120 ]]; then
        echo "EVENT:stale|age=${AGE}s"
        exit 0
    fi
fi

echo "EVENT:running|status=$STATUS"
```

### 2. Trivial event handling without thinking

When the poll returns `EVENT:running`, the sentinel simply starts the next background poll — no analysis needed. The skill prompt instructs the LLM to handle this case with minimal output: just acknowledge and start next poll.

### 3. User interaction between polls

Since the poll runs in background, the user can type messages anytime. The sentinel responds normally. When the background poll completes, the notification arrives and the sentinel processes it after finishing the user interaction.

### 4. State tracking in the prompt

The sentinel tracks counters (restart_count, rapid_crashes) as local variables in the conversation. No external state file needed beyond the orchestrator's own state.json.

## File Changes

| File | Change |
|------|--------|
| `.claude/commands/wt/sentinel.md` | Rewrite poll loop to use single-shot background polls |
