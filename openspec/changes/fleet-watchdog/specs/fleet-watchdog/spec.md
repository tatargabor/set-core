## IN SCOPE
- A stateless watchdog tick on a user timer, and the probes it runs
- The probe contract, the built-in probes, and reading `doctors.d` module doctors as probes
- Finding fingerprints, the local finding store, mute and resolution
- GLM triage of new findings: bounded, shape-only input, a daily budget
- Remediation dispatch to the owning project's agent: modes, limits, the brief
- `GET /api/fleet/watchdog` and its actions; the fleet header badge and overlay panel

## OUT OF SCOPE
- A long-running chat session as the watchdog (rejected: its context would grow all day)
- The watchdog editing any tree itself: fixes are made by the owning project's agent
- Deploying, or sending anything outward (email, chat to a person): never, in any mode
- A second project extension point beside `doctors.d`

## ADDED Requirements

### Requirement: The watchdog runs as a stateless tick on a timer
The system SHALL provide `set-watchdog tick`, run by a systemd user timer (default every 5
minutes). A tick MUST load its state from the store, run every probe whose interval has elapsed,
update the store, and exit. It MUST NOT hold a conversation context across ticks. A tick MUST take
an exclusive lock, so that two ticks never run at once. Each tick MUST append one line to the tick
log, with its start time, its duration, the probes it ran, and the counts of new, open and resolved
findings. The line MUST NOT carry any finding's evidence.

#### Scenario: Overlapping ticks
- **WHEN** a tick starts while another tick still holds the lock
- **THEN** the second tick exits at once with a log line naming the holder pid, and changes nothing

#### Scenario: A probe raises
- **WHEN** one probe raises an exception
- **THEN** the tick records a `watchdog-probe-error` finding for that probe and runs the remaining probes

### Requirement: Probes are declared units with a fingerprint
A probe SHALL declare a name, an interval, and a `collect()` that returns findings. A finding
SHALL carry the probe name, a severity (`fail` or `warn`), a subject (a project slug, a session
id, a unit name), a one-line summary, shape-only evidence (counts, durations, timestamps, ids),
and a fingerprint, computed from the probe name and the subject only. Re-observing the same
fingerprint MUST update the existing finding's `last_seen` and evidence instead of creating a new
one. A finding whose probe ran and did not report it again MUST become `resolved`, with the time.

#### Scenario: The same anomaly on two ticks
- **WHEN** the wake-storm probe reports the same session on two consecutive ticks
- **THEN** the store holds one finding for it, with `first_seen` from the first tick and `last_seen` from the second

#### Scenario: The anomaly stops
- **WHEN** a probe runs and no longer reports a fingerprint that was open
- **THEN** that finding becomes `resolved`, and the fleet's open count drops by one

### Requirement: Built-in probes cover the set features that fail quietly
The system SHALL ship these probes:
- `wake-storm`: a live session receives turns that no human prompt started, at or above a
  configured count within a window (default 3 in 2 hours), while it has no open request of its own;
- `auto-clear-miss`: a live session's measured context fill stays at or above its project's
  auto-clear threshold for longer than a grace period (default 15 min), with no handoff and no
  clear in that time;
- `relay-hold`: a relayed question has been held longer than a bound (default 15 min) although a
  prompt was typed into the asking session's terminal during the hold, counted from the
  transcript's queued-prompt records. A hold with no typed prompt is the owner not having answered
  yet, which the relay itself surfaces, and MUST NOT be reported. A hold whose transcript cannot
  be read MUST be reported, with the typed count unknown;
- `service-health`: set-web does not answer, the agent owner is unreachable, an auto-clear unit is
  inactive for a registered project that has auto-clear armed, or a user unit is in the `failed` state;
- `doctor-delta`: `set-doctor --json` (module doctors included) reports a `fail` record that was
  not present on its previous run. It runs on a slower interval (default 30 min).
A probe that cannot measure its input MUST report that as a `warn` finding. It MUST NOT report no finding.

#### Scenario: The auto-clear watcher stops acting
- **WHEN** a live session has been at 92 % fill for 20 minutes, its project's threshold is 85 %, and no handoff file or clear happened since it crossed
- **THEN** `auto-clear-miss` reports a `fail` finding with that session as its subject, the fill, the threshold and the minutes above it

#### Scenario: A held question the owner has not answered yet
- **WHEN** a relayed question has been held for 40 minutes and its transcript records no prompt queued from the terminal since the hold started
- **THEN** `relay-hold` reports no finding for that session

#### Scenario: A prompt typed into the terminal does not release the held question
- **WHEN** a relayed question has been held for 20 minutes and its transcript records a prompt queued from the terminal after the hold started
- **THEN** `relay-hold` reports a `warn` finding with that session as its subject and the count of typed prompts in its evidence

#### Scenario: A failed unit carries its exit
- **WHEN** a user unit is in the `failed` state
- **THEN** its `service-health` finding carries the unit's systemd `Result` and main exit status, so the triage can name the cause

#### Scenario: The fleet payload cannot be read
- **WHEN** set-web is down and the probes that read the fleet payload cannot get it
- **THEN** those probes report one `warn` saying they could not measure, and `service-health` reports set-web as a `fail`

### Requirement: Module doctors are probes through the existing declarations
The `doctor-delta` probe SHALL obtain module doctors' records only through `set-doctor --json`,
which already merges the `doctors.d` declarations. A project SHALL add a watched invariant by
declaring a module doctor. The watchdog MUST NOT read a second declaration directory.

#### Scenario: A family doctor reports a new fail
- **WHEN** a declared module doctor starts returning a `fail` record for one of its projects
- **THEN** the next `doctor-delta` run opens one finding, with that module and project as its subject

### Requirement: New findings are triaged by GLM within a budget, from shape-only input
When a tick opens one or more new findings, the system SHALL make at most one triage call for
that tick through `set-glm -p`, with JSON output. The call MUST carry each new finding's probe,
severity, subject, summary and evidence, plus the titles of the open bug-register entries. Its
input MUST be capped at a configured size (default 8000 characters). It MUST NOT carry any
transcript text, message body, or file content from a project. For each finding, the answer gives a
verdict (`real`, `noise`, or `known:<entry id>`), an owning project, and a fix brief of at most
600 characters. The daily number of triage calls MUST be capped (`watchdog.triage_daily_calls`,
default 60). Over the cap, with GLM unreachable, or with an answer that cannot be parsed, the
finding MUST stay `untriaged` and stay visible. The answer is keyed by the fingerprint the model
returns, so a brief MUST be checked against the finding it is stored on: a brief that names another
finding of the same call first, or names only another one, MUST leave the finding `untriaged`.

#### Scenario: Budget exhausted
- **WHEN** the day's triage calls have reached the cap and a new finding opens
- **THEN** the finding is stored as `untriaged`, the fleet badge counts it, and no GLM call is made

#### Scenario: A brief written for another finding
- **WHEN** one triage call covers two findings and the brief answered for the first names the second finding's subject before its own, or names only the second's
- **THEN** the first finding stays `untriaged` and the mismatch is logged with both fingerprints

#### Scenario: Known defect
- **WHEN** triage answers `known:B-214` for a `relay-hold` finding
- **THEN** the finding records that entry id and is not dispatched for a fix

### Requirement: Real findings are dispatched to the owning project's agent, never fixed by the watchdog
The system SHALL support remediation modes `off`, `notify`, `propose` and `auto`
(`watchdog.remediation`, default `auto`). In `auto` mode, a finding triaged `real` SHALL be handed
to its owning project through `set-fleet-ask`. The fleet's desk mechanism starts a seat when the
project has none. The brief MUST name the finding, its evidence and the fix brief. It MUST instruct
the agent to enter the defect in its own project's bug register, fix it, prove the fix, and report
done. It MUST state that the agent may not deploy and may not send anything outward. In `propose`
mode, the dispatch is offered as an action and not sent. In `notify` mode, the finding is only shown.
Dispatch limits MUST hold in every mode:
- at most one open dispatch per fingerprint;
- a daily dispatch cap (`watchdog.dispatch_daily`, default 3);
- no re-dispatch of a fingerprint within 24 h after a dispatch that ended without the finding resolving.
The fix agent MUST NOT run on the GLM provider.

#### Scenario: Auto dispatch
- **WHEN** a finding is triaged `real` with owner `set-agent-comm`, the mode is `auto`, and today's dispatches are below the cap
- **THEN** one `set-fleet-ask set-agent-comm` request is sent with the brief, and the finding records the engagement id and `dispatched`

#### Scenario: Cap reached
- **WHEN** a fourth finding is triaged `real` on a day with three dispatches
- **THEN** it is not dispatched, it records `dispatch held: daily cap`, and the panel offers dispatch-now

### Requirement: The fleet header shows the watchdog's state, and a dead watchdog never looks calm
`GET /api/fleet/watchdog` SHALL return the last tick time, the configured interval, the counts by
state and severity, and the open, untriaged and recently resolved findings. The fleet header SHALL
show a watchdog badge with the open count. The badge MUST be red when any open finding is a `fail`.
It MUST be marked stale, as a distinct state from zero, when the last tick is older than three
intervals or no tick was ever recorded. Clicking the badge SHALL open an overlay panel that floats
above the layout and does not push it. The panel lists the findings with their verdict, owner and
dispatch state, and offers dismiss (mute the fingerprint for a chosen number of days) and dispatch-now.

#### Scenario: The timer stopped
- **WHEN** the last tick is 40 minutes old with a 5-minute interval
- **THEN** the badge shows the stale state and the time of the last tick, not a zero count

#### Scenario: A muted fingerprint recurs
- **WHEN** a muted fingerprint is reported again before its mute expires
- **THEN** it is stored with `muted` set, it is not counted on the badge, and the panel lists it under muted
