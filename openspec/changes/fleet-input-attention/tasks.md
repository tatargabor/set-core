## 1. The measurement layer (`lib/set_orch/fleet/state.py`)

- [x] 1.1 Declare the status vocabulary (`busy` / `shell` / `idle` / `waiting`) and the attention classes (`working` / `background` / `input` / `prompt` / `unmeasured`) as module constants, with the binary-derived meaning of `shell` in the comment [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 1.2 Declare `INPUT_WAIT_AMBER_SECONDS = 15` and `INPUT_WAIT_RED_SECONDS = 180` in one place, plus a `tone_for(seconds)` helper returning `plain` / `amber` / `red` [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface]
- [x] 1.3 Add `attention`, `input_wait_seconds`, `runtime_status` and `background_running` to `AgentState`, defaulting to the unmeasured shape [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 1.4 Rewrite the `_apply_declared_wait` docstring IN PLACE with the 2026-08-28 measurement (10/10 stamp match, 2/10 mtime divergence, the pty transition latencies) so the next reader meets the correction rather than a contradiction [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop]
- [x] 1.5 Map the record's status to an attention class, computing `input_wait_seconds` from `statusUpdatedAt` for `input` and `prompt` and leaving it `None` otherwise [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop]
- [x] 1.6 Return `unmeasured` with a logged reason when the record is absent or carries no `status` key, and when the value is one this build does not recognise — an explicit final branch, never a fall-through onto a neighbour [REQ: a-missing-status-is-unmeasured-never-idle]
- [x] 1.7 Keep the log-measured `asking` and `working` states outranking the record, and keep carrying `declaration_ignored` when they disagree [REQ: a-measured-question-outranks-the-record]
- [x] 1.8 Verify no log line emitted on this path carries session text, a project name or an excerpt [REQ: nothing-measured-here-is-persisted]

## 2. Tests for the measurement layer

- [x] 2.1 Unit-test each status → class mapping, including a fabricated unknown status landing in `unmeasured` [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 2.2 Unit-test that a record with no `status` key yields `unmeasured` and no wait duration [REQ: a-missing-status-is-unmeasured-never-idle]
- [x] 2.3 Unit-test that the wait duration comes from `statusUpdatedAt` even when the log mtime is newer — the exact 2/10 shape measured [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop]
- [x] 2.4 Unit-test that an outstanding question tool keeps `asking` against an `idle` record, and that an outstanding Bash keeps `working` and records the disagreement [REQ: a-measured-question-outranks-the-record]
- [x] 2.5 Unit-test the three tone bands at 9 s / 45 s / 240 s, and that `background` resolves no tone at any age [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface]
- [x] 2.6 Prove each new test fails without its fix: `git stash && pytest <file>; git stash pop`, and record which ones passed either way [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop]

## 3. The API envelope (`lib/set_orch/api/fleet.py`)

- [x] 3.1 Carry `attention`, `input_wait_seconds`, `runtime_status` and `background_running` in `_agent_payload` [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 3.2 Carry the two thresholds in the fleet envelope so the client resolves tone from the server's numbers [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface]
- [x] 3.3 Add an attention tally to the envelope with an explicit unbucketed counter, matching the existing state-tally discipline [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 3.4 Test the payload shape, including that an unmeasured agent carries a null duration rather than a zero [REQ: a-missing-status-is-unmeasured-never-idle]

## 4. The web state layer (`web/src/lib/fleetAttention.ts`)

- [x] 4.1 Add the attention classes, the two threshold constants and `inputWaitTone(seconds, thresholds?)` resolving plain / amber / red every render [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface]
- [x] 4.2 Extend `Tally` with the attention counters, keeping the final `else` branch that makes an unrecognised class visible [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 4.3 Add `worstInputWait(agents)` returning the LONGEST wait in a set, for a project row and a group header [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 4.4 Unit-test the tone bands against the Python constants (a fixture asserting both sides carry 15 and 180) [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface]
- [x] 4.5 Unit-test `worstInputWait` picks the maximum, ignores `background` and `working`, and returns nothing for an empty set [REQ: the-project-menu-shows-the-worst-wait-it-contains]

## 5. The project menu (`web/src/components/FleetProjectColumn.tsx`)

- [x] 5.1 Render the input-wait escalation on the project row: an amber or red marker with the duration, from `worstInputWait` [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 5.2 Render the same escalation on the group header and on the parked summary, through the existing single `Counts` component [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 5.3 Move `unknown` off amber to a dashed hollow `fg-muted` marker, and update every test that asserted the amber [REQ: amber-means-waiting-for-you-and-nothing-else]
- [x] 5.4 Component-test that a collapsed group carrying a 5-minute waiter shows red on its header [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 5.5 Tint the project ROW itself — faint background plus a left edge bar in the tone, amber and red only — after the user's reading of the first version: *"a projekt kártya háttere lenne színezve, jobban látszik mint az agent darab és perc"* [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 5.6 Tint a CLOSED group's header the same way, and leave an open one to its rows, so the same fact is not stated twice [REQ: the-project-menu-shows-the-worst-wait-it-contains]

## 6. The agent state line (`web/src/pages/Fleet.tsx`)

- [x] 6.1 Extend `StateLine` for the four attention classes: working / background ("a background command is running") / waiting for input with its duration and tone / stopped at a prompt with its reason [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 6.2 Say on the state line whether a message would be acted on now or queued [REQ: the-surface-says-whether-typing-there-would-be-acted-on]
- [x] 6.3 Put the "the status tracks the loop, not the person" caveat in the tooltip beside the duration, where the reader is standing [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface]
- [x] 6.4 Component-test the four classes render distinctly and that an unmeasured agent renders neither a duration nor an amber marker [REQ: a-missing-status-is-unmeasured-never-idle]

## 7. Verification

- [x] 7.1 Run the Python unit suite and diff the failures against a baseline actually run on HEAD (`regression-baseline` skill), never against a remembered number [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop]
- [x] 7.2 Run the web unit suite and `tsc -b` in `web/` [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 7.3 Build `web/` so port 7400 serves the change [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 7.4 **VISUAL CHECK — open the fleet screen in the browser and LOOK at the project menu**: a working session green, a waiting one amber with its duration, one past 3 minutes red, one with a background command not amber at all. If the browser cannot be reached, this task stays OPEN and is said so in the commit [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 7.5 Cross-check the screen against a live measurement of the same PIDs' records at that moment — the screen and `~/.claude/sessions/*.json` must agree on each session's class [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop]

## 8. The colour vanished on a live screen — reported by the user, same day

- [x] 8.1 Count *working* from the ATTENTION axis on the project row, not from `state`: two live sessions were `busy` in the record and `quiet` in the log at the same instant, so the row rendered NO counter at all [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 8.2 Render a quiet-log/running-loop session as **working** on the tile, instead of falling through to `wait unmeasured` — a measured state printed as an unmeasured one [REQ: four-statuses-map-to-four-distinct-attention-classes]
- [x] 8.3 `escalationTone`: the STRONGEST tone present, one waiter is enough, and a wait with no measured age resolves to amber rather than to silence — the user's rule: *"ha egy várakozó is van akkor kell a szín, a legerősebb szín"* [REQ: the-project-menu-shows-the-worst-wait-it-contains]
- [x] 8.4 Tests for all three, including a project with two working agents and one waiter [REQ: the-project-menu-shows-the-worst-wait-it-contains]

## Evidence — what was actually run (2026-08-28)

- **the measurement layer:** `.venv/bin/python -m pytest tests/unit/test_fleet_input_attention.py
  tests/unit/test_fleet_state.py -q` → **59 passed**.
- **task 2.6, the mutation round** (a git worktree at HEAD instead of a stash — a stash inside a
  killable command can take the session's work with it): four mutants, all caught —
  `shell → input` (2 failures), the empty/absent-status guard removed (2), the wait taken from the
  log's mtime (4), and the thresholds moved to 20 s / 200 s (2). ⚠ The threshold mutant was
  caught by ONE test on the first round: 9 / 45 / 240 s stay in the same bands at 20 / 200, so the
  band test asserted the mechanism and was silent about the result. The boundary tests were
  rewritten in literal seconds and the mutant then failed 2.
- **7.1, the regression set diff:** baseline in a detached worktree at HEAD with
  `PYTHONPATH` pointed at its own three roots and import origin asserted
  (`set_orch` and `set_project_web` both resolved from the worktree; it lacks
  `ATTENTION_INPUT`, so it really is HEAD). Baseline **112** failure entries, this tree **111**;
  `diff` shows the working tree has **one fewer** (`test_paths.py::test_resolve_with_explicit_path`,
  which fails only from a worktree path) and **nothing new**. The skill's leak assertion prints
  371 names here, all of them the venv's own `_pytest*` modules — the venv lives INSIDE the
  repo, so the substring test matches it; no first-party module leaked.
- **7.2:** `npx tsc -b` clean; `npx vitest run` → **78 files, 1206 passed**.
- **7.4, the visual check — DONE, and here is what was seen.** The Chrome extension was not
  connected, so the screen was rendered headless and LOOKED AT rather than asserted:
  `set-core-figma`'s tile reads **`waiting for input 22m · acts now`** in red; `set-core-2023`
  reads `quiet · wait unmeasured` (its record carries no status); the `set-core` and `wpc-pont`
  rows carry the red tint with a red left bar and `1 22m` / `1 3h`; every other row is untinted.
  The live fleet held no wait between 15 s and 3 min, so the amber band was rendered a second
  time with one duration rewritten in flight (47 s) — the row and its bar came out amber, and it
  is clearly separable from red at a glance.
- **8.x, after the user's report:** the same screen re-rendered and looked at again — the
  `set-core` row now carries the amber tint with `1 37s` AND a green `1` for the working
  agent beside it, and the tile reads `working · no open call` instead of `wait unmeasured`.
  Web suite **1219 passed**.
- **7.5, the cross-check:** the screen's classes against `~/.claude/sessions/*.json` at the same
  moment — **9 of 9 agree**, and the two input waits differ from the records' own stamps by
  **3 s**, which is the poll's age and not a disagreement.

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a session's record says `idle` and `statusUpdatedAt` is two hours old THEN the agent is reported as waiting for input for two hours, not rejected as stale [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop, scenario: an-idle-stamp-hours-old-is-the-waits-duration]
- [x] AC-2: WHEN the log's mtime is newer than `statusUpdatedAt` with no newer entry THEN the wait duration comes from `statusUpdatedAt` [REQ: the-runtime-records-status-is-read-as-a-measurement-of-the-session-loop, scenario: the-session-logs-mtime-is-not-used-for-the-wait-duration]
- [x] AC-3: WHEN a session's record says `shell` THEN the class is `background` and it is not counted as waiting for input [REQ: four-statuses-map-to-four-distinct-attention-classes, scenario: a-backgrounded-command-is-not-a-person-waiting]
- [x] AC-4: WHEN the record says `waiting` with a `waitingFor` THEN the class is `prompt` and the reason is carried verbatim [REQ: four-statuses-map-to-four-distinct-attention-classes, scenario: a-permission-prompt-names-what-it-is-waiting-for]
- [x] AC-5: WHEN a record carries no `status` key THEN the class is `unmeasured` and no duration is reported [REQ: a-missing-status-is-unmeasured-never-idle, scenario: a-headless-run-is-not-reported-as-waiting]
- [x] AC-6: WHEN the log holds an outstanding `AskUserQuestion` and the record says `idle` THEN the state stays `asking` and the class is `prompt` [REQ: a-measured-question-outranks-the-record, scenario: an-outstanding-question-tool-wins-over-an-idle-record]
- [x] AC-7: WHEN the record says `idle` while a non-question call is outstanding THEN `working` wins and the disagreement is named [REQ: a-measured-question-outranks-the-record, scenario: a-contradiction-is-carried]
- [x] AC-8: WHEN an agent has waited 9 seconds THEN the tone is plain and it is still reported as waiting [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface, scenario: below-the-first-threshold-nothing-is-marked]
- [x] AC-9: WHEN an agent has waited 45 seconds THEN the tone is amber [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface, scenario: the-amber-band]
- [x] AC-10: WHEN an agent has waited 4 minutes THEN the tone is red [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface, scenario: the-red-band]
- [x] AC-11: WHEN an agent is `background` for 10 minutes THEN no input-wait tone is resolved [REQ: the-escalation-thresholds-are-declared-once-and-carried-to-the-surface, scenario: a-background-busy-agent-never-escalates]
- [x] AC-12: WHEN a collapsed group holds an agent waiting 5 minutes THEN its header carries red [REQ: the-project-menu-shows-the-worst-wait-it-contains, scenario: a-collapsed-group-carries-its-worst-wait]
- [x] AC-13: WHEN a project holds a 4-minute waiter and a 5-second waiter THEN the row carries red [REQ: the-project-menu-shows-the-worst-wait-it-contains, scenario: the-project-row-takes-the-maximum-not-the-freshest]
- [x] AC-19: WHEN a project holds two working agents and one waiting 5 minutes THEN the row carries red, and the working pair is counted from the attention axis [REQ: the-project-menu-shows-the-worst-wait-it-contains, scenario: one-waiting-agent-is-enough-whatever-the-others-are-doing]
- [x] AC-20: WHEN an agent's class is `input` with no timestamp THEN the tone is amber, never absent [REQ: the-project-menu-shows-the-worst-wait-it-contains, scenario: a-wait-with-no-measured-age-is-amber-never-silent]
- [x] AC-18: WHEN a project's longest wait is past a threshold THEN the row's own background and edge carry that tone, and a row below the first threshold stays untinted [REQ: the-project-menu-shows-the-worst-wait-it-contains, scenario: the-row-itself-carries-the-colour-not-only-its-marker]
- [x] AC-14: WHEN a state could not be measured THEN its marker differs from an input-wait marker by shape, not only hue [REQ: amber-means-waiting-for-you-and-nothing-else, scenario: an-unmeasured-agent-is-not-amber]
- [x] AC-15: WHEN the class is `working` or `background` THEN the state line says a message would be queued [REQ: the-surface-says-whether-typing-there-would-be-acted-on, scenario: a-working-session-says-a-message-would-queue]
- [x] AC-16: WHEN the class is `input` THEN the state line says the session would act on a message now [REQ: the-surface-says-whether-typing-there-would-be-acted-on, scenario: an-idle-session-says-a-message-is-acted-on-now]
- [x] AC-17: WHEN the class is computed for an agent in a consumer project THEN any log line names counts or shapes only [REQ: nothing-measured-here-is-persisted, scenario: a-log-line-carries-no-subject-content]
