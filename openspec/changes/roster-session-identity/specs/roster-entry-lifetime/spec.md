## IN SCOPE
- How long an entry lives, split by whether it can ever be acted on.
- Which kind of write is allowed to retire one, and which is forbidden from it.
- What the existing age-based bound continues to govern.

## OUT OF SCOPE
- Where a session identity comes from — see `roster-session-identity`.
- The document's `last_round_at` stamp and what `in_last_round` means.
- Migrating or cleaning up rosters already on disk; the ordinary sweep does that.
- Any change to the stored document's shape.

## ADDED Requirements

### Requirement: An entry that can never be acted on lives only while its agent is observed

The roster SHALL remove, on a whole-fleet write, every entry with no session identity that
that write did not see.

Such an entry is un-restorable by construction — there is no session to resume, and the read
path already reports it as such. Its one stated purpose is to keep the roster from claiming a
smaller fleet than exists while an agent is live and unknown to the runtime, and that purpose
ends when the agent stops being seen.

Measured before this change: **8 entries, 6 un-restorable, 4 with no session identity** — and
three of those four were one live session recorded under successive pids, each left behind
when the runtime's record finally appeared and a second entry was written under the real
session id. The record grew by one dead entry per agent and presented them as fleet history.

The fail direction is what makes this permissible: nothing that could have been acted on is
removed, and because the key is derived rather than allocated, an agent still present
reappears on the next sighting.

#### Scenario: An unseen session-less entry is removed by a whole-fleet write
- **GIVEN** a stored entry with no session identity
- **WHEN** a whole-fleet write does not include that agent
- **THEN** the entry is no longer stored

#### Scenario: A session-less entry that is still seen is kept
- **GIVEN** a stored entry with no session identity
- **WHEN** a whole-fleet write includes that agent
- **THEN** the entry remains stored
- **AND** its first-seen time is unchanged

#### Scenario: An entry that could be acted on is never removed this way
- **GIVEN** a stored entry that carries a session identity
- **WHEN** a whole-fleet write does not include that agent
- **THEN** the entry remains stored

### Requirement: Only a whole-fleet write may retire an entry this way

A write that does not carry the whole fleet SHALL NOT remove any entry on the grounds of not
having seen it.

A partial write knows nothing about what it did not look at, so removing on absence would
delete live agents' rows. The recording call already carries a flag stating whether its input
is the whole fleet, and the document's round stamp is already guarded by it for exactly this
reason; the same flag governs this.

#### Scenario: A partial write keeps what it did not see
- **GIVEN** a stored entry with no session identity
- **WHEN** a write that is not a whole-fleet write omits that agent
- **THEN** the entry remains stored

#### Scenario: A partial write still records what it did see
- **GIVEN** a write that is not a whole-fleet write
- **WHEN** it carries an agent
- **THEN** that agent's entry is written

### Requirement: The age bound continues to govern every other entry

The existing retention bound SHALL continue to apply unchanged to entries that carry a session
identity, and its removals SHALL continue to be logged.

The two rules answer different questions and neither replaces the other: the age bound lets a
record survive a machine being switched off, while the sighting rule removes rows that could
never have been acted on however recent they are.

#### Scenario: A recent session-carrying entry survives an absence
- **GIVEN** a stored entry that carries a session identity and was seen recently
- **WHEN** a whole-fleet write does not include that agent
- **THEN** the entry remains stored

#### Scenario: An old session-carrying entry is still pruned by age
- **GIVEN** a stored entry that carries a session identity and is older than the bound
- **WHEN** any write occurs
- **THEN** the entry is removed
- **AND** the removal is logged with the entry's key and its age
