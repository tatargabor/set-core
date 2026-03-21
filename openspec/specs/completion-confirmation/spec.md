# Spec: Completion Confirmation

## Requirements

### REQ-CC-001: Awaiting Confirmation State
The orchestration state machine MUST support an `awaiting_confirmation` state between completion detection and clean exit.

**Acceptance Criteria:**
- [ ] `awaiting_confirmation` added to terminal states in engine.py (no dispatch)
- [ ] Monitor does NOT restart when state is `awaiting_confirmation`
- [ ] Sentinel does NOT treat `awaiting_confirmation` as a crash
- [ ] State transitions: merged/failed → awaiting_confirmation → done/running

### REQ-CC-002: Sentinel CLI Prompt
When orchestration completes in an interactive terminal, the sentinel MUST display a completion prompt with Accept/Re-run/New-spec options.

**Acceptance Criteria:**
- [ ] Prompt shown after all changes are terminal
- [ ] `read -t $timeout` with configurable timeout (default 300s)
- [ ] Accept → clean exit + report
- [ ] Re-run → spec-switch reset + restart same spec
- [ ] New spec → prompt for path, spec-switch reset + restart
- [ ] Non-interactive sessions auto-stop without prompt

### REQ-CC-003: Sentinel Inbox Completion Actions
The sentinel inbox MUST accept `completion_action` messages from external sources (dashboard, Discord).

**Acceptance Criteria:**
- [ ] Inbox message format: `{"type": "completion_action", "action": "accept|rerun|newspec", "spec": "..."}`
- [ ] Sentinel polls inbox during confirmation wait
- [ ] First action message processed, subsequent ignored
- [ ] Actions trigger same behavior as CLI prompt choices

### REQ-CC-004: Dashboard Completion Card
The web dashboard MUST show a completion card with action buttons when state is `awaiting_confirmation`.

**Acceptance Criteria:**
- [ ] `CompletionCard` component shown on Changes tab when state is `awaiting_confirmation`
- [ ] Three buttons: Accept & Stop, Re-run, New Spec
- [ ] New Spec shows text input for spec path
- [ ] Countdown timer showing remaining auto-stop time
- [ ] API endpoint `POST /api/{project}/completion` sends action to sentinel inbox

### REQ-CC-005: Discord Completion Embed
The Discord bot MUST send a completion embed with reaction buttons when orchestration enters `awaiting_confirmation`.

**Acceptance Criteria:**
- [ ] Embed shows run summary (merged/failed/tokens/duration)
- [ ] Reactions: ✅ Accept, 🔄 Re-run, 📋 New spec
- [ ] Reaction handler sends action to sentinel inbox
- [ ] Reactions cleaned up after action processed

### REQ-CC-006: Configurable Timeout
The completion confirmation timeout MUST be configurable via orchestration config.

**Acceptance Criteria:**
- [ ] `completion_timeout` directive in config.yaml (seconds, default 300)
- [ ] Sentinel reads from directives
- [ ] Dashboard shows countdown from configured timeout
