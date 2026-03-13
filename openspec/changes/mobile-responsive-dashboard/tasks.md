## 1. Foundation

- [x] 1.1 Create `useIsMobile()` hook in `web/src/hooks/useIsMobile.ts` — returns boolean for viewport < 768px, debounced resize listener (150ms), only triggers on boundary crossing
- [x] 1.2 Change default host from `127.0.0.1` to `0.0.0.0` in `lib/wt_orch/cli.py` `cmd_serve`, update help text to note the bind address

## 2. Sidebar Drawer

- [x] 2.1 Add `sidebarOpen` state and hamburger toggle button to `ProjectLayout` in `App.tsx`
- [x] 2.2 Convert sidebar `<aside>` to off-canvas drawer on mobile: `fixed inset-y-0 left-0 z-40` with slide transform, backdrop overlay, `md:relative md:translate-x-0` for desktop
- [x] 2.3 Add mobile top bar (`md:hidden`) with hamburger button, project name, and connection dot
- [x] 2.4 Close drawer on navigation link click and backdrop tap

## 3. Status Header

- [x] 3.1 Make `StatusHeader` responsive: `flex-wrap` on mobile, project+status on first line, stats+actions on second line
- [x] 3.2 Bump action buttons to `min-h-[44px]` and text to `text-sm` on mobile viewports

## 4. Tab Bar

- [x] 4.1 Add `overflow-x-auto` and `flex-nowrap` to the tab bar container in `Dashboard.tsx` for mobile
- [x] 4.2 Add `whitespace-nowrap min-w-fit` to tab buttons, bump tap target to 44px on mobile
- [x] 4.3 Auto-scroll active tab into view with `scrollIntoView()` on tab change

## 5. Change Cards

- [x] 5.1 Create mobile card variant in `ChangeTable.tsx` — conditional render based on `useIsMobile()`: stacked cards showing name, status badge, duration, gate bar, action buttons
- [x] 5.2 Hide token breakdown and session count columns on mobile cards
- [x] 5.3 Ensure action buttons (Stop, Skip) have 44px minimum tap targets in card layout

## 6. Stacked Panels

- [x] 6.1 Update `ResizableSplit` to accept mobile mode — when mobile: top panel full height, no drag handle
- [x] 6.2 Add collapsible log bottom bar on mobile: collapsed shows "Logs ▲" bar, expanded shows log panel at ~60vh
- [x] 6.3 Wire log expand/collapse toggle with tap (no drag) on mobile

## 7. Build and Verify

- [x] 7.1 Run `npm run build` in `web/` to verify no TypeScript errors
- [ ] 7.2 Test mobile layout in Chrome DevTools responsive mode (360px, 414px) — verify sidebar drawer, cards, tab scroll, log panel, and tap targets
