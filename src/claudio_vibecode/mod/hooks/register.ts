import type { Hook, Register } from 'claude-code'

import { type Attachment, parseVibeArgs, summaryOf, withAttachments } from './args'

const USAGE =
  'Usage: /vibe [on|off|qr|status|devices|revoke <id>|update [check|on|off]]'

type Dollar = Parameters<Hook<'turn.start'>>[0]

// Everything with an OS-specific job (the web hub, the voice key, pairing) lives in the
// `claudio-vibecode` Python package; this mod forwards events to the hub on loopback and carries
// out what the phone asked for. CLAUDIO_VIBECODE_PYTHON is set by `install-mod`.
async function python($: Dollar) {
  try {
    return (await $.env.get('CLAUDIO_VIBECODE_PYTHON')) ?? 'python'
  } catch {
    return 'python'
  }
}

async function cli($: Dollar, args: string[], timeoutMs = 15000) {
  const exe = await python($)
  try {
    return await $.process.run([exe, '-m', 'claudio_vibecode', ...args], { timeoutMs })
  } catch (error) {
    $.ui.log(`claudio-vibecode: ${String(error)}`, { to: 'debug' })
    return undefined
  }
}

async function sessionId($: Dollar) {
  try {
    return await $.session.id()
  } catch {
    return 'default' // only when the engine cannot name the session (tests)
  }
}

type Hub = { port: number; token: string; pid: number }
type PhoneCommand =
  | { type: 'prompt'; text: string }
  | { type: 'cancel' }
  | { type: 'submit'; text?: string; attachments?: Attachment[] }
  | { type: 'setdraft'; text: string }
  | { type: 'mute'; on: boolean }
type Polled = { commands: PhoneCommand[]; known: boolean }

let hub: Hub | undefined
let currentTurn: string | undefined
let tries = 0
let busy = false
let lastDraft = ''

async function hubCall($: Dollar, method: 'GET' | 'POST', path: string, body?: unknown) {
  if (!hub) return undefined
  try {
    const res = await $.http.fetch(`http://127.0.0.1:${hub.port}${path}`, {
      method,
      headers: { 'X-Claudio-Mod': hub.token, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    return res.ok ? JSON.parse(res.text) : undefined
  } catch {
    hub = undefined // the hub went away; the next tick looks for it again
    return undefined
  }
}

async function registerWithHub($: Dollar) {
  let cwd = ''
  try {
    cwd = String(await $.session.cwd())
  } catch {
    /* unnamed session */
  }
  let term = ''
  try {
    term = (await $.env.get('TERM_PROGRAM')) ?? ''
  } catch {
    /* unknown terminal */
  }
  await hubCall($, 'POST', '/api/mod/register', {
    session: await sessionId($),
    name: cwd.split(/[\\/]/).filter(Boolean).pop() ?? '',
    cwd,
    term,
    pid: hub?.pid ?? 0,
  })
}

async function connect($: Dollar) {
  const found = await cli($, ['info'], 8000)
  if (!found || found.exitCode !== 0) return
  try {
    const info = JSON.parse(found.stdout) as { port: number; token: string; pid?: number }
    hub = { port: info.port, token: info.token, pid: info.pid ?? 0 }
  } catch {
    return
  }
  await registerWithHub($)
}

function post($: Dollar, event: { kind: string; text?: string; summary?: string; status?: string }) {
  if (!hub) return
  void sessionId($).then(session => hubCall($, 'POST', '/api/mod/event', { session, ...event }))
}

async function tick($: Dollar) {
  if (busy) return
  busy = true
  try {
    if (((await $.store.get('on')) ?? false) !== true) {
      hub = undefined
      return
    }
    if (!hub) {
      if (tries++ % 10 !== 0) return // look for the hub about every 10 s
      await connect($)
      if (!hub) return
    }
    const session = await sessionId($)
    const polled = (await hubCall($, 'GET', `/api/mod/poll?session=${encodeURIComponent(session)}`)) as
      | Polled
      | undefined
    if (!polled) return
    if (!polled.known) await registerWithHub($)
    for (const command of polled.commands) {
      if (command.type === 'prompt') {
        void $.prompt.submit({ text: command.text, asUser: true }).catch(() => undefined)
      } else if (command.type === 'submit') {
        // Send the text from the phone (or, failing that, the prompt box), as pressing Enter would.
        const draft = command.text?.trim() || (await $.prompt.read().catch(() => undefined))?.text.trim()
        if (draft || command.attachments?.length) {
          await $.prompt.fill({ text: '', mode: 'replace' }).catch(() => undefined)
          lastDraft = ''
          void $.prompt
            .submit({ text: withAttachments(draft ?? '', command.attachments), asUser: true })
            .catch(() => undefined)
        }
      } else if (command.type === 'mute') {
        // The sound switch belongs to claudio-tts; ask it the way a person would.
        await $.command
          .run({ command: 'tts', args: command.on ? 'mute' : 'unmute' } as never)
          .catch(() => undefined)
      } else if (command.type === 'setdraft') {
        lastDraft = command.text // the phone's own edit: do not echo it back
        await $.prompt.fill({ text: command.text, mode: 'replace' }).catch(() => undefined)
      } else if (currentTurn) {
        await $.turn.abort({ turnId: currentTurn }).catch(() => undefined)
      }
    }
    // Show the phone what is in the prompt box, so a dictated message can be read before it is sent.
    const box = await $.prompt.read().catch(() => undefined)
    if (box && box.text !== lastDraft) {
      lastDraft = box.text
      await hubCall($, 'POST', '/api/mod/draft', { session, text: box.text })
    }
  } finally {
    busy = false
  }
}

// Once a day (the Python side caches), say if a newer release exists. Never installs anything.
async function noticeUpdate($: Dollar) {
  if (((await $.store.get('updateCheck')) ?? true) !== true) return
  const found = await cli($, ['update', '--quiet'], 8000)
  if (found?.stdout.trim()) $.ui.status('vibecode update available: /vibe update')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'vibe',
      description: 'Control Claude from your phone: /vibe [on|off|qr|status|devices|revoke|update]',
    })
    $.clock.every(1000, () => tick($))
    await noticeUpdate($)
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    currentTurn = e.turnId
    post($, { kind: 'prompt', text: e.text, status: 'working' })
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      currentTurn = undefined
      post($, { kind: 'reply', text: e.answer, summary: summaryOf(e.answer), status: 'idle' })
    }
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    await hubCall($, 'POST', '/api/mod/unregister', { session: await sessionId($) })
    return next(e)
  })

  on('command.run', { command: 'vibe' }, async ($, e) => {
    const cmd = parseVibeArgs(e.args)
    if (!cmd) return { text: USAGE }

    if (cmd.kind === 'on' || cmd.kind === 'qr') {
      await $.store.set('on', true)
      const started = await cli($, ['start'], 20000)
      if (!started || started.exitCode !== 0) {
        return { text: started?.stderr.trim() || started?.stdout.trim() || 'Could not start vibecode.' }
      }
      tries = 0
      await connect($)
      const shown = await cli($, ['qr', ...(cmd.kind === 'qr' && cmd.invert ? ['--invert'] : [])], 20000)
      return { text: shown?.stdout.trim() || shown?.stderr.trim() || 'Vibecode is on.' }
    }
    if (cmd.kind === 'off') {
      await $.store.set('on', false)
      await hubCall($, 'POST', '/api/mod/unregister', { session: await sessionId($) })
      hub = undefined
      const stopped = await cli($, ['stop'])
      return { text: stopped?.stdout.trim() || 'Vibecode is off.' }
    }
    if (cmd.kind === 'update') {
      if (cmd.value === 'on' || cmd.value === 'off') {
        await $.store.set('updateCheck', cmd.value === 'on')
        return { text: `Update check at session start: ${cmd.value}` }
      }
      // Typing /vibe update is the approval; `check` only looks.
      const done = await cli($, cmd.value === 'check' ? ['update', '--check'] : ['update', '--yes'], 300000)
      return { text: done?.stdout.trim() || done?.stderr.trim() || 'Could not run the update.' }
    }
    const args =
      cmd.kind === 'revoke' ? ['revoke', cmd.value] : [cmd.kind]
    const done = await cli($, args)
    return { text: done?.stdout.trim() || done?.stderr.trim() || 'Could not run that.' }
  })
}
