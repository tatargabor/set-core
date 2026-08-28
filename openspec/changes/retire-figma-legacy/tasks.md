## 1. Baseline before anything is deleted

- [x] 1.1 Record the pre-change figma inventory verbatim: `git ls-files | grep -i figma | grep -v '^openspec/changes/retire-figma-legacy/'` — 12 files. **The change's own five files match `figma` too** (the change is named `retire-figma-legacy`), so the raw grep returns 17 and the number drifts as the change moves through archive; the filter is what makes 12→8 a stable measurement rather than a moving one. Save the list; step 5.1 diffs against it [REQ: source-file-discovery-from-figma-raw-directory]
- [x] 1.2 Build a test-failure baseline per the repo's regression-baseline procedure (set of failing test ids, NOT a count — this repo carries pre-existing failure debt that makes a count meaningless). Save the id set. **Measured:** isolated worktree at HEAD, `FIRSTPARTY LEAK: 0` (proven by the error text naming `base/lib/set_orch/api/__init__.py`), **116 failure entries**, `91 failed, 4477 passed, 21 errors` [REQ: source-file-discovery-from-figma-raw-directory]
- [x] 1.3 Record the pre-change `openspec validate --strict` result for the whole repo, so step 5.3 compares against a measured baseline rather than an assumed clean one. **Measured:** `316 passed, 146 failed (462 items)` — and `figma-source-dispatch` is in the PASSING set, which is the defect in one line: it validates cleanly as a live contract [REQ: source-file-discovery-from-figma-raw-directory]

## 2. Withdraw the capability

- [x] 2.1 Delete `openspec/specs/figma-source-dispatch/` (spec.md and the directory). The delta spec in this change is what records the removal; the archive step later moves it into place [REQ: source-file-discovery-from-figma-raw-directory]
- [x] 2.2 Verify nothing else references the capability name: `grep -rn "figma-source-dispatch" --exclude-dir=.git .` returns only this change's own files and the archived `2026-03-15-design-fidelity-bridge` files. **Measured:** every hit is a change document, the archive, or the bug register — zero live code references [REQ: source-file-discovery-from-figma-raw-directory]
- [ ] 2.3 Commit the spec removal on its own, with a pathspec-limited commit (another session works in this checkout) [REQ: source-file-discovery-from-figma-raw-directory]

## 3. Delete the dead carriers, each proven absent first

- [x] 3.1 Run the proving grep for the fetch script and paste its output into the commit message. **The grep as planned was wrong and is corrected here:** its `^./openspec/...` filters never matched, because `grep -rn <pattern> .` prints paths WITHOUT the `./` prefix. It over-reported rather than under-reported, so nothing was hidden — but a filter that silently matches nothing is exactly the shape that hides a finding in the other direction. The grep that actually proves the point asks about CODE, not prose:
  ```
  grep -rn "fetch-figma-design\|fetch_figma_design" --include="*.py" --include="*.sh" --include="*.ts" --include="*.js" --include="*.tsx" --include="*.yaml" --include="*.yml" --include="*.toml" --include="*.json" --exclude-dir=.git . | grep -v "^scripts/fetch-figma-design.py:"
  ```
  **Measured: EMPTY.** Also checked: no `console_scripts` entry in `pyproject.toml`, no symlink in `bin/` [REQ: scope-based-source-file-matching]
- [x] 3.2 Delete `scripts/fetch-figma-design.py` [REQ: scope-based-source-file-matching]
- [x] 3.3 Run the proving grep for the fixture: `grep -rn "figma-raw/TEST\|fixtures/figma" --include="*.py" --include="*.sh" --include="*.ts" --include="*.js" --exclude-dir=.git .` must be EMPTY. **Measured: EMPTY.** A glob-based reader would not appear here — that is what step 5.2 covers [REQ: ui-primitive-exclusion]
- [x] 3.4 Delete `tests/fixtures/figma-raw/TEST/sources/` (4 `.tsx`/`.ts` files) and any directory left empty by it — the whole `tests/fixtures/figma-raw/` tree is gone. **Found while doing this, NOT acted on (out of scope):** `tests/fixtures/design-snapshot.md` is a second zero-reference orphan in the same directory (`grep -rn "fixtures/design-snapshot"` is empty). It is not named in this change's proposal or specs, so it stays — reported to the user instead of swept in [REQ: ui-primitive-exclusion]
- [ ] 3.5 Commit the two deletions with the proving greps quoted, pathspec-limited [REQ: scope-based-source-file-matching]

## 4. Correct the presentation's stale claim

- [x] 4.1 In `docs/presentation/set-core-presentation.md` (slide at :326 area): correct the title `Spec + Figma Design` and the line `**Right:** Figma Make design — the visual blueprint` so they describe the screenshot as a design reference rather than asserting a live pipeline. Keep BOTH image references unchanged. **Measured while doing this, and it made the correction bigger than planned:** `set-design-sync` — the tool the slide credits — **does not exist**. `git ls-files | grep design-sync` is empty and it is not on `PATH`; only documentation mentions it (10+ files). So the slide was not merely stale about Figma, it named a tool that is not in the repository. The new text claims only what is true: tokens live in a committed `design-system.md` and the dispatcher passes each agent its matching part [REQ: source-file-content-output-format]
- [x] 4.2 In `docs/presentation/set-core-bemutato.md` (:347 area): apply the same correction to the Hungarian deck. This deck is a deliberate translation beside its English original and stays Hungarian [REQ: source-file-content-output-format]
- [x] 4.3 In `scripts/build-presentation.py:298`: correct the speaker note `set-design-sync extracts Figma tokens → design-system.md → agents read before implementation`, which names a mechanism the roadmap records as dropped. Keep the `storefront-design.png` path — it is live build input [REQ: source-file-content-output-format]
- [x] 4.4 Apply the same text correction to the two generated `.html` decks (`set-core-presentation.html`, `set-core-bemutato.html`), which carry the slide text verbatim [REQ: source-file-content-output-format]
- [x] 4.5 Record in the commit message that `docs/presentation/*.pdf` and `*.pptx` still carry the OLD wording and are refreshed by the next marp build (`npx @marp-team/marp-cli <deck>.md -o <deck>.pdf --allow-local-files`). A named staleness in a generated artifact, not a silent one. **Verified after the edit:** `grep -rn 'Spec + Figma Design|set-design-sync extracts|Figma Make design'` over both decks, both HTMLs and `build-presentation.py` is EMPTY, and both `.md` decks still carry exactly one `auto/figma/storefront-design.png` reference [REQ: source-file-content-output-format]

## 5. Verify the removal did not take anything with it

- [ ] 5.1 `git ls-files | grep -i figma | grep -v '^openspec/changes/retire-figma-legacy/'` returns exactly 8 files: the 6 archived change documents and the 2 presentation PNGs. Diff against the 1.1 inventory and confirm the 4 that left are the intended ones [REQ: total-output-budget-of-300-lines]
- [ ] 5.2 Re-run the test suite and diff the failing-test-id SET against the 1.2 baseline. Unchanged set is the pass condition. A smaller count is not evidence — a fixture deleted out from under a glob-based reader turns a pass into an ERROR, which is what this catches [REQ: total-output-budget-of-300-lines]
- [ ] 5.3 `openspec validate --strict` across the repo is no worse than the 1.3 baseline [REQ: total-output-budget-of-300-lines]
- [ ] 5.4 Confirm the presentation still builds its slide: `scripts/build-presentation.py` resolves `docs/images/auto/figma/storefront-design.png` and the file exists [REQ: shared-data-files-always-included]
- [ ] 5.5 Confirm the archive was NOT touched: the 6 files under `openspec/changes/archive/2026-03-15-*` are unchanged in `git status` and still contain the MCP-instability finding [REQ: shared-data-files-always-included]

## 6. Close the loop

- [ ] 6.1 Archive the change, then verify `openspec/specs/figma-source-dispatch/` does not exist — neither as a directory nor as an empty file. An all-REMOVED delta must delete the spec, not write an empty one [REQ: source-file-discovery-from-figma-raw-directory]
- [ ] 6.2 Close `B-101` in `openspec/bugs/README.md` with the commit sha and the 5.1 file count as evidence. Closed with evidence, never deleted [REQ: source-file-discovery-from-figma-raw-directory]

## Acceptance Criteria (from spec scenarios)

Every scenario below belongs to a REMOVED requirement, so each acceptance criterion asserts
that the behaviour is **gone and unreachable** — not that it works. A criterion phrased the
other way would be an acceptance test for the thing this change withdraws.

### Source file discovery from figma-raw directory

- [ ] AC-1: WHEN a project contains `docs/figma-raw/<key>/sources/` THEN nothing in set-core discovers it — no tracked file defines or calls `design_sources_for_dispatch()`, verified by `grep -rn "design_sources_for_dispatch" --exclude-dir=.git .` returning only archived change documents [REQ: source-file-discovery-from-figma-raw-directory, scenario: sources-directory-exists-with-files]
- [ ] AC-2: WHEN a project has no `docs/figma-raw/` directory THEN no code path notices or reports it, because no such code path exists — `lib/design/` is absent from `git ls-files` [REQ: source-file-discovery-from-figma-raw-directory, scenario: no-figma-raw-directory-exists]

### UI primitive exclusion

- [ ] AC-3: WHEN the tree is searched for the shadcn primitive fixture `src__components__ui__button.tsx` THEN it is not found — the fixture directory is deleted and no test references it [REQ: ui-primitive-exclusion, scenario: shadcn-button-tsx-excluded]

### Scope-based source file matching

- [ ] AC-4: WHEN a change's scope text mentions "product" THEN no Figma source matching runs anywhere in dispatch — `scripts/fetch-figma-design.py` is deleted and has no caller [REQ: scope-based-source-file-matching, scenario: scope-mentions-product-and-card]
- [ ] AC-5: WHEN a change's scope text mentions "cart" THEN the same holds; the fixtures `src__app__Cart.tsx` and `src__app__data__mockData.ts` are no longer in the tree [REQ: scope-based-source-file-matching, scenario: scope-mentions-cart]
- [ ] AC-6: WHEN scope text contains only infrastructure terms THEN there is no matcher to return empty and no exit code to check — the requirement is withdrawn, not weakened [REQ: scope-based-source-file-matching, scenario: no-keyword-matches]

### Source file content output format

- [ ] AC-7: WHEN the presentation deck is read THEN it no longer asserts a Figma design pipeline — the corrected slide text in both decks and in `scripts/build-presentation.py` describes a design reference, while both image references still resolve [REQ: source-file-content-output-format, scenario: two-files-matched]

### Total output budget of 300 lines

- [ ] AC-8: WHEN `git ls-files | grep -i figma | grep -v '^openspec/changes/retire-figma-legacy/'` is run after the change THEN it returns exactly 8 files (6 archive + 2 presentation PNGs), and the test failure-id set is identical to the pre-change baseline [REQ: total-output-budget-of-300-lines, scenario: budget-exceeded]

### Shared data files always included

- [ ] AC-9: WHEN the archive is inspected after the change THEN all 6 files under `openspec/changes/archive/2026-03-15-*` are byte-identical to their pre-change state, and the presentation build still resolves `docs/images/auto/figma/storefront-design.png` [REQ: shared-data-files-always-included, scenario: product-page-scope-with-mockdata]
