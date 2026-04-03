from __future__ import annotations

"""Project type plugin interface — ABC and dataclasses.

Defines the ProjectType interface that all project knowledge plugins
must implement, plus the data structures they use.

Migrated from: set-project-base/set_project_base/base.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        return ""

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
                return pm
        return None

    def detect_test_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_build_command(self, project_path: str) -> Optional[str]:
        return None

    def detect_e2e_command(self, project_path: str) -> Optional[str]:
        return None

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
        return True

    def post_merge_install(self, project_path: str) -> bool:
        return True

    def ignore_patterns(self) -> list:
        return []

    def merge_strategies(self) -> list:
        return []

    def register_gates(self) -> list:
        """Return domain-specific GateDefinitions for this project type.

        Override in subclass to register gates like e2e, lint, etc.
        Returns list of GateDefinition instances.
        """
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

    def _classify_patterns(self, patterns: list[dict]) -> list[dict]:
        """Classify review patterns as 'template' or 'project' via Sonnet.

        Each pattern dict must have 'pattern' and optionally 'fix_hint'.
        Returns the same dicts with 'scope' field added.
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

        items = [{"pattern": p["pattern"], "fix_hint": p.get("fix_hint", "")} for p in patterns]
        prompt = (
            f"Classify each review finding as \"template\" (generic framework/security pattern "
            f"applicable to any {profile_name} project) or \"project\" (business logic, "
            f"domain-specific, or app-specific pattern).\n\n"
            f"Findings:\n{json.dumps(items, indent=2)}\n\n"
            f"Return ONLY a JSON array: [{{\"pattern\": \"...\", \"scope\": \"template|project\"}}]"
        )

        result = run_claude_logged(
            prompt,
            purpose="classify",
            model="sonnet",
            timeout=60,
            extra_args=["--max-turns", "1"],
        )

        if result.exit_code != 0:
            # Fallback: all project (safe — no template pollution)
            for p in patterns:
                p["scope"] = "project"
            return patterns

        # Parse LLM response
        try:
            import re
            # Extract JSON array from response
            match = re.search(r"\[.*\]", result.stdout, re.DOTALL)
            if match:
                classified = json.loads(match.group())
                scope_map = {c["pattern"]: c["scope"] for c in classified}
                for p in patterns:
                    p["scope"] = scope_map.get(p["pattern"], "project")
            else:
                for p in patterns:
                    p["scope"] = "project"
        except (json.JSONDecodeError, KeyError):
            for p in patterns:
                p["scope"] = "project"

        return patterns

    def persist_review_learnings(self, patterns: list[dict], project_path: str) -> None:
        """Persist classified review learnings to template and project JSONLs.

        Called after each change merge. Classifies patterns via Sonnet,
        writes template-scoped patterns to ~/.config JSONL (with flock),
        writes project-scoped patterns to project JSONL.
        """
        import fcntl
        import json
        import os
        from datetime import datetime, timezone

        if not patterns:
            return

        # Classify
        classified = self._classify_patterns(patterns)

        template_patterns = [p for p in classified if p.get("scope") == "template"]
        project_patterns = [p for p in classified if p.get("scope") == "project"]

        now = datetime.now(timezone.utc).isoformat()

        # --- Template JSONL (flock for concurrency) ---
        if template_patterns:
            tpl_path = self._learnings_template_path(ensure_dir=True)
            lock_path = str(tpl_path) + ".lock"
            lock_fd = open(lock_path, "a")
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                existing = []
                if tpl_path.is_file():
                    with open(tpl_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    existing.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                existing = self._merge_learnings(existing, template_patterns, now)
                with open(tpl_path, "w") as f:
                    for entry in existing:
                        f.write(json.dumps(entry) + "\n")
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()

        # --- Project JSONL ---
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
            with open(proj_path, "w") as f:
                for entry in existing:
                    f.write(json.dumps(entry) + "\n")

    @staticmethod
    def _merge_learnings(
        existing: list[dict], new_patterns: list[dict], now: str, cap: int = 50
    ) -> list[dict]:
        """Merge new patterns into existing, dedup by normalized pattern, cap at N."""
        import re
        by_key: dict[str, dict] = {}
        for e in existing:
            key = re.sub(r"\[(?:CRITICAL|HIGH)\]\s*", "", e.get("pattern", "")).strip().lower()[:60]
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
            else:
                by_key[key] = {
                    "pattern": p["pattern"],
                    "severity": p.get("severity", "HIGH"),
                    "scope": p.get("scope", "project"),
                    "count": 1,
                    "last_seen": now,
                    "source_changes": p.get("source_changes", []),
                    "fix_hint": p.get("fix_hint", ""),
                }

        # Cap: remove oldest by last_seen
        entries = list(by_key.values())
        if len(entries) > cap:
            entries.sort(key=lambda e: e.get("last_seen", ""), reverse=True)
            entries = entries[:cap]

        return entries

    def review_learnings_checklist(self, project_path: str) -> str:
        """Return compact markdown checklist from 3 sources.

        Combines: static baseline [baseline] + template JSONL [template, seen Nx]
        + project JSONL [project, seen Nx]. Max 15 lines.
        """
        import json
        import os

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
                            count = e.get("count", 1)
                            items.append((e["pattern"], f"template, seen {count}x", 500 + count))
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        # 3. Static baseline (lowest priority) — subclass overrides to provide
        baseline = self._review_baseline_items()
        for pattern in baseline:
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

        # Sort by priority descending (no cap — full checklist fits in context)
        unique.sort(key=lambda x: -x[2])

        lines = ["## Review Learnings Checklist (review will BLOCK if violated)"]
        for pattern, tag, _ in unique:
            lines.append(f"- {pattern} [{tag}]")

        return "\n".join(lines)

    def _review_baseline_items(self) -> list[str]:
        """Return static baseline checklist items. Override in subclass."""
        return []
