## Why

A commit is the unit that accumulates, but the only gate that binds commits (`set-leakscan`) runs at **push** and looks for consumer names, credentials, home paths and phone numbers — not the machine's own identity. So a file carrying the local user's name, git email, username or hostname commits silently, and by push time it is buried in history where the only repair is a rewrite. Measured on 2026-09-07: a `--tree` scan of this repository already surfaces the name in prose and docs (mostly deliberate public identity — `github.com/tatargabor/...` URLs), and 24 tracked files match the local username as a word. New occurrences must stop at commit time, while the already-committed ones remain a separate, deliberate decision.

The complementary half: when a committed file genuinely *needs* a machine- or project-specific value, there is no sanctioned local home for it — each subsystem hand-rolls its own (`~/.config/set-core/projects.json`, `discord.json`, `leakscan-allow.txt`). A general local-config layer gives such values an uncommitted address, so the gate's block message can point at a legitimate alternative instead of only saying no.

## What Changes

- **`set-leakscan` gains an `env-marker` category**, resolved at run time from the machine (git email local-part tokens, git user-name tokens, local username, hostname) — the same never-committed principle as the consumer-name list. Matched ASCII-folded on word boundaries; a check that cannot resolve a source says so instead of reporting zero.
- **The env-marker check is diff-based everywhere**: it measures what a diff *adds* (staged added lines, new files, range added lines), never what a file already holds — the tree legitimately carries deliberate public identity, and a whole-file check would block every commit touching README.
- **`--staged` becomes the real commit gate**: scans staged added lines + new files + staged file names, and **blocks all findings regardless of remote visibility** (a commit is history; publication is only one of the ways it escapes). Skips tree-wide checks so a pre-commit hook stays fast.
- **New `--message <file>` mode** for a `commit-msg` hook — a commit message carrying env-specific content (or a consumer name, or a credential) is refused before the commit exists. This is the class `set-leakscan` caught in already-pushed history (`dda47de797e4`).
- **New `--install-hooks` mode**: idempotent, marker-guarded installer for `pre-commit`, `commit-msg` and `pre-push` — never clobbers a hand-written hook. Today a fresh clone has no hooks at all.
- **`set-hook-leakscan` (the agent-side PreToolUse gate) also fires on `git commit`**, scanning the staged content and any `-m`/`-F` message text, so an agent is bound at commit the way it already is at push.
- **New `local-config` layer** (`lib/set_orch/local_config.py` + `set-config get|set|list` subcommands): one resolution chain (env `SETCORE_<KEY>` → project file → machine `config.json` → default), values under `~/.config/set-core/` — outside every repository, never committed.
- **`release-safety.md` gains the commit-time gate** — the two-gates table becomes three, with the commit gate as the earliest checkpoint.

## Capabilities

### New Capabilities
- `env-leak-gate`: the commit-time refusal of environment-specific content — run-time identity resolution, diff-added-only measurement, blocking semantics at commit regardless of remote visibility, commit-message scanning, both-actor hook wiring (git hooks + PreToolUse), the installer, and the loud report of unresolvable sources.
- `local-config`: the local, uncommitted home for machine- and project-specific values — one resolution chain, project-scoped and machine-scoped files under the config dir, a CLI face, and masked listing.

### Modified Capabilities

<!-- None: set-core ships no `leak-scan` capability spec today (the push gate predates
     the OpenSpec rule and its retroactive documentation is a separate change). This
     change only ADDs capabilities. -->

## Impact

- **Code**: `bin/set-leakscan` (env-marker category, `--staged` semantics, `--message`, `--install-hooks`), `bin/set-hook-leakscan` (commit branch), `bin/set-config` + `bin/set-common.sh` (new subcommands over the existing config dir), new `lib/set_orch/local_config.py`.
- **Hooks**: `.git/hooks/pre-commit`, `commit-msg`, `pre-push` in this repository (installer-written; not deployed to consumers — the consumer write paths are sealed, and consumer remotes are private with their own policy).
- **Tests**: `tests/unit/test_leakscan.py` extensions + new tests for the commit gate, message mode, installer, and local-config.
- **Docs**: `.claude/rules/release-safety.md` (three-gates table, env-marker category, the handle-vs-prose rule).
- **No consumer deployment changes.** Consumer projects are NOT given the commit hooks by `set-project init`; their remotes are private and leakscan's existing visibility policy governs them.
