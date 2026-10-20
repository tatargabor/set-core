## MODIFIED Requirements

### Requirement: The role vocabulary is closed, and an unknown role is inert

The framework SHALL recognise exactly these roles: `id`, `path`, `duration-seconds`, `count`, and
the three paired forms `{"progressOf": "<field>"}`, `{"limitOf": "<field>"}` and
`{"stageOrder": ["<stage>", …]}`.

`stageOrder` differs from the other paired forms in its argument only: an array of non-empty strings
rather than a field name. A `stageOrder` whose argument is not an array, or whose array holds a
non-string or an empty string, SHALL leave the field unroled — the same inert outcome as any other
malformed declaration, never a partial order.

An unrecognised role SHALL be ignored silently — not reported as an error, and not allowed to
suppress the value. A malformed `display` key (not an object, or values of the wrong shape) SHALL
leave every field unroled rather than failing the answer.

The fail direction is the whole point. If an unknown role were refused, a producer shipping a new
role would blank a working surface, and the framework would be dictating the producer's release
order. Ignoring means the value renders the way it does today and starts rendering better whenever
the framework learns the role.

The vocabulary SHALL stay closed at seven. No role naming a colour, an icon, a label, a width or a
position is admitted. The *order* of a process is data because the process belongs to the project;
appearance is decided here.

#### Scenario: A producer ships a role the framework does not know yet
- **WHEN** an answer declares `display: {"size": "bytes"}` and `bytes` is not a recognised role
- **THEN** `size` renders as it would with no declaration at all, and nothing on screen reports a
  problem

#### Scenario: A malformed declaration does not cost the answer
- **WHEN** an answer's `display` is a list, a string, or null
- **THEN** the answer renders in full with no roles applied

#### Scenario: A stage order is carried through as a role
- **WHEN** an answer declares `display: {"lane": {"stageOrder": ["planned", "done"]}}`
- **THEN** the `lane` field carries a stage role whose declared order is exactly
  `["planned", "done"]`

#### Scenario: A malformed stage order leaves the field unroled rather than half-ordered
- **WHEN** a `stageOrder` argument is a string, is an empty array, or contains a non-string or an
  empty string
- **THEN** the field carries no stage role at all, and the answer renders in full

## ADDED Requirements

### Requirement: A declared stage order is static, and is never computed from the answer

The declared order SHALL be read from the declaration alone. The framework SHALL NOT derive,
extend, reorder or filter it using the values present in the answer.

This is the condition that carries the others. An order computed from the data loses exactly the
empty stage the producer is asking to preserve, and it makes the order a function of the filter —
so two readers looking at different subsets of the same board would see different processes and
neither would be told. Measured precedent: a producer's `display` block was observed shrinking from
eleven entries to five because it was computed from what happened to be present.

Consequently a stage named in the order but matched by no value in the answer SHALL remain part of
the order, and the framework SHALL be able to report it as present-and-empty rather than absent.

This SHALL NOT be read as overriding "Presence is counted from the data, never from the
declaration". The two requirements govern different objects, and the boundary is exact:

- **Whether the FIELD is roled at all** is decided by the data. A field the answer does not carry
  produces no role, no placeholder and no statement of absence — unchanged.
- **Once the field IS present, which STAGES exist** is decided by the declaration. The stages are
  not the field; they are the vocabulary the field's values are drawn from.

So an answer carrying no rows at all yields nothing, exactly as today; an answer carrying the field
with only one stage's worth of values yields the whole declared order. A producer that wants an
all-empty board rendered must therefore emit the field, because the field's presence is what makes
the declaration applicable.

#### Scenario: An empty declared stage survives
- **WHEN** an order declares `["planned", "specified", "done"]` and no value in the answer is
  `specified`
- **THEN** `specified` is still part of the resolved order, in position, marked as holding nothing

#### Scenario: Two answers over different value sets yield the same order
- **WHEN** the same declaration is resolved against one answer holding only `planned` values and
  another holding only `done` values
- **THEN** both resolve to the identical declared order, in the identical positions

#### Scenario: A field the answer does not carry stays unroled despite its declaration
- **WHEN** `display` declares a stage order for `lane` and no row in the answer carries `lane`
- **THEN** nothing is roled and the surface says nothing about the declared stages — the declaration
  alone never conjures a process onto the screen

#### Scenario: A value outside the order never extends it
- **WHEN** the answer holds a value that appears nowhere in the declared order
- **THEN** the declared order is unchanged — the value is not appended to it and does not displace
  any declared stage
