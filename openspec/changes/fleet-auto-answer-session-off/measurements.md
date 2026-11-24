# fleet-auto-answer-session-off — measurements

## M1 — the real outbound leaves an opted-out terminal alone (task 3.1)

An isolated relay world (own `SET_CONFIG_DIR` and `SET_QUESTION_RELAY_DIR`): relay on,
`question_relay.command = set-auto-answer`, automatic answers ON, the forward a no-op (`true`),
and `auto_answer.off_agents = ["label:scratch-off"]`. A scratch fleet agent labelled
`scratch-off` (haiku, only the question hook wired) asked one question at 14:36:17. Its
`auto-answer.log`:

- `auto answer: off for this agent (label:scratch-off) — forwarding unchanged`
- `auto answer: off — forwarded unchanged (exit 0)`

No worker was started and no pending record was written (the state dir had no `auto-answer/`).
The label was resolved through the real owner daemon (session id → owner agent → label), so
the terminal-named opt-out held for a session the decider knew only by id.

## M2 — the controls in the browser (task 2.3)

`localhost:7400/fleet` after `pnpm build` and a set-web restart. On the `scratch-off`
terminal's header a bot icon sat left of the attach/stop group, named "automatic answers are on
here — click to turn them off for this terminal only". One click turned it amber (`BotOff`,
`data-fleet-terminal-auto-answer="off"`). `set-config get auto_answer.off_agents` then said
`["label:scratch-off"]`, and so did the route. The automatic-answer panel showed
"Off for these agents — their questions go to you unchanged · scratch-off · fleet terminal ·
on again". "on again" removed the row, emptied the config list (`[]`), and turned the header
icon back to `on`. Nothing under the header or the panel moved. The panel's own content got
one section shorter.
