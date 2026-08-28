## Context

This change deletes things. That sounds like it needs no design — and it is exactly why it
does: the risk here is not that the deletion fails, it is that it takes something with it.

Twelve tracked files match `git ls-files | grep -i figma`. They fall into three groups that
look identical from a filename and are not:

| group | files | what it actually is |
|---|---|---|
| dead | `openspec/specs/figma-source-dispatch/spec.md`, `scripts/fetch-figma-design.py`, `tests/fixtures/figma-raw/TEST/sources/*.tsx` (4) | published or shipped, zero implementation, zero references |
| history | 6 files under `openspec/changes/archive/2026-03-15-*` | the record of **why** the Figma MCP path was rejected |
| live | `docs/images/auto/figma/{product-detail,storefront}-design.png` | build input for the presentation, referenced from `scripts/build-presentation.py:298` |

The report that started this came from outside the repo — a peer session in another project
reading `openspec/specs/` to decide its own design pipeline. That is the audience a published
spec has, and it is the reason the dead group is not merely untidy.

Constraint that shapes every decision below: **the framework catches up to mechanisms proven
elsewhere rather than reviving its own abandoned ones.** If Figma-sourced design input is
wanted again, it comes from a project running a working local `.fig` decode path — not from
this spec, which describes a function that was measured unreliable before it was deleted.

## Goals / Non-Goals

**Goals:**

- `openspec/specs/` stops publishing a capability the repository does not implement.
- The two dead carriers (fetch script, test fixture) leave the tree with their absence proven,
  not assumed.
- The presentation stops asserting a mechanism the roadmap records as dropped.
- Deleting is **provably** safe: every removal names the grep that shows nothing calls it.

**Non-Goals:**

- Reimplementing Figma ingestion in any form. Nothing replaces the removed capability.
- Touching the archive. The rejected path's record is the deliverable of those changes, not
  their leftovers.
- Deleting the presentation images, or removing the slide that uses them.
- Regenerating the presentation's binary exports (`.pdf`, `.pptx`) as part of this change —
  see the decision on generated artifacts below.
- Any change to `lib/`, `modules/`, `bin/`, `web/`. Nothing there references any of this.

## Decisions

### 1. Withdraw the capability outright — do not MODIFY it into a smaller one

The delta uses `## REMOVED Requirements` for all six requirements, with a shared Reason and
Migration block.

*Alternative considered:* rewrite the spec around the v0-only pipeline, keeping the capability
name alive. Rejected — the capability is not "smaller now", it is **absent**. A spec renamed
onto a different mechanism carries the old requirements' authority to code that never agreed
to them, and the next reader cannot tell which half was ever true. The v0-only pipeline
already has its own specs; it does not need this name.

*Why the Reason block matters more than usual here:* the archive holds the measurement (the
same MCP returning 13 frames with Tailwind tokens and 3 frames of prose, four seconds apart),
and the delta is where a future reader looking at `openspec/specs/` history will land first.
The delta points at the archive rather than restating it, so there is one copy of the finding.

### 2. Keep the archive — and say so in the proposal, not just in silence

An unstated "we did not delete these" is indistinguishable from an oversight. The proposal has
a `What Explicitly Does NOT Change` section for exactly the two groups a follow-up session
would sweep next.

*Why the archive is load-bearing rather than sentimental:* another project is currently using
this repo's rejection of the MCP path as input for its own design-pipeline decision. An
archive that keeps only the answer and discards the reasoning cannot serve that. This is the
repo's own rule — record the pattern that was wrong, not only the number that is right.

### 3. Prove absence by grep before each delete, and record the command

Each deletion task carries the exact command whose empty output is the licence to delete:

```bash
grep -rn "fetch-figma-design" --exclude-dir=.git . | grep -v "^./openspec/changes/archive/" | grep -v "^./scripts/fetch-figma-design.py"
grep -rn "figma-raw/TEST\|fixtures/figma" --include="*.py" --include="*.sh" --include="*.ts" --include="*.js" --exclude-dir=.git .
```

*Why this is a decision and not a formality:* the reason this spec survived four months is
that its deletion was never checked against anything. A deletion whose safety argument is
"looked unused" produces the same artifact as one that was measured, and only one of them can
be re-checked later.

### 4. The test suite's pass/fail SET is the regression check — not a pass count

The fixture files are inputs. Deleting an input that something quietly reads turns a passing
test into an error, and this repo has a substantial pre-existing failure count that makes a
raw number meaningless. The check is a **set diff** of failing test ids before and after, per
the repo's regression-baseline procedure. An unchanged set is the pass condition; a smaller
count is not evidence of anything.

### 5. Correct the slide text; leave the images and leave the generated exports to the next build

The slide keeps both images. Its title and body currently assert a live mechanism
(`Spec + Figma Design`, `Figma Make design — the visual blueprint`, and the speaker note
`set-design-sync extracts Figma tokens → design-system.md → agents read before implementation`).
The correction says what the screenshot **is** — a design reference that was the input for
this demo — without claiming a pipeline that no longer runs.

Both source decks change: `set-core-presentation.md` (English) and `set-core-bemutato.md`
(the Hungarian translation — a translated deck beside its English original is the
English-first rule succeeding, not a breach of it).

*Generated artifacts:* `.html`, `.pdf` and `.pptx` in `docs/presentation/` are marp exports of
those `.md` files. The `.html` carries the slide text verbatim and is corrected in the same
pass. The `.pdf`/`.pptx` are binary and are **not** regenerated here — regenerating them means
running `npx @marp-team/marp-cli --allow-local-files`, which is a build with its own toolchain
requirements and would put a large binary diff in a change about deleting dead files.

*The trade-off, stated rather than hidden:* until the next presentation build, the committed
`.pdf`/`.pptx` show the old wording. That is a known, named staleness in a generated artifact
whose source is correct — not a contradiction between two live claims. The task list records
it so the next person to run the export knows it is pending rather than discovering it.

## Risks / Trade-offs

- **[A file in the "dead" group turns out to have a caller the grep missed]** → The greps run
  over the whole tracked tree, not a guessed subset, and the delete tasks are separate commits
  from the spec removal, so a revert is one file. The strongest signal is structural: the
  function these describe was deleted with its entire directory four months ago, and nothing
  has failed since.
- **[Deleting the fixture breaks a test that reads the directory by glob rather than by name]**
  → A glob would not appear in a name grep. Mitigated by running the suite and diffing the
  failure set, which catches it regardless of how the file was found.
- **[`openspec archive` behaves unexpectedly on an all-REMOVED delta]** → The archive step is
  what moves the deltas into `openspec/specs/`; a REMOVED delta must delete the spec directory
  rather than write an empty one. Verified explicitly after archive: `openspec/specs/figma-source-dispatch/`
  must not exist and must not exist as an empty file either. The repo has prior archived
  all-REMOVED deltas (`2026-04-03-remove-cli-sentinel`), so this is a check, not an unknown.
- **[Somebody later reads the archive and "restores" the capability from it]** → The delta's
  Migration block states the direction explicitly: adopt from a project with a working local
  `.fig` decode path, do not restore from here. The archive keeps the reasoning; the delta
  keeps the verdict.
- **[The presentation build is never re-run, and the binaries stay stale indefinitely]** →
  Accepted, and named in tasks. The alternative — a binary regeneration inside a deletion
  change — costs more review than the staleness costs a reader, and the sources are correct.

## Migration Plan

No runtime migration: nothing calls the removed capability, so no consumer can break.

Order matters only for reviewability, not correctness:

1. Spec removal (the delta already written) — the contract change.
2. Dead carrier deletions, each preceded by its proving grep.
3. Presentation text correction.
4. Verification: `git ls-files | grep -i figma` returns exactly 8 files (6 archive + 2 PNG),
   the test failure set is unchanged, `openspec validate --strict` no worse than baseline.
5. Archive, then confirm `openspec/specs/figma-source-dispatch/` is gone.
6. Close `B-101` in `openspec/bugs/README.md` with the commit sha.

**Rollback:** `git revert` of the deletion commits restores the files byte-for-byte. Nothing
external depends on them, so a rollback has no cleanup.

## Open Questions

None blocking. One deferred item is recorded rather than resolved: the presentation's binary
exports are regenerated whenever the deck is next built, and this change does not schedule
that build.
