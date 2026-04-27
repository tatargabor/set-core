# Unified Navigation

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Single sidebar component replacing both ProjectLayout and ManagerLayout sidebars
- Two-section layout: global (Control Plane) + per-project (contextual)
- Pluggable sidebar registry for 3rd party navigation items
- Issue count badges always visible
- Active route highlighting across both /set and /manager routes
- Mobile responsive (drawer pattern preserved)
- Service health footer

### Out of scope
- Changing any existing page content (only navigation wrapper changes)
- Adding new pages (uses existing pages)
- Authentication or role-based menu visibility

## Requirements

### Requirement: Unified sidebar layout
The sidebar SHALL have two sections: a global "Control Plane" section at the top and a per-project section below. Both sections SHALL be visible regardless of current route.

#### Scenario: Sidebar structure
- **WHEN** any page loads
- **THEN** sidebar shows: Control Plane section (Overview, All Issues) above, project section (Dashboard, Issues, Sentinel, Worktrees, Memory, Settings) below

#### Scenario: Active route highlighting
- **WHEN** user is on /manager/craftbrew/issues
- **THEN** "Issues" under the project section is highlighted AND the project selector shows "craftbrew"

### Requirement: Cross-navigation
Navigation links SHALL work across route families. Clicking "Dashboard" from a /manager/* page SHALL navigate to /set/:project. Clicking "Issues" from a /set/* page SHALL navigate to /manager/:project/issues. No full page reload.

#### Scenario: Dashboard to Manager
- **WHEN** user clicks "Overview" in Control Plane section while on /set/craftbrew dashboard
- **THEN** navigates to /manager without page reload

#### Scenario: Manager to Dashboard
- **WHEN** user clicks "Dashboard" in project section while on /manager/craftbrew/issues
- **THEN** navigates to /set/craftbrew without page reload

### Requirement: Pluggable sidebar registry
The sidebar SHALL provide a registry where modules can register navigation items. Each registered item specifies: section (global or project), label, icon, route pattern, optional badge component, and sort order.

#### Scenario: 3rd party registers navigation item
- **WHEN** a module calls `registerSidebarItem({ section: 'project', label: 'Deployments', route: '/deploy/:project', icon: '🚀', order: 50 })`
- **THEN** a "Deployments" link appears in the project section of the sidebar

#### Scenario: Badge on registered item
- **WHEN** a module registers an item with a badge component that returns "3"
- **THEN** the sidebar item shows "Deployments (3)" with a colored badge

### Requirement: Issue count badges
The sidebar SHALL show issue count badges next to the "Issues" link (per-project) and "All Issues" link (global). Badges SHALL poll and update automatically.

#### Scenario: Issue badge updates
- **WHEN** a new issue is registered in the manager
- **THEN** the sidebar badge count increments within 5 seconds

### Requirement: Service health footer
The sidebar footer SHALL show the set-manager service health: green dot if running, red if unreachable. Clicking it SHALL navigate to /manager.

#### Scenario: Manager running
- **WHEN** set-manager API responds
- **THEN** footer shows green dot + "Manager: running"

#### Scenario: Manager not running
- **WHEN** set-manager API is unreachable
- **THEN** footer shows red dot + "Manager: offline"

### Requirement: Shared layout
Both `/set/*` and `/manager/*` routes SHALL use the same layout component with the unified sidebar. The separate `ManagerLayout` and `ProjectLayout` SHALL be merged into one.

#### Scenario: Same sidebar on both routes
- **WHEN** user navigates from /set/craftbrew to /manager/craftbrew/issues
- **THEN** the sidebar does not re-render or flash — it remains stable with only the active item changing
