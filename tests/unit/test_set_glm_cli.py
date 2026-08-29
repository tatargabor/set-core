"""`set-glm` as a caller of the resolver, and the two things it must not get wrong.

Run as a subprocess, because what is being asserted is what an operator sees and
what the child process receives — neither of which an in-process import measures.
"""

import json
import os
import pathlib
import stat
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SET_GLM = ROOT / "bin" / "set-glm"

CONFIG = {
    "default": {"provider": "anthropic", "model": "opus"},
    "providers": {
        "anthropic": {"models": ["opus"], "requires_credential": False,
                      "default_model": "opus",
                      "credential": None, "env": {}, "args": []},
        "glm": {
            "models": ["glm-5.3", "glm-5.3-flash"],
            "requires_credential": True,
            "default_model": "glm-5.3-flash",
            "credential": {"token": "tok-abcdefghijklmnop",
                           "base_url": "https://z.invalid/api"},
            "env": {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"},
            "args": ["--autocompact", "700k"],
        },
    },
    "projects": {},
}


@pytest.fixture
def cfgdir(tmp_path):
    d = tmp_path / "set-core"
    d.mkdir()
    p = d / "providers.json"
    p.write_text(json.dumps(CONFIG))
    p.chmod(0o600)
    return d


def run(cfgdir, *args, cwd=None, extra_env=None):
    env = dict(os.environ, SET_CONFIG_DIR=str(cfgdir))
    env.update(extra_env or {})
    return subprocess.run([str(SET_GLM), *args], capture_output=True, text=True,
                          env=env, cwd=str(cwd or ROOT))


def test_print_env_shows_the_resolved_environment(cfgdir):
    r = run(cfgdir, "--print-env")
    assert r.returncode == 0, r.stderr
    assert "ANTHROPIC_BASE_URL=https://z.invalid/api" in r.stdout
    assert "--autocompact 700k" in r.stdout


def test_print_env_masks_the_credential(cfgdir):
    r = run(cfgdir, "--print-env")
    assert "tok-abcdefghijklmnop" not in r.stdout
    assert "tok-ab" in r.stdout and f"({len('tok-abcdefghijklmnop')} chars)" in r.stdout


def test_a_key_merely_ENDING_in_tokens_is_not_masked(cfgdir):
    """The substring bug, held as a test.

    `"TOKEN" in key` was true for `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, so a
    diagnostic printed `900000` as `900000…0000 (6 chars)`. It failed in the
    direction of looking careful, which is why nothing about the output said it
    was wrong. Masking is an exact key match now, and this asserts it stays one.
    """
    r = run(cfgdir, "--print-env")
    assert "CLAUDE_CODE_MAX_CONTEXT_TOKENS=900000\n" in r.stdout
    assert "chars)" not in r.stdout.split("CLAUDE_CODE_MAX_CONTEXT_TOKENS=")[1].split("\n")[0]


def test_print_env_names_the_keys_that_are_removed(cfgdir):
    r = run(cfgdir, "--print-env")
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        assert key in r.stdout.split("# unset:")[1]


def test_the_frame_switch_is_stated_and_names_the_endpoint_not_the_token(cfgdir):
    r = run(cfgdir, "--print-env")
    assert "glm-5.3-flash @ https://z.invalid/api" in r.stdout
    assert "tok-abcdefghijklmnop" not in r.stdout + r.stderr


def test_a_model_outside_the_catalogue_is_refused_before_anything_starts(cfgdir):
    r = run(cfgdir, "--model", "opus", "--print-env")
    assert r.returncode == 1
    assert "does not list model 'opus'" in r.stderr


def test_a_gateway_prefixed_model_is_refused_with_the_bare_form(cfgdir):
    r = run(cfgdir, "--model", "zai/glm-5.3", "--print-env")
    assert r.returncode == 1
    assert "gateway prefix" in r.stderr and "'glm-5.3'" in r.stderr


# AC-21 / AC-22 — the removed tier is named as removed, not reported as an absence
# AC-12
def test_a_repo_env_with_glm_keys_is_named_as_no_longer_read(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".env").write_text("GLM_TOKEN=in-the-repo\nGLM_MODEL=glm-5.3\n")
    empty = tmp_path / "empty-config"
    empty.mkdir()

    r = run(empty, "--print-env", cwd=repo)
    assert r.returncode == 1
    assert "NO LONGER READ" in r.stderr
    assert "set-providers migrate" in r.stderr
    assert str(repo / ".env") in r.stderr
    # and it must not be reported ONLY as "nothing configured"
    assert "no provider configuration" in r.stderr


def test_a_repo_env_without_glm_keys_produces_no_such_hint(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".env").write_text("DATABASE_URL=postgres://x\n")
    empty = tmp_path / "empty-config"
    empty.mkdir()

    r = run(empty, "--print-env", cwd=repo)
    assert r.returncode == 1
    assert "NO LONGER READ" not in r.stderr


def test_a_repo_env_is_never_used_as_a_credential_source(tmp_path):
    """The tier is removed, not merely deprioritised."""
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".env").write_text("GLM_TOKEN=in-the-repo\nGLM_MODEL=glm-5.3\n")
    empty = tmp_path / "empty-config"
    empty.mkdir()

    r = run(empty, "--print-env", cwd=repo)
    assert "in-the-repo" not in r.stdout
