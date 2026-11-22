## 1. Measure before coding

- [ ] 1.1 In a throwaway interactive session (scratch tree, default permission mode, logging hooks), record the `Stop` payload's field names (is `prompt_id` there?), whether `UserPromptSubmit` fires for an `asyncRewake` wake, and what the transcript holds for a dialog answered in the terminal (the `tool_result` shape for allow and for deny). Write the findings into design.md's Context before 2.x starts [REQ: a-finished-turn-is-continuable-from-the-channel]

## 2. Wait detector verdict record (core, `lib/set_orch/fleet/`)

- [ ] 2.1 `wait_detect.decide()` writes `verdicts/<session>.json` (`turn`, `verdict`, `at`; no text) for every decision taken while the relay is on: classified, `SKIPPED` on `stop_hook_active`, `UNKNOWN` on classifier failure. The turn key comes from `prompt_id`, falling back to a sha256 of the final message. Write it atomically [REQ: the-detector-records-its-verdict-for-the-turn]
- [ ] 2.2 Unit tests: DONE, WAITING, SKIPPED and UNKNOWN records; no record while the relay is off; the record holds no message text (assert on a marker string); re-ask output unchanged [REQ: the-detector-records-its-verdict-for-the-turn]

## 3. Permission carrier

- [ ] 3.1 `question_relay.permission(hook_input, …)`: readiness gate (command target only), build a one-question envelope (project · agent label, tool, one-line call summary via `_tool_summary`, options `Allow`/`Deny`), hand it over, write the waiting record with `kind: permission`, and poll for the answer [REQ: a-permission-prompt-is-answerable-from-the-channel]
- [ ] 3.2 Answer mapping: literal `Allow` → allow; `Deny` → deny with the relay-channel message; any other text → deny quoting it. Never allow otherwise [REQ: a-permission-prompt-is-answerable-from-the-channel]
- [ ] 3.3 Terminal-first detection: bounded transcript-tail read; find the newest matching `tool_use` (name + input), and on a `tool_result` for it newer than the hook start, remove the record and exit without output. Releases: timeout, switch off, release marker, outbound failure [REQ: the-terminal-stays-live-and-whichever-side-answers-first-wins]
- [ ] 3.4 `bin/set-hook-permission-relay` thin carrier (stdin → library → stdout JSON, log to `relay.log`, always exit 0, no text in logs) and add it to `install.sh`'s script list [REQ: a-permission-prompt-is-answerable-from-the-channel]
- [ ] 3.5 Unit tests with injected run/clock/sleep: allow, deny, free-text deny, webhook target → no output, outbound failure, terminal-first release (fixture transcript), timeout, switch off. Prove the fail-closed mapping by mutating it to allow-on-anything and showing a test fails [REQ: a-permission-prompt-is-answerable-from-the-channel]

## 4. Continuation carrier

- [ ] 4.1 `lib/set_orch/fleet/continuation.py`: poll the verdict record for this turn's key (≤ 75 s), and act only on DONE [REQ: a-finished-turn-is-continuable-from-the-channel]
- [ ] 4.2 Summary and suggestions call: headless, same flags and guard as the classifier; parse `SUMMARY:` plus up to three `NEXT:` lines; malformed output → no options, free text only [REQ: a-finished-turn-is-continuable-from-the-channel]
- [ ] 4.3 Hand-over with `kind: continuation`, poll for the answer, then exit 2 with the instruction on stderr [REQ: a-finished-turn-is-continuable-from-the-channel]
- [ ] 4.4 Supersede: `UserPromptSubmit` marker newer than arm time, record id no longer its own, or a transcript assistant entry newer than arm time. Check every poll and once more immediately before exit 2. On supersede, remove the own record only, log, and exit 0 [REQ: a-stale-answer-never-acts]
- [ ] 4.5 `bin/set-hook-continue-relay` (exit code is the contract: 0 = nothing, 2 = wake) and `bin/set-hook-relay-supersede` (writes the marker, never blocks a prompt, always exits 0); add both to `install.sh` [REQ: a-stale-answer-never-acts]
- [ ] 4.6 Unit tests: DONE → posted → answered → exit 2 with the text; WAITING / SKIPPED / no verdict → exit 0 with nothing posted; each of the three supersede signals, including one raised between the answer arriving and the exit; malformed suggestions → posted without options; no summary, suggestion or answer text in the record or the log [REQ: a-stale-answer-never-acts]

## 5. Record shape, dedup, wiring

- [ ] 5.1 Both carriers write the waiting record in the question hook's shape plus `kind`. Test it against the bridge's documented reader expectations (`id` form, location, removal = release) [REQ: withdrawal-uses-the-bridge-s-existing-release-contract]
- [ ] 5.2 `notify()` skips a session with a permission or continuation record, re-checking after a grace of ≤ 3 s; unit tests for the skip and the unchanged path [REQ: a-prompt-the-relay-holds-is-not-reported-twice]
- [ ] 5.3 `_hooks_in` / `unwired_projects` / `wire_project` count and add the three entries (PermissionRequest matcher-all with timeout 3700; Stop with `asyncRewake: true` and timeout 3700; UserPromptSubmit with timeout 5), idempotently [REQ: the-wire-check-counts-the-new-hooks]
- [ ] 5.4 `bin/set-deploy-hooks` and this repo's `.claude/settings.json` gain the same entries; extend the existing wire tests [REQ: the-wire-check-counts-the-new-hooks]
- [ ] 5.5 The fleet reads the new records: confirm `list_waiting` and the header's waiting rendering handle `kind`. If the screen changes, rebuild `web/` and look at it in the browser (ui-quality rule: a UI change is not done until somebody looked) [REQ: withdrawal-uses-the-bridge-s-existing-release-contract]

## 6. Reconcile, verify, live acceptance

- [ ] 6.1 Reconcile with the not-yet-archived `hook-notify-relay`: its "notified, never answered" requirement must not contradict this change at archive time. Archive it first (its 3.4 live acceptance is open), then turn the overlap into a MODIFIED delta here [REQ: a-prompt-the-relay-holds-is-not-reported-twice]
- [ ] 6.2 Regression check with the `regression-baseline` skill (set diff against a baseline run, not a remembered number) [REQ: the-wire-check-counts-the-new-hooks]
- [ ] 6.3 Live acceptance, permission: with the switch on, a real Bash permission prompt in a scratch session reaches the channel as Allow/Deny. A channel Allow runs the command. A terminal-first answer closes the post (🔒). Exactly one channel item per prompt [REQ: a-permission-prompt-is-answerable-from-the-channel]
- [ ] 6.4 Live acceptance, continuation: a finished turn posts a continuation with suggestions. A channel answer wakes the session and it acts. A prompt typed first closes the post, and a late answer is dropped (log line). The terminal stays usable throughout [REQ: a-finished-turn-is-continuable-from-the-channel]
- [ ] 6.5 Close B-188(b) and B-190 in the bug register with the live measurements [REQ: a-stale-answer-never-acts]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the relay is on, a Bash call raises a permission prompt and the answer is `Allow` THEN the hook returns allow, the dialog closes and the tool runs [REQ: a-permission-prompt-is-answerable-from-the-channel, scenario: allowed-on-the-channel]
- [ ] AC-2: WHEN the answer is free text THEN the hook returns deny quoting the text and the agent continues with it [REQ: a-permission-prompt-is-answerable-from-the-channel, scenario: free-text-is-a-refusal-with-the-owner-s-words]
- [ ] AC-3: WHEN a PreToolUse hook returns `ask` with the relay on THEN the same question is posted and its answer resolves the dialog [REQ: a-permission-prompt-is-answerable-from-the-channel, scenario: a-hook-raised-confirmation]
- [ ] AC-4: WHEN the target is `webhook` THEN the permission hook exits 0 with no output [REQ: a-permission-prompt-is-answerable-from-the-channel, scenario: webhook-target]
- [ ] AC-5: WHEN the owner answers in the terminal first THEN the record is gone within one poll and a later channel answer acts on nothing [REQ: the-terminal-stays-live-and-whichever-side-answers-first-wins, scenario: answered-in-the-terminal-first]
- [ ] AC-6: WHEN the outbound exits non-zero THEN the permission hook exits at once with no output [REQ: the-terminal-stays-live-and-whichever-side-answers-first-wins, scenario: outbound-fails]
- [ ] AC-7: WHEN a DONE turn's continuation is answered THEN the hook exits 2 with the text and the session acts on it [REQ: a-finished-turn-is-continuable-from-the-channel, scenario: continued-from-the-channel]
- [ ] AC-8: WHEN the verdict is WAITING THEN the continuation hook posts nothing [REQ: a-finished-turn-is-continuable-from-the-channel, scenario: a-waiting-turn-is-not-double-asked]
- [ ] AC-9: WHEN a continuation waits THEN the terminal prompt is usable [REQ: a-finished-turn-is-continuable-from-the-channel, scenario: the-terminal-is-never-held]
- [ ] AC-10: WHEN the owner types a prompt while a continuation waits THEN its record is gone within one poll and the bridge closes the post [REQ: a-stale-answer-never-acts, scenario: the-owner-typed-first]
- [ ] AC-11: WHEN a newer assistant turn exists and a late answer arrives THEN it is dropped with a log line and nothing wakes [REQ: a-stale-answer-never-acts, scenario: a-late-answer-after-a-background-wake]
- [ ] AC-12: WHEN a carrier removes its record unanswered THEN the bridge's release check treats the post as released [REQ: withdrawal-uses-the-bridge-s-existing-release-contract, scenario: release-closes-the-post]
- [ ] AC-13: WHEN the permission carrier holds a prompt and the permission notification fires THEN exactly one channel item exists [REQ: a-prompt-the-relay-holds-is-not-reported-twice, scenario: permission-prompt-with-the-carrier-wired]
- [ ] AC-14: WHEN a project lacks the permission hook at every level THEN the unwired list names it and `set-relay-wire` adds it [REQ: the-wire-check-counts-the-new-hooks, scenario: a-project-missing-the-permission-hook]
- [ ] AC-15: WHEN the classifier answers DONE THEN the verdict record names DONE and that turn's key, and the hook output is unchanged [REQ: the-detector-records-its-verdict-for-the-turn, scenario: a-finished-turn-leaves-a-done-verdict]
- [ ] AC-16: WHEN a turn ends with `stop_hook_active` THEN the record names SKIPPED and no classifier runs [REQ: the-detector-records-its-verdict-for-the-turn, scenario: the-continued-turn-after-a-re-ask]
- [ ] AC-17: WHEN the relay is off THEN no verdict record is written [REQ: the-detector-records-its-verdict-for-the-turn, scenario: the-relay-is-off]
