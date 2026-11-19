## Context

The question relay (`agent-question-relay` capability) carries only `AskUserQuestion` through a PreToolUse hook that holds the question and brings an answer back. Every other terminal-blocking message — permission prompts, the runtime's waiting-for-input notice — stays terminal-only. The user's rule (2026-11-19): every terminal-blocking message must reach the channel. The machine's switch (`question_relay.enabled`) and outbound already exist; the chat bridge (separate repository) answers questions through `question_relay.command`.

Constraint carried over from the question relay's design: the terminal is the fallback in every failure, and the hook must never be the thing that breaks a session. The confidentiality boundary holds: what crosses to the channel is exactly what the terminal already shows the owner, on the owner's own channel; the framework persists nothing derived from it (no message text in any waiting record or log).

## Goals / Non-Goals

Goals:
- Permission prompts and waiting-for-input notices reach the configured outbound as one-way notifications while the switch is on.
- The hook can never block, slow, or answer a session; failures are log lines.
- Unwired projects are named, the same way question-unwired projects already are.

Non-Goals:
- Answering notifications from the channel (the terminal stays the actor).
- Relaying PreToolUse hook denials (a refusal the agent self-corrects is not a blocked human; relaying every refusal is noise). Revisit only if a stuck-agent pattern is measured.
- The prose-wait marking defect (register B-187): its wait-detect audit runs in the same register thread but is not this change.

## Decisions

- **Carrier on the `Notification` event, not on permission internals.** The runtime's Notification hook fires for permission requests and idle waits — the two blocking classes the owner must know about — through one documented event, so no coupling to permission-mode internals. Alternative rejected: intercepting PreToolUse permission decisions, which duplicates the runtime's own gating and misses idle waits.
- **`question_relay.notify_command`, falling back to `question_relay.webhook_url`.** A notify is one-way, so the two-way question command is the wrong shape to reuse blindly (it expects a question envelope and writes answer files). The webhook path already exists for one-way posting. Missing both with the switch on = dropped, logged, readiness names the key — never a guessed default (the question relay's own rule).
- **Carrier mirrors `set-hook-question-relay`: thin executable, logic in `lib/set_orch/fleet/question_relay.py`.** Same switch, same state dir, same log; a new `notify()` entry point beside `relay()`. The hook's settings timeout is 10 s and the code makes exactly one attempt — a notification that fails is a log line, never a stall.
- **Envelope is a superset, not a new format:** `{"kind":"notification","project":...,"agent":...,"session_id":...,"message":...}` on stdin. The bridge's notify entry point (its own repository) reads `kind` first and ignores unknown shapes.
- **Wiring check extends the existing unwired list.** `set-relay-wire` already reports which projects miss the question hook; the same list gains a missing-notification entry per project. The web header's existing unwired rendering needs no new surface — one more name in the list it already shows.
- **`once: true` is irrelevant here** — hooks are configuration, not seeded files; the deploy rules for consumer trees are unchanged.

## Risks / Trade-offs

- **The Notification event's payload shape is runtime-provided** — implement against the documented fields and assert at the carrier boundary (a shape that does not carry a message is logged and dropped, not guessed). First live firing on this machine is the acceptance measurement.
- **Noise if the runtime notifies on non-blocking events.** If a firing class turns out not to block anyone, it is a one-line filter in the carrier, decided on measurement — not a contract change.
- **A notify post that fails silently** looks like the very defect this change fixes; the relay log therefore names every drop reason (missing key, command failure, unreadable shape), and the acceptance test greps those reasons.

## Migration Plan

Additive: new carrier file, new hook entry in the machine's and the template's settings, one more key checked by the wire tool and readiness. Nothing existing changes behaviour while the switch is off; turning the switch on enables questions AND notifications together, which is the user's stated mental model (one relay).

## Revert Plan

Delete the hook entry (or flip the switch off); the carrier file and library code are inert without it.
