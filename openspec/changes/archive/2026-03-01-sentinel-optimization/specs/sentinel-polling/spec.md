## MODIFIED Requirements

### Requirement: Sentinel poll loop SHALL use non-blocking background polls
The sentinel skill SHALL use single-shot background bash commands for polling instead of a long-running foreground while-loop.

#### Scenario: Normal polling cycle
- **WHEN** the sentinel starts monitoring an orchestrator
- **THEN** each poll cycle SHALL be a single bash command run with `run_in_background: true`
- **AND** the command SHALL sleep for 30 seconds, then read orchestration-state.json, then output a single EVENT line
- **AND** the LLM SHALL remain responsive to user input between polls

#### Scenario: Running state event
- **WHEN** the poll returns `EVENT:running`
- **THEN** the sentinel SHALL start the next background poll immediately
- **AND** SHALL NOT perform extended analysis or thinking

#### Scenario: Terminal state event
- **WHEN** the poll returns `EVENT:terminal`
- **THEN** the sentinel SHALL produce the completion report
- **AND** SHALL stop polling

#### Scenario: Process exit event
- **WHEN** the poll returns `EVENT:process_exit`
- **THEN** the sentinel SHALL read logs, diagnose the error, and decide whether to restart
- **AND** SHALL follow the existing crash recovery decision tree

#### Scenario: Checkpoint event
- **WHEN** the poll returns `EVENT:checkpoint`
- **THEN** the sentinel SHALL handle it according to the checkpoint reason (auto-approve periodic, ask user for others)

#### Scenario: Stale state event
- **WHEN** the poll returns `EVENT:stale`
- **THEN** the sentinel SHALL check PID liveness and log activity before deciding next action
