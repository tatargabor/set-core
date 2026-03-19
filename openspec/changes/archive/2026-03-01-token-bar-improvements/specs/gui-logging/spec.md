## MODIFIED Requirements

### Requirement: Worker thread logging
All background worker threads (FeatureWorker, ChatWorker, UsageWorker) SHALL use child loggers under `wt-control.workers.<name>`. Each poll cycle SHALL log at DEBUG level. Errors and timeouts SHALL log at ERROR level with the exception details.

#### Scenario: FeatureWorker poll logging
- **WHEN** the FeatureWorker completes a poll cycle
- **THEN** it logs at DEBUG level the number of projects polled and per-project results

#### Scenario: FeatureWorker subprocess failure
- **WHEN** a `set-memory` or `wt-openspec` subprocess fails or times out
- **THEN** it logs at ERROR level with the command, project name, and exception message

#### Scenario: UsageWorker poll cycle logging
- **WHEN** the UsageWorker starts a poll cycle
- **THEN** it logs at DEBUG level the number of accounts being fetched
- **AND** after each account fetch, it logs the result (success with source, or failure)
- **AND** after the cycle completes, it logs before entering sleep

#### Scenario: UsageWorker API failure logging
- **WHEN** a UsageWorker API call fails across all fallback methods (curl-cffi, curl subprocess, urllib)
- **THEN** it logs at WARNING level with the account name
