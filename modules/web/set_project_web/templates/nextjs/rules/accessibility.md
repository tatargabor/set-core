---
paths:
  - "src/components/**"
  - "src/app/**/*.tsx"
---
# Accessibility Conventions

## Standard
- Target WCAG 2.1 Level AA compliance
- Test with keyboard navigation and screen reader (axe-core in Playwright)

## Semantic HTML
- Use correct heading hierarchy (`h1` → `h2` → `h3`) — never skip levels
- Use `<nav>`, `<main>`, `<aside>`, `<footer>`, `<section>`, `<article>` landmarks
- Use `<button>` for actions, `<a>` for navigation — never the reverse
- Lists of items: use `<ul>`/`<ol>` — not `<div>` sequences

## Images & Media
- Every `<img>` and `<Image>` MUST have `alt` text (empty `alt=""` for decorative only)
- Icons used as actions need `aria-label` on the parent button
- Video/audio: provide captions or transcripts when applicable

## Interactive Elements
- All interactive elements must be keyboard accessible (Tab, Enter, Escape)
- Minimum touch target: 44×44px (WCAG 2.5.5)
- Focus must be visible — never remove outline without replacement (`focus-visible`)
- Trap focus inside modals/dialogs — shadcn Dialog handles this automatically
- Skip-to-content link as first focusable element in layout

## Forms
- Every input needs an associated `<label>` (or `aria-label` for icon inputs)
- Error messages linked via `aria-describedby`
- Required fields marked with `aria-required="true"`
- Form validation errors announced to screen readers (`aria-live="polite"`)

## Color & Motion
- Color contrast ratio: minimum 4.5:1 for normal text, 3:1 for large text
- Never convey information by color alone — use icons/text as well
- Respect `prefers-reduced-motion` — disable animations when set
- Respect `prefers-color-scheme` if dark mode is supported

## Dynamic Content
- Use `aria-live="polite"` for toast notifications and status updates
- Loading states: use `aria-busy="true"` on the container
- Expandable sections: use `aria-expanded` on the trigger
