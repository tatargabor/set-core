# SET Rename: wt-project-base → set-project-base

A `wt-tools` → `set-core` (SET = ShipExactlyThis) átnevezés része. Ez a repó a `set-project-base` lesz.

## Feladat

Hajtsd végre az alábbi rename-et egy commitban, direkt master-re.

### 1. Git tag
```
git tag v-last-wt -m "Last release under wt-project-base name"
```

### 2. Python package átnevezés
```
git mv wt_project_base set_project_base
```

### 3. Minden import frissítése
Az összes `.py` fájlban (set_project_base/, tests/):
- `from wt_project_base` → `from set_project_base`
- `import wt_project_base` → `import set_project_base`
- `wt_project_base.` → `set_project_base.` (patch target stringekben is!)
- `"wt_tools.project_types"` → `"set_tools.project_types"` (entry-point group!)

### 4. pyproject.toml teljes frissítés
```toml
[project]
name = "set-project-base"
description = "Base project type plugin for SET (ShipExactlyThis) — universal project knowledge"
dependencies = ["pyyaml>=5.0"]

[project.scripts]
set-project-base = "set_project_base.cli:main"

[project.entry-points."set_tools.project_types"]
base = "set_project_base:BaseProjectType"

[tool.hatch.build.targets.wheel]
packages = ["set_project_base"]

[tool.hatch.build.targets.wheel.force-include]
"set_project_base/templates" = "set_project_base/templates"
```

### 5. wt/ directory → set/
```
git mv wt set
```
A benne lévő fájlok tartalmában is frissítsd a `wt-` → `set-` és `wt_` → `set_` referenciákat.

### 6. Docs és MD fájlok
- `README.md`: `wt-project-base` → `set-project-base`, `wt-tools` → `set-core`, `wt_project_base` → `set_project_base`
- `CLAUDE.md`: ugyanez
- `openspec/` fájlok: `wt-project-base` → `set-project-base`, `wt-tools` → `set-core`

### 7. CLI-ben lévő entry-point group frissítés
A `set_project_base/cli.py`-ban:
- `entry_points(group="wt_tools.project_types")` → `entry_points(group="set_tools.project_types")`
- `entry_points().get("wt_tools.project_types", [])` → `entry_points().get("set_tools.project_types", [])`
- `prog="wt-project-base"` → `prog="set-project-base"`

### 8. Verifikáció
```bash
python3 -c "from set_project_base import BaseProjectType; print('OK')"
pytest tests/ -x --tb=short
grep -rn 'wt_project_base\|wt-project-base\|wt_tools\.project' --include='*.py' --include='*.toml' .
# ^ Ez 0 találat kell legyen
```

### 9. Commit
```
feat: rename wt-project-base to set-project-base (SET ecosystem rename)
```

**FONTOS**: Az entry-point group MUSZÁJ `set_tools.project_types` legyen, mert a set-core-ban is erre változott!
