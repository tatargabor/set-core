# Design: Issue Management Console

## Context

The issue-management-engine change provides a set-manager service with REST API for process supervision and issue management. This change builds the web UI that consumes that API. The existing set-web already has pages for Dashboard, BattleView, Memory, Settings, and Worktrees. The console adds new pages under `/manager` for project overview, issue management, and per-issue interaction.

## Goals / Non-Goals

**Goals:**
- Full issue lifecycle management from the browser
- Process control (start/stop sentinel/orchestrator) from the browser
- Per-issue unified timeline combining system events and agent chat
- State-aware action buttons that only show valid actions
- Real-time updates via polling (2s for issues, 5s for project overview)

**Non-Goals:**
- Mobile-optimized layout (desktop-first, basic responsive)
- Replacing existing Dashboard/Sentinel pages (coexist under separate routes)
- Offline support or PWA features
- Custom theming beyond existing Tailwind dark mode

## Decisions

### D1: Routing — `/manager` prefix, separate from existing pages

**Decision:** All console pages live under `/manager/*`. Existing pages (`/:project/dashboard`, etc.) remain unchanged.

**Alternatives considered:**
- **Integrate into existing Dashboard** — too crowded, different mental model (monitoring vs management)
- **Separate app** — unnecessary complexity, shares components and auth

**Rationale:** `/manager` is a distinct workspace. Users go there to manage projects and issues, not to watch orchestration progress. Clean separation, shared codebase.

### D2: Issue detail — slide-out panel, not full page

**Decision:** Clicking an issue opens a slide-out panel (50-60% width) from the right. The issue list remains visible behind.

**Alternatives considered:**
- **Full page** — loses list context, requires back navigation
- **Modal** — too constrained for the timeline + chat content
- **Split pane** (permanent) — wastes space when no issue is selected

**Rationale:** Slide-out is the standard pattern for detail views in list-based UIs (Linear, GitHub PRs, Jira). Users can quickly switch between issues without losing list context. If space is too tight for timeline, the panel can expand to full width via a toggle.

### D3: Unified timeline — single stream, three visual styles

**Decision:** The "Console" is a unified timeline that merges audit log entries (system events) and chat messages (user + agent) into one chronological stream. Each entry type has distinct visual styling.

**Alternatives considered:**
- **Separate tabs** (Action Log + Console) — forces context switching, misses the interleaving that tells the story
- **Side-by-side** (events left, chat right) — takes too much space in a slide-out

**Rationale:** Research confirms this is the established pattern (PagerDuty, GitHub Issues, Slack incident channels). System events are centered/gray/small, user messages right-aligned/blue, agent messages left-aligned/gray. Visual hierarchy is enough to distinguish types without spatial separation.

### D4: State-aware buttons — explicit mapping, not computed

**Decision:** Each IssueState has a hardcoded list of available actions. Buttons not in the list for the current state are hidden (not disabled).

**Alternatives considered:**
- **Computed from transition table** — would show too many options (e.g., DIAGNOSED could technically go to MUTED, but that's a secondary action)
- **All buttons always shown, disabled** — cluttered, confusing

**Rationale:** The button map is a UX decision, not a state machine mirror. Some valid transitions (like DISMISSED → nothing) don't need buttons. Explicit mapping keeps the UI clean and intentional.

### D5: Polling, not WebSocket for issues

**Decision:** Issue list and detail use HTTP polling (2s interval). Only per-issue chat uses WebSocket (reusing existing chat.py infrastructure).

**Alternatives considered:**
- **WebSocket for everything** — more complex server-side, existing sentinel data already polls successfully at 1s
- **Server-Sent Events** — simpler than WS but still requires server changes

**Rationale:** Polling at 2s is proven in set-web (sentinel panel polls at 1s). The manager API serves JSON — no streaming needed. Only chat needs bidirectional streaming, and that's already built.

### D6: API proxy through set-web

**Decision:** set-web proxies `/api/manager/*` requests to set-manager's port (3112). The browser only talks to set-web.

**Alternatives considered:**
- **Direct browser → set-manager** — CORS issues, two ports to manage
- **set-manager serves UI too** — duplicates static serving, complicates deployment

**Rationale:** Single origin, no CORS. set-web already has the proxy pattern for its own API. Adding a proxy rule for `/api/manager/*` is trivial.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Polling overhead with many issues | Slow UI, high API load | Only poll detail when panel is open; collapse resolved issues |
| Chat session expiry | Can't resume investigation conversation | Fallback to new session with investigation report as context |
| Slide-out too narrow for timeline | Poor chat UX | Add full-width toggle button; test with real content |
| set-manager not running | Empty/broken UI | Graceful degradation with clear "service not running" message |
| Many states × many buttons | Confusing UX | Explicit button map tested against all 13 states |

## Open Questions

1. **Sidebar navigation** — should the manager get its own sidebar, or reuse the existing project selector with an added "Manager" section?
2. **Issue sound/notification** — should the browser play a sound when a new issue needs attention? Or rely on Discord/email notifications only?
