/**
 * Dictation into the agent's own input — task 7.6.
 *
 * The requirement is that speaking and typing end in the SAME place, so the
 * things worth asserting are the ones where a second path could open up
 * without anybody deciding to:
 *
 *  - the transcript lands in the box the send button reads, and *appends* to
 *    what is already there rather than replacing it;
 *  - **nothing is sent.** A transcript that dispatched itself would put words
 *    nobody read in front of a live agent, and the send is the irreversible
 *    half of this screen;
 *  - **a partial is not what you have.** In-progress text stays outside the
 *    box, so a sentence cut off by a dropped connection cannot be sent as if it
 *    had been finished;
 *  - and when there is no key and no microphone, the control is ABSENT rather
 *    than present-and-failing — asserted against the real component, because
 *    that behaviour is its own and a stub would be measuring the stub.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const voice = vi.hoisted(() => ({ available: { checked: true, hasKey: true, apiKey: 'k', micSupported: true } }))

vi.mock('../../src/hooks/useSonioxAvailable', () => ({
  useSonioxAvailable: () => voice.available,
}))

/**
 * The mic is stubbed for the WIRING tests: the real one opens a WebSocket to a
 * transcription service and asks for a microphone, neither of which a jsdom
 * unit test can have. What is measured here is this component's side of the
 * contract — what it does with a transcript and with a partial.
 */
vi.mock('../../src/components/VoiceInput', () => ({
  default: ({ onTranscript, onPartial, disabled }: {
    onTranscript: (t: string) => void
    onPartial: (t: string) => void
    disabled?: boolean
  }) => (
    <div data-stub-voice={disabled ? 'disabled' : 'ready'}>
      <button data-stub-transcript onClick={() => onTranscript('restart the failing gate')}>final</button>
      <button data-stub-partial onClick={() => onPartial('restart the fail')}>partial</button>
    </div>
  ),
}))

import FleetInstruct from '../../src/components/FleetInstruct'
import type { FleetAgent } from '../../src/lib/fleetTypes'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

const agent = (extra: Partial<FleetAgent> = {}): FleetAgent => ({
  pid: 4242, name: 'a', project: 'demo', branch: 'main', session_id: 's', binding_confirmed: true,
  sources: ['process'], kind: 'interactive', state: 'quiet', tool: null, tool_elapsed_seconds: null,
  other_tools: [], last_movement_seconds: 5, unknown_reason: null, waiting_for: null,
  declaration_ignored: null, population: 'started-here', terminal_label: 't',
  instructable: true, seat: 'demo#a1', ...extra,
} as FleetAgent)

const box = () => document.querySelector('[data-fleet-instruct-input="4242"]') as HTMLTextAreaElement

describe('speaking and typing end in the same place', () => {
  it('puts the transcript in the box the send button reads', () => {
    render(<FleetInstruct agent={agent()} />)
    fireEvent.click(screen.getByText('final'))
    expect(box().value).toBe('restart the failing gate')
    expect((document.querySelector('[data-fleet-instruct-send="4242"]') as HTMLButtonElement).disabled).toBe(false)
  })

  /** Speaking after typing continues the sentence; it does not overwrite it. */
  it('appends rather than replacing what was typed', () => {
    render(<FleetInstruct agent={agent()} />)
    fireEvent.change(box(), { target: { value: 'when the build is green,' } })
    fireEvent.click(screen.getByText('final'))
    expect(box().value).toBe('when the build is green, restart the failing gate')
  })

  /**
   * The load-bearing one. Dictation fills the box; a person sends. Anything
   * else puts words nobody read in front of a running agent.
   */
  it('sends nothing by itself', async () => {
    const post = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response))
    vi.stubGlobal('fetch', post)
    render(<FleetInstruct agent={agent()} />)
    fireEvent.click(screen.getByText('final'))
    fireEvent.click(screen.getByText('partial'))
    await Promise.resolve()
    expect(post).not.toHaveBeenCalled()
  })

  /**
   * A partial that sat in the box would look exactly like something typed and
   * meant — and a connection dropping mid-sentence is how it gets there.
   */
  it('keeps an in-progress partial OUT of the box', () => {
    render(<FleetInstruct agent={agent()} />)
    fireEvent.click(screen.getByText('partial'))
    expect(box().value).toBe('')
    const preview = document.querySelector('[data-fleet-instruct-heard="4242"]')
    expect(preview?.textContent).toContain('restart the fail')
  })

  it('replaces the preview with the finalised words, not with both', () => {
    render(<FleetInstruct agent={agent()} />)
    fireEvent.click(screen.getByText('partial'))
    fireEvent.click(screen.getByText('final'))
    expect(box().value).toBe('restart the failing gate')
    expect(document.querySelector('[data-fleet-instruct-heard="4242"]')).toBeNull()
  })

  /**
   * The component that owns the microphone announces a transcript but never
   * announces that it stopped hearing anything. A recording ended with no
   * finalised words leaves the last partial standing, and *"hearing: …"* about
   * a microphone that is off is a false presence.
   */
  it('drops a preview that stopped being fed', () => {
    vi.useFakeTimers()
    render(<FleetInstruct agent={agent()} />)
    fireEvent.click(screen.getByText('partial'))
    expect(document.querySelector('[data-fleet-instruct-heard="4242"]')).toBeTruthy()
    act(() => { vi.advanceTimersByTime(4000) })
    expect(document.querySelector('[data-fleet-instruct-heard="4242"]')).toBeNull()
  })

  it('offers no dictation where there is no input at all', () => {
    render(<FleetInstruct agent={agent({ instructable: false, reason: 'this session has no seat' })} />)
    expect(document.querySelector('[data-stub-voice]')).toBeNull()
    expect(screen.getByText(/no seat/)).toBeTruthy()
  })
})

describe('unconfigured is absent, not broken', () => {
  /**
   * Asserted against the REAL component: "absent rather than failing" is its
   * own behaviour, and repeating the condition here would be a second copy —
   * the one that drifts. `importActual` walks past the stub above.
   */
  it('renders no control at all without a key or a microphone', async () => {
    const { default: RealVoice } =
      await vi.importActual<typeof import('../../src/components/VoiceInput')>('../../src/components/VoiceInput')

    voice.available = { checked: true, hasKey: false, apiKey: null, micSupported: true }
    const noKey = render(<RealVoice onTranscript={() => {}} onPartial={() => {}} />)
    expect(noKey.container.innerHTML).toBe('')
    cleanup()

    voice.available = { checked: true, hasKey: true, apiKey: 'k', micSupported: false }
    const noMic = render(<RealVoice onTranscript={() => {}} onPartial={() => {}} />)
    expect(noMic.container.innerHTML).toBe('')
    cleanup()

    // And it is really the availability that decides — the same component
    // renders a control when both are there, so the two empties above are an
    // answer rather than a component that never renders anything.
    voice.available = { checked: true, hasKey: true, apiKey: 'k', micSupported: true }
    const ok = render(<RealVoice onTranscript={() => {}} onPartial={() => {}} />)
    await waitFor(() => expect(ok.container.querySelector('button')).toBeTruthy())
  })
})
