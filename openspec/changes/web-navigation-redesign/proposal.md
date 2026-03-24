# Proposal: Web Navigation Redesign

## Why

The web dashboard mixes two URL prefixes (`/set/:project/*` and `/manager/:project/*`) creating confusing navigation. The sidebar shows a flat list of menu items that jump between these prefixes, causing the "issues" route segment to be misinterpreted as a project name. Dashboard and Sentinel point to the same URL. 3rd party apps have no clear integration point. The mental model is broken — the user sees one project but navigates two disconnected "apps."

## What Changes

- **Unified URL prefix**: Replace `/set/:project/*` and `/manager/:project/*` with a single `/p/:name/*` prefix. All project-specific routes live under this.
- **Hierarchical sidebar**: Replace flat menu list with a two-level structure — Level 1: "app" selector (Orchestration, Sentinel, Issues, Memory, Settings), Level 2: dynamic sub-items for the selected app.
- **App-scoped content**: Dashboard tabs (Changes, Phases, Log, Tokens, Sessions, Agent, Learnings, Battle) are distributed into their natural app sections instead of being tabs on a single monolithic page.
- **Sentinel gets its own page**: Sentinel control (start/stop/restart + spec path), sentinel sessions, and agent chat become a dedicated section instead of being split between Manager ProjectDetail and Dashboard tabs.
- **3rd party app registration**: The existing `registerSidebarItem` API evolves into `registerApp` — plugins register top-level apps with their own sub-items and routes.
- **Global vs project context**: When no project is selected, sidebar shows global items (Overview, All Issues). When a project is selected, sidebar shows the app selector with sub-items.
- **Remove /manager/ and /set/ prefixes**: These become legacy redirects for bookmarks.

## Capabilities

### New Capabilities

- `sidebar-app-model` — Hierarchical sidebar with app registration, two-level navigation, and dynamic sub-items
- `unified-project-routes` — Single `/p/:name/` URL prefix replacing `/set/` and `/manager/` split

### Modified Capabilities

- (none — existing specs like `web-dashboard-spa` describe the current tab-based approach which this replaces wholesale)

## Impact

- **web/src/App.tsx** — Complete routing overhaul (new route tree under `/p/:name/`)
- **web/src/lib/sidebarRegistry.ts** — New `SidebarApp` type with children, replaces flat `SidebarItem` model
- **web/src/components/UnifiedSidebar.tsx** — Two-level rendering (app selector + sub-items)
- **web/src/pages/** — Existing pages reorganized, Dashboard.tsx split into app-specific pages
- **All page components** — URL params change from `useParams` to prop-based project passing
- **Legacy redirects** — `/set/:project` → `/p/:name/orch`, `/manager/:project/issues` → `/p/:name/issues`
