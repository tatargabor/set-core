## 1. Close the reinstall path first

- [x] 1.1 Delete the nine memory hook entries from the desired-hooks object in `bin/set-deploy-hooks` so no deploy emits them [REQ: reusable-hook-deployment-script]
- [x] 1.2 Make the `$strip_memory` branch in `_merge_hooks_additively` unconditional, so every deploy removes any `set-hook-memory` entry it finds in any event array [REQ: remove-only-set-hook-memory-stale-entries]
- [x] 1.3 Widen the stale detection to every `set-hook-memory` command in PreToolUse regardless of matcher [REQ: detect-stale-set-hook-memory-entries-in-pretooluse]
- [x] 1.4 Widen the stale detection in PostToolUse: `Read` and `Bash` stop being canonical matchers [REQ: detect-stale-set-hook-memory-entries-in-posttooluse]
- [x] 1.5 Keep `--no-memory` as an accepted no-op flag so existing callers do not break [REQ: reusable-hook-deployment-script]
- [x] 1.6 Prove 1.1–1.5 on a COPY of a project settings.json carrying nine memory hooks and 25 of its own: memory goes to 0, the project's own count and order are unchanged [REQ: reusable-hook-deployment-script]

## 2. Invert the audit before the fleet is checked

- [x] 2.1 Invert the memory-hook check in `set-audit`: presence is ❌ with the count, absence is ✅ [REQ: claude-code-config-dimension]
- [x] 2.2 Remove the guidance that tells a project to run `set-deploy-hooks` in order to INSTALL memory hooks; the guidance now says the same command removes them [REQ: claude-code-config-dimension]
- [x] 2.3 Run `set-audit scan` against a project known to be clean and one seeded with the nine hooks, and check both verdicts by reading the output [REQ: claude-code-config-dimension]

## 3. Remove the MCP surface

- [x] 3.1 Delete the 27 memory tools from `mcp-server/set_mcp_server.py`, leaving the 7 worktree/team tools [REQ: the-mcp-server-exposes-worktree-and-team-tools-only]
- [x] 3.2 Delete every subprocess invocation of `set-memory` and `set-memoryd` from the MCP server [REQ: the-mcp-server-exposes-worktree-and-team-tools-only]
- [x] 3.3 Start the server and enumerate its registered tool names; assert the list equals the 7 and contains none of the 27 [REQ: the-mcp-server-exposes-worktree-and-team-tools-only]

## 4. Remove the CLI, the daemon and the libraries

- [x] 4.1 Delete `bin/set-memory`, `bin/set-memoryd`, `bin/set-memory-hooks` [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 4.2 Delete `bin/set-hook-memory` and the five legacy `set-hook-memory-{warmstart,recall,pretool,posttool,save}` scripts [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 4.3 Delete `lib/set_memoryd/`, `lib/memory/`, `lib/set_hooks/`, `lib/frustration.py` [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 4.4 Remove the memory entries from `install.sh` and the `set-*` symlink/PATH setup [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 4.5 Sweep `lib/ bin/ modules/ mcp-server/ templates/ .claude/` for surviving `set-memory` / `shodh` / `set_memoryd` / `set_hooks` references and remove each; the sweep is over the whole tree, not over the files this change happened to touch [REQ: the-framework-ships-no-memory-subsystem-of-its-own]

## 5. Rewrite the rule book, because a wrong instruction outlives wrong code

- [x] 5.1 Replace CLAUDE.md's **Persistent Memory** section: it currently tells every session, on every prompt, to scan for a `PROJECT MEMORY` block that no component emits [REQ: the-native-memory-directory-is-the-memory-layer]
- [x] 5.2 State the 200-line / 25 KB startup limit wherever the memory index is described, and that content past the cut loads for nobody [REQ: the-index-size-limit-is-stated-because-it-silently-truncates]
- [x] 5.3 Carry the confidentiality rule forward onto whatever writes memory now — no consumer name, no personal name, no harness artifact stored verbatim [REQ: confidentiality-survives-the-removal]
- [x] 5.4 Write down the seven capabilities deliberately not replaced, with the measurement attached (187 injections, 1 reusable line, 21 days) [REQ: the-capabilities-not-replaced-are-stated-not-discovered]
- [x] 5.5 Record that no component may inject a claim about the user's emotional state [REQ: a-memory-records-a-fact-never-a-claim-about-the-users-state]

## 6. Remove the commands, skills and rules that address the subsystem

- [x] 6.1 Delete `.claude/commands/set/memory.md` and `.claude/commands/set/todo.md` [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 6.2 Update `.claude/commands/set/help.md`: drop `set-memory` from the CLI list and replace the memory MCP section with the registered tools [REQ: help-command-covers-cli-tools]
- [x] 6.3 Update `.claude/skills/set/decompose/SKILL.md` and `.claude/rules/capability-guide.md` to stop naming memory commands and MCP tools [REQ: help-command-covers-the-registered-mcp-tools]
- [x] 6.4 Remove the `--mode causal` / `--mode associative` recall call sites from the explore and apply skills; confirm no skill BRANCHES on a recall result rather than merely quoting it [REQ: the-framework-ships-no-memory-subsystem-of-its-own]

## 7. Specs and documentation

- [x] 7.1 Delete the 45 capability spec directories named in the proposal's Removed Capabilities list [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 7.2 Correct the incidental `set-memory` mentions in the ten specs that keep every requirement [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 7.3 Retarget the 70 documentation files; KEEP `docs/research/shodh-memory-audit.md` as the record of a finding that sat unactioned for six months [REQ: the-capabilities-not-replaced-are-stated-not-discovered]
- [x] 7.4 Update `README.md` and `docs/guide/memory.md` to describe the native layer [REQ: the-native-memory-directory-is-the-memory-layer]

## 8. Tests

- [x] 8.1 Delete the 17 test files that exercise the removed code [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 8.2 Add a test asserting `bin/` contains no executable named `set-memory*` or `set-hook-memory*` [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 8.3 Add a test asserting no module under `lib/` and no script under `bin/` imports `shodh_memory`, `set_memoryd` or `set_hooks` [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 8.4 Add a test asserting a `set-deploy-hooks` run produces a settings.json with zero `set-hook-memory` commands [REQ: no-memory-hook-is-deployed]
- [x] 8.5 Prove each new test is a real test: stash the removal and confirm it FAILS, then unstash. A test that passes either way proves nothing and looks like proof forever [REQ: the-framework-ships-no-memory-subsystem-of-its-own]

## 9. Uninstall the package

- [x] 9.1 Sweep `~/code2` and `~/code` for `set-memory` invocations OUTSIDE `.claude/settings.json` — a project's own script may shell out to it — and report what is found before uninstalling [REQ: no-memory-package-is-imported]
- [x] 9.2 `pip uninstall shodh-memory` from the miniconda interpreter (0.1.81) and the linuxbrew interpreter (0.1.90); verify neither resolves it afterwards [REQ: no-memory-package-is-imported]

## 10. Prove the removal

- [x] 10.1 Re-run the machine-wide sweep: zero `set-hook-memory` in any `.claude/settings.json` under `~/code2` and `~/code` [REQ: no-memory-hook-is-deployed]
- [x] 10.2 Run the unit suite against a baseline worktree by SET DIFF, with `PYTHONPATH` pointed at the worktree's own source roots and the session-end leak assertion — this repo is installed editable, so `cd` into a worktree is a proxy for running its code [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 10.3 Prove the leak detector can fire before believing its zero: run it once WITHOUT the import isolation and confirm a non-zero leak count [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 10.4 Invoke `set-hook-leakscan` and `set-hook-checkout-guard` and confirm each still fires — assert the behaviour, not the presence of a line in the config [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 10.5 Close B-49, B-50, B-51, B-52, B-53 and B-54 in `openspec/bugs/README.md` with this change's commit shas; entries stay, they are never deleted [REQ: the-capabilities-not-replaced-are-stated-not-discovered]

## 11. Post-session distillation — the one capability worth rebuilding (user, 2026-08-22)

The removed system's automatic session-end extraction is the ONLY one of the seven lost
capabilities the user has asked for back, and they asked for it in a different shape:
distillation, not capture. The distinction is the whole finding — the old hook captured
whatever prompt was in flight (89.8 % of its output was a raw task notification labelled
as the user's anger); a distillation reads the finished session and writes what was
*learned*. Scoped here, built as its own change.

- [x] 11.1 Write down what distillation must produce, and what disqualifies an entry: a fact learned, never a claim about the user's state, never a harness artifact verbatim [REQ: a-memory-records-a-fact-never-a-claim-about-the-users-state]
- [x] 11.2 Decide where it writes — the native memory directory, one file per fact, plus one index line — and that it may not create a second store [REQ: a-second-store-is-not-introduced]
- [x] 11.3 Decide the trigger and who runs it. A Stop hook was the old carrier and it is what made the capture indiscriminate; state the choice and the reason rather than inheriting it [REQ: the-native-memory-directory-is-the-memory-layer]
- [x] 11.4 Respect the index limit: a distillation that appends unboundedly pushes the index past the 200-line / 25 KB cut, where it loads for nobody and nothing warns [REQ: the-index-size-limit-is-stated-because-it-silently-truncates]
- [x] 11.5 Confidentiality is a gate, not a review step: a consumer name, a partner name or a personal name must be unable to reach a memory file [REQ: confidentiality-survives-the-removal]
- [ ] 11.6 Open it as its own OpenSpec change; this group is the scoping note, not the implementation [REQ: the-capabilities-not-replaced-are-stated-not-discovered]

**Scoping decisions — taken 2026-08-22, each naming the evidence it rests on.**

- **11.1 · What it produces, and what disqualifies an entry.** One durable fact per file, in
  the native frontmatter shape (`type: user | feedback | project | reference`). Disqualified,
  and this is a gate rather than a style note: any claim about the user's *state* (an inferred
  emotion, a sentiment label the source text does not support); any harness artifact stored
  verbatim (a task notification, a cross-session message, another agent's system prompt, a
  transcript fragment); anything the repository already records; anything that only mattered
  inside the session. Measured reason: of 187 memory lines the removed system injected,
  **168 (89.8 %) were `User frustrated` records** and exactly one was a reusable fact.
- **11.2 · Where it writes.** `~/.claude/projects/<slug>/memory/`, one file per fact, plus
  exactly one line in `MEMORY.md`. It may not create a second store — the framework ships no
  memory subsystem, and a new store would re-open what `remove-shodh-memory` closed.
- **11.3 · Trigger: `SessionEnd`, and it only ENQUEUES.** Three reasons, and the first is why
  the old carrier is not inherited: `Stop` fires at the end of **every assistant turn**, so it
  captured whatever prompt was in flight — that indiscriminacy *is* the 89.8 % above. Second,
  `SessionEnd` exists in this Claude Code and fires once, after the transcript is complete
  (measured: the official `plugin-dev` hook reference lists it; this machine's `settings.json`
  currently registers only `Stop`). Third, a model call inside an exit hook is a bad place to
  do the work — it is time-bounded and its output reaches nobody — so the hook writes one queue
  entry (transcript path, project slug, timestamp) and the distiller runs out of band. The
  distiller is judged on the **file it wrote**, never on its own report: a subagent's "done" is
  not evidence that anything happened.
- **11.4 · The index limit is a refusal, not a hope.** Only the first **200 lines / 25 KB** of
  `MEMORY.md` are injected, and nothing warns past the cut. Measured 2026-08-22: this project
  **50 lines / 8 204 bytes**; the largest index on this machine **123 lines / 20 550 bytes** —
  already 82 % of the byte cut. So the distiller writes one index line per fact and **refuses
  to append** once the index would pass 150 lines or 20 KB, reporting instead. An unbounded
  appender silently disables memory for every later session in that project.
- **11.5 · Confidentiality is a pre-write gate.** Reuse `bin/set-leakscan`'s runtime-resolved
  slug list (`private_slugs()`, registry `~/.config/set-core/projects.json`, exceptions in
  `~/.config/set-core/leakscan-allow.txt`) as a library — never a pattern list committed to the
  repository, which would itself be the leak. A candidate memory that matches is **refused**,
  not flagged for a later review, and the matched value is never echoed into the refusal.
- **11.6 · It ships as its own OpenSpec change** — this group is the scoping note.

## 12. The scripts, everywhere — including the machines this one cannot see (user, 2026-08-22)

- [x] 12.1 Audit EVERY script under `bin/` and `lib/` by reading it, not by grepping for the names already known — the sweep that scoped this change missed a whole dashboard page because the frontend called an endpoint rather than a command [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [x] 12.2 Sweep the consumer trees for scripts of THEIR own that invoke the removed commands: `~/code2` and `~/code`, outside `.claude/settings.json`. Report before changing anything — a consumer's own script is theirs, not the framework's [REQ: no-memory-package-is-imported]
- [x] 12.3 `install.sh` must REMOVE a stale memory script it finds on the target machine, not merely stop shipping new ones. A machine that installed before today still has all nine executables on its PATH, and they will keep resolving [REQ: no-memory-command-is-installed]
- [x] 12.4 The removal must survive an install of an OLDER checkout: state what happens when a machine pulls a version that predates this change, and whether the uninstall is idempotent in both directions [REQ: no-memory-command-is-installed]
- [ ] 12.5 Test it on the second machine (amc): install from this checkout, then verify no `set-memory*` or `set-hook-memory*` remains on PATH and no project there carries the nine hooks [REQ: no-memory-hook-is-deployed]

## 13. Hermes — re-examine on a clean slate (user, 2026-08-22)

The user asked for this the moment the removal landed, and the reason is the sequencing:
whatever Hermes was doing was doing it *alongside* a memory subsystem that turned out to be
injecting false claims into every session it touched. Any earlier reading of Hermes was
taken against that background. With the background gone, the reading is worth taking again.

- [ ] 13.1 **Establish what Hermes IS here, before measuring anything.** This session could not: no systemd unit, no running process, and the only match in the tree is a transitive dependency in `web/package-lock.json` (the JS engine of that name), which is almost certainly not the subject. Ask, or find it — do not measure the package-lock match and call it Hermes [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [ ] 13.2 Examine it **after a restart**, per the user's instruction. A long-lived service holds the code it started with, so anything running from before today is still running against the old world — check `systemd ExecMainStartTimestamp` or the equivalent rather than the shipped commit [REQ: the-framework-ships-no-memory-subsystem-of-its-own]
- [ ] 13.3 Check whether it touched the removed subsystem at all: a `set-memory` call, a memory hook, an import, or the store directory. If it did, its behaviour changed today and the change is unannounced [REQ: no-memory-package-is-imported]
- [ ] 13.4 Record the finding where it survives the session — the bug register if it is a defect, the living record if it is a decision. A clean-slate reading that lives only in a conversation is the loss this whole exercise was about [REQ: the-capabilities-not-replaced-are-stated-not-discovered]

## Acceptance Criteria (from spec scenarios)

### the-framework-ships-no-memory-subsystem-of-its-own

- [ ] AC-1: WHEN the framework's `bin/` directory is enumerated after installation THEN it contains no executable whose name begins with `set-memory` or `set-hook-memory` [REQ: the-framework-ships-no-memory-subsystem-of-its-own, scenario: no-memory-command-is-installed]
- [ ] AC-2: WHEN `set-deploy-hooks` writes or updates any project's settings.json THEN the result contains zero hook commands beginning with `set-hook-memory` [REQ: the-framework-ships-no-memory-subsystem-of-its-own, scenario: no-memory-hook-is-deployed]
- [ ] AC-3: WHEN every Python module under `lib/` and every script under `bin/` is scanned for imports THEN none imports `shodh_memory`, `set_memoryd` or `set_hooks` [REQ: the-framework-ships-no-memory-subsystem-of-its-own, scenario: no-memory-package-is-imported]

### the-native-memory-directory-is-the-memory-layer

- [ ] AC-4: WHEN a session reads the project instruction file's memory section THEN it describes the native per-repository Markdown directory and its index, and does not instruct the session to look for an injected block no component emits [REQ: the-native-memory-directory-is-the-memory-layer, scenario: the-rule-book-names-the-real-mechanism]
- [ ] AC-5: WHEN the framework needs to persist knowledge that must survive a session THEN it writes a Markdown file into the native memory directory, or nothing [REQ: the-native-memory-directory-is-the-memory-layer, scenario: a-second-store-is-not-introduced]

### the-index-size-limit-is-stated-because-it-silently-truncates

- [ ] AC-6: WHEN documentation or rules describe maintaining the memory index THEN the 200-line / 25 KB startup limit is stated alongside [REQ: the-index-size-limit-is-stated-because-it-silently-truncates, scenario: the-limit-is-documented-where-the-index-is-described]
- [ ] AC-7: WHEN a memory index exceeds 150 lines or 20 KB THEN the framework treats it as a condition to report, and the report says content past the cut loads for nobody [REQ: the-index-size-limit-is-stated-because-it-silently-truncates, scenario: an-index-approaching-the-limit-is-a-known-condition]

### confidentiality-survives-the-removal

- [ ] AC-8: WHEN a memory file contains a consumer project name, a partner name or a personal name THEN it is treated as a defect to correct [REQ: confidentiality-survives-the-removal, scenario: a-memory-naming-a-consumer-entity-is-a-defect]
- [ ] AC-9: WHEN a task notification, cross-session message, agent prompt or meeting-transcript fragment is available THEN it is not stored verbatim as a memory [REQ: confidentiality-survives-the-removal, scenario: harness-artifacts-are-never-memory]

### a-memory-records-a-fact-never-a-claim-about-the-users-state

- [ ] AC-10: WHEN a prompt contains emphasis such as repeated exclamation marks THEN no memory is written asserting the user is frustrated [REQ: a-memory-records-a-fact-never-a-claim-about-the-users-state, scenario: enthusiasm-is-not-stored-as-frustration]
- [ ] AC-11: WHEN a session begins or a prompt is submitted THEN no component injects a statement about the user's emotional state [REQ: a-memory-records-a-fact-never-a-claim-about-the-users-state, scenario: no-sentiment-label-is-injected-into-a-later-session]

### the-capabilities-not-replaced-are-stated-not-discovered

- [ ] AC-12: WHEN documentation describes the memory layer THEN it states that semantic search, tag filtering, temporal queries, full-text search, cross-device sync, version history and automatic session-end extraction are unavailable, and records that the removed subsystem provided all of them and still produced one reusable line in 187 injections over 21 days [REQ: the-capabilities-not-replaced-are-stated-not-discovered, scenario: the-losses-are-enumerated]
- [ ] AC-13: WHEN a session needs to search memory by concept, tag or date range THEN the documented answer is to read the index and open the topic files, not to reinstall a store [REQ: the-capabilities-not-replaced-are-stated-not-discovered, scenario: a-request-for-a-removed-capability-has-an-answer]

### reusable-hook-deployment-script

- [ ] AC-14: WHEN `set-deploy-hooks <dir>` is called and no settings.json exists THEN it creates one with `set-hook-skill` and `set-hook-stop` and no command beginning with `set-hook-memory` [REQ: reusable-hook-deployment-script, scenario: deploy-to-directory-without-settingsjson]
- [ ] AC-15: WHEN settings.json already exists THEN the framework's hooks merge additively and every hook the project owns is preserved [REQ: reusable-hook-deployment-script, scenario: deploy-to-directory-with-existing-settingsjson]
- [ ] AC-16: WHEN settings.json already contains `set-hook-skill` and `set-hook-stop` and no memory hook THEN the script exits 0 without modification [REQ: reusable-hook-deployment-script, scenario: deploy-to-directory-with-hooks-already-present]
- [ ] AC-17: WHEN a project carrying nine `set-hook-memory` entries is deployed to THEN all nine are removed with no flag passed, and the project's own hooks remain unchanged in count and order [REQ: reusable-hook-deployment-script, scenario: a-deploy-removes-memory-hooks-it-finds]
- [ ] AC-18: WHEN `--no-memory` is passed THEN behaviour is identical to a call without it and the flag is accepted rather than rejected [REQ: reusable-hook-deployment-script, scenario: deploy-with-no-memory-flag]
- [ ] AC-19: WHEN `--quiet` is passed THEN success/info messages are suppressed and only errors print [REQ: reusable-hook-deployment-script, scenario: deploy-with-quiet-flag]

### hook-config-downgrade

- [ ] AC-20: WHEN settings.json has PreToolUse `set-hook-memory` entries for six matchers THEN all six are identified as stale [REQ: detect-stale-set-hook-memory-entries-in-pretooluse, scenario: project-with-6-pretooluse-memory-matchers]
- [ ] AC-21: WHEN PreToolUse contains only the Skill activity-track matcher THEN no stale entries are detected [REQ: detect-stale-set-hook-memory-entries-in-pretooluse, scenario: project-with-only-skill-activity-track-matcher]
- [ ] AC-22: WHEN settings.json has PostToolUse `set-hook-memory` entries for six matchers THEN all six are stale, Read and Bash included [REQ: detect-stale-set-hook-memory-entries-in-posttooluse, scenario: project-with-6-posttooluse-memory-matchers]
- [ ] AC-23: WHEN a custom hook sits alongside stale entries THEN the custom hook is preserved and only `set-hook-memory` entries are removed [REQ: remove-only-set-hook-memory-stale-entries, scenario: non-wt-hooks-preserved-during-downgrade]
- [ ] AC-24: WHEN PreToolUse contains the activity-track.sh entry THEN it is preserved after downgrade [REQ: remove-only-set-hook-memory-stale-entries, scenario: activity-tracksh-preserved-during-downgrade]
- [ ] AC-25: WHEN a project carrying both memory hooks and its own is deployed to THEN the count of hooks not beginning with `set-hook-memory` is identical before and after [REQ: remove-only-set-hook-memory-stale-entries, scenario: a-projects-own-hook-count-is-unchanged-by-the-strip]
- [ ] AC-26: WHEN stale entries are detected and removal proceeds THEN `settings.json.bak` is created before modification [REQ: backup-before-downgrade, scenario: backup-created-on-downgrade]

### the-mcp-server-exposes-worktree-and-team-tools-only

- [ ] AC-27: WHEN the MCP server starts THEN it registers exactly the seven: `list_worktrees`, `get_ralph_status`, `get_worktree_tasks`, `get_team_status`, `get_activity`, `send_message`, `get_inbox` [REQ: the-mcp-server-exposes-worktree-and-team-tools-only, scenario: server-exposes-exactly-the-surviving-tools]
- [ ] AC-28: WHEN the registered tool names are enumerated THEN none is among the 27 memory tools [REQ: the-mcp-server-exposes-worktree-and-team-tools-only, scenario: no-memory-tool-is-registered]
- [ ] AC-29: WHEN the server source is scanned for subprocess invocations THEN no tool invokes `set-memory` or `set-memoryd` [REQ: the-mcp-server-exposes-worktree-and-team-tools-only, scenario: no-tool-shells-out-to-a-removed-command]
- [ ] AC-30: WHEN a worktree or team tool is invoked THEN it uses `projects.json` and does not depend on `CLAUDE_PROJECT_DIR` [REQ: the-mcp-server-exposes-worktree-and-team-tools-only, scenario: worktree-tools-unaffected]

### help-command

- [ ] AC-31: WHEN the help content is loaded THEN the CLI section lists the surviving tools and does not list `set-memory` or `set-memoryd` [REQ: help-command-covers-cli-tools, scenario: cli-tools-listed]
- [ ] AC-32: WHEN a CLI tool is listed THEN it has a one-line description [REQ: help-command-covers-cli-tools, scenario: each-cli-tool-has-description]
- [ ] AC-33: WHEN the help content is loaded THEN it lists at minimum `list_worktrees`, `get_activity`, `get_team_status`, `send_message`, `get_inbox` [REQ: help-command-covers-the-registered-mcp-tools, scenario: worktree-and-team-mcp-tools-listed]
- [ ] AC-34: WHEN the help content is loaded THEN it names none of the memory MCP tools [REQ: help-command-covers-the-registered-mcp-tools, scenario: no-memory-mcp-tool-is-advertised]

### claude-code-config-dimension

- [ ] AC-35: WHEN settings.json has `permissions.allow` entries THEN report ✅ with the count [REQ: claude-code-config-dimension, scenario: check-permissions]
- [ ] AC-36: WHEN there is no `permissions` key or an empty allow array THEN report ❌ with guidance for the detected stack [REQ: claude-code-config-dimension, scenario: missing-permissions]
- [ ] AC-37: WHEN hooks contain `set-hook-memory` THEN report ❌ with the count, guidance to run `set-deploy-hooks` to REMOVE them, and no suggestion to install or restore any memory hook [REQ: claude-code-config-dimension, scenario: check-memory-hooks]
- [ ] AC-38: WHEN hooks contain no `set-hook-memory` entries THEN report ✅ and emit no guidance for this check [REQ: claude-code-config-dimension, scenario: missing-memory-hooks]
- [ ] AC-39: WHEN `.claude/agents/` contains `.md` files THEN report ✅ listing agent names and model settings [REQ: claude-code-config-dimension, scenario: check-agents]
- [ ] AC-40: WHEN `.claude/agents/` is missing or empty THEN report ⚠️ pointing to reference.md [REQ: claude-code-config-dimension, scenario: no-agents-directory]
- [ ] AC-41: WHEN `.claude/rules/` contains `.md` files THEN report ✅ listing rule files and path globs [REQ: claude-code-config-dimension, scenario: check-rules]
- [ ] AC-42: WHEN `.claude/rules/` holds only set-core managed rules or is empty THEN report ⚠️ with guidance to create path-scoped rules [REQ: claude-code-config-dimension, scenario: no-project-specific-rules]
