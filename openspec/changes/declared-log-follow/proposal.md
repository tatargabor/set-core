## Why

A project's status answer can already say *what is running*. It cannot say *what it is doing right
now* — that lives in a file the project writes while it works, and the surface has no way to reach
it. Measured 2026-08-02 against a live producer: such an answer already carries a relative path to
such a file, the file is alive and growing while being watched, and it is line-oriented JSON — one
event per line. The framework runs on the same machine and can read it directly.

The value is the gap between two screens: one that says "a section has been running for 40 seconds"
and one that shows what it just did. The first is a status; the second is the reason anyone keeps
the tab open.

## What Changes

- **A project may declare that one of its fields carries a followable file path.** The declaration
  is an envelope key, keyed by bare field name — the same vocabulary as `caveats`, `deprecated` and
  `_emphasis`. The framework never recognises a field *called* `log`; that would be domain inside
  the framework, and the next project will call it something else.
- **A streaming read endpoint** that follows such a file and emits its new lines as server-sent
  events. Not MCP: an MCP call is request/response, and every chunk would travel through a model's
  context for no reason when the browser and the server are on the same machine.
- **A gate at the effect, not near the alarming word.** The endpoint follows a path only if that
  exact path is currently the value of a follow-declared field in the project's own answer, and only
  if it stays inside the project tree after symlink resolution. Reading only; nothing is ever
  written.
- **A follow control on the surface**, offered beside the value of a declared field and nowhere
  else, and a panel that renders lines as they arrive without recognising any field name inside them.
- **Nothing is persisted.** The stream is read, shown and dropped — not into a cache, not into a
  log, not into this repository. An agent log is the densest domain source there is.

## Capabilities

### New Capabilities
- `project-status-follow`: a project declares which of its fields carry a followable path; set-core
  streams that file's new lines to the surface, gated on the live answer and on the project tree,
  and persists none of it.

### Modified Capabilities

<!-- None. Every existing requirement in project-status-contract, project-status-api and
     project-status-surface stays as written; this capability is built to obey them, in
     particular "The renderer recognises no domain field name" and "set-core reads a project's
     data and persists nothing derived from it". -->

## Impact

- `lib/set_orch/project_status.py` — the envelope grows one optional key; absent means no
  followable field, which is the behaviour every project has today.
- `lib/set_orch/api/project_status.py` — one new streaming route plus its gate.
- `web/src/components/statusShape.tsx`, `StatusValue.tsx` — the control and the panel.
- No change to any existing route, command, or declaration. A project that declares nothing sees
  no difference.
