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

## A UI change is not done until somebody LOOKED at it — stated by the user, 2026-08-20

**Every change that touches the UI carries a visual check, in the browser, as a
task.** Not optional, not "if the extension happens to be connected". Use Claude
in Chrome against the running dashboard, open the screen the change touched, and
look. In planning it is worth naming; **at implementation it is required.**

The user asked for this after a screenshot of a shipped, fully-green change, and
the screenshot is the argument: the whole right-hand side of the fleet screen was
**empty black** while its own header said `3 agent` and `2 as tabs — click one to
switch`, and the docked panel beside it held a terminal squeezed to a horizontal
scrollbar. 655 web tests and 104 Python tests were passing. Two mutation rounds,
18 mutants, all caught. None of it was wrong — and none of it could see this,
because every one of those checks asks *did the mechanism run*, and the defect
was in the *result*.

**What this rule is NOT.** It is not "add a screenshot test". A stored screenshot
compares a render against an earlier render, which is the same class of check one
layer up — it would have gone green on an empty panel that was already empty. The
requirement is a **person or an agent actually looking at the screen and saying
what they see.**

**And when the browser cannot be reached, the task stays OPEN.** Do not mark it
done, do not substitute a structural count for it, and do not let a green suite
imply it. Say so in the task, in the commit, and to the user — an unverifiable
screen is a known unknown, and the whole point of this rule is that it is the one
gap a passing test run cannot cover.

## Before calling a screen done

Look at it. Structural counts — sections, rows, zero JS errors — prove it *renders*; they
say nothing about whether it is readable or whether two fields contradict each other. That
exact gap has already cost a round here: a screen measured as fine had a deprecated value
sitting next to its replacement, and only a human looking at it caught that.
