# project-status-field-roles Specification

## Purpose
A project declares what its own fields ARE, in a closed vocabulary of roles; the framework decides entirely how each role is rendered. Appearance never travels in the contract.

## IN SCOPE
- A project declaring what its own fields ARE, in a closed vocabulary of roles
- The framework carrying that declaration from the envelope through to the surface
- Resolving a declared role against the data actually present, including paired roles
- The rendering the framework chooses for each role, including a progress bar

## OUT OF SCOPE
- Anything about how a value LOOKS travelling in the contract — colour, weight, width, position,
  format strings, precision
- Inferring a role from a field name, a value's magnitude, or any other heuristic
- Unit systems beyond the one a role name fixes (a producer with other units converts on its side)
- Which fields appear on screen at all, and where — decided by the surface's own layout rules

## Requirements

### Requirement: A project declares what a field IS, never how it looks

The envelope MAY carry a `display` key mapping **bare field names** to **roles**. A role states what
the data is — an identifier, a path, a duration in seconds, a count. The framework SHALL decide
entirely how a role is rendered, and MAY change that rendering without any producer changing its
output.

The contract SHALL NOT carry presentation: no colour, weight, alignment, width, format string, or
precision. A role that describes appearance rather than meaning is not part of this vocabulary.

The reason is not fastidiousness. A declaration of appearance freezes one moment's rendering into
every producer's output, so improving the surface later requires all of them to re-ship. There are
few things a value can BE and unlimited ways it can look.

#### Scenario: An identifier stops being formatted as a quantity
- **WHEN** an answer declares `display: {"pid": "id"}` and its data holds `pid: 3218705`
- **THEN** the surface renders the value without thousands separators, because an identifier is a
  name rather than an amount

#### Scenario: The declaration cannot ask for a colour
- **WHEN** an answer declares a role that names an appearance rather than a meaning
- **THEN** the framework ignores it, and the value renders exactly as an undeclared value would

### Requirement: The role vocabulary is closed, and an unknown role is inert

The framework SHALL recognise exactly these roles: `id`, `path`, `duration-seconds`, `count`, and
the two paired forms `{"progressOf": "<field>"}` and `{"limitOf": "<field>"}`.

An unrecognised role SHALL be ignored silently — not reported as an error, and not allowed to
suppress the value. A malformed `display` key (not an object, or values of the wrong shape) SHALL
leave every field unroled rather than failing the answer.

The fail direction is the whole point. If an unknown role were refused, a producer shipping a new
role would blank a working surface, and the framework would be dictating the producer's release
order. Ignoring means the value renders the way it does today and starts rendering better whenever
the framework learns the role.

#### Scenario: A producer ships a role the framework does not know yet
- **WHEN** an answer declares `display: {"size": "bytes"}` and `bytes` is not a recognised role
- **THEN** `size` renders as it would with no declaration at all, and nothing on screen reports a
  problem

#### Scenario: A malformed declaration does not cost the answer
- **WHEN** an answer's `display` is a list, a string, or null
- **THEN** the answer renders in full with no roles applied

### Requirement: Roles are selected by bare field name at any depth

A name in `display` SHALL match a field of that name anywhere in `data`, including inside nested
objects and inside objects within lists. A dotted or path-shaped key SHALL match nothing.

This is the selector `caveats` and `follow` already use, and reusing it is the requirement rather
than an implementation note: a second selector shape in the same envelope means a producer must
know which rule applies to which key, and a mis-shaped key fails **silently** — it matches nothing,
the value renders unroled, and the declaration looks correct.

#### Scenario: A field nested under a diagnostic object still gets its role
- **WHEN** an answer declares `display: {"pid": "id"}` and its data holds `running.debug.pid`
- **THEN** that field renders with the identifier role

#### Scenario: A dotted declaration matches nothing
- **WHEN** an answer declares `display: {"running.pid": "id"}`
- **THEN** no field receives a role from that entry

### Requirement: A paired role requires its partner in the same object

`{"progressOf": "<field>"}` and `{"limitOf": "<field>"}` describe one fact carried by two fields.
The framework SHALL resolve the partner **only among the sibling keys of the object carrying the
roled field**, and SHALL NOT search for it elsewhere in the answer.

When the partner is absent, or is not a number, the paired role SHALL be dropped and the value
rendered as it would be with no declaration.

Both failure modes were designed against, and the second is the dangerous one. A missing partner
invites an invented denominator — a confident lie. A partner found at any depth would match a field
belonging to a *different* run or section, producing a bar that is not merely wrong but plausible.

#### Scenario: A pair renders as one fact
- **WHEN** an object holds `tasksDone: 6` and `tasksTotal: 7`, and `display` declares
  `{"tasksDone": {"progressOf": "tasksTotal"}}`
- **THEN** the surface renders a progress indication for that pair

#### Scenario: A half pair renders as a plain number
- **WHEN** the same declaration applies to an object holding `tasksDone` but no `tasksTotal`
- **THEN** no progress indication is drawn, and `tasksDone` renders as an ordinary value

#### Scenario: A partner elsewhere in the answer is not borrowed
- **WHEN** the roled field's own object has no partner, but another object in the same answer has a
  field of the partner's name
- **THEN** the role is still dropped

### Requirement: Presence is counted from the data, never from the declaration

The framework SHALL derive which roles apply from the fields actually present in `data`. A declared
name that the data does not carry SHALL produce nothing at all — no role, no placeholder, and no
statement that something is missing or hidden.

A declaration is not data. A surface that reports on declared-but-absent fields is announcing an
absence it has not measured, which is the more dangerous half of this defect class: an announcement
about nothing reads as information.

#### Scenario: A declaration wider than the answer
- **WHEN** `display` names ten fields and the answer's data carries three of them
- **THEN** three fields are roled and the surface says nothing about the other seven

### Requirement: A progress indication never replaces the values it summarises

Where a `progressOf` pair or a `limitOf` pair is rendered, the underlying numbers SHALL remain
visible, and any caveat attached to either field SHALL remain attached where the reader is standing.

A bar is a compaction, and the rule that governs every compaction on this surface governs this one:
it may never hide a failure. A bar at 6/7 looks like progress on a run that has not moved in an
hour, so it may summarise the numbers and may not stand in for them.

#### Scenario: The numbers survive the bar
- **WHEN** a progress pair is rendered as a bar
- **THEN** both the value and its partner remain readable on the same screen

#### Scenario: A caveat is not swallowed by the summary
- **WHEN** a field carrying a caveat is rendered inside a paired role
- **THEN** the caveat remains visible beside the rendered value
