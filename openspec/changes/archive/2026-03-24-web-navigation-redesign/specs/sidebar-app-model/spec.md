# Spec: sidebar-app-model

## ADDED Requirements

## IN SCOPE
- Two-level sidebar navigation (app selector + sub-items)
- App registration API for built-in and 3rd party apps
- Dynamic sub-item rendering based on selected app
- Global vs project context switching in sidebar
- Active state highlighting for apps and sub-items

## OUT OF SCOPE
- Drag-and-drop sidebar reordering
- User-customizable sidebar layouts
- Collapsible/pinnable sidebar (keep current responsive behavior)
- Badge/notification system redesign (keep existing badge props)

### Requirement: App registration API

The sidebar registry SHALL support registering top-level "apps" with nested sub-items. Each app SHALL have an `id`, `label`, `icon`, `order`, and a `children` array of sub-items. The existing `registerSidebarItem` function SHALL be replaced by `registerApp`. Each sub-item SHALL have an `id`, `label`, `route` pattern, and optional `matchPatterns` for active state detection.

#### Scenario: Built-in app registration
- **WHEN** the sidebar registry module is imported
- **THEN** 5 built-in apps are registered with labels: "Orchestration", "Sentinel", "Issues", "Memory", "Settings"

#### Scenario: 3rd party app registration
- **WHEN** a plugin calls `registerApp` with a valid app definition
- **THEN** the app appears in the sidebar sorted by its `order` value
- **AND** its sub-items render when the app is selected

### Requirement: Two-level sidebar rendering

The sidebar SHALL render two distinct levels when a project is selected. Level 1 shows app icons/labels as a vertical list. Level 2 shows the sub-items of the currently active app. The active app SHALL be determined by matching the current URL path against registered app routes and their children's routes.

#### Scenario: App selection via URL
- **WHEN** the URL is `/p/my-project/orch/sessions`
- **THEN** the Orchestration app is highlighted at level 1
- **AND** the "Sessions" sub-item is highlighted at level 2

#### Scenario: Clicking a different app
- **WHEN** the user clicks "Issues" in the app selector
- **THEN** the sidebar navigates to `/p/:name/issues` (the app's default route)
- **AND** level 2 updates to show Issues sub-items

### Requirement: Global vs project context

The sidebar SHALL show different content depending on whether a project is selected. When no project is selected, the sidebar SHALL show global items (Overview, All Issues). When a project is selected, the sidebar SHALL show the app selector with sub-items. The project selector dropdown SHALL remain visible in both contexts.

#### Scenario: No project selected
- **WHEN** the user navigates to `/` or deselects a project
- **THEN** the sidebar shows global items: Overview, All Issues
- **AND** the app selector is hidden

#### Scenario: Project selected
- **WHEN** the user selects a project from the dropdown
- **THEN** the sidebar shows the app selector with sub-items
- **AND** global items are hidden (accessible via project deselection)
