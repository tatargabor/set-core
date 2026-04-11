# Module Developer Guide

How to create a new project type plugin for set-core.

## Architecture

```
ProjectType ABC          ← abstract interface (lib/set_orch/profile_types.py)
  └── CoreProfile        ← universal rules: file-size, no-secrets, todo-tracking
        └── WebProjectType    ← web: i18n, Playwright, Prisma, Next.js
              └── MobileProjectType  ← mobile: Capacitor, Xcode, cap sync
        └── DungeonProjectType ← example: .dungeon files, graph verification
```

Every module inherits from `CoreProfile` (or a subclass like `WebProjectType`). Python's Method Resolution Order (MRO) handles the rest.

## The Inheritance Model

### Override + Extend Pattern

The key pattern in set-core modules: **call `super()`, then add your own items**.

```python
class MobileProjectType(WebProjectType):

    def get_verification_rules(self):
        parent_rules = super().get_verification_rules()
        # parent_rules already contains:
        #   CoreProfile:  file-size-limit, no-secrets, todo-tracking (3)
        #   WebProjectType: i18n-completeness, route-registered, ... (12)
        # Total inherited: 15 rules

        mobile_rules = [
            VerificationRule(id="capacitor-config", ...),
        ]
        return parent_rules + mobile_rules  # 16 rules total
```

This works for all list-returning methods:
- `get_verification_rules()` — integrity checks
- `get_orchestration_directives()` — parallel work coordination
- `spec_sections()` — spec writing sections
- `get_templates()` — template variants

### Pure Override Pattern

Some methods return a single value. Override them completely:

```python
class MobileProjectType(WebProjectType):

    @property
    def info(self):
        return ProjectTypeInfo(
            name="mobile",     # unique type name
            version="0.1.0",
            description="...",
            parent="web",      # for documentation only
        )

    def detect_build_command(self, project_path):
        if (Path(project_path) / "ios/App").is_dir():
            return "npm run build && npx cap sync ios"
        return super().detect_build_command(project_path)  # fall back to web
```

### Inherit Without Override

Methods you don't implement are automatically inherited. If `MobileProjectType` does NOT override `collect_test_artifacts()`, calling it uses `WebProjectType`'s implementation (Playwright screenshots). **No code needed — it just works.**

When the parent module is updated (e.g., web adds a new verification rule), child modules automatically pick it up on next run.

## What You Must Implement

Only two things are required:

```python
@property
def info(self) -> ProjectTypeInfo:
    """Return unique metadata."""

def get_templates(self) -> List[TemplateInfo]:
    """Return at least one template variant."""
```

Everything else has defaults (empty lists, None, no-op). Override only what your domain needs.

## Template System

### Template Directory

Each template is a directory of files to deploy into consumer projects:

```
modules/mobile/
  set_project_mobile/
    templates/
      capacitor-nextjs/         ← template variant
        manifest.yaml           ← controls deployment behavior
        capacitor.config.ts     ← deployed to project root
        rules/
          capacitor-conventions.md  ← deployed to .claude/rules/
```

### manifest.yaml

Controls how files are deployed:

```yaml
core:
  - capacitor.config.ts         # always deployed
  - rules/capacitor-conventions.md

protected:
  - .env.example                # never overwritten if project modified it

merge:
  - project-knowledge.yaml      # additive YAML merge (add missing keys)

modules:
  share-extension:              # optional module
    description: "iOS Share Extension scaffold"
    files:
      - ios/ShareExtension/ShareViewController.swift
```

### Template Inheritance (MRO-aware)

When a module inherits from another, both template sets are available:

```python
class MobileProjectType(WebProjectType):
    def get_templates(self):
        return [
            # Mobile-only template
            TemplateInfo(id="capacitor-nextjs", template_dir="templates/capacitor-nextjs"),
        ]
        # The "nextjs" template from WebProjectType is also available
        # via MRO-aware get_template_dir() resolution
```

`set-project init --project-type mobile --template capacitor-nextjs` deploys mobile's template.
`set-project init --project-type mobile --template nextjs` deploys web's template (inherited).

The `get_template_dir()` method walks the MRO to find the correct physical directory for each template, regardless of which class registered it.

## Methods Reference

### Rules & Directives (Override + Extend)

| Method | Returns | Pattern |
|--------|---------|---------|
| `get_verification_rules()` | `List[VerificationRule]` | `super() + own` |
| `get_orchestration_directives()` | `List[OrchestrationDirective]` | `super() + own` |
| `spec_sections()` | `List[SpecSection]` | `super() + own` |
| `get_templates()` | `List[TemplateInfo]` | own only (parent's available via MRO) |

### Detection (Override or Inherit)

| Method | Returns | What it does |
|--------|---------|--------------|
| `detect_test_command(path)` | `Optional[str]` | Auto-detect test runner |
| `detect_build_command(path)` | `Optional[str]` | Auto-detect build step |
| `detect_e2e_command(path)` | `Optional[str]` | Auto-detect E2E test command |
| `detect_package_manager(path)` | `Optional[str]` | Auto-detect npm/pnpm/yarn |
| `detect_dev_server(path)` | `Optional[str]` | Auto-detect dev server command |

Tip: call `super()` as fallback if your detection doesn't match:

```python
def detect_build_command(self, project_path):
    if my_condition:
        return "my-build-command"
    return super().detect_build_command(project_path)
```

### Engine Integration (Override if Needed)

| Method | Default | When to override |
|--------|---------|-----------------|
| `planning_rules()` | `""` | Domain-specific decompose guidance |
| `cross_cutting_files()` | `[]` | Files needing serialization |
| `security_checklist()` | `""` | Security items for proposals |
| `ignore_patterns()` | `[]` | Exclude from digest/codemap |
| `generated_file_patterns()` | `[]` | Auto-resolve merge conflicts |
| `gate_overrides(change_type)` | `{}` | Per-change-type gate config |
| `collect_test_artifacts(wt_path)` | `[]` | Collect screenshots/traces |
| `parse_test_results(stdout)` | `{}` | Parse test output per-test |
| `render_test_skeleton(entries, name)` | `""` | Generate test file template |

### Gates (Override if Needed)

| Method | Default | When to override |
|--------|---------|-----------------|
| `register_gates()` | `[]` | Domain-specific gate executors |
| `e2e_gate_env(port)` | `{}` | Env vars for E2E gate |
| `e2e_pre_gate(wt_path, env)` | `True` | Setup before E2E (migration, seed) |
| `e2e_post_gate(wt_path)` | no-op | Cleanup after E2E |
| `integration_pre_build(wt_path)` | `True` | Setup before build gate |
| `worktree_port(change_name)` | `0` | Deterministic port for worktree |

## Registration

### pyproject.toml

```toml
[project]
name = "set-project-mobile"
version = "0.1.0"
dependencies = ["set-project-web"]  # parent module dependency

[project.entry-points."set_tools.project_types"]
mobile = "set_project_mobile:MobileProjectType"
```

### Installation

```bash
pip install -e modules/mobile
```

### Resolution order

When `set-project init --project-type mobile` runs:

1. Entry points (`set_tools.project_types` group) — highest priority
2. Direct import (`import set_project_mobile`)
3. Built-in modules (`modules/mobile/set_project_mobile/`)
4. `NullProfile` fallback

## Testing Your Module

Follow `modules/example/tests/` as a reference:

```python
# test_project_type.py
def test_info(pt):
    assert pt.info.name == "mobile"
    assert pt.info.parent == "web"

def test_inherits_web_rules(pt):
    rules = pt.get_verification_rules()
    rule_ids = [r.id for r in rules]
    # Core rules inherited
    assert "file-size-limit" in rule_ids
    # Web rules inherited
    assert "i18n-completeness" in rule_ids
    # Mobile rules added
    assert "capacitor-config" in rule_ids

def test_template_exists(pt):
    tdir = pt.get_template_dir("capacitor-nextjs")
    assert tdir is not None
    assert tdir.is_dir()

def test_web_template_still_accessible(pt):
    """Inherited template from web module is available via MRO."""
    tdir = pt.get_template_dir("nextjs")
    assert tdir is not None
    assert tdir.is_dir()
```

## Checklist: New Module

- [ ] Create `modules/<name>/set_project_<name>/__init__.py`
- [ ] Create `project_type.py` with class inheriting from `CoreProfile` (or subclass)
- [ ] Implement `info` property and `get_templates()`
- [ ] Create at least one template directory with `manifest.yaml`
- [ ] Create `pyproject.toml` with entry point
- [ ] Add parent module to dependencies if inheriting
- [ ] Write tests (`test_project_type.py`, `test_integration.py`)
- [ ] `pip install -e modules/<name>`
- [ ] Verify: `set-project init --project-type <name> --template <variant>`
