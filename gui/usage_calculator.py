"""
Usage Calculator - Parse local Claude JSONL files to calculate token usage

This module provides cross-platform local usage calculation without requiring
authentication by parsing the JSONL files Claude Code writes to ~/.claude/projects/
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
import json

__all__ = ["UsageCalculator", "UsageData", "MODEL_PRICES"]

# Per-model token prices in USD per million tokens (as of Feb 2026)
MODEL_PRICES = {
    "claude-opus-4": {
        "input": 15.0, "output": 75.0,
        "cache_read": 3.75, "cache_creation": 18.75,
    },
    "claude-sonnet-4": {
        "input": 3.0, "output": 15.0,
        "cache_read": 0.30, "cache_creation": 3.75,
    },
    "claude-haiku-4": {
        "input": 0.80, "output": 4.0,
        "cache_read": 0.08, "cache_creation": 1.0,
    },
}

# Default prices for unknown models (use sonnet pricing as conservative middle)
_DEFAULT_PRICES = MODEL_PRICES["claude-sonnet-4"]


def _normalize_model(model: str) -> str:
    """Normalize model name to match MODEL_PRICES keys."""
    m = model.lower()
    if "opus" in m:
        return "claude-opus-4"
    if "haiku" in m:
        return "claude-haiku-4"
    if "sonnet" in m:
        return "claude-sonnet-4"
    return model


@dataclass
class UsageData:
    """Aggregated token usage data"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    per_model: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def api_tokens(self) -> int:
        """Tokens sent/received (input + output only, excludes cache)"""
        return self.input_tokens + self.output_tokens

    @property
    def total_tokens(self) -> int:
        """Total tokens including cache operations"""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    def __add__(self, other: "UsageData") -> "UsageData":
        merged = defaultdict(lambda: defaultdict(int))
        for model, counts in self.per_model.items():
            for k, v in counts.items():
                merged[model][k] += v
        for model, counts in other.per_model.items():
            for k, v in counts.items():
                merged[model][k] += v
        return UsageData(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            per_model={m: dict(c) for m, c in merged.items()},
        )

    def estimate_cost(self) -> float:
        """Estimate USD cost based on per-model token counts."""
        if not self.per_model:
            # No model info — use default prices on aggregate
            prices = _DEFAULT_PRICES
            return (
                self.input_tokens * prices["input"]
                + self.output_tokens * prices["output"]
                + self.cache_read_tokens * prices["cache_read"]
                + self.cache_creation_tokens * prices["cache_creation"]
            ) / 1_000_000

        total = 0.0
        for model, counts in self.per_model.items():
            norm = _normalize_model(model)
            prices = MODEL_PRICES.get(norm, _DEFAULT_PRICES)
            total += (
                counts.get("input_tokens", 0) * prices["input"]
                + counts.get("output_tokens", 0) * prices["output"]
                + counts.get("cache_read_tokens", 0) * prices["cache_read"]
                + counts.get("cache_creation_tokens", 0) * prices["cache_creation"]
            ) / 1_000_000
        return total


class UsageCalculator:
    """Calculate token usage from local Claude JSONL files"""

    def __init__(self, claude_dir: Optional[Path] = None, project_dir: Optional[str] = None):
        """
        Initialize calculator.

        Args:
            claude_dir: Path to Claude config directory. Defaults to ~/.claude/
            project_dir: Optional project directory name to filter by.
                When set, only JSONL files from ~/.claude/projects/<project_dir>/ are scanned.
        """
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.project_dir = project_dir

    def get_projects_dir(self) -> Path:
        """Get the projects directory path"""
        return self.claude_dir / "projects"

    def iter_jsonl_files(self):
        """Iterate over all JSONL files in projects directory (recursive, includes subagent sessions)"""
        projects_dir = self.get_projects_dir()
        if not projects_dir.exists():
            return

        if self.project_dir:
            # Scoped: only scan the specific project directory
            scoped_dir = projects_dir / self.project_dir
            if scoped_dir.is_dir():
                for jsonl_file in scoped_dir.rglob("*.jsonl"):
                    yield jsonl_file
        else:
            # Unfiltered: scan all project directories
            for session_dir in projects_dir.iterdir():
                if session_dir.is_dir():
                    for jsonl_file in session_dir.rglob("*.jsonl"):
                        yield jsonl_file

    def parse_usage_line(self, line: str) -> Tuple[Optional[UsageData], Optional[datetime], Optional[str]]:
        """
        Parse a single JSONL line for usage data.

        Returns:
            Tuple of (UsageData, timestamp, model) or (None, None, None) if parsing fails
        """
        try:
            data = json.loads(line)

            # Extract usage from message.usage
            message = data.get("message", {})
            usage = message.get("usage", {})
            if not usage:
                return None, None, None

            # Extract timestamp
            ts_str = data.get("timestamp")
            if not ts_str:
                return None, None, None

            # Parse ISO format timestamp
            timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

            # Extract model name
            model = message.get("model") or data.get("model") or "unknown"

            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_create = usage.get("cache_creation_input_tokens", 0)

            per_model = {model: {
                "input_tokens": inp,
                "output_tokens": out,
                "cache_read_tokens": cache_read,
                "cache_creation_tokens": cache_create,
            }}

            return UsageData(
                input_tokens=inp,
                output_tokens=out,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_create,
                per_model=per_model,
            ), timestamp, model

        except (json.JSONDecodeError, ValueError, KeyError):
            return None, None, None

    def calculate_usage(
        self,
        window_hours: Optional[float] = None,
        since: Optional[datetime] = None
    ) -> UsageData:
        """
        Calculate total usage within a time window.

        Args:
            window_hours: Hours to look back (e.g., 5 for 5h window)
            since: Specific datetime to calculate from (overrides window_hours)

        Returns:
            Aggregated UsageData for the time window
        """
        if since is None and window_hours is not None:
            since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        total = UsageData()

        for jsonl_file in self.iter_jsonl_files():
            try:
                with open(jsonl_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        usage, timestamp, _model = self.parse_usage_line(line)
                        if usage is None or timestamp is None:
                            continue

                        # Filter by time window (handle naive/aware mismatch)
                        if since is not None:
                            cmp_ts = timestamp
                            cmp_since = since
                            if cmp_ts.tzinfo is not None and cmp_since.tzinfo is None:
                                cmp_ts = cmp_ts.replace(tzinfo=None)
                            elif cmp_ts.tzinfo is None and cmp_since.tzinfo is not None:
                                cmp_since = cmp_since.replace(tzinfo=None)
                            if cmp_ts < cmp_since:
                                continue

                        total = total + usage

            except (IOError, OSError):
                continue  # Skip files we can't read

        return total

    def calculate_5h_usage(self) -> UsageData:
        """Calculate usage in the last 5 hours"""
        return self.calculate_usage(window_hours=5)

    def calculate_weekly_usage(self) -> UsageData:
        """Calculate usage in the last 7 days"""
        return self.calculate_usage(window_hours=7 * 24)

    def estimate_percentage(
        self,
        usage: UsageData,
        limit: int
    ) -> float:
        """
        Estimate usage percentage based on a limit.

        Args:
            usage: UsageData to calculate percentage for
            limit: Token limit to compare against

        Returns:
            Percentage (0-100+) of limit used
        """
        if limit <= 0:
            return 0.0
        return (usage.api_tokens / limit) * 100

    def get_usage_summary(
        self,
        limit_5h: int = 500_000,
        limit_weekly: int = 5_000_000
    ) -> dict:
        """
        Get a usage summary matching the format expected by UsageWorker.

        Args:
            limit_5h: Estimated 5-hour token limit
            limit_weekly: Estimated weekly token limit

        Returns:
            Dictionary with usage data in API-compatible format
        """
        usage_5h = self.calculate_5h_usage()
        usage_weekly = self.calculate_weekly_usage()

        session_pct = self.estimate_percentage(usage_5h, limit_5h)
        weekly_pct = self.estimate_percentage(usage_weekly, limit_weekly)

        return {
            "available": True,
            "session_pct": session_pct,
            "session_reset": None,  # No reset time available from local data
            "session_burn": None,   # Can't calculate burn rate without reset time
            "session_tokens": usage_5h.api_tokens,
            "weekly_pct": weekly_pct,
            "weekly_reset": None,
            "weekly_burn": None,
            "weekly_tokens": usage_weekly.api_tokens,
            "estimated_cost_usd": usage_weekly.estimate_cost(),
            "source": "local",
            "is_estimated": True,
        }
