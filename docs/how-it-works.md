# How claudio-vibecode works

Control Claude Code from your phone while you are away from the screen. It is a small web page served by your own
computer: no app, no account, nothing leaves your network.

```
/vibe on        start it and show a QR code (also opens a bigger one in your browser)
/vibe qr        a fresh QR code to pair another phone
/vibe status    address, paired phones, connected sessions
/vibe devices   list paired phones      /vibe revoke <id>   remove one
/vibe off       stop it and close the port
```

## What you get on the phone
- Every Claude session on the computer, with its transcript, the spoken summaries, and a "show full reply" tap.
- A message box. Messages arrive as if you typed them.
- **Stop** cancels the running turn.
- **Tap to speak** (Mic set to PC) holds the key Claude Code's voice mode listens to (space, with `voice.mode: hold`) on the
  computer from your first tap until the second (90 seconds at most). It presses that key in the front window, so the Claude terminal must be
  focusable and the screen unlocked. On macOS allow your terminal app in System Settings > Privacy & Security >
  Accessibility; on Linux install `xdotool` (X11).
- **Bell** turns on a notification when Claude replies and the page is in the background. It is raised by the page itself (a tiny service worker, `/sw.js`), so it needs HTTPS and the page must still be running: Android keeps it alive for a while, longer when Claude's voice plays on the phone; on iPhone add the page to the Home Screen. There is no push service, so a fully asleep page cannot notify.
- `/w` is the same page with huge buttons for a watch browser.

## Windows
Works on Windows 10/11 too: allow `python.exe` on private networks when the firewall asks. See
[windows.md](windows.md#phone-remote-on-windows).

## Security
A paired phone can make Claude run tools on your computer, so treat it like a keyboard.
- Off by default; only while you run `/vibe on`. It also stops itself after 8 idle hours.
- The QR holds a one-time code (5 minutes). The phone swaps it for its own token, stored hashed. Revoke any time.
- Every route needs that token; the page only answers your local network.
- The connection is plain `http` on your Wi-Fi: use a network you trust. For another network or encryption, use
  [Tailscale](https://tailscale.com): `/vibe status` prints the Tailscale address when it is running.

## Limits (v1)
The phone's own microphone (Mic set to Phone, **Tap to speak**) needs HTTPS, so it only appears when Tailscale is installed, connected and has HTTPS certificates enabled; `/vibe` then serves the page at `https://<name>.<tailnet>.ts.net:8443` through `tailscale serve`. The audio is heard by your browser's speech service (Apple or Google), not by this hub. Without Tailscale, use the keyboard's mic key, or set Mic to PC and hold to talk on the computer's mic. A notification when Claude finishes (ntfy for Apple Watch and Wear OS) is on the roadmap.
