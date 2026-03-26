"""Service Manager — main loop, orchestrates everything."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .config import ManagerConfig
from .supervisor import ProjectSupervisor
from ..issues.audit import AuditLog
from ..issues.deployer import DeployRunner
from ..issues.detector import DetectionBridge
from ..issues.fixer import FixRunner
from ..issues.investigator import InvestigationRunner
from ..issues.manager import IssueManager
from ..issues.policy import PolicyEngine
from ..issues.registry import IssueRegistry

logger = logging.getLogger(__name__)


class ServiceManager:
    """The main service. One instance per machine."""

    def __init__(self, config: Optional[ManagerConfig] = None):
        self.config = config or ManagerConfig.load()
        self.supervisors: dict[str, ProjectSupervisor] = {}
        self.issue_managers: dict[str, IssueManager] = {}
        self._running = False
        self._pid_file = self.config.config_dir / "manager.pid"

        # Initialize supervisors for configured projects
        for name, proj_cfg in self.config.projects.items():
            self.supervisors[name] = ProjectSupervisor(proj_cfg)

        # Initialize issue managers per project
        for name, proj_cfg in self.config.projects.items():
            self._init_issue_manager(name, proj_cfg.path)

    def _init_issue_manager(self, project_name: str, project_path: Path):
        """Create issue manager infrastructure for a project."""
        registry = IssueRegistry(project_path)
        audit = AuditLog(project_path)

        mode = self.config.projects.get(project_name)
        mode_str = mode.mode if mode else "e2e"
        policy = PolicyEngine(self.config.issues, mode=mode_str)

        investigator = InvestigationRunner(
            set_core_path=self.config.set_core_path,
            config=self.config.issues,
            audit=audit,
        )
        fixer = FixRunner(
            set_core_path=self.config.set_core_path,
            audit=audit,
        )
        deployer = DeployRunner(
            set_core_path=self.config.set_core_path,
            audit=audit,
            registered_projects={
                n: {"path": str(c.path)} for n, c in self.config.projects.items()
            },
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

        # Detection bridge (state_dir persists processed findings across restarts)
        issues_state_dir = project_path / ".set" / "issues"
        detector = DetectionBridge(
            issue_manager=mgr,
            projects={project_name: {"path": project_path}},
            state_dir=issues_state_dir,
        )
        mgr._detector = detector  # Store for tick access

    def serve(self, skip_sentinels: bool = False):
        """Run the service in foreground (blocking). Called from main thread or background thread."""
        self._write_pid_file()
        self._running = True

        # Only register signal handlers if we're in the main thread
        import threading
        if threading.current_thread() is threading.main_thread():
            self._setup_signal_handlers()

        logger.info(f"set-manager starting (PID={os.getpid()}, "
                     f"tick={self.config.tick_interval_seconds}s, "
                     f"projects={len(self.config.projects)})")

        # Auto-start sentinels for enabled projects (skip in test/thread mode)
        if not skip_sentinels:
            for name, supervisor in self.supervisors.items():
                if supervisor.config.sentinel_enabled:
                    try:
                        supervisor.start_sentinel()
                    except Exception as e:
                        logger.error(f"Failed to start sentinel for {name}: {e}")

        try:
            while self._running:
                self._tick()
                time.sleep(self.config.tick_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self._shutdown()

    def _tick(self):
        """Main tick — called every N seconds."""
        # 1. Health check all projects
        for name, supervisor in self.supervisors.items():
            actions = supervisor.health_check()
            for action in actions:
                logger.warning(f"[{name}] {action}")

        # 2. Scan for new issues from sentinels
        for name, mgr in self.issue_managers.items():
            if hasattr(mgr, '_detector'):
                mgr._detector.scan_all_projects()

        # 3. Process issue queues
        for name, mgr in self.issue_managers.items():
            if mgr.enabled:
                try:
                    mgr.tick()
                except Exception as e:
                    logger.error(f"[{name}] Issue manager tick failed: {e}")

    def _shutdown(self):
        """Clean shutdown — stop all supervised processes."""
        logger.info("Stopping all supervised processes...")
        for name, supervisor in self.supervisors.items():
            supervisor.stop_sentinel()
            supervisor.stop_orchestration()
        self._remove_pid_file()
        logger.info("set-manager stopped")

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        self._running = False

    def _write_pid_file(self):
        self.config.config_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file.write_text(str(os.getpid()))

    def _remove_pid_file(self):
        if self._pid_file.exists():
            self._pid_file.unlink(missing_ok=True)

    def is_running(self) -> bool:
        """Check if another manager instance is running."""
        if not self._pid_file.exists():
            return False
        try:
            pid = int(self._pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            return False

    # --- Project management ---

    def add_project(self, name: str, path: Path, mode: str = "e2e"):
        cfg = self.config.add_project(name, path, mode)
        self.supervisors[name] = ProjectSupervisor(cfg)
        self._init_issue_manager(name, path)
        self.config.save()

    def remove_project(self, name: str):
        sup = self.supervisors.pop(name, None)
        if sup:
            sup.stop_sentinel()
            sup.stop_orchestration()
        self.issue_managers.pop(name, None)
        self.config.remove_project(name)
        self.config.save()

    # --- Status ---

    def status(self) -> dict:
        return {
            "pid": os.getpid(),
            "running": self._running,
            "tick_interval": self.config.tick_interval_seconds,
            "port": self.config.port,
            "projects": {
                name: sup.status() for name, sup in self.supervisors.items()
            },
            "issues": {
                name: mgr.registry.stats()
                for name, mgr in self.issue_managers.items()
            },
        }

    def project_status(self, name: str) -> Optional[dict]:
        sup = self.supervisors.get(name)
        mgr = self.issue_managers.get(name)
        if not sup:
            return None
        result = sup.status()
        if mgr:
            result["issue_stats"] = mgr.registry.stats()
        return result
