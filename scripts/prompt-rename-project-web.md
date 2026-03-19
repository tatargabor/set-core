# SET Rename: wt-project-web → set-project-web

A `wt-tools` → `set-core` (SET = ShipExactlyThis) átnevezés része. Ez a repó a `set-project-web` lesz.

## Feladat

Hajtsd végre az alábbi rename-et egy commitban, direkt master-re.

### 1. Git tag
```
git tag v-last-wt -m "Last release under wt-project-web name"
```

### 2. Python package átnevezés
```
git mv wt_project_web set_project_web
```

### 3. Minden import frissítése
Az összes `.py` fájlban (set_project_web/, tests/):
- `from wt_project_web` → `from set_project_web`
- `import wt_project_web` → `import set_project_web`
- `wt_project_web.` → `set_project_web.` (patch target stringekben is, pl. `with patch("wt_project_web.project_type.subprocess.run")`)
- `from wt_project_base` → `from set_project_base`
- `import wt_project_base` → `import set_project_base`
- `wt_project_base.` → `set_project_base.`
- `"wt_tools.project_types"` → `"set_tools.project_types"` (entry-point group!)

### 4. pyproject.toml teljes frissítés
```toml
[project]
name = "set-project-web"
description = "Web project knowledge plugin for SET (ShipExactlyThis)"
dependencies = ["set-project-base"]

[project.scripts]
set-project-web = "set_project_web.cli:main"

[project.entry-points."set_tools.project_types"]
web = "set_project_web:WebProjectType"

[tool.hatch.build.targets.wheel]
packages = ["set_project_web"]

[tool.hatch.build.targets.wheel.force-include]
"set_project_web/templates" = "set_project_web/templates"
"set_project_web/directives" = "set_project_web/directives"
"set_project_web/verification-rules" = "set_project_web/verification-rules"
```

**FONTOS**: `dependencies = ["set-project-base"]` — a dependency is átnevezve!

### 5. wt/ directory → set/
```
git mv wt set
```
A benne lévő fájlok tartalmában is frissítsd a `wt-` → `set-` és `wt_` → `set_` referenciákat.

### 6. Docs és MD fájlok
- `README.md`: `wt-project-web` → `set-project-web`, `wt-tools` → `set-core`, `wt-project-base` → `set-project-base`, `wt_project_web` → `set_project_web`
- `CLAUDE.md`: ugyanez
- `docs/` fájlok: ugyanez
- `openspec/` fájlok: ugyanez

### 7. CLI-ben lévő referenciák
A `set_project_web/cli.py`-ban:
- `prog="wt-project-web"` → `prog="set-project-web"`

### 8. Verifikáció
```bash
python3 -c "from set_project_web import WebProjectType; print('OK')"
pytest tests/ -x --tb=short
grep -rn 'wt_project_web\|wt-project-web\|wt_project_base\|wt-project-base\|wt_tools\.project' --include='*.py' --include='*.toml' .
# ^ Ez 0 találat kell legyen
```

### 9. Commit
```
feat: rename wt-project-web to set-project-web (SET ecosystem rename)
```

**FONTOS**:
- Az entry-point group MUSZÁJ `set_tools.project_types` legyen!
- A dependency `set-project-base`-re változik (nem `wt-project-base`)!
- A `base.py`-ban és `project_type.py`-ban a `from wt_project_base` importok is frissülnek!
