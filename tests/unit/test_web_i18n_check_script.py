"""Synthetic fixture test for scripts/check-i18n-completeness.ts.

See OpenSpec change: fix-e2e-infra-systematic (T1.1.5).

Builds a minimal fake project on disk, runs the script via `npx tsx` (or skips
if tsx is unavailable), asserts exit code 0 when keys are complete and
non-zero when keys are missing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / (
    "modules/web/set_project_web/templates/nextjs/scripts/check-i18n-completeness.ts"
)


def _tsx_available() -> bool:
    return shutil.which("npx") is not None and shutil.which("node") is not None


pytestmark = pytest.mark.skipif(
    not _tsx_available(),
    reason="npx/node not available — can't run tsx script",
)


@pytest.fixture
def fake_project(tmp_path: Path):
    """Create a minimal Next.js-like project tree with messages/ + src/."""
    (tmp_path / "messages").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "scripts").mkdir()
    shutil.copy(_SCRIPT, tmp_path / "scripts" / "check-i18n-completeness.ts")
    return tmp_path


def _run(root: Path) -> subprocess.CompletedProcess:
    # Reuse whatever tsx the harness can resolve via npx.
    return subprocess.run(
        ["npx", "--yes", "tsx", "scripts/check-i18n-completeness.ts"],
        cwd=root, capture_output=True, text=True, timeout=120,
        env={**os.environ, "SET_I18N_CHECK_ROOT": str(root)},
    )


def test_complete_keys_pass(fake_project: Path):
    (fake_project / "messages" / "hu.json").write_text(
        json.dumps({"home": {"title": "Üdv"}, "nav": {"home": "Főoldal"}})
    )
    (fake_project / "messages" / "en.json").write_text(
        json.dumps({"home": {"title": "Welcome"}, "nav": {"home": "Home"}})
    )
    (fake_project / "src" / "Home.tsx").write_text(
        """import { useTranslations } from 'next-intl';
export default function Home() {
  const t = useTranslations('home');
  const n = useTranslations('nav');
  return <div>{t('title')}{n('home')}</div>;
}
"""
    )
    result = _run(fake_project)
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_missing_key_fails(fake_project: Path):
    (fake_project / "messages" / "hu.json").write_text(
        json.dumps({"home": {"title": "Üdv"}})
    )
    (fake_project / "messages" / "en.json").write_text(
        json.dumps({"home": {"title": "Welcome"}})
    )
    (fake_project / "src" / "Home.tsx").write_text(
        """import { useTranslations } from 'next-intl';
export default function Home() {
  const t = useTranslations('home');
  return <div>{t('title')}{t('missingKey')}</div>;
}
"""
    )
    result = _run(fake_project)
    assert result.returncode == 1, (
        f"Expected exit 1 (missing key), got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "missingKey" in combined or "home.missingKey" in combined, combined


def test_unbalanced_locales_fail(fake_project: Path):
    (fake_project / "messages" / "hu.json").write_text(
        json.dumps({"home": {"title": "Üdv", "subtitle": "Alcím"}})
    )
    # en.json missing subtitle
    (fake_project / "messages" / "en.json").write_text(
        json.dumps({"home": {"title": "Welcome"}})
    )
    (fake_project / "src" / "Home.tsx").write_text(
        """import { useTranslations } from 'next-intl';
export default function Home() {
  const t = useTranslations('home');
  return <div>{t('title')}{t('subtitle')}</div>;
}
"""
    )
    result = _run(fake_project)
    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "subtitle" in combined, combined
