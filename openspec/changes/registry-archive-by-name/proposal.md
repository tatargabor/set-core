## Why

`registry-prune`'s bulk archiving deliberately refuses any entry with open issues —
`ui-quality.md`: compacting must never hide a failure. On the live registry that left four
E2E runs on the list (with 1, 2, 1 and 1 open issues), and an operator who has looked at them
and wants them out has no way to say so.

That refusal is not a bug to override. It protects the **threshold-driven, bulk** selection
from blindly hiding a failure nobody examined. Archiving a **named** entry is a different act:
the operator picked that specific project, exactly as `set-project remove <name>` requires.

There is also no way back. `clear_archive()` exists in the module and has no CLI, so from a
user's seat archiving is one-way.

## What Changes

- **New `set-project archive <name>...`** — archives the named entries, whatever their age and
  wherever they live.
- **New `set-project unarchive <name>...`** — the inverse, restoring the entry exactly.
- **Open issues warn but do not block.** Naming the project is the operator's decision, and the
  issues do not disappear: the sidebar's issue total comes from a separate endpoint — measured
  after the previous archiving run, the count stayed at 14, unchanged.
- **A live sentinel or orchestrator PID blocks, with no override.** Hiding running work is a
  different category from hiding a stale failure; stop it first.
- **A missing directory blocks** — that is deregistration's job (`set-project prune`), and
  archiving is by definition for entries whose directory is alive.
- **An unknown name aborts the whole command** before anything is written, so a typo cannot
  half-apply across the other named entries.
- **Archiving the default project clears the `default` pointer and says so.** Measured on the
  live registry: the default points at one of the four runs. An archived default is invisible
  on the dashboard yet still default — the same dangling-pointer class the prune already
  handles for deregistration.

The E2E-root restriction does **not** apply here: it exists so that *age-based* bulk selection
cannot catch a real project. A named entry involves no selection.

## Capabilities

### Modified Capabilities
- `registry-prune`: adds named archive/unarchive with its own refusal rules, distinct from the
  bulk path's; the existing bulk requirements are unchanged.

## Impact

- `lib/set_orch/registry_prune.py` — new `archive_by_name()`; reuses `apply_archive()`,
  `clear_archive()`, `_open_issue_count()`, `_live_process()`, `_clear_dangling_default()` and
  `project_registry.backup_registry()`.
- `bin/set-project` — two subcommands delegating to the module, as `cmd_prune` does.
- No dashboard change: `X-Archived-Count` and the reveal toggle already cover it.
