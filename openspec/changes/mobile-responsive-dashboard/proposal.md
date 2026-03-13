## Why

The wt-web dashboard is currently desktop-only: a fixed 224px sidebar, a table-based change list with 7 columns, and a pointer-drag resizable split panel. On mobile viewports (360-414px) the sidebar alone fills the screen, table columns overflow, and drag-to-resize is unusable on touch. Users need to monitor and interact with orchestration runs from their phone (Chrome on Android) over LAN or VPN.

## What Changes

- **Sidebar**: Hidden by default on mobile, accessible via hamburger menu as an overlay drawer
- **Tab bar**: Horizontally scrollable on narrow screens instead of wrapping/overflowing
- **ChangeTable**: Switches from `<table>` to stacked card layout on mobile with key info (name, status, duration, actions)
- **ResizableSplit**: Replaced with stacked panels on mobile — tab content full-width on top, log panel as a collapsible bottom sheet
- **StatusHeader**: Wraps to two lines on mobile — project+status on first line, stats+actions on second
- **Touch targets**: Minimum 44px tap targets, text sizes bumped from 9-11px to 13-14px on mobile
- **Server bind**: Default host changes from `127.0.0.1` to `0.0.0.0` so the dashboard is reachable from other devices on the network

## Capabilities

### New Capabilities
- `mobile-layout`: Responsive layout system — sidebar drawer, stacked panels, card-based change list, touch-friendly sizing for mobile viewports (<768px)

### Modified Capabilities
- `web-dashboard-spa`: Add responsive layout requirement — the dashboard SHALL adapt to mobile viewports with touch-friendly controls and readable text sizes

## Impact

- **Components affected**: `App.tsx` (sidebar → drawer), `Dashboard.tsx` (ResizableSplit → stacked), `ChangeTable.tsx` (table → cards), `StatusHeader.tsx` (flex-wrap), `ResizableSplit.tsx` (mobile bypass), tab bar in Dashboard
- **Server**: `cli.py` default host change from `127.0.0.1` to `0.0.0.0`
- **No new dependencies** — uses Tailwind responsive utilities (`md:` breakpoints) already in the project
- **No API changes** — all endpoints remain the same
