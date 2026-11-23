## 1. Stage 1 — dead code, no behaviour change

- [x] 1.1 Record the before-state: `python -c "import set_orch.server"` module count, an import probe of every `lib/set_orch/*.py`, and a regression baseline (regression-baseline skill) [REQ: ikp-config-loading]
- [x] 1.2 Remove `lib/set_orch/_api_old.py` and `tests/unit/test_api_old_deprecated.py`; re-grep importers including tests and conftest first [REQ: none — dead-code removal, design D1]
- [x] 1.3 Remove the bridge's lazy call sites in `lib/set_orch/planner.py` and `lib/set_orch/dispatcher.py`, and any reference in `verifier.py` and `templates.py`, so each path behaves as "no bridge configured" did [REQ: planner-assigns-ikp-packs-per-change]
- [x] 1.4 Remove `lib/set_orch/ikp_bridge.py`, `tests/test_ikp_bridge.py`, `tests/test_ikp_decomposer_dispatch.py`, and the bridge's entry in `tests/unit/test_model_touch_point_coverage.py` [REQ: ikp-config-loading]
- [x] 1.5 Grep lib, bin, modules, templates and web/src for the stopped design-tool integration and remove what remains, keeping any consumer-facing design rule that is still generic [REQ: rule-file-injection]
- [x] 1.6 After-state: the same import probe and module count, and a set diff against the 1.1 baseline that shows no new failure; restart set-web and confirm it serves the fleet view [REQ: graceful-degradation]

## 2. Stage 2 — stop deploying unused consumer artifacts

- [x] 2.1 Re-measure before deleting: `/set:*` slash and Skill invocations across transcripts (30 days), and whether any consumer's own skill or command references a `/set:*` name [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]
- [x] 2.2 Add a `retired` list to the deploy, holding the zero-use `/set:*` commands, `skills/set` entries, and the git-bus messaging commands (keep `set:inbox` only if 2.1 finds a live caller) [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]
- [x] 2.3 In `lib/project/deploy.sh` and the ledger (`lib/set_orch/deploy_ledger.py`): skip retired sources; remove a deployed copy whose hash matches the ledger record; keep and report one that differs [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]
- [x] 2.4 Make `set-project init --dry-run` list each planned retirement, and write nothing [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]
- [x] 2.5 Tests: an unchanged retired copy is removed, an edited one is kept, and the dry-run lists both and writes nothing — each test fails with the change stashed [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]
- [x] 2.6 Remove the retired command and skill sources from set-core's own `.claude/` once no deploy path reads them [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]
- [x] 2.7 Run the dry-run on two real consumers and read the plan; after the real run, diff their hand-authored `.claude/` files, hook config and gate scripts — an empty diff is the pass [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed]

## 3. Archived projects

- [x] 3.1 The doctor skips archived registry entries and prints one summary line with their count; `--project <name>` still checks an archived one (`lib/set_doctor/cli.py`, `checks.py`) [REQ: archived-projects-are-not-checked]
- [x] 3.2 Tests for both doctor scenarios [REQ: archived-projects-are-not-checked]
- [x] 3.3 `set-project archive` and unarchive regenerate the project's role rule, so the notice appears and disappears with the flag [REQ: an-archived-project-tells-the-agent-not-to-develop-it]

## 4. Project role rules

- [x] 4.1 Define the role file schema (role, owns, depends on, depended on by, replaced by) and ship an empty example under `templates/`; the real file lives in the user's set-core config directory [REQ: roles-come-from-a-private-machine-local-file]
- [x] 4.2 Implement `set-project roles`: read the registry and the role file, write `.claude/rules/project-role.md` with a generated-by marker into each existing project, and skip a file without the marker [REQ: one-generated-rule-per-registered-project]
- [x] 4.3 Add the rule's path to `.git/info/exclude` when writing it [REQ: the-rule-never-enters-a-commit]
- [x] 4.4 Reuse the leak scan's visibility decision (and its cache); for a public project, name only public relations and count the private ones; undecidable counts as private [REQ: a-public-repository-names-only-public-siblings]
- [x] 4.5 Open the rule with the archived notice for an archived entry, naming the replacement when the role file gives one [REQ: an-archived-project-tells-the-agent-not-to-develop-it]
- [x] 4.6 `set-project init` regenerates the rule for the project it deploys into [REQ: one-generated-rule-per-registered-project]
- [x] 4.7 The doctor's role check: missing or older than the role file is `warn` with `set-project roles` as the fix; no role file is `skip` with the reason [REQ: the-project-role-rule-is-checked]
- [x] 4.8 Tests for every scenario in the project-role-rule spec, each failing with the change stashed [REQ: one-generated-rule-per-registered-project]
- [ ] 4.9 Operator step, local only: fill the role file from the private project map and run `set-project roles`; open one public and one archived project and read the generated rule [REQ: roles-come-from-a-private-machine-local-file]

## 5. Log hygiene sweep

- [ ] 5.1 Measure WARNING lines per day and the top 10 messages for set-web, set-agent-owner and each set-core hook from the journal; record the table in the change's notes (no consumer names) [REQ: a-sweep-is-measured-before-and-after]
- [ ] 5.2 For each top message: an operator-actionable one stays, an expected outcome moves to debug, a repeating one is logged once per state change [REQ: a-normal-answer-is-not-a-warning]
- [ ] 5.3 A test per demoted message that fails when its level is reverted [REQ: a-sweep-is-measured-before-and-after]
- [ ] 5.4 Restart the services (the agent owner only when no agent it holds is working) and re-measure after 24 hours; record before → after [REQ: a-sweep-is-measured-before-and-after]

## 6. Public/private split and roadmap

- [ ] 6.1 Inventory operator-specific code and config currently in the public repository and list, per item, whether it moves to the private package or becomes a generic seam [REQ: operator-specific-integrations-live-behind-plugin-seams]
- [ ] 6.2 Verify the public core runs without the private package: start set-web and run the public CLIs, and expect no error and no WARNING naming it [REQ: operator-specific-integrations-live-behind-plugin-seams]
- [ ] 6.3 Rewrite the README positioning and `.claude/rules/capability-guide.md` to describe the fleet and tooling layer first, and mark the orchestration commands as being retired [REQ: operator-specific-integrations-live-behind-plugin-seams]
- [ ] 6.4 Create the stage 3–6 follow-up changes as proposals only (`hook-diet`, `retire-orchestration-cli`, `retire-orchestration-engine`, `profile-layer-decision`), each with the precondition named in design.md [REQ: operator-specific-integrations-live-behind-plugin-seams]

## 7. Close

- [ ] 7.1 `openspec validate fleet-era-consolidation --strict`, then `/opsx:verify` with `templates/core/rules/spec-verify-gate.md` [REQ: operator-specific-integrations-live-behind-plugin-seams]
- [ ] 7.2 Run `set-leakscan` on the range before any push [REQ: operator-specific-integrations-live-behind-plugin-seams]

## Notes from applying (measured, 2026-11-23)

- 1.1/1.6 — unit suite, clean worktree at HEAD vs this tree, three import roots, leak check 0 both
  sides: no failure present here that is absent at HEAD (the diff is captured log-line numbers and
  24 baseline-only failures that depend on the checkout path). Import probe: 223 → 221 modules,
  the two removed ones; the only failing import (`manager.api`, aiohttp missing) predates this.
  `import set_orch.server` loads 84 `set_orch` modules before and after. set-web restarted, the
  fleet API answers. Its startup traceback from the chat-bot integration predates the change
  (present at the previous start) — group 5 material.
- 1.5 — no reference to the stopped design-tool integration remained outside the removed bridge.
- 2.1 — 30 days, 12 621 transcripts: 0 `/set:*` slash calls; `set:inbox` 7 Skill calls, all from
  agents reaching for the git-based inbox no project has. Retired anyway — see design.md, Risks.
- 2.5 — the five retire tests catch four mutants (guard off, deploy skip off, ledger forget off,
  dry-run writes), restore verified with `cmp`.
- 2.7 — dry-run on two consumers: 25 planned removals each, `git status` unchanged. Real init on
  one (files gitignored there): removed 25, kept 0; outside the retired paths only `.set-version`,
  the ledger and a first deploy of `set:blueprint` changed. Where the files are tracked, init leaves
  the deletions in the working tree for the project to commit.
- 3.1/3.2 — four tests; with the filter mutated away two of them fail (restore verified with
  `cmp`). On this machine's registry: "24 archived projects skipped", the registry holds 24.
- 4.x — `lib/set_orch/project_roles.py` + `set-project roles`; 13 tests in
  `tests/unit/test_project_roles.py` (one end to end through the real command); four mutants
  (exclude off, marker ignored, visibility ignored, notice off) each turn tests red, restore
  verified with `cmp`. Visibility comes from `set-leakscan`'s own `remote_visibility`; an
  unknown sibling is counted, an unknown self is treated as public. Data repositories
  (`deploy: false`) get no rule. The doctor's new `role` check is listed in the two tests
  that enumerate check names.
- 3.3 — sandbox: archive → the notice appears, unarchive → it is gone, `git status` clean.
  The sandbox needed `HOME` overridden as well as `SET_CONFIG_DIR`: B-200.
- 4.9 stays open: it needs the owner's role content (and, proposed to the family umbrella, the
  umbrella owns the family's entries).

## Acceptance Criteria (from spec scenarios)

### project-role-rule
- [x] AC-1: WHEN the role file does not exist THEN `set-project roles` writes no rule, reports "no role file" with the path and exits 0 [REQ: roles-come-from-a-private-machine-local-file, scenario: no-role-file]
- [x] AC-2: WHEN a registered project has no entry THEN its rule carries registry facts only and says the role is not described [REQ: roles-come-from-a-private-machine-local-file, scenario: a-project-without-an-entry]
- [x] AC-3: WHEN `project-role.md` exists without the marker THEN it is left unchanged and reported as skipped [REQ: one-generated-rule-per-registered-project, scenario: a-hand-written-file-in-the-way]
- [x] AC-4: WHEN `set-project roles` runs twice unchanged THEN the second run changes no byte [REQ: one-generated-rule-per-registered-project, scenario: regeneration-is-idempotent]
- [x] AC-5: WHEN the rule is written into a clean repository THEN `git status --porcelain` stays empty [REQ: the-rule-never-enters-a-commit, scenario: written-into-a-clean-repository]
- [x] AC-6: WHEN a public project has one public and one private dependent THEN the rule names the public one and counts the private one [REQ: a-public-repository-names-only-public-siblings, scenario: a-public-repository-with-a-private-consumer]
- [x] AC-7: WHEN a relation's visibility cannot be decided THEN it is counted as private and not named [REQ: a-public-repository-names-only-public-siblings, scenario: visibility-cannot-be-decided]
- [x] AC-8: WHEN an agent starts in an archived project THEN the rule's first lines say it is archived and not to be developed [REQ: an-archived-project-tells-the-agent-not-to-develop-it, scenario: opening-an-archived-project]
- [x] AC-9: WHEN the archived flag is cleared and the rule regenerated THEN the notice is gone [REQ: an-archived-project-tells-the-agent-not-to-develop-it, scenario: un-archiving]

### service-log-hygiene
- [ ] AC-10: WHEN a poll finds an optional resource absent every cycle THEN at most one WARNING is logged, at the state change [REQ: a-normal-answer-is-not-a-warning, scenario: a-polled-resource-is-absent]
- [ ] AC-11: WHEN a listing returns nothing because there is nothing THEN no WARNING is logged [REQ: a-normal-answer-is-not-a-warning, scenario: an-expected-empty-answer]
- [ ] AC-12: WHEN a demoted message is reverted to WARNING THEN its test fails [REQ: a-sweep-is-measured-before-and-after, scenario: reverting-a-demotion]

### machine-doctor
- [x] AC-13: WHEN the registry holds three archived entries THEN none is checked and one line says "3 archived projects skipped" [REQ: archived-projects-are-not-checked, scenario: an-archived-entry-in-the-registry]
- [x] AC-14: WHEN `--project` names an archived entry THEN it is checked [REQ: archived-projects-are-not-checked, scenario: asking-for-an-archived-project-by-name]
- [x] AC-15: WHEN the role file changed after a rule was generated THEN the role check warns with `set-project roles` as the fix [REQ: the-project-role-rule-is-checked, scenario: a-stale-role-rule]

### project-init-deploy
- [x] AC-16: WHEN a consumer holds an unchanged retired command THEN init removes it and reports it under "retired" [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed, scenario: a-retired-command-deployed-earlier]
- [x] AC-17: WHEN the consumer's retired copy differs from the ledger hash THEN it stays and is reported as kept [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed, scenario: a-retired-file-the-consumer-edited]
- [x] AC-18: WHEN the dry-run runs in a project holding retired copies THEN it lists each removal and writes nothing [REQ: retired-framework-artifacts-are-not-deployed-and-are-removed, scenario: the-dry-run-shows-the-removal]

### opensource
- [ ] AC-19: WHEN the public core runs without the private package THEN commands and the dashboard run with no error or WARNING naming it [REQ: operator-specific-integrations-live-behind-plugin-seams, scenario: the-operator-plugin-is-not-installed]
- [ ] AC-20: WHEN an operator-only feature is proposed THEN it goes into the private package and the public change adds at most a generic seam [REQ: operator-specific-integrations-live-behind-plugin-seams, scenario: a-new-operator-specific-feature]
