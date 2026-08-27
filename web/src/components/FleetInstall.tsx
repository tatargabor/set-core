import { useCallback, useState } from 'react'
import { Blocks, CircleDashed } from 'lucide-react'

import { Chip } from './Chip'

import {
  type Capability,
  type CapabilityReport,
  type InstallReport,
  type Refusal,
  changeStanding,
  installOffered,
  moduleStanding,
  noOfferNote,
  refusalOf,
  reportHeadline,
  reportTense,
  skipsWithReasons,
} from '../lib/fleetInstall'

/**
 * The modules a project has, and installing one — task 7.15.
 *
 * ## Why this is the careful one
 *
 * Every other control on this screen reads. This one **writes into a repository
 * the framework does not own**, so the shape is: a preview first, the report
 * rendered in full, and only then a second, deliberate click that writes. The
 * preview is not a formality — it is the only place the reader can see what the
 * install would leave alone, and *that* is the half a success message hides.
 *
 * ## What the panel refuses to do
 *
 *  - **Render only the successes.** Six untouched files is a good outcome and a
 *    misleading screen unless it is said. Skips are listed with their reasons,
 *    at the same weight as the writes.
 *  - **Compute `changed_nothing`.** It is the producer's own field. Deriving it
 *    from an empty `written` is a second copy of the rule, and the copy that
 *    reads as success.
 *  - **Draw a refusal as an offer.** A missing requirement comes back as 409 and
 *    is rendered red, terminal, with no retry beside it — a warning is something
 *    a reader clicks past, and what lies past it is a half-installed project.
 *  - **Say "wrote" about a preview.** The two payloads differ by one boolean,
 *    so the tense comes from the report rather than from the caller's memory of
 *    which button was pressed.
 */

const STATE_STYLE: Record<string, string> = {
  connected: 'text-emerald-400',
  partial: 'text-amber-400',
  'not-connected': 'text-fg-muted',
  unknown: 'text-amber-400',
}

/**
 * One module's attempt, as a record rather than a state machine.
 *
 * A preview and the real install that follows it are two runs of the same
 * route, and the second must not blank the first while it is in flight: the
 * report on screen is what the reader authorised, and taking it away mid-write
 * leaves them watching a spinner with nothing to compare the outcome to.
 */
interface Attempt {
  running: boolean
  report?: InstallReport
  refusal?: Refusal
}

function ReportBlock({ report, module, root, onInstall, installing }: {
  report: InstallReport
  module: string
  /** The directory the write would land in — the blast radius, named. */
  root?: string
  /** Absent once the write has happened — a real install is not offered twice. */
  onInstall?: () => void
  installing?: boolean
}) {
  const tense = reportTense(report)
  const change = changeStanding(report)
  const skips = skipsWithReasons(report)
  const written = Array.isArray(report.written) ? report.written : []
  return (
    <div className="mt-1.5 border-l-2 border-surface-edge pl-2 space-y-1" data-fleet-install-report={module}>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span
          className={`text-xs font-semibold ${report.dry_run ? 'text-sky-300' : 'text-emerald-400'}`}
          data-fleet-install-tense={report.dry_run ? 'preview' : 'done'}
        >
          {reportHeadline(report)}
        </span>
        <span className="text-xs text-fg-ghost">{tense.note}</span>
      </div>

      {/* `changed_nothing` said out loud — its own field, and the outcome most
          likely to be read as failure when it is in fact the ledger working. */}
      {change.kind === 'nothing' && (
        <div className="text-xs text-fg-muted" data-fleet-install-changed="nothing">
          this install wrote no files — every one of them was left alone for the reason beside it
        </div>
      )}
      {change.kind === 'unstated' && (
        <div className="text-xs text-amber-400" data-fleet-install-changed="unstated">
          ⚠ the report did not say whether anything was written
        </div>
      )}

      {written.length > 0 && (
        <details className="text-xs" data-fleet-install-written={written.length}>
          <summary className="text-fg-muted cursor-pointer">{written.length} file(s) {tense.verb}</summary>
          <ul className="mt-1 space-y-0.5 text-fg-ghost max-h-40 overflow-y-auto">
            {written.map(p => <li key={p} className="truncate" title={p}>{p}</li>)}
          </ul>
        </details>
      )}

      {/* Never behind a fold. The skips are the half a "done" would hide, and
          `ui-quality.md` forbids compacting a thing the reader has to see. */}
      {skips.length > 0 && (
        <div className="text-xs" data-fleet-install-skipped={skips.length}>
          <div className="text-fg-muted">{skips.length} file(s) left alone:</div>
          <ul className="mt-0.5 space-y-0.5">
            {skips.map(s => (
              <li key={s.path} className="text-fg-ghost">
                <span>{s.path}</span>
                <span className={s.stated ? '' : ' text-amber-400'} data-fleet-install-skip-stated={s.stated ? 'yes' : 'no'}>
                  {' — '}{s.reason}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* The second click, and it is the only one that writes. The label carries
          the blast radius rather than a dialog: what it will do and where. */}
      {report.dry_run && onInstall && (
        <button
          onClick={onInstall}
          disabled={installing}
          data-fleet-install-for-real={module}
          className="text-xs text-amber-300 hover:text-amber-200 disabled:opacity-40 underline-offset-2 hover:underline"
        >
          {installing
            ? 'installing…'
            : `install for real — writes ${written.length} file(s) into ${root || report.project}`}
        </button>
      )}
    </div>
  )
}

export default function FleetInstall({ project, root, capabilities }: {
  project: string
  /** The project's directory — named on the button that writes into it. */
  root?: string
  capabilities?: CapabilityReport | null
}) {
  const [open, setOpen] = useState(false)
  const [attempts, setAttempts] = useState<Record<string, Attempt>>({})

  const run = useCallback(async (module: string, dryRun: boolean) => {
    // The previous report stays while the next run is in flight — see `Attempt`.
    setAttempts(a => ({ ...a, [module]: { running: true, report: a[module]?.report } }))
    const settle = (patch: Partial<Attempt>) =>
      setAttempts(a => ({ ...a, [module]: { running: false, report: a[module]?.report, ...patch } }))
    try {
      const res = await fetch(`/api/fleet/projects/${encodeURIComponent(project)}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module, dry_run: dryRun }),
      })
      const payload = await res.json().catch(() => null)
      if (!res.ok) {
        // The refusal is added, not substituted: a real install refused after a
        // preview leaves the reader needing both — what they authorised, and
        // why it did not happen.
        settle({ refusal: refusalOf(res.status, payload?.detail) })
        return
      }
      settle({ report: payload as InstallReport, refusal: undefined })
    } catch (e) {
      settle({ refusal: { kind: 'failed', note: String((e as Error)?.message ?? e) } })
    }
  }, [project])

  const standing = moduleStanding(capabilities)

  // Nothing to say and nothing to offer. Stated rather than silent when the
  // report itself is missing — an absent measurement is not a connected project.
  if (standing.kind === 'unmeasured') {
    return (
      /* `?`, not a zero and not a silence: an absent report is not a project
         with no modules. The dashed ring is this screen's mark for unmeasured
         everywhere else, so it is the mark here too. */
      <Chip
        jump="modules-unmeasured"
        data={{ 'data-fleet-modules': 'unmeasured' }}
        tone="text-amber-400"
        mark={<CircleDashed size={13} strokeWidth={1.75} aria-hidden />}
        count="?"
        title={standing.note}
        label="modules not measured"
      />
    )
  }
  const caps = capabilities?.capabilities ?? []
  if (standing.total === 0) return null

  const summary = [
    standing.notConnected > 0 ? `${standing.notConnected} not connected` : null,
    standing.partial > 0 ? `${standing.partial} partial` : null,
    standing.unknown > 0 ? `${standing.unknown} unknown` : null,
  ].filter(Boolean).join(' · ')
  // The number is what is WRONG when anything is, and the total only when
  // nothing is. A chip showing `4` beside an amber mark would read as four
  // problems; showing the total next to the faults would spend the one number
  // on the reassuring half.
  const wrong = standing.notConnected + standing.partial + standing.unknown

  return (
    <>
      <Chip
        jump="modules"
        onClick={() => setOpen(v => !v)}
        data={{ 'data-fleet-modules': 'measured', 'data-fleet-modules-open': open ? 'on' : 'off' }}
        tone={standing.notConnected > 0 || standing.unknown > 0 ? 'text-fg-muted' : 'text-fg-ghost'}
        mark={<Blocks size={13} strokeWidth={1.75} aria-hidden />}
        count={wrong > 0 ? wrong : standing.total}
        trailing={<span className="text-fg-ghost">{open ? '▾' : '▸'}</span>}
        title={`set-core modules here: ${summary || `all ${standing.total} connected`}. Click to install one that is missing.`}
        label={summary || `${standing.total} modules connected`}
      />
      {open && (
        <div className="basis-full mt-1.5 space-y-1.5" data-fleet-install-panel={project}>
          {caps.map(cap => (
            <CapabilityRow
              key={cap.name}
              cap={cap}
              root={root}
              attempt={attempts[cap.name]}
              onPreview={() => void run(cap.name, true)}
              onInstall={() => void run(cap.name, false)}
            />
          ))}
        </div>
      )}
    </>
  )
}

function CapabilityRow({ cap, root, attempt, onPreview, onInstall }: {
  cap: Capability
  root?: string
  attempt?: Attempt
  onPreview: () => void
  onInstall: () => void
}) {
  const note = noOfferNote(cap)
  const running = attempt?.running === true
  return (
    <div className="text-xs" data-fleet-capability={cap.name} data-fleet-capability-state={cap.state}>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-fg-normal">{cap.name}</span>
        <span className={STATE_STYLE[cap.state] ?? 'text-fg-muted'}>{String(cap.state).replace('-', ' ')}</span>
        {typeof cap.present === 'number' && typeof cap.total === 'number' && (
          <span className="text-fg-ghost tabular-nums">{cap.present}/{cap.total} file(s)</span>
        )}
        {installOffered(cap) && !attempt?.report && (
          <button
            onClick={onPreview}
            disabled={running}
            data-fleet-install-preview={cap.name}
            className="text-sky-300 hover:text-sky-200 disabled:opacity-40 underline-offset-2 hover:underline"
          >
            {running ? 'looking…' : 'preview the install'}
          </button>
        )}
      </div>

      {note && <div className="text-fg-ghost mt-0.5" data-fleet-capability-note={cap.name}>{note}</div>}

      {attempt?.refusal && (
        <div
          className={attempt.refusal.kind === 'failed' ? 'mt-1 text-amber-400' : 'mt-1 text-red-400'}
          data-fleet-install-refusal={attempt.refusal.kind}
        >
          {attempt.refusal.kind === 'not-listed' && 'this screen never listed that project: '}
          {attempt.refusal.kind === 'refused' && 'refused: '}
          {attempt.refusal.kind === 'failed' && 'the attempt failed: '}
          {attempt.refusal.note}
        </div>
      )}

      {attempt?.report && (
        <ReportBlock
          report={attempt.report}
          module={cap.name}
          root={root}
          onInstall={onInstall}
          installing={running}
        />
      )}
    </div>
  )
}
