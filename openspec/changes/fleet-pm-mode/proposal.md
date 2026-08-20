## Why

The fleet screen shows every running agent, but finding the one that needs a person is the
reader's own job — they scan tiles, open terminals, and guess. Measured on this machine
2026-08-20 (`GET /api/fleet/agents`): **18 agents, 0 reported waiting, 17 quiet**. Among those
17 sat an agent whose last utterance was *"⚠ Álljunk meg — más ügynökök is commitolnak ebbe a
repóba"* — a question addressed to a human, invisible to every count on the screen.

Two separate defects produce that blindness, and both are measured:

- **The only source of `waiting` is a declaration.** `lib/set_orch/fleet/state.py`
  (`_apply_declared_wait`) upgrades a quiet agent to `waiting` **only** when the runtime's own
  session record says `status: waiting`. That was true for 0 of 18 agents today and 1 of 22 the
  day before. A queue built on it would be empty.
- **The one case that IS structurally certain is classified as its opposite.** An outstanding
  `AskUserQuestion` or `ExitPlanMode` tool call means the agent is stopped in front of a person.
  Measured on a real log (`set-designer/521a55a7…jsonl`, 3 instances): the `tool_use` entry is
  journaled **8m13s, 9m32s and 1m43s before** its `tool_result`, so the outstanding call is
  visible for the whole time the human is thinking. Today `read_state` returns `working` for it.
  This is the false-value class, failing in the reassuring direction.

What is left after those two is genuinely a prose judgment — *did this quiet agent ask me
something, or did it just finish and report?* Measured today: 12 of 17 quiet agents ended with an
agent utterance, 3 with a user utterance and no reply (work dropped on the floor), 2 with no text
at all. A keyword or `?` test on that is a proxy for a decision, which this repository has already
paid for more than once. A model reads it.

## What Changes

- **A PM mode toggle on the fleet screen.** When on, the fleet presents, full screen, the one
  agent the reader should deal with, and advances only once they have dealt with it.
- **An attention queue** with a declared ordering, a preemption rule, and a history stack
  (back/forward). What is queued is *a person's decision is blocking this agent*, never
  "this agent is idle".
- **The blocking-tool fix in the state layer.** An outstanding `AskUserQuestion` / `ExitPlanMode`
  becomes its own measured state — blocked on a person — instead of `working`. This is worth
  shipping on its own merits: it removes a false value from a screen that exists today.
- **A single judgment pass.** One model call per cycle covering **all** candidates in one prompt
  — not one watcher per agent — classifying each quiet agent's last turn. The queue's own state
  (shown, answered, deferred, history) is held in code, never in the model's context.
- **A structural "the reader dealt with it" test.** Refuted by measurement: a new `user` entry in
  the log is NOT proof. An `Esc` writes exactly that (`[Request interrupted by user]`, measured on
  `itline-web/349ee01c…jsonl`), so the naive test would break the freeze the mode exists to
  provide. The test is that **the agent resumed** — a new assistant utterance or a new outstanding
  call after the question.

**Not in this change:** any notification outside the fleet screen; answering an agent the fleet
holds no terminal for beyond the existing instruct box (2 of 18 today); the work-cycle engine's
`NEEDS_INPUT` questions, which have their own contract in `work-cycle-question-contract` and can
join this queue as a later feed; work awaiting a human with no agent on it (`awaiting`), which
cannot be answered in a terminal and stays a separate entry point.

## Capabilities

### New Capabilities
- `agent-fleet-attention-queue`: what counts as an agent blocking on a person, how those are
  ordered, when one may preempt what is on screen, what removes an item from the queue, and the
  history the reader can step back through.
- `agent-fleet-pm-judgment`: the single per-cycle model pass that classifies quiet agents' last
  turns — its candidate filter, the classes it may return, the fact that its verdict is advisory
  over a structural floor, and the persistence boundary its input imposes.

### Modified Capabilities
- `agent-fleet-state`: an outstanding tool call no longer means "working" unconditionally — a
  call that is itself a question to a person is reported as blocked on a person, carrying which
  tool. Adds the resumed-after-question signal the queue reads.
- `agent-fleet-surface`: the PM toggle, the full-screen presentation, the count of what is
  waiting behind the frozen screen, and the back/forward controls.

## Impact

- `lib/set_orch/fleet/state.py` — blocking-tool classification, resumed signal.
- `lib/set_orch/fleet/` — new modules for the candidate filter, the judgment pass and the queue.
- `lib/set_orch/api/fleet.py` — PM endpoints (queue head, advance, defer, history).
- `lib/set_orch/model_config.py` — a `pm` role, defaulting to `sonnet`.
- `web/src/pages/Fleet.tsx`, `web/src/lib/fleetAttention.ts`, new PM components.
- No consumer-side change; nothing new is deployed by `set-project init`.
- **Depends on `fleet-view` archiving** for the two modified capabilities to have a base spec.
