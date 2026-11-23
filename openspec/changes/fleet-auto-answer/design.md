## Context

The question relay (`lib/set_orch/fleet/question_relay.py`) turns three blocking points into one
contract: a carrier hook builds an envelope (`{"questions": [{id, key, question, optionsList,
multi, audience, source, valasz_tar}]}`), runs the machine's configured outbound
(`question_relay.command`) with the envelope on standard input, records a waiting state, and polls
`<valasz_tar>/<id>__<key>.json` for `{"valasz": "<text>"}`. The first answer that appears is the
answer. The carriers are `AskUserQuestion` (PreToolUse), the permission prompt (PermissionRequest)
and the continuation question after a finished turn (async Stop). They differ only in the `kind`
recorded in the waiting state. The fleet already delivers an answer through the same store
(`deliver_answer`).

A headless model call already exists for the wait detector and the continuation suggestions
(`wait_detect.run_headless`: hooks disabled, no session persisted, a guard environment variable).

## Goals / Non-Goals

**Goals:**
- Answer on the operator's behalf when the answer is an earlier decision, is written down, or is
  the operator's likely choice — through the existing relay contract, without touching its hooks.
- Find an answer that is written anywhere in the project's indexed knowledge, not only in the
  places named in advance.
- Make every automatic answer visible before it acts, attributable to a source, and overridable.
- Never approve an outward or irreversible step, and never answer a permission prompt.

**Non-Goals:**
- A second relay, a second answer store, or a change to the chat bridge.
- A learned operator profile. The decider reads what is written; it stores nothing about the
  operator.
- Replacing the in-session keep-going hook. Keep-going decides whether a session may stop; the
  decider answers a question once one has been asked. They compose.

## Decisions

### D1 — A decider outbound in front of the operator's outbound, not a new hook
`set-auto-answer` is configured as `question_relay.command`; the operator's previous command moves
to `auto_answer.forward_command`. All three carriers reach it with no hook change, and the "first
answer wins" rule the relay already enforces is exactly the override rule this change needs.
*Alternative:* a fourth hook, or a branch inside each carrier. Rejected: three places to keep in
step, and a model call inside a hook that the runtime times out.

### D2 — Return at once; decide in a detached worker
The relay waits for its outbound's exit code before it records the waiting state. The decider
therefore validates the envelope, spawns a detached worker and exits 0. The worker decides,
forwards and, if allowed, writes the answer after the window. *Alternative:* decide synchronously.
Rejected: a 20–90 s model call would sit inside the hook before the waiting record even exists,
so the fleet could not show that the agent is waiting.

### D3 — The relay passes kind, session and working directory through the environment
The envelope has no kind, and its id is a hash, so the outbound cannot tell a permission prompt
from a question, nor which tree to search. Three environment variables on the outbound process
(`SET_RELAY_KIND`, `SET_RELAY_SESSION`, `SET_RELAY_CWD`) carry them. *Alternative:* new envelope
fields. Rejected: the chat bridge reads the envelope verbatim and posts it; extra fields would
leak a local path into a channel.

### D4 — Decide first, then forward the question WITH the proposal
The worker makes its decision (bounded, default 90 s) before it forwards, so the operator's one
message carries the question, the proposed answer, its tier, its source and when it will be
written. The proposal is appended to the question text the bridge already shows. If the decision
fails or times out, the envelope is forwarded unchanged — the operator is never left waiting on
the decider. *Alternative:* forward at once, decide in parallel, and send the proposal as a second
notification. Rejected: two messages per question, and the second may arrive after the operator
has already answered.

### D5 — Three tiers, and the user's choice that `likely` may answer
`decided` and `found` need a verbatim source; `likely` needs a confidence. The first draft in the
conversation allowed only sourced answers; the user's request explicitly includes *"amit
valószínűleg választanék"*, so `likely` answers too, above `auto_answer.likely_min` (default
0.8). The bar, the window and the switch are the operator's levers; the tier is shown on every
proposal so the operator can tell an inference from a recorded decision.

### D6 — Exclusions are two-sided and outrank every tier
An outward or irreversible step is excluded if EITHER a deterministic pattern check (question,
options, chosen answer; English and Hungarian forms; extendable with `auto_answer.never_patterns`)
OR the model's own flag says so. A permission prompt is excluded by kind. Fail direction: a false
positive forwards a question to a person, which is the safe direction; a false negative would
approve a publish in the operator's name, which is the defect this whole change must not have.
Measured motivation: in the session that produced this change, Claude Code's prompt suggestion
under an agent read "mehet a push". A past approval is not an approval of this step — the
project's own rules require the operator's OK for each push, and a consumer's production is never
deployed at all.

### D7 — The answer is written with an exclusive create
The worker writes the answer to a temporary file and links it to the answer path, which fails if a
human answer already exists. It never overwrites. A cancel removes the pending record, and the
worker re-reads it immediately before writing.

### D8 — The lookup is a read-only headless session in the asking tree
The model call runs with `cwd` = the session's working directory, tools limited to reading and
searching, hooks disabled, no persisted session, and the relay's guard variable set (so it cannot
relay its own questions). The prompt names where decisions live — the instruction files of the
project and the user, `.claude/rules/`, the session's newest handoff under `.set/handoff/`, open
changes under `openspec/changes/`, `openspec/bugs/README.md` when present, the project's memory
directory — and any `auto_answer.extra_paths`. These are framework and runtime conventions, not a
project's domain, so the core layer stays domain-free. The output is one JSON object; anything
else is "no decision".

### D8a — The knowledge base runs first, and the decider runs it, not the model
The fixed locations in D8 find what we already know the place of. *"It is in the information, it
only has to be looked up"* is the case they miss: a decision in a meeting note, a design paragraph,
a client document the project indexes. `set-kb search --json` searches the project's whole indexed
knowledge at section level with a stable output contract, and a project can configure roots and
channels for exactly this. The decider runs it in the asking tree with the question and options
and passes the top sections to the model as candidates; the model may open them in full with its
read tools. The decider, not the model, runs the search, so the model keeps read-only tools and
needs no shell. A project where `set-kb doctor` reports search as not working is not blocked: the
fixed locations still apply, and the log says the knowledge base was not used.

### D9 — What is stored, and where
A pending record per call (`<state>/auto-answer/<id>.json`: option, tier, source paths and
excerpts, deadline) lives beside the relay's answer store and is pruned with it (7 days). It holds
the same kind of text the answer store already holds, on the same machine, under the same
retention. The log carries the call id, tier, outcome and source paths, never the question or
answer text — the relay's own log rule.

## Risks / Trade-offs

- [A `likely` answer is wrong] → it is proposed with its tier before it is written; the window,
  the bar and the switch are the operator's; outward steps are excluded regardless.
- [The pattern check misses a phrasing of an outward step] → the model's flag is the second check;
  `never_patterns` extends the first; the deny direction is the default on any parse failure.
- [Cost: a model call per blocking point] → only while the switch is on; the model is configurable
  (`auto_answer.model`); a continuation in a session that keep-going already drives rarely occurs.
- [The forward command is slow or down] → the decider logs it; with no forward command configured
  and no decision, the question is released to the terminal instead of waiting for the timeout.
- [A human answer and the worker race] → exclusive create; the hook reads the first file.

## Migration Plan

1. Ship the decider with the switch off by default.
2. On the machine: `set-config set auto_answer.forward_command "<the current question_relay.command>"`,
   then `set-config set question_relay.command set-auto-answer`. With the switch off this is a
   pass-through; verify one relayed question arrives unchanged.
3. Turn the switch on from the fleet header; watch the first proposals.
Rollback: switch off (pass-through), or restore `question_relay.command`.

## Open Questions

- The window default (60 s is proposed) and the `likely` bar (0.8) — the operator tunes both.
- Whether a `decided` tier should skip the window. Kept at the same window in this change; it can
  be split later without a contract change.
