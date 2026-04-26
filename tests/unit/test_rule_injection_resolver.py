"""Regression tests for two production bugs witnessed in
``micro-web-run-20260426-1640`` while validating the
``dynamic-category-injection`` change.

Bug 1 (`change_reqs` UnboundLocalError):
    The resolver call site referenced ``change_reqs`` which was defined
    later in the function. Resolver always raised
    ``UnboundLocalError`` and fell back to legacy ``classify_diff_content``,
    skipping the audit log entirely. The witnessed run produced 31 KB
    input.md (vs the 28 KB baseline the change was supposed to reduce).

Bug 2 (`_build_rule_injection` substring polysemy):
    ``_build_rule_injection`` was the *other* injection path — separate
    from ``_build_review_learnings`` — and it kept doing substring
    keyword matching. The keyword ``order`` (under ``payment``) matched
    ``border-b``/``border-t`` Tailwind classes that appear in every
    Next.js foundation scope, causing 9 KB of payment/transaction
    patterns to be injected into a scaffolding change. Migrating to
    resolver-driven category→globs lookup eliminates this.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from set_orch.dispatcher import _build_rule_injection
from set_orch.profile_loader import NullProfile


class _WebLikeProfile(NullProfile):
    """Stub profile with the web mapping keys we exercise here."""

    def rule_keyword_mapping(self):
        return {
            "auth": {
                "keywords": ["auth", "login"],
                "globs": ["web/set-auth-middleware.md", "web/set-security-patterns.md"],
            },
            "payment": {
                "keywords": ["payment", "order", "cart"],
                "globs": ["web/set-transaction-patterns.md"],
            },
        }


@pytest.fixture
def web_profile():
    with patch("set_orch.profile_loader.load_profile", return_value=_WebLikeProfile()):
        yield


# ─── Bug 2 regression: resolver-driven category lookup ──────────────────


def test_rule_injection_empty_categories_returns_empty(tmp_path, web_profile):
    """Foundation change has no payment/auth/api categories → no rule
    injection. Previously injected ``set-transaction-patterns.md`` because
    'border-b' substring-matched 'order'."""
    (tmp_path / ".claude" / "rules" / "web").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "web" / "set-transaction-patterns.md").write_text(
        "# Transaction Safety\n\nDangerous payment ordering content."
    )

    scope_with_polysemous_match = (
        "border-b border-t Tailwind classes in foundational chrome and theme"
    )
    result = _build_rule_injection(
        scope_with_polysemous_match,
        str(tmp_path),
        content_categories=set(),
    )
    assert result == "", (
        "Empty categories must produce empty injection; got "
        f"{len(result)} chars. Old substring path matched 'order' → "
        "payment globs."
    )


def test_rule_injection_uses_categories_not_substring_match(tmp_path, web_profile):
    """When the resolver returns {auth}, the injection uses auth globs
    even if the scope text would have substring-matched payment
    keywords."""
    (tmp_path / ".claude" / "rules" / "web").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "web" / "set-auth-middleware.md").write_text(
        "# Auth Middleware\n\nAuth content."
    )
    (tmp_path / ".claude" / "rules" / "web" / "set-security-patterns.md").write_text(
        "# Security\n\nSecurity content."
    )

    scope_with_payment_substring = (
        "border-b layout (substring 'order' would have matched payment)"
    )
    result = _build_rule_injection(
        scope_with_payment_substring,
        str(tmp_path),
        content_categories={"auth"},
    )
    assert "Auth Middleware" in result
    assert "Transaction" not in result, (
        "Resolver categories must drive globs; substring match must NOT "
        "leak payment patterns into an auth-only change."
    )


def test_rule_injection_legacy_fallback_when_categories_none(tmp_path, web_profile):
    """For callers not migrated to the resolver, ``content_categories=None``
    keeps the legacy substring path. Documents the fallback contract."""
    (tmp_path / ".claude" / "rules" / "web").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "web" / "set-auth-middleware.md").write_text(
        "# Auth\n\n..."
    )
    (tmp_path / ".claude" / "rules" / "web" / "set-security-patterns.md").write_text(
        "# Security\n\n..."
    )

    result = _build_rule_injection(
        "Add login flow with session cookie",
        str(tmp_path),
        content_categories=None,
    )
    assert "Auth" in result


# ─── Bug 1 regression: req_ids comes from change object directly ────────


def test_resolver_callsite_does_not_reference_unbound_change_reqs():
    """``req_ids`` must be resolved from ``change.requirements`` directly,
    not from the local ``change_reqs`` variable which is defined later in
    ``dispatch_change``. Verified by AST inspection of the source."""
    import inspect
    from set_orch import dispatcher

    src = inspect.getsource(dispatcher.dispatch_change)
    # The resolver block uses change.requirements via getattr — this
    # avoids the variable-ordering trap that produced the production
    # UnboundLocalError.
    assert 'getattr(change, "requirements", []) or []' in src
    # And it must NOT reference change_reqs at the resolver call site
    # (the variable is defined many lines later for separate purposes).
    resolver_block_start = src.index("resolve_change_categories(")
    resolver_block_end = src.index(")", resolver_block_start)
    resolver_block = src[resolver_block_start:resolver_block_end]
    assert "change_reqs" not in resolver_block, (
        "Resolver call site must not reference change_reqs (UnboundLocalError trap)"
    )
