from __future__ import annotations

"""Project type plugin interface — ABC and dataclasses.

Defines the ProjectType interface that all project knowledge plugins
must implement, plus the data structures they use.

Migrated from: set-project-base/set_project_base/base.py
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProjectTypeInfo:
    """Metadata about a project type plugin."""
    name: str
    version: str
    description: str
    parent: Optional[str] = None  # e.g., "web" extends "base"


@dataclass
class TemplateInfo:
    """A template variant provided by a project type."""
    id: str  # e.g., "nextjs"
    description: str
    template_dir: str  # relative to plugin package


@dataclass
class VerificationRule:
    """A declarative verification rule."""
    id: str
    description: str
    check: str  # check type: cross-file-key-parity, file-mentions, etc.
    severity: str = "warning"  # error, warning, info
    config: Dict[str, Any] = field(default_factory=dict)
    ignore: List[str] = field(default_factory=list)


@dataclass
class OrchestrationDirective:
    """An orchestration guardrail."""
    id: str
    description: str
    trigger: str  # trigger expression
    action: str  # action type: serialize, warn, flag-for-review, post-merge
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpecSection:
    """A section descriptor for the write-spec skill.

    Tells write-spec what to ask the user and where to write the output.
    Core sections are project-type agnostic; modules add domain-specific ones.
    """
    id: str              # e.g., "data_model", "auth_roles"
    title: str           # e.g., "Data Model"
    description: str     # What this section covers
    required: bool       # Block assembly if missing
    phase: int           # Order in the write-spec flow (lower = earlier)
    output_path: str     # Where to write (e.g., "docs/features/{name}.md")
    prompt_hint: str     # Suggested question for the user


class ProjectType(ABC):
    """Base class for project type plugins.

    Project types provide domain-specific knowledge to set-core:
    - Templates for project-knowledge.yaml and .claude/rules/
    - Verification rules for opsx:verify
    - Orchestration directives for the sentinel

    Only `info` and `get_templates` are abstract — all other methods
    have default (empty/no-op) implementations so plugins only override
    what they need.
    """

    @property
    @abstractmethod
    def info(self) -> ProjectTypeInfo:
        """Return project type metadata."""

    @abstractmethod
    def get_templates(self) -> List[TemplateInfo]:
        """Return available template variants."""

    def get_template_dir(self, template_id: str) -> Optional[Path]:
        """Return the directory containing template files for a variant."""
        import inspect

        for tmpl in self.get_templates():
            if tmpl.id == template_id:
                cls_file = inspect.getfile(type(self))
                pkg_dir = Path(cls_file).parent
                return pkg_dir / tmpl.template_dir
        return None

    # --- Rules and directives ---

    def get_verification_rules(self) -> List[VerificationRule]:
        return []

    def get_orchestration_directives(self) -> List[OrchestrationDirective]:
        return []

    def get_all_verification_rules(self) -> List[VerificationRule]:
        return self.get_verification_rules()

    def get_all_orchestration_directives(self) -> List[OrchestrationDirective]:
        return self.get_orchestration_directives()

    # --- Profile methods (engine integration) ---

    def spec_sections(self) -> List[SpecSection]:
        """Return spec sections for the write-spec skill.

        Core sections are project-type agnostic. Modules override to add
        domain-specific sections (e.g., web adds data_model, seed_catalog).
        """
        return []

    def planning_rules(self) -> str:
        """Module-specific planning rules injected into planner prompt."""
        return ""

    def cross_cutting_files(self) -> List[str]:
        """File patterns needing serialization when touched by multiple changes."""
        return []

    def design_page_aliases(self) -> dict[str, list[str]]:
        """Page name → alias list for design brief scope matching.

        Override in modules to add domain-specific aliases (e.g., Hungarian
        route names). Return empty dict to use bridge.sh defaults.
        """
        return {}

    def build_per_change_design(self, change_name: str, scope: str, wt_path: str, snapshot_dir: str) -> bool:
        """Build per-change design.md with tokens + matched design brief pages.

        Override in project-type modules to implement design-specific logic
        (e.g., web module calls bridge.sh for Figma/shadcn design extraction).
        Returns True if a per-change design.md was written.
        """
        return False

    def get_design_dispatch_context(self, scope: str, snapshot_dir: str) -> str:
        """Return design context (tokens + component hierarchy) for dispatch prompt.

        Override in project-type modules to extract design tokens from
        project-specific sources (Figma snapshots, shadcn config, etc.).
        Returns design context string or empty string.
        """
        return ""

    def build_design_review_section(self, snapshot_dir: str) -> str:
        """Return design compliance section for code review prompt.

        Override in project-type modules to generate design adherence checks.
        Returns compliance text or empty string.
        """
        return ""

    def fetch_design_data_model(self, project_path: str) -> str:
        """Return design data model (TypeScript interfaces, entity definitions).

        Override in project-type modules to extract data models from design
        sources (e.g., Figma component code). Returns data model text or empty string.
        """
        return ""

    def collect_test_artifacts(self, wt_path: str) -> list:
        """Collect test artifacts (screenshots, traces, reports) from worktree.

        Returns list of dicts: [{name, path, type, test}]
        - type: "image", "trace", "report", "log"
        - test: parent test name (optional)
        Override in subclass for framework-specific artifact collection.
        """
        return []

    def classify_test_risk(self, scenario: Any, requirement: dict) -> str:
        """Classify a test scenario's risk level for ISTQB risk-based testing.

        Override in subclass to provide domain/keyword-specific classification.
        Core provides risk→min_tests mapping: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.

        Returns "HIGH", "MEDIUM", or "LOW". Default: "LOW".
        """
        return "LOW"

    def security_rules_paths(self, project_path: str) -> List[Path]:
        return []

    def security_checklist(self) -> str:
        return ""

    def generated_file_patterns(self) -> list:
        return []

    def lockfile_pm_map(self) -> list:
        return []

    def detect_package_manager(self, project_path: str) -> Optional[str]:
        d = Path(project_path)
        for lockfile, pm in self.lockfile_pm_map():
            if (d / lockfile).is_file():
                logger.debug("Profile.detect_package_manager(%s) = %s (via %s)", project_path, pm, lockfile)
                return pm
        logger.debug("Profile.detect_package_manager(%s) = None", project_path)
        return None

    def detect_test_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_build_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_e2e_command(self, project_path: str) -> Optional[str]:
        return None

    def render_test_skeleton(self, entries: list, change_name: str) -> str:
        """Render a test skeleton file from test plan entries.

        Override in project-type modules to produce framework-specific syntax
        (e.g., Playwright for web, Vitest for API-only).
        Returns empty string if not supported.
        """
        return ""

    def e2e_gate_env(self, port: int) -> Dict[str, str]:
        """Return env vars for e2e gate with isolated port.

        Override in project-type modules to map the port to framework-specific
        env vars (e.g. PW_PORT for Playwright, PORT for Next.js).
        Core only generates the unique port number.
        """
        return {}

    def worktree_port(self, change_name: str) -> int:
        """Return a deterministic port for a worktree, or 0 for no port injection.

        Override in project-type modules to assign unique ports per worktree.
        Called during bootstrap to write PORT/PW_PORT to .env.
        """
        return 0

    def integration_pre_build(self, wt_path: str) -> bool:
        """Run minimal setup before integration build gate (e.g. DB schema sync).

        Unlike e2e_pre_gate which runs full setup (seed, generate), this does
        only what's needed for the build to succeed (schema push, no seed).
        Returns True if setup succeeded, False on failure (non-blocking).
        """
        return True

    def e2e_pre_gate(self, wt_path: str, env: Dict[str, str]) -> bool:
        """Run setup before e2e tests (e.g. DB migration, seed data).

        Called by the e2e gate runner before executing the test command.
        Returns True if setup succeeded, False to skip e2e.
        """
        return True

    def e2e_post_gate(self, wt_path: str) -> None:
        """Cleanup after e2e tests complete (pass or fail).

        Called in a finally block by the e2e gate runner.
        """

    def detect_dev_server(self, project_path: str) -> Optional[str]:
        return None

    def bootstrap_worktree(self, project_path: str, wt_path: str) -> bool:
        logger.debug("Profile.bootstrap_worktree(%s, %s) = True (base no-op)", project_path, wt_path)
        return True

    def post_merge_install(self, project_path: str) -> bool:
        logger.debug("Profile.post_merge_install(%s) = True (base no-op)", project_path)
        return True

    def ignore_patterns(self) -> list:
        return []

    def merge_strategies(self) -> list:
        return []

    def parse_test_results(self, stdout: str) -> dict[tuple[str, str], str]:
        """Parse E2E test output into per-test pass/fail results.

        Override in subclass to parse framework-specific test output
        (e.g., Playwright for web, pytest for Python).

        Returns {(test_file, test_name): "pass"|"fail"}.
        Default returns empty dict (binary pass/fail only).
        """
        return {}

    def e2e_test_methodology(self) -> str:
        """Return framework-specific E2E test methodology for per-change tests.

        Override in subclass to provide test framework patterns (e.g., Playwright
        serial tests for web, pytest patterns for Python). Injected into each
        change's scope so agents write proper E2E tests alongside their features.
        """
        return ""

    # Backwards compatibility alias
    def acceptance_test_methodology(self) -> str:
        return self.e2e_test_methodology()

    def register_gates(self) -> list:
        """Return domain-specific GateDefinitions for this project type.

        Override in subclass to register gates like e2e, lint, etc.
        Returns list of GateDefinition instances.
        """
        logger.debug("Profile.register_gates() = [] (base no-op)")
        return []

    def gate_overrides(self, change_type: str) -> dict:
        return {}

    def rule_keyword_mapping(self) -> dict:
        return {}

    def get_forbidden_patterns(self) -> list:
        return []

    def generate_startup_file(self, project_path: str) -> str:
        """Generate START.md content for a project.

        Returns full markdown content for the startup file, or empty string
        if the project type doesn't support startup file generation.
        Override in subclass to provide project-type-specific detection.
        """
        return ""

    def generate_smoke_e2e(self, project_path: str) -> Optional[str]:
        """Deprecated: use e2e_smoke_command() instead."""
        return None

    def e2e_smoke_command(self, base_cmd: str, test_names: list) -> Optional[str]:
        """Construct command to run only named tests (smoke subset).

        Used by the merger to run a fast regression check on inherited tests
        before running the change's own tests.

        Args:
            base_cmd: The detected e2e command (e.g., "npx playwright test")
            test_names: List of test names to run as smoke
        Returns:
            Full command string, or None if not supported.
        """
        return None

    def e2e_scoped_command(self, base_cmd: str, spec_files: list) -> Optional[str]:
        """Construct command to run only specific spec files.

        Used by the merger to run only the change's own test files.

        Args:
            base_cmd: The detected e2e command
            spec_files: Relative paths to spec files to run
        Returns:
            Full command string, or None (falls back to base_cmd).
        """
        return None

    def extract_first_test_name(self, spec_path: str) -> Optional[str]:
        """Extract the first test name from a spec file for smoke selection.

        Framework-specific parsing (e.g., regex for test() in Playwright,
        def test_ in pytest). Override in subclass.
        """
        return None

    def get_comparison_conventions(self) -> List[Dict[str, Any]]:
        """Return convention checks for the divergence comparison tool.

        Each check is a dict with:
        - id: short identifier
        - description: human-readable description
        - check: callable(project_dir: Path) -> bool
        """
        return []

    def get_comparison_template_files(self) -> List[str]:
        """Return list of template-relative file paths to check for compliance.

        The compare tool will diff these against the deployed versions.
        Override to specify which template files matter for this project type.
        """
        return []

    def pre_dispatch_checks(self, change_type: str, wt_path: str) -> list:
        return []

    def post_verify_hooks(self, change_name: str, wt_path: str, gate_results: list) -> None:
        pass

    def post_merge_hooks(self, change_name: str, state_file: str) -> None:
        """Run profile-specific post-merge operations (i18n sidecar merge, codegen, etc.)."""
        pass

    def decompose_hints(self) -> list:
        return []

    # --- Review learnings persistence ---

    def _learnings_template_path(self, ensure_dir: bool = False) -> Path:
        """Return path to template-level learnings JSONL for this profile type.

        Stored at ~/.config/set-core/review-learnings/<profile-name>.jsonl.
        Only creates the directory when ensure_dir=True.
        """
        import os
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        config_base = Path(xdg) if xdg else Path.home() / ".config"
        config_dir = config_base / "set-core" / "review-learnings"
        if ensure_dir:
            config_dir.mkdir(parents=True, exist_ok=True)
        name = self.info.name
        return config_dir / f"{name}.jsonl"

    def _classify_patterns(self, patterns: list[dict], project_path: str = "") -> list[dict]:
        """Classify review patterns as 'template' or 'project' via Sonnet.

        Each pattern dict must have 'pattern' and optionally 'fix_hint'.
        Returns the same dicts with 'scope' field added.
        Uses index-based LLM response matching to avoid silent drops
        when the LLM paraphrases pattern strings.
        Falls back to all 'project' if the LLM call fails.
        """
        if not patterns:
            return patterns

        import copy
        import json
        from .subprocess_utils import run_claude_logged

        # Work on copies to avoid mutating caller's data
        patterns = [copy.copy(p) for p in patterns]
        profile_name = self.info.name

        # Index-based items: LLM returns {"idx": N, "scope": ...}
        items = [
            {"idx": i, "pattern": p["pattern"], "fix_hint": p.get("fix_hint", "")}
            for i, p in enumerate(patterns)
        ]
        prompt = (
            f"Classify each review finding as \"template\" (generic framework/security pattern "
            f"applicable to any {profile_name} project) or \"project\" (business logic, "
            f"domain-specific, or app-specific pattern).\n\n"
            f"Examples:\n"
            f"- \"No authentication middleware on API routes\" → template (applies to any web project)\n"
            f"- \"IDOR — any user can modify other users' resources\" → template (generic security)\n"
            f"- \"Budapest postal code validation missing\" → project (domain-specific)\n"
            f"- \"Product name must be unique per brewery\" → project (business rule)\n"
            f"- \"Missing CSRF protection\" → template (generic security)\n"
            f"- \"Loyalty points not deducted on refund\" → project (business logic)\n\n"
            f"Findings:\n{json.dumps(items, indent=2)}\n\n"
            f"Return ONLY a raw JSON array (no markdown fences, no prose): "
            f"[{{\"idx\": 0, \"scope\": \"template|project\"}}, ...]. "
            f"Every idx from 0 to {len(patterns) - 1} must appear exactly once."
        )

        result = run_claude_logged(
            prompt,
            purpose="classify",
            model="sonnet",
            timeout=60,
            extra_args=["--max-turns", "1"],
            cwd=project_path or None,
        )

        if result.exit_code != 0:
            logger.warning(
                "Learnings classifier LLM call failed (exit=%d) — defaulting all to project",
                result.exit_code,
            )
            for p in patterns:
                p["scope"] = "project"
            return patterns

        # Parse LLM response with markdown-fence stripping
        try:
            import re
            stdout = result.stdout
            stdout = re.sub(r"```(?:json)?\s*", "", stdout)
            stdout = re.sub(r"\s*```", "", stdout)
            match = re.search(r"\[.*\]", stdout, re.DOTALL)
            if match:
                classified = json.loads(match.group())
                # Build idx → scope map
                scope_map = {}
                for c in classified:
                    if isinstance(c, dict) and "idx" in c and "scope" in c:
                        idx = c["idx"]
                        if isinstance(idx, int) and 0 <= idx < len(patterns):
                            scope_map[idx] = c["scope"]
                # Apply scopes by index
                for i, p in enumerate(patterns):
                    p["scope"] = scope_map.get(i, "project")
                missing = len(patterns) - len(scope_map)
                if missing > 0:
                    logger.warning(
                        "Learnings classifier: %d/%d entries missing from LLM response — defaulted to project",
                        missing, len(patterns),
                    )
            else:
                logger.warning("Learnings classifier: no JSON array in LLM output — defaulting all to project")
                for p in patterns:
                    p["scope"] = "project"
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Learnings classifier: parse error — defaulting all to project", exc_info=True)
            for p in patterns:
                p["scope"] = "project"

        return patterns

    # Category keywords for scope-aware filtering — aligned with
    # templates.py:classify_diff_content() patterns.
    #
    # Keywords are matched with word boundaries (\b<kw>\b) to avoid false
    # positives from substring hits (e.g., "create" should not match
    # "re-create" or "creation of a form"). Short generic verbs like
    # create/update/delete are intentionally excluded — they would match
    # too broadly. Rely on longer, domain-specific keywords (prisma,
    # findmany, schema, etc.) for database detection.
    LEARNINGS_CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "auth": [
            "auth", "authentication", "authorization", "session", "middleware",
            "login", "logout", "cookie", "password", "bcrypt", "jwt", "token",
            "credential", "permission", "role", "rbac", "idor",
        ],
        "api": [
            "api", "endpoint", "route", "handler", "rate limit", "rate-limit",
            "cors", "csrf", "server action", "server actions",
        ],
        "database": [
            "prisma", "database", "migration", "schema", "sql", "findmany",
            "findfirst", "transaction", "cascade", "foreign key",
            "updatemany", "deletemany", "where clause",
        ],
        "frontend": [
            "component", "tsx", "jsx", "react", "css", "tailwind", "shadcn",
            "button", "form", "layout", "page", "html", "svg", "image",
            "accessibility", "aria", "xss",
        ],
    }

    @staticmethod
    def _assign_categories(pattern: str, fix_hint: str = "") -> list[str]:
        """Assign content categories to a learning based on word-boundary
        keyword matching.

        Returns list of matching categories, or ["general"] if none match.
        Uses `\\b<keyword>\\b` regex to avoid substring false positives.
        """
        import re
        text = (pattern + " " + fix_hint).lower()
        matched = []
        for category, keywords in ProjectType.LEARNINGS_CATEGORY_KEYWORDS.items():
            for kw in keywords:
                # Word-boundary match for single tokens, substring for multi-word
                if " " in kw or "-" in kw:
                    if kw in text:
                        matched.append(category)
                        break
                else:
                    if re.search(r"\b" + re.escape(kw) + r"\b", text):
                        matched.append(category)
                        break
        return matched or ["general"]

    @staticmethod
    def _truncate_fix_hint(fix_hint: str, max_len: int = 200) -> str:
        """Truncate fix_hint: strip code blocks, cap at max_len chars."""
        import re
        # Strip fenced code blocks
        hint = re.sub(r"```[\s\S]*?```", "", fix_hint).strip()
        # Collapse multi-line to single line
        hint = re.sub(r"\s*\n\s*", " ", hint).strip()
        if len(hint) > max_len:
            hint = hint[:max_len - 3] + "..."
        return hint

    @staticmethod
    def _eviction_score(entry: dict) -> float:
        """Compute eviction priority score: higher = more valuable, kept longer.

        Formula: count * severity_weight * recency_factor
        """
        from datetime import datetime, timezone

        count = entry.get("count", 1)

        severity = entry.get("severity", "HIGH").upper()
        severity_weights = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0.5}
        sev_w = severity_weights.get(severity, 1)

        last_seen = entry.get("last_seen", "")
        recency = 0.4  # default: old
        if last_seen:
            try:
                ts = datetime.fromisoformat(last_seen)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - ts).days
                if age_days <= 7:
                    recency = 1.0
                elif age_days <= 30:
                    recency = 0.7
                else:
                    recency = 0.4
            except (ValueError, TypeError):
                pass

        return count * sev_w * recency

    def _dedup_learnings(self, entries: list[dict], project_path: str = "") -> list[dict]:
        """Semantic dedup via Sonnet: merge entries describing the same issue.

        Returns deduplicated entries list. Falls back to no-op on LLM failure.
        """
        if len(entries) <= 1:
            return entries

        import json
        from .subprocess_utils import run_claude_logged

        # Build index of patterns for the LLM
        indexed = [{"idx": i, "pattern": e.get("pattern", "")} for i, e in enumerate(entries)]
        prompt = (
            "Group these review findings by semantic equivalence. "
            "Only merge patterns that describe the EXACT same issue "
            "(e.g., 'No middleware.ts' and 'Missing src/middleware.ts' are the same; "
            "'No auth middleware' and 'Missing CSRF protection' are NOT the same).\n\n"
            f"Patterns:\n{json.dumps(indexed, indent=2)}\n\n"
            "Return ONLY a raw JSON array of groups (no markdown fences, no prose), "
            "where each group is an array of indices. "
            "Every index from 0 to "
            f"{len(entries) - 1} must appear in exactly one group. "
            "Example: [[0, 2, 4], [1], [3]]"
        )

        result = run_claude_logged(
            prompt,
            purpose="classify",
            model="sonnet",
            timeout=60,
            extra_args=["--max-turns", "1"],
            cwd=project_path or None,
        )

        if result.exit_code != 0:
            logger.warning("Learnings dedup LLM call failed (exit=%d) — skipping dedup", result.exit_code)
            return entries

        # Parse merge groups — strip markdown fences first, then extract JSON array
        try:
            import re
            stdout = result.stdout
            # Strip common markdown fence wrappers
            stdout = re.sub(r"```(?:json)?\s*", "", stdout)
            stdout = re.sub(r"\s*```", "", stdout)
            # Extract outermost JSON array (balanced approach: find first [ then
            # match brackets to handle nested groups correctly)
            match = re.search(r"\[\s*\[.*?\]\s*\]", stdout, re.DOTALL)
            if not match:
                # Fallback: non-greedy search for any array
                match = re.search(r"\[.*\]", stdout, re.DOTALL)
            if not match:
                logger.warning("Learnings dedup: no JSON array in LLM output — skipping dedup")
                return entries
            groups = json.loads(match.group())
            if not isinstance(groups, list) or not all(isinstance(g, list) for g in groups):
                logger.warning("Learnings dedup: malformed groups — skipping dedup")
                return entries
            # Extra safety: all indices must be ints within range
            for g in groups:
                for i in g:
                    if not isinstance(i, int) or i < 0 or i >= len(entries):
                        logger.warning("Learnings dedup: out-of-range index %r — skipping dedup", i)
                        return entries
        except (json.JSONDecodeError, TypeError):
            logger.warning("Learnings dedup: JSON parse error — skipping dedup", exc_info=True)
            return entries

        # Validate all indices present
        all_indices = set()
        for g in groups:
            all_indices.update(g)
        if all_indices != set(range(len(entries))):
            logger.warning(
                "Learnings dedup: index mismatch (got %d indices for %d entries) — skipping dedup",
                len(all_indices), len(entries),
            )
            return entries

        # Merge each group
        merged = []
        for group in groups:
            if len(group) == 1:
                merged.append(entries[group[0]])
                continue

            group_entries = [entries[i] for i in group]
            # Keep shortest clear pattern text
            best = min(group_entries, key=lambda e: len(e.get("pattern", "")))
            result_entry = dict(best)
            # Sum counts
            result_entry["count"] = sum(e.get("count", 1) for e in group_entries)
            # Union source_changes (cap 10)
            all_changes: list[str] = []
            for e in group_entries:
                for c in e.get("source_changes", []):
                    if c not in all_changes:
                        all_changes.append(c)
            result_entry["source_changes"] = all_changes[-10:]
            # Most recent last_seen
            result_entry["last_seen"] = max(
                (e.get("last_seen", "") for e in group_entries), default=""
            )
            # Highest severity
            sev_order = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
            result_entry["severity"] = max(
                (e.get("severity", "HIGH") for e in group_entries),
                key=lambda s: sev_order.get(s, 0),
            )
            merged.append(result_entry)

        logger.info(
            "Learnings dedup: %d entries → %d (merged %d groups)",
            len(entries), len(merged), sum(1 for g in groups if len(g) > 1),
        )
        return merged

    def persist_review_learnings(self, patterns: list[dict], project_path: str) -> None:
        """Persist classified review learnings to template and project JSONLs.

        Called after each change merge. Classifies patterns via Sonnet,
        deduplicates semantically, writes template-scoped patterns to
        ~/.config JSONL (with flock), writes project-scoped patterns to
        project JSONL.
        """
        import fcntl
        import json
        import os
        from datetime import datetime, timezone

        if not patterns:
            return

        # Truncate fix_hints before any processing
        for p in patterns:
            if p.get("fix_hint"):
                p["fix_hint"] = self._truncate_fix_hint(p["fix_hint"])

        # Assign categories
        for p in patterns:
            p["categories"] = self._assign_categories(p.get("pattern", ""), p.get("fix_hint", ""))

        # Classify
        classified = self._classify_patterns(patterns, project_path=project_path)

        template_patterns = [p for p in classified if p.get("scope") == "template"]
        project_patterns = [p for p in classified if p.get("scope") == "project"]

        now = datetime.now(timezone.utc).astimezone().isoformat()

        # --- Template JSONL (flock for concurrency) ---
        #
        # Two-phase approach to avoid holding the lock during the slow
        # (up to 60s) dedup LLM call:
        #   1. Acquire lock → read existing → release lock
        #   2. Merge + dedup (slow, no lock held)
        #   3. Re-acquire lock → write atomically → release lock
        # Between phase 1 and 3, another process may have written. We
        # accept that small race window: the last writer wins. Readers
        # never see a half-written file because write happens while
        # holding the lock.
        if template_patterns:
            tpl_path = self._learnings_template_path(ensure_dir=True)
            lock_path = str(tpl_path) + ".lock"

            # Phase 1: read under lock
            existing = []
            lock_fd = open(lock_path, "a")
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                if tpl_path.is_file():
                    with open(tpl_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    existing.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()

            # Phase 2: merge + dedup (slow LLM call) WITHOUT holding lock
            existing = self._merge_learnings(existing, template_patterns, now)
            existing = self._dedup_learnings(existing, project_path=project_path)

            # Phase 3: write under lock
            lock_fd = open(lock_path, "a")
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                with open(tpl_path, "w") as f:
                    for entry in existing:
                        f.write(json.dumps(entry) + "\n")
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()

        # --- Project JSONL ---
        # No flock needed — single-project access, serial merges.
        if project_patterns:
            proj_path = os.path.join(project_path, "set", "orchestration", "review-learnings.jsonl")
            os.makedirs(os.path.dirname(proj_path), exist_ok=True)
            existing = []
            if os.path.isfile(proj_path):
                with open(proj_path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                existing.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            existing = self._merge_learnings(existing, project_patterns, now)
            existing = self._dedup_learnings(existing, project_path=project_path)
            with open(proj_path, "w") as f:
                for entry in existing:
                    f.write(json.dumps(entry) + "\n")

    @staticmethod
    def _merge_learnings(
        existing: list[dict], new_patterns: list[dict], now: str, cap: int = 200
    ) -> list[dict]:
        """Merge new patterns into existing, dedup by normalized pattern.

        Uses severity-weighted eviction with hysteresis (evict to cap-20 when cap reached).
        Backfills categories for existing entries that lack the field.
        Truncates fix_hints that exceed 200 chars.
        """
        import re
        by_key: dict[str, dict] = {}
        for e in existing:
            key = re.sub(r"\[(?:CRITICAL|HIGH)\]\s*", "", e.get("pattern", "")).strip().lower()[:60]
            # Backfill categories for entries that lack them
            if "categories" not in e:
                e["categories"] = ProjectType._assign_categories(
                    e.get("pattern", ""), e.get("fix_hint", ""),
                )
            # Truncate oversized fix_hints on existing entries
            if e.get("fix_hint") and len(e["fix_hint"]) > 200:
                e["fix_hint"] = ProjectType._truncate_fix_hint(e["fix_hint"])
            by_key[key] = e

        for p in new_patterns:
            key = re.sub(r"\[(?:CRITICAL|HIGH)\]\s*", "", p.get("pattern", "")).strip().lower()[:60]
            if key in by_key:
                by_key[key]["count"] = by_key[key].get("count", 1) + 1
                by_key[key]["last_seen"] = now
                changes = by_key[key].get("source_changes", [])
                for c in p.get("source_changes", []):
                    if c not in changes:
                        changes.append(c)
                by_key[key]["source_changes"] = changes[-10:]  # keep last 10
                # Update categories if new pattern has them
                if p.get("categories"):
                    by_key[key]["categories"] = p["categories"]
            else:
                by_key[key] = {
                    "pattern": p["pattern"],
                    "severity": p.get("severity", "HIGH"),
                    "scope": p.get("scope", "project"),
                    "count": 1,
                    "last_seen": now,
                    "source_changes": p.get("source_changes", []),
                    "fix_hint": p.get("fix_hint", ""),
                    "categories": p.get("categories", ["general"]),
                }

        # Eviction: severity-weighted scoring with hysteresis
        entries = list(by_key.values())
        if len(entries) > cap:
            entries.sort(key=ProjectType._eviction_score, reverse=True)
            entries = entries[:cap - 20]  # hysteresis: evict to cap-20

        return entries

    def review_learnings_checklist(
        self, project_path: str, content_categories: "set[str] | None" = None,
    ) -> str:
        """Return compact markdown checklist from 3 sources.

        Combines: static baseline [baseline] + template JSONL [template, seen Nx]
        + project JSONL [project, seen Nx].

        When content_categories is provided, only entries whose categories
        overlap with the provided set (plus "general" always included) are
        returned. This filters learnings to those relevant to the change scope.
        """
        import json
        import os

        # Build the set of accepted categories (always include "general").
        # Note: we use a truthy check, which means an empty set() is treated
        # the same as None — both mean "no category signal, include all
        # entries". This is intentional: `classify_diff_content(scope)` can
        # return set() for ambiguous scopes, and we prefer false positives
        # (over-inclusion) over false negatives (missing critical learnings).
        accepted_cats = None
        if content_categories:
            accepted_cats = content_categories | {"general"}

        def _category_matches(entry: dict) -> bool:
            if accepted_cats is None:
                return True
            entry_cats = set(entry.get("categories", ["general"]))
            return bool(entry_cats & accepted_cats)

        items: list[tuple[str, str, int]] = []  # (pattern, tag, sort_key)

        # 1. Project JSONL (highest priority)
        proj_path = os.path.join(project_path, "set", "orchestration", "review-learnings.jsonl")
        if os.path.isfile(proj_path):
            try:
                with open(proj_path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            e = json.loads(line)
                            if not _category_matches(e):
                                continue
                            count = e.get("count", 1)
                            items.append((e["pattern"], f"project, seen {count}x", 1000 + count))
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        # 2. Template JSONL
        tpl_path = self._learnings_template_path()
        if tpl_path.is_file():
            try:
                with open(tpl_path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            e = json.loads(line)
                            if not _category_matches(e):
                                continue
                            count = e.get("count", 1)
                            items.append((e["pattern"], f"template, seen {count}x", 500 + count))
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        # 3. Static baseline (lowest priority) — subclass overrides to provide
        baseline = self._review_baseline_items()
        for pattern in baseline:
            # Baseline items have no categories — apply keyword filter
            if accepted_cats is not None:
                cats = set(self._assign_categories(pattern))
                if not (cats & accepted_cats):
                    continue
            items.append((pattern, "baseline", 0))

        if not items:
            return ""

        # Deduplicate by normalized pattern (first occurrence wins = highest priority)
        import re
        seen: set[str] = set()
        unique: list[tuple[str, str, int]] = []
        for pattern, tag, sort_key in items:
            norm = re.sub(r"\[(?:CRITICAL|HIGH)\]\s*", "", pattern).strip().lower()[:60]
            if norm not in seen:
                seen.add(norm)
                unique.append((pattern, tag, sort_key))

        # Sort by priority descending (no cap — scope filtering handles size)
        unique.sort(key=lambda x: -x[2])

        lines = ["## Review Learnings Checklist (review will BLOCK if violated)"]
        for pattern, tag, _ in unique:
            lines.append(f"- {pattern} [{tag}]")

        return "\n".join(lines)

    def _review_baseline_items(self) -> list[str]:
        """Return static baseline checklist items. Override in subclass."""
        return []
