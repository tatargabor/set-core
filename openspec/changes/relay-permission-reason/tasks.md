## 1. Reason store (lib/set_orch/fleet/question_relay.py, core)

- [x] 1.1 Key function: `ask_reason_key(tool_name, tool_input)` → sha256 of the tool name and canonical JSON (`sort_keys`, compact separators), first 24 hex chars [REQ: a-hook-can-hand-its-ask-reason-to-the-relay]
- [x] 1.2 `store_ask_reason(hook_input, base, wall)`: validate session, tool name and reason; write `<state>/ask-reasons/<session8>-<key>.json` with reason (≤ 600 chars), source and time, atomically; prune stale records first; log the session prefix and outcome only [REQ: a-hook-can-hand-its-ask-reason-to-the-relay]
- [x] 1.3 `take_ask_reason(session_id, tool_name, tool_input, base, wall)`: return a fresh (≤ 600 s) matching record and delete it; prune stale ones; any read error returns None [REQ: the-permission-post-shows-the-matching-reason]
- [x] 1.4 Prune: remove records older than the window on every store or take [REQ: a-reason-does-not-outlive-its-prompt]

## 2. Carrier (bin/set-hook-notify-relay)

- [x] 2.1 `--ask-reason` mode: read one JSON object on stdin, return 0 at once when the switch is off, otherwise call `store_ask_reason`; print nothing, exit 0 on every path, log no content [REQ: a-hook-can-hand-its-ask-reason-to-the-relay]

## 3. Post text

- [x] 3.1 `permission_question` shows a Bash command up to 1200 characters with a `… [+N chars cut]` marker when longer; other tools keep `_tool_summary` [REQ: the-permission-post-shows-the-command-in-full-up-to-a-bound]
- [x] 3.2 `permission_question` takes the matching reason via `take_ask_reason` and adds `Why it asks (<source>): <reason>`; `permission()` passes its base and clock [REQ: the-permission-post-shows-the-matching-reason]

## 4. Tests (tests/unit/test_relay_ask_reason.py)

- [x] 4.1 Store and carrier: stored while on, nothing while off, malformed input ignored, no command or reason text in the log, exit 0 with no output [REQ: a-hook-can-hand-its-ask-reason-to-the-relay]
- [x] 4.2 Matching: a fresh matching reason is shown and consumed; another command's reason is not shown; a stale reason is not shown and is removed; no reason keeps the post without a `Why it asks` line [REQ: the-permission-post-shows-the-matching-reason]
- [x] 4.3 Command bound: 1500 characters cut at 1200 with a marker naming 300; 200 characters shown whole [REQ: the-permission-post-shows-the-command-in-full-up-to-a-bound]
- [x] 4.4 Prune on write removes a record older than the window [REQ: a-reason-does-not-outlive-its-prompt]
- [x] 4.5 Prove the tests: swap the fixed module back to HEAD and see the new tests fail (clear the `.pyc`), then restore and run the relay suites [REQ: the-permission-post-shows-the-matching-reason]

## 5. Adoption and acceptance

- [x] 5.1 Announce the carrier and its stdin shape on the bus to the family plugin's owner [REQ: a-hook-can-hand-its-ask-reason-to-the-relay]
- [ ] 5.2 Live acceptance: a real guarded command whose guard calls the carrier reaches the channel with its `Why it asks` line and its command; record the measurement in B-188 and close (a) [REQ: the-permission-post-shows-the-matching-reason]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the switch is on and the carrier receives a session, tool, input and reason THEN one reason record exists and the carrier exits 0 with no output [REQ: a-hook-can-hand-its-ask-reason-to-the-relay, scenario: reason-stored-while-the-relay-is-on]
- [x] AC-2: WHEN the switch is off THEN no record is written and the carrier exits 0 with no output [REQ: a-hook-can-hand-its-ask-reason-to-the-relay, scenario: nothing-stored-while-the-relay-is-off]
- [x] AC-3: WHEN stdin is not a JSON object or a field is missing THEN nothing is written and the carrier exits 0 [REQ: a-hook-can-hand-its-ask-reason-to-the-relay, scenario: malformed-input-is-ignored]
- [x] AC-4: WHEN the carrier writes or skips THEN its log names the session prefix and outcome only [REQ: a-hook-can-hand-its-ask-reason-to-the-relay, scenario: no-command-or-reason-text-in-the-log]
- [x] AC-5: WHEN a fresh matching reason exists and the prompt is relayed THEN the post carries `Why it asks (<source>):` and the record is gone [REQ: the-permission-post-shows-the-matching-reason, scenario: a-fresh-matching-reason-appears-in-the-post]
- [x] AC-6: WHEN the stored reason is for another command THEN the post has no `Why it asks` line [REQ: the-permission-post-shows-the-matching-reason, scenario: a-reason-for-another-command-is-not-shown]
- [x] AC-7: WHEN the only matching reason is older than 600 s THEN no `Why it asks` line and the record is removed [REQ: the-permission-post-shows-the-matching-reason, scenario: a-stale-reason-is-not-shown]
- [x] AC-8: WHEN no reason was stored THEN the post has no `Why it asks` line [REQ: the-permission-post-shows-the-matching-reason, scenario: no-reason-keeps-today-s-post]
- [x] AC-9: WHEN a Bash command is 1500 characters THEN the post shows 1200 and a marker naming 300 [REQ: the-permission-post-shows-the-command-in-full-up-to-a-bound, scenario: a-long-bash-command]
- [x] AC-10: WHEN a Bash command is 200 characters THEN it is shown whole with no marker [REQ: the-permission-post-shows-the-command-in-full-up-to-a-bound, scenario: a-short-bash-command]
- [x] AC-11: WHEN a record older than 600 s exists and a new reason is stored THEN the old record is removed [REQ: a-reason-does-not-outlive-its-prompt, scenario: stale-records-are-pruned-on-the-next-write]
