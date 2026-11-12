## Why

The wave-board Stop hook runs `sync` on every Stop of every session in a repository that has
`docs/waveboard/`, and blocks the stop to ask for an Artifact push or a board review. Each block
costs a whole continuation. The owner decided on 2026-11-12 that it runs for nothing and eats
tokens: the boards are now built from the tracked `docs/waveboard/*.json` files by the team's
own portal, and the claude.ai Artifact pushes the hook asks for fail on every machine but one,
because the combined artifact belongs to another organisation. Pushing is to happen **on
request**, not on every Stop.

## What Changes

- **BREAKING (behaviour):** `set-hook-waveboard` is off by default. It runs sync and asks for a
  push or a review only when the machine sets `SET_WAVEBOARD_PUSH` to `on` (or `1`, `true`,
  `yes`, `worktree`). An unset or unrecognised value is off.
- The default target of a board is therefore the tracked job file. `sync`, `pending` and the
  push procedure still work when run by hand. That is the "on request" path.
- The wave-board skill says so: no push at the end of a session or before a handoff unless the
  user asks, or unless the machine has opted in.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `wave-board`: the Stop hook's push reminder and review reminder are opt-in per machine.

## Impact

- `bin/set-hook-waveboard`: the switch is inverted and the docstring updated.
- `.claude/skills/set/wave-board/SKILL.md`: push and review on request; how to opt in.
- `tests/unit/test_wave_board.py`: the hook tests opt in explicitly, and a new test pins the
  silent default.
- Deployed `settings.json` entries stay in place. The hook is on PATH, so the new default
  reaches every consumer at once, with no redeploy.
