<!--
Waves: each `## N.` group is one wave-board item; groups with the same W-number can run in
parallel. Layer marks: [core] = set-core, [deploy] = deploy pipeline / templates,
[consumer] = done in the originating project's own repository (its own commits, its own
evidence; nothing from it is copied into set-core). No module code is touched.
-->

## 1. W0 — Reference freeze and oracle

- [ ] 1.1 [consumer] Freeze edits to the local engine; record the reference commit SHA in the consumer's planning notes [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement]
- [x] 1.2 [core] Write a synthetic fixture corpus under `tests/fixtures/kb/` (no project content): several roots, a client-channel root, duplicates at two priorities, a file matching in many sections, accented file names, a recording `.md` + `.jsonl` pair, a `-raw-` named transcript, an agent-session dump with frontmatter type, an archive folder, build-output markdown [REQ: the-shared-engine-matches-the-reference-engine-on-a-synthetic-corpus]
- [x] 1.3 [core] Write the fixture query list and run the reference engine over the fixture (at the pinned commit) to record expected pages as JSON under `tests/fixtures/kb/expected/` [REQ: the-shared-engine-matches-the-reference-engine-on-a-synthetic-corpus]
- [x] 1.4 [core] Copy the upstream MIT text, upstream repo URL + commit and the port lineage into `lib/set_kb/LICENSE-UPSTREAM`; add the third-party entry to `README.md` [REQ: the-upstream-licence-notice-travels-with-the-engine]
  - Note: the user's decision of 2026-10-07 (design.md) narrows this — the public tree keeps the MIT copyright line and the upstream commit, and does NOT name the upstream repository or organisation.

## 2. W1 — Engine port (core)

- [x] 2.1 [core] `lib/set_kb/store.py`: schema (FTS5 `porter unicode61`, files, properties, meta), bm25 weight order tied to column order, `kb_meta` with schema + SQLite version [REQ: the-engine-runs-on-set-cores-existing-runtime]
- [x] 2.2 [core] Runtime probe: FTS5 + tokenizer check with a remediation message; no fallback [REQ: the-engine-runs-on-set-cores-existing-runtime]
- [x] 2.3 [core] `frontmatter.py`, `chunker.py` (section chunks, heading path, parent link), `lang.py` + `lang_hu.py` [REQ: search-returns-ranked-sections-one-slot-per-source]
- [x] 2.4 [core] `indexer.py`: walk, NFC + POSIX relative paths, layered mtime+size → sha256 change detection, deletions, atomic first build [REQ: paths-are-stored-repository-relative-and-normalised] [REQ: the-index-refreshes-incrementally-on-every-search]
- [x] 2.5 [core] `search.py`: BM25F, source dedup with section counts, duplicate marking by priority, diversity, limit by distinct sources [REQ: search-returns-ranked-sections-one-slot-per-source]
- [x] 2.6 [core] `channels.py` + reserved lane (quota, lead margin; empty = no lane) [REQ: channels-classify-sources-by-root-scoped-rules] [REQ: a-project-can-reserve-part-of-the-page-for-named-channels]
- [x] 2.7 [core] `get_section.py`: verbatim section fetch, leaf resolution, ambiguous-leaf listing [REQ: a-section-can-be-fetched-verbatim]
- [x] 2.8 [core] Attribution first line on every ported module; none on new ones [REQ: the-upstream-licence-notice-travels-with-the-engine]
- [x] 2.9 [core] Unit tests per module + the differential test against `tests/fixtures/kb/expected/`; all green before W2 [REQ: the-shared-engine-matches-the-reference-engine-on-a-synthetic-corpus]

## 3. W2 — Corpus defaults and index lifecycle (core)

- [x] 3.1 [core] `config.py`: defaults ← `~/.config/set-core/kb.json` ← `set/knowledge/kb.json`; `_` keys dropped; legacy-path fallback with warning; loud validation with key paths [REQ: per-project-configuration-is-project-owned-layered-and-validated]
- [x] 3.2 [core] Default exclusion list, additive `exclude`, explicit opt-out key, root-relative matching [REQ: project-exclusions-add-to-the-defaults] [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees]
- [x] 3.3 [core] `.md`-only extension default; `excludeFrontmatter` for agent-session dumps; framework files excluded via `set/.deploy-manifest.json` hash match [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees]
- [x] 3.4 [core] Scope capture (`{scope}` patterns), stored per chunk, `--scope` filter, validation [REQ: a-project-can-capture-a-scope-from-the-path-and-filter-by-it]
- [x] 3.5 [core] Index at `.set/kb/`; `git check-ignore` guard that refuses to write; corpus-config hash, schema and SQLite version force rebuild [REQ: the-index-lives-in-the-projects-runtime-directory-and-never-in-git] [REQ: the-index-refreshes-incrementally-on-every-search]
- [x] 3.6 [core] `fcntl.flock` writer lock; snapshot search with a footer note when locked; WAL + busy timeout [REQ: concurrent-callers-share-one-index-safely]
- [x] 3.7 [core] Worktree seeding from the main checkout's index [REQ: a-fresh-worktree-starts-from-the-main-checkouts-index]
- [x] 3.8 [core] Tests: additive excludes, recording pair, `-raw-` transcript, session dump, build output, edited framework file, archive, ignore guard, interrupted build, channel edit rebuild, concurrent search, worktree seed [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees]

## 4. W3 — Surfaces (core + deploy)

- [x] 4.1 [core] `bin/set-kb` with `index`, `search`, `get`, `sources`; repo-root resolution; text page with footer; `--json` contract with a version field [REQ: one-command-line-is-the-single-implementation-surface] [REQ: the-result-page-states-what-it-did-not-search] [REQ: the-json-output-is-a-stable-contract]
- [x] 4.2 [core] `kb_search` and `kb_get` in `mcp-server/set_mcp_server.py`, calling `set-kb --json` with `cwd = CLAUDE_PROJECT_DIR`; errors returned verbatim [REQ: the-mcp-server-exposes-search-to-every-initialized-project]
- [x] 4.3 [deploy] `.claude/skills/set/kb/SKILL.md` (generic) and `templates/core/rules/kb-search.md` (≤ 15 lines) [REQ: agents-are-told-when-to-search]
- [x] 4.4 [deploy] `lib/project/deploy.sh`: install skill + rule; ensure `.set/` in `.gitignore`; never write `set/knowledge/kb.json` [REQ: deploy-delivers-search-to-every-registered-project]
- [x] 4.5 [core] Tests: CLI outside a repo, zero-hit page, JSON field set, MCP error passthrough, deploy idempotence with a project config present [REQ: deploy-delivers-search-to-every-registered-project]

## 5. W3 — Verification commands (core, parallel with 4)

- [x] 5.1 [core] `set-kb doctor` with blocking vs informational checks and per-rule exclusion counts [REQ: doctor-reports-whether-search-works-in-this-project]
- [x] 5.2 [core] `set-kb findability`: recording discovery (same stem / date-and-part prefix), `findability.globs`, level 1 indexed check naming the excluding rule, level 2 title-query top-k, miss list, non-zero exit on level-1 misses [REQ: saved-recordings-and-named-notes-are-findable]
- [x] 5.3 [core] `set-kb eval`: `{id,q,targets[]}`, multi-target, control arm, fail-closed denominator, lane on/off flag, shape rejection [REQ: retrieval-eval-runs-over-a-project-owned-golden-set-with-a-control-arm]
- [x] 5.4 [core] Tests for the three commands on the fixture corpus [REQ: saved-recordings-and-named-notes-are-findable]

## 6. W4 — Cross-platform proof

- [ ] 6.1 [core] Run the unit suite and `set-kb doctor` on a macOS machine and a Linux machine; record Python + SQLite versions and outcome in the change's verification notes [REQ: the-engine-runs-on-set-cores-existing-runtime]
- [ ] 6.2 [core] Clone the fixture at two different absolute paths on each OS; confirm identical JSON pages (paths, order) across all four [REQ: paths-are-stored-repository-relative-and-normalised]
- [x] 6.3 [core] Time a full build and a no-change refresh on the largest registered corpus; target: no-change refresh under 1 s on ~4k files; record numbers (no project names) [REQ: the-index-refreshes-incrementally-on-every-search]

## 7. W5 — Rollout to every registered project

- [x] 7.1 [deploy] Re-deploy set-core to all registered projects on this machine [REQ: deploy-delivers-search-to-every-registered-project]
- [ ] 7.2 [deploy] Run `set-kb doctor` and `set-kb findability` in every registered project (E2E run directories excluded); keep the per-project results machine-local, outside set-core [REQ: saved-recordings-and-named-notes-are-findable]
- [ ] 7.3 [consumer] For each project where defaults are not enough (client channels, scopes, extra roots, lane), add `set/knowledge/kb.json` in that project's own repository and re-run findability [REQ: per-project-configuration-is-project-owned-layered-and-validated]
- [ ] 7.4 [consumer] In projects that keep recordings in client folders, configure a scope over the client folders and verify a scoped search returns no other client's material [REQ: a-project-can-capture-a-scope-from-the-path-and-filter-by-it]

## 8. W6 — Migrate the originating project (re-measure gate)

- [ ] 8.1 [consumer] Freeze a corpus snapshot; with the legacy config verbatim, run the reference engine and `set-kb eval` with the lane off and on; store both reports and the per-query page diff in the consumer repository [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement]
- [ ] 8.2 [consumer] Gate decision: hits not lower and MRR within 0.005 in both arms; on failure, list differing queries and return to W1 with a fixture reproducing the difference [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement]
- [ ] 8.3 [consumer] On pass: point the project's search script, skill and script callers at `set-kb`; move the config to `set/knowledge/kb.json` [REQ: per-project-configuration-is-project-owned-layered-and-validated]
- [ ] 8.4 [consumer] Switch to the new default corpus (recordings in, framework files out), run findability and eval again, record it as a corpus change; re-sweep the lane quota if recall or MRR moved [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement]
- [ ] 8.5 [consumer] Remove the local engine copy and its typecheck gate once 8.3 and 8.4 are recorded [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement]

## 9. W7 — Close

- [x] 9.1 [core] Document `set-kb` in `docs/` (config keys, defaults, exclusion rationale, lane, scope, verification commands) [REQ: per-project-configuration-is-project-owned-layered-and-validated]
- [ ] 9.2 [core] `openspec validate kb-search --strict`, verify, archive so the three capability specs reach `openspec/specs/` [REQ: one-command-line-is-the-single-implementation-surface]

## Acceptance Criteria (from spec scenarios)

### kb-search-engine
- [ ] AC-1: WHEN Python lacks FTS5 THEN the engine exits non-zero naming FTS5 and a remediation, and creates no index [REQ: the-engine-runs-on-set-cores-existing-runtime, scenario: python-without-fts5]
- [ ] AC-2: WHEN the same content is indexed on macOS and Linux THEN the same query returns the same sources in the same order [REQ: the-engine-runs-on-set-cores-existing-runtime, scenario: same-result-on-macos-and-linux]
- [ ] AC-3: WHEN a repo is cloned at two absolute paths THEN hit paths are identical and no index holds the clone location [REQ: paths-are-stored-repository-relative-and-normalised, scenario: repository-cloned-at-different-paths]
- [ ] AC-4: WHEN an accented file name crosses OSes THEN the stored path is NFC and found on both [REQ: paths-are-stored-repository-relative-and-normalised, scenario: accented-file-name]
- [x] AC-5: WHEN a folder holds `<stem>.jsonl` and `<stem>.md` THEN only the `.md` is indexed [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees, scenario: a-saved-recording-is-indexed-by-its-readable-form]
- [x] AC-6: WHEN a readable transcript's name contains "raw" THEN it is indexed [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees, scenario: a-readable-transcript-whose-name-contains-raw]
- [x] AC-7: WHEN an agent-session dump sits among recordings THEN the dump is excluded and the transcripts are indexed [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees, scenario: agent-session-dump-in-the-same-folder]
- [x] AC-8: WHEN build output or a virtualenv holds markdown THEN none of it is indexed [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees, scenario: build-output-carrying-markdown]
- [x] AC-9: WHEN a deployed framework file was edited by the project THEN it is indexed and unedited ones are not [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees, scenario: framework-file-edited-by-the-project]
- [x] AC-10: WHEN a file is under an archive folder THEN it is indexed [REQ: the-default-corpus-is-every-readable-markdown-file-outside-generated-and-log-trees, scenario: archived-change]
- [x] AC-11: WHEN a project adds one exclude pattern THEN all defaults stay in force [REQ: project-exclusions-add-to-the-defaults, scenario: adding-one-exclusion]
- [x] AC-12: WHEN a project lifts one default explicitly THEN only that one is lifted and the footer shows it [REQ: project-exclusions-add-to-the-defaults, scenario: dropping-a-default-on-purpose]
- [x] AC-13: WHEN `.set/` is not ignored THEN the engine refuses to build and names the path [REQ: the-index-lives-in-the-projects-runtime-directory-and-never-in-git, scenario: runtime-directory-not-ignored]
- [x] AC-14: WHEN a search built the index THEN `git status` lists nothing under `.set/kb/` [REQ: the-index-lives-in-the-projects-runtime-directory-and-never-in-git, scenario: index-never-staged]
- [x] AC-15: WHEN a note is saved and searched right after THEN it is on the page [REQ: the-index-refreshes-incrementally-on-every-search, scenario: a-new-note-is-found-immediately]
- [x] AC-16: WHEN the first build is killed THEN no index exists at the final path and the next search rebuilds [REQ: the-index-refreshes-incrementally-on-every-search, scenario: interrupted-first-build]
- [x] AC-17: WHEN channel rules change THEN the next search reclassifies unchanged files [REQ: the-index-refreshes-incrementally-on-every-search, scenario: channel-rules-edited]
- [x] AC-18: WHEN no-reindex is set THEN the index is not modified [REQ: the-index-refreshes-incrementally-on-every-search, scenario: measurement-run-without-refresh]
- [x] AC-19: WHEN a new worktree searches first THEN its index is seeded from the main checkout [REQ: a-fresh-worktree-starts-from-the-main-checkouts-index, scenario: search-in-a-new-worktree]
- [x] AC-20: WHEN two searches start together THEN one refreshes, the other uses the snapshot with a note, neither fails [REQ: concurrent-callers-share-one-index-safely, scenario: two-agents-search-at-once]
- [x] AC-21: WHEN one file matches in six sections THEN it takes one slot reporting five more [REQ: search-returns-ranked-sections-one-slot-per-source, scenario: a-file-that-owns-the-topic]
- [x] AC-22: WHEN identical content sits at two priorities THEN the higher-priority path is returned, marked duplicate [REQ: search-returns-ranked-sections-one-slot-per-source, scenario: identical-content-at-two-paths]
- [x] AC-23: WHEN a channel rule has no roots THEN config loading fails naming it [REQ: channels-classify-sources-by-root-scoped-rules, scenario: rule-without-roots]
- [x] AC-24: WHEN a same-named folder exists under another root THEN it is not classified into the channel [REQ: channels-classify-sources-by-root-scoped-rules, scenario: same-folder-name-under-a-different-root]
- [x] AC-25: WHEN half the page is reserved for a client channel THEN client hits take their share [REQ: a-project-can-reserve-part-of-the-page-for-named-channels, scenario: client-voice-buried-by-planning-documents]
- [x] AC-26: WHEN no lane channels are configured THEN ranking is by score alone [REQ: a-project-can-reserve-part-of-the-page-for-named-channels, scenario: no-lane-configured]
- [x] AC-27: WHEN a search is restricted to one client scope THEN no other client's file appears [REQ: a-project-can-capture-a-scope-from-the-path-and-filter-by-it, scenario: searching-one-clients-folder]
- [x] AC-28: WHEN a scope pattern lacks `{scope}` THEN config loading fails naming it [REQ: a-project-can-capture-a-scope-from-the-path-and-filter-by-it, scenario: pattern-without-placeholder]
- [x] AC-29: WHEN a ported module is opened THEN its first line points at the notice, which holds the full MIT text and the upstream commit [REQ: the-upstream-licence-notice-travels-with-the-engine, scenario: auditing-a-ported-module]

### kb-search-access
- [x] AC-30: WHEN search runs in a subdirectory THEN it uses the project index and prints root-relative paths [REQ: one-command-line-is-the-single-implementation-surface, scenario: searching-from-any-folder-in-the-project]
- [x] AC-31: WHEN run outside a repository THEN it exits non-zero saying no project was found [REQ: one-command-line-is-the-single-implementation-surface, scenario: outside-a-repository]
- [x] AC-32: WHEN there are zero hits THEN the page prints the exact query and the exclusions [REQ: the-result-page-states-what-it-did-not-search, scenario: zero-hits]
- [x] AC-33: WHEN 40 sources match with limit 8 THEN the page states 32 more [REQ: the-result-page-states-what-it-did-not-search, scenario: results-beyond-the-limit]
- [x] AC-34: WHEN a script reads `hits[0].path` THEN `set-kb get` accepts it unchanged [REQ: the-json-output-is-a-stable-contract, scenario: a-script-consumes-the-hits]
- [x] AC-35: WHEN a leaf heading is ambiguous THEN both full paths are listed and no section printed [REQ: a-section-can-be-fetched-verbatim, scenario: ambiguous-leaf-heading]
- [x] AC-36: WHEN an agent calls `kb_search` THEN it gets hits from its own project's index [REQ: the-mcp-server-exposes-search-to-every-initialized-project, scenario: agent-in-a-project-calls-the-tool]
- [x] AC-37: WHEN `set-kb` fails THEN `kb_search` returns the error text [REQ: the-mcp-server-exposes-search-to-every-initialized-project, scenario: engine-failure-surfaces]
- [x] AC-38: WHEN `set-kb sources` runs THEN each root and channel shows its configured description [REQ: agents-are-told-when-to-search, scenario: project-specific-layers]
- [x] AC-39: WHEN the deployed rule is measured THEN it is at most 15 lines [REQ: agents-are-told-when-to-search, scenario: rule-size]
- [x] AC-40: WHEN a configured project is re-deployed THEN its config is unchanged and skill + rule updated [REQ: deploy-delivers-search-to-every-registered-project, scenario: re-deploy-keeps-the-project-config]
- [x] AC-41: WHEN `.set/` is not ignored at deploy THEN deploy adds and reports the entry [REQ: deploy-delivers-search-to-every-registered-project, scenario: project-without-ignore-entry]
- [x] AC-42: WHEN a config has `_` keys THEN they have no effect [REQ: per-project-configuration-is-project-owned-layered-and-validated, scenario: documentation-keys]
- [x] AC-43: WHEN only the legacy config exists THEN it is used with one warning naming the new path [REQ: per-project-configuration-is-project-owned-layered-and-validated, scenario: legacy-location]
- [x] AC-44: WHEN the language has no pack THEN loading fails naming the key and available packs [REQ: per-project-configuration-is-project-owned-layered-and-validated, scenario: unknown-language]

### kb-search-eval
- [x] AC-45: WHEN the project is healthy THEN doctor exits zero with per-root, channel and rule counts [REQ: doctor-reports-whether-search-works-in-this-project, scenario: healthy-project]
- [x] AC-46: WHEN a rule removes most of a root THEN doctor prints that rule and count [REQ: doctor-reports-whether-search-works-in-this-project, scenario: excluded-share-made-visible]
- [x] AC-47: WHEN a transcript is hidden by an exclusion THEN findability names the rule and exits non-zero [REQ: saved-recordings-and-named-notes-are-findable, scenario: recording-hidden-by-an-exclusion]
- [x] AC-48: WHEN a transcript is indexed THEN its title query returns it in the top 10 [REQ: saved-recordings-and-named-notes-are-findable, scenario: recording-retrievable-by-its-title]
- [x] AC-49: WHEN a project lists findability globs THEN those notes are checked like recordings [REQ: saved-recordings-and-named-notes-are-findable, scenario: a-note-the-project-wants-guaranteed]
- [x] AC-50: WHEN a golden query errors THEN the denominator is kept and the failure listed [REQ: retrieval-eval-runs-over-a-project-owned-golden-set-with-a-control-arm, scenario: failed-search]
- [x] AC-51: WHEN the control arm runs THEN the control query is printed with its recall [REQ: retrieval-eval-runs-over-a-project-owned-golden-set-with-a-control-arm, scenario: control-arm]
- [x] AC-52: WHEN eval disables the lane THEN no query in the run uses it [REQ: retrieval-eval-runs-over-a-project-owned-golden-set-with-a-control-arm, scenario: lane-disabled-for-measurement]
- [x] AC-53: WHEN an engine change alters a fixture order THEN the differential test fails naming the query [REQ: the-shared-engine-matches-the-reference-engine-on-a-synthetic-corpus, scenario: ranking-drift]
- [ ] AC-54: WHEN the shared engine matches hits and MRR within 0.005 in both arms THEN the project may switch [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement, scenario: gate-passes]
- [ ] AC-55: WHEN it finds fewer targets in either arm THEN the project keeps its engine and differing queries are listed [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement, scenario: gate-fails]
- [ ] AC-56: WHEN the project moves to the new default corpus THEN eval is re-run and recorded as a corpus change [REQ: moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement, scenario: corpus-change-measured-on-its-own]
