## MODIFIED Requirements

### Requirement: Each entry is restored by starting an agent that resumes its session

For an entry that is resumable and not already live, the framework SHALL start an agent in
the entry's `cwd` through the service that owns agent lifetimes, resuming the entry's
session id. The framework itself MUST NOT fork the agent process, and the restore logic
MUST NOT be placed in that owner service.

The restored agent SHALL come back under the label the entry recorded, so that the name a
person navigates by survives the reboot along with the conversation. Where the entry records
no label, the framework SHALL derive one and the outcome SHALL state that the name was
derived rather than restored — a generated name presented as a restored one is a false value
in exactly the place a person looks to recognise their own work.

Where the recorded label is already held by another agent, the framework MAY derive a free
variant, and the outcome SHALL report the rename. Restore derives rather than refuses because
the alternative is losing the agent and nobody is watching at that moment; this is the
opposite of a rename requested by a person, which refuses instead.

#### Scenario: A resumable entry comes back as a resumed session

- **WHEN** an entry recorded under label `L` is resumable, its session is not live, and restore runs
- **THEN** an agent is started in the entry's `cwd` resuming that session id under label `L`, and the entry's outcome is `started` naming `L`

#### Scenario: An entry with no recorded label says its name was derived

- **WHEN** an entry whose label is unknown is restored
- **THEN** the agent starts under a derived label and the outcome states the name was derived, not restored

#### Scenario: A collision renames and reports it

- **WHEN** an entry's recorded label is already held by another agent and the entry is restored
- **THEN** the agent starts under a free variant and the outcome reports both the wanted and the used label

#### Scenario: The owner service being unavailable is reported, not swallowed

- **WHEN** restore runs and the service that owns agent lifetimes cannot be reached
- **THEN** the request fails with an explicit unavailable answer, and no entry is reported as started
