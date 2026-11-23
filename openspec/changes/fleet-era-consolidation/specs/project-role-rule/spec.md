## IN SCOPE
- A private, machine-local role file the operator maintains: one entry per registered project
- A generated rule file per registered project, loaded by Claude Code at session start
- The visibility rule: a public repository's rule names only public siblings
- The archived-project notice inside that rule
- Keeping the generated rule out of every commit

## OUT OF SCOPE
- Publishing the full project map anywhere
- Enforcing the role (blocking edits in an archived project) — the rule informs, the owner decides
- Generating roles automatically from code analysis

## ADDED Requirements

### Requirement: Roles come from a private, machine-local file
The role source SHALL be a file under the user's set-core configuration directory, outside
every repository, holding per registered project: a one-line role, what it owns, what it
depends on, and what depends on it. set-core SHALL ship only its schema and an empty example,
never filled-in entries.

#### Scenario: No role file
- **WHEN** the role file does not exist
- **THEN** `set-project roles` writes no rule, reports "no role file" with the path it looked for, and exits 0

#### Scenario: A project without an entry
- **WHEN** a registered project has no entry in the role file
- **THEN** its rule is generated with the registry facts only (path, visibility, archived) and says the role is not described

### Requirement: One generated rule per registered project
`set-project roles` SHALL write `.claude/rules/project-role.md` in every registered project
whose path exists, and `set-project init` and `set-project archive` SHALL regenerate it for the
project they act on. The file SHALL carry a generated-by marker, and a regeneration SHALL
overwrite only a file carrying that marker.

#### Scenario: A hand-written file in the way
- **WHEN** `.claude/rules/project-role.md` exists without the generated-by marker
- **THEN** it is left unchanged and the run reports the path as skipped

#### Scenario: Regeneration is idempotent
- **WHEN** `set-project roles` runs twice with an unchanged role file
- **THEN** the second run changes no byte in any project

### Requirement: The rule never enters a commit
The generated rule SHALL be listed in the repository's `.git/info/exclude` when it is
written, so `git status` stays clean and no commit can carry it.

#### Scenario: Written into a clean repository
- **WHEN** the rule is written into a repository with a clean working tree
- **THEN** `git status --porcelain` is still empty

### Requirement: A public repository names only public siblings
For a project whose remote is public, the rule SHALL name only related projects that are
themselves public; a private relation SHALL be counted, not named ("2 private projects depend
on this one"). Visibility SHALL be decided the same way the leak scan decides it, and an
undecidable visibility SHALL be treated as private.

#### Scenario: A public repository with a private consumer
- **WHEN** a public project has one public and one private dependent in the role file
- **THEN** its rule names the public one and says "1 private project" for the other

#### Scenario: Visibility cannot be decided
- **WHEN** a related project's visibility cannot be determined (offline, non-GitHub remote)
- **THEN** it is counted as private and not named

### Requirement: An archived project tells the agent not to develop it
For a registry entry marked archived, the rule SHALL open with a notice that the project is
archived, that no new development is to be started in it, and which project replaced it when
the role file names one.

#### Scenario: Opening an archived project
- **WHEN** an agent starts a session in a project whose registry entry is archived
- **THEN** the first lines of its role rule say the project is archived and not to be developed

#### Scenario: Un-archiving
- **WHEN** a project's archived flag is cleared and the rule is regenerated
- **THEN** the notice is gone
