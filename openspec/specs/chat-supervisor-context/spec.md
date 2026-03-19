## ADDED Requirements

### Requirement: Dynamic system prompt injection
The chat system SHALL build a dynamic system prompt and pass it via `--append-system-prompt` on every `claude -p --resume` invocation, so the agent receives fresh context with each message.

#### Scenario: Fresh state on every message
- **WHEN** a user sends a message via the orchestration chat
- **THEN** the system reads the current orchestration state and config, builds a context string, and passes it as `--append-system-prompt` to the claude subprocess

#### Scenario: No orchestration running
- **WHEN** no `orchestration-state.json` exists in the project
- **THEN** the system prompt includes a note "Nincs aktív orchestration" and still provides the role description and available commands

### Requirement: Role description in system prompt
The system prompt SHALL include a role description identifying the agent as a Level 2 reactive orchestration supervisor, with explicit instructions to respond in Hungarian.

#### Scenario: Agent identifies as supervisor
- **WHEN** the agent receives its first message
- **THEN** the system prompt contains the supervisor role, available actions, and language preference

### Requirement: Orchestration state summary
The system prompt SHALL include a compact summary of the current orchestration state: change names, statuses, token usage, and active process information.

#### Scenario: Running orchestration with multiple changes
- **WHEN** orchestration is active with 5 changes in various states
- **THEN** the state summary shows each change name, status (pending/running/done/failed), and token count in a readable table format under 500 tokens

#### Scenario: State file unreadable
- **WHEN** the state file exists but cannot be parsed
- **THEN** the system prompt includes "State fájl olvashatatlan" and the agent is still functional

### Requirement: Config summary in system prompt
The system prompt SHALL include key orchestration config values: max_parallel, token_budget, time_limit, test_command, smoke_command.

#### Scenario: Config available
- **WHEN** `.claude/orchestration.yaml` exists
- **THEN** the system prompt includes a condensed config summary with key directives

#### Scenario: No config file
- **WHEN** no orchestration.yaml exists
- **THEN** the config section is omitted from the system prompt

### Requirement: Available commands reference
The system prompt SHALL list the bash commands the agent can use to query and control orchestration, grouped by category (query, control, worktree, comms).

#### Scenario: Commands reference present
- **WHEN** any message is sent to the chat
- **THEN** the system prompt includes a commands reference with examples like `set-orch-core state query`, `set-orchestrate skip`, `wt-loop start`

### Requirement: Context builder as separate module
The context building logic SHALL be in a separate `lib/set_orch/chat_context.py` module with a `build_chat_context(project_path: Path) -> str` function.

#### Scenario: Module interface
- **WHEN** chat.py needs to build context
- **THEN** it calls `build_chat_context(project_path)` which returns a complete system prompt string ready to pass to `--append-system-prompt`
