## Context

An agent started from the fleet screen always runs `claude --dangerously-skip-permissions`
against Anthropic. `lib/set_orch/fleet/ownerd.py:65` holds that argv as a constant, and
`lib/set_orch/api/fleet.py:1044` deliberately refuses to accept an argv from the caller —
its own docstring defends that narrowness, and this design keeps it.

A working alternative-provider runner already exists: `bin/set-glm` (commit `6668bde3`),
reading `~/.config/set-core/glm.env`. It is a shell wrapper on `PATH`. Nothing in the
framework can read its settings, and nothing in the framework can launch it.

Four measurements taken while designing this change constrain everything below. They are
stated with their evidence because three of them fail in the silent direction, and a
silent failure is the one a later reader cannot re-derive.

**M1 — the environment seam is an ordering nothing holds.** `owner.py:167` removes every
environment key beginning with `CLAUDE` from the child's environment, so that a session
marker is not inherited. `owner.py:170` applies the caller's `env=` afterwards. So `env=`
is the only place a `CLAUDE`-prefixed variable can survive. The variable an alternative
provider needs — the context-window override — is exactly such a key. Losing it does not
raise: measured on a consumer project, it produced 9.5 minutes, three consecutive compacts,
zero lines written, and then the CLI's own *"Autocompact is thrashing"*. From outside it
looks like a slow model.

**M2 — resume drops the environment entirely.** `owner.py:579` `recover()` calls
`owner.start(...)` with no `env=`. An agent started on an alternative provider would come
back on the default one: different bill, different context window, identical appearance.
`ownerd.py:65`'s own comment already forbids this class of drift between a resumed and a
fresh agent.

**M3 — the model validator is a closed allowlist.** `lib/set_orch/config.py:28`
`MODEL_NAME_RE` is `^(haiku|sonnet|opus|sonnet-1m|opus-1m|opus-4-6|opus-4-7|opus-4-6-1m|opus-4-7-1m)$`.
Measured: `glm-5.3` and `glm-5.3-flash` both fail it. Alternative-provider model names do
not hit a missing entry; they hit a wall.

**M4 — a bad start reports the wrong thing.** Recorded as B-105: when a child cannot be
executed, `systemd-run` fails, the scope never registers, `await_unit` spins out its
40 × 0.1 s, `adopt` raises, and the route answers `409 did not become active` after roughly
four seconds. That is a *true* sentence about the symptom that points away from the cause.

One more, which is about this design's own evidence rather than about the code:

**M5 — the launch parameters are single-sourced.** `bin/set-glm` and a consumer project's
own implementation were written by the same author from the same single measurement. One
measurement written down twice is not two measurements. Every parameter this change treats
as measured therefore carries a task to re-measure it independently before any artifact
states it as a finding.

A second set-core session is concurrently planning `work-cycle-run-visibility`, which needs
to resolve `argv[0]` against the final child environment — the same lines this change
touches. That collision is resolved in Decision 5 rather than by scheduling.

## Goals / Non-Goals

**Goals:**

- Choose the provider and the model when starting an agent from the fleet screen.
- One machine-level configuration that every set project inherits by reading it, holding
  every token and model setting.
- One resolver, called by both the CLI runner and the fleet, so a measured parameter is
  stated once.
- A per-project override that may carry its own credential, with the winning level visible.
- Fail closed before anything is forked, and never onto a different provider.

**Non-Goals:**

- Replacing `lib/set_orch/model_config.py`'s role-based chain. It answers which model an
  orchestration ROLE uses; this change answers which provider and credential ONE process
  runs on. Provider is the outer axis, model the inner one.
- Absorbing `lib/set_router/` and `cc-accounts.json`. Anthropic OAuth account switching
  stays a separate mechanism with a separate file.
- Changing the orchestration work-unit start (`fleet.py:1532`), which already passes its
  own `--model` to the engine and belongs to the other session's change.
- Automatic provider selection. The provider is chosen by a person or by configuration,
  never inferred from what happens to be in the environment.

## Decisions

### D1 — Measured parameters live as data; the resolver holds no provider knowledge

`~/.config/set-core/providers.json` declares each provider's endpoint, credential, model
catalogue and launch parameters. `lib/set_orch/providers/` reads it and returns environment,
argv extras and provenance. `bin/set-glm` becomes a caller.

*Why:* adding a model must cost zero framework changes, and a value that exists in two
places drifts. The seventh time this repository has taken the declaration-driven route.

*Alternative rejected — constants in Python, config holds only the token:* every new model
becomes a code change and a redeploy to every consumer.

*Alternative rejected — the owner execs `bin/set-glm`:* fewer lines, but the fleet's start
then depends on a shell wrapper being on the service's `PATH`, and the failure surface
becomes a shell exit code. B-105 is precisely what that costs — and see Decision 6.

### D2 — Hybrid merge: the credential and its endpoint are one unit, the model is not

Three levels — machine default, project override, this start. The model resolves
field-wise. The credential and the endpoint resolve together, as one indivisible block; a
level supplying either must supply both.

*Why:* a peer running the field-wise form hit both failure directions in one evening. It
saved them once — a worktree `reset --hard` ate their configuration and they reconstructed
it a key at a time — and it produced, the same evening, a run whose model came from one
source and whose remaining settings came from another: a combination nobody had written
down. A credential belongs to the endpoint it authenticates against, so mixing those two
field-wise yields a 401 at best and the wrong account at worst. The model is precisely the
field that is meant to differ per project.

*Alternative rejected — wholly field-wise:* permits the half-inherited credential above.

*Alternative rejected — wholly block-wise:* every project wanting a different model must
duplicate the credential, and a rotated key then has to be changed in N places.

### D3 — The resolver returns provenance, and the surface shows it

Each resolved field carries the level that supplied it. The launch reports it; the screen
shows it; the record keeps it.

*Why:* this is the condition the same peer attached to accepting a per-project credential —
*"the precedence must be printed at runtime, never inferrable"* — and it is the argument
`OwnedAgent.requested_by` already carries in its own comment: a relation that exists only
at the moment of the act has to be written down during it. After the fork nothing on the
process tree says which provider an agent runs on.

### D4 — `MODEL_NAME_RE` becomes per-provider

The global constant becomes the Anthropic provider's catalogue. Each provider's catalogue
is the allowlist for that provider.

*Why (M3):* the current regex is a closed list, so an alternative provider's names are not
merely absent, they are invalid. Widening the single regex to admit them would also admit
them for Anthropic, where they are wrong.

*Alternative rejected — loosen the regex to a format pattern:* it stops rejecting
typos for every provider at once, which is the validation's whole value.

### D5 — One named operation owns child-environment construction, and a test holds its order

The `owner.py` 162–170 band becomes a single named function. The removal happens inside it,
before the caller's variables are applied. A test fails if that order reverses.

*Why (M1):* the ordering is load-bearing and is currently held by adjacency alone. Someone
moving the removal downward for an entirely sound reason would produce a compact-thrash
loop, not an error. And the concurrent `work-cycle-run-visibility` change needs to resolve
`argv[0]` against the *result* of this band — so giving the band one owner means the two
changes touch a function's interior and its call site, never the same lines. Agreed on the
agent channel; the other session ships this function first, and this change builds on its
final shape.

### D6 — Every refusal happens before the fork

Missing credential, model absent from the resolved provider's catalogue, gateway-prefixed
model name: all refused by the resolver, before any process, scope or handle exists.

*Why (M4):* a start that fails after the fork reports `did not become active` — true, and
pointing away from the cause. A configuration fault must be reported as a configuration
fault. And never as a fallback: a silent fallback would run the work in the other frame
with nothing on the screen saying so.

### D7 — A survival guard where the effect is

Immediately before the fork, assert that every variable the resolver returned is present
with its resolved value. Refuse and name the missing variable otherwise.

*Why:* D5's test protects the order inside one function; this protects the outcome against
every other way a variable can be lost. The guard belongs where the effect is, not where
the alarming word is.

### D8 — Provider and model are recorded at the one point a start is recorded

Not at each caller. An agent whose provider was never recorded reads as *unrecorded*, never
as *default*.

*Why (M2 and its peer):* `OwnedAgent.requested_by` lives only in memory
(`owner.py:121`, exposed at `ownerd.py:213`), so a provider recorded the same way would
vanish when the owning service restarts — while the agent keeps running. A peer hit the
same class in their own run ledger, which stored cost, duration and tokens but not the
provider, leaving them unable to say afterwards which frame a run had used; they fixed it at
the single ledger entry point rather than at a dozen call sites, and that is the shape
copied here. A gap is not a zero: *unrecorded* and *default* must not render the same.

### D9 — The browser gets a catalogue and a presence flag, never a credential

Two separately named exits from the resolver: one returns the catalogue, one returns the
launch environment. Not one function with a redaction flag.

*Why:* a default argument that flips the wrong way publishes a token. Two names cannot be
confused, and the catalogue's return type has no field a credential could occupy. A
provider without a credential is offered as *unusable* rather than omitted, so a person sees
why they cannot pick it — the same "a gap is not a zero" rule.

### D10 — Migration is a command, and the deprecation window is one release

`set-providers migrate`. Reading never migrates. `glm.env` stays readable for one release
with a warning naming the command; after that it is unread and the failure names the
command.

*Why:* migrating on first read is a write hidden inside a resolver — invisible in every
trace, and it fires in whatever process happens to read first. Dropping `bin/set-glm`'s
repo-`.env` tier is a documented behaviour removal, so it fails loudly: the difference
between *"you have not configured this"* and *"the place you configured it is no longer
read"* is the whole of what makes the message actionable.

## Risks / Trade-offs

- **The launch parameters rest on one measurement (M5).** → The independent
  re-measurement is a task in this change, and no artifact may state the parameter as a
  finding until it passes. Until then it is written as single-sourced.
- **A per-project credential means a project can spend against a different account, quietly.**
  → D3: provenance is returned, printed at launch and shown on the screen, and a
  non-default credential is marked on the running agent.
- **Two sessions edit `owner.py` in the same window.** → D5 gives the band one owner and
  one function; the other session ships it first and announces the final shape on the
  channel. Commits here are pathspec-limited, per this repository's own rule.
- **The `--allowedTools` flag restricts nothing (B-106, commit `dd1ac9a0`).** Measured here
  on Anthropic in an empty directory with a clean settings file: `--allowedTools 'Read'`
  plus a prompt asking for Bash ran Bash, `permission_denials` empty. → No flag this change
  emits may be believed to restrict because of its name, and no test in this change may
  assert on `permission_denials`, which is empty in the working *and* the broken case.
  Assert on whether the tool ran.
- **A configuration file holding credentials for several accounts is a larger blast radius
  than one env file.** → Owner-only mode enforced on read as well as on write; the file
  never leaves the machine; diagnostics name the provider and endpoint only. Note that the
  credential is still present in the child process's environment, readable through
  `/proc/<pid>/environ` by the same user — that is unchanged from today's behaviour, and
  it is named here so it is a known property rather than a later discovery.
- **Per-provider validation could regress the Anthropic names.** → A test asserts that every
  name valid before this change is still valid for the Anthropic provider.

## Migration Plan

1. Ship the configuration reader, the resolver and `set-providers` — nothing about starting
   agents changes yet. `bin/set-glm` switches to the resolver and keeps reading `glm.env`
   through the compatibility path.
2. Run `set-providers migrate`. It writes `providers.json` at mode `0600`, reports the
   fields it carried across without their values, and leaves `glm.env` in place so the
   result can be checked against its source.
3. Ship the owner-side change: the named child-environment function (after the concurrent
   change lands it), the survival guard, provider-carrying `start()` and `recover()`, and
   the durable record.
4. Ship the route, the catalogue endpoint and the screen. Look at the screen.
5. In the release after, stop reading `glm.env`.

**Rollback:** steps 1–2 are additive — `glm.env` still exists and still works. After step 3,
rolling back means reverting the commits; no configuration is destroyed by doing so, because
the migration never deletes its source.

## Open Questions

- **Which release closes the deprecation window?** The specs require one window and a loud
  failure after it; naming the version is a release decision, not a design one.
- **Should the orchestration work-unit start (`fleet.py:1532`) eventually resolve its
  `--model` through this resolver too?** It has its own model field today and belongs to
  the concurrent change. Deliberately left alone here; worth revisiting once both land, so
  the framework does not end with two answers to "which model".
- **Does the independent re-measurement (M5) confirm the context-window parameter as
  necessary and sufficient?** If it does not, the parameter set changes but no interface in
  this design does — the values are data.
