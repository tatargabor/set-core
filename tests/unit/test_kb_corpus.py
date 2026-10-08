"""The default corpus, end to end: config defaults → indexer selection.

Every AC here is a scenario of the requirement "the default corpus is every
readable markdown file outside generated and log trees" and of "project
exclusions add to the defaults" — run through `load_config` +
`index_options` on a throwaway repo, exactly the path a project takes.
"""

from __future__ import annotations

import hashlib
import json

from conftest_kb import index_root, make_repo, write
from set_kb.config import CONFIG_REL, footer_exclusions, index_options, load_config, read_framework_ledger
from set_kb.indexer import AtomicIndexSource, RunIndexAtomicOpts, run_index_atomic
from set_kb.search import SearchOpts, search

NO_MACHINE = "/nonexistent/kb-machine.json"

SESSION_FM = "---\ntype: claude-session\ntitle: Agent session dump\n---\n\n# Session dump\n\n" + "word " * 40 + "\n"
BODY = "\n\n" + "word " * 30 + "\n"


def store_for(tmp_path, config=None, name="repo", populate=None):
    """Create a throwaway repo, let `populate(root)` write its files, then
    load the config and index ONCE. Returns (root, cfg, open store)."""
    root = make_repo(tmp_path, name)
    if populate is not None:
        populate(root)
    if config is not None:
        write(root / CONFIG_REL, json.dumps(config, ensure_ascii=False))
    cfg = load_config(root, machine_path=NO_MACHINE)
    store = index_root(
        tmp_path, root, index_options(cfg, framework_ledger=read_framework_ledger(root)), db_name=f"{name}.db"
    )
    return root, cfg, store


def paths_of(store, q="word"):
    return sorted({h.path for h in search(store, q, SearchOpts(lane_quota=0))})


def test_recording_pair_indexes_only_the_readable_form(tmp_path):
    """AC: WHEN a folder holds `<stem>.jsonl` and `<stem>.md` THEN only the
    `.md` is indexed."""

    def populate(root):
        write(root / "meetings" / "2026-09-12-plan.md", "# Plan meeting\n\nrecording word" + BODY)
        write(root / "meetings" / "2026-09-12-plan.jsonl", '{"speaker": "a"}\n')

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    assert paths_of(store, "recording") == ["meetings/2026-09-12-plan.md"]
    store.close()


def test_readable_transcript_named_raw_is_indexed(tmp_path):
    """AC: WHEN a readable transcript's name contains "raw" THEN it is
    indexed — "raw" names the recording format, not the readability."""

    def populate(root):
        write(root / "meetings" / "2026-09-19-copilot-raw-part1.md", "# Raw transcript\n\ntervezés word" + BODY)

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    assert paths_of(store, "tervezés") == ["meetings/2026-09-19-copilot-raw-part1.md"]
    store.close()


def test_agent_session_dump_excluded_by_frontmatter_wherever_saved(tmp_path):
    """AC: WHEN an agent-session dump sits among recordings THEN the dump is
    excluded and the transcripts are indexed. The old directory-level
    exclusion hid recordings; this rule keys on the FILE's frontmatter."""

    def populate(root):
        write(root / "meetings" / "sessions" / "2026-09-20-agent-session.md", SESSION_FM)
        write(root / "meetings" / "sessions" / "2026-09-21-standup.md", "# Standup\n\nstandup word" + BODY)

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    assert paths_of(store, "standup") == ["meetings/sessions/2026-09-21-standup.md"]
    assert paths_of(store, "session dump") == [], "the dump is not on any page"
    store.close()


def test_session_dump_rule_names_itself_in_the_stats(tmp_path):
    """A miss must be explainable: the stats record the rule that excluded the
    file — this is what findability and doctor (W3) will name."""
    root, cfg, _store = store_for(tmp_path)
    write(root / "meetings" / "dump.md", SESSION_FM)
    opts = index_options(cfg, framework_ledger=read_framework_ledger(root))
    opts.force = True
    stats = run_index_atomic(
        RunIndexAtomicOpts(
            db_path=str(tmp_path / "stats.db"),
            sources=[AtomicIndexSource(id="", dir=str(root))],
            index_opts=opts,
        )
    )
    assert stats["excluded"].get("excludeFrontmatter:type") == 1
    assert stats["counts"]["chunks"] == 0, "the dump produced no rows"
    assert stats["counts"]["files"] == 1, "the decision is content-addressed (file state kept, rows none)"


def test_build_output_and_virtualenv_markdown_not_indexed(tmp_path):
    """AC: WHEN build output or a virtualenv holds markdown THEN none of it is
    indexed."""

    def populate(root):
        for p in (
            ".next/standalone/README.md",
            ".venv/lib/site-packages/vendored-readme.md",
            "node_modules/left-pad/README.md",
            "dist/report.md",
            "coverage/summary.md",
            "__pycache__/x.md",
            "third_party/lib/README.md",
            "test-results/out.md",
        ):
            write(root / p, "# generated word" + BODY)
        write(root / "keep.md", "# keep\n\nreal word" + BODY)

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    assert paths_of(store, "word") == ["keep.md"]
    store.close()


def test_framework_file_edited_is_indexed_unedited_is_not(tmp_path):
    """AC: WHEN a deployed framework file was edited by the project THEN it is
    indexed, while unedited ones are not. The ledger is
    `set/.deploy-manifest.json`: path → sha256 of what was deployed."""

    def populate(root):
        untouched = write(root / ".claude" / "rules" / "keep.md", "# framework rule word" + BODY)
        write(root / ".claude" / "rules" / "edited.md", "# framework rule word" + BODY)
        # a body distinct from edited.md's, so exact-content dedup does not
        # collapse the two into one hit — this test is about ledger decisions
        write(root / ".claude" / "notes" / "own.md", "# project note word\n\nownnote " + BODY)
        ledger = {
            "files": {
                ".claude/rules/keep.md": hashlib.sha256(untouched.read_bytes()).hexdigest(),
                ".claude/rules/edited.md": "0" * 64,  # the hash as DEPLOYED; the file moved on
            }
        }
        write(root / "set" / ".deploy-manifest.json", json.dumps(ledger))

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    hits = paths_of(store, "word")
    assert ".claude/rules/edited.md" in hits, "the project edited it — the project owns it"
    assert ".claude/notes/own.md" in hits, "not in the ledger → never treated as framework property"
    assert ".claude/rules/keep.md" not in hits, "hash unchanged → not project knowledge"
    store.close()


def test_includeframeworkfiles_turns_the_ledger_off(tmp_path):
    def populate(root):
        f = write(root / ".claude" / "rules" / "keep.md", "# framework rule word" + BODY)
        write(
            root / "set" / ".deploy-manifest.json",
            json.dumps({"files": {".claude/rules/keep.md": hashlib.sha256(f.read_bytes()).hexdigest()}}),
        )

    _root, _cfg, store = store_for(tmp_path, config={"includeFrameworkFiles": True}, populate=populate)
    assert ".claude/rules/keep.md" in paths_of(store, "word")
    store.close()


def test_archive_is_indexed(tmp_path):
    """AC: WHEN a file sits under an archive folder THEN it is indexed — the
    archive is the decision history, not waste."""

    def populate(root):
        write(root / "openspec" / "changes" / "archive" / "2026-01-01-done.md", "# Archived decision\n\narchive word" + BODY)

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    assert paths_of(store, "archive") == ["openspec/changes/archive/2026-01-01-done.md"]
    store.close()


def test_worktrees_tree_is_excluded(tmp_path):
    """A linked worktree INSIDE the repository (a nested worktree dir) is
    duplicated content, not corpus."""

    def populate(root):
        write(root / "worktrees" / "feat-x" / "note.md", "# worktree copy word" + BODY)
        write(root / "note.md", "# real note word" + BODY)

    _root, _cfg, store = store_for(tmp_path, populate=populate)
    assert paths_of(store, "word") == ["note.md"]
    store.close()


def test_project_exclude_adds_to_defaults_end_to_end(tmp_path):
    """AC: adding one pattern excludes it AND every default stays in force."""

    def populate(root):
        write(root / "private" / "secret.md", "# secret word" + BODY)
        write(root / "node_modules" / "dep.md", "# dep word" + BODY)
        write(root / "keep.md", "# keep word" + BODY)

    _root, cfg, store = store_for(tmp_path, config={"exclude": ["private/**"]}, populate=populate)
    assert paths_of(store, "word") == ["keep.md"]
    assert "private/**" in cfg.effective_exclude() and "node_modules/" in cfg.effective_exclude()
    store.close()


def test_keepdefault_lifts_build_output_end_to_end(tmp_path):
    """AC: lifting one default brings exactly that tree back, and the footer
    shows the active list without it."""

    def populate(root):
        write(root / "dist" / "report.md", "# build note word" + BODY)
        write(root / "node_modules" / "dep.md", "# dep word" + BODY)

    _root, cfg, store = store_for(tmp_path, config={"keepDefault": ["build-output"]}, populate=populate)
    hits = paths_of(store, "word")
    assert "dist/report.md" in hits, "the lifted group's tree is indexed"
    assert "node_modules/dep.md" not in hits, "no other default moved"
    joined = "\n".join(footer_exclusions(cfg))
    assert "dist/" not in joined
    assert "build-output" in joined, "the lift is stated by name"
    assert "**/claude-sessions/" in joined, "the other defaults are shown as still in force"
    store.close()
