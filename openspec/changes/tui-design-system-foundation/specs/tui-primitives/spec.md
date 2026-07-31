## IN SCOPE
- A single shared module (`web/src/components/tui/`) holding the dashboard's reusable visual primitives
- The rule that a screen uses a primitive rather than re-implementing its markup
- Keyboard access and focus behaviour for the primitives that open transient surfaces (popover, dialog, tab strip)
- Each primitive's obligation to state what it withheld when it compacts

## OUT OF SCOPE
- Migrating the Orchestration, Manager, Memory and Settings screens onto the primitives (follow-up change)
- Tooltips — the dashboard's 58 `title=` attributes stay native
- Charts (`recharts`) and the DAG canvas (`@xyflow/react`), which own their own rendering
- The Battle view, which has independent styling by prior decision

## ADDED Requirements

### Requirement: The primitives live in one module and are the only implementation
The dashboard's reusable visual patterns SHALL live in `web/src/components/tui/` and be
exported from it. A screen or feature component SHALL NOT hand-write the markup of a pattern
the module provides.

The module SHALL provide, at minimum: a progress bar, a status indicator, a section divider, a
panel frame, a chip, a key/value list, a tab strip, a table frame, and a badge. The first three
SHALL keep the names and rendered output they have today (`TuiProgress`, `TuiStatus`,
`TuiSection`), so that the six files importing them are unaffected.

#### Scenario: An existing primitive keeps its output
- **WHEN** a component that imported `TuiProgress` from `components/tui` renders after the move
- **THEN** it imports from `components/tui/` and renders the same block-character bar as before

#### Scenario: A hand-rolled pattern is rejected
- **WHEN** a component file outside `web/src/components/tui/` contains the panel-frame class
  string (`rounded border border-neutral-8…`) or an `absolute z-` dropdown container
- **THEN** the drift test fails and names the file and line

### Requirement: A primitive that opens a transient surface is keyboard-operable
Any primitive that opens a surface over the page — popover, dropdown, dialog — SHALL trap focus
while open, restore focus to the trigger on close, close on `Escape`, and close on a click
outside. Tab strips SHALL move selection with the arrow keys and expose the selected tab to
assistive technology.

These behaviours SHALL be obtained from headless primitives (`@radix-ui/react-popover`,
`@radix-ui/react-dialog`, `@radix-ui/react-tabs`) rather than reimplemented, and SHALL be
skinned to the dashboard's monospace language rather than to the library's default appearance.

#### Scenario: Escape closes a popover and returns focus
- **WHEN** a reader opens the column-filter popover in the status table and presses `Escape`
- **THEN** the popover closes and keyboard focus is on the button that opened it

#### Scenario: A dialog does not leak focus to the page behind it
- **WHEN** a dialog is open and the reader presses `Tab` repeatedly
- **THEN** focus cycles within the dialog and never reaches an element behind it

#### Scenario: Arrow keys move between tabs
- **WHEN** a tab in a tab strip has focus and the reader presses the right arrow key
- **THEN** the next tab becomes selected and focused

### Requirement: A primitive that compacts states what it withheld
Any primitive that shows less than it was given — a truncated cell, a capped list, a collapsed
group — SHALL render the withheld count adjacent to the visible content, not in a tooltip and
not only in the control that caused the compacting.

A primitive SHALL NOT compact silently even when the withheld items are all in a non-failing
state, because the reader cannot know that without being told.

#### Scenario: A capped chip list names its remainder
- **WHEN** a chip list is given 9 values and renders 5
- **THEN** a visible `+4 more` affordance appears beside the rendered chips

#### Scenario: A collapsed group carrying a failure marks itself
- **WHEN** a collapsed group contains an item in a failing state
- **THEN** the collapsed header carries a failure marker, so the failure is visible without expanding

### Requirement: A primitive names status by meaning, never by hue
A primitive SHALL express status through the semantic tokens defined by the design system. It
SHALL NOT contain a literal Tailwind colour class such as `text-blue-400`.

#### Scenario: A status indicator uses a token
- **WHEN** the status indicator renders a `merged` status
- **THEN** the emitted class references the done-status token, and the source file contains no
  literal `blue-400`
