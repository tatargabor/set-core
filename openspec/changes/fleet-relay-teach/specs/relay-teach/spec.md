## IN SCOPE
- A Details control on each waiting row of the question-relay panel, opening an overlay with what is asked and what the system waits for
- A Teach control on each single-question, non-permission waiting row: the operator's answer plus an optional explanation or condition
- The project-level taught-rules file `.claude/rules/auto-answer-taught.md` in the asking project's main checkout: appended to, one entry per taught question
- Committing that one file in that project, pathspec-limited, with the project's own commit hooks running
- Answering the waiting call at once with the taught answer, as the operator's answer

## OUT OF SCOPE
- Pushing the commit (the project's own push carries it)
- Editing or deleting a taught rule from the screen (the file is plain Markdown in the project; edit it there)
- Teaching from a multi-question call, or from a permission prompt
- Rules shared across projects, or stored on the machine instead of in the project
- Answering a permission prompt automatically, by a rule or otherwise

## ADDED Requirements

### Requirement: Each waiting question can be opened in full
Every row on the question-relay panel SHALL carry a Details control. It opens an overlay above the layout that moves nothing under it and has its own close control. The overlay SHALL show:
- the agent and project, the kind (question, next step, permission) and how long the call has waited;
- every question of the call with its full text and its options;
- what the decider did with each question: proposal, tier, outcome, reason and checked references.

When the decider never saw the call, the overlay SHALL say so instead of showing an empty verdict. It SHALL also state what the call waits for: an answer on the channel, the proposal's countdown, or a hand-back to the terminal already requested.

#### Scenario: A question the decider abstained on
- **WHEN** the operator opens Details on a waiting question the decider abstained on
- **THEN** the overlay shows the question text, its options, outcome `no-decision` and the decider's one-line reason, and nothing under the overlay moves

#### Scenario: A call the decider never saw
- **WHEN** the operator opens Details on a waiting call with no decider record
- **THEN** the overlay says the decider has no record of this call and shows what the relay itself knows (agent, kind, age, question count)
- **AND** the row offers no Teach control, because the question's text is not recorded outside the decider

### Requirement: A waiting question can be answered once and taught for next time
A single-question waiting row that is not a permission prompt SHALL carry a Teach control. It opens an overlay with:
- the question;
- an answer field, pre-filled with the decider's proposal, or else the agent's recommended option, or else empty;
- the options as one-click fills;
- an optional explanation field for the condition or reason ("whenever the design change is verified, it may go live").

Saving SHALL:
- answer the waiting call at once with the answer, as the operator's own answer, through the relay's answer store;
- append the rule to the asking project's taught-rules file and commit it (next requirement).

Each step's result SHALL be reported in the overlay: answered or why not, and the commit's short sha or why there is none. A failure of one step SHALL NOT undo or block the other. For a multi-question call, a permission prompt, or a call the decider has no record of, the Teach control SHALL NOT be offered, and Details SHALL say why. The question's text is held only in the decider's private pending record: the relay's own waiting record deliberately carries no question text, and this change does not add any.

#### Scenario: Teaching an answer with a condition
- **WHEN** the operator teaches "Igen, mehet" with the explanation "ha a tervezet módosítás le van ellenőrizve" on a waiting question
- **THEN** the agent receives "Igen, mehet" at once, the project's taught-rules file gains one entry holding the question, the answer and the explanation verbatim, and the overlay shows the commit's short sha

#### Scenario: The question ended before the save
- **WHEN** the operator saves a taught rule after the call has already ended
- **THEN** the rule is still written and committed, and the overlay says the question was no longer waiting, so nothing was answered

#### Scenario: A permission prompt
- **WHEN** a permission prompt waits on the relay
- **THEN** its row has no Teach control, and its Details say a permission prompt is answered only by a person

### Requirement: Taught rules live in the project and are committed there
A taught rule SHALL be appended to `.claude/rules/auto-answer-taught.md` in the main checkout of the git repository that contains the call's working directory. For a linked worktree, that is the repository's main worktree. If the file does not exist, it SHALL be created with a short header saying what it is and that every agent session in the project loads it. Earlier entries SHALL NOT be rewritten.

Each entry SHALL hold:
- a heading from the question's first line;
- the full question text, the answer, and the explanation when one was given, all verbatim;
- the date.

It SHALL NOT hold a session id, a local path or a personal name.

The file SHALL then be committed alone, with a pathspec-limited commit that leaves anything else staged in that checkout as it was. The project's own commit hooks SHALL run. The commit SHALL NOT be pushed. When the working directory is not inside a git repository, or the main checkout cannot be resolved, the rule SHALL NOT be written, and the reason SHALL be reported. set-core's own logs SHALL record the project, the file and the commit sha, never the rule's text.

#### Scenario: A call from a linked worktree
- **WHEN** the waiting call's working directory is a linked worktree of a project
- **THEN** the rule is appended and committed in that project's main worktree, and the linked worktree is not touched

#### Scenario: Another session has staged work in the checkout
- **WHEN** the main checkout has other files staged when a rule is saved
- **THEN** the commit contains only the taught-rules file, and the other staged files are still staged afterwards

#### Scenario: A commit hook refuses
- **WHEN** the project's pre-commit hook refuses the commit
- **THEN** the rule stays in the file uncommitted, the call is still answered, and the overlay shows the hook's refusal as the reason there is no commit
