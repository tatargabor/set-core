# Tasks: Web Navigation Redesign

## 1. Sidebar Registry Overhaul

- [x] 1.1 Define `SidebarApp` and `SidebarSubItem` interfaces in `sidebarRegistry.ts` [REQ: app-registration-api]
- [x] 1.2 Implement `registerApp()` function that stores apps with children [REQ: app-registration-api]
- [x] 1.3 Add `getApps()` and `getGlobalItems()` helper functions [REQ: app-registration-api]
- [x] 1.4 Register 5 built-in apps (Orchestration, Sentinel, Issues, Memory, Settings) with sub-items — label "Orchestration" not "Dashboard" [REQ: app-registration-api]
- [x] 1.5 Register global items (Overview, All Issues) for no-project context [REQ: global-vs-project-context]
- [x] 1.6 Deprecate `registerSidebarItem()` — keep as alias that wraps into a single-child app [REQ: app-registration-api]

## 2. Sidebar Component Rewrite

- [x] 2.1 Rewrite `UnifiedSidebar.tsx` to render two levels: app selector (level 1) + sub-items (level 2) [REQ: two-level-sidebar-rendering]
- [x] 2.2 Implement active app detection from current URL path [REQ: two-level-sidebar-rendering]
- [x] 2.3 Implement global vs project context switching — show global items when no project, app selector when project selected [REQ: global-vs-project-context]
- [x] 2.4 Preserve project selector dropdown position and behavior [REQ: global-vs-project-context]
- [x] 2.5 Ensure mobile responsive behavior works with two-level sidebar [REQ: two-level-sidebar-rendering]

## 3. Route Tree Overhaul

- [x] 3.1 Define new route tree in `App.tsx` under `/p/:name/*` with nested routes per app [REQ: unified-url-prefix]
- [x] 3.2 Create `ProjectLayout` component that extracts `:name` param and passes `project` prop to children [REQ: prop-based-project-passing]
- [x] 3.3 Add legacy redirect routes: `/set/:project/*` → `/p/:name/orch/*`, `/manager/:project/*` → `/p/:name/*` [REQ: legacy-redirects]
- [x] 3.4 Add global routes: `/` → Overview, `/issues` → All Issues [REQ: unified-url-prefix]
- [x] 3.5 Remove old `SharedLayout` component and its conditional page rendering [REQ: unified-url-prefix]

## 4. Dashboard Split — Extract Tab Content

- [x] 4.1 Extract Changes view from `Dashboard.tsx` into `OrchOverview.tsx` (the default Orchestration page) [REQ: unified-url-prefix]
- [x] 4.2 Extract Sessions tab into `OrchSessions.tsx` at `/p/:name/orch/sessions` [REQ: unified-url-prefix]
- [x] 4.3 Extract Log tab into `OrchLog.tsx` at `/p/:name/orch/log` [REQ: unified-url-prefix]
- [x] 4.4 Extract Tokens tab into `OrchTokens.tsx` at `/p/:name/orch/tokens` [REQ: unified-url-prefix]
- [x] 4.5 Extract Learnings tab into `OrchLearnings.tsx` at `/p/:name/orch/learnings` [REQ: unified-url-prefix]
- [x] 4.6 Keep Battle view as `/p/:name/orch/battle` (extract from Dashboard) [REQ: unified-url-prefix]
- [x] 4.7 Keep Phases as sub-content within OrchDashboard (not separate route) [REQ: unified-url-prefix]

## 5. Sentinel Page

- [x] 5.1 Create `SentinelPage.tsx` combining: status/controls from `SentinelControl`, session list, spec path input [REQ: unified-url-prefix]
- [x] 5.2 Move `OrchestrationChat.tsx` to `SentinelChat.tsx` at `/p/:name/sentinel/chat` [REQ: unified-url-prefix]
- [x] 5.3 Remove Sentinel from old Manager `ProjectDetail.tsx` (it now has its own page) [REQ: unified-url-prefix]

## 6. Page Component Cleanup

- [x] 6.1 Update `ManagerIssues.tsx` → `IssuesPage.tsx` — receive project as prop, route at `/p/:name/issues` [REQ: prop-based-project-passing]
- [x] 6.2 Move `ManagerMutes.tsx` into Settings sub-route at `/p/:name/settings/mutes` [REQ: prop-based-project-passing]
- [x] 6.3 Update `Settings.tsx` to add sub-navigation (Config | Mutes) [REQ: prop-based-project-passing]
- [x] 6.4 Update `Memory.tsx` to receive project as prop, route at `/p/:name/memory` [REQ: prop-based-project-passing]
- [x] 6.5 Update `Worktrees.tsx` to route at `/p/:name/orch/worktrees` [REQ: prop-based-project-passing]
- [x] 6.6 Update `Manager.tsx` (overview) to route at `/` (global, no project) [REQ: unified-url-prefix]
- [x] 6.7 Remove `ProjectDetail.tsx` — its content is split between SentinelPage and Overview [REQ: unified-url-prefix]

## 7. Build & Verify

- [x] 7.1 TypeScript compile check — 0 errors [REQ: unified-url-prefix]
- [x] 7.2 Build web dist (`pnpm run build`) [REQ: unified-url-prefix]
- [x] 7.3 Verify all routes render correctly by manual navigation [REQ: unified-url-prefix]
- [x] 7.4 Verify legacy redirects work for old bookmarks [REQ: legacy-redirects]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN sidebar module imported THEN 5 built-in apps registered [REQ: app-registration-api, scenario: built-in-app-registration]
- [x] AC-2: WHEN plugin calls registerApp THEN app appears in sidebar sorted by order [REQ: app-registration-api, scenario: 3rd-party-app-registration]
- [x] AC-3: WHEN URL is /p/my-project/orch/sessions THEN Orchestration app highlighted AND Sessions sub-item highlighted [REQ: two-level-sidebar-rendering, scenario: app-selection-via-url]
- [x] AC-4: WHEN user clicks Issues app THEN navigates to /p/:name/issues AND level 2 updates [REQ: two-level-sidebar-rendering, scenario: clicking-a-different-app]
- [x] AC-5: WHEN no project selected THEN sidebar shows Overview and All Issues [REQ: global-vs-project-context, scenario: no-project-selected]
- [x] AC-6: WHEN project selected THEN sidebar shows app selector with sub-items [REQ: global-vs-project-context, scenario: project-selected]
- [x] AC-7: WHEN user visits /p/craftbrew/orch THEN Orchestration dashboard renders [REQ: unified-url-prefix, scenario: orchestration-routes]
- [x] AC-8: WHEN user visits /p/craftbrew/sentinel THEN Sentinel page renders [REQ: unified-url-prefix, scenario: sentinel-routes]
- [x] AC-9: WHEN user visits /set/minishop-run2 THEN redirects to /p/minishop-run2/orch [REQ: legacy-redirects, scenario: old-set-url-redirect]
- [x] AC-10: WHEN user visits /manager/minishop-run2/issues THEN redirects to /p/minishop-run2/issues [REQ: legacy-redirects, scenario: old-manager-url-redirect]
- [x] AC-11: WHEN SharedLayout renders a page THEN page receives project as string prop [REQ: prop-based-project-passing, scenario: page-receives-project-prop]
