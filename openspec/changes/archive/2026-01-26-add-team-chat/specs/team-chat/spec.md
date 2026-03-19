# team-chat Specification

## Purpose

End-to-end encrypted 1:1 chat functionality between team members in the Control Center.

## Dependencies

- Requires: `team-sync` spec (wt-control branch, member.json, TeamWorker)

## ADDED Requirements

### Requirement: Chat Encryption

The system SHALL provide end-to-end encrypted messaging using NaCl cryptography.

#### Scenario: Generate chat keypair

- **GIVEN** the user opens Settings > Team tab
- **WHEN** the user clicks "Generate Chat Key"
- **THEN** a new NaCl keypair is generated
- **AND** the private key is stored in `~/.set-core/chat-keys/{project}.key` with 0600 permissions
- **AND** the public key is included in the next `wt-control-sync`

#### Scenario: Regenerate key with confirmation

- **GIVEN** a chat key already exists for the project
- **WHEN** the user clicks "Generate Chat Key"
- **THEN** a confirmation dialog warns that old messages will be unreadable
- **AND** only proceeds if user confirms

#### Scenario: Display key fingerprint

- **GIVEN** a chat key exists for the project
- **WHEN** the Settings > Team tab is displayed
- **THEN** the key fingerprint (first 8 hex chars of SHA256) is shown

#### Scenario: Encrypt message

- **GIVEN** user A has a keypair and user B's public key is known
- **WHEN** user A sends a message to user B
- **THEN** the message is encrypted using NaCl Box (A's private + B's public)
- **AND** a random nonce is generated for each message

#### Scenario: Decrypt message

- **GIVEN** user B receives an encrypted message from user A
- **WHEN** user B views the chat
- **THEN** the message is decrypted using NaCl Box (B's private + A's public)
- **AND** the plaintext is displayed

### Requirement: Chat CLI

The system SHALL provide a CLI tool for sending and reading chat messages.

#### Scenario: Send message via CLI

- **GIVEN** a chat key exists and recipient has a public key
- **WHEN** the user runs `wt-control-chat send <recipient> <message>`
- **THEN** the message is encrypted and appended to `.wt-control/chat/messages.jsonl`
- **AND** the change is committed and pushed to the wt-control branch

#### Scenario: Read messages via CLI

- **GIVEN** messages exist in the chat
- **WHEN** the user runs `wt-control-chat read`
- **THEN** messages to/from the current user are decrypted and displayed

#### Scenario: JSON output

- **GIVEN** messages exist
- **WHEN** the user runs `wt-control-chat read --json`
- **THEN** messages are output as a JSON array with decrypted text

#### Scenario: List members with chat keys

- **GIVEN** team members are registered
- **WHEN** the user runs `wt-control-chat list-members`
- **THEN** each member is listed with their chat key status and fingerprint

### Requirement: Chat GUI

The system SHALL provide a graphical interface for team chat.

#### Scenario: Chat button in toolbar

- **GIVEN** team sync is enabled
- **WHEN** the Control Center is displayed
- **THEN** a chat button appears in the toolbar

#### Scenario: Chat button hidden when disabled

- **GIVEN** team sync is NOT enabled
- **WHEN** the Control Center is displayed
- **THEN** the chat button is not visible

#### Scenario: Unread message indicator

- **GIVEN** there are unread messages
- **WHEN** the Control Center is displayed
- **THEN** the chat button shows bold styling

#### Scenario: Open chat dialog

- **GIVEN** the chat button is visible
- **WHEN** the user clicks the chat button
- **THEN** a ChatDialog opens with recipient selection

#### Scenario: Recipient dropdown

- **GIVEN** the ChatDialog is open
- **WHEN** the user views the recipient dropdown
- **THEN** only team members with chat public keys are listed
- **AND** the current user is NOT in the list

#### Scenario: No recipients available

- **GIVEN** no team members have chat keys
- **WHEN** the ChatDialog opens
- **THEN** a message indicates "No recipients with chat keys"
- **AND** the send functionality is disabled

#### Scenario: Message history display

- **GIVEN** a conversation exists with the selected recipient
- **WHEN** the ChatDialog displays messages
- **THEN** messages are shown with timestamp, sender ("Me" or name), and decrypted text

#### Scenario: Send message from dialog

- **GIVEN** a recipient is selected and message text is entered
- **WHEN** the user clicks Send or presses Enter
- **THEN** the message is encrypted and sent
- **AND** the input is cleared
- **AND** the message history updates

#### Scenario: Mark messages as read

- **GIVEN** messages are displayed in the ChatDialog
- **WHEN** the user views the conversation
- **THEN** messages are marked as read in the local state
- **AND** the unread indicator is cleared

### Requirement: Member Key Distribution

The system SHALL include chat public keys in member synchronization.

#### Scenario: Include chat key in member.json

- **GIVEN** the user has generated a chat key
- **WHEN** `wt-control-sync` runs
- **THEN** the member.json includes `chat_public_key` (base64) and `chat_key_fingerprint`

#### Scenario: No chat key available

- **GIVEN** the user has NOT generated a chat key
- **WHEN** `wt-control-sync` runs
- **THEN** the member.json has `chat_public_key: null`
