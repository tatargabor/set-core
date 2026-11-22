## 1. Data

- [x] 1.1 `PREVIOUSLY_SHIPPED_IDS` in `providers/defaults.py`, every value moved away from, read from git history; a test that no current default appears in it for the same name

## 2. Migration and refresh

- [x] 2.1 `migrate.build()` writes no `model_ids`; test that a migrated anthropic declaration launches the current default
- [x] 2.2 `migrate.refresh(path, write=False)`: classify, plan, backup + atomic write keeping the mode; tests for the pure copy, the kept override, the filled names, the dry run, the idempotent re-run
- [x] 2.3 `set-providers refresh [--write]`

## 3. Check

- [x] 3.1 `upstream.check` reports stale copied pins → `behind`, with advice naming `set-providers refresh`; test

## 4. This machine

- [x] 4.1 Dry run, then `--write`, on this machine's file; `set-providers upstream --refresh` says `current`; a `sonnet` launch plan names `claude-sonnet-5-5`

## Evidence (2026-11-22)

- `tests/unit/test_providers_refresh.py` 13/13. Mutations caught:
  - `classify_id` ignoring the history: 3 tests fail;
  - the verdict ignoring stale pins: 1 test fails, after the test was narrowed so the stale pins are the only reason for `behind`. The first version let that mutant survive, because an incomplete catalogue also made the verdict `behind`.
- This machine: the dry run listed 3 stale copies (`haiku`, `sonnet`, `sonnet-1m`) and 6 missing names.
- `--write` removed the block and wrote a backup; the file stays mode 600.
- The re-run reports "up to date".
- `set-providers show` gives `sonnet -> claude-sonnet-5-5` and `haiku -> claude-haiku-5-5`; `set-providers upstream --refresh` says `current` and exits 0.
- Regression: across the provider and model test files, 7 fail, and all 7 are in the HEAD baseline set measured for `677ad872`, or are the known `test_fleet_api` rename failure.
- Scope note, measured: Claude Code's own `sonnet` alias already resolves to `claude-sonnet-5-5` (`claude -p --model sonnet`, `modelUsage`). The 4.6 launches came only from paths that translate through set-core's mapping.
