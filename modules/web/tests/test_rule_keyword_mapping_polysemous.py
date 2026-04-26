"""Regression test for Bug #2: ``rule_keyword_mapping`` substring
matches inflated injection. Witnessed in micro-web-run-20260426-1302
where every web scope activated auth + api categories because:

- ``token`` matched "design tokens" (every shadcn scope)
- ``middleware`` matched Next.js middleware mentions (routing, not auth)
- ``route`` matched "page routes" (every page-adding scope)

These three keywords were dropped from
``WebProjectType.rule_keyword_mapping`` in the dynamic-category-injection
change. This test pins the regression so a future contributor doesn't
re-add them.
"""

from __future__ import annotations

import pytest

from set_project_web.project_type import WebProjectType


@pytest.fixture
def auth_keywords():
    return WebProjectType().rule_keyword_mapping()["auth"]["keywords"]


@pytest.fixture
def api_keywords():
    return WebProjectType().rule_keyword_mapping()["api"]["keywords"]


@pytest.fixture
def db_keywords():
    return WebProjectType().rule_keyword_mapping()["database"]["keywords"]


# ─── `schema` polysemy regression (micro-web-run-20260426-1704) ────────


def test_schema_removed_from_database_keywords(db_keywords):
    """`schema` matches "form schema" / "Zod schema" / "JSON schema" —
    every form change. Witnessed in contact-wizard-form: scope
    mentioned "current step's schema validates via form.trigger" →
    database category → 12.5K of set-security-patterns.md (IDOR/auth)
    injected into a form-only change.
    """
    assert "schema" not in db_keywords


def test_database_keywords_kept_unambiguous_terms(db_keywords):
    """Removing schema must not gut the category — strong markers
    (database/prisma/drizzle/migration) still catch real DB scopes."""
    for kw in ("database", "prisma", "drizzle", "migration"):
        assert kw in db_keywords, f"strong DB keyword '{kw}' must remain"


def test_form_schema_scope_does_not_activate_database():
    """Witnessed scope: 'schema' meant Zod form validation schema, not
    DB schema. Scope-detection regex must NOT match this."""
    web = WebProjectType()
    scope = (
        "Multi-step contact form with Zod schema validation per step. "
        "Next button disabled until current step's schema validates "
        "via form.trigger."
    )
    cats = web.detect_scope_categories(scope)
    assert "database" not in cats, (
        f"form-schema scope must NOT activate database; got: {cats}"
    )


def test_real_db_scope_still_activates_database():
    """Sanity: a scope with strong DB markers must still trigger database."""
    web = WebProjectType()
    scope = "Add Prisma migration for User table with email column"
    cats = web.detect_scope_categories(scope)
    assert "database" in cats


def test_database_globs_point_to_db_rules():
    """Witnessed bug: database globs were ['web/set-security-patterns.md']
    which is IDOR/auth/CSRF (~11K) — unrelated to DB. Fix: db-type-safety
    + schema-integrity (the actual DB rule files).
    """
    db_globs = WebProjectType().rule_keyword_mapping()["database"]["globs"]
    assert "web/set-security-patterns.md" not in db_globs, (
        "set-security-patterns is auth/IDOR/CSRF — wrong category mapping"
    )
    db_specific = {"web/set-db-type-safety.md", "web/set-schema-integrity.md"}
    assert any(g in db_specific for g in db_globs), (
        f"database globs must include a DB-specific rule; got {db_globs}"
    )


# ─── Polysemous-keyword removal (existing) ──────────────────────────────


def test_token_removed_from_auth_keywords(auth_keywords):
    """`token` is in 'design tokens' (every shadcn scope) — must NOT
    activate auth via substring match."""
    assert "token" not in auth_keywords


def test_middleware_removed_from_auth_keywords(auth_keywords):
    """`middleware` matches Next.js middleware (routing/i18n), not
    auth-specific."""
    assert "middleware" not in auth_keywords


def test_route_removed_from_api_keywords(api_keywords):
    """`route` matches 'page routes' on every page-adding change."""
    assert "route" not in api_keywords


# ─── Kept keywords still detect real auth/api signals ───────────────────


def test_auth_keywords_kept_unambiguous_terms(auth_keywords):
    """Removing the polysemous ones must not gut the category — the
    unambiguous terms (auth/login/session/cookie/password) still
    catch real auth scopes."""
    for kw in ("auth", "login", "session", "cookie", "password"):
        assert kw in auth_keywords, f"unambiguous auth keyword '{kw}' must remain"


def test_api_keywords_kept_unambiguous_terms(api_keywords):
    for kw in ("api", "endpoint", "handler", "REST", "mutation"):
        assert kw in api_keywords, f"unambiguous api keyword '{kw}' must remain"


# ─── Behavioral regression on the witnessed scope ───────────────────────


def test_design_tokens_scope_does_not_activate_auth():
    """Witnessed scope from micro-web foundation.

    The scope mentions design tokens — under the buggy mapping this
    activated auth via the `token` keyword and injected
    set-auth-middleware.md + set-security-patterns.md (~13 KB
    irrelevant context).
    """
    web = WebProjectType()
    keywords = web.rule_keyword_mapping()["auth"]["keywords"]
    scope = (
        "Set up shadcn/ui with the slate theme. Configure design tokens "
        "in globals.css. Wire ThemeProvider with next-themes."
    )
    scope_lower = scope.lower()
    matches = [kw for kw in keywords if kw.lower() in scope_lower]
    assert matches == [], (
        f"design-tokens scope must NOT match any auth keyword; got: {matches}"
    )


def test_page_routes_scope_does_not_activate_api():
    """Witnessed scope from micro-web foundation."""
    web = WebProjectType()
    keywords = web.rule_keyword_mapping()["api"]["keywords"]
    scope = (
        "Create 4 page routes (Home/About/Blog/Contact) with sticky header "
        "and active link highlighting via usePathname."
    )
    scope_lower = scope.lower()
    matches = [kw for kw in keywords if kw.lower() in scope_lower]
    assert matches == [], (
        f"page-routes scope must NOT match any api keyword; got: {matches}"
    )


def test_real_auth_scope_still_activates_auth():
    """Sanity: the cleanup did not accidentally disable real
    auth-detection. A scope explicitly about login MUST still match
    auth keywords."""
    web = WebProjectType()
    keywords = web.rule_keyword_mapping()["auth"]["keywords"]
    scope = "Add /login page that creates a session cookie via NextAuth."
    scope_lower = scope.lower()
    matches = [kw for kw in keywords if kw.lower() in scope_lower]
    assert matches, (
        "real auth scope MUST match at least one auth keyword after cleanup"
    )


def test_real_api_scope_still_activates_api():
    """Sanity: an explicit API endpoint scope still matches."""
    web = WebProjectType()
    keywords = web.rule_keyword_mapping()["api"]["keywords"]
    scope = "Add POST /api/users endpoint with handler returning the new user."
    scope_lower = scope.lower()
    matches = [kw for kw in keywords if kw.lower() in scope_lower]
    assert matches
