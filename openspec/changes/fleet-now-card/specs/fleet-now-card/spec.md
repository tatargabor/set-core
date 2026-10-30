## IN SCOPE
- A Now window served by the fleet, meant to be kept always on top, showing one item at a time
- The item's actions: answer by option, go there, dictate, done, later, delegate (with reasons to keep)
- Merging the owner queue with the `fleet-waiting-on-you` sources into one ordered sequence
- Outcome feedback after an action and a day's closed count
- Sound cues at project-switch breakpoints, with a backoff when cues are ignored
- The day shape: up to three focus projects, parked projects with resume notes, wind-down mode
- Idea parking
- Card state that is not item content (snoozes, focus projects, counts), and the persistence boundary

## OUT OF SCOPE
- Ranking items (the publishing project ranks; the card shows the order it is given)
- Reading meetings, inboxes or follow-up lists (the publishing project does that)
- Starting or scheduling agents (the card can hand an item to the project; the project decides)
- A chat or phone notifier
- Making the window always-on-top at the operating-system level (the owner's window manager does it;
  the page only declares a compact window size)
- Streaks, points or any loss-framed reward

## ADDED Requirements

### Requirement: The Now window shows one item, never a list

The fleet SHALL serve a page at `/now` that shows exactly one item at a time. The item SHALL be
shown with its project, one imperative sentence, the reason it is first, and an estimate when the
source supplies one. The page SHALL NOT render the titles of the other items; it SHALL show only how
many items follow.

#### Scenario: Five items are open
- **WHEN** the merged queue holds five items
- **THEN** the page shows the first item's project, sentence and reason
- **AND** it shows that four more follow, without their titles

#### Scenario: Nothing is open
- **WHEN** every measured source is empty and no source is unmeasured
- **THEN** the page says nothing is waiting and shows the day's closed count

### Requirement: A gap is shown where the reader is standing

When any source could not be read, the page SHALL show, on the card itself, how many sources are
unmeasured. An empty queue with an unmeasured source SHALL NOT be presented as "nothing is waiting".

#### Scenario: The owner queue cannot be read
- **WHEN** the owner-queue command fails and the other sources are empty
- **THEN** the card states that one source could not be read and why
- **AND** it does not say that nothing is waiting

### Requirement: The merged order is the publisher's rank, then the framework sources by age

The card SHALL order items as follows: items from the owner queue in the order the publishing
project ranked them; then items from the `fleet-waiting-on-you` sources that the owner queue does
not already reference, oldest first. An owner-queue item that references a framework item (by its
source and id) SHALL replace it, so the same thing is not shown twice. Snoozed items SHALL be
excluded until their snooze ends.

#### Scenario: The owner queue references an agent question
- **WHEN** an owner-queue item references an agent question that the agent-question source also lists
- **THEN** the card shows that item once, in the owner queue's position

#### Scenario: No owner queue is published
- **WHEN** no project declares an `owner-queue` command
- **THEN** the card shows the framework sources oldest first
- **AND** it states that no ranked queue is published

### Requirement: A question is answered with one tap

When an item carries answer options, the card SHALL show each option as a button. Choosing one SHALL
send the choice back to where the item came from — the publishing project's `owner-queue-act` write
command for an owner-queue item, the question relay for a relayed agent question — and SHALL report
what that path said became of it. A choice that cannot be delivered SHALL be reported as not
delivered, and the item SHALL stay on the card.

#### Scenario: An option is chosen
- **WHEN** the owner taps an option on an owner-queue item
- **THEN** the card calls the publishing project's write command with the item id and the option
- **AND** on success it shows the outcome feedback and moves to the next item

#### Scenario: The write is refused
- **WHEN** the write command exits non-zero with a reason
- **THEN** the card shows the project's reason
- **AND** the item stays as the current card

### Requirement: Go there and dictate

An item SHALL offer **Go there** only when there is a place the item can be worked on: the fleet with
the agent's tile focused for an agent item, the project's status page for a framework run-state item,
the bus message for a bus item, or the link the publishing project supplied. A ranked item without a
link SHALL NOT offer Go there — the project's status page says nothing about a ranked task (amended
2026-10-30 after first use: *"itt a go there is értelmetlen"*). An item that accepts free text
SHALL offer **dictate**, which uses the dashboard's existing voice input and sends the text through
the same path as an option.

#### Scenario: An agent item
- **WHEN** the owner chooses Go there on an agent-question item
- **THEN** the fleet opens with that agent's tile focused

#### Scenario: Voice input is not available
- **WHEN** no speech service is configured
- **THEN** the dictate control is absent and a typed text field is offered instead

### Requirement: Done, Later and Delegate

Every item SHALL offer Done, Not needed, Later and — when the item is marked delegable — Delegate.
Not needed SHALL ask for one line saying why and send it as Done with that text, so the publisher can
learn which matters are moot; that line also counts as the reason for keeping a delegable item. Done and
Delegate SHALL be sent to the item's source through the same path as an answer. Later SHALL snooze
the item for a chosen interval and SHALL be held by the card, not sent. Keeping a delegable item
(choosing Done or an answer instead of Delegate) SHALL ask for one or two short reasons, and SHALL
NOT ask for more than two.

#### Scenario: Keeping a delegable item
- **WHEN** the owner chooses Done on a delegable item
- **THEN** the card asks for one or two reasons for keeping it before sending
- **AND** the reasons are sent with the action

#### Scenario: Not needed
- **WHEN** the owner chooses Not needed and writes "we moved the domain elsewhere"
- **THEN** the card sends Done with that text and closes the item

#### Scenario: Later
- **WHEN** the owner chooses Later for two hours
- **THEN** the item leaves the card and returns after two hours
- **AND** nothing is sent to the item's source

### Requirement: Feedback names the outcome, not the person

After an action is delivered, the card SHALL show what the action caused, using the outcome text the
source returned when it returned one, and SHALL increment the day's closed count. The card SHALL NOT
show streaks, points, or any message that frames a missed day as a loss. The feedback SHALL close
itself after ten seconds, except a feedback reporting a failure, which SHALL stay until dismissed.

#### Scenario: A delivered answer
- **WHEN** an answer is delivered and the source returns "the agent resumed"
- **THEN** the card shows that outcome and the updated closed count
- **AND** the feedback closes after ten seconds

### Requirement: Cues fire at breakpoints, rarely, and back off

The card SHALL play a sound cue only when the owner's input moves from one project to another
(measured from the fleet's record of the owner's last input per agent) and a new item is first since
the previous cue, or when the first item has a deadline within a configured window. It SHALL NOT cue
while the owner's input has stayed in one project for longer than a configured focus threshold,
except once, after a configured time, when that project is not one of the day's focus projects. The
cue sound SHALL vary between cues. When a configured number of consecutive cues are followed by no
action, the card SHALL lengthen the interval between cues and SHALL show that it has done so.

#### Scenario: Leaving a project
- **WHEN** the owner's input moves from project A to project B and the first item has changed since the last cue
- **THEN** the card plays one cue

#### Scenario: A long block in a focus project
- **WHEN** the owner has worked in a focus project for longer than the focus threshold
- **THEN** no cue plays

#### Scenario: Ignored cues
- **WHEN** three consecutive cues are followed by no action
- **THEN** the interval between cues doubles and the card shows "cues slowed"

### Requirement: The day has up to three focus projects

The card SHALL let the owner pick up to three focus projects for the day, and SHALL NOT accept a
fourth. Items from other projects SHALL still be counted, but SHALL be shown only when no focus
project has an item, or when the item's deadline falls within the configured window. A project
removed from focus SHALL ask for a one-line resume note, which the card SHALL show when that project
is next in focus.

#### Scenario: A fourth project
- **WHEN** three focus projects are picked and the owner tries to add a fourth
- **THEN** the card asks which one to swap out

#### Scenario: Resume note
- **WHEN** the owner removes a project from focus and writes a resume note
- **THEN** the note is shown on that project's first card the next time it is in focus

### Requirement: Wind-down after a configured hour

After a configured evening hour, the card SHALL switch to wind-down: it SHALL offer to write
tomorrow's first card, to hand delegable items to unattended agents through the publishing project,
and to park open work with resume notes, and it SHALL show one neutral line about the hour. It SHALL
NOT block, lock or hide the queue.

#### Scenario: The hour passes
- **WHEN** the configured hour passes while the card is open
- **THEN** the card offers the wind-down actions and still allows the queue to be opened

### Requirement: Ideas are parked, not started

The card SHALL offer an idea-parking control that sends a short text to the publishing project as a
parked idea. The card SHALL show only the number of parked ideas, never their text.

#### Scenario: Parking an idea
- **WHEN** the owner parks an idea
- **THEN** the idea is sent to the publishing project and the parked count increases by one

### Requirement: The card persists no item content

The framework SHALL hold card state — snoozes, focus projects, resume notes, cue history, counts —
keyed by opaque item and project identifiers, under the user's local data directory and outside every
repository. It SHALL NOT write item titles, options, reasons or answers to a file, a cache, or a log.
Resume notes and parked ideas are owner-written text and SHALL be sent to the publishing project
rather than stored by the framework when such a project is declared.

#### Scenario: Logging an action
- **WHEN** an action is delivered
- **THEN** the log line names the item id, the action kind and the outcome status
- **AND** it contains no item title, option text or answer text

### Requirement: The owner can switch projects off on a tag strip

Above the card the page SHALL show one tag per project that has an item, with its item count. Clicking
a tag SHALL switch that project off or back on; a switched-off project's items SHALL NOT come up,
whatever their deadline. The switch SHALL persist across days until the owner changes it. A
switched-off tag SHALL stay visible with its count, the line under the card SHALL say how many items
switched-off tags hide, and the empty state SHALL NOT say that nothing is waiting while any item is
hidden this way. Added 2026-10-30 at the owner's request after first use (*"ki/be kapcsolni felül a
kérdések felett és akkor nem jön fel ami nincs bekapcsolva"*).

#### Scenario: Switching a project off
- **WHEN** the owner switches off a project that has two items while another project has one
- **THEN** the card shows the other project's item, says two are hidden by switched-off tags, and the switched-off tag still shows its count

#### Scenario: Everything left is switched off
- **WHEN** every remaining item belongs to a switched-off project
- **THEN** the empty state names how many items are hidden instead of saying nothing is waiting

### Requirement: The card explains itself

Every control on the page SHALL carry a tooltip saying what it does, the header counts SHALL name what
they count, and a help control SHALL open a floating legend naming every part of the card without
moving the card. Added 2026-10-30 at the owner's request (*"kellene a felületre súgó mi micsoda"*).

#### Scenario: Opening the legend
- **WHEN** the owner opens the help control
- **THEN** a legend over the card names the answer buttons, the text field, Go there, Done, Later, focus and the grey and yellow notes, and the card stays in place

### Requirement: The card has a Goals tab beside the item

*Added 2026-10-30 at the owner's request: "kellene egy olyan fül is, hogy mik a célok … hogyha
megnézem, akkor mindig lássam".*

The `/now` page SHALL offer two tabs, Now and Goals. Goals SHALL list the `owner-goals` answer —
each goal's title, what it serves, deadline, progress, projects and evidence links — with proposed
goals marked unconfirmed, followed by the publisher's suggestions. Switching tabs SHALL NOT change the
window's size or move the tab strip, and the Now tab SHALL stay the default on load.

#### Scenario: Opening the Goals tab
- **WHEN** the owner taps Goals
- **THEN** the goals list replaces the item in the same window, and Now brings the item back

#### Scenario: Unconfirmed goals are counted on the tab
- **WHEN** three goals are proposed and the Now tab is open
- **THEN** the Goals tab label shows that three goals await a verdict

### Requirement: The card's own text follows a local locale setting

*Added 2026-10-30 at the owner's request ("magyarul kellene az egész cucc"); the owner chose a
small translation layer for this card only, with English as the default.*

The card's own text — tab names, counters, buttons, overlays, the help legend, markers, empty
states, default feedback, tooltips and accessible labels — SHALL follow the local setting
`now.locale`. English SHALL be the default and the source of truth; `hu` SHALL switch the card to
a Hungarian dictionary that has exactly the English keys; any other value SHALL read as English
with a warning. Both `GET /api/fleet/now` and `GET /api/fleet/now/goals` SHALL return the setting
as `locale`. Text that comes from the publisher — item sentences, why, option labels, outcomes,
goal titles, advice, check evidence, refusal reasons — SHALL be shown untranslated, and text the
card SENDS to the publisher SHALL NOT change with the locale. The window title SHALL stay
`Now · SET` in every locale.

#### Scenario: The owner switches the card to Hungarian
- **WHEN** `now.locale` is set to `hu` in local config and the card loads
- **THEN** the card's own labels are Hungarian (Most, Célok, Kész, Később, Aktuális még?), the publisher's sentence and option labels are shown exactly as published, and a "not needed" reason is still sent with its English `Not needed:` prefix
