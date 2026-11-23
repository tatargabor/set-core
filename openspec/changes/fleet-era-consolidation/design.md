## Context

A usage audit (30-day window, every transcript on the operator's machine, the settings of every
registered project, the service journals, an import probe of the dashboard) split set-core into
three groups:

- **Used daily:** the dashboard's fleet view and the agent owner, the relay hooks, the wave
  board, knowledge search, the leak scan, `set-project init/register`, the machine doctor, the
  provider tools, and the consumer-side OpenSpec skills.
- **Not used in 30 days:** the orchestration engine (~29k lines of core, loaded only lazily
  through the sentinel API), its web pages, the sentinel/supervisor/manager, the git-based
  messaging path, 21 deployed `/set:*` slash commands with zero invocations, three
  skill-tracking hooks that spawn on every turn in ~48 projects with no measured reader, a
  3.2k-line API module imported by nothing, and the knowledge-pack bridge.
- **Undecided:** which dashboard routes are opened (there is no access log), whether anything
  reads the skill-tracking hooks' output, and how much of the profile layer `init` still needs.

Two more facts shape the design. The registry already has a reversible `archived` flag
(`registry_prune.py`), but nothing downstream honours it: the doctor checks archived entries,
and an agent opened in one has no way to know. And the public repository is the operator's
working tool as much as an open-source framework, so private concerns — a client-facing
board, company processes — keep landing in it because there is nowhere else to put them.

## Goals / Non-Goals

**Goals:**
- Remove what is provably dead and has no consumer-visible effect (stage 1).
- Stop deploying consumer files nobody calls, and remove the copies already deployed (stage 2).
- Make "archived" mean something to both the doctor and an agent.
- Give every project a one-screen statement of its role and relations, without publishing a
  map of private projects.
- Bring WARNING volume down to what an operator should act on.
- Record the public/private boundary and the order of the later retirement stages.

**Non-Goals:**
- Removing the orchestration engine, its CLI, its web UI or the profile layer in this change.
  Those are stages 3–6 and each is its own change (see the roadmap below).
- Creating the private operator package itself. This change only decides where it goes and
  what seam it uses.
- Any production deployment of any project.

## Decisions

### D1 — One umbrella change for the decisions, stages 3–6 as separate changes
This change carries the parts that are either safe now (stages 1–2, the archived notice, the
role rule, the log sweep) or pure decisions (the split, the roadmap). Stages 3–6 each delete a
large surface whose readers are not all measured yet; bundling them would make one change that
cannot be verified or reverted in parts. *Alternative rejected:* one change for everything —
its verify step would be a 60k-line diff.

### D2 — Retired artifacts are a manifest list, not ledger tombstones
The deploy ledger's tombstones already mean "the project deleted this on purpose — never
recreate it". Retirement is the opposite actor: the framework withdraws a file. Reusing
tombstones would blur the two and make an un-retirement look like a project decision. So the
deploy gets a separate `retired` list; a retired path is removed only when its hash still
matches the ledger's record (the framework's own unchanged copy), and a locally edited copy is
kept and reported. This follows the ownership rule `once: true` already established.

### D3 — The role rule is generated, machine-local and git-excluded
The full project map names private projects and clients, so it cannot be committed to any
repository and cannot ship with set-core. The source is a role file in the user's set-core
config directory, and the output is `.claude/rules/project-role.md` in each project, added to
`.git/info/exclude`. Claude Code loads rules at session start, so an agent sees its project's
role, relations and archived status without any hook. *Alternatives rejected:* a section in
each CLAUDE.md (committed, so it leaks in public repos and drifts); a SessionStart hook (one
more process per session — exactly what the hook diet is removing).

### D4 — Visibility is decided the leak scan's way
The rule for "may this repository name that sibling" is the same question the leak scan
already answers (remote visibility, cached, undecidable = private). Reusing that decision
keeps one definition of "public" on the machine.

### D5 — Archived is a skip for the doctor, a notice for the agent, never a block
The owner archives projects that are not to be developed, but an archived repository can still
need a read or a one-off fix. So the doctor skips archived entries (one summary line, still
checkable by name), and the agent is told, not stopped.

### D6 — The public/private split: the public core keeps the generic tooling
**Public (set-core):** the fleet dashboard and agent owner, the relay hooks, knowledge search,
the leak scan, the machine doctor, `set-project`, the provider tools, the wave board's
generic engine, OpenSpec integration, and the plugin seams.
**Private (an operator Layer-3 package, registered through the existing entry points):**
anything that encodes the operator's company — client-facing board configurations and
publishing targets, company process rules, the role file's content, client-specific doctor
modules. The public core must run without it, silently (requirement in `opensource`).
*Alternative rejected:* making set-core private — it loses the open-source users and the
leak-scan discipline that keeps the code generic; the split fixes the cause (no place for
private work) instead of the symptom.

### D7 — Log levels: act-on-it only, once per state change
A poll that finds the same absence every cycle logs it once when the state changes. The
worktree-list fix already shipped for the dashboard (a missing directory answers empty at
debug) is the pattern; the sweep applies it per service, with before/after counts.

## Roadmap — the later stages, each its own change

| stage | change (proposed name) | precondition |
|---|---|---|
| 3 | `hook-diet` — unwire the skill-tracking hooks, remove the git-bus MCP tools and control bins | a reader check for the hooks' output; the fleet view still shows activity |
| 4 | `retire-orchestration-cli` — the orchestration bins and their slash commands' specs | `set-project init` calls none of them |
| 5 | `retire-orchestration-engine` — engine, planner, dispatcher, verifier, merger, sentinel, their API routes and web pages | a week of route-hit counts; a regression-baseline set diff |
| 6 | `profile-layer-decision` — what of the modules and profile deploy `init` still needs | stage 5 done |

## Risks / Trade-offs

- **A consumer still calls a retired slash command** → none measured in 30 days; the dry-run
  lists every removal, and a locally edited copy is never removed.
- **The role rule goes stale** → the doctor warns when it is older than the role file;
  regeneration is one command and idempotent.
- **A public repo's rule leaks a private name through a wrong visibility answer** → an
  undecidable visibility counts as private, and the file is git-excluded anyway, so even a
  wrong answer stays on the machine.
- **Removing the knowledge-pack bridge breaks a lazy import in the dormant planner** → the
  call sites are removed in the same task, and an import probe of every orchestration module
  runs before and after.
- **Services keep running removed code** → set-web restarts after stage 1; the agent owner
  restarts only when no agent it holds is working.
