# Tasks: Unified Sidebar Navigation

## 1. Sidebar Registry

- [x] 1.1 Create `web/src/lib/sidebarRegistry.ts` with `SidebarItem` type and `registerSidebarItem()` / `getSidebarItems()` functions [REQ: pluggable-sidebar-registry]
- [x] 1.2 Define `SidebarItem` interface: section ('global' | 'project'), label, icon, route, badge component, order number [REQ: pluggable-sidebar-registry]
- [x] 1.3 Register built-in items: Control Plane (Overview, All Issues), Project (Dashboard, Issues, Sentinel, Worktrees, Memory, Settings) [REQ: unified-sidebar-layout]

## 2. Unified Sidebar Component

- [x] 2.1 Create `web/src/components/UnifiedSidebar.tsx` with two-section layout (global + project) [REQ: unified-sidebar-layout]
- [x] 2.2 Render global section from registry items where section='global', sorted by order [REQ: unified-sidebar-layout]
- [x] 2.3 Render project section from registry items where section='project', sorted by order [REQ: unified-sidebar-layout]
- [x] 2.4 Implement active route highlighting that works across /set and /manager routes [REQ: unified-sidebar-layout]
- [x] 2.5 Preserve project selector dropdown from existing sidebar [REQ: unified-sidebar-layout]
- [x] 2.6 Add issue count badge next to Issues items (global + per-project) [REQ: issue-count-badges]
- [x] 2.7 Add service health footer: green/red dot + "Manager: running/offline" [REQ: service-health-footer]
- [x] 2.8 Preserve mobile drawer pattern (hamburger → slide-out) [REQ: unified-sidebar-layout]

## 3. Shared Layout

- [x] 3.1 Create `web/src/components/SharedLayout.tsx` that wraps sidebar + main content area [REQ: shared-layout]
- [x] 3.2 Refactor App.tsx: replace separate ProjectLayout and ManagerLayout with SharedLayout [REQ: shared-layout]
- [x] 3.3 Move route definitions into SharedLayout so sidebar remains stable across navigation [REQ: shared-layout]
- [x] 3.4 Ensure sidebar does not re-render/flash on route changes [REQ: shared-layout]

## 4. Cross-Navigation

- [x] 4.1 Update route links: Dashboard → /set/:project, Issues → /manager/:project/issues, Overview → /manager [REQ: cross-navigation]
- [x] 4.2 Ensure project context is preserved when switching between /set and /manager routes [REQ: cross-navigation]
- [x] 4.3 Remove old "Manager Console" link from ProjectLayout sidebar [REQ: cross-navigation]
- [x] 4.4 Remove separate ManagerLayout sidebar (now in UnifiedSidebar) [REQ: shared-layout]

## 5. Badges & Polling

- [x] 5.1 Create `web/src/hooks/useSidebarStats.ts` that polls issue stats for badge counts [REQ: issue-count-badges]
- [x] 5.2 Wire badge component into registered sidebar items for Issues links [REQ: issue-count-badges]
- [x] 5.3 Wire manager health check into sidebar footer [REQ: service-health-footer]

## 6. Cleanup

- [x] 6.1 Remove ManagerLayout from App.tsx [REQ: shared-layout]
- [x] 6.2 Remove sidebar code from Manager.tsx page (keep content only) [REQ: shared-layout]
- [x] 6.3 Verify all existing routes still work (/set/*, /manager/*) [REQ: cross-navigation]
- [x] 6.4 Verify mobile responsiveness preserved [REQ: unified-sidebar-layout]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN any page loads THEN sidebar shows Control Plane + project sections [REQ: unified-sidebar-layout, scenario: sidebar-structure]
- [x] AC-2: WHEN on /manager/craftbrew/issues THEN Issues is highlighted and project selector shows craftbrew [REQ: unified-sidebar-layout, scenario: active-route-highlighting]
- [x] AC-3: WHEN clicking Overview from /set/craftbrew THEN navigates to /manager without reload [REQ: cross-navigation, scenario: dashboard-to-manager]
- [x] AC-4: WHEN clicking Dashboard from /manager/craftbrew/issues THEN navigates to /set/craftbrew without reload [REQ: cross-navigation, scenario: manager-to-dashboard]
- [x] AC-5: WHEN module registers sidebar item THEN it appears in correct section [REQ: pluggable-sidebar-registry, scenario: 3rd-party-registers-navigation-item]
- [x] AC-6: WHEN new issue registered THEN badge count increments within 5s [REQ: issue-count-badges, scenario: issue-badge-updates]
- [x] AC-7: WHEN manager API responds THEN footer shows green + running [REQ: service-health-footer, scenario: manager-running]
- [x] AC-8: WHEN manager unreachable THEN footer shows red + offline [REQ: service-health-footer, scenario: manager-not-running]
- [x] AC-9: WHEN navigating between /set and /manager THEN sidebar stays stable [REQ: shared-layout, scenario: same-sidebar-on-both-routes]
