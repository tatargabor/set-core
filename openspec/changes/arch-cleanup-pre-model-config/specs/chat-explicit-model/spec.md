## ADDED Requirements

### Requirement: ChatSession claude invocation always passes --model

`lib/set_orch/chat.py::ChatSession._run_claude` SHALL include `["--model", self.model]` in the constructed `cmd` list on every invocation, including when `--resume <session_id>` is also present. The function SHALL NOT rely on Claude CLI's session-side model carry-over.

#### Scenario: fresh session passes --model
- **WHEN** a `ChatSession(model="opus-4-6")` runs `_run_claude(text)` without a prior session_id
- **THEN** the constructed `cmd` list contains the contiguous pair `["--model", "opus-4-6"]`
- **AND** the constructed cmd contains `--permission-mode auto`
- **AND** the constructed cmd does NOT contain `--resume`

#### Scenario: resumed session also passes --model
- **WHEN** a `ChatSession(model="opus-4-6")` with `session_id="<id>"` runs `_run_claude(text)`
- **THEN** the constructed `cmd` list contains the contiguous pair `["--model", "opus-4-6"]`
- **AND** the constructed cmd contains `--resume <id>`
- **AND** the constructed cmd does NOT contain `--permission-mode` (resume inherits from session)

#### Scenario: model change between resumes is honored
- **WHEN** a `ChatSession` is created with `model="sonnet"`, `session_id` set, and `self.model` is later mutated to `"opus-4-6"` before `_run_claude` runs again
- **THEN** the resulting cmd contains `--model opus-4-6` (the current `self.model`), not the original `"sonnet"`
