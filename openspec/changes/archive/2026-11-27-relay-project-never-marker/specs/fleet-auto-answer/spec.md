## ADDED Requirements

### Requirement: A project can mark questions that are never answered automatically
A project MAY commit `.claude/auto-answer-never.txt`, one regular expression per line, with blank lines and lines starting with `#` ignored. The worker SHALL read it from the repository's main checkout and from the call's own tree when that is a different worktree. The literal marker `[no-auto]` SHALL be honoured on every machine without the file. Before the decider runs, every pattern and the marker SHALL be searched, case- and accent-insensitively and unanchored, in the text and every option of every question of the call. On any hit the decider SHALL NOT run for that call, no answer SHALL be written, and the whole call SHALL be forwarded to the operator to wait for a human answer, whatever a taught rule, a standing decision or `auto_answer.allow_families` would allow. The outcome SHALL be recorded as excluded with a reason naming the file and line, or the marker, and never the matched text. A pattern that is not a valid regular expression SHALL be matched literally, with a warning.

#### Scenario: A taught rule does not outrank the project's never-rule
- **WHEN** the project's never file holds `elesben feltolt` and an agent asks "Élesben feltöltöm a köteget?" while a taught rule says such uploads may always go
- **THEN** the decider does not run, nothing is written, and the operator receives the question with the reason `never auto-answered: .claude/auto-answer-never.txt:<line>`

#### Scenario: The marker without a file
- **WHEN** a project has no never file and a question contains `[no-auto]`
- **THEN** the call is forwarded to the operator and nothing is written automatically

#### Scenario: A hit in an option
- **WHEN** the question text matches nothing but one of its options matches a never pattern
- **THEN** the whole call is forwarded without a decision

#### Scenario: No hit
- **WHEN** neither the marker nor any pattern occurs in the call
- **THEN** the decider runs exactly as before
