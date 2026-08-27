## 1. Capture the baseline, before anything moves

- [x] 1.1 Record the current pre-change readings from this machine into a scratch note that the later tasks compare against: `discover_agents()`, `is_agent_process(<live pid>)`, `parent_seat(<live pid>)`, `purpose._pid_state(<live pid>)`, `instruct.live_waiters()`. A "it got better" claim needs a before, and the before disappears the moment the first file is edited [REQ: agent-discovery-reports-live-agents-on-macos]
- [x] 1.2 Run the three existing `/proc`-fixture suites and record the pass count, so "unedited and still passing" is a comparison rather than an impression: `tests/unit/test_fleet_discovery.py`, and every other suite that passes a `proc_root` [REQ: the-linux-behaviour-is-preserved-and-is-proven-by-untouched-tests]
- [x] 1.3 Capture `live_waiters()`'s exact return value on both a real waiter (start one if none is running) and a fake `/proc` tree, as the equality target for the consolidation in group 5 [REQ: the-existing-macos-waiter-reader-is-consolidated-without-changing-its-answers]

## 2. The package and its contract

- [x] 2.1 Create `lib/set_orch/fleet/procsource/_types.py` with the shared vocabulary: the six operation names, the sentinel meanings (`None` = could not answer), and any exception type. Kept out of `__init__` so a backend can import it without importing the dispatcher that imports the backend [REQ: one-source-answers-six-named-questions-about-a-process]
- [x] 2.2 Create `lib/set_orch/fleet/procsource/_linux.py` by moving the existing `/proc` readers unedited — `_read`, argv, cwd, ppid (the parse that starts after the LAST `)`), comm, environ, and the `/proc` directory walk. Moved, not rewritten: the Linux path is the one this change must not disturb [REQ: one-source-answers-six-named-questions-about-a-process]
- [x] 2.3 Write `lib/set_orch/fleet/procsource/__init__.py` with an access-time `__getattr__` dispatcher and a reported `BACKEND`, mirroring `fleet/scopes/__init__.py`. Do not bind names at import [REQ: the-backend-is-selected-at-access-time-never-bound-at-import]
- [x] 2.4 Implement the three selection paths: platform default, explicit `/proc` root (Linux backend rooted there, on any platform), explicit backend name (either backend, on any platform) [REQ: a-backend-can-be-selected-explicitly-in-three-ways]
- [x] 2.5 Make an out-of-contract attribute raise an `AttributeError` naming the active backend and the requested operation, rather than returning something that reads as an answer [REQ: one-source-answers-six-named-questions-about-a-process]
- [x] 2.6 Test that replacing a function on the backend module is visible through the dispatcher — the twelve-test failure mode from the previous split, held in a test rather than in a comment [REQ: the-backend-is-selected-at-access-time-never-bound-at-import]
- [x] 2.7 Test the `None` / empty distinction for every operation, on the Linux backend, using an unreadable root versus an empty one [REQ: could-not-answer-is-a-distinct-value-from-nothing-there]

## 3. The Darwin backend

- [x] 3.1 Implement live-pids-by-identity from `ps -A -o pid=,comm=` with basename equality matching, and a test proving a command line merely containing the name does not match [REQ: each-fact-is-read-from-a-measured-macos-source]
- [x] 3.2 Implement batched cwd from `lsof -a -d cwd -Fpn -p <csv>`, parsing the `p`/`n` field pairs [REQ: whole-table-questions-are-answered-by-one-command-not-one-per-pid]
- [x] 3.3 Parse `lsof` stdout regardless of exit code; conclude failure only on `OSError`, timeout, or a binary that cannot be run. Test with a batch of one live and one dead pid — the live pid's cwd must survive an `rc=1` [REQ: lsof-output-is-parsed-regardless-of-its-exit-code]
- [x] 3.4 Implement argv from `ps -ww -o pid=,args=`, splitting on whitespace, with the loss of exact separation documented in the docstring [REQ: the-loss-of-argument-separation-is-stated-not-hidden]
- [x] 3.5 Implement ppid from `ps -o pid=,ppid=` [REQ: each-fact-is-read-from-a-measured-macos-source]
- [x] 3.6 Implement one-env-var from `ps -E -p <pid> -o command=`, returning `None` for unknown and never an empty string [REQ: an-environment-variable-is-read-only-where-macos-permits-it]
- [x] 3.7 Implement comm-of-one-pid from `ps -p <pid> -o comm=`, basename compared [REQ: each-fact-is-read-from-a-measured-macos-source]
- [x] 3.8 Scope the process-table snapshot to one reading pass; no cross-call cache, no TTL. Test that a second pass re-reads [REQ: whole-table-questions-are-answered-by-one-command-not-one-per-pid]
- [x] 3.9 Give every external invocation a timeout and a WARNING on failure that names the command and status and carries no cwd, command line or environment value [REQ: every-external-command-is-bounded-and-logged-on-failure]
- [x] 3.10 Drive the whole backend from a Linux-selectable test using recorded `ps`/`lsof` output, so the Darwin path is verified where it is not the default too [REQ: a-backend-can-be-selected-explicitly-in-three-ways]

## 4. discovery.py reads through the source

- [x] 4.1 Replace `_live_agent_pids`, `_proc_cwd`, `_proc_argv`, `_ppid`, `is_agent_process` and `_classify_kind` with source calls, keeping every signature and every `proc_root` default exactly as they are [REQ: agent-discovery-reports-live-agents-on-macos]
- [x] 4.2 Delete the `sys.platform == "darwin"` branch inside `live_session_ids()` and the now-duplicated `_pids_by_comm_from_ps`, and let the dispatcher provide the behaviour. Assert `live_session_ids()` returns the same value before and after — it works today and must keep working [REQ: callers-above-the-package-do-not-branch-on-platform]
- [x] 4.3 Make `parent_seat` climb via the source, and write its test so that it asserts the ancestry walk RAN — not only that the result is `None`, which a blind implementation also returns [REQ: ancestry-is-answered-from-measurement-rather-than-from-absence]
- [x] 4.4 Verify on this machine with real agents: `discover_agents()` names them with correct cwd, project and kind; `is_agent_process(<live pid>)` is `True` [REQ: agent-discovery-reports-live-agents-on-macos]
- [x] 4.5 Confirm one-shot classification still excludes `-p` / `--print` processes on macOS, given argv now arrives space-split [REQ: the-loss-of-argument-separation-is-stated-not-hidden]

## 5. instruct.py: consolidate, then repair

- [x] 5.1 Move `_ps_session`, `_ps_cwd` and the `ps` table read out of `instruct.py` into the Darwin backend, keeping the bodies as they are. This is a move; a behaviour change here is a defect [REQ: the-existing-macos-waiter-reader-is-consolidated-without-changing-its-answers]
- [x] 5.2 Re-run task 1.3's captured value and require equality on both platforms' paths [REQ: the-existing-macos-waiter-reader-is-consolidated-without-changing-its-answers]
- [x] 5.3 Route `remove_waiter`'s argv and session reads through the source so a real waiter resolves on macOS [REQ: waiter-removal-resolves-a-waiter-on-macos]
- [x] 5.4 Prove every existing refusal survives: not-a-waiter, undeterminable liveness, unreadable own session, alive session. Four tests, because this function is a refusal with a narrow exception and the exception is the dangerous half [REQ: waiter-removal-resolves-a-waiter-on-macos]

## 6. purpose.py stops reporting live runs as stale

- [x] 6.1 Replace `_pid_state`'s `/proc` directory test and `comm` read with source calls [REQ: recorded-runs-report-their-true-status-on-macos]
- [x] 6.2 Preserve the precedence exactly: commit or set-aside means `finished` without consulting the pid [REQ: recorded-runs-report-their-true-status-on-macos]
- [x] 6.3 **DECIDED: folded.** `purpose.py` now imports `AGENT_COMM` from `discovery` instead of spelling `"claude"` a second time. Reason: it was one fact with two spellings, which stays consistent exactly until somebody changes one of them — and this change already makes both backends resolve identity by the same rule, so leaving two literals would preserve a divergence the rest of the work removes. The import direction is the safe one: `discovery` decides identity and does not read runs, so there is no cycle (checked). [REQ: recorded-runs-report-their-true-status-on-macos]
- [x] 6.4 Verify on this machine: a run record naming a live agent pid reads `running`, not `stale` [REQ: recorded-runs-report-their-true-status-on-macos]

- [x] 6.5 **Found by task 7.1's grep, not by the opening enumeration:** route `awaiting._pid_alive` through the source. It was `os.path.isdir(f"/proc/{pid}")` — False for every pid on a Mac, so every recorded orchestrator and ralph pid read as *gone*, and "the process is gone" is exactly what that function calls a finding. Verified in a clean HEAD worktree: `test_a_running_change_with_a_LIVE_pid_is_unverifiable_never_fine` FAILED at HEAD on this platform and passes now [REQ: callers-above-the-package-do-not-branch-on-platform]

## 7. Prove it, including the parts a green suite cannot see

- [x] 7.1 Grep the fleet modules for a surviving `sys.platform` guard on a process read and for any `/proc` path built outside the package. **Result: both clean, and the grep earned its place** — it found `awaiting.py:121`, the fourth `/proc` reader the opening enumeration missed (see 6.5). The `sys.platform` tests that remain (`owner_client.py:56`, `ownerd.py:157,172`) are socket-path and struct-size decisions from the previous change, not process reads. The `"/proc"` strings that remain are the `proc_root` DEFAULT arguments, which are the dispatch sentinel by design [REQ: callers-above-the-package-do-not-branch-on-platform]
- [x] 7.2 **Eight `/proc`-fixture suites are byte-identical** — `git status --porcelain tests/` lists only `test_fleet_waiters_platform.py` as modified, and three new files. `test_fleet_discovery.py`, `test_fleet_purpose.py`, `test_fleet_instruct.py`, `test_fleet_awaiting.py`, `test_fleet_roster.py`, `test_orphan_cleanup.py`, `test_fleet_persistence_boundary.py` and `test_fleet_owner.py` are untouched and pass. **The one edited file is justified rather than silent:** it was written by the `macos-agent-owner` change to drive `discovery._pids_by_comm_from_ps` and `instruct._ps_cwd`/`_ps_session`, which this change relocates into the source. Every assertion in it is the one that was there before; only the patch target moved, and its docstring now says so [REQ: the-linux-behaviour-is-preserved-and-is-proven-by-untouched-tests]
- [x] 7.3 **Mutation-tested rather than stashed** — the new tests import a package that does not exist at HEAD, so stashing proves only that. Five mutations, restore verified by md5 both times:
  - `lsof` bails on a non-zero exit → CAUGHT
  - `ps -o pid=,ppid=,comm=,args=` in one command → CAUGHT
  - binaries called by bare name → CAUGHT
  - dispatcher binds at import → CAUGHT
  - dispatcher caches the lookup lazily → **SURVIVED at first.** The test was the only caller, so the cache was filled with the replacement itself, and a frozen implementation passed a test whose docstring claims access-time resolution. Fixed by calling once BEFORE the replacement; the mutation is caught now. The wrong pattern is recorded here rather than only the right one [REQ: agent-discovery-reports-live-agents-on-macos]
- [x] 7.4 **Set diff against a baseline actually run.** Isolated HEAD worktree, three `PYTHONPATH` roots and the session-end leak assertion from the `regression-baseline` skill: **0 leaks**, so the baseline ran HEAD's code and not this tree's.

  | | failed | passed | errors |
  |---|---|---|---|
  | HEAD | 87 | 4176 | 8 |
  | this tree | 85 | 4231 | 8 |

  **New failures: none.** Recovered: `test_fleet_awaiting.py::test_a_running_change_with_a_LIVE_pid_is_unverifiable_never_fine` — genuine, and the evidence for task 6.5.

  **The second "recovery" is NOT one, and claiming it would have been wrong.** `test_paths.py::TestResolveProjectName::test_resolve_with_explicit_path` compares `resolve_project_name(repo_root)` against `repo_root.name`, so in a worktree it asserts `'set-core' == 'head-check'` — it fails on the BASELINE'S DIRECTORY NAME, not on HEAD's code. A worktree-name-sensitive test is a hazard of this whole baseline method: it appears in the recovered column for free, in the reassuring direction. Verified by running that one test in both trees in isolation.

  One flag matters and is not in the skill's recipe: without `--continue-on-collection-errors` the run stops at 8 collection errors and reports nothing comparable. [REQ: the-linux-behaviour-is-preserved-and-is-proven-by-untouched-tests]
- [x] 7.5 **Looked at, and it found a defect nothing else could.** Fleet screen at `http://127.0.0.1:7400/fleet`, 1600x1000, screenshot taken and read.

  What was seen: header **"2 agents in 2 of 22 projects"** (it was "0 agents in 0 of 22"); the project strip lists `set-copilot 1` and `set-core 1`, both `reg-live`, `set-core` with an `8s` age; the selected project's header resolves its working directory; the agent tile reads `set-copilot-2024 - unknown - master` with its pid. Zero JS errors.

  **The defect the screen found, and no test could:** the first look showed `agents: 0` from a service running the new code. `lsof` was being called by bare name, and a launchd service does not inherit a login shell's `PATH` — the dashboard's has no `/usr/sbin`. So every working directory came back unknown, `discover_agents()` (which skips a pid whose cwd it cannot read) returned an EMPTY FLEET, and the screen was indistinguishable from the `/proc` blindness this change exists to remove. It passed the whole unit suite, because tests replace `subprocess.run`, and it passed every command-line check, because an interactive shell has that directory on its `PATH`. Fixed by resolving both binaries to absolute paths, with a test.

  Two things seen on the same screen that are NOT this change's and are registered instead: the right-hand panel is roughly 800 px of empty black below a 130 px tile, and the agent reports *"the messaging bus could not be asked who exists"* (B-84). [REQ: the-screen-is-looked-at-before-this-is-called-done]

## Acceptance Criteria (from spec scenarios)

### fleet-process-source

- [x] AC-1: WHEN each backend is inspected for its operations THEN both provide all six [REQ: one-source-answers-six-named-questions-about-a-process, scenario: every-backend-answers-the-same-six]
- [x] AC-2: WHEN an operation outside the contract is requested THEN an AttributeError names the backend and the operation [REQ: one-source-answers-six-named-questions-about-a-process, scenario: a-fact-outside-the-contract-is-refused-by-name]
- [x] AC-3: WHEN a shell's command line contains the agent name in a path THEN its pid is not among the live agent pids [REQ: one-source-answers-six-named-questions-about-a-process, scenario: identity-is-not-a-substring]
- [x] AC-4: WHEN the process table cannot be read at all THEN the live-pids query returns None, not an empty list [REQ: could-not-answer-is-a-distinct-value-from-nothing-there, scenario: an-unreadable-process-table-is-not-an-empty-one]
- [x] AC-5: WHEN the table is readable with no matches THEN an empty list is returned, not None [REQ: could-not-answer-is-a-distinct-value-from-nothing-there, scenario: a-readable-table-with-no-matches-is-empty-not-unknown]
- [x] AC-6: WHEN a live pid's cwd cannot be determined THEN cwd is None and the pid is still reported live [REQ: could-not-answer-is-a-distinct-value-from-nothing-there, scenario: a-pid-that-exists-but-whose-cwd-cannot-be-read]
- [x] AC-7: WHEN a test replaces an operation on the backend module THEN the replacement runs through the dispatcher [REQ: the-backend-is-selected-at-access-time-never-bound-at-import, scenario: replacing-a-backend-function-is-visible-through-the-dispatcher]
- [x] AC-8: WHEN the package is asked which backend is active THEN it names one of the two [REQ: the-backend-is-selected-at-access-time-never-bound-at-import, scenario: the-backend-in-use-is-reportable]
- [x] AC-9: WHEN a /proc root is passed while running on macOS THEN the Linux backend rooted there is used [REQ: a-backend-can-be-selected-explicitly-in-three-ways, scenario: an-explicit-root-wins-over-the-platform]
- [x] AC-10: WHEN the macOS backend is requested by name on Linux THEN the macOS backend is returned [REQ: a-backend-can-be-selected-explicitly-in-three-ways, scenario: a-backend-can-be-named-on-the-other-platform]
- [x] AC-11: WHEN no root and no name are given THEN the running platform's backend is returned [REQ: a-backend-can-be-selected-explicitly-in-three-ways, scenario: no-root-means-dispatch-by-platform]
- [x] AC-12: WHEN the reader modules are searched for a sys.platform guard on a process read THEN none is found [REQ: callers-above-the-package-do-not-branch-on-platform, scenario: no-platform-branch-survives-in-the-readers]
- [x] AC-13: WHEN the reader modules are searched for a literal /proc path THEN none is found outside the package [REQ: callers-above-the-package-do-not-branch-on-platform, scenario: no-proc-path-is-built-outside-the-package]

### macos-process-reader

- [x] AC-14: WHEN live pids are requested with a live agent running THEN its pid is among them [REQ: each-fact-is-read-from-a-measured-macos-source, scenario: a-live-agent-is-found-by-identity]
- [x] AC-15: WHEN a table row's comm is an absolute path ending in the name THEN that pid is matched [REQ: each-fact-is-read-from-a-measured-macos-source, scenario: a-full-path-is-matched-by-its-basename]
- [x] AC-16: WHEN the cwd of a live agent pid is requested THEN its absolute working directory is returned [REQ: each-fact-is-read-from-a-measured-macos-source, scenario: the-working-directory-of-a-live-pid-is-resolved]
- [x] AC-17: WHEN the parent pid of a live pid is requested THEN an integer pid is returned [REQ: each-fact-is-read-from-a-measured-macos-source, scenario: the-parent-pid-of-a-live-pid-is-resolved]
- [x] AC-18: WHEN the fleet enumerates every live agent in one pass THEN the process table is read once [REQ: whole-table-questions-are-answered-by-one-command-not-one-per-pid, scenario: one-process-table-read-per-pass]
- [x] AC-19: WHEN several pids' cwds are requested together THEN a single lsof invocation carries all of them [REQ: whole-table-questions-are-answered-by-one-command-not-one-per-pid, scenario: working-directories-are-resolved-in-one-batch]
- [x] AC-20: WHEN two reading passes are performed THEN the second re-reads rather than answering from the first [REQ: whole-table-questions-are-answered-by-one-command-not-one-per-pid, scenario: a-new-pass-re-reads-rather-than-reusing]
- [x] AC-21: WHEN a batch holds one live and one nonexistent pid THEN the live pid's cwd is returned and the missing one is unknown [REQ: lsof-output-is-parsed-regardless-of-its-exit-code, scenario: a-dead-pid-in-the-batch-does-not-discard-the-live-one]
- [x] AC-22: WHEN lsof cannot be executed at all THEN every cwd is unknown and the pids are still listed [REQ: lsof-output-is-parsed-regardless-of-its-exit-code, scenario: a-missing-binary-is-a-failure-an-exit-code-is-not]
- [x] AC-23: WHEN a variable of an owned process is requested THEN its value is returned [REQ: an-environment-variable-is-read-only-where-macos-permits-it, scenario: a-variable-of-an-owned-process-is-read]
- [x] AC-24: WHEN a pid's environment cannot be read THEN None is returned, not an empty string [REQ: an-environment-variable-is-read-only-where-macos-permits-it, scenario: an-unreadable-environment-is-unknown-not-empty]
- [x] AC-25: WHEN a process started with a one-shot flag has its argv read on macOS THEN the flag is present [REQ: the-loss-of-argument-separation-is-stated-not-hidden, scenario: a-flag-is-still-detected]
- [x] AC-26: WHEN a process whose arguments contain no spaces has its argv read THEN the result equals its actual argv [REQ: the-loss-of-argument-separation-is-stated-not-hidden, scenario: positional-structure-survives]
- [x] AC-27: WHEN an external command exceeds its timeout THEN the could-not-answer value is returned and a warning is logged [REQ: every-external-command-is-bounded-and-logged-on-failure, scenario: a-hung-command-does-not-hang-the-fleet]
- [x] AC-28: WHEN a command failure is logged THEN the line carries no cwd and no inspected command line [REQ: every-external-command-is-bounded-and-logged-on-failure, scenario: a-failure-log-carries-no-path]

### fleet-platform-neutral-readers

- [x] AC-29: WHEN agents are discovered on macOS with a live session THEN it appears with the right cwd and is reported interactive [REQ: agent-discovery-reports-live-agents-on-macos, scenario: live-agents-are-listed-on-macos]
- [x] AC-30: WHEN is_agent_process is asked about a live agent pid on macOS THEN it returns true [REQ: agent-discovery-reports-live-agents-on-macos, scenario: a-live-pid-verifies-as-an-agent-on-macos]
- [x] AC-31: WHEN agents are discovered without requesting one-shots THEN a one-shot process is not listed [REQ: agent-discovery-reports-live-agents-on-macos, scenario: a-one-shot-subprocess-is-still-excluded-by-default]
- [x] AC-32: WHEN discover_agent is asked about a live non-agent pid THEN it returns nothing [REQ: agent-discovery-reports-live-agents-on-macos, scenario: a-pid-that-is-not-an-agent-is-still-rejected]
- [x] AC-33: WHEN a process has a live agent among its ancestors THEN that agent's seat is returned [REQ: ancestry-is-answered-from-measurement-rather-than-from-absence, scenario: the-walk-reaches-an-agent-ancestor-when-one-exists]
- [x] AC-34: WHEN a process has no agent ancestor THEN nothing is returned AND the parent-pid operation was invoked [REQ: ancestry-is-answered-from-measurement-rather-than-from-absence, scenario: no-agent-ancestor-is-reported-as-none-having-looked]
- [x] AC-35: WHEN a recorded run's pid is a live agent on macOS THEN it is reported running [REQ: recorded-runs-report-their-true-status-on-macos, scenario: a-live-run-is-running-not-stale]
- [x] AC-36: WHEN a recorded run carries a commit THEN it is finished and its pid is not consulted [REQ: recorded-runs-report-their-true-status-on-macos, scenario: a-finished-run-stays-finished]
- [x] AC-37: WHEN a recorded run's pid no longer exists THEN it is stale [REQ: recorded-runs-report-their-true-status-on-macos, scenario: an-exited-run-is-stale]
- [x] AC-38: WHEN a live macOS waiter whose session is not alive is removed THEN it is removed [REQ: waiter-removal-resolves-a-waiter-on-macos, scenario: a-real-waiter-is-identified-on-macos]
- [x] AC-39: WHEN removal is requested for a live non-waiter pid THEN it is refused naming that it is not a waiter [REQ: waiter-removal-resolves-a-waiter-on-macos, scenario: a-non-waiter-pid-is-still-refused-for-the-right-reason]
- [x] AC-40: WHEN a waiter's session is among the live sessions THEN removal is refused naming that its session is alive [REQ: waiter-removal-resolves-a-waiter-on-macos, scenario: an-alive-session-still-blocks-removal]
- [x] AC-41: WHEN a waiter's session cannot be determined THEN removal is refused [REQ: waiter-removal-resolves-a-waiter-on-macos, scenario: an-unreadable-session-still-blocks-removal]
- [x] AC-42: WHEN live waiters are read after the consolidation THEN the same pid, session, cwd and rooms are reported as before [REQ: the-existing-macos-waiter-reader-is-consolidated-without-changing-its-answers, scenario: waiters-are-unchanged-by-the-consolidation]
- [x] AC-43: WHEN live waiters are read against a fake /proc tree THEN the same waiter is reported as before [REQ: the-existing-macos-waiter-reader-is-consolidated-without-changing-its-answers, scenario: the-linux-waiter-reader-is-unchanged]
- [x] AC-44: WHEN the existing fleet suites are run after the change THEN they pass AND their files are unmodified [REQ: the-linux-behaviour-is-preserved-and-is-proven-by-untouched-tests, scenario: the-proc-fixture-suites-pass-unedited]
- [x] AC-45: WHEN a reader is driven with a fake /proc tree on macOS THEN it reads that tree [REQ: the-linux-behaviour-is-preserved-and-is-proven-by-untouched-tests, scenario: an-explicit-root-still-selects-the-linux-reader-on-macos]
- [x] AC-46: WHEN the fleet screen is opened on macOS with live agents THEN the agents are visible with their projects AND what was seen is recorded [REQ: the-screen-is-looked-at-before-this-is-called-done, scenario: the-fleet-screen-is-verified-visually]
- [ ] AC-47: **NOT EXERCISED, and left open rather than ticked.** The browser WAS reachable, so this scenario's branch never arose. Marking it done would claim a behaviour nobody observed, and a marker outranks the body — a later reader counts the box, not this sentence. [REQ: the-screen-is-looked-at-before-this-is-called-done, scenario: an-unreachable-browser-leaves-the-check-open]


## Traceability — which test carries which acceptance criterion

| AC | evidence |
|---|---|
| 1–11 | `tests/unit/test_fleet_procsource.py` — contract, dispatch, the `None`/empty split |
| 12–13 | `test_no_reader_branches_on_the_platform...`, `test_no_reader_builds_a_proc_path...` — the property held as a test rather than as a rule. Both mutation-checked; the `/proc` one needed two repairs, recorded in its own docstring |
| 14–28 | `test_fleet_procsource.py`, the `test_darwin_*` block, driven from recorded `ps`/`lsof` output so it runs on Linux too |
| 29–32 | `tests/unit/test_fleet_discovery_platform.py` |
| 33–34 | same file — AC-34 asserts the ancestry walk RAN, because its correct answer and its blind answer are the same value |
| 35–37 | `tests/unit/test_fleet_purpose_platform.py` |
| 38–41 | `tests/unit/test_fleet_waiters_platform.py`, the removal block |
| 42 | task 5.2 — measured against a real waiter on this machine: session, cwd and rooms identical before and after, only the pid differs |
| 43–45 | the eight unedited `/proc`-fixture suites (task 7.2) and `test_an_explicit_proc_root_keeps_the_linux_reader_on_macos` |
| 46 | task 7.5 — the screen was opened and looked at, and it found the `PATH` defect |
| 47 | not exercised; see above |
