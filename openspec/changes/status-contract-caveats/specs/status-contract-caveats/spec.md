## IN SCOPE
- How a project declares that a correct value means something narrower than its name suggests
- How that declaration reaches the reader without the framework interpreting it
- Where a caveat must appear relative to the value it qualifies
- What the framework reports about a declared caveat whose key is absent from the answer

## OUT OF SCOPE
- Any framework-side caveat text, key name, or key vocabulary
- Any judgement about whether a caveat's sentence explains anything
- Any gate, threshold, or blocking behaviour derived from caveats
- Replacement semantics — a per-field caveat never replaces the command-level one

## ADDED Requirements

### Requirement: A project declares caveats and the framework interprets none of them
The status envelope SHALL carry an optional `caveats` object mapping a key to a single sentence.
Every sentence SHALL come from the producer. The framework SHALL NOT contain any caveat text, any
caveat key, or any rule deriving one value's caveat from another's.

A caveat states that a correct value means something narrower than its name suggests. Only the
producer can write that sentence: it describes their register, their collection method, their
known blind spot. A framework-supplied caveat would be right for whoever it was written against
and quietly wrong for everyone else, while looking authoritative to both.

#### Scenario: An envelope without caveats behaves exactly as before
- **WHEN** a project's answer carries no `caveats` key
- **THEN** the framework SHALL render the answer exactly as it does today
- **AND** SHALL NOT report that any caveat is missing, hidden, or suppressed

#### Scenario: A caveat key the framework has never seen is carried unchanged
- **WHEN** the `caveats` object uses keys drawn from the project's own vocabulary
- **THEN** the framework SHALL carry them verbatim
- **AND** SHALL NOT require, validate, or normalise the key against any known set

### Requirement: The command-level default always applies and per-field caveats add to it
A `"*"` key in `caveats` SHALL carry the command-level default, which always applies to that
command's values. A per-field key SHALL be treated as an ADDITION to `"*"`, never as a
replacement, and the framework SHALL provide no marker by which a producer can request
replacement.

The deciding argument is direction rather than elegance. If a producer forgets a per-field entry
under additive semantics, the general caveat still stands — the safe loss. Under replacement, the
narrower sentence silently swallows the broader one, which is a quiet loss of the more general and
usually more important statement. The same asymmetry makes a mistyped per-field key survivable:
the `"*"` still renders, so the number is never left with nothing beside it.

#### Scenario: A value with its own caveat still carries the command-level one
- **WHEN** `caveats` declares both `"*"` and a key matching a rendered field
- **THEN** the reader SHALL be shown both
- **AND** the per-field sentence SHALL NOT suppress the `"*"` sentence

#### Scenario: A mistyped per-field key loses only the narrow half
- **WHEN** a per-field caveat key matches no field in the answer, and `"*"` is declared
- **THEN** the `"*"` caveat SHALL still be shown against that command's values
- **AND** no value SHALL be rendered with no caveat at all

### Requirement: The count comes from the data and the declaration only says what to look for
The framework SHALL determine which caveats to display by looking for the declared keys IN THE
ANSWER, and SHALL NOT derive any count, badge, or statement from the declaration alone.

A declaration is a claim about the data, and a claim can be wrong. Counting from the declaration
produced a measured defect elsewhere in this envelope — an announcement that a field was hidden
when the project had stopped sending it — which is a false *absence*, the mirror of the false
value this whole family of signals exists to prevent.

#### Scenario: A caveat for a field the project no longer sends is silent
- **WHEN** `caveats` declares a per-field key that appears nowhere in the answer
- **THEN** nothing SHALL be rendered for that key beside any value
- **AND** the framework SHALL NOT state that a caveat was hidden or withheld

### Requirement: A declared key absent from the answer is diagnostics, never a gate
The framework SHALL be able to list, on request, which declared caveat keys are absent from the
current answer. That listing SHALL NOT block, fail, warn on the main surface, or carry a count
into any status summary.

The framework cannot distinguish a typo from a legitimate absence, and it must not pretend to: a
producer's per-status breakdown may legitimately list only the statuses currently present, so a
caveat keyed on a currently-zero status is correct AND absent. A gate firing daily on that is dead
within a week and takes the real warning with it. The producer recognises which is which at a
glance; the framework's job is to make the question visible, not to answer it.

#### Scenario: An absent declared key is listable but does not fail anything
- **WHEN** `caveats` declares a key that the answer does not contain
- **THEN** that key SHALL appear in the diagnostics listing
- **AND** no gate, exit status, or on-screen alarm SHALL change

### Requirement: A caveat renders beside the value it qualifies
A per-field caveat SHALL be rendered adjacent to the value it qualifies. The `"*"` caveat SHALL be
rendered once, in the header of the command's section. Neither SHALL be rendered only in a
tooltip, only behind an interaction, or only on another tab.

This is the mechanism rather than a presentation preference. The defect being fixed is that the
number travels and the caveat does not, so a caveat one interaction away has not been carried —
it has been filed. It is also the standing layout rule: anything hidden that changes how a value
should be read must be marked where the reader is standing.

#### Scenario: The command-level caveat is stated once, not repeated per value
- **WHEN** `"*"` is declared and the command renders many values
- **THEN** the `"*"` sentence SHALL appear once in that section's header
- **AND** SHALL NOT be repeated beside every value

### Requirement: A caveat is not an alarm and the framework never infers that it is
The framework SHALL render caveats at a visual weight distinct from failures and warnings, and
SHALL NOT derive urgency, severity, or alarm from a caveat's key name or its text.

One visual weight per meaning: if red means broken, a caveat is not red. A caveat says a correct
number means something narrower — neither a failure nor a warning. A producer's field whose name
sounds alarming is still not an alarm unless the producer says so, and the framework has no names
with which to decide otherwise.

#### Scenario: An alarming-sounding key gets no alarming treatment
- **WHEN** a caveat key or sentence contains words such as expired, suspect, or failed
- **THEN** the caveat SHALL render at caveat weight
- **AND** SHALL NOT be styled as an error or counted as one
