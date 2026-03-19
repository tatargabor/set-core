# Modular Architecture

set-core is a **framework** — project-specific logic lives in separate packages (set-project-web, set-project-base, etc.), not in set-core core.

## Rules

1. **Never hardcode project-specific patterns in set-core core.** Web-specific rules (IDOR checks, auth middleware, API patterns) belong in `set-project-web`. Python-specific patterns belong in a Python profile package. set-core provides the abstraction layer (profiles, hooks, config), not the concrete implementations.

2. **Profile system is the extension point.** Project-specific behavior flows through `profile.detect_test_command()`, `profile.security_rules_paths()`, `profile.generated_file_patterns()`, etc. When adding new project-aware behavior, add it to the profile interface first, then implement in the appropriate set-project-* package.

3. **Config resolution order matters.** Always use `config.auto_detect_test_command()` (profile → legacy fallback), not inline PM detection. The config module handles the resolution chain.

4. **Changes to set-core deploy to consumer projects via `set-project init`.** Any file under `.claude/` that set-core generates must be deployable. Test changes against at least one consumer project.

5. **OpenSpec artifacts must be generic.** No project-specific names, paths, or metrics in proposals/designs/tasks/specs. Generalize findings before writing artifacts.
