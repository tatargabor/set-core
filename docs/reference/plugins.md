[< Back to INDEX](../INDEX.md)

# Plugins and Project Types

How to create project type plugins, register custom gates, and use the template system.

## Overview

set-core is extensible through project type plugins. A plugin provides framework-specific behavior -- test detection, forbidden patterns, build commands, verification rules -- without modifying the core engine.

## Creating a Project Type

A project type is a Python class inheriting from `CoreProfile`:

```python
from set_orch.profile_loader import CoreProfile
from set_orch.profile_types import VerificationRule, OrchestrationDirective

class FintechProjectType(CoreProfile):
    """Project type for fintech applications."""

    def detect_test_command(self, project_path: str) -> str:
        if (Path(project_path) / "jest.config.ts").exists():
            return "pnpm test"
        return ""

    def detect_e2e_command(self, project_path: str) -> str:
        if (Path(project_path) / "playwright.config.ts").exists():
            return "pnpm test:e2e"
        return ""

    def get_forbidden_patterns(self) -> list[dict]:
        patterns = super().get_forbidden_patterns()
        patterns.extend([
            {"pattern": r"customer_id.*=.*params\.", "message": "IDOR: use session user ID"},
            {"pattern": r"eval\(", "message": "No eval() in financial code"},
        ])
        return patterns

    def get_verification_rules(self) -> list[VerificationRule]:
        rules = super().get_verification_rules()
        rules.append(VerificationRule(
            name="pci-no-card-numbers",
            description="No credit card numbers in source",
            pattern=r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
            severity="critical",
        ))
        return rules

    def post_merge_install(self, project_path: str) -> list[str]:
        return ["pnpm install", "pnpm db:generate"]
```

## Registering a Plugin

### Option 1: Entry Points (recommended for external plugins)

In your plugin's `pyproject.toml`:

```toml
[project]
name = "set-project-fintech"
version = "0.1.0"

[project.entry-points."set_core.project_types"]
fintech = "my_plugin.project_type:FintechProjectType"
```

Install with `pip install -e .` and set `project_type: fintech` in `.claude/project-type.yaml`.

### Option 2: Built-in Module (ships with set-core)

Place the module under `modules/<name>/` with its own `pyproject.toml`:

```
modules/fintech/
├── pyproject.toml
├── set_project_fintech/
│   ├── __init__.py
│   └── project_type.py
└── templates/
    └── fintech/
        └── rules/
            └── pci-compliance.md
```

Install with `pip install -e modules/fintech`.

### Resolution Priority

1. **Entry points** -- external plugins installed via pip (highest)
2. **Direct import** -- explicit class path in config
3. **Built-in modules** -- `modules/` directory
4. **NullProfile** -- fallback (no-op, no gates)

## Registering Custom Gates

Gates are driven by the profile. The engine calls profile methods during the merge pipeline:

```
execute_merge_queue()
  for each change:
    1. profile.post_merge_install()     -> dep install gate
    2. config.build_command             -> build gate
    3. config.test_command              -> test gate
    4. profile.detect_e2e_command()     -> e2e gate
    5. code review (if review_model)    -> review gate
    6. git merge --ff-only              -> merge
    7. profile.post_merge_install()     -> post-merge cleanup
```

To add a custom gate, extend the appropriate profile method:

```python
def get_verification_rules(self) -> list[VerificationRule]:
    rules = super().get_verification_rules()
    rules.append(VerificationRule(
        name="security-scan",
        description="Run security scanner before merge",
        command="pnpm audit --production",
        severity="critical",
    ))
    return rules
```

## Template System

Plugins can ship template files deployed to consumer projects via `set-project init`.

### Template Locations

| Source | Deployed To | Priority |
|--------|-------------|----------|
| `templates/core/rules/` | `.claude/rules/` | 1 (lowest) |
| `modules/<type>/templates/<template>/` | Various paths | 2 |
| `<project>/.claude/project-templates/` | Various paths | 3 (highest) |

### Path Mapping

- `rules/my-rule.md` -> `.claude/rules/my-rule.md`
- `src/lib/prisma.ts` -> `src/lib/prisma.ts` (project root)
- `framework-rules/web/custom.md` -> `.claude/rules/web/set-custom.md`

### Project-Level Overrides

Projects can override any template by placing files in `.claude/project-templates/`:

```
my-project/.claude/project-templates/
├── rules/
│   └── pci-compliance.md       # project-specific rule
└── src/lib/prisma.ts           # custom Prisma client
```

On `set-project init`, these override module defaults:

```
[project-template] Overwritten: src/lib/prisma.ts
```

### When to Use Which

| Use Case | Location |
|----------|----------|
| All projects of a type | Module template (`modules/<type>/templates/`) |
| Your project only | `.claude/project-templates/` |
| All projects regardless of type | Core template (`templates/core/rules/`) |

## Plugin Conventions

1. **Inherit from `CoreProfile`**, not `ProjectType` directly -- ensures universal rules are included
2. **Keep your own `pyproject.toml`** -- allows standalone `pip install`
3. **Module-specific deps in module's pyproject.toml** -- not in set-core root
4. **OpenSpec lives only in set-core root** -- modules do not have their own `openspec/`
5. **A single change can touch both `lib/set_orch/` and `modules/`** -- this is expected

## Plugin Ecosystem

| Name | Status | Description |
|------|--------|-------------|
| `modules/web` | Stable | Next.js, Playwright, Prisma |
| `modules/example` | Reference | Dungeon Builder demo |
| `set-project-example` | Published | GitHub reference plugin |

To list a community plugin, submit a PR to this doc.

---

<!-- Spec cross-references:
  - openspec/specs/profile-system.md (ProjectType ABC, profile chain)
  - openspec/specs/modular-architecture.md (3-layer model, module conventions)
  - openspec/specs/orchestration-engine.md (gate pipeline, merge queue)
-->

*See also: [Architecture](architecture.md) · [Configuration](configuration.md) · [CLI Reference](cli.md)*

<!-- specs: profile-loader, gate-registry, monorepo-modules -->
