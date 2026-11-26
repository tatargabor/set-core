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
