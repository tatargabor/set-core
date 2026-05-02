## ADDED Requirements

### Requirement: ProjectType exposes test framework detection hook

The `ProjectType` ABC in `lib/set_orch/profile_types.py` SHALL expose a `detect_test_framework(project_dir: Path) -> Optional[str]` method. CoreProfile SHALL return `None` (no detection). WebProjectType SHALL return one of `"vitest" | "jest" | "mocha"` based on the presence of the corresponding config file (`vitest.config.*`, `jest.config.*`, `.mocharc.*`) in `project_dir`, or `None` if none match.

#### Scenario: core profile returns None for test framework
- **WHEN** `CoreProfile().detect_test_framework(Path("/some/dir"))` is called for any directory layout
- **THEN** the result is `None`

#### Scenario: web profile detects vitest
- **WHEN** the project directory contains `vitest.config.ts` and `WebProjectType().detect_test_framework(project_dir)` is called
- **THEN** the result is `"vitest"`

#### Scenario: web profile detects jest
- **WHEN** the project directory contains `jest.config.js` (and no vitest config) and `WebProjectType().detect_test_framework(project_dir)` is called
- **THEN** the result is `"jest"`

#### Scenario: web profile returns None when no config found
- **WHEN** the project directory has neither vitest, jest, nor mocha config files
- **THEN** `WebProjectType().detect_test_framework(project_dir)` returns `None`

### Requirement: ProjectType exposes schema provider detection hook

The `ProjectType` ABC SHALL expose a `detect_schema_provider(project_dir: Path) -> Optional[str]` method. CoreProfile SHALL return `None`. WebProjectType SHALL return `"prisma"` if `prisma/schema.prisma` exists under `project_dir`, otherwise `None`.

#### Scenario: core profile returns None for schema provider
- **WHEN** `CoreProfile().detect_schema_provider(any_dir)` is called
- **THEN** the result is `None`

#### Scenario: web profile detects prisma
- **WHEN** `prisma/schema.prisma` exists in `project_dir` and `WebProjectType().detect_schema_provider(project_dir)` is called
- **THEN** the result is `"prisma"`

#### Scenario: web profile returns None when no schema file
- **WHEN** `prisma/schema.prisma` does not exist
- **THEN** `WebProjectType().detect_schema_provider(project_dir)` returns `None`

### Requirement: ProjectType exposes design globals path hook

The `ProjectType` ABC SHALL expose a `get_design_globals_path(project_dir: Path) -> Optional[Path]` method. CoreProfile SHALL return `None`. WebProjectType SHALL return `project_dir / "v0-export/app/globals.css"` if that file exists, otherwise `None`.

#### Scenario: core profile returns None for design globals
- **WHEN** `CoreProfile().get_design_globals_path(any_dir)` is called
- **THEN** the result is `None`

#### Scenario: web profile returns v0-export globals path when present
- **WHEN** `project_dir/v0-export/app/globals.css` exists
- **THEN** `WebProjectType().get_design_globals_path(project_dir)` returns the absolute Path to that file

#### Scenario: web profile returns None when v0-export globals missing
- **WHEN** `project_dir/v0-export/app/globals.css` does not exist
- **THEN** `WebProjectType().get_design_globals_path(project_dir)` returns `None`

### Requirement: planner.py uses profile hooks instead of hardcoded detection

`lib/set_orch/planner.py` SHALL NOT contain hardcoded references to `vitest`, `jest`, `mocha`, `prisma`, or `v0-export` as path/filename literals after this change. The previous hardcoded detection logic at lines 241-242, 268, 338, 422, and 2802 SHALL be replaced by calls to `profile.detect_test_framework(...)`, `profile.detect_schema_provider(...)`, and `profile.get_design_globals_path(...)` respectively.

#### Scenario: grep for web tokens in planner.py returns no matches in detection paths
- **WHEN** the codebase is scanned with `grep -nE "vitest|prisma|v0-export|mocha\\.config|jest\\.config" lib/set_orch/planner.py`
- **THEN** zero matches occur in production code paths (comments and docstrings explaining the layer rule are permitted)

#### Scenario: planner test framework detection uses profile hook
- **WHEN** the planner runs against a web project with vitest configured
- **THEN** the planner consults `profile.detect_test_framework(project_dir)` and receives `"vitest"`

#### Scenario: planner schema detection uses profile hook
- **WHEN** the planner runs against a web project with `prisma/schema.prisma` present
- **THEN** the planner consults `profile.detect_schema_provider(project_dir)` and receives `"prisma"`

#### Scenario: planner design globals lookup uses profile hook
- **WHEN** the planner needs the design tokens CSS file path
- **THEN** the planner calls `profile.get_design_globals_path(project_dir)` rather than constructing `Path("v0-export") / "app" / "globals.css"` directly
