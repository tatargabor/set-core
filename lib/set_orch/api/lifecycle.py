"""Lifecycle management — startup/shutdown, background supervisor + issue ticks.

Initializes supervisors and issue managers for registered projects,
runs tick loops as asyncio background tasks.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Global service reference (initialized at startup)
_service = None


class UnifiedService:
    """Lightweight service container — supervisors + issue managers for all projects.

    Replaces the old manager/service.py ServiceManager by reusing its components
    without the aiohttp dependency.
    """

    def __init__(self):
        self.supervisors: dict = {}
        self.issue_managers: dict = {}
        self._tick_tasks: list[asyncio.Task] = []

    def init_from_registry(self):
        """Initialize supervisors and issue managers from projects.json."""
        from .helpers import _load_projects
        from ..manager.supervisor import ProjectSupervisor
        from ..manager.config import ProjectConfig

        projects = _load_projects()
        for p in projects:
            name = p.get("name", "")
            path_str = p.get("path", "")
            if not name or not path_str:
                continue
            path = Path(path_str)
            if not path.is_dir():
                continue

            try:
                # Create supervisor
                cfg = ProjectConfig(
                    name=name,
                    path=path,
                    mode=p.get("project_type", p.get("mode", "e2e")),
                )
                self.supervisors[name] = ProjectSupervisor(cfg)

                # Create issue manager
                self._init_issue_manager(name, path)
            except Exception as e:
                logger.warning("Failed to init project %s: %s", name, e)

        logger.info("Unified service initialized: %d projects", len(self.supervisors))

    def _init_issue_manager(self, project_name: str, project_path: Path):
        """Create issue manager infrastructure for a project."""
        try:
            from ..issues.registry import IssueRegistry
            from ..issues.audit import AuditLog
            from ..issues.policy import PolicyEngine
            from ..issues.investigator import InvestigationRunner
            from ..issues.fixer import FixRunner
            from ..issues.deployer import DeployRunner
            from ..issues.manager import IssueManager
            from ..issues.detector import DetectionBridge

            registry = IssueRegistry(project_path)
            audit = AuditLog(project_path)

            # Use default config for now (issues config from manager config)
            try:
                from ..manager.config import ManagerConfig
                mgr_config = ManagerConfig.load()
                issues_config = mgr_config.issues
                set_core_path = mgr_config.set_core_path
            except Exception:
                from ..issues.policy import IssuesPolicyConfig
                issues_config = IssuesPolicyConfig()
                set_core_path = Path(__file__).resolve().parent.parent.parent.parent

            policy = PolicyEngine(issues_config, mode="e2e")
            investigator = InvestigationRunner(
                set_core_path=set_core_path,
                config=issues_config,
                audit=audit,
            )
            fixer = FixRunner(set_core_path=set_core_path, audit=audit)
            deployer = DeployRunner(
                set_core_path=set_core_path,
                audit=audit,
                registered_projects={project_name: {"path": str(project_path)}},
            )

            mgr = IssueManager(
                registry=registry,
                audit=audit,
                policy=policy,
                investigator=investigator,
                fixer=fixer,
                deployer=deployer,
            )
            self.issue_managers[project_name] = mgr

            # Detection bridge
            issues_state_dir = project_path / ".set" / "issues"
            detector = DetectionBridge(
                issue_manager=mgr,
                projects={project_name: {"path": project_path}},
                state_dir=issues_state_dir,
            )
            mgr._detector = detector
        except Exception as e:
            logger.warning("Failed to init issue manager for %s: %s", project_name, e)

    def add_project(self, name: str, path: Path, mode: str = "e2e"):
        """Dynamically register a new project."""
        from ..manager.supervisor import ProjectSupervisor
        from ..manager.config import ProjectConfig

        cfg = ProjectConfig(name=name, path=path, mode=mode)
        self.supervisors[name] = ProjectSupervisor(cfg)
        self._init_issue_manager(name, path)
        logger.info("Added project %s at %s", name, path)

    def remove_project(self, name: str):
        """Remove a project."""
        sup = self.supervisors.pop(name, None)
        if sup:
            sup.stop_sentinel()
        self.issue_managers.pop(name, None)
        logger.info("Removed project %s", name)

    async def start_tick_loops(self, tick_interval: float = 30.0):
        """Start background tick loops for health checks and issue processing."""
        task = asyncio.create_task(self._tick_loop(tick_interval))
        self._tick_tasks.append(task)

    async def _tick_loop(self, interval: float):
        """Main tick loop — health checks + issue processing."""
        while True:
            try:
                await asyncio.sleep(interval)
                self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Tick loop error (continuing): %s", e)

    def _tick(self):
        """Single tick — health check all projects, scan for issues, process queues."""
        # 1. Health check
        for name, supervisor in self.supervisors.items():
            try:
                actions = supervisor.health_check()
                for action in actions:
                    logger.warning("[%s] %s", name, action)
            except Exception as e:
                logger.debug("Health check failed for %s: %s", name, e)

        # 2. Scan for new issues
        for name, mgr in self.issue_managers.items():
            if hasattr(mgr, '_detector'):
                try:
                    mgr._detector.scan_all_projects()
                except Exception as e:
                    logger.debug("Issue scan failed for %s: %s", name, e)

        # 3. Process issue queues
        for name, mgr in self.issue_managers.items():
            if mgr.enabled:
                try:
                    mgr.tick()
                except Exception as e:
                    logger.error("[%s] Issue manager tick failed: %s", name, e)

    async def shutdown(self):
        """Stop tick loops only — leave supervised sentinels alive.

        Sentinels run in their own process groups and manage long E2E runs
        that can take hours. Killing them when set-web restarts destroys
        in-flight iterations and branches (observed: craftbrew-run
        20260415-0146 lost 5h of cart-and-session work because a set-web
        `systemctl restart` triggered this path mid-run). When set-web
        starts back up it re-attaches via the per-project status markers,
        so the sentinels survive the restart transparently.
        """
        for task in self._tick_tasks:
            task.cancel()
        logger.info("Unified service stopped (sentinels left running)")

    def status(self) -> dict:
        """Overall service status."""
        import os
        return {
            "pid": os.getpid(),
            "projects": {
                name: sup.status() for name, sup in self.supervisors.items()
            },
            "issues": {
                name: mgr.registry.stats()
                for name, mgr in self.issue_managers.items()
            },
        }


def get_service() -> UnifiedService | None:
    """Get the global service instance."""
    return _service


async def startup(app=None):
    """Initialize the unified service and start background tasks."""
    global _service

    _service = UnifiedService()
    _service.init_from_registry()

    # Inject service into sentinel/issues routers
    from . import sentinel as sentinel_mod
    from . import issues as issues_mod
    sentinel_mod.set_service(_service)
    issues_mod.set_service(_service)

    # Start tick loops
    await _service.start_tick_loops()

    # Section 3.5: backfill `spec_lineage_id` + `phase` onto pre-existing
    # archive entries the first time we touch each project.  Idempotent
    # via per-project marker file; never blocks startup on failure.
    try:
        from set_orch.migrations.backfill_lineage import maybe_migrate_on_startup
        for project_name, sup in _service.supervisors.items():
            try:
                maybe_migrate_on_startup(str(sup.config.path))
            except Exception:
                logger.warning(
                    "lineage backfill: failed for project %s", project_name,
                    exc_info=True,
                )
    except Exception:
        logger.warning("lineage backfill: skipped (import failed)", exc_info=True)

    logger.info("Unified service started with %d projects", len(_service.supervisors))


async def shutdown():
    """Stop the unified service."""
    global _service
    if _service:
        await _service.shutdown()
        _service = None
