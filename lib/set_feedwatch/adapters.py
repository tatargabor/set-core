"""Source adapters: everything that knows one source's shape lives here.

The rest of the module asks an adapter for an item id; it never parses a source's URL
itself. One adapter today (decided 2026-10-04: Facebook only); the boundary exists so a
second source does not reshape the module.
"""
from __future__ import annotations

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


class Adapter:
    kind = ""
    #: Shown to the collecting agent: how to find an item's permalink and the sort order.
    permalink_hint = ""
    sort_hint = ""

    def item_id(self, link: str) -> str:
        """The source's stable id for an item, or "" when the link carries none."""
        raise NotImplementedError


class FacebookGroupAdapter(Adapter):
    kind = "facebook-group"
    permalink_hint = ("the link on the post's timestamp, of the form "
                      "/groups/<group>/posts/<id>/ or /permalink/<id>/")
    sort_hint = "choose 'New posts' ordering if the group offers it; otherwise say so in the report"
    _ID = re.compile(r"/(?:posts|permalink)/(\d+)")

    def item_id(self, link: str) -> str:
        m = self._ID.search(link or "")
        return m.group(1) if m else ""


ADAPTERS: Dict[str, Adapter] = {a.kind: a for a in (FacebookGroupAdapter(),)}


def any_item_id(link: str) -> str:
    """The id from whichever adapter recognises the link — used where the source is unknown."""
    for a in ADAPTERS.values():
        found = a.item_id(link)
        if found:
            return found
    return ""
