## RENAMED Requirements

### Requirement: Restore takes an explicit selection, or the whole recorded list
FROM: `### Requirement: Restore is a per-project act over the whole recorded list`
TO: `### Requirement: Restore takes an explicit selection, or the whole recorded list`

## MODIFIED Requirements

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

### Requirement: The surface offers restore per project and shows what happened

The fleet screen SHALL offer restore for a project whose record is non-empty. Its **primary
offer SHALL be the last observed composition** — the entries the record marks as belonging to
the last round — and SHALL state how old that observation is, so the reader can tell a
composition from thirty seconds ago from one from three days ago.

Everything recorded but outside that composition SHALL remain reachable on the same screen
and individually selectable for restore. It MUST NOT be dropped from the surface: the record
holding more than the composition is information, and a screen that shows only the
composition would report a smaller history than exists.

When the last round holds no entries for the project, the surface SHALL state that nothing
was open when the fleet was last seen, and MUST NOT present an earlier round's entries as the
composition. When the record's last round is unknown, the surface SHALL fall back to offering
the whole recorded list and SHALL say that the composition could not be determined, rather
than presenting the whole list as the composition.

The screen SHALL state how many entries each offer would attempt before the act is taken, and
SHALL show the per-entry outcome afterwards, including the reason for every entry that did
not start. A project whose record is empty SHALL NOT present a restore control that would do
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
