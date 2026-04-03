# Design: Rename wt/ to set/

## Approach

Bulk sed rename in code + directory rename in templates + auto-migration in set-project init.

## Decisions

### D1: Rename strategy — sed + verify

1. `sed -i` all Python/bash/yaml/md files: `"wt/` → `"set/`, `'wt/` → `'set/`, `/wt/` → `/set/`
2. Rename template directories: `templates/nextjs/wt/` → `templates/nextjs/set/`
3. Rename function: `scaffold_wt_directory` → `scaffold_set_directory`
4. Rename variable: `wt_dir` → `set_dir` (only the config dir variable, not git worktree vars)
5. TypeScript compile + Python import check after

### D2: Migration in set-project init

Add to the migration section of `bin/set-project`:
```bash
if [[ -d "$project_path/wt" && ! -d "$project_path/set" ]]; then
    mv "$project_path/wt" "$project_path/set"
    success "Migrated wt/ → set/"
fi
```

### D3: Backwards compat in Python

Where paths are constructed, check `set/` first:
```python
config_path = project / "set" / "orchestration" / "config.yaml"
if not config_path.exists():
    config_path = project / "wt" / "orchestration" / "config.yaml"  # legacy
```

### D4: .gitignore update

Change `wt/.work/` → `set/.work/` in the gitignore scaffold.

## Risks

- [Risk] Consumer projects with uncommitted wt/ changes → migration renames safely, git tracks as rename
- [Risk] Parallel branches referencing wt/ → merge conflicts possible but resolvable
