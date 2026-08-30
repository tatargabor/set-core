## ADDED Requirements

### Requirement: The wire view owns the right edge while shown

When the wire view is shown, it SHALL take the board's right edge; right-edge docked
bands collapse for the duration and restore their stored arrangement when the wire
view is hidden. Hiding MUST NOT discard any dock band's stored edge, size, or
collapsed state.

#### Scenario: Right-edge bands yield and return

- **WHEN** the wire view toggles on while right-edge bands are docked, then off again
- **THEN** during the on state no right-edge band occupies the edge and the gutter does
- **AND** after toggling off the bands return on the right edge with the same edge,
  size, and collapsed state they had before
