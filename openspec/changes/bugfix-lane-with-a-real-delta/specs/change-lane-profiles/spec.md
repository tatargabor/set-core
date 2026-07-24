## IN SCOPE
- A `bugfix` change type whose gate profile differs from every other one, and cannot be
  obtained without the difference being paid for
- How a project maps its own lane vocabulary onto set-core's change types
- Where the list of valid change types lives

## OUT OF SCOPE
- Choosing between differentiated pipelines — no router is specified anywhere
- Any entrance gate on whether a fix restores or changes a specification (see the design's D4)
- The lane signal mechanism itself, which is unchanged and already shipped

## ADDED Requirements

### Requirement: A lane entry SHALL NOT be able to exist without its behavioural delta
set-core SHALL refuse a `bugfix` declaration from a project that declares no enforced exit
obligation for it. The framework SHALL NOT substitute another change type's gate profile in
that case.

A taxonomy entry that resolves to the same behaviour as an existing one is a false gate: it is
read as meaning something and means nothing. Measured on this repository before the
requirement was written, `feature` and `foundational` are byte-identical, and nobody had
noticed. This requirement makes the new entry structurally incapable of joining them.

Falling back is refused for a reason that is not about danger — the substituted chain is
stricter, so nothing breaks. It is about belief: the project declared a lane, believes it has
one, and silently runs an ordinary change. A false belief is what carries a wrong decision
later.

#### Scenario: A bugfix declaration with no exit obligation is refused
- **WHEN** a change declares `change_type: bugfix` in a project that declares no enforced exit
  obligation for that type
- **THEN** set-core SHALL refuse the declaration with an error naming the missing obligation
- **AND** SHALL NOT resolve the change to another change type's gate profile
- **AND** SHALL NOT report the change as having a lane

#### Scenario: The refusal binds the declaration, not the project
- **WHEN** a project declares no `bugfix` lane at all
- **THEN** its changes SHALL behave exactly as they do today
- **AND** no additional strictness SHALL be applied to them

A project that does not ask for a discount cannot lose protection by not asking. An unknown
change type already applies no per-type defaults, so every universal gate stays blocking —
today's `bugfix` runs the strictest chain, and this requirement must not read as a loosening
of anything.

### Requirement: The project maps its lane vocabulary onto set-core's change types
A project SHALL declare which of its lane signals enforce a given change type, in one place.
set-core SHALL read that mapping and SHALL NOT contain one.

Only the project holds both halves: its own lane names and the set-core change type it
considers equivalent. A framework-side mapping would require a project whose lanes are called
something else to rename them, which is the design failing rather than the project.

#### Scenario: A signal's own lane label is not compared to a change type
- **WHEN** a lane signal declares a lane label that happens to equal a set-core change type
- **THEN** set-core SHALL NOT treat that coincidence as a mapping
- **AND** the mapping SHALL come only from the project's declaration

The two vocabularies overlapping in one project is the worst available reason to build a
coupling on the overlap.

#### Scenario: A near-miss key in the mapping is refused, not ignored
- **WHEN** the mapping declaration carries a key that differs from a known one only by prefix,
  suffix, plural, case or separator
- **THEN** set-core SHALL refuse it, naming both the declared key and the one it resembles
- **AND** SHALL NOT treat the mapping as absent

A silently absent mapping would mean "no exit obligation", which is the refusal path — so a
typo would present as a project that declared nothing, and the reason would be invisible.

### Requirement: An exit obligation counts only when it blocks
set-core SHALL treat a lane signal as an exit obligation only when it resolves to ENFORCE
severity for the change being verified. A signal evaluating at WARN SHALL NOT satisfy the
obligation.

An obligation that does not block leaves the discount unpaid: the entrance becomes cheaper and
nothing stops the defect returning. Lane signals already start at WARN and reach ENFORCE only
when the project's own declared measurement has been recorded, so this reuses a mechanism that
already refuses unproven promotions.

#### Scenario: A WARN-severity exit signal does not buy the cheaper entrance
- **WHEN** a project maps a lane signal to `bugfix` and that signal evaluates at WARN
- **THEN** the `bugfix` declaration SHALL be refused
- **AND** the error SHALL name the unpromoted signal rather than reporting the mapping absent

#### Scenario: The discount is not available on day one
- **WHEN** a project introduces an exit signal and immediately declares `bugfix`
- **THEN** the declaration SHALL be refused until the signal's own promotion condition has
  been satisfied and recorded

This ordering is the requirement, not a side effect of it: the evidence is the price of the
discount, so it cannot be paid afterwards.

### Requirement: The set of valid change types has one home
The valid change types SHALL be defined in exactly one place, and every other component that
needs the list SHALL derive it from there rather than restating it.

Measured before this requirement: the list exists in three places and two disagree. The gate
profile dictionary holds six; the planning skill restates the same six as a hand-written enum;
and the merge guard exempts a set containing two names that exist nowhere else, so its
exemption list names types nothing can produce. That third copy is harmless today — it exempts
nobody — which is exactly why it survived long enough to be read as authoritative.

#### Scenario: A type list that names a non-existent type is a defect
- **WHEN** a component names a change type that the single definition does not contain
- **THEN** that reference SHALL be treated as a defect and corrected
- **AND** SHALL NOT be preserved on the grounds that it currently matches nothing

#### Scenario: Adding a type reaches every consumer of the list
- **WHEN** a change type is added to the single definition
- **THEN** every component that validates or enumerates change types SHALL see it without a
  separate edit
