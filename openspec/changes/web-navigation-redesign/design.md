# Design: Web Navigation Redesign

## Context

The web dashboard evolved organically with two separate URL spaces (`/set/*` for orchestration dashboard, `/manager/*` for project management). This creates routing bugs (e.g., "issues" parsed as project name), confusing navigation (Sentinel and Dashboard point to same URL), and no clear integration point for 3rd party plugins.

The sidebar uses a flat `SidebarItem[]` registry with `global | project` sections. The current 8-tab Dashboard page is monolithic — all orchestration views packed into one component with tab switching.

## Goals / Non-Goals

**Goals:**
- Single URL prefix (`/p/:name/`) — no more /set/ vs /manager/ confusion
- Two-level sidebar — app selector (level 1) + app-specific sub-items (level 2)
- Each "app" (Orchestration, Sentinel, Issues, Memory, Settings) gets its own route tree and sidebar section
- Plugin-friendly: 3rd party apps register with `registerApp()` and get sidebar + routing automatically

**Non-Goals:**
- Changing the visual design (dark theme, layout proportions stay the same)
- Rewriting page component internals (only routing/props change)
- Adding new features to existing pages

## Decisions

### D1: URL structure — `/p/:name/app/sub`

Use `/p/:name/` as the prefix (short, clean). Each app owns a segment:

```
/p/:name/orch              → Orchestration (Changes view, default)
/p/:name/orch/sessions     → Sessions
/p/:name/orch/worktrees    → Worktrees
/p/:name/orch/log          → Log
/p/:name/orch/tokens       → Tokens
/p/:name/orch/learnings    → Learnings
/p/:name/sentinel          → Sentinel control + sessions
/p/:name/sentinel/chat     → Agent chat
/p/:name/issues            → Issues list
/p/:name/issues/:id        → Issue detail (future)
/p/:name/memory            → Memory browser
/p/:name/settings          → Settings
/p/:name/settings/mutes    → Mute patterns (sub-page of Settings)
```

**Why `/p/` not `/project/`:** URLs are typed and shared. Shorter is better. `/p/` is unambiguous.

### D2: Sidebar registry — `registerApp()` replaces `registerSidebarItem()`

```typescript
interface SidebarApp {
  id: string              // 'orchestration', 'sentinel', etc.
  label: string
  icon: string
  order: number
  defaultRoute: string    // '/p/:name/orch' — where clicking the app goes
  children: SidebarSubItem[]
}

interface SidebarSubItem {
  id: string
  label: string
  route: string           // '/p/:name/orch/sessions'
  matchPatterns?: string[]
  badge?: ComponentType<{ project: string | null }>
}
```

Built-in apps are registered at import time (same pattern as current). 3rd party plugins call `registerApp()`.

### D3: Dashboard split — monolithic page → separate routes

Current `Dashboard.tsx` renders 8 tabs in one component. Split into:
- `OrchOverview.tsx` — Changes view (the main table + phases) — the default page for Orchestration app
- `OrchSessions.tsx` — Sessions list + detail (reuse existing SessionViewer)
- `OrchLog.tsx` — Log viewer (extract from Dashboard)
- `OrchTokens.tsx` — Token chart (extract from Dashboard)
- `OrchLearnings.tsx` — Learnings panel (extract from Dashboard)
- `Worktrees.tsx` — stays as-is (already separate)

These are lightweight extractions — pull the tab content into its own file, add route.

**Why not keep tabs?** Tabs force all content into one route. With separate routes, the sidebar sub-items directly link to each view, and the URL is bookmarkable.

### D4: Sentinel gets a real page

Current state: Sentinel control lives in Manager's `ProjectDetail.tsx`, sentinel sessions show in Dashboard's Sessions tab, Agent chat is a Dashboard tab. Merge these into:
- `SentinelPage.tsx` — Status + Start/Stop/Restart controls + spec path input + recent sessions list
- `SentinelChat.tsx` — Agent chat (move from OrchestrationChat)

### D5: Mute Patterns → Settings sub-route

Mute Patterns is a rarely-used settings page. Move from top-level sidebar item to `/p/:name/settings/mutes`. Settings page gets a sub-nav: Config | Mutes.

### D6: Legacy redirects via React Router Navigate

Add redirect routes at the top of the route tree:
```tsx
<Route path="/set/:project" element={<Navigate to={...} replace />} />
<Route path="/manager/:project/issues" element={<Navigate to={...} replace />} />
```

Keep these for 3-6 months, then remove.

### D7: Global context (no project selected)

When no project is selected (`/` or `/projects`):
- Sidebar shows: Overview (multi-project cards), All Issues
- The project selector shows "(select project)"
- Selecting a project navigates to `/p/:name/orch`

## Risks / Trade-offs

- [Risk] Bookmarks to old `/set/` and `/manager/` URLs break → Legacy redirects mitigate this
- [Risk] Large diff touching many files → Mitigate by extracting Dashboard tabs first (mechanical), then rewiring routes
- [Risk] 3rd party plugins using old `registerSidebarItem` → Keep as deprecated alias for one release cycle

## Open Questions

- Should "Battle" view (run comparison) stay under Orchestration or become its own app? (Leaning: keep under Orch as `/p/:name/orch/battle`)
