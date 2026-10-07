"""Channel classification: first match wins, root-scoped, include/exclude."""

from __future__ import annotations

from set_kb.channels import ChannelRule, classify_channel, compile_channel_rules


def rules():
    return compile_channel_rules(
        [
            ChannelRule(channel="client", roots=["corpus/clients"], include=["client-*/**"]),
            ChannelRule(channel="meetings", roots=["corpus/meetings"], include=["meetings/**", "minutes/**"]),
        ]
    )


def test_root_scoped_include():
    r = rules()
    assert classify_channel(r, "corpus/clients", "client-alfa/mail.md") == "client"
    assert classify_channel(r, "corpus/meetings", "minutes/kickoff.md") == "meetings"
    assert classify_channel(r, "corpus/planning", "overview.md") is None


def test_same_folder_name_under_another_root_is_not_classified():
    """The root-scoping rule, enforced: a `meetings/` folder under the CLIENT
    root matches the include pattern but not the ROOTS — the measured
    misclassification this closes."""
    r = rules()
    assert classify_channel(r, "corpus/clients", "meetings/standalone-minutes.md") is None
    assert classify_channel(r, "corpus/meetings", "meetings/x.md") == "meetings"


def test_first_match_wins_so_ordering_is_meaningful():
    r = compile_channel_rules(
        [
            ChannelRule(channel="narrow", roots=["root"], include=["special/**"]),
            ChannelRule(channel="broad", roots=["root"]),
        ]
    )
    assert classify_channel(r, "root", "special/x.md") == "narrow"
    assert classify_channel(r, "root", "other/x.md") == "broad"


def test_exclude_vetos_even_when_include_matched():
    r = compile_channel_rules(
        [ChannelRule(channel="c", roots=["root"], include=["a/**"], exclude=["a/private/**"])]
    )
    assert classify_channel(r, "root", "a/x.md") == "c"
    assert classify_channel(r, "root", "a/private/x.md") is None


def test_no_rules_classifies_nothing():
    assert classify_channel(compile_channel_rules([]), "any", "path.md") is None
    assert classify_channel(compile_channel_rules(None), "any", "path.md") is None
