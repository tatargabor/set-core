# Design: TUI Design System

## Context

The set-web dashboard uses system-ui sans-serif as base font with scattered font-mono overrides (~60% of text). Font sizes are arbitrary pixel values (9-11px) with no clear hierarchy. The Battle tab already establishes a terminal/TUI aesthetic. This change unifies the entire app under a monospace-first design.

## Goals / Non-Goals

**Goals:**
- Consistent monospace typography across all pages
- Readable text on both desktop and mobile (minimum 12px)
- TUI aesthetic matching the Battle tab's feel
- Clean 3-tier size hierarchy

**Non-Goals:**
- Changing layout structure or navigation
- Modifying the color palette
- Adding external font dependencies (CDN/web fonts)

## Decisions

### 1. System monospace stack, no web fonts
**Decision:** Use `ui-monospace, 'Cascadia Code', 'Fira Code', Menlo, Monaco, Consolas, monospace` in index.css body.
**Rationale:** System fonts are instant (no FOUT), available on all platforms. JetBrains Mono is excellent but requires loading. The system stack is good enough — Cascadia Code on Windows, Menlo on macOS, monospace fallback on Linux.

### 2. Three-tier size hierarchy via search-and-replace
**Decision:** Mechanical replacement: `text-[9px]` → `text-xs`, `text-[10px]` → `text-xs`, `text-[11px]` → `text-sm`. Keep existing `text-xs`, `text-sm`, `text-base`, `text-lg` usages as-is.
**Rationale:** This is a safe mechanical transformation. The 9-11px range all collapse to xs/sm which provides enough differentiation while being readable.

### 3. Block-character progress as a shared utility component
**Decision:** Create a `TuiProgress` component that renders `████░░░░ N/M (P%)` as colored text.
**Rationale:** Progress bars appear in 8+ places (domain sidebar, domain card, AC summary, overview, phase view, etc.). A shared component ensures consistency and makes future style changes trivial.

### 4. Status indicator as a shared utility
**Decision:** Create a `TuiStatus` component mapping status strings to Unicode + color.
**Rationale:** Status dots appear in 10+ places. A shared component replaces `<span className="w-2 h-2 rounded-full bg-{color}">` everywhere.

### 5. Section dividers as thin bordered headers
**Decision:** Use `── HEADER ──` text in `text-xs text-neutral-500 uppercase tracking-wider` styling.
**Rationale:** Lighter than a full border-b, more terminal-like, creates clear section breaks.

## Risks / Trade-offs

- [Risk] Monospace text is wider than sans-serif → table columns may need width adjustment → Mitigation: `truncate` class handles overflow, test with real data
- [Risk] Mechanical font-size replacement might make some UI too large → Mitigation: Review each component after replacement, adjust locally where needed
- [Risk] Block-character progress may not render well in all fonts → Mitigation: The characters U+2588 and U+2591 are in all monospace fonts
