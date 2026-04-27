# Screenshot Gallery Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Screenshot gallery for smoke and E2E results
Display Playwright screenshots inline in the dashboard, organized by change and attempt.

#### Scenario: View smoke screenshots for a change
- **WHEN** a change has `smoke_screenshot_count > 0` and `smoke_screenshot_dir` set
- **THEN** a camera icon appears next to the smoke gate badge
- **THEN** clicking it opens an inline gallery showing all PNG files from the screenshot directory
- **THEN** images are displayed as thumbnails with click-to-enlarge

#### Scenario: View phase-end E2E screenshots
- **WHEN** phase-end E2E results exist with screenshots
- **THEN** an E2E screenshots section appears in the dashboard (below changes table or in a dedicated tab)
- **THEN** screenshots are organized by cycle number

#### Scenario: No screenshots available
- **WHEN** `smoke_screenshot_count` is 0 or the directory is empty
- **THEN** no camera icon is shown, no gallery available

### Requirement: Screenshot API endpoint
Backend serves screenshot file listings and images.

#### Scenario: List screenshots for a change
- **WHEN** `GET /api/{project}/changes/{name}/screenshots` is called
- **THEN** returns JSON with `smoke: [{path, name}]` and `e2e: [{path, name}]` arrays

#### Scenario: Serve screenshot image
- **WHEN** a screenshot image path is requested via the static mount
- **THEN** the PNG file is served with correct content-type
- **THEN** paths outside the project's `set/orchestration/` directory are rejected
