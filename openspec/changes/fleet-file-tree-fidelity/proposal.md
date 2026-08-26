## Why

Five defects were reported against the fleet file view on 2026-08-26, four by the reader
looking at the screen and a fifth found while measuring the second. Four of the five share
one shape — **the panel shows less than the tree holds, and says nothing about the
difference** — which is the false-absence class this repository already pays for elsewhere:
a reader concludes a file is not there when the listing simply never offered it.

Measured on a live consumer checkout:

| # | reported | measured |
|---|---|---|
| 1 | a long line runs off the editor, with no way to wrap it | `FleetFileView.tsx` passes no `wordWrap`; Monaco's default is `off` |
| 2 | `.set/` and other directories "simply are not visible" | `git check-ignore -v .set` → ignored; `git ls-files --cached --others --exclude-standard \| grep -c '^\.set/'` → **0**, against **156** files actually there |
| 3 | opening a file does not move the list to it | `Node` marks the active row but nothing expands its ancestors or scrolls to it; opening from a terminal link leaves the tree wherever it was |
| 4 | uncommitted / unstaged files are not marked | the listing carries paths only — no status is fetched, sent, or rendered |
| 5 | *(found while measuring #2)* a bogus `"docs` node, and 11 files that cannot be opened | `git ls-files … \| grep -c '^"'` → **11**; git quotes non-ASCII names, so the path the tree builds and sends back is `"docs/converted/…\303\263….md"`, which no file has |

#5 is the worst of the five and was not reported as a bug at all: the reader saw a `"docs`
folder in the screenshot and read it as clutter. It is really eleven files present in the
tree, listed under a directory that does not exist, and refused on click.

## What Changes

- **The listing answers with fidelity, not with a shell's rendering of it.** `git ls-files`
  and `git status` are read with `-z`, so a path is the bytes git holds and never a quoted
  C-string. No caller has to un-quote anything, and there is nothing to get wrong twice.
- **Ignored files can be asked for.** The listing takes an `ignored` flag. Default OFF —
  the project's own ignore rules stay the default answer. ON adds what those rules exclude,
  minus the heavy build directories the walk fallback already skips, so the answer stays
  inside the cap: measured on a live consumer tree, **1794 → 2005** files with the flag on,
  against **36 149** for a naive "drop `--exclude-standard`".
- **The listing carries each path's git status.** A `status` map from path to git's own
  two-character code, plus `!!` for entries present only because `ignored` was asked for.
  Absent status is "clean", and a project with no repository carries no map at all — a
  MISSING map and an empty one are different facts.
- **The panel marks what is not committed**, on the file row and on every ancestor folder,
  so a modification inside a collapsed directory is visible where the reader is standing.
  This is the [ui-quality](../../../.claude/rules/ui-quality.md) rule about compacting
  never hiding a failure, applied to the tree.
- **The panel follows the open file.** Opening one — from the tree, from a terminal link,
  or from the remembered file on re-open — expands its ancestors and scrolls the row into
  view.
- **Word wrap is a control in the header**, off by default, remembered across the panel's
  many teardowns (docking, enlarging, closing) as a preference and not as project data.
- **An ignored-files control sits beside it**, so the answer to "where is `.set`" is a
  toggle rather than a question.

No breaking change: every new field is additive, and `ignored` defaults to today's answer.

## Capabilities

### New Capabilities

*(none — both surfaces already have a spec)*

### Modified Capabilities

- `project-file-access`: the listing gains path fidelity (`-z`), an opt-in `ignored` flag
  with a stated bound, and a per-path git `status` map whose absence is meaningful.
- `fleet-file-view`: the panel gains a word-wrap control, an ignored-files control, git
  status marks on rows and their ancestors, and the rule that the structure follows the
  opened file.

## Impact

- `lib/set_orch/api/files.py` — `_git_files`, new `_git_status`, `list_files` signature.
- `web/src/lib/fleetFiles.ts` — the tree carries status; ancestor paths; status roll-up.
- `web/src/components/FleetFileView.tsx` — two header controls, the reveal effect, the
  marks on `Node`.
- `tests/unit/test_files_api.py`, `web/tests/unit/fleetFiles.test.ts`, and the file-view
  component tests.
- Contract: `/api/fleet/files` gains a query parameter and two response fields. Additive.
