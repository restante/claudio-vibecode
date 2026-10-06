import { expect, mock, test } from 'claude-code/testing'

import { parseVibeArgs, summaryOf } from './args'

const ok = (stdout: string) => ({
  value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
})

test('summaryOf reads the TTS_SUMMARY block and is empty without one', () => {
  expect(summaryOf('Long answer.\n<!-- TTS_SUMMARY Short version. TTS_SUMMARY -->')).toBe('Short version.')
  expect(summaryOf('Plain reply.')).toBe('')
  expect(summaryOf('Hi <!-- TTS_SUMMARY never closed')).toBe('')
})

test('parseVibeArgs', () => {
  expect(parseVibeArgs('')).toEqual({ kind: 'on' })
  expect(parseVibeArgs('on')).toEqual({ kind: 'on' })
  expect(parseVibeArgs(' OFF ')).toEqual({ kind: 'off' })
  expect(parseVibeArgs('status')).toEqual({ kind: 'status' })
  expect(parseVibeArgs('qr')).toEqual({ kind: 'qr' })
  expect(parseVibeArgs('qr invert')).toEqual({ kind: 'qr', invert: true })
  expect(parseVibeArgs('away on')).toEqual({ kind: 'away', value: 'on' })
  expect(parseVibeArgs('away maybe')).toBeUndefined()
  expect(parseVibeArgs('revoke ab12')).toEqual({ kind: 'revoke', value: 'ab12' })
  expect(parseVibeArgs('revoke')).toBeUndefined()
  expect(parseVibeArgs('update check')).toEqual({ kind: 'update', value: 'check' })
  expect(parseVibeArgs('update off')).toEqual({ kind: 'update', value: 'off' })
  expect(parseVibeArgs('update maybe')).toBeUndefined()
  expect(parseVibeArgs('nope')).toBeUndefined()
})

test('/vibe on starts the hub, registers this session and shows the QR', async ($, on) => {
  mock.store(on)
  mock.env(on, { CLAUDIO_VIBECODE_PYTHON: '/py' })
  const argvs: string[][] = []
  on('process.run', async (_$, e) => {
    argvs.push([...e.argv])
    if (e.argv.includes('info')) return ok(JSON.stringify({ running: true, port: 4711, token: 'tok', pid: 1 }))
    if (e.argv.includes('qr')) return ok('SCAN ME http://192.168.1.2:4711/?pair=abc')
    return ok('')
  })
  const fetched: { url: string; token?: string }[] = []
  on('http.fetch', async (_$, e) => {
    fetched.push({ url: e.url, token: e.init?.headers?.['X-Claudio-Mod'] })
    return { value: { status: 200, ok: true, headers: {}, text: '{}' } }
  })
  const out = (await $.command.run({
    command: 'vibe',
    args: 'on',
    origin: { kind: 'composer' },
    presentation: { layout: 'main', columns: 80 },
  } as never)) as { text: string }
  expect(out.text).toContain('SCAN ME')
  expect(argvs.some(a => a.slice(0, 3).join(' ') === '/py -m claudio_vibecode' && a.includes('start'))).toBe(true)
  expect(fetched.some(f => f.url === 'http://127.0.0.1:4711/api/mod/register' && f.token === 'tok')).toBe(true)
})

test('an unknown /vibe argument prints the usage', async ($, on) => {
  mock.store(on)
  const out = (await $.command.run({
    command: 'vibe',
    args: 'nope',
    origin: { kind: 'composer' },
    presentation: { layout: 'main', columns: 80 },
  } as never)) as { text: string }
  expect(out.text).toContain('Usage')
})

test('without the hub a permission ask is left to the local dialog', async ($, on) => {
  mock.store(on)
  on('tool.check', () => ({ decision: 'ask' }))
  const verdict = await $.tool.check({ tool: 'Bash', input: { command: 'ls' } } as never)
  expect(verdict.decision).toBe('ask')
})
