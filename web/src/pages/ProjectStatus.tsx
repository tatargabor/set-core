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
 */

import { useCallback, useEffect, useState } from 'react'
import {
  getProjectStatus,
  type ProjectStatusResponse,
  type StatusCommandResult,
} from '../lib/api'
import StatusValue, { DeprecationProvider, presentDeprecations } from '../components/StatusValue'

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
          <code className="text-[11px] px-1.5 py-0.5 rounded bg-red-950/60 text-red-400">
            {result.errorClass}
          </code>
        )}
      </div>
      {hint && <p className="text-xs text-red-200/80">{hint}</p>}
      {result.error && <p className="text-xs text-neutral-400">{result.error}</p>}
    </section>
  )
}

function Answer({ name, result }: { name: string; result: StatusCommandResult }) {
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

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium text-neutral-100">{name}</h2>
        <div className="flex items-center gap-3 text-[11px] text-neutral-600">
          {deprecated.size > 0 && (
            <button
              onClick={() => setShowDeprecated(v => !v)}
              className="text-neutral-500 hover:text-neutral-300 underline decoration-dotted"
              title="fields the project still emits but no longer stands behind"
            >
              {showDeprecated ? 'hide' : 'show'} {deprecated.size} deprecated
            </button>
          )}
          {result.contractVersion !== null && <span>contract v{result.contractVersion}</span>}
          {/* The project's own timestamp, shown verbatim — re-formatting it would mean
              deciding what its timezone meant. */}
          {result.generatedAt && <span title="as reported by the project">{result.generatedAt}</span>}
        </div>
      </div>
      <DeprecationProvider value={{ names: deprecated, show: showDeprecated }}>
        <StatusValue value={result.data} />
      </DeprecationProvider>
    </section>
  )
}

export default function ProjectStatus({ project }: Props) {
  const [data, setData] = useState<ProjectStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback((refresh = false) => {
    if (!project) return
    setLoading(true)
    setError(null)
    getProjectStatus(project, { refresh })
      .then(setData)
      .catch(e => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false))
  }, [project])

  // No polling. A contract call spawns the project's own toolchain — one measured
  // command took minutes. This page refreshes when asked, and says how old it is.
  useEffect(() => { load(false) }, [load])

  if (!project) {
    return <div className="p-6 text-sm text-neutral-500">Select a project.</div>
  }

  const contract = data?.contract
  const entries = Object.entries(data?.commands ?? {})

  return (
    <div className="p-6 space-y-4 max-w-5xl overflow-y-auto h-full">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-base font-semibold text-neutral-100">Project Status</h1>
          <p className="text-xs text-neutral-500">
            Read live from the project's own contract — not from set-core's records.
          </p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {loading ? 'Asking…' : 'Ask again'}
        </button>
      </header>

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

      {contract?.configured && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-neutral-600">
          <span>via <span className="text-neutral-400">{contract.source}</span></span>
          <code className="text-neutral-500 break-all">{contract.command}</code>
          {contract.timeout !== null && <span>timeout {contract.timeout}s</span>}
        </div>
      )}

      {/* A single "*" gap is the contract-level one: configured, but nothing declared. */}
      {data?.gaps?.['*'] && (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/20 p-4 text-xs text-amber-200">
          {data.gaps['*']}
        </div>
      )}

      {entries.map(([name, result]) =>
        result.ok
          ? <Answer key={name} name={name} result={result} />
          : <Gap key={name} name={name} result={result} />
      )}

      {!loading && contract?.configured && entries.length === 0 && !data?.gaps?.['*'] && (
        <div className="text-sm text-neutral-500">The project declared no questions to ask.</div>
      )}
    </div>
  )
}
