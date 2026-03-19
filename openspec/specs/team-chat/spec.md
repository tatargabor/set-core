## MODIFIED Requirements

### Requirement: Chat CLI

The system SHALL provide a CLI tool for sending and reading chat messages using per-sender outbox files.

#### Scenario: Send message via CLI

- **GIVEN** a chat key exists and recipient has a public key
- **WHEN** the user runs `set-control-chat send <recipient> <message>`
- **THEN** the message is encrypted and appended to `chat/outbox/{sender-name}.jsonl`
- **AND** the change is committed and pushed to the set-control branch

#### Scenario: Read messages via CLI

- **GIVEN** messages exist across outbox files in `chat/outbox/`
- **WHEN** the user runs `set-control-chat read`
- **THEN** all outbox files are scanned for messages to/from the current user
- **AND** messages are merged, sorted by timestamp, decrypted, and displayed

#### Scenario: JSON output

- **GIVEN** messages exist
- **WHEN** the user runs `set-control-chat read --json`
- **THEN** messages are output as a JSON array with decrypted text

#### Scenario: List members with chat keys

- **GIVEN** team members are registered
- **WHEN** the user runs `set-control-chat list-members`
- **THEN** each member is listed with their chat key status and fingerprint

#### Scenario: Migrate from legacy messages.jsonl

- **GIVEN** `chat/messages.jsonl` exists but `chat/outbox/` does not
- **WHEN** `set-control-chat` runs any read or send command
- **THEN** messages are split from `messages.jsonl` into per-sender outbox files in `chat/outbox/`
- **AND** the original `messages.jsonl` is renamed to `messages.jsonl.migrated`
- **AND** migration runs only once

## ADDED Requirements

### Requirement: Per-Sender Outbox Storage

The system SHALL store chat messages in per-sender outbox files to prevent git merge conflicts.

#### Scenario: Outbox file structure

- **WHEN** a message is sent by `tg@tg-system-product-name`
- **THEN** the message is appended to `chat/outbox/tg@tg-system-product-name.jsonl`
- **AND** the file is created if it does not exist

#### Scenario: No cross-machine file conflicts

- **GIVEN** machine A sends a message (writes to `chat/outbox/user@machineA.jsonl`)
- **AND** machine B sends a message simultaneously (writes to `chat/outbox/user@machineB.jsonl`)
- **WHEN** both machines push to set-control
- **THEN** git merge succeeds without conflicts (different files modified)

#### Scenario: Read merges all outboxes

- **WHEN** messages are read for a conversation between user A and user B
- **THEN** both `chat/outbox/userA.jsonl` and `chat/outbox/userB.jsonl` are scanned
- **AND** relevant messages are merged and sorted by timestamp

#### Scenario: Outbox message format

- **WHEN** a message is written to an outbox file
- **THEN** each line is a JSON object with: `id`, `ts`, `from`, `to`, `enc`, `nonce`
- **AND** the format is identical to the legacy `messages.jsonl` line format
