## ADDED Requirements

### Requirement: A declared hand-over in a finished turn is read, and NEED INPUT is a prompt

The framework SHALL read the last text of a finished turn for the hand-over marker — a line that
starts, after optional whitespace, quote or markdown emphasis characters, with `NEED INPUT:` or
`ALL DONE:` — and SHALL carry it as the agent field `handover` (`need_input`, `all_done`, or null).

The marker SHALL be read only when the session log holds no outstanding call and the last text in
the tail was said by the agent. A `need_input` hand-over SHALL set the attention class to `prompt`,
with the wait measured as for any other finished turn. An `all_done` hand-over SHALL leave the
attention class unchanged. The marker's text SHALL NOT be logged or persisted.

#### Scenario: A finished turn that asks for input is a prompt

- **WHEN** the log holds no outstanding call, the record says `idle`, and the last assistant text
  contains a line starting `NEED INPUT:`
- **THEN** `handover` SHALL be `need_input`
- **AND** the attention class SHALL be `prompt`

#### Scenario: Markdown emphasis does not hide the marker

- **WHEN** the line reads `**NEED INPUT:** …`
- **THEN** `handover` SHALL be `need_input`

#### Scenario: A reply from the person clears it

- **WHEN** a user text follows the agent's `NEED INPUT:` line in the log
- **THEN** `handover` SHALL be null

#### Scenario: The marker mid-sentence is not a hand-over

- **WHEN** the text mentions `NEED INPUT:` inside a line that starts with other words
- **THEN** `handover` SHALL be null

#### Scenario: A running turn is not a hand-over

- **WHEN** the last assistant text carries `NEED INPUT:` and a tool call is outstanding
- **THEN** `handover` SHALL be null and the state SHALL stay `working`

#### Scenario: ALL DONE changes no class

- **WHEN** the last assistant text of a finished, idle turn carries a line starting `ALL DONE:`
- **THEN** `handover` SHALL be `all_done`
- **AND** the attention class SHALL stay `input`
