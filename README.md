<div align="center">

# 📱 claudio-vibecode

### Run Claude Code from your phone. Read it, answer it, approve it, talk to it, hear it.

For vibe coders who don't sit at the monitor all day: start a task, grab a coffee, and keep going from a local web page on your phone. No native app, no account, nothing leaves your network.

[![CI](https://github.com/restante/claudio-vibecode/actions/workflows/ci.yml/badge.svg)](https://github.com/restante/claudio-vibecode/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/macOS-supported-blue) ![Windows](https://img.shields.io/badge/Windows-beta-orange) ![Phones](https://img.shields.io/badge/iPhone%20%2B%20Android-browser-lightgrey)

</div>

---

## ✨ What you get

| On your phone | How |
| --- | --- |
| **See the conversation** | Every Claude Code session on your computer, with transcript and spoken summaries |
| **Send a message** | One text box that mirrors Claude's prompt box. Dictate with the keyboard mic or **Hold to talk**, edit, then **Submit** |
| **Stop Claude** | One tap interrupts what it is doing |
| **Approve tool calls** | In *Away* mode Claude's permission asks go to your phone with the exact command. Risky ones (`rm`, `git push`, `curl`, writes outside the project) need a second tap |
| **Dictate** | Speak into the phone and the text lands in the box. Only shown with [Tailscale](https://tailscale.com) and HTTPS certificates turned on; the browser's own speech service (Apple/Google) hears the audio |
| **Hold to talk** | Presses Claude Code's voice key on your computer for as long as you hold the button |
| **Hear Claude** | Claude's voice plays on the phone (needs [claudio-tts](https://github.com/restante/claudio-tts)). Mute the Mac speakers and listen on the phone only |
| **Feel it** | Haptic feedback on taps, Submit, Stop and approvals (vibration on Android, a light tick on iPhone) |

Works on **iPhone and Android** in the phone's normal browser. Pair once with a **QR code**.

## 🚀 Install

You need [Claude Code](https://claude.com/claude-code) with mods support and about 1 GB of free disk for the voice model (installed by claudio-tts, which this installer fetches for you).

**macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.sh | bash
```

**Windows (PowerShell, beta)**

```powershell
irm https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.ps1 | iex
```

Then restart Claude Code and type:

```
/vibe
```

It starts the hub and shows a QR code. Scan it with your phone camera (same Wi-Fi). That's it.

## 🎮 Commands

| Command | What it does |
| --- | --- |
| `/vibe` or `/vibe on` | Start the hub and show a QR code to pair a phone |
| `/vibe qr` | A fresh QR code (for another phone) |
| `/vibe status` | Address, paired phones, connected sessions, voice-button readiness |
| `/vibe away on` · `off` | Send tool permission asks to the phone instead of the dialog at the keyboard |
| `/vibe devices` · `revoke <id>` | List paired phones · remove one |
| `/vibe off` | Stop the hub and close the port |
| `/vibe update` | Install the newest release. `/vibe update check` only looks, `/vibe update off` stops the daily check |

On the phone page: **Sound** (this session's speech on/off), **Listen** (play Claude's voice on this phone), **Mac speakers** (keep the computer quiet while you listen), **Away**.

## 🔊 Hearing Claude on the phone

claudio-vibecode plugs into [claudio-tts](https://github.com/restante/claudio-tts) as an extra audio output. Tap **🎧 Listen** once (browsers need a tap before they allow sound) and every spoken reply plays on the phone too, whatever your `/tts device` setting is. `/tts device phone` plays on the phone only, and the **Mac speakers** chip keeps the computer quiet.

## 🔐 Security: please read

A paired phone can make Claude run tools on your computer, so treat it like a keyboard.

- Off until you run `/vibe`. It stops itself after 8 idle hours, and `/vibe off` closes the port at once.
- The QR holds a one-time code (5 minutes). The phone swaps it for its own token, stored hashed. Revoke any time.
- Every route needs that token; the pairing page only answers on the computer itself.
- The connection is plain `http` on your Wi-Fi: use a network you trust. For another network or encryption use [Tailscale](https://tailscale.com); `/vibe status` prints the Tailscale address when it is running.
- The page can't use the phone's microphone over plain `http` (browsers require HTTPS for that). Use the keyboard's dictation key, or **Hold to talk**, which uses the computer's mic.

## 🧩 How it works

```mermaid
flowchart LR
  C["Claude Code session"] -- "events (loopback)" --> H["claudio-vibecode hub<br/>(local web server)"]
  H -- "prompt, stop, approve, hold key" --> C
  P["Phone browser"] <-- "page, live updates, audio clips" --> H
  T["claudio-tts"] -- "speech clips" --> H
```

A small mod forwards each session's prompts and replies to the hub on `127.0.0.1` and carries out what the phone asks for (`$.prompt.submit`, `$.turn.abort`, a `tool.check` hook for approvals). The hub serves the phone page and relays Claude's speech from claudio-tts as short audio clips. See [docs/how-it-works.md](docs/how-it-works.md).

## 🖥️ Platforms

macOS is the tested platform. Windows is **beta** (automated tests only; see [docs/windows.md](docs/windows.md)). Linux is best effort.

## 🐞 Report a bug · 🤝 Contribute

Open an [issue](https://github.com/restante/claudio-vibecode/issues) (`claudio-vibecode doctor` output helps) or send a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

## 🗑️ Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.sh | bash -s -- --uninstall
```

This removes claudio-vibecode and leaves claudio-tts alone.

## 🙏 Credits

- My friend [Donato Antonini](https://www.linkedin.com/in/donato-antonini-47b18a48/), for the brainstorming and the idea.
- [claudio-tts](https://github.com/restante/claudio-tts) and [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) for the voice.

## 📄 License

MIT. See [LICENSE](LICENSE).
