# e2e-screenshot-capture

The system SHALL capture PNG screenshots during Playwright E2E test execution via the `screenshot` configuration setting, so that the existing collector pipeline produces visual artifacts without a separate capture step.

## Requirements

- **GIVEN** the decompose planning template instructs agents to create `playwright.config.ts`
- **WHEN** the agent generates the Playwright configuration
- **THEN** the config MUST include `screenshot: 'on'` in the `use` section, producing a PNG for every test (pass and fail)

## Acceptance Criteria

- The planning template text for Playwright E2E setup explicitly mentions `screenshot: 'on'` with rationale
- After an orchestration run using the updated template, `wt/orchestration/e2e-screenshots/<change>/` contains `.png` files (not only `error-context.md`)
- The `e2e_screenshot_count` field in orchestration state is > 0 for changes with E2E tests
