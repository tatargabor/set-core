"""feed-watch: declaration, items and dedupe, scoring, digest, gate, opt-in.

Change `feed-watch`. Each test names the spec scenario it holds. The fixtures are neutral
and invented; nothing here is derived from a real feed.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_feedwatch import cli, items as items_mod, optin, scoring  # noqa: E402
from set_feedwatch.declaration import DeclarationError, load  # noqa: E402

DECL = """\
version: 1
dir: leads
sources:
  - id: devgroup
    kind: facebook-group
    url: https://www.facebook.com/groups/000/
rubric:
  marker: fw
  guidance: leads/RUBRIC.md
  dimensions:
    - {key: fit, label: Fit, max: 3}
    - {key: real, label: Real client, max: 3}
    - {key: size, label: Size, max: 3}
    - {key: reach, label: Reach, max: 3}
  threshold: {total_min: 7, dimension_min: {real: 2}}
labels: {link: Post, collected: Collected, reason: Why, score_heading: "## Scoring", subject: Subject}
drafts:
  suffix: -reply
  blocks: [fw-comment, fw-message]
  gate: GATE
digest:
  filename: "{date}-digest.md"
"""


def item(title="Need a shop", link="https://www.facebook.com/groups/000/posts/123/", body="We need a webshop.",
         score="<!-- fw:score fit=3 real=2 size=2 reach=1 -->", why="core offer", collected="2026-10-04 09:00"):
    return textwrap.dedent(f"""\
        # {title}

        - Post: {link}
        - Collected: {collected}

        ---

        {body}

        ---

        ## Scoring

        {score}
        | x | y |
        - Why: {why}
        """)


@pytest.fixture
def proj(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".set").mkdir()
    gate = f"{sys.executable} -c \"import sys; t=sys.stdin.read(); sys.exit(1 if 'BAD' in t else 0)\""
    (tmp_path / ".set" / "feed-watch.yaml").write_text(DECL.replace("GATE", json.dumps(gate)))
    (tmp_path / "leads").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write(proj, name, text):
    p = proj / "leads" / name
    p.write_text(text, encoding="utf-8")
    return p


# ------------------------------------------------------------------ declaration

def test_no_declaration_exits_nonzero_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """project-without-a-declaration"""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*") if ".git" not in p.parts)
    assert cli.main(["digest", "2026-10-04"]) == 2
    assert "feed-watch.yaml" in capsys.readouterr().err
    assert sorted(p for p in tmp_path.rglob("*") if ".git" not in p.parts) == before


def test_unknown_source_kind_fails_naming_it(proj):
    """unknown-source-kind"""
    f = proj / ".set" / "feed-watch.yaml"
    f.write_text(f.read_text().replace("kind: facebook-group", "kind: carrier-pigeon"))
    with pytest.raises(DeclarationError, match="carrier-pigeon"):
        load()


def test_digest_without_rubric_fails_naming_the_key(proj, capsys):
    """declaration-without-a-rubric"""
    f = proj / ".set" / "feed-watch.yaml"
    f.write_text(re.sub(r"rubric:\n(  .*\n|    .*\n)+", "", f.read_text()))
    assert "rubric" not in f.read_text()
    assert cli.main(["digest", "2026-10-04"]) == 2
    assert "'rubric'" in capsys.readouterr().err


# ------------------------------------------------------------------ items and dedupe

def _first_version_hash(text):
    """The first version's algorithm, kept verbatim as the reference the module must match."""
    lines = text.splitlines()
    marks = [i for i, l in enumerate(lines) if l.strip() == "---"]
    if not marks:
        body = ""
    else:
        end = marks[1] if len(marks) > 1 else len(lines)
        for i in range(marks[0] + 1, end):
            if lines[i].startswith("## Pontozás"):
                end = i
                break
        body = "\n".join(lines[marks[0] + 1:end])
    norm = re.sub(r"\s+", " ", body).strip().lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


@pytest.mark.parametrize("text", [
    item(body="Need  a\n  WEBSHOP\twith Stripe."),
    item(body="Typo'd tetx, kept as is!!"),
    # no closing '---': the body ends at the scoring heading
    "# t\n\n---\n\nopen-ended body\n\n## Pontozás\n\n<!-- x -->\n",
])
def test_hash_is_the_first_versions_algorithm(proj, text):
    """hash-compatibility-with-existing-items"""
    f = proj / ".set" / "feed-watch.yaml"
    f.write_text(f.read_text().replace('score_heading: "## Scoring"', 'score_heading: "## Pontozás"'))
    p = write(proj, "2026-10-04-a.md", text)
    assert items_mod.parse_item(p, load()).hash == _first_version_hash(text)


def test_verbatim_body_is_kept_exactly(proj):
    """verbatim-body"""
    body = "We nede a develper,  urgnet!"
    p = write(proj, "2026-10-04-a.md", item(body=body))
    assert items_mod.body_of(p.read_text(), "## Scoring").strip() == body


def test_same_text_different_link_is_known(proj, capsys, monkeypatch):
    """same-text-different-link"""
    write(proj, "2026-10-04-a.md", item(body="We need a webshop."))
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("we NEED a   webshop."))
    assert cli.main(["check-new", "--link", "ismeretlen link"]) == 3
    assert "leads/2026-10-04-a.md" in capsys.readouterr().out


def test_same_id_different_text_is_known_and_new_is_new(proj, capsys, monkeypatch):
    write(proj, "2026-10-04-a.md", item())
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("edited text"))
    assert cli.main(["check-new", "--link", "https://www.facebook.com/groups/000/permalink/123/"]) == 3
    monkeypatch.setattr(sys, "stdin", io.StringIO("something else"))
    assert cli.main(["check-new", "--link", "https://www.facebook.com/groups/000/posts/999/"]) == 0


def test_seen_skips_drafts_and_digests(proj, capsys):
    write(proj, "2026-10-04-a.md", item())
    write(proj, "2026-10-04-a-reply.md", "draft")
    write(proj, "2026-10-04-digest.md", "digest")
    assert cli.main(["seen"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("123\t") and out[0].endswith("leads/2026-10-04-a.md")


# ------------------------------------------------------------------ scoring

def test_out_of_range_value_is_unscored_not_zero(proj):
    """out-of-range-value"""
    s = scoring.parse_score(item(score="<!-- fw:score fit=4 real=2 size=2 reach=1 -->"), load().rubric)
    assert s.values is None and "above its maximum 3" in s.problem


def test_marker_inside_a_fence_is_not_read(proj):
    """marker-inside-a-fenced-example"""
    text = item(score="```\n<!-- fw:score fit=3 real=3 size=3 reach=3 -->\n```")
    s = scoring.parse_score(text, load().rubric)
    assert s.values is None and s.problem == "no score marker"


@pytest.mark.parametrize("marker,problem", [
    ("<!-- fw:score fit=3 real=2 size=2 -->", "'reach' missing"),
    ("<!-- fw:score fit=3 real=2 size=2 reach=x -->", "not an integer"),
    ("<!-- fw:score fit=3 real=2 size=2 reach=1 junk -->", "malformed"),
    ("text <!-- fw:score fit=3 real=2 size=2 reach=1 -->", "no score marker"),
    ("<!-- other:score fit=3 real=2 size=2 reach=1 -->", "no score marker"),
])
def test_malformed_markers_are_unscored(proj, marker, problem):
    s = scoring.parse_score(item(score=marker), load().rubric)
    assert s.values is None and problem in s.problem


def test_high_total_low_gating_dimension_does_not_qualify(proj):
    """high-total-low-gating-dimension"""
    r = load().rubric
    assert not scoring.qualifies(scoring.parse_score(item(score="<!-- fw:score fit=3 real=1 size=3 reach=3 -->"), r), r)
    assert scoring.qualifies(scoring.parse_score(item(score="<!-- fw:score fit=3 real=2 size=1 reach=1 -->"), r), r)
    assert not scoring.qualifies(scoring.parse_score(item(score="<!-- fw:score fit=2 real=2 size=1 reach=1 -->"), r), r)


def test_digest_ranks_and_warns(proj, capsys):
    """missing-draft"""
    write(proj, "2026-10-04-low.md", item(title="Low", body="b1", link="x",
                                          score="<!-- fw:score fit=1 real=1 size=1 reach=1 -->"))
    write(proj, "2026-10-04-top.md", item(title="Top", body="b2", link="y"))
    write(proj, "2026-10-04-raw.md", item(title="Raw", body="b3", link="z", score=""))
    write(proj, "2026-10-03-old.md", item(title="Old", body="b4", link="w", collected="2026-10-03 08:00"))
    assert cli.main(["digest", "2026-10-04"]) == 0
    err = capsys.readouterr().err
    assert "qualifies but has no draft: 2026-10-04-top.md" in err
    assert "unscored: 2026-10-04-raw.md" in err
    text = (proj / "leads" / "2026-10-04-digest.md").read_text()
    order = [t for t in ("[Top]", "[Low]", "[Raw]") if t in text]
    assert order == ["[Top]", "[Low]", "[Raw]"]
    assert sorted(order, key=text.index) == order
    assert "[Old]" not in text
    assert "WARNING: qualifies but has no draft: 2026-10-04-top.md" in text


# ------------------------------------------------------------------ gate

DRAFT = """# Reply

## Comment
```fw-comment
Hi, we can help. {c}
```

## Message
Subject: About your shop
```fw-message
Hello, details follow. {m}
```
"""


def test_gate_failure_names_the_block(proj, capsys):
    """gate-failure"""
    p = write(proj, "2026-10-04-a-reply.md", DRAFT.format(c="", m="BAD"))
    assert cli.main(["gate", str(p)]) == 1
    out = capsys.readouterr().out
    assert "FAIL 2026-10-04-a-reply.md [fw-message]" in out
    assert "PASS 2026-10-04-a-reply.md [fw-comment]" in out
    assert "PASS 2026-10-04-a-reply.md [subject]" in out


def test_gate_passes_clean_draft(proj, capsys):
    p = write(proj, "2026-10-04-a-reply.md", DRAFT.format(c="", m=""))
    assert cli.main(["gate", str(p)]) == 0


def test_no_gate_declared_is_not_a_pass(proj, capsys):
    """no-gate-declared"""
    f = proj / ".set" / "feed-watch.yaml"
    f.write_text(re.sub(r"  gate: .*\n", "", f.read_text()))
    p = write(proj, "2026-10-04-a-reply.md", DRAFT.format(c="", m=""))
    assert cli.main(["gate", str(p)]) != 0
    out = capsys.readouterr().out
    assert "no gate configured" in out and "PASS" not in out


# ------------------------------------------------------------------ opt-in

@pytest.fixture
def home(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("home")  # outside the project tree, which is what is measured
    cfg, cc = base / "cfg", base / "cc"
    cc.mkdir()
    (cc / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "owner@example.com"}}))
    monkeypatch.setenv("SET_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cc))
    return cfg, cc


def _tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts}


def test_optin_on_writes_outside_the_tree(proj, home, capsys):
    """opt-in-command"""
    cfg, cc = home
    before = _tree(proj)
    assert cli.main(["optin", "on", "--times", "18:30,08:30"]) == 0
    assert _tree(proj) == before
    e = json.loads((cfg / "feed-watch.json").read_text())["projects"][str(proj)]
    assert e == {"enabled": True, "account": "owner@example.com", "times": ["08:30", "18:30"]}
    assert str(optin.PLUGIN_DIR) in json.loads((cc / "settings.json").read_text())["env"]["CLAUDE_CODE_PLUGIN_DIRS"]


def test_optin_is_per_account(proj, home):
    """another-account (Python side; the pane's own check is in the plugin tests)"""
    cli.main(["optin", "on"])
    e = optin.entry(proj)
    assert optin.is_active(e, "OWNER@example.com")
    assert not optin.is_active(e, "someone.else@example.com")
    assert not optin.is_active(e, "")
    cli.main(["optin", "off"])
    assert not optin.is_active(optin.entry(proj), "owner@example.com")


def test_import_copies_and_leaves_the_source_byte_identical(proj, home, tmp_path):
    """import"""
    src = tmp_path / "old-optin.json"
    src.write_bytes(json.dumps({"enabled": True, "user": "owner@example.com", "times": ["07:00"]}).encode())
    before = src.read_bytes()
    assert cli.main(["optin", "import", str(src)]) == 0
    assert src.read_bytes() == before
    assert optin.entry(proj) == {"enabled": True, "account": "owner@example.com", "times": ["07:00"]}


def test_bad_times_are_refused(proj, home):
    assert cli.main(["optin", "on", "--times", "25:00"]) == 1
    assert optin.entry(proj) is None
