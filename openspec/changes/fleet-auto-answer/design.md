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

### D8 — The decision is made by a FORK of the asking session, with references that are checked
Decided by the user on 2026-11-23, after the S2 replay: *„a forkolt session nekem alapvetően
jónak tűnik ha forrásokra kérdezünk rá hivatkozásokkal és annak az eredményét adjuk be a
válaszba"*. Most of the operator's decisions are spoken in the session — they exist in the asking
session's context and in no file. A separate headless call in the tree (the first version of this
decision) cannot see them; S2 measured it at 55 % with sources only.

So the worker runs `claude --resume <session> --fork-session -p` with the decision prompt. The
fork sees the whole conversation, the loaded handoff and the rules, writes to a NEW session id,
and leaves the original untouched. It shares the original's prompt prefix, so most of it is read
from the cache. Tools: read-only (reading and searching files); hooks disabled; the relay guard
variable set, so the fork cannot relay its own questions; bounded in time.

The prompt asks the fork to predict the OPERATOR's answer from the operator's own words, not to
repeat the agent's recommendation, and to return references: each one either an operator message
from the conversation (quoted verbatim) or a file path with a verbatim excerpt. The fork's own
tier is a claim; the tier the decider USES is derived from the references after a mechanical
check:
- a reference to the conversation counts only if the quoted text occurs verbatim in an OPERATOR
  turn of the session's transcript before the question;
- a file reference counts only if the excerpt occurs verbatim in that file;
- `decided` needs at least one checked operator quote or decision record; `found` at least one
  checked file excerpt; a choice whose references all fail is downgraded to `likely` with its
  confidence, and a `likely` answer can still only be written above `likely_min`.

The decider's own knowledge-base step (D8a) runs first and its hits are given to the fork as
candidate sources. The fork's result — choice, checked references, derived tier — is what the
proposal shows and what the window writes.

*Alternative kept as a fallback:* the headless call in the tree with sources only, used when the
session's transcript cannot be resumed (no transcript, a provider the fork cannot reach). It is
logged as `fallback: sources-only`.

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

### D10 — The operator's earlier answers are a candidate source, decided by the study
*"Amit korábban már választottam"* is literally the earlier answers: the same kind of question
answered in the same project before. Those answers live in local transcripts, not in any file the
lookup reads, so a decision taken only in an answer is invisible to D8. Task group 0 measures how
many past answers an earlier answer would have predicted. If it carries a meaningful share, the
decider gets a machine-local index of earlier answers (question, options, choice, time, project —
never leaving the machine, pruned like the answer store) as one more candidate source, tier
`decided` with the earlier answer as its quoted source. If it does not, it is left out.

### D11 — Measure before building, without time leakage
The study replays past questions with only the sources that existed at the question's time:
tracked files from git at that moment, untracked ones only if older, earlier answers only. A
replay against today's files would score decisions that were written down AFTER the question —
often because of it — as findable, and would set the `likely` bar on an inflated accuracy. Fail
direction of skipping this: the bar is set too low and the decider answers wrongly with
confidence.

## Risks / Trade-offs

- [The fork repeats the agent's own recommendation] → the prompt asks for the operator's words, the
  references are checked, and the replay (task 0.4) measures the fork against the recommended-option
  baseline before anything is written.
- [Cost of a fork: it re-reads the session's context] → the shared prefix is mostly cached; only
  while the switch is on; measured in task 2.6.
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
