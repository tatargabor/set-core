## IN SCOPE
- The envelope's optional `caveats` key, as a field the reader accepts and carries

## OUT OF SCOPE
- What a caveat means, where it renders, and how it resolves — all of that belongs to the
  `status-contract-caveats` capability, which this delta deliberately does not duplicate

## MODIFIED Requirements

### Requirement: An answer is an envelope, validated before it is trusted
The reader SHALL accept a JSON object carrying `contractVersion`, `ok`, and — when `ok` is
true — `data`, and MAY carry `generatedAt`, `deprecated` and `caveats`.

A malformed `caveats` SHALL NOT invalidate the answer. The command succeeded and the value is
right; the caveat is what qualifies it, so refusing the whole envelope over its decoration would
turn a cosmetic defect into a missing measurement — the direction this capability exists to
prevent.

*Why this delta exists at all, recorded because the change that introduced it got it wrong first:*
the proposal for `status-contract-caveats` declared no modified capabilities, on the reasoning
that caveats are additive. They are — but adding a key the reader consumes **changes what the
envelope is**, and the envelope belongs to this capability. It was caught by
`test_the_capability_spec_names_the_same_vocabulary_the_reader_emits`, which exists precisely
because a specification silent about behaviour that exists is not a smaller specification but a
wrong one. The guard was written for a future drift and caught its first one here.

#### Scenario: Unsupported contract version
- **WHEN** an answer declares a `contractVersion` this set-core does not support
- **THEN** the reader SHALL refuse it rather than guess at its shape

#### Scenario: The project answers that it could not answer
- **WHEN** an answer carries `ok: false`
- **THEN** the reader SHALL carry the project's own reason through, taking `error`, or
  `message` when `error` is absent
- **AND** SHALL produce a result whose reason states plainly that the project reported a
  failure with no reason, when neither field is present

#### Scenario: An envelope carrying a malformed caveats value still answers
- **WHEN** an answer is otherwise valid and its `caveats` is not a mapping of key to sentence
- **THEN** the reader SHALL keep `ok` true and carry `data` unchanged
- **AND** SHALL carry no caveats rather than refusing the answer
