import { expect, test } from 'claude-code/testing'

const HOME = '/home/tester'
const ROOT = '/work/proj'
const OPTIN = `${HOME}/.config/set-core/feed-watch.json`
const STATE = `${HOME}/.config/set-core/feed-watch.state.json`
const PRESENTATION = { isFullscreen: true, columns: 160 }

type Files = Record<string, string>

function engine(on: any, files: Files, ran: string[], clock = 1_000_000, now = '2026-10-05 08:41', declared = true) {
  on('env.get', ($: any, e: any) => ({ value: e.name === 'HOME' ? HOME : undefined }))
  on('fs.read', ($: any, e: any) => {
    const text = files[e.path]
    if (text === undefined) throw new Error(`ENOENT ${e.path}`)
    return { value: text }
  })
  on('fs.write', ($: any, e: any) => {
    files[e.path] = e.text
    return { value: undefined }
  })
  on('fs.exists', ($: any, e: any) => ({ value: declared && e.path === `${ROOT}/.set/feed-watch.yaml` }))
  on('process.run', ($: any, e: any) => ({
    value: { exitCode: 0, stdout: e.argv[0] === 'date' ? `${now}\n` : `${ROOT}\n`, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('clock.now', () => ({ value: clock }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.close', () => ({ value: undefined }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('command.run', ($: any, e: any) => {
    ran.push(e.command)
    return { text: '' }
  })
}

const owner = (account = 'owner@example.com'): Files => ({
  [OPTIN]: JSON.stringify({ projects: { [ROOT]: { enabled: true, account, times: ['08:30', '18:30'] } } }),
  [`${HOME}/.claude.json`]: JSON.stringify({ oauthAccount: { emailAddress: 'owner@example.com' } }),
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the owner gets the pane, snooze writes this project's state (${surface})`, async ($, on) => {
    const files = owner()
    const ran: string[] = []
    engine(on, files, ran)
    await $.command.run({ command: 'feed-watch-pane', args: 'now', origin: { kind: 'composer' }, presentation: PRESENTATION })
    const ui = await $.ui.mount({ plugin: 'feed-watch-pane', surface, component: 'Pane', requestId: 'feed-watch', props: {} as never })
    expect(await ui.find({ key: 'run' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Chrome window to the front/ })).toBeDefined()
    await ui.press({ key: 'snooze' })
    const st = JSON.parse(files[STATE] ?? '{}').projects[ROOT]
    expect(st.snoozeUntil).toBe(1_000_000 + 3_600_000)
    expect(ran).toEqual([])
    await ui.unmount()
  })
}

test('another account: /feed-watch-pane now refuses', async ($, on) => {
  const files = owner('someone.else@example.com')
  engine(on, files, [])
  const r = await $.command.run({ command: 'feed-watch-pane', args: 'now', origin: { kind: 'composer' }, presentation: PRESENTATION })
  expect(JSON.stringify(r)).toContain('not switched on for this account')
})

test('Run now runs the feed-watch skill locally and marks the slot', async ($, on) => {
  const files = owner()
  const ran: string[] = []
  engine(on, files, ran, 5, '2026-10-05 18:31')
  await $.command.run({ command: 'feed-watch-pane', args: 'now', origin: { kind: 'composer' }, presentation: PRESENTATION })
  const ui = await $.ui.mount({ plugin: 'feed-watch-pane', surface: 'terminal', component: 'Pane', requestId: 'feed-watch', props: {} as never })
  await ui.press({ key: 'run' })
  expect(ran).toEqual(['feed-watch'])
  expect(JSON.parse(files[STATE] ?? '{}').projects[ROOT].handled).toEqual({ '2026-10-05 18:31': 'run' })
  await ui.unmount()
})

test('Switch off disables the opt-in for this project only', async ($, on) => {
  const files = owner()
  const doc = JSON.parse(files[OPTIN]!)
  doc.projects['/other'] = { enabled: true, account: 'owner@example.com' }
  files[OPTIN] = JSON.stringify(doc)
  engine(on, files, [])
  await $.command.run({ command: 'feed-watch-pane', args: 'now', origin: { kind: 'composer' }, presentation: PRESENTATION })
  const ui = await $.ui.mount({ plugin: 'feed-watch-pane', surface: 'terminal', component: 'Pane', requestId: 'feed-watch', props: {} as never })
  await ui.press({ key: 'off' })
  const after = JSON.parse(files[OPTIN]!).projects
  expect(after[ROOT].enabled).toBe(false)
  expect(after['/other'].enabled).toBe(true)
  await ui.unmount()
})

test('a project without the declaration gets no pane', async ($, on) => {
  const files = owner()
  engine(on, files, [], 1_000_000, '2026-10-05 08:41', false)
  const r = await $.command.run({ command: 'feed-watch-pane', args: 'now', origin: { kind: 'composer' }, presentation: PRESENTATION })
  expect(JSON.stringify(r)).toContain('does not declare feed-watch')
})
