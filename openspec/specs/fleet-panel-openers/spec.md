# fleet-panel-openers Specification

## Purpose
One shared opening behaviour for the fleet project header's openers — restore, waiters and
set-core modules — so that a panel is an overlay that changes the size and position of nothing
else, its chrome is uniform, and its body presents repeated records as columns. Created by
archiving change fleet-structured-notices.

## IN SCOPE

- One shared "opens a panel" behaviour for the fleet project header's openers: restore, waiters, set-core modules
- Overlay positioning that never changes the size or position of anything else
- Uniform panel chrome: an icon, a title, counts, and a close control
- Structured panel bodies — columns rather than run-on rows
- Which notices persist on the header and which close themselves
- A compacted fact staying counted where the reader is standing
- A stable open-state marker on every opener

## OUT OF SCOPE

- What any action does — waiter removal and module installation are unchanged (`module-install` governs the latter)
- The wording of any user-visible string
- The across-projects restore result, `FollowPanel`, and the wider modal-shell duplication
- Colour literals outside these surfaces

## Requirements

### Requirement: An opened panel never changes the size or position of anything else

Every opener in the project header SHALL present its content as an overlay positioned above the
layout. A panel MUST NOT participate in the sizing of the header row, and opening or closing one
MUST NOT move any other control, change any strip's height, or cause the header row to wrap
differently.

A strip that displays a notice under some conditions SHALL reserve its height when it displays
none, so that a notice arriving does not shift the row.

#### Scenario: Opening a panel leaves the header unchanged

- **WHEN** the reader opens the waiters panel
- **THEN** the header row's height is unchanged, and every other control in it stays at the same position

#### Scenario: Opening a panel does not push the page

- **WHEN** the reader opens the set-core modules panel
- **THEN** the content below the header does not move

#### Scenario: A notice arriving does not shift the row

- **WHEN** a notice appears in a strip that was showing none
- **THEN** nothing already on that row changes position

### Requirement: Every opener uses one shared panel mechanism

The openers in the project header — restore, waiters and set-core modules — SHALL obtain their
open state and their panel presentation from one shared mechanism, rather than each carrying its
own. Adding a further opener SHALL NOT require a new opening behaviour.

Each opener SHALL carry a stable marker reporting whether its panel is open, so the state is
addressable without relying on the element's text or on it being the only button present.

#### Scenario: A newly added opener behaves like the existing ones

- **WHEN** a further opener is added to the header using the shared mechanism
- **THEN** its panel overlays, carries the same chrome, and exposes the same open-state marker without further work

#### Scenario: Open state is addressable on every opener

- **WHEN** any opener's panel is open
- **THEN** that opener reports its open state through a stable marker

### Requirement: Panel chrome is uniform, and a panel-wide action bar appears only where such actions exist

Every panel SHALL present the same chrome: an icon, a title, the counts that describe its
contents, and a close control. A panel SHALL be closable by that control.

A panel SHALL render a footer of panel-wide actions only when it has panel-wide actions. A panel
whose only actions belong to individual rows MUST NOT render a footer, and its chrome is the close
control alone.

Per-row actions SHALL be preserved. Presenting a panel as carrying information only MUST NOT
remove an action it offers.

#### Scenario: A panel with panel-wide actions renders a footer

- **WHEN** the restore panel is open
- **THEN** it renders its panel-wide actions in a footer alongside the close control

#### Scenario: A panel without panel-wide actions renders only a close control

- **WHEN** the waiters panel or the set-core modules panel is open
- **THEN** its chrome carries a close control and no action footer

#### Scenario: Row actions survive the move into a panel

- **WHEN** the waiters panel is open and an orphaned waiter is listed
- **THEN** that row still offers its removal action behind its confirmation step

#### Scenario: The install action survives the move into a panel

- **WHEN** the set-core modules panel is open and a module is not fully present
- **THEN** that row still offers its preview, and the preview still leads to the separate write action

### Requirement: A panel body presents its rows as columns

A panel listing repeated records SHALL present them as aligned columns with headed fields, rather
than as a run of text within a row. Each field SHALL occupy the same position in every row so
that rows can be compared down a column.

#### Scenario: Waiters are presented as columns

- **WHEN** the waiters panel lists more than one waiter
- **THEN** each waiter's process identifier, status, working directory and action occupy the same column in every row

#### Scenario: Modules are presented as columns

- **WHEN** the set-core modules panel lists the project's modules
- **THEN** each module's name, state, file counts and action occupy the same column in every row

### Requirement: A notice persists if it describes a state and closes itself if it describes an event

A notice describing a condition that is true at the moment of reading SHALL remain available for
as long as that condition holds. A notice describing a completed action SHALL close itself after a
bounded interval, and SHALL also offer an explicit close.

A notice reporting a failure or a partial outcome MUST NOT close itself, whichever of the two it
otherwise resembles.

#### Scenario: A completed result closes itself

- **WHEN** a restore completes with every entry started
- **THEN** its result is shown and then closes without the reader acting

#### Scenario: A partial result does not close itself

- **WHEN** a restore completes with any entry not started
- **THEN** its result remains until the reader closes it

#### Scenario: A state notice remains while its condition holds

- **WHEN** a condition such as an undeclared agent remains true
- **THEN** the notice describing it remains available rather than closing itself

### Requirement: Compacting a notice hides its sentence, never its existence

Where notices are collapsed behind a summary control, that control SHALL remain visible while any
collapsed condition holds, and SHALL state how many conditions it stands for. A reader MUST be
able to tell that something is being withheld without opening anything.

Collapsing MUST NOT be used to remove a failure from view. A withheld or unknown condition and a
failed one SHALL remain distinguishable from each other.

#### Scenario: The summary control states how many notices it holds

- **WHEN** two conditions are collapsed behind one control
- **THEN** that control is visible and states that it stands for two

#### Scenario: The summary control does not disappear while a condition holds

- **WHEN** a collapsed condition is still true
- **THEN** the control that opens it remains on the header

#### Scenario: A withheld condition is not rendered as a failure

- **WHEN** a notice reports that something could not be determined
- **THEN** it is presented distinguishably from a notice reporting that something failed
