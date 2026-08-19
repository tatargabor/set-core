---
paths:
  - "src/components/**"
  - "src/app/**/*.tsx"
  - "src/app/**/*.css"
  - "src/styles/**"
---
# Motion Conventions

## Default position
- Motion is coded and deterministic — never generated video
- No animation dependency by default; the platform covers the common cases
- The un-animated page is the baseline, motion is the enhancement on top of it

## Scroll-linked animation
- Bind animation progress to scroll with CSS `animation-timeline`, not a scroll listener — it runs on the compositor
- Page-long progress: `animation-timeline: scroll(root block)` — always name `root` explicitly, bare `scroll()` means `nearest` and latches onto the closest scroll container
- Per-element reveal on entry: `animation-timeline: view()` with `animation-range`
- `animation-duration` is ignored on a scroll timeline; `animation-timing-function` is not — use `linear` unless easing across scroll distance is intended
- Always set the `both` fill mode, or the element snaps back outside its range
- Named timelines need `scroll-timeline` on the scroller plus `timeline-scope` when the animated element is not its descendant

## Progressive enhancement (mandatory)
- Wrap scroll animation in `@supports (animation-timeline: scroll(root))` **and** `@media (prefers-reduced-motion: no-preference)`
- Phrase it so the static page is the default — never `opacity: 0` waiting to be revealed
- The design-fidelity gate screenshots with `prefers-reduced-motion: reduce` injected: an element revealed only by scrolling is captured blank and fails the diff
- The DOM must be complete and readable with CSS animation disabled — this is the SEO and screen-reader baseline

## Animatable properties
- Animate only `transform`, `translate`, `scale`, `rotate`, `opacity`, `filter`, `clip-path`
- Never animate on scroll: `width`, `height`, `top`, `left`, `margin`, `padding`, `background-position`
- Progress bars use `scaleX` with `transform-origin: left` — not `width`

## Mobile
- `100svh` for sticky or pinned sections — `dvh` re-resolves as the mobile toolbar collapses and rescales the timeline mid-scroll
- Clamp computed scroll progress to `[0, 1]` — iOS rubber-band overscroll goes out of range at both ends
- No `transform`, `filter`, `perspective`, `backdrop-filter`, `will-change` or `contain: paint` on ancestors of `sticky`/`fixed` elements — each becomes the containing block and unpins the descendant
- Never `-webkit-overflow-scrolling: touch` — no effect since iOS 13, breaks `position: fixed`
- Scope `overscroll-behavior` to real containers, never `body` — on `body` it kills pull-to-refresh
- Pinned scrub sections and parallax are desktop-only at best

## Never take the scroll away
- No scroll-jacking, no hidden or restyled-away scrollbar, no per-section `history.pushState`, no intercepting the iOS edge-swipe-back
- Keyboard scrolling (Space, PageDown, Home, End, arrows) must keep working

## JS fallback, when needed
- One `{ passive: true }` listener feeding a single `requestAnimationFrame`
- All reads before all writes — interleaving them thrashes layout every frame
- Re-measure document height with a `ResizeObserver` on `documentElement`; never cache it at load
- Listen on `resize` too — the mobile toolbar changes viewport height

## Specifying motion
- State duration, easing and the reduced-motion fallback inline, next to the thing they animate
- The design-fidelity gate freezes animation sequence, duration and easing as contract — an unspecified value becomes an accidental one

## When a library is justified
- Coordinated multi-scene timelines, or pin plus snap beyond `position: sticky`
- Otherwise the cost is 30–46 kB gzipped against roughly forty lines of local code
