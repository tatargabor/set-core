## MODIFIED Requirements

### Requirement: The framework records each discovered agent durably, keyed on session identity

The framework SHALL persist, for every interactive agent discovery reports, an entry
carrying its session id, its label or name, its `cwd`, its project, its kind, the time it
was first recorded and the time it was last seen. The entry SHALL be keyed on the **session
id**, never on the pid: a pid is reused, so a pid-keyed record cannot survive the reboot
this capability exists for.

The recorded label SHALL be the label the framework itself holds for that agent — the name
a person chose and every control addresses — and NOT the name the runtime derived for the
session. Measured 2026-08-21 after the first real reboot: the runtime's name carries
`nameSource: "derived"`, it is regenerated on every resume, and recording it gave back
`set-core-34` for an agent the user had named `set-core-bugfix`.

Where the framework holds no label for an agent — one it did not start — the entry SHALL
state that the label is unknown. It MUST NOT be filled in from the discovered name: an
invented label renders exactly like a chosen one, and a restore would hand it back as though
it were the name the user gave.

An agent discovery reports without a session id SHALL be recorded as an entry that states
the session id is absent, rather than being dropped — a session alive and unknown to the
runtime's records is a measured condition, and omitting it would make the record claim a
smaller fleet than existed.

#### Scenario: A discovered agent is recorded

- **WHEN** discovery reports an interactive agent with session id `S` and cwd `C`, and the framework holds it under label `L` while the runtime's derived name for it is `D`
- **THEN** the record for that project contains an entry keyed `S` carrying `L`, `C`, its kind, a first-seen time and a last-seen time, and it does not carry `D`

#### Scenario: An agent the framework does not hold is recorded with no label

- **WHEN** discovery reports an interactive agent the framework holds no label for
- **THEN** the entry for it states that its label is unknown, and the runtime's derived name is not recorded in its place

#### Scenario: The label cannot be asked for, and a recorded label is not overwritten by a guess

- **WHEN** the service that holds agent labels cannot be reached while the record is written
- **THEN** an existing entry keeps the label it already carries, and a new entry states its label is unknown

#### Scenario: Seeing the same session again updates last-seen and never duplicates

- **WHEN** discovery reports session id `S` again, at a later time, possibly under a different pid
- **THEN** the existing entry's last-seen time advances, its first-seen time is unchanged, and exactly one entry for `S` exists

#### Scenario: A renamed agent is recorded under its new label

- **WHEN** an agent held under `L` is renamed to `N` and the record is written again
- **THEN** the entry for its session carries `N`

#### Scenario: An agent without a session id is recorded as such

- **WHEN** discovery reports an interactive agent that has no session id
- **THEN** an entry exists for it whose session id is explicitly absent, and it is not silently dropped

#### Scenario: One-shot subprocesses are not recorded

- **WHEN** discovery reports an agent whose kind is `oneshot`
- **THEN** no entry is written for it
