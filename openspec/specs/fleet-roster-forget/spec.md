# fleet-roster-forget Specification

## Purpose
TBD - created by archiving change fleet-roster-forget-surface. Update Purpose after archive.
## Requirements
### Requirement: A recorded entry can be removed from a project's record by key
`DELETE /api/fleet/roster/{project}/{key}` SHALL remove exactly the entry
addressed by `key` from the project's record document and SHALL leave the
conversation file the entry points at untouched. The route SHALL address keys
containing slashes (`{key:path}`), because an entry with no session id is
keyed on a synthetic name containing one, and those MUST be removable rather
than silently unreachable. A key the record does not hold SHALL answer 404.

#### Scenario: An entry is forgotten
- **WHEN** the route is called for a key the record holds
- **THEN** the record no longer holds that entry, the transcript on disk is unchanged, and the route answers with the project and the forgotten key

#### Scenario: An unknown key is a 404, not a silence
- **WHEN** the route is called for a key the record does not hold
- **THEN** the route answers 404 naming the key and the project

### Requirement: The surface offers an armed per-entry forget
The restore dialog's recorded-entry row SHALL offer a forget control placed
after the peek toggle. The first click SHALL send nothing and SHALL open a
confirmation naming the entry; only the confirmation SHALL reach the route. The
control's copy SHALL state that the record entry is removed, the conversation
file on disk stays, and nothing running is stopped.

#### Scenario: The first click deletes nothing
- **WHEN** the trash control is clicked once
- **THEN** no DELETE request is sent and a confirmation naming the entry is shown

#### Scenario: The confirmed click forgets the entry
- **WHEN** the confirmation is accepted
- **THEN** exactly one DELETE is sent to that entry's route, and the project's record is re-read so the row does not remain on screen

#### Scenario: Cancelling forgets nothing
- **WHEN** the confirmation is cancelled
- **THEN** no request is sent and the entry stays on screen

### Requirement: The surface offers a delete of the whole selection, armed, stated in count
The dialog footer SHALL offer a delete of every ticked entry, placed at the
bottom right beside the close control. It SHALL be drawn only when the
selection is non-empty, SHALL state the count, SHALL be armed the same way as
the per-entry control, and SHALL disarm when the selection changes or the
dialog closes. A bulk delete SHALL send one DELETE per ticked entry, remove
each successful key from the selection, and report failures together rather
than silently.

#### Scenario: No selection draws no bulk control
- **WHEN** the dialog is open with nothing ticked
- **THEN** no delete-selection control is drawn

#### Scenario: The confirmed bulk delete removes every ticked entry
- **WHEN** two entries are ticked and the armed confirmation accepts
- **THEN** one DELETE per ticked key is sent and both ticks clear

#### Scenario: A partial failure is visible and still refreshes
- **WHEN** a bulk delete of two succeeds for one and fails for the other
- **THEN** the failure is named in the footer, the successful entry is unticked and the failed one stays ticked, and the record is re-read for the entry that succeeded

### Requirement: A failed forget is shown, never silent
A forget that does not succeed SHALL render its failure reason near where the
act was offered. A failed forget SHALL NOT be reported as removed, and the
entry it concerns SHALL remain on screen and ticked if it was.

#### Scenario: The route refuses
- **WHEN** a delete answers non-2xx or fails at the transport
- **THEN** the reason is shown in the dialog footer and the entry remains listed

