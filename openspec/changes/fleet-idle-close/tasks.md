## 1. Selection

- [x] 1.1 `lib/set_orch/fleet/idle_close.py` (core): `select(agents, threshold_s)` sorts each listed agent into close / keep-unmeasured / keep-busy / unreachable / recent [REQ: only-long-idle-interactive-agents-are-closed]
- [x] 1.2 Unknown idle time, a running tool, or no terminal label keeps the agent, with the reason [REQ: doubt-keeps-the-agent]
- [x] 1.3 Threshold from `--hours`, else local config `fleet_idle_close_hours`, else 48 [REQ: only-long-idle-interactive-agents-are-closed]

## 2. Closing and the record

- [x] 2.1 `run(base_url, threshold_s, dry_run)` reads the listing, stops each selected agent through the stop route, and reports closed / failed / kept [REQ: every-close-is-recorded]
- [x] 2.2 A dry run sends no stop request [REQ: a-dry-run-closes-nothing]
- [x] 2.3 Each close appends one JSON line to `$XDG_STATE_HOME/set-core/fleet-idle-close.jsonl`; a 404 or an error is a failure with no record [REQ: every-close-is-recorded]

## 3. Command and schedule

- [x] 3.1 `bin/set-fleet-idle-close` with `--hours`, `--dry-run`, `--json`, and `install-timer` [REQ: the-schedule-is-installed-on-purpose]
- [x] 3.2 `install-timer` writes a daily user service + timer (Persistent) and enables the timer [REQ: the-schedule-is-installed-on-purpose]

## 4. Verification

- [x] 4.1 Unit tests for selection, dry run, the log and the 404 path, against a real local HTTP server [REQ: only-long-idle-interactive-agents-are-closed]
- [x] 4.2 A live dry run against the running fleet, then the timer installed on this machine [REQ: the-schedule-is-installed-on-purpose] — 2026-11-07: dry run listed 0 to close (2 unmeasured kept, 16 recent); timer enabled for 04:00 daily; one manual service run finished with the same result. Mutation check: input→movement (4 fail), dry-run ignored (1 fail), busy unchecked (2 fail)

## 5. The fleet header

- [x] 5.1 `GET/POST /api/fleet/idle-close` (core API): status (timer, threshold, upcoming, recent closes with running state), switch on/off (installs the timer the first time), threshold 6 h–30 days [REQ: the-fleet-header-shows-and-steers-the-auto-close]
- [x] 5.2 `web/src/lib/fleetIdleClose.ts` + `components/FleetIdleClose.tsx`, mounted beside the question relay [REQ: the-fleet-header-shows-and-steers-the-auto-close]
- [x] 5.3 Visual check in Chrome — 2026-11-08: the moon icon lit on the header; the panel floats over the screen, shows "daily at night · after 2 days · next run today 04:00 · nothing to close" and the 9 hand-closed agents with "bring back"; no write control was clicked. Escape first did NOT close it (the key never reached the document listener); fixed to a capture-phase handler that also stops the key, re-checked: it closes [REQ: the-fleet-header-shows-and-steers-the-auto-close]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an interactive fleet-started agent's last human input is past the threshold THEN it is closed [REQ: only-long-idle-interactive-agents-are-closed, scenario: an-agent-idle-past-the-threshold-is-closed]
- [x] AC-2: WHEN the last human input is within the threshold THEN it is kept [REQ: only-long-idle-interactive-agents-are-closed, scenario: an-agent-used-recently-is-kept]
- [x] AC-3: WHEN input is old but the agent moved recently THEN it is still closed [REQ: only-long-idle-interactive-agents-are-closed, scenario: movement-without-the-owner-does-not-count-as-use]
- [x] AC-4: WHEN idle time is unknown THEN it is kept as unmeasured [REQ: doubt-keeps-the-agent, scenario: unmeasured-idle-time]
- [x] AC-5: WHEN an idle-long agent is running a tool THEN it is kept as busy [REQ: doubt-keeps-the-agent, scenario: busy-at-the-moment]
- [x] AC-6: WHEN run with --dry-run THEN qualifying agents are listed and no stop is sent [REQ: a-dry-run-closes-nothing, scenario: dry-run]
- [x] AC-7: WHEN an agent is closed THEN one log line with its session id is appended [REQ: every-close-is-recorded, scenario: a-close-is-logged]
- [x] AC-8: WHEN the stop route answers 404 THEN it is reported failed and not logged [REQ: every-close-is-recorded, scenario: a-refused-stop-is-not-a-close]
- [x] AC-9: WHEN install-timer runs THEN a daily enabled user timer runs the command [REQ: the-schedule-is-installed-on-purpose, scenario: installing-the-timer]
- [x] AC-10: WHEN the run is on and agents will pass the threshold by the next run THEN their count rides on the closed control [REQ: the-fleet-header-shows-and-steers-the-auto-close, scenario: the-coming-closes-ride-on-the-closed-control]
- [ ] AC-11: WHEN "bring back" is pressed on a closed, not running session THEN only that session is restored — OPEN: not pressed live (it starts a real agent); the request it sends is `keys: [session_id]` to the existing roster restore [REQ: the-fleet-header-shows-and-steers-the-auto-close, scenario: a-closed-agent-is-brought-back]
- [x] AC-12: WHEN systemctl cannot be asked THEN the control shows unknown and the switch is disabled [REQ: the-fleet-header-shows-and-steers-the-auto-close, scenario: unreadable-timer]
- [ ] AC-13: WHEN the panel is open and Escape is pressed THEN the panel closes and the terminal receives no Escape — PARTLY: closing verified in Chrome with focus inside the panel; deliberately NOT driven with a live agent terminal focused, because a leaked Escape would interrupt a real agent [REQ: the-fleet-header-shows-and-steers-the-auto-close, scenario: escape-stays-in-the-panel]
