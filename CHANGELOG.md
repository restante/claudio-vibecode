# Changelog

## Unreleased

- **Removed the preset reply pills** (continue, yes, no, ...). Type or speak instead.
- **Attachments**: an Attach button (a paperclip) in the text box attaches photos and files (camera, photo library, files), and pasting a copied picture into the box works too. Photos are shrunk on the phone first. The files are saved in `.claudio-uploads/` in the session's project folder (git-ignored, deleted after 24 hours) and Claude is told where they are.
- **Notifications**: a bell in the top corner. When Claude replies while the page is in the background, the phone shows a notification (tap it to come back). Needs HTTPS (the Tailscale address) and only works while the page is still alive: Android keeps it for a while, and it lasts longer with Output on Phone; on iPhone add the page to the Home Screen first.
- **Read aloud**: a small speaker icon on each Claude message speaks it through claudio-tts, on the phone or the computer as Output is set. Tap again to stop. Uses claudio-tts's default voice and volume.
- **Mic and Output toggles** (PC or Phone each) above the Speak button, with the mute icon next to Output.
  Mic PC: tap to start and tap to stop on the computer's mic. Mic Phone: tap to speak on the phone's mic (needs Tailscale HTTPS).
  Output Phone: voice on the phone only. Replaces the Hear on phone chip.
- **Working row**: while Claude is busy, the conversation ends with "Claude is working…" and the time so far, with the Stop button next to it. The Stop button in the footer is gone.
- **Removed the Computer speakers chip.** Output Phone now keeps the computer quiet.
- **Removed Approve on phone** (`/vibe away`, OK/Deny cards, the risky-command rules). Use Claude Code's own
  permission modes (plan, auto and so on) instead; permission asks now show only at the keyboard.
- **Phone page look**: warm cream and clay colors with light and dark themes. Clearer labels: a speaker icon for voice on or off, *Send* (was Submit).
- **Speak**: one mic button. Phone mic: speak into the phone and the text lands in the box. Needs Tailscale with HTTPS certificates;
  `/vibe` serves the page through `tailscale serve` on port 8443. `status` and `doctor` say why it is off.
  The browser's speech service (Apple/Google) hears the audio.

## 0.1.0

First release. Spun off from claudio-tts so it can have its own life cycle.

- Local web hub for your phone: transcript per session, one editable text box mirrored with Claude's prompt box,
  Submit, Stop, Away mode with tool approvals (exact command shown, second tap for risky ones).
- QR pairing with one-time codes and revocable per-device tokens.
- **Hold to talk** presses Claude Code's voice key on the computer (macOS, Windows, Linux with xdotool).
- **Listen**: Claude's speech from claudio-tts plays on the phone, with a Mac-speakers switch.
- Sound on/off per session (through claudio-tts), haptic feedback on iPhone and Android, pinned header.
- `/vibe` command, `claudio-vibecode` CLI, one-line installers for macOS and Windows, opt-in `/vibe update`.
