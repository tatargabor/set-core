## Why

The set features that keep the fleet usable all fail quietly. An inbox watch can wake idle
sessions every half hour, and each wake re-reads a whole context. The auto-clear watcher can
stop handing off above its threshold. A relayed question can be held for 55 minutes while the
terminal looks busy (B-214). A user timer can fail. Today a person finds each of these by
accident, often days later, and the bug register's open half is mostly that kind of find
(B-211, B-214, B-215, B-218). `set-doctor` already knows a lot of the static state, but it runs
only when somebody types it, and it does not look at behaviour over time. The machine also has a
GLM quota that goes largely unused. It is cheap enough to watch all day, if each call stays small.

Stated by the user on 2026-11-24, by dictation: *„egy GLM-mel a háttérben futó folyamatosan futó
autó-figyelőt, egyfajta doktort … ha anomáliát lát, akkor szól, és/vagy indít egy fixálást is"*,
*„emészthető mennyiségű token legyen"*, *„a Fleet-be a UI-on … lássuk valamilyen ikonban, számban"*,
*„az elhárítását is kezdje meg automatikusan, nyilván külön agentekben, azok már nem kell, hogy
GLM-esek legyenek"*.

## What Changes

- **New `set-watchdog`, a stateless tick on a systemd user timer** (every 5 min). It is not a
  long-running chat session: a context that grows all day is exactly the cost it watches for.
  Each tick runs deterministic **probes** at no token cost and records what they observe.
- **Probes are small, declared units.** Each one has a name, an interval, what it reads, the
  invariant it checks, and a finding fingerprint. The first ones are built in:
  - wake storm: an idle session is woken without a human prompt again and again;
  - auto-clear miss: a live session stays above its project's threshold with no handoff and no clear;
  - relay hold: a relayed question is held past a bound;
  - service health: set-web, the agent owner, the auto-clear units, and failed user units;
  - doctor delta: a new `fail` in `set-doctor --json`, module doctors included.
  Projects contribute their own checks through the **existing** `doctors.d` declarations
  (`doctor/1`) rather than a second extension point. That is how a project family that builds
  other systems plugs in its own invariants.
- **GLM triage, only for new fingerprints.** One bounded `set-glm -p` call per tick, sent only
  when something new appeared. It classifies each finding as real, noise, or already known
  (matched against the bug register's titles). It names the owning project and writes a fix brief.
  Its input is **shape only**: counts, durations, unit names, session ids and project slugs, never
  transcript text. A daily call budget caps it. Over the budget, or with GLM unreachable, a finding
  stays **untriaged and visible**. It is never dropped.
- **Remediation in a separate Claude agent, never GLM.** A triaged real finding is handed to
  **its owning project's agent** through `set-fleet-ask`. The fleet starts a desk if the project
  has no live seat. The brief: register the defect, fix it, prove the fix, report done. The modes
  are `off | notify | propose | auto` (default `auto`, the user's ask). It is rate-limited: one
  open fix per fingerprint, a daily dispatch cap, and a cooldown after a failed fix. It never
  deploys and never sends anything outward. The brief says so, and the projects' own rules already do.
- **Fleet UI: a 🩺 badge in the fleet header.** It shows the open count, red when any finding is
  a `fail`, and **grey and "stale" when the last tick is older than three intervals**, so a dead
  watchdog never looks calm. An overlay panel lists the findings, the triage verdict, the owner and
  the fix state, with dismiss (mute a fingerprint for N days) and dispatch-now actions.
- **`set-doctor` checks the watchdog itself**: the timer is enabled, and the last tick is fresh.
- State lives under `~/.local/share/set-core/watchdog/` (mode 600). Nothing is written into a repository.

## Capabilities

### New Capabilities
- `fleet-watchdog`: the tick and its timer, the probe contract and the built-in probes, the
  finding store and fingerprinting, GLM triage with its budget and shape-only input, the
  remediation dispatch with its modes and limits, the API, and the fleet header badge and panel.

### Modified Capabilities
- `machine-doctor`: gains the watchdog self-check (timer enabled, last tick fresh).

## Impact

- New: `lib/set_orch/watchdog/` (tick, probes, store, triage, dispatch), `bin/set-watchdog`,
  `templates/systemd/set-watchdog.{service,timer}`, `lib/set_orch/api/watchdog.py`
  (`GET /api/fleet/watchdog`, plus the dismiss and dispatch actions), and a header component
  in `web/src`.
- Changed: `lib/set_doctor/checks.py` (self-check), `install.sh` (install list and unit),
  `docs/reference/` (a `set-watchdog` page).
- Uses without changing: `set-glm` and `set_orch.providers`, `set-fleet-ask` and desks, the fleet
  agents payload (context fill, cache heat), the question relay's state, `doctors.d`.
- Cost: GLM calls only on new fingerprints, under a configured daily cap. Claude tokens only for
  a dispatched fix.
