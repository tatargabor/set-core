## Why

The owner, 2026-11-27, looking at a permission row on the relay board that said only "Allow or Deny on
the channel or in the terminal": *„akarok egy gombot hogy megnyomjam mit nem lehet?"* There was no
button, though the same person can press Allow or Deny on the channel.

The exclusion came from `fleet-relay-answer-own` D4: *"A permission prompt has two fixed answers …
Free text there invites an answer the runtime cannot read."* That reason is about **free text**, not
about the operator answering from the board. The hook already reads the answer fail-closed
(`question_relay.permission_output`: only the literal `Allow` allows), so the two fixed answers are
safe to offer as buttons.

## What Changes

- The relay board shows **Allow** and **Deny** buttons on a permission row (not on one handed back to
  the terminal). One click sends the operator's answer at once — the same answer store the channel
  writes.
- The answer route accepts a permission prompt **only** with exactly one answer that is `Allow` or
  `Deny` (whitespace trimmed) and no teach item. Free text, any other word, several answers, or a
  teach request are still refused with 409 and nothing is written.

## What does NOT change

- The decider never answers a permission prompt, and a permission is never taught as a rule.
- No option, free-text or teach control on a permission row — only the two buttons.

## Capabilities

### Modified Capabilities

- `relay-own-answer`: a permission prompt is answered from the board with its two fixed answers.

## Impact

- `lib/set_orch/api/fleet_relay_teach.py` (`/answer` route)
- `web/src/components/FleetRelayBoard.tsx`, `web/src/lib/fleetRelayBoard.ts`, `web/src/lib/fleetRelayTeach.ts`
- Tests: `tests/unit/test_fleet_relay_teach_api.py`, `web/tests/unit/fleetRelayBoard.test.ts`
