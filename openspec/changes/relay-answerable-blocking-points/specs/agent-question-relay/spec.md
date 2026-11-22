## ADDED Requirements

### Requirement: A permission prompt is answerable from the channel

While the relay is on and its target is `command`, a `PermissionRequest` hook SHALL hand the pending permission to the two-way outbound as one relay question, using the existing envelope (`{"questions": [...]}`, same fields, `key` `Q1`). The question text SHALL name the project and agent label, the tool, and a one-line summary of the call: the command for `Bash`, the path for file tools, otherwise the tool name. Its `optionsList` SHALL be exactly `["Allow", "Deny"]`, and free text SHALL stay open. The hook SHALL map the answer as follows:
- `Allow` → `{"decision": {"behavior": "allow"}}`
- `Deny` → `{"decision": {"behavior": "deny", "message": <a sentence saying the owner denied it from the relay channel>}}`
- any other text → `deny`, with that text quoted in the message.

The hook SHALL never allow on any answer other than the literal `Allow` option. The runtime routes a PreToolUse `ask` decision through the same dialog, so this SHALL cover confirmations raised by hooks as well.

#### Scenario: Allowed on the channel

- **WHEN** the relay is on, a Bash call raises a permission prompt, and the answer file carries `Allow`
- **THEN** the hook returns the allow decision, the dialog closes, and the tool runs

#### Scenario: Free text is a refusal with the owner's words

- **WHEN** the answer file carries "use the staging database instead"
- **THEN** the hook returns `deny` with a message that quotes that text, and the agent continues with it

#### Scenario: A hook-raised confirmation

- **WHEN** a PreToolUse hook returns `permissionDecision: "ask"` and the relay is on
- **THEN** the same question is posted and its answer resolves the dialog

#### Scenario: Webhook target

- **WHEN** the relay's target is `webhook`
- **THEN** the hook exits 0 with no output and the one-way notification path stays the only channel trace

### Requirement: The terminal stays live and whichever side answers first wins

While the permission question waits, the dialog SHALL remain answerable in the terminal. The hook SHALL watch the session transcript for the outcome of the pending call: a `tool_result` for a `tool_use` with the same tool name and input, appearing after the hook started. When it appears, the hook SHALL remove its waiting record, exit 0 with no output, and ignore any later channel answer. Every failure SHALL release the same way: outbound missing or non-zero, timeout (`question_relay.timeout_s`), switch turned off, or release marker. The hook's own entry timeout SHALL be above the relay timeout.

#### Scenario: Answered in the terminal first

- **WHEN** the owner picks Yes in the terminal while the channel question is open
- **THEN** within one poll interval the waiting record is gone, the hook exits without output, and a later channel answer acts on nothing

#### Scenario: Outbound fails

- **WHEN** the outbound exits non-zero
- **THEN** the hook exits at once with no output and the dialog stays in the terminal

### Requirement: A finished turn is continuable from the channel

While the relay is on and its target is `command`, an asynchronous `Stop` hook (`asyncRewake: true`) SHALL act on a turn only when the wait detector's verdict for that same turn is `DONE`. For such a turn it SHALL post one continuation question through the existing envelope. The question SHALL name the project and agent label and carry a one-paragraph summary of what the turn reported. Its `optionsList` SHALL hold one to three suggested next steps, each prefixed so the reader sees it is a suggestion, and free text SHALL stay open. On an answer, the hook SHALL exit 2 with the answer as an instruction on stderr, so that the runtime wakes the idle session with it. The summary and suggestions SHALL come from a headless classifier call (all hooks disabled, no session persisted). If that call fails, the question SHALL still be posted with no options and free text only. Any verdict other than `DONE`, or no verdict for the turn within the hook's verdict wait, SHALL end the hook with exit 0 and nothing posted.

#### Scenario: Continued from the channel

- **WHEN** a turn is classified DONE, the continuation question is posted, and the answer file carries a suggestion or free text
- **THEN** the hook exits 2 with that text, and the idle session wakes and acts on it

#### Scenario: A waiting turn is not double-asked

- **WHEN** the verdict for the turn is WAITING
- **THEN** the continuation hook posts nothing, and the re-ask path alone carries the turn

#### Scenario: The terminal is never held

- **WHEN** the continuation question is waiting
- **THEN** the session's prompt is usable in the terminal

### Requirement: A stale answer never acts

A continuation SHALL be superseded when any of these happens:
- the owner submits a prompt in that session (a `UserPromptSubmit` hook writes a supersede marker);
- a newer continuation is armed for the same session;
- the session transcript gains an assistant entry newer than the moment the continuation was armed.

A superseded continuation SHALL remove its own waiting record if the record is still its own, exit 0 without output, and log that it was superseded. The hook SHALL re-check all three conditions immediately before exiting 2. A permission question whose prompt was resolved in the terminal SHALL likewise never act. No waiting record, marker or log line SHALL hold the summary, the suggestions, the command or the answer text.

#### Scenario: The owner typed first

- **WHEN** a continuation waits and the owner types a new prompt in the terminal
- **THEN** within one poll interval the continuation's waiting record is gone, and the bridge's release check closes the post

#### Scenario: A late answer after a background wake

- **WHEN** the session was woken by something else and produced a new assistant turn, and then a channel answer arrives for the earlier continuation
- **THEN** the answer is dropped with a log line and nothing wakes the session

### Requirement: Withdrawal uses the bridge's existing release contract

Each new carrier SHALL keep exactly one waiting record per session, in the same location and shape the question hook already writes: `id` in the relay's `relay-<session>-<hash>` form, `session_id`, `project`, `cwd`, `questions: 1`, `target`, `started`, `pid`. It SHALL add a `kind` field (`permission` or `continuation`). The record's removal is the withdrawal: no carrier SHALL call the outbound to withdraw a post.

#### Scenario: Release closes the post

- **WHEN** a carrier removes its waiting record without an answer
- **THEN** the bridge's existing release check treats the post as released, with no new bridge command

### Requirement: A prompt the relay holds is not reported twice

The notification carrier SHALL post nothing for a session that has a permission or continuation waiting record. It SHALL check again after a grace period of at most 3 s, because the waiting record is written only once the outbound has accepted the question. Notifications for sessions with no such record SHALL behave as before.

#### Scenario: Permission prompt with the carrier wired

- **WHEN** a permission prompt is held by the permission carrier and the runtime's permission notification fires
- **THEN** exactly one item reaches the channel: the answerable question

### Requirement: The wire check counts the new hooks

The wire check and the unwired-project list SHALL treat these entries as part of the relay:
- the `PermissionRequest` entry (`set-hook-permission-relay`, matcher-all);
- the asynchronous `Stop` entry (`set-hook-continue-relay`, `asyncRewake: true`);
- the `UserPromptSubmit` entry (`set-hook-relay-supersede`).

Machine-local wiring (`set-relay-wire`, and registration into the fleet) SHALL add whichever of them is missing, idempotently, and never twice. `set-deploy-hooks` SHALL NOT add them: they reach a consumer's machine-local settings, never its tracked `settings.json`.

#### Scenario: A project missing the permission hook

- **WHEN** a registered project's settings at every level lack `set-hook-permission-relay`
- **THEN** the unwired list names that project with that hook, and `set-relay-wire` adds it to its machine-local settings
