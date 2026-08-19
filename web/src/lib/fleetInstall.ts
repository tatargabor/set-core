/**
 * Installing a module into a project — task 7.15, the decisions.
 *
 * This is the only act on this screen that **writes into a repository the
 * framework does not own**, and the route was built with that in mind: a
 * `dry_run` that defaults to true, a report that names every file it did NOT
 * touch, and a refusal that comes back as a status code rather than a warning.
 * Everything here exists so the SURFACE cannot quietly undo any of that.
 *
 * Four rules, each stated as a function so it can be asserted in both
 * directions:
 *
 *  - **`changed_nothing` is read, never derived.** `written.length === 0` is a
 *    second copy of the producer's rule, and it is the copy that reads as
 *    success. A report that does not carry the field is *unstated* — not false.
 *  - **A skip without a reason is a finding, not a blank.** The installer's
 *    contract is that nothing is silent; a surface that drops an unexplained
 *    skip re-creates that silence one layer up.
 *  - **A refusal is a refusal.** 409 means the state is wrong — a missing
 *    requirement, a module that does not ship, a directory that cannot be read.
 *    Drawn as an amber warning it becomes something to click past, and what it
 *    leads to is a half-installed project nobody chose.
 *  - **The preview comes first and is not the install.** A report from a dry run
 *    describes what WOULD happen; presenting it as what did happen is the false
 *    value this whole screen is built against.
 */

/** Every state the capability report can carry for one module. */
export type CapabilityState = 'connected' | 'partial' | 'not-connected' | 'unknown'

export interface Capability {
  name: string
  state: CapabilityState | string
  present?: number
  total?: number
  ledgered?: number
  inferred?: number
  reason?: string | null
}

export interface CapabilityReport {
  capabilities?: Capability[]
  ledger_present?: boolean
  unreadable?: string | null
  connected?: number
  partial?: number
  not_connected?: number
  unknown?: number
  declared?: boolean
}

export interface Skip {
  path: string
  reason?: string | null
}

export interface InstallReport {
  module: string
  project: string
  dry_run: boolean
  written?: string[]
  skipped?: Skip[]
  changed_nothing?: boolean
  lines?: string[]
}

/**
 * Whether an install may be OFFERED for this capability.
 *
 * Only where the report says *not connected*, which is the task's own wording
 * and the narrow reading on purpose: `partial` means the project already holds
 * some of these files without an install record, and the report's own `reason`
 * says the framework cannot tell a project edit from its own drift there. An
 * offer on top of that would be asking the reader to authorise a write whose
 * blast radius nobody has measured — so the state is shown and the offer is
 * not, with the reason where the reader is standing.
 */
export function installOffered(cap: Capability): boolean {
  return cap.state === 'not-connected'
}

/** Why no offer is made, for the states where the absence needs a sentence. */
export function noOfferNote(cap: Capability): string | null {
  if (cap.state === 'connected') return null
  if (cap.state === 'partial') {
    return cap.reason || 'some of it is already here without an install record'
  }
  if (cap.state === 'unknown') return 'this module could not be measured, so nothing is offered for it'
  return null
}

export type ChangeStanding =
  /** The producer said it wrote nothing. Its own field, not a derived emptiness. */
  | { kind: 'nothing' }
  /** The producer said it wrote these. */
  | { kind: 'wrote'; count: number }
  /**
   * The producer did not say. NOT the same as nothing — and deliberately not
   * computed from an empty `written`, which is the expression that reads as
   * success exactly when the answer is unknown.
   */
  | { kind: 'unstated' }

export function changeStanding(report: InstallReport): ChangeStanding {
  if (report.changed_nothing === true) return { kind: 'nothing' }
  if (report.changed_nothing === false) {
    return { kind: 'wrote', count: Array.isArray(report.written) ? report.written.length : 0 }
  }
  return { kind: 'unstated' }
}

/**
 * The skips, each guaranteed to carry a sentence.
 *
 * A skip whose reason the producer omitted is rendered as *no reason given*
 * rather than as a bare path: an unexplained skip is the exact silence the
 * installer's contract forbids, and hiding it here would put that silence back.
 */
export function skipsWithReasons(report: InstallReport): { path: string; reason: string; stated: boolean }[] {
  const skipped = Array.isArray(report.skipped) ? report.skipped : []
  return skipped.map(s => {
    const reason = typeof s.reason === 'string' ? s.reason.trim() : ''
    return { path: s.path, reason: reason || 'no reason given', stated: reason.length > 0 }
  })
}

export type Refusal =
  | { kind: 'not-listed'; note: string }
  | { kind: 'refused'; note: string }
  | { kind: 'failed'; note: string }

/**
 * What a non-2xx answer means, kept apart from what it looks like.
 *
 * 404 and 409 are both refusals and neither is a warning: the first says this
 * screen never listed the project, the second says the state is wrong — a
 * missing requirement, a module that does not ship here, a directory that
 * cannot be read. Anything else is a failure of the attempt rather than a
 * verdict on it, and saying so is what stops a reader from "fixing" a project
 * because a server fell over.
 */
export function refusalOf(status: number, detail: unknown): Refusal {
  const note = typeof detail === 'string' && detail.trim()
    ? detail.trim()
    : `the server answered ${status} and said nothing more`
  if (status === 404) return { kind: 'not-listed', note }
  if (status === 409) return { kind: 'refused', note }
  return { kind: 'failed', note }
}

/**
 * What the report is a report OF.
 *
 * A dry run describes what WOULD happen. Rendering it in the past tense is the
 * false value this screen exists against — and it is the easy mistake, because
 * the two payloads are byte-identical apart from one boolean.
 */
export function reportTense(report: InstallReport): { verb: string; note: string } {
  return report.dry_run
    ? {
        verb: 'would write',
        note: 'a preview — nothing has been written yet',
      }
    : {
        verb: 'wrote',
        note: 'this ran for real and wrote into the project',
      }
}

/** A one-line summary of the report, in the tense the report is actually in. */
export function reportHeadline(report: InstallReport): string {
  const change = changeStanding(report)
  const skips = skipsWithReasons(report).length
  const { verb } = reportTense(report)
  const tail = skips > 0 ? `, ${skips} left alone` : ''
  if (change.kind === 'nothing') {
    return `${verb} no files${tail}`
  }
  if (change.kind === 'unstated') {
    return `the report does not say whether anything was written${tail}`
  }
  return `${verb} ${change.count} file(s)${tail}`
}

/**
 * What the project header says about its modules, if anything.
 *
 * Counted from the capability LIST rather than from the report's own totals: a
 * count and its own breakdown disagreeing is the shape that turns a wrong zero
 * into a proof, and the list is the thing the panel goes on to render.
 */
export type ModuleStanding =
  | { kind: 'unmeasured'; note: string }
  | { kind: 'measured'; total: number; notConnected: number; partial: number; unknown: number }

export function moduleStanding(report: CapabilityReport | null | undefined): ModuleStanding {
  if (!report) return { kind: 'unmeasured', note: 'this server did not report what modules the project has' }
  if (report.unreadable) return { kind: 'unmeasured', note: report.unreadable }
  const caps = Array.isArray(report.capabilities) ? report.capabilities : null
  if (!caps) return { kind: 'unmeasured', note: 'the capability report carried no module list' }
  return {
    kind: 'measured',
    total: caps.length,
    notConnected: caps.filter(c => c.state === 'not-connected').length,
    partial: caps.filter(c => c.state === 'partial').length,
    unknown: caps.filter(c => c.state === 'unknown').length,
  }
}
