"""Deploy Runner — deploy fixes to target environments via set-project init."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from .audit import AuditLog
from .models import Issue, now_iso

logger = logging.getLogger(__name__)


class DeployRunner:
    """Deploys fix to target environments via set-project init."""

    def __init__(
        self,
        set_core_path: Path,
        audit: AuditLog,
        deploy_to_all: bool = False,
        registered_projects: Optional[dict] = None,
    ):
        self.set_core_path = set_core_path
        self.audit = audit
        self.deploy_to_all = deploy_to_all
        self.registered_projects = registered_projects or {}
        self._processes: dict[str, list[subprocess.Popen]] = {}
        self._targets: dict[str, list[str]] = {}

    def deploy(self, issue: Issue):
        """Run set-project init on target environments."""
        targets = self._get_deploy_targets(issue)
        self._targets[issue.id] = [str(t) for t in targets]

        procs = []
        for target in targets:
            try:
                proc = subprocess.Popen(
                    ["set-project", "init", str(target)],
                    cwd=str(self.set_core_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                procs.append(proc)
                logger.info(f"Deploy started for {issue.id} → {target}")
            except FileNotFoundError:
                logger.error(f"set-project not found — cannot deploy to {target}")
                self.audit.log(issue.id, "deploy_failed",
                               target=str(target), error="set-project not found")

        self._processes[issue.id] = procs
        self.audit.log(issue.id, "deploy_started",
                       targets=[str(t) for t in targets])

    def is_done(self, issue: Issue) -> bool:
        """Check if all deploy processes have completed."""
        procs = self._processes.get(issue.id, [])
        if not procs:
            return True
        return all(p.poll() is not None for p in procs)

    def succeeded(self, issue: Issue) -> bool:
        """Check if all deploy processes succeeded."""
        procs = self._processes.get(issue.id, [])
        if not procs:
            return True  # No deploys needed = success
        success = all(p.returncode == 0 for p in procs)
        if success:
            self.audit.log(issue.id, "deploy_complete",
                           targets=self._targets.get(issue.id, []))
        else:
            failed = [
                self._targets.get(issue.id, ["?"])[i]
                for i, p in enumerate(procs)
                if p.returncode != 0
            ]
            self.audit.log(issue.id, "deploy_partial_failure", failed_targets=failed)
        self._processes.pop(issue.id, None)
        self._targets.pop(issue.id, None)
        return success

    def _get_deploy_targets(self, issue: Issue) -> list[Path]:
        """Determine which projects need the fix deployed."""
        targets = []

        # Source environment always gets the update
        if issue.environment_path:
            targets.append(Path(issue.environment_path))

        # Optionally deploy to all registered projects
        if self.deploy_to_all and self.registered_projects:
            for proj_config in self.registered_projects.values():
                path = Path(proj_config.get("path", "")) if isinstance(proj_config, dict) else Path(str(proj_config))
                if path and path not in targets and path.exists():
                    targets.append(path)

        return targets
