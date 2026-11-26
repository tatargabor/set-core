## 1. Keep an open question on the relay

- [x] 1.1 `relay(repull=…)`: on a timeout-only release, park then re-pull; never on a switch-off, a fleet release or an outbound failure; a failing re-pull still releases
- [x] 1.2 The hook passes `relay_backfill.repull_after_timeout` (a pull-in with trigger `hook-timeout`)
- [x] 1.3 The carrier waits without the relay's timeout (`CARRY_MAX_S` = 24 h cap)
- [x] 1.4 `--help` / `-h` print usage and act on nothing; an unknown option exits 2
- [x] 1.5 Tests: 6 new; they fail without the fix (stash-and-rerun: 30 failed); 528 relay tests green
- [x] 1.6 Live: a question that reaches the hook's limit stays on the panel (watch `relay.log` for `handed to a carrier to keep it on the relay`) — 2026-11-26, `relay.log`: 22:10:31 `[178edfb4]: no answer within 3300 s; released`, 22:10:47 `the hook's time ran out; handed to a carrier to keep it on the relay`, 22:10:47 backfill pulled it back as the same id `relay-178edfb4-08927f5f`. 22:10:51 the carrier stopped (`answered in the terminal; nothing typed`): the session's transcript shows the call's result was a PreToolUse error from that project's own AskUserQuestion gate, not an answer; the agent re-asked and the new call was on the relay at 22:12:21 (`relay-178edfb4-43d3eac7`). The continuation beside it (`e33f330b`) dropped at 21:54 — out of this change's scope, registered as B-250

## Acceptance

- [x] AC-1: WHEN the hook's time runs out on an unanswered question THEN it is pulled straight back in [REQ: a-question-the-hook-lets-go-only-for-lack-of-time-is-pulled-back-in, scenario: the-hook-s-time-runs-out]
- [x] AC-2: WHEN a pulled-in question waits longer than the hook's limit THEN its carrier still types the channel answer [REQ: a-pulled-in-question-ends-like-a-relayed-one, scenario: a-long-wait]
