## IN SCOPE
- What the "what next?" post says about the session's original goal
- A fixed option to keep going toward that goal, and the instruction it wakes the session with
- Reading the session's opening prompt for the suggester

## OUT OF SCOPE
- When a continuation is posted (still only after a DONE verdict)
- The auto-answer's rules for choosing an option
- Storing goals anywhere

## ADDED Requirements

### Requirement: The continuation post names the session's original goal
The continuation SHALL pass the suggester the session's opening prompt, bounded to 800
characters, beside the final message. The opening prompt is the first user entry in the
transcript whose content is the user's own text rather than a tool result or a system or
command wrapper. When the suggester returns a `GOAL:` line, the post SHALL show
`Started for: <goal>` (at most 200 characters) and ask whether that goal and the reason the
session was started still hold. Without a goal, the post SHALL ask whether anything is left of
what the session was started for. The opening prompt and the goal SHALL NOT be logged or
persisted outside the envelope handed to the outbound.

#### Scenario: a goal is shown
- **WHEN** the session's opening prompt asked for a feature and the suggester returns `GOAL: ship the export feature`
- **THEN** the post contains `Started for: ship the export feature` and asks whether it still holds

#### Scenario: no goal returned
- **WHEN** the suggester returns no `GOAL:` line
- **THEN** the post has no `Started for:` line and still asks whether anything is left to continue

#### Scenario: the opening prompt skips tool results and wrappers
- **WHEN** the transcript starts with a command wrapper entry and a tool result before the user's first own text
- **THEN** the suggester receives that first own text as the opening prompt

### Requirement: The continuation offers keeping going toward the goal
The continuation post's first option SHALL be the fixed option
`→ Keep going toward the original goal`, followed by at most three suggestions. When that option
is the answer, the session SHALL be woken with an instruction to re-read its original goal and
the reason it was started. If they still hold and work is left, it carries on with the next
step. Otherwise it states why in one line and stops. The writer note for an auto-written answer
SHALL be kept.

#### Scenario: the fixed option comes first
- **WHEN** a continuation is posted with two suggestions
- **THEN** the options are the fixed keep-going option followed by the two suggestions

#### Scenario: picking keep going
- **WHEN** the owner answers with the keep-going option
- **THEN** the wake instruction tells the session to re-check its original goal and reason, continue if they hold and work is left, and otherwise say why and stop

#### Scenario: an auto-written keep going names its writer
- **WHEN** the auto-answer writes the keep-going option
- **THEN** the wake instruction says the auto-answer chose it on the owner's behalf
