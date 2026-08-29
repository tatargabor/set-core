/**
 * Which provider an agent will run on, and which one it IS running on.
 *
 * The decisions live here as functions rather than inside the component, so
 * each can be asserted in both directions. The screen renders what these
 * return; it decides nothing itself.
 *
 * Three of them are failure-directional, and the direction is the reason they
 * are functions at all:
 *
 *  - **A provider with no credential is OFFERED, disabled, with the reason.**
 *    Omitting it is the false-absence class: a provider the machine declares
 *    would simply not be on the list, and a reader looking for the one they
 *    just configured would conclude the screen is broken rather than that the
 *    key is missing.
 *  - **An unrecorded provider is not the default.** `recorded: false` means
 *    nobody wrote down what this agent runs on. Rendering the machine default
 *    there is a claim about which account is being billed — and it is
 *    indistinguishable from a measured one, which is what makes it expensive.
 *  - **A credential from a project override is MARKED.** It is the case where
 *    the bill goes somewhere other than the reader expects, and it is invisible
 *    in every other way: same label, same terminal, same transcript.
 */

/** One declared provider, as the catalogue endpoint sends it. */
export interface ProviderCard {
  name: string
  models: string[]
  default_model: string | null
  requires_credential: boolean
  /** Whether a credential is CONFIGURED. Never the credential. */
  configured: boolean
  usable: boolean
}

export interface ProviderCatalogue {
  default_provider: string | null
  default_model: string | null
  providers: ProviderCard[]
  /**
   * What a start naming NOTHING resolves to for the project that was asked
   * about — computed by the SERVER's own resolver, not re-derived here.
   *
   * ⚠ This exists because the screen cannot see a project override: it lives in
   * a file only the owner reads. Measured by looking at the running dashboard:
   * a client-side preview said `anthropic · opus (machine default)` for a
   * project whose override sends it to `glm`. Not "unknown" — a confident,
   * plausible, wrong statement about which account the start would spend
   * against, in the one place this change exists to make visible.
   *
   * `null` means the server could not resolve one; render that as a gap.
   */
  resolved?: {
    provider: string
    model: string
    provenance: Record<string, string>
  } | null
}

/** What a listed agent says about its provider. */
export interface AgentProvider {
  /** `false` means nobody wrote it down — NOT "the default". */
  recorded: boolean
  provider: string | null
  model: string | null
  /** field name -> the level that supplied it. Never a secret. */
  provenance: Record<string, string>
}

export const LEVEL_DEFAULT = 'machine-default'
export const LEVEL_PROJECT = 'project'
export const LEVEL_REQUEST = 'request'
export const LEVEL_PROVIDER = 'provider-default'

/**
 * Every declared provider, in a stable order, each with why it cannot be used.
 *
 * ⚠ Nothing is filtered out. `disabledReason` is `null` for a usable one and a
 * sentence for the rest; the caller renders the option either way. A filter
 * here and a provider that does not exist look identical on the screen.
 */
export function offerableProviders(
  cat: ProviderCatalogue | null,
): Array<ProviderCard & { disabledReason: string | null }> {
  if (!cat) return []
  return cat.providers.map(p => ({
    ...p,
    disabledReason: p.usable
      ? null
      : p.requires_credential && !p.configured
        ? 'no credential configured for this provider yet'
        : 'declared but not usable',
  }))
}

/**
 * The models to offer for a chosen provider — or, with none chosen, none.
 *
 * An empty list with no provider chosen is correct rather than lazy: a model
 * belongs to a provider's catalogue, and a global model list is precisely the
 * cross-provider combination the resolver refuses everywhere else.
 */
export function modelsFor(cat: ProviderCatalogue | null, provider: string | null): string[] {
  if (!cat || !provider) return []
  return cat.providers.find(p => p.name === provider)?.models ?? []
}

export interface ResolvedPreview {
  provider: string | null
  model: string | null
  providerLevel: string
  modelLevel: string
}

/**
 * What the start WOULD resolve to, and which level supplies each half.
 *
 * A preview, so the reader sees the frame before the click rather than after
 * it. It deliberately mirrors the server's precedence instead of guessing:
 * request outranks the machine default, and a model named by the provider is
 * its own level — reporting a provider's own default as `machine-default`
 * would be a false value inside the mechanism that exists to prevent one.
 *
 * ⚠ It NEVER models the project override itself. With nothing chosen it hands
 * back the server's own resolution, provenance and all; only the levels the
 * screen can actually see — a provider or model the reader just picked — are
 * decided here. A preview that derived the override from what the browser can
 * see would be inventing the one level that decides whose account pays, and it
 * did exactly that until somebody looked at the running screen.
 */
export function previewResolution(
  cat: ProviderCatalogue | null,
  chosenProvider: string | null,
  chosenModel: string | null,
): ResolvedPreview {
  // Nothing chosen: the SERVER's answer, verbatim, including its provenance.
  // This is the branch that reports a project override, and it is the only one
  // that can — see `ProviderCatalogue.resolved`.
  if (!chosenProvider && !chosenModel && cat?.resolved) {
    return {
      provider: cat.resolved.provider,
      model: cat.resolved.model,
      providerLevel: cat.resolved.provenance?.provider ?? LEVEL_DEFAULT,
      modelLevel: cat.resolved.provenance?.model ?? LEVEL_DEFAULT,
    }
  }

  const provider = chosenProvider ?? cat?.default_provider ?? null
  const providerLevel = chosenProvider ? LEVEL_REQUEST : LEVEL_DEFAULT
  if (chosenModel) return { provider, model: chosenModel, providerLevel, modelLevel: LEVEL_REQUEST }

  const card = cat?.providers.find(p => p.name === provider) ?? null
  // The machine default model belongs to the machine default PROVIDER. Applied
  // to any other provider it is the cross-provider combination nobody wrote
  // down — the correction taken during implementation on the server side, held
  // here too so the preview and the resolver cannot disagree.
  if (cat?.default_model && provider === cat.default_provider) {
    return { provider, model: cat.default_model, providerLevel, modelLevel: LEVEL_DEFAULT }
  }
  if (card?.default_model) {
    return { provider, model: card.default_model, providerLevel, modelLevel: LEVEL_PROVIDER }
  }
  return { provider, model: null, providerLevel, modelLevel: LEVEL_DEFAULT }
}

/** How one field's provenance reads to a person. */
export function levelLabel(level: string | undefined): string {
  switch (level) {
    case LEVEL_REQUEST: return 'this start'
    case LEVEL_PROJECT: return 'project override'
    case LEVEL_PROVIDER: return "the provider's own default"
    case LEVEL_DEFAULT: return 'machine default'
    default: return 'unknown'
  }
}

export type ProviderMark =
  | { kind: 'unrecorded'; text: string; title: string }
  | { kind: 'override'; text: string; title: string }
  | { kind: 'plain'; text: string; title: string }

/**
 * The marker beside a running agent — three kinds, and they are three facts.
 *
 * `unrecorded` is a GAP and must not render as the default. `override` is the
 * one that changes who pays and is invisible otherwise, so it is marked rather
 * than merely reported. `plain` is everything else, and it still names the
 * provider — an agent whose frame is never stated is one whose cost and quality
 * the next reader assigns to the wrong frame.
 */
export function providerMark(p: AgentProvider | null | undefined): ProviderMark {
  if (!p || !p.recorded || !p.provider) {
    return {
      kind: 'unrecorded',
      text: 'provider unrecorded',
      title:
        'Nobody wrote down which provider this agent runs on — it was started before ' +
        'this was recorded, or by something that named none. This is a gap, not the default.',
    }
  }
  const label = p.model ? `${p.provider} · ${p.model}` : p.provider
  if (p.provenance?.credential === LEVEL_PROJECT) {
    return {
      kind: 'override',
      text: `${label} (project key)`,
      title:
        `Running on ${label}, with a credential from this project's override — ` +
        'so its cost lands on that account rather than on the machine default.',
    }
  }
  return {
    kind: 'plain',
    text: label,
    title:
      `Running on ${label}. Provider from ${levelLabel(p.provenance?.provider)}, ` +
      `model from ${levelLabel(p.provenance?.model)}, ` +
      `credential from ${levelLabel(p.provenance?.credential)}.`,
  }
}

/**
 * Read the catalogue. `null` means COULD NOT ASK — never an empty catalogue.
 *
 * The same distinction `fetchStartLocations` draws, for the same reason: an
 * empty provider list reads as "this machine declares none", and a screen that
 * says that after a failed request is reporting a measurement it did not make.
 */
export async function fetchProviderCatalogue(project?: string): Promise<ProviderCatalogue | null> {
  try {
    const res = await fetch(
      project ? `/api/fleet/providers?project=${encodeURIComponent(project)}` : '/api/fleet/providers')
    if (!res.ok) return null
    const body = await res.json()
    if (!body || !Array.isArray(body.providers)) return null
    return body as ProviderCatalogue
  } catch {
    return null
  }
}
