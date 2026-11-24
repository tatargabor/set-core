# Engagement Takeover Specification

## Purpose

Keeps a cross-project request from stopping for good when the desk that holds it stalls or is gone. The fleet measures whether the desk is live, moving or working in the background; a stalled desk is first interrupted with one line naming the open request, and a desk that is gone or still stalled is replaced by a fresh desk that continues the work from where its predecessor got and says on the bus that it took the request over. Takeovers per request are bounded, and a desk mandate is ended only on measured absence.

## Requirements

### Requirement: A desk is stalled only when nothing shows it working
For an open engagement, the desk SHALL be judged stalled when its last transcript movement is older than the stall bound (default 5 minutes, local config `fleet_takeover_stall_minutes`) AND the CPU time of its process tree outside the agent's own process, measured between two rounds, is below the background bound (default 5 % of one core, local config `fleet_takeover_cpu_percent`). Background CPU that cannot be measured SHALL count as no evidence of work, and the decision SHALL say it was taken on movement alone.

#### Scenario: A hung tool call
- **WHEN** a desk with an open engagement has not moved for longer than the stall bound and its background CPU is below the bound
- **THEN** the desk is judged stalled

#### Scenario: A long test run
- **WHEN** a desk has not moved for longer than the stall bound but a process it started is using CPU above the bound
- **THEN** the desk is judged working and nothing is done to it

### Requirement: A stalled desk is interrupted before it is replaced
The first escalation of an engagement SHALL interrupt the desk's current turn and type one line that names the open request by room and timestamp and asks for a linked reply. The time of the interrupt SHALL be recorded on the engagement. An engagement past the hard ceiling (the waiting bound, default 30 minutes) SHALL receive this interrupt even when its desk is moving, at most once.

#### Scenario: First escalation
- **WHEN** an open engagement's desk is judged stalled and the engagement has never been escalated
- **THEN** the desk's turn is interrupted, the line naming the request is typed into it, and the engagement records the interrupt time

#### Scenario: The hard ceiling
- **WHEN** an open engagement is older than the hard ceiling and has never been escalated, and its desk is moving
- **THEN** the desk is interrupted with the line once, and no replacement is started

### Requirement: An idle desk the bus did not wake is interrupted early
When an open engagement's desk has no turn running (state `quiet`), has not moved since the request was sent, and the request is at least 90 seconds old, the first escalation SHALL be the interrupt, without waiting for the stall bound.

#### Scenario: Idle at the prompt
- **WHEN** a desk idle since before the request has not moved 120 seconds after it was sent
- **THEN** it is interrupted with the line naming the request

#### Scenario: The desk saw it
- **WHEN** the desk moved after the request was sent, or a turn is running, or the request is younger than 90 seconds
- **THEN** no early interrupt is made

### Requirement: A gone or still-stalled desk is replaced by a desk that takes the request over
An open engagement SHALL be taken over when its desk is not live, or when one stall bound after the interrupt the engagement is still unanswered and the desk is still judged stalled. Taking over SHALL stop the old desk, end its mandate with reason `replaced`, start a fresh desk with a mandate that carries the takeover, and re-point the engagement at the new desk. The engagement SHALL stay `open` throughout and count one more handover.

#### Scenario: The desk died
- **WHEN** an open engagement's desk is no longer among the live agents
- **THEN** a new desk is started for the project with the takeover, and the engagement names the new desk

#### Scenario: The interrupt did not help
- **WHEN** an engagement was interrupted one stall bound ago, has no linked reply, and its desk is still stalled
- **THEN** the old desk is stopped, its mandate ends `replaced`, and a new desk takes the request over

#### Scenario: The interrupt helped
- **WHEN** after the interrupt the desk moved or the engagement was answered
- **THEN** nothing is replaced

### Requirement: The taking-over desk is told where the work got and says on the bus that it took over
A takeover mandate SHALL carry the request's room and timestamp, the asker, the predecessor's seat and session id (from the predecessor's mandate when its agent is gone). The desk's session-start context SHALL tell it to read the request on the bus — and, when that room refuses it, to ask the asker once to re-send the request — read where the predecessor got — the end of the predecessor's transcript and the project's open OpenSpec changes — and continue rather than restart; its first bus act SHALL be an unlinked FACT in the request's room naming the request, the predecessor seat and itself; and its answer SHALL be sent in the request's room, linked to the original request.

#### Scenario: Context of a taking-over desk
- **WHEN** a desk started with a takeover begins a session
- **THEN** its context names the request's room and timestamp, the asker, the predecessor seat and session id, the re-send fallback for an unreadable room, and the instruction to continue the predecessor's work, post the unlinked handover FACT first and answer in the request's room

#### Scenario: The handover notice does not close the request
- **WHEN** the new desk posts its handover FACT without a reply link
- **THEN** the engagement stays `open` until a reply linked to the request appears

### Requirement: Takeovers per request are bounded
An engagement SHALL be taken over at most `fleet_takeover_max` times (default 2). Past the bound no further interrupt or takeover SHALL be made; the engagement stays `open` and is reported as waiting.

#### Scenario: The bound is reached
- **WHEN** an engagement already handed over the maximum number of times has a stalled desk
- **THEN** nothing is interrupted or started, and the engagement is still listed as waiting

### Requirement: A mandate is ended for a missing agent only when its unit is measured gone
Ending the mandates of agents absent from a listing SHALL skip every mandate whose recorded unit is measured active, and every mandate whose unit's state cannot be measured. Only a mandate with no live unit SHALL be ended.

#### Scenario: A listing misses a running desk
- **WHEN** a listing does not contain a desk whose scope unit is active
- **THEN** that desk's mandate stays open

#### Scenario: The desk really exited
- **WHEN** a listing does not contain a desk and its unit is measured inactive
- **THEN** its mandate is ended

### Requirement: A running desk whose mandate was ended is re-adopted, not blocked
When desk resolution finds a live, framework-held agent that carries a desk mandate for the project whose record says it ended as missing (reason `ended`), it SHALL re-open that mandate and resolve to that agent. A mandate ended by an act (stopped, replaced, desk-quiet, done) SHALL NOT be re-opened this way.

#### Scenario: Held label, ended mandate
- **WHEN** a request is resolved and the project's running desk carries a mandate that was ended as missing
- **THEN** that mandate is re-opened and the request resolves to the running desk instead of failing `desk-not-ready`

#### Scenario: A deliberately stopped desk is not revived
- **WHEN** a live agent carries a desk mandate that ended with reason `replaced`
- **THEN** it is not re-opened and is not resolved as the desk

### Requirement: A desk waiting on its own request is not swept
The quiet sweep SHALL keep a desk whose seat is the asker of a `resolving` or `open` engagement, with the reason `asking-open`, and SHALL not show a close countdown for it.

#### Scenario: Desk asked another project
- **WHEN** a quiet desk has an open engagement it asked of another project
- **THEN** the sweep keeps it with the reason `asking-open`
