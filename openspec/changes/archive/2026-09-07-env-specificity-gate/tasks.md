## 1. set-leakscan — the env-marker category and the commit gate

- [x] 1.1 Add the run-time identity resolver: tokens from git email local part and user name (≥4 chars, stoplisted), username, hostname (full + first label), ASCII-folded; word-boundary matching on folded text [REQ: the-environments-identity-is-resolved-at-run-time-never-from-the-repository]
- [x] 1.2 Emit a loud warning for identity sources that cannot be resolved, and run the remaining checks anyway [REQ: a-source-that-cannot-be-resolved-is-reported-never-silently-zero]
- [x] 1.3 Add the diff-added scanner: staged added lines + new-file content + staged file names for `--staged`; range added lines for range mode; env-marker skipped in `--tree` [REQ: the-env-marker-check-measures-what-a-diff-adds-never-what-a-file-already-holds]
- [x] 1.4 Repurpose `--staged`: block on all findings without consulting visibility; skip tree-wide checks (ignored-but-tracked, visibility probe); report names the token class and points at local-config and the allow file [REQ: a-staged-commit-carrying-environment-specific-content-is-refused-regardless-of-remote-visibility]
- [x] 1.5 Add `--message <file>` mode scanning a commit message against the full check list, blocking unconditionally [REQ: a-commit-message-carrying-environment-specific-content-is-refused-before-the-commit-exists]
- [x] 1.6 Keep env-marker findings in range mode subject to the existing visibility policy; unit tests for the whole category including the diacritics, handle, and stoplist shapes [REQ: outside-commit-mode-env-marker-findings-follow-the-publication-policy]
- [x] 1.7 Verify the `literal:` allow-file exception suppresses line-locally for env-markers [REQ: deliberate-exceptions-are-recorded-in-the-allow-file-not-remembered]

## 2. set-hook-leakscan — bind the agent at commit

- [x] 2.1 Extend the publish regex with the `commit` verb (heredoc-stripped, separator-anchored as `push` is) [REQ: both-actors-are-bound-at-commit-time]
- [x] 2.2 On a commit command: run `set-leakscan --staged` in the target repo, extract `-m`/`--message` values and `-F <file>` content into a temp file scanned via `--message`; unit tests including the `cd /home/... &&` false-finding shape [REQ: both-actors-are-bound-at-commit-time]

## 3. The installer and the git hooks

- [x] 3.1 Implement `--install-hooks`: marker-guarded, idempotent writer for `pre-commit`, `commit-msg`, `pre-push`; refuses hooks it did not write [REQ: both-actors-are-bound-at-commit-time]
- [x] 3.2 Write the hook script bodies (mirror the pre-push shape: refuse blind when set-leakscan is off PATH) [REQ: both-actors-are-bound-at-commit-time]
- [x] 3.3 Run the installer in this repository and verify: clean commit passes, staged name refuses, hand-written hook preserved [REQ: both-actors-are-bound-at-commit-time]

## 4. local-config — the uncommitted home

- [x] 4.1 Implement `lib/set_orch/local_config.py` (`get`/`set`): env `SETCORE_<KEY>` → project file → machine `config.json` → default; unset returns default without raising; JSON merge on write; 0600/0700 permissions [REQ: one-resolution-chain-and-an-unset-value-reads-as-unset]
- [x] 4.2 Storage under `get_config_dir()`, project scope via the runtime project-name resolver; never writes inside a repository [REQ: values-live-outside-every-repository]
- [x] 4.3 Extend `set-config` with `get|set|list` and `--project`; `list` shows keys and sources with values masked [REQ: the-cli-reads-and-writes-the-same-chain]
- [x] 4.4 Unit tests: override order, unset default, project scoping isolation, merge-not-replace, masked listing, round trip [REQ: one-resolution-chain-and-an-unset-value-reads-as-unset]

## 5. Documentation

- [x] 5.1 Update `.claude/rules/release-safety.md`: the commit gate row in the gates table, the env-marker category, the handle-vs-prose rule, `--staged`/`--message`/`--install-hooks` usage [REQ: both-actors-are-bound-at-commit-time]

## 6. Verification

- [x] 6.1 `openspec validate env-specificity-gate --strict` passes [REQ: both-actors-are-bound-at-commit-time]
- [x] 6.2 Full unit test set-diff against a baseline per the regression-baseline skill — no new failures outside this change's tests [REQ: a-staged-commit-carrying-environment-specific-content-is-refused-regardless-of-remote-visibility]
- [x] 6.3 Live check in this repository: stage a file with a name → commit refused; clean commit passes; commit with leaking `-m` refused by the PreToolUse gate [REQ: a-commit-message-carrying-environment-specific-content-is-refused-before-the-commit-exists]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an added line contains the user's name in its accented form THEN the folded match reports an env-marker finding [REQ: the-environments-identity-is-resolved-at-run-time-never-from-the-repository, scenario: a-name-written-with-diacritics-is-still-found]
- [x] AC-2: WHEN an added line contains the account handle as one unbroken word inside a github.com URL THEN no env-marker finding is produced, as documented behaviour [REQ: the-environments-identity-is-resolved-at-run-time-never-from-the-repository, scenario: the-public-account-handle-inside-a-url-is-not-the-prose-name]
- [x] AC-3: WHEN an added line contains a stoplisted word that is also an identity token THEN no finding is produced for that token [REQ: the-environments-identity-is-resolved-at-run-time-never-from-the-repository, scenario: a-generic-token-from-the-stoplist-does-not-fire]
- [x] AC-4: WHEN git identity is unset in the scanned repository THEN the scan warns the name-token check is skipped AND runs the checks whose sources resolved [REQ: a-source-that-cannot-be-resolved-is-reported-never-silently-zero, scenario: git-identity-is-unset]
- [x] AC-5: WHEN a staged modification touches a file whose unchanged lines contain the user's name THEN the commit is not refused because of those unchanged lines [REQ: the-env-marker-check-measures-what-a-diff-adds-never-what-a-file-already-holds, scenario: pre-existing-contamination-next-to-an-unrelated-edit]
- [x] AC-6: WHEN a staged change adds a line containing the name, email, username or hostname THEN the staged scan reports an env-marker finding naming the token class [REQ: the-env-marker-check-measures-what-a-diff-adds-never-what-a-file-already-holds, scenario: a-new-line-carrying-the-name]
- [x] AC-7: WHEN a new staged file contains the hostname and every remote is private THEN the commit is still refused, with the local-config escape described [REQ: a-staged-commit-carrying-environment-specific-content-is-refused-regardless-of-remote-visibility, scenario: a-hostname-in-a-new-file-on-a-private-remote]
- [x] AC-8: WHEN a commit message contains the user's name THEN the commit-msg hook exits non-zero and the commit is not created [REQ: a-commit-message-carrying-environment-specific-content-is-refused-before-the-commit-exists, scenario: a-message-naming-the-user]
- [x] AC-9: WHEN a commit message contains a credential-shaped string THEN the commit-msg hook refuses it [REQ: a-commit-message-carrying-environment-specific-content-is-refused-before-the-commit-exists, scenario: a-credential-pasted-into-a-message]
- [x] AC-10: WHEN --install-hooks runs where pre-commit is absent THEN the hooks are created and a re-run reports them in place rather than rewriting [REQ: both-actors-are-bound-at-commit-time, scenario: a-fresh-clone-with-no-hooks]
- [x] AC-11: WHEN --install-hooks runs where pre-commit exists without the installer marker THEN it is left untouched and the installer says so [REQ: both-actors-are-bound-at-commit-time, scenario: a-hand-written-pre-commit-hook]
- [x] AC-12: WHEN a session runs git commit -m whose message carries an env-marker THEN the PreToolUse gate blocks the command before git runs [REQ: both-actors-are-bound-at-commit-time, scenario: an-agent-committing-a-leaking-message]
- [x] AC-13: WHEN a push range adds no env-marker lines while the wider tree has them THEN the push is not refused by the env-marker category [REQ: outside-commit-mode-env-marker-findings-follow-the-publication-policy, scenario: old-contamination-does-not-block-a-clean-push]
- [x] AC-14: WHEN the allow file carries a literal: entry matching a would-fire line THEN that line does not block and a line without the literal still blocks [REQ: deliberate-exceptions-are-recorded-in-the-allow-file-not-remembered, scenario: a-deliberately-published-identity-string]
- [x] AC-15: WHEN SETCORE_TOOLS_DIR is set and the key also exists in the project file THEN get returns the environment value [REQ: one-resolution-chain-and-an-unset-value-reads-as-unset, scenario: the-environment-overrides-the-files]
- [x] AC-16: WHEN the key exists nowhere and a default is supplied THEN get returns the default without raising [REQ: one-resolution-chain-and-an-unset-value-reads-as-unset, scenario: a-key-set-nowhere]
- [x] AC-17: WHEN set(endpoint, ..., project=p) runs THEN the value lands in the config dir's projects/p.json merged beside existing keys and no repository file changes [REQ: values-live-outside-every-repository, scenario: a-project-scoped-write]
- [x] AC-18: WHEN the key was set for project p and get runs for project q THEN q does not receive p's value [REQ: values-live-outside-every-repository, scenario: another-project-does-not-see-the-value]
- [x] AC-19: WHEN set-config list runs on a config holding keys THEN values are masked and each key's source file is shown [REQ: the-cli-reads-and-writes-the-same-chain, scenario: listing-never-prints-a-value]
- [x] AC-20: WHEN set-config set db_host localhost --project p then get db_host --project p runs THEN get prints localhost [REQ: the-cli-reads-and-writes-the-same-chain, scenario: a-round-trip]
