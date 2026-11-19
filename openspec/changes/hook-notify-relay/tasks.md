## 1. Library: notify delivery beside the question relay

- [x] 1.1 `notify()` in `lib/set_orch/fleet/question_relay.py`: switch-gated, reads `question_relay.notify_command` falling back to `question_relay.webhook_url`, one attempt, drops with a named missing key when neither is set [REQ: notify-configuration-is-reported-never-completed-by-guess]
- [x] 1.2 Never-block guarantees: no wait on any answer, no retry, failures logged with reasons (missing key, non-zero exit, unreadable shape), and no message text persisted in any record or log [REQ: notify-configuration-is-reported-never-completed-by-guess]
- [x] 1.3 Notification envelope `{"kind":"notification","project":...,"agent":...,"session_id":...,"message":...}` on the notify command's stdin; webhook path posts one minimal message honouring `question_relay.webhook_detail` [REQ: a-non-question-blocking-message-is-notified-never-answered]

## 2. Carrier hook and wiring

- [x] 2.1 `bin/set-hook-notify-relay`: thin carrier — reads the notification event on stdin, asserts the shape (no message → logged drop), calls `notify()`, always exits 0, logs to the relay's log file [REQ: a-non-question-blocking-message-is-notified-never-answered]
- [x] 2.2 Switch-off fast path: exits before touching the log file or starting any process [REQ: a-non-question-blocking-message-is-notified-never-answered]
- [x] 2.3 Hook entry with a 10 s timeout in `.claude/settings.json` (Notification event) and in the deploy template fragment consumers receive [REQ: a-non-question-blocking-message-is-notified-never-answered]
- [x] 2.4 `set-relay-wire` and readiness: the wire check counts the notification carrier; an unwired project is named with the missing hook in the existing unwired list [REQ: the-wire-check-counts-the-notification-hook]

## 3. Tests and acceptance

- [x] 3.1 Unit tests: switch on + notify command → one call with the envelope on stdin, exit 0; switch off → zero processes; missing keys → dropped, readiness names the key; notify command failing → one attempt, logged reason [REQ: notify-configuration-is-reported-never-completed-by-guess]
- [x] 3.2 Carrier test: notification stdin → exits 0 fast, produced no tool-affecting output; malformed stdin → logged drop, exit 0 [REQ: a-non-question-blocking-message-is-notified-never-answered]
- [x] 3.3 Wire test: a project missing only the notification hook appears in the unwired list with the carrier named [REQ: the-wire-check-counts-the-notification-hook]
- [ ] 3.4 Live acceptance (the PIPE is proven live 2026-11-19: sandbox switch, real outbound, real channel — `delivered (120 chars)`, exit 0; the machine switch is ON since 2026-11-19 evening and the fleet is wired (`set-relay-wire --registered`, 20+ projects); enrichment added the same evening: the generic event text gains the pending call from the transcript — measured live "Claude needs your permission to use Bash — Bash: git merge --no-ff …") on this machine: with the switch on and a notify outbound configured, a real permission prompt produces the notification on the channel within seconds while the terminal keeps its prompt; the switch-off state produces nothing [REQ: a-non-question-blocking-message-is-notified-never-answered]

<!--
## Acceptance Criteria (from spec scenarios)

1.1–1.3 → "Notify configuration is reported, never completed by guess" + envelope clauses of "A non-question blocking message is notified, never answered"
2.1–2.3 → "A non-question blocking message is notified, never answered" (switch-off + prompt-relayed scenarios)
2.4, 3.3 → "The wire check counts the notification hook"
3.4 → the "Permission prompt relayed" and "Switch off" scenarios, measured live
-->
