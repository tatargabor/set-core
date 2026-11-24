"""`webhook_forward` — a webhook channel behind the auto-answer decider (Discord, for one).

Exit codes are what the decider acts on: non-zero means the operator did not see the
question, so it must never be 0 on a failed or skipped post.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.fleet import question_relay as qr  # noqa: E402

PROPOSAL = "\n\n🤖 Auto-answer: «Yes» — certain; your words. Written at 14:30:00 unless you answer first."


def _env(question="Ship it?" + PROPOSAL):
    return json.dumps({"questions": [{"id": "c1", "key": "Q1", "question": question,
                                      "optionsList": ["Yes", "No"], "multi": False,
                                      "audience": "operator", "source": "proj · abcd1234"}]})


def _cfg(**kv):
    return lambda key, default=None: kv.get(key, default)


def _run(payload, **cfg):
    posts = []
    code = qr.webhook_forward(payload, get=_cfg(**cfg), post=lambda u, c: posts.append((u, c)),
                              environ={})
    return code, posts


def test_full_detail_posts_question_and_proposal():
    code, posts = _run(_env(), **{qr.KEY_WEBHOOK: "https://hook", qr.KEY_DETAIL: "full"})
    assert code == 0 and len(posts) == 1
    url, content = posts[0]
    assert url == "https://hook"
    assert "Ship it?" in content and "Auto-answer: «Yes»" in content and "– Yes" in content
    assert "proj" in content


def test_summary_hides_text_but_says_a_proposal_exists():
    code, posts = _run(_env(), **{qr.KEY_WEBHOOK: "https://hook"})
    assert code == 0
    content = posts[0][1]
    assert "Ship it?" not in content and "«Yes»" not in content
    assert "automatic answer is proposed" in content


def test_notification_is_posted():
    payload = json.dumps({"kind": "notification", "agent": "proj · abcd", "message": "needs permission"})
    code, posts = _run(payload, **{qr.KEY_WEBHOOK: "https://hook"})
    assert code == 0 and "needs permission" in posts[0][1]


def test_failures_are_never_exit_zero():
    assert _run(_env())[0] != 0                                          # no URL
    assert _run("not json", **{qr.KEY_WEBHOOK: "https://h"})[0] != 0
    assert _run(json.dumps({"questions": []}), **{qr.KEY_WEBHOOK: "https://h"})[0] != 0

    def boom(u, c):
        raise OSError("down")
    code = qr.webhook_forward(_env(), get=_cfg(**{qr.KEY_WEBHOOK: "https://h"}), post=boom, environ={})
    assert code != 0
