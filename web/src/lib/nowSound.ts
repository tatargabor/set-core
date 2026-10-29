/**
 * The Now card's cue tones (fleet-now-card 4.7, design D7).
 *
 * Synthesised with Web Audio rather than shipped as files, and VARIED between
 * cues — pitch and contour change with the variant the server picks — because a
 * repeated identical alert habituates within a few exposures (design.md, evidence).
 * Short and soft: a cue says "look when you can", not "stop now".
 */

/** Note sequences (Hz). Rising, falling and arched contours, in different registers. */
export const CUE_SHAPES: number[][] = [
  [659, 880],
  [880, 659],
  [523, 659, 784],
  [784, 587],
  [587, 880, 740],
  [698, 523],
]

export function cueShape(variant: number | null | undefined): number[] {
  const n = CUE_SHAPES.length
  const i = (((variant ?? 0) % n) + n) % n
  return CUE_SHAPES[i]
}

type AudioCtor = typeof AudioContext

function audioCtor(): AudioCtor | null {
  const w = globalThis as unknown as { AudioContext?: AudioCtor; webkitAudioContext?: AudioCtor }
  return w.AudioContext ?? w.webkitAudioContext ?? null
}

/** A context created inside a user gesture — browsers refuse to start audio otherwise. */
export function createAudio(): AudioContext | null {
  const Ctor = audioCtor()
  if (!Ctor) return null
  try {
    const ctx = new Ctor()
    void ctx.resume?.()
    return ctx
  } catch {
    return null
  }
}

/** Play one cue. Each note ~140 ms with a soft attack and release. */
export function playCue(ctx: AudioContext, variant: number | null | undefined): void {
  const notes = cueShape(variant)
  const start = ctx.currentTime + 0.02
  notes.forEach((freq, i) => {
    const t = start + i * 0.16
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, t)
    gain.gain.setValueAtTime(0.0001, t)
    gain.gain.exponentialRampToValueAtTime(0.18, t + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.14)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start(t)
    osc.stop(t + 0.16)
  })
}
