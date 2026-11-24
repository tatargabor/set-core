## 1. Core

- [x] 1.1 `auto_answer.off_agents(get)`, `set_agent_off(entry, off)`, and `agent_off(session_id, get, resolve_label)` → the matching entry or None; the label is resolved through the owner (pid → session record), and a failed resolution is logged at WARNING. Tests. [REQ: automatic-answers-can-be-turned-off-for-one-agent]
- [x] 1.2 The outbound: with the switch on and the asking session opted out, forward byte for byte and spawn nothing; log the entry. `relay_backfill.undecided_waiting` skips such sessions. Tests, one per path; a mutation of the check is caught. [REQ: automatic-answers-can-be-turned-off-for-one-agent]
- [x] 1.3 `set-auto-answer here off|on|status`: walk up from the parent pid to the first process with a session record, resolve its label, and store `label:` (else `session:`). Tests with a fake process tree. [REQ: automatic-answers-can-be-turned-off-for-one-agent]

## 2. API and screen

- [x] 2.1 `GET /api/fleet/auto-answer` carries `off_agents`; `POST /api/fleet/auto-answer/agent {label | session, off}`. Route tests. [REQ: automatic-answers-can-be-turned-off-for-one-agent]
- [x] 2.2 Fleet terminal header: an icon toggle (bot icon), amber and active while this label is opted out; the accessible name says what it does. The automatic-answer panel lists the opted-out agents, each with "on again". `tsc -b`, the web suite, `pnpm build`. [REQ: automatic-answers-can-be-turned-off-for-one-agent]
- [x] 2.3 Visual check in the browser: toggle it on a terminal header, see the panel list it, turn it back on from the panel. Say what is seen. [REQ: automatic-answers-can-be-turned-off-for-one-agent]

## 3. Live

- [x] 3.1 A scratch fleet agent with its label opted out asks through the real decider outbound (a no-op forward): the outbound log says opted out, no worker starts, nothing is decided. Record it in `measurements.md`. [REQ: automatic-answers-can-be-turned-off-for-one-agent]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the operator opts out the agent they work at and it asks THEN the question reaches the channel unchanged and nothing is written [REQ: automatic-answers-can-be-turned-off-for-one-agent, scenario: planning-at-one-agent]
- [x] AC-2: WHEN another agent asks THEN it is decided as before [REQ: automatic-answers-can-be-turned-off-for-one-agent, scenario: the-other-agents-are-unaffected]
- [x] AC-3: WHEN the opted-out terminal clears and asks under a new session id THEN it is still opted out [REQ: automatic-answers-can-be-turned-off-for-one-agent, scenario: the-terminal-is-cleared] — live in measurements M3 (new session id after /clear, still opted out)
- [x] AC-4: WHEN `! set-auto-answer here off` runs in a fleet terminal THEN its label is opted out; `on` clears, `status` reports [REQ: automatic-answers-can-be-turned-off-for-one-agent, scenario: from-inside-the-session]
- [x] AC-5: WHEN the panel clears an opt-out THEN that agent's next question is decided again [REQ: automatic-answers-can-be-turned-off-for-one-agent, scenario: turned-back-on-from-the-panel]
