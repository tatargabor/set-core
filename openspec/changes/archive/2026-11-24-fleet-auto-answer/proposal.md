## Why

Every point where an agent stops for the operator — an `AskUserQuestion`, a permission prompt, a
finished turn that waits for the next instruction — already reaches the operator through the
question relay and its two-way outbound (`agent-question-relay`, `relay-answerable-blocking-points`).
What is missing is the step before the operator: most of those questions have an answer that
**already exists** — the operator decided it earlier, it is written in the project's rules, a
handoff or a design, or it is the option the operator picks every time. Each one still waits for a
person, so an agent that could have gone on sits idle until somebody reads a channel.

The user's request (2026-11-23), verbatim: *„epitsünk egykepesseget ami akkor sutomatikusan valaszol
heyettem azzal amit valoszinuleg valasztanek vagy korabban mar valsztottam esetleg benne van infoban
csak meg kell keresni"* — answer for me with what I would probably choose, what I already chose, or
what is already in the information and only has to be looked up. A first proposal in the same
conversation allowed only answers backed by a quoted earlier decision; the user's wording widens it
to the likely choice, and that is what this change builds.

What must NOT be inferred is equally concrete, and was measured in the same session: Claude Code's
own prompt suggestion under one agent read **"mehet a push"** — the agent's proposal to publish,
echoed back as if the operator had typed it. An answerer that accepts the obvious continuation
approves the agent's own outward steps in the operator's name.

## What Changes

- **A decider in front of the outbound.** A new outbound command, `set-auto-answer`, is configured
  as the relay's `question_relay.command`; the operator's real outbound moves to
  `auto_answer.forward_command`. No hook changes: the relay already hands every blocking point to
  "the command" and takes the first answer file that appears.
- **The decider looks it up, then decides.** The project knowledge-base search (`set-kb`) runs first
  and hands its best sections to a FORK of the asking session (decided by the user after the first
  replay: the operator's spoken decisions live in the session's context), which answers with
  references that are then checked verbatim; fallback, one headless model call per question, run in the
  asking session's working directory with read-only tools, is pointed at where decisions live: the
  project and user instruction files, the project's rules, the session's newest handoff, the open
  OpenSpec changes, the bug register and the project's memory directory. It returns one choice with
  a **tier** — `decided` (an earlier decision, quoted), `found` (the answer is written somewhere,
  quoted), `likely` (inferred, with a confidence) — and its sources.
- **Hard exclusions, which no tier overrides.** An outward or irreversible step (publish/push,
  deploy, production, sending a message, deleting, paying, credentials) and every permission prompt
  are never answered automatically. They are forwarded with the decider's recommendation attached.
  Detection is two-sided: a deterministic pattern check on the question, the options and the chosen
  answer, and the model's own flag; either one excludes.
- **Visible before it acts, and overridable.** An automatic answer is forwarded to the operator as
  a proposal with its tier and source, and written only after a configurable window
  (`auto_answer.window_s`) if no human answer arrived first. The fleet shows the pending answer on
  the agent and can cancel it.
- **The relay tells its outbound what it is asking about.** The carrier exports the call's kind,
  session id and working directory to the outbound's environment. The envelope the chat bridge
  reads is unchanged.
- **A machine switch.** `auto_answer.enabled`, also as a control on the fleet header next to the
  relay switch. Off means the decider forwards everything untouched.

## Capabilities

### New Capabilities
- `fleet-auto-answer`: the decider outbound — the lookup, the tiers, the exclusions, the
  proposal-then-answer window, the fleet switch and the pending-answer view and cancel, and the
  relay's environment hand-over to its outbound.

### Modified Capabilities
<!-- none: the relay's envelope and hooks are unchanged; the environment hand-over is additive and
     specified in the new capability -->

## Impact

- **Core (`lib/set_orch/fleet/`)**: new `auto_answer.py` (decision, exclusions, window, records);
  `question_relay.py` exports three environment variables to the outbound and nothing else.
- **CLI (`bin/`)**: new `set-auto-answer` (the outbound entry point; added to `install.sh`'s list).
- **API (`lib/set_orch/api/fleet.py`)**: switch route and pending-answer cancel route; the waiting
  listing carries a pending automatic answer.
- **Web (`web/src`)**: the header switch and the pending-answer marker on the agent; rebuilt bundle;
  a visual check in the browser.
- **Machine-local config** (`set-config`): `auto_answer.enabled`, `auto_answer.forward_command`,
  `auto_answer.window_s`, `auto_answer.likely_min`, `auto_answer.model`,
  `auto_answer.never_patterns`. Nothing is written into any project tree.
- **Depends on** the relay carriers being wired on the machine (`set-relay-wire`); works with
  whichever of the three carriers are present.
- **Cost**: one headless model call per relayed blocking point while the switch is on.
