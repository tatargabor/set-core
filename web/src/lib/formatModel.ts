/**
 * Centralized model-label formatting for the web admin UI.
 *
 * The orchestration backend emits model identifiers in several forms:
 *   - short aliases  : "opus", "sonnet", "haiku"
 *   - explicit pins  : "opus-4-6", "opus-4-7", "sonnet-4-6"
 *   - full claude IDs: "claude-opus-4-7", "claude-sonnet-4-6",
 *                      "claude-haiku-4-5-20251001"
 *   - 1M-context     : "claude-opus-4-7[1m]" → render as "opus-4-7-1m"
 *
 * Two helpers:
 *   modelFamily(m)  → "opus" | "sonnet" | "haiku" | m    (for colour grouping)
 *   displayModel(m) → human-readable full version label (for display)
 *
 * Display labels:
 *   "claude-opus-4-7"             → "opus-4-7"
 *   "claude-opus-4-6"             → "opus-4-6"
 *   "claude-sonnet-4-6"           → "sonnet-4-6"
 *   "claude-haiku-4-5-20251001"   → "haiku-4-5"
 *   "claude-opus-4-7[1m]"         → "opus-4-7-1m"
 *   "opus" / "sonnet" / "haiku"   → unchanged (the alias is the label)
 */

/** Family-only identifier — suitable for colour-keyed grouping. */
export function modelFamily(model?: string): string {
  if (!model) return ''
  const m = model.toLowerCase()
  if (m.includes('opus')) return 'opus'
  if (m.includes('sonnet')) return 'sonnet'
  if (m.includes('haiku')) return 'haiku'
  return model
}

/** Full version label for display. Strips `claude-` prefix and the
 * haiku date suffix; converts `[1m]` to a `-1m` suffix.
 */
export function displayModel(model?: string): string {
  if (!model) return ''
  let s = model.trim()
  // Normalize 1M-context suffix: "...[1m]" → "...-1m"
  s = s.replace(/\[1m\]/i, '-1m')
  // Drop the `claude-` prefix the CLI/SDK emits
  if (s.toLowerCase().startsWith('claude-')) s = s.slice(7)
  // haiku full ID has a date suffix (e.g. "haiku-4-5-20251001"); drop it
  // so labels stay short. Keep the X-Y version part.
  // Match: <family>-<num>-<num>-<longdigits>  → <family>-<num>-<num>
  s = s.replace(/^(haiku-\d+-\d+)-\d{6,}$/i, '$1')
  return s
}
