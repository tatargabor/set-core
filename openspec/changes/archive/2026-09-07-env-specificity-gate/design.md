## Context

`set-leakscan` (bin/set-leakscan) is the existing publication gate: it binds a human through a hand-installed `pre-push` git hook and an agent through `set-hook-leakscan` (PreToolUse, matcher Bash, fired only on `git push`). Its categories — consumer names (runtime-resolved from `~/.config/set-core/projects.json`), credentials, home paths, phone numbers, ignored-but-tracked — never look at the machine's own identity, and the gate never runs at commit time.

Measured on 2026-09-07, in this repository:

- `git config user.name` and the login name are the same two-letter handle, the email is a personal gmail whose local part is the person's name split in two, the hostname is that handle plus a device suffix, and the GECOS field is empty — so **the email local part is the only source of the person's actual name tokens on this machine**.
- A tracked-tree grep for the person's name tokens and hostname hits ~20 files, almost all `github.com/<handle>/...` clone URLs and repo links — **deliberate public identity**.
- `\b<login>\b` matches 24 files — doc examples (`<login>@linux` member placeholders) from the old team-sync docs.
- `set-leakscan --tree` today reports one **blocking** `consumer-name:commit-message` finding (`dda47de797e4`): a leak class that sits in pushed history precisely because nothing scanned messages before the commit existed. (Separate finding: `README.md` carries a `mailto:` with a first-name work address — the user's call, not this change's.)

## Goals / Non-Goals

**Goals:**
- Refuse a commit whose staged content or message introduces environment-specific identity — for the human (git hooks) and the agent (PreToolUse) alike.
- Give machine-/project-specific values a sanctioned, uncommitted home so the block message can offer an alternative, not only a refusal.
- Keep the gate fast enough to sit on every commit, and honest about what it could not check.

**Non-Goals:**
- No history scrubbing of the already-committed name/username occurrences (outward-facing rewrite; the user decides separately).
- No consumer deployment of the commit hooks (`set-project init` write paths are sealed; consumer remotes are private and governed by the existing visibility policy).
- No retroactive capability spec for the pre-existing push-time checks (separate change, per the OpenSpec rule).
- No migration of `discord.json` / `projects.json` / `leakscan-allow.txt` into the new local-config layer — they keep working as-is.

## Decisions

**D1 — Identity tokens: email local part, git name, username, hostname; folded, word-bounded, stoplisted.**
Sources resolved at run time: tokens ≥4 chars from the `git config user.email` local part (split on non-letters), tokens ≥4 chars from `git config user.name`, the login name from `getpass.getuser()`, and `socket.gethostname()` (full + first dot label). Matching runs on NFKD-folded, lowercased text with `\b` word boundaries — so the accented prose form of the name fires while `github.com/tatargabor/...` (one unbroken token) does not. The handle exception is **stated in the spec and the rule doc as the rule**, not left to look like an accident; a user who wants the handle gated too adds a `literal:` entry. A small built-in stoplist (user, admin, test, main, local, home, host, dev, git, root, info, mail, gmail, example, com, org, net) keeps a generic name token from crying daily. Rejected alternative: substring matching — it would flag the deliberate URLs and read the handle as the prose name, making the gate unusable on day one.

**D2 — The env-marker check is diff-added-only, everywhere; it never runs in tree mode.**
Measured baseline decides this: a whole-file check blocks every commit touching README (deliberate URLs) and every doc example edit (`<login>@`). The category therefore reads staged added lines (`git diff --cached -U0`), the full text of newly added files, staged file names, and range added lines (`git diff <range> -U0`) — and is skipped for `--tree`. The existing whole-file categories (consumer names, secrets, home paths, phones) are unchanged: the tree is measurably clean of them.

**D3 — `--staged` is repurposed as the commit gate; no new flag.**
Its documented intent was always "before a commit"; it predates the design refinement. Nothing wires the old behaviour (grep: only `release-safety.md` mentions it, and that file is updated by this change). New semantics: added-lines scan of the staged diff, **all findings block without consulting remote visibility**, tree-wide checks (ignored-but-tracked, which walks every tracked file with one `git check-ignore` subprocess each) skipped, visibility (`gh` subprocesses) skipped — a pre-commit call must cost tens of milliseconds, not seconds. A commit is history regardless of who can see the remote; the allow file is the escape.

**D4 — `--message <file>` + a `commit-msg` hook.**
Two measured precedents: the consumer name sitting in `dda47de797e4`'s message, and `79ad2234`'s note that a peer session's name was caught "before the push" — commit-msg catches that class before the commit exists. The mode scans the message file against the full check list, blocks unconditionally, and walks no trees.

**D5 — `--install-hooks` makes an existing claim true.**
The shipped `pre-push` header already says "Installed by set-leakscan", but no installer exists and a fresh clone has no hooks at all. The installer writes `pre-commit`, `commit-msg`, `pre-push`, guarded by the marker line `# Installed by set-leakscan`: absent file → write; marker present → rewrite (upgradeable); no marker → leave untouched and say so. Hooks installed once in this repository by running the installer; consumers are deliberately excluded.

**D6 — The agent gate fires on `git commit` too.**
`set-hook-leakscan`'s `PUBLISH_RX` gains the `commit` verb (same separator/word-boundary shape as `push`, after `strip_heredocs`, so writing *about* committing still works). On a commit it runs `set-leakscan --staged` in the resolved target repo, and extracts `-m`/`--message` values (and reads `-F <file>`) into a temp file scanned via `--message` — extraction rather than scanning the whole command string, so a `cd /home/<user>/...` prefix cannot become a false finding. Reuses `target_repo()`.

**D7 — local-config: one chain over the existing config dir, surfaced through the existing CLI.**
`lib/set_orch/local_config.py` resolves `get(key, project=None)` as: `SETCORE_<KEY>` env → `<config-dir>/projects/<project>.json` → `<config-dir>/config.json` → default. More specific wins; unset is an ordinary answer (default, no raise, no error log). `set()` merges JSON, never replaces; files 0600, directory 0700. `<config-dir>` is `get_config_dir()`'s `~/.config/set-core` (honouring `SET_CONFIG_DIR`, which is what tests use); `<project>` comes from the same resolver as `set-paths`/`paths.resolve_project_name()`. The CLI is `set-config get|set|list` — the existing tool for the existing config home, not a parallel mechanism. `list` prints keys and source files with values masked, on the leakscan `--list-patterns` precedent: show the shape, not the values.

## Risks / Trade-offs

- [The 2-letter username as a word token fires on new doc examples like `<login>@linux`] → accepted deliberately (the ask was unconditional); the block message names the token class and points at `literal:` in the allow file; measured baseline shows the noise is confined to legacy doc examples, which are frozen history.
- [A future machine whose name token is a common word] → stoplist + allow file; the unresolvable-source warning keeps partial blindness visible.
- [Pre-commit latency] → staged diff only; no tree walk, no `check-ignore` loop, no `gh` visibility subprocesses; the commit-msg hook reads one small file.
- [`--staged` semantics change surprises a human who knew the old behaviour] → `release-safety.md` is updated in the same change; the old semantics were wired to nothing.
- [The handle-vs-prose rule reads as a hole] → documented in spec + rule doc as deliberate; one `literal:` line closes it for anyone who wants it closed.
- [commit-msg hook fires on `git commit --amend` of old leaking messages] → correct behaviour: the amend re-creates the message; the allow file is the escape for a deliberate re-commit.

## Migration Plan

1. Implement `set-leakscan` changes + tests; `set-hook-leakscan` commit branch + tests; `local_config` + CLI + tests.
2. Run `set-leakscan --install-hooks` in this repository; verify a clean commit passes and a staged name refuses.
3. Update `release-safety.md` (three-gates table, env-marker category, handle rule) and the capability guide row if needed.
4. Rollback: hooks are single files in `.git/hooks/` — deleting them restores prior behaviour; no data migration exists to undo.

## Open Questions

- Whether to scrub the already-pushed history that carries the name/username (`dda47de797e4`'s message, doc bylines) — the user's call, explicitly out of scope here.
