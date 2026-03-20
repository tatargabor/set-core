# tui-design-system Specification

## Purpose
TBD - created by archiving change tui-design-system. Update Purpose after archive.
## Requirements
### Requirement: Global monospace font
The dashboard SHALL use a monospace font stack as the base font-family for all text. The stack SHALL be `ui-monospace, 'Cascadia Code', 'Fira Code', Menlo, Monaco, Consolas, monospace`.

#### Scenario: Font applied globally
- **WHEN** any page of the dashboard loads
- **THEN** all text renders in monospace font

### Requirement: Font size normalization
All text in the dashboard SHALL use one of three Tailwind preset sizes: `text-xs` (12px) for metadata and timestamps, `text-sm` (14px) for body text and table cells, `text-base` (16px) for section headers and emphasis. Arbitrary pixel sizes (`text-[9px]`, `text-[10px]`, `text-[11px]`) SHALL NOT be used.

#### Scenario: No arbitrary font sizes
- **WHEN** inspecting any rendered text element
- **THEN** the font size is 12px, 14px, or 16px (no 9px, 10px, or 11px values)

### Requirement: Font-mono class removal
All individual `font-mono` class usages SHALL be removed since the global font is already monospace. This prevents redundant class application.

#### Scenario: No font-mono in components
- **WHEN** searching component source files for `font-mono`
- **THEN** zero matches are found (excluding Battle components which have independent styling)

### Requirement: Block-character progress bars
Progress indicators SHALL use Unicode block characters instead of HTML div bars. The format SHALL be `████░░░░ N/M (P%)` using full-block (U+2588) for filled and light-shade (U+2591) for empty, rendered as inline text.

#### Scenario: Domain progress display
- **WHEN** viewing a domain's progress
- **THEN** progress shows as `████████░░ 9/10 (90%)` text, not a colored div bar

### Requirement: Unicode status indicators
Status indicators SHALL use Unicode characters instead of colored dots: `●` (U+25CF) for done/merged, `◉` (U+25C9) for running/active, `○` (U+25CB) for pending/planned, `✕` (U+2715) for failed.

#### Scenario: Change status display
- **WHEN** viewing a change or requirement status
- **THEN** status uses a Unicode character with color instead of a rounded-full div dot

### Requirement: Section divider headers
Section headers within panels SHALL use line-character dividers in the format `── HEADER ──` to create visual separation between content areas.

#### Scenario: Domain card sections
- **WHEN** viewing a domain card with requirements, dependencies, and sources
- **THEN** each section is separated by a `── REQUIREMENTS ──` style header

### Requirement: Mobile touch targets
All interactive elements (buttons, tabs, expandable rows) SHALL have a minimum height of 44px on mobile viewports (below md breakpoint) to meet touch accessibility guidelines.

#### Scenario: Mobile tab buttons
- **WHEN** viewing the dashboard on a mobile viewport
- **THEN** all tab buttons have at least 44px touch target height

