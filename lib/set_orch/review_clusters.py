"""Shared keyword clusters for review findings pattern matching.

Used by engine._persist_run_learnings() and dispatcher._build_review_learnings().
"""

REVIEW_PATTERN_CLUSTERS: dict[str, list[str]] = {
    "no-auth": ["no auth", "no authentication", "zero authentication", "without auth"],
    "no-csrf": ["csrf", "cross-site request"],
    "xss": ["xss", "dangerouslysetinnerhtml", "v-html"],
    "no-rate-limit": ["rate limit", "rate-limit"],
    "secrets-exposed": ["masking", "exposed", "leaked", "codes displayed"],
}
