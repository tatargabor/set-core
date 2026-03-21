# Design: Completion Confirmation

## Architecture

Three response channels feed into one decision point (sentinel inbox). The sentinel owns the decision — dashboard and Discord are input sources, not decision makers.

```
                    ┌─────────────┐
                    │   Sentinel   │
                    │  (decision)  │
                    └──────┬──────┘
                           │ reads inbox
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │ CLI stdin  │ │ Inbox │ │ Inbox     │
        │ (if -t 0)  │ │ (web) │ │ (discord) │
        └───────────┘ └───────┘ └───────────┘
```

### State Machine Extension

```
merged/failed/skipped (all terminal)
  → awaiting_confirmation (new state)
    → done (accept or timeout)
    → running (re-run: spec-switch reset + restart)
```

### Implementation Layers

#### Layer 1: Sentinel (`bin/set-sentinel`)

After `_check_completion` returns true in the main loop:

1. Set state to `awaiting_confirmation`
2. Emit `ORCHESTRATION_AWAITING_CONFIRMATION` event
3. If interactive (`-t 0`): show CLI prompt, read choice
4. If non-interactive: start timeout countdown, poll inbox
5. On response or timeout: execute action

The completion prompt replaces the current direct exit path.

#### Layer 2: Dashboard (`web/` + `lib/set_orch/api.py`)

- **API**: `POST /api/{project}/completion` — accepts `{"action": "accept|rerun|newspec", "spec": "..."}`
- **API handler**: writes to sentinel inbox file (`set-sentinel-inbox send`)
- **Frontend**: `CompletionCard` component — shown when state is `awaiting_confirmation`
- **Buttons**: Accept, Re-run, New Spec (with spec path input)
- **Countdown**: shows remaining time before auto-stop

#### Layer 3: Discord (`lib/set_orch/discord/`)

- **On `ORCHESTRATION_AWAITING_CONFIRMATION` event**: send embed with summary + reaction buttons
- **Reaction handler**: maps ✅→accept, 🔄→rerun, 📋→newspec
- **On reaction**: calls `set-sentinel-inbox send` with action
- **Auto-cleanup**: remove reactions after action processed

### Inbox Protocol

The sentinel inbox already exists (`bin/set-sentinel-inbox`). Extend the message format:

```json
{"type": "completion_action", "action": "accept"}
{"type": "completion_action", "action": "rerun"}
{"type": "completion_action", "action": "newspec", "spec": "docs/v2.md"}
```

The sentinel checks inbox during the confirmation wait loop. First `completion_action` message wins.

### Timeout Behavior

- **Interactive** (terminal): `read -t $timeout` — bash handles it
- **Non-interactive** (nohup/background): poll inbox every 5s, count down from `COMPLETION_TIMEOUT`
- **Default timeout**: 300s (5 min) — configurable via `completion_timeout` directive in config.yaml
- **On timeout**: auto-accept (clean stop), generate report

### State File Changes

Add `awaiting_confirmation` to terminal states list in `engine.py` (so monitor doesn't dispatch new changes):

```python
terminal_statuses = {"merged", "done", "skipped", "failed", "merge-blocked",
                     "integration-failed", "awaiting_confirmation"}
```

But NOT in the `is_transient_failure` list — sentinel should NOT restart on this state.

## Dependencies

- Sentinel inbox (`bin/set-sentinel-inbox`) — exists
- Dashboard API (`lib/set_orch/api.py`) — exists
- Discord bot (`lib/set_orch/discord/`) — exists
- State model (`lib/set_orch/state.py`) — extend
