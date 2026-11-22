## Context

`effective_model_ids` applies a declared block whole, a rule kept deliberately: a partial table would deliver a missing name untranslated. `migrate.build()` wrote `dict(DEFAULT_MODEL_IDS)` on purpose, *"so a migrated machine is pinned to the mapping that existed at migration time"*. That pinning is the defect. It makes every shipped bump a no-op on every migrated machine, and the machine cannot tell its copy from a choice.

## Decisions

- **Stop copying; do not merge.** The whole-block rule stays. A machine without a block gets the default, and a machine that wants a pin writes one. Merging the default under a declared block was rejected, because it would silently change what a deliberate partial block means.
- **History over heuristics.** "Is this entry a copy?" is answered by the values set-core actually shipped, recorded in `PREVIOUSLY_SHIPPED_IDS`, read from git history on 2026-11-22. A heuristic such as "an older release than the current default" was rejected: it would treat a deliberate pin to an older release as a copy and erase it.
- **Explicit command, dry run first.** Reading the configuration never writes it (an existing requirement). The refresh is a command, and `--write` is required to change anything.
- **Writer stays in `migrate.py`.** One module writes `providers.json`. This keeps that invariant and its test.
- **Report through the existing check.** `set-providers upstream` and the fleet screen's provider badge already carry `behind`. Stale pins become one more reason for that verdict, not a new surface.

## Risks

- **A future bump that forgets to record the old value.** That machine's copy would then read as an override and be kept, which fails safe: nothing is erased. The shorthand currency test names the history table in its failure message.
