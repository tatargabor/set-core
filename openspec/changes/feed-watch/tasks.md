## 1. Declaration and package skeleton

- [x] 1.1 Create `lib/set_feedwatch/` with logging, and a declaration loader/validator for `.set/feed-watch.yaml` (version, dir, sources, rubric, drafts, digest) that fails with the missing or unknown key named [REQ: project-opt-in-by-declaration]
- [x] 1.2 Add `bin/set-feed-watch` with the subcommands `seen`, `check-new`, `digest`, `gate` and `optin`; exit non-zero and write nothing when no declaration exists [REQ: project-opt-in-by-declaration]
- [x] 1.3 Deploy the skill only when `.set/feed-watch.yaml` exists (in `_deploy_skills`, see design "Changed during implementation"); `set-project init --dry-run` on a scratch repo without the file mentions feed-watch 0 times, and with the file it plans the skill [REQ: project-opt-in-by-declaration]

## 2. Items and dedupe

- [x] 2.1 Item file parser: header fields by the declared labels, verbatim body between the first two `---` lines, with the scoring-section fallback [REQ: one-file-per-item-with-the-verbatim-text]
- [x] 2.2 Text hash (SHA-1, lower-cased, whitespace-collapsed, 12 hex digits), with a fixture test pinning hashes produced by the first version's algorithm [REQ: dedupe-by-item-id-or-text-hash]
- [x] 2.3 `seen` and `check-new` (exit 0 = new, exit 3 = known, print the stored path) [REQ: dedupe-by-item-id-or-text-hash]
- [x] 2.4 Source adapter interface plus the `facebook-group` adapter (permalink pattern, item-id extraction, sort hint); an unknown `kind` fails validation [REQ: source-adapter-boundary]

## 3. Scoring, digest, drafts

- [x] 3.1 Whole-line marker parser with a configurable marker name; fenced blocks are ignored; missing, malformed or out-of-range markers give unscored with a reason [REQ: score-marker-parsing]
- [x] 3.2 Threshold evaluation (`total_min` plus `dimension_min`) [REQ: threshold-decides-drafts]
- [x] 3.3 `digest <date>`: ranked list, reason lines, links, and warnings for unscored items and missing drafts; the filename comes from the declaration [REQ: daily-digest]
- [x] 3.4 `gate <file>`: extract the declared fenced blocks and the subject, run the declared command per block, exit non-zero naming the failing block; with no gate declared, say "no gate configured" [REQ: reply-drafts-are-gated-text-a-human-sends]
- [x] 3.5 Validation fails when no rubric is declared; ship no default rubric [REQ: project-declared-rubric]

## 4. Skill

- [x] 4.1 Write the generic skill template: preparation (window in front, `seen`, one tab), collection loop, stop conditions, item files, scoring by the project's guidance file, drafts by the project's template, gate, digest, and a report with separate counts [REQ: read-only-collection]
- [x] 4.2 The skill states the read-only rule and names only the declared feed URLs [REQ: read-only-collection]
- [x] 4.3 The stop conditions in the skill: two empty scrolls, login wall, captcha, verification, error page, cap, age, newest-known; a zero-item run with placeholders is reported as a stall [REQ: collection-stops-on-a-stall-or-challenge]
- [x] 4.4 The report format with seen, new, duplicate and filtered counts and the stop reason [REQ: run-report-keeps-the-counts-separate]

## 5. Scheduled pane

- [x] 5.1 Lift the pure scheduling logic (config parse, account match, due slot, lease, answer) into the plugin template, together with its tests [REQ: scheduled-pane-with-four-actions]
- [x] 5.2 Opt-in storage under `~/.config/set-core/feed-watch.json`, keyed by project; `optin on|off|status` [REQ: per-account-opt-in-outside-the-repository]
- [x] 5.3 Lease in `feed-watch.state.json` so only one session shows a slot [REQ: one-session-asks]
- [x] 5.4 `optin import <path>`, which does not touch the source file [REQ: import-of-an-existing-opt-in]
- [ ] 5.5 VISUAL CHECK: open the pane in a real Claude Code session at a due slot, look at it, and record what was seen; this stays open if it could not be looked at [REQ: scheduled-pane-with-four-actions]

## 6. Migration proof against the first version

- [x] 6.1 Write a declaration that maps the consumer's existing layout. `seen` id and hash columns must be IDENTICAL to the first version's; the digest's item set, order, totals, verdicts and warnings must match (wording is the module's own, see design). Measured on a scratch copy of the consumer's files (2 items): all of these matched, and the consumer tree was left untouched [REQ: dedupe-by-item-id-or-text-hash]
- [x] 6.2 Logging check: no item text, author or contact detail in any log line [REQ: read-only-collection]

## Acceptance Criteria (from spec scenarios)

### project-opt-in-by-declaration
- [x] AC-1: WHEN set-feed-watch runs without .set/feed-watch.yaml THEN it exits non-zero naming the file and writes nothing [REQ: project-opt-in-by-declaration, scenario: project-without-a-declaration] — test_no_declaration_exits_nonzero_and_writes_nothing
- [x] AC-2: WHEN set-project init runs for a non-opted-in project THEN no feed-watch file is written [REQ: project-opt-in-by-declaration, scenario: deploy-without-opt-in] — dry-run measurement, task 1.3

### read-only-collection
- [x] AC-3: WHEN the deployed skill is read THEN it forbids posting, commenting, reacting and sending, and names only the declared feeds [REQ: read-only-collection, scenario: the-skill-forbids-writes-to-the-source] — skill text: Iron rules

### collection-stops-on-a-stall-or-challenge
- [ ] AC-4: WHEN a login wall appears THEN the run stops and reports the reason and the count so far [REQ: collection-stops-on-a-stall-or-challenge, scenario: login-wall] — OPEN: needs a live collection run in Chrome; the skill states it, no run has measured it
- [ ] AC-5: WHEN a run collects zero with placeholders visible THEN a stall is reported, not "no new items" [REQ: collection-stops-on-a-stall-or-challenge, scenario: empty-run-with-the-feed-visible] — OPEN: needs a live collection run in Chrome; the skill states it, no run has measured it

### run-report-keeps-the-counts-separate
- [ ] AC-6: WHEN 12 are seen, 3 are duplicates and 4 are filtered THEN the report shows 12/5/3/4 plus the stop reason [REQ: run-report-keeps-the-counts-separate, scenario: mixed-run] — OPEN: needs a live collection run in Chrome; the skill states it, no run has measured it

### one-file-per-item-with-the-verbatim-text
- [ ] AC-7: WHEN an item with typos is collected THEN the body equals the source exactly [REQ: one-file-per-item-with-the-verbatim-text, scenario: verbatim-body] — OPEN: needs a live collection run in Chrome; the skill states it, no run has measured it

### dedupe-by-item-id-or-text-hash
- [x] AC-8: WHEN the same normalised text arrives with an unknown link THEN check-new exits 3 and prints the stored path [REQ: dedupe-by-item-id-or-text-hash, scenario: same-text-different-link] — test_same_text_different_link_is_known
- [x] AC-9: WHEN seen runs over first-version files THEN the hashes are identical [REQ: dedupe-by-item-id-or-text-hash, scenario: hash-compatibility-with-existing-items] — test_hash_is_the_first_versions_algorithm + migration 6.1

### source-adapter-boundary
- [x] AC-10: WHEN a declaration names an unknown kind THEN validation fails naming it [REQ: source-adapter-boundary, scenario: unknown-source-kind] — test_unknown_source_kind_fails_naming_it

### project-declared-rubric
- [x] AC-11: WHEN digest runs without a rubric THEN validation fails naming the key [REQ: project-declared-rubric, scenario: declaration-without-a-rubric] — test_digest_without_rubric_fails_naming_the_key

### score-marker-parsing
- [x] AC-12: WHEN a dimension exceeds its maximum THEN the item is unscored, with a reason [REQ: score-marker-parsing, scenario: out-of-range-value] — test_out_of_range_value_is_unscored_not_zero
- [x] AC-13: WHEN the marker appears only inside a fence THEN it is not read [REQ: score-marker-parsing, scenario: marker-inside-a-fenced-example] — test_marker_inside_a_fence_is_not_read

### threshold-decides-drafts
- [x] AC-14: WHEN the total is high but a gating dimension is low THEN the item does not qualify [REQ: threshold-decides-drafts, scenario: high-total-low-gating-dimension] — test_high_total_low_gating_dimension_does_not_qualify

### daily-digest
- [x] AC-15: WHEN a qualifying item has no draft THEN the digest warns naming it [REQ: daily-digest, scenario: missing-draft] — test_digest_ranks_and_warns

### reply-drafts-are-gated-text-a-human-sends
- [x] AC-16: WHEN the gate rejects a block THEN gate exits non-zero naming the block [REQ: reply-drafts-are-gated-text-a-human-sends, scenario: gate-failure] — test_gate_failure_names_the_block
- [x] AC-17: WHEN no gate is declared THEN gate says so and does not report a pass [REQ: reply-drafts-are-gated-text-a-human-sends, scenario: no-gate-declared] — test_no_gate_declared_is_not_a_pass

### per-account-opt-in-outside-the-repository
- [x] AC-18: WHEN another account loads the plugin THEN no pane or notification appears [REQ: per-account-opt-in-outside-the-repository, scenario: another-account] — panel.test.tsx 'another account' + test_optin_is_per_account
- [x] AC-19: WHEN optin on runs THEN the entry is under ~/.config/set-core and the tree is unchanged [REQ: per-account-opt-in-outside-the-repository, scenario: opt-in-command] — test_optin_on_writes_outside_the_tree

### scheduled-pane-with-four-actions
- [x] AC-20: WHEN the user snoozes THEN no pane appears for 60 minutes [REQ: scheduled-pane-with-four-actions, scenario: snooze] — logic.test.ts 'snooze' + panel.test.tsx snooze
- [x] AC-21: WHEN the user picks off THEN the opt-in is disabled until re-enabled [REQ: scheduled-pane-with-four-actions, scenario: off] — panel.test.tsx 'Switch off' + test_optin_is_per_account

### one-session-asks
- [x] AC-22: WHEN two sessions reach the same slot THEN only the lease holder shows the pane [REQ: one-session-asks, scenario: two-sessions-at-the-slot-time] — logic.test.ts 'the lease' (pure logic; not two live sessions)

### import-of-an-existing-opt-in
- [x] AC-23: WHEN an opt-in is imported THEN the account and times match and the source is byte-identical [REQ: import-of-an-existing-opt-in, scenario: import] — test_import_copies_and_leaves_the_source_byte_identical
