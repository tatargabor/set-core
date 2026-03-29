from __future__ import annotations

"""Bilingual (EN/HU) emotion detection for user prompts.

Detects emotionally charged prompts using simple trigger-group logic:
- Strong triggers (any 1 = high): agent-correction, expletives, giving-up
- Medium triggers (2+ = moderate, 1 = mild): repetition+negation, temporal, escalation, intensifiers
- Session boost: 3+ prior triggers → single medium escalates to moderate

Used by set-hook-memory UserPromptSubmit handler to save high-priority memories
and inject warnings to the current agent.

Note: This module intentionally contains explicit language patterns for
linguistic detection purposes across English and Hungarian.
"""

import re
from typing import Optional

# ============================================================
# Strong triggers — any single match = high
# ============================================================

# Agent-correction: user tells the agent it did something wrong
AGENT_CORRECTION = [
    # EN
    r"\bthat'?s\s+not\s+what\s+I\s+ask",
    r"\bnot\s+what\s+I\s+(meant|asked|said|wanted)",
    r"\bwrong\s+(file|function|directory|path|module|class|method)",
    r"\byou\s+didn'?t\s+(read|check|look|listen)",
    r"\byou'?re\s+not\s+listen",
    r"\bI\s+(just|already)\s+(said|told|asked|explained)\s+(you|this)",
    r"\bread\s+(the|it)\s+(file|code|spec|doc)\s+(first|before)",
    r"\bstop\s+(doing|making|ignoring|repeating)\b",
    # HU
    r"\bnem\s+ezt\s+k[eé]rtem",
    r"\brossz\s+(f[aá]jlt?|file|f[uü]ggv[eé]ny|met[oó]dust?|oszt[aá]lyt?|mapp[aá]t?)",
    r"\bmi[eé]rt\s+nem\s+olvastad",
    r"\bte\s+nem\s+figye",
    r"\b[eé]n\s+azt\s+mondtam",
    r"\bpont\s+ezt\s+mondtam",
    r"\bde\s+h[aá]t\s+mondtam",
    r"\bel\s+se\s+olvastad",
    r"\bmit\s+csin[aá]lt[aá]l",
]

# Expletives: strong/vulgar language
EXPLETIVES = [
    # EN
    r"\bfuck(ing|ed)?\b",
    r"\bshit(ty)?\b",
    r"\bwtf\b",
    r"\bffs\b",
    r"\bbullshit\b",
    r"\bgodda(mn|mit)\b",
    # HU
    r"\bbaszd?\s*meg\b",
    r"\bbasszus\b",
    r"\ba\s+kurva",
    r"\bgeci\b",
    r"\bmi\s+a\s+faszt?\b",
    r"\bmi\s+a\s+pics[aá]t?\b",
    r"\baz\s+isten[ií\xe9]t?\b",
    r"\ba\s+r[aá]k\s+egye",
]

# Giving-up: abandonment language
GIVING_UP = [
    # EN
    r"\bgive\s+up\b",
    r"\bforget\s+it\b",
    r"\bnever\s*mind\b",
    r"\bdone\s+with\s+this\b",
    r"\bwaste\s+of\s+time\b",
    r"\bthis\s+is\s+hopeless\b",
    r"\bno\s+point\b",
    # HU
    r"\bfeladom\b",
    r"\bhagyjuk\b",
    r"\bk[eé]sz\s+vagyok\s+ezzel\b",
    r"\bnincs\s+[eé]rtelme\b",
    r"\bidő?pocs[eé]kol[aá]s",
    r"\brem[eé]nytelen\b",
    r"\bfelejtsd?\s+el\b",
    r"\bhagyj[aá]l?\s+(b[eé]k[eé]n|nyugton)",
]

# ============================================================
# Medium triggers — 2+ combined = moderate, 1 alone = mild
# ============================================================

# Repetition + negation combo
REPETITION_NEGATION = [
    # EN
    r"\bstill\s+(doesn'?t|won'?t|can'?t|not|isn'?t|broken|failing)",
    r"\bagain.{0,15}(doesn'?t|won'?t|not|fail|break|broken|wrong)",
    r"\bkeeps?\s+(break|fail|crash|happen)",
    # HU
    r"\bmegint\s+nem\b",
    r"\bm[aá]r\s+megint\b",
    r"\b[uú]jra\s+nem\b",
    r"\bism[eé]t\s+nem\b",
    r"\bminden\s+alkalommal",
]

# Temporal frustration
TEMPORAL = [
    # EN
    r"\bhow\s+many\s+times\b",
    r"\bI\s+already\s+(told|said|asked|explained|tried|did)",
    r"\bthis\s+is\s+the\s+(third|fourth|fifth|[0-9]+th)\s+time",
    r"\bfor\s+the\s+(nth|umpteenth|hundredth)\s+time",
    r"\bwe'?ve\s+(been\s+through|already\s+(done|tried))\s+this",
    # HU
    r"\bh[aá]nyszor\b",
    r"\bm[aá]r\s+mondtam\b",
    r"\bm[aá]r\s+megmondtam\b",
    r"\bm[aá]r\s+pr[oó]b[aá]ltuk\b",
    r"\bezt\s+m[aá]r\s+csin[aá]ltuk\b",
    r"\bsokad(j[aá]ra|szorra)\b",
    r"\b(napok|[oó]r[aá]k|hetek)\s+[oó]ta\b",
]

# Escalation / absolutes
ESCALATION = [
    # EN
    r"\bnever\s+works?\b",
    r"\balways\s+(break|fail|crash|wrong|broken)",
    r"\b(absolutely|completely|totally|utterly)\s+(broken|useless|wrong|terrible)",
    r"\bimpossible\b",
    # HU
    r"\bsoha\s+(nem|sincs)\b",
    r"\bmindig\s+(rossz|elromlik|hib[aá]s|szar)",
    r"\blehetetlen\b",
    r"\bk[eé]ptelens[eé]g\b",
    r"\bhaszn[aá]lhatatlan\b",
]

# ============================================================
# Intensifier detection (not regex-pattern based)
# ============================================================

_CAPS_RE = re.compile(r'\b[A-Z]{3,}\b')
_PUNCT_RE = re.compile(r'[!?]{2,}')


def _count_intensifiers(text: str) -> int:
    """Count intensifier signals: ALL CAPS words and excessive punctuation."""
    count = 0
    caps_words = _CAPS_RE.findall(text)
    if len(caps_words) >= 2:
        count += 1
    if _PUNCT_RE.search(text):
        count += 1
    return count


# ============================================================
# Compiled pattern groups
# ============================================================

def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


STRONG_GROUPS = {
    'agent-correction': _compile(AGENT_CORRECTION),
    'expletives': _compile(EXPLETIVES),
    'giving-up': _compile(GIVING_UP),
}

MEDIUM_GROUPS = {
    'repetition-negation': _compile(REPETITION_NEGATION),
    'temporal': _compile(TEMPORAL),
    'escalation': _compile(ESCALATION),
}


# ============================================================
# Detection
# ============================================================

def detect(prompt: str, session_history: Optional[dict] = None) -> dict:
    """Detect emotional charge in a user prompt.

    Args:
        prompt: The user's prompt text.
        session_history: Optional dict tracking frustration across session.
            Updated in-place with current detection result.
            Format: {"count": int, "last_level": str}

    Returns:
        dict with keys:
            level: "none", "mild", "moderate", or "high"
            triggers: list of matched trigger group names
            save: bool — whether to save a memory
            inject: bool — whether to inject a warning
    """
    triggers = []

    # Check strong triggers
    strong_hit = False
    for group_name, patterns in STRONG_GROUPS.items():
        if any(p.search(prompt) for p in patterns):
            triggers.append(group_name)
            strong_hit = True

    # Check medium triggers
    medium_count = 0
    for group_name, patterns in MEDIUM_GROUPS.items():
        if any(p.search(prompt) for p in patterns):
            triggers.append(group_name)
            medium_count += 1

    # Check intensifiers (count as medium trigger)
    intensifier_count = _count_intensifiers(prompt)
    if intensifier_count > 0:
        triggers.append('intensifiers')
        medium_count += intensifier_count

    # Determine level
    session_count = (session_history or {}).get('count', 0)

    if strong_hit:
        level = 'high'
    elif medium_count >= 2:
        level = 'moderate'
    elif medium_count >= 1 and session_count >= 3:
        level = 'moderate'  # session boost
    elif medium_count >= 1:
        level = 'mild'
    else:
        level = 'none'

    # Determine actions
    save = level in ('moderate', 'high')
    inject = level != 'none'

    # Update session history
    if session_history is not None and level != 'none':
        session_history['count'] = session_count + 1
        session_history['last_level'] = level

    return {
        'level': level,
        'triggers': triggers,
        'save': save,
        'inject': inject,
    }
