## 1. Settle the assumption the design rests on

- [x] 1.1 Measure whether a `setsid`-ed grandchild of the dashboard's launchd job survives `launchctl kickstart -k com.set-core.web`: start a sleeper with `start_new_session=True` from inside the job, record its pid and `getsid`, kick the job, assert the sleeper is still alive. Write the result — command, output, verdict — into `design.md` under Open Questions, replacing the question. [REQ: an-agent-started-from-the-fleet-survives-a-dashboard-restart]
- [x] 1.2 If 1.1 shows the child dies, stop and record which fallback the measurement forces (double-fork reparented to launchd, or `launchctl submit`) before any code is written; D2 is wrong and the rest of the list changes. [REQ: each-backend-verifies-the-survival-property-at-start-and-refuses-when-it-is-absent]
- [x] 1.3 Measure whether `os.getsid()` and `os.getpgid()` on a same-user process are readable from inside the launchd job without extra privileges, since the verification in 4.x depends on it. [REQ: each-backend-verifies-the-survival-property-at-start-and-refuses-when-it-is-absent]

## 2. The socket path, and the message that names it

- [x] 2.1 Add a macOS branch to `ownerd.default_socket_path()` resolving under the framework's per-user runtime directory, creating the directory before bind. Leave the Linux branch returning exactly what it returns today. [REQ: the-owners-socket-path-is-resolved-per-platform]
- [x] 2.2 Add the `sun_path` length check to the resolver — refuse with the path, its byte length and the platform limit. [REQ: an-unusable-socket-path-is-refused-with-the-reason]
- [x] 2.3 Confirm `owner_client` and `ownerd` obtain the path from the same resolver, and make them if they do not. [REQ: the-owners-socket-path-is-resolved-per-platform]
- [x] 2.4 Replace `owner_client.START_COMMAND` with a per-platform resolver; keep the underlying reason in the reported text and add the command to it. [REQ: the-operator-is-shown-a-command-their-machine-can-run]
- [x] 2.5 Unit tests for 2.1–2.4 that run on either platform by parameterising the platform rather than by skipping. [REQ: the-owners-socket-path-is-resolved-per-platform]

## 3. Make the owner's tests runnable on macOS

Discovered while measuring the baseline for group 2, not planned: `test_fleet_ownerd.py`
fails 14 of its 36 tests on macOS with `OSError: AF_UNIX path too long`, and failed them
identically at HEAD. The tests build their sockets under pytest's `tmp_path`, which is
~150 bytes here — past the same 104-byte `sun_path` limit this change added a check for.
The owner's suite has therefore never run on macOS. Without this group, the Darwin
backend in group 5 lands with no coverage from the suite that exists to cover it.

- [x] 3.1 Add a `sock_dir` fixture to `tests/unit/conftest.py` returning a directory short enough to hold a unix socket on macOS, and say in its docstring why `tmp_path` cannot be used. [REQ: an-unusable-socket-path-is-refused-with-the-reason]
- [x] 3.2 Move every socket path in `test_fleet_ownerd.py` onto `sock_dir`, leaving non-socket uses of `tmp_path` alone. [REQ: an-unusable-socket-path-is-refused-with-the-reason]
- [x] 3.3 Point `test_fleet_owner_platform.py` at the shared fixture instead of its local copy. [REQ: an-unusable-socket-path-is-refused-with-the-reason]
- [x] 3.4 Confirm the 14 baseline failures are gone and that no test that passed before now fails — set-diff against the baseline worktree, not against zero. [REQ: an-unusable-socket-path-is-refused-with-the-reason]

## 4. Split `scopes` into a package, without touching the Linux logic

- [x] 4.1 Convert `lib/set_orch/fleet/scopes.py` into a package: move the file to `scopes/_systemd.py` **unedited**, so the diff is a rename and any later change to it is readable. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 4.2 Write `scopes/__init__.py` holding `Scope`, `ScopeError`, `SCOPE_PREFIX`, `sanitize`, `unit_name`, and dispatch by `sys.platform`. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 4.3 Promote the two private names `owner.py` reaches for — `_await_unit`, `_as_scope` — to the backend contract under public names, or remove `owner.py`'s need for them. Grep for every `scopes._` use and leave none. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 4.4 Run the existing fleet tests on Linux (or under the Linux backend forced) and confirm the split changed nothing. [REQ: the-backend-api-is-one-shape-across-platforms]

## 5. The Darwin backend

Rewritten during implementation — see design decision D1a. The original list said to
implement `scopes.start()`, which the fleet never calls: `owner.py` forks its own pty
and execs `systemd-run` inside the child, so the platform-specific step is above the
package. These tasks widen the backend contract instead.

- [x] 5.1 Add `child_exec(unit, argv, cwd, env)` to the systemd backend, moving `owner.py`'s `systemd-run` exec into it unchanged, and call it from `owner.py`'s forked child. No behaviour change on Linux. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 5.2 Add `adopt(unit, child_pid, cwd)` and `forget(unit)` to the systemd backend — `adopt` is today's `await_unit` plus `assert_sibling`, `forget` is a no-op — and route `owner.py` through them. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 5.3 Implement `scopes/_darwin.py` `child_exec`: exec the agent's argv directly. The survival property comes from `pty.fork()`, which already makes the child a session leader — assert that in a comment naming the measurement, so a later reader does not add a wrapper back. [REQ: an-agent-started-from-the-fleet-survives-a-dashboard-restart]
- [x] 5.4 Implement Darwin `assert_survivable`: read `os.getsid(pid)` and `os.getpgid(pid)` back from the kernel and REFUSE — not warn — when the process does not lead its own session. [REQ: each-backend-verifies-the-survival-property-at-start-and-refuses-when-it-is-absent]
- [x] 5.5 Implement the Darwin record under the runtime directory: label, pid, process start time, cwd. Written by `adopt`, removed by `forget` and by `stop`. [REQ: a-backend-without-a-unit-registry-keeps-its-own-record]
- [x] 5.6 Implement Darwin `get()`, `list_scopes()` and `is_gone()` over the record, reconciling every read against the running system and comparing process start time so a recycled pid is not reported as the agent. [REQ: a-backend-without-a-unit-registry-keeps-its-own-record]
- [x] 5.7 Implement Darwin `stop()` with the same grace/kill escalation the systemd backend exposes, signalling the agent's process group rather than the single pid. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 5.8 Implement Darwin `scope_of(pid)` and `scope_is_gone(scope)`, the two remaining names the API layer and `owner.py` reach for. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 5.9 Turn the dispatcher's single-backend import back into a `sys.platform` selection. [REQ: the-backend-api-is-one-shape-across-platforms]
- [x] 5.10 Unit-test the parts that do not need Darwin — record reconciliation, stale entries, recycled pids, label prefixing, the survivability refusal — so Linux CI covers them. [REQ: a-backend-without-a-unit-registry-keeps-its-own-record]

## 6. Waiters without `/proc`

- [x] 6.1 Split `instruct.live_waiters()` into a platform-neutral argv matcher and a platform process source; keep the `/proc` walk as the Linux source with its behaviour unchanged. [REQ: waiters-are-read-through-a-platform-appropriate-process-source]
- [x] 6.2 Implement the macOS source: one `ps -A -o pid=,command=`, then `lsof` per matched waiter only, for the working directory. [REQ: waiters-are-read-through-a-platform-appropriate-process-source]
- [x] 6.3 Report an unreadable working directory as unknown and keep the waiter in the list. [REQ: a-fact-the-platform-will-not-give-is-absent-not-invented]
- [x] 6.4 Confirm the `None` return still means could-not-measure on both platforms, and that `api/fleet.py`'s branch is reached only then. [REQ: could-not-measure-is-never-widened-into-there-are-none]
- [x] 6.5 Test that a readable-but-empty machine returns an empty measured list, not the could-not-measure value. [REQ: could-not-measure-is-never-widened-into-there-are-none]

## 7. The installer places the job

- [x] 7.1 Add `templates/launchd/com.set-core.agent-owner.plist` with the same placeholder convention as the existing web plist. [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform]
- [x] 7.2 Extend `install_launchd_service` to place, load and report the owner job — running or failed, never silent — mirroring the systemd branch. Do not touch the systemd branch. [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform]
- [x] 7.3 Verify the owner job is independent of the dashboard job: restart the dashboard and confirm the owner's socket still answers. [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform]
- [x] 7.4 Confirm the dashboard still refuses to start the owner itself on macOS. [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform]

## 8. Prove it on the machine

- [x] 8.1 Run `install.sh` on macOS from a state with no owner job and confirm `+ start an agent` renders as an offer rather than as `no agent can be started from here`. [REQ: the-operator-is-shown-a-command-their-machine-can-run]
- [x] 8.2 Start an agent from the Fleet screen, then restart the dashboard's job, and assert the agent's process is still alive. This is the acceptance test for the whole change and must be run, not reasoned about. [REQ: an-agent-started-from-the-fleet-survives-a-dashboard-restart]
- [x] 8.3 Kill the dashboard's job rather than stopping it, and repeat 7.2. [REQ: an-agent-started-from-the-fleet-survives-a-dashboard-restart]
- [x] 8.4 Confirm the Fleet screen no longer reports `the process table could not be read`. [REQ: waiters-are-read-through-a-platform-appropriate-process-source]
- [x] 8.5 Run the full Python and web test suites and compare failures against the pre-change baseline rather than against zero. [REQ: the-backend-api-is-one-shape-across-platforms]

## Acceptance Criteria (from spec scenarios)

### agent-owner-platform

- [x] AC-1: WHEN the socket path is resolved on macOS with `XDG_RUNTIME_DIR` unset THEN the result is under the framework's per-user runtime directory and does not begin with `/run/user/` [REQ: the-owners-socket-path-is-resolved-per-platform, scenario: macos-resolves-a-path-that-exists]
- [x] AC-2: WHEN the socket path is resolved on Linux with `XDG_RUNTIME_DIR` set THEN the result is that directory joined with `set-agent-owner.sock` [REQ: the-owners-socket-path-is-resolved-per-platform, scenario: linux-keeps-the-unit-files-expansion]
- [x] AC-3: WHEN the service binds its socket and a client resolves the path to connect THEN both obtain the same path from the same resolver [REQ: the-owners-socket-path-is-resolved-per-platform, scenario: the-client-and-the-service-agree]
- [x] AC-4: WHEN the resolved socket path exceeds the platform's `sun_path` limit THEN the owner refuses with an error naming the path, its byte length and the limit, and does not report a missing file or directory [REQ: an-unusable-socket-path-is-refused-with-the-reason, scenario: an-over-long-path-is-named-as-such]
- [x] AC-5: WHEN the installer runs on macOS THEN a launchd job for the owner is written to the user's LaunchAgents directory, loaded, and reported as running or failed [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform, scenario: macos-install-places-and-loads-the-job]
- [x] AC-6: WHEN the owner's unit is placed on either platform THEN it is a distinct unit of the service manager, not spawned by the dashboard process [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform, scenario: the-owner-is-a-separate-job-from-the-dashboard]
- [x] AC-7: WHEN the dashboard's service is restarted THEN the owner's service is still running and its socket still answers [REQ: the-installer-places-the-owners-service-unit-on-every-supported-platform, scenario: restarting-the-dashboard-does-not-stop-the-owner]
- [x] AC-8: WHEN the owner is unreachable on macOS THEN the offered command is the launchd command and the text does not contain `systemctl` [REQ: the-operator-is-shown-a-command-their-machine-can-run, scenario: macos-is-not-told-to-run-systemctl]
- [x] AC-9: WHEN the owner is unreachable on Linux THEN the offered command is `systemctl --user start set-agent-owner.service` [REQ: the-operator-is-shown-a-command-their-machine-can-run, scenario: linux-keeps-its-command]
- [x] AC-10: WHEN the owner is unreachable for any reason THEN the reported text carries the underlying reason as well as the command [REQ: the-operator-is-shown-a-command-their-machine-can-run, scenario: the-reason-is-reported-not-replaced-by-the-remedy]

### agent-isolation-backend

- [x] AC-11: WHEN an agent has been started from the fleet and the dashboard's service is restarted THEN the agent's process is still alive afterwards [REQ: an-agent-started-from-the-fleet-survives-a-dashboard-restart, scenario: the-dashboard-is-restarted-under-a-running-agent]
- [x] AC-12: WHEN the dashboard's service is killed THEN the agent's process is still alive afterwards [REQ: an-agent-started-from-the-fleet-survives-a-dashboard-restart, scenario: the-dashboard-is-killed-rather-than-stopped]
- [x] AC-13: WHEN a backend starts an agent and verification finds it inside the dashboard's lifetime scope THEN the start fails naming what was found and no agent is reported as started [REQ: each-backend-verifies-the-survival-property-at-start-and-refuses-when-it-is-absent, scenario: a-start-that-would-not-survive-is-refused]
- [x] AC-14: WHEN a backend reports a start as successful THEN it has read the process's actual relationship from the running system, not inferred it from spawn flags [REQ: each-backend-verifies-the-survival-property-at-start-and-refuses-when-it-is-absent, scenario: the-check-is-measured-not-assumed]
- [x] AC-15: WHEN the owner is restarted and the backend enumerates agents THEN agents recorded before the restart whose processes are alive are listed [REQ: a-backend-without-a-unit-registry-keeps-its-own-record, scenario: enumeration-survives-an-owner-restart]
- [x] AC-16: WHEN the record names a label whose process no longer exists THEN enumeration and lookup both report it gone [REQ: a-backend-without-a-unit-registry-keeps-its-own-record, scenario: a-stale-entry-is-not-reported-as-alive]
- [x] AC-17: WHEN the record names a pid that now belongs to an unrelated process THEN the backend does not report the label alive on the pid alone [REQ: a-backend-without-a-unit-registry-keeps-its-own-record, scenario: a-recycled-pid-is-not-mistaken-for-the-agent]
- [x] AC-18: WHEN the owner starts, enumerates, looks up or stops an agent THEN it calls the same functions with the same arguments on either platform and receives the same result shapes [REQ: the-backend-api-is-one-shape-across-platforms, scenario: callers-do-not-branch-on-platform]
- [x] AC-19: WHEN a label is turned into a backend identifier THEN the framework's own prefix is applied [REQ: the-backend-api-is-one-shape-across-platforms, scenario: a-label-names-the-same-thing-on-both-platforms]

### waiter-measurement

- [x] AC-20: WHEN waiters are read on macOS THEN the result is a measured list, empty or otherwise, and not the could-not-measure answer [REQ: waiters-are-read-through-a-platform-appropriate-process-source, scenario: macos-returns-a-measurement-rather-than-a-permanent-failure]
- [x] AC-21: WHEN waiters are read on Linux THEN the result is the same as before this change for the same running processes [REQ: waiters-are-read-through-a-platform-appropriate-process-source, scenario: linux-behaviour-is-unchanged]
- [x] AC-22: WHEN the process source cannot be read THEN the reader returns could-not-measure, not an empty list, and the surface reports nothing is known about what is listening [REQ: could-not-measure-is-never-widened-into-there-are-none, scenario: an-unreadable-process-source-is-reported-as-such]
- [x] AC-23: WHEN the process source is readable and holds no waiter THEN the reader returns an empty measured list and the surface does not claim the table was unreadable [REQ: could-not-measure-is-never-widened-into-there-are-none, scenario: a-genuinely-empty-machine-is-reported-as-measured]
- [x] AC-24: WHEN a waiter's working directory cannot be read THEN the waiter appears in the measured list with its directory unknown and is not omitted [REQ: a-fact-the-platform-will-not-give-is-absent-not-invented, scenario: a-waiter-with-an-unreadable-working-directory-is-still-listed]
- [x] AC-25: WHEN a per-waiter fact cannot be read THEN the value is reported unknown rather than defaulted to a plausible one [REQ: a-fact-the-platform-will-not-give-is-absent-not-invented, scenario: an-unknown-field-is-not-filled-with-a-guess]
