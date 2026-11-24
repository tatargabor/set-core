## IN SCOPE
- Posting every relay kind (question, permission prompt, finished-turn continuation) to one Discord channel
- Answers by numbered reaction, by reply text, by "number + note", and multi-select closed with ✅
- Deferring with ❌
- Answers counted from allowed users only
- An acknowledgement on the post after the answer is written
- Closing a post whose question no longer waits
- Setup, status and a test probe on one machine

## OUT OF SCOPE
- Changing the relay's envelope, answer-file shape or waiting record
- Re-posting unanswered questions on a schedule
- Content filtering or masking beyond the relay's existing audience field
- Replacing a bridge an operator already uses
- Slash commands, buttons or a gateway connection (REST only)

## ADDED Requirements

### Requirement: The bridge posts each relayed question to the channel
`set-relay-discord post` SHALL read the relay envelope from stdin and post one message per
question to the configured channel. Each message names the asking project and short session id
(the envelope's `source`), what kind of blocking point it is (from `SET_RELAY_KIND`: question,
permission, or what next), the question text, and the options numbered 1 to 5. It SHALL add the
matching number reactions, ❌, and ✅ when the question is multi-select. It SHALL keep a post
record per question (call id, key, message id, options, multi, answer directory, posted time) in
the relay's state directory. It SHALL exit 0 only when every question of the envelope was posted.
Otherwise it SHALL exit non-zero, so the relay releases the question to the terminal. A question
with more than five options SHALL list the rest as text, answerable by reply.

#### Scenario: A two-option question is posted
- **WHEN** the relay pipes an envelope with one question and two options
- **THEN** one message appears in the channel with the project, the kind, the question and options 1 and 2, the reactions 1️⃣ 2️⃣ ❌ are on it, a post record exists, and the command exits 0

#### Scenario: Discord is unreachable
- **WHEN** the post request fails or the channel refuses the bot
- **THEN** the command exits non-zero, writes no post record for the failed question, and logs the call id and the HTTP outcome, never the question text

#### Scenario: Not configured
- **WHEN** `post` runs with no token file, no channel id, or no allowed users
- **THEN** it posts nothing and exits non-zero with a line naming what is missing

### Requirement: Only allowed users answer
The bridge SHALL count reactions and replies only from the Discord user ids listed in
`relay_discord.allowed_users`. The bot's own reactions SHALL never count. With the list empty,
neither `post` nor `poll` SHALL act, because anyone who can see the channel could otherwise answer a
permission prompt.

#### Scenario: A stranger reacts
- **WHEN** a user who is not on the allowed list adds 1️⃣ to a post
- **THEN** no answer is written

### Requirement: The answer is decided from reactions and replies by fixed rules
On each run, `poll` SHALL decide every open post's answer from the allowed users' reactions and
from their replies to that post (a message whose reference is the post), in time order:

- ❌ present → no answer; the question keeps waiting (deferred).
- multi-select: the chosen options (numbered reactions, in option order) and the reply texts collect, and only ✅ closes them into one answer, joined with " · ". ✅ with nothing chosen is not an answer.
- single: the last reply wins. A reply that starts with a valid option number followed by a non-digit ("2, only from Monday") is that option plus the note. Without a reply, exactly one numbered reaction is that option. Two or more numbered reactions are not an answer.

#### Scenario: One reaction answers a single question
- **WHEN** an allowed user adds 2️⃣ to a single-select post with options "Yes" and "No"
- **THEN** the answer written is "No"

#### Scenario: A numbered reply with a note
- **WHEN** an allowed user replies "1, but only after the review" to that post
- **THEN** the answer written is "Yes — but only after the review"

#### Scenario: Free text
- **WHEN** an allowed user replies "Neither: wait for the design call"
- **THEN** the answer written is that text, verbatim

#### Scenario: Multi-select waits for ✅
- **WHEN** an allowed user adds 1️⃣ and 3️⃣ to a multi-select post but no ✅
- **THEN** nothing is written; after ✅ is added, the answer written is the two options joined

#### Scenario: Two reactions on a single question
- **WHEN** 1️⃣ and 2️⃣ are both on a single-select post and there is no reply
- **THEN** nothing is written

### Requirement: A written answer reaches the relay and is acknowledged
When `poll` decides an answer, it SHALL write `<answer dir>/<call id>__<key>.json` as
`{"valasz": "<text>"}` (private mode, written atomically), unless the file already exists. It SHALL
then add 🖥️ to the post and reply under it with what was recorded, and mark the post record
answered. A post already answered SHALL NOT be written again.

#### Scenario: The answer reaches the waiting agent
- **WHEN** the relay waits on a call and its post gets an allowed 1️⃣
- **THEN** within one poll the answer file holds option 1, the relay answers the tool call with it, and the post carries 🖥️ and a reply naming the recorded answer

#### Scenario: The fleet answered first
- **WHEN** the answer file already exists when the post would be decided (the operator answered in the fleet or the decider wrote it)
- **THEN** the bridge writes nothing, marks the post answered, and replies that it was answered elsewhere

### Requirement: A post whose question no longer waits is closed
On each run, `poll` SHALL close an open post when no waiting record in the relay's state
directory carries its call id, and the post is older than a two-minute grace. It closes by
replying that the question no longer waits (answered at the terminal, released, or timed out) and
that an answer there would not reach anyone, then marking the record closed. When the waiting
records cannot be read, it SHALL close nothing. Closed and answered records older than seven days
SHALL be removed.

#### Scenario: Answered at the terminal
- **WHEN** the operator answers the question at the agent's terminal and the relay removes its waiting record
- **THEN** the next poll after the grace replies "closed" under the post and writes no answer

#### Scenario: The waiting folder is unreadable
- **WHEN** the waiting records cannot be read
- **THEN** no post is closed in that run

### Requirement: Setup wires one machine and says what it checked
`set-relay-discord setup --channel <id> --allow <user id>… [--token-stdin]` SHALL store the token
in `~/.config/set-core/relay-discord.token` with mode 600, and the channel and allowed users in
machine-local config. It SHALL verify the token (`GET /users/@me`) and the channel (read access),
and point the relay at `set-relay-discord post`. When `question_relay.command` is the auto-answer
outbound, it points `auto_answer.forward_command` instead, so the decider keeps running in front.
When a different command is already configured, it SHALL replace it only with `--replace`, and
name the old value. It SHALL install and start a user timer that runs `poll` every minute.
`status` SHALL report the configuration, the token check, the timer, and the open and answered
post counts. `test` SHALL post one probe message and report the outcome. No subcommand SHALL print
the token.

#### Scenario: First setup
- **WHEN** setup runs with a valid token, a channel the bot can read, and one allowed user
- **THEN** the token file is mode 600, the config holds the channel and the user, the relay's command points to the bridge, the timer is active, and the output names each check that passed

#### Scenario: An existing bridge is configured
- **WHEN** setup runs on a machine whose forward command is another bridge, without `--replace`
- **THEN** nothing is rewired and the output names the existing command and the flag to replace it

### Requirement: Logs carry ids and outcomes, never text
The bridge's logs and its post records' log lines SHALL carry the call id, the key, the HTTP
status and the outcome. They SHALL never carry the question text, the option labels, or an
answer's text.

#### Scenario: A posted and answered question
- **WHEN** a question is posted and answered
- **THEN** the log lines name the call id, the key and the outcomes, and grep for the question text in the log finds nothing
