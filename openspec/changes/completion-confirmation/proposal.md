# Proposal: Completion Confirmation

## Why

When an orchestration run completes (all changes merged/failed), the sentinel either:
1. Exits cleanly — but the user doesn't know it's done until they check
2. Enters a rapid restart cycle — burning resources and creating noise
3. Re-plans from scratch — destroying the completed state (the Run #7 incident)

There's no interactive "what next?" moment. The user must manually check status, manually kill processes, and manually decide whether to re-run or move on.

## What Changes

Add a **completion confirmation prompt** across three interfaces — any one can respond, the first response wins.

### Flow

```
All changes terminal (merged/failed/skipped)
  │
  ├─ Sentinel: print CLI prompt (stdin if interactive, else auto-stop)
  ├─ Dashboard: show completion card with action buttons
  └─ Discord: send embed with reaction buttons
  │
  ▼
Wait for response (timeout: configurable, default 5min)
  │
  ├─ "Accept & Stop" → clean exit, generate final report
  ├─ "Re-run" → reset orchestration (--fresh), restart with same spec
  ├─ "New spec" → prompt for spec path, spec-switch reset, restart
  └─ Timeout → auto-stop (default), generate report
```

### 1. Sentinel CLI (bash layer)

**Where**: `bin/set-sentinel`, after `_check_completion` returns true.

```bash
completion_prompt() {
    local timeout="${COMPLETION_TIMEOUT:-300}"  # 5 min default

    # Non-interactive (nohup, background) → auto-stop
    if [[ ! -t 0 ]]; then
        sentinel_log "Orchestration complete — auto-stopping (non-interactive)"
        return 0  # accept
    fi

    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║  Orchestration Complete               ║"
    echo "╠═══════════════════════════════════════╣"
    echo "║  [1] Accept & Stop (default in ${timeout}s) ║"
    echo "║  [2] Re-run same spec (--fresh)       ║"
    echo "║  [3] New spec path                    ║"
    echo "╚═══════════════════════════════════════╝"

    read -t "$timeout" -p "Choice [1]: " choice
    case "${choice:-1}" in
        1) return 0 ;;  # accept
        2) return 2 ;;  # re-run
        3) return 3 ;;  # new spec
        *) return 0 ;;  # default accept
    esac
}
```

### 2. Dashboard (web API + frontend)

**Where**: `web/src/pages/Dashboard.tsx` + `lib/set_orch/api.py`

- New API endpoint: `POST /api/{project}/completion-action` with body `{"action": "accept|rerun|newspec", "spec_path": "..."}`
- Dashboard shows a completion card when state is "done" with 3 buttons
- Buttons call the API which writes to sentinel inbox (`set-sentinel-inbox`)
- Sentinel reads inbox in its poll loop and acts on the response

### 3. Discord (bot layer)

**Where**: `lib/set_orch/discord/embeds.py` + `events.py`

- On orchestration complete event, send embed with reaction buttons (✅ 🔄 📋)
- Bot watches for reactions on the completion message
- On reaction, writes to sentinel inbox (same mechanism as dashboard)

### 4. Sentinel Inbox Integration

The sentinel already has `sentinel_check_inbox()` which reads messages. Extend it to handle completion actions:

```bash
# In sentinel poll loop, after completion detected:
if [[ "$completion_pending" == "true" ]]; then
    local inbox_action
    inbox_action=$(sentinel_check_completion_inbox)
    case "$inbox_action" in
        "accept") break ;;
        "rerun") FRESH_FLAG=true; continue ;;
        "newspec:*") SPEC_ARG="${inbox_action#newspec:}"; continue ;;
    esac
fi
```

### 5. Completion State

Add a new state: `"awaiting_confirmation"` between the last merge and clean exit. This state:
- Prevents auto-restart (sentinel sees it as non-terminal)
- Signals to dashboard/Discord that confirmation is needed
- Times out to "done" after the configured period

## Capabilities

### New Capabilities
- `completion-prompt`: Interactive completion confirmation across CLI, web, Discord
- `completion-state`: New "awaiting_confirmation" state in orchestration lifecycle
- `completion-inbox`: Sentinel inbox extension for completion actions

### Modified Capabilities
- `sentinel-exit`: No longer immediate on completion — waits for confirmation
- `dashboard-state`: Shows completion card with action buttons
- `discord-events`: Sends completion embed with reaction buttons

## Risk

**Low-Medium**.

| Risk | Mitigation |
|------|-----------|
| Non-interactive sessions hang | Auto-detect `! -t 0`, auto-stop immediately |
| Dashboard/Discord response lost | Timeout fallback (configurable, default 5min) |
| Multiple interfaces respond simultaneously | First-wins: sentinel inbox is FIFO, first action processed |
| New state confuses existing tooling | "awaiting_confirmation" treated as terminal by monitor (no dispatch) |

## Scope

### In Scope
- Sentinel completion prompt (CLI)
- Dashboard completion card (web)
- Discord completion embed with reactions
- Sentinel inbox extension for completion actions
- `awaiting_confirmation` state
- Configurable timeout
- Auto-stop for non-interactive sessions

### Out of Scope
- Partial completion confirmation (some merged, some failed — existing "stopped" handles this)
- Multi-user approval (first response wins)
- Persistent completion history (run tracking)
