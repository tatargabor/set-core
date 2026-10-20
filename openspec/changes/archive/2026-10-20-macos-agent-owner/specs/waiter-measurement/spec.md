## IN SCOPE
- Reading the machine's waiter processes on a platform without `/proc`.
- Preserving the distinction between "measured, none found" and "could not measure".
- The per-waiter facts the fleet needs: identity, the rooms it waits on, and its
  working directory when the platform will give one.

## OUT OF SCOPE
- What a waiter is for, and the instruct/broadcast behaviour built on top of it.
- Removing or installing waiters — this spec covers reading them only.
- Whether an unmeasurable working directory makes a waiter removable; that decision
  belongs to the caller and is unchanged.

## ADDED Requirements

### Requirement: Waiters are read through a platform-appropriate process source

The waiter reader SHALL obtain the machine's process list through a source the
running platform provides — `/proc` where it exists, and the platform's own process
table where it does not — and SHALL return the same shape from either.

#### Scenario: macOS returns a measurement rather than a permanent failure
- **WHEN** waiters are read on macOS
- **THEN** the result is a measured list, empty or otherwise
- **AND** it is not the "could not measure" answer

#### Scenario: Linux behaviour is unchanged
- **WHEN** waiters are read on Linux
- **THEN** the result is the same as before this change for the same running processes

### Requirement: "Could not measure" is never widened into "there are none"

The reader SHALL return a distinct value when the process source could not be read at
all, and callers SHALL render that as a failure to measure.

An empty list invites installing a waiter; an unreadable process table invites doing
nothing. Collapsing the two produces the one action the reader must not take on the
strength of no evidence.

#### Scenario: An unreadable process source is reported as such
- **WHEN** the process source cannot be read
- **THEN** the reader returns the could-not-measure value, not an empty list
- **AND** the surface reports that nothing is known about what is listening

#### Scenario: A genuinely empty machine is reported as measured
- **WHEN** the process source is readable and holds no waiter
- **THEN** the reader returns an empty measured list
- **AND** the surface does not claim the process table was unreadable

### Requirement: A fact the platform will not give is absent, not invented

A per-waiter fact the platform will not supply SHALL be reported as unknown, and the
waiter SHALL still be listed — a working directory needing privileges the reader does
not have, for instance.

A waiter dropped from the list because one of its fields could not be read is a live
process the surface stops accounting for, which is the same false-absence this
capability exists to prevent.

#### Scenario: A waiter with an unreadable working directory is still listed
- **WHEN** a waiter's working directory cannot be read
- **THEN** the waiter appears in the measured list with its directory unknown
- **AND** it is not omitted

#### Scenario: An unknown field is not filled with a guess
- **WHEN** a per-waiter fact cannot be read
- **THEN** the value is reported as unknown rather than defaulted to a plausible one
