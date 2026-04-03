# Design: Filter Expired Chrome Sessions

## Context

`_fetch_org_name()` currently catches all exceptions and returns `None` — there's no distinction between "session expired" and "network unavailable." The scan adds every session that has a cookie, regardless of whether it actually works. The UsageWorker then polls these dead sessions every 30 seconds forever.

## Goals / Non-Goals

**Goals:**
- Filter out definitively expired sessions during Chrome scan
- Distinguish HTTP auth errors (401/403) from network failures
- Keep sessions with inconclusive validation (network errors) so transient issues don't drop valid sessions

**Non-Goals:**
- Auto-removing expired sessions from `claude-session.json` (manual accounts should persist)
- Retry logic for expired sessions (once expired, they stay expired until next scan)
- UI indicators for "unverified" sessions (keep it simple for now)

## Decisions

### D1: Replace `_fetch_org_name()` with `_validate_session()`

**Choice:** Single function returning `(status, org_name)` tuple where status is `"valid"`, `"expired"`, or `"error"`.

**Why not keep `_fetch_org_name()` and add a separate validator?** Both functions would hit the same `/api/organizations` endpoint. A single call that checks the status code AND extracts the org name avoids double API calls.

**Return type:** `tuple[str, str | None]`
- `("valid", "Org Name")` — session works, org name resolved
- `("expired", None)` — definitive auth failure (401/403 or empty/invalid response body)
- `("error", None)` — network issue, can't determine status

### D2: HTTP status code extraction from curl_cffi and curl subprocess

**curl_cffi:** `resp.status_code` is directly available — check for 401/403 before attempting JSON parse.

**curl subprocess:** Use `curl -w '%{http_code}' -o -` to get status code alongside response body. Parse the last 3 characters as the HTTP status.

**Fallback chain logic:** If curl_cffi returns 401/403 → immediately return `("expired", None)`, don't try curl subprocess. If curl_cffi has a network error → try curl subprocess. The most definitive auth error wins.

### D3: `scan_chrome_sessions()` filtering behavior

```
_validate_session() result  →  scan action
─────────────────────────────────────────────
("valid", org_name)         →  include, name = org_name
("expired", None)           →  EXCLUDE from results
("error", None)             →  include, name = profile name, verified = false
```

Sessions with `"verified": false` are included because a temporary network blip shouldn't remove a valid session. On next scan (or on next startup auto-scan), they'll be re-validated.

### D4: No changes to UsageWorker failure tracking

The UsageWorker already handles per-account failures gracefully (shows `available: False`). Adding consecutive-failure tracking would add complexity for minimal gain — the scan-time filtering is the primary fix. If a session becomes expired between scans, it shows as unavailable until the next scan removes it. This is acceptable behavior.

## Risks / Trade-offs

**[Risk] Cloudflare blocks return non-standard status codes** → The curl_cffi impersonation already handles this. If Cloudflare returns 403, we treat it as inconclusive (`"error"`) rather than expired, since it's Cloudflare blocking us, not Claude rejecting the session. Only check for 401/403 when the response body also indicates auth failure (no valid org JSON).

**[Risk] Claude API changes response format** → We already handle `isinstance(orgs, list)` check. If the API returns unexpected JSON for a valid session, we'd incorrectly mark it as expired. Mitigation: only mark as expired when we get a clear auth error status code.

## Open Questions

None — the approach is straightforward.
