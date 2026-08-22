## Why

An agent names a file constantly — `src/lib/fleetTerminal.ts:214`, `openspec/bugs/README.md`
— and on the fleet screen those names are dead text. Reading one means leaving the screen
that has the context, finding the file by hand in an editor, and coming back; changing one
line means the same trip in reverse. The screen already shows what every agent is doing and
lets a person type at it; what it cannot do is show the thing being talked about.

Nothing here is a research question. The same problem was solved once already in a sibling
project, and this change adopts that shape rather than inventing a second one.

## What Changes

- **A file view panel on the fleet screen.** The project's file structure on the left, the
  opened file on the right with syntax highlighting, and a line the caller named scrolled to
  and marked. It is a panel like any other: dockable to an edge, resizable, sitting beside
  the agent that mentioned the file.
- **The file can be edited and saved.** Chosen by the user on 2026-08-22 over a read-only
  viewer, with the guard requirement stated below as the condition.
- **A file reference in terminal output becomes activatable.** Ctrl+click opens it in the
  panel, `path:line` landing on the line. External URLs already open in a new tab — that
  behaviour is untouched.
- **Two server endpoints** that set-core does not have today: list a project's files, and
  read or write one of them. Both scoped to a known project root.
- **A syntax highlighter enters `web/`.** There is none today: every code-shaped surface in
  the dashboard is a raw `<pre>`.

## Capabilities

### New Capabilities

- `project-file-access`: listing the files of a registered project and reading or writing one
  of them over HTTP — the guard that keeps every path inside a known project root, the size
  and binary limits, the conflict answer when the file changed underneath the caller, and the
  rule that the framework persists no byte of what it read.
- `fleet-file-view`: the panel itself — the structure on the left, the opened file on the
  right, jumping to and marking a line, the edited-but-unsaved state, and what the panel must
  say rather than swallow when a file cannot be shown or a save is refused.
- `terminal-file-links`: a file reference in an agent's terminal output is recognised and can
  be opened, including the route that still works when the agent's own program holds the
  mouse.

### Modified Capabilities

<!-- None. `fleet-dockable-views` already scopes panel typing and docking, and explicitly
     puts "what any particular view SHOWS" out of scope, so a new panel type needs no change
     to its requirements. -->

## Impact

- **New**: `lib/set_orch/api/files.py` (router), its registration in
  `lib/set_orch/api/__init__.py`, and `web/src/components/FleetFileView.tsx` plus its lib.
- **Changed**: `web/src/components/FleetTerminal.tsx` (a link provider for file references),
  `web/src/pages/Fleet.tsx` (the panel and where it opens).
- **Dependency**: `@monaco-editor/react` enters `web/package.json` — the first code-rendering
  dependency in this repo. Loaded lazily, like xterm, so a reader who never opens a file
  never downloads it.
- **A new write path into a project tree.** The repository's whole 2026-07-19 safety track
  exists because write paths into consumer trees were unguarded, and this change adds one
  deliberately. It is therefore guarded at the endpoint — known root, realpath-resolved,
  symlink out refused, size and type limited, and a changed file refused rather than
  overwritten — and that guard is a requirement, not an implementation note.
- **Confidentiality.** A consumer's source is full of domain. set-core may display it and
  persists none of it: no cache, no log line carrying content, no browser storage. Diagnostics
  log the shape of a path, never the file.
