"""Test: global-setup.ts Prisma schema-hash cache skips db push when unchanged.

See OpenSpec change: fix-e2e-infra-systematic (T1.4.2).

`npx prisma db push --force-reset` takes ~30s on a realistic schema. It runs
on every worktree's e2e gate. When the schema hasn't changed since the last
run (common on feature iterations), skipping the push saves the full ~30s.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE = (
    _ROOT / "modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts"
)


def test_schema_hash_cache_present_in_global_setup():
    src = _TEMPLATE.read_text()
    # Contract signals present in source
    assert 'createHash("sha256")' in src or "createHash('sha256')" in src, (
        "Schema-hash cache must compute SHA-256 of prisma/schema.prisma"
    )
    assert ".set/seed-schema-hash" in src or 'seed-schema-hash' in src, (
        "Cache file path must be .set/seed-schema-hash"
    )
    assert "PRISMA_FORCE_RESEED" in src, "Opt-out env var PRISMA_FORCE_RESEED required"
    assert "--force-reset" in src
    # Skip branch — the db push must be gated by a skipReset flag
    assert "skipReset" in src, "must have a skipReset guard around db push"


def test_cache_skipped_when_force_reset_env_set():
    src = _TEMPLATE.read_text()
    # The check should reference process.env.PRISMA_FORCE_RESEED
    assert "process.env.PRISMA_FORCE_RESEED" in src, (
        "PRISMA_FORCE_RESEED must be read from env"
    )


def test_hash_written_after_successful_push():
    src = _TEMPLATE.read_text()
    # The writeFileSync of the cache path must happen AFTER db push --force-reset
    # in the source order. This guards against persisting the hash without
    # having actually run the push.
    push_idx = src.find("prisma db push --force-reset")
    write_idx = src.find("writeFileSync(cachePath")
    assert push_idx > 0 and write_idx > 0
    assert write_idx > push_idx, (
        "seed-schema-hash must be written AFTER prisma db push --force-reset "
        "succeeds — otherwise a crashed push would persist a stale hash and "
        "skip future pushes that were actually needed."
    )
