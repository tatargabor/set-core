# Design — fleet file tree fidelity

## Context

The file view is one panel with two halves and two owners: `lib/set_orch/api/files.py`
answers what the tree holds, `web/src/components/FleetFileView.tsx` decides what a reader
sees of it. Four of the five reported defects sit on the seam — the endpoint knows something
the panel never receives, or the panel receives something it cannot render honestly — so the
change touches both sides and the tests on both sides.

Everything below was measured on a live consumer checkout on 2026-08-26. The numbers are
part of the decisions, not decoration: three of the four choices here would have gone the
other way without them.

## Goals / Non-Goals

**Goals**

- The listing's paths are the tree's paths, byte for byte.
- What the ignore rules hide is reachable, on request, and marked as such.
- Uncommitted work is visible in the structure, including through a collapsed directory.
- The structure follows the open file.
- Long lines can be wrapped.

**Non-Goals**

- Diff, blame, staging, committing, or any other git *action*. `project-file-access` puts
  those out of scope and this change does not move that line: the status is READ and shown.
- A file watcher or a polling listing. The refresh control stays the way the tree is
  re-read — the endpoint runs `git ls-files` and `git status` on a real tree, and a panel
  that did that every few seconds would spend it on a reader looking at one file.
- Creating, renaming or deleting anything. Still no file manager.
- Persisting a project's paths or content in the browser. A wrap flag is a preference; a
  path is a consumer's domain.

## Decisions

### D1 — `-z` on both git reads, rather than un-quoting in Python

`git ls-files` and `git status --porcelain` render a path containing a byte outside the
portable set as a **quoted C-string** (`"docs/…\303\263….md"`), controlled by `core.quotePath`,
which is on by default. Measured: **11 of 1794** paths in the consumer checkout, all of them
under one directory, and the damage was compound — a phantom `"docs` node in the tree, eleven
real files unreachable beneath it, and a refusal on click for a file plainly on disk.

Three ways to fix it:

| option | why not |
|---|---|
| un-quote the C-string in Python | a second implementation of git's own escaping, wrong the first time a `\t` or an embedded quote appears, and it has to be written twice (files and status) |
| `-c core.quotePath=false` | correct, but it is a per-invocation override of a config the user may have set deliberately, and it still leaves newline-in-filename ambiguity in a `\n`-split output |
| **`-z`** ✅ | git emits the raw bytes with a NUL terminator: no quoting, no escaping, and no ambiguity for a name containing a newline. Split on `\0`, drop the trailing empty. |

`-z` is chosen. It also removes the `\n`-split hazard that was always latent and never hit.

**Consequence for `git status -z`:** the porcelain-v1 format under `-z` is
`XY<space><path>\0`, and a rename/copy is `XY<space><to>\0<from>\0` — the second NUL-field is
NOT a new entry. The parser must consume it, or the origin path becomes a phantom status
entry carrying a code git never emitted.

**And that phantom is intermittent, which is what makes it worth a test.** The
malformed-record guard (`field[2] != " "`) drops the origin field whenever the origin's third
character is not a space — true of `src/app.ts`, false of `my file.ts`. Measured while
mutation-testing this parser: the first test written for it renamed `src/app.ts` and passed
with the consume removed. A test that passes against the mutation proves nothing and looks
like proof forever, so the fixture names the case the guard cannot save.

### D2 — `ignored` widens the listing by lifting the ignore rules, then re-applying the walk's skip list

The naive fix is dropping `--exclude-standard`. Measured, that is **36 149** paths against a
cap of 20 000 — the answer would come back truncated, i.e. one silent absence traded for
another, plus a listing dominated by `node_modules` and `.next`.

So the widened listing reuses `_SKIP_DIRS`, the list the non-repository walk already refuses
to enter, applied to any component of the path. Measured result: **2005** paths, against 1794
with the flag off. The 211 difference is `.set/` (156), `.set-designer/` (25), `.claude/`
extras, `.env.local`, `.test-content/` — which is exactly the set the reader was asking for.

Reusing `_SKIP_DIRS` rather than writing a second list is deliberate: two lists that are
meant to agree drift, and this repository has already paid for that in
`files.py:_known_root`, where a guard and its docstring claimed agreement they did not have.

**The bound is honest about itself.** A file inside `node_modules` is still not listable, with
the flag on or off. That is a stated limit of the control, not a claim that nothing is there —
and it is why the ignored entries are *marked* rather than merged: the flag's answer is "these
are the ignored files this view is willing to carry", never "these are all of them".

### D3 — status is a map keyed by path, and its ABSENCE is a value

`{"src/a.ts": " M", "src/b.ts": "??"}`. A path missing from the map is clean.

The whole map is **absent** (`null`, not `{}`) when there is no repository, or when the status
read failed. This is the "a gap is not a zero" rule at the wire level: `{}` says *I asked and
everything is clean*, `null` says *there was nothing to ask*. A panel that receives `{}` from a
non-repository directory would render a tree of unmarked rows and imply cleanliness it never
measured — the same defect class as a screen that reports calm it has not verified.

`-uall` is passed to `git status`, because the default collapses an untracked directory to a
single `dir/` entry while the listing carries its files individually; without it every file in
a new directory would come back unmarked, which is the reassuring direction.

A status read that fails **does not fail the listing**. Files with no marks are useful; an
error instead of the files is not.

### D4 — status roll-up onto ancestors happens in the tree builder, not in `Node`

`buildTree` already owns "what a flat list of paths becomes on screen", and it is the only
place that sees a directory and its whole subtree at once. Rolling up there is one pass over
the tree; rolling up in `Node` would be a walk per directory per render.

The roll-up is a *summary*, not a code: a directory carries "something under here is
untracked" and/or "something under here is changed", never a two-letter git code, because a
directory does not have one and inventing one would be a false value sitting next to a real
one.

### D5 — wrap defaults to OFF, and persists in `localStorage`

Off, because wrapping breaks the correspondence between a screen row and a line number, and
this panel's other feature is *open at line N and mark it* — the terminal links depend on it.
Somebody who asked to go to a line did not ask for the ruler to stop matching.

Persisted, because the panel is torn down for reasons that have nothing to do with the
reader: docking to an edge, enlarging, closing. This is the same complaint already fixed for
"which file was I reading" (`initial`/`onOpened`), arriving for a second piece of panel state.
`localStorage` is allowed here and forbidden for paths and content: the rule that forbids the
latter is about a *consumer's domain leaving the framework's memory*, and a boolean about a
panel is not that. Same for the `ignored` toggle.

`treeWidth` is deliberately NOT changed to match — its own comment states why it is
per-mount (a sensible width differs in the grid and on each of four edges), and that reason
does not apply to a boolean.

### D6 — following the open file expands, never collapses

`expanded` is a `Set<string>`. Revealing adds every ancestor path of the opened file to it.
It never removes one, so a reader's own expansions survive — a "reveal" that tidied the tree
would be the panel overriding a choice somebody made on purpose.

The scroll is `scrollIntoView({ block: 'nearest' })` on the active row, which is a no-op when
the row is already visible: revealing a file the reader just clicked in the tree must not
yank the list.

## Risks / Trade-offs

- **`git status` cost on a large tree** → it runs only on a listing request, which is
  already `git ls-files` on the same tree, and only there. Same 30 s timeout, and a failure
  degrades to "no map" rather than to an error (D3).
- **The `-z` rename parse is easy to get subtly wrong** (D1) → a unit test with a staged
  rename whose ORIGIN path has a space at index 2, asserting no phantom entry appears and
  the record after the rename keeps its own code. A rename of an ordinary path passes on the
  broken parser — measured, not assumed.
- **`ignored=1` still hides `node_modules`** → stated in the spec as a bound of the control,
  and the ignored entries are marked so the reader can see the flag is doing something.
- **`localStorage` for two flags** → both are booleans about a panel, neither derives from a
  project. Read defensively (a throwing accessor in a locked-down browser must not take the
  panel with it).
- **A status map on a 20 000-file listing** → the map carries only non-clean paths, which in
  every measured case is a small fraction. The cap already bounds the worst case.

## Migration Plan

Additive on both sides, so no migration:

- `GET /api/fleet/files` gains `?ignored=0|1` (default `0`) and two response fields:
  `status` (object or `null`) and, per ignored entry, membership in an `ignored` set.
- A dashboard build older than the API sees fields it ignores; an API older than the
  dashboard answers no `status`, which the panel already has to handle as "no claim" (D3).

Rollback is reverting the commit; nothing is written to disk or to a schema.

## Open Questions

None blocking. One deliberately deferred: whether the ignored-files control should be
per-project rather than global. Global for now — one reader, one preference, and a
per-project store is a decision with a place to put it if the global one turns out wrong.
