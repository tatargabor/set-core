## Context

The fleet already sees every registered project, but only through its agents. Whether a project's
work is committed and pushed is answered nowhere in the framework: on 2026-11-24 it took a
hand-written loop over the registry, a second loop over CI files to find which pushes would
deploy, and a third over hosting link files. The loop is the prototype; this change gives it a home
and a screen.

Constraints that shape it:

- The owner asked for it to load **when opened, not continuously** — the fleet listing already
  costs a cycle per project (B-139), and this must not add another.
- The UI bar: an overlay floats and pushes nothing; compacting never hides a failure; a gap is not
  a zero.
- The confidentiality boundary: read consumer trees at runtime, persist nothing derived.
- The standing production-deploy constraint: the screen must make a deploy-on-push visible before
  anybody pushes, and must not itself push.

## Goals / Non-Goals

**Goals:**
- One request answers "which recently active projects are not committed, not pushed, diverged, or
  carry branches/worktrees nobody pushed", in seconds, for the whole registry.
- The second machine's question — "what do I need to pull, what is missing on the remote" — is the
  same table read from the remote's side: ahead = missing on the remote, behind = missing here.
- The deploy hint is shown where the push decision is made.

**Non-Goals:**
- Any write action (push, pull, prune, delete) — a later round, once the deploy hint has been
  measured against real pushes.
- A server-side cache or a refresh cycle.
- Talking to a hosting provider's API.

## Decisions

**D1 — Computed per request, no cache.** `GET /api/fleet/repo-sync` runs the collection
synchronously in a thread pool and answers. The browser keeps the last answer in memory for the
chip. *Alternative:* a background refresher with a cached answer — rejected: it is exactly the
continuous cost the owner ruled out, and a cache file would persist derived consumer data.

**D2 — Activity is commits, by anybody, on any branch.** A project is active if any local or
remote-tracking branch has a commit with a committer date newer than the cutoff
(`git for-each-ref --sort=-committerdate --count=1 refs/heads refs/remotes`). The owner's own rule
(2026-11-24): "commit decides — if anybody committed there, me or someone else"; a fetch or a
session is not activity. (The first draft also counted session transcripts; replaced during apply.)

**D2b — Hiding is a machine-local list, not a registry change.** `fleet_repo_sync_hidden` in
`~/.config/set-core/config.json` holds registered project names the owner does not want in this
table. Archiving a project is a different, wider act (it leaves the whole fleet); hiding only
leaves this table, and the hidden view puts it back.

**D3 — Git plumbing only, with timeouts, bounded parallelism.** Per project: `status --porcelain`,
`rev-parse --abbrev-ref @{u}`, `rev-list --left-right --count @{u}...HEAD`, `for-each-ref` +
`log <b> --not --remotes` per branch, `stash list`, `worktree list --porcelain`,
`merge-base --is-ancestor`, and `FETCH_HEAD`'s mtime for the fetch age. Each command has a 10 s
timeout; projects run on 8 workers. A failed command yields `null` + reason (spec: a gap is not a
zero). `GIT_TERMINAL_PROMPT=0` and `GIT_OPTIONAL_LOCKS=0` so a scan never prompts and never takes
the index lock another agent may need.

**D4 — Fetch is a separate POST.** `git fetch --all --prune` per project, 4 workers, 30 s timeout,
`GIT_TERMINAL_PROMPT=0`, ssh `BatchMode=yes`. Answer per project: `ok | timeout | failed`. It is
the only network act, and it never runs inside the GET.

**D5 — The deploy hint is a reading of the tree's own files, three-valued.** Generic, not a web
module concern: CI files and hosting link files exist for any stack.
- GitLab (`.gitlab-ci.yml`, parsed with `yaml.safe_load`): a job is a deploy job if its `stage` is
  `deploy` or its `environment` (name) contains `prod`. It runs on the current branch if a `rules`
  entry's `if` compares `$CI_COMMIT_BRANCH` to that branch literal (or to `$CI_DEFAULT_BRANCH` and
  the branch is the default) and that entry's `when` is not `manual`/`never`, or an `only` list
  names the branch. A job-level `when` beside `rules`, with no rule-level `when`, is `unknown`:
  how the two combine is not settled by the file, and reading it as "manual" would be the
  deploying misread (changed during apply, 2026-11-24 — the first draft said "counts as manual").
- GitHub (`.github/workflows/*.yml`): a workflow triggered by `push` on the branch (or on all
  branches) with a job whose `environment` contains `prod` or whose name contains `deploy`.
- Hosting link files (`.vercel/`, `vercel.json`, `netlify.toml`, `wrangler.toml`, `fly.toml`,
  `railway.json`/`.toml`): `unknown` unless a CI rule already said `yes` — the production branch
  lives in the provider's settings, not in the tree.
- Anything unparseable is `unknown`, naming the file. `no` only when no CI or hosting file exists or
  every deploy job found is manual/never for this branch.
*Alternative:* ask each project's profile — rejected for this round: no profile declares it today,
and the measurement that motivated the change found the deploy risk in exactly these files.

**D6 — The chip carries the last measurement, never a guess.** Before the first opening: "not
measured". After: count + age, and the age keeps ticking so a stale calm reads as stale.

**D7 — Logging.** INFO per scan: project count, problem count, excluded counts, duration. DEBUG per
project: name and timing. Never a branch name, a path inside the tree, a commit message or a URL.

## Risks / Trade-offs

- [A large registry makes the GET slow] → bounded workers + per-command timeouts; the answer carries
  `duration_ms`, and a timed-out project is a visible gap, not a silent omission.
- [The deploy heuristic misreads a CI file] → it is three-valued and names its file; `unknown` is
  the default whenever the reading is not certain, so the misread direction is "ask", not "safe".
- [Ahead/behind is stale without a fetch] → the row shows the fetch age next to the counts.
- [Session-transcript slug derivation drifts from the runtime's] → the transcript source is the
  secondary one; a project still shows up by its commits.

## Migration Plan

Additive: new module, two routes, one chip. Rollback is removing the chip and the routes. `web/dist`
is rebuilt and committed so a second machine gets the screen with a pull.

## Open Questions

- Whether a later round adds a guarded push button (refusing on `push_may_deploy != no`). Deferred
  until the hint has been checked against the registry by hand once.
