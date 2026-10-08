"""Deploy delivers search to every registered project — and never touches the
project's own search configuration.

`_deploy_kb` (lib/project/deploy.sh) is driven here through a real bash
subprocess, twice, because the deploy's promise is IDEMPOTENCE: a re-deploy of
a configured project leaves its config byte-identical, adds the `.set/` ignore
entry exactly once, and writes `set/knowledge/kb.json` never."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from conftest_kb import GIT_ID, make_repo, write

REPO_ROOT = Path(__file__).resolve().parents[2]

DEPLOY_SNIPPET = r'''
set -uo pipefail
SET_TOOLS_ROOT="{repo_root}"
SCRIPT_DIR="$SET_TOOLS_ROOT/bin"
export DRY_RUN={dry_run}
source "$SET_TOOLS_ROOT/bin/set-common.sh"
source "$SET_TOOLS_ROOT/lib/project/deploy.sh"
_deploy_kb "{project}"
exit $?
'''


def run_deploy_kb(project: Path, dry_run: bool = False) -> subprocess.CompletedProcess:
    script = DEPLOY_SNIPPET.format(repo_root=REPO_ROOT, project=project, dry_run="true" if dry_run else "false")
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=120)


def configured_project(tmp_path, name="kbdeploy") -> Path:
    root = make_repo(tmp_path, name)
    write(root / "set" / "knowledge" / "kb.json", '{"exclude": ["private/**"], "_why": "the project decided this"}\n')
    write(root / ".gitignore", ".env\n")  # no .set/ entry — deploy must add it
    return root


def test_deploy_adds_the_ignore_entry_once_and_reports_it(tmp_path):
    root = configured_project(tmp_path)
    r1 = run_deploy_kb(root)
    assert r1.returncode == 0, r1.stderr
    assert (root / ".gitignore").read_text() == ".env\n.set/\n"
    assert "Added .set/" in r1.stdout, "the add is reported"
    # Idempotence: the second run changes nothing.
    r2 = run_deploy_kb(root)
    assert r2.returncode == 0, r2.stderr
    assert (root / ".gitignore").read_text() == ".env\n.set/\n", "no duplicate entry"
    assert "already ignored" in r2.stdout


def test_redeploy_keeps_the_project_config_byte_identical(tmp_path):
    """AC: WHEN a configured project is re-deployed THEN its config is
    unchanged."""
    root = configured_project(tmp_path)
    before = (root / "set" / "knowledge" / "kb.json").read_bytes()
    run_deploy_kb(root)
    run_deploy_kb(root)
    assert (root / "set" / "knowledge" / "kb.json").read_bytes() == before


def test_deploy_never_creates_the_config(tmp_path):
    """A project with NO config gets one never from deploy — the absence is
    the zero-config default working as designed."""
    root = make_repo(tmp_path, "noconfig")
    write(root / ".gitignore", ".env\n")
    run_deploy_kb(root)
    run_deploy_kb(root)
    assert not (root / "set" / "knowledge" / "kb.json").exists()


def test_dry_run_writes_nothing_but_reports_the_plan(tmp_path):
    root = configured_project(tmp_path)
    r = run_deploy_kb(root, dry_run=True)
    assert r.returncode == 0, r.stderr
    assert (root / ".gitignore").read_text() == ".env\n"
    assert "Would add '.set/'" in r.stdout


def test_the_deployed_rule_is_at_most_15_lines():
    """AC: rule size — measured on the SOURCE; deploy copies it verbatim."""
    lines = (REPO_ROOT / "templates" / "core" / "rules" / "kb-search.md").read_text().splitlines()
    assert len(lines) <= 15
    assert lines[0].startswith("# "), "the rule opens with its statement"


def test_sources_exist_so_the_deploy_cannot_silently_deploy_nothing():
    assert (REPO_ROOT / ".claude" / "skills" / "set" / "kb" / "SKILL.md").is_file()
    assert (REPO_ROOT / "templates" / "core" / "rules" / "kb-search.md").is_file()
