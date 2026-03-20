# Tasks: TUI Design System

## 1. Global monospace font

- [x] 1.1 Update index.css body font-family to monospace stack [REQ: global-monospace-font]

## 2. Remove font-mono classes

- [x] 2.1 Remove all `font-mono` class usages from components (excluding battle/) [REQ: font-mono-class-removal]

## 3. Font size normalization

- [x] 3.1 Replace all `text-[9px]` with `text-xs` across all components [REQ: font-size-normalization]
- [x] 3.2 Replace all `text-[10px]` with `text-xs` across all components [REQ: font-size-normalization]
- [x] 3.3 Replace all `text-[11px]` with `text-sm` across all components [REQ: font-size-normalization]

## 4. TUI utility components

- [x] 4.1 Create TuiProgress component: renders ████░░ N/M (P%) as colored inline text [REQ: block-character-progress-bars]
- [x] 4.2 Create TuiStatus component: maps status string to Unicode char + color [REQ: unicode-status-indicators]
- [x] 4.3 Create TuiSection component: renders ── HEADER ── divider line [REQ: section-divider-headers]

## 5. Apply TUI components to DigestView

- [x] 5.1 Replace div progress bars with TuiProgress in DigestView (domain sidebar, domain card, AC summary) [REQ: block-character-progress-bars]
- [x] 5.2 Replace status dots/text with TuiStatus in DigestView [REQ: unicode-status-indicators]
- [x] 5.3 Replace section headers with TuiSection in DigestView domain cards [REQ: section-divider-headers]

## 6. Apply TUI components to Dashboard components

- [x] 6.1 Replace progress bars with TuiProgress in StatusHeader, PhaseView, ChangeTable [REQ: block-character-progress-bars]
- [x] 6.2 Replace status dots with TuiStatus in ChangeTable, PhaseView, App sidebar [REQ: unicode-status-indicators]
- [x] 6.3 Replace section headers with TuiSection where applicable [REQ: section-divider-headers]

## 7. Apply TUI components to other pages

- [x] 7.1 Apply TuiProgress and TuiStatus to Worktrees page [REQ: block-character-progress-bars]
- [x] 7.2 Apply TuiProgress and TuiStatus to Home page [REQ: unicode-status-indicators]

## 8. Mobile touch targets

- [x] 8.1 Ensure all tab buttons have min-h-[44px] on mobile across Dashboard, DigestView sub-tabs [REQ: mobile-touch-targets]
- [x] 8.2 Ensure expandable rows and interactive elements meet 44px minimum on mobile [REQ: mobile-touch-targets]

## 9. Build and verify

- [x] 9.1 Run TypeScript build to verify no type errors [REQ: font-size-normalization]
- [x] 9.2 Visual spot-check: verify monospace renders correctly on main views [REQ: global-monospace-font]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN any page loads THEN all text renders in monospace font [REQ: global-monospace-font, scenario: font-applied-globally]
- [x] AC-2: WHEN inspecting any text element THEN font size is 12px, 14px, or 16px [REQ: font-size-normalization, scenario: no-arbitrary-font-sizes]
- [x] AC-3: WHEN searching components for font-mono THEN zero matches found (excluding battle/) [REQ: font-mono-class-removal, scenario: no-font-mono-in-components]
- [x] AC-4: WHEN viewing domain progress THEN it shows as block characters like ████████░░ 9/10 [REQ: block-character-progress-bars, scenario: domain-progress-display]
- [x] AC-5: WHEN viewing change status THEN Unicode char with color is used instead of dot div [REQ: unicode-status-indicators, scenario: change-status-display]
- [x] AC-6: WHEN viewing domain card sections THEN each is separated by ── HEADER ── style divider [REQ: section-divider-headers, scenario: domain-card-sections]
- [x] AC-7: WHEN viewing dashboard on mobile THEN all tabs have at least 44px touch target [REQ: mobile-touch-targets, scenario: mobile-tab-buttons]
