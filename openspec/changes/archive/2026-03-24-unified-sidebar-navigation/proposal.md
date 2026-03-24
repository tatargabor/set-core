# Unified Sidebar Navigation

## Why

The set-web UI currently has two separate navigation worlds: the existing Dashboard (`/set/:project/*`) and the new Manager console (`/manager/*`). Each has its own sidebar and layout. Users cannot navigate between them intuitively — there's only a small "Manager Console" link buried in the Dashboard sidebar. This creates a fragmented experience where issue counts and control plane status are invisible when viewing the Dashboard, and project details are invisible when viewing the Manager.

## What Changes

- **Unified sidebar** that combines both Dashboard and Manager navigation in a single component
- **Control Plane section** at the top of the sidebar (global: Overview, All Issues)
- **Per-project section** with all pages from both worlds (Dashboard, Issues, Sentinel, Worktrees, Memory, Settings)
- **Shared layout component** used by both `/set/*` and `/manager/*` routes
- **Pluggable sidebar registry** — 3rd party modules can register custom navigation items (sections, links, badges) via a simple API
- **Issue count badges** visible in the sidebar at all times
- **Manager service health indicator** in the sidebar footer
- Remove the separate `ManagerLayout` — both route families share one layout

## Capabilities

### New Capabilities
- `unified-navigation`: Single sidebar component with cross-navigation, pluggable sections for 3rd party extensions

### Modified Capabilities
- None (no spec-level behavior changes, only UI navigation structure)

## Impact

- `web/src/App.tsx` — remove separate layouts, use unified layout for all routes
- `web/src/components/` — new `UnifiedSidebar.tsx` component
- `web/src/pages/Manager.tsx` — remove sidebar duplication, content-only
- Existing pages unchanged (just wrapped in new layout)
