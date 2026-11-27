## IN SCOPE
- A hook that raises an `ask` can hand its reason to the relay through one carrier call
- The permission post on the channel shows that reason and a bounded full command
- The reason store's lifetime: freshness window, single use, removal at the end of the call

## OUT OF SCOPE
- Answering a permission automatically (the auto-answer still never writes one)
- Changing the asking hook itself (the family plugin's guard adopts the carrier on its side)
- The `--text` notification mode, which stays as it is

## ADDED Requirements

### Requirement: A hook can hand its ask reason to the relay
`set-hook-notify-relay --ask-reason` SHALL read one JSON object on stdin with `session_id`,
`tool_name`, `tool_input`, `reason` and an optional `source`. While the relay switch is on, it
SHALL store the reason in the relay's state directory, keyed by the session and by a hash of
the tool name and the canonically serialised tool input. It SHALL print nothing, exit 0 in
every case, never hold or answer the session, and never log the command, the tool input or the
reason text.

#### Scenario: reason stored while the relay is on
- **WHEN** the switch is on and the carrier receives a session, a tool, its input and a reason
- **THEN** one reason record exists for that session and tool input, and the carrier exits 0 with no output

#### Scenario: nothing stored while the relay is off
- **WHEN** the switch is off
- **THEN** no reason record is written, and the carrier exits 0 with no output

#### Scenario: malformed input is ignored
- **WHEN** stdin is not a JSON object, or the session, tool name or reason is missing or empty
- **THEN** nothing is written, and the carrier exits 0

#### Scenario: no command or reason text in the log
- **WHEN** the carrier writes or skips a reason
- **THEN** its log line names the session prefix and the outcome only, never the tool input or the reason

### Requirement: The permission post shows the matching reason
When the permission relay posts a prompt, it SHALL look up a reason record for the same
session, tool name and canonically equal tool input that is at most 600 seconds old. When one
exists, the post SHALL contain the line `Why it asks (<source>): <reason>`, with the reason
bounded to 600 characters, and the record SHALL be consumed so that it is used at most once. A
reason for a different session, tool or input SHALL never be shown.

#### Scenario: a fresh matching reason appears in the post
- **WHEN** a guard stored a reason for this session and this exact Bash command 30 seconds earlier, and the permission prompt for that command is relayed
- **THEN** the post contains `Why it asks (<source>):` followed by the reason, and the reason record no longer exists

#### Scenario: a reason for another command is not shown
- **WHEN** the stored reason belongs to the same session but a different command
- **THEN** the post has no `Why it asks` line

#### Scenario: a stale reason is not shown
- **WHEN** the only matching reason is older than 600 seconds
- **THEN** the post has no `Why it asks` line, and the stale record is removed

#### Scenario: no reason keeps today's post
- **WHEN** no reason was stored
- **THEN** the post is the permission post without a `Why it asks` line

### Requirement: The permission post shows the command in full up to a bound
The permission post SHALL show the tool's command (for Bash) up to 1200 characters. A longer
command SHALL be cut at that bound and end with an explicit marker stating how many characters
were left out. Other tools keep their existing one-line summary.

#### Scenario: a long Bash command
- **WHEN** a Bash permission prompt's command is 1500 characters long
- **THEN** the post shows its first 1200 characters followed by a marker naming the 300 characters left out

#### Scenario: a short Bash command
- **WHEN** the command is 200 characters long
- **THEN** the post shows it whole, with no cut marker

### Requirement: A reason does not outlive its prompt
A reason record SHALL be removed when it is consumed by a post. Records older than the
freshness window SHALL be removed whenever the store is written or read. A reason that is never
consumed SHALL therefore never be shown after its window ends.

#### Scenario: stale records are pruned on the next write
- **WHEN** a record older than 600 seconds exists and the carrier stores a new reason
- **THEN** the old record is removed
