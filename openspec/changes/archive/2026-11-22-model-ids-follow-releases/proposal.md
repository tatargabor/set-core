## Why

A machine's `providers.json` written by `set-providers migrate` carries a full COPY of the shipped Anthropic id table in its `model_ids` block. A declared block replaces the default whole, so every later move of a shorthand in set-core stops at that file: on 2026-11-22 the shorthands moved to the 5.5 releases (`677ad872`, B-191) and this machine still launched `claude-sonnet-4-6`, because its file had copied the old value. Nothing reports the gap: `set-providers upstream` compares the file's model *names* with what set-core ships, never its *ids*. The owner's question was *„miért nem frissült?"*. The answer is that the update has no path to the machine.

## What Changes

- **The migration stops copying the id table.** The generated anthropic declaration carries no `model_ids` block, so the shipped default applies and follows each release. A deliberate pin stays possible by writing the block by hand.
- **The framework knows every value it has shipped for a name** (`PREVIOUSLY_SHIPPED_IDS`). An entry in a machine's block whose value set-core once shipped for that name, and no longer does, is a stale copy, not an override.
- **`set-providers refresh`** brings an existing file along, as a dry run by default and with `--write` to apply:
  - When every entry in the anthropic block is a copy (current or stale), it removes the block, so the default applies from then on.
  - When the block also holds a genuine override, it keeps the override, rewrites only the stale copies, and fills in shipped names the block lacks.
  - It adds shipped names missing from the anthropic catalogue.
  - It writes a timestamped backup first and keeps the file's mode.
- **`set-providers upstream` reports stale copied pins** as `behind`, naming the name, the copied id and the current id, and points at `set-providers refresh`. The fleet screen already shows that verdict.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-provider-migration`:
  - the migration's generated declaration carries no id table;
  - a refresh command brings an older file along.
- `agent-provider-config`:
  - stale copied pins are recognised;
  - the model check reports them.

## Impact

- `lib/set_orch/providers/defaults.py`: `PREVIOUSLY_SHIPPED_IDS`.
- `lib/set_orch/providers/migrate.py`: `build()` without `model_ids`, plus `refresh()`. This stays the only module that writes the file.
- `lib/set_orch/providers/upstream.py`: stale-pin detection.
- `bin/set-providers`: the `refresh` subcommand.
- Tests.
- This machine's `providers.json` is refreshed once, with a backup.
- Consumers: none. The file is machine-local and never in a repository.
