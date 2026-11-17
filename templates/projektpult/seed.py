#!/usr/bin/env python3
"""Turn a Projektpult spec into the documents the page reads from its artifact db.

Usage:
    python3 seed.py SPEC.json OUT_DIR

SPEC.json:
    {
      "project": "Project name",            # header and tab title
      "subtitle": "Client · topic",         # small line above the name (optional)
      "lang": "hu" | "en",                  # UI language (default hu)
      "groups": {"office": "Office", ...},  # question addressee key -> label, in display order
      "questions": [
        {"id": "Q1", "label": "Q1", "group": "office", "q": "Question text (**bold** allowed)",
         "bg": "background", "src": "source", "status": "open|partial|conflict|answered",
         "private": false, "options": ["A text", "B text", "C text"]}
      ],
      "issues": [
        {"title": "...", "status": "todo|inprogress|review|blocked|onhold|done",
         "area": "...", "owner": "...", "note": "...", "refs": ["Q1"], "due": "YYYY-MM-DD"}
      ]
    }

OUT_DIR receives:
    catalog.json            -> ArtifactData set, collection "catalog", doc_id "questions"
    issues/ISS-NN.json      -> one document per issue, collection "issues", doc_id ISS-NN
    issues-batch-N.json     -> ready "writes" arrays (<= 50 each) for ArtifactData action "batch"

Seed only an empty store: the page owns the issues and answers once people use it. To
refresh the questions later, re-run and `set` catalog/questions again (answers are kept,
they live in their own collection keyed by question id).
"""
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("projektpult.seed")

QSTATUS = {"open", "partial", "conflict", "answered"}
ISTATUS = {"todo", "inprogress", "review", "blocked", "onhold", "done"}
SEGMENT = re.compile(r"^[A-Za-z0-9_\-.~:@+]{1,200}$")
MAX_DOC = 256 * 1024


def fail(msg):
    logger.error(msg)
    sys.exit(1)


def main(argv):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out = Path(argv[2]).resolve()
    (out / "issues").mkdir(parents=True, exist_ok=True)

    groups = spec.get("groups") or {}
    items, seen = [], set()
    for n, q in enumerate(spec.get("questions") or []):
        qid = q.get("id") or fail(f"question #{n} has no id")
        if not SEGMENT.match(qid):
            fail(f"question id {qid!r}: only ASCII letters, digits and _-.~:@+ (put the display form in 'label')")
        if qid in seen:
            fail(f"duplicate question id {qid}")
        seen.add(qid)
        status = q.get("status", "open")
        if status not in QSTATUS:
            fail(f"question {qid}: status {status!r} not in {sorted(QSTATUS)}")
        opts = q.get("options") or []
        if len(opts) > 3:
            fail(f"question {qid}: at most 3 options (A, B, C), got {len(opts)}")
        if q.get("group") and q["group"] not in groups:
            logger.warning("question %s: group %r has no label in 'groups'", qid, q["group"])
        items.append({"id": qid, "label": q.get("label", qid), "group": q.get("group", ""), "q": q.get("q", ""),
                      "bg": q.get("bg", ""), "src": q.get("src", ""), "status": status,
                      "private": bool(q.get("private")), "options": opts, "order": n})
    catalog = {"project": spec.get("project", ""), "subtitle": spec.get("subtitle", ""), "lang": spec.get("lang", "hu"),
               "groups": groups, "items": items}
    body = json.dumps(catalog, ensure_ascii=False)
    if len(body.encode()) > MAX_DOC:
        fail(f"catalog is {len(body.encode())} bytes, over the 256 KiB document limit; shorten 'bg' texts")
    (out / "catalog.json").write_text(body, encoding="utf-8")
    logger.info("catalog: %d questions, %d bytes -> %s", len(items), len(body.encode()), out / "catalog.json")

    writes = []
    for n, x in enumerate(spec.get("issues") or [], 1):
        key = x.get("key") or f"ISS-{n:02d}"
        if not SEGMENT.match(key):
            fail(f"issue key {key!r} is not a valid document id")
        status = x.get("status", "todo")
        if status not in ISTATUS:
            fail(f"issue {key}: status {status!r} not in {sorted(ISTATUS)}")
        doc = {"key": key, "title": x.get("title") or fail(f"issue {key} has no title"), "status": status,
               "area": x.get("area", ""), "owner": x.get("owner", ""), "note": x.get("note", ""),
               "refs": x.get("refs", []), "due": x.get("due", ""), "order": n, "created": x.get("created", "")}
        path = out / "issues" / f"{key}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        writes.append({"op": "set", "collection": "issues", "doc_id": key, "file_path": str(path)})
    for b in range(0, len(writes), 50):
        f = out / f"issues-batch-{b // 50 + 1}.json"
        f.write_text(json.dumps(writes[b:b + 50], ensure_ascii=False, indent=1), encoding="utf-8")
        logger.info("issues batch %s: %d writes", f.name, len(writes[b:b + 50]))
    logger.info("issues: %d", len(writes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
