## 1. Declaration and package skeleton

- [ ] 1.1 Create `lib/set_feedwatch/` with logging, and a declaration loader/validator for `.set/feed-watch.yaml` (version, dir, sources, rubric, drafts, digest) that fails with the missing or unknown key named [REQ: project-opt-in-by-declaration]
- [ ] 1.2 Add `bin/set-feed-watch` with the subcommands `seen`, `check-new`, `digest`, `gate` and `optin`; exit non-zero and write nothing when no declaration exists [REQ: project-opt-in-by-declaration]
- [ ] 1.3 Add the template as an optional deploy-manifest `modules:` entry, and test that a non-opted-in `set-project init --dry-run` plans zero feed-watch files [REQ: project-opt-in-by-declaration]

## 2. Items and dedupe

- [ ] 2.1 Item file parser: header fields by the declared labels, verbatim body between the first two `---` lines, with the scoring-section fallback [REQ: one-file-per-item-with-the-verbatim-text]
- [ ] 2.2 Text hash (SHA-1, lower-cased, whitespace-collapsed, 12 hex digits), with a fixture test pinning hashes produced by the first version's algorithm [REQ: dedupe-by-item-id-or-text-hash]
- [ ] 2.3 `seen` and `check-new` (exit 0 = new, exit 3 = known, print the stored path) [REQ: dedupe-by-item-id-or-text-hash]
- [ ] 2.4 Source adapter interface plus the `facebook-group` adapter (permalink pattern, item-id extraction, sort hint); an unknown `kind` fails validation [REQ: source-adapter-boundary]

## 3. Scoring, digest, drafts

- [ ] 3.1 Whole-line marker parser with a configurable marker name; fenced blocks are ignored; missing, malformed or out-of-range markers give unscored with a reason [REQ: score-marker-parsing]
- [ ] 3.2 Threshold evaluation (`total_min` plus `dimension_min`) [REQ: threshold-decides-drafts]
- [ ] 3.3 `digest <date>`: ranked list, reason lines, links, and warnings for unscored items and missing drafts; the filename comes from the declaration [REQ: daily-digest]
- [ ] 3.4 `gate <file>`: extract the declared fenced blocks and the subject, run the declared command per block, exit non-zero naming the failing block; with no gate declared, say "no gate configured" [REQ: reply-drafts-are-gated-text-a-human-sends]
- [ ] 3.5 Validation fails when no rubric is declared; ship no default rubric [REQ: project-declared-rubric]

## 4. Skill

- [ ] 4.1 Write the generic skill template: preparation (window in front, `seen`, one tab), collection loop, stop conditions, item files, scoring by the project's guidance file, drafts by the project's template, gate, digest, and a report with separate counts [REQ: read-only-collection]
- [ ] 4.2 The skill states the read-only rule and names only the declared feed URLs [REQ: read-only-collection]
- [ ] 4.3 The stop conditions in the skill: two empty scrolls, login wall, captcha, verification, error page, cap, age, newest-known; a zero-item run with placeholders is reported as a stall [REQ: collection-stops-on-a-stall-or-challenge]
- [ ] 4.4 The report format with seen, new, duplicate and filtered counts and the stop reason [REQ: run-report-keeps-the-counts-separate]

## 5. Scheduled pane

- [ ] 5.1 Lift the pure scheduling logic (config parse, account match, due slot, lease, answer) into the plugin template, together with its tests [REQ: scheduled-pane-with-four-actions]
- [ ] 5.2 Opt-in storage under `~/.config/set-core/feed-watch.json`, keyed by project; `optin on|off|status` [REQ: per-account-opt-in-outside-the-repository]
- [ ] 5.3 Lease in `feed-watch.state.json` so only one session shows a slot [REQ: one-session-asks]
- [ ] 5.4 `optin import <path>`, which does not touch the source file [REQ: import-of-an-existing-opt-in]
- [ ] 5.5 VISUAL CHECK: open the pane in a real Claude Code session at a due slot, look at it, and record what was seen; this stays open if it could not be looked at [REQ: scheduled-pane-with-four-actions]

## 6. Migration proof against the first version

- [ ] 6.1 Write a declaration that maps the consumer's existing layout; `seen` and `digest` output must diff empty against the first version's output on the same files (run in the consumer tree; persist nothing from it here) [REQ: dedupe-by-item-id-or-text-hash]
- [ ] 6.2 Logging check: no item text, author or contact detail in any log line [REQ: read-only-collection]

## Acceptance Criteria (from spec scenarios)

### project-opt-in-by-declaration
- [ ] AC-1: WHEN set-feed-watch runs without .set/feed-watch.yaml THEN it exits non-zero naming the file and writes nothing [REQ: project-opt-in-by-declaration, scenario: project-without-a-declaration]
- [ ] AC-2: WHEN set-project init runs for a non-opted-in project THEN no feed-watch file is written [REQ: project-opt-in-by-declaration, scenario: deploy-without-opt-in]

### read-only-collection
- [ ] AC-3: WHEN the deployed skill is read THEN it forbids posting, commenting, reacting and sending, and names only the declared feeds [REQ: read-only-collection, scenario: the-skill-forbids-writes-to-the-source]

### collection-stops-on-a-stall-or-challenge
- [ ] AC-4: WHEN a login wall appears THEN the run stops and reports the reason and the count so far [REQ: collection-stops-on-a-stall-or-challenge, scenario: login-wall]
- [ ] AC-5: WHEN a run collects zero with placeholders visible THEN a stall is reported, not "no new items" [REQ: collection-stops-on-a-stall-or-challenge, scenario: empty-run-with-the-feed-visible]

### run-report-keeps-the-counts-separate
- [ ] AC-6: WHEN 12 are seen, 3 are duplicates and 4 are filtered THEN the report shows 12/5/3/4 plus the stop reason [REQ: run-report-keeps-the-counts-separate, scenario: mixed-run]

### one-file-per-item-with-the-verbatim-text
- [ ] AC-7: WHEN an item with typos is collected THEN the body equals the source exactly [REQ: one-file-per-item-with-the-verbatim-text, scenario: verbatim-body]

### dedupe-by-item-id-or-text-hash
- [ ] AC-8: WHEN the same normalised text arrives with an unknown link THEN check-new exits 3 and prints the stored path [REQ: dedupe-by-item-id-or-text-hash, scenario: same-text-different-link]
- [ ] AC-9: WHEN seen runs over first-version files THEN the hashes are identical [REQ: dedupe-by-item-id-or-text-hash, scenario: hash-compatibility-with-existing-items]

### source-adapter-boundary
- [ ] AC-10: WHEN a declaration names an unknown kind THEN validation fails naming it [REQ: source-adapter-boundary, scenario: unknown-source-kind]

### project-declared-rubric
- [ ] AC-11: WHEN digest runs without a rubric THEN validation fails naming the key [REQ: project-declared-rubric, scenario: declaration-without-a-rubric]

### score-marker-parsing
- [ ] AC-12: WHEN a dimension exceeds its maximum THEN the item is unscored, with a reason [REQ: score-marker-parsing, scenario: out-of-range-value]
- [ ] AC-13: WHEN the marker appears only inside a fence THEN it is not read [REQ: score-marker-parsing, scenario: marker-inside-a-fenced-example]

### threshold-decides-drafts
- [ ] AC-14: WHEN the total is high but a gating dimension is low THEN the item does not qualify [REQ: threshold-decides-drafts, scenario: high-total-low-gating-dimension]

### daily-digest
- [ ] AC-15: WHEN a qualifying item has no draft THEN the digest warns naming it [REQ: daily-digest, scenario: missing-draft]

### reply-drafts-are-gated-text-a-human-sends
- [ ] AC-16: WHEN the gate rejects a block THEN gate exits non-zero naming the block [REQ: reply-drafts-are-gated-text-a-human-sends, scenario: gate-failure]
- [ ] AC-17: WHEN no gate is declared THEN gate says so and does not report a pass [REQ: reply-drafts-are-gated-text-a-human-sends, scenario: no-gate-declared]

### per-account-opt-in-outside-the-repository
- [ ] AC-18: WHEN another account loads the plugin THEN no pane or notification appears [REQ: per-account-opt-in-outside-the-repository, scenario: another-account]
- [ ] AC-19: WHEN optin on runs THEN the entry is under ~/.config/set-core and the tree is unchanged [REQ: per-account-opt-in-outside-the-repository, scenario: opt-in-command]

### scheduled-pane-with-four-actions
- [ ] AC-20: WHEN the user snoozes THEN no pane appears for 60 minutes [REQ: scheduled-pane-with-four-actions, scenario: snooze]
- [ ] AC-21: WHEN the user picks off THEN the opt-in is disabled until re-enabled [REQ: scheduled-pane-with-four-actions, scenario: off]

### one-session-asks
- [ ] AC-22: WHEN two sessions reach the same slot THEN only the lease holder shows the pane [REQ: one-session-asks, scenario: two-sessions-at-the-slot-time]

### import-of-an-existing-opt-in
- [ ] AC-23: WHEN an opt-in is imported THEN the account and times match and the source is byte-identical [REQ: import-of-an-existing-opt-in, scenario: import]
