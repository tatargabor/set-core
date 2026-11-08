## Why

The owner, 2026-11-08, relayed by a consumer session: *„board pagek updatellésére ne égessünk
minden percben tokent amikor megvan valami legyen okosabb a rendszer”*. The team was spending
about twice its 7-day token budget, and the wave-board Stop hook was part of it: it asked for a
push whenever a payload differed from the last push, so every `set-wave-board set` cost the
agent a continuation — and a second one when the board's combined-board document fell due on a
different clock (separate nag stamps). A note edit triggered a push like any status change.

## What Changes

- `set-wave-board sync` classes each pending push — `first`, `milestone` (a wave finished, an
  item turned blocked), `progress`, `notes` (only notes, `updated`/`by` stamps, evidence
  definitions) — and reports it (`push_class`, `combined_push_class`) with the last push time.
- `set-wave-board pushed` stores the marks the next push is classed against (a hash of the
  visible substance, the finished waves, the blocked items) — only when the recorded hash is
  the payload's own.
- `set-hook-waveboard` decides per job: `first`/`milestone` at once (30-minute backoff as
  before); `progress` only when the job was last pushed ≥ `SET_WAVEBOARD_DEBOUNCE_SECONDS`
  (default 3600) ago; `notes` never. A board and its combined document share one decision and
  one block.
- The wave-board skill, and the handoff skill on this machine, tell the agent to flush
  `set-wave-board pending` before a handoff and at session end — a Stop hook cannot tell the
  last Stop from any other.

Not changed: one write per artifact. The board page and the combined board are different
artifacts, so they stay two `ArtifactData` calls — but in one continuation.

## Impact

- `bin/set-wave-board`, `bin/set-hook-waveboard`, `tests/unit/test_wave_board.py`,
  `.claude/skills/set/wave-board/SKILL.md`.
- Push records written before this change carry no marks; their next change is classed
  `progress` (batched), never `notes`, so nothing is silently dropped.
