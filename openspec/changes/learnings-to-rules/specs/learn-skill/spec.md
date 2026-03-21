## ADDED Requirements

## IN SCOPE
- Interactive `/set:learn` skill invokable after an orchestration run
- Reads findings from specified project or auto-detects latest run
- Presents rule candidates to user with classification and confidence
- Accepts user approval/dismissal per candidate
- Writes approved rules to the correct location (core, plugin template, or project-local)
- Optionally triggers `set-project init` to redeploy if core/plugin rules changed

## OUT OF SCOPE
- Automatic invocation (user must explicitly call `/set:learn`)
- Modifying existing rules (only creates new ones)
- Multi-project batch analysis
- WebSocket/real-time streaming of results

### Requirement: Skill invocation and project detection
The `/set:learn` skill SHALL accept an optional project name and auto-detect the latest orchestration run if not specified.

#### Scenario: Explicit project
- **WHEN** the user runs `/set:learn craftbrew`
- **THEN** the skill SHALL load findings from the `craftbrew` project's orchestration directory

#### Scenario: Auto-detect project
- **WHEN** the user runs `/set:learn` without arguments
- **AND** the current working directory is a project with orchestration data
- **THEN** the skill SHALL auto-detect the project name from the directory

#### Scenario: No orchestration data
- **WHEN** no review-findings.jsonl or orchestration state exists for the project
- **THEN** the skill SHALL report "No orchestration findings found for this project" and exit

### Requirement: Present rule candidates for approval
The skill SHALL display each rule candidate with enough context for the user to make an informed decision.

#### Scenario: Candidate presentation
- **WHEN** the analyzer produces rule candidates
- **THEN** each candidate SHALL be shown with: title, classification (core/web/project), confidence level, occurrence count, list of affected changes, and the generated rule text preview

#### Scenario: User approves candidate
- **WHEN** the user approves a candidate
- **THEN** the rule file SHALL be written to the appropriate location based on classification:
  - core → `set-core/.claude/rules/<slug>.md`
  - web → plugin template `rules/<slug>.md` (if plugin repo is accessible)
  - project → current project's `.claude/rules/<slug>.md`

#### Scenario: User dismisses candidate
- **WHEN** the user dismisses a candidate
- **THEN** the candidate SHALL be saved to memory with tag `dismissed-rule:<slug>` so it is not re-suggested in future runs

#### Scenario: User edits before accepting
- **WHEN** the user wants to modify the rule text before accepting
- **THEN** the skill SHALL allow inline editing via AskUserQuestion and write the modified version

### Requirement: Avoid re-suggesting dismissed rules
The skill SHALL check memory for previously dismissed rules before presenting candidates.

#### Scenario: Previously dismissed pattern
- **WHEN** a pattern matches a previously dismissed rule (by normalized summary)
- **THEN** the candidate SHALL be filtered out and not shown to the user

### Requirement: Post-accept deployment
After writing rule files, the skill SHALL offer to redeploy rules to consumer projects.

#### Scenario: Core rule written
- **WHEN** a rule is written to set-core's `.claude/rules/`
- **THEN** the skill SHALL suggest running `set-project init` on consumer projects to deploy the new rule

#### Scenario: Project-local rule written
- **WHEN** a rule is written to the project's local `.claude/rules/`
- **THEN** no redeploy is needed — the rule is immediately available for the next run
