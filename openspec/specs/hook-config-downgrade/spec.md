## Requirements

### Requirement: Detect stale set-hook-memory entries in PreToolUse
The deploy script SHALL identify `set-hook-memory PreToolUse` entries in the PreToolUse array that are not part of the canonical config. The canonical config has zero `set-hook-memory` entries in PreToolUse (only `activity-track.sh` for Skill matcher).

#### Scenario: Project with 6 PreToolUse memory matchers
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json contains PreToolUse entries with command `set-hook-memory PreToolUse` for matchers Read, Edit, Write, Bash, Task, Grep
- **THEN** all 6 entries SHALL be identified as stale

#### Scenario: Project with only Skill activity-track matcher
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** PreToolUse contains only `{matcher: "Skill", command: ".claude/hooks/activity-track.sh"}`
- **THEN** no stale entries SHALL be detected in PreToolUse

### Requirement: Detect stale set-hook-memory entries in PostToolUse
The deploy script SHALL identify `set-hook-memory PostToolUse` entries in the PostToolUse array whose matcher is not in the canonical set (`Read`, `Bash`).

#### Scenario: Project with 6 PostToolUse memory matchers
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** settings.json contains PostToolUse entries with command `set-hook-memory PostToolUse` for matchers Read, Edit, Write, Bash, Task, Grep
- **THEN** Edit, Write, Task, Grep entries SHALL be identified as stale
- **AND** Read, Bash entries SHALL NOT be identified as stale

### Requirement: Remove only set-hook-memory stale entries
The deploy script SHALL remove stale entries surgically — only entries whose command matches `set-hook-memory PreToolUse` or `set-hook-memory PostToolUse` AND whose matcher is not in the canonical set.

#### Scenario: Non-wt hooks preserved during downgrade
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** PreToolUse contains `{matcher: "Bash", command: "my-custom-hook"}` alongside stale set-hook-memory entries
- **THEN** the custom hook entry SHALL be preserved
- **AND** only `set-hook-memory` entries SHALL be removed

#### Scenario: Activity-track.sh preserved during downgrade
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** PreToolUse contains `{matcher: "Skill", command: ".claude/hooks/activity-track.sh"}`
- **THEN** the activity-track.sh entry SHALL be preserved after downgrade

### Requirement: Backup before downgrade
The deploy script SHALL create a `.bak` backup of settings.json before removing stale entries.

#### Scenario: Backup created on downgrade
- **WHEN** stale set-hook-memory entries are detected
- **AND** the script proceeds to remove them
- **THEN** `settings.json.bak` SHALL be created before modification
