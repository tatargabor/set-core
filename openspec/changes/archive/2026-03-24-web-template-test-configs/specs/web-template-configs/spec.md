# Spec: web-template-configs

## IN SCOPE
- Playwright config template with PW_PORT env var
- Vitest config template replacing Jest
- Removal of Tailwind v3 JS config
- Discord webhook config in orchestration template
- manifest.yaml update

## OUT OF SCOPE
- Runtime gate logic changes (already done in prior commits)
- Profile `e2e_gate_env()` method (already implemented)
- E2E scaffold runner changes

## ADDED Requirements

### Requirement: Playwright config template

The web template SHALL include a `playwright.config.ts` that uses `process.env.PW_PORT` for port isolation.

#### Scenario: Deployed config uses PW_PORT
- WHEN `set-project init --project-type web` deploys the template
- THEN `playwright.config.ts` exists in the project root
- AND it reads `PW_PORT` env var with fallback to 3000
- AND `webServer.command` uses the same port
- AND `baseURL` uses `http://localhost:${port}`
- AND `screenshot` is set to `"on"`

### Requirement: Vitest config template

The web template SHALL include `vitest.config.ts` instead of `jest.config.ts`.

#### Scenario: Vitest config deployed
- WHEN `set-project init --project-type web` deploys the template
- THEN `vitest.config.ts` exists in the project root
- AND it excludes `tests/e2e/**` from Vitest runs
- AND `jest.config.ts` is NOT deployed

### Requirement: No Tailwind JS config

The web template SHALL NOT include `tailwind.config.ts` (Tailwind v4 uses CSS-based config).

#### Scenario: Tailwind config not deployed
- WHEN `set-project init --project-type web` deploys the template
- THEN `tailwind.config.ts` does NOT exist in the deployed files

### Requirement: Discord config in orchestration template

The orchestration config template SHALL include a commented Discord notification section.

#### Scenario: Discord section present
- WHEN the orchestration config is generated for a web project
- THEN the config YAML contains a `discord` section with `webhook_url` and `channel_name` fields
