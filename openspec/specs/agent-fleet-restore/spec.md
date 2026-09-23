# agent-fleet-restore Specification

## Purpose
TBD - created by archiving change fleet-agent-restore. Update Purpose after archive.

## Requirements

### Requirement: Each entry is restored by starting an agent that resumes its session

For an entry that is resumable and not already live, the framework SHALL start an agent in
the entry's `cwd` through the service that owns agent lifetimes, resuming the entry's
session id. The framework itself MUST NOT fork the agent process, and the restore logic
MUST NOT be placed in that owner service.

The restarted agent SHALL run on the provider and model recorded for that session. Where no
provider was recorded, the entry SHALL be restored on the resolved default and reported as
having had no recorded provider — it MUST NOT be reported as having been restored onto the
provider it originally ran on.

#### Scenario: A resumable entry comes back as a resumed session

- **WHEN** an entry is resumable, its session is not live, and restore runs
- **THEN** an agent is started in the entry's `cwd` resuming that session id, and the entry's outcome is `started` carrying the new label

#### Scenario: The owner service being unavailable is reported, not swallowed

- **WHEN** restore runs and the service that owns agent lifetimes cannot be reached
- **THEN** the request fails with an explicit unavailable answer, and no entry is reported as started

#### Scenario: A session restored onto the provider it ran on

- **WHEN** an entry whose recorded provider is not the default is restored
- **THEN** the started agent runs on that recorded provider and model, and its credential comes from the same precedence level the original start used

#### Scenario: An entry with no recorded provider says so

- **WHEN** an entry has no recorded provider and is restored
- **THEN** it starts on the resolved default and its outcome states that no provider was recorded

### Requirement: A live session is skipped, never resumed

The framework SHALL NOT resume a session that a live process is bound to, because a resume
against a live session forks its conversation silently. Such an entry SHALL be reported as
skipped with that reason, and the running agent SHALL be left untouched.

#### Scenario: An already-running session is skipped

- **WHEN** an entry's session is bound to a live process and restore runs
- **THEN** that entry's outcome is `skipped` with a reason naming the live session, no resume is attempted, and the running agent is not stopped

#### Scenario: An indeterminate liveness is treated as live

- **WHEN** it cannot be determined whether an entry's session is bound to a live process
- **THEN** the entry is skipped rather than resumed, and the reason states that liveness was indeterminate

### Requirement: An unresumable entry is skipped with its reason

An entry with no transcript SHALL be reported as skipped with a reason naming the missing
transcript. It MUST NOT be reported as failed, and it MUST NOT be silently omitted from the
result.

#### Scenario: An entry with no transcript is skipped and named

- **WHEN** an entry has no transcript and restore runs
- **THEN** its outcome is `skipped` with a reason naming the missing transcript, and it appears in the result

### Requirement: The result reports every entry separately, and a partial restore reads as partial

The restore result SHALL carry one outcome per entry with its reason, and SHALL carry
counts of started, skipped and failed. A restore in which any entry did not start MUST NOT
be presented as a completed restore.

The result SHALL be presented as a bounded notice rather than as a run of text sharing a line with
its own detail. Its headline, the entries that did not start, and the entries that came back under
another name SHALL each occupy their own group within that notice.

A result in which every entry started SHALL close itself after a bounded interval, since it
describes a finished act. A result in which any entry did not start MUST NOT close itself, and
remains until the reader closes it. Where entries are grouped or collapsed, the counts of failed
and skipped entries SHALL remain visible without the reader opening anything.

#### Scenario: A mixed restore reports its parts

- **WHEN** restore runs over 9 entries of which 3 start, 4 are skipped and 2 fail
- **THEN** the result reports 3 started, 4 skipped, 2 failed, with a reason on each of the 6 that did not start

#### Scenario: One entry failing does not abandon the rest

- **WHEN** an entry fails to start
- **THEN** the remaining entries are still attempted, and the failure is reported against that entry alone

#### Scenario: The result groups its detail rather than running it together

- **WHEN** a restore reports entries that did not start and entries that were renamed
- **THEN** the headline, the entries that did not start and the renamed entries are presented as separate groups within one bounded notice

#### Scenario: A complete result closes itself

- **WHEN** a restore completes with every entry started
- **THEN** the result is shown and then closes without the reader acting

#### Scenario: A partial result stays until it is closed

- **WHEN** a restore completes with any entry skipped or failed
- **THEN** the result remains on screen until the reader closes it

#### Scenario: A collapsed group still reports its failures

- **WHEN** entries that did not start are collapsed within the result
- **THEN** the count of failed and skipped entries remains visible without opening the group

### Requirement: The surface offers restore per project and shows what happened

The fleet screen SHALL offer restore for a project whose record is non-empty. Its **primary
offer SHALL be the last observed composition** — the entries the record marks as belonging to
the last round — and SHALL state how old that observation is, so the reader can tell a
composition from thirty seconds ago from one from three days ago.

Everything recorded but outside that composition SHALL remain reachable on the same screen
and individually selectable for restore. It MUST NOT be dropped from the surface: the record
holding more than the composition is information, and a screen that shows only the
composition would report a smaller history than exists.

That list SHALL open as a **dialog over the page**, not inside the row that triggers it, and it
SHALL offer an explicit way out — a close control, the Escape key, and a click outside it — while
a click inside it SHALL NOT close it. A row is as wide as a row: a record of dozens of entries
carrying a transcript excerpt does not fit in one, and a surface that can be opened and not
obviously closed is a trap rather than a compact layout.

**That dialog's height SHALL follow its contents**, up to a maximum. It MUST NOT reserve a fixed
proportion of the viewport regardless of what it holds: a single recorded entry separated from the
panel's own footer by an expanse of empty space misreports how much there is to read. Where the
contents exceed the maximum, the list SHALL scroll while the chrome and any action footer stay in
place, and any entry that cannot be restored SHALL remain counted in the panel's header so that
scrolling can never hide it.

**Entries sharing a label SHALL be presented as one lineage** rather than as that many equal
rows. An entry is keyed on the session id and a resume mints a new one, so one named agent
accumulates one entry per resume; several rows carrying the same name and differing only by an
age is the state in which a person picks the wrong conversation. The lineage SHALL state how
many conversations it holds and the newest one's age, and SHALL open to the individual entries,
each of which stays selectable. A label holding a single entry SHALL be presented as that entry.

**A recorded entry SHALL be readable before it is picked** — its last turns shown on request,
without resuming it or starting anything. Where that read is not possible the surface SHALL say
which reason applies, rather than showing an empty panel that reads like a session with nothing
in it.

When the last round holds no entries for the project, the surface SHALL state that nothing
was open when the fleet was last seen, and MUST NOT present an earlier round's entries as the
composition. When the record's last round is unknown, the surface SHALL fall back to offering
the whole recorded list and SHALL say that the composition could not be determined, rather
than presenting the whole list as the composition.

The screen SHALL state how many entries each offer would attempt before the act is taken, and
SHALL show the per-entry outcome afterwards, including the reason for every entry that did not
start. A project whose record is empty SHALL NOT present a restore control that would do
nothing.

#### Scenario: A project with a record offers restore and names the count

- **WHEN** a project's record holds entries and its screen is opened
- **THEN** a restore control is offered stating how many entries would be attempted

#### Scenario: The primary offer is the last composition, with its age

- **WHEN** a project's record holds 24 entries of which 3 belong to the last round, and its screen is opened
- **THEN** the primary restore control offers those 3, states when that composition was observed, and does not offer to start the other 21

#### Scenario: The rest of the record stays reachable and selectable

- **WHEN** a project's record holds entries outside the last composition
- **THEN** the screen makes those entries reachable and individually selectable for restore, rather than omitting them

#### Scenario: Six entries under one label read as one lineage

- **WHEN** the recorded list holds six entries carrying the same label
- **THEN** they render as one row naming that label, how many conversations it holds and the newest one's age, which opens to the six entries, each still selectable

#### Scenario: A label with one entry is not dressed up as a lineage

- **WHEN** a label holds exactly one recorded entry
- **THEN** it renders as that entry, with no group to open

#### Scenario: An entry can be read before it is picked

- **WHEN** the reader asks to see a recorded entry
- **THEN** the last turns of its session are shown inline, and no agent is started and no session is resumed

#### Scenario: An entry that cannot be read says which reason applies

- **WHEN** the reader asks to see an entry whose transcript is gone or which never had a session id
- **THEN** the reason is shown in place of the turns, rather than an empty panel

#### Scenario: A project that was not open when the fleet went down says so

- **WHEN** a project's record holds entries but none of them belongs to the last round
- **THEN** the screen states that nothing was open when the fleet was last seen, and no earlier round is offered as the composition

#### Scenario: An undeterminable composition is stated, not invented

- **WHEN** the record carries no last round at all
- **THEN** the screen offers the whole recorded list and states that the composition could not be determined

#### Scenario: The outcome of every entry is visible after restoring

- **WHEN** restore completes with entries that were skipped or failed
- **THEN** the screen shows each of those entries with its reason, rather than a single success or failure message

#### Scenario: An empty record offers no restore control

- **WHEN** a project has no recorded entries
- **THEN** no restore control is offered for it

#### Scenario: The recorded list opens as a dialog

- **WHEN** the reader opens the recorded list
- **THEN** it opens as a dialog over the page rather than inside the row that triggered it

#### Scenario: The recorded list can be closed three ways

- **WHEN** the recorded list is open
- **THEN** it can be closed by an explicit close control, by the Escape key, and by a click outside it

#### Scenario: A click inside the list does not throw the reader out

- **WHEN** the reader clicks inside the open list
- **THEN** it stays open

#### Scenario: One recorded entry gives a panel sized for one entry

- **WHEN** a project's record holds a single recorded entry and the reader opens the list
- **THEN** the panel is as tall as its chrome and that entry require, rather than a fixed proportion of the viewport

#### Scenario: A long list scrolls without moving the chrome

- **WHEN** the recorded list holds more entries than the panel's maximum height allows
- **THEN** the list scrolls while the panel's header and any action footer stay in place

#### Scenario: Scrolling cannot hide an entry that cannot be restored

- **WHEN** an entry that cannot be restored lies below the visible part of a scrolling list
- **THEN** the panel's header still counts it

### Requirement: Restore takes an explicit selection, or the whole recorded list

The framework SHALL expose a restore act taking one project and an **optional** set of entry
keys, and SHALL attempt exactly the entries that selection names. With **no selection given**
it SHALL attempt every entry in that project's record, which is the behaviour that already
ships and MUST NOT change. Restore MUST NOT be triggered automatically by discovery, by a
page load, or by the framework starting.

A selection given but **empty** SHALL attempt nothing. It MUST NOT fall back to the whole
list: an absent selection and an empty one are different requests, and the fallback would
act on nine entries where the caller asked for none.

A key naming no recorded entry SHALL be reported as a per-key outcome stating that nothing
is recorded under it. It MUST NOT be silently dropped, because a selection that quietly
attempts fewer entries than it named reads as one that attempted all of them.

#### Scenario: Restoring a project attempts every recorded entry

- **WHEN** restore is requested for a project whose record holds `N` entries, with no selection
- **THEN** the result carries exactly `N` per-entry outcomes, one per recorded entry

#### Scenario: Restoring with a selection attempts exactly that selection

- **WHEN** restore is requested for a project whose record holds `N` entries, naming `k` of their keys
- **THEN** exactly those `k` entries are attempted, the other `N - k` are not attempted at all, and the result carries `k` outcomes

#### Scenario: An empty selection attempts nothing

- **WHEN** restore is requested with a selection that names no keys
- **THEN** no agent is started, and the result does not report the whole record as attempted

#### Scenario: A selected key that is not recorded is reported

- **WHEN** a selection names a key the project's record does not hold
- **THEN** the result carries an outcome for that key stating nothing is recorded under it, rather than omitting it

#### Scenario: Restoring a project with an empty record changes nothing

- **WHEN** restore is requested for a project whose record is empty
- **THEN** no agent is started and the result reports zero entries attempted

### Requirement: The fleet offers restore across projects from one dialog

The fleet screen SHALL offer a fleet-wide reopen control that is reachable without selecting a
project and while agents are running. It SHALL sit in the project column's attention row, after
the status marks, and SHALL NOT be drawn when the fleet-wide record lists no project or cannot
be read.

The control SHALL open a single dialog listing every project that has a record, newest first,
each with its recorded count and the age of its newest entry. Opening a project SHALL show its
recorded entries with the same lineage grouping, per-entry selectability, blocked-entry reasons
and peek as the per-project dialog. A project's entries SHALL be read when that project is
opened, not before.

Selection SHALL span projects. The act SHALL be armed: before anything is posted it SHALL state
how many agents it would start and in how many projects, and it SHALL post nothing until
confirmed. Nothing SHALL be selected when the dialog opens, and there SHALL be no act that
restores a whole project or the whole fleet from this dialog.

Each project's selection SHALL be posted to that project's existing restore route with exactly
the selected keys. The result SHALL be shown per project and summed across projects. It SHALL
read as complete only when every project's request succeeded and every project's own result was
complete. A project whose request failed SHALL be named together with its error, and it MUST NOT
be counted as a project where nothing started.

The dialog SHALL close on its close control, on Escape and on a click outside it, and SHALL NOT
close on a click inside it.

#### Scenario: The control is reachable while agents are running

- **WHEN** agents are running and the fleet-wide record lists projects
- **THEN** the project column's attention row shows the reopen control, with no project selected

#### Scenario: No record, no control

- **WHEN** the fleet-wide record lists no project, or its read fails
- **THEN** no reopen control is drawn

#### Scenario: A project's entries are read on opening it

- **WHEN** the dialog opens listing three projects
- **THEN** no per-project record read has been made, and opening one project reads that project's record only

#### Scenario: One click posts nothing

- **WHEN** entries are ticked in two projects and the restore act is clicked once
- **THEN** the dialog states the agent and project counts and no restore request has been sent

#### Scenario: Confirmed selection posts exactly the ticked keys per project

- **WHEN** two entries are ticked in project A and one in project B, and the act is confirmed
- **THEN** A's restore route receives exactly A's two keys, B's receives exactly B's one key, and no other project's route is called

#### Scenario: A failed project makes the whole result partial and is named

- **WHEN** A's restore completes and B's request is answered with a 503
- **THEN** the result is marked partial, A's outcome is shown, and B is named with the error it returned

#### Scenario: A partial project makes the whole result partial

- **WHEN** every project's request succeeds but one project's result is not complete
- **THEN** the cross-project result is marked partial
