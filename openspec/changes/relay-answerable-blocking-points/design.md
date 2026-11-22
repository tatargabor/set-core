## Context

The question relay (`agent-question-relay`) holds an `AskUserQuestion` call in a PreToolUse hook. It hands the question to a two-way outbound (a chat bridge in its own repository) and answers the call from answer files. Two other blocking classes reach the channel only one way through the notification carrier (`hook-notify-relay`, not yet archived): permission prompts (including confirmations a hook asks for) and the runtime's idle notice. A turn the wait detector classifies DONE reaches the channel only as the generic idle notice.

Measured on Claude Code 2.1.330 on 2026-11-22, in a throwaway interactive session (default permission mode, tmux, hooks logging to a file). Full record in bug register B-188 and B-190:

1. A `PermissionRequest` hook fires for a plain permission prompt and for a PreToolUse `ask`. The dialog is drawn while the hook runs. A hook output `{"decision":{"behavior":"allow"}}` after 15 s closed the dialog, and the tool ran.
2. The `PermissionRequest` payload carries `session_id`, `transcript_path`, `cwd`, `prompt_id`, `permission_mode`, `tool_name`, `tool_input` and `permission_suggestions`. It does not carry the asking hook's reason.
3. Answering the dialog in the terminal first does not terminate the hook: it ran on and answered into nothing 10 s later.
4. A `Stop` hook with `asyncRewake: true` exited 2 twenty seconds after the turn ended. The idle session woke and executed the stderr text as an instruction.
5. A new prompt typed by the owner does not cancel an armed async Stop hook: two armed hooks both woke the session, and the first was already stale.
6. Claude Code's own prompt suggestion is not in the transcript and not in the Stop payload.

The bridge needs nothing new: its `be` entry already accepts option buttons plus free text, and its release check closes a post whose waiting record vanished.

## Goals / Non-Goals

Goals:
- Every point where a session blocks on the owner is answerable from the channel: question, prose wait, permission prompt, hook-raised confirmation, finished turn.
- The terminal stays the fallback, and it stays usable while the channel item is open.
- A stale answer never acts.
- One item per blocking point on the channel.

Non-Goals:
- Persistent permission rules from the channel ("Yes, and always allow"). `permission_suggestions` stay terminal-only.
- Carrying the asking hook's own reason. That is the `--text` adoption on the hook owner's side (B-188(a)).
- Relaying PreToolUse denials. Those are refusals the agent self-corrects, not a blocked human, which is the same position `hook-notify-relay` took.
- Webhook-target answering. A webhook cannot bring an answer back, so the one-way notification stays its only trace.
- Changing the bridge.

## Decisions

- **Permission: `PermissionRequest` hook, not PreToolUse interception.** Measured: it fires beside the drawn dialog, covers hook-raised asks, and its decision resolves the dialog. Rejected alternative: holding PreToolUse for every tool, which would gate every call and duplicate the runtime's own permission logic.
- **Permission answer mapping fails closed.** Only the literal `Allow` option allows. `Deny` and any free text deny, and free text goes to the agent as the deny message, so "use staging instead" steers the agent rather than being lost. A misread free-text "yes" costs one re-prompt, while a misread "no" read as allow would run a command the owner refused.
- **Detecting a terminal-first answer from the transcript.** The hook is not killed when the dialog closes (measured), so it must notice on its own. The pending call is the newest `tool_use` whose name and input equal the payload's `tool_name`/`tool_input`. Its `tool_result` appearing in the transcript means the dialog was resolved, by the terminal or by anything else. The tail read reuses the bounded-tail pattern of `enrich_message`.
- **Continuation: an async `Stop` hook with `asyncRewake`, not a blocking Stop hook.** A blocking hook would hold the session busy for up to an hour, and the owner at the terminal could not use it. The async hook runs beside the idle prompt and wakes the session only on exit 2 (measured).
- **Verdict hand-off without text.** The wait detector writes `verdicts/<session>.json` holding `{turn, verdict, at}`. The continuation hook starts at the same Stop and polls that record for its own turn key for up to 75 s, which covers the detector's 60 s entry. The turn key is the Stop payload's `prompt_id` when present, otherwise a sha256 of `last_assistant_message`. The Stop payload's fields are measured in task 1.1 before this is coded. Alternative rejected: carrying the summary and suggestions in the verdict record. That would persist message-derived text, which the relay's own rule forbids. The second model call costs about 4 s and runs only for DONE turns while the relay is on.
- **Suggestions are set-core's, labelled.** The runtime's suggestion is unreachable (measured). One headless call (`claude -p`, the same flags as the classifier: hooks disabled, no persistence, `cwd=/`, guard env) returns a `SUMMARY:` line and up to three `NEXT:` lines. Options are prefixed `→ ` so the reader knows they are suggestions. Malformed output means no options, free text only; the question still goes out.
- **Supersede by three independent signals.** The signals are a `UserPromptSubmit` marker (fast, so the post closes as soon as the owner types), a newer continuation id for the session, and an assistant entry in the transcript newer than the arm time. The transcript signal catches wakes that bypass `UserPromptSubmit`, such as a background task finishing. All three are re-checked immediately before exit 2. Any one of them alone has a measured or plausible gap; together they cover typed prompts, re-arms and background wakes.
- **Withdrawal is record removal.** The bridge already closes a post whose waiting record disappeared, after its own short patience window. So the carriers keep the question hook's record shape (one per session, `relay-<sid>-<hash>` id) and add `kind`. No withdraw command, and no bridge change.
- **No double report.** `notify()` skips a session that has a permission or continuation record. Because the record is written only after the outbound accepts, it re-checks after a grace of at most 3 s. The notification hook's entry timeout (30 s) leaves room for that.
- **Thin carriers, shared library.** The three executables follow `set-hook-question-relay`: parse stdin, call into `lib/set_orch/fleet/`, and log to the relay log. Permission logic sits beside `relay()` in `question_relay.py` and shares the envelope, answer and waiting-record helpers. The continuation logic lives in a new `continuation.py`, which imports those helpers and the classifier runner from `wait_detect.py`.

## Risks / Trade-offs

- [Runtime behaviour changes in a later version] → Every carrier fails open. No output means the dialog or the idle prompt stays as it is. The live acceptance tasks record the version they ran against.
- [A transcript match picks the wrong `tool_use` when two identical calls are pending] → Parallel identical permission prompts are rare. A mismatch can only release early, which hands the item back to the terminal; it can never allow.
- [The async hook outlives a closed session] → The session's process is gone, so exit 2 wakes nothing. The record is removed on exit, and the bridge closes the post. A `pid` liveness check is already in `list_waiting`.
- [Second model call cost and latency] → It runs only on DONE turns while the relay is on, takes about 4 s, and posts after the turn ended. It never delays the terminal.
- [The owner answers a continuation hours later and the session context moved on] → The transcript supersede rejects it once any assistant turn happened. An untouched idle session is exactly the case where the answer is still wanted.
- [Noise: every DONE turn posts a question] → This is the user's stated requirement. Volume control is a configuration key decided on measurement (`question_relay.continue_enabled`, default on together with the switch), not a contract change.

## Migration Plan

The change is additive. Three hook entries are added to this repo's `.claude/settings.json`, to `set-deploy-hooks`, and through `set-relay-wire` to machine-local settings. The wait detector gains only a file write. With the switch off, nothing new runs past its first readiness check.

Rollback: remove the three entries, or turn the switch off. The verdict file is inert without the continuation hook.

## Open Questions

- The `Stop` payload's exact fields, `prompt_id` in particular. Measured in task 1.1. The hash fallback is designed so the answer does not block the design.
- Whether `UserPromptSubmit` fires for an `asyncRewake` wake. If it does, the supersede marker written by our own wake must not cancel anything. That is harmless, because the waking hook has already exited, but it is measured in task 1.1.
