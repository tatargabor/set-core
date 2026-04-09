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
- **`spec-verify` gate uses LLM verdict text, not severity threshold.** When the spec-verify reviewer emits "VERIFY_RESULT: FAIL" with only WARNING-level findings (no CRITICAL), the gate used to treat it as a hard fail. Observed on `reviews-and-wishlist`: 54/54 tasks complete, 5/5 REQs covered by 27 test cases, review gate passed — spec-verify still failed because the LLM decided two WARNINGs were "must fix before archive". **Fixed in this session** (`lib/set_orch/verifier.py`): gate now requests an explicit `CRITICAL_COUNT: N` sentinel from the LLM alongside `VERIFY_RESULT`, and downgrades FAIL→PASS only when `CRITICAL_COUNT: 0`. Missing sentinel keeps the conservative fail behavior (backward-compat safe). Deliberately avoided body-regex heuristics — past CRITICAL detection via pattern matching has misdiagnosed real findings, so we rely on the model self-reporting instead. Takes effect on next engine restart.
- **Hard-failed changes lose their `retry_context`.** On `reviews-and-wishlist` hard fail we wanted to post-mortem "what did the reviewer say last?" but `retry_context` on the change record was empty. The verifier writes retry context on each retry and clears it when the change reaches a terminal state — hard fail should preserve the last context instead of clearing. Harvest target: verifier should copy last review/spec-verify output into `extras.last_gate_output` on transition to `failed`, never clear it.
- **Rule updates don't reach already-running worktrees.** Rules we harvested this morning (seed-conventions, i18n locale, split auth config, slug source) only applied to changes dispatched AFTER the redeploy. `reviews-and-wishlist` had already been dispatched before the harvest commit and hard-failed on exactly the patterns the new rules would have covered (Hungarian test slugs vs English seed slugs, NextAuth Edge runtime crash). The 4 changes dispatched after the redeploy (shopping-cart, subscription-system, checkout-and-payment, order-and-returns) did NOT hit those same failures — the rules are working, they just arrived late. Harvest target: optional "rule catch-up" command that merges updated `.claude/rules/**` into a running worktree without touching code, similar to `set-project init` but scoped to active branches.
- **Heavy reliance on raw hex colors instead of design tokens.** Main branch after 8 merged changes contains **515 hardcoded hex color occurrences** across 17 unique values — and ALL 17 are from the documented brand palette in `design-system.md`. The design IS consistent, but agents write `bg-[#78350F]` inline instead of using the Tailwind `bg-primary` token defined in `globals.css @theme`. Functional equivalence, stylistic regression (breaks dark mode / future palette refresh). Harvest target: new rule in `ui-conventions.md` mandating tailwind token class names when a `@theme` token with that value exists, plus a verifier hook that flags inline `bg-[#HEX]` / `text-[#HEX]` / `border-[#HEX]` against the active design token set.
- **shadcn/ui under-used.** 8 merged changes + 29 pages, but only 7 `variant=` usages across all components. Agents are writing plain `<button>` / `<div>` with Tailwind classes instead of using `<Button variant="outline">`, `<Badge variant="secondary">`, `<Alert variant="destructive">`, etc. This degrades visual consistency and means the design system never fully "cashes in" — changing shadcn theme tokens wouldn't move most of the app. Harvest target: stronger shadcn-first rule with enforced examples per page type.
- **Zero vitest unit tests written.** Vitest found "No test files found" on main after 8 merged changes. Agents wrote Playwright E2E tests for every change (good) but zero unit tests for business logic in `src/lib/**` (bad). The `test` gate passed every time because it runs with `--passWithNoTests`. Harvest target: make `test` gate fail-block if `src/lib/**/*.ts` exists but `src/lib/**/*.test.ts` does not, OR add a planner-level rule "every change that adds business logic in src/lib must ship a unit test for it".
- **Issue state machine missing `failed → resolved` transition.** `journalctl` shows a loop of `ERROR: Cannot transition ISS-007 from failed to resolved. Valid: ['new', 'investigating', 'dismissed']` every 30 seconds across multiple projects. The issue manager tries to auto-resolve issues whose affected change was merged, but the state machine doesn't allow that direct transition. Harmless (log noise only, no functional impact) but embarrassing. Harvest target: allow `failed → resolved` when the underlying cause was fixed, OR require going through `investigating` first.
- **`python.log` rotated/unlinked on monitor restart.** Diagnosed late afternoon: the engine process still holds the fd open (`/proc/<pid>/fd/3 -> python.log (deleted)`), but the file itself was unlinked from disk — probably by a manual `rm` or an error log rotation. Journalctl still receives the output so nothing is lost, but tail -f on `set/orchestration/python.log` shows a file frozen at 02:28 while the engine is actively working. Fix: SIGHUP handler that reopens the log file, OR python `logging.handlers.WatchedFileHandler` that auto-reopens on inode change. **Fixed in this session** (`lib/set_orch/logging_config.py`): new `WatchedRotatingFileHandler` combines `RotatingFileHandler` size rotation with `WatchedFileHandler` inode-watch auto-reopen. Takes effect on next set-web restart.
- **`set-web` systemd restart kills the engine + set-loop cgroup.** Assumption that processes with `parent=systemd` (PID 1) are "detached" from `set-web` is **wrong for user systemd services**. `systemctl --user restart set-web` terminates the entire control group for the service, which includes any process ever spawned by set-web — even after reparenting to PID 1. Observed on 2026-04-09 18:15: restarted set-web to pick up the activity-timeline live-extend fix; engine monitor (PID 3146279) and set-loop (PID 3805318) were killed even though their parent showed as systemd. The running `reviews-and-moderation` dispatch was interrupted mid-planning and had to be reset+re-dispatched by hand. This is a **serious mid-run dev-cycle problem**: any Python code change that requires set-web reload also kills every running agent loop. Fix options: (1) run engine monitor as a separate systemd user service with its own cgroup so `restart set-web` leaves it alone; (2) use `setsid` / double-fork when spawning set-loop so it breaks out of the service cgroup; (3) add an API-driven in-process code reload path (uvicorn --reload or SIGHUP handler) that doesn't touch the service unit. Until this is fixed, DO NOT restart set-web mid-run — commit code changes and wait for a natural restart window.
- **Implementing spans on the timeline look "empty" for running changes.** Merged changes render 20+ colored bars per change on the timeline (implementing × N + llm:review × N + llm:spec_verify × N + gate:* × N + merge). A currently-running change only has 1–3 `implementing` bars because no gate has fired yet. Visually this reads as "nothing is tracked" even when the agent is actively making dozens of tool calls. **Fixed in this session** (`lib/set_orch/api/activity.py`): (a) `_build_spans()` now live-extends open implementing spans to `end_ts` (~now) when the change is in an ACTIVE_STATUSES set from the state file, instead of anchoring to the last-observed event. (b) `get_activity_timeline()` post-processes each `implementing` span by pulling the drilldown sub-spans from `activity-detail-v2-<change>.jsonl`, clipping to the span's time window, and injecting `detail.llm_calls` / `detail.tool_calls` / `detail.subagent_count` so the frontend can render an inline badge. Takes effect on next set-web restart (see cgroup item above for why that's currently painful).
- **Drilldown message "No session data available" is misleading when the clicked span pre-dates the current session.** Observed on reviews-and-moderation: user clicked the first (stuck PTY, 24m 50s) span and saw *"No session data available. The agent may not have written any session JSONL files yet, or the worktree was cleaned up after the run."* — but the change DID have session data, just in a later span. The drilldown filters the cached sub-spans by the clicked window; if the window is older than any session JSONL, it correctly returns empty — but the message is wrong (there IS session data, just not in this window). Harvest target: differentiate "no session files for this change at all" from "session files exist but none in the requested window" in the drilldown message, and consider defaulting the dashboard's drilldown to the most recent implementing span instead of the first.

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
