## Architecture: Profile-Engine Bridge

### Current State

```
wt-project-base          wt-project-web           wt-tools engine
(Python pip pkg)          (Python pip pkg)          (Python + bash)

ProjectType ABC ────────► WebProjectType            templates.py ──► hardcoded web
  info()                    11 verif rules           dispatcher.py ► hardcoded PM
  get_templates()           7 orch directives        planner.py ──► hardcoded test
  get_verification_rules()  13 rule .md files        verifier.py ─► hardcoded rules
  get_orch_directives()                              merger.py ───► hardcoded install
                                                     builder.py ──► hardcoded build
ProjectTypeResolver                                  config.py ───► hardcoded PM
  resolve_rules()          ┌─ NO CONNECTION ─┐       milestone.py ► hardcoded install
  resolve_directives()     │  between these  │       bin/wt-merge ► hardcoded patterns
                           └─────────────────┘       bin/wt-new ──► hardcoded install

deploy.py ──────────────── wt-project init ─────►  deploys templates to consumer
  copies rule files           works correctly         .claude/rules/, project-knowledge
```

### Target State

```
wt-project-base          wt-project-web           wt-tools engine
(Python pip pkg)          (Python pip pkg)          (Python + bash)

ProjectType ABC           WebProjectType            profile_loader.py
  info()                    all existing +            load_profile(project_path)
  get_templates()           NEW METHODS:               ↓
  get_verif_rules()         ┌───────────────┐    ┌──────────────────────┐
  get_orch_directives()     │planning_rules │───►│ templates.py         │
  NEW:                      │security_rules │───►│ verifier.py          │
  planning_rules()          │security_checkl│───►│ templates.py proposal│
  security_rules_paths()    │gen_file_pats  │───►│ merger.py, wt-merge  │
  security_checklist()      │detect_pm()    │───►│ ALL PM consumers (7) │
  generated_file_pats()     │detect_test()  │───►│ planner.py, config   │
  detect_pm()               │detect_build() │───►│ builder.py           │
  detect_test_cmd()         │detect_dev_srv │───►│ config.py, milestone │
  detect_build_cmd()        │bootstrap_wt() │───►│ dispatcher.py        │
  detect_dev_server()       │post_merge()   │───►│ merger.py            │
  bootstrap_worktree()      │ignore_pats()  │───►│ digest.py            │
  post_merge_install()      └───────────────┘    └──────────────────────┘
  ignore_patterns()
```

---

## Component 1: Extended ProjectType ABC

**File: `wt-project-base/wt_project_base/base.py`**

New methods on the ABC with default (no-op) implementations so existing subclasses don't break:

```python
class ProjectType(ABC):
    # --- EXISTING (unchanged) ---
    @property
    @abstractmethod
    def info(self) -> ProjectTypeInfo: ...

    @abstractmethod
    def get_templates(self) -> List[TemplateInfo]: ...

    @abstractmethod
    def get_verification_rules(self) -> List[VerificationRule]: ...

    @abstractmethod
    def get_orchestration_directives(self) -> List[OrchestrationDirective]: ...

    # --- NEW (with defaults for backward compat) ---

    def planning_rules(self) -> str:
        """Quality patterns for the decompose/planning prompt.

        Returns a text block that gets appended to _PLANNING_RULES in the
        orchestration planner. Should include security patterns, testing
        conventions, and architecture constraints specific to this project type.

        Default: empty string (no additional planning rules).
        """
        return ""

    def security_rules_paths(self, project_path: str) -> List[Path]:
        """Paths to security rule files for review retry context.

        These files get loaded and injected into the retry prompt when
        code review finds CRITICAL issues.

        Default: empty list (falls back to legacy rules/web/ search).
        """
        return []

    def generated_file_patterns(self) -> List[str]:
        """Glob patterns for generated files that can be auto-resolved during merge.

        These files get 'ours' strategy during merge conflicts.
        Examples: "*.tsbuildinfo", "pnpm-lock.yaml", ".next/**"

        Default: empty list (only core patterns like .claude/reflection.md).
        """
        return []

    def lockfile_pm_map(self) -> List[tuple[str, str]]:
        """Mapping of lockfile names to package manager commands.

        Used for PM detection, bootstrap, post-merge install.
        Example: [("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn")]

        Default: empty list (no PM detection).
        """
        return []

    def detect_package_manager(self, project_path: str) -> Optional[str]:
        """Detect the package manager for this project.

        Default implementation uses lockfile_pm_map().
        Override for custom detection (e.g., pyproject.toml → poetry vs pip).
        """
        d = Path(project_path)
        for lockfile, pm in self.lockfile_pm_map():
            if (d / lockfile).is_file():
                return pm
        return None

    def detect_test_command(self, project_path: str) -> Optional[str]:
        """Detect the test command for this project.

        Default: None (no auto-detection, use config directive).
        """
        return None

    def detect_build_command(self, project_path: str) -> Optional[str]:
        """Detect the build command for this project.

        Default: None (no auto-detection, use config directive).
        """
        return None

    def bootstrap_worktree(self, project_path: str, wt_path: str) -> bool:
        """Install dependencies in a new worktree.

        Called after worktree creation. Should install deps but not modify source.
        Default: no-op, returns True.
        """
        return True

    def post_merge_install(self, project_path: str) -> bool:
        """Install dependencies after a merge.

        Called after successful merge on main branch.
        Default: no-op, returns True.
        """
        return True

    def detect_dev_server(self, project_path: str) -> Optional[str]:
        """Detect the dev server start command for this project.

        Framework-specific detection (e.g., package.json scripts.dev for web,
        manage.py runserver for Django). Generic cascade (docker-compose,
        Makefile) stays in config.py.

        Default: None (fall back to generic cascade in config.py).
        """
        return None

    def security_checklist(self) -> str:
        """Security checklist items for proposal.md template.

        Returns markdown checklist lines that get injected into the
        ## Security Checklist section of render_proposal().

        Default: empty string (generic checklist stays in template).
        """
        return ""

    def ignore_patterns(self) -> List[str]:
        """Patterns to ignore during digest/codemap generation.

        Examples: ["node_modules", ".venv", "target", "__pycache__"]
        Default: empty list.
        """
        return []
```

**Backward compatibility**: All new methods have default implementations → existing `BaseProjectType` and `WebProjectType` continue to work unchanged until they implement the new methods.

**PM detection duplication audit** — 7 independent implementations found (not 5 as initially estimated):

| # | File | Function | Lines |
|---|------|----------|-------|
| 1 | `dispatcher.py` | `LOCKFILE_PM_MAP` constant + `_detect_package_manager()` | L54-60, L212-219 |
| 2 | `builder.py` | `_detect_pm()` | L190-203 |
| 3 | `config.py` | `detect_package_manager()` | L603-619 |
| 4 | `config.py` | `auto_detect_test_command()` inline PM detection | L577-583 |
| 5 | `config.py` | `install_dependencies()` via `detect_package_manager()` | L622-646 |
| 6 | `planner.py` | `_auto_detect_test_command()` inline PM detection | L178-187 |
| 7 | `milestone.py` | `_install_dependencies()` + `_detect_dev_server()` | L369-381, L354-362 |

---

## Component 2: WebProjectType New Methods

**File: `wt-project-web/wt_project_web/project_type.py`**

```python
class WebProjectType(BaseProjectType):
    # --- EXISTING (unchanged) ---
    # info, get_templates, get_verification_rules, get_orchestration_directives

    # --- NEW ---

    def planning_rules(self) -> str:
        """Web-specific planning rules for decompose prompt."""
        # Read from a bundled file in the package
        rules_file = Path(__file__).parent / "planning_rules.txt"
        if rules_file.is_file():
            return rules_file.read_text()
        return ""

    def security_rules_paths(self, project_path: str) -> List[Path]:
        """Point to deployed security rule files in the project."""
        rules_dir = Path(project_path) / ".claude" / "rules"
        paths = []
        for pattern in ("security*.md", "auth*.md", "api-design*.md"):
            paths.extend(rules_dir.glob(pattern))
        # Also check template rules (fallback if not deployed)
        if not paths:
            template_rules = Path(__file__).parent / "templates" / "nextjs" / "rules"
            for name in ("security.md", "auth-conventions.md"):
                p = template_rules / name
                if p.is_file():
                    paths.append(p)
        return paths

    def generated_file_patterns(self) -> List[str]:
        return [
            "tsconfig.tsbuildinfo", "*.tsbuildinfo",
            "next-env.d.ts",
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            ".next/**", "dist/**", "build/**",
        ]

    def lockfile_pm_map(self) -> List[tuple[str, str]]:
        return [
            ("pnpm-lock.yaml", "pnpm"),
            ("yarn.lock", "yarn"),
            ("bun.lockb", "bun"),
            ("bun.lock", "bun"),
            ("package-lock.json", "npm"),
        ]

    def detect_test_command(self, project_path: str) -> Optional[str]:
        """Detect test command from package.json scripts."""
        d = Path(project_path)
        pkg_json = d / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        try:
            data = json.loads(pkg_json.read_text())
            scripts = data.get("scripts", {})
            for candidate in ("test", "test:unit", "test:ci"):
                if scripts.get(candidate):
                    return f"{pm} run {candidate}"
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def detect_build_command(self, project_path: str) -> Optional[str]:
        """Detect build command from package.json scripts."""
        d = Path(project_path)
        pkg_json = d / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        try:
            data = json.loads(pkg_json.read_text())
            scripts = data.get("scripts", {})
            for candidate in ("build:ci", "build"):
                if scripts.get(candidate):
                    return f"{pm} run {candidate}"
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def bootstrap_worktree(self, project_path: str, wt_path: str) -> bool:
        """Install npm dependencies in worktree."""
        pkg_json = Path(wt_path) / "package.json"
        node_modules = Path(wt_path) / "node_modules"
        if not pkg_json.is_file() or node_modules.is_dir():
            return True
        pm = self.detect_package_manager(wt_path)
        if not pm:
            return True
        # Try frozen first, fallback to unfrozen
        result = subprocess.run([pm, "install", "--frozen-lockfile"],
                                cwd=wt_path, capture_output=True, timeout=120)
        if result.returncode != 0:
            subprocess.run([pm, "install"], cwd=wt_path, capture_output=True, timeout=120)
        return True

    def post_merge_install(self, project_path: str) -> bool:
        """Install deps after merge if package.json changed."""
        pm = self.detect_package_manager(project_path)
        if not pm:
            return True
        result = subprocess.run([pm, "install"],
                                cwd=project_path, capture_output=True, timeout=300)
        return result.returncode == 0

    def detect_dev_server(self, project_path: str) -> Optional[str]:
        """Detect dev server from package.json scripts.dev."""
        d = Path(project_path)
        pkg_json = d / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        try:
            data = json.loads(pkg_json.read_text())
            if data.get("scripts", {}).get("dev"):
                return f"{pm} run dev"
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def security_checklist(self) -> str:
        """Web-specific security checklist for proposal.md."""
        return """- [ ] Data mutations by client-provided ID include ownership/authorization check
- [ ] Protected resources enforce auth before the handler runs (middleware, not handler-level)
- [ ] Public-facing inputs are validated at the boundary (type, range, size)
- [ ] Multi-user queries are scoped by the owning entity
- [ ] No `dangerouslySetInnerHTML` or `v-html` with user-supplied content"""

    def ignore_patterns(self) -> List[str]:
        return ["node_modules", ".next", "dist", "build", ".turbo"]
```

---

## Component 3: Profile Loader (Bridge)

**File: `wt-tools/lib/wt_orch/profile_loader.py`** (NEW)

This is the central bridge — engine code calls this to get the active profile.

```python
"""Load project-type profile for orchestration engine integration.

Reads wt/plugins/project-type.yaml to find the active project type,
then loads it via Python entry_points (same mechanism as wt-project init).

Provides a singleton-like cache so profile is loaded once per engine session.
Falls back to a NullProfile when no project type is configured or the
plugin package is not installed.
"""

import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

# Cache: loaded once per process
_cached_profile: Optional["ProjectType"] = None
_cache_loaded: bool = False


class NullProfile:
    """Fallback profile when no project type plugin is available.

    All methods return empty/no-op values, so engine falls back
    to its legacy hardcoded behavior.
    """
    def planning_rules(self) -> str: return ""
    def security_rules_paths(self, p: str) -> list: return []
    def security_checklist(self) -> str: return ""
    def generated_file_patterns(self) -> list: return []
    def lockfile_pm_map(self) -> list: return []
    def detect_package_manager(self, p: str) -> Optional[str]: return None
    def detect_test_command(self, p: str) -> Optional[str]: return None
    def detect_build_command(self, p: str) -> Optional[str]: return None
    def detect_dev_server(self, p: str) -> Optional[str]: return None
    def bootstrap_worktree(self, pp: str, wp: str) -> bool: return True
    def post_merge_install(self, p: str) -> bool: return True
    def ignore_patterns(self) -> list: return []

    @property
    def info(self):
        from dataclasses import dataclass
        @dataclass
        class _Info:
            name: str = "null"
            version: str = "0.0.0"
            description: str = "No project type configured"
        return _Info()


def load_profile(project_path: str = ".") -> "ProjectType":
    """Load the active project type profile.

    Resolution:
    1. Read wt/plugins/project-type.yaml → get type name
    2. Load via importlib.metadata entry_points(group='wt_tools.project_types')
    3. Instantiate and return
    4. On any failure → return NullProfile (engine falls back to legacy)

    Default project_path="." works with the engine's CWD convention
    (sentinel always runs from project root). Resolved to absolute path
    for stable cache key.
    """
    global _cached_profile, _cache_loaded

    if _cache_loaded:
        return _cached_profile

    _cache_loaded = True
    project_path = str(Path(project_path).resolve())

    pt_file = Path(project_path) / "wt" / "plugins" / "project-type.yaml"
    if not pt_file.is_file():
        logger.debug("No project-type.yaml found, using NullProfile")
        _cached_profile = NullProfile()
        return _cached_profile

    try:
        import yaml
        with open(pt_file) as f:
            config = yaml.safe_load(f)
        type_name = config.get("type", "")
    except Exception as e:
        logger.warning("Failed to read project-type.yaml: %s", e)
        _cached_profile = NullProfile()
        return _cached_profile

    if not type_name:
        _cached_profile = NullProfile()
        return _cached_profile

    # Load via entry_points (same mechanism as wt-project init)
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group='wt_tools.project_types')
    except TypeError:
        from importlib.metadata import entry_points
        eps = entry_points().get('wt_tools.project_types', [])

    for ep in eps:
        if ep.name == type_name:
            try:
                cls = ep.load()
                _cached_profile = cls()
                logger.info("Loaded profile: %s v%s",
                           _cached_profile.info.name,
                           _cached_profile.info.version)
                return _cached_profile
            except Exception as e:
                logger.warning("Failed to load profile '%s': %s", type_name, e)
                break

    logger.info("Profile '%s' not found in entry_points, using NullProfile", type_name)
    _cached_profile = NullProfile()
    return _cached_profile


def reset_cache():
    """Reset the profile cache (for testing)."""
    global _cached_profile, _cache_loaded
    _cached_profile = None
    _cache_loaded = False
```

---

## Component 4: Engine Integration Points (wt-tools)

### 4a. `templates.py` — Planning Rules

**Current** (L244-344): `_PLANNING_RULES` hardcodes everything in one string.

**After**: Split into core + profile.

**Content analysis — what stays in core, what moves to profile:**

| Lines | Content | Classification |
|-------|---------|----------------|
| L244-255 | Size, naming, deps, complexity constraints | CORE (generic) |
| L256-261 | Security design patterns (IDOR, auth, validation) | CORE — concepts are framework-agnostic; profile *supplements* with framework-specific patterns |
| L262-263 | Test infra setup requirement | CORE (generic) |
| L264-293 | Sub-domain chaining, dep ordering, shared resources | CORE (generic) |
| L294 | Test-per-change requirement | CORE (generic) |
| **L295-317** | **Playwright E2E test planning** (PW_PORT, cold-visit, jest config, prisma) | **WEB-SPECIFIC → moves to profile** |
| L319-326 | Phase assignment | CORE (generic) |
| L328-337 | Model selection, manual tasks | CORE (generic) |
| L339-344 | Output size constraint | CORE (generic) |

Only ~23 lines (L295-317) are web-specific. The security block (L256-261) stays in core because the concepts (IDOR prevention, auth guards, input validation, data scoping) are universal — the profile adds framework-specific implementation patterns (Next.js middleware, Prisma where clause, etc.).

```python
# Core rules (framework-agnostic) — everything EXCEPT L295-317
_PLANNING_RULES_CORE = """Rules:
- Each change should be completable in 1 Ralph loop session
...
Security design patterns — include these constraints in scope when the change
handles user data or access control:
- Authorization on mutations: ...  (stays — universal concept)
- Access control: ...              (stays — universal concept)
- Input validation: ...            (stays — universal concept)
- Data scoping: ...                (stays — universal concept)
...
Test-per-change requirement: ...
Phase assignment: ...
Model selection: ...
Manual tasks: ...
CRITICAL — Output size constraint: ...
"""
# NOTE: L295-317 (Playwright E2E test planning) removed from core.
# It moves to WebProjectType.planning_rules() in wt-project-web.

def _get_planning_rules(project_path: str) -> str:
    """Assemble planning rules from core + profile."""
    from .profile_loader import load_profile
    profile = load_profile(project_path)

    profile_rules = profile.planning_rules()
    if profile_rules:
        return _PLANNING_RULES_CORE + "\n\n" + profile_rules

    # Legacy fallback: if profile returns nothing, use old hardcoded rules
    return _PLANNING_RULES  # original full string with web patterns included
```

**CRITICAL constraint**: The legacy `_PLANNING_RULES` (with Playwright block) MUST be kept as fallback until Phase B completes (WebProjectType implements `planning_rules()` returning the Playwright block). Otherwise, removing L295-317 from core while the profile doesn't yet return them = **Playwright guidance disappears**. See Migration Strategy Phase B→C dependency.

### 4a-bis. `templates.py` — Proposal Security Checklist

**Current** (L68-74): `render_proposal()` hardcodes a web-specific security checklist.

**After**: Profile-first with generic fallback.

```python
_GENERIC_SECURITY_CHECKLIST = """- [ ] Data mutations by client-provided ID include ownership/authorization check
- [ ] Protected resources enforce auth before the handler runs
- [ ] Public-facing inputs are validated at the boundary (type, range, size)
- [ ] Multi-user queries are scoped by the owning entity"""

def render_proposal(change_name, scope, roadmap_item, ...):
    from .profile_loader import load_profile
    profile = load_profile(project_path)

    checklist = profile.security_checklist()
    if not checklist:
        checklist = _GENERIC_SECURITY_CHECKLIST

    parts = [f"""## Why
...
## Security Checklist

Before completing implementation, verify where applicable:
{checklist}
...
"""]
```

### 4b. `verifier.py` — Security Rules for Retry

**Current** (L136-174): `_load_web_security_rules()` hardcodes `rules/web/` path.

**After**: Try profile first, fall back to legacy.

```python
def _load_security_rules(wt_path: str, project_path: str) -> str:
    """Load security rules for review retry context.

    Resolution: profile.security_rules_paths() → legacy web/ search.
    """
    from .profile_loader import load_profile
    profile = load_profile(project_path)

    rule_paths = profile.security_rules_paths(wt_path)
    if rule_paths:
        return _read_rule_files(rule_paths)

    # Legacy fallback
    return _load_web_security_rules(wt_path)
```

### 4c. `dispatcher.py` — PM Detection + Bootstrap

**Current**: `LOCKFILE_PM_MAP` constant (L54-60), `_detect_package_manager()` (L212-219), `bootstrap_worktree()` (L173-209).

**After**: Profile-first with legacy fallback.

```python
def _detect_package_manager(wt_path: str, project_path: str = "") -> str:
    """Detect PM — profile first, then legacy."""
    if project_path:
        from .profile_loader import load_profile
        profile = load_profile(project_path)
        pm = profile.detect_package_manager(wt_path)
        if pm:
            return pm
    # Legacy fallback
    for lockfile, pm in LOCKFILE_PM_MAP:
        if os.path.isfile(os.path.join(wt_path, lockfile)):
            return pm
    return ""


def bootstrap_worktree(project_path: str, wt_path: str) -> int:
    """Bootstrap worktree — env files (core) + deps (profile)."""
    # Core: copy .env files (always)
    copied = _copy_env_files(project_path, wt_path)

    # Profile: install deps
    from .profile_loader import load_profile
    profile = load_profile(project_path)
    profile.bootstrap_worktree(project_path, wt_path)

    return copied
```

### 4d. `merger.py` — Post-Merge Install

**Current** (L561-584): `_post_merge_deps_install()` hardcodes pnpm/yarn/npm.

**After**:

```python
def _post_merge_deps_install(project_path: str) -> None:
    """Post-merge dependency install — profile first, then legacy."""
    from .profile_loader import load_profile
    profile = load_profile(project_path)

    if not isinstance(profile, NullProfile):
        profile.post_merge_install(project_path)
        return

    # Legacy fallback (current code)
    ...
```

### 4e. `builder.py` — Build Command Detection

**Current** (L190-225): `_detect_pm()` and `_detect_build_cmd()` hardcoded.

**After**:

```python
def _detect_build_cmd(project_path: str) -> str:
    """Detect build command — profile first, then legacy."""
    from .profile_loader import load_profile
    profile = load_profile(project_path)

    cmd = profile.detect_build_command(project_path)
    if cmd:
        return cmd

    # Legacy fallback
    ...
```

### 4f. `config.py` — Unified PM + Test Detection

**Current** (L560-619): `auto_detect_test_command()`, `detect_package_manager()` duplicated.

**After**: Delegate to profile, remove duplication.

```python
def auto_detect_test_command(directory: str = ".") -> str:
    """Auto-detect test command — profile first, then legacy."""
    from .profile_loader import load_profile
    profile = load_profile(directory)

    cmd = profile.detect_test_command(directory)
    if cmd:
        return cmd

    # Legacy fallback (current code)
    ...
```

### 4g. `digest.py` — Ignore Patterns

**Current** (L29): Hardcoded `node_modules`.

**After**: Merge core + profile patterns.

```python
_CORE_IGNORE_PATTERNS = {".git", ".claude", ".wt-tools", "__pycache__"}

def _get_ignore_patterns(project_path: str) -> set:
    from .profile_loader import load_profile
    profile = load_profile(project_path)
    return _CORE_IGNORE_PATTERNS | set(profile.ignore_patterns())
```

### 4h. `bin/wt-merge` — Generated File Patterns

**Current** (L47-59): Hardcoded `GENERATED_FILE_PATTERNS` bash array.

**After**: Read from profile config file written at init time.

```bash
# Read profile-specific generated file patterns
_PROFILE_PATTERNS_FILE="$PROJECT_ROOT/wt/plugins/.generated-file-patterns"
if [[ -f "$_PROFILE_PATTERNS_FILE" ]]; then
    while IFS= read -r pat; do
        GENERATED_FILE_PATTERNS+=("$pat")
    done < "$_PROFILE_PATTERNS_FILE"
fi
```

The `.generated-file-patterns` file is written by `profile_loader.py` at engine startup or by `wt-project init`.

### 4i. `bin/wt-new` — Worktree Bootstrap

**Current** (L58-77): Hardcoded PM detection.

**After**: Call profile via Python.

```bash
# Profile-aware bootstrap (replaces hardcoded PM detection)
if command -v python3 &>/dev/null; then
    python3 -c "
from wt_orch.profile_loader import load_profile
profile = load_profile('$PROJECT_ROOT')
profile.bootstrap_worktree('$PROJECT_ROOT', '$WT_PATH')
" 2>/dev/null || {
        # Legacy fallback
        _legacy_bootstrap
    }
fi
```

### 4j. `planner.py` — Test Command Detection

**Current** (L164-195): `_auto_detect_test_command()` has its own inline PM detection (L178-187), independent of `config.py:detect_package_manager()`.

**After**: Delegate to profile, keep as internal fallback.

```python
def _auto_detect_test_command(project_dir: str) -> str:
    """Detect test command — profile first, then legacy."""
    from .profile_loader import load_profile
    profile = load_profile(project_dir)

    cmd = profile.detect_test_command(project_dir)
    if cmd:
        return cmd

    # Legacy fallback (current inline PM detection + package.json parsing)
    ...
```

### 4k. `milestone.py` — Dev Server + Dependency Install

**Current**: Two functions with independent PM detection:
- `_detect_dev_server()` (L342-366): Inline `pnpm-lock.yaml` check → `"pnpm run dev"`
- `_install_dependencies()` (L369-381): Inline lockfile → `pnpm/yarn/npm install`

**After**: Profile-first with legacy fallback.

```python
def _detect_dev_server(wt_path: str, explicit_cmd: str, state_file: str) -> str:
    """Detect dev server — explicit > directive > profile > legacy."""
    if explicit_cmd:
        return explicit_cmd
    # ... existing directive check from state_file ...

    # Profile-aware detection
    from .profile_loader import load_profile
    profile = load_profile(wt_path)
    cmd = profile.detect_dev_server(wt_path)
    if cmd:
        return cmd

    # Legacy fallback (current package.json inline detection)
    ...


def _install_dependencies(wt_path: str) -> bool:
    """Install deps — profile first, then legacy."""
    from .profile_loader import load_profile
    profile = load_profile(wt_path)

    if not isinstance(profile, NullProfile):
        return profile.bootstrap_worktree(wt_path, wt_path)

    # Legacy fallback (current lockfile-based detection)
    ...
```

### 4l. `config.py` — Dev Server + Dependency Install

**Current**:
- `detect_dev_server()` (L653-717): 6-step cascade with inline PM detection (L692)
- `install_dependencies()` (L622-646): Calls `detect_package_manager()` then `pm install`

**After**: Profile-first for the framework-specific step, generic cascade stays.

```python
def detect_dev_server(project_dir: str = ".", ...) -> str | None:
    """Auto-detect dev server command.

    Cascade: explicit override → directive → profile → generic fallback.
    """
    # 1-2: explicit overrides (unchanged)
    ...

    # 3: Profile-aware detection (replaces package.json inline check)
    from .profile_loader import load_profile
    profile = load_profile(project_dir)
    cmd = profile.detect_dev_server(project_dir)
    if cmd:
        return cmd

    # 4-6: Generic fallback (docker-compose, Makefile, manage.py — stays in core)
    ...


def install_dependencies(project_dir: str = ".") -> bool:
    """Install dependencies — profile first, then legacy."""
    from .profile_loader import load_profile
    profile = load_profile(project_dir)

    if not isinstance(profile, NullProfile):
        return profile.post_merge_install(project_dir)

    # Legacy fallback
    ...
```

---

## Component 5: Deployment Separation

### `lib/project/deploy.sh` changes

**Current** (L175-196): Deploys ALL `.claude/rules/` to ALL projects.

**After**: Only deploy core (non-web) rules. Web rules come from wt-project-web templates.

```bash
_deploy_skills() {
    ...
    # Deploy rules — ONLY core rules, NOT web/
    for rule_file in "$WT_TOOLS_ROOT"/.claude/rules/*.md; do
        [[ -f "$rule_file" ]] || continue
        local basename
        basename=$(basename "$rule_file")

        # Skip web-specific rules — these come from wt-project-web templates
        local dir_part
        dir_part=$(basename "$(dirname "$rule_file")")
        [[ "$dir_part" == "web" ]] && continue
        [[ "$dir_part" == "gui" ]] && continue

        # Deploy with wt- prefix
        cp "$rule_file" "$target_dir/.claude/rules/wt-$basename"
    done

    # Web rules are deployed by wt-project-web templates via deploy.py
    # They end up in .claude/rules/ (without wt- prefix)
}
```

---

## Migration Strategy

### Phase A: Non-Breaking Foundation
1. Add new methods to `ProjectType` ABC with defaults (including `detect_dev_server()`, `security_checklist()`) → `wt-project-base` v0.2.0
2. Create `profile_loader.py` in wt-tools with `NullProfile` fallback
3. **Result**: Nothing changes, everything still works via legacy paths

### Phase B: Implement Web Profile Methods
4. Implement new methods in `WebProjectType` (including `detect_dev_server()`, `security_checklist()`) → `wt-project-web` v0.2.0
5. Create `planning_rules.txt` in wt-project-web — **MUST include the Playwright E2E block** (L295-317 from current `_PLANNING_RULES`)
6. **Result**: Profile returns real values, but engine doesn't use them yet

### Phase C: Wire Engine to Profile (one module at a time)

**CRITICAL ORDERING**: Step 12 (`templates.py` split) MUST NOT happen before Phase B step 5 completes. If `_PLANNING_RULES_CORE` drops the Playwright block but `WebProjectType.planning_rules()` doesn't yet return it, Playwright E2E guidance disappears from planning. The other steps (7-11, 13-18) have no such ordering constraint.

**Safe-first order** — PM detection modules can proceed independently:

7. `config.py` — replace `detect_package_manager()`, `auto_detect_test_command()`, `install_dependencies()`, `detect_dev_server()` with profile calls
8. `dispatcher.py` — replace `bootstrap_worktree()` PM detection with profile
9. `builder.py` — replace `_detect_pm()` and `_detect_build_cmd()` with profile
10. `merger.py` — replace `_post_merge_deps_install()` and `_post_merge_build_check()` with profile
11. `milestone.py` — replace `_install_dependencies()` and `_detect_dev_server()` with profile
12. `planner.py` — replace `_auto_detect_test_command()` inline PM detection with profile
13. `templates.py` — split `_PLANNING_RULES` into core + profile (**BLOCKED on Phase B step 5**)
14. `templates.py` — replace `render_proposal()` hardcoded security checklist with profile
15. `verifier.py` — replace `_load_web_security_rules()` with profile-aware version
16. `digest.py` — merge profile ignore patterns

17. **Each step**: profile-first with legacy fallback, testable independently

### Phase D: Bash Integration
18. `bin/wt-merge` — read generated file patterns from profile config file
19. `bin/wt-new` — call profile bootstrap via Python
20. `deploy.sh` — stop deploying web rules (**BLOCKED on Phase C step 15**: verifier must use `profile.security_rules_paths()` before we remove `web/` deployment, otherwise review retry loses all security context)

### Phase E: Cleanup
21. Remove legacy hardcoded constants (`LOCKFILE_PM_MAP`, `GENERATED_FILE_PATTERNS` in dispatcher.py)
22. Remove duplicated `_detect_pm()` / PM detection functions (7 locations across config.py, builder.py, planner.py, milestone.py, dispatcher.py)
23. Remove `_PLANNING_RULES` legacy constant (replaced by `_PLANNING_RULES_CORE` + profile)
24. Mark remaining legacy fallback code with TODO comments for future removal

---

## Data Flow: Planning

```
User: wt-sentinel --spec docs/v1-minishop.md

sentinel → orchestrator → planner.py:run_planning_pipeline()
                              │
                              ├── profile_loader.load_profile(project_path)
                              │     ├── reads wt/plugins/project-type.yaml → "web"
                              │     └── loads WebProjectType via entry_points
                              │
                              ├── _get_planning_rules(project_path)
                              │     ├── _PLANNING_RULES_CORE (generic)
                              │     └── + profile.planning_rules() (web security + Playwright)
                              │
                              ├── profile.detect_test_command(project_path)
                              │     └── reads package.json → "pnpm run test"
                              │
                              └── render_planning_prompt(rules=combined_rules, ...)
                                    └── Claude decomposes spec into changes
                                          └── Each change scope INCLUDES security constraints
```

## Data Flow: Dispatch

```
orchestrator → dispatcher.py:dispatch_change(change, state)
                   │
                   ├── profile.detect_package_manager(project_path) → "pnpm"
                   ├── profile.bootstrap_worktree(project_path, wt_path)
                   │     └── pnpm install --frozen-lockfile
                   ├── _build_proposal_content(change, ...)
                   │     ├── render_proposal(..., project_path=...)
                   │     │     └── profile.security_checklist()
                   │     │           → web-specific items (XSS, middleware, etc.)
                   │     └── includes profile security context in proposal.md
                   └── wt-loop start ... --done test
```

## Data Flow: Verify + Retry

```
verifier.py:handle_change_done(change)
    │
    ├── VG-4: review_change() → finds CRITICAL
    │
    ├── _load_security_rules(wt_path, project_path)
    │     ├── profile.security_rules_paths(wt_path)
    │     │     └── [".claude/rules/security.md", ".claude/rules/auth-conventions.md"]
    │     └── _read_rule_files(paths) → rule content for retry prompt
    │
    └── retry_prompt = fixes + security_rules + instructions
          └── resume_change(change, retry_context=retry_prompt)
```

## Data Flow: Merge

```
merger.py:merge_change(change)
    │
    ├── wt-merge --no-push --llm-resolve
    │     └── GENERATED_FILE_PATTERNS from profile config file
    │
    ├── _post_merge_deps_install(project_path)
    │     └── profile.post_merge_install(project_path) → pnpm install
    │
    └── _post_merge_build_check(change)
          ├── profile.detect_build_command(project_path) → "pnpm run build"
          └── run build
```

---

## Critical Design Constraints

### Constraint 1: project_path passes through CWD, not explicit parameter

The orchestration engine does NOT pass `project_path` as an explicit parameter through
the call chain. Functions like `monitor_loop()`, `dispatch_ready_changes()`,
`_post_merge_deps_install()`, `_post_merge_build_check()` all assume CWD = project root.

**Solution**: `load_profile()` accepts `project_path="."` as default. Since the sentinel
always runs from the project root and never changes CWD, this works. The singleton cache
resolves the path on first call, so subsequent calls return the cached profile regardless
of what string was passed.

```python
def load_profile(project_path: str = ".") -> "ProjectType":
    """Load profile. Default project_path="." works with engine's CWD convention."""
    global _cached_profile, _cache_loaded
    if _cache_loaded:
        return _cached_profile
    # Resolve "." to absolute path for stable cache key
    project_path = str(Path(project_path).resolve())
    ...
```

This means **no engine-level refactoring is needed** — each integration point simply
calls `load_profile()` without arguments and gets the right profile.

### Constraint 2: Verifier pattern mismatch after rules migration

**Current verifier.py:148 patterns:**
```python
("web/*.md", "wt-web-*.md", "*web-security*.md", "*auth-middleware*.md")
```

**Current matching (with both wt-tools and template rules deployed):**

| Deployed file | Source | Matched? |
|---------------|--------|----------|
| `.claude/rules/web/wt-auth-middleware.md` | wt-tools deploy.sh | YES (`web/*.md`) |
| `.claude/rules/web/wt-security-patterns.md` | wt-tools deploy.sh | YES (`web/*.md`) |
| `.claude/rules/web/wt-api-design.md` | wt-tools deploy.sh | YES (`web/*.md`) |
| `.claude/rules/security.md` | wt-project-web template | NO |
| `.claude/rules/auth-conventions.md` | wt-project-web template | NO |
| `.claude/rules/testing-conventions.md` | wt-project-web template | NO |

**Impact**: If we remove wt-tools web rule deployment (Component 5) before updating the
verifier to use `profile.security_rules_paths()` (Component 4b), the verifier loses
access to ALL security rules for review retry context.

**Required ordering**: Component 4b (verifier integration) MUST be wired BEFORE
Component 5 (deploy.sh stops deploying web rules). Add to Phase C→D dependency:

```
Phase C step 15: verifier.py → profile.security_rules_paths()  ← FIRST
Phase D step 20: deploy.sh stops deploying web/                ← AFTER 15
```

The profile's `security_rules_paths()` returns the template-deployed paths directly
(`.claude/rules/security.md`, `.claude/rules/auth-conventions.md`), bypassing the
broken glob patterns entirely.

### Constraint 3: Install variants map to two profile methods

All dependency install operations collapse into two profile methods:

| Engine function | When | Profile method | Install flag |
|----------------|------|----------------|--------------|
| `dispatcher.bootstrap_worktree()` | New worktree created | `bootstrap_worktree()` | `--frozen-lockfile` |
| `merger._post_merge_deps_install()` | After merge on main | `post_merge_install()` | (no flag) |
| `milestone._install_dependencies()` | Milestone checkpoint | `post_merge_install()` | (no flag) |
| `config.install_dependencies()` | Manual CLI call | `post_merge_install()` | (no flag) |

`milestone._install_dependencies()` and `config.install_dependencies()` should both
delegate to `profile.post_merge_install()` (or call `profile.bootstrap_worktree()` if
in a worktree context). The frozen vs unfrozen distinction is the key differentiator.

---

## Testing Strategy

### Unit Tests (wt-tools)
- `test_profile_loader.py`:
  - Loads NullProfile when no project-type.yaml
  - Loads WebProjectType when project-type.yaml says "web"
  - Caches profile (singleton behavior)
  - reset_cache() works
  - NullProfile returns empty/None for all 12 methods

### Integration Tests (wt-tools)
- Each engine module with profile fallback:
  - Profile returns value → engine uses it
  - Profile returns None → engine falls back to legacy
  - NullProfile → engine uses legacy behavior exactly
- Specific regression tests:
  - `_get_planning_rules()` with NullProfile returns full `_PLANNING_RULES` (including Playwright)
  - `_get_planning_rules()` with WebProfile returns `_PLANNING_RULES_CORE` + web planning rules
  - `render_proposal()` with NullProfile uses generic checklist
  - `render_proposal()` with WebProfile uses web-specific checklist
  - `detect_dev_server()` cascade: profile overrides package.json detection but not explicit overrides

### E2E Validation
- Run #14 with profile-based engine → compare metrics with Run #13
- Key metric: review retry count should decrease (security patterns in planning)
- Verify: all 7 PM detection paths use profile when available
- Verify: Playwright E2E guidance present in planning prompt (no regression from split)
