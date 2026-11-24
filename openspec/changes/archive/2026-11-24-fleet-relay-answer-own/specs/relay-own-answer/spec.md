## IN SCOPE
- An answer… control on each waiting question and continuation row of the relay panel
- Free-text answers, one per question, with the options as fills
- Sending them as the operator's answer, at once
- An optional "also teach it" for a single-question call where teach is allowed

## OUT OF SCOPE
- Permission prompts (they keep Allow/Deny on the channel and the terminal)
- Changing what the decider proposes or how it decides
- Editing an answer after it was sent

## ADDED Requirements

### Requirement: The operator can answer a waiting call in their own words
The relay panel SHALL offer an answer… control on every waiting call that is not a permission
prompt. It SHALL open an overlay above the panel, with its own close control, that moves
nothing under it. The overlay SHALL show each question's text and options when the decider's
record holds them, and the question count otherwise. It SHALL hold one empty free-text field
per question; clicking an option fills that field with it.

#### Scenario: Answering differently from the proposal
- **WHEN** the decider proposed «Yes, draft it» and the operator opens answer…, types "No — and do not send it after every conversation", and sends
- **THEN** the agent receives exactly that text as the answer, and the decision log records it as the operator's answer next to the proposal

#### Scenario: A call with two questions
- **WHEN** a call has two questions and the operator fills both fields and sends
- **THEN** both answers reach the agent in their order, and the call is no longer waiting

#### Scenario: A field left empty
- **WHEN** one of the fields is empty
- **THEN** send is not available, and nothing is written

### Requirement: An own answer is the operator's answer, delivered at once
Sending SHALL write each answer to the relay's answer store for the waiting call, the same
store the chat bridge writes, so the waiting carrier answers the agent within one poll. The
route SHALL refuse a call that is no longer waiting, one already handed back to the terminal,
a permission prompt, and a count of answers that differs from the call's question count, each
with its reason. The exclusions and the window of automatic answers SHALL NOT apply: this is
the person answering. Logs SHALL carry the call id and counts only, never the text.

#### Scenario: The call ended before send
- **WHEN** the question was answered in the terminal before the operator pressed send
- **THEN** nothing is written and the overlay says the question is no longer waiting

#### Scenario: A permission prompt
- **WHEN** the waiting call is a permission prompt
- **THEN** its row has no answer… control, and the route refuses it

### Requirement: An own answer can also be taught
For a call with one question where teach is allowed, the overlay SHALL offer "also teach it for
next time" with the optional condition field. When chosen, sending SHALL go through the
existing teach route, so the answer is delivered and the rule is written and committed exactly
as Teach does.

#### Scenario: Answer and teach
- **WHEN** the operator types an own answer, ticks "also teach it", adds a condition and sends
- **THEN** the agent receives the answer, and the project's taught-rules file gains the entry with that answer and condition
