# Release Safety — Pre-Push Sensitive Content Scan

**Before every release** — before `git push`, before `git tag`, before pushing a tag —
scan what is about to leave the repository. set-core is public. A leaked customer name
or credential is not revocable once pushed.

Run the scan on the **release range** (`<last-tag>..HEAD`), not just the last commit.
Nothing is pushed until every check is clean or explicitly cleared.

## Run it, do not re-derive it — `set-leakscan`

**This file used to be a recipe whose commands carried `<name1>|<name2>` placeholders
that somebody had to fill in from memory. Measured 2026-08-19: `grep -rl 'release-safety'`
over the whole repository returned ZERO references, and every public `set-*` repo was
contaminated. A check whose input list has to be reconstructed by hand is a check that
never runs.** The checks below are now implemented:

```bash
set-leakscan                 # the unpushed range — what a push would publish
set-leakscan --staged        # the COMMIT gate — staged added lines, blocks always
set-leakscan --message <file>  # a commit message (the commit-msg hook calls this)
set-leakscan --install-hooks # write/update pre-commit, commit-msg, pre-push
set-leakscan --tree          # the whole tracked tree, for an audit
set-leakscan --list-patterns # what it looks for, without printing the values
```

It resolves the consumer-name list **at run time** from `~/.config/set-core/projects.json`,
because a pattern file committed to the repository would itself be the leak — the same trap
this project's rules already describe for `.gitignore`. Deliberate exceptions go in
`~/.config/set-core/leakscan-allow.txt`, one slug per line; the user's own public repos are
already listed there.

Three gates run it, and they bind **different actors** — none is redundant:

| gate | binds | file |
|---|---|---|
| `.git/hooks/pre-commit` + `commit-msg` | a human, at COMMIT time | `set-leakscan --install-hooks` (marker-guarded, idempotent) |
| `.git/hooks/pre-push` | a human, at push time | `set-leakscan --install-hooks`, or by hand |
| `set-hook-leakscan` (`PreToolUse`, matcher `Bash`) | an agent, on `git commit` and `git push` | `.claude/settings.json` |

An agent can pass `-c core.hooksPath=` without meaning any harm, because **an instruction is
not a constraint — what an agent cannot do is decided by the tools it holds.** A human can
disable a Claude hook. Hence both.

## The commit gate — environment-specific identity dies at commit (2026-09-07)

A commit is the unit that accumulates; by push time the only repair is a history rewrite.
So the gate also runs at commit, on BOTH actors, in two modes:

- **`--staged`** — the `pre-commit` scan: staged **added lines**, new files in full, staged
  file names. Blocks EVERYTHING regardless of remote visibility (a commit is history whoever
  can see the remote). Skips the tree-wide checks to stay fast.
- **`--message <file>`** — the `commit-msg` scan: the message text against the same checks.
  The class `dda47de797e4` proves it needed: a consumer name sat in a pushed commit message
  because nothing scanned messages before the commit existed.

**The env-marker category** — the machine's own identity, resolved at run time and never
stored in any repository: name tokens from `git config user.email`'s local part and
`user.name`, the login name, the hostname. Matched ASCII-folded on word boundaries, so a
name written with its diacritics fires. Two properties are RULES, not accidents:

- **The public account handle inside `github.com/<handle>/...` URLs does not fire** — it is
  one unbroken word, and the tree legitimately carries it in clone instructions. Prose uses
  of the name fire. A `literal:` allow entry closes this for anyone who wants it closed.
- **The check measures what a diff ADDS, never what a file already holds** — the tree
  deliberately carries identity in docs, and a whole-file check would block every commit
  touching README and be removed within a week. It also never runs in `--tree` mode.

If the gate blocks a commit over a value that is legitimately machine-local, the fix is to
move the value to **local config** — `set-config set <key> <value> [--project P]`, stored
under `~/.config/set-core/` outside every repository — and have the code read it with
`set_orch.local_config.get()`. That is the layer's whole purpose: the gate says no, the
config says where the value belongs instead.

**If a gate blocks you, do not reach for `--no-verify`.** Fix the finding, move the value
to local config, or record the exception in the allow file and say so out loud. A bypassed
gate and an absent one are the same thing, except the bypassed one also tells you it is fine.

## The checks

1. **Consumer / customer project names** — in the diff, in commit messages, in tag
   messages. See [external project confidentiality](../../CLAUDE.md). Generalize to
   neutral names (`consumer-app`, `the consumer project`) — never the real name.

   ```bash
   git diff <tag>..HEAD | grep -inE "^\+.*(<name1>|<name2>)"
   git log <tag>..HEAD --format="%H %s%n%b" | grep -inE "<name1>|<name2>"
   git tag -l <newtag> -n50 | grep -inE "<name1>|<name2>"
   ```

2. **Credential and key material** — in added lines:

   ```bash
   git diff <tag>..HEAD | grep -E "^\+" | grep -inE \
     "(sk-[a-zA-Z0-9_-]{16,}|ghp_[a-zA-Z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16}|xox[baprs]-|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY)"
   ```

3. **Assigned credential literals** — `api_key = "..."`, `password: "..."`. Filter out
   `os.environ` / `getenv` / `process.env` reads, type annotations, regexes, and
   placeholders; whatever survives is a real finding.

4. **Absolute local paths** — `/home/<user>/...` in added lines leaks usernames and
   local layout.

5. **Untracked files that are not gitignored** — anything a future `git add -A` would
   sweep in. Local tool caches are the usual offenders:
   `.wrangler/` (Cloudflare account id), `.env*`, `*.pem`, `*.key`, credential caches.
   Fix by gitignoring the path, not by remembering not to add it.

6. **Whole tracked tree**, not just the diff — a secret committed several releases ago
   is still a secret being republished.

7. **Commit MESSAGES across the whole range, and every ref — not just `main`.** Measured
   2026-07-24: the diff scan and the tree scan both came back clean while two commit
   messages still carried a consumer's name. A message is not in any diff and not in any
   tree, so checks 1–6 are structurally blind to it:

   ```bash
   git log <tag>..HEAD --format='%H%n%s%n%b' | grep -inE "<name1>|<name2>"
   git log --all         --format='%s%n%b'   | grep -inE "<name1>|<name2>"
   ```

8. **The scrub's own leftovers.** After a history rewrite, `refs/original/*`, any backup
   tag or branch, and the reflog still hold exactly what was removed. `git push --tags`,
   `--mirror`, or `--all` republishes them, so a repository can be clean on `main` and
   leak anyway. Either delete them before pushing, or push explicit refspecs only —
   never both a scrub and a blanket push.

   ```bash
   git for-each-ref refs/original --format='%(refname) %(objectname)'
   git tag -l 'backup-*'
   ```

## When something is found

- **Not yet pushed** → rewrite history now (`git filter-branch` / `git rebase`), while it
  is still free. Verify with `git branch -r --contains <old-sha>` that no remote has the
  old commits before concluding a force-push is unnecessary.
- **Already pushed** → the credential is compromised. Rotate it. Scrubbing history is
  cleanup, not remediation.

### Doing the rewrite so the result is checkable

- **Substitute mechanically, judge nothing inside the filter.** One uniform `sed` over the
  paths that carried the name means the outcome is reproducible and a single `grep`
  afterwards proves it. A filter that phrases each site nicely cannot be verified in one
  command, which is the whole point of the pass.
- **`--tag-name-filter cat` rewrites your backup tag too.** It is a tag like any other, so
  the safety net silently becomes a copy of the scrubbed history. Re-point it at
  `refs/original/refs/heads/<branch>` afterwards, and check it — measured here, not
  anticipated.
- **Prove the content did not move.** `git diff <backup-tag> <branch> --stat` must be empty
  when the working tree was already fixed by hand before the rewrite. An empty diff is the
  evidence that the pass touched only what it was aimed at.

## Order of operations

Scan → push `main` → tag → **scan the tag message** → push the tag. The tag message is
written by hand and is the step most likely to reintroduce a name the diff scan cleared.
