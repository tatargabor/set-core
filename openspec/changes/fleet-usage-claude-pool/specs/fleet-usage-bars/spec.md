## MODIFIED Requirements

### Requirement: The strip belongs to the header, because the quota is not a per-agent fact

The fleet screen SHALL draw account usage on its header's own line, and SHALL NOT attach a
consumption mark to an agent tab or tile.

At rest it SHALL carry one mark per subscription that answered with figures — the bars, preceded
by a short label naming that subscription — and SHALL make each mark's account recoverable
without navigating away. The accounts by name, and every window including any model-scoped one,
SHALL be reachable in one step from that mark.

A Claude subscription reached both through a browser session and through a CLI account is ONE
subscription: the two records carry the same name and the same figures, and drawing both reads
as two subscriptions. They SHALL be drawn as one mark and one detail row, keeping the better
outcome (measured over unmeasured over unreachable). The detail row SHALL say which kinds it was
reached through.

The label is the shortest text that tells the drawn subscriptions apart. For an email it is the
domain's first label (`gmail`, `acme`). Where two drawn emails share that label, the tokens of the
local part that the group does not share are appended (`acme`, `acme team`). The label is
computed over every Claude account in the measurement, never per account in isolation, because
distinctness is a property of the set — and a label that changed whenever a neighbour went
silent would be a second thing to relearn. Full names, percentages and sentences still live only on the mark's
description and in the detail view.

The reason the marks are per account and not per tab is a measurement, not a layout
preference. A per-tab mark would claim that this agent consumed this share, and that claim
cannot be supported: of the 40 most recent session transcripts on this machine, measured
2026-08-27, **4 carried an owning-account identity and 36 did not**, and the stored account
entries carry no account identifier to join on at all.

#### Scenario: More than one account answered with figures

- **WHEN** the machine holds several usage-capable accounts and more than one answered
- **THEN** the header carries one mark per answering subscription, each preceded by its short
  label, and each still names the account it stands for in full in its description

#### Scenario: Two accounts that would draw identical bars

- **WHEN** two accounts with different names rest beside each other
- **THEN** their labels differ, so the pairs are attributable without opening anything

#### Scenario: Two emails on one domain

- **WHEN** `user@acme.example` and `user.team@acme.example` are both drawn
- **THEN** their labels are `acme` and `acme team`

#### Scenario: One subscription reached two ways

- **WHEN** a browser-session account and a CLI account carry the same email
- **THEN** one mark is drawn for it, and its detail row names both kinds

#### Scenario: An agent tab is drawn

- **WHEN** the fleet screen renders its agent tabs and tiles
- **THEN** no account-consumption mark appears on any of them

#### Scenario: The reader asks for the detail

- **WHEN** the reader opens the detail from that mark
- **THEN** every account is listed by name with every one of its windows, and the detail does not
  displace the header or the screen below it

## ADDED Requirements

### Requirement: The Claude pool reads the week against the time that has passed

*Asked for by the owner on 2026-11-08: «kellene claude-ra egy közös mutató hogy összevonva őket
hány %-on állunk 7 napos időarányosan».*

The strip SHALL lead the Claude subscriptions with one pool mark. The mark counts every Claude
subscription that has a measured, account-wide 7-day window with a known elapsed share. It SHALL
draw the mean consumption above the mean elapsed share, as the two stripes every window uses. It
SHALL carry one number: the summed consumption divided by the summed elapsed share, which is the
share of the pro-rata budget spent so far.

Each subscription SHALL count as one equal share, because no source reports plan sizes. The
mark's description SHALL say so, and SHALL name every Claude subscription it left out and why.
The pool SHALL be toned amber above 100 % (spending ahead of time) and neutral otherwise. It SHALL
NOT use the critical colour, which belongs to a severity a source reports. Without at least one
countable subscription, no pool mark is drawn.

#### Scenario: Two subscriptions behind and ahead of time

- **WHEN** one subscription has spent 20 % with 50 % of its week run, and another 60 % with 40 % run
- **THEN** the pool draws 40 % consumed over 45 % elapsed and reads 89 %

#### Scenario: A subscription without figures

- **WHEN** a Claude subscription answered without a weekly figure, or did not answer
- **THEN** the pool leaves it out and its description names it; the header's existing counts
  still carry it

#### Scenario: Ahead of time

- **WHEN** the pooled consumption exceeds the pooled elapsed share
- **THEN** the number is above 100 % and the mark is amber, never the critical colour

### Requirement: The browser sessions can be rescanned from the strip

The strip's detail SHALL offer a rescan of the browser's Claude sessions. While the scan runs,
the control SHALL say so. When it finishes, the strip SHALL show the measurement taken
immediately afterwards and SHALL name the sessions found. A scan that found nothing or could not
run SHALL say why and SHALL leave the strip's figures as they were.

#### Scenario: A rescan brings an expired session back

- **WHEN** a browser session did not answer, the owner rescans, and the browser holds a fresh cookie
- **THEN** the session's bars return without waiting for the next poll

#### Scenario: The scan cannot run

- **WHEN** the scan's dependency is missing or no browser profile is found
- **THEN** the detail says so, and no stored session is removed
