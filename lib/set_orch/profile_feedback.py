from __future__ import annotations

"""Feedback system — structured anonymized lesson collection and export.

Lessons are stored in set/knowledge/lessons/rule-feedback.yaml with a fixed
schema that forces anonymization by design (rule_id-based, no project names).
"""

import re
import warnings
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


class IssueType(str, Enum):
    """Types of feedback issues."""
    false_positive = "false_positive"
    too_aggressive = "too_aggressive"
    missing_exclude = "missing_exclude"
    missing_rule = "missing_rule"
    config_improvement = "config_improvement"


VALID_ISSUE_TYPES = [e.value for e in IssueType]


@dataclass
class SuggestedFix:
    """A suggested fix for a rule issue."""
    type: str  # e.g., add_exclude, refine_trigger, change_config
    value: str


@dataclass
class FeedbackLesson:
    """A structured feedback lesson about a rule or directive."""
    rule_id: str
    issue: str  # one of IssueType values
    context: str  # description without project/company names
    suggested_fix: Optional[SuggestedFix] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = date.today().isoformat()


def validate_lesson(lesson: FeedbackLesson) -> List[str]:
    """Validate a lesson. Returns list of errors (empty = valid)."""
    errors = []

    if not lesson.rule_id:
        errors.append("rule_id is required")

    if lesson.issue not in VALID_ISSUE_TYPES:
        errors.append(
            f"Invalid issue type '{lesson.issue}'. "
            f"Valid types: {', '.join(VALID_ISSUE_TYPES)}"
        )

    if not lesson.context:
        errors.append("context is required")

    return errors


def check_identifying_content(lesson: FeedbackLesson) -> List[str]:
    """Check if lesson context contains potentially identifying content."""
    warns = []
    path_pattern = re.compile(r'(/[a-zA-Z_][a-zA-Z0-9_/.-]{3,}|[A-Z]:\\)')
    if path_pattern.search(lesson.context):
        warns.append(
            f"Lesson for rule '{lesson.rule_id}' may contain "
            f"project-specific path — review before sharing"
        )
    return warns


class FeedbackStore:
    """Load, append, and save lessons from a YAML file."""

    def __init__(self, store_path: Path):
        self.store_path = store_path
        self._lessons: List[FeedbackLesson] = []
        self._load()

    def _load(self):
        if yaml is None or not self.store_path.exists():
            return
        with open(self.store_path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return
        for entry in data.get("lessons", []):
            fix = None
            if entry.get("suggested_fix"):
                fix = SuggestedFix(
                    type=entry["suggested_fix"].get("type", ""),
                    value=entry["suggested_fix"].get("value", ""),
                )
            self._lessons.append(FeedbackLesson(
                rule_id=entry.get("rule_id", ""),
                issue=entry.get("issue", ""),
                context=entry.get("context", ""),
                suggested_fix=fix,
                timestamp=entry.get("timestamp", ""),
            ))

    def _save(self):
        if yaml is None:
            warnings.warn("PyYAML not installed — cannot save feedback")
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        for lesson in self._lessons:
            entry: Dict[str, Any] = {
                "rule_id": lesson.rule_id,
                "issue": lesson.issue,
                "context": lesson.context,
                "timestamp": lesson.timestamp,
            }
            if lesson.suggested_fix:
                entry["suggested_fix"] = {
                    "type": lesson.suggested_fix.type,
                    "value": lesson.suggested_fix.value,
                }
            entries.append(entry)
        with open(self.store_path, "w") as f:
            yaml.dump(
                {"lessons": entries},
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    def get_lessons(self) -> List[FeedbackLesson]:
        return list(self._lessons)

    def append(self, lesson: FeedbackLesson) -> List[str]:
        """Validate and append a lesson. Returns errors (empty = success)."""
        errors = validate_lesson(lesson)
        if errors:
            return errors
        self._lessons.append(lesson)
        self._save()
        return []

    def export(self) -> str:
        """Export all lessons as anonymized YAML string."""
        if yaml is None:
            return "# Error: PyYAML not installed\n"

        all_warnings = []
        entries = []
        for lesson in self._lessons:
            errors = validate_lesson(lesson)
            if errors:
                all_warnings.append(
                    f"Skipping invalid lesson for '{lesson.rule_id}': {', '.join(errors)}"
                )
                continue
            all_warnings.extend(check_identifying_content(lesson))
            entry: Dict[str, Any] = {
                "rule_id": lesson.rule_id,
                "issue": lesson.issue,
                "context": lesson.context,
            }
            if lesson.suggested_fix:
                entry["suggested_fix"] = {
                    "type": lesson.suggested_fix.type,
                    "value": lesson.suggested_fix.value,
                }
            entries.append(entry)

        header = (
            "# set-project-base feedback export\n"
            "# Rule improvement suggestions from production usage.\n"
            "# Review before sharing — ensure no project-specific information.\n"
            "#\n"
            f"# Exported: {date.today().isoformat()}\n"
            f"# Lessons: {len(entries)}\n"
            "\n"
        )

        body = yaml.dump(
            {"feedback": entries},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        warning_text = ""
        if all_warnings:
            warning_text = "\n".join(f"# WARNING: {w}" for w in all_warnings) + "\n\n"

        return header + warning_text + body
