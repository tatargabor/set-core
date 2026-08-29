## ADDED Requirements

### Requirement: The dead are purgeable from where they are counted

Where the strip reports accounts that did not answer, it SHALL offer the purge action for
exactly those accounts. The action SHALL require an explicit confirmation that names the
accounts and states that their stored credentials will be deleted, and after a confirmed
successful purge the strip SHALL refresh rather than wait for its next poll.

The wording SHALL say the accounts did not answer — never that their credentials expired.
Unreachable is also what a network failure looks like, and the strip does not know which
of the two it is looking at; the confirmation is the human decision that stands in for
that missing knowledge.

The action SHALL be present only while at least one account did not answer, and SHALL
draw no more attention than the count it serves: an offering, not a banner.

#### Scenario: Accounts did not answer

- **WHEN** the strip is showing the accounts that did not answer
- **THEN** the purge action is reachable from that line

#### Scenario: Nothing is silent

- **WHEN** every account answered
- **THEN** no purge action is offered anywhere in the strip

#### Scenario: The confirmation

- **WHEN** the purge action is triggered
- **THEN** a confirmation names the accounts and states that their stored credentials
  will be deleted, and nothing is removed until it is accepted

#### Scenario: A confirmed purge succeeds

- **WHEN** a confirmed purge completes successfully
- **THEN** the strip refreshes its measurement rather than waiting for the next poll
