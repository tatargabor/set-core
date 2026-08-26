## Context

The fleet terminal already draws two kinds of link. A URL opens in a new tab
(`terminalLinkTarget`, `FleetTerminal.tsx`), and a path belonging to the agent's own project
opens in the in-app file view (`fileReference`, `fleetFiles.ts`). Everything else is plain
text, and `fileReference` says why in its own comment: an absolute path outside the project
root is refused because the framework may not read it.

That refusal is right about *reading* and wrong about *reaching*. Reported 2026-08-26 from a
live terminal: an agent printed two `/tmp/claude-chrome-screenshots-*/screenshot-*.jpg` paths
next to a URL, the URL was clickable and the screenshots were not, and getting to them meant
hand-selecting text out of a fixed grid across a horizontal scrollbar.

Constraints that shape the design and are not negotiable here:

- **The terminal's text is data.** It was written by whatever the agent ran. Nothing in it may
  cause anything to happen without a person's deliberate act, and nothing in it may cause a
  *program* to start even then.
- **`project-file-access` must stay what it is.** Its `_DENIED` comment states the rule this
  change must not undo: the API does not become a way to ask whether an arbitrary file exists
  on the machine, politely, one request at a time.
- **The framework persists nothing derived from a consumer's data** (`CLAUDE.md`). Handing a
  path to a desktop handler reads nothing and stores nothing, which is why this is a
  hand-over capability and not a viewer.

Measured on this machine, 2026-08-26, because the whole feature depends on it: the running
`set-web` user unit (`MainPID=1801429`) has `DISPLAY=:1`,
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`, `XDG_RUNTIME_DIR=/run/user/1000` and
`XAUTHORITY=/run/user/1000/gdm/Xauthority` in its environment. A desktop handler started from
the server therefore has a desktop to open on. This is a measurement of one deployment, not a
guarantee about every one — hence the "no handler available" refusal in the spec.

## Goals / Non-Goals

**Goals:**

- An absolute path outside the project, printed in a fleet terminal, is reachable in one
  deliberate act.
- The reader always learns the outcome — opened, or refused and why.
- The refusals are narrow, explicit, and fail toward *not starting a program*.

**Non-Goals:**

- Displaying the file in the dashboard. Out-of-project content is not read at all.
- A file browser, a picker, or any listing outside a registered project.
- Choosing which application opens what. The desktop's associations decide.
- Making the browser's machine and the framework's machine the same thing. When they differ,
  the file opens on the framework's desktop; the design accepts and names that rather than
  pretending to solve it.

## Decisions

### D1 — A separate endpoint and a separate module: `POST /api/desktop/open`

`lib/set_orch/api/desktop.py`, registered in `api/__init__.py` immediately after
`files_router`, i.e. before every `/api/{project}/...` family (finding CB-16: FastAPI resolves
in registration order and a project-shaped route would otherwise swallow it).

Not in `files.py`, and this is the load-bearing part: that module's contract is *confined to a
known project root*, stated in its docstring and enforced by `_confine`. An endpoint that
deliberately steps outside every root does not belong under a guard whose whole claim is that
nothing does. Two guards with opposite claims in one file is how one of them silently becomes
decorative.

*Alternative considered — `/api/fleet/open`.* Rejected: the capability is not about the fleet
screen. `desktop` names what it does, and the path is single-purpose, which makes a future
reader's question ("what can this reach?") answerable from the route name.

### D2 — The guard runs in a fixed order, and the executable rule applies to FILES only

```
absolute? → realpath (follow symlinks) → exists? → regular file or directory?
          → .desktop suffix? → executable bit (regular files only) → hand over
```

Two of these are the ones that would be got wrong:

- **`realpath` before judging.** A symlink is exactly how a harmless-looking path names an
  executable. The suffix and mode checks run on the resolved target, never on the request
  string — the same reasoning `_confine` already documents for containment.
- **The executable bit is checked on regular files only.** Every traversable directory has
  its execute bits set. A guard that applied the rule uniformly would refuse *every*
  directory while looking correct in review and passing any test written only against files.

`.desktop` is refused independently of its mode: a desktop entry is a launcher whether or not
anyone marked it executable.

*Alternative considered — an extension allowlist* (images, PDFs, text, …). Rejected: the user
chose "anything that exists, executables refused", and an allowlist fails in the direction
that trains people to stop using the feature — a refused `.parquet` teaches "this is broken",
while the danger it would avert is already covered by the mode and suffix rules.

### D3 — Hand over detached, and answer about the hand-over

`subprocess.Popen(["xdg-open", path], start_new_session=True)` with all three standard streams
at `DEVNULL`. The answer is `{"opened": true, "path": ...}` and it means *the desktop was
asked*, which is exactly what the spec allows it to claim.

*Alternative considered — `subprocess.run(..., timeout=n)` and report the exit code.*
Rejected twice over: some handlers do not return until their window closes, so a successful
open would time out and be reported as a failure — the fail direction that makes the message
worth ignoring — and `xdg-open`'s exit status is not a reliable statement about what the user
saw anyway.

`shutil.which("xdg-open")` missing is a refusal naming that, not an exception. On a machine
without a desktop this is the honest answer.

### D4 — The client decision lives in `fleetFiles.ts`, beside the one it complements

A new `desktopReference(token, root?)` returns the absolute path a token names, or `null`.
It shares `fileReference`'s punctuation stripping — the parentheses in
`(/tmp/…/screenshot-2.jpg)` are exactly the reported case — and adds:

- must start with a single `/`;
- must not contain `://` (a URL is the other link provider's business);
- a trailing `:<line>` is stripped, because a desktop handler takes no line number and
  `/tmp/run.log:42` should still open `/tmp/run.log`;
- when a project root is known and the path lies inside it, the answer is `null` — the
  in-project route wins, and precedence is decided in one place rather than by the order two
  link providers happen to be registered in.

Consequence, stated rather than discovered later: in a docked panel with no project context,
an in-project ABSOLUTE path is offered as an external one and opens through the desktop
instead of the file view. That is a degradation, not a defect — it reaches the file either
way — and it is the same "no project context, no project behaviour" rule the file link
already follows. A RELATIVE token in that state is left as text, because there is nothing to
resolve it against.

### D5 — Both outcomes are shown, on the terminal's existing status row

Success is reported too, briefly, and that is a deliberate departure from "silence means it
worked". The handler's window may open on another workspace, behind the browser, or on a
second monitor; an invisible success is then indistinguishable from a dead link, which is the
exact complaint this change answers. The message auto-clears; a refusal does not, because a
refusal is something the reader has to read.

The row is the one that already carries `stopError`, so no new surface is introduced.

### D6 — The terminal calls the endpoint itself

`FleetTerminal` already owns a `fetch` for `/stop`. The external open follows it rather than
being threaded through `Fleet.tsx` as another callback: the outcome has to be rendered *in
this terminal's* status row, and lifting it to the page would put a second copy of that state
somewhere that can disagree with the terminal it describes — the same argument the component
already makes for its header portal.

### D7 — A relative token is resolved against the project root, and the SHAPE is what filters it

Added after the second report the same day: an agent printed `openspec/changes/<name>/` — a
directory — and it was plain text. It always would have been. The file listing carries files,
so no directory is ever in the known set, and `fileReference`'s "must be in the known set"
rule is therefore not a bar a directory can clear. The same applies to a gitignored file and
to anything past the listing's 20 000-path cap.

So a relative token that `fileReference` refuses is resolved against the project root and
offered as a desktop reference. Two conditions, and the second is the load-bearing one:

- **a project root must be known.** Otherwise the token would be resolved against a working
  directory the reader cannot see, and would name a stranger's file of that name.
- **it must LOOK like a path.** The known set was doing double duty in `fileReference`: it
  decided the destination AND it kept prose out. This route has no set, so the shape is the
  only filter left, and a terminal is full of sentences. "Contains a slash" alone underlines
  `and/or`, `24/7`, `TCP/IP` and — in this repository's own terminals — `és/vagy`.

The test is: ASCII path characters only, at least one slash, and one of (a second slash, a
trailing slash, a dot-extension). Every one of those misses in the same direction — a real
path is left as text — because a missed link costs a right-click and a wrong one costs the
reader's trust in every underline on the screen.

*Alternative considered — resolve every relative token and let the endpoint refuse the
misses.* Rejected: it is the same trade as the absolute case on paper, but not in practice.
An absolute token is unambiguous; a relative one competes with prose, and the failure is not
one bad link but an underline under half the sentence.

*Alternative considered — ask the server which relative tokens exist.* That is the existence
probe D-nothing: the oracle this design refuses in the first place.

*Alternative considered — open a directory in the file view's tree instead.* Rejected for now:
the panel can show a tree, but the reader asking for a directory is usually asking for a file
manager, and one destination for "everything the file view cannot open" is one rule instead of
three. The endpoint already handles a directory, so this is a change of destination if it ever
turns out to be wanted, not a new mechanism.

## Risks / Trade-offs

- **An underlined token that opens nothing** → accepted, and answered by D5. No existence
  probe: the alternative is a filesystem oracle over the whole machine, which
  `project-file-access` exists to refuse.
- **A desktop handler is still a program, started from web input** → the refusals in D2 are
  the mitigation, and the direction is chosen: when in doubt, refuse. The activation is a
  person's, the path must exist, and anything the desktop would *run* is rejected before
  `xdg-open` is reached.
- **`xdg-open` on a text file may open an editor that then holds a lock or auto-saves** → out of scope for the framework: the desktop's associations are the user's own configuration,
  and the framework neither reads nor writes the file.
- **The browser is not always on the framework's machine** → the answer names the machine, and
  the risk is limited to surprise, not damage.
- **Linux only** → `xdg-open` is the Linux answer; on another platform the endpoint refuses
  with "no desktop handler available" rather than pretending. Adding `open`/`start` later is a
  one-line table, not a redesign.

## Migration Plan

Additive: a new endpoint and a new link kind. Nothing existing changes shape, so rollback is
reverting the commit — no state, no stored data, no config.

The dashboard is served from a build, so the web change requires `pnpm build` in `web/` and a
`set-web` restart for the running service to serve it.

## Open Questions

None. Both decisions that were genuinely open — how wide the openable set is, and whether to
probe for existence — were put to the user on 2026-08-26 and answered: anything that exists
with executables refused, and no probe.
