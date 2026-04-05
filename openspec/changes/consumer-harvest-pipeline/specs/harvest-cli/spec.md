# Spec: Harvest CLI

## ADDED Requirements

## IN SCOPE
- CLI tool `set-harvest` that scans registered consumer projects for unadopted changes
- Git log scanning for ISS fix commits and `.claude/` modifications
- Chronological, per-project, per-commit presentation of changes
- Classification of each commit as framework-relevant or project-specific
- Interactive adoption workflow (adopt / skip / view diff)
- Writing adopted changes to appropriate set-core locations (planning_rules.txt, templates, core code)

## OUT OF SCOPE
- Automatic adoption without user review (always interactive)
- LLM-based classification (heuristic + keyword-based)
- Modifying consumer project code
- Review findings analysis (covered by learnings-to-rules change)

### Requirement: Scan registered projects for unadopted changes

The CLI SHALL scan all registered consumer projects (from `set-project list`) for git commits not yet reviewed, ordered chronologically across projects.

#### Scenario: Scan finds ISS fix commits
- **WHEN** `set-harvest` is run without arguments
- **AND** registered project `craftbrew-run22` has commits matching `fix-iss-*` or `fix:` patterns after `last_harvested_sha`
- **THEN** each ISS fix commit is listed with: project name, date, commit message, files changed
- **AND** commits are ordered chronologically across all projects

#### Scenario: Scan finds .claude/ modifications
- **WHEN** a registered project has commits that modify files under `.claude/rules/`, `.claude/commands/`, or `.claude/skills/`
- **THEN** these commits are listed as potential template divergences
- **AND** the diff against set-core templates is shown

#### Scenario: No unadopted changes
- **WHEN** all registered projects have `last_harvested_sha` equal to their current HEAD
- **THEN** the CLI outputs "No unadopted changes found" and exits

#### Scenario: Single project scan
- **WHEN** `set-harvest --project craftbrew-run22` is run
- **THEN** only that project is scanned
- **AND** the same chronological presentation is used

### Requirement: Classify commit relevance

Each commit SHALL be classified as framework-relevant or project-specific using heuristic rules.

#### Scenario: ISS fix classified as framework-relevant
- **WHEN** an ISS fix commit modifies `package.json` build scripts, `playwright.config.ts`, `vitest.config.ts`, `middleware.ts`, or `.claude/` files
- **THEN** it is classified as `framework` relevance
- **AND** the suggested adoption target is shown (e.g., "planning_rules.txt", "templates/core/rules/", "modules/web/")

#### Scenario: ISS fix classified as project-specific
- **WHEN** an ISS fix commit only modifies app-specific files (e.g., `src/app/`, `prisma/schema.prisma`, `src/components/`)
- **AND** the fix is about specific business logic or data
- **THEN** it is classified as `project-specific`
- **AND** it is shown with a "likely skip" recommendation

#### Scenario: .claude/ modification classified as template divergence
- **WHEN** a commit modifies a `.claude/rules/set-*.md` file (deployed by set-project init)
- **THEN** the diff between the consumer version and the set-core template is shown
- **AND** it is classified as `template-divergence`

### Requirement: Interactive adoption workflow

The CLI SHALL present each unadopted change for interactive review with adopt/skip/view options.

#### Scenario: User adopts a framework-relevant fix
- **WHEN** the user selects "adopt" for a commit
- **THEN** the CLI asks which set-core file to modify (with suggested target)
- **AND** shows the relevant diff
- **AND** the user confirms the edit
- **AND** `last_harvested_sha` is updated for that project

#### Scenario: User skips a commit
- **WHEN** the user selects "skip" for a commit
- **THEN** the commit is marked as reviewed (not adopted)
- **AND** `last_harvested_sha` advances past it
- **AND** the commit is not shown again in future harvests

#### Scenario: User views full diff
- **WHEN** the user selects "view diff" for a commit
- **THEN** the full `git show` diff is displayed
- **AND** the user returns to the adopt/skip choice
