import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, ChevronRight, CircleStop, Copy, Eye, Maximize2, Minimize2, MousePointerClick, Scissors, X } from 'lucide-react'
import { fileReference, type FileRef } from '../lib/fleetFiles'
import {
  type AttachedEvent,
  type CopyOutcome,
  copySelection,
  isAmbiguousCopyKey,
  type PasteOutcome,
  pastedImage,
  uploadPastedImage,
  isCopyRequest,
  isPasteRequest,
  mouseIsTakenByAgent,
  parseControl,
  terminalLinkTarget,
  terminalUrl,
} from '../lib/fleetTerminal'
import { IconButton } from './TileControls'

/**
 * One framework-owned terminal, in the browser — task 8.1.
 *
 * ## The wire, and why the split is not an implementation detail
 *
 * Terminal bytes travel as BINARY frames in both directions; control travels as
 * JSON text. A pty read can end in the middle of a UTF-8 sequence — that is
 * ordinary, not an edge case — so decoding at this boundary would corrupt output
 * silently and in the direction that still looks like data. The bytes therefore
 * go to the emulator **as bytes**: `term.write(Uint8Array)`, never
 * `term.write(new TextDecoder().decode(...))`. Keystrokes go back the same way,
 * encoded once and sent as binary.
 *
 * ## Closing this view does not stop the agent
 *
 * Requirement 5.4, and it is the reason there are two controls here rather than
 * one. `bezárás` detaches the socket; the owner keeps holding the pty and the
 * agent keeps working. Stopping is a separate, explicit act — `POST
 * /api/fleet/agents/{label}/stop` — and it says what it does before it does it.
 * A single ✕ that did both would make every reader who wanted to stop watching
 * kill the thing they were watching.
 *
 * ## Reattach is the ordinary case, not recovery
 *
 * The server sends the buffered screen first, so a reload, a second viewer and a
 * first attach are the same code path — the first frame is the screen as it
 * already is. `replayed_bytes` says how much came back, and `replay_truncated`
 * says the buffer was longer than what was kept. Both are rendered: a replay
 * that silently lost its head would otherwise read as a session that started
 * there.
 *
 * ## Why xterm is loaded dynamically
 *
 * `import()` inside the effect rather than at module scope. Two reasons, both
 * measured rather than stylistic: the emulator is ~300 KB that no reader who
 * never opens a terminal should download, and a static import would drag a
 * canvas/DOM-heavy module into every jsdom unit test that renders an agent tile.
 */

/**
 * The narrowest terminal worth handing to a program — see `refit` below.
 *
 * 80 because that is the width terminal programs assume when they assume one;
 * anything narrower is not a smaller terminal, it is a broken one.
 */
const MIN_COLS = 80

/**
 * How long to wait for a replay that never finishes arriving — B-16.
 *
 * The replay is normally one burst and this timer never fires. It exists for
 * the case where the byte count and what arrives disagree: without it the
 * viewer would keep the pty at the geometry it was found in and never send its
 * own, so a resize would silently stop working. One second is far longer than a
 * local burst and far shorter than a person noticing.
 */
const REPLAY_GRACE_MS = 1000

interface Props {
  label: string
  /** Called when the reader closes the view. Detach only — never a stop. */
  onClose: () => void
  /**
   * Whether this terminal's agent is alone on the panel. Only changes the
   * height — the socket, the replay and the pty are identical either way.
   */
  full?: boolean
  /** Ask the panel to show this agent alone, or to go back to the grid. */
  onToggleFull?: () => void
  /**
   * Called on every keystroke the reader sends into this terminal.
   *
   * Distinct from `onFocusChange`, and the distinction is the whole point:
   * focus says the cursor is here, which can be true for fifteen minutes while
   * nothing happens. PM mode's freeze has to know whether the reader is
   * ACTING, because a screen somebody is parked on with nothing typed is
   * exactly the one a fresher blockage may take.
   *
   * Fires for pasted and program-generated input too. That is correct rather
   * than sloppy — all of it is the reader putting something into this session.
   */
  onInput?: () => void
  /**
   * Called when the keyboard enters or leaves this terminal.
   *
   * Asked for on 2026-08-19: *"az aktuális csempe, amin gépelek, lehetne
   * aktívan jelezve"* — and with several terminals open at once (which is now
   * possible) it stops being decoration: a keystroke goes to exactly one agent,
   * and the reader has to be able to see which. It is taken from real DOM focus
   * on the emulator's own textarea, not from which pane was opened last — the
   * latter is a proxy, and it would say "here" while the keys went elsewhere.
   */
  onFocusChange?: (focused: boolean) => void
  /**
   * Where this terminal's status row should be DRAWN — asked for 2026-08-22:
   * *"egy sorba kerüljön a csempe ikonja és a layout ikon"*.
   *
   * The row itself did not change; only where it lands. It used to open a line
   * of its own directly under the tile's title bar — two icon rows, one above
   * the other, for one agent — which is what B-61 is about.
   *
   * A PORTAL rather than lifting the state up, and the reason is the defect it
   * avoids: phase, the attach acknowledgement and the copy outcome all live in
   * this component, and handing them to the tile would put a second copy of
   * every one of them in a place that can disagree with the socket. The portal
   * moves the DOM and leaves the ownership alone.
   *
   * `null` or absent — a docked panel, a test — and the row renders in place,
   * exactly as before. A surface that only works when someone remembers to pass
   * a slot is a surface that will one day be silently headerless.
   */
  headerSlot?: HTMLElement | null
  /**
   * The project this agent belongs to, and the files it actually has.
   *
   * Both are needed before a token in the output may be offered as a link, and
   * the second is the load-bearing one: without the known set, `12:30` and a
   * sentence containing a dotted word become links to files that do not exist,
   * and a control that fails when clicked is worse than an absent one. See
   * `fileReference`.
   *
   * Absent — a docked panel with no project context, a test — and no file link
   * is offered at all. Nothing degrades to guessing.
   */
  projectRoot?: string
  knownFiles?: ReadonlySet<string>
  /** Open a file the reader activated in this terminal. */
  onOpenFile?: (file: FileRef) => void
}

/** One link the emulator may draw and activate. xterm's `ILink`, structurally. */
interface TerminalLink {
  range: { start: { x: number; y: number }; end: { x: number; y: number } }
  text: string
  activate: (event: MouseEvent) => void
}

/**
 * The little of the emulator the link effect needs.
 *
 * Structural rather than xterm's own `Terminal`, so this module's public shape
 * does not drag a 300 KB type import into every file that mentions it — and so
 * a test can hand it a stub without constructing an emulator.
 */
interface TerminalLike {
  buffer: { active: { getLine(y: number): { translateToString(trim?: boolean): string } | undefined } }
  registerLinkProvider(provider: {
    provideLinks(lineNumber: number, callback: (links: TerminalLink[] | undefined) => void): void
  }): { dispose(): void }
}

type Phase =
  | { kind: 'connecting' }
  | { kind: 'attached'; ack: AttachedEvent }
  | { kind: 'refused'; reason: string }
  | { kind: 'closed'; reason: string }

export default function FleetTerminal({ label, onClose, full, onToggleFull, onFocusChange, onInput, headerSlot, projectRoot, knownFiles, onOpenFile }: Props) {
  const host = useRef<HTMLDivElement | null>(null)
  // Held in a ref because the effect below depends on `[label]` alone: the
  // handler is captured once, so a parent passing a fresh closure each render
  // would have its FIRST one called forever. That failure is silent — the
  // callback still fires, it just reports to a stale owner — which is exactly
  // the kind of thing a passing test suite does not notice.
  const onInputRef = useRef(onInput)
  onInputRef.current = onInput
  const [phase, setPhase] = useState<Phase>({ kind: 'connecting' })
  const [stopping, setStopping] = useState(false)
  const [stopError, setStopError] = useState<string | null>(null)
  const [stopConfirm, setStopConfirm] = useState(false)
  // The attachment details start CLOSED: they are the two facts nothing goes
  // wrong for lack of — the label is already in the tile's title, and the byte
  // count is a measurement of the replay, not of the agent.
  const [details, setDetails] = useState(false)
  /*
    THE TWO FACTS THE COPY PATH NEEDS ON SCREEN — B-60.

    `mouseTaken` is xterm's own `enable-mouse-events` state, read from its class
    rather than tracked here. While it is on, a plain drag goes to the AGENT and
    selects nothing, which is exactly what was reported as "copy does not work".
    The terminal therefore says so where the reader is standing, instead of
    leaving them to discover Shift.

    `copied` is the outcome of the last copy attempt. A clipboard write can be
    refused — an unfocused document, a browser policy — and a copy that silently
    did nothing is the false-absence shape: the reader pastes the PREVIOUS
    clipboard content somewhere and finds out much later.
  */
  const [mouseTaken, setMouseTaken] = useState(false)
  const [copied, setCopied] = useState<CopyOutcome>(null)
  /*
    `pasted` is deliberately silent on SUCCESS — the reader's decision, and the
    typed path is its own receipt. It speaks while an upload is in flight and
    when one fails, because those are the two states a reader cannot see from
    the terminal itself.
  */
  const [pasted, setPasted] = useState<PasteOutcome>(null)
  /**
   * The live emulator, for the ONE thing that must not wait for a re-attach.
   *
   * The socket effect depends on `label` alone, deliberately — re-running it
   * costs a teardown and a replay. But the file listing arrives AFTER the
   * terminal opens (it is fetched once per project, and the terminal is already
   * on screen), so a link provider registered inside that effect would be
   * registered with an empty set and never again: file links would silently
   * never appear. Measured 2026-08-22 while trying to click one.
   *
   * So the provider gets its own effect, and this ref is how it reaches the
   * emulator without owning it.
   */
  const termRef = useRef<TerminalLike | null>(null)
  /** The copy act itself, installed by the effect once the emulator exists. */
  const copyRef = useRef<(() => void) | null>(null)
  const pasteNoticeTimer = useRef<number | undefined>(undefined)
  /** The notice's own timer, so a second copy does not inherit the first's. */
  const copyNoticeTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let dispose: (() => void) | null = null

    void (async () => {
      const [{ Terminal }, { FitAddon }, { WebLinksAddon }] = await Promise.all([
        import('@xterm/xterm'),
        import('@xterm/addon-fit'),
        import('@xterm/addon-web-links'),
      ])
      await import('@xterm/xterm/css/xterm.css')
      if (disposed || !host.current) return

      const term = new Terminal({
        convertEol: false,
        cursorBlink: true,
        fontSize: 12,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        scrollback: 5000,
        theme: { background: '#0b0f14', foreground: '#d7dde4' },
      })
      const fit = new FitAddon()
      term.loadAddon(fit)

      /**
       * URLs in the output are openable — asked for on 2026-08-20: *"terminal
       * ablakban URL nyitható legyen uj lapon"*.
       *
       * An agent prints the address of what it built (a mock page, a preview, a
       * report) and the only way to reach it was to select the text by hand out
       * of a fixed grid — across a line wrap, in a pane that scrolls
       * horizontally. That is a link the terminal already renders and the reader
       * cannot follow.
       *
       * **A new tab, never this one.** The dashboard tab holds every open
       * terminal's socket; navigating it away tears down each attachment and
       * loses the panel arrangement the reader has built. So the handler is
       * explicit rather than left to the addon's default, and it is the two
       * things a target of `_blank` needs to be safe: `noopener` (the opened
       * page cannot reach back through `window.opener`) and `noreferrer`.
       *
       * **Only http(s), and the click is the person's.** The text is written by
       * whatever the agent ran, so it is data, not an instruction: nothing here
       * navigates on its own, and a scheme that could execute something —
       * `javascript:`, `data:`, `file:` — is not opened at all. That decision is
       * `terminalLinkTarget`, next to the rest of the terminal's rules and
       * testable without a browser.
       */
      term.loadAddon(new WebLinksAddon((event, uri) => {
        event.preventDefault()
        const target = terminalLinkTarget(uri)
        if (target) window.open(target, '_blank', 'noopener,noreferrer')
      }))
      term.open(host.current)
      termRef.current = term as unknown as TerminalLike

      /*
        COPY — B-60, reported 2026-08-22 as *"copy-pase mintha nem mene a
        terminal ablakokban most"*.

        Measured on a live agent: selection itself was never broken. What was
        missing is the route into it and out of it, and both halves have the same
        cause — the agent's TUI turns on mouse tracking, so the mouse belongs to
        the program and every keystroke belongs to the pty.

        `Ctrl+C` is deliberately NOT the copy key. In a terminal it is `SIGINT`,
        and these are long-running sessions where an accidental interrupt costs
        real work — so the key is the one Linux terminal emulators already use,
        and it is intercepted BEFORE the emulator, because xterm's own `copy`
        listener never fires: the core swallows the keystroke into the pty first.

        Returning `false` means the keystroke does not reach the agent at all,
        which is the point: a copy must not also be an input.
      */
      const announce = (outcome: CopyOutcome) => {
        if (outcome === null) return
        setCopied(outcome)
        window.clearTimeout(copyNoticeTimer.current)
        copyNoticeTimer.current = window.setTimeout(() => setCopied(null), 2500)
      }
      term.attachCustomKeyEventHandler(e => {
        /*
          Declining the keystroke is the ENTIRE paste fix — see `isPasteRequest`.
          xterm consults this handler before it cancels the event, so returning
          `false` leaves the browser's native paste running, and xterm's own
          listener on the helper textarea delivers the text. Doing nothing here
          is deliberate: anything else would be a second clipboard path.
        */
        if (isPasteRequest(e)) return false
        if (isCopyRequest(e)) {
          void copySelection(term.getSelection()).then(announce)
          return false
        }
        /*
          B-63: Ctrl+C is ambiguous, and the SELECTION resolves it — copy when there is
          one, interrupt when there is not. Chrome claims Ctrl+Shift+C for its own
          inspector, so the key B-60 chose never reaches this handler at all.

          `clearSelection()` is not tidying: it is what keeps the interrupt one keystroke
          away. Copy, selection gone, and the next Ctrl+C is a plain SIGINT again.
        */
        if (isAmbiguousCopyKey(e)) {
          const text = term.getSelection()
          if (!text) return true
          void copySelection(text).then(announce)
          term.clearSelection()
          return false
        }
        return true
      })
      copyRef.current = () => {
        const text = term.getSelection()
        if (!text) {
          setCopied({ ok: false, reason: 'nothing is selected — hold Shift and drag over the text first' })
          window.clearTimeout(copyNoticeTimer.current)
          copyNoticeTimer.current = window.setTimeout(() => setCopied(null), 2500)
          return
        }
        void copySelection(text).then(announce)
      }

      /*
        Whose mouse it is, read from the emulator rather than guessed. xterm sets
        this class exactly while an application mouse protocol is active, so the
        hint appears and disappears with the agent's own mode — a second copy of
        that state here would drift the moment the agent changed it.
      */
      const xtermEl = host.current.querySelector('.xterm')
      setMouseTaken(mouseIsTakenByAgent(xtermEl))
      const classWatch = new MutationObserver(() => setMouseTaken(mouseIsTakenByAgent(xtermEl)))
      if (xtermEl) classWatch.observe(xtermEl, { attributes: true, attributeFilter: ['class'] })

      /**
       * Fit to the box, but never below a usable width — B-13.
       *
       * `FitAddon` derives the column count from the container, and that number
       * goes on to the pty, so a narrow tile does not merely wrap the view: it
       * tells the AGENT to redraw its own terminal UI at that width. Measured at
       * ~30 columns the result is a third-width body with a one-character column
       * stranded at the right edge — *"hülyén tördel … nagyban jól működik"*.
       *
       * A terminal is a fixed-grid device: its content was laid out by the
       * program for a given number of columns, so re-flowing it destroys the
       * layout rather than adapting it. Hence a FLOOR and a window onto the
       * result — the host scrolls horizontally — instead of a cleverer wrap.
       * Above the floor nothing changes, which is why the large case already
       * worked.
       */
      const refit = () => {
        try { fit.fit() } catch { return /* zero-sized container; the observer refits */ }
        if (term.cols < MIN_COLS) term.resize(MIN_COLS, term.rows)
        /*
          B-29 — AND THEN CHECK THAT IT ACTUALLY FITS.

          `FitAddon` derives the row count from the host's OUTER box, so the 1 px
          border on each side is never subtracted. At heights that land just
          under a row multiple it therefore hands back one row MORE than fits,
          and `overflow-y: hidden` cuts the last one. Measured 2026-08-20: a
          224 px host has a 222 px client box, 16 rows x 14 px = 224, and the
          last row showed 12 of its 14 px.

          The row that gets cut is always the last one, which is where every
          terminal program draws its status line — so this is not "one row
          short", it is losing the row that says what the agent is waiting for,
          while everything above it still looks correct.

          The correction is measured against what was RENDERED, not recomputed
          from the box: the cell height is xterm's, and a second copy of that
          arithmetic here would be a second place to drift.
        */
        const el = host.current
        const screen = el?.querySelector('.xterm-screen') as HTMLElement | null
        if (!el || !screen || term.rows < 1) return
        const cell = screen.offsetHeight / term.rows
        if (!(cell > 0)) return
        const fits = Math.floor(el.clientHeight / cell)
        if (fits >= 1 && fits < term.rows) term.resize(term.cols, fits)
      }
      refit()

      const ws = new WebSocket(terminalUrl(label))
      ws.binaryType = 'arraybuffer'
      socket = ws
      const encoder = new TextEncoder()

      /** The pty's size, sent once the replay has landed and on every resize. */
      const sendSize = () => {
        if (ws.readyState !== WebSocket.OPEN) return
        ws.send(JSON.stringify({ resize: { rows: term.rows, cols: term.cols } }))
      }

      /*
        THE TWO GEOMETRIES, AND WHY THEY ARE SEQUENCED — B-16.

        The replay must render at the pty's shape; the tile must then get its
        own. Doing the second before the first has finished resizes the grid out
        from under the bytes, which is the bug this repairs, one layer down.

        `replayLeft` is counted down from `replayed_bytes` — an exact number the
        server sends BEFORE any byte — so the end of the replay is arithmetic,
        not a guess about timing. `settle` is idempotent and also fires on a
        timer, because a replay that arrives short (a dropped frame, a socket
        that ends mid-burst) must not leave the pty stuck at a size nobody is
        looking at. Failing towards "send our size late" is the safe direction;
        failing towards "never send it" is not.
      */
      let replayLeft = 0
      let settled = false
      let settleTimer: number | undefined
      const settle = () => {
        if (settled) return
        settled = true
        if (settleTimer !== undefined) { window.clearTimeout(settleTimer); settleTimer = undefined }
        refit()
        sendSize()
      }

      ws.onmessage = ev => {
        if (typeof ev.data === 'string') {
          const control = parseControl(ev.data)
          if (!control) return
          if (control.event === 'attached') {
            const ack = control as AttachedEvent
            setPhase({ kind: 'attached', ack })
            /*
              B-16 — RENDER THE REPLAY AT THE GEOMETRY IT WAS DRAWN AT.
              Reported 2026-08-19: *"terminal also status bar elromlik ha
              projektet valtok, beleirok, majd visszavaltok"*, and the half that
              names the cause: *"beiras utan megjavul"*. A keystroke changes
              nothing about the socket, the pty or the buffer — it makes the
              remote program REPAINT. So the screen was stale, not lost.

              This ack reaches the browser BEFORE any replay byte (the bridge
              sends it, then starts the output pump), which is what makes the
              repair possible here and nowhere else: adopt the pty's shape
              first, and the bytes that follow land on the grid they were
              composed for. Without it the viewer fitted to its own tile and
              rendered a screen laid out for some other width — silently,
              because the result still looks like a terminal.

              Then, and only then, our own size goes back. If it differs the
              program gets a SIGWINCH and repaints, which is the ordinary path;
              if it matches there is nothing to repaint and nothing is stale.
            */
            if (ack.rows && ack.cols) term.resize(ack.cols, ack.rows)
            // Our own size goes back only once the replay has landed — see
            // `settle` below. Sending it here would resize the grid out from
            // under the very bytes this is protecting.
            replayLeft = ack.replayed_bytes
            if (replayLeft <= 0) settle()
            else settleTimer = window.setTimeout(settle, REPLAY_GRACE_MS)
            term.focus()
            return
          }
          if (control.event === 'unavailable' || control.event === 'refused') {
            setPhase({ kind: 'refused', reason: String((control as { reason?: unknown }).reason ?? control.event) })
          }
          return
        }
        // Bytes, straight through. No decode: see the header of this file.
        const bytes = new Uint8Array(ev.data as ArrayBuffer)
        term.write(bytes)
        // The replay is counted DOWN, not detected. `replayed_bytes` is exact
        // and the server sends it before a single byte, so the end of the
        // replay is arithmetic rather than a guess about timing.
        if (replayLeft > 0) {
          replayLeft -= bytes.length
          if (replayLeft <= 0) settle()
        }
      }
      ws.onerror = () => {
        setPhase(p => (p.kind === 'attached' ? p : { kind: 'refused', reason: 'the connection was not established' }))
      }
      ws.onclose = () => {
        setPhase(p => (
          p.kind === 'refused'
            ? p
            : { kind: 'closed', reason: 'the connection closed — the agent may still be running' }
        ))
      }

      const typed = term.onData(data => {
        onInputRef.current?.()
        if (ws.readyState === WebSocket.OPEN) ws.send(encoder.encode(data))
      })

      const observer = new ResizeObserver(() => {
        refit()
        sendSize()
      })
      observer.observe(host.current)

      // Focus is READ from the DOM rather than tracked by hand. `focusin` /
      // `focusout` bubble (unlike focus/blur), so one pair on the host covers
      // the emulator's textarea whatever it does internally.
      const el = host.current
      const gained = () => onFocusChange?.(true)
      const lost = () => onFocusChange?.(false)
      el.addEventListener('focusin', gained)
      el.addEventListener('focusout', lost)

      /*
        A clipboard IMAGE, which no key can carry on its own.

        Measured 2026-08-22: even the working paste key delivers `text/plain`
        only, and xterm's paste handler reads that and nothing else. The bytes
        live in the browser and the agent lives behind a pty on the server, so
        the panel is the only thing that can move them.

        Capture phase, and `preventDefault` + `stopPropagation` on OUR case
        only: xterm listens on the same subtree, so letting an image paste
        through as well would put the browser's own text rendering of it into
        the pty beside the path.
      */
      const onPaste = (ev: ClipboardEvent) => {
        const image = pastedImage(ev.clipboardData)
        if (!image) return
        ev.preventDefault()
        ev.stopPropagation()
        setPasted({ kind: 'sending' })
        void uploadPastedImage(image).then(result => {
          if (!result.ok) {
            setPasted({ kind: 'failed', reason: result.reason })
            window.clearTimeout(pasteNoticeTimer.current)
            pasteNoticeTimer.current = window.setTimeout(() => setPasted(null), 6000)
            return
          }
          setPasted(null)
          // One binary frame, the same shape `onData` sends. A trailing space and
          // NO newline: the reader decides what to write beside it and when to send.
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(new TextEncoder().encode(result.path + ' '))
          }
        })
      }
      el.addEventListener('paste', onPaste, true)

      dispose = () => {
        if (settleTimer !== undefined) window.clearTimeout(settleTimer)
        window.clearTimeout(copyNoticeTimer.current)
        window.clearTimeout(pasteNoticeTimer.current)
        el.removeEventListener('paste', onPaste, true)
        classWatch.disconnect()
        termRef.current = null
        copyRef.current = null
        observer.disconnect()
        el.removeEventListener('focusin', gained)
        el.removeEventListener('focusout', lost)
        // Leaving takes the keyboard with it: a tile left marked as typed-into
        // after its terminal is gone points at an agent that cannot receive a
        // keystroke.
        onFocusChange?.(false)
        typed.dispose()
        term.dispose()
      }
      if (disposed) { dispose(); ws.close() }
    })()

    return () => {
      disposed = true
      dispose?.()
      // Detach. The owner keeps the pty; requirement 5.4 makes this explicitly
      // not a stop, so nothing here touches the agent's lifetime.
      socket?.close()
    }
    // `label` only — and that now includes the file-link inputs, deliberately.
    // A terminal re-attaching because a file listing arrived would cost a replay
    // and a flicker for a link decoration; the provider is registered with
    // whatever was known when the terminal opened, and a listing that lands
    // later applies to the next one. Stated rather than silent, because the
    // symptom would be "some terminals have file links and some do not".
    //
    // Adding the callbacks here would tear down the socket and
    // re-attach every time the parent re-renders with a new closure — a reattach
    // storm that looks like a flickering terminal and costs a replay each time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [label])

  /*
    FILE REFERENCES — the second kind of link in this output.

    A URL opens in a tab (registered with the emulator above); a path opens in
    the file view. What counts as a path is `fileReference` in the lib, because
    it is fed by text whatever the agent ran produced: it refuses an absolute
    path outside this project, and refuses a relative one the project does not
    have. A link the framework may not read, or that 404s when clicked, is worse
    than plain text.

    Its own effect, and that is the fix rather than the tidy-up: the listing
    arrives after the terminal is already open, so registering this inside the
    socket effect would register it once, with nothing, and never again.
  */
  useEffect(() => {
    const term = termRef.current
    if (!term || !projectRoot || !knownFiles || knownFiles.size === 0 || !onOpenFile) return
    const open = onOpenFile
    const registration = term.registerLinkProvider({
      provideLinks(lineNumber, callback) {
        const row = term.buffer.active.getLine(lineNumber - 1)
        if (!row) { callback(undefined); return }
        const text = row.translateToString(true)
        const links: TerminalLink[] = []
        // Whitespace-separated tokens, with the column kept, so the underline
        // sits on the path and not on the sentence around it.
        const re = /\S+/g
        let m: RegExpExecArray | null
        while ((m = re.exec(text)) !== null) {
          const ref = fileReference(m[0], projectRoot, knownFiles)
          if (!ref) continue
          links.push({
            range: {
              start: { x: m.index + 1, y: lineNumber },
              end: { x: m.index + m[0].length, y: lineNumber },
            },
            text: m[0],
            /*
              CTRL (or CMD), and a plain click deliberately does nothing here.

              A path in this output is ordinary text most of the time, and the
              reader clicks in a terminal to focus it, to place a cursor, to
              select. Opening a file on every such click would take the screen
              somewhere nobody asked to go. The modifier is also what the reader
              was asked for, and what every editor uses for the same act.
            */
            activate: (event: MouseEvent) => { if (event.ctrlKey || event.metaKey) open(ref) },
          })
        }
        callback(links.length ? links : undefined)
      },
    })
    return () => registration.dispose()
  }, [projectRoot, knownFiles, onOpenFile, phase.kind])

  const stop = useCallback(async () => {
    setStopping(true)
    setStopError(null)
    try {
      const res = await fetch(`/api/fleet/agents/${encodeURIComponent(label)}/stop`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setStopError(String(body?.detail ?? `HTTP ${res.status}`))
        return
      }
      onClose()
    } catch (e) {
      setStopError(String((e as Error)?.message ?? e))
    } finally {
      setStopping(false)
      setStopConfirm(false)
    }
  }, [label, onClose])

  /*
    THE STATUS ROW, WRITTEN ONCE AND PLACED TWICE.

    `merged` changes three things and no more: the word *terminal* goes (the
    tile's title bar already names the agent, and the row is beside its name),
    the right-hand group stops pushing itself to the far edge, and the row loses
    the margin it needed as a line of its own. Everything that has to be SAID —
    the phase, the cut replay, a second viewer, the copy outcome — is identical
    in both placements, deliberately: a compacted row that could say less would
    be a second answer to *what is this terminal doing*.
  */
  const merged = !!headerSlot
  /*
        ONE row, and it does NOT wrap — asked for 2026-08-19: *"latszik hogy sok
        helyet elfoglal az agent felső menüsora még a terminal nezet előtt, ezt
        kompaktálni kell. 1 sor elég kellene legyen ikonokkal"*. It used to be
        two: `flex-wrap` plus an `ml-auto` control block meant the three
        sentences dropped onto a line of their own, so five rows stood between
        the tile's title and the terminal.

        ## What stays visible, and why it is not a style choice

        `ui-quality.md`: compaction must never hide a failure. So the split here
        is not text-vs-icon, it is **caveat vs detail**:

        - The PHASE always shows, in its own colour — `connecting…`, `live`,
          a refusal, a close reason. A terminal whose state is one disclosure
          away is a terminal that looks attached while it is not.
        - The two amber facts — a replay whose head was cut, and a second viewer
          who sees your keystrokes — stay as coloured icons. An alarm in a
          tooltip is not an alarm; it is something you have to already suspect.
        - Only the plain numbers move behind the toggle: the label and the byte
          count. Neither is wrong when unseen.
  */
  const header = (
      <div
        className={`flex items-center gap-1.5 min-w-0${merged ? '' : ' mb-1.5'}`}
        data-fleet-terminal-header={merged ? 'merged' : 'own-row'}
      >
        {!merged && <span className="text-xs text-fg-strong shrink-0">terminal</span>}

        {phase.kind === 'connecting' && (
          <span className="text-xs text-sky-400 shrink-0" data-fleet-terminal-phase="connecting">connecting…</span>
        )}
        {phase.kind === 'attached' && (
          <>
            <span className="text-xs text-emerald-400 shrink-0" data-fleet-terminal-phase="attached">live</span>
            {/* Rendered from the acknowledgement, not from a guess: a replay that
                quietly lost its head reads as a session that began there. The
                sentence is unchanged — it moved from the row into the icon's
                accessible name, so nothing that had to be SAID is now unsaid. */}
            {phase.ack.replay_truncated && (
              <IconButton
                icon={Scissors}
                tone="amber"
                testId="replay-truncated"
                mark={{ 'data-fleet-terminal-replay-truncated': 'yes' }}
                label="the start of the buffer was cut — this replay does not begin where the session began"
              />
            )}
            {phase.ack.viewers > 1 && (
              <IconButton
                icon={Eye}
                tone="amber"
                testId="viewers"
                mark={{ 'data-fleet-terminal-viewers': String(phase.ack.viewers) }}
                label={`${phase.ack.viewers} watching — somebody else is on this same terminal and sees what you type`}
              />
            )}
          </>
        )}
        {phase.kind === 'refused' && (
          <span className="text-xs text-red-400 truncate" data-fleet-terminal-phase="refused">
            did not open: {phase.reason}
          </span>
        )}
        {phase.kind === 'closed' && (
          <span className="text-xs text-amber-400 truncate" data-fleet-terminal-phase="closed">{phase.reason}</span>
        )}

        {/*
          COPY, and the caveat that goes with it — B-60.

          Both are icons in the row that already exists rather than a new line:
          the header is already too tall (B-61), and `ui-quality.md` asks for
          compaction that hides nothing. What must not be hidden here is the
          Shift caveat, so it is a coloured icon while the agent holds the mouse
          and absent when it does not — the state itself, taken from xterm.
        */}
        <IconButton
          icon={Copy}
          testId="copy"
          mark={{ 'data-fleet-terminal-copy': 'yes' }}
          label="copy the selection (Ctrl+C while text is selected, or Ctrl+Insert) · paste with Ctrl+V — with nothing selected Ctrl+C still interrupts the agent"
          onClick={() => copyRef.current?.()}
        />
        {mouseTaken && (
          <IconButton
            icon={MousePointerClick}
            tone="amber"
            testId="mouse-taken"
            mark={{ 'data-fleet-terminal-mouse-taken': 'yes' }}
            label="the agent is reading the mouse — hold Shift while dragging to select text"
          />
        )}
        {copied && (
          <span
            className={`text-xs shrink-0 ${copied.ok ? 'text-emerald-400' : 'text-amber-400'}`}
            data-fleet-terminal-copied={copied.ok ? 'yes' : 'no'}
          >
            {copied.ok ? `copied ${copied.chars} chars` : `not copied: ${copied.reason}`}
          </span>
        )}
        {/*
          The paste notice exists for the two states the terminal itself cannot
          show: an upload on its way, and one that failed. Success says nothing —
          the path appearing in the prompt is the receipt, and the header is
          already too tall (B-61).
        */}
        {pasted && (
          <span
            className={`text-xs shrink-0 ${pasted.kind === 'sending' ? 'text-slate-400' : 'text-amber-400'}`}
            data-fleet-terminal-pasted={pasted.kind}
          >
            {pasted.kind === 'sending'
              ? 'sending the image…'
              : `image not sent: ${pasted.reason}`}
          </span>
        )}

        {/* The details, on request — *"esetleg lenyitható részletekkel"*. */}
        <IconButton
          icon={details ? ChevronDown : ChevronRight}
          testId="details"
          active={details}
          label={details ? 'hide the attachment details' : 'the terminal label and how much screen was replayed'}
          onClick={() => setDetails(d => !d)}
        />

        <span className={`flex items-center gap-0.5 shrink-0${merged ? '' : ' ml-auto'}`}>
          {/* Two controls, never one. Requirement 5.4: closing the view is not a
              stop, so the stop has to be its own act — and it still says so, in
              the accessible name that replaced the sentence. The confirm step is
              what an icon on its own could not carry, so it is kept: the first
              click arms, the second acts. */}
          {stopConfirm ? (
            <IconButton
              icon={CircleStop}
              tone="amber"
              testId="stop-confirm"
              active
              mark={{ 'data-fleet-terminal-stop-confirm': 'armed' }}
              label={stopping ? 'stopping…' : 'sure? stop it — the process ends, which is not the same as closing this view'}
              onClick={() => { if (!stopping) void stop() }}
            />
          ) : (
            <IconButton
              icon={CircleStop}
              testId="stop"
              mark={{ 'data-fleet-terminal-stop': 'armable' }}
              label="stop the agent — a separate, explicit act"
              onClick={() => setStopConfirm(true)}
            />
          )}
          {onToggleFull && (
            <IconButton
              icon={full ? Minimize2 : Maximize2}
              testId="full"
              active={full}
              mark={{ 'data-fleet-terminal-full': full ? 'on' : 'off' }}
              label={full
                ? 'back to the grid — the terminal stays attached, nothing is stopped or reconnected'
                : 'show this agent alone, filling the panel — the other agents are counted in the header, not silently dropped'}
              onClick={onToggleFull}
            />
          )}
          <IconButton
            icon={X}
            testId="close"
            mark={{ 'data-fleet-terminal-close': 'yes' }}
            label="close (the agent keeps running) — detach only, and you can attach here again later"
            onClick={onClose}
          />
        </span>
      </div>
  )

  return (
    <div
      className={`flex-1 min-h-0 flex flex-col${
        merged ? ' mt-1.5' : ' border-t border-surface-line mt-3 pt-2'}`}
      data-fleet-terminal={label}
      data-fleet-own-surface="terminal"
    >
      {headerSlot ? createPortal(header, headerSlot) : header}

      {details && (
        <div className="text-xs text-fg-ghost mb-1.5 flex items-baseline gap-2 flex-wrap" data-fleet-terminal-details>
          <span className="truncate max-w-[24rem]">{label}</span>
          {phase.kind === 'attached' && (
            <span className="tabular-nums" title="How much of the screen was replayed when this view attached.">
              {phase.ack.replayed_bytes} bytes replayed
            </span>
          )}
        </div>
      )}

      {stopError && (
        <div className="text-xs text-red-400 mb-1">the stop failed: {stopError}</div>
      )}

      <div
        ref={host}
        data-fleet-terminal-host
        /* Full screen fills what the card gives it, rather than taking a guessed
           fraction of the viewport. `62vh` was that guess, and it is why the
           maximised agent stopped ~100 px short of the bottom — raised
           2026-08-19: *"agent maximize nem nyitja ki teljesen az aljáig"*. No
           single fraction can be right: the strip above this varies with the
           header, the waiters and the modules panel, so the only correct height
           is the one that is left. The `ResizeObserver` above refits xterm, so a
           flexible box is not a problem for the terminal itself. */
        /* `flex-[1_1_12rem] min-h-0`, and the two halves are one decision — B-29.
           12rem used to be a `min-height`, i.e. a floor nothing could take back.
           In the grid that is right: the card is content-sized and the floor is
           what gives the terminal its size at all. In the enlarged card it is
           not: that card is a `flex-1` child of a chain that ends in
           `overflow: hidden`, so a floor larger than the room left does not make
           the terminal bigger, it pushes its bottom out of the card — measured
           2026-08-20 at a 440 px window, last row 4 of 14 px, and at 400 px gone
           entirely with the page unable to scroll to it.

           As a flex BASIS the same 12rem is a preference: it still contributes
           192 px to a content-sized card, and it yields when there is less room
           rather than overflowing. The alternative — letting the card scroll —
           was rejected: it keeps the floor and puts the status line below a fold
           the reader has to discover, which is the shape `ui-quality.md`
           forbids. A short terminal is honest; a truncated one is not. */
        className="flex-[1_1_12rem] min-h-0 rounded border border-surface-edge overflow-x-auto overflow-y-hidden bg-[#0b0f14]"
      />
    </div>
  )
}
