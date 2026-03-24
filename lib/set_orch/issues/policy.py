"""Policy Engine — configurable rules for auto-fix, timeouts, and muting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import Diagnosis, Issue, IssueState, MutePattern


@dataclass
class ConcurrencyConfig:
    max_parallel_investigations: int = 3
    max_parallel_fixes: int = 1  # Hard rule: always 1


@dataclass
class RetryConfig:
    max_retries: int = 2
    backoff_seconds: int = 60


@dataclass
class InvestigationConfig:
    token_budget: int = 50000
    timeout_seconds: int = 300
    template: str = "default"
    auto_investigate: bool = True


@dataclass
class IssuesPolicyConfig:
    enabled: bool = True

    # Timeout by severity (seconds). None = never auto-approve. 0 = instant.
    timeout_by_severity: dict[str, Optional[int]] = field(default_factory=lambda: {
        "unknown": None,
        "low": 120,
        "medium": 300,
        "high": 900,
        "critical": None,
    })

    # Mode overrides
    modes: dict[str, dict] = field(default_factory=dict)

    # Auto-fix conditions
    auto_fix_conditions: dict = field(default_factory=lambda: {
        "min_confidence": 0.85,
        "max_scope": "multi_file",
        "blocked_tags": ["db_migration", "auth", "security", "data_loss_risk"],
    })

    # Always manual
    always_manual: list[dict] = field(default_factory=list)

    # Sub-configs
    investigation: InvestigationConfig = field(default_factory=InvestigationConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)

    # Auto-fix severity lists per mode
    auto_fix_severity: list[str] = field(default_factory=lambda: ["low", "medium"])

    @classmethod
    def from_dict(cls, data: dict) -> IssuesPolicyConfig:
        cfg = cls()
        if not data:
            return cfg

        cfg.enabled = data.get("enabled", True)

        if "timeout_by_severity" in data:
            cfg.timeout_by_severity.update(data["timeout_by_severity"])

        if "modes" in data:
            cfg.modes = data["modes"]

        if "auto_fix_conditions" in data:
            cfg.auto_fix_conditions.update(data["auto_fix_conditions"])

        if "always_manual" in data:
            cfg.always_manual = data["always_manual"]

        if "auto_fix_severity" in data:
            cfg.auto_fix_severity = data["auto_fix_severity"]

        if "investigation" in data:
            inv = data["investigation"]
            cfg.investigation = InvestigationConfig(
                token_budget=inv.get("token_budget", 50000),
                timeout_seconds=inv.get("timeout_seconds", 300),
                template=inv.get("template", "default"),
                auto_investigate=inv.get("auto_investigate", True),
            )

        if "retry" in data:
            r = data["retry"]
            cfg.retry = RetryConfig(
                max_retries=r.get("max_retries", 2),
                backoff_seconds=r.get("backoff_seconds", 60),
            )

        if "concurrency" in data:
            c = data["concurrency"]
            cfg.concurrency = ConcurrencyConfig(
                max_parallel_investigations=c.get("max_parallel_investigations", 3),
                max_parallel_fixes=min(c.get("max_parallel_fixes", 1), 1),  # enforce max 1
            )

        return cfg


# Scope ordering for max_scope comparison
_SCOPE_ORDER = {"single_file": 0, "multi_file": 1, "cross_module": 2, "unknown": 3}


class PolicyEngine:
    """Evaluates policies for issue management decisions."""

    def __init__(self, config: IssuesPolicyConfig, mode: str = "e2e"):
        self.config = config
        self.mode = mode

    def _effective_config(self) -> dict:
        """Get mode-specific overrides merged with defaults."""
        mode_overrides = self.config.modes.get(self.mode, {})
        return mode_overrides

    def get_timeout(self, issue: Issue) -> Optional[int]:
        """Get approval timeout in seconds for this issue. None = never auto-approve. 0 = instant."""
        overrides = self._effective_config()
        timeouts = overrides.get("timeout_by_severity", self.config.timeout_by_severity)
        return timeouts.get(issue.severity, self.config.timeout_by_severity.get(issue.severity))

    def can_auto_fix(self, issue: Issue) -> bool:
        """Evaluate whether an issue can be auto-fixed based on policy."""
        if not issue.diagnosis:
            return False

        diag = issue.diagnosis

        # Unknown severity = never auto-fix
        if issue.severity == "unknown":
            return False

        # Check always_manual rules
        for rule in self.config.always_manual:
            if "severity" in rule and issue.severity == rule["severity"]:
                return False
            if "scope" in rule and diag.fix_scope == rule["scope"]:
                return False
            if "tags" in rule:
                if any(t in diag.tags for t in rule["tags"]):
                    return False

        # Check severity is in auto-fix list for this mode
        overrides = self._effective_config()
        allowed_severities = overrides.get("auto_fix_severity", self.config.auto_fix_severity)
        if issue.severity not in allowed_severities:
            return False

        # Check conditions
        conditions = self.config.auto_fix_conditions
        min_conf = conditions.get("min_confidence", 0.85)
        if diag.confidence < min_conf:
            return False

        max_scope = conditions.get("max_scope", "multi_file")
        if _SCOPE_ORDER.get(diag.fix_scope, 3) > _SCOPE_ORDER.get(max_scope, 1):
            return False

        blocked_tags = conditions.get("blocked_tags", [])
        if any(t in blocked_tags for t in diag.tags):
            return False

        # Check timeout exists (if null, means always manual)
        timeout = self.get_timeout(issue)
        if timeout is None:
            return False

        return True

    def should_auto_investigate(self, issue: Issue) -> bool:
        """Should this issue be auto-investigated?"""
        return self.config.investigation.auto_investigate

    def should_register(
        self,
        source: str,
        severity_hint: str,
        error_summary: str,
        mute_match: Optional[MutePattern] = None,
    ) -> bool:
        """Filter: which detection events become issues?"""
        if mute_match:
            return False

        match source:
            case "sentinel":
                return True  # All sentinel findings become issues
            case "gate":
                return True
            case "watchdog":
                return True
            case "user":
                return True

        return True

    def assess_severity_hint(self, source: str, detail: str = "") -> str:
        """Provide initial severity hint from source type. Actual severity set by investigation."""
        return "unknown"
