## Why

A reader looking at an agent's terminal on the fleet screen cannot hand it a picture.
Measured 2026-08-22 (B-62): the one paste key that works, `Ctrl+Shift+V`, delivers a
`ClipboardEvent` whose `types` are `["text/plain"]` only, and xterm's paste handler reads
`getData("text/plain")` and nothing else. So no key in this panel can carry an image, and
none ever could.

This is not the same defect as the missing `Ctrl+V` path, which is fixed (`b4d7aa87`). It
is an absence with a cause: the agent runs behind a pty **on the server**, and the image
lives in the **reader's browser**. Nothing in between carries bytes. A screenshot of a
broken screen is the single most useful thing a person can give a coding agent, and today
the only way to do it is to leave the fleet screen entirely, save the file by hand
somewhere the agent can reach, and type the path.

## What Changes

- A pasted **image** in an agent terminal is uploaded from the browser to the framework and
  written to a **shared scratch root outside every project tree** —
  `~/.local/share/set-core/paste/`. The reader's decision, 2026-08-22: not into the
  consumer's working tree, because writing into a consumer tree is the operation class the
  2026-07-19 safety track closed, and this feature has no reason to reopen it.
- The terminal then **types the absolute path followed by a space** into the pty, with **no
  Enter**. The reader keeps control of what is sent and when.
- **The success path stays quiet** (the reader's choice) — the typed path is itself the
  receipt. **A failure never stays quiet**: a refused, oversized, unsupported or
  interrupted paste says so where the reader is standing. A save that silently does nothing
  is the false-absence shape this repository has already paid for more than once.
- **A pasted image is not a file the framework keeps.** Entries expire and are removed on a
  bound, and the store has a size ceiling; neither the bytes nor the file name are logged.
- Text paste is untouched. `Ctrl+V` and `Ctrl+Shift+V` keep delivering text exactly as they
  do now, and a paste carrying **both** text and an image is treated as text.

## Capabilities

### New Capabilities
- `terminal-image-paste`: what happens in the panel when a clipboard image is pasted into an
  agent terminal — what is accepted, what is typed into the pty, what is said when it fails,
  and what is never kept.
- `paste-store`: the framework-side store for pasted binary content — where it lives, what it
  accepts, what bounds it enforces, when an entry disappears, and what it must never persist
  or log.

### Modified Capabilities
<!-- none: the text paste behaviour specified elsewhere is unchanged by this change -->

## Impact

- **Web** — `web/src/components/FleetTerminal.tsx` (the paste listener and the pty write),
  `web/src/lib/fleetTerminal.ts` (the decision functions), and their unit tests.
- **API** — a new upload route beside `lib/set_orch/api/files.py`. It does **not** belong in
  that module: `files.py` owns one project file, read or written in place, and its own header
  forbids it becoming a store. This writes framework-owned scratch, which is a different
  guard and a different lifetime.
- **Confidentiality** — a pasted image is a consumer's content. It must not reach a repo, a
  log, a diagnostic dump, or anything that can leave the machine. Only the SHAPE of the
  operation is logged (mime type, byte count, outcome), never a name or the bytes.
- **NOT touched** — no project tree is written, no deployment path, no orchestration state.
