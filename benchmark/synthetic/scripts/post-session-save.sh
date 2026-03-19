#!/bin/bash
# post-session-save.sh — Extract conventions from change files and save to memory
#
# Called by run.sh after each Mode B session. Reads the change file,
# extracts Developer Notes corrections, and saves them as memories.
# This ensures forward-looking advice gets saved even when the agent
# runs out of turns before step 8.
#
# Usage: post-session-save.sh <change-file> <change-number>

set -euo pipefail

CHANGE_FILE="${1:?Usage: post-session-save.sh <change-file> <change-number>}"
CHANGE_NUM="${2:?}"

command -v set-memory &>/dev/null || exit 0
set-memory health &>/dev/null || exit 0

# --- Extract and save Developer Notes corrections ---

if grep -q "Developer Notes" "$CHANGE_FILE" 2>/dev/null; then
  echo "    Found Developer Notes in C$CHANGE_NUM"

  # Extract the Developer Notes section (between ### Developer Notes and the next ### or end)
  NOTES=$(sed -n '/### Developer Notes/,/^### /p' "$CHANGE_FILE" | head -n -1)

  # Parse numbered items from Developer Notes
  # Each item starts with a number followed by period and bold text
  echo "$NOTES" | grep -E '^\s*[0-9]+\.' | while IFS= read -r line; do
  # Clean up the line — strip leading whitespace and number prefix
  clean=$(echo "$line" | sed 's/^\s*[0-9]\+\.\s*//')

  # Skip empty lines
  [[ -z "$clean" ]] && continue

  # Determine tags based on content
  TAGS="convention,correction,change:C${CHANGE_NUM},source:devnotes"
  case "$clean" in
    *error*code*|*dot.notation*|*SCREAMING*)
      TAGS="$TAGS,error-codes,cat:B"
      ;;
    *result*key*|*nesting*|*wrapper*)
      TAGS="$TAGS,response-format,cat:B"
      ;;
    *sort*|*order*|*newest*|*oldest*)
      TAGS="$TAGS,sort-order,cat:B"
      ;;
    *removedAt*|*deletedAt*|*soft-delete*|*Soft-delete*)
      TAGS="$TAGS,soft-delete,cat:B"
      ;;
    *busy_timeout*|*SQLITE_BUSY*|*concurrent*)
      TAGS="$TAGS,sqlite,concurrency,cat:C"
      ;;
    *nanoid*|*collision*)
      TAGS="$TAGS,id-format,cat:C"
      ;;
    *body-parser*|*413*|*Payload*Too*Large*|*limit*)
      TAGS="$TAGS,body-parser,cat:C"
      ;;
    *flat*categor*|*hierarchical*|*parent_id*)
      TAGS="$TAGS,architecture,cat:D"
      ;;
    *query*layer*|*inline*SQL*|*db/*.js*)
      TAGS="$TAGS,architecture,cat:D"
      ;;
    *centralized*error*|*try-catch*|*next.err*)
      TAGS="$TAGS,architecture,cat:D"
      ;;
    *ISO*8601*|*mobile*app*|*backward*compat*)
      TAGS="$TAGS,stakeholder,cat:E"
      ;;
    *bulk*|*batch*|*100*item*|*max*)
      TAGS="$TAGS,stakeholder,cat:E"
      ;;
    *date*|*fmtDate*|*format*)
      TAGS="$TAGS,date-format"
      ;;
  esac

  # Save to memory
  echo "LogBook project correction (from C$CHANGE_NUM code review): $clean" \
    | set-memory remember --type Decision --tags "$TAGS" 2>/dev/null || true
  echo "    Saved: ${clean:0:80}..."
  done
fi

# --- Also save key conventions from existing code (C01 only) ---

if [[ "$CHANGE_NUM" == "01" ]]; then
  # After C01, save the conventions established in code
  # These are Category A (code-readable) but having them in memory helps recall

  if [[ -f "src/routes/events.js" ]]; then
    # Check for pagination format
    if grep -q "entries" "src/routes/events.js" 2>/dev/null; then
      echo 'LogBook convention: List endpoints use {entries: [...], paging: {current, size, count, pages}} format for pagination.' \
        | set-memory remember --type Decision --tags "convention,pagination,api-format,source:code" 2>/dev/null || true
      echo "    Saved: pagination convention"
    fi

    # Check for error format
    if grep -q "fault" "src/routes/events.js" 2>/dev/null || grep -q "fault" "src/middleware/errors.js" 2>/dev/null; then
      echo 'LogBook convention: Error responses use {fault: {reason: "...", code: "...", ts: "..."}} format. Key: fault (not error), reason (not message).' \
        | set-memory remember --type Decision --tags "convention,error-format,api-format,source:code" 2>/dev/null || true
      echo "    Saved: error format convention"
    fi

    # Check for ok wrapper
    if grep -q "ok: true" "src/routes/events.js" 2>/dev/null; then
      echo 'LogBook convention: All success responses include {ok: true, ...} wrapper.' \
        | set-memory remember --type Decision --tags "convention,response-format,api-format,source:code" 2>/dev/null || true
      echo "    Saved: ok wrapper convention"
    fi

    # Check for ID format
    if grep -q "makeId" "src/lib/ids.js" 2>/dev/null; then
      echo 'LogBook convention: Entity IDs use prefixed nanoid format via makeId(prefix) from lib/ids.js. Events: evt_, Categories: cat_.' \
        | set-memory remember --type Decision --tags "convention,id-format,source:code" 2>/dev/null || true
      echo "    Saved: ID format convention"
    fi

    # Check for fmtDate
    if [[ -f "src/lib/fmt.js" ]]; then
      echo 'LogBook convention: ALL dates in API responses use fmtDate() from lib/fmt.js. Returns YYYY/MM/DD HH:mm format.' \
        | set-memory remember --type Decision --tags "convention,date-format,utility,source:code" 2>/dev/null || true
      echo "    Saved: date format convention"
    fi

    # Check for removedAt
    if grep -q "removedAt" "src/db/setup.js" 2>/dev/null; then
      echo 'LogBook convention: Soft-delete uses removedAt column (nullable DATETIME). NOT deletedAt or isDeleted.' \
        | set-memory remember --type Decision --tags "convention,soft-delete,database,source:code" 2>/dev/null || true
      echo "    Saved: soft-delete convention"
    fi
  fi
fi

echo "    Memory extraction complete for C$CHANGE_NUM"
