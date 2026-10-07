<div align="center">

# Claudio vibecode

### Vibe code with your voice, from anywhere.

Talk to Claude Code from your phone, show it a photo or a file, and hear it talk back. Start a task at your desk, walk away, and keep the conversation going with no keyboard and no monitor.

[![CI](https://github.com/restante/claudio-vibecode/actions/workflows/ci.yml/badge.svg)](https://github.com/restante/claudio-vibecode/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/macOS-supported-blue) ![Windows](https://img.shields.io/badge/Windows-beta-orange) ![Phones](https://img.shields.io/badge/iPhone%20%2B%20Android-browser-lightgrey)

<img src="docs/images/hero.png" alt="The Claudio vibecode page on a phone: the conversation, Claude working with a Stop button, and the same page in dark mode" width="860">

</div>

## Why

Claude Code does its best work when you let it run. But a long task shouldn't keep you chained to the monitor.

Claudio vibecode is a free, open-source remote control for Claude Code, built around your voice. Use Claude Code from your phone, on iPhone or Android: say what you want, attach a photo or a file, hear Claude's answer read aloud, and say what's next. Claude Code remote, Claude Code mobile and Claude Code voice, in one small package.

It puts a small web page on your phone that is connected to the Claude Code sessions on your computer. Nothing to install on the phone, no account, and nothing leaves your network.

### Voice, front and center

- **Speak your prompts.** Tap **Speak**, say it, tap again. Your words land in the text box, so you can fix a word before you send. Use your phone's mic, or your computer's.
- **Hear every reply.** Claude's short spoken summary plays as it finishes, on your phone or on your computer. Tap the speaker icon on any message to hear it again.
- **Keep the loop going.** Speak, listen, speak. Vibe code on a walk, in the car park, or on the sofa.
- **Choose where you talk and listen.** Mic and speakers are separate switches, each on PC or Phone.

### And everything else you need

- **Read** what Claude is doing, across every session you have open.
- **Show Claude what you see.** Attach a photo, a screenshot or a file from your phone, or paste a copied picture.
- **Type** when talking isn't an option. Your message arrives as if you had typed it at the keyboard.
- **Stop** a task that is going the wrong way, with one tap.
- **Get notified** when Claude replies while the page is in the background.

## Install in a minute

You need [Claude Code](https://claude.com/claude-code) with mods support and about 1 GB of free disk for the voice model. The installer fetches everything else, including [claudio-tts](https://github.com/restante/claudio-tts), which provides Claude's voice.

**macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.sh | bash
```

**Windows (PowerShell, beta)**

```powershell
irm https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.ps1 | iex
```

Then restart Claude Code. That's the whole install.

## Pair your phone

Pairing takes about ten seconds, and you only do it once per phone.

<div align="center">
<img src="docs/images/pairing.png" alt="Typing /vibe on in Claude Code shows a QR code to scan with the phone's camera" width="760">
</div>

1. In any Claude Code session, type `/vibe on`. It starts the hub and shows a QR code. A larger one opens in your browser too.
2. Open your phone's camera and point it at the code. Your phone and computer need to be on the same Wi-Fi.
3. Tap the link. The page opens, already paired.

The code works once and expires in 5 minutes. Need another phone? Type `/vibe qr` for a fresh one. Done for the day? `/vibe off` closes everything.

## Take it with you

On its own, the page works on your home or office Wi-Fi. To use it from the train, a café, or the other side of town, add [Tailscale](https://tailscale.com). It connects your phone and your computer over a private, encrypted network, so there's nothing to open on your router and nothing exposed to the internet. Tailscale has a free plan for personal use.

1. **Install Tailscale** on your computer and on your phone, and sign in to both with the same account.
2. **Turn on HTTPS.** In the Tailscale admin console, under DNS, enable MagicDNS and HTTPS Certificates. It's a one-time switch.
3. **Run `/vibe on`.** Claudio vibecode notices Tailscale and serves the page securely at `https://<your-computer>.<your-tailnet>.ts.net:8443`. The QR code points there.
4. **Scan it with your phone**, with the Tailscale app connected, and pair as above.

From then on, open the same address from anywhere with the Tailscale app on. Your computer needs to be awake with Claude Code running. `/vibe status` shows the address and confirms **Phone mic: ready**.

A bonus: the secure address is what unlocks the **Phone mic** and **notifications**, so Tailscale gives you the full experience, not just the distance.

> **Pair using the secure address.** The Wi-Fi address and the Tailscale address are different places to your phone, and each needs its own pairing. Pair through the Tailscale one and your phone stays paired wherever you are.

## A quick tour

<table>
<tr>
<td width="300"><img src="docs/images/idle.png" alt="The conversation view with a message, two attached files, the Send button, Mic and Out controls, and a Speak button" width="280"></td>
<td valign="top">

**Your sessions, at the top.** Every Claude Code session on your computer is one tap away. A green dot means idle, amber means Claude is working.

**The conversation.** Your messages and Claude's replies. Replies show Claude's short spoken summary first. Tap **Show full reply** for the whole thing, or the small speaker icon to hear it read aloud.

**One text box.** It mirrors the prompt box on your computer. Type, or tap **Speak** and talk, then edit before you send. **Clear** appears only when there is something to clear, and **Send** appears only when there is something to send.

**Attach anything.** Tap **Attach** to take a photo, pick one from your library, or choose a file. You can also paste a copied picture into the box. Ask Claude about a screenshot, a crash log or a design, straight from your phone.

**Mic, Out, and mute.** Choose where you talk and where you listen. More on that below.

</td>
</tr>
<tr>
<td width="300"><img src="docs/images/working.png" alt="Claude is working: a row at the end of the conversation shows the time so far and a Stop button" width="280"></td>
<td valign="top">

**You always know when Claude is busy.** While it works, the conversation ends with a "Claude is working" row and the time so far. If it's heading the wrong way, tap **Stop**. It cancels the turn right away.

**Light and dark.** The page follows your phone's setting.

</td>
</tr>
</table>

## Talk and listen your way

Two independent choices sit right above the Speak button. The microphone icon is **Mic**, where you talk. The headphones icon is **Out**, where you listen. Each is **PC** (the monitor icon) or **Phone**.

| | PC | Phone |
| --- | --- | --- |
| **Mic** | Tap **Speak**, talk to your computer's mic through Claude Code's voice mode, tap again to stop | Tap **Speak**, talk to your phone's mic, tap again to stop |
| **Out** | Claude's voice plays on your computer | Claude's voice plays on your phone only, and the computer stays quiet |

The speaker icon next to them mutes Claude's voice for the current session.

Mix them however you like. Talk to your phone and listen on your computer. Or leave your computer entirely: Mic on Phone, Out on Phone.

> **Phone mic needs HTTPS.** Browsers only let a page use the microphone over a secure connection. With [Tailscale](https://tailscale.com) installed and HTTPS certificates enabled, `/vibe` serves the page securely and the Phone mic turns on by itself. Without it, use your keyboard's dictation key, or set Mic to PC. The speech is transcribed by your browser's speech service (Apple or Google), never by this project.

## Show Claude what you see

Point your phone at the problem. Attach a photo of an error on another screen, a screenshot of a bug, a crash log, a PDF spec or a design, then ask Claude about it.

1. Tap **Attach** (the paperclip) in the text box. Your phone offers Take Photo, Photo Library and Choose File. You can pick several.
2. Or **paste** a picture you've copied: long-press in the text box and tap Paste.
3. Each file appears as a small chip above Send, with a thumbnail and a cross to remove it. Add your question and tap **Send**.

Claude receives the files together with your message and reads them like any other file in your project. Photos are shrunk on your phone first, so a 12 MB photo uploads in a moment.

Files are saved in a `.claudio-uploads` folder inside your project. It's ignored by git and cleaned up after 24 hours. You can attach images, PDFs and text or code files, up to 8 per message and 20 MB each. More in [Secure by design](#secure-by-design).

## Know when Claude replies

Tap the bell in the top corner and allow notifications. When Claude replies while the page is in the background, your phone shows a notification. Tap it to come back.

This works through the page itself, with no push service involved, so there are two honest limits:

- It needs the secure (HTTPS) address, as above. Without it, the bell stays hidden.
- It works while the page is still alive. Android Chrome keeps it going for a while, longer when Out is set to Phone. On iPhone, open the page in Safari and use Share, then **Add to Home Screen**. iOS puts background pages to sleep quickly.

## Commands

| Command | What it does |
| --- | --- |
| `/vibe` or `/vibe on` | Start the hub and show a QR code to pair a phone |
| `/vibe qr` | A fresh QR code, for another phone |
| `/vibe status` | Address, paired phones, connected sessions, voice readiness |
| `/vibe devices` and `revoke <id>` | List paired phones, or remove one |
| `/vibe off` | Stop the hub and close the port |
| `/vibe update` | Install the newest release. `update check` only looks, `update off` stops the daily check |

## Secure by design

Letting a phone talk to Claude Code is a serious thing, so security is built in from the start, not added later. A paired phone can make Claude run tools on your computer, so it's treated like a keyboard: nobody gets near it unless you let them, and it stays in your hands.

**Why it's secure**

- **Closed until you open it.** Nothing runs until you type `/vibe`. `/vibe off` closes the port at once, and it shuts itself down after 8 idle hours.
- **Pairing you control.** The QR code holds a random, single-use code that expires in 5 minutes. Guessing is blocked too: pairing attempts are rate limited. The code is shown on your computer only, and the pairing page refuses anyone who isn't on that computer.
- **A key for every phone.** After pairing, each phone gets its own 256-bit random token. It's stored on your computer only as a hash, never in plain text, and the cookie is `HttpOnly` and `SameSite=Strict`. Lose a phone? `/vibe revoke` removes it immediately.
- **No open doors.** Every route needs that token, apart from the page itself. The routes used by Claude Code and by admin tools answer only on your own computer and need a separate secret.
- **Protected against other websites.** Actions need a custom header and a matching origin, so a page you happen to have open in another tab can't make your phone or your computer do anything.
- **Encrypted when you leave home.** With [Tailscale](https://tailscale.com), everything travels through a private, encrypted network and over HTTPS. There's no port forwarding, and nothing is exposed to the public internet.
- **Nothing leaves your network.** No cloud, no account, no analytics, no tracking. The page is one file with no external requests, so nothing else loads when you open it. The server uses only Python's standard library, which keeps the code small and easy to audit.
- **Attachments are boxed in.** Files you send are saved in a `.claudio-uploads` folder inside the session's project, ignored by git and deleted after 24 hours. Only images, PDFs and text or code files are accepted, up to 20 MB each. Names are cleaned so a file can't escape that folder, and your phone never chooses a path: it can only refer to files the hub itself saved.
- **Open source.** It's MIT licensed, and every line is there for you to read.

**What to keep in mind**

- On plain Wi-Fi the connection is `http`, which isn't encrypted. Use a network you trust, or use Tailscale. `/vibe status` shows both addresses.
- Anyone holding a paired, unlocked phone can use it like your keyboard. Keep your phone locked, and revoke it if it's lost.

## How it works

```mermaid
flowchart LR
  C["Claude Code session"] -- "events (loopback)" --> H["claudio-vibecode hub<br/>(local web server)"]
  H -- "prompt, stop, voice key" --> C
  P["Phone browser"] <-- "page, live updates, audio" --> H
  T["claudio-tts"] -- "speech" --> H
```

A small mod inside Claude Code forwards each session's prompts and replies to the hub on `127.0.0.1`, and carries out what your phone asks for. The hub serves the phone page and relays Claude's voice from claudio-tts as short audio clips. The page is a single HTML file with no build step and no external requests. More in [docs/how-it-works.md](docs/how-it-works.md).

## Questions

**Does it work away from home?**
Yes, with [Tailscale](https://tailscale.com). See [Take it with you](#take-it-with-you).

**Do I need Tailscale?**
No. On the same Wi-Fi it works as is. Tailscale adds the Phone mic, notifications, and use from anywhere.

**Why does Speak with the PC mic ask for permission on my Mac?**
It presses Claude Code's voice key for you in the front window, so your terminal needs Accessibility access: System Settings, Privacy & Security, Accessibility. On Linux, install `xdotool`. Keep the screen unlocked.

**Can I send Claude a photo or a file?**
Yes. Tap **Attach**, or paste a copied picture. See [Show Claude what you see](#show-claude-what-you-see).

**Which phones work?**
iPhone and Android, in the phone's normal browser. Notifications on iPhone need Safari and a Home Screen page.

**What does it cost?**
Nothing. It's MIT licensed.

## Platforms

macOS is the tested platform. Windows is **beta**: automated tests only, see [docs/windows.md](docs/windows.md). Linux is best effort.

## Get involved

Found a bug? Open an [issue](https://github.com/restante/claudio-vibecode/issues). Output from `claudio-vibecode doctor` helps a lot. Pull requests are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.sh | bash -s -- --uninstall
```

This removes claudio-vibecode and leaves claudio-tts alone.

## Credits

- [claudio-tts](https://github.com/restante/claudio-tts) and [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) for the voice.

## License

MIT. See [LICENSE](LICENSE).
