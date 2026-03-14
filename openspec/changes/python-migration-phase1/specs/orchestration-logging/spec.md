## ADDED Requirements

### Requirement: Structured logging configuration
The system SHALL provide a `logging_config.py` module that configures Python's `logging` framework for all orchestration modules.

The logger hierarchy SHALL use `wt_orch` as root logger name. Each module SHALL obtain its logger via `logging.getLogger(__name__)`.

#### Scenario: Default initialization
- **WHEN** `setup_logging()` is called without arguments
- **THEN** a rotating file handler is configured writing to `wt/orchestration/orchestration.log` (relative to project root)
- **AND** a stderr handler is configured for WARNING+ level
- **AND** file handler logs DEBUG+ level
- **AND** file rotation occurs at 5MB with 3 backups

#### Scenario: Custom log path
- **WHEN** `setup_logging(log_path="/custom/path.log")` is called
- **THEN** the file handler writes to the specified path
- **AND** parent directories are created if they don't exist

#### Scenario: Log format
- **WHEN** a log message is emitted
- **THEN** the format SHALL be `%(asctime)s %(levelname)s %(name)s:%(funcName)s %(message)s`
- **AND** extras dict keys are appended as `key=value` pairs when present

### Requirement: Module-level logger access
Every Python module in `lib/wt_orch/` SHALL use `logger = logging.getLogger(__name__)` for logging.

#### Scenario: Logger naming
- **WHEN** `lib/wt_orch/config.py` logs a message
- **THEN** the logger name is `wt_orch.config`

### Requirement: Extras support in log messages
The logging system SHALL support structured extras via the standard `logging` extra mechanism.

#### Scenario: Logging with extras
- **WHEN** `logger.info("dispatch_change", extra={"change": "add-auth", "attempt": 2})` is called
- **THEN** the log line includes `change=add-auth attempt=2` appended to the message

### Requirement: Backward-compatible log path
The logging system SHALL detect and use the existing orchestration log path when running inside an active orchestration session.

#### Scenario: Existing orchestration.log
- **WHEN** `STATE_FILENAME` environment variable is set
- **THEN** the log file path is derived as the same directory as the state file
- **AND** the filename is `orchestration.log`
