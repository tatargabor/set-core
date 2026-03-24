# Web Template Gitignore

## ADDED Requirements

## IN SCOPE
- Adding .gitignore to the nextjs web template
- Including test/e2e output directories and build artifacts
- Deploying .gitignore via set-project init

## OUT OF SCOPE
- Modifying existing project .gitignore files (only template for new projects)
- Adding .gitattributes entries (already handled by run scripts)

### Requirement: Web template includes comprehensive gitignore
The nextjs web template SHALL include a `.gitignore` file that covers all generated, test, and cache directories that agents and integration gates produce during orchestration runs.

#### Scenario: Playwright artifacts are gitignored
- **WHEN** integration e2e gate generates `playwright-report/` and `test-results/` directories
- **THEN** these files do NOT appear as dirty in `git status`

#### Scenario: Template gitignore deployed by set-project init
- **WHEN** `set-project init --project-type web --template nextjs` is run
- **THEN** the `.gitignore` file is deployed to the project root

### Requirement: Gitignore covers Claude CLI cache files
The `.gitignore` SHALL include patterns for Claude CLI internal cache files (hash-named png/md files under `.claude/`) that are not part of the project source.

#### Scenario: Claude cache files are gitignored
- **WHEN** Claude CLI creates temporary files under `.claude/` (screenshots, reflections, logs)
- **THEN** these files do NOT appear as dirty in `git status`
