## ADDED Requirements

### Requirement: Directed Agent Messaging via Slash Command

The system SHALL provide a `/wt:msg` slash command for agents to send directed messages to specific agents or members.

#### Scenario: Send directed message

- **GIVEN** an agent is working in a worktree
- **WHEN** the agent runs `/wt:msg tg@tg-system-product-name/gep2-linux "Can you review the auth changes?"`
- **THEN** the message is encrypted and appended to the sender's local outbox file (`chat/outbox/{sender}.jsonl`)
- **AND** the message is delivered on the next sync cycle (within 15 seconds)

#### Scenario: Send multiline message

- **GIVEN** an agent needs to send a bug report
- **WHEN** the agent runs `/wt:msg target "BUG: Start button\nSteps: 1. Click\nExpected: Works\nActual: Fails"`
- **THEN** the multiline message is preserved in the outbox file

#### Scenario: Send to member without change_id

- **GIVEN** member "peter@laptop" has only one active worktree
- **WHEN** the agent runs `/wt:msg peter@laptop "Ready to merge"`
- **THEN** the message is delivered to peter@laptop's only active change

#### Scenario: Ambiguous target

- **GIVEN** member "peter@laptop" has multiple active worktrees
- **WHEN** the agent runs `/wt:msg peter@laptop "message"` without specifying change_id
- **THEN** the command reports available targets and asks the agent to specify `<member>/<change_id>`

#### Scenario: Recipient not found

- **WHEN** the agent runs `/wt:msg unknown@host "message"`
- **THEN** the command reports "Recipient not found" with available members listed

### Requirement: Agent Inbox via Slash Command

The system SHALL provide a `/wt:inbox` slash command for agents to read incoming messages.

#### Scenario: Read unread messages

- **GIVEN** messages exist addressed to the current agent's member/change_id
- **WHEN** the agent runs `/wt:inbox`
- **THEN** unread messages are displayed with: timestamp, sender, message text
- **AND** messages are displayed in chronological order

#### Scenario: Read all messages

- **WHEN** the agent runs `/wt:inbox --all`
- **THEN** all messages (read and unread) for this worktree are displayed

#### Scenario: No messages

- **GIVEN** no messages exist for the current agent
- **WHEN** the agent runs `/wt:inbox`
- **THEN** output shows "No unread messages"

#### Scenario: Inbox shows messages from all senders

- **GIVEN** messages from multiple senders exist across outbox files
- **WHEN** the agent runs `/wt:inbox`
- **THEN** messages from all senders are merged and sorted by timestamp

### Requirement: MCP Send Message Tool

The system SHALL expose a `send_message()` MCP tool for programmatic agent messaging. The tool only appends to a local outbox file; it does NOT commit or push (the sync cycle handles delivery).

#### Scenario: Send message via MCP

- **WHEN** agent calls `send_message(recipient="tg@linux/gep2-linux", message="PONG received")`
- **THEN** the message is encrypted and appended to the sender's local outbox file
- **AND** the tool returns confirmation: `{"status": "queued", "id": "<uuid>", "delivery": "next sync cycle (~15s)"}`

#### Scenario: Send multiline message via MCP

- **WHEN** agent calls `send_message(recipient="target", message="Line 1\nLine 2\nLine 3")`
- **THEN** the multiline text is preserved as a single message in the outbox

#### Scenario: Send fails without chat key

- **GIVEN** the sender has no chat key for the project
- **WHEN** agent calls `send_message()`
- **THEN** the tool returns error: "No chat key configured. Generate one in GUI Settings > Team."

### Requirement: MCP Inbox Tool

The system SHALL expose a `get_inbox()` MCP tool for programmatic message reading. The tool reads local outbox files only (no git operations).

#### Scenario: Get inbox messages

- **WHEN** agent calls `get_inbox()`
- **THEN** returns messages addressed to the current member/change_id
- **AND** messages are sorted by timestamp
- **AND** each message includes: id, timestamp, sender, text

#### Scenario: Get inbox since timestamp

- **WHEN** agent calls `get_inbox(since="2026-02-08T08:00:00Z")`
- **THEN** returns only messages with timestamp after the specified time

#### Scenario: Get inbox as structured data

- **WHEN** agent calls `get_inbox()`
- **THEN** returns a formatted text output with one message per line
- **AND** format: `[timestamp] sender: message_text`

### Requirement: Batched Message Delivery

The system SHALL deliver messages by piggybacking on the existing sync cycle, NOT by pushing immediately.

#### Scenario: Message queued locally

- **WHEN** `send_message()` is called
- **THEN** the message is appended to `chat/outbox/{sender}.jsonl` in the local `.set-control` worktree
- **AND** no git commit or push occurs

#### Scenario: Sync cycle delivers messages

- **GIVEN** new messages exist in `chat/outbox/{sender}.jsonl` since last commit
- **WHEN** `set-control-sync --full` runs (every 15 seconds)
- **THEN** outbox changes are included in the `git add -A`
- **AND** pushed to remote in the same commit as member status updates

#### Scenario: Multiple messages batched

- **GIVEN** agent sends 5 messages within a 15-second window
- **WHEN** the next sync cycle runs
- **THEN** all 5 messages are delivered in a single commit + push

#### Scenario: Zero additional GitHub load

- **GIVEN** 2 machines syncing every 15 seconds
- **WHEN** agents exchange 100 messages per hour
- **THEN** the number of git push operations remains identical to baseline (~480/hour)

### Requirement: Control Branch History Compaction

The system SHALL provide a mechanism to compact the set-control branch history to prevent unbounded growth.

#### Scenario: Manual compaction

- **WHEN** user runs `set-control-sync --compact`
- **THEN** all commits on the set-control branch are squashed into a single commit
- **AND** the branch is force-pushed with `--force-with-lease`

#### Scenario: Other machines recover after compaction

- **GIVEN** machine A ran `--compact` and force-pushed
- **WHEN** machine B runs `set-control-sync --full`
- **THEN** the pull fails due to diverged history
- **AND** recovery kicks in: fetch, reset --hard to remote, reapply own status
- **AND** machine B continues syncing normally

#### Scenario: Concurrent compaction prevented

- **GIVEN** machine A is running `--compact` and force-pushing
- **WHEN** machine B simultaneously tries `--compact`
- **THEN** one push succeeds (force-with-lease) and the other is rejected
- **AND** the rejected machine falls back to normal sync recovery

#### Scenario: Auto-compact on threshold

- **GIVEN** the set-control branch has more than the configured threshold commits (default: 1000)
- **WHEN** `set-control-sync --full` runs
- **THEN** compaction is triggered automatically (squash + force-push)
- **AND** a log message is emitted: "Auto-compacting set-control (N commits)"

#### Scenario: Configurable compact threshold

- **GIVEN** the team settings contain `compact_threshold` value (e.g., 50 for testing)
- **WHEN** `set-control-sync --full` runs
- **THEN** the configured threshold is used instead of the default 1000
- **AND** this allows testing compaction with small numbers of commits

#### Scenario: Manual compact override

- **WHEN** user runs `set-control-sync --compact`
- **THEN** compaction runs immediately regardless of commit count
