"""Configuration: layering, `_` documentation keys, legacy fallback, loud
validation with key paths, the default corpus groups, and the factories."""

from __future__ import annotations

import json
import logging

import pytest

from conftest_kb import make_repo, write
from set_kb.config import (
    CONFIG_REL,
    DEFAULT_EXCLUSION_GROUPS,
    DEFAULT_GROUP_NAMES,
    ConfigError,
    KbConfig,
    corpus_config_hash,
    footer_exclusions,
    index_options,
    load_config,
    search_options,
)

NO_MACHINE = "/nonexistent/kb-machine.json"


def cfg_of(tmp_path, config: dict | None, name="repo"):
    root = make_repo(tmp_path, name)
    if config is not None:
        write(root / CONFIG_REL, json.dumps(config, ensure_ascii=False))
    return load_config(root, machine_path=NO_MACHINE)


def test_defaults_when_no_config_exists(tmp_path):
    cfg = cfg_of(tmp_path, None)
    assert [s.ref for s in cfg.sources] == [""], "no config → the whole repository, one root"
    assert cfg.extensions == [".md"], "the default corpus is .md-only"
    assert cfg.exclude_defaults is True and cfg.keep_default == [] and cfg.exclude == []
    assert cfg.exclude_frontmatter == {"type": ["*-session-claude-code", "claude-session"]}
    eff = cfg.effective_exclude()
    for _name, patterns in DEFAULT_EXCLUSION_GROUPS:
        assert all(p in eff for p in patterns), "every default group is in force"


def test_underscore_keys_are_documentation(tmp_path):
    """AC: WHEN a config has `_` keys THEN they have no effect."""
    cfg = cfg_of(tmp_path, {"_why": "recordings must be findable", "exclude": ["private/"], "ranking": {"_note": "tuned", "laneQuota": 0.5}})
    assert cfg.exclude == ["private/"]
    assert cfg.ranking["laneQuota"] == 0.5
    assert "config._why" not in json.dumps(cfg.ranking)


def test_exclude_is_additive_to_the_defaults(tmp_path):
    """AC: WHEN a project adds one exclude pattern THEN all defaults stay in
    force."""
    cfg = cfg_of(tmp_path, {"exclude": ["private/**"]})
    eff = cfg.effective_exclude()
    assert "private/**" in eff
    assert "node_modules/" in eff, "the added pattern did not re-admit the default trees"


def test_keepdefault_lifts_exactly_one_group(tmp_path):
    """AC: WHEN a project config names one default to keep out THEN only that
    one is lifted."""
    cfg = cfg_of(tmp_path, {"keepDefault": ["agent-logs"]})
    eff = cfg.effective_exclude()
    assert "**/claude-sessions/" not in eff and "**/tool-calls/" not in eff
    assert "node_modules/" in eff and "dist/" in eff, "no other default moved"


def test_unknown_keepdefault_name_is_loud(tmp_path):
    with pytest.raises(ConfigError, match="unknown default group 'agents'"):
        cfg_of(tmp_path, {"keepDefault": ["agents"]})


def test_excludedefaults_false_lifts_every_group(tmp_path):
    cfg = cfg_of(tmp_path, {"excludeDefaults": False, "exclude": ["private/**"]})
    eff = cfg.effective_exclude()
    assert "node_modules/" not in eff and "dist/" not in eff
    assert "private/**" in eff, "the project's own patterns still apply"


def test_layering_machine_then_project(tmp_path, tmp_path_factory):
    root = make_repo(tmp_path)
    machine = tmp_path_factory.mktemp("machine") / "kb.json"
    machine.write_text(json.dumps({"language": "hu", "ranking": {"laneQuota": 0.5, "laneChannels": ["client"]}}), encoding="utf-8")
    write(root / CONFIG_REL, json.dumps({"ranking": {"laneQuota": 0.7}}))
    cfg = load_config(root, machine_path=machine)
    assert cfg.language == "hu", "the machine layer fills what the project omits"
    assert cfg.ranking["laneQuota"] == 0.7, "the project layer wins"
    assert cfg.ranking["laneChannels"] == ["client"], "sibling keys merge"


def test_exclude_accumulates_across_layers(tmp_path, tmp_path_factory):
    root = make_repo(tmp_path)
    machine = tmp_path_factory.mktemp("machine2") / "kb.json"
    machine.write_text(json.dumps({"exclude": ["machine-only/**"]}), encoding="utf-8")
    write(root / CONFIG_REL, json.dumps({"exclude": ["project-only/**"]}))
    cfg = load_config(root, machine_path=machine)
    eff = cfg.effective_exclude()
    assert "machine-only/**" in eff and "project-only/**" in eff, "exclude is additive at every layer"


def test_legacy_location_is_used_with_one_warning(tmp_path, caplog):
    """AC: WHEN only the legacy config exists THEN it is used and one warning
    names `set/knowledge/kb.json`."""
    root = make_repo(tmp_path)
    write(root / "kb.config.json", json.dumps({"exclude": ["legacy/**"], "language": "hu"}))
    with caplog.at_level(logging.WARNING, logger="set_kb.config"):
        cfg = load_config(root, machine_path=NO_MACHINE)
    assert cfg.legacy is True
    assert cfg.exclude == ["legacy/**"]
    assert cfg.language == "hu"
    warnings = [r for r in caplog.records if "kb.config.json" in r.getMessage()]
    assert len(warnings) == 1, "one warning per run, not one per key"
    assert CONFIG_REL in warnings[0].getMessage(), "the warning names the new location"


def test_project_file_beats_legacy_file(tmp_path):
    root = make_repo(tmp_path)
    write(root / "kb.config.json", json.dumps({"exclude": ["legacy/**"]}))
    write(root / CONFIG_REL, json.dumps({"exclude": ["current/**"]}))
    cfg = load_config(root, machine_path=NO_MACHINE)
    assert cfg.legacy is False and cfg.exclude == ["current/**"]


def test_unknown_language_names_key_and_packs(tmp_path):
    """AC: WHEN the language has no pack THEN loading fails naming the key and
    the available packs."""
    with pytest.raises(ConfigError, match=r"config\.language.*'de'.*available packs: .*hu"):
        cfg_of(tmp_path, {"language": "de"})


def test_channel_rule_without_roots_names_the_rule(tmp_path):
    """AC: WHEN a channel rule has no roots THEN config loading fails naming
    it."""
    with pytest.raises(ConfigError, match=r"config\.channels\[0\] \(rule 'client'\).*roots"):
        cfg_of(tmp_path, {"channels": [{"channel": "client", "include": ["client-*/**"]}]})


def test_empty_roots_is_also_without_roots(tmp_path):
    with pytest.raises(ConfigError, match="roots"):
        cfg_of(tmp_path, {"channels": [{"channel": "c", "roots": []}]})


def test_scope_pattern_without_placeholder_names_the_pattern(tmp_path):
    """AC: WHEN a scope pattern lacks `{scope}` THEN loading fails naming the
    pattern."""
    with pytest.raises(ConfigError, match=r"config\.scopes\[0\].*docs/clients/\*\*.*\{scope\}"):
        cfg_of(tmp_path, {"scopes": [{"name": "client", "pattern": "docs/clients/**"}]})


def test_non_string_pattern_names_the_key_path(tmp_path):
    with pytest.raises(ConfigError, match=r"config\.exclude\[1\]: expected a string"):
        cfg_of(tmp_path, {"exclude": ["ok/**", 42]})


def test_extensions_must_be_non_empty_strings(tmp_path):
    with pytest.raises(ConfigError, match=r"config\.extensions\[0\]"):
        cfg_of(tmp_path, {"extensions": [7]})
    with pytest.raises(ConfigError, match="at least one extension"):
        cfg_of(tmp_path, {"extensions": []})


def test_lane_numbers_are_range_checked(tmp_path):
    with pytest.raises(ConfigError, match=r"config\.ranking\.laneQuota"):
        cfg_of(tmp_path, {"ranking": {"laneQuota": 1.5}})


def test_unknown_top_level_key_warns_but_loads(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="set_kb.config"):
        cfg = cfg_of(tmp_path, {"exlude": ["typo/**"]})
    assert cfg.exclude == [], "a typo'd key must not silently do work"
    assert any("exlude" in r.getMessage() for r in caplog.records)


def test_corpus_hash_tracks_what_rows_depend_on(tmp_path):
    a = cfg_of(tmp_path, {"channels": [{"channel": "client", "roots": ["docs"]}]}, name="r1")
    b = cfg_of(tmp_path, {"channels": [{"channel": "client", "roots": ["docs"]}]}, name="r2")
    assert corpus_config_hash(a) == corpus_config_hash(b), "identical configs hash identically"
    c = cfg_of(tmp_path, {"channels": [{"channel": "client", "roots": ["docs2"]}]}, name="r3")
    assert corpus_config_hash(a) != corpus_config_hash(c), "a channel change re-classifies rows"
    plain = cfg_of(tmp_path, None, name="r4")
    tuned = cfg_of(tmp_path, {"language": "hu", "ranking": {"laneQuota": 0.9}}, name="r5")
    assert corpus_config_hash(plain) == corpus_config_hash(tuned), "language and ranking never touch rows"
    reshaped = cfg_of(tmp_path, {"excludeFrontmatter": {"type": ["other-dump"]}}, name="r6")
    assert corpus_config_hash(plain) != corpus_config_hash(reshaped), "the frontmatter rule decides rows"


def test_index_options_factory_carries_the_effective_corpus(tmp_path):
    cfg = cfg_of(tmp_path, {"exclude": ["private/**"], "channels": [{"channel": "c", "roots": ["r"]}]})
    opts = index_options(cfg, framework_ledger={"x.md": "h"})
    assert "private/**" in opts.exclude and "node_modules/" in opts.exclude
    assert opts.extensions == [".md"]
    assert opts.framework_ledger == {"x.md": "h"}
    cfg2 = cfg_of(tmp_path, {"includeFrameworkFiles": True}, name="r2")
    assert index_options(cfg2).framework_ledger is None, "includeFrameworkFiles passes no ledger"


def test_search_options_factory_and_overrides(tmp_path):
    cfg = cfg_of(tmp_path, {"language": "hu", "ranking": {"laneQuota": 0.5, "laneChannels": ["client"]}, "sources": [{"ref": "docs", "priority": 5}]})
    opts = search_options(cfg)
    assert opts.lane_quota == 0.5 and list(opts.lane_channels) == ["client"]
    assert opts.root_priority == {"docs": 5}
    assert opts.language.id == "hu"
    assert search_options(cfg, limit=3, scope="client=alfa").limit == 3


def test_footer_exclusions_state_the_active_list(tmp_path):
    """AC: the footer shows the active list without the lifted default — and
    names the lift, so the page never reads as an accident."""
    cfg = cfg_of(tmp_path, {"keepDefault": ["agent-logs"]})
    lines = footer_exclusions(cfg)
    joined = "\n".join(lines)
    assert "**/claude-sessions/" not in joined, "the lifted group is not in the active list"
    assert "agent-logs" in joined, "the lift itself is stated"
    assert "node_modules/" in joined, "the rest of the defaults are shown as in force"
    assert "unmodified framework-deployed files excluded" in joined
    all_on = footer_exclusions(cfg_of(tmp_path, {"excludeDefaults": True}, name="r2"))
    assert any("excludes:" in l for l in all_on)
