const OPEN = '<!-- TTS_SUMMARY'
const CLOSE = 'TTS_SUMMARY -->'

/** The spoken summary of a reply (the TTS_SUMMARY block), or '' when it has none. */
export const summaryOf = (text: string): string => {
  const start = text.indexOf(OPEN)
  if (start === -1) return ''
  const rest = text.slice(start + OPEN.length)
  const end = rest.indexOf(CLOSE)
  return end === -1 ? '' : rest.slice(0, end).trim()
}

export type VibeCommand =
  | { kind: 'on' | 'off' | 'status' | 'devices' }
  | { kind: 'qr'; invert?: boolean }
  | { kind: 'away'; value: 'on' | 'off' }
  | { kind: 'revoke'; value: string }
  | { kind: 'update'; value?: 'check' | 'on' | 'off' }

/** Parses `/vibe` arguments; undefined when they make no sense. No argument turns it on. */
export const parseVibeArgs = (args: string): VibeCommand | undefined => {
  const [word = '', ...words] = args.trim().toLowerCase().split(/\s+/)
  const rest = words.join(' ')
  if (word === '' || word === 'on' || word === 'start') return { kind: 'on' }
  if (word === 'off' || word === 'stop') return { kind: 'off' }
  if (word === 'status') return { kind: 'status' }
  if (word === 'devices' || word === 'phones') return { kind: 'devices' }
  if (word === 'qr' || word === 'pair') return rest === 'invert' ? { kind: 'qr', invert: true } : { kind: 'qr' }
  if (word === 'away') return rest === 'on' || rest === 'off' ? { kind: 'away', value: rest } : undefined
  if (word === 'revoke') return rest ? { kind: 'revoke', value: rest } : undefined
  if (word === 'update' || word === 'upgrade') {
    if (rest === '') return { kind: 'update' }
    if (rest === 'check' || rest === 'on' || rest === 'off') return { kind: 'update', value: rest }
  }
  return undefined
}
