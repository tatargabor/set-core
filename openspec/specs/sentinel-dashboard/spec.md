# Capability: sentinel-dashboard (delta)

## MODIFIED Requirements

### Requirement: Sentinel tab in Dashboard
The set-web Dashboard SHALL include a "Sentinel" tab that displays sentinel event stream, findings, and allows message sending. The sentinel process management (start/stop/restart) SHALL be available from the manager project detail page, not from the sentinel tab itself.

#### Scenario: Tab visible when sentinel data exists
- **WHEN** the user opens the Dashboard and `.wt/sentinel/status.json` exists
- **THEN** a "Sentinel" tab SHALL appear in the tab bar

#### Scenario: Tab shows inactive state
- **WHEN** the Sentinel tab is active but `status.json` shows `active: false` or `last_event_at` is older than 60 seconds
- **THEN** the status bar SHALL show "Sentinel not running" with the last activity timestamp

## ADDED Requirements

### Requirement: Sentinel launch uses skill file

The manager supervisor SHALL read the sentinel skill file from the project's `.claude/commands/set/sentinel.md` and use its full content as the `claude -p` prompt, instead of the hardcoded 3-line `SENTINEL_PROMPT`.

#### Scenario: Skill file exists
- **WHEN** supervisor starts a sentinel for a project at `/path/to/project`
- **THEN** it reads `/path/to/project/.claude/commands/set/sentinel.md` and passes its content as the prompt to `claude -p --max-turns 500`

#### Scenario: Skill file not found
- **WHEN** the skill file does not exist at the expected path
- **THEN** the supervisor falls back to the existing hardcoded `SENTINEL_PROMPT` and logs a warning

#### Scenario: Spec argument injected into prompt
- **WHEN** the sentinel start request includes `{"spec": "docs/"}`
- **THEN** the supervisor appends `\n\nArguments: --spec docs/` to the skill content before passing it to `claude -p`

### Requirement: Sentinel start API accepts spec parameter

The `POST /api/projects/{name}/sentinel/start` endpoint SHALL accept an optional `spec` field in the request body.

#### Scenario: Start with spec
- **WHEN** client sends `POST /api/projects/craftbrew/sentinel/start` with body `{"spec": "docs/"}`
- **THEN** the sentinel process is started with the spec path passed as argument

#### Scenario: Start without spec
- **WHEN** client sends `POST /api/projects/craftbrew/sentinel/start` with empty body
- **THEN** the sentinel process is started without a spec argument (sentinel skill defaults apply)

### Requirement: Remove separate orchestrator start/stop API

The orchestrator start and stop endpoints SHALL be removed from the manager API. The sentinel skill manages the orchestrator lifecycle internally.

#### Scenario: Orchestrator endpoints removed
- **WHEN** client sends `POST /api/projects/{name}/orchestration/start`
- **THEN** the server returns 404 (endpoint no longer exists)
