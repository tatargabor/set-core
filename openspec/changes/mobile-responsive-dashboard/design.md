## Context

The wt-web dashboard is a React 19 SPA using Tailwind CSS 4, served by a FastAPI/Uvicorn backend. The current layout assumes desktop viewports: a fixed `w-56` (224px) sidebar in `App.tsx`, a `<table>` in `ChangeTable.tsx`, and a pointer-drag `ResizableSplit` for the content/log split. All font sizes are 9-11px. None of these patterns work on a 360-414px mobile viewport.

The project already uses Tailwind CSS 4, which provides responsive breakpoints (`md:`, `lg:`) out of the box. No additional CSS framework is needed.

## Goals / Non-Goals

**Goals:**
- Dashboard usable on mobile Chrome (Android, 360-414px width)
- Same URL, same app — responsive, not a separate mobile build
- Touch-friendly: 44px minimum tap targets, readable text
- Core mobile workflows: view change status, see logs, approve/stop/skip
- Server reachable from other devices (LAN/VPN) via `0.0.0.0` bind

**Non-Goals:**
- Native app or PWA (no offline, no install prompt)
- Tablet-specific layouts (tablet gets desktop layout via `md:` breakpoint)
- Redesigning the desktop layout — mobile-only changes, desktop stays the same
- New features — this is purely responsive adaptation

## Decisions

### D1: Tailwind responsive breakpoints, not separate components

**Decision**: Use `md:` (768px) breakpoint to conditionally show/hide and restyle existing components. Mobile is the base, desktop is the `md:` override.

**Alternatives considered**:
- Separate `MobileDashboard.tsx` — rejected: duplicates logic, diverges over time
- `useMediaQuery()` hook with conditional rendering — rejected: heavier, SSR-unfriendly, same component tree works with CSS

**Approach**: Write mobile-first classes, add `md:` prefixes for desktop behavior. Example: `hidden md:flex` for sidebar, `flex md:hidden` for hamburger button.

### D2: Sidebar → off-canvas drawer on mobile

**Decision**: The sidebar in `App.tsx` (`ProjectLayout`) becomes a slide-in drawer on mobile, toggled by a hamburger button in a new mobile top bar.

**Implementation**:
- Add `sidebarOpen` state to `ProjectLayout`
- Sidebar gets: `fixed inset-y-0 left-0 z-40 w-64 transform -translate-x-full transition-transform` on mobile, shown via `translate-x-0` when open
- Backdrop overlay when drawer is open (click to close)
- Desktop: sidebar remains static with `md:relative md:translate-x-0`
- Hamburger button: `md:hidden` in a new mobile header bar

### D3: ChangeTable → card layout on mobile

**Decision**: On mobile, render each change as a stacked card instead of a table row.

**Implementation**:
- Add a `useIsMobile()` hook (simple `window.innerWidth < 768` with resize listener) for conditional rendering — this is the one case where CSS alone isn't enough (need different DOM structure)
- Mobile card shows: name (bold), status badge, duration, action buttons
- Token breakdown and session count hidden on mobile (secondary info)
- Gate bar remains visible (compact, already works narrow)
- Desktop: existing `<table>` unchanged

### D4: ResizableSplit → stacked with collapsible log on mobile

**Decision**: On mobile, replace the drag-split with a full-height tab content area and a bottom collapsible log sheet.

**Implementation**:
- `ResizableSplit` gets a `mobile` prop (or uses `useIsMobile()`)
- Mobile mode: top panel takes full height, bottom panel renders as a fixed-bottom bar ("Logs ▲") that expands to 60vh on tap
- No drag handle on mobile — just tap to expand/collapse
- Desktop: unchanged pointer-drag behavior

### D5: StatusHeader wraps on mobile

**Decision**: Use `flex-wrap` so the header naturally breaks to two lines on narrow screens.

**Implementation**:
- First line: project name + status badge + connection dot
- Second line: stats (version, duration, tokens) + action buttons
- Buttons get `min-h-[44px]` on mobile for touch targets
- `text-xs` → `text-sm` on mobile for readability

### D6: Tab bar horizontal scroll on mobile

**Decision**: Tab bar gets `overflow-x-auto` and `flex-nowrap` on mobile so tabs scroll horizontally.

**Implementation**:
- Wrap tab bar in a container with `overflow-x-auto scrollbar-hide`
- Each tab gets `whitespace-nowrap` and `min-w-fit`
- Active tab auto-scrolls into view via `scrollIntoView()`
- Desktop: unchanged (tabs fit in one row)

### D7: Server default host → 0.0.0.0

**Decision**: Change the default bind from `127.0.0.1` to `0.0.0.0` in `cli.py`.

**Rationale**: This is a development tool running locally. Binding to all interfaces lets phones on the same network reach it without requiring `--host 0.0.0.0` every time. Users who want to restrict can use `--host 127.0.0.1`.

## Risks / Trade-offs

- **[Risk] 0.0.0.0 exposes dashboard to LAN** → Acceptable for a dev tool. No auth, no sensitive mutations. Add a note in `--help` text.
- **[Risk] useIsMobile hook causes re-render on resize** → Debounce with 150ms delay, only triggers on crossing the 768px boundary.
- **[Risk] Card layout may look different from table** → Intentional; cards are the standard mobile pattern for data lists. Info hierarchy preserved.
- **[Risk] Log bottom sheet may cover action buttons** → Log sheet caps at 60vh, always leaves status header visible.
