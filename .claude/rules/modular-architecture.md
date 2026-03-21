# Modular Architecture

set-core is a **framework** with a plugin system. The architecture has three layers:

## Layer 1: Core (`lib/set_orch/`)
Abstract orchestration engine. NEVER contains project-specific logic (web patterns, framework detection, etc.).

- `profile_types.py` — `ProjectType` ABC + dataclasses (`VerificationRule`, `OrchestrationDirective`, etc.)
- `profile_loader.py` — `NullProfile`, `CoreProfile` (universal rules), profile resolution chain
- Profile resolution: entry_points → direct import → built-in `modules/` → NullProfile

## Layer 2: Built-in Modules (`modules/`)
Project-type plugins that ship with set-core. Each is a standalone pip-installable package with its own `pyproject.toml`.

- `modules/web/` — `WebProjectType(CoreProfile)` — web/Next.js rules, Playwright detection, Prisma patterns
- `modules/example/` — `DungeonProjectType(CoreProfile)` — reference implementation

## Layer 3: External Plugins (separate repos)
Private or community plugins. Registered via `entry_points` in their own `pyproject.toml`. Entry_points take priority over built-in modules.

Example: `set-project-fintech` with IDOR rules, PCI compliance checks — lives in a separate repo with its own `openspec/`.

## Rules

1. **Never hardcode project-specific patterns in `lib/set_orch/`.** Web-specific rules (IDOR checks, auth middleware, Playwright detection, package.json parsing) belong in `modules/web/`. set-core core provides the abstraction layer (profiles, hooks, config), not concrete implementations.

2. **Profile system is the extension point.** Project-specific behavior flows through `profile.detect_test_command()`, `profile.detect_e2e_command()`, `profile.get_forbidden_patterns()`, etc. When adding new project-aware behavior, add it to the `ProjectType` ABC in `profile_types.py` first, then implement in the appropriate module.

3. **CoreProfile provides universal rules only.** The 3 verification rules (file-size, no-secrets, todo-tracking) and 4 orchestration directives (dep install, lockfile serialize, config review) apply to ALL projects regardless of tech stack. If a rule is specific to a framework → module.

4. **Modules inherit from CoreProfile.** `WebProjectType(CoreProfile)`, not `ProjectType` directly. This ensures universal rules are always included. External plugins should also inherit from `CoreProfile`.

5. **Each module keeps its own `pyproject.toml`.** This allows standalone installation (`pip install -e modules/web`) and forking. Module-specific dependencies go in the module's pyproject.toml, not set-core's.

6. **OpenSpec lives only in set-core root.** Modules do NOT have their own `openspec/` directory. A single change can touch both `lib/set_orch/` and `modules/web/` — this is expected and correct.

7. **Backwards compatibility shim.** `lib/set_project_base/` re-exports from the new locations so that `from set_project_base import BaseProjectType` still works for external plugins during transition.

8. **Changes to set-core deploy to consumer projects via `set-project init`.** Any file under `.claude/` that set-core generates must be deployable.
