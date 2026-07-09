# Release Safety — Pre-Push Sensitive Content Scan

**Before every release** — before `git push`, before `git tag`, before pushing a tag —
scan what is about to leave the repository. set-core is public. A leaked customer name
or credential is not revocable once pushed.

Run the scan on the **release range** (`<last-tag>..HEAD`), not just the last commit.
Nothing is pushed until every check is clean or explicitly cleared.

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

## When something is found

- **Not yet pushed** → rewrite history now (`git filter-branch` / `git rebase`), while it
  is still free. Verify with `git branch -r --contains <old-sha>` that no remote has the
  old commits before concluding a force-push is unnecessary.
- **Already pushed** → the credential is compromised. Rotate it. Scrubbing history is
  cleanup, not remediation.

## Order of operations

Scan → push `main` → tag → **scan the tag message** → push the tag. The tag message is
written by hand and is the step most likely to reintroduce a name the diff scan cleared.
