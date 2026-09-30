## Context

`lib/set_orch/api/desktop.py` is one of three path guards in `api/`, and the only one that
confines nothing by location: it steps outside every project root on purpose and guards the
**act** instead — a path may be OPENED, never RUN. Its refusal list was measured on a Linux
desktop in August (`B-89`, the `.jar` case), and the opener is the module-level constant
`xdg-open`.

The framework now also runs on macOS, where that constant does not exist. Measured 2026-09-25
from a fleet terminal on the Mac mini: activating `~/Downloads/<name>.pdf` answered
`501 no desktop handler available (xdg-open not found)`.

The endpoint's callers are fleet terminals, where every character of a path was written by
whatever an agent ran. A person's activation starts the request, but the text is data, not an
instruction — which is why the guard exists at all and why widening the platform without
widening the guard would be the wrong half of the job.

## Goals / Non-Goals

**Goals**
- The endpoint works on macOS with the same contract it has on Linux.
- The refusal list is complete for *both* platforms, each entry resting on a measurement.
- The tests hold on both platforms, on either machine.

**Non-Goals**
- Windows (`start`). Nothing runs the framework there; adding an untested third branch would
  be a claim nobody has measured.
- Probing the local desktop for what it would do with a suffix. The guard answers from the
  path alone, deliberately: a guard that asked the machine would answer differently on every
  machine and could not be tested at all.
- Any change to the route, the request body, or the answer keys.

## Decisions

**1. Resolve the opener from `sys.platform`, in a function, not at import.**
A module-level constant computed at import is invisible to a test that wants the other
platform's branch — and this module has exactly two branches worth testing. A small
`_opener_name()` returning `open` on `darwin` and `xdg-open` otherwise is monkeypatchable, so
both branches are covered on whichever machine runs the suite. *Alternative rejected:* keeping
`_OPENER` and swapping it at import time — one machine would then only ever test its own half,
which is the "two agents generalise from the runtime each can see" failure this repo has paid
for before.

**2. No fallback between openers.** If the platform's opener is missing, refuse — exactly as
today. *Alternative rejected:* try `open`, then `xdg-open`. On a Linux box with a stray
`open(1)` (the util-linux `openvt`-adjacent name, or any user script called `open`) that would
hand an agent-written path to an unknown program. The contract is that every outcome is
reported; a fallback trades a reported refusal for an unreported guess.

**3. `.app` goes in `_LAUNCHER_SUFFIXES`, not in the executable-bit path.** A bundle is a
*directory*. The bit check is `if not is_dir and os.access(...)`, and that exemption is
correct and deliberate — every traversable directory has the bit, so a uniform check would
refuse every folder while passing any suite written only against files. So `.app` must be
caught by name, in the class that already exists for "this is a launcher whatever its
permission bits say". This is the one macOS class a correct Linux-shaped guard waves through,
which is why it gets its own requirement rather than a list entry.

**4. `.command`, `.terminal`, `.dmg` go in `_ASSOCIATION_RUNS`.** Measured on this machine with
`mdls -name kMDItemContentType`: `com.apple.terminal.shell-script`,
`com.apple.terminal.settings`, `com.apple.disk-image-udif`. The first two are executed by
Terminal; the third mounts, which is the act `.pkg`/`.deb`/`.snap` are already refused for.

**5. `.workflow` is left out.** The same probe returned a dynamic UTI
(`dyn.ah62d4rv4ge81s55wrrxg2551`) — nothing is registered for it here. The module's rule is
that the list is a floor widened by measurement; adding a suffix because its name sounds
executable is how a list stops meaning anything.

## Risks / Trade-offs

- **A macOS-only test passes as a skip on Linux, and a green suite then says nothing.** →
  Patch `_opener_name()` rather than gating on `sys.platform`; assert the argv the endpoint
  would spawn. No test in this change may be conditional on the host platform.
- **`.dmg` refusal is a small usability loss** (a person might legitimately want to mount one
  from a terminal path). → Accepted, and it is the direction the module already chose for
  `.pkg`: refusing an ordinary file is an inconvenience, letting an installer through is a hole.
- **The list is still a floor, on both platforms.** → Stated in the spec rather than implied,
  so the next reader widens it by measuring rather than assuming it is complete.

## Migration Plan

None. No stored state, no API shape change; a Linux caller's behaviour is byte-identical. The
change is live as soon as the server process restarts — and a shipped commit is not a running
system, so the macOS verification is done against a restarted `set-web`.

## Open Questions

- Windows is unaddressed by choice; if the framework is ever run there, `start` needs its own
  measured launcher classes (`.lnk`, `.scf`, `.url`), not an extrapolation from this change.
