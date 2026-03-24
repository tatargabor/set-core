# Design: monorepo-module-migration

## Context

Three project-type modules exist as separate repos. The base module contains: ABC interface + dataclasses, universal rules, template resolver, template deployer, feedback system, and CLI. The web module extends base with 14 web-specific rules. The example module is a reference implementation.

The base module is framework infrastructure, not a plugin — it should be part of set-core. The web and example modules are genuine plugins that should live in `modules/` for monorepo development while remaining forkable.

Module repos contain standalone scaffolding (.claude/, openspec/, set/, CLAUDE.md, README.md) that's unnecessary in the monorepo — templates live inside each module's `set_project_{name}/templates/` already.

## Goals / Non-Goals

**Goals:**
- Absorb base module entirely into set-core lib/set_orch/
- Move web and example into modules/ (source + pyproject.toml + tests ONLY)
- Strip all scaffolding from module directories (openspec, .claude, set, CLAUDE.md, README.md)
- WebProjectType inherits from CoreProfile (set-core) instead of BaseProjectType (base)
- Remove web-specific code from verifier.py core
- Profile loader resolves built-in modules from modules/ path
- External plugins still work via entry_points

**Non-Goals:**
- Change the plugin method interface (NullProfile methods stay the same)
- Change how templates are structured inside modules
- Add new module types in this change

## Decisions

### D1: Base module decomposition into set-core

```
set-project-base/set_project_base/     →  set-core destination
────────────────────────────────────────────────────────────
base.py (ABC + dataclasses)            →  lib/set_orch/profile_types.py
project_type.py (BaseProjectType)      →  CoreProfile in profile_loader.py
resolver.py (ProjectTypeResolver)      →  lib/set_orch/profile_resolver.py
deploy.py (template deploy)            →  lib/set_orch/profile_deploy.py
feedback.py (FeedbackStore)            →  lib/set_orch/profile_feedback.py
cli.py (set-project-base CLI)          →  merged into bin/set-project
__init__.py                            →  imports from new locations
```

**Why separate files?** Each base.py module has a distinct concern. Putting them all in profile_loader.py would make it too large. The `profile_` prefix groups them logically.

### D2: CoreProfile — replaces BaseProjectType

```python
# lib/set_orch/profile_loader.py

class CoreProfile(ProjectType):
    """Universal project knowledge built into set-core.

    3 verification rules: file-size-limit, no-secrets, todo-tracking
    4 orchestration directives: npm/pip install, lockfile serialize, config review
    """
    ...

class NullProfile(ProjectType):
    """Fallback — all methods return empty/no-op."""
    ...
```

**CoreProfile vs NullProfile:**
- `NullProfile` — everything empty, used when no project type configured
- `CoreProfile` — universal rules/directives, used as parent for all real profiles

### D3: Module directory structure (web, example)

```
modules/
├── web/
│   ├── set_project_web/          ← Python package (source only)
│   │   ├── __init__.py
│   │   ├── project_type.py       ← WebProjectType(CoreProfile)
│   │   ├── planning_rules.txt
│   │   ├── templates/            ← nextjs/, spa/ templates
│   │   ├── directives/
│   │   └── verification-rules/
│   ├── pyproject.toml            ← standalone installable
│   └── tests/
└── example/
    ├── set_project_example/
    │   ├── __init__.py
    │   ├── project_type.py       ← DungeonProjectType(CoreProfile)
    │   ├── build.py
    │   └── templates/
    ├── pyproject.toml
    └── tests/
```

**What's kept:** Python package, pyproject.toml, tests/
**What's stripped:** openspec/, CLAUDE.md, README.md, .claude/, set/, .git/, *.egg-info/

### D4: WebProjectType inheritance change

```python
# BEFORE (set-project-web):
from set_project_base import BaseProjectType
class WebProjectType(BaseProjectType): ...

# AFTER (modules/web):
from set_orch.profile_loader import CoreProfile
class WebProjectType(CoreProfile): ...
```

The web module's pyproject.toml drops `set-project-base` dependency and adds `set-core` (or the import works via PYTHONPATH in monorepo dev).

### D5: Profile loader resolution — 4 steps

```python
def load_profile(type_name):
    # 1. entry_points (external plugins — highest priority)
    # 2. direct import set_project_{type_name} (editable install resilience)
    # 3. built-in modules/{type_name}/ (NEW — monorepo fallback)
    # 4. NullProfile
```

Step 3: find set-core root via `Path(__file__).resolve().parents[2]`, check `modules/{type}/set_project_{type}/__init__.py` exists, `sys.path.insert` + import.

### D6: Web-specific code removal from verifier.py

```python
# BEFORE:
def _auto_detect_e2e_command(wt_path, profile=None):
    # 1. profile.detect_e2e_command()
    # 2. package.json script lookup     ← WEB-SPECIFIC (remove)
    # 3. "npx playwright test"          ← WEB-SPECIFIC (remove)

# AFTER:
def _auto_detect_e2e_command(wt_path, profile=None):
    # 1. profile.detect_e2e_command()
    # 2. return "" (no fallback in core)
```

Also remove `_read_package_json_scripts()` — it only existed for the web fallback.

### D7: Module pyproject.toml dependency update

```toml
# modules/web/pyproject.toml
[project]
dependencies = []  # No more set-project-base dependency
# CoreProfile is imported from set_orch which is on PYTHONPATH in monorepo
# For standalone install: set-core must be installed first

[project.entry-points."set_tools.project_types"]
web = "set_project_web:WebProjectType"  # unchanged
```

### D8: Backwards compatibility shim

For a transition period, `set_project_base` import should still work when set-core is installed. Add a thin `set_project_base/__init__.py` in `lib/` that re-exports from the new locations:

```python
# lib/set_project_base/__init__.py (compatibility shim)
from set_orch.profile_types import *
from set_orch.profile_loader import CoreProfile as BaseProjectType
from set_orch.profile_resolver import ProjectTypeResolver
```

This lets existing external plugins that `from set_project_base import BaseProjectType` continue to work.
