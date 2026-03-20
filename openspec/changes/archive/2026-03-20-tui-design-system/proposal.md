# Proposal: TUI Design System

## Why

The set-web dashboard uses inconsistent font sizing (6 different arbitrary pixel sizes from 9px to 11px), a sans-serif base font with scattered `font-mono` overrides, and text that's too small for mobile use. The result is a UI with no clear visual hierarchy and poor readability, especially on mobile devices. The Battle tab already establishes a terminal/TUI aesthetic that the rest of the dashboard should match.

## What Changes

### Phase 1: Global monospace font
- Override `body` font-family to monospace stack in `index.css`
- Remove all individual `font-mono` class usage (now redundant)

### Phase 2: Font size normalization
- Replace all `text-[9px]`, `text-[10px]`, `text-[11px]` arbitrary values with Tailwind preset sizes
- Establish 3-tier hierarchy: `text-xs` (metadata), `text-sm` (body/default), `text-base` (headers)

### Phase 3: TUI visual elements
- Replace HTML div progress bars with block-character text bars (████░░)
- Replace dot status indicators with Unicode characters (● ◉ ○ ✕)
- Add section divider headers (── HEADER ──)

### Phase 4: Mobile layout improvements
- Ensure touch targets meet 44px minimum on interactive elements
- Accordion-style domain cards on mobile instead of dropdown picker

## Capabilities

### New Capabilities
- `tui-design-system`: Global monospace-first design system with normalized sizing and TUI visual elements

### Modified Capabilities
- (none)

## Impact

- **All frontend files**: ~37 component files affected by font-mono removal and size normalization
- **index.css**: Global font-family override
- **No backend changes**
- **No API changes**
- **Visual breaking change**: Entire UI appearance shifts to monospace
