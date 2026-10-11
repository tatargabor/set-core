## IN SCOPE
- A `PreToolUse` hook on `AskUserQuestion` that relays the question when the switch is on
- Per-machine configuration of the outbound: a two-way command, or a notify-only webhook
- A waiting record per relayed question, which the fleet reads
- The fleet header's switch, readiness, waiting count and per-question release
- Deploying the hook to every project

## OUT OF SCOPE
- Headless (`-p`) sessions — the runtime does not offer them the tool
- Permission prompts, plan approval, and free-text questions asked outside the tool
- Questions a work cycle writes into a task file (`work-cycle-question-outbound`)
- Any chat-side behaviour: posting, masking, audience filtering and answer collection belong
  to the outbound command
- Routing a question to another machine — each machine relays its own agents

## ADDED Requirements

### Requirement: The relay is off by default, and off changes nothing

The relay SHALL be enabled only by the machine's local configuration key
`question_relay.enabled`. When it is not `true`, the hook SHALL exit 0 with no output and
without starting any other process, so the question is shown at the terminal as it would be
without the hook.

#### Scenario: Switch off

- **WHEN** an agent calls `AskUserQuestion` and `question_relay.enabled` is unset or false
- **THEN** the hook exits 0 with no output and the picker appears at the terminal

### Requirement: An incomplete configuration is reported, never completed by guess

The relay SHALL read its outbound from local configuration only: `question_relay.target`
(`command` or `webhook`), and for `command` the command line in `question_relay.command` and
the audience in `question_relay.audience`; for `webhook` the URL in
`question_relay.webhook_url`. The framework SHALL NOT supply a default audience, command or
URL. A configuration missing a required key SHALL be reported by name, and the hook SHALL
release the question.

#### Scenario: Audience missing

- **WHEN** the relay is on with target `command` and no `question_relay.audience`
- **THEN** the hook releases the question, logs the missing key, and the fleet's readiness
  names `question_relay.audience` as missing

### Requirement: A two-way outbound receives an envelope and the answer comes back

For target `command`, the hook SHALL pass the outbound, on stdin, a JSON object
`{"questions": [...]}` with one entry per question in the tool call, each carrying `id` (the
same for every question of one call, unique per call), `key` (`Q1`, `Q2`, …), `question`,
`optionsList` (the option labels as an array, never a joined string), `multi`, `audience`
(from configuration), `source` (the project and agent label), and `valasz_tar` (the local
directory where this relay expects the answer). The hook SHALL then wait until a file
`<valasz_tar>/<id>__<key>.json` with a non-empty `valasz` field exists for every question,
and SHALL answer the tool call by returning `permissionDecision: "allow"` with the original
input plus `answers`, mapping each question's text to its answer text.

#### Scenario: Answered on the channel

- **WHEN** the relay is on, the outbound accepts the envelope, and answer files arrive for
  every question
- **THEN** the hook returns the answers and the agent continues without a picker

#### Scenario: Several questions in one call

- **WHEN** a call carries two questions and only the first answer has arrived
- **THEN** the hook keeps waiting

### Requirement: Every failure releases the question to the terminal

The hook SHALL release the question (exit 0, no output, so the picker appears) when: the
outbound command is missing or exits non-zero; the wait reaches
`question_relay.timeout_s` (default 3300 s, below the hook's own timeout); the switch is
turned off while waiting; or the waiting record's release marker is set. A released question
SHALL never be answered by the relay afterwards, and an answer arriving later SHALL be
ignored. Diagnostics SHALL name the reason and the counts, never the question text.

#### Scenario: Outbound fails

- **WHEN** the outbound command exits non-zero
- **THEN** the hook releases at once and the picker appears

#### Scenario: Switch turned off while waiting

- **WHEN** a question is waiting on the channel and the switch is turned off
- **THEN** the hook releases within its poll interval

#### Scenario: Released from the fleet

- **WHEN** the reader chooses "answer here instead" on a waiting question
- **THEN** the hook releases within its poll interval and the picker appears

### Requirement: A waiting question is recorded where the fleet can read it

While a question waits on a two-way outbound, the hook SHALL keep a waiting record under the
relay's state directory naming the session id, the project, the working directory, the number
of questions, the target, and when it started — and SHALL NOT write the question or option
text into it. The record SHALL be removed when the question is answered or released.

#### Scenario: Waiting record lifecycle

- **WHEN** a question is handed to a two-way outbound
- **THEN** a waiting record exists for its session until the answer arrives or the question
  is released, and it holds no question text

### Requirement: A webhook outbound notifies and releases

For target `webhook`, the hook SHALL post one message to `question_relay.webhook_url` and
release the question at once. By default (`question_relay.webhook_detail` unset or
`minimal`) the message SHALL name the project, the agent label and each question's short
`header`, and SHALL NOT carry the question text or options; with `full` it SHALL also carry
them. A failed post SHALL be logged and SHALL NOT delay the release.

#### Scenario: Minimal notice

- **WHEN** an agent asks with the relay on and target `webhook` at the default detail
- **THEN** the webhook receives the project, agent and headers only, and the picker appears

### Requirement: The fleet header carries the switch and what is waiting

The fleet header SHALL show the relay switch with its state. When the configuration is
incomplete, the switch SHALL be shown as not ready and name the missing keys; turning it on
SHALL be refused. While questions wait on the channel, the header SHALL show their count
without opening anything, and a list SHALL name each waiting question's project and session
age, with a control that releases it to the terminal.

#### Scenario: Turning the relay on

- **WHEN** the configuration is complete and the reader turns the switch on
- **THEN** `question_relay.enabled` becomes true and the header shows it on

#### Scenario: Not ready

- **WHEN** the configuration lacks a required key
- **THEN** the switch cannot be turned on and its title names the missing key

#### Scenario: Waiting count

- **WHEN** two questions wait on the channel
- **THEN** the closed header shows 2 waiting

### Requirement: The hook reaches every project

`set-deploy-hooks` SHALL add the relay hook as a `PreToolUse` entry with matcher
`AskUserQuestion` and a timeout of 3600 s, merged by matcher like the other base hooks, and
idempotently.

#### Scenario: Deploy twice

- **WHEN** hooks are deployed to a project twice
- **THEN** its settings hold exactly one relay hook entry
