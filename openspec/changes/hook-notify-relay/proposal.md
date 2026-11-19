## Why

The question relay carries only `AskUserQuestion`, so every other terminal-blocking message — a permission prompt, the runtime's "waiting for your input" notice — stands in a terminal nobody is watching while the relay claims the machine is covered. The user's rule from 2026-11-19: *"minden terminál blokkoló üzenetnek át kell jönnie"* — every terminal-blocking message must reach the channel. Measured twice the same day (bug register B-184, re-reported live): a session blocked on a permission prompt produced nothing on the channel.

## What Changes

- A notify-only relay hook on the runtime's `Notification` event (permission requests, idle waits): the message reaches the configured outbound as a notification — **no answer path**, the terminal keeps being the place the blocking message is acted on.
- The notification honours the machine's existing relay switch (`question_relay.enabled`): off means nothing fires, exactly as with questions.
- The carrier is fire-and-forget: it never blocks, never answers, and its failure changes nothing at the terminal.
- Fleet wiring (`set-relay-wire` and the deploy templates) includes the new hook in the "wired" check, so an unwired project is named by the header the same way question-unwired projects already are.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-question-relay`: a new requirement class — notify-only delivery of non-question blocking messages through the same switch and outbound, with never-block and terminal-fallback guarantees.

## Impact

- `bin/set-hook-notify-relay` (new carrier hook), `lib/set_orch/fleet/question_relay.py` (notify delivery + readiness), `.claude/settings.json` (Notification hook), `bin/set-relay-wire` and `templates/core/settings` fragments (wiring + the unwired check), the web header's unwired naming (already reads the wire list — no API shape change beyond the missing-hook list gaining one entry).
- The machine's outbound (chat bridge) needs a notify-only entry point; that lives in the bridge's own repository and is a deployment dependency, not a framework contract.
