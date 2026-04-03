## ADDED Requirements

## IN SCOPE
- Profile ABC method for generating START.md content
- Web profile implementation with Node.js stack detection
- START.md file generation at project root
- CLAUDE.md reference section pointing to START.md
- Post-merge regeneration of START.md on main branch
- Extensible section structure (install, dev, db, test, with room for deploy/seed later)

## OUT OF SCOPE
- Non-Node.js project detection (Python, Go, etc.) — future profile implementations
- Production deploy instructions — will be added later as a section
- Docker/container setup — will be added later as a section
- CI/CD pipeline instructions

### Requirement: Profile ABC defines startup file generation
The `ProjectType` ABC SHALL define a `generate_startup_file(self, project_path: str) -> str` method that returns the full markdown content for a `START.md` file. The default implementation in `CoreProfile` SHALL return an empty string (no startup file for unknown project types).

#### Scenario: Web profile generates startup file
- **WHEN** `generate_startup_file()` is called on a `WebProjectType` instance
- **AND** the project has a `package.json` with a `dev` script
- **THEN** it SHALL return markdown content with at minimum an install and dev server section

#### Scenario: Unknown project type returns empty
- **WHEN** `generate_startup_file()` is called on a `CoreProfile` instance (no specific type)
- **THEN** it SHALL return an empty string

### Requirement: Web profile detects project stack for START.md
The `WebProjectType.generate_startup_file()` SHALL detect the project's stack from filesystem and produce structured markdown sections. Detection SHALL include:
1. Package manager (pnpm/npm/yarn/bun) from lockfile presence
2. Dev server command from `package.json` scripts
3. Database tool (Prisma/Drizzle) from dependencies
4. Test runner from `package.json` scripts
5. E2E framework (Playwright) from config file or dependencies

Each detected component becomes a section in START.md. Sections SHALL use `##` headings for extensibility.

#### Scenario: Full stack Next.js project
- **WHEN** the project has pnpm lockfile, `next` in dependencies, `prisma` in devDependencies, and `playwright.config.ts`
- **THEN** START.md SHALL contain sections: Install, Dev Server, Database, Tests, E2E Tests

#### Scenario: Minimal project with only dev server
- **WHEN** the project has only a `dev` script in package.json
- **THEN** START.md SHALL contain sections: Install, Dev Server

### Requirement: START.md has stable section structure
START.md SHALL use a consistent structure with `##` section headings. Each section SHALL contain a bash code block with the exact commands. The file SHALL have a header comment indicating it is auto-generated and will be regenerated on merge.

#### Scenario: START.md structure
- **WHEN** START.md is generated for a Next.js + Prisma project
- **THEN** it SHALL follow this structure:
  - Header: `# Application Startup` with auto-generated notice
  - `## Install` — dependency installation
  - `## Dev Server` — how to start the dev server
  - `## Database` — migration and seed commands
  - `## Tests` — unit test command
  - `## E2E Tests` — playwright setup and run

### Requirement: CLAUDE.md references START.md
The deploy process (`set-project init`) SHALL add a `## Getting Started` section to CLAUDE.md that references START.md. This section SHALL be marked as `set-core:managed`. The section SHALL instruct the reader to consult START.md for application startup commands.

#### Scenario: CLAUDE.md gets reference on init
- **WHEN** `set-project init` runs and CLAUDE.md has no `## Getting Started` section
- **THEN** it SHALL append a managed section referencing START.md

#### Scenario: CLAUDE.md already has reference
- **WHEN** `set-project init` runs and CLAUDE.md already has `## Getting Started`
- **THEN** it SHALL NOT duplicate the section

### Requirement: Post-merge regeneration
After a successful merge, the merger SHALL regenerate START.md on the main branch using the current profile's `generate_startup_file()`. This ensures START.md stays current as infrastructure changes merge.

#### Scenario: Merge adds Prisma — START.md updated
- **WHEN** a change that adds Prisma is merged to main
- **THEN** the merger SHALL regenerate START.md, which now includes the Database section

#### Scenario: No profile available — skip regeneration
- **WHEN** a merge completes but no project profile can be loaded
- **THEN** the merger SHALL skip START.md regeneration without error
