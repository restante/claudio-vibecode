# Changelog

## 0.1.0

First release. Spun off from claudio-tts so it can have its own life cycle.

- Local web hub for your phone: transcript per session, one editable text box mirrored with Claude's prompt box,
  Submit, Stop, Away mode with tool approvals (exact command shown, second tap for risky ones).
- QR pairing with one-time codes and revocable per-device tokens.
- **Hold to talk** presses Claude Code's voice key on the computer (macOS, Windows, Linux with xdotool).
- **Listen**: Claude's speech from claudio-tts plays on the phone, with a Mac-speakers switch.
- Sound on/off per session (through claudio-tts), haptic feedback on iPhone and Android, pinned header.
- `/vibe` command, `claudio-vibecode` CLI, one-line installers for macOS and Windows, opt-in `/vibe update`.
