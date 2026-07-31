/**
 * Project Status — what the PROJECT says about itself, read live.
 *
 * Everything else in this dashboard shows what set-core did. This page shows where the
 * project stands: its releases, its open bugs, its environments, whatever else it chose
 * to publish. set-core does not model any of it; it asks and renders the answer.
 *
 * Three things this screen must never do, because each one turns a status panel into a
 * source of false calm:
 *
 * - **Show a gap as a zero.** A command that could not be asked renders as a visible
 *   failure with its reason, in the same place the number would have been.
 * - **Round anything.** Counts come from the project; they are shown as given.
 * - **Store what it read.** Nothing is cached in localStorage, nothing is posted back.
 *   The consumer's domain lives on the consumer's disk.
 *
 * The answers are tabbed, one tab per command the project declares. Tabs bring a risk
 * the stacked layout did not have: a failed command can sit behind an unselected tab,
 * so the page looks fine while something is broken. The tab strip therefore marks every
 * command that failed, and a count of them sits next to the strip — a gap must be
 * visible from wherever you are standing, not only from the tab it belongs to.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  getProjectStatus,
  postProjectWrite,
  type ProjectStatusResponse,
  type StatusCommandResult,
} from '../lib/api'
import StatusValue, {
  ActionProvider,
  DeprecationProvider,
  presentDeprecations,
} from '../components/StatusValue'
import {
  CaveatProvider,
  CaveatNote,
  presentCaveats,
  absentCaveatKeys,
  COMMAND_LEVEL_CAVEAT,
} from '../components/statusShape'

interface Props {
  project?: string | null
}

/** Why a command produced nothing — in the operator's terms, not the project's. */
const GAP_HINT: Record<string, string> = {
  'not-configured': 'This project publishes no status contract.',
  'command-not-found': 'The configured command is not on this machine.',
  'timeout': 'The project did not answer in time.',
  'spawn-failed': 'The command could not be started.',
  'response-too-large': 'The answer was too large to be a summary.',
  'nonzero-exit': 'The command ran and failed.',
  'invalid-json': 'The answer was not JSON.',
  'invalid-envelope': 'The answer was not in the contract envelope.',
  'missing-version': 'The answer declared no contract version.',
  'unsupported-version': 'The answer uses a contract version this set-core does not read.',
  'project-reported-failure': 'The project answered, and reported a failure.',
  'missing-data': 'The envelope arrived without data.',
}

function Gap({ name, result }: { name: string; result: StatusCommandResult }) {
  const hint = result.errorClass ? GAP_HINT[result.errorClass] : undefined
  return (
    <section className="rounded-lg border border-red-900/60 bg-red-950/20 p-4 space-y-1">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-red-300">{name}</h2>
        {result.errorClass && (
          <code className="text-xs px-1.5 py-0.5 rounded bg-red-950/60 text-red-400">
            {result.errorClass}
          </code>
        )}
      </div>
      {hint && <p className="text-xs text-red-200/80">{hint}</p>}
      {result.error && <p className="text-xs text-neutral-400">{result.error}</p>}
    </section>
  )
}

function Answer({
  name, result, onAction,
}: {
  name: string
  result: StatusCommandResult
  onAction: (command: string, args: Record<string, unknown>) => Promise<{ ok: boolean; error?: string | null }>
}) {
  // Deprecated fields are hidden by default, per command. A field the project has
  // replaced but still emits would otherwise sit next to its replacement contradicting
  // it — found on a live screen, not reasoned about.
  const [showDeprecated, setShowDeprecated] = useState(false)
  // The declaration says what to look for; the DATA says how many there are. A field
  // declared deprecated but no longer sent would otherwise be announced as hidden when
  // it was never there — a false absence, and the mirror of the false value this
  // mechanism exists to prevent. Raised by the consumer's side as an invariant on
  // theirs; it turned out to bite here too.
  const declared = new Set(result.deprecated ?? [])
  const deprecated = presentDeprecations(result.data, declared)

  // Caveats: the same rule one field along. The declaration says what to look for, the DATA
  // says what is there — a caveat printed for a field the project stopped sending would be a
  // false absence, which is what `presentDeprecations` was corrected for.
  //
  // ADDITIVE, never replacing: the "*" sentence always applies and always shows, and a
  // per-field sentence ADDS to it. The direction is the argument — forget a per-field entry
  // and the general caveat still stands; let it replace, and the narrower sentence silently
  // swallows the broader one.
  const caveats = result.caveats ?? {}
  const starCaveat = caveats[COMMAND_LEVEL_CAVEAT]
  const perField = presentCaveats(result.data, caveats)
  const absentCaveats = absentCaveatKeys(result.data, caveats)
  const [showAbsent, setShowAbsent] = useState(false)

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium text-neutral-100">{name}</h2>
        <div className="flex items-center gap-3 text-xs text-neutral-600">
          {deprecated.size > 0 && (
            <button
              onClick={() => setShowDeprecated(v => !v)}
              className="text-neutral-500 hover:text-neutral-300 underline decoration-dotted"
              title="fields the project still emits but no longer stands behind"
            >
              {showDeprecated ? 'hide' : 'show'} {deprecated.size} deprecated
            </button>
          )}
          {absentCaveats.length > 0 && (
            <button
              onClick={() => setShowAbsent(v => !v)}
              className="text-neutral-500 hover:text-neutral-300 underline decoration-dotted"
              title="declared caveats whose key is not in this answer — diagnostics, not a fault"
            >
              {showAbsent ? 'hide' : 'show'} {absentCaveats.length} unmatched caveat{absentCaveats.length === 1 ? '' : 's'}
            </button>
          )}
          {result.contractVersion !== null && <span>contract v{result.contractVersion}</span>}
          {/* The project's own timestamp, shown verbatim — re-formatting it would mean
              deciding what its timezone meant. */}
          {result.generatedAt && <span title="as reported by the project">{result.generatedAt}</span>}
        </div>
      </div>
      {/* Once, in the header — not repeated beside every value. It qualifies the command. */}
      {starCaveat && <CaveatNote>{starCaveat}</CaveatNote>}
      {showAbsent && absentCaveats.length > 0 && (
        <div className="text-xs text-neutral-500 space-y-0.5">
          <div className="text-neutral-600">
            declared, but no field of this answer carries the key — legitimate when the value is
            currently absent, a typo otherwise. The project decides; this only shows the question.
          </div>
          {absentCaveats.map((k: string) => (
            <div key={k} className=" text-neutral-400">{k}</div>
          ))}
        </div>
      )}
      <DeprecationProvider value={{ names: deprecated, show: showDeprecated }}>
        <CaveatProvider value={{ perField }}>
          <ActionProvider value={onAction}>
            <StatusValue value={result.data} />
          </ActionProvider>
        </CaveatProvider>
      </DeprecationProvider>
    </section>
  )
}

export default function ProjectStatus({ project }: Props) {
  const [data, setData] = useState<ProjectStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // The active tab is held by NAME, not by index: the project can change what it
  // declares between two loads, and an index would then quietly select a different
  // command than the one that was open.
  const [active, setActive] = useState<string | null>(null)
  // Answers the project marked too expensive to ask automatically, once someone has
  // asked. Kept apart from `data` so a later page-load refresh cannot silently drop
  // them — an answer that vanishes because something else reloaded reads as a failure.
  const [onDemandData, setOnDemandData] = useState<Record<string, StatusCommandResult>>({})
  const [asking, setAsking] = useState<string | null>(null)

  const load = useCallback((refresh = false) => {
    if (!project) return
    setLoading(true)
    setError(null)
    getProjectStatus(project, { refresh })
      .then(setData)
      .catch(e => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false))
  }, [project])

  // An expensive answer is fetched only when a person asks for it by name. The page
  // never does this on its own: one measured probe on a real project took minutes, and
  // a status screen that hangs is a status screen nobody opens.
  const askOnDemand = useCallback((name: string) => {
    if (!project) return
    setAsking(name)
    getProjectStatus(project, { commands: [name], refresh: true })
      .then(res => {
        const result = res.commands?.[name]
        if (result) setOnDemandData(prev => ({ ...prev, [name]: result }))
      })
      .catch(e => setError(String(e?.message ?? e)))
      .finally(() => setAsking(null))
  }, [project])

  // No polling. A contract call spawns the project's own toolchain — one measured
  // command took minutes. This page refreshes when asked, and says how old it is.
  useEffect(() => { load(false) }, [load])

  // A write goes out, and then the page re-reads. Not because the answer is stale by a
  // clock, but because it is stale by an action WE took — leaving the old answer on
  // screen would show a step as outstanding immediately after recording that it is not.
  const runAction = useCallback(
    async (command: string, args: Record<string, unknown>) => {
      if (!project) return { ok: false, error: 'no project' }
      const res = await postProjectWrite(project, command, args)
      if (res.ok) load(true)
      return { ok: res.ok, error: res.error }
    },
    [project, load],
  )

  if (!project) {
    return <div className="p-6 text-sm text-neutral-500">Select a project.</div>
  }

  const contract = data?.contract
  // The tab strip lists every declared command, including the expensive ones. Leaving
  // those out until asked would hide that the project answers them at all — and a reader
  // cannot ask for something they cannot see.
  const answered = { ...(data?.commands ?? {}), ...onDemandData }
  const declaredOrder = contract?.commands ?? []
  const names = declaredOrder.length
    ? declaredOrder.filter(n => n in answered || (contract?.onDemand ?? []).includes(n))
    : Object.keys(answered)
  const entries: Array<[string, StatusCommandResult | undefined]> =
    names.map(n => [n, answered[n]])
  // An unasked answer is NOT a failure and must never be counted as one — that is the
  // false-absence shape, and the tab strip is exactly where it would be believed.
  const failing = entries.filter(([, r]) => r && !r.ok)
  // Which tab opens: the reader's choice if they made one, then the project's declared
  // primary, then declaration order. The middle step is the point — without it the page
  // opens on whatever the project happened to list first, which is an ordering decision
  // nobody made. Only the project knows which of its answers is "where do we stand", and
  // set-core must not infer it from a command's name.
  const preferred = contract?.primary && entries.some(([n]) => n === contract.primary)
    ? contract.primary
    : entries[0]?.[0] ?? null
  const activeName = active && entries.some(([n]) => n === active) ? active : preferred
  const activeResult = entries.find(([n]) => n === activeName)?.[1]

  return (
    // Same three-zone shell as the Orchestration dashboard so the two read as one product
    // (user, 2026-07-25): a StatusHeader-styled bar, a pill tab strip, then a scroll region.
    // The vertical flex column with overflow-hidden keeps the header and tabs fixed while the
    // answer below scrolls on its own — a live answer is 67 rows by nine columns, and its
    // horizontal scrolling belongs to the table, never to the page.
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header bar — mirrors StatusHeader's chrome (bg, border, padding) so the two apps
          share one visual language. */}
      <div className="flex flex-wrap items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 border-b border-neutral-800 bg-neutral-900/50 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-neutral-100">{project}</h2>
          <span
            className="px-2 py-0.5 rounded text-sm font-medium bg-neutral-800 text-neutral-400"
            title="Read live from the project's own contract — not from set-core's records."
          >
            Project Status
          </span>
        </div>

        {contract?.configured && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-neutral-600">
            <span>via <span className="text-neutral-400">{contract.source}</span></span>
            <code className="text-neutral-500 break-all">{contract.command}</code>
            {contract.timeout !== null && <span>timeout {contract.timeout}s</span>}
          </div>
        )}

        <button
          onClick={() => load(true)}
          disabled={loading}
          className="ml-auto px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm rounded font-medium bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {loading ? 'Asking…' : 'Ask again'}
        </button>
      </div>

      {/* Tab bar — pill style, identical to the Orchestration dashboard's tab bar. */}
      {entries.length > 0 && (
        <div
          role="tablist"
          className="flex items-center gap-1 px-3 py-1 border-b border-neutral-800 bg-neutral-900 overflow-x-auto max-w-full scrollbar-hide shrink-0"
        >
          {entries.map(([name, result]) => {
            const isActive = name === activeName
            return (
              <button
                key={name}
                role="tab"
                aria-selected={isActive}
                data-status-tab={name}
                onClick={() => setActive(name)}
                className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm whitespace-nowrap rounded transition-colors ${
                  isActive
                    ? 'bg-neutral-800 text-neutral-200 font-medium'
                    : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50'
                }`}
              >
                {name}
                {/* A failed command must be visible from every tab, not only its own —
                    otherwise tabbing is how a broken thing starts looking fine. An
                    UNASKED one gets a different, quiet mark: it is not broken, and one
                    visual weight per meaning means red stays reserved for broken. */}
                {result && !result.ok && (
                  <span className="ml-1.5 text-red-400" title="this command failed">●</span>
                )}
                {!result && (
                  <span className="ml-1.5 text-neutral-600" title="not asked yet — expensive">○</span>
                )}
              </button>
            )
          })}
          {failing.length > 0 && (
            <span className="ml-auto shrink-0 pl-2 pr-1 text-xs text-red-400">
              {failing.length} of {entries.length} failed
            </span>
          )}
        </div>
      )}

      {/* Scroll region — the answer and every banner live here. */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
        {error && (
          <div className="rounded-lg border border-red-900/60 bg-red-950/20 p-4 text-xs text-red-300">
            Could not reach set-core's status route: {error}
          </div>
        )}

        {contract && !contract.configured && (
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-2">
            <h2 className="text-sm font-medium text-neutral-200">
              This project publishes no status contract
            </h2>
            <p className="text-xs text-neutral-500">
              Nothing is wrong — most projects publish none. To make this page live, the
              project drops a <code className="text-neutral-400">.set-endpoint.json</code> at
              its root declaring the command set-core may run and which questions it answers,
              or an operator sets <code className="text-neutral-400">status_api.command</code> in
              its orchestration config.
            </p>
          </div>
        )}

        {/* A single "*" gap is the contract-level one: configured, but nothing declared. */}
        {data?.gaps?.['*'] && (
          <div className="rounded-lg border border-amber-900/60 bg-amber-950/20 p-4 text-xs text-amber-200">
            {data.gaps['*']}
          </div>
        )}

        {activeName && !activeResult && (
          <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
            <h2 className="text-sm font-medium text-neutral-100">{activeName}</h2>
            <p className="text-xs text-neutral-500">
              The project marks this answer as expensive, so the page does not ask for it on
              its own. Nothing is known about it yet — this is not a gap and not a zero.
            </p>
            <button
              onClick={() => askOnDemand(activeName)}
              disabled={asking === activeName}
              className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {asking === activeName ? 'Asking…' : 'Ask now'}
            </button>
          </section>
        )}

        {activeName && activeResult && (
          activeResult.ok
            ? <Answer name={activeName} result={activeResult} onAction={runAction} />
            : <Gap name={activeName} result={activeResult} />
        )}

        {!loading && contract?.configured && entries.length === 0 && !data?.gaps?.['*'] && (
          <div className="text-sm text-neutral-500">The project declared no questions to ask.</div>
        )}
      </div>
    </div>
  )
}
