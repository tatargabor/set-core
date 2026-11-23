"""`set-project register` — a data repository enters the registry without
anything being deployed into it, and stays undeployed: `init` refuses it and
install.sh's per-project redeploy skips it."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SET_PROJECT = REPO / "bin" / "set-project"


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "projects.json").write_text(json.dumps({"default": "main", "projects": {}}))
    # SET_MANAGER_URL points at a closed port: a deploying `init` also registers the
    # project with the running dashboard, which writes the REAL registry — measured
    # 2026-11-12, when a mutant run left a pytest repo in this machine's projects.json.
    return {**os.environ, "SET_CONFIG_DIR": str(cfg), "SET_MANAGER_URL": "http://127.0.0.1:9"}


def registry(env) -> dict:
    return json.loads((Path(env["SET_CONFIG_DIR"]) / "projects.json").read_text())


def data_repo(tmp_path, name="corpus") -> Path:
    d = tmp_path / name
    (d / "wiki").mkdir(parents=True)
    (d / "wiki" / "page.md").write_text("# A page\n")
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    subprocess.run(["git", "-C", str(d), "add", "."], check=True)
    subprocess.run(["git", "-C", str(d), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
    return d


def sp(env, *args, cwd=None):
    return subprocess.run([str(SET_PROJECT), *args], env=env, cwd=cwd, capture_output=True, text=True, timeout=120)


def untouched(repo: Path) -> None:
    """No deploy: nothing tracked or trackable is written. The one machine-local file the
    relay wiring adds (863a7a18, `relay-wire-on-register`) is `.claude/settings.local.json`,
    kept out of git via `.git/info/exclude` — allowed, and nothing else under `.claude/`."""
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout
    assert status == "", f"nothing may be written into the repository:\n{status}"
    claude = repo / ".claude"
    extra = sorted(str(f.relative_to(repo)) for f in claude.rglob("*") if f.is_file()) if claude.exists() else []
    assert extra in ([], [".claude/settings.local.json"]), f"only the machine-local relay file may appear: {extra}"


def test_register_adds_a_no_deploy_entry_and_writes_nothing_into_the_repo(env, tmp_path):
    repo = data_repo(tmp_path)
    r = sp(env, "register", "--path", str(repo))
    assert r.returncode == 0, r.stderr
    entry = registry(env)["projects"]["corpus"]
    assert entry["path"] == str(repo) and entry["deploy"] is False and entry["addedAt"]
    assert registry(env)["default"] == "main", "a data repository never becomes the default"
    untouched(repo)


def test_register_from_inside_the_repo_with_a_name(env, tmp_path):
    repo = data_repo(tmp_path, "checkout-dir")
    r = sp(env, "register", "--name", "shared-corpus", "--no-deploy", cwd=repo / "wiki")
    assert r.returncode == 0, r.stderr
    assert registry(env)["projects"]["shared-corpus"]["path"] == str(repo), "resolved to the repo root"


def test_register_is_idempotent_and_marks_a_hand_made_entry(env, tmp_path):
    repo = data_repo(tmp_path)
    reg = registry(env)
    reg["projects"]["corpus"] = {"path": str(repo), "addedAt": "2026-11-12T00:00:00Z"}  # added by hand
    (Path(env["SET_CONFIG_DIR"]) / "projects.json").write_text(json.dumps(reg))
    r = sp(env, "register", "--path", str(repo))
    assert r.returncode == 0 and "marked no-deploy" in r.stdout + r.stderr
    assert registry(env)["projects"]["corpus"] == {"path": str(repo), "addedAt": "2026-11-12T00:00:00Z", "deploy": False}
    again = sp(env, "register", "--path", str(repo))
    assert again.returncode == 0 and "nothing to do" in again.stdout + again.stderr


def test_register_refuses_a_name_taken_by_another_path(env, tmp_path):
    a, b = data_repo(tmp_path, "a"), data_repo(tmp_path, "b")
    assert sp(env, "register", "--name", "corpus", "--path", str(a)).returncode == 0
    r = sp(env, "register", "--name", "corpus", "--path", str(b))
    assert r.returncode == 1 and "already used" in r.stdout + r.stderr
    assert registry(env)["projects"]["corpus"]["path"] == str(a)


def test_register_dry_run_changes_nothing(env, tmp_path):
    repo = data_repo(tmp_path)
    before = registry(env)
    r = sp(env, "register", "--path", str(repo), "--dry-run")
    assert r.returncode == 0 and "Would register" in r.stdout + r.stderr
    assert registry(env) == before


def test_register_outside_a_git_repository_fails(env, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    r = sp(env, "register", "--path", str(plain))
    assert r.returncode == 1 and "Not a git repository" in r.stdout + r.stderr


def test_init_refuses_a_no_deploy_repository_whatever_name_it_is_given(env, tmp_path):
    repo = data_repo(tmp_path)
    assert sp(env, "register", "--name", "shared-corpus", "--path", str(repo)).returncode == 0
    for args in ((), ("--name", "other-name")):
        r = sp(env, "init", *args, cwd=repo)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "no deploy" in r.stdout + r.stderr and "set-project remove shared-corpus" in r.stdout + r.stderr
        untouched(repo)
    assert set(registry(env)["projects"]) == {"shared-corpus"}, "init registered nothing new either"


def test_install_redeploy_loop_skips_no_deploy_entries(tmp_path):
    """install.sh runs `set-project init` in every path its jq filter yields; the filter
    must leave the no-deploy entries out. Run the filter exactly as install.sh carries it."""
    text = (REPO / "install.sh").read_text()
    m = re.search(r"project_paths=\$\(jq -r '([^']+)' \"\$projects_file\"", text)
    assert m, "install_projects' jq filter not found"
    sample = tmp_path / "projects.json"
    sample.write_text(json.dumps({"projects": {
        "app": {"path": "/x/app"},
        "corpus": {"path": "/x/corpus", "deploy": False},
        "legacy": {"path": "/x/legacy", "deploy": True},
    }}))
    out = subprocess.run(["jq", "-r", m.group(1), str(sample)], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["/x/app", "/x/legacy"]


# B-194: git reports the RESOLVED path, the registry may hold a symlink spelling.

def linked(tmp_path, repo: Path, name="link") -> Path:
    link = tmp_path / name
    link.symlink_to(repo, target_is_directory=True)
    return link


def test_init_dry_run_in_a_repo_registered_through_a_symlink_proceeds(env, tmp_path):
    repo = data_repo(tmp_path, "real")
    link = linked(tmp_path, repo, "app")
    reg = registry(env)
    reg["projects"]["app"] = {"path": str(link), "addedAt": "2026-11-23T00:00:00Z"}
    (Path(env["SET_CONFIG_DIR"]) / "projects.json").write_text(json.dumps(reg))
    r = sp(env, "init", "--name", "app", "--dry-run", cwd=link)
    out = r.stdout + r.stderr
    assert "already used for" not in out, out
    assert r.returncode == 0, out
    assert set(registry(env)["projects"]) == {"app"}


def test_init_refuses_a_no_deploy_repo_registered_through_a_symlink(env, tmp_path):
    repo = data_repo(tmp_path, "real")
    link = linked(tmp_path, repo, "corpus")
    assert sp(env, "register", "--name", "corpus", "--path", str(link)).returncode == 0
    # register resolves via git, so force the symlink spelling into the entry
    reg = registry(env)
    reg["projects"]["corpus"]["path"] = str(link)
    (Path(env["SET_CONFIG_DIR"]) / "projects.json").write_text(json.dumps(reg))
    r = sp(env, "init", "--name", "other-name", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "no deploy" in r.stdout + r.stderr
    untouched(repo)


def test_register_through_the_other_spelling_is_idempotent(env, tmp_path):
    repo = data_repo(tmp_path, "real")
    link = linked(tmp_path, repo, "corpus")
    reg = registry(env)
    reg["projects"]["corpus"] = {"path": str(link), "addedAt": "2026-11-23T00:00:00Z", "deploy": False}
    (Path(env["SET_CONFIG_DIR"]) / "projects.json").write_text(json.dumps(reg))
    r = sp(env, "register", "--name", "corpus", "--path", str(repo))
    assert r.returncode == 0 and "nothing to do" in r.stdout + r.stderr, r.stdout + r.stderr
