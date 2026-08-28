/**
 * When an input wait turns amber and when it turns red — one answer per screen.
 *
 * The thresholds arrive in the fleet envelope (`input_wait_thresholds`) because
 * the server declares them; they reach the components through a context because
 * they are needed in two unrelated subtrees — the project column's counters and
 * each agent tile's state line — and a value threaded by hand through one of
 * those and not the other is a screen where the row and the tile disagree about
 * when a wait became urgent.
 *
 * The default is `null`, which makes `inputWaitTone` fall back to the constants
 * compiled into the client. Those are the same two numbers, and a unit test
 * asserts they match the Python source. So a server too old to send the table
 * still colours — and colours identically.
 */
import { createContext, useContext } from 'react'

import type { InputWaitThresholds } from './fleetAttention'

export const WaitThresholdsContext = createContext<InputWaitThresholds | null>(null)

export function useWaitThresholds(): InputWaitThresholds | null {
  return useContext(WaitThresholdsContext)
}
