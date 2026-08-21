## Why

When a work-cycle section needs a person, the engine already handles it end to end **on this
side of the machine**: `cli.py` marks the task `- [?]` with its question
(`connector.mark_awaiting`), the awaiting task holds the groups that declare a dependency on
it, an answer dropped into the tree is taken in on every entry path
(`connector.intake`), the task is released and the answer is carried into the next run's
prompt (`connector.record_answer` → `connector.answers_for` → `prompt.build_unit_prompt`).

What does not exist is the step in the middle: **nobody is told**. The answer directory is
reachable only by somebody already at this machine, so a cycle that meets a question at 01:00
does no further work until a person opens the repository. The night is what is lost, not the
minute.

Two trees on this machine have built that middle step and produced measurements from it. This
change takes its **shape** — as a contract an outbound can satisfy without knowing who else
does — and does not require either of them to change.

⚠ **This proposal was rewritten on 2026-08-21 after an adversarial review refuted much of its
first version.** What the first version claimed, and what is actually true:

| the first version said | measured |
|---|---|
| set-core ships no outbound of its own, and its notification module speaks one direction only | **false, but the first correction over-shot.** `lib/set_orch/discord/__init__.py:96` registers `on_reaction_add`, accepts **three hard-coded emoji**, maps them to `accept`/`rerun`/`newspec` and shells out to `set-sentinel-inbox send --type completion_action`; `events.py:343` adds them as buttons. So it **speaks in both directions — but carries no identity**: the payload has no run id, no change, no task and no message id, the handler filters on the emoji alone, and `completion_message_id` is stored at `events.py:346` and **read nowhere** (grep: two hits, both writes). It is a reaction-driven, uncorrelated, three-fixed-action run-completion acknowledgement — not an answer to a question |
| the pickup is new work | **false.** `lib/set_workcycle/connector.py` (457 lines) already implements it. That half is documented retroactively by `deferred-work-connector` (in `work-cycle-engine-apply-first`) and is **out of scope here** |
| the pickup reuses `prompt.py`'s `answers` route | **misnamed.** `prompt.py:95-101` is a string builder; the pickup is `connector.clear_awaiting` + `record_answer`, driven from `cli.py:118-131` |
| `lock.py` already carries run scoping for answers | **false.** `lock.py` is a per-tree mutex keyed on a session seat; there is no run identity to honour |
| the two trees close the loop in daily use | **overstated — and the first correction was ALSO wrong, in the same direction.** It said "newest answer 2026-08-12", which is the newest file at the *top level* of the answer directory. Four answers dated **2026-08-17** sit in the rejected subdirectory, and one of them closed its round trip in **nine minutes** (question 10:13 → answer 10:22). The loop works and it was the **pickup** that rejected the result — which is more interesting than either version said. Supportable: "used, and it produced measurements". Not supportable: "daily" |

## What Changes

- **A versioned question envelope**, produced from the awaiting tasks of a change: the task's
  identity, the question text, a structured option list, an audience, and where the answer is
  expected.
- **`audience` is required and the FRAMEWORK never invents it.** A project may declare a
  fail-closed default — the working implementation defaults apply-side questions to its
  developer audience and never to its client audience, so a night-time outbound cannot jump
  the decision order. What the framework must not do is supply a value of its own.
- **Options are structured, never a joined string.** Measured: a display string built by
  joining options cannot be split back safely, because the separator can occur inside one.
- **A declared outbound**, resolved from the project's own configuration the way the status
  contract already resolves its commands — plus, and this is new, **an explicit operator
  opt-in**, because this is the first declared command that reaches a network.
- **The hand-off is best-effort and can never fail the cycle** — and, unlike the first
  version of this proposal, a failed hand-off is **retried**, because "handed over once"
  combined with "failure changes nothing" produced permanent silence.
- **The envelope must not carry local filesystem paths off the machine.** It is handed to
  something that posts into a chat room; an absolute path publishes the username, the machine
  layout and the project's directory name.

**Preconditions, not tasks here:**

- **B-38 — an answer must be data, not an instruction.** `prompt.py:95-101` interpolates
  answer text into a full-session prompt under *"act on them rather than asking again"*, and
  `runner.py:60-81` runs it with the project's own hooks. Today only somebody at this machine
  can write an answer. **This change is precisely what extends that write surface to whoever
  can post in a chat channel.** No outbound is wired until `work-cycle-answer-is-data` lands.
- **B-36** — an engine call without a change silently consumes pending answers without
  applying them. Independent of this change and live today.

**Not in this change:** any outbound implementation; the answer pickup (see
`deferred-work-connector` (in `work-cycle-engine-apply-first`)); masking or redaction of the question text, which is measurable
only where the text becomes a message; any surface that displays pending questions.

## Capabilities

### New Capabilities
- `human-question-contract`: the versioned envelope for a question raised by a work cycle —
  identity, text, structured options, audience, answer location — and the rules that make it
  safe to produce: the framework never invents a value, a missing audience is a refusal
  rather than a default, no local path leaves the machine, and nothing derived from the
  question's content is persisted by the framework.
- `question-outbound-binding`: how a question reaches an outbound the project declares — the
  declaration, the operator opt-in a network-reaching command requires, the best-effort
  hand-off with retry, and the once-outstanding rule that keeps a person from being asked the
  same thing twice.

### Modified Capabilities
<!-- None. The capabilities of `work-cycle-engine-apply-first` and of the retroactive
     `deferred-work-connector` (in `work-cycle-engine-apply-first`) are consumed here, not altered. -->

## Impact

- `lib/set_workcycle/` — `cli.py` (where a `- [?]` is marked today, driven by
  `verdict.stops` / `open_decisions`, **not** by an `engine.py` `NEEDS_INPUT` path — that path
  does not exist; the outcome enum lives at `verdict.py`), and a new module for the envelope
  and the binding.
- **`lib/set_orch/discord/`** — the existing reaction-driven answer path is the shape being
  generalised. Whether it becomes the first conforming outbound, or stays as it is, is a
  design question, not an assumption.
- The outbound is resolved from configuration, never imported. No new dependency.
- The agent bus is an accelerator only. ⚠ Its delivery is **once per agent, not once per
  session**: `set-agent-comm/src/store.mjs:1325-1361` seeds a new seat's cursor from the
  furthest read across that agent's past seats, floored at one hour for a sibling writer. An
  entry read by a session that then dies without acting is gone for that agent.
