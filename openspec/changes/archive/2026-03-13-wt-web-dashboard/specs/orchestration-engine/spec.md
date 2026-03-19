## MODIFIED Requirements

### Requirement: CLI entry point subcommands
The `set-orch-core` CLI SHALL support the following subcommands: `process`, `state`, `template`, and `serve`. The `serve` subcommand SHALL start the FastAPI web dashboard server. The `cli.py` module SHALL import and delegate to `server.py` for the serve command.

#### Scenario: Serve subcommand
- **WHEN** user runs `set-orch-core serve --port 7400`
- **THEN** the FastAPI server starts with API endpoints, WebSocket support, and static file serving

#### Scenario: Existing subcommands unchanged
- **WHEN** user runs `set-orch-core process check-pid --pid 1234 --expect-cmd wt-loop`
- **THEN** the behavior is identical to the pre-change implementation

#### Scenario: Help text
- **WHEN** user runs `set-orch-core --help`
- **THEN** all four subcommands (process, state, template, serve) are listed with descriptions
