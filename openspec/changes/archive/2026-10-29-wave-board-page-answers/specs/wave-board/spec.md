## ADDED Requirements

### Requirement: Viewers set statuses and answer waits on the page

The board page SHALL offer every item's status as a select and SHALL write a pick to `board/statuses`
as `{item: {status, at}}`. A pick SHALL be shown over the pushed status only while it is newer than the
item's `updated`. Each wait in the "Waiting on people" panel SHALL offer one button per `options` entry
and a free-text field, and SHALL write an answer to `board/answers` under `<item>|<ref>` (or
`<item>|#<index>` without a ref). The page SHALL NOT write `board/state`.

#### Scenario: Pick a status and answer a question

- **WHEN** a viewer sets H1.2 to done, clicks "C" on wait P1 and sends "99 000 Ft" as the other answer to G2
- **THEN** `board/statuses` holds `H1.2: done`, `board/answers` holds `H0.1|P1: C` and `H2.3|G2: 99 000 Ft`,
  and the page shows the new status and both answers

### Requirement: Page choices come back through import

`import <job> --dir DIR` SHALL apply each status pick newer than its item's last change as a manual
status, and each answer newer than the wait's recorded one as `answer` and `answered`; it SHALL print one
`STATUS` or `ANSWER` line per change and change nothing on a second run with the same documents.

#### Scenario: An old pick is ignored

- **WHEN** the statuses document holds a pick older than the item's last change
- **THEN** import leaves that item's status as it is

### Requirement: The page speaks the board's language

A job file SHALL accept `lang` (`en` or `hu`), set by `lang <job> <lang>`; it SHALL be in the payload only when
set. With `hu`, the page SHALL show its own labels in Hungarian, including "Egyéb" for the free-text answer.

#### Scenario: Hungarian board

- **WHEN** `lang job hu` runs and the page renders the payload
- **THEN** the panel is titled "Kire várunk" and the in-progress pill reads "folyamatban"
