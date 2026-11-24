## IN SCOPE
- Adopting a cross-project REQUEST or QUESTION posted straight into a relation room as an engagement
- Closing an adopted engagement on a linked reply or on the addressed project's unlinked answer
- Giving an unclaimed adopted engagement the project's live desk, or a started one after a grace

## OUT OF SCOPE
- Changes inside the bus (`set-agent-comm`)
- Requests in a project's own room or in a room of two sessions
- Requests addressed to one session
- Storing request or reply text
- Changing how an engagement opened by `set-fleet-ask` is closed

## ADDED Requirements

### Requirement: A request posted straight into a relation room is adopted
The takeover round SHALL open an engagement with source `room`, in state `open`, for every REQUEST or QUESTION entry in a relation room (`dm-<a>--<b>`) written by a seat of one of the two projects that is unaddressed or addressed to the other project by name, that is at least 90 seconds and at most 24 hours old, that is newer than the moment adoption was first switched on, and for whose room and timestamp no engagement exists. The engagement SHALL hold the asker seat, the addressed project, the room and the timestamp, and no text of the entry. An entry addressed to one session (`<project>#<id>`) SHALL NOT be adopted.

#### Scenario: An unaddressed request in a relation room
- **WHEN** a seat of project A posts an unaddressed REQUEST in `dm-A--B`, adoption was switched on before it, and two minutes have passed
- **THEN** an open engagement with source `room`, asker that seat, project B, and the entry's room and timestamp exists

#### Scenario: Already tracked
- **WHEN** the entry's room and timestamp already belong to an engagement
- **THEN** no second engagement is opened

#### Scenario: Addressed to one session
- **WHEN** the REQUEST is addressed to `B#<id>`
- **THEN** it is not adopted

#### Scenario: Older than adoption
- **WHEN** the entry predates the moment adoption was first switched on
- **THEN** it is not adopted

### Requirement: An adopted request is answered by a linked or an unlinked answer
An engagement with source `room` SHALL become `answered` when a seat of the addressed project posts, in the same room after the request, an entry linked to the request, or an ANSWER entry linked to nothing. An ANSWER linked to a different request, and an entry of any other type, SHALL NOT answer it. An engagement opened by `set-fleet-ask` SHALL keep being answered only by a linked reply.

#### Scenario: Unlinked answer
- **WHEN** after an adopted request the addressed project posts an ANSWER without a reply link in that room
- **THEN** the engagement is `answered`

#### Scenario: An answer to something else
- **WHEN** the only later entry by the addressed project is an ANSWER linked to a different request
- **THEN** the engagement stays `open`

### Requirement: An unclaimed adopted request gets a desk
An adopted engagement with no desk SHALL be assigned the addressed project's live framework desk when one exists, without counting a handover. When none exists and the request is younger than the stall bound, nothing SHALL be done. When none exists but a live session of the project has read the request (its bus read cursor in that room is at or past the request), no desk SHALL be started; an unreadable cursor store SHALL count as unread. When none exists, nobody live has read it, and the request is at least one stall bound old, a desk SHALL be started for the project with a takeover that names the request and no predecessor, and assigned to the engagement without counting a handover. That desk's context SHALL say that nobody picked the request up and that it was started to answer it.

#### Scenario: A live desk exists
- **WHEN** an unclaimed adopted engagement's project has a live framework desk
- **THEN** the engagement names that desk and its handover count is 0

#### Scenario: No desk, within the grace
- **WHEN** an unclaimed adopted engagement's project has no live desk and the request is younger than the stall bound
- **THEN** no desk is started

#### Scenario: Read by a live session
- **WHEN** an unclaimed adopted engagement's project has no live desk, the request is older than the stall bound, and a live session of the project has read it
- **THEN** no desk is started

#### Scenario: No desk, past the grace
- **WHEN** an unclaimed adopted engagement's project has no live desk, no live session of it has read the request, and the request is older than the stall bound
- **THEN** a desk is started with a takeover naming the request and no predecessor, the engagement names it, and its handover count is 0
