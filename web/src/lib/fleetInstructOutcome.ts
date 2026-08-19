/**
 * What became of one instruction, as the surface must state it — task 7.7.
 *
 * The producer's rule, carried through unchanged: **an HTTP 200 is not a
 * delivery.** Three fields say three different things and no two of them may be
 * collapsed — `accepted` (the send happened and was answered), `outcome` (what
 * the channel said became of it) and `delivered_to_agent` (the agent has it).
 * A surface that renders "sent ✓" off the status code is stating an event that
 * did not happen, in the one place that looks like success.
 *
 * Two outcomes are traps, and each is a defect class this repository names:
 *
 *  - **`held` is not a resting state.** It has a clock and expires on its own,
 *    so a tile that draws it once and stops is showing "held" for a message
 *    that may already be dead. `settled` is false for it, and this module
 *    forces the caller to say the age — see {@link holdNote}.
 *  - **`unknown` is never upgraded to a delivery.** The channel gave no usable
 *    answer; that is not a quiet yes.
 */

import type { InstructReport } from './fleetTypes'

export type Tone = 'delivered' | 'undelivered' | 'pending' | 'failed' | 'unknown'

export interface OutcomeMeaning {
  /** One short label, in the reader's terms rather than the channel's. */
  label: string
  /** What it actually means for the message. Shown next to the label. */
  note: string
  tone: Tone
}

/**
 * The meaning of each outcome.
 *
 * Written from the producer's own definitions rather than guessed, because two
 * of them are counter-intuitive in the direction that matters: `at-turn-end` IS
 * a delivery (the agent's stop-hook will not let the turn close over unread
 * addressed mail), and `wakes-nobody` is not a failure of the send — the entry
 * exists and claims nobody's attention.
 */
export const OUTCOMES: Record<string, OutcomeMeaning> = {
  'arrives-now': {
    label: 'arrives now',
    note: 'a waiter under that session can start a turn with it',
    tone: 'delivered',
  },
  'at-turn-end': {
    label: 'arrives at the turn’s end',
    note: 'the session is working; its stop-hook will not let the turn close over unread mail',
    tone: 'delivered',
  },
  'sits-unread': {
    label: 'sits unread',
    note: 'nothing will start a turn there until a person types into that session',
    tone: 'undelivered',
  },
  'wakes-nobody': {
    label: 'wakes nobody',
    note: 'the channel says the entry claims nobody’s attention',
    tone: 'undelivered',
  },
  held: {
    label: 'held',
    note: 'not delivered: a person at the far end must approve it, and the hold expires on its own',
    tone: 'pending',
  },
  expired: {
    label: 'the hold expired',
    note: 'nobody approved it in time — it was never delivered',
    tone: 'failed',
  },
  unknown: {
    label: 'no usable answer',
    note: 'the channel did not say what became of it — this is not a quiet yes',
    tone: 'unknown',
  },
  refused: {
    label: 'refused',
    note: 'the send did not happen',
    tone: 'failed',
  },
  'not-instructable': {
    label: 'no address',
    note: 'this agent has no identity on the bus, so there was nothing to send to',
    tone: 'failed',
  },
}

/** An outcome this build does not know is shown AS ITSELF, never as a success. */
export function meaningOf(outcome: string): OutcomeMeaning {
  return OUTCOMES[outcome] ?? {
    label: outcome,
    note: 'an outcome this screen does not recognise — shown as the channel named it',
    tone: 'unknown',
  }
}

/**
 * Whether the report is finished.
 *
 * Read from the producer's own `settled` when it is there, and computed the
 * same way when it is not — `held` is the only non-terminal outcome, and the
 * fallback must not resolve it to "done" on an older server.
 */
export function isSettled(report: Pick<InstructReport, 'outcome' | 'settled'>): boolean {
  if (typeof report.settled === 'boolean') return report.settled
  return report.outcome !== 'held'
}

/**
 * What a still-open hold must say, given how long ago it was reported.
 *
 * There is no endpoint that re-asks what became of a hold, so the honest
 * statement is not "held" — it is "held as of N ago, and not re-checked since".
 * The distinction is the whole point of the outcome being non-terminal: the
 * first sentence is a claim about now that nobody verified, the second is a
 * claim about a moment that is true forever.
 */
export function holdNote(ageSeconds: number): string {
  const age = ageSeconds < 90
    ? `${Math.max(0, Math.round(ageSeconds))}s`
    : `${Math.round(ageSeconds / 60)}m`
  return `held as of ${age} ago — expires on its own, and nothing has re-checked it since`
}

/**
 * Whether to offer the missing-waiter remedy — task 7.7's own instruction.
 *
 * `waiters_here: 0` is the place the offer belongs: the message will sit unread
 * because nothing under that session can start a turn. Offered only when the
 * count was actually reported — an absent count is not a zero, and offering an
 * install off a missing field would propose a fix for a problem nobody measured.
 *
 * ## And only when a message EXISTS to sit unread
 *
 * Reported 2026-08-19 with a screenshot: a send the channel refused — the seat
 * was in a room the sender had not joined — rendered this remedy underneath the
 * refusal, saying *"every instruction sent here sits unread"*. Nothing had been
 * sent. The waiter count is a true measurement of a condition the send never
 * reached, and the sentence built on it is a present-tense claim about messages
 * that do not exist.
 *
 * It also displaced the remedy that WAS true: the channel's own notice named
 * the room to join, and the reader's eye had two remedies to choose between,
 * one of which could not work.
 *
 * This is the same class as a count taken from a declaration instead of from
 * the data — the number is right and the thing it is offered as evidence FOR
 * was never in play. `accepted === false` means no message left, so there is
 * nothing for a waiter to have failed to pick up.
 */
export function offerWaiterRemedy(
  report: Pick<InstructReport, 'waiters_here' | 'waiters' | 'accepted'>,
): boolean {
  // A refused send has nothing waiting. `false` only — an ABSENT `accepted` is
  // not a refusal, and suppressing the remedy on a missing field would hide a
  // real one on an older server.
  if (report.accepted === false) return false
  const n = typeof report.waiters_here === 'number' ? report.waiters_here : report.waiters
  return n === 0
}
