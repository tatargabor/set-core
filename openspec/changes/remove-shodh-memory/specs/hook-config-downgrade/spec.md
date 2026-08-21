## MODIFIED Requirements

### Requirement: Detect stale set-hook-memory entries in PreToolUse
The deploy script SHALL identify EVERY `set-hook-memory` entry in the PreToolUse array as
stale. The canonical config has zero `set-hook-memory` entries in any event array, so no
matcher is exempt.

#### Scenario: Project with 6 PreToolUse memory matchers
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json contains PreToolUse entries with command `set-hook-memory PreToolUse` for matchers Read, Edit, Write, Bash, Task, Grep
- **THEN** all 6 entries SHALL be identified as stale

#### Scenario: Project with only Skill activity-track matcher
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** PreToolUse contains only `{matcher: "Skill", command: ".claude/hooks/activity-track.sh"}`
- **THEN** no stale entries SHALL be detected in PreToolUse

### Requirement: Detect stale set-hook-memory entries in PostToolUse
The deploy script SHALL identify EVERY `set-hook-memory` entry in the PostToolUse array as
stale, regardless of matcher. `Read` and `Bash` are no longer canonical; they were the two
matchers that carried the removed subsystem's only surviving write path.

#### Scenario: Project with 6 PostToolUse memory matchers
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json contains PostToolUse entries with command `set-hook-memory PostToolUse` for matchers Read, Edit, Write, Bash, Task, Grep
- **THEN** all 6 entries SHALL be identified as stale, Read and Bash included

### Requirement: Remove only set-hook-memory stale entries
The deploy script SHALL remove stale entries surgically — every entry whose command begins
with `set-hook-memory`, in any event array, and nothing else. A project's own hooks SHALL
survive in their original order.

#### Scenario: Non-wt hooks preserved during downgrade
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** PreToolUse contains `{matcher: "Bash", command: "my-custom-hook"}` alongside stale set-hook-memory entries
- **THEN** the custom hook entry SHALL be preserved
- **AND** only `set-hook-memory` entries SHALL be removed

#### Scenario: Activity-track.sh preserved during downgrade
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** PreToolUse contains `{matcher: "Skill", command: ".claude/hooks/activity-track.sh"}`
- **THEN** the activity-track.sh entry SHALL be preserved after downgrade

#### Scenario: A project's own hook count is unchanged by the strip
- **WHEN** a project carrying both memory hooks and its own hooks is deployed to
- **THEN** the count of hooks NOT beginning with `set-hook-memory` SHALL be identical before and after

### Requirement: Backup before downgrade
The deploy script SHALL create a `.bak` backup of settings.json before removing stale entries.

#### Scenario: Backup created on downgrade
- **WHEN** stale set-hook-memory entries are detected
- **AND** the script proceeds to remove them
- **THEN** `settings.json.bak` SHALL be created before modification
