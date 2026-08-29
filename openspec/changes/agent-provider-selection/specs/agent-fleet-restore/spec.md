## MODIFIED Requirements

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
