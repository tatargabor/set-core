"""Restore and the recorded provider — task 7.7.

A separate file from `test_fleet_restore.py`, like the sibling owner and API
provider files, because two tracks edit the fleet at once.

The whole of this file is one distinction: a resumed agent runs on the provider
its session was STARTED on, or it is reported as having had none. Never on the
machine default with nobody saying so — after a reboot that is a month of
conversations resumed against a different account, and the transcript, the label
and the screen all look exactly as they did before.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import pytest

from set_orch.fleet import discovery, restore as restore_mod, roster

# Reuse the sibling file's fixtures: it owns the roster seeding, and a second
# copy would drift from it silently.
from tests.unit.test_fleet_restore import _A, _seed, _transcripts_and_liveness  # noqa: F401


class _Owner:
    """Records the recover calls, and answers with a provider when told to."""

    def __init__(self, *, answers_provider: bool = True, held: Optional[List[str]] = None):
        self.recovered: List[Dict[str, Any]] = []
        self.answers_provider = answers_provider
        self.held = list(held or [])
        self.pid = 100

    def health(self):
        return {"ok": True}

    def list_agents(self):
        return [{"label": h} for h in self.held]

    def recover(self, *, unit, session_id, cwd, label=None, resume_argv=None,
                provider_unit=None):
        self.recovered.append({"unit": unit, "session_id": session_id, "cwd": cwd,
                               "label": label, "provider_unit": provider_unit})
        self.pid += 1
        answer = {"label": label, "pid": self.pid, "unit": unit}
        if self.answers_provider:
            answer.update({"provider": "glm", "model": "glm-4.6"})
        return answer


def test_a_restore_names_which_record_the_resume_continues(tmp_path):
    """The record is keyed on the unit the agent was STARTED under.

    An ordinary restore reuses the recorded label, so the two units coincide and
    this looks like a no-op — which is exactly why the renamed case below is the
    one that matters. Both are asserted, because a `provider_unit` that is merely
    *equal* to `unit` proves nothing about which one was used.
    """
    owner = _Owner()
    path, _, cwd = _seed(tmp_path, ["S1"])
    restore_mod.restore("proj", client=owner, roster_path=path,
                        known_roots={os.path.realpath(cwd)})
    call = owner.recovered[0]
    assert call["provider_unit"] == "set-agent-proj-s1.scope"


def test_a_renamed_restore_still_finds_the_original_record(tmp_path):
    """The case the whole parameter exists for.

    A restore renames when the wanted label is taken. The provider record is
    keyed on the ORIGINAL unit, so passing the new one would find nothing — and
    "nothing recorded" resumes on the ambient default. The defect 6.7 closed,
    reappearing through the one path that legitimately changes the name.
    """
    owner = _Owner(held=["proj-s1"])
    path, _, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})

    started = out["started"][0]
    assert started["label_used"] != started["wanted_label"], "the fixture did not rename"
    call = owner.recovered[0]
    # The unit STARTED is the new one …
    assert call["unit"] == "set-agent-proj-s1-r2.scope"
    # … and the record consulted is the old one.
    assert call["provider_unit"] == "set-agent-proj-s1.scope"


def test_a_restored_agent_reports_the_provider_it_came_back_on(tmp_path):
    owner = _Owner()
    path, _, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    started = out["started"][0]
    assert started["provider_recorded"] is True
    assert started["provider"] == "glm"
    assert started["model"] == "glm-4.6"


def test_an_entry_with_no_recorded_provider_says_so(tmp_path):
    """`provider_recorded: false` is a GAP.

    The owner answers with no provider when it resolved none — an entry recorded
    before this existed, or started by something that named no provider. The
    honest report is "nobody wrote it down". The machine default's name in that
    slot would be a claim about which account the resume is spending against,
    and it would be indistinguishable from a measured one.
    """
    owner = _Owner(answers_provider=False)
    path, _, cwd = _seed(tmp_path, ["S1"])
    out = restore_mod.restore("proj", client=owner, roster_path=path,
                              known_roots={os.path.realpath(cwd)})
    started = out["started"][0]
    assert started["provider_recorded"] is False
    assert started["provider"] is None
