## Why

An agent the fleet starts always runs `claude --dangerously-skip-permissions` against
Anthropic. There is no way to start one on a different provider, and no way to say which
model it should use — so the screen that exists to show what every agent is doing cannot
express the one thing that decides what an agent costs and how large a context it can hold.

A working GLM runner already exists (`bin/set-glm`), with the endpoint, the context window
and three fail-closed branches measured. It is a shell wrapper on `PATH`, reachable from a
terminal and from nowhere else. The fleet cannot use it, the framework cannot read its
settings, and its configuration lives in a file (`~/.config/set-core/glm.env`) that only it
knows about.

The user asked for both halves at once: choose the provider and the model when starting an
agent from the fleet screen, and keep every token and model setting in one central set-core
place that every set project inherits — not in a project's own `.env`, which a worktree
`reset --hard` takes with it.

## What Changes

- **New central config `~/.config/set-core/providers.json`** (mode `0600`), beside the
  central config home that already holds `config.json`, `cc-accounts.json`,
  `projects.json` and `jira.json`. It declares providers, their measured parameters, their
  model catalogues, their tokens, and the per-project overrides. Projects inherit it by
  READING it; `set-project init` must never copy it into a consumer tree.
- **New resolver module `lib/set_orch/providers/`** — one function that turns
  (project, requested provider, requested model) into the child process's env and argv
  extras, plus the **provenance** of every field. Both `bin/set-glm` and the fleet's agent
  owner call it. There is no second reader and no JavaScript copy.
- **Provider and model become part of starting an agent.** `StartAgentBody` gains two
  optional named fields; it still refuses a free-form `argv`, which is the narrowness its
  own docstring defends. The owner threads the resolver's env through the one seam that
  survives its `CLAUDE*` strip.
- **A named function owns the child-env construction** in `owner.py`, so the strip-then-
  update ORDER is held by a test instead of by adjacency. A second set-core change is
  planned against the same lines; this gives that band one owner.
- **A start guard where the effect is:** the owner refuses, before the fork, if any env key
  the resolver returned did not survive into the child env.
- **`recover()` carries the provider it recovered.** Today it starts without `env=`, so a
  resumed agent would silently change framework.
- **Provider, model and provenance reach a durable record**, at one entry point, not only
  the in-memory `OwnedAgent`.
- **The fleet start form gains provider and model selection**, and shows which precedence
  level won.
- **New `set-providers` CLI** with an explicit `migrate` subcommand.
- **BREAKING — `~/.config/set-core/glm.env` is replaced.** It stays readable for one
  release, with a deprecation warning naming `set-providers migrate`, then stops being read.
- **BREAKING — `bin/set-glm` stops reading the repository's own `.env`.** That middle
  configuration tier is documented today. Its removal is the direct consequence of putting
  credentials in a central place, and it must fail loudly rather than fall through to a
  stop that names the wrong cause.

## Capabilities

### New Capabilities

- `agent-provider-config`: the central `providers.json` — its shape, its permissions, what
  a provider declaration contains, and the rule that a new model costs no framework change.
- `agent-provider-resolution`: the resolver — the three-level precedence with its hybrid
  merge (credential and endpoint inseparable, model standalone), the provenance it returns,
  and the fail-closed refusals that all happen before any process is forked.
- `agent-provider-start`: starting an agent on a chosen provider — the request shape, the
  env seam and the guard that it survived, what is recorded durably, and how a resume keeps
  the framework it was started in.
- `agent-provider-migration`: `set-providers`, the explicit one-shot migration off
  `glm.env`, the one-release deprecation window, and the loud removal of the repo-`.env`
  tier.

### Modified Capabilities

- `agent-fleet-restore`: an entry is restored by starting an agent that resumes its
  session. That start must now reproduce the provider the session ran on; restoring onto a
  different provider is a silent change of both cost and context window.

## Impact

**Code**

- `lib/set_orch/providers/` (new), `bin/set-providers` (new)
- `bin/set-glm` — becomes a caller of the resolver rather than a second implementation
- `lib/set_orch/fleet/owner.py` — child-env construction, the survival guard, `start()`,
  `recover()`, `OwnedAgent`
- `lib/set_orch/fleet/ownerd.py`, `lib/set_orch/fleet/owner_client.py` — the socket
  protocol carries provider and model
- `lib/set_orch/api/fleet.py` — `StartAgentBody`, the start route, and a catalogue endpoint
- `lib/set_orch/fleet/restore.py` — restore reproduces the recorded provider
- `lib/set_orch/config.py` — `MODEL_NAME_RE` stops being a single global allowlist and
  becomes per-provider; today's regex remains the Anthropic provider's list
- `web/src/pages/Fleet.tsx` and the fleet start form's tests

**Configuration**

- `~/.config/set-core/providers.json` — new, `0600`, machine-level
- `~/.config/set-core/glm.env` — deprecated for one release, then unread

**Not affected, deliberately**

- `lib/set_orch/model_config.py`'s role-based chain (`agent`, `digest`, `review`, …). It
  answers which model an orchestration ROLE uses; this change answers which provider and
  credential ONE process runs on. Provider is the outer axis, model the inner one.
- `lib/set_router/` and `cc-accounts.json` — Anthropic OAuth account switching stays where
  it is; this change does not absorb it.
- The browser. It receives a catalogue of provider and model names and a boolean saying
  whether a token is configured. It never receives a token.

**Confidentiality**

`providers.json` holds credentials and is machine-level by design; nothing derived from it
is persisted into this repository, and diagnostics name the provider and the endpoint, never
the token.
