## ADDED Requirements

## IN SCOPE
- Correct `postcss.config.mjs` for Tailwind CSS v4 in wt-project-web nextjs template
- Correct `jest.config.ts` key name and add Prisma test environment guidance
- Add common `next.config.js` defaults (images.unoptimized)
- Extend `data-model.md` rule with worktree DB init and Prisma version guidance
- Extend `testing-conventions.md` rule with pnpm build blocking fix and node environment
- Add new `worktree-setup.md` rule covering common worktree setup issues

## OUT OF SCOPE
- spa template (non-Next.js) corrections
- Runtime enforcement of these conventions (enforcement belongs in verify gate rules)
- Automated detection of whether a deployed project uses v3 vs v4 Tailwind

### Requirement: Correct Tailwind v4 PostCSS config
The `postcss.config.mjs` template SHALL use the `@tailwindcss/postcss` plugin syntax required by Tailwind CSS v4, not the v3 `tailwindcss: {}` syntax.

#### Scenario: Deployed postcss.config.mjs works with Tailwind v4
- **WHEN** `wt-project init` deploys templates to a new project
- **THEN** `postcss.config.mjs` contains `"@tailwindcss/postcss": {}` as the plugin key
- **AND** a Next.js build does not fail with "Unknown plugin: tailwindcss"

#### Scenario: Template references correct package
- **WHEN** the template is inspected
- **THEN** the plugin key is `"@tailwindcss/postcss"` (string, not bare import)
- **AND** `autoprefixer: {}` remains as the second plugin

### Requirement: Correct Jest config key
The `jest.config.ts` template SHALL use `setupFilesAfterEnv` (not `setupFilesAfterSetup`) as the Jest configuration key for setup files that run after the test framework is installed.

#### Scenario: jest.config.ts has correct key
- **WHEN** the template is inspected
- **THEN** the key `setupFilesAfterEnv` is present
- **AND** the key `setupFilesAfterSetup` does not appear

### Requirement: next.config.js common defaults
The `next.config.js` template SHALL include `images: { unoptimized: true }` as a default, since consumer projects commonly use placeholder image paths that trigger Next.js image optimization errors.

#### Scenario: next.config.js deployed with images setting
- **WHEN** `wt-project init` deploys the nextjs template
- **THEN** `next.config.js` contains `images: { unoptimized: true }` in the config object
- **AND** a Next.js build with local/placeholder image paths does not error on image optimization

### Requirement: data-model.md worktree DB guidance
The `data-model.md` rule SHALL include a section on worktree-specific database setup, stating that `dev.db` is gitignored and each worktree requires explicit `prisma migrate deploy && prisma db seed` before running tests.

#### Scenario: Rule covers worktree DB init
- **WHEN** the `data-model.md` rule is inspected
- **THEN** it contains instructions to run `prisma migrate deploy` (not `prisma migrate dev`) in worktrees
- **AND** it notes that `prisma db seed` is required since seed data is not committed

#### Scenario: Rule covers Prisma version constraint
- **WHEN** the `data-model.md` rule is inspected
- **THEN** it documents that Prisma 7 introduced a breaking change (datasource `url` field removed)
- **AND** it recommends pinning `prisma@6` until v7 migration is explicitly planned

### Requirement: testing-conventions.md pnpm and node env guidance
The `testing-conventions.md` rule SHALL document that Prisma tests require `@jest-environment node` and that `pnpm approve-builds` is interactive — requiring `pnpm.onlyBuiltDependencies` in `package.json` for non-interactive CI/worktree environments.

#### Scenario: Rule covers Jest node environment for Prisma
- **WHEN** the `testing-conventions.md` rule is inspected
- **THEN** it contains a note that test files importing Prisma client must use `@jest-environment node` docblock comment
- **AND** it explains that the default jsdom environment causes Prisma to fail

#### Scenario: Rule covers pnpm interactive build scripts
- **WHEN** the `testing-conventions.md` rule is inspected
- **THEN** it contains guidance to add `pnpm.onlyBuiltDependencies` to `package.json`
- **AND** it explains this prevents `pnpm approve-builds` from blocking non-interactive environments

### Requirement: New worktree-setup.md rule
A new rule file `worktree-setup.md` SHALL be added to the nextjs template, path-scoped to `prisma/**` and `jest.config*` files, consolidating common worktree environment setup patterns.

#### Scenario: Rule is path-scoped and activates on relevant files
- **WHEN** the rule file is inspected
- **THEN** the YAML frontmatter contains `paths:` entries covering `prisma/**` and `jest.config*`
- **AND** the rule body covers: db init (`prisma migrate deploy && prisma db seed`), port conflict resolution, pnpm non-interactive setup

#### Scenario: Rule is deployed by wt-project init
- **WHEN** `wt-project init --project-type web` runs
- **THEN** `worktree-setup.md` appears in the project's `.claude/rules/` directory
