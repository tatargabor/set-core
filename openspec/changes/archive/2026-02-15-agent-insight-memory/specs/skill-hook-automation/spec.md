## MODIFIED Requirements

### Requirement: Memory hooks use only valid shodh-memory types
All `set-memory remember --type` invocations in hook templates SHALL use valid shodh-memory types: `Decision`, `Learning`, or `Context`. The hooks SHALL NOT use `Observation` or `Event`. Mid-flow type option lists SHALL only offer `Decision`, `Learning`, `Context` — not `Observation`.

#### Scenario: Archive hook saves completion record
- **WHEN** the archive hook saves a change completion event
- **THEN** it uses `--type Context` (not `--type Event`)

#### Scenario: Apply hook saves error observations
- **WHEN** the apply hook saves error descriptions
- **THEN** it uses `--type Learning` (not `--type Observation`)

#### Scenario: Hooks reinstalled after update
- **WHEN** `set-memory-hooks install` is run after the type mapping fix
- **THEN** all installed SKILL.md files contain only valid types

#### Scenario: Mid-flow type options are valid
- **WHEN** a SKILL.md offers type choices for mid-flow saves (e.g., `--type <Decision|Learning|Context>`)
- **THEN** it does NOT include `Observation` or `Event` as options

## ADDED Requirements

### Requirement: Memory hooks use structured tags
All `set-memory remember` invocations in SKILL.md hooks SHALL use structured tags: `change:<name>`, `phase:<skill>`, `source:<agent|user>`, and optional topic tags.

#### Scenario: Mid-flow user save uses structured tags
- **WHEN** the mid-flow hook saves user-shared knowledge in any skill
- **THEN** the `--tags` argument follows the format `change:<change-name>,phase:<skill-name>,source:user,<topic>`

#### Scenario: Apply post-session save uses structured tags
- **WHEN** the apply Step 7 hook saves errors or patterns
- **THEN** the `--tags` argument follows the format `change:<change-name>,phase:apply,source:agent,<topic>`

#### Scenario: Archive save uses structured tags
- **WHEN** the archive hook saves decisions, lessons, or completion records
- **THEN** the `--tags` argument follows the format `change:<change-name>,phase:archive,source:agent,<topic>`

### Requirement: Enhanced recall in hooks uses mode and tag parameters
All `set-memory recall` invocations in SKILL.md hooks SHALL use `--mode hybrid` for combined semantic+temporal search, and `--tags change:<name>` where a specific change context exists.

#### Scenario: Continue skill recall uses enhanced parameters
- **WHEN** the continue skill runs its recall step
- **THEN** it uses `set-memory recall "<query>" --limit 5 --mode hybrid --tags change:<name>`

#### Scenario: Apply skill recall uses enhanced parameters
- **WHEN** the apply skill runs its recall step
- **THEN** it uses `set-memory recall "<query>" --limit 5 --mode hybrid --tags change:<name>`

#### Scenario: Explore skill recall without change context
- **WHEN** the explore skill runs its recall step
- **AND** there is no specific change context (free exploration)
- **THEN** it uses `set-memory recall "<query>" --limit 5 --mode hybrid` without `--tags` filter

### Requirement: Verify-change skill has memory hooks
The verify-change SKILL.md SHALL include recall before verification and remember after verification for problems found and lessons learned.

#### Scenario: Verify recall before verification
- **WHEN** the verify skill starts verification
- **THEN** it runs `set-memory recall "<change-name> verification issues" --limit 5 --mode hybrid --tags change:<name>`
- **AND** uses relevant memories to inform the verification

#### Scenario: Verify remember on problems found
- **WHEN** the verify skill finds implementation problems
- **THEN** it saves each problem as `set-memory remember --type Learning --tags change:<name>,phase:verify,source:agent,issue`

#### Scenario: Verify remember on successful verification
- **WHEN** the verify skill completes successfully with noteworthy observations
- **THEN** it saves observations as `set-memory remember --type Learning --tags change:<name>,phase:verify,source:agent,pattern`

### Requirement: Sync-specs skill has memory hooks
The sync-specs SKILL.md SHALL save merge decisions to set-memory when spec conflicts are resolved or significant merge choices are made.

#### Scenario: Sync-specs saves merge decisions
- **WHEN** the sync-specs skill resolves a spec merge conflict or makes a significant merge choice
- **THEN** it saves the decision as `set-memory remember --type Decision --tags change:<name>,phase:sync-specs,source:agent,spec-merge`

#### Scenario: Sync-specs with no significant decisions
- **WHEN** the sync-specs skill performs a straightforward merge with no conflicts
- **THEN** it does NOT save any memory (no noise)
