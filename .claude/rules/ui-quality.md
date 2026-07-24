# UI Quality — the dashboard is a product, not a debug view

Stated by the user on 2026-07-24: the web UI must meet **modern standards — legible,
compact, easy to navigate**. This is a standing bar, not a request about one screen.

It is worth writing down because the default failure here is not ugliness. It is a page
that renders everything it has, in the order it arrived, and calls that "showing the
data". That page is honest and unusable, and unusable means unread.

## What the bar actually means

- **Compact before complete.** A screen that shows twenty facts shows none of them. Group,
  tab, or collapse until the first screenful answers the question the page exists to
  answer, and everything else is one click away.
- **Navigable means locatable.** Someone arriving cold should be able to find a thing
  without scrolling to look for it. Tabs, a sticky header, a visible current position.
- **Density is a decision, not an accident.** Prefer a table to a list of cards when the
  rows are comparable; prefer a card when they are not.
- **One visual weight per meaning.** If red means "broken", nothing decorative is red.

## The rule that outranks the rest

**Compacting must never hide a failure.** Every layout that hides something — a tab, an
accordion, a "show more" — creates a place a broken thing can sit while the page looks
fine. So anything hidden that is *wrong* must be marked where the reader is standing, not
only where it lives: a failure count next to the tab strip, a marker on the tab itself.

This is the same rule as "a gap is not a zero", applied to layout instead of to values. A
tidy screen that reports calm it has not verified is worse than a cluttered one that does
not, because it is more convincing.

## Before calling a screen done

Look at it. Structural counts — sections, rows, zero JS errors — prove it *renders*; they
say nothing about whether it is readable or whether two fields contradict each other. That
exact gap has already cost a round here: a screen measured as fine had a deprecated value
sitting next to its replacement, and only a human looking at it caught that.
