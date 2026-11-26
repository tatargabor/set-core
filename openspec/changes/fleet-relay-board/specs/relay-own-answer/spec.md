## MODIFIED Requirements

### Requirement: The operator can answer a waiting call in their own words
The relay board SHALL offer, on every waiting call that is not a permission prompt and was not handed back to the terminal, one free-text answer field per question beside its options, in the row itself. The row SHALL show each question's text and options when the decider's record holds them, and say that the text is only on the channel or in the terminal otherwise.

#### Scenario: Answering differently from the proposal
- **WHEN** the decider proposed «Yes, draft it» and the operator types "No — and do not send it after every conversation" into that row's field and presses Enter
- **THEN** the agent receives exactly that text as the answer, and the decision log records it as the operator's answer next to the proposal

#### Scenario: A call with two questions
- **WHEN** a call has two questions and the operator gives both an answer and sends
- **THEN** both answers reach the agent in their order, and the call is no longer waiting

#### Scenario: A field left empty
- **WHEN** one question of a several-question call has no answer
- **THEN** send is not available, and nothing is written

### Requirement: An own answer can also be taught
For a call with one question where teach is allowed, the board row SHALL offer "teach it too" with the optional condition field. When chosen, the row's answer — an option click or a typed answer — SHALL go through the existing teach route, so the answer is delivered and the rule is written and committed exactly as Teach does.

#### Scenario: Answer and teach
- **WHEN** the operator ticks "teach it too", adds a condition, types an own answer on the row and presses Enter
- **THEN** the agent receives the answer, and the project's taught-rules file gains the entry with that answer and condition

## ADDED Requirements

### Requirement: The relay panel shows every waiting question in full and answers it in place
Opening the fleet's question-relay panel SHALL show a large floating board, above the layout and moving nothing under it, with its own close control. The board SHALL show one row per waiting question with the agent, the call's kind and age, the question text in full, its options, and the decider's verdict with its reason and proposed answer, with no further click. Each option of a question SHALL be a control; on a call with one question that is not a permission prompt and was not handed back to the terminal, choosing an option SHALL send it at once as the operator's own answer. On a call with several questions the board SHALL send when every question has a choice. Each question SHALL also offer a free-text answer in the operator's own words. The decider's proposed answer SHALL be marked on its option, or offered as an extra choice when it is not one of the options. A permission prompt SHALL show no answer controls. A call the decider has no record of SHALL say that its text is only on the channel or in the terminal.

#### Scenario: Reading and answering without another click
- **WHEN** a single-question call waits and the operator opens the relay panel
- **THEN** the board shows the question in full, its options, and the decider's reason, and one click on an option answers the agent with it

#### Scenario: A several-question call
- **WHEN** a call with three questions waits
- **THEN** nothing is sent until each question has a choice, and then one send delivers all three answers

#### Scenario: A permission prompt
- **WHEN** the waiting call is a permission prompt
- **THEN** its row shows no option or free-text control
