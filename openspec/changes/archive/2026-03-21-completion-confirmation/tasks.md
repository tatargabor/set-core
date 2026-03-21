# Tasks: completion-confirmation

## 1. State model extension

- [x] 1.1 Add `awaiting_confirmation` to terminal states in `lib/set_orch/engine.py` — no dispatch, no restart
- [x] 1.2 Update `is_transient_failure()` in `bin/set-sentinel` — `awaiting_confirmation` is NOT transient (don't restart)
- [x] 1.3 Add `completion_timeout` directive parsing in `lib/set_orch/config.py` (default 300s)

## 2. Sentinel CLI prompt

- [x] 2.1 Add `completion_prompt()` logic to `bin/set-sentinel` — interactive prompt with Accept/Re-run/New-spec, read with timeout
- [x] 2.2 Add inbox polling for non-interactive mode — polls for `completion_action` messages with timeout countdown
- [x] 2.3 Integrate into main loop — after done/awaiting_confirmation status, handle response (accept→exit, rerun→fresh restart, newspec→spec-switch)

## 3. Sentinel inbox extension

- [x] 3.1 Inbox handles `completion_action` message type via existing `set-sentinel-inbox` check
- [x] 3.2 Sentinel parses completion action from inbox JSON (action + optional spec path)

## 4. Dashboard completion card

- [x] 4.1 Add `POST /api/{project}/completion` endpoint to `lib/set_orch/api.py` — validates action, writes to sentinel inbox
- [x] 4.2 Create `web/src/components/CompletionCard.tsx` — Accept/Re-run/New Spec buttons + spec path input
- [x] 4.3 Integrate `CompletionCard` into `Dashboard.tsx` — shown when state is `done` or `awaiting_confirmation`

## 5. Discord completion embed

- [x] 5.1 Add `build_completion_confirmation_embed()` to `lib/set_orch/discord/embeds.py` — summary + reaction instructions
- [x] 5.2 Handle completion in `events.py` — send confirmation embed with ✅🔄📋 reactions instead of plain summary
- [x] 5.3 Add `on_reaction_add` handler in `discord/__init__.py` — maps reactions to `set-sentinel-inbox send` calls
- [x] 5.4 Reactions cleaned up after action processed (clear_reactions call)

## 6. Tests

- [x] 6.1 Interactive sentinel: completion prompt logic integrated with read -t timeout
- [x] 6.2 Non-interactive: auto-stop via inbox poll timeout
- [x] 6.3 Dashboard API: POST /api/{project}/completion writes to inbox
- [x] 6.4 Inbox completion action triggers correct sentinel response (accept/rerun/newspec)
