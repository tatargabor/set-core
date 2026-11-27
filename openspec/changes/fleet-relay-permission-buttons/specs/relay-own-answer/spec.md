## MODIFIED Requirements

### Requirement: An own answer is the operator's answer, delivered at once
Sending SHALL write each answer to the relay's answer store for the waiting call, the same
store the chat bridge writes, so the waiting carrier answers the agent within one poll. The
route SHALL refuse a call that is no longer waiting, one already handed back to the terminal,
and a count of answers that differs from the call's question count, each with its reason. For
a permission prompt the route SHALL accept only exactly one answer that is `Allow` or `Deny`
(surrounding whitespace ignored) with no teach item, and SHALL refuse anything else with its
reason and write nothing. The exclusions and the window of automatic answers SHALL NOT apply:
this is the person answering. Logs SHALL carry the call id and counts only, never the text.

#### Scenario: The call ended before send
- **WHEN** the question was answered in the terminal before the operator pressed send
- **THEN** nothing is written and the overlay says the question is no longer waiting

#### Scenario: A permission prompt
- **WHEN** the waiting call is a permission prompt and the answer is not exactly `Allow` or `Deny`, or carries a teach item
- **THEN** the route refuses it and nothing is written

#### Scenario: A permission prompt answered with a fixed answer
- **WHEN** the waiting call is a permission prompt and the answer is `Allow` or `Deny`
- **THEN** that word is written to the relay's answer store, and the hook turns it into the same decision the channel's button would

## ADDED Requirements

### Requirement: The relay board answers a permission prompt with Allow or Deny
On a permission prompt that was not handed back to the terminal, the relay board SHALL show
exactly two controls, **Allow** and **Deny**, and no option, free-text or teach control. One
click SHALL send that word at once as the operator's own answer and the row SHALL report it as
sent. The row's status SHALL keep saying the prompt is never answered automatically.

#### Scenario: The operator denies from the board
- **WHEN** a permission prompt waits on the relay and the operator clicks Deny on its row
- **THEN** `Deny` is written to the answer store for that call and the row shows it as answered

#### Scenario: Handed back to the terminal
- **WHEN** the permission prompt was handed back to the terminal
- **THEN** its row shows neither button
