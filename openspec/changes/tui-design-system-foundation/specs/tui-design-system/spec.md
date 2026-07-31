## ADDED Requirements

### Requirement: Status colour is named by meaning, through a token
The dashboard SHALL define its status colours as semantic design tokens in a Tailwind v4
`@theme` block in `web/src/index.css`. A token SHALL be named for what it means
(`--color-status-done`, `--color-status-active`, `--color-status-fail`,
`--color-status-warn`, `--color-status-blocked`, `--color-status-idle`), never for its hue.

Component source SHALL reference the token. A literal status colour class — `text-blue-400`,
`text-green-400`, `text-red-400`, `text-yellow-400`, `text-orange-400` — SHALL NOT appear
outside `web/src/index.css` and the primitive module.

This requirement exists because the same six meanings are currently re-derived by hand in **493
places across 47 files**, which is why one screen's "done" is a different blue from another's,
and why a future second surface cannot be reskinned at all.

#### Scenario: A component expresses a done status
- **WHEN** a component renders a merged or completed status
- **THEN** it applies the done-status token, and its source file contains no literal `blue-400`

#### Scenario: Meaning survives a palette change
- **WHEN** the value of `--color-status-fail` is changed in `index.css`
- **THEN** every failing indicator across every screen changes with it, and no component file is edited

### Requirement: Design-system drift fails the build
A unit test SHALL assert the design system's mechanical rules against the source tree and fail
when one is violated. It SHALL cover, at minimum: arbitrary font sizes (`text-[<n>px]`),
`font-mono` usages, and literal status colour classes.

The test SHALL report the offending file and line, SHALL carry its exemptions as an explicit
in-test list rather than as a pattern loose enough to admit new violations, and each exemption
SHALL state why it is exempt.

The reason this requirement exists is measurable: the three prose requirements below have been
in the specification since they were archived, and on 2026-07-31 the tree held **81 arbitrary
font sizes across 15 files** and **34 `font-mono` usages**. A rule nothing measures does not
hold.

#### Scenario: A reintroduced arbitrary font size fails
- **WHEN** a component adds `text-[11px]` and the unit suite runs
- **THEN** the drift test fails and names that file and line

#### Scenario: The test is proven to fire before its pass is believed
- **WHEN** a known violation is deliberately introduced and the drift test is run
- **THEN** it fails; and when the violation is removed it passes, so a green result distinguishes
  "clean" from "cannot detect"

## MODIFIED Requirements

### Requirement: Font size normalization
All text in the dashboard SHALL use one of three Tailwind preset sizes: `text-xs` (12px) for metadata and timestamps, `text-sm` (14px) for body text and table cells, `text-base` (16px) for section headers and emphasis. Arbitrary pixel sizes (`text-[9px]`, `text-[10px]`, `text-[11px]`) SHALL NOT be used.

Conformance SHALL be enforced by the drift test rather than by review. The 81 existing
violations across 15 files SHALL be migrated as part of this change, so that the test starts
from zero rather than from a grandfathered baseline.

#### Scenario: No arbitrary font sizes
- **WHEN** inspecting any rendered text element
- **THEN** the font size is 12px, 14px, or 16px (no 9px, 10px, or 11px values)

#### Scenario: The rule is measured, not assumed
- **WHEN** the unit suite runs against the source tree
- **THEN** a `text-[<n>px]` occurrence in any component file fails the run

### Requirement: Font-mono class removal
All individual `font-mono` class usages SHALL be removed since the global font is already monospace. This prevents redundant class application.

Conformance SHALL be enforced by the drift test. The Battle components remain exempt by prior
decision, and that exemption SHALL be stated in the test itself rather than implied by the
search pattern.

#### Scenario: No font-mono in components
- **WHEN** searching component source files for `font-mono`
- **THEN** zero matches are found (excluding Battle components which have independent styling)

#### Scenario: The exemption is explicit
- **WHEN** reading the drift test
- **THEN** the Battle exemption appears as a named entry with its reason, not as an absent pattern
