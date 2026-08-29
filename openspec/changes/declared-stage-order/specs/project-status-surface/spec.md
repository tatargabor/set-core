## ADDED Requirements

### Requirement: A declared stage order governs presentation, and a value outside it stays visible and marked

Where a field carries a declared stage order, the surface SHALL present that field's values in the
declared order, SHALL draw a declared stage that holds no rows, and SHALL draw any value absent from
the declared order **visibly and distinctly**.

A value outside the order SHALL NOT be dropped, and SHALL NOT be sorted silently to the end. Sorting
it last without a mark is the failure this requirement exists to prevent: it is indistinguishable on
screen from a genuine final stage, so a mis-keyed value reads as finished work.

This undertaking is what buys the other half of the agreement — the producer keeps its "nothing
matched" bucket *outside* the declared order, so that "nothing matched" stays sayable, rather than
declaring it as a stage where it would be indistinguishable from a real one. A producer relying on
this SHALL NOT need to invent a private sentinel value.

The mark SHALL identify the value as outside the declared process, not as an error: an unmatched
value is a legitimate state of the producer's data, and may be the first sight of a stage the
declaration has not caught up with.

Rendering choice remains the framework's. Columns, a grouped list, or one ordered table column all
satisfy this requirement; nothing here promises a board.

#### Scenario: A declared stage holding nothing is drawn
- **WHEN** the order declares a stage that no row matches
- **THEN** that stage appears in its declared position, shown as holding no rows

#### Scenario: A value outside the order is visible and marked
- **WHEN** a row carries a stage value that appears nowhere in the declared order
- **THEN** the row is present on screen and is marked as outside the declared order

#### Scenario: An unmatched value is never quietly last
- **WHEN** rows carry a mix of declared values and one undeclared value
- **THEN** the undeclared value is not rendered as an unmarked final stage, and cannot be mistaken
  for the end of the process

#### Scenario: An absent declaration changes nothing
- **WHEN** no stage order is declared for a field
- **THEN** that field's values are ordered exactly as they are today, with no stage presentation
  applied
