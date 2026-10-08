## Context

A live session (2026-10-03, B-156) measured a `file:` URI printed by an agent producing no
link at all, and — in the same running system — Ctrl+click producing zero activation while
the agent's TUI held mouse tracking. The endpoint half was proven healthy in the same
session: the identical page opened through the file view's desktop button, and the browser's
history carries the visit. So both defects sit in the browser: the recogniser, and the
gesture.

## Goals / Non-Goals

- **Goal:** the URI spelling reaches the same pipes as the bare path; the documented gesture
  (Ctrl+click) activates a confirmed reference in both mouse-tracking states.
- **Non-Goal:** no change to `desktop-open`'s refusal classes, request fields or endpoint;
  no change to http(s) URL handling; no new modifier vocabulary.

## Decisions

- **Translate the spelling, do not special-case the destination.** `fileUriPath` maps a
  `file:` URI to its pathname (host empty or `localhost` only, absolute, decodable) and the
  result flows through the SAME candidate pipeline as any printed path. Why: the URI names a
  file on this machine, and the guards that rule on the path (`desktop.py`'s refusal list,
  the file endpoints' confinement) are exactly the guards that rule on the bare form — a
  second route would be a second opinion about what may open. Another host is refused because
  it names a file on a machine this framework does not hold.
- **The terminal steals Ctrl+click on a confirmed reference, in the capture phase.** Why not
  defer to xterm per tracking state: the TUI's mode flips between attaches (measured in both
  states twenty minutes apart), xterm's own activation is gated on its internal hover state,
  and with tracking on xterm never activates at all. One policy in both states — the reader
  holding CTRL means the link, not the application, which is real-terminal convention and
  this screen's own documented gesture. Without the modifier, without a hit, or on another
  button the handler returns untouched, so the program keeps its mouse and selection keeps
  Shift. The cell arithmetic (`referenceAtColumn`) lives in the lib, where it is measurable
  without a browser.
- **A 600 ms same-target debounce is the double-fire guard.** With tracking off, xterm's own
  path would also have acted; the steal runs first in the capture phase and stops the event,
  but the debounce removes the residual case instead of reasoning about listener order.

## Risks

- A wrapped token (a URL longer than the terminal's width) is still offered per visual row —
  the recogniser sees a partial token and offers what that partial names. Pre-existing for
  every long path, not introduced here; the destination in the worst case is a reported
  "no such file", never a wrong file that opens silently (the listing proof and the
  re-fetch guard rule).
