Groups carry `<!-- depends: -->` annotations because this change is a good candidate to be
driven by the engine it is about. Absence means *depends on the previous group* (fail-closed),
so every independent group states it.

## 1. Start integrity — resolution before the claim

<!-- depends: none -->

- [ ] 1.1 Add a resolution step in the owner that takes the FINAL child environment (after the `CLAUDE*` strip and after `env=` is applied) and answers whether `argv[0]` can be executed in it. One function, one argument, no reads of `os.environ` inside it — the design's D1 seam, placed so the parallel provider track's `env=` changes flow through it unchanged. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]
- [ ] 1.2 Refuse an unresolvable command BEFORE `pty.fork()`, with a message naming the command and the PATH it was looked for in — and not naming a scope, a unit, or a service. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]
- [ ] 1.3 Prove the seam rather than either side of it: a test that resolves against an environment DIFFERENT from the test process's own and shows the caller's environment does not decide the answer. ⚠ A test that sets `PATH` for itself measures the proxy, not the thing. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]
- [ ] 1.4 Refusal leaves nothing claimed: no label held, no scope of that name, and an immediately repeated start is not refused as already running. [REQ: resolution-happens-before-anything-is-claimed]
- [ ] 1.5 The post-fork failure path reports the child's exit status instead of `did not become active` when the child died rather than the scope failing to register. Keep the liveness wait for the case it was written for. [REQ: resolution-happens-before-anything-is-claimed]
- [ ] 1.6 Assert the measured shape as a regression test: unresolvable command → refusal naming the command, no four-second wait, and the string `did not become active` absent from the message. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]
- [ ] 1.7 Keep the argv construction unforgeable and checkable: the command name and starting subcommand stay in one place, and a test resolves the subcommand against the engine's own parser (it must be one that starts a unit). [REQ: one-command-name-checkable-against-the-engine-s-own-parser]
- [ ] 1.8 Install `set-work-cycle` where the owner resolves it, and verify with the owner's OWN environment: `env -i PATH=<owner PATH> sh -c 'command -v set-work-cycle'` prints a path. ⚠ This is step 2 of the migration plan and NOT a substitute for 1.1–1.2 — record which of the two open options from the design was chosen and why. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]

## 2. What a run leaves behind — the record

<!-- depends: none -->

- [ ] 2.1 Carry the declared origin into the unit record, distinguishable from an assumed one; a run started with none records *not declared*, never a default that reads like a declaration. [REQ: a-run-records-where-it-came-from]
- [ ] 2.2 ⚠ Pass the REQUESTER through: the unit-start route sends the identified requester in the engine's `--started-by` instead of the literal `fleet-surface` (`fleet.py:1562`), and the literal survives only as the fallback when no requester was given. Without this the record carries one constant for every screen-started run and the change's own question stays unanswered. [REQ: a-run-records-where-it-came-from]
- [ ] 2.3 Render origin as a CLAIM, not a measurement, everywhere it is serialised — it is a caller's assertion the framework does not verify. [REQ: a-run-records-where-it-came-from]
- [ ] 2.4 Persist the agent session identifier read off the session's own stream; a session that never announced one records *unknown*, distinguishable from a run with no session. [REQ: a-run-records-which-agent-session-executed-it]
- [ ] 2.5 Make the session's transcript reachable from the record (the identifier plus what a reader needs to locate it), without the framework copying any of it. [REQ: a-run-records-which-agent-session-executed-it]
- [ ] 2.6 A record written before these fields existed still reads: absent fields report *unknown* / *not declared* rather than failing to parse. [REQ: a-run-records-which-agent-session-executed-it]
- [ ] 2.7 Carry the new fields across the D10 seam the way this repo already does it: extend the reader on the `set_orch` side AND the test that fails when the two copies diverge (`tests/unit/test_fleet_awaiting.py` is the worked example). A field added on one side only is invisible, not broken. [REQ: a-run-records-which-agent-session-executed-it]

## 3. What a run leaves behind — the stream

<!-- depends: 2 -->

- [ ] 3.1 Wire `on_event` to an incremental JSONL sink beside the unit record, under the tree the engine was given — never a framework-side path. [REQ: a-run-s-stream-survives-the-process-that-produced-it]
- [ ] 3.2 Write as events arrive, not at the end: a run killed mid-way keeps everything up to the kill. Test by killing, not by returning early. [REQ: a-run-s-stream-survives-the-process-that-produced-it]
- [ ] 3.3 Mark a completed stream as complete, so a truncated one is distinguishable from a finished one. ⚠ A missing terminator and a stream that never started must not look alike. [REQ: a-run-s-stream-survives-the-process-that-produced-it]
- [ ] 3.4 A run that produced no stream states the absence; nothing renders it as an empty successful run. [REQ: a-run-s-stream-survives-the-process-that-produced-it]
- [ ] 3.5 Assert the confidentiality boundary as a test: the sink resolves under the tree passed to the engine, for a tree that is NOT the framework's own. [REQ: the-stream-is-written-where-the-project-owns-it-never-into-the-framework]
- [ ] 3.6 Assert that framework logs about a run carry identifiers, counts and outcome and NO text taken from the stream — the check is on the log output, not on the intent. [REQ: the-stream-is-written-where-the-project-owns-it-never-into-the-framework]

## 4. Reading scope — what a project may declare

<!-- depends: none -->

- [ ] 4.1 Accept a list of reading paths in the adoption declaration, alongside `changes_dir` and `gates`; a declaration without the key behaves exactly as today. [REQ: a-project-may-declare-where-a-unit-reads-from]
- [ ] 4.2 Carry them into the unit prompt, presented SEPARATELY from the change's own artifacts — one is the work, the other is background. [REQ: a-project-may-declare-where-a-unit-reads-from]
- [ ] 4.3 Report a declared path that does not exist, on the start and on the run record; the run proceeds with what does exist. [REQ: a-declared-path-that-is-not-there-is-reported-not-silently-dropped]
- [ ] 4.4 Distinguish *the declaration reached nothing* from *nothing was declared*. [REQ: a-declared-path-that-is-not-there-is-reported-not-silently-dropped]
- [ ] 4.5 Refuse a declared path resolving outside the project tree, naming it; no content from outside the tree reaches the prompt. Test with a traversal and with a symlink — the two are different escapes. [REQ: a-declaration-reaches-outside-the-change-directory-but-never-outside-the-project]

## 5. The read API the screen needs

<!-- depends: 2, 3 -->

⚠ **Half of this is already built — measure before writing.** `lib/set_orch/fleet/purpose.py`
`read_purposes()` already walks every unit record for a project and computes
`finished | running | stale` with pid verification; `lib/set_orch/fleet/awaiting.py` already
parses the awaiting marker. These tasks EXTEND those readers. Building a second reader of one
state is the defect this group exists to avoid.

- [ ] 5.1 Extend `Purpose` with the fields it does not carry: gate outcome, commit, set-aside condition, origin and session. Same reader, same seam — no new one. [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive]
- [ ] 5.2 Assert that the existing stale detection still holds after the extension, INCLUDING `pid_unverified` — this is a regression guard on behaviour that already ships, not a new build. [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive]
- [ ] 5.3 Expose a project's runs as a LIST (today the reader is joined per-pid onto an agent tile, so a run with no live process has nowhere to appear). [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive]
- [ ] 5.4 Serve *what is runnable and why not* by running `set-work-cycle status --json` and caching it — refreshed on a start, on a finish and on a task-file change, never per poll. ⚠ Do NOT copy the group/dependency resolver into `set_orch`: the second-copy pattern here is for constants and regexes with a divergence test, and a fail-closed resolver with cycle detection is not that kind of copy. [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started]
- [ ] 5.5 The run list renders when the engine is NOT installed: records read, runnability reported as unavailable with the reason. A missing engine must not empty the screen. [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started]
- [ ] 5.6 Report a project with no adoption declaration as not adopted, naming what is missing — distinct from a project with no changes. [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started]
- [ ] 5.7 Serve a finished run's persisted stream, labelled as a recording, with its completeness stated. [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock]

## 6. The screen

<!-- depends: 5 -->

- [ ] 6.1 Per project: the changes the engine can drive, each with runnable state or the engine's reason. Table over cards — the rows are comparable. [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started]
- [ ] 6.2 The not-adopted and nothing-runnable states, each saying which it is. A zero here is a shape error until the input's shape has been looked at. [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started]
- [ ] 6.3 A start control that offers no command, argv or label field — only the change, the seat and the optional limit and model. [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point]
- [ ] 6.4 Show a refusal where the person acted, in the refusal's own words, with nothing shown as started. Covers all three refusal sources: the engine, the location check, the unresolvable command. [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point]
- [ ] 6.5 When the terminal-holding service is unavailable, the control states it cannot start and what to run — it is not a control that fails when used. [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point]
- [ ] 6.6 Render a run: origin (as a claim), seat, session, verdict, gate, commit, set-aside condition and its question. A run that never reported a verdict gets its own state, not "no outcome yet". [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive]
- [ ] 6.7 An unconfirmed live claim says which question was answered — a process holds that identifier, not that the run is alive — and is not rendered as an ordinary running run. [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive]
- [ ] 6.8 Mark failed / set-aside / stale runs ON the container the reader can see — with a count, not merely a dot — wherever runs are collapsed, grouped or behind a tab. [REQ: a-failing-run-is-marked-where-the-reader-is-standing]
- [ ] 6.9 No marker when nothing is wrong — AND the absence must not be produced by state the screen failed to read. Assert the read-failure path separately. [REQ: a-failing-run-is-marked-where-the-reader-is-standing]
- [ ] 6.10 Open a running unit's terminal in the project's existing dock, labelled as a work unit with its change, distinguishable from a hand-started session. [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock]
- [ ] 6.11 Closing the view does not stop the run, and the run stays reachable from the project's runs. [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock]
- [ ] 6.12 A finished run opens its recording in the same place, explicitly marked as a recording rather than a live terminal. [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock]

## 7. Looking at it, and closing the loop

<!-- depends: 6 -->

- [ ] 7.1 Open every touched screen in the browser against the running dashboard and describe what is SEEN — including the refused-start state, the not-adopted state and the empty state. ⚠ If the browser cannot be reached, this task stays OPEN and the commit says so; no passing test run substitutes for it. [REQ: the-screen-is-verified-by-looking-at-it]
- [ ] 7.2 Prove the fixes are fixes: stash each and re-run its test, confirming red without the change and green with it. Assert both the mutation and the restore. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]
- [ ] 7.3 Close B-105 in `openspec/bugs/README.md` with the commit sha and the re-run of its own measurement; the entry stays. [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine]
- [ ] 7.4 Drive one non-trivial change with the engine THROUGH THE SCREEN, end to end, and record what it produced — the product, not the exit code. This is the evidence the change is finished. [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point]

## Acceptance Criteria (from spec scenarios)

### work-unit-start-integrity

- [ ] AC-1: WHEN a work-unit start is requested and the engine command does not resolve in the child's environment THEN the request is refused, with no scope, label or process identifier reported, and the refusal names the command and the environment [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine, scenario: the-engine-command-cannot-be-resolved-in-the-child-s-environment]
- [ ] AC-2: WHEN the engine command resolves in the child's environment THEN the start proceeds and the response carries the label, the process identifier and the argument vector [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine, scenario: the-engine-command-resolves]
- [ ] AC-3: WHEN a start is refused because the command could not be resolved THEN the refusal names the missing command, does not report a scope/unit/service that did not become active, and does not make the caller wait for a liveness timeout [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine, scenario: the-refusal-names-the-cause-not-the-symptom]
- [ ] AC-4: WHEN the command resolves in the handling process's environment but not in the child's THEN the start is refused with the same refusal as if neither could resolve it [REQ: a-start-is-reported-as-started-only-when-the-child-could-become-the-engine, scenario: a-caller-s-environment-that-differs-from-the-child-s-does-not-decide-the-answer]
- [ ] AC-5: WHEN a start is refused for an unresolvable command THEN no label is held, no scope exists, and a subsequent start of the same unit is not refused as already running [REQ: resolution-happens-before-anything-is-claimed, scenario: an-unresolvable-command-leaves-nothing-behind]
- [ ] AC-6: WHEN the child fails to become the engine after the scope was claimed THEN the claim is released and the caller is told the start failed with the child's exit status [REQ: resolution-happens-before-anything-is-claimed, scenario: the-child-fails-to-exec-for-a-reason-resolution-cannot-predict]
- [ ] AC-7: WHEN a caller requests a work-unit start THEN no field of that request can name the command, the subcommand or an arbitrary argument [REQ: one-command-name-checkable-against-the-engine-s-own-parser, scenario: the-argv-is-built-never-supplied]
- [ ] AC-8: WHEN the engine's parser no longer recognises the named starting subcommand as one that starts a unit THEN the check fails rather than the mismatch surviving until a run is attempted [REQ: one-command-name-checkable-against-the-engine-s-own-parser, scenario: a-subcommand-that-no-longer-starts-a-unit-is-caught]

### work-unit-run-observability

- [ ] AC-9: WHEN a unit is started with a declared origin THEN the record carries it verbatim and it is readable without the starting process [REQ: a-run-records-where-it-came-from, scenario: a-declared-origin-is-recorded]
- [ ] AC-10: WHEN a unit is started on behalf of an identified requester THEN the record carries that requester and not a constant naming the surface that relayed the request [REQ: a-run-records-where-it-came-from, scenario: the-origin-is-the-requester-not-the-surface-that-relayed-it]
- [ ] AC-11: WHEN a unit is started without a declared origin THEN the record states that none was declared and names no source [REQ: a-run-records-where-it-came-from, scenario: no-origin-was-declared]
- [ ] AC-12: WHEN the started session announces its identifier THEN the record carries it and a reader can reach the session's transcript from the record [REQ: a-run-records-which-agent-session-executed-it, scenario: the-session-announced-its-identifier]
- [ ] AC-13: WHEN the session ends without announcing an identifier THEN the record states it is unknown and the run is not recorded as having no session [REQ: a-run-records-which-agent-session-executed-it, scenario: the-session-ended-without-announcing-one]
- [ ] AC-14: WHEN a unit has finished and neither its process nor its terminal exists THEN the run's stream is readable from the project's runtime area, keyed to its unit record [REQ: a-run-s-stream-survives-the-process-that-produced-it, scenario: a-finished-run-is-read-after-the-fact]
- [ ] AC-15: WHEN a run is killed before it produces a verdict THEN the stream persisted so far remains and is distinguishable from a completed run's [REQ: a-run-s-stream-survives-the-process-that-produced-it, scenario: a-run-is-killed-mid-way]
- [ ] AC-16: WHEN a run produced no stream THEN the absence is stated and it is not rendered as an empty but successful run [REQ: a-run-s-stream-survives-the-process-that-produced-it, scenario: a-run-that-produced-no-stream-at-all]
- [ ] AC-17: WHEN the framework logs anything about a run THEN the log carries identifiers, counts and outcome and no text taken from the stream [REQ: the-stream-is-written-where-the-project-owns-it-never-into-the-framework, scenario: the-framework-logs-a-run]
- [ ] AC-18: WHEN a unit runs in a project tree that is not the framework's own THEN its stream is written under that project's runtime area and nothing derived from it is written under the framework's tree [REQ: the-stream-is-written-where-the-project-owns-it-never-into-the-framework, scenario: a-run-in-a-project-outside-the-framework-s-tree]

### work-cycle-reading-scope

- [ ] AC-19: WHEN a project declares additional reading paths and a unit is started THEN the unit is told about them, presented separately from the change's own artifacts [REQ: a-project-may-declare-where-a-unit-reads-from, scenario: a-project-declares-reading-paths]
- [ ] AC-20: WHEN a project's declaration carries no reading paths THEN the unit reads exactly what it reads today and the engine adds no path of its own [REQ: a-project-may-declare-where-a-unit-reads-from, scenario: a-project-declares-none]
- [ ] AC-21: WHEN a declared reading path does not exist THEN the start reports which path was missing and the run proceeds with the paths that do exist [REQ: a-declared-path-that-is-not-there-is-reported-not-silently-dropped, scenario: a-declared-path-is-missing]
- [ ] AC-22: WHEN none of the declared reading paths exist THEN the caller is told the declaration reached nothing, distinguishably from a project that declared nothing [REQ: a-declared-path-that-is-not-there-is-reported-not-silently-dropped, scenario: every-declared-path-is-missing]
- [ ] AC-23: WHEN a declared reading path resolves outside the project tree THEN it is refused and named, and no content from outside the tree reaches the prompt [REQ: a-declaration-reaches-outside-the-change-directory-but-never-outside-the-project, scenario: a-path-escaping-the-project-tree]

### work-cycle-screen

- [ ] AC-24: WHEN the screen shows a project that has adopted the engine THEN each change is listed with whether a unit is runnable, and a change that is not carries the engine's reason [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started, scenario: an-adopted-project-with-a-runnable-change]
- [ ] AC-25: WHEN the screen shows a project with no adoption declaration THEN it is shown as not adopted, naming what is missing, and no start is offered [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started, scenario: a-project-that-has-not-adopted-the-engine]
- [ ] AC-26: WHEN no change in a project has a runnable group THEN the screen says so with per-group reasons, distinguishably from a project with no changes [REQ: a-project-s-changes-and-their-runnable-state-are-visible-before-anything-is-started, scenario: nothing-is-runnable]
- [ ] AC-27: WHEN a person starts a unit for a change from the screen THEN the run appears among that project's runs with its change, group and seat [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point, scenario: a-unit-is-started]
- [ ] AC-28: WHEN the start is refused by the engine, the location check, or an unresolvable command THEN the refusal is shown where the person acted, in its own words, and nothing is shown as started [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point, scenario: the-start-is-refused]
- [ ] AC-29: WHEN the service that would hold the run's terminal is unavailable THEN the control states it cannot start and what to run to repair it, rather than failing when used [REQ: a-unit-is-started-from-the-screen-through-the-engine-s-own-entry-point, scenario: the-service-that-holds-terminals-is-unavailable]
- [ ] AC-30: WHEN a run has finished and its process is gone THEN its verdict, gate outcome and commit are shown from the record with nothing running [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive, scenario: a-finished-run]
- [ ] AC-31: WHEN recorded state claims a run in progress whose process is no longer alive THEN it is shown as stale, not as running [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive, scenario: a-stale-claim]
- [ ] AC-32: WHEN a record claims a live run and the process holding that identifier cannot be confirmed to be the agent THEN the surface says which question was answered and does not render it as an ordinary running run [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive, scenario: a-live-claim-whose-process-identifier-could-not-be-confirmed]
- [ ] AC-33: WHEN a run was set aside because a person must answer THEN the question and its task are shown and the run is not shown as failed [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive, scenario: a-run-set-aside-for-a-person]
- [ ] AC-34: WHEN a run ended without reporting a verdict THEN that is shown as its own state, not as a run with no outcome yet [REQ: a-run-is-readable-from-what-the-engine-recorded-with-no-process-alive, scenario: a-run-that-never-reported-a-verdict]
- [ ] AC-35: WHEN a project's runs are collapsed and one of them failed THEN the collapsed container carries a marker naming how many [REQ: a-failing-run-is-marked-where-the-reader-is-standing, scenario: a-failure-inside-a-collapsed-group]
- [ ] AC-36: WHEN no run failed, was set aside, or is stale THEN no marker is shown, and the absence is not produced by state the screen failed to read [REQ: a-failing-run-is-marked-where-the-reader-is-standing, scenario: everything-is-well]
- [ ] AC-37: WHEN a person opens a running unit from the screen THEN its terminal appears in that project's dock, labelled as a work unit with its change [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock, scenario: opening-a-running-unit-s-terminal]
- [ ] AC-38: WHEN a person closes a running unit's terminal view THEN the run continues and remains reachable from the project's runs [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock, scenario: closing-the-view]
- [ ] AC-39: WHEN a person opens a run whose process has ended THEN the run's persisted stream is shown, labelled as a recording rather than a live terminal [REQ: a-running-unit-s-terminal-is-reachable-in-the-project-s-dock, scenario: a-finished-run-has-no-terminal]
- [ ] AC-40: WHEN the work is claimed complete THEN each touched screen has been opened and described by what was seen, including the refused-start and empty states [REQ: the-screen-is-verified-by-looking-at-it, scenario: the-screens-are-looked-at]
- [ ] AC-41: WHEN the browser cannot be reached to perform that check THEN the verification is reported as not done and no passing test run is offered in its place [REQ: the-screen-is-verified-by-looking-at-it, scenario: the-browser-cannot-be-reached]
