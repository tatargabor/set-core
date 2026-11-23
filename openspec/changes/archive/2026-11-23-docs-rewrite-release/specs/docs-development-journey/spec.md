# Spec: docs-development-journey

## ADDED Requirements

## IN SCOPE
- Development statistics showcase (commits, LOC, specs, runs)
- Key milestones timeline extracted from git history
- Lessons learned section from E2E benchmark reports
- Architecture evolution narrative (3 repos → monorepo, manual → autonomous)
- Benchmark highlights (minishop zero-intervention, craftbrew 15-change)

## OUT OF SCOPE
- Full changelog (too granular)
- Per-commit details
- Internal post-mortem details (keep high-level insights only)

### Requirement: Development statistics showcase

The documentation SHALL include a section with quantitative metrics demonstrating the system's maturity and scope.

#### Scenario: Stats section shows key numbers
- **WHEN** a visitor reads the development journey section
- **THEN** they see: total commits (1,287), capability specs (363), Python LOC (44K), TypeScript LOC (12K), E2E runs completed, and test count

### Requirement: Architecture evolution narrative

The documentation SHALL describe how the system evolved, showing the progression from simple to sophisticated.

#### Scenario: Evolution milestones visible
- **WHEN** reading the journey section
- **THEN** key architectural transitions are described: worktree tools → orchestration engine → autonomous sentinel → quality gates → modular plugin system → web dashboard

### Requirement: Benchmark highlights

The documentation SHALL showcase results from real autonomous orchestration runs.

#### Scenario: Minishop benchmark featured
- **WHEN** reading benchmark highlights
- **THEN** the minishop-run4 results are shown: 6/6 changes merged, 0 human interventions, 1h45m, 38 tests + 32 E2E tests

#### Scenario: Visual proof with screenshots
- **WHEN** benchmark results are presented
- **THEN** they include dashboard screenshots showing the completed orchestration and the built application

### Requirement: Lessons learned

The documentation SHALL include key production insights discovered through real E2E runs.

#### Scenario: Actionable lessons presented
- **WHEN** reading the lessons section
- **THEN** each lesson has: what happened, what was learned, and what was fixed
