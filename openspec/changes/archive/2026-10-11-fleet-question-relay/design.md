## Context

Measured facts this design rests on are in the proposal. Two existing pieces are reused
rather than rebuilt:

- **A chat bridge already running on this machine** takes a question list as JSON on stdin,
  posts each question with numbered reactions, polls the channel every few minutes, and
  writes each answer as `<valasz_tar>/<id>__<key>.json` (`valasz` = the answer text). It
  owns masking, the audience gate and answer collection. Dry-run measured: it accepts a
  relay-shaped question unchanged, and the posted text does not include `valasz_tar`.
- **`work-cycle-question-outbound`** (open, not built) defines the rules for a question
  envelope: a required audience the framework never invents, structured options, no local
  path published, no question text in diagnostics, best-effort hand-off.

## Goals / Non-Goals

**Goals:** one switch, every interactive agent in every deployed project, an answer from the
channel, and the terminal as the fallback in every failure. A second operator on another
machine configures a webhook and gets notified without the first operator's bridge.

**Non-Goals:** cross-machine routing, headless sessions, permission and plan prompts, any
chat-side logic.

## Decisions

**D1 — A `PreToolUse` hook, not a fleet-side watcher.** Only the hook can supply the answer
(`updatedInput.answers`), and only the hook sees the question before the picker blocks the
terminal. A watcher could at most notify.

**D2 — Adopt the bridge's envelope spelling.** `id`, `key`, `question`, `optionsList`,
`multi`, `audience`, `source`, `valasz_tar` (Hungarian field names quoted verbatim, as the
existing artifact names them). The open `work-cycle-question-outbound` lists "the exact field
spelling" as an open question to be settled with an existing implementation; this is that
implementation, and that change should adopt the same spelling rather than define a third.
`valasz_tar` is a local path handed to a local command — it is not published (measured), and
publishing it would be the command's defect, not the envelope's.

**D3 — The audience comes from local configuration, never from the framework.** The bridge
only forwards the audience it is allowed to wake someone for; the framework does not know
what that is. No audience configured → the question is released and readiness says why.

**D4 — Fail-open to the terminal.** Release = exit 0 with no output (measured: the picker
appears, and the question is then in the transcript, so the fleet's normal asking detection
takes over). Every failure path ends there. The relay never answers with a default.

**D5 — Poll, re-checking two things.** Every 3 s the hook checks: all answer files present →
answer; `question_relay.enabled` no longer true → release; the waiting record's `release`
marker → release; past `question_relay.timeout_s` (default 3300) → release. The hook entry's
own timeout is 3600 s, so the internal deadline always fires first. A question released and
then answered on the channel leaves an orphan answer file; it is ignored and pruned after
7 days.

**D6 — The waiting record carries no content.** `~/.local/share/set-core/question-relay/
waiting/<session_id>.json`: session id, project, cwd, question count, target, started, id.
The fleet joins it to agents by session id. Question text stays in the transcript and with
the outbound.

**D7 — Webhook = notify, minimal by default.** A webhook cannot return an answer, so it
notifies and releases. The default message names project, agent and the questions' short
headers only — the bridge masks content before posting and a raw webhook does not, so
carrying the text is an explicit `webhook_detail: full` choice.

**D8 — The switch lives in local config.** The hook is a separate process in every session,
so the switch must be a file it can read; `local_config` is the existing machine-local
layer, outside every repository. The fleet's `POST` writes it; readiness is computed from
the same keys the hook reads, by one function both use.

**D9 — `source` is the project and the session's first 8 characters.** The owner gives a
started agent no label in its environment (checked: `ownerd.py` sets none), so the session
id is the one identity every session has; the fleet shows the same 8 characters. Never a
path.

## Risks / Trade-offs

- [While waiting, the terminal shows "running PreToolUse hook" and cannot be answered
  there] → the fleet's "answer here instead" and the switch both release within one poll.
- [The bridge polls the channel every 3 minutes] → answers take up to that long; acceptable
  for an away-from-desk channel.
- [The hook timeout ceiling above 700 s is unmeasured] → the internal deadline (3300 s)
  releases first; the first live run measures whether 3600 s holds.
- [The hook runs in every interactive session] → off is one small file read; measured cost
  is checked in verification.
- [An answer from the channel enters the agent's context] → the same as an answer typed at
  the terminal; the bridge only accepts answers from its trusted answerers.
- [An outbound that exits 0 without having posted holds the question until the timeout]
  → the command contract is "exit 0 = every question handed over"; anything else must be
  non-zero, and the hook releases at once on non-zero. Measured on the real bridge
  2026-10-11: a post refused by Discord ("Missing Access") still exited 0, and the hook held
  the question until it was released from the fleet. Reported to the bridge's owner; the
  relay stays off until the bridge exits non-zero in that case.

