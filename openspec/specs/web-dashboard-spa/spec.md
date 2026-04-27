# Capability: web-dashboard-spa (delta)

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Manager overview page
The manager overview page at `/manager` SHALL display registered projects as clickable summary tiles that link to individual project detail pages.

#### Scenario: Tile displays summary
- **WHEN** the manager overview loads with registered projects
- **THEN** each tile shows project name, mode badge, sentinel status (running/idle), and if running: progress summary (e.g., "5/12 merged, 1.8M tokens")

#### Scenario: Tile links to detail
- **WHEN** user clicks a project tile
- **THEN** browser navigates to `/manager/:project` detail view

#### Scenario: No inline process controls on tiles
- **WHEN** the overview page renders
- **THEN** tiles do NOT contain Start/Stop/Restart buttons — process control lives in the detail view only
