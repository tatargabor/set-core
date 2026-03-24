/** Shared style constants for issue management UI. */

import type { IssueState } from '../../lib/api'

export const STATE_STYLES: Record<IssueState, { color: string; bg: string; icon: string; label: string }> = {
  new:                { color: 'text-blue-400',    bg: 'bg-blue-400/10',    icon: '●',  label: 'New' },
  investigating:      { color: 'text-yellow-400',  bg: 'bg-yellow-400/10',  icon: '🔍', label: 'Investigating' },
  diagnosed:          { color: 'text-orange-400',  bg: 'bg-orange-400/10',  icon: '◆',  label: 'Diagnosed' },
  awaiting_approval:  { color: 'text-amber-400',   bg: 'bg-amber-400/10',   icon: '⏱',  label: 'Awaiting' },
  fixing:             { color: 'text-purple-400',  bg: 'bg-purple-400/10',  icon: '🔧', label: 'Fixing' },
  verifying:          { color: 'text-indigo-400',  bg: 'bg-indigo-400/10',  icon: '✓',  label: 'Verifying' },
  deploying:          { color: 'text-cyan-400',    bg: 'bg-cyan-400/10',    icon: '🚀', label: 'Deploying' },
  resolved:           { color: 'text-green-400',   bg: 'bg-green-400/10',   icon: '✓',  label: 'Resolved' },
  dismissed:          { color: 'text-neutral-500', bg: 'bg-neutral-500/10', icon: '✕',  label: 'Dismissed' },
  muted:              { color: 'text-neutral-600', bg: 'bg-neutral-600/10', icon: '🔇', label: 'Muted' },
  failed:             { color: 'text-red-400',     bg: 'bg-red-400/10',     icon: '✗',  label: 'Failed' },
  skipped:            { color: 'text-neutral-400', bg: 'bg-neutral-400/10', icon: '→',  label: 'Skipped' },
  cancelled:          { color: 'text-neutral-500', bg: 'bg-neutral-500/10', icon: '⊘',  label: 'Cancelled' },
}

export const SEVERITY_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  unknown:  { color: 'text-neutral-400', bg: 'bg-neutral-400/10', label: '?' },
  low:      { color: 'text-blue-300',    bg: 'bg-blue-300/10',    label: 'Low' },
  medium:   { color: 'text-yellow-400',  bg: 'bg-yellow-400/10',  label: 'Med' },
  high:     { color: 'text-orange-400',  bg: 'bg-orange-400/10',  label: 'High' },
  critical: { color: 'text-red-400',     bg: 'bg-red-400/10',     label: 'Crit' },
}

export const MODE_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  e2e:         { color: 'text-blue-400',    bg: 'bg-blue-500/10',    label: 'E2E' },
  production:  { color: 'text-red-400',     bg: 'bg-red-500/10',     label: 'PROD' },
  development: { color: 'text-neutral-400', bg: 'bg-neutral-500/10', label: 'DEV' },
}

// Urgency grouping
export const ATTENTION_STATES: IssueState[] = ['new', 'diagnosed', 'awaiting_approval']
export const IN_PROGRESS_STATES: IssueState[] = ['investigating', 'fixing', 'verifying', 'deploying']
export const DONE_STATES: IssueState[] = ['resolved', 'dismissed', 'muted', 'skipped', 'cancelled', 'failed']

// State-aware button map
export const STATE_BUTTONS: Record<IssueState, string[]> = {
  new:               ['investigate', 'dismiss', 'mute', 'skip'],
  investigating:     ['cancel', 'dismiss'],
  diagnosed:         ['fix', 'investigate_more', 'dismiss', 'mute', 'skip'],
  awaiting_approval: ['fix', 'extend', 'cancel', 'dismiss'],
  fixing:            ['cancel'],
  verifying:         ['cancel'],
  deploying:         [],
  resolved:          [],
  dismissed:         ['reopen'],
  muted:             ['reopen'],
  failed:            ['retry', 'investigate_more', 'dismiss'],
  skipped:           ['reopen'],
  cancelled:         ['reopen', 'dismiss'],
}
