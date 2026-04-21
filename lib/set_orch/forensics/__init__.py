"""Forensic analysis of completed orchestration runs.

Reads Claude Code session transcripts (`~/.claude/projects/<encoded-path>/*.jsonl`)
and orchestration-level logs (`~/.local/share/set-core/e2e-runs/<run-id>/`) and
surfaces filtered views that keep post-run debugging context-efficient.

All logic is read-only and project-agnostic (Layer 1 / core).
"""
from .resolver import ResolvedRun, resolve_run, NoSessionDirsError
from .digest import DigestResult, digest_run
from .timeline import Timeline, session_timeline, AmbiguousSessionPrefix, SessionNotFound
from .grep import GrepMatch, grep_content
from .orchestration import OrchestrationSummary, orchestration_summary, OrchestrationDirMissing

__all__ = [
    "ResolvedRun",
    "resolve_run",
    "NoSessionDirsError",
    "DigestResult",
    "digest_run",
    "Timeline",
    "session_timeline",
    "AmbiguousSessionPrefix",
    "SessionNotFound",
    "GrepMatch",
    "grep_content",
    "OrchestrationSummary",
    "orchestration_summary",
    "OrchestrationDirMissing",
]
