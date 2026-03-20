## ADDED Requirements

## IN SCOPE
- Mapping orchestration events to Discord embeds
- In-place embed updates for progress (no spam)
- Main channel summary messages (one-liners)
- Thread-level detailed status embeds
- @mention on errors/stuck states

## OUT OF SCOPE
- Custom embed templates or user-configurable message formats
- File attachments (logs, screenshots)
- Reaction-based controls (approve/reject from Discord)
- Webhook-only mode (bot-less) — may be added later as a simpler alternative

### Requirement: Event-to-Discord mapping
The system SHALL subscribe to the orchestration event bus and translate events into Discord messages.

#### Scenario: Run start notification
- **WHEN** a `STATE_CHANGE` event indicates orchestration has started
- **THEN** a one-line message is posted to the main project channel: "🟢 <member> started Run #<N> (<count> changes)"
- **AND** a thread is created with a detailed status embed

#### Scenario: Change status update
- **WHEN** a `STATE_CHANGE` event indicates a change moved to a new status (dispatched, verifying, merging, merged, blocked)
- **THEN** the run thread's status embed is edited in-place to reflect the new state
- **AND** no new message is posted (embed edit only)

#### Scenario: Merge success
- **WHEN** a `MERGE_ATTEMPT` event indicates successful merge
- **THEN** the thread embed is updated with a checkmark for that change
- **AND** a one-line message is posted to the main channel: "✅ <member>: <change-name> merged"

#### Scenario: Agent stuck or crash
- **WHEN** a sentinel `crash` or `finding` event with severity >= "warning" is emitted
- **THEN** a message is posted to the main channel: "❌ <member>: <change-name> — <reason>"
- **AND** the configured error mention target is pinged (@role or @user)

#### Scenario: Run complete
- **WHEN** orchestration reaches terminal state (done, failed)
- **THEN** the thread embed is finalized with a summary (merged/blocked/failed counts, duration, tokens)
- **AND** a summary message is posted to the main channel: "📊 <member> Run #<N> done: <X>/<Y> merged"

### Requirement: Live status embed
The system SHALL maintain a single live-updating embed per run thread that shows current state of all changes.

#### Scenario: Embed structure
- **WHEN** the status embed is rendered
- **THEN** it contains: run number, member name, start time, elapsed time, per-change rows with status icon and progress, total token usage, agent count

#### Scenario: Embed update frequency
- **WHEN** activity.json changes for any agent in the run
- **THEN** the embed is updated at most once per 30 seconds to respect Discord rate limits

#### Scenario: Progress bar in embed
- **WHEN** a change has task progress data (e.g., 4/8 tasks complete)
- **THEN** the embed row shows a text progress bar: "████░░░░ 4/8"

### Requirement: Rate limit compliance
The system SHALL respect Discord API rate limits.

#### Scenario: Embed edit throttling
- **WHEN** multiple events arrive within a short window
- **THEN** embed updates are batched and the edit is sent at most once per 30 seconds per message

#### Scenario: Channel message throttling
- **WHEN** multiple main-channel messages would be sent within 5 seconds
- **THEN** messages are queued and sent with at least 2-second spacing
