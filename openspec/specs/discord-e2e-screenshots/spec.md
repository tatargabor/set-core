## ADDED Requirements

## IN SCOPE
- Post E2E test screenshots to the run's Discord thread after phase-end tests
- Handle both pass and fail cases

## OUT OF SCOPE
- E2E test execution or orchestration
- Screenshot comparison between cycles

### Requirement: E2E screenshots posted after phase-end tests
When phase-end E2E tests complete, the system SHALL post screenshots from the E2E directory to the run's Discord thread.

#### Scenario: E2E test with screenshots
- **WHEN** a phase-end E2E test completes (pass or fail)
- **AND** `SetRuntime().e2e_screenshots_dir(cycle)` contains `.png` files
- **THEN** the screenshots are posted to the run thread
- **AND** the message indicates the E2E cycle number and pass/fail result

#### Scenario: E2E test without screenshots
- **WHEN** a phase-end E2E test completes
- **AND** no screenshots exist
- **THEN** no screenshot message is posted
