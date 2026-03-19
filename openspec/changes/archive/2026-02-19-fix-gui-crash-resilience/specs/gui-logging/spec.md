## ADDED Requirements

### Requirement: Worker thread logging
All background worker threads (FeatureWorker, ChatWorker, UsageWorker) SHALL use child loggers under `wt-control.workers.<name>`. Each poll cycle SHALL log at DEBUG level. Errors and timeouts SHALL log at ERROR level with the exception details.

#### Scenario: FeatureWorker poll logging
- **WHEN** the FeatureWorker completes a poll cycle
- **THEN** it logs at DEBUG level the number of projects polled and per-project results

#### Scenario: FeatureWorker subprocess failure
- **WHEN** a `set-memory` or `wt-openspec` subprocess fails or times out
- **THEN** it logs at ERROR level with the command, project name, and exception message

### Requirement: Signal handler exception logging
When a signal handler catches an exception via the error boundary, it SHALL log at ERROR level with the full traceback, the signal name, and the data that caused the error.

#### Scenario: Exception in update_status handler
- **WHEN** `update_status()` catches an exception
- **THEN** the log contains `ERROR wt-control.main_window: update_status failed:` followed by the traceback
