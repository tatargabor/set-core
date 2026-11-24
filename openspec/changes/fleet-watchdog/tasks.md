## 1. Tick, store and lock (Layer 1: `lib/set_orch/fleet_watchdog/`)

- [x] 1.1 `store.py`: findings file and tick log under the state dir (`SET_WATCHDOG_DIR` overrides it, mode 600), fingerprint = sha256(probe + subject), upsert with `first_seen`/`last_seen`, resolve-on-absence for probes that ran, mute with expiry [REQ: probes-are-declared-units-with-a-fingerprint]
- [x] 1.2 `probe.py`: the probe contract (name, interval, `collect(ctx) -> list[Finding]`), the `Finding` dataclass (shape-only evidence), and the registry of built-ins [REQ: probes-are-declared-units-with-a-fingerprint]
- [x] 1.3 `tick.py`: exclusive `flock`, the `watchdog.enabled` kill switch, running due probes by interval, turning an exception into a `watchdog-probe-error` finding, one tick-log line without evidence [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer]
- [x] 1.4 `bin/set-watchdog` (`tick`, `status [--json]`, `probes`, `mute <fp> --days N`, `dispatch <fp>`), added to the `install.sh` scripts list [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer]
- [ ] 1.5 `templates/systemd/set-watchdog.{service,timer}` (5 min), installed and enabled by `install.sh` the way `set-fleet-idle-close` is [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer]
- [x] 1.6 Unit tests: lock contention, a probe raising, upsert/resolve/mute, no evidence in the tick log [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer]

## 2. Built-in probes

- [x] 2.1 `wake-storm`: read the live sessions' transcripts from the fleet payload. Count turn starts that are an inbox-watch task-notification or an `isMeta` bus Stop-hook continuation, in windows with no `origin.kind == "human"` record. Report a `warn` when a live transcript shows no recognisable turn-start marker. Fixtures are built from the measured record shapes, with no real text [REQ: built-in-probes-cover-the-set-features-that-fail-quietly]
- [x] 2.2 `auto-clear-miss`: fill from the fleet payload. Threshold from the unit's `ExecStart` `--threshold`, otherwise the watcher package's default (measure how to read it first; if it is unreadable, report a `warn`). A handoff or clear since crossing is read from the tree's `.set/handoff/` and the session id change [REQ: built-in-probes-cover-the-set-features-that-fail-quietly]
- [x] 2.3 `relay-hold`: the relay's waiting records older than the bound [REQ: built-in-probes-cover-the-set-features-that-fail-quietly]
- [x] 2.4 `service-health`: set-web answers, `owner_reachable` in the payload, auto-clear units for armed projects, `systemctl --user --failed` [REQ: built-in-probes-cover-the-set-features-that-fail-quietly]
- [x] 2.5 `doctor-delta`: `set-doctor --json` on a 30-min interval with a timeout. Only the records new since its previous run open findings. Module records keep their `module` + `project` as the subject [REQ: module-doctors-are-probes-through-the-existing-declarations]
- [x] 2.6 Probe tests, including the "payload unreadable → one `warn`, never silence" path for every payload-reading probe [REQ: built-in-probes-cover-the-set-features-that-fail-quietly]
- [x] 2.7 Live measurement: one tick on this machine. Record each probe's finding count, and check every finding by hand against its source (true or false positive) in `openspec/changes/fleet-watchdog/measurements.md` [REQ: built-in-probes-cover-the-set-features-that-fail-quietly]

## 3. GLM triage

- [x] 3.1 `triage.py`: batch the tick's new findings and the open bug-register titles (the owning project's register when it has one), cap the input (`watchdog.triage_max_chars`, default 8000), run `set-glm -p --output-format json`, parse the verdict, owner and brief (≤ 600 chars) [REQ: new-findings-are-triaged-by-glm-within-a-budget-from-shape-only-input]
- [x] 3.2 Daily call counter (`watchdog.triage_daily_calls`, default 60). Over the cap, GLM unreachable, or an unparseable answer → `untriaged`, never `noise` [REQ: new-findings-are-triaged-by-glm-within-a-budget-from-shape-only-input]
- [x] 3.3 Tests: a fake `set-glm` on PATH for the subprocess contract, the budget, the parse failure, `known:<id>`, and an assertion that the prompt holds no field outside the shape-only set [REQ: new-findings-are-triaged-by-glm-within-a-budget-from-shape-only-input]

## 4. Remediation dispatch

- [x] 4.1 `dispatch.py`: the modes (`watchdog.remediation`, default `auto`), the brief (finding, evidence, fix brief; register, fix, prove, report; no deploy, no outward message), sent through `set-fleet-ask <owner>`, with the engagement id recorded [REQ: real-findings-are-dispatched-to-the-owning-project-s-agent-never-fixed-by-the-watchdog]
- [x] 4.2 Limits: one open dispatch per fingerprint, `watchdog.dispatch_daily` (default 3), a 24 h cooldown after an unresolved dispatch, `dispatch held: <reason>` recorded [REQ: real-findings-are-dispatched-to-the-owning-project-s-agent-never-fixed-by-the-watchdog]
- [x] 4.3 Tests with a fake `set-fleet-ask`: auto, propose, notify, the cap, the cooldown, a `known` verdict never dispatched, and no provider override passed [REQ: real-findings-are-dispatched-to-the-owning-project-s-agent-never-fixed-by-the-watchdog]

## 5. API and fleet UI

- [ ] 5.1 `lib/set_orch/api/watchdog.py`: `GET /api/fleet/watchdog` (last tick, interval, counts, open/untriaged/muted/recent-resolved), `POST …/{fp}/mute`, `POST …/{fp}/dispatch`; registered in `server.py` [REQ: the-fleet-header-shows-the-watchdog-s-state-and-a-dead-watchdog-never-looks-calm]
- [ ] 5.2 `web/src/components/FleetWatchdog.tsx`: the header badge (ok / count / red / stale) and the overlay panel (absolute, closable, never pushes), wired into `pages/Fleet.tsx` beside the auto-answer control [REQ: the-fleet-header-shows-the-watchdog-s-state-and-a-dead-watchdog-never-looks-calm]
- [ ] 5.3 Web unit tests for the four badge states and the panel actions; API tests [REQ: the-fleet-header-shows-the-watchdog-s-state-and-a-dead-watchdog-never-looks-calm]
- [ ] 5.4 `pnpm build` in `web/`, then a **visual check in the browser** (Claude in Chrome) on the running dashboard: badge with a real finding, badge stale (timer stopped), panel open without reflow. If the browser cannot be reached, this task stays OPEN [REQ: the-fleet-header-shows-the-watchdog-s-state-and-a-dead-watchdog-never-looks-calm]

## 6. Doctor self-check and docs

- [ ] 6.1 `lib/set_doctor/checks.py`: the `watchdog` record (timer state plus the last tick from the tick log) and its tests [REQ: the-watchdog-itself-is-checked]
- [ ] 6.2 `docs/reference/set-watchdog.md`: probes, config keys, modes, what leaves the machine, the kill switch; a row in the capability guide [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a tick starts while another holds the lock THEN it exits at once, logs the holder pid, changes nothing [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer, scenario: overlapping-ticks]
- [x] AC-2: WHEN one probe raises THEN a `watchdog-probe-error` finding is recorded and the other probes run [REQ: the-watchdog-runs-as-a-stateless-tick-on-a-timer, scenario: a-probe-raises]
- [x] AC-3: WHEN the same session is reported on two ticks THEN one finding with first_seen/last_seen from each [REQ: probes-are-declared-units-with-a-fingerprint, scenario: the-same-anomaly-on-two-ticks]
- [x] AC-4: WHEN a probe runs and no longer reports an open fingerprint THEN it becomes resolved and the open count drops [REQ: probes-are-declared-units-with-a-fingerprint, scenario: the-anomaly-stops]
- [x] AC-5: WHEN a session sits above its threshold 20 min with no handoff or clear THEN `auto-clear-miss` reports a fail with fill, threshold and minutes [REQ: built-in-probes-cover-the-set-features-that-fail-quietly, scenario: the-auto-clear-watcher-stops-acting]
- [x] AC-6: WHEN set-web is down THEN payload probes report one could-not-measure warn and `service-health` a fail [REQ: built-in-probes-cover-the-set-features-that-fail-quietly, scenario: the-fleet-payload-cannot-be-read]
- [x] AC-7: WHEN a module doctor starts returning a fail THEN the next `doctor-delta` run opens one finding with module and project as subject [REQ: module-doctors-are-probes-through-the-existing-declarations, scenario: a-family-doctor-reports-a-new-fail]
- [x] AC-8: WHEN the triage cap is reached THEN a new finding is stored untriaged, counted, and no GLM call is made [REQ: new-findings-are-triaged-by-glm-within-a-budget-from-shape-only-input, scenario: budget-exhausted]
- [x] AC-9: WHEN triage answers `known:B-214` THEN the entry id is recorded and nothing is dispatched [REQ: new-findings-are-triaged-by-glm-within-a-budget-from-shape-only-input, scenario: known-defect]
- [x] AC-10: WHEN a real finding with an owner arrives in auto mode under the cap THEN one `set-fleet-ask` is sent and the engagement id recorded [REQ: real-findings-are-dispatched-to-the-owning-project-s-agent-never-fixed-by-the-watchdog, scenario: auto-dispatch]
- [x] AC-11: WHEN a fourth real finding arrives on a day with three dispatches THEN it is held with `daily cap` and dispatch-now is offered [REQ: real-findings-are-dispatched-to-the-owning-project-s-agent-never-fixed-by-the-watchdog, scenario: cap-reached]
- [x] AC-12: WHEN the last tick is 40 min old at a 5-min interval THEN the badge shows stale and the last tick time, not zero [REQ: the-fleet-header-shows-the-watchdog-s-state-and-a-dead-watchdog-never-looks-calm, scenario: the-timer-stopped]
- [x] AC-13: WHEN a muted fingerprint recurs THEN it is stored muted, not counted, and listed under muted [REQ: the-fleet-header-shows-the-watchdog-s-state-and-a-dead-watchdog-never-looks-calm, scenario: a-muted-fingerprint-recurs]
- [ ] AC-14: WHEN the timer is enabled and the last tick is two hours old THEN the doctor's `watchdog` record is fail naming the last tick [REQ: the-watchdog-itself-is-checked, scenario: timer-installed-but-ticks-stopped]
- [ ] AC-15: WHEN no timer unit exists THEN the `watchdog` record is warn with the install command [REQ: the-watchdog-itself-is-checked, scenario: not-installed]
