# Tasks: completion-confirmation

## 1. State model extension

- [ ] 1.1 Add `awaiting_confirmation` to terminal states in `lib/set_orch/engine.py` — no dispatch, no restart
- [ ] 1.2 Update `is_transient_failure()` in `bin/set-sentinel` — `awaiting_confirmation` is NOT transient (don't restart)
- [ ] 1.3 Add `completion_timeout` directive parsing in `lib/set_orch/config.py` (default 300s)

## 2. Sentinel CLI prompt

- [ ] 2.1 Add `completion_prompt()` function to `bin/set-sentinel` — interactive prompt with Accept/Re-run/New-spec, read with timeout
- [ ] 2.2 Add `completion_wait_inbox()` function — non-interactive: poll inbox for `completion_action` messages with timeout countdown
- [ ] 2.3 Integrate into main loop — after `_check_completion` returns true, set state to `awaiting_confirmation`, call prompt or inbox wait, handle response (accept→exit, rerun→fresh restart, newspec→spec-switch)

## 3. Sentinel inbox extension

- [ ] 3.1 Extend `bin/set-sentinel-inbox` to accept `completion_action` message type
- [ ] 3.2 Add `sentinel_check_completion_inbox()` to sentinel — reads and parses completion action messages

## 4. Dashboard completion card

- [ ] 4.1 Add `POST /api/{project}/completion` endpoint to `lib/set_orch/api.py` — validates action, writes to sentinel inbox via `set-sentinel-inbox send`
- [ ] 4.2 Create `web/src/components/CompletionCard.tsx` — shows when state is `awaiting_confirmation`, three buttons + countdown + optional spec input
- [ ] 4.3 Integrate `CompletionCard` into `Dashboard.tsx` — show above changes list when state is `awaiting_confirmation`

## 5. Discord completion embed

- [ ] 5.1 Add `build_completion_embed()` to `lib/set_orch/discord/embeds.py` — summary (merged/failed/tokens/duration) + instructions
- [ ] 5.2 Handle `ORCHESTRATION_AWAITING_CONFIRMATION` event in `lib/set_orch/discord/events.py` — send embed, add reactions (✅🔄📋)
- [ ] 5.3 Add reaction handler in Discord bot — map reactions to `set-sentinel-inbox send` calls
- [ ] 5.4 Clean up reactions after action processed

## 6. Tests

- [ ] 6.1 Test: interactive sentinel shows prompt on completion, accepts input
- [ ] 6.2 Test: non-interactive sentinel auto-stops after timeout
- [ ] 6.3 Test: dashboard API sends completion action to inbox
- [ ] 6.4 Test: inbox completion action triggers correct sentinel response
