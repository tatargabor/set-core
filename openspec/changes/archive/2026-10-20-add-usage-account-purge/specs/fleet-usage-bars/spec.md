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

## MODIFIED Requirements

### Requirement: The strip belongs to the header, because the quota is not a per-agent fact

The fleet screen SHALL draw account usage on its header's own line, and SHALL NOT attach a
consumption mark to an agent tab or tile.

At rest it SHALL carry one mark per account that answered with figures — the bars, preceded by
a short label naming that account — and SHALL make each mark's account recoverable without
navigating away. The accounts by name, and every window including any model-scoped one, SHALL
be reachable in one step from that mark.

The resting form stays compact, but not wordless: several accounts draw the same-shaped pair
of bars, and pairs that cannot be attributed are names the reader must reconstruct from a
tooltip to use at all. Asked for by the user on 2026-08-29 — a word, an icon or a letter
before the bars. The label is the shortest text that distinguishes the accounts: for an email,
the domain's first label (`gmail`, `itline`), because the shared local part distinguishes
nothing; otherwise the name, capped. Full names, percentages and sentences still live only on
the mark's description and in the detail view — the 2026-08-27 compaction
(*"ez nagyon sok helyet elvisz … szovegek nem kellenek"*) survives as everything the label
does not say.

The reason the marks are per account and not per tab is a measurement, not a layout
preference. A per-tab mark would claim that this agent consumed this share, and that claim
cannot be supported: of the 40 most recent session transcripts on this machine, measured
2026-08-27, **4 carried an owning-account identity and 36 did not**, and the stored account
entries carry no account identifier to join on at all. A mark drawn on 4 tabs out of 40 is not
a coverage gap the reader can see — it looks exactly like 36 agents consuming nothing.

#### Scenario: More than one account answered with figures

- **WHEN** the machine holds several usage-capable accounts and more than one answered
- **THEN** the header carries one mark per answering account, each preceded by its short
  label, and each still names the account it stands for in full in its description

#### Scenario: Two accounts that would draw identical bars

- **WHEN** two accounts with different names rest beside each other
- **THEN** their labels differ, so the pairs are attributable without opening anything

#### Scenario: An agent tab is drawn

- **WHEN** the fleet screen renders its agent tabs and tiles
- **THEN** no account-consumption mark appears on any of them

#### Scenario: The reader asks for the detail

- **WHEN** the reader opens the detail from that mark
- **THEN** every account is listed by name with every one of its windows, and the detail does not
  displace the header or the screen below it
