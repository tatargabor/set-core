"""set-manager CLI — service management commands."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

from .config import ManagerConfig


@click.group()
def cli():
    """set-manager — control plane for set-core."""
    pass


@cli.command()
@click.option("--config", type=click.Path(exists=True), default=None, help="Config file path")
@click.option("--port", type=int, default=None, help="API port (default: 3112)")
def serve(config, port):
    """Run set-manager in foreground. (DEPRECATED — use 'set-core serve' instead)"""
    import warnings
    warnings.warn(
        "set-manager serve is deprecated. Use 'set-core serve' instead, "
        "which runs a unified server with orchestration API, sentinel, and issues.",
        DeprecationWarning,
        stacklevel=2,
    )
    click.echo("⚠️  DEPRECATED: Use 'set-core serve' for the unified server.", err=True)
    click.echo("   set-manager serve will be removed in a future release.", err=True)
    click.echo("", err=True)

    from .service import ServiceManager
    from .api import create_api
    from aiohttp import web
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    cfg = ManagerConfig.load(Path(config) if config else None)
    if port:
        cfg.port = port

    service = ServiceManager(cfg)

    # Check for duplicate instance
    if service.is_running():
        click.echo("Error: Another set-manager instance is already running.", err=True)
        sys.exit(1)

    # Create API app
    app = create_api(service)

    # Run tick loop in background thread + API server in main thread
    import threading

    def tick_loop():
        service.serve(skip_sentinels=True)

    tick_thread = threading.Thread(target=tick_loop, daemon=True)
    tick_thread.start()

    click.echo(f"set-manager serving on http://localhost:{cfg.port}")
    click.echo(f"  Projects: {len(cfg.projects)}")
    click.echo(f"  Tick interval: {cfg.tick_interval_seconds}s")
    click.echo(f"  Console: http://localhost:3111/manager (requires set-web)")
    web.run_app(app, port=cfg.port, print=None)


@cli.command()
def start():
    """Enable and start set-manager systemd service."""
    _systemctl("enable", "--now", "set-manager")
    click.echo("set-manager started")


@cli.command()
def stop():
    """Stop set-manager systemd service."""
    _systemctl("stop", "set-manager")
    click.echo("set-manager stopped")


@cli.command()
def status():
    """Show set-manager status."""
    cfg = ManagerConfig.load()
    pid_file = cfg.config_dir / "manager.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            click.echo(f"set-manager: running (PID={pid})")
        except (ValueError, ProcessLookupError):
            click.echo("set-manager: not running (stale PID file)")
    else:
        click.echo("set-manager: not running")

    click.echo(f"Config: {cfg.config_dir / 'config.yaml'}")
    click.echo(f"Projects: {len(cfg.projects)}")
    for name, proj in cfg.projects.items():
        click.echo(f"  {name}: {proj.path} [{proj.mode}]")


@cli.group()
def project():
    """Manage projects."""
    pass


@project.command("add")
@click.argument("name")
@click.argument("path", type=click.Path())
@click.option("--mode", type=click.Choice(["e2e", "production", "development"]), default="e2e")
def project_add(name, path, mode):
    """Register a project."""
    cfg = ManagerConfig.load()
    cfg.add_project(name, Path(path).resolve(), mode)
    cfg.save()
    click.echo(f"Project '{name}' added ({mode})")


@project.command("remove")
@click.argument("name")
def project_remove(name):
    """Remove a project."""
    cfg = ManagerConfig.load()
    cfg.remove_project(name)
    cfg.save()
    click.echo(f"Project '{name}' removed")


@project.command("list")
def project_list():
    """List registered projects."""
    cfg = ManagerConfig.load()
    if not cfg.projects:
        click.echo("No projects registered")
        return
    for name, proj in cfg.projects.items():
        click.echo(f"  {name}: {proj.path} [{proj.mode}]")


@cli.command()
def install():
    """Install systemd user service files."""
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)

    # set-manager.service
    manager_unit = unit_dir / "set-manager.service"
    manager_unit.write_text(MANAGER_UNIT.format(
        python=sys.executable,
        home=Path.home(),
    ))
    click.echo(f"Created {manager_unit}")

    _systemctl("daemon-reload")
    click.echo("Run 'set-manager start' to enable and start the service")


def _systemctl(*args):
    """Run systemctl --user command."""
    subprocess.run(["systemctl", "--user", *args], check=True)


MANAGER_UNIT = """[Unit]
Description=Set-Core Management Service
After=network.target

[Service]
Type=simple
ExecStart={python} -m set_orch.manager.cli serve
Restart=always
RestartSec=5
WorkingDirectory={home}

[Install]
WantedBy=default.target
"""


def main():
    cli()


if __name__ == "__main__":
    main()
