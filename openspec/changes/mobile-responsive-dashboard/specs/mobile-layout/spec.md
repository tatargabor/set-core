## ADDED Requirements

### Requirement: Mobile sidebar drawer
On viewports below 768px, the sidebar SHALL be hidden by default and accessible via a hamburger menu button. The sidebar SHALL slide in from the left as an overlay drawer with a semi-transparent backdrop. Tapping the backdrop or a navigation link SHALL close the drawer.

#### Scenario: Open sidebar on mobile
- **WHEN** user taps the hamburger button on a mobile viewport
- **THEN** the sidebar slides in from the left with a dark backdrop overlay

#### Scenario: Close sidebar by backdrop tap
- **WHEN** the sidebar drawer is open and user taps the backdrop
- **THEN** the sidebar slides out and the backdrop disappears

#### Scenario: Close sidebar on navigation
- **WHEN** the sidebar drawer is open and user taps a navigation link
- **THEN** the sidebar closes and the selected page loads

#### Scenario: Desktop sidebar unchanged
- **WHEN** viewport is 768px or wider
- **THEN** the sidebar is statically visible as before (no hamburger, no overlay)

### Requirement: Mobile top bar
On viewports below 768px, a fixed top bar SHALL be displayed containing the hamburger menu button, the project name, and the connection status indicator.

#### Scenario: Mobile top bar content
- **WHEN** a project is selected on a mobile viewport
- **THEN** the top bar shows a hamburger icon, the project name, and a green/red connection dot

### Requirement: Touch-friendly tap targets
On viewports below 768px, all interactive elements (buttons, links, tab items) SHALL have a minimum touch target of 44px height. Text sizes for body content SHALL be at least 13px.

#### Scenario: Button tap targets
- **WHEN** the dashboard renders on a mobile viewport
- **THEN** all action buttons (Approve, Stop, Skip) have at least 44px touch target height

#### Scenario: Tab tap targets
- **WHEN** the tab bar renders on a mobile viewport
- **THEN** each tab item has at least 44px height

### Requirement: Mobile change cards
On viewports below 768px, the change list SHALL render as stacked cards instead of a table. Each card SHALL show the change name, status badge, duration, and action buttons. Gate indicators SHALL remain visible. Token breakdown and session count MAY be hidden.

#### Scenario: Card layout on mobile
- **WHEN** the dashboard shows 5 changes on a mobile viewport
- **THEN** 5 stacked cards are rendered, each showing name, status, duration, and action buttons

#### Scenario: Card actions
- **WHEN** a change card shows a running change on mobile
- **THEN** the card includes a Stop button with 44px minimum tap target

#### Scenario: Desktop table unchanged
- **WHEN** the viewport is 768px or wider
- **THEN** the change list renders as the existing table layout

### Requirement: Stacked panel layout on mobile
On viewports below 768px, the ResizableSplit SHALL be replaced with a stacked layout: tab content takes full available height, and the log panel renders as a collapsible bottom bar. The drag handle SHALL NOT appear on mobile.

#### Scenario: Log panel collapsed by default
- **WHEN** the dashboard loads on a mobile viewport
- **THEN** the tab content fills the screen and a "Logs" bar appears at the bottom

#### Scenario: Expand log panel
- **WHEN** user taps the "Logs" bar on mobile
- **THEN** the log panel expands to approximately 60% of viewport height

#### Scenario: Collapse log panel
- **WHEN** the log panel is expanded and user taps the "Logs" bar header
- **THEN** the log panel collapses back to the bottom bar

### Requirement: Scrollable tab bar on mobile
On viewports below 768px, the tab bar SHALL be horizontally scrollable when tabs overflow the viewport width. The active tab SHALL auto-scroll into view.

#### Scenario: Tab overflow scroll
- **WHEN** 7 tabs render on a 360px viewport
- **THEN** the tab bar is horizontally scrollable and does not wrap

#### Scenario: Active tab visible
- **WHEN** user switches to a tab that is off-screen in the scrollable area
- **THEN** the tab bar scrolls to make the active tab visible

### Requirement: Responsive status header
On viewports below 768px, the status header SHALL wrap its content across multiple lines: project name with status badge on the first line, statistics and action buttons on the second line.

#### Scenario: Header wrapping on mobile
- **WHEN** the status header renders on a 360px viewport
- **THEN** project info appears on the first line and stats/actions on the second line

#### Scenario: Desktop header unchanged
- **WHEN** the viewport is 768px or wider
- **THEN** the status header renders in a single line as before
