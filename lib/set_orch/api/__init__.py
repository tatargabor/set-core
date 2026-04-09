from __future__ import annotations

"""Unified API package — modular FastAPI routers for the set-core web dashboard.

Modules:
    helpers         — shared utilities (project registry, state paths, worktrees)
    projects        — /api/projects CRUD + enriched stats
    orchestration   — /api/{p}/state, changes, plans, digest, coverage, requirements
    sessions        — /api/{p}/sessions, logs, activity
    sentinel        — /api/{p}/sentinel/* (supervisor control + events)
    issues          — /api/{p}/issues/* (issue management engine)
    actions         — /api/{p}/approve, stop, start, pause, resume, skip, processes
    media           — /api/{p}/screenshots, worktree logs, soniox
    learnings       — /api/{p}/review-findings, gate-stats, reflections, timeline, scoreboard
    lifecycle       — startup/shutdown, background supervisor + issue ticks
    plugins         — entry_points route discovery
"""

from fastapi import APIRouter

from .projects import router as projects_router
from .orchestration import router as orchestration_router
from .sessions import router as sessions_router
from .actions import router as actions_router
from .media import router as media_router
from ._sentinel_orch import router as sentinel_orch_router
from .learnings import router as learnings_router
from .activity import router as activity_router
from .activity_detail import router as activity_detail_router

# Unified router that combines all domain routers
router = APIRouter()
router.include_router(projects_router)
router.include_router(orchestration_router)
router.include_router(sessions_router)
router.include_router(actions_router)
router.include_router(media_router)
router.include_router(sentinel_orch_router)
router.include_router(learnings_router)
router.include_router(activity_router)
router.include_router(activity_detail_router)

# Optional routers (sentinel control, issues) — added when lifecycle starts
# These are registered dynamically in lifecycle.py since they need service instances


def include_optional_routers(parent_router: APIRouter):
    """Register optional routers that may not be available at import time."""
    try:
        from .sentinel import router as sentinel_router
        parent_router.include_router(sentinel_router)
    except ImportError:
        pass
    try:
        from .issues import router as issues_router
        parent_router.include_router(issues_router)
    except ImportError:
        pass
    try:
        from .plugins import discover_and_register
        discover_and_register(parent_router)
    except ImportError:
        pass
