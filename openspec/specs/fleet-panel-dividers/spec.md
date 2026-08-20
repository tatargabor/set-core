# Fleet Panel Dividers Specification

## Purpose

Owns the edge between two panes on the fleet screen: dragging it, reaching it with the
keyboard, and storing its position durably per user without disturbing the arrangement
it shares a document with.

## IN SCOPE
- Dragging the edge between two panes with a pointer, on either axis
- Reaching and moving that edge with the keyboard alone
- Remembering each divider's position across reloads, browsers and restarts
- Refusing to store a position from which the divider could not be recovered

## OUT OF SCOPE
- Which panes exist and what they contain (see `fleet-dockable-views`)
- The 1–4 column arrangement of agent tiles, which is a separate preference
- Per-project divider positions: a divider belongs to the screen, not to a project

## Requirements

### Requirement: A pane's edge is draggable
The surface SHALL let a person change the size of a pane by dragging the divider
beside it, and the pane SHALL follow the pointer while the drag is in progress.

#### Scenario: The pane follows the pointer
- **WHEN** a person presses the primary button on a divider and moves the pointer
- **THEN** the pane resizes by the distance moved, measured from where the drag began

#### Scenario: A dropped intermediate event does not accumulate error
- **WHEN** one or more pointer-move events are lost during a drag
- **THEN** the next event still resizes the pane to the position the pointer is
  actually at, because each position is measured from the drag's origin rather
  than accumulated from deltas

#### Scenario: Crossing a divider does not resize anything
- **WHEN** a pointer moves across a divider without a press having occurred
- **THEN** no resize takes place

#### Scenario: A non-primary button does not begin a drag
- **WHEN** a person presses a non-primary button on a divider
- **THEN** no drag begins

### Requirement: The divider is reachable without a pointer
The surface SHALL let a person move a divider using the keyboard, and every
keyboard adjustment SHALL be persisted.

#### Scenario: Arrow keys move the divider
- **WHEN** a divider has keyboard focus and an arrow key along its axis is pressed
- **THEN** the pane resizes by a fixed step, and the new position is persisted

#### Scenario: A keyboard user is not denied persistence
- **WHEN** a person adjusts a divider using only the keyboard
- **THEN** the position is stored, because no pointer-release event will occur to
  trigger a deferred save

#### Scenario: The position is announced
- **WHEN** a divider is presented
- **THEN** it exposes its current, minimum and maximum values and its orientation
  to assistive technology

### Requirement: A divider position is stored durably, per user, on the server
The system SHALL store each divider's position in the framework's durable
per-user document alongside the hand-made arrangement, keyed by divider.

#### Scenario: The position survives a reload
- **WHEN** a person drags a divider and later reloads the surface
- **THEN** the pane is rendered at the stored position

#### Scenario: The position is not browser-local
- **WHEN** the surface is opened in a second browser on the same machine
- **THEN** the stored position applies there too

#### Scenario: The write happens once per gesture
- **WHEN** a person drags a divider across many intermediate positions
- **THEN** exactly one write is performed, on release, rather than one per position

### Requirement: An absent position is a default, never a zero
The system SHALL treat a divider with no stored position, or with a stored value
that is not a usable number, as having no position — the caller's own default
applies. It SHALL NOT coerce such a value into a size.

#### Scenario: A divider that was never dragged
- **WHEN** a divider has no stored entry
- **THEN** the pane renders at the default size the surface declares for it

#### Scenario: A value that is not a number
- **WHEN** the stored document carries a non-numeric value for a divider
- **THEN** it is treated as absent, and the default applies

#### Scenario: A pane cannot be stored into invisibility
- **WHEN** a position outside the range the surface can render and recover is
  submitted
- **THEN** it is clamped into that range, so the edge remains grabbable

### Requirement: Storing a divider position does not disturb the arrangement
Writing a divider position SHALL NOT alter the stored arrangement of projects,
and SHALL NOT change the version that guards it.

#### Scenario: The arrangement is untouched
- **WHEN** a divider position is written
- **THEN** the groups, the parked list and the unassigned order are unchanged

#### Scenario: The guarding version does not move
- **WHEN** a divider position is written
- **THEN** the arrangement's version is the same before and after, so a client
  holding that version can still save an arrangement edit

#### Scenario: Saying nothing about dividers does not delete them
- **WHEN** a client replaces the arrangement without mentioning divider positions
- **THEN** the stored positions are preserved

#### Scenario: Explicitly sending no dividers does clear them
- **WHEN** a client replaces the arrangement and explicitly supplies an empty set
  of divider positions
- **THEN** the stored positions are cleared, so a reset remains possible
