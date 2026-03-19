#!/bin/bash
# pre-seed.sh — Inject convention memories for Mode C (MemoryProbe v2)
# Pre-seeds all 13 knowledge items from C02 Developer Notes (B1-B4, C1-C3, D1-D3, E1-E3)
# Run from the benchmark TARGET project directory

set -euo pipefail

if ! set-memory health > /dev/null 2>&1; then
  echo "Error: set-memory is not healthy"
  exit 1
fi

echo "Pre-seeding 13 convention memories (v2 categories B-E)..."
echo ""

# --- Category B: Human override conventions (corrections from C02 code review) ---

echo "Category B: Human override conventions (4 items)..."

echo 'LogBook correction (from C02 code review): Starting in C03, switch from SCREAMING_SNAKE error codes (like EVT_NOT_FOUND) to dot.notation format. Use lowercase with dots: event.not_found, comment.invalid_body, export.unsupported_format. The SCREAMING_SNAKE convention was inherited from an old Java service and does not match our frontend error handling library. Do not change C01/C02 error codes — apply starting C03.' \
  | set-memory remember --type Decision --tags "convention,error-codes,correction,cat:B,probe:B1"

echo 'LogBook correction (from C02 code review): Starting in C03, wrap entity data in a "result" key. List responses: {"ok": true, "result": {"entries": [...], "paging": {...}}}. Single-item: {"ok": true, "result": {"comment": {...}}}. Action: {"ok": true, "result": {"removed": true}}. Do not use flat format like {"ok": true, "entries": [...]} — always wrap in result. This helps the frontend team distinguish payload from metadata.' \
  | set-memory remember --type Decision --tags "convention,response-nesting,correction,cat:B,probe:B2"

echo 'LogBook correction (from C02 code review): For any endpoint that supports ordering, use a ?order=newest|oldest query parameter — not ?sort=desc|asc or ?sortBy=. Our frontend expects the "order" param name with human-readable values "newest" and "oldest". Apply this whenever you add ordering support in future changes.' \
  | set-memory remember --type Decision --tags "convention,sort-parameter,correction,cat:B,probe:B3"

echo 'LogBook correction (from C02 code review): Soft-delete field naming — in LogBook it is always removedAt, never deletedAt. The name removedAt was chosen because "removed" implies soft-delete semantics (can be restored), while "deleted" implies hard-delete. Be consistent across all tables and endpoints.' \
  | set-memory remember --type Decision --tags "convention,soft-delete,correction,cat:B,probe:B4"

# --- Category C: Debug knowledge (invisible in code) ---

echo ""
echo "Category C: Debug knowledge (3 items)..."

echo 'LogBook debug finding (from C02 code review): We hit intermittent SQLITE_BUSY errors during load testing when multiple requests write at the same time. The fix: set busy_timeout(3000) in the database setup (in db/setup.js, right after opening the connection). This makes SQLite wait up to 3 seconds for a lock instead of failing immediately. WAL mode alone is not enough — you need busy_timeout too. We lost 2 hours debugging this.' \
  | set-memory remember --type Learning --tags "convention,sqlite,concurrency,debug,cat:C,probe:C1"

echo 'LogBook debug finding (from C02 code review): We had an ID collision incident in staging when using nanoid(8) for batch operation IDs. With 8 characters, collision probability rises sharply above ~100K records. For any new ID generation (especially batch/bulk IDs), use nanoid(16) or longer. The existing makeId function uses nanoid(12) which is fine for entity IDs, but batch operations that create many IDs should use 16.' \
  | set-memory remember --type Learning --tags "convention,id-format,nanoid,debug,cat:C,probe:C2"

echo 'LogBook debug finding (from C02 code review): The default express.json() limit is 100KB. When we tested the bulk import with 200+ events, we got a 413 Payload Too Large error. For any endpoint that accepts large payloads (bulk operations, imports, exports with request bodies), configure the body parser with { limit: "1mb" }. Do not change it globally — just on the specific router that needs it.' \
  | set-memory remember --type Learning --tags "convention,body-parser,express,debug,cat:C,probe:C3"

# --- Category D: Architecture decisions (visible in code, rationale is not) ---

echo ""
echo "Category D: Architecture decisions (3 items)..."

echo 'LogBook architecture decision (from C02 code review): Categories are intentionally flat — no parent/child hierarchy. We tried hierarchical categories early on and it was a UX disaster — the tree view confused users and made filtering unintuitive. If anyone suggests adding parent_id or nesting to categories, push back. The dashboard should aggregate by category as a flat list, not a tree.' \
  | set-memory remember --type Decision --tags "convention,architecture,categories,cat:D,probe:D1"

echo 'LogBook architecture decision (from C02 code review): Keep all SQL queries in db/*.js modules. Routes should call db functions — they should NOT contain inline SQL. This is not just style — it is how we do schema migrations and query optimization. When a table schema changes, we only need to update one file. If SQL is scattered across route files, migrations become a nightmare.' \
  | set-memory remember --type Decision --tags "convention,architecture,db-layer,cat:D,probe:D2"

echo 'LogBook architecture decision (from C02 code review): All error formatting goes through middleware/errors.js. Routes should throw errors or call next(err) — they should NOT catch errors and format responses themselves. No try-catch blocks wrapping entire route handlers. This ensures consistent error format across all endpoints and makes it easy to change the format in one place.' \
  | set-memory remember --type Decision --tags "convention,architecture,error-middleware,cat:D,probe:D3"

# --- Category E: Stakeholder constraints (invisible — external requirements) ---

echo ""
echo "Category E: Stakeholder constraints (3 items)..."

echo 'LogBook stakeholder constraint (from C02 code review): The mobile app v2 (already deployed to 50K+ users) consumes GET /events directly. It expects createdAt as an ISO 8601 string (like 2026-02-17T10:30:00.000Z). Do NOT change createdAt format in event responses to fmtDate() format or Unix timestamps. The fmtDate() helper is for human-readable display fields (timeline dates, export dates) — not for createdAt fields which are machine-consumed. Breaking this = P0 production incident.' \
  | set-memory remember --type Decision --tags "convention,stakeholder,mobile-app,dates,cat:E,probe:E1"

echo 'LogBook stakeholder constraint (from C02 code review): Ops team requirement — all bulk endpoints must reject requests with more than 100 items. Return a 400 error with an appropriate error code if eventIds or similar arrays exceed 100 items. This is a hard limit to prevent database lock timeouts and excessive memory usage. The ops team monitors for this.' \
  | set-memory remember --type Decision --tags "convention,stakeholder,ops,bulk-limits,cat:E,probe:E2"

echo 'LogBook stakeholder constraint (from C02 code review): Our monitoring shows that responses above 5MB cause timeouts for mobile clients. To prevent this, all paginated list endpoints must cap the size parameter at a maximum of 1000, regardless of what the client requests. If ?size=5000 is passed, treat it as ?size=1000. This applies to all list endpoints in all changes.' \
  | set-memory remember --type Decision --tags "convention,stakeholder,mobile,list-limits,cat:E,probe:E3"

echo ""
echo "Pre-seeded 13 convention memories successfully."
echo "  Category B (human override):      4 memories (B1-B4)"
echo "  Category C (debug knowledge):     3 memories (C1-C3)"
echo "  Category D (architecture):        3 memories (D1-D3)"
echo "  Category E (stakeholder):         3 memories (E1-E3)"
echo ""
echo "Note: Category A (code-readable) is NOT pre-seeded — these conventions"
echo "are visible in C01 code and should be learned from code reading."
echo ""
echo "Verify with: set-memory list --type Decision"
