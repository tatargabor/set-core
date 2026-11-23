## Why

set-core is now used as a fleet and tooling layer — the dashboard and agent owner, the agent bus
hooks, knowledge search, the leak scan, the machine doctor, the wave board — while the
orchestration engine it was built around has not run on this machine in 30 days. A usage audit
measured that split, and it found the repository carrying, deploying and logging far more than is
used: dead modules with live import paths, 21 deployed slash commands with zero calls in 30 days,
a dashboard that logged ~98k WARNING lines in a week, and archived projects that every check and
every agent still treats as active. The public repository also no longer says what it is for.
This change consolidates the part that is used, retires the first, safe layers of what is not,
and writes down how the public core and the operator's private tooling separate — before more
work lands on the wrong side.

## What Changes

- **Retire dead code, stage 1 (no behaviour change):** remove the superseded API module, the
  knowledge-pack bridge with its call sites and tests, and the remaining references to a
  stopped design-tool integration.
- **Retire unused consumer artifacts, stage 2:** stop deploying the slash commands and skills
  that measured zero use, and the git-based messaging commands; previously deployed copies are
  removed through the deploy ledger's tombstones. **BREAKING** for a consumer that still calls
  one of them (none measured).
- **An archived project means "do not develop":** the machine doctor skips archived registry
  entries (one summary line), and an agent opening an archived project is told so in the
  project role rule it loads at session start.
- **Project role rules:** a generated, machine-local rule per registered project that states
  its role, what it owns, what it depends on and what depends on it, from a private,
  operator-maintained role file. Public repositories name only public siblings. Never
  committed.
- **Log hygiene sweep:** every long-running set-core service and hook is measured for WARNING
  volume; routine outcomes move to debug, each fix with a test that fails without it.
- **Public core vs. operator plugin — decision and roadmap:** the public repository keeps the
  generic fleet and tooling layer; operator-specific integrations move behind the existing
  plugin seams into a private Layer-3 package. Follow-up changes are named for stages 3–6
  (hook diet, orchestration CLI, orchestration engine and its web UI, the profile layer).

## Capabilities

### New Capabilities
- `project-role-rule`: the generated, machine-local role rule per project, its private source,
  the visibility rule for public repositories, and the archived-project notice it carries.
- `service-log-hygiene`: what may be logged at WARNING by a long-running set-core service, and
  how a sweep proves a fix.

### Modified Capabilities
- `machine-doctor`: archived registry entries are skipped with one summary line; a stale or
  missing project role rule is a warning with its fix.
- `project-init-deploy`: only artifacts in use are deployed; retired ones are tombstoned so a
  redeploy removes the copies it wrote earlier.
- `opensource`: operator-specific integrations live behind plugin seams, not in the public core.
- `ikp-bridge`, `ikp-decompose-context`, `ikp-dispatch-injection`: removed.

## Impact

- Code: `lib/set_orch/_api_old.py`, `lib/set_orch/ikp_bridge.py` and its call sites in the
  planner and dispatcher, their tests; `bin/set-project` (new `roles` subcommand, `archive`
  regenerates the rule); `lib/set_doctor/` (archived skip, role-rule check); the deploy
  manifest and its tombstones; logging call sites found by the sweep.
- Consumers: on their next `set-project init`, ~27 unused framework files are removed; each
  registered project gains one untracked, git-excluded rule file.
- Services: set-web and set-agent-owner need a restart to drop removed code — the agent owner
  only when no agent it holds is working.
- Docs: README positioning, the capability guide, and a roadmap entry for stages 3–6.
