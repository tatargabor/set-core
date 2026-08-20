## 1. Recognising the command, cheaply and without false fire

- [ ] 1.1 Create `bin/set-hook-checkout-guard` reading the PreToolUse JSON payload on stdin, exit 0 = allow / exit 2 = refuse, following `bin/set-hook-leakscan`'s contract [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]
- [ ] 1.2 One anchored, compiled regex for the guarded verbs (`git commit`, `git add`, `git stash`), matched at command start or after a separator; exit 0 immediately on any other command without touching the index [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]
- [ ] 1.3 Lift leakscan's `strip_heredocs` so a command that merely WRITES about `git commit` — a test fixture, a doc — is not matched; this hook's own tests are the first thing that would trip it [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]
- [ ] 1.4 Lift leakscan's `cd` resolution so the repository examined is the one the command actually runs in, not the session's cwd [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]
- [ ] 1.5 Return allow when the target is not a git repository, and when `git` is unavailable [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]

## 2. Measuring who staged what

- [ ] 2.1 Read `session_id` from the payload the way `bin/set-hook-memory:50` already does; state in a comment what happens when it is absent [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.2 Register the hook on `PostToolUse` / `Bash` as well as `PreToolUse`, and branch on the event name inside one script [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.3 On `PreToolUse` of a staging command, write the current `git diff --cached --name-only` into a single pending pre-snapshot slot in `/tmp/set-checkout-guard-<session_id>.json`, keyed by repository root [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.4 On `PostToolUse` of that command, snapshot again; ADD the arrivals to the session's owned set and SUBTRACT the departures, so an unstaged path stops being claimed [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.5 Nothing anywhere reads the command's arguments to decide ownership — assert this with a test that stages via a shell glob and via a variable, and expects both attributed [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.6 Comment at the delta computation that the attribution is not exact: a neighbour staging inside this command's window is credited here, and that miss is permissive [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.7 A staged path that entered the index outside any observed command is FOREIGN — assert this direction in a test, because the opposite default reproduces the defect exactly [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]
- [ ] 2.8 Refuse a single command that both stages and then commits with no pathspec; the message names the composing rewrite (`git add x && git commit -- x`), not a generic one [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command]

## 3. The refusals

- [ ] 3.1 Refuse `git commit` with no pathspec when `git diff --cached --name-only` holds a foreign path; list the foreign paths and name `git commit -- <paths>` as the remedy [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 3.2 Allow `git commit` when every staged path is the session's own — no message at all [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 3.3 Allow `git commit` that carries an explicit pathspec, even with foreign paths staged; the measured behaviour is that such a commit leaves them in the index [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 3.4 Treat `git commit --amend` with no pathspec as the same act, on the same ground [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 3.5 Refuse `git add -A`, `git add --all`, `git add .`, and `git add -u` with no pathspec; allow `git add <explicit paths>` [REQ: a-staging-command-may-not-sweep-what-it-was-not-given]
- [ ] 3.6 Refuse `git commit -a` — it stages every tracked modification in the checkout, including another session's [REQ: a-staging-command-may-not-sweep-what-it-was-not-given]
- [ ] 3.7 Refuse pathspec-less `git stash` when the checkout holds staged or modified paths the session did not produce [REQ: removing-another-sessions-work-from-the-working-tree-is-refused]
- [ ] 3.8 The stash refusal states the specific consequence: the other session's files leave the WORKING TREE, its `git status` reads clean, and the work sits in a stash entry it has no reason to look in [REQ: removing-another-sessions-work-from-the-working-tree-is-refused]
- [ ] 3.9 Mention in the commit-refusal message that `git commit -- <paths>` commits working-tree content, so a deliberately staged partial hunk would go whole (design risk list) [REQ: a-commit-may-not-carry-another-sessions-staged-work]

## 4. The guard changes nothing, and fails in the stated direction

- [ ] 4.1 No code path in the hook writes to the index, the working tree, or the stash — assert it in a test that compares all three before and after a refusal [REQ: the-guard-refuses-and-changes-nothing-itself]
- [ ] 4.2 Never unstage a foreign path "helpfully": that takes back what another session is holding right now [REQ: the-guard-refuses-and-changes-nothing-itself]
- [ ] 4.3 On an internal exception, allow the command and say so on stderr — a crashing guard that blocks every Bash call is worse than the defect. Mark this as the one deliberate fail-open [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]
- [ ] 4.4 A session working in its own git worktree is not refused; its index holds only its own paths (measured: each worktree has `.git/worktrees/<name>/index`) [REQ: the-guard-is-silent-where-the-hazard-does-not-exist]

## 5. Wiring and the rule that was missing its second half

- [ ] 5.1 Register the hook in `.claude/settings.json` under the existing `PreToolUse` / `Bash` matcher, beside `set-hook-leakscan` [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 5.2 Amend `.claude/rules/cross-cutting-checklist.md`: the pathspec belongs on the COMMIT in addition to the `add`, not instead of it — and say that `git add <path>` alone was measured insufficient on 2026-08-20 [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 5.3 Record in the rule the measured limitation that `git commit -- <path>` fails for a path git does not yet track, so `git add` is still required first [REQ: a-commit-may-not-carry-another-sessions-staged-work]

## 6. Proving the guard is a guard

- [ ] 6.1 For every refusal test, stash the hook change and rerun: a test that passes without the guard proves nothing. Record which tests were checked this way [REQ: a-commit-may-not-carry-another-sessions-staged-work]
- [ ] 6.2 Include at least one test that proves the guard REFUSES, not only tests that prove it allows — a silently broken guard is indistinguishable from a quiet one (design risk list) [REQ: the-guard-refuses-and-changes-nothing-itself]
- [ ] 6.3 Mutation round over the hook with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared between runs; assert each mutation pattern occurs exactly once before replacing, and verify the RESTORE by re-grepping the file [REQ: the-guard-refuses-and-changes-nothing-itself]
- [ ] 6.4 Test the two-session case end to end in a throwaway repo: session B stages its own path, session A commits with no pathspec, guard refuses; then A commits with `-- <its paths>` and B's staged entry is still there [REQ: a-commit-may-not-carry-another-sessions-staged-work]

## 7. Closing the register entry

- [ ] 7.1 Close **B-32** in `openspec/bugs/README.md` with the commit sha, keeping the entry — the register closes with evidence and never deletes [REQ: a-commit-may-not-carry-another-sessions-staged-work]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a session runs `git commit` with no pathspec and the index holds a path it did not stage THEN the command is refused, the foreign paths are listed, and `git commit -- <paths>` is named [REQ: a-commit-may-not-carry-another-sessions-staged-work, scenario: a-pathspec-less-commit-over-a-foreign-staged-path-is-refused]
- [ ] AC-2: WHEN a session runs `git commit` with no pathspec and every staged path is its own THEN the command is allowed and the guard says nothing [REQ: a-commit-may-not-carry-another-sessions-staged-work, scenario: a-sessions-own-work-commits-without-interference]
- [ ] AC-3: WHEN a session runs `git commit` with an explicit pathspec while a foreign path is staged THEN the command is allowed and the foreign entry stays in the index [REQ: a-commit-may-not-carry-another-sessions-staged-work, scenario: a-commit-that-names-its-paths-is-allowed-regardless]
- [ ] AC-4: WHEN a session runs `git commit --amend` with no pathspec while a foreign path is staged THEN it is refused on the same ground [REQ: a-commit-may-not-carry-another-sessions-staged-work, scenario: amending-is-the-same-act]
- [ ] AC-5: WHEN a session runs `git add -A` THEN the command is refused and staging explicit paths is named instead [REQ: a-staging-command-may-not-sweep-what-it-was-not-given, scenario: a-sweeping-add-is-refused]
- [ ] AC-6: WHEN a session runs `git add` with explicit paths THEN the command is allowed [REQ: a-staging-command-may-not-sweep-what-it-was-not-given, scenario: an-explicit-add-is-allowed]
- [ ] AC-7: WHEN a session runs `git commit -a` THEN it is refused, because it stages every tracked modification in the checkout [REQ: a-staging-command-may-not-sweep-what-it-was-not-given, scenario: staging-everything-tracked-is-the-same-sweep]
- [ ] AC-8: WHEN a session runs `git stash` with no pathspec and the checkout holds paths it did not stage or modify THEN the command is refused and the working-tree removal is stated [REQ: removing-another-sessions-work-from-the-working-tree-is-refused, scenario: a-stash-that-would-take-another-sessions-files-is-refused]
- [ ] AC-9: WHEN a stash is refused on this ground THEN the message states that the other session's `git status` would read clean and its work would sit in a stash entry it has no reason to look in [REQ: removing-another-sessions-work-from-the-working-tree-is-refused, scenario: the-refusal-explains-why-this-one-is-worse-than-a-commit]
- [ ] AC-10: WHEN a session stages a path by an explicit path, a glob, a variable, a pipeline or a script THEN that path is recognised as its own, because attribution comes from the index changing [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command, scenario: a-path-is-attributed-however-the-command-happened-to-name-it]
- [ ] AC-11: WHEN the index holds a path that entered it outside any observed command of the running session THEN it is treated as foreign and not assumed to be the session's own [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command, scenario: a-path-that-appeared-outside-this-sessions-commands-is-foreign]
- [ ] AC-12: WHEN a session that has staged nothing runs a pathspec-less `git commit` and the index is not empty THEN the command is refused [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command, scenario: a-session-that-staged-nothing-does-not-own-a-populated-index]
- [ ] AC-13: WHEN a session stages a path and later unstages it THEN the guard no longer counts it as the session's own [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command, scenario: a-path-the-session-unstaged-stops-being-its-own]
- [ ] AC-14: WHEN one command both stages a path and then runs `git commit` with no pathspec THEN it is refused and the composing rewrite is named [REQ: ownership-is-measured-from-the-index-not-parsed-from-the-command, scenario: staging-and-committing-in-one-command-is-refused-with-the-composing-remedy]
- [ ] AC-15: WHEN the guard refuses a command THEN the index, the working tree and the stash list are exactly as they were, and foreign staged entries are untouched [REQ: the-guard-refuses-and-changes-nothing-itself, scenario: a-refusal-leaves-everything-where-it-was]
- [ ] AC-16: WHEN the guard finds a foreign staged path THEN it does not unstage it [REQ: the-guard-refuses-and-changes-nothing-itself, scenario: the-guard-does-not-unstage-on-the-sessions-behalf]
- [ ] AC-17: WHEN an agent in its own git worktree stages its work and commits with no pathspec THEN the command is allowed [REQ: the-guard-is-silent-where-the-hazard-does-not-exist, scenario: a-dedicated-worktree-is-not-policed]
- [ ] AC-18: WHEN the command runs somewhere that is not a git repository THEN the guard allows it rather than erroring [REQ: the-guard-is-silent-where-the-hazard-does-not-exist, scenario: a-command-outside-a-repository-passes-through]
- [ ] AC-19: WHEN a session runs a command that is not a guarded git verb THEN the guard allows it without examining the index [REQ: the-guard-is-silent-where-the-hazard-does-not-exist, scenario: a-non-git-command-is-not-inspected]
