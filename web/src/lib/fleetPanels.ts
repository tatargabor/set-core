/**
 * What KIND of panel this is — declared by whatever opened it, never inferred.
 *
 * ## The assumption this file exists to remove
 *
 * Until now every panel on the fleet screen was an agent terminal. Nothing said
 * so; it was true because nothing else had ever been put there, and the stored
 * memory encoded it by holding a bare list of terminal labels. A list of strings
 * means "agent" only to a reader who already knows.
 *
 * So a panel now carries `{ kind, id }`. The agent terminal becomes one kind
 * among several rather than the implicit whole, which is what lets a second kind
 * exist at all.
 *
 * ## Declared, not inferred — the same shape three other records here reached
 *
 * `requested_by` for lineage, the agent goal, and the population of an agent are
 * all recorded at the moment of the act, for one measured reason: a fact that
 * exists only when something is created cannot be recovered later by inspecting
 * the result. Guessing a panel's kind from its contents would be wrong exactly
 * when the contents are unusual — which is when it matters.
 *
 * ## An unknown kind is REPORTED, never rendered as the kind it resembles
 *
 * A stored layout outlives the build that wrote it. When a panel names a kind
 * this build does not have, the honest outcome is to say so where the reader is
 * standing — the same rule the arrangement already applies to a project it can
 * no longer find: report it, do not silently drop it. Rendering it as an agent
 * tile with empty fields would be the false-value class, and dropping it would
 * be false absence: the reader would conclude they had closed something they
 * never closed.
 */

/** The agent terminal — the kind every panel used to be. */
export const PANEL_AGENT = 'agent'

/**
 * Every panel kind this build can render.
 *
 * A registry rather than a union type alone, because the question asked at
 * runtime — *can I render what this stored layout names?* — is about THIS build,
 * and a type has no answer at runtime. Docked view kinds join this list as they
 * are built; nothing here may name a domain concept, because the framework layer
 * knows that a view exists and never what it lists.
 */
export const KNOWN_PANEL_KINDS: readonly string[] = [PANEL_AGENT]

/** One panel: what kind it is, and which instance of that kind. */
export interface PanelRef {
  kind: string
  /** Identifies the instance within its kind — for an agent, its label. */
  id: string
}

export type PanelResolution =
  /** This build can render it. */
  | { known: true; ref: PanelRef }
  /**
   * This build cannot. NOT an error and NOT a reason to drop the panel: the
   * surface renders a placeholder naming the kind, so the reader can see that
   * something is there and what it claims to be.
   */
  | { known: false; ref: PanelRef; reason: string }

/** Whether a value is a usable panel reference at all. */
export function isPanelRef(value: unknown): value is PanelRef {
  if (!value || typeof value !== 'object') return false
  const v = value as Partial<PanelRef>
  return typeof v.kind === 'string' && v.kind.length > 0
    && typeof v.id === 'string' && v.id.length > 0
}

/**
 * Resolve one panel against what this build knows.
 *
 * Note what this deliberately does NOT do: decide whether the instance still
 * exists. That is the caller's join against live state, and conflating the two
 * would make "this build cannot render that kind" and "that agent has gone"
 * arrive as one answer, when they need different words on screen.
 */
export function resolvePanel(ref: PanelRef): PanelResolution {
  if (KNOWN_PANEL_KINDS.includes(ref.kind)) return { known: true, ref }
  return {
    known: false,
    ref,
    reason: `this build has no panel of kind "${ref.kind}"`,
  }
}

/**
 * The panels a stored view asks for, in order, each resolved.
 *
 * **Reads the older shape too.** A memory written before panels had kinds holds
 * `terminals: string[]`, which meant agents. Those become agent panels here
 * rather than being migrated in place: a migration that rewrites storage on read
 * turns every reader into a writer, and a reader that cannot write (private mode,
 * a disabled store) would then silently lose the layout it just read.
 *
 * Anything unusable is dropped rather than guessed at — a stored entry that is
 * not a panel reference is corruption, not a preference.
 */
export function resolvePanels(
  stored: { panels?: unknown; terminals?: readonly string[] } | null | undefined,
): PanelResolution[] {
  const out: PanelResolution[] = []
  const seen = new Set<string>()
  const push = (ref: PanelRef) => {
    const key = `${ref.kind} ${ref.id}`
    if (seen.has(key)) return
    seen.add(key)
    out.push(resolvePanel(ref))
  }
  for (const label of stored?.terminals ?? []) {
    if (typeof label === 'string' && label) push({ kind: PANEL_AGENT, id: label })
  }
  const panels = stored?.panels
  if (Array.isArray(panels)) for (const entry of panels) if (isPanelRef(entry)) push(entry)
  return out
}

/** The panels this build can render, unwrapped — the ordinary rendering path. */
export function renderablePanels(resolutions: readonly PanelResolution[]): PanelRef[] {
  return resolutions
    .filter((r): r is Extract<PanelResolution, { known: true }> => r.known)
    .map(r => r.ref)
}

/**
 * The panels this build cannot render.
 *
 * Named as its own list rather than left to be derived by subtraction, for the
 * same reason `parked_missing` is stated on the server: an inference standing in
 * for data is where a wrong answer looks like a computed one.
 */
export function unrenderablePanels(
  resolutions: readonly PanelResolution[],
): Extract<PanelResolution, { known: false }>[] {
  return resolutions.filter((r): r is Extract<PanelResolution, { known: false }> => !r.known)
}
