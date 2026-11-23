## Why

Nothing tells anyone when Anthropic ships a model that set-core does not know. Measured
2026-09-29: Anthropic's public model overview lists `claude-sonnet-5-5`, released the day
before, while set-core's `sonnet` still resolves to `claude-sonnet-4-6`. Separately,
B-156: the model catalogue in a machine's `providers.json` is copied once at migration, so
a name set-core ships later (`opus-5-5`) never reaches the "Start an agent here" dialog.
Both gaps are silent. The user asked for set-core to read a public model list and **advise**
that set-core (or the machine's config) needs updating. Self-updating was not asked for.

## What Changes

- A check that fetches Anthropic's public model overview
  (`https://platform.claude.com/docs/en/about-claude/models/overview.md`, no key needed).
  It extracts the model ids from the overview table's "Claude API ID" and
  "Claude API alias" rows only, and compares them with the ids set-core ships
  (`DEFAULT_MODEL_IDS`).
- The same check compares the names set-core ships (`ANTHROPIC_MODEL_NAMES`) with the
  machine's declared `anthropic` catalogue, which reports B-156's gap on this machine.
- The result has three states, `current`, `behind` and `unknown`. A failed fetch or a page
  that yields zero ids is `unknown`, **never** `current`.
- The fetched ids are cached for 24 h under `~/.cache/set-core/`. This is public data, so
  the confidentiality boundary is not touched.
- Surfaces: `set-providers upstream [--refresh] [--json]` (exit 0 current, 1 behind,
  2 unknown), `GET /api/fleet/models/upstream`, and a notice in the "Start an agent" dialog.
- **Advice only.** The check never edits `providers.json`, `defaults.py` or
  `set-common.sh`. Adding a model stays a reviewed set-core commit, because the short name
  → id mapping is a decision rather than something to derive.

## Capabilities

### New Capabilities
- `upstream-model-watch`: reads the provider's public model list, compares it with what
  set-core ships and what the machine declares, and reports the gap as advice. It fails
  as `unknown`, never as `current`.

### Modified Capabilities
<!-- none: the catalogue, resolver and start contract are unchanged -->

## Impact

- New: `lib/set_orch/providers/upstream.py` (Layer 1). It stays provider-shaped: the
  source URL and the parser belong to the `anthropic` provider only. No web or project
  specifics.
- `bin/set-providers`: new `upstream` subcommand.
- `lib/set_orch/api/fleet.py`: new read-only route.
- `web/src/pages/Fleet.tsx` start dialog, plus `web/src/lib/fleetProviders.ts`: the notice.
- Network: one HTTPS GET to a public Anthropic docs page, at most once per 24 h per
  machine unless `--refresh` is given. No credential or local data is sent.
