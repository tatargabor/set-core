## MODIFIED Requirements

### Requirement: Colour states the reported severity, and one weight means one thing

The screen SHALL colour a window's mark from the severity the measurement reports, and SHALL NOT
compute a band of its own. The colour reserved for a critical window SHALL NOT be used decoratively
anywhere in the strip.

The severity a measurement reports is the severity its source stated, or — for a source that
states none — the band its measurement applied, in the one place that source's specification
defines. The screen cannot tell those apart and does not need to: its rule is the same either
way, take the severity the record carries and never derive one from the percentage. With more
than one source behind one strip, wording on the screen SHALL NOT attribute a band to the
service, because for one of the sources that attribution is not true.

#### Scenario: A window arrives labelled critical

- **WHEN** the measurement reports a window's severity as critical
- **THEN** that window's mark is drawn in the critical colour

#### Scenario: A window arrives labelled normal

- **WHEN** the measurement reports a window's severity as normal
- **THEN** the mark is not drawn in the critical colour, whatever its percentage

#### Scenario: A window banded at measurement

- **WHEN** a window's severity was banded by its own source's measurement rather than stated
  by that source's upstream
- **THEN** the screen colours it by that severity through the same rule as any other window,
  and no wording on the screen names the service as the band's author
