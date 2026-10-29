## ADDED Requirements

### Requirement: Items record what they wait on

An item SHALL be able to carry `waits`, a list of objects `{kind, who, text, ref}` where `kind` is `decision` or
`blocker`. `wait` SHALL append one, or replace in place the wait with the same `ref`; `unwait` SHALL
remove the one named by `--ref`, all with `--all`, or the only one when the item has one. A wait SHALL
NOT change the item's status. Empty text, an unknown item and an unknown ref SHALL be usage errors.
Waits SHALL be part of the payload.

#### Scenario: A decision and a blocker on one item

- **WHEN** `wait job H2.3 --decision "Price on the site?" --who Gábor --ref G2` and
  `wait job H2.3 --blocker "Run migration 0019" --who Gábor --ref G9` run
- **THEN** the item carries both waits in that order, its status is unchanged, and the payload
  carries them after `sync`

#### Scenario: Same ref replaces

- **WHEN** a second `wait` uses a ref that is already on the item
- **THEN** the earlier wait is replaced in its position, not duplicated

### Requirement: The page lists every open wait by person

The board page SHALL show a "Waiting on people" panel above the waves, with one group per `who`
(unnamed waits grouped together), decisions before blockers, each line naming the item id, the ref
and the text. Waits on skipped items SHALL be left out; waits on done items SHALL be shown. The
summary SHALL count decisions and blockers, and each row and Kanban card SHALL show its own waits.
The panel SHALL be hidden when nothing waits.

#### Scenario: Two people, two groups

- **WHEN** the payload has waits on Gábor and on András
- **THEN** the panel shows two groups with their counts, and the summary shows the totals

### Requirement: Status pills fit their column

In the Waves view, the status column SHALL be as wide as the widest pill in the wave, so no pill label
overflows its pill or its column, and the rows of a wave SHALL stay aligned. At 320px no part of the
page SHALL scroll horizontally.

#### Scenario: "in progress" fits

- **WHEN** a wave holds an in-progress item
- **THEN** its pill's text stays inside the pill, measured at 1280, 375 and 320px
