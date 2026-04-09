# v0.1.0-alpha — Early Alpha Release

**Status:** Early alpha. Functional for experimentation, not for production workloads.

> The point of this release is to get set-core into other people's hands. It works end-to-end today — spec in, merged features out — but it has rough edges. The sentinel auto-recovers from most of them, which is how it stays usable as an alpha. If you're willing to watch it run, expect small bugs to go away *during* your first session as the system investigates and fixes itself.

## What works today

- Full orchestration loop: spec → digest → plan → parallel agents in git worktrees → quality gates → merge
- OpenSpec integration: every change has a proposal, design, spec, and task list before any code is written
- Web project type (`--project-type web --template nextjs`): Next.js 14 + Prisma + NextAuth v5 + Playwright + shadcn/ui, with framework-specific rules and gate patterns
- Web dashboard at `localhost:7400`: real-time gate progress, activity timeline, per-change breakdown, logs, issue tracking
- Sentinel supervisor: autonomous bug investigation (`/opsx:ff`-driven fix proposals), automatic change re-dispatch, orphan recovery
- Multi-change parallel execution (configurable via `max_parallel`)
- Integration gates: build → test → e2e → review → rules → spec-verify, each with its own retry budget
- Design pipeline: `design-brief.md` + `design-system.md` scope-matched to per-change `design.md` so agents implement against concrete visual tokens
- Review gate with round-robin retry context: the agent gets the reviewer's findings back on its next iteration
- Session resume across dispatcher retries (warm Claude cache, keeps token cost down)
- Consumer project diagnostics via `set-harvest`

## Known issues

These are tracked and being worked on. We're shipping anyway because the sentinel copes with most of them in practice.

### 1. `dispatched` state can stick without a worktree path

**Symptom:** A change goes into status `dispatched`, then never transitions. No `worktree_path`, no `ralph_pid`.
**Root cause:** Not yet identified. Race between worktree creation and state write in the dispatcher.
**Mitigation:** The sentinel detects the stuck state after ~10 minutes, spawns an investigation agent (ISS-00X), and re-dispatches the change on a fresh worktree (`-2` suffix). Observed working in `craftbrew-run-20260409-0034`.
**Impact:** One extra dispatch cycle, maybe 5–10 minutes of wall clock, small token overhead for the investigation agent.
**Fix target:** framework, next release.

### 2. ~15% change failure rate on a 12-change plan

**Symptom:** In the reference craftbrew run (12 changes), 2 ended up `failed` after exhausting verify retries (`cart-and-session`, `reviews-and-wishlist`).
**Root cause:** Mix of: rules that didn't cover a pattern (fixed in today's harvest), failures during integration merge when two changes touched overlapping files, and a retry budget that gave up too early.
**Mitigation:** Today's rule harvest (`rules/seed-conventions.md`, tightened `testing-conventions.md`, `nextjs-patterns.md`, `auth-conventions.md`, `i18n-conventions.md`, `transaction-safety.md`) covers the patterns that drove most of those failures. The failure rate is expected to drop in future runs.
**Impact:** In a run of N changes, expect 1–2 to need manual retry with updated context, or to be merged as "known degraded."
**Fix target:** framework (verify-retry budget tuning) + web template (rule coverage, ongoing).

### 3. `python.log` gap on monitor restart

**Symptom:** After a set-web restart, `set/orchestration/python.log` stops being written to for the new monitor process. Activity still goes to journald (`journalctl --user -u set-web`), so nothing is lost.
**Root cause:** Logging setup doesn't re-open the file handle on monitor fork after service restart.
**Mitigation:** Use `journalctl --user -u set-web -f` as the primary log source during development.
**Fix target:** framework, next release.

### 4. Opus used for agent planning by default

**Symptom:** First iteration of any change uses Claude Opus for planning, which is expensive on larger specs.
**Root cause:** `default_model: opus` in `set/orchestration/config.yaml` of the reference scaffolds. This is intentional for test runs — real projects can override to `sonnet`.
**Mitigation:** Set `default_model: sonnet` (or leave the default on a new project — `set-project init` ships a sensible mix). Model routing (`model_routing: on`) auto-escalates only when a gate fails.
**Fix target:** user configuration, not a bug.

### 5. `minishop` scaffold uses the legacy Figma pattern

**Symptom:** `tests/e2e/scaffolds/minishop/` references `docs/figma-raw/.../design-snapshot.md` instead of the newer `design.make` + `design-brief.md` + `design-system.md` pattern used by `craftbrew`.
**Root cause:** The scaffold was written before the design-sync pipeline refactor.
**Mitigation:** It still runs — `set-figma-fetch` is the legacy tool behind it and still works. For new projects, follow the `craftbrew` scaffold as the reference. For examples of the modern design pipeline, see `tests/e2e/scaffolds/craftbrew/docs/`.
**Fix target:** scaffold rewrite, not a blocker.

### 6. Protected template files need manual sync on re-deploy

**Symptom:** `playwright.config.ts`, `next.config.js`, `package.json`, `src/app/globals.css`, `.env.example` are marked protected in the web template manifest. `set-project init` skips them on re-deploy, even when the template ships a fix.
**Root cause:** Protected status is correct for user-edited files, but mid-run harvest fixes to the template can't propagate automatically.
**Mitigation:** When a template fix lands, either flip the file's protected status temporarily, or copy the file by hand into the running project before restarting the sentinel.
**Fix target:** framework — smarter protected-file merge (3-way), next release.

## Not yet implemented

Features that are designed but not built. Do not expect them in v0.1.0-alpha.

- **Design compliance gate** — OpenSpec change `design-compliance-gate` (0/38 tasks). LLM vision review of Playwright screenshots against design tokens, with a dedicated retry budget. Spec + design + tasks all written; implementation is the next big chunk of work.
- **Reference docs for CLI, configuration, architecture, plugins** — stubs exist under `docs/reference/`, content still being written as part of `docs-rewrite-release` (25/55 tasks remaining).
- **Examples directory content** — `docs/examples/minishop-walkthrough.md` and `docs/examples/first-project.md` are TODO.
- **Postgres / MySQL database isolation** — current E2E suite assumes SQLite-per-worktree. Postgres needs per-worker database naming in `e2e_db_setup` / `e2e_db_teardown` hooks.
- **Windows support** — set-core runs on Linux and macOS (including Apple Silicon). Windows via WSL2 is untested but likely works.

## How to try it

See the main `README.md` for install. Shortest path from a clean machine:

```bash
# 1. Install set-core (see README for prerequisites)
pip install -e ".[all]"

# 2. Start the web dashboard
systemctl --user start set-web    # or: set-web serve

# 3. Initialize a new project
cd ~/my-project
set-project init --name my-project --project-type web --template nextjs

# 4. Write a spec at docs/spec.md

# 5. Start orchestration via the web UI at http://localhost:7400
#    (pick your project, click Start, paste spec path)
```

## Reporting bugs

- **GitHub Issues:** [setcode-dev/set-core/issues](https://git.setcode.dev/root/set-core/issues) (primary)
- **What to include:** `set/orchestration/python.log` (or `journalctl --user -u set-web` since the restart), `orchestration-state.json`, the spec you tried, and what happened vs. what you expected.
- **Known-issue triage:** Check this document first — if your symptom matches one of the items above, comment on the linked tracking issue instead of opening a new one.

## Upgrade path

This is the first tagged release. There is no upgrade path yet. If you tried set-core from a pre-tag `main` checkout, the safest move is to re-clone and re-run `set-project init` on your project.

## Release checklist (work-in-progress)

Things still open between "main is ready" and "announce on external channels". Picking these up in the next session.

### Observed during the reference run, not yet in the Known issues list

- **Review gate false-positive on truncated diffs.** On a large change (`checkout-and-payment`) the round-2 LLM reviewer returned `NOT_FIXED — payment-step.tsx content truncated from diff`, despite all other findings being resolved. The truncation was on the reviewer's input, not the code. Gate treated this as a hard fail and consumed a verify retry slot. Fix: map "cannot verify" to a neutral/WARN verdict, not CRITICAL.
- **`chain.log` 0-byte buffering.** `.set/logs/ralph-iter-XXX-chain.log` stays empty for minutes at a time because `claude -p --verbose` stdout is buffered by `tee` and only flushes on process exit or large chunks. Observable on long Opus iterations. Real progress is in git commits and `loop-state.json` — the chain log is misleading. Fix: run `claude` under `stdbuf -oL` or use `script(1)` instead of `tee` to force line buffering.
- **`placehold.co` SVG regression in inherited E2E tests.** During integration smoke runs (inherited specs from already-merged changes), Next.js rejects placehold.co images with *"type image/svg+xml but dangerouslyAllowSVG is disabled"*. The smoke gate is non-blocking so it doesn't stop the merge, but the warning is noise and points at a real issue: the web template should either set `images.dangerouslyAllowSVG: true` in `next.config.js` OR agents should avoid `placehold.co` for `<Image>` sources (prefer `.png` endpoints or `unoptimized`). Harvest target for the next template update.

### Release tasks (do not cut the tag yet)

- [ ] Wait until the current reference run (`craftbrew-run-20260409-0034`) either finishes or stabilizes at a good merged share, then snapshot final numbers
- [ ] Re-verify `setcode.dev` landing is live and points at the public repo
- [ ] Take a fresh dashboard screenshot for the LinkedIn post (activity timeline + gate bar)
- [ ] Final proofread of `docs/announcements/v0.1.0-alpha.md` drafts
- [ ] `git tag v0.1.0-alpha` + `git push --tags` (both remotes: github + gitlab)
- [ ] Create GitHub release with release notes excerpt from this file
- [ ] Post the LinkedIn draft
- [ ] Post the Anthropic Discord / community variant
- [ ] Post the OpenSpec community variant
- [ ] Pin the repo on the author's GitHub profile

## License

MIT. See `LICENSE`.
