"""Who counts as a measurable account, and what an entry without a credential is.

The store shapes are real ones — two of them still exist on disk — but every
name and key here is invented. A fixture carrying a real address would put a live
account into a public repository, which is the leak this module is meant to
prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

from set_orch.usage.accounts import KIND_CC, KIND_WEB, discover_accounts


def _write(directory: Path, name: str, payload) -> None:
    (directory / name).write_text(json.dumps(payload))


def test_both_stores_are_discovered_with_their_kinds(tmp_path):
    _write(tmp_path, "claude-session.json", {
        "accounts": [{"name": "alpha@example.invalid", "sessionKey": "sk-web-1"}],
    })
    _write(tmp_path, "cc-accounts.json", {
        "active": "beta@example.invalid",
        "accounts": [{
            "email": "beta@example.invalid",
            "credentials": {"claudeAiOauth": {"accessToken": "tok-1"}},
        }],
    })

    accounts = discover_accounts(tmp_path)

    assert [a.kind for a in accounts] == [KIND_WEB, KIND_CC]
    assert {a.name for a in accounts} == {"alpha@example.invalid", "beta@example.invalid"}
    assert accounts[1].active is True


def test_an_entry_without_a_credential_is_not_an_account(tmp_path):
    """A row that can never carry a figure is worse than no row at all.

    On screen it is indistinguishable from an account that failed today, so the
    reader is told a failure happened where none did.
    """
    _write(tmp_path, "claude-session.json", {
        "accounts": [
            {"name": "alpha@example.invalid", "sessionKey": "sk-web-1"},
            {"name": "gamma@example.invalid", "sessionKey": ""},
            {"name": "delta@example.invalid"},
        ],
    })
    _write(tmp_path, "cc-accounts.json", {
        "accounts": [
            {"email": "beta@example.invalid", "credentials": {"claudeAiOauth": {}}},
            {"email": "epsilon@example.invalid"},
        ],
    })

    accounts = discover_accounts(tmp_path)

    assert [a.name for a in accounts] == ["alpha@example.invalid"]


def test_no_credentials_at_all_is_an_empty_list(tmp_path):
    assert discover_accounts(tmp_path) == []


def test_the_legacy_single_key_shape_is_still_read(tmp_path):
    _write(tmp_path, "claude-session.json", {"sessionKey": "sk-legacy"})

    accounts = discover_accounts(tmp_path)

    assert len(accounts) == 1
    assert accounts[0].kind == KIND_WEB


def test_a_scanned_duplicate_does_not_double_the_list(tmp_path):
    """Same key, two entries — one account, and the manual one wins.

    The scanned copy is the one that disappears when the browser profile is
    cleared, so it is the wrong half to keep.
    """
    _write(tmp_path, "claude-session.json", {
        "accounts": [
            {"name": "scanned", "sessionKey": "sk-same", "source": "chrome-scan"},
            {"name": "manual", "sessionKey": "sk-same", "source": "manual"},
        ],
    })

    accounts = discover_accounts(tmp_path)

    assert [a.name for a in accounts] == ["manual"]


def test_an_unreadable_store_does_not_take_the_other_one_with_it(tmp_path):
    (tmp_path / "claude-session.json").write_text("{ not json")
    _write(tmp_path, "cc-accounts.json", {
        "accounts": [{
            "email": "beta@example.invalid",
            "credentials": {"claudeAiOauth": {"accessToken": "tok-1"}},
        }],
    })

    accounts = discover_accounts(tmp_path)

    assert [a.kind for a in accounts] == [KIND_CC]


def test_the_credential_is_not_in_the_repr(tmp_path):
    """The leak that needs no decision to happen: an object printed in a log."""
    _write(tmp_path, "claude-session.json", {
        "accounts": [{"name": "alpha@example.invalid", "sessionKey": "sk-secret-value"}],
    })

    account = discover_accounts(tmp_path)[0]

    assert "sk-secret-value" not in repr(account)
    assert account.credential == "sk-secret-value"
